"""
RFS Database Migration (RFS v4.1)

데이터베이스 마이그레이션 시스템
"""

import asyncio
import importlib.util
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = get_logger(__name__)


class MigrationStatus(str, Enum):
    """마이그레이션 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationInfo:
    """마이그레이션 정보"""

    version: str
    name: str
    description = ""
    created_at: datetime = field(default_factory=datetime.now)
    applied_at = None
    status: MigrationStatus = MigrationStatus.PENDING
    checksum = None


class Migration(ABC):
    """마이그레이션 기본 클래스"""

    def __init__(self, version: str, name: str, description=""):
        self.info = MigrationInfo(version, name, description)

    @abstractmethod
    async def up(self) -> Result[None, str]:
        """마이그레이션 적용"""
        pass

    @abstractmethod
    async def down(self) -> Result[None, str]:
        """마이그레이션 롤백"""
        pass

    def validate(self) -> Result[None, str]:
        """마이그레이션 유효성 검증"""
        if not self.info.version:
            return Failure("마이그레이션 버전이 필요합니다")
        if not self.info.name:
            return Failure("마이그레이션 이름이 필요합니다")
        return Success(None)


class SQLMigration(Migration):
    """SQL 마이그레이션"""

    def __init__(
        self, version: str, name: str, up_sql: str, down_sql: str, description=""
    ):
        super().__init__(version, name, description)
        self.up_sql = up_sql
        self.down_sql = down_sql

    async def up(self) -> Result[None, str]:
        """SQL 마이그레이션 적용"""
        try:
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            result = await database.execute_query(self.up_sql)
            if not result.is_success():
                return Failure(f"마이그레이션 실행 실패: {result.unwrap_err()}")
            logger.info(f"마이그레이션 적용 완료: {self.info.name}")
            return Success(None)
        except Exception as e:
            return Failure(f"마이그레이션 적용 실패: {str(e)}")

    async def down(self) -> Result[None, str]:
        """SQL 마이그레이션 롤백"""
        try:
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            result = await database.execute_query(self.down_sql)
            if not result.is_success():
                return Failure(f"마이그레이션 롤백 실패: {result.unwrap_err()}")
            logger.info(f"마이그레이션 롤백 완료: {self.info.name}")
            return Success(None)
        except Exception as e:
            return Failure(f"마이그레이션 롤백 실패: {str(e)}")


class PythonMigration(Migration):
    """Python 마이그레이션"""

    def __init__(self, version: str, name: str, up_func, down_func, description=""):
        super().__init__(version, name, description)
        self.up_func = up_func
        self.down_func = down_func

    async def up(self) -> Result[None, str]:
        """Python 마이그레이션 적용"""
        try:
            if asyncio.iscoroutinefunction(self.up_func):
                result = await self.up_func()
            else:
                result = self.up_func()
            if type(result).__name__ == "Result":
                return result
            logger.info(f"마이그레이션 적용 완료: {self.info.name}")
            return Success(None)
        except Exception as e:
            return Failure(f"마이그레이션 적용 실패: {str(e)}")

    async def down(self) -> Result[None, str]:
        """Python 마이그레이션 롤백"""
        try:
            if asyncio.iscoroutinefunction(self.down_func):
                result = await self.down_func()
            else:
                result = self.down_func()
            if type(result).__name__ == "Result":
                return result
            logger.info(f"마이그레이션 롤백 완료: {self.info.name}")
            return Success(None)
        except Exception as e:
            return Failure(f"마이그레이션 롤백 실패: {str(e)}")


class MigrationManager(ABC):
    """마이그레이션 매니저 기본 클래스"""

    def __init__(self, migrations_dir="migrations"):
        self.migrations_dir = migrations_dir
        self.migrations = {}

    @abstractmethod
    async def create_migration_table(self) -> Result[None, str]:
        """마이그레이션 테이블 생성"""
        pass

    @abstractmethod
    async def get_applied_migrations(self) -> Result[List[str], str]:
        """적용된 마이그레이션 목록 조회"""
        pass

    @abstractmethod
    async def record_migration(self, migration: Migration) -> Result[None, str]:
        """마이그레이션 기록"""
        pass

    @abstractmethod
    async def remove_migration_record(self, version: str) -> Result[None, str]:
        """마이그레이션 기록 제거"""
        pass

    async def discover_migrations(self) -> Result[List[Migration], str]:
        """마이그레이션 파일 검색"""
        try:
            if not os.path.exists(self.migrations_dir):
                logger.warning(
                    f"마이그레이션 디렉토리가 없습니다: {self.migrations_dir}"
                )
                return Success([])
            migrations = []
            for filename in sorted(os.listdir(self.migrations_dir)):
                if filename.endswith(".py") and filename != "__init__.py":
                    result = await self._load_migration_file(filename)
                    if result.is_success():
                        migration = result.unwrap()
                        migrations = migrations + [migration]
                        self.migrations = {
                            **self.migrations,
                            migration.info.version: migration,
                        }
            logger.info(f"마이그레이션 검색 완료: {len(migrations)}개")
            return Success(migrations)
        except Exception as e:
            return Failure(f"마이그레이션 검색 실패: {str(e)}")

    async def _load_migration_file(self, filename: str) -> Result[Migration, str]:
        """마이그레이션 파일 로드"""
        try:
            filepath = os.path.join(self.migrations_dir, filename)
            spec = importlib.util.spec_from_file_location("migration", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "Migration"):
                migration_class = module.Migration
                if issubclass(migration_class, Migration):
                    migration = migration_class()
                    return Success(migration)
            return Failure(f"Migration 클래스를 찾을 수 없습니다: {filename}")
        except Exception as e:
            return Failure(f"마이그레이션 파일 로드 실패 ({filename}): {str(e)}")

    async def run_migrations(
        self, target_version: str = None
    ) -> Result[List[str], str]:
        """마이그레이션 실행"""
        try:
            table_result = await self.create_migration_table()
            if not table_result.is_success():
                return Failure(table_result.unwrap_err())
            discover_result = await self.discover_migrations()
            if not discover_result.is_success():
                return Failure(discover_result.unwrap_err())
            all_migrations = discover_result.unwrap()
            applied_result = await self.get_applied_migrations()
            if not applied_result.is_success():
                return Failure(applied_result.unwrap_err())
            applied_versions = set(applied_result.unwrap())
            pending_migrations = []
            for migration in sorted(all_migrations, key=lambda m: m.info.version):
                if migration.info.version not in applied_versions:
                    pending_migrations = pending_migrations + [migration]
                    if target_version and migration.info.version == target_version:
                        break
            applied_migrations = []
            for migration in pending_migrations:
                logger.info(f"마이그레이션 실행 중: {migration.info.name}")
                migration.info.status = MigrationStatus.RUNNING
                up_result = await migration.up()
                if not up_result.is_success():
                    migration.info.status = MigrationStatus.FAILED
                    return Failure(
                        f"마이그레이션 실패 ({migration.info.name}): {up_result.unwrap_err()}"
                    )
                migration.info.status = MigrationStatus.COMPLETED
                migration.info.applied_at = datetime.now()
                record_result = await self.record_migration(migration)
                if not record_result.is_success():
                    return Failure(
                        f"마이그레이션 기록 실패: {record_result.unwrap_err()}"
                    )
                applied_migrations = applied_migrations + [migration.info.version]
                logger.info(f"마이그레이션 완료: {migration.info.name}")
            logger.info(f"마이그레이션 실행 완료: {len(applied_migrations)}개")
            return Success(applied_migrations)
        except Exception as e:
            return Failure(f"마이그레이션 실행 실패: {str(e)}")

    async def rollback_migration(
        self, target_version: str = None
    ) -> Result[List[str], str]:
        """마이그레이션 롤백"""
        try:
            applied_result = await self.get_applied_migrations()
            if not applied_result.is_success():
                return Failure(applied_result.unwrap_err())
            applied_versions = applied_result.unwrap()
            rollback_migrations = []
            for version in reversed(sorted(applied_versions)):
                if version in self.migrations:
                    rollback_migrations = rollback_migrations + [
                        self.migrations[version]
                    ]
                    if target_version and version == target_version:
                        break
            rolled_back = []
            for migration in rollback_migrations:
                logger.info(f"마이그레이션 롤백 중: {migration.info.name}")
                down_result = await migration.down()
                if not down_result.is_success():
                    migration.info.status = MigrationStatus.FAILED
                    return Failure(
                        f"마이그레이션 롤백 실패 ({migration.info.name}): {down_result.unwrap_err()}"
                    )
                remove_result = await self.remove_migration_record(
                    migration.info.version
                )
                if not remove_result.is_success():
                    return Failure(
                        f"마이그레이션 기록 제거 실패: {remove_result.unwrap_err()}"
                    )
                migration.info.status = MigrationStatus.ROLLED_BACK
                rolled_back = rolled_back + [migration.info.version]
                logger.info(f"마이그레이션 롤백 완료: {migration.info.name}")
            logger.info(f"마이그레이션 롤백 완료: {len(rolled_back)}개")
            return Success(rolled_back)
        except Exception as e:
            return Failure(f"마이그레이션 롤백 실패: {str(e)}")


class AlembicMigrationManager(MigrationManager):
    """Alembic 마이그레이션 매니저"""

    def __init__(self, migrations_dir="migrations"):
        super().__init__(migrations_dir)
        try:
            import alembic

            self.alembic_available = True
        except ImportError:
            self.alembic_available = False
            logger.warning("Alembic이 설치되지 않았습니다")

    async def create_migration_table(self) -> Result[None, str]:
        """마이그레이션 테이블 생성"""
        try:
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            create_table_sql = "\n            CREATE TABLE IF NOT EXISTS rfs_migrations (\n                version VARCHAR(255) PRIMARY KEY,\n                name VARCHAR(255) NOT NULL,\n                description TEXT,\n                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                checksum VARCHAR(255)\n            )\n            "
            result = await database.execute_query(create_table_sql)
            if not result.is_success():
                return Failure(f"마이그레이션 테이블 생성 실패: {result.unwrap_err()}")
            return Success(None)
        except Exception as e:
            return Failure(f"마이그레이션 테이블 생성 실패: {str(e)}")

    async def get_applied_migrations(self) -> Result[List[str], str]:
        """적용된 마이그레이션 목록 조회"""
        try:
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            query = "SELECT version FROM rfs_migrations ORDER BY version"
            result = await database.execute_query(query)
            if not result.is_success():
                return Failure(f"마이그레이션 조회 실패: {result.unwrap_err()}")
            rows = result.unwrap()
            versions = [
                row[0] if type(row).__name__ == "tuple" else row.version for row in rows
            ]
            return Success(versions)
        except Exception as e:
            return Failure(f"마이그레이션 조회 실패: {str(e)}")

    async def record_migration(self, migration: Migration) -> Result[None, str]:
        """마이그레이션 기록"""
        try:
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            insert_sql = "\n            INSERT INTO rfs_migrations (version, name, description, applied_at, checksum)\n            VALUES (?, ?, ?, ?, ?)\n            "
            params = {
                "version": migration.info.version,
                "name": migration.info.name,
                "description": migration.info.description,
                "applied_at": migration.info.applied_at,
                "checksum": migration.info.checksum,
            }
            result = await database.execute_query(insert_sql, params)
            if not result.is_success():
                return Failure(f"마이그레이션 기록 실패: {result.unwrap_err()}")
            return Success(None)
        except Exception as e:
            return Failure(f"마이그레이션 기록 실패: {str(e)}")

    async def remove_migration_record(self, version: str) -> Result[None, str]:
        """마이그레이션 기록 제거"""
        try:
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            delete_sql = "DELETE FROM rfs_migrations WHERE version = ?"
            params = {"version": version}
            result = await database.execute_query(delete_sql, params)
            if not result.is_success():
                return Failure(f"마이그레이션 기록 제거 실패: {result.unwrap_err()}")
            return Success(None)
        except Exception as e:
            return Failure(f"마이그레이션 기록 제거 실패: {str(e)}")


_migration_manager = None


def get_migration_manager() -> Optional[MigrationManager]:
    """마이그레이션 매니저 인스턴스 반환"""
    return _migration_manager


def set_migration_manager(manager: MigrationManager):
    """마이그레이션 매니저 설정"""
    # global _migration_manager - removed for functional programming
    _migration_manager = manager


def create_migration(
    version: str,
    name: str,
    up_sql: str = None,
    down_sql: str = None,
    up_func=None,
    down_func=None,
    description="",
) -> Migration:
    """마이그레이션 생성"""
    if up_sql and down_sql:
        return SQLMigration(version, name, up_sql, down_sql, description)
    elif up_func and down_func:
        return PythonMigration(version, name, up_func, down_func, description)
    else:
        raise ValueError("SQL 또는 Python 함수를 제공해야 합니다")


async def run_migrations(target_version: str = None) -> Result[List[str], str]:
    """마이그레이션 실행"""
    manager = get_migration_manager()
    if not manager:
        return Failure("마이그레이션 매니저가 설정되지 않았습니다")
    return await manager.run_migrations(target_version)


async def rollback_migration(target_version: str = None) -> Result[List[str], str]:
    """마이그레이션 롤백"""
    manager = get_migration_manager()
    if not manager:
        return Failure("마이그레이션 매니저가 설정되지 않았습니다")
    return await manager.rollback_migration(target_version)
