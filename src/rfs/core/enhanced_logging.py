"""
RFS v4.1 Enhanced Logging System
향상된 로깅 시스템 with 구조화된 로그, 메트릭 추적, 컨텍스트 관리

주요 기능:
- 구조화된 로깅 (JSON, 메타데이터)
- 성능 메트릭 자동 수집
- 컨텍스트 추적 (요청 ID, 사용자 정보 등)
- 로그 레벨별 필터링 및 라우팅
- 비동기 로그 처리
"""

import asyncio
import inspect
import json
import logging
import sys
import time
import traceback
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .config import get_config
from .result import Failure, Result, Success


class LogLevel(Enum):
    """로그 레벨"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_value(cls, value):
        """
        안전한 LogLevel 생성
        딕셔너리, 문자열 등 다양한 입력 형태를 처리

        Args:
            value: 로그 레벨 값 (str, dict, 기타)

        Returns:
            LogLevel: 파싱된 LogLevel enum

        Raises:
            ValueError: 유효하지 않은 로그 레벨값인 경우
        """
        # 이미 LogLevel 인스턴스인 경우
        if isinstance(value, cls):
            return value

        # 딕셔너리 형태 처리 (Cloud Run 환경 대응)
        if isinstance(value, dict):
            if 'log_level' in value:
                value = value['log_level']
            else:
                # 딕셔너리에 log_level 키가 없으면 기본값 반환
                return cls.INFO

        # 문자열이 아닌 경우 문자열로 변환
        if not isinstance(value, str):
            value = str(value)

        # 대소문자 무관하게 처리
        value = value.upper().strip()

        # 유효한 값인지 확인
        for level in cls:
            if level.value == value:
                return level

        # 유효하지 않은 값인 경우 기본값 반환 (안전한 Fallback)
        return cls.INFO


@dataclass
class LogContext:
    """로그 컨텍스트"""

    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    correlation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    service_name: Optional[str] = None
    operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class LogEntry:
    """로그 엔트리"""

    timestamp: datetime
    level: LogLevel
    message: str
    logger_name: str
    module: Optional[str] = None
    function: Optional[str] = None
    line_number: Optional[int] = None
    context: Optional[LogContext] = None
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    error_type: Optional[str] = None
    error_traceback: Optional[str] = None
    execution_time_ms: Optional[float] = None
    memory_used_mb: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "logger": self.logger_name,
            "module": self.module,
            "function": self.function,
            "line": self.line_number,
            "data": self.data,
            "tags": self.tags,
        }
        if self.context:
            data["context"] = {"context": self.context.to_dict()}
        if self.error_type:
            data = {
                **data,
                "error": {
                    "error": {
                        "type": self.error_type,
                        "traceback": self.error_traceback,
                    }
                },
            }
        if self.execution_time_ms is not None:
            data = {
                **data,
                "metrics": {
                    "metrics": {
                        "execution_time_ms": self.execution_time_ms,
                        "memory_used_mb": self.memory_used_mb,
                    }
                },
            }
        return {k: v for k, v in data.items() if v is not None}

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


_log_context: ContextVar[Optional[LogContext]] = ContextVar("log_context", default=None)


class EnhancedLogger:
    """향상된 로거"""

    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        enable_console: bool = True,
        enable_file: bool = False,
        file_path: Optional[str] = None,
        enable_json: bool = True,
        enable_async: bool = True,
    ):
        self.name = name
        self.level = level
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.file_path = Path(file_path) if file_path else None
        self.enable_json = enable_json
        self.enable_async = enable_async
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.value))
        self._setup_handlers()
        self._log_queue: Optional[asyncio.Queue] = None
        self._log_processor_task: Optional[asyncio.Task] = None
        self._async_initialized = False
        self._filters: List[Callable[[LogEntry], bool]] = []
        self._handlers: List[Callable[[LogEntry], None]] = []

    def _setup_handlers(self) -> None:
        """핸들러 설정"""
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            if self.enable_json:
                console_handler.setFormatter(self._create_json_formatter())
            else:
                console_handler.setFormatter(self._create_standard_formatter())
            self._logger.addHandler(console_handler)
        if self.enable_file and self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(self.file_path)
            file_handler.setFormatter(self._create_json_formatter())
            self._logger.addHandler(file_handler)

    async def _initialize_async_components(self) -> None:
        """비동기 컴포넌트 초기화"""
        if not self.enable_async or self._async_initialized:
            return
        try:
            self._log_queue = asyncio.Queue()
            self._log_processor_task = asyncio.create_task(self._process_logs())
            self._async_initialized = True
        except RuntimeError:
            self.enable_async = False

    def _create_json_formatter(self) -> logging.Formatter:
        """JSON 포매터 생성"""

        class JSONFormatter(logging.Formatter):

            def format(self, record):
                if hasattr(record, "_log_entry"):
                    return record._log_entry.to_json()
                return super().format(record)

        return JSONFormatter()

    def _create_standard_formatter(self) -> logging.Formatter:
        """표준 포매터 생성"""
        return logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    def _get_caller_info(self) -> Dict[str, Any]:
        """호출자 정보 추출"""
        frame = inspect.currentframe()
        try:
            for _ in range(10):
                frame = frame.f_back
                if not frame:
                    break
                code = frame.f_code
                filename = code.co_filename
                if "logging" in filename or "enhanced_logging" in filename:
                    continue
                return {
                    "module": Path(filename).stem,
                    "function": code.co_name,
                    "line_number": frame.f_lineno,
                }
            return {}
        except Exception:
            return {}
        finally:
            del frame

    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ) -> LogEntry:
        """로그 엔트리 생성"""
        caller_info = self._get_caller_info()
        context = _log_context.get()
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            logger_name=self.name,
            module=caller_info.get("module"),
            function=caller_info.get("function"),
            line_number=caller_info.get("line_number"),
            context=context,
            data=data or {},
            tags=tags or [],
        )
        if error:
            entry.error_type = type(error).__name__
            entry.error_traceback = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
        for key, value in kwargs.items():
            if key not in ["execution_time_ms", "memory_used_mb"]:
                entry.data = {**entry.data, key: value}
        entry.execution_time_ms = kwargs.get("execution_time_ms")
        entry.memory_used_mb = kwargs.get("memory_used_mb")
        return entry

    async def _process_logs(self) -> None:
        """비동기 로그 처리"""
        while True:
            try:
                entry = await self._log_queue.get()
                if entry is None:
                    break
                await self._write_log_entry(entry)
                self._log_queue.task_done()
            except Exception as e:
                print(f"Log processing error: {e}", file=sys.stderr)

    async def _write_log_entry(self, entry: LogEntry) -> None:
        """로그 엔트리 쓰기"""
        for filter_func in self._filters:
            if not filter_func(entry):
                return
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                print(f"Log handler error: {e}", file=sys.stderr)
        log_level = getattr(logging, entry.level.value)
        record = self._logger.makeRecord(
            self.name,
            log_level,
            entry.module or "",
            entry.line_number or 0,
            entry.message,
            (),
            None,
        )
        record._log_entry = entry
        self._logger.handle(record)

    def _log(
        self,
        level: LogLevel,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ) -> None:
        """내부 로그 메서드"""
        if level.value < self.level.value:
            return
        entry = self._create_log_entry(level, message, data, tags, error, **kwargs)
        if self.enable_async and self._log_queue:
            try:
                self._log_queue.put_nowait(entry)
            except asyncio.QueueFull:
                self._sync_log_entry(entry)
        else:
            self._sync_log_entry(entry)

    def _sync_log_entry(self, entry: LogEntry) -> None:
        """동기식 로그 엔트리 처리"""
        for filter_func in self._filters:
            if not filter_func(entry):
                return
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                print(f"Log handler error: {e}", file=sys.stderr)
        log_level = getattr(logging, entry.level.value)
        record = self._logger.makeRecord(
            self.name,
            log_level,
            entry.module or "",
            entry.line_number or 0,
            entry.message,
            (),
            None,
        )
        record._log_entry = entry
        self._logger.handle(record)

    def log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[LogContext] = None,
        **kwargs,
    ) -> None:
        """공개 로그 메서드"""
        if self.enable_async and (not self._async_initialized):
            try:
                loop = asyncio.get_running_loop()
                if loop and (not loop.is_closed()):
                    self._log_queue = asyncio.Queue()
                    self._log_processor_task = asyncio.create_task(self._process_logs())
                    self._async_initialized = True
            except RuntimeError:
                self.enable_async = False
        data = kwargs
        tags = None
        kwargs = {k: v for k, v in kwargs.items() if k != "exception', None"}
        if context:
            data = {**data, **context.extra_data}
            tags = context.tags
            if context.exception and (not error):
                error = context.exception
        self._log(level, message, data, tags, error)

    def debug(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """디버그 로그"""
        self._log(LogLevel.DEBUG, message, data, tags, **kwargs)

    def info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """정보 로그"""
        self._log(LogLevel.INFO, message, data, tags, **kwargs)

    def warning(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """경고 로그"""
        self._log(LogLevel.WARNING, message, data, tags, **kwargs)

    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """에러 로그"""
        self._log(LogLevel.ERROR, message, data, tags, error, **kwargs)

    def critical(
        self,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """치명적 에러 로그"""
        self._log(LogLevel.CRITICAL, message, data, tags, error, **kwargs)

    def add_filter(self, filter_func: Callable[[LogEntry], bool]) -> None:
        """필터 추가"""
        self._filters = self._filters + [filter_func]

    def add_handler(self, handler_func: Callable[[LogEntry], None]) -> None:
        """핸들러 추가"""
        self._handlers = self._handlers + [handler_func]

    async def close(self) -> None:
        """로거 종료"""
        if self._log_queue:
            await self._log_queue.join()
            await self._log_queue.put(None)
            if self._log_processor_task:
                await self._log_processor_task


_loggers: Dict[str, EnhancedLogger] = {}
_default_logger: Optional[EnhancedLogger] = None


def get_logger(
    name: Optional[str] = None, level: LogLevel = LogLevel.INFO, **kwargs
) -> EnhancedLogger:
    """로거 조회/생성"""
    if name is None:
        name = "rfs"
    if name not in _loggers:
        _loggers[name] = EnhancedLogger(name, level, **kwargs)
    return _loggers[name]


def get_default_logger() -> EnhancedLogger:
    """기본 로거 조회"""
    global _default_logger
    if _default_logger is None:
        try:
            config = get_config()
            log_level = getattr(config, "log_level", "INFO")
            
            # 안전한 LogLevel 생성 (딕셔너리, 문자열 모두 처리)
            safe_log_level = LogLevel.from_value(log_level)
            _default_logger = get_logger("rfs", safe_log_level)
            
        except Exception as e:
            # 설정 로드 실패 시 안전한 기본값으로 생성
            import logging
            logging.error(f"기본 로거 생성 중 오류 발생: {e}")
            _default_logger = get_logger("rfs", LogLevel.INFO)
            
    return _default_logger

def create_safe_logger(name: str, level=None, **kwargs) -> EnhancedLogger:
    """
    안전한 로거 생성
    다양한 log_level 입력 형태를 방어적으로 처리
    
    Args:
        name: 로거 이름
        level: 로그 레벨 (str, dict, LogLevel, 기타)
        **kwargs: 추가 로거 설정
    
    Returns:
        EnhancedLogger: 생성된 로거 인스턴스
    """
    try:
        if level is not None:
            level = LogLevel.from_value(level)
        else:
            level = LogLevel.INFO
        return get_logger(name, level, **kwargs)
    except Exception as e:
        # 생성 실패 시 기본 설정으로 생성
        import logging
        logging.error(f"안전 로거 생성 중 오류 발생: {e}")
        return get_logger(name, LogLevel.INFO, **kwargs)


def validate_log_level_config(config_value):
    """
    로그 레벨 설정값 검증 및 정규화
    
    Args:
        config_value: 설정에서 가져온 로그 레벨 값
        
    Returns:
        LogLevel: 검증된 LogLevel enum
        
    Example:
        >>> validate_log_level_config('DEBUG')
        LogLevel.DEBUG
        >>> validate_log_level_config({'log_level': 'INFO'})
        LogLevel.INFO
        >>> validate_log_level_config('invalid')
        LogLevel.INFO
    """
    try:
        return LogLevel.from_value(config_value)
    except Exception:
        # 모든 예외에 대해 안전한 기본값 반환
        return LogLevel.INFO


def set_log_context(context: LogContext) -> None:
    """로그 컨텍스트 설정"""
    _log_context.set(context)


def get_log_context() -> Optional[LogContext]:
    """로그 컨텍스트 조회"""
    return _log_context.get()


def clear_log_context() -> None:
    """로그 컨텍스트 제거"""
    _log_context.set(None)


def log_info(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs,
) -> None:
    """정보 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.info(message, data, tags, **kwargs)


