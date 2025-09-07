"""
Tests for remaining missing coverage in base.py
base.py의 남은 missing coverage를 위한 테스트
"""

import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.async_tasks.base import (
    LoggingHook,
    MetricsHook,
    TaskHook,
    TaskMetadata,
    TaskPriority,
    TaskResult,
    TaskStatus,
)


class TestTaskHookInterface:
    """Test TaskHook abstract interface - covers lines 345, 350, 355"""

    def test_task_hook_cannot_be_instantiated(self):
        """Test TaskHook is abstract"""
        with pytest.raises(TypeError):
            TaskHook()

    @pytest.mark.asyncio
    async def test_task_hook_concrete_implementation(self):
        """Test concrete TaskHook implementation"""

        class ConcreteHook(TaskHook):
            def __init__(self):
                self.calls = []

            async def before_execute(self, metadata, context):
                self.calls.append(("before", metadata.task_id))

            async def after_execute(self, metadata, result):
                self.calls.append(("after", metadata.task_id))

            async def on_exception(self, metadata, exception):
                self.calls.append(("exception", metadata.task_id, str(exception)))

        hook = ConcreteHook()
        metadata = TaskMetadata(task_id="hook_test")

        await hook.before_execute(metadata, {})
        await hook.after_execute(metadata, "result")
        await hook.on_exception(metadata, ValueError("test"))

        assert len(hook.calls) == 3
        assert hook.calls[0] == ("before", "hook_test")
        assert hook.calls[1] == ("after", "hook_test")
        assert hook.calls[2] == ("exception", "hook_test", "test")


class TestMetricsHookEdgeCases:
    """Test MetricsHook edge cases - covers lines 396, 400-410, 414"""

    @pytest.mark.asyncio
    async def test_metrics_hook_before_execute_increment(self):
        """Test before_execute increments total_tasks - covers line 396"""

        hook = MetricsHook()

        # Initial state
        assert hook.metrics["total_tasks"] == 0

        # Call before_execute multiple times
        metadata1 = TaskMetadata(task_id="task1")
        metadata2 = TaskMetadata(task_id="task2")

        await hook.before_execute(metadata1, {})
        assert hook.metrics["total_tasks"] == 1

        await hook.before_execute(metadata2, {})
        assert hook.metrics["total_tasks"] == 2

    @pytest.mark.asyncio
    async def test_metrics_hook_after_execute_with_duration(self):
        """Test after_execute with duration - covers lines 400-410"""

        hook = MetricsHook()

        # Create metadata with duration
        start_time = datetime.now() - timedelta(seconds=2)
        end_time = datetime.now()

        metadata = TaskMetadata(
            task_id="duration_task", started_at=start_time, completed_at=end_time
        )

        await hook.after_execute(metadata, "success")

        # Check metrics were updated
        assert hook.metrics["successful_tasks"] == 1
        assert len(hook.metrics["task_durations"]) == 1

        # Check duration was recorded correctly
        duration = hook.metrics["task_durations"][0]
        assert isinstance(duration, timedelta)
        assert 1.5 <= duration.total_seconds() <= 2.5

    @pytest.mark.asyncio
    async def test_metrics_hook_after_execute_without_duration(self):
        """Test after_execute without duration"""

        hook = MetricsHook()

        # Metadata without timing info
        metadata = TaskMetadata(task_id="no_duration_task")

        await hook.after_execute(metadata, "success")

        # Should still increment successful_tasks
        assert hook.metrics["successful_tasks"] == 1
        # But no duration should be recorded
        assert len(hook.metrics["task_durations"]) == 0

    @pytest.mark.asyncio
    async def test_metrics_hook_on_exception_increment(self):
        """Test on_exception increments failed_tasks - covers line 414"""

        hook = MetricsHook()

        assert hook.metrics["failed_tasks"] == 0

        metadata = TaskMetadata(task_id="failed_task")

        await hook.on_exception(metadata, ValueError("test error"))

        assert hook.metrics["failed_tasks"] == 1

    def test_metrics_hook_get_metrics_complex_scenario(self):
        """Test get_metrics with complex scenario"""

        hook = MetricsHook()

        # Set up complex metrics scenario
        hook.metrics = {
            **hook.metrics,
            "total_tasks": 10,
            "successful_tasks": 7,
            "failed_tasks": 3,
            "task_durations": [
                timedelta(seconds=1.5),
                timedelta(seconds=2.0),
                timedelta(seconds=0.5),
                timedelta(seconds=3.0),
                timedelta(seconds=1.0),
                timedelta(seconds=2.5),
                timedelta(seconds=1.8),
            ],
            "total_duration": timedelta(seconds=12.3),
        }

        metrics = hook.get_metrics()

        # Check calculated values
        assert metrics["success_rate"] == 0.7  # 7/10

        # Check average duration calculation
        expected_avg = sum([1.5, 2.0, 0.5, 3.0, 1.0, 2.5, 1.8]) / 7
        actual_avg = metrics["average_duration"].total_seconds()
        assert abs(actual_avg - expected_avg) < 0.01

    def test_metrics_hook_get_metrics_zero_division_safety(self):
        """Test get_metrics handles zero division safely"""

        hook = MetricsHook()

        # No tasks scenario
        hook.metrics = {
            **hook.metrics,
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "task_durations": [],
        }

        metrics = hook.get_metrics()

        # Should handle zero division gracefully
        assert metrics["success_rate"] == 0
        assert metrics["average_duration"] is None


