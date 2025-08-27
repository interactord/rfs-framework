"""
Session 모듈 격리 테스트 - 예외 처리 커버리지 개선
실제 실행 가능한 최소한의 의존성으로 session.py 테스트
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


def load_session_module():
    """session.py 모듈을 직접 로드"""

    # Mock all dependencies
    mock_modules = {}

    # Result types
    class Success:
        def __init__(self, value):
            self.value = value

        def is_success(self):
            return True

        def unwrap(self):
            return self.value

    class Failure:
        def __init__(self, error):
            self.error = error

        def is_success(self):
            return False

        def unwrap_error(self):
            return self.error

    result_module = Mock()
    result_module.Success = Success
    result_module.Failure = Failure
    result_module.Result = Mock()
    mock_modules["rfs.core.result"] = result_module

    # Enhanced logging
    logger_module = Mock()
    logger_module.get_logger = Mock(return_value=Mock())
    mock_modules["rfs.core.enhanced_logging"] = logger_module

    # Singleton
    singleton_module = Mock()
    singleton_module.SingletonMeta = type
    mock_modules["rfs.core.singleton"] = singleton_module

    # Database base
    base_module = Mock()
    base_module.Database = Mock()
    base_module.get_database = Mock(return_value=None)
    mock_modules["rfs.database.base"] = base_module

    # Models
    models_module = Mock()
    models_module.BaseModel = Mock()
    models_module.ModelRegistry = Mock()
    models_module.get_model_registry = Mock()
    mock_modules["rfs.database.models_refactored"] = models_module

    # Monkey patch sys.modules
    original_modules = {}
    for name, module in mock_modules.items():
        if name in sys.modules:
            original_modules[name] = sys.modules[name]
        sys.modules[name] = module

    try:
        # Load session module
        session_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "rfs"
            / "database"
            / "session.py"
        )
        spec = importlib.util.spec_from_file_location(
            "rfs.database.session", session_path
        )
        session_module = importlib.util.module_from_spec(spec)

        # Add to sys.modules before executing
        sys.modules["rfs.database.session"] = session_module
        spec.loader.exec_module(session_module)

        return session_module, Success, Failure
    finally:
        # Restore original modules
        for name in mock_modules:
            if name in original_modules:
                sys.modules[name] = original_modules[name]
            else:
                sys.modules.pop(name, None)


@pytest.fixture
def session_classes():
    """Session 관련 클래스들 로드"""
    return load_session_module()


class TestSessionConfigIsolated:
    """SessionConfig 격리 테스트"""

    def test_session_config_all_attributes(self, session_classes):
        """SessionConfig 모든 속성 테스트"""
        session_module, Success, Failure = session_classes

        # 기본값 테스트
        config = session_module.SessionConfig()
        assert config.auto_commit is True
        assert config.auto_flush is True
        assert config.expire_on_commit is False
        assert config.isolation_level == "READ_COMMITTED"
        assert config.timeout == 30
        assert config.pool_size == 10
        assert config.max_overflow == 20

        # 커스텀 값 테스트
        custom_config = session_module.SessionConfig(
            auto_commit=False, timeout=45, pool_size=15
        )
        assert custom_config.auto_commit is False
        assert custom_config.timeout == 45
        assert custom_config.pool_size == 15


class TestSQLAlchemySessionIsolated:
    """SQLAlchemy Session 격리 테스트"""

    @pytest.mark.asyncio
    async def test_begin_already_active(self, session_classes):
        """이미 활성화된 세션 begin 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True

        result = await session.begin()
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_begin_success(self, session_classes):
        """세션 시작 성공 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        mock_db.create_session = AsyncMock(return_value=Mock())

        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = False

        result = await session.begin()
        assert result.is_success()
        assert session._is_active is True

    @pytest.mark.asyncio
    async def test_begin_exception(self, session_classes):
        """세션 시작 예외 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        mock_db.create_session = AsyncMock(side_effect=Exception("Connection failed"))

        session = session_module.SQLAlchemySession(mock_db)

        result = await session.begin()
        assert not result.is_success()
        assert "세션 시작 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_commit_not_active(self, session_classes):
        """비활성 상태 commit 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = False
        session._session = None

        result = await session.commit()
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_commit_success(self, session_classes):
        """commit 성공 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()

        result = await session.commit()
        assert result.is_success()
        session._session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_exception(self, session_classes):
        """commit 예외 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()
        session._session.commit = AsyncMock(side_effect=Exception("Commit failed"))

        result = await session.commit()
        assert not result.is_success()
        assert "커밋 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_rollback_not_active(self, session_classes):
        """비활성 상태 rollback 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = False
        session._session = None

        result = await session.rollback()
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_rollback_success(self, session_classes):
        """rollback 성공 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()

        result = await session.rollback()
        assert result.is_success()
        session._session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_exception(self, session_classes):
        """rollback 예외 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()
        session._session.rollback = AsyncMock(side_effect=Exception("Rollback failed"))

        result = await session.rollback()
        assert not result.is_success()
        assert "롤백 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_close_not_active(self, session_classes):
        """비활성 상태 close 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = False

        result = await session.close()
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_close_success(self, session_classes):
        """close 성공 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()

        result = await session.close()
        assert result.is_success()
        assert session._is_active is False
        session._session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_exception(self, session_classes):
        """close 예외 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()
        session._session.close = AsyncMock(side_effect=Exception("Close failed"))

        result = await session.close()
        assert not result.is_success()
        assert "세션 종료 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_execute_not_active(self, session_classes):
        """비활성 상태 execute 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = False

        result = await session.execute("SELECT 1")
        assert not result.is_success()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_execute_success(self, session_classes):
        """execute 성공 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()
        mock_result = Mock()
        session._session.execute = AsyncMock(return_value=mock_result)

        result = await session.execute("SELECT 1", {"param": "value"})
        assert result.is_success()
        assert result.unwrap() == mock_result
        session._session.execute.assert_called_once_with("SELECT 1", {"param": "value"})

    @pytest.mark.asyncio
    async def test_execute_exception(self, session_classes):
        """execute 예외 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True
        session._session = AsyncMock()
        session._session.execute = AsyncMock(side_effect=Exception("Query failed"))

        result = await session.execute("SELECT 1")
        assert not result.is_success()
        assert "쿼리 실행 실패" in result.unwrap_error()


