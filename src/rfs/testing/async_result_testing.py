"""
RFS Framework AsyncResult 전용 테스트 유틸리티

AsyncResult 모나드를 위한 포괄적인 테스트 도구들을 제공합니다.
성공/실패 검증, 성능 테스트, 목킹, 시나리오 테스트 등을 지원합니다.
"""

import asyncio
import time
import random
import inspect
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional, TypeVar, Union
from unittest.mock import Mock, AsyncMock

from ..async_pipeline import AsyncResult
from ..core.result import Result, Success, Failure
from ..hof.core import pipe, curry
from ..hof.collections import compact_map, partition, first

T = TypeVar('T')
E = TypeVar('E')

# pytest 지원 (선택적)
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    pytest = None
    PYTEST_AVAILABLE = False


class AsyncResultTestError(Exception):
    """AsyncResult 테스트 에러"""
    pass


@dataclass
class AsyncResultTestContext:
    """AsyncResult 테스트 컨텍스트"""
    test_name: str
    start_time: float
    timeout: Optional[float] = None
    metadata: dict = field(default_factory=dict)
    assertions_count: int = 0
    failures: List[str] = field(default_factory=list)


class AsyncResultTestUtils:
    """AsyncResult 테스트 헬퍼 클래스"""
    
    @staticmethod
    async def assert_success(
        async_result: AsyncResult[T, E],
        expected_value: Optional[T] = None,
        value_matcher: Optional[Callable[[T], bool]] = None,
        timeout: Optional[float] = None,
        message: Optional[str] = None
    ):
        """
        AsyncResult가 성공하는지 검증
        
        Args:
            async_result: 검증할 AsyncResult
            expected_value: 예상되는 성공 값 (정확한 비교)
            value_matcher: 성공 값 검증 함수 (복잡한 비교)
            timeout: 타임아웃 (초)
            message: 커스텀 에러 메시지
            
        Raises:
            AsyncResultTestError: 검증 실패 시
            asyncio.TimeoutError: 타임아웃 시
            
        Example:
            >>> await AsyncResultTestUtils.assert_success(
            ...     AsyncResult.from_value("test"),
            ...     expected_value="test"
            ... )
            >>> await AsyncResultTestUtils.assert_success(
            ...     AsyncResult.from_value({"user_id": 123}),
            ...     value_matcher=lambda v: v["user_id"] == 123
            ... )
        """
        try:
            # 타임아웃 적용
            if timeout:
                result = await asyncio.wait_for(async_result.to_result(), timeout)
            else:
                result = await async_result.to_result()
            
            # 성공 여부 검증
            if not result.is_success():
                error_msg = message or f"AsyncResult가 실패했습니다: {result.unwrap_error()}"
                raise AsyncResultTestError(error_msg)
            
            actual_value = result.unwrap()
            
            # 예상 값 검증
            if expected_value is not None:
                if actual_value != expected_value:
                    error_msg = message or f"예상 값: {expected_value}, 실제 값: {actual_value}"
                    raise AsyncResultTestError(error_msg)
            
            # 값 매처 검증
            if value_matcher is not None:
                if not value_matcher(actual_value):
                    error_msg = message or f"값 매처가 실패했습니다: {actual_value}"
                    raise AsyncResultTestError(error_msg)
                    
        except asyncio.TimeoutError:
            error_msg = message or f"AsyncResult가 {timeout}초 내에 완료되지 않았습니다"
            raise asyncio.TimeoutError(error_msg)
        except AsyncResultTestError:
            raise
        except Exception as e:
            error_msg = message or f"예상치 못한 에러 발생: {str(e)}"
            raise AsyncResultTestError(error_msg)
    
    @staticmethod
    async def assert_failure(
        async_result: AsyncResult[T, E],
        expected_error: Optional[E] = None,
        expected_error_type: Optional[type] = None,
        error_matcher: Optional[Callable[[E], bool]] = None,
        timeout: Optional[float] = None,
        message: Optional[str] = None
    ):
        """
        AsyncResult가 실패하는지 검증
        
        Args:
            async_result: 검증할 AsyncResult
            expected_error: 예상되는 에러 값
            expected_error_type: 예상되는 에러 타입
            error_matcher: 에러 검증 함수
            timeout: 타임아웃 (초)
            message: 커스텀 에러 메시지
            
        Example:
            >>> await AsyncResultTestUtils.assert_failure(
            ...     AsyncResult.from_error("Not found"),
            ...     expected_error="Not found"
            ... )
            >>> await AsyncResultTestUtils.assert_failure(
            ...     AsyncResult.from_error(ValueError("Invalid")),
            ...     expected_error_type=ValueError
            ... )
        """
        try:
            # 타임아웃 적용
            if timeout:
                result = await asyncio.wait_for(async_result.to_result(), timeout)
            else:
                result = await async_result.to_result()
            
            # 실패 여부 검증
            if result.is_success():
                error_msg = message or f"AsyncResult가 성공했습니다: {result.unwrap()}"
                raise AsyncResultTestError(error_msg)
            
            actual_error = result.unwrap_error()
            
            # 예상 에러 검증
            if expected_error is not None:
                if actual_error != expected_error:
                    error_msg = message or f"예상 에러: {expected_error}, 실제 에러: {actual_error}"
                    raise AsyncResultTestError(error_msg)
            
            # 에러 타입 검증
            if expected_error_type is not None:
                if not isinstance(actual_error, expected_error_type):
                    error_msg = message or f"예상 에러 타입: {expected_error_type.__name__}, 실제 타입: {type(actual_error).__name__}"
                    raise AsyncResultTestError(error_msg)
            
            # 에러 매처 검증
            if error_matcher is not None:
                if not error_matcher(actual_error):
                    error_msg = message or f"에러 매처가 실패했습니다: {actual_error}"
                    raise AsyncResultTestError(error_msg)
                    
        except asyncio.TimeoutError:
            error_msg = message or f"AsyncResult가 {timeout}초 내에 완료되지 않았습니다"
            raise asyncio.TimeoutError(error_msg)
        except AsyncResultTestError:
            raise
        except Exception as e:
            error_msg = message or f"예상치 못한 에러 발생: {str(e)}"
            raise AsyncResultTestError(error_msg)
    
    @staticmethod
    async def assert_execution_time(
        async_result: AsyncResult[T, E],
        max_seconds: float,
        min_seconds: float = 0,
        message: Optional[str] = None
    ) -> float:
        """
        AsyncResult 실행 시간 검증
        
        Args:
            async_result: 검증할 AsyncResult
            max_seconds: 최대 실행 시간 (초)
            min_seconds: 최소 실행 시간 (초)
            message: 커스텀 에러 메시지
            
        Returns:
            float: 실제 실행 시간
            
        Example:
            >>> execution_time = await AsyncResultTestUtils.assert_execution_time(
            ...     AsyncResult.from_async(slow_operation),
            ...     max_seconds=2.0,
            ...     min_seconds=0.5
            ... )
        """
        start_time = time.time()
        
        try:
            await async_result.to_result()
            execution_time = time.time() - start_time
            
            # 최대 시간 검증
            if execution_time > max_seconds:
                error_msg = message or f"실행 시간이 너무 깁니다: {execution_time:.3f}초 > {max_seconds}초"
                raise AsyncResultTestError(error_msg)
            
            # 최소 시간 검증
            if execution_time < min_seconds:
                error_msg = message or f"실행 시간이 너무 짧습니다: {execution_time:.3f}초 < {min_seconds}초"
                raise AsyncResultTestError(error_msg)
            
            return execution_time
            
        except AsyncResultTestError:
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = message or f"실행 중 에러 발생 ({execution_time:.3f}초): {str(e)}"
            raise AsyncResultTestError(error_msg)
    
    @staticmethod
    async def assert_eventually_succeeds(
        async_result_factory: Callable[[], AsyncResult[T, E]],
        max_attempts: int = 5,
        delay_between_attempts: float = 1.0,
        timeout_per_attempt: Optional[float] = None,
        message: Optional[str] = None
    ) -> T:
        """
        AsyncResult가 최종적으로 성공하는지 검증 (재시도 포함)
        
        Args:
            async_result_factory: AsyncResult를 생성하는 팩토리 함수
            max_attempts: 최대 시도 횟수
            delay_between_attempts: 시도 간 지연 시간 (초)
            timeout_per_attempt: 시도당 타임아웃 (초)
            message: 커스텀 에러 메시지
            
        Returns:
            T: 최종 성공 값
            
        Example:
            >>> result = await AsyncResultTestUtils.assert_eventually_succeeds(
            ...     lambda: AsyncResult.from_async(unreliable_operation),
            ...     max_attempts=3,
            ...     delay_between_attempts=0.5
            ... )
        """
        errors = []
        
        for attempt in range(max_attempts):
            try:
                async_result = async_result_factory()
                
                if timeout_per_attempt:
                    result = await asyncio.wait_for(async_result.to_result(), timeout_per_attempt)
                else:
                    result = await async_result.to_result()
                
                if result.is_success():
                    return result.unwrap()
                else:
                    errors.append(f"시도 {attempt + 1}: {result.unwrap_error()}")
                    
            except Exception as e:
                errors.append(f"시도 {attempt + 1}: {str(e)}")
            
            # 마지막 시도가 아니면 지연
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay_between_attempts)
        
        # 모든 시도 실패
        error_msg = message or f"{max_attempts}번 시도 모두 실패:\n" + "\n".join(errors)
        raise AsyncResultTestError(error_msg)
    
    @staticmethod
    async def assert_chain_order(
        async_results: List[AsyncResult[T, E]],
        expected_order: Optional[List[Any]] = None,
        timeout: Optional[float] = None,
        message: Optional[str] = None
    ):
        """
        AsyncResult 체인의 실행 순서 검증
        
        Args:
            async_results: 검증할 AsyncResult 리스트
            expected_order: 예상되는 완료 순서 (인덱스 리스트)
            timeout: 전체 타임아웃 (초)
            message: 커스텀 에러 메시지
            
        Example:
            >>> await AsyncResultTestUtils.assert_chain_order([
            ...     AsyncResult.from_async(fast_operation),  # 0번이 먼저 완료되어야 함
            ...     AsyncResult.from_async(slow_operation),  # 1번이 나중에 완료되어야 함
            ... ], expected_order=[0, 1])
        """
        completion_order = []
        tasks = []
        
        # 각 AsyncResult를 태스크로 변환 (완료 순서 추적)
        for i, async_result in enumerate(async_results):
            async def track_completion(index: int, ar: AsyncResult):
                result = await ar.to_result()
                completion_order.append(index)
                return result
            
            task = asyncio.create_task(track_completion(i, async_result))
            tasks.append(task)
        
        try:
            # 모든 태스크 완료 대기
            if timeout:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout)
            else:
                await asyncio.gather(*tasks)
            
            # 순서 검증
            if expected_order is not None:
                if completion_order != expected_order:
                    error_msg = message or f"예상 완료 순서: {expected_order}, 실제 순서: {completion_order}"
                    raise AsyncResultTestError(error_msg)
                    
        except asyncio.TimeoutError:
            error_msg = message or f"체인 완료가 {timeout}초 내에 이루어지지 않았습니다"
            raise asyncio.TimeoutError(error_msg)
        except AsyncResultTestError:
            raise
        except Exception as e:
            error_msg = message or f"체인 실행 중 에러 발생: {str(e)}"
            raise AsyncResultTestError(error_msg)


