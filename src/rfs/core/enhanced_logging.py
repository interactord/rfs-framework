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
import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union, List, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextvars import ContextVar
from pathlib import Path
import inspect
import time
from functools import wraps

from .result import Result, Success, Failure
from .config import get_config


class LogLevel(Enum):
    """로그 레벨"""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """로그 컨텍스트"""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    # 비즈니스 컨텍스트
    tenant_id: Optional[str] = None
    service_name: Optional[str] = None
    operation: Optional[str] = None
    
    # 메타데이터
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
    
    # 위치 정보
    module: Optional[str] = None
    function: Optional[str] = None
    line_number: Optional[int] = None
    
    # 컨텍스트
    context: Optional[LogContext] = None
    
    # 추가 데이터
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # 에러 정보 (ERROR/CRITICAL 레벨용)
    error_type: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # 성능 메트릭
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
            "tags": self.tags
        }
        
        if self.context:
            data["context"] = self.context.to_dict()
        
        if self.error_type:
            data["error"] = {
                "type": self.error_type,
                "traceback": self.error_traceback
            }
        
        if self.execution_time_ms is not None:
            data["metrics"] = {
                "execution_time_ms": self.execution_time_ms,
                "memory_used_mb": self.memory_used_mb
            }
        
        return {k: v for k, v in data.items() if v is not None}
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


