"""
Comprehensive test coverage for queue.py to reach 90% coverage

queue.py 모듈의 90% 커버리지 달성을 위한 포괄적 테스트
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rfs.async_tasks.base import TaskPriority
from rfs.async_tasks.queue import (
    DelayedTaskQueue,
    DistributedTaskQueue,
    PriorityTaskQueue,
    QueueItem,
    SimpleTaskQueue,
    TaskQueue,
    get_task_queue,
)


class TestQueueItem:
    """QueueItem 테스트"""

    def test_queue_item_creation(self):
        """QueueItem 생성 테스트"""
        now = datetime.now()
        item = QueueItem(
            priority=1, timestamp=now, task_id="test-task", data={"key": "value"}
        )

        assert item.priority == 1
        assert item.timestamp == now
        assert item.task_id == "test-task"
        assert item.data == {"key": "value"}

    def test_queue_item_ordering(self):
        """QueueItem 순서 비교 테스트"""
        now = datetime.now()
        item1 = QueueItem(priority=1, timestamp=now, task_id="task1")
        item2 = QueueItem(priority=2, timestamp=now, task_id="task2")
        item3 = QueueItem(
            priority=1, timestamp=now + timedelta(seconds=1), task_id="task3"
        )

        # 우선순위가 낮을수록 먼저
        assert item1 < item2
        assert not (item2 < item1)

        # 같은 우선순위면 timestamp는 비교 안함 (compare=False)
        assert not (item1 < item3)
        assert not (item3 < item1)


class TestSimpleTaskQueue:
    """SimpleTaskQueue 테스트"""

    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """기본 연산 테스트"""
        queue = SimpleTaskQueue()

        # 빈 큐 확인
        assert await queue.size() == 0

        # 아이템 추가
        await queue.put("item1")
        await queue.put("item2")

        # 크기 확인
        assert await queue.size() == 2

        # 아이템 가져오기 (FIFO)
        item1 = await queue.get()
        assert item1 == "item1"

        item2 = await queue.get()
        assert item2 == "item2"

        assert await queue.size() == 0

    @pytest.mark.asyncio
    async def test_peek_operation(self):
        """peek 연산 테스트"""
        queue = SimpleTaskQueue()

        # 빈 큐에서 peek
        result = await queue.peek()
        assert result is None

        # 아이템 추가 후 peek
        await queue.put("peek_item")
        peeked = await queue.peek()
        assert peeked == "peek_item"

        # peek 후에도 아이템이 큐에 남아있는지 확인
        assert await queue.size() == 1
        actual = await queue.get()
        assert actual == "peek_item"

    @pytest.mark.asyncio
    async def test_clear_operation(self):
        """clear 연산 테스트"""
        queue = SimpleTaskQueue()

        # 아이템들 추가
        for i in range(5):
            await queue.put(f"item{i}")

        assert await queue.size() == 5

        # 큐 클리어
        await queue.clear()
        assert await queue.size() == 0

        # 빈 큐 클리어 (아무일도 안일어나야 함)
        await queue.clear()
        assert await queue.size() == 0


class TestPriorityTaskQueue:
    """PriorityTaskQueue 테스트"""

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """우선순위 순서 테스트"""
        queue = PriorityTaskQueue()

        # 다른 우선순위로 추가 (높은 숫자 = 낮은 우선순위)
        await queue.put((3, "low_priority"))
        await queue.put((1, "high_priority"))
        await queue.put((2, "medium_priority"))

        # 우선순위 순으로 가져오기
        item1 = await queue.get()
        assert item1 == (1, "high_priority")

        item2 = await queue.get()
        assert item2 == (2, "medium_priority")

        item3 = await queue.get()
        assert item3 == (3, "low_priority")

    @pytest.mark.asyncio
    async def test_size_and_clear(self):
        """크기 확인 및 클리어 테스트"""
        queue = PriorityTaskQueue()

        assert await queue.size() == 0

        await queue.put((1, "task1"))
        await queue.put((2, "task2"))

        assert await queue.size() == 2

        await queue.clear()
        assert await queue.size() == 0

    @pytest.mark.asyncio
    async def test_peek_operation(self):
        """peek 연산 테스트"""
        queue = PriorityTaskQueue()

        # 빈 큐에서 peek
        result = await queue.peek()
        assert result is None

        # 아이템들 추가
        await queue.put((3, "low"))
        await queue.put((1, "high"))

        # 가장 높은 우선순위 아이템 peek
        peeked = await queue.peek()
        assert peeked == (1, "high")

        # 실제로 가져와도 같은 아이템
        actual = await queue.get()
        assert actual == (1, "high")

    @pytest.mark.asyncio
    async def test_remove_operation(self):
        """특정 작업 제거 테스트"""
        queue = PriorityTaskQueue()

        # 여러 아이템 추가
        await queue.put((1, "task1"))
        await queue.put((2, "task2"))
        await queue.put((3, "task3"))

        # 존재하는 작업 제거
        result = await queue.remove("task2")
        assert result is True
        assert await queue.size() == 2

        # 존재하지 않는 작업 제거 시도
        result = await queue.remove("nonexistent")
        assert result is False
        assert await queue.size() == 2

        # 남은 작업들 확인
        item1 = await queue.get()
        assert item1 == (1, "task1")

        item2 = await queue.get()
        assert item2 == (3, "task3")

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """동시성 테스트"""
        queue = PriorityTaskQueue()

        async def producer():
            for i in range(10):
                await queue.put((i, f"task{i}"))
                await asyncio.sleep(0.01)

        async def consumer():
            results = []
            for _ in range(10):
                item = await queue.get()
                results.append(item)
                await asyncio.sleep(0.01)
            return results

        # 동시에 실행
        producer_task = asyncio.create_task(producer())
        consumer_task = asyncio.create_task(consumer())

        results = await consumer_task
        await producer_task

        # 우선순위 순으로 정렬되어 나왔는지 확인
        priorities = [r[0] for r in results]
        assert priorities == sorted(priorities)


class TestDelayedTaskQueue:
    """DelayedTaskQueue 테스트"""

    @pytest.mark.asyncio
    async def test_immediate_execution(self):
        """즉시 실행 테스트"""
        queue = DelayedTaskQueue()
        await queue.start()

        try:
            # 지연 없이 추가
            await queue.put((1, "immediate_task"))

            # 짧은 시간 후 가져올 수 있어야 함
            await asyncio.sleep(0.1)

            item = await queue.get()
            assert item == (1, "immediate_task")
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_delayed_execution(self):
        """지연 실행 테스트"""
        queue = DelayedTaskQueue()
        await queue.start()

        try:
            start_time = datetime.now()

            # 0.2초 지연으로 추가
            await queue.put((1, "delayed_task"), delay=timedelta(seconds=0.2))

            # 즉시는 가져올 수 없음 (타임아웃)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(queue.get(), timeout=0.1)

            # 충분한 시간 후에는 가져올 수 있음
            item = await asyncio.wait_for(queue.get(), timeout=0.3)
            end_time = datetime.now()

            assert item == (1, "delayed_task")
            elapsed = (end_time - start_time).total_seconds()
            assert elapsed >= 0.2
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_size_and_clear(self):
        """크기 및 클리어 테스트"""
        queue = DelayedTaskQueue()
        await queue.start()

        try:
            assert await queue.size() == 0

            # 지연 작업 추가
            await queue.put((1, "task1"), delay=timedelta(seconds=1))
            await queue.put((2, "task2"))  # 즉시

            await asyncio.sleep(0.1)  # ready_queue로 이동 대기

            size = await queue.size()
            assert size >= 1  # 최소 1개는 있어야 함

            await queue.clear()
            assert await queue.size() == 0
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_peek_operation(self):
        """peek 연산 테스트"""
        queue = DelayedTaskQueue()
        await queue.start()

        try:
            # 빈 큐에서 peek
            result = await queue.peek()
            assert result is None

            # 즉시 실행 작업 추가
            await queue.put((1, "immediate"))
            await asyncio.sleep(0.1)

            # peek 확인
            peeked = await queue.peek()
            assert peeked == (1, "immediate")

            # 지연 작업만 있는 경우
            await queue.clear()
            await queue.put((2, "delayed"), delay=timedelta(seconds=1))
            await asyncio.sleep(0.1)

            peeked = await queue.peek()
            assert peeked == (2, "delayed")
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_process_delayed_error_handling(self):
        """지연 처리 에러 핸들링 테스트"""
        queue = DelayedTaskQueue()

        # _process_delayed에서 예외 발생 시뮬레이션
        original_method = queue._ready_queue.put

        async def failing_put(item):
            raise Exception("Simulated error")

        with patch.object(queue._ready_queue, "put", side_effect=failing_put):
            await queue.start()

            try:
                await queue.put((1, "task"))
                await asyncio.sleep(0.2)  # 에러 처리 대기
                # 예외가 발생해도 큐가 계속 동작해야 함
            finally:
                await queue.stop()

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        """시작/정지 생명주기 테스트"""
        queue = DelayedTaskQueue()

        # 시작 전에는 worker_task가 없음
        assert queue._worker_task is None

        # 시작
        await queue.start()
        assert queue._worker_task is not None

        # 중복 시작은 무시
        old_task = queue._worker_task
        await queue.start()
        assert queue._worker_task is old_task

        # 정지
        await queue.stop()
        assert queue._worker_task is None

        # 중복 정지는 안전
        await queue.stop()
        assert queue._worker_task is None


@pytest.mark.asyncio
async def test_distributed_task_queue_mock():
    """DistributedTaskQueue 모킹 테스트"""
    # Redis 모킹
    mock_redis = Mock()
    mock_redis.rpush.return_value = 1
    mock_redis.blpop.return_value = (
        "test_queue:high",
        b'{"priority": 1, "task_id": "test", "timestamp": "2023-01-01T00:00:00"}',
    )
    mock_redis.llen.return_value = 5
    mock_redis.delete.return_value = 1
    mock_redis.lindex.return_value = (
        b'{"priority": 1, "task_id": "peek_test", "timestamp": "2023-01-01T00:00:00"}'
    )

    queue = DistributedTaskQueue(redis_client=mock_redis)

    # put 테스트
    await queue.put((1, "test_task"))
    mock_redis.rpush.assert_called()

    # get 테스트
    item = await queue.get()
    assert item == (1, "test")

    # size 테스트
    size = await queue.size()
    assert size == 25  # 5개 큐 * 5 = 25

    # clear 테스트
    await queue.clear()
    assert mock_redis.delete.call_count == 5  # 5개 우선순위 큐

    # peek 테스트
    peeked = await queue.peek()
    assert peeked == (1, "peek_test")


@pytest.mark.asyncio
async def test_distributed_queue_serialization():
    """직렬화/역직렬화 테스트"""
    # JSON 시리얼라이저
    mock_redis = Mock()
    queue_json = DistributedTaskQueue(redis_client=mock_redis, serializer="json")

    test_data = {"priority": 1, "task_id": "test", "timestamp": "2023-01-01"}

    # JSON 직렬화
    serialized = queue_json._serialize(test_data)
    assert isinstance(serialized, bytes)

    # JSON 역직렬화
    deserialized = queue_json._deserialize(serialized)
    assert deserialized == test_data

    # Pickle 시리얼라이저
    queue_pickle = DistributedTaskQueue(redis_client=mock_redis, serializer="pickle")

    # Pickle 직렬화/역직렬화
    serialized_pickle = queue_pickle._serialize(test_data)
    deserialized_pickle = queue_pickle._deserialize(serialized_pickle)
    assert deserialized_pickle == test_data


@pytest.mark.asyncio
async def test_distributed_queue_non_priority():
    """비우선순위 분산 큐 테스트"""
    mock_redis = Mock()
    mock_redis.rpush.return_value = 1
    mock_redis.blpop.return_value = (
        "simple_queue",
        b'{"priority": 1, "task_id": "simple", "timestamp": "2023-01-01T00:00:00"}',
    )
    mock_redis.llen.return_value = 3
    mock_redis.delete.return_value = 1
    mock_redis.lindex.return_value = (
        b'{"priority": 2, "task_id": "peek_simple", "timestamp": "2023-01-01T00:00:00"}'
    )

    queue = DistributedTaskQueue(
        redis_client=mock_redis, queue_name="simple_queue", priority_queues=False
    )

    # put/get 테스트
    await queue.put((1, "simple_task"))
    item = await queue.get()
    assert item == (1, "simple")

    # size 테스트
    size = await queue.size()
    assert size == 3

    # clear 테스트
    await queue.clear()
    mock_redis.delete.assert_called_with("simple_queue")

    # peek 테스트
    peeked = await queue.peek()
    assert peeked == (2, "peek_simple")


@pytest.mark.asyncio
async def test_distributed_queue_stats():
    """분산 큐 통계 테스트"""
    mock_redis = Mock()
    mock_redis.llen.return_value = 2

    # 우선순위 큐 통계
    queue_priority = DistributedTaskQueue(redis_client=mock_redis, priority_queues=True)
    stats = await queue_priority.get_stats()

    expected_priorities = ["CRITICAL", "HIGH", "NORMAL", "LOW", "BACKGROUND"]
    for priority in expected_priorities:
        assert priority in stats
        assert stats[priority] == 2

    # 단순 큐 통계
    queue_simple = DistributedTaskQueue(redis_client=mock_redis, priority_queues=False)
    stats = await queue_simple.get_stats()
    assert "total" in stats
    assert stats["total"] == 2


@pytest.mark.asyncio
async def test_distributed_queue_get_timeout():
    """분산 큐 get 타임아웃 테스트"""
    mock_redis = Mock()
    # blpop이 None을 반환하도록 설정 (타임아웃)
    mock_redis.blpop.side_effect = [
        None,
        None,
        (
            "test_queue:normal",
            b'{"priority": 2, "task_id": "delayed", "timestamp": "2023-01-01T00:00:00"}',
        ),
    ]

    queue = DistributedTaskQueue(redis_client=mock_redis)

    # 첫 번째 시도에서는 타임아웃 발생, 세 번째에서 성공
    with patch("asyncio.sleep") as mock_sleep:
        item = await queue.get()
        assert item == (2, "delayed")
        # sleep이 2번 호출되었는지 확인 (두 번의 타임아웃)
        assert mock_sleep.call_count == 2


class TestGlobalQueue:
    """전역 큐 함수 테스트"""

    def test_get_task_queue_singleton(self):
        """전역 큐 싱글톤 테스트"""
        # 전역 변수 초기화
        import rfs.async_tasks.queue

        rfs.async_tasks.queue._global_queue = None

        # 첫 번째 호출
        queue1 = get_task_queue()
        assert queue1 is not None
        assert isinstance(queue1, PriorityTaskQueue)

        # 두 번째 호출에서 같은 인스턴스 반환
        queue2 = get_task_queue()
        assert queue1 is queue2

    @pytest.mark.asyncio
    async def test_global_queue_functionality(self):
        """전역 큐 기능 테스트"""
        import rfs.async_tasks.queue

        rfs.async_tasks.queue._global_queue = None

        queue = get_task_queue()

        # 기본 기능 테스트
        await queue.put((1, "global_test"))
        item = await queue.get()
        assert item == (1, "global_test")


class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_priority_queue_empty_get_timeout(self):
        """우선순위 큐 빈 상태에서 get 타임아웃 테스트"""
        queue = PriorityTaskQueue()

        # 빈 큐에서 get 시도 (타임아웃)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_delayed_queue_without_start(self):
        """DelayedTaskQueue 시작 없이 사용 테스트"""
        queue = DelayedTaskQueue()

        # start 하지 않고 put/get 시도
        await queue.put((1, "no_start_task"))

        # get은 계속 기다릴 것임
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_queue_item_with_none_data(self):
        """QueueItem data None 테스트"""
        item = QueueItem(priority=1, timestamp=datetime.now(), task_id="test")
        assert item.data is None

    @pytest.mark.asyncio
    async def test_distributed_queue_priority_enum(self):
        """분산 큐 TaskPriority enum 테스트"""
        mock_redis = Mock()
        queue = DistributedTaskQueue(redis_client=mock_redis)

        # 각 우선순위 값에 대한 큐 이름 확인
        assert queue.queue_names[TaskPriority.CRITICAL] == "task_queue:critical"
        assert queue.queue_names[TaskPriority.HIGH] == "task_queue:high"
        assert queue.queue_names[TaskPriority.NORMAL] == "task_queue:normal"
        assert queue.queue_names[TaskPriority.LOW] == "task_queue:low"
        assert queue.queue_names[TaskPriority.BACKGROUND] == "task_queue:background"


@pytest.mark.asyncio
async def test_priority_queue_concurrent_condition():
    """우선순위 큐 condition 동시성 테스트"""
    queue = PriorityTaskQueue()

    results = []

    async def consumer():
        for _ in range(3):
            item = await queue.get()
            results.append(item)

    async def producer():
        await asyncio.sleep(0.01)
        await queue.put((3, "third"))
        await queue.put((1, "first"))
        await queue.put((2, "second"))

    # 동시 실행
    await asyncio.gather(consumer(), producer())

    # 우선순위 순서 확인
    assert results[0] == (1, "first")
    assert results[1] == (2, "second")
    assert results[2] == (3, "third")
