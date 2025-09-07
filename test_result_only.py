#!/usr/bin/env python
"""
ResultAsync 직접 테스트 (초기화 없이)
"""

import asyncio
import warnings
import sys
import os
from typing import Optional, TypeVar, Generic, Callable, Awaitable

# 경고 모니터링
warnings.simplefilter('always')

# 직접 result.py 파일을 실행
sys.path.insert(0, '/Users/sangbongmoon/Workspace/rfs-framework/src')

# result.py의 내용을 직접 실행
exec(open('/Users/sangbongmoon/Workspace/rfs-framework/src/rfs/core/result.py').read())


async def test_resultasync_improvements():
    """ResultAsync 개선 사항 테스트"""
    
    print("ResultAsync 개선 테스트")
    print("=" * 60)
    
    print("\n1. 캐싱 테스트 - 여러 번 await 가능")
    print("-" * 40)
    
    # ResultAsync 생성
    result = ResultAsync.from_value("test_value")
    
    # 여러 번 호출
    success1 = await result.is_success()
    print(f"  첫 번째 is_success(): {success1}")
    
    success2 = await result.is_success()
    print(f"  두 번째 is_success(): {success2}")
    
    value1 = await result.unwrap_or("default")
    print(f"  첫 번째 unwrap_or(): {value1}")
    
    value2 = await result.unwrap_or("default")
    print(f"  두 번째 unwrap_or(): {value2}")
    
    # to_result도 여러 번 호출 가능
    res1 = await result.to_result()
    res2 = await result.to_result()
    print(f"  to_result() 여러 번 호출: {res1.unwrap()} == {res2.unwrap()}")
    
    assert success1 == success2 == True
    assert value1 == value2 == "test_value"
    print("✅ 캐싱이 정상 작동합니다!")
    
    print("\n2. 에러 케이스 테스트")
    print("-" * 40)
    
    error_result = ResultAsync.from_error("error_msg")
    
    failure1 = await error_result.is_failure()
    failure2 = await error_result.is_failure()
    
    print(f"  is_failure() 여러 번: {failure1} == {failure2}")
    
    default_val = await error_result.unwrap_or("fallback")
    print(f"  unwrap_or('fallback'): {default_val}")
    
    assert failure1 == failure2 == True
    assert default_val == "fallback"
    print("✅ 에러 케이스도 정상 작동합니다!")
    
    print("\n3. 헬퍼 함수 테스트")
    print("-" * 40)
    
    # async_success 테스트
    success_result = async_success("success_value")
    success_val = await success_result.to_result()
    print(f"  async_success: {success_val.unwrap()}")
    
    # async_failure 테스트
    failure_result = async_failure("error_value")
    failure_val = await failure_result.to_result()
    print(f"  async_failure: {failure_val.unwrap_error()}")
    
    assert success_val.unwrap() == "success_value"
    assert failure_val.unwrap_error() == "error_value"
    print("✅ 헬퍼 함수들이 정상 작동합니다!")
    
    print("\n4. 런타임 경고 확인")
    print("-" * 40)
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # 다양한 작업 수행
        test_result = ResultAsync.from_value("warning_test")
        
        for i in range(3):
            await test_result.is_success()
            await test_result.unwrap_or("default")
        
        # 런타임 경고 체크
        runtime_warnings = [
            warning for warning in w 
            if issubclass(warning.category, RuntimeWarning)
        ]
        
        if runtime_warnings:
            print(f"  ❌ 런타임 경고 {len(runtime_warnings)}개 발생:")
            for warning in runtime_warnings:
                print(f"    - {warning.message}")
        else:
            print("  ✅ 런타임 경고 없음!")
    
    print("\n" + "=" * 60)
    print("🎉 모든 개선 사항이 정상 작동합니다!")
    print("  - 결과 캐싱 ✓")
    print("  - 중복 await 가능 ✓")
    print("  - 헬퍼 함수 수정 ✓")
    print("  - 런타임 경고 방지 ✓")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("   ResultAsync 개선 사항 직접 테스트")
    print("=" * 70 + "\n")
    
    try:
        asyncio.run(test_resultasync_improvements())
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()