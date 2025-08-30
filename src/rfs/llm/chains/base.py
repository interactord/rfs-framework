"""
LLM 체인 기본 클래스

모든 LLM 체인이 상속해야 하는 기본 추상 클래스입니다.
Result Pattern과 HOF 패턴을 완전히 지원합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Union
from rfs.core.result import Result, Success, Failure
from rfs.hof.core import pipe, compose
from rfs.async_pipeline.async_result import AsyncResult


class LLMChain(ABC):
    """LLM 체인 기본 클래스
    
    모든 LLM 체인 구현체가 상속해야 하는 추상 클래스입니다.
    체인 조합과 실행을 위한 기본 인터페이스를 제공합니다.
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.metadata = {}
    
    @abstractmethod
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """체인 실행
        
        Args:
            inputs: 입력 데이터
            context: 실행 컨텍스트
            
        Returns:
            Result[Dict[str, Any], str]: 실행 결과 또는 에러 메시지
        """
        pass
    
    def then(self, next_chain: 'LLMChain') -> 'SequentialChain':
        """체인 연결 (순차 실행)
        
        Args:
            next_chain: 다음에 실행할 체인
            
        Returns:
            SequentialChain: 순차 실행 체인
        """
        from .sequential import SequentialChain
        return SequentialChain([self, next_chain])
    
    def parallel(self, *chains: 'LLMChain') -> 'ParallelChain':
        """병렬 체인 실행
        
        Args:
            *chains: 병렬로 실행할 체인들
            
        Returns:
            ParallelChain: 병렬 실행 체인
        """
        from .parallel import ParallelChain
        return ParallelChain([self] + list(chains))
    
    def when(
        self, 
        condition: Callable[[Dict[str, Any]], bool],
        else_chain: Optional['LLMChain'] = None
    ) -> 'ConditionalChain':
        """조건부 체인 실행
        
        Args:
            condition: 조건 함수
            else_chain: 조건이 거짓일 때 실행할 체인
            
        Returns:
            ConditionalChain: 조건부 실행 체인
        """
        from .conditional import ConditionalChain
        return ConditionalChain(condition, self, else_chain)
    
    def with_retry(
        self,
        max_retries: int = 3,
        retry_condition: Optional[Callable[[Result], bool]] = None
    ) -> 'RetryChain':
        """재시도 기능이 있는 체인으로 래핑
        
        Args:
            max_retries: 최대 재시도 횟수
            retry_condition: 재시도 조건 함수
            
        Returns:
            RetryChain: 재시도 체인
        """
        from .retry import RetryChain
        return RetryChain(self, max_retries, retry_condition)
    
    def with_timeout(self, timeout_seconds: float) -> 'TimeoutChain':
        """타임아웃 기능이 있는 체인으로 래핑
        
        Args:
            timeout_seconds: 타임아웃 시간 (초)
            
        Returns:
            TimeoutChain: 타임아웃 체인
        """
        from .timeout import TimeoutChain
        return TimeoutChain(self, timeout_seconds)
    
    def set_metadata(self, **metadata) -> 'LLMChain':
        """체인 메타데이터 설정
        
        Args:
            **metadata: 설정할 메타데이터
            
        Returns:
            LLMChain: 자기 자신 (메소드 체이닝용)
        """
        self.metadata.update(metadata)
        return self
    
    def get_info(self) -> Dict[str, Any]:
        """체인 정보 반환
        
        Returns:
            Dict[str, Any]: 체인 메타데이터
        """
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "metadata": self.metadata
        }


