#!/usr/bin/env python3
"""
ResultAsync __await__ 메서드만 테스트
가장 간단한 케이스부터 시작
"""

import asyncio
import sys
import os

# 환경 변수 설정
os.environ['RFS_ENV'] = 'test'

# rfs 모듈 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from rfs.core.result import Result, Success, Failure, ResultAsync


async def test_1_direct_await():
    """가장 간단한 테스트: 직접 await"""
    print("테스트 1: ResultAsync를 직접 await")
    
    # ResultAsync 생성
    async_result = ResultAsync.from_value(42)
    
    # 직접 await (이전에는 여기서 TypeError 발생)
    result = await async_result
    
    print(f"  타입: {type(result)}")
    print(f"  성공 여부: {result.is_success()}")
    print(f"  값: {result.unwrap()}")
    
    assert result.is_success()
    assert result.unwrap() == 42
    print("  ✅ 통과!")


async def test_2_simple_chain():
    """간단한 체이닝 테스트"""
    print("\n테스트 2: 간단한 체이닝")
    
    # 간단한 async 함수
    async def double(x):
        return x * 2
    
    # 체이닝
    result = await (
        ResultAsync.from_value(10)
        .map_async(double)
    )
    
    print(f"  타입: {type(result)}")
    print(f"  성공 여부: {result.is_success()}")
    print(f"  값: {result.unwrap()}")
    
    assert result.is_success()
    assert result.unwrap() == 20
    print("  ✅ 통과!")


async def test_3_bind_chain():
    """bind_async 체이닝 테스트"""
    print("\n테스트 3: bind_async 체이닝")
    
    # bind에 사용할 함수
    async def validate_and_double(x: int) -> Result[int, str]:
        if x > 0:
            return Success(x * 2)
        return Failure("음수입니다")
    
    # 체이닝
    result = await (
        ResultAsync.from_value(10)
        .bind_async(validate_and_double)
    )
    
    print(f"  타입: {type(result)}")
    print(f"  성공 여부: {result.is_success()}")
    print(f"  값: {result.unwrap()}")
    
    assert result.is_success()
    assert result.unwrap() == 20
    print("  ✅ 통과!")


async def test_4_bind_with_resultasync():
    """bind_async에 ResultAsync를 반환하는 함수 사용"""
    print("\n테스트 4: bind_async with ResultAsync 반환")
    
    # ResultAsync를 반환하는 함수
    def double_async(x: int) -> ResultAsync[int, str]:
        return ResultAsync.from_value(x * 2)
    
    # 체이닝
    result = await (
        ResultAsync.from_value(10)
        .bind_async(double_async)
    )
    
    print(f"  타입: {type(result)}")
    print(f"  성공 여부: {result.is_success()}")
    
    if result.is_success():
        print(f"  값: {result.unwrap()}")
        assert result.unwrap() == 20
        print("  ✅ 통과!")
    else:
        print(f"  에러: {result.unwrap_error()}")
        print("  ❌ 실패!")
        return False
    
    return True


async def test_5_multiple_binds():
    """여러 bind_async 체이닝"""
    print("\n테스트 5: 여러 bind_async 체이닝")
    
    def add_five(x: int) -> ResultAsync[int, str]:
        return ResultAsync.from_value(x + 5)
    
    def multiply_two(x: int) -> ResultAsync[int, str]:
        return ResultAsync.from_value(x * 2)
    
    # 체이닝
    result = await (
        ResultAsync.from_value(10)
        .bind_async(multiply_two)  # 10 * 2 = 20
        .bind_async(add_five)       # 20 + 5 = 25
    )
    
    print(f"  타입: {type(result)}")
    print(f"  성공 여부: {result.is_success()}")
    
    if result.is_success():
        print(f"  값: {result.unwrap()}")
        assert result.unwrap() == 25
        print("  ✅ 통과!")
    else:
        print(f"  에러: {result.unwrap_error()}")
        print("  ❌ 실패!")
        return False
    
    return True


async def main():
    """모든 테스트 실행"""
    print("=" * 60)
    print("ResultAsync __await__ 메서드 단계별 테스트")
    print("=" * 60)
    
    try:
        await test_1_direct_await()
        await test_2_simple_chain()
        await test_3_bind_chain()
        success_4 = await test_4_bind_with_resultasync()
        success_5 = await test_5_multiple_binds()
        
        print("\n" + "=" * 60)
        if success_4 and success_5:
            print("🎉 모든 테스트 통과!")
            print("\n__await__ 메서드가 정상적으로 작동합니다.")
            print("ResultAsync 체이닝 버그가 해결되었습니다!")
        else:
            print("⚠️ 일부 테스트 실패")
            print("bind_async에서 ResultAsync 처리에 문제가 있습니다.")
    except Exception as e:
        print(f"\n❌ 테스트 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())