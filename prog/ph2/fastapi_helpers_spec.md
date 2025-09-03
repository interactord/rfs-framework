# FastAPI 헬퍼 상세 사양서

**문서 버전**: 1.0  
**작성일**: 2025-09-03  
**상태**: 설계 완료

---

## 📋 개요

Phase 1에서 완성된 MonoResult/FluxResult를 FastAPI와 완벽하게 통합하기 위한 헬퍼 시스템의 상세 사양입니다. 실제 웹 애플리케이션 개발에서 Result 패턴을 자연스럽게 활용할 수 있도록 지원합니다.

---

## 🎯 1. Response Helpers (`response_helpers.py`)

### 1.1 @handle_result 데코레이터

**목적**: MonoResult 또는 일반 Result를 HTTP 응답으로 자동 변환

#### 구현 사양
```python
from typing import Callable, Any, Union
from functools import wraps
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from rfs.core.result import Result
from rfs.reactive.mono_result import MonoResult

def handle_result(func: Callable) -> Callable:
    """
    Result 또는 MonoResult를 반환하는 함수를 FastAPI 응답으로 자동 변환
    
    지원하는 반환 타입:
    - Result[T, APIError] → JSONResponse 또는 HTTPException
    - MonoResult[T, APIError] → 자동으로 .to_result() 호출 후 변환
    - Result[T, str] → APIError로 자동 래핑 후 변환
    
    Example:
        @app.get("/users/{user_id}")
        @handle_result
        async def get_user(user_id: str) -> Result[User, APIError]:
            return await user_service.get_user(user_id)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Union[JSONResponse, HTTPException]:
        try:
            result = await func(*args, **kwargs)
            
            # MonoResult인 경우 Result로 변환
            if hasattr(result, 'to_result'):
                result = await result.to_result()
            
            if result.is_success():
                success_data = result.unwrap()
                
                # Pydantic 모델인 경우 dict() 호출
                if hasattr(success_data, 'dict'):
                    response_data = success_data.dict()
                else:
                    response_data = success_data
                
                return JSONResponse(
                    content=response_data,
                    status_code=200
                )
            else:
                error = result.unwrap_error()
                
                # APIError가 아닌 경우 자동 변환
                if not isinstance(error, APIError):
                    error = APIError.internal_server_error(str(error))
                
                # HTTPException으로 변환
                raise HTTPException(
                    status_code=error.status_code,
                    detail={
                        "code": error.code,
                        "message": error.message,
                        "details": error.details
                    }
                )
                
        except Exception as e:
            # 예상치 못한 예외를 APIError로 변환
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            api_error = APIError.internal_server_error("예상치 못한 오류가 발생했습니다")
            raise HTTPException(
                status_code=api_error.status_code,
                detail={
                    "code": api_error.code,
                    "message": api_error.message,
                    "details": {"original_error": str(e)}
                }
            )
    
    return wrapper
```

### 1.2 @handle_flux_result 데코레이터

**목적**: FluxResult를 배치 응답으로 자동 변환

