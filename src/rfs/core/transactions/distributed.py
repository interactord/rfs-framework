"""
Distributed Transaction Support for RFS Framework

분산 트랜잭션 지원 - 2PC, Saga 패턴
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from ...events import Event, EventBus, get_event_bus
from ..result import Failure, Result, Success
from .base import (
    TransactionError,
    TransactionMetadata,
    TransactionOptions,
    TransactionStatus,
)
from .manager import TransactionManager, get_transaction_manager

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ParticipantStatus(Enum):
    """참여자 상태"""

    UNKNOWN = "unknown"
    PREPARED = "prepared"
    COMMITTED = "committed"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


@dataclass
class ParticipantInfo:
    """트랜잭션 참여자 정보"""

    participant_id: str
    resource_name: str
    status: ParticipantStatus = ParticipantStatus.UNKNOWN
    prepared_at = None
    committed_at = None
    aborted_at = None
    vote = None
    data: Dict[str, Any] = field(default_factory=dict)


class TransactionCoordinator(ABC):
    """트랜잭션 코디네이터 인터페이스"""

    @abstractmethod
    def prepare(self, transaction_id: str) -> Result[bool, str]:
        """준비 단계"""
        pass

    @abstractmethod
    def commit(self, transaction_id: str) -> Result[None, str]:
        """커밋 단계"""
        pass

    @abstractmethod
    def abort(self, transaction_id: str) -> Result[None, str]:
        """중단 단계"""
        pass


class TwoPhaseCommit:
    """
    2단계 커밋 프로토콜

    분산 트랜잭션을 위한 2PC 구현
    """

    def __init__(self, timeout: timedelta = timedelta(seconds=30)):
        self.participants = {}
        self.coordinators = {}
        self.timeout = timeout
        self.transaction_id = str(uuid.uuid4())
        self.status = TransactionStatus.ACTIVE

    def register_participant(
        self,
        participant_id: str,
        coordinator: TransactionCoordinator,
        resource_name=None,
    ):
        """참여자 등록"""
        self.participants = {
            **self.participants,
            participant_id: ParticipantInfo(
                participant_id=participant_id,
                resource_name=resource_name or participant_id,
            ),
        }
        self.coordinators = {**self.coordinators, participant_id: coordinator}

    def execute(self) -> Result[None, str]:
        """
        2PC 실행

        Phase 1: Prepare (투표)
        Phase 2: Commit/Abort (결정)
        """
        prepare_result = self._prepare_phase()
        if type(prepare_result).__name__ == "Failure":
            self._abort_all()
            return Failure(f"Prepare phase failed: {prepare_result.error}")
        all_voted_commit = all((p.vote for p in self.participants.values()))
        if not all_voted_commit:
            self._abort_all()
            return Failure("One or more participants voted to abort")
        commit_result = self._commit_phase()
        if type(commit_result).__name__ == "Failure":
            logger.error(f"Commit phase failed: {commit_result.error}")
            self.status = TransactionStatus.FAILED
            return Failure(f"Commit phase failed: {commit_result.error}")
        self.status = TransactionStatus.COMMITTED
        return Success(None)

    def _prepare_phase(self) -> Result[None, str]:
        """준비 단계 실행"""
        errors = []
        for participant_id, participant in self.participants.items():
            coordinator = self.coordinators[participant_id]
            try:
                result = coordinator.prepare(self.transaction_id)
                if type(result).__name__ == "Success":
                    participant.vote = result.value
                    participant.status = ParticipantStatus.PREPARED
                    participant.prepared_at = datetime.now()
                else:
                    participant.vote = False
                    participant.status = ParticipantStatus.ABORTED
                    errors = errors + [f"{participant_id}: {result.error}"]
            except Exception as e:
                participant.vote = False
                participant.status = ParticipantStatus.ABORTED
                errors = errors + [f"{participant_id}: {str(e)}"]
        if errors:
            return Failure("; ".join(errors))
        return Success(None)

    def _commit_phase(self) -> Result[None, str]:
        """커밋 단계 실행"""
        errors = []
        for participant_id, participant in self.participants.items():
            if participant.status != ParticipantStatus.PREPARED:
                continue
            coordinator = self.coordinators[participant_id]
            try:
                result = coordinator.commit(self.transaction_id)
                if type(result).__name__ == "Success":
                    participant.status = ParticipantStatus.COMMITTED
                    participant.committed_at = datetime.now()
                else:
                    errors = errors + [f"{participant_id}: {result.error}"]
            except Exception as e:
                errors = errors + [f"{participant_id}: {str(e)}"]
        if errors:
            return Failure("; ".join(errors))
        return Success(None)

    def _abort_all(self):
        """모든 참여자 중단"""
        for participant_id, participant in self.participants.items():
            if participant.status in [
                ParticipantStatus.COMMITTED,
                ParticipantStatus.ABORTED,
            ]:
                continue
            coordinator = self.coordinators[participant_id]
            try:
                coordinator.abort(self.transaction_id)
                participant.status = ParticipantStatus.ABORTED
                participant.aborted_at = datetime.now()
            except Exception as e:
                logger.error(f"Failed to abort participant {participant_id}: {e}")


@dataclass
class SagaStep:
    """Saga 단계"""

    name: str
    action: Callable[..., Result[Any, str]]
    compensation: Callable[..., Result[None, str]]
    data: Optional[Dict[str, Any]] = None
    completed = False
    compensated = False
    result = None


class SagaTransaction:
    """
    Saga 패턴 트랜잭션

    보상 트랜잭션을 통한 분산 트랜잭션 관리
    """

    def __init__(self, name="saga"):
        self.name = name
        self.saga_id = str(uuid.uuid4())
        self.steps = []
        self.completed_steps = []
        self.status = TransactionStatus.ACTIVE
        self.event_bus = get_event_bus()

    def add_step(
        self,
        name: str,
        action: Callable[..., Result[Any, str]],
        compensation: Callable[..., Result[None, str]],
        data: Optional[Dict[str, Any]] = None,
    ):
        """Saga 단계 추가"""
        step = SagaStep(
            name=name, action=action, compensation=compensation, data=data or {}
        )
        self.steps = self.steps + [step]

    def execute(self) -> Result[Any, str]:
        """
        Saga 실행

        각 단계를 순차적으로 실행하고,
        실패 시 보상 트랜잭션 실행
        """
        results = []
        self.event_bus.publish(
            Event(type="saga.started", source=self.name, data={"saga_id": self.saga_id})
        )
        for step in self.steps:
            try:
                logger.info(f"Executing saga step: {step.name}")
                self.event_bus.publish(
                    Event(
                        type="saga.step.started",
                        source=self.name,
                        data={"saga_id": self.saga_id, "step": step.name},
                    )
                )
                result = step.action(**step.data)
                if type(result).__name__ == "Success":
                    step.completed = True
                    step.result = result.value
                    self.completed_steps = self.completed_steps + [step]
                    results = results + [result.value]
                    self.event_bus.publish(
                        Event(
                            type="saga.step.completed",
                            source=self.name,
                            data={
                                "saga_id": self.saga_id,
                                "step": step.name,
                                "result": result.value,
                            },
                        )
                    )
                else:
                    logger.error(f"Saga step {step.name} failed: {result.error}")
                    self.event_bus.publish(
                        Event(
                            type="saga.step.failed",
                            source=self.name,
                            data={
                                "saga_id": self.saga_id,
                                "step": step.name,
                                "error": result.error,
                            },
                        )
                    )
                    compensation_result = self._compensate()
                    if type(compensation_result).__name__ == "Failure":
                        self.status = TransactionStatus.FAILED
                        return Failure(
                            f"Step {step.name} failed and compensation failed: {result.error}, {compensation_result.error}"
                        )
                    self.status = TransactionStatus.ROLLED_BACK
                    return Failure(f"Saga failed at step {step.name}: {result.error}")
            except Exception as e:
                logger.error(f"Saga step {step.name} raised exception: {e}")
                compensation_result = self._compensate()
                if type(compensation_result).__name__ == "Failure":
                    self.status = TransactionStatus.FAILED
                    return Failure(
                        f"Step {step.name} failed with exception and compensation failed: {str(e)}, {compensation_result.error}"
                    )
                self.status = TransactionStatus.ROLLED_BACK
                return Failure(f"Saga failed at step {step.name}: {str(e)}")
        self.event_bus.publish(
            Event(
                type="saga.completed",
                source=self.name,
                data={"saga_id": self.saga_id, "results": results},
            )
        )
        self.status = TransactionStatus.COMMITTED
        return Success(results)

    def _compensate(self) -> Result[None, str]:
        """보상 트랜잭션 실행"""
        logger.info(f"Starting compensation for saga {self.saga_id}")
        self.event_bus.publish(
            Event(
                type="saga.compensation.started",
                source=self.name,
                data={"saga_id": self.saga_id},
            )
        )
        errors = []
        for step in reversed(self.completed_steps):
            if step.compensated:
                continue
            try:
                logger.info(f"Compensating step: {step.name}")
                self.event_bus.publish(
                    Event(
                        type="saga.compensation.step",
                        source=self.name,
                        data={"saga_id": self.saga_id, "step": step.name},
                    )
                )
                compensation_data = step.data.copy()
                if step.result:
                    compensation_data = {
                        **compensation_data,
                        "result": {"result": step.result},
                    }
                result = step.compensation(**compensation_data)
                if type(result).__name__ == "Success":
                    step.compensated = True
                else:
                    errors = errors + [
                        f"Failed to compensate {step.name}: {result.error}"
                    ]
            except Exception as e:
                errors = errors + [
                    f"Exception during compensation of {step.name}: {str(e)}"
                ]
        if errors:
            self.event_bus.publish(
                Event(
                    type="saga.compensation.failed",
                    source=self.name,
                    data={"saga_id": self.saga_id, "errors": errors},
                )
            )
            return Failure("; ".join(errors))
        self.event_bus.publish(
            Event(
                type="saga.compensation.completed",
                source=self.name,
                data={"saga_id": self.saga_id},
            )
        )
        return Success(None)

    async def execute_async(self) -> Result[Any, str]:
        """비동기 Saga 실행"""
        results = []
        for step in self.steps:
            try:
                if asyncio.iscoroutinefunction(step.action):
                    result = await step.action(**step.data)
                else:
                    result = step.action(**step.data)
                if type(result).__name__ == "Success":
                    step.completed = True
                    step.result = result.value
                    self.completed_steps = self.completed_steps + [step]
                    results = results + [result.value]
                else:
                    compensation_result = await self._compensate_async()
                    if type(compensation_result).__name__ == "Failure":
                        self.status = TransactionStatus.FAILED
                        return Failure(
                            f"Step {step.name} failed and compensation failed: {result.error}, {compensation_result.error}"
                        )
                    self.status = TransactionStatus.ROLLED_BACK
                    return Failure(f"Saga failed at step {step.name}: {result.error}")
            except Exception as e:
                compensation_result = await self._compensate_async()
                if type(compensation_result).__name__ == "Failure":
                    self.status = TransactionStatus.FAILED
                    return Failure(
                        f"Step {step.name} failed with exception and compensation failed: {str(e)}, {compensation_result.error}"
                    )
                self.status = TransactionStatus.ROLLED_BACK
                return Failure(f"Saga failed at step {step.name}: {str(e)}")
        self.status = TransactionStatus.COMMITTED
        return Success(results)

    async def _compensate_async(self) -> Result[None, str]:
        """비동기 보상 트랜잭션 실행"""
        errors = []
        for step in reversed(self.completed_steps):
            if step.compensated:
                continue
            try:
                compensation_data = step.data.copy()
                if step.result:
                    compensation_data = {
                        **compensation_data,
                        "result": {"result": step.result},
                    }
                if asyncio.iscoroutinefunction(step.compensation):
                    result = await step.compensation(**compensation_data)
                else:
                    result = step.compensation(**compensation_data)
                if type(result).__name__ == "Success":
                    step.compensated = True
                else:
                    errors = errors + [
                        f"Failed to compensate {step.name}: {result.error}"
                    ]
            except Exception as e:
                errors = errors + [
                    f"Exception during compensation of {step.name}: {str(e)}"
                ]
        if errors:
            return Failure("; ".join(errors))
        return Success(None)


class DistributedTransaction:
    """
    분산 트랜잭션 매니저

    2PC와 Saga 패턴을 통합 관리
    """

    def __init__(self):
        self.transaction_manager = get_transaction_manager()
        self.active_2pc = {}
        self.active_sagas = {}

    def create_2pc(
        self,
        transaction_id=None,
        timeout: timedelta = timedelta(seconds=30),
    ) -> TwoPhaseCommit:
        """2PC 트랜잭션 생성"""
        tx_id = transaction_id or str(uuid.uuid4())
        tpc = TwoPhaseCommit(timeout=timeout)
        self.active_2pc = {**self.active_2pc, tx_id: tpc}
        return tpc

    def create_saga(self, name="saga", saga_id=None) -> SagaTransaction:
        """Saga 트랜잭션 생성"""
        saga = SagaTransaction(name=name)
        if saga_id:
            saga.saga_id = saga_id
        self.active_sagas = {**self.active_sagas, saga.saga_id: saga}
        return saga

    def get_2pc(self, transaction_id: str) -> Optional[TwoPhaseCommit]:
        """2PC 트랜잭션 조회"""
        return self.active_2pc.get(transaction_id)

    def get_saga(self, saga_id: str) -> Optional[SagaTransaction]:
        """Saga 트랜잭션 조회"""
        return self.active_sagas.get(saga_id)

    def cleanup(self):
        """완료된 트랜잭션 정리"""
        completed_2pc = [
            tx_id
            for tx_id, tpc in self.active_2pc.items()
            if tpc.status
            in [TransactionStatus.COMMITTED, TransactionStatus.ROLLED_BACK]
        ]
        for tx_id in completed_2pc:
            del self.active_2pc[tx_id]
        completed_sagas = [
            saga_id
            for saga_id, saga in self.active_sagas.items()
            if saga.status
            in [TransactionStatus.COMMITTED, TransactionStatus.ROLLED_BACK]
        ]
        for saga_id in completed_sagas:
            del self.active_sagas[saga_id]


def distributed_transaction(use_2pc=False):
    """
    분산 트랜잭션 데코레이터

    Args:
        use_2pc: 2PC 사용 여부 (False면 Saga 사용)
    """

    def decorator(func: Callable) -> Callable:

        def wrapper(*args, **kwargs):
            dt = DistributedTransaction()
            if use_2pc:
                tpc = dt.create_2pc()
                kwargs["tpc"] = {"tpc": tpc}
                result = func(*args, **kwargs)
                if result:
                    exec_result = tpc.execute()
                    if type(exec_result).__name__ == "Failure":
                        raise TransactionError(exec_result.error)
            else:
                saga = dt.create_saga(name=func.__name__)
                kwargs["saga"] = {"saga": saga}
                result = func(*args, **kwargs)
                if result:
                    exec_result = saga.execute()
                    if type(exec_result).__name__ == "Failure":
                        raise TransactionError(exec_result.error)
            return result

        return wrapper

    return decorator


def saga_step(name: str, compensation: Callable):
    """
    Saga 단계 데코레이터

    Args:
        name: 단계 이름
        compensation: 보상 함수
    """

    def decorator(action: Callable) -> Callable:
        action._saga_step = True
        action._saga_name = name
        action._saga_compensation = compensation
        return action

    return decorator


def compensate(func: Callable) -> Callable:
    """보상 함수 표시 데코레이터"""
    func._is_compensation = True
    return func


class CompensationAction:
    """보상 액션"""

    def __init__(self, action: Callable, data: Optional[Dict[str, Any]] = None):
        self.action = action
        self.data = data or {}

    def execute(self) -> Result[None, str]:
        """보상 실행"""
        try:
            result = self.action(**self.data)
            if type(result).__name__ == "Result":
                return result
            return Success(None)
        except Exception as e:
            return Failure(str(e))
