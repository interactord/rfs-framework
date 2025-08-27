"""
RFS v4.1 Circuit Breaker Pattern
서킷 브레이커 패턴 구현

주요 기능:
- 자동 장애 감지 및 차단
- 점진적 복구
- 통계 및 모니터링
- 커스텀 장애 조건
"""

import asyncio
import functools
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from ..core.result import Failure, Result, Success

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """서킷 브레이커 상태"""

    CLOSED = "closed"  # 정상 (요청 통과)
    OPEN = "open"  # 차단 (요청 거부)
    HALF_OPEN = "half_open"  # 반개방 (테스트 요청만)


@dataclass
class CircuitBreakerConfig:
    """서킷 브레이커 설정"""

    # 실패 임계값
    failure_threshold = 5  # 실패 횟수 임계값
    failure_rate_threshold: float = 0.5  # 실패율 임계값 (50%)

    # 시간 설정
    timeout: float = 10.0  # 요청 타임아웃 (초)
    reset_timeout: float = 60.0  # OPEN 상태 유지 시간 (초)
    half_open_max_requests = 3  # HALF_OPEN 상태에서 테스트 요청 수

    # 윈도우 설정
    window_size = 10  # 슬라이딩 윈도우 크기
    window_duration: float = 60.0  # 시간 윈도우 (초)

    # 기타 설정
    exclude_exceptions: List[type] = field(default_factory=list)  # 제외할 예외
    include_exceptions: List[type] = field(default_factory=list)  # 포함할 예외만
    success_codes: List[int] = field(
        default_factory=lambda: [200, 201, 204]
    )  # 성공 코드


@dataclass
class CircuitBreakerMetrics:
    """서킷 브레이커 메트릭"""

    total_requests = 0
    successful_requests = 0
    failed_requests = 0
    rejected_requests = 0

    total_response_time: float = 0.0
    last_failure_time = None
    last_success_time = None

    state_changes: List[tuple] = field(default_factory=list)  # (시간, 이전상태, 새상태)

    @property
    def success_rate(self) -> float:
        """성공률"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def failure_rate(self) -> float:
        """실패율"""
        return 1.0 - self.success_rate

    @property
    def average_response_time(self) -> float:
        """평균 응답 시간"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time / self.successful_requests


