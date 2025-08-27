"""
Session 모듈 커버리지 향상을 위한 집중 테스트

RFS Framework Database Session 시스템의 미커버 코드 라인들을 테스트
"""

from contextvars import ContextVar
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rfs.core.result import Failure, Success
from rfs.database.session import (
    DatabaseSession,
    DatabaseTransaction,
    SessionConfig,
    SessionManager,
    SQLAlchemySession,
    TortoiseSession,
    create_session,
    current_session,
    current_transaction,
    get_current_transaction,
    get_session,
    get_session_manager,
    session_scope,
    transaction_scope,
    with_session,
    with_transaction,
)


class MockDatabase:
    """테스트용 Mock 데이터베이스"""

    def __init__(self, db_type="mock"):
        self.db_type = db_type
        self.sessions = []

    async def create_session(self):
        """Mock 세션 생성"""
        mock_session = Mock()
        mock_session.commit = AsyncMock(return_value=None)
        mock_session.rollback = AsyncMock(return_value=None)
        mock_session.close = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=Mock())
        mock_session.refresh = AsyncMock(return_value=None)
        self.sessions.append(mock_session)
        return mock_session


class TestSessionConfig:
    """SessionConfig 테스트"""

    def test_default_config(self):
        """기본 설정 테스트"""
        config = SessionConfig()

        assert config.auto_commit is True
        assert config.auto_flush is True
        assert config.expire_on_commit is False
        assert config.isolation_level == "READ_COMMITTED"
        assert config.timeout == 30
        assert config.pool_size == 10
        assert config.max_overflow == 20

    def test_custom_config(self):
        """커스텀 설정 테스트"""
        config = SessionConfig(
            auto_commit=False,
            auto_flush=False,
            expire_on_commit=True,
            isolation_level="SERIALIZABLE",
            timeout=60,
            pool_size=5,
            max_overflow=10,
        )

        assert config.auto_commit is False
        assert config.auto_flush is False
        assert config.expire_on_commit is True
        assert config.isolation_level == "SERIALIZABLE"
        assert config.timeout == 60
        assert config.pool_size == 5
        assert config.max_overflow == 10


class TestDatabaseSession:
    """DatabaseSession 추상 클래스 테스트"""

    @pytest.fixture
    def mock_database(self):
        return MockDatabase()

    @pytest.fixture
    def session_config(self):
        return SessionConfig(timeout=60, pool_size=5)

    def test_session_initialization(self, mock_database, session_config):
        """세션 초기화 테스트"""
        # DatabaseSession은 추상 클래스이므로 SQLAlchemySession 사용
        session = SQLAlchemySession(mock_database, session_config)

        assert session.database == mock_database
        assert session.config == session_config
        assert session.session_id == id(session)
        assert session._session is None
        assert session._is_active is False
        assert session._transaction is None

    def test_session_is_active_property(self, mock_database):
        """is_active 프로퍼티 테스트"""
        session = SQLAlchemySession(mock_database)

        assert session.is_active is False
        session._is_active = True
        assert session.is_active is True


