"""
AsyncResult 모나드 단위 테스트

AsyncResult 클래스의 모든 메서드와 에지 케이스를 검증합니다.
"""

import asyncio
import pytest
from typing import List

from rfs.async_pipeline import AsyncResult, async_success, async_failure
from rfs.core.result import Success, Failure


class TestAsyncResultBasic:
    """AsyncResult 기본 기능 테스트"""
    
    @pytest.mark.asyncio
    async def test_from_value_success(self):
        """성공 값으로부터 AsyncResult 생성 테스트"""
        result = AsyncResult.from_value(42)
        value = await result.unwrap_async()
        assert value == 42
    
    @pytest.mark.asyncio
    async def test_from_error_failure(self):
        """에러로부터 AsyncResult 생성 테스트"""
        error_msg = "테스트 에러"
        result = AsyncResult.from_error(error_msg)
        
        with pytest.raises(Exception):
            await result.unwrap_async()
    
    @pytest.mark.asyncio
    async def test_from_async_success(self):
        """성공하는 비동기 함수로부터 생성 테스트"""
        async def success_func():
            await asyncio.sleep(0.01)
            return "성공"
        
        result = AsyncResult.from_async(success_func)
        value = await result.unwrap_async()
        assert value == "성공"
    
    @pytest.mark.asyncio
    async def test_from_async_failure(self):
        """실패하는 비동기 함수로부터 생성 테스트"""
        async def fail_func():
            await asyncio.sleep(0.01)
            raise ValueError("비동기 실패")
        
        result = AsyncResult.from_async(fail_func)
        
        with pytest.raises(ValueError, match="비동기 실패"):
            await result.unwrap_async()


class TestAsyncResultChaining:
    """AsyncResult 체이닝 기능 테스트"""
    
    @pytest.mark.asyncio
    async def test_bind_async_success_chain(self):
        """성공적인 bind_async 체이닝 테스트"""
        async def double(x: int) -> int:
            return x * 2
            
        async def add_ten(x: int) -> int:
            return x + 10
        
        result = await (
            AsyncResult.from_value(5)
            .bind_async(lambda x: AsyncResult.from_async(lambda: double(x)))
            .bind_async(lambda x: AsyncResult.from_async(lambda: add_ten(x)))
        )
        
        value = await result.unwrap_async()
        assert value == 20  # (5 * 2) + 10
    
    @pytest.mark.asyncio
    async def test_bind_async_failure_short_circuit(self):
        """bind_async에서 실패 시 단축 평가 테스트"""
        call_count = 0
        
        async def increment_and_fail(x: int) -> int:
            nonlocal call_count
            call_count += 1
            raise ValueError("중간 실패")
        
        async def should_not_be_called(x: int) -> int:
            nonlocal call_count
            call_count += 1000  # 호출되면 안 되는 함수
            return x
        
        result = await (
            AsyncResult.from_value(10)
            .bind_async(lambda x: AsyncResult.from_async(lambda: increment_and_fail(x)))
            .bind_async(lambda x: AsyncResult.from_async(lambda: should_not_be_called(x)))
        )
        
        assert call_count == 1  # 첫 번째 함수만 호출됨
        with pytest.raises(ValueError, match="중간 실패"):
            await result.unwrap_async()
    
    @pytest.mark.asyncio
    async def test_map_async_success(self):
        """map_async 성공 케이스 테스트"""
        async def async_transform(x: str) -> str:
            await asyncio.sleep(0.01)
            return x.upper()
        
        result = await (
            AsyncResult.from_value("hello world")
            .map_async(async_transform)
        )
        
        value = await result.unwrap_async()
        assert value == "HELLO WORLD"
    
    @pytest.mark.asyncio
    async def test_map_sync_success(self):
        """map_sync 성공 케이스 테스트"""
        def sync_transform(x: int) -> str:
            return f"결과: {x}"
        
        result = await (
            AsyncResult.from_value(42)
            .map_sync(sync_transform)
        )
        
        value = await result.unwrap_async()
        assert value == "결과: 42"
    
    @pytest.mark.asyncio
    async def test_mixed_sync_async_chain(self):
        """동기/비동기 함수 혼합 체이닝 테스트"""
        def sync_double(x: int) -> int:
            return x * 2
        
        async def async_add_five(x: int) -> int:
            await asyncio.sleep(0.01)
            return x + 5
        
        def sync_to_string(x: int) -> str:
            return f"최종값: {x}"
        
        result = await (
            AsyncResult.from_value(10)
            .map_sync(sync_double)
            .bind_async(lambda x: AsyncResult.from_async(lambda: async_add_five(x)))
            .map_sync(sync_to_string)
        )
        
        value = await result.unwrap_async()
        assert value == "최종값: 25"  # ((10 * 2) + 5)


class TestAsyncResultErrorHandling:
    """AsyncResult 에러 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_unwrap_or_else_async_success(self):
        """성공 시 unwrap_or_else_async 테스트"""
        async def fallback_func(error):
            return "폴백값"
        
        result = AsyncResult.from_value("정상값")
        value = await result.unwrap_or_else_async(fallback_func)
        assert value == "정상값"
    
    @pytest.mark.asyncio
    async def test_unwrap_or_else_async_failure(self):
        """실패 시 unwrap_or_else_async 테스트"""
        async def fallback_func(error):
            return f"폴백: {error}"
        
        result = AsyncResult.from_error("원본 에러")
        value = await result.unwrap_or_else_async(fallback_func)
        assert value == "폴백: 원본 에러"
    
    @pytest.mark.asyncio
    async def test_to_result_success(self):
        """성공 케이스의 to_result 테스트"""
        async_result = AsyncResult.from_value("테스트 값")
        regular_result = await async_result.to_result()
        
        assert regular_result.is_success()
        assert regular_result.unwrap() == "테스트 값"
    
    @pytest.mark.asyncio
    async def test_to_result_failure(self):
        """실패 케이스의 to_result 테스트"""
        async_result = AsyncResult.from_error("테스트 에러")
        regular_result = await async_result.to_result()
        
        assert regular_result.is_failure()
        assert regular_result.unwrap_error() == "테스트 에러"


class TestAsyncResultUtilityFunctions:
    """AsyncResult 편의 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_async_success_helper(self):
        """async_success 편의 함수 테스트"""
        result = async_success("성공값")
        value = await result.unwrap_async()
        assert value == "성공값"
    
    @pytest.mark.asyncio
    async def test_async_failure_helper(self):
        """async_failure 편의 함수 테스트"""
        result = async_failure("실패값")
        
        with pytest.raises(Exception):
            await result.unwrap_async()


class TestAsyncResultPerformance:
    """AsyncResult 성능 테스트"""
    
    @pytest.mark.asyncio
    async def test_large_chain_performance(self):
        """긴 체이닝의 성능 테스트"""
        import time
        
        def sync_increment(x: int) -> int:
            return x + 1
        
        start_time = time.time()
        
        # 100번 체이닝
        result = AsyncResult.from_value(0)
        for _ in range(100):
            result = result.map_sync(sync_increment)
        
        final_value = await result.unwrap_async()
        end_time = time.time()
        
        assert final_value == 100
        # 체이닝이 1초 이내에 완료되어야 함
        assert (end_time - start_time) < 1.0
    
    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """동시 실행 성능 테스트"""
        async def slow_operation(x: int) -> int:
            await asyncio.sleep(0.1)
            return x * 2
        
        # 여러 AsyncResult를 동시에 실행
        tasks = []
        for i in range(5):
            result = AsyncResult.from_async(lambda i=i: slow_operation(i))
            tasks.append(result.unwrap_async())
        
        import time
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 순차 실행이면 0.5초, 동시 실행이면 0.1초 정도
        assert (end_time - start_time) < 0.2
        assert results == [0, 2, 4, 6, 8]


class TestAsyncResultEdgeCases:
    """AsyncResult 에지 케이스 테스트"""
    
    @pytest.mark.asyncio
    async def test_none_value_handling(self):
        """None 값 처리 테스트"""
        result = AsyncResult.from_value(None)
        value = await result.unwrap_async()
        assert value is None
    
    @pytest.mark.asyncio
    async def test_empty_string_handling(self):
        """빈 문자열 처리 테스트"""
        result = AsyncResult.from_value("")
        value = await result.unwrap_async()
        assert value == ""
    
    @pytest.mark.asyncio
    async def test_nested_async_result_flatten(self):
        """중첩 AsyncResult 평탄화 테스트"""
        inner_result = AsyncResult.from_value("내부값")
        
        async def return_async_result(x):
            return inner_result
        
        # 중첩된 AsyncResult를 올바르게 처리하는지 확인
        outer_result = AsyncResult.from_async(lambda: return_async_result("외부값"))
        
        # 실제 구현에서는 이를 어떻게 처리할지에 따라 테스트 조정 필요
        # 현재는 기본적인 동작 확인
        result = await outer_result.to_result()
        assert result.is_success()
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """타임아웃 처리 테스트"""
        async def slow_operation():
            await asyncio.sleep(1.0)  # 1초 대기
            return "완료"
        
        result = AsyncResult.from_async(slow_operation)
        
        # 짧은 타임아웃으로 테스트
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(result.unwrap_async(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_exception_context_preservation(self):
        """예외 컨텍스트 보존 테스트"""
        async def complex_failure():
            try:
                raise ValueError("원본 에러")
            except ValueError:
                raise RuntimeError("감싸진 에러") from ValueError("원본 에러")
        
        result = AsyncResult.from_async(complex_failure)
        
        with pytest.raises(RuntimeError, match="감싸진 에러"):
            await result.unwrap_async()


if __name__ == "__main__":
    # 개별 테스트 실행을 위한 헬퍼
    asyncio.run(pytest.main([__file__, "-v"]))