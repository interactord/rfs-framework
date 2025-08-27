"""
Cloud Run Logging/Monitoring Integration Tests

Google Cloud Run의 로깅, 모니터링, 메트릭 수집 및 통합 테스트
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from rfs.cloud_run.helpers import (
    CloudMonitoringClient,
    get_monitoring_client,
    log_error,
    log_info,
    log_warning,
    monitor_performance,
    record_metric,
)


class TestCloudMonitoringClient:
    """Cloud Monitoring Client 테스트"""

    def test_monitoring_client_singleton(self):
        """Monitoring Client 싱글톤 패턴 확인"""
        client1 = CloudMonitoringClient()
        client2 = CloudMonitoringClient()

        assert client1 is client2

    def test_initial_state(self):
        """Monitoring Client 초기 상태 확인"""
        client = CloudMonitoringClient()

        assert client._metrics == []
        assert client._logs == []

    def test_record_metric_basic(self):
        """기본 메트릭 기록 테스트"""
        client = CloudMonitoringClient()

        client.record_metric("cpu_usage", 75.5, unit="percent")

        assert len(client._metrics) == 1
        metric = client._metrics[0]

        assert metric["name"] == "cpu_usage"
        assert metric["value"] == 75.5
        assert metric["unit"] == "percent"
        assert metric["labels"] == {}
        assert isinstance(metric["timestamp"], datetime)

    def test_record_metric_with_labels(self):
        """레이블이 포함된 메트릭 기록"""
        client = CloudMonitoringClient()

        labels = {
            "service": "user-api",
            "environment": "production",
            "region": "asia-northeast3",
        }

        client.record_metric("request_count", 1250, unit="count", labels=labels)

        assert len(client._metrics) == 1
        metric = client._metrics[0]

        assert metric["name"] == "request_count"
        assert metric["value"] == 1250
        assert metric["unit"] == "count"
        assert metric["labels"] == labels

    def test_record_multiple_metrics(self):
        """다수 메트릭 기록 테스트"""
        client = CloudMonitoringClient()

        metrics_to_record = [
            ("cpu_usage", 65.2, "percent", {"instance": "web-1"}),
            ("memory_usage", 512.8, "MB", {"instance": "web-1"}),
            ("request_latency", 45.3, "ms", {"endpoint": "/api/users"}),
            ("error_rate", 0.05, "rate", {"service": "auth"}),
        ]

        for name, value, unit, labels in metrics_to_record:
            client.record_metric(name, value, unit, labels)

        assert len(client._metrics) == 4

        # 각 메트릭 검증
        names = [m["name"] for m in client._metrics]
        assert "cpu_usage" in names
        assert "memory_usage" in names
        assert "request_latency" in names
        assert "error_rate" in names

    def test_log_entry_basic(self):
        """기본 로그 기록 테스트"""
        client = CloudMonitoringClient()

        client.log("INFO", "Service started successfully")

        assert len(client._logs) == 1
        log_entry = client._logs[0]

        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Service started successfully"
        assert isinstance(log_entry["timestamp"], datetime)

    def test_log_entry_with_metadata(self):
        """메타데이터가 포함된 로그 기록"""
        client = CloudMonitoringClient()

        client.log(
            "ERROR",
            "Database connection failed",
            error_code=500,
            database="user_db",
            retry_count=3,
            duration_ms=1500.5,
        )

        assert len(client._logs) == 1
        log_entry = client._logs[0]

        assert log_entry["level"] == "ERROR"
        assert log_entry["message"] == "Database connection failed"
        assert log_entry["error_code"] == 500
        assert log_entry["database"] == "user_db"
        assert log_entry["retry_count"] == 3
        assert log_entry["duration_ms"] == 1500.5

    def test_get_metrics(self):
        """메트릭 조회 테스트"""
        client = CloudMonitoringClient()

        # 메트릭 기록
        client.record_metric("test_metric_1", 100.0)
        client.record_metric("test_metric_2", 200.0)

        # 메트릭 조회
        metrics = client.get_metrics()

        assert len(metrics) == 2
        assert isinstance(metrics, list)

        # 원본 데이터 수정이 조회 결과에 영향을 주지 않는지 확인
        original_count = len(client._metrics)
        metrics.append({"name": "fake_metric"})
        assert len(client._metrics) == original_count

    def test_get_logs(self):
        """로그 조회 테스트"""
        client = CloudMonitoringClient()

        # 로그 기록
        client.log("INFO", "First log entry")
        client.log("WARN", "Second log entry")

        # 로그 조회
        logs = client.get_logs()

        assert len(logs) == 2
        assert isinstance(logs, list)

        # 원본 데이터 보호 확인
        original_count = len(client._logs)
        logs.append({"level": "FAKE", "message": "fake"})
        assert len(client._logs) == original_count

    def test_concurrent_metric_recording(self):
        """동시 메트릭 기록 테스트"""
        client = CloudMonitoringClient()

        # 동시에 여러 메트릭 기록 (순차적으로 하지만 빠르게)
        for i in range(100):
            client.record_metric(f"metric_{i}", float(i), "count")

        assert len(client._metrics) == 100

        # 모든 메트릭이 고유한지 확인
        names = [m["name"] for m in client._metrics]
        assert len(set(names)) == 100

    def test_large_metric_values(self):
        """큰 메트릭 값 처리 테스트"""
        client = CloudMonitoringClient()

        large_values = [
            1e6,  # 백만
            1e9,  # 십억
            1e12,  # 조
            3.14159265359,  # 소수점 정밀도
            -1000.5,  # 음수
        ]

        for i, value in enumerate(large_values):
            client.record_metric(f"large_metric_{i}", value)

        assert len(client._metrics) == len(large_values)

        # 값들이 정확히 저장되었는지 확인
        for i, expected_value in enumerate(large_values):
            metric = client._metrics[i]
            assert metric["value"] == expected_value


class TestMonitoringHelperFunctions:
    """모니터링 헬퍼 함수 테스트"""

    def test_get_monitoring_client_singleton(self):
        """글로벌 모니터링 클라이언트 싱글톤 확인"""
        client1 = get_monitoring_client()
        client2 = get_monitoring_client()

        assert client1 is client2
        assert isinstance(client1, CloudMonitoringClient)

    def test_record_metric_helper(self):
        """record_metric 헬퍼 함수 테스트"""
        with patch("rfs.cloud_run.helpers.get_monitoring_client") as mock_get_client:
            mock_client = MagicMock(spec=CloudMonitoringClient)
            mock_get_client.return_value = mock_client

            record_metric("test_metric", 123.45, "ms", {"service": "api"})

            mock_client.record_metric.assert_called_once_with(
                "test_metric", 123.45, "ms", {"service": "api"}
            )

    def test_log_info_helper(self):
        """log_info 헬퍼 함수 테스트"""
        with patch("rfs.cloud_run.helpers.get_monitoring_client") as mock_get_client:
            mock_client = MagicMock(spec=CloudMonitoringClient)
            mock_get_client.return_value = mock_client

            log_info("Service started", service_name="api", port=8080)

            mock_client.log.assert_called_once_with(
                "INFO", "Service started", service_name="api", port=8080
            )

    def test_log_warning_helper(self):
        """log_warning 헬퍼 함수 테스트"""
        with patch("rfs.cloud_run.helpers.get_monitoring_client") as mock_get_client:
            mock_client = MagicMock(spec=CloudMonitoringClient)
            mock_get_client.return_value = mock_client

            log_warning("High memory usage", memory_percent=85.2)

            mock_client.log.assert_called_once_with(
                "WARNING", "High memory usage", memory_percent=85.2
            )

    def test_log_error_helper(self):
        """log_error 헬퍼 함수 테스트"""
        with patch("rfs.cloud_run.helpers.get_monitoring_client") as mock_get_client:
            mock_client = MagicMock(spec=CloudMonitoringClient)
            mock_get_client.return_value = mock_client

            log_error("Database connection failed", error_code=500, retry_attempt=3)

            mock_client.log.assert_called_once_with(
                "ERROR", "Database connection failed", error_code=500, retry_attempt=3
            )


class TestPerformanceMonitoringDecorator:
    """성능 모니터링 데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_monitor_performance_async_function_success(self):
        """비동기 함수 성능 모니터링 성공 케이스"""
        with patch("rfs.cloud_run.helpers.record_metric") as mock_record_metric:

            @monitor_performance
            async def async_test_function(value):
                await asyncio.sleep(0.1)  # 100ms 지연
                return value * 2

            result = await async_test_function(21)

            assert result == 42

            # 메트릭이 기록되었는지 확인
            mock_record_metric.assert_called_once()
            call_args = mock_record_metric.call_args

            assert call_args[0][0] == "function.async_test_function.duration"
            assert call_args[0][2] == "ms"
            # 실행 시간이 대략 100ms 정도여야 함
            duration_ms = call_args[0][1]
            assert 80 <= duration_ms <= 200  # 오차 범위 고려

    def test_monitor_performance_sync_function_success(self):
        """동기 함수 성능 모니터링 성공 케이스"""
        with patch("rfs.cloud_run.helpers.record_metric") as mock_record_metric:

            @monitor_performance
            def sync_test_function(a, b):
                time.sleep(0.05)  # 50ms 지연
                return a + b

            result = sync_test_function(10, 15)

            assert result == 25

            # 메트릭이 기록되었는지 확인
            mock_record_metric.assert_called_once()
            call_args = mock_record_metric.call_args

            assert call_args[0][0] == "function.sync_test_function.duration"
            assert call_args[0][2] == "ms"
            # 실행 시간이 대략 50ms 정도여야 함
            duration_ms = call_args[0][1]
            assert 30 <= duration_ms <= 100  # 오차 범위 고려

    @pytest.mark.asyncio
    async def test_monitor_performance_async_function_exception(self):
        """비동기 함수 성능 모니터링 예외 케이스"""
        with patch("rfs.cloud_run.helpers.log_error") as mock_log_error:

            @monitor_performance
            async def failing_async_function():
                await asyncio.sleep(0.01)
                raise ValueError("Test error")

            with pytest.raises(ValueError, match="Test error"):
                await failing_async_function()

            # 에러가 로깅되었는지 확인
            mock_log_error.assert_called_once()
            call_args = mock_log_error.call_args
            assert "Function failing_async_function failed:" in call_args[0][0]

    def test_monitor_performance_sync_function_exception(self):
        """동기 함수 성능 모니터링 예외 케이스"""
        with patch("rfs.cloud_run.helpers.log_error") as mock_log_error:

            @monitor_performance
            def failing_sync_function():
                time.sleep(0.01)
                raise RuntimeError("Sync test error")

            with pytest.raises(RuntimeError, match="Sync test error"):
                failing_sync_function()

            # 에러가 로깅되었는지 확인
            mock_log_error.assert_called_once()
            call_args = mock_log_error.call_args
            assert "Function failing_sync_function failed:" in call_args[0][0]

    def test_monitor_performance_function_metadata_preservation(self):
        """데코레이터가 함수 메타데이터를 보존하는지 확인"""

        @monitor_performance
        def documented_function(x, y):
            """이 함수는 x와 y를 더합니다."""
            return x + y

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "이 함수는 x와 y를 더합니다."

    @pytest.mark.asyncio
    async def test_monitor_performance_async_detection(self):
        """데코레이터가 비동기 함수를 올바르게 감지하는지 확인"""
        with patch("rfs.cloud_run.helpers.record_metric"):

            @monitor_performance
            async def async_func():
                return "async_result"

            @monitor_performance
            def sync_func():
                return "sync_result"

            # 비동기 함수는 await로 호출 가능
            result1 = await async_func()
            assert result1 == "async_result"

            # 동기 함수는 직접 호출
            result2 = sync_func()
            assert result2 == "sync_result"

    def test_monitor_performance_concurrent_calls(self):
        """동시 호출에서 성능 모니터링이 독립적으로 작동하는지 확인"""
        call_times = []

        with patch("rfs.cloud_run.helpers.record_metric") as mock_record_metric:

            @monitor_performance
            def timed_function(delay_ms):
                time.sleep(delay_ms / 1000.0)
                return f"completed_{delay_ms}"

            # 다른 지연 시간으로 함수 호출
            result1 = timed_function(50)
            result2 = timed_function(100)
            result3 = timed_function(25)

            assert result1 == "completed_50"
            assert result2 == "completed_100"
            assert result3 == "completed_25"

            # 각 호출에 대해 메트릭이 기록되었는지 확인
            assert mock_record_metric.call_count == 3


