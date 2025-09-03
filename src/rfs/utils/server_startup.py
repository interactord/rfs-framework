"""
RFS Framework - 통합 서버 시작 유틸리티

PR에서 발견된 모든 서버 시작 오류 패턴들을 해결하는 원스톱 솔루션을 제공합니다.

주요 기능:
- 원클릭 서버 검증 및 수정
- 설정 기반 자동 처리
- 종합적인 시작 준비 상태 확인
- 프로젝트별 커스터마이제이션 지원

이 모듈은 다른 프로젝트에서 RFS Framework를 사용할 때 
PR에서 발견된 것과 같은 문제들이 발생하지 않도록 예방합니다.
"""

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..core.result import Failure, Result, Success
from ..core.enhanced_logging import get_logger
from ..hof.core import pipe
from ..hof.combinators import with_fallback
from ..hof.async_hof import async_with_fallback
from ..web.startup_utils import (
    validate_imports,
    safe_import,
    check_missing_types,
    resolve_import_path,
    check_dependencies,
    validate_server_startup,
    auto_fix_missing_imports,
    create_startup_report
)

logger = get_logger(__name__)


@dataclass
class ServerStartupConfig:
    """
    서버 시작 설정 클래스
    
    프로젝트별로 커스터마이즈할 수 있는 모든 설정들을 포함합니다.
    """
    # 기본 설정
    project_root: str
    project_name: str = "RFS Project"
    
    # 모듈 검증 설정
    core_modules: List[str] = field(default_factory=lambda: [])
    optional_modules: List[str] = field(default_factory=lambda: [])
    
    # 타입 검증 설정
    required_types: List[str] = field(default_factory=lambda: ['Dict', 'List', 'Optional', 'Union', 'Any'])
    check_type_imports: bool = True
    auto_fix_imports: bool = False
    
    # 의존성 설정
    required_packages: List[str] = field(default_factory=lambda: ['rfs'])
    optional_packages: List[str] = field(default_factory=lambda: [])
    
    # 검증 설정
    strict_mode: bool = False  # True면 모든 검사 통과해야 함
    enable_auto_fix: bool = False  # True면 자동 수정 시도
    
    # 로깅 설정
    verbose_logging: bool = True
    create_report: bool = True


