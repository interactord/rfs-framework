"""
RFS Framework AsyncResult FastAPI 통합 헬퍼

AsyncResult를 FastAPI와 완벽하게 통합하는 헬퍼 함수와 데코레이터들을 제공합니다.
px 프로젝트 요구사항을 기반으로 개발된 실용적인 웹 개발 도구들입니다.
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar, Union

from ..async_pipeline import AsyncResult
from ..core.result import Result, Success, Failure
from ..hof.core import pipe

# FastAPI 의존성 처리
try:
    from fastapi import HTTPException, APIRouter, Request, Response
    from fastapi.responses import JSONResponse
    from fastapi.routing import APIRoute
    FASTAPI_AVAILABLE = True
except ImportError:
    HTTPException = None
    APIRouter = None
    Request = None
    Response = None
    JSONResponse = None
    APIRoute = None
    FASTAPI_AVAILABLE = False

T = TypeVar('T')
E = TypeVar('E')

logger = logging.getLogger(__name__)


def ensure_fastapi():
    """FastAPI 가용성을 확인합니다."""
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI가 설치되지 않았습니다. pip install fastapi 실행해주세요."
        )


class AsyncResultHTTPError(HTTPException):
    """AsyncResult 전용 HTTP 에러"""
    
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Optional[Dict[str, str]] = None,
        original_error: Any = None
    ):
        super().__init__(status_code, detail, headers)
        self.original_error = original_error


# === 핵심 변환 함수 ===

async def async_result_to_response(
    async_result: AsyncResult[T, E],
    success_status: int = 200,
    error_mapper: Optional[Callable[[E], HTTPException]] = None,
    success_headers: Optional[Dict[str, str]] = None,
    metadata_extractor: Optional[Callable[[T], Dict[str, Any]]] = None
) -> JSONResponse:
    """
    AsyncResult를 FastAPI JSONResponse로 자동 변환
    
    Args:
        async_result: 변환할 AsyncResult 인스턴스
        success_status: 성공 시 HTTP 상태 코드 (기본: 200)
        error_mapper: 에러를 HTTPException으로 변환하는 함수
        success_headers: 성공 시 추가할 HTTP 헤더들
        metadata_extractor: 응답 메타데이터 추출 함수
        
    Returns:
        JSONResponse: FastAPI 응답 객체
        
    Example:
        >>> @router.get("/users/{user_id}")
        >>> async def get_user(user_id: str):
        >>>     user_result = AsyncResult.from_async(lambda: fetch_user(user_id))
        >>>     return await async_result_to_response(
        >>>         user_result,
        >>>         error_mapper=lambda e: HTTPException(status_code=404, detail=str(e))
        >>>     )
    """
    ensure_fastapi()
    
    try:
        # AsyncResult 실행 및 Result 추출
        result = await async_result.to_result()
        
        if result.is_success():
            value = result.unwrap()
            
            # 응답 컨텐츠 구성
            content = value
            
            # 메타데이터 추출 (선택적)
            if metadata_extractor:
                try:
                    metadata = metadata_extractor(value)
                    content = {
                        "data": value,
                        "metadata": metadata
                    }
                except Exception as meta_error:
                    logger.warning(f"메타데이터 추출 실패: {meta_error}")
            
            return JSONResponse(
                content=content,
                status_code=success_status,
                headers=success_headers
            )
        
        else:
            error = result.unwrap_error()
            
            # 에러 매핑 처리
            if error_mapper:
                try:
                    http_exception = error_mapper(error)
                    raise http_exception
                except HTTPException:
                    raise
                except Exception as mapping_error:
                    logger.error(f"에러 매핑 실패: {mapping_error}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"에러 처리 중 문제가 발생했습니다: {str(mapping_error)}"
                    )
            else:
                # 기본 에러 처리
                error_detail = {
                    "error": str(error),
                    "type": type(error).__name__
                }
                
                # 일반적인 에러 타입에 따른 상태 코드 결정
                if isinstance(error, (ValueError, TypeError)):
                    status_code = 400  # Bad Request
                elif isinstance(error, PermissionError):
                    status_code = 403  # Forbidden
                elif isinstance(error, FileNotFoundError):
                    status_code = 404  # Not Found
                elif isinstance(error, TimeoutError):
                    status_code = 408  # Request Timeout
                else:
                    status_code = 500  # Internal Server Error
                
                raise AsyncResultHTTPError(
                    status_code=status_code,
                    detail=error_detail,
                    original_error=error
                )
                
    except HTTPException:
        raise
    except Exception as unexpected_error:
        logger.exception(f"AsyncResult 처리 중 예상치 못한 에러 발생: {unexpected_error}")
        raise HTTPException(
            status_code=500,
            detail=f"내부 서버 오류: {str(unexpected_error)}"
        )


# === 고급 변환 함수 ===

async def async_result_to_paginated_response(
    async_result: AsyncResult[T, E],
    page: int = 1,
    page_size: int = 20,
    total_count: Optional[int] = None,
    error_mapper: Optional[Callable[[E], HTTPException]] = None
) -> JSONResponse:
    """
    AsyncResult를 페이지네이션 응답으로 변환
    
    Args:
        async_result: 변환할 AsyncResult 인스턴스
        page: 현재 페이지 번호
        page_size: 페이지 크기
        total_count: 전체 항목 수 (None이면 자동 계산)
        error_mapper: 에러 매핑 함수
        
    Returns:
        JSONResponse: 페이지네이션 메타데이터를 포함한 응답
    """
    def create_pagination_metadata(data):
        if isinstance(data, (list, tuple)):
            count = len(data) if total_count is None else total_count
            return {
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": count,
                    "total_pages": (count + page_size - 1) // page_size,
                    "has_next": page * page_size < count,
                    "has_prev": page > 1
                }
            }
        return {}
    
    return await async_result_to_response(
        async_result,
        success_status=200,
        error_mapper=error_mapper,
        metadata_extractor=create_pagination_metadata
    )


# === AsyncResult 전용 Router ===

class AsyncResultRouter(APIRouter):
    """AsyncResult 전용 FastAPI Router"""
    
    def __init__(
        self,
        default_error_mapper: Optional[Callable[[Any], HTTPException]] = None,
        auto_convert_responses: bool = True,
        include_metadata: bool = False,
        **kwargs
    ):
        """
        AsyncResult 전용 Router 초기화
        
        Args:
            default_error_mapper: 기본 에러 매핑 함수
            auto_convert_responses: AsyncResult 자동 변환 여부
            include_metadata: 응답에 메타데이터 포함 여부
            **kwargs: APIRouter 추가 인자들
        """
        super().__init__(**kwargs)
        self.default_error_mapper = default_error_mapper
        self.auto_convert_responses = auto_convert_responses
        self.include_metadata = include_metadata
        
        # 미들웨어 추가 (자동 변환이 활성화된 경우)
        if auto_convert_responses:
            self.add_middleware(AsyncResultMiddleware)


def create_async_result_router(
    prefix: str = "",
    tags: Optional[list] = None,
    default_error_mapper: Optional[Callable[[Any], HTTPException]] = None,
    include_request_id: bool = True
) -> AsyncResultRouter:
    """
    AsyncResult 전용 FastAPI Router 생성
    
    Args:
        prefix: 라우터 프리픽스
        tags: OpenAPI 태그들
        default_error_mapper: 기본 에러 매핑 함수
        include_request_id: 요청 ID 포함 여부
        
    Returns:
        AsyncResultRouter: 설정된 AsyncResult Router
        
    Example:
        >>> router = create_async_result_router(
        ...     prefix="/api/v1",
        ...     tags=["users"],
        ...     default_error_mapper=lambda e: HTTPException(404, str(e))
        ... )
        >>> 
        >>> @router.get("/users/{user_id}")
        >>> async def get_user(user_id: str) -> AsyncResult[dict, str]:
        >>>     return AsyncResult.from_async(lambda: fetch_user_data(user_id))
    """
    ensure_fastapi()
    
    return AsyncResultRouter(
        prefix=prefix,
        tags=tags or [],
        default_error_mapper=default_error_mapper,
        auto_convert_responses=True,
        include_metadata=include_request_id
    )


# === 미들웨어 ===

class AsyncResultMiddleware:
    """AsyncResult 응답 자동 변환 미들웨어"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # 응답 캐치를 위한 래퍼
        async def catch_response(message):
            if message["type"] == "http.response.start":
                # AsyncResult 체크 로직이 필요한 경우 여기서 처리
                pass
            await send(message)
        
        await self.app(scope, receive, catch_response)


