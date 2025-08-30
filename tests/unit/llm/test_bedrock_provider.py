"""
AWS Bedrock Provider 단위 테스트

Bedrock Provider의 기본 동작을 테스트합니다.
Mock을 사용하여 외부 API 의존성을 제거합니다.
"""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from rfs.core.result import Success, Failure


@pytest.mark.asyncio
class TestBedrockProvider:
    """AWS Bedrock Provider 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.api_key = "test_bedrock_api_key"
        self.region = "us-east-1"
        
        # Bedrock 관련 import 확인
        try:
            from rfs.llm.providers.bedrock import BedrockProvider
            self.provider_class = BedrockProvider
            self.has_bedrock = True
        except ImportError:
            self.has_bedrock = False
    
    def test_provider_initialization_api_key(self):
        """API Key 인증으로 Bedrock Provider 초기화 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client') as mock_client:
            mock_runtime_client = Mock()
            mock_bedrock_client = Mock()
            mock_client.side_effect = [mock_runtime_client, mock_bedrock_client]
            
            with patch.dict('os.environ', {'AWS_BEARER_TOKEN_BEDROCK': self.api_key}):
                provider = self.provider_class(api_key=self.api_key, region=self.region)
                
                assert provider.client == mock_runtime_client
                assert provider.bedrock_client == mock_bedrock_client
                assert provider.region == self.region
                assert provider.version == "1.0.0"
                assert "anthropic.claude-3-5-sonnet-20241022-v2:0" in provider.supported_models
                assert "text_generation" in provider.capabilities
    
    def test_provider_initialization_credentials(self):
        """AWS 자격증명으로 초기화 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.Session') as mock_session_class:
            mock_session = Mock()
            mock_client = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session
            
            with patch('boto3.client') as mock_boto_client:
                mock_bedrock_client = Mock()
                mock_boto_client.return_value = mock_bedrock_client
                
                provider = self.provider_class(
                    aws_access_key="test_access_key",
                    aws_secret_key="test_secret_key",
                    region=self.region
                )
                
                assert provider.client == mock_client
                assert provider.bedrock_client == mock_bedrock_client
                
                # Session이 올바른 파라미터로 생성되었는지 확인
                mock_session_class.assert_called_once_with(
                    aws_access_key_id="test_access_key",
                    aws_secret_access_key="test_secret_key",
                    aws_session_token=None,
                    region_name=self.region,
                    profile_name=None
                )
    
    def test_get_model_provider(self):
        """모델 제공업체 추출 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client'):
            provider = self.provider_class(api_key=self.api_key)
            
            assert provider._get_model_provider("anthropic.claude-3-haiku") == "anthropic"
            assert provider._get_model_provider("meta.llama3-70b") == "meta"
            assert provider._get_model_provider("amazon.titan-text") == "amazon"
            assert provider._get_model_provider("unknown.model") == "unknown"
    
    async def test_generate_claude_success(self):
        """Claude 모델 텍스트 생성 성공 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        # Mock Claude 응답
        claude_response = {
            "content": [
                {
                    "type": "text",
                    "text": "Claude 모델 응답입니다."
                }
            ]
        }
        
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps(claude_response).encode()
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.return_value = mock_response
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="anthropic.claude-3-haiku-20240307-v1:0",
                temperature=0.5,
                max_tokens=1000
            )
            
            assert result.is_success()
            response_text = result.unwrap()
            assert response_text == "Claude 모델 응답입니다."
            
            # invoke_model이 올바른 파라미터로 호출되었는지 확인
            mock_client.invoke_model.assert_called_once()
            call_args = mock_client.invoke_model.call_args
            assert call_args[1]["modelId"] == "anthropic.claude-3-haiku-20240307-v1:0"
            assert call_args[1]["contentType"] == "application/json"
            
            # 요청 본문 확인
            body_data = json.loads(call_args[1]["body"])
            assert body_data["temperature"] == 0.5
            assert body_data["max_tokens"] == 1000
            assert body_data["messages"][0]["content"][0]["text"] == "테스트 프롬프트"
    
    async def test_generate_llama_success(self):
        """Llama 모델 텍스트 생성 성공 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        # Mock Llama 응답
        llama_response = {
            "generation": "Llama 모델 응답입니다."
        }
        
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps(llama_response).encode()
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.return_value = mock_response
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="meta.llama3-1-8b-instruct-v1:0",
                temperature=0.7,
                max_tokens=512
            )
            
            assert result.is_success()
            response_text = result.unwrap()
            assert response_text == "Llama 모델 응답입니다."
            
            # 요청 본문이 Llama 형식으로 구성되었는지 확인
            call_args = mock_client.invoke_model.call_args
            body_data = json.loads(call_args[1]["body"])
            assert body_data["prompt"] == "테스트 프롬프트"
            assert body_data["temperature"] == 0.7
            assert body_data["max_gen_len"] == 512
    
    async def test_generate_titan_success(self):
        """Titan 모델 텍스트 생성 성공 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        # Mock Titan 응답
        titan_response = {
            "results": [
                {
                    "outputText": "Titan 모델 응답입니다."
                }
            ]
        }
        
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps(titan_response).encode()
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.return_value = mock_response
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="amazon.titan-text-express-v1",
                temperature=0.8
            )
            
            assert result.is_success()
            response_text = result.unwrap()
            assert response_text == "Titan 모델 응답입니다."
            
            # 요청 본문이 Titan 형식으로 구성되었는지 확인
            call_args = mock_client.invoke_model.call_args
            body_data = json.loads(call_args[1]["body"])
            assert body_data["inputText"] == "테스트 프롬프트"
            assert body_data["textGenerationConfig"]["temperature"] == 0.8
    
    async def test_generate_unsupported_provider(self):
        """지원하지 않는 모델 제공업체 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client'):
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="unsupported.unknown-model"
            )
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "지원하지 않는 모델 제공업체" in error_message
    
    async def test_generate_client_error(self):
        """AWS ClientError 처리 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        # ClientError Mock 생성
        from botocore.exceptions import ClientError
        
        error_response = {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "User: ... is not authorized to perform: bedrock:InvokeModel"
            }
        }
        client_error = ClientError(error_response, "InvokeModel")
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.side_effect = client_error
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="anthropic.claude-3-haiku-20240307-v1:0"
            )
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "모델 접근 권한 없음" in error_message
    
    async def test_generate_general_exception(self):
        """일반 예외 처리 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.side_effect = Exception("연결 오류")
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.generate(
                prompt="테스트 프롬프트",
                model="anthropic.claude-3-haiku-20240307-v1:0"
            )
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "Bedrock API 호출 실패" in error_message
            assert "연결 오류" in error_message
    
    async def test_embed_success(self):
        """임베딩 생성 성공 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        # Mock 임베딩 응답
        embedding_response = {
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
        }
        
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps(embedding_response).encode()
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.return_value = mock_response
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.embed(
                text="테스트 텍스트",
                model="amazon.titan-embed-text-v1"
            )
            
            assert result.is_success()
            embedding_vector = result.unwrap()
            assert embedding_vector == [0.1, 0.2, 0.3, 0.4, 0.5]
            
            # 임베딩 요청이 올바르게 구성되었는지 확인
            call_args = mock_client.invoke_model.call_args
            assert call_args[1]["modelId"] == "amazon.titan-embed-text-v1"
            body_data = json.loads(call_args[1]["body"])
            assert body_data["inputText"] == "테스트 텍스트"
    
    async def test_embed_default_model(self):
        """기본 임베딩 모델 사용 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        embedding_response = {
            "embedding": [0.1, 0.2, 0.3]
        }
        
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps(embedding_response).encode()
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.return_value = mock_response
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.embed("테스트 텍스트")  # 모델 지정하지 않음
            
            assert result.is_success()
            
            # 기본 임베딩 모델이 사용되었는지 확인
            call_args = mock_client.invoke_model.call_args
            assert call_args[1]["modelId"] == "amazon.titan-embed-text-v1"
    
    async def test_embed_failure(self):
        """임베딩 생성 실패 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client') as mock_client_func:
            mock_client = Mock()
            mock_client.invoke_model.side_effect = Exception("임베딩 실패")
            mock_bedrock_client = Mock()
            mock_client_func.side_effect = [mock_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = await provider.embed("테스트 텍스트")
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "Bedrock 임베딩 호출 실패" in error_message
    
    def test_get_token_count_claude(self):
        """Claude 모델 토큰 수 추정 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client'):
            provider = self.provider_class(api_key=self.api_key)
            
            test_text = "hello world test"  # 3 단어
            result = provider.get_token_count(test_text, "anthropic.claude-3-haiku")
            
            assert result.is_success()
            token_count = result.unwrap()
            # Claude: 단어당 1.3 토큰 추정
            expected_tokens = int(3 * 1.3)
            assert token_count == expected_tokens
    
    def test_get_token_count_llama(self):
        """Llama 모델 토큰 수 추정 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client'):
            provider = self.provider_class(api_key=self.api_key)
            
            test_text = "hello world test example"  # 4 단어
            result = provider.get_token_count(test_text, "meta.llama3-8b")
            
            assert result.is_success()
            token_count = result.unwrap()
            # Llama: 단어당 1.2 토큰 추정
            expected_tokens = int(4 * 1.2)
            assert token_count == expected_tokens
    
    def test_get_available_models_success(self):
        """사용 가능한 모델 목록 조회 성공 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        # Mock 모델 목록 응답
        models_response = {
            "modelSummaries": [
                {
                    "modelId": "anthropic.claude-3-haiku-20240307-v1:0",
                    "modelName": "Claude 3 Haiku",
                    "providerName": "Anthropic",
                    "inputModalities": ["TEXT"],
                    "outputModalities": ["TEXT"],
                    "responseStreamingSupported": True
                },
                {
                    "modelId": "meta.llama3-1-8b-instruct-v1:0",
                    "modelName": "Llama 3.1 8B Instruct",
                    "providerName": "Meta",
                    "inputModalities": ["TEXT"],
                    "outputModalities": ["TEXT"],
                    "responseStreamingSupported": False
                }
            ]
        }
        
        with patch('boto3.client') as mock_client_func:
            mock_runtime_client = Mock()
            mock_bedrock_client = Mock()
            mock_bedrock_client.list_foundation_models.return_value = models_response
            mock_client_func.side_effect = [mock_runtime_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = provider.get_available_models()
            
            assert result.is_success()
            models = result.unwrap()
            assert len(models) == 2
            
            # 첫 번째 모델 확인
            assert models[0]["model_id"] == "anthropic.claude-3-haiku-20240307-v1:0"
            assert models[0]["model_name"] == "Claude 3 Haiku"
            assert models[0]["provider_name"] == "Anthropic"
            assert models[0]["response_streaming_supported"] is True
            
            # 두 번째 모델 확인
            assert models[1]["model_id"] == "meta.llama3-1-8b-instruct-v1:0"
            assert models[1]["provider_name"] == "Meta"
    
    def test_get_available_models_failure(self):
        """모델 목록 조회 실패 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client') as mock_client_func:
            mock_runtime_client = Mock()
            mock_bedrock_client = Mock()
            mock_bedrock_client.list_foundation_models.side_effect = Exception("모델 목록 조회 실패")
            mock_client_func.side_effect = [mock_runtime_client, mock_bedrock_client]
            
            provider = self.provider_class(api_key=self.api_key)
            
            result = provider.get_available_models()
            
            assert result.is_failure()
            error_message = result.unwrap_error()
            assert "모델 목록 조회 실패" in error_message
    
    def test_get_provider_info(self):
        """Provider 정보 반환 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client'):
            # API Key 인증 모드
            with patch.dict('os.environ', {'AWS_BEARER_TOKEN_BEDROCK': 'test_token'}):
                provider = self.provider_class(api_key=self.api_key)
                info = provider.get_provider_info()
                
                assert info["name"] == "BedrockProvider"
                assert info["provider_type"] == "bedrock"
                assert info["region"] == "us-east-1"
                assert info["api_key_auth"] is True
                assert info["iam_auth"] is False
                assert "anthropic" in info["supported_providers"]
                assert info["converse_api_support"] is True
                assert info["multimodal_support"] is True
    
    def test_get_provider_info_iam_mode(self):
        """IAM 인증 모드에서 Provider 정보 반환 테스트"""
        if not self.has_bedrock:
            pytest.skip("boto3가 설치되지 않았습니다")
        
        with patch('boto3.client'):
            # IAM 인증 모드 (API Key 없음)
            with patch.dict('os.environ', {}, clear=True):  # 환경변수 제거
                provider = self.provider_class(
                    aws_access_key="test_access_key",
                    aws_secret_key="test_secret_key"
                )
                info = provider.get_provider_info()
                
                assert info["api_key_auth"] is False
                assert info["iam_auth"] is True