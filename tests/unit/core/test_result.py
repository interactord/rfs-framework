"""
Unit tests for Result pattern (RFS Framework)
"""

from typing import Any

import pytest

from rfs.core.result import (
    Either,
    Failure,
    Maybe,
    Result,
    Success,
    combine,
    either_to_result,
    first_success,
    none,
    partition,
    result_to_either,
    result_to_maybe,
    sequence,
    some,
    traverse,
    traverse_either,
    traverse_maybe,
)


class TestResultBasics:
    """Basic Result pattern tests"""

    def test_success_creation(self):
        """Test Success creation and properties"""
        result = Success(42)
        assert result.is_success() is True
        assert result.is_failure() is False
        assert result.unwrap() == 42
        assert result.unwrap_or(0) == 42

    def test_failure_creation(self):
        """Test Failure creation and properties"""
        result = Failure("error")
        assert result.is_success() is False
        assert result.is_failure() is True
        assert result.unwrap_error() == "error"
        assert result.unwrap_or(0) == 0

    def test_success_helper(self):
        """Test Success helper function"""
        result = Success(100)
        assert isinstance(result, Success)
        assert result.unwrap() == 100

    def test_failure_helper(self):
        """Test Failure helper function"""
        result = Failure("failed")
        assert isinstance(result, Failure)
        assert result.unwrap_error() == "failed"


class TestResultTransformations:
    """Test Result transformation methods"""

    def test_map_on_success(self):
        """Test map on Success"""
        result = Success(10)
        mapped = result.map(lambda x: x * 2)
        assert mapped.unwrap() == 20

    def test_map_on_failure(self):
        """Test map on Failure"""
        result = Failure("error")
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_failure()
        assert mapped.unwrap_error() == "error"

    def test_flat_map_on_success(self):
        """Test flat_map (bind) on Success"""
        result = Success(10)
        mapped = result.flat_map(lambda x: Success(x * 2))
        assert mapped.unwrap() == 20

    def test_flat_map_on_failure(self):
        """Test flat_map (bind) on Failure"""
        result = Failure("error")
        mapped = result.flat_map(lambda x: Success(x * 2))
        assert mapped.is_failure()
        assert mapped.unwrap_error() == "error"

    def test_map_err_on_success(self):
        """Test map_err on Success"""
        result = Success(10)
        mapped = result.map_error(lambda e: f"Error: {e}")
        assert mapped.is_success()
        assert mapped.unwrap() == 10

    def test_map_err_on_failure(self):
        """Test map_err on Failure"""
        result = Failure("error")
        mapped = result.map_error(lambda e: f"Error: {e}")
        assert mapped.is_failure()
        assert mapped.unwrap_error() == "Error: error"


class TestResultCombinators:
    """Test Result combinator functions"""

    def test_sequence_all_success(self):
        """Test sequence with all Success values"""
        results = [Success(1), Success(2), Success(3)]
        combined = sequence(results)
        assert combined.is_success()
        assert combined.unwrap() == [1, 2, 3]

    def test_sequence_with_failure(self):
        """Test sequence with a Failure"""
        results = [Success(1), Failure("error"), Success(3)]
        combined = sequence(results)
        assert combined.is_failure()
        assert combined.unwrap_error() == "error"

    def test_combine_all_success(self):
        """Test combine with all Success values"""
        results = [Success(1), Success(2), Success(3)]
        combined = combine(*results)
        assert combined.is_success()
        assert combined.unwrap() == (1, 2, 3)

    def test_first_success(self):
        """Test first_success returns first Success"""
        result = first_success(Failure("error1"), Success(42), Success(100))
        assert result.is_success()
        assert result.unwrap() == 42

    def test_first_success_all_failures(self):
        """Test first_success with all Failures"""
        result = first_success(Failure("error1"), Failure("error2"))
        assert result.is_failure()
        assert result.unwrap_error() == ["error1", "error2"]

    def test_partition(self):
        """Test partition separates Success and Failure"""
        results = [Success(1), Failure("error"), Success(2)]
        successes, failures = partition(results)
        assert successes == [1, 2]
        assert failures == ["error"]


class TestResultFunctionalPatterns:
    """Test functional programming patterns with Result"""

    def test_traverse(self):
        """Test traverse function"""
        items = [1, 2, 3]
        result = traverse(items, lambda x: Success(x * 2))
        assert result.is_success()
        assert result.unwrap() == [2, 4, 6]

    def test_traverse_with_failure(self):
        """Test traverse with Failure"""
        items = [1, 2, 3]

        def process(x):
            if x == 2:
                return Failure("error at 2")
            return Success(x * 2)

        result = traverse(items, process)
        assert result.is_failure()
        assert result.unwrap_error() == "error at 2"

    def test_or_else(self):
        """Test or_else fallback"""
        result1 = Failure("error")
        result2 = result1.or_else(lambda: Success(42))
        assert result2.is_success()
        assert result2.unwrap() == 42

    def test_filter(self):
        """Test filter on Success"""
        result = Success(10)
        filtered = result.filter(lambda x: x > 5, "too small")
        assert filtered.is_success()

        filtered2 = result.filter(lambda x: x > 20, "too small")
        assert filtered2.is_failure()
        assert filtered2.unwrap_error() == "too small"


class TestResultConversions:
    """Test Result conversions to/from other types"""

    def test_result_to_either(self):
        """Test converting Result to Either"""
        result = Success(42)
        either = result_to_either(result)
        assert either.is_right()

        result2 = Failure("error")
        either2 = result_to_either(result2)
        assert either2.is_left()

    def test_result_to_maybe(self):
        """Test converting Result to Maybe"""
        result = Success(42)
        maybe = result_to_maybe(result)
        assert maybe.is_some()

        result2 = Failure("error")
        maybe2 = result_to_maybe(result2)
        assert maybe2.is_none()


class TestResultErrorHandling:
    """Test error handling patterns with Result"""

    def test_try_catch(self):
        """Test try_catch wrapper"""

        def safe_divide(a: int, b: int) -> Result[float, str]:
            if b == 0:
                return Failure("Division by zero")
            return Success(a / b)

        result = safe_divide(10, 2)
        assert result.is_success()
        assert result.unwrap() == 5.0

        result2 = safe_divide(10, 0)
        assert result2.is_failure()
        assert result2.unwrap_error() == "Division by zero"

    def test_recover(self):
        """Test recovery from errors"""
        result = Failure("error")
        recovered = result.or_else(lambda: Success(0))
        assert recovered.is_success()
        assert recovered.unwrap() == 0


class TestResultChaining:
    """Test method chaining with Result"""

    def test_chain_operations(self):
        """Test chaining multiple operations"""
        result = (
            Success(10)
            .map(lambda x: x * 2)
            .filter(lambda x: x > 10, "too small")
            .map(lambda x: x + 5)
        )
        assert result.is_success()
        assert result.unwrap() == 25

    def test_chain_with_failure(self):
        """Test chaining stops on Failure"""
        result = (
            Success(5)
            .map(lambda x: x * 2)
            .filter(lambda x: x > 20, "too small")
            .map(lambda x: x + 5)
        )
        assert result.is_failure()
        assert result.unwrap_error() == "too small"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
