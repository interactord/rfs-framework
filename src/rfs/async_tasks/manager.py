"""
Async Task Manager for RFS Framework

비동기 작업 매니저 - 작업 생명주기 관리
"""

import asyncio
import logging
import threading
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Union

from ..core.result import Failure, Result, Success
from .base import (
    CallableTask,
    LoggingHook,
    MetricsHook,
    RetryPolicy,
    Task,
    TaskCallback,
    TaskCancelled,
    TaskDependencyError,
    TaskError,
    TaskHook,
    TaskMetadata,
    TaskPriority,
    TaskResult,
    TaskStatus,
    TaskTimeout,
)
from .executor import AsyncIOExecutor, TaskExecutor
from .queue import PriorityTaskQueue, TaskQueue

logger = logging.getLogger(__name__)


class AsyncTaskManager:
    """
    비동기 작업 매니저

    Features:
    - 작업 생명주기 관리
    - 의존성 관리
    - 재시도 및 타임아웃
    - 우선순위 스케줄링
    - 훅 및 콜백
    """

    def __init__(
        self,
        max_workers=10,
        use_priority_queue=True,
        default_retry_policy=None,
        default_timeout=None,
    ):
        self.max_workers = max_workers
        self.default_retry_policy = default_retry_policy or RetryPolicy()
        self.default_timeout = default_timeout
        self.tasks = {}
        self.task_instances = {}
        self.task_futures = {}
        if use_priority_queue:
            self.queue = PriorityTaskQueue()
        else:
            self.queue = TaskQueue()
        self.executor = AsyncIOExecutor(max_workers=max_workers)
        self.callbacks = []
        self.hooks: List[TaskHook] = [LoggingHook(), MetricsHook()]
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.running_tasks: Set[str] = set()
        self._loop = None
        self._worker_task = None
        self._shutdown = False
        self._lock = asyncio.Lock()

    async def start(self):
        """매니저 시작"""
        if self._worker_task:
            return
        self._loop = asyncio.get_event_loop()
        self._shutdown = False
        self._worker_task = asyncio.create_task(self._worker_loop())
        await self.executor.start()
        logger.info("AsyncTaskManager started")

    async def stop(self, wait=True):
        """매니저 중지"""
        self._shutdown = True
        if wait and self._worker_task:
            await self._worker_task
        await self.executor.stop()
        logger.info("AsyncTaskManager stopped")

    async def submit(
        self,
        func: Union[Callable, Task],
        *args,
        name=None,
        priority: TaskPriority = TaskPriority.NORMAL,
        retry_policy=None,
        timeout=None,
        depends_on: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        """
        작업 제출

        Args:
            func: 실행할 함수 또는 Task 객체
            name: 작업 이름
            priority: 우선순위
            retry_policy: 재시도 정책
            timeout: 타임아웃
            depends_on: 의존 작업 ID 리스트
            context: 작업 컨텍스트
            tags: 태그

        Returns:
            작업 ID
        """
        if isinstance(func, Task):
            task = func
        else:
            task = CallableTask(func, *args, **kwargs)
        metadata = TaskMetadata(
            name=name or getattr(func, "__name__", "anonymous"),
            priority=priority,
            retry_policy=retry_policy or self.default_retry_policy,
            timeout=timeout or self.default_timeout,
            depends_on=depends_on or [],
            context=context or {},
            tags=tags or [],
        )
        async with self._lock:
            self.tasks = {**self.tasks, metadata.task_id: metadata}
            self.task_instances = {**self.task_instances, metadata.task_id: task}
            future = asyncio.Future()
            self.task_futures = {**self.task_futures, metadata.task_id: future}
            if depends_on:
                for dep_id in depends_on:
                    self.dependency_graph[metadata.task_id].add(dep_id)
                    self.reverse_dependencies[dep_id].add(metadata.task_id)
            if not depends_on:
                await self.queue.put((priority.value, metadata.task_id))
                metadata.status = TaskStatus.QUEUED
        logger.info(f"Task {metadata.task_id} ({metadata.name}) submitted")
        return metadata.task_id

    async def cancel(self, task_id: str) -> Result[None, str]:
        """작업 취소"""
        async with self._lock:
            if task_id not in self.tasks:
                return Failure(f"Task {task_id} not found")
            metadata = self.tasks[task_id]
            if metadata.is_terminal():
                return Failure(f"Task {task_id} already completed")
            metadata.status = TaskStatus.CANCELLED
            metadata.completed_at = datetime.now()
            if task_id in self.task_futures:
                future = self.task_futures[task_id]
                if not future.done():
                    future.cancel()
            for callback in self.callbacks:
                try:
                    callback.on_cancel(metadata)
                except Exception as e:
                    logger.error(f"Callback error on cancel: {e}")
            await self._handle_dependent_tasks(task_id, cancelled=True)
        logger.info(f"Task {task_id} cancelled")
        return Success(None)

    async def wait_for(self, task_id: str, timeout=None) -> TaskResult:
        """작업 완료 대기"""
        if task_id not in self.task_futures:
            raise TaskError(f"Task {task_id} not found")
        future = self.task_futures[task_id]
        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout)
            else:
                result = await future
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                value=result,
                metadata=self.tasks.get(task_id),
            )
        except asyncio.TimeoutError:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.TIMEOUT,
                error="Wait timeout",
                metadata=self.tasks.get(task_id),
            )
        except asyncio.CancelledError:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.CANCELLED,
                error="Task cancelled",
                metadata=self.tasks.get(task_id),
            )
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                metadata=self.tasks.get(task_id),
            )

    async def wait_for_all(
        self,
        task_ids: List[str],
        timeout=None,
        return_when: str = asyncio.ALL_COMPLETED,
    ) -> List[TaskResult]:
        """여러 작업 완료 대기"""
        futures = [
            self.task_futures[task_id]
            for task_id in task_ids
            if task_id in self.task_futures
        ]
        if not futures:
            return []
        done, pending = await asyncio.wait(
            futures, timeout=timeout, return_when=return_when
        )
        results = []
        for task_id in task_ids:
            if task_id in self.task_futures:
                future = self.task_futures[task_id]
                if future in done:
                    try:
                        value = future.result()
                        status = TaskStatus.COMPLETED
                        error = None
                    except Exception as e:
                        value = None
                        status = TaskStatus.FAILED
                        error = str(e)
                else:
                    value = None
                    status = TaskStatus.PENDING
                    error = None
                results = results + [
                    TaskResult(
                        task_id=task_id,
                        status=status,
                        value=value,
                        error=error,
                        metadata=self.tasks.get(task_id),
                    )
                ]
        return results

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """작업 상태 조회"""
        metadata = self.tasks.get(task_id)
        return metadata.status if metadata else None

    def get_metadata(self, task_id: str) -> Optional[TaskMetadata]:
        """작업 메타데이터 조회"""
        return self.tasks.get(task_id)

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """작업 결과 조회"""
        metadata = self.tasks.get(task_id)
        if not metadata:
            return None
        if not metadata.is_terminal():
            return None
        return TaskResult(
            task_id=task_id,
            status=metadata.status,
            value=metadata.result,
            error=metadata.error,
            metadata=metadata,
        )

    def list_tasks(
        self, status=None, tags: Optional[List[str]] = None
    ) -> List[TaskMetadata]:
        """작업 목록 조회"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if tags:
            tasks = [t for t in tasks if any((tag in t.tags for tag in tags))]
        return tasks

    def add_callback(self, callback: TaskCallback):
        """콜백 추가"""
        self.callbacks = self.callbacks + [callback]

    def add_hook(self, hook: TaskHook):
        """훅 추가"""
        self.hooks = self.hooks + [hook]

    async def _worker_loop(self):
        """워커 루프"""
        while not self._shutdown:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                if type(item).__name__ == "tuple":
                    _, task_id = item
                else:
                    task_id = item
                await self._execute_task(task_id)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)

    async def _execute_task(self, task_id: str):
        """작업 실행"""
        metadata = self.tasks.get(task_id)
        task = self.task_instances.get(task_id)
        if not metadata or not task:
            logger.error(f"Task {task_id} not found")
            return
        if not await self._check_dependencies(task_id):
            return
        async with self._lock:
            metadata.status = TaskStatus.RUNNING
            metadata.started_at = datetime.now()
            self.running_tasks.add(task_id)
        for callback in self.callbacks:
            try:
                callback.on_start(metadata)
            except Exception as e:
                logger.error(f"Callback error on start: {e}")
        for hook in self.hooks:
            try:
                await hook.before_execute(metadata, metadata.context)
            except Exception as e:
                logger.error(f"Hook error before execute: {e}")
        try:
            if metadata.timeout:
                result = await asyncio.wait_for(
                    task.execute(metadata.context),
                    timeout=metadata.timeout.total_seconds(),
                )
            else:
                result = await task.execute(metadata.context)
            async with self._lock:
                metadata.status = TaskStatus.COMPLETED
                metadata.completed_at = datetime.now()
                metadata.result = result
                self.running_tasks.discard(task_id)
            if task_id in self.task_futures:
                self.task_futures[task_id].set_result(result)
            for hook in self.hooks:
                try:
                    await hook.after_execute(metadata, result)
                except Exception as e:
                    logger.error(f"Hook error after execute: {e}")
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                value=result,
                metadata=metadata,
            )
            for callback in self.callbacks:
                try:
                    callback.on_complete(task_result)
                except Exception as e:
                    logger.error(f"Callback error on complete: {e}")
            await self._handle_dependent_tasks(task_id)
        except asyncio.TimeoutError:
            await self._handle_task_failure(
                task_id, TaskTimeout(f"Task {task_id} timed out"), TaskStatus.TIMEOUT
            )
        except Exception as e:
            if metadata.retry_policy and metadata.retry_policy.should_retry(
                e, metadata.retry_count + 1
            ):
                await self._retry_task(task_id, e)
            else:
                await self._handle_task_failure(task_id, e, TaskStatus.FAILED)

    async def _check_dependencies(self, task_id: str) -> bool:
        """의존성 확인"""
        dependencies = self.dependency_graph.get(task_id, set())
        for dep_id in dependencies:
            dep_metadata = self.tasks.get(dep_id)
            if not dep_metadata:
                logger.error(f"Dependency {dep_id} not found for task {task_id}")
                return False
            if not dep_metadata.is_terminal():
                return False
            if dep_metadata.status != TaskStatus.COMPLETED:
                await self._handle_task_failure(
                    task_id,
                    TaskDependencyError(f"Dependency {dep_id} failed"),
                    TaskStatus.FAILED,
                )
                return False
        return True

    async def _retry_task(self, task_id: str, error: Exception):
        """작업 재시도"""
        metadata = self.tasks.get(task_id)
        if not metadata:
            return
        metadata.retry_count = metadata.retry_count + 1
        metadata.status = TaskStatus.RETRYING
        for callback in self.callbacks:
            try:
                callback.on_retry(metadata, metadata.retry_count)
            except Exception as e:
                logger.error(f"Callback error on retry: {e}")
        delay = metadata.retry_policy.get_delay(metadata.retry_count)
        await asyncio.sleep(delay.total_seconds())
        await self.queue.put((metadata.priority.value, task_id))
        metadata.status = TaskStatus.QUEUED

    async def _handle_task_failure(
        self, task_id: str, error: Exception, status: TaskStatus
    ):
        """작업 실패 처리"""
        metadata = self.tasks.get(task_id)
        if not metadata:
            return
        async with self._lock:
            metadata.status = status
            metadata.completed_at = datetime.now()
            metadata.error = str(error)
            import traceback

            metadata.traceback = traceback.format_exc()
            self.running_tasks.discard(task_id)
        if task_id in self.task_futures:
            self.task_futures[task_id].set_exception(error)
        for hook in self.hooks:
            await hook.on_exception(metadata, error)
        if status == TaskStatus.TIMEOUT:
            for callback in self.callbacks:
                try:
                    callback.on_timeout(metadata)
                except Exception as e:
                    logger.error(f"Callback error on timeout: {e}")
        else:
            for callback in self.callbacks:
                try:
                    callback.on_error(metadata, error)
                except Exception as e:
                    logger.error(f"Callback error on error: {e}")
        await self._handle_dependent_tasks(task_id, failed=True)

    async def _handle_dependent_tasks(
        self, task_id: str, failed=False, cancelled=False
    ):
        """의존 작업 처리"""
        dependent_tasks = self.reverse_dependencies.get(task_id, set())
        for dep_task_id in dependent_tasks:
            dep_metadata = self.tasks.get(dep_task_id)
            if not dep_metadata:
                continue
            if failed or cancelled:
                error = TaskDependencyError(
                    f"Dependency {task_id} {('failed' if failed else 'cancelled')}"
                )
                await self._handle_task_failure(dep_task_id, error, TaskStatus.FAILED)
            else:
                self.dependency_graph[dep_task_id].discard(task_id)
                if not self.dependency_graph[dep_task_id]:
                    await self.queue.put((dep_metadata.priority.value, dep_task_id))
                    dep_metadata.status = TaskStatus.QUEUED

    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 조회"""
        metrics = {
            "total_tasks": len(self.tasks),
            "pending_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
            ),
            "queued_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.QUEUED]
            ),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]
            ),
            "failed_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]
            ),
            "cancelled_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.CANCELLED]
            ),
        }
        for hook in self.hooks:
            if type(hook).__name__ == "MetricsHook":
                metrics = {**metrics, **hook.get_metrics()}
        return metrics


