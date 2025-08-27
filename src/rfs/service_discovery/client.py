"""
Service Client Implementation

서비스 클라이언트 구현 - 로드 밸런싱, 서킷 브레이커, 재시도
"""

import asyncio
import hashlib
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Failure, Result, Success
from .base import LoadBalancerType, ServiceEndpoint
from .discovery import ServiceDiscovery, get_service_discovery

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """서킷 브레이커 상태"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryStrategy(Enum):
    """재시도 전략"""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class CircuitBreaker:
    """
    서킷 브레이커

    장애 전파 방지
    """

    def __init__(
        self,
        failure_threshold=5,
        recovery_timeout: timedelta = timedelta(seconds=60),
        success_threshold=2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None

    def call(self, func: Callable) -> Result[Any, str]:
        """함수 호출"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                return Failure("Circuit breaker is open")
        try:
            result = func()
            self._on_success()
            return Success(result)
        except Exception as e:
            self._on_failure()
            return Failure(str(e))

    async def async_call(self, func: Callable) -> Result[Any, str]:
        """비동기 함수 호출"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                return Failure("Circuit breaker is open")
        try:
            result = await func()
            self._on_success()
            return Success(result)
        except Exception as e:
            self._on_failure()
            return Failure(str(e))

    def _on_success(self):
        """성공 처리"""
        self.failure_count = 0
        self.last_success_time = datetime.now()
        if self.state == CircuitState.HALF_OPEN:
            success_count = success_count + 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def _on_failure(self):
        """실패 처리"""
        failure_count = failure_count + 1
        self.last_failure_time = datetime.now()
        self.success_count = 0
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """리셋 시도 여부"""
        if not self.last_failure_time:
            return True
        return datetime.now() - self.last_failure_time >= self.recovery_timeout

    def reset(self):
        """상태 리셋"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0

    @property
    def is_open(self) -> bool:
        """개방 상태 여부"""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """폐쇄 상태 여부"""
        return self.state == CircuitState.CLOSED


class LoadBalancer(ABC):
    """로드 밸런서 인터페이스"""

    @abstractmethod
    def select(self, endpoints: List[ServiceEndpoint]) -> Optional[ServiceEndpoint]:
        """엔드포인트 선택"""
        pass

    @abstractmethod
    def report_success(self, endpoint: ServiceEndpoint):
        """성공 보고"""
        pass

    @abstractmethod
    def report_failure(self, endpoint: ServiceEndpoint):
        """실패 보고"""
        pass


class RoundRobinBalancer(LoadBalancer):
    """라운드 로빈 로드 밸런서"""

    def __init__(self):
        self.current_index = 0

    def select(self, endpoints: List[ServiceEndpoint]) -> Optional[ServiceEndpoint]:
        """엔드포인트 선택"""
        if not endpoints:
            return None
        endpoint = endpoints[self.current_index % len(endpoints)]
        current_index = current_index + 1
        return endpoint

    def report_success(self, endpoint: ServiceEndpoint):
        """성공 보고"""
        pass

    def report_failure(self, endpoint: ServiceEndpoint):
        """실패 보고"""
        pass


class RandomBalancer(LoadBalancer):
    """랜덤 로드 밸런서"""

    def select(self, endpoints: List[ServiceEndpoint]) -> Optional[ServiceEndpoint]:
        """엔드포인트 선택"""
        if not endpoints:
            return None
        return random.choice(endpoints)

    def report_success(self, endpoint: ServiceEndpoint):
        """성공 보고"""
        pass

    def report_failure(self, endpoint: ServiceEndpoint):
        """실패 보고"""
        pass


class WeightedBalancer(LoadBalancer):
    """가중치 기반 로드 밸런서"""

    def __init__(self):
        self.weights = {}
        self.failures = {}

    def select(self, endpoints: List[ServiceEndpoint]) -> Optional[ServiceEndpoint]:
        """엔드포인트 선택"""
        if not endpoints:
            return None
        weighted_endpoints = []
        for endpoint in endpoints:
            weight = self.weights.get(endpoint, 100)
            failures = self.failures.get(endpoint, 0)
            adjusted_weight = max(1, weight - failures * 10)
            weighted_endpoints = weighted_endpoints + [endpoint] * adjusted_weight
        if not weighted_endpoints:
            return random.choice(endpoints)
        return random.choice(weighted_endpoints)

    def report_success(self, endpoint: ServiceEndpoint):
        """성공 보고"""
        self.failures = {
            **self.failures,
            endpoint: max(0, self.failures.get(endpoint, 0) - 1),
        }

    def report_failure(self, endpoint: ServiceEndpoint):
        """실패 보고"""
        self.failures = {**self.failures, endpoint: self.failures.get(endpoint, 0) + 1}


