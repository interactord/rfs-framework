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
import time
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import logging
import pickle
import shutil

from ..core.result import Result, Success, Failure
from ..events import Event, get_event_bus

logger = logging.getLogger(__name__)


class RollbackTrigger(Enum):
    """롤백 트리거"""
    MANUAL = "manual"           # 수동 롤백
    AUTO_ERROR_RATE = "auto_error_rate"    # 에러율 기반 자동
    AUTO_LATENCY = "auto_latency"          # 지연 기반 자동
    AUTO_HEALTH_CHECK = "auto_health_check" # 헬스체크 실패
    AUTO_RESOURCE = "auto_resource"        # 리소스 부족
    AUTO_DEPENDENCY = "auto_dependency"    # 의존성 문제


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
    dependencies: Dict[str, str]  # dependency_name: version
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeploymentCheckpoint':
        """딕셔너리에서 생성"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
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
    end_time: Optional[datetime] = None
    status: RollbackStatus = RollbackStatus.PENDING
    error_message: Optional[str] = None
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
        checkpoint_dir: str = "/tmp/rfs_checkpoints",
        max_checkpoints: int = 10,
        auto_rollback_enabled: bool = True
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_checkpoints = max_checkpoints
        self.auto_rollback_enabled = auto_rollback_enabled
        
        # 메모리 캐시
        self.checkpoints: Dict[str, List[DeploymentCheckpoint]] = {}
        self.rollback_history: List[RollbackRecord] = []
        self.current_rollback: Optional[RollbackRecord] = None
        
        # 롤백 전략
        self.rollback_strategies: Dict[str, Callable] = {}
        
        # 이벤트 버스
        self.event_bus = get_event_bus()
        
        # 체크포인트 로드
        self._load_checkpoints()
    
    def _load_checkpoints(self) -> None:
        """저장된 체크포인트 로드"""
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.checkpoint"):
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    checkpoint = DeploymentCheckpoint.from_dict(data)
                    
                    if checkpoint.service_name not in self.checkpoints:
                        self.checkpoints[checkpoint.service_name] = []
                    
                    self.checkpoints[checkpoint.service_name].append(checkpoint)
            
            # 시간순 정렬
            for service_name in self.checkpoints:
                self.checkpoints[service_name].sort(key=lambda x: x.timestamp)
                
        except Exception as e:
            logger.error(f"Failed to load checkpoints: {e}")
    
    async def create_checkpoint(
        self,
        service_name: str,
        version: str,
        configuration: Dict[str, Any],
        environment_variables: Optional[Dict[str, str]] = None,
        dependencies: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
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
                metadata=metadata or {}
            )
            
            # 메모리에 저장
            if service_name not in self.checkpoints:
                self.checkpoints[service_name] = []
            
            self.checkpoints[service_name].append(checkpoint)
            
            # 최대 개수 유지
            if len(self.checkpoints[service_name]) > self.max_checkpoints:
                old_checkpoint = self.checkpoints[service_name].pop(0)
                # 오래된 파일 삭제
                old_file = self.checkpoint_dir / f"{old_checkpoint.checkpoint_id}.checkpoint"
                if old_file.exists():
                    old_file.unlink()
            
            # 파일로 저장
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.checkpoint"
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            
            logger.info(f"Created checkpoint {checkpoint_id} for {service_name} v{version}")
            
            # 이벤트 발행
            await self.event_bus.publish(Event(
                type="checkpoint.created",
                data={"checkpoint_id": checkpoint_id, "service": service_name, "version": version}
            ))
            
            return Success(checkpoint)
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return Failure(f"Failed to create checkpoint: {str(e)}")
    
    async def rollback(
        self,
        service_name: str,
        target_version: Optional[str] = None,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
        reason: str = "Manual rollback requested"
    ) -> Result[RollbackRecord, str]:
        """롤백 실행"""
        try:
            # 체크포인트 찾기
            if service_name not in self.checkpoints or not self.checkpoints[service_name]:
                return Failure(f"No checkpoints found for {service_name}")
            
            checkpoints = self.checkpoints[service_name]
            
            # 타겟 체크포인트 선택
            if target_version:
                target_checkpoint = next(
                    (cp for cp in reversed(checkpoints) if cp.version == target_version),
                    None
                )
                if not target_checkpoint:
                    return Failure(f"Checkpoint for version {target_version} not found")
            else:
                # 가장 최근의 안정적인 체크포인트 선택 (현재 버전 제외)
                if len(checkpoints) < 2:
                    return Failure("No previous checkpoint available for rollback")
                target_checkpoint = checkpoints[-2]
            
            current_checkpoint = checkpoints[-1]
            
            # 롤백 기록 생성
            rollback_id = f"rollback_{service_name}_{int(time.time())}"
            rollback_record = RollbackRecord(
                rollback_id=rollback_id,
                service_name=service_name,
                from_version=current_checkpoint.version,
                to_version=target_checkpoint.version,
                trigger=trigger,
                reason=reason,
                start_time=datetime.now(),
                status=RollbackStatus.IN_PROGRESS
            )
            
            self.current_rollback = rollback_record
            self.rollback_history.append(rollback_record)
            
            logger.info(f"Starting rollback for {service_name}: {current_checkpoint.version} -> {target_checkpoint.version}")
            
            # 이벤트 발행
            await self.event_bus.publish(Event(
                type="rollback.started",
                data={
                    "rollback_id": rollback_id,
                    "service": service_name,
                    "from_version": current_checkpoint.version,
                    "to_version": target_checkpoint.version,
                    "trigger": trigger.value,
                    "reason": reason
                }
            ))
            
            # 롤백 실행 (실제 구현에서는 배포 시스템과 연동)
            result = await self._execute_rollback(target_checkpoint)
            
            if isinstance(result, Success):
                rollback_record.status = RollbackStatus.COMPLETED
                rollback_record.end_time = datetime.now()
                
                logger.info(f"Rollback completed successfully in {rollback_record.duration}")
                
                await self.event_bus.publish(Event(
                    type="rollback.completed",
                    data={
                        "rollback_id": rollback_id,
                        "duration": str(rollback_record.duration)
                    }
                ))
                
                return Success(rollback_record)
            else:
                rollback_record.status = RollbackStatus.FAILED
                rollback_record.end_time = datetime.now()
                rollback_record.error_message = result.error
                
                logger.error(f"Rollback failed: {result.error}")
                
                await self.event_bus.publish(Event(
                    type="rollback.failed",
                    data={
                        "rollback_id": rollback_id,
                        "error": result.error
                    }
                ))
                
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
        self,
        checkpoint: DeploymentCheckpoint
    ) -> Result[bool, str]:
        """롤백 실행 로직"""
        try:
            # 1. 설정 복원
            logger.info(f"Restoring configuration for {checkpoint.service_name}...")
            await asyncio.sleep(1)  # 시뮬레이션
            
            # 2. 환경 변수 복원
            logger.info("Restoring environment variables...")
            await asyncio.sleep(0.5)  # 시뮬레이션
            
            # 3. 의존성 복원
            logger.info("Restoring dependencies...")
            for dep_name, dep_version in checkpoint.dependencies.items():
                logger.info(f"  - {dep_name}: {dep_version}")
                await asyncio.sleep(0.2)  # 시뮬레이션
            
            # 4. 서비스 재시작
            logger.info("Restarting service...")
            await asyncio.sleep(2)  # 시뮬레이션
            
            # 5. 헬스체크
            logger.info("Performing health check...")
            await asyncio.sleep(1)  # 시뮬레이션
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Rollback execution failed: {str(e)}")
    
    async def can_rollback(
        self,
        service_name: str,
        target_version: Optional[str] = None
    ) -> Result[bool, str]:
        """롤백 가능 여부 확인"""
        try:
            # 진행 중인 롤백이 있는지 확인
            if self.current_rollback and self.current_rollback.service_name == service_name:
                return Failure("Rollback already in progress")
            
            # 체크포인트 존재 확인
            if service_name not in self.checkpoints or not self.checkpoints[service_name]:
                return Failure("No checkpoints available")
            
            checkpoints = self.checkpoints[service_name]
            
            if target_version:
                # 특정 버전 체크포인트 존재 확인
                has_checkpoint = any(cp.version == target_version for cp in checkpoints)
                if not has_checkpoint:
                    return Failure(f"No checkpoint for version {target_version}")
            else:
                # 이전 체크포인트 존재 확인
                if len(checkpoints) < 2:
                    return Failure("No previous checkpoint available")
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Error checking rollback availability: {str(e)}")
    
    def get_rollback_history(
        self,
        service_name: Optional[str] = None,
        limit: int = 10
    ) -> List[RollbackRecord]:
        """롤백 히스토리 조회"""
        history = self.rollback_history
        
        if service_name:
            history = [r for r in history if r.service_name == service_name]
        
        # 최근 순으로 정렬
        history.sort(key=lambda x: x.start_time, reverse=True)
        
        return history[:limit]
    
    def get_checkpoints(
        self,
        service_name: str,
        limit: Optional[int] = None
    ) -> List[DeploymentCheckpoint]:
        """체크포인트 목록 조회"""
        if service_name not in self.checkpoints:
            return []
        
        checkpoints = self.checkpoints[service_name]
        
        if limit:
            return checkpoints[-limit:]
        
        return checkpoints
    
    async def auto_rollback_check(
        self,
        service_name: str,
        metrics: Dict[str, float],
        thresholds: Dict[str, float]
    ) -> Result[Optional[RollbackRecord], str]:
        """자동 롤백 체크 및 실행"""
        if not self.auto_rollback_enabled:
            return Success(None)
        
        try:
            trigger = None
            reason = None
            
            # 에러율 체크
            if "error_rate" in metrics and "max_error_rate" in thresholds:
                if metrics["error_rate"] > thresholds["max_error_rate"]:
                    trigger = RollbackTrigger.AUTO_ERROR_RATE
                    reason = f"Error rate {metrics['error_rate']:.2%} exceeded threshold {thresholds['max_error_rate']:.2%}"
            
            # 지연 체크
            if not trigger and "latency_p99" in metrics and "max_latency" in thresholds:
                if metrics["latency_p99"] > thresholds["max_latency"]:
                    trigger = RollbackTrigger.AUTO_LATENCY
                    reason = f"P99 latency {metrics['latency_p99']:.2f}s exceeded threshold {thresholds['max_latency']:.2f}s"
            
            # 리소스 사용률 체크
            if not trigger and "cpu_usage" in metrics and "max_cpu" in thresholds:
                if metrics["cpu_usage"] > thresholds["max_cpu"]:
                    trigger = RollbackTrigger.AUTO_RESOURCE
                    reason = f"CPU usage {metrics['cpu_usage']:.1%} exceeded threshold {thresholds['max_cpu']:.1%}"
            
            # 롤백 실행
            if trigger:
                logger.warning(f"Auto rollback triggered: {reason}")
                result = await self.rollback(
                    service_name=service_name,
                    trigger=trigger,
                    reason=reason
                )
                
                if isinstance(result, Success):
                    return Success(result.value)
                else:
                    return Failure(f"Auto rollback failed: {result.error}")
            
            return Success(None)
            
        except Exception as e:
            logger.error(f"Auto rollback check failed: {e}")
            return Failure(f"Auto rollback check failed: {str(e)}")
    
    def cleanup_old_checkpoints(
        self,
        service_name: Optional[str] = None,
        older_than_days: int = 30
    ) -> int:
        """오래된 체크포인트 정리"""
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        removed_count = 0
        
        services = [service_name] if service_name else list(self.checkpoints.keys())
        
        for svc in services:
            if svc not in self.checkpoints:
                continue
            
            old_checkpoints = [
                cp for cp in self.checkpoints[svc]
                if cp.timestamp < cutoff_date
            ]
            
            for checkpoint in old_checkpoints:
                # 파일 삭제
                checkpoint_file = self.checkpoint_dir / f"{checkpoint.checkpoint_id}.checkpoint"
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
                
                # 메모리에서 제거
                self.checkpoints[svc].remove(checkpoint)
                removed_count += 1
        
        logger.info(f"Cleaned up {removed_count} old checkpoints")
        return removed_count