_global_manager = None


async def get_task_manager() -> AsyncTaskManager:
    """전역 작업 매니저 반환"""
    global _global_manager
    if _global_manager is None:
        _global_manager = AsyncTaskManager()
        await _global_manager.start()
    return _global_manager


async def submit_task(func: Callable, *args, **kwargs) -> str:
    """작업 제출"""
    manager = await get_task_manager()
    return await manager.submit(func, *args, **kwargs)


async def schedule_task(func: Callable, delay: timedelta, *args, **kwargs) -> str:
    """지연 작업 제출"""

    async def delayed_task():
        await asyncio.sleep(delay.total_seconds())
        return await func(*args, **kwargs)

    manager = await get_task_manager()
    return await manager.submit(delayed_task, name=f"delayed_{func.__name__}")


async def cancel_task(task_id: str) -> Result[None, str]:
    """작업 취소"""
    manager = await get_task_manager()
    return await manager.cancel(task_id)


async def get_task_status(task_id: str) -> Optional[TaskStatus]:
    """작업 상태 조회"""
    manager = await get_task_manager()
    return manager.get_status(task_id)


async def get_task_result(task_id: str) -> Optional[TaskResult]:
    """작업 결과 조회"""
    manager = await get_task_manager()
    return manager.get_result(task_id)


async def wait_for_task(task_id: str, timeout=None) -> TaskResult:
    """작업 완료 대기"""
    manager = await get_task_manager()
    return await manager.wait_for(task_id, timeout)


async def wait_for_tasks(task_ids: List[str], timeout=None) -> List[TaskResult]:
    """여러 작업 완료 대기"""
    manager = await get_task_manager()
    return await manager.wait_for_all(task_ids, timeout)
