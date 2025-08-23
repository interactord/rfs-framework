"""
Test Runner (RFS v4)

고급 테스트 실행 및 관리 시스템
- 다양한 테스트 프레임워크 지원
- 병렬 테스트 실행
- 코드 커버리지 측정
- 테스트 결과 분석
"""

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import xml.etree.ElementTree as ET

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.tree import Tree
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ...core import Result, Success, Failure

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class TestFramework(Enum):
    """지원하는 테스트 프레임워크"""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    ASYNCIO = "asyncio"
    CUSTOM = "custom"


class TestType(Enum):
    """테스트 유형"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    END_TO_END = "e2e"
    SECURITY = "security"


@dataclass
class TestConfig:
    """테스트 설정"""
    framework: TestFramework = TestFramework.PYTEST
    test_paths: List[str] = field(default_factory=lambda: ["tests/"])
    patterns: List[str] = field(default_factory=lambda: ["test_*.py", "*_test.py"])
    parallel: bool = True
    max_workers: int = 4
    coverage: bool = True
    coverage_threshold: float = 80.0
    verbose: bool = True
    fail_fast: bool = False
    timeout: int = 300  # 5분
    environment_vars: Dict[str, str] = field(default_factory=dict)
    fixtures_path: Optional[str] = None
    mock_config: Optional[Dict[str, Any]] = None


@dataclass
class TestResult:
    """테스트 결과"""
    framework: TestFramework
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    execution_time: float = 0.0
    coverage_percentage: Optional[float] = None
    failed_test_details: List[Dict[str, Any]] = field(default_factory=list)
    coverage_report: Optional[Dict[str, Any]] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """성공률 계산"""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100
    
    @property
    def is_successful(self) -> bool:
        """테스트 성공 여부"""
        return self.failed_tests == 0 and self.error_tests == 0


class TestRunner:
    """고급 테스트 실행기"""
    
    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or TestConfig()
        self.project_path = Path.cwd()
        self.test_history: List[TestResult] = []
    
    async def run_tests(self, test_type: Optional[TestType] = None, **kwargs) -> Result[TestResult, str]:
        """테스트 실행"""
        try:
            # 설정 업데이트
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            if console:
                console.print(Panel(
                    f"🧪 RFS v4 테스트 실행 시작\n\n"
                    f"🔧 프레임워크: {self.config.framework.value}\n"
                    f"📁 경로: {', '.join(self.config.test_paths)}\n"
                    f"⚡ 병렬 실행: {'예' if self.config.parallel else '아니오'}\n"
                    f"📊 커버리지: {'예' if self.config.coverage else '아니오'}\n"
                    f"🎯 타입: {test_type.value if test_type else '모든 타입'}",
                    title="테스트 실행",
                    border_style="blue"
                ))
            
            # 테스트 실행
            start_time = time.time()
            
            if self.config.framework == TestFramework.PYTEST:
                result = await self._run_pytest(test_type)
            elif self.config.framework == TestFramework.UNITTEST:
                result = await self._run_unittest(test_type)
            elif self.config.framework == TestFramework.ASYNCIO:
                result = await self._run_asyncio_tests(test_type)
            else:
                return Failure(f"지원하지 않는 테스트 프레임워크: {self.config.framework}")
            
            if result.is_failure():
                return result
            
            test_result = result.unwrap()
            test_result.execution_time = time.time() - start_time
            
            # 테스트 결과 표시
            if console:
                await self._display_test_results(test_result)
            
            # 이력에 추가
            self.test_history.append(test_result)
            
            return Success(test_result)
            
        except Exception as e:
            return Failure(f"테스트 실행 실패: {str(e)}")
    
    async def _run_pytest(self, test_type: Optional[TestType]) -> Result[TestResult, str]:
        """pytest 실행"""
        try:
            # pytest 명령어 구성
            cmd = ['python', '-m', 'pytest']
            
            # 테스트 경로 추가
            for path in self.config.test_paths:
                if Path(path).exists():
                    cmd.append(path)
            
            # 옵션 추가
            if self.config.verbose:
                cmd.append('-v')
            
            if self.config.fail_fast:
                cmd.append('-x')
            
            if self.config.parallel and self.config.max_workers > 1:
                cmd.extend(['-n', str(self.config.max_workers)])
            
            if self.config.coverage:
                cmd.extend([
                    '--cov=.',
                    '--cov-report=xml',
                    '--cov-report=html',
                    '--cov-report=term-missing'
                ])
            
            # JUnit XML 리포트
            cmd.extend(['--junit-xml=test-results.xml'])
            
            # 테스트 타입 필터링
            if test_type:
                cmd.extend(['-m', test_type.value])
            
            # 환경 변수 설정
            env = {**os.environ, **self.config.environment_vars}
            
            if console:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task("pytest 실행 중...", total=None)
                    
                    # pytest 실행
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                        env=env
                    )
                    
                    output_lines = []
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            break
                        
                        line_str = line.decode().strip()
                        output_lines.append(line_str)
                    
                    await process.wait()
                    progress.remove_task(task)
            
            # 결과 파싱
            test_result = await self._parse_pytest_results(process.returncode, output_lines)
            return Success(test_result)
            
        except Exception as e:
            return Failure(f"pytest 실행 실패: {str(e)}")
    
    async def _parse_pytest_results(self, return_code: int, output_lines: List[str]) -> TestResult:
        """pytest 결과 파싱"""
        result = TestResult(framework=TestFramework.PYTEST)
        
        try:
            # JUnit XML 파싱
            xml_file = Path("test-results.xml")
            if xml_file.exists():
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                result.total_tests = int(root.get('tests', 0))
                result.failed_tests = int(root.get('failures', 0))
                result.error_tests = int(root.get('errors', 0))
                result.skipped_tests = int(root.get('skipped', 0))
                result.passed_tests = result.total_tests - result.failed_tests - result.error_tests - result.skipped_tests
                
                # 실패한 테스트 상세 정보
                for testcase in root.findall('.//testcase'):
                    failure = testcase.find('failure')
                    error = testcase.find('error')
                    
                    if failure is not None or error is not None:
                        result.failed_test_details.append({
                            'name': testcase.get('name', ''),
                            'classname': testcase.get('classname', ''),
                            'time': float(testcase.get('time', 0)),
                            'message': (failure or error).get('message', '') if (failure or error) is not None else '',
                            'details': (failure or error).text if (failure or error) is not None else ''
                        })
            
            # 커버리지 정보 파싱
            coverage_xml = Path("coverage.xml")
            if coverage_xml.exists() and self.config.coverage:
                try:
                    tree = ET.parse(coverage_xml)
                    root = tree.getroot()
                    coverage_elem = root.find('.//coverage')
                    if coverage_elem is not None:
                        result.coverage_percentage = float(coverage_elem.get('line-rate', 0)) * 100
                except:
                    pass
            
        except Exception as e:
            if console:
                console.print(f"⚠️  결과 파싱 중 오류: {str(e)}", style="yellow")
        
        return result
    
    async def _run_unittest(self, test_type: Optional[TestType]) -> Result[TestResult, str]:
        """unittest 실행"""
        try:
            # unittest 명령어 구성
            cmd = ['python', '-m', 'unittest']
            
            if self.config.verbose:
                cmd.append('-v')
            
            # 테스트 디스커버리
            cmd.extend(['discover', '-s', self.config.test_paths[0], '-p', 'test_*.py'])
            
            # 실행
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await process.communicate()
            output = stdout.decode()
            
            # 결과 파싱 (간단한 구현)
            result = TestResult(framework=TestFramework.UNITTEST)
            
            # unittest 출력에서 정보 추출
            lines = output.split('\n')
            for line in lines:
                if 'Ran' in line and 'test' in line:
                    import re
                    match = re.search(r'Ran (\d+) test', line)
                    if match:
                        result.total_tests = int(match.group(1))
                
                if 'FAILED' in line:
                    match = re.search(r'FAILED \(.*failures=(\d+).*\)', line)
                    if match:
                        result.failed_tests = int(match.group(1))
            
            result.passed_tests = result.total_tests - result.failed_tests
            
            return Success(result)
            
        except Exception as e:
            return Failure(f"unittest 실행 실패: {str(e)}")
    
    async def _run_asyncio_tests(self, test_type: Optional[TestType]) -> Result[TestResult, str]:
        """asyncio 기반 테스트 실행"""
        try:
            # pytest-asyncio 사용
            cmd = ['python', '-m', 'pytest', '--asyncio-mode=auto']
            
            for path in self.config.test_paths:
                if Path(path).exists():
                    cmd.append(path)
            
            if self.config.verbose:
                cmd.append('-v')
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await process.communicate()
            
            # pytest 결과 파싱 재사용
            result = await self._parse_pytest_results(process.returncode, stdout.decode().split('\n'))
            result.framework = TestFramework.ASYNCIO
            
            return Success(result)
            
        except Exception as e:
            return Failure(f"asyncio 테스트 실행 실패: {str(e)}")
    
    async def _display_test_results(self, result: TestResult) -> None:
        """테스트 결과 표시"""
        if not console:
            return
        
        # 결과 요약 테이블
        summary_table = Table(title="테스트 결과 요약", show_header=True, header_style="bold magenta")
        summary_table.add_column("항목", style="cyan", width=15)
        summary_table.add_column("값", style="white", justify="right")
        summary_table.add_column("비율", style="green", justify="right")
        
        summary_table.add_row("총 테스트", str(result.total_tests), "100%")
        summary_table.add_row(
            "통과", 
            f"[green]{result.passed_tests}[/green]", 
            f"[green]{result.success_rate:.1f}%[/green]"
        )
        
        if result.failed_tests > 0:
            failure_rate = (result.failed_tests / result.total_tests) * 100 if result.total_tests > 0 else 0
            summary_table.add_row(
                "실패", 
                f"[red]{result.failed_tests}[/red]", 
                f"[red]{failure_rate:.1f}%[/red]"
            )
        
        if result.skipped_tests > 0:
            skip_rate = (result.skipped_tests / result.total_tests) * 100 if result.total_tests > 0 else 0
            summary_table.add_row(
                "건너뜀", 
                f"[yellow]{result.skipped_tests}[/yellow]", 
                f"[yellow]{skip_rate:.1f}%[/yellow]"
            )
        
        summary_table.add_row("실행 시간", f"{result.execution_time:.2f}초", "")
        
        if result.coverage_percentage is not None:
            coverage_color = "green" if result.coverage_percentage >= self.config.coverage_threshold else "red"
            summary_table.add_row(
                "코드 커버리지", 
                f"[{coverage_color}]{result.coverage_percentage:.1f}%[/{coverage_color}]",
                f"목표: {self.config.coverage_threshold}%"
            )
        
        console.print(summary_table)
        
        # 실패한 테스트 상세 정보
        if result.failed_test_details:
            console.print("\n")
            failure_tree = Tree("❌ 실패한 테스트")
            
            for failure in result.failed_test_details:
                test_node = failure_tree.add(f"[red]{failure['name']}[/red] ({failure['classname']})")
                if failure['message']:
                    test_node.add(f"메시지: {failure['message']}")
                if failure['time']:
                    test_node.add(f"실행 시간: {failure['time']:.3f}초")
            
            console.print(failure_tree)
        
        # 최종 상태
        if result.is_successful:
            console.print(Panel(
                f"✅ 모든 테스트 통과!\n\n"
                f"🎯 성공률: {result.success_rate:.1f}%\n"
                f"⏱️  실행 시간: {result.execution_time:.2f}초"
                + (f"\n📊 코드 커버리지: {result.coverage_percentage:.1f}%" if result.coverage_percentage else ""),
                title="테스트 성공",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"❌ {result.failed_tests}개 테스트 실패\n\n"
                f"🎯 성공률: {result.success_rate:.1f}%\n"
                f"⏱️  실행 시간: {result.execution_time:.2f}초\n\n"
                f"💡 실패한 테스트를 확인하고 수정해주세요.",
                title="테스트 실패",
                border_style="red"
            ))
    
    async def generate_test_template(self, test_name: str, test_type: TestType) -> Result[str, str]:
        """테스트 템플릿 생성"""
        try:
            template = self._get_test_template(test_name, test_type)
            
            # 테스트 파일 경로 결정
            test_dir = Path(self.config.test_paths[0])
            test_dir.mkdir(parents=True, exist_ok=True)
            
            test_file = test_dir / f"test_{test_name.lower()}.py"
            
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(template)
            
            if console:
                console.print(Panel(
                    f"✅ 테스트 템플릿 생성 완료\n\n"
                    f"📁 파일: {test_file}\n"
                    f"🧪 유형: {test_type.value}\n"
                    f"🔧 프레임워크: {self.config.framework.value}",
                    title="테스트 템플릿",
                    border_style="green"
                ))
            
            return Success(f"테스트 템플릿 생성 완료: {test_file}")
            
        except Exception as e:
            return Failure(f"테스트 템플릿 생성 실패: {str(e)}")
    
    def _get_test_template(self, test_name: str, test_type: TestType) -> str:
        """테스트 템플릿 생성"""
        if self.config.framework == TestFramework.PYTEST:
            return f'''"""
{test_name.title()} 테스트

