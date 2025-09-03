"""
FastAPI Response 헬퍼 시스템

Result 패턴을 FastAPI HTTP 응답으로 자동 변환하는 
데코레이터와 헬퍼 함수를 제공합니다.
"""

from typing import Callable, Any, Union, List
from functools import wraps
import asyncio
import logging
import time
from datetime import datetime

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from rfs.core.result import Result
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult
from .errors import APIError
from .types import FastAPIResult, FastAPIMonoResult, FastAPIFluxResult

logger = logging.getLogger(__name__)


def handle_result(func: Callable) -> Callable:
    """
    Result 또는 MonoResult를 반환하는 함수를 FastAPI 응답으로 자동 변환
    
    지원하는 반환 타입:
    - Result[T, APIError] → JSONResponse 또는 HTTPException
    - MonoResult[T, APIError] → 자동으로 .to_result() 호출 후 변환
    - Result[T, str] → APIError로 자동 래핑 후 변환
    
    Args:
        func: 데코레이트할 함수
        
    Returns:
        Callable: 래핑된 함수
        
    Example:
        @app.get("/users/{user_id}")
        @handle_result
        async def get_user(user_id: str) -> Result[User, APIError]:
            return await user_service.get_user(user_id)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Union[JSONResponse, HTTPException]:
        start_time = time.time()
        
        try:
            # 함수 실행
            result = await func(*args, **kwargs)
            processing_time = (time.time() - start_time) * 1000
            
            # MonoResult인 경우 Result로 변환
            if hasattr(result, 'to_result') and callable(getattr(result, 'to_result')):
                result = await result.to_result()
            
            # Result가 아닌 경우 에러
            if not hasattr(result, 'is_success'):
                logger.error(f"Function {func.__name__} must return Result or MonoResult")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "내부 서버 오류: 잘못된 응답 타입",
                        "details": {"expected": "Result or MonoResult", "got": str(type(result))}
                    }
                )
            
            if result.is_success():
                success_data = result.unwrap()
                
                # Pydantic 모델인 경우 dict() 호출
                if hasattr(success_data, 'dict'):
                    response_data = success_data.dict()
                elif hasattr(success_data, 'model_dump'):  # Pydantic v2
                    response_data = success_data.model_dump()
                else:
                    response_data = success_data
                
                # 성공 로깅
                logger.info(
                    f"API 성공: {func.__name__} ({processing_time:.2f}ms)"
                )
                
                return JSONResponse(
                    content=response_data,
                    status_code=200,
                    headers={"X-Processing-Time-MS": str(int(processing_time))}
                )
            else:
                error = result.unwrap_error()
                
                # APIError가 아닌 경우 자동 변환
                if not isinstance(error, APIError):
                    if isinstance(error, str):
                        error = APIError.internal_server_error(error)
                    elif isinstance(error, Exception):
                        error = APIError.from_exception(error)
                    else:
                        error = APIError.internal_server_error(str(error))
                
                # 에러 로깅
                logger.warning(
                    f"API 에러: {func.__name__} ({processing_time:.2f}ms) - "
                    f"{error.code.value}: {error.message}"
                )
                
                # HTTPException으로 변환
                raise HTTPException(
                    status_code=error.status_code,
                    detail={
                        "code": error.code.value,
                        "message": error.message,
                        "details": error.details,
                        "timestamp": datetime.now().isoformat(),
                        "processing_time_ms": int(processing_time)
                    },
                    headers={"X-Processing-Time-MS": str(int(processing_time))}
                )
                
        except HTTPException:
            # FastAPI의 HTTPException은 그대로 전파
            raise
            
        except Exception as e:
            # 예상치 못한 예외를 APIError로 변환
            processing_time = (time.time() - start_time) * 1000
            logger.exception(f"예상치 못한 에러 in {func.__name__}: {e}")
            
            api_error = APIError.from_exception(e)
            raise HTTPException(
                status_code=api_error.status_code,
                detail={
                    "code": api_error.code.value,
                    "message": api_error.message,
                    "details": api_error.details,
                    "timestamp": datetime.now().isoformat(),
                    "processing_time_ms": int(processing_time),
                    "original_error": str(e)
                },
                headers={"X-Processing-Time-MS": str(int(processing_time))}
            )
    
    return wrapper


def handle_flux_result(
    partial_success: bool = True,
    include_errors: bool = False,
    max_errors_in_response: int = 10
) -> Callable:
    """
    FluxResult를 배치 처리 HTTP 응답으로 자동 변환
    
    Args:
        partial_success: 부분 성공을 허용할지 여부 (기본: True)
        include_errors: 응답에 에러 정보를 포함할지 여부 (기본: False)
        max_errors_in_response: 응답에 포함할 최대 에러 개수 (기본: 10)
    
    Returns:
        Callable: 데코레이터 함수
    
    Response Format:
        {
            "success": true/false,
            "summary": {
                "total": 전체 처리된 항목 수,
                "successful": 성공한 항목 수,
                "failed": 실패한 항목 수,
                "success_rate": 성공률 (0.0 ~ 1.0),
                "processing_time_ms": 처리 시간
            },
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
            start_time = time.time()
            
            try:
                # 함수 실행
                flux_result = await func(*args, **kwargs)
                processing_time = (time.time() - start_time) * 1000
                
                # FluxResult가 아닌 경우 에러
                if not hasattr(flux_result, 'count_total'):
                    logger.error(f"Function {func.__name__} must return FluxResult")
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "code": "INTERNAL_SERVER_ERROR",
                            "message": "내부 서버 오류: FluxResult가 아닌 응답",
                            "details": {"expected": "FluxResult", "got": str(type(flux_result))}
                        }
                    )
                
                # 통계 정보 수집
                total_count = flux_result.count_total()
                success_count = flux_result.count_success()
                failure_count = flux_result.count_failures()
                success_rate = flux_result.success_rate()
                
                # 성공한 결과들 수집
                success_values_result = await flux_result.collect_success_values().to_result()
                successful_results = success_values_result.unwrap() if success_values_result.is_success() else []
                
                # 응답 데이터 구성
                response_data = {
                    "success": success_count > 0 and (partial_success or failure_count == 0),
                    "summary": {
                        "total": total_count,
                        "successful": success_count,
                        "failed": failure_count,
                        "success_rate": round(success_rate, 4),
                        "processing_time_ms": int(processing_time)
                    },
                    "results": successful_results
                }
                
                # 에러 정보 포함 (옵션)
                if include_errors and failure_count > 0:
                    error_values_result = await flux_result.collect_error_values().to_result()
                    if error_values_result.is_success():
                        all_errors = error_values_result.unwrap()
                        
                        # 에러 개수 제한
                        limited_errors = all_errors[:max_errors_in_response]
                        
                        # APIError가 아닌 에러들을 변환
                        formatted_errors = []
                        for error in limited_errors:
                            if isinstance(error, APIError):
                                formatted_errors.append(error.to_dict())
                            else:
                                api_error = APIError.from_service_error(error)
                                formatted_errors.append(api_error.to_dict())
                        
                        response_data["errors"] = formatted_errors
                        
                        # 에러가 잘렸을 경우 알림
                        if len(all_errors) > max_errors_in_response:
                            response_data["errors_truncated"] = {
                                "total_errors": len(all_errors),
                                "shown_errors": len(formatted_errors)
                            }
                
                # HTTP 상태 코드 결정
                if failure_count == 0:
                    status_code = 200  # 모든 작업 성공
                elif success_count > 0 and partial_success:
                    status_code = 207  # Multi-Status (부분 성공)
                else:
                    status_code = 400  # 전체 실패 또는 부분 성공 불허용
                
                # 성공 로깅
                logger.info(
                    f"배치 처리 완료: {func.__name__} ({processing_time:.2f}ms) - "
                    f"성공: {success_count}/{total_count} ({success_rate:.1%})"
                )
                
                return JSONResponse(
                    content=response_data,
                    status_code=status_code,
                    headers={
                        "X-Processing-Time-MS": str(int(processing_time)),
                        "X-Batch-Total": str(total_count),
                        "X-Batch-Success": str(success_count),
                        "X-Batch-Failed": str(failure_count)
                    }
                )
                
            except HTTPException:
                # FastAPI의 HTTPException은 그대로 전파
                raise
                
            except Exception as e:
                # 예상치 못한 예외 처리
                processing_time = (time.time() - start_time) * 1000
                logger.exception(f"배치 처리 중 예상치 못한 오류 in {func.__name__}: {e}")
                
                api_error = APIError.from_exception(e)
                raise HTTPException(
                    status_code=api_error.status_code,
                    detail={
                        "code": api_error.code.value,
                        "message": f"배치 처리 중 오류: {api_error.message}",
                        "details": api_error.details,
                        "timestamp": datetime.now().isoformat(),
                        "processing_time_ms": int(processing_time),
                        "original_error": str(e)
                    },
                    headers={"X-Processing-Time-MS": str(int(processing_time))}
                )
        
        return wrapper
    
    return decorator


