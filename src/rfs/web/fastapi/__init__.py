"""
RFS Framework FastAPI 통합 모듈

FastAPI와 Result 패턴의 완벽한 통합을 제공합니다.
Phase 2 구현: MonoResult/FluxResult → FastAPI Response 자동 변환

주요 기능:
- @handle_result, @handle_flux_result 데코레이터
- APIError 클래스 체계 및 HTTP 상태 코드 매핑
- Result 패턴 기반 의존성 주입
- 구조화된 에러 응답 및 성능 모니터링
"""

from .errors import APIError, ErrorCode
from .types import FastAPIResult, FastAPIMonoResult, FastAPIFluxResult
from .response_helpers import handle_result, handle_flux_result
from .dependencies import ResultDependency, result_dependency, inject_result_service
from .middleware import ResultLoggingMiddleware, ExceptionToResultMiddleware

__all__ = [
    # 에러 처리
    "APIError",
    "ErrorCode",
    
    # 타입 별칭
    "FastAPIResult", 
    "FastAPIMonoResult",
    "FastAPIFluxResult",
    
    # 응답 헬퍼
    "handle_result",
    "handle_flux_result",
    
    # 의존성 주입
    "ResultDependency",
    "result_dependency", 
    "inject_result_service",
    
    # 미들웨어
    "ResultLoggingMiddleware",
    "ExceptionToResultMiddleware",
]

__version__ = "2.0.0"
__author__ = "RFS Framework Team"
__description__ = "FastAPI + Result 패턴 완벽 통합"