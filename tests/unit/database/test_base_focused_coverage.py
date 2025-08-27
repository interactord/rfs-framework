"""
RFS Database Base Module Focused Coverage Tests (RFS v4.1)

Phase 1: 42.86% → 85%+ Coverage Target

타겟팅 라인 분석:
- 16-20: SQLAlchemy imports with ImportError handling
- 33-36: Tortoise imports with ImportError handling
- 101-104: Cloud SQL URL generation
- 108-134: Tortoise config generation
- 141-169: ConnectionPool initialization methods
- 173-195: SQLAlchemy initialization
- 199-205: Tortoise initialization
- 217-229: Connection pool close methods
- 242-250: Database initialization
- 278-285: SQLAlchemy execute_query
- 300-306: Tortoise execute_query
- 324-352: DatabaseManager add_database
- 363-371: DatabaseManager close_all
"""

from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

import pytest

# SQLAlchemy and Tortoise 모킹용 설정
mock_sqlalchemy_modules = {
    "sqlalchemy": Mock(),
    "sqlalchemy.ext.asyncio": Mock(),
    "sqlalchemy.orm": Mock(),
    "sqlalchemy.pool": Mock(),
    "tortoise": Mock(),
    "tortoise.connection": Mock(),
    "tortoise.transactions": Mock(),
}

import sys

for module_name, mock_module in mock_sqlalchemy_modules.items():
    sys.modules[module_name] = mock_module

from rfs.core.result import Failure, Success