# 편의 함수들

def create_success_response(data: Any, processing_time_ms: float = 0) -> JSONResponse:
    """성공 응답 생성 편의 함수
    
    Args:
        data: 응답 데이터
        processing_time_ms: 처리 시간 (밀리초)
        
    Returns:
        JSONResponse: JSON 응답
    """
    # Pydantic 모델 처리
    if hasattr(data, 'dict'):
        response_data = data.dict()
    elif hasattr(data, 'model_dump'):  # Pydantic v2
        response_data = data.model_dump()
    else:
        response_data = data
    
    headers = {}
    if processing_time_ms > 0:
        headers["X-Processing-Time-MS"] = str(int(processing_time_ms))
    
    return JSONResponse(
        content=response_data,
        status_code=200,
        headers=headers
    )


def create_error_response(error: Union[APIError, str, Exception]) -> HTTPException:
    """에러 응답 생성 편의 함수
    
    Args:
        error: 에러 (APIError, 문자열, 또는 예외)
        
    Returns:
        HTTPException: HTTP 예외
    """
    if isinstance(error, APIError):
        api_error = error
    elif isinstance(error, str):
        api_error = APIError.internal_server_error(error)
    elif isinstance(error, Exception):
        api_error = APIError.from_exception(error)
    else:
        api_error = APIError.internal_server_error(str(error))
    
    return HTTPException(
        status_code=api_error.status_code,
        detail={
            "code": api_error.code.value,
            "message": api_error.message,
            "details": api_error.details,
            "timestamp": datetime.now().isoformat()
        }
    )


