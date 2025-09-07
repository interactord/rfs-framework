"""
Production Monitor 단위 테스트

긴급 수정 사항 검증:
- 메트릭 병합 로직이 올바르게 작동하는지 확인
- 시스템, 애플리케이션, 네트워크 메트릭이 모두 수집되는지 검증
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rfs import Success
from rfs.production.monitoring.production_monitor import (
    MonitoringConfig,
    ProductionMonitor,
    ServiceHealth,
    SystemStatus,
)


class TestProductionMonitor:
    """Production Monitor 테스트"""

    @pytest.fixture
    def config(self):
        """테스트용 모니터링 설정"""
        return MonitoringConfig(
            enable_system_monitoring=True,
            enable_application_monitoring=True,
            enable_network_monitoring=True,
            enable_custom_metrics=False,
        )

    @pytest.fixture
    def monitor(self, config):
        """Production Monitor 인스턴스"""
        return ProductionMonitor(config)

    @pytest.mark.asyncio
    async def test_metrics_merging_logic(self, monitor):
        """메트릭 병합 로직 테스트 - 긴급 수정 사항 검증"""
        # Given: 각 메트릭 수집 함수를 모킹
        system_metrics = {
            "cpu_usage_percent": 45.5,
            "memory_usage_percent": 60.2,
            "disk_usage_percent": 75.0,
        }
        app_metrics = {
            "request_count": 100,
            "error_count": 5,
            "avg_response_time_ms": 150.0,
        }
        network_metrics = {
            "network_in_mbps": 10.5,
            "network_out_mbps": 8.3,
        }

        monitor.metrics_collector._collect_system_metrics = AsyncMock(
            return_value=system_metrics
        )
        monitor.metrics_collector._collect_application_metrics = AsyncMock(
            return_value=app_metrics
        )
        monitor.metrics_collector._collect_network_metrics = AsyncMock(
            return_value=network_metrics
        )

        # When: 메트릭 수집 실행
        result = await monitor.collect_metrics()

        # Then: 모든 메트릭이 올바르게 병합되었는지 확인
        assert result.is_success()
        metrics = result.unwrap()

        # 시스템 메트릭 확인
        assert metrics.cpu_usage_percent == 45.5
        assert metrics.memory_usage_percent == 60.2
        assert metrics.disk_usage_percent == 75.0

        # 애플리케이션 메트릭 확인
        assert metrics.request_count == 100
        assert metrics.error_count == 5
        assert metrics.avg_response_time_ms == 150.0

        # 네트워크 메트릭 확인
        assert metrics.network_in_mbps == 10.5
        assert metrics.network_out_mbps == 8.3

        # 메트릭 수집 함수들이 호출되었는지 확인
        monitor.metrics_collector._collect_system_metrics.assert_called_once()
        monitor.metrics_collector._collect_application_metrics.assert_called_once()
        monitor.metrics_collector._collect_network_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_metrics_collection(self, monitor):
        """일부 메트릭만 활성화된 경우 테스트"""
        # Given: 시스템 모니터링만 활성화
        monitor.config.enable_system_monitoring = True
        monitor.config.enable_application_monitoring = False
        monitor.config.enable_network_monitoring = False

        system_metrics = {
            "cpu_usage_percent": 30.0,
            "memory_usage_percent": 40.0,
            "disk_usage_percent": 50.0,
        }

        monitor.metrics_collector._collect_system_metrics = AsyncMock(
            return_value=system_metrics
        )
        monitor.metrics_collector._collect_application_metrics = AsyncMock()
        monitor.metrics_collector._collect_network_metrics = AsyncMock()

        # When: 메트릭 수집
        result = await monitor.collect_metrics()

        # Then: 시스템 메트릭만 수집되었는지 확인
        assert result.is_success()
        metrics = result.unwrap()

        assert metrics.cpu_usage_percent == 30.0
        assert metrics.memory_usage_percent == 40.0
        assert metrics.disk_usage_percent == 50.0

        # 다른 수집 함수들은 호출되지 않았는지 확인
        monitor.metrics_collector._collect_system_metrics.assert_called_once()
        monitor.metrics_collector._collect_application_metrics.assert_not_called()
        monitor.metrics_collector._collect_network_metrics.assert_not_called()

    @pytest.mark.asyncio
    async def test_system_status_determination(self, monitor):
        """시스템 상태 결정 로직 테스트"""
        # Given: 높은 CPU 사용률
        monitor.metrics_collector._collect_system_metrics = AsyncMock(
            return_value={
                "cpu_usage_percent": 95.0,  # Critical threshold
                "memory_usage_percent": 50.0,
                "disk_usage_percent": 40.0,
            }
        )
        monitor.metrics_collector._collect_application_metrics = AsyncMock(
            return_value={
                "request_count": 100,
                "error_count": 2,
                "avg_response_time_ms": 100.0,
            }
        )
        monitor.config.enable_network_monitoring = False

        # When: 메트릭 수집
        result = await monitor.collect_metrics()

        # Then: 시스템 상태가 CRITICAL인지 확인
        assert result.is_success()
        metrics = result.unwrap()
        assert metrics.system_status == SystemStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_service_health_determination(self, monitor):
        """서비스 헬스 결정 로직 테스트"""
        # Given: 높은 에러율
        monitor.metrics_collector._collect_system_metrics = AsyncMock(
            return_value={
                "cpu_usage_percent": 40.0,
                "memory_usage_percent": 50.0,
                "disk_usage_percent": 60.0,
            }
        )
        monitor.metrics_collector._collect_application_metrics = AsyncMock(
            return_value={
                "request_count": 100,
                "error_count": 25,  # 25% error rate - unhealthy
                "avg_response_time_ms": 100.0,
            }
        )
        monitor.config.enable_network_monitoring = False

        # When: 메트릭 수집
        result = await monitor.collect_metrics()

        # Then: 서비스 헬스가 DOWN인지 확인
        assert result.is_success()
        metrics = result.unwrap()
        assert metrics.service_health == ServiceHealth.DOWN

    @pytest.mark.asyncio
    async def test_metrics_collection_error_handling(self, monitor):
        """메트릭 수집 중 오류 처리 테스트"""
        # Given: 시스템 메트릭 수집 중 오류 발생
        monitor.metrics_collector._collect_system_metrics = AsyncMock(
            side_effect=Exception("Simulated error")
        )

        # When: 메트릭 수집
        result = await monitor.collect_metrics()

        # Then: 실패 결과 반환
        assert result.is_failure()
        assert "메트릭 수집 실패" in result.unwrap_error()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
