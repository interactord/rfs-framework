# 테스팅 유틸리티 상세 사양서

**문서 버전**: 1.0  
**작성일**: 2025-09-03  
**상태**: 설계 완료

---

## 📋 개요

Phase 1의 MonoResult/FluxResult 패턴과 Phase 2의 FastAPI 통합을 효과적으로 테스트하기 위한 전문 테스팅 유틸리티의 상세 사양입니다. Result 패턴 기반 코드의 테스트 작성을 대폭 간소화하고 일관성을 보장합니다.

---

## 🎯 1. Result 모킹 시스템 (`result_helpers.py`)

### 1.1 ResultServiceMocker 클래스

**목적**: Result 패턴을 반환하는 서비스를 쉽게 모킹할 수 있는 클래스

#### 구현 사양
```python
from typing import Any, List, Optional, Union, Callable, Type
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
import asyncio
import pytest
from rfs.core.result import Result, Success, Failure

class ResultServiceMocker:
    """Result 패턴 기반 서비스 모킹 클래스"""
    
    def __init__(self, service_path: str, method_name: str):
        """
        ResultServiceMocker 초기화
        
        Args:
            service_path: 서비스 클래스의 임포트 경로 ("services.user_service.UserService")
            method_name: 모킹할 메서드 이름 ("get_user_async")
        """
        self.service_path = service_path
        self.method_name = method_name
        self.full_path = f"{service_path}.{method_name}"
        
        # 호출 기록
        self.call_count = 0
        self.call_args_history: List[tuple] = []
        self.call_kwargs_history: List[dict] = []
        
        # 반환값 설정
        self._return_results: List[Result] = []
        self._return_sequence: List[Result] = []
        self._sequence_index = 0
        self._side_effect_func: Optional[Callable] = None
        
        # Mock 객체
        self._mock_obj: Optional[MagicMock] = None
        self._patcher = None
    
    def return_success(self, value: Any) -> "ResultServiceMocker":
        """성공 결과 반환 설정"""
        self._return_results = [Success(value)]
        return self
    
    def return_error(self, error: Any) -> "ResultServiceMocker":
        """에러 결과 반환 설정"""
        self._return_results = [Failure(error)]
        return self
    
    def return_sequence(self, results: List[Result]) -> "ResultServiceMocker":
        """
        순차적 결과 반환 설정
        
        Args:
            results: 호출 순서대로 반환할 Result 리스트
            
        Example:
            mocker.return_sequence([
                Success(user1),
                Failure("User not found"),
                Success(user2)
            ])
        """
        self._return_sequence = results.copy()
        self._sequence_index = 0
        return self
    
    def return_success_sequence(self, values: List[Any]) -> "ResultServiceMocker":
        """성공 값들의 순차적 반환 설정 (편의 메서드)"""
        results = [Success(value) for value in values]
        return self.return_sequence(results)
    
    def return_error_sequence(self, errors: List[Any]) -> "ResultServiceMocker":
        """에러 값들의 순차적 반환 설정 (편의 메서드)"""
        results = [Failure(error) for error in errors]
        return self.return_sequence(results)
    
    def return_mixed_sequence(self, items: List[Union[tuple, Any]]) -> "ResultServiceMocker":
        """
        성공/에러 혼합 순차적 반환 설정
        
        Args:
            items: (success/error, value) 튜플 또는 단순 값의 리스트
            
        Example:
            mocker.return_mixed_sequence([
                ("success", user1),
                ("error", "Not found"),
                user2,  # 단순 값은 자동으로 Success
                ("error", APIError.not_found("User"))
            ])
        """
        results = []
        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                result_type, value = item
                if result_type == "success":
                    results.append(Success(value))
                elif result_type == "error":
                    results.append(Failure(value))
                else:
                    raise ValueError(f"Invalid result type: {result_type}")
            else:
                # 단순 값은 Success로 처리
                results.append(Success(item))
        
        return self.return_sequence(results)
    
    def side_effect(self, func: Callable) -> "ResultServiceMocker":
        """
        사이드 이펙트 함수 설정 (동적 반환값 생성)
        
        Args:
            func: (*args, **kwargs) -> Result를 반환하는 함수
            
        Example:
            def dynamic_user_response(user_id: str) -> Result[User, str]:
                if user_id == "123":
                    return Success(User(id="123", name="Test User"))
                else:
                    return Failure("User not found")
            
            mocker.side_effect(dynamic_user_response)
        """
        self._side_effect_func = func
        return self
    
    async def __call__(self, *args, **kwargs) -> Result:
        """Mock 함수가 호출될 때 실행되는 로직"""
        self.call_count += 1
        self.call_args_history.append(args)
        self.call_kwargs_history.append(kwargs)
        
        # 사이드 이펙트 함수가 있는 경우 우선 실행
        if self._side_effect_func:
            result = self._side_effect_func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        
        # 순차적 반환이 설정된 경우
        if self._return_sequence:
            if self._sequence_index < len(self._return_sequence):
                result = self._return_sequence[self._sequence_index]
                self._sequence_index += 1
                return result
            else:
                # 시퀀스가 끝난 경우 마지막 결과 반복
                return self._return_sequence[-1] if self._return_sequence else Failure("Mock sequence exhausted")
        
        # 단일 반환값이 설정된 경우
        if self._return_results:
            return self._return_results[0]
        
        # 아무것도 설정되지 않은 경우 기본 에러
        return Failure(f"No mock result configured for {self.method_name}")
    
    def assert_called(self):
        """한 번 이상 호출되었는지 검증"""
        assert self.call_count > 0, f"{self.method_name} was not called"
    
    def assert_not_called(self):
        """호출되지 않았는지 검증"""
        assert self.call_count == 0, f"{self.method_name} was called {self.call_count} times"
    
    def assert_called_once(self):
        """정확히 한 번 호출되었는지 검증"""
        assert self.call_count == 1, f"Expected 1 call, got {self.call_count}"
    
    def assert_called_with(self, *args, **kwargs):
        """마지막 호출의 인자 검증"""
        assert self.call_count > 0, f"{self.method_name} was not called"
        last_args = self.call_args_history[-1]
        last_kwargs = self.call_kwargs_history[-1]
        assert last_args == args and last_kwargs == kwargs, \
            f"Expected call with {args}, {kwargs}, got {last_args}, {last_kwargs}"
    
    def assert_called_once_with(self, *args, **kwargs):
        """정확히 한 번 호출되고 인자가 일치하는지 검증"""
        self.assert_called_once()
        self.assert_called_with(*args, **kwargs)
    
    def reset_mock(self):
        """Mock 상태 초기화"""
        self.call_count = 0
        self.call_args_history.clear()
        self.call_kwargs_history.clear()
        self._sequence_index = 0

@contextmanager
def mock_result_service(service_path: str, method_name: str):
    """
    Result 패턴 서비스 모킹 컨텍스트 매니저
    
    Args:
        service_path: 서비스 클래스 경로
        method_name: 모킹할 메서드 이름
        
    Example:
        with mock_result_service("services.user_service", "get_user_async") as mock_svc:
            mock_svc.return_success(User(id="123"))
            result = await user_service.get_user_async("123")
            assert_result_success(result, User)
    """
    mocker = ResultServiceMocker(service_path, method_name)
    
    with patch(mocker.full_path, new=mocker):
        yield mocker
```