class ServerStartupManager:
    """
    서버 시작 관리자 클래스
    
    모든 서버 시작 관련 작업을 통합적으로 관리합니다.
    """
    
    def __init__(self, config: ServerStartupConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{config.project_name}")
        self.validation_results = {}
        
    def validate_all(self) -> Result[Dict[str, Any], str]:
        """
        모든 검증을 순차적으로 실행합니다.
        
        Returns:
            Result[Dict[str, Any], str]: 종합 검증 결과
        """
        try:
            # 함수형 파이프라인으로 검증 단계들을 연결
            validation_pipeline = pipe(
                self._validate_core_modules,
                lambda result: result.bind(self._validate_optional_modules),
                lambda result: result.bind(self._validate_dependencies),
                lambda result: result.bind(self._validate_type_imports),
                lambda result: result.bind(self._finalize_validation)
            )
            
            # 초기 상태로 파이프라인 시작
            initial_state = Success({
                'modules': {'core': {}, 'optional': {}},
                'dependencies': {},
                'types': {},
                'overall_status': True,
                'errors': [],
                'warnings': []
            })
            
            result = validation_pipeline(initial_state)
            
            if result.is_success():
                self.validation_results = result.unwrap()
                if self.config.verbose_logging:
                    self.logger.info("모든 검증이 완료되었습니다.")
                    
                if self.config.create_report:
                    report = create_startup_report(self.validation_results)
                    self.logger.info(f"\n{report}")
                
            return result
            
        except Exception as e:
            return Failure(f"검증 중 예외 발생: {str(e)}")
    
    def _validate_core_modules(self, state: Result[Dict[str, Any], str]) -> Result[Dict[str, Any], str]:
        """핵심 모듈들을 검증합니다."""
        if state.is_failure():
            return state
            
        current_state = state.unwrap()
        
        for module in self.config.core_modules:
            result = safe_import(module)
            success = result.is_success()
            current_state['modules']['core'][module] = success
            
            if not success:
                error_msg = f"핵심 모듈 import 실패: {module} - {result.unwrap_error()}"
                current_state['errors'].append(error_msg)
                if self.config.strict_mode:
                    current_state['overall_status'] = False
                self.logger.error(error_msg)
            else:
                if self.config.verbose_logging:
                    self.logger.info(f"핵심 모듈 검증 성공: {module}")
        
        return Success(current_state)
    
    def _validate_optional_modules(self, state: Result[Dict[str, Any], str]) -> Result[Dict[str, Any], str]:
        """선택적 모듈들을 검증합니다."""
        if state.is_failure():
            return state
            
        current_state = state.unwrap()
        
        for module in self.config.optional_modules:
            result = safe_import(module)
            success = result.is_success()
            current_state['modules']['optional'][module] = success
            
            if not success:
                warning_msg = f"선택적 모듈 사용 불가: {module} - {result.unwrap_error()}"
                current_state['warnings'].append(warning_msg)
                if self.config.verbose_logging:
                    self.logger.warning(warning_msg)
            else:
                if self.config.verbose_logging:
                    self.logger.info(f"선택적 모듈 검증 성공: {module}")
        
        return Success(current_state)
    
    def _validate_dependencies(self, state: Result[Dict[str, Any], str]) -> Result[Dict[str, Any], str]:
        """의존성 패키지들을 검증합니다."""
        if state.is_failure():
            return state
            
        current_state = state.unwrap()
        
        # 필수 패키지 검증
        if self.config.required_packages:
            dep_result = check_dependencies(self.config.required_packages)
            if dep_result.is_success():
                current_state['dependencies']['required'] = dep_result.unwrap()
                if self.config.verbose_logging:
                    packages = dep_result.unwrap()
                    for pkg, version in packages.items():
                        self.logger.info(f"필수 패키지 확인: {pkg} v{version}")
            else:
                error_msg = f"필수 의존성 체크 실패: {dep_result.unwrap_error()}"
                current_state['errors'].append(error_msg)
                if self.config.strict_mode:
                    current_state['overall_status'] = False
                self.logger.error(error_msg)
        
        # 선택적 패키지 검증
        if self.config.optional_packages:
            optional_packages = {}
            for package in self.config.optional_packages:
                result = check_dependencies([package])
                if result.is_success():
                    pkg_info = result.unwrap()
                    optional_packages.update(pkg_info)
                    if self.config.verbose_logging:
                        for pkg, version in pkg_info.items():
                            self.logger.info(f"선택적 패키지 확인: {pkg} v{version}")
                else:
                    if self.config.verbose_logging:
                        self.logger.warning(f"선택적 패키지 사용 불가: {package}")
            
            current_state['dependencies']['optional'] = optional_packages
        
        return Success(current_state)
    
    def _validate_type_imports(self, state: Result[Dict[str, Any], str]) -> Result[Dict[str, Any], str]:
        """타입 import들을 검증합니다."""
        if state.is_failure() or not self.config.check_type_imports:
            return state
            
        current_state = state.unwrap()
        type_check_results = {}
        
        try:
            # 프로젝트 루트에서 Python 파일들을 찾아서 검사
            project_path = Path(self.config.project_root)
            python_files = list(project_path.rglob("*.py"))
            
            for py_file in python_files:
                # __pycache__ 등 무시할 파일들 스킵
                if '__pycache__' in str(py_file) or '.git' in str(py_file):
                    continue
                
                result = check_missing_types(str(py_file))
                if result.is_success():
                    missing_types = result.unwrap()
                    if missing_types:
                        type_check_results[str(py_file)] = missing_types
                        warning_msg = f"누락된 타입 import 발견: {py_file.name} - {missing_types}"
                        current_state['warnings'].append(warning_msg)
                        
                        # 자동 수정 시도 (설정된 경우)
                        if self.config.enable_auto_fix and self.config.auto_fix_imports:
                            fix_result = auto_fix_missing_imports(str(py_file), dry_run=False)
                            if fix_result.is_success():
                                changes = fix_result.unwrap()
                                self.logger.info(f"자동 수정 완료: {py_file.name} - {changes}")
                            else:
                                self.logger.warning(f"자동 수정 실패: {py_file.name} - {fix_result.unwrap_error()}")
                        else:
                            if self.config.verbose_logging:
                                self.logger.warning(warning_msg)
                else:
                    if self.config.verbose_logging:
                        self.logger.warning(f"타입 체크 실패: {py_file.name} - {result.unwrap_error()}")
            
            current_state['types'] = type_check_results
            
        except Exception as e:
            error_msg = f"타입 import 검증 중 오류: {str(e)}"
            current_state['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return Success(current_state)
    
    def _finalize_validation(self, state: Result[Dict[str, Any], str]) -> Result[Dict[str, Any], str]:
        """검증 결과를 최종 정리합니다."""
        if state.is_failure():
            return state
            
        current_state = state.unwrap()
        
        # 전체 상태 결정
        has_critical_errors = len(current_state['errors']) > 0
        
        if self.config.strict_mode:
            current_state['overall_status'] = not has_critical_errors
        else:
            # 관대한 모드에서는 핵심 모듈만 통과하면 OK
            core_modules_ok = all(current_state['modules']['core'].values())
            current_state['overall_status'] = core_modules_ok and not has_critical_errors
        
        # 통계 정보 추가
        current_state['stats'] = {
            'total_modules_checked': len(self.config.core_modules) + len(self.config.optional_modules),
            'core_modules_passed': sum(current_state['modules']['core'].values()),
            'optional_modules_passed': sum(current_state['modules']['optional'].values()),
            'dependencies_found': len(current_state.get('dependencies', {}).get('required', {})),
            'type_issues_found': sum(len(types) for types in current_state.get('types', {}).values()),
            'total_errors': len(current_state['errors']),
            'total_warnings': len(current_state['warnings'])
        }
        
        return Success(current_state)
    
    async def validate_all_async(self) -> Result[Dict[str, Any], str]:
        """
        비동기 방식으로 모든 검증을 실행합니다.
        
        Returns:
            Result[Dict[str, Any], str]: 종합 검증 결과
        """
        # 비동기 fallback 패턴을 사용한 안전한 검증
        safe_validation = async_with_fallback(
            lambda: asyncio.get_event_loop().run_in_executor(None, self.validate_all),
            lambda error: asyncio.sleep(0.1).then(lambda: Failure(f"비동기 검증 실패: {str(error)}"))
        )
        
        try:
            # 동기 validate_all을 executor에서 실행
            result = await asyncio.get_event_loop().run_in_executor(None, self.validate_all)
            return result
        except Exception as e:
            return Failure(f"비동기 검증 중 오류 발생: {str(e)}")


# ==================== 편의 함수들 ====================

def quick_server_check(project_root: str, **kwargs) -> Result[bool, str]:
    """
    빠른 서버 준비 상태 체크
    
    Args:
        project_root: 프로젝트 루트 경로
        **kwargs: ServerStartupConfig에 전달할 추가 설정
        
    Returns:
        Result[bool, str]: 준비 완료 여부
    """
    try:
        config = ServerStartupConfig(
            project_root=project_root,
            strict_mode=False,  # 빠른 체크이므로 관대하게
            verbose_logging=False,  # 로그 최소화
            create_report=False,
            **kwargs
        )
        
        manager = ServerStartupManager(config)
        result = manager.validate_all()
        
        if result.is_success():
            validation_data = result.unwrap()
            return Success(validation_data['overall_status'])
        else:
            return Failure(result.unwrap_error())
            
    except Exception as e:
        return Failure(f"빠른 체크 중 오류: {str(e)}")


async def quick_server_check_async(project_root: str, **kwargs) -> Result[bool, str]:
    """
    비동기 빠른 서버 준비 상태 체크
    """
    try:
        config = ServerStartupConfig(
            project_root=project_root,
            strict_mode=False,
            verbose_logging=False,
            create_report=False,
            **kwargs
        )
        
        manager = ServerStartupManager(config)
        result = await manager.validate_all_async()
        
        if result.is_success():
            validation_data = result.unwrap()
            return Success(validation_data['overall_status'])
        else:
            return Failure(result.unwrap_error())
            
    except Exception as e:
        return Failure(f"비동기 빠른 체크 중 오류: {str(e)}")


def create_default_config(project_root: str) -> ServerStartupConfig:
    """
    RFS Framework를 사용하는 일반적인 프로젝트의 기본 설정을 생성합니다.
    
    Args:
        project_root: 프로젝트 루트 경로
        
    Returns:
        ServerStartupConfig: 기본 설정
    """
    return ServerStartupConfig(
        project_root=project_root,
        project_name="RFS Project",
        core_modules=[
            'rfs.core.result',
            'rfs.core.config', 
            'rfs.hof'
        ],
        optional_modules=[
            'rfs.web.server',
            'rfs.reactive',
            'rfs.async_tasks'
        ],
        required_types=['Dict', 'List', 'Optional', 'Union', 'Any', 'Callable'],
        required_packages=['rfs'],
        optional_packages=['fastapi', 'uvicorn', 'pydantic'],
        strict_mode=False,
        enable_auto_fix=True,
        auto_fix_imports=True,
        verbose_logging=True,
        create_report=True
    )


def validate_rfs_project(project_root: str, auto_fix: bool = False) -> Result[str, str]:
    """
    RFS 프로젝트를 위한 원클릭 검증 및 수정
    
    Args:
        project_root: 프로젝트 루트 경로  
        auto_fix: 자동 수정 허용 여부
        
    Returns:
        Result[str, str]: 성공 시 검증 보고서, 실패 시 에러 메시지
    """
    try:
        config = create_default_config(project_root)
        config.enable_auto_fix = auto_fix
        config.auto_fix_imports = auto_fix
        
        manager = ServerStartupManager(config)
        result = manager.validate_all()
        
        if result.is_success():
            validation_data = result.unwrap()
            report = create_startup_report(validation_data)
            
            if validation_data['overall_status']:
                return Success(f"✅ RFS 프로젝트 검증 완료!\n\n{report}")
            else:
                return Success(f"⚠️ RFS 프로젝트 검증 완료 (일부 문제 발견)\n\n{report}")
        else:
            return Failure(f"❌ 검증 실패: {result.unwrap_error()}")
            
    except Exception as e:
        return Failure(f"검증 중 예외 발생: {str(e)}")


# ==================== CLI 지원 ====================

def run_startup_validator(args: List[str] = None) -> None:
    """
    CLI에서 서버 시작 검증기를 실행합니다.
    
    Args:
        args: CLI 인수들 (None이면 sys.argv 사용)
    """
    import argparse
    import sys
    
    if args is None:
        args = sys.argv[1:]
    
    parser = argparse.ArgumentParser(
        description="RFS Framework 서버 시작 검증 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예제:
  python -m rfs.utils.server_startup /path/to/project
  python -m rfs.utils.server_startup /path/to/project --auto-fix
  python -m rfs.utils.server_startup /path/to/project --strict
        """
    )
    
    parser.add_argument('project_root', help='프로젝트 루트 디렉토리 경로')
    parser.add_argument('--auto-fix', action='store_true', help='자동 수정 허용')
    parser.add_argument('--strict', action='store_true', help='엄격 모드 (모든 검사 통과 필요)')
    parser.add_argument('--quiet', action='store_true', help='최소 출력 모드')
    parser.add_argument('--no-report', action='store_true', help='보고서 생성 안함')
    
    parsed_args = parser.parse_args(args)
    
    try:
        result = validate_rfs_project(
            parsed_args.project_root,
            auto_fix=parsed_args.auto_fix
        )
        
        if result.is_success():
            report = result.unwrap()
            if not parsed_args.quiet:
                print(report)
            sys.exit(0)
        else:
            error = result.unwrap_error()
            if not parsed_args.quiet:
                print(f"오류: {error}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        if not parsed_args.quiet:
            print("\n검증이 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        if not parsed_args.quiet:
            print(f"예상치 못한 오류: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    run_startup_validator()