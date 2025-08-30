"""
LLM Provider 기본 인터페이스

모든 LLM Provider가 구현해야 하는 기본 인터페이스를 정의합니다.
Result Pattern과 HOF 패턴을 완전히 지원합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from rfs.core.result import Result
from rfs.hof.core import curry


class LLMProvider(ABC):
    """LLM Provider 기본 인터페이스
    
    모든 LLM 제공업체 구현체가 상속해야 하는 추상 클래스입니다.
    Result Pattern을 통한 안전한 에러 처리를 보장합니다.
    """
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        model: str,
        **kwargs
    ) -> Result[str, str]:
        """텍스트 생성
        
        Args:
            prompt: 생성할 텍스트에 대한 프롬프트
            model: 사용할 모델명
            **kwargs: 추가 파라미터 (temperature, max_tokens 등)
            
        Returns:
            Result[str, str]: 성공시 생성된 텍스트, 실패시 에러 메시지
        """
        pass
    
    @abstractmethod
    async def embed(
        self, 
        text: str, 
        model: Optional[str] = None
    ) -> Result[List[float], str]:
        """텍스트 임베딩
        
        Args:
            text: 임베딩할 텍스트
            model: 임베딩 모델명 (옵션)
            
        Returns:
            Result[List[float], str]: 성공시 임베딩 벡터, 실패시 에러 메시지
        """
        pass
    
    @abstractmethod
    def get_token_count(self, text: str, model: str) -> int:
        """토큰 수 계산
        
        Args:
            text: 토큰 수를 계산할 텍스트
            model: 모델명 (토큰 계산 방식이 모델에 따라 다를 수 있음)
            
        Returns:
            int: 토큰 수
        """
        pass
    
    @curry
    async def generate_with_config(
        self,
        config: Dict[str, Any],
        prompt: str,
        model: str,
        **kwargs
    ) -> Result[str, str]:
        """설정과 함께 텍스트 생성 (HOF 패턴)
        
        Args:
            config: 생성 설정
            prompt: 프롬프트
            model: 모델명
            **kwargs: 추가 파라미터
            
        Returns:
            Result[str, str]: 생성 결과
        """
        # 설정을 kwargs에 병합
        merged_kwargs = {**config, **kwargs}
        return await self.generate(prompt, model, **merged_kwargs)
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Provider 정보 반환
        
        Returns:
            Dict[str, Any]: Provider 메타데이터
        """
        return {
            "name": self.__class__.__name__,
            "version": getattr(self, "version", "unknown"),
            "supported_models": getattr(self, "supported_models", []),
            "capabilities": getattr(self, "capabilities", [])
        }