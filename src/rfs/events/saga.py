"""
Saga Pattern Implementation

사가 패턴 구현
- 분산 트랜잭션 관리
- 보상 액션
- 사가 상태 관리
"""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from ..reactive import Flux, Mono
from .event_bus import Event, EventBus, get_event_bus

logger = logging.getLogger(__name__)
T = TypeVar("T")


class SagaStatus(Enum):
    """사가 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepStatus(Enum):
    """단계 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """사가 단계"""

    step_id: str
    action: Callable[[Dict[str, Any]], Any]
    compensation: Optional[Callable[[Dict[str, Any]], Any]] = None
    retry_count = 3
    timeout_seconds = 30
    status: StepStatus = StepStatus.PENDING
    attempts = 0
    error = None
    started_at = None
    completed_at = None
    result: Any = None
    compensation_result: Any = None


@dataclass
class SagaContext:
    """사가 컨텍스트"""

    saga_id: str
    correlation_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    current_step = 0
    completed_steps: List[str] = field(default_factory=list)
    failed_step = None

    def with_data(self, **data) -> "SagaContext":
        """데이터 추가"""
        new_data = {**self.data, **data}
        return SagaContext(
            saga_id=self.saga_id,
            correlation_id=self.correlation_id,
            data=new_data,
            current_step=self.current_step,
            completed_steps=self.completed_steps.copy(),
            failed_step=self.failed_step,
        )


