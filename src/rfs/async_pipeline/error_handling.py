"""
AsyncPipeline 에러 처리 시스템

비동기 파이프라인에서 발생하는 다양한 에러 상황을 우아하게 처리하는 도구들.
재시도, 폴백, 서킷 브레이커 등의 고급 에러 복구 메커니즘을 제공합니다.
"""

import asyncio
import time
import logging
from collections import deque
from typing import Any, Awaitable, Callable, Dict, Optional, Type, Union
from dataclasses import dataclass, field
from enum import Enum

from .async_result import AsyncResult
from ..core.result import Success, Failure

logger = logging.getLogger(__name__)

# 타입 정의
T = TypeVar = Any
U = TypeVar = Any
E = TypeVar = Any


class ErrorSeverity(Enum):
    """에러 심각도 레벨"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AsyncErrorContext:
    """
    비동기 에러 컨텍스트
    
    에러 발생 시점의 상황 정보를 포함하여 디버깅과 모니터링을 돕습니다.
    """
    operation_name: str
    step_index: int
    error: Exception
    timestamp: float = field(default_factory=time.time)
    input_value: Any = None
    duration: float = 0.0
    retry_count: int = 0
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """에러 컨텍스트를 딕셔너리로 변환"""
        return {
            'operation_name': self.operation_name,
            'step_index': self.step_index,
            'error_message': str(self.error),
            'error_type': type(self.error).__name__,
            'timestamp': self.timestamp,
            'duration': self.duration,
            'retry_count': self.retry_count,
            'severity': self.severity.value,
            'metadata': self.metadata
        }
    
    def __str__(self) -> str:
        return (f"AsyncErrorContext(operation={self.operation_name}, "
                f"step={self.step_index}, error={type(self.error).__name__}, "
                f"retries={self.retry_count})")


class AsyncRetryWrapper:
    """
    비동기 재시도 래퍼
    
    지수 백오프, 지터, 조건부 재시도 등의 고급 재시도 전략을 지원합니다.
    
    Example:
        >>> retry_wrapper = AsyncRetryWrapper(
        ...     max_attempts=3,
        ...     base_delay=1.0,
        ...     backoff_factor=2.0,
        ...     max_delay=30.0,
        ...     jitter=True
        ... )
        >>> result = await retry_wrapper(unreliable_async_function)
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        exceptions: tuple[Type[Exception], ...] = (Exception,),
        retry_condition: Callable[[Exception], bool] | None = None
    ):
        """
        AsyncRetryWrapper 생성자
        
        Args:
            max_attempts: 최대 재시도 횟수
            base_delay: 기본 지연 시간 (초)
            backoff_factor: 백오프 배수
            max_delay: 최대 지연 시간 (초)
            jitter: 지터 적용 여부 (지연 시간에 랜덤 요소 추가)
            exceptions: 재시도 대상 예외 타입들
            retry_condition: 재시도 조건 함수 (예외를 받아 bool 반환)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.jitter = jitter
        self.exceptions = exceptions
        self.retry_condition = retry_condition or (lambda e: True)
    
    async def __call__(self, func: Callable[[], Awaitable[T]]) -> AsyncResult[T, AsyncErrorContext]:
        """
        재시도 실행
        
        Args:
            func: 실행할 비동기 함수
            
        Returns:
            AsyncResult[T, AsyncErrorContext]: 실행 결과 또는 에러 컨텍스트
        """
        last_error = None
        attempt_start = time.time()
        
        for attempt in range(self.max_attempts):
            try:
                # 첫 번째 시도가 아닌 경우 지연
                if attempt > 0:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                
                operation_start = time.time()
                result = await func()
                operation_duration = time.time() - operation_start
                
                # 성공 시 결과 반환
                return AsyncResult.from_value(result)
                
            except self.exceptions as e:
                last_error = e
                operation_duration = time.time() - operation_start
                
                # 재시도 조건 확인
                if not self.retry_condition(e):
                    error_context = AsyncErrorContext(
                        operation_name=getattr(func, '__name__', 'unknown'),
                        step_index=0,
                        error=e,
                        duration=operation_duration,
                        retry_count=attempt,
                        severity=ErrorSeverity.HIGH,
                        metadata={
                            'retry_skipped': True,
                            'reason': 'retry_condition_failed'
                        }
                    )
                    return AsyncResult.from_error(error_context)
                
                # 마지막 시도인 경우 에러 컨텍스트 반환
                if attempt == self.max_attempts - 1:
                    total_duration = time.time() - attempt_start
                    error_context = AsyncErrorContext(
                        operation_name=getattr(func, '__name__', 'unknown'),
                        step_index=0,
                        error=e,
                        duration=total_duration,
                        retry_count=attempt + 1,
                        severity=ErrorSeverity.HIGH,
                        metadata={
                            'max_attempts_exceeded': True,
                            'total_attempts': self.max_attempts
                        }
                    )
                    return AsyncResult.from_error(error_context)
                
                # 재시도 로그
                logger.warning(
                    f"재시도 {attempt + 1}/{self.max_attempts} - "
                    f"함수: {getattr(func, '__name__', 'unknown')}, "
                    f"에러: {type(e).__name__}: {str(e)}"
                )
        
        # 이론적으로 도달하지 않는 코드
        error_context = AsyncErrorContext(
            operation_name=getattr(func, '__name__', 'unknown'),
            step_index=0,
            error=last_error or Exception("Unknown error"),
            retry_count=self.max_attempts,
            severity=ErrorSeverity.CRITICAL
        )
        return AsyncResult.from_error(error_context)
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        지연 시간 계산 (지수 백오프 + 지터)
        
        Args:
            attempt: 현재 시도 번호 (0부터 시작)
            
        Returns:
            float: 계산된 지연 시간
        """
        # 지수 백오프
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        # 지터 적용
        if self.jitter:
            import random
            jitter_range = delay * 0.1  # 10% 지터
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class AsyncFallbackWrapper:
    """
    비동기 폴백 래퍼
    
    주 함수 실행 실패 시 대체 함수를 실행하는 폴백 메커니즘을 제공합니다.
    
    Example:
        >>> fallback = AsyncFallbackWrapper(default_data_source)
        >>> result = await fallback(primary_data_source)
    """
    
    def __init__(
        self,
        fallback_func: Callable[[], Awaitable[T]],
        fallback_condition: Callable[[Exception], bool] | None = None,
        chain_errors: bool = True
    ):
        """
        AsyncFallbackWrapper 생성자
        
        Args:
            fallback_func: 폴백 함수
            fallback_condition: 폴백 실행 조건 (예외를 받아 bool 반환)
            chain_errors: 에러 체이닝 여부
        """
        self.fallback_func = fallback_func
        self.fallback_condition = fallback_condition or (lambda e: True)
        self.chain_errors = chain_errors
    
    async def __call__(self, primary_func: Callable[[], Awaitable[T]]) -> AsyncResult[T, AsyncErrorContext]:
        """
        주 함수 실행, 실패 시 폴백 함수 실행
        
        Args:
            primary_func: 주 함수
            
        Returns:
            AsyncResult[T, AsyncErrorContext]: 실행 결과
        """
        primary_start = time.time()
        primary_error = None
        
        # 주 함수 실행 시도
        try:
            result = await primary_func()
            return AsyncResult.from_value(result)
            
        except Exception as e:
            primary_error = e
            primary_duration = time.time() - primary_start
            
            # 폴백 조건 확인
            if not self.fallback_condition(e):
                error_context = AsyncErrorContext(
                    operation_name=getattr(primary_func, '__name__', 'unknown'),
                    step_index=0,
                    error=e,
                    duration=primary_duration,
                    severity=ErrorSeverity.HIGH,
                    metadata={
                        'fallback_skipped': True,
                        'reason': 'fallback_condition_failed'
                    }
                )
                return AsyncResult.from_error(error_context)
            
            logger.warning(
                f"주 함수 실패, 폴백 실행 - "
                f"함수: {getattr(primary_func, '__name__', 'unknown')}, "
                f"에러: {type(e).__name__}: {str(e)}"
            )
        
        # 폴백 함수 실행
        fallback_start = time.time()
        try:
            fallback_result = await self.fallback_func()
            fallback_duration = time.time() - fallback_start
            
            logger.info(
                f"폴백 함수 성공 - "
                f"함수: {getattr(self.fallback_func, '__name__', 'fallback')}, "
                f"소요시간: {fallback_duration:.3f}초"
            )
            
            return AsyncResult.from_value(fallback_result)
            
        except Exception as fallback_error:
            fallback_duration = time.time() - fallback_start
            total_duration = time.time() - primary_start
            
            # 에러 체이닝
            if self.chain_errors:
                error_message = f"주 함수 에러: {str(primary_error)}, 폴백 함수 에러: {str(fallback_error)}"
                chained_error = Exception(error_message)
            else:
                chained_error = fallback_error
            
            error_context = AsyncErrorContext(
                operation_name=getattr(primary_func, '__name__', 'unknown'),
                step_index=0,
                error=chained_error,
                duration=total_duration,
                severity=ErrorSeverity.CRITICAL,
                metadata={
                    'primary_error': str(primary_error),
                    'fallback_error': str(fallback_error),
                    'primary_duration': time.time() - primary_start - fallback_duration,
                    'fallback_duration': fallback_duration
                }
            )
            return AsyncResult.from_error(error_context)


