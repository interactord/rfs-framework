# Mono API

Mono reactive stream API documentation for RFS Framework.

**주요 클래스:**
- `Mono`: 단일 값 비동기 스트림

## 사용 예제

### 기본 Mono 생성

```python
from rfs.reactive import Mono
import asyncio
from typing import Optional

# 값으로부터 Mono 생성
mono = Mono.just("Hello, World!")
result = await mono.subscribe()
print(result)  # "Hello, World!"

# 빈 Mono 생성
empty_mono = Mono.empty()
result = await empty_mono.subscribe()
print(result)  # None

# 에러 Mono 생성
error_mono = Mono.error(ValueError("Something went wrong"))
try:
    await error_mono.subscribe()
except ValueError as e:
    print(f"Error: {e}")
```

### 비동기 작업에서 Mono 생성

```python
from rfs.reactive import Mono
import aiohttp
import asyncio

async def fetch_user(user_id: int) -> dict:
    """사용자 데이터를 API에서 가져오는 비동기 함수"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.example.com/users/{user_id}") as response:
            if response.status == 200:
                return await response.json()
            else:
                raise ValueError(f"User {user_id} not found")

# 비동기 함수를 Mono로 래핑
def get_user_mono(user_id: int) -> Mono[dict]:
    return Mono.from_callable(lambda: fetch_user(user_id))

# 사용
user_mono = get_user_mono(123)
user_data = await user_mono.subscribe()
print(f"User: {user_data['name']}")
```

### Mono 변환 연산자

```python
from rfs.reactive import Mono

# map - 값 변환
number_mono = Mono.just(5)
squared_mono = number_mono.map(lambda x: x ** 2)
result = await squared_mono.subscribe()
print(result)  # 25

# flatMap - Mono를 반환하는 함수로 변환
def get_user_profile(user_id: int) -> Mono[dict]:
    return Mono.just({"id": user_id, "name": f"User{user_id}"})

def get_user_posts(user: dict) -> Mono[list]:
    return Mono.just([f"Post by {user['name']}", f"Another post by {user['name']}"])

user_posts = (
    Mono.just(1)
    .flat_map(get_user_profile)
    .flat_map(get_user_posts)
)

posts = await user_posts.subscribe()
print(posts)  # ["Post by User1", "Another post by User1"]

# filter - 조건부 필터링
positive_mono = Mono.just(-5).filter(lambda x: x > 0)
result = await positive_mono.subscribe()
print(result)  # None (필터링됨)
```

### 에러 처리

```python
from rfs.reactive import Mono

# onErrorReturn - 에러 시 기본값 반환
def risky_operation(value: int) -> Mono[int]:
    if value < 0:
        return Mono.error(ValueError("Negative value not allowed"))
    return Mono.just(value * 2)

safe_mono = (
    risky_operation(-5)
    .on_error_return(0)  # 에러 시 0 반환
)

result = await safe_mono.subscribe()
print(result)  # 0

# onErrorResume - 에러 시 대체 Mono 실행
def fallback_operation(error: Exception) -> Mono[int]:
    print(f"Fallback triggered due to: {error}")
    return Mono.just(100)

resilient_mono = (
    risky_operation(-5)
    .on_error_resume(fallback_operation)
)

result = await resilient_mono.subscribe()
print(result)  # 100

# retry - 재시도
import random

def unreliable_service() -> Mono[str]:
    if random.random() < 0.7:  # 70% 실패율
        return Mono.error(RuntimeError("Service unavailable"))
    return Mono.just("Success!")

reliable_mono = (
    Mono.from_callable(unreliable_service)
    .retry(max_attempts=3, delay=1.0)
)

result = await reliable_mono.subscribe()
print(result)  # 재시도 후 성공하면 "Success!"
```

### 조건부 실행과 타임아웃

