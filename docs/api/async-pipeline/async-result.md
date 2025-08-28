# AsyncResult API

RFS Framework의 비동기 전용 Result 모나드 API 레퍼런스입니다.

## 모듈 임포트

```python
from rfs.async_pipeline import (
    AsyncResult,
    async_success,
    async_failure,
    from_awaitable,
    sequence_async_results,
    parallel_map_async
)
```

## 핵심 클래스

### AsyncResult[T, E]

비동기 전용 Result 모나드로, 모든 연산이 비동기로 처리되며 자동 에러 핸들링과 타입 안전성을 제공합니다.

```python
class AsyncResult(Generic[T, E]):
    """
    비동기 전용 Result 모나드
    
    특징:
    - 모든 연산이 비동기로 처리됨
    - 자동 에러 핸들링 및 타입 안전성 보장
    - 기존 Result 패턴과 완전 호환
    - 체이닝 최적화 및 컨텍스트 보존
    """
```

#### 생성자 메서드

##### from_async

비동기 함수로부터 AsyncResult를 생성합니다.

```python
@classmethod
def from_async(cls, async_func: Callable[[], Awaitable[T]]) -> 'AsyncResult[T, Exception]'
```

**매개변수:**
- `async_func`: 비동기 함수

**반환값:**
- `AsyncResult[T, Exception]`: 새로운 AsyncResult 인스턴스

**사용 예시:**

```python
async def fetch_user_data(user_id: str) -> dict:
    # 사용자 데이터 조회 로직
    return {"id": user_id, "name": f"User {user_id}"}

# AsyncResult로 래핑
user_result = AsyncResult.from_async(lambda: fetch_user_data("123"))
user_data = await user_result.unwrap_async()
```

##### from_value

값으로부터 즉시 성공하는 AsyncResult를 생성합니다.

```python
@classmethod
def from_value(cls, value: T) -> 'AsyncResult[T, E]'
```

**사용 예시:**

```python
success_result = AsyncResult.from_value({"status": "ok"})
value = await success_result.unwrap_async()  # {"status": "ok"}
```

##### from_error

에러로부터 즉시 실패하는 AsyncResult를 생성합니다.

```python
@classmethod
def from_error(cls, error: E) -> 'AsyncResult[T, E]'
```

**사용 예시:**

```python
error_result = AsyncResult.from_error("Something went wrong")
try:
    await error_result.unwrap_async()
except Exception as e:
    print(f"Error: {e}")  # Error: Something went wrong
```

##### from_result

기존 Result로부터 AsyncResult를 생성합니다.

```python
@classmethod
def from_result(cls, result: Result[T, E]) -> 'AsyncResult[T, E]'
```

**사용 예시:**

```python
from rfs.core.result import Success, Failure

# 기존 Result를 AsyncResult로 변환
sync_result = Success("data")
async_result = AsyncResult.from_result(sync_result)
data = await async_result.unwrap_async()  # "data"
```

#### 상태 확인 메서드

##### is_success

성공 여부를 비동기로 확인합니다.

```python
async def is_success(self) -> bool
```

##### is_failure

실패 여부를 비동기로 확인합니다.

```python
async def is_failure(self) -> bool
```

**사용 예시:**

```python
result = AsyncResult.from_value("success")

if await result.is_success():
    print("작업이 성공했습니다")
    
if await result.is_failure():
    print("작업이 실패했습니다")
```

#### 값 추출 메서드

##### unwrap_async

성공 값을 추출합니다. 실패 시 예외가 발생합니다.

```python
async def unwrap_async(self) -> T
```

**사용 예시:**

```python
success_result = AsyncResult.from_value("data")
data = await success_result.unwrap_async()  # "data"

error_result = AsyncResult.from_error("error")
try:
    await error_result.unwrap_async()
except Exception as e:
    print(f"Error: {e}")
```

##### unwrap_or_async

값을 추출하거나 실패 시 기본값을 반환합니다.

```python
async def unwrap_or_async(self, default: T) -> T
```

**사용 예시:**

```python
error_result = AsyncResult.from_error("error")
value = await error_result.unwrap_or_async("default")  # "default"
```

##### unwrap_or_else_async

