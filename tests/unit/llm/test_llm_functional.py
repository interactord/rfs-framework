"""
LLM 모듈 기능적 단위 테스트

실제 사용 가능한 모듈들에 대한 포괄적 테스트
모킹을 통한 외부 의존성 제거
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from rfs.core.result import Success, Failure


class TestLLMModuleImports:
    """LLM 모듈 import 테스트"""
    
    def test_core_module_imports(self):
        """핵심 모듈 import 테스트"""
        from rfs.llm.manager import LLMManager
        from rfs.llm.providers.base import LLMProvider
        
        assert LLMManager is not None
        assert LLMProvider is not None
        
    def test_template_module_import(self):
        """템플릿 모듈 import 테스트"""
        try:
            from rfs.llm.prompts.template import PromptTemplate
            assert PromptTemplate is not None
        except ImportError as e:
            pytest.skip(f"템플릿 모듈을 가져올 수 없습니다: {e}")
    
    def test_chain_modules_import(self):
        """체인 모듈들 import 테스트"""
        try:
            from rfs.llm.chains.base import Chain
            from rfs.llm.chains.sequential import SequentialChain
            assert Chain is not None
            assert SequentialChain is not None
        except ImportError as e:
            pytest.skip(f"체인 모듈들을 가져올 수 없습니다: {e}")

    def test_rag_modules_import(self):
        """RAG 모듈들 import 테스트"""
        try:
            from rfs.llm.rag.vector_store import VectorStore
            from rfs.llm.rag.engine import RAGEngine
            assert VectorStore is not None
            assert RAGEngine is not None
        except ImportError as e:
            pytest.skip(f"RAG 모듈들을 가져올 수 없습니다: {e}")

    def test_monitoring_modules_import(self):
        """모니터링 모듈들 import 테스트"""
        try:
            from rfs.llm.monitoring.token_monitor import TokenMonitor
            from rfs.llm.monitoring.metrics import MetricsCollector
            assert TokenMonitor is not None
            assert MetricsCollector is not None
        except ImportError as e:
            pytest.skip(f"모니터링 모듈들을 가져올 수 없습니다: {e}")


class TestLLMBaseProvider:
    """LLM Base Provider 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        from rfs.llm.providers.base import LLMProvider
        self.provider_class = LLMProvider
    
    def test_provider_is_abstract(self):
        """Provider가 추상 클래스인지 테스트"""
        with pytest.raises(TypeError):
            # 추상 클래스이므로 직접 인스턴스화 불가
            self.provider_class()
    
    def test_provider_interface(self):
        """Provider 인터페이스 테스트"""
        # 필수 메서드들이 정의되어 있는지 확인
        assert hasattr(self.provider_class, 'generate')
        assert hasattr(self.provider_class, 'embed')
        assert hasattr(self.provider_class, 'get_token_count')


class TestLLMManager:
    """LLM Manager 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        from rfs.llm.manager import LLMManager
        from rfs.llm.providers.base import LLMProvider
        self.manager_class = LLMManager
        self.provider_class = LLMProvider
        self.manager = LLMManager()
    
    def test_manager_initialization(self):
        """Manager 초기화 테스트"""
        assert self.manager is not None
        assert hasattr(self.manager, '_providers')
        assert hasattr(self.manager, '_default_provider')
        assert len(self.manager._providers) == 0
        assert self.manager._default_provider is None
    
    def test_register_provider_success(self):
        """Provider 등록 성공 테스트"""
        # Mock Provider 생성
        mock_provider = Mock(spec=self.provider_class)
        mock_provider.generate = AsyncMock(return_value=Success({"response": "test"}))
        
        result = self.manager.register_provider("test", mock_provider)
        
        assert result.is_success()
        assert "test" in self.manager._providers
        assert self.manager._providers["test"] == mock_provider
        assert self.manager._default_provider == "test"
    
    def test_register_duplicate_provider(self):
        """중복 Provider 등록 테스트"""
        mock_provider1 = Mock(spec=self.provider_class)
        mock_provider2 = Mock(spec=self.provider_class)
        
        self.manager.register_provider("test", mock_provider1)
        result = self.manager.register_provider("test", mock_provider2)
        
        assert result.is_failure()
        assert "이미 등록되어 있습니다" in result.unwrap_error()
    
    def test_check_provider_exists(self):
        """Provider 존재 확인 테스트"""
        mock_provider = Mock(spec=self.provider_class)
        
        # Provider 목록 확인으로 대체
        assert len(self.manager.list_providers()) == 0
        
        self.manager.register_provider("test", mock_provider)
        assert len(self.manager.list_providers()) == 1
        assert "test" in self.manager.list_providers()
    
    @pytest.mark.asyncio
    async def test_generate_with_registered_provider(self):
        """등록된 Provider로 생성 테스트"""
        mock_provider = Mock(spec=self.provider_class)
        mock_provider.generate = AsyncMock(return_value=Success({
            "response": "테스트 응답",
            "model": "test-model",
            "usage": {"total_tokens": 10}
        }))
        
        self.manager.register_provider("test", mock_provider)
        
        result = await self.manager.generate(
            provider="test",
            prompt="테스트 프롬프트",
            model="test-model"
        )
        
        assert result.is_success()
        response_data = result.unwrap()
        assert response_data["response"] == "테스트 응답"
        
        mock_provider.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_with_nonexistent_provider(self):
        """존재하지 않는 Provider로 생성 시도 테스트"""
        result = await self.manager.generate(
            provider="nonexistent",
            prompt="테스트 프롬프트",
            model="test-model"
        )
        
        assert result.is_failure()
        error_msg = result.unwrap_error().lower()
        assert "nonexistent" in error_msg or "not found" in error_msg or "찾을 수 없습니다" in error_msg


class TestPromptTemplate:
    """Prompt Template 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.prompts.template import PromptTemplate
            self.template_class = PromptTemplate
            self.has_template = True
        except ImportError:
            self.has_template = False
    
    def test_template_creation(self):
        """템플릿 생성 테스트"""
        if not self.has_template:
            pytest.skip("PromptTemplate 모듈을 사용할 수 없습니다")
        
        template = self.template_class("Hello {name}!")
        assert template is not None
        assert template.template == "Hello {name}!"
    
    def test_template_rendering(self):
        """템플릿 렌더링 테스트"""
        if not self.has_template:
            pytest.skip("PromptTemplate 모듈을 사용할 수 없습니다")
        
        template = self.template_class("Hello {name}!")
        result = template.render(name="World")
        
        assert result.is_success()
        assert result.unwrap() == "Hello World!"
    
    def test_template_missing_variable(self):
        """템플릿 변수 누락 테스트"""
        if not self.has_template:
            pytest.skip("PromptTemplate 모듈을 사용할 수 없습니다")
        
        template = self.template_class("Hello {name}!")
        result = template.render()  # name 변수 누락
        
        assert result.is_failure()


