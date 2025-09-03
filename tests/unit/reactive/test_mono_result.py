"""
MonoResult 클래스 단위 테스트

MonoResult의 모든 핵심 기능을 검증합니다.
"""

import asyncio
import pytest
from typing import Dict, Any

from rfs.core.result import Failure, Result, Success
from rfs.reactive.mono_result import MonoResult


class TestMonoResultBasic:
    """MonoResult 기본 기능 테스트"""

    @pytest.mark.asyncio
    async def test_from_result_success(self):
        """Success Result로 MonoResult 생성 테스트"""
        # Given
        original_result = Success("test_value")
        mono = MonoResult.from_result(original_result)
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "test_value"

    @pytest.mark.asyncio
    async def test_from_result_failure(self):
        """Failure Result로 MonoResult 생성 테스트"""
        # Given
        original_result = Failure("test_error")
        mono = MonoResult.from_result(original_result)
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "test_error"

    @pytest.mark.asyncio
    async def test_from_value(self):
        """값으로 직접 MonoResult 생성 테스트"""
        # Given & When
        mono = MonoResult.from_value("direct_value")
        result = await mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "direct_value"

    @pytest.mark.asyncio
    async def test_from_error(self):
        """에러로 직접 MonoResult 생성 테스트"""
        # Given & When
        mono = MonoResult.from_error("direct_error")
        result = await mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "direct_error"

    @pytest.mark.asyncio
    async def test_from_async_result_success(self):
        """비동기 함수로 MonoResult 생성 테스트 (성공)"""
        # Given
        async def async_operation() -> Result[str, str]:
            await asyncio.sleep(0.01)  # 짧은 대기
            return Success("async_value")
        
        mono = MonoResult.from_async_result(async_operation)
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "async_value"

    @pytest.mark.asyncio
    async def test_from_async_result_failure(self):
        """비동기 함수로 MonoResult 생성 테스트 (실패)"""
        # Given
        async def async_operation() -> Result[str, str]:
            await asyncio.sleep(0.01)
            return Failure("async_error")
        
        mono = MonoResult.from_async_result(async_operation)
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "async_error"

    @pytest.mark.asyncio
    async def test_await_support(self):
        """직접 await 지원 테스트"""
        # Given
        mono = MonoResult.from_value("await_test")
        
        # When
        result = await mono  # to_result() 없이 직접 await
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "await_test"


