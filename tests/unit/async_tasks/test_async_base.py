"""
Unit tests for async_tasks base components
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

from rfs.async_tasks.base import (
    BackoffStrategy,
    RetryPolicy,
    TaskMetadata,
    TaskPriority,
    TaskResult,
    TaskStatus,
)
from rfs.core.result import Failure, Success


class TestTaskStatus:
    """Test TaskStatus enum"""

    def test_task_status_values(self):
        """Test TaskStatus enum values"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.QUEUED.value == "queued"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.TIMEOUT.value == "timeout"
        assert TaskStatus.RETRYING.value == "retrying"

    def test_task_status_uniqueness(self):
        """Test that all status values are unique"""
        values = [status.value for status in TaskStatus]
        assert len(values) == len(set(values))


class TestTaskPriority:
    """Test TaskPriority enum"""

    def test_task_priority_values(self):
        """Test TaskPriority enum values"""
        assert TaskPriority.CRITICAL.value == 0
        assert TaskPriority.HIGH.value == 1
        assert TaskPriority.NORMAL.value == 2
        assert TaskPriority.LOW.value == 3
        assert TaskPriority.BACKGROUND.value == 4

    def test_task_priority_comparison(self):
        """Test TaskPriority comparison"""
        assert TaskPriority.CRITICAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.NORMAL
        assert TaskPriority.NORMAL < TaskPriority.LOW
        assert TaskPriority.LOW < TaskPriority.BACKGROUND

    def test_task_priority_ordering(self):
        """Test TaskPriority ordering for queue operations"""
        priorities = [
            TaskPriority.LOW,
            TaskPriority.CRITICAL,
            TaskPriority.NORMAL,
            TaskPriority.HIGH,
            TaskPriority.BACKGROUND,
        ]

        sorted_priorities = sorted(priorities)
        assert sorted_priorities[0] == TaskPriority.CRITICAL
        assert sorted_priorities[1] == TaskPriority.HIGH
        assert sorted_priorities[2] == TaskPriority.NORMAL
        assert sorted_priorities[3] == TaskPriority.LOW
        assert sorted_priorities[4] == TaskPriority.BACKGROUND


class TestBackoffStrategy:
    """Test BackoffStrategy enum"""

    def test_backoff_strategy_values(self):
        """Test BackoffStrategy enum values"""
        assert BackoffStrategy.FIXED.value == "fixed"
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"
        assert BackoffStrategy.JITTER.value == "jitter"


