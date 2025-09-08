#!/usr/bin/env python3
"""
ResultAsync 체이닝 버그 수정 검증 스크립트
독립 실행 가능한 테스트
"""

import asyncio
import sys
import os

# rfs 모듈 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 환경 변수 설정
os.environ['RFS_ENV'] = 'test'

# 이제 import
from rfs.core.result import Result, Success, Failure, ResultAsync


async def test_basic_chaining():
    """기본 체이닝 테스트"""
    print("테스트 1: 기본 체이닝 with await")
    
    try:
        # 이전에 실패했던 패턴
        result = await (
            ResultAsync.from_value(10)
            .map_async(lambda x: asyncio.coroutine(lambda: x * 2)())
            .bind_async(lambda x: ResultAsync.from_value(x + 5))
        )
        
        assert result.is_success()
        assert result.unwrap() == 25
        print("✅ 성공: 체이닝이 정상 작동합니다!")
        return True
    except TypeError as e:
        print(f"❌ 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 에러: {e}")
        return False


async def test_direct_await():
    """직접 await 테스트"""
    print("\n테스트 2: ResultAsync 객체 직접 await")
    
    try:
        result_async = ResultAsync.from_value(5)
        result = await result_async  # 이전에는 여기서 에러 발생
        
        assert isinstance(result, Result)
        assert result.is_success()
        assert result.unwrap() == 5
        print("✅ 성공: ResultAsync를 직접 await할 수 있습니다!")
        return True
    except TypeError as e:
        print(f"❌ 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 에러: {e}")
        return False


async def test_complex_chaining():
    """복잡한 체이닝 테스트"""
    print("\n테스트 3: 복잡한 체이닝 패턴")
    
    async def validate_positive(x: int) -> Result[int, str]:
        if x > 0:
            return Success(x)
        return Failure("음수는 허용되지 않습니다")
    
    async def double_value(x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2
    
    try:
        result = await (
            ResultAsync.from_value(10)
            .bind_async(validate_positive)
            .map_async(double_value)
            .map_async(lambda x: asyncio.coroutine(lambda: x + 100)())
        )
        
        assert result.is_success()
        assert result.unwrap() == 120
        print("✅ 성공: 복잡한 체이닝도 작동합니다!")
        return True
    except Exception as e:
        print(f"❌ 실패: {e}")
        return False


async def test_failure_propagation():
    """실패 전파 테스트"""
    print("\n테스트 4: 체이닝 중 실패 전파")
    
    async def fail_if_even(x: int) -> Result[int, str]:
        if x % 2 == 0:
            return Failure(f"{x}는 짝수입니다")
        return Success(x)
    
    async def never_called(x: int) -> int:
        raise Exception("이 함수는 호출되지 않아야 합니다")
    
    try:
        result = await (
            ResultAsync.from_value(10)
            .bind_async(fail_if_even)
            .map_async(never_called)
        )
        
        assert result.is_failure()
        assert result.unwrap_error() == "10는 짝수입니다"
        print("✅ 성공: 실패가 올바르게 전파됩니다!")
        return True
    except Exception as e:
        print(f"❌ 실패: {e}")
        return False


async def test_no_runtime_warnings():
    """RuntimeWarning 없음 테스트"""
    print("\n테스트 5: RuntimeWarning 발생 여부")
    
    import warnings
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        try:
            result = await (
                ResultAsync.from_value(10)
                .bind_async(lambda x: ResultAsync.from_value(x * 2))
                .map_async(lambda x: asyncio.coroutine(lambda: x + 5)())
            )
            
            runtime_warnings = [
                warning for warning in w 
                if issubclass(warning.category, RuntimeWarning)
            ]
            
            if runtime_warnings:
                print(f"❌ RuntimeWarning 발생: {runtime_warnings}")
                return False
            
            assert result.is_success()
            assert result.unwrap() == 25
            print("✅ 성공: RuntimeWarning 없이 실행됩니다!")
            return True
        except Exception as e:
            print(f"❌ 실패: {e}")
            return False


async def main():
    """모든 테스트 실행"""
    print("=" * 60)
    print("ResultAsync 체이닝 버그 수정 검증")
    print("RFS Framework v4.6.3")
    print("=" * 60)
    
    results = []
    
    # 모든 테스트 실행
    results.append(await test_basic_chaining())
    results.append(await test_direct_await())
    results.append(await test_complex_chaining())
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
    print(f"성공: {passed}")
    print(f"실패: {failed}")
    
    if failed == 0:
        print("\n🎉 모든 테스트가 통과했습니다!")
        print("ResultAsync 체이닝 버그가 성공적으로 수정되었습니다.")
    else:
        print(f"\n⚠️ {failed}개의 테스트가 실패했습니다.")
        print("추가 디버깅이 필요합니다.")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)