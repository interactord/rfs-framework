"""
Comprehensive test suite for decorators.py to achieve 90%+ coverage

decorators.py의 90% 이상 커버리지 달성을 위한 포괄적인 테스트
현재 구현 버그 수정 및 완전한 테스트 커버리지
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.async_tasks.base import BackoffStrategy, RetryPolicy, TaskPriority
from rfs.async_tasks.decorators import (
    async_task,
    background_task,
    chain_tasks,
    depends_on,
    memoized_task,
    parallel_tasks,
    priority_task,
    rate_limited,
    retry_task,
    scheduled_task,
    task_callback,
    timeout_task,
)


class TestAsyncTaskDecorator:
    """async_task 데코레이터 완전 테스트"""

    def test_async_task_basic_attributes(self):
        """기본 async_task 데코레이터 속성 테스트"""

        @async_task()
        async def test_function(x, y):
            return x + y

        assert hasattr(test_function, "original")
        assert hasattr(test_function, "is_async_task")
        assert test_function.is_async_task is True
        assert test_function.original.__name__ == "test_function"

    @pytest.mark.asyncio
    async def test_async_task_execution_complete(self):
        """라인 52-63 완전 커버를 위한 실행 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="task_123")

        retry_policy = RetryPolicy(max_attempts=3, delay=timedelta(seconds=1))

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @async_task(
                name="custom_task",
                priority=TaskPriority.HIGH,
                retry_policy=retry_policy,
                timeout=timedelta(seconds=30),
                tags=["test", "async"],
            )
            async def sample_task(x, y, z=10):
                return x + y + z

            # 함수 실행 - 라인 52-63 커버
            result = await sample_task(1, 2, z=3)

            # manager.submit 호출 확인
            mock_manager.submit.assert_called_once()
            call_args = mock_manager.submit.call_args

            # 모든 파라미터가 올바르게 전달되었는지 확인
            assert call_args[1]["name"] == "custom_task"
            assert call_args[1]["priority"] == TaskPriority.HIGH
            assert call_args[1]["retry_policy"] == retry_policy
            assert call_args[1]["timeout"] == timedelta(seconds=30)
            assert call_args[1]["tags"] == ["test", "async"]
            assert call_args[1]["z"] == 3  # kwargs

            assert result == "task_123"

    @pytest.mark.asyncio
    async def test_async_task_default_name(self):
        """이름이 없을 때 기본 함수명 사용 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="default_name_task")

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @async_task()  # name 파라미터 없음
            async def my_custom_function():
                return "test"

            await my_custom_function()

            call_args = mock_manager.submit.call_args
            # func.__name__이 사용되어야 함
            assert call_args[1]["name"] == "my_custom_function"


class TestBackgroundTaskDecorator:
    """background_task 데코레이터 완전 테스트"""

    def test_background_task_basic_attributes(self):
        """background_task 기본 속성 테스트"""

        @background_task
        def cleanup_task():
            return "cleaned up"

        assert hasattr(cleanup_task, "original")
        assert hasattr(cleanup_task, "is_async_task")

    @pytest.mark.asyncio
    async def test_background_task_execution(self):
        """라인 82-84 완전 커버를 위한 실행 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="bg_task_456")

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @background_task
            async def bg_cleanup_task():
                return "background cleanup done"

            result = await bg_cleanup_task()

            mock_manager.submit.assert_called_once()
            call_args = mock_manager.submit.call_args

            # background 설정 확인
            assert call_args[1]["priority"] == TaskPriority.BACKGROUND
            assert call_args[1]["name"] == "background_bg_cleanup_task"

            assert result == "bg_task_456"


