"""
ResultAsync 체이닝 버그 수정 테스트
RFS Framework v4.6.3

이 테스트는 ResultAsync가 Python의 awaitable 프로토콜을 제대로 구현하여
체이닝된 메서드들을 await할 수 있는지 검증합니다.
"""

import asyncio
import pytest
from typing import Any

from rfs.core.result import Result, Success, Failure, ResultAsync


class TestResultAsyncChaining:
    """ResultAsync 체이닝 기능 테스트"""

    @pytest.mark.asyncio
    async def test_basic_chaining_with_await(self):
        """기본 체이닝이 await와 함께 작동하는지 테스트"""
        # 문서에서 제시한 실패하던 패턴
        result = await (
            ResultAsync.from_value(10)
            .map_async(lambda x: asyncio.coroutine(lambda: x * 2)())
            .bind_async(lambda x: ResultAsync.from_value(x + 5))
        )
        
        # 결과 검증
        assert result.is_success()
        assert result.unwrap() == 25  # (10 * 2) + 5

    @pytest.mark.asyncio
    async def test_direct_await_on_resultasync(self):
        """ResultAsync 객체를 직접 await할 수 있는지 테스트"""
        # 문서에서 제시한 실패하던 패턴
        result_async = ResultAsync.from_value(5)
        result = await result_async  # 이제 에러가 발생하지 않아야 함
        
        # 결과 검증
        assert isinstance(result, Result)
        assert result.is_success()
        assert result.unwrap() == 5

    @pytest.mark.asyncio
    async def test_complex_chaining_pattern(self):
        """복잡한 체이닝 패턴 테스트"""
        
        async def validate_positive(x: int) -> Result[int, str]:
            """양수 검증 함수"""
            if x > 0:
                return Success(x)
            return Failure("음수는 허용되지 않습니다")
        
        async def double_value(x: int) -> int:
            """값을 두 배로 만드는 비동기 함수"""
            await asyncio.sleep(0.01)  # 비동기 작업 시뮬레이션
            return x * 2
        
        # 체이닝 테스트
        result = await (
            ResultAsync.from_value(10)
            .bind_async(validate_positive)
            .map_async(double_value)
            .map_async(lambda x: x + 100)
        )
        
        assert result.is_success()
        assert result.unwrap() == 120  # (10 * 2) + 100

    @pytest.mark.asyncio
    async def test_chaining_with_failure_propagation(self):
        """체이닝 중 실패가 올바르게 전파되는지 테스트"""
        
        async def fail_if_even(x: int) -> Result[int, str]:
            """짝수면 실패하는 함수"""
            if x % 2 == 0:
                return Failure(f"{x}는 짝수입니다")
            return Success(x)
        
        async def never_called(x: int) -> int:
            """실패 후에는 호출되지 않아야 하는 함수"""
            raise Exception("이 함수는 호출되지 않아야 합니다")
        
        # 실패가 전파되는지 테스트
        result = await (
            ResultAsync.from_value(10)  # 짝수
            .bind_async(fail_if_even)   # 여기서 실패
            .map_async(never_called)     # 호출되지 않아야 함
        )
        
        assert result.is_failure()
        assert result.unwrap_error() == "10는 짝수입니다"

    @pytest.mark.asyncio
    async def test_multiple_await_on_same_resultasync(self):
        """같은 ResultAsync를 여러 번 await해도 캐싱이 작동하는지 테스트"""
        
        call_count = 0
        
        async def expensive_operation() -> Result[int, str]:
            """비용이 큰 연산 시뮬레이션"""
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return Success(42)
        
        result_async = ResultAsync(expensive_operation())
        
        # 여러 번 await
        result1 = await result_async
        result2 = await result_async
        result3 = await result_async
        
        # 모두 같은 결과를 반환해야 함
        assert result1 is result2 is result3
        assert result1.unwrap() == 42
        
        # expensive_operation은 한 번만 호출되어야 함 (캐싱)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_from_value_and_from_error_chaining(self):
        """from_value와 from_error 생성자가 체이닝과 작동하는지 테스트"""
        
        # from_value 체이닝
        success_result = await (
            ResultAsync.from_value("hello")
            .map_async(lambda x: asyncio.coroutine(lambda: x.upper())())
            .map_async(lambda x: asyncio.coroutine(lambda: f"{x}!")())
        )
        
        assert success_result.is_success()
        assert success_result.unwrap() == "HELLO!"
        
        # from_error는 체이닝 중에도 실패 상태를 유지
        error_result = await (
            ResultAsync.from_error("초기 에러")
            .map_async(lambda x: asyncio.coroutine(lambda: x * 2)())
            .bind_async(lambda x: ResultAsync.from_value(x + 5))
        )
        
        assert error_result.is_failure()
        assert error_result.unwrap_error() == "초기 에러"

    @pytest.mark.asyncio
    async def test_exception_handling_in_chaining(self):
        """체이닝 중 예외가 올바르게 처리되는지 테스트"""
        
        async def raise_exception(x: int) -> int:
            """예외를 발생시키는 함수"""
            raise ValueError(f"의도적인 예외: {x}")
        
        result = await (
            ResultAsync.from_value(10)
            .map_async(raise_exception)  # 여기서 예외 발생
            .map_async(lambda x: x * 2)  # 호출되지 않아야 함
        )
        
        assert result.is_failure()
        error = result.unwrap_error()
        assert isinstance(error, ValueError)
        assert str(error) == "의도적인 예외: 10"

    @pytest.mark.asyncio
    async def test_mixed_sync_async_operations(self):
        """동기/비동기 연산이 섞인 체이닝 테스트"""
        
        def sync_double(x: int) -> Result[int, str]:
            """동기 함수"""
            return Success(x * 2)
        
        async def async_add_ten(x: int) -> int:
            """비동기 함수"""
            await asyncio.sleep(0.01)
            return x + 10
        
        # bind와 bind_async, map과 map_async 혼용
        result = await (
            ResultAsync.from_value(5)
            .bind(sync_double)  # 동기 bind
            .map_async(async_add_ten)  # 비동기 map
            .map(lambda x: x * 3)  # 동기 map
        )
        
        assert result.is_success()
        assert result.unwrap() == 60  # ((5 * 2) + 10) * 3

    @pytest.mark.asyncio
    async def test_no_runtime_warnings(self):
        """RuntimeWarning이 발생하지 않는지 테스트"""
        # 이 테스트는 경고 없이 실행되어야 함
        import warnings
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # 문서에서 RuntimeWarning을 발생시켰던 패턴
            result = await (
                ResultAsync.from_value(10)
                .bind_async(lambda x: ResultAsync.from_value(x * 2))
                .map_async(lambda x: asyncio.coroutine(lambda: x + 5)())
            )
            
            # RuntimeWarning이 없어야 함
            runtime_warnings = [
                warning for warning in w 
                if issubclass(warning.category, RuntimeWarning)
            ]
            assert len(runtime_warnings) == 0, f"RuntimeWarning 발생: {runtime_warnings}"
            
            # 결과도 올바르게 계산되어야 함
            assert result.is_success()
            assert result.unwrap() == 25


if __name__ == "__main__":
    # 직접 실행 시 모든 테스트 실행
    asyncio.run(pytest.main([__file__, "-v"]))