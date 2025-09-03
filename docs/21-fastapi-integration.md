# FastAPI 통합 가이드

RFS Framework의 Result 패턴을 FastAPI와 완벽하게 통합하는 방법을 설명합니다. 자동 응답 변환, 에러 처리, 의존성 주입 등의 기능을 제공합니다.

## 개요

FastAPI 통합 모듈은 다음 핵심 기능을 제공합니다:

- **자동 Result → HTTP Response 변환**
- **통합된 에러 처리 시스템** 
- **Result 패턴 기반 의존성 주입**
- **성능 모니터링 미들웨어**

## 기본 설정

```python
from fastapi import FastAPI
from rfs.web.fastapi import setup_rfs_middleware
from rfs.web.fastapi.middleware import (
    ResultLoggingMiddleware,
    PerformanceMetricsMiddleware,
    ExceptionToResultMiddleware
)

app = FastAPI()

# RFS 미들웨어 설정
setup_rfs_middleware(app)

# 또는 개별 미들웨어 추가
app.add_middleware(ResultLoggingMiddleware)
app.add_middleware(PerformanceMetricsMiddleware)
app.add_middleware(ExceptionToResultMiddleware)
```

## 자동 응답 변환

### @handle_result 데코레이터

```python
from fastapi import FastAPI
from rfs.web.fastapi.response_helpers import handle_result, handle_flux_result
from rfs.web.fastapi.errors import APIError
from rfs.core.result import Result, Success, Failure

app = FastAPI()

@app.get("/users/{user_id}")
@handle_result
async def get_user(user_id: str) -> Result[dict, APIError]:
    """사용자 조회 - 자동으로 Result를 HTTP Response로 변환"""
    if user_id == "invalid":
        return Failure(APIError.not_found("User", user_id))
    
    user = {"id": user_id, "name": "John Doe", "email": "john@example.com"}
    return Success(user)

# 성공 시: 200 OK with JSON body
# 실패 시: 404 Not Found with error details
```

### MonoResult와 함께 사용

```python
from rfs.reactive.mono_result import MonoResult

@app.post("/users")
@handle_result
async def create_user(user_data: dict) -> Result[dict, APIError]:
    """사용자 생성 - MonoResult 체이닝과 자동 변환"""
    return await (
        MonoResult.from_async_result(lambda: validate_user_data(user_data))
        .bind_async_result(lambda data: save_user_to_db(data))
        .map_result(lambda user: serialize_user(user))
        .map_error(lambda e: APIError.from_service_error(e))
        .timeout(10.0)
        .to_result()
    )
```

### 배치 처리 - @handle_flux_result

```python
@app.post("/users/batch")
@handle_flux_result(partial_success=True, include_errors=True)
async def create_users_batch(users_data: List[dict]) -> FluxResult[dict, APIError]:
    """배치 사용자 생성 - FluxResult 자동 변환"""
    return await (
        FluxResult.from_iterable_async(users_data, create_single_user)
        .filter_results(lambda user: user.get("active", True))
        .batch_collect(batch_size=5, max_concurrent=3)
    )

# 응답 형태:
# {
#   "results": [...],  # 성공한 결과들
#   "errors": [...],   # 실패한 결과들 (include_errors=True)
#   "summary": {
#     "total": 10,
#     "success": 8,
#     "failure": 2,
#     "success_rate": 0.8
#   }
# }
```

## APIError 시스템

### 표준 에러 코드

```python
from rfs.web.fastapi.errors import APIError, ErrorCode

# 사전 정의된 에러 생성
not_found_error = APIError.not_found("User", "123")
validation_error = APIError.validation_failed("Invalid email format", {"field": "email"})
auth_error = APIError.unauthorized("Invalid token")
server_error = APIError.internal_server_error("Database connection failed")

# 커스텀 에러 생성
custom_error = APIError(
    code=ErrorCode.BUSINESS_RULE_VIOLATION,
    message="계정 잔액이 부족합니다",
    details={"balance": 1000, "required": 2000},
    http_status_code=422
)
```