#### 구현 사양
```python
from rfs.reactive.flux_result import FluxResult

def handle_flux_result(
    partial_success: bool = True,
    include_errors: bool = False
) -> Callable:
    """
    FluxResult를 배치 처리 HTTP 응답으로 자동 변환
    
    Args:
        partial_success: 부분 성공을 허용할지 여부 (기본: True)
        include_errors: 응답에 에러 정보를 포함할지 여부 (기본: False)
    
    Response Format:
        {
            "success": true/false,
            "total": 전체 처리된 항목 수,
            "successful": 성공한 항목 수,
            "failed": 실패한 항목 수,
            "success_rate": 성공률 (0.0 ~ 1.0),
            "results": [...],  // 성공한 결과들
            "errors": [...]    // include_errors=True일 때만 포함
        }
    
    Example:
        @app.post("/users/batch")
        @handle_flux_result(partial_success=True, include_errors=True)
        async def create_users_batch(
            users: List[UserCreateRequest]
        ) -> FluxResult[User, APIError]:
            return await user_service.create_users_batch(users)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> JSONResponse:
            try:
                flux_result = await func(*args, **kwargs)
                
                # 통계 정보 수집
                total_count = flux_result.count_total()
                success_count = flux_result.count_success()
                failure_count = flux_result.count_failures()
                success_rate = flux_result.success_rate()
                
                # 성공한 결과들 수집
                success_values = flux_result.collect_success_values()
                successful_results = await success_values.to_result()
                
                response_data = {
                    "success": success_count > 0 and (partial_success or failure_count == 0),
                    "total": total_count,
                    "successful": success_count,
                    "failed": failure_count,
                    "success_rate": success_rate,
                    "results": successful_results.unwrap() if successful_results.is_success() else []
                }
                
                # 에러 정보 포함 (옵션)
                if include_errors and failure_count > 0:
                    error_values = flux_result.collect_error_values()
                    error_results = await error_values.to_result()
                    response_data["errors"] = error_results.unwrap() if error_results.is_success() else []
                
                # HTTP 상태 코드 결정
                if failure_count == 0:
                    status_code = 200  # 모든 작업 성공
                elif success_count > 0 and partial_success:
                    status_code = 207  # Multi-Status (부분 성공)
                else:
                    status_code = 400  # 전체 실패 또는 부분 성공 불허용
                
                return JSONResponse(
                    content=response_data,
                    status_code=status_code
                )
                
            except Exception as e:
                logger.exception(f"Unexpected error in batch operation {func.__name__}: {e}")
                api_error = APIError.internal_server_error("배치 처리 중 예상치 못한 오류가 발생했습니다")
                raise HTTPException(
                    status_code=api_error.status_code,
                    detail={
                        "code": api_error.code,
                        "message": api_error.message,
                        "details": {"original_error": str(e)}
                    }
                )
        
        return wrapper
    
    return decorator
```

---

## 🚨 2. Error Handling (`errors.py`)

### 2.1 APIError 클래스

**목적**: 웹 API 전용 에러 표현 및 HTTP 상태 코드 매핑

#### 구현 사양
```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
from enum import Enum

class ErrorCode(str, Enum):
    """표준 API 에러 코드"""
    # Client Errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Server Errors (5xx)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

@dataclass
class APIError:
    """웹 API 전용 에러 클래스"""
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = field(default_factory=dict)
    status_code: int = 500
    
    def __post_init__(self):
        """상태 코드 자동 매핑"""
        if self.status_code == 500:  # 기본값인 경우에만 자동 매핑
            self.status_code = self._get_default_status_code()
    
    def _get_default_status_code(self) -> int:
        """에러 코드에 따른 기본 HTTP 상태 코드 매핑"""
        code_to_status = {
            ErrorCode.VALIDATION_ERROR: 400,
            ErrorCode.UNAUTHORIZED: 401,
            ErrorCode.FORBIDDEN: 403,
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.CONFLICT: 409,
            ErrorCode.RATE_LIMITED: 429,
            ErrorCode.INTERNAL_SERVER_ERROR: 500,
            ErrorCode.SERVICE_UNAVAILABLE: 503,
            ErrorCode.TIMEOUT_ERROR: 504,
            ErrorCode.DATABASE_ERROR: 500,
        }
        return code_to_status.get(self.code, 500)
    
    # === 클래스 메서드 팩토리들 ===
    
    @classmethod
    def not_found(cls, resource: str, resource_id: Optional[str] = None) -> "APIError":
        """리소스를 찾을 수 없는 경우"""
        message = f"{resource}을(를) 찾을 수 없습니다"
        details = {"resource": resource}
        if resource_id:
            details["resource_id"] = resource_id
        
        return cls(
            code=ErrorCode.NOT_FOUND,
            message=message,
            details=details
        )
    
    @classmethod
    def validation_error(cls, field_errors: Dict[str, str]) -> "APIError":
        """입력값 검증 실패"""
        return cls(
            code=ErrorCode.VALIDATION_ERROR,
            message="입력값이 유효하지 않습니다",
            details={"field_errors": field_errors}
        )
    
    @classmethod
    def unauthorized(cls, reason: Optional[str] = None) -> "APIError":
        """인증 실패"""
        message = "인증이 필요합니다"
        details = {}
        if reason:
            details["reason"] = reason
        
        return cls(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            details=details
        )
    
    @classmethod
    def forbidden(cls, resource: str, action: str) -> "APIError":
        """권한 부족"""
        return cls(
            code=ErrorCode.FORBIDDEN,
            message=f"{resource}에 대한 {action} 권한이 없습니다",
            details={"resource": resource, "action": action}
        )
    
    @classmethod
    def conflict(cls, resource: str, reason: str) -> "APIError":
        """리소스 충돌"""
        return cls(
            code=ErrorCode.CONFLICT,
            message=f"{resource} 충돌이 발생했습니다: {reason}",
            details={"resource": resource, "reason": reason}
        )
    
    @classmethod
    def internal_server_error(cls, message: str = "내부 서버 오류가 발생했습니다") -> "APIError":
        """내부 서버 에러"""
        return cls(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message
        )
    
    @classmethod
    def timeout_error(cls, operation: str, timeout_seconds: float) -> "APIError":
        """타임아웃 에러"""
        return cls(
            code=ErrorCode.TIMEOUT_ERROR,
            message=f"{operation} 작업이 시간 초과되었습니다 ({timeout_seconds}초)",
            details={"operation": operation, "timeout_seconds": timeout_seconds}
        )
    
    @classmethod
    def from_exception(cls, exception: Exception) -> "APIError":
        """일반 예외를 APIError로 변환"""
        error_type = type(exception).__name__
        
        # 특정 예외 타입에 따른 매핑
        if "NotFound" in error_type or "DoesNotExist" in error_type:
            return cls.not_found("리소스", str(exception))
        elif "ValidationError" in error_type or "ValueError" in error_type:
            return cls.validation_error({"general": str(exception)})
        elif "PermissionError" in error_type:
            return cls.forbidden("리소스", "접근")
        elif "TimeoutError" in error_type:
            return cls.timeout_error("요청", 30.0)
        else:
            return cls.internal_server_error(f"예상치 못한 오류: {str(exception)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code
        }
```

