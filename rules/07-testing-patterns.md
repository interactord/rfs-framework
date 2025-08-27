# 테스트 패턴 가이드

## 개요

RFS Framework는 함수형 프로그래밍과 Result 패턴을 활용한 테스트 작성을 권장합니다. 모든 테스트는 부작용 없이 예측 가능하며, 격리되어 실행됩니다.

## 핵심 원칙

1. **Result 패턴 사용**: 예외 대신 Result로 실패 검증
2. **순수 함수 테스트**: 부작용 없는 함수 우선 테스트
3. **Given-When-Then**: 명확한 테스트 구조
4. **격리된 테스트**: 테스트 간 상태 공유 금지

## 테스트 구조

### Given-When-Then 패턴

```python
import pytest
from rfs.core.result import Success, Failure

def test_user_creation():
    """사용자 생성 테스트 - GWT 패턴"""
    
    # Given: 테스트 준비
    user_data = {
        "email": "test@example.com",
        "name": "Test User",
        "age": 25
    }
    repository = InMemoryUserRepository()
    service = UserService(repository)
    
    # When: 테스트 실행
    result = service.create_user(user_data)
    
    # Then: 결과 검증
    assert result.is_success()
    user = result.unwrap()
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert repository.count() == 1
```

### 테스트 명명 규칙

```python
class TestUserService:
    """UserService 테스트 스위트"""
    
    def test_create_user_with_valid_data_returns_success(self):
        """유효한 데이터로 사용자 생성 시 Success 반환"""
        pass
    
    def test_create_user_with_invalid_email_returns_failure(self):
        """잘못된 이메일로 사용자 생성 시 Failure 반환"""
        pass
    
    def test_update_user_when_not_found_returns_failure(self):
        """존재하지 않는 사용자 업데이트 시 Failure 반환"""
        pass
```

## Result 패턴 테스트

### Success/Failure 검증

```python
def test_result_success():
    """Success 케이스 테스트"""
    result = divide(10, 2)
    
    # Success 검증
    assert result.is_success()
    assert not result.is_failure()
    assert result.unwrap() == 5
    assert result.unwrap_or(0) == 5

def test_result_failure():
    """Failure 케이스 테스트"""
    result = divide(10, 0)
    
    # Failure 검증
    assert result.is_failure()
    assert not result.is_success()
    assert result.unwrap_error() == "Division by zero"
    assert result.unwrap_or(0) == 0

def test_result_chaining():
    """Result 체이닝 테스트"""
    result = Success(10)
        .map(lambda x: x * 2)
        .bind(lambda x: Success(x + 5) if x > 15 else Failure("Too small"))
        .map(lambda x: str(x))
    
    assert result.is_success()
    assert result.unwrap() == "25"
```

### 다중 Result 테스트

```python
from rfs.core.result import sequence, combine, partition

def test_sequence_all_success():
    """모든 Result가 성공인 경우"""
    results = [Success(1), Success(2), Success(3)]
    combined = sequence(results)
    
    assert combined.is_success()
    assert combined.unwrap() == [1, 2, 3]

def test_sequence_with_failure():
    """하나라도 실패인 경우"""
    results = [Success(1), Failure("error"), Success(3)]
    combined = sequence(results)
    
    assert combined.is_failure()
    assert combined.unwrap_error() == "error"

def test_partition():
    """성공과 실패 분리"""
    results = [Success(1), Failure("e1"), Success(2), Failure("e2")]
    successes, failures = partition(results)
    
    assert successes == [1, 2]
    assert failures == ["e1", "e2"]
```

## 비동기 테스트

### pytest-asyncio 사용

```python
import pytest
import asyncio
from rfs.core.result import AsyncResult

@pytest.mark.asyncio
async def test_async_operation():
    """비동기 작업 테스트"""
    # Given
    user_id = "123"
    
    # When
    result = await fetch_user_async(user_id)
    
    # Then
    assert result.is_success()
    user = result.unwrap()
    assert user.id == user_id

@pytest.mark.asyncio
async def test_async_result_chaining():
    """비동기 Result 체이닝"""
    result = await AsyncResult.from_value(10)
        .map_async(async_double)  # async def async_double(x): return x * 2
        .bind_async(async_validate)  # Result 반환하는 비동기 함수
        .map(lambda x: str(x))
    
    assert result.is_success()
    assert result.unwrap() == "20"
```

