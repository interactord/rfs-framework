# AsyncResult Web Integration

RFS Framework v4.4.0에서 도입된 AsyncResult 웹 통합 기능에 대한 종합 가이드입니다.

## 개요

AsyncResult 웹 통합은 FastAPI와 AsyncResult 패턴을 원활하게 연결하여, 웹 애플리케이션에서 함수형 프로그래밍의 이점을 활용할 수 있게 합니다.

## 주요 기능

### 🚀 FastAPI AsyncResult 헬퍼

```python
from rfs.web.fastapi_helpers import async_result_to_response
from rfs.reactive.mono import Mono
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    # AsyncResult를 FastAPI 응답으로 자동 변환
    user_result = await get_user_from_db(user_id)
    return await async_result_to_response(user_result)
```

#### 주요 함수들

- `async_result_to_response()` - AsyncResult → JSONResponse 변환
- `async_result_to_paginated_response()` - 페이지네이션 응답 생성
- `create_async_result_router()` - AsyncResult 전용 라우터
- `batch_async_results_to_response()` - 배치 응답 처리

### 📊 AsyncResult 로깅

```python
from rfs.logging.async_logging import AsyncResultLogger, log_async_chain

logger = AsyncResultLogger()

@log_async_chain(logger, "user_processing")
async def process_user_data(user_data: dict):
    return await (
        validate_user_data(user_data)
        .bind(enrich_user_profile)
        .bind(save_to_database)
    )
```

#### 특징

- **민감 데이터 마스킹**: password, token, key 자동 마스킹
- **성능 메트릭**: p50, p90, p99, 최대/최소값 수집
- **구조화된 로깅**: JSON 형태의 구조화된 로그
- **체인 추적**: AsyncResult 체인 전체 추적

### 🧪 AsyncResult 테스팅

```python
from rfs.testing.async_result_testing import AsyncResultTestUtils, AsyncResultMockBuilder

class TestUserService:
    async def test_user_creation_success(self):
        # Mock 빌더로 테스트 시나리오 생성
        mock_result = AsyncResultMockBuilder.success({"id": 123, "name": "test"})
        
        # AsyncResult 검증 유틸리티
        await AsyncResultTestUtils.assert_success(
            mock_result, 
            expected_value={"id": 123, "name": "test"}
        )
    
    async def test_intermittent_failure(self):
        # 간헐적 실패 시나리오 테스트
        mock_result = AsyncResultMockBuilder.intermittent_failure(
            success_data={"status": "ok"}, 
            error_data="Connection failed",
            failure_rate=0.3
        )
        
        results = []
        for _ in range(10):
            result = await mock_result.build()
            results.append(result.is_success())
        
        # 약 30% 실패율 확인
        failure_count = sum(1 for success in results if not success)
        assert 2 <= failure_count <= 4  # 30% ± 10%
```

#### 테스팅 도구들

- `AsyncResultTestUtils` - 검증 및 매칭 유틸리티
- `AsyncResultMockBuilder` - Mock 객체 빌더
- `AsyncResultPerformanceTester` - 성능 테스트 도구

## 실제 사용 예시

### FastAPI 애플리케이션 구성

```python
from fastapi import FastAPI, HTTPException
from rfs.web.fastapi_helpers import (
    async_result_to_response,
    create_async_result_router,
    create_error_mapper
)
from rfs.logging.async_logging import AsyncResultLogger, log_async_chain
from rfs.core.result import Success, Failure

app = FastAPI(title="RFS AsyncResult Web Demo")
logger = AsyncResultLogger()

# 에러 매퍼 설정
error_mapper = create_error_mapper({
    "UserNotFound": lambda e: HTTPException(status_code=404, detail=str(e)),
    "ValidationError": lambda e: HTTPException(status_code=400, detail=str(e)),
    "DatabaseError": lambda e: HTTPException(status_code=500, detail="내부 서버 오류")
})

@app.get("/api/users/{user_id}")
@log_async_chain(logger, "get_user")
async def get_user_endpoint(user_id: str):
    """사용자 조회 API"""
    result = await get_user_with_profile(user_id)
    return await async_result_to_response(
        result, 
        error_mapper=error_mapper,
        success_headers={"X-Cache-Status": "MISS"}
    )

@app.get("/api/users")
@log_async_chain(logger, "list_users") 
async def list_users_endpoint(page: int = 1, page_size: int = 20):
    """사용자 목록 API (페이지네이션)"""
    result = await get_users_paginated(page, page_size)
    return await async_result_to_paginated_response(
        result,
        page=page,
        page_size=page_size
    )

async def get_user_with_profile(user_id: str):
    """사용자 정보와 프로필을 함께 조회"""
    return await (
        fetch_user(user_id)
        .bind(lambda user: enrich_with_profile(user))
        .bind(lambda user: add_permissions(user))
    )
```

### 로깅 설정

```python
from rfs.logging.async_logging import configure_async_result_logging

# AsyncResult 로깅 설정
configure_async_result_logging(
    log_level="INFO",
    mask_sensitive=True,  # 민감 데이터 마스킹 활성화
    collect_metrics=True,  # 성능 메트릭 수집
    output_format="json"   # JSON 형태로 출력
)
```

### 테스트 설정

