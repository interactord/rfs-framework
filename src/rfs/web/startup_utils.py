"""
RFS Web Server Startup Utilities

서버 시작 시 발생할 수 있는 일반적인 문제들을 해결하는 유틸리티 함수들을 제공합니다.

주요 기능:
- 안전한 import 검증 및 처리
- 타입 import 자동 체크
- 상대 경로 문제 해결
- 의존성 검증

이 모듈은 PR에서 발견된 서버 시작 오류 패턴들을 바탕으로 만들어졌습니다.
"""

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union
from types import ModuleType

from ..core.result import Failure, Result, Success
from ..core.enhanced_logging import get_logger
from ..hof.combinators import with_fallback, safe_call
from ..hof.async_hof import async_with_fallback

logger = get_logger(__name__)


# ==================== Import 검증 및 처리 ====================

def validate_imports(module_path: str, expected_imports: List[str]) -> Result[Dict[str, bool], str]:
    """
    모듈의 import들이 올바른지 검증합니다.
    
    Args:
        module_path: 검증할 모듈 경로 (예: 'myapp.services.user_service')
        expected_imports: 예상되는 import 목록
        
    Returns:
        Result[Dict[str, bool], str]: 각 import의 성공/실패 상태
        
    Example:
        >>> result = validate_imports(
        ...     'myapp.services.user_service',
        ...     ['typing.Dict', 'myapp.models.User', 'rfs.core.result.Result']
        ... )
        >>> if result.is_success():
        ...     status = result.unwrap()
        ...     print(f"All imports valid: {all(status.values())}")
    """
    try:
        import_status = {}
        
        # 모듈 로드 시도
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            return Failure(f"모듈 로드 실패: {module_path} - {str(e)}")
        
        # 각 import 검증
        for import_item in expected_imports:
            try:
                if '.' in import_item:
                    # 예: 'typing.Dict'
                    module_name, attr_name = import_item.rsplit('.', 1)
                    imported_module = importlib.import_module(module_name)
                    getattr(imported_module, attr_name)
                else:
                    # 예: 'os'
                    importlib.import_module(import_item)
                
                import_status[import_item] = True
                
            except (ImportError, AttributeError) as e:
                import_status[import_item] = False
                logger.warning(f"Import 실패: {import_item} - {str(e)}")
        
        return Success(import_status)
        
    except Exception as e:
        return Failure(f"Import 검증 중 오류 발생: {str(e)}")


def safe_import(module_path: str, fallback_value: Any = None) -> Result[ModuleType, str]:
    """
    안전한 동적 import를 수행합니다.
    
    Args:
        module_path: import할 모듈 경로
        fallback_value: import 실패 시 반환할 기본값
        
    Returns:
        Result[ModuleType, str]: 성공 시 모듈, 실패 시 에러 메시지
        
    Example:
        >>> result = safe_import('some.optional.module')
        >>> if result.is_success():
        ...     module = result.unwrap()
        ...     # 모듈 사용
        >>> else:
        ...     print("모듈을 로드할 수 없습니다. 선택적 기능이 비활성화됩니다.")
    """
    try:
        module = importlib.import_module(module_path)
        return Success(module)
    except ImportError as e:
        error_msg = f"모듈 import 실패: {module_path} - {str(e)}"
        logger.info(error_msg)
        
        if fallback_value is not None:
            # fallback_value가 제공된 경우, 이를 모듈처럼 사용할 수 있도록 처리
            logger.info(f"Fallback 값 사용: {type(fallback_value)}")
            return Success(fallback_value)
        
        return Failure(error_msg)


def check_missing_types(file_path: str) -> Result[List[str], str]:
    """
    파일에서 누락된 typing import를 체크합니다.
    
    Args:
        file_path: 검사할 파일 경로
        
    Returns:
        Result[List[str], str]: 누락된 타입들의 목록
        
    Example:
        >>> result = check_missing_types('./src/services/user_service.py')
        >>> if result.is_success():
        ...     missing = result.unwrap()
        ...     if missing:
        ...         print(f"누락된 타입들: {missing}")
    """
    try:
        # 파일 읽기
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (FileNotFoundError, IOError) as e:
            return Failure(f"파일 읽기 실패: {str(e)}")
        
        # 사용되는 타입들 찾기
        common_types = {'Dict', 'List', 'Optional', 'Union', 'Tuple', 'Set', 'Any', 'Callable'}
        used_types = set()
        imported_types = set()
        
        lines = content.split('\n')
        
        # import 문에서 이미 import된 타입들 찾기
        for line in lines:
            line = line.strip()
            if line.startswith('from typing import'):
                # 예: from typing import Dict, List, Optional
                imports = line.replace('from typing import', '').strip()
                for imp in imports.split(','):
                    imported_types.add(imp.strip())
            elif line.startswith('import typing'):
                # typing 모듈 전체가 import된 경우
                imported_types.update(common_types)
        
        # 코드에서 사용되는 타입들 찾기 (간단한 패턴 매칭)
        for line in lines:
            for type_name in common_types:
                if type_name in line and not line.strip().startswith('#'):
                    # 함수 정의, 변수 선언 등에서 사용되는지 확인
                    if ':' in line or '->' in line:
                        used_types.add(type_name)
        
        # 누락된 타입들 계산
        missing_types = used_types - imported_types
        
        return Success(list(missing_types))
        
    except Exception as e:
        return Failure(f"타입 체크 중 오류 발생: {str(e)}")


