# AsyncResult 테스팅 API

RFS Framework의 AsyncResult 테스팅 유틸리티 API 레퍼런스입니다.

## 모듈 임포트

```python
from rfs.testing.async_result_testing import (
    AsyncResultTestUtils,
    AsyncResultMockBuilder,
    AsyncResultPerformanceTester,
    create_test_async_result,
    mock_async_success,
    mock_async_failure
)
```

## 주요 클래스

### AsyncResultTestUtils

AsyncResult 검증을 위한 유틸리티 클래스입니다.

```python
class AsyncResultTestUtils:
    """AsyncResult 테스팅을 위한 유틸리티 클래스"""
```

#### 정적 메서드

##### assert_success

AsyncResult가 성공 상태인지 검증합니다.

```python
@staticmethod
async def assert_success(
    async_result: AsyncResult[T, E],
    expected_value: Optional[T] = None,
    value_matcher: Optional[Callable[[T], bool]] = None,
    timeout: Optional[float] = None
) -> T
```

**매개변수:**
- `async_result`: 검증할 AsyncResult
- `expected_value`: 기대되는 값 (선택사항)
- `value_matcher`: 값 검증 함수 (선택사항)
- `timeout`: 타임아웃 시간 (초, 선택사항)

**반환값:**
- 성공한 경우 unwrapped 값

**사용 예시:**

```python
import pytest

class TestUserService:
    @pytest.mark.asyncio
    async def test_get_user_success(self):
        # Given
        user_data = {"id": 123, "name": "테스트 사용자"}
        user_result = await get_user(123)
        
        # When & Then
        actual_user = await AsyncResultTestUtils.assert_success(
            user_result,
            expected_value=user_data
        )
        
        assert actual_user == user_data
    
    @pytest.mark.asyncio
    async def test_user_validation_with_matcher(self):
        # Given
        user_result = await create_user({"name": "신규사용자", "email": "test@example.com"})
        
        # When & Then - 커스텀 매처 사용
        user = await AsyncResultTestUtils.assert_success(
            user_result,
            value_matcher=lambda u: u["id"] > 0 and "@" in u["email"]
        )
        
        assert user["name"] == "신규사용자"
```

##### assert_failure

AsyncResult가 실패 상태인지 검증합니다.

```python
@staticmethod
async def assert_failure(
    async_result: AsyncResult[T, E],
    expected_error: Optional[E] = None,
    error_matcher: Optional[Callable[[E], bool]] = None,
    timeout: Optional[float] = None
) -> E
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_invalid_user_id(self):
    # Given
    invalid_result = await get_user(-1)
    
    # When & Then
    error = await AsyncResultTestUtils.assert_failure(
        invalid_result,
        error_matcher=lambda e: "invalid" in str(e).lower()
    )
    
    assert "사용자 ID가 유효하지 않습니다" in str(error)
```

##### assert_timeout

AsyncResult가 지정된 시간 내에 완료되는지 검증합니다.

```python
@staticmethod
async def assert_timeout(
    async_result: AsyncResult[T, E],
    max_duration_ms: float,
    min_duration_ms: float = 0
) -> bool
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_operation_performance(self):
    # Given
    start_time = time.time()
    result = await process_data(large_dataset)
    
    # When & Then - 5초 이내 완료되어야 함
    is_within_timeout = await AsyncResultTestUtils.assert_timeout(
        result, 
        max_duration_ms=5000
    )
    
    assert is_within_timeout
```

##### wait_for_condition

특정 조건이 만족될 때까지 대기합니다.

```python
@staticmethod
async def wait_for_condition(
    condition_func: Callable[[], Awaitable[bool]],
    timeout: float = 10.0,
    check_interval: float = 0.1
) -> bool
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_eventual_consistency(self):
    # Given
    await create_user(user_data)
    
    # When & Then - 데이터베이스 동기화 대기
    is_synced = await AsyncResultTestUtils.wait_for_condition(
        condition_func=lambda: check_user_exists_in_readonly_db(user_id),
        timeout=5.0,
        check_interval=0.5
    )
    
    assert is_synced
```

