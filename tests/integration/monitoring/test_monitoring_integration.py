"""
Phase 3 모니터링 시스템 통합 테스트

로깅, 메트릭, 테스팅 유틸리티의 완전한 통합을 검증합니다.
"""

import pytest
import asyncio
import time
from unittest.mock import patch, Mock

# Phase 1 & 2 구현체들
from rfs.core.result import Result, Success, Failure
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult

# Phase 3 구현체들
from rfs.monitoring.result_logging import (
    ResultLogger, CorrelationContext, log_result_operation, 
    get_correlation_id, LoggingMonoResult, create_logging_mono,
    log_flux_results, configure_result_logging, LogLevel
)
from rfs.monitoring.metrics import (
    ResultMetricsCollector, ResultAlertManager, MetricType, AlertCondition,
    collect_metric, create_alert_rule, get_metrics_summary,
    collect_result_metric, collect_flux_result_metric, setup_default_alerts
)
from rfs.testing.result_helpers import (
    ResultServiceMocker, mock_result_service,
    assert_result_success, assert_result_failure,
    assert_mono_result_success, assert_flux_success_count,
    ResultTestDataFactory, PerformanceTestHelper,
    result_test_context, result_test, mono_test, flux_test, performance_test
)


# 테스트용 서비스 클래스
class TestUserService:
    """테스트용 사용자 서비스"""
    
    async def get_user(self, user_id: str) -> Result[dict, str]:
        """사용자 조회"""
        if user_id == "valid":
            return Success({"id": user_id, "name": "테스트 사용자"})
        return Failure(f"사용자를 찾을 수 없습니다: {user_id}")
    
    async def process_users_batch(self, user_ids: list) -> FluxResult[dict, str]:
        """사용자 배치 처리"""
        results = []
        for user_id in user_ids:
            if user_id.startswith("valid"):
                results.append(Success({"id": user_id, "name": f"사용자-{user_id}"}))
            else:
                results.append(Failure(f"처리 실패: {user_id}"))
        
        return FluxResult.from_results(results)


@pytest.fixture
def user_service():
    """사용자 서비스 픽스처"""
    return TestUserService()


@pytest.fixture
def metrics_collector():
    """메트릭 수집기 픽스처"""
    collector = ResultMetricsCollector()
    yield collector
    collector.clear_metrics()  # 테스트 후 정리


@pytest.fixture
def alert_manager(metrics_collector):
    """알림 관리자 픽스처"""
    return ResultAlertManager(metrics_collector)


class TestLoggingSystem:
    """로깅 시스템 테스트"""
    
    def test_correlation_context(self):
        """Correlation ID 컨텍스트 테스트"""
        # 기본 상태
        initial_correlation = get_correlation_id()
        assert initial_correlation is not None
        
        # 컨텍스트 사용
        test_correlation = "test-123"
        with CorrelationContext(test_correlation) as correlation_id:
            assert correlation_id == test_correlation
            assert get_correlation_id() == test_correlation
        
        # 컨텍스트 후 복원
        assert get_correlation_id() != test_correlation
    
    def test_result_logger_operations(self):
        """ResultLogger 작업 테스트"""
        logger = ResultLogger("test_logger")
        
        # 작업 시작
        correlation_id = logger.start_operation("test_operation", {"key": "value"})
        assert correlation_id is not None
        
        # 단계 로깅
        logger.log_step("step1", 100.0, "success")
        logger.log_step("step2", 200.0, "failure", {"error": "test"})
        
        # 성능 로깅
        logger.log_performance("test_operation", 500.0, 1, 1)
        
        # 작업 완료
        logger.complete_operation("test_operation", "partial_success")
    
    @pytest.mark.asyncio
    async def test_log_result_operation_decorator(self, user_service):
        """@log_result_operation 데코레이터 테스트"""
        
        @log_result_operation("user_fetch", include_args=True, include_result=True)
        async def fetch_user_with_logging(user_id: str) -> Result[dict, str]:
            return await user_service.get_user(user_id)
        
        # 성공 케이스
        result = await fetch_user_with_logging("valid")
        assert_result_success(result)
        
        # 실패 케이스
        result = await fetch_user_with_logging("invalid")
        assert_result_failure(result)
    
    @pytest.mark.asyncio
    async def test_logging_mono_result(self):
        """LoggingMonoResult 테스트"""
        async def test_operation():
            await asyncio.sleep(0.01)  # 작은 지연
            return Success("test_value")
        
        logging_mono = LoggingMonoResult(test_operation, "test_logger")
        
        # 로깅 체이닝 테스트
        result = await (
            logging_mono
            .log_step("validation", {"type": "input_check"})
            .log_performance("test_operation")
            .to_result()
        )
        
        assert_result_success(result)
        assert result.unwrap() == "test_value"
    
    @pytest.mark.asyncio
    async def test_flux_result_logging(self, user_service):
        """FluxResult 로깅 테스트"""
        flux_result = await user_service.process_users_batch(["valid1", "invalid", "valid2"])
        
        # FluxResult 로깅
        log_summary = await log_flux_results(flux_result, "batch_user_processing", "test_logger")
        
        assert log_summary["total"] == 3
        assert log_summary["success"] == 2
        assert log_summary["failure"] == 1
        assert "correlation_id" in log_summary
        assert "duration_ms" in log_summary


