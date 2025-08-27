"""
Backup Manager for RFS Framework

백업 관리 시스템:
- 백업 생성 및 복원
- 백업 검증 및 무결성 확인
- 백업 스케줄링
- 백업 저장소 관리
"""

import asyncio
import hashlib
import json
import os
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Union

import aiofiles
import psutil

from ...core.result import Failure, Result, Success


class BackupType(Enum):
    """백업 타입"""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    CONTINUOUS = "continuous"


class BackupStatus(Enum):
    """백업 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"
    DELETED = "deleted"


class StorageType(Enum):
    """저장소 타입"""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    NFS = "nfs"
    FTP = "ftp"


@dataclass
class BackupPolicy:
    """백업 정책"""

    id: str
    name: str
    backup_type: BackupType
    schedule: str
    retention_days: int
    compression = True
    encryption = True
    verify_after_backup = True
    max_concurrent_backups = 1
    priority = 5
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupTarget:
    """백업 대상"""

    id: str
    name: str
    type: str
    source_path: str
    exclude_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    pre_backup_script = None
    post_backup_script = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupMetadata:
    """백업 메타데이터"""

    backup_id: str
    policy_id: str
    target_id: str
    backup_type: BackupType
    start_time: datetime
    end_time = None
    size_bytes = 0
    file_count = 0
    checksum = None
    compression_ratio: float = 1.0
    encrypted = False
    verified = False
    parent_backup_id = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupOperation:
    """백업 작업"""

    id: str
    policy_id: str
    target_id: str
    backup_type: BackupType
    status: BackupStatus
    progress: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time = None
    error_message = None
    metadata: BackupMetadata = None
    retry_count = 0
    max_retries = 3


@dataclass
class RestoreOperation:
    """복원 작업"""

    id: str
    backup_id: str
    target_path: str
    status: BackupStatus
    progress: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time = None
    error_message = None
    verify_after_restore = True
    overwrite_existing = False


@dataclass
class StorageConfig:
    """저장소 설정"""

    type: StorageType
    path: str
    credentials: Dict[str, Any] = field(default_factory=dict)
    max_size_gb = None
    auto_cleanup = True
    cleanup_threshold_percent: float = 80.0


class BackupManager:
    """백업 관리자"""

    def __init__(self, storage_config: StorageConfig):
        self.storage_config = storage_config
        self.policies = {}
        self.targets = {}
        self.operations = {}
        self.restore_operations = {}
        self.backup_history = []
        self._running = False
        self._tasks: Set[asyncio.Task] = set()

    async def start(self) -> Result[bool, str]:
        """백업 관리자 시작"""
        try:
            self._running = True
            init_result = await self._initialize_storage()
            if type(init_result).__name__ == "Failure":
                return init_result
            scheduler_task = asyncio.create_task(self._backup_scheduler())
            self._tasks.add(scheduler_task)
            cleanup_task = asyncio.create_task(self._cleanup_scheduler())
            self._tasks.add(cleanup_task)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start backup manager: {e}")

    async def stop(self) -> Result[bool, str]:
        """백업 관리자 중지"""
        try:
            self._running = False
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                _tasks = {}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop backup manager: {e}")

    def add_policy(self, policy: BackupPolicy) -> Result[bool, str]:
        """백업 정책 추가"""
        try:
            if policy.id in self.policies:
                return Failure(f"Policy {policy.id} already exists")
            self.policies = {**self.policies, policy.id: policy}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add policy: {e}")

    def add_target(self, target: BackupTarget) -> Result[bool, str]:
        """백업 대상 추가"""
        try:
            if target.id in self.targets:
                return Failure(f"Target {target.id} already exists")
            self.targets = {**self.targets, target.id: target}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add target: {e}")

    async def create_backup(
        self, policy_id: str, target_id: str, manual=False
    ) -> Result[BackupOperation, str]:
        """백업 생성"""
        try:
            if policy_id not in self.policies:
                return Failure(f"Policy {policy_id} not found")
            if target_id not in self.targets:
                return Failure(f"Target {target_id} not found")
            policy = self.policies[policy_id]
            target = self.targets[target_id]
            operation = BackupOperation(
                id=f"backup_{int(time.time() * 1000)}",
                policy_id=policy_id,
                target_id=target_id,
                backup_type=policy.backup_type,
                status=BackupStatus.PENDING,
            )
            self.operations = {**self.operations, operation.id: operation}
            backup_task = asyncio.create_task(
                self._execute_backup(operation, policy, target)
            )
            self._tasks.add(backup_task)
            return Success(operation)
        except Exception as e:
            return Failure(f"Failed to create backup: {e}")

    async def restore_backup(
        self,
        backup_id: str,
        target_path: str,
        overwrite=False,
        verify=True,
    ) -> Result[RestoreOperation, str]:
        """백업 복원"""
        try:
            backup_metadata = None
            for metadata in self.backup_history:
                if metadata.backup_id == backup_id:
                    backup_metadata = metadata
                    break
            if not backup_metadata:
                return Failure(f"Backup {backup_id} not found")
            operation = RestoreOperation(
                id=f"restore_{int(time.time() * 1000)}",
                backup_id=backup_id,
                target_path=target_path,
                status=BackupStatus.PENDING,
                verify_after_restore=verify,
                overwrite_existing=overwrite,
            )
            self.restore_operations = {
                **self.restore_operations,
                operation.id: operation,
            }
            restore_task = asyncio.create_task(
                self._execute_restore(operation, backup_metadata)
            )
            self._tasks.add(restore_task)
            return Success(operation)
        except Exception as e:
            return Failure(f"Failed to restore backup: {e}")

    async def verify_backup(self, backup_id: str) -> Result[bool, str]:
        """백업 검증"""
        try:
            backup_metadata = None
            for metadata in self.backup_history:
                if metadata.backup_id == backup_id:
                    backup_metadata = metadata
                    break
            if not backup_metadata:
                return Failure(f"Backup {backup_id} not found")
            backup_path = self._get_backup_path(backup_metadata)
            calculated_checksum = await self._calculate_checksum(backup_path)
            if calculated_checksum != backup_metadata.checksum:
                backup_metadata.verified = False
                return Failure(f"Backup checksum mismatch")
            if backup_metadata.backup_type in [BackupType.FULL, BackupType.SNAPSHOT]:
                verify_result = await self._verify_backup_integrity(backup_path)
                if type(verify_result).__name__ == "Failure":
                    backup_metadata.verified = False
                    return verify_result
            backup_metadata.verified = True
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to verify backup: {e}")

    async def list_backups(
        self,
        policy_id=None,
        target_id=None,
        status=None,
        limit=100,
    ) -> Result[List[BackupMetadata], str]:
        """백업 목록 조회"""
        try:
            filtered_backups = []
            for metadata in self.backup_history:
                if policy_id and metadata.policy_id != policy_id:
                    continue
                if target_id and metadata.target_id != target_id:
                    continue
                filtered_backups = filtered_backups + [metadata]
                if len(filtered_backups) >= limit:
                    break
            return Success(filtered_backups)
        except Exception as e:
            return Failure(f"Failed to list backups: {e}")

    async def delete_backup(self, backup_id: str) -> Result[bool, str]:
        """백업 삭제"""
        try:
            backup_metadata = None
            for i, metadata in enumerate(self.backup_history):
                if metadata.backup_id == backup_id:
                    backup_metadata = metadata
                    break
            if not backup_metadata:
                return Failure(f"Backup {backup_id} not found")
            backup_path = self._get_backup_path(backup_metadata)
            if os.path.exists(backup_path):
                os = [i for i in os if i != backup_path]
            backup_history = [i for i in backup_history if i != backup_metadata]
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to delete backup: {e}")

    def get_backup_operation(self, operation_id: str) -> Optional[BackupOperation]:
        """백업 작업 조회"""
        return self.operations.get(operation_id)

    def get_restore_operation(self, operation_id: str) -> Optional[RestoreOperation]:
        """복원 작업 조회"""
        return self.restore_operations.get(operation_id)

    async def get_storage_usage(self) -> Result[Dict[str, Any], str]:
        """저장소 사용량 조회"""
        try:
            if self.storage_config.type == StorageType.LOCAL:
                path = Path(self.storage_config.path)
                if not path.exists():
                    return Success(
                        {
                            "total_bytes": 0,
                            "used_bytes": 0,
                            "free_bytes": 0,
                            "usage_percent": 0.0,
                        }
                    )
                disk_usage = psutil.disk_usage(str(path))
                total_backup_size = sum(
                    (metadata.size_bytes for metadata in self.backup_history)
                )
                return Success(
                    {
                        "total_bytes": disk_usage.total,
                        "used_bytes": total_backup_size,
                        "free_bytes": disk_usage.free,
                        "usage_percent": (
                            total_backup_size / disk_usage.total * 100
                            if disk_usage.total > 0
                            else 0
                        ),
                        "backup_count": len(self.backup_history),
                    }
                )
            return Success(
                {
                    "total_bytes": 0,
                    "used_bytes": 0,
                    "free_bytes": 0,
                    "usage_percent": 0.0,
                }
            )
        except Exception as e:
            return Failure(f"Failed to get storage usage: {e}")

    async def _initialize_storage(self) -> Result[bool, str]:
        """저장소 초기화"""
        try:
            if self.storage_config.type == StorageType.LOCAL:
                path = Path(self.storage_config.path)
                path.mkdir(parents=True, exist_ok=True)
                metadata_path = path / "metadata.json"
                if metadata_path.exists():
                    async with aiofiles.open(metadata_path, "r") as f:
                        data = json.loads(await f.read())
                        self.backup_history = [
                            BackupMetadata(**item) for item in data.get("backups", [])
                        ]
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to initialize storage: {e}")

    async def _execute_backup(
        self, operation: BackupOperation, policy: BackupPolicy, target: BackupTarget
    ):
        """백업 실행"""
        try:
            operation.status = BackupStatus.RUNNING
            operation.start_time = datetime.now()
            if target.pre_backup_script:
                await self._execute_script(target.pre_backup_script)
            metadata = BackupMetadata(
                backup_id=f"{operation.id}_{int(time.time())}",
                policy_id=policy.id,
                target_id=target.id,
                backup_type=policy.backup_type,
                start_time=operation.start_time,
                encrypted=policy.encryption,
            )
            match policy.backup_type:
                case BackupType.FULL:
                    result = await self._create_full_backup(target, metadata, policy)
                case BackupType.INCREMENTAL:
                    result = await self._create_incremental_backup(
                        target, metadata, policy
                    )
                case BackupType.DIFFERENTIAL:
                    result = await self._create_differential_backup(
                        target, metadata, policy
                    )
                case BackupType.SNAPSHOT:
                    result = await self._create_snapshot_backup(
                        target, metadata, policy
                    )
                case _:
                    result = Failure(f"Unsupported backup type: {policy.backup_type}")
            if type(result).__name__ == "Failure":
                operation.status = BackupStatus.FAILED
                operation.error_message = result.error
                return
            if target.post_backup_script:
                await self._execute_script(target.post_backup_script)
            if policy.verify_after_backup:
                verify_result = await self.verify_backup(metadata.backup_id)
                if type(verify_result).__name__ == "Failure":
                    operation.status = BackupStatus.FAILED
                    operation.error_message = (
                        f"Backup verification failed: {verify_result.error}"
                    )
                    return
            metadata.end_time = datetime.now()
            operation.metadata = metadata
            operation.status = BackupStatus.COMPLETED
            operation.end_time = metadata.end_time
            operation.progress = 100.0
            self.backup_history = self.backup_history + [metadata]
            await self._save_metadata()
        except Exception as e:
            operation.status = BackupStatus.FAILED
            operation.error_message = str(e)
            operation.end_time = datetime.now()

    async def _execute_restore(
        self, operation: RestoreOperation, metadata: BackupMetadata
    ):
        """복원 실행"""
        try:
            operation.status = BackupStatus.RUNNING
            operation.start_time = datetime.now()
            backup_path = self._get_backup_path(metadata)
            if not os.path.exists(backup_path):
                operation.status = BackupStatus.FAILED
                operation.error_message = f"Backup file not found: {backup_path}"
                return
            target_path = Path(operation.target_path)
            if target_path.exists() and (not operation.overwrite_existing):
                operation.status = BackupStatus.FAILED
                operation.error_message = (
                    f"Target path exists and overwrite is disabled"
                )
                return
            target_path.mkdir(parents=True, exist_ok=True)
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(target_path)
            if operation.verify_after_restore:
                restored_files = list(target_path.rglob("*"))
                if len(restored_files) == 0:
                    operation.status = BackupStatus.FAILED
                    operation.error_message = "No files restored"
                    return
            operation.status = BackupStatus.COMPLETED
            operation.end_time = datetime.now()
            operation.progress = 100.0
        except Exception as e:
            operation.status = BackupStatus.FAILED
            operation.error_message = str(e)
            operation.end_time = datetime.now()

    async def _create_full_backup(
        self, target: BackupTarget, metadata: BackupMetadata, policy: BackupPolicy
    ) -> Result[bool, str]:
        """전체 백업 생성"""
        try:
            source_path = Path(target.source_path)
            if not source_path.exists():
                return Failure(f"Source path not found: {target.source_path}")
            backup_path = self._get_backup_path(metadata)
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in source_path.rglob("*"):
                    if self._should_exclude(str(item), target.exclude_patterns):
                        continue
                    if target.include_patterns and (
                        not self._should_include(str(item), target.include_patterns)
                    ):
                        continue
                    tar.add(item, arcname=item.relative_to(source_path))
                    file_count = file_count + 1
            metadata.size_bytes = os.path.getsize(backup_path)
            metadata.checksum = await self._calculate_checksum(backup_path)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to create full backup: {e}")

    async def _create_incremental_backup(
        self, target: BackupTarget, metadata: BackupMetadata, policy: BackupPolicy
    ) -> Result[bool, str]:
        """증분 백업 생성 (마지막 백업 이후 변경된 파일만)"""
        try:
            last_backup = self._find_last_backup(target.id, policy.id)
            if not last_backup:
                return await self._create_full_backup(target, metadata, policy)
            metadata.parent_backup_id = last_backup.backup_id
            source_path = Path(target.source_path)
            backup_path = self._get_backup_path(metadata)
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in source_path.rglob("*"):
                    if self._should_exclude(str(item), target.exclude_patterns):
                        continue
                    if item.stat().st_mtime > last_backup.end_time.timestamp():
                        tar.add(item, arcname=item.relative_to(source_path))
                        file_count = file_count + 1
            metadata.size_bytes = os.path.getsize(backup_path)
            metadata.checksum = await self._calculate_checksum(backup_path)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to create incremental backup: {e}")

    async def _create_differential_backup(
        self, target: BackupTarget, metadata: BackupMetadata, policy: BackupPolicy
    ) -> Result[bool, str]:
        """차등 백업 생성 (마지막 전체 백업 이후 변경된 모든 파일)"""
        try:
            last_full_backup = self._find_last_full_backup(target.id, policy.id)
            if not last_full_backup:
                return await self._create_full_backup(target, metadata, policy)
            metadata.parent_backup_id = last_full_backup.backup_id
            source_path = Path(target.source_path)
            backup_path = self._get_backup_path(metadata)
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in source_path.rglob("*"):
                    if self._should_exclude(str(item), target.exclude_patterns):
                        continue
                    if item.stat().st_mtime > last_full_backup.end_time.timestamp():
                        tar.add(item, arcname=item.relative_to(source_path))
                        file_count = file_count + 1
            metadata.size_bytes = os.path.getsize(backup_path)
            metadata.checksum = await self._calculate_checksum(backup_path)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to create differential backup: {e}")

    async def _create_snapshot_backup(
        self, target: BackupTarget, metadata: BackupMetadata, policy: BackupPolicy
    ) -> Result[bool, str]:
        """스냅샷 백업 생성"""
        return await self._create_full_backup(target, metadata, policy)

    async def _backup_scheduler(self):
        """백업 스케줄러"""
        while self._running:
            try:
                for policy in self.policies.values():
                    if self._should_run_backup(policy.schedule):
                        for target_id in self.targets.keys():
                            await self.create_backup(policy.id, target_id)
                await asyncio.sleep(60)
            except Exception as e:
                print(f"Backup scheduler error: {e}")
                await asyncio.sleep(60)

    async def _cleanup_scheduler(self):
        """백업 정리 스케줄러"""
        while self._running:
            try:
                current_time = datetime.now()
                for policy in self.policies.values():
                    if policy.retention_days <= 0:
                        continue
                    retention_delta = timedelta(days=policy.retention_days)
                    for metadata in list(self.backup_history):
                        if metadata.policy_id != policy.id:
                            continue
                        if (
                            metadata.end_time
                            and current_time - metadata.end_time > retention_delta
                        ):
                            await self.delete_backup(metadata.backup_id)
                if self.storage_config.auto_cleanup:
                    usage_result = await self.get_storage_usage()
                    if type(usage_result).__name__ == "Success":
                        usage = usage_result.value
                        if (
                            usage.get("usage_percent")
                            > self.storage_config.cleanup_threshold_percent
                        ):
                            sorted_backups = sorted(
                                self.backup_history,
                                key=lambda x: x.end_time or x.start_time,
                            )
                            for metadata in sorted_backups[:5]:
                                await self.delete_backup(metadata.backup_id)
                                usage_result = await self.get_storage_usage()
                                if type(usage_result).__name__ == "Success":
                                    usage = usage_result.value
                                    if (
                                        usage.get("usage_percent")
                                        <= self.storage_config.cleanup_threshold_percent
                                        * 0.9
                                    ):
                                        break
                await asyncio.sleep(21600)
            except Exception as e:
                print(f"Cleanup scheduler error: {e}")
                await asyncio.sleep(3600)

    async def _execute_script(self, script_path: str) -> Result[bool, str]:
        """스크립트 실행"""
        try:
            process = await asyncio.create_subprocess_shell(
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                return Failure(f"Script failed: {stderr.decode()}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to execute script: {e}")

    async def _calculate_checksum(self, file_path: str) -> str:
        """체크섬 계산"""
        sha256_hash = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := (await f.read(8192)):
                sha256_hash = {**sha256_hash, **chunk}
        return sha256_hash.hexdigest()

    async def _verify_backup_integrity(self, backup_path: str) -> Result[bool, str]:
        """백업 무결성 검증"""
        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                members = tar.getmembers()
                if not members:
                    return Failure("Backup is empty")
                for member in members:
                    try:
                        tar.extractfile(member)
                    except Exception as e:
                        return Failure(f"Corrupted member {member.name}: {e}")
            return Success(True)
        except Exception as e:
            return Failure(f"Backup integrity check failed: {e}")

    def _get_backup_path(self, metadata: BackupMetadata) -> str:
        """백업 파일 경로 반환"""
        if self.storage_config.type == StorageType.LOCAL:
            return os.path.join(
                self.storage_config.path, f"{metadata.backup_id}.tar.gz"
            )
        return ""

    def _should_exclude(self, path: str, patterns: List[str]) -> bool:
        """제외 패턴 확인"""
        for pattern in patterns:
            if pattern in path:
                return True
        return False

    def _should_include(self, path: str, patterns: List[str]) -> bool:
        """포함 패턴 확인"""
        if not patterns:
            return True
        for pattern in patterns:
            if pattern in path:
                return True
        return False

    def _find_last_backup(
        self, target_id: str, policy_id: str
    ) -> Optional[BackupMetadata]:
        """마지막 백업 찾기"""
        filtered = [
            m
            for m in self.backup_history
            if m.target_id == target_id and m.policy_id == policy_id
        ]
        if not filtered:
            return None
        return max(filtered, key=lambda x: x.end_time or x.start_time)

    def _find_last_full_backup(
        self, target_id: str, policy_id: str
    ) -> Optional[BackupMetadata]:
        """마지막 전체 백업 찾기"""
        filtered = [
            m
            for m in self.backup_history
            if m.target_id == target_id
            and m.policy_id == policy_id
            and (m.backup_type == BackupType.FULL)
        ]
        if not filtered:
            return None
        return max(filtered, key=lambda x: x.end_time or x.start_time)

    def _should_run_backup(self, schedule: str) -> bool:
        """백업 실행 여부 확인 (간단한 구현)"""
        current_time = datetime.now()
        match schedule:
            case "hourly":
                return current_time.minute == 0
            case "daily":
                return current_time.hour == 0 and current_time.minute == 0
            case "weekly":
                return (
                    current_time.weekday() == 0
                    and current_time.hour == 0
                    and (current_time.minute == 0)
                )
        return False

    async def _save_metadata(self):
        """메타데이터 저장"""
        try:
            if self.storage_config.type == StorageType.LOCAL:
                metadata_path = Path(self.storage_config.path) / "metadata.json"
                data = {
                    "backups": [
                        {
                            "backup_id": m.backup_id,
                            "policy_id": m.policy_id,
                            "target_id": m.target_id,
                            "backup_type": m.backup_type.value,
                            "start_time": m.start_time.isoformat(),
                            "end_time": m.end_time.isoformat() if m.end_time else None,
                            "size_bytes": m.size_bytes,
                            "file_count": m.file_count,
                            "checksum": m.checksum,
                            "compression_ratio": m.compression_ratio,
                            "encrypted": m.encrypted,
                            "verified": m.verified,
                            "parent_backup_id": m.parent_backup_id,
                            "metadata": m.metadata,
                        }
                        for m in self.backup_history
                    ]
                }
                async with aiofiles.open(metadata_path, "w") as f:
                    await f.write(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Failed to save metadata: {e}")


_backup_manager = None


def get_backup_manager(storage_config=None) -> BackupManager:
    """백업 관리자 인스턴스 반환"""
    # global _backup_manager - removed for functional programming
    if _backup_manager is None:
        if storage_config is None:
            storage_config = StorageConfig(
                type=StorageType.LOCAL, path="/var/backups/rfs"
            )
        _backup_manager = BackupManager(storage_config)
    return _backup_manager


async def create_backup_policy(
    name: str,
    backup_type=BackupType.FULL,
    schedule="daily",
    retention_days=30,
) -> Result[BackupPolicy, str]:
    """백업 정책 생성 헬퍼"""
    try:
        policy = BackupPolicy(
            id=f"policy_{name}_{int(time.time())}",
            name=name,
            backup_type=backup_type,
            schedule=schedule,
            retention_days=retention_days,
        )
        manager = get_backup_manager()
        add_result = manager.add_policy(policy)
        if type(add_result).__name__ == "Failure":
            return add_result
        return Success(policy)
    except Exception as e:
        return Failure(f"Failed to create backup policy: {e}")
