"""
Simplified unit tests for database migration module
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rfs.core.result import Failure, Success
from rfs.database.migration import (
    Migration,
    MigrationInfo,
    MigrationManager,
    MigrationStatus,
    PythonMigration,
    SQLMigration,
)


class TestMigrationStatus:
    """Test MigrationStatus enumeration"""

    def test_migration_status_values(self):
        """Test migration status enum values"""
        assert MigrationStatus.PENDING.value == "pending"
        assert MigrationStatus.RUNNING.value == "running"
        assert MigrationStatus.COMPLETED.value == "completed"
        assert MigrationStatus.FAILED.value == "failed"
        assert MigrationStatus.ROLLED_BACK.value == "rolled_back"


class TestMigrationInfo:
    """Test MigrationInfo dataclass"""

    def test_migration_info_creation(self):
        """Test creating migration info"""
        info = MigrationInfo(
            version="001", name="test_migration", description="Test migration"
        )

        assert info.version == "001"
        assert info.name == "test_migration"
        assert info.description == "Test migration"
        assert info.status == MigrationStatus.PENDING
        assert info.applied_at is None
        assert isinstance(info.created_at, datetime)

    def test_migration_info_defaults(self):
        """Test migration info with default values"""
        info = MigrationInfo("001", "test")

        assert info.description == ""
        assert info.status == MigrationStatus.PENDING
        assert info.checksum is None


class TestMigrationBaseClass:
    """Test Migration abstract base class"""

    def test_migration_validation_success(self):
        """Test successful migration validation"""

        class TestMigration(Migration):
            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration = TestMigration("001", "test_migration")
        result = migration.validate()

        assert result.is_success()

    def test_migration_validation_missing_version(self):
        """Test migration validation with missing version"""

        class TestMigration(Migration):
            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration = TestMigration("", "test_migration")
        result = migration.validate()

        assert result.is_failure()
        assert "버전이 필요합니다" in str(result.unwrap_error())

    def test_migration_validation_missing_name(self):
        """Test migration validation with missing name"""

        class TestMigration(Migration):
            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration = TestMigration("001", "")
        result = migration.validate()

        assert result.is_failure()
        assert "이름이 필요합니다" in str(result.unwrap_error())


class TestSQLMigration:
    """Test SQLMigration class"""

    def test_sql_migration_creation(self):
        """Test creating SQL migration"""
        migration = SQLMigration(
            version="001",
            name="create_users_table",
            up_sql="CREATE TABLE users (id INT PRIMARY KEY);",
            down_sql="DROP TABLE users;",
            description="Create users table",
        )

        assert migration.info.version == "001"
        assert migration.info.name == "create_users_table"
        assert migration.up_sql == "CREATE TABLE users (id INT PRIMARY KEY);"
        assert migration.down_sql == "DROP TABLE users;"

    @pytest.mark.asyncio
    async def test_sql_migration_up_success(self):
        """Test successful SQL migration up"""
        migration = SQLMigration(
            "001", "test", "CREATE TABLE test;", "DROP TABLE test;"
        )

        mock_database = Mock()
        mock_database.execute_query = AsyncMock(return_value=Success(None))

        with patch("rfs.database.base.get_database", return_value=mock_database):
            result = await migration.up()

        assert result.is_success()
        mock_database.execute_query.assert_called_once_with("CREATE TABLE test;")

    @pytest.mark.asyncio
    async def test_sql_migration_up_no_database(self):
        """Test SQL migration up with no database connection"""
        migration = SQLMigration(
            "001", "test", "CREATE TABLE test;", "DROP TABLE test;"
        )

        with patch("rfs.database.base.get_database", return_value=None):
            result = await migration.up()

        assert result.is_failure()
        assert "데이터베이스 연결을 찾을 수 없습니다" in str(result.unwrap_error())

    @pytest.mark.asyncio
    async def test_sql_migration_down_success(self):
        """Test successful SQL migration down"""
        migration = SQLMigration(
            "001", "test", "CREATE TABLE test;", "DROP TABLE test;"
        )

        mock_database = Mock()
        mock_database.execute_query = AsyncMock(return_value=Success(None))

        with patch("rfs.database.base.get_database", return_value=mock_database):
            result = await migration.down()

        assert result.is_success()
        mock_database.execute_query.assert_called_once_with("DROP TABLE test;")


class TestPythonMigration:
    """Test PythonMigration class"""

    def test_python_migration_creation(self):
        """Test creating Python migration"""
        up_func = Mock()
        down_func = Mock()

        migration = PythonMigration(
            version="001",
            name="seed_data",
            up_func=up_func,
            down_func=down_func,
            description="Seed initial data",
        )

        assert migration.info.version == "001"
        assert migration.info.name == "seed_data"
        assert migration.up_func == up_func
        assert migration.down_func == down_func

    @pytest.mark.asyncio
    async def test_python_migration_sync_function(self):
        """Test Python migration with sync function"""
        up_func = Mock(return_value=Success(None))
        down_func = Mock(return_value=Success(None))

        migration = PythonMigration("001", "test", up_func, down_func)

        result = await migration.up()
        assert result.is_success()
        up_func.assert_called_once()

        result = await migration.down()
        assert result.is_success()
        down_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_python_migration_async_function(self):
        """Test Python migration with async function"""
        up_func = AsyncMock(return_value=Success(None))
        down_func = AsyncMock(return_value=Success(None))

        migration = PythonMigration("001", "test", up_func, down_func)

        result = await migration.up()
        assert result.is_success()
        up_func.assert_called_once()

        result = await migration.down()
        assert result.is_success()
        down_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_python_migration_function_exception(self):
        """Test Python migration with function exception"""
        up_func = Mock(side_effect=Exception("Function failed"))
        migration = PythonMigration("001", "test", up_func, Mock())

        result = await migration.up()
        assert result.is_failure()
        assert "Function failed" in str(result.unwrap_error())


class TestMigrationManager:
    """Test MigrationManager abstract class and common functionality"""

    def test_migration_manager_initialization(self):
        """Test migration manager initialization"""

        class ConcreteMigrationManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        manager = ConcreteMigrationManager("custom_migrations")
        assert manager.migrations_dir == "custom_migrations"
        assert manager.migrations == {}

    def test_migration_manager_default_dir(self):
        """Test migration manager with default directory"""

        class ConcreteMigrationManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        manager = ConcreteMigrationManager()
        assert manager.migrations_dir == "migrations"

    @pytest.mark.asyncio
    async def test_discover_migrations_no_directory(self):
        """Test discovering migrations when directory doesn't exist"""

        class ConcreteMigrationManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        manager = ConcreteMigrationManager("nonexistent_dir")
        result = await manager.discover_migrations()

        assert result.is_success()
        assert result.unwrap() == []

    @pytest.mark.asyncio
    async def test_discover_migrations_empty_directory(self):
        """Test discovering migrations in empty directory"""

        class ConcreteMigrationManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ConcreteMigrationManager(temp_dir)
            result = await manager.discover_migrations()

            assert result.is_success()
            assert result.unwrap() == []


