"""
Base Components for Async Task Management

비동기 작업 관리 기본 컴포넌트
"""

from enum import Enum
from typing import Any, Dict, Optional, Callable, List, Union, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid
from abc import ABC, abstractmethod

from ..core import Result, Success, Failure

T = TypeVar('T')


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"  # 대기 중
    QUEUED = "queued"  # 큐에 있음
    RUNNING = "running"  # 실행 중
    COMPLETED = "completed"  # 완료
    FAILED = "failed"  # 실패
    CANCELLED = "cancelled"  # 취소됨
    TIMEOUT = "timeout"  # 타임아웃
    RETRYING = "retrying"  # 재시도 중


class TaskPriority(Enum):
    """작업 우선순위"""
    CRITICAL = 0  # 최고 우선순위
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4  # 최저 우선순위
    
    def __lt__(self, other):
        return self.value < other.value


class BackoffStrategy(Enum):
    """재시도 백오프 전략"""
    FIXED = "fixed"  # 고정 지연
    LINEAR = "linear"  # 선형 증가
    EXPONENTIAL = "exponential"  # 지수 증가
    JITTER = "jitter"  # 랜덤 지터 추가


@dataclass
class RetryPolicy:
    """재시도 정책"""
    max_attempts: int = 3
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
            if not any(isinstance(exception, exc_type) for exc_type in self.retry_on):
                return False
        
        if self.retry_condition:
            return self.retry_condition(exception)
        
        return True
    
    def get_delay(self, attempt: int) -> timedelta:
        """재시도 지연 시간 계산"""
        if self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.delay
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.delay * attempt
        elif self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.delay * (self.backoff_multiplier ** (attempt - 1))
        else:  # JITTER
            import random
            base_delay = self.delay * (self.backoff_multiplier ** (attempt - 1))
            jitter = random.uniform(0, base_delay.total_seconds() * 0.1)
            delay = base_delay + timedelta(seconds=jitter)
        
        # 최대 지연 시간 제한
        if delay > self.max_delay:
            delay = self.max_delay
        
        return delay


