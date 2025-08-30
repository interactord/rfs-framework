"""
Google Gemini Provider 구현

Google GenAI SDK를 사용하여 Gemini 모델 기능을 제공하는 Provider 구현체입니다.
Result Pattern과 RFS Framework의 모든 패턴을 준수합니다.
"""

from typing import List, Optional, Dict, Any, Union
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from .base import LLMProvider

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


if GEMINI_AVAILABLE:
    @Service("llm_service")
    class GeminiProvider(LLMProvider):
        """Google Gemini API Provider
        
        Google의 Gemini 모델들을 사용하여 텍스트 생성과 임베딩을 제공합니다.
        Vertex AI와 직접 Gemini API를 모두 지원합니다.
        """
        
        def __init__(
            self,
            api_key: Optional[str] = None,
            project: Optional[str] = None,
            location: str = "us-central1",
            use_vertex: bool = False,
            client_options: Optional[Dict[str, Any]] = None
        ):
            """Gemini Provider 초기화
            
            Args:
                api_key: Gemini API 키 (환경변수 GEMINI_API_KEY에서 자동 로드)
                project: GCP 프로젝트 ID (Vertex AI 사용시 필요)
                location: GCP 리전 (Vertex AI 사용시)
                use_vertex: Vertex AI API 사용 여부
                client_options: 추가 클라이언트 설정 옵션
            """
            if not GEMINI_AVAILABLE:
                raise ImportError(
                    "Google GenAI SDK가 설치되지 않았습니다. 'pip install google-genai' 명령으로 설치하세요."
                )
            
            try:
                # Client 초기화
                if use_vertex:
                    if not project:
                        raise ValueError("Vertex AI 사용시 project 매개변수가 필요합니다")
                    self.client = genai.Client(
                        vertexai=True,
                        project=project,
                        location=location,
                        **(client_options or {})
                    )
                else:
                    # Direct Gemini API 사용
                    self.client = genai.Client(
                        api_key=api_key,
                        **(client_options or {})
                    )
                
                self.use_vertex = use_vertex
                self.project = project
                self.location = location
                
                # Provider 메타데이터
                self.version = "1.0.0"
                self.supported_models = [
                    "gemini-2.0-flash-exp",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash", 
                    "gemini-1.5-flash-8b"
                ]
                self.capabilities = [
                    "text_generation", 
                    "chat", 
                    "multimodal",
                    "function_calling",
                    "token_counting"
                ]
                
                # 기본 안전 설정
                self.default_safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH", 
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
                
            except Exception as e:
                raise RuntimeError(f"Gemini Provider 초기화 실패: {str(e)}")
        
        async def generate(
            self,
            prompt: str,
            model: str,
            **kwargs
        ) -> Result[str, str]:
            """Gemini API를 사용하여 텍스트 생성
            
            Args:
                prompt: 생성할 텍스트에 대한 프롬프트
                model: 사용할 Gemini 모델명
                **kwargs: 추가 파라미터
                
            Returns:
                Result[str, str]: 성공시 생성된 텍스트, 실패시 에러 메시지
            """
            try:
                # 기본 생성 설정
                generation_config = {
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_output_tokens": kwargs.get("max_tokens", 1000),
                    "top_p": kwargs.get("top_p", 0.95),
                    "top_k": kwargs.get("top_k", 40)
                }
                
                # 안전 설정 (사용자 정의 또는 기본값)
                safety_settings = kwargs.get("safety_settings", self.default_safety_settings)
                
                # 요청 구성
                request_params = {
                    "model": model,
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generation_config": generation_config,
                    "safety_settings": safety_settings
                }
                
                # 시스템 명령 지원 (있는 경우)
                if "system_instruction" in kwargs:
                    request_params["system_instruction"] = {
                        "parts": [{"text": kwargs["system_instruction"]}]
                    }
                
                # API 호출
                response = await self.client.aio.models.generate_content(**request_params)
                
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    
                    # 안전 체크
                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason == "SAFETY":
                        return Failure("콘텐츠가 안전 정책에 의해 차단되었습니다")
                    
                    if candidate.content and candidate.content.parts:
                        text_content = candidate.content.parts[0].text
                        return Success(text_content)
                    else:
                        return Failure("Gemini API가 빈 응답을 반환했습니다")
                else:
                    return Failure("Gemini API 응답에 후보가 없습니다")
                    
            except Exception as e:
                error_msg = str(e)
                
                # 일반적인 Gemini 에러 처리
                if "quota" in error_msg.lower():
                    return Failure(f"API 할당량 초과: {error_msg}")
                elif "permission" in error_msg.lower() or "auth" in error_msg.lower():
                    return Failure(f"인증 오류: {error_msg}")
                elif "rate" in error_msg.lower():
                    return Failure(f"요청 속도 제한 초과: {error_msg}")
                else:
                    return Failure(f"Gemini API 호출 실패: {error_msg}")
        
        async def embed(
            self,
            text: str,
            model: Optional[str] = None
        ) -> Result[List[float], str]:
            """Gemini Embeddings API를 사용하여 텍스트 임베딩
            
            Args:
                text: 임베딩할 텍스트
                model: 임베딩 모델명 (기본: text-embedding-004)
                
            Returns:
                Result[List[float], str]: 성공시 임베딩 벡터, 실패시 에러 메시지
            """
            try:
                # 기본 임베딩 모델
                embedding_model = model or "text-embedding-004"
                
                # 임베딩 요청
                response = await self.client.aio.models.embed_content(
                    model=embedding_model,
                    content=text,
                    task_type="RETRIEVAL_DOCUMENT"  # 기본값으로 문서 검색용
                )
                
                if response.embedding and response.embedding.values:
                    return Success(response.embedding.values)
                else:
                    return Failure("Gemini Embeddings API가 빈 임베딩을 반환했습니다")
                    
            except Exception as e:
                error_msg = str(e)
                
                # 임베딩 특화 에러 처리
                if "model" in error_msg.lower() and "not found" in error_msg.lower():
                    return Failure(f"임베딩 모델을 찾을 수 없습니다: {model}")
                elif "quota" in error_msg.lower():
                    return Failure(f"임베딩 API 할당량 초과: {error_msg}")
                else:
                    return Failure(f"Gemini 임베딩 실패: {error_msg}")
        
        def get_token_count(self, text: str, model: str) -> Result[int, str]:
            """Gemini API를 사용하여 토큰 수 계산
            
            Args:
                text: 토큰 수를 계산할 텍스트
                model: 모델명 (토큰 계산에 영향)
                
            Returns:
                Result[int, str]: 성공시 토큰 수, 실패시 에러 메시지
            """
            try:
                # Gemini API의 count_tokens 메서드 사용
                response = self.client.models.count_tokens(
                    model=model,
                    contents=[{"parts": [{"text": text}]}]
                )
                
                if response.total_tokens is not None:
                    return Success(response.total_tokens)
                else:
                    return Failure("토큰 수 계산 실패: API가 토큰 수를 반환하지 않았습니다")
                    
            except Exception as e:
                error_msg = str(e)
                
                # 토큰 계산 관련 에러 처리
                if "model" in error_msg.lower() and "not found" in error_msg.lower():
                    return Failure(f"모델을 찾을 수 없습니다: {model}")
                else:
                    # 토큰 계산 실패시 대략적인 추정값 반환
                    estimated_tokens = len(text.split()) * 1.3  # 대략적인 추정
                    return Success(int(estimated_tokens))
        
        def get_available_models(self) -> Result[List[Dict[str, Any]], str]:
            """사용 가능한 Gemini 모델 목록 조회
            
            Returns:
                Result[List[Dict], str]: 사용 가능한 모델 정보 목록
            """
            try:
                models_response = self.client.models.list()
                
                available_models = []
                for model in models_response:
                    model_info = {
                        "name": model.name,
                        "display_name": getattr(model, 'display_name', model.name),
                        "description": getattr(model, 'description', ''),
                        "version": getattr(model, 'version', ''),
                        "input_token_limit": getattr(model, 'input_token_limit', None),
                        "output_token_limit": getattr(model, 'output_token_limit', None),
                        "supported_generation_methods": getattr(model, 'supported_generation_methods', [])
                    }
                    available_models.append(model_info)
                
                return Success(available_models)
                
            except Exception as e:
                return Failure(f"모델 목록 조회 실패: {str(e)}")
        
        def get_provider_info(self) -> Dict[str, Any]:
            """Gemini Provider 정보 반환"""
            base_info = super().get_provider_info()
            
            gemini_info = {
                "provider_type": "gemini",
                "api_type": "vertex_ai" if self.use_vertex else "direct_api",
                "project": self.project if self.use_vertex else None,
                "location": self.location if self.use_vertex else None,
                "safety_settings": "enabled",
                "multimodal_support": True,
                "function_calling_support": True
            }
            
            return {**base_info, **gemini_info}


# Gemini 라이브러리가 없는 경우를 위한 더미 클래스
else:
    class GeminiProvider:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Google GenAI SDK가 설치되지 않았습니다. 'pip install google-genai' 명령으로 설치하세요."
            )