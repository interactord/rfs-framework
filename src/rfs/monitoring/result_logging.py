"""
Result 패턴 통합 로깅 시스템

MonoResult와 FluxResult의 실행 과정을 자동으로 추적하고
구조화된 로그를 생성합니다. Correlation ID 기반 분산 추적을 지원합니다.
"""

import asyncio
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from enum import Enum

from rfs.core.result import Result, Success, Failure
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult

T = TypeVar('T')
E = TypeVar('E')

# Correlation ID 컨텍스트 변수
_correlation_context: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """로그 레벨"""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """로그 컨텍스트 정보"""
    correlation_id: str
    operation_name: str
    start_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_step(self, step_name: str, duration_ms: float, status: str, details: Optional[Dict[str, Any]] = None):
        """실행 단계 추가"""
        step = {
            "step_name": step_name,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": round(duration_ms, 2),
            "status": status,
            "details": details or {}
        }
        self.steps.append(step)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "correlation_id": self.correlation_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "total_duration_ms": round((time.time() - self.start_time) * 1000, 2),
            "metadata": self.metadata,
            "steps": self.steps,
            "step_count": len(self.steps)
        }


class CorrelationContext:
    """Correlation ID 컨텍스트 관리자"""
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
        self.token = None
    
    def __enter__(self) -> str:
        self.token = _correlation_context.set(self.correlation_id)
        return self.correlation_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            _correlation_context.reset(self.token)


def get_correlation_id() -> str:
    """현재 Correlation ID 반환"""
    correlation_id = _correlation_context.get()
    if correlation_id is None:
        # 새로운 correlation ID 생성 및 설정
        correlation_id = str(uuid.uuid4())[:8]
        _correlation_context.set(correlation_id)
    return correlation_id


def with_correlation_id(correlation_id: str) -> CorrelationContext:
    """Correlation ID 컨텍스트 생성 헬퍼"""
    return CorrelationContext(correlation_id)


