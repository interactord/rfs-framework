"""
Final coverage tests for decorators.py to reach 100%
Missing lines: [224, 323, 324, 327, 328, 331, 332, 336]
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from rfs.async_tasks.decorators import chain_tasks, task_callback


class TestFinalCoverage:
    """Final coverage tests for missing lines"""

    @pytest.mark.asyncio
    async def test_chain_tasks_return_coverage(self):
        """Line 224 coverage - chain_tasks return statement"""

        def task1(**kwargs):
            # CallableTask passes context as kwargs
            return {"result": "task1", "input": kwargs.get("input", 0)}

        def task2(**kwargs):
            return {"result": "task2", "previous": kwargs.get("result", None)}

        @chain_tasks(task1, task2)
        async def test_chain():
            pass

        # Line 224: return results
        results = await test_chain(context={"input": 42})

        # Verify the return happened (line 224)
        assert results is not None
        assert isinstance(results, list)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_task_callback_complete_branch(self):
        """Lines 323-324 coverage - on_complete callback execution"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="callback_test")
        mock_manager.add_callback = AsyncMock()

        complete_calls = []

        def handle_complete(result):
            # Line 323-324: if on_complete: on_complete(result)
            complete_calls.append(result)
            return f"Handled: {result}"

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @task_callback(on_complete=handle_complete)
            async def test_task():
                return "test result"

            await test_task()

            # Get the callback object and test the on_complete method
            callback_obj = mock_manager.add_callback.call_args[0][0]

            # Trigger on_complete to cover lines 323-324
            callback_obj.on_complete("test_result")

            # Verify the callback was executed
            assert len(complete_calls) == 1
            assert complete_calls[0] == "test_result"

    @pytest.mark.asyncio
    async def test_task_callback_error_branch(self):
        """Lines 327-328 coverage - on_error callback execution"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="error_test")
        mock_manager.add_callback = AsyncMock()

        error_calls = []

        def handle_error(error):
            # Line 327-328: if on_error: on_error(error)
            error_calls.append(str(error))
            return f"Error handled: {error}"

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @task_callback(on_error=handle_error)
            async def test_task():
                return "test result"

            await test_task()

            callback_obj = mock_manager.add_callback.call_args[0][0]

            # Trigger on_error to cover lines 327-328
            test_error = ValueError("Test error")
            callback_obj.on_error({"task_id": "test"}, test_error)

            assert len(error_calls) == 1
            assert "Test error" in error_calls[0]

    @pytest.mark.asyncio
    async def test_task_callback_cancel_branch(self):
        """Lines 331-332 coverage - on_cancel callback execution"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="cancel_test")
        mock_manager.add_callback = AsyncMock()

        cancel_calls = []

        def handle_cancel(metadata):
            # Line 331-332: if on_cancel: on_cancel(metadata)
            cancel_calls.append(metadata)
            return f"Cancel handled: {metadata}"

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @task_callback(on_cancel=handle_cancel)
            async def test_task():
                return "test result"

            await test_task()

            callback_obj = mock_manager.add_callback.call_args[0][0]

            # Trigger on_cancel to cover lines 331-332
            test_metadata = {"task_id": "test_cancel", "reason": "user_cancelled"}
            callback_obj.on_cancel(test_metadata)

            assert len(cancel_calls) == 1
            assert cancel_calls[0] == test_metadata

    @pytest.mark.asyncio
    async def test_task_callback_timeout_branch(self):
        """Line 336 coverage - on_timeout calling on_error"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="timeout_test")
        mock_manager.add_callback = AsyncMock()

        timeout_error_calls = []

        def handle_error(error):
            # Line 336: on_error(TimeoutError("Task timed out"))
            timeout_error_calls.append(error)
            return f"Timeout error: {error}"

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @task_callback(
                on_error=handle_error
            )  # on_error provided, on_complete/cancel not
            async def test_task():
                return "test result"

            await test_task()

            callback_obj = mock_manager.add_callback.call_args[0][0]

            # Trigger on_timeout to cover line 336
            # This should call on_error with TimeoutError
            callback_obj.on_timeout({"task_id": "timeout_test"})

            assert len(timeout_error_calls) == 1
            assert isinstance(timeout_error_calls[0], TimeoutError)
            assert "Task timed out" in str(timeout_error_calls[0])
