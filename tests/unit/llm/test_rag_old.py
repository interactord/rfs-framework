"""
RAG 시스템 단위 테스트

RAG(Retrieval Augmented Generation) 시스템의 기본 동작을 테스트합니다.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List
import tempfile
import shutil

from rfs.core.result import Success, Failure


@pytest.mark.asyncio
class TestVectorStore:
    """벡터 스토어 기본 동작 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.rag.vector_store import VectorStore
            self.vector_store_class = VectorStore
            self.has_rag = True
        except ImportError:
            self.has_rag = False
    
    def test_vector_store_abstract_interface(self):
        """벡터 스토어 추상 인터페이스 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # 추상 클래스는 직접 인스턴스화할 수 없어야 함
        with pytest.raises(TypeError):
            self.vector_store_class()


@pytest.mark.asyncio
class TestRAGEngine:
    """RAG 엔진 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.rag.engine import RAGEngine
            from rfs.llm.rag.vector_store import VectorStore
            from rfs.llm.manager import LLMManager
            
            self.rag_engine_class = RAGEngine
            self.vector_store_class = VectorStore
            self.llm_manager_class = LLMManager
            self.has_rag = True
        except ImportError:
            self.has_rag = False
    
    async def test_rag_engine_initialization(self):
        """RAG 엔진 초기화 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # Mock 객체들 생성
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        
        # RAG 엔진 생성
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        assert rag_engine.vector_store == mock_vector_store
        assert rag_engine.llm_manager == mock_llm_manager
        assert rag_engine.version == "1.0.0"
    
    async def test_add_knowledge_success(self):
        """지식 베이스 문서 추가 성공 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # Mock 설정
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_vector_store.add_documents = AsyncMock(return_value=Success(["doc_1"]))
        
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        # 문서 추가
        documents = [{"id": "test_doc", "content": "테스트 문서입니다.", "metadata": {"source": "test"}}]
        result = await rag_engine.add_knowledge(documents)
        
        assert result.is_success()
        
        # 벡터 스토어의 add_documents가 호출되었는지 확인
        mock_vector_store.add_documents.assert_called_once()
        
        # 호출된 인자 확인
        call_args = mock_vector_store.add_documents.call_args[0][0]  # 첫 번째 인자 (documents)
        assert len(call_args) == 1
        assert call_args[0]["content"] == "테스트 문서입니다."
        assert call_args[0]["doc_id"] == "test_doc"
        assert call_args[0]["metadata"]["source"] == "test"
    
    async def test_add_to_knowledge_base_chunking(self):
        """긴 문서의 청킹 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_vector_store.add_documents = AsyncMock(return_value=Success(None))
        
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        
        # 작은 청크 사이즈로 설정
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager,
            chunk_size=50,  # 작은 청크 사이즈
            chunk_overlap=10
        )
        
        # 긴 텍스트
        long_text = "이것은 매우 긴 텍스트입니다. " * 10  # 청크가 분할될 만큼 긴 텍스트
        
        result = await rag_engine.add_to_knowledge_base(
            text=long_text,
            doc_id="long_doc"
        )
        
        assert result.is_success()
        
        # add_documents가 호출되었는지 확인
        mock_vector_store.add_documents.assert_called_once()
        
        # 여러 청크로 분할되었는지 확인
        call_args = mock_vector_store.add_documents.call_args[0][0]
        assert len(call_args) > 1  # 여러 청크로 분할되어야 함
    
    async def test_search_knowledge_base_success(self):
        """지식 베이스 검색 성공 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # Mock 검색 결과
        mock_search_results = [
            {
                "content": "Python은 프로그래밍 언어입니다.",
                "metadata": {"source": "doc1", "score": 0.9},
                "doc_id": "doc1_chunk0"
            },
            {
                "content": "Python은 간단하고 가독성이 좋습니다.",
                "metadata": {"source": "doc2", "score": 0.8},
                "doc_id": "doc2_chunk0"
            }
        ]
        
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_vector_store.search = AsyncMock(return_value=Success(mock_search_results))
        
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        # 검색 실행
        result = await rag_engine.search_knowledge_base(
            query="Python이란 무엇인가요?",
            top_k=2
        )
        
        assert result.is_success()
        search_results = result.unwrap()
        
        # 검색 결과 확인
        assert len(search_results) == 2
        assert search_results[0]["content"] == "Python은 프로그래밍 언어입니다."
        assert search_results[1]["content"] == "Python은 간단하고 가독성이 좋습니다."
        
        # 벡터 스토어 검색이 호출되었는지 확인
        mock_vector_store.search.assert_called_once_with(
            query="Python이란 무엇인가요?",
            top_k=2,
            threshold=0.7
        )
    
    async def test_generate_answer_success(self):
        """RAG 답변 생성 성공 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # Mock 검색 결과
        mock_search_results = [
            {
                "content": "FastAPI는 고성능 Python 웹 프레임워크입니다.",
                "metadata": {"source": "doc1"},
                "doc_id": "doc1_chunk0"
            }
        ]
        
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_vector_store.search = AsyncMock(return_value=Success(mock_search_results))
        
        # Mock LLM 응답
        mock_llm_response = {
            "response": "FastAPI는 고성능을 자랑하는 현대적인 Python 웹 프레임워크입니다.",
            "model": "test-model",
            "usage": {"total_tokens": 50}
        }
        
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        mock_llm_manager.generate = AsyncMock(return_value=Success(mock_llm_response))
        
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        # 답변 생성
        result = await rag_engine.generate_answer(
            question="FastAPI란 무엇인가요?",
            provider="test",
            model="test-model",
            template="basic"
        )
        
        assert result.is_success()
        answer_data = result.unwrap()
        
        # 답변 데이터 구조 확인
        assert "answer" in answer_data
        assert "sources" in answer_data
        assert "question" in answer_data
        assert "template" in answer_data
        
        assert answer_data["answer"] == mock_llm_response["response"]
        assert answer_data["question"] == "FastAPI란 무엇인가요?"
        assert len(answer_data["sources"]) == 1
        
        # 검색과 LLM 생성이 호출되었는지 확인
        mock_vector_store.search.assert_called_once()
        mock_llm_manager.generate.assert_called_once()
    
    async def test_generate_answer_no_sources_found(self):
        """관련 소스가 없을 때 답변 생성 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # 빈 검색 결과
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_vector_store.search = AsyncMock(return_value=Success([]))
        
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        result = await rag_engine.generate_answer(
            question="알 수 없는 주제",
            provider="test",
            model="test-model",
            template="basic"
        )
        
        # 검색은 되지만 소스가 없어서 답변을 생성하지 않아야 함
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "관련 문서를 찾을 수 없습니다" in error_message
        
        # 검색은 호출되었지만 LLM 생성은 호출되지 않아야 함
        mock_vector_store.search.assert_called_once()
        mock_llm_manager.generate.assert_not_called()
    
    async def test_generate_answer_search_failure(self):
        """검색 실패 시 답변 생성 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # 검색 실패
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_vector_store.search = AsyncMock(return_value=Failure("벡터 스토어 오류"))
        
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        result = await rag_engine.generate_answer(
            question="테스트 질문",
            provider="test",
            model="test-model"
        )
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "벡터 스토어 오류" in error_message
    
    async def test_generate_answer_llm_failure(self):
        """LLM 답변 생성 실패 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # 성공적인 검색
        mock_search_results = [
            {
                "content": "테스트 내용",
                "metadata": {"source": "test"},
                "doc_id": "test_doc"
            }
        ]
        
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_vector_store.search = AsyncMock(return_value=Success(mock_search_results))
        
        # LLM 생성 실패
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        mock_llm_manager.generate = AsyncMock(return_value=Failure("LLM API 오류"))
        
        rag_engine = self.rag_engine_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        result = await rag_engine.generate_answer(
            question="테스트 질문",
            provider="test",
            model="test-model"
        )
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "LLM API 오류" in error_message
        
        # 검색과 LLM 생성 모두 호출되었는지 확인
        mock_vector_store.search.assert_called_once()
        mock_llm_manager.generate.assert_called_once()


