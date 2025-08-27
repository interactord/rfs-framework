"""
Task Executor Implementation for Async Task Management

작업 실행자 구현 - ThreadPool, ProcessPool, AsyncIO
"""

import asyncio
import concurrent.futures
import logging
import multiprocessing
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Failure, Result, Success
from .base import Task, TaskMetadata

logger = logging.getLogger(__name__)


class TaskExecutor(ABC):
    """작업 실행자 인터페이스"""

    @abstractmethod
    async def start(self):
        """실행자 시작"""
        pass

    @abstractmethod
    async def stop(self):
        """실행자 중지"""
        pass

    @abstractmethod
    async def execute(self, task: Task, context: Dict[str, Any]) -> Any:
        """작업 실행"""
        pass

    @abstractmethod
    async def submit(
        self, func: Callable, *args, **kwargs
    ) -> concurrent.futures.Future:
        """작업 제출"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        pass


class ThreadPoolExecutor(TaskExecutor):
    """스레드 풀 실행자"""

    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.executor = None
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self._lock = threading.Lock()

    async def start(self):
        """실행자 시작"""
        if not self.executor:
            self.executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers, thread_name_prefix="task_worker"
            )
            logger.info(f"ThreadPoolExecutor started with {self.max_workers} workers")

    async def stop(self):
        """실행자 중지"""
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
            logger.info("ThreadPoolExecutor stopped")

    async def execute(self, task: Task, context: Dict[str, Any]) -> Any:
        """작업 실행"""
        if not self.executor:
            raise RuntimeError("Executor not started")

        loop = asyncio.get_event_loop()

        with self._lock:
            self.active_tasks = self.active_tasks + 1

        try:
            # 동기 작업을 스레드에서 실행
            if asyncio.iscoroutinefunction(task.execute):
                # 비동기 작업은 직접 실행
                result = await task.execute(context)
            else:
                # 동기 작업은 스레드 풀에서 실행
                result = await loop.run_in_executor(
                    self.executor, task.execute, context
                )

            with self._lock:
                self.completed_tasks = self.completed_tasks + 1

            return result

        except Exception as e:
            with self._lock:
                self.failed_tasks = self.failed_tasks + 1
            raise
        finally:
            with self._lock:
                self.active_tasks = self.active_tasks - 1

    async def submit(
        self, func: Callable, *args, **kwargs
    ) -> concurrent.futures.Future:
        """작업 제출"""
        if not self.executor:
            raise RuntimeError("Executor not started")

        return self.executor.submit(func, *args, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        with self._lock:
            return {
                "type": "ThreadPool",
                "max_workers": self.max_workers,
                "active_tasks": self.active_tasks,
                "completed_tasks": self.completed_tasks,
                "failed_tasks": self.failed_tasks,
            }


class ProcessPoolExecutor(TaskExecutor):
    """프로세스 풀 실행자"""

    def __init__(self, max_workers=None):
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.executor = None
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self._manager = multiprocessing.Manager()
        self._stats = self._manager.dict()

    async def start(self):
        """실행자 시작"""
        if not self.executor:
            self.executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers
            )
            self._stats = {**self._stats, "active_tasks": 0}
            self._stats = {**self._stats, "completed_tasks": 0}
            self._stats = {**self._stats, "failed_tasks": 0}
            logger.info(f"ProcessPoolExecutor started with {self.max_workers} workers")

    async def stop(self):
        """실행자 중지"""
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
            logger.info("ProcessPoolExecutor stopped")

    async def execute(self, task: Task, context: Dict[str, Any]) -> Any:
        """작업 실행"""
        if not self.executor:
            raise RuntimeError("Executor not started")

        loop = asyncio.get_event_loop()

        self._stats = {**self._stats, "active_tasks": self._stats["active_tasks"] + 1}

        try:
            # 프로세스에서 실행 (pickle 가능한 작업만)
            if asyncio.iscoroutinefunction(task.execute):
                # 비동기 작업은 현재 프로세스에서 실행
                result = await task.execute(context)
            else:
                # 동기 작업은 프로세스 풀에서 실행
                result = await loop.run_in_executor(
                    self.executor, task.execute, context
                )

            self._stats = {
                **self._stats,
                "completed_tasks": self._stats["completed_tasks"] + 1,
            }
            return result

        except Exception as e:
            self._stats = {
                **self._stats,
                "failed_tasks": self._stats["failed_tasks"] + 1,
            }
            raise
        finally:
            self._stats = {
                **self._stats,
                "active_tasks": self._stats["active_tasks"] - 1,
            }

    async def submit(
        self, func: Callable, *args, **kwargs
    ) -> concurrent.futures.Future:
        """작업 제출"""
        if not self.executor:
            raise RuntimeError("Executor not started")

        return self.executor.submit(func, *args, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        return {
            "type": "ProcessPool",
            "max_workers": self.max_workers,
            "active_tasks": self._stats.get("active_tasks", 0),
            "completed_tasks": self._stats.get("completed_tasks", 0),
            "failed_tasks": self._stats.get("failed_tasks", 0),
        }


class AsyncIOExecutor(TaskExecutor):
    """AsyncIO 실행자"""

    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        self.active_tasks = []
        self.completed_tasks = 0
        self.failed_tasks = 0
        self._lock = asyncio.Lock()

    async def start(self):
        """실행자 시작"""
        logger.info(f"AsyncIOExecutor started with {self.max_workers} concurrent tasks")

    async def stop(self):
        """실행자 중지"""
        # 활성 작업 취소
        async with self._lock:
            for task in self.active_tasks:
                if not task.done():
                    task.cancel()

            # 모든 작업 완료 대기
            if self.active_tasks:
                await asyncio.gather(*self.active_tasks, return_exceptions=True)

            self.active_tasks = []

        logger.info("AsyncIOExecutor stopped")

    async def execute(self, task: Task, context: Dict[str, Any]) -> Any:
        """작업 실행"""
        async with self.semaphore:
            async with self._lock:
                current_task = asyncio.current_task()
                if current_task:
                    self.active_tasks.append(current_task)

            try:
                # 비동기 작업 실행
                if asyncio.iscoroutinefunction(task.execute):
                    result = await task.execute(context)
                else:
                    # 동기 작업을 비동기로 래핑
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, task.execute, context)

                async with self._lock:
                    self.completed_tasks = self.completed_tasks + 1

                return result

            except Exception as e:
                async with self._lock:
                    self.failed_tasks = self.failed_tasks + 1
                raise
            finally:
                async with self._lock:
                    current_task = asyncio.current_task()
                    if current_task in self.active_tasks:
                        self.active_tasks = [
                            i for i in self.active_tasks if i != current_task
                        ]

    async def submit(self, func: Callable, *args, **kwargs) -> asyncio.Task:
        """작업 제출"""

        async def wrapped():
            async with self.semaphore:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, func, *args, **kwargs)

        task = asyncio.create_task(wrapped())

        async with self._lock:
            self.active_tasks.append(task)

        return task

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        return {
            "type": "AsyncIO",
            "max_workers": self.max_workers,
            "active_tasks": len(self.active_tasks),
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
        }


class HybridExecutor(TaskExecutor):
    """
    하이브리드 실행자

    CPU 집약적 작업은 프로세스 풀,
    I/O 집약적 작업은 AsyncIO로 실행
    """

    def __init__(
        self,
        async_workers=10,
        process_workers=None,
        thread_workers=5,
    ):
        self.async_executor = AsyncIOExecutor(async_workers)
        self.process_executor = ProcessPoolExecutor(process_workers)
        self.thread_executor = ThreadPoolExecutor(thread_workers)

    async def start(self):
        """실행자 시작"""
        await self.async_executor.start()
        await self.process_executor.start()
        await self.thread_executor.start()
        logger.info("HybridExecutor started")

    async def stop(self):
        """실행자 중지"""
        await self.async_executor.stop()
        await self.process_executor.stop()
        await self.thread_executor.stop()
        logger.info("HybridExecutor stopped")

    async def execute(self, task: Task, context: Dict[str, Any]) -> Any:
        """작업 실행"""
        # 작업 타입에 따라 실행자 선택
        task_type = context.get("task_type", "async")

        match task_type:
            case "cpu":
                # CPU 집약적 작업
                return await self.process_executor.execute(task, context)
            case "io":
                # I/O 집약적 작업 (동기)
                return await self.thread_executor.execute(task, context)
            case _:
                # 기본: 비동기 작업
                return await self.async_executor.execute(task, context)

    async def submit(self, func: Callable, *args, **kwargs):
        """작업 제출"""
        task_type = kwargs.pop("task_type", "async")

        match task_type:
            case "cpu":
                return await self.process_executor.submit(func, *args, **kwargs)
            case "io":
                return await self.thread_executor.submit(func, *args, **kwargs)
            case _:
                return await self.async_executor.submit(func, *args, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        return {
            "type": "Hybrid",
            "async": self.async_executor.get_stats(),
            "process": self.process_executor.get_stats(),
            "thread": self.thread_executor.get_stats(),
        }


# 전역 실행자
_global_executor = None


def get_executor() -> TaskExecutor:
    """전역 작업 실행자 반환"""
    global _global_executor
    if _global_executor is None:
        _global_executor = HybridExecutor()
    return _global_executor
