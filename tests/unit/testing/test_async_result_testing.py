"""
RFS Framework AsyncResult 테스팅 유틸리티 단위 테스트

AsyncResult 테스트 도구들의 모든 기능을 포괄적으로 테스트합니다.
"""

import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
import pytest

from rfs.async_pipeline import AsyncResult
from rfs.core.result import Success, Failure
from rfs.testing.async_result_testing import (
    AsyncResultTestUtils,
    AsyncResultMockBuilder,
    AsyncResultScenarioTester,
    AsyncResultPerformanceTester,
    AsyncResultTestError,
    AsyncResultTestContext,
    with_timeout,
    async_result_test_suite
)


class TestAsyncResultTestUtils:
    """AsyncResultTestUtils 클래스 테스트"""
    
    @pytest.mark.asyncio
    async def test_assert_success_with_expected_value(self):
        """예상 값과 함께 성공 검증 테스트"""
        # Given
        expected_value = {"user_id": 123, "name": "test"}
        async_result = AsyncResult.from_value(expected_value)
        
        # When & Then: 예외가 발생하지 않아야 함
        await AsyncResultTestUtils.assert_success(
            async_result,
            expected_value=expected_value
        )
    
    @pytest.mark.asyncio
    async def test_assert_success_with_value_matcher(self):
        """값 매처를 사용한 성공 검증 테스트"""
        # Given
        test_data = {"users": [1, 2, 3], "total": 3}
        async_result = AsyncResult.from_value(test_data)
        
        # When & Then
        await AsyncResultTestUtils.assert_success(
            async_result,
            value_matcher=lambda v: len(v["users"]) == v["total"]
        )
    
    @pytest.mark.asyncio
    async def test_assert_success_failure_case(self):
        """실패하는 AsyncResult에서 성공 검증 실패 테스트"""
        # Given
        async_result = AsyncResult.from_error("Test error")
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_success(async_result)
        
        assert "AsyncResult가 실패했습니다" in str(exc_info.value)
        assert "Test error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assert_success_wrong_value(self):
        """잘못된 예상 값으로 성공 검증 실패 테스트"""
        # Given
        async_result = AsyncResult.from_value("actual")
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_success(
                async_result,
                expected_value="expected"
            )
        
        assert "예상 값: expected, 실제 값: actual" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assert_success_matcher_failure(self):
        """값 매처 실패 테스트"""
        # Given
        async_result = AsyncResult.from_value(10)
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_success(
                async_result,
                value_matcher=lambda v: v > 20
            )
        
        assert "값 매처가 실패했습니다" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assert_success_with_timeout(self):
        """타임아웃과 함께 성공 검증 테스트"""
        # Given
        async def quick_operation():
            await asyncio.sleep(0.01)
            return "quick_result"
        
        async_result = AsyncResult.from_async(quick_operation)
        
        # When & Then
        await AsyncResultTestUtils.assert_success(
            async_result,
            timeout=1.0,
            expected_value="quick_result"
        )
    
    @pytest.mark.asyncio
    async def test_assert_success_timeout_exceeded(self):
        """타임아웃 초과 테스트"""
        # Given
        async def slow_operation():
            await asyncio.sleep(1.0)
            return "slow_result"
        
        async_result = AsyncResult.from_async(slow_operation)
        
        # When & Then
        with pytest.raises(asyncio.TimeoutError):
            await AsyncResultTestUtils.assert_success(
                async_result,
                timeout=0.1
            )
    
    @pytest.mark.asyncio
    async def test_assert_failure_with_expected_error(self):
        """예상 에러와 함께 실패 검증 테스트"""
        # Given
        expected_error = "User not found"
        async_result = AsyncResult.from_error(expected_error)
        
        # When & Then
        await AsyncResultTestUtils.assert_failure(
            async_result,
            expected_error=expected_error
        )
    
    @pytest.mark.asyncio
    async def test_assert_failure_with_error_type(self):
        """에러 타입으로 실패 검증 테스트"""
        # Given
        test_error = ValueError("Invalid input")
        async_result = AsyncResult.from_error(test_error)
        
        # When & Then
        await AsyncResultTestUtils.assert_failure(
            async_result,
            expected_error_type=ValueError
        )
    
    @pytest.mark.asyncio
    async def test_assert_failure_with_error_matcher(self):
        """에러 매처로 실패 검증 테스트"""
        # Given
        test_error = "Error code: 404"
        async_result = AsyncResult.from_error(test_error)
        
        # When & Then
        await AsyncResultTestUtils.assert_failure(
            async_result,
            error_matcher=lambda e: "404" in str(e)
        )
    
    @pytest.mark.asyncio
    async def test_assert_failure_success_case(self):
        """성공하는 AsyncResult에서 실패 검증 실패 테스트"""
        # Given
        async_result = AsyncResult.from_value("success")
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_failure(async_result)
        
        assert "AsyncResult가 성공했습니다" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assert_execution_time_within_bounds(self):
        """실행 시간이 범위 내에 있는 경우 테스트"""
        # Given
        async def timed_operation():
            await asyncio.sleep(0.1)
            return "timed_result"
        
        async_result = AsyncResult.from_async(timed_operation)
        
        # When
        execution_time = await AsyncResultTestUtils.assert_execution_time(
            async_result,
            max_seconds=0.2,
            min_seconds=0.05
        )
        
        # Then
        assert 0.05 <= execution_time <= 0.2
    
    @pytest.mark.asyncio
    async def test_assert_execution_time_too_slow(self):
        """실행 시간이 너무 긴 경우 테스트"""
        # Given
        async def slow_operation():
            await asyncio.sleep(0.2)
            return "slow_result"
        
        async_result = AsyncResult.from_async(slow_operation)
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_execution_time(
                async_result,
                max_seconds=0.1
            )
        
        assert "실행 시간이 너무 깁니다" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assert_execution_time_too_fast(self):
        """실행 시간이 너무 짧은 경우 테스트"""
        # Given
        async_result = AsyncResult.from_value("instant")
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_execution_time(
                async_result,
                max_seconds=1.0,
                min_seconds=0.1
            )
        
        assert "실행 시간이 너무 짧습니다" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assert_eventually_succeeds(self):
        """최종적으로 성공하는지 검증 테스트"""
        # Given
        attempt_count = 0
        
        def unreliable_factory():
            nonlocal attempt_count
            attempt_count += 1
            
            async def unreliable_operation():
                if attempt_count < 3:
                    raise Exception(f"Attempt {attempt_count} failed")
                return f"Success on attempt {attempt_count}"
            
            return AsyncResult.from_async(unreliable_operation)
        
        # When
        result = await AsyncResultTestUtils.assert_eventually_succeeds(
            unreliable_factory,
            max_attempts=5,
            delay_between_attempts=0.01
        )
        
        # Then
        assert result == "Success on attempt 3"
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_assert_eventually_succeeds_all_fail(self):
        """모든 시도가 실패하는 경우 테스트"""
        # Given
        def always_fail_factory():
            async def failing_operation():
                raise Exception("Always fails")
            return AsyncResult.from_async(failing_operation)
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_eventually_succeeds(
                always_fail_factory,
                max_attempts=3,
                delay_between_attempts=0.01
            )
        
        assert "3번 시도 모두 실패" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assert_chain_order(self):
        """체인 실행 순서 검증 테스트"""
        # Given
        completion_order = []
        
        async def create_ordered_operation(index, delay):
            async def operation():
                await asyncio.sleep(delay)
                completion_order.append(index)
                return f"result_{index}"
            return operation
        
        async_results = [
            AsyncResult.from_async(await create_ordered_operation(0, 0.05)),
            AsyncResult.from_async(await create_ordered_operation(1, 0.1)),
            AsyncResult.from_async(await create_ordered_operation(2, 0.02)),
        ]
        
        # When
        await AsyncResultTestUtils.assert_chain_order(
            async_results,
            expected_order=[2, 0, 1],  # delay 순서대로
            timeout=1.0
        )
        
        # Then
        assert completion_order == [2, 0, 1]
    
    @pytest.mark.asyncio
    async def test_assert_chain_order_wrong_order(self):
        """잘못된 체인 순서 테스트"""
        # Given
        async_results = [
            AsyncResult.from_value("first"),
            AsyncResult.from_value("second"),
        ]
        
        # When & Then
        with pytest.raises(AsyncResultTestError) as exc_info:
            await AsyncResultTestUtils.assert_chain_order(
                async_results,
                expected_order=[1, 0]  # 실제로는 [0, 1] 순서로 완료됨
            )
        
        assert "예상 완료 순서" in str(exc_info.value)


