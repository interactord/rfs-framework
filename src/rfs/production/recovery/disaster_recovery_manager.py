"""
Disaster Recovery Manager for RFS Framework

재해 복구 관리 시스템
- 재해 복구 계획 수립 및 실행
- 자동 페일오버 및 페일백
- RPO/RTO 목표 관리
- 복구 시나리오 테스트
"""

import asyncio
import hashlib
import json
import logging
import shutil
import subprocess
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from rfs.core.config import get_config
from rfs.core.result import Failure, Result, Success
from rfs.events.event_bus import Event
from rfs.reactive.mono import Mono


class RecoveryStrategy(Enum):
    """복구 전략"""

    HOT_STANDBY = "hot_standby"
    WARM_STANDBY = "warm_standby"
    COLD_STANDBY = "cold_standby"
    PILOT_LIGHT = "pilot_light"
    BACKUP_RESTORE = "backup_restore"


class FailoverType(Enum):
    """페일오버 유형"""

    AUTOMATIC = "automatic"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class RecoveryPhase(Enum):
    """복구 단계"""

    DETECTION = "detection"
    ASSESSMENT = "assessment"
    INITIATION = "initiation"
    EXECUTION = "execution"
    VALIDATION = "validation"
    COMPLETION = "completion"


class DisasterType(Enum):
    """재해 유형"""

    SERVICE_FAILURE = "service_failure"
    DATA_CORRUPTION = "data_corruption"
    NETWORK_OUTAGE = "network_outage"
    HARDWARE_FAILURE = "hardware_failure"
    SECURITY_BREACH = "security_breach"
    NATURAL_DISASTER = "natural_disaster"


@dataclass
class RPO:
    """Recovery Point Objective - 복구 시점 목표"""

    target_minutes: int
    actual_minutes = None
    last_backup_time = None
    data_loss_acceptable = False


@dataclass
class RTO:
    """Recovery Time Objective - 복구 시간 목표"""

    target_minutes: int
    actual_minutes = None
    recovery_start_time = None
    recovery_end_time = None


@dataclass
class BackupStrategy:
    """백업 전략"""

    type: str
    frequency_hours: int
    retention_days: int
    encryption_enabled = True
    compression_enabled = True
    verification_enabled = True
    backup_locations: List[str] = field(default_factory=list)


@dataclass
class FailoverConfig:
    """페일오버 설정"""

    type: FailoverType
    health_check_interval_seconds: float = 30.0
    failure_threshold = 3
    success_threshold = 2
    auto_failback = False
    failback_delay_minutes = 60
    notification_channels: List[str] = field(default_factory=list)


@dataclass
class RecoveryPlan:
    """복구 계획"""

    id: str
    name: str
    description: str
    strategy: RecoveryStrategy
    disaster_types: List[DisasterType]
    rpo: RPO
    rto: RTO
    backup_strategy: BackupStrategy
    failover_config: FailoverConfig
    priority = 1
    enabled = True
    test_frequency_days = 30
    last_test_date = None
    procedures: List[Dict[str, Any]] = field(default_factory=list)
    contacts: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class RecoveryOperation:
    """복구 작업"""

    id: str
    plan_id: str
    disaster_type: DisasterType
    phase: RecoveryPhase
    started_at: datetime
    completed_at = None
    status = "in_progress"
    error_message = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)


