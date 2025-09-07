#!/usr/bin/env python
"""
ResultAsync 런타임 경고 재현을 위한 간단한 테스트
"""

import asyncio
import warnings
from typing import Awaitable, TypeVar, Generic, Callable

# 경고를 모두 표시
warnings.simplefilter('always')

T = TypeVar('T')
E = TypeVar('E')


# 간단한 Result 클래스들
class Success:
    def __init__(self, value):
        self.value = value
    
    def is_success(self):
        return True
    
    def unwrap(self):
        return self.value
    
    def unwrap_or(self, default):
        return self.value


class Failure:
    def __init__(self, error):
        self.error = error
    
    def is_success(self):
        return False
    
    def unwrap(self):
        raise Exception(f"Cannot unwrap failure: {self.error}")
    
    def unwrap_or(self, default):
        return default


class ResultAsync(Generic[T, E]):
    """문제가 있는 ResultAsync 구현"""
    
    def __init__(self, result):
        self._result = result
    
    @classmethod
    def from_value_wrong(cls, value):
        """문제가 있는 구현 - 코루틴을 생성하지 않음"""
        async def create_success():
            return Success(value)
        # create_success를 호출하지 않음 - 함수 객체만 전달
        return cls(create_success)  # 문제: () 없음
    
    @classmethod
    def from_value_correct(cls, value):
        """올바른 구현 - 코루틴 객체 생성"""
        async def create_success():
            return Success(value)
        # create_success()를 호출하여 코루틴 객체 생성
        return cls(create_success())  # 올바름: () 있음
    
    async def is_success(self):
        """비동기 메서드 - await 없이 호출하면 경고 발생"""
        if callable(self._result):
            # 함수라면 호출해야 함
            result = await self._result()
        else:
            # 코루틴이라면 await
            result = await self._result
        return result.is_success()
    
    async def unwrap_or(self, default):
        """비동기 메서드"""
        if callable(self._result):
            result = await self._result()
        else:
            result = await self._result
        return result.unwrap_or(default)


async def test_wrong_pattern():
    """잘못된 패턴 - 경고 발생"""
    print("\n=== 잘못된 패턴 (경고 발생 예상) ===")
    
    # from_value_wrong 사용
    result = ResultAsync.from_value_wrong("test")
    
    # 이 부분에서 문제 발생 가능
    try:
        success = await result.is_success()
        print(f"성공: {success}")
        
        value = await result.unwrap_or("default")
        print(f"값: {value}")
    except Exception as e:
        print(f"에러: {e}")


async def test_correct_pattern():
    """올바른 패턴"""
    print("\n=== 올바른 패턴 ===")
    
    # from_value_correct 사용
    result = ResultAsync.from_value_correct("test")
    
    try:
        success = await result.is_success()
        print(f"성공: {success}")
        
        value = await result.unwrap_or("default")
        print(f"값: {value}")
    except Exception as e:
        print(f"에러: {e}")


async def test_sync_call_async_method():
    """비동기 메서드를 동기적으로 호출하면 경고 발생"""
    print("\n=== 비동기 메서드를 await 없이 호출 (경고 발생) ===")
    
    result = ResultAsync.from_value_correct("test")
    
    # await 없이 호출하면 경고 발생
    print("is_success() 를 await 없이 호출:")
    coro = result.is_success()  # 코루틴 객체 반환, 실행되지 않음
    print(f"반환 타입: {type(coro)}")
    
    # 나중에 await로 실행
    success = await coro
    print(f"결과: {success}")


async def main():
    """메인 테스트 함수"""
    print("ResultAsync 런타임 경고 테스트")
    print("=" * 60)
    
    await test_wrong_pattern()
    await test_correct_pattern()
    await test_sync_call_async_method()
    
    print("\n" + "=" * 60)
    print("테스트 완료")


if __name__ == "__main__":
    # 비동기 함수 실행
    asyncio.run(main())