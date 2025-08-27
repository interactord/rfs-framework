"""
RFS Framework Cache TTL 및 만료 단위 테스트

캐시 아이템의 TTL(Time To Live) 및 만료 처리 기능을 테스트합니다.
"""

import asyncio
import os

# 테스트 헬퍼 import
import sys
import time
from datetime import datetime, timedelta

import pytest

from rfs.cache.memory_cache import MemoryCache, MemoryCacheConfig
from rfs.core.result import Failure, Success

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from tests.utils.async_helpers import cache_context, create_memory_cache


class TestCacheTTL:
    """캐시 TTL 및 만료 테스트"""

    @pytest.mark.asyncio
    async def test_cache_ttl_basic(self):
        """기본 TTL 기능 테스트"""
        # lazy_expiration이 True인 경우를 위해 설정 명시
        config = MemoryCacheConfig(
            max_size=100, lazy_expiration=True  # 명시적으로 lazy expiration 활성화
        )
        cache = await create_memory_cache(config)

        try:
            # TTL과 함께 아이템 저장
            result = await cache.set("ttl_key", "ttl_value", ttl=1)
            assert result.is_success()

            # 즉시 조회 - 성공해야 함
            result = await cache.get("ttl_key")
            assert result.is_success()
            assert result.get() == "ttl_value"

            # TTL 만료 대기
            await asyncio.sleep(1.2)

            # 만료 후 조회 - 실패해야 함
            result = await cache.get("ttl_key")
            assert result.is_failure() or result.get() is None
        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_cache_ttl_update(self):
        """TTL 업데이트 테스트"""
        async with cache_context() as cache:
            # 짧은 TTL로 저장
            await cache.set("update_ttl_key", "value", ttl=1)

            # TTL 업데이트 (더 긴 TTL로)
            await cache.set("update_ttl_key", "new_value", ttl=5)

            # 원래 TTL이 만료된 후에도 조회 가능해야 함
            await asyncio.sleep(2)
            result = await cache.get("update_ttl_key")
            assert result.is_success()
            assert result.get() == "new_value"

    @pytest.mark.asyncio
    async def test_cache_ttl_zero(self):
        """TTL 0 (즉시 만료) 테스트"""
        async with cache_context() as cache:
            # TTL 0으로 저장
            result = await cache.set("zero_ttl", "value", ttl=0)

            # 즉시 조회 - 이미 만료되어야 함
            result = await cache.get("zero_ttl")
            assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_ttl_infinite(self):
        """무한 TTL (만료 없음) 테스트"""
        async with cache_context() as cache:
            # TTL 없이 저장 (무한)
            await cache.set("infinite_ttl", "value")

            # 시간이 지나도 조회 가능해야 함
            await asyncio.sleep(1)
            result = await cache.get("infinite_ttl")
            assert result.is_success()
            assert result.get() == "value"

    @pytest.mark.asyncio
    async def test_cache_expire_command(self):
        """EXPIRE 명령 테스트"""
        async with cache_context() as cache:
            # TTL 없이 저장
            await cache.set("expire_key", "value")

            # EXPIRE 명령으로 TTL 설정
            if hasattr(cache, "expire"):
                result = await cache.expire("expire_key", 1)
                assert result.is_success()

                # 만료 전 조회
                result = await cache.get("expire_key")
                assert result.is_success()

                # 만료 후 조회
                await asyncio.sleep(1.5)
                result = await cache.get("expire_key")
                assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_ttl_remaining(self):
        """남은 TTL 조회 테스트"""
        async with cache_context() as cache:
            # TTL과 함께 저장
            await cache.set("ttl_remaining", "value", ttl=10)

            # TTL 조회
            if hasattr(cache, "ttl"):
                result = await cache.ttl("ttl_remaining")
                if result.is_success():
                    remaining = result.get()
                    assert 8 <= remaining <= 10  # 약간의 시간차 허용

                # 존재하지 않는 키의 TTL
                result = await cache.ttl("nonexistent")
                if result.is_success():
                    assert result.get() == -2 or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_persist_command(self):
        """PERSIST 명령 테스트 (TTL 제거)"""
        async with cache_context() as cache:
            # TTL과 함께 저장
            await cache.set("persist_key", "value", ttl=2)

            # PERSIST 명령으로 TTL 제거
            if hasattr(cache, "persist"):
                result = await cache.persist("persist_key")
                assert result.is_success()

                # TTL이 제거되어 만료되지 않아야 함
                await asyncio.sleep(3)
                result = await cache.get("persist_key")
                assert result.is_success()
                assert result.get() == "value"

    @pytest.mark.asyncio
    async def test_cache_lazy_expiration(self):
        """지연 만료 (Lazy Expiration) 테스트"""
        config = MemoryCacheConfig(max_size=100, lazy_expiration=True)
        cache = await create_memory_cache(config)

        try:
            # TTL과 함께 여러 아이템 저장
            for i in range(5):
                await cache.set(f"lazy_{i}", f"value_{i}", ttl=1)

            # 만료 대기
            await asyncio.sleep(1.5)

            # 지연 만료는 접근 시점에 체크
            for i in range(5):
                result = await cache.get(f"lazy_{i}")
                assert result.is_failure() or result.get() is None
        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_cache_active_expiration(self):
        """능동 만료 (Active Expiration) 테스트"""
        config = MemoryCacheConfig(
            max_size=100, lazy_expiration=False, cleanup_interval=1  # 1초마다 정리
        )
        cache = await create_memory_cache(config)

        try:
            # TTL과 함께 아이템 저장
            await cache.set("active_expire", "value", ttl=1)

            # 정리 주기 대기
            await asyncio.sleep(2)

            # 능동 만료로 이미 제거되어야 함
            result = await cache.get("active_expire")
            assert result.is_failure() or result.get() is None
        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_cache_ttl_with_different_units(self):
        """다양한 시간 단위의 TTL 테스트"""
        async with cache_context() as cache:
            # 초 단위
            await cache.set("ttl_seconds", "value", ttl=2)

            # 밀리초 단위 (지원하는 경우)
            if hasattr(cache, "psetex"):
                await cache.psetex("ttl_milliseconds", 500, "value")
                await asyncio.sleep(0.6)
                result = await cache.get("ttl_milliseconds")
                assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_ttl_batch_operations(self):
        """배치 TTL 작업 테스트"""
        async with cache_context() as cache:
            # 여러 아이템을 다른 TTL로 저장
            items = [
                ("ttl_1s", "value1", 1),
                ("ttl_2s", "value2", 2),
                ("ttl_3s", "value3", 3),
                ("ttl_none", "value4", None),
            ]

            for key, value, ttl in items:
                await cache.set(key, value, ttl=ttl)

            # 1.5초 후 확인
            await asyncio.sleep(1.5)

            # ttl_1s는 만료
            result = await cache.get("ttl_1s")
            assert result.is_failure() or result.get() is None

            # ttl_2s, ttl_3s는 아직 유효
            result = await cache.get("ttl_2s")
            assert result.is_success()

            result = await cache.get("ttl_3s")
            assert result.is_success()

            # ttl_none은 계속 유효
            result = await cache.get("ttl_none")
            assert result.is_success()

    @pytest.mark.asyncio
    async def test_cache_ttl_precision(self):
        """TTL 정밀도 테스트"""
        async with cache_context() as cache:
            # 정확한 시간 측정
            start_time = time.time()
            await cache.set("precision_key", "value", ttl=1)

            # 0.8초 후 - 아직 유효해야 함
            await asyncio.sleep(0.8)
            result = await cache.get("precision_key")
            assert result.is_success()

            # 추가 0.5초 후 - 만료되어야 함 (총 1.3초)
            await asyncio.sleep(0.5)
            result = await cache.get("precision_key")
            assert result.is_failure() or result.get() is None

            elapsed = time.time() - start_time
            assert 1.0 <= elapsed <= 1.5  # 더 넓은 오차 허용

    @pytest.mark.asyncio
    async def test_cache_refresh_ttl_basic(self):
        """기본 TTL 갱신 테스트"""
        async with cache_context() as cache:
            # TTL과 함께 아이템 저장
            await cache.set("refresh_key", "value", ttl=2)

            # 1초 후 TTL 갱신 (갱신 시점부터 3초)
            await asyncio.sleep(1)
            result = await cache.refresh_ttl("refresh_key", 3)
            assert result.is_success()

            # 원래 TTL(2초)이 지난 후에도 여전히 유효해야 함
            await asyncio.sleep(1.5)  # 총 2.5초
            result = await cache.get("refresh_key")
            assert result.is_success()
            assert result.get() == "value"

            # 갱신 시점부터 3초 후에는 만료되어야 함 (총 4초)
            await asyncio.sleep(2)  # 총 4.5초 (갱신 후 3.5초)
            result = await cache.get("refresh_key")
            assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_refresh_ttl_original(self):
        """원래 TTL로 갱신 테스트"""
        async with cache_context() as cache:
            # TTL과 함께 아이템 저장
            await cache.set("refresh_orig_key", "value", ttl=3)

            # 2초 후 원래 TTL로 갱신 (ttl=None)
            await asyncio.sleep(2)
            result = await cache.refresh_ttl("refresh_orig_key")
            assert result.is_success()

            # 원래 TTL(3초)만큼 더 기다려도 유효해야 함
            await asyncio.sleep(2.5)  # 원래 만료 시점 + 2.5초
            result = await cache.get("refresh_orig_key")
            assert result.is_success()
            assert result.get() == "value"

    @pytest.mark.asyncio
    async def test_cache_refresh_ttl_nonexistent(self):
        """존재하지 않는 키의 TTL 갱신 테스트"""
        async with cache_context() as cache:
            # 존재하지 않는 키의 TTL 갱신 시도
            result = await cache.refresh_ttl("nonexistent_key", 10)
            assert result.is_failure()
            assert "키가 존재하지 않음" in result.get_error()

    @pytest.mark.asyncio
    async def test_cache_refresh_ttl_no_original_ttl(self):
        """원래 TTL이 없는 키의 갱신 테스트"""
        async with cache_context() as cache:
            # TTL 없이 저장
            await cache.set("no_ttl_key", "value")

            # 원래 TTL로 갱신 시도 (변경 없어야 함)
            result = await cache.refresh_ttl("no_ttl_key")
            assert result.is_success()

            # 여전히 유효해야 함
            result = await cache.get("no_ttl_key")
            assert result.is_success()
            assert result.get() == "value"

    @pytest.mark.asyncio
    async def test_cache_persist_command(self):
        """PERSIST 명령 테스트 (TTL 제거)"""
        async with cache_context() as cache:
            # TTL과 함께 저장
            await cache.set("persist_key", "value", ttl=2)

            # PERSIST 명령으로 TTL 제거
            result = await cache.persist("persist_key")
            assert result.is_success()

            # TTL이 제거되어 만료되지 않아야 함
            await asyncio.sleep(3)
            result = await cache.get("persist_key")
            assert result.is_success()
            assert result.get() == "value"

    @pytest.mark.asyncio
    async def test_cache_persist_nonexistent(self):
        """존재하지 않는 키의 PERSIST 테스트"""
        async with cache_context() as cache:
            # 존재하지 않는 키의 PERSIST 시도
            result = await cache.persist("nonexistent_key")
            assert result.is_failure()
            assert "키가 존재하지 않음" in result.get_error()

    @pytest.mark.asyncio
    async def test_cache_refresh_ttl_zero(self):
        """TTL을 0으로 갱신하여 즉시 만료시키는 테스트"""
        async with cache_context() as cache:
            # TTL과 함께 저장
            await cache.set("zero_refresh_key", "value", ttl=10)

            # TTL을 0으로 갱신 (즉시 만료)
            result = await cache.refresh_ttl("zero_refresh_key", 0)
            assert result.is_success()

            # 즉시 만료되어야 함
            result = await cache.get("zero_refresh_key")
            assert result.is_failure() or result.get() is None

    @pytest.mark.asyncio
    async def test_cache_refresh_ttl_multiple_times(self):
        """여러 번 TTL 갱신 테스트"""
        async with cache_context() as cache:
            # TTL과 함께 저장
            await cache.set("multi_refresh_key", "value", ttl=2)

            # 첫 번째 갱신
            await asyncio.sleep(1)
            result = await cache.refresh_ttl("multi_refresh_key", 3)
            assert result.is_success()

            # 두 번째 갱신
            await asyncio.sleep(1)
            result = await cache.refresh_ttl("multi_refresh_key", 5)
            assert result.is_success()

            # 최종 TTL 확인
            await asyncio.sleep(2)  # 원래 TTL은 이미 지남
            result = await cache.get("multi_refresh_key")
            assert result.is_success()  # 마지막 갱신으로 인해 유효
            assert result.get() == "value"