class TestRAGEngine:
    """RAG Engine 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.rag.engine import RAGEngine
            from rfs.llm.rag.vector_store import VectorStore
            self.rag_class = RAGEngine
            self.vector_store_class = VectorStore
            self.has_rag = True
        except ImportError:
            self.has_rag = False
    
    def test_rag_engine_initialization(self):
        """RAG Engine 초기화 테스트"""
        if not self.has_rag:
            pytest.skip("RAG 모듈을 사용할 수 없습니다")
        
        mock_vector_store = Mock(spec=self.vector_store_class)
        mock_llm_manager = Mock()
        
        rag_engine = self.rag_class(
            vector_store=mock_vector_store,
            llm_manager=mock_llm_manager
        )
        
        assert rag_engine is not None
        assert rag_engine.vector_store == mock_vector_store
        assert rag_engine.llm_manager == mock_llm_manager


class TestChainSystem:
    """Chain System 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.chains.base import LLMChain
            from rfs.llm.chains.sequential import SequentialChain
            self.chain_class = LLMChain
            self.sequential_class = SequentialChain
            self.has_chains = True
        except ImportError:
            self.has_chains = False
    
    def test_chain_creation(self):
        """체인 생성 테스트"""
        if not self.has_chains:
            pytest.skip("체인 모듈을 사용할 수 없습니다")
        
        # Mock chain을 생성하여 SequentialChain에 전달
        from unittest.mock import Mock, AsyncMock
        from rfs.core.result import Success
        
        mock_chain = Mock(spec=self.chain_class)
        mock_chain.run = AsyncMock(return_value=Success({'output': 'test'}))
        mock_chain.name = 'test_chain'
        
        # Sequential Chain은 chains 리스트가 필요
        chain = self.sequential_class(chains=[mock_chain])
        assert chain is not None
        assert len(chain.chains) == 1
    
    @pytest.mark.asyncio
    async def test_sequential_chain_execution(self):
        """Sequential Chain 실행 테스트"""
        if not self.has_chains:
            pytest.skip("체인 모듈을 사용할 수 없습니다")
        
        # Mock chain들 생성
        from unittest.mock import Mock, AsyncMock
        from rfs.core.result import Success
        
        mock_chain1 = Mock(spec=self.chain_class)
        mock_chain1.run = AsyncMock(return_value=Success({'output': 'step1 result'}))
        mock_chain1.name = 'chain1'
        
        mock_chain2 = Mock(spec=self.chain_class)
        mock_chain2.run = AsyncMock(return_value=Success({'output': 'step2 result'}))
        mock_chain2.name = 'chain2'
        
        # SequentialChain 생성
        seq_chain = self.sequential_class(chains=[mock_chain1, mock_chain2])
        
        # 체인 실행
        result = await seq_chain.run({'input': 'test'})
        
        # 결과 검증
        assert result.is_success()
        
        # 각 체인이 호출되었는지 확인
        mock_chain1.run.assert_called_once()
        mock_chain2.run.assert_called_once()


class TestTokenMonitor:
    """Token Monitor 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.monitoring.token_monitor import TokenMonitor
            self.monitor_class = TokenMonitor
            self.has_monitoring = True
        except ImportError:
            self.has_monitoring = False
    
    def test_token_monitor_initialization(self):
        """토큰 모니터 초기화 테스트"""
        if not self.has_monitoring:
            pytest.skip("모니터링 모듈을 사용할 수 없습니다")
        
        monitor = self.monitor_class()
        assert monitor is not None
    
    def test_token_usage_tracking(self):
        """토큰 사용량 추적 테스트"""
        if not self.has_monitoring:
            pytest.skip("모니터링 모듈을 사용할 수 없습니다")
        
        monitor = self.monitor_class()
        
        # 토큰 사용량 기록
        monitor.record_usage("test-provider", "test-model", 100, 50)
        
        # 사용량이 올바르게 기록되었는지 확인
        total_usage = monitor.get_total_usage()
        assert total_usage >= 150  # input + output tokens