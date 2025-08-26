"""
RFS Framework field import 오류 재현 스크립트
"""
import traceback
import sys


def reproduce_field_error():
    """field import 오류를 재현합니다."""
    print("🔍 RFS Framework field import 오류 재현 중...")
    print("=" * 60)
    
    try:
        print("Step 1: RFS Framework import 시도...")
        from rfs.cache import RedisCache, RedisCacheConfig
        print("✅ RFS Framework import 성공")
        
    except NameError as e:
        print("❌ NameError 발생!")
        print(f"Error: {e}")
        print("\n📋 Stack Trace:")
        traceback.print_exc()
        
        # 에러 분석
        print("\n🔍 에러 분석:")
        print("- 파일: rfs/core/config.py:97")
        print("- 문제: `field` 함수가 import되지 않음")
        print("- 원인: `from dataclasses import field` 누락")
        
        return False
        
    except ImportError as e:
        print("❌ ImportError 발생!")
        print(f"Error: {e}")
        print("RFS Framework가 설치되지 않았을 수 있습니다.")
        return False
        
    except Exception as e:
        print(f"❌ 예상치 못한 에러: {e}")
        traceback.print_exc()
        return False
    
    return True


def test_fix_validation():
    """수정사항이 적용되었는지 확인합니다."""
    print("\n🧪 수정사항 검증 중...")
    
    try:
        # 수정된 버전에서는 정상 동작해야 함
        from rfs.core.config import RFSConfig
        
        # 설정 객체 생성 테스트
        config = RFSConfig()
        assert hasattr(config, 'custom'), "custom 필드가 없습니다"
        assert isinstance(config.custom, dict), "custom 필드가 dict 타입이 아닙니다"
        
        # 기본 동작 테스트  
        config.custom['test_key'] = 'test_value'
        assert config.custom['test_key'] == 'test_value', "custom 필드 동작 오류"
        
        print("✅ 수정사항 검증 성공")
        return True
        
    except Exception as e:
        print(f"❌ 수정사항 검증 실패: {e}")
        traceback.print_exc()
        return False


def main():
    """메인 실행 함수"""
    print("🚀 RFS Framework field import 버그 재현 및 검증")
    print("Python 버전:", sys.version)
    print("=" * 60)
    
    # 1. 버그 재현
    error_reproduced = not reproduce_field_error()
    
    if error_reproduced:
        print("\n✅ 버그가 성공적으로 재현되었습니다.")
        print("📝 이 결과를 바탕으로 PR을 작성할 수 있습니다.")
    else:
        print("\n🎉 오류가 발생하지 않았습니다!")
        print("수정사항이 이미 적용되었거나 환경이 다를 수 있습니다.")
        
        # 수정사항 검증 시도
        test_fix_validation()
    
    print("\n" + "=" * 60)
    print("재현 스크립트 완료")


if __name__ == "__main__":
    main()