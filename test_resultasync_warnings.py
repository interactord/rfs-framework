#!/usr/bin/env python
"""
ResultAsync 런타임 경고 테스트

이 스크립트는 ResultAsync 클래스 사용 시 발생하는 런타임 경고를 재현합니다.
"""

import asyncio
import warnings
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 환경 변수 설정
os.environ['RFS_ENV'] = 'test'

# 경고를 모두 표시하도록 설정
warnings.simplefilter('always')


async def test_resultasync_warnings():
    """ResultAsync 런타임 경고를 재현하는 테스트"""
    
    # 간단한 import로만 테스트
    print("Importing ResultAsync...")
    from rfs.core.result import Result, Success, Failure
    
    # ResultAsync는 따로 정의해보기
    from typing import Awaitable, TypeVar, Generic, Callable
    
    T = TypeVar('T')
    E = TypeVar('E')
    
    class TestResultAsync(Generic[T, E]):
        """테스트용 간단한 ResultAsync"""
        
        def __init__(self, result: Awaitable[Result[T, E]]):
            self._result = result
        
        @classmethod
        def from_value(cls, value: T) -> 'TestResultAsync[T, E]':
            """값으로부터 ResultAsync 생성 - 문제가 되는 패턴"""
            async def create_success() -> Result[T, E]:
                return Success(value)
            # 여기서 create_success를 호출하지 않으면 코루틴이 생성되지 않음
            return cls(create_success())  # () 가 중요!
        
        @classmethod
        def from_value_wrong(cls, value: T) -> 'TestResultAsync[T, E]':
            """잘못된 패턴 - 코루틴을 생성하지 않음"""
            async def create_success() -> Result[T, E]:
                return Success(value)
            # create_success를 호출하지 않아서 문제 발생
            return cls(create_success)  # () 없음 - 문제!
        
        async def is_success(self) -> bool:
            """비동기 성공 여부 확인"""
            result = await self._result
            return result.is_success()
        
        async def unwrap_or(self, default: T) -> T:
            """비동기 값 추출"""
            result = await self._result
            return result.unwrap_or(default)
    
    print("\n=== 올바른 패턴 테스트 ===")
    try:
        result1 = TestResultAsync.from_value("test")
        is_success = await result1.is_success()
        print(f"성공 여부: {is_success}")
        value = await result1.unwrap_or("default")
        print(f"값: {value}")
        print("✅ 경고 없음!")
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
    
    print("\n=== 잘못된 패턴 테스트 (경고 발생 예상) ===")
    try:
        result2 = TestResultAsync.from_value_wrong("test")
        # 이 부분에서 경고가 발생할 것으로 예상
        is_success = await result2.is_success()
        print(f"성공 여부: {is_success}")
    except Exception as e:
        print(f"❌ 에러 발생: {e}")


if __name__ == "__main__":
    print("ResultAsync 런타임 경고 테스트 시작\n")
    print("=" * 60)
    
    # 비동기 함수 실행
    asyncio.run(test_resultasync_warnings())
    
    print("\n" + "=" * 60)
    print("테스트 완료")