class TestSQLAlchemySession:
    """SQLAlchemySession 테스트"""

    @pytest.fixture
    def mock_database(self):
        return MockDatabase("sqlalchemy")

    @pytest.fixture
    def session(self, mock_database):
        return SQLAlchemySession(mock_database)

    @pytest.mark.asyncio
    async def test_begin_new_session(self, session):
        """새 세션 시작 테스트"""
        result = await session.begin()

        assert result.is_success()
        assert session._is_active is True
        assert session._session is not None

    @pytest.mark.asyncio
    async def test_begin_already_active_session(self, session):
        """이미 활성화된 세션 시작 테스트"""
        # 첫 번째 시작
        await session.begin()

        # 두 번째 시작 (이미 활성화됨)
        result = await session.begin()

        assert result.is_success()
        assert session._is_active is True

    @pytest.mark.asyncio
    async def test_begin_exception(self, session):
        """세션 시작 중 예외 발생 테스트"""
        # Mock database가 예외를 발생시키도록 설정
        session.database.create_session = AsyncMock(
            side_effect=Exception("Connection error")
        )

        result = await session.begin()

        assert not result.is_success()
        assert "세션 시작 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_commit_inactive_session(self, session):
        """비활성 세션 커밋 테스트"""
        result = await session.commit()

        assert result.is_success()  # 비활성 세션은 성공으로 처리

    @pytest.mark.asyncio
    async def test_commit_active_session(self, session):
        """활성 세션 커밋 테스트"""
        await session.begin()

        result = await session.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_commit_exception(self, session):
        """커밋 중 예외 발생 테스트"""
        await session.begin()
        session._session.commit = AsyncMock(side_effect=Exception("Commit error"))

        result = await session.commit()

        assert not result.is_success()
        assert "커밋 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_rollback_inactive_session(self, session):
        """비활성 세션 롤백 테스트"""
        result = await session.rollback()

        assert result.is_success()  # 비활성 세션은 성공으로 처리

    @pytest.mark.asyncio
    async def test_rollback_active_session(self, session):
        """활성 세션 롤백 테스트"""
        await session.begin()

        result = await session.rollback()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_rollback_exception(self, session):
        """롤백 중 예외 발생 테스트"""
        await session.begin()
        session._session.rollback = AsyncMock(side_effect=Exception("Rollback error"))

        result = await session.rollback()

        assert not result.is_success()
        assert "롤백 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_close_inactive_session(self, session):
        """비활성 세션 종료 테스트"""
        result = await session.close()

        assert result.is_success()  # 비활성 세션은 성공으로 처리

    @pytest.mark.asyncio
    async def test_close_active_session(self, session):
        """활성 세션 종료 테스트"""
        await session.begin()

        result = await session.close()

        assert result.is_success()
        assert session._is_active is False

    @pytest.mark.asyncio
    async def test_close_exception(self, session):
        """세션 종료 중 예외 발생 테스트"""
        await session.begin()
        session._session.close = AsyncMock(side_effect=Exception("Close error"))

        result = await session.close()

        assert not result.is_success()
        assert "세션 종료 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_execute_inactive_session(self, session):
        """비활성 세션에서 쿼리 실행 테스트"""
        result = await session.execute("SELECT * FROM users")

        assert not result.is_success()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_execute_active_session(self, session):
        """활성 세션에서 쿼리 실행 테스트"""
        await session.begin()

        result = await session.execute("SELECT * FROM users", {"limit": 10})

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_execute_exception(self, session):
        """쿼리 실행 중 예외 발생 테스트"""
        await session.begin()
        session._session.execute = AsyncMock(side_effect=Exception("Query error"))

        result = await session.execute("SELECT * FROM users")

        assert not result.is_success()
        assert "쿼리 실행 실패" in result.unwrap_error()


class TestTortoiseSession:
    """TortoiseSession 테스트"""

    @pytest.fixture
    def mock_database(self):
        return MockDatabase("tortoise")

    @pytest.fixture
    def session(self, mock_database):
        return TortoiseSession(mock_database)

    @pytest.mark.asyncio
    async def test_begin_session(self, session):
        """Tortoise 세션 시작 테스트"""
        result = await session.begin()

        assert result.is_success()
        assert session._is_active is True

    @pytest.mark.asyncio
    async def test_begin_exception(self, session):
        """Tortoise 세션 시작 중 예외 발생"""
        session.database.create_session = AsyncMock(
            side_effect=Exception("Tortoise error")
        )

        result = await session.begin()

        assert not result.is_success()
        assert "세션 시작 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_commit_session(self, session):
        """Tortoise 세션 커밋 테스트"""
        await session.begin()

        result = await session.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_commit_inactive_session(self, session):
        """Tortoise 비활성 세션 커밋"""
        result = await session.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_rollback_session(self, session):
        """Tortoise 세션 롤백 테스트"""
        await session.begin()

        result = await session.rollback()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_close_session(self, session):
        """Tortoise 세션 종료 테스트"""
        await session.begin()

        result = await session.close()

        assert result.is_success()
        assert session._is_active is False

    @pytest.mark.asyncio
    async def test_execute_with_tortoise_connections(self, session):
        """Tortoise connections를 사용한 쿼리 실행"""
        await session.begin()

        with patch("rfs.database.session.connections") as mock_connections:
            mock_connection = Mock()
            mock_connection.execute_query = AsyncMock(return_value=[{"id": 1}])
            mock_connections.get.return_value = mock_connection

            result = await session.execute("SELECT * FROM users", ["param1"])

            assert result.is_success()
            mock_connections.get.assert_called_with("default")
            mock_connection.execute_query.assert_called_with(
                "SELECT * FROM users", ["param1"]
            )

    @pytest.mark.asyncio
    async def test_execute_exception(self, session):
        """Tortoise 쿼리 실행 예외"""
        await session.begin()

        with patch("rfs.database.session.connections") as mock_connections:
            mock_connections.get.side_effect = Exception("Connection error")

            result = await session.execute("SELECT * FROM users")

            assert not result.is_success()
            assert "쿼리 실행 실패" in result.unwrap_error()