class TestRetryPolicy:
    """Test RetryPolicy class"""

    def test_retry_policy_defaults(self):
        """Test RetryPolicy with default values"""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.delay == timedelta(seconds=1)
        assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert policy.backoff_multiplier == 2.0
        assert policy.max_delay == timedelta(minutes=5)
        assert policy.retry_on == []
        assert policy.retry_condition is None

    def test_retry_policy_custom_values(self):
        """Test RetryPolicy with custom values"""
        policy = RetryPolicy(
            max_attempts=5,
            delay=timedelta(seconds=2),
            backoff_strategy=BackoffStrategy.LINEAR,
            backoff_multiplier=1.5,
            max_delay=timedelta(minutes=10),
        )
        assert policy.max_attempts == 5
        assert policy.delay == timedelta(seconds=2)
        assert policy.backoff_strategy == BackoffStrategy.LINEAR
        assert policy.backoff_multiplier == 1.5
        assert policy.max_delay == timedelta(minutes=10)

    def test_should_retry_attempts(self):
        """Test should_retry based on attempts"""
        policy = RetryPolicy(max_attempts=3)

        error = ValueError("test error")
        assert policy.should_retry(error, 1) is True
        assert policy.should_retry(error, 2) is True
        assert policy.should_retry(error, 3) is False
        assert policy.should_retry(error, 4) is False

    def test_should_retry_with_condition(self):
        """Test should_retry with custom condition"""

        def retry_on_value_error(exc):
            return isinstance(exc, ValueError)

        policy = RetryPolicy(
            max_attempts=5,
            retry_condition=retry_on_value_error,
        )

        value_error = ValueError("test")
        runtime_error = RuntimeError("test")

        assert policy.should_retry(value_error, 1) is True
        assert policy.should_retry(runtime_error, 1) is False

    def test_get_delay_fixed_strategy(self):
        """Test get_delay with fixed strategy"""
        policy = RetryPolicy(
            delay=timedelta(seconds=2),
            backoff_strategy=BackoffStrategy.FIXED,
        )

        assert policy.get_delay(1) == timedelta(seconds=2)
        assert policy.get_delay(2) == timedelta(seconds=2)
        assert policy.get_delay(3) == timedelta(seconds=2)

    def test_get_delay_linear_strategy(self):
        """Test get_delay with linear strategy"""
        policy = RetryPolicy(
            delay=timedelta(seconds=1),
            backoff_strategy=BackoffStrategy.LINEAR,
        )

        assert policy.get_delay(1) == timedelta(seconds=1)
        assert policy.get_delay(2) == timedelta(seconds=2)
        assert policy.get_delay(3) == timedelta(seconds=3)

    def test_get_delay_exponential_strategy(self):
        """Test get_delay with exponential strategy"""
        policy = RetryPolicy(
            delay=timedelta(seconds=1),
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
        )

        assert policy.get_delay(1) == timedelta(seconds=1)
        assert policy.get_delay(2) == timedelta(seconds=2)
        assert policy.get_delay(3) == timedelta(seconds=4)

    def test_get_delay_with_max_delay(self):
        """Test get_delay respects max_delay"""
        policy = RetryPolicy(
            delay=timedelta(seconds=10),
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=10,
            max_delay=timedelta(seconds=30),
        )

        # This would be 1000 seconds without max_delay
        assert policy.get_delay(3) == timedelta(seconds=30)

    def test_get_delay_jitter_strategy(self):
        """Test get_delay with jitter strategy"""
        policy = RetryPolicy(
            delay=timedelta(seconds=1),
            backoff_strategy=BackoffStrategy.JITTER,
            backoff_multiplier=2.0,
        )

        # Jitter adds randomness, so we just check it's within range
        delay = policy.get_delay(2)
        assert delay >= timedelta(seconds=2)  # base delay
        assert delay <= timedelta(seconds=2.2)  # base + 10% jitter


class TestTaskMetadata:
    """Test TaskMetadata class"""

    def test_task_metadata_creation(self):
        """Test TaskMetadata creation"""
        now = datetime.now()
        metadata = TaskMetadata(
            task_id="test-123",
            name="test_task",
            status=TaskStatus.RUNNING,
            priority=TaskPriority.HIGH,
            created_at=now,
            tags=["test", "unit"],
            context={"env": "test", "version": "1.0"},
        )

        assert metadata.task_id == "test-123"
        assert metadata.name == "test_task"
        assert metadata.status == TaskStatus.RUNNING
        assert metadata.priority == TaskPriority.HIGH
        assert metadata.tags == ["test", "unit"]
        assert metadata.context == {"env": "test", "version": "1.0"}
        assert metadata.created_at == now

    def test_task_metadata_defaults(self):
        """Test TaskMetadata with default values"""
        metadata = TaskMetadata()

        assert metadata.task_id  # Should have a generated UUID
        assert metadata.name == ""
        assert metadata.status == TaskStatus.PENDING
        assert metadata.priority == TaskPriority.NORMAL
        assert isinstance(metadata.created_at, datetime)
        assert metadata.tags == []
        assert metadata.context == {}
        assert metadata.result is None
        assert metadata.error is None

    def test_task_metadata_duration(self):
        """Test TaskMetadata duration calculation"""
        started = datetime.now() - timedelta(seconds=10)
        completed = datetime.now()

        metadata = TaskMetadata(
            started_at=started,
            completed_at=completed,
        )

        duration = metadata.duration()
        assert duration is not None
        assert 9.5 <= duration.total_seconds() <= 10.5

    def test_task_metadata_is_terminal(self):
        """Test TaskMetadata is_terminal method"""
        metadata = TaskMetadata()

        # Non-terminal states
        for status in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING]:
            metadata.status = status
            assert metadata.is_terminal() is False

        # Terminal states
        for status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        ]:
            metadata.status = status
            assert metadata.is_terminal() is True

    def test_task_metadata_is_ready(self):
        """Test TaskMetadata is_ready method"""
        # Ready: pending with no dependencies
        metadata = TaskMetadata(status=TaskStatus.PENDING)
        assert metadata.is_ready() is True

        # Not ready: has dependencies
        metadata.depends_on = ["task-1"]
        assert metadata.is_ready() is False

        # Not ready: wrong status
        metadata = TaskMetadata(status=TaskStatus.RUNNING)
        assert metadata.is_ready() is False