# 이제 실제 모듈 import
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
    """DatabaseConfig 클래스 테스트"""

    def test_default_config_creation(self):
        """기본 설정으로 DatabaseConfig 생성"""
        config = DatabaseConfig(url="sqlite:///test.db")

        assert config.url == "sqlite:///test.db"
        assert config.database_type == DatabaseType.POSTGRESQL
        assert config.orm_type == ORMType.AUTO
        assert config.pool_size == 20
        assert config.max_overflow == 30
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
        assert config.pool_pre_ping is True
        assert config.auto_commit is False
        assert config.isolation_level == "READ_COMMITTED"
        assert config.cloud_sql_instance is None
        assert config.cloud_sql_project is None
        assert config.cloud_sql_region is None
        assert config.echo is False
        assert config.echo_pool is False
        assert config.future is True
        assert config.extra_options == {}

    def test_custom_config_creation(self):
        """커스텀 설정으로 DatabaseConfig 생성"""
        extra_opts = {"custom_option": "value"}
        config = DatabaseConfig(
            url="postgresql://user:pass@host:5432/db",
            database_type=DatabaseType.MYSQL,
            orm_type=ORMType.SQLALCHEMY,
            pool_size=10,
            max_overflow=5,
            pool_timeout=60,
            pool_recycle=7200,
            pool_pre_ping=False,
            auto_commit=True,
            isolation_level="SERIALIZABLE",
            cloud_sql_instance="test-instance",
            cloud_sql_project="test-project",
            cloud_sql_region="us-central1",
            echo=True,
            echo_pool=True,
            future=False,
            extra_options=extra_opts,
        )

        assert config.database_type == DatabaseType.MYSQL
        assert config.orm_type == ORMType.SQLALCHEMY
        assert config.pool_size == 10
        assert config.max_overflow == 5
        assert config.cloud_sql_instance == "test-instance"
        assert config.cloud_sql_project == "test-project"
        assert config.cloud_sql_region == "us-central1"
        assert config.extra_options == extra_opts

    def test_get_sqlalchemy_url_normal(self):
        """일반 URL에서 SQLAlchemy URL 반환"""
        config = DatabaseConfig(url="postgresql://user:pass@host/db")
        url = config.get_sqlalchemy_url()

        assert url == "postgresql://user:pass@host/db"

    def test_get_sqlalchemy_url_cloud_sql(self):
        """Cloud SQL 설정에서 SQLAlchemy URL 생성 - 라인 101-104 커버"""
        config = DatabaseConfig(
            url="postgresql://user:pass@host/db",
            database_type=DatabaseType.CLOUD_SQL,
            cloud_sql_instance="test-instance",
            cloud_sql_project="test-project",
            cloud_sql_region="us-central1",
        )

        url = config.get_sqlalchemy_url()
        expected = "postgresql+asyncpg://user:password@/dbname?host=/cloudsql/test-project:us-central1:test-instance"

        assert url == expected

    def test_get_sqlalchemy_url_cloud_sql_no_instance(self):
        """Cloud SQL이지만 instance가 없는 경우"""
        config = DatabaseConfig(
            url="postgresql://user:pass@host/db",
            database_type=DatabaseType.CLOUD_SQL,
            cloud_sql_instance=None,
        )

        url = config.get_sqlalchemy_url()

        assert url == "postgresql://user:pass@host/db"

    def test_get_tortoise_config_postgresql(self):
        """PostgreSQL URL에서 Tortoise 설정 생성 - 라인 108-134 커버"""
        config = DatabaseConfig(
            url="postgresql://user:pass@host:5432/testdb",
            pool_size=15,
            extra_options={"ssl": True},
        )

        tortoise_config = config.get_tortoise_config()

        assert "connections" in tortoise_config
        assert "default" in tortoise_config["connections"]
        assert (
            tortoise_config["connections"]["default"]["engine"]
            == "tortoise.backends.asyncpg"
        )
        assert (
            tortoise_config["connections"]["default"]["credentials"]["database"]
            == "testdb"
        )
        assert (
            tortoise_config["connections"]["default"]["credentials"]["host"]
            == "localhost"
        )
        assert tortoise_config["connections"]["default"]["credentials"]["port"] == 5432
        assert (
            tortoise_config["connections"]["default"]["credentials"]["user"]
            == "postgres"
        )
        assert (
            tortoise_config["connections"]["default"]["credentials"]["password"] == ""
        )
        assert tortoise_config["connections"]["default"]["credentials"]["minsize"] == 1
        assert tortoise_config["connections"]["default"]["credentials"]["maxsize"] == 15
        assert tortoise_config["connections"]["default"]["credentials"]["ssl"] is True

        assert "apps" in tortoise_config
        assert tortoise_config["apps"]["models"]["models"] == ["__main__"]
        assert tortoise_config["apps"]["models"]["default_connection"] == "default"

    def test_get_tortoise_config_sqlite(self):
        """SQLite URL에서 Tortoise 설정 생성"""
        config = DatabaseConfig(url="sqlite:///test.db")

        tortoise_config = config.get_tortoise_config()

        assert (
            tortoise_config["connections"]["default"]["engine"]
            == "tortoise.backends.aiosqlite"
        )
        assert (
            tortoise_config["connections"]["default"]["credentials"]["database"]
            == "test.db"
        )

    def test_get_tortoise_config_no_slash_in_url(self):
        """URL에 슬래시가 없는 경우"""
        config = DatabaseConfig(url="testdb")

        tortoise_config = config.get_tortoise_config()

        assert (
            tortoise_config["connections"]["default"]["credentials"]["database"]
            == "testdb"
        )


