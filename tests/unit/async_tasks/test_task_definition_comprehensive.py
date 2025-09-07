"""
Comprehensive tests for task_definition module
task_definition 모듈의 포괄적 테스트
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch

import pytest

from rfs.async_tasks.task_definition import (
    TaskContext,
    TaskDefinition,
    TaskRegistry,
    TaskType,
    _task_registry,
    batch_task,
    create_task_definition,
    get_task_definition,
    list_task_definitions,
    priority_task,
    realtime_task,
    scheduled_task,
    task_handler,
)
from rfs.core.result import Failure, Success


class TestTaskType:
    """Test TaskType enum"""

    def test_task_type_values(self):
        """Test TaskType enum values"""
        assert TaskType.BATCH.value == "batch"
        assert TaskType.REALTIME.value == "realtime"
        assert TaskType.SCHEDULED.value == "scheduled"
        assert TaskType.EVENT_DRIVEN.value == "event_driven"
        assert TaskType.BACKGROUND.value == "background"
        assert TaskType.PRIORITY.value == "priority"

    def test_task_type_comparison(self):
        """Test TaskType comparison"""
        assert TaskType.BATCH != TaskType.REALTIME
        assert TaskType.BATCH == TaskType.BATCH


class TestTaskContext:
    """Test TaskContext class"""

    def test_task_context_creation(self):
        """Test TaskContext creation with required fields"""
        context = TaskContext(
            task_id="test-123", task_name="test_task", task_type=TaskType.BATCH
        )

        assert context.task_id == "test-123"
        assert context.task_name == "test_task"
        assert context.task_type == TaskType.BATCH
        assert context.retry_count == 0
        assert context.max_retries == 3
        assert context.timeout_seconds is None
        assert isinstance(context.metadata, dict)
        assert len(context.metadata) == 0
        assert isinstance(context.execution_time, datetime)

    def test_task_context_full_creation(self):
        """Test TaskContext creation with all fields"""
        metadata = {"key": "value"}
        execution_time = datetime.now()

        context = TaskContext(
            task_id="test-456",
            task_name="complex_task",
            task_type=TaskType.PRIORITY,
            execution_time=execution_time,
            retry_count=2,
            max_retries=5,
            timeout_seconds=30,
            metadata=metadata,
        )

        assert context.task_id == "test-456"
        assert context.task_name == "complex_task"
        assert context.task_type == TaskType.PRIORITY
        assert context.execution_time == execution_time
        assert context.retry_count == 2
        assert context.max_retries == 5
        assert context.timeout_seconds == 30
        assert context.metadata == metadata

    def test_with_retry(self):
        """Test with_retry method"""
        original_time = datetime.now() - timedelta(seconds=10)
        context = TaskContext(
            task_id="retry-test",
            task_name="retry_task",
            task_type=TaskType.BACKGROUND,
            execution_time=original_time,
            retry_count=1,
            max_retries=3,
            metadata={"original": "data"},
        )

        retry_context = context.with_retry()

        assert retry_context.task_id == context.task_id
        assert retry_context.task_name == context.task_name
        assert retry_context.task_type == context.task_type
        assert retry_context.retry_count == 2  # incremented
        assert retry_context.max_retries == context.max_retries
        assert retry_context.execution_time > original_time  # new time
        assert retry_context.metadata == {"original": "data"}  # copied

        # Original context unchanged
        assert context.retry_count == 1
        assert context.execution_time == original_time

    def test_should_retry(self):
        """Test should_retry method"""
        context = TaskContext(
            task_id="test",
            task_name="test",
            task_type=TaskType.BACKGROUND,
            retry_count=1,
            max_retries=3,
        )

        assert context.should_retry() is True

        # At max retries
        context.retry_count = 3
        assert context.should_retry() is False

        # Beyond max retries
        context.retry_count = 5
        assert context.should_retry() is False

        # Zero retries allowed
        context.retry_count = 0
        context.max_retries = 0
        assert context.should_retry() is False

    def test_add_metadata(self):
        """Test add_metadata method"""
        context = TaskContext(
            task_id="test",
            task_name="test",
            task_type=TaskType.BACKGROUND,
            metadata={"existing": "value"},
        )

        context.add_metadata("new_key", "new_value")

        assert context.metadata["existing"] == "value"
        assert context.metadata["new_key"] == "new_value"
        assert len(context.metadata) == 2

        # Overwrite existing
        context.add_metadata("existing", "updated")
        assert context.metadata["existing"] == "updated"
        assert len(context.metadata) == 2

    def test_get_metadata(self):
        """Test get_metadata method"""
        context = TaskContext(
            task_id="test",
            task_name="test",
            task_type=TaskType.BACKGROUND,
            metadata={"key1": "value1", "key2": 42},
        )

        assert context.get_metadata("key1") == "value1"
        assert context.get_metadata("key2") == 42
        assert context.get_metadata("nonexistent") is None
        assert context.get_metadata("nonexistent", "default") == "default"


class TestTaskDefinition:
    """Test TaskDefinition class"""

    def test_simple_handler(self):
        """Simple test handler"""

        def simple_handler(context: TaskContext):
            return "success"

        return simple_handler

    def test_task_definition_creation(self):
        """Test TaskDefinition creation with minimal parameters"""

        def test_handler(context: TaskContext):
            return "test_result"

        task_def = TaskDefinition(
            name="test_task", task_type=TaskType.BATCH, handler=test_handler
        )

        assert task_def.name == "test_task"
        assert task_def.task_type == TaskType.BATCH
        assert task_def.handler == test_handler
        assert task_def.description is None
        assert task_def.priority == 5
        assert task_def.timeout_seconds is None
        assert task_def.max_retries == 3
        assert task_def.retry_delay_seconds == 1
        assert task_def.retry_exponential_backoff is False
        assert task_def.tags == []
        assert task_def.metadata == {}
        assert task_def.schedule_cron is None
        assert task_def.schedule_interval is None
        assert task_def.schedule_at is None
        assert task_def.dependencies == []
        assert task_def.conditions == []

    def test_task_definition_full_creation(self):
        """Test TaskDefinition creation with all parameters"""

        def test_handler(context: TaskContext):
            return "test_result"

        def test_condition(context: TaskContext):
            return True

        schedule_time = datetime.now() + timedelta(hours=1)
        schedule_interval = timedelta(minutes=30)
        tags = ["tag1", "tag2"]
        metadata = {"env": "test", "version": "1.0"}
        dependencies = ["dep1", "dep2"]
        conditions = [test_condition]

        task_def = TaskDefinition(
            name="complex_task",
            task_type=TaskType.SCHEDULED,
            handler=test_handler,
            description="A complex test task",
            priority=8,
            timeout_seconds=60,
            max_retries=5,
            retry_delay_seconds=2,
            retry_exponential_backoff=True,
            tags=tags,
            metadata=metadata,
            schedule_cron="0 */30 * * *",
            schedule_interval=schedule_interval,
            schedule_at=schedule_time,
            dependencies=dependencies,
            conditions=conditions,
        )

        assert task_def.name == "complex_task"
        assert task_def.task_type == TaskType.SCHEDULED
        assert task_def.handler == test_handler
        assert task_def.description == "A complex test task"
        assert task_def.priority == 8
        assert task_def.timeout_seconds == 60
        assert task_def.max_retries == 5
        assert task_def.retry_delay_seconds == 2
        assert task_def.retry_exponential_backoff is True
        assert task_def.tags == tags
        assert task_def.metadata == metadata
        assert task_def.schedule_cron == "0 */30 * * *"
        assert task_def.schedule_interval == schedule_interval
        assert task_def.schedule_at == schedule_time
        assert task_def.dependencies == dependencies
        assert task_def.conditions == conditions

    def test_task_definition_validation_errors(self):
        """Test TaskDefinition validation errors"""
        # Non-callable handler
        with pytest.raises(ValueError, match="Handler must be callable"):
            TaskDefinition(
                name="test", task_type=TaskType.BATCH, handler="not_callable"
            )

        # Invalid priority
        def test_handler(context: TaskContext):
            return "test"

        with pytest.raises(ValueError, match="Priority must be between 1-10"):
            TaskDefinition(
                name="test", task_type=TaskType.BATCH, handler=test_handler, priority=0
            )

        with pytest.raises(ValueError, match="Priority must be between 1-10"):
            TaskDefinition(
                name="test", task_type=TaskType.BATCH, handler=test_handler, priority=11
            )

    def test_handler_signature_validation(self):
        """Test handler signature validation"""

        # Handler without parameters should raise error
        def no_params_handler():
            return "test"

        with pytest.raises(ValueError, match="Handler must accept TaskContext"):
            TaskDefinition(
                name="test", task_type=TaskType.BATCH, handler=no_params_handler
            )

        # Handler with correct signature should work
        def correct_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="test", task_type=TaskType.BATCH, handler=correct_handler
        )
        assert task_def.handler == correct_handler

    def test_can_execute_without_conditions(self):
        """Test can_execute without conditions"""

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="test", task_type=TaskType.BATCH, handler=test_handler, conditions=[]
        )

        context = TaskContext(
            task_id="test", task_name="test", task_type=TaskType.BATCH
        )

        assert task_def.can_execute(context) is True

    def test_can_execute_with_passing_conditions(self):
        """Test can_execute with passing conditions"""

        def test_handler(context: TaskContext):
            return "test"

        def condition1(context: TaskContext):
            return True

        def condition2(context: TaskContext):
            return context.retry_count < 5

        task_def = TaskDefinition(
            name="test",
            task_type=TaskType.BATCH,
            handler=test_handler,
            conditions=[condition1, condition2],
        )

        context = TaskContext(
            task_id="test", task_name="test", task_type=TaskType.BATCH, retry_count=2
        )

        assert task_def.can_execute(context) is True

    def test_can_execute_with_failing_conditions(self):
        """Test can_execute with failing conditions"""

        def test_handler(context: TaskContext):
            return "test"

        def failing_condition(context: TaskContext):
            return False

        task_def = TaskDefinition(
            name="test",
            task_type=TaskType.BATCH,
            handler=test_handler,
            conditions=[failing_condition],
        )

        context = TaskContext(
            task_id="test", task_name="test", task_type=TaskType.BATCH
        )

        assert task_def.can_execute(context) is False

    def test_can_execute_with_exception_in_condition(self):
        """Test can_execute with exception in condition"""

        def test_handler(context: TaskContext):
            return "test"

        def exception_condition(context: TaskContext):
            raise ValueError("Condition error")

        task_def = TaskDefinition(
            name="test",
            task_type=TaskType.BATCH,
            handler=test_handler,
            conditions=[exception_condition],
        )

        context = TaskContext(
            task_id="test", task_name="test", task_type=TaskType.BATCH
        )

        assert task_def.can_execute(context) is False
        assert "condition_error" in context.metadata
        assert "Condition error" in context.metadata["condition_error"]

    @pytest.mark.asyncio
    async def test_execute_sync_handler(self):
        """Test execute with sync handler"""

        def sync_handler(context: TaskContext):
            return f"sync_result_{context.task_id}"

        task_def = TaskDefinition(
            name="sync_task", task_type=TaskType.BATCH, handler=sync_handler
        )

        context = TaskContext(
            task_id="sync-123", task_name="sync_task", task_type=TaskType.BATCH
        )

        result = await task_def.execute(context)

        assert result.is_success()
        assert result.value == "sync_result_sync-123"

    @pytest.mark.asyncio
    async def test_execute_async_handler(self):
        """Test execute with async handler"""

        async def async_handler(context: TaskContext):
            await asyncio.sleep(0.001)  # Small delay
            return f"async_result_{context.task_name}"

        task_def = TaskDefinition(
            name="async_task", task_type=TaskType.BACKGROUND, handler=async_handler
        )

        context = TaskContext(
            task_id="async-456", task_name="async_task", task_type=TaskType.BACKGROUND
        )

        result = await task_def.execute(context)

        assert result.is_success()
        assert result.value == "async_result_async_task"

    @pytest.mark.asyncio
    async def test_execute_with_conditions_fail(self):
        """Test execute when conditions fail"""

        def test_handler(context: TaskContext):
            return "should_not_run"

        def failing_condition(context: TaskContext):
            return False

        task_def = TaskDefinition(
            name="conditional_task",
            task_type=TaskType.BATCH,
            handler=test_handler,
            conditions=[failing_condition],
        )

        context = TaskContext(
            task_id="test", task_name="conditional_task", task_type=TaskType.BATCH
        )

        result = await task_def.execute(context)

        assert result.is_failure()
        assert "conditions not met" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test execute with timeout"""

        async def slow_handler(context: TaskContext):
            await asyncio.sleep(1.0)  # Will timeout
            return "slow_result"

        task_def = TaskDefinition(
            name="slow_task",
            task_type=TaskType.BATCH,
            handler=slow_handler,
            timeout_seconds=0.1,  # Very short timeout
        )

        context = TaskContext(
            task_id="slow-test", task_name="slow_task", task_type=TaskType.BATCH
        )

        result = await task_def.execute(context)

        assert result.is_failure()
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_with_handler_exception(self):
        """Test execute when handler raises exception"""

        def failing_handler(context: TaskContext):
            raise RuntimeError("Handler failed")

        task_def = TaskDefinition(
            name="failing_task", task_type=TaskType.BATCH, handler=failing_handler
        )

        context = TaskContext(
            task_id="fail-test", task_name="failing_task", task_type=TaskType.BATCH
        )

        result = await task_def.execute(context)

        assert result.is_failure()
        assert "Handler failed" in result.error

    def test_get_next_run_time_none(self):
        """Test get_next_run_time when no schedule"""

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="no_schedule_task", task_type=TaskType.BATCH, handler=test_handler
        )

        assert task_def.get_next_run_time() is None

    def test_get_next_run_time_schedule_at(self):
        """Test get_next_run_time with schedule_at"""

        def test_handler(context: TaskContext):
            return "test"

        future_time = datetime.now() + timedelta(hours=2)
        task_def = TaskDefinition(
            name="scheduled_at_task",
            task_type=TaskType.SCHEDULED,
            handler=test_handler,
            schedule_at=future_time,
        )

        next_run = task_def.get_next_run_time()
        assert next_run == future_time

        # Past time should return None (or next interval/cron if set)
        past_time = datetime.now() - timedelta(hours=1)
        task_def.schedule_at = past_time
        next_run = task_def.get_next_run_time()
        assert next_run is None

    def test_get_next_run_time_interval(self):
        """Test get_next_run_time with schedule_interval"""

        def test_handler(context: TaskContext):
            return "test"

        interval = timedelta(minutes=30)
        task_def = TaskDefinition(
            name="interval_task",
            task_type=TaskType.SCHEDULED,
            handler=test_handler,
            schedule_interval=interval,
        )

        from_time = datetime.now()
        next_run = task_def.get_next_run_time(from_time)

        expected = from_time + interval
        assert abs((next_run - expected).total_seconds()) < 1  # Allow small difference

    def test_get_next_run_time_cron_hourly(self):
        """Test get_next_run_time with hourly cron"""

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="cron_hourly_task",
            task_type=TaskType.SCHEDULED,
            handler=test_handler,
            schedule_cron="0 * * * *",  # Every hour
        )

        from_time = datetime.now().replace(minute=30, second=0, microsecond=0)
        next_run = task_def.get_next_run_time(from_time)

        # Should be next hour at minute 0
        expected = from_time.replace(minute=0) + timedelta(hours=1)
        assert next_run == expected

    def test_get_next_run_time_cron_daily(self):
        """Test get_next_run_time with daily cron"""

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="cron_daily_task",
            task_type=TaskType.SCHEDULED,
            handler=test_handler,
            schedule_cron="0 0 * * *",  # Daily at midnight
        )

        from_time = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        next_run = task_def.get_next_run_time(from_time)

        # Should be next day at midnight
        expected = from_time.replace(hour=0, minute=0) + timedelta(days=1)
        assert next_run == expected

    def test_get_next_run_time_invalid_cron(self):
        """Test get_next_run_time with invalid cron"""

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="invalid_cron_task",
            task_type=TaskType.SCHEDULED,
            handler=test_handler,
            schedule_cron="invalid cron",
        )

        next_run = task_def.get_next_run_time()
        assert next_run is None

    def test_add_tag(self):
        """Test add_tag method"""

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="tag_test_task",
            task_type=TaskType.BATCH,
            handler=test_handler,
            tags=["existing"],
        )

        # Add new tag
        task_def.add_tag("new_tag")
        assert "new_tag" in task_def.tags
        assert "existing" in task_def.tags

        # Add duplicate tag (should not duplicate)
        task_def.add_tag("existing")
        assert task_def.tags.count("existing") == 1

    def test_has_tag(self):
        """Test has_tag method"""

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="tag_check_task",
            task_type=TaskType.BATCH,
            handler=test_handler,
            tags=["tag1", "tag2"],
        )

        assert task_def.has_tag("tag1") is True
        assert task_def.has_tag("tag2") is True
        assert task_def.has_tag("nonexistent") is False

    def test_to_dict(self):
        """Test to_dict method"""

        def test_handler(context: TaskContext):
            return "test"

        schedule_at = datetime.now() + timedelta(hours=1)
        schedule_interval = timedelta(minutes=30)

        task_def = TaskDefinition(
            name="dict_test_task",
            task_type=TaskType.PRIORITY,
            handler=test_handler,
            description="Test task for dict conversion",
            priority=7,
            timeout_seconds=120,
            max_retries=4,
            retry_delay_seconds=3,
            retry_exponential_backoff=True,
            tags=["test", "dict"],
            metadata={"env": "test"},
            schedule_cron="0 */30 * * *",
            schedule_interval=schedule_interval,
            schedule_at=schedule_at,
            dependencies=["dep1", "dep2"],
        )

        result_dict = task_def.to_dict()

        assert result_dict["name"] == "dict_test_task"
        assert result_dict["task_type"] == "priority"
        assert result_dict["description"] == "Test task for dict conversion"
        assert result_dict["priority"] == 7
        assert result_dict["timeout_seconds"] == 120
        assert result_dict["max_retries"] == 4
        assert result_dict["retry_delay_seconds"] == 3
        assert result_dict["retry_exponential_backoff"] is True
        assert result_dict["tags"] == ["test", "dict"]
        assert result_dict["metadata"] == {"env": "test"}
        assert result_dict["schedule_cron"] == "0 */30 * * *"
        assert result_dict["schedule_interval"] == schedule_interval.total_seconds()
        assert result_dict["schedule_at"] == schedule_at.isoformat()
        assert result_dict["dependencies"] == ["dep1", "dep2"]


