"""
RFS v4.1 Logging Decorators
고급 로깅 어노테이션 구현

주요 기능:
- @LoggedOperation: 작업 레벨 로깅
- @AuditLogged: 감사 로그 생성
- @ErrorLogged: 에러 자동 로깅
- @PerformanceLogged: 성능 메트릭 로깅
"""

import asyncio
import functools
import inspect
import json
import logging
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from .result import Failure, Result, Success

logger = logging.getLogger(__name__)
T = TypeVar("T")


class LogLevel(Enum):
    """로그 레벨"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditEventType(Enum):
    """감사 이벤트 타입"""

    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    SECURITY_EVENT = "SECURITY_EVENT"
    DATA_ACCESS = "DATA_ACCESS"
    API_CALL = "API_CALL"


@dataclass
class OperationContext:
    """작업 컨텍스트"""

    operation_id: str
    operation_name: str
    start_time: datetime
    end_time = None
    duration_ms = None
    user_id = None
    session_id = None
    trace_id = None
    span_id = None
    parent_span_id = None
    tags: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data["start_time"] = {"start_time": self.start_time.isoformat()}
        if self.end_time:
            data["end_time"] = {"end_time": self.end_time.isoformat()}
        return data


@dataclass
class AuditLogEntry:
    """감사 로그 엔트리"""

    audit_id: str
    timestamp: datetime
    event_type: AuditEventType
    user_id: Optional[str]
    resource_type: str
    resource_id: Optional[str]
    action: str
    result: str
    ip_address = None
    user_agent = None
    session_id = None
    changes: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message = None

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        data = asdict(self)
        data["timestamp"] = {"timestamp": self.timestamp.isoformat()}
        data["event_type"] = {"event_type": self.event_type.value}
        return json.dumps(data, default=str)


class AuditLogger:
    """감사 로거"""

    def __init__(self, log_file=None):
        self.log_file = log_file
        self.audit_logs = []
        self.logger = logging.getLogger("audit")
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            self.logger.addHandler(file_handler)

    def log(self, entry: AuditLogEntry) -> None:
        """감사 로그 기록"""
        self.audit_logs = self.audit_logs + [entry]
        self.logger.info(entry.to_json())
        if self.log_file:
            try:
                with open(self.log_file, "a") as f:
                    f.write(entry.to_json() + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log to file: {e}")

    def get_logs(
        self,
        user_id=None,
        event_type=None,
        start_time=None,
        end_time=None,
        limit=100,
    ) -> List[AuditLogEntry]:
        """감사 로그 조회"""
        logs = self.audit_logs
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        if event_type:
            logs = [l for l in logs if l.event_type == event_type]
        if start_time:
            logs = [l for l in logs if l.timestamp >= start_time]
        if end_time:
            logs = [l for l in logs if l.timestamp <= end_time]
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs[:limit]


_audit_logger = AuditLogger()


def LoggedOperation(
    level: LogLevel = LogLevel.INFO,
    include_args=True,
    include_result=False,
    include_timing=True,
    include_errors=True,
    tags: Optional[Dict[str, Any]] = None,
):
    """
    작업 레벨 로깅 데코레이터

    Args:
        level: 로그 레벨
        include_args: 인자 포함 여부
        include_result: 결과 포함 여부
        include_timing: 실행 시간 포함 여부
        include_errors: 에러 포함 여부
        tags: 추가 태그
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            operation_id = str(uuid.uuid4())[:8]
            operation_name = f"{func.__module__}.{func.__name__}"
            context = OperationContext(
                operation_id=operation_id,
                operation_name=operation_name,
                start_time=datetime.now(),
                tags=tags or {},
            )
            log_func = getattr(logger, level.value.lower(), logger.info)
            log_message = f"[{operation_id}] Starting operation: {operation_name}"
            if include_args:
                safe_args = _mask_sensitive_data(args)
                safe_kwargs = _mask_sensitive_data(kwargs)
                log_message = (
                    log_message + f" | Args: {safe_args} | Kwargs: {safe_kwargs}"
                )
            log_func(log_message)
            try:
                start_time = time.time()
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                context.end_time = datetime.now()
                context.duration_ms = execution_time
                log_message = f"[{operation_id}] Completed operation: {operation_name}"
                if include_timing:
                    log_message = log_message + f" | Duration: {execution_time:.2f}ms"
                if include_result:
                    safe_result = _mask_sensitive_data(result)
                    log_message = log_message + f" | Result: {safe_result}"
                log_func(log_message)
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                context.end_time = datetime.now()
                context.duration_ms = execution_time
                if include_errors:
                    error_id = str(uuid.uuid4())[:8]
                    logger.error(
                        f"[{operation_id}] Operation failed: {operation_name} | Error ID: {error_id} | Error: {str(e)} | Duration: {execution_time:.2f}ms"
                    )
                    logger.debug(f"[{error_id}] Stack trace:\n{traceback.format_exc()}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            operation_id = str(uuid.uuid4())[:8]
            operation_name = f"{func.__module__}.{func.__name__}"
            context = OperationContext(
                operation_id=operation_id,
                operation_name=operation_name,
                start_time=datetime.now(),
                tags=tags or {},
            )
            log_func = getattr(logger, level.value.lower(), logger.info)
            log_message = f"[{operation_id}] Starting operation: {operation_name}"
            if include_args:
                safe_args = _mask_sensitive_data(args)
                safe_kwargs = _mask_sensitive_data(kwargs)
                log_message = (
                    log_message + f" | Args: {safe_args} | Kwargs: {safe_kwargs}"
                )
            log_func(log_message)
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                context.end_time = datetime.now()
                context.duration_ms = execution_time
                log_message = f"[{operation_id}] Completed operation: {operation_name}"
                if include_timing:
                    log_message = log_message + f" | Duration: {execution_time:.2f}ms"
                if include_result:
                    safe_result = _mask_sensitive_data(result)
                    log_message = log_message + f" | Result: {safe_result}"
                log_func(log_message)
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                context.end_time = datetime.now()
                context.duration_ms = execution_time
                if include_errors:
                    error_id = str(uuid.uuid4())[:8]
                    logger.error(
                        f"[{operation_id}] Operation failed: {operation_name} | Error ID: {error_id} | Error: {str(e)} | Duration: {execution_time:.2f}ms"
                    )
                    logger.debug(f"[{error_id}] Stack trace:\n{traceback.format_exc()}")
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def AuditLogged(
    event_type: AuditEventType,
    resource_type: str,
    include_changes=True,
    include_user_info=True,
    custom_message=None,
):
    """
    감사 로그 데코레이터

    Args:
        event_type: 이벤트 타입
        resource_type: 리소스 타입
        include_changes: 변경사항 포함 여부
        include_user_info: 사용자 정보 포함 여부
        custom_message: 커스텀 메시지
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            audit_id = str(uuid.uuid4())
            user_id = None
            session_id = None
            if include_user_info:
                user_id = kwargs.get("user_id") or getattr(
                    args[0] if args else None, "user_id", None
                )
                session_id = kwargs.get("session_id")
            resource_id = kwargs.get("id") or kwargs.get("resource_id")
            before_state = None
            if event_type == AuditEventType.UPDATE and include_changes:
                before_state = {}
            try:
                result = await func(*args, **kwargs)
                changes = None
                if include_changes and before_state is not None:
                    changes = {"updated_fields": []}
                entry = AuditLogEntry(
                    audit_id=audit_id,
                    timestamp=datetime.now(),
                    event_type=event_type,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    action=func.__name__,
                    result="SUCCESS",
                    session_id=session_id,
                    changes=changes,
                    metadata={
                        "function": f"{func.__module__}.{func.__name__}",
                        "custom_message": custom_message,
                    },
                )
                _audit_logger.log(entry)
                return result
            except Exception as e:
                entry = AuditLogEntry(
                    audit_id=audit_id,
                    timestamp=datetime.now(),
                    event_type=event_type,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    action=func.__name__,
                    result="FAILURE",
                    session_id=session_id,
                    error_message=str(e),
                    metadata={
                        "function": f"{func.__module__}.{func.__name__}",
                        "custom_message": custom_message,
                    },
                )
                _audit_logger.log(entry)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            audit_id = str(uuid.uuid4())
            user_id = None
            session_id = None
            if include_user_info:
                user_id = kwargs.get("user_id") or getattr(
                    args[0] if args else None, "user_id", None
                )
                session_id = kwargs.get("session_id")
            resource_id = kwargs.get("id") or kwargs.get("resource_id")
            before_state = None
            if event_type == AuditEventType.UPDATE and include_changes:
                before_state = {}
            try:
                result = func(*args, **kwargs)
                changes = None
                if include_changes and before_state is not None:
                    changes = {"updated_fields": []}
                entry = AuditLogEntry(
                    audit_id=audit_id,
                    timestamp=datetime.now(),
                    event_type=event_type,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    action=func.__name__,
                    result="SUCCESS",
                    session_id=session_id,
                    changes=changes,
                    metadata={
                        "function": f"{func.__module__}.{func.__name__}",
                        "custom_message": custom_message,
                    },
                )
                _audit_logger.log(entry)
                return result
            except Exception as e:
                entry = AuditLogEntry(
                    audit_id=audit_id,
                    timestamp=datetime.now(),
                    event_type=event_type,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    action=func.__name__,
                    result="FAILURE",
                    session_id=session_id,
                    error_message=str(e),
                    metadata={
                        "function": f"{func.__module__}.{func.__name__}",
                        "custom_message": custom_message,
                    },
                )
                _audit_logger.log(entry)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def ErrorLogged(
    include_stack_trace=True,
    notify=False,
    severity: LogLevel = LogLevel.ERROR,
):
    """
    에러 자동 로깅 데코레이터

    Args:
        include_stack_trace: 스택 트레이스 포함 여부
        notify: 알림 전송 여부
        severity: 에러 심각도
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_id = str(uuid.uuid4())
                log_func = getattr(logger, severity.value.lower(), logger.error)
                error_message = f"Error ID: {error_id} | Function: {func.__module__}.{func.__name__} | Error: {str(e)}"
                log_func(error_message)
                if include_stack_trace:
                    logger.debug(f"[{error_id}] Stack trace:\n{traceback.format_exc()}")
                if notify:
                    logger.critical(f"NOTIFICATION REQUIRED: {error_message}")
                return Failure(str(e))

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_id = str(uuid.uuid4())
                log_func = getattr(logger, severity.value.lower(), logger.error)
                error_message = f"Error ID: {error_id} | Function: {func.__module__}.{func.__name__} | Error: {str(e)}"
                log_func(error_message)
                if include_stack_trace:
                    logger.debug(f"[{error_id}] Stack trace:\n{traceback.format_exc()}")
                if notify:
                    logger.critical(f"NOTIFICATION REQUIRED: {error_message}")
                return Failure(str(e))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _mask_sensitive_data(data: Any) -> Any:
    """민감한 데이터 마스킹"""
    if type(data).__name__ == "dict":
        masked = {}
        sensitive_keys = [
            "password",
            "token",
            "secret",
            "api_key",
            "private_key",
            "ssn",
        ]
        for key, value in data.items():
            if any((sensitive in key.lower() for sensitive in sensitive_keys)):
                masked[key] = {key: "***MASKED***"}
            else:
                masked[key] = {key: _mask_sensitive_data(value)}
        return masked
    elif type(data).__name__ in ["list", "tuple"]:
        return [_mask_sensitive_data(item) for item in data]
    elif type(data).__name__ == "str":
        if "@" in data and "." in data:
            parts = data.split("@")
            if len(parts) == 2:
                username = parts[0]
                if len(username) > 2:
                    return f"{username[:2]}***@{parts[1]}"
        return data
    else:
        return data


def get_audit_logger() -> AuditLogger:
    """글로벌 감사 로거 반환"""
    return _audit_logger


def set_audit_log_file(file_path: str) -> None:
    """감사 로그 파일 설정"""
    # global _audit_logger - removed for functional programming
    _audit_logger = AuditLogger(log_file=file_path)