### 서비스 에러 자동 변환

```python
class UserService:
    async def get_user(self, user_id: str) -> Result[User, str]:
        # 서비스에서 string 에러 반환
        if not user_id:
            return Failure("Invalid user ID")
        # ... 로직
        return Success(user)

@app.get("/users/{user_id}")
@handle_result
async def get_user(user_id: str) -> Result[dict, APIError]:
    result = await user_service.get_user(user_id)
    # 서비스 에러를 APIError로 자동 변환
    return result.map_error(lambda e: APIError.from_service_error(e))
```

## 의존성 주입

### Result 기반 의존성

```python
from rfs.web.fastapi.dependencies import ResultDependency, inject_result_service

# 의존성 클래스 정의
class UserServiceDependency(ResultDependency[UserService]):
    async def __call__(self) -> Result[UserService, APIError]:
        try:
            # 의존성 생성 로직
            service = UserService(db_connection=get_db())
            return Success(service)
        except Exception as e:
            return Failure(APIError.internal_server_error(f"Service initialization failed: {e}"))

# 의존성 사용
@app.get("/users/{user_id}")
@handle_result
async def get_user(
    user_id: str,
    user_service: UserService = Depends(UserServiceDependency())
) -> Result[dict, APIError]:
    return await user_service.get_user(user_id)
```

### 서비스 레지스트리 사용

```python
from rfs.web.fastapi.dependencies import ServiceRegistry, inject_result_service

# 서비스 등록
registry = ServiceRegistry()
registry.register("user_service", UserService(db_connection))
registry.register("auth_service", AuthService(token_provider))

# 의존성 주입
@app.get("/users/{user_id}")
@inject_result_service("user_service")
async def get_user(user_id: str, service: UserService) -> Result[dict, APIError]:
    return await service.get_user(user_id)
```

## 미들웨어 시스템

### 로깅 미들웨어

```python
from rfs.web.fastapi.middleware import ResultLoggingMiddleware

app.add_middleware(
    ResultLoggingMiddleware,
    log_requests=True,
    log_responses=True,
    log_errors=True,
    exclude_paths=["/health", "/metrics"]
)

# 자동으로 다음 정보를 로깅:
# - Request ID (correlation ID)
# - 요청/응답 페이로드
# - 처리 시간
# - 에러 상세 정보
```

### 성능 모니터링 미들웨어

```python
from rfs.web.fastapi.middleware import PerformanceMetricsMiddleware

app.add_middleware(
    PerformanceMetricsMiddleware,
    track_response_times=True,
    track_payload_sizes=True,
    alert_slow_requests=True,
    slow_request_threshold=5.0  # 5초 초과 시 경고
)

# 자동으로 다음 메트릭 수집:
# - 엔드포인트별 응답 시간
# - 요청/응답 크기
# - 에러율
# - 처리량(throughput)
```

### 예외 변환 미들웨어

```python
from rfs.web.fastapi.middleware import ExceptionToResultMiddleware

app.add_middleware(ExceptionToResultMiddleware)

# 캐치되지 않은 예외를 자동으로 APIError로 변환
# - ValidationError → APIError.validation_failed()
# - PermissionError → APIError.forbidden()
# - TimeoutError → APIError.timeout()
# - 기타 → APIError.internal_server_error()
```

## 실용적인 예제들

### 인증이 필요한 엔드포인트

```python
from rfs.web.fastapi.dependencies import AuthDependency

class RequireAuth(AuthDependency):
    async def __call__(self, authorization: str = Header(...)) -> Result[User, APIError]:
        if not authorization.startswith("Bearer "):
            return Failure(APIError.unauthorized("Invalid token format"))
        
        token = authorization.split(" ")[1]
        result = await auth_service.verify_token(token)
        
        return result.map_error(lambda e: APIError.unauthorized(f"Token verification failed: {e}"))

@app.get("/protected")
@handle_result
async def protected_endpoint(current_user: User = Depends(RequireAuth())) -> Result[dict, APIError]:
    return Success({"message": f"Hello {current_user.name}!"})
```

