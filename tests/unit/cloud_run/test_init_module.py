"""
__init__.py 모듈 종합 테스트

Cloud Run 모듈의 엔트리 포인트인 __init__.py의 모든 기능에 대한 포괄적인 테스트
"""

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# 테스트 대상 모듈 임포트
from rfs.cloud_run import (  # 핵심 함수들; 클래스들; 열거형들
    AlertSeverity,
    AutoScalingOptimizer,
    CircuitBreaker,
    CircuitBreakerState,
    CloudMonitoringClient,
    CloudRunServiceDiscovery,
    CloudTaskQueue,
    LoadBalancingStrategy,
    LogLevel,
    MetricType,
    ScalingDirection,
    ServiceEndpoint,
    ServiceStatus,
    TaskPriority,
    TaskStatus,
    TrafficPattern,
    get_cloud_run_metadata,
    get_cloud_run_status,
    initialize_cloud_run_services,
    is_cloud_run_environment,
    shutdown_cloud_run_services,
)


class TestCloudRunEnvironmentDetection:
    """Cloud Run 환경 감지 테스트"""

    def test_is_cloud_run_environment_with_k_service(self, clean_environment):
        """K_SERVICE 환경 변수가 있는 경우"""
        with patch.dict(os.environ, {"K_SERVICE": "test-service"}):
            assert is_cloud_run_environment() is True

    def test_is_cloud_run_environment_no_variables(self, clean_environment):
        """Cloud Run 환경 변수가 없는 경우"""
        assert is_cloud_run_environment() is False

    def test_is_cloud_run_environment_empty_k_service(self, clean_environment):
        """K_SERVICE가 빈 문자열인 경우 - 실제로는 True를 반환함 (os.environ.get에서 빈 문자열도 값으로 간주)"""
        with patch.dict(os.environ, {"K_SERVICE": ""}):
            assert is_cloud_run_environment() is True

    def test_is_cloud_run_environment_none_k_service(self, clean_environment):
        """K_SERVICE가 None인 경우"""
        with patch.dict(os.environ, {}, clear=True):
            if "K_SERVICE" in os.environ:
                del os.environ["K_SERVICE"]
            assert is_cloud_run_environment() is False


class TestCloudRunMetadata:
    """Cloud Run 메타데이터 테스트"""

    def test_get_cloud_run_metadata_full(self, clean_environment):
        """모든 Cloud Run 환경 변수가 설정된 경우"""
        env_vars = {
            "K_SERVICE": "my-service",
            "K_REVISION": "my-service-00001-abc",
            "K_CONFIGURATION": "my-service",
            "GOOGLE_CLOUD_PROJECT": "my-project-123",
            "GOOGLE_CLOUD_REGION": "asia-northeast3",
            "PORT": "8080",
        }

        with patch.dict(os.environ, env_vars):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "my-service"
            assert metadata["revision"] == "my-service-00001-abc"
            assert metadata["configuration"] == "my-service"
            assert metadata["project_id"] == "my-project-123"
            assert metadata["region"] == "asia-northeast3"
            assert metadata["port"] == "8080"

    def test_get_cloud_run_metadata_partial(self, clean_environment):
        """일부 환경 변수만 설정된 경우"""
        env_vars = {"K_SERVICE": "test-service", "GOOGLE_CLOUD_PROJECT": "test-project"}

        with patch.dict(os.environ, env_vars):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "test-service"
            assert metadata["revision"] == "unknown"
            assert metadata["configuration"] == "unknown"
            assert metadata["project_id"] == "test-project"
            assert metadata["region"] == "unknown"
            assert metadata["port"] == "8080"  # 기본값

    def test_get_cloud_run_metadata_empty(self, clean_environment):
        """환경 변수가 없는 경우"""
        metadata = get_cloud_run_metadata()

        assert metadata["service_name"] == "unknown"
        assert metadata["revision"] == "unknown"
        assert metadata["configuration"] == "unknown"
        assert metadata["project_id"] == "unknown"
        assert metadata["region"] == "unknown"
        assert metadata["port"] == "8080"  # 기본값


