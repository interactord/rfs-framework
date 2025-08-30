"""
OpenAI Provider 구현

OpenAI API를 사용하여 LLM 기능을 제공하는 Provider 구현체입니다.
Result Pattern과 RFS Framework의 모든 패턴을 준수합니다.
"""

from typing import List, Optional, Dict, Any
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from .base import LLMProvider

try:
    from openai import AsyncOpenAI
    import tiktoken
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


if OPENAI_AVAILABLE:
    @Service("llm_service")
    class OpenAIProvider(LLMProvider):
        """OpenAI API Provider
        
        OpenAI의 GPT 모델들을 사용하여 텍스트 생성과 임베딩을 제공합니다.
        """
        
        def __init__(
            self, 
            api_key: str, 
            base_url: Optional[str] = None,
            organization: Optional[str] = None,
            project: Optional[str] = None
        ):
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "OpenAI가 설치되지 않았습니다. 'pip install openai tiktoken' 명령으로 설치하세요."
                )
            
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                organization=organization,
                project=project
            )
            
            self.version = "1.0.0"
            self.supported_models = [
                "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini",
                "gpt-3.5-turbo", "gpt-3.5-turbo-16k"
            ]
            self.capabilities = ["text_generation", "chat", "embeddings", "token_counting"]
        
        async def generate(
            self, 
            prompt: str, 
            model: str,
            **kwargs
        ) -> Result[str, str]:
            """OpenAI API를 사용하여 텍스트 생성"""
            try:
                # 기본값 설정
                default_params = {
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "top_p": 1.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0
                }
                
                # 파라미터 병합
                params = {**default_params, **kwargs}
                
                # Chat Completion API 사용
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    **params
                )
                
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    if content:
                        return Success(content)
                    else:
                        return Failure("OpenAI API가 빈 응답을 반환했습니다")
                else:
                    return Failure("OpenAI API 응답에 선택지가 없습니다")
                
            except Exception as e:
                return Failure(f"OpenAI API 호출 실패: {str(e)}")
        
        async def embed(
            self, 
            text: str, 
            model: Optional[str] = None
        ) -> Result[List[float], str]:
            """OpenAI Embeddings API를 사용하여 텍스트 임베딩"""
            try:
                # 기본 임베딩 모델 설정
                embedding_model = model or "text-embedding-3-small"
                
                response = await self.client.embeddings.create(
                    model=embedding_model,
                    input=text
                )
                
                if response.data and len(response.data) > 0:
                    embedding = response.data[0].embedding
                    return Success(embedding)
                else:
                    return Failure("OpenAI Embeddings API가 빈 응답을 반환했습니다")
                    
            except Exception as e:
                return Failure(f"OpenAI 임베딩 실패: {str(e)}")
        
        def get_token_count(self, text: str, model: str) -> int:
            """tiktoken을 사용하여 토큰 수 계산"""
            try:
                # 모델에 따른 인코딩 선택
                if model.startswith("gpt-4"):
                    encoding = tiktoken.encoding_for_model("gpt-4")
                elif model.startswith("gpt-3.5"):
                    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
                else:
                    # 기본값으로 cl100k_base 사용
                    encoding = tiktoken.get_encoding("cl100k_base")
                
                return len(encoding.encode(text))
            
            except Exception:
                # 대략적인 토큰 계산 (1토큰 ≈ 4글자)
                return len(text) // 4
        
        async def generate_chat(
            self,
            messages: List[Dict[str, str]],
            model: str,
            **kwargs
        ) -> Result[str, str]:
            """채팅 형식으로 텍스트 생성 (추가 기능)"""
            try:
                default_params = {
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
                
                params = {**default_params, **kwargs}
                
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **params
                )
                
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    if content:
                        return Success(content)
                    else:
                        return Failure("OpenAI API가 빈 응답을 반환했습니다")
                else:
                    return Failure("OpenAI API 응답에 선택지가 없습니다")
                    
            except Exception as e:
                return Failure(f"OpenAI 채팅 API 호출 실패: {str(e)}")
        
        def get_provider_info(self) -> Dict[str, Any]:
            """OpenAI Provider 정보 반환"""
            return {
                "name": "OpenAIProvider",
                "version": self.version,
                "supported_models": self.supported_models,
                "capabilities": self.capabilities,
                "api_version": "v1",
                "pricing_info": {
                    "gpt-4": {"input": 0.00003, "output": 0.00006},
                    "gpt-3.5-turbo": {"input": 0.0000015, "output": 0.000002},
                    "text-embedding-3-small": {"input": 0.00000002}
                }
            }

else:
    class OpenAIProvider(LLMProvider):
        """OpenAI가 설치되지 않은 경우의 더미 클래스"""
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "OpenAI 라이브러리가 설치되지 않았습니다. "
                "'pip install openai tiktoken' 명령으로 설치하세요."
            )
        
        async def generate(self, prompt: str, model: str, **kwargs) -> Result[str, str]:
            return Failure("OpenAI 라이브러리가 설치되지 않았습니다")
        
        async def embed(self, text: str, model: Optional[str] = None) -> Result[List[float], str]:
            return Failure("OpenAI 라이브러리가 설치되지 않았습니다")
        
        def get_token_count(self, text: str, model: str) -> int:
            return 0