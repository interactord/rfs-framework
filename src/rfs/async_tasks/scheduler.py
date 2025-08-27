"""
Task Scheduler for Async Task Management

작업 스케줄러 - Cron, Interval, OneTime 스케줄링
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import croniter

from ..core.result import Failure, Result, Success
from .base import CallableTask, Task, TaskPriority
from .manager import AsyncTaskManager, get_task_manager

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """스케줄 타입"""

    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class Schedule:
    """스케줄 정의"""

    schedule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schedule_type: ScheduleType = ScheduleType.ONCE
    expression = None
    interval = None
    start_time = None
    end_time = None
    timezone = "UTC"
    max_runs = None
    run_count = 0
    last_run = None
    next_run = None
    enabled = True

    def calculate_next_run(self) -> Optional[datetime]:
        """다음 실행 시간 계산"""
        now = datetime.now()
        if self.end_time and now >= self.end_time:
            return None
        if self.max_runs and self.run_count >= self.max_runs:
            return None
        match self.schedule_type:
            case ScheduleType.CRON:
                if self.expression:
                    cron = croniter.croniter(self.expression, now)
                    return cron.get_next(datetime)
            case ScheduleType.INTERVAL:
                if self.interval:
                    if self.last_run:
                        return self.last_run + self.interval
                    else:
                        return now + self.interval
            case ScheduleType.ONCE:
                if self.start_time and self.run_count == 0:
                    return self.start_time
            case ScheduleType.DAILY:
                if self.last_run:
                    next_run = self.last_run + timedelta(days=1)
                else:
                    next_run = now.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ) + timedelta(days=1)
                return next_run
            case ScheduleType.WEEKLY:
                if self.last_run:
                    next_run = self.last_run + timedelta(weeks=1)
                else:
                    days_until_monday = (7 - now.weekday()) % 7
                    if days_until_monday == 0:
                        days_until_monday = 7
                    next_run = now + timedelta(days=days_until_monday)
                    next_run = next_run.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                return next_run
            case ScheduleType.MONTHLY:
                if self.last_run:
                    if self.last_run.month == 12:
                        next_run = self.last_run.replace(
                            year=self.last_run.year + 1, month=1
                        )
                    else:
                        next_run = self.last_run.replace(month=self.last_run.month + 1)
                else:
                    if now.month == 12:
                        next_run = now.replace(year=now.year + 1, month=1, day=1)
                    else:
                        next_run = now.replace(month=now.month + 1, day=1)
                    next_run = next_run.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                return next_run
        return None


@dataclass
class ScheduledTask:
    """스케줄된 작업"""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name = ""
    task: Union[Callable, Task] = None
    schedule: Schedule = field(default_factory=Schedule)
    priority: TaskPriority = TaskPriority.NORMAL
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    enabled = True

    def should_run(self) -> bool:
        """실행 여부 확인"""
        if not self.enabled or not self.schedule.enabled:
            return False
        now = datetime.now()
        if self.schedule.next_run and now >= self.schedule.next_run:
            return True
        return False


class CronSchedule(Schedule):
    """Cron 스케줄"""

    def __init__(self, expression: str, **kwargs):
        super().__init__(
            schedule_type=ScheduleType.CRON, expression=expression, **kwargs
        )


class IntervalSchedule(Schedule):
    """간격 스케줄"""

    def __init__(self, interval: timedelta, **kwargs):
        super().__init__(
            schedule_type=ScheduleType.INTERVAL, interval=interval, **kwargs
        )


class OneTimeSchedule(Schedule):
    """일회성 스케줄"""

    def __init__(self, start_time: datetime, **kwargs):
        super().__init__(
            schedule_type=ScheduleType.ONCE, start_time=start_time, max_runs=1, **kwargs
        )


class TaskScheduler:
    """
    작업 스케줄러

    Features:
    - Cron 표현식 지원
    - 반복 실행
    - 시간대 지원
    - 동적 스케줄 관리
    """

    def __init__(self, task_manager=None):
        self.task_manager = task_manager
        self.scheduled_tasks = {}
        self._scheduler_task = None
        self._shutdown = False
        self._lock = asyncio.Lock()

    async def start(self):
        """스케줄러 시작"""
        if self._scheduler_task:
            return
        if not self.task_manager:
            self.task_manager = await get_task_manager()
        self._shutdown = False
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("TaskScheduler started")

    async def stop(self):
        """스케줄러 중지"""
        self._shutdown = True
        if self._scheduler_task:
            await self._scheduler_task
        self._scheduler_task = None
        logger.info("TaskScheduler stopped")

    async def schedule(
        self,
        func: Union[Callable, Task],
        schedule: Schedule,
        name=None,
        priority: TaskPriority = TaskPriority.NORMAL,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """작업 스케줄링"""
        if type(func).__name__ == "Task":
            task = func
        else:
            task = CallableTask(func)
        scheduled_task = ScheduledTask(
            name=name or getattr(func, "__name__", "scheduled"),
            task=task,
            schedule=schedule,
            priority=priority,
            context=context or {},
            tags=tags or [],
        )
        scheduled_task.schedule.next_run = scheduled_task.schedule.calculate_next_run()
        async with self._lock:
            self.scheduled_tasks = {
                **self.scheduled_tasks,
                scheduled_task.task_id: scheduled_task,
            }
        logger.info(
            f"Task {scheduled_task.name} scheduled with ID {scheduled_task.task_id}"
        )
        return scheduled_task.task_id

    async def cancel(self, task_id: str) -> Result[None, str]:
        """스케줄 취소"""
        async with self._lock:
            if task_id not in self.scheduled_tasks:
                return Failure(f"Scheduled task {task_id} not found")
            del self.scheduled_tasks[task_id]
            logger.info(f"Scheduled task {task_id} cancelled")
            return Success(None)

    async def pause(self, task_id: str) -> Result[None, str]:
        """스케줄 일시 중지"""
        async with self._lock:
            if task_id not in self.scheduled_tasks:
                return Failure(f"Scheduled task {task_id} not found")
            self.scheduled_tasks[task_id].enabled = False
            logger.info(f"Scheduled task {task_id} paused")
            return Success(None)

    async def resume(self, task_id: str) -> Result[None, str]:
        """스케줄 재개"""
        async with self._lock:
            if task_id not in self.scheduled_tasks:
                return Failure(f"Scheduled task {task_id} not found")
            task = self.scheduled_tasks[task_id]
            task.enabled = True
            task.schedule.next_run = task.schedule.calculate_next_run()
            logger.info(f"Scheduled task {task_id} resumed")
            return Success(None)

    def list_schedules(self) -> List[ScheduledTask]:
        """스케줄 목록 조회"""
        return list(self.scheduled_tasks.values())

    def get_schedule(self, task_id: str) -> Optional[ScheduledTask]:
        """스케줄 조회"""
        return self.scheduled_tasks.get(task_id)

    async def _scheduler_loop(self):
        """스케줄러 루프"""
        while not self._shutdown:
            try:
                now = datetime.now()
                tasks_to_run = []
                async with self._lock:
                    for task_id, scheduled_task in self.scheduled_tasks.items():
                        if scheduled_task.should_run():
                            tasks_to_run = tasks_to_run + [scheduled_task]
                            scheduled_task.schedule.last_run = now
                            scheduled_task.schedule.run_count = (
                                scheduled_task.schedule.run_count + 1
                            )
                            scheduled_task.schedule.next_run = (
                                scheduled_task.schedule.calculate_next_run()
                            )
                            if (
                                scheduled_task.schedule.max_runs
                                and scheduled_task.schedule.run_count
                                >= scheduled_task.schedule.max_runs
                            ):
                                scheduled_task.enabled = False
                for scheduled_task in tasks_to_run:
                    await self._run_scheduled_task(scheduled_task)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _run_scheduled_task(self, scheduled_task: ScheduledTask):
        """스케줄된 작업 실행"""
        try:
            task_id = await self.task_manager.submit(
                scheduled_task.task,
                name=f"{scheduled_task.name}_run_{scheduled_task.schedule.run_count}",
                priority=scheduled_task.priority,
                context={
                    **scheduled_task.context,
                    "scheduled_task_id": scheduled_task.task_id,
                    "schedule_run_count": scheduled_task.schedule.run_count,
                },
                tags=scheduled_task.tags + ["scheduled"],
            )
            logger.info(
                f"Scheduled task {scheduled_task.name} submitted with ID {task_id} (run {scheduled_task.schedule.run_count})"
            )
        except Exception as e:
            logger.error(f"Failed to run scheduled task {scheduled_task.name}: {e}")


_global_scheduler = None


async def get_scheduler() -> TaskScheduler:
    """전역 스케줄러 반환"""
    # global _global_scheduler - removed for functional programming
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = TaskScheduler()
        await _global_scheduler.start()
    return _global_scheduler


async def schedule_cron(func: Callable, expression: str, **kwargs) -> str:
    """Cron 작업 스케줄"""
    scheduler = await get_scheduler()
    schedule = CronSchedule(expression)
    return await scheduler.schedule(func, schedule, **kwargs)


async def schedule_interval(func: Callable, interval: timedelta, **kwargs) -> str:
    """반복 작업 스케줄"""
    scheduler = await get_scheduler()
    schedule = IntervalSchedule(interval)
    return await scheduler.schedule(func, schedule, **kwargs)


async def schedule_once(func: Callable, start_time: datetime, **kwargs) -> str:
    """일회성 작업 스케줄"""
    scheduler = await get_scheduler()
    schedule = OneTimeSchedule(start_time)
    return await scheduler.schedule(func, schedule, **kwargs)
