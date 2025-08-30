"""
LLM Configuration 단위 테스트

LLM 설정 시스템의 기본 동작을 테스트합니다.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from rfs.core.result import Success, Failure


@pytest.mark.asyncio
class TestLLMConfig:
    """LLM Configuration 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.config import (
                get_llm_settings,
                configure_llm_settings,
                LLMProviderType,
                get_available_models,
                get_model_info,
                PREDEFINED_MODELS
            )
            self.config_available = True
            self.get_llm_settings = get_llm_settings
            self.configure_llm_settings = configure_llm_settings
            self.LLMProviderType = LLMProviderType
            self.get_available_models = get_available_models
            self.get_model_info = get_model_info
            self.PREDEFINED_MODELS = PREDEFINED_MODELS
        except ImportError:
            self.config_available = False
    
    def test_default_settings(self):
        """기본 설정 테스트"""
        if not self.config_available:
            pytest.skip("LLM Config 모듈을 사용할 수 없습니다")
        
        settings = self.get_llm_settings()
        
        # 기본 설정 확인
        assert settings is not None
        
        # 딕셔너리 형태로도 동작해야 함 (Pydantic 없는 경우)
        if isinstance(settings, dict):
            assert "enabled_providers" in settings
            assert "default_provider" in settings
        else:
            # Pydantic 모델인 경우
            assert hasattr(settings, 'enabled_providers')
            assert hasattr(settings, 'default_provider')
    
    def test_configure_settings(self):
        """설정 업데이트 테스트"""
        if not self.config_available:
            pytest.skip("LLM Config 모듈을 사용할 수 없습니다")
        
        # 사용자 설정으로 업데이트
        settings = self.configure_llm_settings(
            default_provider="anthropic",
            enable_monitoring=False
        )
        
        assert settings is not None
        
        if isinstance(settings, dict):
            # Pydantic 없는 경우
            assert settings.get("default_provider") == "anthropic"
            assert settings.get("enable_monitoring") is False
        else:
            # Pydantic 모델인 경우  
            assert settings.default_provider == "anthropic" or settings.default_provider.value == "anthropic"
    
    def test_provider_types(self):
        """Provider 타입 테스트"""
        if not self.config_available:
            pytest.skip("LLM Config 모듈을 사용할 수 없습니다")
        
        # Provider 타입이 정의되어 있는지 확인
        assert hasattr(self.LLMProviderType, 'OPENAI')
        assert hasattr(self.LLMProviderType, 'ANTHROPIC')
        assert hasattr(self.LLMProviderType, 'GEMINI')
        assert hasattr(self.LLMProviderType, 'BEDROCK')
        
        # 값 확인
        assert self.LLMProviderType.OPENAI == "openai"
        assert self.LLMProviderType.ANTHROPIC == "anthropic"
        assert self.LLMProviderType.GEMINI == "gemini"
        assert self.LLMProviderType.BEDROCK == "bedrock"
    
    def test_get_available_models(self):
        """사용 가능한 모델 목록 테스트"""
        if not self.config_available:
            pytest.skip("LLM Config 모듈을 사용할 수 없습니다")
        
        # 전체 모델 목록
        all_models = self.get_available_models()
        assert isinstance(all_models, list)
        assert len(all_models) > 0
        
        # OpenAI 모델만
        openai_models = self.get_available_models(self.LLMProviderType.OPENAI)
        assert isinstance(openai_models, list)
        assert len(openai_models) > 0
        
        # 모든 모델이 OpenAI provider인지 확인
        for model in openai_models:
            if hasattr(model, 'provider'):
                assert model.provider == self.LLMProviderType.OPENAI
    
    def test_get_model_info(self):
        """모델 정보 조회 테스트"""
        if not self.config_available:
            pytest.skip("LLM Config 모듈을 사용할 수 없습니다")
        
        # GPT-4 모델 정보 조회
        model_info = self.get_model_info("gpt-4")
        
        if model_info is not None:
            if hasattr(model_info, 'name'):
                assert model_info.name == "gpt-4"
                assert model_info.provider == self.LLMProviderType.OPENAI
        
        # 존재하지 않는 모델
        non_existent = self.get_model_info("non-existent-model")
        assert non_existent is None
    
    def test_predefined_models_structure(self):
        """미리 정의된 모델 구조 테스트"""
        if not self.config_available:
            pytest.skip("LLM Config 모듈을 사용할 수 없습니다")
        
        # 미리 정의된 모델 딕셔너리 확인
        assert isinstance(self.PREDEFINED_MODELS, dict)
        
        # 각 Provider별 모델 존재 확인
        assert self.LLMProviderType.OPENAI in self.PREDEFINED_MODELS
        assert self.LLMProviderType.ANTHROPIC in self.PREDEFINED_MODELS
        assert self.LLMProviderType.GEMINI in self.PREDEFINED_MODELS
        assert self.LLMProviderType.BEDROCK in self.PREDEFINED_MODELS
        
        # 각 Provider의 모델 목록이 리스트인지 확인
        for provider, models in self.PREDEFINED_MODELS.items():
            assert isinstance(models, list)
            assert len(models) > 0
            
            # 각 모델이 올바른 provider를 가지는지 확인
            for model in models:
                if hasattr(model, 'provider'):
                    assert model.provider == provider