class TestMigrationWorkflow:
    """Test migration workflow integration"""

    @pytest.mark.asyncio
    async def test_run_migrations_workflow(self):
        """Test complete run migrations workflow"""

        class TestMigrationManager(MigrationManager):
            def __init__(self):
                super().__init__()
                self.applied = []
                self.table_created = False

            async def create_migration_table(self):
                self.table_created = True
                return Success(None)

            async def get_applied_migrations(self):
                return Success(self.applied)

            async def record_migration(self, migration):
                self.applied.append(migration.info.version)
                return Success(None)

            async def remove_migration_record(self, version):
                if version in self.applied:
                    self.applied.remove(version)
                return Success(None)

        manager = TestMigrationManager()

        # Create test migrations
        class TestMigration1(Migration):
            def __init__(self):
                super().__init__("001", "first_migration")

            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        class TestMigration2(Migration):
            def __init__(self):
                super().__init__("002", "second_migration")

            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        # Add migrations to manager
        migration1 = TestMigration1()
        migration2 = TestMigration2()
        manager.migrations["001"] = migration1
        manager.migrations["002"] = migration2

        # Mock discover_migrations to return our test migrations
        with patch.object(
            manager,
            "discover_migrations",
            return_value=Success([migration1, migration2]),
        ):
            result = await manager.run_migrations()

        assert result.is_success()
        applied = result.unwrap()
        assert "001" in applied
        assert "002" in applied
        assert manager.table_created
        assert migration1.info.status == MigrationStatus.COMPLETED
        assert migration2.info.status == MigrationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_migrations_with_target(self):
        """Test run migrations with target version"""

        class TestMigrationManager(MigrationManager):
            def __init__(self):
                super().__init__()
                self.applied = []

            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success(self.applied)

            async def record_migration(self, migration):
                self.applied.append(migration.info.version)
                return Success(None)

            async def remove_migration_record(self, version):
                if version in self.applied:
                    self.applied.remove(version)
                return Success(None)

        manager = TestMigrationManager()

        class TestMigration(Migration):
            def __init__(self, version, name):
                super().__init__(version, name)

            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration1 = TestMigration("001", "first")
        migration2 = TestMigration("002", "second")

        with patch.object(
            manager,
            "discover_migrations",
            return_value=Success([migration1, migration2]),
        ):
            # Run only up to version 001
            result = await manager.run_migrations("001")

        assert result.is_success()
        applied = result.unwrap()
        assert "001" in applied
        assert "002" not in applied

    @pytest.mark.asyncio
    async def test_migration_failure_handling(self):
        """Test migration failure handling"""

        class TestMigrationManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        manager = TestMigrationManager()

        class FailingMigration(Migration):
            def __init__(self):
                super().__init__("001", "failing_migration")

            async def up(self):
                return Failure("Migration failed")

            async def down(self):
                return Success(None)

        failing_migration = FailingMigration()

        with patch.object(
            manager, "discover_migrations", return_value=Success([failing_migration])
        ):
            result = await manager.run_migrations()

        assert result.is_failure()
        assert "Migration failed" in str(result.unwrap_error())
        assert failing_migration.info.status == MigrationStatus.FAILED