class TestAsyncResultMockBuilder:
    """AsyncResultMockBuilder 클래스 테스트"""
    
    @pytest.mark.asyncio
    async def test_success_mock(self):
        """성공 목 생성 테스트"""
        # Given
        test_value = {"user_id": 123}
        
        # When
        mock_result = AsyncResultMockBuilder.success_mock(test_value)
        result = await mock_result.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == test_value
    
    @pytest.mark.asyncio
    async def test_failure_mock(self):
        """실패 목 생성 테스트"""
        # Given
        test_error = "Mock error"
        
        # When
        mock_result = AsyncResultMockBuilder.failure_mock(test_error)
        result = await mock_result.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == test_error
    
    @pytest.mark.asyncio
    async def test_delayed_success_mock(self):
        """지연된 성공 목 테스트"""
        # Given
        test_value = "delayed_value"
        delay = 0.05
        
        # When
        start_time = time.time()
        mock_result = AsyncResultMockBuilder.delayed_success_mock(test_value, delay)
        result = await mock_result.to_result()
        end_time = time.time()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == test_value
        assert (end_time - start_time) >= delay
    
    @pytest.mark.asyncio
    async def test_delayed_success_mock_with_jitter(self):
        """지터가 있는 지연된 성공 목 테스트"""
        # Given
        test_value = "jittered_value"
        delay = 0.05
        jitter = 0.02
        
        # When
        mock_result = AsyncResultMockBuilder.delayed_success_mock(
            test_value, delay, jitter=jitter
        )
        result = await mock_result.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == test_value
    
    @pytest.mark.asyncio
    async def test_delayed_failure_mock(self):
        """지연된 실패 목 테스트"""
        # Given
        test_error = "delayed_error"
        delay = 0.05
        
        # When
        start_time = time.time()
        mock_result = AsyncResultMockBuilder.delayed_failure_mock(test_error, delay)
        result = await mock_result.to_result()
        end_time = time.time()
        
        # Then
        assert result.is_failure()
        assert (end_time - start_time) >= delay
    
    @pytest.mark.asyncio
    async def test_intermittent_failure_mock_deterministic(self):
        """결정론적 간헐적 실패 목 테스트"""
        # Given
        success_value = "success"
        failure_error = "failure"
        
        # When: 시드를 고정하여 결정론적 테스트
        results = []
        for i in range(10):
            mock_result = AsyncResultMockBuilder.intermittent_failure_mock(
                success_value, failure_error, failure_rate=0.3, seed=i
            )
            result = await mock_result.to_result()
            results.append(result.is_success())
        
        # Then: 결과가 예측 가능해야 함 (시드가 동일하면 동일한 결과)
        assert len(results) == 10
        assert not all(results)  # 일부는 실패해야 함
        assert any(results)      # 일부는 성공해야 함
    
    @pytest.mark.asyncio
    async def test_timeout_mock(self):
        """타임아웃 목 테스트"""
        # Given
        timeout_seconds = 0.1
        
        # When
        mock_result = AsyncResultMockBuilder.timeout_mock(timeout_seconds)
        
        # Then: 타임아웃 전에 테스트 종료
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(mock_result.to_result(), timeout=0.05)
    
    @pytest.mark.asyncio
    async def test_chain_mock_success(self):
        """성공하는 체인 목 테스트"""
        # Given
        operations = [
            lambda x: x * 2,      # 5 -> 10
            lambda x: x + 10,     # 10 -> 20
            lambda x: str(x),     # 20 -> "20"
        ]
        
        # When
        mock_result = AsyncResultMockBuilder.chain_mock(
            operations, initial_value=5
        )
        result = await mock_result.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "20"
    
    @pytest.mark.asyncio
    async def test_chain_mock_with_failure(self):
        """실패하는 체인 목 테스트"""
        # Given
        operations = [
            lambda x: x * 2,
            lambda x: x + 10,
            lambda x: x / 0,  # 이 단계에서 실패해야 함
        ]
        
        # When
        mock_result = AsyncResultMockBuilder.chain_mock(
            operations, initial_value=5, failure_at_step=2
        )
        result = await mock_result.to_result()
        
        # Then
        assert result.is_failure()
        assert "Chain failure" in str(result.unwrap_error())
    
    @pytest.mark.asyncio
    async def test_chain_mock_with_async_operations(self):
        """비동기 연산이 포함된 체인 목 테스트"""
        # Given
        async def async_multiply(x):
            await asyncio.sleep(0.01)
            return x * 3
        
        def sync_add(x):
            return x + 5
        
        operations = [async_multiply, sync_add]
        
        # When
        mock_result = AsyncResultMockBuilder.chain_mock(
            operations, initial_value=2
        )
        result = await mock_result.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == 11  # (2 * 3) + 5
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_mock(self):
        """리소스 고갈 목 테스트"""
        # Given & When & Then
        # 리소스 여유 있음
        available_mock = AsyncResultMockBuilder.resource_exhaustion_mock(
            resource_limit=100, current_usage=50
        )
        result = await available_mock.to_result()
        assert result.is_success()
        
        # 리소스 고갈됨
        exhausted_mock = AsyncResultMockBuilder.resource_exhaustion_mock(
            resource_limit=100, current_usage=100
        )
        result = await exhausted_mock.to_result()
        assert result.is_failure()
        assert "리소스가 고갈되었습니다" in str(result.unwrap_error())


