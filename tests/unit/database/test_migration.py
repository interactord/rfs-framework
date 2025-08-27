"""
Unit tests for database migration module
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

from rfs.core.result import Failure, Success
from rfs.database.migration import (
    AlembicMigrationManager,
    Migration,
    MigrationInfo,
    MigrationManager,
    MigrationStatus,
    PythonMigration,
    SQLMigration,
    create_migration,
    get_migration_manager,
    rollback_migration,
    run_migrations,
    set_migration_manager,
)


class TestMigrationStatus:
    """Test MigrationStatus enum"""

    def test_status_values(self):
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
            version="001", name="create_users_table", description="Create users table"
        )

        assert info.version == "001"
        assert info.name == "create_users_table"
        assert info.description == "Create users table"
        assert info.status == MigrationStatus.PENDING
        assert info.applied_at is None
        assert info.error is None

    def test_migration_info_with_status(self):
        """Test migration info with custom status"""
        applied_time = datetime.now()
        info = MigrationInfo(
            version="002",
            name="add_email_column",
            description="Add email column to users",
            status=MigrationStatus.COMPLETED,
            applied_at=applied_time,
        )

        assert info.status == MigrationStatus.COMPLETED
        assert info.applied_at == applied_time

    def test_migration_info_with_error(self):
        """Test migration info with error"""
        info = MigrationInfo(
            version="003",
            name="failed_migration",
            description="This migration failed",
            status=MigrationStatus.FAILED,
            error="Database connection error",
        )

        assert info.status == MigrationStatus.FAILED
        assert info.error == "Database connection error"

    def test_migration_info_to_dict(self):
        """Test migration info serialization"""
        info = MigrationInfo(
            version="004",
            name="test_migration",
            description="Test migration",
            status=MigrationStatus.COMPLETED,
            applied_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        dict_repr = info.to_dict()
        assert dict_repr["version"] == "004"
        assert dict_repr["name"] == "test_migration"
        assert dict_repr["status"] == "completed"
        assert dict_repr["applied_at"] == "2024-01-01T12:00:00"


class TestMigration:
    """Test Migration abstract class"""

    def test_abstract_class(self):
        """Test that abstract class cannot be instantiated"""
        with pytest.raises(TypeError):
            migration = Migration("001", "test")

    def test_concrete_implementation(self):
        """Test concrete migration implementation"""

        class ConcreteMigration(Migration):
            async def up(self, database):
                return Success(None)

            async def down(self, database):
                return Success(None)

            def validate(self):
                return Success(None)

        migration = ConcreteMigration("001", "test_migration")
        assert migration.version == "001"
        assert migration.name == "test_migration"
        assert migration.description == ""
        assert migration.checksum is None

    def test_migration_with_description(self):
        """Test migration with description"""

        class TestMigration(Migration):
            async def up(self, database):
                return Success(None)

            async def down(self, database):
                return Success(None)

            def validate(self):
                return Success(None)

        migration = TestMigration("002", "create_table", description="Create new table")
        assert migration.description == "Create new table"

    def test_migration_comparison(self):
        """Test migration version comparison"""

        class TestMigration(Migration):
            async def up(self, database):
                return Success(None)

            async def down(self, database):
                return Success(None)

            def validate(self):
                return Success(None)

        m1 = TestMigration("001", "first")
        m2 = TestMigration("002", "second")
        m3 = TestMigration("001", "duplicate")

        assert m1 < m2
        assert m2 > m1
        assert m1 == m3  # Same version


class TestSQLMigration:
    """Test SQLMigration class"""

    def test_sql_migration_creation(self):
        """Test creating SQL migration"""
        migration = SQLMigration(
            "001",
            "create_users",
            up_sql="CREATE TABLE users (id INT PRIMARY KEY)",
            down_sql="DROP TABLE users",
        )

        assert migration.version == "001"
        assert migration.up_sql == "CREATE TABLE users (id INT PRIMARY KEY)"
        assert migration.down_sql == "DROP TABLE users"

    def test_sql_migration_from_files(self):
        """Test loading SQL migration from files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            up_file = Path(tmpdir) / "001_up.sql"
            down_file = Path(tmpdir) / "001_down.sql"

            up_file.write_text("CREATE TABLE test (id INT)")
            down_file.write_text("DROP TABLE test")

            migration = SQLMigration.from_files(
                "001", "test_migration", up_file=str(up_file), down_file=str(down_file)
            )

            assert migration.up_sql == "CREATE TABLE test (id INT)"
            assert migration.down_sql == "DROP TABLE test"

    @pytest.mark.asyncio
    async def test_sql_migration_up(self):
        """Test executing SQL migration up"""
        migration = SQLMigration(
            "001", "create_table", up_sql="CREATE TABLE test (id INT)"
        )

        mock_db = Mock()
        mock_db.execute = AsyncMock(return_value=Success(None))

        result = await migration.up(mock_db)
        assert result.is_success()
        mock_db.execute.assert_called_with("CREATE TABLE test (id INT)")

    @pytest.mark.asyncio
    async def test_sql_migration_down(self):
        """Test executing SQL migration down"""
        migration = SQLMigration("001", "drop_table", down_sql="DROP TABLE test")

        mock_db = Mock()
        mock_db.execute = AsyncMock(return_value=Success(None))

        result = await migration.down(mock_db)
        assert result.is_success()
        mock_db.execute.assert_called_with("DROP TABLE test")

    def test_sql_migration_validation(self):
        """Test SQL migration validation"""
        # Valid migration
        valid = SQLMigration(
            "001",
            "valid",
            up_sql="CREATE TABLE test (id INT)",
            down_sql="DROP TABLE test",
        )
        assert valid.validate().is_success()

        # Invalid migration (no up SQL)
        invalid = SQLMigration("002", "invalid", up_sql="")
        result = invalid.validate()
        assert result.is_failure()
        assert "Up SQL is required" in str(result.unwrap_err())

    def test_sql_migration_multi_statement(self):
        """Test SQL migration with multiple statements"""
        migration = SQLMigration(
            "001",
            "multi_statement",
            up_sql="""
            CREATE TABLE users (id INT PRIMARY KEY);
            CREATE TABLE posts (id INT PRIMARY KEY, user_id INT);
            CREATE INDEX idx_user_id ON posts(user_id);
            """,
            down_sql="""
            DROP TABLE posts;
            DROP TABLE users;
            """,
        )

        statements = migration.get_up_statements()
        assert len(statements) == 3
        assert "CREATE TABLE users" in statements[0]
        assert "CREATE TABLE posts" in statements[1]
        assert "CREATE INDEX" in statements[2]


