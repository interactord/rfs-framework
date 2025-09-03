# 테스팅 가이드

RFS Framework의 Result 패턴을 위한 전용 테스팅 도구와 모범 사례를 설명합니다.

## 개요

### 핵심 테스팅 도구

- **ResultServiceMocker**: Result 패턴 전용 모킹 시스템
- **Assertion Functions**: Result/MonoResult/FluxResult 검증 함수들
- **Test Data Factory**: 테스트 데이터 생성 유틸리티
- **Performance Testing**: 성능 테스트 헬퍼 도구들

## 기본 설정

```python
import pytest
from rfs.testing.result_helpers import (
    assert_result_success,
    assert_result_failure, 
    mock_result_service,
    ResultTestDataFactory,
    result_test_context
)
```

## Result 패턴 Assertion 함수들

### 기본 Result 검증

```python
from rfs.core.result import Success, Failure

def test_basic_result_assertions():
    success_result = Success("test data")
    failure_result = Failure("error message")
    
    # 성공 검증
    assert_result_success(success_result)
    assert_result_success(success_result, expected_type=str)
    assert_result_value(success_result, "test data")
    
    # 실패 검증  
    assert_result_failure(failure_result)
    assert_result_error(failure_result, "error message")
    
    # 타입 검증
    assert_result_success(Success(42), expected_type=int)
    assert_result_failure(Failure(ValueError("invalid")), expected_error_type=ValueError)
```

### MonoResult 검증

```python
@pytest.mark.asyncio
async def test_mono_result_assertions():
    # 성공하는 MonoResult
    success_mono = MonoResult.from_result(Success("async data"))
    
    result = await success_mono.to_result()
    assert_mono_result_success(result)
    assert_mono_result_value(result, "async data")
    
    # 실패하는 MonoResult
    failure_mono = MonoResult.from_result(Failure("async error"))
    
    result = await failure_mono.to_result()
    assert_mono_result_failure(result)
    assert_mono_result_error(result, "async error")
```

### FluxResult 검증

```python
@pytest.mark.asyncio  
async def test_flux_result_assertions():
    # 테스트 데이터 준비
    test_data = ["item1", "item2", "item3", "item4"]
    
    # 일부 성공, 일부 실패하는 처리 함수
    async def process_item(item: str) -> Result[str, str]:
        if item == "item2":
            return Failure(f"Failed to process {item}")
        return Success(f"processed_{item}")
    
    # FluxResult 생성 및 실행
    flux_result = await FluxResult.from_iterable_async(test_data, process_item)
    
    # FluxResult 검증
    assert_flux_success_count(flux_result, 3)  # 3개 성공
    assert_flux_failure_count(flux_result, 1)  # 1개 실패
    assert_flux_total_count(flux_result, 4)    # 총 4개
    assert_flux_success_rate(flux_result, 0.75) # 75% 성공률
    
    # 성공한 값들 검증
    expected_values = ["processed_item1", "processed_item3", "processed_item4"]
    assert_flux_success_values(flux_result, expected_values)
```

## 서비스 모킹 시스템

### 기본 서비스 모킹

```python
from rfs.testing.result_helpers import mock_result_service, ResultServiceMocker

class UserService:
    async def get_user(self, user_id: str) -> Result[dict, str]:
        # 실제 구현에서는 데이터베이스 호출 등
        pass
    
    async def create_user(self, user_data: dict) -> Result[dict, str]:
        pass

@pytest.mark.asyncio
async def test_user_service_mocking():
    # 컨텍스트 매니저 방식
    with mock_result_service("user_service", "get_user") as mock_svc:
        # 성공 응답 설정
        mock_svc.return_success({"id": "123", "name": "Test User"})
        
        # 실제 서비스 호출 (모킹됨)
        service = UserService()
        result = await service.get_user("123")
        
        # 검증
        assert_result_success(result)
        assert_result_value(result, {"id": "123", "name": "Test User"})
        mock_svc.assert_called_once_with("123")

@pytest.mark.asyncio        
async def test_user_service_failure_mocking():
    with mock_result_service("user_service", "get_user") as mock_svc:
        # 실패 응답 설정
        mock_svc.return_failure("User not found")
        
        service = UserService()
        result = await service.get_user("nonexistent")
        
        assert_result_failure(result)
        assert_result_error(result, "User not found")
        mock_svc.assert_called_once_with("nonexistent")
```

### 고급 모킹 패턴

