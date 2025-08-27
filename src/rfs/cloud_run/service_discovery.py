"""
Cloud Run Service Discovery (RFS v4)

Cloud Run 네이티브 서비스 검색 및 통신
- 서비스 자동 발견 및 등록
- 서비스 간 HTTP/gRPC 통신 최적화
- 헬스 체크 및 회로 차단기 패턴
- Load Balancing 및 Retry 정책
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from google.auth import default as google_auth_default
    from google.cloud import run_v2
    from pydantic import BaseModel, ConfigDict, Field, field_validator

    GOOGLE_CLOUD_AVAILABLE = True
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object
    Field = lambda default=None, **kwargs: default
    run_v2 = None
    GOOGLE_CLOUD_AVAILABLE = False
    PYDANTIC_AVAILABLE = False
from ..core.enhanced_logging import log_debug, log_error, log_info, log_warning
from ..core.result import Failure, Maybe, Result, Success
from ..reactive import Flux, Mono

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """서비스 상태"""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"


class LoadBalancingStrategy(str, Enum):
    """로드 밸런싱 전략"""

    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"


if PYDANTIC_AVAILABLE:

    class ServiceEndpoint(BaseModel):
        """서비스 엔드포인트 정보 (Pydantic v2)"""

        model_config = ConfigDict(
            str_strip_whitespace=True, validate_default=True, frozen=False
        )
        service_name: str = Field(
            ..., min_length=1, max_length=100, description="서비스 이름"
        )
        url: str = Field(
            ..., pattern="^https?://[a-zA-Z0-9\\-\\.]+", description="서비스 URL"
        )
        region: str = Field(default="us-central1", description="서비스 리전")
        project_id: str = Field(
            ..., min_length=1, description="Google Cloud 프로젝트 ID"
        )
        health_check_path: str = Field(default="/health", description="헬스 체크 경로")
        status: ServiceStatus = Field(
            default=ServiceStatus.UNKNOWN, description="서비스 상태"
        )
        last_health_check: datetime | None = Field(
            default=None, description="마지막 헬스 체크 시간"
        )
        response_time_ms: float = Field(
            default=0.0, ge=0.0, description="평균 응답 시간 (밀리초)"
        )
        error_rate: float = Field(
            default=0.0, ge=0.0, le=1.0, description="에러율 (0-1)"
        )
        active_connections: int = Field(default=0, ge=0, description="활성 연결 수")
        weight: float = Field(
            default=1.0, ge=0.0, le=1.0, description="로드 밸런싱 가중치"
        )

        @field_validator("url")
        @classmethod
        def validate_url(cls, v: str) -> str:
            """URL 검증"""
            if not v.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            return v.strip()

        def is_healthy(self) -> bool:
            """서비스 건강 상태 확인"""
            return self.status == ServiceStatus.HEALTHY

        def update_metrics(self, response_time: float, success: bool) -> None:
            """메트릭 업데이트"""
            alpha = 0.1
            self.response_time_ms = (
                1 - alpha
            ) * self.response_time_ms + alpha * response_time
            if not success:
                self.error_rate = (1 - alpha) * self.error_rate + alpha * 1.0
            else:
                self.error_rate = (1 - alpha) * self.error_rate + alpha * 0.0

else:

    @dataclass
    class ServiceEndpoint:
        """서비스 엔드포인트 정보 (Fallback)"""

        service_name: str
        url: str
        project_id: str
        region = "us-central1"
        health_check_path = "/health"
        status: ServiceStatus = ServiceStatus.UNKNOWN
        last_health_check = None
        response_time_ms: float = 0.0
        error_rate: float = 0.0
        active_connections = 0
        weight: float = 1.0

        def is_healthy(self) -> bool:
            return self.status == ServiceStatus.HEALTHY

        def update_metrics(self, response_time: float, success: bool) -> None:
            alpha = 0.1
            self.response_time_ms = (
                1 - alpha
            ) * self.response_time_ms + alpha * response_time
            if not success:
                self.error_rate = (1 - alpha) * self.error_rate + alpha * 1.0
            else:
                self.error_rate = (1 - alpha) * self.error_rate + alpha * 0.0


class CircuitBreakerState(str, Enum):
    """회로 차단기 상태"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """회로 차단기 구현"""

    failure_threshold = 5
    recovery_timeout = 60
    success_threshold = 2

    def __post_init__(self):
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def call(self, func: Callable) -> Any:
        """회로 차단기를 통한 함수 호출"""
        match self.state:
            case CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("회로 차단기 복구 시도 모드로 전환")
                else:
                    raise Exception("Circuit breaker is OPEN")
            case CircuitBreakerState.HALF_OPEN:
                if self.success_count >= self.success_threshold:
                    self._reset()
                    logger.info("회로 차단기 복구 완료")
                try:
                    result = func()
                    self._on_success()
                    return result
                except Exception as e:
                    self._on_failure()
                    raise

    def _should_attempt_reset(self) -> bool:
        """복구 시도 여부 확인"""
        if self.last_failure_time is None:
            return True
        return datetime.now() - self.last_failure_time > timedelta(
            seconds=self.recovery_timeout
        )

    def _on_success(self) -> None:
        """성공 시 처리"""
        match self.state:
            case CircuitBreakerState.HALF_OPEN:
                success_count = success_count + 1
            case _:
                self._reset()

    def _on_failure(self) -> None:
        """실패 시 처리"""
        self.failure_count = self.failure_count + 1
        self.last_failure_time = datetime.now()
        match self.state:
            case CircuitBreakerState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
                    logger.warning("회로 차단기가 OPEN 상태로 전환되었습니다")
            case CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                self.success_count = 0
                logger.warning("회로 차단기 복구 실패, OPEN 상태로 전환")

    def _reset(self) -> None:
        """회로 차단기 초기화"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0