class TestTortoiseSessionIsolated:
    """Tortoise Session 격리 테스트"""

    @pytest.mark.asyncio
    async def test_begin_success(self, session_classes):
        """Tortoise 세션 시작 성공 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        mock_db.create_session = AsyncMock(return_value=Mock())

        session = session_module.TortoiseSession(mock_db)

        result = await session.begin()
        assert result.is_success()
        assert session._is_active is True

    @pytest.mark.asyncio
    async def test_begin_exception(self, session_classes):
        """Tortoise 세션 시작 예외 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        mock_db.create_session = AsyncMock(
            side_effect=Exception("Tortoise connection failed")
        )

        session = session_module.TortoiseSession(mock_db)

        result = await session.begin()
        assert not result.is_success()
        assert "세션 시작 실패" in result.unwrap_error()


class TestDatabaseTransactionIsolated:
    """DatabaseTransaction 격리 테스트"""

    @pytest.mark.asyncio
    async def test_begin_session_not_active(self, session_classes):
        """세션이 비활성화된 상태에서 트랜잭션 시작 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = False

        transaction = session_module.DatabaseTransaction(session)

        result = await transaction.begin()
        assert not result.is_success()
        assert "세션이 활성화되지 않았습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_begin_success(self, session_classes):
        """트랜잭션 시작 성공 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        session._is_active = True

        transaction = session_module.DatabaseTransaction(session)

        result = await transaction.begin()
        assert result.is_success()
        assert transaction._is_active is True

    def test_is_active_property(self, session_classes):
        """is_active 프로퍼티 테스트"""
        session_module, Success, Failure = session_classes

        mock_db = Mock()
        session = session_module.SQLAlchemySession(mock_db)
        transaction = session_module.DatabaseTransaction(session)

        # 초기 상태는 비활성
        assert not transaction.is_active

        # 활성화
        transaction._is_active = True
        assert transaction.is_active


class TestSessionManagerIsolated:
    """SessionManager 격리 테스트"""

    def test_singleton_behavior(self, session_classes):
        """SessionManager 싱글톤 동작 테스트"""
        session_module, Success, Failure = session_classes

        manager1 = session_module.get_session_manager()
        manager2 = session_module.get_session_manager()

        assert manager1 is manager2

    def test_init(self, session_classes):
        """SessionManager 초기화 테스트"""
        session_module, Success, Failure = session_classes

        manager = session_module.SessionManager()

        assert hasattr(manager, "config")
        assert hasattr(manager, "_sessions")
        assert isinstance(manager._sessions, dict)
        assert len(manager._sessions) == 0

    def test_set_config(self, session_classes):
        """SessionManager set_config 테스트"""
        session_module, Success, Failure = session_classes

        manager = session_module.SessionManager()
        new_config = session_module.SessionConfig(timeout=60)

        manager.set_config(new_config)

        assert manager.config == new_config
        assert manager.config.timeout == 60

    @pytest.mark.asyncio
    async def test_create_session_no_database(self, session_classes):
        """데이터베이스 없이 세션 생성 테스트"""
        session_module, Success, Failure = session_classes

        manager = session_module.SessionManager()

        result = await manager.create_session(None)
        assert not result.is_success()
        assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_create_session_unsupported_type(self, session_classes):
        """지원되지 않는 데이터베이스 타입 테스트"""
        session_module, Success, Failure = session_classes

        class UnsupportedDB:
            pass

        manager = session_module.SessionManager()
        unsupported_db = UnsupportedDB()

        result = await manager.create_session(unsupported_db)
        assert not result.is_success()
        assert "지원되지 않는 데이터베이스 타입입니다" in result.unwrap_error()


class TestDecoratorExceptions:
    """데코레이터 예외 처리 테스트"""

    def test_with_session_sync_function_error(self, session_classes):
        """with_session 데코레이터 동기 함수 에러 테스트"""
        session_module, Success, Failure = session_classes

        @session_module.with_session
        def sync_function():
            return "test"

        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):
            sync_function()

    def test_with_transaction_sync_function_error(self, session_classes):
        """with_transaction 데코레이터 동기 함수 에러 테스트"""
        session_module, Success, Failure = session_classes

        @session_module.with_transaction
        def sync_function():
            return "test"

        with pytest.raises(RuntimeError, match="동기 함수는 지원되지 않습니다"):
            sync_function()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
