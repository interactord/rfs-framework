"""
Cloud Run Missing Coverage Areas Tests

helpers.py의 미커버 영역들을 집중적으로 테스트하여 커버리지 향상
- 예외 처리 블록들
- 조건부 실행 경로들
- 스케일링 로직
- 초기화 및 설정 로직
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from rfs.cloud_run.helpers import (
    AutoScalingOptimizer,
    call_service,
    get_autoscaling_optimizer,
    get_scaling_stats,
    initialize_cloud_run_services,
    is_cloud_run_environment,
    optimize_scaling,
)
from rfs.core.result import Failure, Success


class TestServiceCallExceptionHandling:
    """서비스 호출 예외 처리 테스트 (174-175번 라인)"""

    @pytest.mark.asyncio
    async def test_call_service_with_mock_exception(self):
        """서비스 호출 중 예외 발생 시 Failure 반환 테스트"""

        # call_service 함수 내부에서 예외가 발생하도록 설정
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
            mock_discovery = MagicMock()

            # 정상적인 endpoint를 반환하지만, 실제 호출에서 예외 발생
            from rfs.cloud_run.helpers import ServiceEndpoint

            endpoint = ServiceEndpoint("test-service", "https://test.example.com")
            endpoint.is_healthy = True
            mock_discovery.get_service.return_value = endpoint
            mock_get_sd.return_value = mock_discovery

            # datetime.now()에서 예외 발생하도록 패치
            with patch("rfs.cloud_run.helpers.datetime") as mock_datetime:
                mock_datetime.now.side_effect = Exception("Timestamp error")

                result = await call_service("test-service", "/api/test")

                # 예외가 Failure로 변환되었는지 확인
                assert isinstance(result, Failure)
                assert "Timestamp error" in result.error

    @pytest.mark.asyncio
    async def test_call_service_response_creation_exception(self):
        """응답 생성 중 예외 발생 테스트"""

        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
            mock_discovery = MagicMock()

            from rfs.cloud_run.helpers import ServiceEndpoint

            endpoint = ServiceEndpoint("test-service", "https://test.example.com")
            endpoint.is_healthy = True
            mock_discovery.get_service.return_value = endpoint
            mock_get_sd.return_value = mock_discovery

            # isoformat() 메서드에서 예외 발생하도록 설정
            with patch("rfs.cloud_run.helpers.datetime") as mock_datetime:
                mock_now = MagicMock()
                mock_now.isoformat.side_effect = ValueError("ISO format error")
                mock_datetime.now.return_value = mock_now

                result = await call_service("test-service", "/api/test")

                assert isinstance(result, Failure)
                assert "ISO format error" in result.error


class TestAutoScalingOptimizerConfiguration:
    """AutoScaling 최적화기 설정 테스트 (415, 419, 428-438번 라인)"""

    def test_autoscaling_configure_method(self, isolated_monitoring_client):
        """configure 메서드 테스트"""
        optimizer = AutoScalingOptimizer()

        # 초기 설정 확인
        initial_config = optimizer._config.copy()

        # 설정 업데이트
        new_config = {
            "min_instances": 2,
            "max_instances": 200,
            "target_cpu": 80,
            "custom_setting": "test_value",
        }

        optimizer.configure(**new_config)

        # 설정이 병합되었는지 확인
        assert optimizer._config["min_instances"] == 2
        assert optimizer._config["max_instances"] == 200
        assert optimizer._config["target_cpu"] == 80
        assert optimizer._config["custom_setting"] == "test_value"

        # 기존 설정이 유지되는지 확인
        assert optimizer._config["target_memory"] == initial_config["target_memory"]
        assert (
            optimizer._config["scale_down_delay"] == initial_config["scale_down_delay"]
        )

    def test_analyze_metrics_hardcoded_returns(self):
        """analyze_metrics 메서드의 하드코딩된 반환값 테스트"""
        optimizer = AutoScalingOptimizer()

        # 현재 구현은 하드코딩된 값을 반환
        result = optimizer.analyze_metrics()

        # 예상되는 키들이 모두 있는지 확인
        expected_keys = [
            "should_scale_up",
            "should_scale_down",
            "current_instances",
            "recommended_instances",
        ]
        for key in expected_keys:
            assert key in result

        # 기본값들 확인
        assert result["should_scale_up"] is False
        assert result["should_scale_down"] is False
        assert result["current_instances"] == 1
        assert result["recommended_instances"] == 1

    def test_get_recommendations_no_scaling_needed(self):
        """스케일링이 필요하지 않을 때 권장사항 테스트"""
        optimizer = AutoScalingOptimizer()

        # analyze_metrics가 스케일링 불필요를 반환하도록 패치
        with patch.object(optimizer, "analyze_metrics") as mock_analyze:
            mock_analyze.return_value = {
                "should_scale_up": False,
                "should_scale_down": False,
                "current_instances": 1,
                "recommended_instances": 1,
            }

            recommendations = optimizer.get_recommendations()

            # 스케일링 불필요 시 빈 리스트 반환
            assert recommendations == []

    def test_get_recommendations_scale_up(self):
        """스케일 업 권장사항 테스트 (430-433번 라인)"""
        optimizer = AutoScalingOptimizer()

        # 스케일 업이 필요한 상황 시뮬레이션
        with patch.object(optimizer, "analyze_metrics") as mock_analyze:
            mock_analyze.return_value = {
                "should_scale_up": True,
                "should_scale_down": False,
                "current_instances": 1,
                "recommended_instances": 5,
            }

            recommendations = optimizer.get_recommendations()

            assert len(recommendations) == 1
            assert "Scale up to 5 instances" in recommendations[0]

    def test_get_recommendations_scale_down(self):
        """스케일 다운 권장사항 테스트 (434-437번 라인)"""
        optimizer = AutoScalingOptimizer()

        # 스케일 다운이 필요한 상황 시뮬레이션
        with patch.object(optimizer, "analyze_metrics") as mock_analyze:
            mock_analyze.return_value = {
                "should_scale_up": False,
                "should_scale_down": True,
                "current_instances": 10,
                "recommended_instances": 3,
            }

            recommendations = optimizer.get_recommendations()

            assert len(recommendations) == 1
            assert "Scale down to 3 instances" in recommendations[0]

    def test_get_recommendations_missing_recommended_instances(self):
        """recommended_instances가 없는 경우 테스트"""
        optimizer = AutoScalingOptimizer()

        # recommended_instances 키가 없는 분석 결과
        with patch.object(optimizer, "analyze_metrics") as mock_analyze:
            mock_analyze.return_value = {
                "should_scale_up": True,
                "should_scale_down": False,
                "current_instances": 1,
                # recommended_instances 키 누락
            }

            recommendations = optimizer.get_recommendations()

            # get() 메서드 사용으로 None이 반환되어 "None instances"가 포함됨
            assert len(recommendations) == 1
            assert "Scale up to None instances" in recommendations[0]


class TestScalingHelperFunctions:
    """스케일링 헬퍼 함수들 테스트 (458-462, 472-473번 라인)"""

    def test_optimize_scaling_function(self):
        """optimize_scaling 함수 테스트"""

        with patch(
            "rfs.cloud_run.helpers.get_autoscaling_optimizer"
        ) as mock_get_optimizer:
            mock_optimizer = MagicMock(spec=AutoScalingOptimizer)
            mock_optimizer.get_recommendations.return_value = [
                "Scale up to 5 instances",
                "Increase memory allocation",
            ]
            mock_get_optimizer.return_value = mock_optimizer

            with patch("rfs.cloud_run.helpers.logger") as mock_logger:
                # 설정으로 함수 호출
                optimize_scaling(
                    min_instances=1, max_instances=10, target_cpu=75, custom_metric=100
                )

                # optimizer의 configure가 호출되었는지 확인
                mock_optimizer.configure.assert_called_once_with(
                    min_instances=1, max_instances=10, target_cpu=75, custom_metric=100
                )

                # 권장사항들이 로깅되었는지 확인
                assert mock_logger.info.call_count == 2
                mock_logger.info.assert_any_call(
                    "Scaling recommendation: Scale up to 5 instances"
                )
                mock_logger.info.assert_any_call(
                    "Scaling recommendation: Increase memory allocation"
                )

    def test_get_scaling_stats_function(self):
        """get_scaling_stats 함수 테스트 (472-473번 라인)"""

        with patch(
            "rfs.cloud_run.helpers.get_autoscaling_optimizer"
        ) as mock_get_optimizer:
            mock_optimizer = MagicMock(spec=AutoScalingOptimizer)
            expected_stats = {
                "current_instances": 3,
                "recommended_instances": 5,
                "cpu_usage": 85.2,
                "memory_usage": 67.3,
            }
            mock_optimizer.analyze_metrics.return_value = expected_stats
            mock_get_optimizer.return_value = mock_optimizer

            # 함수 호출 및 결과 확인
            result = get_scaling_stats()

            assert result == expected_stats
            mock_optimizer.analyze_metrics.assert_called_once()

    def test_get_autoscaling_optimizer_singleton(self):
        """get_autoscaling_optimizer 싱글톤 확인"""
        optimizer1 = get_autoscaling_optimizer()
        optimizer2 = get_autoscaling_optimizer()

        assert optimizer1 is optimizer2
        assert isinstance(optimizer1, AutoScalingOptimizer)


class TestInitializationLogic:
    """초기화 로직 테스트 (478-486번 라인)"""

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_in_cloud_run_env(self):
        """Cloud Run 환경에서 서비스 초기화 테스트"""

        with (
            patch("rfs.cloud_run.helpers.is_cloud_run_environment", return_value=True),
            patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd,
            patch("rfs.cloud_run.helpers.get_monitoring_client") as mock_get_mc,
            patch("rfs.cloud_run.helpers.logger") as mock_logger,
        ):

            # Mock 객체들 설정
            mock_discovery = AsyncMock()
            mock_monitoring = MagicMock()
            mock_get_sd.return_value = mock_discovery
            mock_get_mc.return_value = mock_monitoring

            # 함수 호출
            await initialize_cloud_run_services()

            # 각 컴포넌트가 초기화되었는지 확인
            mock_discovery.initialize.assert_called_once()
            mock_monitoring.log.assert_called_once_with(
                "INFO", "Cloud Run services initialized"
            )

            # 로깅이 수행되었는지 확인
            assert mock_logger.info.call_count == 2
            mock_logger.info.assert_any_call("Initializing Cloud Run services...")
            mock_logger.info.assert_any_call(
                "Cloud Run services initialized successfully"
            )

    @pytest.mark.asyncio
    async def test_initialize_cloud_run_services_not_in_cloud_run_env(self):
        """Cloud Run이 아닌 환경에서 서비스 초기화 테스트"""

        with (
            patch("rfs.cloud_run.helpers.is_cloud_run_environment", return_value=False),
            patch("rfs.cloud_run.helpers.logger") as mock_logger,
        ):

            # 함수 호출
            await initialize_cloud_run_services()

            # Cloud Run이 아닌 환경 메시지 로깅 확인
            mock_logger.info.assert_called_once_with(
                "Not running in Cloud Run environment"
            )

    def test_is_cloud_run_environment_various_combinations(self):
        """다양한 환경 변수 조합에서 Cloud Run 감지 테스트"""

        # 모든 변수가 없는 경우
        with patch.dict(os.environ, {}, clear=True):
            assert is_cloud_run_environment() is False

        # K_SERVICE만 있는 경우
        with patch.dict(os.environ, {"K_SERVICE": "test"}, clear=True):
            assert is_cloud_run_environment() is True

        # K_REVISION만 있는 경우
        with patch.dict(os.environ, {"K_REVISION": "test-rev"}, clear=True):
            assert is_cloud_run_environment() is True

        # K_CONFIGURATION만 있는 경우
        with patch.dict(os.environ, {"K_CONFIGURATION": "test-config"}, clear=True):
            assert is_cloud_run_environment() is True

        # CLOUD_RUN_JOB만 있는 경우
        with patch.dict(os.environ, {"CLOUD_RUN_JOB": "test-job"}, clear=True):
            assert is_cloud_run_environment() is True

        # 여러 변수가 함께 있는 경우
        with patch.dict(
            os.environ,
            {
                "K_SERVICE": "service",
                "K_REVISION": "revision",
                "GOOGLE_CLOUD_PROJECT": "project",
            },
            clear=True,
        ):
            assert is_cloud_run_environment() is True

        # 관련 없는 변수들만 있는 경우
        with patch.dict(
            os.environ,
            {"HOME": "/home/user", "PATH": "/usr/bin", "SOME_OTHER_VAR": "value"},
            clear=True,
        ):
            assert is_cloud_run_environment() is False


class TestEdgeCasesAndErrorScenarios:
    """엣지 케이스 및 오류 시나리오 테스트"""

    def test_autoscaling_optimizer_with_extreme_values(self):
        """극단적인 값들로 AutoScaling 설정 테스트"""
        optimizer = AutoScalingOptimizer()

        # 극단적인 설정값들
        extreme_config = {
            "min_instances": 0,
            "max_instances": 10000,
            "target_cpu": 0.1,
            "target_memory": 99.9,
            "scale_down_delay": 0,
            "negative_value": -100,
            "zero_value": 0,
            "large_value": 999999999,
        }

        # 예외 없이 설정이 적용되어야 함
        optimizer.configure(**extreme_config)

        for key, expected_value in extreme_config.items():
            assert optimizer._config[key] == expected_value

    def test_get_recommendations_with_both_scale_flags_true(self):
        """스케일 업과 다운이 모두 True인 비정상적 상황 테스트"""
        optimizer = AutoScalingOptimizer()

        # 논리적으로 불가능하지만 발생할 수 있는 상황
        with patch.object(optimizer, "analyze_metrics") as mock_analyze:
            mock_analyze.return_value = {
                "should_scale_up": True,
                "should_scale_down": True,  # 동시에 True
                "current_instances": 5,
                "recommended_instances": 8,
            }

            recommendations = optimizer.get_recommendations()

            # should_scale_up가 먼저 체크되므로 스케일 업 권장사항만 반환
            assert len(recommendations) == 1
            assert "Scale up to 8 instances" in recommendations[0]

    @pytest.mark.asyncio
    async def test_initialize_services_exception_handling(self):
        """서비스 초기화 중 예외 발생 시나리오"""

        with (
            patch("rfs.cloud_run.helpers.is_cloud_run_environment", return_value=True),
            patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd,
            patch("rfs.cloud_run.helpers.logger") as mock_logger,
        ):

            # 서비스 디스커버리 초기화에서 예외 발생
            mock_discovery = AsyncMock()
            mock_discovery.initialize.side_effect = Exception("Initialization failed")
            mock_get_sd.return_value = mock_discovery

            # 예외가 발생해도 함수가 중단되지 않고 계속 실행되어야 함
            with pytest.raises(Exception, match="Initialization failed"):
                await initialize_cloud_run_services()

            # 초기화 시도는 되었어야 함
            mock_logger.info.assert_called_with("Initializing Cloud Run services...")

    def test_empty_and_none_recommendations(self):
        """빈 권장사항과 None 값 처리 테스트"""
        optimizer = AutoScalingOptimizer()

        # None 값이 포함된 분석 결과
        with patch.object(optimizer, "analyze_metrics") as mock_analyze:
            mock_analyze.return_value = {
                "should_scale_up": False,
                "should_scale_down": False,
                "current_instances": None,
                "recommended_instances": None,
            }

            recommendations = optimizer.get_recommendations()

            # 스케일링 불필요하므로 빈 리스트
            assert recommendations == []

    def test_scaling_with_no_configuration(self):
        """설정 없이 스케일링 최적화 실행"""

        with patch(
            "rfs.cloud_run.helpers.get_autoscaling_optimizer"
        ) as mock_get_optimizer:
            mock_optimizer = MagicMock(spec=AutoScalingOptimizer)
            mock_optimizer.get_recommendations.return_value = []
            mock_get_optimizer.return_value = mock_optimizer

            with patch("rfs.cloud_run.helpers.logger") as mock_logger:
                # 설정 없이 호출
                optimize_scaling()

                # configure가 빈 kwargs로 호출되었는지 확인
                mock_optimizer.configure.assert_called_once_with()

                # 권장사항이 없으므로 로깅도 없어야 함
                mock_logger.info.assert_not_called()


class TestConcurrencyAndAsyncBehavior:
    """동시성 및 비동기 동작 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_service_calls_with_exceptions(self):
        """동시 서비스 호출에서 일부 실패 테스트"""

        call_results = []

        async def make_successful_call(service_name: str):
            with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
                mock_discovery = MagicMock()
                from rfs.cloud_run.helpers import ServiceEndpoint

                endpoint = ServiceEndpoint(
                    service_name, f"https://{service_name}.example.com"
                )
                endpoint.is_healthy = True
                mock_discovery.get_service.return_value = endpoint
                mock_get_sd.return_value = mock_discovery

                result = await call_service(service_name, "/api/test")
                call_results.append((service_name, result))

        async def make_failed_call(service_name: str):
            # 서비스를 찾을 수 없도록 설정하여 실패 유도
            with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
                mock_discovery = MagicMock()
                mock_discovery.get_service.return_value = None
                mock_get_sd.return_value = mock_discovery

                result = await call_service(service_name, "/api/test")
                call_results.append((service_name, result))

        # 동시에 여러 서비스 호출 (일부는 실패하도록)
        await asyncio.gather(
            make_successful_call("service1"),
            make_failed_call("service2"),
            make_successful_call("service3"),
            make_failed_call("service4"),
            return_exceptions=True,
        )

        # 결과 검증
        assert len(call_results) == 4

        successful_calls = [result for _, result in call_results if result.is_success()]
        failed_calls = [result for _, result in call_results if result.is_failure()]

        # 성공 2개, 실패 2개 예상
        assert len(successful_calls) == 2
        assert len(failed_calls) == 2
