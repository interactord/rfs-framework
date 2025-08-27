"""
Task Decorators for Async Task Management

작업 데코레이터 - 비동기 작업 선언적 관리
"""

import asyncio
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, List, Optional, Union

from ..hof.async_hof import async_retry, async_timeout

# Import from HOF library
from ..hof.decorators import memoize as hof_memoize
from ..hof.decorators import rate_limit as hof_rate_limit
from ..hof.decorators import retry as hof_retry
from .base import BackoffStrategy, RetryPolicy, TaskChain, TaskGroup, TaskPriority
from .manager import get_task_manager
from .scheduler import CronSchedule, IntervalSchedule, get_scheduler

logger = logging.getLogger(__name__)


def async_task(
    name=None,
    priority: TaskPriority = TaskPriority.NORMAL,
    retry_policy=None,
    timeout=None,
    tags: Optional[List[str]] = None,
):
    """
    비동기 작업 데코레이터

    Usage:
        @async_task(name="process_data", priority=TaskPriority.HIGH)
        async def process_data(data: dict):
            # 작업 처리
            return result

    Args:
        name: 작업 이름
        priority: 우선순위
        retry_policy: 재시도 정책
        timeout: 타임아웃
        tags: 태그
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            manager = await get_task_manager()
            task_id = await manager.submit(
                func,
                *args,
                name=name or func.__name__,
                priority=priority,
                retry_policy=retry_policy,
                timeout=timeout,
                tags=tags,
                **kwargs,
            )
            return task_id

        wrapper.original = func
        wrapper.is_async_task = True
        return wrapper

    return decorator


def background_task(func: Callable) -> Callable:
    """
    백그라운드 작업 데코레이터

    Usage:
        @background_task
        def cleanup_old_files():
            # 정리 작업
            pass
    """
    return async_task(
        name=f"background_{func.__name__}", priority=TaskPriority.BACKGROUND
    )(func)


def scheduled_task(
    cron=None,
    interval=None,
    start_time=None,
    **kwargs,
):
    """
    스케줄된 작업 데코레이터

    Usage:
        @scheduled_task(cron="0 * * * *")  # 매시간
        async def hourly_report():
            pass

        @scheduled_task(interval=timedelta(minutes=30))
        async def periodic_sync():
            pass

    Args:
        cron: Cron 표현식
        interval: 반복 간격
        start_time: 시작 시간
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            scheduler = await get_scheduler()
            if cron:
                schedule = CronSchedule(cron)
            elif interval:
                schedule = IntervalSchedule(interval)
            else:
                raise ValueError("Either cron or interval must be specified")
            task_id = await scheduler.schedule(
                func, schedule, name=kwargs.get("name", func.__name__), **kwargs
            )
            return task_id

        # Note: actual scheduling should be done when the scheduler is started
        wrapper.schedule_info = {"schedule": None, "start_time": start_time}
        if cron:
            wrapper.schedule_info["schedule"] = CronSchedule(cron)
        elif interval:
            wrapper.schedule_info["schedule"] = IntervalSchedule(interval)
        return wrapper

    return decorator


def retry_task(
    max_attempts=3,
    delay: timedelta = timedelta(seconds=1),
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    retry_on: Optional[List[type[Exception]]] = None,
):
    """
    재시도 작업 데코레이터

    Usage:
        @retry_task(max_attempts=5, delay=timedelta(seconds=2))
        async def unreliable_api_call():
            # API 호출
            pass

    Args:
        max_attempts: 최대 재시도 횟수
        delay: 재시도 지연
        backoff: 백오프 전략
        retry_on: 재시도할 예외 타입
    """
    retry_policy = RetryPolicy(
        max_attempts=max_attempts,
        delay=delay,
        backoff_strategy=backoff,
        retry_on=retry_on or [],
    )

    def decorator(func: Callable) -> Callable:
        return async_task(retry_policy=retry_policy)(func)

    return decorator


def timeout_task(seconds: int):
    """
    타임아웃 작업 데코레이터

    Usage:
        @timeout_task(30)  # 30초 타임아웃
        async def long_running_task():
            pass
    """

    def decorator(func: Callable) -> Callable:
        return async_task(timeout=timedelta(seconds=seconds))(func)

    return decorator


def priority_task(priority: TaskPriority):
    """
    우선순위 작업 데코레이터

    Usage:
        @priority_task(TaskPriority.CRITICAL)
        async def critical_operation():
            pass
    """

    def decorator(func: Callable) -> Callable:
        return async_task(priority=priority)(func)

    return decorator


