"""
Fixed simple tests to improve async_tasks coverage
수정된 간단한 async_tasks 테스트로 커버리지 향상
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.async_tasks.base import (
    BackoffStrategy,
    CallableTask,
    RetryPolicy,
    Task,
    TaskCallback,
    TaskCancelled,
    TaskDependencyError,
    TaskError,
    TaskMetadata,
    TaskPriority,
    TaskResult,
    TaskStatus,
    TaskTimeout,
)
from rfs.core.result import Failure, Success


class TestTaskErrors:
    """Test task error classes"""

    def test_task_error(self):
        """Test TaskError exception"""
        error = TaskError("Test error message", task_id="task-123")
        assert str(error) == "Test error message"
        assert error.task_id == "task-123"

        # Test without task_id
        error2 = TaskError("No task ID")
        assert str(error2) == "No task ID"
        assert error2.task_id is None

    def test_task_timeout(self):
        """Test TaskTimeout exception"""
        timeout = TaskTimeout("Task timed out", task_id="timeout-task")
        assert str(timeout) == "Task timed out"
        assert timeout.task_id == "timeout-task"
        assert isinstance(timeout, TaskError)

    def test_task_cancelled(self):
        """Test TaskCancelled exception"""
        cancelled = TaskCancelled("Task was cancelled", task_id="cancelled-task")
        assert str(cancelled) == "Task was cancelled"
        assert cancelled.task_id == "cancelled-task"
        assert isinstance(cancelled, TaskError)

    def test_task_dependency_error(self):
        """Test TaskDependencyError exception"""
        dep_error = TaskDependencyError("Dependency failed", task_id="dep-task")
        assert str(dep_error) == "Dependency failed"
        assert dep_error.task_id == "dep-task"
        assert isinstance(dep_error, TaskError)


class TestCallableTaskFixed:
    """Test CallableTask implementation with working patterns"""

    @pytest.mark.asyncio
    async def test_callable_task_async_function_no_args(self):
        """Test CallableTask with async function without args"""

        async def async_func():
            await asyncio.sleep(0.001)
            return "async_result"

        task = CallableTask(async_func)
        result = await task.execute({})

        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_callable_task_async_function_with_kwargs(self):
        """Test CallableTask with async function using kwargs"""

        async def async_func(**kwargs):
            await asyncio.sleep(0.001)
            return f"result_{kwargs.get('test_key', 'default')}"

        task = CallableTask(async_func)
        result = await task.execute({"test_key": "value"})

        assert result == "result_value"

    def test_callable_task_validate(self):
        """Test CallableTask validate method"""

        def dummy_func():
            return "test"

        task = CallableTask(dummy_func)
        result = task.validate({"test": "context"})

        assert isinstance(result, Success)
        assert result.value is None

    def test_callable_task_cleanup(self):
        """Test CallableTask cleanup method"""

        def dummy_func():
            return "test"

        task = CallableTask(dummy_func)
        # Should not raise any exception
        task.cleanup({"test": "context"})


class TestTaskAbstract:
    """Test Task abstract class"""

    def test_task_abstract(self):
        """Test that Task cannot be instantiated"""
        with pytest.raises(TypeError):
            Task()


class TestBackoffStrategyValues:
    """Test BackoffStrategy enum values"""

    def test_backoff_strategy_values(self):
        """Test all BackoffStrategy values"""
        assert BackoffStrategy.FIXED.value == "fixed"
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"
        assert BackoffStrategy.JITTER.value == "jitter"


class TestRetryPolicySimple:
    """Test RetryPolicy basic functionality"""

    def test_retry_policy_creation(self):
        """Test RetryPolicy creation with defaults"""
        policy = RetryPolicy()

        assert policy.max_attempts == 3
        assert policy.delay == timedelta(seconds=1)
        assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert policy.backoff_multiplier == 2.0
        assert policy.max_delay == timedelta(minutes=5)

    def test_should_retry_max_attempts(self):
        """Test should_retry with max attempts"""
        policy = RetryPolicy(max_attempts=2)

        exception = ValueError("test")

        # First attempt should allow retry
        assert policy.should_retry(exception, 1) is True

        # At max attempts should not retry
        assert policy.should_retry(exception, 2) is False

        # Beyond max attempts should not retry
        assert policy.should_retry(exception, 3) is False

    def test_get_delay_fixed(self):
        """Test get_delay with FIXED strategy"""
        policy = RetryPolicy(
            delay=timedelta(seconds=5), backoff_strategy=BackoffStrategy.FIXED
        )

        # All attempts should have same delay
        assert policy.get_delay(1) == timedelta(seconds=5)
        assert policy.get_delay(3) == timedelta(seconds=5)
        assert policy.get_delay(10) == timedelta(seconds=5)

    def test_get_delay_linear(self):
        """Test get_delay with LINEAR strategy"""
        policy = RetryPolicy(
            delay=timedelta(seconds=2), backoff_strategy=BackoffStrategy.LINEAR
        )

        assert policy.get_delay(1) == timedelta(seconds=2)
        assert policy.get_delay(2) == timedelta(seconds=4)
        assert policy.get_delay(3) == timedelta(seconds=6)

    def test_get_delay_exponential(self):
        """Test get_delay with EXPONENTIAL strategy"""
        policy = RetryPolicy(
            delay=timedelta(seconds=1),
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
        )

        assert policy.get_delay(1) == timedelta(seconds=1)
        assert policy.get_delay(2) == timedelta(seconds=2)
        assert policy.get_delay(3) == timedelta(seconds=4)

    def test_get_delay_max_delay_enforcement(self):
        """Test that max_delay is enforced"""
        policy = RetryPolicy(
            delay=timedelta(seconds=10),
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=10.0,
            max_delay=timedelta(seconds=30),
        )

        # Should be capped at max_delay
        delay = policy.get_delay(3)  # Would be 10 * 10^2 = 1000 seconds
        assert delay == timedelta(seconds=30)


class TestTaskPriorityComparison:
    """Test TaskPriority comparison"""

    def test_task_priority_comparison(self):
        """Test TaskPriority __lt__ method"""
        assert TaskPriority.CRITICAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.NORMAL
        assert TaskPriority.NORMAL < TaskPriority.LOW
        assert TaskPriority.LOW < TaskPriority.BACKGROUND

        # Should not be less than self
        assert not (TaskPriority.NORMAL < TaskPriority.NORMAL)


class TestTaskMetadataEdgeCases:
    """Test TaskMetadata edge cases"""

    def test_task_metadata_duration_none_cases(self):
        """Test duration method when timestamps are None"""
        metadata = TaskMetadata()

        # No timestamps
        assert metadata.duration() is None

        # Only started_at
        metadata.started_at = datetime.now()
        assert metadata.duration() is None

        # Only completed_at
        metadata.started_at = None
        metadata.completed_at = datetime.now()
        assert metadata.duration() is None

    def test_task_metadata_is_ready_with_dependencies(self):
        """Test is_ready with dependencies"""
        metadata = TaskMetadata(status=TaskStatus.PENDING)

        # No dependencies - should be ready
        assert metadata.is_ready() is True

        # With dependencies - should not be ready
        metadata.depends_on = ["task1", "task2"]
        assert metadata.is_ready() is False

        # Different status - should not be ready even without dependencies
        metadata.depends_on = []
        metadata.status = TaskStatus.RUNNING
        assert metadata.is_ready() is False


class TestTaskResultEdgeCases:
    """Test TaskResult edge cases"""

    def test_task_result_is_methods_with_retrying(self):
        """Test is_success and is_failure with RETRYING status"""
        result = TaskResult(task_id="retry_test", status=TaskStatus.RETRYING)

        # RETRYING should not be success or failure
        assert result.is_success() is False
        assert result.is_failure() is False

    def test_task_result_to_result_with_none_error(self):
        """Test to_result with None error message"""
        result = TaskResult(task_id="fail_test", status=TaskStatus.FAILED, error=None)

        converted = result.to_result()
        assert isinstance(converted, Failure)
        assert "Task failed with status: FAILED" in converted.error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
