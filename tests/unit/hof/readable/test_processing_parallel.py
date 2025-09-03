"""
병렬 처리 기능 테스트

ParallelDataProcessor와 AsyncDataProcessor의 기능을 검증합니다.
"""

import asyncio
import pytest
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from unittest.mock import patch, MagicMock

from rfs.hof.readable.processing import (
    ParallelDataProcessor, 
    AsyncDataProcessor,
    extract_from_parallel,
    quick_parallel_process,
    quick_async_process
)


class TestParallelDataProcessor:
    """ParallelDataProcessor 클래스 테스트"""
    
    def test_parallel_transform_with_threads(self):
        """스레드를 사용한 병렬 변환 테스트"""
        data = [1, 2, 3, 4, 5]
        processor = ParallelDataProcessor(data)
        
        def slow_transform(x):
            time.sleep(0.01)  # 짧은 지연 시뮬레이션
            return x * 2
        
        start_time = time.time()
        result = processor.parallel_transform(slow_transform, max_workers=3)
        parallel_time = time.time() - start_time
        
        # 순차 처리 시간과 비교
        start_time = time.time()
        sequential_result = [slow_transform(x) for x in data]
        sequential_time = time.time() - start_time
        
        assert result.collect() == [2, 4, 6, 8, 10]
        assert result.collect() == sequential_result
        assert parallel_time < sequential_time  # 병렬 처리가 더 빨라야 함
    
    def test_parallel_transform_with_processes(self):
        """프로세스를 사용한 병렬 변환 테스트"""
        data = [1, 2, 3, 4]
        processor = ParallelDataProcessor(data)
        
        def cpu_intensive_task(x):
            # CPU 집약적 작업 시뮬레이션
            total = 0
            for i in range(10000):
                total += x * i
            return total
        
        result = processor.parallel_transform(
            cpu_intensive_task, 
            max_workers=2, 
            use_processes=True
        )
        
        # 결과가 정확한지 확인
        expected = [cpu_intensive_task(x) for x in data]
        assert result.collect() == expected
    
    def test_parallel_filter(self):
        """병렬 필터링 테스트"""
        data = list(range(20))
        processor = ParallelDataProcessor(data)
        
        def slow_predicate(x):
            time.sleep(0.001)  # 짧은 지연
            return x % 2 == 0
        
        result = processor.parallel_filter(slow_predicate, max_workers=4)
        
        expected = [x for x in data if x % 2 == 0]
        assert result.collect() == expected
    
    def test_parallel_reduce(self):
        """병렬 리듀스 테스트"""
        data = [1, 2, 3, 4, 5]
        processor = ParallelDataProcessor(data)
        
        def add_func(acc, x):
            return acc + x
        
        result = processor.parallel_reduce(add_func, 0, max_workers=2)
        
        assert result == sum(data)
    
    def test_chaining_parallel_operations(self):
        """병렬 연산들의 체이닝 테스트"""
        data = list(range(10))
        
        result = (ParallelDataProcessor(data)
                 .parallel_transform(lambda x: x * 2, max_workers=2)
                 .parallel_filter(lambda x: x > 5, max_workers=2)
                 .collect())
        
        expected = [x * 2 for x in data if x * 2 > 5]
        assert result == expected
    
    def test_error_handling_in_parallel_transform(self):
        """병렬 변환 중 에러 처리 테스트"""
        data = [1, 2, 0, 4]  # 0으로 나눌 때 에러 발생
        processor = ParallelDataProcessor(data)
        
        def risky_transform(x):
            return 10 / x  # x=0일 때 ZeroDivisionError
        
        with pytest.raises(ZeroDivisionError):
            processor.parallel_transform(risky_transform, max_workers=2).collect()
    
    def test_max_workers_default(self):
        """max_workers 기본값 테스트"""
        data = [1, 2, 3]
        processor = ParallelDataProcessor(data)
        
        # max_workers=None일 때 기본값 사용
        result = processor.parallel_transform(lambda x: x * 2)
        assert result.collect() == [2, 4, 6]