@dataclass
class TaskMetadata:
    """작업 메타데이터"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # 시간 정보
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 실행 정보
    retry_count: int = 0
    retry_policy: Optional[RetryPolicy] = None
    timeout: Optional[timedelta] = None
    
    # 의존성
    depends_on: List[str] = field(default_factory=list)  # 의존 작업 ID
    parent_id: Optional[str] = None  # 부모 작업 ID
    children_ids: List[str] = field(default_factory=list)  # 자식 작업 ID
    
    # 컨텍스트
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # 결과
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    
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
            TaskStatus.TIMEOUT
        ]
    
    def is_ready(self) -> bool:
        """실행 가능 상태 확인"""
        return self.status == TaskStatus.PENDING and not self.depends_on


@dataclass
class TaskResult(Generic[T]):
    """작업 결과"""
    task_id: str
    status: TaskStatus
    value: Optional[T] = None
    error: Optional[str] = None
    metadata: Optional[TaskMetadata] = None
    
    def is_success(self) -> bool:
        """성공 여부"""
        return self.status == TaskStatus.COMPLETED
    
    def is_failure(self) -> bool:
        """실패 여부"""
        return self.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.CANCELLED]
    
    def to_result(self) -> Result[T, str]:
        """Result 타입으로 변환"""
        if self.is_success():
            return Success(self.value)
        else:
            return Failure(self.error or f"Task failed with status: {self.status}")


class TaskCallback(ABC):
    """작업 콜백 인터페이스"""
    
    @abstractmethod
    def on_start(self, metadata: TaskMetadata):
        """작업 시작 시"""
        pass
    
    @abstractmethod
    def on_complete(self, result: TaskResult):
        """작업 완료 시"""
        pass
    
    @abstractmethod
    def on_error(self, metadata: TaskMetadata, error: Exception):
        """에러 발생 시"""
        pass
    
    @abstractmethod
    def on_cancel(self, metadata: TaskMetadata):
        """작업 취소 시"""
        pass
    
    @abstractmethod
    def on_timeout(self, metadata: TaskMetadata):
        """타임아웃 시"""
        pass
    
    @abstractmethod
    def on_retry(self, metadata: TaskMetadata, attempt: int):
        """재시도 시"""
        pass


class TaskError(Exception):
    """작업 에러"""
    def __init__(self, message: str, task_id: Optional[str] = None):
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
        """작업 실행"""
        pass
    
    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> Result[None, str]:
        """작업 검증"""
        pass
    
    @abstractmethod
    def cleanup(self, context: Dict[str, Any]):
        """작업 정리"""
        pass


class CallableTask(Task[T]):
    """호출 가능 작업"""
    
    def __init__(self, func: Callable[..., T], *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    async def execute(self, context: Dict[str, Any]) -> T:
        """작업 실행"""
        import asyncio
        
        # 컨텍스트를 kwargs에 병합
        merged_kwargs = {**self.kwargs, **context}
        
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(*self.args, **merged_kwargs)
        else:
            # 동기 함수를 비동기로 실행
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.func,
                *self.args,
                **merged_kwargs
            )
    
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
    name: str = "chain"
    
    async def execute(self, context: Dict[str, Any]) -> List[Any]:
        """체인 실행"""
        results = []
        chain_context = context.copy()
        
        for i, task in enumerate(self.tasks):
            # 이전 결과를 컨텍스트에 추가
            if results:
                chain_context['previous_result'] = results[-1]
                chain_context['all_results'] = results
            
            result = await task.execute(chain_context)
            results.append(result)
            
            # 결과를 다음 작업의 입력으로 사용
            if isinstance(result, dict):
                chain_context.update(result)
        
        return results


@dataclass
class TaskGroup:
    """작업 그룹 (병렬 실행)"""
    tasks: List[Task]
    name: str = "group"
    fail_fast: bool = False  # 하나라도 실패하면 모두 취소
    
    async def execute(self, context: Dict[str, Any]) -> List[Any]:
        """그룹 실행"""
        import asyncio
        
        # 모든 작업을 병렬로 실행
        coroutines = [
            task.execute(context.copy())
            for task in self.tasks
        ]
        
        if self.fail_fast:
            # 하나라도 실패하면 모두 취소
            results = []
            tasks = [asyncio.create_task(coro) for coro in coroutines]
            
            try:
                for task in asyncio.as_completed(tasks):
                    result = await task
                    results.append(result)
            except Exception as e:
                # 실행 중인 작업 취소
                for task in tasks:
                    if not task.done():
                        task.cancel()
                raise e
            
            return results
        else:
            # 모든 작업 완료 대기
            return await asyncio.gather(*coroutines, return_exceptions=True)


class TaskHook(ABC):
    """작업 훅 인터페이스"""
    
    @abstractmethod
    async def before_execute(self, metadata: TaskMetadata, context: Dict[str, Any]):
        """실행 전 훅"""
        pass
    
    @abstractmethod
    async def after_execute(self, metadata: TaskMetadata, result: Any):
        """실행 후 훅"""
        pass
    
    @abstractmethod
    async def on_exception(self, metadata: TaskMetadata, exception: Exception):
        """예외 발생 시 훅"""
        pass


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
            exc_info=True
        )


class MetricsHook(TaskHook):
    """메트릭 수집 훅"""
    
    def __init__(self):
        self.metrics = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_duration': timedelta(),
            'task_durations': []
        }
    
    async def before_execute(self, metadata: TaskMetadata, context: Dict[str, Any]):
        """실행 전 메트릭"""
        self.metrics['total_tasks'] += 1
    
    async def after_execute(self, metadata: TaskMetadata, result: Any):
        """실행 후 메트릭"""
        self.metrics['successful_tasks'] += 1
        if metadata.duration():
            duration = metadata.duration()
            self.metrics['total_duration'] += duration
            self.metrics['task_durations'].append(duration)
    
    async def on_exception(self, metadata: TaskMetadata, exception: Exception):
        """예외 메트릭"""
        self.metrics['failed_tasks'] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 조회"""
        avg_duration = None
        if self.metrics['task_durations']:
            total_seconds = sum(d.total_seconds() for d in self.metrics['task_durations'])
            avg_duration = timedelta(seconds=total_seconds / len(self.metrics['task_durations']))
        
        return {
            **self.metrics,
            'success_rate': (
                self.metrics['successful_tasks'] / self.metrics['total_tasks']
                if self.metrics['total_tasks'] > 0 else 0
            ),
            'average_duration': avg_duration
        }