"""
FastAPI 미들웨어 시스템

Result 패턴과 통합된 미들웨어를 제공하여
로깅, 예외 처리, 성능 모니터링을 자동화합니다.
"""

import time
import uuid
import logging
import asyncio
from typing import Callable, Any, Optional, Dict, List
from contextlib import asynccontextmanager
import json
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp, Receive, Scope, Send

from rfs.core.result import Result, Success, Failure
from .errors import APIError, ErrorCode

logger = logging.getLogger(__name__)


class ResultLoggingMiddleware(BaseHTTPMiddleware):
    """
    Result 패턴 기반 로깅 미들웨어
    
    모든 요청/응답을 자동으로 로깅하고 성능 메트릭을 수집합니다.
    Result 패턴과 통합되어 성공/실패를 구분하여 기록합니다.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        *,
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 10000,
        exclude_paths: Optional[List[str]] = None,
        include_headers: bool = True
    ):
        """
        Args:
            app: ASGI 애플리케이션
            log_request_body: 요청 본문을 로깅할지 여부
            log_response_body: 응답 본문을 로깅할지 여부
            max_body_size: 로깅할 최대 본문 크기 (바이트)
            exclude_paths: 로깅에서 제외할 경로 목록
            include_headers: 헤더 정보를 포함할지 여부
        """
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
        self.exclude_paths = exclude_paths or []
        self.include_headers = include_headers
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """요청/응답 로깅 처리"""
        # 요청 ID 생성
        request_id = str(uuid.uuid4())[:8]
        
        # 제외 경로 확인
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # 시작 시간 기록
        start_time = time.time()
        
        # 요청 로깅
        await self._log_request(request, request_id)
        
        try:
            # 요청 처리
            response = await call_next(request)
            
            # 처리 시간 계산
            processing_time = (time.time() - start_time) * 1000
            
            # 응답 로깅
            await self._log_response(request, response, request_id, processing_time)
            
            # 응답 헤더에 메트릭 추가
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Processing-Time-MS"] = str(int(processing_time))
            
            return response
            
        except Exception as e:
            # 예외 로깅
            processing_time = (time.time() - start_time) * 1000
            await self._log_exception(request, e, request_id, processing_time)
            raise
    
    async def _log_request(self, request: Request, request_id: str):
        """요청 정보 로깅"""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": self._get_client_ip(request)
        }
        
        # 헤더 정보 추가
        if self.include_headers:
            log_data["headers"] = dict(request.headers)
        
        # 요청 본문 추가
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await self._read_request_body(request)
                if body and len(body) <= self.max_body_size:
                    try:
                        log_data["body"] = json.loads(body.decode("utf-8"))
                    except json.JSONDecodeError:
                        log_data["body"] = body.decode("utf-8", errors="replace")[:self.max_body_size]
                elif len(body) > self.max_body_size:
                    log_data["body"] = f"<body too large: {len(body)} bytes>"
            except Exception as e:
                log_data["body_error"] = str(e)
        
        logger.info(f"요청 시작: {request.method} {request.url.path}", extra={"request_data": log_data})
    
    async def _log_response(
        self, 
        request: Request, 
        response: Response, 
        request_id: str, 
        processing_time: float
    ):
        """응답 정보 로깅"""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "status_code": response.status_code,
            "processing_time_ms": round(processing_time, 2),
            "method": request.method,
            "path": request.url.path
        }
        
        # 응답 헤더 추가
        if self.include_headers:
            log_data["response_headers"] = dict(response.headers)
        
        # 응답 본문 추가 (JSONResponse인 경우만)
        if self.log_response_body and isinstance(response, JSONResponse):
            try:
                if hasattr(response, 'body') and len(response.body) <= self.max_body_size:
                    body_str = response.body.decode("utf-8")
                    log_data["response_body"] = json.loads(body_str)
            except Exception as e:
                log_data["response_body_error"] = str(e)
        
        # 성공/실패에 따른 로그 레벨 결정
        if response.status_code < 400:
            logger.info(f"요청 성공: {request.method} {request.url.path} ({processing_time:.2f}ms)", 
                       extra={"response_data": log_data})
        elif response.status_code < 500:
            logger.warning(f"클라이언트 에러: {request.method} {request.url.path} ({processing_time:.2f}ms)",
                          extra={"response_data": log_data})
        else:
            logger.error(f"서버 에러: {request.method} {request.url.path} ({processing_time:.2f}ms)",
                        extra={"response_data": log_data})
    
    async def _log_exception(
        self, 
        request: Request, 
        exception: Exception, 
        request_id: str, 
        processing_time: float
    ):
        """예외 정보 로깅"""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "processing_time_ms": round(processing_time, 2),
            "method": request.method,
            "path": request.url.path
        }
        
        logger.exception(f"요청 처리 중 예외 발생: {request.method} {request.url.path}",
                        extra={"exception_data": log_data})
    
    async def _read_request_body(self, request: Request) -> bytes:
        """요청 본문 읽기 (중복 읽기 방지)"""
        if hasattr(request.state, "_cached_body"):
            return request.state._cached_body
        
        body = await request.body()
        request.state._cached_body = body
        return body
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        # X-Forwarded-For 헤더 확인 (로드밸런서/프록시 환경)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 직접 연결인 경우
        if request.client:
            return request.client.host
        
        return "unknown"


class ExceptionToResultMiddleware(BaseHTTPMiddleware):
    """
    예외를 Result 패턴으로 변환하는 미들웨어
    
    처리되지 않은 예외를 APIError로 자동 변환하여
    일관된 에러 응답 형식을 제공합니다.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        *,
        debug: bool = False,
        include_traceback: bool = False,
        custom_error_handlers: Optional[Dict[type, Callable]] = None
    ):
        """
        Args:
            app: ASGI 애플리케이션
            debug: 디버그 모드 (상세 에러 정보 포함)
            include_traceback: 스택 트레이스 포함 여부
            custom_error_handlers: 커스텀 에러 핸들러 맵
        """
        super().__init__(app)
        self.debug = debug
        self.include_traceback = include_traceback
        self.custom_error_handlers = custom_error_handlers or {}
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """예외 처리 및 Result 변환"""
        try:
            return await call_next(request)
        
        except Exception as e:
            # 커스텀 핸들러가 있는지 확인
            exception_type = type(e)
            if exception_type in self.custom_error_handlers:
                handler = self.custom_error_handlers[exception_type]
                try:
                    return await self._handle_custom_exception(handler, e, request)
                except Exception as handler_error:
                    logger.exception(f"커스텀 에러 핸들러 실행 실패: {handler_error}")
                    # 핸들러 실패 시 기본 처리로 진행
            
            # APIError로 변환
            api_error = self._convert_to_api_error(e)
            
            # 에러 응답 생성
            return self._create_error_response(api_error, request, e)
    
    def _convert_to_api_error(self, exception: Exception) -> APIError:
        """예외를 APIError로 변환"""
        # 이미 APIError인 경우 그대로 반환
        if isinstance(exception, APIError):
            return exception
        
        # HTTPException 처리
        if hasattr(exception, 'status_code') and hasattr(exception, 'detail'):
            return APIError(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=str(exception.detail),
                status_code=exception.status_code
            )
        
        # 일반 예외 처리
        return APIError.from_exception(exception)
    
    def _create_error_response(
        self, 
        api_error: APIError, 
        request: Request, 
        original_exception: Exception
    ) -> JSONResponse:
        """에러 응답 생성"""
        error_detail = {
            "code": api_error.code.value,
            "message": api_error.message,
            "details": api_error.details,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
            "method": request.method
        }
        
        # 디버그 정보 추가
        if self.debug:
            error_detail["debug"] = {
                "exception_type": type(original_exception).__name__,
                "exception_args": str(original_exception.args)
            }
        
        # 스택 트레이스 추가
        if self.include_traceback:
            import traceback
            error_detail["traceback"] = traceback.format_exc()
        
        # 요청 ID 추가 (로깅 미들웨어에서 설정된 경우)
        request_id = getattr(request.state, 'request_id', None)
        if request_id:
            error_detail["request_id"] = request_id
        
        return JSONResponse(
            content=error_detail,
            status_code=api_error.status_code,
            headers={
                "Content-Type": "application/json",
                "X-Error-Code": api_error.code.value
            }
        )
    
    async def _handle_custom_exception(
        self, 
        handler: Callable, 
        exception: Exception, 
        request: Request
    ) -> Response:
        """커스텀 예외 핸들러 실행"""
        if asyncio.iscoroutinefunction(handler):
            return await handler(exception, request)
        else:
            return handler(exception, request)


