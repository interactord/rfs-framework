"""
Cloud Run Helpers Tests - Google Cloud Run Official Patterns

RFS Cloud Run 헬퍼 함수 시스템 테스트
Google Cloud Run 공식 패턴 및 모범 사례 검증
- Cloud Run 환경 감지 및 메타데이터 조회
- Service Discovery 패턴
- Task Queue 통합
- Monitoring 및 Performance 최적화
- Auto Scaling 최적화
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from rfs.cloud_run.helpers import (
    AutoScalingOptimizer,
    CloudMonitoringClient,
    CloudRunServiceDiscovery,
    CloudTaskQueue,
    ServiceEndpoint,
    call_service,
    discover_services,
    get_autoscaling_optimizer,
    get_cloud_run_region,
    get_cloud_run_revision,
    get_cloud_run_service_name,
    get_cloud_run_status,
    get_monitoring_client,
    get_scaling_stats,
    get_service_discovery,
    get_task_queue,
    initialize_cloud_run_services,
    is_cloud_run_environment,
    log_error,
    log_info,
    log_warning,
    monitor_performance,
    optimize_scaling,
    record_metric,
    schedule_task,
    shutdown_cloud_run_services,
    submit_task,
    task_handler,
)
from rfs.core.result import Failure, Result, Success


class TestCloudRunEnvironmentDetection:
    """Cloud Run 환경 감지 테스트"""

    def setup_method(self):
        """테스트 설정 - 기존 환경 변수 백업"""
        self.original_env = {
            "K_SERVICE": os.environ.get("K_SERVICE"),
            "K_REVISION": os.environ.get("K_REVISION"),
            "K_CONFIGURATION": os.environ.get("K_CONFIGURATION"),
            "CLOUD_RUN_JOB": os.environ.get("CLOUD_RUN_JOB"),
            "CLOUD_RUN_REGION": os.environ.get("CLOUD_RUN_REGION"),
        }

    def teardown_method(self):
        """테스트 후 정리 - 환경 변수 복원"""
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_cloud_run_environment_detection_with_service(self):
        """K_SERVICE 환경 변수로 Cloud Run 환경 감지 테스트"""
        # Given: Cloud Run 서비스 환경 설정
        os.environ["K_SERVICE"] = "test-service"
        os.environ.pop("K_REVISION", None)
        os.environ.pop("K_CONFIGURATION", None)
        os.environ.pop("CLOUD_RUN_JOB", None)

        # When: 환경 감지 실행
        is_cloud_run = is_cloud_run_environment()

        # Then: Cloud Run 환경으로 인식
        assert is_cloud_run is True

    def test_cloud_run_environment_detection_with_job(self):
        """CLOUD_RUN_JOB 환경 변수로 Cloud Run 환경 감지 테스트"""
        # Given: Cloud Run Job 환경 설정
        os.environ["CLOUD_RUN_JOB"] = "test-job"
        os.environ.pop("K_SERVICE", None)
        os.environ.pop("K_REVISION", None)
        os.environ.pop("K_CONFIGURATION", None)

        # When: 환경 감지 실행
        is_cloud_run = is_cloud_run_environment()

        # Then: Cloud Run 환경으로 인식
        assert is_cloud_run is True

    def test_cloud_run_environment_detection_all_variables(self):
        """모든 Cloud Run 환경 변수 설정 시 감지 테스트"""
        # Given: 완전한 Cloud Run 서비스 환경
        os.environ.update(
            {
                "K_SERVICE": "comprehensive-service",
                "K_REVISION": "comprehensive-service-00001-abc",
                "K_CONFIGURATION": "comprehensive-service",
                "CLOUD_RUN_REGION": "asia-northeast3",
            }
        )

        # When: 환경 감지 및 메타데이터 조회
        is_cloud_run = is_cloud_run_environment()
        service_name = get_cloud_run_service_name()
        revision = get_cloud_run_revision()
        region = get_cloud_run_region()

        # Then: 모든 값이 올바르게 감지됨
        assert is_cloud_run is True
        assert service_name == "comprehensive-service"
        assert revision == "comprehensive-service-00001-abc"
        assert region == "asia-northeast3"

    def test_non_cloud_run_environment(self):
        """Cloud Run이 아닌 환경 감지 테스트"""
        # Given: Cloud Run 환경 변수 모두 제거
        for key in ["K_SERVICE", "K_REVISION", "K_CONFIGURATION", "CLOUD_RUN_JOB"]:
            os.environ.pop(key, None)

        # When: 환경 감지 실행
        is_cloud_run = is_cloud_run_environment()
        service_name = get_cloud_run_service_name()
        revision = get_cloud_run_revision()

        # Then: Cloud Run이 아닌 환경으로 인식
        assert is_cloud_run is False
        assert service_name is None
        assert revision is None

    def test_cloud_run_status_comprehensive(self):
        """포괄적인 Cloud Run 상태 조회 테스트"""
        # Given: 완전한 Cloud Run 환경 설정
        os.environ.update(
            {
                "K_SERVICE": "status-service",
                "K_REVISION": "status-service-00002-def",
                "CLOUD_RUN_REGION": "us-central1",
            }
        )

        # When: 상태 조회
        status = get_cloud_run_status()

        # Then: 모든 상태 정보가 올바르게 반환됨
        assert status["is_cloud_run"] is True
        assert status["service_name"] == "status-service"
        assert status["revision"] == "status-service-00002-def"
        assert status["region"] == "us-central1"

    def test_cloud_run_region_default_value(self):
        """Cloud Run 리전 기본값 테스트"""
        # Given: CLOUD_RUN_REGION 환경 변수 제거
        os.environ.pop("CLOUD_RUN_REGION", None)

        # When: 리전 조회
        region = get_cloud_run_region()

        # Then: 기본값 반환
        assert region == "asia-northeast3"


class TestServiceDiscoveryPatterns:
    """Service Discovery 패턴 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # 싱글톤 인스턴스 리셋을 위해 새로운 인스턴스 생성
        self.discovery = CloudRunServiceDiscovery()
        self.discovery._services = {}
        self.discovery._initialized = False

    @pytest.mark.asyncio
    async def test_service_discovery_initialization(self):
        """Service Discovery 초기화 테스트"""
        # Given: 초기화되지 않은 Service Discovery
        assert self.discovery._initialized is False

        # When: 초기화 실행
        await self.discovery.initialize()

        # Then: 초기화 완료
        assert self.discovery._initialized is True

    def test_service_registration_and_retrieval(self):
        """서비스 등록 및 조회 테스트"""
        # Given: 서비스 엔드포인트 생성
        endpoint = ServiceEndpoint(
            name="billing-service",
            url="https://billing-service-abc123-uc.a.run.app",
            region="us-central1",
        )

        # When: 서비스 등록
        self.discovery.register_service("billing", endpoint)

        # Then: 등록된 서비스 조회 가능
        retrieved = self.discovery.get_service("billing")
        assert retrieved is not None
        assert retrieved.name == "billing-service"
        assert retrieved.url == "https://billing-service-abc123-uc.a.run.app"
        assert retrieved.region == "us-central1"

    def test_service_list_management(self):
        """서비스 목록 관리 테스트"""
        # Given: 여러 서비스 엔드포인트
        services = [
            (
                "user",
                ServiceEndpoint(
                    "user-service", "https://user-service-def456-uc.a.run.app"
                ),
            ),
            (
                "auth",
                ServiceEndpoint(
                    "auth-service", "https://auth-service-ghi789-uc.a.run.app"
                ),
            ),
            (
                "payment",
                ServiceEndpoint(
                    "payment-service", "https://payment-service-jkl012-uc.a.run.app"
                ),
            ),
        ]

        # When: 서비스들 등록
        for name, endpoint in services:
            self.discovery.register_service(name, endpoint)

        # Then: 등록된 서비스 목록 조회
        service_list = self.discovery.list_services()
        assert len(service_list) == 3
        assert "user" in service_list
        assert "auth" in service_list
        assert "payment" in service_list

    def test_service_endpoint_health_check_url_generation(self):
        """서비스 엔드포인트 헬스 체크 URL 생성 테스트"""
        # Given: 서비스 엔드포인트
        endpoint = ServiceEndpoint(
            name="health-service", url="https://health-service-mno345-uc.a.run.app"
        )

        # When: 헬스 체크 URL 확인
        # Then: 올바른 헬스 체크 URL 생성
        expected_health_url = "https://health-service-mno345-uc.a.run.app/health"
        assert endpoint.health_check_url == expected_health_url

    @pytest.mark.asyncio
    async def test_service_endpoint_health_check(self):
        """서비스 엔드포인트 헬스 체크 테스트"""
        # Given: 건강한 서비스 엔드포인트
        endpoint = ServiceEndpoint(
            name="healthy-service", url="https://healthy-service-pqr678-uc.a.run.app"
        )

        # When: 헬스 체크 실행
        is_healthy = await endpoint.check_health()

        # Then: 헬스 체크 결과 확인
        assert is_healthy is True
        assert endpoint.last_health_check is not None
        assert isinstance(endpoint.last_health_check, datetime)

    @pytest.mark.asyncio
    async def test_discover_services_with_pattern(self):
        """패턴을 사용한 서비스 탐색 테스트"""
        # Given: 서비스 등록
        discovery = get_service_discovery()
        discovery._services = {}  # 리셋

        endpoints = [
            ServiceEndpoint(
                "api-user-service", "https://api-user-service-stu901-uc.a.run.app"
            ),
            ServiceEndpoint(
                "api-billing-service", "https://api-billing-service-vwx234-uc.a.run.app"
            ),
            ServiceEndpoint(
                "worker-service", "https://worker-service-yza567-uc.a.run.app"
            ),
        ]

        for i, endpoint in enumerate(endpoints):
            discovery.register_service(f"service-{i}", endpoint)

        # When: 패턴으로 서비스 탐색
        api_services = await discover_services("api")
        all_services = await discover_services("*")

        # Then: 패턴에 맞는 서비스만 반환
        assert len(api_services) == 2  # api로 시작하는 서비스 2개
        assert len(all_services) == 3  # 전체 서비스 3개

    @pytest.mark.asyncio
    async def test_call_service_success(self):
        """서비스 호출 성공 테스트"""
        # Given: 등록된 서비스
        discovery = get_service_discovery()
        discovery._services = {}  # 리셋

        endpoint = ServiceEndpoint(
            name="call-test-service",
            url="https://call-test-service-abc890-uc.a.run.app",
        )
        endpoint.is_healthy = True
        discovery.register_service("call-test", endpoint)

        # When: 서비스 호출
        result = await call_service(
            service_name="call-test",
            path="/api/users",
            method="GET",
            data={"user_id": 123},
        )

        # Then: 성공적인 응답
        assert result.is_success()
        response_data = result.unwrap()
        assert response_data["status"] == "success"
        assert response_data["data"]["user_id"] == 123

    @pytest.mark.asyncio
    async def test_call_service_not_found(self):
        """존재하지 않는 서비스 호출 테스트"""
        # Given: 등록되지 않은 서비스 이름
        discovery = get_service_discovery()
        discovery._services = {}  # 리셋

        # When: 존재하지 않는 서비스 호출
        result = await call_service("nonexistent-service", "/api/test")

        # Then: 실패 결과
        assert result.is_failure()
        assert "Service not found: nonexistent-service" in result.unwrap_err()

    @pytest.mark.asyncio
    async def test_call_service_unhealthy(self):
        """건강하지 않은 서비스 호출 테스트"""
        # Given: 건강하지 않은 서비스
        discovery = get_service_discovery()
        discovery._services = {}  # 리셋

        endpoint = ServiceEndpoint(
            "unhealthy-service", "https://unhealthy-service-def123-uc.a.run.app"
        )
        endpoint.is_healthy = False
        discovery.register_service("unhealthy", endpoint)

        # When: 건강하지 않은 서비스 호출
        result = await call_service("unhealthy", "/api/test")

        # Then: 실패 결과
        assert result.is_failure()
        assert "Service unhealthy: unhealthy" in result.unwrap_err()


