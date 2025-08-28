"""
AsyncPipeline 에러 처리 시스템 단위 테스트

AsyncRetryWrapper, AsyncFallbackWrapper, AsyncCircuitBreaker 등의 에러 처리 컴포넌트를 검증합니다.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from rfs.async_pipeline import (
    AsyncErrorContext, AsyncRetryWrapper, AsyncFallbackWrapper,
    AsyncCircuitBreaker, AsyncErrorStrategy, AsyncErrorMonitor,
    ErrorSeverity, with_retry, with_fallback, with_circuit_breaker
)
from rfs.async_pipeline.async_result import AsyncResult


class TestAsyncErrorContext:
    """AsyncErrorContext 테스트"""
    
    def test_error_context_creation(self):
        """에러 컨텍스트 생성 테스트"""
        error = ValueError("테스트 에러")
        context = AsyncErrorContext("fetch_data", 2, error)
        
        assert context.operation_name == "fetch_data"
        assert context.step == 2
        assert context.error == error
        assert context.timestamp > 0
    
    def test_error_context_string_representation(self):
        """에러 컨텍스트 문자열 표현 테스트"""
        error = RuntimeError("연결 실패")
        context = AsyncErrorContext("api_call", 1, error)
        
        str_repr = str(context)
        assert "api_call" in str_repr
        assert "step 1" in str_repr
        assert "연결 실패" in str_repr


class TestAsyncRetryWrapper:
    """AsyncRetryWrapper 재시도 메커니즘 테스트"""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """첫 번째 시도에서 성공하는 경우 테스트"""
        call_count = 0
        
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "성공"
        
        retry_wrapper = AsyncRetryWrapper(max_attempts=3)
        result = await retry_wrapper(success_func)
        
        value = await result.unwrap_async()
        assert value == "성공"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """몇 번 실패 후 성공하는 경우 테스트"""
        call_count = 0
        
        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"시도 {call_count} 실패")
            return f"3번째 시도에서 성공"
        
        retry_wrapper = AsyncRetryWrapper(
            max_attempts=5,
            base_delay=0.01,
            backoff_factor=2.0
        )
        
        start_time = time.time()
        result = await retry_wrapper(eventually_succeed)
        end_time = time.time()
        
        value = await result.unwrap_async()
        assert value == "3번째 시도에서 성공"
        assert call_count == 3
        
        # 지수 백오프 확인: 0.01 + 0.02 = 0.03초 정도 소요되어야 함
        assert 0.02 < (end_time - start_time) < 0.1
    
    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self):
        """모든 시도가 실패하는 경우 테스트"""
        call_count = 0
        
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"시도 {call_count} 실패")
        
        retry_wrapper = AsyncRetryWrapper(max_attempts=3, base_delay=0.01)
        result = await retry_wrapper(always_fail)
        
        assert call_count == 3
        with pytest.raises(ValueError, match="시도 3 실패"):
            await result.unwrap_async()
    
    @pytest.mark.asyncio
    async def test_retry_with_specific_exceptions(self):
        """특정 예외만 재시도하는 경우 테스트"""
        call_count = 0
        
        async def mixed_failures():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("재시도 가능한 에러")
            elif call_count == 2:
                raise ValueError("재시도 불가능한 에러")
        
        retry_wrapper = AsyncRetryWrapper(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,)
        )
        
        result = await retry_wrapper(mixed_failures)
        
        assert call_count == 2
        with pytest.raises(ValueError, match="재시도 불가능한 에러"):
            await result.unwrap_async()
    
    @pytest.mark.asyncio
    async def test_with_retry_decorator_factory(self):
        """with_retry 데코레이터 팩토리 테스트"""
        call_count = 0
        
        retry_wrapper = with_retry(max_attempts=2, base_delay=0.01)
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("첫 번째 실패")
            return "두 번째 성공"
        
        result = await retry_wrapper(test_func)
        value = await result.unwrap_async()
        
        assert value == "두 번째 성공"
        assert call_count == 2


class TestAsyncFallbackWrapper:
    """AsyncFallbackWrapper 폴백 메커니즘 테스트"""
    
    @pytest.mark.asyncio
    async def test_fallback_primary_success(self):
        """주 함수가 성공하는 경우 테스트"""
        async def primary():
            return "주 함수 성공"
        
        async def fallback():
            return "폴백 함수"
        
        wrapper = AsyncFallbackWrapper(fallback)
        result = await wrapper(primary)
        
        value = await result.unwrap_async()
        assert value == "주 함수 성공"
    
    @pytest.mark.asyncio
    async def test_fallback_primary_fails_fallback_succeeds(self):
        """주 함수 실패, 폴백 함수 성공 테스트"""
        async def primary():
            raise ConnectionError("주 함수 실패")
        
        async def fallback():
            await asyncio.sleep(0.01)
            return "폴백 성공"
        
        wrapper = AsyncFallbackWrapper(fallback)
        result = await wrapper(primary)
        
        value = await result.unwrap_async()
        assert value == "폴백 성공"
    
    @pytest.mark.asyncio
    async def test_fallback_both_fail(self):
        """주 함수와 폴백 함수 모두 실패하는 경우 테스트"""
        async def primary():
            raise ValueError("주 함수 에러")
        
        async def fallback():
            raise RuntimeError("폴백 함수 에러")
        
        wrapper = AsyncFallbackWrapper(fallback)
        result = await wrapper(primary)
        
        with pytest.raises(Exception) as exc_info:
            await result.unwrap_async()
        
        # 복합 에러 메시지 확인
        error_msg = str(exc_info.value)
        assert "주 함수 에러" in error_msg
        assert "폴백 함수 에러" in error_msg
    
    @pytest.mark.asyncio
    async def test_with_fallback_decorator_factory(self):
        """with_fallback 데코레이터 팩토리 테스트"""
        async def fallback_func():
            return "폴백 결과"
        
        wrapper = with_fallback(fallback_func)
        
        async def failing_primary():
            raise Exception("주 함수 실패")
        
        result = await wrapper(failing_primary)
        value = await result.unwrap_async()
        
        assert value == "폴백 결과"


class TestAsyncCircuitBreaker:
    """AsyncCircuitBreaker 서킷브레이커 테스트"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """서킷브레이커 닫힌 상태(정상) 테스트"""
        circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=3,
            timeout=1.0
        )
        
        call_count = 0
        
        async def success_func():
            nonlocal call_count
            call_count += 1
            return f"성공 {call_count}"
        
        # 여러 번 성공적으로 호출
        for i in range(5):
            result = await circuit_breaker(success_func)
            value = await result.unwrap_async()
            assert value == f"성공 {i + 1}"
        
        assert circuit_breaker.state == "CLOSED"
        assert call_count == 5
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """연속 실패 후 서킷브레이커가 열리는 테스트"""
        circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=3,
            timeout=0.1
        )
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"실패 {call_count}")
        
        # 실패 임계치까지 호출
        for i in range(3):
            result = await circuit_breaker(failing_func)
            with pytest.raises(RuntimeError):
                await result.unwrap_async()
        
        # 서킷브레이커가 열렸는지 확인
        assert circuit_breaker.state == "OPEN"
        assert call_count == 3
        
        # 서킷브레이커가 열린 상태에서는 함수가 호출되지 않음
        result = await circuit_breaker(failing_func)
        with pytest.raises(Exception) as exc_info:
            await result.unwrap_async()
        
        assert "Circuit breaker is OPEN" in str(exc_info.value)
        assert call_count == 3  # 호출되지 않음
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_state(self):
        """서킷브레이커 반열림 상태 테스트"""
        circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=2,
            timeout=0.05  # 짧은 타임아웃
        )
        
        async def initially_failing_then_success():
            # 처음에는 실패, 나중에는 성공
            if circuit_breaker.failure_count < 2:
                raise Exception("초기 실패")
            return "복구됨"
        
        # 서킷브레이커를 열기 위해 실패
        for _ in range(2):
            result = await circuit_breaker(initially_failing_then_success)
            with pytest.raises(Exception):
                await result.unwrap_async()
        
        assert circuit_breaker.state == "OPEN"
        
        # 타임아웃 대기
        await asyncio.sleep(0.06)
        
        # 이제 성공하는 함수로 테스트
        async def success_func():
            return "복구 성공"
        
        result = await circuit_breaker(success_func)
        value = await result.unwrap_async()
        
        assert value == "복구 성공"
        assert circuit_breaker.state == "CLOSED"
    
    @pytest.mark.asyncio
    async def test_with_circuit_breaker_decorator(self):
        """with_circuit_breaker 데코레이터 테스트"""
        circuit_breaker_wrapper = with_circuit_breaker(
            failure_threshold=2,
            timeout=0.1
        )
        
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception(f"실패 {call_count}")
            return f"성공 {call_count}"
        
        # 처음 두 번은 실패
        for _ in range(2):
            result = await circuit_breaker_wrapper(test_func)
            with pytest.raises(Exception):
                await result.unwrap_async()
        
        # 세 번째 호출은 서킷브레이커가 차단
        result = await circuit_breaker_wrapper(test_func)
        with pytest.raises(Exception) as exc_info:
            await result.unwrap_async()
        
        assert "Circuit breaker" in str(exc_info.value)
        assert call_count == 2


class TestAsyncErrorStrategy:
    """AsyncErrorStrategy 에러 전략 테스트"""
    
    @pytest.mark.asyncio
    async def test_error_strategy_ignore(self):
        """에러 무시 전략 테스트"""
        strategy = AsyncErrorStrategy("ignore")
        
        async def failing_func():
            raise ValueError("무시될 에러")
        
        result = await strategy.handle_error(failing_func, ValueError("무시될 에러"))
        
        # ignore 전략은 기본값을 반환하거나 에러를 무시
        # 구체적인 구현에 따라 테스트 조정 필요
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_error_strategy_retry(self):
        """에러 재시도 전략 테스트"""
        strategy = AsyncErrorStrategy("retry", max_retries=2)
        
        call_count = 0
        
        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("재시도될 에러")
            return "재시도 성공"
        
        result = await strategy.apply(eventually_succeed)
        value = await result.unwrap_async()
        
        assert value == "재시도 성공"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_error_strategy_fallback(self):
        """에러 폴백 전략 테스트"""
        async def fallback_func():
            return "폴백 결과"
        
        strategy = AsyncErrorStrategy("fallback", fallback_function=fallback_func)
        
        async def failing_func():
            raise RuntimeError("폴백될 에러")
        
        result = await strategy.apply(failing_func)
        value = await result.unwrap_async()
        
        assert value == "폴백 결과"


class TestAsyncErrorMonitor:
    """AsyncErrorMonitor 에러 모니터링 테스트"""
    
    def test_error_monitor_creation(self):
        """에러 모니터 생성 테스트"""
        monitor = AsyncErrorMonitor()
        
        assert monitor.total_errors == 0
        assert len(monitor.error_history) == 0
    
    @pytest.mark.asyncio
    async def test_error_monitor_recording(self):
        """에러 기록 테스트"""
        monitor = AsyncErrorMonitor()
        
        error1 = ValueError("첫 번째 에러")
        error2 = RuntimeError("두 번째 에러")
        
        monitor.record_error("operation1", error1, ErrorSeverity.HIGH)
        monitor.record_error("operation2", error2, ErrorSeverity.MEDIUM)
        
        assert monitor.total_errors == 2
        assert len(monitor.error_history) == 2
        
        # 최근 에러 확인
        recent_error = monitor.get_recent_errors(1)[0]
        assert recent_error.operation_name == "operation2"
        assert recent_error.error == error2
        assert recent_error.severity == ErrorSeverity.MEDIUM
    
    def test_error_monitor_severity_filtering(self):
        """심각도별 에러 필터링 테스트"""
        monitor = AsyncErrorMonitor()
        
        # 다양한 심각도의 에러 추가
        monitor.record_error("op1", ValueError("낮음"), ErrorSeverity.LOW)
        monitor.record_error("op2", RuntimeError("중간"), ErrorSeverity.MEDIUM)
        monitor.record_error("op3", ConnectionError("높음"), ErrorSeverity.HIGH)
        monitor.record_error("op4", Exception("긴급"), ErrorSeverity.CRITICAL)
        
        # 심각도별 필터링
        high_errors = monitor.get_errors_by_severity(ErrorSeverity.HIGH)
        critical_errors = monitor.get_errors_by_severity(ErrorSeverity.CRITICAL)
        
        assert len(high_errors) == 1
        assert len(critical_errors) == 1
        assert high_errors[0].operation_name == "op3"
        assert critical_errors[0].operation_name == "op4"
    
    def test_error_monitor_statistics(self):
        """에러 통계 테스트"""
        monitor = AsyncErrorMonitor()
        
        # 같은 연산에 대한 여러 에러
        for i in range(5):
            monitor.record_error("database_connect", 
                               ConnectionError(f"연결 실패 {i}"), 
                               ErrorSeverity.HIGH)
        
        for i in range(3):
            monitor.record_error("api_call", 
                               RuntimeError(f"API 실패 {i}"), 
                               ErrorSeverity.MEDIUM)
        
        stats = monitor.get_error_statistics()
        
        assert stats["total_errors"] == 8
        assert stats["errors_by_operation"]["database_connect"] == 5
        assert stats["errors_by_operation"]["api_call"] == 3
        assert stats["errors_by_severity"][ErrorSeverity.HIGH] == 5
        assert stats["errors_by_severity"][ErrorSeverity.MEDIUM] == 3


class TestIntegratedErrorHandling:
    """통합 에러 처리 시나리오 테스트"""
    
    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker(self):
        """재시도와 서킷브레이커 조합 테스트"""
        circuit_breaker = AsyncCircuitBreaker(failure_threshold=3, timeout=0.1)
        retry_wrapper = AsyncRetryWrapper(max_attempts=2, base_delay=0.01)
        
        call_count = 0
        
        async def unreliable_service():
            nonlocal call_count
            call_count += 1
            raise ConnectionError(f"서비스 실패 {call_count}")
        
        # 재시도 + 서킷브레이커 조합
        async def combined_wrapper():
            retry_result = await retry_wrapper(unreliable_service)
            return await circuit_breaker(lambda: retry_result.to_result())
        
        # 여러 번 실패하여 서킷브레이커가 열릴 때까지 테스트
        for attempt in range(4):
            try:
                result = await combined_wrapper()
                await result.unwrap_async()
            except Exception as e:
                if "Circuit breaker" in str(e):
                    break
        
        # 서킷브레이커가 열렸는지 확인
        assert circuit_breaker.state == "OPEN"
    
    @pytest.mark.asyncio
    async def test_fallback_with_monitoring(self):
        """폴백과 모니터링 조합 테스트"""
        monitor = AsyncErrorMonitor()
        
        async def primary_service():
            error = RuntimeError("주 서비스 실패")
            monitor.record_error("primary_service", error, ErrorSeverity.HIGH)
            raise error
        
        async def fallback_service():
            return "폴백 서비스 성공"
        
        wrapper = AsyncFallbackWrapper(fallback_service)
        result = await wrapper(primary_service)
        value = await result.unwrap_async()
        
        assert value == "폴백 서비스 성공"
        assert monitor.total_errors == 1
        assert monitor.get_recent_errors(1)[0].operation_name == "primary_service"
    
    @pytest.mark.asyncio
    async def test_comprehensive_error_handling_pipeline(self):
        """종합 에러 처리 파이프라인 테스트"""
        from rfs.async_pipeline import AsyncPipeline
        
        monitor = AsyncErrorMonitor()
        
        def step1(x: str) -> str:
            if x == "fail_step1":
                error = ValueError("1단계 실패")
                monitor.record_error("step1", error, ErrorSeverity.MEDIUM)
                raise error
            return f"1단계: {x}"
        
        async def step2(x: str) -> str:
            if "fail_step2" in x:
                error = ConnectionError("2단계 연결 실패")
                monitor.record_error("step2", error, ErrorSeverity.HIGH)
                raise error
            await asyncio.sleep(0.01)
            return f"2단계: {x}"
        
        def step3(x: str) -> str:
            return f"3단계: {x}"
        
        # 에러 처리 전략이 적용된 파이프라인
        retry_step2 = with_retry(max_attempts=2)(step2)
        fallback_step3 = with_fallback(lambda: asyncio.sleep(0.01) or "3단계: 폴백")(step3)
        
        pipeline = AsyncPipeline([
            step1,
            lambda x: retry_step2(x).unwrap_async() if hasattr(retry_step2(x), 'unwrap_async') else step2(x),
            lambda x: fallback_step3(x).unwrap_async() if hasattr(fallback_step3(x), 'unwrap_async') else step3(x)
        ])
        
        # 정상 케이스
        result = await pipeline.execute("정상")
        value = await result.unwrap_async()
        assert "3단계: 2단계: 1단계: 정상" in value
        
        # 1단계 실패 케이스
        result = await pipeline.execute("fail_step1")
        with pytest.raises(ValueError, match="1단계 실패"):
            await result.unwrap_async()
        
        assert monitor.total_errors >= 1


if __name__ == "__main__":
    # 개별 테스트 실행을 위한 헬퍼
    asyncio.run(pytest.main([__file__, "-v"]))