class PerformanceMetricsMiddleware(BaseHTTPMiddleware):
    """
    성능 메트릭 수집 미들웨어
    
    요청별 성능 지표를 수집하고 모니터링합니다.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        *,
        slow_request_threshold: float = 1000.0,  # ms
        collect_detailed_metrics: bool = True,
        metrics_callback: Optional[Callable] = None
    ):
        """
        Args:
            app: ASGI 애플리케이션
            slow_request_threshold: 느린 요청 임계값 (밀리초)
            collect_detailed_metrics: 상세 메트릭 수집 여부
            metrics_callback: 메트릭 콜백 함수
        """
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.collect_detailed_metrics = collect_detailed_metrics
        self.metrics_callback = metrics_callback
        self._request_count = 0
        self._total_processing_time = 0.0
        self._slow_requests = 0
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """성능 메트릭 수집"""
        start_time = time.time()
        start_memory = None
        
        # 상세 메트릭 수집 시 메모리 사용량 측정
        if self.collect_detailed_metrics:
            import psutil
            process = psutil.Process()
            start_memory = process.memory_info().rss
        
        try:
            # 요청 처리
            response = await call_next(request)
            
            # 메트릭 계산
            processing_time = (time.time() - start_time) * 1000
            await self._collect_metrics(request, response, processing_time, start_memory)
            
            return response
            
        except Exception as e:
            # 예외 발생 시에도 메트릭 수집
            processing_time = (time.time() - start_time) * 1000
            await self._collect_exception_metrics(request, e, processing_time, start_memory)
            raise
    
    async def _collect_metrics(
        self, 
        request: Request, 
        response: Response, 
        processing_time: float,
        start_memory: Optional[int]
    ):
        """성공 요청 메트릭 수집"""
        # 기본 카운터 업데이트
        self._request_count += 1
        self._total_processing_time += processing_time
        
        # 느린 요청 카운트
        if processing_time > self.slow_request_threshold:
            self._slow_requests += 1
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "processing_time_ms": round(processing_time, 2),
            "is_slow": processing_time > self.slow_request_threshold
        }
        
        # 상세 메트릭 추가
        if self.collect_detailed_metrics and start_memory:
            import psutil
            process = psutil.Process()
            end_memory = process.memory_info().rss
            
            metrics.update({
                "memory_start_mb": round(start_memory / 1024 / 1024, 2),
                "memory_end_mb": round(end_memory / 1024 / 1024, 2),
                "memory_delta_mb": round((end_memory - start_memory) / 1024 / 1024, 2),
                "cpu_percent": process.cpu_percent()
            })
        
        # 느린 요청 로깅
        if processing_time > self.slow_request_threshold:
            logger.warning(
                f"느린 요청 감지: {request.method} {request.url.path} "
                f"({processing_time:.2f}ms > {self.slow_request_threshold}ms)",
                extra={"performance_metrics": metrics}
            )
        
        # 콜백 함수 호출
        if self.metrics_callback:
            try:
                if asyncio.iscoroutinefunction(self.metrics_callback):
                    await self.metrics_callback(metrics)
                else:
                    self.metrics_callback(metrics)
            except Exception as e:
                logger.exception(f"메트릭 콜백 실행 실패: {e}")
    
    async def _collect_exception_metrics(
        self, 
        request: Request, 
        exception: Exception, 
        processing_time: float,
        start_memory: Optional[int]
    ):
        """예외 발생 시 메트릭 수집"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exception).__name__,
            "processing_time_ms": round(processing_time, 2),
            "is_error": True
        }
        
        logger.error(
            f"요청 처리 중 예외: {request.method} {request.url.path} "
            f"({processing_time:.2f}ms)",
            extra={"error_metrics": metrics}
        )
    
    def get_summary_metrics(self) -> Dict[str, Any]:
        """요약 메트릭 반환"""
        avg_processing_time = (
            self._total_processing_time / self._request_count 
            if self._request_count > 0 else 0
        )
        
        slow_request_rate = (
            self._slow_requests / self._request_count 
            if self._request_count > 0 else 0
        )
        
        return {
            "total_requests": self._request_count,
            "average_processing_time_ms": round(avg_processing_time, 2),
            "slow_requests": self._slow_requests,
            "slow_request_rate": round(slow_request_rate, 4),
            "slow_request_threshold_ms": self.slow_request_threshold
        }