# 고급 응답 헬퍼들

def handle_paginated_result(
    page_size: int = 20,
    max_page_size: int = 100
) -> Callable:
    """페이지네이션 지원 Result 핸들러
    
    Args:
        page_size: 기본 페이지 크기
        max_page_size: 최대 페이지 크기
        
    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @handle_result
        async def wrapper(*args, page: int = 1, size: int = page_size, **kwargs):
            # 페이지 파라미터 검증
            if page < 1:
                return APIError.validation_error({"page": "페이지는 1 이상이어야 합니다"})
            
            if size < 1 or size > max_page_size:
                return APIError.validation_error({
                    "size": f"페이지 크기는 1~{max_page_size} 사이여야 합니다"
                })
            
            # 원본 함수 호출
            result = await func(*args, page=page, size=size, **kwargs)
            
            # 페이지네이션 메타데이터 추가
            if result.is_success():
                data = result.unwrap()
                if isinstance(data, dict) and 'items' in data:
                    data['pagination'] = {
                        'page': page,
                        'size': size,
                        'total': data.get('total', len(data['items']))
                    }
            
            return result
        
        return wrapper
    
    return decorator


def handle_cached_result(cache_seconds: int = 300) -> Callable:
    """캐시 헤더가 포함된 Result 핸들러
    
    Args:
        cache_seconds: 캐시 시간 (초)
        
    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # handle_result 데코레이터를 직접 적용
            @handle_result
            async def cached_func():
                return await func(*args, **kwargs)
            
            # 캐시된 함수 실행
            response = await cached_func()
            
            # 성공 응답인 경우 캐시 헤더 추가
            if isinstance(response, JSONResponse):
                response.headers["Cache-Control"] = f"public, max-age={cache_seconds}"
                response.headers["Expires"] = str(int(time.time() + cache_seconds))
            
            return response
        
        return wrapper
    
    return decorator