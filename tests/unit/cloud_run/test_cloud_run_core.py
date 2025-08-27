"""
Cloud Run 핵심 모듈 테스트

Google Cloud Run 환경 검출, 메타데이터 처리, 서비스 초기화/종료 등을 테스트
"""

import asyncio
import os
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs import Failure, Result, Success
from rfs.cloud_run import (
    get_cloud_run_metadata,
    get_cloud_run_status,
    initialize_cloud_run_services,
    is_cloud_run_environment,
    shutdown_cloud_run_services,
)


class TestCloudRunEnvironmentDetection:
    """Cloud Run 환경 검출 테스트"""

    def test_is_cloud_run_environment_true(self):
        """Cloud Run 환경에서 True 반환 테스트"""
        with patch.dict(os.environ, {"K_SERVICE": "test-service"}):
            result = is_cloud_run_environment()
            assert result is True

    def test_is_cloud_run_environment_false(self):
        """로컬 환경에서 False 반환 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            result = is_cloud_run_environment()
            assert result is False

    def test_is_cloud_run_environment_empty_k_service(self):
        """K_SERVICE가 빈 문자열일 때 True 반환 테스트 (키가 존재함)"""
        with patch.dict(os.environ, {"K_SERVICE": ""}):
            result = is_cloud_run_environment()
            # 빈 문자열도 K_SERVICE 키가 존재하는 것으로 간주
            assert result is True


class TestCloudRunMetadata:
    """Cloud Run 메타데이터 테스트"""

    def test_get_cloud_run_metadata_full(self):
        """모든 메타데이터가 설정된 경우 테스트"""
        env_vars = {
            "K_SERVICE": "test-service",
            "K_REVISION": "test-revision-001",
            "K_CONFIGURATION": "test-config",
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GOOGLE_CLOUD_REGION": "asia-northeast3",
            "PORT": "8080",
        }

        with patch.dict(os.environ, env_vars):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "test-service"
            assert metadata["revision"] == "test-revision-001"
            assert metadata["configuration"] == "test-config"
            assert metadata["project_id"] == "test-project"
            assert metadata["region"] == "asia-northeast3"
            assert metadata["port"] == "8080"

    def test_get_cloud_run_metadata_minimal(self):
        """메타데이터가 설정되지 않은 경우 기본값 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "unknown"
            assert metadata["revision"] == "unknown"
            assert metadata["configuration"] == "unknown"
            assert metadata["project_id"] == "unknown"
            assert metadata["region"] == "unknown"
            assert metadata["port"] == "8080"  # 기본 포트

    def test_get_cloud_run_metadata_partial(self):
        """일부 메타데이터만 설정된 경우 테스트"""
        env_vars = {
            "K_SERVICE": "partial-service",
            "GOOGLE_CLOUD_PROJECT": "partial-project",
            "PORT": "9090",
        }

        with patch.dict(os.environ, env_vars):
            metadata = get_cloud_run_metadata()

            assert metadata["service_name"] == "partial-service"
            assert metadata["project_id"] == "partial-project"
            assert metadata["port"] == "9090"
            assert metadata["revision"] == "unknown"
            assert metadata["configuration"] == "unknown"
            assert metadata["region"] == "unknown"