값을 추출하거나 실패 시 비동기 함수로 기본값을 생성합니다.

```python
async def unwrap_or_else_async(self, default_func: Callable[[E], Awaitable[T]]) -> T
```

**사용 예시:**

```python
async def create_default_value(error):
    print(f"Creating default due to: {error}")
    return "fallback_value"

error_result = AsyncResult.from_error("network_error")
value = await error_result.unwrap_or_else_async(create_default_value)
# 출력: Creating default due to: network_error
# 반환값: "fallback_value"
```

#### 변환 메서드

##### bind_async

비동기 함수와 모나딕 바인딩을 수행합니다 (flatMap).

```python
def bind_async(self, func: Callable[[T], 'AsyncResult[U, E]']) -> 'AsyncResult[U, E]'
```

**사용 예시:**

```python
async def validate_user(user_data: dict) -> AsyncResult[dict, str]:
    if not user_data.get("email"):
        return AsyncResult.from_error("Email is required")
    return AsyncResult.from_value(user_data)

async def save_user(user_data: dict) -> AsyncResult[dict, str]:
    # 사용자 저장 로직
    saved_user = {**user_data, "id": "generated_id"}
    return AsyncResult.from_value(saved_user)

# 체이닝
result = await (
    AsyncResult.from_value({"email": "user@example.com", "name": "John"})
    .bind_async(validate_user)
    .bind_async(save_user)
    .to_result()
)

if result.is_success():
    saved_user = result.unwrap()
    print(f"사용자 저장됨: {saved_user}")
```

##### map_async

비동기 함수로 값을 변환합니다.

```python
def map_async(self, func: Callable[[T], Awaitable[U]]) -> 'AsyncResult[U, E]'
```

**사용 예시:**

```python
async def enrich_user_data(user: dict) -> dict:
    # 사용자 데이터 보강
    return {**user, "last_login": "2025-01-01T00:00:00Z"}

result = await (
    AsyncResult.from_value({"id": "123", "name": "John"})
    .map_async(enrich_user_data)
    .unwrap_async()
)

print(result)  # {"id": "123", "name": "John", "last_login": "2025-01-01T00:00:00Z"}
```

##### map_sync

동기 함수로 값을 변환합니다.

```python
def map_sync(self, func: Callable[[T], U]) -> 'AsyncResult[U, E]'
```

**사용 예시:**

```python
result = await (
    AsyncResult.from_value("hello")
    .map_sync(lambda s: s.upper())
    .map_sync(lambda s: f"Message: {s}")
    .unwrap_async()
)

print(result)  # "Message: HELLO"
```

##### map_error

에러 값을 변환합니다.

```python
def map_error(self, func: Callable[[E], U]) -> 'AsyncResult[T, U]'
```

**사용 예시:**

```python
result = await (
    AsyncResult.from_error("network_timeout")
    .map_error(lambda e: f"네트워크 오류: {e}")
    .to_result()
)

print(result.unwrap_error())  # "네트워크 오류: network_timeout"
```

#### 에러 복구 메서드

##### recover_async

실패 시 비동기 복구 함수를 실행합니다.

```python
def recover_async(self, recovery_func: Callable[[E], Awaitable[T]]) -> 'AsyncResult[T, E]'
```

**사용 예시:**

```python
async def fetch_from_cache(error):
    print(f"Primary failed ({error}), fetching from cache...")
    return {"data": "cached_data", "stale": True}

async def fetch_from_primary():
    # 주 데이터 소스 (실패 시뮬레이션)
    raise ConnectionError("Primary database unavailable")

result = await (
    AsyncResult.from_async(fetch_from_primary)
    .recover_async(fetch_from_cache)
    .unwrap_async()
)

print(result)  # {"data": "cached_data", "stale": True}
```

##### recover_with_async

실패 시 다른 AsyncResult로 복구합니다.

```python
def recover_with_async(self, recovery_func: Callable[[E], 'AsyncResult[T, E]']) -> 'AsyncResult[T, E]'
```

**사용 예시:**

