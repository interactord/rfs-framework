"""
벡터 스토어 추상 인터페이스

다양한 벡터 데이터베이스 구현체들을 위한 공통 인터페이스를 정의합니다.
Result Pattern을 통한 안전한 에러 처리를 보장합니다.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from rfs.core.result import Result
from rfs.hof.collections import compact_map


class VectorStore(ABC):
    """벡터 스토어 추상 인터페이스
    
    모든 벡터 데이터베이스 구현체가 상속해야 하는 추상 클래스입니다.
    문서 저장, 검색, 삭제 등의 기본 기능을 정의합니다.
    """
    
    @abstractmethod
    async def add_documents(
        self, 
        documents: List[Dict[str, Any]]
    ) -> Result[List[str], str]:
        """문서 추가
        
        Args:
            documents: 추가할 문서 목록
                각 문서는 다음 키를 포함해야 합니다:
                - content: 문서 내용 (str)
                - id: 문서 ID (str, 선택사항)
                - metadata: 메타데이터 (dict, 선택사항)
                
        Returns:
            Result[List[str], str]: 성공시 추가된 문서 ID 목록, 실패시 에러 메시지
        """
        pass
    
    @abstractmethod
    async def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Result[List[Dict[str, Any]], str]:
        """유사도 검색
        
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
            filter_metadata: 메타데이터 필터
            **kwargs: 추가 검색 파라미터
            
        Returns:
            Result[List[Dict[str, Any]], str]: 성공시 검색된 문서 목록, 실패시 에러 메시지
                각 문서는 다음 정보를 포함합니다:
                - id: 문서 ID
                - content: 문서 내용
                - metadata: 메타데이터
                - score/distance: 유사도 점수 또는 거리
        """
        pass
    
    @abstractmethod
    async def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Result[List[Dict[str, Any]], str]:
        """벡터를 사용한 유사도 검색
        
        Args:
            embedding: 검색할 임베딩 벡터
            k: 반환할 문서 수
            filter_metadata: 메타데이터 필터
            **kwargs: 추가 검색 파라미터
            
        Returns:
            Result[List[Dict[str, Any]], str]: 성공시 검색된 문서 목록, 실패시 에러 메시지
        """
        pass
    
    @abstractmethod
    async def delete_documents(self, ids: List[str]) -> Result[None, str]:
        """문서 삭제
        
        Args:
            ids: 삭제할 문서 ID 목록
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        pass
    
    @abstractmethod
    async def update_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> Result[List[str], str]:
        """문서 업데이트
        
        Args:
            documents: 업데이트할 문서 목록
                각 문서는 반드시 id를 포함해야 합니다.
                
        Returns:
            Result[List[str], str]: 성공시 업데이트된 문서 ID 목록, 실패시 에러 메시지
        """
        pass
    
    @abstractmethod
    async def get_document_by_id(self, doc_id: str) -> Result[Dict[str, Any], str]:
        """ID로 문서 조회
        
        Args:
            doc_id: 조회할 문서 ID
            
        Returns:
            Result[Dict[str, Any], str]: 성공시 문서 정보, 실패시 에러 메시지
        """
        pass
    
    @abstractmethod
    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 반환
        
        Returns:
            Dict[str, Any]: 컬렉션 메타데이터
        """
        pass
    
    # 유용한 유틸리티 메소드들
    async def add_text_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> Result[List[str], str]:
        """텍스트 문서들을 간편하게 추가
        
        Args:
            texts: 추가할 텍스트 목록
            metadatas: 각 텍스트의 메타데이터 목록 (선택사항)
            ids: 각 텍스트의 ID 목록 (선택사항)
            
        Returns:
            Result[List[str], str]: 추가된 문서 ID 목록 또는 에러 메시지
        """
        try:
            documents = []
            for i, text in enumerate(texts):
                doc = {"content": text}
                
                if ids and i < len(ids):
                    doc["id"] = ids[i]
                else:
                    doc["id"] = f"doc_{i}_{hash(text) % 1000000}"
                
                if metadatas and i < len(metadatas):
                    doc["metadata"] = metadatas[i]
                
                documents.append(doc)
            
            return await self.add_documents(documents)
            
        except Exception as e:
            return Failure(f"텍스트 문서 추가 실패: {str(e)}")
    
    async def search_with_threshold(
        self,
        query: str,
        similarity_threshold: float = 0.7,
        max_results: int = 10
    ) -> Result[List[Dict[str, Any]], str]:
        """임계값 기반 유사도 검색
        
        Args:
            query: 검색 쿼리
            similarity_threshold: 유사도 임계값 (0.0 ~ 1.0)
            max_results: 최대 결과 수
            
        Returns:
            Result[List[Dict[str, Any]], str]: 필터링된 검색 결과
        """
        search_result = await self.similarity_search(query, k=max_results)
        
        if search_result.is_failure():
            return search_result
        
        documents = search_result.unwrap()
        
        # 임계값으로 필터링 (스코어가 있는 경우에만)
        filtered_docs = []
        for doc in documents:
            score = doc.get('score', doc.get('similarity', 1.0))
            if score >= similarity_threshold:
                filtered_docs.append(doc)
        
        return Success(filtered_docs)
    
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ) -> List[str]:
        """텍스트를 청크로 분할
        
        Args:
            text: 분할할 텍스트
            chunk_size: 청크 크기
            chunk_overlap: 청크 간 겹침
            separators: 분할에 사용할 구분자 목록
            
        Returns:
            List[str]: 분할된 텍스트 청크 목록
        """
        if separators is None:
            separators = ["\n\n", "\n", ". ", " ", ""]
        
        chunks = []
        current_chunk = ""
        
        # 간단한 청크 분할 로직
        words = text.split()
        
        for word in words:
            test_chunk = current_chunk + (" " if current_chunk else "") + word
            
            if len(test_chunk) <= chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 오버랩 처리
                if chunk_overlap > 0 and chunks:
                    overlap_words = current_chunk.split()[-chunk_overlap//10:]
                    current_chunk = " ".join(overlap_words) + " " + word
                else:
                    current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks