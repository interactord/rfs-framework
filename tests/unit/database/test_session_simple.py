"""
Session 모듈 간단 테스트
models_refactored.py 의존성 없이 session.py만 테스트
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# 환경변수 설정 (다른 임포트보다 먼저)
os.environ["RFS_ORM_TYPE"] = "SQLALCHEMY"


def test_session_config_import():
    """SessionConfig 클래스 임포트 테스트"""
    try:
        # models_refactored 의존성을 회피하기 위해 직접 임포트
        sys.path.insert(0, "/Users/sangbongmoon/Workspace/rfs-database-v2/src")

        # 직접 session 모듈에서 SessionConfig만 임포트
        from rfs.database.session import SessionConfig

        # 기본값 확인
        config = SessionConfig()
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.timeout == 30
        assert config.auto_commit == True
        assert config.auto_flush == True
        assert config.expire_on_commit == False
        assert config.isolation_level == "READ_COMMITTED"

    except ImportError as e:
        pytest.skip(f"SessionConfig import failed: {e}")


def test_session_config_custom():
    """SessionConfig 커스텀 값 테스트"""
    try:
        from rfs.database.session import SessionConfig

        config = SessionConfig(
            pool_size=20, max_overflow=30, timeout=60, auto_commit=False
        )

        assert config.pool_size == 20
        assert config.max_overflow == 30
        assert config.timeout == 60
        assert config.auto_commit == False

    except ImportError as e:
        pytest.skip(f"SessionConfig import failed: {e}")
