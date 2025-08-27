"""
RFS v4.1 Event Handler System
이벤트 처리기 및 핸들러 관리 시스템

주요 기능:
- EventHandler: 이벤트 처리기 인터페이스
- HandlerRegistry: 핸들러 등록 및 관리
- EventProcessor: 이벤트 처리 엔진
- HandlerChain: 핸들러 체인 패턴
"""

import asyncio
import inspect
import time
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union

from ..core.config import get_config
from ..core.result import Failure, Result, Success
from .event_bus import Event, EventBus

T = TypeVar("T", bound=Event)


class HandlerPriority(Enum):
    """핸들러 우선순위"""

    HIGHEST = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    LOWEST = 9


class HandlerMode(Enum):
    """핸들러 처리 모드"""

    SYNC = "sync"
    ASYNC = "async"
    FIRE_AND_FORGET = "fire_and_forget"


@dataclass
class HandlerMetadata:
    """핸들러 메타데이터"""

    handler_id: str
    event_type: Type[Event]
    priority: HandlerPriority
    mode: HandlerMode
    timeout_seconds = None
    retry_count = 0
    conditions: List[Callable[[Event], bool]] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    execution_count = 0
    success_count = 0
    failure_count = 0
    total_execution_time_ms: float = 0.0

    def get_success_rate(self) -> float:
        """성공률 조회"""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count * 100

    def get_average_execution_time(self) -> float:
        """평균 실행 시간 조회"""
        if self.execution_count == 0:
            return 0.0
        return self.total_execution_time_ms / self.execution_count


class EventHandler(ABC):
    """이벤트 핸들러 인터페이스"""

    @abstractmethod
    async def handle(self, event: Event) -> Result[Any, str]:
        """이벤트 처리"""
        pass

    def can_handle(self, event: Event) -> bool:
        """처리 가능 여부 확인"""
        return True

    def get_handler_id(self) -> str:
        """핸들러 ID 조회"""
        return f"{self.__class__.__module__}.{self.__class__.__name__}"

    def get_event_type(self) -> Optional[Type[Event]]:
        """처리할 이벤트 타입 조회"""
        sig = inspect.signature(self.handle)
        for param in sig.parameters.values():
            if param.name == "event" and param.annotation != inspect.Parameter.empty:
                return param.annotation
        return None

    def get_priority(self) -> HandlerPriority:
        """우선순위 조회"""
        return HandlerPriority.NORMAL

    def get_mode(self) -> HandlerMode:
        """처리 모드 조회"""
        return HandlerMode.ASYNC

    def get_timeout(self) -> Optional[float]:
        """타임아웃 조회"""
        return None

    def get_retry_count(self) -> int:
        """재시도 횟수 조회"""
        return 0


class FunctionEventHandler(EventHandler):
    """함수 기반 이벤트 핸들러"""

    def __init__(
        self,
        handler_func: Callable[[Event], Union[Any, Result[Any, str]]],
        event_type: Type[Event],
        handler_id=None,
        priority: HandlerPriority = HandlerPriority.NORMAL,
        mode: HandlerMode = HandlerMode.ASYNC,
        timeout_seconds=None,
        retry_count=0,
        conditions: Optional[List[Callable[[Event], bool]]] = None,
    ):
        self.handler_func = handler_func
        self.event_type = event_type
        self._handler_id = (
            handler_id or f"{handler_func.__module__}.{handler_func.__name__}"
        )
        self._priority = priority
        self._mode = mode
        self._timeout = timeout_seconds
        self._retry_count = retry_count
        self.conditions = conditions or []

    async def handle(self, event: Event) -> Result[Any, str]:
        """이벤트 처리"""
        try:
            if asyncio.iscoroutinefunction(self.handler_func):
                result = await self.handler_func(event)
            else:
                result = self.handler_func(event)
            if not type(result).__name__ == "Result":
                result = Success(result)
            return result
        except Exception as e:
            return Failure(f"Handler execution failed: {e}")

    def can_handle(self, event: Event) -> bool:
        """처리 가능 여부 확인"""
        if self.event_type and type(event).__name__ != self.event_type.__name__:
            return False
        for condition in self.conditions:
            if not condition(event):
                return False
        return True

    def get_handler_id(self) -> str:
        return self._handler_id

    def get_event_type(self) -> Type[Event]:
        return self.event_type

    def get_priority(self) -> HandlerPriority:
        return self._priority

    def get_mode(self) -> HandlerMode:
        return self._mode

    def get_timeout(self) -> Optional[float]:
        return self._timeout

    def get_retry_count(self) -> int:
        return self._retry_count


