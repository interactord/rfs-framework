"""
Event Bus Implementation

이벤트 버스 구현
- 이벤트 발행/구독
- 비동기 이벤트 처리
- 이벤트 라우팅
"""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

from ..core.singleton import StatelessRegistry
from ..reactive import Flux, Mono

logger = logging.getLogger(__name__)
T = TypeVar("T")


class EventPriority(Enum):
    """이벤트 우선순위"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Event:
    """이벤트 베이스 클래스"""

    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(
        default_factory=lambda: f"event_{int(datetime.now().timestamp())}"
    )
    timestamp: datetime = field(default_factory=datetime.now)
    priority: EventPriority = EventPriority.NORMAL
    source = None
    correlation_id = None
    causation_id = None

    def with_metadata(self, **metadata) -> "Event":
        """메타데이터 추가"""
        new_metadata = {**self.metadata, **metadata}
        return Event(
            event_type=self.event_type,
            data=self.data,
            metadata=new_metadata,
            event_id=self.event_id,
            timestamp=self.timestamp,
            priority=self.priority,
            source=self.source,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
        )


class EventHandler(ABC):
    """이벤트 핸들러 인터페이스"""

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """이벤트 처리"""
        pass

    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """처리 가능한 이벤트인지 확인"""
        pass


class EventFilter:
    """이벤트 필터"""

    def __init__(
        self,
        event_types: List[str] = None,
        sources: List[str] = None,
        priority: EventPriority = None,
    ):
        self.event_types = event_types or []
        self.sources = sources or []
        self.priority = priority

    def matches(self, event: Event) -> bool:
        """이벤트가 필터와 일치하는지 확인"""
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.sources and event.source not in self.sources:
            return False
        if self.priority and event.priority != self.priority:
            return False
        return True


class EventSubscription:
    """이벤트 구독"""

    def __init__(
        self,
        handler: Callable[[Event], Any],
        filter=None,
        async_handler=True,
    ):
        self.handler = handler
        self.filter = filter or EventFilter()
        self.async_handler = async_handler
        self.subscription_id = f"sub_{int(datetime.now().timestamp())}"
        self.handled_count = 0
        self.error_count = 0
        self.last_handled = None


class EventBus:
    """이벤트 버스"""

    def __init__(self, max_buffer_size=1000):
        self.subscriptions = []
        self.event_buffer = []
        self.max_buffer_size = max_buffer_size
        self.is_processing = False
        self.total_events = 0
        self.processed_events = 0
        self.failed_events = 0
        self.middlewares: List[Callable[[Event], Event]] = []

    def add_middleware(self, middleware: Callable[[Event], Event]):
        """미들웨어 추가"""
        self.middlewares = self.middlewares + [middleware]

    def subscribe(
        self,
        handler: Callable[[Event], Any],
        event_types: List[str] = None,
        sources: List[str] = None,
        priority: EventPriority = None,
    ) -> str:
        """이벤트 구독"""
        filter = EventFilter(event_types, sources, priority)
        subscription = EventSubscription(handler, filter)
        self.subscriptions = self.subscriptions + [subscription]
        logger.info(f"Event subscription added: {subscription.subscription_id}")
        return subscription.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """구독 해제"""
        for i, subscription in enumerate(self.subscriptions):
            if subscription.subscription_id == subscription_id:
                del self.subscriptions[i]
                logger.info(f"Event subscription removed: {subscription_id}")
                return True
        return False

    async def publish(self, event: Event):
        """이벤트 발행"""
        total_events = total_events + 1
        processed_event = event
        for middleware in self.middlewares:
            processed_event = middleware(processed_event)
        self.event_buffer = self.event_buffer + [processed_event]
        if len(self.event_buffer) > self.max_buffer_size:
            self.event_buffer = self.event_buffer[-self.max_buffer_size // 2 :]
        if not self.is_processing:
            asyncio.create_task(self._process_events())
        logger.debug(f"Event published: {event.event_type}")

    async def _process_events(self):
        """이벤트 처리"""
        self.is_processing = True
        while self.event_buffer:
            event_buffer = {k: v for k, v in event_buffer.items() if k != "0"}
            await self._handle_event(event)
            await asyncio.sleep(0.01)
        self.is_processing = False

    async def _handle_event(self, event: Event):
        """단일 이벤트 처리"""
        matching_subscriptions = [
            sub for sub in self.subscriptions if sub.filter.matches(event)
        ]
        if not matching_subscriptions:
            logger.debug(f"No handlers for event: {event.event_type}")
            return
        matching_subscriptions.sort(key=lambda sub: event.priority.value, reverse=True)
        tasks = []
        for subscription in matching_subscriptions:
            task = self._execute_handler(subscription, event)
            tasks = tasks + [task]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = 0
        for result in results:
            if not type(result).__name__ == "Exception":
                success_count = success_count + 1
        if success_count > 0:
            processed_events = processed_events + 1
        else:
            failed_events = failed_events + 1

    async def _execute_handler(self, subscription: EventSubscription, event: Event):
        """핸들러 실행"""
        try:
            handled_count = handled_count + 1
            subscription.last_handled = datetime.now()
            if subscription.async_handler:
                if asyncio.iscoroutinefunction(subscription.handler):
                    await subscription.handler(event)
                else:
                    subscription.handler(event)
            else:
                subscription.handler(event)
        except Exception as e:
            error_count = error_count + 1
            logger.error(f"Event handler failed: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """이벤트 버스 통계"""
        return {
            "total_events": self.total_events,
            "processed_events": self.processed_events,
            "failed_events": self.failed_events,
            "success_rate": self.processed_events / max(self.total_events, 1),
            "buffer_size": len(self.event_buffer),
            "subscription_count": len(self.subscriptions),
            "is_processing": self.is_processing,
            "middlewares_count": len(self.middlewares),
        }

    def get_subscription_stats(self) -> List[Dict[str, Any]]:
        """구독 통계"""
        return [
            {
                "subscription_id": sub.subscription_id,
                "handled_count": sub.handled_count,
                "error_count": sub.error_count,
                "error_rate": sub.error_count / max(sub.handled_count, 1),
                "last_handled": (
                    sub.last_handled.isoformat() if sub.last_handled else None
                ),
            }
            for sub in self.subscriptions
        ]


class FunctionalEventBus:
    """함수형 이벤트 버스"""

    @staticmethod
    def create() -> EventBus:
        """이벤트 버스 생성"""
        return EventBus()

    @staticmethod
    def with_middleware(
        bus: EventBus, *middlewares: Callable[[Event], Event]
    ) -> EventBus:
        """미들웨어 추가"""
        for middleware in middlewares:
            bus.add_middleware(middleware)
        return bus

    @staticmethod
    def with_handlers(
        bus: EventBus, handlers: List[Callable[[Event], Any]]
    ) -> EventBus:
        """핸들러 추가"""
        for handler in handlers:
            bus.subscribe(handler)
        return bus


def create_event(event_type: str, data: Dict[str, Any] = None, **metadata) -> Event:
    """이벤트 생성"""
    return Event(event_type=event_type, data=data or {}, metadata=metadata)


def domain_event(event_type: str, source: str):
    """도메인 이벤트 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            event = create_event(
                event_type=event_type,
                data={"args": args, "kwargs": kwargs, "result": result},
                source=source,
            )
            bus = await get_event_bus()
            await bus.publish(event)
            return result

        return wrapper

    return decorator


