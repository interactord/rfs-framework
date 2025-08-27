"""
RFS Testing Framework - Fixtures Module
테스트 픽스처 관리 및 설정
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

import pytest

from ..core.result import Failure, Result, Success


class FixtureScope(Enum):
    """픽스처 스코프"""

    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    SESSION = "session"


@dataclass
class FixtureConfig:
    """픽스처 설정"""

    scope: FixtureScope = FixtureScope.FUNCTION
    autouse = False
    params = None
    ids = None


# 픽스처 레지스트리
_fixtures = {}


def fixture(
    scope: FixtureScope = FixtureScope.FUNCTION,
    autouse=False,
    params=None,
    ids=None,
) -> Callable:
    """픽스처 데코레이터"""

    def decorator(func: Callable) -> Callable:
        # pytest fixture 래핑
        pytest_fixture = pytest.fixture(
            scope=scope.value, autouse=autouse, params=params, ids=ids
        )
        wrapped_func = pytest_fixture(func)

        # 레지스트리에 저장
        _fixtures[func.__name__] = wrapped_func

        return wrapped_func

    return decorator


def setup_fixture(name: str) -> Callable:
    """셋업 픽스처"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 셋업 실행
            result = func(*args, **kwargs)
            _fixtures[f"{name}_setup"] = result
            return result

        return fixture(autouse=True)(wrapper)

    return decorator


def teardown_fixture(name: str) -> Callable:
    """티어다운 픽스처"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            yield  # 테스트 실행
            # 티어다운 실행
            func(*args, **kwargs)
            if f"{name}_setup" in _fixtures:
                del _fixtures[f"{name}_setup"]

        return fixture(autouse=True)(wrapper)

    return decorator


@fixture(scope=FixtureScope.SESSION)
def database_fixture():
    """데이터베이스 픽스처"""
    from ..database.base import Database

    # 테스트 데이터베이스 설정
    db_config = {"driver": "sqlite", "database": ":memory:", "echo": False}

    db = Database(db_config)

    # 셋업
    db.connect()
    db.create_tables()

    yield db

    # 티어다운
    db.drop_tables()
    db.disconnect()


@fixture(scope=FixtureScope.SESSION)
def redis_fixture():
    """Redis 픽스처"""
    import fakeredis

    # FakeRedis 인스턴스 생성
    redis_client = fakeredis.FakeStrictRedis()

    yield redis_client

    # 클린업
    redis_client.flushall()


@fixture(scope=FixtureScope.FUNCTION)
async def web_client_fixture():
    """웹 클라이언트 픽스처"""
    from httpx import AsyncClient

    async with AsyncClient() as client:
        yield client


@fixture(scope=FixtureScope.FUNCTION)
def mock_server_fixture():
    """목 서버 픽스처"""
    from unittest.mock import MagicMock

    # Mock 서버 생성
    server = MagicMock()
    server.start = MagicMock(return_value=Success(None))
    server.stop = MagicMock(return_value=Success(None))
    server.is_running = False

    def start():
        server.is_running = True
        return Success(None)

    def stop():
        server.is_running = False
        return Success(None)

    server.start = start
    server.stop = stop

    return server


# Async 픽스처 헬퍼
def async_fixture(func: Callable) -> Callable:
    """비동기 픽스처 데코레이터"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(func(*args, **kwargs))

    return fixture()(wrapper)


# 테스트 데이터 픽스처
@fixture(scope=FixtureScope.MODULE)
def test_data_fixture():
    """테스트 데이터 픽스처"""
    return {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@test.com"},
            {"id": 2, "name": "Bob", "email": "bob@test.com"},
            {"id": 3, "name": "Charlie", "email": "charlie@test.com"},
        ],
        "posts": [
            {"id": 1, "user_id": 1, "title": "First Post", "content": "Hello World"},
            {"id": 2, "user_id": 2, "title": "Second Post", "content": "Test Content"},
        ],
        "config": {
            "api_key": "test-api-key",
            "base_url": "http://localhost:8000",
            "timeout": 30,
        },
    }


# 환경 설정 픽스처
@fixture(scope=FixtureScope.SESSION)
def env_fixture(monkeypatch):
    """환경 변수 픽스처"""
    test_env = {
        "RFS_ENV": "test",
        "DATABASE_URL": "sqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/0",
        "API_KEY": "test-key-123",
        "DEBUG": "true",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    yield test_env

    # 환경 변수 정리는 monkeypatch가 자동으로 처리


# 임시 디렉토리 픽스처
@fixture(scope=FixtureScope.FUNCTION)
def temp_dir_fixture(tmp_path):
    """임시 디렉토리 픽스처"""
    test_dir = tmp_path / "test_workspace"
    test_dir.mkdir()

    # 테스트 파일들 생성
    (test_dir / "config.json").write_text('{"test": true}')
    (test_dir / "data.txt").write_text("test data")

    yield test_dir

    # tmp_path는 pytest가 자동으로 정리


__all__ = [
    "FixtureScope",
    "FixtureConfig",
    "fixture",
    "setup_fixture",
    "teardown_fixture",
    "database_fixture",
    "redis_fixture",
    "web_client_fixture",
    "mock_server_fixture",
    "async_fixture",
    "test_data_fixture",
    "env_fixture",
    "temp_dir_fixture",
]