### AsyncResultMockBuilder

테스트용 AsyncResult Mock 객체를 생성하는 빌더 클래스입니다.

```python
class AsyncResultMockBuilder:
    """AsyncResult Mock 빌더 클래스"""
```

#### 정적 메서드

##### success

성공하는 AsyncResult Mock을 생성합니다.

```python
@staticmethod
def success(data: T, delay_ms: int = 0) -> 'MockAsyncResult[T, Any]'
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_success_scenario(self):
    # Given
    mock_data = {"result": "success", "value": 42}
    mock_result = AsyncResultMockBuilder.success(mock_data, delay_ms=100)
    
    # When
    result = await mock_result.build()
    
    # Then
    await AsyncResultTestUtils.assert_success(result, expected_value=mock_data)
```

##### failure

실패하는 AsyncResult Mock을 생성합니다.

```python
@staticmethod
def failure(error: E, delay_ms: int = 0) -> 'MockAsyncResult[Any, E]'
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_failure_scenario(self):
    # Given
    error_message = "네트워크 연결 실패"
    mock_result = AsyncResultMockBuilder.failure(error_message, delay_ms=50)
    
    # When
    result = await mock_result.build()
    
    # Then
    error = await AsyncResultTestUtils.assert_failure(result)
    assert error == error_message
```

##### delayed

지연을 가지는 AsyncResult Mock을 생성합니다.

```python
@staticmethod
def delayed(
    data: T, 
    delay_ms: int,
    jitter_ms: int = 0
) -> 'MockAsyncResult[T, Any]'
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_delayed_response(self):
    # Given - 500ms ± 100ms 지연
    mock_result = AsyncResultMockBuilder.delayed(
        {"data": "delayed"}, 
        delay_ms=500,
        jitter_ms=100
    )
    
    # When
    start_time = time.time()
    result = await mock_result.build()
    elapsed_ms = (time.time() - start_time) * 1000
    
    # Then
    await AsyncResultTestUtils.assert_success(result)
    assert 400 <= elapsed_ms <= 600  # 지연 시간 검증
```

##### intermittent_failure

간헐적으로 실패하는 AsyncResult Mock을 생성합니다.

```python
@staticmethod
def intermittent_failure(
    success_data: T,
    error_data: E,
    failure_rate: float = 0.5,
    delay_ms: int = 0
) -> 'MockAsyncResult[T, E]'
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_retry_mechanism(self):
    # Given - 30% 실패율
    mock_result = AsyncResultMockBuilder.intermittent_failure(
        success_data={"status": "ok"},
        error_data="일시적 장애",
        failure_rate=0.3
    )
    
    # When - 여러 번 시도
    results = []
    for _ in range(20):
        result = await mock_result.build()
        results.append(result.is_success())
    
    # Then - 약 70% 성공률 확인
    success_count = sum(results)
    assert 10 <= success_count <= 18  # 70% ± 20%
```

##### chain

여러 AsyncResult를 체인으로 연결하는 Mock을 생성합니다.

```python
@staticmethod
def chain(
    operations: List[Callable[[], AsyncResult[Any, Any]]],
    fail_at_step: Optional[int] = None
) -> 'MockAsyncResult[Any, Any]'
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_operation_chain(self):
    # Given
    step1 = lambda: AsyncResultMockBuilder.success("step1_result").build()
    step2 = lambda: AsyncResultMockBuilder.success("step2_result").build()
    step3 = lambda: AsyncResultMockBuilder.success("step3_result").build()
    
    mock_chain = AsyncResultMockBuilder.chain([step1, step2, step3])
    
    # When
    result = await mock_chain.build()
    
    # Then
    await AsyncResultTestUtils.assert_success(result)

@pytest.mark.asyncio
async def test_chain_failure_at_step(self):
    # Given - 2번째 단계에서 실패
    step1 = lambda: AsyncResultMockBuilder.success("step1_ok").build()
    step2 = lambda: AsyncResultMockBuilder.failure("step2_failed").build()
    step3 = lambda: AsyncResultMockBuilder.success("step3_ok").build()
    
    mock_chain = AsyncResultMockBuilder.chain([step1, step2, step3], fail_at_step=1)
    
    # When
    result = await mock_chain.build()
    
    # Then
    error = await AsyncResultTestUtils.assert_failure(result)
    assert "step2_failed" in str(error)
```