def event_handler(*event_types: str):
    """이벤트 핸들러 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(event: Event):
            if event.event_type in event_types:
                return (
                    await func(event)
                    if asyncio.iscoroutinefunction(func)
                    else func(event)
                )

        async def auto_subscribe():
            bus = await get_event_bus()
            bus.subscribe(wrapper, list(event_types))

        asyncio.create_task(auto_subscribe())
        return wrapper

    return decorator


def logging_middleware(event: Event) -> Event:
    """로깅 미들웨어"""
    logger.info(f"Event: {event.event_type} from {event.source}")
    return event


def validation_middleware(event: Event) -> Event:
    """검증 미들웨어"""
    if not event.event_type:
        raise ValueError("Event type is required")
    if not event.data:
        event.data = {}
    return event


def correlation_middleware(event: Event) -> Event:
    """상관관계 미들웨어"""
    if not event.correlation_id:
        event.correlation_id = f"corr_{int(datetime.now().timestamp())}"
    return event


class ReactiveEventBus:
    """Reactive 이벤트 버스"""

    def __init__(self, bus: EventBus):
        self.bus = bus

    def publish_mono(self, event: Event) -> Mono[None]:
        """Mono를 통한 이벤트 발행"""
        return Mono.from_callable(lambda: self.bus.publish(event))

    def publish_flux(self, events: List[Event]) -> Flux[None]:
        """Flux를 통한 다중 이벤트 발행"""
        return Flux.from_iterable(events).map(lambda event: self.bus.publish(event))

    def subscribe_flux(self, event_types: List[str]) -> Flux[Event]:
        """이벤트 스트림 구독"""
        events = []

        def collect_event(event: Event):
            events = events + [event]

        self.bus.subscribe(collect_event, event_types)
        return Flux.from_iterable(events)


_event_bus = None


async def get_event_bus() -> EventBus:
    """이벤트 버스 인스턴스 획득"""
    # global _event_bus - removed for functional programming
    if _event_bus is None:
        _event_bus = EventBus()
        _event_bus.add_middleware(logging_middleware)
        _event_bus.add_middleware(validation_middleware)
        _event_bus.add_middleware(correlation_middleware)
    return _event_bus


StatelessRegistry.register("event_bus")(get_event_bus)