### 1.2 AsyncResult 모킹 헬퍼

#### 구현 사양
```python
class AsyncResultMocker:
    """비동기 Result 작업 전용 모킹 클래스"""
    
    def __init__(self, operation_name: str = "test_operation"):
        self.operation_name = operation_name
        self._delay_ms: float = 0
        self._should_timeout: bool = False
        self._timeout_seconds: float = 1.0
    
    def with_delay(self, delay_ms: float) -> "AsyncResultMocker":
        """비동기 작업 지연 시뮬레이션"""
        self._delay_ms = delay_ms
        return self
    
    def with_timeout(self, timeout_seconds: float = 1.0) -> "AsyncResultMocker":
        """타임아웃 시뮬레이션"""
        self._should_timeout = True
        self._timeout_seconds = timeout_seconds
        return self
    
    async def create_async_result(self, result: Result) -> Result:
        """비동기 Result 생성"""
        if self._delay_ms > 0:
            await asyncio.sleep(self._delay_ms / 1000.0)
        
        if self._should_timeout:
            await asyncio.sleep(self._timeout_seconds + 0.1)
        
        return result

def create_test_mono_result(result: Result, delay_ms: float = 0) -> MonoResult:
    """테스트용 MonoResult 생성"""
    async def test_async_func():
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        return result
    
    return MonoResult(test_async_func)

def create_test_flux_result(results: List[Result]) -> FluxResult:
    """테스트용 FluxResult 생성"""
    return FluxResult.from_results(results)

# 편의 함수들
def success_mono(value: Any, delay_ms: float = 0) -> MonoResult:
    """성공 MonoResult 생성"""
    return create_test_mono_result(Success(value), delay_ms)

def error_mono(error: Any, delay_ms: float = 0) -> MonoResult:
    """에러 MonoResult 생성"""
    return create_test_mono_result(Failure(error), delay_ms)

def mixed_flux(success_values: List[Any], error_values: List[Any]) -> FluxResult:
    """성공/에러 혼합 FluxResult 생성"""
    results = []
    results.extend([Success(v) for v in success_values])
    results.extend([Failure(e) for e in error_values])
    return FluxResult.from_results(results)
```