```python
from rfs.reactive import Mono
import asyncio

# switchIfEmpty - 빈 값일 때 대체 Mono 실행
def get_cached_data(key: str) -> Mono[str]:
    # 캐시에서 데이터 조회 (빈 결과)
    return Mono.empty()

def fetch_fresh_data(key: str) -> Mono[str]:
    return Mono.just(f"Fresh data for {key}")

data_mono = (
    get_cached_data("user:123")
    .switch_if_empty(fetch_fresh_data("user:123"))
)

result = await data_mono.subscribe()
print(result)  # "Fresh data for user:123"

# timeout - 타임아웃 설정
async def slow_operation() -> str:
    await asyncio.sleep(5)  # 5초 지연
    return "Completed"

timeout_mono = (
    Mono.from_callable(slow_operation)
    .timeout(2.0)  # 2초 타임아웃
    .on_error_return("Timed out")
)

result = await timeout_mono.subscribe()
print(result)  # "Timed out"
```

### Mono 결합

```python
from rfs.reactive import Mono

# zip - 여러 Mono를 결합
user_mono = Mono.just({"id": 1, "name": "Alice"})
posts_mono = Mono.just(["Post 1", "Post 2"])
profile_mono = Mono.just({"bio": "Software Developer"})

combined_mono = Mono.zip(
    user_mono,
    posts_mono, 
    profile_mono,
    lambda user, posts, profile: {
        "user": user,
        "posts": posts,
        "profile": profile
    }
)

result = await combined_mono.subscribe()
print(result)
# {
#   "user": {"id": 1, "name": "Alice"},
#   "posts": ["Post 1", "Post 2"],
#   "profile": {"bio": "Software Developer"}
# }

# then - 순차 실행 (이전 결과 무시)
def save_user(user: dict) -> Mono[None]:
    print(f"Saving user: {user}")
    return Mono.just(None)

def send_welcome_email(user: dict) -> Mono[None]:
    print(f"Sending welcome email to: {user['email']}")
    return Mono.just(None)

registration_flow = (
    Mono.just({"name": "Bob", "email": "bob@example.com"})
    .flat_map(save_user)
    .then(send_welcome_email({"email": "bob@example.com"}))
)

await registration_flow.subscribe()
```

### 부수 효과와 디버깅

```python
from rfs.reactive import Mono

# doOnNext - 값이 방출될 때 부수 효과 실행
def log_value(value):
    print(f"Processing value: {value}")

result_mono = (
    Mono.just(42)
    .do_on_next(log_value)  # 로깅
    .map(lambda x: x * 2)
    .do_on_next(lambda x: print(f"After doubling: {x}"))
)

result = await result_mono.subscribe()
# 출력:
# Processing value: 42
# After doubling: 84

# doOnError - 에러 발생 시 부수 효과
def log_error(error):
    print(f"Error occurred: {error}")

error_mono = (
    Mono.error(RuntimeError("Something failed"))
    .do_on_error(log_error)
    .on_error_return("Fallback")
)

result = await error_mono.subscribe()
# 출력: Error occurred: Something failed
# 결과: "Fallback"

# doFinally - 완료/에러 관계없이 실행
def cleanup():
    print("Cleaning up resources")

final_mono = (
    Mono.just("data")
    .map(lambda x: x.upper())
    .do_finally(cleanup)
)

result = await final_mono.subscribe()
# 출력: Cleaning up resources
# 결과: "DATA"
```

### 캐싱과 공유

```python
from rfs.reactive import Mono
import time

# cache - 결과 캐싱
expensive_computation = Mono.from_callable(lambda: time.time())
cached_mono = expensive_computation.cache()

# 여러 번 구독해도 한 번만 실행됨
result1 = await cached_mono.subscribe()
await asyncio.sleep(1)
result2 = await cached_mono.subscribe()

print(result1 == result2)  # True

# share - 여러 구독자 간 공유
shared_mono = (
    Mono.from_callable(lambda: print("Expensive operation") or "result")
    .share()
)

# 동시에 여러 구독자가 있어도 한 번만 실행
await asyncio.gather(
    shared_mono.subscribe(),
    shared_mono.subscribe(),
    shared_mono.subscribe()
)
# "Expensive operation"은 한 번만 출력됨
```