```python
@pytest.mark.asyncio
async def test_conditional_mocking():
    """조건부 응답 모킹"""
    
    def mock_behavior(user_id: str) -> Result[dict, str]:
        if user_id == "admin":
            return Success({"id": user_id, "role": "admin"})
        elif user_id == "invalid":
            return Failure("Invalid user ID")
        else:
            return Success({"id": user_id, "role": "user"})
    
    with mock_result_service("user_service", "get_user") as mock_svc:
        mock_svc.side_effect = mock_behavior
        
        service = UserService()
        
        # 관리자 사용자
        result = await service.get_user("admin")
        assert_result_success(result)
        assert result.unwrap()["role"] == "admin"
        
        # 일반 사용자  
        result = await service.get_user("user123")
        assert_result_success(result)
        assert result.unwrap()["role"] == "user"
        
        # 잘못된 사용자
        result = await service.get_user("invalid")
        assert_result_failure(result)

@pytest.mark.asyncio
async def test_sequential_responses():
    """순차적 응답 모킹"""
    
    with mock_result_service("user_service", "get_user") as mock_svc:
        # 첫 번째 호출은 성공, 두 번째는 실패
        mock_svc.return_success_then_failure(
            success_value={"id": "123", "name": "User"},
            failure_value="Service temporarily unavailable"
        )
        
        service = UserService()
        
        # 첫 번째 호출 - 성공
        result1 = await service.get_user("123")
        assert_result_success(result1)
        
        # 두 번째 호출 - 실패
        result2 = await service.get_user("123") 
        assert_result_failure(result2)
        
        assert mock_svc.call_count == 2
```

### 클래스 기반 모킹

```python
def test_class_based_mocking():
    """클래스 기반 세밀한 모킹 제어"""
    
    mocker = ResultServiceMocker()
    
    # 여러 메서드 모킹 설정
    mocker.mock_method("user_service", "get_user", Success({"id": "123"}))
    mocker.mock_method("user_service", "create_user", Success({"id": "456", "created": True}))
    mocker.mock_method("email_service", "send_email", Success({"sent": True}))
    
    with mocker:
        # 모든 서비스 호출이 모킹됨
        user_result = user_service.get_user("123")
        create_result = user_service.create_user({"name": "New User"})
        email_result = email_service.send_email("test@example.com", "Hello")
        
        assert_result_success(user_result)
        assert_result_success(create_result)
        assert_result_success(email_result)
    
    # 호출 검증
    mocker.assert_method_called("user_service", "get_user", "123")
    mocker.assert_method_call_count("email_service", "send_email", 1)
```

## 테스트 데이터 생성

### 기본 테스트 데이터 팩토리

```python
from rfs.testing.result_helpers import ResultTestDataFactory

def test_data_factory_usage():
    factory = ResultTestDataFactory()
    
    # 기본 Result 객체 생성
    success_results = factory.create_success_results(
        values=["data1", "data2", "data3"]
    )
    
    failure_results = factory.create_failure_results(
        errors=["error1", "error2", "error3"]
    )
    
    # 검증
    for result in success_results:
        assert_result_success(result)
    
    for result in failure_results:
        assert_result_failure(result)
    
    # 혼합 결과 생성 (70% 성공, 30% 실패)
    mixed_results = factory.create_mixed_results(
        total_count=100,
        success_rate=0.7,
        success_factory=lambda i: f"success_{i}",
        failure_factory=lambda i: f"error_{i}"
    )
    
    successful = [r for r in mixed_results if r.is_success()]
    failed = [r for r in mixed_results if r.is_failure()]
    
    assert len(successful) == 70
    assert len(failed) == 30
```

### 도메인별 테스트 데이터

```python
class UserTestDataFactory(ResultTestDataFactory):
    def create_user_data(self, user_id: str = None) -> dict:
        return {
            "id": user_id or f"user_{self.sequence()}",
            "name": f"Test User {self.sequence()}",
            "email": f"user{self.sequence()}@example.com",
            "created_at": "2025-09-03T15:30:00Z",
            "active": True
        }
    
    def create_user_success_results(self, count: int = 5) -> List[Result[dict, str]]:
        return [
            Success(self.create_user_data()) 
            for _ in range(count)
        ]
    
    def create_user_failure_scenarios(self) -> List[Result[dict, str]]:
        return [
            Failure("User not found"),
            Failure("Invalid user ID format"),
            Failure("Database connection failed"),
            Failure("Permission denied"),
            Failure("User account suspended")
        ]

def test_domain_specific_factory():
    factory = UserTestDataFactory()
    
    # 사용자 성공 데이터
    user_results = factory.create_user_success_results(3)
    
    for result in user_results:
        assert_result_success(result, expected_type=dict)
        user_data = result.unwrap()
        assert "id" in user_data
        assert "name" in user_data
        assert "email" in user_data
    
    # 실패 시나리오
    failure_results = factory.create_user_failure_scenarios()
    
    for result in failure_results:
        assert_result_failure(result)
```