class TestTaskRegistry:
    """Test TaskRegistry class"""

    def test_registry_creation(self):
        """Test TaskRegistry creation"""
        registry = TaskRegistry()
        assert len(registry._tasks) == 0
        assert len(registry._handlers) == 0

    def test_register_task(self):
        """Test task registration"""
        registry = TaskRegistry()

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="register_test", task_type=TaskType.BATCH, handler=test_handler
        )

        registry.register(task_def)

        assert "register_test" in registry._tasks
        assert "register_test" in registry._handlers
        assert registry._tasks["register_test"] == task_def
        assert registry._handlers["register_test"] == test_handler

    def test_register_duplicate_task(self):
        """Test registering duplicate task name"""
        registry = TaskRegistry()

        def test_handler1(context: TaskContext):
            return "test1"

        def test_handler2(context: TaskContext):
            return "test2"

        task_def1 = TaskDefinition(
            name="duplicate_test", task_type=TaskType.BATCH, handler=test_handler1
        )

        task_def2 = TaskDefinition(
            name="duplicate_test", task_type=TaskType.REALTIME, handler=test_handler2
        )

        registry.register(task_def1)

        with pytest.raises(ValueError, match="Task already registered"):
            registry.register(task_def2)

    def test_unregister_task(self):
        """Test task unregistration"""
        registry = TaskRegistry()

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="unregister_test", task_type=TaskType.BATCH, handler=test_handler
        )

        registry.register(task_def)
        assert "unregister_test" in registry._tasks

        registry.unregister("unregister_test")
        assert "unregister_test" not in registry._tasks
        assert "unregister_test" not in registry._handlers

        # Unregistering non-existent task should not raise error
        registry.unregister("nonexistent")

    def test_get_task(self):
        """Test getting task from registry"""
        registry = TaskRegistry()

        def test_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="get_test", task_type=TaskType.BATCH, handler=test_handler
        )

        registry.register(task_def)

        retrieved = registry.get("get_test")
        assert retrieved == task_def

        # Non-existent task
        assert registry.get("nonexistent") is None

    def test_list_all(self):
        """Test listing all tasks"""
        registry = TaskRegistry()

        def handler1(context: TaskContext):
            return "test1"

        def handler2(context: TaskContext):
            return "test2"

        task1 = TaskDefinition("task1", TaskType.BATCH, handler1)
        task2 = TaskDefinition("task2", TaskType.REALTIME, handler2)

        registry.register(task1)
        registry.register(task2)

        all_tasks = registry.list_all()
        assert len(all_tasks) == 2
        assert task1 in all_tasks
        assert task2 in all_tasks

    def test_list_by_type(self):
        """Test listing tasks by type"""
        registry = TaskRegistry()

        def handler1(context: TaskContext):
            return "test1"

        def handler2(context: TaskContext):
            return "test2"

        def handler3(context: TaskContext):
            return "test3"

        task1 = TaskDefinition("batch1", TaskType.BATCH, handler1)
        task2 = TaskDefinition("batch2", TaskType.BATCH, handler2)
        task3 = TaskDefinition("realtime1", TaskType.REALTIME, handler3)

        registry.register(task1)
        registry.register(task2)
        registry.register(task3)

        batch_tasks = registry.list_by_type(TaskType.BATCH)
        assert len(batch_tasks) == 2
        assert task1 in batch_tasks
        assert task2 in batch_tasks
        assert task3 not in batch_tasks

        realtime_tasks = registry.list_by_type(TaskType.REALTIME)
        assert len(realtime_tasks) == 1
        assert task3 in realtime_tasks

    def test_list_by_tag(self):
        """Test listing tasks by tag"""
        registry = TaskRegistry()

        def handler1(context: TaskContext):
            return "test1"

        def handler2(context: TaskContext):
            return "test2"

        def handler3(context: TaskContext):
            return "test3"

        task1 = TaskDefinition("task1", TaskType.BATCH, handler1, tags=["web", "api"])
        task2 = TaskDefinition("task2", TaskType.BATCH, handler2, tags=["web", "ui"])
        task3 = TaskDefinition("task3", TaskType.BATCH, handler3, tags=["data"])

        registry.register(task1)
        registry.register(task2)
        registry.register(task3)

        web_tasks = registry.list_by_tag("web")
        assert len(web_tasks) == 2
        assert task1 in web_tasks
        assert task2 in web_tasks

        api_tasks = registry.list_by_tag("api")
        assert len(api_tasks) == 1
        assert task1 in api_tasks

        nonexistent_tasks = registry.list_by_tag("nonexistent")
        assert len(nonexistent_tasks) == 0

    def test_list_scheduled(self):
        """Test listing scheduled tasks"""
        registry = TaskRegistry()

        def handler1(context: TaskContext):
            return "test1"

        def handler2(context: TaskContext):
            return "test2"

        def handler3(context: TaskContext):
            return "test3"

        def handler4(context: TaskContext):
            return "test4"

        task1 = TaskDefinition(
            "cron_task", TaskType.SCHEDULED, handler1, schedule_cron="0 0 * * *"
        )
        task2 = TaskDefinition(
            "interval_task",
            TaskType.SCHEDULED,
            handler2,
            schedule_interval=timedelta(hours=1),
        )
        task3 = TaskDefinition(
            "at_task",
            TaskType.SCHEDULED,
            handler3,
            schedule_at=datetime.now() + timedelta(hours=1),
        )
        task4 = TaskDefinition("no_schedule", TaskType.BATCH, handler4)

        registry.register(task1)
        registry.register(task2)
        registry.register(task3)
        registry.register(task4)

        scheduled_tasks = registry.list_scheduled()
        assert len(scheduled_tasks) == 3
        assert task1 in scheduled_tasks
        assert task2 in scheduled_tasks
        assert task3 in scheduled_tasks
        assert task4 not in scheduled_tasks


