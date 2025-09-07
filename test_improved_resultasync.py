#!/usr/bin/env python
"""
개선된 ResultAsync 테스트 스크립트

캐싱과 런타임 경고 방지 기능을 테스트합니다.
"""

import asyncio
import warnings
import sys
import os

# 프로젝트 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 환경 변수 설정
os.environ['RFS_ENV'] = 'test'

# 경고 모니터링
warnings.simplefilter('always')


async def test_improved_resultasync():
    """개선된 ResultAsync 테스트"""
    print("개선된 ResultAsync 테스트 시작")
    print("=" * 60)
    
    # 직접 필요한 모듈만 import
    from rfs.core.result import Result, Success, Failure, ResultAsync
    
    print("\n1. 기본 생성 및 캐싱 테스트")
    print("-" * 40)
    
    # from_value 테스트
    result = ResultAsync.from_value("test_value")
    
    # 여러 번 호출해도 캐싱으로 문제 없음
    success1 = await result.is_success()
    success2 = await result.is_success()
    value1 = await result.unwrap_or("default")
    value2 = await result.unwrap_or("default")
    
    print(f"✓ is_success (첫 번째): {success1}")
    print(f"✓ is_success (두 번째): {success2}")
    print(f"✓ unwrap_or (첫 번째): {value1}")
    print(f"✓ unwrap_or (두 번째): {value2}")
    
    assert success1 == success2 == True
    assert value1 == value2 == "test_value"
    print("✅ 캐싱이 정상 작동합니다!")
    
    print("\n2. from_error 테스트")
    print("-" * 40)
    
    error_result = ResultAsync.from_error("test_error")
    
    is_fail1 = await error_result.is_failure()
    is_fail2 = await error_result.is_failure()
    default_val = await error_result.unwrap_or("fallback")
    
    print(f"✓ is_failure (첫 번째): {is_fail1}")
    print(f"✓ is_failure (두 번째): {is_fail2}")
    print(f"✓ unwrap_or with default: {default_val}")
    
    assert is_fail1 == is_fail2 == True
    assert default_val == "fallback"
    print("✅ 에러 케이스도 정상 작동합니다!")
    
    print("\n3. bind_async 테스트")
    print("-" * 40)
    
    async def process_data(value: str) -> Result[str, str]:
        """비동기 처리 함수"""
        await asyncio.sleep(0.01)
        return Success(f"processed_{value}")
    
    chained_result = ResultAsync.from_value("data").bind_async(process_data)
    final = await chained_result.to_result()
    
    print(f"✓ Chained result: {final.unwrap()}")
    assert final.unwrap() == "processed_data"
    print("✅ bind_async 체이닝이 정상 작동합니다!")
    
    print("\n4. map_async 테스트")
    print("-" * 40)
    
    async def transform(value: str) -> str:
        """비동기 변환 함수"""
        await asyncio.sleep(0.01)
        return value.upper()
    
    mapped_result = ResultAsync.from_value("hello").map_async(transform)
    mapped_final = await mapped_result.to_result()
    
    print(f"✓ Mapped result: {mapped_final.unwrap()}")
    assert mapped_final.unwrap() == "HELLO"
    print("✅ map_async가 정상 작동합니다!")
    
    print("\n5. 헬퍼 함수 테스트")
    print("-" * 40)
    
    from rfs.core.result import async_success, async_failure
    
    success_result = async_success("success")
    success_val = await success_result.to_result()
    
    failure_result = async_failure("failure")
    failure_val = await failure_result.to_result()
    
    print(f"✓ async_success: {success_val.unwrap()}")
    print(f"✓ async_failure: {failure_val.unwrap_error()}")
    
    assert success_val.unwrap() == "success"
    assert failure_val.unwrap_error() == "failure"
    print("✅ 헬퍼 함수들이 정상 작동합니다!")
    
    print("\n" + "=" * 60)
    print("🎉 모든 테스트 통과! 런타임 경고 없음!")


async def test_runtime_warnings():
    """런타임 경고 감지 테스트"""
    print("\n런타임 경고 감지 테스트")
    print("=" * 60)
    
    from rfs.core.result import ResultAsync
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # ResultAsync 사용
        result = ResultAsync.from_value("test")
        
        # 여러 번 호출
        for i in range(3):
            success = await result.is_success()
            value = await result.unwrap_or("default")
            print(f"  반복 {i+1}: success={success}, value={value}")
        
        # 런타임 경고 확인
        runtime_warnings = [
            warning for warning in w 
            if issubclass(warning.category, RuntimeWarning)
        ]
        
        if runtime_warnings:
            print(f"\n❌ 런타임 경고 발생:")
            for warning in runtime_warnings:
                print(f"  - {warning.message}")
        else:
            print("\n✅ 런타임 경고 없음!")
        
        return len(runtime_warnings) == 0


async def main():
    """메인 함수"""
    print("\n" + "=" * 70)
    print("   ResultAsync 개선 사항 테스트")
    print("=" * 70 + "\n")
    
    try:
        # 기능 테스트
        await test_improved_resultasync()
        
        # 경고 테스트
        no_warnings = await test_runtime_warnings()
        
        if no_warnings:
            print("\n" + "=" * 70)
            print("   ✅ 모든 개선 사항이 정상 작동합니다!")
            print("   - 캐싱 기능 ✓")
            print("   - 런타임 경고 방지 ✓")
            print("   - 헬퍼 함수 수정 ✓")
            print("=" * 70)
        else:
            print("\n⚠️ 일부 런타임 경고가 여전히 발생합니다.")
            
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())