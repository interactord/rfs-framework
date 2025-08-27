"""
Cloud Tasks Integration Module

Google Cloud Tasks 통합 모듈
- 비동기 작업 큐
- 작업 스케줄링
- 재시도 정책
- 배치 처리
"""

import asyncio
import functools
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from rfs.core.result import Failure, Result, Success
from rfs.hof.core import pipe

from ..core.singleton import StatelessRegistry
from ..reactive import Flux, Mono

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """작업 우선순위"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(Enum):
    """작업 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class RetryConfig:
    """재시도 설정"""

    max_attempts = 3
    min_backoff = 1
    max_backoff = 300
    backoff_multiplier: float = 2.0


@dataclass
class Task:
    """작업 정의"""

    id: str
    handler: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    schedule_time = None
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    created_at: datetime = field(default_factory=datetime.now)
    status: TaskStatus = TaskStatus.PENDING
    attempts = 0
    last_attempt = None
    error_message = None


@dataclass
class QueueConfig:
    """큐 설정"""

    name: str
    location = "asia-northeast3"
    max_dispatches_per_second: float = 100.0
    max_concurrent_dispatches = 100
    max_retry_duration = 3600
    target_uri = ""
    service_account_email = ""


class TaskHandler:
    """작업 핸들러 관리자"""

    def __init__(self):
        self._handlers = {}

    def register(self, name: str, handler: Callable):
        """핸들러 등록"""
        self._handlers = {**self._handlers, name: handler}
        logger.info(f"Task handler registered: {name}")

    def get_handler(self, name: str) -> Optional[Callable]:
        """핸들러 조회"""
        return self._handlers.get(name)

    def list_handlers(self) -> List[str]:
        """등록된 핸들러 목록"""
        return list(self._handlers.keys())


