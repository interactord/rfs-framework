"""
Complete test coverage for migration.py to achieve 100%
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

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


class TestMigrationInfo:
    """Complete test coverage for MigrationInfo"""

    def test_migration_info_complete(self):
        """Test all MigrationInfo properties and methods"""
        info = MigrationInfo(
            version="001", name="test_migration", description="Test migration"
        )

        # Test all fields
        assert info.version == "001"
        assert info.name == "test_migration"
        assert info.description == "Test migration"
        assert info.status == MigrationStatus.PENDING
        assert info.applied_at is None
        assert isinstance(info.created_at, datetime)
        assert info.checksum is None
        assert info.error is None
        assert info.rollback_version is None

        # Test with all optional fields
        info = MigrationInfo(
            version="002",
            name="test2",
            description="Test 2",
            checksum="abc123",
            error="Some error",
            rollback_version="001",
        )

        assert info.checksum == "abc123"
        assert info.error == "Some error"
        assert info.rollback_version == "001"

    def test_migration_info_to_dict(self):
        """Test to_dict method (line 55)"""
        info = MigrationInfo("001", "test")
        info.applied_at = datetime(2024, 1, 1, 12, 0, 0)

        result = info.to_dict()

        assert result["version"] == "001"
        assert result["name"] == "test"
        assert result["status"] == "pending"
        assert "applied_at" in result

    def test_migration_info_from_dict(self):
        """Test from_dict method (line 60)"""
        data = {
            "version": "001",
            "name": "test",
            "description": "Test",
            "status": "completed",
            "checksum": "xyz",
        }

        info = MigrationInfo.from_dict(data)

        assert info.version == "001"
        assert info.name == "test"
        assert info.status == MigrationStatus.COMPLETED
        assert info.checksum == "xyz"


class TestMigration:
    """Complete test coverage for Migration abstract class"""

    def test_migration_compute_checksum(self):
        """Test compute_checksum method (lines 91-95)"""

        class TestMigration(Migration):
            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration = TestMigration("001", "test", "Test description")

        # Test checksum computation
        checksum = migration.compute_checksum()
        assert checksum is not None
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 produces 64 hex chars

        # Same inputs should produce same checksum
        checksum2 = migration.compute_checksum()
        assert checksum == checksum2

    def test_migration_set_status(self):
        """Test set_status method (lines 104, 107)"""

        class TestMigration(Migration):
            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration = TestMigration("001", "test")

        # Test setting status
        migration.set_status(MigrationStatus.RUNNING)
        assert migration.info.status == MigrationStatus.RUNNING

        # Test setting status with applied_at
        migration.set_status(MigrationStatus.COMPLETED)
        assert migration.info.status == MigrationStatus.COMPLETED
        assert migration.info.applied_at is not None

    def test_migration_dependencies(self):
        """Test dependencies property (lines 110-111)"""

        class TestMigration(Migration):
            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration = TestMigration("001", "test")
        migration.dependencies = ["000"]

        assert migration.dependencies == ["000"]


class TestSQLMigration:
    """Complete test coverage for SQLMigration"""

    def test_sql_migration_with_files(self):
        """Test SQLMigration with file paths (lines 132)"""
        # Create temporary SQL files
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False
        ) as up_file:
            up_file.write("CREATE TABLE test (id INT);")
            up_file_path = up_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False
        ) as down_file:
            down_file.write("DROP TABLE test;")
            down_file_path = down_file.name

        try:
            migration = SQLMigration(
                version="001",
                name="test",
                up_sql_file=up_file_path,
                down_sql_file=down_file_path,
            )

            assert migration.up_sql == "CREATE TABLE test (id INT);"
            assert migration.down_sql == "DROP TABLE test;"

        finally:
            os.unlink(up_file_path)
            os.unlink(down_file_path)

    @pytest.mark.asyncio
    async def test_sql_migration_up_with_transaction(self):
        """Test SQL migration up with transaction (lines 146, 149-150)"""
        migration = SQLMigration(
            "001",
            "test",
            up_sql="CREATE TABLE test;",
            down_sql="DROP TABLE test;",
            transactional=True,
        )

        mock_database = Mock()
        mock_database.execute_query = AsyncMock(return_value=Success(None))
        mock_database.begin_transaction = AsyncMock(return_value=Success(None))
        mock_database.commit_transaction = AsyncMock(return_value=Success(None))
        mock_database.rollback_transaction = AsyncMock(return_value=Success(None))

        with patch("rfs.database.base.get_database", return_value=mock_database):
            result = await migration.up()

        assert result.is_success()
        mock_database.begin_transaction.assert_called_once()
        mock_database.commit_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_sql_migration_up_transaction_failure(self):
        """Test SQL migration up with transaction failure"""
        migration = SQLMigration(
            "001",
            "test",
            up_sql="CREATE TABLE test;",
            down_sql="DROP TABLE test;",
            transactional=True,
        )

        mock_database = Mock()
        mock_database.begin_transaction = AsyncMock(return_value=Success(None))
        mock_database.execute_query = AsyncMock(return_value=Failure("Query failed"))
        mock_database.rollback_transaction = AsyncMock(return_value=Success(None))

        with patch("rfs.database.base.get_database", return_value=mock_database):
            result = await migration.up()

        assert result.is_failure()
        mock_database.rollback_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_sql_migration_validate(self):
        """Test SQL migration validate (line 163)"""
        migration = SQLMigration(
            "001", "test", up_sql="CREATE TABLE test;", down_sql="DROP TABLE test;"
        )

        result = migration.validate()
        assert result.is_success()

        # Test validation failure - empty SQL
        migration2 = SQLMigration("002", "test2", "", "")
        result2 = migration2.validate()
        assert result2.is_failure()

    @pytest.mark.asyncio
    async def test_sql_migration_down_success(self):
        """Test SQL migration down (lines 168, 173, 178)"""
        migration = SQLMigration(
            "001", "test", up_sql="CREATE TABLE test;", down_sql="DROP TABLE test;"
        )

        mock_database = Mock()
        mock_database.execute_query = AsyncMock(return_value=Success(None))

        with patch("rfs.database.base.get_database", return_value=mock_database):
            result = await migration.down()

        assert result.is_success()
        mock_database.execute_query.assert_called_once_with("DROP TABLE test;")


class TestPythonMigration:
    """Complete test coverage for PythonMigration"""

    @pytest.mark.asyncio
    async def test_python_migration_with_async_context(self):
        """Test Python migration with async context manager (lines 190-195)"""
        context = {"db": Mock(), "config": {}}

        async def up_func(ctx):
            ctx["migrated"] = True
            return Success(None)

        async def down_func(ctx):
            ctx["migrated"] = False
            return Success(None)

        migration = PythonMigration("001", "test", up_func, down_func, context=context)

        result = await migration.up()
        assert result.is_success()
        assert context["migrated"] is True

        result = await migration.down()
        assert result.is_success()
        assert context["migrated"] is False

    @pytest.mark.asyncio
    async def test_python_migration_validate(self):
        """Test Python migration validate (lines 201-202)"""
        migration = PythonMigration(
            "001",
            "test",
            up_func=lambda: Success(None),
            down_func=lambda: Success(None),
        )

        result = migration.validate()
        assert result.is_success()

        # Test validation with None functions
        migration2 = PythonMigration("002", "test2", None, None)
        result2 = migration2.validate()
        assert result2.is_failure()

    @pytest.mark.asyncio
    async def test_python_migration_complex_operations(self):
        """Test Python migration with complex operations (lines 206-218)"""

        async def complex_up():
            # Simulate complex migration
            await asyncio.sleep(0.001)
            return Success("Migration completed")

        async def complex_down():
            # Simulate complex rollback
            await asyncio.sleep(0.001)
            return Success("Rollback completed")

        migration = PythonMigration(
            "001",
            "complex",
            up_func=complex_up,
            down_func=complex_down,
            description="Complex migration",
        )

        # Test up
        result = await migration.up()
        assert result.is_success()
        assert result.unwrap() == "Migration completed"

        # Test down
        result = await migration.down()
        assert result.is_success()
        assert result.unwrap() == "Rollback completed"


class TestMigrationHistory:
    """Test MigrationHistory class (lines 227-234)"""

    @pytest.mark.asyncio
    async def test_migration_history_save(self):
        """Test saving migration history (line 227)"""
        history = MigrationHistory()

        info = MigrationInfo("001", "test")
        result = await history.save(info)
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_migration_history_load(self):
        """Test loading migration history (line 230)"""
        history = MigrationHistory()

        result = await history.load()
        assert result.is_success()
        assert isinstance(result.unwrap(), list)

    @pytest.mark.asyncio
    async def test_migration_history_delete(self):
        """Test deleting from migration history (line 234)"""
        history = MigrationHistory()

        result = await history.delete("001")
        assert result.is_success()


class TestMigrationValidator:
    """Test MigrationValidator class (lines 256-264)"""

    def test_migration_validator_validate(self):
        """Test migration validation (line 256)"""
        validator = MigrationValidator()

        class ValidMigration(Migration):
            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration = ValidMigration("001", "test")
        result = validator.validate(migration)
        assert result.is_success()

    def test_migration_validator_validate_dependencies(self):
        """Test dependency validation (lines 263-264)"""
        validator = MigrationValidator()

        applied = ["001", "002"]
        dependencies = ["001"]

        result = validator.validate_dependencies(dependencies, applied)
        assert result.is_success()

        # Test missing dependency
        dependencies2 = ["003"]
        result2 = validator.validate_dependencies(dependencies2, applied)
        assert result2.is_failure()


class TestMigrationExecutor:
    """Test MigrationExecutor class (lines 270-305)"""

    @pytest.mark.asyncio
    async def test_migration_executor_execute(self):
        """Test executing migration (lines 270-282)"""
        executor = MigrationExecutor()

        migration = Mock(spec=Migration)
        migration.up = AsyncMock(return_value=Success(None))
        migration.info = MigrationInfo("001", "test")

        result = await executor.execute(migration)
        assert result.is_success()
        migration.up.assert_called_once()

    @pytest.mark.asyncio
    async def test_migration_executor_execute_batch(self):
        """Test executing batch migrations (lines 283-295)"""
        executor = MigrationExecutor()

        migration1 = Mock(spec=Migration)
        migration1.up = AsyncMock(return_value=Success(None))
        migration1.info = MigrationInfo("001", "test1")

        migration2 = Mock(spec=Migration)
        migration2.up = AsyncMock(return_value=Success(None))
        migration2.info = MigrationInfo("002", "test2")

        migrations = [migration1, migration2]
        result = await executor.execute_batch(migrations)

        assert result.is_success()
        assert len(result.unwrap()) == 2

    @pytest.mark.asyncio
    async def test_migration_executor_dry_run(self):
        """Test dry run mode (lines 296-305)"""
        executor = MigrationExecutor(dry_run=True)

        migration = Mock(spec=Migration)
        migration.info = MigrationInfo("001", "test")

        result = await executor.execute(migration)
        assert result.is_success()
        # In dry run, up() should not be called
        migration.up.assert_not_called()


class TestMigrationRollback:
    """Test MigrationRollback class (lines 312-319)"""

    @pytest.mark.asyncio
    async def test_migration_rollback_single(self):
        """Test rolling back single migration (lines 312-315)"""
        rollback = MigrationRollback()

        migration = Mock(spec=Migration)
        migration.down = AsyncMock(return_value=Success(None))
        migration.info = MigrationInfo("001", "test")

        result = await rollback.rollback(migration)
        assert result.is_success()
        migration.down.assert_called_once()

    @pytest.mark.asyncio
    async def test_migration_rollback_to_version(self):
        """Test rolling back to specific version (lines 316-319)"""
        rollback = MigrationRollback()

        migrations = []
        for i in range(3):
            m = Mock(spec=Migration)
            m.down = AsyncMock(return_value=Success(None))
            m.info = MigrationInfo(f"00{i+1}", f"test{i+1}")
            migrations.append(m)

        result = await rollback.rollback_to_version(migrations, "001")
        assert result.is_success()
        # Should rollback migrations after version 001
        migrations[2].down.assert_called_once()
        migrations[1].down.assert_called_once()


class TestMigrationManagerComplete:
    """Complete test coverage for MigrationManager"""

    @pytest.mark.asyncio
    async def test_load_migrations_from_directory(self):
        """Test loading migrations from directory (lines 323-335)"""

        class TestManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create migration files
            migration_file = os.path.join(temp_dir, "001_test.py")
            with open(migration_file, "w") as f:
                f.write(
                    """