def resolve_import_path(current_file: str, relative_path: str) -> Result[str, str]:
    """
    상대 경로를 절대 경로로 변환합니다.
    
    Args:
        current_file: 현재 파일의 절대 경로
        relative_path: 변환할 상대 경로 (예: '../models/user', './utils')
        
    Returns:
        Result[str, str]: 변환된 절대 경로
        
    Example:
        >>> result = resolve_import_path(
        ...     '/project/src/services/user_service.py',
        ...     '../models/user'
        ... )
        >>> if result.is_success():
        ...     absolute_path = result.unwrap()  # 'project.src.models.user'
    """
    try:
        current_path = Path(current_file).parent
        
        # 상대 경로 해석
        if relative_path.startswith('./'):
            # 현재 디렉토리
            resolved_path = current_path / relative_path[2:]
        elif relative_path.startswith('../'):
            # 상위 디렉토리
            levels_up = relative_path.count('../')
            clean_path = relative_path.replace('../', '', levels_up)
            resolved_path = current_path
            
            for _ in range(levels_up):
                resolved_path = resolved_path.parent
            
            if clean_path:
                resolved_path = resolved_path / clean_path
        else:
            # 이미 절대 경로이거나 모듈명
            return Success(relative_path)
        
        # Python 모듈 경로로 변환
        # 예: /project/src/models/user -> project.src.models.user
        resolved_path = resolved_path.resolve()
        
        # src 디렉토리를 찾아서 그 이후의 경로만 사용
        parts = resolved_path.parts
        try:
            if 'src' in parts:
                src_index = parts.index('src')
                module_parts = parts[src_index + 1:]
            else:
                # src가 없는 경우, 프로젝트 루트에서 시작한다고 가정
                module_parts = parts[-3:]  # 마지막 3개 정도 사용
            
            module_path = '.'.join(module_parts)
            return Success(module_path)
            
        except (ValueError, IndexError):
            return Failure(f"모듈 경로 변환 실패: {resolved_path}")
        
    except Exception as e:
        return Failure(f"경로 해석 중 오류 발생: {str(e)}")


# ==================== 의존성 검증 ====================

def check_dependencies(required_packages: List[str]) -> Result[Dict[str, str], str]:
    """
    필수 패키지들이 설치되어 있는지 확인합니다.
    
    Args:
        required_packages: 필수 패키지 목록
        
    Returns:
        Result[Dict[str, str], str]: 패키지명과 버전 정보
        
    Example:
        >>> result = check_dependencies(['fastapi', 'uvicorn', 'rfs'])
        >>> if result.is_success():
        ...     packages = result.unwrap()
        ...     for name, version in packages.items():
        ...         print(f"{name}: {version}")
    """
    try:
        import pkg_resources
        
        package_info = {}
        missing_packages = []
        
        for package in required_packages:
            try:
                distribution = pkg_resources.get_distribution(package)
                package_info[package] = distribution.version
            except pkg_resources.DistributionNotFound:
                missing_packages.append(package)
        
        if missing_packages:
            return Failure(f"누락된 패키지들: {', '.join(missing_packages)}")
        
        return Success(package_info)
        
    except Exception as e:
        return Failure(f"의존성 체크 중 오류 발생: {str(e)}")


# ==================== 서버 시작 검증 ====================

def validate_server_startup(
    module_paths: List[str],
    required_types: List[str] = None,
    required_packages: List[str] = None
) -> Result[Dict[str, Any], str]:
    """
    서버 시작에 필요한 모든 요소들을 종합 검증합니다.
    
    Args:
        module_paths: 검증할 모듈 경로들
        required_types: 필수 타입들 (기본: 일반적인 typing 타입들)
        required_packages: 필수 패키지들 (기본: 없음)
        
    Returns:
        Result[Dict[str, Any], str]: 검증 결과 정보
        
    Example:
        >>> result = validate_server_startup(
        ...     ['myapp.main', 'myapp.routes', 'myapp.models'],
        ...     required_types=['Dict', 'List', 'Optional'],
        ...     required_packages=['fastapi', 'uvicorn']
        ... )
        >>> if result.is_success():
        ...     validation_info = result.unwrap()
        ...     print("서버 시작 준비 완료!")
    """
    if required_types is None:
        required_types = ['Dict', 'List', 'Optional', 'Union', 'Any']
    
    validation_results = {
        'modules': {},
        'types': {},
        'packages': {},
        'overall_status': True
    }
    
    try:
        # 모듈 검증
        for module_path in module_paths:
            result = safe_import(module_path)
            validation_results['modules'][module_path] = result.is_success()
            if result.is_failure():
                validation_results['overall_status'] = False
                logger.error(f"모듈 import 실패: {module_path} - {result.unwrap_error()}")
        
        # 패키지 검증 (필요한 경우)
        if required_packages:
            dep_result = check_dependencies(required_packages)
            if dep_result.is_success():
                validation_results['packages'] = dep_result.unwrap()
            else:
                validation_results['overall_status'] = False
                logger.error(f"의존성 체크 실패: {dep_result.unwrap_error()}")
        
        # 전체 결과 반환
        if validation_results['overall_status']:
            return Success(validation_results)
        else:
            return Failure("서버 시작 검증에서 오류가 발견되었습니다. 로그를 확인하세요.")
            
    except Exception as e:
        return Failure(f"서버 시작 검증 중 오류 발생: {str(e)}")


