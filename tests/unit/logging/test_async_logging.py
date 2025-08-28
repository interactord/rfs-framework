"""
RFS Framework AsyncResult 로깅 단위 테스트

AsyncResult 로깅 시스템의 모든 기능을 포괄적으로 테스트합니다.
"""

import asyncio
import logging
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import pytest

from rfs.async_pipeline import AsyncResult
from rfs.core.result import Success, Failure
from rfs.logging.async_logging import (
    AsyncResultLogger,
    AsyncResultLogContext,
    AsyncResultLogEntry,
    LogLevel,
    get_async_result_logger,
    configure_async_result_logging,
    log_async_chain,
    create_logged_pipeline,
    async_result_log_context,
    SENSITIVE_KEYS
)


class TestAsyncResultLogEntry:
    """AsyncResultLogEntry 클래스 테스트"""
    
    def test_log_entry_creation(self):
        """로그 엔트리 생성 테스트"""
        # Given & When
        entry = AsyncResultLogEntry(
            timestamp=1234567890.0,
            operation_name="test_operation",
            operation_id="op_123",
            level=LogLevel.INFO,
            message="Test message",
            data={"key": "value"},
            duration=1.5,
            chain_depth=2
        )
        
        # Then
        assert entry.operation_name == "test_operation"
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"
        assert entry.data == {"key": "value"}
        assert entry.duration == 1.5
        assert entry.chain_depth == 2
    
    def test_log_entry_to_dict(self):
        """로그 엔트리 딕셔너리 변환 테스트"""
        # Given
        entry = AsyncResultLogEntry(
            timestamp=1234567890.0,
            operation_name="test_op",
            operation_id="op_123",
            level=LogLevel.WARNING,
            message="Warning message"
        )
        
        # When
        entry_dict = entry.to_dict()
        
        # Then
        assert entry_dict["operation_name"] == "test_op"
        assert entry_dict["level"] == LogLevel.WARNING
        assert entry_dict["message"] == "Warning message"
        assert "timestamp" in entry_dict
    
    def test_log_entry_to_json(self):
        """로그 엔트리 JSON 변환 테스트"""
        # Given
        entry = AsyncResultLogEntry(
            timestamp=1234567890.0,
            operation_name="json_test",
            operation_id="op_json",
            level=LogLevel.ERROR,
            message="Error message"
        )
        
        # When
        json_str = entry.to_json()
        
        # Then
        assert '"operation_name":"json_test"' in json_str
        assert '"level":"ERROR"' in json_str
        assert '"message":"Error message"' in json_str