### AsyncResultPerformanceTester

AsyncResult의 성능을 측정하는 클래스입니다.

```python
class AsyncResultPerformanceTester:
    """AsyncResult 성능 테스팅 클래스"""
```

#### 정적 메서드

##### measure_operation

단일 작업의 성능을 측정합니다.

```python
@staticmethod
async def measure_operation(
    operation: Callable[[], Awaitable[AsyncResult[T, E]]],
    iterations: int = 100,
    warmup_iterations: int = 10,
    max_concurrency: int = 1
) -> PerformanceMetrics
```

**반환값:**
```python
@dataclass
class PerformanceMetrics:
    total_iterations: int
    success_count: int
    failure_count: int
    success_rate: float
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    throughput_per_second: float
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_user_service_performance(self):
    # Given
    async def user_operation():
        return await get_user_from_database(123)
    
    # When
    metrics = await AsyncResultPerformanceTester.measure_operation(
        user_operation,
        iterations=200,
        warmup_iterations=20
    )
    
    # Then
    assert metrics.success_rate >= 0.95  # 95% 이상 성공률
    assert metrics.p95_ms <= 100  # 95 퍼센타일이 100ms 이하
    assert metrics.throughput_per_second >= 50  # 초당 50개 이상 처리
```

##### benchmark_comparison

여러 작업의 성능을 비교합니다.

```python
@staticmethod
async def benchmark_comparison(
    operations: Dict[str, Callable[[], Awaitable[AsyncResult[Any, Any]]]],
    iterations: int = 100
) -> Dict[str, PerformanceMetrics]
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_cache_performance_comparison(self):
    # Given
    operations = {
        "with_cache": lambda: get_user_with_cache(123),
        "without_cache": lambda: get_user_without_cache(123),
        "memory_cache": lambda: get_user_memory_cache(123)
    }
    
    # When
    results = await AsyncResultPerformanceTester.benchmark_comparison(
        operations, 
        iterations=100
    )
    
    # Then
    cache_metrics = results["with_cache"]
    no_cache_metrics = results["without_cache"]
    
    # 캐시가 더 빨라야 함
    assert cache_metrics.avg_duration_ms < no_cache_metrics.avg_duration_ms
    # 캐시 성능이 최소 2배 이상 빨라야 함
    assert no_cache_metrics.avg_duration_ms / cache_metrics.avg_duration_ms >= 2.0
```

##### stress_test

부하 테스트를 수행합니다.

```python
@staticmethod
async def stress_test(
    operation: Callable[[], Awaitable[AsyncResult[T, E]]],
    concurrent_users: int,
    duration_seconds: int,
    ramp_up_seconds: int = 0
) -> StressTestResults
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_api_under_load(self):
    # Given
    async def api_call():
        return await process_user_request(sample_data)
    
    # When - 50명 동시 사용자, 60초간 테스트
    results = await AsyncResultPerformanceTester.stress_test(
        api_call,
        concurrent_users=50,
        duration_seconds=60,
        ramp_up_seconds=10
    )
    
    # Then
    assert results.success_rate >= 0.90  # 90% 이상 성공률
    assert results.avg_response_time_ms <= 500  # 평균 응답시간 500ms 이하
    assert results.errors_per_second <= 1.0  # 초당 에러 1개 이하
```

## 유틸리티 함수

### create_test_async_result