class AsyncResultMockBuilder:
    """AsyncResult 목 객체 생성기"""
    
    @staticmethod
    def success_mock(value: T) -> AsyncResult[T, E]:
        """
        성공하는 AsyncResult 목 생성
        
        Args:
            value: 성공 값
            
        Returns:
            AsyncResult[T, E]: 성공하는 목 객체
        """
        return AsyncResult.from_value(value)
    
    @staticmethod
    def failure_mock(error: E) -> AsyncResult[T, E]:
        """
        실패하는 AsyncResult 목 생성
        
        Args:
            error: 에러 값
            
        Returns:
            AsyncResult[T, E]: 실패하는 목 객체
        """
        return AsyncResult.from_error(error)
    
    @staticmethod
    def delayed_success_mock(
        value: T,
        delay_seconds: float,
        jitter: float = 0.0
    ) -> AsyncResult[T, E]:
        """
        지연된 성공 AsyncResult 목 생성
        
        Args:
            value: 성공 값
            delay_seconds: 지연 시간 (초)
            jitter: 지연 시간 랜덤 변동 (초)
            
        Returns:
            AsyncResult[T, E]: 지연된 성공 목 객체
            
        Example:
            >>> mock = AsyncResultMockBuilder.delayed_success_mock(
            ...     "data", delay_seconds=1.0, jitter=0.2
            ... )
            >>> # 0.8~1.2초 후에 "data"로 성공
        """
        async def delayed_operation():
            actual_delay = delay_seconds
            if jitter > 0:
                actual_delay += random.uniform(-jitter, jitter)
            
            if actual_delay > 0:
                await asyncio.sleep(actual_delay)
            return value
        
        return AsyncResult.from_async(delayed_operation)
    
    @staticmethod
    def delayed_failure_mock(
        error: E,
        delay_seconds: float,
        jitter: float = 0.0
    ) -> AsyncResult[T, E]:
        """
        지연된 실패 AsyncResult 목 생성
        
        Args:
            error: 에러 값
            delay_seconds: 지연 시간 (초)
            jitter: 지연 시간 랜덤 변동 (초)
            
        Returns:
            AsyncResult[T, E]: 지연된 실패 목 객체
        """
        async def delayed_operation():
            actual_delay = delay_seconds
            if jitter > 0:
                actual_delay += random.uniform(-jitter, jitter)
            
            if actual_delay > 0:
                await asyncio.sleep(actual_delay)
            raise Exception(error)
        
        return AsyncResult.from_async(delayed_operation)
    
    @staticmethod
    def intermittent_failure_mock(
        success_value: T,
        failure_error: E,
        failure_rate: float = 0.5,
        seed: Optional[int] = None
    ) -> AsyncResult[T, E]:
        """
        간헐적으로 실패하는 AsyncResult 목 생성
        
        Args:
            success_value: 성공 시 반환 값
            failure_error: 실패 시 에러 값
            failure_rate: 실패 확률 (0.0 ~ 1.0)
            seed: 랜덤 시드 (재현 가능한 테스트용)
            
        Returns:
            AsyncResult[T, E]: 간헐적 실패 목 객체
            
        Example:
            >>> mock = AsyncResultMockBuilder.intermittent_failure_mock(
            ...     "success", "failure", failure_rate=0.3
            ... )
            >>> # 70% 확률로 성공, 30% 확률로 실패
        """
        if seed is not None:
            random.seed(seed)
        
        async def intermittent_operation():
            if random.random() < failure_rate:
                raise Exception(failure_error)
            return success_value
        
        return AsyncResult.from_async(intermittent_operation)
    
    @staticmethod
    def timeout_mock(timeout_seconds: float) -> AsyncResult[T, E]:
        """
        타임아웃되는 AsyncResult 목 생성
        
        Args:
            timeout_seconds: 타임아웃 시간 (초)
            
        Returns:
            AsyncResult[T, E]: 타임아웃되는 목 객체
        """
        async def timeout_operation():
            await asyncio.sleep(timeout_seconds)
            # 실제로는 완료되지 않음 (테스트에서 타임아웃 처리)
            return "timeout_completed"  # pragma: no cover
        
        return AsyncResult.from_async(timeout_operation)
    
    @staticmethod
    def chain_mock(
        operations: List[Callable[[Any], Any]],
        initial_value: Any = None,
        failure_at_step: Optional[int] = None,
        failure_error: Any = "Chain failure"
    ) -> AsyncResult[Any, Any]:
        """
        체인 연산 목 생성
        
        Args:
            operations: 연산 함수 리스트
            initial_value: 초기 값
            failure_at_step: 실패할 단계 (0부터 시작, None이면 실패 없음)
            failure_error: 실패 시 에러 값
            
        Returns:
            AsyncResult: 체인 연산 목 객체
            
        Example:
            >>> operations = [
            ...     lambda x: x * 2,
            ...     lambda x: x + 10,
            ...     lambda x: str(x)
            ... ]
            >>> mock = AsyncResultMockBuilder.chain_mock(
            ...     operations, initial_value=5
            ... )
            >>> # 5 -> 10 -> 20 -> "20"
        """
        async def chain_operation():
            value = initial_value
            
            for i, operation in enumerate(operations):
                if failure_at_step is not None and i == failure_at_step:
                    raise Exception(failure_error)
                
                # 비동기 함수인지 확인
                if inspect.iscoroutinefunction(operation):
                    value = await operation(value)
                else:
                    value = operation(value)
            
            return value
        
        return AsyncResult.from_async(chain_operation)
    
    @staticmethod
    def resource_exhaustion_mock(
        resource_limit: int,
        current_usage: int = 0
    ) -> AsyncResult[str, str]:
        """
        리소스 고갈 시나리오 목 생성
        
        Args:
            resource_limit: 리소스 한계
            current_usage: 현재 사용량
            
        Returns:
            AsyncResult: 리소스 상태에 따른 결과
        """
        async def resource_operation():
            if current_usage >= resource_limit:
                raise Exception("리소스가 고갈되었습니다")
            return f"리소스 사용: {current_usage}/{resource_limit}"
        
        return AsyncResult.from_async(resource_operation)


