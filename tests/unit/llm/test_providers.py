"""
LLM Provider 단위 테스트

LLM Provider들의 기본 동작을 테스트합니다.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from rfs.core.result import Success, Failure


class TestLLMProvider:
    """LLM Provider 기본 동작 테스트"""
    
    def test_provider_imports(self):
        """Provider 임포트 테스트"""
        try:
            from rfs.llm.providers.base import LLMProvider
            from rfs.llm.providers.openai import OpenAIProvider
            from rfs.llm.providers.anthropic import AnthropicProvider
            assert True
        except ImportError as e:
            pytest.skip(f"LLM 모듈을 사용할 수 없습니다: {e}")


@pytest.mark.asyncio
class TestOpenAIProvider:
    """OpenAI Provider 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.api_key = "test_api_key"
        
        # OpenAI 관련 임포트 확인
        try:
            from rfs.llm.providers.openai import OpenAIProvider
            self.provider_class = OpenAIProvider
            self.has_openai = True
        except ImportError:
            self.has_openai = False
    
    def test_provider_initialization(self):
        """Provider 초기화 테스트"""
        if not self.has_openai:
            pytest.skip("OpenAI 라이브러리가 설치되지 않았습니다")
        
        provider = self.provider_class(api_key=self.api_key)
        assert provider.api_key == self.api_key
        assert provider.base_url == "https://api.openai.com/v1"
        assert provider.timeout == 30
        assert provider.max_retries == 3
    
    async def test_generate_success(self):
        """텍스트 생성 성공 테스트"""
        if not self.has_openai:
            pytest.skip("OpenAI 라이브러리가 설치되지 않았습니다")
        
        # Mock 응답 데이터
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "테스트 응답입니다."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            },
            "model": "gpt-3.5-turbo"
        }
        
        provider = self.provider_class(api_key=self.api_key)
        
        # AsyncOpenAI 클라이언트 모킹
        with patch.object(provider, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=Mock(**mock_response))
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="gpt-3.5-turbo"
            )
            
            assert result.is_success()
            response_data = result.unwrap()
            assert response_data["response"] == "테스트 응답입니다."
            assert response_data["model"] == "gpt-3.5-turbo"
            assert response_data["usage"]["total_tokens"] == 15
    
    async def test_generate_failure(self):
        """텍스트 생성 실패 테스트"""
        if not self.has_openai:
            pytest.skip("OpenAI 라이브러리가 설치되지 않았습니다")
        
        provider = self.provider_class(api_key=self.api_key)
        
        # AsyncOpenAI 클라이언트 예외 모킹
        with patch.object(provider, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API 호출 실패")
            )
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="gpt-3.5-turbo"
            )
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "API 호출 실패" in error_message
    
    async def test_embed_success(self):
        """임베딩 생성 성공 테스트"""
        if not self.has_openai:
            pytest.skip("OpenAI 라이브러리가 설치되지 않았습니다")
        
        # Mock 임베딩 응답
        mock_response = {
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "index": 0
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "total_tokens": 5
            }
        }
        
        provider = self.provider_class(api_key=self.api_key)
        
        with patch.object(provider, 'client') as mock_client:
            mock_client.embeddings.create = AsyncMock(return_value=Mock(**mock_response))
            
            result = await provider.embed(
                text="테스트 텍스트",
                model="text-embedding-ada-002"
            )
            
            assert result.is_success()
            embedding_data = result.unwrap()
            assert embedding_data["embedding"] == [0.1, 0.2, 0.3, 0.4, 0.5]
            assert embedding_data["usage"]["total_tokens"] == 5
    
    def test_get_token_count(self):
        """토큰 카운트 테스트"""
        if not self.has_openai:
            pytest.skip("OpenAI 라이브러리가 설치되지 않았습니다")
        
        provider = self.provider_class(api_key=self.api_key)
        
        with patch('tiktoken.encoding_for_model') as mock_encoding:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = [1, 2, 3, 4, 5]
            mock_encoding.return_value = mock_encoder
            
            result = provider.get_token_count("테스트 텍스트", "gpt-3.5-turbo")
            
            assert result.is_success()
            token_count = result.unwrap()
            assert token_count == 5