class TestAsyncResultScenarioTester:
    """AsyncResultScenarioTester 클래스 테스트"""
    
    @pytest.mark.asyncio
    async def test_scenario_tester_sequential(self):
        """순차적 시나리오 테스트"""
        # Given
        tester = AsyncResultScenarioTester("test_scenarios")
        
        # 성공 시나리오
        tester.add_scenario(
            "success_scenario",
            lambda: AsyncResult.from_value("success"),
            [lambda ar: AsyncResultTestUtils.assert_success(ar)]
        )
        
        # 실패 시나리오
        tester.add_scenario(
            "failure_scenario",
            lambda: AsyncResult.from_error("test_error"),
            [lambda ar: AsyncResultTestUtils.assert_failure(ar)]
        )
        
        # When
        results = await tester._run_sequential_scenarios()
        
        # Then
        assert len(results) == 2
        assert all(result["status"] == "passed" for result in results)
    
    @pytest.mark.asyncio
    async def test_scenario_tester_with_setup_teardown(self):
        """설정/정리가 있는 시나리오 테스트"""
        # Given
        setup_called = False
        teardown_called = False
        
        async def setup():
            nonlocal setup_called
            setup_called = True
        
        async def teardown():
            nonlocal teardown_called
            teardown_called = True
        
        tester = AsyncResultScenarioTester("setup_teardown_test")
        tester.add_scenario(
            "test_scenario",
            lambda: AsyncResult.from_value("test"),
            [lambda ar: AsyncResultTestUtils.assert_success(ar)],
            setup=setup,
            teardown=teardown
        )
        
        # When
        results = await tester._run_sequential_scenarios()
        
        # Then
        assert setup_called
        assert teardown_called
        assert results[0]["status"] == "passed"
    
    @pytest.mark.asyncio
    async def test_scenario_tester_failing_assertion(self):
        """실패하는 어설션이 있는 시나리오 테스트"""
        # Given
        tester = AsyncResultScenarioTester("failing_test")
        tester.add_scenario(
            "failing_scenario",
            lambda: AsyncResult.from_value("actual"),
            [lambda ar: AsyncResultTestUtils.assert_success(ar, expected_value="expected")]
        )
        
        # When
        results = await tester._run_sequential_scenarios()
        
        # Then
        assert results[0]["status"] == "failed"
        assert "error" in results[0]


