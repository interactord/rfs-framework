"""
RFS v4.1 Async Task Manager
비동기 작업 관리 시스템

주요 기능:
- 비동기 작업 제출 및 관리
- 작업 상태 추적 및 모니터링
- 작업 취소 및 타임아웃 처리
- 우선순위 기반 작업 처리
- 결과 조회 및 콜백 지원
"""

import asyncio
import logging
import time
import uuid
import weakref
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from ..core.result import Failure, Result, Success

logger = logging.getLogger(__name__)
T = TypeVar("T")
E = TypeVar("E")


class TaskStatus(Enum):
    """작업 상태"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """작업 우선순위"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskInfo:
    """작업 정보"""

    id: str
    name: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    function_name: Optional[str] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    result: Any = None
    error: Optional[Exception] = None
    error_message: Optional[str] = None
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    @property
    def execution_time(self) -> Optional[float]:
        """실행 시간 계산 (초)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def total_time(self) -> float:
        """총 처리 시간 계산 (초)"""
        end_time = self.completed_at or datetime.now()
        return (end_time - self.created_at).total_seconds()

    @property
    def is_finished(self) -> bool:
        """작업 완료 여부"""
        return self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        ]


class TaskCallback(ABC):
    """작업 콜백 인터페이스"""

    @abstractmethod
    async def on_started(self, task_info: TaskInfo) -> None:
        """작업 시작 시 호출"""
        pass

    @abstractmethod
    async def on_completed(self, task_info: TaskInfo, result: Any) -> None:
        """작업 완료 시 호출"""
        pass

    @abstractmethod
    async def on_failed(self, task_info: TaskInfo, error: Exception) -> None:
        """작업 실패 시 호출"""
        pass

    @abstractmethod
    async def on_cancelled(self, task_info: TaskInfo) -> None:
        """작업 취소 시 호출"""
        pass


class SimpleTaskCallback(TaskCallback):
    """간단한 작업 콜백 구현"""

    def __init__(
        self,
        on_started=None,
        on_completed=None,
        on_failed=None,
        on_cancelled=None,
    ):
        self.started_callback = on_started
        self.completed_callback = on_completed
        self.failed_callback = on_failed
        self.cancelled_callback = on_cancelled

    async def on_started(self, task_info: TaskInfo) -> None:
        if self.started_callback:
            if asyncio.iscoroutinefunction(self.started_callback):
                await self.started_callback(task_info)
            else:
                self.started_callback(task_info)

    async def on_completed(self, task_info: TaskInfo, result: Any) -> None:
        if self.completed_callback:
            if asyncio.iscoroutinefunction(self.completed_callback):
                await self.completed_callback(task_info, result)
            else:
                self.completed_callback(task_info, result)

    async def on_failed(self, task_info: TaskInfo, error: Exception) -> None:
        if self.failed_callback:
            if asyncio.iscoroutinefunction(self.failed_callback):
                await self.failed_callback(task_info, error)
            else:
                self.failed_callback(task_info, error)

    async def on_cancelled(self, task_info: TaskInfo) -> None:
        if self.cancelled_callback:
            if asyncio.iscoroutinefunction(self.cancelled_callback):
                await self.cancelled_callback(task_info)
            else:
                self.cancelled_callback(task_info)


@dataclass
class TaskManagerConfig:
    """작업 매니저 설정"""

    max_workers = 10
    max_queue_size = 1000
    default_timeout = None
    default_max_retries = 3
    enable_result_caching = True
    result_cache_ttl = 3600
    cleanup_interval = 300
    enable_detailed_logging = False
    collect_metrics = True
    metrics_interval = 60


class AsyncTaskManager:
    """
    비동기 작업 관리자

    주요 기능:
    - 비동기 작업 제출 및 관리
    - 우선순위 기반 작업 처리
    - 작업 상태 추적 및 모니터링
    - 작업 취소 및 타임아웃 처리
    - 콜백 지원

    사용법:
        manager = AsyncTaskManager()
        task_id = await manager.submit(my_async_function, arg1, arg2)
        result = await manager.get_result(task_id)
    """

    def __init__(self, config: TaskManagerConfig = None):
        self.config = config or TaskManagerConfig()
        self.tasks = {}
        self.running_tasks = {}
        self.pending_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.config.max_queue_size
        )
        self.semaphore = asyncio.Semaphore(self.config.max_workers)
        self.callbacks: Dict[str, List[TaskCallback]] = {}
        self.global_callbacks = []
        self.is_running = False
        self.worker_tasks = []
        self.metrics = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "average_execution_time": 0.0,
            "current_queue_size": 0,
            "active_tasks": 0,
        }
        self.cleanup_task = None
        self.metrics_task = None

    async def start(self) -> None:
        """작업 매니저 시작"""
        if self.is_running:
            return
        self.is_running = True
        for i in range(self.config.max_workers):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self.config.collect_metrics:
            self.metrics_task = asyncio.create_task(self._metrics_loop())
        logger.info(f"AsyncTaskManager started with {self.config.max_workers} workers")

    async def stop(self) -> None:
        """작업 매니저 중지"""
        if not self.is_running:
            return
        self.is_running = False
        cancel_tasks = []
        for task_id in list(self.running_tasks.keys()):
            cancel_tasks = cancel_tasks + [self.cancel_task(task_id)]
        if cancel_tasks:
            await asyncio.gather(*cancel_tasks, return_exceptions=True)
        for worker_task in self.worker_tasks:
            worker_task.cancel()
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.metrics_task:
            self.metrics_task.cancel()
        logger.info("AsyncTaskManager stopped")

    async def submit(
        self,
        func: Callable,
        *args,
        task_id=None,
        name=None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout=None,
        max_retries: int = None,
        callback=None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        """
        비동기 작업 제출

        Args:
            func: 실행할 함수
            *args: 함수 인자
            task_id: 작업 ID (선택사항)
            name: 작업 이름
            priority: 작업 우선순위
            timeout: 타임아웃 (초)
            max_retries: 최대 재시도 횟수
            callback: 작업 콜백
            metadata: 메타데이터
            tags: 태그
            **kwargs: 함수 키워드 인자

        Returns:
            str: 작업 ID
        """
        if not self.is_running:
            await self.start()
        if task_id is None:
            task_id = str(uuid.uuid4())
        if task_id in self.tasks:
            raise ValueError(f"Task with ID {task_id} already exists")
        task_info = TaskInfo(
            id=task_id,
            name=name or getattr(func, "__name__", str(func)),
            status=TaskStatus.PENDING,
            priority=priority,
            function_name=getattr(func, "__name__", str(func)),
            args=args,
            kwargs=kwargs,
            timeout_seconds=timeout or self.config.default_timeout,
            max_retries=max_retries or self.config.default_max_retries,
            metadata=metadata or {},
            tags=tags or [],
        )
        self.tasks = {**self.tasks, task_id: task_info}
        if callback:
            self.register_callback(task_id, callback)
        priority_value = -priority.value
        await self.pending_queue.put(
            (priority_value, time.time(), task_id, func, args, kwargs)
        )
        task_info.status = TaskStatus.QUEUED
        self.metrics = {
            **self.metrics,
            "total_submitted": self.metrics["total_submitted"] + 1,
        }
        self.metrics = {
            **self.metrics,
            "current_queue_size": self.pending_queue.qsize(),
        }
        if self.config.enable_detailed_logging:
            logger.debug(
                f"Task {task_id} ({task_info.name}) submitted with priority {priority.name}"
            )
        return task_id

    async def _worker(self, worker_name: str) -> None:
        """워커 루프"""
        logger.debug(f"Worker {worker_name} started")
        while self.is_running:
            try:
                try:
                    priority, timestamp, task_id, func, args, kwargs = (
                        await asyncio.wait_for(self.pending_queue.get(), timeout=1.0)
                    )
                except asyncio.TimeoutError:
                    continue
                async with self.semaphore:
                    await self._execute_task(task_id, func, args, kwargs)
                self.pending_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
        logger.debug(f"Worker {worker_name} stopped")

    async def _execute_task(
        self, task_id: str, func: Callable, args: tuple, kwargs: dict
    ) -> None:
        """작업 실행"""
        task_info = self.tasks.get(task_id)
        if not task_info:
            logger.error(f"Task {task_id} not found")
            return
        if task_info.status == TaskStatus.CANCELLED:
            return
        task_info.status = TaskStatus.RUNNING
        task_info.started_at = datetime.now()
        self.metrics = {
            **self.metrics,
            "active_tasks": self.metrics["active_tasks"] + 1,
        }
        await self._call_callbacks(task_id, "on_started", task_info)
        try:
            timeout = task_info.timeout_seconds
            if asyncio.iscoroutinefunction(func):
                if timeout:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=timeout
                    )
                else:
                    result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    if timeout:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(
                                executor, lambda: func(*args, **kwargs)
                            ),
                            timeout=timeout,
                        )
                    else:
                        result = await loop.run_in_executor(
                            executor, lambda: func(*args, **kwargs)
                        )
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now()
            task_info.result = result
            self.metrics = {
                **self.metrics,
                "total_completed": self.metrics["total_completed"] + 1,
            }
            await self._call_callbacks(task_id, "on_completed", task_info, result)
            if self.config.enable_detailed_logging:
                logger.debug(f"Task {task_id} completed successfully")
        except asyncio.TimeoutError:
            task_info.status = TaskStatus.TIMEOUT
            task_info.completed_at = datetime.now()
            task_info.error_message = f"Task timed out after {timeout} seconds"
            self.metrics = {
                **self.metrics,
                "total_failed": self.metrics["total_failed"] + 1,
            }
            await self._call_callbacks(
                task_id, "on_failed", task_info, TimeoutError(task_info.error_message)
            )
            logger.warning(f"Task {task_id} timed out after {timeout} seconds")
        except asyncio.CancelledError:
            task_info.status = TaskStatus.CANCELLED
            task_info.completed_at = datetime.now()
            self.metrics = {
                **self.metrics,
                "total_cancelled": self.metrics["total_cancelled"] + 1,
            }
            await self._call_callbacks(task_id, "on_cancelled", task_info)
            logger.info(f"Task {task_id} was cancelled")
        except Exception as e:
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now()
            task_info.error = e
            task_info.error_message = str(e)
            self.metrics = {
                **self.metrics,
                "total_failed": self.metrics["total_failed"] + 1,
            }
            await self._call_callbacks(task_id, "on_failed", task_info, e)
            logger.error(f"Task {task_id} failed: {e}")
        finally:
            self.metrics = {
                **self.metrics,
                "active_tasks": self.metrics["active_tasks"] - 1,
            }
            self.metrics = {
                **self.metrics,
                "current_queue_size": self.pending_queue.qsize(),
            }
            running_tasks = {
                k: v for k, v in running_tasks.items() if k != "task_id, None"
            }

    async def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """작업 상태 조회"""
        task_info = self.tasks.get(task_id)
        return task_info.status if task_info else None

    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """작업 정보 조회"""
        return self.tasks.get(task_id)

    async def get_result(self, task_id: str, timeout=None) -> Result[Any, str]:
        """
        작업 결과 조회

        Args:
            task_id: 작업 ID
            timeout: 대기 타임아웃 (초)

        Returns:
            Result: 작업 결과 또는 오류
        """
        task_info = self.tasks.get(task_id)
        if not task_info:
            return Failure(f"Task {task_id} not found")
        if task_info.is_finished:
            if task_info.status == TaskStatus.COMPLETED:
                return Success(task_info.result)
            else:
                return Failure(
                    task_info.error_message
                    or f"Task {task_id} {task_info.status.value}"
                )
        start_time = time.time()
        while not task_info.is_finished:
            if timeout and time.time() - start_time > timeout:
                return Failure(f"Timeout waiting for task {task_id} result")
            await asyncio.sleep(0.1)
        if task_info.status == TaskStatus.COMPLETED:
            return Success(task_info.result)
        else:
            return Failure(
                task_info.error_message or f"Task {task_id} {task_info.status.value}"
            )

    async def cancel_task(self, task_id: str) -> bool:
        """
        작업 취소

        Args:
            task_id: 작업 ID

        Returns:
            bool: 취소 성공 여부
        """
        task_info = self.tasks.get(task_id)
        if not task_info:
            return False
        if task_info.is_finished:
            return False
        if task_id in self.running_tasks:
            running_task = self.running_tasks[task_id]
            running_task.cancel()
        task_info.status = TaskStatus.CANCELLED
        task_info.completed_at = datetime.now()
        return True

    async def wait_for_completion(
        self, task_ids: List[str], timeout=None
    ) -> Dict[str, Result]:
        """
        여러 작업의 완료를 기다림

        Args:
            task_ids: 작업 ID 목록
            timeout: 대기 타임아웃 (초)

        Returns:
            Dict[str, Result]: 작업별 결과
        """
        results = {}

        async def get_task_result(task_id: str) -> tuple[str, Result]:
            result = await self.get_result(task_id, timeout)
            return (task_id, result)

        tasks = [get_task_result(task_id) for task_id in task_ids]
        try:
            if timeout:
                completed_results = await asyncio.wait_for(
                    asyncio.gather(*tasks), timeout=timeout
                )
            else:
                completed_results = await asyncio.gather(*tasks)
            for task_id, result in completed_results:
                results[task_id] = {task_id: result}
        except asyncio.TimeoutError:
            for task_id in task_ids:
                if task_id not in results:
                    results = {
                        **results,
                        task_id: {
                            task_id: Failure(f"Timeout waiting for task {task_id}")
                        },
                    }
        return results

    def register_callback(self, task_id: str, callback: TaskCallback) -> None:
        """작업별 콜백 등록"""
        if task_id not in self.callbacks:
            self.callbacks = {**self.callbacks, task_id: []}
        self.callbacks[task_id] = callbacks[task_id] + [callback]

    def register_global_callback(self, callback: TaskCallback) -> None:
        """전역 콜백 등록"""
        self.global_callbacks = self.global_callbacks + [callback]

    async def _call_callbacks(self, task_id: str, method_name: str, *args) -> None:
        """콜백 호출"""
        if task_id in self.callbacks:
            for callback in self.callbacks[task_id]:
                try:
                    method = getattr(callback, method_name)
                    await method(*args)
                except Exception as e:
                    logger.error(f"Callback error for task {task_id}: {e}")
        for callback in self.global_callbacks:
            try:
                method = getattr(callback, method_name)
                await method(*args)
            except Exception as e:
                logger.error(f"Global callback error for task {task_id}: {e}")

    async def _cleanup_loop(self) -> None:
        """주기적 정리 루프"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_completed_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _cleanup_completed_tasks(self) -> None:
        """완료된 작업 정리"""
        if not self.config.enable_result_caching:
            return
        current_time = datetime.now()
        expired_tasks = []
        for task_id, task_info in self.tasks.items():
            if (
                task_info.is_finished
                and task_info.completed_at
                and (
                    (current_time - task_info.completed_at).total_seconds()
                    > self.config.result_cache_ttl
                )
            ):
                expired_tasks = expired_tasks + [task_id]
        for task_id in expired_tasks:
            del self.tasks[task_id]
            callbacks = {k: v for k, v in callbacks.items() if k != "task_id, None"}
        if expired_tasks:
            logger.debug(f"Cleaned up {len(expired_tasks)} expired tasks")

    async def _metrics_loop(self) -> None:
        """메트릭 수집 루프"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.metrics_interval)
                await self._update_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics loop error: {e}")

    async def _update_metrics(self) -> None:
        """메트릭 업데이트"""
        completed_tasks = [
            task
            for task in self.tasks.values()
            if task.status == TaskStatus.COMPLETED and task.execution_time
        ]
        if completed_tasks:
            total_execution_time = sum(
                (task.execution_time for task in completed_tasks)
            )
            self.metrics = {
                **self.metrics,
                "average_execution_time": total_execution_time / len(completed_tasks),
            }
        self.metrics = {
            **self.metrics,
            "current_queue_size": self.pending_queue.qsize(),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 조회"""
        return self.metrics.copy()

    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskInfo]:
        """상태별 작업 목록 조회"""
        return [task for task in self.tasks.values() if task.status == status]

    def get_tasks_by_tag(self, tag: str) -> List[TaskInfo]:
        """태그별 작업 목록 조회"""
        return [task for task in self.tasks.values() if tag in task.tags]