class TestCloudTaskQueuePatterns:
    """Cloud Task Queue 패턴 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # 싱글톤 인스턴스 리셋
        self.task_queue = CloudTaskQueue()
        self.task_queue._queue = []
        self.task_queue._processing = False

    @pytest.mark.asyncio
    async def test_task_queue_enqueue(self):
        """태스크 큐 추가 테스트"""
        # Given: 태스크 데이터
        task_data = {
            "url": "/api/process-payment",
            "payload": {"payment_id": "pay_123", "amount": 100.00},
            "method": "POST",
        }

        # When: 태스크 추가
        task_id = await self.task_queue.enqueue(task_data)

        # Then: 태스크가 큐에 추가됨
        assert task_id is not None
        assert len(self.task_queue._queue) == 1
        assert self.task_queue._queue[0]["payload"]["payment_id"] == "pay_123"

    @pytest.mark.asyncio
    async def test_task_queue_processing(self):
        """태스크 큐 처리 테스트"""
        # Given: 여러 태스크 추가
        tasks = [
            {"url": "/task1", "payload": {"data": "task1"}},
            {"url": "/task2", "payload": {"data": "task2"}},
            {"url": "/task3", "payload": {"data": "task3"}},
        ]

        for task in tasks:
            await self.task_queue.enqueue(task)

        # When: 태스크 처리 시뮬레이션을 위한 잠시 대기
        await asyncio.sleep(0.2)

        # Then: 큐가 처리됨
        assert len(self.task_queue._queue) == 0

    def test_task_handler_decorator(self):
        """태스크 핸들러 데코레이터 테스트"""

        # Given: 태스크 핸들러 함수
        @task_handler("/api/process-order")
        async def process_order_handler(payload):
            return {"status": "processed", "order_id": payload.get("order_id")}

        # When: 데코레이터 적용 확인
        # Then: 함수가 정상적으로 장식됨
        assert callable(process_order_handler)

    @pytest.mark.asyncio
    async def test_submit_task_helper(self):
        """태스크 제출 헬퍼 함수 테스트"""
        # Given: 태스크 데이터
        url = "/api/send-notification"
        payload = {
            "user_id": "user_456",
            "notification_type": "email",
            "message": "Your order has been processed",
        }

        # When: 태스크 제출
        task_id = await submit_task(url, payload, delay_seconds=0)

        # Then: 태스크 ID 반환
        assert task_id is not None
        assert isinstance(task_id, str)

    @pytest.mark.asyncio
    async def test_schedule_task_helper(self):
        """태스크 스케줄링 헬퍼 함수 테스트"""
        # Given: 미래 실행 시간
        future_time = datetime.now() + timedelta(minutes=30)
        url = "/api/scheduled-maintenance"
        payload = {"maintenance_type": "database_cleanup"}

        # When: 태스크 스케줄링
        task_id = await schedule_task(url, payload, future_time)

        # Then: 스케줄된 태스크 ID 반환
        assert task_id is not None
        assert isinstance(task_id, str)

    @pytest.mark.asyncio
    async def test_task_queue_with_delay(self):
        """지연된 태스크 처리 테스트"""
        # Given: 지연 시간이 있는 태스크
        url = "/api/delayed-task"
        payload = {"task_type": "delayed_processing"}
        delay_seconds = 1

        # When: 지연된 태스크 제출
        start_time = time.time()
        task_id = await submit_task(url, payload, delay_seconds)
        end_time = time.time()

        # Then: 지연 시간이 적용됨
        elapsed_time = end_time - start_time
        assert elapsed_time >= delay_seconds
        assert task_id is not None


class TestMonitoringIntegration:
    """모니터링 통합 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # 싱글톤 인스턴스 리셋
        self.monitoring_client = CloudMonitoringClient()
        self.monitoring_client._metrics = []
        self.monitoring_client._logs = []

    def test_monitoring_client_singleton(self):
        """모니터링 클라이언트 싱글톤 테스트"""
        # Given: 여러 번 클라이언트 요청
        client1 = get_monitoring_client()
        client2 = get_monitoring_client()

        # When & Then: 같은 인스턴스 반환
        assert client1 is client2

    def test_metric_recording(self):
        """메트릭 기록 테스트"""
        # Given: 메트릭 데이터
        metric_name = "api_requests_total"
        metric_value = 150.0
        metric_unit = "requests"
        labels = {"endpoint": "/api/users", "method": "GET", "status": "200"}

        # When: 메트릭 기록
        self.monitoring_client.record_metric(
            metric_name, metric_value, metric_unit, labels
        )

        # Then: 메트릭이 저장됨
        metrics = self.monitoring_client.get_metrics()
        assert len(metrics) == 1
        assert metrics[0]["name"] == metric_name
        assert metrics[0]["value"] == metric_value
        assert metrics[0]["unit"] == metric_unit
        assert metrics[0]["labels"]["endpoint"] == "/api/users"

    def test_metric_recording_helper(self):
        """메트릭 기록 헬퍼 함수 테스트"""
        # Given: 헬퍼 함수 사용
        record_metric(
            name="response_time_ms",
            value=250.5,
            unit="milliseconds",
            labels={"service": "user-service", "operation": "get_user"},
        )

        # When: 메트릭 조회
        client = get_monitoring_client()
        metrics = client.get_metrics()

        # Then: 메트릭이 기록됨
        assert len(metrics) >= 1
        response_time_metric = next(
            m for m in metrics if m["name"] == "response_time_ms"
        )
        assert response_time_metric["value"] == 250.5
        assert response_time_metric["labels"]["service"] == "user-service"

    def test_logging_functions(self):
        """로깅 함수들 테스트"""
        # Given: 다양한 로그 레벨
        info_message = "User authentication successful"
        warning_message = "API rate limit approaching"
        error_message = "Database connection failed"

        # When: 로그 기록
        log_info(info_message, user_id="user_789")
        log_warning(warning_message, rate_limit_remaining=10)
        log_error(error_message, database="postgres", retry_count=3)

        # Then: 로그가 기록됨
        client = get_monitoring_client()
        logs = client.get_logs()

        assert len(logs) == 3

        info_log = next(log for log in logs if log["level"] == "INFO")
        warning_log = next(log for log in logs if log["level"] == "WARNING")
        error_log = next(log for log in logs if log["level"] == "ERROR")

        assert info_log["message"] == info_message
        assert info_log["user_id"] == "user_789"

        assert warning_log["message"] == warning_message
        assert warning_log["rate_limit_remaining"] == 10

        assert error_log["message"] == error_message
        assert error_log["database"] == "postgres"

    @pytest.mark.asyncio
    async def test_performance_monitoring_decorator_async(self):
        """비동기 성능 모니터링 데코레이터 테스트"""

        # Given: 모니터링 장식된 비동기 함수
        @monitor_performance
        async def async_api_call():
            await asyncio.sleep(0.1)  # 100ms 시뮬레이션
            return {"data": "async_result"}

        # When: 함수 실행
        result = await async_api_call()

        # Then: 결과 반환 및 메트릭 기록
        assert result["data"] == "async_result"

        client = get_monitoring_client()
        metrics = client.get_metrics()

        # 함수 실행 시간 메트릭 확인
        duration_metrics = [
            m for m in metrics if "async_api_call.duration" in m["name"]
        ]
        assert len(duration_metrics) >= 1
        assert duration_metrics[0]["value"] >= 100  # 최소 100ms

    def test_performance_monitoring_decorator_sync(self):
        """동기 성능 모니터링 데코레이터 테스트"""

        # Given: 모니터링 장식된 동기 함수
        @monitor_performance
        def sync_calculation():
            time.sleep(0.05)  # 50ms 시뮬레이션
            return {"result": 42}

        # When: 함수 실행
        result = sync_calculation()

        # Then: 결과 반환 및 메트릭 기록
        assert result["result"] == 42

        client = get_monitoring_client()
        metrics = client.get_metrics()

        # 함수 실행 시간 메트릭 확인
        duration_metrics = [
            m for m in metrics if "sync_calculation.duration" in m["name"]
        ]
        assert len(duration_metrics) >= 1
        assert duration_metrics[0]["value"] >= 50  # 최소 50ms

    @pytest.mark.asyncio
    async def test_performance_monitoring_with_error(self):
        """에러 발생 시 성능 모니터링 테스트"""

        # Given: 에러가 발생하는 함수
        @monitor_performance
        async def failing_function():
            await asyncio.sleep(0.02)
            raise ValueError("Test error")

        # When: 함수 실행 (에러 발생)
        with pytest.raises(ValueError, match="Test error"):
            await failing_function()

        # Then: 에러 로그가 기록됨
        client = get_monitoring_client()
        logs = client.get_logs()

        error_logs = [log for log in logs if log["level"] == "ERROR"]
        assert len(error_logs) >= 1
        assert "failing_function" in error_logs[0]["message"]