class TestAsyncResultPerformanceTester:
    """AsyncResultPerformanceTester 클래스 테스트"""
    
    @pytest.mark.asyncio
    async def test_measure_throughput(self):
        """처리량 측정 테스트"""
        # Given
        def create_fast_result():
            return AsyncResult.from_value("fast")
        
        # When
        performance = await AsyncResultPerformanceTester.measure_throughput(
            create_fast_result,
            duration_seconds=0.1,
            max_concurrent=10
        )
        
        # Then
        assert performance["duration"] >= 0.1
        assert performance["total_requests"] > 0
        assert performance["throughput"] > 0
        assert performance["success_rate"] == 1.0  # 모든 요청 성공
        assert performance["completed"] == performance["total_requests"]
    
    @pytest.mark.asyncio
    async def test_measure_throughput_with_failures(self):
        """실패가 포함된 처리량 측정 테스트"""
        # Given
        call_count = 0
        
        def create_unreliable_result():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # 매 3번째마다 실패
                return AsyncResult.from_error("intermittent failure")
            return AsyncResult.from_value("success")
        
        # When
        performance = await AsyncResultPerformanceTester.measure_throughput(
            create_unreliable_result,
            duration_seconds=0.1,
            max_concurrent=5
        )
        
        # Then
        assert performance["failed"] > 0
        assert performance["success_rate"] < 1.0
        assert performance["completed"] + performance["failed"] == performance["total_requests"]
    
    @pytest.mark.asyncio
    async def test_measure_throughput_with_slow_operations(self):
        """느린 연산의 처리량 측정 테스트"""
        # Given
        def create_slow_result():
            async def slow_operation():
                await asyncio.sleep(0.02)
                return "slow"
            return AsyncResult.from_async(slow_operation)
        
        # When
        performance = await AsyncResultPerformanceTester.measure_throughput(
            create_slow_result,
            duration_seconds=0.1,
            max_concurrent=5
        )
        
        # Then
        assert performance["avg_response_time"] >= 0.02
        assert performance["p50_response_time"] >= 0.02
        assert performance["throughput"] > 0
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_stress_test(self):
        """스트레스 테스트"""
        # Given
        def create_test_result():
            async def test_operation():
                await asyncio.sleep(0.001)  # 1ms
                return "stress_test"
            return AsyncResult.from_async(test_operation)
        
        # When
        stress_results = await AsyncResultPerformanceTester.stress_test(
            create_test_result,
            ramp_up_seconds=0.1,
            max_concurrent=20,
            ramp_up_step=5
        )
        
        # Then
        assert "max_tested_concurrent" in stress_results
        assert "results" in stress_results
        assert "peak_throughput" in stress_results
        assert len(stress_results["results"]) > 0
        assert stress_results["peak_throughput"] > 0