_default_task_manager = None


def get_default_task_manager() -> AsyncTaskManager:
    """기본 작업 매니저 조회"""
    # global _default_task_manager - removed for functional programming
    if _default_task_manager is None:
        _default_task_manager = AsyncTaskManager()
    return _default_task_manager


def create_task_manager(config: TaskManagerConfig = None) -> AsyncTaskManager:
    """새 작업 매니저 생성"""
    return AsyncTaskManager(config or TaskManagerConfig())


async def submit_task(func: Callable, *args, **kwargs) -> str:
    """기본 매니저에 작업 제출"""
    manager = get_default_task_manager()
    return await manager.submit(func, *args, **kwargs)


async def get_task_result(task_id: str, timeout=None) -> Result[Any, str]:
    """기본 매니저에서 작업 결과 조회"""
    manager = get_default_task_manager()
    return await manager.get_result(task_id, timeout)


if __name__ == "__main__":

    async def example_usage():
        """사용 예제"""
        print("🧪 AsyncTaskManager Example")
        config = TaskManagerConfig(max_workers=5, enable_detailed_logging=True)
        manager = AsyncTaskManager(config)

        async def async_task(name: str, delay: float) -> str:
            await asyncio.sleep(delay)
            return f"Task {name} completed after {delay}s"

        def sync_task(name: str, value: int) -> int:
            time.sleep(0.1)
            return value * 2

        task1_id = await manager.submit(
            async_task, "async1", 1.0, priority=TaskPriority.HIGH
        )
        task2_id = await manager.submit(
            sync_task, "sync1", 42, priority=TaskPriority.NORMAL
        )
        task3_id = await manager.submit(
            async_task, "async2", 0.5, priority=TaskPriority.CRITICAL
        )
        print(f"Submitted tasks: {task1_id[:8]}, {task2_id[:8]}, {task3_id[:8]}")
        results = await manager.wait_for_completion(
            [task1_id, task2_id, task3_id], timeout=5.0
        )
        for task_id, result in results.items():
            if result.is_success():
                print(f"Task {task_id[:8]}: {result.value}")
            else:
                print(f"Task {task_id[:8]} failed: {result.error}")
        metrics = manager.get_metrics()
        print(f"Metrics: {metrics}")
        await manager.stop()
        print("Example completed!")

    asyncio.run(example_usage())