class TestAsyncDataProcessor:
    """AsyncDataProcessor 클래스 테스트"""
    
    @pytest.mark.asyncio
    async def test_async_transform(self):
        """비동기 변환 테스트"""
        data = [1, 2, 3, 4]
        processor = AsyncDataProcessor(data)
        
        async def async_double(x):
            await asyncio.sleep(0.001)  # 짧은 비동기 지연
            return x * 2
        
        result = await processor.async_transform(async_double, max_concurrent=2)
        assert result.collect() == [2, 4, 6, 8]
    
    @pytest.mark.asyncio
    async def test_async_filter(self):
        """비동기 필터링 테스트"""
        data = list(range(10))
        processor = AsyncDataProcessor(data)
        
        async def async_is_even(x):
            await asyncio.sleep(0.001)
            return x % 2 == 0
        
        result = await processor.async_filter(async_is_even, max_concurrent=3)
        expected = [x for x in data if x % 2 == 0]
        assert result.collect() == expected
    
    @pytest.mark.asyncio
    async def test_async_chaining(self):
        """비동기 연산 체이닝 테스트"""
        data = [1, 2, 3, 4, 5]
        
        async def async_multiply(x):
            await asyncio.sleep(0.001)
            return x * 3
        
        async def async_is_large(x):
            await asyncio.sleep(0.001)
            return x > 6
        
        result = await (AsyncDataProcessor(data)
                       .async_transform(async_multiply, max_concurrent=2)
                       .async_filter(async_is_large, max_concurrent=2))
        
        expected = [x * 3 for x in data if x * 3 > 6]
        assert result.collect() == expected
    
    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """비동기 처리 중 에러 처리 테스트"""
        data = [1, 2, 0, 4]
        processor = AsyncDataProcessor(data)
        
        async def risky_async_transform(x):
            await asyncio.sleep(0.001)
            return 10 / x  # x=0일 때 에러 발생
        
        with pytest.raises(ZeroDivisionError):
            await processor.async_transform(risky_async_transform, max_concurrent=2)


class TestConvenienceFunctions:
    """편의 함수들 테스트"""
    
    def test_extract_from_parallel(self):
        """extract_from_parallel 함수 테스트"""
        data = [1, 2, 3, 4, 5]
        
        processor = extract_from_parallel(data)
        assert isinstance(processor, ParallelDataProcessor)
        
        result = processor.parallel_transform(lambda x: x * 2, max_workers=2)
        assert result.collect() == [2, 4, 6, 8, 10]
    
    def test_quick_parallel_process(self):
        """quick_parallel_process 함수 테스트"""
        data = [1, 2, 3, 4, 5]
        
        # transform 연산
        result = quick_parallel_process(
            data=data,
            operations=['transform'],
            transform_func=lambda x: x * 2,
            max_workers=2
        )
        
        assert result == [2, 4, 6, 8, 10]
    
    def test_quick_parallel_process_with_filter(self):
        """필터링을 포함한 quick_parallel_process 테스트"""
        data = list(range(10))
        
        result = quick_parallel_process(
            data=data,
            operations=['filter'],
            filter_func=lambda x: x % 2 == 0,
            max_workers=2
        )
        
        expected = [x for x in data if x % 2 == 0]
        assert result == expected
    
    def test_quick_parallel_process_chaining(self):
        """연산 체이닝을 포함한 quick_parallel_process 테스트"""
        data = list(range(10))
        
        result = quick_parallel_process(
            data=data,
            operations=['transform', 'filter'],
            transform_func=lambda x: x * 2,
            filter_func=lambda x: x > 5,
            max_workers=2
        )
        
        expected = [x * 2 for x in data if x * 2 > 5]
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_quick_async_process(self):
        """quick_async_process 함수 테스트"""
        data = [1, 2, 3, 4]
        
        async def async_operation(x):
            await asyncio.sleep(0.001)
            return x * 2
        
        result = await quick_async_process(
            data=data,
            operations=[async_operation],
            max_concurrent=2
        )
        
        assert result == [2, 4, 6, 8]
    
    @pytest.mark.asyncio
    async def test_quick_async_process_multiple_operations(self):
        """여러 연산을 포함한 quick_async_process 테스트"""
        data = [1, 2, 3, 4, 5]
        
        async def async_multiply(x):
            await asyncio.sleep(0.001)
            return x * 2
        
        async def async_add(x):
            await asyncio.sleep(0.001)
            return x + 1
        
        result = await quick_async_process(
            data=data,
            operations=[async_multiply, async_add],
            max_concurrent=2
        )
        
        expected = [(x * 2) + 1 for x in data]
        assert result == expected


