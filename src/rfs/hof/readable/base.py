"""
RFS Readable HOF Base Classes

플루언트 인터페이스의 기본 클래스들을 제공합니다.
모든 readable HOF 클래스들이 상속받아 사용하는 기본 기능들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, Optional, TypeVar, Union
from rfs.core.result import Result, Success, Failure

from .types import T, U, ErrorInfo

class FluentBase(Generic[T], ABC):
    """
    모든 플루언트 인터페이스의 기본 클래스
    
    이 클래스는 값을 보유하고 체이닝 가능한 메서드들을 제공합니다.
    모든 readable HOF 클래스들의 기본이 되는 클래스입니다.
    """
    
    def __init__(self, value: T):
        """
        플루언트 객체를 초기화합니다.
        
        Args:
            value: 보관할 값
        """
        self._value = value
    
    @property
    def value(self) -> T:
        """내부 값에 접근"""
        return self._value
    
    def map(self, func: Callable[[T], U]) -> 'FluentBase[U]':
        """
        값을 변환하여 새로운 플루언트 객체를 반환합니다.
        
        Args:
            func: 변환 함수
            
        Returns:
            변환된 값을 가진 새로운 플루언트 객체
        """
        try:
            transformed = func(self._value)
            # 같은 클래스의 새 인스턴스를 생성하여 반환
            return self.__class__(transformed)
        except Exception as e:
            # 에러가 발생하면 에러 정보를 담은 객체 반환
            error_info = ErrorInfo(f"변환 실패: {str(e)}", "transformation_error", e)
            return self.__class__(error_info)
    
    def tap(self, func: Callable[[T], None]) -> 'FluentBase[T]':
        """
        값을 변경하지 않고 부수 효과만 수행합니다 (디버깅, 로깅 등에 유용).
        
        Args:
            func: 부수 효과를 수행할 함수
            
        Returns:
            자기 자신 (체이닝을 위해)
        """
        try:
            func(self._value)
        except Exception:
            # tap에서는 에러를 무시하고 계속 진행
            pass
        return self
    
    def to_result(self) -> Result[T, str]:
        """
        Result 타입으로 변환합니다.
        
        Returns:
            Success 또는 Failure Result
        """
        try:
            # ErrorInfo인 경우 Failure로 변환
            if isinstance(self._value, ErrorInfo):
                return Failure(self._value.message)
            return Success(self._value)
        except Exception as e:
            return Failure(f"Result 변환 실패: {str(e)}")
    
    def if_present(self, func: Callable[[T], None]) -> 'FluentBase[T]':
        """
        값이 존재하는 경우에만 함수를 실행합니다.
        
        Args:
            func: 값이 존재할 때 실행할 함수
            
        Returns:
            자기 자신
        """
        if self._value is not None and not isinstance(self._value, ErrorInfo):
            try:
                func(self._value)
            except Exception:
                # 에러 발생 시 무시하고 계속 진행
                pass
        return self
    
    def or_else(self, default_value: T) -> 'FluentBase[T]':
        """
        값이 없거나 에러인 경우 기본값을 사용합니다.
        
        Args:
            default_value: 사용할 기본값
            
        Returns:
            값 또는 기본값을 가진 새로운 플루언트 객체
        """
        if self._value is None or isinstance(self._value, ErrorInfo):
            return self.__class__(default_value)
        return self
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self._value})"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._value!r})"

class ChainableResult(Generic[T]):
    """
    Result와 체이닝을 결합한 클래스
    
    Result 패턴과 플루언트 인터페이스를 결합하여
    에러가 안전하게 전파되는 체이닝을 제공합니다.
    """
    
    def __init__(self, result: Result[T, str]):
        """
        ChainableResult를 초기화합니다.
        
        Args:
            result: 래핑할 Result 객체
        """
        self._result = result
    
    @property
    def result(self) -> Result[T, str]:
        """내부 Result 객체에 접근"""
        return self._result
    
    def bind(self, func: Callable[[T], Result[U, str]]) -> 'ChainableResult[U]':
        """
        모나드 bind 연산을 수행합니다.
        성공한 경우에만 함수를 적용하고, 실패는 전파됩니다.
        
        Args:
            func: 적용할 함수 (T -> Result[U, str])
            
        Returns:
            새로운 ChainableResult
        """
        if self._result.is_success():
            try:
                new_result = func(self._result.unwrap())
                return ChainableResult(new_result)
            except Exception as e:
                return ChainableResult(Failure(f"bind 연산 실패: {str(e)}"))
        else:
            return ChainableResult(Failure(self._result.unwrap_error()))
    
    def map(self, func: Callable[[T], U]) -> 'ChainableResult[U]':
        """
        함수를 매핑합니다.
        성공한 경우에만 함수를 적용하고, 실패는 전파됩니다.
        
        Args:
            func: 적용할 함수 (T -> U)
            
        Returns:
            새로운 ChainableResult
        """
        if self._result.is_success():
            try:
                transformed = func(self._result.unwrap())
                return ChainableResult(Success(transformed))
            except Exception as e:
                return ChainableResult(Failure(f"map 연산 실패: {str(e)}"))
        else:
            return ChainableResult(Failure(self._result.unwrap_error()))
    
    def filter(self, predicate: Callable[[T], bool], error_msg: str = "필터 조건을 만족하지 않음") -> 'ChainableResult[T]':
        """
        조건을 만족하는 경우에만 값을 유지합니다.
        
        Args:
            predicate: 필터링 조건
            error_msg: 조건을 만족하지 않을 때 사용할 에러 메시지
            
        Returns:
            필터링된 ChainableResult
        """
        if self._result.is_success():
            try:
                value = self._result.unwrap()
                if predicate(value):
                    return self
                else:
                    return ChainableResult(Failure(error_msg))
            except Exception as e:
                return ChainableResult(Failure(f"필터 조건 확인 실패: {str(e)}"))
        else:
            return self
    
    def tap(self, func: Callable[[T], None]) -> 'ChainableResult[T]':
        """
        성공한 경우에만 부수 효과를 수행합니다.
        
        Args:
            func: 부수 효과를 수행할 함수
            
        Returns:
            자기 자신
        """
        if self._result.is_success():
            try:
                func(self._result.unwrap())
            except Exception:
                # tap에서는 에러를 무시하고 계속 진행
                pass
        return self
    
    def unwrap_or_default(self, default: T) -> T:
        """
        성공 시 값을 반환하고, 실패 시 기본값을 반환합니다.
        
        Args:
            default: 실패 시 사용할 기본값
            
        Returns:
            성공한 경우 값, 실패한 경우 기본값
        """
        return self._result.unwrap() if self._result.is_success() else default
    
    def unwrap_or_else(self, func: Callable[[str], T]) -> T:
        """
        성공 시 값을 반환하고, 실패 시 에러 메시지로부터 값을 생성합니다.
        
        Args:
            func: 에러 메시지로부터 값을 생성하는 함수
            
        Returns:
            성공한 경우 값, 실패한 경우 함수 결과
        """
        if self._result.is_success():
            return self._result.unwrap()
        else:
            try:
                return func(self._result.unwrap_error())
            except Exception:
                raise ValueError(f"기본값 생성 실패: {self._result.unwrap_error()}")
    
    def is_success(self) -> bool:
        """성공 여부를 확인합니다."""
        return self._result.is_success()
    
    def is_failure(self) -> bool:
        """실패 여부를 확인합니다."""
        return self._result.is_failure()
    
    def __str__(self) -> str:
        return f"ChainableResult({self._result})"
    
    def __repr__(self) -> str:
        return f"ChainableResult({self._result!r})"

# 편의 함수들
def success(value: T) -> ChainableResult[T]:
    """성공 ChainableResult를 생성합니다."""
    return ChainableResult(Success(value))

def failure(error: str) -> ChainableResult[Any]:
    """실패 ChainableResult를 생성합니다."""
    return ChainableResult(Failure(error))

def from_result(result: Result[T, str]) -> ChainableResult[T]:
    """Result로부터 ChainableResult를 생성합니다."""
    return ChainableResult(result)