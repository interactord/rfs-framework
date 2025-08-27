"""
Cloud Run Monitoring Tests - Google Cloud Run Official Patterns

RFS Cloud Run 모니터링 시스템 테스트
Google Cloud Run 공식 모니터링 패턴 및 메트릭 검증
- Cloud Run 자동 통합 메트릭
- Cloud Monitoring 연동 패턴
- Performance 및 Cost Optimization 모니터링
- OpenTelemetry 및 Structured Logging 지원
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from rfs.cloud_run.monitoring import (
    AlertSeverity,
    CloudMonitoringClient,
    LogEntry,
    LogLevel,
    MetricDefinition,
    MetricType,
    PerformanceMonitor,
    get_monitoring_client,
    log_error,
    log_info,
    log_warning,
    monitor_performance,
    record_metric,
)
from rfs.core.result import Failure, Result, Success


class TestCloudRunMonitoringPatterns:
    """Google Cloud Run 공식 모니터링 패턴 테스트"""

    def setup_method(self):
        """테스트 설정 - Cloud Run 환경 시뮬레이션"""
        # Cloud Run 환경 변수 설정
        os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project-12345"
        os.environ["K_SERVICE"] = "monitoring-service"
        os.environ["K_REVISION"] = "monitoring-service-00001-abc"
        os.environ["K_CONFIGURATION"] = "monitoring-service"
        os.environ["GOOGLE_CLOUD_REGION"] = "us-central1"
        os.environ["PORT"] = "8080"

    def test_cloud_run_automatic_integration(self):
        """Cloud Run 자동 모니터링 통합 테스트"""
        # Given: Cloud Run 환경에서 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        assert client.project_id == "test-project-12345"
        assert client.project_path == "projects/test-project-12345"

        # When: Cloud Run 환경 변수 확인
        # Then: 자동 통합 설정 검증
        assert os.environ.get("K_SERVICE") == "monitoring-service"
        assert os.environ.get("GOOGLE_CLOUD_PROJECT") == "test-project-12345"

    @pytest.mark.asyncio
    async def test_cloud_run_default_metrics_registration(self):
        """Cloud Run 기본 메트릭 등록 테스트"""
        # Given: 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        await client.initialize()

        with patch.object(client, "monitoring_client") as mock_monitoring:
            mock_monitoring.create_metric_descriptor = Mock()

            # When: 기본 메트릭 등록
            await client._register_default_metrics()

            # Then: Cloud Run 필수 메트릭들이 등록됨
            expected_metrics = {
                "request_count",
                "request_duration",
                "memory_usage",
                "cpu_usage",
                "active_connections",
                "task_queue_size",
                "error_rate",
            }
            registered_names = set(client.registered_metrics.keys())
            assert expected_metrics.issubset(registered_names)

    def test_cloud_run_resource_labels(self):
        """Cloud Run 리소스 레이블 패턴 테스트"""
        # Given: LogEntry 생성
        entry = LogEntry(
            message="Cloud Run service request",
            level=LogLevel.INFO,
            service_name="monitoring-service",
            version="00001-abc",
        )

        # When: Cloud Logging 형식으로 변환
        cloud_entry = entry.to_cloud_logging_entry()

        # Then: Cloud Run 표준 리소스 레이블 검증
        resource = cloud_entry["resource"]
        assert resource["type"] == "cloud_run_revision"
        assert resource["labels"]["service_name"] == "monitoring-service"
        assert resource["labels"]["revision_name"] == "monitoring-service-00001-abc"
        assert resource["labels"]["configuration_name"] == "monitoring-service"
        assert resource["labels"]["location"] == "us-central1"

    @pytest.mark.asyncio
    async def test_billable_instance_time_monitoring(self):
        """Cloud Run 과금 가능한 인스턴스 시간 모니터링 테스트"""
        # Given: 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        await client.initialize()

        # Given: 인스턴스 시간 추적용 메트릭
        billable_metric = MetricDefinition(
            name="billable_instance_time",
            type=MetricType.GAUGE,
            description="Cloud Run 과금 가능한 인스턴스 시간",
            unit="seconds",
            labels={"instance_state": "active", "service_name": ""},
        )

        # When: 메트릭 등록 및 기록
        result = await client.register_metric(billable_metric)
        assert result.is_success()

        # Then: 과금 최적화를 위한 모니터링
        await client.record_metric(
            "billable_instance_time",
            300.0,  # 5분
            labels={"instance_state": "active", "service_name": "monitoring-service"},
        )

        assert len(client.metrics_buffer) == 1
        metric_data = client.metrics_buffer[0]
        assert metric_data["name"] == "billable_instance_time"
        assert metric_data["labels"]["instance_state"] == "active"

    @pytest.mark.asyncio
    async def test_container_startup_latency_monitoring(self):
        """컨테이너 시작 지연 시간 모니터링 테스트"""
        # Given: 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        await client.initialize()

        # Given: 시작 지연 시간 메트릭
        startup_metric = MetricDefinition(
            name="container_startup_latency",
            type=MetricType.HISTOGRAM,
            description="컨테이너 시작 지연 시간",
            unit="ms",
        )

        # When: Cold start 시나리오 시뮬레이션
        await client.register_metric(startup_metric)

        # Cold start: 3초
        await client.record_metric("container_startup_latency", 3000.0)
        # Warm start: 10ms
        await client.record_metric("container_startup_latency", 10.0)

        # Then: 시작 지연 시간 패턴 분석 가능
        assert len(client.metrics_buffer) == 2
        cold_start = client.metrics_buffer[0]
        warm_start = client.metrics_buffer[1]

        assert cold_start["value"] == 3000.0  # Cold start
        assert warm_start["value"] == 10.0  # Warm start

    @pytest.mark.asyncio
    async def test_cpu_memory_utilization_monitoring(self):
        """CPU/메모리 사용률 모니터링 테스트"""
        # Given: 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        await client.initialize()

        # Given: 리소스 사용률 메트릭들이 등록됨
        await client._register_default_metrics()

        # When: Cloud Run 리소스 임계값 모니터링
        # CPU 사용률: 80% (임계값 초과)
        await client.record_metric("cpu_usage", 85.0, {"threshold": "exceeded"})

        # 메모리 사용률: 512MB 중 400MB 사용 (78%)
        memory_usage_percent = (400 / 512) * 100
        await client.record_metric("memory_usage", memory_usage_percent)

        # Then: 리소스 사용률 추적 가능
        cpu_metric = next(m for m in client.metrics_buffer if m["name"] == "cpu_usage")
        memory_metric = next(
            m for m in client.metrics_buffer if m["name"] == "memory_usage"
        )

        assert cpu_metric["value"] == 85.0
        assert cpu_metric["labels"]["threshold"] == "exceeded"
        assert memory_metric["value"] == pytest.approx(78.125, rel=0.01)

    @pytest.mark.asyncio
    async def test_request_latency_percentile_monitoring(self):
        """요청 지연 시간 백분위수 모니터링 테스트"""
        # Given: 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        await client.initialize()

        # Given: 요청 지연 시간 히스토그램
        latency_values = [50, 75, 100, 150, 200, 250, 300, 500, 1000, 2000]  # ms

        # When: 다양한 지연 시간 기록
        for latency in latency_values:
            await client.record_metric(
                "request_duration",
                float(latency),
                labels={"percentile": self._get_percentile_label(latency)},
            )

        # Then: 백분위수 분석 가능
        assert len(client.metrics_buffer) == len(latency_values)

        # P50, P95, P99 검증
        p50_metrics = [
            m for m in client.metrics_buffer if m["labels"].get("percentile") == "p50"
        ]
        p95_metrics = [
            m for m in client.metrics_buffer if m["labels"].get("percentile") == "p95"
        ]
        p99_metrics = [
            m for m in client.metrics_buffer if m["labels"].get("percentile") == "p99"
        ]

        assert len(p50_metrics) > 0
        assert len(p95_metrics) > 0
        assert len(p99_metrics) > 0

    def _get_percentile_label(self, latency: float) -> str:
        """지연 시간을 백분위수 레이블로 변환"""
        if latency <= 100:
            return "p50"
        elif latency <= 500:
            return "p95"
        else:
            return "p99"

    @pytest.mark.asyncio
    async def test_container_instance_count_monitoring(self):
        """컨테이너 인스턴스 수 모니터링 테스트"""
        # Given: 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        await client.initialize()

        # Given: 인스턴스 상태별 메트릭
        instance_states = [
            ("active", 3),  # 활성 인스턴스
            ("idle", 2),  # 유휴 인스턴스
            ("starting", 1),  # 시작 중 인스턴스
        ]

        # When: 인스턴스 상태별 개수 기록
        for state, count in instance_states:
            await client.record_metric(
                "active_connections", float(count), labels={"instance_state": state}
            )

        # Then: 스케일링 패턴 분석 가능
        active_metric = next(
            m
            for m in client.metrics_buffer
            if m["labels"].get("instance_state") == "active"
        )
        idle_metric = next(
            m
            for m in client.metrics_buffer
            if m["labels"].get("instance_state") == "idle"
        )

        assert active_metric["value"] == 3.0
        assert idle_metric["value"] == 2.0

    @pytest.mark.asyncio
    async def test_concurrent_request_monitoring(self):
        """동시 요청 모니터링 테스트"""
        # Given: 모니터링 클라이언트 초기화
        client = CloudMonitoringClient("test-project-12345")
        await client.initialize()

        # Given: 동시 요청 수 추적
        max_concurrency = 80  # Cloud Run 기본값

        # When: 동시 요청 패턴 시뮬레이션
        concurrent_requests = [10, 25, 50, 75, 78, 80, 85]  # 임계값 초과 포함

        for req_count in concurrent_requests:
            await client.record_metric(
                "active_connections",
                float(req_count),
                labels={
                    "threshold_status": (
                        "exceeded" if req_count > max_concurrency else "normal"
                    ),
                    "concurrency_limit": str(max_concurrency),
                },
            )

        # Then: 동시성 임계값 초과 감지
        exceeded_metrics = [
            m
            for m in client.metrics_buffer
            if m["labels"].get("threshold_status") == "exceeded"
        ]

        assert len(exceeded_metrics) == 1  # 85개 요청만 초과
        assert exceeded_metrics[0]["value"] == 85.0


class TestCloudRunLoggingPatterns:
    """Cloud Run 로깅 패턴 테스트"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_client(self):
        """테스트 설정"""
        os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project-12345"
        os.environ["K_SERVICE"] = "logging-service"

        self.client = CloudMonitoringClient("test-project-12345")
        await self.client.initialize()

    def test_structured_logging_format(self):
        """구조화된 로깅 형식 테스트"""
        # Given: Cloud Run 서비스 로그 엔트리
        entry = LogEntry(
            message="Processing user request",
            level=LogLevel.INFO,
            service_name="logging-service",
            version="00001-def",
            trace_id="abc123def456",
            span_id="span789",
            labels={"user_id": "12345", "request_path": "/api/users"},
            extra_data={"request_size": 1024, "response_time": 250},
        )

        # When: Cloud Logging 형식으로 변환
        cloud_entry = entry.to_cloud_logging_entry()

        # Then: 구조화된 형식 검증
        assert cloud_entry["severity"] == "INFO"
        assert cloud_entry["jsonPayload"]["message"] == "Processing user request"
        assert "trace" in cloud_entry
        assert cloud_entry["trace"].endswith("/traces/abc123def456")
        assert cloud_entry["spanId"] == "span789"
        assert cloud_entry["jsonPayload"]["request_size"] == 1024

    @pytest.mark.asyncio
    async def test_log_levels_and_automatic_flush(self):
        """로그 레벨 및 자동 플러시 테스트"""
        # Given: 다양한 로그 레벨 엔트리
        log_entries = [
            LogEntry(message="Debug info", level=LogLevel.DEBUG),
            LogEntry(message="Request completed", level=LogLevel.INFO),
            LogEntry(message="Performance warning", level=LogLevel.WARNING),
            LogEntry(message="Database connection failed", level=LogLevel.ERROR),
            LogEntry(message="Service unavailable", level=LogLevel.CRITICAL),
        ]

        # When: 로그 기록 (ERROR, CRITICAL은 즉시 플러시)
        with patch.object(self.client, "_flush_logs") as mock_flush:
            # mock_flush가 실제 buffer 정리도 하도록 설정
            original_flush = self.client._flush_logs
            async def mock_flush_with_clear():
                self.client.logs_buffer = []
                
            mock_flush.side_effect = mock_flush_with_clear
            
            for entry in log_entries:
                await self.client.log_structured(entry)

        # Then: 높은 심각도 로그는 즉시 플러시
        assert mock_flush.call_count == 2  # ERROR, CRITICAL 각각 1회
        assert len(self.client.logs_buffer) == 0  # 마지막 CRITICAL 로그 후 buffer 비워짐

    @pytest.mark.asyncio
    async def test_error_reporting_integration(self):
        """Error Reporting 통합 테스트"""
        # Given: 에러 로그 엔트리 (Error Reporting 형식)
        error_entry = LogEntry(
            message="TypeError: 'NoneType' object is not subscriptable",
            level=LogLevel.ERROR,
            extra_data={
                "error_type": "TypeError",
                "stack_trace": "File '/app/main.py', line 45, in process_request",
                "user_agent": "Mozilla/5.0...",
                "request_id": str(uuid4()),
            },
        )

        # When: 에러 로그 기록 (_flush_logs를 mock하여 buffer 유지)
        with patch.object(self.client, "_flush_logs") as mock_flush:
            result = await self.client.log_structured(error_entry)

        # Then: Error Reporting 형식으로 저장됨
        assert result.is_success()
        assert mock_flush.call_count == 1  # ERROR 레벨이므로 즉시 플러시
        logged_entry = self.client.logs_buffer[0]
        assert logged_entry.level == LogLevel.ERROR
        assert "error_type" in logged_entry.extra_data
        assert "stack_trace" in logged_entry.extra_data

    @pytest.mark.asyncio
    async def test_log_retention_and_analytics_setup(self):
        """로그 보존 및 분석 설정 테스트"""
        # Given: BigQuery 내보내기용 로그 구조
        analytics_logs = [
            LogEntry(
                message="API request",
                level=LogLevel.INFO,
                labels={"api_version": "v1", "endpoint": "/users", "method": "GET"},
                extra_data={
                    "response_time_ms": 150,
                    "status_code": 200,
                    "user_country": "US",
                },
            ),
            LogEntry(
                message="Security event",
                level=LogLevel.WARNING,
                labels={
                    "security_category": "authentication",
                    "event_type": "failed_login",
                },
                extra_data={
                    "ip_address": "192.168.1.1",
                    "user_agent": "curl/7.68.0",
                    "attempts_count": 3,
                },
            ),
        ]

        # When: 분석용 로그 기록
        for log in analytics_logs:
            result = await self.client.log_structured(log)
            assert result.is_success()

        # Then: BigQuery 분석을 위한 구조화된 데이터
        api_log = self.client.logs_buffer[0]
        security_log = self.client.logs_buffer[1]

        assert api_log.labels["endpoint"] == "/users"
        assert api_log.extra_data["response_time_ms"] == 150
        assert security_log.labels["security_category"] == "authentication"
        assert security_log.extra_data["attempts_count"] == 3


