"""
Tests for TaskChain and TaskGroup actual execution logic
TaskChain과 TaskGroup의 실제 실행 로직 테스트
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from rfs.async_tasks.base import (
    CallableTask,
    TaskChain,
    TaskGroup,
    TaskMetadata,
)


class MockTask:
    """Mock task that works with async execution"""

    def __init__(self, result_value, delay=0.001, should_fail=False):
        self.result_value = result_value
        self.delay = delay
        self.should_fail = should_fail
        self.executed = False

    async def execute(self, context):
        """Mock execute method"""
        await asyncio.sleep(self.delay)
        self.executed = True

        if self.should_fail:
            raise ValueError(f"Mock task failed: {self.result_value}")

        return self.result_value


class TestTaskChainExecution:
    """Test TaskChain execution logic - covers lines 290-306"""

    @pytest.mark.asyncio
    async def test_task_chain_sequential_execution(self):
        """Test TaskChain executes tasks in sequence"""

        task1 = MockTask("result1")
        task2 = MockTask("result2")
        task3 = MockTask("result3")

        chain = TaskChain(tasks=[task1, task2, task3], name="sequential_test")

        start_time = datetime.now()
        results = await chain.execute({"initial": "context"})
        end_time = datetime.now()

        # Verify results
        assert len(results) == 3
        assert results == ["result1", "result2", "result3"]

        # Verify all tasks were executed
        assert task1.executed
        assert task2.executed
        assert task3.executed

        # Verify sequential execution (total time should be sum of delays)
        total_time = (end_time - start_time).total_seconds()
        assert total_time >= 0.003  # 3 * 0.001 seconds minimum

    @pytest.mark.asyncio
    async def test_task_chain_context_propagation_detailed(self):
        """Test detailed context propagation in TaskChain"""

        execution_contexts = []

        def make_context_capture_func(name):
            def capture_context(**kwargs):
                # Capture the context for analysis
                execution_contexts.append((name, dict(kwargs)))
                return {"from": name}

            return capture_context

        task1 = CallableTask(make_context_capture_func("task1"))
        task2 = CallableTask(make_context_capture_func("task2"))
        task3 = CallableTask(make_context_capture_func("task3"))

        chain = TaskChain(tasks=[task1, task2, task3])

        initial_context = {"initial": "value", "shared": "original"}
        results = await chain.execute(initial_context)

        # Analyze captured contexts
        assert len(execution_contexts) == 3

        # First task should get original context
        task1_name, task1_context = execution_contexts[0]
        assert task1_name == "task1"
        assert task1_context["initial"] == "value"
        assert task1_context["shared"] == "original"

        # Second task should get previous result and all results
        task2_name, task2_context = execution_contexts[1]
        assert task2_name == "task2"
        assert "previous_result" in task2_context
        assert "all_results" in task2_context
        assert task2_context["initial"] == "value"  # Original context preserved
        assert task2_context["from"] == "task1"  # Dict result merged

        # Third task should have all accumulated context
        task3_name, task3_context = execution_contexts[2]
        assert task3_name == "task3"
        assert "previous_result" in task3_context
        assert "all_results" in task3_context
        assert task3_context["from"] == "task2"  # Latest dict result

    @pytest.mark.asyncio
    async def test_task_chain_empty_tasks(self):
        """Test TaskChain with no tasks"""

        chain = TaskChain(tasks=[])
        results = await chain.execute({"test": "context"})

        assert results == []

    @pytest.mark.asyncio
    async def test_task_chain_single_task(self):
        """Test TaskChain with single task"""

        task = MockTask("single_result")
        chain = TaskChain(tasks=[task])

        results = await chain.execute({})

        assert len(results) == 1
        assert results[0] == "single_result"

    @pytest.mark.asyncio
    async def test_task_chain_non_dict_result_handling(self):
        """Test TaskChain handling of non-dict results - covers line 304-306"""

        def make_result_func(result):
            def result_func(**kwargs):
                return result

            return result_func

        # Mix of dict and non-dict results
        task1 = CallableTask(make_result_func({"key": "dict_result"}))
        task2 = CallableTask(make_result_func("string_result"))
        task3 = CallableTask(make_result_func(42))
        task4 = CallableTask(make_result_func({"another": "dict"}))

        chain = TaskChain(tasks=[task1, task2, task3, task4])

        results = await chain.execute({"initial": "context"})

        assert len(results) == 4
        assert results[0] == {"key": "dict_result"}
        assert results[1] == "string_result"
        assert results[2] == 42
        assert results[3] == {"another": "dict"}


class TestTaskGroupExecution:
    """Test TaskGroup execution logic - covers lines 319-336"""

    @pytest.mark.asyncio
    async def test_task_group_parallel_execution_timing(self):
        """Test TaskGroup executes tasks in parallel"""

        # Tasks with different delays
        task1 = MockTask("result1", delay=0.01)
        task2 = MockTask("result2", delay=0.02)
        task3 = MockTask("result3", delay=0.01)

        group = TaskGroup(tasks=[task1, task2, task3], fail_fast=False)

        start_time = datetime.now()
        results = await group.execute({})
        end_time = datetime.now()

        # Verify results (order may vary due to parallel execution)
        assert len(results) == 3
        assert set(results) == {"result1", "result2", "result3"}

        # Verify parallel execution (should be faster than sequential)
        total_time = (end_time - start_time).total_seconds()
        assert total_time < 0.05  # Much less than 0.04 (sum of delays)
        assert total_time >= 0.02  # At least the longest delay

    @pytest.mark.asyncio
    async def test_task_group_fail_fast_cancellation_detailed(self):
        """Test TaskGroup fail_fast mode with detailed cancellation - covers lines 322-333"""

        task1 = MockTask("quick_success", delay=0.001)
        task2 = MockTask("will_fail", delay=0.005, should_fail=True)
        task3 = MockTask("slow_task", delay=1.0)  # Should be cancelled

        group = TaskGroup(tasks=[task1, task2, task3], fail_fast=True)

        start_time = datetime.now()

        with pytest.raises(ValueError, match="Mock task failed: will_fail"):
            await group.execute({})

        end_time = datetime.now()

        # Should fail quickly, not wait for slow task
        total_time = (end_time - start_time).total_seconds()
        assert total_time < 0.1  # Much less than 1 second

        # Quick task should have succeeded
        assert task1.executed
        # Failing task should have been attempted
        assert task2.executed
        # Slow task may or may not have started, but shouldn't complete

    @pytest.mark.asyncio
    async def test_task_group_no_fail_fast_with_exceptions(self):
        """Test TaskGroup without fail_fast handles exceptions - covers line 336"""

        task1 = MockTask("success1", delay=0.001)
        task2 = MockTask("will_fail", delay=0.002, should_fail=True)
        task3 = MockTask("success2", delay=0.001)

        group = TaskGroup(tasks=[task1, task2, task3], fail_fast=False)

        results = await group.execute({})

        # Should return all results including exceptions
        assert len(results) == 3

        # Find success and exception results
        success_results = [r for r in results if isinstance(r, str)]
        exception_results = [r for r in results if isinstance(r, Exception)]

        assert len(success_results) == 2
        assert len(exception_results) == 1
        assert set(success_results) == {"success1", "success2"}
        assert "Mock task failed: will_fail" in str(exception_results[0])

    @pytest.mark.asyncio
    async def test_task_group_empty_tasks(self):
        """Test TaskGroup with no tasks"""

        group = TaskGroup(tasks=[])
        results = await group.execute({})

        assert results == []

    @pytest.mark.asyncio
    async def test_task_group_single_task(self):
        """Test TaskGroup with single task"""

        task = MockTask("single_result")
        group = TaskGroup(tasks=[task])

        results = await group.execute({})

        assert len(results) == 1
        assert results[0] == "single_result"

    @pytest.mark.asyncio
    async def test_task_group_context_isolation(self):
        """Test TaskGroup tasks receive separate context copies"""

        def modify_context(**kwargs):
            kwargs["modified"] = True
            return f"task_result_{kwargs.get('task_id', 'unknown')}"

        task1 = CallableTask(modify_context)
        task2 = CallableTask(modify_context)
        task3 = CallableTask(modify_context)

        group = TaskGroup(tasks=[task1, task2, task3])

        original_context = {"task_id": "shared", "original": "value"}
        results = await group.execute(original_context)

        # All tasks should have executed successfully
        assert len(results) == 3
        for result in results:
            assert result == "task_result_shared"

        # Original context should not be modified
        assert "modified" not in original_context
        assert original_context["original"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
