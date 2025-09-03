"""
FastAPI 통합용 타입 별칭 시스템

Result 패턴과 FastAPI의 완벽한 타입 통합을 위한 
편의 타입 별칭 및 헬퍼 함수를 제공합니다.
"""

from typing import TypeVar, Union, Any
from rfs.core.result import Result, Success, Failure
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult
from .errors import APIError

T = TypeVar('T')
E = TypeVar('E')

# FastAPI 전용 Result 타입 별칭
FastAPIResult = Result[T, APIError]
"""FastAPI용 Result 타입 - APIError를 에러 타입으로 고정"""

FastAPIMonoResult = MonoResult[T, APIError] 
"""FastAPI용 MonoResult 타입 - APIError를 에러 타입으로 고정"""

FastAPIFluxResult = FluxResult[T, APIError]
"""FastAPI용 FluxResult 타입 - APIError를 에러 타입으로 고정"""

# 응답 타입 별칭 (문서화 및 타입 힌트용)
SuccessResponse = T
"""성공 응답 타입"""

ErrorResponse = APIError
"""에러 응답 타입"""


def success_response(data: T) -> FastAPIResult[T]:
    """성공 응답 생성 헬퍼
    
    Args:
        data: 성공 데이터
        
    Returns:
        FastAPIResult[T]: 성공 응답
        
    Example:
        >>> user = User(id="123", name="김철수")
        >>> response = success_response(user)
        >>> assert response.is_success()
        >>> assert response.unwrap() == user
    """
    return Success(data)


def error_response(error: Union[APIError, str, Exception]) -> FastAPIResult[Any]:
    """에러 응답 생성 헬퍼
    
    Args:
        error: 에러 (APIError, 문자열, 또는 예외)
        
    Returns:
        FastAPIResult[Any]: 에러 응답
        
    Example:
        >>> error_resp = error_response("사용자를 찾을 수 없습니다")
        >>> assert error_resp.is_failure()
        >>> 
        >>> api_error = APIError.not_found("사용자", "123")
        >>> error_resp = error_response(api_error)
        >>> assert error_resp.unwrap_error() == api_error
    """
    if isinstance(error, APIError):
        return Failure(error)
    elif isinstance(error, str):
        return Failure(APIError.internal_server_error(error))
    elif isinstance(error, Exception):
        return Failure(APIError.from_exception(error))
    else:
        return Failure(APIError.internal_server_error("알 수 없는 오류"))


def mono_success(data: T) -> FastAPIMonoResult[T]:
    """MonoResult 성공 응답 생성 헬퍼
    
    Args:
        data: 성공 데이터
        
    Returns:
        FastAPIMonoResult[T]: 성공 MonoResult
        
    Example:
        >>> user = User(id="123", name="김철수")
        >>> mono = mono_success(user)
        >>> result = await mono.to_result()
        >>> assert result.is_success()
    """
    return MonoResult.from_value(data)


def mono_error(error: Union[APIError, str, Exception]) -> FastAPIMonoResult[Any]:
    """MonoResult 에러 응답 생성 헬퍼
    
    Args:
        error: 에러 (APIError, 문자열, 또는 예외)
        
    Returns:
        FastAPIMonoResult[Any]: 에러 MonoResult
        
    Example:
        >>> api_error = APIError.not_found("사용자")
        >>> mono = mono_error(api_error)
        >>> result = await mono.to_result()
        >>> assert result.is_failure()
    """
    if isinstance(error, APIError):
        api_error = error
    elif isinstance(error, str):
        api_error = APIError.internal_server_error(error)
    elif isinstance(error, Exception):
        api_error = APIError.from_exception(error)
    else:
        api_error = APIError.internal_server_error("알 수 없는 오류")
    
    return MonoResult.from_error(api_error)


def flux_success(data_list: list[T]) -> FastAPIFluxResult[T]:
    """FluxResult 성공 응답 생성 헬퍼
    
    Args:
        data_list: 성공 데이터 리스트
        
    Returns:
        FastAPIFluxResult[T]: 성공 FluxResult
        
    Example:
        >>> users = [User(id="1"), User(id="2")]
        >>> flux = flux_success(users)
        >>> assert flux.count_success() == 2
    """
    return FluxResult.from_values(data_list)