### AsyncResult와 Mono 통합

RFS Framework v4.4.0부터 Mono와 AsyncResult를 완벽하게 통합할 수 있습니다.

```python
from rfs.reactive import Mono
from rfs.async_pipeline import AsyncResult
from rfs.core.result import Success, Failure

# AsyncResult를 Mono로 변환
def async_result_to_mono(async_result: AsyncResult) -> Mono:
    """AsyncResult를 Mono로 변환"""
    async def converter():
        result = await async_result.to_result()
        if result.is_success():
            return result.unwrap()
        else:
            raise Exception(result.unwrap_error())
    
    return Mono.from_callable(converter)

# Mono를 AsyncResult로 변환  
def mono_to_async_result(mono: Mono) -> AsyncResult:
    """Mono를 AsyncResult로 변환"""
    async def converter():
        try:
            value = await mono.to_future()
            return Success(value)
        except Exception as e:
            return Failure(str(e))
    
    return AsyncResult(converter())

# 통합 사용 예시
async def integrated_processing():
    """Mono와 AsyncResult 통합 처리"""
    
    # 1. AsyncResult로 사용자 검증
    user_validation = AsyncResult.from_async(lambda: validate_user("user123"))
    
    # 2. AsyncResult를 Mono로 변환하여 프로필 조회
    profile_mono = (
        async_result_to_mono(user_validation)
        .flat_map(lambda user: fetch_user_profile_mono(user["id"]))
        .map(lambda profile: {**profile, "validated": True})
    )
    
    # 3. 최종 결과를 AsyncResult로 변환
    final_result = mono_to_async_result(profile_mono)
    
    # 4. 결과 처리
    if await final_result.is_success():
        profile = await final_result.unwrap_async()
        print(f"검증된 프로필: {profile}")
        return profile
    else:
        error = await final_result.to_result().then(lambda r: r.unwrap_error())
        print(f"처리 실패: {error}")
        return None

# 실행
await integrated_processing()
```

### 실제 웹 API 사용 사례

```python
from rfs.reactive import Mono
from rfs.web.fastapi_helpers import async_result_to_response
from rfs.logging.async_logging import AsyncResultLogger, log_async_chain
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()
logger = AsyncResultLogger()

class UserService:
    """사용자 서비스 클래스"""
    
    def get_user_mono(self, user_id: str) -> Mono[dict]:
        """사용자 정보 조회를 Mono로 반환"""
        async def fetch_user():
            # 외부 API 호출 시뮬레이션
            if user_id == "404":
                raise HTTPException(status_code=404, detail="User not found")
            return {"id": user_id, "name": f"User {user_id}", "email": f"user{user_id}@example.com"}
        
        return Mono.from_callable(fetch_user).timeout(5.0)
    
    def enrich_user_profile_mono(self, user: dict) -> Mono[dict]:
        """사용자 프로필 보강을 Mono로 반환"""
        async def enrich():
            # 추가 정보 조회
            return {
                **user,
                "profile_completed": True,
                "last_login": "2025-01-01T10:00:00Z",
                "preferences": {"theme": "dark", "language": "ko"}
            }
        
        return Mono.from_callable(enrich)

user_service = UserService()

@app.get("/api/users/{user_id}")
@log_async_chain(logger, "get_user_with_mono")
async def get_user_with_mono(user_id: str):
    """Mono를 사용한 사용자 조회 API"""
    
    try:
        # Mono 체이닝으로 사용자 데이터 처리
        user_data = await (
            user_service.get_user_mono(user_id)
            .flat_map(lambda user: user_service.enrich_user_profile_mono(user))
            .map(lambda profile: {
                "user": profile,
                "retrieved_at": "2025-01-01T12:00:00Z",
                "source": "mono_pipeline"
            })
            .on_error_return({
                "error": "사용자 조회 실패",
                "user_id": user_id
            })
            .to_future()
        )
        
        return user_data
        
    except Exception as e:
        return {"error": str(e), "user_id": user_id}

# 캐시 우선 전략
@app.get("/api/users/{user_id}/cached")
async def get_cached_user(user_id: str):
    """캐시 우선 사용자 조회"""
    
    def get_from_cache() -> Mono[dict]:
        """캐시에서 사용자 조회 (빈 결과 시뮬레이션)"""
        return Mono.empty()
    
    def get_fresh_data() -> Mono[dict]:
        """새로운 데이터 조회"""
        return (
            user_service.get_user_mono(user_id)
            .flat_map(user_service.enrich_user_profile_mono)
            .map(lambda user: {**user, "cached": False, "fresh": True})
        )
    
    result = await (
        get_from_cache()
        .switch_if_empty(get_fresh_data())
        .on_error_return({"error": "모든 조회 방법 실패"})
        .to_future()
    )
    
    return result
```