class TestLoggingIntegration:
    """로깅 통합 테스트"""

    def test_structured_logging(self):
        """구조화된 로깅 테스트"""
        client = get_monitoring_client()

        # 기존 로그 클리어
        client._logs = []

        # 구조화된 로그 기록
        log_info(
            "User login",
            user_id="user_123",
            ip_address="192.168.1.100",
            user_agent="Chrome/91.0",
            timestamp=datetime.now().isoformat(),
        )

        logs = client.get_logs()
        assert len(logs) == 1

        log_entry = logs[0]
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "User login"
        assert log_entry["user_id"] == "user_123"
        assert log_entry["ip_address"] == "192.168.1.100"

    def test_log_level_filtering_concept(self):
        """로그 레벨 필터링 개념 테스트"""
        client = get_monitoring_client()
        client._logs = []

        # 다양한 레벨의 로그 기록
        log_info("Info message", event="user_action")
        log_warning("Warning message", memory_usage="high")
        log_error("Error message", error_code=500)

        logs = client.get_logs()
        assert len(logs) == 3

        # 레벨별 분류
        log_levels = [log["level"] for log in logs]
        assert "INFO" in log_levels
        assert "WARNING" in log_levels
        assert "ERROR" in log_levels

    def test_log_aggregation(self):
        """로그 집계 테스트"""
        client = get_monitoring_client()
        client._logs = []

        # 대량 로그 생성
        for i in range(50):
            if i % 3 == 0:
                log_error("Error occurred", request_id=f"req_{i}")
            elif i % 3 == 1:
                log_warning("Warning detected", request_id=f"req_{i}")
            else:
                log_info("Info logged", request_id=f"req_{i}")

        logs = client.get_logs()
        assert len(logs) == 50

        # 레벨별 카운트
        error_count = len([log for log in logs if log["level"] == "ERROR"])
        warning_count = len([log for log in logs if log["level"] == "WARNING"])
        info_count = len([log for log in logs if log["level"] == "INFO"])

        # 대략적인 분포 확인 (50개를 3으로 나누면 각각 17, 17, 16개 정도)
        assert 15 <= error_count <= 18
        assert 15 <= warning_count <= 18
        assert 15 <= info_count <= 18