# 전역 컨텍스트 변수
_log_context: ContextVar[Optional[LogContext]] = ContextVar('log_context', default=None)


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
        enable_async: bool = True
    ):
        self.name = name
        self.level = level
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.file_path = Path(file_path) if file_path else None
        self.enable_json = enable_json
        self.enable_async = enable_async
        
        # 표준 로거 설정
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.value))
        
        # 핸들러 설정
        self._setup_handlers()
        
        # 비동기 로그 큐
        self._log_queue: Optional[asyncio.Queue] = None
        self._log_processor_task: Optional[asyncio.Task] = None
        
        # 비동기 컴포넌트는 지연 초기화
        self._async_initialized = False
        
        # 필터와 핸들러
        self._filters: List[Callable[[LogEntry], bool]] = []
        self._handlers: List[Callable[[LogEntry], None]] = []
    
    def _setup_handlers(self) -> None:
        """핸들러 설정"""
        # 기존 핸들러 제거
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)
        
        # 콘솔 핸들러
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            if self.enable_json:
                console_handler.setFormatter(self._create_json_formatter())
            else:
                console_handler.setFormatter(self._create_standard_formatter())
            self._logger.addHandler(console_handler)
        
        # 파일 핸들러
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
            # 이벤트 루프가 없는 경우 동기 모드로 폴백
            self.enable_async = False
    
    def _create_json_formatter(self) -> logging.Formatter:
        """JSON 포매터 생성"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                # LogEntry에서 JSON 변환
                if hasattr(record, '_log_entry'):
                    return record._log_entry.to_json()
                return super().format(record)
        
        return JSONFormatter()
    
    def _create_standard_formatter(self) -> logging.Formatter:
        """표준 포매터 생성"""
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _get_caller_info(self) -> Dict[str, Any]:
        """호출자 정보 추출"""
        frame = inspect.currentframe()
        try:
            # 스택을 올라가면서 로거 메서드가 아닌 첫 번째 프레임 찾기
            for _ in range(10):  # 최대 10 레벨까지
                frame = frame.f_back
                if not frame:
                    break
                
                code = frame.f_code
                filename = code.co_filename
                
                # 로거 관련 파일은 건너뛰기
                if 'logging' in filename or 'enhanced_logging' in filename:
                    continue
                
                return {
                    "module": Path(filename).stem,
                    "function": code.co_name,
                    "line_number": frame.f_lineno
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
        **kwargs
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
            tags=tags or []
        )
        
        # 에러 정보 추가
        if error:
            entry.error_type = type(error).__name__
            entry.error_traceback = ''.join(traceback.format_exception(
                type(error), error, error.__traceback__
            ))
        
        # 추가 데이터
        for key, value in kwargs.items():
            if key not in ['execution_time_ms', 'memory_used_mb']:
                entry.data[key] = value
        
        # 메트릭 정보
        entry.execution_time_ms = kwargs.get('execution_time_ms')
        entry.memory_used_mb = kwargs.get('memory_used_mb')
        
        return entry
    
    async def _process_logs(self) -> None:
        """비동기 로그 처리"""
        while True:
            try:
                entry = await self._log_queue.get()
                if entry is None:  # 종료 신호
                    break
                
                await self._write_log_entry(entry)
                self._log_queue.task_done()
                
            except Exception as e:
                # 로깅 시스템의 에러는 표준 에러로 출력
                print(f"Log processing error: {e}", file=sys.stderr)
    
    async def _write_log_entry(self, entry: LogEntry) -> None:
        """로그 엔트리 쓰기"""
        # 필터 적용
        for filter_func in self._filters:
            if not filter_func(entry):
                return
        
        # 사용자 정의 핸들러 실행
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                print(f"Log handler error: {e}", file=sys.stderr)
        
        # 표준 로거로 출력
        log_level = getattr(logging, entry.level.value)
        record = self._logger.makeRecord(
            self.name, log_level, entry.module or "", entry.line_number or 0,
            entry.message, (), None
        )
        record._log_entry = entry  # 커스텀 포매터에서 사용
        self._logger.handle(record)
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        error: Optional[Exception] = None,
        **kwargs
    ) -> None:
        """내부 로그 메서드"""
        if level.value < self.level.value:  # 레벨 체크는 단순 문자열 비교
            return
        
        entry = self._create_log_entry(level, message, data, tags, error, **kwargs)
        
        if self.enable_async and self._log_queue:
            # 비동기 로깅
            try:
                self._log_queue.put_nowait(entry)
            except asyncio.QueueFull:
                # 큐가 가득 찬 경우 동기 로깅으로 폴백
                self._sync_log_entry(entry)
        else:
            # 동기 로깅
            self._sync_log_entry(entry)
    
    def _sync_log_entry(self, entry: LogEntry) -> None:
        """동기식 로그 엔트리 처리"""
        # 필터 적용
        for filter_func in self._filters:
            if not filter_func(entry):
                return
        
        # 사용자 정의 핸들러 실행
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                print(f"Log handler error: {e}", file=sys.stderr)
        
        # 표준 로거로 출력
        log_level = getattr(logging, entry.level.value)
        record = self._logger.makeRecord(
            self.name, log_level, entry.module or "", entry.line_number or 0,
            entry.message, (), None
        )
        record._log_entry = entry  # 커스텀 포매터에서 사용
        self._logger.handle(record)
    
    def log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[LogContext] = None,
        **kwargs
    ) -> None:
        """공개 로그 메서드"""
        # 지연 초기화 시도 (이벤트 루프가 없어도 동작)
        if self.enable_async and not self._async_initialized:
            try:
                # 이벤트 루프가 실행 중인 경우만 초기화
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    self._log_queue = asyncio.Queue()
                    self._log_processor_task = asyncio.create_task(self._process_logs())
                    self._async_initialized = True
            except RuntimeError:
                # 이벤트 루프가 없는 경우 동기 모드로 폴백
                self.enable_async = False
        
        # 컨텍스트에서 데이터 추출
        data = kwargs
        tags = None
        error = kwargs.pop('exception', None)
        
        if context:
            data.update(context.extra_data)
            tags = context.tags
            if context.exception and not error:
                error = context.exception
        
        self._log(level, message, data, tags, error)
    
    def debug(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        """디버그 로그"""
        self._log(LogLevel.DEBUG, message, data, tags, **kwargs)
    
    def info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        """정보 로그"""
        self._log(LogLevel.INFO, message, data, tags, **kwargs)
    
    def warning(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        """경고 로그"""
        self._log(LogLevel.WARNING, message, data, tags, **kwargs)
    
    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        """에러 로그"""
        self._log(LogLevel.ERROR, message, data, tags, error, **kwargs)
    
    def critical(
        self,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        """치명적 에러 로그"""
        self._log(LogLevel.CRITICAL, message, data, tags, error, **kwargs)
    
    def add_filter(self, filter_func: Callable[[LogEntry], bool]) -> None:
        """필터 추가"""
        self._filters.append(filter_func)
    
    def add_handler(self, handler_func: Callable[[LogEntry], None]) -> None:
        """핸들러 추가"""
        self._handlers.append(handler_func)
    
    async def close(self) -> None:
        """로거 종료"""
        if self._log_queue:
            # 처리 대기 중인 로그 완료
            await self._log_queue.join()
            
            # 종료 신호
            await self._log_queue.put(None)
            
            # 프로세서 태스크 종료
            if self._log_processor_task:
                await self._log_processor_task


# 전역 로거 레지스트리
_loggers: Dict[str, EnhancedLogger] = {}
_default_logger: Optional[EnhancedLogger] = None


def get_logger(
    name: Optional[str] = None,
    level: LogLevel = LogLevel.INFO,
    **kwargs
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
        config = get_config()
        log_level = getattr(config, 'log_level', 'INFO')
        _default_logger = get_logger("rfs", LogLevel(log_level))
    return _default_logger


def set_log_context(context: LogContext) -> None:
    """로그 컨텍스트 설정"""
    _log_context.set(context)


def get_log_context() -> Optional[LogContext]:
    """로그 컨텍스트 조회"""
    return _log_context.get()


def clear_log_context() -> None:
    """로그 컨텍스트 제거"""
    _log_context.set(None)


# 편의 함수들
def log_info(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs
) -> None:
    """정보 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.info(message, data, tags, **kwargs)