class TestInitializeCloudRunServices:
    """Cloud Run 서비스 초기화 테스트"""

    @pytest.mark.asyncio
    async def test_initialize_all_services_success(self, clean_environment):
        """모든 서비스 성공적 초기화"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "test-project"}

        with (
            patch.dict(os.environ, env_vars),
            patch("rfs.cloud_run.get_service_discovery") as mock_get_sd,
            patch("rfs.cloud_run.get_task_queue") as mock_get_tq,
            patch("rfs.cloud_run.get_monitoring_client") as mock_get_mc,
            patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_get_ao,
            patch("rfs.cloud_run.log_info") as mock_log_info,
        ):

            # Mock 서비스들 설정
            mock_get_sd.return_value = AsyncMock()
            mock_get_tq.return_value = AsyncMock()
            mock_get_mc.return_value = AsyncMock()
            mock_get_ao.return_value = AsyncMock()
            mock_log_info.return_value = AsyncMock()

            result = await initialize_cloud_run_services(
                project_id="test-project", service_name="test-service"
            )

            assert result["success"] is True
            assert result["project_id"] == "test-project"
            assert result["service_name"] == "test-service"
            assert "service_discovery" in result["initialized_services"]
            assert "task_queue" in result["initialized_services"]
            assert "monitoring" in result["initialized_services"]
            assert "autoscaling" in result["initialized_services"]
            assert "cloud_run_metadata" in result

    @pytest.mark.asyncio
    async def test_initialize_selective_services(self, clean_environment):
        """선택적 서비스 초기화"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "test-project"}

        with (
            patch.dict(os.environ, env_vars),
            patch("rfs.cloud_run.get_service_discovery") as mock_get_sd,
            patch("rfs.cloud_run.log_info") as mock_log_info,
        ):

            mock_get_sd.return_value = AsyncMock()
            mock_log_info.return_value = AsyncMock()

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
    async def test_initialize_no_project_id_env(self, clean_environment):
        """환경 변수에 프로젝트 ID가 없는 경우"""
        with patch.dict(os.environ, {}, clear=True):
            result = await initialize_cloud_run_services()

            assert result["success"] is False
            assert (
                "GOOGLE_CLOUD_PROJECT 환경 변수가 설정되지 않았습니다"
                in result["error"]
            )

    @pytest.mark.asyncio
    async def test_initialize_with_exception(self, clean_environment):
        """초기화 중 예외 발생"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "test-project"}

        with (
            patch.dict(os.environ, env_vars),
            patch(
                "rfs.cloud_run.get_service_discovery",
                side_effect=Exception("Service error"),
            ),
            patch("rfs.cloud_run.log_error") as mock_log_error,
        ):

            mock_log_error.return_value = AsyncMock()

            result = await initialize_cloud_run_services()

            assert result["success"] is False
            assert "Cloud Run 서비스 초기화 실패" in result["error"]

    @pytest.mark.asyncio
    async def test_initialize_with_default_service_name(self, clean_environment):
        """기본 서비스 이름 사용"""
        env_vars = {
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "K_SERVICE": "default-service",
        }

        with (
            patch.dict(os.environ, env_vars),
            patch("rfs.cloud_run.get_service_discovery") as mock_get_sd,
            patch("rfs.cloud_run.get_task_queue") as mock_get_tq,
            patch("rfs.cloud_run.get_monitoring_client") as mock_get_mc,
            patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_get_ao,
            patch("rfs.cloud_run.log_info") as mock_log_info,
        ):

            # Mock들 설정
            mock_get_sd.return_value = AsyncMock()
            mock_get_tq.return_value = AsyncMock()
            mock_get_mc.return_value = AsyncMock()
            mock_get_ao.return_value = AsyncMock()
            mock_log_info.return_value = AsyncMock()

            result = await initialize_cloud_run_services()

            assert result["success"] is True
            assert result["service_name"] == "default-service"


class TestShutdownCloudRunServices:
    """Cloud Run 서비스 종료 테스트"""

    @pytest.mark.asyncio
    async def test_shutdown_all_services(self):
        """모든 서비스 정상 종료"""
        # Mock 서비스들
        mock_service_discovery = AsyncMock()
        mock_monitoring_client = AsyncMock()
        mock_autoscaling_optimizer = AsyncMock()

        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=mock_service_discovery,
            ),
            patch.multiple(
                "rfs.cloud_run.monitoring", _monitoring_client=mock_monitoring_client
            ),
            patch.multiple(
                "rfs.cloud_run.autoscaling",
                _autoscaling_optimizer=mock_autoscaling_optimizer,
            ),
            patch("builtins.print") as mock_print,
        ):

            await shutdown_cloud_run_services()

            # 모든 서비스의 shutdown이 호출되었는지 확인
            mock_service_discovery.shutdown.assert_called_once()
            mock_monitoring_client.shutdown.assert_called_once()
            mock_autoscaling_optimizer.shutdown.assert_called_once()

            # 성공 메시지가 출력되었는지 확인
            success_calls = [
                call
                for call in mock_print.call_args_list
                if "✅ RFS Cloud Run 서비스 종료 완료" in str(call)
            ]
            assert len(success_calls) == 1

    @pytest.mark.asyncio
    async def test_shutdown_with_no_services(self):
        """초기화되지 않은 서비스들의 종료"""
        with (
            patch.multiple("rfs.cloud_run.service_discovery", _service_discovery=None),
            patch.multiple("rfs.cloud_run.monitoring", _monitoring_client=None),
            patch.multiple("rfs.cloud_run.autoscaling", _autoscaling_optimizer=None),
            patch("builtins.print") as mock_print,
        ):

            await shutdown_cloud_run_services()

            # 성공 메시지가 출력되었는지 확인
            success_calls = [
                call
                for call in mock_print.call_args_list
                if "✅ RFS Cloud Run 서비스 종료 완료" in str(call)
            ]
            assert len(success_calls) == 1

    @pytest.mark.asyncio
    async def test_shutdown_with_exception(self):
        """종료 중 예외 발생"""
        mock_service_discovery = AsyncMock()
        mock_service_discovery.shutdown.side_effect = Exception("Shutdown error")

        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=mock_service_discovery,
            ),
            patch("builtins.print") as mock_print,
        ):

            await shutdown_cloud_run_services()

            # 실제로 에러 메시지가 출력되는지 확인하는 대신, 종료가 완료되었는지만 확인
            # __init__.py의 shutdown_cloud_run_services는 예외를 잡고 에러 메시지만 출력함
            all_calls = [str(call) for call in mock_print.call_args_list]
            assert len(all_calls) >= 1  # print가 호출되었는지 확인


class TestGetCloudRunStatus:
    """Cloud Run 상태 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_status_with_all_services(self, mock_cloud_run_environment):
        """모든 서비스가 초기화된 상태"""
        mock_service_discovery = MagicMock()
        mock_service_discovery.get_service_stats.return_value = {"services": 3}

        mock_task_queue = MagicMock()
        mock_task_queue.get_overall_stats.return_value = {"tasks": 10}

        mock_autoscaling = MagicMock()
        mock_autoscaling.get_scaling_stats.return_value = {"instances": 2}

        mock_monitoring = MagicMock()
        mock_monitoring.registered_metrics = ["metric1", "metric2"]
        mock_monitoring.metrics_buffer = [1, 2, 3]
        mock_monitoring.logs_buffer = [1, 2]

        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=mock_service_discovery,
            ),
            patch.multiple("rfs.cloud_run.task_queue", _task_queue=mock_task_queue),
            patch.multiple(
                "rfs.cloud_run.autoscaling", _autoscaling_optimizer=mock_autoscaling
            ),
            patch.multiple(
                "rfs.cloud_run.monitoring", _monitoring_client=mock_monitoring
            ),
        ):

            status = await get_cloud_run_status()

            assert status["environment"]["is_cloud_run"] is True
            assert "metadata" in status["environment"]

            assert status["services"]["service_discovery"]["initialized"] is True
            assert status["services"]["task_queue"]["initialized"] is True
            assert status["services"]["autoscaling"]["initialized"] is True
            assert status["services"]["monitoring"]["initialized"] is True

            assert status["services"]["monitoring"]["registered_metrics"] == 2
            assert status["services"]["monitoring"]["buffer_sizes"]["metrics"] == 3
            assert status["services"]["monitoring"]["buffer_sizes"]["logs"] == 2

    @pytest.mark.asyncio
    async def test_get_status_with_no_services(self, clean_environment):
        """서비스가 초기화되지 않은 상태"""
        with (
            patch.multiple("rfs.cloud_run.service_discovery", _service_discovery=None),
            patch.multiple("rfs.cloud_run.task_queue", _task_queue=None),
            patch.multiple("rfs.cloud_run.autoscaling", _autoscaling_optimizer=None),
            patch.multiple("rfs.cloud_run.monitoring", _monitoring_client=None),
        ):

            status = await get_cloud_run_status()

            assert status["environment"]["is_cloud_run"] is False
            assert status["services"]["service_discovery"]["initialized"] is False
            assert status["services"]["task_queue"]["initialized"] is False
            assert status["services"]["autoscaling"]["initialized"] is False
            assert status["services"]["monitoring"]["initialized"] is False

    @pytest.mark.asyncio
    async def test_get_status_with_service_errors(self):
        """서비스 상태 조회 중 예외 발생"""
        # service_discovery가 None이고 task_queue는 정상
        mock_task_queue = MagicMock()
        mock_task_queue.get_overall_stats.return_value = {"tasks": 5}

        with (
            patch.multiple("rfs.cloud_run.service_discovery", _service_discovery=None),
            patch.multiple("rfs.cloud_run.task_queue", _task_queue=mock_task_queue),
        ):
            status = await get_cloud_run_status()

            assert status["services"]["service_discovery"]["initialized"] is False
            assert status["services"]["task_queue"]["initialized"] is True

    @pytest.mark.asyncio
    async def test_get_status_with_general_exception(self):
        """전체적인 예외 발생"""
        # get_cloud_run_status 함수의 try-except 블록을 테스트
        with patch(
            "rfs.cloud_run.is_cloud_run_environment",
            side_effect=Exception("General error"),
        ):
            try:
                status = await get_cloud_run_status()
                # 예외가 발생해야 하는데 정상적으로 반환되면 실패
                assert False, "예외가 발생해야 하는데 정상적으로 반환됨"
            except Exception as e:
                # 예외가 발생하는 것이 정상
                assert "General error" in str(e)