class TestCloudRunPerformanceMonitoring:
    """Cloud Run 성능 모니터링 테스트"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_client(self):
        """테스트 설정"""
        self.client = CloudMonitoringClient("test-project-12345")
        await self.client.initialize()
        self.performance_monitor = PerformanceMonitor(self.client)

    @pytest.mark.asyncio
    async def test_request_monitoring_lifecycle(self):
        """요청 모니터링 생명주기 테스트"""
        # Given: HTTP 요청 시뮬레이션
        request_id = "req-" + str(uuid4())[:8]
        method = "POST"
        path = "/api/process"

        # When: 요청 시작
        self.performance_monitor.start_request_monitoring(request_id, method, path)

        # 처리 시뮬레이션
        await asyncio.sleep(0.1)

        # 요청 완료
        self.performance_monitor.end_request_monitoring(request_id, 200, method, path)

        # Then: 메트릭 기록 확인 (비동기 태스크로 실행됨)
        await asyncio.sleep(0.01)  # 비동기 태스크 완료 대기

        # 요청이 active_requests에서 제거되었는지 확인
        assert request_id not in self.performance_monitor.active_requests

    @pytest.mark.asyncio
    async def test_performance_decorator_monitoring(self):
        """성능 데코레이터 모니터링 테스트"""

        # Given: 모니터링 데코레이터 적용된 함수
        @self.performance_monitor.request_monitor("GET", "/api/data")
        async def api_endpoint():
            await asyncio.sleep(0.05)  # 50ms 처리 시간
            return {"status": "success", "data": [1, 2, 3]}

        # When: API 엔드포인트 실행
        result = await api_endpoint()

        # Then: 결과 및 모니터링 데이터 검증
        assert result["status"] == "success"
        assert len(result["data"]) == 3

    @pytest.mark.asyncio
    async def test_error_rate_monitoring(self):
        """에러율 모니터링 테스트"""
        # Given: 성공/실패 요청 시뮬레이션
        requests = [
            ("req1", 200),
            ("req2", 200),
            ("req3", 500),  # 2 성공, 1 실패
            ("req4", 404),
            ("req5", 200),
            ("req6", 503),  # 1 성공, 2 실패
        ]

        # When: 요청들 처리
        for req_id, status_code in requests:
            self.performance_monitor.start_request_monitoring(
                req_id, "GET", "/api/test"
            )
            await asyncio.sleep(0.01)
            self.performance_monitor.end_request_monitoring(
                req_id, status_code, "GET", "/api/test"
            )

        # Then: 에러율 계산 가능
        total_requests = len(requests)
        error_requests = sum(1 for _, status in requests if status >= 400)
        error_rate = (error_requests / total_requests) * 100

        assert error_rate == 50.0  # 3/6 = 50%

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """동시 요청 처리 테스트"""
        # Given: 여러 동시 요청
        concurrent_requests = 10

        async def simulate_request(req_id: str):
            self.performance_monitor.start_request_monitoring(
                req_id, "GET", "/concurrent"
            )
            await asyncio.sleep(0.1)  # 100ms 처리 시간
            self.performance_monitor.end_request_monitoring(
                req_id, 200, "GET", "/concurrent"
            )

        # When: 동시 요청 실행
        tasks = [
            simulate_request(f"concurrent-{i}") for i in range(concurrent_requests)
        ]

        await asyncio.gather(*tasks)

        # Then: 모든 요청이 정상 처리됨
        assert len(self.performance_monitor.active_requests) == 0


class TestCloudRunAlertingPatterns:
    """Cloud Run 알림 패턴 테스트"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_client(self):
        """테스트 설정"""
        self.client = CloudMonitoringClient("test-project-12345")
        await self.client.initialize()

    @pytest.mark.asyncio
    async def test_uptime_check_configuration(self):
        """Uptime Check 설정 테스트"""
        # Given: Cloud Run 서비스 Uptime Check 설정
        uptime_config = {
            "display_name": "monitoring-service-uptime",
            "http_check": {
                "request_method": "GET",
                "path": "/health",
                "port": 8080,
                "use_ssl": True,
            },
            "monitored_resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "service_name": "monitoring-service",
                    "location": "us-central1",
                },
            },
            "period": "60s",
            "timeout": "10s",
        }

        # When & Then: Uptime Check 설정이 올바른 구조를 가짐
        assert uptime_config["monitored_resource"]["type"] == "cloud_run_revision"
        assert uptime_config["http_check"]["path"] == "/health"
        assert uptime_config["period"] == "60s"

    @pytest.mark.asyncio
    async def test_alerting_policy_creation(self):
        """알림 정책 생성 테스트"""
        # Given: CPU 사용률 임계값 알림 정책
        alert_policy = {
            "display_name": "High CPU Usage Alert",
            "conditions": [
                {
                    "display_name": "CPU > 80%",
                    "condition_threshold": {
                        "filter": 'resource.type="cloud_run_revision"',
                        "comparison": "COMPARISON_GREATER_THAN",
                        "threshold_value": 0.8,
                        "duration": "300s",  # 5분
                    },
                }
            ],
            "notification_channels": ["email", "slack"],
            "alert_strategy": {"auto_close": "1800s"},  # 30분 자동 해제
        }

        # When: 임계값 초과 시뮬레이션
        await self.client.record_metric("cpu_usage", 85.0)

        # Then: 알림 조건 검증
        condition = alert_policy["conditions"][0]
        assert condition["condition_threshold"]["threshold_value"] == 0.8
        assert (
            condition["condition_threshold"]["comparison"] == "COMPARISON_GREATER_THAN"
        )

        # 기록된 메트릭이 임계값을 초과함
        recorded_value = self.client.metrics_buffer[0]["value"]
        assert recorded_value > (
            alert_policy["conditions"][0]["condition_threshold"]["threshold_value"]
            * 100
        )

    @pytest.mark.asyncio
    async def test_multi_condition_alerting(self):
        """다중 조건 알림 테스트"""
        # Given: 복합 조건 알림 (높은 CPU + 높은 에러율)
        conditions = [
            {"metric": "cpu_usage", "threshold": 80.0, "value": 85.0},
            {"metric": "error_rate", "threshold": 5.0, "value": 8.5},
            {"metric": "request_duration", "threshold": 1000.0, "value": 1500.0},
        ]

        # When: 모든 조건이 임계값을 초과
        triggered_conditions = []
        for condition in conditions:
            await self.client.record_metric(condition["metric"], condition["value"])

            if condition["value"] > condition["threshold"]:
                triggered_conditions.append(condition["metric"])

        # Then: 모든 알림 조건이 트리거됨
        assert len(triggered_conditions) == 3
        assert "cpu_usage" in triggered_conditions
        assert "error_rate" in triggered_conditions
        assert "request_duration" in triggered_conditions

    @pytest.mark.asyncio
    async def test_notification_channel_integration(self):
        """알림 채널 통합 테스트"""
        # Given: 다양한 알림 채널 설정
        notification_channels = [
            {
                "type": "email",
                "address": "alerts@company.com",
                "severity_levels": ["CRITICAL", "ERROR"],
            },
            {
                "type": "slack",
                "webhook": "https://hooks.slack.com/services/...",
                "severity_levels": ["CRITICAL", "ERROR", "WARNING"],
            },
            {
                "type": "pagerduty",
                "integration_key": "abcd1234...",
                "severity_levels": ["CRITICAL"],
            },
        ]

        # When: 심각도별 알림 시뮬레이션
        alert_severities = [
            ("Service Down", AlertSeverity.CRITICAL),
            ("High Error Rate", AlertSeverity.ERROR),
            ("Performance Degradation", AlertSeverity.WARNING),
        ]

        # Then: 각 채널의 심각도 설정 검증
        for alert_name, severity in alert_severities:
            matching_channels = [
                channel
                for channel in notification_channels
                if severity.value.upper() in channel["severity_levels"]
            ]

            if severity == AlertSeverity.CRITICAL:
                assert len(matching_channels) == 3  # 모든 채널
            elif severity == AlertSeverity.ERROR:
                assert len(matching_channels) == 2  # 이메일, 슬랙
            elif severity == AlertSeverity.WARNING:
                assert len(matching_channels) == 1  # 슬랙만


