"""
RFS Message Queue System (RFS v4.1)

통합 메시징 시스템
- Pub/Sub 패턴 지원
- Redis/RabbitMQ/Google Pub/Sub 통합
- 메시지 지속성 및 재시도 메커니즘
- Dead Letter Queue 지원
"""

from .base import (
    BrokerType,
    Message,
    MessageBroker,
    MessageConfig,
    get_message_broker,
    get_message_manager,
)
from .decorators import (
    dead_letter_queue,
    message_handler,
    retry_on_failure,
    topic_subscriber,
)
from .memory_broker import MemoryMessageBroker, MemoryMessageConfig
from .patterns import EventBus, MessageRouter, RequestResponse, Saga, WorkQueue
from .publisher import BatchPublisher, Publisher, publish_batch, publish_message
from .redis_broker import RedisMessageBroker, RedisMessageConfig
from .subscriber import (
    MessageHandler,
    Subscriber,
    SubscriptionConfig,
    create_subscription,
    subscribe_topic,
)

__all__ = [
    # Core Components
    "Message",
    "MessageBroker",
    "MessageConfig",
    "BrokerType",
    "get_message_broker",
    "get_message_manager",
    # Publisher
    "Publisher",
    "BatchPublisher",
    "publish_message",
    "publish_batch",
    # Subscriber
    "Subscriber",
    "MessageHandler",
    "SubscriptionConfig",
    "subscribe_topic",
    "create_subscription",
    # Brokers
    "RedisMessageBroker",
    "RedisMessageConfig",
    "MemoryMessageBroker",
    "MemoryMessageConfig",
    # Decorators
    "message_handler",
    "topic_subscriber",
    "retry_on_failure",
    "dead_letter_queue",
    # Patterns
    "RequestResponse",
    "WorkQueue",
    "EventBus",
    "Saga",
    "MessageRouter",
]

__version__ = "4.1.0"
__messaging_features__ = [
    "Pub/Sub 패턴",
    "Redis/RabbitMQ 지원",
    "메시지 지속성",
    "재시도 메커니즘",
    "Dead Letter Queue",
    "배치 처리",
    "메시지 라우팅",
    "Saga 패턴",
    "Request-Response",
    "Work Queue",
]
