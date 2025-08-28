"""
RFS Message Queue Base (RFS v4.1)

메시지 큐 기본 클래스 및 설정
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = get_logger(__name__)

T = TypeVar("T")


class BrokerType(str, Enum):
    """브로커 타입"""

    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    GOOGLE_PUBSUB = "google_pubsub"
    MEMORY = "memory"


class MessagePriority(int, Enum):
    """메시지 우선순위"""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 9
    CRITICAL = 10


@dataclass
class Message:
    """메시지"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    data: Any = None
    headers: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: MessagePriority = MessagePriority.NORMAL
    ttl: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    dead_letter_topic: Optional[str] = None
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

        if not (
            hasattr(self.timestamp, "__class__")
            and self.timestamp.__class__.__name__ == "datetime"
        ):
            self.timestamp = datetime.now()

    @property
    def is_expired(self) -> bool:
        """메시지 만료 확인"""
        if self.ttl is None:
            return False

        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl

    @property
    def should_retry(self) -> bool:
        """재시도 가능 여부"""
        return self.retry_count < self.max_retries

    def increment_retry(self):
        """재시도 횟수 증가"""
        self.retry_count = self.retry_count + 1

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "topic": self.topic,
            "data": self.data,
            "headers": self.headers,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "ttl": self.ttl,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "dead_letter_topic": self.dead_letter_topic,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """딕셔너리에서 생성"""
        timestamp = data.get("timestamp")
        if type(timestamp).__name__ == "str":
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        priority = data.get("priority", MessagePriority.NORMAL.value)
        if type(priority).__name__ == "int":
            priority = MessagePriority(priority)

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic=data.get("topic", ""),
            data=data.get("data"),
            headers=data.get("headers", {}),
            timestamp=timestamp,
            priority=priority,
            ttl=data.get("ttl"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            dead_letter_topic=data.get("dead_letter_topic"),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
        )

    def serialize(self) -> bytes:
        """직렬화"""
        try:
            return json.dumps(self.to_dict(), ensure_ascii=False).encode()
        except Exception as e:
            logger.error(f"메시지 직렬화 실패: {e}")
            return b""

    @classmethod
    def deserialize(cls, data: bytes) -> Optional["Message"]:
        """역직렬화"""
        try:
            message_dict = json.loads(data.decode())
            return cls.from_dict(message_dict)
        except Exception as e:
            logger.error(f"메시지 역직렬화 실패: {e}")
            return None


@dataclass
class MessageConfig:
    """메시지 설정"""

    # 브로커 설정
    broker_type: BrokerType = BrokerType.REDIS
    broker_url: str = "redis://localhost:6379"
    host: str = "localhost"
    port: int = 6379

    # 연결 설정
    connection_pool_size: int = 10
    connection_timeout: int = 30
    heartbeat_interval: int = 30

    # 메시지 설정
    default_ttl: int = 3600  # 1시간
    max_message_size: int = 1024 * 1024  # 1MB
    default_max_retries: int = 3
    max_retries: int = 3  # Alias for compatibility

    # 배치 처리
    batch_size: int = 100
    batch_timeout: float = 1.0  # 초

    # Dead Letter Queue
    enable_dlq: bool = True
    dlq_suffix: str = ".dlq"

    # 메트릭스
    enable_metrics: bool = True
    metrics_interval: int = 60

    # 직렬화
    serializer: str = "json"  # json, pickle, msgpack
    compression: bool = False

    # 기타
    namespace: str = "rfs"
    auto_ack: bool = True
    prefetch_count: int = 10


