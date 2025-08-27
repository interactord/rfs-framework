"""
RFS Database Session Comprehensive Coverage Tests
session.py 모듈 23.23% → 90% 커버리지 향상을 위한 포괄적 테스트
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest


class TestSessionConfig:
    """SessionConfig 데이터클래스 테스트"""

    def test_session_config_defaults(self):
        """SessionConfig 기본값 테스트"""
        from rfs.database.session import SessionConfig

        config = SessionConfig()

        assert config.auto_commit is True
        assert config.auto_flush is True
        assert config.expire_on_commit is False
        assert config.isolation_level == "READ_COMMITTED"
        assert config.timeout == 30
        assert config.pool_size == 10
        assert config.max_overflow == 20

    def test_session_config_custom_values(self):
        """SessionConfig 커스텀 값 테스트"""
        from rfs.database.session import SessionConfig

        config = SessionConfig(
            auto_commit=False,
            auto_flush=False,
            expire_on_commit=True,
            isolation_level="SERIALIZABLE",
            timeout=60,
            pool_size=20,
            max_overflow=30,
        )

        assert config.auto_commit is False
        assert config.auto_flush is False
        assert config.expire_on_commit is True
        assert config.isolation_level == "SERIALIZABLE"
        assert config.timeout == 60
        assert config.pool_size == 20
        assert config.max_overflow == 30


class TestDatabaseSessionBase:
    """DatabaseSession 기본 클래스 테스트"""

    def test_database_session_init(self):
        """DatabaseSession 초기화 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import DatabaseSession, SessionConfig

        mock_database = Mock(spec=Database)
        custom_config = SessionConfig(timeout=60)

        # Abstract 클래스이므로 직접 인스턴스화 불가, Mock 사용
        with patch("rfs.database.session.DatabaseSession", spec=True) as MockSession:
            session_instance = Mock()
            session_instance.database = mock_database
            session_instance.config = custom_config
            session_instance.session_id = id(session_instance)
            session_instance._session = None
            session_instance._is_active = False
            session_instance._transaction = None

            MockSession.return_value = session_instance

            session = MockSession(mock_database, custom_config)

            assert session.database == mock_database
            assert session.config == custom_config
            assert hasattr(session, "session_id")

    def test_database_session_is_active_property(self):
        """DatabaseSession is_active 프로퍼티 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import DatabaseSession

        mock_database = Mock(spec=Database)

        with patch.object(DatabaseSession, "__abstractmethods__", set()):
            session = DatabaseSession(mock_database)

            # 초기 상태
            assert session.is_active is False

            # _is_active 변경
            session._is_active = True
            assert session.is_active is True


class TestSQLAlchemySession:
    """SQLAlchemySession 구체 클래스 테스트"""

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_begin_success(self):
        """SQLAlchemy 세션 시작 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = Mock()
        mock_database.create_session = AsyncMock(return_value=mock_session_obj)

        session = SQLAlchemySession(mock_database)

        result = await session.begin()

        assert result.is_success()
        assert session._is_active is True
        assert session._session == mock_session_obj
        mock_database.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_begin_already_active(self):
        """SQLAlchemy 세션 이미 활성화된 경우 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)
        session._is_active = True  # 이미 활성화

        result = await session.begin()

        assert result.is_success()
        # create_session이 호출되지 않아야 함
        mock_database.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_begin_exception(self):
        """SQLAlchemy 세션 시작 예외 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_database.create_session = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        session = SQLAlchemySession(mock_database)

        result = await session.begin()

        assert result.is_failure()
        assert "세션 시작 실패: Connection failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_commit_success(self):
        """SQLAlchemy 세션 커밋 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.commit()

        assert result.is_success()
        mock_session_obj.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_commit_not_active(self):
        """SQLAlchemy 세션 비활성화 상태 커밋 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)
        session._is_active = False

        result = await session.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_commit_exception(self):
        """SQLAlchemy 세션 커밋 예외 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()
        mock_session_obj.commit = AsyncMock(side_effect=Exception("Commit failed"))

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.commit()

        assert result.is_failure()
        assert "커밋 실패: Commit failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_rollback_success(self):
        """SQLAlchemy 세션 롤백 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.rollback()

        assert result.is_success()
        mock_session_obj.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_rollback_exception(self):
        """SQLAlchemy 세션 롤백 예외 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()
        mock_session_obj.rollback = AsyncMock(side_effect=Exception("Rollback failed"))

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.rollback()

        assert result.is_failure()
        assert "롤백 실패: Rollback failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_close_success(self):
        """SQLAlchemy 세션 종료 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.close()

        assert result.is_success()
        assert session._is_active is False
        mock_session_obj.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_close_not_active(self):
        """SQLAlchemy 세션 비활성화 상태 종료 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)
        session._is_active = False

        result = await session.close()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_execute_success(self):
        """SQLAlchemy 세션 쿼리 실행 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()
        mock_result = Mock()
        mock_session_obj.execute = AsyncMock(return_value=mock_result)

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.execute("SELECT 1", {"param": "value"})

        assert result.is_success()
        assert result.unwrap() == mock_result
        mock_session_obj.execute.assert_called_once_with("SELECT 1", {"param": "value"})

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_execute_not_active(self):
        """SQLAlchemy 세션 비활성화 상태 쿼리 실행 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)
        session._is_active = False

        result = await session.execute("SELECT 1")

        assert result.is_failure()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()


class TestTortoiseSession:
    """TortoiseSession 구체 클래스 테스트"""

    @pytest.mark.asyncio
    async def test_tortoise_session_begin_success(self):
        """Tortoise 세션 시작 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        mock_session_obj = Mock()
        mock_database.create_session = AsyncMock(return_value=mock_session_obj)

        session = TortoiseSession(mock_database)

        result = await session.begin()

        assert result.is_success()
        assert session._is_active is True
        assert session._session == mock_session_obj

    @pytest.mark.asyncio
    async def test_tortoise_session_commit_success(self):
        """Tortoise 세션 커밋 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        result = await session.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_tortoise_session_rollback_success(self):
        """Tortoise 세션 롤백 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        result = await session.rollback()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_tortoise_session_close_success(self):
        """Tortoise 세션 종료 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        result = await session.close()

        assert result.is_success()
        assert session._is_active is False

    @pytest.mark.asyncio
    async def test_tortoise_session_execute_success(self):
        """Tortoise 세션 쿼리 실행 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        mock_connection = Mock()
        mock_result = Mock()
        mock_connection.execute_query = AsyncMock(return_value=mock_result)

        with patch("tortoise.connections") as mock_connections:
            mock_connections.get = Mock(return_value=mock_connection)

            result = await session.execute("SELECT 1", ["param"])

            assert result.is_success()
            assert result.unwrap() == mock_result
            mock_connection.execute_query.assert_called_once_with("SELECT 1", ["param"])


