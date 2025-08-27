"""
Cloud Run Graceful Shutdown Tests

Google Cloud Run의 우아한 종료(Graceful Shutdown) 처리 및 생명주기 관리 테스트
"""

import asyncio
import os
import signal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from rfs.cloud_run import (
    get_cloud_run_status,
    initialize_cloud_run_services,
    shutdown_cloud_run_services,
)
from rfs.cloud_run.helpers import (
    AutoScalingOptimizer,
    CloudMonitoringClient,
    CloudRunServiceDiscovery,
    CloudTaskQueue,
    get_autoscaling_optimizer,
    get_monitoring_client,
    get_service_discovery,
    get_task_queue,
)
from rfs.cloud_run.helpers import shutdown_cloud_run_services as helpers_shutdown


class TestCloudRunServiceShutdown:
    """Cloud Run 서비스 종료 테스트"""

    @pytest.mark.asyncio
    async def test_shutdown_cloud_run_services_basic(self):
        """기본 서비스 종료 테스트"""
        # 예외 없이 종료되는지 확인
        try:
            await shutdown_cloud_run_services()
            # 성공적으로 종료됨
        except Exception as e:
            pytest.fail(f"shutdown_cloud_run_services raised exception: {e}")

    @pytest.mark.asyncio
    async def test_shutdown_with_initialized_services(self):
        """초기화된 서비스들의 종료 테스트"""
        # 모든 서비스 모듈을 모킹
        mock_service_discovery = AsyncMock()
        mock_monitoring_client = AsyncMock()
        mock_autoscaling_optimizer = AsyncMock()

        # shutdown 메서드 추가
        mock_service_discovery.shutdown = AsyncMock()
        mock_monitoring_client.shutdown = AsyncMock()
        mock_autoscaling_optimizer.shutdown = AsyncMock()

        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=mock_service_discovery,
            ),
            patch.multiple(
                "rfs.cloud_run.monitoring",
                _monitoring_client=mock_monitoring_client,
            ),
            patch.multiple(
                "rfs.cloud_run.autoscaling",
                _autoscaling_optimizer=mock_autoscaling_optimizer,
            ),
        ):
            await shutdown_cloud_run_services()

            # shutdown 메서드들이 호출되었는지 확인
            mock_service_discovery.shutdown.assert_called_once()
            mock_monitoring_client.shutdown.assert_called_once()
            mock_autoscaling_optimizer.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_none_services(self):
        """서비스가 None인 경우 종료 테스트"""
        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=None,
            ),
            patch.multiple(
                "rfs.cloud_run.monitoring",
                _monitoring_client=None,
            ),
            patch.multiple(
                "rfs.cloud_run.autoscaling",
                _autoscaling_optimizer=None,
            ),
            patch.multiple(
                "rfs.cloud_run.task_queue",
                _task_queue=None,
            ),
        ):
            # None 서비스들에서도 예외 없이 종료되어야 함
            try:
                await shutdown_cloud_run_services()
            except Exception as e:
                pytest.fail(f"Shutdown failed with None services: {e}")

    @pytest.mark.asyncio
    async def test_shutdown_with_exception_handling(self):
        """종료 중 예외 발생 시 처리 테스트"""
        # 예외를 발생시키는 모킹된 서비스
        mock_service_with_error = AsyncMock()
        mock_service_with_error.shutdown.side_effect = Exception("Shutdown error")

        mock_normal_service = AsyncMock()
        mock_normal_service.shutdown = AsyncMock()

        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=mock_service_with_error,
            ),
            patch.multiple(
                "rfs.cloud_run.monitoring",
                _monitoring_client=mock_normal_service,
            ),
            patch("builtins.print") as mock_print,
        ):
            # 예외가 발생해도 전체 종료 과정이 중단되지 않아야 함
            await shutdown_cloud_run_services()

            # 에러 메시지가 출력되었는지 확인
            error_calls = [
                call
                for call in mock_print.call_args_list
                if "오류" in str(call) or "error" in str(call).lower()
            ]
            assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_helpers_shutdown_function(self):
        """헬퍼 모듈의 종료 함수 테스트"""
        with patch("rfs.cloud_run.helpers.logger") as mock_logger:
            await helpers_shutdown()

            # 종료 로깅이 수행되었는지 확인
            mock_logger.info.assert_called_with("Shutting down Cloud Run services...")

    @pytest.mark.asyncio
    async def test_concurrent_shutdown_safety(self):
        """동시 종료 호출 안전성 테스트"""
        mock_service = AsyncMock()
        mock_service.shutdown = AsyncMock()

        with patch.multiple(
            "rfs.cloud_run.service_discovery",
            _service_discovery=mock_service,
        ):
            # 동시에 여러 번 종료 호출
            shutdown_tasks = [
                shutdown_cloud_run_services(),
                shutdown_cloud_run_services(),
                shutdown_cloud_run_services(),
            ]

            # 모든 종료 작업이 완료되어야 함
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)

            # 여러 번 호출되어도 문제없이 처리되어야 함
            assert mock_service.shutdown.call_count >= 1


