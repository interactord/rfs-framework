"""
Google Gemini Provider 단위 테스트

Gemini Provider의 기본 동작을 테스트합니다.
Mock을 사용하여 외부 API 의존성을 제거합니다.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from rfs.core.result import Success, Failure


@pytest.mark.asyncio
class TestGeminiProvider:
    """Google Gemini Provider 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.api_key = "test_api_key"
        
        # Gemini 관련 import 확인
        try:
            from rfs.llm.providers.gemini import GeminiProvider
            self.provider_class = GeminiProvider
            self.has_gemini = True
        except ImportError:
            self.has_gemini = False
    
    def test_provider_initialization(self):
        """Gemini Provider 초기화 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            assert provider.client == mock_client
            assert provider.version == "1.0.0"
            assert "gemini-2.0-flash-exp" in provider.supported_models
            assert "text_generation" in provider.capabilities
            assert provider.use_vertex is False
            
            # 클라이언트가 올바른 파라미터로 생성되었는지 확인
            mock_client_class.assert_called_once_with(
                api_key=self.api_key
            )
    
    def test_provider_initialization_vertex(self):
        """Vertex AI 모드 초기화 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(
                project="test-project",
                location="us-central1",
                use_vertex=True
            )
            
            assert provider.client == mock_client
            assert provider.use_vertex is True
            assert provider.project == "test-project"
            assert provider.location == "us-central1"
            
            # Vertex AI 클라이언트가 올바른 파라미터로 생성되었는지 확인
            mock_client_class.assert_called_once_with(
                vertexai=True,
                project="test-project",
                location="us-central1"
            )
    
    async def test_generate_success(self):
        """텍스트 생성 성공 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        # Mock 응답 데이터
        mock_candidate = Mock()
        mock_candidate.content = Mock()
        mock_candidate.content.parts = [Mock()]
        mock_candidate.content.parts[0].text = "테스트 응답입니다."
        mock_candidate.finish_reason = "STOP"
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.aio = Mock()
            mock_client.aio.models = Mock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="gemini-1.5-flash"
            )
            
            assert result.is_success()
            response_text = result.unwrap()
            assert response_text == "테스트 응답입니다."
            
            # generate_content가 올바른 파라미터로 호출되었는지 확인
            mock_client.aio.models.generate_content.assert_called_once()
            call_args = mock_client.aio.models.generate_content.call_args
            assert call_args[1]["model"] == "gemini-1.5-flash"
            assert call_args[1]["contents"][0]["parts"][0]["text"] == "테스트 프롬프트"
    
    async def test_generate_with_system_instruction(self):
        """시스템 명령과 함께 텍스트 생성 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        mock_candidate = Mock()
        mock_candidate.content = Mock()
        mock_candidate.content.parts = [Mock()]
        mock_candidate.content.parts[0].text = "시스템 명령 적용된 응답"
        mock_candidate.finish_reason = "STOP"
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.aio = Mock()
            mock_client.aio.models = Mock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="gemini-1.5-pro",
                system_instruction="당신은 도움이 되는 AI 어시스턴트입니다.",
                temperature=0.5,
                max_tokens=500
            )
            
            assert result.is_success()
            response_text = result.unwrap()
            assert response_text == "시스템 명령 적용된 응답"
            
            # 시스템 명령과 추가 파라미터가 전달되었는지 확인
            call_args = mock_client.aio.models.generate_content.call_args
            assert "system_instruction" in call_args[1]
            assert call_args[1]["system_instruction"]["parts"][0]["text"] == "당신은 도움이 되는 AI 어시스턴트입니다."
            assert call_args[1]["generation_config"]["temperature"] == 0.5
            assert call_args[1]["generation_config"]["max_output_tokens"] == 500
    
    async def test_generate_safety_blocked(self):
        """안전 정책으로 차단된 경우 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        mock_candidate = Mock()
        mock_candidate.finish_reason = "SAFETY"
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.aio = Mock()
            mock_client.aio.models = Mock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="부적절한 프롬프트",
                model="gemini-1.5-flash"
            )
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "안전 정책에 의해 차단" in error_message
    
    async def test_generate_failure(self):
        """텍스트 생성 실패 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.aio = Mock()
            mock_client.aio.models = Mock()
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=Exception("API 호출 실패")
            )
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="gemini-1.5-flash"
            )
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "Gemini API 호출 실패" in error_message
            assert "API 호출 실패" in error_message
    
    async def test_embed_success(self):
        """임베딩 생성 성공 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        # Mock 임베딩 응답
        mock_embedding = Mock()
        mock_embedding.values = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        mock_response = Mock()
        mock_response.embedding = mock_embedding
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.aio = Mock()
            mock_client.aio.models = Mock()
            mock_client.aio.models.embed_content = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.embed(
                text="테스트 텍스트",
                model="text-embedding-004"
            )
            
            assert result.is_success()
            embedding_vector = result.unwrap()
            assert embedding_vector == [0.1, 0.2, 0.3, 0.4, 0.5]
            
            # embed_content가 올바른 파라미터로 호출되었는지 확인
            mock_client.aio.models.embed_content.assert_called_once_with(
                model="text-embedding-004",
                content="테스트 텍스트",
                task_type="RETRIEVAL_DOCUMENT"
            )
    
    async def test_embed_default_model(self):
        """기본 임베딩 모델 사용 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        mock_embedding = Mock()
        mock_embedding.values = [0.1, 0.2, 0.3]
        
        mock_response = Mock()
        mock_response.embedding = mock_embedding
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.aio = Mock()
            mock_client.aio.models = Mock()
            mock_client.aio.models.embed_content = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.embed("테스트 텍스트")  # 모델 지정하지 않음
            
            assert result.is_success()
            
            # 기본 모델이 사용되었는지 확인
            call_args = mock_client.aio.models.embed_content.call_args
            assert call_args[1]["model"] == "text-embedding-004"
    
    async def test_embed_failure(self):
        """임베딩 생성 실패 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.aio = Mock()
            mock_client.aio.models = Mock()
            mock_client.aio.models.embed_content = AsyncMock(
                side_effect=Exception("임베딩 API 실패")
            )
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.embed("테스트 텍스트")
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "Gemini 임베딩 실패" in error_message
    
    def test_get_token_count_success(self):
        """토큰 수 계산 성공 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        # Mock 토큰 카운트 응답
        mock_response = Mock()
        mock_response.total_tokens = 15
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.models = Mock()
            mock_client.models.count_tokens = Mock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = provider.get_token_count("테스트 텍스트", "gemini-1.5-flash")
            
            assert result.is_success()
            token_count = result.unwrap()
            assert token_count == 15
            
            # count_tokens가 올바른 파라미터로 호출되었는지 확인
            mock_client.models.count_tokens.assert_called_once_with(
                model="gemini-1.5-flash",
                contents=[{"parts": [{"text": "테스트 텍스트"}]}]
            )
    
    def test_get_token_count_fallback(self):
        """토큰 수 계산 실패시 추정값 반환 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.models = Mock()
            mock_client.models.count_tokens = Mock(
                side_effect=Exception("토큰 계산 실패")
            )
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            test_text = "hello world test"  # 3 단어
            result = provider.get_token_count(test_text, "gemini-1.5-flash")
            
            assert result.is_success()
            token_count = result.unwrap()
            # 3 단어 * 1.3 = 3.9 -> 3 토큰으로 추정
            assert token_count == int(3 * 1.3)
    
    def test_get_available_models_success(self):
        """사용 가능한 모델 목록 조회 성공 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        # Mock 모델 목록
        mock_model1 = Mock()
        mock_model1.name = "models/gemini-1.5-flash"
        mock_model1.display_name = "Gemini 1.5 Flash"
        mock_model1.description = "Fast and versatile model"
        
        mock_model2 = Mock()
        mock_model2.name = "models/gemini-1.5-pro"
        mock_model2.display_name = "Gemini 1.5 Pro"
        mock_model2.description = "Advanced reasoning model"
        
        mock_models = [mock_model1, mock_model2]
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.models = Mock()
            mock_client.models.list = Mock(return_value=mock_models)
            mock_client_class.return_value = mock_client
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = provider.get_available_models()
            
            assert result.is_success()
            models = result.unwrap()
            assert len(models) == 2
            assert models[0]["name"] == "models/gemini-1.5-flash"
            assert models[0]["display_name"] == "Gemini 1.5 Flash"
            assert models[1]["name"] == "models/gemini-1.5-pro"
    
    def test_get_provider_info(self):
        """Provider 정보 반환 테스트"""
        if not self.has_gemini:
            pytest.skip("Google GenAI SDK가 설치되지 않았습니다")
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # 직접 API 사용 모드
            provider = self.provider_class(api_key=self.api_key)
            info = provider.get_provider_info()
            
            assert info["name"] == "GeminiProvider"
            assert info["provider_type"] == "gemini"
            assert info["api_type"] == "direct_api"
            assert info["multimodal_support"] is True
            assert info["function_calling_support"] is True
            
            # Vertex AI 모드
            provider_vertex = self.provider_class(
                project="test-project",
                use_vertex=True
            )
            info_vertex = provider_vertex.get_provider_info()
            
            assert info_vertex["api_type"] == "vertex_ai"
            assert info_vertex["project"] == "test-project"