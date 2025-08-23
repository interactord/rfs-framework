"""
RFS Message Queue System (RFS v4.1)

통합 메시징 시스템
- Pub/Sub 패턴 지원
- Redis/RabbitMQ/Google Pub/Sub 통합
- 메시지 지속성 및 재시도 메커니즘
- Dead Letter Queue 지원
"""

from .base import (
    Message, MessageBroker, MessageConfig, BrokerType,
    get_message_broker, get_message_manager
)
from .publisher import (
    Publisher, BatchPublisher,
    publish_message, publish_batch
)
from .subscriber import (
    Subscriber, MessageHandler, SubscriptionConfig,
    subscribe_topic, create_subscription
)
from .redis_broker import (
    RedisMessageBroker, RedisMessageConfig
)
from .memory_broker import (
    MemoryMessageBroker, MemoryMessageConfig
)
from .decorators import (
    message_handler, topic_subscriber,
    retry_on_failure, dead_letter_queue
)
from .patterns import (
    RequestResponse, WorkQueue, EventBus,
    Saga, MessageRouter
)

__all__ = [
    # Core Components
    "Message", "MessageBroker", "MessageConfig", "BrokerType",
    "get_message_broker", "get_message_manager",
    
    # Publisher
    "Publisher", "BatchPublisher",
    "publish_message", "publish_batch",
    
    # Subscriber
    "Subscriber", "MessageHandler", "SubscriptionConfig",
    "subscribe_topic", "create_subscription",
    
    # Brokers
    "RedisMessageBroker", "RedisMessageConfig",
    "MemoryMessageBroker", "MemoryMessageConfig",
    
    # Decorators
    "message_handler", "topic_subscriber",
    "retry_on_failure", "dead_letter_queue",
    
    # Patterns
    "RequestResponse", "WorkQueue", "EventBus",
    "Saga", "MessageRouter"
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
    "Work Queue"
]