class ResultLogger:
    """Result 패턴 전용 로거"""
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.name = name
        self.level = level
        self.logger = logging.getLogger(f"rfs.result.{name}")
        self._contexts: Dict[str, LogContext] = {}
    
    def start_operation(self, operation_name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """작업 시작 로깅"""
        correlation_id = get_correlation_id()
        
        context = LogContext(
            correlation_id=correlation_id,
            operation_name=operation_name,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        self._contexts[correlation_id] = context
        
        self.logger.info(
            f"작업 시작: {operation_name}",
            extra={
                "correlation_id": correlation_id,
                "operation_name": operation_name,
                "metadata": metadata or {},
                "event_type": "operation_start"
            }
        )
        
        return correlation_id
    
    def log_step(self, step_name: str, duration_ms: float, status: str = "success", 
                 details: Optional[Dict[str, Any]] = None):
        """실행 단계 로깅"""
        correlation_id = get_correlation_id()
        
        if correlation_id in self._contexts:
            self._contexts[correlation_id].add_step(step_name, duration_ms, status, details)
        
        log_level = getattr(logging, status.upper() if status in ["ERROR", "WARNING"] else "INFO")
        
        self.logger.log(
            log_level,
            f"단계 완료: {step_name} ({duration_ms:.2f}ms)",
            extra={
                "correlation_id": correlation_id,
                "step_name": step_name,
                "duration_ms": duration_ms,
                "status": status,
                "details": details or {},
                "event_type": "step_completion"
            }
        )
    
    def log_result(self, result: Result[T, E], operation_name: Optional[str] = None):
        """Result 로깅"""
        correlation_id = get_correlation_id()
        
        if result.is_success():
            self.logger.info(
                f"작업 성공: {operation_name or 'unknown'}",
                extra={
                    "correlation_id": correlation_id,
                    "operation_name": operation_name,
                    "result_type": "success",
                    "result_value_type": type(result.unwrap()).__name__,
                    "event_type": "result_success"
                }
            )
        else:
            error = result.unwrap_error()
            self.logger.error(
                f"작업 실패: {operation_name or 'unknown'} - {error}",
                extra={
                    "correlation_id": correlation_id,
                    "operation_name": operation_name,
                    "result_type": "failure",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "event_type": "result_failure"
                }
            )
    
    def log_performance(self, operation_name: str, duration_ms: float, 
                       success_count: int = 0, failure_count: int = 0,
                       additional_metrics: Optional[Dict[str, Any]] = None):
        """성능 메트릭 로깅"""
        correlation_id = get_correlation_id()
        
        total_count = success_count + failure_count
        success_rate = success_count / total_count if total_count > 0 else 0
        
        metrics = {
            "duration_ms": duration_ms,
            "total_operations": total_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_rate, 4),
            **(additional_metrics or {})
        }
        
        self.logger.info(
            f"성능 메트릭: {operation_name} ({duration_ms:.2f}ms, 성공률: {success_rate:.1%})",
            extra={
                "correlation_id": correlation_id,
                "operation_name": operation_name,
                "performance_metrics": metrics,
                "event_type": "performance_metrics"
            }
        )
    
    def complete_operation(self, operation_name: str, status: str = "success"):
        """작업 완료 로깅"""
        correlation_id = get_correlation_id()
        
        context = self._contexts.pop(correlation_id, None)
        if context:
            total_duration = (time.time() - context.start_time) * 1000
            
            self.logger.info(
                f"작업 완료: {operation_name} ({total_duration:.2f}ms)",
                extra={
                    "correlation_id": correlation_id,
                    "operation_summary": context.to_dict(),
                    "final_status": status,
                    "event_type": "operation_complete"
                }
            )
    
    def log_error(self, error: Exception, operation_name: Optional[str] = None, 
                  context_details: Optional[Dict[str, Any]] = None):
        """에러 로깅"""
        correlation_id = get_correlation_id()
        
        self.logger.exception(
            f"예외 발생: {operation_name or 'unknown'} - {error}",
            extra={
                "correlation_id": correlation_id,
                "operation_name": operation_name,
                "exception_type": type(error).__name__,
                "exception_message": str(error),
                "context_details": context_details or {},
                "event_type": "exception_occurred"
            },
            exc_info=error
        )


# 전역 Result 로거
_result_logger = ResultLogger("default")


def log_result_operation(
    operation_name: str, 
    logger_name: str = "default",
    include_args: bool = False,
    include_result: bool = True
):
    """
    Result 반환 함수를 자동으로 로깅하는 데코레이터
    
    Args:
        operation_name: 작업 이름
        logger_name: 로거 이름
        include_args: 함수 인수 로깅 포함 여부
        include_result: 결과 로깅 포함 여부
    
    Example:
        >>> @log_result_operation("user_processing")
        >>> async def process_user(user_id: str) -> Result[User, str]:
        ...     return await fetch_and_validate_user(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result_logger = ResultLogger(logger_name)
            
            # 메타데이터 준비
            metadata = {"function_name": func.__name__}
            if include_args:
                metadata["args"] = args
                metadata["kwargs"] = kwargs
            
            # 작업 시작
            correlation_id = result_logger.start_operation(operation_name, metadata)
            start_time = time.time()
            
            try:
                # 함수 실행
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # 결과 로깅
                if include_result:
                    result_logger.log_result(result, operation_name)
                
                # 성능 로깅
                success = 1 if (hasattr(result, 'is_success') and result.is_success()) else 0
                failure = 1 - success
                result_logger.log_performance(operation_name, duration_ms, success, failure)
                
                # 작업 완료
                result_logger.complete_operation(operation_name, "success" if success else "failure")
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # 에러 로깅
                result_logger.log_error(e, operation_name, {"duration_ms": duration_ms})
                result_logger.complete_operation(operation_name, "error")
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 동기 함수는 간단한 로깅만 수행
            result_logger = ResultLogger(logger_name)
            
            metadata = {"function_name": func.__name__}
            if include_args:
                metadata["args"] = args
                metadata["kwargs"] = kwargs
            
            correlation_id = result_logger.start_operation(operation_name, metadata)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                if include_result and hasattr(result, 'is_success'):
                    result_logger.log_result(result, operation_name)
                
                result_logger.complete_operation(operation_name, "success")
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                result_logger.log_error(e, operation_name, {"duration_ms": duration_ms})
                result_logger.complete_operation(operation_name, "error")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# MonoResult와 FluxResult 로깅 확장

class LoggingMonoResult(MonoResult[T, E]):
    """로깅 기능이 확장된 MonoResult"""
    
    def __init__(self, async_func: Callable, logger_name: str = "mono"):
        super().__init__(async_func)
        self._logger = ResultLogger(logger_name)
        self._operation_name = "mono_operation"
    
    def log_step(self, step_name: str, details: Optional[Dict[str, Any]] = None) -> "LoggingMonoResult[T, E]":
        """단계별 로깅 추가"""
        async def logged_func():
            start_time = time.time()
            try:
                result = await self._async_func()
                duration_ms = (time.time() - start_time) * 1000
                
                status = "success" if result.is_success() else "failure"
                self._logger.log_step(step_name, duration_ms, status, details)
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self._logger.log_step(step_name, duration_ms, "error", {"exception": str(e)})
                raise
        
        return LoggingMonoResult(logged_func, self._logger.name)
    
    def log_error(self, error_context: str) -> "LoggingMonoResult[T, E]":
        """에러 로깅 추가"""
        async def error_logged_func():
            try:
                return await self._async_func()
            except Exception as e:
                self._logger.log_error(e, error_context)
                raise
        
        return LoggingMonoResult(error_logged_func, self._logger.name)
    
    def log_performance(self, operation_name: str) -> "LoggingMonoResult[T, E]":
        """성능 로깅 추가"""
        self._operation_name = operation_name
        
        async def perf_logged_func():
            start_time = time.time()
            try:
                result = await self._async_func()
                duration_ms = (time.time() - start_time) * 1000
                
                success = 1 if result.is_success() else 0
                failure = 1 - success
                self._logger.log_performance(operation_name, duration_ms, success, failure)
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self._logger.log_performance(operation_name, duration_ms, 0, 1, 
                                           {"exception": str(e)})
                raise
        
        return LoggingMonoResult(perf_logged_func, self._logger.name)


# 편의 함수들

def create_logging_mono(
    async_func: Callable, 
    operation_name: str, 
    logger_name: str = "mono"
) -> LoggingMonoResult[Any, Any]:
    """로깅 MonoResult 생성 헬퍼"""
    mono = LoggingMonoResult(async_func, logger_name)
    return mono.log_performance(operation_name)


async def log_flux_results(
    flux_result: FluxResult[T, E], 
    operation_name: str,
    logger_name: str = "flux"
):
    """FluxResult 로깅 헬퍼"""
    result_logger = ResultLogger(logger_name)
    start_time = time.time()
    
    correlation_id = result_logger.start_operation(operation_name, {
        "total_items": flux_result.count_total(),
        "result_type": "FluxResult"
    })
    
    try:
        # 결과 수집
        success_count = flux_result.count_success()
        failure_count = flux_result.count_failures()
        total_count = flux_result.count_total()
        
        duration_ms = (time.time() - start_time) * 1000
        
        # 성능 로깅
        result_logger.log_performance(
            operation_name, 
            duration_ms, 
            success_count, 
            failure_count,
            {
                "total_items": total_count,
                "success_rate": success_count / total_count if total_count > 0 else 0
            }
        )
        
        # 작업 완료
        status = "success" if failure_count == 0 else "partial_success" if success_count > 0 else "failure"
        result_logger.complete_operation(operation_name, status)
        
        return {
            "correlation_id": correlation_id,
            "total": total_count,
            "success": success_count,
            "failure": failure_count,
            "duration_ms": duration_ms
        }
        
    except Exception as e:
        result_logger.log_error(e, operation_name)
        result_logger.complete_operation(operation_name, "error")
        raise


# 로깅 설정 헬퍼

def configure_result_logging(
    level: LogLevel = LogLevel.INFO,
    format_string: Optional[str] = None,
    include_correlation: bool = True
):
    """Result 로깅 시스템 설정"""
    
    if format_string is None:
        if include_correlation:
            format_string = (
                "%(asctime)s - %(name)s - %(levelname)s - "
                "[%(correlation_id)s] %(message)s"
            )
        else:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 로거 설정
    rfs_logger = logging.getLogger("rfs.result")
    rfs_logger.setLevel(getattr(logging, level.value))
    
    # 핸들러 설정
    if not rfs_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(format_string)
        handler.setFormatter(formatter)
        rfs_logger.addHandler(handler)
    
    logger.info(f"Result 로깅 시스템이 {level.value} 레벨로 설정되었습니다")