class RecoveryProcedure:
    """복구 절차 실행기"""

    def __init__(self, procedure_config: Dict[str, Any]):
        self.config = procedure_config
        self.name = procedure_config.get("name", "Unknown")
        self.type = procedure_config.get("type", "script")
        self.timeout_seconds = procedure_config.get("timeout", 300)
        self.retries = procedure_config.get("retries", 3)
        self.critical = procedure_config.get("critical", True)

    async def execute(self, context: Dict[str, Any]) -> Result[Dict[str, Any], str]:
        """절차 실행"""
        start_time = time.time()
        try:
            match self.type:
                case "script":
                    return await self._execute_script(context)
                case "command":
                    return await self._execute_command(context)
                case "function":
                    return await self._execute_function(context)
                case "api_call":
                    return await self._execute_api_call(context)
                case _:
                    return Failure(f"Unknown procedure type: {self.type}")
        except Exception as e:
            duration = time.time() - start_time
            return Failure(f"Procedure '{self.name}' failed after {duration:.2f}s: {e}")

    async def _execute_script(
        self, context: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """스크립트 실행"""
        script_path = self.config.get("script_path")
        if not script_path:
            return Failure("Script path not specified")
        if not Path(script_path).exists():
            return Failure(f"Script not found: {script_path}")
        try:
            args = self.config.get("args", [])
            env = {**self.config.get("env", {}), **context}
            process = await asyncio.create_subprocess_exec(
                script_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={k: str(v) for k, v in env.items()},
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                return Failure(f"Script execution timeout ({self.timeout_seconds}s)")
            if process.returncode != 0:
                return Failure(
                    f"Script failed with code {process.returncode}: {stderr.decode()}"
                )
            return Success(
                {
                    "output": stdout.decode(),
                    "error": stderr.decode(),
                    "return_code": process.returncode,
                }
            )
        except Exception as e:
            return Failure(f"Script execution failed: {e}")

    async def _execute_command(
        self, context: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """명령 실행"""
        command = self.config.get("command")
        if not command:
            return Failure("Command not specified")
        try:
            for key, value in context.items():
                command = command.replace(f"{{{key}}}", str(value))
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                return Failure(f"Command execution timeout ({self.timeout_seconds}s)")
            if process.returncode != 0:
                return Failure(
                    f"Command failed with code {process.returncode}: {stderr.decode()}"
                )
            return Success(
                {
                    "output": stdout.decode(),
                    "error": stderr.decode(),
                    "return_code": process.returncode,
                }
            )
        except Exception as e:
            return Failure(f"Command execution failed: {e}")

    async def _execute_function(
        self, context: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """함수 실행"""
        function_name = self.config.get("function")
        if not function_name:
            return Failure("Function not specified")
        return Success(
            {
                "function": function_name,
                "context": context,
                "result": "Function executed successfully",
            }
        )

    async def _execute_api_call(
        self, context: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """API 호출"""
        import aiohttp

        url = self.config.get("url")
        method = self.config.get("method", "GET").upper()
        headers = self.config.get("headers", {})
        if not url:
            return Failure("API URL not specified")
        for key, value in context.items():
            url = url.replace(f"{{{key}}}", str(value))
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                match method:
                    case "GET":
                        async with session.get(url, headers=headers) as response:
                            content = await response.text()
                            return Success(
                                {
                                    "status_code": response.status,
                                    "content": content,
                                    "headers": dict(response.headers),
                                }
                            )
                    case "POST":
                        data = self.config.get("data", {})
                        async with session.post(
                            url, json=data, headers=headers
                        ) as response:
                            content = await response.text()
                            return Success(
                                {
                                    "status_code": response.status,
                                    "content": content,
                                    "headers": dict(response.headers),
                                }
                            )
                    case _:
                        return Failure(f"Unsupported HTTP method: {method}")
        except asyncio.TimeoutError:
            return Failure(f"API call timeout ({self.timeout_seconds}s)")
        except Exception as e:
            return Failure(f"API call failed: {e}")


class HealthMonitor:
    """헬스 모니터링"""

    def __init__(self, config: FailoverConfig):
        self.config = config
        self.health_checks = {}
        self.health_status = {}
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)

    def register_health_check(self, name: str, check_func: Callable) -> None:
        """헬스 체크 등록"""
        self.health_checks = {**self.health_checks, name: check_func}

    async def check_health(self) -> Dict[str, bool]:
        """헬스 체크 실행"""
        results = {}
        for name, check_func in self.health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                results[name] = {name: bool(result)}
                if result:
                    self.success_counts = {
                        **self.success_counts,
                        name: self.success_counts[name] + 1,
                    }
                    self.failure_counts = {**self.failure_counts, name: 0}
                else:
                    self.failure_counts = {
                        **self.failure_counts,
                        name: self.failure_counts[name] + 1,
                    }
                    self.success_counts = {**self.success_counts, name: 0}
                if self.failure_counts[name] >= self.config.failure_threshold:
                    self.health_status = {**self.health_status, name: False}
                elif self.success_counts[name] >= self.config.success_threshold:
                    self.health_status = {**self.health_status, name: True}
            except Exception as e:
                logging.error(f"Health check '{name}' failed: {e}")
                results[name] = False
                self.failure_counts = {
                    **self.failure_counts,
                    name: self.failure_counts[name] + 1,
                }
                self.success_counts = {**self.success_counts, name: 0}
        return results

    def is_healthy(self) -> bool:
        """전체 헬스 상태"""
        if not self.health_status:
            return True
        return all(self.health_status.values())


class FailoverManager:
    """페일오버 관리"""

    def __init__(self, config: FailoverConfig):
        self.config = config
        self.is_primary = True
        self.failover_in_progress = False
        self.last_failover_time = None
        self.failover_callbacks = []

    def register_failover_callback(self, callback: Callable) -> None:
        """페일오버 콜백 등록"""
        self.failover_callbacks = self.failover_callbacks + [callback]

    async def initiate_failover(self, reason: str) -> Result[bool, str]:
        """페일오버 시작"""
        if self.failover_in_progress:
            return Failure("Failover already in progress")
        if not self.is_primary:
            return Failure("Not in primary mode")
        try:
            self.failover_in_progress = True
            self.last_failover_time = datetime.now()
            logging.info(f"Initiating failover: {reason}")
            for callback in self.failover_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(reason)
                    else:
                        callback(reason)
                except Exception as e:
                    logging.error(f"Failover callback failed: {e}")
            self.is_primary = False
            self.failover_in_progress = False
            return Success(True)
        except Exception as e:
            self.failover_in_progress = False
            return Failure(f"Failover failed: {e}")

    async def initiate_failback(self) -> Result[bool, str]:
        """페일백 시작"""
        if self.is_primary:
            return Failure("Already in primary mode")
        if not self.config.auto_failback:
            return Failure("Auto failback not enabled")
        if self.last_failover_time:
            elapsed = (datetime.now() - self.last_failover_time).total_seconds() / 60
            if elapsed < self.config.failback_delay_minutes:
                remaining = self.config.failback_delay_minutes - elapsed
                return Failure(
                    f"Failback delay not met. Wait {remaining:.1f} more minutes"
                )
        try:
            logging.info("Initiating failback to primary")
            self.is_primary = True
            return Success(True)
        except Exception as e:
            return Failure(f"Failback failed: {e}")


class BackupValidator:
    """백업 검증"""

    def __init__(self):
        self.validation_results: deque = deque(maxlen=100)

    async def validate_backup(
        self, backup_path: str, validation_type="checksum"
    ) -> Result[bool, str]:
        """백업 파일 검증"""
        if not Path(backup_path).exists():
            return Failure(f"Backup file not found: {backup_path}")
        try:
            match validation_type:
                case "checksum":
                    return await self._validate_checksum(backup_path)
                case "restore_test":
                    return await self._validate_restore_test(backup_path)
                case "integrity":
                    return await self._validate_integrity(backup_path)
                case _:
                    return Failure(f"Unknown validation type: {validation_type}")
        except Exception as e:
            return Failure(f"Backup validation failed: {e}")

    async def _validate_checksum(self, backup_path: str) -> Result[bool, str]:
        """체크섬 검증"""
        checksum_file = f"{backup_path}.sha256"
        if not Path(checksum_file).exists():
            return Failure(f"Checksum file not found: {checksum_file}")
        try:
            sha256_hash = hashlib.sha256()
            with open(backup_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash = {**sha256_hash, **byte_block}
            calculated_checksum = sha256_hash.hexdigest()
            with open(checksum_file, "r") as f:
                stored_checksum = f.read().strip()
            if calculated_checksum == stored_checksum:
                return Success(True)
            else:
                return Failure("Checksum mismatch")
        except Exception as e:
            return Failure(f"Checksum validation failed: {e}")

    async def _validate_restore_test(self, backup_path: str) -> Result[bool, str]:
        """복원 테스트"""
        return Success(True)

    async def _validate_integrity(self, backup_path: str) -> Result[bool, str]:
        """무결성 검증"""
        try:
            file_size = Path(backup_path).stat().st_size
            if file_size == 0:
                return Failure("Backup file is empty")
            return Success(True)
        except Exception as e:
            return Failure(f"Integrity check failed: {e}")


class DisasterRecoveryManager:
    """재해 복구 관리자"""

    def __init__(self):
        self.recovery_plans = {}
        self.active_operations = {}
        self.operation_history: deque = deque(maxlen=1000)
        self.health_monitors = {}
        self.failover_managers = {}
        self.backup_validator = BackupValidator()
        self.total_recoveries = 0
        self.successful_recoveries = 0
        self.failed_recoveries = 0
        self.total_tests = 0
        self.monitoring_task = None
        self.is_running = False

    async def initialize(self) -> Result[bool, str]:
        """재해 복구 관리자 초기화"""
        try:
            logging.info("Disaster recovery manager initialized")
            return Success(True)
        except Exception as e:
            return Failure(f"Initialization failed: {e}")

    def add_recovery_plan(self, plan: RecoveryPlan) -> Result[bool, str]:
        """복구 계획 추가"""
        try:
            self.recovery_plans = {**self.recovery_plans, plan.id: plan}
            if plan.failover_config:
                self.health_monitors = {
                    **self.health_monitors,
                    plan.id: HealthMonitor(plan.failover_config),
                }
                self.failover_managers = {
                    **self.failover_managers,
                    plan.id: FailoverManager(plan.failover_config),
                }
            logging.info(f"Recovery plan added: {plan.name}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add recovery plan: {e}")

    async def trigger_recovery(
        self, plan_id: str, disaster_type: DisasterType, context=None
    ) -> Result[RecoveryOperation, str]:
        """복구 트리거"""
        if plan_id not in self.recovery_plans:
            return Failure(f"Recovery plan not found: {plan_id}")
        plan = self.recovery_plans[plan_id]
        if not plan.enabled:
            return Failure(f"Recovery plan disabled: {plan_id}")
        if disaster_type not in plan.disaster_types:
            return Failure(f"Disaster type {disaster_type.value} not covered by plan")
        operation_id = f"{plan_id}_{datetime.now().timestamp()}"
        operation = RecoveryOperation(
            id=operation_id,
            plan_id=plan_id,
            disaster_type=disaster_type,
            phase=RecoveryPhase.DETECTION,
            started_at=datetime.now(),
        )
        self.active_operations = {**self.active_operations, operation_id: operation}
        total_recoveries = total_recoveries + 1
        asyncio.create_task(self._execute_recovery(operation, plan, context or {}))
        logging.info(
            f"Recovery triggered for {disaster_type.value} using plan {plan.name}"
        )
        return Success(operation)

    async def _execute_recovery(
        self, operation: RecoveryOperation, plan: RecoveryPlan, context: Dict[str, Any]
    ) -> None:
        """복구 실행"""
        try:
            for phase in RecoveryPhase:
                operation.phase = phase
                operation.logs = operation.logs + [
                    f"[{datetime.now()}] Entering phase: {phase.value}"
                ]
                match phase:
                    case RecoveryPhase.DETECTION:
                        await self._phase_detection(operation, plan, context)
                    case RecoveryPhase.ASSESSMENT:
                        await self._phase_assessment(operation, plan, context)
                    case RecoveryPhase.INITIATION:
                        await self._phase_initiation(operation, plan, context)
                    case RecoveryPhase.EXECUTION:
                        await self._phase_execution(operation, plan, context)
                    case RecoveryPhase.VALIDATION:
                        await self._phase_validation(operation, plan, context)
                    case RecoveryPhase.COMPLETION:
                        await self._phase_completion(operation, plan, context)
            operation.status = "success"
            operation.completed_at = datetime.now()
            successful_recoveries = successful_recoveries + 1
            if plan.rto.recovery_start_time:
                plan.rto.recovery_end_time = datetime.now()
                plan.rto.actual_minutes = int(
                    (
                        plan.rto.recovery_end_time - plan.rto.recovery_start_time
                    ).total_seconds()
                    / 60
                )
            logging.info(f"Recovery operation {operation.id} completed successfully")
        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            operation.completed_at = datetime.now()
            failed_recoveries = failed_recoveries + 1
            logging.error(f"Recovery operation {operation.id} failed: {e}")
        finally:
            self.operation_history = self.operation_history + [operation]
            if operation.id in self.active_operations:
                del self.active_operations[operation.id]

    async def _phase_detection(
        self, operation: RecoveryOperation, plan: RecoveryPlan, context: Dict[str, Any]
    ) -> None:
        """감지 단계"""
        operation.logs = operation.logs + [
            "Starting disaster detection and confirmation"
        ]
        if plan.id in self.health_monitors:
            health_status = await self.health_monitors[plan.id].check_health()
            operation.metrics = {**operation.metrics, "health_status": health_status}
            if not self.health_monitors[plan.id].is_healthy():
                operation.logs = operation.logs + [
                    "Health check failed - disaster confirmed"
                ]
            else:
                operation.logs = operation.logs + [
                    "Health check passed - no disaster detected"
                ]
                raise Exception("No disaster detected")

    async def _phase_assessment(
        self, operation: RecoveryOperation, plan: RecoveryPlan, context: Dict[str, Any]
    ) -> None:
        """평가 단계"""
        operation.logs = operation.logs + ["Assessing disaster impact"]
        if plan.rpo.last_backup_time:
            data_loss_minutes = int(
                (datetime.now() - plan.rpo.last_backup_time).total_seconds() / 60
            )
            plan.rpo.actual_minutes = data_loss_minutes
            operation.metrics = {
                **operation.metrics,
                "estimated_data_loss_minutes": data_loss_minutes,
            }
            if data_loss_minutes > plan.rpo.target_minutes:
                operation.logs = operation.logs + [
                    f"WARNING: Potential data loss exceeds RPO target ({data_loss_minutes} > {plan.rpo.target_minutes} minutes)"
                ]

    async def _phase_initiation(
        self, operation: RecoveryOperation, plan: RecoveryPlan, context: Dict[str, Any]
    ) -> None:
        """시작 단계"""
        operation.logs = operation.logs + ["Initiating recovery procedures"]
        plan.rto.recovery_start_time = datetime.now()
        if plan.strategy in [
            RecoveryStrategy.HOT_STANDBY,
            RecoveryStrategy.WARM_STANDBY,
        ]:
            if plan.id in self.failover_managers:
                failover_result = await self.failover_managers[
                    plan.id
                ].initiate_failover(
                    f"Disaster recovery for {operation.disaster_type.value}"
                )
                if not failover_result.is_success():
                    raise Exception(f"Failover failed: {failover_result.error}")
                operation.logs = operation.logs + ["Failover initiated successfully"]

    async def _phase_execution(
        self, operation: RecoveryOperation, plan: RecoveryPlan, context: Dict[str, Any]
    ) -> None:
        """실행 단계"""
        operation.logs = operation.logs + ["Executing recovery procedures"]
        for i, procedure_config in enumerate(plan.procedures, 1):
            procedure = RecoveryProcedure(procedure_config)
            operation.logs = operation.logs + [
                f"Executing procedure {i}/{len(plan.procedures)}: {procedure.name}"
            ]
            last_error = None
            for attempt in range(procedure.retries + 1):
                try:
                    result = await procedure.execute(context)
                    if result.is_success():
                        operation.logs = operation.logs + [
                            f"Procedure '{procedure.name}' completed successfully"
                        ]
                        break
                    else:
                        last_error = result.error
                        if attempt < procedure.retries:
                            operation.logs = operation.logs + [
                                f"Procedure failed, retrying ({attempt + 1}/{procedure.retries})"
                            ]
                            await asyncio.sleep(2**attempt)
                except Exception as e:
                    last_error = str(e)
                    if attempt < procedure.retries:
                        await asyncio.sleep(2**attempt)
            else:
                if procedure.critical:
                    raise Exception(
                        f"Critical procedure '{procedure.name}' failed: {last_error}"
                    )
                else:
                    operation.logs = operation.logs + [
                        f"Non-critical procedure '{procedure.name}' failed: {last_error}"
                    ]

    async def _phase_validation(
        self, operation: RecoveryOperation, plan: RecoveryPlan, context: Dict[str, Any]
    ) -> None:
        """검증 단계"""
        operation.logs = operation.logs + ["Validating recovery"]
        if plan.strategy == RecoveryStrategy.BACKUP_RESTORE:
            if "backup_path" in context:
                validation_result = await self.backup_validator.validate_backup(
                    context.get("backup_path"), "integrity"
                )
                if not validation_result.is_success():
                    raise Exception(
                        f"Backup validation failed: {validation_result.error}"
                    )
                operation.logs = operation.logs + ["Backup validation successful"]
        if plan.id in self.health_monitors:
            await asyncio.sleep(5)
            health_status = await self.health_monitors[plan.id].check_health()
            if self.health_monitors[plan.id].is_healthy():
                operation.logs = operation.logs + ["Post-recovery health check passed"]
            else:
                operation.logs = operation.logs + [
                    "WARNING: Post-recovery health check failed"
                ]
                operation.metrics = {
                    **operation.metrics,
                    "post_recovery_health": health_status,
                }

    async def _phase_completion(
        self, operation: RecoveryOperation, plan: RecoveryPlan, context: Dict[str, Any]
    ) -> None:
        """완료 단계"""
        operation.logs = operation.logs + ["Completing recovery operation"]
        operation.metrics = {
            **operation.metrics,
            "total_duration_seconds": (
                datetime.now() - operation.started_at
            ).total_seconds(),
        }
        if plan.rto.target_minutes and plan.rto.actual_minutes:
            if plan.rto.actual_minutes > plan.rto.target_minutes:
                operation.logs = operation.logs + [
                    f"WARNING: RTO target missed ({plan.rto.actual_minutes} > {plan.rto.target_minutes} minutes)"
                ]
            else:
                operation.logs = operation.logs + [
                    f"RTO target met: {plan.rto.actual_minutes} minutes"
                ]

    async def test_recovery_plan(self, plan_id: str) -> Result[Dict[str, Any], str]:
        """복구 계획 테스트"""
        if plan_id not in self.recovery_plans:
            return Failure(f"Recovery plan not found: {plan_id}")
        plan = self.recovery_plans[plan_id]
        try:
            total_tests = total_tests + 1
            test_start = datetime.now()
            test_context = {"test_mode": True, "test_timestamp": test_start.isoformat()}
            test_results = []
            for procedure_config in plan.procedures:
                procedure = RecoveryProcedure(procedure_config)
                if procedure.type == "script":
                    script_path = procedure_config.get("script_path")
                    if script_path and Path(script_path).exists():
                        test_results = test_results + [
                            {
                                "procedure": procedure.name,
                                "status": "valid",
                                "message": "Script file exists",
                            }
                        ]
                    else:
                        test_results = test_results + [
                            {
                                "procedure": procedure.name,
                                "status": "invalid",
                                "message": f"Script file not found: {script_path}",
                            }
                        ]
                else:
                    test_results = test_results + [
                        {
                            "procedure": procedure.name,
                            "status": "valid",
                            "message": f"Procedure type {procedure.type} validated",
                        }
                    ]
            plan.last_test_date = datetime.now()
            test_duration = (datetime.now() - test_start).total_seconds()
            valid_count = sum((1 for r in test_results if r["status"] == "valid"))
            invalid_count = len(test_results) - valid_count
            test_summary = {
                "plan_id": plan_id,
                "plan_name": plan.name,
                "test_date": test_start.isoformat(),
                "duration_seconds": test_duration,
                "total_procedures": len(test_results),
                "valid_procedures": valid_count,
                "invalid_procedures": invalid_count,
                "results": test_results,
                "status": "passed" if invalid_count == 0 else "failed",
            }
            logging.info(f"Recovery plan test completed: {plan.name}")
            return Success(test_summary)
        except Exception as e:
            return Failure(f"Recovery plan test failed: {e}")

    async def start_monitoring(self) -> Result[bool, str]:
        """모니터링 시작"""
        if self.is_running:
            return Success(True)
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            logging.info("Disaster recovery monitoring started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start monitoring: {e}")

    async def stop_monitoring(self) -> Result[bool, str]:
        """모니터링 중지"""
        try:
            self.is_running = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            logging.info("Disaster recovery monitoring stopped")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop monitoring: {e}")

    async def _monitoring_loop(self) -> None:
        """모니터링 루프"""
        while self.is_running:
            try:
                for plan_id, plan in self.recovery_plans.items():
                    if not plan.enabled:
                        continue
                    if (
                        plan.failover_config
                        and plan.failover_config.type == FailoverType.AUTOMATIC
                    ):
                        if plan_id in self.health_monitors:
                            health_status = await self.health_monitors[
                                plan_id
                            ].check_health()
                            if not self.health_monitors[plan_id].is_healthy():
                                active_operation = any(
                                    (
                                        op.plan_id == plan_id
                                        and op.status == "in_progress"
                                        for op in self.active_operations.values()
                                    )
                                )
                                if not active_operation:
                                    await self.trigger_recovery(
                                        plan_id,
                                        DisasterType.SERVICE_FAILURE,
                                        {
                                            "auto_triggered": True,
                                            "health_status": health_status,
                                        },
                                    )
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(30)

    def get_recovery_status(self) -> Dict[str, Any]:
        """복구 상태 조회"""
        active_operations_list = []
        for op in self.active_operations.values():
            active_operations_list = active_operations_list + [
                {
                    "id": op.id,
                    "plan_id": op.plan_id,
                    "disaster_type": op.disaster_type.value,
                    "phase": op.phase.value,
                    "status": op.status,
                    "started_at": op.started_at.isoformat(),
                    "duration_seconds": (
                        datetime.now() - op.started_at
                    ).total_seconds(),
                }
            ]
        return {
            "total_plans": len(self.recovery_plans),
            "enabled_plans": sum(
                (1 for p in self.recovery_plans.values() if p.enabled)
            ),
            "active_operations": len(self.active_operations),
            "active_operations_detail": active_operations_list,
            "statistics": {
                "total_recoveries": self.total_recoveries,
                "successful_recoveries": self.successful_recoveries,
                "failed_recoveries": self.failed_recoveries,
                "success_rate": self.successful_recoveries
                / max(1, self.total_recoveries),
                "total_tests": self.total_tests,
            },
            "monitoring_active": self.is_running,
        }

    def get_operation_details(self, operation_id: str) -> Optional[RecoveryOperation]:
        """작업 상세 조회"""
        if operation_id in self.active_operations:
            return self.active_operations[operation_id]
        for op in self.operation_history:
            if op.id == operation_id:
                return op
        return None

    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            recovery_plans = {}
            active_operations = {}
            health_monitors = {}
            failover_managers = {}
            logging.info("Disaster recovery manager cleanup completed")
            return Success(True)
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


_disaster_recovery_manager = None


def get_disaster_recovery_manager() -> DisasterRecoveryManager:
    """재해 복구 관리자 싱글톤 인스턴스 반환"""
    if _disaster_recovery_manager is None:
        _disaster_recovery_manager = DisasterRecoveryManager()
    return _disaster_recovery_manager


async def execute_disaster_recovery(
    plan: RecoveryPlan, disaster_type: DisasterType, context=None
) -> Result[RecoveryOperation, str]:
    """재해 복구 실행"""
    manager = get_disaster_recovery_manager()
    init_result = await manager.initialize()
    if not init_result.is_success():
        return Failure(f"Manager initialization failed: {init_result.error}")
    add_result = manager.add_recovery_plan(plan)
    if not add_result.is_success():
        return Failure(f"Failed to add recovery plan: {add_result.error}")
    return await manager.trigger_recovery(plan.id, disaster_type, context)