class TestCloudRunServiceInitialization:
    """Cloud Run 서비스 초기화 테스트"""

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_success(self):
        """모든 서비스 초기화 성공 테스트"""
        project_id = "test-project"
        service_name = "test-service"

        mock_service_discovery = Mock()
        mock_task_queue = Mock()
        mock_monitoring_client = Mock()
        mock_autoscaling_optimizer = Mock()

        with patch(
            "rfs.cloud_run.get_service_discovery", return_value=mock_service_discovery
        ) as mock_get_sd:
            with patch(
                "rfs.cloud_run.get_task_queue", return_value=mock_task_queue
            ) as mock_get_tq:
                with patch(
                    "rfs.cloud_run.get_monitoring_client",
                    return_value=mock_monitoring_client,
                ) as mock_get_mc:
                    with patch(
                        "rfs.cloud_run.get_autoscaling_optimizer",
                        return_value=mock_autoscaling_optimizer,
                    ) as mock_get_ao:
                        with patch(
                            "rfs.cloud_run.log_info", new_callable=AsyncMock
                        ) as mock_log:
                            result = await initialize_cloud_run_services(
                                project_id=project_id, service_name=service_name
                            )

                            assert result["success"] is True
                            assert result["project_id"] == project_id
                            assert result["service_name"] == service_name
                            assert "service_discovery" in result["initialized_services"]
                            assert "task_queue" in result["initialized_services"]
                            assert "monitoring" in result["initialized_services"]
                            assert "autoscaling" in result["initialized_services"]

                            mock_get_sd.assert_called_once_with(project_id)
                            mock_get_tq.assert_called_once_with(project_id)
                            mock_get_mc.assert_called_once_with(project_id)
                            mock_get_ao.assert_called_once_with(
                                project_id, service_name
                            )

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_with_env_vars(self):
        """환경변수에서 프로젝트 ID와 서비스명 읽기 테스트"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "env-project", "K_SERVICE": "env-service"}

        mock_service_discovery = Mock()

        with patch.dict(os.environ, env_vars):
            with patch(
                "rfs.cloud_run.get_service_discovery",
                return_value=mock_service_discovery,
            ):
                with patch("rfs.cloud_run.get_task_queue", return_value=Mock()):
                    with patch(
                        "rfs.cloud_run.get_monitoring_client", return_value=Mock()
                    ):
                        with patch(
                            "rfs.cloud_run.get_autoscaling_optimizer",
                            return_value=Mock(),
                        ):
                            with patch(
                                "rfs.cloud_run.log_info", new_callable=AsyncMock
                            ):
                                result = await initialize_cloud_run_services()

                                assert result["success"] is True
                                assert result["project_id"] == "env-project"
                                assert result["service_name"] == "env-service"

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_selective_disable(self):
        """선택적 서비스 비활성화 테스트"""
        project_id = "test-project"

        with patch(
            "rfs.cloud_run.get_service_discovery", return_value=Mock()
        ) as mock_get_sd:
            with patch(
                "rfs.cloud_run.get_task_queue", return_value=Mock()
            ) as mock_get_tq:
                result = await initialize_cloud_run_services(
                    project_id=project_id,
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

                mock_get_sd.assert_called_once()
                mock_get_tq.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_missing_project_id(self):
        """프로젝트 ID가 없을 때 에러 처리 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            result = await initialize_cloud_run_services()

            assert result["success"] is False
            assert (
                "GOOGLE_CLOUD_PROJECT 환경 변수가 설정되지 않았습니다"
                in result["error"]
            )

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_exception_handling(self):
        """서비스 초기화 중 예외 발생 시 처리 테스트"""
        project_id = "test-project"

        with patch(
            "rfs.cloud_run.get_service_discovery",
            side_effect=Exception("Service discovery error"),
        ):
            with patch(
                "rfs.cloud_run.log_error", new_callable=AsyncMock
            ) as mock_log_error:
                result = await initialize_cloud_run_services(
                    project_id=project_id,
                    enable_task_queue=False,
                    enable_monitoring=False,
                    enable_autoscaling=False,
                )

                assert result["success"] is False
                assert "Cloud Run 서비스 초기화 실패" in result["error"]


class TestCloudRunServiceShutdown:
    """Cloud Run 서비스 종료 테스트"""

    @pytest.mark.asyncio
    async def test_shutdown_cloud_run_services_success(self):
        """서비스 종료 성공 테스트"""
        mock_service_discovery = Mock()
        mock_service_discovery.shutdown = AsyncMock()
        mock_monitoring_client = Mock()
        mock_monitoring_client.shutdown = AsyncMock()
        mock_autoscaling_optimizer = Mock()
        mock_autoscaling_optimizer.shutdown = AsyncMock()

        with patch(
            "rfs.cloud_run.service_discovery._service_discovery", mock_service_discovery
        ):
            with patch(
                "rfs.cloud_run.monitoring._monitoring_client", mock_monitoring_client
            ):
                with patch(
                    "rfs.cloud_run.autoscaling._autoscaling_optimizer",
                    mock_autoscaling_optimizer,
                ):
                    with patch("builtins.print") as mock_print:
                        await shutdown_cloud_run_services()

                        mock_service_discovery.shutdown.assert_called_once()
                        mock_monitoring_client.shutdown.assert_called_once()
                        mock_autoscaling_optimizer.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_cloud_run_services_with_none_services(self):
        """초기화되지 않은 서비스들 종료 테스트"""
        with patch("rfs.cloud_run.service_discovery._service_discovery", None):
            with patch("rfs.cloud_run.monitoring._monitoring_client", None):
                with patch("rfs.cloud_run.autoscaling._autoscaling_optimizer", None):
                    with patch("builtins.print") as mock_print:
                        await shutdown_cloud_run_services()

                        # 예외 없이 완료되어야 함
                        assert mock_print.called

    @pytest.mark.asyncio
    async def test_shutdown_cloud_run_services_with_exception(self):
        """서비스 종료 중 예외 발생 테스트"""
        with patch(
            "rfs.cloud_run.service_discovery._service_discovery",
            side_effect=Exception("Import error"),
        ):
            with patch("builtins.print") as mock_print:
                await shutdown_cloud_run_services()

                # 예외가 발생해도 프로그램이 중단되지 않아야 함
                assert mock_print.called