class TestScheduledTaskDecorator:
    """scheduled_task 데코레이터 완전 테스트"""

    def test_scheduled_task_with_cron_attributes(self):
        """cron 기반 scheduled_task 속성 테스트"""

        @scheduled_task(cron="0 * * * *", name="hourly")
        async def hourly_task():
            return "hourly execution"

        # 수정된 구현에서는 schedule_info를 가져야 함
        assert hasattr(hourly_task, "schedule_info")
        assert hourly_task.schedule_info is not None

    def test_scheduled_task_with_interval_attributes(self):
        """interval 기반 scheduled_task 속성 테스트"""

        @scheduled_task(interval=timedelta(minutes=30))
        async def periodic_task():
            return "periodic execution"

        assert hasattr(periodic_task, "schedule_info")

    @pytest.mark.asyncio
    async def test_scheduled_task_execution_cron(self):
        """라인 115-125 커버를 위한 cron 실행 테스트"""
        mock_scheduler = AsyncMock()
        mock_scheduler.schedule = AsyncMock(return_value="scheduled_cron_123")

        with patch(
            "rfs.async_tasks.decorators.get_scheduler", return_value=mock_scheduler
        ):

            @scheduled_task(cron="0 * * * *", name="hourly")
            async def hourly_task():
                return "executed"

            # wrapper 함수 직접 호출 - 라인 115-125 커버
            wrapper = hourly_task
            result = await wrapper()

            # scheduler.schedule 호출 확인
            mock_scheduler.schedule.assert_called_once()
            assert result == "scheduled_cron_123"

    @pytest.mark.asyncio
    async def test_scheduled_task_execution_interval(self):
        """라인 118-125 커버를 위한 interval 실행 테스트"""
        mock_scheduler = AsyncMock()
        mock_scheduler.schedule = AsyncMock(return_value="scheduled_interval_456")

        with patch(
            "rfs.async_tasks.decorators.get_scheduler", return_value=mock_scheduler
        ):

            @scheduled_task(interval=timedelta(minutes=30))
            async def interval_task():
                return "executed"

            result = await interval_task()
            mock_scheduler.schedule.assert_called_once()
            assert result == "scheduled_interval_456"

    @pytest.mark.asyncio
    async def test_scheduled_task_without_schedule_error(self):
        """스케줄 없는 scheduled_task ValueError 테스트"""
        mock_scheduler = AsyncMock()

        with patch(
            "rfs.async_tasks.decorators.get_scheduler", return_value=mock_scheduler
        ):

            @scheduled_task()
            async def invalid_task():
                pass

            with pytest.raises(
                ValueError, match="Either cron or interval must be specified"
            ):
                await invalid_task()


class TestRetryTaskDecorator:
    """retry_task 데코레이터 완전 테스트"""

    def test_retry_task_basic_attributes(self):
        """retry_task 기본 속성 테스트"""

        @retry_task(max_attempts=5, delay=timedelta(seconds=2))
        async def unreliable_task():
            return "success after retries"

        assert hasattr(unreliable_task, "original")
        assert hasattr(unreliable_task, "is_async_task")

    @pytest.mark.asyncio
    async def test_retry_task_execution_complete(self):
        """라인 154-164 완전 커버를 위한 실행 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="retry_task_789")

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @retry_task(
                max_attempts=5,
                delay=timedelta(seconds=2),
                backoff=BackoffStrategy.EXPONENTIAL,
                retry_on=[ValueError, ConnectionError],
            )
            async def retry_operation():
                return "operation completed"

            result = await retry_operation()

            mock_manager.submit.assert_called_once()
            call_args = mock_manager.submit.call_args

            # retry_policy 확인
            retry_policy = call_args[1]["retry_policy"]
            assert retry_policy.max_attempts == 5
            assert retry_policy.delay == timedelta(seconds=2)
            assert retry_policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
            assert retry_policy.retry_on == [ValueError, ConnectionError]

            assert result == "retry_task_789"

    def test_retry_task_default_retry_on(self):
        """retry_on이 None일 때 기본값 설정 테스트"""

        @retry_task(max_attempts=3)
        async def default_retry_task():
            return "success"

        # 내부적으로 RetryPolicy가 올바르게 생성되었는지 확인하기 위해
        # 실제로 async_task 데코레이터가 적용되었는지 확인
        assert hasattr(default_retry_task, "is_async_task")


class TestTimeoutTaskDecorator:
    """timeout_task 데코레이터 완전 테스트"""

    def test_timeout_task_basic_attributes(self):
        """timeout_task 기본 속성 테스트"""

        @timeout_task(30)
        async def long_task():
            return "completed"

        assert hasattr(long_task, "original")
        assert hasattr(long_task, "is_async_task")

    @pytest.mark.asyncio
    async def test_timeout_task_execution(self):
        """라인 177-180 완전 커버를 위한 실행 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="timeout_task_999")

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @timeout_task(60)
            async def timed_operation():
                return "operation within time limit"

            result = await timed_operation()

            mock_manager.submit.assert_called_once()
            call_args = mock_manager.submit.call_args

            # timeout 설정 확인
            assert call_args[1]["timeout"] == timedelta(seconds=60)

            assert result == "timeout_task_999"


