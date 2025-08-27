"""
Database Session 비즈니스 예외 시나리오 기반 테스트

실제 운영 환경에서 발생할 수 있는 다양한 예외 상황들을 시뮬레이션하여
견고한 예외 처리를 테스트합니다.
"""

import asyncio
import os
import sqlite3
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# 실제와 유사한 Exception 클래스들 정의
class DatabaseConnectionError(Exception):
    """데이터베이스 연결 실패"""

    pass


class TransactionError(Exception):
    """트랜잭션 처리 오류"""

    pass


class SessionTimeoutError(Exception):
    """세션 타임아웃"""

    pass


class DeadlockError(Exception):
    """데드락 발생"""

    pass


class ConstraintViolationError(Exception):
    """제약 조건 위반"""

    pass


class InsufficientStorageError(Exception):
    """디스크 공간 부족"""

    pass


@pytest.fixture
def mock_dependencies():
    """실제와 유사한 의존성 Mock 생성"""
    import sys

    # Result 클래스들 - 실제 구현과 동일
    class Success:
        def __init__(self, value):
            self._value = value

        def is_success(self):
            return True

        def unwrap(self):
            return self._value

        def unwrap_error(self):
            raise ValueError("Success에서 error를 unwrap할 수 없습니다")

    class Failure:
        def __init__(self, error):
            self._error = error

        def is_success(self):
            return False

        def unwrap(self):
            raise ValueError("Failure에서 value를 unwrap할 수 없습니다")

        def unwrap_error(self):
            return self._error

    # Mock modules 설정
    mock_result = Mock()
    mock_result.Success = Success
    mock_result.Failure = Failure
    mock_result.Result = Mock()

    mock_logging = Mock()
    mock_logger = Mock()
    mock_logging.get_logger.return_value = mock_logger

    mock_singleton = Mock()
    mock_singleton.SingletonMeta = type

    mock_base = Mock()
    mock_base.Database = Mock()
    mock_base.get_database = Mock()
    mock_base.SQLAlchemyDatabase = Mock()
    mock_base.TortoiseDatabase = Mock()

    mock_models = Mock()
    mock_models.BaseModel = Mock()

    # sys.modules에 등록
    modules_to_mock = {
        "rfs.core.result": mock_result,
        "rfs.core.enhanced_logging": mock_logging,
        "rfs.core.singleton": mock_singleton,
        "rfs.database.base": mock_base,
        "rfs.database.models_refactored": mock_models,
    }

    original_modules = {}
    for name, module in modules_to_mock.items():
        if name in sys.modules:
            original_modules[name] = sys.modules[name]
        sys.modules[name] = module

    # session 모듈 import
    try:
        from rfs.database.session import (
            DatabaseSession,
            DatabaseTransaction,
            SessionConfig,
            SessionManager,
            SQLAlchemySession,
            TortoiseSession,
            get_session_manager,
            session_scope,
            transaction_scope,
            with_session,
            with_transaction,
        )

        yield {
            "SessionConfig": SessionConfig,
            "SQLAlchemySession": SQLAlchemySession,
            "TortoiseSession": TortoiseSession,
            "DatabaseTransaction": DatabaseTransaction,
            "SessionManager": SessionManager,
            "get_session_manager": get_session_manager,
            "session_scope": session_scope,
            "transaction_scope": transaction_scope,
            "with_session": with_session,
            "with_transaction": with_transaction,
            "Success": Success,
            "Failure": Failure,
            "logger": mock_logger,
        }
    finally:
        # 원래 모듈들 복원
        for name in modules_to_mock:
            if name in original_modules:
                sys.modules[name] = original_modules[name]
            else:
                sys.modules.pop(name, None)