테스트용 AsyncResult를 간단히 생성합니다.

```python
def create_test_async_result(
    success_value: Optional[T] = None,
    failure_value: Optional[E] = None,
    delay_ms: int = 0
) -> AsyncResult[T, E]
```

**사용 예시:**

```python
@pytest.mark.asyncio
async def test_simple_success():
    # Given
    test_data = {"message": "테스트 성공"}
    result = create_test_async_result(success_value=test_data)
    
    # When & Then
    await AsyncResultTestUtils.assert_success(result, expected_value=test_data)

@pytest.mark.asyncio
async def test_simple_failure():
    # Given
    error_msg = "테스트 실패"
    result = create_test_async_result(failure_value=error_msg)
    
    # When & Then
    error = await AsyncResultTestUtils.assert_failure(result)
    assert error == error_msg
```

### mock_async_success

성공하는 AsyncResult Mock을 생성하는 단축 함수입니다.

```python
def mock_async_success(data: T, delay_ms: int = 0) -> AsyncResult[T, Any]
```

### mock_async_failure

실패하는 AsyncResult Mock을 생성하는 단축 함수입니다.

```python
def mock_async_failure(error: E, delay_ms: int = 0) -> AsyncResult[Any, E]
```

## 통합 테스트 예시

### 완전한 서비스 테스트

```python
import pytest
from unittest.mock import AsyncMock, patch
from rfs.testing.async_result_testing import *

class TestUserRegistrationService:
    @pytest.fixture
    async def user_service(self):
        return UserRegistrationService()
    
    @pytest.fixture
    def valid_user_data(self):
        return {
            "name": "홍길동",
            "email": "hong@example.com", 
            "password": "secure_password123",
            "phone": "010-1234-5678"
        }
    
    @pytest.mark.asyncio
    async def test_successful_registration(self, user_service, valid_user_data):
        """정상적인 사용자 등록 테스트"""
        # Given
        with patch('external_email_service.send_welcome_email') as mock_email:
            mock_email.return_value = mock_async_success({"status": "sent"})
            
            # When
            result = await user_service.register_user(valid_user_data)
            
            # Then
            user = await AsyncResultTestUtils.assert_success(
                result,
                value_matcher=lambda u: u["id"] > 0 and u["status"] == "active"
            )
            
            assert user["name"] == valid_user_data["name"]
            assert user["email"] == valid_user_data["email"]
            assert "password" not in user  # 비밀번호는 응답에 포함되지 않음
            mock_email.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_duplicate_email_failure(self, user_service, valid_user_data):
        """중복 이메일 등록 실패 테스트"""
        # Given - 먼저 사용자 등록
        await user_service.register_user(valid_user_data)
        
        # When - 같은 이메일로 다시 등록 시도
        duplicate_result = await user_service.register_user(valid_user_data)
        
        # Then
        error = await AsyncResultTestUtils.assert_failure(
            duplicate_result,
            error_matcher=lambda e: "이미 존재" in str(e)
        )
        assert "이메일" in str(error)
    
    @pytest.mark.asyncio
    async def test_external_service_failure_handling(self, user_service, valid_user_data):
        """외부 서비스 실패 처리 테스트"""
        # Given - 이메일 서비스 실패 시뮬레이션
        with patch('external_email_service.send_welcome_email') as mock_email:
            mock_email.return_value = mock_async_failure("이메일 서비스 오류")
            
            # When
            result = await user_service.register_user(valid_user_data)
            
            # Then - 사용자는 등록되지만 이메일 전송 실패 로그
            user = await AsyncResultTestUtils.assert_success(result)
            assert user["email_status"] == "pending"  # 이메일 재시도 대기
    
    @pytest.mark.asyncio
    async def test_registration_performance(self, user_service):
        """등록 성능 테스트"""
        # Given
        async def registration_operation():
            user_data = {
                "name": f"사용자{random.randint(1000, 9999)}",
                "email": f"user{random.randint(1000, 9999)}@test.com",
                "password": "password123",
                "phone": "010-0000-0000"
            }
            return await user_service.register_user(user_data)
        
        # When
        metrics = await AsyncResultPerformanceTester.measure_operation(
            registration_operation,
            iterations=50,
            max_concurrency=5
        )
        
        # Then
        assert metrics.success_rate >= 0.95
        assert metrics.avg_duration_ms <= 200  # 평균 200ms 이하
        assert metrics.p95_ms <= 500  # 95퍼센타일 500ms 이하

    @pytest.mark.asyncio 
    async def test_concurrent_registrations(self, user_service):
        """동시 등록 처리 테스트"""
        # Given - 여러 사용자 동시 등록
        user_count = 20
        registration_tasks = []
        
        for i in range(user_count):
            user_data = {
                "name": f"동시사용자{i}",
                "email": f"concurrent{i}@test.com",
                "password": "password123",
                "phone": f"010-{i:04d}-0000"
            }
            task = user_service.register_user(user_data)
            registration_tasks.append(task)
        
        # When - 모든 등록 작업 동시 실행
        results = await asyncio.gather(*registration_tasks, return_exceptions=True)
        
        # Then
        success_count = 0
        for result in results:
            if isinstance(result, AsyncResult):
                if (await result).is_success():
                    success_count += 1
        
        # 최소 95% 성공률
        assert success_count / user_count >= 0.95
    
    @pytest.mark.asyncio
    async def test_intermittent_database_failure(self, user_service, valid_user_data):
        """간헐적 데이터베이스 실패 처리 테스트"""
        # Given - DB 연결 간헐적 실패 시뮬레이션
        with patch('database.save_user') as mock_db:
            mock_db.return_value = AsyncResultMockBuilder.intermittent_failure(
                success_data={"id": 123, "status": "saved"},
                error_data="DB 연결 오류",
                failure_rate=0.3  # 30% 실패율
            ).build()
            
            # When - 재시도 로직 테스트 (최대 3회)
            success_count = 0
            total_attempts = 10
            
            for _ in range(total_attempts):
                try:
                    result = await user_service.register_user_with_retry(
                        valid_user_data, 
                        max_retries=3
                    )
                    if (await result).is_success():
                        success_count += 1
                except Exception:
                    pass
            
            # Then - 재시도 덕분에 높은 성공률
            success_rate = success_count / total_attempts
            assert success_rate >= 0.85  # 재시도로 85% 이상 성공률 달성
```

