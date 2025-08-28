# FastAPI AsyncResult Helpers API

RFS Framework의 FastAPI AsyncResult 헬퍼 API 레퍼런스입니다.

## 모듈 임포트

```python
from rfs.web.fastapi_helpers import (
    async_result_to_response,
    async_result_to_paginated_response,
    AsyncResultRouter,
    create_async_result_router,
    AsyncResultEndpoint,
    create_error_mapper,
    batch_async_results_to_response,
    AsyncResultHTTPError
)
```

## 주요 함수

### async_result_to_response

AsyncResult를 FastAPI JSONResponse로 변환합니다.

```python
async def async_result_to_response(
    async_result: AsyncResult[T, E],
    success_status: int = 200,
    error_mapper: Optional[Callable[[E], HTTPException]] = None,
    success_headers: Optional[Dict[str, str]] = None,
    metadata_extractor: Optional[Callable[[T], Dict[str, Any]]] = None
) -> JSONResponse
```

#### 매개변수

- `async_result`: 변환할 AsyncResult 객체
- `success_status`: 성공 시 HTTP 상태 코드 (기본값: 200)
- `error_mapper`: 에러를 HTTPException으로 매핑하는 함수
- `success_headers`: 성공 응답에 추가할 HTTP 헤더
- `metadata_extractor`: 응답에 메타데이터를 추가하는 함수

#### 반환값

- `JSONResponse`: FastAPI 응답 객체

#### 사용 예시

```python
from fastapi import FastAPI, HTTPException
from rfs.web.fastapi_helpers import async_result_to_response

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    user_result = await fetch_user(user_id)
    
    # 에러 매퍼 정의
    def error_mapper(error: str) -> HTTPException:
        if "not found" in error.lower():
            return HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        return HTTPException(status_code=500, detail="서버 오류")
    
    # 메타데이터 추출기
    def metadata_extractor(user: dict) -> dict:
        return {
            "fetched_at": datetime.utcnow().isoformat(),
            "user_type": user.get("type", "standard")
        }
    
    return await async_result_to_response(
        user_result,
        error_mapper=error_mapper,
        success_headers={"X-Cache-Status": "MISS"},
        metadata_extractor=metadata_extractor
    )
```

### async_result_to_paginated_response

페이지네이션을 지원하는 AsyncResult 응답을 생성합니다.

```python
async def async_result_to_paginated_response(
    async_result: AsyncResult[List[T], E],
    page: int,
    page_size: int,
    total_count: Optional[int] = None,
    error_mapper: Optional[Callable[[E], HTTPException]] = None
) -> JSONResponse
```

#### 매개변수

- `async_result`: 리스트 데이터를 포함한 AsyncResult
- `page`: 현재 페이지 번호 (1부터 시작)
- `page_size`: 페이지당 항목 수
- `total_count`: 전체 항목 수 (None이면 자동 계산)
- `error_mapper`: 에러 매핑 함수

#### 반환값

페이지네이션 정보가 포함된 JSONResponse

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_count": 150,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

#### 사용 예시

```python
@app.get("/users")
async def list_users(page: int = 1, page_size: int = 20):
    users_result = await fetch_users_paginated(page, page_size)
    return await async_result_to_paginated_response(
        users_result,
        page=page,
        page_size=page_size
    )
```

### batch_async_results_to_response

여러 AsyncResult를 배치로 처리하여 응답을 생성합니다.

```python
async def batch_async_results_to_response(
    async_results: List[AsyncResult[T, E]],
    max_concurrency: int = 10,
    success_status: int = 200,
    partial_success_status: int = 207,
    error_mapper: Optional[Callable[[E], HTTPException]] = None
) -> JSONResponse
```

#### 매개변수

- `async_results`: 처리할 AsyncResult 리스트
- `max_concurrency`: 최대 동시 처리 수
- `success_status`: 모든 작업 성공 시 상태 코드
- `partial_success_status`: 부분 성공 시 상태 코드
- `error_mapper`: 에러 매핑 함수

#### 반환값

배치 처리 결과가 포함된 JSONResponse

```json
{
  "results": [
    {"status": "success", "data": {...}},
    {"status": "error", "error": "..."}
  ],
  "summary": {
    "total": 10,
    "succeeded": 8,
    "failed": 2,
    "success_rate": 0.8
  }
}
```

#### 사용 예시

```python
@app.post("/users/batch")
async def process_users_batch(user_ids: List[str]):
    results = [process_user(user_id) for user_id in user_ids]
    
    return await batch_async_results_to_response(
        results,
        max_concurrency=5,
        partial_success_status=207
    )
```

## 클래스

### AsyncResultRouter

AsyncResult 전용 FastAPI 라우터 클래스입니다.

```python
class AsyncResultRouter(APIRouter):
    def __init__(
        self,
        error_mapper: Optional[Callable[[Any], HTTPException]] = None,
        success_headers: Optional[Dict[str, str]] = None,
        **kwargs
    )
```

#### 매개변수

- `error_mapper`: 기본 에러 매퍼 함수
- `success_headers`: 기본 성공 응답 헤더
- `**kwargs`: APIRouter의 기타 매개변수

#### 메서드

##### add_async_result_route

AsyncResult를 반환하는 엔드포인트를 자동으로 래핑합니다.

```python
def add_async_result_route(
    self,
    path: str,
    endpoint: Callable[..., Awaitable[AsyncResult[Any, Any]]],
    methods: List[str] = ["GET"],
    **kwargs
)
```

#### 사용 예시