## 성능 테스팅

### 기본 성능 측정

```python
from rfs.testing.result_helpers import PerformanceTestHelper
import asyncio

@pytest.mark.asyncio
async def test_operation_performance():
    """작업 성능 측정"""
    
    perf_helper = PerformanceTestHelper()
    
    async def test_operation():
        # 테스트할 작업
        await asyncio.sleep(0.1)  # 100ms 시뮬레이션
        return Success("operation completed")
    
    # 성능 측정
    results = await perf_helper.measure_async_operation(
        operation=test_operation,
        iterations=10,
        max_concurrent=3
    )
    
    # 성능 검증
    assert results.average_duration_ms >= 100  # 최소 100ms
    assert results.average_duration_ms <= 200  # 최대 200ms
    assert results.success_rate == 1.0         # 100% 성공
    assert results.total_iterations == 10
    
    print(f"평균 처리시간: {results.average_duration_ms:.2f}ms")
    print(f"95백분위수: {results.p95_duration_ms:.2f}ms")
    print(f"최대 처리시간: {results.max_duration_ms:.2f}ms")

@pytest.mark.asyncio
async def test_load_testing():
    """부하 테스트"""
    
    perf_helper = PerformanceTestHelper()
    
    async def load_test_operation():
        # 실제 서비스 호출 시뮬레이션
        await asyncio.sleep(0.05)  # 50ms
        
        # 90% 성공률 시뮬레이션
        import random
        if random.random() < 0.9:
            return Success({"processed": True})
        else:
            return Failure("Service temporarily unavailable")
    
    # 높은 동시성으로 부하 테스트
    results = await perf_helper.load_test(
        operation=load_test_operation,
        total_requests=1000,
        concurrent_requests=50,
        duration_seconds=30
    )
    
    # 부하 테스트 결과 검증
    assert results.requests_per_second >= 100  # 최소 100 RPS
    assert results.success_rate >= 0.85        # 85% 이상 성공률
    assert results.p95_duration_ms <= 100     # 95백분위수 100ms 이하
    
    print(f"RPS: {results.requests_per_second:.2f}")
    print(f"성공률: {results.success_rate:.2%}")
    print(f"평균 지연시간: {results.average_duration_ms:.2f}ms")
```

### 메모리 사용량 테스트

```python
@pytest.mark.asyncio
async def test_memory_usage():
    """메모리 사용량 테스트"""
    
    perf_helper = PerformanceTestHelper()
    
    # 대량 데이터 처리 시뮬레이션
    async def memory_intensive_operation():
        large_data = ["item"] * 10000  # 큰 데이터셋
        
        flux_result = await FluxResult.from_iterable_async(
            large_data, 
            lambda item: Success(f"processed_{item}")
        )
        
        return await flux_result.collect_results()
    
    memory_usage = await perf_helper.measure_memory_usage(
        operation=memory_intensive_operation,
        iterations=5
    )
    
    # 메모리 사용량 검증
    assert memory_usage.peak_memory_mb <= 100    # 100MB 이하
    assert memory_usage.memory_growth_mb <= 10   # 증가량 10MB 이하
    
    print(f"최대 메모리 사용량: {memory_usage.peak_memory_mb:.2f}MB")
    print(f"메모리 증가량: {memory_usage.memory_growth_mb:.2f}MB")
```

## 통합 테스트 컨텍스트

### 전체 테스트 환경 설정

```python
from rfs.testing.result_helpers import result_test_context

@pytest.mark.asyncio
async def test_complete_workflow():
    """완전한 워크플로우 통합 테스트"""
    
    async with result_test_context() as ctx:
        # 테스트 환경 자동 설정
        ctx.setup_logging(level="DEBUG")
        ctx.setup_metrics_collection()
        ctx.setup_service_mocks({
            "user_service.get_user": Success({"id": "123", "name": "Test User"}),
            "email_service.send_email": Success({"sent": True}),
            "audit_service.log_action": Success({"logged": True})
        })
        
        # 실제 비즈니스 로직 테스트
        result = await complete_user_registration_workflow({
            "name": "New User",
            "email": "newuser@example.com"
        })
        
        # 결과 검증
        assert_result_success(result)
        
        # 서비스 호출 검증
        ctx.assert_service_called("user_service.get_user")
        ctx.assert_service_called("email_service.send_email")
        ctx.assert_service_called("audit_service.log_action")
        
        # 메트릭 검증
        metrics = ctx.get_collected_metrics()
        assert metrics["user_registration_success"] >= 1
```

## 테스트 마커와 분류