class AsyncCircuitBreaker:
    """
    비동기 서킷 브레이커
    
    연속적인 실패 시 일정 시간 동안 요청을 차단하여 시스템 보호.
    """
    
    class State(Enum):
        CLOSED = "closed"      # 정상 동작
        OPEN = "open"          # 차단 상태
        HALF_OPEN = "half_open"  # 복구 시도 상태
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exceptions: tuple[Type[Exception], ...] = (Exception,),
        success_threshold: int = 3
    ):
        """
        AsyncCircuitBreaker 생성자
        
        Args:
            failure_threshold: 실패 임계점 (연속 실패 횟수)
            recovery_timeout: 복구 시도 대기 시간 (초)
            expected_exceptions: 서킷브레이커가 처리할 예외 타입들
            success_threshold: HALF_OPEN에서 CLOSED로 전환 임계점
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        self.success_threshold = success_threshold
        
        self.state = self.State.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.call_count = 0
        
        self._lock = asyncio.Lock()
    
    async def __call__(self, func: Callable[[], Awaitable[T]]) -> AsyncResult[T, AsyncErrorContext]:
        """
        서킷 브레이커를 통한 함수 실행
        
        Args:
            func: 실행할 함수
            
        Returns:
            AsyncResult[T, AsyncErrorContext]: 실행 결과
        """
        async with self._lock:
            self.call_count += 1
            
            # 상태 확인 및 업데이트
            await self._update_state()
            
            # OPEN 상태인 경우 즉시 에러 반환
            if self.state == self.State.OPEN:
                error_context = AsyncErrorContext(
                    operation_name=getattr(func, '__name__', 'unknown'),
                    step_index=0,
                    error=Exception("Circuit breaker is OPEN"),
                    severity=ErrorSeverity.HIGH,
                    metadata={
                        'circuit_state': self.state.value,
                        'failure_count': self.failure_count,
                        'last_failure_time': self.last_failure_time
                    }
                )
                return AsyncResult.from_error(error_context)
        
        # 함수 실행
        start_time = time.time()
        try:
            result = await func()
            duration = time.time() - start_time
            
            # 성공 처리
            async with self._lock:
                await self._on_success()
            
            return AsyncResult.from_value(result)
            
        except self.expected_exceptions as e:
            duration = time.time() - start_time
            
            # 실패 처리
            async with self._lock:
                await self._on_failure()
            
            error_context = AsyncErrorContext(
                operation_name=getattr(func, '__name__', 'unknown'),
                step_index=0,
                error=e,
                duration=duration,
                severity=ErrorSeverity.MEDIUM,
                metadata={
                    'circuit_state': self.state.value,
                    'failure_count': self.failure_count
                }
            )
            return AsyncResult.from_error(error_context)
    
    async def _update_state(self):
        """서킷 브레이커 상태 업데이트"""
        current_time = time.time()
        
        if (self.state == self.State.OPEN and 
            current_time - self.last_failure_time >= self.recovery_timeout):
            self.state = self.State.HALF_OPEN
            self.success_count = 0
            logger.info("Circuit breaker state: OPEN -> HALF_OPEN")
    
    async def _on_success(self):
        """성공 시 상태 처리"""
        if self.state == self.State.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = self.State.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker state: HALF_OPEN -> CLOSED")
        elif self.state == self.State.CLOSED:
            self.failure_count = 0
    
    async def _on_failure(self):
        """실패 시 상태 처리"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == self.State.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = self.State.OPEN
                logger.warning("Circuit breaker state: CLOSED -> OPEN")
        elif self.state == self.State.HALF_OPEN:
            self.state = self.State.OPEN
            logger.warning("Circuit breaker state: HALF_OPEN -> OPEN")
    
    def get_stats(self) -> Dict[str, Any]:
        """서킷 브레이커 통계 정보 반환"""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'call_count': self.call_count,
            'last_failure_time': self.last_failure_time
        }


