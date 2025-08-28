"""
AsyncPipeline 성능 최적화 도구 단위 테스트

AsyncCache, AsyncBackpressureController, 병렬 처리 도구 등을 검증합니다.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, patch
from typing import List, Dict, Any

from rfs.async_pipeline import (
    AsyncPerformanceMonitor, AsyncBackpressureController,
    AsyncStreamProcessor, AsyncCache, PerformanceMetrics,
    parallel_map, async_cached, async_rate_limited,
    get_global_cache, get_global_monitor
)
from rfs.async_pipeline.async_result import AsyncResult


class TestAsyncCache:
    """AsyncCache 캐싱 시스템 테스트"""
    
    @pytest.mark.asyncio
    async def test_cache_basic_operations(self):
        """캐시 기본 연산 테스트"""
        cache = AsyncCache(max_size=100, ttl=1.0)
        
        # 캐시에 저장
        await cache.set("key1", "value1")
        await cache.set("key2", {"data": "complex_value"})
        
        # 캐시에서 조회
        value1 = await cache.get("key1")
        value2 = await cache.get("key2")
        
        assert value1 == "value1"
        assert value2 == {"data": "complex_value"}
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """캐시 미스 테스트"""
        cache = AsyncCache()
        
        value = await cache.get("nonexistent_key")
        assert value is None
        
        # 기본값 반환 테스트
        default_value = await cache.get("nonexistent_key", default="기본값")
        assert default_value == "기본값"
    
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """캐시 TTL 만료 테스트"""
        cache = AsyncCache(ttl=0.05)  # 50ms TTL
        
        await cache.set("expire_key", "expire_value")
        
        # 즉시 조회 - 값이 있어야 함
        value = await cache.get("expire_key")
        assert value == "expire_value"
        
        # TTL 만료 대기
        await asyncio.sleep(0.06)
        
        # 만료 후 조회 - None이어야 함
        value = await cache.get("expire_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_max_size_lru_eviction(self):
        """캐시 최대 크기 및 LRU 제거 테스트"""
        cache = AsyncCache(max_size=3)
        
        # 캐시 크기 초과하여 저장
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # 모든 값이 있는지 확인
        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        
        # key1을 다시 접근하여 최근 사용으로 만듦
        await cache.get("key1")
        
        # 새로운 키 추가 - key2가 제거되어야 함 (LRU)
        await cache.set("key4", "value4")
        
        assert await cache.get("key1") == "value1"  # 최근 사용됨
        assert await cache.get("key2") is None      # 제거됨
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"  # 새로 추가됨
    
    @pytest.mark.asyncio
    async def test_cache_clear_and_stats(self):
        """캐시 정리 및 통계 테스트"""
        cache = AsyncCache()
        
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # 통계 확인
        stats = cache.get_stats()
        assert stats["size"] == 2
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0
        
        # 캐시 정리
        await cache.clear()
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert cache.get_stats()["size"] == 0


class TestAsyncCachedDecorator:
    """@async_cached 데코레이터 테스트"""
    
    @pytest.mark.asyncio
    async def test_async_cached_function(self):
        """비동기 함수 캐싱 테스트"""
        call_count = 0
        
        @async_cached(ttl=1.0)
        async def expensive_operation(x: int, y: int) -> int:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # 시뮬레이션
            return x + y
        
        # 첫 번째 호출 - 실제 실행
        result1 = await expensive_operation(5, 3)
        assert result1 == 8
        assert call_count == 1
        
        # 두 번째 호출 - 캐시에서 반환
        result2 = await expensive_operation(5, 3)
        assert result2 == 8
        assert call_count == 1  # 호출 횟수 증가 안 함
        
        # 다른 매개변수 - 새로 실행
        result3 = await expensive_operation(10, 2)
        assert result3 == 12
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_async_cached_with_custom_key_func(self):
        """커스텀 키 함수가 있는 캐싱 테스트"""
        call_count = 0
        
        def custom_key(user_id: str, **kwargs) -> str:
            return f"user:{user_id}"
        
        @async_cached(ttl=1.0, key_func=custom_key)
        async def get_user_data(user_id: str, include_details: bool = False) -> dict:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {"user_id": user_id, "data": f"call_{call_count}"}
        
        # 같은 user_id, 다른 매개변수 - 커스텀 키로 인해 캐시됨
        result1 = await get_user_data("123", include_details=True)
        result2 = await get_user_data("123", include_details=False)
        
        assert result1 == result2  # 캐시된 결과
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_async_cached_error_handling(self):
        """캐싱 중 에러 처리 테스트"""
        call_count = 0
        
        @async_cached(ttl=1.0)
        async def sometimes_failing_func(should_fail: bool) -> str:
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ValueError("의도적 실패")
            return f"성공_{call_count}"
        
        # 성공 케이스 - 캐시됨
        result1 = await sometimes_failing_func(False)
        result2 = await sometimes_failing_func(False)
        
        assert result1 == result2
        assert call_count == 1
        
        # 실패 케이스 - 캐시되지 않음
        with pytest.raises(ValueError, match="의도적 실패"):
            await sometimes_failing_func(True)
        
        with pytest.raises(ValueError, match="의도적 실패"):
            await sometimes_failing_func(True)
        
        assert call_count == 3  # 실패한 호출은 캐시되지 않아 매번 호출


class TestAsyncRateLimit:
    """@async_rate_limited 레이트 리미터 테스트"""
    
    @pytest.mark.asyncio
    async def test_rate_limited_basic(self):
        """기본 레이트 리미팅 테스트"""
        call_times = []
        
        @async_rate_limited(calls_per_second=5.0)  # 초당 5회 호출 제한
        async def rate_limited_func(value: int) -> int:
            call_times.append(time.time())
            return value * 2
        
        start_time = time.time()
        
        # 10번 빠르게 호출
        results = []
        for i in range(10):
            result = await rate_limited_func(i)
            results.append(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 10번 호출을 5 calls/sec로 제한하면 최소 2초 필요
        # 실제로는 약간의 오버헤드 포함하여 1.8초 이상 소요되어야 함
        assert total_time >= 1.8
        assert len(results) == 10
        assert results == [i * 2 for i in range(10)]
    
    @pytest.mark.asyncio
    async def test_rate_limited_burst_allowed(self):
        """버스트 허용 레이트 리미팅 테스트"""
        @async_rate_limited(calls_per_second=2.0, burst_size=3)
        async def burst_limited_func(value: str) -> str:
            return f"처리됨_{value}"
        
        start_time = time.time()
        
        # 처음 3개는 버스트로 빠르게 처리
        results = []
        for i in range(3):
            result = await burst_limited_func(f"item_{i}")
            results.append(result)
        
        burst_time = time.time() - start_time
        
        # 버스트는 매우 빠르게 처리되어야 함 (< 0.1초)
        assert burst_time < 0.1
        assert len(results) == 3
        
        # 추가 호출은 레이트 제한 적용
        start_additional = time.time()
        result4 = await burst_limited_func("item_3")
        additional_time = time.time() - start_additional
        
        # 2 calls/sec 제한으로 약 0.5초 대기
        assert additional_time >= 0.4
        assert result4 == "처리됨_item_3"


class TestParallelMap:
    """parallel_map 병렬 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_parallel_map_basic(self):
        """기본 병렬 매핑 테스트"""
        async def slow_double(x: int) -> int:
            await asyncio.sleep(0.1)
            return x * 2
        
        items = [1, 2, 3, 4, 5]
        
        start_time = time.time()
        results = await parallel_map(slow_double, items, max_concurrency=5)
        end_time = time.time()
        
        # 순차 실행이면 0.5초, 병렬 실행이면 0.1초 정도
        assert (end_time - start_time) < 0.2
        
        # 결과 확인
        values = []
        for result in results:
            values.append(await result.unwrap_async())
        
        assert values == [2, 4, 6, 8, 10]
    
    @pytest.mark.asyncio
    async def test_parallel_map_concurrency_limit(self):
        """동시성 제한 테스트"""
        active_count = 0
        max_concurrent = 0
        
        async def track_concurrency(x: int) -> int:
            nonlocal active_count, max_concurrent
            active_count += 1
            max_concurrent = max(max_concurrent, active_count)
            
            await asyncio.sleep(0.05)
            
            active_count -= 1
            return x * 3
        
        items = list(range(10))
        results = await parallel_map(track_concurrency, items, max_concurrency=3)
        
        # 최대 동시 실행 수가 제한되었는지 확인
        assert max_concurrent <= 3
        
        # 결과 확인
        values = []
        for result in results:
            values.append(await result.unwrap_async())
        
        assert values == [i * 3 for i in range(10)]
    
    @pytest.mark.asyncio
    async def test_parallel_map_with_failures(self):
        """실패가 포함된 병렬 매핑 테스트"""
        async def sometimes_fail(x: int) -> int:
            await asyncio.sleep(0.01)
            if x % 3 == 0 and x != 0:  # 3, 6, 9... 에서 실패
                raise ValueError(f"의도적 실패: {x}")
            return x * 2
        
        items = list(range(10))  # 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
        results = await parallel_map(sometimes_fail, items, max_concurrency=5)
        
        # 개별 결과 확인
        for i, result in enumerate(results):
            if i % 3 == 0 and i != 0:  # 3, 6, 9에서 실패
                with pytest.raises(ValueError, match=f"의도적 실패: {i}"):
                    await result.unwrap_async()
            else:  # 나머지는 성공
                value = await result.unwrap_async()
                assert value == i * 2


