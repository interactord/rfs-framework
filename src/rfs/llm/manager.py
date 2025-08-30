"""
LLM Manager

LLM 작업을 관리하는 중앙 매니저입니다.
여러 Provider를 관리하고, Result Pattern과 HOF를 완전히 지원합니다.
"""

from typing import Dict, Optional, Any, List
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from rfs.hof.core import pipe, curry
from .providers.base import LLMProvider
from .config import get_llm_settings, LLMProviderType


@Service("llm_manager")
class LLMManager:
    """LLM 작업을 관리하는 중앙 매니저
    
    여러 LLM Provider를 등록하고 관리하며,
    Result Pattern과 HOF 패턴을 완전히 지원합니다.
    """
    
    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._default_provider: Optional[str] = None
        self._settings = get_llm_settings()
        
        # 설정에서 기본 Provider 설정
        if hasattr(self._settings, 'default_provider'):
            self._configured_default_provider = self._settings.default_provider.value
        else:
            self._configured_default_provider = "openai"
    
    def register_provider(
        self, 
        name: str, 
        provider: LLMProvider
    ) -> Result[None, str]:
        """Provider 등록
        
        Args:
            name: Provider 이름
            provider: LLMProvider 인스턴스
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        if name in self._providers:
            return Failure(f"Provider '{name}'가 이미 등록되어 있습니다")
        
        try:
            self._providers[name] = provider
            
            # 첫 번째 Provider를 기본값으로 설정
            if self._default_provider is None:
                self._default_provider = name
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"Provider 등록 실패: {str(e)}")
    
    def unregister_provider(self, name: str) -> Result[None, str]:
        """Provider 등록 해제
        
        Args:
            name: 해제할 Provider 이름
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        if name not in self._providers:
            return Failure(f"Provider '{name}'를 찾을 수 없습니다")
        
        try:
            del self._providers[name]
            
            # 기본 Provider가 삭제된 경우 다른 Provider로 변경
            if self._default_provider == name:
                if self._providers:
                    self._default_provider = next(iter(self._providers.keys()))
                else:
                    self._default_provider = None
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"Provider 등록 해제 실패: {str(e)}")
    
    def set_default_provider(self, name: str) -> Result[None, str]:
        """기본 Provider 설정
        
        Args:
            name: 기본으로 설정할 Provider 이름
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        if name not in self._providers:
            return Failure(f"Provider '{name}'를 찾을 수 없습니다")
        
        self._default_provider = name
        return Success(None)
    
    def get_provider(self, name: str) -> Result[LLMProvider, str]:
        """Provider 조회
        
        Args:
            name: 조회할 Provider 이름
            
        Returns:
            Result[LLMProvider, str]: 성공시 Provider, 실패시 에러 메시지
        """
        if name not in self._providers:
            return Failure(f"Provider '{name}'를 찾을 수 없습니다")
        
        return Success(self._providers[name])
    
    def list_providers(self) -> List[str]:
        """등록된 모든 Provider 목록 반환
        
        Returns:
            List[str]: Provider 이름 목록
        """
        return list(self._providers.keys())
    
    def get_default_provider_name(self) -> Optional[str]:
        """기본 Provider 이름 반환
        
        Returns:
            Optional[str]: 기본 Provider 이름 또는 None
        """
        return self._default_provider
    
    @curry
    async def generate_with_provider(
        self, 
        provider_name: str, 
        prompt: str, 
        model: str,
        **kwargs
    ) -> Result[str, str]:
        """특정 Provider로 텍스트 생성 (HOF 패턴)
        
        Args:
            provider_name: 사용할 Provider 이름
            prompt: 프롬프트
            model: 모델명
            **kwargs: 추가 파라미터
            
        Returns:
            Result[str, str]: 생성된 텍스트 또는 에러 메시지
        """
        provider_result = self.get_provider(provider_name)
        if provider_result.is_failure():
            return provider_result
        
        provider = provider_result.unwrap()
        return await provider.generate(prompt, model, **kwargs)
    
    async def generate(
        self, 
        prompt: str, 
        model: str,
        provider: Optional[str] = None,
        **kwargs
    ) -> Result[str, str]:
        """텍스트 생성 (기본 또는 지정된 Provider 사용)
        
        Args:
            prompt: 프롬프트
            model: 모델명
            provider: 사용할 Provider 이름 (None이면 기본 Provider)
            **kwargs: 추가 파라미터
            
        Returns:
            Result[str, str]: 생성된 텍스트 또는 에러 메시지
        """
        provider_name = provider or self._default_provider
        if not provider_name:
            return Failure("등록된 Provider가 없습니다")
        
        return await self.generate_with_provider(provider_name, prompt, model, **kwargs)
    
    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Result[List[float], str]:
        """텍스트 임베딩
        
        Args:
            text: 임베딩할 텍스트
            model: 임베딩 모델명
            provider: 사용할 Provider 이름
            
        Returns:
            Result[List[float], str]: 임베딩 벡터 또는 에러 메시지
        """
        provider_name = provider or self._default_provider
        if not provider_name:
            return Failure("등록된 Provider가 없습니다")
        
        provider_result = self.get_provider(provider_name)
        if provider_result.is_failure():
            return provider_result
        
        provider_instance = provider_result.unwrap()
        return await provider_instance.embed(text, model)
    
    def get_token_count(
        self,
        text: str,
        model: str,
        provider: Optional[str] = None
    ) -> Result[int, str]:
        """토큰 수 계산
        
        Args:
            text: 계산할 텍스트
            model: 모델명
            provider: 사용할 Provider 이름
            
        Returns:
            Result[int, str]: 토큰 수 또는 에러 메시지
        """
        provider_name = provider or self._default_provider
        if not provider_name:
            return Failure("등록된 Provider가 없습니다")
        
        provider_result = self.get_provider(provider_name)
        if provider_result.is_failure():
            return provider_result
        
        try:
            provider_instance = provider_result.unwrap()
            token_count = provider_instance.get_token_count(text, model)
            return Success(token_count)
        except Exception as e:
            return Failure(f"토큰 수 계산 실패: {str(e)}")
    
    def get_all_provider_info(self) -> Dict[str, Any]:
        """모든 Provider 정보 반환
        
        Returns:
            Dict[str, Any]: 모든 Provider의 정보
        """
        info = {}
        for name, provider in self._providers.items():
            info[name] = provider.get_provider_info()
        
        return {
            "providers": info,
            "default_provider": self._default_provider,
            "total_providers": len(self._providers)
        }
    
    # HOF 기반 파이프라인 생성 함수들
    def create_generation_pipeline(
        self,
        provider_name: str,
        model: str,
        **default_kwargs
    ):
        """텍스트 생성 파이프라인 생성 (HOF 패턴)
        
        Args:
            provider_name: Provider 이름
            model: 모델명
            **default_kwargs: 기본 파라미터
            
        Returns:
            Callable: 프롬프트를 받아 결과를 반환하는 함수
        """
        return pipe(
            lambda prompt: self.generate_with_provider(
                provider_name, prompt, model, **default_kwargs
            )
        )
    
    def create_multi_provider_pipeline(
        self,
        providers: List[str],
        model: str,
        **kwargs
    ):
        """여러 Provider를 사용한 파이프라인 생성
        
        Args:
            providers: 사용할 Provider 이름 목록
            model: 모델명
            **kwargs: 파라미터
            
        Returns:
            Callable: 프롬프트를 받아 여러 결과를 반환하는 함수
        """
        async def multi_generate(prompt: str) -> Result[Dict[str, str], str]:
            results = {}
            
            for provider_name in providers:
                result = await self.generate_with_provider(
                    provider_name, prompt, model, **kwargs
                )
                
                if result.is_success():
                    results[provider_name] = result.unwrap()
                else:
                    results[provider_name] = f"Error: {result.unwrap_error()}"
            
            return Success(results)
        
        return multi_generate
    
    def auto_configure_from_settings(self) -> Result[None, str]:
        """설정에서 Provider 자동 구성
        
        환경 설정을 기반으로 사용 가능한 Provider들을 자동으로 등록합니다.
        
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        try:
            # OpenAI Provider
            if hasattr(self._settings, 'openai') and self._settings.openai.api_key:
                from .providers.openai import OpenAIProvider
                openai_provider = OpenAIProvider(
                    api_key=self._settings.openai.api_key,
                    organization=getattr(self._settings.openai, 'organization', None),
                    base_url=getattr(self._settings.openai, 'base_url', None)
                )
                self.register_provider("openai", openai_provider)
            
            # Anthropic Provider  
            if hasattr(self._settings, 'anthropic') and self._settings.anthropic.api_key:
                from .providers.anthropic import AnthropicProvider
                anthropic_provider = AnthropicProvider(
                    api_key=self._settings.anthropic.api_key,
                    base_url=getattr(self._settings.anthropic, 'base_url', None)
                )
                self.register_provider("anthropic", anthropic_provider)
            
            # Gemini Provider
            if hasattr(self._settings, 'gemini'):
                try:
                    from .providers.gemini import GeminiProvider
                    if self._settings.gemini.api_key or self._settings.gemini.project:
                        gemini_provider = GeminiProvider(
                            api_key=self._settings.gemini.api_key,
                            project=self._settings.gemini.project,
                            location=self._settings.gemini.location,
                            use_vertex=self._settings.gemini.use_vertex
                        )
                        self.register_provider("gemini", gemini_provider)
                except ImportError:
                    pass  # Gemini SDK가 없으면 스킵
            
            # Bedrock Provider
            if hasattr(self._settings, 'bedrock'):
                try:
                    from .providers.bedrock import BedrockProvider
                    if (self._settings.bedrock.api_key or 
                        (self._settings.bedrock.aws_access_key and self._settings.bedrock.aws_secret_key)):
                        bedrock_provider = BedrockProvider(
                            api_key=self._settings.bedrock.api_key,
                            region=self._settings.bedrock.region,
                            aws_access_key=self._settings.bedrock.aws_access_key,
                            aws_secret_key=self._settings.bedrock.aws_secret_key
                        )
                        self.register_provider("bedrock", bedrock_provider)
                except ImportError:
                    pass  # Bedrock SDK가 없으면 스킵
            
            # 설정된 기본 Provider 적용
            if self._configured_default_provider in self._providers:
                self._default_provider = self._configured_default_provider
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"Provider 자동 구성 실패: {str(e)}")
    
    def get_settings_info(self) -> Dict[str, Any]:
        """현재 설정 정보 반환
        
        Returns:
            Dict[str, Any]: 설정 정보
        """
        if hasattr(self._settings, 'dict'):
            return self._settings.dict()
        else:
            return dict(self._settings)
    
    def get_configured_providers(self) -> List[str]:
        """설정에서 활성화된 Provider 목록 반환
        
        Returns:
            List[str]: 활성화된 Provider 목록
        """
        if hasattr(self._settings, 'enabled_providers'):
            return [p.value for p in self._settings.enabled_providers]
        else:
            return ["openai"]


def create_llm_manager_from_config() -> Result[LLMManager, str]:
    """설정에서 LLMManager 생성
    
    환경 설정을 기반으로 LLMManager 인스턴스를 생성하고 
    사용 가능한 Provider들을 자동으로 등록합니다.
    
    Returns:
        Result[LLMManager, str]: 설정된 LLMManager 또는 에러 메시지
    """
    try:
        manager = LLMManager()
        configure_result = manager.auto_configure_from_settings()
        
        if configure_result.is_failure():
            return configure_result
        
        if not manager.list_providers():
            return Failure("설정에서 사용 가능한 Provider를 찾을 수 없습니다")
        
        return Success(manager)
        
    except Exception as e:
        return Failure(f"LLMManager 생성 실패: {str(e)}")