```python
# AsyncResult 전용 라우터 생성
router = AsyncResultRouter(
    prefix="/api/v1",
    error_mapper=lambda e: HTTPException(status_code=500, detail=str(e))
)

# AsyncResult를 반환하는 함수를 자동 래핑
@router.get("/users/{user_id}")
async def get_user(user_id: str) -> AsyncResult[dict, str]:
    return await fetch_user(user_id)

# 메인 앱에 라우터 포함
app.include_router(router)
```

### AsyncResultEndpoint

AsyncResult 기반 엔드포인트의 기본 클래스입니다.

```python
class AsyncResultEndpoint:
    def __init__(
        self,
        error_mapper: Optional[Callable[[Any], HTTPException]] = None,
        success_headers: Optional[Dict[str, str]] = None,
        metadata_extractor: Optional[Callable[[Any], Dict[str, Any]]] = None
    )
```

#### 메서드

##### process

AsyncResult를 처리하여 응답을 생성합니다.

```python
async def process(
    self, 
    async_result: AsyncResult[T, E]
) -> JSONResponse
```

#### 사용 예시

```python
class UserEndpoint(AsyncResultEndpoint):
    def __init__(self):
        super().__init__(
            error_mapper=self.map_user_errors,
            success_headers={"X-API-Version": "v1"}
        )
    
    def map_user_errors(self, error: str) -> HTTPException:
        if "not found" in error:
            return HTTPException(status_code=404, detail="사용자 없음")
        return HTTPException(status_code=500, detail="서버 오류")

user_endpoint = UserEndpoint()

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    result = await fetch_user(user_id)
    return await user_endpoint.process(result)
```

### AsyncResultHTTPError

AsyncResult용 커스텀 HTTP 예외 클래스입니다.

```python
class AsyncResultHTTPError(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        original_error: Any = None,
        context: Optional[Dict[str, Any]] = None
    )
```

#### 매개변수

- `status_code`: HTTP 상태 코드
- `detail`: 에러 메시지
- `original_error`: 원본 에러 객체
- `context`: 추가 컨텍스트 정보

#### 사용 예시

```python
def create_user_error_mapper():
    def mapper(error: str) -> AsyncResultHTTPError:
        if "validation" in error:
            return AsyncResultHTTPError(
                status_code=400,
                detail="입력 데이터가 유효하지 않습니다",
                original_error=error,
                context={"error_type": "validation"}
            )
        elif "duplicate" in error:
            return AsyncResultHTTPError(
                status_code=409,
                detail="이미 존재하는 사용자입니다",
                original_error=error,
                context={"error_type": "conflict"}
            )
        else:
            return AsyncResultHTTPError(
                status_code=500,
                detail="서버 내부 오류",
                original_error=error,
                context={"error_type": "internal"}
            )
    return mapper
```

## 유틸리티 함수

### create_async_result_router

AsyncResult 전용 라우터를 생성하는 팩토리 함수입니다.

```python
def create_async_result_router(
    prefix: str = "",
    error_mapper: Optional[Callable[[Any], HTTPException]] = None,
    success_headers: Optional[Dict[str, str]] = None,
    **router_kwargs
) -> AsyncResultRouter
```

#### 사용 예시

```python
# 사용자 관리용 라우터 생성
user_router = create_async_result_router(
    prefix="/users",
    error_mapper=create_user_error_mapper(),
    success_headers={"X-Resource-Type": "user"}
)
```

### create_error_mapper

에러 매핑 함수를 생성하는 팩토리 함수입니다.

```python
def create_error_mapper(
    error_mappings: Dict[str, Callable[[str], HTTPException]],
    default_mapper: Optional[Callable[[str], HTTPException]] = None
) -> Callable[[str], HTTPException]
```

#### 매개변수

- `error_mappings`: 에러 타입별 매핑 함수 사전
- `default_mapper`: 기본 에러 매핑 함수

#### 사용 예시

```python
# 에러 매핑 함수 생성
error_mapper = create_error_mapper({
    "UserNotFound": lambda e: HTTPException(status_code=404, detail="사용자 없음"),
    "ValidationError": lambda e: HTTPException(status_code=400, detail="검증 실패"),
    "DatabaseError": lambda e: HTTPException(status_code=500, detail="DB 오류")
})

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    result = await fetch_user(user_id)
    return await async_result_to_response(result, error_mapper=error_mapper)
```

## 성능 및 최적화

### 동시성 제어

```python
from asyncio import Semaphore

# 동시 요청 수 제한
semaphore = Semaphore(10)

async def rate_limited_endpoint(request_data: dict):
    async with semaphore:
        result = await process_request(request_data)
        return await async_result_to_response(result)
```

### 캐싱 통합

```python
from functools import wraps
import asyncio

def cached_async_result(ttl: int = 300):
    cache = {}
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash((args, tuple(kwargs.items())))}"
            
            if cache_key in cache:
                return cache[cache_key]
            
            result = await func(*args, **kwargs)
            if result.is_success():
                cache[cache_key] = result
                # TTL 후 캐시 제거
                asyncio.create_task(remove_from_cache(cache_key, ttl))
            
            return result
        return wrapper
    return decorator
    
async def remove_from_cache(key: str, delay: int):
    await asyncio.sleep(delay)
    cache.pop(key, None)
```

## 모니터링 및 로깅

### 요청/응답 로깅

```python
import logging
from fastapi import Request, Response
import time

logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # 요청 로깅
    logger.info(f"Request started: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # 응답 로깅
    duration = time.time() - start_time
    logger.info(
        f"Request completed: {request.method} {request.url.path} "
        f"Status: {response.status_code} Duration: {duration:.3f}s"
    )
    
    return response
```

---

이 API를 통해 FastAPI와 AsyncResult를 효율적으로 통합할 수 있습니다. 자세한 사용 예시는 [AsyncResult Web Integration 가이드](../26-asyncresult-web-integration.md)를 참조하세요.