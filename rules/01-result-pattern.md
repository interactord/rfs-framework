# Result Pattern 및 에러 처리 규칙

## 핵심 원칙

**절대 예외를 던지지 마세요!** 모든 함수는 명시적인 에러 처리를 위해 `Result[T, E]` 타입을 반환해야 합니다.

## Railway Oriented Programming

### 기본 패턴

```python
# ❌ 잘못된 방법 - 예외 던지기
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Division by zero")
    return a / b

# ✅ 올바른 방법 - Result 반환
def divide(a: float, b: float) -> Result[float, str]:
    if b == 0:
        return Failure("Division by zero")
    return Success(a / b)
```

### 함수 체이닝

Result 패턴의 강력함은 함수를 안전하게 체이닝할 수 있다는 점입니다:

```python
# map: 성공값을 변환
result = Success(10)
    .map(lambda x: x * 2)  # Success(20)
    .map(lambda x: x + 5)  # Success(25)

# bind (flat_map): Result를 반환하는 함수 연결
def validate(x: int) -> Result[int, str]:
    return Success(x) if x > 0 else Failure("음수는 허용되지 않습니다")

def double(x: int) -> Result[int, str]:
    return Success(x * 2)

result = Success(5)
    .bind(validate)  # Success(5)
    .bind(double)    # Success(10)

# 에러가 발생하면 체인이 중단됨
result = Success(-5)
    .bind(validate)  # Failure("음수는 허용되지 않습니다")
    .bind(double)    # Failure("음수는 허용되지 않습니다") - 실행되지 않음
```

## 에러 핸들링 규칙

### 1. 모든 실패 가능한 연산은 Result를 반환

```python
# 파일 읽기
def read_config(path: str) -> Result[dict, str]:
    try:
        with open(path) as f:
            return Success(json.load(f))
    except FileNotFoundError:
        return Failure(f"파일을 찾을 수 없음: {path}")
    except json.JSONDecodeError as e:
        return Failure(f"JSON 파싱 실패: {e}")
```

### 2. 에러 타입 명시

에러 타입을 명확하게 정의하여 타입 안정성 확보:

```python
from dataclasses import dataclass
from typing import Union

@dataclass
class ValidationError:
    field: str
    message: str

@dataclass
class NetworkError:
    code: int
    message: str

ErrorType = Union[ValidationError, NetworkError]

def process_request(data: dict) -> Result[Response, ErrorType]:
    # 유효성 검사 실패
    if not data.get("id"):
        return Failure(ValidationError("id", "ID는 필수입니다"))
    
    # 네트워크 오류
    response = await fetch_data(data["id"])
    if response.status != 200:
        return Failure(NetworkError(response.status, "요청 실패"))
    
    return Success(response)
```

### 3. 복구 가능한 에러 처리

```python
# or_else: 실패 시 대체 Result 제공
result = fetch_from_cache(key).or_else(
    lambda _: fetch_from_database(key)
).or_else(
    lambda _: Success(default_value)
)

# recover: 특정 에러에 대한 복구
def recover_network_error(error: ErrorType) -> Result[Response, ErrorType]:
    match error:
        case NetworkError(code=503):
            return Success(cached_response)
        case _:
            return Failure(error)

result = process_request(data).or_else(recover_network_error)
```

## 비동기 Result 처리

### AsyncResult 패턴

```python
from rfs.core.result import AsyncResult

async def fetch_user(id: int) -> Result[User, str]:
    return await AsyncResult.from_coroutine(
        database.get_user(id)
    ).map_error(lambda e: f"사용자 조회 실패: {e}")

# 비동기 체이닝
result = await AsyncResult.from_value(user_id)
    .bind_async(fetch_user)
    .map_async(enrich_user_data)
    .bind_async(save_to_cache)
```

## 비동기 Result 베스트 프랙티스 ⭐

### 1. AsyncResult 변환 패턴

```python
# ✅ 표준 예외 처리를 AsyncResult로 변환
async def safe_api_call(endpoint: str) -> AsyncResult[dict]:
    """API 호출을 안전한 AsyncResult로 래핑"""
    try:
        response = await http_client.get(endpoint)
        if response.status_code == 200:
            return Success(response.json())
        else:
            return Failure(f"HTTP {response.status_code}: {response.text}")
    except aiohttp.ClientError as e:
        return Failure(f"네트워크 오류: {str(e)}")
    except Exception as e:
        return Failure(f"예상치 못한 오류: {str(e)}")

# ✅ asyncio.gather를 AsyncResult로 변환
async def parallel_fetch_users(user_ids: list[str]) -> AsyncResult[list[User]]:
    """여러 사용자를 병렬로 조회하여 모든 성공 시만 Success 반환"""
    try:
        tasks = [fetch_user(uid) for uid in user_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 모든 결과가 Success인지 확인
        users = []
        for result in results:
            if isinstance(result, Exception):
                return Failure(f"조회 실패: {str(result)}")
            if result.is_failure():
                return Failure(result.unwrap_error())
            users.append(result.unwrap())
        
        return Success(users)
    except Exception as e:
        return Failure(f"병렬 처리 실패: {str(e)}")
```

### 2. Result와 asyncio 통합