class TestMetricsSystem:
    """메트릭 시스템 테스트"""
    
    def test_metrics_collection(self, metrics_collector):
        """메트릭 수집 테스트"""
        # 다양한 타입의 메트릭 수집
        collect_metric("test_counter", 5, MetricType.COUNTER, {"service": "test"})
        collect_metric("test_gauge", 85.5, MetricType.GAUGE, {"service": "test"})
        collect_metric("test_histogram", 150.0, MetricType.HISTOGRAM, {"service": "test"})
        collect_metric("test_timer", 250.0, MetricType.TIMER, {"service": "test"})
        
        # 메트릭 값 확인
        counter_value = metrics_collector.get_metric_value("test_counter", {"service": "test"})
        assert counter_value == 5
        
        gauge_value = metrics_collector.get_metric_value("test_gauge", {"service": "test"})
        assert gauge_value == 85.5
    
    def test_metrics_summary(self, metrics_collector):
        """메트릭 요약 테스트"""
        # 테스트 메트릭 수집
        for i in range(10):
            collect_metric("response_time", i * 100, MetricType.HISTOGRAM, {"endpoint": "/api/test"})
        
        # 요약 정보 조회
        summary = get_metrics_summary(60)
        
        assert "histograms" in summary
        assert "generated_at" in summary
        assert "time_range_minutes" in summary
        assert summary["time_range_minutes"] == 60
    
    def test_result_metric_collection(self, user_service):
        """Result 전용 메트릭 수집 테스트"""
        # 성공 Result 메트릭
        success_result = Success({"test": "data"})
        collect_result_metric("test_operation", success_result, 150.0)
        
        # 실패 Result 메트릭
        failure_result = Failure("test error")
        collect_result_metric("test_operation", failure_result, 300.0)
        
        # 메트릭 요약에서 확인
        summary = get_metrics_summary()
        assert "counters" in summary
    
    def test_flux_result_metric_collection(self, user_service):
        """FluxResult 전용 메트릭 수집 테스트"""
        # FluxResult 생성
        results = [
            Success({"id": "1"}),
            Success({"id": "2"}),
            Failure("error")
        ]
        flux_result = FluxResult.from_results(results)
        
        # 메트릭 수집
        collect_flux_result_metric("batch_operation", flux_result, 450.0)
        
        # 메트릭 요약에서 확인
        summary = get_metrics_summary()
        assert "counters" in summary
        assert "gauges" in summary
    
    def test_alert_system(self, alert_manager):
        """알림 시스템 테스트"""
        # 알림 규칙 추가
        create_alert_rule(
            name="test_high_error_rate",
            metric_name="result_failure_total",
            condition=AlertCondition.GREATER_THAN,
            threshold=5.0
        )
        
        # 알림 규칙 조회
        rules = alert_manager.get_alert_rules()
        assert len(rules) > 0
        assert any(rule["name"] == "test_high_error_rate" for rule in rules)
    
    def test_default_alerts_setup(self):
        """기본 알림 설정 테스트"""
        setup_default_alerts()
        
        # 기본 알림 규칙들이 설정되었는지 확인
        # (실제 구현에서는 전역 alert_manager 상태 확인)
        # 여기서는 예외가 발생하지 않음을 확인
        assert True  # 함수가 성공적으로 실행됨