class TestAsyncBackpressureController:
    """AsyncBackpressureController 백프레셔 제어 테스트"""
    
    @pytest.mark.asyncio
    async def test_backpressure_basic_flow_control(self):
        """기본 흐름 제어 테스트"""
        controller = AsyncBackpressureController(buffer_size=3)
        
        processed_items = []
        
        async def producer():
            for i in range(10):
                await controller.put(f"item_{i}")
            await controller.put(None)  # 종료 신호
        
        async def consumer():
            while True:
                item = await controller.get()
                if item is None:
                    break
                processed_items.append(item)
                await asyncio.sleep(0.01)  # 처리 시간 시뮬레이션
        
        # 생산자와 소비자 동시 실행
        await asyncio.gather(producer(), consumer())
        
        assert len(processed_items) == 10
        assert processed_items == [f"item_{i}" for i in range(10)]
    
    @pytest.mark.asyncio
    async def test_backpressure_overflow_protection(self):
        """버퍼 오버플로우 보호 테스트"""
        controller = AsyncBackpressureController(buffer_size=2, drop_on_overflow=True)
        
        # 빠르게 많은 아이템 추가 (버퍼 크기 초과)
        for i in range(5):
            try:
                await asyncio.wait_for(controller.put(f"item_{i}"), timeout=0.1)
            except asyncio.TimeoutError:
                break  # 버퍼가 가득 찬 경우
        
        # 소비
        consumed = []
        try:
            while True:
                item = await asyncio.wait_for(controller.get(), timeout=0.1)
                if item is None:
                    break
                consumed.append(item)
        except asyncio.TimeoutError:
            pass
        
        # 버퍼 크기만큼만 저장되었는지 확인
        assert len(consumed) <= 2
    
    @pytest.mark.asyncio
    async def test_backpressure_multiple_consumers(self):
        """다중 소비자 테스트"""
        controller = AsyncBackpressureController(buffer_size=5)
        consumer_results = [[] for _ in range(3)]
        
        async def producer():
            for i in range(15):
                await controller.put(f"item_{i}")
            # 소비자 수만큼 종료 신호 전송
            for _ in range(3):
                await controller.put(None)
        
        async def consumer(consumer_id: int):
            while True:
                item = await controller.get()
                if item is None:
                    break
                consumer_results[consumer_id].append(item)
                await asyncio.sleep(0.01)
        
        # 다중 소비자 실행
        tasks = [
            asyncio.create_task(producer()),
            asyncio.create_task(consumer(0)),
            asyncio.create_task(consumer(1)),
            asyncio.create_task(consumer(2))
        ]
        
        await asyncio.gather(*tasks)
        
        # 모든 아이템이 소비되었는지 확인
        total_consumed = sum(len(results) for results in consumer_results)
        assert total_consumed == 15
        
        # 각 소비자가 일정량 처리했는지 확인
        for results in consumer_results:
            assert len(results) > 0