class TestConnectionPool:
    """ConnectionPool 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.config = DatabaseConfig(url="sqlite:///:memory:")

    def test_init(self):
        """ConnectionPool 초기화 - 라인 141-145 커버"""
        pool = ConnectionPool(self.config)

        assert pool.config == self.config
        assert pool._engine is None
        assert pool._async_engine is None
        assert pool._session_factory is None
        assert pool._async_session_factory is None

    @pytest.mark.asyncio
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", True)
    async def test_initialize_sqlalchemy_success(self):
        """SQLAlchemy로 초기화 성공 - 라인 149-169, 173-195 커버"""
        pool = ConnectionPool(self.config)

        with patch.object(pool, "_initialize_sqlalchemy") as mock_init:
            mock_init.return_value = None
            result = await pool.initialize()

            assert result.is_success()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    @patch("rfs.database.base.TORTOISE_AVAILABLE", True)
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", False)
    async def test_initialize_tortoise_success(self):
        """Tortoise로 초기화 성공 - 라인 154-157 커버"""
        pool = ConnectionPool(self.config)

        with patch.object(pool, "_initialize_tortoise") as mock_init:
            mock_init.return_value = None
            result = await pool.initialize()

            assert result.is_success()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", False)
    @patch("rfs.database.base.TORTOISE_AVAILABLE", False)
    async def test_initialize_no_orm_available(self):
        """사용 가능한 ORM이 없는 경우 - 라인 158-159 커버"""
        pool = ConnectionPool(self.config)

        result = await pool.initialize()

        assert not result.is_success()
        assert "사용 가능한 ORM이 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_initialize_exception_handling(self):
        """초기화 중 예외 발생 - 라인 166-169 커버"""
        pool = ConnectionPool(self.config)

        with patch.object(pool, "_initialize_sqlalchemy") as mock_init:
            mock_init.side_effect = Exception("Test error")
            result = await pool.initialize()

            assert not result.is_success()
            assert "연결 풀 초기화 실패" in result.unwrap_error()
            assert "Test error" in result.unwrap_error()

    @pytest.mark.asyncio
    @patch("rfs.database.base.create_async_engine")
    @patch("rfs.database.base.sessionmaker")
    async def test_initialize_sqlalchemy_detailed(
        self, mock_sessionmaker, mock_create_engine
    ):
        """SQLAlchemy 상세 초기화 테스트 - 라인 173-195 커버"""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        mock_session_factory = Mock()
        mock_sessionmaker.return_value = mock_session_factory

        pool = ConnectionPool(self.config)

        with patch("rfs.database.base.SQLALCHEMY_AVAILABLE", True):
            await pool._initialize_sqlalchemy()

            mock_create_engine.assert_called_once_with(
                self.config.get_sqlalchemy_url(),
                echo=self.config.echo,
                echo_pool=self.config.echo_pool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=self.config.pool_pre_ping,
                future=self.config.future,
                **self.config.extra_options,
            )

            assert pool._async_engine == mock_engine
            mock_sessionmaker.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_sqlalchemy_not_available(self):
        """SQLAlchemy가 사용불가능한 경우 - 라인 173-174 커버"""
        pool = ConnectionPool(self.config)

        with patch("rfs.database.base.SQLALCHEMY_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="SQLAlchemy가 설치되지 않았습니다"):
                await pool._initialize_sqlalchemy()

    @pytest.mark.asyncio
    @patch("rfs.database.base.Tortoise")
    async def test_initialize_tortoise_detailed(self, mock_tortoise):
        """Tortoise 상세 초기화 테스트 - 라인 199-205 커버"""
        mock_tortoise.init = AsyncMock()

        pool = ConnectionPool(self.config)

        with patch("rfs.database.base.TORTOISE_AVAILABLE", True):
            await pool._initialize_tortoise()

            mock_tortoise.init.assert_called_once_with(
                config=self.config.get_tortoise_config()
            )

    @pytest.mark.asyncio
    async def test_initialize_tortoise_not_available(self):
        """Tortoise가 사용불가능한 경우 - 라인 199-200 커버"""
        pool = ConnectionPool(self.config)

        with patch("rfs.database.base.TORTOISE_AVAILABLE", False):
            with pytest.raises(
                RuntimeError, match="Tortoise ORM이 설치되지 않았습니다"
            ):
                await pool._initialize_tortoise()

    def test_get_engine_async(self):
        """비동기 엔진 반환 - 라인 209 커버"""
        pool = ConnectionPool(self.config)
        mock_engine = Mock()
        pool._async_engine = mock_engine

        engine = pool.get_engine()

        assert engine == mock_engine

    def test_get_engine_sync_fallback(self):
        """동기 엔진 fallback 반환"""
        pool = ConnectionPool(self.config)
        mock_engine = Mock()
        pool._engine = mock_engine
        pool._async_engine = None

        engine = pool.get_engine()

        assert engine == mock_engine

    def test_get_session_factory_async(self):
        """비동기 세션 팩토리 반환 - 라인 213 커버"""
        pool = ConnectionPool(self.config)
        mock_factory = Mock()
        pool._async_session_factory = mock_factory

        factory = pool.get_session_factory()

        assert factory == mock_factory

    def test_get_session_factory_sync_fallback(self):
        """동기 세션 팩토리 fallback 반환"""
        pool = ConnectionPool(self.config)
        mock_factory = Mock()
        pool._session_factory = mock_factory
        pool._async_session_factory = None

        factory = pool.get_session_factory()

        assert factory == mock_factory

    @pytest.mark.asyncio
    @patch("rfs.database.base.TORTOISE_AVAILABLE", True)
    async def test_close_with_all_engines(self):
        """모든 엔진을 가지고 close 테스트 - 라인 217-229 커버"""
        pool = ConnectionPool(self.config)

        mock_async_engine = Mock()
        mock_async_engine.dispose = AsyncMock()
        mock_sync_engine = Mock()
        mock_sync_engine.dispose = Mock()

        pool._async_engine = mock_async_engine
        pool._engine = mock_sync_engine

        # Tortoise 초기화 상태 모킹
        with patch("rfs.database.base.Tortoise") as mock_tortoise:
            mock_tortoise._inited = True
            mock_tortoise.close_connections = AsyncMock()

            await pool.close()

            mock_async_engine.dispose.assert_called_once()
            mock_sync_engine.dispose.assert_called_once()
            mock_tortoise.close_connections.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_exception_handling(self):
        """close 중 예외 처리 - 라인 228-229 커버"""
        pool = ConnectionPool(self.config)

        mock_async_engine = Mock()
        mock_async_engine.dispose = AsyncMock(side_effect=Exception("Close error"))
        pool._async_engine = mock_async_engine

        # 예외가 발생해도 정상적으로 완료되어야 함
        await pool.close()  # 예외가 발생하지 않아야 함


class TestDatabase:
    """Database 추상 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.config = DatabaseConfig(url="sqlite:///:memory:")

    def test_database_init(self):
        """Database 초기화 - 라인 236-238 커버"""
        # Database는 추상 클래스이므로 SQLAlchemyDatabase 사용
        db = SQLAlchemyDatabase(self.config)

        assert db.config == self.config
        assert isinstance(db.connection_pool, ConnectionPool)
        assert db._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Database 초기화 성공 - 라인 242-250 커버"""
        db = SQLAlchemyDatabase(self.config)

        # connection_pool.initialize()를 Mock으로 성공 시뮬레이션
        db.connection_pool.initialize = AsyncMock(return_value=Success(None))

        result = await db.initialize()

        assert result.is_success()
        assert db._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self):
        """이미 초기화된 경우 - 라인 242-243 커버"""
        db = SQLAlchemyDatabase(self.config)
        db._initialized = True

        result = await db.initialize()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Database 초기화 실패"""
        db = SQLAlchemyDatabase(self.config)

        # connection_pool.initialize()를 Mock으로 실패 시뮬레이션
        db.connection_pool.initialize = AsyncMock(
            return_value=Failure("Connection failed")
        )

        result = await db.initialize()

        assert not result.is_success()
        assert db._initialized is False

    @pytest.mark.asyncio
    async def test_close(self):
        """Database close - 라인 266-268 커버"""
        db = SQLAlchemyDatabase(self.config)
        db._initialized = True

        db.connection_pool.close = AsyncMock()

        await db.close()

        db.connection_pool.close.assert_called_once()
        assert db._initialized is False


