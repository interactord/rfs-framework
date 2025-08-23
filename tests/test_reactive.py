"""
Reactive Streams Tests
"""

import pytest
import asyncio
from rfs.reactive import Flux, Mono

class TestFlux:
    """Flux 테스트"""
    
    @pytest.mark.asyncio
    async def test_flux_basic_operations(self):
        """기본 Flux 연산 테스트"""
        
        result = await (
            Flux.from_iterable([1, 2, 3, 4, 5])
            .map(lambda x: x * 2)
            .filter(lambda x: x > 5)
            .to_list()
        )
        
        assert result == [6, 8, 10]
    
    @pytest.mark.asyncio
    async def test_flux_buffer(self):
        """Flux 버퍼 테스트"""
        
        result = await (
            Flux.from_iterable([1, 2, 3, 4, 5, 6])
            .buffer(3)
            .to_list()
        )
        
        assert len(result) == 2
        assert result[0] == [1, 2, 3]
        assert result[1] == [4, 5, 6]
    
    @pytest.mark.asyncio
    async def test_flux_parallel(self):
        """Flux 병렬 처리 테스트"""
        
        async def slow_operation(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * x
        
        start_time = asyncio.get_event_loop().time()
        
        result = await (
            Flux.from_iterable([1, 2, 3, 4, 5])
            .map(slow_operation)
            .parallel(max_concurrency=3)
            .sequential()
            .to_list()
        )
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        assert set(result) == {1, 4, 9, 16, 25}
        assert duration < 0.05  # 병렬 처리로 빨라야 함
    
    @pytest.mark.asyncio
    async def test_flux_reduce(self):
        """Flux 리듀스 테스트"""
        
        result = await (
            Flux.from_iterable([1, 2, 3, 4, 5])
            .reduce(0, lambda acc, x: acc + x)
        )
        
        assert result == 15
    
    @pytest.mark.asyncio
    async def test_flux_zip(self):
        """Flux zip 테스트"""
        
        flux1 = Flux.from_iterable([1, 2, 3])
        flux2 = Flux.from_iterable(['a', 'b', 'c'])
        
        result = await flux1.zip_with(flux2, lambda x, y: f"{x}{y}").to_list()
        
        assert result == ["1a", "2b", "3c"]
    
    @pytest.mark.asyncio
    async def test_flux_error_handling(self):
        """Flux 에러 처리 테스트"""
        
        def risky_operation(x: int) -> int:
            if x == 3:
                raise ValueError("Error at 3")
            return x * 2
        
        result = await (
            Flux.from_iterable([1, 2, 3, 4, 5])
            .map(risky_operation)
            .on_error_continue(lambda e: None)
            .to_list()
        )
        
        # 3에서 에러가 발생하여 제외됨
        assert result == [2, 4, 8, 10]

class TestMono:
    """Mono 테스트"""
    
    @pytest.mark.asyncio
    async def test_mono_basic(self):
        """기본 Mono 테스트"""
        
        result = await (
            Mono.just(42)
            .map(lambda x: x * 2)
            .await_result()
        )
        
        assert result == 84
    
    @pytest.mark.asyncio
    async def test_mono_flatmap(self):
        """Mono flatMap 테스트"""
        
        result = await (
            Mono.just(10)
            .flat_map(lambda x: Mono.just(x + 5))
            .await_result()
        )
        
        assert result == 15
    
    @pytest.mark.asyncio
    async def test_mono_retry(self):
        """Mono 재시도 테스트"""
        
        attempt_count = 0
        
        def failing_operation(x: int) -> int:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Not ready yet")
            return x * 2
        
        result = await (
            Mono.from_callable(lambda: failing_operation(21))
            .retry(max_attempts=3)
            .await_result()
        )
        
        assert result == 42
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_mono_timeout(self):
        """Mono 타임아웃 테스트"""
        
        async def slow_operation():
            await asyncio.sleep(0.2)
            return "result"
        
        with pytest.raises(asyncio.TimeoutError):
            await (
                Mono.from_callable(slow_operation)
                .timeout(0.1)
                .await_result()
            )
    
    @pytest.mark.asyncio
    async def test_mono_error_handling(self):
        """Mono 에러 처리 테스트"""
        
        def failing_operation() -> str:
            raise ValueError("Something went wrong")
        
        result = await (
            Mono.from_callable(failing_operation)
            .on_error_return("default_value")
            .await_result()
        )
        
        assert result == "default_value"
    
    @pytest.mark.asyncio
    async def test_mono_switch_if_empty(self):
        """Mono switchIfEmpty 테스트"""
        
        result = await (
            Mono.empty()
            .switch_if_empty(Mono.just("fallback"))
            .await_result()
        )
        
        assert result == "fallback"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])