def log_warning(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs,
) -> None:
    """경고 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.warning(message, data, tags, **kwargs)


def log_error(
    message: str,
    error: Optional[Exception] = None,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs,
) -> None:
    """에러 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.error(message, error, data, tags, **kwargs)


def log_debug(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs,
) -> None:
    """디버그 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.debug(message, data, tags, **kwargs)


def log_critical(
    message: str,
    error: Optional[Exception] = None,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs,
) -> None:
    """치명적 에러 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.critical(message, error, data, tags, **kwargs)


def log_execution(
    level: LogLevel = LogLevel.INFO,
    include_args: bool = False,
    include_result: bool = False,
    logger_name: Optional[str] = None,
):
    """함수 실행 로깅 데코레이터"""

    def decorator(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(logger_name) if logger_name else get_default_logger()
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__qualname__}"
            log_data = {"function": func_name}
            if include_args:
                log_data["args"] = {"args": str(args)}
                log_data["kwargs"] = {"kwargs": str(kwargs)}
            logger._log(level, f"Function started: {func_name}", log_data)
            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                success_data = {
                    "function": func_name,
                    "success": True,
                    "execution_time_ms": execution_time,
                }
                if include_result:
                    success_data["result"] = {"result": str(result)}
                logger._log(level, f"Function completed: {func_name}", success_data)
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                error_data = {
                    "function": func_name,
                    "success": False,
                    "execution_time_ms": execution_time,
                }
                logger.error(f"Function failed: {func_name}", e, error_data)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(logger_name) if logger_name else get_default_logger()
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__qualname__}"
            log_data = {"function": func_name}
            if include_args:
                log_data["args"] = {"args": str(args)}
                log_data["kwargs"] = {"kwargs": str(kwargs)}
            logger._log(level, f"Function started: {func_name}", log_data)
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                success_data = {
                    "function": func_name,
                    "success": True,
                    "execution_time_ms": execution_time,
                }
                if include_result:
                    success_data["result"] = {"result": str(result)}
                logger._log(level, f"Function completed: {func_name}", success_data)
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                error_data = {
                    "function": func_name,
                    "success": False,
                    "execution_time_ms": execution_time,
                }
                logger.error(f"Function failed: {func_name}", e, error_data)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


class LogContextManager:
    """로그 컨텍스트 관리자"""

    def __init__(self, context: LogContext):
        self.context = context
        self.previous_context = None

    def __enter__(self):
        self.previous_context = get_log_context()
        set_log_context(self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_log_context(self.previous_context)


def with_log_context(context: LogContext) -> LogContextManager:
    """로그 컨텍스트와 함께 실행"""
    return LogContextManager(context)
