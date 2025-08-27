"""
Edge case tests to reach 100% coverage for queue.py
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from rfs.async_tasks.queue import (
    DelayedTaskQueue,
    DistributedTaskQueue,
    SimpleTaskQueue,
)


@pytest.mark.asyncio
async def test_simple_queue_clear_empty_exception():
    """SimpleTaskQueue clear에서 QueueEmpty 예외 발생 테스트"""
    queue = SimpleTaskQueue()

    # 큐에 아이템 추가
    await queue.put("item1")

    # clear 도중 QueueEmpty 예외 발생 시뮬레이션
    original_get_nowait = queue._queue.get_nowait
    call_count = [0]

    def mock_get_nowait():
        call_count[0] += 1
        if call_count[0] == 1:
            return original_get_nowait()  # 첫 번째는 성공
        else:
            raise asyncio.QueueEmpty()  # 두 번째는 예외

    with patch.object(queue._queue, "get_nowait", side_effect=mock_get_nowait):
        await queue.clear()  # 예외가 잡혀야 함

    # 큐가 비워졌는지 확인
    assert await queue.size() == 0


@pytest.mark.asyncio
async def test_delayed_queue_clear_empty_exception():
    """DelayedTaskQueue clear에서 QueueEmpty 예외 발생 테스트"""
    queue = DelayedTaskQueue()
    await queue.start()

    try:
        # ready_queue에 아이템 추가
        await queue.put((1, "item1"))
        await asyncio.sleep(0.1)  # ready_queue로 이동 대기

        # clear 도중 QueueEmpty 예외 발생 시뮬레이션
        original_get_nowait = queue._ready_queue.get_nowait
        call_count = [0]

        def mock_get_nowait():
            call_count[0] += 1
            if call_count[0] == 1:
                return original_get_nowait()  # 첫 번째는 성공
            else:
                raise asyncio.QueueEmpty()  # 두 번째는 예외

        with patch.object(
            queue._ready_queue, "get_nowait", side_effect=mock_get_nowait
        ):
            await queue.clear()  # 예외가 잡혀야 함
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_distributed_queue_peek_empty_all():
    """DistributedTaskQueue peek에서 모든 큐가 비어있는 경우"""
    mock_redis = Mock()
    # 모든 큐에서 lindex가 None 반환 (비어있음)
    mock_redis.lindex.return_value = None

    queue = DistributedTaskQueue(redis_client=mock_redis, priority_queues=True)

    result = await queue.peek()
    assert result is None  # line 379 coverage

    # 모든 우선순위 큐에 대해 lindex 호출되었는지 확인
    assert mock_redis.lindex.call_count == 5  # 5개 우선순위 큐
