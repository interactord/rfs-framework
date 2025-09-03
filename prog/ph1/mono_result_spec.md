# MonoResult[T, E] 클래스 상세 사양서

**버전**: v1.0  
**작성일**: 2025-09-03  
**상태**: 🟡 설계 단계

---

## 📋 클래스 개요

MonoResult[T, E]는 Mono의 비동기 처리 능력과 Result의 타입 안전한 에러 처리를 결합한 클래스입니다. 복잡한 비동기 + Result 패턴을 우아하게 처리할 수 있도록 설계되었습니다.

### 🎯 설계 목표
1. **타입 안전성**: 컴파일 타임 에러 검출
2. **우아한 체이닝**: 명확하고 읽기 쉬운 비동기 플로우
3. **성능 최적화**: 불필요한 오버헤드 최소화
4. **호환성**: 기존 Mono/Result와 완벽 호환

---

## 🏗️ 클래스 구조

### 타입 정의
```python
from typing import Generic, TypeVar, Callable, Awaitable, Optional
from rfs.core.result import Result, Success, Failure

T = TypeVar('T')  # 성공 값 타입
E = TypeVar('E')  # 에러 값 타입
U = TypeVar('U')  # 변환된 값 타입
F = TypeVar('F')  # 변환된 에러 타입

class MonoResult(Generic[T, E]):
    """
    Mono + Result 패턴 통합 클래스
    비동기 처리와 타입 안전한 에러 처리 결합
    """
```

### 내부 상태
```python
class MonoResult(Generic[T, E]):
    def __init__(self, async_func: Callable[[], Awaitable[Result[T, E]]]):
        """
        MonoResult 생성자
        
        Args:
            async_func: Result[T, E]를 반환하는 비동기 함수
        """
        self._async_func = async_func
        self._cached_result: Optional[Result[T, E]] = None
        self._is_cached = False
```

---

## 🔧 핵심 메서드

### 생성 메서드 (Static Factory)

#### `from_result(result: Result[T, E]) -> MonoResult[T, E]`
```python
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
```

#### `from_async_result(async_func: Callable[[], Awaitable[Result[T, E]]]) -> MonoResult[T, E]`
```python
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
        ...     # 데이터베이스에서 사용자 조회
        ...     return Success(user) if user_found else Failure("사용자 없음")
        >>> mono = MonoResult.from_async_result(lambda: fetch_user("123"))
    """
    return MonoResult(async_func)
```

#### `from_value(value: T) -> MonoResult[T, E]`
```python
@staticmethod
def from_value(value: T) -> "MonoResult[T, E]":
    """
    성공 값으로 MonoResult 생성
    
    Args:
        value: 성공 값
        
    Returns:
        MonoResult: Success를 감싼 MonoResult
    """
    return MonoResult.from_result(Success(value))
```

#### `from_error(error: E) -> MonoResult[T, E]`
```python
@staticmethod  
def from_error(error: E) -> "MonoResult[T, E]":
    """
    에러 값으로 MonoResult 생성
    
    Args:
        error: 에러 값
        
    Returns:
        MonoResult: Failure를 감싼 MonoResult
    """
    return MonoResult.from_result(Failure(error))
```

### 변환 메서드 (Transformation)

#### `map(func: Callable[[T], U]) -> MonoResult[U, E]`
```python
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
                return Success(func(result.unwrap()))
            except Exception as e:
                return Failure(e)  # 변환 중 예외 발생 시 Failure로 변환
        else:
            return result  # 에러는 그대로 전파
    
    return MonoResult(mapped)
```

#### `map_error(func: Callable[[E], F]) -> MonoResult[T, F]`
```python
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
                return Failure(func(result.unwrap_error()))
            except Exception as e:
                return Failure(e)
        else:
            return result
    
    return MonoResult(error_mapped)
```

### 체이닝 메서드 (Chaining)

#### `bind_result(func: Callable[[T], Result[U, E]]) -> MonoResult[U, E]`
```python
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
            return result
    
    return MonoResult(bound)
```

#### `bind_async_result(func: Callable[[T], Awaitable[Result[U, E]]]) -> MonoResult[U, E]`
```python
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
            return result
    
    return MonoResult(async_bound)
```

### 에러 처리 메서드

#### `on_error_return_result(func: Callable[[E], Result[T, E]]) -> MonoResult[T, E]`
```python
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
            return result
    
    return MonoResult(with_error_recovery)
```