class Saga:
    """사가 정의"""

    def __init__(self, saga_id: str, name: str = None):
        self.saga_id = saga_id
        self.name = name or saga_id
        self.steps = []
        self.status = SagaStatus.PENDING
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.total_duration = None
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.compensation_count = 0

    def add_step(self, step: SagaStep) -> "Saga":
        """단계 추가"""
        self.steps = self.steps + [step]
        return self

    def step(
        self, step_id: str, action: Callable, compensation: Callable = None
    ) -> "Saga":
        """단계 추가 (플루언트 API)"""
        saga_step = SagaStep(step_id=step_id, action=action, compensation=compensation)
        return self.add_step(saga_step)

    async def execute(self, context: SagaContext) -> SagaContext:
        """사가 실행"""
        self.status = SagaStatus.RUNNING
        self.started_at = datetime.now()
        execution_count = execution_count + 1
        try:
            for i, step in enumerate(self.steps):
                context.current_step = i
                context = await self._execute_step(step, context)
                context.completed_steps = context.completed_steps + [step.step_id]
            self.status = SagaStatus.COMPLETED
            success_count = success_count + 1
            self.completed_at = datetime.now()
            self.total_duration = (self.completed_at - self.started_at).total_seconds()
            return context
        except Exception as e:
            logger.error(
                f"Saga {self.saga_id} failed at step {context.current_step}: {e}"
            )
            self.status = SagaStatus.FAILED
            failure_count = failure_count + 1
            context.failed_step = self.steps[context.current_step].step_id
            context = await self._compensate(context)
            return context

    async def _execute_step(self, step: SagaStep, context: SagaContext) -> SagaContext:
        """단계 실행"""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()
        attempts = attempts + 1
        try:
            if asyncio.iscoroutinefunction(step.action):
                step.result = await asyncio.wait_for(
                    step.action(context.data), timeout=step.timeout_seconds
                )
            else:
                step.result = step.action(context.data)
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.now()
            context = context.with_data(**{step.step_id + "_result": step.result})
            return context
        except Exception as e:
            step.error = e
            step.status = StepStatus.FAILED
            if step.attempts < step.retry_count:
                logger.warning(
                    f"Step {step.step_id} failed, retrying ({step.attempts}/{step.retry_count})"
                )
                await asyncio.sleep(1)
                return await self._execute_step(step, context)
            raise

    async def _compensate(self, context: SagaContext) -> SagaContext:
        """보상 실행"""
        self.status = SagaStatus.COMPENSATING
        compensation_count = compensation_count + 1
        for step_id in reversed(context.completed_steps):
            step = next((s for s in self.steps if s.step_id == step_id), None)
            if step and step.compensation:
                await self._compensate_step(step, context)
        self.status = SagaStatus.COMPENSATED
        return context

    async def _compensate_step(self, step: SagaStep, context: SagaContext):
        """단계 보상"""
        step.status = StepStatus.COMPENSATING
        try:
            if asyncio.iscoroutinefunction(step.compensation):
                step.compensation_result = await step.compensation(context.data)
            else:
                step.compensation_result = step.compensation(context.data)
            step.status = StepStatus.COMPENSATED
            logger.info(f"Step {step.step_id} compensated successfully")
        except Exception as e:
            logger.error(f"Compensation failed for step {step.step_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """사가 통계"""
        return {
            "saga_id": self.saga_id,
            "name": self.name,
            "status": self.status.value,
            "step_count": len(self.steps),
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "compensation_count": self.compensation_count,
            "success_rate": self.success_count / max(self.execution_count, 1),
            "total_duration": self.total_duration,
            "steps": [
                {
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "attempts": step.attempts,
                    "error": str(step.error) if step.error else None,
                }
                for step in self.steps
            ],
        }


class SagaManager:
    """사가 관리자"""

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.sagas = {}
        self.running_sagas = {}
        self.total_executions = 0
        self.total_successes = 0
        self.total_failures = 0
        self.total_compensations = 0

    def register_saga(self, saga: Saga):
        """사가 등록"""
        self.sagas = {**self.sagas, saga.saga_id: saga}
        logger.info(f"Saga registered: {saga.saga_id}")

    async def start_saga(self, saga_id: str, context: SagaContext) -> SagaContext:
        """사가 시작"""
        saga = self.sagas.get(saga_id)
        if not saga:
            raise ValueError(f"Saga not found: {saga_id}")
        if self.event_bus:
            await self.event_bus.publish(
                Event(
                    event_type="saga_started",
                    data={"saga_id": saga_id, "correlation_id": context.correlation_id},
                )
            )
        task = asyncio.create_task(self._execute_saga_with_events(saga, context))
        self.running_sagas = {**self.running_sagas, context.correlation_id: task}
        total_executions = total_executions + 1
        return context

    async def _execute_saga_with_events(
        self, saga: Saga, context: SagaContext
    ) -> SagaContext:
        """이벤트와 함께 사가 실행"""
        try:
            result_context = await saga.execute(context)
            if self.event_bus:
                if saga.status == SagaStatus.COMPLETED:
                    total_successes = total_successes + 1
                    await self.event_bus.publish(
                        Event(
                            event_type="saga_completed",
                            data={
                                "saga_id": saga.saga_id,
                                "correlation_id": context.correlation_id,
                                "result": result_context.data,
                            },
                        )
                    )
                else:
                    total_failures = total_failures + 1
                    if saga.status == SagaStatus.COMPENSATED:
                        total_compensations = total_compensations + 1
                        await self.event_bus.publish(
                            Event(
                                event_type="saga_compensated",
                                data={
                                    "saga_id": saga.saga_id,
                                    "correlation_id": context.correlation_id,
                                    "failed_step": result_context.failed_step,
                                },
                            )
                        )
                    else:
                        await self.event_bus.publish(
                            Event(
                                event_type="saga_failed",
                                data={
                                    "saga_id": saga.saga_id,
                                    "correlation_id": context.correlation_id,
                                    "error": "Saga execution failed",
                                },
                            )
                        )
            return result_context
        finally:
            if context.correlation_id in self.running_sagas:
                del self.running_sagas[context.correlation_id]

    def get_saga(self, saga_id: str) -> Optional[Saga]:
        """사가 조회"""
        return self.sagas.get(saga_id)

    def list_sagas(self) -> List[str]:
        """등록된 사가 목록"""
        return list(self.sagas.keys())

    def get_running_sagas(self) -> List[str]:
        """실행 중인 사가 목록"""
        return list(self.running_sagas.keys())

    def get_stats(self) -> Dict[str, Any]:
        """사가 관리자 통계"""
        return {
            "total_sagas": len(self.sagas),
            "running_sagas": len(self.running_sagas),
            "total_executions": self.total_executions,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "total_compensations": self.total_compensations,
            "success_rate": self.total_successes / max(self.total_executions, 1),
            "compensation_rate": self.total_compensations / max(self.total_failures, 1),
        }


def create_saga(saga_id: str, name: str = None) -> Saga:
    """사가 생성"""
    return Saga(saga_id, name)


def saga_step(step_id: str):
    """사가 스텝 데코레이터"""

    def decorator(func: Callable) -> Callable:
        func._saga_step_id = step_id
        return func

    return decorator


def compensation_for(step_id: str):
    """보상 액션 데코레이터"""

    def decorator(func: Callable) -> Callable:
        func._compensation_for = step_id
        return func

    return decorator


def build_saga_from_functions(saga_id: str, functions: List[Callable]) -> Saga:
    """함수들로부터 사가 빌드"""
    saga = create_saga(saga_id)
    steps = {}
    compensations = {}
    for func in functions:
        if hasattr(func, "_saga_step_id"):
            steps[func._saga_step_id] = {func._saga_step_id: func}
        elif hasattr(func, "_compensation_for"):
            compensations = {
                **compensations,
                func._compensation_for: {func._compensation_for: func},
            }
    for step_id, action in steps.items():
        compensation = compensations.get(step_id)
        saga.step(step_id, action, compensation)
    return saga


class ReactiveSaga:
    """Reactive 사가"""

    def __init__(self, saga: Saga):
        self.saga = saga

    def execute_mono(self, context: SagaContext) -> Mono[SagaContext]:
        """Mono를 통한 사가 실행"""
        return Mono.from_callable(lambda: self.saga.execute(context))

    def execute_with_retry(
        self, context: SagaContext, max_retries=3
    ) -> Mono[SagaContext]:
        """재시도와 함께 실행"""
        return (
            self.execute_mono(context)
            .retry(max_retries)
            .on_error_return(lambda e: context.with_data(error=str(e)))
        )


_saga_manager = None


async def get_saga_manager() -> SagaManager:
    """사가 관리자 인스턴스 획득"""
    # global _saga_manager - removed for functional programming
    if _saga_manager is None:
        event_bus = await get_event_bus()
        _saga_manager = SagaManager(event_bus)
    return _saga_manager