class CloudRunServiceDiscovery:
    """Cloud Run 서비스 검색 및 관리"""

    def __init__(
        self,
        project_id: str,
        region="us-central1",
        health_check_interval=30,
    ):
        self.project_id = project_id
        self.region = region
        self.health_check_interval = health_check_interval
        self.services = {}
        self.circuit_breakers = {}
        self.session = None
        self.cloud_run_client = None
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                credentials, _ = google_auth_default()
                self.cloud_run_client = run_v2.ServicesClient(credentials=credentials)
            except Exception as e:
                logger.warning(f"Cloud Run 클라이언트 초기화 실패: {e}")
        self.health_check_task = None

    async def initialize(self):
        """서비스 검색 초기화"""
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        self.session = aiohttp.ClientSession(timeout=timeout)
        if self.cloud_run_client:
            await self._discover_services()
        self.health_check_task = asyncio.create_task(self._health_check_scheduler())
        logger.info("Cloud Run 서비스 검색이 초기화되었습니다")

    async def _discover_services(self):
        """Cloud Run 서비스 자동 검색"""
        if not GOOGLE_CLOUD_AVAILABLE or not self.cloud_run_client:
            logger.warning("Google Cloud 클라이언트를 사용할 수 없습니다")
            return
        try:
            parent = f"projects/{self.project_id}/locations/{self.region}"
            services = self.cloud_run_client.list_services(parent=parent)
            discovered_count = 0
            for service in services:
                service_name = service.name.split("/")[-1]
                service_url = service.uri
                if service_url and service_name not in self.services:
                    endpoint = ServiceEndpoint(
                        service_name=service_name,
                        url=service_url,
                        project_id=self.project_id,
                        region=self.region,
                    )
                    self.services = {**self.services, service_name: endpoint}
                    self.circuit_breakers = {
                        **self.circuit_breakers,
                        service_name: CircuitBreaker(),
                    }
                    discovered_count = discovered_count + 1
                    logger.info(f"서비스 발견: {service_name} -> {service_url}")
            logger.info(f"총 {discovered_count}개 서비스를 발견했습니다")
        except Exception as e:
            logger.error(f"서비스 검색 중 오류: {e}")

    def register_service(self, endpoint: ServiceEndpoint) -> Result[None, str]:
        """서비스 수동 등록"""
        try:
            if endpoint.service_name in self.services:
                return Failure(
                    f"서비스 '{endpoint.service_name}'이 이미 등록되어 있습니다"
                )
            self.services = {**self.services, endpoint.service_name: endpoint}
            self.circuit_breakers = {
                **self.circuit_breakers,
                endpoint.service_name: CircuitBreaker(),
            }
            logger.info(f"서비스 등록 완료: {endpoint.service_name}")
            return Success(None)
        except Exception as e:
            return Failure(f"서비스 등록 실패: {str(e)}")

    def get_service(self, service_name: str) -> Maybe[ServiceEndpoint]:
        """서비스 조회"""
        if service_name in self.services:
            return Maybe.some(self.services[service_name])
        return Maybe.none()

    def get_healthy_services(self) -> List[ServiceEndpoint]:
        """건강한 서비스 목록 조회"""
        return [svc for svc in self.services.values() if svc.is_healthy()]

    async def health_check(self, service_name: str) -> Result[bool, str]:
        """개별 서비스 헬스 체크"""
        if service_name not in self.services:
            return Failure(f"서비스 '{service_name}'을 찾을 수 없습니다")
        service = self.services[service_name]
        health_url = f"{service.url.rstrip('/')}{service.health_check_path}"
        try:
            start_time = time.time()
            async with self.session.get(health_url) as response:
                response_time = (time.time() - start_time) * 1000
                success = response.status == 200
                service.update_metrics(response_time, success)
                service.last_health_check = datetime.now()
                if success:
                    service.status = ServiceStatus.HEALTHY
                    return Success(True)
                else:
                    service.status = ServiceStatus.UNHEALTHY
                    return Failure(f"헬스 체크 실패: HTTP {response.status}")
        except asyncio.TimeoutError:
            service.status = ServiceStatus.UNHEALTHY
            service.update_metrics(10000, False)
            return Failure("헬스 체크 타임아웃")
        except Exception as e:
            service.status = ServiceStatus.UNHEALTHY
            service.update_metrics(10000, False)
            return Failure(f"헬스 체크 오류: {str(e)}")

    async def _health_check_scheduler(self):
        """정기적 헬스 체크 실행"""
        while True:
            try:
                tasks = []
                for service_name in self.services.keys():
                    task = asyncio.create_task(self.health_check(service_name))
                    tasks = tasks + [(service_name, task)]
                for service_name, task in tasks:
                    try:
                        result = await task
                        match result:
                            case Success(_):
                                logger.debug(f"헬스 체크 성공: {service_name}")
                            case Failure(error):
                                logger.warning(
                                    f"헬스 체크 실패: {service_name} - {error}"
                                )
                    except Exception as e:
                        logger.error(f"헬스 체크 태스크 오류: {service_name} - {e}")
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"헬스 체크 스케줄러 오류: {e}")
                await asyncio.sleep(self.health_check_interval)

    async def call_service(
        self,
        service_name: str,
        path="/",
        method="GET",
        data=None,
        headers=None,
    ) -> Result[Dict[str, Any], str]:
        """회로 차단기를 통한 안전한 서비스 호출"""
        if service_name not in self.services:
            return Failure(f"서비스 '{service_name}'을 찾을 수 없습니다")
        service = self.services[service_name]
        circuit_breaker = self.circuit_breakers[service_name]
        if not service.is_healthy():
            return Failure(f"서비스 '{service_name}'이 비정상 상태입니다")
        try:
            result = circuit_breaker.call(
                lambda: self._make_http_request(service, path, method, data, headers)
            )
            return await result
        except Exception as e:
            return Failure(f"서비스 호출 실패: {str(e)}")

    async def _make_http_request(
        self,
        service: ServiceEndpoint,
        path: str,
        method: str,
        data: Any,
        headers: Optional[Dict[str, str]],
    ) -> Result[Dict[str, Any], str]:
        """실제 HTTP 요청 수행"""
        url = f"{service.url.rstrip('/')}/{path.lstrip('/')}"
        request_headers = headers or {}
        service.active_connections = service.active_connections + 1
        try:
            start_time = time.time()
            match method.upper():
                case "GET":
                    async with self.session.get(
                        url, headers=request_headers
                    ) as response:
                        response_time = (time.time() - start_time) * 1000
                        service.update_metrics(response_time, response.status < 400)
                        if response.status < 400:
                            result = await response.json()
                            return Success(result)
                        else:
                            error_text = await response.text()
                            return Failure(f"HTTP {response.status}: {error_text}")
                case "POST" | "PUT" | "PATCH":
                    json_data = json.dumps(data) if data else None
                    if json_data:
                        request_headers = {
                            **request_headers,
                            "Content-Type": "application/json",
                        }
                    async with self.session.request(
                        method, url, data=json_data, headers=request_headers
                    ) as response:
                        response_time = (time.time() - start_time) * 1000
                        service.update_metrics(response_time, response.status < 400)
                        if response.status < 400:
                            result = await response.json()
                            return Success(result)
                        else:
                            error_text = await response.text()
                            return Failure(f"HTTP {response.status}: {error_text}")
                case _:
                    return Failure(f"지원하지 않는 HTTP 메서드: {method}")
        except Exception as e:
            service.update_metrics(10000, False)
            return Failure(f"HTTP 요청 오류: {str(e)}")
        finally:
            service.active_connections = service.active_connections - 1

    def get_load_balanced_service(
        self,
        service_names: List[str],
        strategy=LoadBalancingStrategy.ROUND_ROBIN,
    ) -> Maybe[ServiceEndpoint]:
        """로드 밸런싱된 서비스 선택"""
        healthy_services = [
            self.services[name]
            for name in service_names
            if name in self.services and self.services[name].is_healthy()
        ]
        if not healthy_services:
            return Maybe.none()
        match strategy:
            case LoadBalancingStrategy.ROUND_ROBIN:
                import random

                selected = random.choice(healthy_services)
                return Maybe.some(selected)
            case LoadBalancingStrategy.WEIGHTED:
                weights = [svc.weight for svc in healthy_services]
                selected = self._weighted_choice(healthy_services, weights)
                return Maybe.some(selected)
            case LoadBalancingStrategy.LEAST_CONNECTIONS:
                selected = min(healthy_services, key=lambda x: x.active_connections)
                return Maybe.some(selected)
            case LoadBalancingStrategy.RANDOM:
                import random

                selected = random.choice(healthy_services)
                return Maybe.some(selected)
            case _:
                return Maybe.some(healthy_services[0])

    def _weighted_choice(
        self, services: List[ServiceEndpoint], weights: List[float]
    ) -> ServiceEndpoint:
        """가중치 기반 선택"""
        import random

        total = sum(weights)
        r = random.uniform(0, total)
        upto = 0
        for service, weight in zip(services, weights):
            if upto + weight >= r:
                return service
            upto = upto + weight
        return services[-1]

    async def shutdown(self):
        """서비스 검색 종료"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        if self.session:
            await self.session.close()
        logger.info("Cloud Run 서비스 검색이 종료되었습니다")

    def get_service_stats(self) -> Dict[str, Any]:
        """서비스 통계 조회"""
        total_services = len(self.services)
        healthy_services = len(self.get_healthy_services())
        avg_response_time = 0.0
        avg_error_rate = 0.0
        if self.services:
            avg_response_time = (
                sum((svc.response_time_ms for svc in self.services.values()))
                / total_services
            )
            avg_error_rate = (
                sum((svc.error_rate for svc in self.services.values())) / total_services
            )
        return {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "unhealthy_services": total_services - healthy_services,
            "health_rate": healthy_services / max(total_services, 1),
            "avg_response_time_ms": avg_response_time,
            "avg_error_rate": avg_error_rate,
            "circuit_breakers": {
                name: cb.state.value for name, cb in self.circuit_breakers.items()
            },
        }


_service_discovery = None


async def get_service_discovery(
    project_id: str = None, region="us-central1"
) -> CloudRunServiceDiscovery:
    """서비스 검색 인스턴스 획득"""
    # global _service_discovery - removed for functional programming
    if _service_discovery is None:
        if project_id is None:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get(
                "GCP_PROJECT"
            )
        if not project_id:
            raise ValueError(
                "프로젝트 ID가 필요합니다. 환경 변수 GOOGLE_CLOUD_PROJECT 또는 매개변수로 설정하세요."
            )
        _service_discovery = CloudRunServiceDiscovery(project_id, region)
        await _service_discovery.initialize()
    return _service_discovery


@dataclass
class ServiceQuery:
    """서비스 검색 쿼리"""

    service_name = None
    version = None
    region = None
    tags: Optional[List[str]] = None
    only_healthy = True
    min_weight: float = 0.0
    max_response_time_ms = None

    def matches(self, endpoint: ServiceEndpoint) -> bool:
        """엔드포인트가 쿼리와 일치하는지 확인"""
        if self.service_name and endpoint.service_name != self.service_name:
            return False
        if self.region and endpoint.region != self.region:
            return False
        if self.only_healthy and (not endpoint.is_healthy()):
            return False
        if endpoint.weight < self.min_weight:
            return False
        if (
            self.max_response_time_ms is not None
            and endpoint.response_time_ms > self.max_response_time_ms
        ):
            return False
        return True


class EnhancedServiceDiscovery(CloudRunServiceDiscovery):
    """향상된 서비스 검색"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_groups: Dict[str, List[str]] = {}
        self.round_robin_counters = {}
        self.sticky_sessions = {}
        self.call_metrics: Dict[str, List[float]] = {}
        self.success_rates = {}
        self.service_cache = {}
        self.cache_ttl = 300

    def create_service_group(self, group_name: str, service_names: List[str]) -> None:
        """서비스 그룹 생성"""
        self.service_groups = {**self.service_groups, group_name: service_names}
        logger.info(f"서비스 그룹 생성: {group_name} -> {service_names}")

    def query_services(self, query: ServiceQuery) -> List[ServiceEndpoint]:
        """고급 서비스 검색"""
        results = []
        for service in self.services.values():
            if query.matches(service):
                results = results + [service]
        results.sort(key=lambda s: (s.response_time_ms, -s.weight))
        return results

    async def call_service_with_retry(
        self,
        service_name: str,
        path="/",
        method="GET",
        max_retries=3,
        retry_delay=1.0,
        **kwargs,
    ) -> Result[Dict[str, Any], str]:
        """재시도 지원 서비스 호출"""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = await self.call_service(service_name, path, method, **kwargs)
                if result.is_success():
                    self._record_call_success(service_name)
                    return result
                else:
                    last_error = result.error
            except Exception as e:
                last_error = str(e)
            if attempt < max_retries:
                await asyncio.sleep(retry_delay * 2**attempt)
                logger.warning(
                    f"서비스 호출 재시도 {attempt + 1}/{max_retries}: {service_name}"
                )
        self._record_call_failure(service_name)
        return Failure(f"서비스 호출 실패 (최대 재시도 초과): {last_error}")

    def _record_call_success(self, service_name: str) -> None:
        """호출 성공 기록"""
        if service_name not in self.success_rates:
            self.success_rates = {**self.success_rates, service_name: 1.0}
        else:
            alpha = 0.1
            self.success_rates = {
                **self.success_rates,
                service_name: (1 - alpha) * self.success_rates[service_name]
                + alpha * 1.0,
            }

    def _record_call_failure(self, service_name: str) -> None:
        """호출 실패 기록"""
        if service_name not in self.success_rates:
            self.success_rates = {**self.success_rates, service_name: 0.0}
        else:
            alpha = 0.1
            self.success_rates = {
                **self.success_rates,
                service_name: (1 - alpha) * self.success_rates[service_name]
                + alpha * 0.0,
            }

    async def call_service_group(
        self,
        group_name: str,
        path="/",
        method="GET",
        strategy=LoadBalancingStrategy.ROUND_ROBIN,
        **kwargs,
    ) -> Result[Dict[str, Any], str]:
        """서비스 그룹 호출"""
        if group_name not in self.service_groups:
            return Failure(f"서비스 그룹을 찾을 수 없습니다: {group_name}")
        service_names = self.service_groups[group_name]
        selected_service = self.get_load_balanced_service(service_names, strategy)
        if selected_service.is_none():
            return Failure(f"서비스 그룹에 사용 가능한 서비스가 없습니다: {group_name}")
        service = selected_service.unwrap()
        return await self.call_service(service.service_name, path, method, **kwargs)

    def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """서비스 메트릭 조회"""
        if service_name not in self.services:
            return {}
        service = self.services[service_name]
        circuit_breaker = self.circuit_breakers.get(service_name)
        return {
            "service_name": service_name,
            "status": service.status.value,
            "response_time_ms": service.response_time_ms,
            "error_rate": service.error_rate,
            "active_connections": service.active_connections,
            "weight": service.weight,
            "success_rate": self.success_rates.get(service_name, 0.0),
            "circuit_breaker_state": (
                circuit_breaker.state.value if circuit_breaker else "unknown"
            ),
            "last_health_check": (
                service.last_health_check.isoformat()
                if service.last_health_check
                else None
            ),
        }

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """종합 통계 조회"""
        base_stats = self.get_service_stats()
        total_calls = sum((len(metrics) for metrics in self.call_metrics.values()))
        avg_success_rate = sum(self.success_rates.values()) / max(
            len(self.success_rates), 1
        )
        enhanced_stats = {
            **base_stats,
            "total_calls": total_calls,
            "avg_success_rate": avg_success_rate,
            "service_groups": len(self.service_groups),
            "cached_items": len(self.service_cache),
        }
        return enhanced_stats