{test_type.value} 테스트를 위한 pytest 기반 테스트
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

# RFS Framework 임포트
from rfs import Result, Success, Failure


class Test{test_name.title()}:
    """
    {test_name.title()} 테스트 클래스
    """
    
    def setup_method(self):
        """각 테스트 메서드 실행 전 설정"""
        pass
    
    def teardown_method(self):
        """각 테스트 메서드 실행 후 정리"""
        pass
    
    def test_{test_name}_success(self):
        """성공 시나리오 테스트"""
        # Given (준비)
        
        # When (실행)
        
        # Then (검증)
        assert True  # TODO: 실제 테스트 구현
    
    def test_{test_name}_failure(self):
        """실패 시나리오 테스트"""
        # Given (준비)
        
        # When (실행)
        
        # Then (검증)
        assert True  # TODO: 실제 테스트 구현
    
    @pytest.mark.asyncio
    async def test_{test_name}_async(self):
        """비동기 테스트"""
        # Given (준비)
        
        # When (실행)
        
        # Then (검증)
        assert True  # TODO: 실제 테스트 구현
    
    @pytest.mark.parametrize("input_data,expected", [
        ("test1", "expected1"),
        ("test2", "expected2"),
    ])
    def test_{test_name}_parametrized(self, input_data, expected):
        """매개변수화 테스트"""
        # Given (준비)
        
        # When (실행)
        
        # Then (검증)
        assert True  # TODO: 실제 테스트 구현
    
    def test_{test_name}_with_mock(self):
        """모킹을 사용한 테스트"""
        with patch('module.function') as mock_func:
            # Given (준비)
            mock_func.return_value = "mocked_result"
            
            # When (실행)
            
            # Then (검증)
            mock_func.assert_called_once()
            assert True  # TODO: 실제 테스트 구현