# === 데코레이터 팩토리 함수들 ===

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: tuple[Type[Exception], ...] = (Exception,)
) -> AsyncRetryWrapper:
    """
    재시도 데코레이터 팩토리
    
    Args:
        max_attempts: 최대 재시도 횟수
        base_delay: 기본 지연 시간
        backoff_factor: 백오프 배수
        max_delay: 최대 지연 시간
        jitter: 지터 적용 여부
        exceptions: 재시도 대상 예외들
        
    Returns:
        AsyncRetryWrapper: 재시도 래퍼
        
    Example:
        >>> @with_retry(max_attempts=3, base_delay=1.0)
        >>> async def unreliable_function():
        ...     # 가끔 실패할 수 있는 함수
        ...     pass
    """
    return AsyncRetryWrapper(
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_factor=backoff_factor,
        max_delay=max_delay,
        jitter=jitter,
        exceptions=exceptions
    )


def with_fallback(
    fallback_func: Callable[[], Awaitable[T]],
    fallback_condition: Callable[[Exception], bool] | None = None
) -> AsyncFallbackWrapper:
    """
    폴백 데코레이터 팩토리
    
    Args:
        fallback_func: 폴백 함수
        fallback_condition: 폴백 실행 조건
        
    Returns:
        AsyncFallbackWrapper: 폴백 래퍼
        
    Example:
        >>> async def default_response():
        ...     return {"status": "fallback"}
        >>> 
        >>> fallback_wrapper = with_fallback(default_response)
        >>> result = await fallback_wrapper(primary_function)
    """
    return AsyncFallbackWrapper(fallback_func, fallback_condition)


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exceptions: tuple[Type[Exception], ...] = (Exception,)
) -> AsyncCircuitBreaker:
    """
    서킷 브레이커 데코레이터 팩토리
    
    Args:
        failure_threshold: 실패 임계점
        recovery_timeout: 복구 시도 대기 시간
        expected_exceptions: 처리할 예외 타입들
        
    Returns:
        AsyncCircuitBreaker: 서킷 브레이커
    """
    return AsyncCircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exceptions=expected_exceptions
    )


