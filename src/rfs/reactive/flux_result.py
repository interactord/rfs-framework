"""
FluxResult - Flux와 Result 패턴 통합

Flux의 스트림 처리 능력과 Result의 타입 안전한 에러 처리를 결합한 클래스입니다.
여러 개의 Result를 스트림으로 처리하고, 성공한 결과만 필터링하거나 
배치로 수집하는 등의 작업을 우아하게 처리할 수 있도록 설계되었습니다.
"""

import asyncio
from typing import Any, Awaitable, Callable, Generic, List, TypeVar, Union

from ..core.result import Failure, Result, Success
from .mono_result import MonoResult

T = TypeVar("T")  # 성공 값 타입
E = TypeVar("E")  # 에러 값 타입
U = TypeVar("U")  # 변환된 값 타입
F = TypeVar("F")  # 변환된 에러 타입


class FluxResult(Generic[T, E]):
    """
    Flux + Result 패턴 통합 클래스
    
    여러 개의 Result를 스트림으로 처리하고, 성공/실패를 분리하여
    배치 처리나 병렬 처리를 우아하게 수행할 수 있습니다.
    
    주요 특징:
    - 스트림 기반 Result 처리
    - 성공한 결과만 필터링
    - 병렬 비동기 매핑
    - 배치 수집 및 집계
    
    Example:
        >>> # 사용자 배치 처리
        >>> user_ids = ["1", "2", "3", "invalid"]
        >>> results = await (
        ...     FluxResult.from_async_results([
        ...         lambda: fetch_user(user_id) for user_id in user_ids
        ...     ])
        ...     .filter_success()
        ...     .parallel_map_async(lambda user: validate_user_async(user))
        ...     .collect_results()
        ...     .to_result()
        ... )
    """

    def __init__(self, results: List[Result[T, E]]):
        """
        FluxResult 생성자
        
        Args:
            results: Result 리스트
        """
        self._results = results

    # ==================== 생성 메서드 (Static Factory) ====================

    @staticmethod
    def from_results(results: List[Result[T, E]]) -> "FluxResult[T, E]":
        """
        Result 리스트로 FluxResult 생성
        
        Args:
            results: Result 리스트
            
        Returns:
            FluxResult: 결과들을 감싼 FluxResult
            
        Example:
            >>> results = [Success("a"), Failure("error"), Success("b")]
            >>> flux = FluxResult.from_results(results)
        """
        return FluxResult(results)

    @staticmethod
    async def from_async_results(
        async_funcs: List[Callable[[], Awaitable[Result[T, E]]]]
    ) -> "FluxResult[T, E]":
        """
        비동기 Result 함수 리스트로 FluxResult 생성
        
        Args:
            async_funcs: 비동기 Result 함수 리스트
            
        Returns:
            FluxResult: 비동기 실행 결과들을 감싼 FluxResult
            
        Example:
            >>> async_funcs = [
            ...     lambda: fetch_user("1"),
            ...     lambda: fetch_user("2"),
            ...     lambda: fetch_user("3")
            ... ]
            >>> flux = await FluxResult.from_async_results(async_funcs)
        """
        # 모든 비동기 함수를 병렬로 실행
        tasks = [func() for func in async_funcs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외를 Result로 변환
        converted_results = []
        for result in results:
            if isinstance(result, Exception):
                converted_results.append(Failure(str(result)))
            else:
                converted_results.append(result)
        
        return FluxResult(converted_results)

    @staticmethod
    def from_values(values: List[T]) -> "FluxResult[T, E]":
        """
        값 리스트로 FluxResult 생성 (모두 성공으로 처리)
        
        Args:
            values: 값 리스트
            
        Returns:
            FluxResult: 성공 결과들을 감싼 FluxResult
            
        Example:
            >>> flux = FluxResult.from_values(["a", "b", "c"])
        """
        results = [Success(value) for value in values]
        return FluxResult(results)

    @staticmethod
    def empty() -> "FluxResult[T, E]":
        """
        빈 FluxResult 생성
        
        Returns:
            FluxResult: 빈 FluxResult
        """
        return FluxResult([])

    # ==================== 변환 메서드 ====================

    def map(self, func: Callable[[T], U]) -> "FluxResult[U, E]":
        """
        성공 값들을 변환 (에러는 그대로 전파)
        
        Args:
            func: 값 변환 함수
            
        Returns:
            FluxResult: 변환된 값들을 가진 FluxResult
            
        Example:
            >>> flux = FluxResult.from_values(["hello", "world"])
            >>> upper_flux = flux.map(lambda s: s.upper())
        """
        transformed_results = []
        for result in self._results:
            if result.is_success():
                try:
                    transformed_value = func(result.unwrap())
                    transformed_results.append(Success(transformed_value))
                except Exception as e:
                    transformed_results.append(Failure(e))
            else:
                transformed_results.append(result)  # 에러는 그대로 전파
        
        return FluxResult(transformed_results)

    def map_error(self, func: Callable[[E], F]) -> "FluxResult[T, F]":
        """
        에러들을 변환 (성공 값은 그대로 유지)
        
        Args:
            func: 에러 변환 함수
            
        Returns:
            FluxResult: 변환된 에러들을 가진 FluxResult
        """
        transformed_results = []
        for result in self._results:
            if result.is_failure():
                try:
                    transformed_error = func(result.unwrap_error())
                    transformed_results.append(Failure(transformed_error))
                except Exception as e:
                    transformed_results.append(Failure(e))
            else:
                transformed_results.append(result)  # 성공은 그대로 유지
        
        return FluxResult(transformed_results)

    # ==================== 필터링 메서드 ====================

    def filter_success(self) -> "FluxResult[T, E]":
        """
        성공한 결과만 필터링
        
        Returns:
            FluxResult: 성공한 결과들만 포함하는 FluxResult
            
        Example:
            >>> results = [Success("a"), Failure("error"), Success("b")]
            >>> flux = FluxResult.from_results(results)
            >>> success_only = flux.filter_success()  # [Success("a"), Success("b")]
        """
        success_results = [r for r in self._results if r.is_success()]
        return FluxResult(success_results)

    def filter_failures(self) -> "FluxResult[T, E]":
        """
        실패한 결과만 필터링
        
        Returns:
            FluxResult: 실패한 결과들만 포함하는 FluxResult
        """
        failure_results = [r for r in self._results if r.is_failure()]
        return FluxResult(failure_results)

    def filter(self, predicate: Callable[[T], bool]) -> "FluxResult[T, E]":
        """
        성공 값에 대한 조건부 필터링
        
        Args:
            predicate: 필터 조건 함수
            
        Returns:
            FluxResult: 조건을 만족하는 성공 결과들만 포함
            
        Example:
            >>> numbers = FluxResult.from_values([1, 2, 3, 4, 5])
            >>> evens = numbers.filter(lambda n: n % 2 == 0)
        """
        filtered_results = []
        for result in self._results:
            if result.is_success():
                try:
                    if predicate(result.unwrap()):
                        filtered_results.append(result)
                except Exception:
                    # predicate 실행 중 예외 발생 시 제외
                    pass
            else:
                # 실패는 그대로 유지 (나중에 filter_success로 제거 가능)
                filtered_results.append(result)
        
        return FluxResult(filtered_results)

    # ==================== 병렬 처리 메서드 ====================

    async def parallel_map_async(
        self,
        func: Callable[[T], Awaitable[Result[U, E]]],
        max_concurrency: int = 10
    ) -> "FluxResult[U, E]":
        """
        성공 값들을 병렬로 비동기 변환
        
        Args:
            func: 비동기 변환 함수
            max_concurrency: 최대 동시 실행 수
            
        Returns:
            FluxResult: 변환된 결과들을 가진 FluxResult
            
        Example:
            >>> users = FluxResult.from_values([user1, user2, user3])
            >>> validated = await users.parallel_map_async(
            ...     lambda user: validate_user_async(user),
            ...     max_concurrency=5
            ... )
        """
        # 세마포어로 동시 실행 수 제한
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def process_result(result: Result[T, E]) -> Result[U, E]:
            if result.is_failure():
                return result  # 실패는 그대로 전파
            
            async with semaphore:
                try:
                    return await func(result.unwrap())
                except Exception as e:
                    return Failure(e)
        
        # 모든 결과를 병렬로 처리
        tasks = [process_result(result) for result in self._results]
        transformed_results = await asyncio.gather(*tasks)
        
        return FluxResult(transformed_results)

    async def parallel_map(
        self,
        func: Callable[[T], U],
        max_concurrency: int = 10
    ) -> "FluxResult[U, E]":
        """
        성공 값들을 병렬로 동기 변환 (executor 사용)
        
        Args:
            func: 동기 변환 함수
            max_concurrency: 최대 동시 실행 수
            
        Returns:
            FluxResult: 변환된 결과들을 가진 FluxResult
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def process_result(result: Result[T, E]) -> Result[U, E]:
            if result.is_failure():
                return result
            
            async with semaphore:
                loop = asyncio.get_event_loop()
                try:
                    transformed_value = await loop.run_in_executor(
                        None, func, result.unwrap()
                    )
                    return Success(transformed_value)
                except Exception as e:
                    return Failure(e)
        
        tasks = [process_result(result) for result in self._results]
        transformed_results = await asyncio.gather(*tasks)
        
        return FluxResult(transformed_results)

    # ==================== 수집 및 집계 메서드 ====================

    def collect_results(self) -> "MonoResult[List[T], List[E]]":
        """
        모든 결과를 MonoResult로 수집
        
        Returns:
            MonoResult: 성공 값들의 리스트 또는 에러들의 리스트
            
        Example:
            >>> flux = FluxResult.from_values([1, 2, 3])
            >>> mono = flux.collect_results()
            >>> result = await mono.to_result()  # Success([1, 2, 3])
        """
        successes = []
        failures = []
        
        for result in self._results:
            if result.is_success():
                successes.append(result.unwrap())
            else:
                failures.append(result.unwrap_error())
        
        if not failures:
            # 모든 결과가 성공인 경우
            return MonoResult.from_result(Success(successes))
        else:
            # 하나라도 실패가 있는 경우
            return MonoResult.from_result(Failure(failures))

    def collect_success_values(self) -> "MonoResult[List[T], str]":
        """
        성공 값들만 수집 (실패는 무시)
        
        Returns:
            MonoResult: 성공 값들의 리스트
            
        Example:
            >>> mixed = [Success("a"), Failure("error"), Success("b")]
            >>> flux = FluxResult.from_results(mixed)
            >>> mono = flux.collect_success_values()
            >>> result = await mono.to_result()  # Success(["a", "b"])
        """
        success_values = [
            result.unwrap() for result in self._results 
            if result.is_success()
        ]
        return MonoResult.from_result(Success(success_values))

    def collect_error_values(self) -> "MonoResult[List[E], str]":
        """
        에러 값들만 수집 (성공은 무시)
        
        Returns:
            MonoResult: 에러 값들의 리스트
        """
        error_values = [
            result.unwrap_error() for result in self._results 
            if result.is_failure()
        ]
        return MonoResult.from_result(Success(error_values))

    # ==================== 통계 및 분석 메서드 ====================

    def count_success(self) -> int:
        """성공한 결과의 개수"""
        return len([r for r in self._results if r.is_success()])

    def count_failures(self) -> int:
        """실패한 결과의 개수"""
        return len([r for r in self._results if r.is_failure()])

    def count_total(self) -> int:
        """전체 결과의 개수"""
        return len(self._results)

    def success_rate(self) -> float:
        """성공률 (0.0 ~ 1.0)"""
        total = self.count_total()
        if total == 0:
            return 0.0
        return self.count_success() / total

    def is_all_success(self) -> bool:
        """모든 결과가 성공인지 확인"""
        return all(r.is_success() for r in self._results)

    def is_any_failure(self) -> bool:
        """하나라도 실패가 있는지 확인"""
        return any(r.is_failure() for r in self._results)

    # ==================== 편의 메서드 ====================

    def take(self, n: int) -> "FluxResult[T, E]":
        """처음 n개 결과만 선택"""
        return FluxResult(self._results[:n])

    def skip(self, n: int) -> "FluxResult[T, E]":
        """처음 n개 결과 건너뛰기"""
        return FluxResult(self._results[n:])

    def to_list(self) -> List[Result[T, E]]:
        """내부 Results 리스트 반환"""
        return self._results.copy()

    def __len__(self) -> int:
        """결과 개수 반환"""
        return len(self._results)

    def __iter__(self):
        """반복자 지원"""
        return iter(self._results)

    def __repr__(self) -> str:
        """디버깅을 위한 문자열 표현"""
        success_count = self.count_success()
        failure_count = self.count_failures()
        return f"FluxResult(success={success_count}, failures={failure_count}, total={len(self._results)})"