class MessageBroker(ABC):
    """메시지 브로커 추상 클래스"""

    def __init__(self, config: MessageConfig):
        self.config = config
        self._connected = False
        self._publishers: Dict[str, Any] = {}
        self._subscribers: Dict[str, Any] = {}
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "messages_acked": 0,
            "messages_nacked": 0,
            "messages_expired": 0,
            "messages_retried": 0,
            "errors": 0,
        }

    @abstractmethod
    async def connect(self) -> Result[None, str]:
        """브로커 연결"""
        pass

    @abstractmethod
    async def disconnect(self) -> Result[None, str]:
        """브로커 연결 해제"""
        pass

    @abstractmethod
    async def publish(self, topic: str, message: Message) -> Result[None, str]:
        """메시지 발행"""
        pass

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable) -> Result[None, str]:
        """토픽 구독"""
        pass

    @abstractmethod
    async def unsubscribe(self, topic: str) -> Result[None, str]:
        """구독 해제"""
        pass

    @abstractmethod
    async def create_topic(self, topic: str, **kwargs) -> Result[None, str]:
        """토픽 생성"""
        pass

    @abstractmethod
    async def delete_topic(self, topic: str) -> Result[None, str]:
        """토픽 삭제"""
        pass

    @abstractmethod
    async def list_topics(self) -> Result[List[str], str]:
        """토픽 목록"""
        pass

    # 배치 처리
    async def publish_batch(
        self, topic: str, messages: List[Message]
    ) -> Result[None, str]:
        """배치 메시지 발행"""
        try:
            for message in messages:
                result = await self.publish(topic, message)
                if not result.is_success():
                    return result

            return Success(None)

        except Exception as e:
            error_msg = f"배치 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    # 메시지 확인
    async def ack_message(self, message: Message) -> Result[None, str]:
        """메시지 확인"""
        self._stats = {
            **self._stats,
            "messages_acked": self._stats["messages_acked"] + 1,
        }
        return Success(None)

    async def nack_message(self, message: Message, requeue=True) -> Result[None, str]:
        """메시지 거부"""
        self._stats = {
            **self._stats,
            "messages_nacked": self._stats["messages_nacked"] + 1,
        }

        if requeue and message.should_retry:
            message.increment_retry()
            # 재시도 로직
            result = await self.publish(message.topic, message)
            if result.is_success():
                self._stats = {
                    **self._stats,
                    "messages_retried": self._stats["messages_retried"] + 1,
                }
            return result
        elif message.dead_letter_topic:
            # Dead Letter Queue로 이동
            return await self.publish(message.dead_letter_topic, message)

        return Success(None)

    # 유틸리티 메서드
    def _validate_message(self, message: Message) -> Result[None, str]:
        """메시지 유효성 검증"""
        if not message.topic:
            return Failure("토픽이 필요합니다")

        if message.is_expired:
            return Failure("메시지가 만료되었습니다")

        # 메시지 크기 확인
        serialized = message.serialize()
        if len(serialized) > self.config.max_message_size:
            return Failure(f"메시지가 너무 큽니다: {len(serialized)} bytes")

        return Success(None)

    def _make_topic_name(self, topic: str) -> str:
        """네임스페이스가 포함된 토픽 이름 생성"""
        if self.config.namespace:
            return f"{self.config.namespace}.{topic}"
        return topic

    def _make_dlq_topic(self, topic: str) -> str:
        """Dead Letter Queue 토픽 이름 생성"""
        return f"{topic}{self.config.dlq_suffix}"

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        total_messages = self._stats["messages_sent"] + self._stats["messages_received"]
        error_rate = (
            (self._stats["errors"] / total_messages) if total_messages > 0 else 0
        )

        return {
            **self._stats,
            "total_messages": total_messages,
            "error_rate": round(error_rate, 4),
        }

    def reset_stats(self):
        """통계 초기화"""
        for key in self._stats:
            self._stats = {**self._stats, key: 0}

    @property
    def is_connected(self) -> bool:
        """연결 상태"""
        return self._connected