class TestCloudRunStatus:
    """Cloud Run 상태 확인 테스트"""

    @pytest.mark.asyncio
    async def test_get_cloud_run_status_success(self):
        """상태 확인 성공 테스트"""
        env_vars = {
            "K_SERVICE": "status-test-service",
            "GOOGLE_CLOUD_PROJECT": "status-test-project",
        }

        mock_service_discovery = Mock()
        mock_service_discovery.get_service_stats.return_value = {"active_services": 5}

        mock_task_queue = Mock()
        mock_task_queue.get_overall_stats.return_value = {"pending_tasks": 3}

        mock_autoscaling = Mock()
        mock_autoscaling.get_scaling_stats.return_value = {"current_instances": 2}

        mock_monitoring = Mock()
        mock_monitoring.registered_metrics = ["cpu", "memory"]
        mock_monitoring.metrics_buffer = [1, 2, 3]
        mock_monitoring.logs_buffer = [1, 2]

        with patch.dict(os.environ, env_vars):
            with patch(
                "rfs.cloud_run.service_discovery._service_discovery",
                mock_service_discovery,
            ):
                with patch("rfs.cloud_run.task_queue._task_queue", mock_task_queue):
                    with patch(
                        "rfs.cloud_run.autoscaling._autoscaling_optimizer",
                        mock_autoscaling,
                    ):
                        with patch(
                            "rfs.cloud_run.monitoring._monitoring_client",
                            mock_monitoring,
                        ):
                            status = await get_cloud_run_status()

                            assert status["environment"]["is_cloud_run"] is True
                            assert (
                                status["environment"]["metadata"]["service_name"]
                                == "status-test-service"
                            )
                            assert (
                                status["services"]["service_discovery"]["initialized"]
                                is True
                            )
                            assert (
                                status["services"]["task_queue"]["initialized"] is True
                            )
                            assert (
                                status["services"]["autoscaling"]["initialized"] is True
                            )
                            assert (
                                status["services"]["monitoring"]["initialized"] is True
                            )

    @pytest.mark.asyncio
    async def test_get_cloud_run_status_no_services_initialized(self):
        """서비스가 초기화되지 않은 상태 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("rfs.cloud_run.service_discovery._service_discovery", None):
                with patch("rfs.cloud_run.task_queue._task_queue", None):
                    with patch(
                        "rfs.cloud_run.autoscaling._autoscaling_optimizer", None
                    ):
                        with patch("rfs.cloud_run.monitoring._monitoring_client", None):
                            status = await get_cloud_run_status()

                            assert status["environment"]["is_cloud_run"] is False
                            assert (
                                status["services"]["service_discovery"]["initialized"]
                                is False
                            )
                            assert (
                                status["services"]["task_queue"]["initialized"] is False
                            )
                            assert (
                                status["services"]["autoscaling"]["initialized"]
                                is False
                            )
                            assert (
                                status["services"]["monitoring"]["initialized"] is False
                            )

    @pytest.mark.asyncio
    async def test_get_cloud_run_status_with_service_errors(self):
        """서비스 상태 확인 중 에러 발생 테스트"""
        with patch(
            "rfs.cloud_run.service_discovery._service_discovery",
            side_effect=Exception("Service discovery error"),
        ):
            with patch(
                "rfs.cloud_run.task_queue._task_queue",
                side_effect=Exception("Task queue error"),
            ):
                status = await get_cloud_run_status()

                assert "error" in status["services"]["service_discovery"]
                assert "error" in status["services"]["task_queue"]


class TestCloudRunIntegration:
    """Cloud Run 통합 테스트"""

    def test_cloud_run_module_attributes(self):
        """모듈 속성 테스트"""
        from rfs.cloud_run import __cloud_run_features__, __version__

        assert __version__ == "4.0.0"
        assert isinstance(__cloud_run_features__, list)
        assert len(__cloud_run_features__) > 0
        assert "Service Discovery with Circuit Breakers" in __cloud_run_features__

    @pytest.mark.asyncio
    async def test_full_service_lifecycle(self):
        """전체 서비스 생명주기 테스트"""
        project_id = "lifecycle-test-project"
        service_name = "lifecycle-test-service"

        # Mock 서비스들
        mock_services = {
            "service_discovery": Mock(),
            "task_queue": Mock(),
            "monitoring_client": Mock(),
            "autoscaling_optimizer": Mock(),
        }

        # 모든 서비스에 shutdown 메서드 추가
        for service in mock_services.values():
            service.shutdown = AsyncMock()

        # 초기화 테스트
        with patch(
            "rfs.cloud_run.get_service_discovery",
            return_value=mock_services["service_discovery"],
        ):
            with patch(
                "rfs.cloud_run.get_task_queue", return_value=mock_services["task_queue"]
            ):
                with patch(
                    "rfs.cloud_run.get_monitoring_client",
                    return_value=mock_services["monitoring_client"],
                ):
                    with patch(
                        "rfs.cloud_run.get_autoscaling_optimizer",
                        return_value=mock_services["autoscaling_optimizer"],
                    ):
                        with patch("rfs.cloud_run.log_info", new_callable=AsyncMock):

                            # 초기화
                            init_result = await initialize_cloud_run_services(
                                project_id=project_id, service_name=service_name
                            )

                            assert init_result["success"] is True
                            assert len(init_result["initialized_services"]) == 4

                            # 상태 확인
                            with patch(
                                "rfs.cloud_run.service_discovery._service_discovery",
                                mock_services["service_discovery"],
                            ):
                                with patch(
                                    "rfs.cloud_run.task_queue._task_queue",
                                    mock_services["task_queue"],
                                ):
                                    with patch(
                                        "rfs.cloud_run.monitoring._monitoring_client",
                                        mock_services["monitoring_client"],
                                    ):
                                        with patch(
                                            "rfs.cloud_run.autoscaling._autoscaling_optimizer",
                                            mock_services["autoscaling_optimizer"],
                                        ):

                                            # 모든 서비스에 필요한 메서드들 설정
                                            mock_services[
                                                "service_discovery"
                                            ].get_service_stats = Mock(
                                                return_value={"active": 1}
                                            )
                                            mock_services[
                                                "task_queue"
                                            ].get_overall_stats = Mock(
                                                return_value={"pending": 0}
                                            )
                                            mock_services[
                                                "autoscaling_optimizer"
                                            ].get_scaling_stats = Mock(
                                                return_value={"instances": 1}
                                            )
                                            mock_services[
                                                "monitoring_client"
                                            ].registered_metrics = ["test"]
                                            mock_services[
                                                "monitoring_client"
                                            ].metrics_buffer = []
                                            mock_services[
                                                "monitoring_client"
                                            ].logs_buffer = []

                                            status = await get_cloud_run_status()

                                            assert all(
                                                service["initialized"]
                                                for service in status[
                                                    "services"
                                                ].values()
                                            )

                                            # 종료
                                            with patch("builtins.print"):
                                                await shutdown_cloud_run_services()

                                            # 모든 서비스의 shutdown이 호출되었는지 확인
                                            for service in mock_services.values():
                                                service.shutdown.assert_called()

    def test_result_pattern_integration(self):
        """Result 패턴 통합 테스트"""
        # Success 케이스
        success_result: Result[dict, str] = Success({"status": "ok"})
        assert success_result.is_success()
        assert success_result.get()["status"] == "ok"

        # Failure 케이스
        failure_result: Result[dict, str] = Failure("Service initialization failed")
        assert failure_result.is_failure()
        assert "Service initialization failed" in failure_result.get_error()

    @pytest.mark.parametrize(
        "env_vars,expected_is_cloud_run",
        [
            ({"K_SERVICE": "test"}, True),
            (
                {"K_SERVICE": "test-service", "GOOGLE_CLOUD_PROJECT": "test-project"},
                True,
            ),
            ({}, False),
            (
                {"GOOGLE_CLOUD_PROJECT": "test-project"},
                False,
            ),  # K_SERVICE가 없으면 False
        ],
    )
    def test_environment_detection_scenarios(self, env_vars, expected_is_cloud_run):
        """다양한 환경 시나리오에서 환경 검출 테스트"""
        with patch.dict(os.environ, env_vars, clear=True):
            result = is_cloud_run_environment()
            assert result == expected_is_cloud_run

    def test_metadata_consistency(self):
        """메타데이터 일관성 테스트"""
        test_env = {
            "K_SERVICE": "consistency-test",
            "K_REVISION": "rev-123",
            "GOOGLE_CLOUD_PROJECT": "consistency-project",
        }

        with patch.dict(os.environ, test_env):
            metadata1 = get_cloud_run_metadata()
            metadata2 = get_cloud_run_metadata()

            # 같은 환경에서 호출하면 같은 결과
            assert metadata1 == metadata2
            assert metadata1["service_name"] == "consistency-test"
            assert metadata1["revision"] == "rev-123"
            assert metadata1["project_id"] == "consistency-project"