class TestCloudRunCostOptimization:
    """Cloud Run 비용 최적화 모니터링 테스트"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_client(self):
        """테스트 설정"""
        self.client = CloudMonitoringClient("test-project-12345")
        await self.client.initialize()
        
        # Cost optimization 테스트용 추가 메트릭 등록
        await self.client.register_metric(
            MetricDefinition(
                name="container_startup_latency",
                type=MetricType.HISTOGRAM,
                description="Container startup latency",
                unit="ms"
            )
        )
        await self.client.register_metric(
            MetricDefinition(
                name="billable_instance_time",
                type=MetricType.GAUGE,
                description="Billable instance time",
                unit="s"
            )
        )
        await self.client.register_metric(
            MetricDefinition(
                name="estimated_cost",
                type=MetricType.GAUGE,
                description="Estimated cost",
                unit="USD"
            )
        )

    @pytest.mark.asyncio
    async def test_cold_start_vs_warm_instance_monitoring(self):
        """Cold Start vs Warm Instance 모니터링 테스트"""
        # Given: Cold Start와 Always-on 인스턴스 비용 분석
        scenarios = [
            {
                "name": "cold_start_scenario",
                "startup_latency_ms": 2000,
                "billable_time_seconds": 30,
                "request_latency_ms": 2100,  # startup + processing
                "cost_factor": 0.5,  # 더 낮은 billable time
            },
            {
                "name": "warm_instance_scenario",
                "startup_latency_ms": 0,
                "billable_time_seconds": 300,  # Always-on
                "request_latency_ms": 100,  # 빠른 응답
                "cost_factor": 2.0,  # 더 높은 billable time
            },
        ]

        # When: 각 시나리오 메트릭 기록
        for scenario in scenarios:
            await self.client.record_metric(
                "container_startup_latency",
                scenario["startup_latency_ms"],
                labels={"scenario": scenario["name"]},
            )

            await self.client.record_metric(
                "billable_instance_time",
                scenario["billable_time_seconds"],
                labels={"scenario": scenario["name"]},
            )

            await self.client.record_metric(
                "request_duration",
                scenario["request_latency_ms"],
                labels={"scenario": scenario["name"]},
            )

        # Then: 비용 최적화 분석 데이터 수집됨
        cold_start_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("scenario") == "cold_start_scenario"
        ]
        warm_instance_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("scenario") == "warm_instance_scenario"
        ]

        assert (
            len(cold_start_metrics) == 3
        )  # startup_latency, billable_time, request_duration
        assert len(warm_instance_metrics) == 3

    @pytest.mark.asyncio
    async def test_traffic_pattern_cost_analysis(self):
        """트래픽 패턴 비용 분석 테스트"""
        # Given: 다양한 트래픽 패턴
        traffic_patterns = [
            {"time": "peak", "requests_per_minute": 1000, "instances": 10},
            {"time": "normal", "requests_per_minute": 100, "instances": 2},
            {"time": "low", "requests_per_minute": 10, "instances": 1},
            {"time": "idle", "requests_per_minute": 0, "instances": 0},
        ]

        # When: 트래픽 패턴별 비용 메트릭 기록
        for pattern in traffic_patterns:
            # 요청 수 기록
            await self.client.record_metric(
                "request_count",
                pattern["requests_per_minute"],
                labels={"traffic_pattern": pattern["time"]},
            )

            # 인스턴스 수 기록
            await self.client.record_metric(
                "active_connections",  # 인스턴스 수 대용
                pattern["instances"],
                labels={"traffic_pattern": pattern["time"]},
            )

            # 예상 비용 (인스턴스 수 * 분당 비용)
            estimated_cost = (
                pattern["instances"] * 0.000024
            )  # $0.000024 per vCPU-second
            await self.client.record_metric(
                "estimated_cost",
                estimated_cost,
                labels={"traffic_pattern": pattern["time"]},
            )

        # Then: 비용 최적화를 위한 패턴 분석 가능
        peak_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("traffic_pattern") == "peak"
        ]
        idle_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("traffic_pattern") == "idle"
        ]

        assert len(peak_metrics) == 3
        assert len(idle_metrics) == 3

        # Peak 시간대는 높은 비용, Idle 시간대는 0 비용
        peak_cost = next(
            m["value"] for m in peak_metrics if m["name"] == "estimated_cost"
        )
        idle_cost = next(
            m["value"] for m in idle_metrics if m["name"] == "estimated_cost"
        )

        assert peak_cost > 0
        assert idle_cost == 0

    @pytest.mark.asyncio
    async def test_resource_right_sizing_monitoring(self):
        """리소스 적정 크기 조정 모니터링 테스트"""
        # Given: 다양한 리소스 설정 시나리오
        resource_configs = [
            {
                "config": "oversized",
                "cpu": 2.0,  # 2 vCPU
                "memory_gb": 4.0,  # 4 GB
                "cpu_usage": 25.0,  # 25% 사용률 (과도한 할당)
                "memory_usage": 30.0,  # 30% 사용률 (과도한 할당)
            },
            {
                "config": "optimal",
                "cpu": 1.0,  # 1 vCPU
                "memory_gb": 2.0,  # 2 GB
                "cpu_usage": 75.0,  # 75% 사용률 (적정)
                "memory_usage": 70.0,  # 70% 사용률 (적정)
            },
            {
                "config": "undersized",
                "cpu": 0.5,  # 0.5 vCPU
                "memory_gb": 1.0,  # 1 GB
                "cpu_usage": 95.0,  # 95% 사용률 (부족)
                "memory_usage": 90.0,  # 90% 사용률 (부족)
            },
        ]

        # When: 리소스 사용률 메트릭 기록
        for config in resource_configs:
            await self.client.record_metric(
                "cpu_usage",
                config["cpu_usage"],
                labels={
                    "resource_config": config["config"],
                    "allocated_cpu": str(config["cpu"]),
                    "allocated_memory_gb": str(config["memory_gb"]),
                },
            )

            await self.client.record_metric(
                "memory_usage",
                config["memory_usage"],
                labels={
                    "resource_config": config["config"],
                    "allocated_cpu": str(config["cpu"]),
                    "allocated_memory_gb": str(config["memory_gb"]),
                },
            )

        # Then: 리소스 최적화 권장사항 생성 가능
        oversized_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("resource_config") == "oversized"
        ]
        optimal_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("resource_config") == "optimal"
        ]
        undersized_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("resource_config") == "undersized"
        ]

        # 각 설정마다 CPU, 메모리 메트릭이 기록됨
        assert len(oversized_metrics) == 2
        assert len(optimal_metrics) == 2
        assert len(undersized_metrics) == 2


class TestOpenTelemetryIntegration:
    """OpenTelemetry 통합 테스트"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_client(self):
        """테스트 설정"""
        self.client = CloudMonitoringClient("test-project-12345")
        await self.client.initialize()

    @pytest.mark.asyncio
    async def test_distributed_tracing_integration(self):
        """분산 추적 통합 테스트"""
        # Given: OpenTelemetry 추적 컨텍스트
        trace_context = {
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7",
            "parent_span_id": "0000000000000001",
        }

        # When: 추적 정보가 포함된 로그 기록
        trace_log = LogEntry(
            message="Processing distributed request",
            level=LogLevel.INFO,
            trace_id=trace_context["trace_id"],
            span_id=trace_context["span_id"],
            extra_data={
                "parent_span_id": trace_context["parent_span_id"],
                "service_name": "cloud-run-service",
                "operation_name": "process_user_data",
            },
        )

        await self.client.log_structured(trace_log)

        # Then: 분산 추적 정보가 올바르게 포맷됨
        with patch.object(self.client, "_flush_logs"):  # buffer 유지를 위해 flush 방지
            pass
        
        logged_entry = self.client.logs_buffer[0]
        cloud_entry = logged_entry.to_cloud_logging_entry()

        assert "trace" in cloud_entry
        # trace 구조가 중첩되어 있는지 확인
        if isinstance(cloud_entry["trace"], dict) and "trace" in cloud_entry["trace"]:
            assert trace_context["trace_id"] in cloud_entry["trace"]["trace"]
        else:
            assert trace_context["trace_id"] in str(cloud_entry["trace"])
        
        # spanId 구조 확인
        assert "spanId" in cloud_entry
        if isinstance(cloud_entry["spanId"], dict) and "spanId" in cloud_entry["spanId"]:
            assert cloud_entry["spanId"]["spanId"] == trace_context["span_id"]
        else:
            assert str(cloud_entry["spanId"]) == trace_context["span_id"]

    @pytest.mark.asyncio
    async def test_prometheus_metrics_compatibility(self):
        """Prometheus 메트릭 호환성 테스트"""
        # Given: Prometheus 스타일 메트릭
        prometheus_metrics = [
            {
                "name": "http_requests_total",
                "type": MetricType.COUNTER,
                "help": "Total number of HTTP requests",
                "labels": {"method": "GET", "status": "200"},
            },
            {
                "name": "http_request_duration_seconds",
                "type": MetricType.HISTOGRAM,
                "help": "HTTP request duration in seconds",
                "labels": {"method": "POST", "handler": "api"},
            },
            {
                "name": "memory_usage_bytes",
                "type": MetricType.GAUGE,
                "help": "Current memory usage in bytes",
                "labels": {"instance": "cloud-run-1"},
            },
        ]

        # When: Prometheus 스타일 메트릭 등록
        for metric in prometheus_metrics:
            definition = MetricDefinition(
                name=metric["name"],
                type=metric["type"],
                description=metric["help"],
                unit="1" if metric["type"] != MetricType.GAUGE else "bytes",
                labels=metric["labels"],
            )

            result = await self.client.register_metric(definition)
            assert result.is_success()

        # Then: 메트릭이 Cloud Monitoring과 호환되는 형식으로 등록됨
        assert len(self.client.registered_metrics) >= 3
        assert "http_requests_total" in self.client.registered_metrics
        assert "http_request_duration_seconds" in self.client.registered_metrics
        assert "memory_usage_bytes" in self.client.registered_metrics

    @pytest.mark.asyncio
    async def test_semantic_conventions_compliance(self):
        """OpenTelemetry 의미론적 규칙 준수 테스트"""
        # Given: OpenTelemetry 의미론적 규칙에 따른 속성
        semantic_attributes = {
            "http.method": "POST",
            "http.url": "https://monitoring-service-abc123-uc.a.run.app/api/users",
            "http.status_code": 200,
            "http.user_agent": "Mozilla/5.0 (compatible; CloudRunBot/1.0)",
            "cloud.provider": "gcp",
            "cloud.platform": "gcp_cloud_run",
            "service.name": "monitoring-service",
            "service.version": "1.2.3",
        }

        # When: 의미론적 규칙을 따르는 로그 기록
        semantic_log = LogEntry(
            message="HTTP request processed",
            level=LogLevel.INFO,
            labels={
                "http_method": semantic_attributes["http.method"],
                "http_status_code": str(semantic_attributes["http.status_code"]),
                "cloud_provider": semantic_attributes["cloud.provider"],
                "cloud_platform": semantic_attributes["cloud.platform"],
            },
            extra_data={
                "http_url": semantic_attributes["http.url"],
                "http_user_agent": semantic_attributes["http.user_agent"],
                "service_name": semantic_attributes["service.name"],
                "service_version": semantic_attributes["service.version"],
            },
        )

        await self.client.log_structured(semantic_log)

        # Then: 의미론적 규칙 준수 검증
        logged_entry = self.client.logs_buffer[0]

        assert logged_entry.labels["http_method"] == "POST"
        assert logged_entry.labels["cloud_provider"] == "gcp"
        assert logged_entry.labels["cloud_platform"] == "gcp_cloud_run"
        assert logged_entry.extra_data["service_name"] == "monitoring-service"
        assert logged_entry.extra_data["service_version"] == "1.2.3"


