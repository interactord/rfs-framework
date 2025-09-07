"""
RFS Framework MemoryCache 단위 테스트

메모리 캐시의 기본 연산, 저장, 조회, 삭제 기능을 테스트합니다.
async fixture 문제를 해결하기 위해 헬퍼 함수 패턴을 사용합니다.
"""

import asyncio
import os

# 테스트 헬퍼 import
import sys
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from rfs.cache.memory_cache import CacheItem, MemoryCache, MemoryCacheConfig
from rfs.core.result import Failure, Success

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from tests.utils.async_helpers import cache_context, create_memory_cache


class TestMemoryCache:
    """메모리 캐시 기본 기능 테스트"""

    @pytest.mark.asyncio
    async def test_cache_connection(self):
        """캐시 연결 및 해제 테스트"""
        config = MemoryCacheConfig(max_size=100)
        cache = await create_memory_cache(config)

        try:
            # 연결 상태 확인
            assert cache.is_connected

            # 설정 확인
            assert cache.config.max_size == 100
        finally:
            await cache.disconnect()
            assert not cache.is_connected

    @pytest.mark.asyncio
    async def test_cache_basic_operations(self):
        """캐시 기본 연산 테스트 (set, get, delete)"""
        async with cache_context() as cache:
            # SET 연산
            result = await cache.set("key1", "value1")
            assert result.is_success()

            # GET 연산
            result = await cache.get("key1")
            assert result.is_success()
            assert result.get() == "value1"

            # DELETE 연산
            result = await cache.delete("key1")
            assert result.is_success()

            # 삭제 후 조회
            result = await cache.get("key1")
            assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_multiple_items(self):
        """여러 아이템 저장 및 조회"""
        async with cache_context() as cache:
            items = {
                "user:1": {"id": 1, "name": "Alice"},
                "user:2": {"id": 2, "name": "Bob"},
                "product:1": {"id": 1, "name": "Laptop"},
                "product:2": {"id": 2, "name": "Mouse"},
            }

            # 모든 아이템 저장
            for key, value in items.items():
                result = await cache.set(key, value)
                assert result.is_success()

            # 모든 아이템 조회
            for key, expected_value in items.items():
                result = await cache.get(key)
                assert result.is_success()
                assert result.get() == expected_value

    @pytest.mark.asyncio
    async def test_cache_update_existing_key(self):
        """기존 키 업데이트 테스트"""
        async with cache_context() as cache:
            # 초기 값 설정
            await cache.set("update_key", "initial_value")

            # 값 확인
            result = await cache.get("update_key")
            assert result.get() == "initial_value"

            # 값 업데이트
            await cache.set("update_key", "updated_value")

            # 업데이트된 값 확인
            result = await cache.get("update_key")
            assert result.get() == "updated_value"

    @pytest.mark.asyncio
    async def test_cache_nonexistent_key(self):
        """존재하지 않는 키 조회"""
        async with cache_context() as cache:
            result = await cache.get("nonexistent_key")
            assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_clear_all(self):
        """전체 캐시 삭제"""
        async with cache_context() as cache:
            # 여러 아이템 저장
            for i in range(5):
                await cache.set(f"key_{i}", f"value_{i}")

            # 전체 삭제
            if hasattr(cache, "clear"):
                result = await cache.clear()
                assert result.is_success()

                # 모든 키가 삭제되었는지 확인
                for i in range(5):
                    result = await cache.get(f"key_{i}")
                    assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_exists_operation(self):
        """키 존재 여부 확인"""
        async with cache_context() as cache:
            # 키 저장
            await cache.set("exists_key", "value")

            # EXISTS 연산
            if hasattr(cache, "exists"):
                result = await cache.exists("exists_key")
                assert result.is_success()
                assert result.get() is True

                result = await cache.exists("not_exists_key")
                assert result.is_success()
                assert result.get() is False

    @pytest.mark.asyncio
    async def test_cache_keys_operation(self):
        """모든 키 조회"""
        async with cache_context() as cache:
            # 여러 키 저장
            keys = ["key1", "key2", "key3"]
            for key in keys:
                await cache.set(key, f"value_{key}")

            # KEYS 연산
            if hasattr(cache, "keys"):
                result = await cache.keys()
                assert result.is_success()
                returned_keys = result.get()

                for key in keys:
                    assert key in returned_keys

    @pytest.mark.asyncio
    async def test_cache_mget_mset_operations(self):
        """다중 get/set 연산"""
        async with cache_context() as cache:
            # MSET
            if hasattr(cache, "mset"):
                items = {"mkey1": "mvalue1", "mkey2": "mvalue2", "mkey3": "mvalue3"}
                result = await cache.mset(items)
                assert result.is_success()

            # MGET
            if hasattr(cache, "mget"):
                keys = ["mkey1", "mkey2", "mkey3"]
                result = await cache.mget(keys)
                assert result.is_success()
                values = result.get()

                assert values["mkey1"] == "mvalue1"
                assert values["mkey2"] == "mvalue2"
                assert values["mkey3"] == "mvalue3"

    @pytest.mark.asyncio
    async def test_cache_data_types(self):
        """다양한 데이터 타입 저장"""
        async with cache_context() as cache:
            test_data = {
                "string": "test string",
                "integer": 42,
                "float": 3.14159,
                "boolean": True,
                "list": [1, 2, 3, 4, 5],
                "dict": {"nested": {"key": "value"}},
                "none": None,
            }

            # 각 데이터 타입 저장 및 조회
            for key, value in test_data.items():
                # 저장
                result = await cache.set(f"type_{key}", value)
                assert result.is_success()

                # 조회
                result = await cache.get(f"type_{key}")
                assert result.is_success()
                assert result.get() == value

    @pytest.mark.asyncio
    async def test_cache_size_limit(self):
        """캐시 크기 제한 테스트"""
        config = MemoryCacheConfig(max_size=5, eviction_policy="lru")
        cache = await create_memory_cache(config)

        try:
            # 최대 크기보다 많은 아이템 저장
            for i in range(10):
                await cache.set(f"size_key_{i}", f"value_{i}")

            # 캐시 크기 확인
            if hasattr(cache, "size"):
                result = await cache.size()
                if result.is_success():
                    assert result.get() <= 5
        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_cache_namespace(self):
        """네임스페이스 지원 테스트"""
        async with cache_context() as cache:
            # 네임스페이스가 지원되는 경우
            if hasattr(cache, "set_with_namespace"):
                # 다른 네임스페이스에 같은 키 저장
                await cache.set_with_namespace("ns1", "key", "value1")
                await cache.set_with_namespace("ns2", "key", "value2")

                # 각 네임스페이스에서 조회
                result = await cache.get_with_namespace("ns1", "key")
                assert result.get() == "value1"

                result = await cache.get_with_namespace("ns2", "key")
                assert result.get() == "value2"

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """캐시 통계 테스트"""
        async with cache_context() as cache:
            # 여러 연산 수행
            await cache.set("stats_key1", "value1")
            await cache.get("stats_key1")
            await cache.get("nonexistent")
            await cache.delete("stats_key1")

            # 통계 조회
            if hasattr(cache, "stats"):
                result = await cache.stats()
                if result.is_success():
                    stats = result.get()
                    # 통계 항목 확인
                    assert "hits" in stats or "misses" in stats or "sets" in stats

    @pytest.mark.asyncio
    async def test_cache_concurrent_access(self):
        """동시 접근 테스트"""
        async with cache_context() as cache:

            async def writer(prefix, count):
                for i in range(count):
                    await cache.set(f"{prefix}_{i}", f"value_{i}")

            async def reader(prefix, count):
                results = []
                for i in range(count):
                    result = await cache.get(f"{prefix}_{i}")
                    if result.is_success():
                        results.append(result.get())
                return results

            # 동시에 여러 writer 실행
            await asyncio.gather(
                writer("concurrent1", 10),
                writer("concurrent2", 10),
                writer("concurrent3", 10),
            )

            # 동시에 여러 reader 실행
            results = await asyncio.gather(
                reader("concurrent1", 10),
                reader("concurrent2", 10),
                reader("concurrent3", 10),
            )

            # 각 reader가 올바른 값을 읽었는지 확인
            for reader_results in results:
                assert len(reader_results) > 0