# 미들웨어 설정 헬퍼 함수들

def setup_result_middleware(
    app: FastAPI,
    *,
    enable_logging: bool = True,
    enable_exception_handling: bool = True,
    enable_metrics: bool = True,
    logging_config: Optional[Dict[str, Any]] = None,
    exception_config: Optional[Dict[str, Any]] = None,
    metrics_config: Optional[Dict[str, Any]] = None
):
    """
    Result 패턴 통합 미들웨어를 FastAPI 앱에 설정합니다.
    
    Args:
        app: FastAPI 애플리케이션
        enable_logging: 로깅 미들웨어 활성화
        enable_exception_handling: 예외 처리 미들웨어 활성화
        enable_metrics: 메트릭 미들웨어 활성화
        logging_config: 로깅 미들웨어 설정
        exception_config: 예외 처리 미들웨어 설정
        metrics_config: 메트릭 미들웨어 설정
    """
    # 메트릭 미들웨어 (가장 바깥쪽)
    if enable_metrics:
        metrics_settings = metrics_config or {}
        app.add_middleware(PerformanceMetricsMiddleware, **metrics_settings)
    
    # 로깅 미들웨어
    if enable_logging:
        logging_settings = logging_config or {}
        app.add_middleware(ResultLoggingMiddleware, **logging_settings)
    
    # 예외 처리 미들웨어 (가장 안쪽)
    if enable_exception_handling:
        exception_settings = exception_config or {}
        app.add_middleware(ExceptionToResultMiddleware, **exception_settings)
    
    logger.info("Result 패턴 미들웨어가 설정되었습니다")