class TestDatabaseTransaction:
    """DatabaseTransaction 테스트"""

    @pytest.fixture
    def mock_session(self):
        session = Mock(spec=DatabaseSession)
        session.is_active = True
        session.commit = AsyncMock(return_value=Success(None))
        session.rollback = AsyncMock(return_value=Success(None))
        return session

    @pytest.fixture
    def transaction(self, mock_session):
        return DatabaseTransaction(mock_session)

    @pytest.mark.asyncio
    async def test_begin_transaction(self, transaction):
        """트랜잭션 시작 테스트"""
        result = await transaction.begin()

        assert result.is_success()
        assert transaction._is_active is True
        assert current_transaction.get() == transaction

    @pytest.mark.asyncio
    async def test_begin_transaction_inactive_session(self):
        """비활성 세션에서 트랜잭션 시작"""
        inactive_session = Mock(spec=DatabaseSession)
        inactive_session.is_active = False

        transaction = DatabaseTransaction(inactive_session)
        result = await transaction.begin()

        assert not result.is_success()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_begin_transaction_exception(self, transaction):
        """트랜잭션 시작 중 예외"""
        with patch(
            "rfs.database.session.current_transaction.set",
            side_effect=Exception("Context error"),
        ):
            result = await transaction.begin()

            assert not result.is_success()
            assert "트랜잭션 시작 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_commit_transaction(self, transaction):
        """트랜잭션 커밋 테스트"""
        await transaction.begin()

        result = await transaction.commit()

        assert result.is_success()
        assert transaction._is_active is False
        assert current_transaction.get() is None

    @pytest.mark.asyncio
    async def test_commit_inactive_transaction(self, transaction):
        """비활성 트랜잭션 커밋"""
        result = await transaction.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_rollback_transaction(self, transaction):
        """트랜잭션 롤백 테스트"""
        await transaction.begin()

        result = await transaction.rollback()

        assert result.is_success()
        assert transaction._is_active is False
        assert current_transaction.get() is None

    @pytest.mark.asyncio
    async def test_rollback_inactive_transaction(self, transaction):
        """비활성 트랜잭션 롤백"""
        result = await transaction.rollback()

        assert result.is_success()

    def test_is_active_property(self, transaction):
        """is_active 프로퍼티 테스트"""
        assert transaction.is_active is False

        transaction._is_active = True
        assert transaction.is_active is True

    @pytest.mark.asyncio
    async def test_context_manager_success(self, transaction):
        """트랜잭션 컨텍스트 매니저 성공 시나리오"""
        async with transaction as tx:
            assert tx == transaction
            assert transaction._is_active is True

        # 정상 종료 시 커밋됨
        transaction.session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_context_manager_exception(self, transaction):
        """트랜잭션 컨텍스트 매니저 예외 시나리오"""
        try:
            async with transaction as tx:
                raise Exception("Test exception")
        except Exception:
            pass

        # 예외 발생 시 롤백됨
        transaction.session.rollback.assert_called()