class TestPythonMigration:
    """Test PythonMigration class"""

    def test_python_migration_creation(self):
        """Test creating Python migration"""

        async def up_func(database):
            # Custom migration logic
            return Success(None)

        async def down_func(database):
            # Custom rollback logic
            return Success(None)

        migration = PythonMigration(
            "001", "custom_migration", up_func=up_func, down_func=down_func
        )

        assert migration.version == "001"
        assert migration.up_func == up_func
        assert migration.down_func == down_func

    @pytest.mark.asyncio
    async def test_python_migration_up(self):
        """Test executing Python migration up"""
        mock_db = Mock()

        async def up_func(database):
            assert database == mock_db
            return Success("Migration completed")

        migration = PythonMigration("001", "python_up", up_func=up_func)

        result = await migration.up(mock_db)
        assert result.is_success()
        assert result.unwrap() == "Migration completed"

    @pytest.mark.asyncio
    async def test_python_migration_down(self):
        """Test executing Python migration down"""
        mock_db = Mock()

        async def down_func(database):
            assert database == mock_db
            return Success("Rollback completed")

        migration = PythonMigration("001", "python_down", down_func=down_func)

        result = await migration.down(mock_db)
        assert result.is_success()
        assert result.unwrap() == "Rollback completed"

    @pytest.mark.asyncio
    async def test_python_migration_with_error(self):
        """Test Python migration with error"""

        async def failing_up(database):
            return Failure("Migration failed")

        migration = PythonMigration("001", "failing", up_func=failing_up)

        mock_db = Mock()
        result = await migration.up(mock_db)
        assert result.is_failure()
        assert "Migration failed" in str(result.unwrap_err())

    def test_python_migration_validation(self):
        """Test Python migration validation"""

        # Valid migration
        async def up_func(db):
            pass

        async def down_func(db):
            pass

        valid = PythonMigration("001", "valid", up_func=up_func, down_func=down_func)
        assert valid.validate().is_success()

        # Invalid migration (no up function)
        invalid = PythonMigration("002", "invalid", up_func=None)
        result = invalid.validate()
        assert result.is_failure()
        assert "Up function is required" in str(result.unwrap_err())


