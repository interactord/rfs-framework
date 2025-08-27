"""
RFS Framework 테스트 설정 및 공통 fixture

이 모듈은 전체 테스트 스위트에서 공통으로 사용되는 fixture와 설정을 제공합니다.
"""

import asyncio
import logging
import os
import tempfile
from typing import Any, AsyncGenerator, Dict, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

# Test environment setup
os.environ["RFS_ENV"] = "test"
os.environ["LOG_LEVEL"] = "DEBUG"

# Disable logging during tests unless explicitly needed
logging.getLogger("rfs").setLevel(logging.CRITICAL)


# 세션 레벨 이벤트 루프 제거 - pytest-asyncio가 자동으로 함수 레벨에서 관리
# @pytest.fixture(scope="session")
# def event_loop():
#     """이벤트 루프 fixture - 전체 테스트 세션용"""
#     loop = asyncio.new_event_loop()
#     yield loop
#     loop.close()


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """임시 디렉토리 fixture"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """테스트용 샘플 설정"""
    return {
        "database": {"url": "sqlite:///test.db", "pool_size": 5, "echo": False},
        "cache": {"type": "memory", "ttl": 300, "max_size": 1000},
        "messaging": {"broker": "memory", "queue_size": 100},
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    }


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis 클라이언트"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    mock.exists.return_value = False
    mock.ttl.return_value = -1
    mock.ping.return_value = True
    mock.pipeline.return_value = mock
    mock.execute.return_value = []
    mock.watch.return_value = None
    mock.multi.return_value = None
    return mock


@pytest.fixture
def mock_database_connection() -> MagicMock:
    """Mock 데이터베이스 연결"""
    mock = MagicMock()
    mock.begin.return_value = mock
    mock.commit.return_value = None
    mock.rollback.return_value = None
    mock.close.return_value = None
    mock.execute.return_value = MagicMock()
    mock.fetchone.return_value = None
    mock.fetchall.return_value = []
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=None)
    return mock


@pytest.fixture
def mock_transaction_manager() -> MagicMock:
    """Mock 트랜잭션 매니저"""
    mock = MagicMock()
    mock.begin.return_value = MagicMock()
    mock.commit.return_value = None
    mock.rollback.return_value = None
    mock.get_current.return_value = None
    mock.is_active.return_value = False
    return mock


@pytest.fixture
def in_memory_db_engine():
    """인메모리 SQLite 엔진 fixture (mock)"""
    mock = MagicMock()
    mock.dispose.return_value = None
    return mock


@pytest.fixture
async def async_in_memory_db():
    """비동기 인메모리 데이터베이스 fixture (mock)"""
    mock_engine = MagicMock()
    mock_session = MagicMock()

    yield {"engine": mock_engine, "session": mock_session}


@pytest.fixture
def mock_message_broker():
    """Mock 메시지 브로커"""

    class MockBroker:
        def __init__(self):
            self.messages = []
            self.subscribers = {}
            self.is_connected = True

        async def publish(self, topic: str, message: Any):
            self.messages.append({"topic": topic, "message": message})

        async def subscribe(self, topic: str, handler):
            if topic not in self.subscribers:
                self.subscribers[topic] = []
            self.subscribers[topic].append(handler)

        async def connect(self):
            self.is_connected = True

        async def disconnect(self):
            self.is_connected = False

    return MockBroker()


@pytest.fixture
def sample_data():
    """테스트용 샘플 데이터"""
    return {
        "users": [
            {"id": 1, "name": "김철수", "email": "kim@example.com", "age": 30},
            {"id": 2, "name": "이영희", "email": "lee@example.com", "age": 25},
            {"id": 3, "name": "박민수", "email": "park@example.com", "age": 35},
        ],
        "products": [
            {"id": 1, "name": "노트북", "price": 1500000, "category": "전자제품"},
            {"id": 2, "name": "마우스", "price": 50000, "category": "전자제품"},
            {"id": 3, "name": "책상", "price": 200000, "category": "가구"},
        ],
        "orders": [
            {"id": 1, "user_id": 1, "product_id": 1, "quantity": 1, "total": 1500000},
            {"id": 2, "user_id": 2, "product_id": 2, "quantity": 2, "total": 100000},
        ],
    }


@pytest.fixture
def mock_async_function():
    """비동기 함수 mock"""
    return AsyncMock()


@pytest.fixture
def performance_timer():
    """성능 측정용 타이머"""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()

        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

    return Timer()


@pytest.fixture
def edge_case_data():
    """엣지 케이스 테스트 데이터"""
    return {
        "empty_values": ["", None, [], {}, set()],
        "large_values": {
            "string": "a" * 10000,
            "number": 2**63 - 1,
            "list": list(range(10000)),
            "dict": {f"key_{i}": f"value_{i}" for i in range(1000)},
        },
        "unicode_values": ["🚀", "한글", "🔥💯", "Émojis", "中文"],
        "special_characters": ["\n", "\t", "\r", "\\", "'", '"', "&", "<", ">"],
    }


@pytest.fixture
def error_scenarios():
    """오류 시나리오 데이터"""
    return {
        "network_errors": [ConnectionError, TimeoutError, OSError],
        "data_errors": [ValueError, TypeError, KeyError],
        "business_errors": ["INSUFFICIENT_BALANCE", "INVALID_USER", "EXPIRED_TOKEN"],
        "system_errors": [MemoryError, PermissionError, FileNotFoundError],
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """각 테스트 전후 환경 설정"""
    # 테스트 시작 전 설정
    original_env = os.environ.copy()

    yield

    # 테스트 후 정리
    os.environ.clear()
    os.environ.update(original_env)


# Cloud Run 전용 픽스처들 추가
@pytest.fixture(autouse=True)
def reset_cloud_run_singletons():
    """각 테스트 후 Cloud Run 싱글톤 인스턴스들 초기화"""
    yield

    # 싱글톤 레지스트리 정리
    try:
        from rfs.core.singleton import SingletonMeta

        SingletonMeta._instances = {}
    except ImportError:
        pass


@pytest.fixture
def clean_environment():
    """환경 변수 정리된 상태 제공"""
    cloud_run_vars = [
        "K_SERVICE",
        "K_REVISION",
        "K_CONFIGURATION",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_REGION",
        "CLOUD_RUN_REGION",
        "PORT",
        "CLOUD_RUN_JOB",
    ]

    # 기존 값들 백업
    backup = {}
    for var in cloud_run_vars:
        if var in os.environ:
            backup[var] = os.environ[var]
            del os.environ[var]

    yield

    # 환경 변수 복원
    for var, value in backup.items():
        os.environ[var] = value


@pytest.fixture
def mock_cloud_run_environment():
    """Mock Cloud Run 환경 제공"""
    env_vars = {
        "K_SERVICE": "test-service",
        "K_REVISION": "test-service-00001-abc",
        "K_CONFIGURATION": "test-service",
        "GOOGLE_CLOUD_PROJECT": "test-project-123",
        "GOOGLE_CLOUD_REGION": "asia-northeast3",
        "PORT": "8080",
    }

    from unittest.mock import patch

    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def isolated_monitoring_client():
    """격리된 모니터링 클라이언트 제공"""
    from rfs.cloud_run.helpers import CloudMonitoringClient

    # 새 인스턴스 강제 생성
    if hasattr(CloudMonitoringClient, "_instances"):
        CloudMonitoringClient._instances.clear()

    client = CloudMonitoringClient()
    client._metrics = []
    client._logs = []

    yield client

    # 정리
    if hasattr(CloudMonitoringClient, "_instances"):
        CloudMonitoringClient._instances.clear()


@pytest.fixture
def isolated_task_queue():
    """격리된 작업 큐 제공"""
    from rfs.cloud_run.helpers import CloudTaskQueue

    # 새 인스턴스 강제 생성
    if hasattr(CloudTaskQueue, "_instances"):
        CloudTaskQueue._instances.clear()

    queue = CloudTaskQueue()
    queue._queue = []
    queue._processing = False

    yield queue

    # 정리
    if hasattr(CloudTaskQueue, "_instances"):
        CloudTaskQueue._instances.clear()


@pytest.fixture
def isolated_service_discovery():
    """격리된 서비스 디스커버리 제공"""
    from rfs.cloud_run.helpers import CloudRunServiceDiscovery

    # 새 인스턴스 강제 생성
    if hasattr(CloudRunServiceDiscovery, "_instances"):
        CloudRunServiceDiscovery._instances.clear()

    discovery = CloudRunServiceDiscovery()
    discovery._services = {}
    discovery._initialized = False

    yield discovery

    # 정리
    if hasattr(CloudRunServiceDiscovery, "_instances"):
        CloudRunServiceDiscovery._instances.clear()


# 성능 최적화를 위한 마커들
def pytest_configure(config):
    """커스텀 마커 등록"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "cloud_run: marks tests as cloud run specific")


# Parametrize helpers - 중복 방지를 위해 비활성화
# def pytest_generate_tests(metafunc):
#     """동적 매개변수 생성"""
#     if "concurrency_level" in metafunc.fixturenames:
#         metafunc.parametrize("concurrency_level", [1, 5, 10, 50, 100])
#
#     if "cache_size" in metafunc.fixturenames:
#         metafunc.parametrize("cache_size", [10, 100, 1000, 10000])
#
#     if "data_size" in metafunc.fixturenames:
#         metafunc.parametrize("data_size", ["small", "medium", "large"])