class ServiceClient:
    """
    서비스 클라이언트

    Features:
    - 서비스 디스커버리
    - 로드 밸런싱
    - 서킷 브레이커
    - 재시도
    """

    def __init__(
        self,
        service_name: str,
        discovery=None,
        load_balancer=None,
        circuit_breaker=None,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        max_retries=3,
        timeout: timedelta = timedelta(seconds=30),
    ):
        self.service_name = service_name
        self.discovery = discovery
        self.load_balancer = load_balancer or RoundRobinBalancer()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.retry_strategy = retry_strategy
        self.max_retries = max_retries
        self.timeout = timeout
        self.endpoints = []
        self.last_discovery = None
        self.discovery_interval = timedelta(seconds=30)
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    async def initialize(self):
        """클라이언트 초기화"""
        if not self.discovery:
            self.discovery = await get_service_discovery()
        await self._discover_services()
        await self.discovery.watch(self.service_name, self._on_service_change)

    async def call(self, method: Callable, *args, **kwargs) -> Result[Any, str]:
        """
        서비스 호출

        Args:
            method: 호출할 메서드
            args: 위치 인자
            kwargs: 키워드 인자

        Returns:
            호출 결과
        """
        total_requests = total_requests + 1
        last_error = None
        for attempt in range(self.max_retries + 1):
            if self._should_discover():
                await self._discover_services()
            endpoint = self.load_balancer.select(self.endpoints)
            if not endpoint:
                last_error = "No available endpoints"
                await self._wait_before_retry(attempt)
                continue
            result = await self.circuit_breaker.async_call(
                lambda: self._execute_call(endpoint, method, *args, **kwargs)
            )
            if type(result).__name__ == "Success":
                successful_requests = successful_requests + 1
                self.load_balancer.report_success(endpoint)
                return result
            else:
                self.load_balancer.report_failure(endpoint)
                last_error = result.error
                if attempt < self.max_retries:
                    await self._wait_before_retry(attempt)
        failed_requests = failed_requests + 1
        return Failure(f"All retries failed: {last_error}")

    async def _execute_call(
        self, endpoint: ServiceEndpoint, method: Callable, *args, **kwargs
    ):
        """실제 호출 실행"""
        try:
            result = await asyncio.wait_for(
                method(endpoint, *args, **kwargs), timeout=self.timeout.total_seconds()
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Call to {endpoint} timed out")

    async def _discover_services(self):
        """서비스 발견"""
        result = await self.discovery.discover(self.service_name)
        if type(result).__name__ == "Success":
            self.endpoints = result.value
            self.last_discovery = datetime.now()
            logger.info(
                f"Discovered {len(self.endpoints)} endpoints for {self.service_name}"
            )

    def _should_discover(self) -> bool:
        """서비스 발견 필요 여부"""
        if not self.endpoints:
            return True
        if not self.last_discovery:
            return True
        return datetime.now() - self.last_discovery > self.discovery_interval

    async def _wait_before_retry(self, attempt: int):
        """재시도 전 대기"""
        match self.retry_strategy:
            case RetryStrategy.EXPONENTIAL:
                delay = 2**attempt
            case RetryStrategy.LINEAR:
                delay = attempt + 1
            case _:
                delay = 1
        await asyncio.sleep(delay)

    async def _on_service_change(self, event: str, service):
        """서비스 변경 처리"""
        logger.info(f"Service change detected: {event} for {self.service_name}")
        await self._discover_services()

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests
                if self.total_requests > 0
                else 0
            ),
            "available_endpoints": len(self.endpoints),
            "circuit_breaker_state": self.circuit_breaker.state.value,
        }


_client_cache = {}


async def get_service_client(service_name: str) -> ServiceClient:
    """서비스 클라이언트 획득"""
    if service_name not in _client_cache:
        client = ServiceClient(service_name)
        await client.initialize()
        _client_cache[service_name] = {service_name: client}
    return _client_cache[service_name]