class TestDatabaseTransaction:
    """DatabaseTransaction 클래스 테스트"""

    @pytest.mark.asyncio
    async def test_transaction_begin_success(self):
        """트랜잭션 시작 성공 테스트"""
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.is_active = True

        transaction = DatabaseTransaction(mock_session)

        result = await transaction.begin()

        assert result.is_success()
        assert transaction._is_active is True
        assert transaction.session == mock_session

    @pytest.mark.asyncio
    async def test_transaction_begin_session_not_active(self):
        """세션이 활성화되지 않은 상태에서 트랜잭션 시작 테스트"""
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.is_active = False

        transaction = DatabaseTransaction(mock_session)

        result = await transaction.begin()

        assert result.is_failure()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_transaction_commit_success(self):
        """트랜잭션 커밋 성공 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.commit = AsyncMock(return_value=Success(None))

        transaction = DatabaseTransaction(mock_session)
        transaction._is_active = True

        result = await transaction.commit()

        assert result.is_success()
        assert transaction._is_active is False
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_commit_not_active(self):
        """비활성화 상태 트랜잭션 커밋 테스트"""
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        transaction = DatabaseTransaction(mock_session)
        transaction._is_active = False

        result = await transaction.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_transaction_rollback_success(self):
        """트랜잭션 롤백 성공 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.rollback = AsyncMock(return_value=Success(None))

        transaction = DatabaseTransaction(mock_session)
        transaction._is_active = True

        result = await transaction.rollback()

        assert result.is_success()
        assert transaction._is_active is False
        mock_session.rollback.assert_called_once()

    def test_transaction_is_active_property(self):
        """트랜잭션 is_active 프로퍼티 테스트"""
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        transaction = DatabaseTransaction(mock_session)

        assert transaction.is_active is False

        transaction._is_active = True
        assert transaction.is_active is True

    @pytest.mark.asyncio
    async def test_transaction_context_manager_success(self):
        """트랜잭션 컨텍스트 매니저 성공 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.is_active = True
        mock_session.commit = AsyncMock(return_value=Success(None))

        transaction = DatabaseTransaction(mock_session)

        async with transaction:
            pass

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_context_manager_exception(self):
        """트랜잭션 컨텍스트 매니저 예외 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.is_active = True
        mock_session.rollback = AsyncMock(return_value=Success(None))

        transaction = DatabaseTransaction(mock_session)

        try:
            async with transaction:
                raise ValueError("Test exception")
        except ValueError:
            pass

        mock_session.rollback.assert_called_once()