class TestAutoScalingOptimization:
    """Auto Scaling 최적화 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # 싱글톤 인스턴스 리셋
        self.optimizer = AutoScalingOptimizer()
        self.optimizer._config = {
            "min_instances": 0,
            "max_instances": 100,
            "target_cpu": 60,
            "target_memory": 70,
            "scale_down_delay": 300,
        }
        self.optimizer._metrics = []

    def test_autoscaling_optimizer_singleton(self):
        """Auto Scaling 옵티마이저 싱글톤 테스트"""
        # Given: 여러 번 옵티마이저 요청
        optimizer1 = get_autoscaling_optimizer()
        optimizer2 = get_autoscaling_optimizer()

        # When & Then: 같은 인스턴스 반환
        assert optimizer1 is optimizer2

    def test_scaling_configuration(self):
        """스케일링 설정 테스트"""
        # Given: 새로운 설정
        new_config = {
            "min_instances": 2,
            "max_instances": 50,
            "target_cpu": 70,
            "scale_down_delay": 600,
        }

        # When: 설정 업데이트
        self.optimizer.configure(**new_config)

        # Then: 설정이 업데이트됨
        assert self.optimizer._config["min_instances"] == 2
        assert self.optimizer._config["max_instances"] == 50
        assert self.optimizer._config["target_cpu"] == 70
        assert self.optimizer._config["scale_down_delay"] == 600

        # 기존 설정은 유지
        assert self.optimizer._config["target_memory"] == 70

    def test_metrics_analysis(self):
        """메트릭 분석 테스트"""
        # Given: 옵티마이저 설정
        # When: 메트릭 분석 실행
        analysis = self.optimizer.analyze_metrics()

        # Then: 분석 결과 반환
        assert isinstance(analysis, dict)
        assert "should_scale_up" in analysis
        assert "should_scale_down" in analysis
        assert "current_instances" in analysis
        assert "recommended_instances" in analysis

        # 기본값 검증
        assert analysis["current_instances"] == 1
        assert analysis["recommended_instances"] == 1

    def test_scaling_recommendations(self):
        """스케일링 권장사항 테스트"""
        # Given: 기본 설정
        # When: 권장사항 조회
        recommendations = self.optimizer.get_recommendations()

        # Then: 권장사항 목록 반환
        assert isinstance(recommendations, list)
        # 기본 상태에서는 권장사항이 없을 수 있음

    def test_optimize_scaling_helper(self):
        """스케일링 최적화 헬퍼 함수 테스트"""
        # Given: 스케일링 설정
        config = {"min_instances": 1, "max_instances": 20, "target_cpu": 80}

        # When: 스케일링 최적화 실행
        optimize_scaling(**config)

        # Then: 설정이 적용됨
        optimizer = get_autoscaling_optimizer()
        assert optimizer._config["min_instances"] == 1
        assert optimizer._config["max_instances"] == 20
        assert optimizer._config["target_cpu"] == 80

    def test_scaling_stats_helper(self):
        """스케일링 통계 헬퍼 함수 테스트"""
        # Given: 옵티마이저 설정
        # When: 통계 조회
        stats = get_scaling_stats()

        # Then: 통계 데이터 반환
        assert isinstance(stats, dict)
        assert "should_scale_up" in stats
        assert "should_scale_down" in stats
        assert "current_instances" in stats
        assert "recommended_instances" in stats


class TestCloudRunServiceLifecycle:
    """Cloud Run 서비스 생명주기 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # 환경 변수 설정
        os.environ["K_SERVICE"] = "lifecycle-test-service"
        os.environ["K_REVISION"] = "lifecycle-test-service-00001-abc"

    def teardown_method(self):
        """테스트 후 정리"""
        # 환경 변수 정리
        os.environ.pop("K_SERVICE", None)
        os.environ.pop("K_REVISION", None)

    @pytest.mark.asyncio
    async def test_cloud_run_services_initialization_in_cloud_run(self):
        """Cloud Run 환경에서 서비스 초기화 테스트"""
        # Given: Cloud Run 환경
        assert is_cloud_run_environment() is True

        # When: 서비스 초기화
        await initialize_cloud_run_services()

        # Then: 서비스들이 초기화됨
        discovery = get_service_discovery()
        assert discovery._initialized is True

        monitoring = get_monitoring_client()
        logs = monitoring.get_logs()

        # 초기화 로그 확인
        init_logs = [log for log in logs if "initialized" in log["message"].lower()]
        assert len(init_logs) >= 1

    @pytest.mark.asyncio
    async def test_cloud_run_services_initialization_non_cloud_run(self):
        """Cloud Run이 아닌 환경에서 서비스 초기화 테스트"""
        # Given: Cloud Run이 아닌 환경
        os.environ.pop("K_SERVICE", None)
        os.environ.pop("K_REVISION", None)

        assert is_cloud_run_environment() is False

        # When: 서비스 초기화
        await initialize_cloud_run_services()

        # Then: 초기화 건너뛰기 메시지 확인
        # (실제 로그는 logger를 통해 출력되므로 여기서는 환경 확인만)
        assert is_cloud_run_environment() is False

    @pytest.mark.asyncio
    async def test_cloud_run_services_shutdown(self):
        """Cloud Run 서비스 종료 테스트"""
        # Given: 초기화된 서비스들
        await initialize_cloud_run_services()

        # When: 서비스 종료
        await shutdown_cloud_run_services()

        # Then: 종료 처리 완료 (현재는 pass이지만 실제로는 리소스 정리)
        # 이 테스트는 종료 함수가 에러 없이 실행되는지 확인