### 파일 업로드 처리

```python
from fastapi import UploadFile, File

@app.post("/upload")
@handle_result
async def upload_file(file: UploadFile = File(...)) -> Result[dict, APIError]:
    return await (
        MonoResult.from_async_result(lambda: validate_file(file))
        .bind_async_result(lambda f: save_file_to_storage(f))
        .bind_async_result(lambda path: process_file_async(path))
        .map_result(lambda result: {"file_id": result.id, "status": "processed"})
        .map_error(lambda e: APIError.from_service_error(e))
        .timeout(300.0)  # 5분 타임아웃
        .to_result()
    )
```

### 페이지네이션과 필터링

```python
from typing import Optional

@app.get("/users")
@handle_result
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
    search: Optional[str] = Query(None)
) -> Result[dict, APIError]:
    
    filters = UserFilters(
        active_only=active_only,
        search_term=search,
        page=page,
        page_size=size
    )
    
    return await (
        MonoResult.from_async_result(lambda: user_service.list_users(filters))
        .map_result(lambda result: {
            "users": result.items,
            "pagination": {
                "page": page,
                "size": size,
                "total": result.total_count,
                "pages": result.total_pages
            }
        })
        .map_error(lambda e: APIError.from_service_error(e))
        .to_result()
    )
```

## 테스팅

### FastAPI 테스트 클라이언트와 함께

```python
import pytest
from fastapi.testclient import TestClient
from rfs.testing.result_helpers import assert_result_success, mock_result_service

@pytest.fixture
def client():
    return TestClient(app)

def test_get_user_success(client):
    with mock_result_service("user_service", "get_user") as mock_svc:
        mock_svc.return_success({"id": "123", "name": "Test User"})
        
        response = client.get("/users/123")
        
        assert response.status_code == 200
        assert response.json()["id"] == "123"
        mock_svc.assert_called_once_with("123")

def test_get_user_not_found(client):
    with mock_result_service("user_service", "get_user") as mock_svc:
        mock_svc.return_failure(APIError.not_found("User", "123"))
        
        response = client.get("/users/123")
        
        assert response.status_code == 404
        assert "User" in response.json()["message"]
```

## 성능 최적화

### 응답 캐싱

```python
from functools import lru_cache

@lru_cache(maxsize=1000, typed=True)
async def cached_user_lookup(user_id: str) -> Result[dict, APIError]:
    return await user_service.get_user(user_id)

@app.get("/users/{user_id}/cached")
@handle_result
async def get_cached_user(user_id: str) -> Result[dict, APIError]:
    return await cached_user_lookup(user_id)
```

### 배경 작업

```python
from fastapi import BackgroundTasks

@app.post("/users/{user_id}/notifications")
@handle_result
async def send_notification(
    user_id: str,
    message: str,
    background_tasks: BackgroundTasks
) -> Result[dict, APIError]:
    
    # 즉시 응답
    background_tasks.add_task(send_notification_async, user_id, message)
    return Success({"message": "Notification queued"})

async def send_notification_async(user_id: str, message: str):
    result = await (
        MonoResult.from_async_result(lambda: notification_service.send(user_id, message))
        .retry_on_failure(max_retries=3)
        .to_result()
    )
    
    if result.is_failure():
        logger.error(f"Failed to send notification: {result.unwrap_error()}")
```

## 모범 사례

1. **일관된 에러 처리**: 모든 엔드포인트에서 APIError 사용
2. **적절한 HTTP 상태 코드**: ErrorCode에서 자동 매핑 활용
3. **타임아웃 설정**: 모든 외부 호출에 타임아웃 적용
4. **로깅과 모니터링**: 미들웨어를 통한 자동 로깅 활용
5. **테스트 가능성**: Result 패턴으로 쉬운 모킹과 테스트

## 추가 자료

- [MonoResult 가이드](20-monoresult-guide.md)
- [Result 패턴](01-core-patterns.md)
- [API 레퍼런스](api/web/fastapi.md)