class TestSessionManager:
    """SessionManager 테스트"""

    @pytest.fixture
    def manager(self):
        return SessionManager()

    @pytest.fixture
    def mock_database(self):
        return MockDatabase()

    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        manager1 = SessionManager()
        manager2 = SessionManager()

        assert manager1 is manager2

    def test_default_config(self, manager):
        """기본 설정 테스트"""
        assert isinstance(manager.config, SessionConfig)
        assert manager._sessions == {}

    def test_set_config(self, manager):
        """설정 업데이트 테스트"""
        custom_config = SessionConfig(timeout=120, pool_size=20)

        manager.set_config(custom_config)

        assert manager.config == custom_config

    @pytest.mark.asyncio
    async def test_create_session_without_database(self, manager):
        """데이터베이스 없이 세션 생성"""
        with patch("rfs.database.session.get_database", return_value=None):
            result = await manager.create_session()

            assert not result.is_success()
            assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_create_session_with_database(self, manager):
        """데이터베이스와 함께 세션 생성"""
        mock_db = MockDatabase()

        with patch("rfs.database.session.get_database", return_value=mock_db):
            with patch("rfs.database.session.SQLAlchemyDatabase") as mock_sqlalchemy:
                with patch("rfs.database.session.TortoiseDatabase") as mock_tortoise:
                    # SQLAlchemy 데이터베이스로 설정
                    type(mock_db).__name__ = "SQLAlchemyDatabase"

                    result = await manager.create_session()

                    assert result.is_success()
                    session = result.unwrap()
                    assert isinstance(session, SQLAlchemySession)
                    assert session.session_id in manager._sessions

    @pytest.mark.asyncio
    async def test_create_session_with_tortoise_database(self, manager):
        """Tortoise 데이터베이스로 세션 생성"""
        mock_db = MockDatabase()

        with patch("rfs.database.session.get_database", return_value=mock_db):
            with patch("rfs.database.session.SQLAlchemyDatabase") as mock_sqlalchemy:
                with patch("rfs.database.session.TortoiseDatabase") as mock_tortoise:
                    # Tortoise 데이터베이스로 설정
                    type(mock_db).__name__ = "TortoiseDatabase"

                    result = await manager.create_session()

                    assert result.is_success()
                    session = result.unwrap()
                    assert isinstance(session, TortoiseSession)

    @pytest.mark.asyncio
    async def test_create_session_unsupported_database(self, manager):
        """지원되지 않는 데이터베이스 타입"""
        mock_db = MockDatabase()
        type(mock_db).__name__ = "UnsupportedDatabase"

        with patch("rfs.database.session.get_database", return_value=mock_db):
            result = await manager.create_session()

            assert not result.is_success()
            assert "지원되지 않는 데이터베이스 타입입니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_create_session_exception(self, manager):
        """세션 생성 중 예외"""
        with patch(
            "rfs.database.session.get_database", side_effect=Exception("Database error")
        ):
            result = await manager.create_session()

            assert not result.is_success()
            assert "세션 생성 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_close_session(self, manager):
        """세션 종료 테스트"""
        mock_session = Mock(spec=DatabaseSession)
        mock_session.session_id = 123
        mock_session.close = AsyncMock(return_value=Success(None))

        manager._sessions[123] = mock_session

        result = await manager.close_session(mock_session)

        assert result.is_success()
        mock_session.close.assert_called()

    @pytest.mark.asyncio
    async def test_close_session_failure(self, manager):
        """세션 종료 실패"""
        mock_session = Mock(spec=DatabaseSession)
        mock_session.close = AsyncMock(return_value=Failure("Close error"))

        result = await manager.close_session(mock_session)

        assert not result.is_success()

    @pytest.mark.asyncio
    async def test_close_session_exception(self, manager):
        """세션 종료 중 예외"""
        mock_session = Mock(spec=DatabaseSession)
        mock_session.close = AsyncMock(side_effect=Exception("Close exception"))

        result = await manager.close_session(mock_session)

        assert not result.is_success()
        assert "세션 종료 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_close_all_sessions(self, manager):
        """모든 세션 종료"""
        # Mock 세션들 생성
        mock_session1 = Mock(spec=DatabaseSession)
        mock_session1.close = AsyncMock(return_value=Success(None))
        mock_session2 = Mock(spec=DatabaseSession)
        mock_session2.close = AsyncMock(return_value=Success(None))

        manager._sessions = {1: mock_session1, 2: mock_session2}

        result = await manager.close_all_sessions()

        assert result.is_success()
        mock_session1.close.assert_called()
        mock_session2.close.assert_called()

    @pytest.mark.asyncio
    async def test_close_all_sessions_exception(self, manager):
        """모든 세션 종료 중 예외"""
        mock_session = Mock(spec=DatabaseSession)
        mock_session.close = AsyncMock(side_effect=Exception("Close error"))

        manager._sessions = {1: mock_session}

        result = await manager.close_all_sessions()

        assert not result.is_success()
        assert "세션 일괄 종료 실패" in result.unwrap_error()

    def test_get_current_session(self, manager):
        """현재 세션 조회"""
        mock_session = Mock(spec=DatabaseSession)
        current_session.set(mock_session)

        session = manager.get_current_session()

        assert session == mock_session

        # 정리
        current_session.set(None)

    def test_get_current_transaction(self, manager):
        """현재 트랜잭션 조회"""
        mock_transaction = Mock(spec=DatabaseTransaction)
        current_transaction.set(mock_transaction)

        transaction = manager.get_current_transaction()

        assert transaction == mock_transaction

        # 정리
        current_transaction.set(None)


