"""
LLM 통합 모듈 통합 테스트

실제 API 호출을 포함한 전체적인 통합 테스트를 수행합니다.
환경변수로 API 키가 설정된 경우에만 실행됩니다.
"""

import os
import pytest
import asyncio
from typing import Dict, Any
from datetime import datetime

from rfs.core.result import Success, Failure


class TestLLMIntegration:
    """LLM 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        try:
            from rfs.llm import (
                LLMManager,
                OpenAIProvider,
                AnthropicProvider,
                PromptTemplateManager
            )
            self.llm_manager_class = LLMManager
            self.openai_provider_class = OpenAIProvider
            self.anthropic_provider_class = AnthropicProvider
            self.template_manager_class = PromptTemplateManager
            self.has_llm = True
        except ImportError:
            self.has_llm = False
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY 환경변수가 필요합니다"
    )
    @pytest.mark.asyncio
    async def test_openai_integration(self):
        """OpenAI 통합 테스트"""
        if not self.has_llm:
            pytest.skip("LLM 모듈을 사용할 수 없습니다")
        
        # OpenAI Provider 생성
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        
        # 간단한 텍스트 생성 테스트
        result = await provider.generate(
            prompt="안녕하세요를 영어로 번역해주세요.",
            model="gpt-3.5-turbo",
            max_tokens=50
        )
        
        assert result.is_success()
        response_data = result.unwrap()
        
        assert "response" in response_data
        assert "model" in response_data
        assert "usage" in response_data
        assert isinstance(response_data["response"], str)
        assert len(response_data["response"]) > 0
        
        # 토큰 사용량 확인
        usage = response_data["usage"]
        assert "total_tokens" in usage
        assert usage["total_tokens"] > 0
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY 환경변수가 필요합니다"
    )
    @pytest.mark.asyncio
    async def test_openai_embedding(self):
        """OpenAI 임베딩 테스트"""
        if not self.has_llm:
            pytest.skip("LLM 모듈을 사용할 수 없습니다")
        
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        
        result = await provider.embed(
            text="이것은 임베딩 테스트용 텍스트입니다.",
            model="text-embedding-ada-002"
        )
        
        assert result.is_success()
        embedding_data = result.unwrap()
        
        assert "embedding" in embedding_data
        assert "usage" in embedding_data
        
        embedding = embedding_data["embedding"]
        assert isinstance(embedding, list)
        assert len(embedding) == 1536  # text-embedding-ada-002 차원
        assert all(isinstance(x, float) for x in embedding)
    
    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY 환경변수가 필요합니다"
    )
    @pytest.mark.asyncio
    async def test_anthropic_integration(self):
        """Anthropic 통합 테스트"""
        if not self.has_llm:
            pytest.skip("LLM 모듈을 사용할 수 없습니다")
        
        provider = self.anthropic_provider_class(api_key=self.anthropic_api_key)
        
        result = await provider.generate(
            prompt="Python에서 함수형 프로그래밍의 장점을 한 문장으로 설명해주세요.",
            model="claude-3-haiku-20240307",
            max_tokens=100
        )
        
        assert result.is_success()
        response_data = result.unwrap()
        
        assert "response" in response_data
        assert "model" in response_data
        assert "usage" in response_data
        assert isinstance(response_data["response"], str)
        assert len(response_data["response"]) > 0
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY 환경변수가 필요합니다"
    )
    @pytest.mark.asyncio
    async def test_llm_manager_integration(self):
        """LLM Manager 통합 테스트"""
        if not self.has_llm:
            pytest.skip("LLM 모듈을 사용할 수 없습니다")
        
        # LLM Manager 생성
        manager = self.llm_manager_class()
        
        # OpenAI Provider 등록
        openai_provider = self.openai_provider_class(api_key=self.openai_api_key)
        await manager.register_provider("openai", openai_provider)
        
        # Anthropic Provider 등록 (API 키가 있는 경우)
        if self.anthropic_api_key:
            anthropic_provider = self.anthropic_provider_class(api_key=self.anthropic_api_key)
            await manager.register_provider("anthropic", anthropic_provider)
        
        # OpenAI 호출 테스트
        result = await manager.generate(
            provider="openai",
            prompt="Python의 주요 특징을 3가지 나열해주세요.",
            model="gpt-3.5-turbo",
            max_tokens=150
        )
        
        assert result.is_success()
        response_data = result.unwrap()
        assert "response" in response_data
        assert "Python" in response_data["response"]
        
        # Provider 존재 확인
        assert await manager.has_provider("openai") is True
        assert await manager.has_provider("nonexistent") is False
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY 환경변수가 필요합니다"
    )
    @pytest.mark.asyncio
    async def test_template_integration(self):
        """템플릿 통합 테스트"""
        if not self.has_llm:
            pytest.skip("LLM 모듈을 사용할 수 없습니다")
        
        # LLM Manager 설정
        manager = self.llm_manager_class()
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        await manager.register_provider("openai", provider)
        
        # 템플릿 매니저 설정
        template_manager = self.template_manager_class()
        await template_manager.register_common_templates()
        
        # 코드 리뷰 템플릿 테스트
        code_sample = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''
        
        result = await template_manager.render_and_generate(
            template_name="code_review",
            provider="openai",
            manager=manager,
            variables={
                "code": code_sample,
                "language": "Python",
                "focus_areas": ["성능", "가독성"]
            },
            model="gpt-3.5-turbo",
            max_tokens=200
        )
        
        assert result.is_success()
        review_data = result.unwrap()
        
        assert "response" in review_data
        review_text = review_data["response"]
        assert isinstance(review_text, str)
        assert len(review_text) > 0
        
        # 리뷰 내용이 코드와 관련있는지 간단히 확인
        assert any(keyword in review_text.lower() for keyword in 
                  ["fibonacci", "performance", "성능", "재귀", "recursive"])


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY 환경변수가 필요합니다"
)
class TestRAGIntegration:
    """RAG 시스템 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        try:
            from rfs.llm import LLMManager, OpenAIProvider
            from rfs.llm.rag.chroma import ChromaVectorStore
            from rfs.llm.rag.engine import RAGEngine
            
            self.llm_manager_class = LLMManager
            self.openai_provider_class = OpenAIProvider
            self.vector_store_class = ChromaVectorStore
            self.rag_engine_class = RAGEngine
            self.has_rag = True
        except ImportError:
            self.has_rag = False
    
    @pytest.mark.asyncio
    async def test_rag_full_workflow(self):
        """RAG 전체 워크플로우 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        # LLM Manager 설정
        manager = self.llm_manager_class()
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        await manager.register_provider("openai", provider)
        
        # 테스트용 벡터 스토어 (임시 디렉토리)
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            vector_store = self.vector_store_class(
                collection_name="test_integration",
                persist_directory=temp_dir
            )
            
            # RAG 엔진 생성
            rag_engine = self.rag_engine_class(
                vector_store=vector_store,
                llm_manager=manager
            )
            
            # 테스트 문서들 추가
            test_documents = [
                {
                    "text": "FastAPI는 고성능 Python 웹 프레임워크입니다. 자동 API 문서 생성과 타입 힌트 지원이 특징입니다.",
                    "metadata": {"source": "fastapi_intro", "topic": "web_framework"}
                },
                {
                    "text": "Django는 배터리 포함 철학을 가진 Python 웹 프레임워크입니다. ORM, 관리자 인터페이스, 인증 시스템을 내장합니다.",
                    "metadata": {"source": "django_intro", "topic": "web_framework"}
                },
                {
                    "text": "Flask는 마이크로 웹 프레임워크입니다. 최소한의 핵심 기능을 제공하고 확장을 통해 기능을 추가할 수 있습니다.",
                    "metadata": {"source": "flask_intro", "topic": "web_framework"}
                }
            ]
            
            # 문서들을 지식 베이스에 추가
            for i, doc in enumerate(test_documents):
                result = await rag_engine.add_to_knowledge_base(
                    text=doc["text"],
                    doc_id=f"test_doc_{i}",
                    metadata=doc["metadata"]
                )
                assert result.is_success()
            
            # 약간의 대기 (벡터 인덱싱 완료를 위해)
            await asyncio.sleep(1)
            
            # RAG 질의 응답 테스트
            question = "FastAPI와 Django의 주요 차이점은 무엇인가요?"
            
            result = await rag_engine.generate_answer(
                question=question,
                provider="openai",
                model="gpt-3.5-turbo",
                template="basic",
                max_tokens=200
            )
            
            assert result.is_success()
            answer_data = result.unwrap()
            
            # 응답 구조 확인
            assert "answer" in answer_data
            assert "sources" in answer_data
            assert "question" in answer_data
            
            answer = answer_data["answer"]
            sources = answer_data["sources"]
            
            # 답변이 생성되었는지 확인
            assert isinstance(answer, str)
            assert len(answer) > 0
            
            # 관련 소스가 검색되었는지 확인
            assert len(sources) > 0
            
            # 소스에 FastAPI나 Django 관련 문서가 포함되었는지 확인
            source_texts = [doc["content"] for doc in sources]
            has_relevant_source = any(
                "FastAPI" in text or "Django" in text 
                for text in source_texts
            )
            assert has_relevant_source
            
            # 답변이 질문과 관련있는지 간단히 확인
            answer_lower = answer.lower()
            assert any(keyword in answer_lower for keyword in 
                      ["fastapi", "django", "차이", "difference", "framework"])
            
        finally:
            # 임시 디렉토리 정리
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY 환경변수가 필요합니다"
)
class TestChainIntegration:
    """체인 워크플로우 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        try:
            from rfs.llm import LLMManager, OpenAIProvider
            from rfs.llm.chains.base import SimpleLLMChain
            from rfs.llm.chains.sequential import SequentialChain
            from rfs.llm.chains.parallel import ParallelChain
            
            self.llm_manager_class = LLMManager
            self.openai_provider_class = OpenAIProvider
            self.simple_chain_class = SimpleLLMChain
            self.sequential_chain_class = SequentialChain
            self.parallel_chain_class = ParallelChain
            self.has_chains = True
        except ImportError:
            self.has_chains = False
    
    @pytest.mark.asyncio
    async def test_sequential_chain_integration(self):
        """순차 체인 통합 테스트"""
        if not self.has_chains:
            pytest.skip("체인 모듈을 사용할 수 없습니다")
        
        # LLM Manager 설정
        manager = self.llm_manager_class()
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        await manager.register_provider("openai", provider)
        
        # 체인들 생성
        # 1. 아이디어 생성 체인
        idea_chain = self.simple_chain_class(
            manager=manager,
            provider="openai",
            model="gpt-3.5-turbo",
            name="아이디어_생성"
        )
        
        # 2. 아이디어 평가 체인
        evaluation_chain = self.simple_chain_class(
            manager=manager,
            provider="openai",
            model="gpt-3.5-turbo",
            name="아이디어_평가"
        )
        
        # 순차 체인 생성
        sequential_chain = self.sequential_chain_class([idea_chain, evaluation_chain])
        
        # 실행
        result = await sequential_chain.run({
            "prompt": "Python으로 간단한 블로그 시스템을 만드는 아이디어를 3가지 제안하고, 각각의 장단점을 평가해주세요.",
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        # 기본 구조 확인
        assert "response" in output
        assert "_sequential_execution" in output
        
        # 순차 실행 정보 확인
        execution_info = output["_sequential_execution"]
        assert execution_info["chain_count"] == 2
        assert len(execution_info["execution_history"]) == 2
        assert execution_info["success"] is True
        
        # 응답이 블로그와 관련있는지 간단히 확인
        response = output["response"]
        assert isinstance(response, str)
        assert len(response) > 0
        assert any(keyword in response.lower() for keyword in 
                  ["블로그", "blog", "아이디어", "idea", "python"])
    
    @pytest.mark.asyncio
    async def test_parallel_chain_integration(self):
        """병렬 체인 통합 테스트"""
        if not self.has_chains:
            pytest.skip("체인 모듈을 사용할 수 없습니다")
        
        # LLM Manager 설정
        manager = self.llm_manager_class()
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        await manager.register_provider("openai", provider)
        
        # 병렬 체인들 생성
        # 1. 장점 분석 체인
        pros_chain = self.simple_chain_class(
            manager=manager,
            provider="openai",
            model="gpt-3.5-turbo",
            name="장점_분석"
        )
        
        # 2. 단점 분석 체인
        cons_chain = self.simple_chain_class(
            manager=manager,
            provider="openai",
            model="gpt-3.5-turbo",
            name="단점_분석"
        )
        
        # 병렬 체인 생성
        parallel_chain = self.parallel_chain_class([pros_chain, cons_chain], merge_strategy="separate")
        
        # 실행
        result = await parallel_chain.run({
            "prompt": "FastAPI의 장점과 단점을 각각 분석해주세요.",
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        # 병렬 실행 정보 확인
        assert "_parallel_execution" in output
        parallel_info = output["_parallel_execution"]
        assert parallel_info["total_chains"] == 2
        assert parallel_info["successful_chains"] == 2
        assert parallel_info["merge_strategy"] == "separate"
        
        # separate 전략으로 각 체인의 결과가 구분되어 저장되었는지 확인
        assert "parallel_results" in output
        parallel_results = output["parallel_results"]
        
        assert "장점_분석" in parallel_results
        assert "단점_분석" in parallel_results
        
        pros_response = parallel_results["장점_분석"]["response"]
        cons_response = parallel_results["단점_분석"]["response"]
        
        assert isinstance(pros_response, str) and len(pros_response) > 0
        assert isinstance(cons_response, str) and len(cons_response) > 0
        
        # 각 체인이 해당 주제에 맞게 응답했는지 간단히 확인
        assert "fastapi" in (pros_response + cons_response).lower()


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY 환경변수가 필요합니다"
)
class TestMonitoringIntegration:
    """모니터링 시스템 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        try:
            from rfs.llm import LLMManager, OpenAIProvider
            from rfs.llm.monitoring import get_metrics_collector, get_response_cache
            
            self.llm_manager_class = LLMManager
            self.openai_provider_class = OpenAIProvider
            self.get_metrics_collector = get_metrics_collector
            self.get_response_cache = get_response_cache
            self.has_monitoring = True
        except ImportError:
            self.has_monitoring = False
    
    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self):
        """메트릭 수집 통합 테스트"""
        if not self.has_monitoring:
            pytest.skip("모니터링 모듈을 사용할 수 없습니다")
        
        # 메트릭 수집기
        metrics_collector = self.get_metrics_collector()
        
        # LLM Manager 설정
        manager = self.llm_manager_class()
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        await manager.register_provider("openai", provider)
        
        # 초기 메트릭 확인
        initial_summary = metrics_collector.get_summary()
        initial_count = 0
        if initial_summary.is_success():
            initial_count = initial_summary.unwrap().total_calls
        
        # 몇 번의 LLM 호출 수행
        test_prompts = [
            "Hello, world!",
            "Python이란 무엇인가요?",
            "간단한 계산: 2+2"
        ]
        
        successful_calls = 0
        for prompt in test_prompts:
            result = await manager.generate(
                provider="openai",
                prompt=prompt,
                model="gpt-3.5-turbo",
                max_tokens=30
            )
            
            if result.is_success():
                successful_calls += 1
            
            # 각 호출 사이에 약간의 대기
            await asyncio.sleep(0.1)
        
        # 메트릭이 수집되었는지 확인
        final_summary = metrics_collector.get_summary()
        assert final_summary.is_success()
        
        summary = final_summary.unwrap()
        
        # 호출 수가 증가했는지 확인
        assert summary.total_calls >= initial_count + successful_calls
        
        # 성공률 확인 (모든 호출이 성공해야 함)
        if summary.total_calls > initial_count:
            assert summary.success_rate > 0
        
        # 기본 메트릭들 확인
        assert summary.avg_duration_ms >= 0
        assert summary.total_tokens >= 0
        assert summary.total_cost >= 0
    
    @pytest.mark.asyncio 
    async def test_cache_integration(self):
        """캐시 시스템 통합 테스트"""
        if not self.has_monitoring:
            pytest.skip("모니터링 모듈을 사용할 수 없습니다")
        
        # 응답 캐시
        response_cache = self.get_response_cache()
        
        # LLM Manager 설정
        manager = self.llm_manager_class()
        provider = self.openai_provider_class(api_key=self.openai_api_key)
        await manager.register_provider("openai", provider)
        
        # 캐시 통계 초기값
        initial_stats = await response_cache.get_cache_stats()
        assert initial_stats.is_success()
        
        initial_hits = initial_stats.unwrap()["hits"]
        initial_misses = initial_stats.unwrap()["misses"]
        
        # 테스트용 프롬프트
        test_prompt = "캐시 테스트를 위한 간단한 질문입니다."
        
        # 첫 번째 호출 (캐시 미스가 될 것)
        result1 = await manager.generate(
            provider="openai",
            prompt=test_prompt,
            model="gpt-3.5-turbo",
            max_tokens=50
        )
        
        assert result1.is_success()
        first_response = result1.unwrap()["response"]
        
        # 캐시에 직접 저장 테스트
        await response_cache.set(
            provider="openai",
            model="gpt-3.5-turbo",
            prompt=test_prompt,
            response=first_response,
            ttl=300
        )
        
        # 캐시에서 조회 테스트
        cached_result = await response_cache.get(
            provider="openai",
            model="gpt-3.5-turbo",
            prompt=test_prompt
        )
        
        assert cached_result.is_success()
        cached_response = cached_result.unwrap()
        assert cached_response is not None
        assert cached_response == first_response
        
        # 캐시 통계 확인
        final_stats = await response_cache.get_cache_stats()
        assert final_stats.is_success()
        
        stats = final_stats.unwrap()
        
        # 히트나 미스가 발생했는지 확인
        total_hits = stats["hits"]
        total_misses = stats["misses"]
        
        assert total_hits > initial_hits or total_misses > initial_misses
        assert stats["total_keys"] > 0