"""
Cloud Run Health Check System Tests

Google Cloud Run의 헬스체크 시스템과 서비스 상태 관리 테스트
"""

import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rfs.cloud_run import (
    get_cloud_run_metadata,
)
from rfs.cloud_run import get_cloud_run_status as get_module_status
from rfs.cloud_run import (
    initialize_cloud_run_services,
    shutdown_cloud_run_services,
)
from rfs.cloud_run.helpers import (
    CloudRunServiceDiscovery,
    ServiceEndpoint,
    call_service,
    discover_services,
    get_cloud_run_region,
    get_cloud_run_revision,
    get_cloud_run_service_name,
    get_cloud_run_status,
    get_service_discovery,
    is_cloud_run_environment,
)
from rfs.core.result import Failure, Success


class TestServiceEndpoint:
    """서비스 엔드포인트 헬스체크 테스트"""

    def test_service_endpoint_creation(self):
        """서비스 엔드포인트 생성 테스트"""
        endpoint = ServiceEndpoint("test-service", "https://test.example.com")

        assert endpoint.name == "test-service"
        assert endpoint.url == "https://test.example.com"
        assert endpoint.health_check_url == "https://test.example.com/health"
        assert endpoint.is_healthy is True
        assert endpoint.region == "asia-northeast3"  # 기본값
        assert endpoint.last_health_check is None

    def test_service_endpoint_with_custom_region(self):
        """커스텀 리전으로 서비스 엔드포인트 생성"""
        endpoint = ServiceEndpoint(
            "test-service", "https://test.example.com", region="us-central1"
        )

        assert endpoint.region == "us-central1"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """헬스체크 성공 테스트"""
        endpoint = ServiceEndpoint("test-service", "https://test.example.com")

        result = await endpoint.check_health()

        assert result is True
        assert endpoint.last_health_check is not None
        assert isinstance(endpoint.last_health_check, datetime)
        # 최근 시간인지 확인 (1초 이내)
        assert datetime.now() - endpoint.last_health_check < timedelta(seconds=1)

    @pytest.mark.asyncio
    async def test_health_check_timing(self):
        """헬스체크 타이밍 검증"""
        endpoint = ServiceEndpoint("test-service", "https://test.example.com")

        before = datetime.now()
        await endpoint.check_health()
        after = datetime.now()

        assert before <= endpoint.last_health_check <= after

    def test_unhealthy_endpoint_behavior(self):
        """비정상 상태 엔드포인트 동작 확인"""
        endpoint = ServiceEndpoint("test-service", "https://test.example.com")
        endpoint.is_healthy = False

        assert endpoint.is_healthy is False
        # 헬스체크 URL은 그대로 유지
        assert endpoint.health_check_url == "https://test.example.com/health"


class TestCloudRunServiceDiscovery:
    """Cloud Run 서비스 디스커버리 테스트"""

    def test_service_discovery_singleton(self):
        """서비스 디스커버리 싱글톤 패턴 확인"""
        discovery1 = CloudRunServiceDiscovery()
        discovery2 = CloudRunServiceDiscovery()

        assert discovery1 is discovery2

    def test_initial_state(self):
        """초기 상태 확인"""
        discovery = CloudRunServiceDiscovery()

        assert discovery._services == {}
        assert discovery._initialized is False
        assert discovery.list_services() == []

    @pytest.mark.asyncio
    async def test_initialization(self):
        """서비스 디스커버리 초기화 테스트"""
        discovery = CloudRunServiceDiscovery()

        # 초기에는 초기화되지 않음
        assert discovery._initialized is False

        await discovery.initialize()

        # 초기화 완료
        assert discovery._initialized is True

    @pytest.mark.asyncio
    async def test_multiple_initialization(self):
        """중복 초기화 시도 테스트"""
        discovery = CloudRunServiceDiscovery()

        await discovery.initialize()
        assert discovery._initialized is True

        # 재초기화 시도
        await discovery.initialize()
        assert discovery._initialized is True

    def test_service_registration(self):
        """서비스 등록 테스트"""
        discovery = CloudRunServiceDiscovery()
        endpoint = ServiceEndpoint("auth-service", "https://auth.example.com")

        discovery.register_service("auth-service", endpoint)

        assert "auth-service" in discovery.list_services()
        assert discovery.get_service("auth-service") is endpoint

    def test_multiple_service_registration(self):
        """여러 서비스 등록 테스트"""
        discovery = CloudRunServiceDiscovery()

        auth_endpoint = ServiceEndpoint("auth-service", "https://auth.example.com")
        user_endpoint = ServiceEndpoint("user-service", "https://user.example.com")

        discovery.register_service("auth-service", auth_endpoint)
        discovery.register_service("user-service", user_endpoint)

        services = discovery.list_services()
        assert len(services) == 2
        assert "auth-service" in services
        assert "user-service" in services

    def test_service_retrieval(self):
        """서비스 조회 테스트"""
        discovery = CloudRunServiceDiscovery()
        endpoint = ServiceEndpoint("test-service", "https://test.example.com")

        discovery.register_service("test-service", endpoint)

        retrieved = discovery.get_service("test-service")
        assert retrieved is endpoint

        # 존재하지 않는 서비스
        non_existent = discovery.get_service("non-existent")
        assert non_existent is None

    def test_service_override(self):
        """서비스 등록 덮어쓰기 테스트"""
        discovery = CloudRunServiceDiscovery()

        endpoint1 = ServiceEndpoint("test-service", "https://test1.example.com")
        endpoint2 = ServiceEndpoint("test-service", "https://test2.example.com")

        discovery.register_service("test-service", endpoint1)
        discovery.register_service("test-service", endpoint2)

        # 최신 등록된 서비스가 우선
        retrieved = discovery.get_service("test-service")
        assert retrieved is endpoint2
        assert retrieved.url == "https://test2.example.com"


