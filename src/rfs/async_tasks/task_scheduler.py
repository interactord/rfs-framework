"""
RFS v4.1 Task Scheduler System
작업 스케줄링 및 실행 관리 시스템

주요 기능:
- TaskScheduler: 작업 스케줄링 엔진
- ScheduleConfig: 스케줄 설정 관리
- ScheduleType: 스케줄 유형 분류
"""

import asyncio
import heapq
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import weakref

from ..core.result import Result, Success, Failure
from ..core.config import get_config
from .task_definition import TaskDefinition, TaskContext, TaskType, get_task_definition
from .task_manager import AsyncTaskManager, TaskPriority, TaskStatus


class ScheduleType(Enum):
    """스케줄 유형"""
    ONCE = "once"               # 한 번만 실행
    INTERVAL = "interval"       # 주기적 실행
    CRON = "cron"              # 크론 표현식
    DELAYED = "delayed"         # 지연 실행
    RECURRING = "recurring"     # 반복 실행
    DEPENDENCY = "dependency"   # 의존성 기반


@dataclass
class ScheduleConfig:
    """스케줄 설정"""
    task_name: str
    schedule_type: ScheduleType
    
    # 시간 기반 스케줄
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    interval: Optional[timedelta] = None
    delay: Optional[timedelta] = None
    cron_expression: Optional[str] = None
    
    # 실행 제한
    max_runs: Optional[int] = None
    run_count: int = 0
    
    # 조건부 실행
    conditions: List[Callable] = field(default_factory=list)
    
    # 메타데이터
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def should_run(self, current_time: datetime) -> bool:
        """실행 여부 확인"""
        if not self.enabled:
            return False
        
        # 실행 횟수 제한 확인
        if self.max_runs is not None and self.run_count >= self.max_runs:
            return False
        
        # 시간 범위 확인
        if self.start_time and current_time < self.start_time:
            return False
        
        if self.end_time and current_time > self.end_time:
            return False
        
        return True
    
    def get_next_run_time(self, from_time: Optional[datetime] = None) -> Optional[datetime]:
        """다음 실행 시간 계산"""
        if not from_time:
            from_time = datetime.now()
        
        if not self.should_run(from_time):
            return None
        
        if self.schedule_type == ScheduleType.ONCE:
            if self.run_count > 0:
                return None
            return self.start_time or from_time
        
        elif self.schedule_type == ScheduleType.DELAYED:
            if self.run_count > 0:
                return None
            return from_time + (self.delay or timedelta(seconds=0))
        
        elif self.schedule_type == ScheduleType.INTERVAL:
            if not self.interval:
                return None
            
            next_time = from_time + self.interval
            if self.end_time and next_time > self.end_time:
                return None
            
            return next_time
        
        elif self.schedule_type == ScheduleType.CRON:
            return self._parse_cron_next_time(from_time)
        
        elif self.schedule_type == ScheduleType.RECURRING:
            if not self.interval:
                return None
            return from_time + self.interval
        
        return None
    
    def _parse_cron_next_time(self, from_time: datetime) -> Optional[datetime]:
        """크론 표현식에서 다음 실행 시간 계산"""
        if not self.cron_expression:
            return None
        
        # 간단한 크론 파싱 (실제로는 croniter 등 라이브러리 사용 권장)
        try:
            parts = self.cron_expression.split()
            if len(parts) != 5:
                return None
            
            minute, hour, day, month, weekday = parts
            
            # 매시간 정각 (0 * * * *)
            if minute == "0" and hour == "*":
                next_hour = from_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                return next_hour
            
            # 매일 특정 시간 (0 9 * * *)
            if minute == "0" and hour.isdigit():
                target_hour = int(hour)
                next_run = from_time.replace(hour=target_hour, minute=0, second=0, microsecond=0)
                if next_run <= from_time:
                    next_run += timedelta(days=1)
                return next_run
            
        except Exception:
            pass
        
        return None
    
    def increment_run_count(self) -> None:
        """실행 횟수 증가"""
        self.run_count += 1


@dataclass
class ScheduledTask:
    """스케줄된 작업 정보"""
    config: ScheduleConfig
    next_run_time: datetime
    task_definition: TaskDefinition
    
    def __lt__(self, other: "ScheduledTask") -> bool:
        """우선순위 큐를 위한 비교"""
        return self.next_run_time < other.next_run_time


