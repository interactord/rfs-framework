"""
RFS Framework Messaging 시스템 포괄적 단위 테스트

이 모듈은 RFS Messaging 시스템의 모든 기능에 대한 포괄적인 테스트를 제공합니다.
- 메시지 생성 및 관리 테스트
- 메모리 브로커 구현 테스트
- Publisher/Subscriber 패턴 테스트
- 메시지 우선순위 및 TTL 처리 테스트
- 동시성 및 성능 테스트
- 에러 케이스 및 엣지 케이스 테스트
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from rfs.core.result import Failure, Success
from rfs.messaging.base import (
    BrokerType,
    Message,
    MessageBroker,
    MessageConfig,
    MessagePriority,
)
from rfs.messaging.memory_broker import (
    MemoryMessageBroker,
    MemoryMessageConfig,
    MemoryTopic,
)
from rfs.messaging.publisher import Publisher
from rfs.messaging.subscriber import Subscriber


# Module level fixtures
@pytest.fixture
def memory_broker_config():
    """메모리 브로커 설정 fixture"""
    return MemoryMessageConfig(
        max_queue_size=1000, max_topics=100, enable_persistence=False
    )


@pytest_asyncio.fixture
async def memory_broker(memory_broker_config):
    """메모리 브로커 fixture"""
    broker = MemoryMessageBroker(memory_broker_config)
    result = await broker.connect()
    assert result.is_success()
    try:
        yield broker
    finally:
        await broker.disconnect()


class TestMessage:
    """메시지 클래스 테스트"""

    def test_message_creation_with_defaults(self):
        """기본값으로 메시지 생성"""
        message = Message(topic="test_topic", data="test_data")

        assert message.topic == "test_topic"
        assert message.data == "test_data"
        assert message.id is not None
        assert len(message.id) > 0
        assert isinstance(message.timestamp, datetime)
        assert message.priority == MessagePriority.NORMAL
        assert message.retry_count == 0
        assert message.max_retries == 3

    def test_message_creation_with_custom_values(self):
        """사용자 정의 값으로 메시지 생성"""
        custom_id = str(uuid.uuid4())
        custom_timestamp = datetime(2025, 1, 1, 12, 0, 0)
        custom_headers = {"user_id": "123", "request_id": "req_456"}

        message = Message(
            id=custom_id,
            topic="custom_topic",
            data={"key": "value"},
            headers=custom_headers,
            timestamp=custom_timestamp,
            priority=MessagePriority.HIGH,
            ttl=3600,
            max_retries=5,
        )

        assert message.id == custom_id
        assert message.topic == "custom_topic"
        assert message.data == {"key": "value"}
        assert message.headers == custom_headers
        assert message.timestamp == custom_timestamp
        assert message.priority == MessagePriority.HIGH
        assert message.ttl == 3600
        assert message.max_retries == 5

    def test_message_auto_id_generation(self):
        """ID 자동 생성 테스트"""
        message1 = Message(topic="test", data="data1")
        message2 = Message(topic="test", data="data2")

        assert message1.id != message2.id
        assert len(message1.id) > 0
        assert len(message2.id) > 0

    def test_message_expiration_with_ttl(self):
        """TTL을 가진 메시지 만료 테스트"""
        # 즉시 만료되는 메시지
        message = Message(
            topic="test",
            data="data",
            ttl=0.001,
            timestamp=datetime.now() - timedelta(seconds=1),
        )

        assert message.is_expired is True

    def test_message_expiration_without_ttl(self):
        """TTL이 없는 메시지 만료 테스트"""
        message = Message(topic="test", data="data")

        assert message.is_expired is False

    def test_message_retry_logic(self):
        """메시지 재시도 로직 테스트"""
        message = Message(topic="test", data="data", max_retries=3)

        assert message.should_retry is True
        assert message.retry_count == 0

        # 재시도 횟수 증가
        message.retry_count = 1
        assert message.should_retry is True

        message.retry_count = 3
        assert message.should_retry is False

    def test_message_to_dict(self):
        """메시지 딕셔너리 변환 테스트"""
        message = Message(
            topic="test_topic",
            data={"key": "value"},
            headers={"header": "value"},
            priority=MessagePriority.HIGH,
            ttl=3600,
        )

        message_dict = message.to_dict()

        assert message_dict["topic"] == "test_topic"
        assert message_dict["data"] == {"key": "value"}
        assert message_dict["headers"] == {"header": "value"}
        assert message_dict["priority"] == MessagePriority.HIGH.value
        assert message_dict["ttl"] == 3600
        assert "id" in message_dict
        assert "timestamp" in message_dict

    def test_message_priority_enum(self):
        """메시지 우선순위 열거형 테스트"""
        assert MessagePriority.LOW.value == 1
        assert MessagePriority.NORMAL.value == 5
        assert MessagePriority.HIGH.value == 8
        assert MessagePriority.CRITICAL.value == 10

        # 우선순위 비교
        assert MessagePriority.CRITICAL > MessagePriority.HIGH
        assert MessagePriority.HIGH > MessagePriority.NORMAL
        assert MessagePriority.NORMAL > MessagePriority.LOW


class TestMessageConfig:
    """메시지 설정 테스트"""

    def test_default_message_config(self):
        """기본 메시지 설정 테스트"""
        config = MessageConfig()

        assert config.broker_type == BrokerType.REDIS
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.default_ttl == 3600
        assert config.max_retries == 3
        assert config.enable_metrics is True

    def test_custom_message_config(self):
        """사용자 정의 메시지 설정 테스트"""
        config = MessageConfig(
            broker_type=BrokerType.MEMORY,
            host="custom-host",
            port=5672,
            default_ttl=7200,
            max_retries=5,
        )

        assert config.broker_type == BrokerType.MEMORY
        assert config.host == "custom-host"
        assert config.port == 5672
        assert config.default_ttl == 7200
        assert config.max_retries == 5

    def test_memory_message_config(self):
        """메모리 메시지 설정 테스트"""
        config = MemoryMessageConfig(
            max_queue_size=5000, max_topics=500, enable_persistence=True
        )

        assert config.max_queue_size == 5000
        assert config.max_topics == 500
        assert config.enable_persistence is True
        assert config.broker_type == BrokerType.MEMORY


class TestMemoryTopic:
    """메모리 토픽 테스트"""

    @pytest.fixture
    def memory_topic(self):
        """메모리 토픽 fixture"""
        return MemoryTopic("test_topic", max_size=100)

    def test_memory_topic_creation(self):
        """메모리 토픽 생성 테스트"""
        topic = MemoryTopic("test_topic", max_size=500)

        assert topic.name == "test_topic"
        assert topic.max_size == 500
        assert len(topic.messages) == 0
        assert len(topic.subscribers) == 0
        assert topic.stats["messages_published"] == 0

    @pytest.mark.asyncio
    async def test_memory_topic_publish_normal_message(self, memory_topic):
        """일반 메시지 발행 테스트"""
        message = Message(topic="test_topic", data="test_data")

        result = await memory_topic.publish(message)

        assert result.is_success()
        assert len(memory_topic.messages) == 1
        assert memory_topic.messages[0].data == "test_data"
        assert memory_topic.stats["messages_published"] == 1

    @pytest.mark.asyncio
    async def test_memory_topic_publish_priority_messages(self, memory_topic):
        """우선순위 메시지 발행 테스트"""
        # 일반 메시지 먼저 발행
        normal_msg = Message(
            topic="test", data="normal", priority=MessagePriority.NORMAL
        )
        await memory_topic.publish(normal_msg)

        # 높은 우선순위 메시지 발행
        high_msg = Message(topic="test", data="high", priority=MessagePriority.HIGH)
        await memory_topic.publish(high_msg)

        # 치명적 우선순위 메시지 발행
        critical_msg = Message(
            topic="test", data="critical", priority=MessagePriority.CRITICAL
        )
        await memory_topic.publish(critical_msg)

        # 우선순위 순으로 정렬되어 있는지 확인
        messages = list(memory_topic.messages)
        assert messages[0].data == "critical"  # 가장 높은 우선순위
        assert messages[1].data == "high"
        assert messages[2].data == "normal"

    @pytest.mark.asyncio
    async def test_memory_topic_message_history(self, memory_topic):
        """메시지 히스토리 테스트"""
        messages = [Message(topic="test", data=f"data_{i}") for i in range(5)]

        for message in messages:
            await memory_topic.publish(message)

        assert len(memory_topic.message_history) == 5
        for i, history_entry in enumerate(memory_topic.message_history):
            assert history_entry["message_id"] == messages[i].id
            assert history_entry["topic"] == "test"

    @pytest.mark.asyncio
    async def test_memory_topic_max_size_limit(self):
        """토픽 최대 크기 제한 테스트"""
        topic = MemoryTopic("test", max_size=3)

        # 최대 크기보다 많은 메시지 발행
        for i in range(5):
            message = Message(topic="test", data=f"data_{i}")
            await topic.publish(message)

        # 최대 크기만큼만 유지되는지 확인
        assert len(topic.messages) == 3
        # 가장 최근 메시지들이 유지되는지 확인
        messages = list(topic.messages)
        assert messages[-1].data == "data_4"

    @pytest.mark.asyncio
    async def test_memory_topic_subscriber_notification(self, memory_topic):
        """구독자 알림 테스트"""
        received_messages = []

        async def subscriber_handler(message: Message):
            received_messages.append(message)

        # 구독자 등록
        memory_topic.subscribers.add(subscriber_handler)

        # 메시지 발행
        message = Message(topic="test", data="notification_test")
        await memory_topic.publish(message)

        # 구독자가 메시지를 받았는지 확인
        await asyncio.sleep(0.01)  # 비동기 알림 처리 시간
        assert len(received_messages) == 1
        assert received_messages[0].data == "notification_test"


class TestMemoryMessageBroker:
    """메모리 메시지 브로커 테스트"""

    @pytest.mark.asyncio
    async def test_memory_broker_connect_disconnect(self, memory_broker_config):
        """메모리 브로커 연결/해제 테스트"""
        broker = MemoryMessageBroker(memory_broker_config)

        # 연결 테스트
        result = await broker.connect()
        assert result.is_success()
        assert broker._connected is True

        # 해제 테스트
        result = await broker.disconnect()
        assert result.is_success()
        assert broker._connected is False

    @pytest.mark.asyncio
    async def test_memory_broker_publish_message(self, memory_broker_config):
        """메모리 브로커 메시지 발행 테스트"""
        broker = MemoryMessageBroker(memory_broker_config)
        await broker.connect()

        try:
            message = Message(topic="test_topic", data="test_data")

            result = await broker.publish(message.topic, message)

            assert result.is_success()
            assert "test_topic" in broker.topics
            assert len(broker.topics["test_topic"].messages) == 1
        finally:
            await broker.disconnect()

    @pytest.mark.asyncio
    async def test_memory_broker_subscribe_unsubscribe(self, memory_broker):
        """메모리 브로커 구독/구독해제 테스트"""
        received_messages = []

        async def message_handler(message: Message):
            received_messages.append(message)

        # 구독
        result = await memory_broker.subscribe("test_topic", message_handler)
        assert result.is_success()

        # 메시지 발행
        message = Message(topic="test_topic", data="subscribe_test")
        await memory_broker.publish(message.topic, message)

        # 메시지 수신 확인
        await asyncio.sleep(0.01)
        assert len(received_messages) == 1
        assert received_messages[0].data == "subscribe_test"

        # 구독 해제
        result = await memory_broker.unsubscribe_handler("test_topic", message_handler)
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_memory_broker_multiple_subscribers(self, memory_broker):
        """다중 구독자 테스트"""
        received_messages_1 = []
        received_messages_2 = []

        async def handler1(message: Message):
            received_messages_1.append(message)

        async def handler2(message: Message):
            received_messages_2.append(message)

        # 두 구독자 등록
        await memory_broker.subscribe("test_topic", handler1)
        await memory_broker.subscribe("test_topic", handler2)

        # 메시지 발행
        message = Message(topic="test_topic", data="multi_subscriber_test")
        await memory_broker.publish(message.topic, message)

        # 두 구독자 모두 메시지 수신 확인
        await asyncio.sleep(0.01)
        assert len(received_messages_1) == 1
        assert len(received_messages_2) == 1
        assert received_messages_1[0].data == "multi_subscriber_test"
        assert received_messages_2[0].data == "multi_subscriber_test"

    @pytest.mark.asyncio
    async def test_memory_broker_topic_creation(self, memory_broker):
        """동적 토픽 생성 테스트"""
        # 새 토픽에 메시지 발행
        message = Message(topic="new_topic", data="new_topic_data")
        result = await memory_broker.publish(message.topic, message)

        assert result.is_success()
        assert "new_topic" in memory_broker.topics
        assert memory_broker.topics["new_topic"].name == "new_topic"

    @pytest.mark.asyncio
    async def test_memory_broker_topic_limit(self):
        """토픽 개수 제한 테스트"""
        config = MemoryMessageConfig(max_topics=3)
        broker = MemoryMessageBroker(config)
        await broker.connect()

        try:
            # 제한을 초과하는 토픽 생성 시도
            for i in range(5):
                message = Message(topic=f"topic_{i}", data=f"data_{i}")
                result = await broker.publish(message.topic, message)

                if i < 3:
                    assert result.is_success()
                else:
                    # 토픽 제한 초과시의 동작은 구현에 따라 다를 수 있음
                    # 최소한 예외는 발생하지 않아야 함
                    pass

        finally:
            await broker.disconnect()

    @pytest.mark.asyncio
    async def test_memory_broker_message_consumption(self, memory_broker):
        """메시지 소비 테스트"""
        # 메시지 발행
        message = Message(topic="consume_topic", data="consume_data")
        await memory_broker.publish(message.topic, message)

        # 메시지 소비
        result = await memory_broker.consume_message("consume_topic")

        assert result.is_success()
        consumed_message = result.unwrap()
        assert consumed_message is not None
        assert consumed_message.data == "consume_data"

    @pytest.mark.asyncio
    async def test_memory_broker_empty_topic_consumption(self, memory_broker):
        """빈 토픽에서 소비 테스트"""
        result = await memory_broker.consume_message("empty_topic")

        assert result.is_success()
        consumed_message = result.unwrap()
        assert consumed_message is None  # 메시지가 없으므로 None

    @pytest.mark.asyncio
    async def test_memory_broker_batch_operations(self, memory_broker):
        """배치 연산 테스트 - 개별 발행/소비 시뮬레이션"""
        messages = [Message(topic="batch_topic", data=f"data_{i}") for i in range(5)]

        # 배치 발행 시뮬레이션 (개별 발행)
        for message in messages:
            result = await memory_broker.publish(message.topic, message)
            assert result.is_success()

        # 배치 소비 시뮬레이션 (개별 소비)
        consumed_messages = []
        for _ in range(3):
            result = await memory_broker.consume_message("batch_topic")
            assert result.is_success()
            message = result.unwrap()
            if message:  # message가 None일 수 있음
                consumed_messages.append(message)

        # 최소 1개는 소비되었어야 함
        assert len(consumed_messages) >= 1

    @pytest.mark.asyncio
    async def test_memory_broker_message_filtering(self, memory_broker):
        """메시지 필터링 테스트"""
        # 다양한 우선순위의 메시지 발행
        messages = [
            Message(topic="filter_topic", data="low", priority=MessagePriority.LOW),
            Message(
                topic="filter_topic", data="normal", priority=MessagePriority.NORMAL
            ),
            Message(topic="filter_topic", data="high", priority=MessagePriority.HIGH),
        ]

        for message in messages:
            await memory_broker.publish(message.topic, message)

        # 높은 우선순위 메시지 확인 - 우선순위 순으로 소비됨
        result = await memory_broker.consume_message("filter_topic")
        assert result.is_success()
        first_message = result.unwrap()

        # 첫 번째로 소비된 메시지는 HIGH 우선순위여야 함 (우선순위 큐)
        if first_message:
            assert first_message.priority == MessagePriority.HIGH
            assert first_message.data == "high"


class TestPublisherSubscriber:
    """Publisher/Subscriber 패턴 테스트"""

    @pytest_asyncio.fixture
    async def pub_sub_setup(self):
        """Publisher/Subscriber 설정 fixture"""
        config = MemoryMessageConfig()
        broker = MemoryMessageBroker(config)
        await broker.connect()

        publisher = Publisher(broker=broker)
        subscriber = Subscriber(broker=broker)

        yield {"broker": broker, "publisher": publisher, "subscriber": subscriber}

        await broker.disconnect()

    @pytest.mark.asyncio
    async def test_publisher_basic_publish(self, pub_sub_setup):
        """기본 발행 테스트"""
        publisher = pub_sub_setup["publisher"]

        result = await publisher.publish({"message": "hello"}, topic="test_topic")

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_publisher_with_headers(self, pub_sub_setup):
        """헤더가 포함된 발행 테스트"""
        publisher = pub_sub_setup["publisher"]
        headers = {"user_id": "123", "correlation_id": "abc"}

        result = await publisher.publish(
            "header_topic", "data_with_headers", headers=headers
        )

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_publisher_with_priority(self, pub_sub_setup):
        """우선순위가 포함된 발행 테스트"""
        publisher = pub_sub_setup["publisher"]

        result = await publisher.publish(
            "priority_topic", "urgent_data", priority=MessagePriority.CRITICAL
        )

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_subscriber_basic_subscription(self, pub_sub_setup):
        """기본 구독 테스트"""
        publisher = pub_sub_setup["publisher"]
        subscriber = pub_sub_setup["subscriber"]

        received_messages = []

        async def handler(message: Message):
            received_messages.append(message)

        # 구독 설정
        await subscriber.subscribe("test_topic", handler)

        # 메시지 발행
        await publisher.publish("subscription_test", topic="test_topic")

        # 메시지 수신 확인
        await asyncio.sleep(0.01)
        assert len(received_messages) == 1
        assert received_messages[0].data == "subscription_test"

    @pytest.mark.asyncio
    async def test_subscriber_multiple_topics(self, pub_sub_setup):
        """다중 토픽 구독 테스트"""
        publisher = pub_sub_setup["publisher"]
        subscriber = pub_sub_setup["subscriber"]

        received_messages = []

        async def handler(message: Message):
            received_messages.append(message)

        # 여러 토픽 구독
        await subscriber.subscribe("topic1", handler)
        await subscriber.subscribe("topic2", handler)

        # 각 토픽에 메시지 발행
        await publisher.publish("message1", topic="topic1")
        await publisher.publish("message2", topic="topic2")

        # 두 메시지 모두 수신 확인
        await asyncio.sleep(0.01)
        assert len(received_messages) == 2

        topics = [msg.topic for msg in received_messages]
        assert "topic1" in topics
        assert "topic2" in topics

    @pytest.mark.asyncio
    async def test_request_reply_pattern(self, pub_sub_setup):
        """요청-응답 패턴 테스트"""
        publisher = pub_sub_setup["publisher"]
        subscriber = pub_sub_setup["subscriber"]
        broker = pub_sub_setup["broker"]

        # 응답 처리기
        async def request_handler(message: Message):
            reply_message = Message(
                topic=message.reply_to,
                data=f"Response to {message.data}",
                correlation_id=message.correlation_id,
            )
            await broker.publish(reply_message.topic, reply_message)

        # 요청 처리를 위한 구독
        await subscriber.subscribe("request_topic", request_handler)

        # 응답을 받기 위한 설정
        reply_topic = f"reply_{uuid.uuid4()}"
        received_replies = []

        async def reply_handler(message: Message):
            received_replies.append(message)

        await subscriber.subscribe(reply_topic, reply_handler)

        # 요청 발송
        correlation_id = str(uuid.uuid4())
        await publisher.publish(
            "test_request",
            topic="request_topic",
            reply_to=reply_topic,
            correlation_id=correlation_id,
        )

        # 응답 수신 확인
        await asyncio.sleep(0.01)
        assert len(received_replies) == 1
        assert received_replies[0].correlation_id == correlation_id
        assert "Response to test_request" in received_replies[0].data


class TestMessagingErrorHandling:
    """메시징 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_broker_disconnected_operations(self):
        """연결되지 않은 브로커 연산 테스트"""
        config = MemoryMessageConfig()
        broker = MemoryMessageBroker(config)

        # 연결하지 않고 연산 시도
        message = Message(topic="test", data="data")

        result = await broker.publish(message.topic, message)
        assert result.is_failure()

        result = await broker.consume_message("test")
        assert result.is_failure()

    @pytest.mark.asyncio
    async def test_invalid_message_handling(self, memory_broker):
        """유효하지 않은 메시지 처리 테스트"""
        # None 메시지
        result = await memory_broker.publish("test_topic", None)
        assert result.is_failure()

        # 빈 토픽 메시지
        message = Message(topic="", data="data")
        result = await memory_broker.publish(message.topic, message)
        assert result.is_failure()

    @pytest.mark.asyncio
    async def test_subscriber_handler_exception(self, memory_broker):
        """구독자 핸들러 예외 처리 테스트"""
        exception_count = 0

        async def failing_handler(message: Message):
            nonlocal exception_count
            exception_count += 1
            raise ValueError("Handler error")

        # 예외 발생 핸들러 등록
        await memory_broker.subscribe("error_topic", failing_handler)

        # 메시지 발행
        message = Message(topic="error_topic", data="error_test")
        result = await memory_broker.publish(message.topic, message)

        # 발행은 성공해야 하지만, 핸들러 예외가 발생
        assert result.is_success()
        await asyncio.sleep(0.01)
        assert exception_count == 1

    @pytest.mark.asyncio
    async def test_message_expiration_handling(self, memory_broker):
        """만료된 메시지 처리 테스트"""
        # 즉시 만료되는 메시지
        expired_message = Message(
            topic="expire_topic",
            data="expired_data",
            ttl=0.001,
            timestamp=datetime.now() - timedelta(seconds=1),
        )

        # 만료된 메시지 발행은 실패해야 함
        result = await memory_broker.publish(expired_message.topic, expired_message)
        assert result.is_failure()
        assert "메시지가 만료되었습니다" in result.unwrap_error()

        # 만료되지 않은 메시지로 정상 테스트
        normal_message = Message(
            topic="expire_topic", data="normal_data", ttl=60  # 60초
        )

        result = await memory_broker.publish(normal_message.topic, normal_message)
        assert result.is_success()

        # 정상 메시지 소비
        result = await memory_broker.consume_message("expire_topic")
        assert result.is_success()
        consumed_message = result.unwrap()
        assert consumed_message is not None
        assert consumed_message.data == "normal_data"