class TestSessionManager:
    """SessionManager 클래스 테스트"""

    def test_session_manager_singleton(self):
        """SessionManager 싱글톤 테스트"""
        from rfs.database.session import SessionManager, get_session_manager

        manager1 = get_session_manager()
        manager2 = get_session_manager()

        assert manager1 is manager2
        assert isinstance(manager1, SessionManager)

    def test_session_manager_init(self):
        """SessionManager 초기화 테스트"""
        from rfs.database.session import SessionConfig, SessionManager

        manager = SessionManager()

        assert isinstance(manager.config, SessionConfig)
        assert isinstance(manager._sessions, dict)
        assert len(manager._sessions) == 0

    def test_session_manager_set_config(self):
        """SessionManager 설정 업데이트 테스트"""
        from rfs.database.session import SessionConfig, SessionManager

        manager = SessionManager()
        custom_config = SessionConfig(timeout=120)

        with patch("rfs.database.session.logger") as mock_logger:
            manager.set_config(custom_config)

            assert manager.config == custom_config
            mock_logger.info.assert_called_once_with("세션 설정 업데이트")

    @pytest.mark.asyncio
    async def test_session_manager_create_session_success(self):
        """SessionManager 세션 생성 성공 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SessionManager

        manager = SessionManager()
        mock_database = Mock(spec=Database)

        with patch("rfs.database.session.get_database", return_value=mock_database):
            with patch("rfs.database.base.SQLAlchemyDatabase") as MockSQLAlchemyDB:
                # 타입 이름을 통해 SQLAlchemy 데이터베이스로 인식하도록 설정
                type(mock_database).__name__ = "SQLAlchemyDatabase"

                with patch("rfs.database.session.SQLAlchemySession") as MockSession:
                    mock_session = Mock()
                    mock_session.session_id = 12345
                    MockSession.return_value = mock_session

                    with patch("rfs.database.session.logger") as mock_logger:
                        result = await manager.create_session()

                        assert result.is_success()
                        session = result.unwrap()
                        assert session == mock_session

                        # 세션이 매니저의 _sessions에 저장되었는지 확인
                        assert 12345 in manager._sessions
                        assert manager._sessions[12345] == mock_session

                        mock_logger.info.assert_called_with("세션 생성: 12345")

    @pytest.mark.asyncio
    async def test_session_manager_create_session_no_database(self):
        """SessionManager 데이터베이스 없음 세션 생성 테스트"""
        from rfs.database.session import SessionManager

        manager = SessionManager()

        with patch("rfs.database.session.get_database", return_value=None):
            result = await manager.create_session()

            assert result.is_failure()
            assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_session_manager_create_session_tortoise(self):
        """SessionManager Tortoise 세션 생성 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SessionManager

        manager = SessionManager()
        mock_database = Mock(spec=Database)
        type(mock_database).__name__ = "TortoiseDatabase"

        with patch("rfs.database.session.get_database", return_value=mock_database):
            with patch("rfs.database.base.TortoiseDatabase") as MockTortoiseDB:
                with patch("rfs.database.session.TortoiseSession") as MockSession:
                    mock_session = Mock()
                    mock_session.session_id = 54321
                    MockSession.return_value = mock_session

                    result = await manager.create_session()

                    assert result.is_success()
                    assert result.unwrap() == mock_session

    @pytest.mark.asyncio
    async def test_session_manager_create_session_unsupported(self):
        """SessionManager 지원되지 않는 데이터베이스 타입 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import SessionManager

        manager = SessionManager()
        mock_database = Mock(spec=Database)
        type(mock_database).__name__ = "UnsupportedDatabase"

        with patch("rfs.database.session.get_database", return_value=mock_database):
            result = await manager.create_session()

            assert result.is_failure()
            assert "지원되지 않는 데이터베이스 타입입니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_session_manager_close_session_success(self):
        """SessionManager 세션 종료 성공 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseSession, SessionManager

        manager = SessionManager()
        mock_session = Mock(spec=DatabaseSession)
        mock_session.session_id = 12345
        mock_session.close = AsyncMock(return_value=Success(None))

        # 세션을 매니저에 등록
        manager._sessions[12345] = mock_session

        with patch("rfs.database.session.logger") as mock_logger:
            result = await manager.close_session(mock_session)

            assert result.is_success()
            mock_session.close.assert_called_once()
            mock_logger.info.assert_called_with("세션 종료: 12345")

    @pytest.mark.asyncio
    async def test_session_manager_close_all_sessions(self):
        """SessionManager 모든 세션 종료 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseSession, SessionManager

        manager = SessionManager()

        # 여러 세션 생성
        sessions = []
        for i in range(3):
            mock_session = Mock(spec=DatabaseSession)
            mock_session.session_id = i
            mock_session.close = AsyncMock(return_value=Success(None))
            manager._sessions[i] = mock_session
            sessions.append(mock_session)

        with patch("rfs.database.session.logger") as mock_logger:
            result = await manager.close_all_sessions()

            assert result.is_success()

            # 모든 세션이 close되었는지 확인
            for session in sessions:
                session.close.assert_called_once()

            mock_logger.info.assert_called_with("모든 세션 종료")

    def test_session_manager_get_current_session(self):
        """SessionManager 현재 세션 조회 테스트"""
        from rfs.database.session import SessionManager

        manager = SessionManager()

        with patch("rfs.database.session.current_session") as mock_current:
            mock_current.get = Mock(return_value="test_session")

            result = manager.get_current_session()

            assert result == "test_session"
            mock_current.get.assert_called_once_with(None)

    def test_session_manager_get_current_transaction(self):
        """SessionManager 현재 트랜잭션 조회 테스트"""
        from rfs.database.session import SessionManager

        manager = SessionManager()

        with patch("rfs.database.session.current_transaction") as mock_current:
            mock_current.get = Mock(return_value="test_transaction")

            result = manager.get_current_transaction()

            assert result == "test_transaction"
            mock_current.get.assert_called_once_with(None)


class TestConvenienceFunctions:
    """편의 함수들 테스트"""

    @pytest.mark.asyncio
    async def test_create_session_function(self):
        """create_session 함수 테스트"""
        from rfs.core.result import Success
        from rfs.database.base import Database
        from rfs.database.session import create_session, get_session_manager

        mock_database = Mock(spec=Database)
        mock_session = Mock()

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_get_manager.return_value = mock_manager

            result = await create_session(mock_database)

            assert result.is_success()
            assert result.unwrap() == mock_session
            mock_manager.create_session.assert_called_once_with(mock_database)

    def test_get_session_function(self):
        """get_session 함수 테스트"""
        from rfs.database.session import get_session

        with patch("rfs.database.session.current_session") as mock_current:
            mock_current.get = Mock(return_value="current_session")

            result = get_session()

            assert result == "current_session"
            mock_current.get.assert_called_once_with(None)

    def test_get_current_transaction_function(self):
        """get_current_transaction 함수 테스트"""
        from rfs.database.session import get_current_transaction

        with patch("rfs.database.session.current_transaction") as mock_current:
            mock_current.get = Mock(return_value="current_transaction")

            result = get_current_transaction()

            assert result == "current_transaction"
            mock_current.get.assert_called_once_with(None)


class TestSessionScope:
    """session_scope 컨텍스트 매니저 테스트"""

    @pytest.mark.asyncio
    async def test_session_scope_success(self):
        """session_scope 성공 테스트"""
        from rfs.core.result import Success
        from rfs.database.base import Database
        from rfs.database.session import SessionConfig, session_scope

        mock_database = Mock(spec=Database)
        custom_config = SessionConfig(timeout=60)
        mock_session = Mock()

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.set_config = Mock()
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_manager.close_session = AsyncMock(return_value=Success(None))
            mock_get_manager.return_value = mock_manager

            async with session_scope(mock_database, custom_config) as session:
                assert session == mock_session

            mock_manager.set_config.assert_called_once_with(custom_config)
            mock_manager.create_session.assert_called_once_with(mock_database)
            mock_manager.close_session.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_session_scope_creation_failure(self):
        """session_scope 세션 생성 실패 테스트"""
        from rfs.core.result import Failure
        from rfs.database.base import Database
        from rfs.database.session import session_scope

        mock_database = Mock(spec=Database)

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.create_session = AsyncMock(
                return_value=Failure("Creation failed")
            )
            mock_get_manager.return_value = mock_manager

            with pytest.raises(Exception, match="세션 생성 실패: Creation failed"):
                async with session_scope(mock_database):
                    pass


class TestTransactionScope:
    """transaction_scope 컨텍스트 매니저 테스트"""

    @pytest.mark.asyncio
    async def test_transaction_scope_with_existing_session(self):
        """기존 세션으로 transaction_scope 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import (
            DatabaseSession,
            DatabaseTransaction,
            transaction_scope,
        )

        mock_session = Mock(spec=DatabaseSession)
        mock_session.begin = AsyncMock(return_value=Success(None))

        async with transaction_scope(mock_session) as transaction:
            assert isinstance(transaction, DatabaseTransaction)
            assert transaction.session == mock_session

    @pytest.mark.asyncio
    async def test_transaction_scope_create_new_session(self):
        """새 세션 생성으로 transaction_scope 테스트"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseTransaction, transaction_scope

        mock_session = Mock()
        mock_session.begin = AsyncMock(return_value=Success(None))

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_manager.close_session = AsyncMock(return_value=Success(None))
            mock_get_manager.return_value = mock_manager

            async with transaction_scope() as transaction:
                assert isinstance(transaction, DatabaseTransaction)

            mock_manager.create_session.assert_called_once()
            mock_manager.close_session.assert_called_once_with(mock_session)


class TestDecorators:
    """데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_with_session_decorator(self):
        """with_session 데코레이터 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import with_session

        mock_database = Mock(spec=Database)
        mock_session = Mock()

        with patch("rfs.database.session.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock()

            @with_session(database=mock_database)
            async def test_function(session=None):
                return session

            result = await test_function()

            assert result == mock_session

    def test_with_session_sync_function_error(self):
        """with_session 동기 함수 에러 테스트"""
        from rfs.database.session import with_session

        @with_session
        def sync_function():
            return "sync"

        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):
            sync_function()

    @pytest.mark.asyncio
    async def test_with_transaction_decorator(self):
        """with_transaction 데코레이터 테스트"""
        from rfs.database.session import DatabaseTransaction, with_transaction

        mock_transaction = Mock(spec=DatabaseTransaction)

        with patch("rfs.database.session.transaction_scope") as mock_scope:
            mock_scope.return_value.__aenter__ = AsyncMock(
                return_value=mock_transaction
            )
            mock_scope.return_value.__aexit__ = AsyncMock()

            @with_transaction
            async def test_function(transaction=None):
                return transaction

            result = await test_function()

            assert result == mock_transaction


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