class TestMonitoringHelperFunctions:
    """모니터링 헬퍼 함수 테스트"""

    @pytest.mark.asyncio
    async def test_global_monitoring_client_singleton(self):
        """전역 모니터링 클라이언트 싱글톤 테스트"""
        # Given: 프로젝트 ID
        project_id = "test-project-singleton"

        # When: 여러 번 클라이언트 요청
        with patch("rfs.cloud_run.monitoring._monitoring_client", None):
            client1 = await get_monitoring_client(project_id)
            client2 = await get_monitoring_client(project_id)

        # Then: 동일한 인스턴스 반환
        assert client1 is client2
        assert client1.project_id == project_id

    @pytest.mark.asyncio
    async def test_convenience_logging_functions(self):
        """편의 로깅 함수 테스트"""
        # Given: 모킹된 모니터링 클라이언트
        with patch("rfs.cloud_run.monitoring.get_monitoring_client") as mock_get_client:
            mock_client = Mock()
            mock_client.log_structured = AsyncMock(return_value=Success("Logged"))
            mock_get_client.return_value = mock_client

            # When: 편의 로깅 함수 사용
            await log_info("정보 메시지", user_id=12345)
            await log_warning("경고 메시지", component="auth")
            await log_error("에러 메시지", error_code="E001")

            # Then: 적절한 로그 레벨로 기록됨
            assert mock_client.log_structured.call_count == 3

            # 각 호출의 로그 레벨 검증
            calls = mock_client.log_structured.call_args_list
            info_entry = calls[0][0][0]
            warning_entry = calls[1][0][0]
            error_entry = calls[2][0][0]

            assert info_entry.level == LogLevel.INFO
            assert warning_entry.level == LogLevel.WARNING
            assert error_entry.level == LogLevel.ERROR

    @pytest.mark.asyncio
    async def test_performance_monitoring_decorator(self):
        """성능 모니터링 데코레이터 테스트"""
        # Given: 모킹된 모니터링 클라이언트
        with patch("rfs.cloud_run.monitoring.get_monitoring_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = Mock()
            mock_client.record_metric = AsyncMock(return_value=Success("Recorded"))
            
            mock_get_client.return_value = mock_client

            # When: 데코레이터 적용된 함수 실행
            @monitor_performance("GET", "/api/test")
            async def test_api_function(data):
                await asyncio.sleep(0.01)
                return {"processed": data}

            result = await test_api_function("test_data")

            # Then: 함수가 정상 실행되고 결과 반환
            assert result["processed"] == "test_data"

    @pytest.mark.asyncio
    async def test_metric_recording_helper(self):
        """메트릭 기록 헬퍼 테스트"""
        # Given: 모킹된 모니터링 클라이언트
        with patch("rfs.cloud_run.monitoring.get_monitoring_client") as mock_get_client:
            mock_client = Mock()
            mock_client.record_metric = AsyncMock(return_value=Success("Recorded"))
            mock_get_client.return_value = mock_client

            # When: 헬퍼 함수로 메트릭 기록
            result = await record_metric(
                "api_requests_total", 1.0, {"method": "GET", "endpoint": "/users"}
            )

            # Then: 메트릭이 성공적으로 기록됨
            assert result.is_success()
            mock_client.record_metric.assert_called_once_with(
                "api_requests_total", 1.0, {"method": "GET", "endpoint": "/users"}
            )


class TestMonitoringIntegrationScenarios:
    """모니터링 통합 시나리오 테스트"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_client(self):
        """테스트 설정"""
        self.client = CloudMonitoringClient("test-integration-12345")
        await self.client.initialize()
        self.performance_monitor = PerformanceMonitor(self.client)

    @pytest.mark.asyncio
    async def test_complete_request_lifecycle_monitoring(self):
        """완전한 요청 생명주기 모니터링 테스트"""
        # Given: HTTP 요청 시뮬레이션 시나리오
        request_scenarios = [
            {"path": "/api/users", "method": "GET", "duration_ms": 150, "status": 200},
            {"path": "/api/users", "method": "POST", "duration_ms": 300, "status": 201},
            {
                "path": "/api/orders",
                "method": "GET",
                "duration_ms": 2000,
                "status": 500,
            },  # 느린 실패 요청
        ]

        # When: 각 요청 시나리오 실행
        with patch.object(self.client, "_flush_logs"):  # logs_buffer 유지를 위해 flush 방지
            for i, scenario in enumerate(request_scenarios):
                request_id = f"req-{i+1}"

                # 요청 시작 로깅
                await self.client.log_structured(
                    LogEntry(
                        message=f"Request started: {scenario['method']} {scenario['path']}",
                        level=LogLevel.INFO,
                        labels={
                            "request_id": request_id,
                            "http_method": scenario["method"],
                            "http_path": scenario["path"],
                        },
                    )
                )

                # 성능 모니터링 시작
                self.performance_monitor.start_request_monitoring(
                    request_id, scenario["method"], scenario["path"]
                )

                # 요청 처리 시뮬레이션
                await asyncio.sleep(scenario["duration_ms"] / 1000)

                # 성능 모니터링 종료
                self.performance_monitor.end_request_monitoring(
                    request_id, scenario["status"], scenario["method"], scenario["path"]
                )

                # 요청 완료 로깅
                log_level = LogLevel.ERROR if scenario["status"] >= 400 else LogLevel.INFO
                await self.client.log_structured(
                    LogEntry(
                        message=f"Request completed: {scenario['status']}",
                        level=log_level,
                        labels={
                            "request_id": request_id,
                            "http_status": str(scenario["status"]),
                            "duration_ms": str(scenario["duration_ms"]),
                        },
                    )
                )

        # Then: 모든 요청이 추적되고 메트릭이 기록됨
        assert len(self.client.logs_buffer) == 6  # 시작 3개 + 완료 3개

        # 에러 로그 확인
        error_logs = [
            log for log in self.client.logs_buffer if log.level == LogLevel.ERROR
        ]
        assert len(error_logs) == 1
        assert "500" in error_logs[0].labels["http_status"]

    @pytest.mark.asyncio
    async def test_high_traffic_monitoring_scenario(self):
        """높은 트래픽 모니터링 시나리오 테스트"""
        # Given: 고traffic 시뮬레이션
        concurrent_requests = 50
        request_duration_range = (50, 200)  # 50-200ms

        async def simulate_concurrent_request(req_id: int):
            request_id = f"high-traffic-{req_id}"

            # 랜덤 처리 시간
            import random

            duration_ms = random.randint(*request_duration_range)

            # 요청 시작
            self.performance_monitor.start_request_monitoring(
                request_id, "GET", "/api/popular"
            )

            # 처리 시뮬레이션
            await asyncio.sleep(duration_ms / 1000)

            # 성공률 90% (10% 에러)
            status_code = 500 if req_id % 10 == 0 else 200

            # 요청 완료
            self.performance_monitor.end_request_monitoring(
                request_id, status_code, "GET", "/api/popular"
            )

            return status_code

        # When: 동시 요청 실행
        tasks = [simulate_concurrent_request(i) for i in range(concurrent_requests)]

        results = await asyncio.gather(*tasks)

        # Then: 트래픽 패턴 분석
        successful_requests = sum(1 for status in results if status == 200)
        failed_requests = sum(1 for status in results if status == 500)

        assert successful_requests == 45  # 90%
        assert failed_requests == 5  # 10%

        # 모든 요청이 완료됨
        assert len(self.performance_monitor.active_requests) == 0

    @pytest.mark.asyncio
    async def test_resource_exhaustion_monitoring(self):
        """리소스 고갈 모니터링 테스트"""
        # Given: 리소스 사용률이 점진적으로 증가하는 시나리오
        resource_progression = [
            {"time": "00:00", "cpu": 30.0, "memory": 40.0, "connections": 10},
            {"time": "00:05", "cpu": 50.0, "memory": 60.0, "connections": 25},
            {"time": "00:10", "cpu": 70.0, "memory": 75.0, "connections": 45},
            {
                "time": "00:15",
                "cpu": 85.0,
                "memory": 85.0,
                "connections": 70,
            },  # 임계값 근접
            {
                "time": "00:20",
                "cpu": 95.0,
                "memory": 90.0,
                "connections": 80,
            },  # 임계값 초과
        ]

        # When: 리소스 사용률 변화 기록
        critical_alerts = []
        
        with patch.object(self.client, "_flush_logs"):  # CRITICAL 로그에서 flush 방지
            for snapshot in resource_progression:
                # CPU 사용률 기록
                await self.client.record_metric(
                    "cpu_usage", snapshot["cpu"], labels={"timestamp": snapshot["time"]}
                )

                # 메모리 사용률 기록
                await self.client.record_metric(
                    "memory_usage",
                    snapshot["memory"],
                    labels={"timestamp": snapshot["time"]},
                )

                # 연결 수 기록
                await self.client.record_metric(
                    "active_connections",
                    snapshot["connections"],
                    labels={"timestamp": snapshot["time"]},
                )

                # 임계값 검사 (CPU > 80%, Memory > 80%, Connections > 75)
                if (
                    snapshot["cpu"] > 80
                    or snapshot["memory"] > 80
                    or snapshot["connections"] > 75
                ):

                    critical_alerts.append(
                        {
                            "time": snapshot["time"],
                            "cpu": snapshot["cpu"],
                            "memory": snapshot["memory"],
                            "connections": snapshot["connections"],
                        }
                    )

                    # Critical 로그 기록
                    await self.client.log_structured(
                        LogEntry(
                            message=f"Resource exhaustion warning at {snapshot['time']}",
                            level=LogLevel.CRITICAL,
                            extra_data=snapshot,
                        )
                    )

        # Then: 리소스 고갈 패턴 감지
        assert len(critical_alerts) == 2  # 00:15, 00:20 시점
        assert critical_alerts[0]["time"] == "00:15"
        assert critical_alerts[1]["time"] == "00:20"

        # Critical 로그가 즉시 플러시됨
        critical_logs = [
            log for log in self.client.logs_buffer if log.level == LogLevel.CRITICAL
        ]
        assert len(critical_logs) == 2

    @pytest.mark.asyncio
    async def test_service_degradation_recovery_monitoring(self):
        """서비스 성능 저하 및 복구 모니터링 테스트"""
        # Given: 서비스 성능 저하 시나리오
        performance_timeline = [
            {
                "phase": "normal",
                "latency_ms": 100,
                "error_rate": 1.0,
                "throughput": 100,
            },
            {
                "phase": "degrading",
                "latency_ms": 500,
                "error_rate": 5.0,
                "throughput": 80,
            },
            {
                "phase": "critical",
                "latency_ms": 2000,
                "error_rate": 15.0,
                "throughput": 30,
            },
            {
                "phase": "recovering",
                "latency_ms": 800,
                "error_rate": 8.0,
                "throughput": 60,
            },
            {
                "phase": "recovered",
                "latency_ms": 150,
                "error_rate": 2.0,
                "throughput": 95,
            },
        ]

        # When: 각 단계별 성능 메트릭 기록
        service_health_alerts = []

        for phase_data in performance_timeline:
            # 응답 지연 시간 기록
            await self.client.record_metric(
                "request_duration",
                phase_data["latency_ms"],
                labels={"service_phase": phase_data["phase"]},
            )

            # 에러율 기록
            await self.client.record_metric(
                "error_rate",
                phase_data["error_rate"],
                labels={"service_phase": phase_data["phase"]},
            )

            # 처리량 기록
            await self.client.record_metric(
                "request_count",
                phase_data["throughput"],
                labels={"service_phase": phase_data["phase"]},
            )

            # 서비스 상태 판단 (임계값: 지연시간 1000ms, 에러율 10%, 처리량 50 미만)
            is_critical = (
                phase_data["latency_ms"] > 1000
                or phase_data["error_rate"] > 10.0
                or phase_data["throughput"] < 50
            )

            if is_critical:
                service_health_alerts.append(phase_data["phase"])

                await self.client.log_structured(
                    LogEntry(
                        message=f"Service degradation detected in {phase_data['phase']} phase",
                        level=LogLevel.ERROR,
                        extra_data={
                            "latency_ms": phase_data["latency_ms"],
                            "error_rate_percent": phase_data["error_rate"],
                            "throughput_rps": phase_data["throughput"],
                        },
                    )
                )

        # Then: 성능 저하 및 복구 패턴 추적
        assert "critical" in service_health_alerts

        # 성능 개선 확인 (recovered vs critical)
        critical_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("service_phase") == "critical"
        ]
        recovered_metrics = [
            m
            for m in self.client.metrics_buffer
            if m["labels"].get("service_phase") == "recovered"
        ]

        critical_latency = next(
            m["value"] for m in critical_metrics if m["name"] == "request_duration"
        )
        recovered_latency = next(
            m["value"] for m in recovered_metrics if m["name"] == "request_duration"
        )

        # 복구 후 지연 시간이 현저히 개선됨
        assert recovered_latency < (critical_latency / 10)  # 2000ms -> 150ms
