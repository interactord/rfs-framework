#!/usr/bin/env python3
"""
RFS Framework 규칙 검증 스크립트

모든 RFS Framework 필수 규칙을 검증하고 위반 사항을 보고합니다.
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Dict, NamedTuple
from dataclasses import dataclass
import argparse


class Violation(NamedTuple):
    """규칙 위반 정보"""
    file_path: str
    line_number: int
    rule_name: str
    message: str
    severity: str  # 'error', 'warning', 'info'


@dataclass
class ValidationResult:
    """검증 결과"""
    total_files: int = 0
    violations: List[Violation] = None
    
    def __post_init__(self):
        if self.violations is None:
            self.violations = []


class RFSRuleValidator:
    """RFS Framework 규칙 검증기"""
    
    def __init__(self, project_root: Path):
        """
        검증기를 초기화합니다.
        
        Args:
            project_root: 프로젝트 루트 디렉토리
        """
        self.project_root = project_root
        self.src_path = project_root / "src"
        self.tests_path = project_root / "tests"
    
    def validate_all_rules(self) -> ValidationResult:
        """
        모든 RFS Framework 규칙을 검증합니다.
        
        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult()
        python_files = list(self._find_python_files())
        result.total_files = len(python_files)
        
        for file_path in python_files:
            try:
                # 각 규칙별 검증 실행
                result.violations.extend(self._check_result_pattern(file_path))
                result.violations.extend(self._check_korean_comments(file_path))
                result.violations.extend(self._check_immutability(file_path))
                result.violations.extend(self._check_pattern_matching(file_path))
                result.violations.extend(self._check_type_hints(file_path))
                result.violations.extend(self._check_framework_usage(file_path))
            except Exception as e:
                result.violations.append(
                    Violation(
                        file_path=str(file_path),
                        line_number=0,
                        rule_name="파일 처리 오류",
                        message=f"파일 처리 중 오류 발생: {e}",
                        severity="error"
                    )
                )
        
        return result
    
    def _find_python_files(self):
        """Python 파일을 찾습니다."""
        for path in [self.src_path, self.tests_path]:
            if path.exists():
                yield from path.rglob("*.py")
    
    def _check_result_pattern(self, file_path: Path) -> List[Violation]:
        """Result 패턴 사용을 검증합니다."""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except (UnicodeDecodeError, SyntaxError):
            return [Violation(
                file_path=str(file_path),
                line_number=0,
                rule_name="Result 패턴",
                message="파일을 파싱할 수 없습니다",
                severity="error"
            )]
        
        # raise 문 검출
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                # 테스트 파일은 예외
                if "test" in str(file_path).lower():
                    continue
                
                violations.append(
                    Violation(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        rule_name="Result 패턴",
                        message="예외를 던지는 대신 Result 패턴을 사용해야 합니다",
                        severity="error"
                    )
                )
        
        # Result import 확인 (비즈니스 로직 파일)
        if self._is_business_logic_file(file_path):
            has_result_import = any(
                isinstance(node, ast.ImportFrom) and 
                node.module and 
                "rfs.core.result" in node.module
                for node in ast.walk(tree)
            )
            
            if not has_result_import:
                violations.append(
                    Violation(
                        file_path=str(file_path),
                        line_number=1,
                        rule_name="Result 패턴",
                        message="비즈니스 로직 파일에서 Result import가 없습니다",
                        severity="warning"
                    )
                )
        
        return violations
    
    def _check_korean_comments(self, file_path: Path) -> List[Violation]:
        """한글 주석 사용을 검증합니다."""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return [Violation(
                file_path=str(file_path),
                line_number=0,
                rule_name="한글 주석",
                message="UTF-8 인코딩이 필요합니다",
                severity="error"
            )]
        
        for line_no, line in enumerate(lines, 1):
            # 주석 찾기
            if '#' in line and not line.strip().startswith('#!'):
                comment_part = line.split('#', 1)[1].strip()
                
                # 빈 주석 또는 코드 주석처리는 제외
                if not comment_part or comment_part.startswith((' TODO:', ' FIXME:', ' NOTE:')):
                    continue
                
                # URL이나 기술 용어 제외
                if any(keyword in comment_part for keyword in [
                    'http', 'https', 'www.', '.com', '.org', 
                    'TODO', 'FIXME', 'XXX', 'HACK'
                ]):
                    continue
                
                # 한글이 포함되어 있는지 확인
                if not any(ord(c) > 127 for c in comment_part):
                    # 기술 용어 위주의 짧은 주석은 경고만
                    severity = "warning" if len(comment_part.split()) <= 3 else "error"
                    
                    violations.append(
                        Violation(
                            file_path=str(file_path),
                            line_number=line_no,
                            rule_name="한글 주석",
                            message=f"한글 주석을 사용해야 합니다: '{comment_part}'",
                            severity=severity
                        )
                    )
        
        # Docstring 검증
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except:
            return violations
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                docstring = ast.get_docstring(node)
                if docstring and not any(ord(c) > 127 for c in docstring):
                    violations.append(
                        Violation(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            rule_name="한글 주석",
                            message=f"{node.name}의 docstring이 한글이어야 합니다",
                            severity="warning"
                        )
                    )
        
        return violations
    
    def _check_immutability(self, file_path: Path) -> List[Violation]:
        """불변성 규칙을 검증합니다."""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except:
            return violations
        
        # 직접적인 리스트/딕셔너리 수정 패턴 찾기
        for node in ast.walk(tree):
            # list.append(), dict[key] = value 등
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr in ['append', 'extend', 'insert', 'remove', 'pop', 'clear']):
                    violations.append(
                        Violation(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            rule_name="불변성",
                            message=f"리스트를 직접 수정하는 대신 새로운 리스트를 생성하세요: {node.func.attr}()",
                            severity="warning"
                        )
                    )
            
            # dict[key] = value
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Subscript):
                        violations.append(
                            Violation(
                                file_path=str(file_path),
                                line_number=node.lineno,
                                rule_name="불변성",
                                message="딕셔너리를 직접 수정하는 대신 스프레드 연산자를 사용하세요",
                                severity="warning"
                            )
                        )
        
        # dataclass frozen 확인
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                has_dataclass = False
                has_frozen = False
                
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == 'dataclass':
                        has_dataclass = True
                    elif isinstance(decorator, ast.Call):
                        if (isinstance(decorator.func, ast.Name) and 
                            decorator.func.id == 'dataclass'):
                            has_dataclass = True
                            # frozen=True 확인
                            for keyword in decorator.keywords:
                                if keyword.arg == 'frozen' and isinstance(keyword.value, ast.Constant):
                                    has_frozen = keyword.value.value
                
                if has_dataclass and not has_frozen:
                    violations.append(
                        Violation(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            rule_name="불변성",
                            message=f"dataclass {node.name}에 frozen=True를 추가하세요",
                            severity="warning"
                        )
                    )
        
        return violations
    
    def _check_pattern_matching(self, file_path: Path) -> List[Violation]:
        """패턴 매칭 사용을 권장합니다."""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except:
            return violations
        
        # 긴 if-elif 체인 찾기
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                elif_count = 0
                current = node
                
                while hasattr(current, 'orelse') and current.orelse:
                    if (len(current.orelse) == 1 and 
                        isinstance(current.orelse[0], ast.If)):
                        elif_count += 1
                        current = current.orelse[0]
                    else:
                        break
                
                if elif_count >= 3:  # 3개 이상의 elif
                    violations.append(
                        Violation(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            rule_name="패턴 매칭",
                            message=f"긴 if-elif 체인({elif_count + 1}개)은 match 문으로 대체를 고려하세요",
                            severity="info"
                        )
                    )
        
        return violations
    
    def _check_type_hints(self, file_path: Path) -> List[Violation]:
        """타입 힌트를 검증합니다."""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except:
            return violations
        
        # public 함수의 타입 힌트 확인
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # private 함수는 제외
                if node.name.startswith('_'):
                    continue
                
                # 테스트 함수는 제외
                if node.name.startswith('test_'):
                    continue
                
                # 반환 타입 확인
                if node.returns is None:
                    violations.append(
                        Violation(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            rule_name="타입 힌트",
                            message=f"함수 {node.name}에 반환 타입 힌트가 필요합니다",
                            severity="warning"
                        )
                    )
                
                # 매개변수 타입 확인
                for arg in node.args.args:
                    if arg.arg == 'self' or arg.arg == 'cls':
                        continue
                    if arg.annotation is None:
                        violations.append(
                            Violation(
                                file_path=str(file_path),
                                line_number=node.lineno,
                                rule_name="타입 힌트",
                                message=f"함수 {node.name}의 매개변수 {arg.arg}에 타입 힌트가 필요합니다",
                                severity="warning"
                            )
                        )
        
        return violations
    
    def _check_framework_usage(self, file_path: Path) -> List[Violation]:
        """RFS Framework 사용을 검증합니다."""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return violations
        
        # 커스텀 구현 대신 Framework 기능 사용 권장
        problematic_patterns = [
            (r'def\s+validate_\w+', 'RFS Framework의 검증 유틸리티 사용을 고려하세요'),
            (r'class\s+\w*Config\w*', 'RFS Framework의 Config 시스템 사용을 고려하세요'),
            (r'def\s+retry_\w+', 'RFS Framework의 재시도 기능 사용을 고려하세요'),
        ]
        
        lines = content.split('\n')
        for line_no, line in enumerate(lines, 1):
            for pattern, message in problematic_patterns:
                if re.search(pattern, line):
                    violations.append(
                        Violation(
                            file_path=str(file_path),
                            line_number=line_no,
                            rule_name="Framework 사용",
                            message=message,
                            severity="info"
                        )
                    )
        
        return violations
    
    def _is_business_logic_file(self, file_path: Path) -> bool:
        """비즈니스 로직 파일인지 확인합니다."""
        # 테스트, 설정, __init__ 파일 제외
        if any(part in str(file_path).lower() for part in ['test', 'config', '__init__']):
            return False
        
        # src 디렉토리 내의 파일
        return 'src' in str(file_path)