---

## 🧪 2. 검증 헬퍼 함수 (`assertions.py`)

### 2.1 Result 검증 함수들

#### 구현 사양
```python
from typing import Type, TypeVar, Any, List, Callable, Optional
import pytest
from rfs.core.result import Result, Success, Failure

T = TypeVar('T')
E = TypeVar('E')

def assert_result_success(
    result: Result[T, E], 
    expected_type: Optional[Type[T]] = None,
    expected_value: Optional[T] = None
):
    """
    Result가 성공인지 검증
    
    Args:
        result: 검증할 Result
        expected_type: 성공 값의 예상 타입 (옵션)
        expected_value: 성공 값의 예상 값 (옵션)
        
    Example:
        result = Success("test")
        assert_result_success(result, str, "test")
    """
    assert result.is_success(), f"Expected success, got failure: {result.unwrap_error()}"
    
    success_value = result.unwrap()
    
    if expected_type is not None:
        assert isinstance(success_value, expected_type), \
            f"Expected {expected_type.__name__}, got {type(success_value).__name__}"
    
    if expected_value is not None:
        assert success_value == expected_value, \
            f"Expected {expected_value}, got {success_value}"

def assert_result_failure(
    result: Result[T, E],
    expected_error_type: Optional[Type[E]] = None,
    expected_error_value: Optional[E] = None,
    error_message_contains: Optional[str] = None
):
    """
    Result가 실패인지 검증
    
    Args:
        result: 검증할 Result
        expected_error_type: 에러의 예상 타입 (옵션)
        expected_error_value: 에러의 예상 값 (옵션)
        error_message_contains: 에러 메시지에 포함되어야 할 문자열 (옵션)
        
    Example:
        result = Failure(APIError.not_found("User"))
        assert_result_failure(result, APIError, error_message_contains="not found")
    """
    assert result.is_failure(), f"Expected failure, got success: {result.unwrap()}"
    
    error_value = result.unwrap_error()
    
    if expected_error_type is not None:
        assert isinstance(error_value, expected_error_type), \
            f"Expected {expected_error_type.__name__}, got {type(error_value).__name__}"
    
    if expected_error_value is not None:
        assert error_value == expected_error_value, \
            f"Expected {expected_error_value}, got {error_value}"
    
    if error_message_contains is not None:
        error_str = str(error_value)
        assert error_message_contains.lower() in error_str.lower(), \
            f"Expected error message to contain '{error_message_contains}', got '{error_str}'"

def assert_result_type(result: Result[T, E], success_type: Type[T], error_type: Type[E]):
    """Result의 제네릭 타입 검증 (타입 힌트용)"""
    if result.is_success():
        assert isinstance(result.unwrap(), success_type)
    else:
        assert isinstance(result.unwrap_error(), error_type)
```

### 2.2 MonoResult/FluxResult 전용 검증

