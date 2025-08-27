"""
RFS Messaging Performance Tests (RFS v4.3)

메시징 시스템 성능 테스트
"""

import asyncio

import pytest

from rfs.messaging.base import Message
from rfs.messaging.memory_broker import MemoryMessageBroker, MemoryMessageConfig


class TestMessagingPerformance:
    """메시징 성능 테스트"""

    @pytest.mark.asyncio
    async def test_high_volume_publishing(self, performance_timer):
        """대용량 발행 성능 테스트"""
        config = MemoryMessageConfig(max_queue_size=50000)
        broker = MemoryMessageBroker(config)
        await broker.connect()

        try:
            performance_timer.start()

            # 10,000개 메시지 발행
            tasks = []
            for i in range(10000):
                message = Message(topic="perf_topic", data=f"data_{i}")
                tasks.append(broker.publish(message.topic, message))

            results = await asyncio.gather(*tasks)
            performance_timer.stop()

            # 모든 발행이 성공했는지 확인
            assert all(result.is_success() for result in results)

            # 10,000개 발행이 5초 미만이어야 함
            assert performance_timer.elapsed < 5.0

        finally:
            await broker.disconnect()

    @pytest.mark.asyncio
    async def test_concurrent_publish_subscribe(self, performance_timer):
        """동시 발행/구독 성능 테스트"""
        config = MemoryMessageConfig()
        broker = MemoryMessageBroker(config)
        await broker.connect()

        try:
            received_count = 0

            async def counter_handler(message: Message):
                nonlocal received_count
                received_count += 1

            # 구독자 등록
            await broker.subscribe("concurrent_topic", counter_handler)

            performance_timer.start()

            # 동시 발행
            async def publisher_worker(worker_id: int, message_count: int):
                for i in range(message_count):
                    message = Message(
                        topic="concurrent_topic", data=f"worker_{worker_id}_msg_{i}"
                    )
                    await broker.publish(message.topic, message)

            # 5개 워커가 각각 100개 메시지 발행
            tasks = [publisher_worker(i, 100) for i in range(5)]
            await asyncio.gather(*tasks)

            performance_timer.stop()

            # 모든 메시지가 처리될 시간 대기
            await asyncio.sleep(0.1)

            # 500개 메시지 발행/구독이 2초 미만이어야 함
            assert performance_timer.elapsed < 2.0
            assert received_count == 500

        finally:
            await broker.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message_size", ["small", "medium", "large"])
    async def test_message_size_performance(self, message_size, performance_timer):
        """메시지 크기별 성능 테스트"""
        config = MemoryMessageConfig()
        broker = MemoryMessageBroker(config)
        await broker.connect()

        try:
            # 크기별 데이터 생성
            data_sizes = {
                "small": "x" * 100,  # 100 bytes
                "medium": "x" * 10000,  # 10KB
                "large": "x" * 1000000,  # 1MB
            }

            data = data_sizes[message_size]
            message_count = 100

            performance_timer.start()

            # 메시지 발행
            for i in range(message_count):
                message = Message(topic="size_test", data=data)
                result = await broker.publish(message.topic, message)
                assert result.is_success()

            performance_timer.stop()

            # 크기별 성능 기준
            max_times = {
                "small": 0.1,  # 100개 작은 메시지: 0.1초
                "medium": 1.0,  # 100개 중간 메시지: 1초
                "large": 5.0,  # 100개 큰 메시지: 5초
            }

            assert performance_timer.elapsed < max_times[message_size]

        finally:
            await broker.disconnect()