class TestCloudRunHelpersIntegrationScenarios:
    """Cloud Run Helpers 통합 시나리오 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # Cloud Run 환경 설정
        os.environ.update(
            {
                "K_SERVICE": "integration-service",
                "K_REVISION": "integration-service-00001-xyz",
                "CLOUD_RUN_REGION": "asia-northeast3",
                "GOOGLE_CLOUD_PROJECT": "integration-project-12345",
            }
        )

    def teardown_method(self):
        """테스트 후 정리"""
        # 환경 변수 정리
        for key in [
            "K_SERVICE",
            "K_REVISION",
            "CLOUD_RUN_REGION",
            "GOOGLE_CLOUD_PROJECT",
        ]:
            os.environ.pop(key, None)

    @pytest.mark.asyncio
    async def test_complete_microservice_communication_flow(self):
        """완전한 마이크로서비스 통신 플로우 테스트"""
        # Given: 여러 마이크로서비스 등록
        discovery = get_service_discovery()
        discovery._services = {}  # 리셋

        services = [
            (
                "user",
                ServiceEndpoint(
                    "user-service",
                    "https://user-service-abc123-an3.a.run.app",
                    "asia-northeast3",
                ),
            ),
            (
                "billing",
                ServiceEndpoint(
                    "billing-service",
                    "https://billing-service-def456-an3.a.run.app",
                    "asia-northeast3",
                ),
            ),
            (
                "notification",
                ServiceEndpoint(
                    "notification-service",
                    "https://notification-service-ghi789-an3.a.run.app",
                    "asia-northeast3",
                ),
            ),
        ]

        for name, endpoint in services:
            discovery.register_service(name, endpoint)

        # When: 서비스 간 통신 플로우 시뮬레이션

        # 1. 사용자 정보 조회
        user_result = await call_service("user", "/api/users/123")
        assert user_result.is_success()

        # 2. 결제 처리
        billing_result = await call_service(
            "billing",
            "/api/payments",
            method="POST",
            data={"user_id": 123, "amount": 99.99},
        )
        assert billing_result.is_success()

        # 3. 알림 발송 (비동기 태스크로)
        task_queue = get_task_queue()
        notification_task_id = await task_queue.enqueue(
            {
                "service": "notification",
                "path": "/api/notifications",
                "payload": {"user_id": 123, "type": "payment_success"},
            }
        )
        assert notification_task_id is not None

        # Then: 전체 플로우 완료
        assert len(discovery.list_services()) == 3

    @pytest.mark.asyncio
    async def test_performance_monitoring_and_scaling_integration(self):
        """성능 모니터링 및 스케일링 통합 테스트"""
        # Given: 성능 모니터링 및 스케일링 설정
        monitoring = get_monitoring_client()
        optimizer = get_autoscaling_optimizer()

        monitoring._metrics = []  # 리셋

        # When: 고부하 시나리오 시뮬레이션

        # 1. 높은 CPU 사용률 메트릭 기록
        for i in range(10):
            record_metric(
                "cpu_usage", 85.0 + i, "percent", {"instance": f"instance-{i}"}
            )

        # 2. 높은 요청 수 메트릭 기록
        for i in range(20):
            record_metric(
                "requests_per_second", 50.0 + i * 2, "rps", {"endpoint": "/api/heavy"}
            )

        # 3. 스케일링 분석
        scaling_analysis = optimizer.analyze_metrics()
        scaling_recommendations = optimizer.get_recommendations()

        # Then: 메트릭 수집 및 분석 완료
        metrics = monitoring.get_metrics()
        cpu_metrics = [m for m in metrics if m["name"] == "cpu_usage"]
        request_metrics = [m for m in metrics if m["name"] == "requests_per_second"]

        assert len(cpu_metrics) == 10
        assert len(request_metrics) == 20
        assert isinstance(scaling_analysis, dict)
        assert isinstance(scaling_recommendations, list)

    @pytest.mark.asyncio
    async def test_error_recovery_and_circuit_breaker_pattern(self):
        """에러 복구 및 Circuit Breaker 패턴 테스트"""
        # Given: 불안정한 서비스 시뮬레이션
        discovery = get_service_discovery()
        discovery._services = {}  # 리셋

        # 불안정한 서비스 등록
        unstable_endpoint = ServiceEndpoint(
            "unstable-service", "https://unstable-service-jkl012-an3.a.run.app"
        )
        discovery.register_service("unstable", unstable_endpoint)

        # When: 여러 번 서비스 호출 (일부 실패 시뮬레이션)
        results = []

        for i in range(10):
            # 홀수 번째 호출은 서비스를 건강하지 않게 설정
            if i % 2 == 1:
                unstable_endpoint.is_healthy = False
            else:
                unstable_endpoint.is_healthy = True

            result = await call_service("unstable", f"/api/data/{i}")
            results.append(result)

            # 에러 로깅
            if result.is_failure():
                log_error(
                    f"Service call failed for iteration {i}", error=result.unwrap_err()
                )

        # Then: 성공과 실패가 적절히 기록됨
        successful_calls = [r for r in results if r.is_success()]
        failed_calls = [r for r in results if r.is_failure()]

        assert len(successful_calls) == 5  # 짝수 번째 호출
        assert len(failed_calls) == 5  # 홀수 번째 호출

        # 에러 로그 확인
        monitoring = get_monitoring_client()
        logs = monitoring.get_logs()
        error_logs = [log for log in logs if log["level"] == "ERROR"]

        assert len(error_logs) == 5  # 실패한 호출에 대한 에러 로그

    @pytest.mark.asyncio
    async def test_scheduled_maintenance_task_workflow(self):
        """예약된 유지보수 태스크 워크플로우 테스트"""
        # Given: 유지보수 태스크 스케줄링
        maintenance_time = datetime.now() + timedelta(seconds=2)  # 2초 후 실행

        # When: 유지보수 태스크 스케줄링
        maintenance_task_id = await schedule_task(
            url="/api/maintenance/database-cleanup",
            payload={
                "cleanup_type": "old_logs",
                "retention_days": 30,
                "tables": ["access_logs", "error_logs", "audit_logs"],
            },
            schedule_time=maintenance_time,
        )

        # Then: 태스크가 스케줄됨
        assert maintenance_task_id is not None

        # 스케줄된 시간까지 대기
        await asyncio.sleep(2.5)

        # 태스크가 처리되었는지 확인 (큐가 비어있음)
        task_queue = get_task_queue()
        assert len(task_queue._queue) == 0  # 모든 태스크가 처리됨

    @pytest.mark.asyncio
    async def test_comprehensive_monitoring_dashboard_data(self):
        """포괄적인 모니터링 대시보드 데이터 테스트"""
        # Given: 다양한 메트릭 및 로그 생성
        monitoring = get_monitoring_client()
        monitoring._metrics = []  # 리셋
        monitoring._logs = []  # 리셋

        # When: 다양한 운영 메트릭 시뮬레이션

        # 1. API 응답 시간 메트릭
        api_endpoints = ["/api/users", "/api/orders", "/api/payments", "/api/reports"]
        for endpoint in api_endpoints:
            for i in range(5):
                response_time = 100 + (i * 20)  # 100ms ~ 180ms
                record_metric(
                    "api_response_time", response_time, "ms", {"endpoint": endpoint}
                )

        # 2. 에러율 메트릭
        for endpoint in api_endpoints:
            error_rate = (
                2.5 if "payments" in endpoint else 1.0
            )  # 결제 API는 높은 에러율
            record_metric("error_rate", error_rate, "percent", {"endpoint": endpoint})

        # 3. 서비스 상태 로그
        services_status = [
            ("user-service", "healthy"),
            ("billing-service", "degraded"),
            ("notification-service", "healthy"),
            ("reporting-service", "maintenance"),
        ]

        for service, status in services_status:
            if status == "healthy":
                log_info(
                    f"Service {service} is running normally",
                    service=service,
                    status=status,
                )
            elif status == "degraded":
                log_warning(
                    f"Service {service} is experiencing issues",
                    service=service,
                    status=status,
                )
            else:
                log_error(
                    f"Service {service} is under maintenance",
                    service=service,
                    status=status,
                )

        # 4. 인프라 메트릭
        infra_metrics = [
            ("memory_usage", 75.5, "percent"),
            ("disk_usage", 45.2, "percent"),
            ("network_in", 1024.0, "KB/s"),
            ("network_out", 512.0, "KB/s"),
        ]

        for metric_name, value, unit in infra_metrics:
            record_metric(metric_name, value, unit, {"region": "asia-northeast3"})

        # Then: 대시보드용 데이터 수집 완료
        all_metrics = monitoring.get_metrics()
        all_logs = monitoring.get_logs()

        # 메트릭 검증
        api_metrics = [m for m in all_metrics if m["name"] == "api_response_time"]
        error_metrics = [m for m in all_metrics if m["name"] == "error_rate"]
        infra_metrics = [
            m
            for m in all_metrics
            if m["name"] in ["memory_usage", "disk_usage", "network_in", "network_out"]
        ]

        assert len(api_metrics) == 20  # 4 endpoints * 5 measurements
        assert len(error_metrics) == 4  # 4 endpoints
        assert len(infra_metrics) == 4  # 4 infrastructure metrics

        # 로그 검증
        info_logs = [log for log in all_logs if log["level"] == "INFO"]
        warning_logs = [log for log in all_logs if log["level"] == "WARNING"]
        error_logs = [log for log in all_logs if log["level"] == "ERROR"]

        assert len(info_logs) == 2  # healthy services
        assert len(warning_logs) == 1  # degraded service
        assert len(error_logs) == 1  # maintenance service
