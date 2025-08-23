#!/usr/bin/env python3
"""
code_quality.py - 코드 품질 자동화 스크립트

V2 모듈 코드 품질 관리를 위한 통합 도구
"""
import subprocess
import sys
import json
import ast
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any
import argparse


class FunctionalProgrammingReporter:
    """함수형 프로그래밍 위반 상세 보고 및 수정 가이드"""
    
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
    
    def generate_fix_suggestions(self, violations: Dict[str, List[Dict[str, Any]]]) -> str:
        """각 위반에 대한 구체적인 수정 예시 생성"""
        output_lines = []
        output_lines.append("\n" + "="*60)
        output_lines.append("📝 함수형 프로그래밍 수정 가이드")
        output_lines.append("="*60)
        
        # 위반 유형별 수정 예시
        fix_examples = {
            'mutation_patterns': {
                'title': '딕셔너리 직접 수정',
                'before': 'self._metrics[\'hits\'] = self._metrics[\'hits\'] + 1',
                'after': 'self._metrics = {**self._metrics, \'hits\': self._metrics[\'hits\'] + 1}'
            },
            'dict_mutation': {
                'title': 'dict.update() 사용',
                'before': 'merged_info.update(result.enhanced_info)',
                'after': 'merged_info = {**merged_info, **result.enhanced_info}'
            },
            'imperative_loops': {
                'title': 'for 루프 + append 패턴',
                'before': '''result = []
for item in items:
    if condition(item):
        result.append(transform(item))''',
                'after': 'result = list(map(transform, filter(condition, items)))'
            },
            'global_variables': {
                'title': 'global 키워드 사용',
                'before': '''global counter
counter += 1''',
                'after': '''def increment(counter: int) -> int:
    return counter + 1'''
            }
        }
        
        # 파일별 수정 우선순위 결정
        priority_files = self._prioritize_files(violations)
        
        output_lines.append("\n🎯 수정 우선순위:")
        output_lines.append("1. Mock 파일들 (테스트 코드, 위험도 낮음)")
        output_lines.append("2. Core 서비스 (비즈니스 로직, 신중히 수정)")
        output_lines.append("3. 기타 모듈 (점진적 리팩토링)\n")
        
        # 수정 예시
        output_lines.append("📚 패턴별 수정 예시:\n")
        for rule_type, example in fix_examples.items():
            output_lines.append(f"### {example['title']}")
            output_lines.append("❌ Before:")
            output_lines.append(f"```python\n{example['before']}\n```")
            output_lines.append("✅ After:")
            output_lines.append(f"```python\n{example['after']}\n```\n")
        
        return "\n".join(output_lines)
    
    def _prioritize_files(self, violations: Dict[str, List[Dict[str, Any]]]) -> List[Tuple[str, int]]:
        """파일별 수정 우선순위 결정"""
        priority_list = []
        
        for file_path, file_violations in violations.items():
            priority_score = 0
            
            # Mock 파일은 우선순위 높음 (안전함)
            if 'mock' in file_path.lower():
                priority_score = 100
            # Core 서비스는 중간 우선순위
            elif 'core' in file_path:
                priority_score = 50
            # 기타 파일은 낮은 우선순위
            else:
                priority_score = 10
            
            # 위반 개수도 고려
            priority_score += len(file_violations)
            
            priority_list.append((file_path, priority_score))
        
        # 우선순위 순으로 정렬
        priority_list.sort(key=lambda x: x[1], reverse=True)
        return priority_list
    
    def export_to_markdown(self, violations: Dict[str, List[Dict[str, Any]]]) -> str:
        """마크다운 형식으로 체크리스트 생성"""
        output_lines = []
        output_lines.append("# 함수형 프로그래밍 수정 체크리스트\n")
        output_lines.append(f"생성일: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        
        # 통계
        total_violations = sum(len(v) for v in violations.values())
        output_lines.append(f"## 📊 통계")
        output_lines.append(f"- 총 위반: {total_violations}개")
        output_lines.append(f"- 영향 파일: {len(violations)}개\n")
        
        # 파일별 체크리스트
        priority_files = self._prioritize_files(violations)
        
        output_lines.append("## 📋 수정 항목\n")
        
        for file_path, _ in priority_files:
            file_violations = violations[file_path]
            output_lines.append(f"### 📁 {file_path}")
            output_lines.append(f"위반 개수: {len(file_violations)}개\n")
            
            for violation in file_violations:
                output_lines.append(f"- [ ] **라인 {violation['line']}**: {violation['message']}")
                if violation.get('suggestion'):
                    output_lines.append(f"  - 💡 {violation['suggestion']}")
            output_lines.append("")
        
        return "\n".join(output_lines)


class FunctionalProgrammingChecker:
    """함수형 프로그래밍 규칙 검사기"""

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir

        # 검사 규칙들
        self.rules = {
            "isinstance_usage": self._check_isinstance_usage,
            "mutation_patterns": self._check_mutation_patterns,
            "imperative_loops": self._check_imperative_loops,
            "list_append_loops": self._check_list_append_loops,
            "dict_mutation": self._check_dict_mutation,
            "global_variables": self._check_global_variables,
            "map_filter_priority": self._check_map_filter_priority
        }

    def check_all_files(self) -> Dict[str, List[Dict[str, Any]]]:
        """모든 Python 파일에 대해 함수형 프로그래밍 규칙 검사"""
        violations = {}
        
        # 함수형 프로그래밍 검사에서 제외할 파일들
        excluded_files = {
            "app/services/v2/enhancers/functional/cloud_worker.py",  # 상태 관리 클래스
            "app/services/v2/enhancers/web_search.py",  # Generator 스트리밍 로직
            "app/services/v2/enhancers/functional/result.py",  # Early return 필요
            "app/services/v2/extractors/linkedin.py",  # 복잡한 텍스트 처리 로직
        }

        python_files = list(self.target_dir.rglob("*.py"))

        for file_path in python_files:
            # __pycache__, .pyc 파일 제외
            if "__pycache__" in str(file_path) or file_path.suffix == ".pyc":
                continue
            
            # 제외 파일 목록 확인
            relative_path = file_path.relative_to(self.target_dir.parent.parent.parent)
            if str(relative_path) in excluded_files:
                continue

            file_violations = self._check_file(file_path)
            if file_violations:
                violations[str(relative_path)] = file_violations

        return violations

    def _check_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """단일 파일 검사"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)

            # OrderedDict를 사용하는 파일은 검사에서 제외
            if 'OrderedDict' in content:
                return []

            violations = []

            # 각 규칙 적용
            for rule_name, rule_func in self.rules.items():
                rule_violations = rule_func(tree, content, file_path)
                violations.extend(rule_violations)

            return violations

        except (UnicodeDecodeError, SyntaxError):
            # 파싱할 수 없는 파일은 건너뛰기
            return []

    def _check_isinstance_usage(self, tree: ast.AST, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """isinstance() 사용 검사"""
        violations = []

        class IsInstanceVisitor(ast.NodeVisitor):
            def visit_Call(self, node):
                if (isinstance(node.func, ast.Name) and node.func.id == 'isinstance'):
                    # 예외 처리용 isinstance는 허용 (Exception 타입 체크)
                    if len(node.args) >= 2:
                        second_arg = node.args[1]
                        # Exception 타입 체크 허용
                        if isinstance(second_arg, ast.Name) and second_arg.id == 'Exception':
                            return
                        # Tuple이나 복합 타입에서 Exception이 포함된 경우도 허용
                        if isinstance(second_arg, ast.Tuple):
                            for elt in second_arg.elts:
                                if isinstance(elt, ast.Name) and elt.id == 'Exception':
                                    return
                    
                    violations.append({
                        'line': node.lineno,
                        'rule': 'isinstance_usage',
                        'message': 'isinstance() 사용 금지 - SingleDispatch 패턴 사용 권장',
                        'suggestion': '@singledispatch 데코레이터를 사용하여 타입별 함수 분리'
                    })
                self.generic_visit(node)

        IsInstanceVisitor().visit(tree)
        return violations

    def _check_mutation_patterns(self, tree: ast.AST, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """변형 패턴 검사 (리스트/딕셔너리 직접 수정)"""
        violations = []
        
        # 캐시 관련 함수 내부인지 확인을 위한 컨텍스트
        cache_function_patterns = [
            'cache', 'cached_', '_cache', 'get_cache', 'clear_cache', 
            'create_cache', 'with_cache', 'memoize', 'lru_cache'
        ]

        class MutationVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name.lower()
                self.generic_visit(node)
                self.current_function = old_function

            def visit_Assign(self, node):
                # 딕셔너리 키 할당 검사: dict[key] = value
                for target in node.targets:
                    if isinstance(target, ast.Subscript):
                        # 캐시 함수 내부에서는 예외 처리
                        is_cache_function = (self.current_function and 
                                           any(pattern in self.current_function for pattern in cache_function_patterns))
                        
                        if not is_cache_function:
                            violations.append({
                                'line': node.lineno,
                                'rule': 'mutation_patterns',
                                'message': '딕셔너리 직접 수정 - 불변성 원칙 위반',
                                'suggestion': '{**원본, "키": "값"} 패턴으로 새 딕셔너리 생성'
                            })
                self.generic_visit(node)

            def visit_AugAssign(self, node):
                # += 등 증강 할당 연산자
                if isinstance(node.target, (ast.Subscript, ast.Attribute)):
                    violations.append({
                        'line': node.lineno,
                        'rule': 'mutation_patterns',
                        'message': '증강 할당으로 인한 직접 수정 - 불변성 원칙 위반',
                        'suggestion': '새로운 값으로 대체하거나 함수형 조합 사용'
                    })
                self.generic_visit(node)

        visitor = MutationVisitor()
        visitor.visit(tree)
        return violations

    def _check_imperative_loops(self, tree: ast.AST, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """명령형 루프 검사"""
        violations = []

        class LoopVisitor(ast.NodeVisitor):
            def visit_For(self, node):
                # for 루프 내부에서 리스트 조작하는 패턴 찾기
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Call):
                        if (isinstance(stmt.func, ast.Attribute) and
                            stmt.func.attr in ['append', 'extend']):
                            violations.append({
                                'line': node.lineno,
                                'rule': 'imperative_loops',
                                'message': 'for 루프 + append 패턴 - 함수형 패턴 사용 권장',
                                'suggestion': 'map() 또는 list comprehension 사용'
                            })
                            break
                self.generic_visit(node)

        LoopVisitor().visit(tree)
        return violations

    def _check_list_append_loops(self, tree: ast.AST, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """리스트 append 루프 패턴 검사"""
        violations = []

        # 정규식으로 일반적인 append 루프 패턴 찾기
        append_loop_pattern = r'for\s+\w+\s+in\s+.*?:\s*\n\s*\w+\.append\('

        lines = content.split('\n')
        for i, line in enumerate(lines):
            if re.search(r'\.append\(', line):
                # 위쪽으로 for 루프 찾기
                for j in range(max(0, i-5), i):
                    if re.search(r'for\s+\w+\s+in\s+', lines[j]):
                        violations.append({
                            'line': i + 1,
                            'rule': 'list_append_loops',
                            'message': 'append 루프 패턴 - Map/Filter 사용 권장',
                            'suggestion': 'list(map(함수, 반복가능객체)) 또는 [표현식 for 항목 in 반복가능객체] 사용'
                        })
                        break

        return violations

    def _check_dict_mutation(self, tree: ast.AST, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """딕셔너리 변형 패턴 검사"""
        violations = []

        class DictMutationVisitor(ast.NodeVisitor):
            def visit_Call(self, node):
                # dict.update() 호출 검사
                if (isinstance(node.func, ast.Attribute) and
                    node.func.attr == 'update'):
                    violations.append({
                        'line': node.lineno,
                        'rule': 'dict_mutation',
                        'message': 'dict.update() 사용 - 불변성 원칙 위반',
                        'suggestion': '{**dict1, **dict2} 패턴으로 새 딕셔너리 생성'
                    })

                # dict.pop(), dict.clear() 등
                if (isinstance(node.func, ast.Attribute) and
                    node.func.attr in ['pop', 'popitem', 'clear', 'setdefault']):
                    violations.append({
                        'line': node.lineno,
                        'rule': 'dict_mutation',
                        'message': f'dict.{node.func.attr}() 사용 - 불변성 원칙 위반',
                        'suggestion': '함수형 패턴으로 새로운 딕셔너리 생성'
                    })

                self.generic_visit(node)

        DictMutationVisitor().visit(tree)
        return violations

    def _check_global_variables(self, tree: ast.AST, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """전역 변수 수정 검사"""
        violations = []

        class GlobalVisitor(ast.NodeVisitor):
            def visit_Global(self, node):
                violations.append({
                    'line': node.lineno,
                    'rule': 'global_variables',
                    'message': 'global 키워드 사용 - 순수 함수 원칙 위반',
                    'suggestion': '함수 매개변수로 전달하거나 함수형 패턴 사용'
                })
                self.generic_visit(node)

        GlobalVisitor().visit(tree)
        return violations

    def _check_map_filter_priority(self, tree: ast.AST, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Map/Filter 우선순위 검사 (List Comprehension 남용)"""
        violations = []

        class ComprehensionVisitor(ast.NodeVisitor):
            def visit_ListComp(self, node):
                # 복잡한 list comprehension이 있는지 검사
                # 3개 이상의 for 절이 있거나 복잡한 표현식이 있으면 경고
                if len(node.generators) >= 2:
                    violations.append({
                        'line': node.lineno,
                        'rule': 'map_filter_priority',
                        'message': '복잡한 List Comprehension - Map/Filter 조합 권장',
                        'suggestion': 'filter()와 map()을 순차적으로 연결하여 가독성 향상'
                    })

                # 조건이 있는 comprehension에서 map/filter 권장
                for gen in node.generators:
                    if len(gen.ifs) > 1:  # 복잡한 조건
                        violations.append({
                            'line': node.lineno,
                            'rule': 'map_filter_priority',
                            'message': '복잡한 조건의 List Comprehension - Map/Filter 분리 권장',
                            'suggestion': 'filter(조건함수, 데이터)를 먼저 적용한 후 map(변환함수) 적용'
                        })

                self.generic_visit(node)

        ComprehensionVisitor().visit(tree)
        return violations


class CodeQualityChecker:
    """코드 품질 검사 자동화"""

    def __init__(self, project_root: Path, target_dir: str = "app/services/v2"):
        self.project_root = project_root
        self.target_dir = project_root / target_dir
        self.results: Dict[str, Any] = {}

    def run_command(self, cmd: List[str], check_return_code: bool = False) -> Tuple[bool, str]:
        """명령어 실행"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            success = result.returncode == 0 if check_return_code else True
            output = result.stdout + result.stderr
            return success, output
        except Exception as e:
            return False, str(e)

    def run_pyflakes(self) -> Tuple[bool, str]:
        """Pyflakes 실행 - 사용하지 않는 import 감지"""
        print("🔍 Pyflakes 실행 중...")
        cmd = ["pyflakes", str(self.target_dir)]
        success, output = self.run_command(cmd)

        # pyflakes는 출력이 있으면 문제가 있다는 의미
        has_issues = bool(output.strip())
        self.results["pyflakes"] = {
            "success": not has_issues,
            "issues_count": len(output.strip().split('\n')) if has_issues else 0,
            "output": output
        }

        return not has_issues, output

    def run_autoflake(self, dry_run: bool = False) -> Tuple[bool, str]:
        """Autoflake 실행 - 사용하지 않는 import 자동 제거"""
        print("🧹 Autoflake 실행 중...")
        cmd = [
            "autoflake",
            "--remove-all-unused-imports",
            "--remove-unused-variables",
            "--remove-duplicate-keys"
        ]

        if not dry_run:
            cmd.append("--in-place")

        cmd.extend(["--recursive", str(self.target_dir)])

        success, output = self.run_command(cmd)
        self.results["autoflake"] = {
            "success": success,
            "dry_run": dry_run,
            "output": output
        }

        return success, output

    def run_black(self, check_only: bool = False) -> Tuple[bool, str]:
        """Black 실행 - 코드 포매팅"""
        print("🎨 Black 실행 중...")
        cmd = ["black"]

        if check_only:
            cmd.append("--check")

        cmd.append(str(self.target_dir))

        success, output = self.run_command(cmd, check_return_code=check_only)
        self.results["black"] = {
            "success": success,
            "check_only": check_only,
            "output": output
        }

        return success, output

    def run_isort(self, check_only: bool = False) -> Tuple[bool, str]:
        """isort 실행 - import 정렬"""
        print("📚 isort 실행 중...")
        cmd = ["isort"]

        if check_only:
            cmd.append("--check-only")

        cmd.append(str(self.target_dir))

        success, output = self.run_command(cmd, check_return_code=check_only)
        self.results["isort"] = {
            "success": success,
            "check_only": check_only,
            "output": output
        }

        return success, output

    def run_mypy(self) -> Tuple[bool, str]:
        """Mypy 실행 - 타입 체킹"""
        print("🔍 Mypy 실행 중...")
        cmd = ["mypy", str(self.target_dir)]

        success, output = self.run_command(cmd, check_return_code=True)
        self.results["mypy"] = {
            "success": success,
            "output": output
        }

        return success, output

    def run_pylint(self) -> Tuple[bool, str]:
        """Pylint 실행 - 코드 품질 검사"""
        print("📊 Pylint 실행 중...")
        cmd = ["pylint", str(self.target_dir)]

        success, output = self.run_command(cmd)

        # Pylint 점수 추출
        score = self._extract_pylint_score(output)
        self.results["pylint"] = {
            "success": success,
            "score": score,
            "output": output
        }

        return success, output

    def _extract_pylint_score(self, output: str) -> float:
        """Pylint 출력에서 점수 추출"""
        try:
            for line in output.split('\n'):
                if 'Your code has been rated at' in line:
                    score_part = line.split('rated at')[1].split('/')[0].strip()
                    return float(score_part)
        except:
            pass
        return 0.0

    def run_functional_programming_check(self, show_suggestions: bool = False) -> Tuple[bool, str]:
        """함수형 프로그래밍 규칙 검사"""
        print("🧮 함수형 프로그래밍 규칙 검사 중...")
        fp_checker = FunctionalProgrammingChecker(self.target_dir)
        violations = fp_checker.check_all_files()

        success = len(violations) == 0

        # 결과 구성
        if violations:
            output_lines = ["함수형 프로그래밍 규칙 위반 항목들:"]
            for file_path, file_violations in violations.items():
                output_lines.append(f"\n📁 {file_path}:")
                for violation in file_violations:
                    output_lines.append(f"  ❌ 라인 {violation['line']:3d}: {violation['message']}")
                    if violation.get('suggestion'):
                        output_lines.append(f"     💡 제안: {violation['suggestion']}")
            output = "\n".join(output_lines)
        else:
            output = "✅ 모든 함수형 프로그래밍 규칙을 준수하고 있습니다!"

        # 수정 가이드 추가
        if show_suggestions and violations:
            reporter = FunctionalProgrammingReporter(self.target_dir)
            suggestions = reporter.generate_fix_suggestions(violations)
            output += "\n" + suggestions
        
        self.results["functional_programming"] = {
            "success": success,
            "violation_count": sum(len(v) for v in violations.values()),
            "file_count": len(violations),
            "violations": violations,
            "output": output
        }

        return success, output

    def run_all_checks(self, fix: bool = False) -> None:
        """모든 검사 실행"""
        print("🚀 코드 품질 검사 시작\n")

        # 1. 초기 상태 확인
        print("📋 1단계: 초기 상태 확인")
        self.run_pyflakes()
        print()

        # 2. 자동 수정 도구 실행 (fix 모드인 경우)
        if fix:
            print("🔧 2단계: 자동 수정 도구 실행")
            self.run_autoflake(dry_run=False)
            self.run_black(check_only=False)
            self.run_isort(check_only=False)
            print()
        else:
            print("🔍 2단계: 체크 모드 실행")
            self.run_autoflake(dry_run=True)
            self.run_black(check_only=True)
            self.run_isort(check_only=True)
            print()

        # 3. 함수형 프로그래밍 규칙 검사
        print("🧮 3단계: 함수형 프로그래밍 규칙 검사")
        self.run_functional_programming_check(show_suggestions=fix)
        print()

        # 4. 정적 분석 도구 실행
        print("📊 4단계: 정적 분석 도구 실행")
        self.run_mypy()
        self.run_pylint()
        print()

        # 5. 결과 리포트
        self.print_summary()

    def print_summary(self) -> None:
        """결과 요약 출력"""
        print("=" * 60)
        print("📊 코드 품질 검사 결과 요약")
        print("=" * 60)

        for tool, result in self.results.items():
            status = "✅ 통과" if result["success"] else "❌ 실패"
            print(f"{tool.upper():12} | {status}")

            if tool == "pyflakes" and not result["success"]:
                print(f"             | 이슈 수: {result['issues_count']}")

            if tool == "pylint" and "score" in result:
                print(f"             | 점수: {result['score']:.1f}/10.0")

            if tool == "functional_programming" and not result["success"]:
                print(f"             | 위반 항목: {result['violation_count']}개")
                print(f"             | 영향 파일: {result['file_count']}개")

        print("=" * 60)

        # 전체 성공 여부
        all_passed = all(result["success"] for result in self.results.values())
        overall_status = "🎉 모든 검사 통과!" if all_passed else "⚠️  일부 검사 실패"
        print(f"전체 결과: {overall_status}")
        print()

    def save_results(self, output_file: Path) -> None:
        """결과를 JSON 파일로 저장"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"📄 결과가 {output_file}에 저장되었습니다.")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="V2 모듈 코드 품질 검사 도구")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="자동 수정 모드 (autoflake, black, isort만 적용, 함수형 규칙은 가이드만 제공)"
    )
    parser.add_argument(
        "--target-dir",
        default="app/services/v2",
        help="검사할 디렉토리 (기본값: app/services/v2)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="결과 JSON 파일 경로"
    )
    parser.add_argument(
        "--functional-only",
        action="store_true",
        help="함수형 프로그래밍 규칙만 검사"
    )
    parser.add_argument(
        "--show-suggestions",
        action="store_true",
        help="함수형 프로그래밍 위반에 대한 수정 가이드 표시"
    )
    parser.add_argument(
        "--export-checklist",
        action="store_true",
        help="수정 체크리스트를 마크다운으로 출력"
    )
    parser.add_argument(
        "--show-details",
        action="store_true",
        help="위반 항목 상세 출력"
    )

    args = parser.parse_args()

    project_root = Path.cwd()
    checker = CodeQualityChecker(project_root, args.target_dir)

    try:
        if args.functional_only:
            # 함수형 프로그래밍 규칙만 검사
            print("🧮 함수형 프로그래밍 규칙 검사 모드\n")
            success, output = checker.run_functional_programming_check(show_suggestions=args.show_suggestions)
            print(output)
            
            # 체크리스트 출력
            if args.export_checklist and not success:
                fp_result = checker.results.get("functional_programming", {})
                violations = fp_result.get("violations", {})
                if violations:
                    reporter = FunctionalProgrammingReporter(checker.target_dir)
                    checklist = reporter.export_to_markdown(violations)
                    
                    # 파일로 저장
                    checklist_file = Path("functional_fix_checklist.md")
                    with open(checklist_file, 'w', encoding='utf-8') as f:
                        f.write(checklist)
                    print(f"\n📋 체크리스트가 {checklist_file}에 저장되었습니다.")

            if args.show_details and not success:
                print("\n" + "="*60)
                print("📋 위반 항목 상세 정보")
                print("="*60)
                fp_result = checker.results.get("functional_programming", {})
                violations = fp_result.get("violations", {})

                for file_path, file_violations in violations.items():
                    print(f"\n📁 {file_path}:")
                    for violation in file_violations:
                        print(f"  ❌ 라인 {violation['line']:3d}: {violation['message']}")
                        if violation.get('suggestion'):
                            print(f"     💡 제안: {violation['suggestion']}")
                        print(f"     🏷️  규칙: {violation['rule']}")
                        print()
        else:
            checker.run_all_checks(fix=args.fix)

        if args.output:
            checker.save_results(args.output)

    except KeyboardInterrupt:
        print("\n⏹️  사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
