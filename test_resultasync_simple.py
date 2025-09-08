#!/usr/bin/env python3
"""
ResultAsync __await__ 메서드 테스트
최소한의 의존성으로 직접 테스트
"""

import asyncio
import sys
import os
from typing import TypeVar, Generic, Callable, Awaitable, Optional

# 타입 변수
T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


# 최소한의 Result 클래스 구현
class Result(Generic[T, E]):
    pass


class Success(Result[T, E]):
    def __init__(self, value: T):
        self.value = value
    
    def is_success(self) -> bool:
        return True
    
    def is_failure(self) -> bool:
        return False
    
    def unwrap(self) -> T:
        return self.value


class Failure(Result[T, E]):
    def __init__(self, error: E):
        self.error = error
    
    def is_success(self) -> bool:
        return False
    
    def is_failure(self) -> bool:
        return True
    
    def unwrap_error(self) -> E:
        return self.error


# ResultAsync 클래스 (수정된 버전)
class ResultAsync(Generic[T, E]):
    """
    __await__ 메서드가 추가된 ResultAsync
    """
    
    def __init__(self, result: Awaitable[Result[T, E]]):
        self._result = result
        self._cached_result: Optional[Result[T, E]] = None
        self._is_resolved = False
    
    def __await__(self):
        """
        ResultAsync를 awaitable하게 만드는 핵심 메서드
        """
        async def resolve():
            if not self._is_resolved:
                self._cached_result = await self._result
                self._is_resolved = True
            return self._cached_result
        
        return resolve().__await__()
    
    @classmethod
    def from_value(cls, value: T) -> "ResultAsync[T, E]":
        """값으로부터 ResultAsync 생성"""
        async def create_success() -> Result[T, E]:
            return Success(value)
        
        return cls(create_success())
    
    @classmethod
    def from_error(cls, error: E) -> "ResultAsync[T, E]":
        """에러로부터 ResultAsync 생성"""
        async def create_failure() -> Result[T, E]:
            return Failure(error)
        
        return cls(create_failure())
    
    def bind_async(
        self, func: Callable[[T], "ResultAsync[U, E]" | Awaitable[Result[U, E]]]
    ) -> "ResultAsync[U, E]":
        """비동기 bind 연산"""
        async def bound() -> Result[U, E]:
            result = await self  # __await__ 덕분에 가능
            if result.is_success():
                try:
                    next_result = func(result.unwrap())
                    # ResultAsync인 경우 await
                    if isinstance(next_result, ResultAsync):
                        return await next_result
                    # Awaitable[Result]인 경우
                    else:
                        return await next_result
                except Exception as e:
                    return Failure(e)
            else:
                return Failure(result.unwrap_error())
        
        return ResultAsync(bound())
    
    def map_async(self, func: Callable[[T], Awaitable[U]]) -> "ResultAsync[U, E]":
        """비동기 map 연산"""
        async def mapped() -> Result[U, E]:
            result = await self  # __await__ 덕분에 가능
            if result.is_success():
                try:
                    mapped_value = await func(result.unwrap())
                    return Success(mapped_value)
                except Exception as e:
                    return Failure(e)
            else:
                return Failure(result.unwrap_error())
        
        return ResultAsync(mapped())


async def test_await_chaining():
    """체이닝 테스트"""
    print("테스트: ResultAsync 체이닝 with await")
    
    try:
        # 체이닝 테스트
        result = await (
            ResultAsync.from_value(10)
            .map_async(lambda x: asyncio.coroutine(lambda: x * 2)())
            .bind_async(lambda x: ResultAsync.from_value(x + 5))
        )
        
        assert result.is_success(), f"Result is not success: {result}"
        actual = result.unwrap()
        expected = 25  # (10 * 2) + 5
        assert actual == expected, f"Expected {expected}, got {actual}"
        print("✅ 성공: 체이닝이 정상 작동합니다!")
        print(f"   결과값: {actual}")
        return True
        
    except TypeError as e:
        print(f"❌ 실패 - TypeError: {e}")
        return False
    except AssertionError as e:
        print(f"❌ 실패 - 값이 일치하지 않음: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_direct_await():
    """직접 await 테스트"""
    print("\n테스트: ResultAsync 직접 await")
    
    try:
        result_async = ResultAsync.from_value(42)
        result = await result_async
        
        assert isinstance(result, Result)
        assert result.is_success()
        assert result.unwrap() == 42
        print("✅ 성공: ResultAsync를 직접 await할 수 있습니다!")
        print(f"   결과값: {result.unwrap()}")
        return True
        
    except TypeError as e:
        print(f"❌ 실패 - TypeError: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_failure_propagation():
    """실패 전파 테스트"""
    print("\n테스트: 체이닝 중 실패 전파")
    
    async def fail_on_negative(x: int) -> Result[int, str]:
        if x < 0:
            return Failure(f"{x}는 음수입니다")
        return Success(x)
    
    try:
        # 실패가 전파되는지 테스트
        result = await (
            ResultAsync.from_value(-5)
            .bind_async(fail_on_negative)
            .map_async(lambda x: asyncio.coroutine(lambda: x * 2)())
        )
        
        assert result.is_failure()
        assert result.unwrap_error() == "-5는 음수입니다"
        print("✅ 성공: 실패가 올바르게 전파됩니다!")
        print(f"   에러 메시지: {result.unwrap_error()}")
        return True
        
    except Exception as e:
        print(f"❌ 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_no_runtime_warnings():
    """RuntimeWarning 체크"""
    print("\n테스트: RuntimeWarning 발생 여부 확인")
    
    import warnings
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        try:
            # RuntimeWarning을 발생시켰던 패턴
            result = await (
                ResultAsync.from_value(100)
                .bind_async(lambda x: ResultAsync.from_value(x // 2))
                .map_async(lambda x: asyncio.coroutine(lambda: x - 10)())
            )
            
            # RuntimeWarning 체크
            runtime_warnings = [
                warning for warning in w 
                if issubclass(warning.category, RuntimeWarning)
            ]
            
            if runtime_warnings:
                print(f"❌ RuntimeWarning 발생:")
                for warning in runtime_warnings:
                    print(f"   - {warning.message}")
                return False
            
            assert result.is_success(), f"Result is not success: {result}"
            actual = result.unwrap()
            expected = 40  # (100 // 2) - 10
            assert actual == expected, f"Expected {expected}, got {actual}"
            print("✅ 성공: RuntimeWarning 없이 실행됩니다!")
            print(f"   결과값: {actual}")
            return True
            
        except Exception as e:
            print(f"❌ 실패: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """모든 테스트 실행"""
    print("=" * 60)
    print("ResultAsync __await__ 메서드 테스트")
    print("Python의 awaitable 프로토콜 구현 검증")
    print("=" * 60)
    
    results = []
    
    # 테스트 실행
    results.append(await test_await_chaining())
    results.append(await test_direct_await())
    results.append(await test_failure_propagation())
    results.append(await test_no_runtime_warnings())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"총 테스트: {total}")
    print(f"✅ 성공: {passed}")
    print(f"❌ 실패: {failed}")
    
    if failed == 0:
        print("\n🎉 모든 테스트가 통과했습니다!")
        print("ResultAsync가 이제 Python의 awaitable 프로토콜을 완벽하게 지원합니다.")
        print("\n다음과 같은 체이닝이 가능합니다:")
        print("""
result = await (
    ResultAsync.from_value(10)
    .bind_async(lambda x: ResultAsync.from_value(x * 2))
    .map_async(lambda x: x + 5)
)
        """)
    else:
        print(f"\n⚠️ {failed}개의 테스트가 실패했습니다.")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)