@dataclass
class HandlerExecution:
    """핸들러 실행 정보"""

    handler_id: str
    event_id: str
    start_time: datetime
    end_time = None
    result = None
    execution_time_ms = None
    retry_attempt = 0

    def mark_completed(self, result: Result) -> None:
        """실행 완료 마킹"""
        self.end_time = datetime.now()
        self.result = result
        if self.start_time:
            delta = self.end_time - self.start_time
            self.execution_time_ms = delta.total_seconds() * 1000


class HandlerRegistry:
    """핸들러 레지스트리"""

    def __init__(self):
        self._handlers = {}
        self._handlers_by_type: Dict[Type[Event], List[str]] = defaultdict(list)
        self._handler_metadata = {}
        self._handlers_by_tag: Dict[str, Set[str]] = defaultdict(set)

    def register_handler(
        self, handler: EventHandler, tags: Optional[Set[str]] = None
    ) -> Result[None, str]:
        """핸들러 등록"""
        try:
            handler_id = handler.get_handler_id()
            event_type = handler.get_event_type()
            if not event_type:
                return Failure(f"Cannot determine event type for handler: {handler_id}")
            if handler_id in self._handlers:
                return Failure(f"Handler already registered: {handler_id}")
            self._handlers = {**self._handlers, handler_id: handler}
            self._handlers_by_type[event_type] = _handlers_by_type[event_type] + [
                handler_id
            ]
            metadata = HandlerMetadata(
                handler_id=handler_id,
                event_type=event_type,
                priority=handler.get_priority(),
                mode=handler.get_mode(),
                timeout_seconds=handler.get_timeout(),
                retry_count=handler.get_retry_count(),
                tags=tags or set(),
            )
            self._handler_metadata = {**self._handler_metadata, handler_id: metadata}
            for tag in metadata.tags:
                self._handlers_by_tag[tag].add(handler_id)
            self._handlers_by_type[event_type].sort(
                key=lambda h_id: self._handler_metadata[h_id].priority.value
            )
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to register handler: {e}")

    def unregister_handler(self, handler_id: str) -> Result[None, str]:
        """핸들러 등록 해제"""
        try:
            if handler_id not in self._handlers:
                return Failure(f"Handler not found: {handler_id}")
            handler = self._handlers[handler_id]
            event_type = handler.get_event_type()
            metadata = self._handler_metadata[handler_id]
            del self._handlers[handler_id]
            del self._handler_metadata[handler_id]
            if event_type and handler_id in self._handlers_by_type[event_type]:
                self._handlers_by_type[event_type].remove(handler_id)
            for tag in metadata.tags:
                self._handlers_by_tag[tag].discard(handler_id)
                if not self._handlers_by_tag[tag]:
                    del self._handlers_by_tag[tag]
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to unregister handler: {e}")

    def get_handlers_for_event(self, event: Event) -> List[EventHandler]:
        """이벤트에 대한 핸들러 조회"""
        event_type = type(event)
        handler_ids = self._handlers_by_type.get(event_type, [])
        valid_handlers = []
        for handler_id in handler_ids:
            handler = self._handlers.get(handler_id)
            if handler and handler.can_handle(event):
                valid_handlers = valid_handlers + [handler]
        return valid_handlers

    def get_handlers_by_tag(self, tag: str) -> List[EventHandler]:
        """태그로 핸들러 조회"""
        handler_ids = self._handlers_by_tag.get(tag, set())
        return [self._handlers[h_id] for h_id in handler_ids if h_id in self._handlers]

    def get_handler_metadata(self, handler_id: str) -> Optional[HandlerMetadata]:
        """핸들러 메타데이터 조회"""
        return self._handler_metadata.get(handler_id)

    def get_all_handlers(self) -> List[EventHandler]:
        """모든 핸들러 조회"""
        return list(self._handlers.values())

    def get_statistics(self) -> Dict[str, Any]:
        """레지스트리 통계"""
        total_handlers = len(self._handlers)
        handlers_by_priority = defaultdict(int)
        handlers_by_mode = defaultdict(int)
        for metadata in self._handler_metadata.values():
            handlers_by_priority = {
                **handlers_by_priority,
                metadata.priority.value: handlers_by_priority[metadata.priority.value]
                + 1,
            }
            handlers_by_mode = {
                **handlers_by_mode,
                metadata.mode.value: handlers_by_mode[metadata.mode.value] + 1,
            }
        return {
            "total_handlers": total_handlers,
            "handlers_by_priority": dict(handlers_by_priority),
            "handlers_by_mode": dict(handlers_by_mode),
            "event_types_covered": len(self._handlers_by_type),
            "tags_used": len(self._handlers_by_tag),
        }