class TestTaskResult:
    """Test TaskResult class"""

    def test_task_result_success(self):
        """Test TaskResult for successful task"""
        metadata = TaskMetadata(
            task_id="success-123",
            status=TaskStatus.COMPLETED,
            started_at=datetime.now() - timedelta(seconds=5),
            completed_at=datetime.now(),
        )

        result = TaskResult(
            task_id="success-123",
            status=TaskStatus.COMPLETED,
            value={"data": "test_value"},
            metadata=metadata,
        )

        assert result.task_id == "success-123"
        assert result.status == TaskStatus.COMPLETED
        assert result.value == {"data": "test_value"}
        assert result.error is None
        assert result.is_success() is True
        assert result.is_failure() is False

        # Test to_result conversion
        converted = result.to_result()
        assert isinstance(converted, Success)
        assert converted.value == {"data": "test_value"}

    def test_task_result_failure(self):
        """Test TaskResult for failed task"""
        metadata = TaskMetadata(
            task_id="failure-123",
            status=TaskStatus.FAILED,
        )

        result = TaskResult(
            task_id="failure-123",
            status=TaskStatus.FAILED,
            error="Task execution failed",
            metadata=metadata,
        )

        assert result.task_id == "failure-123"
        assert result.status == TaskStatus.FAILED
        assert result.value is None
        assert result.error == "Task execution failed"
        assert result.is_success() is False
        assert result.is_failure() is True

        # Test to_result conversion
        converted = result.to_result()
        assert isinstance(converted, Failure)
        assert "Task execution failed" in str(converted.error)

    def test_task_result_timeout(self):
        """Test TaskResult for timeout"""
        result = TaskResult(
            task_id="timeout-123",
            status=TaskStatus.TIMEOUT,
            error="Task timed out after 30 seconds",
        )

        assert result.task_id == "timeout-123"
        assert result.status == TaskStatus.TIMEOUT
        assert result.is_success() is False
        assert result.is_failure() is True

        converted = result.to_result()
        assert isinstance(converted, Failure)

    def test_task_result_cancelled(self):
        """Test TaskResult for cancelled task"""
        result = TaskResult(
            task_id="cancelled-123",
            status=TaskStatus.CANCELLED,
        )

        assert result.task_id == "cancelled-123"
        assert result.status == TaskStatus.CANCELLED
        assert result.is_success() is False
        assert result.is_failure() is True

        converted = result.to_result()
        assert isinstance(converted, Failure)
        assert "CANCELLED" in str(converted.error)

    def test_task_result_pending(self):
        """Test TaskResult for pending task"""
        result = TaskResult(
            task_id="pending-123",
            status=TaskStatus.PENDING,
        )

        assert result.task_id == "pending-123"
        assert result.status == TaskStatus.PENDING
        assert result.value is None
        assert result.error is None
        assert result.is_success() is False
        assert result.is_failure() is False  # Pending is not considered failure