#### 구현 사양
```python
import time
from typing import List, Callable, Awaitable

async def assert_mono_result_success(
    mono_result: MonoResult[T, E],
    expected_type: Optional[Type[T]] = None,
    expected_value: Optional[T] = None
):
    """MonoResult 성공 검증"""
    result = await mono_result.to_result()
    assert_result_success(result, expected_type, expected_value)

async def assert_mono_result_failure(
    mono_result: MonoResult[T, E],
    expected_error_type: Optional[Type[E]] = None,
    expected_error_value: Optional[E] = None
):
    """MonoResult 실패 검증"""
    result = await mono_result.to_result()
    assert_result_failure(result, expected_error_type, expected_error_value)

async def assert_mono_result_timeout(
    mono_result: MonoResult[T, E],
    timeout_seconds: float,
    tolerance_percent: float = 10.0
):
    """
    MonoResult 타임아웃 검증
    
    Args:
        mono_result: 검증할 MonoResult
        timeout_seconds: 예상 타임아웃 시간
        tolerance_percent: 허용 오차 비율 (기본 10%)
    """
    start_time = time.time()
    result = await mono_result.to_result()
    elapsed_time = time.time() - start_time
    
    # 타임아웃이 발생했는지 확인
    assert result.is_failure(), "Expected timeout failure"
    error_message = str(result.unwrap_error()).lower()
    assert "timeout" in error_message, f"Expected timeout error, got: {result.unwrap_error()}"
    
    # 타임아웃 시간 검증 (허용 오차 내)
    tolerance = timeout_seconds * (tolerance_percent / 100.0)
    min_time = timeout_seconds - tolerance
    max_time = timeout_seconds + tolerance
    
    assert min_time <= elapsed_time <= max_time, \
        f"Expected timeout around {timeout_seconds}s, got {elapsed_time:.3f}s"

def assert_flux_result_stats(
    flux_result: FluxResult[T, E],
    expected_total: int,
    expected_success: int,
    expected_failures: int
):
    """FluxResult 통계 검증"""
    assert flux_result.count_total() == expected_total, \
        f"Expected total {expected_total}, got {flux_result.count_total()}"
    
    assert flux_result.count_success() == expected_success, \
        f"Expected success {expected_success}, got {flux_result.count_success()}"
    
    assert flux_result.count_failures() == expected_failures, \
        f"Expected failures {expected_failures}, got {flux_result.count_failures()}"

def assert_flux_result_success_rate(
    flux_result: FluxResult[T, E],
    expected_rate: float,
    tolerance: float = 0.01
):
    """FluxResult 성공률 검증"""
    actual_rate = flux_result.success_rate()
    assert abs(actual_rate - expected_rate) <= tolerance, \
        f"Expected success rate {expected_rate:.2%}, got {actual_rate:.2%}"

async def assert_flux_result_all_success(
    flux_result: FluxResult[T, E],
    expected_values: Optional[List[T]] = None
):
    """FluxResult 모든 결과가 성공인지 검증"""
    assert flux_result.is_all_success(), "Expected all results to be successful"
    
    if expected_values is not None:
        success_values = await flux_result.collect_success_values().to_result()
        assert success_values.is_success(), "Failed to collect success values"
        
        actual_values = success_values.unwrap()
        assert actual_values == expected_values, \
            f"Expected values {expected_values}, got {actual_values}"

def assert_flux_result_any_failure(flux_result: FluxResult[T, E]):
    """FluxResult에 실패가 있는지 검증"""
    assert flux_result.is_any_failure(), "Expected at least one failure"

async def assert_flux_result_parallel_performance(
    flux_creation_func: Callable[[], Awaitable[FluxResult[T, E]]],
    sequential_time_ms: float,
    expected_speedup_ratio: float = 2.0
):
    """
    FluxResult 병렬 처리 성능 검증
    
    Args:
        flux_creation_func: FluxResult를 생성하는 비동기 함수
        sequential_time_ms: 순차 처리 시간 (밀리초)
        expected_speedup_ratio: 예상 성능 향상 비율
    """
    start_time = time.time()
    flux_result = await flux_creation_func()
    parallel_time = (time.time() - start_time) * 1000
    
    expected_max_time = sequential_time_ms / expected_speedup_ratio
    
    assert parallel_time <= expected_max_time, \
        f"Expected parallel processing to complete within {expected_max_time:.2f}ms, " \
        f"but took {parallel_time:.2f}ms"
```

---

## 🎯 3. 테스트 픽스처 (`fixtures.py`)

### 3.1 공통 테스트 픽스처

#### 구현 사양
```python
import pytest
from typing import Dict, Any, List
from dataclasses import dataclass
from rfs.core.result import Success, Failure
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult

@dataclass
class TestUser:
    """테스트용 사용자 모델"""
    id: str
    name: str
    email: str
    active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "active": self.active
        }

@dataclass
class TestAPIError:
    """테스트용 API 에러"""
    code: str
    message: str
    status_code: int = 500

# === 기본 테스트 데이터 ===

@pytest.fixture
def sample_user() -> TestUser:
    """샘플 사용자 데이터"""
    return TestUser(
        id="test-123",
        name="테스트 사용자",
        email="test@example.com",
        active=True
    )

@pytest.fixture
def sample_users() -> List[TestUser]:
    """샘플 사용자 리스트"""
    return [
        TestUser(id="1", name="Alice", email="alice@test.com"),
        TestUser(id="2", name="Bob", email="bob@test.com"),
        TestUser(id="3", name="Charlie", email="charlie@test.com"),
    ]

@pytest.fixture
def sample_api_error() -> TestAPIError:
    """샘플 API 에러"""
    return TestAPIError(
        code="USER_NOT_FOUND",
        message="사용자를 찾을 수 없습니다",
        status_code=404
    )

# === Result 픽스처 ===

@pytest.fixture
def success_result(sample_user: TestUser) -> Success[TestUser]:
    """성공 Result 픽스처"""
    return Success(sample_user)

@pytest.fixture
def failure_result(sample_api_error: TestAPIError) -> Failure[TestAPIError]:
    """실패 Result 픽스처"""
    return Failure(sample_api_error)

@pytest.fixture
def mixed_results(sample_users: List[TestUser], sample_api_error: TestAPIError) -> List[Result]:
    """성공/실패 혼합 Result 리스트"""
    return [
        Success(sample_users[0]),
        Failure(sample_api_error),
        Success(sample_users[1]),
        Success(sample_users[2]),
        Failure(TestAPIError("VALIDATION_ERROR", "Invalid data", 400))
    ]

# === MonoResult 픽스처 ===

@pytest.fixture
def success_mono_result(sample_user: TestUser) -> MonoResult[TestUser, TestAPIError]:
    """성공 MonoResult 픽스처"""
    return MonoResult.from_value(sample_user)

@pytest.fixture
def failure_mono_result(sample_api_error: TestAPIError) -> MonoResult[TestUser, TestAPIError]:
    """실패 MonoResult 픽스처"""
    return MonoResult.from_error(sample_api_error)

@pytest.fixture
def slow_mono_result(sample_user: TestUser) -> MonoResult[TestUser, TestAPIError]:
    """느린 MonoResult 픽스처 (1초 지연)"""
    async def slow_operation():
        await asyncio.sleep(1.0)
        return Success(sample_user)
    
    return MonoResult(slow_operation)

# === FluxResult 픽스처 ===

@pytest.fixture
def success_flux_result(sample_users: List[TestUser]) -> FluxResult[TestUser, TestAPIError]:
    """모두 성공하는 FluxResult 픽스처"""
    results = [Success(user) for user in sample_users]
    return FluxResult.from_results(results)

@pytest.fixture
def mixed_flux_result(mixed_results: List[Result]) -> FluxResult[TestUser, TestAPIError]:
    """성공/실패 혼합 FluxResult 픽스처"""
    return FluxResult.from_results(mixed_results)

@pytest.fixture
def failure_flux_result(sample_api_error: TestAPIError) -> FluxResult[TestUser, TestAPIError]:
    """모두 실패하는 FluxResult 픽스처"""
    errors = [sample_api_error] * 3
    results = [Failure(error) for error in errors]
    return FluxResult.from_results(results)

# === 성능 테스트 픽스처 ===

@pytest.fixture
def performance_test_data() -> Dict[str, Any]:
    """성능 테스트용 데이터"""
    return {
        "small_dataset": list(range(10)),
        "medium_dataset": list(range(100)),
        "large_dataset": list(range(1000)),
        "timeout_threshold_ms": 5000,
        "parallel_speedup_ratio": 3.0
    }

# === Mock 설정 픽스처 ===

@pytest.fixture
def mock_async_delay():
    """비동기 지연 시뮬레이션"""
    async def delay(ms: float):
        await asyncio.sleep(ms / 1000.0)
    
    return delay

@pytest.fixture
def result_mocker_factory():
    """ResultServiceMocker 팩토리"""
    def create_mocker(service_path: str, method_name: str) -> ResultServiceMocker:
        return ResultServiceMocker(service_path, method_name)
    
    return create_mocker
```

---

## 🛠️ 4. 테스트 데이터 생성기 (`generators.py`)

### 4.1 동적 테스트 데이터 생성