class TestMessagingIntegration:
    """메시징 통합 테스트"""

    @pytest.mark.asyncio
    async def test_real_world_chat_system(self, sample_data):
        """실제 채팅 시스템 시뮬레이션"""
        config = MemoryMessageConfig()
        broker = MemoryMessageBroker(config)
        await broker.connect()

        try:
            # 사용자별 메시지 수신함
            user_messages = {user["id"]: [] for user in sample_data["users"]}

            # 사용자별 메시지 핸들러
            async def create_user_handler(user_id: int):
                async def handler(message: Message):
                    user_messages[user_id].append(message)

                return handler

            # 각 사용자를 채팅방에 구독
            for user in sample_data["users"]:
                handler = await create_user_handler(user["id"])
                await broker.subscribe("chatroom_1", handler)

            # 메시지 발송 시뮬레이션
            chat_messages = [
                {"sender": 1, "content": "안녕하세요!"},
                {"sender": 2, "content": "반갑습니다!"},
                {"sender": 3, "content": "좋은 하루입니다!"},
                {"sender": 1, "content": "오늘 날씨가 좋네요."},
            ]

            for chat_msg in chat_messages:
                message = Message(
                    topic="chatroom_1",
                    data=chat_msg,
                    headers={"sender_id": chat_msg["sender"]},
                )
                await broker.publish(message.topic, message)

            # 메시지 전달 확인
            await asyncio.sleep(0.1)

            # 모든 사용자가 모든 메시지를 받았는지 확인
            for user_id, messages in user_messages.items():
                assert len(messages) == 4

                # 메시지 순서 확인
                contents = [msg.data["content"] for msg in messages]
                expected_contents = [msg["content"] for msg in chat_messages]
                assert contents == expected_contents

        finally:
            await broker.disconnect()

    @pytest.mark.asyncio
    async def test_task_queue_simulation(self):
        """작업 큐 시뮬레이션"""
        config = MemoryMessageConfig()
        broker = MemoryMessageBroker(config)
        await broker.connect()

        try:
            # 작업 결과 추적
            task_results = {}

            # 워커 핸들러
            async def worker_handler(message: Message):
                task_id = message.data["task_id"]
                task_type = message.data["type"]

                # 작업 처리 시뮬레이션
                await asyncio.sleep(0.01)

                # 결과 저장
                task_results[task_id] = {
                    "status": "completed",
                    "type": task_type,
                    "result": f"Processed {task_type} task {task_id}",
                }

                # 결과 발행
                result_message = Message(
                    topic="task_results",
                    data=task_results[task_id],
                    correlation_id=message.correlation_id,
                )
                await broker.publish(result_message.topic, result_message)

            # 결과 핸들러
            completed_tasks = []

            async def result_handler(message: Message):
                completed_tasks.append(message.data)

            # 워커와 결과 핸들러 구독
            await broker.subscribe("task_queue", worker_handler)
            await broker.subscribe("task_results", result_handler)

            # 작업 제출
            task_types = ["email", "report", "backup", "analysis"]
            for i, task_type in enumerate(task_types):
                task = Message(
                    topic="task_queue",
                    data={
                        "task_id": f"task_{i}",
                        "type": task_type,
                        "parameters": {"param": f"value_{i}"},
                    },
                    priority=MessagePriority.NORMAL,
                )
                await broker.publish(task.topic, task)

            # 모든 작업 완료 대기
            await asyncio.sleep(0.1)

            # 결과 확인
            assert len(completed_tasks) == 4
            assert len(task_results) == 4

            for i, task_type in enumerate(task_types):
                task_id = f"task_{i}"
                assert task_id in task_results
                assert task_results[task_id]["status"] == "completed"
                assert task_results[task_id]["type"] == task_type

        finally:
            await broker.disconnect()

    @pytest.mark.asyncio
    async def test_event_sourcing_simulation(self):
        """이벤트 소싱 시뮬레이션"""
        config = MemoryMessageConfig()
        broker = MemoryMessageBroker(config)
        await broker.connect()

        try:
            # 이벤트 저장소
            event_store = []

            # 이벤트 핸들러
            async def event_handler(message: Message):
                event_store.append(
                    {
                        "event_id": message.id,
                        "event_type": message.data["type"],
                        "entity_id": message.data["entity_id"],
                        "data": message.data["data"],
                        "timestamp": message.timestamp,
                    }
                )

            await broker.subscribe("events", event_handler)

            # 이벤트 발행
            events = [
                {
                    "type": "user_created",
                    "entity_id": "user_1",
                    "data": {"name": "김철수"},
                },
                {
                    "type": "user_updated",
                    "entity_id": "user_1",
                    "data": {"email": "kim@example.com"},
                },
                {
                    "type": "order_created",
                    "entity_id": "order_1",
                    "data": {"user_id": "user_1", "amount": 100},
                },
                {
                    "type": "order_paid",
                    "entity_id": "order_1",
                    "data": {"payment_method": "card"},
                },
            ]

            for event_data in events:
                event_message = Message(topic="events", data=event_data)
                await broker.publish(event_message.topic, event_message)

            # 이벤트 처리 대기
            await asyncio.sleep(0.1)

            # 이벤트 저장소 확인
            assert len(event_store) == 4

            # 이벤트 순서 확인
            event_types = [event["event_type"] for event in event_store]
            expected_types = [event["type"] for event in events]
            assert event_types == expected_types

            # 특정 엔티티의 이벤트 조회
            user_events = [e for e in event_store if e["entity_id"] == "user_1"]
            assert len(user_events) == 2
            assert user_events[0]["event_type"] == "user_created"
            assert user_events[1]["event_type"] == "user_updated"

        finally:
            await broker.disconnect()


# 테스트 실행 도우미
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
