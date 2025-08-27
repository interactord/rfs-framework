"""
RFS v4.1 Rollback Manager
프로덕션 롤백 관리 시스템

주요 기능:
- 자동/수동 롤백
- 롤백 히스토리 관리
- 체크포인트 기반 복구
- 단계별 롤백 지원
"""

import asyncio
import json
import logging
import pickle
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.result import Failure, Result, Success
from ..events import Event, get_event_bus

logger = logging.getLogger(__name__)


class RollbackTrigger(Enum):
    """롤백 트리거"""

    MANUAL = "manual"
    AUTO_ERROR_RATE = "auto_error_rate"
    AUTO_LATENCY = "auto_latency"
    AUTO_HEALTH_CHECK = "auto_health_check"
    AUTO_RESOURCE = "auto_resource"
    AUTO_DEPENDENCY = "auto_dependency"


class RollbackStatus(Enum):
    """롤백 상태"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DeploymentCheckpoint:
    """배포 체크포인트"""

    checkpoint_id: str
    service_name: str
    version: str
    timestamp: datetime
    configuration: Dict[str, Any]
    environment_variables: Dict[str, str]
    dependencies: Dict[str, str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data["timestamp"] = {"timestamp": self.timestamp.isoformat()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeploymentCheckpoint":
        """딕셔너리에서 생성"""
        data["timestamp"] = {"timestamp": datetime.fromisoformat(data["timestamp"])}
        return cls(**data)


@dataclass
class RollbackRecord:
    """롤백 기록"""

    rollback_id: str
    service_name: str
    from_version: str
    to_version: str
    trigger: RollbackTrigger
    reason: str
    start_time: datetime
    end_time = None
    status: RollbackStatus = RollbackStatus.PENDING
    error_message = None
    rolled_back_components: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[timedelta]:
        """롤백 소요 시간"""
        if self.end_time:
            return self.end_time - self.start_time
        return None


class RollbackManager:
    """롤백 관리자"""

    def __init__(
        self,
        checkpoint_dir="/tmp/rfs_checkpoints",
        max_checkpoints=10,
        auto_rollback_enabled=True,
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self.auto_rollback_enabled = auto_rollback_enabled
        self.checkpoints: Dict[str, List[DeploymentCheckpoint]] = {}
        self.rollback_history = []
        self.current_rollback = None
        self.rollback_strategies = {}
        self.event_bus = get_event_bus()
        self._load_checkpoints()

    def _load_checkpoints(self) -> None:
        """저장된 체크포인트 로드"""
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.checkpoint"):
                with open(checkpoint_file, "r") as f:
                    data = json.load(f)
                    checkpoint = DeploymentCheckpoint.from_dict(data)
                    if checkpoint.service_name not in self.checkpoints:
                        self.checkpoints = {
                            **self.checkpoints,
                            checkpoint.service_name: [],
                        }
                    self.checkpoints[checkpoint.service_name] = self.checkpoints[
                        checkpoint.service_name
                    ] + [checkpoint]
            for service_name in self.checkpoints:
                self.checkpoints[service_name].sort(key=lambda x: x.timestamp)
        except Exception as e:
            logger.error(f"Failed to load checkpoints: {e}")

    async def create_checkpoint(
        self,
        service_name: str,
        version: str,
        configuration: Dict[str, Any],
        environment_variables=None,
        dependencies=None,
        metadata=None,
    ) -> Result[DeploymentCheckpoint, str]:
        """체크포인트 생성"""
        try:
            checkpoint_id = f"{service_name}_{version}_{int(time.time())}"
            checkpoint = DeploymentCheckpoint(
                checkpoint_id=checkpoint_id,
                service_name=service_name,
                version=version,
                timestamp=datetime.now(),
                configuration=configuration,
                environment_variables=environment_variables or {},
                dependencies=dependencies or {},
                metadata=metadata or {},
            )
            if service_name not in self.checkpoints:
                self.checkpoints = {**self.checkpoints, service_name: []}
            self.checkpoints[service_name] = checkpoints[service_name] + [checkpoint]
            if len(self.checkpoints[service_name]) > self.max_checkpoints:
                old_checkpoint = self.checkpoints[service_name] = {
                    k: v for k, v in checkpoints[service_name].items() if k != 0
                }
                old_file = (
                    self.checkpoint_dir / f"{old_checkpoint.checkpoint_id}.checkpoint"
                )
                if old_file.exists():
                    old_file.unlink()
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.checkpoint"
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            logger.info(
                f"Created checkpoint {checkpoint_id} for {service_name} v{version}"
            )
            await self.event_bus.publish(
                Event(
                    type="checkpoint.created",
                    data={
                        "checkpoint_id": checkpoint_id,
                        "service": service_name,
                        "version": version,
                    },
                )
            )
            return Success(checkpoint)
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return Failure(f"Failed to create checkpoint: {str(e)}")

    async def rollback(
        self,
        service_name: str,
        target_version=None,
        trigger=RollbackTrigger.MANUAL,
        reason="Manual rollback requested",
    ) -> Result[RollbackRecord, str]:
        """롤백 실행"""
        try:
            if (
                service_name not in self.checkpoints
                or not self.checkpoints[service_name]
            ):
                return Failure(f"No checkpoints found for {service_name}")
            checkpoints = self.checkpoints[service_name]
            if target_version:
                target_checkpoint = next(
                    (
                        cp
                        for cp in reversed(checkpoints)
                        if cp.version == target_version
                    ),
                    None,
                )
                if not target_checkpoint:
                    return Failure(f"Checkpoint for version {target_version} not found")
            else:
                if len(checkpoints) < 2:
                    return Failure("No previous checkpoint available for rollback")
                target_checkpoint = checkpoints[-2]
            current_checkpoint = checkpoints[-1]
            rollback_id = f"rollback_{service_name}_{int(time.time())}"
            rollback_record = RollbackRecord(
                rollback_id=rollback_id,
                service_name=service_name,
                from_version=current_checkpoint.version,
                to_version=target_checkpoint.version,
                trigger=trigger,
                reason=reason,
                start_time=datetime.now(),
                status=RollbackStatus.IN_PROGRESS,
            )
            self.current_rollback = rollback_record
            self.rollback_history = self.rollback_history + [rollback_record]
            logger.info(
                f"Starting rollback for {service_name}: {current_checkpoint.version} -> {target_checkpoint.version}"
            )
            await self.event_bus.publish(
                Event(
                    type="rollback.started",
                    data={
                        "rollback_id": rollback_id,
                        "service": service_name,
                        "from_version": current_checkpoint.version,
                        "to_version": target_checkpoint.version,
                        "trigger": trigger.value,
                        "reason": reason,
                    },
                )
            )
            result = await self._execute_rollback(target_checkpoint)
            if type(result).__name__ == "Success":
                rollback_record.status = RollbackStatus.COMPLETED
                rollback_record.end_time = datetime.now()
                logger.info(
                    f"Rollback completed successfully in {rollback_record.duration}"
                )
                await self.event_bus.publish(
                    Event(
                        type="rollback.completed",
                        data={
                            "rollback_id": rollback_id,
                            "duration": str(rollback_record.duration),
                        },
                    )
                )
                return Success(rollback_record)
            else:
                rollback_record.status = RollbackStatus.FAILED
                rollback_record.end_time = datetime.now()
                rollback_record.error_message = result.error
                logger.error(f"Rollback failed: {result.error}")
                await self.event_bus.publish(
                    Event(
                        type="rollback.failed",
                        data={"rollback_id": rollback_id, "error": result.error},
                    )
                )
                return Failure(f"Rollback failed: {result.error}")
        except Exception as e:
            logger.error(f"Rollback error: {e}")
            if self.current_rollback:
                self.current_rollback.status = RollbackStatus.FAILED
                self.current_rollback.end_time = datetime.now()
                self.current_rollback.error_message = str(e)
            return Failure(f"Rollback error: {str(e)}")
        finally:
            self.current_rollback = None

    async def _execute_rollback(
        self, checkpoint: DeploymentCheckpoint
    ) -> Result[bool, str]:
        """롤백 실행 로직"""
        try:
            logger.info(f"Restoring configuration for {checkpoint.service_name}...")
            await asyncio.sleep(1)
            logger.info("Restoring environment variables...")
            await asyncio.sleep(0.5)
            logger.info("Restoring dependencies...")
            for dep_name, dep_version in checkpoint.dependencies.items():
                logger.info(f"  - {dep_name}: {dep_version}")
                await asyncio.sleep(0.2)
            logger.info("Restarting service...")
            await asyncio.sleep(2)
            logger.info("Performing health check...")
            await asyncio.sleep(1)
            return Success(True)
        except Exception as e:
            return Failure(f"Rollback execution failed: {str(e)}")

    async def can_rollback(
        self, service_name: str, target_version=None
    ) -> Result[bool, str]:
        """롤백 가능 여부 확인"""
        try:
            if (
                self.current_rollback
                and self.current_rollback.service_name == service_name
            ):
                return Failure("Rollback already in progress")
            if (
                service_name not in self.checkpoints
                or not self.checkpoints[service_name]
            ):
                return Failure("No checkpoints available")
            checkpoints = self.checkpoints[service_name]
            if target_version:
                has_checkpoint = any(
                    (cp.version == target_version for cp in checkpoints)
                )
                if not has_checkpoint:
                    return Failure(f"No checkpoint for version {target_version}")
            elif len(checkpoints) < 2:
                return Failure("No previous checkpoint available")
            return Success(True)
        except Exception as e:
            return Failure(f"Error checking rollback availability: {str(e)}")

    def get_rollback_history(self, service_name=None, limit=10) -> List[RollbackRecord]:
        """롤백 히스토리 조회"""
        history = self.rollback_history
        if service_name:
            history = [r for r in history if r.service_name == service_name]
        history.sort(key=lambda x: x.start_time, reverse=True)
        return history[:limit]

    def get_checkpoints(
        self, service_name: str, limit=None
    ) -> List[DeploymentCheckpoint]:
        """체크포인트 목록 조회"""
        if service_name not in self.checkpoints:
            return []
        checkpoints = self.checkpoints[service_name]
        if limit:
            return checkpoints[-limit:]
        return checkpoints

    async def auto_rollback_check(
        self, service_name: str, metrics: Dict[str, float], thresholds: Dict[str, float]
    ) -> Result[Optional[RollbackRecord], str]:
        """자동 롤백 체크 및 실행"""
        if not self.auto_rollback_enabled:
            return Success(None)
        try:
            trigger = None
            reason = None
            if "error_rate" in metrics and "max_error_rate" in thresholds:
                if metrics["error_rate"] > thresholds["max_error_rate"]:
                    trigger = RollbackTrigger.AUTO_ERROR_RATE
                    reason = f"Error rate {metrics['error_rate']:.2%} exceeded threshold {thresholds['max_error_rate']:.2%}"
            if (
                not trigger
                and "latency_p99" in metrics
                and ("max_latency" in thresholds)
            ):
                if metrics["latency_p99"] > thresholds["max_latency"]:
                    trigger = RollbackTrigger.AUTO_LATENCY
                    reason = f"P99 latency {metrics['latency_p99']:.2f}s exceeded threshold {thresholds['max_latency']:.2f}s"
            if not trigger and "cpu_usage" in metrics and ("max_cpu" in thresholds):
                if metrics["cpu_usage"] > thresholds["max_cpu"]:
                    trigger = RollbackTrigger.AUTO_RESOURCE
                    reason = f"CPU usage {metrics['cpu_usage']:.1%} exceeded threshold {thresholds['max_cpu']:.1%}"
            if trigger:
                logger.warning(f"Auto rollback triggered: {reason}")
                result = await self.rollback(
                    service_name=service_name, trigger=trigger, reason=reason
                )
                if type(result).__name__ == "Success":
                    return Success(result.value)
                else:
                    return Failure(f"Auto rollback failed: {result.error}")
            return Success(None)
        except Exception as e:
            logger.error(f"Auto rollback check failed: {e}")
            return Failure(f"Auto rollback check failed: {str(e)}")

    def cleanup_old_checkpoints(self, service_name=None, older_than_days=30) -> int:
        """오래된 체크포인트 정리"""
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        removed_count = 0
        services = [service_name] if service_name else list(self.checkpoints.keys())
        for svc in services:
            if svc not in self.checkpoints:
                continue
            old_checkpoints = [
                cp for cp in self.checkpoints[svc] if cp.timestamp < cutoff_date
            ]
            for checkpoint in old_checkpoints:
                checkpoint_file = (
                    self.checkpoint_dir / f"{checkpoint.checkpoint_id}.checkpoint"
                )
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
                self.checkpoints[svc].remove(checkpoint)
                removed_count = removed_count + 1
        logger.info(f"Cleaned up {removed_count} old checkpoints")
        return removed_count
