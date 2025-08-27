"""
Cloud Run Environment Variable Management Tests

Google Cloud Run의 환경 변수 관리, 설정, 및 런타임 환경 테스트
"""

import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from rfs.cloud_run import (
    get_cloud_run_metadata,
    initialize_cloud_run_services,
    is_cloud_run_environment,
)
from rfs.cloud_run.helpers import (
    get_cloud_run_region,
    get_cloud_run_revision,
    get_cloud_run_service_name,
    get_cloud_run_status,
)
from rfs.cloud_run.helpers import is_cloud_run_environment as helpers_is_cloud_run


class TestCloudRunEnvironmentDetection:
    """Cloud Run 환경 감지 테스트"""

    def test_is_cloud_run_environment_false_empty_env(self):
        """빈 환경변수에서 Cloud Run 환경 감지 실패"""
        with patch.dict(os.environ, {}, clear=True):
            assert is_cloud_run_environment() is False
            assert helpers_is_cloud_run() is False

    def test_is_cloud_run_environment_k_service(self):
        """K_SERVICE 환경변수로 Cloud Run 환경 감지"""
        test_cases = [
            "my-service",
            "user-auth-service",
            "api-gateway-v2",
            "microservice-12345",
        ]

        for service_name in test_cases:
            with patch.dict(os.environ, {"K_SERVICE": service_name}, clear=True):
                assert is_cloud_run_environment() is True
                assert helpers_is_cloud_run() is True
                assert get_cloud_run_service_name() == service_name

    def test_is_cloud_run_environment_k_revision(self):
        """K_REVISION 환경변수로 Cloud Run 환경 감지"""
        test_revisions = [
            "my-service-00001-abc",
            "api-v2-00042-xyz",
            "worker-service-00123-def",
        ]

        for revision in test_revisions:
            with patch.dict(os.environ, {"K_REVISION": revision}, clear=True):
                # __init__.py의 함수는 K_SERVICE만 체크하므로 False
                assert is_cloud_run_environment() is False
                # helpers.py의 함수는 여러 환경변수 체크하므로 True
                assert helpers_is_cloud_run() is True
                assert get_cloud_run_revision() == revision

    def test_is_cloud_run_environment_k_configuration(self):
        """K_CONFIGURATION 환경변수로 Cloud Run 환경 감지"""
        test_configs = [
            "my-service-config",
            "production-api-config",
            "staging-worker-config",
        ]

        for config in test_configs:
            with patch.dict(os.environ, {"K_CONFIGURATION": config}, clear=True):
                # __init__.py의 함수는 K_SERVICE만 체크하므로 False
                assert is_cloud_run_environment() is False
                # helpers.py의 함수는 여러 환경변수 체크하므로 True
                assert helpers_is_cloud_run() is True

    def test_is_cloud_run_environment_cloud_run_job(self):
        """CLOUD_RUN_JOB 환경변수로 Cloud Run Jobs 환경 감지"""
        test_jobs = [
            "batch-processor-job",
            "data-migration-job",
            "report-generator-job",
        ]

        for job in test_jobs:
            with patch.dict(os.environ, {"CLOUD_RUN_JOB": job}, clear=True):
                # __init__.py의 함수는 K_SERVICE만 체크하므로 False
                assert is_cloud_run_environment() is False
                # helpers.py의 함수는 여러 환경변수 체크하므로 True
                assert helpers_is_cloud_run() is True

    def test_is_cloud_run_environment_multiple_indicators(self):
        """여러 Cloud Run 지시자가 동시에 존재하는 경우"""
        env_vars = {
            "K_SERVICE": "my-awesome-service",
            "K_REVISION": "my-awesome-service-00001-abc",
            "K_CONFIGURATION": "my-awesome-service",
            "GOOGLE_CLOUD_PROJECT": "my-project-123",
            "PORT": "8080",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            assert is_cloud_run_environment() is True
            assert helpers_is_cloud_run() is True

    def test_is_cloud_run_environment_partial_indicators(self):
        """부분적 Cloud Run 지시자 조합"""
        # K_SERVICE만 있는 경우
        with patch.dict(os.environ, {"K_SERVICE": "test-service"}, clear=True):
            assert helpers_is_cloud_run() is True

        # K_REVISION만 있는 경우
        with patch.dict(os.environ, {"K_REVISION": "test-rev-001"}, clear=True):
            assert helpers_is_cloud_run() is True

        # K_CONFIGURATION만 있는 경우
        with patch.dict(os.environ, {"K_CONFIGURATION": "test-config"}, clear=True):
            assert helpers_is_cloud_run() is True

    def test_is_cloud_run_environment_non_cloud_run_vars(self):
        """Cloud Run과 관련 없는 환경변수들"""
        non_cloud_run_vars = {
            "HOME": "/home/user",
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "ko_KR.UTF-8",
            "NODE_ENV": "production",
            "DATABASE_URL": "postgres://localhost/mydb",
        }

        with patch.dict(os.environ, non_cloud_run_vars, clear=True):
            assert is_cloud_run_environment() is False
            assert helpers_is_cloud_run() is False


class TestCloudRunMetadataExtraction:
    """Cloud Run 메타데이터 추출 테스트"""

    def test_get_cloud_run_service_name_none(self):
        """서비스 이름이 설정되지 않은 경우"""
        with patch.dict(os.environ, {}, clear=True):
            assert get_cloud_run_service_name() is None

    def test_get_cloud_run_service_name_values(self):
        """다양한 서비스 이름 값 테스트"""
        test_names = [
            "simple-service",
            "complex-microservice-api-v2",
            "user_auth_service",
            "service-123-prod",
        ]

        for name in test_names:
            with patch.dict(os.environ, {"K_SERVICE": name}, clear=True):
                assert get_cloud_run_service_name() == name

    def test_get_cloud_run_revision_none(self):
        """리비전이 설정되지 않은 경우"""
        with patch.dict(os.environ, {}, clear=True):
            assert get_cloud_run_revision() is None

    def test_get_cloud_run_revision_formats(self):
        """다양한 리비전 형식 테스트"""
        test_revisions = [
            "service-00001-abc",
            "my-api-v2-00042-xyz123",
            "worker-service-00999-def456",
        ]

        for revision in test_revisions:
            with patch.dict(os.environ, {"K_REVISION": revision}, clear=True):
                assert get_cloud_run_revision() == revision

    def test_get_cloud_run_region_default(self):
        """기본 리전 반환 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            assert get_cloud_run_region() == "asia-northeast3"

    def test_get_cloud_run_region_custom(self):
        """커스텀 리전 설정 테스트"""
        test_regions = [
            "us-central1",
            "europe-west1",
            "asia-northeast1",
            "australia-southeast1",
        ]

        for region in test_regions:
            with patch.dict(os.environ, {"CLOUD_RUN_REGION": region}, clear=True):
                assert get_cloud_run_region() == region

    def test_get_cloud_run_metadata_complete(self):
        """완전한 Cloud Run 메타데이터 테스트"""
        full_env = {
            "K_SERVICE": "my-production-api",
            "K_REVISION": "my-production-api-00023-xyz789",
            "K_CONFIGURATION": "my-production-api",
            "GOOGLE_CLOUD_PROJECT": "my-company-prod-12345",
            "GOOGLE_CLOUD_REGION": "us-central1",
            "PORT": "8080",
        }

        with patch.dict(os.environ, full_env, clear=True):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "my-production-api"
            assert metadata["revision"] == "my-production-api-00023-xyz789"
            assert metadata["configuration"] == "my-production-api"
            assert metadata["project_id"] == "my-company-prod-12345"
            assert metadata["region"] == "us-central1"
            assert metadata["port"] == "8080"

    def test_get_cloud_run_metadata_defaults(self):
        """기본값이 적용된 메타데이터 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "unknown"
            assert metadata["revision"] == "unknown"
            assert metadata["configuration"] == "unknown"
            assert metadata["project_id"] == "unknown"
            assert metadata["region"] == "unknown"
            assert metadata["port"] == "8080"  # PORT 기본값

    def test_get_cloud_run_metadata_partial(self):
        """부분적으로 설정된 메타데이터 테스트"""
        partial_env = {
            "K_SERVICE": "partial-service",
            "GOOGLE_CLOUD_PROJECT": "partial-project",
            "PORT": "9000",
        }

        with patch.dict(os.environ, partial_env, clear=True):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "partial-service"
            assert metadata["revision"] == "unknown"
            assert metadata["configuration"] == "unknown"
            assert metadata["project_id"] == "partial-project"
            assert metadata["region"] == "unknown"
            assert metadata["port"] == "9000"


class TestEnvironmentBasedServiceInitialization:
    """환경 기반 서비스 초기화 테스트"""

    @pytest.mark.asyncio
    async def test_initialize_services_with_explicit_params(self):
        """명시적 파라미터로 서비스 초기화"""
        with (
            patch("rfs.cloud_run.get_service_discovery") as mock_sd,
            patch("rfs.cloud_run.get_task_queue") as mock_tq,
            patch("rfs.cloud_run.get_monitoring_client") as mock_mc,
            patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_ao,
            patch("rfs.cloud_run.log_info"),
        ):

            mock_sd.return_value = "service_discovery_instance"
            mock_tq.return_value = "task_queue_instance"
            mock_mc.return_value = "monitoring_instance"
            mock_ao.return_value = "autoscaling_instance"

            result = await initialize_cloud_run_services(
                project_id="explicit-project-123",
                service_name="explicit-service",
                enable_service_discovery=True,
                enable_task_queue=True,
                enable_monitoring=True,
                enable_autoscaling=True,
            )

            assert result["success"] is True
            assert result["project_id"] == "explicit-project-123"
            assert result["service_name"] == "explicit-service"
            assert len(result["initialized_services"]) == 4

    @pytest.mark.asyncio
    async def test_initialize_services_from_environment(self):
        """환경변수에서 서비스 초기화 정보 추출"""
        env_vars = {
            "GOOGLE_CLOUD_PROJECT": "env-project-456",
            "K_SERVICE": "env-service-name",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with (
                patch("rfs.cloud_run.get_service_discovery") as mock_sd,
                patch("rfs.cloud_run.get_task_queue") as mock_tq,
                patch("rfs.cloud_run.get_monitoring_client") as mock_mc,
                patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_ao,
                patch("rfs.cloud_run.log_info"),
            ):

                mock_sd.return_value = "service_discovery"
                mock_tq.return_value = "task_queue"
                mock_mc.return_value = "monitoring"
                mock_ao.return_value = "autoscaling"

                result = await initialize_cloud_run_services()

                assert result["success"] is True
                assert result["project_id"] == "env-project-456"
                assert result["service_name"] == "env-service-name"

    @pytest.mark.asyncio
    async def test_initialize_services_missing_project_id(self):
        """프로젝트 ID 누락 시 초기화 실패"""
        with patch.dict(os.environ, {}, clear=True):
            result = await initialize_cloud_run_services()

            assert result["success"] is False
            assert "GOOGLE_CLOUD_PROJECT" in result["error"]

    @pytest.mark.asyncio
    async def test_initialize_services_default_service_name(self):
        """서비스 이름 기본값 사용"""
        with patch.dict(
            os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=True
        ):
            with (
                patch("rfs.cloud_run.get_service_discovery") as mock_sd,
                patch("rfs.cloud_run.get_task_queue") as mock_tq,
                patch("rfs.cloud_run.get_monitoring_client") as mock_mc,
                patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_ao,
                patch("rfs.cloud_run.log_info"),
            ):

                mock_sd.return_value = "service_discovery"
                mock_tq.return_value = "task_queue"
                mock_mc.return_value = "monitoring"
                mock_ao.return_value = "autoscaling"

                result = await initialize_cloud_run_services()

                assert result["success"] is True
                assert result["service_name"] == "rfs-service"  # 기본값

    @pytest.mark.asyncio
    async def test_initialize_services_selective_enablement(self):
        """선택적 서비스 활성화 테스트"""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with (
                patch("rfs.cloud_run.get_service_discovery") as mock_sd,
                patch("rfs.cloud_run.log_info"),
            ):

                mock_sd.return_value = "service_discovery_only"

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


class TestEnvironmentVariableValidation:
    """환경 변수 검증 테스트"""

    def test_required_env_vars_validation(self):
        """필수 환경 변수 검증"""
        required_vars = ["GOOGLE_CLOUD_PROJECT"]

        with patch.dict(os.environ, {}, clear=True):
            for var in required_vars:
                assert os.getenv(var) is None

    def test_optional_env_vars_defaults(self):
        """선택적 환경 변수 기본값 확인"""
        with patch.dict(os.environ, {}, clear=True):
            # 기본값이 있는 것들
            assert get_cloud_run_region() == "asia-northeast3"

            # None이 반환되는 것들
            assert get_cloud_run_service_name() is None
            assert get_cloud_run_revision() is None

    def test_env_var_precedence(self):
        """환경 변수 우선순위 테스트"""
        # 명시적 파라미터 vs 환경 변수 우선순위는
        # initialize_cloud_run_services에서 이미 테스트됨

        # 여기서는 환경 변수 자체의 우선순위 테스트
        env_vars = {
            "CLOUD_RUN_REGION": "us-central1",  # 명시적 리전
            "GOOGLE_CLOUD_REGION": "asia-northeast1",  # 다른 리전 변수
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # CLOUD_RUN_REGION이 우선되어야 함
            assert get_cloud_run_region() == "us-central1"

    def test_env_var_type_safety(self):
        """환경 변수 타입 안전성 테스트"""
        # 환경 변수는 항상 문자열이므로 적절한 변환 확인
        test_cases = {
            "PORT": "8080",
            "K_SERVICE": "my-service",
            "GOOGLE_CLOUD_PROJECT": "project-123",
        }

        for key, value in test_cases.items():
            with patch.dict(os.environ, {key: value}, clear=True):
                retrieved = os.getenv(key)
                assert isinstance(retrieved, str)
                assert retrieved == value

    def test_env_var_edge_cases(self):
        """환경 변수 엣지 케이스 테스트"""
        edge_cases = {
            "empty_string": "",
            "whitespace": "   ",
            "special_chars": "service-with-@#$%^&*()_+",
            "unicode": "서비스-이름-한글",
            "very_long": "a" * 255,
        }

        for case_name, value in edge_cases.items():
            with patch.dict(os.environ, {"K_SERVICE": value}, clear=True):
                assert get_cloud_run_service_name() == value

    def test_cloud_run_status_integration(self):
        """Cloud Run 상태와 환경 변수 통합 테스트"""
        production_env = {
            "K_SERVICE": "production-api-v2",
            "K_REVISION": "production-api-v2-00042-xyz123",
            "GOOGLE_CLOUD_PROJECT": "my-company-prod",
            "CLOUD_RUN_REGION": "us-central1",
            "PORT": "8080",
        }

        with patch.dict(os.environ, production_env, clear=True):
            status = get_cloud_run_status()

            assert status["is_cloud_run"] is True
            assert status["service_name"] == "production-api-v2"
            assert status["revision"] == "production-api-v2-00042-xyz123"
            assert status["region"] == "us-central1"

    def test_environment_configuration_matrix(self):
        """환경 설정 매트릭스 테스트"""
        environments = {
            "development": {
                "K_SERVICE": "dev-service",
                "GOOGLE_CLOUD_PROJECT": "dev-project",
                "CLOUD_RUN_REGION": "us-central1",
            },
            "staging": {
                "K_SERVICE": "staging-service",
                "GOOGLE_CLOUD_PROJECT": "staging-project",
                "CLOUD_RUN_REGION": "us-east1",
            },
            "production": {
                "K_SERVICE": "prod-service",
                "GOOGLE_CLOUD_PROJECT": "prod-project",
                "CLOUD_RUN_REGION": "asia-northeast3",
            },
        }

        for env_name, env_vars in environments.items():
            with patch.dict(os.environ, env_vars, clear=True):
                assert is_cloud_run_environment() is True
                assert get_cloud_run_service_name() == env_vars["K_SERVICE"]
                assert get_cloud_run_region() == env_vars["CLOUD_RUN_REGION"]

                metadata = get_cloud_run_metadata()
                assert metadata["project_id"] == env_vars["GOOGLE_CLOUD_PROJECT"]