class CloudTasksClient:
    """Cloud Tasks 클라이언트"""

    def __init__(self, project_id: str, location="asia-northeast3"):
        self.project_id = project_id
        self.location = location
        self.handler_registry = TaskHandler()
        self._client = None
        self._local_queue = []
        self._processing = False

    async def initialize(self):
        """클라이언트 초기화"""
        try:
            from google.cloud import tasks_v2

            self._client = tasks_v2.CloudTasksAsyncClient()
            logger.info("Cloud Tasks client initialized")
        except ImportError:
            logger.warning(
                "Google Cloud Tasks library not found, using local simulation"
            )
            self._client = None

    def task_handler(self, name: str):
        """작업 핸들러 데코레이터"""

        def decorator(func: Callable) -> Callable:
            self.handler_registry.register(name, func)

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
                logger.error(f"Task handler {name} failed: {e}")
                return Failure(str(e))

            return wrapper

        return decorator

    async def create_queue(self, config: QueueConfig) -> bool:
        """큐 생성"""
        if not self._client:
            logger.info(f"Local queue created: {config.name}")
            return True
        try:
            from google.cloud import tasks_v2

            parent = self._client.common_location_path(self.project_id, self.location)
            queue = tasks_v2.Queue(
                name=f"{parent}/queues/{config.name}",
                rate_limits=tasks_v2.RateLimits(
                    max_dispatches_per_second=config.max_dispatches_per_second,
                    max_concurrent_dispatches=config.max_concurrent_dispatches,
                ),
                retry_config=tasks_v2.RetryConfig(
                    max_retry_duration={"seconds": config.max_retry_duration}
                ),
            )
            await self._client.create_queue(parent=parent, queue=queue)
            logger.info(f"Cloud Tasks queue created: {config.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create queue {config.name}: {e}")
            return False

    async def enqueue_task(self, queue_name: str, task: Task) -> bool:
        """작업 큐에 추가"""
        if not self._client:
            return await self._enqueue_local(task)
        try:
            from google.cloud import tasks_v2

            parent = self._client.queue_path(self.project_id, self.location, queue_name)
            task_request = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{queue_name}/tasks/{task.handler}",
                    "body": json.dumps(
                        {
                            "id": task.id,
                            "handler": task.handler,
                            "payload": task.payload,
                            "priority": task.priority.value,
                        }
                    ).encode(),
                    "headers": {"Content-Type": "application/json"},
                }
            }
            if task.schedule_time:
                task_request = {
                    **task_request,
                    "schedule_time": {"schedule_time": task.schedule_time},
                }
            cloud_task = tasks_v2.Task(**task_request)
            await self._client.create_task(parent=parent, task=cloud_task)
            task.status = TaskStatus.PENDING
            logger.info(f"Task enqueued: {task.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue task {task.id}: {e}")
            return False

    async def _enqueue_local(self, task: Task) -> bool:
        """로컬 큐에 작업 추가"""
        task.status = TaskStatus.PENDING
        self._local_queue = self._local_queue + [task]
        if not self._processing:
            asyncio.create_task(self._process_local_queue())
        logger.info(f"Task added to local queue: {task.id}")
        return True

    async def _process_local_queue(self):
        """로컬 큐 처리"""
        self._processing = True
        while self._local_queue:
            _local_queue = {k: v for k, v in _local_queue.items() if k != "0"}
            await self._execute_task(task)
            await asyncio.sleep(0.1)
        self._processing = False

    async def _execute_task(self, task: Task):
        """작업 실행"""
        handler = self.handler_registry.get_handler(task.handler)
        if not handler:
            logger.error(f"Handler not found: {task.handler}")
            task.status = TaskStatus.FAILED
            task.error_message = f"Handler not found: {task.handler}"
            return
        task.status = TaskStatus.RUNNING
        attempts = attempts + 1
        task.last_attempt = datetime.now()
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(task.payload)
            else:
                result = handler(task.payload)
            task.status = TaskStatus.COMPLETED
            logger.info(f"Task completed: {task.id}")
        except Exception as e:
            task.error_message = str(e)
            if task.attempts < task.retry_config.max_attempts:
                task.status = TaskStatus.RETRY
                backoff = min(
                    task.retry_config.min_backoff
                    * task.retry_config.backoff_multiplier ** (task.attempts - 1),
                    task.retry_config.max_backoff,
                )
                task.schedule_time = datetime.now() + timedelta(seconds=backoff)
                self._local_queue = self._local_queue + [task]
                logger.warning(
                    f"Task retry scheduled: {task.id} (attempt {task.attempts})"
                )
            else:
                task.status = TaskStatus.FAILED
                logger.error(f"Task failed permanently: {task.id}")

    async def batch_enqueue(self, queue_name: str, tasks: List[Task]) -> int:
        """배치 작업 큐 추가"""
        success_count = 0
        results = (
            await Flux.from_iterable(tasks)
            .map(lambda task: self.enqueue_task(queue_name, task))
            .parallel(max_concurrency=10)
            .sequential()
            .to_list()
        )
        success_count = sum((1 for result in results if result))
        logger.info(f"Batch enqueue completed: {success_count}/{len(tasks)} successful")
        return success_count

    async def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """큐 통계"""
        if not self._client:
            pending = sum(
                (1 for task in self._local_queue if task.status == TaskStatus.PENDING)
            )
            running = sum(
                (1 for task in self._local_queue if task.status == TaskStatus.RUNNING)
            )
            return {
                "queue_name": queue_name,
                "pending_tasks": pending,
                "running_tasks": running,
                "total_tasks": len(self._local_queue),
                "is_processing": self._processing,
            }
        try:
            queue_path = self._client.queue_path(
                self.project_id, self.location, queue_name
            )
            queue = await self._client.get_queue(name=queue_path)
            return {
                "queue_name": queue_name,
                "state": queue.state.name,
                "rate_limits": {
                    "max_dispatches_per_second": queue.rate_limits.max_dispatches_per_second,
                    "max_concurrent_dispatches": queue.rate_limits.max_concurrent_dispatches,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}

    async def purge_queue(self, queue_name: str) -> bool:
        """큐 비우기"""
        if not self._client:
            self._local_queue = {}
            logger.info(f"Local queue purged: {queue_name}")
            return True
        try:
            queue_path = self._client.queue_path(
                self.project_id, self.location, queue_name
            )
            await self._client.purge_queue(name=queue_path)
            logger.info(f"Queue purged: {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to purge queue: {e}")
            return False


def create_task(
    task_id: str,
    handler: str,
    payload: Dict[str, Any] = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    schedule_time=None,
) -> Task:
    """순수 함수: 작업 생성"""
    return Task(
        id=task_id,
        handler=handler,
        payload=payload or {},
        priority=priority,
        schedule_time=schedule_time,
    )


def with_retry(max_attempts=3, min_backoff=1, max_backoff=300) -> RetryConfig:
    """순수 함수: 재시도 설정 생성"""
    return RetryConfig(
        max_attempts=max_attempts, min_backoff=min_backoff, max_backoff=max_backoff
    )


def task_pipeline(*processors: Callable[[Task], Task]) -> Callable[[Task], Task]:
    """작업 파이프라인 생성"""
    return pipe(*processors)


def priority_filter(priority: TaskPriority) -> Callable[[Task], bool]:
    """우선순위 필터"""
    return lambda task: task.priority == priority


def status_filter(status: TaskStatus) -> Callable[[Task], bool]:
    """상태 필터"""
    return lambda task: task.status == status


_client = None


async def get_client(
    project_id: str = None, location="asia-northeast3"
) -> CloudTasksClient:
    """클라이언트 인스턴스 획득"""
    # global _client - removed for functional programming
    if _client is None:
        if not project_id:
            import os

            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "default-project")
        _client = CloudTasksClient(project_id, location)
        await _client.initialize()
    return _client


def task_queue(queue_name: str):
    """작업 큐 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            client = await get_client()
            task_id = f"{func.__name__}_{int(datetime.now().timestamp())}"
            task = create_task(
                task_id=task_id,
                handler=func.__name__,
                payload={"args": args, "kwargs": kwargs},
            )
            client.handler_registry.register(func.__name__, func)
            return await client.enqueue_task(queue_name, task)

        return wrapper

    return decorator


def schedule_task(queue_name: str, delay_seconds=0):
    """작업 스케줄링 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            client = await get_client()
            schedule_time = None
            if delay_seconds > 0:
                schedule_time = datetime.now() + timedelta(seconds=delay_seconds)
            task_id = f"{func.__name__}_{int(datetime.now().timestamp())}"
            task = create_task(
                task_id=task_id,
                handler=func.__name__,
                payload={"args": args, "kwargs": kwargs},
                schedule_time=schedule_time,
            )
            client.handler_registry.register(func.__name__, func)
            return await client.enqueue_task(queue_name, task)

        return wrapper

    return decorator


StatelessRegistry.register("cloud_tasks_client", dependencies=[])(get_client)