#### 구현 사양
```python
from typing import Generator, List, Callable, Any, Type, TypeVar
from dataclasses import dataclass, field
from enum import Enum
import random
import string
from datetime import datetime, timedelta

T = TypeVar('T')

class DataGeneratorConfig:
    """테스트 데이터 생성 설정"""
    def __init__(self):
        self.seed = 42  # 재현 가능한 랜덤 시드
        self.locale = "ko_KR"  # 로케일 설정
    
    def set_seed(self, seed: int):
        """랜덤 시드 설정"""
        self.seed = seed
        random.seed(seed)

class ResultTestDataGenerator:
    """Result 패턴 테스트 데이터 생성기"""
    
    def __init__(self, config: DataGeneratorConfig = None):
        self.config = config or DataGeneratorConfig()
        random.seed(self.config.seed)
    
    def generate_success_results(
        self,
        count: int,
        value_generator: Callable[[], T]
    ) -> List[Success[T]]:
        """성공 Result 리스트 생성"""
        return [Success(value_generator()) for _ in range(count)]
    
    def generate_failure_results(
        self,
        count: int,
        error_generator: Callable[[], Any]
    ) -> List[Failure[Any]]:
        """실패 Result 리스트 생성"""
        return [Failure(error_generator()) for _ in range(count)]
    
    def generate_mixed_results(
        self,
        total_count: int,
        success_ratio: float,
        value_generator: Callable[[], T],
        error_generator: Callable[[], Any]
    ) -> List[Result[T, Any]]:
        """
        성공/실패 혼합 Result 리스트 생성
        
        Args:
            total_count: 총 결과 개수
            success_ratio: 성공 비율 (0.0 ~ 1.0)
            value_generator: 성공 값 생성 함수
            error_generator: 에러 값 생성 함수
        """
        success_count = int(total_count * success_ratio)
        failure_count = total_count - success_count
        
        results = []
        results.extend(self.generate_success_results(success_count, value_generator))
        results.extend(self.generate_failure_results(failure_count, error_generator))
        
        # 순서를 섞음
        random.shuffle(results)
        return results
    
    def generate_performance_test_data(
        self,
        sizes: List[int],
        complexity_levels: List[str] = None
    ) -> Dict[str, List[Any]]:
        """
        성능 테스트용 데이터 생성
        
        Args:
            sizes: 데이터 크기 리스트
            complexity_levels: 복잡도 레벨 ("simple", "medium", "complex")
        """
        if complexity_levels is None:
            complexity_levels = ["simple", "medium", "complex"]
        
        test_data = {}
        
        for size in sizes:
            for level in complexity_levels:
                key = f"{level}_{size}"
                
                if level == "simple":
                    # 단순 문자열 데이터
                    test_data[key] = [f"item_{i}" for i in range(size)]
                elif level == "medium":
                    # 딕셔너리 데이터
                    test_data[key] = [
                        {"id": i, "value": f"value_{i}", "timestamp": datetime.now()}
                        for i in range(size)
                    ]
                elif level == "complex":
                    # 복잡한 중첩 구조
                    test_data[key] = [
                        {
                            "id": i,
                            "metadata": {
                                "tags": [f"tag_{j}" for j in range(3)],
                                "properties": {f"prop_{k}": f"val_{k}" for k in range(5)}
                            },
                            "created_at": datetime.now() - timedelta(hours=i)
                        }
                        for i in range(size)
                    ]
        
        return test_data

# === 도메인별 생성기 ===

class UserDataGenerator:
    """사용자 데이터 생성기"""
    
    @staticmethod
    def random_user() -> TestUser:
        """랜덤 사용자 생성"""
        user_id = ''.join(random.choices(string.digits, k=6))
        names = ["김철수", "이영희", "박민수", "정미영", "최준호", "한지영"]
        name = random.choice(names)
        email = f"user{user_id}@test.com"
        active = random.choice([True, True, True, False])  # 75% 활성 사용자
        
        return TestUser(id=user_id, name=name, email=email, active=active)
    
    @staticmethod
    def user_batch(count: int) -> List[TestUser]:
        """사용자 배치 생성"""
        return [UserDataGenerator.random_user() for _ in range(count)]
    
    @staticmethod
    def invalid_user() -> Dict[str, Any]:
        """유효하지 않은 사용자 데이터 생성"""
        invalid_patterns = [
            {"id": "", "name": "Valid Name", "email": "valid@test.com"},  # 빈 ID
            {"id": "123", "name": "", "email": "valid@test.com"},  # 빈 이름
            {"id": "123", "name": "Valid Name", "email": "invalid-email"},  # 잘못된 이메일
            {"id": "123", "name": "Valid Name"},  # 이메일 누락
        ]
        return random.choice(invalid_patterns)

class APIErrorGenerator:
    """API 에러 생성기"""
    
    ERROR_TEMPLATES = [
        {"code": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다", "status_code": 404},
        {"code": "VALIDATION_ERROR", "message": "입력값이 유효하지 않습니다", "status_code": 400},
        {"code": "UNAUTHORIZED", "message": "인증이 필요합니다", "status_code": 401},
        {"code": "FORBIDDEN", "message": "권한이 부족합니다", "status_code": 403},
        {"code": "INTERNAL_ERROR", "message": "내부 서버 오류", "status_code": 500},
        {"code": "TIMEOUT_ERROR", "message": "요청 시간이 초과되었습니다", "status_code": 504},
    ]
    
    @staticmethod
    def random_error() -> TestAPIError:
        """랜덤 API 에러 생성"""
        template = random.choice(APIErrorGenerator.ERROR_TEMPLATES)
        return TestAPIError(**template)
    
    @staticmethod
    def error_by_type(error_type: str) -> TestAPIError:
        """특정 타입의 에러 생성"""
        for template in APIErrorGenerator.ERROR_TEMPLATES:
            if template["code"].startswith(error_type.upper()):
                return TestAPIError(**template)
        
        # 기본 에러
        return TestAPIError(
            code="UNKNOWN_ERROR",
            message="알 수 없는 오류",
            status_code=500
        )

# === 생성기 팩토리 ===

class TestDataFactory:
    """테스트 데이터 팩토리"""
    
    def __init__(self, seed: int = 42):
        self.config = DataGeneratorConfig()
        self.config.set_seed(seed)
        self.result_generator = ResultTestDataGenerator(self.config)
        self.user_generator = UserDataGenerator()
        self.error_generator = APIErrorGenerator()
    
    def create_test_scenario(
        self,
        scenario_name: str,
        data_size: int = 10,
        success_ratio: float = 0.8
    ) -> Dict[str, Any]:
        """
        테스트 시나리오 데이터 생성
        
        Returns:
            Dict: 시나리오별 테스트 데이터
        """
        scenarios = {
            "user_management": {
                "valid_users": self.user_generator.user_batch(data_size),
                "invalid_users": [self.user_generator.invalid_user() for _ in range(3)],
                "mixed_results": self.result_generator.generate_mixed_results(
                    data_size,
                    success_ratio,
                    self.user_generator.random_user,
                    self.error_generator.random_error
                )
            },
            "api_errors": {
                "common_errors": [
                    self.error_generator.error_by_type("NOT_FOUND"),
                    self.error_generator.error_by_type("VALIDATION"),
                    self.error_generator.error_by_type("UNAUTHORIZED")
                ],
                "server_errors": [
                    self.error_generator.error_by_type("INTERNAL"),
                    self.error_generator.error_by_type("TIMEOUT")
                ]
            },
            "performance": self.result_generator.generate_performance_test_data(
                sizes=[10, 100, 1000],
                complexity_levels=["simple", "complex"]
            )
        }
        
        return scenarios.get(scenario_name, {})
```

---

## 📊 성능 및 품질 요구사항

### 성능 요구사항
- Mock 설정 오버헤드: <1ms per mock
- 테스트 데이터 생성 속도: >1000 items/second
- 검증 함수 실행 시간: <10ms per assertion
- 메모리 사용량: <50MB (1000개 테스트 데이터 기준)

### 품질 요구사항
- Mock 정확도: 99.9% (실제 서비스와 동일한 동작)
- 검증 함수 신뢰성: 100% (False positive/negative 0%)
- 테스트 데이터 다양성: 95% (Edge case 커버리지)
- 재현성: 100% (동일 시드로 동일 결과 생성)

### 확장성 요구사항
- 동시 테스트 실행: 100+ parallel tests
- 테스트 데이터 크기: 10,000+ items
- Mock 서비스 개수: 50+ services per test
- 커스텀 생성기: 플러그인 방식으로 확장 가능

---

**문서 상태**: 설계 완료, 구현 대기  
**다음 단계**: Phase 3 구현 시작 및 통합 테스트