class TestTaskMetadataComplexScenarios:
    """Test TaskMetadata complex scenarios"""

    def test_task_metadata_full_lifecycle(self):
        """Test TaskMetadata through full task lifecycle"""

        # Create metadata for a complete task lifecycle
        metadata = TaskMetadata(
            task_id="lifecycle_task",
            name="Full Lifecycle Task",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            scheduled_at=datetime.now() + timedelta(minutes=5),
            depends_on=["task1", "task2"],
            parent_id="parent_task",
            children_ids=["child1", "child2"],
            context={"env": "test", "version": "1.0"},
            tags=["integration", "high-priority"],
            timeout=timedelta(minutes=30),
        )

        # Initial state checks
        assert not metadata.is_ready()  # Has dependencies
        assert not metadata.is_terminal()  # Still pending
        assert metadata.duration() is None  # Not started yet

        # Start the task
        metadata.status = TaskStatus.RUNNING
        metadata.started_at = datetime.now()

        assert not metadata.is_terminal()  # Still running
        assert metadata.duration() is None  # Not completed yet

        # Complete the task
        metadata.status = TaskStatus.COMPLETED
        metadata.completed_at = datetime.now()
        metadata.result = "Task completed successfully"

        assert metadata.is_terminal()  # Now complete
        assert metadata.duration() is not None  # Has duration

        # Verify all data is preserved
        assert metadata.name == "Full Lifecycle Task"
        assert metadata.priority == TaskPriority.HIGH
        assert metadata.depends_on == ["task1", "task2"]
        assert metadata.parent_id == "parent_task"
        assert metadata.children_ids == ["child1", "child2"]
        assert metadata.context["env"] == "test"
        assert "integration" in metadata.tags
        assert metadata.timeout == timedelta(minutes=30)
        assert metadata.result == "Task completed successfully"

    def test_task_metadata_error_scenario(self):
        """Test TaskMetadata in error scenario"""

        metadata = TaskMetadata(
            task_id="error_task",
            status=TaskStatus.RUNNING,
            retry_count=2,
            started_at=datetime.now(),
        )

        # Simulate task failure
        metadata.status = TaskStatus.FAILED
        metadata.completed_at = datetime.now()
        metadata.error = "Task failed due to network timeout"
        metadata.traceback = "Traceback (most recent call last):\n  File..."

        # Verify error state
        assert metadata.is_terminal()
        assert metadata.duration() is not None
        assert metadata.error == "Task failed due to network timeout"
        assert metadata.traceback.startswith("Traceback")

    def test_task_metadata_retry_scenario(self):
        """Test TaskMetadata in retry scenario"""

        from rfs.async_tasks.base import BackoffStrategy, RetryPolicy

        retry_policy = RetryPolicy(
            max_attempts=3,
            delay=timedelta(seconds=1),
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
        )

        metadata = TaskMetadata(
            task_id="retry_task",
            status=TaskStatus.RETRYING,
            retry_count=1,
            retry_policy=retry_policy,
        )

        # Verify retry configuration
        assert metadata.retry_count == 1
        assert metadata.retry_policy.max_attempts == 3
        assert metadata.retry_policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert not metadata.is_terminal()  # Still retrying


class TestCompleteTaskResult:
    """Test TaskResult comprehensive scenarios"""

    def test_task_result_all_status_conversions(self):
        """Test TaskResult to_result() for all statuses"""

        from rfs.core.result import Failure, Success

        # Success case
        success_result = TaskResult(
            task_id="success", status=TaskStatus.COMPLETED, value={"data": "success"}
        )
        converted = success_result.to_result()
        assert isinstance(converted, Success)
        assert converted.value == {"data": "success"}

        # Failed case
        failed_result = TaskResult(
            task_id="failed", status=TaskStatus.FAILED, error="Execution failed"
        )
        converted = failed_result.to_result()
        assert isinstance(converted, Failure)
        assert "Execution failed" in str(converted.error)

        # Timeout case
        timeout_result = TaskResult(
            task_id="timeout", status=TaskStatus.TIMEOUT, error="Task timed out"
        )
        converted = timeout_result.to_result()
        assert isinstance(converted, Failure)
        assert "Task timed out" in str(converted.error)

        # Cancelled case
        cancelled_result = TaskResult(task_id="cancelled", status=TaskStatus.CANCELLED)
        converted = cancelled_result.to_result()
        assert isinstance(converted, Failure)
        assert "CANCELLED" in str(converted.error)

    def test_task_result_is_methods_comprehensive(self):
        """Test TaskResult is_success and is_failure methods comprehensively"""

        # Test success case
        success_result = TaskResult("test", TaskStatus.COMPLETED, value="success")
        assert success_result.is_success()
        assert not success_result.is_failure()

        # Test all failure cases
        failure_statuses = [TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.CANCELLED]

        for status in failure_statuses:
            failure_result = TaskResult("test", status, error="error")
            assert not failure_result.is_success()
            assert failure_result.is_failure()

        # Test non-terminal cases
        non_terminal_statuses = [
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
        ]

        for status in non_terminal_statuses:
            pending_result = TaskResult("test", status)
            assert not pending_result.is_success()
            assert not pending_result.is_failure()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
