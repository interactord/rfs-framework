"""
Unit tests for Flux reactive streams (RFS Framework)
"""

import asyncio
from typing import List

import pytest

from rfs.reactive.flux import Flux


class TestFluxCreation:
    """Test Flux creation methods"""

    @pytest.mark.asyncio
    async def test_just_creation(self):
        """Test creating Flux with just method"""
        flux = Flux.just(1, 2, 3)
        result = await flux.collect_list()
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_from_iterable(self):
        """Test creating Flux from iterable"""
        items = [4, 5, 6]
        flux = Flux.from_iterable(items)
        result = await flux.collect_list()
        assert result == [4, 5, 6]

    @pytest.mark.asyncio
    async def test_range(self):
        """Test creating Flux with range"""
        flux = Flux.range(0, 5)
        result = await flux.collect_list()
        assert result == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_empty(self):
        """Test creating empty Flux"""
        flux = Flux.empty()
        result = await flux.collect_list()
        assert result == []


class TestFluxTransformations:
    """Test Flux transformation operations"""

    @pytest.mark.asyncio
    async def test_map(self):
        """Test map transformation"""
        flux = Flux.just(1, 2, 3)
        result = await flux.map(lambda x: x * 2).collect_list()
        assert result == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_filter(self):
        """Test filter operation"""
        flux = Flux.range(0, 10)
        result = await flux.filter(lambda x: x % 2 == 0).collect_list()
        assert result == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_flat_map(self):
        """Test flat_map operation"""
        flux = Flux.just(1, 2, 3)
        result = await flux.flat_map(lambda x: Flux.just(x, x * 10)).collect_list()
        assert result == [1, 10, 2, 20, 3, 30]

    @pytest.mark.asyncio
    async def test_take(self):
        """Test take operation"""
        flux = Flux.range(0, 10)
        result = await flux.take(3).collect_list()
        assert result == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_skip(self):
        """Test skip operation"""
        flux = Flux.range(0, 5)
        result = await flux.skip(2).collect_list()
        assert result == [2, 3, 4]

    @pytest.mark.asyncio
    async def test_distinct(self):
        """Test distinct operation"""
        flux = Flux.just(1, 2, 2, 3, 1, 4)
        result = await flux.distinct().collect_list()
        assert result == [1, 2, 3, 4]


class TestFluxAggregation:
    """Test Flux aggregation operations"""

    @pytest.mark.asyncio
    async def test_reduce(self):
        """Test reduce operation"""
        flux = Flux.just(1, 2, 3, 4)
        result = await flux.reduce(0, lambda acc, x: acc + x).collect_list()
        assert result == [10]

    @pytest.mark.asyncio
    async def test_count(self):
        """Test count operation"""
        flux = Flux.range(0, 5)
        result = await flux.count()
        assert result == 5

    @pytest.mark.asyncio
    async def test_any(self):
        """Test any predicate"""
        flux = Flux.just(1, 2, 3, 4, 5)
        result = await flux.any(lambda x: x > 3)
        assert result is True

        result2 = await flux.any(lambda x: x > 10)
        assert result2 is False

    @pytest.mark.asyncio
    async def test_all(self):
        """Test all predicate"""
        flux = Flux.just(2, 4, 6)
        result = await flux.all(lambda x: x % 2 == 0)
        assert result is True

        flux2 = Flux.just(2, 3, 4)
        result2 = await flux2.all(lambda x: x % 2 == 0)
        assert result2 is False


class TestFluxCombination:
    """Test Flux combination operations"""

    @pytest.mark.asyncio
    async def test_zip(self):
        """Test zip operation"""
        flux1 = Flux.just(1, 2, 3)
        flux2 = Flux.just("a", "b", "c")
        result = await flux1.zip(flux2).collect_list()
        assert result == [(1, "a"), (2, "b"), (3, "c")]

    @pytest.mark.asyncio
    async def test_merge(self):
        """Test merge operation"""
        flux1 = Flux.just(1, 2)
        flux2 = Flux.just(3, 4)
        result = await Flux.merge(flux1, flux2).collect_list()
        assert set(result) == {1, 2, 3, 4}

    @pytest.mark.asyncio
    async def test_concat(self):
        """Test concat operation"""
        flux1 = Flux.just(1, 2)
        flux2 = Flux.just(3, 4)
        result = await Flux.concat(flux1, flux2).collect_list()
        assert result == [1, 2, 3, 4]


class TestFluxBuffering:
    """Test Flux buffering operations"""

    @pytest.mark.asyncio
    async def test_buffer(self):
        """Test buffer operation"""
        flux = Flux.range(0, 6)
        result = await flux.buffer(2).collect_list()
        assert result == [[0, 1], [2, 3], [4, 5]]

    @pytest.mark.asyncio
    async def test_window(self):
        """Test window by size"""
        flux = Flux.range(0, 5)
        windows = await flux.window(size=2).collect_list()
        assert len(windows) == 3

        # Collect items from first window
        first_window = windows[0]
        items = await first_window.collect_list()
        assert items == [0, 1]


class TestFluxErrorHandling:
    """Test Flux error handling"""

    @pytest.mark.asyncio
    async def test_on_error_return(self):
        """Test error recovery with default value"""

        async def source_with_error():
            yield 1
            yield 2
            raise ValueError("test error")
            yield 3

        flux = Flux(source_with_error)
        result = await flux.on_error_return(-1).collect_list()
        assert result == [1, 2, -1]

    @pytest.mark.asyncio
    async def test_on_error_continue(self):
        """Test continuing on error"""

        async def source_with_error():
            yield 1
            raise ValueError("test error")
            yield 2  # This won't be reached

        flux = Flux(source_with_error)
        result = await flux.on_error_continue().collect_list()
        assert result == [1]


class TestFluxParallel:
    """Test Flux parallel processing"""

    @pytest.mark.asyncio
    async def test_parallel_processing(self):
        """Test parallel processing"""
        flux = Flux.range(0, 10)
        result = await flux.parallel(parallelism=2).map(lambda x: x * 2).collect_list()
        # Result order may vary due to parallel processing
        assert set(result) == set(range(0, 20, 2))
        assert len(result) == 10


class TestFluxSubscription:
    """Test Flux subscription patterns"""

    @pytest.mark.asyncio
    async def test_subscribe(self):
        """Test subscribe with callbacks"""
        collected = []
        error = None
        completed = False

        def on_next(item):
            collected.append(item)

        def on_error(e):
            nonlocal error
            error = e

        def on_complete():
            nonlocal completed
            completed = True

        flux = Flux.just(1, 2, 3)
        await flux.subscribe(on_next, on_error, on_complete)

        assert collected == [1, 2, 3]
        assert error is None
        assert completed is True


class TestFluxThrottling:
    """Test Flux throttling operations"""

    @pytest.mark.asyncio
    async def test_throttle(self):
        """Test throttle operation"""
        flux = Flux.range(0, 5)
        # Throttle to 10 elements per 0.1 seconds
        result = await flux.throttle(elements=10, duration=0.1).collect_list()
        assert result == [0, 1, 2, 3, 4]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
