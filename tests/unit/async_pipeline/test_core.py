"""
AsyncPipeline 코어 기능 단위 테스트

AsyncPipeline, AsyncPipelineBuilder 및 관련 유틸리티 함수들을 검증합니다.
"""

import asyncio
import pytest
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock

from rfs.async_pipeline import (
    AsyncPipeline, AsyncPipelineBuilder, async_pipe, 
    execute_async_pipeline, parallel_pipeline_execution
)
from rfs.async_pipeline.async_result import AsyncResult
from rfs.core.result import Success, Failure


class TestAsyncPipelineBasic:
    """AsyncPipeline 기본 기능 테스트"""
    
    @pytest.mark.asyncio
    async def test_empty_pipeline_execution(self):
        """빈 파이프라인 실행 테스트"""
        pipeline = AsyncPipeline([])
        result = await pipeline.execute("입력값")
        value = await result.unwrap_async()
        assert value == "입력값"  # 빈 파이프라인은 입력값을 그대로 반환
    
    @pytest.mark.asyncio
    async def test_single_sync_operation(self):
        """단일 동기 연산 테스트"""
        def double(x: int) -> int:
            return x * 2
        
        pipeline = AsyncPipeline([double])
        result = await pipeline.execute(5)
        value = await result.unwrap_async()
        assert value == 10
    
    @pytest.mark.asyncio
    async def test_single_async_operation(self):
        """단일 비동기 연산 테스트"""
        async def async_double(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2
        
        pipeline = AsyncPipeline([async_double])
        result = await pipeline.execute(7)
        value = await result.unwrap_async()
        assert value == 14
    
    @pytest.mark.asyncio
    async def test_mixed_sync_async_pipeline(self):
        """동기/비동기 혼합 파이프라인 테스트"""
        def sync_add_one(x: int) -> int:
            return x + 1
        
        async def async_multiply_three(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 3
        
        def sync_to_string(x: int) -> str:
            return f"결과: {x}"
        
        pipeline = AsyncPipeline([sync_add_one, async_multiply_three, sync_to_string])
        result = await pipeline.execute(5)
        value = await result.unwrap_async()
        assert value == "결과: 18"  # ((5 + 1) * 3) = 18
    
    @pytest.mark.asyncio
    async def test_pipeline_with_error(self):
        """에러가 발생하는 파이프라인 테스트"""
        def normal_operation(x: int) -> int:
            return x + 10
        
        async def failing_operation(x: int) -> int:
            raise ValueError("파이프라인 실행 중 에러")
        
        def should_not_execute(x: int) -> int:
            assert False, "이 함수는 실행되면 안 됩니다"
        
        pipeline = AsyncPipeline([normal_operation, failing_operation, should_not_execute])
        result = await pipeline.execute(5)
        
        with pytest.raises(ValueError, match="파이프라인 실행 중 에러"):
            await result.unwrap_async()


class TestAsyncPipelineBuilder:
    """AsyncPipelineBuilder 테스트"""
    
    @pytest.mark.asyncio
    async def test_builder_pattern_basic(self):
        """빌더 패턴 기본 사용 테스트"""
        def add_five(x: int) -> int:
            return x + 5
        
        async def multiply_two(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2
        
        pipeline = (
            AsyncPipelineBuilder()
            .add_step(add_five)
            .add_step(multiply_two)
            .build()
        )
        
        result = await pipeline.execute(10)
        value = await result.unwrap_async()
        assert value == 30  # (10 + 5) * 2
    
    @pytest.mark.asyncio
    async def test_builder_with_conditional_steps(self):
        """조건부 스텝을 포함한 빌더 테스트"""
        def increment(x: int) -> int:
            return x + 1
        
        async def async_double(x: int) -> int:
            return x * 2
        
        builder = AsyncPipelineBuilder().add_step(increment)
        
        # 조건에 따라 스텝 추가
        condition = True
        if condition:
            builder.add_step(async_double)
        
        pipeline = builder.build()
        result = await pipeline.execute(5)
        value = await result.unwrap_async()
        assert value == 12  # (5 + 1) * 2
    
    @pytest.mark.asyncio
    async def test_builder_with_error_handling_strategy(self):
        """에러 처리 전략이 있는 빌더 테스트"""
        def normal_step(x: int) -> int:
            return x + 10
        
        async def failing_step(x: int) -> int:
            if x > 15:
                raise ValueError("값이 너무 큼")
            return x * 2
        
        # 에러 처리 전략 설정
        builder = (
            AsyncPipelineBuilder()
            .add_step(normal_step)
            .add_step(failing_step)
            .with_error_strategy("continue_on_error")  # 가상의 전략
        )
        
        pipeline = builder.build()
        result = await pipeline.execute(10)
        
        # 실제 에러 처리 전략에 따라 결과가 달라질 수 있음
        with pytest.raises(ValueError):
            await result.unwrap_async()


class TestAsyncPipeUtilityFunction:
    """async_pipe 팩토리 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_async_pipe_factory(self):
        """async_pipe 팩토리 함수 기본 테스트"""
        def step1(x: str) -> str:
            return x.upper()
        
        async def step2(x: str) -> str:
            await asyncio.sleep(0.01)
            return f"처리된: {x}"
        
        def step3(x: str) -> str:
            return f"[{x}]"
        
        pipeline = async_pipe(step1, step2, step3)
        result = await pipeline.execute("hello")
        value = await result.unwrap_async()
        assert value == "[처리된: HELLO]"
    
    @pytest.mark.asyncio
    async def test_async_pipe_empty(self):
        """빈 async_pipe 테스트"""
        pipeline = async_pipe()
        result = await pipeline.execute("테스트")
        value = await result.unwrap_async()
        assert value == "테스트"
    
    @pytest.mark.asyncio
    async def test_async_pipe_single_operation(self):
        """단일 연산 async_pipe 테스트"""
        def single_op(x: int) -> int:
            return x ** 2
        
        pipeline = async_pipe(single_op)
        result = await pipeline.execute(4)
        value = await result.unwrap_async()
        assert value == 16


class TestExecuteAsyncPipeline:
    """execute_async_pipeline 직접 실행 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_execute_pipeline_directly(self):
        """파이프라인 직접 실행 테스트"""
        operations = [
            lambda x: x + 1,
            lambda x: x * 2,
            lambda x: f"최종: {x}"
        ]
        
        result = await execute_async_pipeline(operations, 5)
        value = await result.unwrap_async()
        assert value == "최종: 12"  # (5 + 1) * 2 = 12
    
    @pytest.mark.asyncio
    async def test_execute_pipeline_with_async_operations(self):
        """비동기 연산이 포함된 직접 실행 테스트"""
        async def async_op1(x: int) -> int:
            await asyncio.sleep(0.01)
            return x + 5
        
        def sync_op(x: int) -> int:
            return x * 3
        
        async def async_op2(x: int) -> str:
            await asyncio.sleep(0.01)
            return f"결과값: {x}"
        
        operations = [async_op1, sync_op, async_op2]
        result = await execute_async_pipeline(operations, 2)
        value = await result.unwrap_async()
        assert value == "결과값: 21"  # (2 + 5) * 3 = 21


class TestParallelPipelineExecution:
    """parallel_pipeline_execution 병렬 실행 테스트"""
    
    @pytest.mark.asyncio
    async def test_parallel_pipeline_basic(self):
        """기본 병렬 파이프라인 실행 테스트"""
        async def slow_operation(x: int) -> int:
            await asyncio.sleep(0.1)
            return x * 2
        
        pipelines = [
            async_pipe(slow_operation),
            async_pipe(slow_operation),
            async_pipe(slow_operation)
        ]
        
        inputs = [1, 2, 3]
        
        import time
        start_time = time.time()
        results = await parallel_pipeline_execution(pipelines, inputs)
        end_time = time.time()
        
        # 순차 실행이면 0.3초, 병렬 실행이면 0.1초 정도
        assert (end_time - start_time) < 0.2
        
        # 결과 확인
        values = []
        for result in results:
            values.append(await result.unwrap_async())
        
        assert values == [2, 4, 6]
    
    @pytest.mark.asyncio
    async def test_parallel_with_different_pipelines(self):
        """다른 파이프라인들의 병렬 실행 테스트"""
        pipeline1 = async_pipe(lambda x: x + 1, lambda x: x * 2)
        pipeline2 = async_pipe(lambda x: x * 3, lambda x: f"결과: {x}")
        pipeline3 = async_pipe(lambda x: x ** 2)
        
        pipelines = [pipeline1, pipeline2, pipeline3]
        inputs = [5, 2, 4]
        
        results = await parallel_pipeline_execution(pipelines, inputs)
        values = []
        for result in results:
            values.append(await result.unwrap_async())
        
        expected = [
            12,      # (5 + 1) * 2 = 12
            "결과: 6",  # 2 * 3 = 6, "결과: 6" 
            16       # 4 ** 2 = 16
        ]
        assert values == expected
    
    @pytest.mark.asyncio
    async def test_parallel_with_failures(self):
        """실패가 포함된 병렬 실행 테스트"""
        def success_operation(x: int) -> int:
            return x + 10
        
        def failing_operation(x: int) -> int:
            raise ValueError(f"에러: {x}")
        
        pipeline1 = async_pipe(success_operation)
        pipeline2 = async_pipe(failing_operation)
        pipeline3 = async_pipe(success_operation)
        
        pipelines = [pipeline1, pipeline2, pipeline3]
        inputs = [1, 2, 3]
        
        results = await parallel_pipeline_execution(pipelines, inputs)
        
        # 첫 번째와 세 번째는 성공, 두 번째는 실패
        assert await results[0].unwrap_async() == 11
        
        with pytest.raises(ValueError, match="에러: 2"):
            await results[1].unwrap_async()
        
        assert await results[2].unwrap_async() == 13


class TestAsyncPipelineAdvanced:
    """AsyncPipeline 고급 기능 테스트"""
    
    @pytest.mark.asyncio
    async def test_pipeline_with_context_preservation(self):
        """컨텍스트 보존 테스트"""
        context_values = []
        
        def capture_context_sync(x: str) -> str:
            context_values.append(f"sync: {x}")
            return x.upper()
        
        async def capture_context_async(x: str) -> str:
            await asyncio.sleep(0.01)
            context_values.append(f"async: {x}")
            return f"처리됨_{x}"
        
        pipeline = async_pipe(capture_context_sync, capture_context_async)
        result = await pipeline.execute("test")
        value = await result.unwrap_async()
        
        assert value == "처리됨_TEST"
        assert context_values == ["sync: test", "async: TEST"]
    
    @pytest.mark.asyncio
    async def test_pipeline_performance_monitoring(self):
        """파이프라인 성능 모니터링 테스트"""
        execution_times = []
        
        async def monitored_operation(x: int) -> int:
            import time
            start = time.time()
            await asyncio.sleep(0.05)
            end = time.time()
            execution_times.append(end - start)
            return x * 2
        
        pipeline = async_pipe(monitored_operation, monitored_operation)
        result = await pipeline.execute(5)
        value = await result.unwrap_async()
        
        assert value == 20  # 5 * 2 * 2
        assert len(execution_times) == 2
        # 각 연산이 대략 0.05초 소요되었는지 확인
        for exec_time in execution_times:
            assert 0.04 < exec_time < 0.1
    
    @pytest.mark.asyncio
    async def test_pipeline_with_resource_cleanup(self):
        """리소스 정리가 있는 파이프라인 테스트"""
        cleanup_calls = []
        
        class ResourceManager:
            def __init__(self, name: str):
                self.name = name
                self.is_open = True
            
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                cleanup_calls.append(f"cleanup: {self.name}")
                self.is_open = False
            
            def process(self, data):
                if not self.is_open:
                    raise RuntimeError("리소스가 이미 닫혔습니다")
                return f"{self.name}: {data}"
        
        def use_resource_sync(x: str) -> str:
            with ResourceManager("sync_resource") as resource:
                return resource.process(x)
        
        async def use_resource_async(x: str) -> str:
            with ResourceManager("async_resource") as resource:
                await asyncio.sleep(0.01)
                return resource.process(x)
        
        pipeline = async_pipe(use_resource_sync, use_resource_async)
        result = await pipeline.execute("데이터")
        value = await result.unwrap_async()
        
        assert value == "async_resource: sync_resource: 데이터"
        assert "cleanup: sync_resource" in cleanup_calls
        assert "cleanup: async_resource" in cleanup_calls


class TestAsyncPipelineEdgeCases:
    """AsyncPipeline 에지 케이스 테스트"""
    
    @pytest.mark.asyncio
    async def test_pipeline_with_none_values(self):
        """None 값 처리 파이프라인 테스트"""
        def handle_none(x) -> str:
            if x is None:
                return "None 처리됨"
            return str(x)
        
        async def async_none_handler(x: str) -> str:
            await asyncio.sleep(0.01)
            return f"비동기: {x}"
        
        pipeline = async_pipe(handle_none, async_none_handler)
        result = await pipeline.execute(None)
        value = await result.unwrap_async()
        assert value == "비동기: None 처리됨"
    
    @pytest.mark.asyncio
    async def test_pipeline_with_large_data(self):
        """대용량 데이터 처리 파이프라인 테스트"""
        def create_large_list(x: int) -> List[int]:
            return list(range(x))
        
        async def process_large_list(data: List[int]) -> int:
            await asyncio.sleep(0.01)
            return sum(data)
        
        def format_result(x: int) -> str:
            return f"합계: {x:,}"
        
        pipeline = async_pipe(create_large_list, process_large_list, format_result)
        result = await pipeline.execute(1000)
        value = await result.unwrap_async()
        
        expected_sum = sum(range(1000))  # 499500
        assert value == f"합계: {expected_sum:,}"
    
    @pytest.mark.asyncio
    async def test_deeply_nested_pipeline(self):
        """깊이 중첩된 파이프라인 테스트"""
        operations = []
        
        # 50개의 연산을 생성 (동기/비동기 번갈아)
        for i in range(50):
            if i % 2 == 0:
                # 동기 연산
                operations.append(lambda x, i=i: x + i)
            else:
                # 비동기 연산
                async def async_op(x, i=i):
                    await asyncio.sleep(0.001)
                    return x + i
                operations.append(async_op)
        
        pipeline = AsyncPipeline(operations)
        result = await pipeline.execute(0)
        value = await result.unwrap_async()
        
        # 0 + 0 + 1 + 2 + 3 + ... + 49 = sum(0 to 49) = 1225
        expected = sum(range(50))
        assert value == expected


if __name__ == "__main__":
    # 개별 테스트 실행을 위한 헬퍼
    asyncio.run(pytest.main([__file__, "-v"]))