async def discover_services() -> List[ServiceEndpoint]:
    """서비스 자동 검색"""
    discovery = await get_service_discovery()
    return list(discovery.services.values())


async def call_service(
    service_name: str, path="/", **kwargs
) -> Result[Dict[str, Any], str]:
    """서비스 호출"""
    discovery = await get_service_discovery()
    return await discovery.call_service(service_name, path, **kwargs)


async def health_check_all() -> Dict[str, bool]:
    """모든 서비스 헬스 체크"""
    discovery = await get_service_discovery()
    results = {}
    for service_name in discovery.services.keys():
        result = await discovery.health_check(service_name)
        match result:
            case Success(_):
                results = {**results, service_name: True}
            case Failure(_):
                results = {**results, service_name: False}
    return results


async def get_enhanced_service_discovery(
    project_id: str = None, region="us-central1"
) -> EnhancedServiceDiscovery:
    """향상된 서비스 검색 인스턴스 획득"""
    if project_id is None:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get(
            "GCP_PROJECT"
        )
    if not project_id:
        raise ValueError("프로젝트 ID가 필요합니다.")
    discovery = EnhancedServiceDiscovery(project_id, region)
    await discovery.initialize()
    return discovery


async def find_services(query: ServiceQuery) -> List[ServiceEndpoint]:
    """고급 서비스 검색"""
    discovery = await get_enhanced_service_discovery()
    return discovery.query_services(query)


async def call_service_safely(
    service_name: str, path="/", max_retries=3, **kwargs
) -> Result[Dict[str, Any], str]:
    """안전한 서비스 호출 (재시도 지원)"""
    discovery = await get_enhanced_service_discovery()
    return await discovery.call_service_with_retry(
        service_name, path, max_retries=max_retries, **kwargs
    )