class TestMigrationManager:
    """Test MigrationManager class"""

    @pytest.fixture
    def manager(self):
        """Create migration manager instance"""
        mock_db = Mock()
        return MigrationManager(mock_db)

    def test_manager_initialization(self, manager):
        """Test migration manager initialization"""
        assert manager._database is not None
        assert manager._migrations == []
        assert manager._history == []
        assert manager._lock is not None

    def test_add_migration(self, manager):
        """Test adding migration"""
        migration = SQLMigration("001", "test", up_sql="CREATE TABLE test (id INT)")

        result = manager.add_migration(migration)
        assert result.is_success()
        assert migration in manager._migrations
        assert len(manager._migrations) == 1

    def test_add_duplicate_migration(self, manager):
        """Test adding duplicate migration version"""
        m1 = SQLMigration("001", "first", up_sql="SQL1")
        m2 = SQLMigration("001", "second", up_sql="SQL2")

        manager.add_migration(m1)
        result = manager.add_migration(m2)
        assert result.is_failure()
        assert "already exists" in str(result.unwrap_err())

    def test_get_migration(self, manager):
        """Test getting migration by version"""
        migration = SQLMigration("001", "test", up_sql="SQL")
        manager.add_migration(migration)

        result = manager.get_migration("001")
        assert result.is_success()
        assert result.unwrap() == migration

    def test_get_nonexistent_migration(self, manager):
        """Test getting non-existent migration"""
        result = manager.get_migration("999")
        assert result.is_failure()
        assert "not found" in str(result.unwrap_err())

    def test_list_migrations(self, manager):
        """Test listing migrations"""
        m1 = SQLMigration("001", "first", up_sql="SQL1")
        m2 = SQLMigration("002", "second", up_sql="SQL2")

        manager.add_migration(m1)
        manager.add_migration(m2)

        migrations = manager.list_migrations()
        assert len(migrations) == 2
        assert migrations[0].version == "001"
        assert migrations[1].version == "002"

    def test_get_pending_migrations(self, manager):
        """Test getting pending migrations"""
        m1 = SQLMigration("001", "first", up_sql="SQL1")
        m2 = SQLMigration("002", "second", up_sql="SQL2")

        manager.add_migration(m1)
        manager.add_migration(m2)

        # Mark first as completed
        manager._history.append(
            MigrationInfo(version="001", name="first", status=MigrationStatus.COMPLETED)
        )

        pending = manager.get_pending_migrations()
        assert len(pending) == 1
        assert pending[0].version == "002"

    @pytest.mark.asyncio
    async def test_run_migration(self, manager):
        """Test running single migration"""
        migration = SQLMigration("001", "test", up_sql="CREATE TABLE test (id INT)")

        manager._database.execute = AsyncMock(return_value=Success(None))
        manager.add_migration(migration)

        result = await manager.run_migration("001")
        assert result.is_success()

        # Check history
        assert len(manager._history) == 1
        assert manager._history[0].version == "001"
        assert manager._history[0].status == MigrationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_migration_with_error(self, manager):
        """Test running migration that fails"""
        migration = SQLMigration("001", "failing", up_sql="INVALID SQL")

        manager._database.execute = AsyncMock(return_value=Failure("SQL syntax error"))
        manager.add_migration(migration)

        result = await manager.run_migration("001")
        assert result.is_failure()

        # Check history
        assert len(manager._history) == 1
        assert manager._history[0].status == MigrationStatus.FAILED
        assert "SQL syntax error" in manager._history[0].error

    @pytest.mark.asyncio
    async def test_run_all_migrations(self, manager):
        """Test running all pending migrations"""
        m1 = SQLMigration("001", "first", up_sql="SQL1")
        m2 = SQLMigration("002", "second", up_sql="SQL2")
        m3 = SQLMigration("003", "third", up_sql="SQL3")

        manager.add_migration(m1)
        manager.add_migration(m2)
        manager.add_migration(m3)

        manager._database.execute = AsyncMock(return_value=Success(None))

        result = await manager.run_all()
        assert result.is_success()
        assert result.unwrap() == 3  # Number of migrations run

        # All should be in history
        assert len(manager._history) == 3
        assert all(h.status == MigrationStatus.COMPLETED for h in manager._history)

    @pytest.mark.asyncio
    async def test_rollback_migration(self, manager):
        """Test rolling back migration"""
        migration = SQLMigration(
            "001",
            "test",
            up_sql="CREATE TABLE test (id INT)",
            down_sql="DROP TABLE test",
        )

        manager._database.execute = AsyncMock(return_value=Success(None))
        manager.add_migration(migration)

        # Run migration first
        await manager.run_migration("001")

        # Then rollback
        result = await manager.rollback_migration("001")
        assert result.is_success()

        # Check history
        history = [h for h in manager._history if h.version == "001"]
        assert any(h.status == MigrationStatus.ROLLED_BACK for h in history)

    @pytest.mark.asyncio
    async def test_rollback_to_version(self, manager):
        """Test rolling back to specific version"""
        m1 = SQLMigration("001", "first", up_sql="SQL1", down_sql="DOWN1")
        m2 = SQLMigration("002", "second", up_sql="SQL2", down_sql="DOWN2")
        m3 = SQLMigration("003", "third", up_sql="SQL3", down_sql="DOWN3")

        for m in [m1, m2, m3]:
            manager.add_migration(m)

        manager._database.execute = AsyncMock(return_value=Success(None))

        # Run all migrations
        await manager.run_all()

        # Rollback to version 001 (should rollback 003 and 002)
        result = await manager.rollback_to("001")
        assert result.is_success()
        assert result.unwrap() == 2  # Number of migrations rolled back

    def test_get_migration_history(self, manager):
        """Test getting migration history"""
        # Add some history
        manager._history.extend(
            [
                MigrationInfo("001", "first", status=MigrationStatus.COMPLETED),
                MigrationInfo("002", "second", status=MigrationStatus.FAILED),
                MigrationInfo("003", "third", status=MigrationStatus.ROLLED_BACK),
            ]
        )

        history = manager.get_history()
        assert len(history) == 3
        assert history[0].version == "001"
        assert history[1].status == MigrationStatus.FAILED
        assert history[2].status == MigrationStatus.ROLLED_BACK

    def test_clear_history(self, manager):
        """Test clearing migration history"""
        manager._history.extend(
            [MigrationInfo("001", "first"), MigrationInfo("002", "second")]
        )

        manager.clear_history()
        assert len(manager._history) == 0