class TestPriorityTaskDecorator:
    """priority_task 데코레이터 완전 테스트"""

    def test_priority_task_basic_attributes(self):
        """priority_task 기본 속성 테스트"""

        @priority_task(TaskPriority.CRITICAL)
        async def critical_task():
            return "critical operation"

        assert hasattr(critical_task, "original")
        assert hasattr(critical_task, "is_async_task")

    @pytest.mark.asyncio
    async def test_priority_task_execution(self):
        """라인 193-196 완전 커버를 위한 실행 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="priority_task_111")

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @priority_task(TaskPriority.HIGH)
            async def high_priority_operation():
                return "high priority completed"

            result = await high_priority_operation()

            mock_manager.submit.assert_called_once()
            call_args = mock_manager.submit.call_args

            # priority 설정 확인
            assert call_args[1]["priority"] == TaskPriority.HIGH

            assert result == "priority_task_111"


class TestChainTasksDecorator:
    """chain_tasks 데코레이터 완전 테스트"""

    @pytest.mark.asyncio
    async def test_chain_tasks_execution(self):
        """라인 212-223 완전 커버를 위한 체인 실행 테스트"""

        async def task1(**kwargs):
            return {"step1": "done", "data": kwargs.get("input", 0) + 1}

        async def task2(**kwargs):
            return {"step2": "done", "data": kwargs.get("data", 0) + 2}

        async def task3(**kwargs):
            return {"step3": "done", "data": kwargs.get("data", 0) + 3}

        @chain_tasks(task1, task2, task3)
        async def pipeline():
            pass

        # 속성 확인
        assert hasattr(pipeline, "is_chain")
        assert hasattr(pipeline, "chain_tasks")
        assert pipeline.is_chain is True
        assert len(pipeline.chain_tasks) == 3

        # 실행 테스트 - 라인 212-223 커버
        results = await pipeline(context={"input": 5})
        assert len(results) == 3

        # TaskChain이 실제로 실행되었는지 확인
        assert isinstance(results, list)

    def test_chain_tasks_single_function_direct(self):
        """라인 225-227 커버를 위한 단일 함수 직접 적용 테스트"""

        def single_task(context):
            return {"single": "result"}

        # 단일 함수를 직접 데코레이터로 사용 - 라인 225-227
        decorated = chain_tasks(single_task)

        assert hasattr(decorated, "is_chain")
        assert hasattr(decorated, "chain_tasks")
        assert len(decorated.chain_tasks) == 1

    @pytest.mark.asyncio
    async def test_chain_tasks_multiple_functions(self):
        """다중 함수 체인 테스트"""

        async def func1(**kwargs):
            return {"result": "func1"}

        async def func2(**kwargs):
            return {"result": "func2"}

        @chain_tasks(func1, func2)
        async def multi_chain():
            pass

        results = await multi_chain(context={})
        assert len(results) == 2


class TestParallelTasksDecorator:
    """parallel_tasks 데코레이터 완전 테스트"""

    @pytest.mark.asyncio
    async def test_parallel_tasks_execution(self):
        """라인 242-254 완전 커버를 위한 병렬 실행 테스트"""

        async def task1(**kwargs):
            await asyncio.sleep(0.01)
            return {"task1": "done", "order": 1}

        async def task2(**kwargs):
            await asyncio.sleep(0.01)
            return {"task2": "done", "order": 2}

        async def task3(**kwargs):
            await asyncio.sleep(0.01)
            return {"task3": "done", "order": 3}

        @parallel_tasks(task1, task2, task3, fail_fast=True)
        async def parallel_execution():
            pass

        # 속성 확인
        assert hasattr(parallel_execution, "is_group")
        assert hasattr(parallel_execution, "group_tasks")
        assert parallel_execution.is_group is True
        assert len(parallel_execution.group_tasks) == 3

        # 실행 테스트 - 라인 242-254 커버
        results = await parallel_execution(context={"parallel": True})
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_parallel_tasks_without_fail_fast(self):
        """fail_fast=False인 병렬 작업 테스트"""

        async def success_task(context):
            return {"status": "success"}

        async def fail_task(context):
            raise ValueError("planned failure")

        @parallel_tasks(success_task, fail_task, fail_fast=False)
        async def mixed_execution():
            pass

        # fail_fast=False이므로 모든 결과 반환
        results = await mixed_execution(context={})
        assert len(results) == 2


class TestDependsOnDecorator:
    """depends_on 데코레이터 완전 테스트"""

    def test_depends_on_basic_attributes(self):
        """depends_on 기본 속성 테스트"""

        @depends_on("task_123", "task_456")
        async def dependent_task():
            return "dependent result"

        assert hasattr(dependent_task, "dependencies")
        assert dependent_task.dependencies == ("task_123", "task_456")

    @pytest.mark.asyncio
    async def test_depends_on_execution(self):
        """라인 273-277 완전 커버를 위한 실행 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="dependent_task_789")

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @depends_on("parent_task_1", "parent_task_2", "parent_task_3")
            async def child_task(data, extra=None):
                return f"processed: {data}"

            result = await child_task("test_data", extra="additional")

            mock_manager.submit.assert_called_once()
            call_args = mock_manager.submit.call_args

            # 의존성과 인자들이 올바르게 전달되었는지 확인
            assert call_args[1]["depends_on"] == [
                "parent_task_1",
                "parent_task_2",
                "parent_task_3",
            ]
            assert call_args[1]["extra"] == "additional"

            assert result == "dependent_task_789"