def log_warning(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs
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
    **kwargs
) -> None:
    """에러 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.error(message, error, data, tags, **kwargs)


def log_debug(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    logger_name: Optional[str] = None,
    **kwargs
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
    **kwargs
) -> None:
    """치명적 에러 로그 (편의 함수)"""
    logger = get_logger(logger_name) if logger_name else get_default_logger()
    logger.critical(message, error, data, tags, **kwargs)


# 데코레이터
def log_execution(
    level: LogLevel = LogLevel.INFO,
    include_args: bool = False,
    include_result: bool = False,
    logger_name: Optional[str] = None
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
                log_data["args"] = str(args)
                log_data["kwargs"] = str(kwargs)
            
            logger._log(level, f"Function started: {func_name}", log_data)
            
            try:
                result = await func(*args, **kwargs)
                
                execution_time = (time.time() - start_time) * 1000
                success_data = {
                    "function": func_name,
                    "success": True,
                    "execution_time_ms": execution_time
                }
                
                if include_result:
                    success_data["result"] = str(result)
                
                logger._log(level, f"Function completed: {func_name}", success_data)
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                error_data = {
                    "function": func_name,
                    "success": False,
                    "execution_time_ms": execution_time
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
                log_data["args"] = str(args)
                log_data["kwargs"] = str(kwargs)
            
            logger._log(level, f"Function started: {func_name}", log_data)
            
            try:
                result = func(*args, **kwargs)
                
                execution_time = (time.time() - start_time) * 1000
                success_data = {
                    "function": func_name,
                    "success": True,
                    "execution_time_ms": execution_time
                }
                
                if include_result:
                    success_data["result"] = str(result)
                
                logger._log(level, f"Function completed: {func_name}", success_data)
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                error_data = {
                    "function": func_name,
                    "success": False,
                    "execution_time_ms": execution_time
                }
                
                logger.error(f"Function failed: {func_name}", e, error_data)
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# 컨텍스트 매니저
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