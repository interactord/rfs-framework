"""
MonoResult - Mono와 Result 패턴 통합

Mono의 비동기 처리 능력과 Result의 타입 안전한 에러 처리를 결합한 클래스입니다.
복잡한 비동기 + Result 패턴을 우아하게 처리할 수 있도록 설계되었습니다.
"""

import asyncio
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

from ..core.result import Failure, Result, Success

T = TypeVar("T")  # 성공 값 타입
E = TypeVar("E")  # 에러 값 타입
U = TypeVar("U")  # 변환된 값 타입
F = TypeVar("F")  # 변환된 에러 타입


class MonoResult(Generic[T, E]):
    """
    Mono + Result 패턴 통합 클래스
    
    비동기 처리와 타입 안전한 에러 처리를 결합하여
    복잡한 비동기 Result 체이닝을 우아하게 처리합니다.
    
    주요 특징:
    - 타입 안전한 에러 처리
    - 우아한 비동기 체이닝
    - 성능 최적화된 설계
    - 기존 Mono/Result와 완벽 호환
    
    Example:
        >>> async def process_user(user_id: str) -> Result[ProcessedUser, str]:
        ...     return await (
        ...         MonoResult.from_async_result(lambda: fetch_user(user_id))
        ...         .bind_async_result(lambda user: validate_user_async(user))
        ...         .bind_result(lambda user: transform_user_data(user))
        ...         .map_error(lambda e: f"사용자 처리 실패: {e}")
        ...         .timeout(5.0)
        ...         .to_result()
        ...     )
    """

    def __init__(self, async_func: Callable[[], Awaitable[Result[T, E]]]):
        """
        MonoResult 생성자
        
        Args:
            async_func: Result[T, E]를 반환하는 비동기 함수
        """
        self._async_func = async_func

    # ==================== 생성 메서드 (Static Factory) ====================

    @staticmethod
    def from_result(result: Result[T, E]) -> "MonoResult[T, E]":
        """
        동기 Result를 MonoResult로 변환
        
        Args:
            result: 변환할 Result 인스턴스
            
        Returns:
            MonoResult: 동기 result를 감싼 MonoResult
            
        Example:
            >>> user_result = Success(User(id=1, name="김철수"))
            >>> mono = MonoResult.from_result(user_result)
            >>> final_result = await mono.to_result()
        """
        async def async_wrapper():
            return result
        return MonoResult(async_wrapper)

    @staticmethod
    def from_async_result(async_func: Callable[[], Awaitable[Result[T, E]]]) -> "MonoResult[T, E]":
        """
        비동기 Result 함수를 MonoResult로 변환
        
        Args:
            async_func: Result[T, E]를 반환하는 비동기 함수
            
        Returns:
            MonoResult: 비동기 함수를 감싼 MonoResult
            
        Example:
            >>> async def fetch_user(user_id: str) -> Result[User, str]:
            ...     return Success(user) if user_found else Failure("사용자 없음")
            >>> mono = MonoResult.from_async_result(lambda: fetch_user("123"))
        """
        return MonoResult(async_func)

    @staticmethod
    def from_value(value: T) -> "MonoResult[T, E]":
        """
        성공 값으로 MonoResult 생성
        
        Args:
            value: 성공 값
            
        Returns:
            MonoResult: Success를 감싼 MonoResult
            
        Example:
            >>> mono = MonoResult.from_value("test_data")
            >>> result = await mono.to_result()  # Success("test_data")
        """
        return MonoResult.from_result(Success(value))

    @staticmethod
    def from_error(error: E) -> "MonoResult[T, E]":
        """
        에러 값으로 MonoResult 생성
        
        Args:
            error: 에러 값
            
        Returns:
            MonoResult: Failure를 감싼 MonoResult
            
        Example:
            >>> mono = MonoResult.from_error("connection_failed")
            >>> result = await mono.to_result()  # Failure("connection_failed")
        """
        return MonoResult.from_result(Failure(error))

    # ==================== 변환 메서드 (Transformation) ====================

    def map(self, func: Callable[[T], U]) -> "MonoResult[U, E]":
        """
        성공 값 변환 (에러는 그대로 전파)
        
        Args:
            func: 값 변환 함수
            
        Returns:
            MonoResult: 변환된 값을 가진 MonoResult
            
        Example:
            >>> user_mono = MonoResult.from_value(User(name="김철수"))
            >>> name_mono = user_mono.map(lambda user: user.name)
            >>> result = await name_mono.to_result()  # Success("김철수")
        """
        async def mapped():
            result = await self._async_func()
            if result.is_success():
                try:
                    transformed_value = func(result.unwrap())
                    return Success(transformed_value)
                except Exception as e:
                    return Failure(e)  # 변환 중 예외 발생 시 Failure로 변환
            else:
                return result  # 에러는 그대로 전파
        
        return MonoResult(mapped)

    def map_error(self, func: Callable[[E], F]) -> "MonoResult[T, F]":
        """
        에러 타입 변환 (성공 값은 그대로 유지)
        
        Args:
            func: 에러 변환 함수
            
        Returns:
            MonoResult: 변환된 에러 타입을 가진 MonoResult
            
        Example:
            >>> error_mono = MonoResult.from_error("DB 연결 실패")
            >>> typed_error_mono = error_mono.map_error(lambda e: DatabaseError(e))
        """
        async def error_mapped():
            result = await self._async_func()
            if result.is_failure():
                try:
                    transformed_error = func(result.unwrap_error())
                    return Failure(transformed_error)
                except Exception as e:
                    return Failure(e)
            else:
                return result  # 성공은 그대로 유지
        
        return MonoResult(error_mapped)

    # ==================== 체이닝 메서드 (Chaining) ====================

    def bind_result(self, func: Callable[[T], Result[U, E]]) -> "MonoResult[U, E]":
        """
        동기 Result 함수와 체이닝
        
        Args:
            func: T를 받아 Result[U, E]를 반환하는 함수
            
        Returns:
            MonoResult: 체이닝된 MonoResult
            
        Example:
            >>> user_mono = MonoResult.from_async_result(fetch_user)
            >>> validated_mono = user_mono.bind_result(lambda user: validate_user(user))
        """
        async def bound():
            result = await self._async_func()
            if result.is_success():
                try:
                    return func(result.unwrap())
                except Exception as e:
                    return Failure(e)
            else:
                return result  # 에러는 그대로 전파
        
        return MonoResult(bound)

    def bind_async_result(self, func: Callable[[T], Awaitable[Result[U, E]]]) -> "MonoResult[U, E]":
        """
        비동기 Result 함수와 체이닝
        
        Args:
            func: T를 받아 Awaitable[Result[U, E]]를 반환하는 함수
            
        Returns:
            MonoResult: 체이닝된 MonoResult
            
        Example:
            >>> user_mono = MonoResult.from_async_result(fetch_user)  
            >>> processed_mono = user_mono.bind_async_result(lambda user: process_user_async(user))
        """
        async def async_bound():
            result = await self._async_func()
            if result.is_success():
                try:
                    return await func(result.unwrap())
                except Exception as e:
                    return Failure(e)
            else:
                return result  # 에러는 그대로 전파
        
        return MonoResult(async_bound)

    # ==================== 에러 처리 메서드 ====================

    def on_error_return_result(self, func: Callable[[E], Result[T, E]]) -> "MonoResult[T, E]":
        """
        에러 발생 시 대체 Result 반환
        
        Args:
            func: 에러를 받아 대체 Result를 반환하는 함수
            
        Returns:
            MonoResult: 에러 복구가 적용된 MonoResult
            
        Example:
            >>> mono = MonoResult.from_async_result(risky_operation)
            >>> safe_mono = mono.on_error_return_result(
            ...     lambda e: Success(default_value)  # 에러 시 기본값 반환
            ... )
        """
        async def with_error_recovery():
            result = await self._async_func()
            if result.is_failure():
                try:
                    return func(result.unwrap_error())
                except Exception as e:
                    return Failure(e)
            else:
                return result  # 성공은 그대로 유지
        
        return MonoResult(with_error_recovery)

    def on_error_return_value(self, value: T) -> "MonoResult[T, E]":
        """
        에러 발생 시 기본값 반환 (편의 메서드)
        
        Args:
            value: 에러 시 반환할 기본값
            
        Returns:
            MonoResult: 에러 복구가 적용된 MonoResult
        """
        return self.on_error_return_result(lambda _: Success(value))

    # ==================== 고급 기능 ====================

    def timeout(self, seconds: float) -> "MonoResult[T, E]":
        """
        타임아웃 설정
        
        Args:
            seconds: 타임아웃 시간(초)
            
        Returns:
            MonoResult: 타임아웃이 적용된 MonoResult
            
        Note:
            TimeoutError 발생 시 Failure로 래핑됩니다
            
        Example:
            >>> mono = MonoResult.from_async_result(slow_operation).timeout(5.0)
            >>> result = await mono.to_result()
        """
        async def with_timeout():
            try:
                return await asyncio.wait_for(self._async_func(), timeout=seconds)
            except asyncio.TimeoutError:
                return Failure(f"Operation timed out after {seconds} seconds")
            except Exception as e:
                return Failure(e)
        
        return MonoResult(with_timeout)

    def cache(self) -> "MonoResult[T, E]":
        """
        결과 캐싱 (한 번 계산된 결과를 재사용)
        
        Returns:
            MonoResult: 캐싱이 적용된 MonoResult
            
        Note:
            첫 번째 실행 후 결과가 캐시되어 이후 호출에서 재사용됩니다.
            
        Example:
            >>> expensive_mono = MonoResult.from_async_result(expensive_operation).cache()
            >>> result1 = await expensive_mono.to_result()  # 실제 실행
            >>> result2 = await expensive_mono.to_result()  # 캐시된 결과 반환
        """
        cached_result = None
        is_cached = False
        
        async def cached_execution():
            nonlocal cached_result, is_cached
            if not is_cached:
                cached_result = await self._async_func()
                is_cached = True
            return cached_result
        
        return MonoResult(cached_execution)

    def do_on_success(self, action: Callable[[T], None]) -> "MonoResult[T, E]":
        """
        성공 시 사이드 이펙트 실행 (디버깅/로깅용)
        
        Args:
            action: 성공 값에 대해 실행할 사이드 이펙트 함수
            
        Returns:
            MonoResult: 원본과 동일한 MonoResult (사이드 이펙트만 추가)
            
        Example:
            >>> mono = MonoResult.from_value("test").do_on_success(
            ...     lambda value: print(f"성공: {value}")
            ... )
        """
        async def with_success_side_effect():
            result = await self._async_func()
            if result.is_success():
                try:
                    action(result.unwrap())
                except Exception:
                    pass  # 사이드 이펙트 실패는 무시
            return result
        
        return MonoResult(with_success_side_effect)

    def do_on_error(self, action: Callable[[E], None]) -> "MonoResult[T, E]":
        """
        에러 시 사이드 이펙트 실행 (디버깅/로깅용)
        
        Args:
            action: 에러에 대해 실행할 사이드 이펙트 함수
            
        Returns:
            MonoResult: 원본과 동일한 MonoResult (사이드 이펙트만 추가)
            
        Example:
            >>> mono = MonoResult.from_error("fail").do_on_error(
            ...     lambda error: print(f"에러 발생: {error}")
            ... )
        """
        async def with_error_side_effect():
            result = await self._async_func()
            if result.is_failure():
                try:
                    action(result.unwrap_error())
                except Exception:
                    pass  # 사이드 이펙트 실패는 무시
            return result
        
        return MonoResult(with_error_side_effect)

    # ==================== 최종 변환 ====================

    async def to_result(self) -> Result[T, E]:
        """
        MonoResult를 최종 Result로 변환
        
        Returns:
            Result[T, E]: 최종 실행 결과
            
        Example:
            >>> mono = MonoResult.from_async_result(fetch_user).map(lambda u: u.name)
            >>> result = await mono.to_result()
            >>> if result.is_success():
            ...     print(f"사용자 이름: {result.unwrap()}")
        """
        return await self._async_func()

    # ==================== 편의 메서드 ====================

    def __await__(self):
        """
        await 직접 지원 (to_result()와 동일)
        
        Example:
            >>> result = await MonoResult.from_value("test")
            >>> # 위는 다음과 동일: await MonoResult.from_value("test").to_result()
        """
        return self.to_result().__await__()

    def __repr__(self) -> str:
        """디버깅을 위한 문자열 표현"""
        return f"MonoResult({self.__class__.__name__})"