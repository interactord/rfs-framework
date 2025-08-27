"""
RFS v4.1 Task Definition System
작업 정의 및 처리기 관리 시스템

주요 기능:
- TaskDefinition: 작업 정의 및 메타데이터
- TaskType: 작업 유형 분류
- TaskContext: 작업 실행 컨텍스트
- task_handler 데코레이터: 작업 처리기 등록
"""

import asyncio
import inspect
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union, get_type_hints

from ..core.config import get_config
from ..core.result import Failure, Result, Success


class TaskType(Enum):
    """작업 유형"""

    BATCH = "batch"  # 배치 작업
    REALTIME = "realtime"  # 실시간 작업
    SCHEDULED = "scheduled"  # 스케줄된 작업
    EVENT_DRIVEN = "event_driven"  # 이벤트 기반 작업
    BACKGROUND = "background"  # 백그라운드 작업
    PRIORITY = "priority"  # 우선순위 작업


@dataclass
class TaskContext:
    """작업 실행 컨텍스트"""

    task_id: str
    task_name: str
    task_type: TaskType
    execution_time: datetime = field(default_factory=datetime.now)
    retry_count = 0
    max_retries = 3
    timeout_seconds = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_retry(self) -> "TaskContext":
        """재시도 컨텍스트 생성"""
        return TaskContext(
            task_id=self.task_id,
            task_name=self.task_name,
            task_type=self.task_type,
            execution_time=datetime.now(),
            retry_count=self.retry_count + 1,
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
            metadata=self.metadata.copy(),
        )

    def should_retry(self) -> bool:
        """재시도 가능 여부 확인"""
        return self.retry_count < self.max_retries

    def add_metadata(self, key: str, value: Any) -> None:
        """메타데이터 추가"""
        self.metadata = {**self.metadata, key: value}

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """메타데이터 조회"""
        return self.metadata.get(key, default)


@dataclass
class TaskDefinition:
    """작업 정의"""

    name: str
    task_type: TaskType
    handler: Callable
    description = None
    priority = 5  # 1-10, 높을수록 우선순위
    timeout_seconds = None
    max_retries = 3
    retry_delay_seconds = 1
    retry_exponential_backoff = False
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 스케줄링 관련
    schedule_cron = None
    schedule_interval = None
    schedule_at = None

    # 의존성
    dependencies: List[str] = field(default_factory=list)

    # 조건부 실행
    conditions: List[Callable] = field(default_factory=list)

    def __post_init__(self):
        """초기화 후 검증"""
        if not callable(self.handler):
            raise ValueError(f"Handler must be callable: {self.handler}")

        if self.priority < 1 or self.priority > 10:
            raise ValueError(f"Priority must be between 1-10: {self.priority}")

        # 핸들러 시그니처 검증
        self._validate_handler_signature()

    def _validate_handler_signature(self) -> None:
        """핸들러 시그니처 검증"""
        sig = inspect.signature(self.handler)

        # 첫 번째 매개변수는 TaskContext여야 함
        params = list(sig.parameters.values())
        if not params:
            raise ValueError(
                f"Handler must accept TaskContext as first parameter: {self.name}"
            )

        first_param = params[0]
        type_hints = get_type_hints(self.handler)

        if first_param.name in type_hints:
            hint = type_hints[first_param.name]
            if hint != TaskContext:
                raise ValueError(f"First parameter must be TaskContext: {self.name}")

    def can_execute(self, context: TaskContext) -> bool:
        """실행 가능 여부 확인"""
        # 조건 검사
        try:
            for condition in self.conditions:
                if not condition(context):
                    return False
            return True
        except Exception as e:
            # 조건 검사 실패시 실행 불가
            context.add_metadata("condition_error", str(e))
            return False

    async def execute(self, context: TaskContext, *args, **kwargs) -> Result[Any, str]:
        """작업 실행"""
        if not self.can_execute(context):
            return Failure(f"Task conditions not met: {self.name}")

        try:
            # 타임아웃 설정
            timeout = self.timeout_seconds or context.timeout_seconds

            # 핸들러 실행
            if asyncio.iscoroutinefunction(self.handler):
                if timeout:
                    result = await asyncio.wait_for(
                        self.handler(context, *args, **kwargs), timeout=timeout
                    )
                else:
                    result = await self.handler(context, *args, **kwargs)
            else:
                # 동기 함수를 비동기로 실행
                if timeout:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(self.handler, context, *args, **kwargs),
                        timeout=timeout,
                    )
                else:
                    result = await asyncio.to_thread(
                        self.handler, context, *args, **kwargs
                    )

            return Success(result)

        except asyncio.TimeoutError:
            return Failure(f"Task timeout: {self.name}")
        except Exception as e:
            return Failure(f"Task execution error: {e}")

    def get_next_run_time(self, from_time=None) -> Optional[datetime]:
        """다음 실행 시간 계산"""
        if not from_time:
            from_time = datetime.now()

        if self.schedule_at and self.schedule_at > from_time:
            return self.schedule_at

        if self.schedule_interval:
            return from_time + self.schedule_interval

        if self.schedule_cron:
            # 크론 표현식 파싱 (간단한 구현)
            return self._parse_cron(self.schedule_cron, from_time)

        return None

    def _parse_cron(self, cron_expr: str, from_time: datetime) -> Optional[datetime]:
        """크론 표현식 파싱 (간단한 구현)"""
        # 실제 구현에서는 croniter 등의 라이브러리 사용 권장
        # 여기서는 기본적인 케이스만 처리

        parts = cron_expr.split()
        if len(parts) != 5:
            return None

        # 매시간 정각 (0 * * * *)
        if parts[0] == "0" and parts[1] == "*":
            next_hour = from_time.replace(
                minute=0, second=0, microsecond=0
            ) + timedelta(hours=1)
            return next_hour

        # 매일 자정 (0 0 * * *) - 모든 필드가 정확히 맞는 경우만
        if (
            parts[0] == "0"
            and parts[1] == "0"
            and parts[2] == "*"
            and parts[3] == "*"
            and parts[4] == "*"
        ):
            next_day = from_time.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            return next_day

        return None

    def add_tag(self, tag: str) -> None:
        """태그 추가"""
        if tag not in self.tags:
            self.tags = self.tags + [tag]

    def has_tag(self, tag: str) -> bool:
        """태그 존재 확인"""
        return tag in self.tags

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "name": self.name,
            "task_type": self.task_type.value,
            "description": self.description,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "retry_exponential_backoff": self.retry_exponential_backoff,
            "tags": self.tags.copy(),
            "metadata": self.metadata.copy(),
            "schedule_cron": self.schedule_cron,
            "schedule_interval": (
                self.schedule_interval.total_seconds()
                if self.schedule_interval
                else None
            ),
            "schedule_at": self.schedule_at.isoformat() if self.schedule_at else None,
            "dependencies": self.dependencies.copy(),
        }


class TaskRegistry:
    """작업 정의 레지스트리"""

    def __init__(self):
        self._tasks = {}
        self._handlers = {}

    def register(self, task_def: TaskDefinition) -> None:
        """작업 정의 등록"""
        if task_def.name in self._tasks:
            raise ValueError(f"Task already registered: {task_def.name}")

        self._tasks = {**self._tasks, task_def.name: task_def}
        self._handlers = {**self._handlers, task_def.name: task_def.handler}

    def unregister(self, name: str) -> None:
        """작업 정의 해제"""
        if name in self._tasks:
            del self._tasks[name]
        if name in self._handlers:
            del self._handlers[name]

    def get(self, name: str) -> Optional[TaskDefinition]:
        """작업 정의 조회"""
        return self._tasks.get(name)

    def list_all(self) -> List[TaskDefinition]:
        """모든 작업 정의 조회"""
        return list(self._tasks.values())

    def list_by_type(self, task_type: TaskType) -> List[TaskDefinition]:
        """유형별 작업 정의 조회"""
        return [task for task in self._tasks.values() if task.task_type == task_type]

    def list_by_tag(self, tag: str) -> List[TaskDefinition]:
        """태그별 작업 정의 조회"""
        return [task for task in self._tasks.values() if task.has_tag(tag)]

    def list_scheduled(self) -> List[TaskDefinition]:
        """스케줄된 작업 조회"""
        return [
            task
            for task in self._tasks.values()
            if task.schedule_cron or task.schedule_interval or task.schedule_at
        ]


# 전역 레지스트리
_task_registry = TaskRegistry()


def task_handler(
    name: str,
    task_type: TaskType = TaskType.BACKGROUND,
    description=None,
    priority=5,
    timeout_seconds=None,
    max_retries=3,
    retry_delay_seconds=1,
    retry_exponential_backoff=False,
    tags: Optional[List[str]] = None,
    schedule_cron=None,
    schedule_interval=None,
    schedule_at=None,
    dependencies: Optional[List[str]] = None,
    conditions: Optional[List[Callable]] = None,
    **metadata,
) -> Callable:
    """작업 처리기 데코레이터"""

    def decorator(func: Callable) -> Callable:
        # TaskDefinition 생성
        task_def = TaskDefinition(
            name=name,
            task_type=task_type,
            handler=func,
            description=description or func.__doc__,
            priority=priority,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            retry_exponential_backoff=retry_exponential_backoff,
            tags=tags or [],
            metadata=metadata,
            schedule_cron=schedule_cron,
            schedule_interval=schedule_interval,
            schedule_at=schedule_at,
            dependencies=dependencies or [],
            conditions=conditions or [],
        )

        # 레지스트리에 등록
        _task_registry.register(task_def)

        return func

    return decorator


def get_task_definition(name: str) -> Optional[TaskDefinition]:
    """작업 정의 조회"""
    return _task_registry.get(name)


def list_task_definitions() -> List[TaskDefinition]:
    """모든 작업 정의 조회"""
    return _task_registry.list_all()


def create_task_definition(
    name: str, handler: Callable, task_type: TaskType = TaskType.BACKGROUND, **kwargs
) -> TaskDefinition:
    """작업 정의 생성"""
    task_def = TaskDefinition(name=name, task_type=task_type, handler=handler, **kwargs)

    _task_registry.register(task_def)
    return task_def


# 편의 함수들
def batch_task(name: str, **kwargs):
    """배치 작업 데코레이터"""
    return task_handler(name, TaskType.BATCH, **kwargs)


def scheduled_task(name: str, schedule_cron: str, **kwargs):
    """스케줄된 작업 데코레이터"""
    return task_handler(name, TaskType.SCHEDULED, schedule_cron=schedule_cron, **kwargs)


def realtime_task(name: str, **kwargs):
    """실시간 작업 데코레이터"""
    return task_handler(name, TaskType.REALTIME, **kwargs)


def priority_task(name: str, priority=8, **kwargs):
    """우선순위 작업 데코레이터"""
    return task_handler(name, TaskType.PRIORITY, priority=priority, **kwargs)
