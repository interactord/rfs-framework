"""
Unit tests for database base module
"""

import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

from rfs.core.result import Failure, Success
from rfs.database.base import (
    SQLALCHEMY_AVAILABLE,
    TORTOISE_AVAILABLE,
    ConnectionPool,
    Database,
    DatabaseConfig,
    DatabaseManager,
    DatabaseType,
    ORMType,
    SQLAlchemyDatabase,
    TortoiseDatabase,
    get_database,
    get_database_manager,
)


class TestDatabaseConfig:
    """Test DatabaseConfig class"""

    def test_default_config(self):
        """Test default configuration values"""
        config = DatabaseConfig(url="postgresql://localhost/test")

        assert config.url == "postgresql://localhost/test"
        assert config.database_type == DatabaseType.POSTGRESQL
        assert config.orm_type == ORMType.AUTO
        assert config.pool_size == 20
        assert config.max_overflow == 30
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
        assert config.pool_pre_ping is True
        assert config.auto_commit is False
        assert config.isolation_level == "READ_COMMITTED"
        assert config.echo is False
        assert config.echo_pool is False
        assert config.future is True

    def test_custom_config(self):
        """Test custom configuration values"""
        config = DatabaseConfig(
            url="mysql://localhost/test",
            database_type=DatabaseType.MYSQL,
            orm_type=ORMType.SQLALCHEMY,
            pool_size=50,
            echo=True,
        )

        assert config.url == "mysql://localhost/test"
        assert config.database_type == DatabaseType.MYSQL
        assert config.orm_type == ORMType.SQLALCHEMY
        assert config.pool_size == 50
        assert config.echo is True

    def test_cloud_sql_config(self):
        """Test Cloud SQL configuration"""
        config = DatabaseConfig(
            url="postgresql://localhost/test",
            database_type=DatabaseType.CLOUD_SQL,
            cloud_sql_instance="project:region:instance",
            cloud_sql_project="my-project",
            cloud_sql_region="us-central1",
        )

        assert config.database_type == DatabaseType.CLOUD_SQL
        assert config.cloud_sql_instance == "project:region:instance"
        assert config.cloud_sql_project == "my-project"
        assert config.cloud_sql_region == "us-central1"

    def test_get_sqlalchemy_url(self):
        """Test SQLAlchemy URL generation"""
        config = DatabaseConfig(url="postgresql://localhost/test")

        # Test normal URL
        assert config.get_sqlalchemy_url() == "postgresql://localhost/test"

        # Test async URL conversion
        config.url = "postgresql+asyncpg://localhost/test"
        assert config.get_sqlalchemy_url() == "postgresql+asyncpg://localhost/test"

    def test_get_tortoise_url(self):
        """Test Tortoise URL generation"""
        config = DatabaseConfig(url="postgresql://localhost/test")

        # Test normal URL
        assert config.get_tortoise_url() == "postgresql://localhost/test"

        # Test postgres URL conversion
        config.url = "postgres://localhost/test"
        assert config.get_tortoise_url() == "postgres://localhost/test"

    def test_extra_options(self):
        """Test extra options configuration"""
        extra = {"connect_timeout": 10, "server_side_cursors": True}
        config = DatabaseConfig(url="postgresql://localhost/test", extra_options=extra)

        assert config.extra_options == extra
        assert config.extra_options["connect_timeout"] == 10