class TestTaskHandlerDecorator:
    """Test task_handler decorator and related functions"""

    def setup_method(self):
        """Setup before each test"""
        # Clear the global registry
        _task_registry._tasks = {}
        _task_registry._handlers = {}

    def test_task_handler_basic(self):
        """Test basic task_handler decorator"""

        @task_handler("basic_task")
        def basic_handler(context: TaskContext):
            return "basic_result"

        # Check if task was registered
        task_def = _task_registry.get("basic_task")
        assert task_def is not None
        assert task_def.name == "basic_task"
        assert task_def.task_type == TaskType.BACKGROUND  # default
        assert task_def.handler == basic_handler

        # Check if original function is returned
        assert basic_handler.__name__ == "basic_handler"

    def test_task_handler_full_options(self):
        """Test task_handler decorator with all options"""
        schedule_time = datetime.now() + timedelta(hours=1)

        def test_condition(context: TaskContext):
            return True

        @task_handler(
            name="full_options_task",
            task_type=TaskType.PRIORITY,
            description="Task with all options",
            priority=9,
            timeout_seconds=300,
            max_retries=5,
            retry_delay_seconds=10,
            retry_exponential_backoff=True,
            tags=["important", "test"],
            schedule_cron="0 */6 * * *",
            schedule_interval=timedelta(hours=6),
            schedule_at=schedule_time,
            dependencies=["other_task"],
            conditions=[test_condition],
            custom_metadata="custom_value",
        )
        def full_options_handler(context: TaskContext):
            return "full_result"

        task_def = _task_registry.get("full_options_task")
        assert task_def is not None
        assert task_def.name == "full_options_task"
        assert task_def.task_type == TaskType.PRIORITY
        assert task_def.description == "Task with all options"
        assert task_def.priority == 9
        assert task_def.timeout_seconds == 300
        assert task_def.max_retries == 5
        assert task_def.retry_delay_seconds == 10
        assert task_def.retry_exponential_backoff is True
        assert task_def.tags == ["important", "test"]
        assert task_def.schedule_cron == "0 */6 * * *"
        assert task_def.schedule_interval == timedelta(hours=6)
        assert task_def.schedule_at == schedule_time
        assert task_def.dependencies == ["other_task"]
        assert task_def.conditions == [test_condition]
        assert task_def.metadata["custom_metadata"] == "custom_value"

    def test_task_handler_with_docstring(self):
        """Test task_handler using function docstring as description"""

        @task_handler("docstring_task")
        def docstring_handler(context: TaskContext):
            """This is a test handler with docstring."""
            return "docstring_result"

        task_def = _task_registry.get("docstring_task")
        assert task_def.description == "This is a test handler with docstring."

    def test_get_task_definition_function(self):
        """Test get_task_definition function"""

        @task_handler("get_test_task")
        def get_test_handler(context: TaskContext):
            return "get_test_result"

        task_def = get_task_definition("get_test_task")
        assert task_def is not None
        assert task_def.name == "get_test_task"

        assert get_task_definition("nonexistent") is None

    def test_list_task_definitions_function(self):
        """Test list_task_definitions function"""

        @task_handler("list_test1")
        def handler1(context: TaskContext):
            return "result1"

        @task_handler("list_test2")
        def handler2(context: TaskContext):
            return "result2"

        all_tasks = list_task_definitions()
        assert len(all_tasks) >= 2  # May have other tasks from other tests

        task_names = [task.name for task in all_tasks]
        assert "list_test1" in task_names
        assert "list_test2" in task_names

    def test_create_task_definition_function(self):
        """Test create_task_definition function"""

        def create_test_handler(context: TaskContext):
            return "create_test_result"

        task_def = create_task_definition(
            name="create_test_task",
            handler=create_test_handler,
            task_type=TaskType.REALTIME,
            priority=7,
        )

        assert task_def.name == "create_test_task"
        assert task_def.task_type == TaskType.REALTIME
        assert task_def.priority == 7
        assert task_def.handler == create_test_handler

        # Check if registered
        registered_task = _task_registry.get("create_test_task")
        assert registered_task == task_def

    def test_batch_task_decorator(self):
        """Test batch_task convenience decorator"""

        @batch_task("batch_convenience_task", priority=8)
        def batch_handler(context: TaskContext):
            return "batch_result"

        task_def = _task_registry.get("batch_convenience_task")
        assert task_def is not None
        assert task_def.task_type == TaskType.BATCH
        assert task_def.priority == 8

    def test_scheduled_task_decorator(self):
        """Test scheduled_task convenience decorator"""

        @scheduled_task("scheduled_convenience_task", "0 0 * * *", priority=6)
        def scheduled_handler(context: TaskContext):
            return "scheduled_result"

        task_def = _task_registry.get("scheduled_convenience_task")
        assert task_def is not None
        assert task_def.task_type == TaskType.SCHEDULED
        assert task_def.schedule_cron == "0 0 * * *"
        assert task_def.priority == 6

    def test_realtime_task_decorator(self):
        """Test realtime_task convenience decorator"""

        @realtime_task("realtime_convenience_task", max_retries=1)
        def realtime_handler(context: TaskContext):
            return "realtime_result"

        task_def = _task_registry.get("realtime_convenience_task")
        assert task_def is not None
        assert task_def.task_type == TaskType.REALTIME
        assert task_def.max_retries == 1

    def test_priority_task_decorator(self):
        """Test priority_task convenience decorator"""

        @priority_task("priority_convenience_task", priority=9)
        def priority_handler(context: TaskContext):
            return "priority_result"

        task_def = _task_registry.get("priority_convenience_task")
        assert task_def is not None
        assert task_def.task_type == TaskType.PRIORITY
        assert task_def.priority == 9

        # Test default priority
        @priority_task("default_priority_task")
        def default_priority_handler(context: TaskContext):
            return "default_priority_result"

        task_def2 = _task_registry.get("default_priority_task")
        assert task_def2.priority == 8  # default for priority_task


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