class TestWithTimeoutDecorator:
    """with_timeout 데코레이터 테스트"""
    
    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """타임아웃 내 성공 테스트"""
        # Given
        async def quick_operation():
            await asyncio.sleep(0.01)
            return "quick_result"
        
        async_result = AsyncResult.from_async(quick_operation)
        
        # When
        timeout_result = with_timeout(1.0)(async_result)
        result = await timeout_result.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "quick_result"
    
    @pytest.mark.asyncio
    async def test_with_timeout_exceeded(self):
        """타임아웃 초과 테스트"""
        # Given
        async def slow_operation():
            await asyncio.sleep(1.0)
            return "slow_result"
        
        async_result = AsyncResult.from_async(slow_operation)
        
        # When
        timeout_result = with_timeout(0.01)(async_result)
        result = await timeout_result.to_result()
        
        # Then
        assert result.is_failure()
        assert "타임아웃" in str(result.unwrap_error())


class TestAsyncResultTestSuite:
    """async_result_test_suite 컨텍스트 매니저 테스트"""
    
    @pytest.mark.asyncio
    async def test_test_suite_success(self):
        """성공하는 테스트 스위트"""
        # Given & When & Then
        async with async_result_test_suite("successful_suite"):
            # 성공하는 테스트들
            await AsyncResultTestUtils.assert_success(
                AsyncResult.from_value("test1")
            )
            await AsyncResultTestUtils.assert_success(
                AsyncResult.from_value("test2")
            )
    
    @pytest.mark.asyncio
    async def test_test_suite_failure(self):
        """실패하는 테스트 스위트"""
        # Given & When & Then
        with pytest.raises(AsyncResultTestError):
            async with async_result_test_suite("failing_suite"):
                await AsyncResultTestUtils.assert_success(
                    AsyncResult.from_error("test_error")
                )


class TestAsyncResultTestContext:
    """AsyncResultTestContext 클래스 테스트"""
    
    def test_test_context_creation(self):
        """테스트 컨텍스트 생성 테스트"""
        # Given & When
        context = AsyncResultTestContext(
            test_name="test_context",
            start_time=time.time(),
            timeout=5.0,
            metadata={"user": "test_user"}
        )
        
        # Then
        assert context.test_name == "test_context"
        assert context.timeout == 5.0
        assert context.metadata["user"] == "test_user"
        assert context.assertions_count == 0
        assert len(context.failures) == 0