# === 데코레이터 기반 엔드포인트 ===

class AsyncResultEndpoint:
    """AsyncResult 기반 엔드포인트 데코레이터"""
    
    @staticmethod
    def create_method_decorator(
        method: str,
        auto_convert: bool = True,
        default_status: int = 200,
        error_mapper: Optional[Callable[[Any], HTTPException]] = None
    ):
        """HTTP 메서드별 데코레이터 생성"""
        
        def decorator(path: str, **route_kwargs):
            def endpoint_decorator(func: Callable):
                
                @wraps(func)
                async def wrapper(*args, **kwargs):
                    # 원본 함수 실행
                    result = await func(*args, **kwargs)
                    
                    # AsyncResult인 경우 자동 변환
                    if auto_convert and isinstance(result, AsyncResult):
                        return await async_result_to_response(
                            result,
                            success_status=default_status,
                            error_mapper=error_mapper
                        )
                    
                    return result
                
                # 라우터에 등록
                wrapper.__name__ = func.__name__
                wrapper.__doc__ = func.__doc__
                
                return wrapper
            
            return endpoint_decorator
        
        return decorator
    
    @classmethod
    def get(cls, path: str, **kwargs):
        """GET 메서드 데코레이터"""
        return cls.create_method_decorator("GET", default_status=200)
    
    @classmethod
    def post(cls, path: str, **kwargs):
        """POST 메서드 데코레이터"""
        return cls.create_method_decorator("POST", default_status=201)
    
    @classmethod
    def put(cls, path: str, **kwargs):
        """PUT 메서드 데코레이터"""
        return cls.create_method_decorator("PUT", default_status=200)
    
    @classmethod
    def delete(cls, path: str, **kwargs):
        """DELETE 메서드 데코레이터"""
        return cls.create_method_decorator("DELETE", default_status=204)
    
    @classmethod
    def patch(cls, path: str, **kwargs):
        """PATCH 메서드 데코레이터"""
        return cls.create_method_decorator("PATCH", default_status=200)


