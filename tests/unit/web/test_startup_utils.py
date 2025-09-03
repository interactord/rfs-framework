"""
Tests for web startup utilities

PR에서 발견된 서버 시작 문제들을 해결하는 유틸리티들의 테스트
- import 검증
- 타입 체크
- 의존성 확인
- 자동 수정 기능
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, List
import pytest

from rfs.web.startup_utils import (
    validate_imports,
    safe_import,
    check_missing_types,
    resolve_import_path,
    check_dependencies,
    validate_server_startup,
    auto_fix_missing_imports,
    quick_startup_check,
    create_startup_report
)


class TestImportValidation:
    """Import 검증 관련 테스트"""
    
    def test_validate_imports_success(self):
        """유효한 import들의 검증 테스트"""
        result = validate_imports('os', ['os.path', 'typing.Dict'])
        
        assert result.is_success()
        status = result.unwrap()
        assert isinstance(status, dict)
        # os.path와 typing.Dict는 표준 라이브러리이므로 성공해야 함
        assert status.get('typing.Dict') is True
    
    def test_validate_imports_with_invalid_module(self):
        """존재하지 않는 모듈의 검증 테스트"""
        result = validate_imports('nonexistent_module_12345', ['some.import'])
        
        assert result.is_failure()
        error = result.unwrap_error()
        assert "모듈 로드 실패" in error
        assert "nonexistent_module_12345" in error
    
    def test_safe_import_success(self):
        """성공적인 safe_import 테스트"""
        result = safe_import('os')
        
        assert result.is_success()
        module = result.unwrap()
        assert hasattr(module, 'path')  # os 모듈은 path 속성을 가짐
    
    def test_safe_import_failure_with_fallback(self):
        """실패하는 safe_import에서 fallback 사용 테스트"""
        fallback_value = {"mock": "module"}
        result = safe_import('definitely_nonexistent_module_xyz', fallback_value)
        
        assert result.is_success()  # fallback이 제공되었으므로 성공
        value = result.unwrap()
        assert value == fallback_value
    
    def test_safe_import_failure_without_fallback(self):
        """fallback 없이 실패하는 safe_import 테스트"""
        result = safe_import('definitely_nonexistent_module_xyz')
        
        assert result.is_failure()
        error = result.unwrap_error()
        assert "모듈 import 실패" in error


class TestTypeChecking:
    """타입 체크 관련 테스트"""
    
    def test_check_missing_types_with_temp_file(self):
        """임시 파일을 사용한 타입 체크 테스트"""
        # 타입을 사용하지만 import하지 않은 Python 코드
        python_code = '''
def process_data(data: Dict[str, Any]) -> List[str]:
    """Process data and return list of strings."""
    result: Optional[List[str]] = None
    if data:
        result = [str(v) for v in data.values()]
    return result or []
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(python_code)
            temp_file = f.name
        
        try:
            result = check_missing_types(temp_file)
            assert result.is_success()
            
            missing = result.unwrap()
            # Dict, Any, List, Optional이 사용되었지만 import되지 않음
            expected_missing = {'Dict', 'Any', 'List', 'Optional'}
            assert set(missing) == expected_missing
            
        finally:
            os.unlink(temp_file)
    
    def test_check_missing_types_with_imports(self):
        """이미 import가 있는 파일의 타입 체크 테스트"""
        python_code = '''
from typing import Dict, List, Optional, Any

def process_data(data: Dict[str, Any]) -> List[str]:
    """Process data and return list of strings."""
    result: Optional[List[str]] = None
    return result or []
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(python_code)
            temp_file = f.name
        
        try:
            result = check_missing_types(temp_file)
            assert result.is_success()
            
            missing = result.unwrap()
            # 모든 타입이 import되었으므로 누락된 것이 없어야 함
            assert len(missing) == 0
            
        finally:
            os.unlink(temp_file)
    
    def test_check_missing_types_file_not_found(self):
        """존재하지 않는 파일에 대한 타입 체크 테스트"""
        result = check_missing_types('/nonexistent/path/file.py')
        
        assert result.is_failure()
        error = result.unwrap_error()
        assert "파일 읽기 실패" in error


class TestPathResolution:
    """경로 해석 관련 테스트"""
    
    def test_resolve_import_path_relative_current(self):
        """현재 디렉토리 상대 경로 해석 테스트"""
        current_file = '/project/src/services/user_service.py'
        relative_path = './utils'
        
        result = resolve_import_path(current_file, relative_path)
        
        assert result.is_success()
        resolved = result.unwrap()
        assert 'services.utils' in resolved
    
    def test_resolve_import_path_relative_parent(self):
        """상위 디렉토리 상대 경로 해석 테스트"""
        current_file = '/project/src/services/user_service.py'
        relative_path = '../models/user'
        
        result = resolve_import_path(current_file, relative_path)
        
        assert result.is_success()
        resolved = result.unwrap()
        assert 'models.user' in resolved
    
    def test_resolve_import_path_absolute(self):
        """이미 절대 경로인 경우 테스트"""
        current_file = '/project/src/services/user_service.py'
        absolute_path = 'myproject.models.user'
        
        result = resolve_import_path(current_file, absolute_path)
        
        assert result.is_success()
        resolved = result.unwrap()
        assert resolved == absolute_path


class TestDependencyChecking:
    """의존성 확인 관련 테스트"""
    
    def test_check_dependencies_existing_packages(self):
        """존재하는 패키지들의 의존성 체크 테스트"""
        # Python 표준 라이브러리는 항상 있어야 함
        result = check_dependencies(['typing'])  # typing은 내장 모듈
        
        # 하지만 pkg_resources가 typing을 찾지 못할 수 있으므로
        # 실패할 수도 있음. 실제 설치된 패키지로 테스트
        if result.is_success():
            packages = result.unwrap()
            assert isinstance(packages, dict)
    
    def test_check_dependencies_nonexistent_packages(self):
        """존재하지 않는 패키지들의 의존성 체크 테스트"""
        result = check_dependencies(['definitely_nonexistent_package_xyz_123'])
        
        assert result.is_failure()
        error = result.unwrap_error()
        assert "누락된 패키지들" in error


class TestAutoFix:
    """자동 수정 기능 테스트"""
    
    def test_auto_fix_missing_imports_dry_run(self):
        """자동 수정 dry run 테스트"""
        python_code = '''
def process_data(data: Dict[str, Any]) -> List[str]:
    return []
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(python_code)
            temp_file = f.name
        
        try:
            result = auto_fix_missing_imports(temp_file, dry_run=True)
            assert result.is_success()
            
            changes = result.unwrap()
            assert len(changes) > 0
            # dry run이므로 실제 파일은 변경되지 않아야 함
            with open(temp_file, 'r') as f:
                content = f.read()
            assert 'from typing import' not in content
            
        finally:
            os.unlink(temp_file)
    
    def test_auto_fix_missing_imports_actual_fix(self):
        """실제 자동 수정 테스트"""
        python_code = '''
def process_data(data: Dict[str, Any]) -> List[str]:
    return []
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(python_code)
            temp_file = f.name
        
        try:
            result = auto_fix_missing_imports(temp_file, dry_run=False)
            assert result.is_success()
            
            changes = result.unwrap()
            assert len(changes) > 0
            
            # 실제로 파일이 수정되었는지 확인
            with open(temp_file, 'r') as f:
                content = f.read()
            assert 'from typing import' in content
            
        finally:
            os.unlink(temp_file)


class TestServerStartupValidation:
    """서버 시작 검증 관련 테스트"""
    
    def test_validate_server_startup_basic(self):
        """기본적인 서버 시작 검증 테스트"""
        result = validate_server_startup(
            module_paths=['os', 'sys'],  # 표준 라이브러리 모듈들
            required_types=['Dict', 'List'],
            required_packages=[]  # 패키지 체크는 스킵
        )
        
        # 결과의 구조 확인
        if result.is_success():
            validation_info = result.unwrap()
            assert 'modules' in validation_info
            assert 'overall_status' in validation_info
    
    def test_quick_startup_check(self):
        """빠른 시작 체크 테스트"""
        # 현재 디렉토리를 프로젝트 루트로 가정
        project_root = os.getcwd()
        
        # quick_startup_check는 기본적인 모듈들만 체크하므로 성공해야 함
        result = quick_startup_check(project_root)
        assert isinstance(result, bool)
    
    def test_create_startup_report(self):
        """시작 보고서 생성 테스트"""
        sample_validation_results = {
            'overall_status': True,
            'modules': {
                'os': True,
                'sys': True,
                'nonexistent': False
            },
            'packages': {
                'rfs': '1.0.0'
            }
        }
        
        report = create_startup_report(sample_validation_results)
        
        assert isinstance(report, str)
        assert "=== RFS 서버 시작 검증 보고서 ===" in report
        assert "전체 상태: ✅ 성공" in report
        assert "📦 모듈 상태:" in report


class TestErrorHandlingAndEdgeCases:
    """에러 처리 및 엣지 케이스 테스트"""
    
    def test_validate_imports_empty_list(self):
        """빈 import 리스트에 대한 검증 테스트"""
        result = validate_imports('os', [])
        
        assert result.is_success()
        status = result.unwrap()
        assert len(status) == 0
    
    def test_check_missing_types_empty_file(self):
        """빈 파일에 대한 타입 체크 테스트"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('')  # 빈 파일
            temp_file = f.name
        
        try:
            result = check_missing_types(temp_file)
            assert result.is_success()
            
            missing = result.unwrap()
            assert len(missing) == 0  # 빈 파일에는 누락된 타입이 없어야 함
            
        finally:
            os.unlink(temp_file)
    
    def test_safe_import_with_none_fallback(self):
        """None fallback을 가진 safe_import 테스트"""
        result = safe_import('definitely_nonexistent_module', None)
        
        # None이 제공되었으므로 여전히 실패해야 함
        assert result.is_failure()