class TestMetricsIntegration:
    """메트릭 통합 테스트"""

    def test_application_metrics(self):
        """애플리케이션 메트릭 테스트"""
        client = get_monitoring_client()
        client._metrics = []

        # 애플리케이션 메트릭 기록
        record_metric("app.requests.total", 1000, "count")
        record_metric("app.requests.success", 950, "count")
        record_metric("app.requests.error", 50, "count")
        record_metric("app.response.time.avg", 245.3, "ms")
        record_metric("app.memory.usage", 512.8, "MB")

        metrics = client.get_metrics()
        assert len(metrics) == 5

        # 메트릭 이름 확인
        metric_names = [m["name"] for m in metrics]
        assert "app.requests.total" in metric_names
        assert "app.requests.success" in metric_names
        assert "app.requests.error" in metric_names
        assert "app.response.time.avg" in metric_names
        assert "app.memory.usage" in metric_names

    def test_custom_metrics_with_labels(self):
        """레이블이 있는 커스텀 메트릭 테스트"""
        client = get_monitoring_client()
        client._metrics = []

        # 서비스별 메트릭
        services = ["user-api", "auth-api", "payment-api"]

        for service in services:
            record_metric(
                "service.cpu.usage",
                65.0 + hash(service) % 20,  # 가변 CPU 사용률
                "percent",
                {"service": service, "environment": "production"},
            )

        metrics = client.get_metrics()
        assert len(metrics) == 3

        # 모든 메트릭이 올바른 레이블을 가지는지 확인
        for metric in metrics:
            assert metric["labels"]["environment"] == "production"
            assert metric["labels"]["service"] in services

    def test_time_series_metrics(self):
        """시계열 메트릭 테스트"""
        client = get_monitoring_client()
        client._metrics = []

        # 시간 경과에 따른 메트릭 시뮬레이션
        base_time = datetime.now()

        for i in range(10):
            # CPU 사용률이 시간에 따라 변화
            cpu_usage = 50 + 30 * (i / 10)  # 50%에서 80%까지 증가

            record_metric("system.cpu.usage", cpu_usage, "percent")

            # 약간의 시간 간격 시뮬레이션 (실제로는 timestamp 조작)
            if client._metrics:
                client._metrics[-1]["timestamp"] = base_time + timedelta(minutes=i)

        metrics = client.get_metrics()
        assert len(metrics) == 10

        # 시간 순서 확인
        timestamps = [m["timestamp"] for m in metrics]
        assert timestamps == sorted(timestamps)

        # 값의 증가 추세 확인
        values = [m["value"] for m in metrics]
        assert values[0] < values[-1]  # 첫 번째 < 마지막

    def test_metric_aggregation_concepts(self):
        """메트릭 집계 개념 테스트"""
        client = get_monitoring_client()
        client._metrics = []

        # 동일한 메트릭명으로 여러 값 기록
        request_times = [120, 150, 200, 95, 300, 80, 250, 180]

        for req_time in request_times:
            record_metric(
                "api.response.time", req_time, "ms", {"endpoint": "/api/users"}
            )

        metrics = client.get_metrics()
        assert len(metrics) == len(request_times)

        # 통계 계산 (실제 구현에서는 모니터링 시스템에서 처리)
        values = [m["value"] for m in metrics]
        avg_response_time = sum(values) / len(values)
        max_response_time = max(values)
        min_response_time = min(values)

        assert 100 <= avg_response_time <= 200  # 대략적인 평균
        assert max_response_time == 300
        assert min_response_time == 80
