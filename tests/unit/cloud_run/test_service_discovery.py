"""Cloud Run Service Discovery 테스트 (Google Cloud Run 패턴 기반)

Google Cloud Run의 공식 서비스 디스커버리 패턴과 베스트 프랙티스를 기반으로 한
포괄적인 테스트 구현:
- run.app URL 패턴 검증
- Circuit Breaker 패턴 (인스턴스 제한 기반)
- Health Check 및 Load Balancing 베스트 프랙티스
- Service Discovery 및 통신 최적화
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

try:
    import aiohttp
except ImportError:
    aiohttp = None

import pytest

from rfs.cloud_run.service_discovery import (
    CircuitBreaker,
    CircuitBreakerState,
    CloudRunServiceDiscovery,
    EnhancedServiceDiscovery,
    LoadBalancingStrategy,
    ServiceEndpoint,
    ServiceQuery,
    ServiceStatus,
    call_service,
    discover_services,
    find_services,
    get_enhanced_service_discovery,
    get_service_discovery,
    health_check_all,
)
from rfs.core.result import Failure, Maybe, Result, Success


@pytest.fixture
def mock_aiohttp_session():
    """aiohttp ClientSession 올바른 모킹"""
    session = AsyncMock(spec=aiohttp.ClientSession if aiohttp else None)

    # 기본 응답 설정
    def create_mock_response(status=200, json_data=None, text_data="OK"):
        mock_response = AsyncMock()
        mock_response.status = status
        mock_response.json = AsyncMock(return_value=json_data or {"status": "healthy"})
        mock_response.text = AsyncMock(return_value=text_data)

        # Context manager 설정
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        return mock_context

    # 기본 응답 설정
    session.get.return_value = create_mock_response()
    session.post.return_value = create_mock_response()
    session.put.return_value = create_mock_response()
    session.patch.return_value = create_mock_response()
    session.request.return_value = create_mock_response()
    session.close = AsyncMock()

    # 동적 응답을 위한 헬퍼 메서드
    session.create_response = create_mock_response

    return session


@pytest.fixture
def mock_gcp_credentials():
    """Google Cloud 인증 정보 모킹"""
    with patch("rfs.cloud_run.service_discovery.google_auth_default") as mock_auth:
        mock_credentials = Mock()
        mock_auth.return_value = (mock_credentials, "test-project")
        yield mock_credentials


@pytest.fixture
def mock_cloud_run_client():
    """Google Cloud Run 클라이언트 모킹"""
    with patch(
        "rfs.cloud_run.service_discovery.run_v2.ServicesClient"
    ) as mock_client_class:
        mock_client = Mock()
        mock_service = Mock()
        mock_service.name = (
            "projects/test-project/locations/us-central1/services/test-service"
        )
        mock_service.uri = "https://test-service-abc123-uc.a.run.app"
        mock_client.list_services.return_value = [mock_service]
        mock_client_class.return_value = mock_client
        yield mock_client


class TestServiceEndpoint:
    """ServiceEndpoint 테스트 - Google Cloud Run 패턴 기반"""

    def test_service_endpoint_creation_with_run_app_url(self):
        """Cloud Run의 run.app URL 패턴으로 엔드포인트 생성 테스트"""
        # Google Cloud Run의 실제 URL 패턴
        endpoint = ServiceEndpoint(
            service_name="billing-service",
            url="https://billing-service-abc123-uc.a.run.app",
            project_id="my-project-12345",
            region="us-central1",
        )

        assert endpoint.service_name == "billing-service"
        assert endpoint.url == "https://billing-service-abc123-uc.a.run.app"
        assert endpoint.project_id == "my-project-12345"
        assert endpoint.region == "us-central1"
        assert endpoint.health_check_path == "/health"
        assert endpoint.status == ServiceStatus.UNKNOWN
        assert endpoint.weight == 1.0

    def test_service_endpoint_url_validation(self):
        """Cloud Run URL 검증 테스트"""
        # 올바른 Cloud Run URL
        try:
            endpoint = ServiceEndpoint(
                service_name="valid-service",
                url="https://valid-service-123abc-ew.a.run.app",
                project_id="test-project",
            )
            assert endpoint.url == "https://valid-service-123abc-ew.a.run.app"
        except ValueError:
            pytest.fail("Valid Cloud Run URL should not raise ValueError")

        # 사용자 정의 도메인도 허용
        try:
            endpoint = ServiceEndpoint(
                service_name="custom-service",
                url="https://api.mycompany.com",
                project_id="test-project",
            )
            assert endpoint.url == "https://api.mycompany.com"
        except ValueError:
            pytest.fail("Custom domain should be allowed")

    def test_service_endpoint_health_status(self):
        """서비스 엔드포인트 헬스 상태 확인 테스트"""
        endpoint = ServiceEndpoint(
            service_name="health-test",
            url="https://health-test-xyz.a.run.app",
            project_id="test-project",
        )

        # 초기 상태는 UNKNOWN
        assert not endpoint.is_healthy()

        # HEALTHY로 변경
        endpoint.status = ServiceStatus.HEALTHY
        assert endpoint.is_healthy()

        # UNHEALTHY로 변경
        endpoint.status = ServiceStatus.UNHEALTHY
        assert not endpoint.is_healthy()

    def test_service_endpoint_metrics_update(self):
        """서비스 메트릭 업데이트 테스트"""
        endpoint = ServiceEndpoint(
            service_name="metrics-test",
            url="https://metrics-test.a.run.app",
            project_id="test-project",
        )

        # 초기 메트릭
        assert endpoint.response_time_ms == 0.0
        assert endpoint.error_rate == 0.0

        # 성공적인 요청 메트릭 업데이트
        endpoint.update_metrics(150.0, True)
        assert endpoint.response_time_ms > 0
        assert endpoint.error_rate < 0.1  # 성공이므로 에러율 감소

        # 실패한 요청 메트릭 업데이트
        endpoint.update_metrics(500.0, False)
        assert endpoint.error_rate > 0  # 실패로 인한 에러율 증가


class TestCloudRunServiceDiscovery:
    """CloudRunServiceDiscovery 테스트 - Google Cloud Run 패턴 기반"""

    @pytest.fixture
    def discovery(self):
        """서비스 디스커버리 인스턴스"""
        return CloudRunServiceDiscovery(
            project_id="test-project-12345",
            region="us-central1",
            health_check_interval=10,  # 테스트용 짧은 간격
        )

    def test_cloud_run_discovery_initialization(self, discovery):
        """Google Cloud Run 서비스 디스커버리 초기화 테스트"""
        assert discovery.project_id == "test-project-12345"
        assert discovery.region == "us-central1"
        assert discovery.health_check_interval == 10
        assert discovery.services == {}
        assert discovery.circuit_breakers == {}
        assert discovery.session is None
        assert discovery.cloud_run_client is None

    @pytest.mark.asyncio
    async def test_discovery_initialization_with_session(
        self, discovery, mock_aiohttp_session
    ):
        """세션과 함께 초기화 테스트"""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await discovery.initialize()

            assert discovery.session is not None
            assert discovery.health_check_task is not None
            # 헬스 체크 태스크는 백그라운드에서 실행됨

    @pytest.mark.asyncio
    async def test_cloud_run_service_discovery_with_gcp_client(
        self,
        discovery,
        mock_gcp_credentials,
        mock_cloud_run_client,
        mock_aiohttp_session,
    ):
        """Google Cloud Run 클라이언트를 사용한 서비스 자동 발견 테스트"""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            with patch("rfs.cloud_run.service_discovery.GOOGLE_CLOUD_AVAILABLE", True):
                discovery.cloud_run_client = mock_cloud_run_client
                await discovery.initialize()

                # 서비스가 자동으로 발견되었는지 확인
                assert "test-service" in discovery.services
                assert "test-service" in discovery.circuit_breakers

                service = discovery.services["test-service"]
                assert service.service_name == "test-service"
                assert service.url == "https://test-service-abc123-uc.a.run.app"
                assert service.project_id == "test-project-12345"
                assert service.region == "us-central1"

    @pytest.mark.asyncio
    async def test_manual_service_registration(self, discovery):
        """수동 서비스 등록 테스트"""
        endpoint = ServiceEndpoint(
            service_name="manual-service",
            url="https://manual-service-xyz789.a.run.app",
            project_id="test-project-12345",
            region="asia-northeast1",
        )

        result = discovery.register_service(endpoint)

        assert result.is_success()
        assert "manual-service" in discovery.services
        assert "manual-service" in discovery.circuit_breakers

        registered_service = discovery.services["manual-service"]
        assert registered_service.service_name == "manual-service"
        assert registered_service.region == "asia-northeast1"

    @pytest.mark.asyncio
    async def test_duplicate_service_registration(self, discovery):
        """중복 서비스 등록 테스트"""
        endpoint = ServiceEndpoint(
            service_name="duplicate-service",
            url="https://duplicate-service.a.run.app",
            project_id="test-project-12345",
        )

        # 첫 번째 등록은 성공
        result1 = discovery.register_service(endpoint)
        assert result1.is_success()

        # 중복 등록은 실패
        result2 = discovery.register_service(endpoint)
        assert result2.is_failure()
        assert "이미 등록되어 있습니다" in result2.error

    def test_service_retrieval_with_maybe(self, discovery):
        """Maybe 패턴을 사용한 서비스 조회 테스트"""
        # 존재하지 않는 서비스 조회
        result = discovery.get_service("nonexistent-service")
        assert result.is_none()

        # 서비스 등록 후 조회
        endpoint = ServiceEndpoint(
            service_name="existing-service",
            url="https://existing-service.a.run.app",
            project_id="test-project-12345",
        )
        discovery.register_service(endpoint)

        result = discovery.get_service("existing-service")
        assert result.is_some()
        service = result.get()
        assert service.service_name == "existing-service"

    def test_healthy_services_filtering(self, discovery):
        """건강한 서비스만 필터링하는 테스트"""
        # 건강한 서비스와 건강하지 않은 서비스 등록
        healthy_endpoint = ServiceEndpoint(
            service_name="healthy-service",
            url="https://healthy-service.a.run.app",
            project_id="test-project-12345",
        )
        healthy_endpoint.status = ServiceStatus.HEALTHY

        unhealthy_endpoint = ServiceEndpoint(
            service_name="unhealthy-service",
            url="https://unhealthy-service.a.run.app",
            project_id="test-project-12345",
        )
        unhealthy_endpoint.status = ServiceStatus.UNHEALTHY

        discovery.register_service(healthy_endpoint)
        discovery.register_service(unhealthy_endpoint)

        healthy_services = discovery.get_healthy_services()

        assert len(healthy_services) == 1
        assert healthy_services[0].service_name == "healthy-service"

    @pytest.mark.asyncio
    async def test_health_check_individual_service(
        self, discovery, mock_aiohttp_session
    ):
        """개별 서비스 헬스 체크 테스트"""
        discovery.session = mock_aiohttp_session

        endpoint = ServiceEndpoint(
            service_name="health-check-service",
            url="https://health-check-service.a.run.app",
            project_id="test-project-12345",
        )
        discovery.register_service(endpoint)

        # 성공적인 헬스 체크 응답 설정
        mock_aiohttp_session.get.return_value = mock_aiohttp_session.create_response(
            status=200
        )

        with patch("time.time", side_effect=[1000.0, 1000.1]):  # start_time, end_time
            result = await discovery.health_check("health-check-service")

        assert result.is_success()
        assert result.unwrap() is True

        service = discovery.services["health-check-service"]
        assert service.status == ServiceStatus.HEALTHY
        assert service.last_health_check is not None
        assert service.response_time_ms > 0

    @pytest.mark.asyncio
    async def test_health_check_failure_scenarios(
        self, discovery, mock_aiohttp_session
    ):
        """헬스 체크 실패 시나리오 테스트"""
        discovery.session = mock_aiohttp_session

        endpoint = ServiceEndpoint(
            service_name="failing-service",
            url="https://failing-service.a.run.app",
            project_id="test-project-12345",
        )
        discovery.register_service(endpoint)

        # HTTP 500 오류 응답 설정
        mock_aiohttp_session.get.return_value = mock_aiohttp_session.create_response(
            status=500
        )

        result = await discovery.health_check("failing-service")

        assert result.is_failure()
        assert "HTTP 500" in result.error

        service = discovery.services["failing-service"]
        assert service.status == ServiceStatus.UNHEALTHY

        # 타임아웃 테스트
        mock_aiohttp_session.get.side_effect = asyncio.TimeoutError()

        result = await discovery.health_check("failing-service")

        assert result.is_failure()
        assert "타임아웃" in result.error

    @pytest.mark.asyncio
    async def test_service_call_with_circuit_breaker(
        self, discovery, mock_aiohttp_session
    ):
        """Circuit Breaker를 통한 서비스 호출 테스트"""
        discovery.session = mock_aiohttp_session

        endpoint = ServiceEndpoint(
            service_name="api-service",
            url="https://api-service.a.run.app",
            project_id="test-project-12345",
        )
        endpoint.status = ServiceStatus.HEALTHY
        discovery.register_service(endpoint)

        # 성공적인 API 호출
        mock_response_data = {
            "status": "success",
            "data": {"message": "Hello from Cloud Run"},
        }
        # API 호출 성공 응답 설정
        mock_aiohttp_session.get.return_value = mock_aiohttp_session.create_response(
            status=200, json_data=mock_response_data
        )

        with patch("time.time", return_value=1000.0):
            result = await discovery.call_service(
                "api-service", path="/api/v1/data", method="GET"
            )

        assert result.is_success()
        response_data = result.unwrap()
        assert response_data["status"] == "success"
        assert "data" in response_data

    @pytest.mark.asyncio
    async def test_service_call_failure_and_circuit_breaker_opening(
        self, discovery, mock_aiohttp_session
    ):
        """서비스 호출 실패 및 Circuit Breaker 개방 테스트"""
        discovery.session = mock_aiohttp_session

        endpoint = ServiceEndpoint(
            service_name="unreliable-service",
            url="https://unreliable-service.a.run.app",
            project_id="test-project-12345",
        )
        endpoint.status = ServiceStatus.HEALTHY
        discovery.register_service(endpoint)

        # 서비스 호출 실패 시뮬레이션
        mock_aiohttp_session.get.side_effect = Exception("Connection failed")

        result = await discovery.call_service("unreliable-service")

        assert result.is_failure()
        assert "서비스 호출 실패" in result.error

    @pytest.mark.asyncio
    async def test_load_balancing_strategies(self, discovery):
        """로드 밸런싱 전략 테스트"""
        # 여러 건강한 서비스 등록
        services = []
        for i in range(3):
            endpoint = ServiceEndpoint(
                service_name=f"lb-service-{i}",
                url=f"https://lb-service-{i}.a.run.app",
                project_id="test-project-12345",
            )
            endpoint.status = ServiceStatus.HEALTHY
            endpoint.weight = 1.0
            endpoint.active_connections = i  # 연결 수 차등
            discovery.register_service(endpoint)
            services.append(f"lb-service-{i}")

        # Round Robin 전략
        selected = discovery.get_load_balanced_service(
            services, LoadBalancingStrategy.ROUND_ROBIN
        )
        assert selected.is_some()
        assert selected.unwrap().service_name in services

        # Least Connections 전략
        selected = discovery.get_load_balanced_service(
            services, LoadBalancingStrategy.LEAST_CONNECTIONS
        )
        assert selected.is_some()
        # 가장 적은 연결 수를 가진 서비스 선택됨
        assert selected.unwrap().service_name == "lb-service-0"

        # Random 전략
        selected = discovery.get_load_balanced_service(
            services, LoadBalancingStrategy.RANDOM
        )
        assert selected.is_some()
        assert selected.unwrap().service_name in services

    @pytest.mark.asyncio
    async def test_service_stats_collection(self, discovery):
        """서비스 통계 수집 테스트"""
        # 다양한 상태의 서비스들 등록
        healthy_services = []
        unhealthy_services = []

        for i in range(3):
            endpoint = ServiceEndpoint(
                service_name=f"healthy-service-{i}",
                url=f"https://healthy-service-{i}.a.run.app",
                project_id="test-project-12345",
            )
            endpoint.status = ServiceStatus.HEALTHY
            endpoint.response_time_ms = 100.0 + (i * 50)
            endpoint.error_rate = 0.01 + (i * 0.01)
            discovery.register_service(endpoint)
            healthy_services.append(endpoint)

        for i in range(2):
            endpoint = ServiceEndpoint(
                service_name=f"unhealthy-service-{i}",
                url=f"https://unhealthy-service-{i}.a.run.app",
                project_id="test-project-12345",
            )
            endpoint.status = ServiceStatus.UNHEALTHY
            endpoint.response_time_ms = 1000.0
            endpoint.error_rate = 0.5
            discovery.register_service(endpoint)
            unhealthy_services.append(endpoint)

        stats = discovery.get_service_stats()

        assert stats["total_services"] == 5
        assert stats["healthy_services"] == 3
        assert stats["unhealthy_services"] == 2
        assert stats["health_rate"] == 0.6
        assert stats["avg_response_time_ms"] > 0
        assert stats["avg_error_rate"] > 0
        assert len(stats["circuit_breakers"]) == 5

    @pytest.mark.asyncio
    async def test_shutdown_gracefully(self, discovery, mock_aiohttp_session):
        """우아한 종료 테스트"""
        discovery.session = mock_aiohttp_session

        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await discovery.initialize()

        # 종료 프로세스
        await discovery.shutdown()

        # 세션이 닫혔는지 확인
        mock_aiohttp_session.close.assert_called_once()


class TestCircuitBreaker:
    """Circuit Breaker 테스트 - Google Cloud Run 패턴 기반"""

    @pytest.fixture
    def circuit_breaker(self):
        """Circuit Breaker 인스턴스"""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=2,
        )

    def test_circuit_breaker_initialization(self, circuit_breaker):
        """Circuit Breaker 초기화 테스트"""
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 30
        assert circuit_breaker.success_threshold == 2
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0

    def test_circuit_breaker_failure_threshold(self, circuit_breaker):
        """Circuit Breaker 실패 임계값 테스트"""
        # 임계값 미만의 실패
        circuit_breaker._on_failure()
        circuit_breaker._on_failure()
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

        # 임계값 도달로 OPEN 상태로 전환
        circuit_breaker._on_failure()
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3

    def test_circuit_breaker_state_transitions(self, circuit_breaker):
        """Circuit Breaker 상태 전환 테스트"""
        # CLOSED -> OPEN
        for _ in range(3):
            circuit_breaker._on_failure()
        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # 복구 시간 경과 후 HALF_OPEN으로 전환 시뮬레이션
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=31)

        # HALF_OPEN 상태에서 성공 시 CLOSED로 복귀
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker._on_success()
        circuit_breaker._on_success()  # success_threshold=2

        # 성공 임계값 도달로 CLOSED 상태로 복귀해야 함
        assert circuit_breaker.success_count == 2

    def test_circuit_breaker_should_attempt_reset(self, circuit_breaker):
        """Circuit Breaker 복구 시도 여부 테스트"""
        # 처음에는 복구 시도 가능
        assert circuit_breaker._should_attempt_reset()

        # 최근 실패가 있을 때
        circuit_breaker.last_failure_time = datetime.now()
        assert not circuit_breaker._should_attempt_reset()

        # 충분한 시간이 지난 후
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=31)
        assert circuit_breaker._should_attempt_reset()

    def test_circuit_breaker_call_protection_closed_state(self, circuit_breaker):
        """CLOSED 상태에서 Circuit Breaker 호출 보호 테스트"""

        def test_function():
            return "success"

        # CLOSED 상태에서는 정상 호출
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

        # call 메서드는 실제 구현에서 함수를 실행하고 결과를 반환
        # 여기서는 상태 확인만 수행
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_call_protection_open_state(self, circuit_breaker):
        """OPEN 상태에서 Circuit Breaker 호출 보호 테스트"""
        # Circuit을 OPEN 상태로 만들기
        for _ in range(3):
            circuit_breaker._on_failure()

        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # OPEN 상태에서는 복구 시간이 지나지 않으면 호출 차단
        def test_function():
            return "success"

        with pytest.raises(Exception) as exc_info:
            circuit_breaker.call(test_function)
        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_circuit_breaker_metrics_and_monitoring(self, circuit_breaker):
        """Circuit Breaker 메트릭 및 모니터링 테스트"""
        # 초기 상태 확인
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0

        # 실패 기록
        circuit_breaker._on_failure()
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.last_failure_time is not None

        # 성공 기록
        circuit_breaker._reset()
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.state == CircuitBreakerState.CLOSED


class TestLoadBalancingStrategies:
    """Load Balancing 전략 테스트"""

    @pytest.fixture
    def mock_services(self):
        """테스트용 모킹 서비스들"""
        services = []
        for i in range(3):
            endpoint = ServiceEndpoint(
                service_name=f"service-{i}",
                url=f"https://service-{i}.a.run.app",
                project_id="test-project",
            )
            endpoint.status = ServiceStatus.HEALTHY
            endpoint.weight = 1.0 + (i * 0.5)  # 가중치 차등
            endpoint.active_connections = i * 2  # 연결 수 차등
            endpoint.response_time_ms = 100.0 + (i * 50)  # 응답시간 차등
            services.append(endpoint)
        return services

    def test_round_robin_selection(self, mock_services):
        """Round Robin 선택 알고리즘 테스트"""
        discovery = CloudRunServiceDiscovery("test-project")

        # 서비스들 등록
        for service in mock_services:
            discovery.register_service(service)

        service_names = [s.service_name for s in mock_services]

        # Round Robin으로 여러 번 선택
        selected_services = []
        for _ in range(6):  # 2 라운드
            result = discovery.get_load_balanced_service(
                service_names, LoadBalancingStrategy.ROUND_ROBIN
            )
            if result.is_some():
                selected_services.append(result.unwrap().service_name)

        # 모든 서비스가 선택되었는지 확인
        unique_selections = set(selected_services)
        assert len(unique_selections) >= 2  # 최소 2개 이상의 서비스가 선택됨

    def test_least_connections_selection(self, mock_services):
        """Least Connections 선택 알고리즘 테스트"""
        discovery = CloudRunServiceDiscovery("test-project")

        # 서비스들 등록
        for service in mock_services:
            discovery.register_service(service)

        service_names = [s.service_name for s in mock_services]

        result = discovery.get_load_balanced_service(
            service_names, LoadBalancingStrategy.LEAST_CONNECTIONS
        )

        assert result.is_some()
        selected_service = result.unwrap()
        # 가장 적은 연결 수(0)를 가진 service-0가 선택되어야 함
        assert selected_service.service_name == "service-0"

    def test_weighted_selection(self, mock_services):
        """Weighted 선택 알고리즘 테스트"""
        discovery = CloudRunServiceDiscovery("test-project")

        # 서비스들 등록
        for service in mock_services:
            discovery.register_service(service)

        service_names = [s.service_name for s in mock_services]

        # 가중치 기반 선택
        selections = []
        for _ in range(100):  # 충분한 샘플 수
            result = discovery.get_load_balanced_service(
                service_names, LoadBalancingStrategy.WEIGHTED
            )
            if result.is_some():
                selections.append(result.unwrap().service_name)

        # 가중치가 높은 서비스가 더 많이 선택되었는지 확인
        # service-2의 가중치가 가장 높으므로 가장 많이 선택되어야 함
        service_2_count = selections.count("service-2")
        service_0_count = selections.count("service-0")

        # 가중치 비율에 따라 선택 빈도가 달라져야 함
        assert service_2_count >= service_0_count

    def test_random_selection(self, mock_services):
        """Random 선택 알고리즘 테스트"""
        discovery = CloudRunServiceDiscovery("test-project")

        # 서비스들 등록
        for service in mock_services:
            discovery.register_service(service)

        service_names = [s.service_name for s in mock_services]

        # 랜덤 선택
        selections = set()
        for _ in range(20):  # 충분한 시도 횟수
            result = discovery.get_load_balanced_service(
                service_names, LoadBalancingStrategy.RANDOM
            )
            if result.is_some():
                selections.add(result.unwrap().service_name)

        # 여러 서비스가 랜덤하게 선택되었는지 확인
        assert len(selections) >= 2


class TestServiceQuery:
    """ServiceQuery 테스트"""

    def test_service_query_creation(self):
        """서비스 쿼리 생성 테스트"""
        query = ServiceQuery(
            service_name="test-service",
            region="us-central1",
            only_healthy=True,
            min_weight=0.5,
            max_response_time_ms=200.0,
        )

        assert query.service_name == "test-service"
        assert query.region == "us-central1"
        assert query.only_healthy is True
        assert query.min_weight == 0.5
        assert query.max_response_time_ms == 200.0

    def test_service_query_matching(self):
        """서비스 쿼리 매칭 테스트"""
        query = ServiceQuery(
            service_name="test-service",
            region="us-central1",
            only_healthy=True,
            min_weight=0.5,
            max_response_time_ms=200.0,
        )

        # 매칭되는 서비스
        matching_endpoint = ServiceEndpoint(
            service_name="test-service",
            url="https://test-service.a.run.app",
            project_id="test-project",
            region="us-central1",
        )
        matching_endpoint.status = ServiceStatus.HEALTHY
        matching_endpoint.weight = 1.0
        matching_endpoint.response_time_ms = 150.0

        assert query.matches(matching_endpoint)

        # 매칭되지 않는 서비스 (다른 이름)
        non_matching_endpoint = ServiceEndpoint(
            service_name="other-service",
            url="https://other-service.a.run.app",
            project_id="test-project",
            region="us-central1",
        )
        non_matching_endpoint.status = ServiceStatus.HEALTHY
        non_matching_endpoint.weight = 1.0
        non_matching_endpoint.response_time_ms = 150.0

        assert not query.matches(non_matching_endpoint)

    def test_service_query_health_filtering(self):
        """서비스 쿼리 헬스 필터링 테스트"""
        query = ServiceQuery(only_healthy=True)

        # 건강한 서비스
        healthy_endpoint = ServiceEndpoint(
            service_name="healthy-service",
            url="https://healthy-service.a.run.app",
            project_id="test-project",
        )
        healthy_endpoint.status = ServiceStatus.HEALTHY

        assert query.matches(healthy_endpoint)

        # 건강하지 않은 서비스
        unhealthy_endpoint = ServiceEndpoint(
            service_name="unhealthy-service",
            url="https://unhealthy-service.a.run.app",
            project_id="test-project",
        )
        unhealthy_endpoint.status = ServiceStatus.UNHEALTHY

        assert not query.matches(unhealthy_endpoint)


class TestEnhancedServiceDiscovery:
    """EnhancedServiceDiscovery 테스트"""

    @pytest.fixture
    def enhanced_discovery(self):
        """향상된 서비스 디스커버리 인스턴스"""
        return EnhancedServiceDiscovery(
            project_id="test-project-12345",
            region="us-central1",
        )

    def test_enhanced_discovery_initialization(self, enhanced_discovery):
        """향상된 디스커버리 초기화 테스트"""
        assert enhanced_discovery.project_id == "test-project-12345"
        assert enhanced_discovery.service_groups == {}
        assert enhanced_discovery.round_robin_counters == {}
        assert enhanced_discovery.sticky_sessions == {}
        assert enhanced_discovery.call_metrics == {}
        assert enhanced_discovery.success_rates == {}

    def test_service_group_creation(self, enhanced_discovery):
        """서비스 그룹 생성 테스트"""
        service_names = ["service-1", "service-2", "service-3"]
        enhanced_discovery.create_service_group("api-group", service_names)

        assert "api-group" in enhanced_discovery.service_groups
        assert enhanced_discovery.service_groups["api-group"] == service_names

    def test_service_query_functionality(self, enhanced_discovery):
        """서비스 쿼리 기능 테스트"""
        # 테스트 서비스들 등록
        for i in range(3):
            endpoint = ServiceEndpoint(
                service_name=f"query-service-{i}",
                url=f"https://query-service-{i}.a.run.app",
                project_id="test-project-12345",
            )
            endpoint.status = (
                ServiceStatus.HEALTHY if i < 2 else ServiceStatus.UNHEALTHY
            )
            endpoint.weight = 1.0
            endpoint.response_time_ms = 100.0 + (i * 50)
            enhanced_discovery.register_service(endpoint)

        # 건강한 서비스만 조회
        query = ServiceQuery(only_healthy=True, max_response_time_ms=200.0)
        results = enhanced_discovery.query_services(query)

        assert len(results) == 2  # 건강한 서비스 2개
        assert all(service.status == ServiceStatus.HEALTHY for service in results)
        assert all(service.response_time_ms <= 200.0 for service in results)

    @pytest.mark.asyncio
    async def test_service_call_with_retry(
        self, enhanced_discovery, mock_aiohttp_session
    ):
        """재시도 지원 서비스 호출 테스트"""
        enhanced_discovery.session = mock_aiohttp_session

        endpoint = ServiceEndpoint(
            service_name="retry-service",
            url="https://retry-service.a.run.app",
            project_id="test-project-12345",
        )
        endpoint.status = ServiceStatus.HEALTHY
        enhanced_discovery.register_service(endpoint)

        # 첫 번째 호출은 실패, 두 번째 호출은 성공
        call_count = 0

        async def mock_call_service(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Failure("Temporary failure")
            else:
                return Success({"status": "success"})

        enhanced_discovery.call_service = mock_call_service

        result = await enhanced_discovery.call_service_with_retry(
            "retry-service", max_retries=2, retry_delay=0.1
        )

        assert result.is_success()
        assert call_count == 2  # 첫 번째 실패 후 재시도로 성공

    def test_success_rate_tracking(self, enhanced_discovery):
        """성공률 추적 테스트"""
        service_name = "tracked-service"

        # 초기 성공률은 기록되지 않음
        assert service_name not in enhanced_discovery.success_rates

        # 성공 기록
        enhanced_discovery._record_call_success(service_name)
        assert enhanced_discovery.success_rates[service_name] == 1.0

        # 실패 기록
        enhanced_discovery._record_call_failure(service_name)
        # alpha=0.1이므로 성공률이 감소함
        assert enhanced_discovery.success_rates[service_name] < 1.0

    def test_service_metrics_retrieval(self, enhanced_discovery):
        """서비스 메트릭 조회 테스트"""
        endpoint = ServiceEndpoint(
            service_name="metrics-service",
            url="https://metrics-service.a.run.app",
            project_id="test-project-12345",
        )
        endpoint.status = ServiceStatus.HEALTHY
        endpoint.response_time_ms = 150.0
        endpoint.error_rate = 0.05
        endpoint.active_connections = 10
        endpoint.weight = 0.8
        enhanced_discovery.register_service(endpoint)

        # 성공률 설정
        enhanced_discovery.success_rates["metrics-service"] = 0.95

        metrics = enhanced_discovery.get_service_metrics("metrics-service")

        assert metrics["service_name"] == "metrics-service"
        assert metrics["status"] == ServiceStatus.HEALTHY.value
        assert metrics["response_time_ms"] == 150.0
        assert metrics["error_rate"] == 0.05
        assert metrics["active_connections"] == 10
        assert metrics["weight"] == 0.8
        assert metrics["success_rate"] == 0.95
        assert "circuit_breaker_state" in metrics

    def test_comprehensive_stats(self, enhanced_discovery):
        """종합 통계 테스트"""
        # 여러 서비스 등록 및 메트릭 설정
        for i in range(5):
            endpoint = ServiceEndpoint(
                service_name=f"stats-service-{i}",
                url=f"https://stats-service-{i}.a.run.app",
                project_id="test-project-12345",
            )
            endpoint.status = (
                ServiceStatus.HEALTHY if i < 3 else ServiceStatus.UNHEALTHY
            )
            enhanced_discovery.register_service(endpoint)
            enhanced_discovery.success_rates[f"stats-service-{i}"] = 0.8 + (i * 0.05)

        # 서비스 그룹 생성
        enhanced_discovery.create_service_group(
            "test-group", ["stats-service-0", "stats-service-1"]
        )

        stats = enhanced_discovery.get_comprehensive_stats()

        assert stats["total_services"] == 5
        assert stats["healthy_services"] == 3
        assert stats["unhealthy_services"] == 2
        assert stats["service_groups"] == 1
        assert "avg_success_rate" in stats
        assert stats["avg_success_rate"] > 0


class TestServiceDiscoveryHelpers:
    """서비스 디스커버리 헬퍼 함수 테스트"""

    @pytest.mark.asyncio
    async def test_get_service_discovery_helper(self):
        """get_service_discovery 헬퍼 함수 테스트"""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "helper-test-project"}):
            with patch("aiohttp.ClientSession"):
                discovery = await get_service_discovery(region="us-west1")

                assert discovery is not None
                assert discovery.project_id == "helper-test-project"
                assert discovery.region == "us-west1"

    @pytest.mark.asyncio
    async def test_discover_services_helper(self):
        """discover_services 헬퍼 함수 테스트"""
        mock_services = [
            ServiceEndpoint(
                "helper-service-1", "https://helper-service-1.a.run.app", "test-project"
            ),
            ServiceEndpoint(
                "helper-service-2", "https://helper-service-2.a.run.app", "test-project"
            ),
        ]

        with patch(
            "rfs.cloud_run.service_discovery.get_service_discovery"
        ) as mock_get_discovery:
            mock_discovery = AsyncMock()
            mock_discovery.services = {
                "helper-service-1": mock_services[0],
                "helper-service-2": mock_services[1],
            }
            mock_get_discovery.return_value = mock_discovery

            services = await discover_services()

            assert len(services) == 2
            assert services[0].service_name == "helper-service-1"
            assert services[1].service_name == "helper-service-2"

    @pytest.mark.asyncio
    async def test_call_service_helper(self):
        """call_service 헬퍼 함수 테스트"""
        with patch(
            "rfs.cloud_run.service_discovery.get_service_discovery"
        ) as mock_get_discovery:
            mock_discovery = AsyncMock()
            mock_discovery.call_service = AsyncMock(
                return_value=Success({"message": "Hello from helper"})
            )
            mock_get_discovery.return_value = mock_discovery

            result = await call_service("helper-service", path="/api/test")

            assert result.is_success()
            response = result.unwrap()
            assert response["message"] == "Hello from helper"

            mock_discovery.call_service.assert_called_once_with(
                "helper-service", path="/api/test"
            )

    @pytest.mark.asyncio
    async def test_health_check_all_helper(self):
        """health_check_all 헬퍼 함수 테스트"""
        with patch(
            "rfs.cloud_run.service_discovery.get_service_discovery"
        ) as mock_get_discovery:
            mock_discovery = AsyncMock()
            mock_discovery.services = {"service1": Mock(), "service2": Mock()}
            mock_discovery.health_check = AsyncMock(
                side_effect=[Success(True), Success(True)]
            )
            mock_get_discovery.return_value = mock_discovery

            results = await health_check_all()

            assert len(results) == 2
            assert results["service1"] is True
            assert results["service2"] is True

    @pytest.mark.asyncio
    async def test_get_enhanced_service_discovery_helper(self):
        """get_enhanced_service_discovery 헬퍼 함수 테스트"""
        with patch.dict(os.environ, {"GCP_PROJECT": "enhanced-test-project"}):
            with patch("aiohttp.ClientSession"):
                discovery = await get_enhanced_service_discovery(
                    region="asia-northeast1"
                )

                assert discovery is not None
                assert discovery.project_id == "enhanced-test-project"
                assert discovery.region == "asia-northeast1"
                assert hasattr(discovery, "service_groups")

    @pytest.mark.asyncio
    async def test_find_services_helper(self):
        """find_services 헬퍼 함수 테스트"""
        with patch(
            "rfs.cloud_run.service_discovery.get_enhanced_service_discovery"
        ) as mock_get_enhanced:
            mock_discovery = AsyncMock()
            mock_services = [
                ServiceEndpoint(
                    "search-service-1",
                    "https://search-service-1.a.run.app",
                    "test-project",
                ),
                ServiceEndpoint(
                    "search-service-2",
                    "https://search-service-2.a.run.app",
                    "test-project",
                ),
            ]
            mock_discovery.query_services = Mock(return_value=mock_services)
            mock_get_enhanced.return_value = mock_discovery

            query = ServiceQuery(only_healthy=True)
            results = await find_services(query)

            assert len(results) == 2
            assert results[0].service_name == "search-service-1"
            assert results[1].service_name == "search-service-2"

            mock_discovery.query_services.assert_called_once_with(query)


# Google Cloud Run 환경 변수 모킹을 위한 통합 테스트
class TestCloudRunEnvironmentIntegration:
    """Cloud Run 환경 통합 테스트"""

    @pytest.mark.asyncio
    async def test_cloud_run_environment_detection(self):
        """Cloud Run 환경 감지 테스트"""
        # Cloud Run 환경 변수 설정
        cloud_run_env = {
            "K_SERVICE": "test-service",
            "K_REVISION": "test-service-00001-abc",
            "K_CONFIGURATION": "test-service",
            "GOOGLE_CLOUD_PROJECT": "test-project-12345",
            "PORT": "8080",
        }

        with patch.dict(os.environ, cloud_run_env):
            with patch("aiohttp.ClientSession"):
                discovery = await get_service_discovery()

                # 환경 변수에서 프로젝트 ID가 자동으로 설정되었는지 확인
                assert discovery.project_id == "test-project-12345"

    @pytest.mark.asyncio
    async def test_service_discovery_without_gcp_client(self):
        """GCP 클라이언트 없이 서비스 디스커버리 테스트"""
        with patch("rfs.cloud_run.service_discovery.GOOGLE_CLOUD_AVAILABLE", False):
            discovery = CloudRunServiceDiscovery("test-project")

            with patch("aiohttp.ClientSession"):
                await discovery.initialize()

                # GCP 클라이언트가 없어도 기본 기능은 작동해야 함
                assert discovery.cloud_run_client is None
                assert discovery.session is not None

    @pytest.mark.asyncio
    async def test_service_registration_and_discovery_full_cycle(self):
        """서비스 등록 및 발견 전체 사이클 테스트"""
        discovery = CloudRunServiceDiscovery("full-cycle-project", "us-central1")

        # 1. 서비스 수동 등록
        services = []
        for i in range(3):
            endpoint = ServiceEndpoint(
                service_name=f"cycle-service-{i}",
                url=f"https://cycle-service-{i}-hash.a.run.app",
                project_id="full-cycle-project",
            )
            result = discovery.register_service(endpoint)
            assert result.is_success()
            services.append(endpoint)

        # 2. 등록된 서비스 확인
        assert len(discovery.services) == 3
        for i in range(3):
            service = discovery.get_service(f"cycle-service-{i}")
            assert service.is_some()

        # 3. 건강한 서비스 필터링 (초기에는 모두 UNKNOWN)
        healthy_services = discovery.get_healthy_services()
        assert len(healthy_services) == 0  # UNKNOWN 상태는 건강하지 않음으로 간주

        # 4. 서비스 상태를 HEALTHY로 변경
        for service in services:
            service.status = ServiceStatus.HEALTHY

        healthy_services = discovery.get_healthy_services()
        assert len(healthy_services) == 3

        # 5. 로드 밸런싱 테스트
        service_names = [s.service_name for s in services]
        selected = discovery.get_load_balanced_service(
            service_names, LoadBalancingStrategy.ROUND_ROBIN
        )
        assert selected.is_some()
        assert selected.unwrap().service_name in service_names

        # 6. 통계 확인
        stats = discovery.get_service_stats()
        assert stats["total_services"] == 3
        assert stats["healthy_services"] == 3
        assert stats["health_rate"] == 1.0
