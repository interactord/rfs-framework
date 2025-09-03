"""
Tests for ResultAsync extended methods

PR에서 요구된 ResultAsync 확장 메서드들의 테스트
- from_error, from_value 클래스 메서드
- unwrap_or_async, bind_async, map_async 인스턴스 메서드
"""

import asyncio
import pytest
from typing import Any

from rfs.core.result import Failure, Result, ResultAsync, Success


class TestResultAsyncExtensions:
    """ResultAsync 확장 메서드들 테스트"""
    
    def test_from_error_creates_failure_result(self):
        """from_error가 실패 상태의 ResultAsync를 생성하는지 테스트"""
        error_msg = "test error"
        async_result = ResultAsync.from_error(error_msg)
        
        # ResultAsync 타입 확인
        assert isinstance(async_result, ResultAsync)
        
        # 실제 실행해서 결과 확인
        async def check_result():
            result = await async_result.to_result()
            assert result.is_failure()
            assert result.unwrap_error() == error_msg
        
        asyncio.run(check_result())
    
    def test_from_value_creates_success_result(self):
        """from_value가 성공 상태의 ResultAsync를 생성하는지 테스트"""
        test_value = "test value"
        async_result = ResultAsync.from_value(test_value)
        
        # ResultAsync 타입 확인
        assert isinstance(async_result, ResultAsync)
        
        # 실제 실행해서 결과 확인
        async def check_result():
            result = await async_result.to_result()
            assert result.is_success()
            assert result.unwrap() == test_value
        
        asyncio.run(check_result())
    
    def test_unwrap_or_async_with_success(self):
        """성공 상태에서 unwrap_or_async가 값을 반환하는지 테스트"""
        test_value = 42
        default_value = 0
        
        async def test_unwrap():
            async_result = ResultAsync.from_value(test_value)
            actual_value = await async_result.unwrap_or_async(default_value)
            assert actual_value == test_value
        
        asyncio.run(test_unwrap())
    
    def test_unwrap_or_async_with_failure(self):
        """실패 상태에서 unwrap_or_async가 기본값을 반환하는지 테스트"""
        test_error = "test error"
        default_value = "default"
        
        async def test_unwrap():
            async_result = ResultAsync.from_error(test_error)
            actual_value = await async_result.unwrap_or_async(default_value)
            assert actual_value == default_value
        
        asyncio.run(test_unwrap())
    
    def test_bind_async_with_success(self):
        """성공 상태에서 bind_async가 함수를 적용하는지 테스트"""
        initial_value = "hello"
        
        async def transform_function(value: str) -> Result[str, str]:
            await asyncio.sleep(0.01)  # 비동기 작업 시뮬레이션
            return Success(value.upper())
        
        async def test_bind():
            async_result = ResultAsync.from_value(initial_value)
            bound_result = async_result.bind_async(transform_function)
            final_result = await bound_result.to_result()
            
            assert final_result.is_success()
            assert final_result.unwrap() == "HELLO"
        
        asyncio.run(test_bind())
    
    def test_bind_async_with_failure(self):
        """실패 상태에서 bind_async가 함수를 실행하지 않는지 테스트"""
        test_error = "original error"
        
        async def transform_function(value: Any) -> Result[str, str]:
            # 이 함수는 호출되지 않아야 함
            return Success("should not be called")
        
        async def test_bind():
            async_result = ResultAsync.from_error(test_error)
            bound_result = async_result.bind_async(transform_function)
            final_result = await bound_result.to_result()
            
            assert final_result.is_failure()
            assert final_result.unwrap_error() == test_error
        
        asyncio.run(test_bind())
    
    def test_bind_async_with_function_error(self):
        """bind_async에서 함수가 실패 Result를 반환하는 경우 테스트"""
        initial_value = "test"
        function_error = "function failed"
        
        async def failing_function(value: str) -> Result[str, str]:
            await asyncio.sleep(0.01)
            return Failure(function_error)
        
        async def test_bind():
            async_result = ResultAsync.from_value(initial_value)
            bound_result = async_result.bind_async(failing_function)
            final_result = await bound_result.to_result()
            
            assert final_result.is_failure()
            assert final_result.unwrap_error() == function_error
        
        asyncio.run(test_bind())
    
    def test_map_async_with_success(self):
        """성공 상태에서 map_async가 비동기 함수를 적용하는지 테스트"""
        initial_value = 10
        
        async def async_double(value: int) -> int:
            await asyncio.sleep(0.01)  # 비동기 작업 시뮬레이션
            return value * 2
        
        async def test_map():
            async_result = ResultAsync.from_value(initial_value)
            mapped_result = async_result.map_async(async_double)
            final_result = await mapped_result.to_result()
            
            assert final_result.is_success()
            assert final_result.unwrap() == 20
        
        asyncio.run(test_map())
    
    def test_map_async_with_failure(self):
        """실패 상태에서 map_async가 함수를 실행하지 않는지 테스트"""
        test_error = "original error"
        
        async def async_transform(value: Any) -> str:
            # 이 함수는 호출되지 않아야 함
            return "should not be called"
        
        async def test_map():
            async_result = ResultAsync.from_error(test_error)
            mapped_result = async_result.map_async(async_transform)
            final_result = await mapped_result.to_result()
            
            assert final_result.is_failure()
            assert final_result.unwrap_error() == test_error
        
        asyncio.run(test_map())
    
    def test_map_async_with_exception(self):
        """map_async에서 비동기 함수가 예외를 발생시키는 경우 테스트"""
        initial_value = "test"
        
        async def failing_async_function(value: str) -> str:
            await asyncio.sleep(0.01)
            raise ValueError("async function failed")
        
        async def test_map():
            async_result = ResultAsync.from_value(initial_value)
            mapped_result = async_result.map_async(failing_async_function)
            final_result = await mapped_result.to_result()
            
            assert final_result.is_failure()
            # 예외가 Result의 Failure로 변환되는지 확인
            error = final_result.unwrap_error()
            assert isinstance(error, ValueError)
            assert "async function failed" in str(error)
        
        asyncio.run(test_map())
    
    def test_chaining_multiple_operations(self):
        """여러 확장 메서드들을 체이닝해서 사용하는 경우 테스트"""
        initial_value = 5
        
        async def async_multiply(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 3
        
        async def async_transform(value: int) -> Result[str, str]:
            await asyncio.sleep(0.01)
            if value > 10:
                return Success(f"big_number_{value}")
            return Failure("too_small")
        
        async def test_chaining():
            # from_value -> map_async -> bind_async -> unwrap_or_async
            result_value = await (
                ResultAsync.from_value(initial_value)
                .map_async(async_multiply)  # 5 * 3 = 15
                .bind_async(async_transform)  # "big_number_15"
                .unwrap_or_async("default")
            )
            
            assert result_value == "big_number_15"
        
        asyncio.run(test_chaining())
    
    def test_chaining_with_early_failure(self):
        """체이닝 중 일찍 실패하는 경우 테스트"""
        async def async_failing_transform(value: int) -> Result[str, str]:
            await asyncio.sleep(0.01)
            return Failure("early_failure")
        
        async def async_should_not_call(value: str) -> str:
            # 이 함수는 호출되지 않아야 함
            return "should_not_be_called"
        
        async def test_early_failure():
            result_value = await (
                ResultAsync.from_value(10)
                .bind_async(async_failing_transform)  # 여기서 실패
                .map_async(async_should_not_call)     # 실행되지 않아야 함
                .unwrap_or_async("fallback")
            )
            
            assert result_value == "fallback"
        
        asyncio.run(test_early_failure())


class TestResultAsyncPRCompatibility:
    """PR에서 요구된 정확한 시그니처와 동작 확인"""
    
    def test_pr_example_usage_pattern(self):
        """PR 문서에 나온 사용 패턴이 동작하는지 테스트"""
        
        async def test_pr_pattern():
            # PR에서 요구한 패턴: AsyncResult.from_error("connection failed")
            error_result = ResultAsync.from_error("connection failed")
            result = await error_result.to_result()
            assert result.is_failure()
            assert result.unwrap_error() == "connection failed"
            
            # PR에서 요구한 패턴: AsyncResult.from_value(value)
            success_result = ResultAsync.from_value("success_data")
            result = await success_result.to_result()
            assert result.is_success()
            assert result.unwrap() == "success_data"
            
            # unwrap_or_async 사용
            default_value = await error_result.unwrap_or_async("default")
            assert default_value == "default"
        
        asyncio.run(test_pr_pattern())
    
    def test_compatibility_with_existing_resultasync(self):
        """기존 ResultAsync 메서드들과의 호환성 테스트"""
        
        async def test_compatibility():
            # 기존 방식으로 생성
            async def create_success():
                return Success("existing_way")
            
            existing_result = ResultAsync(create_success())
            
            # 새로운 확장 메서드들과 함께 사용
            combined_value = await existing_result.unwrap_or_async("fallback")
            assert combined_value == "existing_way"
            
            # 기존 메서드들도 정상 동작
            assert await existing_result.is_success()
            assert await existing_result.unwrap() == "existing_way"
        
        asyncio.run(test_compatibility())