class TestAsyncStreamProcessor:
    """AsyncStreamProcessor 스트림 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_stream_processor_basic(self):
        """기본 스트림 처리 테스트"""
        async def data_generator():
            for i in range(10):
                yield f"data_{i}"
                await asyncio.sleep(0.01)
        
        async def process_item(item: str) -> str:
            await asyncio.sleep(0.01)
            return f"processed_{item}"
        
        processor = AsyncStreamProcessor(
            generator=data_generator,
            processor_func=process_item,
            batch_size=3,
            max_concurrency=2
        )
        
        results = await processor.process_stream()
        
        assert len(results) == 10
        for i, result in enumerate(results):
            expected = f"processed_data_{i}"
            assert result == expected
    
    @pytest.mark.asyncio
    async def test_stream_processor_batching(self):
        """스트림 배치 처리 테스트"""
        batch_sizes = []
        
        async def batch_data_generator():
            for i in range(7):  # 배치 크기 3으로 나누어떨어지지 않는 수
                yield f"item_{i}"
        
        async def batch_processor(batch: List[str]) -> List[str]:
            batch_sizes.append(len(batch))
            await asyncio.sleep(0.01)
            return [f"batch_processed_{item}" for item in batch]
        
        processor = AsyncStreamProcessor(
            generator=batch_data_generator,
            processor_func=batch_processor,
            batch_size=3,
            enable_batching=True
        )
        
        results = await processor.process_stream()
        
        # 배치 크기 확인: [3, 3, 1]
        assert batch_sizes == [3, 3, 1]
        assert len(results) == 7
    
    @pytest.mark.asyncio
    async def test_stream_processor_error_handling(self):
        """스트림 처리 에러 핸들링 테스트"""
        async def error_prone_generator():
            for i in range(5):
                if i == 3:
                    raise RuntimeError("생성기 에러")
                yield f"item_{i}"
        
        async def process_item(item: str) -> str:
            if "item_1" in item:
                raise ValueError("처리 에러")
            return f"processed_{item}"
        
        processor = AsyncStreamProcessor(
            generator=error_prone_generator,
            processor_func=process_item,
            error_strategy="continue"  # 에러 시 계속 진행
        )
        
        results = await processor.process_stream()
        
        # 에러가 발생한 항목을 제외한 결과
        expected_results = [
            "processed_item_0",
            # item_1은 처리 에러로 제외
            "processed_item_2",
            # item_3, item_4는 생성기 에러로 제외
        ]
        
        assert len(results) == len(expected_results)
        for i, expected in enumerate(expected_results):
            assert results[i] == expected


class TestAsyncPerformanceMonitor:
    """AsyncPerformanceMonitor 성능 모니터링 테스트"""
    
    @pytest.mark.asyncio
    async def test_performance_monitor_basic_metrics(self):
        """기본 성능 메트릭 테스트"""
        monitor = AsyncPerformanceMonitor()
        
        async def monitored_operation(duration: float) -> str:
            async with monitor.measure("test_operation"):
                await asyncio.sleep(duration)
                return f"완료: {duration}"
        
        # 여러 번 실행하여 메트릭 수집
        await monitored_operation(0.1)
        await monitored_operation(0.05)
        await monitored_operation(0.15)
        
        metrics = monitor.get_metrics("test_operation")
        
        assert metrics.call_count == 3
        assert 0.25 < metrics.total_duration < 0.35  # 대략적인 총 시간
        assert 0.05 <= metrics.min_duration <= 0.06
        assert 0.15 <= metrics.max_duration <= 0.16
        assert 0.08 < metrics.avg_duration < 0.12
    
    @pytest.mark.asyncio
    async def test_performance_monitor_error_tracking(self):
        """에러 추적 성능 모니터링 테스트"""
        monitor = AsyncPerformanceMonitor()
        
        async def error_prone_operation(should_fail: bool) -> str:
            async with monitor.measure("error_test"):
                await asyncio.sleep(0.01)
                if should_fail:
                    raise RuntimeError("의도적 실패")
                return "성공"
        
        # 성공 케이스 2회
        await error_prone_operation(False)
        await error_prone_operation(False)
        
        # 실패 케이스 1회
        try:
            await error_prone_operation(True)
        except RuntimeError:
            pass
        
        metrics = monitor.get_metrics("error_test")
        
        assert metrics.call_count == 3
        assert metrics.success_count == 2
        assert metrics.error_count == 1
        assert metrics.success_rate == 2/3
    
    def test_performance_monitor_global_instance(self):
        """전역 성능 모니터 인스턴스 테스트"""
        monitor1 = get_global_monitor()
        monitor2 = get_global_monitor()
        
        # 동일한 인스턴스인지 확인
        assert monitor1 is monitor2
    
    @pytest.mark.asyncio
    async def test_performance_monitor_concurrent_operations(self):
        """동시 실행 성능 모니터링 테스트"""
        monitor = AsyncPerformanceMonitor()
        
        async def concurrent_operation(operation_id: str) -> str:
            async with monitor.measure("concurrent_test"):
                await asyncio.sleep(0.1)
                return f"완료: {operation_id}"
        
        # 5개 동시 실행
        tasks = [
            concurrent_operation(f"op_{i}") 
            for i in range(5)
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 병렬 실행으로 0.1초 정도 소요
        assert (end_time - start_time) < 0.15
        assert len(results) == 5
        
        metrics = monitor.get_metrics("concurrent_test")
        assert metrics.call_count == 5
        
        # 각 호출은 0.1초 정도 소요
        for call_duration in metrics.duration_history:
            assert 0.08 < call_duration < 0.12


class TestGlobalCacheAndMonitor:
    """전역 캐시 및 모니터 인스턴스 테스트"""
    
    def test_global_cache_singleton(self):
        """전역 캐시 싱글톤 테스트"""
        cache1 = get_global_cache()
        cache2 = get_global_cache()
        
        assert cache1 is cache2
        assert isinstance(cache1, AsyncCache)
    
    @pytest.mark.asyncio
    async def test_global_cache_persistence(self):
        """전역 캐시 데이터 지속성 테스트"""
        cache1 = get_global_cache()
        await cache1.set("global_key", "global_value")
        
        cache2 = get_global_cache()
        value = await cache2.get("global_key")
        
        assert value == "global_value"
    
    def test_global_monitor_singleton(self):
        """전역 모니터 싱글톤 테스트"""
        monitor1 = get_global_monitor()
        monitor2 = get_global_monitor()
        
        assert monitor1 is monitor2
        assert isinstance(monitor1, AsyncPerformanceMonitor)
    
    @pytest.mark.asyncio
    async def test_integrated_global_cache_and_monitor(self):
        """전역 캐시와 모니터 통합 테스트"""
        cache = get_global_cache()
        monitor = get_global_monitor()
        
        @async_cached(ttl=1.0)
        async def monitored_cached_function(x: int) -> int:
            async with monitor.measure("cached_function"):
                await asyncio.sleep(0.05)
                return x * x
        
        # 첫 번째 호출 - 실행 + 캐시 저장
        result1 = await monitored_cached_function(5)
        
        # 두 번째 호출 - 캐시에서 반환 (모니터링은 여전히 적용)
        result2 = await monitored_cached_function(5)
        
        assert result1 == result2 == 25
        
        # 모니터링 메트릭 확인
        metrics = monitor.get_metrics("cached_function")
        assert metrics.call_count >= 1  # 최소 1회 실행


if __name__ == "__main__":
    # 개별 테스트 실행을 위한 헬퍼
    asyncio.run(pytest.main([__file__, "-v"]))