```python
import pytest
from rfs.testing.async_result_testing import (
    AsyncResultTestUtils,
    AsyncResultMockBuilder,
    create_test_async_result
)

@pytest.fixture
async def user_service():
    return UserService()

class TestUserAPI:
    @pytest.mark.asyncio
    async def test_get_user_success(self, user_service):
        # 성공 케이스 테스트
        user_data = {"id": 123, "name": "테스트 사용자", "email": "test@example.com"}
        mock_result = create_test_async_result(success_value=user_data)
        
        await AsyncResultTestUtils.assert_success(
            mock_result,
            expected_value=user_data,
            timeout=1.0
        )
    
    @pytest.mark.asyncio
    async def test_get_user_performance(self, user_service):
        # 성능 테스트
        from rfs.testing.async_result_testing import AsyncResultPerformanceTester
        
        async def user_operation():
            return await user_service.get_user("123")
        
        metrics = await AsyncResultPerformanceTester.measure_operation(
            user_operation,
            iterations=100
        )
        
        assert metrics.p95_ms < 100  # 95%가 100ms 이하
        assert metrics.success_rate > 0.95  # 95% 이상 성공률
```

## 성능 최적화

### 배치 처리

```python
from rfs.web.fastapi_helpers import batch_async_results_to_response

@app.post("/api/users/batch")
async def process_users_batch(user_ids: List[str]):
    """여러 사용자를 배치로 처리"""
    results = [get_user_with_profile(user_id) for user_id in user_ids]
    
    return await batch_async_results_to_response(
        results,
        max_concurrency=10,  # 최대 10개 동시 처리
        success_status=200,
        partial_success_status=207
    )
```

### 캐싱 전략

```python
from functools import wraps
from rfs.cache import redis_cache

def cached_async_result(ttl: int = 300):
    """AsyncResult 캐싱 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash((args, tuple(kwargs.items())))}"
            
            # 캐시에서 확인
            cached = await redis_cache.get(cache_key)
            if cached:
                return Success(cached)
            
            # 함수 실행
            result = await func(*args, **kwargs)
            if result.is_success():
                await redis_cache.set(cache_key, result.unwrap(), ttl)
            
            return result
        return wrapper
    return decorator

@cached_async_result(ttl=600)  # 10분 캐싱
async def get_user_profile(user_id: str):
    return await fetch_user_profile_from_db(user_id)
```

## 에러 처리 전략

### 글로벌 에러 핸들러

```python
from fastapi import Request, Response
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """글로벌 예외 처리"""
    logger.error(f"Unhandled exception: {exc}", extra={
        "path": request.url.path,
        "method": request.method,
        "exception_type": type(exc).__name__
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "내부 서버 오류가 발생했습니다",
            "request_id": request.headers.get("X-Request-ID"),
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

### 회로 차단기 패턴

```python
from rfs.reactive.mono import Mono
from rfs.circuit_breaker import CircuitBreaker

# 외부 API 호출용 회로 차단기
external_api_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_duration=30,
    expected_exception=TimeoutError
)

@external_api_breaker
async def call_external_api(endpoint: str):
    """외부 API 호출 (회로 차단기 적용)"""
    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint, timeout=5.0)
        if response.status_code == 200:
            return Success(response.json())
        else:
            return Failure(f"API 호출 실패: {response.status_code}")
```

## 모니터링 및 관찰성

### 메트릭 수집

```python
from prometheus_client import Counter, Histogram, start_http_server

# 메트릭 정의
REQUEST_COUNT = Counter('rfs_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('rfs_request_duration_seconds', 'Request duration')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """메트릭 수집 미들웨어"""
    start_time = time.time()
    
    response = await call_next(request)
    
    # 메트릭 기록
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_DURATION.observe(time.time() - start_time)
    
    return response

# 메트릭 서버 시작
start_http_server(9090)
```

### 헬스체크

```python
@app.get("/health")
async def health_check():
    """애플리케이션 헬스체크"""
    checks = {
        "database": await check_database_connection(),
        "cache": await check_redis_connection(),
        "external_api": await check_external_api_status()
    }
    
    all_healthy = all(check.is_success() for check in checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": {
                name: "ok" if check.is_success() else "error" 
                for name, check in checks.items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

## 배포 및 운영

### Docker 설정

```dockerfile
FROM python:3.11-slim

# RFS Framework 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 애플리케이션 코드
COPY . /app
WORKDIR /app

# AsyncResult 로깅 설정
ENV RFS_LOG_LEVEL=INFO
ENV RFS_LOG_FORMAT=json
ENV RFS_MASK_SENSITIVE=true

# 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Kubernetes 배포

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rfs-web-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rfs-web-app
  template:
    metadata:
      labels:
        app: rfs-web-app
    spec:
      containers:
      - name: app
        image: rfs-web-app:4.4.0
        ports:
        - containerPort: 8080
        env:
        - name: RFS_ENV
          value: "production"
        - name: RFS_LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

## 다음 단계

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/) 참조
- [RFS HOF 사용 가이드](16-hof-usage-guide.md) 확인
- [결과 패턴 가이드](01-core-patterns.md) 학습
- [프로덕션 배포 가이드](05-deployment.md) 읽기

---

AsyncResult 웹 통합을 통해 함수형 프로그래밍의 강력함을 웹 애플리케이션에서 활용하세요! 🚀