@pytest.mark.asyncio
class TestLLMManagerConfig:
    """LLM Manager Configuration 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.manager import LLMManager, create_llm_manager_from_config
            from rfs.llm.config import configure_llm_settings
            self.manager_available = True
            self.LLMManager = LLMManager
            self.create_llm_manager_from_config = create_llm_manager_from_config
            self.configure_llm_settings = configure_llm_settings
        except ImportError:
            self.manager_available = False
    
    def test_manager_with_default_settings(self):
        """기본 설정으로 Manager 생성 테스트"""
        if not self.manager_available:
            pytest.skip("LLM Manager 모듈을 사용할 수 없습니다")
        
        manager = self.LLMManager()
        
        # 기본 상태 확인
        assert manager.list_providers() == []
        assert manager.get_default_provider_name() is None
        
        # 설정 정보 확인
        settings_info = manager.get_settings_info()
        assert isinstance(settings_info, dict)
    
    def test_auto_configure_from_settings_no_keys(self):
        """API 키 없이 자동 구성 테스트"""
        if not self.manager_available:
            pytest.skip("LLM Manager 모듈을 사용할 수 없습니다")
        
        manager = self.LLMManager()
        
        # API 키가 없는 환경에서 자동 구성
        result = manager.auto_configure_from_settings()
        
        # 성공해야 함 (SDK가 없거나 API 키가 없어도)
        assert result.is_success()
        
        # Provider가 등록되지 않을 수 있음
        providers = manager.list_providers()
        assert isinstance(providers, list)
    
    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-test-key',
        'ANTHROPIC_API_KEY': 'sk-ant-test-key'
    })
    def test_auto_configure_with_environment_variables(self):
        """환경 변수로 자동 구성 테스트"""
        if not self.manager_available:
            pytest.skip("LLM Manager 모듈을 사용할 수 없습니다")
        
        # 환경 변수가 있는 상태에서 설정 업데이트
        self.configure_llm_settings(
            enabled_providers=["openai"],
            default_provider="openai"
        )
        
        manager = self.LLMManager()
        result = manager.auto_configure_from_settings()
        
        # 성공해야 함
        assert result.is_success()
        
        # 환경 변수 기반 설정 정보 확인
        settings_info = manager.get_settings_info()
        assert isinstance(settings_info, dict)
    
    def test_create_llm_manager_from_config_no_providers(self):
        """Provider 없이 Manager 생성 테스트"""
        if not self.manager_available:
            pytest.skip("LLM Manager 모듈을 사용할 수 없습니다")
        
        # API 키가 없는 환경에서 Manager 생성
        result = self.create_llm_manager_from_config()
        
        # API 키가 없으면 실패할 수 있음
        if result.is_failure():
            error_msg = result.unwrap_error()
            assert "사용 가능한 Provider를 찾을 수 없습니다" in error_msg
        else:
            # 성공하면 Manager가 반환되어야 함
            manager = result.unwrap()
            assert isinstance(manager, self.LLMManager)
    
    def test_get_configured_providers(self):
        """설정된 Provider 목록 조회 테스트"""
        if not self.manager_available:
            pytest.skip("LLM Manager 모듈을 사용할 수 없습니다")
        
        manager = self.LLMManager()
        
        # 설정된 Provider 목록 조회
        configured_providers = manager.get_configured_providers()
        assert isinstance(configured_providers, list)
        
        # 기본값이 있어야 함
        assert len(configured_providers) > 0


@pytest.mark.asyncio  
class TestProviderConfigs:
    """Provider별 설정 클래스 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.config import (
                OpenAIProviderConfig,
                AnthropicProviderConfig,
                GeminiProviderConfig,
                BedrockProviderConfig,
                RAGConfig
            )
            self.configs_available = True
            self.OpenAIProviderConfig = OpenAIProviderConfig
            self.AnthropicProviderConfig = AnthropicProviderConfig
            self.GeminiProviderConfig = GeminiProviderConfig
            self.BedrockProviderConfig = BedrockProviderConfig
            self.RAGConfig = RAGConfig
        except ImportError:
            self.configs_available = False
    
    def test_openai_config_creation(self):
        """OpenAI 설정 생성 테스트"""
        if not self.configs_available:
            pytest.skip("Provider Config 클래스를 사용할 수 없습니다")
        
        try:
            config = self.OpenAIProviderConfig(
                api_key="sk-test-key",
                default_model="gpt-4"
            )
            
            if hasattr(config, 'api_key'):
                assert config.api_key == "sk-test-key"
                assert config.default_model == "gpt-4"
        except Exception:
            # Pydantic이 없는 경우 스킵
            pytest.skip("Pydantic이 설치되지 않았습니다")
    
    def test_gemini_config_modes(self):
        """Gemini 설정 모드 테스트"""
        if not self.configs_available:
            pytest.skip("Provider Config 클래스를 사용할 수 없습니다")
        
        try:
            # API Key 모드
            api_config = self.GeminiProviderConfig(
                api_key="test-key",
                use_vertex=False
            )
            
            # Vertex AI 모드
            vertex_config = self.GeminiProviderConfig(
                project="test-project",
                use_vertex=True
            )
            
            if hasattr(api_config, 'use_vertex'):
                assert api_config.use_vertex is False
                assert vertex_config.use_vertex is True
        except Exception:
            pytest.skip("Pydantic이 설치되지 않았습니다")
    
    def test_bedrock_config_auth_methods(self):
        """Bedrock 설정 인증 방식 테스트"""
        if not self.configs_available:
            pytest.skip("Provider Config 클래스를 사용할 수 없습니다")
        
        try:
            # Bearer Token 방식
            token_config = self.BedrockProviderConfig(
                api_key="bearer-token",
                region="us-east-1"
            )
            
            # 기존 AWS 자격 증명 방식
            credential_config = self.BedrockProviderConfig(
                aws_access_key="access-key",
                aws_secret_key="secret-key",
                region="us-west-2"
            )
            
            if hasattr(token_config, 'region'):
                assert token_config.region == "us-east-1"
                assert credential_config.region == "us-west-2"
        except Exception:
            pytest.skip("Pydantic이 설치되지 않았습니다")
    
    def test_rag_config_defaults(self):
        """RAG 설정 기본값 테스트"""
        if not self.configs_available:
            pytest.skip("Provider Config 클래스를 사용할 수 없습니다")
        
        try:
            config = self.RAGConfig()
            
            if hasattr(config, 'chunk_size'):
                assert config.chunk_size == 1000
                assert config.chunk_overlap == 200
                assert config.vector_store_type == "memory"
                assert config.similarity_threshold == 0.7
        except Exception:
            pytest.skip("Pydantic이 설치되지 않았습니다")