```python
def fallback_service(error) -> AsyncResult[str, str]:
    print(f"Primary service failed: {error}")
    return AsyncResult.from_async(lambda: fetch_from_backup_service())

async def fetch_from_backup_service():
    return "backup_data"

result = await (
    AsyncResult.from_error("primary_service_down")
    .recover_with_async(fallback_service)
    .unwrap_async()
)

print(result)  # "backup_data"
```

#### 필터링 메서드

##### filter_async

비동기 조건으로 필터링합니다.

```python
def filter_async(self, predicate: Callable[[T], Awaitable[bool]], error: E) -> 'AsyncResult[T, E]'
```

**사용 예시:**

```python
async def is_adult(user: dict) -> bool:
    # 나이 확인 로직 (비동기 DB 조회 등)
    return user.get("age", 0) >= 18

result = await (
    AsyncResult.from_value({"name": "John", "age": 25})
    .filter_async(is_adult, "미성년자는 사용할 수 없습니다")
    .unwrap_async()
)

print(result)  # {"name": "John", "age": 25}
```

##### filter_sync

동기 조건으로 필터링합니다.

```python
def filter_sync(self, predicate: Callable[[T], bool], error: E) -> 'AsyncResult[T, E]'
```

**사용 예시:**

```python
result = await (
    AsyncResult.from_value(42)
    .filter_sync(lambda x: x > 0, "음수는 허용되지 않습니다")
    .unwrap_async()
)

print(result)  # 42
```

#### 결합 메서드

##### zip_with

다른 AsyncResult와 결합합니다.

```python
def zip_with(self, other: 'AsyncResult[U, E]') -> 'AsyncResult[tuple[T, U], E]'
```

**사용 예시:**

```python
user_result = AsyncResult.from_value({"name": "John"})
profile_result = AsyncResult.from_value({"bio": "Developer"})

combined = await (
    user_result
    .zip_with(profile_result)
    .unwrap_async()
)

print(combined)  # ({"name": "John"}, {"bio": "Developer"})
```

#### 변환 및 추출 메서드

##### to_result

일반 Result로 변환합니다.

```python
async def to_result(self) -> Result[T, E]
```

##### to_awaitable

Awaitable로 변환합니다 (성공 값만 반환, 실패 시 예외).

```python
def to_awaitable(self) -> Awaitable[T]
```

**사용 예시:**

```python
# Result로 변환
async_result = AsyncResult.from_value("data")
sync_result = await async_result.to_result()

# Awaitable로 변환 (await 직접 가능)
data = await async_result.to_awaitable()  # "data"
```

## 편의 함수

### async_success

성공 값으로 AsyncResult를 생성합니다.

```python
def async_success(value: T) -> AsyncResult[T, E]
```

### async_failure

에러로 AsyncResult를 생성합니다.

```python
def async_failure(error: E) -> AsyncResult[T, E]
```

### from_awaitable

일반 Awaitable을 AsyncResult로 래핑합니다.

```python
def from_awaitable(awaitable: Awaitable[T]) -> AsyncResult[T, Exception]
```

**사용 예시:**

```python
import asyncio

# 편의 함수 사용
success = async_success("데이터")
failure = async_failure("에러 발생")

# Awaitable 래핑
async def some_async_operation():
    await asyncio.sleep(0.1)
    return "결과"

result = from_awaitable(some_async_operation())
data = await result.unwrap_async()  # "결과"
```

### sequence_async_results

AsyncResult 리스트를 병렬로 실행하여 결과 리스트를 생성합니다.

```python
async def sequence_async_results(
    results: list[AsyncResult[T, E]]
) -> AsyncResult[list[T], E]
```

**사용 예시:**

```python
# 여러 비동기 작업을 병렬 실행
async def fetch_user(user_id: str):
    return f"User {user_id}"

user_results = [
    AsyncResult.from_async(lambda: fetch_user("1")),
    AsyncResult.from_async(lambda: fetch_user("2")),
    AsyncResult.from_async(lambda: fetch_user("3"))
]

all_users = await sequence_async_results(user_results)
users = await all_users.unwrap_async()
print(users)  # ["User 1", "User 2", "User 3"]
```

### parallel_map_async

리스트의 각 항목에 비동기 함수를 병렬 적용합니다.