class TestDatabaseConnectionFailures:
    """데이터베이스 연결 실패 시나리오"""

    @pytest.mark.asyncio
    async def test_connection_timeout_during_session_creation(self, mock_dependencies):
        """세션 생성 시 연결 타임아웃"""
        classes = mock_dependencies

        # 연결 타임아웃 시뮬레이션
        mock_db = Mock()
        mock_db.create_session = AsyncMock(
            side_effect=asyncio.TimeoutError("Connection timeout after 30s")
        )

        session = classes["SQLAlchemySession"](mock_db)

        result = await session.begin()
        assert not result.is_success()
        assert "Connection timeout" in result.unwrap_error()
        assert not session._is_active

    @pytest.mark.asyncio
    async def test_database_server_unavailable(self, mock_dependencies):
        """DB 서버 다운 상황"""
        classes = mock_dependencies

        mock_db = Mock()
        mock_db.create_session = AsyncMock(
            side_effect=DatabaseConnectionError(
                "FATAL: database system is shutting down"
            )
        )

        session = classes["SQLAlchemySession"](mock_db)

        result = await session.begin()
        assert not result.is_success()
        assert "shutting down" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_connection_pool_exhausted(self, mock_dependencies):
        """커넥션 풀 고갈"""
        classes = mock_dependencies

        mock_db = Mock()
        mock_db.create_session = AsyncMock(
            side_effect=DatabaseConnectionError(
                "FATAL: sorry, too many clients already"
            )
        )

        session = classes["SQLAlchemySession"](mock_db)

        result = await session.begin()
        assert not result.is_success()
        assert "too many clients" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_authentication_failure(self, mock_dependencies):
        """인증 실패"""
        classes = mock_dependencies

        mock_db = Mock()
        mock_db.create_session = AsyncMock(
            side_effect=DatabaseConnectionError(
                "FATAL: password authentication failed for user"
            )
        )

        session = classes["SQLAlchemySession"](mock_db)

        result = await session.begin()
        assert not result.is_success()
        assert "authentication failed" in result.unwrap_error()


class TestTransactionFailures:
    """트랜잭션 처리 실패 시나리오"""

    @pytest.mark.asyncio
    async def test_deadlock_during_commit(self, mock_dependencies):
        """커밋 시 데드락 발생"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session._is_active = True
        session._session = AsyncMock()

        # PostgreSQL 스타일 데드락 에러
        session._session.commit = AsyncMock(
            side_effect=DeadlockError("ERROR: deadlock detected")
        )

        result = await session.commit()
        assert not result.is_success()
        assert "deadlock detected" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_constraint_violation_rollback(self, mock_dependencies):
        """제약 조건 위반으로 인한 롤백"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session._is_active = True
        session._session = AsyncMock()

        # 외래키 제약조건 위반
        session._session.rollback = AsyncMock(
            side_effect=ConstraintViolationError(
                "ERROR: foreign key constraint violation"
            )
        )

        result = await session.rollback()
        assert not result.is_success()
        assert "constraint violation" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_transaction_timeout(self, mock_dependencies):
        """트랜잭션 타임아웃"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session._is_active = True
        session._session = AsyncMock()

        session._session.commit = AsyncMock(
            side_effect=SessionTimeoutError(
                "ERROR: canceling statement due to statement timeout"
            )
        )

        result = await session.commit()
        assert not result.is_success()
        assert "timeout" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_insufficient_disk_space(self, mock_dependencies):
        """디스크 공간 부족으로 트랜잭션 실패"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session._is_active = True
        session._session = AsyncMock()

        session._session.commit = AsyncMock(
            side_effect=InsufficientStorageError(
                "ERROR: could not extend file - No space left on device"
            )
        )

        result = await session.commit()
        assert not result.is_success()
        assert "No space left" in result.unwrap_error()