class TestGlobalFunctions:
    """전역 함수들 테스트"""

    def test_get_session_manager_singleton(self):
        """get_session_manager 싱글톤 테스트"""
        manager1 = get_session_manager()
        manager2 = get_session_manager()

        assert manager1 is manager2
        assert isinstance(manager1, SessionManager)

    @pytest.mark.asyncio
    async def test_create_session_function(self):
        """create_session 전역 함수 테스트"""
        mock_db = MockDatabase()

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock(spec=SessionManager)
            mock_manager.create_session = AsyncMock(return_value=Success(Mock()))
            mock_get_manager.return_value = mock_manager

            result = await create_session(mock_db)

            assert result.is_success()
            mock_manager.create_session.assert_called_with(mock_db)

    def test_get_session_function(self):
        """get_session 전역 함수 테스트"""
        mock_session = Mock(spec=DatabaseSession)
        current_session.set(mock_session)

        session = get_session()

        assert session == mock_session

        # 정리
        current_session.set(None)

    def test_get_current_transaction_function(self):
        """get_current_transaction 전역 함수 테스트"""
        mock_transaction = Mock(spec=DatabaseTransaction)
        current_transaction.set(mock_transaction)

        transaction = get_current_transaction()

        assert transaction == mock_transaction

        # 정리
        current_transaction.set(None)


class TestContextManagers:
    """컨텍스트 매니저 테스트"""

    @pytest.mark.asyncio
    async def test_session_scope(self):
        """session_scope 컨텍스트 매니저 테스트"""
        mock_db = MockDatabase()

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock(spec=SessionManager)
            mock_session = Mock(spec=DatabaseSession)
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_manager.close_session = AsyncMock(return_value=Success(None))
            mock_get_manager.return_value = mock_manager

            async with session_scope(mock_db) as session:
                assert session == mock_session

            mock_manager.create_session.assert_called_with(mock_db)
            mock_manager.close_session.assert_called_with(mock_session)

    @pytest.mark.asyncio
    async def test_session_scope_with_config(self):
        """config가 있는 session_scope 테스트"""
        custom_config = SessionConfig(timeout=120)

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock(spec=SessionManager)
            mock_session = Mock(spec=DatabaseSession)
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_manager.close_session = AsyncMock(return_value=Success(None))
            mock_manager.set_config = Mock()
            mock_get_manager.return_value = mock_manager

            async with session_scope(config=custom_config) as session:
                pass

            mock_manager.set_config.assert_called_with(custom_config)

    @pytest.mark.asyncio
    async def test_session_scope_creation_failure(self):
        """session_scope 세션 생성 실패"""
        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock(spec=SessionManager)
            mock_manager.create_session = AsyncMock(
                return_value=Failure("Creation failed")
            )
            mock_get_manager.return_value = mock_manager

            with pytest.raises(Exception, match="세션 생성 실패"):
                async with session_scope():
                    pass

    @pytest.mark.asyncio
    async def test_transaction_scope_with_existing_session(self):
        """기존 세션과 함께 transaction_scope 테스트"""
        mock_session = Mock(spec=DatabaseSession)

        async with transaction_scope(mock_session) as transaction:
            assert isinstance(transaction, DatabaseTransaction)
            assert transaction.session == mock_session

    @pytest.mark.asyncio
    async def test_transaction_scope_without_session(self):
        """세션 없이 transaction_scope 테스트 (새 세션 생성)"""
        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock(spec=SessionManager)
            mock_session = Mock(spec=DatabaseSession)
            mock_session.begin = AsyncMock(return_value=Success(None))
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_manager.close_session = AsyncMock(return_value=Success(None))
            mock_get_manager.return_value = mock_manager

            async with transaction_scope() as transaction:
                assert isinstance(transaction, DatabaseTransaction)

            mock_manager.create_session.assert_called()
            mock_session.begin.assert_called()
            mock_manager.close_session.assert_called_with(mock_session)

    @pytest.mark.asyncio
    async def test_transaction_scope_session_creation_failure(self):
        """transaction_scope 세션 생성 실패"""
        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock(spec=SessionManager)
            mock_manager.create_session = AsyncMock(
                return_value=Failure("Session creation failed")
            )
            mock_get_manager.return_value = mock_manager

            with pytest.raises(Exception, match="세션 생성 실패"):
                async with transaction_scope():
                    pass

    @pytest.mark.asyncio
    async def test_transaction_scope_begin_failure(self):
        """transaction_scope 세션 시작 실패"""
        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock(spec=SessionManager)
            mock_session = Mock(spec=DatabaseSession)
            mock_session.begin = AsyncMock(return_value=Failure("Begin failed"))
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_get_manager.return_value = mock_manager

            with pytest.raises(Exception, match="세션 시작 실패"):
                async with transaction_scope():
                    pass