### 에러 복구와 회복력 패턴

```python
from rfs.reactive import Mono
import random
import asyncio

class ResilientDataService:
    """회복력 있는 데이터 서비스"""
    
    def fetch_from_primary(self, key: str) -> Mono[dict]:
        """주 데이터 소스에서 조회"""
        async def primary_fetch():
            # 70% 확률로 실패 시뮬레이션
            if random.random() < 0.7:
                raise ConnectionError("Primary database unavailable")
            return {"source": "primary", "data": f"primary_data_{key}"}
        
        return Mono.from_callable(primary_fetch).timeout(2.0)
    
    def fetch_from_backup(self, key: str) -> Mono[dict]:
        """백업 데이터 소스에서 조회"""
        async def backup_fetch():
            # 30% 확률로 실패
            if random.random() < 0.3:
                raise ConnectionError("Backup database unavailable")
            return {"source": "backup", "data": f"backup_data_{key}"}
        
        return Mono.from_callable(backup_fetch).timeout(3.0)
    
    def fetch_from_cache(self, key: str) -> Mono[dict]:
        """캐시에서 조회 (항상 성공)"""
        async def cache_fetch():
            return {"source": "cache", "data": f"cached_data_{key}", "stale": True}
        
        return Mono.from_callable(cache_fetch)
    
    def resilient_fetch(self, key: str) -> Mono[dict]:
        """회복력 있는 데이터 조회"""
        return (
            self.fetch_from_primary(key)
            .on_error_resume(lambda _: self.fetch_from_backup(key))
            .on_error_resume(lambda _: self.fetch_from_cache(key))
            .retry(max_attempts=2)  # 최대 2회 재시도
            .do_on_next(lambda data: print(f"데이터 조회 성공: {data['source']}에서"))
            .do_on_error(lambda error: print(f"모든 조회 실패: {error}"))
        )

# 사용 예시
async def test_resilient_service():
    service = ResilientDataService()
    
    # 10개의 키에 대해 회복력 있는 조회 수행
    keys = [f"key_{i}" for i in range(10)]
    
    for key in keys:
        try:
            result = await service.resilient_fetch(key).to_future()
            print(f"{key}: {result}")
        except Exception as e:
            print(f"{key} 최종 실패: {e}")

# 실행
await test_resilient_service()
```

## 관련 문서

- [반응형 프로그래밍 가이드](../../27-reactive-programming-guide.md) - 종합적인 반응형 프로그래밍 가이드
- [Flux API](flux.md) - 다중 값 반응형 스트림
- [AsyncResult API](../async-pipeline/async-result.md) - 비동기 Result 모나드
- [AsyncResult Web Integration](../../26-asyncresult-web-integration.md) - 웹 통합 가이드
- [반응형 프로그래밍](../../01-core-patterns.md#reactive-programming) - 반응형 패턴 개념
- [비동기 처리](../../22-hot-library.md) - 함수형 반응형 유틸리티