### 동시성 테스트

```python
@pytest.mark.asyncio
async def test_concurrent_operations():
    """동시 실행 테스트"""
    # Given
    user_ids = ["1", "2", "3", "4", "5"]
    
    # When - 동시에 5개 조회
    tasks = [fetch_user_async(id) for id in user_ids]
    results = await asyncio.gather(*tasks)
    
    # Then
    assert all(r.is_success() for r in results)
    users = [r.unwrap() for r in results]
    assert len(users) == 5
```

## 목(Mock) 객체 활용

### unittest.mock 사용

```python
from unittest.mock import Mock, patch

def test_with_mock_dependency():
    """목 객체로 의존성 테스트"""
    # Given - 목 객체 생성
    mock_repo = Mock(spec=UserRepository)
    mock_repo.find_by_email.return_value = Success(None)  # 중복 없음
    mock_repo.save.return_value = Success(user)
    
    mock_email = Mock(spec=EmailService)
    mock_email.send.return_value = Success(None)
    
    service = UserService(mock_repo, mock_email)
    
    # When
    result = service.create_user(user_data)
    
    # Then
    assert result.is_success()
    mock_repo.find_by_email.assert_called_once_with("test@example.com")
    mock_repo.save.assert_called_once()
    mock_email.send.assert_called_once()
```

### 부분 목 사용

```python
@patch('rfs.services.external_api.call')
def test_with_patched_external_call(mock_call):
    """외부 API 호출 패치"""
    # Given
    mock_call.return_value = {"status": "ok", "data": {...}}
    
    # When
    result = process_with_external_api(data)
    
    # Then
    assert result.is_success()
    mock_call.assert_called_with(expected_params)
```

## 픽스처(Fixture) 활용

### pytest 픽스처

```python
import pytest
from datetime import datetime

@pytest.fixture
def user():
    """테스트용 사용자 픽스처"""
    return User(
        id=UserId("test-123"),
        email=Email("test@example.com"),
        name="Test User",
        created_at=datetime.now()
    )

@pytest.fixture
def repository():
    """테스트용 레포지토리 픽스처"""
    return InMemoryUserRepository()

@pytest.fixture
def service(repository):
    """서비스 픽스처 - 의존성 주입"""
    email_service = MockEmailService()
    return UserService(repository, email_service)

def test_update_user(service, user):
    """픽스처를 활용한 테스트"""
    # Given
    service.repository.save(user)
    
    # When
    updated = user.with_name("Updated Name")
    result = service.update_user(updated)
    
    # Then
    assert result.is_success()
    assert result.unwrap().name == "Updated Name"
```

### 스코프별 픽스처

```python
@pytest.fixture(scope="session")
def database():
    """세션 레벨 데이터베이스 픽스처"""
    db = TestDatabase()
    db.migrate()
    yield db
    db.cleanup()

@pytest.fixture(scope="function")
def transaction(database):
    """함수 레벨 트랜잭션 픽스처"""
    tx = database.begin()
    yield tx
    tx.rollback()
```

## 파라미터화 테스트

### pytest.mark.parametrize

```python
@pytest.mark.parametrize("input,expected", [
    (0, Failure("Division by zero")),
    (1, Success(10)),
    (2, Success(5)),
    (-1, Success(-10)),
])
def test_divide_parametrized(input, expected):
    """파라미터화된 나누기 테스트"""
    result = divide(10, input)
    
    if expected.is_success():
        assert result.is_success()
        assert result.unwrap() == expected.unwrap()
    else:
        assert result.is_failure()
        assert result.unwrap_error() == expected.unwrap_error()

@pytest.mark.parametrize("email,is_valid", [
    ("user@example.com", True),
    ("user.name@example.co.uk", True),
    ("invalid", False),
    ("@example.com", False),
    ("user@", False),
])
def test_email_validation(email, is_valid):
    """이메일 검증 파라미터화 테스트"""
    result = validate_email(email)
    assert result.is_success() == is_valid
```