### 커스텀 pytest 마커

```python
import pytest

# 테스트 마커 정의
result_test = pytest.mark.result_test           # Result 패턴 테스트
mono_test = pytest.mark.mono_test               # MonoResult 테스트  
flux_test = pytest.mark.flux_test               # FluxResult 테스트
performance_test = pytest.mark.performance_test # 성능 테스트

@result_test
def test_basic_result_operations():
    """기본 Result 연산 테스트"""
    pass

@mono_test
@pytest.mark.asyncio
async def test_mono_result_chaining():
    """MonoResult 체이닝 테스트"""
    pass

@flux_test  
@pytest.mark.asyncio
async def test_batch_processing():
    """배치 처리 테스트"""
    pass

@performance_test
@pytest.mark.asyncio
async def test_high_load_scenario():
    """고부하 시나리오 테스트"""
    pass
```

### 테스트 실행 명령

```bash
# Result 패턴 테스트만 실행
pytest -m result_test

# 성능 테스트 제외하고 실행
pytest -m "not performance_test"

# 비동기 테스트만 실행
pytest -m "mono_test or flux_test"

# 커버리지와 함께 실행
pytest --cov=rfs.testing --cov-report=html
```

## 모범 사례

### 1. 테스트 구조화

```python
class TestUserService:
    """사용자 서비스 테스트 클래스"""
    
    @pytest.fixture
    def user_factory(self):
        return UserTestDataFactory()
    
    @pytest.fixture  
    def mock_dependencies(self):
        return {
            "database.get_user": Success({"id": "123"}),
            "cache.get_user": Failure("Cache miss"),
            "audit.log_access": Success({"logged": True})
        }
    
    @result_test
    def test_user_creation_success(self, user_factory, mock_dependencies):
        """사용자 생성 성공 시나리오"""
        pass
    
    @result_test
    def test_user_creation_failure(self, user_factory, mock_dependencies):
        """사용자 생성 실패 시나리오"""  
        pass
    
    @performance_test
    @pytest.mark.asyncio
    async def test_bulk_user_processing(self, user_factory):
        """대량 사용자 처리 성능 테스트"""
        pass
```

### 2. 에러 시나리오 테스팅

```python
@pytest.mark.parametrize("error_scenario", [
    "network_timeout", 
    "database_connection_failed",
    "invalid_input_data",
    "insufficient_permissions",
    "rate_limit_exceeded"
])
@pytest.mark.asyncio
async def test_error_handling_scenarios(error_scenario):
    """다양한 에러 시나리오 테스트"""
    
    error_configs = {
        "network_timeout": Failure("Network timeout after 30s"),
        "database_connection_failed": Failure("Cannot connect to database"),
        "invalid_input_data": Failure("Input validation failed"),
        "insufficient_permissions": Failure("Access denied"),
        "rate_limit_exceeded": Failure("Rate limit exceeded, try again later")
    }
    
    expected_error = error_configs[error_scenario]
    
    with mock_result_service("external_service", "call") as mock_svc:
        mock_svc.return_failure(expected_error.unwrap_error())
        
        result = await call_external_service_with_retry()
        
        assert_result_failure(result)
        assert expected_error.unwrap_error() in result.unwrap_error()
```

### 3. 통합 테스트 패턴

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_user_journey():
    """사용자 여정 종단간 테스트"""
    
    async with result_test_context() as ctx:
        # 1. 사용자 등록
        registration_result = await register_new_user({
            "email": "testuser@example.com",
            "name": "Test User"
        })
        assert_result_success(registration_result)
        user_id = registration_result.unwrap()["user_id"]
        
        # 2. 이메일 인증
        verification_result = await verify_email(user_id, "verification_token")
        assert_result_success(verification_result)
        
        # 3. 프로필 업데이트
        profile_result = await update_user_profile(user_id, {
            "bio": "Test user bio",
            "preferences": {"notifications": True}
        })
        assert_result_success(profile_result)
        
        # 4. 사용자 데이터 조회
        user_result = await get_user_with_profile(user_id)
        assert_result_success(user_result)
        
        user_data = user_result.unwrap()
        assert user_data["email"] == "testuser@example.com"
        assert user_data["verified"] == True
        assert user_data["bio"] == "Test user bio"
        
        # 메트릭 검증
        metrics = ctx.get_collected_metrics()
        assert metrics["user_registration_success"] == 1
        assert metrics["email_verification_success"] == 1
        assert metrics["profile_update_success"] == 1
```

## 추가 자료

- [Result 패턴 가이드](01-core-patterns.md)
- [MonoResult 가이드](20-monoresult-guide.md) 
- [모니터링 가이드](22-monitoring-observability.md)