class TestSessionLifecycleEdgeCases:
    """세션 생명주기 엣지 케이스"""

    @pytest.mark.asyncio
    async def test_session_already_closed_operations(self, mock_dependencies):
        """이미 닫힌 세션에서 작업 시도"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)

        # 세션을 닫힌 상태로 설정
        session._is_active = False
        session._session = None

        # 이미 닫힌 세션에서 작업 시도
        commit_result = await session.commit()
        assert commit_result.is_success()  # 이미 비활성이면 성공 반환

        rollback_result = await session.rollback()
        assert rollback_result.is_success()  # 이미 비활성이면 성공 반환

        execute_result = await session.execute("SELECT 1")
        assert not execute_result.is_success()
        assert "세션이 활성화되지 않았습니다" in execute_result.unwrap_error()

    @pytest.mark.asyncio
    async def test_double_begin_session(self, mock_dependencies):
        """이미 활성화된 세션에 begin 호출"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)

        # 세션을 활성화 상태로 설정
        session._is_active = True

        # 이미 활성화된 세션에 begin 호출
        result = await session.begin()
        assert result.is_success()  # 이미 활성화되면 성공 반환

    @pytest.mark.asyncio
    async def test_force_close_with_active_transaction(self, mock_dependencies):
        """활성 트랜잭션이 있는 상태에서 강제 세션 종료"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session._is_active = True
        session._session = AsyncMock()

        # 강제 종료 시 리소스 정리 실패
        session._session.close = AsyncMock(
            side_effect=Exception("WARNING: there is already a transaction in progress")
        )

        result = await session.close()
        assert not result.is_success()
        assert "transaction in progress" in result.unwrap_error()


class TestContextManagerScenarios:
    """컨텍스트 매니저 시나리오"""

    @pytest.mark.asyncio
    async def test_context_manager_begin_failure(self, mock_dependencies):
        """컨텍스트 매니저 진입 시 begin 실패"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session.begin = AsyncMock(return_value=classes["Failure"]("Connection refused"))

        # 컨텍스트 매니저 진입 실패 시 예외 발생
        with pytest.raises(Exception, match="세션 시작 실패"):
            async with session:
                pass

    @pytest.mark.asyncio
    async def test_context_manager_business_exception_rollback(self, mock_dependencies):
        """비즈니스 로직 예외 발생 시 자동 롤백"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session.begin = AsyncMock(return_value=classes["Success"](None))
        session.rollback = AsyncMock(return_value=classes["Success"](None))
        session.close = AsyncMock(return_value=classes["Success"](None))

        # 비즈니스 로직에서 예외 발생
        try:
            async with session:
                raise ValueError("사용자 입력 검증 실패")
        except ValueError:
            pass

        # rollback이 호출되었는지 확인
        session.rollback.assert_called_once()
        session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_successful_commit(self, mock_dependencies):
        """정상 처리 시 자동 커밋"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db)
        session.begin = AsyncMock(return_value=classes["Success"](None))
        session.commit = AsyncMock(return_value=classes["Success"](None))
        session.close = AsyncMock(return_value=classes["Success"](None))

        # 정상 처리
        async with session:
            pass  # 성공적인 비즈니스 로직

        # commit이 호출되었는지 확인
        session.commit.assert_called_once()
        session.close.assert_called_once()


class TestSessionManagerBusinessScenarios:
    """SessionManager 비즈니스 시나리오"""

    @pytest.mark.asyncio
    async def test_create_session_with_configuration_error(self, mock_dependencies):
        """잘못된 설정으로 세션 생성 시도"""
        classes = mock_dependencies

        manager = classes["SessionManager"]()

        # 잘못된 데이터베이스 설정
        invalid_db = Mock()
        invalid_db.__class__.__name__ = "UnsupportedDBType"

        result = await manager.create_session(invalid_db)
        assert not result.is_success()
        assert "지원되지 않는 데이터베이스 타입입니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_session_manager_memory_leak_prevention(self, mock_dependencies):
        """메모리 누수 방지를 위한 세션 정리"""
        classes = mock_dependencies

        manager = classes["SessionManager"]()

        # 여러 세션 생성
        mock_db = Mock()
        mock_db.__class__.__name__ = "SQLAlchemyDatabase"

        sessions = []
        for i in range(5):
            session_mock = Mock()
            session_mock.session_id = f"session_{i}"
            session_mock.close = AsyncMock(return_value=classes["Success"](None))

            # 매니저에 수동으로 추가
            manager._sessions[f"session_{i}"] = session_mock
            sessions.append(session_mock)

        # 모든 세션 정리
        result = await manager.close_all_sessions()
        assert result.is_success()

        # 모든 세션이 정리되었는지 확인
        for session_mock in sessions:
            session_mock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_session_creation_race_condition(self, mock_dependencies):
        """동시 세션 생성으로 인한 경쟁 조건"""
        classes = mock_dependencies

        manager = classes["SessionManager"]()

        mock_db = Mock()
        mock_db.__class__.__name__ = "SQLAlchemyDatabase"

        # 동시에 여러 세션 생성 시도
        tasks = []
        for i in range(3):
            task = manager.create_session(mock_db)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 모든 세션이 성공적으로 생성되었는지 확인
        for result in results:
            if not isinstance(result, Exception):
                assert result.is_success()


