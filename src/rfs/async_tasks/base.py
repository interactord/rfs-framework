"""
Base Components for Async Task Management

비동기 작업 관리 기본 컴포넌트
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from ..core.result import Failure, Result, Success

T = TypeVar("T")


class TaskStatus(Enum):
    """작업 상태"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """작업 우선순위"""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4

    def __lt__(self, other):
        return self.value < other.value


class BackoffStrategy(Enum):
    """재시도 백오프 전략"""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    JITTER = "jitter"


@dataclass
class RetryPolicy:
    """재시도 정책"""

    max_attempts = 3
    delay: timedelta = timedelta(seconds=1)
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    max_delay: timedelta = timedelta(minutes=5)
    retry_on: List[type[Exception]] = field(default_factory=list)
    retry_condition: Optional[Callable[[Exception], bool]] = None

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """재시도 여부 판단"""
        if attempt >= self.max_attempts:
            return False
        if self.retry_on:
            if not any(
                (type(exception).__name__ == "exc_type" for exc_type in self.retry_on)
            ):
                return False
        if self.retry_condition:
            return self.retry_condition(exception)
        return True

    def get_delay(self, attempt: int) -> timedelta:
        """재시도 지연 시간 계산"""
        match self.backoff_strategy:
            case BackoffStrategy.FIXED:
                delay = self.delay
            case BackoffStrategy.LINEAR:
                delay = self.delay * attempt
            case BackoffStrategy.EXPONENTIAL:
                delay = self.delay * self.backoff_multiplier ** (attempt - 1)
            case _:
                import random

                base_delay = self.delay * self.backoff_multiplier ** (attempt - 1)
                jitter = random.uniform(0, base_delay.total_seconds() * 0.1)
                delay = base_delay + timedelta(seconds=jitter)
        if delay > self.max_delay:
            delay = self.max_delay
        return delay


@dataclass
class TaskMetadata:
    """작업 메타데이터"""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at = None
    started_at = None
    completed_at = None
    retry_count = 0
    retry_policy = None
    timeout = None
    depends_on: List[str] = field(default_factory=list)
    parent_id = None
    children_ids: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    result = None
    error = None
    traceback = None

    def duration(self) -> Optional[timedelta]:
        """실행 시간"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def is_terminal(self) -> bool:
        """종료 상태 확인"""
        return self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        ]

    def is_ready(self) -> bool:
        """실행 가능 상태 확인"""
        return self.status == TaskStatus.PENDING and (not self.depends_on)


@dataclass
class TaskResult(Generic[T]):
    """작업 결과"""

    task_id: str
    status: TaskStatus
    value = None
    error = None
    metadata = None

    def is_success(self) -> bool:
        """성공 여부"""
        return self.status == TaskStatus.COMPLETED

    def is_failure(self) -> bool:
        """실패 여부"""
        return self.status in [
            TaskStatus.FAILED,
            TaskStatus.TIMEOUT,
            TaskStatus.CANCELLED,
        ]

    def to_result(self) -> Result[T, str]:
        """Result 타입으로 변환"""
        if self.is_success():
            return Success(self.value)
        else:
            return Failure(self.error or f"Task failed with status: {self.status.name}")


class TaskCallback(ABC):
    """작업 콜백 인터페이스"""

    @abstractmethod
    def on_start(self, metadata: TaskMetadata):
        """작업 시작 시 호출되는 콜백

        Args:
            metadata: 작업 메타데이터
        """
        raise NotImplementedError

    @abstractmethod
    def on_complete(self, result: TaskResult):
        """작업 완료 시 호출되는 콜백

        Args:
            result: 작업 실행 결과
        """
        raise NotImplementedError

    @abstractmethod
    def on_error(self, metadata: TaskMetadata, error: Exception):
        """에러 발생 시 호출되는 콜백

        Args:
            metadata: 작업 메타데이터
            error: 발생한 예외
        """
        raise NotImplementedError

    @abstractmethod
    def on_cancel(self, metadata: TaskMetadata):
        """작업 취소 시 호출되는 콜백

        Args:
            metadata: 작업 메타데이터
        """
        raise NotImplementedError

    @abstractmethod
    def on_timeout(self, metadata: TaskMetadata):
        """타임아웃 시 호출되는 콜백

        Args:
            metadata: 작업 메타데이터
        """
        raise NotImplementedError

    @abstractmethod
    def on_retry(self, metadata: TaskMetadata, attempt: int):
        """재시도 시 호출되는 콜백

        Args:
            metadata: 작업 메타데이터
            attempt: 재시도 횟수
        """
        raise NotImplementedError


class TaskError(Exception):
    """작업 에러"""

    def __init__(self, message: str, task_id=None):
        super().__init__(message)
        self.task_id = task_id


class TaskTimeout(TaskError):
    """작업 타임아웃"""

    pass


class TaskCancelled(TaskError):
    """작업 취소"""

    pass


class TaskDependencyError(TaskError):
    """작업 의존성 에러"""

    pass