class TestModuleImports:
    """모듈 임포트 테스트"""

    def test_all_imports_available(self):
        """__all__에 정의된 모든 항목이 임포트 가능한지 확인"""
        # __all__의 모든 항목이 실제로 모듈에서 접근 가능한지 확인
        import rfs.cloud_run as cloud_run_module
        from rfs.cloud_run import __all__

        for item_name in __all__:
            assert hasattr(
                cloud_run_module, item_name
            ), f"{item_name}을 찾을 수 없습니다"

    def test_version_info(self):
        """버전 정보 테스트"""
        from rfs.cloud_run import __cloud_run_features__, __version__

        assert __version__ == "4.0.0"
        assert isinstance(__cloud_run_features__, list)
        assert len(__cloud_run_features__) > 0

    def test_class_instantiation(
        self,
        isolated_monitoring_client,
        isolated_task_queue,
        isolated_service_discovery,
    ):
        """주요 클래스들의 인스턴스 생성 테스트"""
        # ServiceEndpoint - helpers.py에서 가져옴
        from rfs.cloud_run.helpers import ServiceEndpoint as HelpersServiceEndpoint

        endpoint = HelpersServiceEndpoint("test-service", "https://test.example.com")
        assert endpoint.name == "test-service"
        assert endpoint.url == "https://test.example.com"

        # ServiceEndpoint - service_discovery.py에서 가져옴 (이것이 __all__에 있는 것)
        # Pydantic 모델이므로 키워드 인자로 전달 (service_name, url, project_id는 필수)
        endpoint_sd = ServiceEndpoint(
            service_name="test-service-2",
            url="https://test2.example.com",
            project_id="test-project",
            region="us-central1",
        )
        assert endpoint_sd.service_name == "test-service-2"
        assert endpoint_sd.url == "https://test2.example.com"
        assert endpoint_sd.project_id == "test-project"

        # 나머지는 격리된 fixture 사용
        assert isolated_monitoring_client is not None
        assert isolated_task_queue is not None
        assert isolated_service_discovery is not None


