"""
RFS Framework 표준 테스트 유틸리티

RFS Framework 개발을 위한 표준화된 테스트 인프라 제공:
- RFSTestCase: 기본 테스트 클래스
- Result 패턴 테스트 유틸리티
- 비동기 테스트 지원
- pytest 픽스처
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, TypeVar
from unittest.mock import AsyncMock, Mock

import pytest

from rfs.core.result import Failure, Result, Success

T = TypeVar("T")
E = TypeVar("E")


class RFSTestCase:
    """RFS Framework 표준 테스트 베이스 클래스"""

    def setup_method(self) -> None:
        """테스트 메서드별 설정"""
        self.mock_container: Mock = Mock()
        self.test_data: Dict[str, Any] = {}

    def teardown_method(self) -> None:
        """테스트 메서드별 정리"""
        self.mock_container.reset_mock()
        self.test_data.clear()

    def assert_success(
        self, result: Result[Any, Any], expected_value: Any = None
    ) -> None:
        """Result Success 검증

        Args:
            result: 검증할 Result 객체
            expected_value: 예상 값 (선택적)

        Raises:
            AssertionError: Result가 Success가 아니거나 값이 예상과 다를 때
        """
        assert (
            result.is_success()
        ), f"Expected Success but got Failure: {result.unwrap_error() if result.is_failure() else 'Unknown'}"

        if expected_value is not None:
            actual_value = result.unwrap()
            assert (
                actual_value == expected_value
            ), f"Expected {expected_value} but got {actual_value}"

    def assert_failure(
        self, result: Result[Any, Any], expected_error: Any = None
    ) -> None:
        """Result Failure 검증

        Args:
            result: 검증할 Result 객체
            expected_error: 예상 에러 (선택적)

        Raises:
            AssertionError: Result가 Failure가 아니거나 에러가 예상과 다를 때
        """
        assert (
            result.is_failure()
        ), f"Expected Failure but got Success: {result.unwrap() if result.is_success() else 'Unknown'}"

        if expected_error is not None:
            actual_error = result.unwrap_error()
            assert (
                actual_error == expected_error
            ), f"Expected error {expected_error} but got {actual_error}"

    def assert_success_type(
        self, result: Result[Any, Any], expected_type: type
    ) -> None:
        """Result Success 값의 타입 검증

        Args:
            result: 검증할 Result 객체
            expected_type: 예상 타입
        """
        self.assert_success(result)
        actual_value = result.unwrap()
        assert isinstance(
            actual_value, expected_type
        ), f"Expected type {expected_type} but got {type(actual_value)}"

    def assert_failure_contains(
        self, result: Result[Any, Any], error_substring: str
    ) -> None:
        """Result Failure 에러 메시지 부분 일치 검증

        Args:
            result: 검증할 Result 객체
            error_substring: 에러 메시지에 포함되어야 할 문자열
        """
        self.assert_failure(result)
        error_message = str(result.unwrap_error())
        assert (
            error_substring in error_message
        ), f"Error message '{error_message}' does not contain '{error_substring}'"

    def create_mock_result_success(self, value: T) -> Result[T, Any]:
        """성공 Result 모킹 헬퍼"""
        return Success(value)

    def create_mock_result_failure(self, error: E) -> Result[Any, E]:
        """실패 Result 모킹 헬퍼"""
        return Failure(error)

    def create_async_mock_result(self, result: Result[T, E]) -> AsyncMock:
        """비동기 Result 반환 함수 모킹 헬퍼"""
        mock = AsyncMock()
        mock.return_value = result
        return mock


@pytest.fixture
def rfs_test_environment() -> Dict[str, Any]:
    """RFS 테스트 환경 픽스처

    Returns:
        Dict[str, Any]: 테스트 환경 설정
    """
    return {
        "redis_enabled": False,
        "rapidapi_enabled": False,
        "test_mode": True,
        "log_level": "DEBUG",
        "environment": "test",
        "mock_external_services": True,
    }


@pytest.fixture
def sample_data() -> Dict[str, Any]:
    """테스트용 샘플 데이터 픽스처"""
    return {
        "users": [
            {"id": 1, "name": "홍길동", "email": "hong@example.com"},
            {"id": 2, "name": "김철수", "email": "kim@example.com"},
            {"id": 3, "name": "이영희", "email": "lee@example.com"},
        ],
        "products": [
            {"id": 1, "name": "노트북", "price": 1500000},
            {"id": 2, "name": "마우스", "price": 50000},
        ],
        "config": {"api_timeout": 30, "max_retries": 3, "cache_ttl": 3600},
    }


@pytest.fixture
def edge_case_data() -> Dict[str, Any]:
    """엣지 케이스 테스트용 데이터 픽스처"""
    return {
        "empty_values": {"string": "", "list": [], "dict": {}, "none": None},
        "large_values": {
            "string": "x" * 10000,
            "list": list(range(1000)),
            "number": 999999999999999999,
        },
        "unicode_values": ["안녕하세요", "こんにちは", "🌟✨🎉", "Ñoël", "Москва"],
        "special_characters": ["\n\r\t", "\"'`", "<>&", "\\//", "@#$%^&*()"],
    }


class AsyncTestMixin:
    """비동기 테스트를 위한 믹스인 클래스"""

    @pytest.mark.asyncio
    async def assert_async_success(
        self, async_result_func: Callable, expected_value: Any = None
    ) -> None:
        """비동기 함수의 Success 결과 검증

        Args:
            async_result_func: 비동기 Result 반환 함수
            expected_value: 예상 값 (선택적)
        """
        result = await async_result_func()
        assert (
            result.is_success()
        ), f"Expected Success but got Failure: {result.unwrap_error() if result.is_failure() else 'Unknown'}"

        if expected_value is not None:
            actual_value = result.unwrap()
            assert (
                actual_value == expected_value
            ), f"Expected {expected_value} but got {actual_value}"

    @pytest.mark.asyncio
    async def assert_async_failure(
        self, async_result_func: Callable, expected_error: Any = None
    ) -> None:
        """비동기 함수의 Failure 결과 검증

        Args:
            async_result_func: 비동기 Result 반환 함수
            expected_error: 예상 에러 (선택적)
        """
        result = await async_result_func()
        assert (
            result.is_failure()
        ), f"Expected Failure but got Success: {result.unwrap() if result.is_success() else 'Unknown'}"

        if expected_error is not None:
            actual_error = result.unwrap_error()
            assert (
                actual_error == expected_error
            ), f"Expected error {expected_error} but got {actual_error}"


def async_test_decorator(func: Callable) -> Callable:
    """비동기 테스트 데코레이터

    Args:
        func: 테스트 함수

    Returns:
        Callable: pytest.mark.asyncio가 적용된 테스트 함수
    """
    return pytest.mark.asyncio(func)


class MockHOFPipeline:
    """HOF 파이프라인 테스트용 모킹 클래스"""

    def __init__(self):
        self.operations: List[Callable] = []
        self.results: List[Result] = []

    def add_operation(self, operation: Callable, expected_result: Result) -> None:
        """파이프라인에 연산과 예상 결과 추가

        Args:
            operation: 추가할 연산
            expected_result: 예상 결과
        """
        self.operations.append(operation)
        self.results.append(expected_result)

    def mock_pipeline(self, initial_value: Any) -> Result:
        """파이프라인 실행 모킹

        Args:
            initial_value: 초기 값

        Returns:
            Result: 모킹된 파이프라인 실행 결과
        """
        if not self.results:
            return Success(initial_value)

        # 첫 번째 실패 결과 반환 또는 마지막 성공 결과 반환
        for result in self.results:
            if result.is_failure():
                return result

        return self.results[-1]


@pytest.fixture
def mock_hof_pipeline() -> MockHOFPipeline:
    """HOF 파이프라인 모킹 픽스처"""
    return MockHOFPipeline()


def performance_test(max_duration_ms: int = 1000):
    """성능 테스트 데코레이터

    Args:
        max_duration_ms: 최대 허용 실행 시간 (밀리초)

    Returns:
        Callable: 성능 테스트가 적용된 데코레이터
    """

    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            import time

            start_time = time.time()
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000

                assert (
                    duration_ms <= max_duration_ms
                ), f"Test took {duration_ms:.2f}ms, expected <= {max_duration_ms}ms"
                return result
            except Exception as e:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                raise

        def sync_wrapper(*args, **kwargs):
            import time

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000

                assert (
                    duration_ms <= max_duration_ms
                ), f"Test took {duration_ms:.2f}ms, expected <= {max_duration_ms}ms"
                return result
            except Exception as e:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                raise

        if asyncio.iscoroutinefunction(func):
            return pytest.mark.asyncio(async_wrapper)
        else:
            return sync_wrapper

    return decorator


# HOF 테스트를 위한 유틸리티 함수들
def create_test_pipeline(*operations: Callable) -> List[Callable]:
    """테스트용 파이프라인 생성

    Args:
        *operations: 파이프라인에 포함할 연산들

    Returns:
        List[Callable]: 파이프라인 연산 리스트
    """
    return list(operations)


def assert_pipeline_result(
    pipeline: List[Callable], initial_value: Any, expected_result: Result
) -> None:
    """파이프라인 실행 결과 검증

    Args:
        pipeline: 테스트할 파이프라인
        initial_value: 초기 입력 값
        expected_result: 예상 결과
    """
    # 실제 파이프라인 실행은 호출하는 테스트에서 구현
    # 여기서는 결과 검증 로직만 제공
    from rfs.core.result import pipe_results

    pipeline_func = pipe_results(*pipeline)
    actual_result = pipeline_func(initial_value)

    if expected_result.is_success():
        assert (
            actual_result.is_success()
        ), f"Expected Success but got Failure: {actual_result.unwrap_error()}"
        assert actual_result.unwrap() == expected_result.unwrap()
    else:
        assert (
            actual_result.is_failure()
        ), f"Expected Failure but got Success: {actual_result.unwrap()}"
        # 에러 메시지는 정확히 일치하지 않을 수 있으므로 타입만 확인
        assert type(actual_result.unwrap_error()) == type(
            expected_result.unwrap_error()
        )