class MessageManager(metaclass=SingletonMeta):
    """메시지 매니저"""

    def __init__(self):
        self.brokers = {}
        self.default_broker = None

    async def add_broker(self, name: str, broker: MessageBroker) -> Result[None, str]:
        """브로커 추가"""
        try:
            # 브로커 연결
            connect_result = await broker.connect()
            if not connect_result.is_success():
                return Failure(f"브로커 연결 실패: {connect_result.unwrap_error()}")

            self.brokers = {**self.brokers, name: broker}

            # 첫 번째 브로커를 기본으로 설정
            if not self.default_broker:
                self.default_broker = name

            logger.info(f"메시지 브로커 추가: {name}")
            return Success(None)

        except Exception as e:
            return Failure(f"브로커 추가 실패: {str(e)}")

    def get_broker(self, name: str = None) -> Optional[MessageBroker]:
        """브로커 조회"""
        if name is None:
            name = self.default_broker

        return self.brokers.get(name) if name else None

    async def remove_broker(self, name: str) -> Result[None, str]:
        """브로커 제거"""
        try:
            if name not in self.brokers:
                return Success(None)

            broker = self.brokers[name]

            # 연결 해제
            disconnect_result = await broker.disconnect()
            if not disconnect_result.is_success():
                logger.warning(
                    f"브로커 연결 해제 실패: {disconnect_result.unwrap_error()}"
                )

            del self.brokers[name]

            # 기본 브로커 재설정
            if self.default_broker == name:
                self.default_broker = (
                    next(iter(self.brokers.keys())) if self.brokers else None
                )

            logger.info(f"메시지 브로커 제거: {name}")
            return Success(None)

        except Exception as e:
            return Failure(f"브로커 제거 실패: {str(e)}")

    async def close_all(self) -> Result[None, str]:
        """모든 브로커 연결 해제"""
        try:
            for name, broker in list(self.brokers.items()):
                await self.remove_broker(name)

            logger.info("모든 메시지 브로커 연결 해제")
            return Success(None)

        except Exception as e:
            return Failure(f"브로커 일괄 해제 실패: {str(e)}")

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """모든 브로커 통계"""
        return {name: broker.get_stats() for name, broker in self.brokers.items()}


# 전역 메시지 매니저
def get_message_manager() -> MessageManager:
    """메시지 매니저 인스턴스 반환"""
    return MessageManager()


def get_message_broker(name: str = None) -> Optional[MessageBroker]:
    """메시지 브로커 인스턴스 반환"""
    manager = get_message_manager()
    return manager.get_broker(name)


# 브로커 팩토리
async def create_message_broker(
    config: MessageConfig, name="default"
) -> Result[MessageBroker, str]:
    """메시지 브로커 생성"""
    try:
        match config.broker_type:
            case BrokerType.REDIS:
                from .redis_broker import RedisMessageBroker

                broker = RedisMessageBroker(config)
            case BrokerType.MEMORY:
                from .memory_broker import MemoryMessageBroker

                broker = MemoryMessageBroker(config)
            case BrokerType.RABBITMQ:
                # RabbitMQ 구현 (향후 추가)
                return Failure("RabbitMQ는 아직 구현되지 않았습니다")
            case BrokerType.GOOGLE_PUBSUB:
                # Google Pub/Sub 구현 (향후 추가)
                return Failure("Google Pub/Sub은 아직 구현되지 않았습니다")
            case _:
                return Failure(f"지원되지 않는 브로커 타입: {config.broker_type}")

        # 메시지 매니저에 추가
        manager = get_message_manager()
        add_result = await manager.add_broker(name, broker)

        if not add_result.is_success():
            return Failure(add_result.unwrap_error())

        return Success(broker)

    except Exception as e:
        return Failure(f"브로커 생성 실패: {str(e)}")


# 고수준 메시징 인터페이스
@dataclass
class Messaging:
    broker_name = "default"

    @property
    def broker(self) -> Optional[MessageBroker]:
        """메시지 브로커"""
        return get_message_broker(self.broker_name)

    async def send(self, topic: str, data: Any, **kwargs) -> bool:
        """메시지 전송"""
        broker = self.broker
        if not broker:
            return False

        message = Message(topic=topic, data=data, **kwargs)
        result = await broker.publish(topic, message)
        return result.is_success()

    async def listen(self, topic: str, handler: Callable) -> bool:
        """토픽 구독"""
        broker = self.broker
        if not broker:
            return False

        result = await broker.subscribe(topic, handler)
        return result.is_success()

    async def stop_listening(self, topic: str) -> bool:
        """구독 해제"""
        broker = self.broker
        if not broker:
            return False

        result = await broker.unsubscribe(topic)
        return result.is_success()


# 전역 메시징 인스턴스
_default_messaging = Messaging()


def messaging() -> Messaging:
    """기본 메시징 인스턴스 반환"""
    return _default_messaging