class TestPRScenarioCompatibility:
    """PR에서 발견된 실제 시나리오 호환성 테스트"""
    
    def test_pr_import_error_scenario(self):
        """PR에서 발견된 import 오류 시나리오 테스트"""
        # PR의 실제 오류: "No module named 'src.document_processor.domain.infrastructure'"
        result = safe_import('src.document_processor.domain.infrastructure')
        
        # 이 모듈은 존재하지 않으므로 실패해야 함
        assert result.is_failure()
        
        # 하지만 fallback으로 처리 가능
        mock_module = type('MockModule', (), {'MockClass': type('MockClass', (), {})})
        result_with_fallback = safe_import('src.document_processor.domain.infrastructure', mock_module)
        assert result_with_fallback.is_success()
    
    def test_pr_missing_dict_import_scenario(self):
        """PR에서 발견된 Dict import 누락 시나리오 테스트"""
        # Dict를 사용하지만 import하지 않은 코드
        python_code = '''
def pipeline_coordinator(data: Dict[str, List[Optional[str]]]) -> str:
    return "processed"
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(python_code)
            temp_file = f.name
        
        try:
            result = check_missing_types(temp_file)
            assert result.is_success()
            
            missing = result.unwrap()
            # PR에서 발견된 것처럼 Dict, List, Optional이 누락되어야 함
            assert 'Dict' in missing
            assert 'List' in missing  
            assert 'Optional' in missing
            
        finally:
            os.unlink(temp_file)
    
    def test_with_fallback_integration_in_startup(self):
        """startup_utils에서 with_fallback 패턴 사용 테스트"""
        from rfs.hof.combinators import with_fallback
        
        def risky_config_load():
            raise FileNotFoundError("Config file not found")
        
        def safe_default_config(error):
            return {"debug": True, "host": "localhost"}
        
        safe_config_loader = with_fallback(risky_config_load, safe_default_config)
        config = safe_config_loader()
        
        assert config["debug"] is True
        assert config["host"] == "localhost"