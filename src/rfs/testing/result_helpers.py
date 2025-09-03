"""
Result 패턴 전용 테스팅 헬퍼 시스템

Result, MonoResult, FluxResult의 테스트를 위한 
전문 모킹, 어설션, 테스트 데이터 생성 도구를 제공합니다.
"""

import asyncio
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, Type
from unittest.mock import Mock, AsyncMock, MagicMock
import pytest
import logging

from rfs.core.result import Result, Success, Failure
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult

T = TypeVar('T')
E = TypeVar('E')

logger = logging.getLogger(__name__)


@dataclass
class MockCallRecord:
    """모킹 호출 기록"""
    method_name: str
    args: tuple
    kwargs: dict
    timestamp: float
    result: Any = None
    exception: Optional[Exception] = None
    
    @property
    def was_successful(self) -> bool:
        """호출이 성공했는지 확인"""
        return self.exception is None


class ResultServiceMocker:
    """Result 패턴 서비스 전용 모킹 클래스"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.call_records: List[MockCallRecord] = []
        self._mocked_methods: Dict[str, Mock] = {}
        self._predefined_responses: Dict[str, List[Any]] = {}
        self._default_responses: Dict[str, Any] = {}
        
    def mock_method(self, method_name: str, return_value: Any = None, side_effect: Any = None):
        """메서드 모킹 설정"""
        if asyncio.iscoroutinefunction(return_value) or asyncio.iscoroutine(return_value):
            mock = AsyncMock()
        else:
            mock = Mock()
        
        if return_value is not None:
            mock.return_value = return_value
        if side_effect is not None:
            mock.side_effect = side_effect
        
        # 호출 기록을 위한 래퍼
        original_call = mock._mock_call if hasattr(mock, '_mock_call') else mock
        
        def record_call(*args, **kwargs):
            start_time = time.time()
            record = MockCallRecord(
                method_name=method_name,
                args=args,
                kwargs=kwargs,
                timestamp=start_time
            )
            
            try:
                if asyncio.iscoroutinefunction(original_call):
                    async def async_wrapper():
                        result = await original_call(*args, **kwargs)
                        record.result = result
                        self.call_records.append(record)
                        return result
                    return async_wrapper()
                else:
                    result = original_call(*args, **kwargs)
                    record.result = result
                    self.call_records.append(record)
                    return result
            except Exception as e:
                record.exception = e
                self.call_records.append(record)
                raise
        
        mock.side_effect = record_call
        self._mocked_methods[method_name] = mock
        
        return mock
    
    def return_success(self, method_name: str, value: T) -> "ResultServiceMocker":
        """성공 Result 반환 설정"""
        return self.mock_method(method_name, Success(value))
    
    def return_failure(self, method_name: str, error: E) -> "ResultServiceMocker":
        """실패 Result 반환 설정"""
        return self.mock_method(method_name, Failure(error))
    
    def return_mono_success(self, method_name: str, value: T) -> "ResultServiceMocker":
        """성공 MonoResult 반환 설정"""
        async def mono_func():
            return Success(value)
        return self.mock_method(method_name, MonoResult(mono_func))
    
    def return_mono_failure(self, method_name: str, error: E) -> "ResultServiceMocker":
        """실패 MonoResult 반환 설정"""
        async def mono_func():
            return Failure(error)
        return self.mock_method(method_name, MonoResult(mono_func))
    
    def return_flux_results(self, method_name: str, results: List[Result[T, E]]) -> "ResultServiceMocker":
        """FluxResult 반환 설정"""
        flux_result = FluxResult.from_results(results)
        return self.mock_method(method_name, flux_result)
    
    def return_sequence(self, method_name: str, values: List[Any]) -> "ResultServiceMocker":
        """순차적 반환값 설정"""
        self._predefined_responses[method_name] = values.copy()
        
        def sequence_side_effect(*args, **kwargs):
            if method_name in self._predefined_responses and self._predefined_responses[method_name]:
                return self._predefined_responses[method_name].pop(0)
            else:
                # 기본값 또는 예외
                if method_name in self._default_responses:
                    return self._default_responses[method_name]
                raise ValueError(f"No more predefined responses for {method_name}")
        
        return self.mock_method(method_name, side_effect=sequence_side_effect)
    
    def assert_called(self, method_name: str):
        """메서드가 호출되었는지 확인"""
        calls = [record for record in self.call_records if record.method_name == method_name]
        assert len(calls) > 0, f"Method {method_name} was not called"
    
    def assert_called_once(self, method_name: str):
        """메서드가 정확히 한 번 호출되었는지 확인"""
        calls = [record for record in self.call_records if record.method_name == method_name]
        assert len(calls) == 1, f"Method {method_name} was called {len(calls)} times, expected 1"
    
    def assert_called_with(self, method_name: str, *args, **kwargs):
        """메서드가 특정 인수로 호출되었는지 확인"""
        matching_calls = [
            record for record in self.call_records 
            if record.method_name == method_name and record.args == args and record.kwargs == kwargs
        ]
        assert len(matching_calls) > 0, f"Method {method_name} was not called with args {args} and kwargs {kwargs}"
    
    def assert_not_called(self, method_name: str):
        """메서드가 호출되지 않았는지 확인"""
        calls = [record for record in self.call_records if record.method_name == method_name]
        assert len(calls) == 0, f"Method {method_name} was called {len(calls)} times, expected 0"
    
    def get_call_count(self, method_name: str) -> int:
        """특정 메서드 호출 횟수 반환"""
        return len([record for record in self.call_records if record.method_name == method_name])
    
    def get_call_args(self, method_name: str, call_index: int = 0) -> tuple:
        """특정 호출의 인수 반환"""
        calls = [record for record in self.call_records if record.method_name == method_name]
        if call_index < len(calls):
            return calls[call_index].args
        raise IndexError(f"Call index {call_index} out of range for method {method_name}")
    
    def reset_mock(self):
        """모킹 상태 초기화"""
        self.call_records.clear()
        for mock in self._mocked_methods.values():
            mock.reset_mock()
        self._predefined_responses.clear()
    
    def get_mock(self, method_name: str) -> Optional[Mock]:
        """특정 메서드의 Mock 객체 반환"""
        return self._mocked_methods.get(method_name)


@contextmanager
def mock_result_service(service_name: str, *methods: str):
    """Result 서비스 모킹 컨텍스트 매니저"""
    mocker = ResultServiceMocker(service_name)
    
    # 메서드들을 기본 설정으로 모킹
    for method_name in methods:
        mocker.mock_method(method_name)
    
    try:
        yield mocker
    finally:
        mocker.reset_mock()


# Result 검증 함수들

def assert_result_success(result: Result[T, E], expected_type: Optional[Type[T]] = None):
    """Result가 성공인지 확인"""
    assert result.is_success(), f"Expected success but got failure: {result.unwrap_error()}"
    
    if expected_type is not None:
        value = result.unwrap()
        assert isinstance(value, expected_type), \
            f"Expected type {expected_type.__name__}, got {type(value).__name__}"


def assert_result_failure(result: Result[T, E], expected_error_type: Optional[Type[E]] = None):
    """Result가 실패인지 확인"""
    assert result.is_failure(), f"Expected failure but got success: {result.unwrap()}"
    
    if expected_error_type is not None:
        error = result.unwrap_error()
        assert isinstance(error, expected_error_type), \
            f"Expected error type {expected_error_type.__name__}, got {type(error).__name__}"


def assert_result_value(result: Result[T, E], expected_value: T):
    """Result의 값이 예상값과 같은지 확인"""
    assert_result_success(result)
    actual_value = result.unwrap()
    assert actual_value == expected_value, \
        f"Expected value {expected_value}, got {actual_value}"


def assert_result_error(result: Result[T, E], expected_error: E):
    """Result의 에러가 예상값과 같은지 확인"""
    assert_result_failure(result)
    actual_error = result.unwrap_error()
    assert actual_error == expected_error, \
        f"Expected error {expected_error}, got {actual_error}"


# MonoResult 검증 함수들

async def assert_mono_result_success(
    mono_result: MonoResult[T, E], 
    expected_type: Optional[Type[T]] = None
):
    """MonoResult가 성공인지 확인"""
    result = await mono_result.to_result()
    assert_result_success(result, expected_type)


async def assert_mono_result_failure(
    mono_result: MonoResult[T, E], 
    expected_error_type: Optional[Type[E]] = None
):
    """MonoResult가 실패인지 확인"""
    result = await mono_result.to_result()
    assert_result_failure(result, expected_error_type)


async def assert_mono_result_value(mono_result: MonoResult[T, E], expected_value: T):
    """MonoResult의 값이 예상값과 같은지 확인"""
    result = await mono_result.to_result()
    assert_result_value(result, expected_value)


# FluxResult 검증 함수들

def assert_flux_success_count(flux_result: FluxResult[T, E], expected_count: int):
    """FluxResult의 성공 개수 확인"""
    actual_count = flux_result.count_success()
    assert actual_count == expected_count, \
        f"Expected {expected_count} successes, got {actual_count}"


def assert_flux_failure_count(flux_result: FluxResult[T, E], expected_count: int):
    """FluxResult의 실패 개수 확인"""
    actual_count = flux_result.count_failures()
    assert actual_count == expected_count, \
        f"Expected {expected_count} failures, got {actual_count}"


def assert_flux_total_count(flux_result: FluxResult[T, E], expected_count: int):
    """FluxResult의 총 개수 확인"""
    actual_count = flux_result.count_total()
    assert actual_count == expected_count, \
        f"Expected {expected_count} total items, got {actual_count}"


def assert_flux_success_rate(flux_result: FluxResult[T, E], expected_rate: float, tolerance: float = 0.01):
    """FluxResult의 성공률 확인"""
    actual_rate = flux_result.success_rate()
    assert abs(actual_rate - expected_rate) <= tolerance, \
        f"Expected success rate {expected_rate}, got {actual_rate}"


async def assert_flux_success_values(flux_result: FluxResult[T, E], expected_values: List[T]):
    """FluxResult의 성공 값들 확인"""
    success_values_result = await flux_result.collect_success_values().to_result()
    assert_result_success(success_values_result)
    
    actual_values = success_values_result.unwrap()
    assert actual_values == expected_values, \
        f"Expected success values {expected_values}, got {actual_values}"


# 테스트 데이터 생성기

class ResultTestDataFactory:
    """Result 패턴 테스트 데이터 생성 팩토리"""
    
    @staticmethod
    def create_success_result(value: T = "test_value") -> Result[T, str]:
        """성공 Result 생성"""
        return Success(value)
    
    @staticmethod
    def create_failure_result(error: E = "test_error") -> Result[str, E]:
        """실패 Result 생성"""
        return Failure(error)
    
    @staticmethod
    def create_success_mono(value: T = "test_value") -> MonoResult[T, str]:
        """성공 MonoResult 생성"""
        async def success_func():
            return Success(value)
        return MonoResult(success_func)
    
    @staticmethod
    def create_failure_mono(error: E = "test_error") -> MonoResult[str, E]:
        """실패 MonoResult 생성"""
        async def failure_func():
            return Failure(error)
        return MonoResult(failure_func)
    
    @staticmethod
    def create_mixed_flux(
        success_values: List[T], 
        error_values: List[E]
    ) -> FluxResult[T, E]:
        """성공/실패 혼합 FluxResult 생성"""
        results = []
        
        for value in success_values:
            results.append(Success(value))
        
        for error in error_values:
            results.append(Failure(error))
        
        return FluxResult.from_results(results)
    
    @staticmethod
    def create_all_success_flux(values: List[T]) -> FluxResult[T, str]:
        """모든 성공 FluxResult 생성"""
        return FluxResult.from_values(values)
    
    @staticmethod
    def create_all_failure_flux(errors: List[E]) -> FluxResult[str, E]:
        """모든 실패 FluxResult 생성"""
        results = [Failure(error) for error in errors]
        return FluxResult.from_results(results)


# 성능 테스트 헬퍼

class PerformanceTestHelper:
    """성능 테스트 도우미"""
    
    @staticmethod
    async def measure_mono_performance(
        mono_result: MonoResult[T, E], 
        max_duration_ms: float = 1000.0
    ) -> Dict[str, Any]:
        """MonoResult 성능 측정"""
        start_time = time.time()
        
        try:
            result = await mono_result.to_result()
            duration_ms = (time.time() - start_time) * 1000
            
            performance_data = {
                "duration_ms": duration_ms,
                "max_duration_ms": max_duration_ms,
                "is_within_limit": duration_ms <= max_duration_ms,
                "success": result.is_success(),
                "timestamp": start_time
            }
            
            if not performance_data["is_within_limit"]:
                logger.warning(f"Performance test failed: {duration_ms}ms > {max_duration_ms}ms")
            
            return performance_data
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {
                "duration_ms": duration_ms,
                "max_duration_ms": max_duration_ms,
                "is_within_limit": False,
                "success": False,
                "exception": str(e),
                "timestamp": start_time
            }
    
    @staticmethod
    def assert_performance(performance_data: Dict[str, Any]):
        """성능 데이터 검증"""
        assert performance_data["is_within_limit"], \
            f"Performance test failed: {performance_data['duration_ms']}ms > {performance_data['max_duration_ms']}ms"


# 통합 테스트 헬퍼

@asynccontextmanager
async def result_test_context(
    service_mocks: Optional[Dict[str, ResultServiceMocker]] = None,
    performance_tracking: bool = False
):
    """Result 패턴 통합 테스트 컨텍스트"""
    
    context = {
        "service_mocks": service_mocks or {},
        "performance_data": [] if performance_tracking else None,
        "start_time": time.time()
    }
    
    try:
        yield context
    finally:
        # 정리 작업
        for mocker in context["service_mocks"].values():
            mocker.reset_mock()
        
        # 성능 데이터 로깅
        if context["performance_data"]:
            total_duration = time.time() - context["start_time"]
            logger.info(f"Test completed in {total_duration:.2f}s with {len(context['performance_data'])} performance measurements")


# Pytest 픽스처들

@pytest.fixture
def result_factory():
    """Result 테스트 데이터 팩토리 픽스처"""
    return ResultTestDataFactory()


@pytest.fixture
def success_result():
    """성공 Result 픽스처"""
    return ResultTestDataFactory.create_success_result("fixture_value")


@pytest.fixture
def failure_result():
    """실패 Result 픽스처"""
    return ResultTestDataFactory.create_failure_result("fixture_error")


@pytest.fixture
async def success_mono():
    """성공 MonoResult 픽스처"""
    return ResultTestDataFactory.create_success_mono("fixture_mono_value")


@pytest.fixture
def performance_helper():
    """성능 테스트 헬퍼 픽스처"""
    return PerformanceTestHelper()


# 커스텀 pytest 마커

def result_test(func):
    """Result 테스트임을 표시하는 데코레이터"""
    func.pytestmark = pytest.mark.result_test
    return func


def mono_test(func):
    """MonoResult 테스트임을 표시하는 데코레이터"""
    func.pytestmark = pytest.mark.mono_test
    return func


def flux_test(func):
    """FluxResult 테스트임을 표시하는 데코레이터"""
    func.pytestmark = pytest.mark.flux_test
    return func


def performance_test(max_duration_ms: float = 1000.0):
    """성능 테스트 데코레이터"""
    def decorator(func):
        func.pytestmark = pytest.mark.performance_test
        func.__performance_max_duration__ = max_duration_ms
        return func
    return decorator