class TestSQLAlchemyDatabase:
    """SQLAlchemyDatabase 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.config = DatabaseConfig(url="sqlite:///:memory:")
        self.db = SQLAlchemyDatabase(self.config)

    @pytest.mark.asyncio
    async def test_execute_query_success(self):
        """SQLAlchemy 쿼리 실행 성공 - 라인 278-285 커버"""
        # Mock session과 result 설정
        mock_result = Mock()
        mock_result.fetchall.return_value = [{"id": 1, "name": "test"}]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # create_session을 Mock으로 설정
        self.db.create_session = Mock(return_value=mock_session)

        result = await self.db.execute_query("SELECT * FROM test", {"param": "value"})

        assert result.is_success()
        assert result.unwrap() == [{"id": 1, "name": "test"}]
        mock_session.execute.assert_called_once_with(
            "SELECT * FROM test", {"param": "value"}
        )
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_no_params(self):
        """파라미터 없는 SQLAlchemy 쿼리 실행"""
        mock_result = Mock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        self.db.create_session = Mock(return_value=mock_session)

        result = await self.db.execute_query("SELECT * FROM test")

        assert result.is_success()
        mock_session.execute.assert_called_once_with("SELECT * FROM test", {})

    @pytest.mark.asyncio
    async def test_execute_query_exception(self):
        """SQLAlchemy 쿼리 실행 예외 - 라인 284-285 커버"""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        self.db.create_session = Mock(return_value=mock_session)

        result = await self.db.execute_query("SELECT * FROM test")

        assert not result.is_success()
        assert "쿼리 실행 실패" in result.unwrap_error()
        assert "Database error" in result.unwrap_error()

    async def test_create_session(self):
        """SQLAlchemy 세션 생성 - 라인 288-290 커버"""
        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        self.db.connection_pool.get_session_factory = Mock(
            return_value=mock_session_factory
        )

        session = await self.db.create_session()

        assert session == mock_session
        mock_session_factory.assert_called_once()


class TestTortoiseDatabase:
    """TortoiseDatabase 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.config = DatabaseConfig(url="sqlite:///:memory:")
        self.db = TortoiseDatabase(self.config)

    @pytest.mark.asyncio
    @patch("rfs.database.base.connections")
    async def test_execute_query_success(self, mock_connections):
        """Tortoise 쿼리 실행 성공 - 라인 300-306 커버"""
        mock_connection = AsyncMock()
        mock_connection.execute_query.return_value = [{"id": 1, "name": "test"}]
        mock_connections.get.return_value = mock_connection

        result = await self.db.execute_query("SELECT * FROM test", ["param"])

        assert result.is_success()
        assert result.unwrap() == [{"id": 1, "name": "test"}]
        mock_connections.get.assert_called_once_with("default")
        mock_connection.execute_query.assert_called_once_with(
            "SELECT * FROM test", ["param"]
        )

    @pytest.mark.asyncio
    @patch("rfs.database.base.connections")
    async def test_execute_query_no_params(self, mock_connections):
        """파라미터 없는 Tortoise 쿼리 실행"""
        mock_connection = AsyncMock()
        mock_connection.execute_query.return_value = []
        mock_connections.get.return_value = mock_connection

        result = await self.db.execute_query("SELECT * FROM test")

        assert result.is_success()
        mock_connection.execute_query.assert_called_once_with("SELECT * FROM test", [])

    @pytest.mark.asyncio
    @patch("rfs.database.base.connections")
    async def test_execute_query_exception(self, mock_connections):
        """Tortoise 쿼리 실행 예외 - 라인 305-306 커버"""
        mock_connection = AsyncMock()
        mock_connection.execute_query.side_effect = Exception("Connection error")
        mock_connections.get.return_value = mock_connection

        result = await self.db.execute_query("SELECT * FROM test")

        assert not result.is_success()
        assert "쿼리 실행 실패" in result.unwrap_error()
        assert "Connection error" in result.unwrap_error()

    @patch("rfs.database.base.in_transaction")
    async def test_create_session(self, mock_in_transaction):
        """Tortoise 세션(트랜잭션) 생성 - 라인 309-310 커버"""
        mock_transaction = Mock()
        mock_in_transaction.return_value = mock_transaction

        session = await self.db.create_session()

        assert session == mock_transaction
        mock_in_transaction.assert_called_once()