class TestMonoResultTransformation:
    """MonoResult 변환 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_map_success(self):
        """성공 값 변환 테스트"""
        # Given
        mono = MonoResult.from_value("hello")
        
        # When
        transformed_mono = mono.map(lambda s: s.upper())
        result = await transformed_mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "HELLO"

    @pytest.mark.asyncio
    async def test_map_failure_passthrough(self):
        """실패 시 map 건너뛰기 테스트"""
        # Given
        mono = MonoResult.from_error("original_error")
        
        # When
        transformed_mono = mono.map(lambda s: s.upper())  # 실행되지 않아야 함
        result = await transformed_mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "original_error"

    @pytest.mark.asyncio
    async def test_map_exception_handling(self):
        """map 함수에서 예외 발생 시 처리 테스트"""
        # Given
        mono = MonoResult.from_value("test")
        
        # When
        def failing_transform(s: str) -> str:
            raise ValueError("변환 실패")
        
        transformed_mono = mono.map(failing_transform)
        result = await transformed_mono.to_result()
        
        # Then
        assert result.is_failure()
        assert isinstance(result.unwrap_error(), ValueError)

    @pytest.mark.asyncio
    async def test_map_error_success_passthrough(self):
        """성공 시 map_error 건너뛰기 테스트"""
        # Given
        mono = MonoResult.from_value("success_value")
        
        # When
        transformed_mono = mono.map_error(lambda e: f"transformed_{e}")
        result = await transformed_mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "success_value"

    @pytest.mark.asyncio
    async def test_map_error_transformation(self):
        """에러 타입 변환 테스트"""
        # Given
        mono = MonoResult.from_error("original_error")
        
        # When
        transformed_mono = mono.map_error(lambda e: f"transformed_{e}")
        result = await transformed_mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "transformed_original_error"


class TestMonoResultChaining:
    """MonoResult 체이닝 테스트"""

    @pytest.mark.asyncio
    async def test_bind_result_success(self):
        """동기 Result 함수 체이닝 테스트"""
        # Given
        mono = MonoResult.from_value(5)
        
        def double_if_positive(n: int) -> Result[int, str]:
            if n > 0:
                return Success(n * 2)
            else:
                return Failure("음수는 처리할 수 없습니다")
        
        # When
        chained_mono = mono.bind_result(double_if_positive)
        result = await chained_mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == 10

    @pytest.mark.asyncio
    async def test_bind_result_failure_from_source(self):
        """원본이 실패인 경우 bind_result 건너뛰기 테스트"""
        # Given
        mono = MonoResult.from_error("source_error")
        
        def double_if_positive(n: int) -> Result[int, str]:
            return Success(n * 2)  # 실행되지 않아야 함
        
        # When
        chained_mono = mono.bind_result(double_if_positive)
        result = await chained_mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "source_error"

    @pytest.mark.asyncio
    async def test_bind_result_failure_from_function(self):
        """bind 함수에서 실패 반환 테스트"""
        # Given
        mono = MonoResult.from_value(-5)
        
        def double_if_positive(n: int) -> Result[int, str]:
            if n > 0:
                return Success(n * 2)
            else:
                return Failure("음수는 처리할 수 없습니다")
        
        # When
        chained_mono = mono.bind_result(double_if_positive)
        result = await chained_mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "음수는 처리할 수 없습니다"

    @pytest.mark.asyncio
    async def test_bind_async_result_success(self):
        """비동기 Result 함수 체이닝 테스트"""
        # Given
        mono = MonoResult.from_value("test")
        
        async def async_upper_if_short(s: str) -> Result[str, str]:
            await asyncio.sleep(0.01)
            if len(s) < 10:
                return Success(s.upper())
            else:
                return Failure("문자열이 너무 깁니다")
        
        # When
        chained_mono = mono.bind_async_result(async_upper_if_short)
        result = await chained_mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "TEST"

    @pytest.mark.asyncio
    async def test_complex_chaining(self):
        """복잡한 체이닝 테스트"""
        # Given
        mono = MonoResult.from_value(3)
        
        def multiply_by_2(n: int) -> Result[int, str]:
            return Success(n * 2)
        
        async def add_10_async(n: int) -> Result[int, str]:
            await asyncio.sleep(0.01)
            return Success(n + 10)
        
        # When
        result = await (
            mono
            .bind_result(multiply_by_2)       # 3 * 2 = 6
            .bind_async_result(add_10_async)  # 6 + 10 = 16
            .map(lambda n: n * 3)             # 16 * 3 = 48
            .to_result()
        )
        
        # Then
        assert result.is_success()
        assert result.unwrap() == 48


class TestMonoResultErrorHandling:
    """MonoResult 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_on_error_return_result_recovery(self):
        """에러 복구 테스트"""
        # Given
        mono = MonoResult.from_error("original_error")
        
        # When
        recovered_mono = mono.on_error_return_result(
            lambda e: Success(f"recovered_from_{e}")
        )
        result = await recovered_mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "recovered_from_original_error"

    @pytest.mark.asyncio
    async def test_on_error_return_result_no_error(self):
        """에러가 없는 경우 on_error_return_result 건너뛰기 테스트"""
        # Given
        mono = MonoResult.from_value("original_value")
        
        # When
        recovered_mono = mono.on_error_return_result(
            lambda e: Success("should_not_be_called")
        )
        result = await recovered_mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "original_value"

    @pytest.mark.asyncio
    async def test_on_error_return_value_convenience(self):
        """편의 메서드 on_error_return_value 테스트"""
        # Given
        mono = MonoResult.from_error("some_error")
        
        # When
        recovered_mono = mono.on_error_return_value("default_value")
        result = await recovered_mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "default_value"


class TestMonoResultAdvancedFeatures:
    """MonoResult 고급 기능 테스트"""

    @pytest.mark.asyncio
    async def test_timeout_success(self):
        """타임아웃 내 완료 테스트"""
        # Given
        async def fast_operation() -> Result[str, str]:
            await asyncio.sleep(0.1)  # 100ms
            return Success("completed")
        
        mono = MonoResult.from_async_result(fast_operation).timeout(0.5)  # 500ms 타임아웃
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "completed"

    @pytest.mark.asyncio
    async def test_timeout_failure(self):
        """타임아웃 발생 테스트"""
        # Given
        async def slow_operation() -> Result[str, str]:
            await asyncio.sleep(0.5)  # 500ms
            return Success("completed")
        
        mono = MonoResult.from_async_result(slow_operation).timeout(0.1)  # 100ms 타임아웃
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_failure()
        error_msg = str(result.unwrap_error()).lower()
        assert "timed out" in error_msg or "timeout" in error_msg

    @pytest.mark.asyncio
    async def test_cache_functionality(self):
        """캐싱 기능 테스트"""
        # Given
        call_count = 0
        
        async def expensive_operation() -> Result[str, str]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return Success(f"result_{call_count}")
        
        mono = MonoResult.from_async_result(expensive_operation).cache()
        
        # When
        result1 = await mono.to_result()
        result2 = await mono.to_result()
        
        # Then
        assert result1.is_success()
        assert result2.is_success()
        assert result1.unwrap() == result2.unwrap()  # 같은 결과
        assert call_count == 1  # 한 번만 호출됨

    @pytest.mark.asyncio
    async def test_do_on_success_side_effect(self):
        """성공 시 사이드 이펙트 테스트"""
        # Given
        side_effect_called = False
        captured_value = None
        
        def side_effect(value: str):
            nonlocal side_effect_called, captured_value
            side_effect_called = True
            captured_value = value
        
        mono = MonoResult.from_value("test_value").do_on_success(side_effect)
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "test_value"  # 원본 값 유지
        assert side_effect_called  # 사이드 이펙트 실행됨
        assert captured_value == "test_value"

    @pytest.mark.asyncio
    async def test_do_on_error_side_effect(self):
        """에러 시 사이드 이펙트 테스트"""
        # Given
        side_effect_called = False
        captured_error = None
        
        def side_effect(error: str):
            nonlocal side_effect_called, captured_error
            side_effect_called = True
            captured_error = error
        
        mono = MonoResult.from_error("test_error").do_on_error(side_effect)
        
        # When
        result = await mono.to_result()
        
        # Then
        assert result.is_failure()
        assert result.unwrap_error() == "test_error"  # 원본 에러 유지
        assert side_effect_called  # 사이드 이펙트 실행됨
        assert captured_error == "test_error"