class TestAlembicMigrationManager:
    """Test Alembic migration manager"""

    @pytest.mark.skipif(
        not pytest.importorskip("alembic", reason="Alembic not installed"),
        reason="Alembic not installed",
    )
    def test_alembic_manager_initialization(self):
        """Test Alembic manager initialization"""
        mock_db = Mock()
        manager = AlembicMigrationManager(mock_db, config_path="alembic.ini")

        assert manager._database == mock_db
        assert manager._config_path == "alembic.ini"
        assert manager._alembic_cfg is None

    @pytest.mark.skipif(
        not pytest.importorskip("alembic", reason="Alembic not installed"),
        reason="Alembic not installed",
    )
    def test_alembic_init(self):
        """Test initializing Alembic"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_db = Mock()
            config_path = os.path.join(tmpdir, "alembic.ini")

            manager = AlembicMigrationManager(mock_db, config_path=config_path)

            with patch("alembic.command.init") as mock_init:
                result = manager.init(tmpdir)
                assert result.is_success()
                mock_init.assert_called_once()


class TestMigrationFactoryFunctions:
    """Test migration factory functions"""

    def test_create_migration_sql(self):
        """Test creating SQL migration"""
        result = create_migration(
            "001",
            "create_table",
            migration_type="sql",
            up_sql="CREATE TABLE test (id INT)",
            down_sql="DROP TABLE test",
        )

        assert result.is_success()
        migration = result.unwrap()
        assert isinstance(migration, SQLMigration)
        assert migration.version == "001"
        assert migration.up_sql == "CREATE TABLE test (id INT)"

    def test_create_migration_python(self):
        """Test creating Python migration"""

        async def up(db):
            return Success(None)

        async def down(db):
            return Success(None)

        result = create_migration(
            "002", "custom", migration_type="python", up_func=up, down_func=down
        )

        assert result.is_success()
        migration = result.unwrap()
        assert isinstance(migration, PythonMigration)
        assert migration.up_func == up

    def test_create_migration_invalid_type(self):
        """Test creating migration with invalid type"""
        result = create_migration("003", "invalid", migration_type="invalid")

        assert result.is_failure()
        assert "Invalid migration type" in str(result.unwrap_err())

    @pytest.mark.asyncio
    async def test_run_migrations_function(self):
        """Test run_migrations helper function"""
        mock_manager = Mock(spec=MigrationManager)
        mock_manager.run_all = AsyncMock(return_value=Success(2))

        with patch("rfs.database.migration._migration_manager", mock_manager):
            result = await run_migrations()
            assert result.is_success()
            assert result.unwrap() == 2
            mock_manager.run_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_migration_function(self):
        """Test rollback_migration helper function"""
        mock_manager = Mock(spec=MigrationManager)
        mock_manager.rollback_migration = AsyncMock(return_value=Success(None))

        with patch("rfs.database.migration._migration_manager", mock_manager):
            result = await rollback_migration("001")
            assert result.is_success()
            mock_manager.rollback_migration.assert_called_with("001")

    def test_get_migration_manager(self):
        """Test getting migration manager"""
        mock_db = Mock()

        # Set manager
        manager = MigrationManager(mock_db)
        set_migration_manager(manager)

        # Get manager
        retrieved = get_migration_manager()
        assert retrieved == manager

    def test_get_migration_manager_not_set(self):
        """Test getting manager when not set"""
        with patch("rfs.database.migration._migration_manager", None):
            result = get_migration_manager()
            assert result is None