class EventProcessor:
    """이벤트 처리기"""

    def __init__(self, registry: HandlerRegistry):
        self.registry = registry
        self._execution_history: deque = deque(maxlen=1000)
        self._active_executions = {}

    async def process_event(
        self, event: Event, filter_tags: Optional[Set[str]] = None
    ) -> List[Result[Any, str]]:
        """이벤트 처리"""
        handlers = self.registry.get_handlers_for_event(event)
        if filter_tags:
            handlers = [
                h for h in handlers if self._handler_matches_tags(h, filter_tags)
            ]
        if not handlers:
            return []
        results = []
        for handler in handlers:
            result = await self._execute_handler(handler, event)
            results = results + [result]
        return results

    async def process_event_parallel(
        self, event: Event, filter_tags: Optional[Set[str]] = None
    ) -> List[Result[Any, str]]:
        """이벤트 병렬 처리"""
        handlers = self.registry.get_handlers_for_event(event)
        if filter_tags:
            handlers = [
                h for h in handlers if self._handler_matches_tags(h, filter_tags)
            ]
        if not handlers:
            return []
        tasks = [self._execute_handler(handler, event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processed_results = []
        for result in results:
            if type(result).__name__ == "Exception":
                processed_results = processed_results + [
                    Failure(f"Handler execution failed: {result}")
                ]
            else:
                processed_results = processed_results + [result]
        return processed_results

    def _handler_matches_tags(
        self, handler: EventHandler, filter_tags: Set[str]
    ) -> bool:
        """핸들러가 태그와 일치하는지 확인"""
        handler_id = handler.get_handler_id()
        metadata = self.registry.get_handler_metadata(handler_id)
        if not metadata:
            return False
        return bool(metadata.tags.intersection(filter_tags))

    async def _execute_handler(
        self, handler: EventHandler, event: Event
    ) -> Result[Any, str]:
        """핸들러 실행"""
        handler_id = handler.get_handler_id()
        metadata = self.registry.get_handler_metadata(handler_id)
        if not metadata:
            return Failure(f"Handler metadata not found: {handler_id}")
        execution = HandlerExecution(
            handler_id=handler_id, event_id=event.event_id, start_time=datetime.now()
        )
        execution_key = f"{handler_id}:{event.event_id}"
        self._active_executions = {**self._active_executions, execution_key: execution}
        try:
            max_retries = metadata.retry_count + 1
            last_error = None
            for attempt in range(max_retries):
                execution.retry_attempt = attempt
                try:
                    if metadata.timeout_seconds:
                        result = await asyncio.wait_for(
                            handler.handle(event), timeout=metadata.timeout_seconds
                        )
                    else:
                        result = await handler.handle(event)
                    execution.mark_completed(result)
                    self._update_handler_stats(metadata, execution, True)
                    return result
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue
                    else:
                        break
            failure_result = Failure(
                f"Handler failed after {max_retries} attempts: {last_error}"
            )
            execution.mark_completed(failure_result)
            self._update_handler_stats(metadata, execution, False)
            return failure_result
        finally:
            if execution_key in self._active_executions:
                del self._active_executions[execution_key]
            self._execution_history = self._execution_history + [execution]

    def _update_handler_stats(
        self, metadata: HandlerMetadata, execution: HandlerExecution, success: bool
    ) -> None:
        """핸들러 통계 업데이트"""
        execution_count = execution_count + 1
        if success:
            success_count = success_count + 1
        else:
            failure_count = failure_count + 1
        if execution.execution_time_ms:
            total_execution_time_ms = (
                total_execution_time_ms + execution.execution_time_ms
            )

    def get_execution_history(
        self, handler_id=None, limit=100
    ) -> List[HandlerExecution]:
        """실행 기록 조회"""
        history = list(self._execution_history)
        if handler_id:
            history = [ex for ex in history if ex.handler_id == handler_id]
        return history[-limit:]

    def get_active_executions(self) -> List[HandlerExecution]:
        """현재 실행 중인 핸들러 조회"""
        return list(self._active_executions.values())


class HandlerChain:
    """핸들러 체인"""

    def __init__(self, handlers: List[EventHandler]):
        self.handlers = handlers
        self.break_on_failure = False
        self.aggregate_results = True

    async def process(self, event: Event) -> Result[List[Any], str]:
        """체인 처리"""
        results = []
        for handler in self.handlers:
            if not handler.can_handle(event):
                continue
            try:
                result = await handler.handle(event)
                results = results + [result]
                if self.break_on_failure and result.is_failure():
                    break
            except Exception as e:
                failure = Failure(f"Handler chain error: {e}")
                results = results + [failure]
                if self.break_on_failure:
                    break
        if self.aggregate_results:
            return Success(results)
        else:
            return results[-1] if results else Failure("No handlers processed")


def event_handler(
    event_type: Type[Event],
    priority: HandlerPriority = HandlerPriority.NORMAL,
    mode: HandlerMode = HandlerMode.ASYNC,
    timeout_seconds=None,
    retry_count=0,
    conditions: Optional[List[Callable[[Event], bool]]] = None,
    tags: Optional[Set[str]] = None,
):
    """이벤트 핸들러 데코레이터"""

    def decorator(func: Callable[[Event], Union[Any, Result[Any, str]]]):
        handler = FunctionEventHandler(
            handler_func=func,
            event_type=event_type,
            priority=priority,
            mode=mode,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            conditions=conditions or [],
        )
        handler._decorator_tags = tags
        func._event_handler = handler
        return func

    return decorator


_default_registry = None
_default_processor = None


def get_default_handler_registry() -> HandlerRegistry:
    """기본 핸들러 레지스트리 조회"""
    # global _default_registry - removed for functional programming
    if _default_registry is None:
        _default_registry = HandlerRegistry()
    return _default_registry


def get_default_event_processor() -> EventProcessor:
    """기본 이벤트 처리기 조회"""
    # global _default_processor - removed for functional programming
    if _default_processor is None:
        registry = get_default_handler_registry()
        _default_processor = EventProcessor(registry)
    return _default_processor


def register_handler(
    handler: EventHandler, tags: Optional[Set[str]] = None
) -> Result[None, str]:
    """핸들러 등록 (편의 함수)"""
    registry = get_default_handler_registry()
    return registry.register_handler(handler, tags)


def process_event(event: Event) -> List[Result[Any, str]]:
    """이벤트 처리 (편의 함수)"""
    processor = get_default_event_processor()
    return asyncio.create_task(processor.process_event(event))