def flux_mixed(
    success_data: list[T],
    errors: list[Union[APIError, str, Exception]]
) -> FastAPIFluxResult[T]:
    """성공/실패 혼합 FluxResult 생성 헬퍼
    
    Args:
        success_data: 성공 데이터 리스트
        errors: 에러 리스트
        
    Returns:
        FastAPIFluxResult[T]: 혼합 FluxResult
        
    Example:
        >>> users = [User(id="1")]
        >>> errors = ["User 2 not found"]
        >>> flux = flux_mixed(users, errors)
        >>> assert flux.count_success() == 1
        >>> assert flux.count_failures() == 1
    """
    results = []
    
    # 성공 데이터 추가
    for data in success_data:
        results.append(Success(data))
    
    # 에러 데이터 추가
    for error in errors:
        if isinstance(error, APIError):
            api_error = error
        elif isinstance(error, str):
            api_error = APIError.internal_server_error(error)
        elif isinstance(error, Exception):
            api_error = APIError.from_exception(error)
        else:
            api_error = APIError.internal_server_error(str(error))
        
        results.append(Failure(api_error))
    
    return FluxResult.from_results(results)


# 타입 검증 헬퍼 함수들

def is_fastapi_result(obj: Any) -> bool:
    """객체가 FastAPI Result인지 확인
    
    Args:
        obj: 확인할 객체
        
    Returns:
        bool: FastAPI Result 여부
    """
    return (
        isinstance(obj, Result) and 
        hasattr(obj, '_error') and
        isinstance(getattr(obj, '_error', None), APIError)
    )


def is_fastapi_mono_result(obj: Any) -> bool:
    """객체가 FastAPI MonoResult인지 확인
    
    Args:
        obj: 확인할 객체
        
    Returns:
        bool: FastAPI MonoResult 여부
    """
    return isinstance(obj, MonoResult)


def is_fastapi_flux_result(obj: Any) -> bool:
    """객체가 FastAPI FluxResult인지 확인
    
    Args:
        obj: 확인할 객체
        
    Returns:
        bool: FastAPI FluxResult 여부
    """
    return isinstance(obj, FluxResult)


# 변환 헬퍼 함수들

def to_fastapi_result(result: Result[T, Any]) -> FastAPIResult[T]:
    """일반 Result를 FastAPI Result로 변환
    
    Args:
        result: 변환할 Result
        
    Returns:
        FastAPIResult[T]: 변환된 FastAPI Result
    """
    if result.is_success():
        return Success(result.unwrap())
    else:
        error = result.unwrap_error()
        if isinstance(error, APIError):
            return Failure(error)
        else:
            return Failure(APIError.from_service_error(error))


def to_fastapi_mono_result(mono_result: MonoResult[T, Any]) -> FastAPIMonoResult[T]:
    """일반 MonoResult를 FastAPI MonoResult로 변환
    
    Args:
        mono_result: 변환할 MonoResult
        
    Returns:
        FastAPIMonoResult[T]: 변환된 FastAPI MonoResult
    """
    async def converted_func():
        result = await mono_result.to_result()
        return to_fastapi_result(result)
    
    return MonoResult(converted_func)


def to_fastapi_flux_result(flux_result: FluxResult[T, Any]) -> FastAPIFluxResult[T]:
    """일반 FluxResult를 FastAPI FluxResult로 변환
    
    Args:
        flux_result: 변환할 FluxResult
        
    Returns:
        FastAPIFluxResult[T]: 변환된 FastAPI FluxResult
    """
    converted_results = []
    
    for result in flux_result.to_list():
        converted_results.append(to_fastapi_result(result))
    
    return FluxResult.from_results(converted_results)


# 편의 상수들

# 자주 사용되는 에러 응답들
UNAUTHORIZED_ERROR = error_response(APIError.unauthorized())
FORBIDDEN_ERROR = error_response(APIError.forbidden("리소스", "접근"))
NOT_FOUND_ERROR = error_response(APIError.not_found("리소스"))
INTERNAL_ERROR = error_response(APIError.internal_server_error())

# 빈 성공 응답
EMPTY_SUCCESS = success_response(None)
EMPTY_LIST_SUCCESS = success_response([])
EMPTY_DICT_SUCCESS = success_response({})