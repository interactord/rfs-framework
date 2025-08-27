"""
Direct session module test - avoiding import issues
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


def test_session_config():
    """SessionConfig 기본 테스트"""
    import os
    import sys

    # models.py import 문제 우회
    with patch.dict(sys.modules):
        # models import를 Mock으로 대체
        mock_models = Mock()
        mock_models.BaseModel = Mock()
        mock_models.ModelRegistry = Mock()
        mock_models.get_model_registry = Mock()
        sys.modules["rfs.database.models_refactored"] = mock_models

        from rfs.database.session import SessionConfig

        config = SessionConfig()
        assert config.auto_commit is True
        assert config.auto_flush is True
        assert config.expire_on_commit is False
        assert config.isolation_level == "READ_COMMITTED"
        assert config.timeout == 30
        assert config.pool_size == 10
        assert config.max_overflow == 20


@pytest.mark.asyncio
async def test_session_manager_basic():
    """SessionManager 기본 기능 테스트"""
    import sys

    with patch.dict(sys.modules):
        # Mock dependencies
        mock_models = Mock()
        mock_base = Mock()
        mock_base.get_database = Mock(return_value=None)
        sys.modules["rfs.database.models_refactored"] = mock_models
        sys.modules["rfs.database.base"] = mock_base

        from rfs.database.session import SessionManager, get_session_manager

        # 싱글톤 테스트
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        assert manager1 is manager2

        # 기본 설정 확인
        assert hasattr(manager1, "config")
        assert hasattr(manager1, "_sessions")
        assert len(manager1._sessions) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