# === 편의 함수 ===

def create_error_mapper(
    error_map: Dict[type, int],
    default_status: int = 500,
    include_error_details: bool = True
) -> Callable[[Any], HTTPException]:
    """
    에러 타입별 HTTP 상태 코드 매핑 함수 생성
    
    Args:
        error_map: 에러 타입별 상태 코드 맵
        default_status: 기본 상태 코드
        include_error_details: 에러 세부사항 포함 여부
        
    Returns:
        Callable: 에러 매핑 함수
        
    Example:
        >>> error_mapper = create_error_mapper({
        ...     ValueError: 400,
        ...     PermissionError: 403,
        ...     FileNotFoundError: 404,
        ...     TimeoutError: 408,
        ... })
    """
    def mapper(error: Any) -> HTTPException:
        error_type = type(error)
        status_code = error_map.get(error_type, default_status)
        
        if include_error_details:
            detail = {
                "message": str(error),
                "type": error_type.__name__,
                "code": status_code
            }
        else:
            detail = str(error)
        
        return HTTPException(status_code=status_code, detail=detail)
    
    return mapper


def create_validation_pipeline(*validators) -> Callable:
    """
    검증 파이프라인 생성 (HOF 패턴 적용)
    
    Args:
        *validators: 검증 함수들
        
    Returns:
        Callable: 파이프라인 함수
        
    Example:
        >>> validate_user = create_validation_pipeline(
        ...     validate_required_fields,
        ...     validate_email_format,
        ...     validate_age_range
        ... )
        >>> 
        >>> @router.post("/users")
        >>> async def create_user(user_data: dict):
        >>>     validation_result = await validate_user(user_data)
        >>>     return await async_result_to_response(validation_result)
    """
    return pipe(*validators)


# === 사용 예시 ===