class SimpleLLMChain(LLMChain):
    """간단한 LLM 체인 구현체
    
    단일 LLM 호출을 위한 기본 체인 구현체입니다.
    """
    
    def __init__(
        self,
        llm_manager: 'LLMManager',
        prompt_template: str,
        model: str,
        provider: Optional[str] = None,
        name: Optional[str] = None,
        **llm_kwargs
    ):
        super().__init__(name)
        self.llm_manager = llm_manager
        self.prompt_template = prompt_template
        self.model = model
        self.provider = provider
        self.llm_kwargs = llm_kwargs
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """간단한 LLM 체인 실행"""
        try:
            # 프롬프트 템플릿에 변수 대입
            prompt = self.prompt_template.format(**inputs)
            
            # LLM 호출
            result = await self.llm_manager.generate(
                prompt=prompt,
                model=self.model,
                provider=self.provider,
                **self.llm_kwargs
            )
            
            if result.is_failure():
                return result
            
            response = result.unwrap()
            
            # 결과 반환
            output = inputs.copy()  # 입력 값들을 복사
            output.update({
                "response": response,
                "prompt": prompt,
                "model": self.model,
                "provider": self.provider
            })
            
            return Success(output)
            
        except Exception as e:
            return Failure(f"SimpleLLMChain 실행 실패: {str(e)}")


class TemplatedLLMChain(LLMChain):
    """템플릿 기반 LLM 체인
    
    PromptTemplateManager를 사용하는 고급 체인 구현체입니다.
    """
    
    def __init__(
        self,
        llm_manager: 'LLMManager',
        template_manager: 'PromptTemplateManager',
        template_name: str,
        model: str,
        provider: Optional[str] = None,
        name: Optional[str] = None,
        **llm_kwargs
    ):
        super().__init__(name)
        self.llm_manager = llm_manager
        self.template_manager = template_manager
        self.template_name = template_name
        self.model = model
        self.provider = provider
        self.llm_kwargs = llm_kwargs
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """템플릿 기반 LLM 체인 실행"""
        try:
            # 템플릿 렌더링 및 LLM 생성
            result = await self.template_manager.render_and_generate(
                template_name=self.template_name,
                llm_manager=self.llm_manager,
                model=self.model,
                variables=inputs,
                provider=self.provider,
                **self.llm_kwargs
            )
            
            if result.is_failure():
                return result
            
            response = result.unwrap()
            
            # 결과 반환
            output = inputs.copy()
            output.update({
                "response": response,
                "template_name": self.template_name,
                "model": self.model,
                "provider": self.provider
            })
            
            return Success(output)
            
        except Exception as e:
            return Failure(f"TemplatedLLMChain 실행 실패: {str(e)}")


class RAGChain(LLMChain):
    """RAG 기반 LLM 체인
    
    RAG Engine을 사용하는 지식 기반 체인 구현체입니다.
    """
    
    def __init__(
        self,
        rag_engine: 'RAGEngine',
        model: str,
        template_name: str = "rag_basic",
        provider: Optional[str] = None,
        k: int = 5,
        name: Optional[str] = None,
        **rag_kwargs
    ):
        super().__init__(name)
        self.rag_engine = rag_engine
        self.model = model
        self.template_name = template_name
        self.provider = provider
        self.k = k
        self.rag_kwargs = rag_kwargs
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """RAG 체인 실행"""
        try:
            # 질문 추출 (question 또는 query 키에서)
            question = inputs.get("question") or inputs.get("query")
            if not question:
                return Failure("RAG 체인에는 'question' 또는 'query' 입력이 필요합니다")
            
            # RAG 질의응답
            result = await self.rag_engine.query(
                question=question,
                model=self.model,
                template_name=self.template_name,
                provider=self.provider,
                k=self.k,
                **self.rag_kwargs
            )
            
            if result.is_failure():
                return result
            
            rag_response = result.unwrap()
            
            # 결과 반환
            output = inputs.copy()
            output.update(rag_response)
            
            return Success(output)
            
        except Exception as e:
            return Failure(f"RAGChain 실행 실패: {str(e)}")


class TransformationChain(LLMChain):
    """데이터 변환 체인
    
    입력 데이터를 변환하는 체인입니다. LLM을 호출하지 않습니다.
    """
    
    def __init__(
        self,
        transform_function: Callable[[Dict[str, Any]], Dict[str, Any]],
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.transform_function = transform_function
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """데이터 변환 체인 실행"""
        try:
            transformed = self.transform_function(inputs)
            return Success(transformed)
        except Exception as e:
            return Failure(f"TransformationChain 실행 실패: {str(e)}")