class TestTortoiseSpecificScenarios:
    """Tortoise ORM 특수 시나리오"""

    @pytest.mark.asyncio
    async def test_tortoise_connection_pool_error(self, mock_dependencies):
        """Tortoise ORM 커넥션 풀 에러"""
        classes = mock_dependencies

        mock_db = Mock()
        mock_db.create_session = AsyncMock(
            side_effect=DatabaseConnectionError("Tortoise connection pool exhausted")
        )

        session = classes["TortoiseSession"](mock_db)

        result = await session.begin()
        assert not result.is_success()
        assert "pool exhausted" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_query_execution_with_connection_mock(
        self, mock_dependencies
    ):
        """Tortoise의 실제 연결을 통한 쿼리 실행 테스트"""
        classes = mock_dependencies

        mock_db = Mock()
        session = classes["TortoiseSession"](mock_db)
        session._is_active = True

        # Tortoise connections mock 설정
        with patch("rfs.database.session.connections") as mock_connections:
            mock_connection = Mock()
            mock_connection.execute_query = AsyncMock(return_value=("result", []))
            mock_connections.get.return_value = mock_connection

            result = await session.execute("SELECT COUNT(*) FROM users", [])
            assert result.is_success()
            assert result.unwrap() == ("result", [])

            mock_connections.get.assert_called_with("default")
            mock_connection.execute_query.assert_called_with(
                "SELECT COUNT(*) FROM users", []
            )


class TestDecoratorBusinessScenarios:
    """데코레이터 비즈니스 시나리오"""

    def test_with_session_decorator_sync_function_business_error(
        self, mock_dependencies
    ):
        """비즈니스 로직에서 동기 함수 사용 시 에러"""
        classes = mock_dependencies

        # 실제 비즈니스 코드에서 실수로 동기 함수에 데코레이터 적용
        @classes["with_session"]
        def process_user_data(user_id, session=None):
            # 비즈니스 로직 - 동기 함수
            return f"Processed user {user_id}"

        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):
            process_user_data(123)

    @pytest.mark.asyncio
    async def test_with_session_decorator_successful_business_logic(
        self, mock_dependencies
    ):
        """세션 데코레이터를 사용한 성공적인 비즈니스 로직"""
        classes = mock_dependencies

        # 실제 비즈니스 로직과 유사한 async 함수
        @classes["with_session"]
        async def create_user(name, email, session=None):
            # Mock 세션을 통한 비즈니스 로직
            assert session is not None
            return f"Created user: {name} ({email})"

        # session_scope Mock 설정 필요
        with patch("rfs.database.session.session_scope") as mock_scope:
            mock_session = Mock()
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await create_user("홍길동", "hong@example.com")
            assert "Created user: 홍길동" in result


class TestPerformanceAndResourceManagement:
    """성능 및 리소스 관리 테스트"""

    @pytest.mark.asyncio
    async def test_session_timeout_handling(self, mock_dependencies):
        """세션 타임아웃 처리"""
        classes = mock_dependencies

        # 30초 타임아웃 설정
        config = classes["SessionConfig"](timeout=30)

        mock_db = Mock()
        session = classes["SQLAlchemySession"](mock_db, config)
        session._is_active = True
        session._session = AsyncMock()

        # 장시간 실행 쿼리 시뮬레이션
        session._session.execute = AsyncMock(
            side_effect=SessionTimeoutError("Query execution timeout")
        )

        result = await session.execute(
            "SELECT * FROM large_table WHERE complex_condition = true"
        )
        assert not result.is_success()
        assert "timeout" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_connection_pool_configuration(self, mock_dependencies):
        """커넥션 풀 설정 테스트"""
        classes = mock_dependencies

        # 커넥션 풀 설정
        config = classes["SessionConfig"](pool_size=5, max_overflow=10, timeout=60)

        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.timeout == 60

        # 실제 비즈니스에서 이런 설정이 적용되는지 확인
        manager = classes["SessionManager"]()
        manager.set_config(config)

        assert manager.config.pool_size == 5
        assert manager.config.max_overflow == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