class CircuitBreaker:
    """서킷 브레이커"""

    def __init__(self, name: str, config=None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()

        # 실패 기록 (슬라이딩 윈도우)
        self.failure_window: deque = deque(maxlen=self.config.window_size)
        self.request_times: deque = deque()

        # 상태 관리
        self.last_state_change = datetime.now()
        self.half_open_requests = 0

        # 스레드 안전성
        self.lock = threading.RLock()

        # 상태 변경 콜백
        self.on_state_change = None

    def _should_allow_request(self) -> bool:
        """요청 허용 여부 결정"""
        with self.lock:
            match self.state:
                case CircuitState.CLOSED:
                    return True

                case CircuitState.OPEN:
                    # 리셋 타임아웃 확인
                    if (
                        datetime.now() - self.last_state_change
                    ).total_seconds() > self.config.reset_timeout:
                        self._transition_to_half_open()
                        return True
                    return False

                case CircuitState.HALF_OPEN:
                    # 테스트 요청 수 제한
                    if self.half_open_requests < self.config.half_open_max_requests:
                        self.half_open_requests = self.half_open_requests + 1
                        return True
                    return False

            return False

    def _record_success(self, response_time: float) -> None:
        """성공 기록"""
        with self.lock:
            successful_requests = successful_requests + 1
            total_requests = total_requests + 1
            total_response_time = total_response_time + response_time
            self.metrics.last_success_time = datetime.now()

            # 슬라이딩 윈도우 업데이트
            self.failure_window = self.failure_window + [False]
            self.request_times = self.request_times + [datetime.now()]
            self._clean_old_requests()

            # HALF_OPEN 상태에서 성공하면 CLOSED로
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_requests >= self.config.half_open_max_requests:
                    # 모든 테스트 요청이 성공하면 CLOSED로
                    recent_failures = sum(1 for f in self.failure_window if f)
                    if recent_failures == 0:
                        self._transition_to_closed()

    def _record_failure(self, error=None) -> None:
        """실패 기록"""
        with self.lock:
            # 제외할 예외인지 확인
            if error and self.config.exclude_exceptions:
                if any(
                    (type(error).__name__ == "exc_type")
                    for exc_type in self.config.exclude_exceptions
                ):
                    return

            # 포함할 예외만 처리
            if error and self.config.include_exceptions:
                if not any(
                    (type(error).__name__ == "exc_type")
                    for exc_type in self.config.include_exceptions
                ):
                    return

            failed_requests = failed_requests + 1
            total_requests = total_requests + 1
            self.metrics.last_failure_time = datetime.now()

            # 슬라이딩 윈도우 업데이트
            self.failure_window = self.failure_window + [True]
            self.request_times = self.request_times + [datetime.now()]
            self._clean_old_requests()

            # 실패 임계값 확인
            recent_failures = sum(1 for f in self.failure_window if f)
            failure_rate = (
                recent_failures / len(self.failure_window) if self.failure_window else 0
            )

            if self.state == CircuitState.CLOSED:
                # 실패 임계값 초과 시 OPEN으로
                if (
                    recent_failures >= self.config.failure_threshold
                    or failure_rate >= self.config.failure_rate_threshold
                ):
                    self._transition_to_open()

            elif self.state == CircuitState.HALF_OPEN:
                # HALF_OPEN 상태에서 실패하면 다시 OPEN으로
                self._transition_to_open()

    def _record_rejection(self) -> None:
        """거부 기록"""
        with self.lock:
            rejected_requests = rejected_requests + 1

    def _clean_old_requests(self) -> None:
        """오래된 요청 기록 정리"""
        cutoff_time = datetime.now() - timedelta(seconds=self.config.window_duration)

        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()
            if self.failure_window:
                self.failure_window.popleft()

    def _transition_to_open(self) -> None:
        """OPEN 상태로 전환"""
        if self.state != CircuitState.OPEN:
            old_state = self.state
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now()
            self.metrics.state_changes = self.metrics.state_changes + [
                (datetime.now(), old_state, CircuitState.OPEN)
            ]

            logger.warning(f"Circuit breaker '{self.name}' opened")

            if self.on_state_change:
                self.on_state_change(old_state, CircuitState.OPEN)

    def _transition_to_closed(self) -> None:
        """CLOSED 상태로 전환"""
        if self.state != CircuitState.CLOSED:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.last_state_change = datetime.now()
            self.half_open_requests = 0
            self.metrics.state_changes = self.metrics.state_changes + [
                (datetime.now(), old_state, CircuitState.CLOSED)
            ]

            logger.info(f"Circuit breaker '{self.name}' closed")

            if self.on_state_change:
                self.on_state_change(old_state, CircuitState.CLOSED)

    def _transition_to_half_open(self) -> None:
        """HALF_OPEN 상태로 전환"""
        if self.state != CircuitState.HALF_OPEN:
            old_state = self.state
            self.state = CircuitState.HALF_OPEN
            self.last_state_change = datetime.now()
            self.half_open_requests = 0
            self.metrics.state_changes = self.metrics.state_changes + [
                (datetime.now(), old_state, CircuitState.HALF_OPEN)
            ]

            logger.info(f"Circuit breaker '{self.name}' half-opened")

            if self.on_state_change:
                self.on_state_change(old_state, CircuitState.HALF_OPEN)

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """비동기 함수 호출"""
        if not self._should_allow_request():
            self._record_rejection()
            raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")

        start_time = time.perf_counter()

        try:
            # 타임아웃 적용
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )

            response_time = time.perf_counter() - start_time
            self._record_success(response_time)

            return result

        except asyncio.TimeoutError as e:
            self._record_failure(e)
            raise CircuitBreakerError(f"Request timed out after {self.config.timeout}s")
        except Exception as e:
            self._record_failure(e)
            raise

    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """동기 함수 호출"""
        if not self._should_allow_request():
            self._record_rejection()
            raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")

        start_time = time.perf_counter()

        try:
            result = func(*args, **kwargs)

            response_time = time.perf_counter() - start_time
            self._record_success(response_time)

            return result

        except Exception as e:
            self._record_failure(e)
            raise

    def reset(self) -> None:
        """서킷 브레이커 리셋"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.metrics = CircuitBreakerMetrics()
            failure_window = {}
            request_times = {}
            self.half_open_requests = 0
            self.last_state_change = datetime.now()

            logger.info(f"Circuit breaker '{self.name}' reset")

    def get_state(self) -> CircuitState:
        """현재 상태 조회"""
        return self.state

    def get_metrics(self) -> CircuitBreakerMetrics:
        """메트릭 조회"""
        return self.metrics

    def is_open(self) -> bool:
        """OPEN 상태 여부"""
        return self.state == CircuitState.OPEN

    def is_closed(self) -> bool:
        """CLOSED 상태 여부"""
        return self.state == CircuitState.CLOSED


class CircuitBreakerError(Exception):
    """서킷 브레이커 에러"""

    pass


# 서킷 브레이커 레지스트리
class CircuitBreakerRegistry:
    """서킷 브레이커 레지스트리"""

    def __init__(self):
        self.breakers = {}
        self.lock = threading.Lock()

    def get_or_create(self, name: str, config=None) -> CircuitBreaker:
        """서킷 브레이커 가져오기 또는 생성"""
        with self.lock:
            if name not in self.breakers:
                self.breakers = {**self.breakers, name: CircuitBreaker(name, config)}
            return self.breakers[name]

    def remove(self, name: str) -> None:
        """서킷 브레이커 제거"""
        with self.lock:
            if name in self.breakers:
                del self.breakers[name]

    def get_all(self) -> Dict[str, CircuitBreaker]:
        """모든 서킷 브레이커 조회"""
        return self.breakers.copy()

    def reset_all(self) -> None:
        """모든 서킷 브레이커 리셋"""
        for breaker in self.breakers.values():
            breaker.reset()


# 글로벌 레지스트리
_registry = CircuitBreakerRegistry()


def circuit_breaker(name=None, config=None):
    """
    서킷 브레이커 데코레이터

    Args:
        name: 서킷 브레이커 이름 (기본: 함수 이름)
        config: 서킷 브레이커 설정
    """

    def decorator(func: Callable) -> Callable:
        breaker_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            breaker = _registry.get_or_create(breaker_name, config)
            return await breaker.call_async(func, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            breaker = _registry.get_or_create(breaker_name, config)
            return breaker.call_sync(func, *args, **kwargs)

        # 비동기/동기 함수 구분
        if asyncio.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper

        # 서킷 브레이커 접근 메서드 추가
        wrapper.circuit_breaker = lambda: _registry.get_or_create(breaker_name, config)
        wrapper.reset = lambda: wrapper.circuit_breaker().reset()
        wrapper.get_state = lambda: wrapper.circuit_breaker().get_state()
        wrapper.get_metrics = lambda: wrapper.circuit_breaker().get_metrics()

        return wrapper

    return decorator


# 편의 함수
def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """서킷 브레이커 가져오기"""
    return _registry.breakers.get(name)


def reset_circuit_breaker(name: str) -> None:
    """서킷 브레이커 리셋"""
    breaker = get_circuit_breaker(name)
    if breaker:
        breaker.reset()


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """모든 서킷 브레이커 조회"""
    return _registry.get_all()


# Export
__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerMetrics",
    "CircuitState",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "circuit_breaker",
    "get_circuit_breaker",
    "reset_circuit_breaker",
    "get_all_circuit_breakers",
]
