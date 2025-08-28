"""
AsyncResult 모나드 - 비동기 전용 Result 타입

비동기 함수형 프로그래밍을 위한 우아한 Result 모나드 구현.
기존 Result 패턴과 완전 호환되며 비동기 연산에 최적화되어 있습니다.
"""

import asyncio
from typing import Awaitable, Callable, Generic, TypeVar, Union

from ..core.result import Result, Success, Failure

T = TypeVar('T')
U = TypeVar('U')
E = TypeVar('E')


class AsyncResult(Generic[T, E]):
    """
    비동기 전용 Result 모나드
    
    특징:
    - 모든 연산이 비동기로 처리됨
    - 자동 에러 핸들링 및 타입 안전성 보장
    - 기존 Result 패턴과 완전 호환
    - 체이닝 최적화 및 컨텍스트 보존
    """
    
    def __init__(self, coro: Awaitable[Result[T, E]]):
        """
        AsyncResult 생성자
        
        Args:
            coro: Result를 반환하는 코루틴
        """
        self._coro = coro
        self._cached_result: Result[T, E] | None = None
    
    @classmethod
    def from_async(cls, async_func: Callable[[], Awaitable[T]]) -> 'AsyncResult[T, Exception]':
        """
        비동기 함수로부터 AsyncResult 생성
        
        Args:
            async_func: 비동기 함수
            
        Returns:
            AsyncResult[T, Exception]: 새로운 AsyncResult 인스턴스
            
        Example:
            >>> async def fetch_data():
            ...     return "data"
            >>> result = AsyncResult.from_async(fetch_data)
            >>> data = await result.unwrap_async()
            'data'
        """
        async def wrapper():
            try:
                result = await async_func()
                return Success(result)
            except Exception as e:
                return Failure(e)
        
        return cls(wrapper())
    
    @classmethod
    def from_value(cls, value: T) -> 'AsyncResult[T, E]':
        """
        값으로부터 AsyncResult 생성 (즉시 성공)
        
        Args:
            value: 성공 값
            
        Returns:
            AsyncResult[T, E]: 성공 상태의 AsyncResult
        """
        async def wrapper():
            return Success(value)
        
        return cls(wrapper())
    
    @classmethod
    def from_error(cls, error: E) -> 'AsyncResult[T, E]':
        """
        에러로부터 AsyncResult 생성 (즉시 실패)
        
        Args:
            error: 에러 값
            
        Returns:
            AsyncResult[T, E]: 실패 상태의 AsyncResult
        """
        async def wrapper():
            return Failure(error)
        
        return cls(wrapper())
    
    @classmethod
    def from_result(cls, result: Result[T, E]) -> 'AsyncResult[T, E]':
        """
        기존 Result로부터 AsyncResult 생성
        
        Args:
            result: 기존 Result 인스턴스
            
        Returns:
            AsyncResult[T, E]: Result를 래핑한 AsyncResult
        """
        async def wrapper():
            return result
        
        return cls(wrapper())
    
    async def _get_result(self) -> Result[T, E]:
        """
        내부 Result를 캐싱하여 반환
        
        Returns:
            Result[T, E]: 실행된 결과
        """
        if self._cached_result is None:
            self._cached_result = await self._coro
        return self._cached_result
    
    async def is_success(self) -> bool:
        """
        성공 여부 확인 (비동기)
        
        Returns:
            bool: 성공 여부
        """
        result = await self._get_result()
        return result.is_success()
    
    async def is_failure(self) -> bool:
        """
        실패 여부 확인 (비동기)
        
        Returns:
            bool: 실패 여부
        """
        result = await self._get_result()
        return result.is_failure()
    
    async def unwrap_async(self) -> T:
        """
        값 추출 (실패 시 예외 발생)
        
        Returns:
            T: 성공 값
            
        Raises:
            Exception: 실패 시 원본 에러
        """
        result = await self._get_result()
        return result.unwrap()
    
    async def unwrap_or_async(self, default: T) -> T:
        """
        값 추출 (실패 시 기본값 반환)
        
        Args:
            default: 실패 시 반환할 기본값
            
        Returns:
            T: 성공 값 또는 기본값
        """
        result = await self._get_result()
        return result.unwrap_or(default)
    
    async def unwrap_or_else_async(self, default_func: Callable[[E], Awaitable[T]]) -> T:
        """
        값 추출 (실패 시 비동기 함수로 기본값 생성)
        
        Args:
            default_func: 에러를 받아 기본값을 생성하는 비동기 함수
            
        Returns:
            T: 성공 값 또는 생성된 기본값
        """
        result = await self._get_result()
        if result.is_success():
            return result.unwrap()
        else:
            return await default_func(result.unwrap_error())
    
    def bind_async(self, func: Callable[[T], 'AsyncResult[U, E]']) -> 'AsyncResult[U, E]':
        """
        비동기 함수와 모나딕 바인딩 (flatMap)
        
        Args:
            func: T를 받아서 AsyncResult[U, E]를 반환하는 함수
            
        Returns:
            AsyncResult[U, E]: 바인딩된 결과
            
        Example:
            >>> async def validate_user(data):
            ...     return AsyncResult.from_value(data) if data else AsyncResult.from_error("Invalid")
            >>> result = AsyncResult.from_value("user_data")
            >>> validated = result.bind_async(validate_user)
        """
        async def bound():
            result = await self._get_result()
            if result.is_success():
                try:
                    next_result = func(result.unwrap())
                    return await next_result._get_result()
                except Exception as e:
                    return Failure(e)
            else:
                return Failure(result.unwrap_error())
        
        return AsyncResult(bound())
    
    def map_async(self, func: Callable[[T], Awaitable[U]]) -> 'AsyncResult[U, E]':
        """
        비동기 함수로 값 변환
        
        Args:
            func: T를 받아서 Awaitable[U]를 반환하는 함수
            
        Returns:
            AsyncResult[U, E]: 변환된 결과
            
        Example:
            >>> async def process_data(data):
            ...     return data.upper()
            >>> result = AsyncResult.from_value("hello")
            >>> processed = result.map_async(process_data)
            >>> await processed.unwrap_async()  # "HELLO"
        """
        async def mapped():
            result = await self._get_result()
            if result.is_success():
                try:
                    new_value = await func(result.unwrap())
                    return Success(new_value)
                except Exception as e:
                    return Failure(e)
            else:
                return Failure(result.unwrap_error())
        
        return AsyncResult(mapped())
    
    def map_sync(self, func: Callable[[T], U]) -> 'AsyncResult[U, E]':
        """
        동기 함수로 값 변환
        
        Args:
            func: T를 받아서 U를 반환하는 함수
            
        Returns:
            AsyncResult[U, E]: 변환된 결과
        """
        async def mapped():
            result = await self._get_result()
            if result.is_success():
                try:
                    new_value = func(result.unwrap())
                    return Success(new_value)
                except Exception as e:
                    return Failure(e)
            else:
                return Failure(result.unwrap_error())
        
        return AsyncResult(mapped())
    
    def map_error(self, func: Callable[[E], U]) -> 'AsyncResult[T, U]':
        """
        에러 값 변환
        
        Args:
            func: E를 받아서 U를 반환하는 함수
            
        Returns:
            AsyncResult[T, U]: 에러가 변환된 결과
        """
        async def error_mapped():
            result = await self._get_result()
            if result.is_success():
                return Success(result.unwrap())
            else:
                try:
                    new_error = func(result.unwrap_error())
                    return Failure(new_error)
                except Exception as e:
                    return Failure(e)
        
        return AsyncResult(error_mapped())
    
    def recover_async(self, recovery_func: Callable[[E], Awaitable[T]]) -> 'AsyncResult[T, E]':
        """
        실패 시 비동기 복구 함수 실행
        
        Args:
            recovery_func: 에러를 받아서 복구 값을 생성하는 비동기 함수
            
        Returns:
            AsyncResult[T, E]: 복구된 결과
        """
        async def recovered():
            result = await self._get_result()
            if result.is_success():
                return result
            else:
                try:
                    recovered_value = await recovery_func(result.unwrap_error())
                    return Success(recovered_value)
                except Exception as e:
                    return Failure(e)
        
        return AsyncResult(recovered())
    
    def recover_with_async(self, recovery_func: Callable[[E], 'AsyncResult[T, E]']) -> 'AsyncResult[T, E]':
        """
        실패 시 다른 AsyncResult로 복구
        
        Args:
            recovery_func: 에러를 받아서 새로운 AsyncResult를 반환하는 함수
            
        Returns:
            AsyncResult[T, E]: 복구된 결과
        """
        async def recovered():
            result = await self._get_result()
            if result.is_success():
                return result
            else:
                try:
                    recovery_result = recovery_func(result.unwrap_error())
                    return await recovery_result._get_result()
                except Exception as e:
                    return Failure(e)
        
        return AsyncResult(recovered())
    
    def filter_async(self, predicate: Callable[[T], Awaitable[bool]], error: E) -> 'AsyncResult[T, E]':
        """
        비동기 조건으로 필터링
        
        Args:
            predicate: T를 받아서 bool을 반환하는 비동기 조건 함수
            error: 조건을 만족하지 않을 때 사용할 에러
            
        Returns:
            AsyncResult[T, E]: 필터링된 결과
        """
        async def filtered():
            result = await self._get_result()
            if result.is_success():
                try:
                    value = result.unwrap()
                    if await predicate(value):
                        return Success(value)
                    else:
                        return Failure(error)
                except Exception as e:
                    return Failure(e)
            else:
                return result
        
        return AsyncResult(filtered())
    
    def filter_sync(self, predicate: Callable[[T], bool], error: E) -> 'AsyncResult[T, E]':
        """
        동기 조건으로 필터링
        
        Args:
            predicate: T를 받아서 bool을 반환하는 조건 함수
            error: 조건을 만족하지 않을 때 사용할 에러
            
        Returns:
            AsyncResult[T, E]: 필터링된 결과
        """
        async def filtered():
            result = await self._get_result()
            if result.is_success():
                try:
                    value = result.unwrap()
                    if predicate(value):
                        return Success(value)
                    else:
                        return Failure(error)
                except Exception as e:
                    return Failure(e)
            else:
                return result
        
        return AsyncResult(filtered())
    
    async def to_result(self) -> Result[T, E]:
        """
        일반 Result로 변환
        
        Returns:
            Result[T, E]: 동기 Result 객체
        """
        return await self._get_result()
    
    def to_awaitable(self) -> Awaitable[T]:
        """
        Awaitable로 변환 (성공 값만 반환, 실패 시 예외)
        
        Returns:
            Awaitable[T]: 성공 값을 반환하는 Awaitable
        """
        return self.unwrap_async()
    
    def zip_with(self, other: 'AsyncResult[U, E]') -> 'AsyncResult[tuple[T, U], E]':
        """
        다른 AsyncResult와 결합
        
        Args:
            other: 결합할 다른 AsyncResult
            
        Returns:
            AsyncResult[tuple[T, U], E]: 결합된 결과
        """
        async def zipped():
            result1 = await self._get_result()
            result2 = await other._get_result()
            
            if result1.is_success() and result2.is_success():
                return Success((result1.unwrap(), result2.unwrap()))
            elif result1.is_failure():
                return Failure(result1.unwrap_error())
            else:
                return Failure(result2.unwrap_error())
        
        return AsyncResult(zipped())
    
    def __await__(self):
        """
        await 지원 (성공 값 직접 반환)
        
        Note: 이 방법은 편의성을 위한 것이며, 에러 처리가 필요한 경우 
              unwrap_async() 또는 to_result()를 사용하는 것이 좋습니다.
        """
        return self.unwrap_async().__await__()
    
    async def __aenter__(self):
        """
        비동기 컨텍스트 매니저 진입
        
        Returns:
            Result[T, E]: 내부 Result
        """
        return await self._get_result()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        비동기 컨텍스트 매니저 종료
        """
        pass
    
    def __repr__(self) -> str:
        return f"AsyncResult({self._coro})"


# === 편의 함수들 ===

def async_success(value: T) -> AsyncResult[T, E]:
    """
    성공 값으로 AsyncResult 생성
    
    Args:
        value: 성공 값
        
    Returns:
        AsyncResult[T, E]: 성공 상태의 AsyncResult
    """
    return AsyncResult.from_value(value)


def async_failure(error: E) -> AsyncResult[T, E]:
    """
    에러로 AsyncResult 생성
    
    Args:
        error: 에러 값
        
    Returns:
        AsyncResult[T, E]: 실패 상태의 AsyncResult
    """
    return AsyncResult.from_error(error)


def from_awaitable(awaitable: Awaitable[T]) -> AsyncResult[T, Exception]:
    """
    일반 Awaitable을 AsyncResult로 래핑
    
    Args:
        awaitable: 변환할 Awaitable
        
    Returns:
        AsyncResult[T, Exception]: 래핑된 AsyncResult
    """
    async def wrapper():
        try:
            result = await awaitable
            return Success(result)
        except Exception as e:
            return Failure(e)
    
    return AsyncResult(wrapper())


async def sequence_async_results(
    results: list[AsyncResult[T, E]]
) -> AsyncResult[list[T], E]:
    """
    AsyncResult 리스트를 병렬로 실행하여 결과 리스트 생성
    
    Args:
        results: AsyncResult들의 리스트
        
    Returns:
        AsyncResult[list[T], E]: 모든 결과의 리스트 또는 첫 번째 에러
    """
    async def sequenced():
        # 모든 AsyncResult를 병렬로 실행
        resolved_results = await asyncio.gather(
            *[result._get_result() for result in results],
            return_exceptions=False
        )
        
        # 결과 검증 및 수집
        values = []
        for result in resolved_results:
            if result.is_success():
                values.append(result.unwrap())
            else:
                return Failure(result.unwrap_error())
        
        return Success(values)
    
    return AsyncResult(sequenced())


async def parallel_map_async(
    func: Callable[[T], Awaitable[U]], 
    items: list[T],
    max_concurrency: int = 10
) -> AsyncResult[list[U], Exception]:
    """
    리스트의 각 항목에 비동기 함수를 병렬 적용 (동시성 제한)
    
    Args:
        func: 각 항목에 적용할 비동기 함수
        items: 처리할 항목들
        max_concurrency: 최대 동시 실행 수
        
    Returns:
        AsyncResult[list[U], Exception]: 변환된 결과들의 리스트
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded_func(item):
        async with semaphore:
            return await func(item)
    
    async def mapped():
        try:
            results = await asyncio.gather(
                *[bounded_func(item) for item in items]
            )
            return Success(results)
        except Exception as e:
            return Failure(e)
    
    return AsyncResult(mapped())