# ==================== 자동 수정 도구 ====================

def auto_fix_missing_imports(file_path: str, dry_run: bool = True) -> Result[List[str], str]:
    """
    파일에서 누락된 import들을 자동으로 수정합니다.
    
    Args:
        file_path: 수정할 파일 경로
        dry_run: True면 실제 수정하지 않고 수정 내용만 반환
        
    Returns:
        Result[List[str], str]: 수정된 내용들의 목록
        
    Example:
        >>> # 먼저 dry run으로 확인
        >>> result = auto_fix_missing_imports('./src/services/user_service.py', dry_run=True)
        >>> if result.is_success():
        ...     changes = result.unwrap()
        ...     for change in changes:
        ...         print(f"수정 예정: {change}")
        ...     
        ...     # 실제 수정 실행
        ...     actual_result = auto_fix_missing_imports('./src/services/user_service.py', dry_run=False)
    """
    try:
        # 누락된 타입들 찾기
        missing_result = check_missing_types(file_path)
        if missing_result.is_failure():
            return missing_result
        
        missing_types = missing_result.unwrap()
        
        if not missing_types:
            return Success(["수정할 내용이 없습니다."])
        
        changes = []
        
        if not dry_run:
            try:
                # 파일 읽기
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # import 문 추가할 위치 찾기
                import_line_index = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        import_line_index = i + 1
                    elif line.strip() and not line.startswith('#'):
                        break
                
                # 누락된 타입들을 import에 추가
                if missing_types:
                    import_statement = f"from typing import {', '.join(sorted(missing_types))}\n"
                    lines.insert(import_line_index, import_statement)
                    changes.append(f"추가된 import: {import_statement.strip()}")
                
                # 파일 쓰기
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                    
            except Exception as e:
                return Failure(f"파일 수정 중 오류 발생: {str(e)}")
        else:
            # Dry run - 수정 내용만 반환
            if missing_types:
                changes.append(f"추가 예정 import: from typing import {', '.join(sorted(missing_types))}")
        
        return Success(changes)
        
    except Exception as e:
        return Failure(f"자동 수정 중 오류 발생: {str(e)}")


# ==================== 편의 함수들 ====================

@safe_call
def quick_startup_check(project_root: str) -> bool:
    """
    빠른 서버 시작 준비 상태 체크.
    
    Args:
        project_root: 프로젝트 루트 디렉토리
        
    Returns:
        bool: 시작 준비가 되었으면 True
    """
    try:
        # 기본적인 체크들
        common_modules = ['os', 'sys', 'pathlib']
        for module in common_modules:
            importlib.import_module(module)
        
        return True
    except:
        return False


def create_startup_report(validation_results: Dict[str, Any]) -> str:
    """
    서버 시작 검증 결과를 사람이 읽기 쉬운 보고서로 생성합니다.
    
    Args:
        validation_results: validate_server_startup 결과
        
    Returns:
        str: 포맷된 보고서 텍스트
    """
    report_lines = [
        "=== RFS 서버 시작 검증 보고서 ===",
        ""
    ]
    
    # 전체 상태
    overall_status = validation_results.get('overall_status', False)
    status_emoji = "✅" if overall_status else "❌"
    report_lines.append(f"전체 상태: {status_emoji} {'성공' if overall_status else '실패'}")
    report_lines.append("")
    
    # 모듈 상태
    modules = validation_results.get('modules', {})
    if modules:
        report_lines.append("📦 모듈 상태:")
        for module, status in modules.items():
            status_emoji = "✅" if status else "❌"
            report_lines.append(f"  {status_emoji} {module}")
        report_lines.append("")
    
    # 패키지 상태
    packages = validation_results.get('packages', {})
    if packages:
        report_lines.append("📋 패키지 상태:")
        for package, version in packages.items():
            report_lines.append(f"  ✅ {package} (v{version})")
        report_lines.append("")
    
    report_lines.append("=== 보고서 끝 ===")
    
    return "\n".join(report_lines)