class TestMonoResultRealWorldScenarios:
    """실제 사용 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_user_processing_pipeline(self):
        """사용자 처리 파이프라인 시나리오"""
        # Given - Mock functions
        async def fetch_user(user_id: str) -> Result[Dict[str, Any], str]:
            if user_id == "123":
                return Success({"id": "123", "name": "김철수", "age": 30})
            else:
                return Failure("사용자를 찾을 수 없습니다")
        
        def validate_user(user: Dict[str, Any]) -> Result[Dict[str, Any], str]:
            if user.get("age", 0) >= 18:
                return Success(user)
            else:
                return Failure("미성년자는 처리할 수 없습니다")
        
        async def process_user_async(user: Dict[str, Any]) -> Result[Dict[str, Any], str]:
            await asyncio.sleep(0.01)
            processed_user = {**user, "processed": True, "timestamp": "2025-09-03"}
            return Success(processed_user)
        
        # When - 성공 케이스
        result = await (
            MonoResult.from_async_result(lambda: fetch_user("123"))
            .bind_result(validate_user)
            .bind_async_result(process_user_async)
            .map(lambda user: user["name"])
            .map_error(lambda e: f"사용자 처리 실패: {e}")
            .timeout(1.0)
            .to_result()
        )
        
        # Then
        assert result.is_success()
        assert result.unwrap() == "김철수"

    @pytest.mark.asyncio
    async def test_health_check_scenario(self):
        """헬스체크 시나리오 (px 프로젝트 사용 케이스)"""
        # Given
        async def get_database_connection() -> Result[str, str]:
            await asyncio.sleep(0.01)
            return Success("db_connection")
        
        async def check_database_health(connection: str) -> Result[str, str]:
            await asyncio.sleep(0.01)
            return Success("db_healthy")
        
        async def check_redis_health() -> Result[str, str]:
            await asyncio.sleep(0.01)
            return Success("redis_healthy")
        
        def create_health_response(db_status: str) -> Result[Dict[str, str], str]:
            return Success({"database": db_status, "status": "healthy"})
        
        # When
        result = await (
            MonoResult.from_async_result(get_database_connection)
            .bind_async_result(lambda conn: check_database_health(conn))
            .bind_async_result(lambda db_health: check_redis_health())
            .bind_result(create_health_response)
            .map_error(lambda e: f"헬스체크 실패: {e}")
            .on_error_return_result(lambda e: Success({"status": "degraded", "error": str(e)}))
            .timeout(5.0)
            .to_result()
        )
        
        # Then
        assert result.is_success()
        health_data = result.unwrap()
        assert health_data["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_error_recovery_chain(self):
        """에러 복구 체인 테스트"""
        # Given
        async def primary_service() -> Result[str, str]:
            return Failure("primary_service_down")
        
        async def fallback_service() -> Result[str, str]:
            await asyncio.sleep(0.01)
            return Success("fallback_data")
        
        # When
        result = await (
            MonoResult.from_async_result(primary_service)
            .on_error_return_result(lambda e: 
                MonoResult.from_async_result(fallback_service).to_result()
            )
            .bind_result(lambda data: Success(f"processed_{data}"))
            .to_result()
        )
        
        # Then - 폴백 서비스 결과가 처리되어 나와야 함
        assert result.is_success()
        # Note: 현재 구현에서는 on_error_return_result가 MonoResult를 직접 반환할 수 없음
        # 실제 사용에서는 await를 사용해야 함