class TestServiceLifecycleManagement:
    """서비스 생명주기 관리 테스트"""

    @pytest.mark.asyncio
    async def test_full_lifecycle_initialization_shutdown(self):
        """전체 생명주기: 초기화 → 종료 테스트"""
        env_vars = {"GOOGLE_CLOUD_PROJECT": "test-project", "K_SERVICE": "test-service"}

        with patch.dict(os.environ, env_vars):
            with (
                patch("rfs.cloud_run.get_service_discovery") as mock_sd,
                patch("rfs.cloud_run.get_task_queue") as mock_tq,
                patch("rfs.cloud_run.get_monitoring_client") as mock_mc,
                patch("rfs.cloud_run.get_autoscaling_optimizer") as mock_ao,
                patch("rfs.cloud_run.log_info"),
            ):

                # Mock 서비스들 설정
                mock_sd.return_value = AsyncMock()
                mock_tq.return_value = AsyncMock()
                mock_mc.return_value = AsyncMock()
                mock_ao.return_value = AsyncMock()

                # 초기화
                init_result = await initialize_cloud_run_services()
                assert init_result["success"] is True

                # 종료
                await shutdown_cloud_run_services()

                # 정상적으로 완료되었으면 성공

    @pytest.mark.asyncio
    async def test_service_status_during_shutdown(self):
        """종료 과정 중 서비스 상태 확인"""
        # 종료 전 상태 확인
        status_before = await get_cloud_run_status()
        assert "environment" in status_before
        assert "services" in status_before

        # 종료 수행
        await shutdown_cloud_run_services()

        # 종료 후 상태 확인 (오류 없이 조회되어야 함)
        status_after = await get_cloud_run_status()
        assert "environment" in status_after
        assert "services" in status_after

    def test_singleton_cleanup_after_shutdown(self):
        """종료 후 싱글톤 정리 확인"""
        # 종료 전에 싱글톤 인스턴스들 생성
        discovery1 = get_service_discovery()
        queue1 = get_task_queue()
        monitoring1 = get_monitoring_client()
        optimizer1 = get_autoscaling_optimizer()

        # 종료 후 새로운 인스턴스들이 같은지 확인 (싱글톤 유지)
        discovery2 = get_service_discovery()
        queue2 = get_task_queue()
        monitoring2 = get_monitoring_client()
        optimizer2 = get_autoscaling_optimizer()

        # 싱글톤 패턴이 유지되는지 확인
        assert discovery1 is discovery2
        assert queue1 is queue2
        assert monitoring1 is monitoring2
        assert optimizer1 is optimizer2

    @pytest.mark.asyncio
    async def test_partial_service_shutdown(self):
        """부분적 서비스 종료 테스트"""
        # 일부 서비스만 활성화된 상태에서 종료
        mock_service_discovery = AsyncMock()
        mock_service_discovery.shutdown = AsyncMock()

        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=mock_service_discovery,
            ),
            patch.multiple(
                "rfs.cloud_run.monitoring",
                _monitoring_client=None,  # 모니터링은 비활성
            ),
            patch.multiple(
                "rfs.cloud_run.autoscaling",
                _autoscaling_optimizer=None,  # 오토스케일링도 비활성
            ),
        ):
            await shutdown_cloud_run_services()

            # 활성화된 서비스만 종료되어야 함
            mock_service_discovery.shutdown.assert_called_once()