class TestPerformanceComparison:
    """성능 비교 테스트"""
    
    def test_parallel_vs_sequential_performance(self):
        """병렬 처리와 순차 처리 성능 비교"""
        data = list(range(50))  # 적당한 크기의 데이터
        
        def cpu_task(x):
            time.sleep(0.01)  # I/O 지연 시뮬레이션
            return x ** 2
        
        # 순차 처리
        start_time = time.time()
        sequential_result = [cpu_task(x) for x in data]
        sequential_time = time.time() - start_time
        
        # 병렬 처리
        start_time = time.time()
        parallel_result = (ParallelDataProcessor(data)
                          .parallel_transform(cpu_task, max_workers=4)
                          .collect())
        parallel_time = time.time() - start_time
        
        assert sequential_result == parallel_result
        assert parallel_time < sequential_time * 0.8  # 병렬 처리가 20% 이상 빨라야 함
        
        print(f"순차 처리 시간: {sequential_time:.3f}초")
        print(f"병렬 처리 시간: {parallel_time:.3f}초")
        print(f"성능 향상: {(sequential_time / parallel_time):.2f}배")


@pytest.fixture
def sample_data():
    """테스트용 샘플 데이터"""
    return [
        {"id": 1, "value": 10, "category": "A"},
        {"id": 2, "value": 20, "category": "B"},
        {"id": 3, "value": 30, "category": "A"},
        {"id": 4, "value": 40, "category": "B"},
        {"id": 5, "value": 50, "category": "A"},
    ]


class TestRealWorldScenarios:
    """실제 사용 사례 테스트"""
    
    def test_data_processing_pipeline(self, sample_data):
        """실제 데이터 처리 파이프라인 테스트"""
        
        def validate_data(item):
            time.sleep(0.001)  # 검증 지연 시뮬레이션
            return item['value'] > 0
        
        def enrich_data(item):
            time.sleep(0.001)  # 데이터 보강 지연
            return {
                **item,
                'processed': True,
                'double_value': item['value'] * 2
            }
        
        def filter_category_a(item):
            return item['category'] == 'A'
        
        result = (ParallelDataProcessor(sample_data)
                 .parallel_filter(validate_data, max_workers=2)
                 .parallel_transform(enrich_data, max_workers=2)
                 .parallel_filter(filter_category_a, max_workers=2)
                 .collect())
        
        # 카테고리 A인 항목들만 처리되었는지 확인
        assert len(result) == 3  # A 카테고리 항목은 3개
        for item in result:
            assert item['category'] == 'A'
            assert item['processed'] is True
            assert 'double_value' in item
    
    @pytest.mark.asyncio
    async def test_async_api_processing_pipeline(self, sample_data):
        """비동기 API 처리 파이프라인 테스트"""
        
        async def fetch_additional_data(item):
            await asyncio.sleep(0.01)  # API 호출 시뮬레이션
            return {
                **item,
                'external_data': f"api_data_{item['id']}"
            }
        
        async def validate_async(item):
            await asyncio.sleep(0.005)  # 비동기 검증
            return item['value'] >= 20
        
        result = await (AsyncDataProcessor(sample_data)
                       .async_transform(fetch_additional_data, max_concurrent=3)
                       .async_filter(validate_async, max_concurrent=2))
        
        # value >= 20인 항목들만 남아있는지 확인
        result_items = result.collect()
        assert len(result_items) == 3  # value가 20, 30, 40, 50인 항목들
        for item in result_items:
            assert item['value'] >= 20
            assert 'external_data' in item