def format_violations(result: ValidationResult, show_warnings: bool = True, show_info: bool = False) -> str:
    """위반 사항을 포맷팅합니다."""
    if not result.violations:
        return "✅ 모든 RFS Framework 규칙을 준수합니다!"
    
    # 심각도별로 분류
    errors = [v for v in result.violations if v.severity == 'error']
    warnings = [v for v in result.violations if v.severity == 'warning']
    infos = [v for v in result.violations if v.severity == 'info']
    
    output = []
    
    if errors:
        output.append(f"❌ 오류 ({len(errors)}개):")
        for violation in errors:
            output.append(f"  {violation.file_path}:{violation.line_number} - {violation.rule_name}: {violation.message}")
    
    if warnings and show_warnings:
        output.append(f"\n⚠️  경고 ({len(warnings)}개):")
        for violation in warnings:
            output.append(f"  {violation.file_path}:{violation.line_number} - {violation.rule_name}: {violation.message}")
    
    if infos and show_info:
        output.append(f"\nℹ️  정보 ({len(infos)}개):")
        for violation in infos:
            output.append(f"  {violation.file_path}:{violation.line_number} - {violation.rule_name}: {violation.message}")
    
    # 요약
    output.append(f"\n📊 요약:")
    output.append(f"  전체 파일: {result.total_files}개")
    output.append(f"  오류: {len(errors)}개")
    if show_warnings:
        output.append(f"  경고: {len(warnings)}개")
    if show_info:
        output.append(f"  정보: {len(infos)}개")
    
    return "\n".join(output)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="RFS Framework 규칙 검증 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python validate_rfs_rules.py                    # 기본 검증
  python validate_rfs_rules.py --no-warnings      # 경고 숨김
  python validate_rfs_rules.py --show-info        # 정보 표시
  python validate_rfs_rules.py --strict           # 엄격 모드 (경고도 실패)
        """
    )
    
    parser.add_argument(
        '--project-root',
        type=Path,
        default=Path.cwd(),
        help='프로젝트 루트 디렉토리 (기본값: 현재 디렉토리)'
    )
    
    parser.add_argument(
        '--no-warnings',
        action='store_true',
        help='경고 메시지 숨김'
    )
    
    parser.add_argument(
        '--show-info',
        action='store_true',
        help='정보 메시지 표시'
    )
    
    parser.add_argument(
        '--strict',
        action='store_true',
        help='엄격 모드: 경고도 실패로 처리'
    )
    
    args = parser.parse_args()
    
    # 검증 실행
    validator = RFSRuleValidator(args.project_root)
    result = validator.validate_all_rules()
    
    # 결과 출력
    show_warnings = not args.no_warnings
    output = format_violations(result, show_warnings, args.show_info)
    print(output)
    
    # 종료 코드 결정
    errors = [v for v in result.violations if v.severity == 'error']
    warnings = [v for v in result.violations if v.severity == 'warning']
    
    if errors:
        sys.exit(1)  # 오류가 있으면 실패
    elif warnings and args.strict:
        sys.exit(1)  # 엄격 모드에서 경고가 있으면 실패
    else:
        sys.exit(0)  # 성공


if __name__ == '__main__':
    main()