@asynccontextmanager
async def result_middleware_context(app: FastAPI):
    """
    미들웨어 컨텍스트 매니저
    
    애플리케이션 시작/종료 시 미들웨어 관련 리소스를 관리합니다.
    
    Example:
        >>> app = FastAPI()
        >>> 
        >>> @asynccontextmanager
        >>> async def lifespan(app: FastAPI):
        ...     async with result_middleware_context(app):
        ...         yield
        >>> 
        >>> app = FastAPI(lifespan=lifespan)
    """
    # 시작 시 초기화
    logger.info("Result 미들웨어 컨텍스트 시작")
    
    try:
        yield
    finally:
        # 종료 시 정리
        logger.info("Result 미들웨어 컨텍스트 종료")


# 편의 함수들

def create_custom_error_handler(
    exception_type: type,
    handler: Callable[[Exception, Request], Response]
) -> Dict[type, Callable]:
    """
    커스텀 에러 핸들러 생성 헬퍼
    
    Args:
        exception_type: 처리할 예외 타입
        handler: 에러 핸들러 함수
        
    Returns:
        Dict[type, Callable]: 에러 핸들러 맵
    """
    return {exception_type: handler}


async def log_custom_metric(
    metric_name: str,
    value: float,
    tags: Optional[Dict[str, str]] = None
):
    """
    커스텀 메트릭 로깅
    
    Args:
        metric_name: 메트릭 이름
        value: 메트릭 값
        tags: 추가 태그
    """
    metric_data = {
        "metric_name": metric_name,
        "value": value,
        "timestamp": datetime.now().isoformat(),
        "tags": tags or {}
    }
    
    logger.info(f"커스텀 메트릭: {metric_name}={value}", extra={"custom_metric": metric_data})