"""
Anthropic Provider 구현

Anthropic의 Claude API를 사용하여 LLM 기능을 제공하는 Provider 구현체입니다.
Result Pattern과 RFS Framework의 모든 패턴을 준수합니다.
"""

from typing import List, Optional, Dict, Any
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from .base import LLMProvider

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


if ANTHROPIC_AVAILABLE:
    @Service("llm_service")
    class AnthropicProvider(LLMProvider):
        """Anthropic Claude API Provider
        
        Anthropic의 Claude 모델들을 사용하여 텍스트 생성을 제공합니다.
        """
        
        def __init__(
            self, 
            api_key: str,
            base_url: Optional[str] = None
        ):
            if not ANTHROPIC_AVAILABLE:
                raise ImportError(
                    "Anthropic이 설치되지 않았습니다. 'pip install anthropic' 명령으로 설치하세요."
                )
            
            self.client = anthropic.AsyncAnthropic(
                api_key=api_key,
                base_url=base_url
            )
            
            self.version = "1.0.0"
            self.supported_models = [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229", 
                "claude-3-haiku-20240307",
                "claude-3-5-sonnet-20241022"
            ]
            self.capabilities = ["text_generation", "chat", "token_counting"]
        
        async def generate(
            self, 
            prompt: str, 
            model: str,
            **kwargs
        ) -> Result[str, str]:
            """Anthropic API를 사용하여 텍스트 생성"""
            try:
                # 기본값 설정
                default_params = {
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
                
                # 파라미터 병합
                params = {**default_params, **kwargs}
                
                # Messages API 사용
                response = await self.client.messages.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    **params
                )
                
                if response.content and len(response.content) > 0:
                    # 텍스트 블록 추출
                    content_block = response.content[0]
                    if hasattr(content_block, 'text'):
                        return Success(content_block.text)
                    else:
                        return Failure("Anthropic API 응답 형식이 예상과 다릅니다")
                else:
                    return Failure("Anthropic API가 빈 응답을 반환했습니다")
                
            except Exception as e:
                return Failure(f"Anthropic API 호출 실패: {str(e)}")
        
        async def embed(
            self, 
            text: str, 
            model: Optional[str] = None
        ) -> Result[List[float], str]:
            """Anthropic은 현재 임베딩 API를 제공하지 않습니다"""
            return Failure("Anthropic은 현재 임베딩 API를 지원하지 않습니다")
        
        def get_token_count(self, text: str, model: str) -> int:
            """대략적인 토큰 수 계산 (Anthropic의 정확한 토큰 계산 라이브러리는 없음)"""
            try:
                # Claude의 토큰 계산은 대략 1토큰 ≈ 3.5글자 정도
                return int(len(text) / 3.5)
            except Exception:
                return len(text) // 4  # 기본값
        
        async def generate_chat(
            self,
            messages: List[Dict[str, str]],
            model: str,
            **kwargs
        ) -> Result[str, str]:
            """채팅 형식으로 텍스트 생성 (추가 기능)"""
            try:
                default_params = {
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
                
                params = {**default_params, **kwargs}
                
                response = await self.client.messages.create(
                    model=model,
                    messages=messages,
                    **params
                )
                
                if response.content and len(response.content) > 0:
                    content_block = response.content[0]
                    if hasattr(content_block, 'text'):
                        return Success(content_block.text)
                    else:
                        return Failure("Anthropic API 응답 형식이 예상과 다릅니다")
                else:
                    return Failure("Anthropic API가 빈 응답을 반환했습니다")
                    
            except Exception as e:
                return Failure(f"Anthropic 채팅 API 호출 실패: {str(e)}")
        
        def get_provider_info(self) -> Dict[str, Any]:
            """Anthropic Provider 정보 반환"""
            return {
                "name": "AnthropicProvider",
                "version": self.version,
                "supported_models": self.supported_models,
                "capabilities": self.capabilities,
                "api_version": "2023-06-01",
                "pricing_info": {
                    "claude-3-opus-20240229": {"input": 0.000015, "output": 0.000075},
                    "claude-3-sonnet-20240229": {"input": 0.000003, "output": 0.000015},
                    "claude-3-haiku-20240307": {"input": 0.00000025, "output": 0.00000125},
                    "claude-3-5-sonnet-20241022": {"input": 0.000003, "output": 0.000015}
                }
            }

else:
    class AnthropicProvider(LLMProvider):
        """Anthropic이 설치되지 않은 경우의 더미 클래스"""
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Anthropic 라이브러리가 설치되지 않았습니다. "
                "'pip install anthropic' 명령으로 설치하세요."
            )
        
        async def generate(self, prompt: str, model: str, **kwargs) -> Result[str, str]:
            return Failure("Anthropic 라이브러리가 설치되지 않았습니다")
        
        async def embed(self, text: str, model: Optional[str] = None) -> Result[List[float], str]:
            return Failure("Anthropic 라이브러리가 설치되지 않았습니다")
        
        def get_token_count(self, text: str, model: str) -> int:
            return 0