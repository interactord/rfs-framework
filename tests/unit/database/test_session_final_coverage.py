"""
RFS Database Session Final Coverage Tests
session.py 모듈의 마지막 누락 라인들: 101, 208, 303, 479, 487, 548-552, 555
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestFinalCoverage:
    """마지막 누락된 커버리지 라인들에 대한 테스트"""

    @pytest.mark.asyncio
    async def test_database_session_context_manager_commit_success_line_101(self):
        """Line 101: DatabaseSession context manager 정상 종료시 commit"""
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

        # 정상 종료 (예외 없음) - commit 경로
        async with session:
            # 정상적으로 작업 수행
            pass

        # 정상 종료로 commit이 호출되어야 함 (line 101)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_tortoise_session_commit_not_active_line_208(self):
        """Line 208: Tortoise commit에서 비활성화 상태"""
        from rfs.database.base import Database
        from rfs.database.session import TortoiseSession

        mock_database = Mock(spec=Database)
        session = TortoiseSession(mock_database)
        session._is_active = False  # 비활성화 상태

        result = await session.commit()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_database_transaction_rollback_not_active_line_303(self):
        """Line 303: Transaction rollback에서 비활성화 상태"""
        from rfs.database.session import DatabaseSession, DatabaseTransaction

        mock_session = Mock(spec=DatabaseSession)
        transaction = DatabaseTransaction(mock_session)
        transaction._is_active = False  # 비활성화 상태

        result = await transaction.rollback()

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_transaction_scope_session_creation_exception_line_479(self):
        """Line 479: transaction_scope에서 세션 생성 실패"""
        from rfs.core.result import Failure
        from rfs.database.session import transaction_scope

        # 세션이 없는 상태에서 transaction_scope 사용
        scope = transaction_scope(None)

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.create_session = AsyncMock(
                return_value=Failure("Session creation failed")
            )
            mock_get_manager.return_value = mock_manager

            with pytest.raises(
                Exception, match="세션 생성 실패: Session creation failed"
            ):
                async with scope:
                    pass

    @pytest.mark.asyncio
    async def test_transaction_scope_session_begin_exception_line_487(self):
        """Line 487: transaction_scope에서 세션 begin 실패"""
        from rfs.core.result import Failure, Success
        from rfs.database.session import DatabaseSession, transaction_scope

        # 세션이 없는 상태에서 transaction_scope 사용
        scope = transaction_scope(None)

        mock_session = Mock(spec=DatabaseSession)
        mock_session.begin = AsyncMock(return_value=Failure("Begin failed"))

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_get_manager.return_value = mock_manager

            with pytest.raises(Exception, match="세션 시작 실패: Begin failed"):
                async with scope:
                    pass

    def test_with_transaction_sync_function_lines_548_552(self):
        """Lines 548-552: with_transaction 동기 함수 에러"""
        from rfs.database.session import with_transaction

        @with_transaction
        def sync_function():
            return "sync result"

        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):
            sync_function()

    def test_with_transaction_decorator_return_line_555(self):
        """Line 555: with_transaction 데코레이터 함수 반환"""
        from rfs.database.session import with_transaction

        # 데코레이터를 함수 없이 호출하는 경우
        decorator = with_transaction()

        @decorator
        async def test_function(transaction=None):
            return "decorated"

        # 데코레이터가 함수를 반환하는지 확인
        assert asyncio.iscoroutinefunction(test_function)

    @pytest.mark.asyncio
    async def test_session_scope_config_setting(self):
        """session_scope에서 config 설정"""
        from rfs.core.result import Success
        from rfs.database.base import Database
        from rfs.database.session import SessionConfig, session_scope

        mock_database = Mock(spec=Database)
        custom_config = SessionConfig(timeout=120)
        mock_session = Mock()

        with patch("rfs.database.session.get_session_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.set_config = Mock()
            mock_manager.create_session = AsyncMock(return_value=Success(mock_session))
            mock_manager.close_session = AsyncMock(return_value=Success(None))
            mock_get_manager.return_value = mock_manager

            async with session_scope(mock_database, custom_config) as session:
                assert session == mock_session

            # config가 설정되었는지 확인
            mock_manager.set_config.assert_called_once_with(custom_config)

    @pytest.mark.asyncio
    async def test_additional_missing_lines(self):
        """추가 누락 라인 테스트"""
        from rfs.database.base import Database
        from rfs.database.session import DatabaseSession, SessionConfig

        # SessionConfig의 기본값이 없을 때 처리
        mock_database = Mock(spec=Database)

        # Abstract method 테스트는 이미 다른 테스트에서 커버됨
        # 여기서는 DatabaseSession 초기화 시 config가 None인 경우를 테스트
        with patch.object(DatabaseSession, "__abstractmethods__", set()):
            session = DatabaseSession(mock_database, None)
            assert isinstance(session.config, SessionConfig)
            assert session.config.auto_commit is True

    def test_with_session_decorator_without_function(self):
        """with_session 데코레이터를 함수 없이 호출"""
        from rfs.database.session import with_session

        decorator = with_session()

        @decorator
        async def test_function(session=None):
            return "decorated"

        assert asyncio.iscoroutinefunction(test_function)

    def test_with_session_sync_function_error(self):
        """with_session 동기 함수 에러"""
        from rfs.database.session import with_session

        @with_session
        def sync_function():
            return "sync"

        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):
            sync_function()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