## 프로퍼티 기반 테스트

### Hypothesis 사용

```python
from hypothesis import given, strategies as st

@given(st.integers())
def test_addition_commutative(x):
    """덧셈의 교환 법칙"""
    assert add(x, 5) == add(5, x)

@given(st.lists(st.integers()))
def test_sort_idempotent(lst):
    """정렬의 멱등성"""
    sorted_once = sorted(lst)
    sorted_twice = sorted(sorted_once)
    assert sorted_once == sorted_twice

@given(
    st.text(min_size=1),
    st.emails(),
    st.integers(min_value=0, max_value=150)
)
def test_user_creation_properties(name, email, age):
    """사용자 생성 속성 테스트"""
    result = create_user(name=name, email=email, age=age)
    
    if age < 0 or age > 120:
        assert result.is_failure()
    else:
        assert result.is_success()
        user = result.unwrap()
        assert user.name == name
        assert user.email == email
```

## 통합 테스트

### 레이어 통합 테스트

```python
@pytest.mark.integration
class TestUserIntegration:
    """사용자 관련 통합 테스트"""
    
    @pytest.fixture(autouse=True)
    def setup(self, database):
        """테스트 환경 설정"""
        self.db = database
        self.repository = PostgresUserRepository(self.db)
        self.email_service = SmtpEmailService(test_config)
        self.service = UserService(self.repository, self.email_service)
    
    def test_complete_user_flow(self):
        """전체 사용자 플로우 테스트"""
        # 1. 사용자 생성
        create_result = self.service.create_user({
            "email": "test@example.com",
            "name": "Test User"
        })
        assert create_result.is_success()
        user_id = create_result.unwrap().id
        
        # 2. 사용자 조회
        get_result = self.service.get_user(user_id)
        assert get_result.is_success()
        
        # 3. 사용자 업데이트
        update_result = self.service.update_user(
            user_id, 
            {"name": "Updated Name"}
        )
        assert update_result.is_success()
        
        # 4. 검증
        final_user = self.repository.find_by_id(user_id).unwrap()
        assert final_user.name == "Updated Name"
```

## 리액티브 스트림 테스트

### StepVerifier 사용

```python
from rfs.reactive.test import StepVerifier
from rfs.reactive.mono import Mono
from rfs.reactive.flux import Flux

def test_mono_transformation():
    """Mono 변환 테스트"""
    mono = Mono.just(10)
        .map(lambda x: x * 2)
        .filter(lambda x: x > 15)
    
    StepVerifier.create(mono)
        .expect_next(20)
        .verify_complete()

def test_flux_error_handling():
    """Flux 에러 처리 테스트"""
    flux = Flux.from_iterable([1, 2, 0, 3])
        .map(lambda x: 10 / x)
        .on_error_return(-1)
    
    StepVerifier.create(flux)
        .expect_next(10.0)
        .expect_next(5.0)
        .expect_next(-1)
        .verify_complete()
```

## 테스트 커버리지

### Coverage 설정

```python
# pytest.ini
[tool:pytest]
addopts = --cov=rfs --cov-report=term-missing --cov-report=html
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# 최소 커버리지 요구사항
[coverage:run]
branch = True
source = rfs

[coverage:report]
fail_under = 80
show_missing = True
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
```

## 모범 사례

1. **작은 단위 테스트**: 하나의 기능만 테스트
2. **명확한 이름**: 테스트가 무엇을 검증하는지 명확히
3. **독립적 실행**: 테스트 순서에 무관하게 실행
4. **빠른 실행**: 단위 테스트는 밀리초 단위
5. **Result 패턴 활용**: 예외 대신 Result로 실패 처리
6. **목 객체 적절히**: 외부 의존성은 목으로 대체
7. **테스트 우선**: TDD로 테스트 먼저 작성