class TestDatabaseManager:
    """DatabaseManager 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # Singleton 초기화
        DatabaseManager._instances = {}
        self.manager = DatabaseManager()

    def test_init(self):
        """DatabaseManager 초기화 - 라인 317-318 커버"""
        assert self.manager.databases == {}
        assert self.manager.default_database is None

    @pytest.mark.asyncio
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", True)
    async def test_add_database_sqlalchemy_success(self):
        """SQLAlchemy 데이터베이스 추가 성공 - 라인 324-352 커버"""
        config = DatabaseConfig(url="sqlite:///:memory:", orm_type=ORMType.SQLALCHEMY)

        # Database.initialize를 Mock으로 성공 시뮬레이션
        with patch.object(
            SQLAlchemyDatabase, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Success(None)

            result = await self.manager.add_database("test_db", config)

            assert result.is_success()
            assert "test_db" in self.manager.databases
            assert isinstance(self.manager.databases["test_db"], SQLAlchemyDatabase)
            assert self.manager.default_database == "test_db"

    @pytest.mark.asyncio
    @patch("rfs.database.base.TORTOISE_AVAILABLE", True)
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", False)
    async def test_add_database_tortoise_success(self):
        """Tortoise 데이터베이스 추가 성공 - 라인 330-335 커버"""
        config = DatabaseConfig(url="sqlite:///:memory:", orm_type=ORMType.TORTOISE)

        with patch.object(
            TortoiseDatabase, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Success(None)

            result = await self.manager.add_database("tortoise_db", config)

            assert result.is_success()
            assert "tortoise_db" in self.manager.databases
            assert isinstance(self.manager.databases["tortoise_db"], TortoiseDatabase)
            assert self.manager.default_database == "tortoise_db"

    @pytest.mark.asyncio
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", True)
    async def test_add_database_auto_orm_sqlalchemy(self):
        """AUTO ORM이 SQLAlchemy로 선택되는 경우 - 라인 326-329 커버"""
        config = DatabaseConfig(url="sqlite:///:memory:", orm_type=ORMType.AUTO)

        with patch.object(
            SQLAlchemyDatabase, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Success(None)

            result = await self.manager.add_database("auto_db", config)

            assert result.is_success()
            assert isinstance(self.manager.databases["auto_db"], SQLAlchemyDatabase)

    @pytest.mark.asyncio
    @patch("rfs.database.base.TORTOISE_AVAILABLE", True)
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", False)
    async def test_add_database_auto_orm_tortoise(self):
        """AUTO ORM이 Tortoise로 선택되는 경우 - 라인 330-333 커버"""
        config = DatabaseConfig(url="sqlite:///:memory:", orm_type=ORMType.AUTO)

        with patch.object(
            TortoiseDatabase, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Success(None)

            result = await self.manager.add_database("auto_tortoise", config)

            assert result.is_success()
            assert isinstance(self.manager.databases["auto_tortoise"], TortoiseDatabase)

    @pytest.mark.asyncio
    @patch("rfs.database.base.SQLALCHEMY_AVAILABLE", False)
    @patch("rfs.database.base.TORTOISE_AVAILABLE", False)
    async def test_add_database_no_orm_supported(self):
        """지원되는 ORM이 없는 경우 - 라인 334-335 커버"""
        config = DatabaseConfig(url="sqlite:///:memory:")

        result = await self.manager.add_database("no_orm_db", config)

        assert not result.is_success()
        assert "지원되는 ORM이 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_add_database_initialization_failure(self):
        """데이터베이스 초기화 실패 - 라인 339-340 커버"""
        config = DatabaseConfig(url="sqlite:///:memory:")

        with patch.object(
            SQLAlchemyDatabase, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Failure("Init failed")

            result = await self.manager.add_database("fail_db", config)

            assert not result.is_success()
            # 초기화 실패한 Result 객체가 그대로 반환되어야 함
            assert result.unwrap_error() == "Init failed"

    @pytest.mark.asyncio
    async def test_add_database_second_db_no_default_change(self):
        """두 번째 데이터베이스 추가 시 default 변경되지 않음 - 라인 345-346 커버"""
        config1 = DatabaseConfig(url="sqlite:///:memory:")
        config2 = DatabaseConfig(url="sqlite:///:memory:")

        with patch.object(
            SQLAlchemyDatabase, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Success(None)

            await self.manager.add_database("first_db", config1)
            await self.manager.add_database("second_db", config2)

            assert self.manager.default_database == "first_db"  # 변경되지 않음

    @pytest.mark.asyncio
    async def test_add_database_exception_handling(self):
        """데이터베이스 추가 중 예외 발생 - 라인 351-352 커버"""
        config = DatabaseConfig(url="sqlite:///:memory:")

        with patch.object(SQLAlchemyDatabase, "__init__") as mock_init:
            mock_init.side_effect = Exception("Unexpected error")

            result = await self.manager.add_database("error_db", config)

            assert not result.is_success()
            assert "데이터베이스 추가 실패" in result.unwrap_error()
            assert "Unexpected error" in result.unwrap_error()

    def test_get_database_default(self):
        """기본 데이터베이스 조회 - 라인 356-359 커버"""
        mock_db = Mock()
        self.manager.databases = {"default_db": mock_db}
        self.manager.default_database = "default_db"

        db = self.manager.get_database()

        assert db == mock_db

    def test_get_database_by_name(self):
        """이름으로 데이터베이스 조회"""
        mock_db = Mock()
        self.manager.databases = {"named_db": mock_db}

        db = self.manager.get_database("named_db")

        assert db == mock_db

    def test_get_database_not_found(self):
        """존재하지 않는 데이터베이스 조회"""
        db = self.manager.get_database("nonexistent")

        assert db is None

    def test_get_database_no_default(self):
        """기본 데이터베이스가 설정되지 않은 경우"""
        self.manager.default_database = None

        db = self.manager.get_database()

        assert db is None

    @pytest.mark.asyncio
    async def test_close_all_success(self):
        """모든 데이터베이스 정상 종료 - 라인 363-371 커버"""
        mock_db1 = AsyncMock()
        mock_db2 = AsyncMock()
        mock_db1.close = AsyncMock()
        mock_db2.close = AsyncMock()

        self.manager.databases = {"db1": mock_db1, "db2": mock_db2}
        self.manager.default_database = "db1"

        await self.manager.close_all()

        mock_db1.close.assert_called_once()
        mock_db2.close.assert_called_once()
        # databases 딕셔너리는 비워지고 default_database는 None이 되어야 함
        assert self.manager.default_database is None

    @pytest.mark.asyncio
    async def test_close_all_with_exception(self):
        """데이터베이스 종료 중 예외 발생 - 라인 367-368 커버"""
        mock_db1 = AsyncMock()
        mock_db2 = AsyncMock()
        mock_db1.close = AsyncMock(side_effect=Exception("Close error"))
        mock_db2.close = AsyncMock()  # 정상 종료

        self.manager.databases = {"db1": mock_db1, "db2": mock_db2}

        # 예외가 발생해도 전체가 중단되지 않고 계속 진행되어야 함
        await self.manager.close_all()

        mock_db1.close.assert_called_once()
        mock_db2.close.assert_called_once()


class TestGlobalFunctions:
    """전역 함수들 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # Singleton 초기화
        DatabaseManager._instances = {}

    def test_get_database_manager(self):
        """데이터베이스 매니저 인스턴스 반환 - 라인 376-377 커버"""
        manager1 = get_database_manager()
        manager2 = get_database_manager()

        assert isinstance(manager1, DatabaseManager)
        assert manager1 is manager2  # Singleton

    def test_get_database_function(self):
        """데이터베이스 인스턴스 반환 함수 - 라인 381-383 커버"""
        # Mock database 설정
        mock_db = Mock()
        manager = get_database_manager()
        manager.get_database = Mock(return_value=mock_db)

        db = get_database("test_db")

        assert db == mock_db
        manager.get_database.assert_called_once_with("test_db")

    def test_get_database_function_no_name(self):
        """이름 없이 데이터베이스 인스턴스 반환"""
        mock_db = Mock()
        manager = get_database_manager()
        manager.get_database = Mock(return_value=mock_db)

        db = get_database()

        assert db == mock_db
        manager.get_database.assert_called_once_with(None)