### 고급 기능

#### `timeout(seconds: float) -> MonoResult[T, E]`
```python
def timeout(self, seconds: float) -> "MonoResult[T, E]":
    """
    타임아웃 설정
    
    Args:
        seconds: 타임아웃 시간(초)
        
    Returns:
        MonoResult: 타임아웃이 적용된 MonoResult
        
    Raises:
        TimeoutError: 타임아웃 발생 시 (Failure로 래핑됨)
    """
    async def with_timeout():
        try:
            return await asyncio.wait_for(self._async_func(), timeout=seconds)
        except asyncio.TimeoutError:
            return Failure(f"Operation timed out after {seconds} seconds")
        except Exception as e:
            return Failure(e)
    
    return MonoResult(with_timeout)
```

#### `cache() -> MonoResult[T, E]`
```python
def cache(self) -> "MonoResult[T, E]":
    """
    결과 캐싱 (한 번 계산된 결과를 재사용)
    
    Returns:
        MonoResult: 캐싱이 적용된 MonoResult
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
```

### 최종 변환

#### `to_result() -> Awaitable[Result[T, E]]`
```python
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
```

---

## 💡 사용 예제

### 기본 사용법
```python
# 1. 단순한 값 생성
user_mono = MonoResult.from_value(User(id=1, name="김철수"))

# 2. 비동기 함수 래핑
async def fetch_user(user_id: str) -> Result[User, str]:
    return Success(User(id=user_id, name="김철수"))

user_mono = MonoResult.from_async_result(lambda: fetch_user("123"))

# 3. 체이닝
result = await (
    MonoResult.from_async_result(lambda: fetch_user("123"))
    .map(lambda user: user.name)
    .bind_result(lambda name: validate_name(name))
    .map_error(lambda e: f"사용자 처리 실패: {e}")
    .timeout(5.0)
    .to_result()
)
```

### 실제 사용 사례 (Health Check)
```python
async def health_check() -> Result[HealthResponse, HealthError]:
    return await (
        MonoResult.from_async_result(get_database_connection)
        .bind_async_result(lambda db: check_database_health(db))
        .bind_async_result(lambda db_health: check_redis_health())
        .bind_result(lambda redis_health: create_health_response(db_health, redis_health))
        .map_error(lambda e: HealthError(f"헬스체크 실패: {e}"))
        .on_error_return_result(lambda e: Success(HealthResponse(status="degraded", error=str(e))))
        .timeout(10.0)
        .to_result()
    )
```

---

## 🧪 테스트 시나리오

### 성공 케이스
```python
@pytest.mark.asyncio
async def test_successful_chain():
    result = await (
        MonoResult.from_value("test")
        .map(lambda s: s.upper())
        .bind_result(lambda s: Success(f"processed_{s}"))
        .to_result()
    )
    
    assert result.is_success()
    assert result.unwrap() == "processed_TEST"
```

### 에러 처리 케이스
```python
@pytest.mark.asyncio
async def test_error_handling():
    result = await (
        MonoResult.from_error("initial_error")
        .map(lambda s: s.upper())  # 실행되지 않음
        .map_error(lambda e: f"handled_{e}")
        .to_result()
    )
    
    assert result.is_failure()
    assert result.unwrap_error() == "handled_initial_error"
```

### 타임아웃 케이스
```python
@pytest.mark.asyncio
async def test_timeout():
    async def slow_operation():
        await asyncio.sleep(2.0)
        return Success("completed")
    
    result = await (
        MonoResult.from_async_result(slow_operation)
        .timeout(1.0)  # 1초 타임아웃
        .to_result()
    )
    
    assert result.is_failure()
    assert "timed out" in str(result.unwrap_error()).lower()
```

---

## 📊 성능 특성

### 예상 성능 지표
- **오버헤드**: 기존 Mono 대비 < 5%
- **메모리 사용량**: 최소한의 추가 메모리 사용
- **타입 체크 시간**: 컴파일 타임 최적화

### 최적화 전략
1. **레이지 평가**: 필요할 때만 실행
2. **캐싱**: 중복 계산 방지
3. **타입 힌트 최적화**: mypy 최적화

---

**상태**: Phase 1 구현 준비 완료 - MonoResult 클래스 설계 완료  
**다음 단계**: 실제 구현 시작 (`src/rfs/reactive/mono_result.py`)