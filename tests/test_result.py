"""
Result Type Tests
"""

import pytest
import asyncio
from rfs.core.result import (
    Result, Success, Failure, success, failure,
    try_except, async_try_except, pipe_results,
    sequence, traverse, lift, lift2,
    first_success, partition_results
)

class TestResult:
    """Result 타입 테스트"""
    
    def test_success_creation(self):
        """Success 생성 테스트"""
        result = success(42)
        
        assert result.is_success() is True
        assert result.is_failure() is False
        assert result.unwrap() == 42
        assert result.unwrap_or(0) == 42
    
    def test_failure_creation(self):
        """Failure 생성 테스트"""
        result = failure("error message")
        
        assert result.is_success() is False
        assert result.is_failure() is True
        assert result.unwrap_or(42) == 42
        
        with pytest.raises(ValueError):
            result.unwrap()
    
    def test_success_map(self):
        """Success map 테스트"""
        result = success(5).map(lambda x: x * 2)
        
        assert result.is_success() is True
        assert result.unwrap() == 10
    
    def test_failure_map(self):
        """Failure map 테스트"""
        result = failure("error").map(lambda x: x * 2)
        
        assert result.is_failure() is True
        assert result.unwrap_error() == "error"
    
    def test_success_bind(self):
        """Success bind (flatMap) 테스트"""
        def divide_by_two(x: int) -> Result[float, str]:
            return success(x / 2.0)
        
        result = success(10).bind(divide_by_two)
        
        assert result.is_success() is True
        assert result.unwrap() == 5.0
    
    def test_failure_bind(self):
        """Failure bind 테스트"""
        def divide_by_two(x: int) -> Result[float, str]:
            return success(x / 2.0)
        
        result = failure("error").bind(divide_by_two)
        
        assert result.is_failure() is True
        assert result.unwrap_error() == "error"
    
    def test_map_error(self):
        """에러 매핑 테스트"""
        result = failure("original error").map_error(lambda e: f"mapped: {e}")
        
        assert result.is_failure() is True
        assert result.unwrap_error() == "mapped: original error"
    
    def test_try_except_success(self):
        """try_except 성공 케이스"""
        result = try_except(lambda: 10 / 2)
        
        assert result.is_success() is True
        assert result.unwrap() == 5.0
    
    def test_try_except_failure(self):
        """try_except 실패 케이스"""
        result = try_except(lambda: 10 / 0)
        
        assert result.is_failure() is True
        assert isinstance(result.unwrap_error(), ZeroDivisionError)
    
    @pytest.mark.asyncio
    async def test_async_try_except_success(self):
        """async_try_except 성공 케이스"""
        async def async_operation():
            await asyncio.sleep(0.01)
            return 42
        
        result = await async_try_except(async_operation)
        
        assert result.is_success() is True
        assert result.unwrap() == 42
    
    @pytest.mark.asyncio
    async def test_async_try_except_failure(self):
        """async_try_except 실패 케이스"""
        async def failing_async_operation():
            await asyncio.sleep(0.01)
            raise ValueError("async error")
        
        result = await async_try_except(failing_async_operation)
        
        assert result.is_failure() is True
        assert isinstance(result.unwrap_error(), ValueError)
    
    def test_pipe_results_success(self):
        """pipe_results 성공 케이스"""
        def add_one(x: int) -> Result[int, str]:
            return success(x + 1)
        
        def multiply_two(x: int) -> Result[int, str]:
            return success(x * 2)
        
        pipeline = pipe_results(add_one, multiply_two)
        result = pipeline(5)
        
        assert result.is_success() is True
        assert result.unwrap() == 12  # (5 + 1) * 2
    
    def test_pipe_results_failure(self):
        """pipe_results 실패 케이스"""
        def add_one(x: int) -> Result[int, str]:
            return success(x + 1)
        
        def fail_always(x: int) -> Result[int, str]:
            return failure("always fails")
        
        def multiply_two(x: int) -> Result[int, str]:
            return success(x * 2)
        
        pipeline = pipe_results(add_one, fail_always, multiply_two)
        result = pipeline(5)
        
        assert result.is_failure() is True
        assert result.unwrap_error() == "always fails"
    
    def test_sequence_success(self):
        """sequence 성공 케이스"""
        results = [success(1), success(2), success(3)]
        combined = sequence(results)
        
        assert combined.is_success() is True
        assert combined.unwrap() == [1, 2, 3]
    
    def test_sequence_failure(self):
        """sequence 실패 케이스"""
        results = [success(1), failure("error"), success(3)]
        combined = sequence(results)
        
        assert combined.is_failure() is True
        assert combined.unwrap_error() == "error"
    
    def test_traverse_success(self):
        """traverse 성공 케이스"""
        def safe_divide(x: int) -> Result[float, str]:
            if x == 0:
                return failure("division by zero")
            return success(10.0 / x)
        
        result = traverse([1, 2, 5], safe_divide)
        
        assert result.is_success() is True
        assert result.unwrap() == [10.0, 5.0, 2.0]
    
    def test_traverse_failure(self):
        """traverse 실패 케이스"""
        def safe_divide(x: int) -> Result[float, str]:
            if x == 0:
                return failure("division by zero")
            return success(10.0 / x)
        
        result = traverse([1, 0, 5], safe_divide)
        
        assert result.is_failure() is True
        assert result.unwrap_error() == "division by zero"
    
    def test_lift_function(self):
        """lift 함수 테스트"""
        add_ten = lambda x: x + 10
        lifted_add_ten = lift(add_ten)
        
        # 성공 케이스
        result = lifted_add_ten(success(5))
        assert result.is_success() is True
        assert result.unwrap() == 15
        
        # 실패 케이스
        result = lifted_add_ten(failure("error"))
        assert result.is_failure() is True
        assert result.unwrap_error() == "error"
    
    def test_lift2_function(self):
        """lift2 함수 테스트"""
        add = lambda x, y: x + y
        lifted_add = lift2(add)
        
        # 성공 케이스
        result = lifted_add(success(5), success(3))
        assert result.is_success() is True
        assert result.unwrap() == 8
        
        # 첫 번째 실패
        result = lifted_add(failure("error1"), success(3))
        assert result.is_failure() is True
        assert result.unwrap_error() == "error1"
        
        # 두 번째 실패
        result = lifted_add(success(5), failure("error2"))
        assert result.is_failure() is True
        assert result.unwrap_error() == "error2"
    
    def test_first_success(self):
        """first_success 테스트"""
        # 첫 번째가 성공
        result = first_success(success(1), success(2), failure("error"))
        assert result.is_success() is True
        assert result.unwrap() == 1
        
        # 두 번째가 성공
        result = first_success(failure("error1"), success(2), failure("error2"))
        assert result.is_success() is True
        assert result.unwrap() == 2
        
        # 모두 실패
        result = first_success(failure("error1"), failure("error2"))
        assert result.is_failure() is True
        assert result.unwrap_error() == ["error1", "error2"]
    
    def test_partition_results(self):
        """partition_results 테스트"""
        results = [success(1), failure("error1"), success(2), failure("error2"), success(3)]
        successes, failures = partition_results(results)
        
        assert successes == [1, 2, 3]
        assert failures == ["error1", "error2"]
    
    def test_equality(self):
        """Result 동등성 테스트"""
        assert success(42) == success(42)
        assert failure("error") == failure("error")
        assert success(42) != failure("error")
        assert success(42) != success(43)
    
    def test_repr(self):
        """Result 문자열 표현 테스트"""
        assert repr(success(42)) == "Success(42)"
        assert repr(failure("error")) == "Failure(error)"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])