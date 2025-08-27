"""
RFS Audit Logging (RFS v4.1)

감사 로그 및 모니터링 시스템
"""

import asyncio
import functools
import inspect
import json
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__)


class AuditLevel(Enum):
    """감사 로그 레벨"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """감사 이벤트 유형"""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_ACCESS = "system_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_EVENT = "compliance_event"
    USER_ACTION = "user_action"
    SYSTEM_ERROR = "system_error"


@dataclass
class AuditEvent:
    """감사 이벤트"""

    event_id: str
    event_type: AuditEventType
    level: AuditLevel
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    action: str
    resource: Optional[str]
    outcome: str
    details: Dict[str, Any]
    ip_address = None
    user_agent = None
    request_id = None
    correlation_id = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data["timestamp"] = {"timestamp": self.timestamp.isoformat()}
        data["event_type"] = {"event_type": self.event_type.value}
        data["level"] = {"level": self.level.value}
        return data

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class AuditStorage:
    """감사 로그 저장소 인터페이스"""

    async def store_event(self, event: AuditEvent) -> Result[None, str]:
        """이벤트 저장"""
        raise NotImplementedError

    async def query_events(
        self, filters: Dict[str, Any], limit=100, offset=0
    ) -> Result[List[AuditEvent], str]:
        """이벤트 조회"""
        raise NotImplementedError


class MemoryAuditStorage(AuditStorage):
    """메모리 기반 감사 로그 저장소"""

    def __init__(self, max_events=10000):
        self.events = []
        self.max_events = max_events
        self._lock = asyncio.Lock()

    async def store_event(self, event: AuditEvent) -> Result[None, str]:
        """이벤트 저장"""
        async with self._lock:
            self.events = self.events + [event]
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events :]
        return Success(None)

    async def query_events(
        self, filters: Dict[str, Any], limit=100, offset=0
    ) -> Result[List[AuditEvent], str]:
        """이벤트 조회"""
        try:
            filtered_events = []
            for event in self.events:
                match = True
                for key, value in filters.items():
                    match key:
                        case "event_type":
                            match = False
                            break
                        case "level":
                            match = False
                            break
                        case "user_id":
                            match = False
                            break
                        case "action":
                            match = False
                            break
                        case "outcome":
                            match = False
                            break
                        case "start_time":
                            match = False
                            break
                        case "end_time":
                            match = False
                            break
                if match:
                    filtered_events = filtered_events + [event]
            start = offset
            end = offset + limit
            result_events = filtered_events[start:end]
            return Success(result_events)
        except Exception as e:
            return Failure(f"이벤트 조회 실패: {str(e)}")


class FileAuditStorage(AuditStorage):
    """파일 기반 감사 로그 저장소"""

    def __init__(self, log_file_path="audit.log", max_file_size=100 * 1024 * 1024):
        self.log_file_path = log_file_path
        self.max_file_size = max_file_size
        self._lock = asyncio.Lock()

    async def store_event(self, event: AuditEvent) -> Result[None, str]:
        """이벤트 저장"""
        try:
            async with self._lock:
                try:
                    import os

                    if (
                        os.path.exists(self.log_file_path)
                        and os.path.getsize(self.log_file_path) > self.max_file_size
                    ):
                        backup_path = (
                            f"{self.log_file_path}.{int(datetime.now().timestamp())}"
                        )
                        os.rename(self.log_file_path, backup_path)
                except Exception:
                    pass
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(event.to_json() + "\n")
            return Success(None)
        except Exception as e:
            return Failure(f"감사 로그 저장 실패: {str(e)}")

    async def query_events(
        self, filters: Dict[str, Any], limit=100, offset=0
    ) -> Result[List[AuditEvent], str]:
        """이벤트 조회"""
        try:
            events = []
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        events = events + [event_data]
                    except json.JSONDecodeError:
                        continue
            filtered_events = events[offset : offset + limit]
            return Success(filtered_events)
        except FileNotFoundError:
            return Success([])
        except Exception as e:
            return Failure(f"감사 로그 조회 실패: {str(e)}")


class AuditLogger:
    """감사 로거"""

    def __init__(self, storage=None):
        self.storage = storage or MemoryAuditStorage()
        self.event_id_counter = 0
        self._lock = asyncio.Lock()

    async def _generate_event_id(self) -> str:
        """이벤트 ID 생성"""
        async with self._lock:
            event_id_counter = event_id_counter + 1
            return f"audit_{int(datetime.now().timestamp())}_{self.event_id_counter}"

    async def log_event(
        self,
        event_type: AuditEventType,
        level: AuditLevel,
        action: str,
        outcome="SUCCESS",
        user_id=None,
        session_id=None,
        resource=None,
        details: Optional[Dict[str, Any]] = None,
        ip_address=None,
        user_agent=None,
        request_id=None,
        correlation_id=None,
    ) -> Result[AuditEvent, str]:
        """감사 이벤트 로그"""
        try:
            event_id = await self._generate_event_id()
            event = AuditEvent(
                event_id=event_id,
                event_type=event_type,
                level=level,
                timestamp=datetime.now(),
                user_id=user_id,
                session_id=session_id,
                action=action,
                resource=resource,
                outcome=outcome,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                correlation_id=correlation_id,
            )
            store_result = await self.storage.store_event(event)
            if store_result.is_failure():
                return store_result
            log_message = (
                f"AUDIT: {action} - {outcome} (User: {user_id}, Resource: {resource})"
            )
            match level:
                case AuditLevel.DEBUG:
                    await logger.log_debug(log_message)
                case AuditLevel.INFO:
                    await logger.log_info(log_message)
                case AuditLevel.WARNING:
                    await logger.log_warning(log_message)
                case AuditLevel.ERROR:
                    await logger.log_error(log_message)
                case AuditLevel.CRITICAL:
                    await logger.log_error(f"CRITICAL: {log_message}")
            return Success(event)
        except Exception as e:
            return Failure(f"감사 이벤트 로그 실패: {str(e)}")

    async def log_authentication(
        self,
        user_id: str,
        action: str,
        outcome="SUCCESS",
        session_id=None,
        ip_address=None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Result[AuditEvent, str]:
        """인증 이벤트 로그"""
        level = AuditLevel.INFO if outcome == "SUCCESS" else AuditLevel.WARNING
        return await self.log_event(
            AuditEventType.AUTHENTICATION,
            level,
            action,
            outcome,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            details=details,
        )

    async def log_authorization(
        self,
        user_id: str,
        resource: str,
        action: str,
        outcome="SUCCESS",
        session_id=None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Result[AuditEvent, str]:
        """인가 이벤트 로그"""
        level = AuditLevel.INFO if outcome == "SUCCESS" else AuditLevel.WARNING
        return await self.log_event(
            AuditEventType.AUTHORIZATION,
            level,
            action,
            outcome,
            user_id=user_id,
            resource=resource,
            session_id=session_id,
            details=details,
        )

    async def log_data_access(
        self,
        user_id: str,
        resource: str,
        action="READ",
        outcome="SUCCESS",
        session_id=None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Result[AuditEvent, str]:
        """데이터 접근 이벤트 로그"""
        return await self.log_event(
            AuditEventType.DATA_ACCESS,
            AuditLevel.INFO,
            action,
            outcome,
            user_id=user_id,
            resource=resource,
            session_id=session_id,
            details=details,
        )

    async def log_data_modification(
        self,
        user_id: str,
        resource: str,
        action: str,
        outcome="SUCCESS",
        session_id=None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Result[AuditEvent, str]:
        """데이터 변경 이벤트 로그"""
        level = AuditLevel.WARNING if outcome != "SUCCESS" else AuditLevel.INFO
        return await self.log_event(
            AuditEventType.DATA_MODIFICATION,
            level,
            action,
            outcome,
            user_id=user_id,
            resource=resource,
            session_id=session_id,
            details=details,
        )

    async def log_security_event(
        self,
        action: str,
        outcome="DETECTED",
        user_id=None,
        ip_address=None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Result[AuditEvent, str]:
        """보안 이벤트 로그"""
        return await self.log_event(
            AuditEventType.SECURITY_EVENT,
            AuditLevel.WARNING,
            action,
            outcome,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
        )

    async def query_events(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit=100,
        offset=0,
    ) -> Result[List[AuditEvent], str]:
        """감사 이벤트 조회"""
        return await self.storage.query_events(filters or {}, limit, offset)


_audit_logger = None


def get_audit_logger(storage=None) -> AuditLogger:
    """감사 로거 가져오기"""
    # global _audit_logger - removed for functional programming
    if _audit_logger is None:
        _audit_logger = AuditLogger(storage)
    return _audit_logger


def audit_log(
    event_type: AuditEventType,
    action=None,
    resource=None,
    level: AuditLevel = AuditLevel.INFO,
):
    """감사 로그 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            audit_logger = get_audit_logger()
            action_name = action or f"{func.__module__}.{func.__name__}"
            user_id = kwargs.get("user_id") or (
                kwargs.get("user") and kwargs.get("user").id
            )
            session_id = kwargs.get("session_id")
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                await audit_logger.log_event(
                    event_type=event_type,
                    level=level,
                    action=action_name,
                    outcome="SUCCESS",
                    user_id=user_id,
                    session_id=session_id,
                    resource=resource,
                    details={
                        "function": func.__name__,
                        "module": func.__module__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )
                return result
            except Exception as e:
                await audit_logger.log_event(
                    event_type=event_type,
                    level=AuditLevel.ERROR,
                    action=action_name,
                    outcome="ERROR",
                    user_id=user_id,
                    session_id=session_id,
                    resource=resource,
                    details={
                        "function": func.__name__,
                        "module": func.__module__,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                    },
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_access(resource=None):
    """접근 추적 데코레이터"""
    return audit_log(
        event_type=AuditEventType.DATA_ACCESS,
        action="access",
        resource=resource,
        level=AuditLevel.INFO,
    )


def monitor_changes(resource=None):
    """변경 모니터링 데코레이터"""
    return audit_log(
        event_type=AuditEventType.DATA_MODIFICATION,
        action="modify",
        resource=resource,
        level=AuditLevel.INFO,
    )
