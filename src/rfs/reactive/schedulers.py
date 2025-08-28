"""
Schedulers for Reactive Streams

비동기 작업 스케줄링
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Callable, Optional


class SchedulerType(Enum):
    """스케줄러 타입"""

    IMMEDIATE = "immediate"
    SINGLE = "single"
    PARALLEL = "parallel"
    IO = "io"


class Scheduler:
    """리액티브 스케줄러"""

    def __init__(self, scheduler_type: SchedulerType = SchedulerType.IMMEDIATE) -> None:
        self.scheduler_type = scheduler_type
        self._executor = None

        if scheduler_type == SchedulerType.IO:
            self._executor = ThreadPoolExecutor(
                max_workers=10, thread_name_prefix="rfs-io"
            )
        elif scheduler_type == SchedulerType.PARALLEL:
            self._executor = ThreadPoolExecutor(
                max_workers=None, thread_name_prefix="rfs-parallel"
            )

    async def schedule(self, task: Callable, delay=None):
        """작업 스케줄링"""
        if delay:
            await asyncio.sleep(delay)

        if self.scheduler_type == SchedulerType.IMMEDIATE:
            if asyncio.iscoroutinefunction(task):
                return await task()
            return task()

        elif self.scheduler_type == SchedulerType.SINGLE:
            # 단일 스레드에서 순차 실행
            if asyncio.iscoroutinefunction(task):
                return await task()
            return task()

        elif self.scheduler_type in [SchedulerType.PARALLEL, SchedulerType.IO]:
            # 스레드 풀에서 실행
            if asyncio.iscoroutinefunction(task):
                # 코루틴을 스레드에서 실행
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self._executor, lambda: asyncio.run(task())
                )
            else:
                # 일반 함수를 스레드에서 실행
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(self._executor, task)

    def dispose(self):
        """스케줄러 정리"""
        if self._executor:
            self._executor.shutdown(wait=True)

    def __del__(self):
        """소멸자"""
        self.dispose()


# 미리 정의된 스케줄러들
immediate = Scheduler(SchedulerType.IMMEDIATE)
single = Scheduler(SchedulerType.SINGLE)
parallel = Scheduler(SchedulerType.PARALLEL)
io = Scheduler(SchedulerType.IO)
