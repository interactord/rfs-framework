"""
AWS Bedrock Provider 구현

AWS Bedrock API Key 인증을 사용하여 다양한 Foundation Models을 제공하는 Provider 구현체입니다.
Result Pattern과 RFS Framework의 모든 패턴을 준수합니다.
"""

import json
import os
from typing import List, Optional, Dict, Any, Union
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from .base import LLMProvider

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


if BOTO3_AVAILABLE:
    @Service("llm_service")
    class BedrockProvider(LLMProvider):
        """AWS Bedrock API Provider
        
        AWS Bedrock의 다양한 Foundation Models (Claude, Llama, Titan 등)을 
        통합적으로 사용할 수 있게 해주는 Provider입니다.
        """
        
        def __init__(
            self,
            api_key: Optional[str] = None,
            region: str = "us-east-1", 
            aws_access_key: Optional[str] = None,
            aws_secret_key: Optional[str] = None,
            aws_session_token: Optional[str] = None,
            profile_name: Optional[str] = None,
            endpoint_url: Optional[str] = None
        ):
            """Bedrock Provider 초기화
            
            Args:
                api_key: AWS Bedrock API Key (AWS_BEARER_TOKEN_BEDROCK 환경변수에서 자동 로드)
                region: AWS 리전
                aws_access_key: AWS Access Key ID
                aws_secret_key: AWS Secret Access Key
                aws_session_token: AWS Session Token (temporary credentials)
                profile_name: AWS Profile 이름
                endpoint_url: 커스텀 엔드포인트 URL
            """
            if not BOTO3_AVAILABLE:
                raise ImportError(
                    "boto3가 설치되지 않았습니다. 'pip install boto3' 명령으로 설치하세요."
                )
            
            self.region = region
            
            try:
                # API Key 기반 인증 (새로운 방식)
                if api_key or os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
                    bearer_token = api_key or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
                    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = bearer_token
                    
                    self.client = boto3.client(
                        service_name="bedrock-runtime",
                        region_name=region,
                        endpoint_url=endpoint_url
                    )
                
                # 기존 AWS 자격 증명 기반 인증
                elif aws_access_key and aws_secret_key:
                    session = boto3.Session(
                        aws_access_key_id=aws_access_key,
                        aws_secret_access_key=aws_secret_key,
                        aws_session_token=aws_session_token,
                        region_name=region,
                        profile_name=profile_name
                    )
                    self.client = session.client(
                        service_name="bedrock-runtime",
                        endpoint_url=endpoint_url
                    )
                    
                else:
                    # 기본 AWS 자격 증명 체인 사용
                    self.client = boto3.client(
                        service_name="bedrock-runtime",
                        region_name=region,
                        endpoint_url=endpoint_url
                    )
                
                # 모델 접근을 위한 bedrock 클라이언트도 생성
                self.bedrock_client = boto3.client(
                    service_name="bedrock",
                    region_name=region,
                    endpoint_url=endpoint_url
                )
                
                # Provider 메타데이터
                self.version = "1.0.0"
                self.supported_models = [
                    # Anthropic Claude
                    "anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "anthropic.claude-3-5-sonnet-20240620-v1:0",
                    "anthropic.claude-3-5-haiku-20241022-v1:0",
                    "anthropic.claude-3-haiku-20240307-v1:0",
                    "anthropic.claude-3-opus-20240229-v1:0",
                    # Meta Llama
                    "meta.llama3-2-90b-instruct-v1:0",
                    "meta.llama3-2-11b-instruct-v1:0",
                    "meta.llama3-1-70b-instruct-v1:0",
                    "meta.llama3-1-8b-instruct-v1:0",
                    # Amazon Titan
                    "amazon.titan-text-premier-v1:0",
                    "amazon.titan-text-express-v1",
                    "amazon.titan-embed-text-v1"
                ]
                self.capabilities = [
                    "text_generation", 
                    "chat", 
                    "embeddings",
                    "multimodal",  # Claude 3 vision
                    "function_calling"  # Some models
                ]
                
                # 모델별 설정 매핑
                self.model_configs = {
                    "anthropic": {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4000,
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "top_k": 250,
                        "stop_sequences": []
                    },
                    "meta": {
                        "max_gen_len": 2048,
                        "temperature": 0.7,
                        "top_p": 0.9
                    },
                    "amazon": {
                        "maxTokenCount": 4000,
                        "temperature": 0.7,
                        "topP": 0.9
                    }
                }
                
            except Exception as e:
                raise RuntimeError(f"Bedrock Provider 초기화 실패: {str(e)}")
        
        def _get_model_provider(self, model: str) -> str:
            """모델명에서 제공업체 추출"""
            if model.startswith("anthropic."):
                return "anthropic"
            elif model.startswith("meta."):
                return "meta" 
            elif model.startswith("amazon."):
                return "amazon"
            elif model.startswith("ai21."):
                return "ai21"
            elif model.startswith("cohere."):
                return "cohere"
            else:
                return "unknown"
        
        def _prepare_anthropic_request(
            self, 
            prompt: str, 
            model: str, 
            **kwargs
        ) -> Dict[str, Any]:
            """Claude 모델을 위한 요청 준비"""
            config = self.model_configs["anthropic"].copy()
            config.update(kwargs)
            
            # max_tokens 매개변수 처리
            if "max_tokens" in config:
                config["max_tokens"] = config.pop("max_tokens")
            
            return {
                "anthropic_version": config.get("anthropic_version", "bedrock-2023-05-31"),
                "max_tokens": config.get("max_tokens", 4000),
                "temperature": config.get("temperature", 0.7),
                "top_p": config.get("top_p", 0.9),
                "top_k": config.get("top_k", 250),
                "stop_sequences": config.get("stop_sequences", []),
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}]
                    }
                ]
            }
        
        def _prepare_llama_request(
            self, 
            prompt: str, 
            model: str, 
            **kwargs
        ) -> Dict[str, Any]:
            """Llama 모델을 위한 요청 준비"""
            config = self.model_configs["meta"].copy()
            config.update(kwargs)
            
            return {
                "prompt": prompt,
                "max_gen_len": config.get("max_tokens", config.get("max_gen_len", 2048)),
                "temperature": config.get("temperature", 0.7),
                "top_p": config.get("top_p", 0.9)
            }
        
        def _prepare_titan_request(
            self, 
            prompt: str, 
            model: str, 
            **kwargs
        ) -> Dict[str, Any]:
            """Titan 모델을 위한 요청 준비"""
            config = self.model_configs["amazon"].copy()
            config.update(kwargs)
            
            return {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": config.get("max_tokens", config.get("maxTokenCount", 4000)),
                    "temperature": config.get("temperature", 0.7),
                    "topP": config.get("topP", 0.9),
                    "stopSequences": config.get("stop_sequences", [])
                }
            }
        
        async def generate(
            self,
            prompt: str,
            model: str,
            **kwargs
        ) -> Result[str, str]:
            """Bedrock API를 사용하여 텍스트 생성
            
            Args:
                prompt: 생성할 텍스트에 대한 프롬프트
                model: 사용할 Bedrock 모델명
                **kwargs: 추가 파라미터
                
            Returns:
                Result[str, str]: 성공시 생성된 텍스트, 실패시 에러 메시지
            """
            try:
                provider = self._get_model_provider(model)
                
                # 모델별 요청 구성
                if provider == "anthropic":
                    request_body = self._prepare_anthropic_request(prompt, model, **kwargs)
                elif provider == "meta":
                    request_body = self._prepare_llama_request(prompt, model, **kwargs)
                elif provider == "amazon":
                    request_body = self._prepare_titan_request(prompt, model, **kwargs)
                else:
                    return Failure(f"지원하지 않는 모델 제공업체: {provider}")
                
                # Bedrock API 호출
                response = self.client.invoke_model(
                    modelId=model,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(request_body)
                )
                
                # 응답 파싱
                response_body = json.loads(response["body"].read())
                
                # 모델별 응답 처리
                if provider == "anthropic":
                    if "content" in response_body and response_body["content"]:
                        content = response_body["content"][0]
                        if content.get("type") == "text":
                            return Success(content["text"])
                    return Failure("Claude 모델이 빈 응답을 반환했습니다")
                    
                elif provider == "meta":
                    if "generation" in response_body:
                        return Success(response_body["generation"])
                    return Failure("Llama 모델이 빈 응답을 반환했습니다")
                    
                elif provider == "amazon":
                    if "results" in response_body and response_body["results"]:
                        result = response_body["results"][0]
                        return Success(result.get("outputText", ""))
                    return Failure("Titan 모델이 빈 응답을 반환했습니다")
                    
                return Failure("알 수 없는 응답 형식입니다")
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                error_message = e.response.get("Error", {}).get("Message", str(e))
                
                # AWS 특화 에러 처리
                if error_code == "AccessDeniedException":
                    return Failure(f"모델 접근 권한 없음: {error_message}")
                elif error_code == "ValidationException":
                    return Failure(f"요청 유효성 검사 실패: {error_message}")
                elif error_code == "ThrottlingException":
                    return Failure(f"요청 속도 제한 초과: {error_message}")
                elif error_code == "ServiceUnavailableException":
                    return Failure(f"서비스 일시 불가: {error_message}")
                else:
                    return Failure(f"Bedrock API 오류 ({error_code}): {error_message}")
                    
            except Exception as e:
                return Failure(f"Bedrock API 호출 실패: {str(e)}")
        
        async def embed(
            self,
            text: str,
            model: Optional[str] = None
        ) -> Result[List[float], str]:
            """Bedrock Embeddings를 사용하여 텍스트 임베딩
            
            Args:
                text: 임베딩할 텍스트
                model: 임베딩 모델명 (기본: amazon.titan-embed-text-v1)
                
            Returns:
                Result[List[float], str]: 성공시 임베딩 벡터, 실패시 에러 메시지
            """
            try:
                # 기본 임베딩 모델
                embedding_model = model or "amazon.titan-embed-text-v1"
                
                # 임베딩 요청 구성
                request_body = {
                    "inputText": text
                }
                
                # Bedrock Embeddings API 호출
                response = self.client.invoke_model(
                    modelId=embedding_model,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(request_body)
                )
                
                # 응답 파싱
                response_body = json.loads(response["body"].read())
                
                if "embedding" in response_body:
                    return Success(response_body["embedding"])
                else:
                    return Failure("Bedrock Embeddings API가 빈 임베딩을 반환했습니다")
                    
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                error_message = e.response.get("Error", {}).get("Message", str(e))
                return Failure(f"Bedrock 임베딩 실패 ({error_code}): {error_message}")
                
            except Exception as e:
                return Failure(f"Bedrock 임베딩 호출 실패: {str(e)}")
        
        def get_token_count(self, text: str, model: str) -> Result[int, str]:
            """텍스트의 토큰 수 추정
            
            Bedrock은 직접적인 토큰 계산 API를 제공하지 않으므로,
            모델별 추정 알고리즘을 사용합니다.
            
            Args:
                text: 토큰 수를 계산할 텍스트
                model: 모델명
                
            Returns:
                Result[int, str]: 성공시 추정 토큰 수, 실패시 에러 메시지
            """
            try:
                provider = self._get_model_provider(model)
                
                # 기본적인 토큰 추정 (단어 수 기반)
                word_count = len(text.split())
                
                if provider == "anthropic":
                    # Claude: 대략 단어당 1.3 토큰
                    estimated_tokens = int(word_count * 1.3)
                elif provider == "meta":
                    # Llama: 대략 단어당 1.2 토큰
                    estimated_tokens = int(word_count * 1.2)
                elif provider == "amazon":
                    # Titan: 대략 단어당 1.25 토큰
                    estimated_tokens = int(word_count * 1.25)
                else:
                    # 기본값: 단어당 1.3 토큰
                    estimated_tokens = int(word_count * 1.3)
                
                return Success(estimated_tokens)
                
            except Exception as e:
                return Failure(f"토큰 수 추정 실패: {str(e)}")
        
        def get_available_models(self) -> Result[List[Dict[str, Any]], str]:
            """사용 가능한 Bedrock 모델 목록 조회
            
            Returns:
                Result[List[Dict], str]: 사용 가능한 모델 정보 목록
            """
            try:
                # Bedrock에서 사용 가능한 Foundation Models 조회
                response = self.bedrock_client.list_foundation_models()
                
                available_models = []
                for model in response.get("modelSummaries", []):
                    model_info = {
                        "model_id": model.get("modelId"),
                        "model_name": model.get("modelName"),
                        "provider_name": model.get("providerName"),
                        "input_modalities": model.get("inputModalities", []),
                        "output_modalities": model.get("outputModalities", []),
                        "response_streaming_supported": model.get("responseStreamingSupported", False),
                        "customizations_supported": model.get("customizationsSupported", []),
                        "inference_types_supported": model.get("inferenceTypesSupported", [])
                    }
                    available_models.append(model_info)
                
                return Success(available_models)
                
            except Exception as e:
                return Failure(f"모델 목록 조회 실패: {str(e)}")
        
        def get_provider_info(self) -> Dict[str, Any]:
            """Bedrock Provider 정보 반환"""
            base_info = super().get_provider_info()
            
            bedrock_info = {
                "provider_type": "bedrock",
                "region": self.region,
                "supported_providers": ["anthropic", "meta", "amazon", "ai21", "cohere"],
                "api_key_auth": "AWS_BEARER_TOKEN_BEDROCK" in os.environ,
                "iam_auth": "AWS_BEARER_TOKEN_BEDROCK" not in os.environ,
                "converse_api_support": True,
                "streaming_support": True,
                "multimodal_support": True
            }
            
            return {**base_info, **bedrock_info}


# boto3가 없는 경우를 위한 더미 클래스
else:
    class BedrockProvider:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "boto3가 설치되지 않았습니다. 'pip install boto3' 명령으로 설치하세요."
            )