class TestConnectionPool:
    """Test ConnectionPool class"""

    def test_pool_initialization(self):
        """Test connection pool initialization"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        pool = ConnectionPool(config)

        assert pool.config == config
        assert pool._connections == []
        assert pool._available == []
        assert pool._in_use == set()
        assert pool._lock is not None
        assert pool._closed is False

    @pytest.mark.asyncio
    async def test_acquire_connection(self):
        """Test acquiring connection from pool"""
        config = DatabaseConfig(url="postgresql://localhost/test", pool_size=2)
        pool = ConnectionPool(config)

        mock_conn = Mock()
        pool._create_connection = Mock(return_value=Success(mock_conn))

        # Acquire first connection
        result = await pool.acquire()
        assert result.is_success()
        assert result.unwrap() == mock_conn
        assert mock_conn in pool._in_use
        assert len(pool._connections) == 1

    @pytest.mark.asyncio
    async def test_release_connection(self):
        """Test releasing connection back to pool"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        pool = ConnectionPool(config)

        mock_conn = Mock()
        pool._connections.append(mock_conn)
        pool._in_use.add(mock_conn)

        # Release connection
        await pool.release(mock_conn)
        assert mock_conn not in pool._in_use
        assert mock_conn in pool._available

    @pytest.mark.asyncio
    async def test_pool_exhaustion(self):
        """Test pool exhaustion handling"""
        config = DatabaseConfig(
            url="postgresql://localhost/test",
            pool_size=1,
            max_overflow=0,
            pool_timeout=0.1,
        )
        pool = ConnectionPool(config)

        mock_conn = Mock()
        pool._create_connection = Mock(return_value=Success(mock_conn))

        # Acquire connection
        result1 = await pool.acquire()
        assert result1.is_success()

        # Try to acquire another (should timeout)
        result2 = await pool.acquire()
        assert result2.is_failure()
        assert "Connection pool exhausted" in str(result2.unwrap_err())

    @pytest.mark.asyncio
    async def test_close_pool(self):
        """Test closing connection pool"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        pool = ConnectionPool(config)

        mock_conn = Mock()
        mock_conn.close = AsyncMock()
        pool._connections.append(mock_conn)

        # Close pool
        await pool.close()
        assert pool._closed is True
        mock_conn.close.assert_called_once()
        assert len(pool._connections) == 0

    def test_pool_statistics(self):
        """Test pool statistics"""
        config = DatabaseConfig(url="postgresql://localhost/test", pool_size=10)
        pool = ConnectionPool(config)

        # Add some connections
        for _ in range(3):
            conn = Mock()
            pool._connections.append(conn)
            pool._available.append(conn)

        # Mark one as in use
        in_use_conn = pool._available.pop()
        pool._in_use.add(in_use_conn)

        stats = pool.get_statistics()
        assert stats["total_connections"] == 3
        assert stats["available_connections"] == 2
        assert stats["in_use_connections"] == 1
        assert stats["pool_size"] == 10
        assert stats["max_overflow"] == 30


class TestSQLAlchemyDatabase:
    """Test SQLAlchemy database implementation"""

    @pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not installed")
    def test_initialization(self):
        """Test SQLAlchemy database initialization"""
        config = DatabaseConfig(url="sqlite:///:memory:")
        db = SQLAlchemyDatabase(config)

        assert db.config == config
        assert db._engine is None
        assert db._session_factory is None
        assert db._metadata is not None

    @pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not installed")
    @pytest.mark.asyncio
    async def test_connect(self):
        """Test database connection"""
        config = DatabaseConfig(url="sqlite:///:memory:")
        db = SQLAlchemyDatabase(config)

        result = await db.connect()
        assert result.is_success()
        assert db._engine is not None
        assert db._session_factory is not None

        # Cleanup
        await db.disconnect()

    @pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not installed")
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test database disconnection"""
        config = DatabaseConfig(url="sqlite:///:memory:")
        db = SQLAlchemyDatabase(config)

        # Connect first
        await db.connect()
        assert db._engine is not None

        # Disconnect
        result = await db.disconnect()
        assert result.is_success()

    @pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not installed")
    @pytest.mark.asyncio
    async def test_execute_query(self):
        """Test query execution"""
        config = DatabaseConfig(url="sqlite:///:memory:")
        db = SQLAlchemyDatabase(config)

        await db.connect()

        # Create test table
        await db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        # Insert data
        result = await db.execute(
            "INSERT INTO test (name) VALUES (?)", params=["test_name"]
        )
        assert result.is_success()

        # Query data
        result = await db.execute("SELECT * FROM test")
        assert result.is_success()
        rows = result.unwrap()
        assert len(rows) == 1

        await db.disconnect()

    @pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not installed")
    def test_get_session(self):
        """Test session creation"""
        config = DatabaseConfig(url="sqlite:///:memory:")
        db = SQLAlchemyDatabase(config)

        with patch.object(db, "_session_factory") as mock_factory:
            mock_session = Mock()
            mock_factory.return_value = mock_session

            session = db.get_session()
            assert session == mock_session
            mock_factory.assert_called_once()