### 성능 회귀 테스트

```python
@pytest.mark.performance
class TestPerformanceRegression:
    """성능 회귀 테스트"""
    
    PERFORMANCE_BASELINES = {
        "user_lookup": {"p95_ms": 50, "success_rate": 0.99},
        "user_creation": {"p95_ms": 200, "success_rate": 0.98},
        "bulk_operation": {"throughput_per_second": 100}
    }
    
    @pytest.mark.asyncio
    async def test_user_lookup_performance_baseline(self):
        """사용자 조회 성능 기준선 테스트"""
        # Given
        baseline = self.PERFORMANCE_BASELINES["user_lookup"]
        
        async def lookup_operation():
            return await get_user_optimized(123)
        
        # When
        metrics = await AsyncResultPerformanceTester.measure_operation(
            lookup_operation,
            iterations=1000
        )
        
        # Then
        assert metrics.p95_ms <= baseline["p95_ms"], \
            f"P95 응답시간 회귀: {metrics.p95_ms}ms > {baseline['p95_ms']}ms"
        assert metrics.success_rate >= baseline["success_rate"], \
            f"성공률 회귀: {metrics.success_rate} < {baseline['success_rate']}"
```

---

이 API를 통해 AsyncResult의 동작을 철저히 테스트하고 성능을 검증할 수 있습니다. 자세한 사용 예시는 [AsyncResult Web Integration 가이드](../26-asyncresult-web-integration.md)를 참조하세요.