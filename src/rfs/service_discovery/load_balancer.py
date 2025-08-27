"""
RFS v4.1 Client-Side Load Balancing
클라이언트 사이드 로드 밸런싱 구현

주요 기능:
- 다양한 로드 밸런싱 알고리즘
- 헬스체크 및 자동 제외
- 가중치 기반 분산
- 서킷 브레이커 통합
"""

import asyncio
import hashlib
import logging
import random
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

from ..core.result import Failure, Result, Success
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


class LoadBalancingStrategy(Enum):
    """로드 밸런싱 전략"""

    ROUND_ROBIN = "round_robin"  # 라운드 로빈
    RANDOM = "random"  # 랜덤
    LEAST_CONNECTIONS = "least_connections"  # 최소 연결
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"  # 가중치 라운드 로빈
    CONSISTENT_HASH = "consistent_hash"  # 일관된 해싱
    LEAST_RESPONSE_TIME = "least_response_time"  # 최소 응답 시간


class HealthStatus(Enum):
    """헬스 상태"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    """서비스 인스턴스"""

    id: str
    host: str
    port: int
    weight = 1  # 가중치 (기본 1)

    # 상태 정보
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_health_check = None
    consecutive_failures = 0

    # 성능 메트릭
    active_connections = 0
    total_requests = 0
    total_response_time: float = 0.0
    last_response_time: float = 0.0

    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def url(self) -> str:
        """URL 생성"""
        return f"http://{self.host}:{self.port}"

    @property
    def average_response_time(self) -> float:
        """평균 응답 시간"""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests

    def is_available(self) -> bool:
        """사용 가능 여부"""
        return self.health_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]


@dataclass
class LoadBalancerConfig:
    """로드 밸런서 설정"""

    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN

    # 헬스체크 설정
    health_check_enabled = True
    health_check_interval: float = 30.0  # 초
    health_check_timeout: float = 5.0  # 초
    health_check_path = "/health"
    max_consecutive_failures = 3

    # 재시도 설정
    retry_enabled = True
    max_retries = 3
    retry_delay: float = 1.0  # 초

    # 서킷 브레이커 설정
    circuit_breaker_enabled = True
    circuit_breaker_config = None

    # 기타 설정
    sticky_sessions = False  # 세션 고정
    session_cookie_name = "LB_SESSION"


class LoadBalancingAlgorithm(ABC):
    """로드 밸런싱 알고리즘 기본 클래스"""

    @abstractmethod
    def select(
        self, instances: List[ServiceInstance], context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """인스턴스 선택"""
        pass

    @abstractmethod
    def reset(self) -> None:
        """상태 리셋"""
        pass


class RoundRobinAlgorithm(LoadBalancingAlgorithm):
    """라운드 로빈 알고리즘"""

    def __init__(self):
        self.current_index = 0
        self.lock = threading.Lock()

    def select(
        self, instances: List[ServiceInstance], context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """라운드 로빈 방식으로 선택"""
        if not instances:
            return None

        available = [i for i in instances if i.is_available()]
        if not available:
            return None

        with self.lock:
            instance = available[self.current_index % len(available)]
            current_index = current_index + 1
            return instance

    def reset(self) -> None:
        """인덱스 리셋"""
        self.current_index = 0


class RandomAlgorithm(LoadBalancingAlgorithm):
    """랜덤 알고리즘"""

    def select(
        self, instances: List[ServiceInstance], context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """랜덤하게 선택"""
        available = [i for i in instances if i.is_available()]
        if not available:
            return None

        return random.choice(available)

    def reset(self) -> None:
        """상태 없음"""
        pass


class LeastConnectionsAlgorithm(LoadBalancingAlgorithm):
    """최소 연결 알고리즘"""

    def select(
        self, instances: List[ServiceInstance], context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """활성 연결이 가장 적은 인스턴스 선택"""
        available = [i for i in instances if i.is_available()]
        if not available:
            return None

        return min(available, key=lambda i: i.active_connections)

    def reset(self) -> None:
        """상태 없음"""
        pass


class WeightedRoundRobinAlgorithm(LoadBalancingAlgorithm):
    """가중치 라운드 로빈 알고리즘"""

    def __init__(self):
        self.current_weights = {}
        self.lock = threading.Lock()

    def select(
        self, instances: List[ServiceInstance], context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """가중치 기반 라운드 로빈"""
        available = [i for i in instances if i.is_available()]
        if not available:
            return None

        with self.lock:
            # 가중치 초기화
            for instance in available:
                if instance.id not in self.current_weights:
                    self.current_weights = {**self.current_weights, instance.id: 0}

            # 가중치 증가
            total_weight = 0
            for instance in available:
                self.current_weights[instance.id] = self.current_weights[
                    instance.id
                ] + (instance.weight)
                total_weight = total_weight + instance.weight

            # 최대 가중치 인스턴스 선택
            selected = max(available, key=lambda i: self.current_weights[i.id])

            # 선택된 인스턴스 가중치 감소
            self.current_weights[selected.id] = self.current_weights[selected.id] - (
                total_weight
            )

            return selected

    def reset(self) -> None:
        """가중치 리셋"""
        current_weights = {}


class ConsistentHashAlgorithm(LoadBalancingAlgorithm):
    """일관된 해싱 알고리즘"""

    def __init__(self, virtual_nodes=150):
        self.virtual_nodes = virtual_nodes
        self.ring = {}
        self.sorted_keys = []

    def _hash(self, key: str) -> int:
        """해시 함수"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def _build_ring(self, instances: List[ServiceInstance]) -> None:
        """해시 링 구축"""
        ring = {}

        for instance in instances:
            if instance.is_available():
                for i in range(self.virtual_nodes):
                    virtual_key = f"{instance.id}:{i}"
                    hash_value = self._hash(virtual_key)
                    self.ring = {**self.ring, hash_value: instance}

        self.sorted_keys = sorted(self.ring.keys())

    def select(
        self, instances: List[ServiceInstance], context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """일관된 해싱으로 선택"""
        available = [i for i in instances if i.is_available()]
        if not available:
            return None

        # 해시 링 재구축 (인스턴스 변경 시)
        self._build_ring(available)

        if not self.ring:
            return None

        # 컨텍스트에서 키 추출 (예: 사용자 ID, 세션 ID)
        key = ""
        if context:
            key = (
                context.get("key", "")
                or context.get("user_id", "")
                or context.get("session_id", "")
            )

        if not key:
            key = str(random.random())

        # 해시 계산
        hash_value = self._hash(key)

        # 이진 검색으로 다음 노드 찾기
        for sorted_key in self.sorted_keys:
            if sorted_key >= hash_value:
                return self.ring[sorted_key]

        # 링의 처음으로 돌아감
        return self.ring[self.sorted_keys[0]]

    def reset(self) -> None:
        """링 리셋"""
        ring = {}
        sorted_keys = {}


class LeastResponseTimeAlgorithm(LoadBalancingAlgorithm):
    """최소 응답 시간 알고리즘"""

    def select(
        self, instances: List[ServiceInstance], context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """평균 응답 시간이 가장 짧은 인스턴스 선택"""
        available = [i for i in instances if i.is_available()]
        if not available:
            return None

        # 요청이 없는 인스턴스 우선
        no_requests = [i for i in available if i.total_requests == 0]
        if no_requests:
            return random.choice(no_requests)

        return min(available, key=lambda i: i.average_response_time)

    def reset(self) -> None:
        """상태 없음"""
        pass


class LoadBalancer:
    """로드 밸런서"""

    def __init__(self, service_name: str, config=None):
        self.service_name = service_name
        self.config = config or LoadBalancerConfig()

        # 인스턴스 관리
        self.instances = {}
        self.lock = threading.RLock()

        # 알고리즘 선택
        self.algorithm = self._create_algorithm(self.config.strategy)

        # 서킷 브레이커
        self.circuit_breakers = {}

        # 헬스체크 태스크
        self.health_check_task = None

        # 세션 고정
        self.session_affinity = {}  # session_id -> instance_id

        # 통계
        self.total_requests = 0
        self.failed_requests = 0

    def _create_algorithm(
        self, strategy: LoadBalancingStrategy
    ) -> LoadBalancingAlgorithm:
        """알고리즘 생성"""
        algorithms = {
            LoadBalancingStrategy.ROUND_ROBIN: RoundRobinAlgorithm,
            LoadBalancingStrategy.RANDOM: RandomAlgorithm,
            LoadBalancingStrategy.LEAST_CONNECTIONS: LeastConnectionsAlgorithm,
            LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN: WeightedRoundRobinAlgorithm,
            LoadBalancingStrategy.CONSISTENT_HASH: ConsistentHashAlgorithm,
            LoadBalancingStrategy.LEAST_RESPONSE_TIME: LeastResponseTimeAlgorithm,
        }

        algorithm_class = algorithms.get(strategy, RoundRobinAlgorithm)
        return algorithm_class()

    def add_instance(self, instance: ServiceInstance) -> None:
        """인스턴스 추가"""
        with self.lock:
            self.instances = {**self.instances, instance.id: instance}

            # 서킷 브레이커 생성
            if self.config.circuit_breaker_enabled:
                self.circuit_breakers = {
                    **self.circuit_breakers,
                    instance.id: CircuitBreaker(
                        name=f"{self.service_name}:{instance.id}",
                        config=self.config.circuit_breaker_config,
                    ),
                }

            logger.info(
                f"Added instance {instance.id} to load balancer {self.service_name}"
            )

    def remove_instance(self, instance_id: str) -> None:
        """인스턴스 제거"""
        with self.lock:
            if instance_id in self.instances:
                del self.instances[instance_id]

                if instance_id in self.circuit_breakers:
                    del self.circuit_breakers[instance_id]

                # 세션 정리
                sessions_to_remove = [
                    session_id
                    for session_id, inst_id in self.session_affinity.items()
                    if inst_id == instance_id
                ]
                for session_id in sessions_to_remove:
                    del self.session_affinity[session_id]

                logger.info(
                    f"Removed instance {instance_id} from load balancer {self.service_name}"
                )

    def select_instance(
        self, context: Optional[Dict[str, Any]] = None
    ) -> Optional[ServiceInstance]:
        """인스턴스 선택"""
        with self.lock:
            # 세션 고정 확인
            if self.config.sticky_sessions and context:
                session_id = context.get("session_id")
                if session_id and session_id in self.session_affinity:
                    instance_id = self.session_affinity[session_id]
                    instance = self.instances.get(instance_id)
                    if instance and instance.is_available():
                        return instance

            # 알고리즘으로 선택
            instances = list(self.instances.values())
            selected = self.algorithm.select(instances, context)

            # 세션 고정 저장
            if selected and self.config.sticky_sessions and context:
                session_id = context.get("session_id")
                if session_id:
                    self.session_affinity = {
                        **self.session_affinity,
                        session_id: selected.id,
                    }

            return selected

    async def call(
        self, func: Callable, *args, context: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Any:
        """로드 밸런싱된 호출"""
        retries = 0
        last_error = None

        while retries <= self.config.max_retries:
            # 인스턴스 선택
            instance = self.select_instance(context)
            if not instance:
                raise LoadBalancerError("No available instances")

            try:
                # 연결 수 증가
                active_connections = active_connections + 1
                total_requests = total_requests + 1

                start_time = time.perf_counter()

                # 서킷 브레이커를 통한 호출
                if self.config.circuit_breaker_enabled:
                    breaker = self.circuit_breakers.get(instance.id)
                    if breaker:
                        if asyncio.iscoroutinefunction(func):
                            result = await breaker.call_async(
                                func, instance, *args, **kwargs
                            )
                        else:
                            result = breaker.call_sync(func, instance, *args, **kwargs)
                    else:
                        result = (
                            await func(instance, *args, **kwargs)
                            if asyncio.iscoroutinefunction(func)
                            else func(instance, *args, **kwargs)
                        )
                else:
                    result = (
                        await func(instance, *args, **kwargs)
                        if asyncio.iscoroutinefunction(func)
                        else func(instance, *args, **kwargs)
                    )

                # 메트릭 업데이트
                response_time = time.perf_counter() - start_time
                total_requests = total_requests + 1
                total_response_time = total_response_time + response_time
                instance.last_response_time = response_time
                instance.consecutive_failures = 0

                return result

            except Exception as e:
                last_error = e
                consecutive_failures = consecutive_failures + 1
                failed_requests = failed_requests + 1

                # 최대 실패 횟수 초과 시 인스턴스 비활성화
                if (
                    instance.consecutive_failures
                    >= self.config.max_consecutive_failures
                ):
                    instance.health_status = HealthStatus.UNHEALTHY
                    logger.warning(f"Instance {instance.id} marked as unhealthy")

                # 재시도
                if self.config.retry_enabled and retries < self.config.max_retries:
                    retries = retries + 1
                    await asyncio.sleep(self.config.retry_delay * retries)
                else:
                    raise

            finally:
                # 연결 수 감소
                instance.active_connections = max(0, instance.active_connections - 1)

        raise LoadBalancerError(f"All retry attempts failed: {last_error}")

    async def health_check(self, instance: ServiceInstance) -> HealthStatus:
        """헬스체크 수행"""
        try:
            # 실제 구현에서는 HTTP 요청 수행
            # 여기서는 시뮬레이션
            await asyncio.sleep(0.1)

            # 90% 확률로 healthy
            if random.random() < 0.9:
                return HealthStatus.HEALTHY
            else:
                return HealthStatus.DEGRADED

        except Exception as e:
            logger.error(f"Health check failed for instance {instance.id}: {e}")
            return HealthStatus.UNHEALTHY

    async def start_health_checks(self) -> None:
        """헬스체크 시작"""
        if not self.config.health_check_enabled:
            return

        async def health_check_loop():
            while True:
                try:
                    # 모든 인스턴스 헬스체크
                    for instance in list(self.instances.values()):
                        status = await self.health_check(instance)
                        instance.health_status = status
                        instance.last_health_check = datetime.now()

                        if status == HealthStatus.HEALTHY:
                            instance.consecutive_failures = 0

                    await asyncio.sleep(self.config.health_check_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health check loop error: {e}")
                    await asyncio.sleep(self.config.health_check_interval)

        self.health_check_task = asyncio.create_task(health_check_loop())

    async def stop_health_checks(self) -> None:
        """헬스체크 중지"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            self.health_check_task = None

    def get_statistics(self) -> Dict[str, Any]:
        """통계 조회"""
        with self.lock:
            available_instances = [
                i for i in self.instances.values() if i.is_available()
            ]

            return {
                "service_name": self.service_name,
                "strategy": self.config.strategy.value,
                "total_instances": len(self.instances),
                "available_instances": len(available_instances),
                "total_requests": self.total_requests,
                "failed_requests": self.failed_requests,
                "failure_rate": self.failed_requests / max(self.total_requests, 1),
                "instances": {
                    instance.id: {
                        "status": instance.health_status.value,
                        "active_connections": instance.active_connections,
                        "total_requests": instance.total_requests,
                        "average_response_time": instance.average_response_time,
                        "consecutive_failures": instance.consecutive_failures,
                    }
                    for instance in self.instances.values()
                },
            }


class LoadBalancerError(Exception):
    """로드 밸런서 에러"""

    pass


# Export
__all__ = [
    "LoadBalancer",
    "LoadBalancerConfig",
    "LoadBalancingStrategy",
    "ServiceInstance",
    "HealthStatus",
    "LoadBalancerError",
    "LoadBalancingAlgorithm",
    "RoundRobinAlgorithm",
    "RandomAlgorithm",
    "LeastConnectionsAlgorithm",
    "WeightedRoundRobinAlgorithm",
    "ConsistentHashAlgorithm",
    "LeastResponseTimeAlgorithm",
]