class Task(ABC, Generic[T]):
    """작업 인터페이스"""

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> T:
        """작업 실행 메서드

        Args:
            context: 작업 실행 컨텍스트

        Returns:
            작업 실행 결과
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> Result[None, str]:
        """작업 실행 전 검증

        Args:
            context: 작업 실행 컨텍스트

        Returns:
            Success(None) 또는 Failure(에러 메시지)
        """
        raise NotImplementedError

    @abstractmethod
    def cleanup(self, context: Dict[str, Any]):
        """작업 종료 후 정리

        Args:
            context: 작업 실행 컨텍스트
        """
        raise NotImplementedError


class CallableTask(Task[T]):
    """호출 가능 작업"""

    def __init__(self, func: Callable[..., T], *args, **kwargs):
        self.func = func
        self.args = args
        # kwargs 파라미터가 따로 전달된 경우 처리
        if "kwargs" in kwargs:
            self.kwargs = kwargs["kwargs"]
        else:
            self.kwargs = kwargs

    async def execute(self, context: Dict[str, Any]) -> T:
        """작업 실행"""
        import asyncio
        from functools import partial

        merged_kwargs = {**self.kwargs, **context}
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(*self.args, **merged_kwargs)
        else:
            loop = asyncio.get_event_loop()
            # functools.partial을 사용하여 kwargs를 올바르게 전달
            partial_func = partial(self.func, *self.args, **merged_kwargs)
            return await loop.run_in_executor(None, partial_func)

    def validate(self, context: Dict[str, Any]) -> Result[None, str]:
        """작업 검증"""
        return Success(None)

    def cleanup(self, context: Dict[str, Any]):
        """작업 정리"""
        pass


@dataclass
class TaskChain:
    """작업 체인"""

    tasks: List[Task]
    name = "chain"

    async def execute(self, context: Dict[str, Any]) -> List[Any]:
        """체인 실행"""
        results = []
        chain_context = context.copy()
        for i, task in enumerate(self.tasks):
            if results:
                chain_context = {
                    **chain_context,
                    "previous_result": {"previous_result": results[-1]},
                }
                chain_context = {
                    **chain_context,
                    "all_results": {"all_results": results},
                }
            result = await task.execute(chain_context)
            results = results + [result]
            if type(result).__name__ == "dict":
                chain_context = {**chain_context, **result}
        return results


@dataclass
class TaskGroup:
    """작업 그룹 (병렬 실행)"""

    tasks: List[Task]
    name = "group"
    fail_fast = False

    async def execute(self, context: Dict[str, Any]) -> List[Any]:
        """그룹 실행"""
        import asyncio

        coroutines = [task.execute(context.copy()) for task in self.tasks]
        if self.fail_fast:
            results = []
            tasks = [asyncio.create_task(coro) for coro in coroutines]
            try:
                for task in asyncio.as_completed(tasks):
                    result = await task
                    results = results + [result]
            except Exception as e:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                raise e
            return results
        else:
            return await asyncio.gather(*coroutines, return_exceptions=True)


class TaskHook(ABC):
    """작업 훅 인터페이스"""

    @abstractmethod
    async def before_execute(self, metadata: TaskMetadata, context: Dict[str, Any]):
        """작업 실행 전 훅

        Args:
            metadata: 작업 메타데이터
            context: 작업 실행 컨텍스트
        """
        raise NotImplementedError

    @abstractmethod
    async def after_execute(self, metadata: TaskMetadata, result: Any):
        """작업 실행 후 훅

        Args:
            metadata: 작업 메타데이터
            result: 작업 실행 결과
        """
        raise NotImplementedError

    @abstractmethod
    async def on_exception(self, metadata: TaskMetadata, exception: Exception):
        """예외 발생 시 훅

        Args:
            metadata: 작업 메타데이터
            exception: 발생한 예외
        """
        raise NotImplementedError


class LoggingHook(TaskHook):
    """로깅 훅"""

    def __init__(self, logger=None):
        import logging

        self.logger = logger or logging.getLogger(__name__)

    async def before_execute(self, metadata: TaskMetadata, context: Dict[str, Any]):
        """실행 전 로깅"""
        self.logger.info(f"Task {metadata.task_id} ({metadata.name}) starting")

    async def after_execute(self, metadata: TaskMetadata, result: Any):
        """실행 후 로깅"""
        self.logger.info(f"Task {metadata.task_id} ({metadata.name}) completed")

    async def on_exception(self, metadata: TaskMetadata, exception: Exception):
        """예외 로깅"""
        self.logger.error(
            f"Task {metadata.task_id} ({metadata.name}) failed: {exception}",
            exc_info=True,
        )


class MetricsHook(TaskHook):
    """메트릭 수집 훅"""

    def __init__(self):
        self.metrics = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_duration": timedelta(),
            "task_durations": [],
        }

    async def before_execute(self, metadata: TaskMetadata, context: Dict[str, Any]):
        """실행 전 메트릭"""
        self.metrics = {**self.metrics, "total_tasks": self.metrics["total_tasks"] + 1}

    async def after_execute(self, metadata: TaskMetadata, result: Any):
        """실행 후 메트릭"""
        self.metrics = {
            **self.metrics,
            "successful_tasks": self.metrics["successful_tasks"] + 1,
        }
        if metadata.duration():
            duration = metadata.duration()
            self.metrics = {
                **self.metrics,
                "total_duration": self.metrics["total_duration"] + duration,
            }
            self.metrics["task_durations"] = self.metrics["task_durations"] + [duration]

    async def on_exception(self, metadata: TaskMetadata, exception: Exception):
        """예외 메트릭"""
        self.metrics = {
            **self.metrics,
            "failed_tasks": self.metrics["failed_tasks"] + 1,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 조회"""
        avg_duration = None
        if self.metrics["task_durations"]:
            total_seconds = sum(
                (d.total_seconds() for d in self.metrics["task_durations"])
            )
            avg_duration = timedelta(
                seconds=total_seconds / len(self.metrics["task_durations"])
            )
        return {
            **self.metrics,
            "success_rate": (
                self.metrics["successful_tasks"] / self.metrics["total_tasks"]
                if self.metrics["total_tasks"] > 0
                else 0
            ),
            "average_duration": avg_duration,
        }