---

## 🔗 3. Dependencies (`dependencies.py`)

### 3.1 Result 기반 의존성 주입

#### 구현 사양
```python
from typing import Callable, Type, TypeVar, Optional
from fastapi import Depends, HTTPException
from rfs.core.result import Result
from rfs.reactive.mono_result import MonoResult

T = TypeVar('T')
E = TypeVar('E')

class ResultDependency:
    """Result 패턴을 지원하는 의존성 주입 래퍼"""
    
    def __init__(self, dependency: Callable[..., Result[T, E]]):
        self.dependency = dependency
    
    async def __call__(self, *args, **kwargs) -> T:
        """
        의존성을 실행하고 Result를 해제
        실패 시 자동으로 HTTPException 발생
        """
        result = await self.dependency(*args, **kwargs)
        
        if result.is_success():
            return result.unwrap()
        else:
            error = result.unwrap_error()
            
            # APIError인 경우 적절한 HTTP 응답으로 변환
            if isinstance(error, APIError):
                raise HTTPException(
                    status_code=error.status_code,
                    detail=error.to_dict()
                )
            else:
                # 일반 에러는 내부 서버 에러로 처리
                api_error = APIError.from_exception(Exception(str(error)))
                raise HTTPException(
                    status_code=api_error.status_code,
                    detail=api_error.to_dict()
                )

def result_dependency(dependency: Callable[..., Result[T, E]]) -> Callable[..., T]:
    """
    Result를 반환하는 의존성을 FastAPI 의존성으로 변환
    
    Example:
        async def get_current_user(token: str) -> Result[User, APIError]:
            # 사용자 인증 로직
            pass
        
        @app.get("/profile")
        async def get_profile(
            current_user: User = Depends(result_dependency(get_current_user))
        ):
            return current_user
    """
    return ResultDependency(dependency)

async def inject_result_service(
    service_class: Type[T], 
    *args, 
    **kwargs
) -> Result[T, APIError]:
    """
    서비스 클래스를 Result로 래핑하여 주입
    
    Example:
        @app.get("/users/{user_id}")
        async def get_user(
            user_id: str,
            user_service: UserService = Depends(
                lambda: inject_result_service(UserService)
            )
        ) -> Result[User, APIError]:
            return await user_service.get_user(user_id)
    """
    try:
        service_instance = service_class(*args, **kwargs)
        return Success(service_instance)
    except Exception as e:
        logger.exception(f"Failed to inject service {service_class.__name__}: {e}")
        return Failure(APIError.internal_server_error(
            f"서비스 주입 실패: {service_class.__name__}"
        ))
```

---

## ⚡ 4. Middleware (`middleware.py`)

### 4.1 Result 로깅 미들웨어

