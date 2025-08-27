"""
RFS Database Session Missing Coverage Tests
session.py 모듈의 누락된 라인들에 대한 집중 테스트
Missing lines: 192, 214-215, 221, 227-228, 234, 240-241, 247-260, 283-284, 323, 360, 362, 367-369, 400-401, 499
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestMissingCoverageLines:
    """누락된 커버리지 라인들에 대한 집중 테스트"""

    @pytest.mark.asyncio
    async def test_tortoise_session_begin_already_active_line_192(self):
        """Line 192: Tortoise begin에서 이미 활성화된 경우"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True  # 이미 활성화

        result = await session.begin()

        assert result.is_success()
        # create_session이 호출되지 않아야 함
        mock_database.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_tortoise_session_commit_exception_lines_214_215(self):
        """Lines 214-215: Tortoise commit 예외 처리"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        # commit에서 예외 발생하도록 mock 설정 - 실제로는 Tortoise는 자동 커밋이지만
        # 예외가 발생할 수 있는 상황을 시뮬레이션
        with patch("rfs.database.session.logger") as mock_logger:
            mock_logger.debug.side_effect = Exception("Logger error")

            result = await session.commit()

            assert result.is_failure()
            assert "커밋 실패: Logger error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_session_rollback_not_active_line_221(self):
        """Line 221: Tortoise rollback에서 비활성화 상태"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = False  # 비활성화 상태

        result = await session.rollback()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_tortoise_session_rollback_exception_lines_227_228(self):
        """Lines 227-228: Tortoise rollback 예외 처리"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        # rollback에서 예외 발생하도록 설정
        with patch("rfs.database.session.logger") as mock_logger:
            mock_logger.debug.side_effect = Exception("Logger error")

            result = await session.rollback()

            assert result.is_failure()
            assert "롤백 실패: Logger error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_session_close_not_active_line_234(self):
        """Line 234: Tortoise close에서 비활성화 상태"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = False  # 비활성화 상태

        result = await session.close()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_tortoise_session_close_exception_lines_240_241(self):
        """Lines 240-241: Tortoise close 예외 처리"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        # close에서 예외 발생하도록 설정
        with patch("rfs.database.session.logger") as mock_logger:
            mock_logger.debug.side_effect = Exception("Logger error")

            result = await session.close()

            assert result.is_failure()
            assert "세션 종료 실패: Logger error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_session_execute_not_active_line_249(self):
        """Line 249: Tortoise execute에서 세션 비활성화"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = False  # 비활성화 상태

        result = await session.execute("SELECT 1")

        assert result.is_failure()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_session_execute_with_tortoise_connections_lines_252_260(
        self,
    ):
        """Lines 252-260: Tortoise execute 성공 및 예외"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        # 성공 케이스
        mock_connection = Mock()
        mock_result = [{"id": 1, "name": "test"}]
        mock_connection.execute_query = AsyncMock(return_value=mock_result)

        with patch("tortoise.connections") as mock_connections:
            mock_connections.get.return_value = mock_connection

            result = await session.execute("SELECT * FROM users", {"param": "value"})

            assert result.is_success()
            assert result.unwrap() == mock_result
            mock_connections.get.assert_called_once_with("default")
            mock_connection.execute_query.assert_called_once_with(
                "SELECT * FROM users", {"param": "value"}
            )

    @pytest.mark.asyncio
    async def test_tortoise_session_execute_exception_lines_259_260(self):
        """Lines 259-260: Tortoise execute 예외 처리"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = True

        # 예외 발생 케이스
        with patch("tortoise.connections") as mock_connections:
            mock_connections.get.side_effect = Exception("Connection failed")

            result = await session.execute("SELECT 1")

            assert result.is_failure()
            assert "쿼리 실행 실패: Connection failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_database_transaction_begin_exception_lines_283_284(self):
        """Lines 283-284: Transaction begin 예외 처리"""
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.is_active = True

        transaction = DatabaseTransaction(mock_session)

        # begin 중 예외 발생 시뮬레이션
        with patch("rfs.database.session.current_transaction") as mock_current:
            mock_current.set.side_effect = Exception("Context error")

            result = await transaction.begin()

            assert result.is_failure()
            assert "트랜잭션 시작 실패: Context error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_database_transaction_context_manager_begin_exception_line_323(self):
        """Line 323: Transaction context manager begin 예외"""
        from rfs.core.result import Failure
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        mock_session.is_active = True

        transaction = DatabaseTransaction(mock_session)

        # begin이 실패하도록 설정
        with patch.object(transaction, "begin", new_callable=AsyncMock) as mock_begin:
            mock_begin.return_value = Failure("Begin failed")

            with pytest.raises(Exception, match="트랜잭션 시작 실패: Begin failed"):
                async with transaction:
                    pass

    @pytest.mark.asyncio
    async def test_session_manager_create_session_type_name_line_360(self):
        """Line 360: SessionManager의 SQLAlchemy 타입 체크"""
        from rfs.database.base import Database
        from rfs.database.session import SessionManager

        manager = SessionManager()
        mock_database = Mock(spec=Database)

        # SQLAlchemyDatabase 타입으로 설정
        type(mock_database).__name__ = "SQLAlchemyDatabase"

        with patch("rfs.database.session.get_database", return_value=mock_database):
            with patch("rfs.database.session.SQLAlchemySession") as MockSession:
                mock_session = Mock()
                mock_session.session_id = 12345
                MockSession.return_value = mock_session

                result = await manager.create_session()

                assert result.is_success()
                assert result.unwrap() == mock_session
                MockSession.assert_called_once_with(mock_database, manager.config)

    @pytest.mark.asyncio
    async def test_session_manager_create_session_tortoise_type_line_362(self):
        """Line 362: SessionManager의 Tortoise 타입 체크"""
        from rfs.database.base import Database
        from rfs.database.session import SessionManager

        manager = SessionManager()
        mock_database = Mock(spec=Database)

        # TortoiseDatabase 타입으로 설정
        type(mock_database).__name__ = "TortoiseDatabase"

        with patch("rfs.database.session.get_database", return_value=mock_database):
            with patch("rfs.database.session.TortoiseSession") as MockSession:
                mock_session = Mock()
                mock_session.session_id = 54321
                MockSession.return_value = mock_session

                result = await manager.create_session()

                assert result.is_success()
                assert result.unwrap() == mock_session
                MockSession.assert_called_once_with(mock_database, manager.config)

    @pytest.mark.asyncio
    async def test_session_manager_create_session_dict_update_line_367(self):
        """Line 367: SessionManager의 sessions dict 업데이트"""
        from rfs.database.base import Database
        from rfs.database.session import SessionManager

        manager = SessionManager()
        mock_database = Mock(spec=Database)
        type(mock_database).__name__ = "SQLAlchemyDatabase"

        # 기존 세션이 있는 상태에서 새 세션 추가
        existing_session = Mock()
        existing_session.session_id = 999
        manager._sessions = {999: existing_session}

        with patch("rfs.database.session.get_database", return_value=mock_database):
            with patch("rfs.database.session.SQLAlchemySession") as MockSession:
                mock_session = Mock()
                mock_session.session_id = 12345
                MockSession.return_value = mock_session

                result = await manager.create_session()

                assert result.is_success()
                # dict spread 연산 테스트
                assert 999 in manager._sessions
                assert 12345 in manager._sessions
                assert manager._sessions[12345] == mock_session

    @pytest.mark.asyncio
    async def test_session_manager_create_session_exception_lines_371_372(self):
        """Lines 371-372: SessionManager create_session 예외 처리"""
        from rfs.database.session import SessionManager

        manager = SessionManager()

        # get_database에서 예외 발생
        with patch(
            "rfs.database.session.get_database", side_effect=Exception("Database error")
        ):
            result = await manager.create_session()

            assert result.is_failure()
            assert "세션 생성 실패: Database error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_session_manager_close_all_sessions_exception_lines_400_401(self):
        """Lines 400-401: SessionManager close_all_sessions 예외 처리"""
        from rfs.core.result import Success
        from rfs.database.session import DatabaseSession, SessionManager

        manager = SessionManager()

        # 세션 생성
        mock_session = Mock(spec=DatabaseSession)
        mock_session.session_id = 12345
        mock_session.close = AsyncMock(return_value=Success(None))
        manager._sessions[12345] = mock_session

        # close_session에서 예외 발생하도록 설정
        with patch.object(
            manager, "close_session", side_effect=Exception("Close error")
        ):
            result = await manager.close_all_sessions()

            assert result.is_failure()
            assert "세션 일괄 종료 실패: Close error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_transaction_scope_rollback_on_exception_line_499(self):
        """Line 499: transaction_scope __aexit__ rollback on exception"""
        from rfs.core.result import Success
        from rfs.database.session import (
            DatabaseSession,
            DatabaseTransaction,
            transaction_scope,
        )

        mock_session = Mock(spec=DatabaseSession)
        mock_transaction = Mock(spec=DatabaseTransaction)
        mock_transaction.rollback = AsyncMock(return_value=Success(None))
        mock_transaction.commit = AsyncMock(return_value=Success(None))

        # transaction_scope 객체 생성
        scope = transaction_scope(mock_session)

        # transaction과 session 설정
        scope.transaction = mock_transaction
        scope.session = mock_session
        scope._created_session = False

        # 예외가 있는 경우 __aexit__ 호출 (exc_type이 None이 아닌 경우 → rollback)
        await scope.__aexit__(ValueError, ValueError("Test exception"), None)

        # rollback이 호출되었는지 확인 (line 499)
        mock_transaction.rollback.assert_called_once()
        mock_transaction.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_rollback_not_active_line_145(self):
        """Line 145: SQLAlchemy rollback에서 비활성화 상태 (추가 확인)"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)
        session._is_active = False  # 비활성화
        session._session = None

        result = await session.rollback()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_execute_no_session_line_175(self):
        """SQLAlchemy execute에서 session이 None인 경우"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)
        session._is_active = True  # 활성화되어 있지만
        session._session = None  # 세션 객체가 None

        result = await session.execute("SELECT 1")

        assert result.is_failure()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_execute_exception_lines_181_182(self):
        """Lines 181-182: SQLAlchemy execute 예외 처리"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()
        mock_session_obj.execute = AsyncMock(side_effect=Exception("Query failed"))

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.execute("SELECT 1", {"param": "value"})

        assert result.is_failure()
        assert "쿼리 실행 실패: Query failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_session_begin_exception_lines_201_202(self):
        """Lines 201-202: Tortoise begin 예외 처리"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        mock_database.create_session = AsyncMock(
            side_effect=Exception("Session creation failed")
        )

        session = TortoiseSession(mock_database)

        result = await session.begin()

        assert result.is_failure()
        assert "세션 시작 실패: Session creation failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_session_close_exception_lines_167_168(self):
        """Lines 167-168: SQLAlchemy close 예외 처리"""
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        mock_session_obj = AsyncMock()
        mock_session_obj.close = AsyncMock(side_effect=Exception("Close failed"))

        session = SQLAlchemySession(mock_database)
        session._is_active = True
        session._session = mock_session_obj

        result = await session.close()

        assert result.is_failure()
        assert "세션 종료 실패: Close failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_database_session_context_manager_begin_exception_lines_89_95(self):
        """Lines 89-95: DatabaseSession context manager begin 예외"""
        from rfs.core.result import Failure
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)

        # begin이 실패하도록 설정
        with patch.object(session, "begin", new_callable=AsyncMock) as mock_begin:
            mock_begin.return_value = Failure("Begin failed")

            with pytest.raises(Exception, match="세션 시작 실패: Begin failed"):
                async with session:
                    pass

    @pytest.mark.asyncio
    async def test_database_session_context_manager_exception_cleanup_lines_99_106(
        self,
    ):
        """Lines 99-106: DatabaseSession context manager 예외 시 정리"""
        from rfs.core.result import Success
        from rfs.database.base import Database
        from rfs.database.session import SQLAlchemySession

        mock_database = Mock(spec=Database)
        session = SQLAlchemySession(mock_database)

        # Mocks for session operations
        session.begin = AsyncMock(return_value=Success(None))
        session.commit = AsyncMock(return_value=Success(None))
        session.rollback = AsyncMock(return_value=Success(None))
        session.close = AsyncMock(return_value=Success(None))

        # 예외 발생 상황에서의 rollback과 close 호출 확인
        try:
            async with session:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # 예외 발생으로 rollback이 호출되어야 함
        session.rollback.assert_called_once()
        session.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
