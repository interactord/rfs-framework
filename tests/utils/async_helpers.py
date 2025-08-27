"""
비동기 테스트 헬퍼 유틸리티

pytest-asyncio의 클래스 기반 테스트에서 발생하는 async fixture 문제를 해결하기 위한
헬퍼 함수와 컨텍스트 매니저를 제공합니다.
"""

import asyncio
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Optional

from rfs.cache.memory_cache import MemoryCache, MemoryCacheConfig
from rfs.core.result import Failure, Success
from rfs.messaging.memory_broker import MemoryMessageBroker, MemoryMessageConfig

# ============================================================================
# Messaging 헬퍼 함수
# ============================================================================


async def create_memory_broker(
    config=None,
) -> MemoryMessageBroker:
    """
    메모리 메시지 브로커를 생성하고 연결합니다.

    Args:
        config: 브로커 설정 (None일 경우 기본값 사용)

    Returns:
        연결된 MemoryMessageBroker 인스턴스

    Raises:
        Exception: 브로커 연결 실패 시
    """
    if config is None:
        config = MemoryMessageConfig(
            max_queue_size=1000, max_topics=100, enable_persistence=False
        )

    broker = MemoryMessageBroker(config)
    result = await broker.connect()

    if result.is_failure():
        raise Exception(f"Failed to connect broker: {result.get_error()}")

    return broker


@asynccontextmanager
async def broker_context(
    config=None,
) -> AsyncGenerator[MemoryMessageBroker, None]:
    """
    메시지 브로커 컨텍스트 매니저.

    자동으로 브로커를 생성, 연결하고 사용 후 정리합니다.

    Args:
        config: 브로커 설정 (None일 경우 기본값 사용)

    Yields:
        연결된 MemoryMessageBroker 인스턴스

    Example:
        async with broker_context() as broker:
            await broker.publish(message)
    """
    broker = await create_memory_broker(config)
    try:
        yield broker
    finally:
        await broker.disconnect()


# ============================================================================
# Cache 헬퍼 함수
# ============================================================================


async def create_memory_cache(
    config=None,
) -> MemoryCache:
    """
    메모리 캐시를 생성하고 연결합니다.

    Args:
        config: 캐시 설정 (None일 경우 기본값 사용)

    Returns:
        연결된 MemoryCache 인스턴스

    Raises:
        Exception: 캐시 연결 실패 시
    """
    if config is None:
        config = MemoryCacheConfig(
            max_size=100,
            eviction_policy="lru",
            cleanup_interval=1,
            lazy_expiration=True,
            min_ttl=1,  # TTL 테스트를 위해 min_ttl을 1초로 설정
        )

    cache = MemoryCache(config)
    result = await cache.connect()

    if result.is_failure():
        raise Exception(f"Failed to connect cache: {result.get_error()}")

    return cache


@asynccontextmanager
async def cache_context(
    config=None,
) -> AsyncGenerator[MemoryCache, None]:
    """
    캐시 컨텍스트 매니저.

    자동으로 캐시를 생성, 연결하고 사용 후 정리합니다.

    Args:
        config: 캐시 설정 (None일 경우 기본값 사용)

    Yields:
        연결된 MemoryCache 인스턴스

    Example:
        async with cache_context() as cache:
            await cache.set("key", "value")
    """
    cache = await create_memory_cache(config)
    try:
        yield cache
    finally:
        await cache.disconnect()


# ============================================================================
# 테스트 타임아웃 헬퍼
# ============================================================================


def async_test_with_timeout(timeout: float = 5.0):
    """
    비동기 테스트에 타임아웃을 적용하는 데코레이터.

    Args:
        timeout: 타임아웃 시간 (초 단위, 기본값: 5초)

    Example:
        @async_test_with_timeout(10.0)
        async def test_something():
            await long_running_operation()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                raise AssertionError(f"Test timed out after {timeout} seconds")

        return wrapper

    return decorator


# ============================================================================
# 테스트용 Mock 객체 생성 헬퍼
# ============================================================================


class AsyncContextManagerMock:
    """비동기 컨텍스트 매니저를 시뮬레이션하는 Mock 객체"""

    def __init__(self, return_value: Any = None):
        self.return_value = return_value
        self.enter_called = False
        self.exit_called = False

    async def __aenter__(self):
        self.enter_called = True
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exit_called = True
        return False


def create_async_mock(return_value: Any = None) -> AsyncContextManagerMock:
    """
    비동기 컨텍스트 매니저 Mock 객체를 생성합니다.

    Args:
        return_value: __aenter__에서 반환할 값

    Returns:
        AsyncContextManagerMock 인스턴스
    """
    return AsyncContextManagerMock(return_value)


# ============================================================================
# 비동기 리소스 관리 헬퍼
# ============================================================================


class AsyncResourceManager:
    """
    여러 비동기 리소스를 관리하는 헬퍼 클래스.

    테스트에서 여러 리소스를 사용할 때 자동으로 정리를 보장합니다.
    """

    def __init__(self):
        self.resources = []
        self.cleanup_funcs = []

    def add_resource(self, resource: Any, cleanup_func=None):
        """
        관리할 리소스를 추가합니다.

        Args:
            resource: 관리할 리소스
            cleanup_func: 정리 함수 (옵션)
        """
        self.resources.append(resource)
        if cleanup_func:
            self.cleanup_funcs.append(cleanup_func)

    async def cleanup(self):
        """모든 리소스를 정리합니다."""
        for cleanup_func in reversed(self.cleanup_funcs):
            try:
                if asyncio.iscoroutinefunction(cleanup_func):
                    await cleanup_func()
                else:
                    cleanup_func()
            except Exception:
                pass  # 정리 중 오류는 무시

        self.resources.clear()
        self.cleanup_funcs.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        return False


# ============================================================================
# 테스트 데이터 생성 헬퍼
# ============================================================================


def create_test_message(topic="test_topic", data: Any = None) -> dict:
    """
    테스트용 메시지 데이터를 생성합니다.

    Args:
        topic: 메시지 토픽
        data: 메시지 데이터

    Returns:
        메시지 딕셔너리
    """
    import uuid
    from datetime import datetime

    return {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "data": data or {"test": "data"},
        "timestamp": datetime.now(),
        "headers": {},
    }


def create_test_cache_data(count=10) -> dict:
    """
    테스트용 캐시 데이터를 생성합니다.

    Args:
        count: 생성할 데이터 개수

    Returns:
        키-값 쌍의 딕셔너리
    """
    return {f"key_{i}": f"value_{i}" for i in range(count)}