```python
# ✅ asyncio 태스크 관리
async def manage_background_tasks(operations: list[callable]) -> AsyncResult[list]:
    """백그라운드 태스크를 관리하고 결과를 안전하게 수집"""
    tasks = []
    try:
        for operation in operations:
            task = asyncio.create_task(operation())
            tasks.append(task)
        
        done, pending = await asyncio.wait(tasks, timeout=30.0)
        
        # 완료되지 않은 태스크 취소
        for task in pending:
            task.cancel()
        
        # 완료된 태스크 결과 수집
        results = []
        for task in done:
            try:
                result = await task
                results.append(result)
            except Exception as e:
                return Failure(f"태스크 실행 실패: {str(e)}")
        
        return Success(results)
    except asyncio.TimeoutError:
        return Failure("작업 시간 초과")
    finally:
        # 남은 태스크 정리
        for task in tasks:
            if not task.done():
                task.cancel()
```

### 3. 컨텍스트 매니저와 Result 통합

```python
# ✅ 비동기 컨텍스트 매니저를 Result로 래핑
async def with_database_transaction(operation: callable) -> AsyncResult[T]:
    """데이터베이스 트랜잭션을 Result 패턴으로 관리"""
    async with database.transaction() as tx:
        try:
            result = await operation(tx)
            await tx.commit()
            return Success(result)
        except Exception as e:
            await tx.rollback()
            return Failure(f"트랜잭션 실패: {str(e)}")

# 사용 예
async def create_user_with_profile(user_data: dict) -> AsyncResult[User]:
    return await with_database_transaction(
        lambda tx: create_user_and_profile(tx, user_data)
    )
```

### 4. 재시도 패턴과 Result 통합

```python
# ✅ 지수 백오프를 포함한 재시도 패턴
async def retry_with_backoff(
    operation: callable,
    max_retries: int = 3,
    base_delay: float = 1.0
) -> AsyncResult[T]:
    """지수 백오프 재시도 패턴"""
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            result = await operation()
            if result.is_success():
                return result
            last_error = result.unwrap_error()
        except Exception as e:
            last_error = str(e)
        
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
    
    return Failure(f"재시도 {max_retries}회 후 실패: {last_error}")

# 사용 예
async def reliable_api_call(endpoint: str) -> AsyncResult[dict]:
    return await retry_with_backoff(
        lambda: safe_api_call(endpoint),
        max_retries=3
    )
```

### 5. 스트림 처리와 Result 통합

```python
# ✅ 비동기 스트림을 Result로 안전하게 처리
async def process_async_stream(
    stream: AsyncIterator[T],
    processor: callable
) -> AsyncResult[list]:
    """비동기 스트림을 안전하게 처리"""
    results = []
    try:
        async for item in stream:
            processed = await processor(item)
            if processed.is_failure():
                return Failure(f"항목 처리 실패: {processed.unwrap_error()}")
            results.append(processed.unwrap())
        
        return Success(results)
    except Exception as e:
        return Failure(f"스트림 처리 실패: {str(e)}")

# 실제 사용 예
async def process_file_stream(file_path: str) -> AsyncResult[list[dict]]:
    async def read_lines():
        async with aiofiles.open(file_path, 'r') as f:
            async for line in f:
                yield line.strip()
    
    return await process_async_stream(
        read_lines(),
        lambda line: parse_json_line(line)
    )
```

## 다중 Result 조합

### sequence: 모든 Result가 성공해야 성공

```python
from rfs.core.result import sequence

results = [
    validate_name(name),
    validate_email(email),
    validate_age(age)
]

# 모두 성공하면 Success([name, email, age])
# 하나라도 실패하면 첫 번째 실패 반환
combined = sequence(results)
```

### combine: 독립적인 Result 병합

```python
from rfs.core.result import combine

# 두 Result를 튜플로 결합
result = combine(
    fetch_user_profile(id),
    fetch_user_settings(id)
)  # Result[(Profile, Settings), Error]
```

### partition: 성공과 실패 분리

```python
from rfs.core.result import partition

results = [process(item) for item in items]
successes, failures = partition(results)

print(f"성공: {len(successes)}, 실패: {len(failures)}")
```

## 타입 변환

### Result ↔ Maybe/Either 변환

```python
from rfs.core.result import (
    result_to_maybe, 
    result_to_either,
    maybe_to_result,
    either_to_result
)

# Result → Maybe (에러 정보 손실)
maybe = result_to_maybe(Success(42))  # Some(42)
maybe = result_to_maybe(Failure("err"))  # None

# Result → Either
either = result_to_either(Success(42))  # Right(42)
either = result_to_either(Failure("err"))  # Left("err")

# Maybe → Result
result = maybe_to_result(Some(42), "값이 없음")  # Success(42)
result = maybe_to_result(None, "값이 없음")  # Failure("값이 없음")
```

## 테스트 작성 규칙

테스트에서도 Result 패턴 사용:

```python
def test_user_creation():
    # Given
    user_data = {"name": "John", "email": "john@example.com"}
    
    # When
    result = create_user(user_data)
    
    # Then - Result 패턴으로 검증
    assert result.is_success()
    user = result.unwrap()
    assert user.name == "John"
    
def test_user_creation_failure():
    # Given
    invalid_data = {"name": ""}
    
    # When
    result = create_user(invalid_data)
    
    # Then
    assert result.is_failure()
    assert "이름은 필수" in result.unwrap_error()
```

## 모범 사례

1. **Early Return 활용**: Guard 패턴과 함께 사용
2. **에러 메시지 구체화**: 디버깅을 위해 충분한 컨텍스트 제공
3. **타입 힌트 명시**: `Result[T, E]`에서 T와 E를 명확히 정의
4. **에러 변환**: `map_error`로 레이어 간 에러 타입 변환
5. **로깅 통합**: 실패 시 자동 로깅 구현

```python
def with_logging(result: Result[T, E]) -> Result[T, E]:
    if result.is_failure():
        logger.error(f"Operation failed: {result.unwrap_error()}")
    return result

result = process_data(input).map(with_logging)
```