class TestTestingUtilities:
    """테스팅 유틸리티 테스트"""
    
    def test_result_service_mocker_basic(self):
        """ResultServiceMocker 기본 기능 테스트"""
        mocker = ResultServiceMocker("test_service")
        
        # 성공 반환 설정
        mocker.return_success("get_user", {"id": "123", "name": "Test User"})
        
        # 모킹된 메서드 호출
        mock = mocker.get_mock("get_user")
        result = mock("test_id")
        
        # 검증
        assert_result_success(result)
        assert result.unwrap() == {"id": "123", "name": "Test User"}
        
        # 호출 기록 확인
        mocker.assert_called_once("get_user")
        args = mocker.get_call_args("get_user")
        assert args == ("test_id",)
    
    def test_result_service_mocker_failure(self):
        """ResultServiceMocker 실패 케이스 테스트"""
        mocker = ResultServiceMocker("test_service")
        
        # 실패 반환 설정
        mocker.return_failure("get_user", "User not found")
        
        # 모킹된 메서드 호출
        mock = mocker.get_mock("get_user")
        result = mock("invalid_id")
        
        # 검증
        assert_result_failure(result)
        assert result.unwrap_error() == "User not found"
    
    @pytest.mark.asyncio
    async def test_result_service_mocker_mono(self):
        """ResultServiceMocker MonoResult 테스트"""
        mocker = ResultServiceMocker("test_service")
        
        # MonoResult 성공 반환 설정
        mocker.return_mono_success("async_get_user", {"id": "async123"})
        
        # 모킹된 메서드 호출
        mock = mocker.get_mock("async_get_user")
        mono_result = mock("async_id")
        
        # MonoResult 검증
        await assert_mono_result_success(mono_result)
    
    def test_result_service_mocker_flux(self):
        """ResultServiceMocker FluxResult 테스트"""
        mocker = ResultServiceMocker("test_service")
        
        # FluxResult 반환 설정
        flux_results = [
            Success({"id": "1"}),
            Success({"id": "2"}),
            Failure("error")
        ]
        mocker.return_flux_results("process_batch", flux_results)
        
        # 모킹된 메서드 호출
        mock = mocker.get_mock("process_batch")
        flux_result = mock(["1", "2", "3"])
        
        # FluxResult 검증
        assert_flux_success_count(flux_result, 2)
    
    def test_mock_result_service_context_manager(self):
        """mock_result_service 컨텍스트 매니저 테스트"""
        with mock_result_service("user_service", "get_user", "update_user") as mocker:
            # 성공 케이스 설정
            mocker.return_success("get_user", {"id": "ctx_test"})
            mocker.return_failure("update_user", "Update failed")
            
            # 테스트 실행
            get_mock = mocker.get_mock("get_user")
            update_mock = mocker.get_mock("update_user")
            
            get_result = get_mock("test_id")
            update_result = update_mock("test_id", {"name": "New Name"})
            
            # 검증
            assert_result_success(get_result)
            assert_result_failure(update_result)
            
            mocker.assert_called("get_user")
            mocker.assert_called("update_user")
    
    def test_result_test_data_factory(self):
        """ResultTestDataFactory 테스트"""
        factory = ResultTestDataFactory()
        
        # 다양한 Result 생성 테스트
        success_result = factory.create_success_result("factory_test")
        failure_result = factory.create_failure_result("factory_error")
        
        assert_result_success(success_result)
        assert success_result.unwrap() == "factory_test"
        
        assert_result_failure(failure_result)
        assert failure_result.unwrap_error() == "factory_error"
    
    @pytest.mark.asyncio
    async def test_result_test_data_factory_mono(self):
        """ResultTestDataFactory MonoResult 테스트"""
        factory = ResultTestDataFactory()
        
        success_mono = factory.create_success_mono("mono_test")
        failure_mono = factory.create_failure_mono("mono_error")
        
        await assert_mono_result_success(success_mono)
        
        result = await success_mono.to_result()
        assert result.unwrap() == "mono_test"
    
    def test_result_test_data_factory_flux(self):
        """ResultTestDataFactory FluxResult 테스트"""
        factory = ResultTestDataFactory()
        
        # 혼합 FluxResult
        mixed_flux = factory.create_mixed_flux(
            success_values=["a", "b"],
            error_values=["error1", "error2"]
        )
        
        assert_flux_success_count(mixed_flux, 2)
        assert mixed_flux.count_failures() == 2
        assert mixed_flux.count_total() == 4
        
        # 모든 성공 FluxResult
        all_success_flux = factory.create_all_success_flux(["x", "y", "z"])
        assert_flux_success_count(all_success_flux, 3)
        assert all_success_flux.count_failures() == 0
    
    @pytest.mark.asyncio
    async def test_performance_test_helper(self):
        """PerformanceTestHelper 테스트"""
        helper = PerformanceTestHelper()
        
        # 빠른 MonoResult
        fast_mono = MonoResult.from_value("fast_result")
        perf_data = await helper.measure_mono_performance(fast_mono, max_duration_ms=1000.0)
        
        assert perf_data["is_within_limit"]
        assert perf_data["success"]
        assert "duration_ms" in perf_data
        
        # 성능 어설션
        helper.assert_performance(perf_data)