def chain_tasks(*funcs: Callable):
    """
    작업 체인 생성

    Usage:
        @chain_tasks(fetch_data, process_data, save_result)
        async def data_pipeline():
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            from .base import CallableTask, TaskChain

            tasks = [CallableTask(f) for f in funcs]
            chain = TaskChain(tasks, name=func.__name__)
            context = kwargs.get("context", {})
            results = await chain.execute(context)
            return results

        wrapper.is_chain = True
        wrapper.chain_tasks = funcs
        return wrapper

    if len(funcs) == 1 and callable(funcs[0]):
        return decorator(funcs[0])
    return decorator


def parallel_tasks(*funcs: Callable, fail_fast=False):
    """
    병렬 작업 그룹 생성

    Usage:
        @parallel_tasks(task1, task2, task3, fail_fast=True)
        async def parallel_execution():
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            from .base import CallableTask

            tasks = [CallableTask(f) for f in funcs]
            group = TaskGroup(tasks, name=func.__name__, fail_fast=fail_fast)
            context = kwargs.get("context", {})
            results = await group.execute(context)
            return results

        wrapper.is_group = True
        wrapper.group_tasks = funcs
        return wrapper

    return decorator


def depends_on(*task_ids: str):
    """
    의존성 작업 데코레이터

    Usage:
        @depends_on("task_123", "task_456")
        async def dependent_task():
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            manager = await get_task_manager()
            task_id = await manager.submit(
                func, *args, depends_on=list(task_ids), **kwargs
            )
            return task_id

        wrapper.dependencies = task_ids
        return wrapper

    return decorator


def task_callback(
    on_complete=None,
    on_error=None,
    on_cancel=None,
):
    """
    작업 콜백 데코레이터

    Usage:
        def handle_complete(result):
            print(f"Task completed: {result}")

        def handle_error(error):
            print(f"Task failed: {error}")

        @task_callback(on_complete=handle_complete, on_error=handle_error)
        async def monitored_task():
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            manager = await get_task_manager()
            from .base import TaskCallback as BaseCallback

            class CustomCallback(BaseCallback):

                def on_start(self, metadata):
                    pass

                def on_complete(self, result):
                    if on_complete:
                        on_complete(result)

                def on_error(self, metadata, error):
                    if on_error:
                        on_error(error)

                def on_cancel(self, metadata):
                    if on_cancel:
                        on_cancel(metadata)

                def on_timeout(self, metadata):
                    if on_error:
                        on_error(TimeoutError("Task timed out"))

                def on_retry(self, metadata, attempt):
                    pass

            callback = CustomCallback()
            manager.add_callback(callback)
            task_id = await manager.submit(func, *args, **kwargs)
            return task_id

        return wrapper

    return decorator


def memoized_task(ttl=None):
    """
    메모이제이션 작업 데코레이터

    결과를 캐시하여 동일한 입력에 대해 재실행하지 않음

    Usage:
        @memoized_task(ttl=timedelta(hours=1))
        async def expensive_computation(x, y):
            return x ** y
    """
    cache = {}
    cache_times = {}

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = (args, tuple(sorted(kwargs.items())))
            if cache_key in cache:
                if ttl:
                    cached_time = cache_times.get(cache_key)
                    if cached_time and datetime.now() - cached_time < ttl:
                        logger.debug(f"Cache hit for {func.__name__}")
                        return cache[cache_key]
                else:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cache[cache_key]
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            cache[cache_key] = result
            if ttl:
                cache_times[cache_key] = datetime.now()
            return result

        wrapper._cache = cache
        wrapper._cache_times = cache_times
        return wrapper

    return decorator


def rate_limited(max_calls: int, period: timedelta):
    """
    레이트 리미팅 작업 데코레이터

    Usage:
        @rate_limited(max_calls=10, period=timedelta(minutes=1))
        async def api_call():
            pass
    """
    calls = []

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        async def wrapper(*args, **kwargs):
            now = datetime.now()
            nonlocal calls
            calls = [call_time for call_time in calls if now - call_time < period]
            if len(calls) >= max_calls:
                wait_time = period - (now - calls[0])
                logger.warning(f"Rate limit exceeded, waiting {wait_time}")
                await asyncio.sleep(wait_time.total_seconds())
                calls = [call_time for call_time in calls if now - call_time < period]
            calls = calls + [now]
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator
