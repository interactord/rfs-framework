"""
Cloud Tasks Queue System (RFS v4)

Cloud Tasks 기반 비동기 작업 큐 시스템
- 작업 큐 생성 및 관리
- 지연 실행 및 스케줄링
- 재시도 정책 및 데드레터 큐
- 우선순위 기반 작업 처리
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

try:
    from google.cloud import logging as cloud_logging
    from google.cloud import tasks_v2
    from google.protobuf import duration_pb2, timestamp_pb2
    from pydantic import BaseModel, ConfigDict, Field, field_validator

    GOOGLE_CLOUD_AVAILABLE = True
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object
    Field = lambda default=None, **kwargs: default
    tasks_v2 = None
    GOOGLE_CLOUD_AVAILABLE = False
    PYDANTIC_AVAILABLE = False
from ..core.result import Failure, Result, Success
from ..events import Event, get_event_bus
from ..reactive import Flux, Mono

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    """작업 우선순위"""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class TaskStatus(str, Enum):
    """작업 상태"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


if PYDANTIC_AVAILABLE:

    class TaskDefinition(BaseModel):
        """작업 정의 (Pydantic v2)"""

        model_config = ConfigDict(
            str_strip_whitespace=True, validate_default=True, frozen=False
        )
        task_id: str = Field(
            ..., min_length=1, max_length=100, description="작업 고유 ID"
        )
        handler_path: str = Field(
            ..., pattern="^/[a-zA-Z0-9\\-_/]*$", description="작업 처리 핸들러 경로"
        )
        payload: Dict[str, Any] = field(default_factory=dict)
        priority: TaskPriority = Field(
            default=TaskPriority.NORMAL, description="작업 우선순위"
        )
        schedule_time: datetime | None = Field(
            default=None, description="예약 실행 시간"
        )
        delay_seconds: int = Field(
            default=0, ge=0, le=86400 * 30, description="지연 시간 (초)"
        )
        max_retry_count: int = Field(
            default=3, ge=0, le=100, description="최대 재시도 횟수"
        )
        retry_min_backoff: int = Field(
            default=1, ge=1, description="최소 재시도 백오프 (초)"
        )
        retry_max_backoff: int = Field(
            default=300, ge=1, description="최대 재시도 백오프 (초)"
        )
        http_method: str = Field(
            default="POST",
            pattern="^(GET|POST|PUT|DELETE|PATCH)$",
            description="HTTP 메서드",
        )
        headers: Dict[str, Any] = field(default_factory=dict)
        queue_name: str = Field(
            default="default", min_length=1, max_length=100, description="큐 이름"
        )
        tags: List[str] = field(default_factory=list)
        created_at: datetime = Field(
            default_factory=datetime.now, description="생성 시간"
        )

        @field_validator("schedule_time")
        @classmethod
        def validate_schedule_time(cls, v: datetime | None) -> datetime | None:
            """예약 시간 검증"""
            if v is not None and v < datetime.now():
                raise ValueError("예약 시간은 현재 시간보다 미래여야 합니다")
            return v

        @field_validator("payload")
        @classmethod
        def validate_payload(cls, v: Dict[str, Any]) -> Dict[str, Any]:
            """페이로드 크기 검증"""
            payload_str = json.dumps(v, ensure_ascii=False)
            if len(payload_str.encode("utf-8")) > 100 * 1024:
                raise ValueError("페이로드 크기는 100KB를 초과할 수 없습니다")
            return v

        def calculate_schedule_time(self) -> datetime:
            """실제 실행 시간 계산"""
            if self.schedule_time:
                return self.schedule_time
            elif self.delay_seconds > 0:
                return datetime.now() + timedelta(seconds=self.delay_seconds)
            else:
                return datetime.now()

        def to_cloud_task(self, target_url: str) -> Dict[str, Any]:
            """Cloud Tasks 형식으로 변환"""
            task_data = {
                "http_request": {
                    "http_method": getattr(tasks_v2.HttpMethod, self.http_method),
                    "url": f"{target_url.rstrip('/')}{self.handler_path}",
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Task-ID": self.task_id,
                        "X-Task-Priority": str(self.priority.value),
                        **self.headers,
                    },
                    "body": json.dumps(
                        {
                            "task_id": self.task_id,
                            "payload": self.payload,
                            "priority": self.priority.value,
                            "tags": self.tags,
                            "created_at": self.created_at.isoformat(),
                        }
                    ).encode("utf-8"),
                }
            }
            schedule_time = self.calculate_schedule_time()
            if schedule_time > datetime.now():
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(schedule_time)
                task_data["schedule_time"] = {"schedule_time": timestamp}
            return task_data

else:
    from dataclasses import dataclass, field

    @dataclass
    class TaskDefinition:
        """작업 정의 (Fallback)"""

        task_id: str
        handler_path: str
        payload: Dict[str, Any] = field(default_factory=dict)
        priority: TaskPriority = TaskPriority.NORMAL
        schedule_time = None
        delay_seconds = 0
        max_retry_count = 3
        retry_min_backoff = 1
        retry_max_backoff = 300
        http_method = "POST"
        headers: Dict[str, Any] = field(default_factory=dict)
        queue_name = "default"
        tags: List[str] = field(default_factory=list)
        created_at: datetime = field(default_factory=datetime.now)

        def calculate_schedule_time(self) -> datetime:
            if self.schedule_time:
                return self.schedule_time
            elif self.delay_seconds > 0:
                return datetime.now() + timedelta(seconds=self.delay_seconds)
            else:
                return datetime.now()


class CloudTaskQueue:
    """Cloud Tasks 큐 관리자"""

    def __init__(self, project_id: str, location="us-central1", service_url=None):
        self.project_id = project_id
        self.location = location
        self.service_url = (
            service_url
            or f"https://{os.environ.get('K_SERVICE', 'localhost')}-{os.environ.get('K_REVISION', 'dev')}.a.run.app"
        )
        self.client = None
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                self.client = tasks_v2.CloudTasksClient()
            except Exception as e:
                logger.warning(f"Cloud Tasks 클라이언트 초기화 실패: {e}")
        self.queues = {}
        self.task_handlers = {}
        self.task_stats = {"submitted": 0, "completed": 0, "failed": 0, "retried": 0}

    async def initialize(self):
        """큐 시스템 초기화"""
        await self.create_queue("default", max_concurrent_dispatches=100)
        await self.create_queue("high-priority", max_concurrent_dispatches=200)
        await self.create_queue("low-priority", max_concurrent_dispatches=50)
        logger.info("Cloud Tasks 큐 시스템이 초기화되었습니다")

    async def create_queue(
        self,
        queue_name: str,
        max_concurrent_dispatches=100,
        max_dispatches_per_second=100.0,
    ) -> Result[str, str]:
        """큐 생성"""
        if not GOOGLE_CLOUD_AVAILABLE or not self.client:
            queue_path = f"projects/{self.project_id}/locations/{self.location}/queues/{queue_name}"
            self.queues = {**self.queues, queue_name: queue_path}
            return Success(queue_path)
        try:
            parent = f"projects/{self.project_id}/locations/{self.location}"
            queue_path = f"{parent}/queues/{queue_name}"
            try:
                existing_queue = self.client.get_queue(name=queue_path)
                self.queues = {**self.queues, queue_name: queue_path}
                logger.info(f"기존 큐 사용: {queue_name}")
                return Success(queue_path)
            except Exception:
                pass
            queue_config = {
                "name": queue_path,
                "rate_limits": {
                    "max_concurrent_dispatches": max_concurrent_dispatches,
                    "max_dispatches_per_second": max_dispatches_per_second,
                },
                "retry_config": {
                    "max_attempts": 10,
                    "min_backoff": duration_pb2.Duration(seconds=1),
                    "max_backoff": duration_pb2.Duration(seconds=300),
                    "max_doublings": 5,
                },
            }
            queue = self.client.create_queue(parent=parent, queue=queue_config)
            self.queues = {**self.queues, queue_name: queue.name}
            logger.info(f"큐 생성 완료: {queue_name}")
            return Success(queue.name)
        except Exception as e:
            error_msg = f"큐 생성 실패: {queue_name} - {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    def register_handler(self, path: str, handler: Callable[[Dict[str, Any]], Any]):
        """작업 핸들러 등록"""
        self.task_handlers = {**self.task_handlers, path: handler}
        logger.info(f"작업 핸들러 등록: {path}")

    async def submit_task(self, task: TaskDefinition) -> Result[str, str]:
        """작업 제출"""
        try:
            if task.queue_name not in self.queues:
                await self.create_queue(task.queue_name)
            queue_path = self.queues[task.queue_name]
            if not GOOGLE_CLOUD_AVAILABLE or not self.client:
                return await self._execute_local_task(task)
            cloud_task = task.to_cloud_task(self.service_url)
            cloud_task = {
                **cloud_task,
                "name": {"name": f"{queue_path}/tasks/{task.task_id}"},
            }
            created_task = self.client.create_task(parent=queue_path, task=cloud_task)
            self.task_stats = {
                **self.task_stats,
                "submitted": self.task_stats["submitted"] + 1,
            }
            await self._publish_task_event("task.submitted", task)
            logger.info(f"작업 제출 완료: {task.task_id}")
            return Success(created_task.name)
        except Exception as e:
            error_msg = f"작업 제출 실패: {task.task_id} - {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _execute_local_task(self, task: TaskDefinition) -> Result[str, str]:
        """로컬 환경에서 작업 즉시 실행"""
        try:
            schedule_time = task.calculate_schedule_time()
            if schedule_time > datetime.now():
                delay = (schedule_time - datetime.now()).total_seconds()
                await asyncio.sleep(delay)
            if task.handler_path in self.task_handlers:
                handler = self.task_handlers[task.handler_path]
                request_data = {
                    "task_id": task.task_id,
                    "payload": task.payload,
                    "priority": task.priority.value,
                    "tags": task.tags,
                    "created_at": task.created_at.isoformat(),
                }
                if asyncio.iscoroutinefunction(handler):
                    await handler(request_data)
                else:
                    handler(request_data)
                await self._publish_task_event("task.completed", task)
                self.task_stats = {
                    **self.task_stats,
                    "completed": self.task_stats["completed"] + 1,
                }
                return Success(f"local-{task.task_id}")
            else:
                error_msg = f"핸들러를 찾을 수 없습니다: {task.handler_path}"
                await self._publish_task_event("task.failed", task, error_msg)
                self.task_stats = {
                    **self.task_stats,
                    "failed": self.task_stats["failed"] + 1,
                }
                return Failure(error_msg)
        except Exception as e:
            error_msg = f"로컬 작업 실행 실패: {str(e)}"
            await self._publish_task_event("task.failed", task, error_msg)
            self.task_stats = {
                **self.task_stats,
                "failed": self.task_stats["failed"] + 1,
            }
            return Failure(error_msg)

    async def submit_batch_tasks(
        self, tasks: List[TaskDefinition]
    ) -> Dict[str, Result[str, str]]:
        """배치 작업 제출"""
        results = {}
        submit_tasks = []
        for task in tasks:
            submit_task = asyncio.create_task(self.submit_task(task))
            submit_tasks = submit_tasks + [(task.task_id, submit_task)]
        for task_id, submit_task in submit_tasks:
            try:
                result = await submit_task
                results[task_id] = {task_id: result}
            except Exception as e:
                results = {
                    **results,
                    task_id: {task_id: Failure(f"배치 제출 오류: {str(e)}")},
                }
        success_count = len(
            [r for r in results.values() if type(r).__name__ == "Success"]
        )
        logger.info(f"배치 작업 제출 완료: {success_count}/{len(tasks)}개 성공")
        return results

    async def cancel_task(self, queue_name: str, task_name: str) -> Result[None, str]:
        """작업 취소"""
        if not GOOGLE_CLOUD_AVAILABLE or not self.client:
            return Failure("Cloud Tasks를 사용할 수 없습니다")
        try:
            full_task_name = f"{self.queues[queue_name]}/tasks/{task_name}"
            self.client.delete_task(name=full_task_name)
            logger.info(f"작업 취소 완료: {task_name}")
            return Success(None)
        except Exception as e:
            error_msg = f"작업 취소 실패: {task_name} - {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _publish_task_event(
        self, event_type: str, task: TaskDefinition, error=None
    ):
        """작업 이벤트 발행"""
        try:
            event_bus = await get_event_bus()
            event_data = {
                "task_id": task.task_id,
                "queue_name": task.queue_name,
                "priority": task.priority.value,
                "handler_path": task.handler_path,
                "tags": task.tags,
            }
            if error:
                event_data["error"] = {"error": error}
            event = Event(event_type=event_type, data=event_data, source="cloud_tasks")
            await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"작업 이벤트 발행 실패: {e}")

    def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """큐 통계 조회"""
        return {
            "queue_name": queue_name,
            "pending_tasks": 0,
            "in_flight_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
        }

    def get_overall_stats(self) -> Dict[str, Any]:
        """전체 통계 조회"""
        return {
            "queues_count": len(self.queues),
            "registered_handlers": len(self.task_handlers),
            "task_stats": self.task_stats.copy(),
            "queue_names": list(self.queues.keys()),
        }


class TaskScheduler:
    """작업 스케줄링 도우미"""

    def __init__(self, queue: CloudTaskQueue):
        self.queue = queue

    async def schedule_daily(
        self,
        task_id: str,
        handler_path: str,
        payload: Dict[str, Any],
        hour=9,
        minute=0,
    ) -> Result[str, str]:
        """매일 반복 작업 스케줄링"""
        from datetime import date

        tomorrow = date.today() + timedelta(days=1)
        schedule_time = datetime.combine(
            tomorrow, datetime.min.time().replace(hour=hour, minute=minute)
        )
        task = TaskDefinition(
            task_id=f"{task_id}-{tomorrow.isoformat()}",
            handler_path=handler_path,
            payload=payload,
            schedule_time=schedule_time,
            tags=["scheduled", "daily"],
        )
        return await self.queue.submit_task(task)

    async def schedule_weekly(
        self,
        task_id: str,
        handler_path: str,
        payload: Dict[str, Any],
        weekday=0,
        hour=9,
    ) -> Result[str, str]:
        """매주 반복 작업 스케줄링"""
        from datetime import date

        today = date.today()
        days_ahead = weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead = days_ahead + 7
        next_occurrence = today + timedelta(days=days_ahead)
        schedule_time = datetime.combine(
            next_occurrence, datetime.min.time().replace(hour=hour)
        )
        task = TaskDefinition(
            task_id=f"{task_id}-{next_occurrence.isoformat()}",
            handler_path=handler_path,
            payload=payload,
            schedule_time=schedule_time,
            tags=["scheduled", "weekly"],
        )
        return await self.queue.submit_task(task)


_task_queue = None


async def get_task_queue(project_id: str = None) -> CloudTaskQueue:
    """작업 큐 인스턴스 획득"""
    # global _task_queue - removed for functional programming
    if _task_queue is None:
        if project_id is None:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                raise ValueError("프로젝트 ID가 필요합니다")
        _task_queue = CloudTaskQueue(project_id)
        await _task_queue.initialize()
    return _task_queue


async def submit_task(
    task_id: str, handler_path: str, payload=None, **kwargs
) -> Result[str, str]:
    """간단한 작업 제출"""
    queue = await get_task_queue()
    task = TaskDefinition(
        task_id=task_id, handler_path=handler_path, payload=payload or {}, **kwargs
    )
    return await queue.submit_task(task)


async def schedule_task(
    task_id: str,
    handler_path: str,
    schedule_time: datetime,
    payload=None,
    **kwargs,
) -> Result[str, str]:
    """시간 예약 작업 제출"""
    queue = await get_task_queue()
    task = TaskDefinition(
        task_id=task_id,
        handler_path=handler_path,
        payload=payload or {},
        schedule_time=schedule_time,
        **kwargs,
    )
    return await queue.submit_task(task)


def task_handler(path: str):
    """작업 핸들러 데코레이터"""

    def decorator(func: Callable):

        async def register_handler():
            queue = await get_task_queue()
            queue.register_handler(path, func)

        asyncio.create_task(register_handler())
        return func

    return decorator