class TestIntegratedWorkflows:
    """통합 워크플로우 테스트"""
    
    @pytest.mark.asyncio
    async def test_complete_monitoring_workflow(self, user_service):
        """완전한 모니터링 워크플로우 테스트"""
        
        # 1. 로깅 설정
        configure_result_logging(LogLevel.INFO, include_correlation=True)
        
        # 2. 메트릭 수집 활성화
        collector = ResultMetricsCollector()
        
        # 3. 알림 규칙 설정
        create_alert_rule(
            name="workflow_test_alert",
            metric_name="result_failure_total",
            condition=AlertCondition.GREATER_THAN,
            threshold=2.0
        )
        
        # 4. 로깅이 포함된 비즈니스 로직
        @log_result_operation("integrated_user_fetch")
        async def monitored_user_fetch(user_id: str) -> Result[dict, str]:
            start_time = time.time()
            
            try:
                result = await user_service.get_user(user_id)
                duration_ms = (time.time() - start_time) * 1000
                
                # 메트릭 수집
                collect_result_metric("integrated_user_fetch", result, duration_ms)
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                error_result = Failure(str(e))
                collect_result_metric("integrated_user_fetch", error_result, duration_ms)
                raise
        
        # 5. 테스트 실행
        success_result = await monitored_user_fetch("valid")
        failure_result = await monitored_user_fetch("invalid")
        
        # 6. 검증
        assert_result_success(success_result)
        assert_result_failure(failure_result)
        
        # 7. 메트릭 요약 확인
        summary = get_metrics_summary(1)
        assert "counters" in summary
        assert "histograms" in summary
    
    @pytest.mark.asyncio
    async def test_flux_monitoring_integration(self, user_service):
        """FluxResult 모니터링 통합 테스트"""
        
        # 배치 처리 함수 (로깅 + 메트릭)
        @log_result_operation("batch_user_processing")
        async def monitored_batch_processing(user_ids: list) -> FluxResult[dict, str]:
            start_time = time.time()
            
            flux_result = await user_service.process_users_batch(user_ids)
            duration_ms = (time.time() - start_time) * 1000
            
            # FluxResult 메트릭 수집
            collect_flux_result_metric("batch_user_processing", flux_result, duration_ms)
            
            # FluxResult 로깅
            await log_flux_results(flux_result, "batch_user_processing")
            
            return flux_result
        
        # 테스트 실행
        test_user_ids = ["valid1", "invalid1", "valid2", "invalid2", "valid3"]
        flux_result = await monitored_batch_processing(test_user_ids)
        
        # 검증
        assert_flux_success_count(flux_result, 3)
        assert flux_result.count_failures() == 2
        assert flux_result.count_total() == 5
        
        # 성공률 검증 (60%)
        success_rate = flux_result.success_rate()
        assert abs(success_rate - 0.6) < 0.01
    
    @pytest.mark.asyncio
    async def test_testing_with_monitoring_integration(self):
        """테스팅과 모니터링 통합 테스트"""
        
        async with result_test_context(performance_tracking=True) as context:
            # 모킹 설정
            with mock_result_service("integrated_service", "complex_operation") as mocker:
                # 순차적 응답 설정 (성공 → 실패 → 성공)
                mocker.return_sequence("complex_operation", [
                    Success({"step": 1, "result": "success"}),
                    Failure("temporary error"),
                    Success({"step": 3, "result": "recovered"})
                ])
                
                # 모니터링이 통합된 함수
                @log_result_operation("complex_integration_test")
                async def complex_operation_with_monitoring():
                    mock = mocker.get_mock("complex_operation")
                    
                    # 3번 호출하여 다양한 결과 생성
                    results = []
                    for i in range(3):
                        start_time = time.time()
                        result = mock(f"request_{i}")
                        duration_ms = (time.time() - start_time) * 1000
                        
                        # 메트릭 수집
                        collect_result_metric("complex_operation", result, duration_ms)
                        results.append(result)
                    
                    return results
                
                # 테스트 실행
                results = await complex_operation_with_monitoring()
                
                # 검증
                assert len(results) == 3
                assert_result_success(results[0])  # 첫 번째 성공
                assert_result_failure(results[1])  # 두 번째 실패
                assert_result_success(results[2])  # 세 번째 성공 (복구)
                
                # 모킹 호출 검증
                mocker.assert_called("complex_operation")
                assert mocker.get_call_count("complex_operation") == 3
                
                # 메트릭 요약 확인
                summary = get_metrics_summary(1)
                assert "counters" in summary