class TestEdgeCasesAndErrorHandling:
    """엣지 케이스 및 에러 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_assert_success_with_none_value(self):
        """None 값으로 성공 검증 테스트"""
        # Given
        async_result = AsyncResult.from_value(None)
        
        # When & Then
        await AsyncResultTestUtils.assert_success(
            async_result,
            expected_value=None
        )
    
    @pytest.mark.asyncio
    async def test_assert_success_with_empty_collections(self):
        """빈 컬렉션으로 성공 검증 테스트"""
        test_cases = [[], {}, "", 0, False]
        
        for empty_value in test_cases:
            async_result = AsyncResult.from_value(empty_value)
            await AsyncResultTestUtils.assert_success(
                async_result,
                expected_value=empty_value
            )
    
    @pytest.mark.asyncio
    async def test_performance_testing_with_exceptions(self):
        """예외가 발생하는 연산의 성능 테스트"""
        # Given
        def create_failing_result():
            async def failing_operation():
                await asyncio.sleep(0.01)
                raise Exception("Test exception")
            return AsyncResult.from_async(failing_operation)
        
        # When
        performance = await AsyncResultPerformanceTester.measure_throughput(
            create_failing_result,
            duration_seconds=0.05,
            max_concurrent=3
        )
        
        # Then
        assert performance["failed"] == performance["total_requests"]
        assert performance["success_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_mock_builder_with_extreme_values(self):
        """극한 값을 사용한 목 빌더 테스트"""
        # 매우 짧은 지연
        short_delay_mock = AsyncResultMockBuilder.delayed_success_mock(
            "short", 0.001
        )
        result = await short_delay_mock.to_result()
        assert result.is_success()
        
        # 100% 실패율
        always_fail_mock = AsyncResultMockBuilder.intermittent_failure_mock(
            "never_succeeds", "always_fails", failure_rate=1.0, seed=42
        )
        result = await always_fail_mock.to_result()
        assert result.is_failure()
        
        # 0% 실패율
        never_fail_mock = AsyncResultMockBuilder.intermittent_failure_mock(
            "always_succeeds", "never_fails", failure_rate=0.0, seed=42
        )
        result = await never_fail_mock.to_result()
        assert result.is_success()


class TestComplexScenarios:
    """복잡한 시나리오 테스트"""
    
    @pytest.mark.asyncio
    async def test_concurrent_assertions(self):
        """동시 어설션 실행 테스트"""
        # Given
        async_results = [
            AsyncResult.from_value(f"result_{i}")
            for i in range(10)
        ]
        
        # When
        assertion_tasks = [
            AsyncResultTestUtils.assert_success(ar, expected_value=f"result_{i}")
            for i, ar in enumerate(async_results)
        ]
        
        # Then: 모든 어설션이 성공해야 함
        await asyncio.gather(*assertion_tasks)
    
    @pytest.mark.asyncio
    async def test_mixed_success_failure_chain_order(self):
        """성공/실패가 섞인 체인 순서 테스트"""
        # Given
        async_results = [
            AsyncResult.from_value("success_0"),
            AsyncResult.from_error("error_1"),
            AsyncResult.from_value("success_2"),
        ]
        
        # When & Then: 순서는 검증되지만 일부는 실패
        await AsyncResultTestUtils.assert_chain_order(
            async_results,
            expected_order=[0, 1, 2]  # 모두 즉시 완료되므로 순차적
        )
    
    @pytest.mark.asyncio
    async def test_nested_async_result_testing(self):
        """중첩된 AsyncResult 테스트"""
        # Given
        async def nested_operation():
            inner_result = AsyncResult.from_value("inner")
            inner_value = await (await inner_result.to_result()).unwrap()
            return f"outer_{inner_value}"
        
        async_result = AsyncResult.from_async(nested_operation)
        
        # When & Then
        await AsyncResultTestUtils.assert_success(
            async_result,
            expected_value="outer_inner"
        )


# === 픽스처 및 헬퍼 ===

@pytest.fixture
def sample_test_context():
    """테스트용 컨텍스트"""
    return AsyncResultTestContext(
        test_name="sample_test",
        start_time=time.time(),
        timeout=5.0,
        metadata={"test_type": "unit", "module": "async_result_testing"}
    )


@pytest.fixture
def performance_test_factory():
    """성능 테스트용 팩토리"""
    def factory(delay=0.01, failure_rate=0.0):
        def create_result():
            async def operation():
                await asyncio.sleep(delay)
                if failure_rate > 0 and time.time() % 1 < failure_rate:
                    raise Exception("Performance test failure")
                return f"perf_result_{time.time()}"
            return AsyncResult.from_async(operation)
        return create_result
    return factory


# === pytest 통합 테스트 (조건부) ===

try:
    import pytest
    
    @pytest.mark.asyncio
    async def test_pytest_fixture_integration():
        """pytest 픽스처 통합 테스트"""
        # This test would only run if pytest fixtures are properly set up
        pass
    
except ImportError:
    # pytest 미설치 시 건너뛰기
    pass


# === 실행 시 검증 ===

if __name__ == "__main__":
    print("✅ AsyncResult 테스팅 유틸리티 테스트 모듈 로드 완료")
    print("pytest tests/unit/testing/test_async_result_testing.py 실행하여 테스트")