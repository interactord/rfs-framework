"""
Tests to achieve 100% coverage for task_definition.py
task_definition.py 100% 커버리지 달성을 위한 테스트
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch

import pytest

from rfs.async_tasks.task_definition import (
    TaskContext,
    TaskDefinition,
    TaskType,
)


class TestTaskDefinitionLine128:
    """Test line 128 - type hint validation error"""

    def test_handler_with_wrong_type_hint(self):
        """Test handler with wrong type hint for first parameter - covers line 128"""

        # Create a handler with wrong type hint
        def wrong_type_handler(context: str, data: Any):  # Wrong type hint
            return data

        # Mock get_type_hints to return wrong type
        with patch("rfs.async_tasks.task_definition.get_type_hints") as mock_hints:
            mock_hints.return_value = {"context": str}  # Wrong type, not TaskContext

            with pytest.raises(ValueError, match="First parameter must be TaskContext"):
                TaskDefinition(
                    name="wrong_hint_task",
                    task_type=TaskType.BATCH,
                    handler=wrong_type_handler,
                )


class TestTaskDefinitionLine163:
    """Test line 163 - sync handler with timeout"""

    @pytest.mark.asyncio
    async def test_sync_handler_with_timeout(self):
        """Test sync handler with timeout - covers line 163"""

        def sync_handler(context: TaskContext, data: str):
            # Simulate some work
            import time

            time.sleep(0.01)  # Short sleep
            return f"sync_result_{data}"

        task_def = TaskDefinition(
            name="sync_timeout_task",
            task_type=TaskType.BATCH,
            handler=sync_handler,
            timeout_seconds=5,  # Set timeout
        )

        context = TaskContext(
            task_id="test-sync-timeout",
            task_name="sync_timeout_task",
            task_type=TaskType.BATCH,
        )

        # Execute with timeout (should succeed since handler is fast)
        result = await task_def.execute(context, "test_data")

        assert result.is_success()
        assert result.value == "sync_result_test_data"

    @pytest.mark.asyncio
    async def test_sync_handler_timeout_exceeded(self):
        """Test sync handler exceeding timeout"""

        def slow_sync_handler(context: TaskContext):
            # This would be slow but we'll mock asyncio.wait_for
            import time

            time.sleep(10)  # Very slow
            return "should_timeout"

        task_def = TaskDefinition(
            name="slow_sync_task",
            task_type=TaskType.BATCH,
            handler=slow_sync_handler,
            timeout_seconds=0.001,  # Very short timeout
        )

        context = TaskContext(
            task_id="test-timeout", task_name="slow_sync_task", task_type=TaskType.BATCH
        )

        # Should timeout
        result = await task_def.execute(context)

        assert result.is_failure()
        assert "timeout" in result.error.lower()


class TestTaskDefinitionLine221:
    """Test line 221 - parse_cron returning None for unknown patterns"""

    def test_parse_cron_unknown_pattern(self):
        """Test parse_cron with unknown pattern - covers line 221"""

        def dummy_handler(context: TaskContext):
            return "test"

        task_def = TaskDefinition(
            name="cron_task",
            task_type=TaskType.SCHEDULED,
            handler=dummy_handler,
            schedule_cron="30 15 * * *",  # 3:30 PM daily - not in simple implementation
        )

        # This cron pattern is not handled by the simple implementation
        # It will reach the end of _parse_cron and return None (line 221)
        from_time = datetime.now()
        next_run = task_def.get_next_run_time(from_time)

        assert next_run is None

    def test_parse_cron_complex_patterns(self):
        """Test various cron patterns that return None"""

        def dummy_handler(context: TaskContext):
            return "test"

        # Test various patterns that aren't handled
        unhandled_patterns = [
            "*/5 * * * *",  # Every 5 minutes
            "0 */2 * * *",  # Every 2 hours
            "0 0 1 * *",  # First day of month
            "0 0 * * 1",  # Every Monday
            "15 14 1 * *",  # Specific day and time
            "0 9-17 * * *",  # Business hours
            "*/15 * * * *",  # Every 15 minutes
        ]

        for pattern in unhandled_patterns:
            task_def = TaskDefinition(
                name="cron_test",
                task_type=TaskType.SCHEDULED,
                handler=dummy_handler,
                schedule_cron=pattern,
            )

            next_run = task_def.get_next_run_time()
            assert next_run is None, f"Pattern {pattern} should return None"


class TestHandlerSignatureValidationEdgeCases:
    """Test additional edge cases for handler signature validation"""

    def test_handler_with_type_hint_no_taskcontext(self):
        """Test handler with type hints but wrong type"""

        def handler_with_different_hint(ctx: dict):
            return "test"

        with patch("rfs.async_tasks.task_definition.get_type_hints") as mock_hints:
            # Return dict type instead of TaskContext
            mock_hints.return_value = {"ctx": dict}

            with pytest.raises(ValueError, match="First parameter must be TaskContext"):
                TaskDefinition(
                    name="wrong_type_task",
                    task_type=TaskType.BATCH,
                    handler=handler_with_different_hint,
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