# === 시나리오 테스트 도구 ===

class AsyncResultScenarioTester:
    """AsyncResult 시나리오 테스트 도구"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.scenarios = []
        self.setup_functions = []
        self.teardown_functions = []
    
    def add_scenario(
        self,
        name: str,
        async_result_factory: Callable[[], AsyncResult],
        assertions: List[Callable],
        setup: Optional[Callable] = None,
        teardown: Optional[Callable] = None
    ):
        """시나리오 추가"""
        self.scenarios.append({
            "name": name,
            "factory": async_result_factory,
            "assertions": assertions,
            "setup": setup,
            "teardown": teardown
        })
    
    async def run_scenarios(self, parallel: bool = False):
        """모든 시나리오 실행"""
        if parallel:
            await self._run_parallel_scenarios()
        else:
            await self._run_sequential_scenarios()
    
    async def _run_sequential_scenarios(self):
        """순차적 시나리오 실행"""
        results = []
        
        for scenario in self.scenarios:
            result = await self._run_single_scenario(scenario)
            results.append(result)
        
        return results
    
    async def _run_parallel_scenarios(self):
        """병렬 시나리오 실행"""
        tasks = [
            self._run_single_scenario(scenario)
            for scenario in self.scenarios
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_single_scenario(self, scenario):
        """개별 시나리오 실행"""
        scenario_name = scenario["name"]
        
        try:
            # Setup
            if scenario["setup"]:
                await scenario["setup"]()
            
            # AsyncResult 생성 및 실행
            async_result = scenario["factory"]()
            
            # 모든 어설션 실행
            for assertion in scenario["assertions"]:
                await assertion(async_result)
            
            return {"scenario": scenario_name, "status": "passed"}
            
        except Exception as e:
            return {"scenario": scenario_name, "status": "failed", "error": str(e)}
        
        finally:
            # Teardown
            if scenario["teardown"]:
                try:
                    await scenario["teardown"]()
                except Exception as teardown_error:
                    print(f"Teardown 에러 in {scenario_name}: {teardown_error}")


# === 성능 및 부하 테스트 ===

class AsyncResultPerformanceTester:
    """AsyncResult 성능 테스트 도구"""
    
    @staticmethod
    async def measure_throughput(
        async_result_factory: Callable[[], AsyncResult],
        duration_seconds: float = 10.0,
        max_concurrent: int = 100
    ) -> dict:
        """
        처리량 측정
        
        Args:
            async_result_factory: AsyncResult 팩토리 함수
            duration_seconds: 측정 시간 (초)
            max_concurrent: 최대 동시 실행 수
            
        Returns:
            dict: 성능 측정 결과
        """
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        completed = 0
        failed = 0
        total_response_time = 0
        response_times = []
        
        # 세마포어로 동시성 제어
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def single_execution():
            nonlocal completed, failed, total_response_time
            
            async with semaphore:
                execution_start = time.time()
                
                try:
                    async_result = async_result_factory()
                    result = await async_result.to_result()
                    
                    execution_time = time.time() - execution_start
                    response_times.append(execution_time)
                    total_response_time += execution_time
                    
                    if result.is_success():
                        completed += 1
                    else:
                        failed += 1
                        
                except Exception:
                    failed += 1
                    execution_time = time.time() - execution_start
                    response_times.append(execution_time)
        
        # 지정된 시간 동안 실행
        tasks = []
        while time.time() < end_time:
            if len(tasks) < max_concurrent:
                task = asyncio.create_task(single_execution())
                tasks.append(task)
            
            # 완료된 태스크 정리
            done_tasks = [t for t in tasks if t.done()]
            for task in done_tasks:
                tasks.remove(task)
            
            await asyncio.sleep(0.01)  # CPU 점유율 조절
        
        # 남은 태스크 완료 대기
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 계산
        actual_duration = time.time() - start_time
        total_requests = completed + failed
        
        if response_times:
            response_times.sort()
            avg_response_time = total_response_time / len(response_times)
            p50 = response_times[len(response_times) // 2]
            p90 = response_times[int(len(response_times) * 0.9)]
            p99 = response_times[int(len(response_times) * 0.99)]
        else:
            avg_response_time = p50 = p90 = p99 = 0
        
        return {
            "duration": actual_duration,
            "total_requests": total_requests,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total_requests if total_requests > 0 else 0,
            "throughput": total_requests / actual_duration,
            "avg_response_time": avg_response_time,
            "p50_response_time": p50,
            "p90_response_time": p90,
            "p99_response_time": p99,
            "max_concurrent": max_concurrent
        }
    
    @staticmethod
    async def stress_test(
        async_result_factory: Callable[[], AsyncResult],
        ramp_up_seconds: float = 30.0,
        max_concurrent: int = 1000,
        ramp_up_step: int = 10
    ) -> dict:
        """
        스트레스 테스트 실행
        
        Args:
            async_result_factory: AsyncResult 팩토리 함수
            ramp_up_seconds: 부하 증가 시간
            max_concurrent: 최대 동시 실행 수
            ramp_up_step: 부하 증가 단위
            
        Returns:
            dict: 스트레스 테스트 결과
        """
        results = []
        
        current_concurrent = ramp_up_step
        step_duration = ramp_up_seconds / (max_concurrent // ramp_up_step)
        
        while current_concurrent <= max_concurrent:
            print(f"동시 실행 수: {current_concurrent}")
            
            # 각 단계별 성능 측정
            result = await AsyncResultPerformanceTester.measure_throughput(
                async_result_factory,
                duration_seconds=step_duration,
                max_concurrent=current_concurrent
            )
            
            result["concurrent_users"] = current_concurrent
            results.append(result)
            
            # 성능 임계치 체크 (응답 시간이 너무 길어지면 중단)
            if result["avg_response_time"] > 10.0:  # 10초 임계치
                print(f"응답 시간 임계치 초과로 스트레스 테스트 중단: {result['avg_response_time']:.3f}초")
                break
            
            current_concurrent += ramp_up_step
        
        return {
            "max_tested_concurrent": current_concurrent - ramp_up_step,
            "results": results,
            "peak_throughput": max(r["throughput"] for r in results),
            "performance_degradation_point": next(
                (r["concurrent_users"] for r in results if r["avg_response_time"] > 1.0),
                None
            )
        }


# === pytest 통합 (선택적) ===

if PYTEST_AVAILABLE:
    
    @pytest.fixture
    def async_result_utils():
        """AsyncResult 테스트 유틸리티 픽스처"""
        return AsyncResultTestUtils()
    
    @pytest.fixture
    def async_result_mocks():
        """AsyncResult 목 생성기 픽스처"""
        return AsyncResultMockBuilder()
    
    @pytest.fixture
    async def async_result_test_context():
        """AsyncResult 테스트 컨텍스트 픽스처"""
        context = AsyncResultTestContext(
            test_name="pytest_test",
            start_time=time.time()
        )
        
        yield context
        
        # 테스트 종료 시 정리
        if context.failures:
            pytest.fail(f"AsyncResult 테스트 실패: {'; '.join(context.failures)}")
    
    # pytest 마커 정의
    def pytest_configure(config):
        """pytest 설정"""
        config.addinivalue_line(
            "markers", "async_result: AsyncResult 관련 테스트"
        )
        config.addinivalue_line(
            "markers", "async_result_slow: 느린 AsyncResult 테스트"
        )
        config.addinivalue_line(
            "markers", "async_result_integration: AsyncResult 통합 테스트"
        )


# === 편의 함수 ===

@curry
def with_timeout(timeout_seconds: float, async_result: AsyncResult[T, E]) -> AsyncResult[T, Union[E, str]]:
    """
    AsyncResult에 타임아웃 적용
    
    Args:
        timeout_seconds: 타임아웃 시간 (초)
        async_result: 원본 AsyncResult
        
    Returns:
        AsyncResult: 타임아웃이 적용된 AsyncResult
    """
    async def timeout_wrapper():
        try:
            result = await asyncio.wait_for(async_result.to_result(), timeout_seconds)
            return result
        except asyncio.TimeoutError:
            return Failure(f"타임아웃: {timeout_seconds}초")
    
    return AsyncResult(timeout_wrapper())


@asynccontextmanager
async def async_result_test_suite(suite_name: str):
    """
    AsyncResult 테스트 스위트 컨텍스트 매니저
    
    Args:
        suite_name: 테스트 스위트 이름
    """
    start_time = time.time()
    print(f"🧪 AsyncResult 테스트 스위트 시작: {suite_name}")
    
    try:
        yield
        duration = time.time() - start_time
        print(f"✅ 테스트 스위트 완료: {suite_name} ({duration:.3f}초)")
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ 테스트 스위트 실패: {suite_name} ({duration:.3f}초) - {str(e)}")
        raise


# === 사용 예시 ===

def get_usage_examples():
    """사용 예시 반환"""
    return {
        "basic_assertions": '''
import asyncio
from rfs.testing.async_result_testing import AsyncResultTestUtils
from rfs.async_pipeline import AsyncResult

async def test_basic_assertions():
    # 성공 테스트
    success_result = AsyncResult.from_value("test_data")
    await AsyncResultTestUtils.assert_success(
        success_result,
        expected_value="test_data"
    )
    
    # 실패 테스트
    failure_result = AsyncResult.from_error("test_error")
    await AsyncResultTestUtils.assert_failure(
        failure_result,
        expected_error="test_error"
    )
        ''',
        
        "performance_testing": '''
from rfs.testing.async_result_testing import AsyncResultPerformanceTester

async def test_performance():
    # 성능 측정
    def create_test_result():
        return AsyncResult.from_async(lambda: asyncio.sleep(0.1))
    
    performance = await AsyncResultPerformanceTester.measure_throughput(
        create_test_result,
        duration_seconds=5.0,
        max_concurrent=50
    )
    
    print(f"처리량: {performance['throughput']:.1f} req/sec")
    print(f"평균 응답시간: {performance['avg_response_time']:.3f}초")
        ''',
        
        "mock_testing": '''
from rfs.testing.async_result_testing import AsyncResultMockBuilder

async def test_with_mocks():
    # 간헐적 실패 목 테스트
    unreliable_mock = AsyncResultMockBuilder.intermittent_failure_mock(
        success_value="success",
        failure_error="network_error",
        failure_rate=0.3  # 30% 실패율
    )
    
    # 여러 번 실행하여 간헐적 실패 확인
    results = []
    for _ in range(10):
        result = await unreliable_mock.to_result()
        results.append(result.is_success())
    
    success_count = sum(results)
    print(f"성공률: {success_count}/10 ({success_count*10}%)")
        ''',
        
        "scenario_testing": '''
from rfs.testing.async_result_testing import AsyncResultScenarioTester, AsyncResultTestUtils

async def test_scenarios():
    tester = AsyncResultScenarioTester("user_workflow")
    
    # 시나리오 1: 정상 플로우
    tester.add_scenario(
        "normal_flow",
        lambda: AsyncResult.from_async(lambda: simulate_user_creation()),
        [
            lambda ar: AsyncResultTestUtils.assert_success(ar),
            lambda ar: AsyncResultTestUtils.assert_execution_time(ar, max_seconds=2.0)
        ]
    )
    
    # 시나리오 2: 에러 처리
    tester.add_scenario(
        "error_handling",
        lambda: AsyncResult.from_async(lambda: simulate_validation_error()),
        [
            lambda ar: AsyncResultTestUtils.assert_failure(
                ar, expected_error_type=ValueError
            )
        ]
    )
    
    results = await tester.run_scenarios(parallel=True)
    print("시나리오 테스트 결과:", results)
        ''',
        
        "pytest_integration": '''
import pytest
from rfs.testing.async_result_testing import AsyncResultTestUtils
from rfs.async_pipeline import AsyncResult

@pytest.mark.async_result
async def test_with_pytest(async_result_utils, async_result_mocks):
    # pytest 픽스처 사용
    success_mock = async_result_mocks.success_mock("test_value")
    
    await async_result_utils.assert_success(
        success_mock,
        value_matcher=lambda v: v == "test_value"
    )

@pytest.mark.async_result_slow
async def test_timeout_handling():
    timeout_mock = AsyncResultMockBuilder.timeout_mock(5.0)
    
    with pytest.raises(asyncio.TimeoutError):
        await AsyncResultTestUtils.assert_success(
            timeout_mock,
            timeout=1.0  # 1초 타임아웃으로 5초 작업 테스트
        )
        '''
    }


# === 모듈 정보 ===

__version__ = "1.0.0"
__author__ = "RFS Framework Team"

def get_module_info():
    """모듈 정보 반환"""
    return {
        "name": "RFS AsyncResult Testing Utilities",
        "version": __version__,
        "features": [
            "성공/실패 검증 도구",
            "실행 시간 및 성능 테스트",
            "다양한 목 객체 생성기",
            "시나리오 테스트 프레임워크",
            "부하 테스트 및 스트레스 테스트",
            "pytest 통합 지원",
            "HOF 패턴 통합"
        ],
        "dependencies": {
            "rfs_framework": ">= 4.3.0",
            "python": ">= 3.8",
            "pytest": ">= 7.0.0 (선택적)"
        }
    }