@pytest.mark.asyncio
class TestAnthropicProvider:
    """Anthropic Provider 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.api_key = "test_api_key"
        
        # Anthropic 관련 임포트 확인
        try:
            from rfs.llm.providers.anthropic import AnthropicProvider
            self.provider_class = AnthropicProvider
            self.has_anthropic = True
        except ImportError:
            self.has_anthropic = False
    
    def test_provider_initialization(self):
        """Provider 초기화 테스트"""
        if not self.has_anthropic:
            pytest.skip("Anthropic 라이브러리가 설치되지 않았습니다")
        
        provider = self.provider_class(api_key=self.api_key)
        assert provider.api_key == self.api_key
        assert provider.base_url == "https://api.anthropic.com"
        assert provider.timeout == 30
        assert provider.max_retries == 3
    
    async def test_generate_success(self):
        """텍스트 생성 성공 테스트"""
        if not self.has_anthropic:
            pytest.skip("Anthropic 라이브러리가 설치되지 않았습니다")
        
        # Mock 응답 데이터
        mock_response = {
            "content": [
                {
                    "text": "테스트 응답입니다."
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5
            },
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn"
        }
        
        provider = self.provider_class(api_key=self.api_key)
        
        # AsyncAnthropic 클라이언트 모킹
        with patch.object(provider, 'client') as mock_client:
            mock_client.messages.create = AsyncMock(return_value=Mock(**mock_response))
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="claude-3-haiku-20240307"
            )
            
            assert result.is_success()
            response_data = result.unwrap()
            assert response_data["response"] == "테스트 응답입니다."
            assert response_data["model"] == "claude-3-haiku-20240307"
            assert response_data["usage"]["input_tokens"] == 10
            assert response_data["usage"]["output_tokens"] == 5
    
    async def test_generate_failure(self):
        """텍스트 생성 실패 테스트"""
        if not self.has_anthropic:
            pytest.skip("Anthropic 라이브러리가 설치되지 않았습니다")
        
        provider = self.provider_class(api_key=self.api_key)
        
        # AsyncAnthropic 클라이언트 예외 모킹
        with patch.object(provider, 'client') as mock_client:
            mock_client.messages.create = AsyncMock(
                side_effect=Exception("API 호출 실패")
            )
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="claude-3-haiku-20240307"
            )
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "API 호출 실패" in error_message
    
    def test_get_token_count_estimation(self):
        """토큰 카운트 추정 테스트"""
        if not self.has_anthropic:
            pytest.skip("Anthropic 라이브러리가 설치되지 않았습니다")
        
        provider = self.provider_class(api_key=self.api_key)
        
        result = provider.get_token_count(
            "테스트 텍스트입니다. 이것은 토큰 카운트 테스트용 텍스트입니다.",
            "claude-3-haiku-20240307"
        )
        
        assert result.is_success()
        token_count = result.unwrap()
        assert isinstance(token_count, int)
        assert token_count > 0


@pytest.mark.asyncio 
class TestLLMManager:
    """LLM Manager 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.manager import LLMManager
            from rfs.llm.providers.base import LLMProvider
            self.manager_class = LLMManager
            self.provider_class = LLMProvider
            self.has_llm_manager = True
        except ImportError:
            self.has_llm_manager = False
    
    def test_manager_initialization(self):
        """Manager 초기화 테스트"""
        if not self.has_llm_manager:
            pytest.skip("LLM Manager를 사용할 수 없습니다")
        
        manager = self.manager_class()
        assert len(manager.providers) == 0
    
    async def test_register_provider(self):
        """Provider 등록 테스트"""
        if not self.has_llm_manager:
            pytest.skip("LLM Manager를 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        # Mock Provider 생성
        mock_provider = Mock(spec=self.provider_class)
        
        result = await manager.register_provider("test", mock_provider)
        
        assert result.is_success()
        assert "test" in manager.providers
        assert manager.providers["test"] == mock_provider
    
    async def test_has_provider(self):
        """Provider 존재 확인 테스트"""
        if not self.has_llm_manager:
            pytest.skip("LLM Manager를 사용할 수 없습니다")
        
        manager = self.manager_class()
        mock_provider = Mock(spec=self.provider_class)
        
        await manager.register_provider("test", mock_provider)
        
        assert await manager.has_provider("test") is True
        assert await manager.has_provider("nonexistent") is False
    
    async def test_generate_success(self):
        """텍스트 생성 성공 테스트"""
        if not self.has_llm_manager:
            pytest.skip("LLM Manager를 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        # Mock Provider 생성
        mock_provider = Mock(spec=self.provider_class)
        mock_provider.generate = AsyncMock(return_value=Success({
            "response": "테스트 응답",
            "model": "test-model",
            "usage": {"total_tokens": 10}
        }))
        
        await manager.register_provider("test", mock_provider)
        
        result = await manager.generate(
            provider="test",
            prompt="테스트 프롬프트",
            model="test-model"
        )
        
        assert result.is_success()
        response_data = result.unwrap()
        assert response_data["response"] == "테스트 응답"
        
        # Provider의 generate 메서드가 호출되었는지 확인
        mock_provider.generate.assert_called_once_with(
            prompt="테스트 프롬프트",
            model="test-model"
        )
    
    async def test_generate_provider_not_found(self):
        """존재하지 않는 Provider로 생성 시도 테스트"""
        if not self.has_llm_manager:
            pytest.skip("LLM Manager를 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        result = await manager.generate(
            provider="nonexistent",
            prompt="테스트 프롬프트",
            model="test-model"
        )
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "Provider 'nonexistent' not found" in error_message