class TestAsyncResultLogger:
    """AsyncResultLogger 클래스 테스트"""
    
    @pytest.fixture
    def mock_logger(self):
        """모킹된 Python 로거"""
        return Mock(spec=logging.Logger)
    
    @pytest.fixture
    def async_result_logger(self, mock_logger):
        """테스트용 AsyncResultLogger"""
        return AsyncResultLogger(
            logger=mock_logger,
            enable_sensitive_masking=True,
            enable_performance_tracking=True
        )
    
    def test_logger_initialization(self, mock_logger):
        """로거 초기화 테스트"""
        # Given & When
        logger = AsyncResultLogger(
            logger=mock_logger,
            enable_sensitive_masking=False,
            max_data_length=500,
            sensitive_keys={"custom_secret"}
        )
        
        # Then
        assert logger.logger == mock_logger
        assert logger.enable_sensitive_masking is False
        assert logger.max_data_length == 500
        assert "custom_secret" in logger.sensitive_keys
    
    @pytest.mark.asyncio
    async def test_log_chain_success(self, async_result_logger, mock_logger):
        """성공하는 AsyncResult 체인 로깅 테스트"""
        # Given
        test_data = {"user_id": 123}
        async_result = AsyncResult.from_value(test_data)
        
        # When
        logged_result = async_result_logger.log_chain("test_operation")(async_result)
        result = await logged_result.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == test_data
        
        # 로깅 호출 확인
        assert mock_logger.log.call_count >= 2  # 시작 + 성공 로그
        
        # 시작 로그 확인
        start_call_args = mock_logger.log.call_args_list[0]
        assert "🚀 test_operation: 시작" in start_call_args[0][1]
        
        # 성공 로그 확인  
        success_call_args = mock_logger.log.call_args_list[1]
        assert "✅ test_operation: 성공" in success_call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_log_chain_failure(self, async_result_logger, mock_logger):
        """실패하는 AsyncResult 체인 로깅 테스트"""
        # Given
        error_message = "Test error"
        async_result = AsyncResult.from_error(error_message)
        
        # When
        logged_result = async_result_logger.log_chain("test_failure")(async_result)
        result = await logged_result.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == error_message
        
        # 실패 로그 확인
        failure_calls = [
            call for call in mock_logger.log.call_args_list
            if "❌ test_failure: 실패" in call[0][1]
        ]
        assert len(failure_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_log_chain_exception_handling(self, async_result_logger, mock_logger):
        """예상치 못한 예외 처리 테스트"""
        # Given
        async def failing_operation():
            raise RuntimeError("Unexpected error")
        
        async_result = AsyncResult.from_async(failing_operation)
        
        # When
        logged_result = async_result_logger.log_chain("test_exception")(async_result)
        result = await logged_result.to_result()
        
        # Then
        assert result.is_failure()
        assert isinstance(result.unwrap_error(), RuntimeError)
        
        # 예외 로그 확인
        exception_calls = [
            call for call in mock_logger.log.call_args_list
            if "💥 test_exception: 예상치 못한 예외 발생" in call[0][1]
        ]
        assert len(exception_calls) >= 1
    
    def test_format_value_simple_data(self, async_result_logger):
        """단순 데이터 포맷팅 테스트"""
        test_cases = [
            (None, "None"),
            ("test", "test"),
            (123, "123"),
            (True, "True"),
        ]
        
        for input_value, expected in test_cases:
            result = async_result_logger._format_value(input_value)
            assert result == expected
    
    def test_format_value_long_string(self, async_result_logger):
        """긴 문자열 포맷팅 테스트"""
        # Given
        long_string = "a" * 2000  # max_data_length(1000)보다 긴 문자열
        
        # When
        result = async_result_logger._format_value(long_string)
        
        # Then
        assert len(result) < len(long_string)
        assert "..." in result
        assert "길이: 2000" in result
    
    def test_format_dict_with_sensitive_keys(self, async_result_logger):
        """민감한 키가 포함된 딕셔너리 포맷팅 테스트"""
        # Given
        sensitive_data = {
            "username": "testuser",
            "password": "secret123",
            "api_key": "abc123def456",
            "email": "test@example.com"
        }
        
        # When
        result = async_result_logger._format_dict(sensitive_data)
        
        # Then
        assert "testuser" in result
        assert "test@example.com" in result
        assert "***MASKED***" in result
        assert "secret123" not in result
        assert "abc123def456" not in result
    
    def test_format_dict_without_masking(self, mock_logger):
        """마스킹 비활성화된 딕셔너리 포맷팅 테스트"""
        # Given
        logger = AsyncResultLogger(
            logger=mock_logger,
            enable_sensitive_masking=False
        )
        data = {"password": "secret123", "username": "testuser"}
        
        # When
        result = logger._format_dict(data)
        
        # Then
        assert "secret123" in result  # 마스킹되지 않아야 함
        assert "testuser" in result
    
    def test_format_collection(self, async_result_logger):
        """컬렉션 포맷팅 테스트"""
        # Given
        small_list = [1, 2, 3]
        large_list = list(range(20))
        
        # When
        small_result = async_result_logger._format_collection(small_list)
        large_result = async_result_logger._format_collection(large_list)
        
        # Then
        assert "[1, 2, 3]" in small_result
        assert "... (총 20개 항목)" in large_result
    
    def test_performance_metrics_recording(self, async_result_logger):
        """성능 메트릭 기록 테스트"""
        # Given
        operation_name = "test_performance"
        duration = 1.5
        
        # When
        async_result_logger._record_performance_metric(operation_name, duration)
        
        # Then
        assert operation_name in async_result_logger._performance_metrics
        assert duration in async_result_logger._performance_metrics[operation_name]
    
    def test_get_performance_summary(self, async_result_logger):
        """성능 요약 정보 테스트"""
        # Given
        operation_name = "test_op"
        durations = [1.0, 1.5, 2.0, 2.5, 3.0]
        
        for duration in durations:
            async_result_logger._record_performance_metric(operation_name, duration)
        
        # When
        summary = async_result_logger.get_performance_summary(operation_name)
        
        # Then
        assert summary["count"] == 5
        assert summary["min"] == 1.0
        assert summary["max"] == 3.0
        assert summary["avg"] == 2.0
        assert summary["total_time"] == 10.0
    
    def test_get_performance_summary_all_operations(self, async_result_logger):
        """전체 연산 성능 요약 테스트"""
        # Given
        async_result_logger._record_performance_metric("op1", 1.0)
        async_result_logger._record_performance_metric("op2", 2.0)
        
        # When
        summary = async_result_logger.get_performance_summary()
        
        # Then
        assert "op1" in summary
        assert "op2" in summary
        assert summary["op1"]["avg"] == 1.0
        assert summary["op2"]["avg"] == 2.0
    
    def test_get_performance_summary_missing_operation(self, async_result_logger):
        """존재하지 않는 연산 성능 요약 테스트"""
        # Given & When
        summary = async_result_logger.get_performance_summary("nonexistent")
        
        # Then
        assert "error" in summary
        assert "연산 'nonexistent'에 대한 메트릭이 없습니다" in summary["error"]


class TestGlobalLoggerManagement:
    """전역 로거 관리 테스트"""
    
    def test_get_async_result_logger_singleton(self):
        """전역 로거 싱글톤 패턴 테스트"""
        # Given & When
        logger1 = get_async_result_logger("test_logger")
        logger2 = get_async_result_logger("test_logger")
        
        # Then
        assert logger1 is logger2  # 동일한 인스턴스여야 함
    
    def test_get_async_result_logger_different_names(self):
        """다른 이름의 로거들 테스트"""
        # Given & When
        logger1 = get_async_result_logger("logger1")
        logger2 = get_async_result_logger("logger2")
        
        # Then
        assert logger1 is not logger2  # 다른 인스턴스여야 함
    
    @patch('rfs.logging.async_logging.logging.getLogger')
    def test_configure_async_result_logging(self, mock_get_logger):
        """AsyncResult 로깅 설정 테스트"""
        # Given
        mock_python_logger = Mock(spec=logging.Logger)
        mock_python_logger.handlers = []
        mock_get_logger.return_value = mock_python_logger
        
        # When
        async_logger = configure_async_result_logging(
            logger_name="test_config",
            log_level="DEBUG",
            enable_json_logging=False
        )
        
        # Then
        assert isinstance(async_logger, AsyncResultLogger)
        mock_python_logger.setLevel.assert_called_with(logging.DEBUG)


class TestLogAsyncChain:
    """log_async_chain 데코레이터 테스트"""
    
    @pytest.mark.asyncio
    async def test_curried_log_async_chain(self):
        """커링된 log_async_chain 사용 테스트"""
        with patch('rfs.logging.async_logging.get_async_result_logger') as mock_get_logger:
            # Given
            mock_logger = Mock(spec=AsyncResultLogger)
            mock_logger.log_chain.return_value = lambda ar: ar  # pass-through
            mock_get_logger.return_value = mock_logger
            
            # When
            log_decorator = log_async_chain("test_curried")
            async_result = AsyncResult.from_value("test")
            logged_result = log_decorator(async_result)
            result = await logged_result.to_result()
            
            # Then
            assert result.is_success()
            mock_logger.log_chain.assert_called_once_with("test_curried", LogLevel.INFO)


class TestCreateLoggedPipeline:
    """create_logged_pipeline 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_logged_pipeline_creation(self):
        """로깅된 파이프라인 생성 테스트"""
        with patch('rfs.logging.async_logging.get_async_result_logger') as mock_get_logger:
            # Given
            mock_logger = Mock(spec=AsyncResultLogger)
            mock_logger.log_chain.return_value = lambda ar: ar  # pass-through
            mock_get_logger.return_value = mock_logger
            
            def operation1(x):
                return x * 2
            
            def operation2(x):
                return x + 10
            
            # When
            pipeline = create_logged_pipeline(
                operation1, operation2, 
                pipeline_name="test_pipeline"
            )
            
            # Then
            assert callable(pipeline)
            # 각 연산에 대해 로깅이 설정되었는지 확인
            assert mock_logger.log_chain.call_count == 2


class TestAsyncResultLogContext:
    """async_result_log_context 컨텍스트 매니저 테스트"""
    
    @pytest.mark.asyncio
    async def test_log_context_manager(self):
        """로그 컨텍스트 매니저 테스트"""
        with patch('rfs.logging.async_logging.get_async_result_logger') as mock_get_logger:
            # Given
            mock_logger = Mock(spec=AsyncResultLogger)
            mock_python_logger = Mock(spec=logging.Logger)
            mock_logger.logger = mock_python_logger
            mock_get_logger.return_value = mock_logger
            
            # When
            async with async_result_log_context(
                "test_context", 
                user_id="123"
            ) as operation_id:
                # Then
                assert operation_id is not None
                assert "test_context" in operation_id
            
            # 시작과 종료 로그 확인
            assert mock_python_logger.info.call_count >= 2


class TestSensitiveDataMasking:
    """민감한 데이터 마스킹 테스트"""
    
    @pytest.fixture
    def masking_logger(self):
        """마스킹이 활성화된 로거"""
        mock_logger = Mock(spec=logging.Logger)
        return AsyncResultLogger(
            logger=mock_logger,
            enable_sensitive_masking=True,
            sensitive_keys=SENSITIVE_KEYS | {"custom_secret"}
        )
    
    def test_sensitive_keys_masking(self, masking_logger):
        """기본 민감한 키들 마스킹 테스트"""
        sensitive_data = {
            "password": "secret123",
            "api_key": "abc123",
            "token": "jwt_token",
            "credit_card": "1234-5678-9012-3456",
            "normal_field": "visible_value"
        }
        
        # When
        result = masking_logger._format_dict(sensitive_data)
        
        # Then
        assert "***MASKED***" in result
        assert "visible_value" in result
        assert "secret123" not in result
        assert "abc123" not in result
        assert "jwt_token" not in result
        assert "1234-5678-9012-3456" not in result
    
    def test_custom_sensitive_key(self, masking_logger):
        """커스텀 민감한 키 마스킹 테스트"""
        # Given
        data = {
            "custom_secret": "should_be_masked",
            "normal_data": "should_be_visible"
        }
        
        # When
        result = masking_logger._format_dict(data)
        
        # Then
        assert "***MASKED***" in result
        assert "should_be_visible" in result
        assert "should_be_masked" not in result
    
    def test_nested_dict_masking(self, masking_logger):
        """중첩된 딕셔너리 마스킹 테스트"""
        # Given
        nested_data = {
            "user": {
                "name": "John Doe",
                "credentials": {
                    "password": "secret",
                    "api_key": "key123"
                }
            },
            "public_data": "visible"
        }
        
        # When
        result = masking_logger._format_dict(nested_data)
        
        # Then
        assert "John Doe" in result
        assert "visible" in result
        assert "***MASKED***" in result
        assert "secret" not in result
        assert "key123" not in result


class TestPerformanceTracking:
    """성능 추적 테스트"""
    
    @pytest.mark.asyncio
    async def test_performance_tracking_enabled(self):
        """성능 추적 활성화 테스트"""
        # Given
        mock_logger = Mock(spec=logging.Logger)
        async_logger = AsyncResultLogger(
            logger=mock_logger,
            enable_performance_tracking=True
        )
        
        async def slow_operation():
            await asyncio.sleep(0.01)
            return "result"
        
        async_result = AsyncResult.from_async(slow_operation)
        
        # When
        logged_result = async_logger.log_chain("perf_test")(async_result)
        await logged_result.to_result()
        
        # Then
        assert "perf_test" in async_logger._performance_metrics
        assert len(async_logger._performance_metrics["perf_test"]) == 1
        assert async_logger._performance_metrics["perf_test"][0] > 0
    
    @pytest.mark.asyncio
    async def test_performance_tracking_disabled(self):
        """성능 추적 비활성화 테스트"""
        # Given
        mock_logger = Mock(spec=logging.Logger)
        async_logger = AsyncResultLogger(
            logger=mock_logger,
            enable_performance_tracking=False
        )
        
        async_result = AsyncResult.from_value("result")
        
        # When
        logged_result = async_logger.log_chain("no_perf_test")(async_result)
        await logged_result.to_result()
        
        # Then
        assert "no_perf_test" not in async_logger._performance_metrics
    
    def test_performance_metrics_memory_management(self):
        """성능 메트릭 메모리 관리 테스트"""
        # Given
        mock_logger = Mock(spec=logging.Logger)
        async_logger = AsyncResultLogger(logger=mock_logger)
        operation_name = "memory_test"
        
        # When: 100개 초과의 메트릭 추가
        for i in range(150):
            async_logger._record_performance_metric(operation_name, float(i))
        
        # Then: 최근 100개만 유지되어야 함
        metrics = async_logger._performance_metrics[operation_name]
        assert len(metrics) == 100
        assert metrics[0] == 50.0  # 처음 50개는 제거되었어야 함
        assert metrics[-1] == 149.0


class TestEdgeCases:
    """엣지 케이스 테스트"""
    
    @pytest.mark.asyncio
    async def test_empty_operation_name(self):
        """빈 연산 이름 테스트"""
        # Given
        mock_logger = Mock(spec=logging.Logger)
        async_logger = AsyncResultLogger(logger=mock_logger)
        async_result = AsyncResult.from_value("test")
        
        # When
        logged_result = async_logger.log_chain("")(async_result)
        result = await logged_result.to_result()
        
        # Then
        assert result.is_success()
        # 로깅이 호출되었는지 확인
        assert mock_logger.log.call_count > 0
    
    @pytest.mark.asyncio
    async def test_very_long_data(self):
        """매우 긴 데이터 처리 테스트"""
        # Given
        mock_logger = Mock(spec=logging.Logger)
        async_logger = AsyncResultLogger(
            logger=mock_logger,
            max_data_length=100  # 짧은 길이로 설정
        )
        
        long_data = "a" * 10000
        async_result = AsyncResult.from_value(long_data)
        
        # When
        logged_result = async_logger.log_chain("long_data_test")(async_result)
        await logged_result.to_result()
        
        # Then: 로깅은 성공해야 하고, 데이터는 잘려야 함
        assert mock_logger.log.call_count > 0
        
        # 로그 메시지에서 데이터 길이 확인
        log_calls = mock_logger.log.call_args_list
        success_call = next(call for call in log_calls if "성공" in call[0][1])
        extra_data = success_call[1]["extra"]["async_result_data"]
        assert len(extra_data) <= 100 + 50  # 약간의 마진 포함
    
    @pytest.mark.asyncio
    async def test_circular_reference_data(self):
        """순환 참조 데이터 처리 테스트"""
        # Given
        mock_logger = Mock(spec=logging.Logger)
        async_logger = AsyncResultLogger(logger=mock_logger)
        
        # 순환 참조 생성
        data = {"key": "value"}
        data["self"] = data
        
        async_result = AsyncResult.from_value(data)
        
        # When & Then: 예외가 발생하지 않아야 함
        logged_result = async_logger.log_chain("circular_test")(async_result)
        result = await logged_result.to_result()
        
        assert result.is_success()
    
    def test_format_value_with_exception(self):
        """값 포맷팅 중 예외 처리 테스트"""
        # Given
        mock_logger = Mock(spec=logging.Logger)
        async_logger = AsyncResultLogger(logger=mock_logger)
        
        # str() 메서드에서 예외를 발생시키는 객체
        class BadObject:
            def __str__(self):
                raise Exception("Cannot convert to string")
        
        bad_obj = BadObject()
        
        # When
        result = async_logger._format_value(bad_obj)
        
        # Then: 예외 처리되어 에러 메시지 반환
        assert "<포맷팅 에러:" in result


# === 통합 테스트 ===

class TestIntegration:
    """통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_full_logging_workflow(self):
        """전체 로깅 워크플로우 테스트"""
        # Given: 실제 로거 사용
        import logging
        
        # 메모리 핸들러로 로그 캡처
        from logging.handlers import MemoryHandler
        target_handler = logging.StreamHandler()
        memory_handler = MemoryHandler(capacity=100, target=target_handler)
        
        python_logger = logging.getLogger("test_workflow")
        python_logger.addHandler(memory_handler)
        python_logger.setLevel(logging.INFO)
        
        async_logger = AsyncResultLogger(
            logger=python_logger,
            enable_sensitive_masking=True,
            enable_performance_tracking=True
        )
        
        # When: 복잡한 연산 체인 실행
        async def fetch_user_data():
            await asyncio.sleep(0.01)
            return {
                "user_id": 123,
                "name": "Test User",
                "password": "secret123"  # 마스킹되어야 함
            }
        
        async def validate_user(user_data):
            await asyncio.sleep(0.01)
            if user_data.get("user_id"):
                return user_data
            else:
                raise ValueError("Invalid user")
        
        # 체인 실행
        result = await (
            async_logger.log_chain("fetch_user")(
                AsyncResult.from_async(fetch_user_data)
            ).bind_async(lambda user: 
                async_logger.log_chain("validate_user")(
                    AsyncResult.from_async(lambda: validate_user(user))
                )
            )
        )
        
        # Then
        final_result = await result.to_result()
        assert final_result.is_success()
        
        # 성능 메트릭 확인
        fetch_metrics = async_logger.get_performance_summary("fetch_user")
        validate_metrics = async_logger.get_performance_summary("validate_user")
        
        assert fetch_metrics["count"] == 1
        assert validate_metrics["count"] == 1
        assert fetch_metrics["avg"] > 0
        assert validate_metrics["avg"] > 0


# === 픽스처 및 헬퍼 ===

@pytest.fixture
def sample_sensitive_data():
    """테스트용 민감한 데이터"""
    return {
        "user_id": 123,
        "username": "testuser",
        "password": "secret123",
        "api_key": "abc123def456",
        "email": "test@example.com",
        "profile": {
            "name": "Test User",
            "secret_key": "inner_secret"
        }
    }


@pytest.fixture
def mock_performance_data():
    """테스트용 성능 데이터"""
    return {
        "operation_durations": [0.1, 0.15, 0.12, 0.18, 0.13, 0.16, 0.14],
        "expected_avg": 0.14,
        "expected_min": 0.1,
        "expected_max": 0.18
    }


# === 실행 시 검증 ===

if __name__ == "__main__":
    print("✅ AsyncResult 로깅 테스트 모듈 로드 완료")
    print("pytest tests/unit/logging/test_async_logging.py 실행하여 테스트")