#### 구현 사양
```python
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)

class ResultLoggingMiddleware(BaseHTTPMiddleware):
    """Result 패턴 기반 API의 로깅 및 모니터링"""
    
    def __init__(self, app, log_level: str = "INFO"):
        super().__init__(app)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 요청 시작 시간 기록
        start_time = time.time()
        
        # 요청 로깅
        logger.log(
            self.log_level,
            f"API 요청 시작: {request.method} {request.url.path}"
        )
        
        try:
            response = await call_next(request)
            
            # 응답 시간 계산
            process_time = time.time() - start_time
            
            # 성공/실패 판단
            is_success = 200 <= response.status_code < 400
            
            # 응답 로깅
            logger.log(
                self.log_level,
                f"API 응답 완료: {request.method} {request.url.path} "
                f"- 상태: {response.status_code} "
                f"- 처리시간: {process_time:.3f}초 "
                f"- 결과: {'성공' if is_success else '실패'}"
            )
            
            # 성능 모니터링을 위한 헤더 추가
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Result-Status"] = "success" if is_success else "error"
            
            return response
            
        except Exception as e:
            # 예외 로깅
            process_time = time.time() - start_time
            logger.error(
                f"API 예외 발생: {request.method} {request.url.path} "
                f"- 처리시간: {process_time:.3f}초 "
                f"- 예외: {type(e).__name__}: {str(e)}"
            )
            raise

class ExceptionToResultMiddleware(BaseHTTPMiddleware):
    """예상치 못한 예외를 Result 패턴으로 자동 변환"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
            
        except HTTPException:
            # FastAPI의 HTTPException은 그대로 전파
            raise
            
        except Exception as e:
            # 예상치 못한 예외를 APIError로 변환
            logger.exception(f"Unhandled exception in {request.url.path}: {e}")
            
            api_error = APIError.from_exception(e)
            raise HTTPException(
                status_code=api_error.status_code,
                detail=api_error.to_dict()
            )
```

---

## 🔧 5. Type Aliases (`types.py`)

### 5.1 편의 타입 정의

#### 구현 사양
```python
from typing import TypeVar, Union
from rfs.core.result import Result
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult
from .errors import APIError

T = TypeVar('T')

# FastAPI 전용 Result 타입 별칭
FastAPIResult = Result[T, APIError]
FastAPIMonoResult = MonoResult[T, APIError] 
FastAPIFluxResult = FluxResult[T, APIError]

# 응답 타입 별칭 (문서화용)
SuccessResponse = T
ErrorResponse = APIError

# 편의 함수들
def success_response(data: T) -> FastAPIResult[T]:
    """성공 응답 생성 헬퍼"""
    from rfs.core.result import Success
    return Success(data)

def error_response(error: Union[APIError, str, Exception]) -> FastAPIResult[T]:
    """에러 응답 생성 헬퍼"""
    from rfs.core.result import Failure
    
    if isinstance(error, APIError):
        return Failure(error)
    elif isinstance(error, str):
        return Failure(APIError.internal_server_error(error))
    elif isinstance(error, Exception):
        return Failure(APIError.from_exception(error))
    else:
        return Failure(APIError.internal_server_error("알 수 없는 오류"))

async def mono_success(data: T) -> FastAPIMonoResult[T]:
    """MonoResult 성공 응답 생성 헬퍼"""
    return MonoResult.from_value(data)

async def mono_error(error: Union[APIError, str, Exception]) -> FastAPIMonoResult[T]:
    """MonoResult 에러 응답 생성 헬퍼"""
    if isinstance(error, APIError):
        api_error = error
    elif isinstance(error, str):
        api_error = APIError.internal_server_error(error)
    elif isinstance(error, Exception):
        api_error = APIError.from_exception(error)
    else:
        api_error = APIError.internal_server_error("알 수 없는 오류")
    
    return MonoResult.from_error(api_error)
```

---

## 📊 성능 및 품질 요구사항

### 성능 요구사항
- 데코레이터 오버헤드: <10ms
- 메모리 사용량 증가: <50MB
- CPU 오버헤드: <5%

### 품질 요구사항
- 타입 힌트 100% 커버리지
- 단위 테스트 커버리지 90% 이상
- MyPy 타입 검사 0 에러
- 문서화 완전성 95% 이상

### 호환성 요구사항
- FastAPI 0.100+ 지원
- Python 3.9+ 지원
- Phase 1 MonoResult/FluxResult와 100% 호환
- 기존 RFS Framework와 완전 통합

---

**문서 상태**: 설계 완료, 구현 대기  
**다음 단계**: 실제 구현 및 단위 테스트 작성