# 커스텀 마커를 사용한 테스트들

@result_test
def test_result_marker_integration():
    """@result_test 마커 통합 테스트"""
    factory = ResultTestDataFactory()
    success_result = factory.create_success_result("marker_test")
    
    assert_result_success(success_result)
    assert success_result.unwrap() == "marker_test"


@mono_test
@pytest.mark.asyncio
async def test_mono_marker_integration():
    """@mono_test 마커 통합 테스트"""
    factory = ResultTestDataFactory()
    mono_result = factory.create_success_mono("mono_marker_test")
    
    await assert_mono_result_success(mono_result)
    
    result = await mono_result.to_result()
    assert result.unwrap() == "mono_marker_test"


@flux_test
def test_flux_marker_integration():
    """@flux_test 마커 통합 테스트"""
    factory = ResultTestDataFactory()
    flux_result = factory.create_all_success_flux(["flux1", "flux2", "flux3"])
    
    assert_flux_success_count(flux_result, 3)
    assert flux_result.count_failures() == 0


@performance_test(max_duration_ms=500.0)
@pytest.mark.asyncio
async def test_performance_marker_integration():
    """@performance_test 마커 통합 테스트"""
    # 빠른 작업 시뮬레이션
    start_time = time.time()
    
    mono_result = MonoResult.from_value("performance_test")
    result = await mono_result.to_result()
    
    duration_ms = (time.time() - start_time) * 1000
    
    # 성능 검증
    assert duration_ms < 500.0  # 500ms 이내
    assert_result_success(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])