"""
Enhanced Logger Implementation

향상된 로거 구현 - 컨텍스트 인식, 구조화된 로깅
"""

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional, Union

_log_context: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})
_trace_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "_trace_context", default=None
)


class LogLevel(IntEnum):
    """로그 레벨"""

    TRACE = 5
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    FATAL = logging.CRITICAL


class LogContext:
    """로그 컨텍스트"""

    def __init__(self, **fields):
        self.fields = fields
        self._token = None

    def __enter__(self):
        """컨텍스트 진입"""
        current = _log_context.get()
        updated = {**current, **self.fields}
        self._token = _log_context.set(updated)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료"""
        if self._token:
            _log_context.reset(self._token)

    def add_field(self, key: str, value: Any):
        """필드 추가"""
        self.fields = {**self.fields, key: value}

    def remove_field(self, key: str) -> None:
        """필드 제거"""
        self.fields = {k: v for k, v in self.fields.items() if k != key}

    def get_fields(self) -> dict[str, Any]:
        """필드 조회"""
        return dict(self.fields)


class RFSLogger:
    """
    RFS 프레임워크 로거

    Features:
    - 구조화된 로깅
    - 컨텍스트 전파
    - 분산 추적
    - 성능 메트릭
    """

    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        handlers: Optional[List[logging.Handler]] = None,
    ):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        logging.addLevelName(LogLevel.TRACE, "TRACE")
        if handlers:
            for handler in handlers:
                self.logger.addHandler(handler)
        elif not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(self._get_default_formatter())
            self.logger.addHandler(handler)
        self.log_counts = {level: 0 for level in LogLevel}

    def trace(self, message: str, **kwargs):
        """TRACE 레벨 로그"""
        self._log(LogLevel.TRACE, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """DEBUG 레벨 로그"""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """INFO 레벨 로그"""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """WARNING 레벨 로그"""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, error=None, **kwargs):
        """ERROR 레벨 로그"""
        if error:
            kwargs["error"] = {"error": str(error)}
            kwargs["error_type"] = {"error_type": type(error).__name__}
            kwargs["stacktrace"] = {"stacktrace": traceback.format_exc()}
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, error=None, **kwargs):
        """CRITICAL 레벨 로그"""
        if error:
            kwargs["error"] = {"error": str(error)}
            kwargs["error_type"] = {"error_type": type(error).__name__}
            kwargs["stacktrace"] = {"stacktrace": traceback.format_exc()}
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def fatal(self, message: str, error=None, **kwargs):
        """FATAL 레벨 로그 (CRITICAL의 별칭)"""
        self.critical(message, error, **kwargs)

    def _log(self, level: LogLevel, message: str, **kwargs):
        """내부 로그 메서드"""
        self.log_counts = {**self.log_counts, level: self.log_counts[level] + 1}
        context = _log_context.get()
        fields = {**context, **kwargs}
        from .tracing import get_current_span

        span = get_current_span()
        if span:
            fields["trace_id"] = {"trace_id": span.trace_id}
            fields["span_id"] = {"span_id": span.span_id}
        fields["timestamp"] = {"timestamp": datetime.now().isoformat()}
        fields["logger"] = {"logger": self.name}
        fields["level"] = {"level": logging.getLevelName(level)}
        record = self._create_log_record(level, message, fields)
        self.logger.handle(record)

    def _create_log_record(
        self, level: int, message: str, fields: Dict[str, Any]
    ) -> logging.LogRecord:
        """로그 레코드 생성"""
        record = self.logger.makeRecord(
            self.name, level, "(unknown file)", 0, message, (), None
        )
        record.fields = fields
        record.structured = True
        return record

    def _get_default_formatter(self) -> logging.Formatter:
        """기본 포매터"""
        try:
            from .formatters import StructuredFormatter
            return StructuredFormatter()
        except ImportError:
            return logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    def with_context(self, **fields) -> LogContext:
        """컨텍스트 추가"""
        return LogContext(**fields)

    def with_fields(self, **fields) -> "RFSLogger":
        """필드가 추가된 새 로거"""
        new_logger = RFSLogger(
            f"{self.name}[{','.join(fields.keys())}]",
            level=LogLevel(self.logger.level),
            handlers=list(self.logger.handlers),
        )
        current = _log_context.get()
        _log_context.set({**current, **fields})
        return new_logger

    def get_child(self, suffix: str) -> "RFSLogger":
        """자식 로거 생성"""
        return RFSLogger(
            f"{self.name}.{suffix}",
            level=LogLevel(self.logger.level),
            handlers=list(self.logger.handlers),
        )

    def set_level(self, level: LogLevel):
        """로그 레벨 설정"""
        self.logger.setLevel(level)

    def add_handler(self, handler: logging.Handler):
        """핸들러 추가"""
        self.logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler):
        """핸들러 제거"""
        self.logger.removeHandler(handler)

    def get_metrics(self) -> dict[str, int]:
        """로그 메트릭 조회"""
        return {level.name: count for level, count in self.log_counts.items()}

    def reset_metrics(self) -> None:
        """메트릭 리셋"""
        self.log_counts = {level: 0 for level in LogLevel}


_logger_cache: dict[str, RFSLogger] = {}


def get_logger(name: Optional[str] = None) -> RFSLogger:
    """로거 획득"""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "root")
        else:
            name = "root"
    if name not in _logger_cache:
        _logger_cache[name] = RFSLogger(name)
    return _logger_cache[name]


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    format="structured",
    handlers: Optional[List[logging.Handler]] = None,
    **kwargs,
):
    """
    로깅 설정

    Args:
        level: 로그 레벨
        format: 로그 포맷 ('structured', 'json', 'colored', 'compact')
        handlers: 핸들러 목록
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    match format:
        case "json":
            from .formatters import JsonFormatter

            formatter = JsonFormatter(**kwargs)
        case "colored":
            from .formatters import ColoredFormatter

            formatter = ColoredFormatter(**kwargs)
        case "compact":
            from .formatters import CompactFormatter

            formatter = CompactFormatter(**kwargs)
        case _:
            from .formatters import StructuredFormatter

            formatter = StructuredFormatter(**kwargs)
    if handlers:
        for handler in handlers:
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    logging.addLevelName(LogLevel.TRACE, "TRACE")


def set_global_context(**fields):
    """전역 로그 컨텍스트 설정"""
    current = _log_context.get()
    _log_context.set({**current, **fields})


def clear_global_context():
    """전역 로그 컨텍스트 클리어"""
    _log_context.set({})


def get_global_context() -> Dict[str, Any]:
    """전역 로그 컨텍스트 조회"""
    return _log_context.get()
