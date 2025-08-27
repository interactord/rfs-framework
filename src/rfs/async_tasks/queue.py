"""
Task Queue Implementation for Async Task Management

작업 큐 구현 - 우선순위, 지연, 분산 큐
"""

import asyncio
import heapq
import json
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import redis

from .base import TaskPriority


@dataclass(order=True)
class QueueItem:
    """큐 아이템"""

    priority: int
    timestamp: datetime = field(compare=False)
    task_id: str = field(compare=False)
    data: Any = field(default=None, compare=False)


class TaskQueue(ABC):
    """작업 큐 인터페이스"""

    @abstractmethod
    async def put(self, item: Any):
        """아이템 추가"""
        pass

    @abstractmethod
    async def get(self) -> Any:
        """아이템 가져오기"""
        pass

    @abstractmethod
    async def size(self) -> int:
        """큐 크기"""
        pass

    @abstractmethod
    async def clear(self):
        """큐 클리어"""
        pass

    @abstractmethod
    async def peek(self) -> Optional[Any]:
        """다음 아이템 미리보기"""
        pass


class SimpleTaskQueue(TaskQueue):
    """단순 작업 큐"""

    def __init__(self):
        self._queue = asyncio.Queue()

    async def put(self, item: Any):
        """아이템 추가"""
        await self._queue.put(item)

    async def get(self) -> Any:
        """아이템 가져오기"""
        return await self._queue.get()

    async def size(self) -> int:
        """큐 크기"""
        return self._queue.qsize()

    async def clear(self):
        """큐 클리어"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def peek(self) -> Optional[Any]:
        """다음 아이템 미리보기"""
        if self._queue.empty():
            return None
        item = await self._queue.get()
        await self._queue.put(item)
        return item


class PriorityTaskQueue(TaskQueue):
    """우선순위 작업 큐"""

    def __init__(self):
        self._heap = []
        self._condition = asyncio.Condition()
        self._counter = 0

    async def put(self, item: Tuple[int, str]):
        """아이템 추가"""
        priority, task_id = item
        async with self._condition:
            queue_item = QueueItem(
                priority=priority, timestamp=datetime.now(), task_id=task_id
            )
            heapq.heappush(self._heap, queue_item)
            self._counter = self._counter + 1
            self._condition.notify()

    async def get(self) -> Tuple[int, str]:
        """아이템 가져오기"""
        async with self._condition:
            while not self._heap:
                await self._condition.wait()
            item = heapq.heappop(self._heap)
            return (item.priority, item.task_id)

    async def size(self) -> int:
        """큐 크기"""
        async with self._condition:
            return len(self._heap)

    async def clear(self):
        """큐 클리어"""
        async with self._condition:
            self._heap = []
            self._counter = 0

    async def peek(self) -> Optional[Tuple[int, str]]:
        """다음 아이템 미리보기"""
        async with self._condition:
            if not self._heap:
                return None
            item = self._heap[0]
            return (item.priority, item.task_id)

    async def remove(self, task_id: str) -> bool:
        """특정 작업 제거"""
        async with self._condition:
            for i, item in enumerate(self._heap):
                if item.task_id == task_id:
                    del self._heap[i]
                    heapq.heapify(self._heap)
                    return True
            return False


class DelayedTaskQueue(TaskQueue):
    """지연 작업 큐"""

    def __init__(self):
        self._items: List[Tuple[datetime, QueueItem]] = []
        self._condition = asyncio.Condition()
        self._worker_task = None
        self._ready_queue = asyncio.Queue()

    async def start(self):
        """큐 시작"""
        if not self._worker_task:
            self._worker_task = asyncio.create_task(self._process_delayed())

    async def stop(self):
        """큐 중지"""
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

    async def put(self, item: Tuple[int, str], delay=None):
        """아이템 추가"""
        priority, task_id = item
        if delay:
            scheduled_time = datetime.now() + delay
        else:
            scheduled_time = datetime.now()
        async with self._condition:
            queue_item = QueueItem(
                priority=priority, timestamp=scheduled_time, task_id=task_id
            )
            import bisect

            bisect.insort(self._items, (scheduled_time, queue_item))
            self._condition.notify()

    async def get(self) -> Tuple[int, str]:
        """아이템 가져오기"""
        item = await self._ready_queue.get()
        return (item.priority, item.task_id)

    async def size(self) -> int:
        """큐 크기"""
        async with self._condition:
            return len(self._items) + self._ready_queue.qsize()

    async def clear(self):
        """큐 클리어"""
        async with self._condition:
            self._items = []
        while not self._ready_queue.empty():
            try:
                self._ready_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def peek(self) -> Optional[Tuple[int, str]]:
        """다음 아이템 미리보기"""
        if not self._ready_queue.empty():
            item = await self._ready_queue.get()
            await self._ready_queue.put(item)
            return (item.priority, item.task_id)
        async with self._condition:
            if self._items:
                _, item = self._items[0]
                return (item.priority, item.task_id)
        return None

    async def _process_delayed(self):
        """지연 작업 처리"""
        while True:
            try:
                async with self._condition:
                    now = datetime.now()
                    ready_items = []
                    while self._items and self._items[0][0] <= now:
                        _, item = self._items.pop(0)
                        ready_items = ready_items + [item]
                    for item in ready_items:
                        await self._ready_queue.put(item)
                    if self._items:
                        next_time = self._items[0][0]
                        wait_time = (next_time - now).total_seconds()
                        await asyncio.wait_for(
                            self._condition.wait(), timeout=max(0.1, wait_time)
                        )
                    else:
                        await self._condition.wait()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                import logging

                logging.error(f"Error in delayed queue processor: {e}")
                await asyncio.sleep(1)


class DistributedTaskQueue(TaskQueue):
    """
    분산 작업 큐 (Redis 기반)

    여러 프로세스/머신에서 공유 가능한 큐
    """

    def __init__(
        self,
        redis_client=None,
        queue_name="task_queue",
        priority_queues=True,
        serializer="json",
    ):
        self.redis = redis_client or redis.Redis(decode_responses=False)
        self.queue_name = queue_name
        self.priority_queues = priority_queues
        self.serializer = serializer
        if priority_queues:
            self.queue_names = {
                TaskPriority.CRITICAL: f"{queue_name}:critical",
                TaskPriority.HIGH: f"{queue_name}:high",
                TaskPriority.NORMAL: f"{queue_name}:normal",
                TaskPriority.LOW: f"{queue_name}:low",
                TaskPriority.BACKGROUND: f"{queue_name}:background",
            }

    def _serialize(self, data: Any) -> bytes:
        """데이터 직렬화"""
        if self.serializer == "json":
            return json.dumps(data).encode("utf-8")
        else:
            return pickle.dumps(data)

    def _deserialize(self, data: bytes) -> Any:
        """데이터 역직렬화"""
        if self.serializer == "json":
            return json.loads(data.decode("utf-8"))
        else:
            return pickle.loads(data)

    async def put(self, item: Tuple[int, str]):
        """아이템 추가"""
        priority_value, task_id = item
        if self.priority_queues:
            priority = TaskPriority(priority_value)
            queue_name = self.queue_names[priority]
        else:
            queue_name = self.queue_name
        data = self._serialize(
            {
                "priority": priority_value,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
            }
        )
        await asyncio.get_event_loop().run_in_executor(
            None, self.redis.rpush, queue_name, data
        )

    async def get(self) -> Tuple[int, str]:
        """아이템 가져오기"""
        if self.priority_queues:
            queue_names = [
                self.queue_names[TaskPriority.CRITICAL],
                self.queue_names[TaskPriority.HIGH],
                self.queue_names[TaskPriority.NORMAL],
                self.queue_names[TaskPriority.LOW],
                self.queue_names[TaskPriority.BACKGROUND],
            ]
        else:
            queue_names = [self.queue_name]
        while True:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.redis.blpop, queue_names, 1
            )
            if result:
                queue_name, data = result
                item = self._deserialize(data)
                return (item.get("priority"), item.get("task_id"))
            await asyncio.sleep(0.1)

    async def size(self) -> int:
        """큐 크기"""
        total = 0
        if self.priority_queues:
            for queue_name in self.queue_names.values():
                length = await asyncio.get_event_loop().run_in_executor(
                    None, self.redis.llen, queue_name
                )
                total = total + length
        else:
            total = await asyncio.get_event_loop().run_in_executor(
                None, self.redis.llen, self.queue_name
            )
        return total

    async def clear(self):
        """큐 클리어"""
        if self.priority_queues:
            for queue_name in self.queue_names.values():
                await asyncio.get_event_loop().run_in_executor(
                    None, self.redis.delete, queue_name
                )
        else:
            await asyncio.get_event_loop().run_in_executor(
                None, self.redis.delete, self.queue_name
            )

    async def peek(self) -> Optional[Tuple[int, str]]:
        """다음 아이템 미리보기"""
        if self.priority_queues:
            queue_names = [
                self.queue_names[TaskPriority.CRITICAL],
                self.queue_names[TaskPriority.HIGH],
                self.queue_names[TaskPriority.NORMAL],
                self.queue_names[TaskPriority.LOW],
                self.queue_names[TaskPriority.BACKGROUND],
            ]
        else:
            queue_names = [self.queue_name]
        for queue_name in queue_names:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.redis.lindex, queue_name, 0
            )
            if result:
                item = self._deserialize(result)
                return (item.get("priority"), item.get("task_id"))
        return None

    async def get_stats(self) -> Dict[str, int]:
        """큐 통계"""
        stats = {}
        if self.priority_queues:
            for priority, queue_name in self.queue_names.items():
                length = await asyncio.get_event_loop().run_in_executor(
                    None, self.redis.llen, queue_name
                )
                stats[priority.name] = length
        else:
            length = await asyncio.get_event_loop().run_in_executor(
                None, self.redis.llen, self.queue_name
            )
            stats["total"] = length
        return stats


_global_queue = None


def get_task_queue() -> TaskQueue:
    """전역 작업 큐 반환"""
    global _global_queue
    if _global_queue is None:
        _global_queue = PriorityTaskQueue()
    return _global_queue