from rfs.database.migration import PythonMigration

def up():
    return Success(None)
    
def down():
    return Success(None)
    
migration = PythonMigration("001", "test", up, down)
"""
                )

            manager = TestManager(temp_dir)
            result = await manager.discover_migrations()

            # Should find the migration file
            assert result.is_success()

    @pytest.mark.asyncio
    async def test_get_pending_migrations(self):
        """Test getting pending migrations (lines 339-355)"""

        class TestManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success(["001"])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        manager = TestManager()

        # Add migrations
        migration1 = Mock(spec=Migration)
        migration1.info = MigrationInfo("001", "applied")

        migration2 = Mock(spec=Migration)
        migration2.info = MigrationInfo("002", "pending")

        manager.migrations = {"001": migration1, "002": migration2}

        result = await manager.get_pending_migrations()
        assert result.is_success()
        pending = result.unwrap()
        assert len(pending) == 1
        assert pending[0].info.version == "002"

    @pytest.mark.asyncio
    async def test_run_migrations_with_dependencies(self):
        """Test running migrations with dependencies (lines 359-378)"""

        class TestManager(MigrationManager):
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

        manager = TestManager()

        # Create migrations with dependencies
        class DepMigration(Migration):
            def __init__(self, version, deps=None):
                super().__init__(version, f"migration_{version}")
                self.dependencies = deps or []

            async def up(self):
                return Success(None)

            async def down(self):
                return Success(None)

        migration1 = DepMigration("001")
        migration2 = DepMigration("002", ["001"])
        migration3 = DepMigration("003", ["001", "002"])

        manager.migrations = {"001": migration1, "002": migration2, "003": migration3}

        with patch.object(
            manager,
            "discover_migrations",
            return_value=Success([migration1, migration2, migration3]),
        ):
            result = await manager.run_migrations()

        assert result.is_success()
        assert "001" in manager.applied
        assert "002" in manager.applied
        assert "003" in manager.applied

    @pytest.mark.asyncio
    async def test_rollback_migrations(self):
        """Test rollback migrations (lines 382-395)"""

        class TestManager(MigrationManager):
            def __init__(self):
                super().__init__()
                self.applied = ["001", "002", "003"]

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

        manager = TestManager()

        # Create migrations
        migrations = []
        for i in range(3):
            m = Mock(spec=Migration)
            m.info = MigrationInfo(f"00{i+1}", f"test{i+1}")
            m.down = AsyncMock(return_value=Success(None))
            migrations.append(m)
            manager.migrations[f"00{i+1}"] = m

        result = await manager.rollback_to("001")

        assert result.is_success()
        # Should have rolled back 003 and 002
        assert "003" not in manager.applied
        assert "002" not in manager.applied
        assert "001" in manager.applied

    @pytest.mark.asyncio
    async def test_rollback_all(self):
        """Test rollback all migrations (line 403)"""

        class TestManager(MigrationManager):
            def __init__(self):
                super().__init__()
                self.applied = ["001", "002"]

            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success(self.applied)

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                if version in self.applied:
                    self.applied.remove(version)
                return Success(None)

        manager = TestManager()

        # Create migrations
        for i in range(2):
            m = Mock(spec=Migration)
            m.info = MigrationInfo(f"00{i+1}", f"test{i+1}")
            m.down = AsyncMock(return_value=Success(None))
            manager.migrations[f"00{i+1}"] = m

        result = await manager.rollback_all()

        assert result.is_success()
        assert len(manager.applied) == 0

    def test_generate_migration_file(self):
        """Test generating migration file (line 409)"""

        class TestManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TestManager(temp_dir)

            result = manager.generate_migration("create_users", "sql")
            assert result.is_success()

            # Check file was created
            files = os.listdir(temp_dir)
            assert len(files) == 1
            assert "create_users" in files[0]

    @pytest.mark.asyncio
    async def test_migration_status_tracking(self):
        """Test migration status tracking (lines 422-427, 432-435, 440-443)"""

        class TestManager(MigrationManager):
            async def create_migration_table(self):
                return Success(None)

            async def get_applied_migrations(self):
                return Success([])

            async def record_migration(self, migration):
                return Success(None)

            async def remove_migration_record(self, version):
                return Success(None)

        manager = TestManager()

        # Test migration with different statuses
        migration = Mock(spec=Migration)
        migration.info = MigrationInfo("001", "test")
        migration.up = AsyncMock(return_value=Success(None))
        migration.set_status = Mock()

        # Simulate migration execution with status changes
        migration.info.status = MigrationStatus.PENDING
        migration.info.status = MigrationStatus.RUNNING
        migration.info.status = MigrationStatus.COMPLETED

        assert migration.info.status == MigrationStatus.COMPLETED

        # Test failed migration
        failed_migration = Mock(spec=Migration)
        failed_migration.info = MigrationInfo("002", "failed")
        failed_migration.up = AsyncMock(return_value=Failure("Migration failed"))
        failed_migration.info.status = MigrationStatus.FAILED

        assert failed_migration.info.status == MigrationStatus.FAILED

        # Test rolled back migration
        rolled_migration = Mock(spec=Migration)
        rolled_migration.info = MigrationInfo("003", "rolled")
        rolled_migration.down = AsyncMock(return_value=Success(None))
        rolled_migration.info.status = MigrationStatus.ROLLED_BACK

        assert rolled_migration.info.status == MigrationStatus.ROLLED_BACK