class TestServiceDiscoveryFunctions:
    """서비스 디스커버리 헬퍼 함수 테스트"""

    def test_get_service_discovery_singleton(self):
        """글로벌 서비스 디스커버리 인스턴스 반환 확인"""
        discovery1 = get_service_discovery()
        discovery2 = get_service_discovery()

        assert discovery1 is discovery2
        assert isinstance(discovery1, CloudRunServiceDiscovery)

    @pytest.mark.asyncio
    async def test_discover_services_empty(self):
        """빈 서비스 디스커버리에서 서비스 탐색"""
        # 새로운 인스턴스 생성 (테스트 격리)
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get:
            mock_discovery = CloudRunServiceDiscovery()
            mock_discovery._services = {}  # 명시적으로 비우기
            mock_get.return_value = mock_discovery

            services = await discover_services()

            assert services == []

    @pytest.mark.asyncio
    async def test_discover_services_with_pattern(self):
        """패턴을 사용한 서비스 탐색"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get:
            mock_discovery = CloudRunServiceDiscovery()

            # 테스트용 서비스들 등록
            auth_endpoint = ServiceEndpoint("auth-service", "https://auth.example.com")
            user_endpoint = ServiceEndpoint("user-service", "https://user.example.com")
            payment_endpoint = ServiceEndpoint(
                "payment-api", "https://payment.example.com"
            )

            mock_discovery.register_service("auth-service", auth_endpoint)
            mock_discovery.register_service("user-service", user_endpoint)
            mock_discovery.register_service("payment-api", payment_endpoint)

            mock_get.return_value = mock_discovery

            # 모든 서비스 탐색
            all_services = await discover_services("*")
            assert len(all_services) == 3

            # 패턴 매칭 서비스 탐색
            service_pattern = await discover_services("service")
            service_names = [s.name for s in service_pattern]
            assert "auth-service" in service_names
            assert "user-service" in service_names
            assert "payment-api" not in service_names

    @pytest.mark.asyncio
    async def test_discover_services_initialization(self):
        """서비스 탐색 시 자동 초기화 확인"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get:
            mock_discovery = AsyncMock(spec=CloudRunServiceDiscovery)
            mock_discovery.list_services.return_value = []
            mock_get.return_value = mock_discovery

            await discover_services()

            # 초기화 메서드가 호출되었는지 확인
            mock_discovery.initialize.assert_called_once()


class TestServiceCalls:
    """서비스 호출 테스트"""

    @pytest.mark.asyncio
    async def test_call_service_success(self):
        """정상 서비스 호출 테스트"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get:
            mock_discovery = MagicMock(spec=CloudRunServiceDiscovery)
            endpoint = ServiceEndpoint("test-service", "https://test.example.com")
            endpoint.is_healthy = True
            mock_discovery.get_service.return_value = endpoint
            mock_get.return_value = mock_discovery

            result = await call_service(
                "test-service", "/api/users", method="GET", data={"user_id": "123"}
            )

            assert isinstance(result, Success)
            response_data = result.value
            assert response_data["status"] == "success"
            assert response_data["data"] == {"user_id": "123"}
            assert "timestamp" in response_data

    @pytest.mark.asyncio
    async def test_call_service_not_found(self):
        """존재하지 않는 서비스 호출 테스트"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get:
            mock_discovery = MagicMock(spec=CloudRunServiceDiscovery)
            mock_discovery.get_service.return_value = None
            mock_get.return_value = mock_discovery

            result = await call_service("non-existent-service", "/api/test")

            assert isinstance(result, Failure)
            assert "Service not found: non-existent-service" in result.error

    @pytest.mark.asyncio
    async def test_call_service_unhealthy(self):
        """비정상 서비스 호출 테스트"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get:
            mock_discovery = MagicMock(spec=CloudRunServiceDiscovery)
            endpoint = ServiceEndpoint("test-service", "https://test.example.com")
            endpoint.is_healthy = False
            mock_discovery.get_service.return_value = endpoint
            mock_get.return_value = mock_discovery

            result = await call_service("test-service", "/api/test")

            assert isinstance(result, Failure)
            assert "Service unhealthy: test-service" in result.error

    @pytest.mark.asyncio
    async def test_call_service_with_headers(self):
        """헤더를 포함한 서비스 호출 테스트"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get:
            mock_discovery = MagicMock(spec=CloudRunServiceDiscovery)
            endpoint = ServiceEndpoint("test-service", "https://test.example.com")
            endpoint.is_healthy = True
            mock_discovery.get_service.return_value = endpoint
            mock_get.return_value = mock_discovery

            headers = {
                "Authorization": "Bearer token123",
                "Content-Type": "application/json",
            }
            result = await call_service(
                "test-service",
                "/api/protected",
                method="POST",
                data={"action": "update"},
                headers=headers,
            )

            assert isinstance(result, Success)