```python
async def parallel_map_async(
    func: Callable[[T], Awaitable[U]], 
    items: list[T],
    max_concurrency: int = 10
) -> AsyncResult[list[U], Exception]
```

**매개변수:**
- `func`: 각 항목에 적용할 비동기 함수
- `items`: 처리할 항목들
- `max_concurrency`: 최대 동시 실행 수 (기본값: 10)

**사용 예시:**

```python
async def process_item(item: str) -> str:
    await asyncio.sleep(0.1)  # 처리 시뮬레이션
    return f"processed_{item}"

items = ["a", "b", "c", "d", "e"]
results = await parallel_map_async(process_item, items, max_concurrency=3)
processed_items = await results.unwrap_async()
print(processed_items)  # ["processed_a", "processed_b", ...]
```

## 고급 사용 패턴

### 체이닝 패턴

```python
async def comprehensive_user_processing():
    """사용자 처리 파이프라인"""
    
    user_data = {"email": "user@example.com", "name": "John"}
    
    result = await (
        AsyncResult.from_value(user_data)
        # 1. 검증
        .bind_async(validate_user_email)
        .bind_async(validate_user_name)
        # 2. 보강
        .map_async(enrich_user_profile)
        .map_async(add_user_permissions)
        # 3. 저장
        .bind_async(save_user_to_database)
        # 4. 결과 변환
        .to_result()
    )
    
    if result.is_success():
        user = result.unwrap()
        print(f"사용자 처리 완료: {user['id']}")
        return user
    else:
        print(f"처리 실패: {result.unwrap_error()}")
        return None
```

### 에러 복구 체인

```python
async def resilient_data_fetch(query: str):
    """계층화된 에러 복구"""
    
    result = await (
        # 1차: 주 데이터베이스
        AsyncResult.from_async(lambda: fetch_from_primary_db(query))
        # 2차: 백업 데이터베이스
        .recover_async(lambda _: fetch_from_backup_db(query))
        # 3차: 캐시
        .recover_async(lambda _: fetch_from_cache(query))
        # 4차: 기본값
        .recover_async(lambda _: get_default_data(query))
        .unwrap_async()
    )
    
    return result
```

### 병렬 작업 조합

```python
async def parallel_user_data_loading(user_id: str):
    """사용자 관련 데이터를 병렬로 로드"""
    
    # 각각 독립적인 AsyncResult 생성
    user_profile = AsyncResult.from_async(lambda: fetch_user_profile(user_id))
    user_posts = AsyncResult.from_async(lambda: fetch_user_posts(user_id))
    user_friends = AsyncResult.from_async(lambda: fetch_user_friends(user_id))
    
    # 모든 작업을 병렬로 실행
    combined = await sequence_async_results([user_profile, user_posts, user_friends])
    
    if await combined.is_success():
        profile, posts, friends = await combined.unwrap_async()
        return {
            "profile": profile,
            "posts": posts, 
            "friends": friends
        }
    else:
        # 개별 실패 처리
        return await handle_partial_failures(user_profile, user_posts, user_friends)
```

## 컨텍스트 매니저 사용

AsyncResult는 비동기 컨텍스트 매니저를 지원합니다.

```python
async def context_manager_example():
    """컨텍스트 매니저로 AsyncResult 사용"""
    
    user_result = AsyncResult.from_async(lambda: fetch_user("123"))
    
    async with user_result as result:
        if result.is_success():
            user = result.unwrap()
            print(f"사용자: {user}")
        else:
            print(f"에러: {result.unwrap_error()}")
```

## 성능 최적화 팁

1. **캐싱 활용**: 반복되는 연산 결과 캐시
2. **병렬 처리**: `sequence_async_results`와 `parallel_map_async` 활용
3. **동시성 제어**: `max_concurrency` 매개변수로 리소스 관리
4. **에러 복구**: 계층화된 복구 전략으로 시스템 안정성 향상

## 관련 문서

- [반응형 프로그래밍 가이드](../../27-reactive-programming-guide.md)
- [Result 패턴](../../01-core-patterns.md#result-pattern)
- [AsyncResult Web Integration](../../26-asyncresult-web-integration.md)
- [HOF 사용 가이드](../../16-hof-usage-guide.md)