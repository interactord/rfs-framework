"""
RFS Cache Performance Tests (RFS v4.3)

캐시 시스템 성능 테스트
"""

import asyncio

import pytest

from rfs.cache.memory_cache import MemoryCache, MemoryCacheConfig


class TestCachePerformance:
    """캐시 성능 테스트"""

    @pytest.mark.asyncio
    async def test_memory_cache_performance_basic_operations(self, performance_timer):
        """기본 연산 성능 테스트"""
        config = MemoryCacheConfig(max_size=10000)
        cache = MemoryCache(config)
        await cache.connect()

        try:
            performance_timer.start()

            # 1000개 데이터 저장
            for i in range(1000):
                await cache.set(f"perf_key_{i}", f"value_{i}")

            performance_timer.stop()

            # 1000번 저장이 1초 미만이어야 함
            assert performance_timer.elapsed < 1.0

            performance_timer.start()

            # 1000개 데이터 조회
            for i in range(1000):
                result = await cache.get(f"perf_key_{i}")
                assert result.unwrap() == f"value_{i}"

            performance_timer.stop()

            # 1000번 조회가 0.5초 미만이어야 함
            assert performance_timer.elapsed < 0.5

        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_memory_cache_concurrent_performance(self, performance_timer):
        """동시 연산 성능 테스트"""
        config = MemoryCacheConfig(max_size=5000)
        cache = MemoryCache(config)
        await cache.connect()

        try:

            async def worker(worker_id: int, operations: int):
                for i in range(operations):
                    key = f"worker_{worker_id}_key_{i}"
                    value = f"worker_{worker_id}_value_{i}"
                    await cache.set(key, value)
                    result = await cache.get(key)
                    assert result.unwrap() == value

            performance_timer.start()

            # 10개 워커가 각각 100번 연산 (총 2000번)
            tasks = [worker(i, 100) for i in range(10)]
            await asyncio.gather(*tasks)

            performance_timer.stop()

            # 2000번 연산이 2초 미만이어야 함
            assert performance_timer.elapsed < 2.0

        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cache_size", [100, 1000, 10000])
    async def test_memory_cache_scaling_performance(
        self, cache_size, performance_timer
    ):
        """캐시 크기별 성능 테스트"""
        config = MemoryCacheConfig(max_size=cache_size * 2)
        cache = MemoryCache(config)
        await cache.connect()

        try:
            performance_timer.start()

            # 지정된 크기만큼 데이터 저장
            for i in range(cache_size):
                await cache.set(f"scale_key_{i}", f"value_{i}")

            # 전체 데이터 조회
            for i in range(cache_size):
                result = await cache.get(f"scale_key_{i}")
                assert result.unwrap() == f"value_{i}"

            performance_timer.stop()

            # 크기별 성능 기준 (선형적이지 않을 수 있음)
            expected_time = cache_size / 1000.0  # 1000개당 1초 기준
            assert performance_timer.elapsed < max(expected_time, 0.1)

        finally:
            await cache.disconnect()