class TaskScheduler:
    """작업 스케줄러"""
    
    def __init__(self, task_manager: Optional[AsyncTaskManager] = None):
        self.task_manager = task_manager or AsyncTaskManager()
        self._schedules: Dict[str, ScheduleConfig] = {}
        self._scheduled_tasks: List[ScheduledTask] = []  # 힙 큐
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)  # task -> dependencies
        self._dependents: Dict[str, Set[str]] = defaultdict(set)    # task -> dependents
        self._completed_tasks: Set[str] = set()
        
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        self.logger = logging.getLogger(__name__)
        
        # 통계
        self._stats = {
            "scheduled_count": 0,
            "executed_count": 0,
            "failed_count": 0,
            "skipped_count": 0
        }
    
    async def start(self) -> None:
        """스케줄러 시작"""
        if self._running:
            return
        
        self._running = True
        self._shutdown_event.clear()
        
        # 메인 스케줄러 루프 시작
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        self.logger.info("Task scheduler started")
    
    async def stop(self) -> None:
        """스케줄러 중지"""
        if not self._running:
            return
        
        self._running = False
        self._shutdown_event.set()
        
        # 실행 중인 작업들 취소
        for task in self._running_tasks.values():
            if not task.done():
                task.cancel()
        
        # 모든 작업 완료 대기
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        
        # 스케줄러 태스크 취소
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Task scheduler stopped")
    
    def schedule_task(
        self,
        task_name: str,
        schedule_type: ScheduleType,
        **schedule_kwargs
    ) -> Result[None, str]:
        """작업 스케줄 등록"""
        try:
            # 작업 정의 확인
            task_def = get_task_definition(task_name)
            if not task_def:
                return Failure(f"Task definition not found: {task_name}")
            
            # 스케줄 설정 생성
            config = ScheduleConfig(
                task_name=task_name,
                schedule_type=schedule_type,
                **schedule_kwargs
            )
            
            # 의존성 처리
            if task_def.dependencies:
                for dep in task_def.dependencies:
                    self._dependencies[task_name].add(dep)
                    self._dependents[dep].add(task_name)
            
            # 스케줄 등록
            self._schedules[task_name] = config
            
            # 다음 실행 시간 계산 및 큐에 추가
            self._schedule_next_run(task_name, config, task_def)
            
            self._stats["scheduled_count"] += 1
            
            self.logger.info(f"Task scheduled: {task_name} ({schedule_type.value})")
            return Success(None)
            
        except Exception as e:
            return Failure(f"Failed to schedule task: {e}")
    
    def unschedule_task(self, task_name: str) -> Result[None, str]:
        """작업 스케줄 해제"""
        try:
            if task_name not in self._schedules:
                return Failure(f"Task not scheduled: {task_name}")
            
            # 스케줄 제거
            del self._schedules[task_name]
            
            # 스케줄된 작업 큐에서 제거
            self._scheduled_tasks = [
                task for task in self._scheduled_tasks
                if task.config.task_name != task_name
            ]
            heapq.heapify(self._scheduled_tasks)
            
            # 실행 중인 작업 취소
            if task_name in self._running_tasks:
                self._running_tasks[task_name].cancel()
                del self._running_tasks[task_name]
            
            # 의존성 제거
            if task_name in self._dependencies:
                for dep in self._dependencies[task_name]:
                    self._dependents[dep].discard(task_name)
                del self._dependencies[task_name]
            
            if task_name in self._dependents:
                for dependent in self._dependents[task_name]:
                    self._dependencies[dependent].discard(task_name)
                del self._dependents[task_name]
            
            self.logger.info(f"Task unscheduled: {task_name}")
            return Success(None)
            
        except Exception as e:
            return Failure(f"Failed to unschedule task: {e}")
    
    def _schedule_next_run(
        self,
        task_name: str,
        config: ScheduleConfig,
        task_def: TaskDefinition
    ) -> None:
        """다음 실행을 스케줄"""
        next_time = config.get_next_run_time()
        if next_time:
            scheduled_task = ScheduledTask(
                config=config,
                next_run_time=next_time,
                task_definition=task_def
            )
            heapq.heappush(self._scheduled_tasks, scheduled_task)
    
    async def _scheduler_loop(self) -> None:
        """메인 스케줄러 루프"""
        while self._running and not self._shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                # 실행할 작업들 확인
                ready_tasks = []
                while (self._scheduled_tasks and 
                       self._scheduled_tasks[0].next_run_time <= current_time):
                    ready_tasks.append(heapq.heappop(self._scheduled_tasks))
                
                # 의존성 체크 후 실행
                for scheduled_task in ready_tasks:
                    await self._execute_scheduled_task(scheduled_task)
                
                # 완료된 작업 정리
                await self._cleanup_completed_tasks()
                
                # 짧은 대기
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
                    break
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(1.0)
    
    async def _execute_scheduled_task(self, scheduled_task: ScheduledTask) -> None:
        """스케줄된 작업 실행"""
        task_name = scheduled_task.config.task_name
        
        try:
            # 의존성 확인
            if not self._are_dependencies_met(task_name):
                # 의존성이 충족되지 않은 경우 잠시 후 재시도
                scheduled_task.next_run_time = datetime.now() + timedelta(seconds=10)
                heapq.heappush(self._scheduled_tasks, scheduled_task)
                self._stats["skipped_count"] += 1
                return
            
            # 조건 확인
            context = TaskContext(
                task_id=f"{task_name}_{datetime.now().isoformat()}",
                task_name=task_name,
                task_type=scheduled_task.task_definition.task_type,
                execution_time=datetime.now()
            )
            
            if not scheduled_task.task_definition.can_execute(context):
                self._stats["skipped_count"] += 1
                self.logger.info(f"Task skipped (conditions not met): {task_name}")
            else:
                # 작업 실행
                task_info = await self.task_manager.submit_task(
                    task_name,
                    TaskPriority.NORMAL,  # 스케줄된 작업은 기본 우선순위
                    context=context
                )
                
                if task_info:
                    self._running_tasks[task_name] = asyncio.create_task(
                        self._monitor_task_execution(task_name, task_info.task_id)
                    )
                    self._stats["executed_count"] += 1
                else:
                    self._stats["failed_count"] += 1
            
            # 다음 실행 스케줄
            scheduled_task.config.increment_run_count()
            self._schedule_next_run(
                task_name,
                scheduled_task.config,
                scheduled_task.task_definition
            )
            
        except Exception as e:
            self.logger.error(f"Failed to execute scheduled task {task_name}: {e}")
            self._stats["failed_count"] += 1
    
    def _are_dependencies_met(self, task_name: str) -> bool:
        """의존성 충족 여부 확인"""
        dependencies = self._dependencies.get(task_name, set())
        return all(dep in self._completed_tasks for dep in dependencies)
    
    async def _monitor_task_execution(self, task_name: str, task_id: str) -> None:
        """작업 실행 모니터링"""
        try:
            # 작업 완료까지 대기
            while True:
                task_info = self.task_manager.get_task_info(task_id)
                if not task_info:
                    break
                
                if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    if task_info.status == TaskStatus.COMPLETED:
                        self._completed_tasks.add(task_name)
                        
                        # 의존하는 작업들에게 알림
                        await self._notify_dependents(task_name)
                    
                    break
                
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.logger.error(f"Error monitoring task {task_name}: {e}")
        finally:
            if task_name in self._running_tasks:
                del self._running_tasks[task_name]
    
    async def _notify_dependents(self, completed_task: str) -> None:
        """의존하는 작업들에게 완료 알림"""
        dependents = self._dependents.get(completed_task, set())
        for dependent in dependents:
            if self._are_dependencies_met(dependent):
                # 의존성이 충족된 작업을 즉시 실행 가능하도록 스케줄
                config = self._schedules.get(dependent)
                task_def = get_task_definition(dependent)
                
                if config and task_def:
                    scheduled_task = ScheduledTask(
                        config=config,
                        next_run_time=datetime.now(),
                        task_definition=task_def
                    )
                    heapq.heappush(self._scheduled_tasks, scheduled_task)
    
    async def _cleanup_completed_tasks(self) -> None:
        """완료된 작업 정리"""
        completed_tasks = []
        for task_name, task in self._running_tasks.items():
            if task.done():
                completed_tasks.append(task_name)
        
        for task_name in completed_tasks:
            del self._running_tasks[task_name]
    
    def get_schedule_info(self, task_name: str) -> Optional[Dict[str, Any]]:
        """스케줄 정보 조회"""
        config = self._schedules.get(task_name)
        if not config:
            return None
        
        next_run_time = config.get_next_run_time()
        
        return {
            "task_name": task_name,
            "schedule_type": config.schedule_type.value,
            "enabled": config.enabled,
            "run_count": config.run_count,
            "max_runs": config.max_runs,
            "next_run_time": next_run_time.isoformat() if next_run_time else None,
            "dependencies": list(self._dependencies.get(task_name, set())),
            "dependents": list(self._dependents.get(task_name, set()))
        }
    
    def list_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """스케줄된 작업 목록"""
        return [
            self.get_schedule_info(task_name)
            for task_name in self._schedules.keys()
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """스케줄러 통계"""
        return {
            **self._stats,
            "active_schedules": len(self._schedules),
            "pending_tasks": len(self._scheduled_tasks),
            "running_tasks": len(self._running_tasks),
            "completed_tasks": len(self._completed_tasks)
        }


# 전역 스케줄러 인스턴스
_default_scheduler: Optional[TaskScheduler] = None


def create_scheduler(task_manager: Optional[AsyncTaskManager] = None) -> TaskScheduler:
    """스케줄러 생성"""
    return TaskScheduler(task_manager)


def get_default_scheduler() -> TaskScheduler:
    """기본 스케줄러 조회"""
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = TaskScheduler()
    return _default_scheduler


async def schedule_task(
    task_name: str,
    schedule_type: ScheduleType,
    **kwargs
) -> Result[None, str]:
    """작업 스케줄 등록 (편의 함수)"""
    scheduler = get_default_scheduler()
    return scheduler.schedule_task(task_name, schedule_type, **kwargs)