class TestDecorators:
    """데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_with_session_decorator(self):
        """with_session 데코레이터 테스트"""
        with patch("rfs.database.session.session_scope") as mock_scope:
            mock_session = Mock(spec=DatabaseSession)
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock()

            @with_session
            async def test_func(session=None):
                assert session == mock_session
                return "success"

            result = await test_func()
            assert result == "success"

    @pytest.mark.asyncio
    async def test_with_session_decorator_with_database(self):
        """데이터베이스가 있는 with_session 데코레이터"""
        mock_db = MockDatabase()

        with patch("rfs.database.session.session_scope") as mock_scope:
            mock_session = Mock(spec=DatabaseSession)
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock()

            @with_session(database=mock_db)
            async def test_func(session=None):
                return session

            result = await test_func()
            assert result == mock_session
            mock_scope.assert_called_with(mock_db, None)

    def test_with_session_sync_function_error(self):
        """with_session 동기 함수 에러"""
        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):

            @with_session
            def sync_func():
                pass

            sync_func()

    @pytest.mark.asyncio
    async def test_with_transaction_decorator(self):
        """with_transaction 데코레이터 테스트"""
        with patch("rfs.database.session.transaction_scope") as mock_scope:
            mock_transaction = Mock(spec=DatabaseTransaction)
            mock_scope.return_value.__aenter__ = AsyncMock(
                return_value=mock_transaction
            )
            mock_scope.return_value.__aexit__ = AsyncMock()

            @with_transaction
            async def test_func(transaction=None):
                assert transaction == mock_transaction
                return "success"

            result = await test_func()
            assert result == "success"

    @pytest.mark.asyncio
    async def test_with_transaction_decorator_with_session(self):
        """세션이 있는 with_transaction 데코레이터"""
        mock_session = Mock(spec=DatabaseSession)

        with patch("rfs.database.session.transaction_scope") as mock_scope:
            mock_transaction = Mock(spec=DatabaseTransaction)
            mock_scope.return_value.__aenter__ = AsyncMock(
                return_value=mock_transaction
            )
            mock_scope.return_value.__aexit__ = AsyncMock()

            @with_transaction(session=mock_session)
            async def test_func(transaction=None):
                return transaction

            result = await test_func()
            assert result == mock_transaction
            mock_scope.assert_called_with(mock_session)

    def test_with_transaction_sync_function_error(self):
        """with_transaction 동기 함수 에러"""
        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):

            @with_transaction
            def sync_func():
                pass

            sync_func()


class TestSessionContextManager:
    """DatabaseSession 컨텍스트 매니저 테스트"""

    @pytest.fixture
    def mock_database(self):
        return MockDatabase()

    @pytest.mark.asyncio
    async def test_session_context_manager_success(self, mock_database):
        """세션 컨텍스트 매니저 성공 시나리오"""
        session = SQLAlchemySession(mock_database)

        async with session as s:
            assert s == session
            assert current_session.get() == session

        # 컨텍스트 종료 후 정리됨
        assert current_session.get() is None

    @pytest.mark.asyncio
    async def test_session_context_manager_exception(self, mock_database):
        """세션 컨텍스트 매니저 예외 시나리오"""
        session = SQLAlchemySession(mock_database)

        try:
            async with session:
                raise Exception("Test exception")
        except Exception:
            pass

        # 예외 발생해도 정리됨
        assert current_session.get() is None

    @pytest.mark.asyncio
    async def test_session_context_manager_begin_failure(self, mock_database):
        """세션 컨텍스트 매니저 시작 실패"""
        session = SQLAlchemySession(mock_database)
        session.database.create_session = AsyncMock(
            side_effect=Exception("Begin error")
        )

        with pytest.raises(Exception, match="세션 시작 실패"):
            async with session:
                pass
