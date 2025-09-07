"""
추상 메서드 NotImplementedError 테스트

추상 메서드들이 NotImplementedError를 발생시키는지 확인
"""

from typing import Any, Dict

import pytest

from rfs.async_tasks.base import (
    Task,
    TaskCallback,
    TaskHook,
    TaskMetadata,
    TaskResult,
    TaskStatus,
)
from rfs.core.result import Success


class TestTaskCallbackAbstractMethods:
    """TaskCallback 추상 메서드 테스트"""

    def test_callback_on_start_raises(self):
        """on_start 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            TaskCallback.on_start(None, metadata)

    def test_callback_on_complete_raises(self):
        """on_complete 메서드가 NotImplementedError를 발생시키는지 확인"""
        result = TaskResult(
            task_id="test-id", status=TaskStatus.COMPLETED, value="test"
        )

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            TaskCallback.on_complete(None, result)

    def test_callback_on_error_raises(self):
        """on_error 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()
        error = Exception("test error")

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            TaskCallback.on_error(None, metadata, error)

    def test_callback_on_cancel_raises(self):
        """on_cancel 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            TaskCallback.on_cancel(None, metadata)

    def test_callback_on_timeout_raises(self):
        """on_timeout 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            TaskCallback.on_timeout(None, metadata)

    def test_callback_on_retry_raises(self):
        """on_retry 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            TaskCallback.on_retry(None, metadata, 1)


class TestTaskAbstractMethods:
    """Task 추상 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_task_execute_raises(self):
        """execute 메서드가 NotImplementedError를 발생시키는지 확인"""
        context = {"test": "data"}

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            await Task.execute(None, context)

    def test_task_validate_raises(self):
        """validate 메서드가 NotImplementedError를 발생시키는지 확인"""
        context = {"test": "data"}

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            Task.validate(None, context)

    def test_task_cleanup_raises(self):
        """cleanup 메서드가 NotImplementedError를 발생시키는지 확인"""
        context = {"test": "data"}

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            Task.cleanup(None, context)


class TestTaskHookAbstractMethods:
    """TaskHook 추상 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_hook_before_execute_raises(self):
        """before_execute 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()
        context = {"test": "data"}

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            await TaskHook.before_execute(None, metadata, context)

    @pytest.mark.asyncio
    async def test_hook_after_execute_raises(self):
        """after_execute 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()
        result = "test result"

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            await TaskHook.after_execute(None, metadata, result)

    @pytest.mark.asyncio
    async def test_hook_on_exception_raises(self):
        """on_exception 메서드가 NotImplementedError를 발생시키는지 확인"""
        metadata = TaskMetadata()
        exception = Exception("test error")

        with pytest.raises(NotImplementedError):
            # 추상 메서드 직접 호출
            await TaskHook.on_exception(None, metadata, exception)