class TestEnvironmentDetection:
    """Cloud Run 환경 감지 테스트"""

    def test_cloud_run_environment_detection_false(self):
        """Cloud Run이 아닌 환경에서의 감지"""
        with patch.dict(os.environ, {}, clear=True):
            assert is_cloud_run_environment() is False

    def test_cloud_run_environment_detection_k_service(self):
        """K_SERVICE 환경변수로 Cloud Run 감지"""
        with patch.dict(os.environ, {"K_SERVICE": "test-service"}):
            assert is_cloud_run_environment() is True

    def test_cloud_run_environment_detection_k_revision(self):
        """K_REVISION 환경변수로 Cloud Run 감지"""
        with patch.dict(os.environ, {"K_REVISION": "test-revision-001"}):
            assert is_cloud_run_environment() is True

    def test_cloud_run_environment_detection_k_configuration(self):
        """K_CONFIGURATION 환경변수로 Cloud Run 감지"""
        with patch.dict(os.environ, {"K_CONFIGURATION": "test-config"}):
            assert is_cloud_run_environment() is True

    def test_cloud_run_environment_detection_cloud_run_job(self):
        """CLOUD_RUN_JOB 환경변수로 Cloud Run 감지"""
        with patch.dict(os.environ, {"CLOUD_RUN_JOB": "test-job"}):
            assert is_cloud_run_environment() is True

    def test_cloud_run_multiple_env_vars(self):
        """여러 환경변수가 설정된 경우"""
        with patch.dict(
            os.environ,
            {
                "K_SERVICE": "test-service",
                "K_REVISION": "test-revision-001",
                "GOOGLE_CLOUD_PROJECT": "test-project",
            },
        ):
            assert is_cloud_run_environment() is True

    def test_get_cloud_run_service_name(self):
        """Cloud Run 서비스 이름 조회"""
        with patch.dict(os.environ, {"K_SERVICE": "my-awesome-service"}):
            assert get_cloud_run_service_name() == "my-awesome-service"

    def test_get_cloud_run_service_name_none(self):
        """서비스 이름이 설정되지 않은 경우"""
        with patch.dict(os.environ, {}, clear=True):
            assert get_cloud_run_service_name() is None

    def test_get_cloud_run_revision(self):
        """Cloud Run 리비전 조회"""
        with patch.dict(os.environ, {"K_REVISION": "my-service-00001-abc"}):
            assert get_cloud_run_revision() == "my-service-00001-abc"

    def test_get_cloud_run_revision_none(self):
        """리비전이 설정되지 않은 경우"""
        with patch.dict(os.environ, {}, clear=True):
            assert get_cloud_run_revision() is None

    def test_get_cloud_run_region_default(self):
        """기본 리전 반환 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            assert get_cloud_run_region() == "asia-northeast3"

    def test_get_cloud_run_region_custom(self):
        """커스텀 리전 설정 테스트"""
        with patch.dict(os.environ, {"CLOUD_RUN_REGION": "us-central1"}):
            assert get_cloud_run_region() == "us-central1"


class TestCloudRunStatus:
    """Cloud Run 상태 조회 테스트"""

    def test_get_cloud_run_status_local(self):
        """로컬 환경에서의 상태 조회"""
        with patch.dict(os.environ, {}, clear=True):
            status = get_cloud_run_status()

            assert status["is_cloud_run"] is False
            assert status["service_name"] is None
            assert status["revision"] is None
            assert status["region"] == "asia-northeast3"

    def test_get_cloud_run_status_cloud_run(self):
        """Cloud Run 환경에서의 상태 조회"""
        env_vars = {
            "K_SERVICE": "test-service",
            "K_REVISION": "test-service-00001-abc",
            "CLOUD_RUN_REGION": "us-central1",
        }

        with patch.dict(os.environ, env_vars):
            status = get_cloud_run_status()

            assert status["is_cloud_run"] is True
            assert status["service_name"] == "test-service"
            assert status["revision"] == "test-service-00001-abc"
            assert status["region"] == "us-central1"


class TestCloudRunModuleFunctions:
    """Cloud Run 모듈 레벨 함수 테스트"""

    def test_get_cloud_run_metadata_local(self):
        """로컬 환경에서 메타데이터 조회"""
        with patch.dict(os.environ, {}, clear=True):
            metadata = get_cloud_run_metadata()

            expected_keys = [
                "service_name",
                "revision",
                "configuration",
                "project_id",
                "region",
                "port",
            ]

            for key in expected_keys:
                assert key in metadata

            # 기본값 확인
            assert metadata["service_name"] == "unknown"
            assert metadata["revision"] == "unknown"
            assert metadata["port"] == "8080"
            assert metadata["region"] == "unknown"

    def test_get_cloud_run_metadata_cloud_run(self):
        """Cloud Run 환경에서 메타데이터 조회"""
        env_vars = {
            "K_SERVICE": "my-service",
            "K_REVISION": "my-service-00001-abc",
            "K_CONFIGURATION": "my-service",
            "GOOGLE_CLOUD_PROJECT": "my-project-123",
            "GOOGLE_CLOUD_REGION": "asia-northeast1",
            "PORT": "8080",
        }

        with patch.dict(os.environ, env_vars):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "my-service"
            assert metadata["revision"] == "my-service-00001-abc"
            assert metadata["configuration"] == "my-service"
            assert metadata["project_id"] == "my-project-123"
            assert metadata["region"] == "asia-northeast1"
            assert metadata["port"] == "8080"

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_success(self):
        """Cloud Run 서비스 초기화 성공 테스트"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "test-project", "K_SERVICE": "test-service"}

        with patch.dict(os.environ, env_vars):
            with (
                patch("rfs.cloud_run.get_service_discovery") as mock_sd,
                patch("rfs.cloud_run.get_task_queue") as mock_tq,
                patch("rfs.cloud_run.get_monitoring_client") as mock_mc,
                patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_ao,
                patch("rfs.cloud_run.log_info") as mock_log,
            ):

                # Mock 반환값들
                mock_sd.return_value = "mocked_service_discovery"
                mock_tq.return_value = "mocked_task_queue"
                mock_mc.return_value = "mocked_monitoring"
                mock_ao.return_value = "mocked_autoscaling"

                result = await initialize_cloud_run_services()

                assert result["success"] is True
                assert result["project_id"] == "test-project"
                assert result["service_name"] == "test-service"
                assert "service_discovery" in result["initialized_services"]
                assert "task_queue" in result["initialized_services"]
                assert "monitoring" in result["initialized_services"]
                assert "autoscaling" in result["initialized_services"]
                assert "cloud_run_metadata" in result

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_no_project_id(self):
        """프로젝트 ID가 없는 경우 초기화 실패"""
        with patch.dict(os.environ, {}, clear=True):
            result = await initialize_cloud_run_services()

            assert result["success"] is False
            assert (
                "GOOGLE_CLOUD_PROJECT 환경 변수가 설정되지 않았습니다"
                in result["error"]
            )

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_partial(self):
        """부분적 서비스 초기화"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "test-project"}

        with patch.dict(os.environ, env_vars):
            result = await initialize_cloud_run_services(
                enable_service_discovery=True,
                enable_task_queue=False,
                enable_monitoring=False,
                enable_autoscaling=False,
            )

            assert result["success"] is True
            assert "service_discovery" in result["initialized_services"]
            assert "task_queue" not in result["initialized_services"]
            assert "monitoring" not in result["initialized_services"]
            assert "autoscaling" not in result["initialized_services"]

    @pytest.mark.asyncio
    async def test_get_module_status(self):
        """모듈 상태 조회 테스트"""
        with patch("rfs.cloud_run.is_cloud_run_environment") as mock_env:
            with patch("rfs.cloud_run.get_cloud_run_metadata") as mock_metadata:
                mock_env.return_value = True
                mock_metadata.return_value = {"service_name": "test-service"}

                status = await get_module_status()

                assert "environment" in status
                assert "services" in status
                assert status["environment"]["is_cloud_run"] is True
                assert (
                    status["environment"]["metadata"]["service_name"] == "test-service"
                )

    @pytest.mark.asyncio
    async def test_shutdown_cloud_run_services(self):
        """Cloud Run 서비스 종료 테스트"""
        # 예외가 발생하지 않는지 확인
        try:
            await shutdown_cloud_run_services()
            # 정상 종료됨
        except Exception as e:
            pytest.fail(f"shutdown_cloud_run_services raised an exception: {e}")