# === 조합된 에러 처리 전략 ===

class AsyncErrorStrategy:
    """
    복합 에러 처리 전략
    
    재시도, 폴백, 서킷브레이커를 조합한 포괄적인 에러 처리 전략
    """
    
    def __init__(
        self,
        retry_config: Dict[str, Any] | None = None,
        fallback_func: Callable[[], Awaitable[T]] | None = None,
        circuit_config: Dict[str, Any] | None = None
    ):
        """
        AsyncErrorStrategy 생성자
        
        Args:
            retry_config: 재시도 설정
            fallback_func: 폴백 함수
            circuit_config: 서킷브레이커 설정
        """
        self.retry_wrapper = AsyncRetryWrapper(**retry_config) if retry_config else None
        self.fallback_wrapper = AsyncFallbackWrapper(fallback_func) if fallback_func else None
        self.circuit_breaker = AsyncCircuitBreaker(**circuit_config) if circuit_config else None
    
    async def execute(self, func: Callable[[], Awaitable[T]]) -> AsyncResult[T, AsyncErrorContext]:
        """
        전략에 따라 함수 실행
        
        실행 순서: Circuit Breaker -> Retry -> Fallback
        """
        current_func = func
        
        # 폴백 적용
        if self.fallback_wrapper:
            current_func = lambda: self.fallback_wrapper(current_func)
        
        # 재시도 적용
        if self.retry_wrapper:
            current_func = lambda: self.retry_wrapper(current_func)
        
        # 서킷 브레이커 적용
        if self.circuit_breaker:
            return await self.circuit_breaker(current_func)
        else:
            return await current_func()


# === 에러 모니터링 및 분석 ===

class AsyncErrorMonitor:
    """
    비동기 에러 모니터링 시스템
    
    에러 발생 패턴 분석, 알림, 통계 수집 등의 기능 제공
    """
    
    def __init__(self, max_history_size: int = 1000):
        """
        Args:
            max_history_size: 최대 히스토리 보관 개수
        """
        self.error_history: deque[AsyncErrorContext] = deque(maxlen=max_history_size)
        self.error_stats: Dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    async def record_error(self, error_context: AsyncErrorContext):
        """에러 기록"""
        async with self._lock:
            self.error_history.append(error_context)
            
            # 통계 업데이트
            error_type = type(error_context.error).__name__
            self.error_stats[error_type] = self.error_stats.get(error_type, 0) + 1
    
    async def get_recent_errors(self, count: int = 10) -> list[AsyncErrorContext]:
        """최근 에러 조회"""
        async with self._lock:
            return list(self.error_history)[-count:]
    
    async def get_error_stats(self) -> Dict[str, Any]:
        """에러 통계 조회"""
        async with self._lock:
            total_errors = len(self.error_history)
            if total_errors == 0:
                return {'total_errors': 0}
            
            # 심각도별 분포
            severity_distribution = {}
            operation_distribution = {}
            
            for error in self.error_history:
                severity = error.severity.value
                operation = error.operation_name
                
                severity_distribution[severity] = severity_distribution.get(severity, 0) + 1
                operation_distribution[operation] = operation_distribution.get(operation, 0) + 1
            
            return {
                'total_errors': total_errors,
                'error_types': dict(self.error_stats),
                'severity_distribution': severity_distribution,
                'operation_distribution': operation_distribution,
                'recent_error_rate': self._calculate_recent_error_rate()
            }
    
    def _calculate_recent_error_rate(self) -> float:
        """최근 에러 발생률 계산 (지난 5분)"""
        current_time = time.time()
        recent_threshold = current_time - 300  # 5분
        
        recent_errors = sum(
            1 for error in self.error_history 
            if error.timestamp >= recent_threshold
        )
        
        return recent_errors / 5.0  # 분당 에러 수