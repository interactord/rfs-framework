"""
RFS Framework AsyncResult 전용 로깅 유틸리티

AsyncResult 체인의 각 단계를 자동으로 로깅하고 추적하는 고급 로깅 시스템.
민감한 정보 자동 마스킹, 구조화된 로깅, 성능 메트릭 수집 등을 지원합니다.
"""

import asyncio
import json
import logging
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

from ..async_pipeline import AsyncResult
from ..core.result import Result, Success, Failure
from ..hof.core import pipe, curry
from ..hof.collections import compact_map, partition

T = TypeVar('T')
E = TypeVar('E')

# 민감한 키워드 목록 (확장 가능)
SENSITIVE_KEYS = {
    'password', 'passwd', 'pwd', 'secret', 'token', 'key', 'auth', 'authorization',
    'credential', 'credentials', 'api_key', 'access_key', 'private_key', 'session',
    'cookie', 'csrf', 'jwt', 'bearer', 'oauth', 'refresh_token', 'client_secret',
    'signature', 'hash', 'salt', 'pin', 'ssn', 'social_security', 'credit_card',
    'card_number', 'cvv', 'cvc', 'account_number', 'routing_number', 'bank_account'
}


class LogLevel(Enum):
    """로깅 레벨"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AsyncResultLogContext:
    """AsyncResult 로깅 컨텍스트"""
    operation_name: str
    operation_id: str
    start_time: float
    chain_depth: int = 0
    parent_operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class AsyncResultLogEntry:
    """AsyncResult 로그 엔트리"""
    timestamp: float
    operation_name: str
    operation_id: str
    level: LogLevel
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    duration: Optional[float] = None
    chain_depth: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)


class AsyncResultLogger:
    """AsyncResult 체인 자동 로깅 클래스"""
    
    def __init__(
        self,
        logger: logging.Logger,
        enable_sensitive_masking: bool = True,
        enable_performance_tracking: bool = True,
        enable_chain_tracking: bool = True,
        max_data_length: int = 1000,
        sensitive_keys: Optional[Set[str]] = None
    ):
        """
        AsyncResult Logger 초기화
        
        Args:
            logger: Python 표준 로거
            enable_sensitive_masking: 민감한 정보 마스킹 활성화
            enable_performance_tracking: 성능 추적 활성화  
            enable_chain_tracking: 체인 추적 활성화
            max_data_length: 최대 데이터 길이 (로깅용)
            sensitive_keys: 추가 민감한 키워드 목록
        """
        self.logger = logger
        self.enable_sensitive_masking = enable_sensitive_masking
        self.enable_performance_tracking = enable_performance_tracking
        self.enable_chain_tracking = enable_chain_tracking
        self.max_data_length = max_data_length
        
        # 민감한 키워드 설정
        self.sensitive_keys = SENSITIVE_KEYS.copy()
        if sensitive_keys:
            self.sensitive_keys.update(sensitive_keys)
        
        # 성능 메트릭 저장소
        self._performance_metrics: Dict[str, List[float]] = {}
        self._operation_contexts: Dict[str, AsyncResultLogContext] = {}
    
    # === 핵심 로깅 메서드 ===
    
    def log_chain(
        self,
        operation_name: str,
        log_level: LogLevel = LogLevel.INFO,
        include_performance: bool = None,
        include_chain_info: bool = None,
        custom_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        AsyncResult 체인의 각 단계를 자동 로깅
        
        Args:
            operation_name: 연산 이름 (로그에 표시될 식별자)
            log_level: 로깅 레벨
            include_performance: 성능 정보 포함 여부
            include_chain_info: 체인 정보 포함 여부
            custom_metadata: 커스텀 메타데이터
            
        Returns:
            Callable: AsyncResult를 래핑하는 데코레이터 함수
            
        Example:
            >>> logger = AsyncResultLogger(logging.getLogger(__name__))
            >>> result = await (
            ...     logger.log_chain("user_fetch")(
            ...         AsyncResult.from_async(fetch_user)
            ...     )
            ...     .bind_async(lambda user: 
            ...         logger.log_chain("user_validation")(
            ...             validate_user_async(user)
            ...         )
            ...     )
            ... )
        """
        # 설정 기본값 적용
        include_performance = include_performance if include_performance is not None else self.enable_performance_tracking
        include_chain_info = include_chain_info if include_chain_info is not None else self.enable_chain_tracking
        
        def decorator(async_result: AsyncResult[T, E]) -> AsyncResult[T, E]:
            return self._wrap_async_result(
                async_result,
                operation_name,
                log_level,
                include_performance,
                include_chain_info,
                custom_metadata or {}
            )
        
        return decorator
    
    def _wrap_async_result(
        self,
        async_result: AsyncResult[T, E],
        operation_name: str,
        log_level: LogLevel,
        include_performance: bool,
        include_chain_info: bool,
        custom_metadata: Dict[str, Any]
    ) -> AsyncResult[T, E]:
        """AsyncResult 래핑 및 로깅 추가"""
        
        async def logged_execution():
            operation_id = f"{operation_name}_{int(time.time() * 1000000)}"
            start_time = time.time()
            
            # 컨텍스트 생성
            context = AsyncResultLogContext(
                operation_name=operation_name,
                operation_id=operation_id,
                start_time=start_time,
                metadata=custom_metadata
            )
            
            if include_chain_info:
                self._operation_contexts[operation_id] = context
            
            try:
                # 시작 로그
                self._log_operation_start(context, log_level)
                
                # 실제 AsyncResult 실행
                result = await async_result.to_result()
                
                # 종료 시간 계산
                end_time = time.time()
                duration = end_time - start_time
                
                # 성공/실패에 따른 로깅
                if result.is_success():
                    value = result.unwrap()
                    self._log_operation_success(
                        context, value, duration, log_level, include_performance
                    )
                else:
                    error = result.unwrap_error()
                    self._log_operation_failure(
                        context, error, duration, log_level, include_performance
                    )
                
                # 성능 메트릭 저장
                if include_performance:
                    self._record_performance_metric(operation_name, duration)
                
                return result
                
            except Exception as unexpected_error:
                end_time = time.time()
                duration = end_time - start_time
                
                self._log_operation_exception(
                    context, unexpected_error, duration, log_level
                )
                
                # 에러를 Failure로 래핑하여 반환
                return Failure(unexpected_error)
            
            finally:
                # 컨텍스트 정리
                if include_chain_info and operation_id in self._operation_contexts:
                    del self._operation_contexts[operation_id]
        
        return AsyncResult(logged_execution())
    
    # === 개별 로깅 메서드 ===
    
    def _log_operation_start(
        self,
        context: AsyncResultLogContext,
        log_level: LogLevel
    ):
        """연산 시작 로그"""
        entry = AsyncResultLogEntry(
            timestamp=context.start_time,
            operation_name=context.operation_name,
            operation_id=context.operation_id,
            level=log_level,
            message=f"🚀 {context.operation_name}: 시작",
            chain_depth=context.chain_depth,
            metadata=context.metadata
        )
        
        self._emit_log(entry)
    
    def _log_operation_success(
        self,
        context: AsyncResultLogContext,
        value: Any,
        duration: float,
        log_level: LogLevel,
        include_performance: bool
    ):
        """연산 성공 로그"""
        formatted_value = self._format_value(value)
        
        message_parts = [f"✅ {context.operation_name}: 성공"]
        if include_performance:
            message_parts.append(f"({duration:.3f}초)")
        
        entry = AsyncResultLogEntry(
            timestamp=time.time(),
            operation_name=context.operation_name,
            operation_id=context.operation_id,
            level=log_level,
            message=" ".join(message_parts),
            data=formatted_value,
            duration=duration if include_performance else None,
            chain_depth=context.chain_depth,
            metadata=context.metadata
        )
        
        self._emit_log(entry)
    
    def _log_operation_failure(
        self,
        context: AsyncResultLogContext,
        error: Any,
        duration: float,
        log_level: LogLevel,
        include_performance: bool
    ):
        """연산 실패 로그"""
        error_str = str(error)
        
        message_parts = [f"❌ {context.operation_name}: 실패 - {error_str}"]
        if include_performance:
            message_parts.append(f"({duration:.3f}초)")
        
        entry = AsyncResultLogEntry(
            timestamp=time.time(),
            operation_name=context.operation_name,
            operation_id=context.operation_id,
            level=LogLevel.ERROR,  # 실패는 항상 ERROR 레벨
            message=" ".join(message_parts),
            error=error_str,
            duration=duration if include_performance else None,
            chain_depth=context.chain_depth,
            metadata=context.metadata
        )
        
        self._emit_log(entry)
    
    def _log_operation_exception(
        self,
        context: AsyncResultLogContext,
        exception: Exception,
        duration: float,
        log_level: LogLevel
    ):
        """예상치 못한 예외 로그"""
        error_details = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc()
        }
        
        entry = AsyncResultLogEntry(
            timestamp=time.time(),
            operation_name=context.operation_name,
            operation_id=context.operation_id,
            level=LogLevel.CRITICAL,
            message=f"💥 {context.operation_name}: 예상치 못한 예외 발생",
            error=json.dumps(error_details, ensure_ascii=False),
            duration=duration,
            chain_depth=context.chain_depth,
            metadata=context.metadata
        )
        
        self._emit_log(entry)
    
    # === 데이터 포맷팅 및 마스킹 ===
    
    def _format_value(self, value: Any) -> str:
        """로깅용 값 포맷팅 (민감한 정보 마스킹)"""
        try:
            if value is None:
                return "None"
            
            # 딕셔너리 처리
            if isinstance(value, dict):
                return self._format_dict(value)
            
            # 리스트/튜플 처리
            elif isinstance(value, (list, tuple)):
                return self._format_collection(value)
            
            # 문자열 처리
            elif isinstance(value, str):
                # 길이 제한 적용
                if len(value) > self.max_data_length:
                    return f"{value[:self.max_data_length]}... (길이: {len(value)})"
                return value
            
            # 기타 타입
            else:
                value_str = str(value)
                if len(value_str) > self.max_data_length:
                    return f"{value_str[:self.max_data_length]}... (타입: {type(value).__name__})"
                return value_str
                
        except Exception as format_error:
            return f"<포맷팅 에러: {str(format_error)}>"
    
    def _format_dict(self, data: dict) -> str:
        """딕셔너리 포맷팅 (민감한 정보 마스킹)"""
        if not self.enable_sensitive_masking:
            return str(data)
        
        masked = {}
        
        for key, value in data.items():
            key_lower = str(key).lower()
            
            # 민감한 키 체크
            if any(sensitive in key_lower for sensitive in self.sensitive_keys):
                masked[key] = "***MASKED***"
            else:
                # 값도 재귀적으로 포맷팅
                if isinstance(value, dict):
                    masked[key] = self._format_dict(value)
                elif isinstance(value, (list, tuple)):
                    masked[key] = self._format_collection(value)
                else:
                    value_str = str(value)
                    if len(value_str) > 100:  # 개별 값 길이 제한
                        masked[key] = f"{value_str[:100]}..."
                    else:
                        masked[key] = value
        
        formatted = str(masked)
        if len(formatted) > self.max_data_length:
            return f"{formatted[:self.max_data_length]}... (총 키 수: {len(data)})"
        
        return formatted
    
    def _format_collection(self, collection) -> str:
        """컬렉션 포맷팅"""
        try:
            if len(collection) == 0:
                return str(collection)
            
            # 샘플링 (너무 많은 경우 일부만)
            if len(collection) > 10:
                sample = list(collection)[:10]
                return f"{str(sample)[:-1]}, ... (총 {len(collection)}개 항목)]"
            
            # 각 항목 포맷팅
            formatted_items = []
            for item in collection:
                if isinstance(item, dict):
                    formatted_items.append(self._format_dict(item))
                else:
                    item_str = str(item)
                    if len(item_str) > 50:
                        formatted_items.append(f"{item_str[:50]}...")
                    else:
                        formatted_items.append(item_str)
            
            result = str(formatted_items)
            if len(result) > self.max_data_length:
                return f"{result[:self.max_data_length]}... (총 {len(collection)}개 항목)"
            
            return result
            
        except Exception:
            return f"<컬렉션 (길이: {len(collection)})>"
    
    # === 성능 메트릭 관리 ===
    
    def _record_performance_metric(self, operation_name: str, duration: float):
        """성능 메트릭 기록"""
        if operation_name not in self._performance_metrics:
            self._performance_metrics[operation_name] = []
        
        metrics = self._performance_metrics[operation_name]
        metrics.append(duration)
        
        # 최근 100개만 유지 (메모리 관리)
        if len(metrics) > 100:
            self._performance_metrics[operation_name] = metrics[-100:]
    
    def get_performance_summary(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """성능 요약 정보 반환"""
        if operation_name:
            if operation_name not in self._performance_metrics:
                return {"error": f"연산 '{operation_name}'에 대한 메트릭이 없습니다"}
            
            metrics = self._performance_metrics[operation_name]
            return self._calculate_performance_stats(operation_name, metrics)
        
        # 전체 연산 요약
        summary = {}
        for op_name, metrics in self._performance_metrics.items():
            summary[op_name] = self._calculate_performance_stats(op_name, metrics)
        
        return summary
    
    def _calculate_performance_stats(self, operation_name: str, metrics: List[float]) -> Dict[str, Any]:
        """성능 통계 계산"""
        if not metrics:
            return {"count": 0}
        
        sorted_metrics = sorted(metrics)
        count = len(metrics)
        
        return {
            "count": count,
            "min": min(metrics),
            "max": max(metrics),
            "avg": sum(metrics) / count,
            "p50": sorted_metrics[count // 2],
            "p90": sorted_metrics[int(count * 0.9)],
            "p99": sorted_metrics[int(count * 0.99)] if count >= 100 else sorted_metrics[-1],
            "total_time": sum(metrics)
        }
    
    # === 로그 출력 ===
    
    def _emit_log(self, entry: AsyncResultLogEntry):
        """로그 엔트리 출력"""
        # Python 로깅 레벨 매핑
        level_mapping = {
            LogLevel.TRACE: logging.DEBUG,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        
        python_level = level_mapping.get(entry.level, logging.INFO)
        
        # 추가 정보를 포함한 메시지 생성
        extra_info = {
            "operation_id": entry.operation_id,
            "chain_depth": entry.chain_depth,
            "duration": entry.duration,
            "async_result_data": entry.data,
            "async_result_error": entry.error,
            "async_result_metadata": entry.metadata
        }
        
        # 로그 출력
        self.logger.log(python_level, entry.message, extra=extra_info)


# === 전역 로거 인스턴스 관리 ===

_global_async_loggers: Dict[str, AsyncResultLogger] = {}


def get_async_result_logger(
    logger_name: str = "rfs.async_result",
    **logger_kwargs
) -> AsyncResultLogger:
    """
    글로벌 AsyncResult 로거 반환
    
    Args:
        logger_name: 로거 이름
        **logger_kwargs: AsyncResultLogger 초기화 인자들
        
    Returns:
        AsyncResultLogger: 설정된 로거 인스턴스
    """
    if logger_name not in _global_async_loggers:
        python_logger = logging.getLogger(logger_name)
        _global_async_loggers[logger_name] = AsyncResultLogger(
            python_logger, **logger_kwargs
        )
    
    return _global_async_loggers[logger_name]


def configure_async_result_logging(
    logger_name: str = "rfs.async_result",
    log_level: str = "INFO",
    log_format: Optional[str] = None,
    enable_json_logging: bool = False,
    **logger_kwargs
) -> AsyncResultLogger:
    """
    AsyncResult 로깅 설정
    
    Args:
        logger_name: 로거 이름
        log_level: 로깅 레벨
        log_format: 로그 포맷 (None이면 기본값 사용)
        enable_json_logging: JSON 로깅 활성화
        **logger_kwargs: AsyncResultLogger 추가 설정
        
    Returns:
        AsyncResultLogger: 설정된 로거
    """
    python_logger = logging.getLogger(logger_name)
    python_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 핸들러 설정
    if not python_logger.handlers:
        handler = logging.StreamHandler()
        
        if enable_json_logging:
            # JSON 포맷터 (구조화된 로깅)
            from .formatters import JsonFormatter
            formatter = JsonFormatter()
        else:
            # 기본 포맷터
            if log_format is None:
                log_format = (
                    "%(asctime)s - %(name)s - %(levelname)s - "
                    "%(message)s [%(operation_id)s]"
                )
            formatter = logging.Formatter(log_format)
        
        handler.setFormatter(formatter)
        python_logger.addHandler(handler)
    
    # AsyncResultLogger 생성 및 캐시
    async_logger = AsyncResultLogger(python_logger, **logger_kwargs)
    _global_async_loggers[logger_name] = async_logger
    
    return async_logger


# === 데코레이터 단축 함수 ===

@curry
def log_async_chain(
    operation_name: str,
    log_level: LogLevel = LogLevel.INFO,
    logger_name: str = "rfs.async_result"
):
    """
    AsyncResult 체인 로깅 데코레이터 (커링된 함수)
    
    Args:
        operation_name: 연산 이름
        log_level: 로깅 레벨
        logger_name: 로거 이름
        
    Returns:
        Callable: 데코레이터 함수
        
    Example:
        >>> # 커링된 사용
        >>> log_user_fetch = log_async_chain("user_fetch")
        >>> result = await log_user_fetch(
        ...     AsyncResult.from_async(fetch_user)
        ... )
        >>> 
        >>> # 체이닝 사용
        >>> result = await (
        ...     AsyncResult.from_async(fetch_user)
        ...     .bind_async(log_async_chain("user_validation")(validate_user))
        ... )
    """
    logger = get_async_result_logger(logger_name)
    return logger.log_chain(operation_name, log_level)


# === HOF 패턴 통합 ===

def create_logged_pipeline(*operations, pipeline_name: str = "pipeline"):
    """
    로깅이 통합된 파이프라인 생성 (HOF 패턴)
    
    Args:
        *operations: 파이프라인 연산들
        pipeline_name: 파이프라인 이름
        
    Returns:
        Callable: 로깅이 포함된 파이프라인
        
    Example:
        >>> logged_pipeline = create_logged_pipeline(
        ...     validate_input,
        ...     fetch_data,
        ...     transform_data,
        ...     pipeline_name="data_processing"
        ... )
        >>> result = await logged_pipeline(input_data)
    """
    logger = get_async_result_logger()
    
    # 각 연산을 로깅으로 래핑
    logged_operations = []
    for i, operation in enumerate(operations):
        operation_name = f"{pipeline_name}_step_{i+1}"
        if hasattr(operation, '__name__'):
            operation_name = f"{pipeline_name}_{operation.__name__}"
        
        logged_op = logger.log_chain(operation_name)(operation)
        logged_operations.append(logged_op)
    
    return pipe(*logged_operations)


@asynccontextmanager
async def async_result_log_context(
    operation_name: str,
    logger_name: str = "rfs.async_result",
    **context_metadata
):
    """
    AsyncResult 로깅 컨텍스트 매니저
    
    Args:
        operation_name: 연산 이름
        logger_name: 로거 이름
        **context_metadata: 컨텍스트 메타데이터
        
    Example:
        >>> async with async_result_log_context("batch_processing", user_id="123"):
        ...     result1 = await AsyncResult.from_async(operation1)
        ...     result2 = await AsyncResult.from_async(operation2)
    """
    logger = get_async_result_logger(logger_name)
    operation_id = f"{operation_name}_{int(time.time() * 1000000)}"
    start_time = time.time()
    
    # 시작 로그
    logger.logger.info(
        f"🏁 {operation_name} 컨텍스트 시작",
        extra={
            "operation_id": operation_id,
            "context_metadata": context_metadata
        }
    )
    
    try:
        yield operation_id
    except Exception as e:
        # 컨텍스트 내 에러 로깅
        logger.logger.error(
            f"💥 {operation_name} 컨텍스트 에러: {str(e)}",
            extra={
                "operation_id": operation_id,
                "error": str(e),
                "context_metadata": context_metadata
            }
        )
        raise
    finally:
        # 종료 로그
        duration = time.time() - start_time
        logger.logger.info(
            f"🏁 {operation_name} 컨텍스트 종료 ({duration:.3f}초)",
            extra={
                "operation_id": operation_id,
                "duration": duration,
                "context_metadata": context_metadata
            }
        )


# === 사용 예시 ===

def get_usage_examples():
    """사용 예시 반환"""
    return {
        "basic_logging": '''
from rfs.logging.async_logging import get_async_result_logger
from rfs.async_pipeline import AsyncResult

logger = get_async_result_logger()

# 기본 체인 로깅
result = await (
    logger.log_chain("user_fetch")(
        AsyncResult.from_async(fetch_user)
    )
    .bind_async(lambda user: 
        logger.log_chain("user_validation")(
            validate_user_async(user)
        )
    )
)
        ''',
        
        "curried_logging": '''
from rfs.logging.async_logging import log_async_chain

# 커링된 로깅 함수 생성
log_user_fetch = log_async_chain("user_fetch")
log_user_validation = log_async_chain("user_validation")

result = await (
    log_user_fetch(AsyncResult.from_async(fetch_user))
    .bind_async(lambda user: log_user_validation(validate_user_async(user)))
)
        ''',
        
        "pipeline_logging": '''
from rfs.logging.async_logging import create_logged_pipeline

# 로깅이 통합된 파이프라인
user_processing_pipeline = create_logged_pipeline(
    validate_input,
    fetch_user_data,
    enrich_user_profile,
    format_response,
    pipeline_name="user_processing"
)

result = await user_processing_pipeline(user_input)
        ''',
        
        "context_logging": '''
from rfs.logging.async_logging import async_result_log_context

async with async_result_log_context("batch_processing", batch_id="batch_123"):
    users = await AsyncResult.from_async(lambda: fetch_users())
    processed = await AsyncResult.from_async(lambda: process_users(users))
    saved = await AsyncResult.from_async(lambda: save_results(processed))
        ''',
        
        "performance_monitoring": '''
from rfs.logging.async_logging import configure_async_result_logging

# 성능 추적이 활성화된 로거 설정
logger = configure_async_result_logging(
    logger_name="app.performance",
    log_level="INFO",
    enable_performance_tracking=True,
    enable_json_logging=True
)

# 사용 후 성능 요약 확인
performance_summary = logger.get_performance_summary("user_fetch")
print(f"평균 응답 시간: {performance_summary['avg']:.3f}초")
        '''
    }


# === 모듈 정보 ===

__version__ = "1.0.0"
__author__ = "RFS Framework Team"

def get_module_info():
    """모듈 정보 반환"""
    return {
        "name": "RFS AsyncResult Logging",
        "version": __version__,
        "features": [
            "AsyncResult 체인 자동 로깅",
            "민감한 정보 자동 마스킹",
            "성능 메트릭 추적",
            "구조화된 로깅 지원",
            "HOF 패턴 통합",
            "컨텍스트 매니저 지원"
        ],
        "dependencies": {
            "rfs_framework": ">= 4.3.0",
            "python": ">= 3.8"
        }
    }