"""
Event-driven Architecture module

이벤트 기반 아키텍처 모듈
"""

from .cqrs import (
    Command,
    CommandBus,
    CommandHandler,
    CommandResult,
    Query,
    QueryBus,
    QueryHandler,
    QueryResult,
    command,
    query,
)
from .event_bus import (
    Event,
    EventBus,
    EventFilter,
    EventHandler,
    EventSubscription,
    event_handler,
    get_event_bus,
)
from .event_handler import EventHandler as EnhancedEventHandler
from .event_handler import (
    EventProcessor,
    FunctionEventHandler,
    HandlerChain,
    HandlerMetadata,
    HandlerMode,
    HandlerPriority,
    HandlerRegistry,
    get_default_event_processor,
    get_default_handler_registry,
    process_event,
    register_handler,
)
from .event_store import EventStore, EventStream
from .saga import Saga, SagaManager, saga_step

__all__ = [
    # Event Bus
    "EventBus",
    "Event",
    "event_handler",
    "EventHandler",
    "EventFilter",
    "get_event_bus",
    "EventSubscription",
    # Event Store
    "EventStore",
    "EventStream",
    # Saga
    "Saga",
    "SagaManager",
    "saga_step",
    # CQRS
    "CommandHandler",
    "QueryHandler",
    "CommandBus",
    "QueryBus",
    "Command",
    "Query",
    "CommandResult",
    "QueryResult",
    "command",
    "query",
    # Enhanced Event Handler System (NEW)
    "EnhancedEventHandler",
    "HandlerRegistry",
    "EventProcessor",
    "HandlerChain",
    "HandlerPriority",
    "HandlerMode",
    "HandlerMetadata",
    "FunctionEventHandler",
    "get_default_handler_registry",
    "get_default_event_processor",
    "register_handler",
    "process_event",
]