class TestTortoiseDatabase:
    """Test Tortoise ORM database implementation"""

    @pytest.mark.skipif(not TORTOISE_AVAILABLE, reason="Tortoise ORM not installed")
    def test_initialization(self):
        """Test Tortoise database initialization"""
        config = DatabaseConfig(url="sqlite://:memory:")
        db = TortoiseDatabase(config)

        assert db.config == config
        assert db._initialized is False

    @pytest.mark.skipif(not TORTOISE_AVAILABLE, reason="Tortoise ORM not installed")
    @pytest.mark.asyncio
    async def test_connect(self):
        """Test database connection"""
        config = DatabaseConfig(url="sqlite://:memory:")
        db = TortoiseDatabase(config)

        with patch("rfs.database.base.Tortoise") as mock_tortoise:
            mock_tortoise.init = AsyncMock(return_value=None)

            result = await db.connect()
            assert result.is_success()
            assert db._initialized is True
            mock_tortoise.init.assert_called_once()

    @pytest.mark.skipif(not TORTOISE_AVAILABLE, reason="Tortoise ORM not installed")
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test database disconnection"""
        config = DatabaseConfig(url="sqlite://:memory:")
        db = TortoiseDatabase(config)
        db._initialized = True

        with patch("rfs.database.base.Tortoise") as mock_tortoise:
            mock_tortoise.close_connections = AsyncMock()

            result = await db.disconnect()
            assert result.is_success()
            assert db._initialized is False
            mock_tortoise.close_connections.assert_called_once()


class TestDatabaseManager:
    """Test DatabaseManager singleton"""

    def test_singleton_pattern(self):
        """Test singleton pattern implementation"""
        manager1 = DatabaseManager()
        manager2 = DatabaseManager()

        assert manager1 is manager2

    def test_register_database(self):
        """Test database registration"""
        manager = DatabaseManager()
        manager.clear()  # Clear any existing databases

        config = DatabaseConfig(url="sqlite:///:memory:")
        mock_db = Mock(spec=Database)

        result = manager.register("test_db", mock_db)
        assert result.is_success()
        assert "test_db" in manager._databases

    def test_get_database(self):
        """Test getting registered database"""
        manager = DatabaseManager()
        manager.clear()

        mock_db = Mock(spec=Database)
        manager.register("test_db", mock_db)

        result = manager.get("test_db")
        assert result.is_success()
        assert result.unwrap() == mock_db

    def test_get_nonexistent_database(self):
        """Test getting non-existent database"""
        manager = DatabaseManager()
        manager.clear()

        result = manager.get("nonexistent")
        assert result.is_failure()
        assert "Database 'nonexistent' not found" in str(result.unwrap_err())

    def test_remove_database(self):
        """Test removing database"""
        manager = DatabaseManager()
        manager.clear()

        mock_db = Mock(spec=Database)
        manager.register("test_db", mock_db)

        result = manager.remove("test_db")
        assert result.is_success()
        assert "test_db" not in manager._databases

    def test_list_databases(self):
        """Test listing registered databases"""
        manager = DatabaseManager()
        manager.clear()

        mock_db1 = Mock(spec=Database)
        mock_db2 = Mock(spec=Database)

        manager.register("db1", mock_db1)
        manager.register("db2", mock_db2)

        databases = manager.list_databases()
        assert "db1" in databases
        assert "db2" in databases
        assert len(databases) == 2

    @pytest.mark.asyncio
    async def test_close_all(self):
        """Test closing all databases"""
        manager = DatabaseManager()
        manager.clear()

        mock_db1 = Mock(spec=Database)
        mock_db1.disconnect = AsyncMock(return_value=Success(None))
        mock_db2 = Mock(spec=Database)
        mock_db2.disconnect = AsyncMock(return_value=Success(None))

        manager.register("db1", mock_db1)
        manager.register("db2", mock_db2)

        result = await manager.close_all()
        assert result.is_success()
        mock_db1.disconnect.assert_called_once()
        mock_db2.disconnect.assert_called_once()


class TestDatabaseFactory:
    """Test database factory functions"""

    def test_get_database_sqlalchemy(self):
        """Test getting SQLAlchemy database"""
        config = DatabaseConfig(url="sqlite:///:memory:", orm_type=ORMType.SQLALCHEMY)

        with patch("rfs.database.base.SQLALCHEMY_AVAILABLE", True):
            result = get_database(config)
            assert result.is_success()
            db = result.unwrap()
            assert isinstance(db, Database)

    def test_get_database_tortoise(self):
        """Test getting Tortoise database"""
        config = DatabaseConfig(url="sqlite://:memory:", orm_type=ORMType.TORTOISE)

        with patch("rfs.database.base.TORTOISE_AVAILABLE", True):
            result = get_database(config)
            assert result.is_success()
            db = result.unwrap()
            assert isinstance(db, Database)

    def test_get_database_auto_selection(self):
        """Test automatic ORM selection"""
        config = DatabaseConfig(url="sqlite:///:memory:", orm_type=ORMType.AUTO)

        # Test with SQLAlchemy available
        with patch("rfs.database.base.SQLALCHEMY_AVAILABLE", True):
            with patch("rfs.database.base.TORTOISE_AVAILABLE", False):
                result = get_database(config)
                assert result.is_success()

    def test_get_database_no_orm_available(self):
        """Test when no ORM is available"""
        config = DatabaseConfig(url="sqlite:///:memory:", orm_type=ORMType.AUTO)

        with patch("rfs.database.base.SQLALCHEMY_AVAILABLE", False):
            with patch("rfs.database.base.TORTOISE_AVAILABLE", False):
                result = get_database(config)
                assert result.is_failure()
                assert "No ORM library available" in str(result.unwrap_err())

    def test_get_database_manager(self):
        """Test getting database manager singleton"""
        manager1 = get_database_manager()
        manager2 = get_database_manager()

        assert manager1 is manager2
        assert isinstance(manager1, DatabaseManager)


class TestDatabaseIntegration:
    """Integration tests for database components"""

    @pytest.mark.asyncio
    async def test_database_lifecycle(self):
        """Test complete database lifecycle"""
        config = DatabaseConfig(url="sqlite:///:memory:")

        # Get database
        db_result = get_database(config)
        assert db_result.is_success()
        db = db_result.unwrap()

        # Register with manager
        manager = get_database_manager()
        manager.register("test", db)

        # Connect
        connect_result = await db.connect()
        assert connect_result.is_success()

        # Use database
        if hasattr(db, "execute"):
            result = await db.execute("SELECT 1")
            assert result.is_success()

        # Disconnect
        disconnect_result = await db.disconnect()
        assert disconnect_result.is_success()

        # Remove from manager
        manager.remove("test")

    @pytest.mark.asyncio
    async def test_connection_pool_lifecycle(self):
        """Test connection pool lifecycle"""
        config = DatabaseConfig(
            url="postgresql://localhost/test", pool_size=5, max_overflow=2
        )

        pool = ConnectionPool(config)

        # Mock connection creation
        mock_conn = Mock()
        pool._create_connection = Mock(return_value=Success(mock_conn))

        # Acquire multiple connections
        connections = []
        for _ in range(3):
            result = await pool.acquire()
            assert result.is_success()
            connections.append(result.unwrap())

        # Check pool state
        stats = pool.get_statistics()
        assert stats["in_use_connections"] == 3
        assert stats["total_connections"] == 3

        # Release connections
        for conn in connections:
            await pool.release(conn)

        # Check pool state after release
        stats = pool.get_statistics()
        assert stats["in_use_connections"] == 0
        assert stats["available_connections"] == 3

        # Close pool
        await pool.close()
        assert pool._closed is True