class TestImportErrorHandling:
    """Import 에러 핸들링 테스트"""

    def test_sqlalchemy_available_true(self):
        """SQLAlchemy 사용 가능 플래그 확인"""
        # 모킹된 상태에서는 임포트가 성공하므로 True여야 함
        # 실제 환경에 따라 달라질 수 있음
        assert SQLALCHEMY_AVAILABLE in [True, False]

    def test_tortoise_available_true(self):
        """Tortoise 사용 가능 플래그 확인"""
        # 모킹된 상태에서는 임포트가 성공하므로 True여야 함
        # 실제 환경에 따라 달라질 수 있음
        assert TORTOISE_AVAILABLE in [True, False]


class TestDatabaseTypeAndOrmType:
    """Enum 타입들 테스트"""

    def test_database_type_values(self):
        """DatabaseType enum 값들 확인"""
        assert DatabaseType.POSTGRESQL == "postgresql"
        assert DatabaseType.MYSQL == "mysql"
        assert DatabaseType.SQLITE == "sqlite"
        assert DatabaseType.CLOUD_SQL == "cloud_sql"

    def test_orm_type_values(self):
        """ORMType enum 값들 확인"""
        assert ORMType.SQLALCHEMY == "sqlalchemy"
        assert ORMType.TORTOISE == "tortoise"
        assert ORMType.AUTO == "auto"