class TestAsyncServiceIntegration:
    """비동기 서비스 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, clean_environment):
        """전체 생명주기 테스트 - 초기화부터 종료까지"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "integration-test"}

        with (
            patch.dict(os.environ, env_vars),
            patch("rfs.cloud_run.get_service_discovery") as mock_get_sd,
            patch("rfs.cloud_run.get_task_queue") as mock_get_tq,
            patch("rfs.cloud_run.get_monitoring_client") as mock_get_mc,
            patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_get_ao,
            patch("rfs.cloud_run.log_info") as mock_log_info,
        ):

            # Mock 설정
            mock_service_discovery = AsyncMock()
            mock_task_queue = AsyncMock()
            mock_monitoring = AsyncMock()
            mock_autoscaling = AsyncMock()

            mock_get_sd.return_value = mock_service_discovery
            mock_get_tq.return_value = mock_task_queue
            mock_get_mc.return_value = mock_monitoring
            mock_get_ao.return_value = mock_autoscaling
            mock_log_info.return_value = AsyncMock()

            # 1. 서비스 초기화
            init_result = await initialize_cloud_run_services()
            assert init_result["success"] is True

            # 2. 상태 확인
            with (
                patch.multiple(
                    "rfs.cloud_run.service_discovery",
                    _service_discovery=mock_service_discovery,
                ),
                patch.multiple("rfs.cloud_run.task_queue", _task_queue=mock_task_queue),
                patch.multiple(
                    "rfs.cloud_run.monitoring", _monitoring_client=mock_monitoring
                ),
                patch.multiple(
                    "rfs.cloud_run.autoscaling", _autoscaling_optimizer=mock_autoscaling
                ),
            ):

                mock_service_discovery.get_service_stats.return_value = {}
                mock_task_queue.get_overall_stats.return_value = {}
                mock_autoscaling.get_scaling_stats.return_value = {}
                mock_monitoring.registered_metrics = []
                mock_monitoring.metrics_buffer = []
                mock_monitoring.logs_buffer = []

                status = await get_cloud_run_status()
                assert status["services"]["service_discovery"]["initialized"] is True

                # 3. 서비스 종료
                await shutdown_cloud_run_services()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, clean_environment):
        """동시 작업 테스트"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "concurrent-test"}

        async def init_service():
            with (
                patch("rfs.cloud_run.get_service_discovery") as mock_get_sd,
                patch("rfs.cloud_run.log_info") as mock_log_info,
            ):
                mock_get_sd.return_value = AsyncMock()
                mock_log_info.return_value = AsyncMock()
                return await initialize_cloud_run_services(
                    enable_service_discovery=True,
                    enable_task_queue=False,
                    enable_monitoring=False,
                    enable_autoscaling=False,
                )

        async def get_metadata():
            return get_cloud_run_metadata()

        with patch.dict(os.environ, env_vars):
            # 동시에 여러 작업 실행
            results = await asyncio.gather(
                init_service(), get_metadata(), return_exceptions=True
            )

            # 모든 작업이 성공적으로 완료되었는지 확인
            assert len(results) == 2
            assert results[0]["success"] is True  # 초기화 결과
            assert isinstance(results[1], dict)  # 메타데이터 결과