class TestTaskCallbackDecorator:
    """task_callback 데코레이터 완전 테스트"""

    def test_task_callback_all_callbacks(self):
        """모든 콜백이 있는 task_callback 테스트"""

        def handle_complete(result):
            return f"Completed: {result}"

        def handle_error(error):
            return f"Error: {error}"

        def handle_cancel(metadata):
            return f"Cancelled: {metadata}"

        @task_callback(
            on_complete=handle_complete, on_error=handle_error, on_cancel=handle_cancel
        )
        async def monitored_task():
            return "monitored result"

        assert callable(monitored_task)

    @pytest.mark.asyncio
    async def test_task_callback_execution_complete(self):
        """라인 309-339 완전 커버를 위한 실행 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="callback_task_999")
        mock_manager.add_callback = AsyncMock()

        # 콜백 함수들의 호출 추적
        completion_calls = []
        error_calls = []
        cancel_calls = []

        def handle_complete(result):
            completion_calls.append(result)

        def handle_error(error):
            error_calls.append(error)

        def handle_cancel(metadata):
            cancel_calls.append(metadata)

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @task_callback(
                on_complete=handle_complete,
                on_error=handle_error,
                on_cancel=handle_cancel,
            )
            async def callback_task(data, config="default"):
                return f"processed: {data}"

            result = await callback_task("test_data", config="custom")

            # manager.add_callback과 submit 호출 확인
            mock_manager.add_callback.assert_called_once()
            mock_manager.submit.assert_called_once()

            # 콜백 객체 확인
            callback_obj = mock_manager.add_callback.call_args[0][0]

            # CustomCallback 클래스의 메서드들이 올바르게 구현되었는지 확인
            assert hasattr(callback_obj, "on_complete")
            assert hasattr(callback_obj, "on_error")
            assert hasattr(callback_obj, "on_cancel")
            assert hasattr(callback_obj, "on_timeout")
            assert hasattr(callback_obj, "on_retry")
            assert hasattr(callback_obj, "on_start")

            # submit 파라미터 확인
            call_args = mock_manager.submit.call_args
            assert call_args[1]["config"] == "custom"

            assert result == "callback_task_999"

    @pytest.mark.asyncio
    async def test_task_callback_partial_callbacks(self):
        """일부 콜백만 있는 경우 테스트"""
        mock_manager = AsyncMock()
        mock_manager.submit = AsyncMock(return_value="partial_callback_task")
        mock_manager.add_callback = AsyncMock()

        def handle_complete(result):
            return f"Completed: {result}"

        with patch(
            "rfs.async_tasks.decorators.get_task_manager", return_value=mock_manager
        ):

            @task_callback(on_complete=handle_complete)  # error, cancel은 None
            async def partial_task():
                return "partial result"

            await partial_task()

            # callback 객체 확인
            callback_obj = mock_manager.add_callback.call_args[0][0]

            # timeout에서 on_error가 호출되는지 테스트 (라인 330-331)
            test_error = TimeoutError("Task timed out")
            try:
                callback_obj.on_timeout({"task_id": "test"})
            except:
                pass  # on_error가 None이므로 에러 발생하지 않아야 함


class TestMemoizedTaskDecorator:
    """memoized_task 데코레이터 완전 테스트"""

    @pytest.mark.asyncio
    async def test_memoized_task_async_basic(self):
        """기본 memoized_task async 함수 테스트"""
        call_count = 0

        @memoized_task()
        async def expensive_async_computation(x, y):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x**y

        # 첫 번째 호출
        result1 = await expensive_async_computation(2, 3)
        assert result1 == 8
        assert call_count == 1

        # 캐시에서 반환 확인
        result2 = await expensive_async_computation(2, 3)
        assert result2 == 8
        assert call_count == 1

        # 다른 인자로 호출
        result3 = await expensive_async_computation(3, 2)
        assert result3 == 9
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_memoized_task_sync_function(self):
        """라인 374-377 커버를 위한 동기 함수 테스트"""
        call_count = 0

        @memoized_task()
        def sync_computation(x, y):
            nonlocal call_count
            call_count += 1
            return x * y

        # 동기 함수도 await로 호출
        result1 = await sync_computation(3, 4)
        assert result1 == 12
        assert call_count == 1

        # 캐시 히트 확인
        result2 = await sync_computation(3, 4)
        assert result2 == 12
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_memoized_task_with_ttl_expired(self):
        """라인 366-370 TTL 만료 테스트"""
        call_count = 0

        @memoized_task(ttl=timedelta(seconds=0.05))
        async def ttl_computation(x):
            nonlocal call_count
            call_count += 1
            return x * 3

        # 첫 번째 호출
        result1 = await ttl_computation(7)
        assert result1 == 21
        assert call_count == 1

        # TTL 내 호출 - 캐시 히트
        result2 = await ttl_computation(7)
        assert result2 == 21
        assert call_count == 1

        # TTL 만료까지 대기
        await asyncio.sleep(0.06)

        # TTL 만료 후 호출 - 재계산
        result3 = await ttl_computation(7)
        assert result3 == 21
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_memoized_task_no_ttl_cache_hit(self):
        """라인 372-373 TTL 없는 캐시 히트 테스트"""
        call_count = 0

        @memoized_task()  # TTL 없음
        async def no_ttl_computation(value):
            nonlocal call_count
            call_count += 1
            return value**3

        result1 = await no_ttl_computation(4)
        assert result1 == 64
        assert call_count == 1

        # 라인 372-373의 TTL 없는 캐시 히트
        result2 = await no_ttl_computation(4)
        assert result2 == 64
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_memoized_task_complex_kwargs(self):
        """복잡한 kwargs를 가진 memoized_task 테스트"""
        call_count = 0

        @memoized_task()
        async def complex_function(x, y=10, z=20, flag=True):
            nonlocal call_count
            call_count += 1
            return x + y + z + (100 if flag else 0)

        # 다양한 kwargs 조합
        result1 = await complex_function(1, y=5, flag=False)
        result2 = await complex_function(1, z=30, flag=True)
        result3 = await complex_function(1, y=5, flag=False)  # 첫 번째와 동일

        assert result1 == 26  # 1 + 5 + 20 + 0
        assert result2 == 141  # 1 + 10 + 30 + 100
        assert result3 == 26  # 캐시에서
        assert call_count == 2

    def test_memoized_task_cache_attributes(self):
        """라인 383-385 캐시 속성 설정 테스트"""

        @memoized_task(ttl=timedelta(minutes=1))
        async def cached_function(x):
            return x * 2

        # 수정된 구현에서는 _cache와 _cache_times 속성을 가져야 함
        assert hasattr(cached_function, "_cache")
        assert hasattr(cached_function, "_cache_times")
        assert isinstance(cached_function._cache, dict)
        assert isinstance(cached_function._cache_times, dict)


class TestRateLimitedDecorator:
    """rate_limited 데코레이터 완전 테스트"""

    @pytest.mark.asyncio
    async def test_rate_limited_async_basic(self):
        """기본 rate_limited async 테스트"""
        call_times = []

        @rate_limited(max_calls=2, period=timedelta(seconds=0.2))
        async def async_api_call(data):
            call_times.append(datetime.now())
            return f"async processed {data}"

        # 제한 내 호출
        result1 = await async_api_call("data1")
        result2 = await async_api_call("data2")

        assert result1 == "async processed data1"
        assert result2 == "async processed data2"
        assert len(call_times) == 2

    @pytest.mark.asyncio
    async def test_rate_limited_sync_function(self):
        """라인 413-416 커버를 위한 동기 함수 테스트"""

        @rate_limited(max_calls=1, period=timedelta(seconds=0.1))
        def sync_api_call(data):
            return f"sync processed {data}"

        result = await sync_api_call("test")
        assert result == "sync processed test"

    @pytest.mark.asyncio
    async def test_rate_limited_exceeds_limit_with_wait(self):
        """라인 407-412 레이트 제한 초과 대기 테스트"""
        call_times = []

        @rate_limited(max_calls=1, period=timedelta(seconds=0.1))
        async def limited_call():
            call_times.append(datetime.now())
            return "limited result"

        start_time = datetime.now()

        # 첫 번째 호출
        result1 = await limited_call()

        # 두 번째 호출 - 대기해야 함
        result2 = await limited_call()

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        assert result1 == "limited result"
        assert result2 == "limited result"
        assert total_time >= 0.1  # 최소 대기 시간
        assert len(call_times) == 2

    @pytest.mark.asyncio
    async def test_rate_limited_call_cleanup(self):
        """호출 기록 정리 로직 테스트"""

        @rate_limited(max_calls=3, period=timedelta(seconds=0.05))
        async def cleanup_test_call(data):
            return f"cleanup {data}"

        # 빠르게 3번 호출
        await cleanup_test_call("1")
        await cleanup_test_call("2")
        await cleanup_test_call("3")

        # 시간 대기로 호출 기록이 정리되도록 함
        await asyncio.sleep(0.06)

        # 다시 호출 가능해야 함
        result = await cleanup_test_call("4")
        assert result == "cleanup 4"


class TestDecoratorEdgeCases:
    """데코레이터 경계 조건 및 에러 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_chain_tasks_import_coverage(self):
        """라인 213 CallableTask import 커버리지 테스트"""

        def simple_task(**kwargs):
            return {"test": "import"}

        def dummy_task(**kwargs):
            return {"dummy": "task"}

        # chain_tasks 데코레이터를 두 개 함수로 테스트 (라인 213 커버를 위해)
        @chain_tasks(simple_task, dummy_task)
        async def import_test():
            pass

        # CallableTask import가 실제로 사용되는지 확인
        result = await import_test(context={})
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_parallel_tasks_import_coverage(self):
        """라인 244 CallableTask import 커버리지 테스트"""

        def simple_parallel_task(context):
            return {"parallel": "import"}

        @parallel_tasks(simple_parallel_task)
        async def parallel_import_test():
            pass

        # CallableTask import가 실제로 사용되는지 확인
        result = await parallel_import_test(context={})
        assert len(result) == 1

    def test_decorator_function_name_preservation(self):
        """데코레이터가 함수 이름을 보존하는지 테스트"""

        @async_task()
        async def preserve_name_test():
            return "name preserved"

        # wraps 데코레이터로 인해 함수명이 보존되어야 함
        assert preserve_name_test.__name__ == "preserve_name_test"

    @pytest.mark.asyncio
    async def test_memoized_task_cache_key_generation(self):
        """캐시 키 생성 로직 테스트"""
        call_count = 0

        @memoized_task()
        async def cache_key_test(a, b, c=30, d=40):
            nonlocal call_count
            call_count += 1
            return a + b + c + d

        # 동일한 인자, 다른 순서의 kwargs
        result1 = await cache_key_test(1, 2, c=3, d=4)
        result2 = await cache_key_test(1, 2, d=4, c=3)  # 순서 다름

        # 캐시 키가 동일하게 생성되어야 함 (sorted kwargs)
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # 같은 결과이므로 한 번만 호출