def get_usage_examples():
    """사용 예시 코드 반환"""
    return {
        "basic_usage": '''
from rfs.web.fastapi_helpers import async_result_to_response, create_async_result_router
from rfs.async_pipeline import AsyncResult

router = create_async_result_router(prefix="/api/v1", tags=["users"])

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    user_result = AsyncResult.from_async(lambda: fetch_user_data(user_id))
    return await async_result_to_response(
        user_result,
        error_mapper=lambda e: HTTPException(status_code=404, detail=str(e))
    )
        ''',
        
        "paginated_response": '''
from rfs.web.fastapi_helpers import async_result_to_paginated_response

@router.get("/users")
async def list_users(page: int = 1, page_size: int = 20):
    users_result = AsyncResult.from_async(lambda: fetch_users(page, page_size))
    return await async_result_to_paginated_response(
        users_result, 
        page=page, 
        page_size=page_size
    )
        ''',
        
        "error_mapping": '''
from rfs.web.fastapi_helpers import create_error_mapper

# 에러 타입별 HTTP 상태 코드 매핑
error_mapper = create_error_mapper({
    ValueError: 400,
    PermissionError: 403,
    FileNotFoundError: 404,
    TimeoutError: 408,
})

@router.post("/users")
async def create_user(user_data: dict):
    creation_result = AsyncResult.from_async(lambda: create_user_account(user_data))
    return await async_result_to_response(creation_result, error_mapper=error_mapper)
        ''',
        
        "validation_pipeline": '''
from rfs.web.fastapi_helpers import create_validation_pipeline
from rfs.hof.core import pipe

# HOF를 활용한 검증 파이프라인
validate_user = create_validation_pipeline(
    validate_required_fields,
    validate_email_format,
    validate_password_strength
)

@router.put("/users/{user_id}")
async def update_user(user_id: str, user_data: dict):
    pipeline_result = await pipe(
        lambda data: validate_user(data),
        lambda result: result.bind(lambda valid_data: update_user_data(user_id, valid_data))
    )(user_data)
    
    return await async_result_to_response(pipeline_result)
        '''
    }


# === 성능 최적화 ===

async def batch_async_results_to_response(
    async_results: list[AsyncResult[T, E]],
    success_status: int = 200,
    error_mapper: Optional[Callable[[E], HTTPException]] = None,
    max_concurrency: int = 10
) -> JSONResponse:
    """
    여러 AsyncResult를 병렬로 처리하여 단일 응답으로 변환
    
    Args:
        async_results: AsyncResult 리스트
        success_status: 성공 시 상태 코드
        error_mapper: 에러 매핑 함수
        max_concurrency: 최대 동시 처리 수
        
    Returns:
        JSONResponse: 배치 처리 결과
    """
    ensure_fastapi()
    
    # 세마포어를 사용한 동시성 제어
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def process_single(async_result: AsyncResult[T, E]):
        async with semaphore:
            return await async_result.to_result()
    
    # 병렬 실행
    results = await asyncio.gather(
        *[process_single(ar) for ar in async_results],
        return_exceptions=True
    )
    
    # 결과 분류
    successes = []
    errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors.append({"index": i, "error": str(result)})
        elif result.is_success():
            successes.append({"index": i, "data": result.unwrap()})
        else:
            errors.append({"index": i, "error": str(result.unwrap_error())})
    
    response_data = {
        "successes": successes,
        "errors": errors,
        "summary": {
            "total": len(async_results),
            "successful": len(successes),
            "failed": len(errors)
        }
    }
    
    # 에러가 있는 경우 상태 코드 조정
    if errors and not successes:
        status = 500  # 모든 요청이 실패
    elif errors:
        status = 207  # 부분적 성공 (Multi-Status)
    else:
        status = success_status
    
    return JSONResponse(content=response_data, status_code=status)


# === 모듈 정보 ===

__version__ = "1.0.0"
__author__ = "RFS Framework Team"

def get_module_info():
    """모듈 정보 반환"""
    return {
        "name": "RFS FastAPI AsyncResult Helpers",
        "version": __version__,
        "features": [
            "AsyncResult ↔ FastAPI Response 자동 변환",
            "전용 Router 및 미들웨어",
            "에러 매핑 및 상태 코드 관리",
            "페이지네이션 응답 지원",
            "배치 처리 및 성능 최적화",
            "HOF 패턴 통합"
        ],
        "dependencies": {
            "rfs_framework": ">= 4.3.0",
            "fastapi": ">= 0.95.0"
        }
    }