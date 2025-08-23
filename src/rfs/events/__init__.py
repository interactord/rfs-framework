"""
Event-driven Architecture module

이벤트 기반 아키텍처 모듈
"""

from .event_bus import EventBus, Event, event_handler, EventHandler, EventFilter, EventSubscription
from .event_store import EventStore, EventStream
from .saga import Saga, SagaManager, saga_step
from .cqrs import (
    CommandHandler, QueryHandler, command, query,
    CommandBus, QueryBus, Command, Query, CommandResult, QueryResult
)
from .event_handler import (
    EventHandler as EnhancedEventHandler, HandlerRegistry, EventProcessor, HandlerChain,
    HandlerPriority, HandlerMode, HandlerMetadata, FunctionEventHandler,
    get_default_handler_registry, get_default_event_processor,
    register_handler, process_event
)

__all__ = [
    # Event Bus
    "EventBus",
    "Event", 
    "event_handler",
    "EventHandler",
    "EventFilter",
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
    "process_event"
]