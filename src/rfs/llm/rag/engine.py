"""
RAG Engine

검색 증강 생성(Retrieval Augmented Generation) 엔진 구현체입니다.
벡터 스토어와 LLM Manager, 프롬프트 템플릿을 통합하여 
지식 기반 질의응답 시스템을 제공합니다.
"""

from typing import List, Dict, Any, Optional, Union
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from rfs.hof.core import pipe
from .vector_store import VectorStore


@Service("llm_service")
class RAGEngine:
    """RAG (Retrieval Augmented Generation) 엔진
    
    벡터 검색과 LLM 생성을 결합하여 지식 기반 질의응답을 제공합니다.
    Result Pattern과 HOF 패턴을 완전히 지원합니다.
    """
    
    def __init__(
        self,
        llm_manager: 'LLMManager',
        vector_store: VectorStore,
        template_manager: Optional['PromptTemplateManager'] = None
    ):
        self.llm_manager = llm_manager
        self.vector_store = vector_store
        self.template_manager = template_manager
        
        # 기본 RAG 템플릿 등록
        if self.template_manager:
            self._register_default_templates()
    
    def _register_default_templates(self):
        """기본 RAG 템플릿들을 등록합니다"""
        try:
            # 기본 RAG 템플릿
            basic_rag_template = """다음 컨텍스트를 기반으로 질문에 답변해주세요.

컨텍스트:
{% for doc in context_documents %}
{{ doc.content }}
---
{% endfor %}

질문: {{ question }}

답변: 제공된 컨텍스트를 바탕으로 답변하겠습니다."""

            # 상세 RAG 템플릿
            detailed_rag_template = """다음 컨텍스트 정보를 참고하여 질문에 대해 상세히 답변해주세요.

참고 컨텍스트:
{% for doc in context_documents %}
📄 문서 {{ loop.index }}: {{ doc.metadata.get('title', '제목 없음') }}
{{ doc.content }}
{% if doc.metadata %}
메타정보: {{ doc.metadata }}
{% endif %}

---
{% endfor %}

질문: {{ question }}

{% if instruction %}
답변 지침: {{ instruction }}
{% endif %}

답변:"""

            # 요약 RAG 템플릿
            summary_rag_template = """다음 정보들을 종합하여 {{ question }}에 대해 간결하게 답변해주세요.

관련 정보:
{% for doc in context_documents %}
• {{ doc.content[:200] }}{% if doc.content|length > 200 %}...{% endif %}
{% endfor %}

요약 답변 ({{ max_words | default(100) }}단어 이내):"""

            # 비교 분석 RAG 템플릿
            comparative_rag_template = """여러 관점에서 {{ question }}에 대해 비교 분석해주세요.

참고 자료:
{% for doc in context_documents %}
관점 {{ loop.index }}:
{{ doc.content }}
{% if doc.metadata.source %}
출처: {{ doc.metadata.source }}
{% endif %}

{% endfor %}

비교 분석:
1. 공통점:
2. 차이점:
3. 결론:"""

            # 템플릿 등록
            templates = {
                "rag_basic": basic_rag_template,
                "rag_detailed": detailed_rag_template,
                "rag_summary": summary_rag_template,
                "rag_comparative": comparative_rag_template
            }
            
            for name, template in templates.items():
                self.template_manager.register_template(name, template)
                
        except Exception as e:
            # 템플릿 등록 실패는 치명적이지 않으므로 로그만 남김
            pass
    
    async def query(
        self,
        question: str,
        model: str,
        k: int = 5,
        template_name: str = "rag_basic",
        provider: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Result[Dict[str, Any], str]:
        """RAG 기반 질의응답
        
        Args:
            question: 질문
            model: 사용할 LLM 모델
            k: 검색할 문서 수
            template_name: 사용할 프롬프트 템플릿
            provider: LLM Provider 이름
            similarity_threshold: 유사도 임계값
            filter_metadata: 검색 시 사용할 메타데이터 필터
            **kwargs: LLM 생성 추가 파라미터
            
        Returns:
            Result[Dict[str, Any], str]: RAG 응답 결과
        """
        try:
            # 1. 관련 문서 검색
            if similarity_threshold:
                search_result = await self.vector_store.search_with_threshold(
                    query=question,
                    similarity_threshold=similarity_threshold,
                    max_results=k
                )
            else:
                search_result = await self.vector_store.similarity_search(
                    query=question,
                    k=k,
                    filter_metadata=filter_metadata
                )
            
            if search_result.is_failure():
                return search_result
            
            context_documents = search_result.unwrap()
            
            # 2. 컨텍스트가 없는 경우 처리
            if not context_documents:
                return Success({
                    "answer": "관련 정보를 찾을 수 없습니다. 다른 질문을 해보세요.",
                    "context_documents": [],
                    "question": question,
                    "context_count": 0
                })
            
            # 3. 프롬프트 생성 및 LLM 호출
            if self.template_manager:
                # 템플릿 사용
                generation_result = await self.template_manager.render_and_generate(
                    template_name=template_name,
                    llm_manager=self.llm_manager,
                    model=model,
                    variables={
                        "question": question,
                        "context_documents": context_documents,
                        **kwargs
                    },
                    provider=provider
                )
            else:
                # 기본 프롬프트 사용
                context_text = "\n---\n".join([doc["content"] for doc in context_documents])
                prompt = f"다음 컨텍스트를 기반으로 질문에 답변해주세요.\n\n컨텍스트:\n{context_text}\n\n질문: {question}\n\n답변:"
                
                generation_result = await self.llm_manager.generate(
                    prompt=prompt,
                    model=model,
                    provider=provider,
                    **kwargs
                )
            
            if generation_result.is_failure():
                return generation_result
            
            answer = generation_result.unwrap()
            
            return Success({
                "answer": answer,
                "context_documents": context_documents,
                "question": question,
                "context_count": len(context_documents),
                "template_used": template_name,
                "model_used": model,
                "provider_used": provider
            })
            
        except Exception as e:
            return Failure(f"RAG 질의응답 실패: {str(e)}")
    
    async def add_knowledge(
        self,
        documents: List[Dict[str, Any]]
    ) -> Result[List[str], str]:
        """지식 베이스에 문서 추가
        
        Args:
            documents: 추가할 문서 목록
            
        Returns:
            Result[List[str], str]: 추가된 문서 ID 목록 또는 에러 메시지
        """
        return await self.vector_store.add_documents(documents)
    
    async def add_knowledge_from_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        auto_chunk: bool = True
    ) -> Result[List[str], str]:
        """텍스트들을 지식 베이스에 추가 (자동 청킹 지원)
        
        Args:
            texts: 추가할 텍스트 목록
            metadatas: 각 텍스트의 메타데이터
            chunk_size: 청킹 크기 (auto_chunk=True인 경우)
            chunk_overlap: 청크 간 겹침
            auto_chunk: 자동 청킹 여부
            
        Returns:
            Result[List[str], str]: 추가된 문서 ID 목록
        """
        try:
            processed_texts = []
            processed_metadatas = []
            
            for i, text in enumerate(texts):
                base_metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                
                if auto_chunk and len(text) > chunk_size:
                    # 텍스트 청킹
                    chunks = self.vector_store.chunk_text(
                        text=text,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap
                    )
                    
                    for j, chunk in enumerate(chunks):
                        processed_texts.append(chunk)
                        chunk_metadata = base_metadata.copy()
                        chunk_metadata.update({
                            "chunk_index": j,
                            "total_chunks": len(chunks),
                            "original_text_index": i,
                            "is_chunked": True
                        })
                        processed_metadatas.append(chunk_metadata)
                else:
                    processed_texts.append(text)
                    processed_metadatas.append(base_metadata)
            
            return await self.vector_store.add_text_documents(
                texts=processed_texts,
                metadatas=processed_metadatas
            )
            
        except Exception as e:
            return Failure(f"텍스트 지식 베이스 추가 실패: {str(e)}")
    
    async def update_knowledge(
        self,
        documents: List[Dict[str, Any]]
    ) -> Result[List[str], str]:
        """지식 베이스 문서 업데이트
        
        Args:
            documents: 업데이트할 문서 목록 (ID 포함 필요)
            
        Returns:
            Result[List[str], str]: 업데이트된 문서 ID 목록
        """
        return await self.vector_store.update_documents(documents)
    
    async def remove_knowledge(
        self,
        document_ids: List[str]
    ) -> Result[None, str]:
        """지식 베이스에서 문서 삭제
        
        Args:
            document_ids: 삭제할 문서 ID 목록
            
        Returns:
            Result[None, str]: 삭제 결과
        """
        return await self.vector_store.delete_documents(document_ids)
    
    async def search_knowledge(
        self,
        query: str,
        k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None
    ) -> Result[List[Dict[str, Any]], str]:
        """지식 베이스 검색 (LLM 없이)
        
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
            filter_metadata: 메타데이터 필터
            similarity_threshold: 유사도 임계값
            
        Returns:
            Result[List[Dict[str, Any]], str]: 검색 결과
        """
        if similarity_threshold:
            return await self.vector_store.search_with_threshold(
                query=query,
                similarity_threshold=similarity_threshold,
                max_results=k
            )
        else:
            return await self.vector_store.similarity_search(
                query=query,
                k=k,
                filter_metadata=filter_metadata
            )
    
    async def get_knowledge_stats(self) -> Result[Dict[str, Any], str]:
        """지식 베이스 통계 정보
        
        Returns:
            Result[Dict[str, Any], str]: 통계 정보
        """
        try:
            collection_info = self.vector_store.get_collection_info()
            
            # ChromaDB의 경우 상세 통계 조회
            if hasattr(self.vector_store, 'get_collection_stats'):
                stats_result = await self.vector_store.get_collection_stats()
                if stats_result.is_success():
                    stats = stats_result.unwrap()
                    collection_info.update(stats)
            
            return Success(collection_info)
            
        except Exception as e:
            return Failure(f"지식 베이스 통계 조회 실패: {str(e)}")
    
    def create_qa_pipeline(
        self,
        model: str,
        template_name: str = "rag_basic",
        k: int = 5,
        provider: Optional[str] = None,
        **default_kwargs
    ):
        """질의응답 파이프라인 생성 (HOF 패턴)
        
        Args:
            model: 사용할 모델
            template_name: 템플릿 이름
            k: 검색할 문서 수
            provider: Provider 이름
            **default_kwargs: 기본 파라미터
            
        Returns:
            Callable: 질문을 받아 답변을 반환하는 함수
        """
        async def qa_pipeline(question: str, **kwargs) -> Result[Dict[str, Any], str]:
            merged_kwargs = {**default_kwargs, **kwargs}
            return await self.query(
                question=question,
                model=model,
                template_name=template_name,
                k=k,
                provider=provider,
                **merged_kwargs
            )
        
        return qa_pipeline
    
    def create_knowledge_ingestion_pipeline(
        self,
        auto_chunk: bool = True,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """지식 수집 파이프라인 생성 (HOF 패턴)
        
        Args:
            auto_chunk: 자동 청킹 여부
            chunk_size: 청킹 크기
            chunk_overlap: 청크 겹침
            
        Returns:
            Callable: 텍스트를 받아 지식 베이스에 추가하는 함수
        """
        async def ingestion_pipeline(
            texts: List[str],
            metadatas: Optional[List[Dict[str, Any]]] = None
        ) -> Result[List[str], str]:
            return await self.add_knowledge_from_texts(
                texts=texts,
                metadatas=metadatas,
                auto_chunk=auto_chunk,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
        
        return ingestion_pipeline