@pytest.mark.asyncio
class TestChromaVectorStore:
    """ChromaDB 벡터 스토어 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.rag.chroma import ChromaVectorStore
            self.chroma_store_class = ChromaVectorStore
            self.has_chroma = True
        except ImportError:
            self.has_chroma = False
    
    def test_chroma_initialization(self):
        """ChromaDB 초기화 테스트"""
        if not self.has_chroma:
            pytest.skip("ChromaDB 모듈을 사용할 수 없습니다")
        
        # 임시 디렉토리 사용
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.chroma_store_class(
                collection_name="test_collection",
                persist_directory=temp_dir
            )
            
            assert store.collection_name == "test_collection"
            assert store.persist_directory == temp_dir
    
    async def test_chroma_add_and_search_mock(self):
        """ChromaDB 문서 추가 및 검색 Mock 테스트"""
        if not self.has_chroma:
            pytest.skip("ChromaDB 모듈을 사용할 수 없습니다")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.chroma_store_class(
                collection_name="test_collection", 
                persist_directory=temp_dir
            )
            
            # collection 속성을 Mock으로 대체
            mock_collection = Mock()
            mock_collection.add = Mock()
            mock_collection.query = Mock(return_value={
                'documents': [["테스트 문서 내용"]],
                'metadatas': [[{"source": "test"}]],
                'distances': [[0.1]],
                'ids': [["doc1"]]
            })
            
            store.collection = mock_collection
            
            # 문서 추가 테스트
            documents = [
                {
                    "content": "테스트 문서 내용",
                    "doc_id": "doc1",
                    "metadata": {"source": "test"}
                }
            ]
            
            result = await store.add_documents(documents)
            assert result.is_success()
            
            # add 메서드가 호출되었는지 확인
            mock_collection.add.assert_called_once()
            
            # 검색 테스트
            search_result = await store.search("테스트 쿼리", top_k=1)
            assert search_result.is_success()
            
            search_data = search_result.unwrap()
            assert len(search_data) == 1
            assert search_data[0]["content"] == "테스트 문서 내용"
            
            # query 메서드가 호출되었는지 확인
            mock_collection.query.assert_called_once()
    
    def test_chroma_statistics_mock(self):
        """ChromaDB 통계 Mock 테스트"""
        if not self.has_chroma:
            pytest.skip("ChromaDB 모듈을 사용할 수 없습니다")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.chroma_store_class(
                collection_name="test_collection",
                persist_directory=temp_dir
            )
            
            # collection을 Mock으로 대체
            mock_collection = Mock()
            mock_collection.count = Mock(return_value=42)
            
            store.collection = mock_collection
            
            # 통계 조회
            stats = store.get_statistics()
            assert stats.is_success()
            
            stats_data = stats.unwrap()
            assert stats_data["document_count"] == 42
            assert stats_data["collection_name"] == "test_collection"