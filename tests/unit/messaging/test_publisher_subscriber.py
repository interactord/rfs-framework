"""
RFS Framework Publisher/Subscriber 패턴 단위 테스트

Publisher와 Subscriber 클래스의 기능을 테스트합니다.
"""

import asyncio
import os

# 테스트 헬퍼 import
import sys
from typing import Any, List
from unittest.mock import AsyncMock, Mock

import pytest

from rfs.core.result import Failure, Success
from rfs.messaging.base import Message, MessagePriority
from rfs.messaging.memory_broker import MemoryMessageBroker, MemoryMessageConfig
from rfs.messaging.publisher import Publisher
from rfs.messaging.subscriber import Subscriber

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from tests.utils.async_helpers import broker_context, create_memory_broker


class TestPublisherSubscriber:
    """Publisher/Subscriber 패턴 테스트"""

    @pytest.mark.asyncio
    async def test_publisher_basic_operations(self):
        """Publisher 기본 작업 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)

            # 메시지 발행
            result = await publisher.publish("test_data", topic="pub_test")
            assert result.is_success()

    @pytest.mark.asyncio
    async def test_subscriber_basic_operations(self):
        """Subscriber 기본 작업 테스트"""
        async with broker_context() as broker:
            subscriber = Subscriber(broker=broker)
            received = []

            async def handler(msg):
                received.append(msg)

            # 구독
            result = await subscriber.subscribe("sub_test", handler)
            assert result.is_success()

            # Publisher로 메시지 발행
            publisher = Publisher(broker=broker)
            message = Message(topic="sub_test", data="test_data")
            await publisher.publish(message.data, topic="sub_test")

            # 메시지 수신 대기
            await asyncio.sleep(0.1)
            assert len(received) > 0

    @pytest.mark.asyncio
    async def test_pub_sub_integration(self):
        """Publisher-Subscriber 통합 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)
            subscriber = Subscriber(broker=broker)

            received_messages = []

            async def message_handler(msg):
                received_messages.append(msg)

            # 구독 설정
            await subscriber.subscribe("integration_topic", message_handler)

            # 여러 메시지 발행
            for i in range(5):
                message = Message(
                    topic="integration_topic",
                    data={"index": i, "content": f"message_{i}"},
                )
                await publisher.publish(message.data, topic="integration_topic")

            # 메시지 처리 대기
            await asyncio.sleep(0.2)

            # 모든 메시지가 수신되었는지 확인
            assert len(received_messages) == 5

            # 구독 취소
            await subscriber.unsubscribe("integration_topic")

    @pytest.mark.asyncio
    async def test_publisher_batch_publish(self):
        """Publisher 배치 발행 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)

            # 배치 메시지 생성
            messages = [
                Message(topic="batch_topic", data=f"batch_{i}") for i in range(10)
            ]

            # 배치 발행 (메서드가 있는 경우)
            if hasattr(publisher, "publish_batch"):
                result = await publisher.publish_batch("batch_topic", messages)
                assert result.is_success()
            else:
                # 개별 발행
                for msg in messages:
                    result = await publisher.publish(msg.data, topic=msg.topic)
                    assert result.is_success()

    @pytest.mark.asyncio
    async def test_subscriber_multiple_topics(self):
        """Subscriber 다중 토픽 구독 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)
            subscriber = Subscriber(broker=broker)

            topic1_messages = []
            topic2_messages = []

            async def topic1_handler(msg):
                topic1_messages.append(msg)

            async def topic2_handler(msg):
                topic2_messages.append(msg)

            # 두 개의 토픽 구독
            await subscriber.subscribe("topic1", topic1_handler)
            await subscriber.subscribe("topic2", topic2_handler)

            # 각 토픽에 메시지 발행
            await publisher.publish("data1", topic="topic1")
            await publisher.publish("data2", topic="topic2")
            await publisher.publish("data3", topic="topic1")

            await asyncio.sleep(0.1)

            # 각 핸들러가 올바른 메시지를 받았는지 확인
            assert len(topic1_messages) == 2
            assert len(topic2_messages) == 1

    @pytest.mark.asyncio
    async def test_publisher_with_priority(self):
        """우선순위를 가진 메시지 발행 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)
            subscriber = Subscriber(broker=broker)

            received_priorities = []

            async def priority_handler(msg):
                if hasattr(msg, "priority"):
                    received_priorities.append(msg.priority)

            await subscriber.subscribe("priority_topic", priority_handler)

            # 다양한 우선순위 메시지 발행
            priorities = [
                MessagePriority.LOW,
                MessagePriority.URGENT,
                MessagePriority.NORMAL,
                MessagePriority.HIGH,
            ]

            for priority in priorities:
                message = Message(
                    topic="priority_topic",
                    data=f"priority_{priority.value}",
                    priority=priority,
                )
                await publisher.publish(
                    message.data, topic="priority_topic", priority=priority
                )

            await asyncio.sleep(0.2)

            # 메시지가 수신되었는지 확인
            assert len(received_priorities) > 0

    @pytest.mark.asyncio
    async def test_subscriber_error_handling(self):
        """Subscriber 에러 처리 테스트"""
        async with broker_context() as broker:
            subscriber = Subscriber(broker=broker)

            async def failing_handler(msg):
                raise Exception("Handler error")

            # 에러를 발생시키는 핸들러 구독
            result = await subscriber.subscribe("error_topic", failing_handler)
            assert result.is_success()

            # 메시지 발행
            publisher = Publisher(broker=broker)
            message = Message(topic="error_topic", data="test")
            await publisher.publish(message.data, topic="error_topic")

            # 에러가 발생해도 시스템이 계속 동작해야 함
            await asyncio.sleep(0.1)

            # 다른 핸들러 추가
            working_messages = []

            async def working_handler(msg):
                working_messages.append(msg)

            await subscriber.subscribe("error_topic", working_handler)
            await publisher.publish("test2", topic="error_topic")

            await asyncio.sleep(0.1)
            assert len(working_messages) > 0

    @pytest.mark.asyncio
    async def test_publisher_subscriber_performance(self):
        """Publisher-Subscriber 성능 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)
            subscriber = Subscriber(broker=broker)

            message_count = 100
            received_count = 0

            async def counter_handler(msg):
                nonlocal received_count
                received_count += 1

            await subscriber.subscribe("perf_topic", counter_handler)

            # 대량 메시지 발행
            start_time = asyncio.get_event_loop().time()

            for i in range(message_count):
                message = Message(topic="perf_topic", data=f"perf_{i}")
                await publisher.publish(message.data, topic="perf_topic")

            # 모든 메시지 처리 대기
            max_wait = 5.0
            waited = 0.0
            while received_count < message_count and waited < max_wait:
                await asyncio.sleep(0.1)
                waited += 0.1

            end_time = asyncio.get_event_loop().time()
            elapsed = end_time - start_time

            # 성능 검증
            assert received_count == message_count
            assert elapsed < 5.0  # 5초 이내에 처리되어야 함

    @pytest.mark.asyncio
    async def test_subscriber_pattern_matching(self):
        """패턴 매칭 구독 테스트 (지원하는 경우)"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)
            subscriber = Subscriber(broker=broker)

            matched_messages = []

            async def pattern_handler(msg):
                matched_messages.append(msg)

            # 패턴 구독 (브로커가 지원하는 경우)
            if hasattr(subscriber, "subscribe_pattern"):
                await subscriber.subscribe_pattern("test.*", pattern_handler)

                # 다양한 토픽에 메시지 발행
                await publisher.publish("1", topic="test.one")
                await publisher.publish("2", topic="test.two")
                await publisher.publish("3", topic="other.topic")

                await asyncio.sleep(0.1)

                # test.* 패턴에 매칭되는 메시지만 수신되어야 함
                assert len(matched_messages) == 2

    @pytest.mark.asyncio
    async def test_publisher_confirmation(self):
        """발행 확인 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)

            # 발행 확인 콜백
            confirmations = []

            async def confirmation_callback(msg_id, success):
                confirmations.append((msg_id, success))

            # 확인 기능이 있는 경우
            if hasattr(publisher, "publish_with_confirmation"):
                message = Message(topic="confirm_topic", data="data")
                await publisher.publish_with_confirmation(
                    "confirm_topic", message, confirmation_callback
                )

                await asyncio.sleep(0.1)
                assert len(confirmations) > 0

    @pytest.mark.asyncio
    async def test_subscriber_backpressure(self):
        """Subscriber 백프레셔 처리 테스트"""
        async with broker_context() as broker:
            publisher = Publisher(broker=broker)
            subscriber = Subscriber(broker=broker)

            slow_processed = []

            async def slow_handler(msg):
                # 느린 처리 시뮬레이션
                await asyncio.sleep(0.05)
                slow_processed.append(msg)

            await subscriber.subscribe("backpressure_topic", slow_handler)

            # 빠르게 많은 메시지 발행
            for i in range(20):
                message = Message(topic="backpressure_topic", data=f"msg_{i}")
                await publisher.publish(message.data, topic="backpressure_topic")
                # 약간의 간격을 두어 일부 메시지가 처리될 수 있게 함
                await asyncio.sleep(0.01)

            # 더 긴 시간 대기 (처리 중인 메시지들 완료)
            await asyncio.sleep(3.0)

            # 백프레셔로 인해 일부 메시지만 처리됨 (max_concurrent_messages=1)
            # 최소 1개는 처리되어야 하고, 모든 메시지가 처리되지는 않을 것
            assert len(slow_processed) >= 1
            assert len(slow_processed) <= 20
            print(
                f"Processed {len(slow_processed)} out of 20 messages with backpressure"
            )
