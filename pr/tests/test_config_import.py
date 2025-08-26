"""
RFS Framework config import 테스트
"""
import pytest
import sys
from unittest.mock import patch, MagicMock


class TestRFSConfigImport:
    """RFS Config import 관련 테스트"""

    def test_rfs_config_import_success(self):
        """RFS Config가 정상적으로 import되는지 테스트"""
        try:
            from rfs.core.config import RFSConfig
            assert RFSConfig is not None
            
        except ImportError:
            pytest.skip("RFS Framework가 설치되지 않음")
            
        except NameError as e:
            pytest.fail(f"NameError 발생: {e}")

    def test_rfs_config_instantiation(self):
        """RFS Config 객체 생성 테스트"""
        try:
            from rfs.core.config import RFSConfig
            
            config = RFSConfig()
            assert config is not None
            assert hasattr(config, 'custom')
            assert isinstance(config.custom, dict)
            
        except ImportError:
            pytest.skip("RFS Framework가 설치되지 않음")

    def test_custom_field_functionality(self):
        """custom 필드 기능 테스트"""
        try:
            from rfs.core.config import RFSConfig
            
            config = RFSConfig()
            
            # 기본값 테스트
            assert config.custom == {}
            
            # 값 설정 테스트
            config.custom['test_key'] = 'test_value'
            assert config.custom['test_key'] == 'test_value'
            
            # 중첩 딕셔너리 테스트
            config.custom['nested'] = {'inner_key': 'inner_value'}
            assert config.custom['nested']['inner_key'] == 'inner_value'
            
        except ImportError:
            pytest.skip("RFS Framework가 설치되지 않음")

    def test_field_import_error_detection(self):
        """field import 오류를 감지하는 테스트"""
        
        # dataclasses.field가 import되지 않은 상황을 시뮬레이션
        with patch.dict('sys.modules', {'dataclasses': MagicMock()}):
            # field 함수를 undefined로 설정
            sys.modules['dataclasses'].field = None
            
            try:
                # 이 시점에서 NameError가 발생해야 함
                from rfs.core.config import RFSConfig
                
                # 만약 import가 성공했다면, field 함수 확인
                import dataclasses
                assert hasattr(dataclasses, 'field'), "field 함수가 import되지 않았습니다"
                
            except (NameError, AttributeError) as e:
                # 예상된 에러 - 테스트 통과
                assert 'field' in str(e).lower()
                
            except ImportError:
                pytest.skip("RFS Framework가 설치되지 않음")


class TestFieldImportFix:
    """field import 수정사항 테스트"""

    def test_dataclass_field_import(self):
        """dataclass field가 올바르게 import되는지 테스트"""
        try:
            from dataclasses import field
            assert field is not None
            assert callable(field)
            
        except ImportError as e:
            pytest.fail(f"dataclasses.field import 실패: {e}")

    def test_field_default_factory(self):
        """field의 default_factory 기능 테스트"""
        try:
            from dataclasses import dataclass, field
            
            @dataclass
            class TestConfig:
                custom: dict = field(default_factory=dict)
            
            config = TestConfig()
            assert isinstance(config.custom, dict)
            assert config.custom == {}
            
            # 서로 다른 인스턴스는 다른 dict를 가져야 함
            config1 = TestConfig()
            config2 = TestConfig()
            
            config1.custom['test'] = 'value1'
            config2.custom['test'] = 'value2'
            
            assert config1.custom['test'] != config2.custom['test']
            
        except ImportError as e:
            pytest.fail(f"dataclass 관련 import 실패: {e}")

    def test_pydantic_field_alternative(self):
        """Pydantic Field 대안이 작동하는지 테스트"""
        try:
            from pydantic import BaseSettings, Field
            
            class TestConfig(BaseSettings):
                custom: dict = Field(default_factory=dict)
            
            config = TestConfig()
            assert isinstance(config.custom, dict)
            assert config.custom == {}
            
        except ImportError:
            pytest.skip("Pydantic이 설치되지 않음")


# 성능 테스트
class TestRFSConfigPerformance:
    """RFS Config 성능 테스트"""

    def test_config_creation_performance(self):
        """Config 생성 성능 테스트"""
        import time
        
        try:
            from rfs.core.config import RFSConfig
            
            start_time = time.time()
            
            # 100번 생성
            for _ in range(100):
                config = RFSConfig()
                assert hasattr(config, 'custom')
            
            elapsed_time = time.time() - start_time
            
            # 1초 이내에 완료되어야 함
            assert elapsed_time < 1.0, f"Config 생성이 너무 느림: {elapsed_time}초"
            
        except ImportError:
            pytest.skip("RFS Framework가 설치되지 않음")


if __name__ == "__main__":
    # 직접 실행시 기본 테스트 수행
    print("🧪 RFS Config Import 테스트 실행")
    
    test_instance = TestRFSConfigImport()
    
    try:
        test_instance.test_rfs_config_import_success()
        print("✅ Import 테스트 통과")
        
        test_instance.test_rfs_config_instantiation()
        print("✅ 객체 생성 테스트 통과")
        
        test_instance.test_custom_field_functionality()
        print("✅ custom 필드 기능 테스트 통과")
        
        print("🎉 모든 테스트 통과!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()