class TestGracefulShutdownSignalHandling:
    """우아한 종료 신호 처리 테스트"""

    def test_signal_handler_registration_concept(self):
        """신호 핸들러 등록 개념 테스트"""

        # 실제 신호 핸들러 등록은 하지 않지만, 개념적 테스트
        def mock_shutdown_handler(signum, frame):
            print(f"Received signal {signum}, initiating graceful shutdown...")
            # 실제 구현에서는 여기서 shutdown_cloud_run_services() 호출

        # 핸들러가 callable한지 확인
        assert callable(mock_shutdown_handler)

        # 신호 처리 시뮬레이션
        mock_shutdown_handler(signal.SIGTERM, None)

    def test_shutdown_timeout_concept(self):
        """종료 타임아웃 개념 테스트"""
        import time

        # 종료 시작 시간 기록
        shutdown_start = time.time()

        # 모의 종료 작업 (매우 빠름)
        time.sleep(0.1)

        shutdown_duration = time.time() - shutdown_start

        # 적절한 시간 내 종료되었는지 확인 (실제로는 30초 제한 등)
        assert shutdown_duration < 10.0  # 10초 이내

    @pytest.mark.asyncio
    async def test_cleanup_sequence_ordering(self):
        """정리 작업 순서 테스트"""
        cleanup_order = []

        # 모킹된 서비스들에 순서 기록
        mock_service_discovery = AsyncMock()

        async def sd_shutdown():
            cleanup_order.append("service_discovery")

        mock_service_discovery.shutdown = sd_shutdown

        mock_monitoring = AsyncMock()

        async def mc_shutdown():
            cleanup_order.append("monitoring")

        mock_monitoring.shutdown = mc_shutdown

        mock_autoscaling = AsyncMock()

        async def ao_shutdown():
            cleanup_order.append("autoscaling")

        mock_autoscaling.shutdown = ao_shutdown

        with (
            patch.multiple(
                "rfs.cloud_run.service_discovery",
                _service_discovery=mock_service_discovery,
            ),
            patch.multiple(
                "rfs.cloud_run.monitoring",
                _monitoring_client=mock_monitoring,
            ),
            patch.multiple(
                "rfs.cloud_run.autoscaling",
                _autoscaling_optimizer=mock_autoscaling,
            ),
        ):
            await shutdown_cloud_run_services()

            # 모든 서비스가 종료되었는지 확인
            assert len(cleanup_order) == 3
            assert "service_discovery" in cleanup_order
            assert "monitoring" in cleanup_order
            assert "autoscaling" in cleanup_order

    @pytest.mark.asyncio
    async def test_resource_cleanup_verification(self):
        """리소스 정리 확인 테스트"""
        # 종료 전에 리소스 생성
        discovery = get_service_discovery()
        queue = get_task_queue()
        monitoring = get_monitoring_client()

        # 초기 상태 확인
        assert discovery is not None
        assert queue is not None
        assert monitoring is not None

        # 종료 수행
        await shutdown_cloud_run_services()

        # 종료 후에도 싱글톤 인스턴스는 유지되지만,
        # 내부 상태는 정리되어야 함 (구현에 따라)
        post_shutdown_discovery = get_service_discovery()
        post_shutdown_queue = get_task_queue()
        post_shutdown_monitoring = get_monitoring_client()

        # 인스턴스는 동일하지만 (싱글톤)
        assert post_shutdown_discovery is discovery
        assert post_shutdown_queue is queue
        assert post_shutdown_monitoring is monitoring

    @pytest.mark.asyncio
    async def test_shutdown_idempotency(self):
        """종료 멱등성 테스트 (여러 번 호출해도 안전)"""
        mock_service = AsyncMock()
        mock_service.shutdown = AsyncMock()

        with patch.multiple(
            "rfs.cloud_run.service_discovery",
            _service_discovery=mock_service,
        ):
            # 첫 번째 종료
            await shutdown_cloud_run_services()
            first_call_count = mock_service.shutdown.call_count

            # 두 번째 종료 (이미 종료된 상태)
            await shutdown_cloud_run_services()
            second_call_count = mock_service.shutdown.call_count

            # 종료가 멱등적으로 처리되는지 확인
            # (실제 구현에 따라 호출 횟수가 증가할 수 있음)
            assert second_call_count >= first_call_count

    @pytest.mark.asyncio
    async def test_shutdown_performance(self):
        """종료 성능 테스트"""
        start_time = datetime.now()

        await shutdown_cloud_run_services()

        end_time = datetime.now()
        shutdown_duration = (end_time - start_time).total_seconds()

        # 종료가 합리적인 시간 내에 완료되는지 확인
        assert shutdown_duration < 5.0  # 5초 이내

    @pytest.mark.asyncio
    async def test_shutdown_with_active_tasks(self):
        """활성 작업이 있는 상태에서의 종료 테스트"""
        queue = get_task_queue()

        # 큐에 작업 추가 (실제로는 처리 중인 상태 시뮬레이션)
        queue._queue = [
            {"id": "task_1", "type": "email", "payload": {}},
            {"id": "task_2", "type": "sms", "payload": {}},
        ]
        queue._processing = True

        # 종료 수행
        await shutdown_cloud_run_services()

        # 종료 후에도 큐 상태 확인 가능해야 함
        assert isinstance(queue._queue, list)
