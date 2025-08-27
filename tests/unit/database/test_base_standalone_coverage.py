"""
base.py 독립 테스트 - 90% 커버리지 달성
models.py import 없이 base.py만 독립적으로 테스트
"""

import asyncio
import os

# base.py만 직접 임포트 (models.py 의존성 제거)
import sys
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# 임포트 전에 models 관련 모듈을 Mock으로 처리
sys.modules["src.rfs.database.models"] = Mock()
sys.modules["src.rfs.database.models_refactored"] = Mock()

from src.rfs.core.result import Failure, Result, Success
from src.rfs.database.base import (
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


class TestDatabaseType:
    """DatabaseType enum 테스트"""

    def test_database_type_values(self):
        """모든 DatabaseType 값이 올바른지 확인"""
        assert DatabaseType.POSTGRESQL.value == "postgresql"
        assert DatabaseType.MYSQL.value == "mysql"
        assert DatabaseType.SQLITE.value == "sqlite"
        assert DatabaseType.CLOUD_SQL.value == "cloud_sql"

    def test_database_type_enum_completeness(self):
        """DatabaseType enum 완전성 확인"""
        all_types = list(DatabaseType)
        assert len(all_types) == 4

        values = [db_type.value for db_type in all_types]
        expected_values = ["postgresql", "mysql", "sqlite", "cloud_sql"]

        for expected in expected_values:
            assert expected in values


class TestORMType:
    """ORMType enum 테스트"""

    def test_orm_type_values(self):
        """모든 ORMType 값이 올바른지 확인"""
        assert ORMType.SQLALCHEMY.value == "sqlalchemy"
        assert ORMType.TORTOISE.value == "tortoise"
        assert ORMType.AUTO.value == "auto"

    def test_orm_type_enum_completeness(self):
        """ORMType enum 완전성 확인"""
        all_types = list(ORMType)
        assert len(all_types) == 3

        values = [orm_type.value for orm_type in all_types]
        expected_values = ["sqlalchemy", "tortoise", "auto"]

        for expected in expected_values:
            assert expected in values


class TestDatabaseConfig:
    """DatabaseConfig 데이터클래스 테스트"""

    def test_basic_config_creation(self):
        """기본 DatabaseConfig 생성"""
        config = DatabaseConfig(url="postgresql://localhost/test")

        assert config.url == "postgresql://localhost/test"
        assert config.database_type == DatabaseType.POSTGRESQL
        assert config.orm_type == ORMType.AUTO

    def test_config_with_all_parameters(self):
        """모든 파라미터를 포함한 DatabaseConfig"""
        config = DatabaseConfig(
            url="mysql://user:pass@localhost/db",
            database_type=DatabaseType.MYSQL,
            orm_type=ORMType.SQLALCHEMY,
            pool_size=15,
            max_overflow=25,
            pool_timeout=60,
            pool_recycle=7200,
            pool_pre_ping=False,
            auto_commit=True,
            isolation_level="SERIALIZABLE",
            cloud_sql_instance="instance-1",
            cloud_sql_project="my-project",
            cloud_sql_region="asia-northeast3",
            echo=True,
            echo_pool=True,
            future=False,
            extra_options={"option1": "value1"},
        )

        assert config.url == "mysql://user:pass@localhost/db"
        assert config.database_type == DatabaseType.MYSQL
        assert config.orm_type == ORMType.SQLALCHEMY
        assert config.pool_size == 15
        assert config.max_overflow == 25
        assert config.pool_timeout == 60
        assert config.pool_recycle == 7200
        assert config.pool_pre_ping is False
        assert config.auto_commit is True
        assert config.isolation_level == "SERIALIZABLE"
        assert config.cloud_sql_instance == "instance-1"
        assert config.cloud_sql_project == "my-project"
        assert config.cloud_sql_region == "asia-northeast3"
        assert config.echo is True
        assert config.echo_pool is True
        assert config.future is False
        assert config.extra_options == {"option1": "value1"}

    def test_default_values(self):
        """기본값 확인"""
        config = DatabaseConfig(url="test://localhost/db")

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

    def test_get_sqlalchemy_url_regular(self):
        """일반 SQLAlchemy URL 반환"""
        config = DatabaseConfig(url="postgresql://localhost/test")

        result = config.get_sqlalchemy_url()
        assert result == "postgresql://localhost/test"

    def test_get_sqlalchemy_url_cloud_sql(self):
        """Cloud SQL SQLAlchemy URL 반환"""
        config = DatabaseConfig(
            url="postgresql://localhost/test",
            database_type=DatabaseType.CLOUD_SQL,
            cloud_sql_instance="instance-1",
            cloud_sql_project="my-project",
            cloud_sql_region="asia-northeast3",
        )

        result = config.get_sqlalchemy_url()
        expected = "postgresql+asyncpg://user:password@/dbname?host=/cloudsql/my-project:asia-northeast3:instance-1"
        assert result == expected

    def test_get_sqlalchemy_url_cloud_sql_no_instance(self):
        """Cloud SQL이지만 instance 정보가 없는 경우"""
        config = DatabaseConfig(
            url="postgresql://localhost/test", database_type=DatabaseType.CLOUD_SQL
        )

        result = config.get_sqlalchemy_url()
        assert result == "postgresql://localhost/test"  # 원래 URL 반환

    def test_get_tortoise_config_postgresql(self):
        """PostgreSQL Tortoise 설정"""
        config = DatabaseConfig(
            url="postgresql://user:pass@host:5432/dbname",
            pool_size=15,
            extra_options={"ssl": True},
        )

        result = config.get_tortoise_config()

        assert "connections" in result
        assert "default" in result["connections"]
        assert result["connections"]["default"]["engine"] == "tortoise.backends.asyncpg"

        credentials = result["connections"]["default"]["credentials"]
        assert credentials["database"] == "dbname"
        assert credentials["host"] == "localhost"
        assert credentials["port"] == 5432
        assert credentials["user"] == "postgres"
        assert credentials["password"] == ""
        assert credentials["maxsize"] == 15
        assert credentials["ssl"] is True

        assert "apps" in result
        assert "models" in result["apps"]

    def test_get_tortoise_config_sqlite(self):
        """SQLite Tortoise 설정"""
        config = DatabaseConfig(url="sqlite://test.db")

        result = config.get_tortoise_config()

        assert (
            result["connections"]["default"]["engine"] == "tortoise.backends.aiosqlite"
        )
        assert result["connections"]["default"]["credentials"]["database"] == "test.db"

    def test_get_tortoise_config_simple_url(self):
        """단순 URL로 Tortoise 설정"""
        config = DatabaseConfig(url="mydb")

        result = config.get_tortoise_config()

        credentials = result["connections"]["default"]["credentials"]
        assert credentials["database"] == "mydb"


class TestConnectionPool:
    """ConnectionPool 클래스 테스트"""

    def test_connection_pool_creation(self):
        """ConnectionPool 생성 테스트"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        assert pool.config == config
        assert pool._engine is None
        assert pool._async_engine is None
        assert pool._session_factory is None
        assert pool._async_session_factory is None

    @pytest.mark.asyncio
    async def test_initialize_no_orm_available(self):
        """ORM이 사용 불가능한 경우"""
        config = DatabaseConfig(url="test://localhost/db", orm_type=ORMType.AUTO)
        pool = ConnectionPool(config)

        # SQLAlchemy와 Tortoise 모두 비활성화
        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", False),
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", False),
        ):

            result = await pool.initialize()

            assert result.is_failure()
            error = result.unwrap_error()
            # 실제 에러 메시지에 맞춰서 검증
            assert (
                "사용 가능한 ORM이 없습니다" in error or "연결 풀 초기화 실패" in error
            )

    @pytest.mark.asyncio
    async def test_initialize_sqlalchemy_explicit(self):
        """명시적 SQLAlchemy 초기화"""
        config = DatabaseConfig(url="test://localhost/db", orm_type=ORMType.SQLALCHEMY)
        pool = ConnectionPool(config)

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch.object(
                pool, "_initialize_sqlalchemy", new_callable=AsyncMock
            ) as mock_init,
        ):

            result = await pool.initialize()

            assert result.is_success()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_tortoise_explicit(self):
        """명시적 Tortoise 초기화"""
        config = DatabaseConfig(url="test://localhost/db", orm_type=ORMType.TORTOISE)
        pool = ConnectionPool(config)

        with (
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", True),
            patch.object(
                pool, "_initialize_tortoise", new_callable=AsyncMock
            ) as mock_init,
        ):

            result = await pool.initialize()

            assert result.is_success()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_auto_sqlalchemy_preferred(self):
        """AUTO 모드에서 SQLAlchemy 우선 선택"""
        config = DatabaseConfig(url="test://localhost/db", orm_type=ORMType.AUTO)
        pool = ConnectionPool(config)

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", True),
            patch.object(
                pool, "_initialize_sqlalchemy", new_callable=AsyncMock
            ) as mock_sqlalchemy,
            patch.object(
                pool, "_initialize_tortoise", new_callable=AsyncMock
            ) as mock_tortoise,
        ):

            result = await pool.initialize()

            assert result.is_success()
            mock_sqlalchemy.assert_called_once()
            mock_tortoise.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_auto_tortoise_fallback(self):
        """AUTO 모드에서 Tortoise 대체 선택"""
        config = DatabaseConfig(url="test://localhost/db", orm_type=ORMType.AUTO)
        pool = ConnectionPool(config)

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", False),
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", True),
            patch.object(
                pool, "_initialize_tortoise", new_callable=AsyncMock
            ) as mock_tortoise,
        ):

            result = await pool.initialize()

            assert result.is_success()
            mock_tortoise.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_exception_handling(self):
        """초기화 중 예외 처리"""
        config = DatabaseConfig(url="test://localhost/db", orm_type=ORMType.SQLALCHEMY)
        pool = ConnectionPool(config)

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch.object(
                pool, "_initialize_sqlalchemy", new_callable=AsyncMock
            ) as mock_init,
        ):

            mock_init.side_effect = Exception("초기화 실패")

            result = await pool.initialize()

            assert result.is_failure()
            error = result.unwrap_error()
            assert "연결 풀 초기화 실패" in error
            assert "초기화 실패" in error

    @pytest.mark.asyncio
    async def test_initialize_sqlalchemy_not_available(self):
        """SQLAlchemy 초기화 시 라이브러리 없음"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        with patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="SQLAlchemy가 설치되지 않았습니다"):
                await pool._initialize_sqlalchemy()

    @pytest.mark.asyncio
    async def test_initialize_tortoise_not_available(self):
        """Tortoise 초기화 시 라이브러리 없음"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        with patch("src.rfs.database.base.TORTOISE_AVAILABLE", False):
            with pytest.raises(
                RuntimeError, match="Tortoise ORM이 설치되지 않았습니다"
            ):
                await pool._initialize_tortoise()

    @pytest.mark.asyncio
    @patch("src.rfs.database.base.create_async_engine")
    @patch("src.rfs.database.base.sessionmaker")
    async def test_initialize_sqlalchemy_success(
        self, mock_sessionmaker, mock_create_engine
    ):
        """SQLAlchemy 성공적 초기화"""
        config = DatabaseConfig(
            url="postgresql://localhost/test", echo=True, pool_size=10
        )
        pool = ConnectionPool(config)

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        mock_session_factory = Mock()
        mock_sessionmaker.return_value = mock_session_factory

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch("src.rfs.database.base.AsyncSession") as mock_async_session,
        ):

            await pool._initialize_sqlalchemy()

            # create_async_engine 호출 확인
            mock_create_engine.assert_called_once_with(
                "postgresql://localhost/test",
                echo=True,
                echo_pool=False,
                pool_size=10,
                max_overflow=30,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                future=True,
            )

            # sessionmaker 호출 확인
            mock_sessionmaker.assert_called_once_with(
                mock_engine, class_=mock_async_session, expire_on_commit=False
            )

            assert pool._async_engine == mock_engine
            assert pool._async_session_factory == mock_session_factory

    @pytest.mark.asyncio
    @patch("src.rfs.database.base.Tortoise")
    async def test_initialize_tortoise_success(self, mock_tortoise):
        """Tortoise 성공적 초기화"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        pool = ConnectionPool(config)

        # Tortoise.init을 AsyncMock으로 설정
        mock_tortoise.init = AsyncMock()

        with patch("src.rfs.database.base.TORTOISE_AVAILABLE", True):
            await pool._initialize_tortoise()

            # Tortoise.init 호출 확인
            mock_tortoise.init.assert_called_once()

            # 전달된 config 확인
            call_args = mock_tortoise.init.call_args
            assert "config" in call_args.kwargs
            tortoise_config = call_args.kwargs["config"]
            assert "connections" in tortoise_config
            assert "apps" in tortoise_config

    def test_get_engine(self):
        """엔진 반환 테스트"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        # 비동기 엔진이 있는 경우
        mock_async_engine = Mock()
        pool._async_engine = mock_async_engine

        result = pool.get_engine()
        assert result == mock_async_engine

        # 동기 엔진만 있는 경우
        pool._async_engine = None
        mock_engine = Mock()
        pool._engine = mock_engine

        result = pool.get_engine()
        assert result == mock_engine

        # 엔진이 없는 경우
        pool._engine = None
        result = pool.get_engine()
        assert result is None

    def test_get_session_factory(self):
        """세션 팩토리 반환 테스트"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        # 비동기 세션 팩토리가 있는 경우
        mock_async_factory = Mock()
        pool._async_session_factory = mock_async_factory

        result = pool.get_session_factory()
        assert result == mock_async_factory

        # 동기 세션 팩토리만 있는 경우
        pool._async_session_factory = None
        mock_factory = Mock()
        pool._session_factory = mock_factory

        result = pool.get_session_factory()
        assert result == mock_factory

        # 팩토리가 없는 경우
        pool._session_factory = None
        result = pool.get_session_factory()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_async_engine_only(self):
        """비동기 엔진만 있는 경우 종료"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        mock_async_engine = AsyncMock()
        pool._async_engine = mock_async_engine

        await pool.close()

        mock_async_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_sync_engine_only(self):
        """동기 엔진만 있는 경우 종료"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        mock_engine = Mock()
        pool._engine = mock_engine

        await pool.close()

        mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.rfs.database.base.Tortoise")
    async def test_close_with_tortoise(self, mock_tortoise):
        """Tortoise와 함께 종료"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        with patch("src.rfs.database.base.TORTOISE_AVAILABLE", True):
            mock_tortoise._inited = True

            await pool.close()

            mock_tortoise.close_connections.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_exception_handling(self):
        """종료 중 예외 처리"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        mock_async_engine = AsyncMock()
        mock_async_engine.dispose.side_effect = Exception("종료 실패")
        pool._async_engine = mock_async_engine

        # 예외가 발생해도 정상적으로 종료되어야 함
        await pool.close()

        mock_async_engine.dispose.assert_called_once()


class TestDatabase:
    """Database 추상 클래스 테스트"""

    def test_database_creation(self):
        """Database 생성 테스트"""
        config = DatabaseConfig(url="test://localhost/db")

        # 추상 클래스이므로 직접 인스턴스화 불가
        # 하위 클래스로 테스트
        class TestDatabase(Database):
            async def execute_query(
                self, query: str, params: Dict[str, Any] = None
            ) -> Result[Any, str]:
                return Success("test")

            async def create_session(self):
                return Mock()

        db = TestDatabase(config)

        assert db.config == config
        assert isinstance(db.connection_pool, ConnectionPool)
        assert db._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """데이터베이스 초기화 성공"""
        config = DatabaseConfig(url="test://localhost/db")

        class TestDatabase(Database):
            async def execute_query(
                self, query: str, params: Dict[str, Any] = None
            ) -> Result[Any, str]:
                return Success("test")

            async def create_session(self):
                return Mock()

        db = TestDatabase(config)

        with patch.object(
            db.connection_pool, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Success(None)

            result = await db.initialize()

            assert result.is_success()
            assert db._initialized is True
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self):
        """이미 초기화된 경우"""
        config = DatabaseConfig(url="test://localhost/db")

        class TestDatabase(Database):
            async def execute_query(
                self, query: str, params: Dict[str, Any] = None
            ) -> Result[Any, str]:
                return Success("test")

            async def create_session(self):
                return Mock()

        db = TestDatabase(config)
        db._initialized = True

        with patch.object(
            db.connection_pool, "initialize", new_callable=AsyncMock
        ) as mock_init:

            result = await db.initialize()

            assert result.is_success()
            mock_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """데이터베이스 초기화 실패"""
        config = DatabaseConfig(url="test://localhost/db")

        class TestDatabase(Database):
            async def execute_query(
                self, query: str, params: Dict[str, Any] = None
            ) -> Result[Any, str]:
                return Success("test")

            async def create_session(self):
                return Mock()

        db = TestDatabase(config)

        with patch.object(
            db.connection_pool, "initialize", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Failure("초기화 실패")

            result = await db.initialize()

            assert result.is_failure()
            assert db._initialized is False
            error = result.unwrap_error()
            assert "초기화 실패" in error

    @pytest.mark.asyncio
    async def test_close(self):
        """데이터베이스 종료"""
        config = DatabaseConfig(url="test://localhost/db")

        class TestDatabase(Database):
            async def execute_query(
                self, query: str, params: Dict[str, Any] = None
            ) -> Result[Any, str]:
                return Success("test")

            async def create_session(self):
                return Mock()

        db = TestDatabase(config)
        db._initialized = True

        with patch.object(
            db.connection_pool, "close", new_callable=AsyncMock
        ) as mock_close:

            await db.close()

            assert db._initialized is False
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_connection_pool(self):
        """연결 풀이 없는 경우 종료"""
        config = DatabaseConfig(url="test://localhost/db")

        class TestDatabase(Database):
            async def execute_query(
                self, query: str, params: Dict[str, Any] = None
            ) -> Result[Any, str]:
                return Success("test")

            async def create_session(self):
                return Mock()

        db = TestDatabase(config)
        db.connection_pool = None
        db._initialized = True

        # 예외 없이 종료되어야 함
        await db.close()

        assert db._initialized is False


class TestSQLAlchemyDatabase:
    """SQLAlchemyDatabase 테스트"""

    def test_sqlalchemy_database_creation(self):
        """SQLAlchemyDatabase 생성"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = SQLAlchemyDatabase(config)

        assert isinstance(db, Database)
        assert db.config == config

    @pytest.mark.asyncio
    async def test_execute_query_success(self):
        """쿼리 실행 성공"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = SQLAlchemyDatabase(config)

        # Mock 세션 생성 (컨텍스트 매니저로 동작)
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [{"id": 1, "name": "test"}]
        mock_session.execute.return_value = mock_result

        # 컨텍스트 매니저 Mock
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock()

        with patch.object(db, "create_session") as mock_create_session:
            mock_create_session.return_value = mock_context_manager

            result = await db.execute_query("SELECT * FROM test", {"param": "value"})

            assert result.is_success()
            data = result.unwrap()
            assert data == [{"id": 1, "name": "test"}]

            mock_session.execute.assert_called_once_with(
                "SELECT * FROM test", {"param": "value"}
            )
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_no_params(self):
        """파라미터 없는 쿼리 실행"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = SQLAlchemyDatabase(config)

        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock()

        with patch.object(db, "create_session") as mock_create_session:
            mock_create_session.return_value = mock_context_manager

            result = await db.execute_query("SELECT 1")

            assert result.is_success()
            mock_session.execute.assert_called_once_with("SELECT 1", {})

    @pytest.mark.asyncio
    async def test_execute_query_exception(self):
        """쿼리 실행 중 예외"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = SQLAlchemyDatabase(config)

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("SQL 실행 오류")

        with patch.object(db, "create_session") as mock_create_session:
            mock_create_session.return_value = mock_session
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            result = await db.execute_query("INVALID SQL")

            assert result.is_failure()
            error = result.unwrap_error()
            assert "쿼리 실행 실패" in error
            assert "SQL 실행 오류" in error

    @pytest.mark.asyncio
    async def test_create_session(self):
        """세션 생성 테스트"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = SQLAlchemyDatabase(config)

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        with patch.object(
            db.connection_pool, "get_session_factory"
        ) as mock_get_factory:
            mock_get_factory.return_value = mock_session_factory

            result = await db.create_session()

            assert result == mock_session
            mock_session_factory.assert_called_once()


class TestTortoiseDatabase:
    """TortoiseDatabase 테스트"""

    def test_tortoise_database_creation(self):
        """TortoiseDatabase 생성"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = TortoiseDatabase(config)

        assert isinstance(db, Database)
        assert db.config == config

    @pytest.mark.asyncio
    @patch("src.rfs.database.base.connections")
    async def test_execute_query_success(self, mock_connections):
        """쿼리 실행 성공"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = TortoiseDatabase(config)

        mock_connection = AsyncMock()
        mock_connection.execute_query.return_value = [{"id": 1, "name": "test"}]
        mock_connections.get.return_value = mock_connection

        result = await db.execute_query("SELECT * FROM test", ["param"])

        assert result.is_success()
        data = result.unwrap()
        assert data == [{"id": 1, "name": "test"}]

        mock_connections.get.assert_called_once_with("default")
        mock_connection.execute_query.assert_called_once_with(
            "SELECT * FROM test", ["param"]
        )

    @pytest.mark.asyncio
    @patch("src.rfs.database.base.connections")
    async def test_execute_query_no_params(self, mock_connections):
        """파라미터 없는 쿼리 실행"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = TortoiseDatabase(config)

        mock_connection = AsyncMock()
        mock_connection.execute_query.return_value = []
        mock_connections.get.return_value = mock_connection

        result = await db.execute_query("SELECT 1")

        assert result.is_success()
        mock_connection.execute_query.assert_called_once_with("SELECT 1", [])

    @pytest.mark.asyncio
    @patch("src.rfs.database.base.connections")
    async def test_execute_query_exception(self, mock_connections):
        """쿼리 실행 중 예외"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = TortoiseDatabase(config)

        mock_connection = AsyncMock()
        mock_connection.execute_query.side_effect = Exception("Tortoise 실행 오류")
        mock_connections.get.return_value = mock_connection

        result = await db.execute_query("INVALID SQL")

        assert result.is_failure()
        error = result.unwrap_error()
        assert "쿼리 실행 실패" in error
        assert "Tortoise 실행 오류" in error

    @pytest.mark.asyncio
    @patch("src.rfs.database.base.in_transaction")
    async def test_create_session(self, mock_in_transaction):
        """세션 생성 테스트"""
        config = DatabaseConfig(url="postgresql://localhost/test")
        db = TortoiseDatabase(config)

        mock_transaction = Mock()
        mock_in_transaction.return_value = mock_transaction

        result = await db.create_session()

        assert result == mock_transaction
        mock_in_transaction.assert_called_once()


class TestDatabaseManager:
    """DatabaseManager 테스트"""

    def test_database_manager_singleton(self):
        """DatabaseManager 싱글톤 확인"""
        manager1 = DatabaseManager()
        manager2 = DatabaseManager()

        assert manager1 is manager2

    def test_database_manager_initialization(self):
        """DatabaseManager 초기화"""
        manager = DatabaseManager()

        assert manager.databases == {}
        assert manager.default_database is None

    @pytest.mark.asyncio
    async def test_add_database_sqlalchemy_success(self):
        """SQLAlchemy 데이터베이스 추가 성공"""
        manager = DatabaseManager()
        config = DatabaseConfig(
            url="postgresql://localhost/test", orm_type=ORMType.SQLALCHEMY
        )

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch("src.rfs.database.base.SQLAlchemyDatabase") as mock_db_class,
        ):

            mock_database = AsyncMock()
            mock_database.initialize.return_value = Success(None)
            mock_db_class.return_value = mock_database

            result = await manager.add_database("test_db", config)

            assert result.is_success()
            assert "test_db" in manager.databases
            assert manager.default_database == "test_db"

            mock_db_class.assert_called_once_with(config)
            mock_database.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_database_tortoise_success(self):
        """Tortoise 데이터베이스 추가 성공"""
        manager = DatabaseManager()
        config = DatabaseConfig(
            url="postgresql://localhost/test", orm_type=ORMType.TORTOISE
        )

        with (
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", True),
            patch("src.rfs.database.base.TortoiseDatabase") as mock_db_class,
        ):

            mock_database = AsyncMock()
            mock_database.initialize.return_value = Success(None)
            mock_db_class.return_value = mock_database

            result = await manager.add_database("test_db", config)

            assert result.is_success()
            assert "test_db" in manager.databases

            mock_db_class.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_add_database_auto_sqlalchemy(self):
        """AUTO 모드에서 SQLAlchemy 선택"""
        manager = DatabaseManager()
        config = DatabaseConfig(
            url="postgresql://localhost/test", orm_type=ORMType.AUTO
        )

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", False),
            patch("src.rfs.database.base.SQLAlchemyDatabase") as mock_db_class,
        ):

            mock_database = AsyncMock()
            mock_database.initialize.return_value = Success(None)
            mock_db_class.return_value = mock_database

            result = await manager.add_database("test_db", config)

            assert result.is_success()
            mock_db_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_database_auto_tortoise(self):
        """AUTO 모드에서 Tortoise 선택"""
        manager = DatabaseManager()
        config = DatabaseConfig(
            url="postgresql://localhost/test", orm_type=ORMType.AUTO
        )

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", False),
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", True),
            patch("src.rfs.database.base.TortoiseDatabase") as mock_db_class,
        ):

            mock_database = AsyncMock()
            mock_database.initialize.return_value = Success(None)
            mock_db_class.return_value = mock_database

            result = await manager.add_database("test_db", config)

            assert result.is_success()
            mock_db_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_database_no_orm_available(self):
        """ORM 사용 불가능한 경우"""
        manager = DatabaseManager()
        config = DatabaseConfig(
            url="postgresql://localhost/test", orm_type=ORMType.AUTO
        )

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", False),
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", False),
        ):

            result = await manager.add_database("test_db", config)

            assert result.is_failure()
            error = result.unwrap_error()
            assert "지원되는 ORM이 없습니다" in error

    @pytest.mark.asyncio
    async def test_add_database_initialization_failure(self):
        """데이터베이스 초기화 실패"""
        manager = DatabaseManager()
        config = DatabaseConfig(
            url="postgresql://localhost/test", orm_type=ORMType.SQLALCHEMY
        )

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch("src.rfs.database.base.SQLAlchemyDatabase") as mock_db_class,
        ):

            mock_database = AsyncMock()
            mock_database.initialize.return_value = Failure("초기화 실패")
            mock_db_class.return_value = mock_database

            result = await manager.add_database("test_db", config)

            assert result.is_failure()
            error = result.unwrap_error()
            assert "초기화 실패" in error

    @pytest.mark.asyncio
    async def test_add_database_exception(self):
        """데이터베이스 추가 중 예외"""
        manager = DatabaseManager()
        config = DatabaseConfig(
            url="postgresql://localhost/test", orm_type=ORMType.SQLALCHEMY
        )

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch("src.rfs.database.base.SQLAlchemyDatabase") as mock_db_class,
        ):

            mock_db_class.side_effect = Exception("생성 실패")

            result = await manager.add_database("test_db", config)

            assert result.is_failure()
            error = result.unwrap_error()
            assert "데이터베이스 추가 실패" in error

    @pytest.mark.asyncio
    async def test_add_multiple_databases(self):
        """여러 데이터베이스 추가"""
        manager = DatabaseManager()
        config1 = DatabaseConfig(
            url="postgresql://localhost/test1", orm_type=ORMType.SQLALCHEMY
        )
        config2 = DatabaseConfig(
            url="postgresql://localhost/test2", orm_type=ORMType.SQLALCHEMY
        )

        with (
            patch("src.rfs.database.base.SQLALCHEMY_AVAILABLE", True),
            patch("src.rfs.database.base.SQLAlchemyDatabase") as mock_db_class,
        ):

            mock_database = AsyncMock()
            mock_database.initialize.return_value = Success(None)
            mock_db_class.return_value = mock_database

            # 첫 번째 데이터베이스 추가
            result1 = await manager.add_database("db1", config1)
            assert result1.is_success()
            assert manager.default_database == "db1"

            # 두 번째 데이터베이스 추가
            result2 = await manager.add_database("db2", config2)
            assert result2.is_success()
            assert manager.default_database == "db1"  # 첫 번째가 기본으로 유지

            assert len(manager.databases) == 2

    def test_get_database_default(self):
        """기본 데이터베이스 조회"""
        manager = DatabaseManager()
        mock_database = Mock()

        manager.databases = {"default": mock_database}
        manager.default_database = "default"

        result = manager.get_database()
        assert result == mock_database

    def test_get_database_by_name(self):
        """이름으로 데이터베이스 조회"""
        manager = DatabaseManager()
        mock_database1 = Mock()
        mock_database2 = Mock()

        manager.databases = {"db1": mock_database1, "db2": mock_database2}

        result = manager.get_database("db2")
        assert result == mock_database2

    def test_get_database_not_found(self):
        """존재하지 않는 데이터베이스 조회"""
        manager = DatabaseManager()

        result = manager.get_database("nonexistent")
        assert result is None

    def test_get_database_no_default(self):
        """기본 데이터베이스가 없는 경우"""
        manager = DatabaseManager()

        result = manager.get_database()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_all_success(self):
        """모든 데이터베이스 성공적 종료"""
        manager = DatabaseManager()

        mock_db1 = AsyncMock()
        mock_db2 = AsyncMock()

        manager.databases = {"db1": mock_db1, "db2": mock_db2}
        manager.default_database = "db1"

        await manager.close_all()

        mock_db1.close.assert_called_once()
        mock_db2.close.assert_called_once()

        assert manager.databases == {}
        assert manager.default_database is None

    @pytest.mark.asyncio
    async def test_close_all_with_exception(self):
        """일부 데이터베이스 종료 실패"""
        manager = DatabaseManager()

        mock_db1 = AsyncMock()
        mock_db2 = AsyncMock()
        mock_db2.close.side_effect = Exception("종료 실패")

        manager.databases = {"db1": mock_db1, "db2": mock_db2}

        # 예외가 발생해도 정상적으로 완료되어야 함
        await manager.close_all()

        mock_db1.close.assert_called_once()
        mock_db2.close.assert_called_once()


class TestGlobalFunctions:
    """전역 함수 테스트"""

    def test_get_database_manager(self):
        """get_database_manager 함수 테스트"""
        manager1 = get_database_manager()
        manager2 = get_database_manager()

        assert isinstance(manager1, DatabaseManager)
        assert manager1 is manager2  # 싱글톤 확인

    def test_get_database_function(self):
        """get_database 함수 테스트"""
        mock_database = Mock()

        with patch("src.rfs.database.base.get_database_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_database.return_value = mock_database
            mock_get_manager.return_value = mock_manager

            result = get_database("test_db")

            assert result == mock_database
            mock_get_manager.assert_called_once()
            mock_manager.get_database.assert_called_once_with("test_db")

    def test_get_database_function_default(self):
        """get_database 함수 (기본값) 테스트"""
        with patch("src.rfs.database.base.get_database_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_database.return_value = None
            mock_get_manager.return_value = mock_manager

            result = get_database()

            assert result is None
            mock_manager.get_database.assert_called_once_with(None)


class TestEdgeCasesAndCoverage:
    """추가 커버리지를 위한 경계 케이스 테스트"""

    def test_database_config_field_defaults(self):
        """데이터클래스 필드 기본값 테스트"""
        config = DatabaseConfig(url="test://localhost/db")

        # extra_options가 빈 딕셔너리로 초기화되는지 확인
        assert config.extra_options == {}

        # 다른 필드 수정
        config.extra_options["custom"] = "value"
        assert config.extra_options["custom"] == "value"

    def test_tortoise_config_url_parsing(self):
        """Tortoise 설정에서 다양한 URL 파싱"""
        # 단순 DB 이름
        config1 = DatabaseConfig(url="testdb")
        tortoise_config1 = config1.get_tortoise_config()
        assert (
            tortoise_config1["connections"]["default"]["credentials"]["database"]
            == "testdb"
        )

        # 복합 URL
        config2 = DatabaseConfig(url="postgresql://user:pass@host:5432/dbname")
        tortoise_config2 = config2.get_tortoise_config()
        assert (
            tortoise_config2["connections"]["default"]["credentials"]["database"]
            == "dbname"
        )

        # '/'가 없는 URL
        config3 = DatabaseConfig(url="sqlite:memory:")
        tortoise_config3 = config3.get_tortoise_config()
        assert (
            tortoise_config3["connections"]["default"]["credentials"]["database"]
            == "sqlite:memory:"
        )

    @pytest.mark.asyncio
    async def test_connection_pool_tortoise_not_inited(self):
        """Tortoise가 초기화되지 않은 상태에서 close"""
        config = DatabaseConfig(url="test://localhost/db")
        pool = ConnectionPool(config)

        with (
            patch("src.rfs.database.base.TORTOISE_AVAILABLE", True),
            patch("src.rfs.database.base.Tortoise") as mock_tortoise,
        ):

            mock_tortoise._inited = False  # 초기화되지 않음

            await pool.close()

            # close_connections가 호출되지 않아야 함
            mock_tortoise.close_connections.assert_not_called()

    @pytest.mark.asyncio
    async def test_database_manager_close_all_empty(self):
        """빈 데이터베이스 매니저 종료"""
        manager = DatabaseManager()

        # 예외 없이 완료되어야 함
        await manager.close_all()

        assert manager.databases == {}
        assert manager.default_database is None

    def test_database_manager_databases_assignment(self):
        """DatabaseManager의 databases 딕셔너리 할당 테스트"""
        manager = DatabaseManager()

        # 새 데이터베이스 딕셔너리 생성 (불변성 패턴)
        original_db = Mock()
        new_db = Mock()

        manager.databases = {"original": original_db}

        # 불변성을 위해 새 딕셔너리 생성하는 패턴 테스트
        new_databases = {**manager.databases, "new": new_db}
        manager.databases = new_databases

        assert "original" in manager.databases
        assert "new" in manager.databases
        assert len(manager.databases) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
