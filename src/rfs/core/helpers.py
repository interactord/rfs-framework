"""
Core Helper Functions

RFS Framework의 핵심 헬퍼 함수들
싱글톤 패턴과 간편한 접근을 제공
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, TypeVar

from ..events import Event, EventBus
from .config import ConfigManager, RFSConfig
from .enhanced_logging import LogContext, LogLevel, get_default_logger
from .singleton import SingletonMeta

# 로거 설정 - Enhanced Logger 통합
logger = logging.getLogger(__name__)
_enhanced_logger = get_default_logger()

T = TypeVar("T")


# ============= Configuration Helpers =============

_config_instance = None


def get_config() -> RFSConfig:
    """
    전역 설정 인스턴스 반환

    Returns:
        RFSConfig: 애플리케이션 설정
    """
    # global _config_instance - removed for functional programming
    if _config_instance is None:
        config_manager = ConfigManager()
        _config_instance = config_manager.from_env()
    return _config_instance


def get(key: str, default: Any = None) -> Any:
    """
    설정 값 가져오기

    Args:
        key: 설정 키 (점 표기법 지원)
        default: 기본값

    Returns:
        설정 값 또는 기본값
    """
    config = get_config()

    # 점 표기법 처리 (예: "database.host")
    keys = key.split(".")
    value = config

    try:
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif type(value).__name__ == "dict":
                value = value.get(k)
            else:
                return default
        return value
    except (AttributeError, KeyError, TypeError):
        return default


# ============= Event System Helpers =============


class GlobalEventBus(metaclass=SingletonMeta):
    """전역 이벤트 버스 싱글톤"""

    def __init__(self):
        self._bus = EventBus()

    @property
    def bus(self) -> EventBus:
        return self._bus


def get_event_bus() -> EventBus:
    """
    전역 이벤트 버스 인스턴스 반환

    Returns:
        EventBus: 전역 이벤트 버스
    """
    return GlobalEventBus().bus


def create_event(
    event_type: str,
    data: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None,
    source: str = None,
    correlation_id: str = None,
) -> Event:
    """
    이벤트 생성 헬퍼

    Args:
        event_type: 이벤트 타입
        data: 이벤트 데이터
        metadata: 메타데이터
        source: 이벤트 소스
        correlation_id: 상관관계 ID

    Returns:
        Event: 생성된 이벤트
    """
    return Event(
        event_type=event_type,
        data=data or {},
        metadata=metadata or {},
        source=source or "system",
        correlation_id=correlation_id,
    )


async def publish_event(event_type: str, data: Dict[str, Any] = None, **kwargs) -> None:
    """
    이벤트 발행 헬퍼

    Args:
        event_type: 이벤트 타입
        data: 이벤트 데이터
        **kwargs: 추가 이벤트 속성
    """
    event = create_event(event_type, data, **kwargs)
    bus = get_event_bus()
    await bus.publish(event)


# ============= Logging Helpers =============


def setup_logging(level="INFO", format: str = None, handlers: list = None) -> None:
    """
    로깅 설정

    Args:
        level: 로그 레벨
        format: 로그 포맷
        handlers: 로그 핸들러 리스트
    """
    log_format = format or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=getattr(logging, level.upper()), format=log_format, handlers=handlers
    )


def log_info(message: str, **kwargs) -> None:
    """
    INFO 레벨 로그

    Args:
        message: 로그 메시지
        **kwargs: 추가 컨텍스트
    """
    # Enhanced Logger 통합
    context = LogContext(extra_data=kwargs, timestamp=datetime.now())
    _enhanced_logger.log(LogLevel.INFO, message, context=context)

    # Backward compatibility
    extra = {"timestamp": datetime.now().isoformat(), **kwargs}
    logger.info(message, extra=extra)


def log_warning(message: str, **kwargs) -> None:
    """
    WARNING 레벨 로그

    Args:
        message: 로그 메시지
        **kwargs: 추가 컨텍스트
    """
    # Enhanced Logger 통합
    context = LogContext(extra_data=kwargs, timestamp=datetime.now())
    _enhanced_logger.log(LogLevel.WARNING, message, context=context)

    # Backward compatibility
    extra = {"timestamp": datetime.now().isoformat(), **kwargs}
    logger.warning(message, extra=extra)


def log_error(message: str, exception: Exception = None, **kwargs) -> None:
    """
    ERROR 레벨 로그

    Args:
        message: 로그 메시지
        exception: 예외 객체
        **kwargs: 추가 컨텍스트
    """
    # Enhanced Logger 통합
    error_data = {"exception": str(exception) if exception else None, **kwargs}
    context = LogContext(
        extra_data=error_data, timestamp=datetime.now(), exception=exception
    )
    _enhanced_logger.log(LogLevel.ERROR, message, context=context)

    # Backward compatibility
    extra = {
        "timestamp": datetime.now().isoformat(),
        "exception": str(exception) if exception else None,
        **kwargs,
    }
    logger.error(message, exc_info=exception, extra=extra)


def log_debug(message: str, **kwargs) -> None:
    """
    DEBUG 레벨 로그

    Args:
        message: 로그 메시지
        **kwargs: 추가 컨텍스트
    """
    # Enhanced Logger 통합
    context = LogContext(extra_data=kwargs, timestamp=datetime.now())
    _enhanced_logger.log(LogLevel.DEBUG, message, context=context)

    # Backward compatibility
    extra = {"timestamp": datetime.now().isoformat(), **kwargs}
    logger.debug(message, extra=extra)


# ============= Performance Monitoring Helpers =============

import time
from contextlib import contextmanager


@contextmanager
def monitor_performance(operation_name: str):
    """
    성능 모니터링 컨텍스트 매니저

    Args:
        operation_name: 작업 이름

    Example:
        with monitor_performance("database_query"):
            result = await db.query()
    """
    start_time = time.time()

    try:
        log_debug(f"Starting operation: {operation_name}")
        yield
    finally:
        elapsed_time = time.time() - start_time
        log_info(
            f"Operation completed: {operation_name}",
            duration_ms=elapsed_time * 1000,
            operation=operation_name,
        )


def record_metric(
    metric_name: str, value: float, unit: str = None, tags: Dict[str, str] = None
) -> None:
    """
    메트릭 기록

    Args:
        metric_name: 메트릭 이름
        value: 메트릭 값
        unit: 단위
        tags: 태그
    """
    log_info(
        f"Metric recorded: {metric_name}",
        metric_name=metric_name,
        value=value,
        unit=unit,
        tags=tags or {},
    )


# ============= Enhanced Logging Convenience Functions =============


def get_enhanced_logger():
    """
    Enhanced Logger 인스턴스 반환

    Returns:
        EnhancedLogger: 전역 Enhanced Logger
    """
    return _enhanced_logger


def log_with_context(
    level: str, message: str, context_data: Dict[str, Any] = None, **kwargs
) -> None:
    """
    컨텍스트와 함께 로그 기록

    Args:
        level: 로그 레벨 (info, warning, error, debug)
        message: 로그 메시지
        context_data: 컨텍스트 데이터
        **kwargs: 추가 컨텍스트
    """
    log_level = getattr(LogLevel, level.upper(), LogLevel.INFO)
    context_data = context_data or {}
    context_data = {**context_data, **kwargs}
    context = LogContext(extra_data=context_data, timestamp=datetime.now())
    _enhanced_logger.log(log_level, message, context=context)


# ============= Export Helpers =============

__all__ = [
    # Configuration
    "get_config",
    "get",
    # Event System
    "get_event_bus",
    "create_event",
    "publish_event",
    # Logging (Legacy + Enhanced)
    "setup_logging",
    "log_info",
    "log_warning",
    "log_error",
    "log_debug",
    "get_enhanced_logger",
    "log_with_context",
    # Performance
    "monitor_performance",
    "record_metric",
]