'''
        
        else:  # unittest
            return f'''"""
{test_name.title()} 테스트

{test_type.value} 테스트를 위한 unittest 기반 테스트
"""

import unittest
import asyncio
from unittest.mock import Mock, patch

# RFS Framework 임포트
from rfs import Result, Success, Failure


class Test{test_name.title()}(unittest.TestCase):
    """
    {test_name.title()} 테스트 클래스
    """
    
    def setUp(self):
        """각 테스트 메서드 실행 전 설정"""
        pass
    
    def tearDown(self):
        """각 테스트 메서드 실행 후 정리"""
        pass
    
    def test_{test_name}_success(self):
        """성공 시나리오 테스트"""
        # Given (준비)
        
        # When (실행)
        
        # Then (검증)
        self.assertTrue(True)  # TODO: 실제 테스트 구현
    
    def test_{test_name}_failure(self):
        """실패 시나리오 테스트"""
        # Given (준비)
        
        # When (실행)
        
        # Then (검증)
        self.assertTrue(True)  # TODO: 실제 테스트 구현
    
    def test_{test_name}_async(self):
        """비동기 테스트"""
        async def async_test():
            # Given (준비)
            
            # When (실행)
            
            # Then (검증)
            self.assertTrue(True)  # TODO: 실제 테스트 구현
        
        asyncio.run(async_test())
    
    @patch('module.function')
    def test_{test_name}_with_mock(self, mock_func):
        """모킹을 사용한 테스트"""
        # Given (준비)
        mock_func.return_value = "mocked_result"
        
        # When (실행)
        
        # Then (검증)
        mock_func.assert_called_once()
        self.assertTrue(True)  # TODO: 실제 테스트 구현


if __name__ == '__main__':
    unittest.main()
'''
    
    def get_test_history(self) -> List[TestResult]:
        """테스트 실행 이력 조회"""
        return self.test_history.copy()
    
    def get_coverage_report(self) -> Optional[Dict[str, Any]]:
        """커버리지 리포트 조회"""
        if not self.test_history:
            return None
        
        latest_result = self.test_history[-1]
        return latest_result.coverage_report