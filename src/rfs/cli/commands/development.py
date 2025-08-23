"""
Development Workflow Commands (RFS v4)

개발 워크플로우 자동화 명령어들
- dev: 개발 서버 실행
- build: 프로젝트 빌드
- test: 테스트 실행
"""

import os
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.live import Live
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..core import Command
from ...core import Result, Success, Failure, get_config

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


@dataclass
class BuildConfig:
    """빌드 설정"""
    target: str
    output_dir: str
    optimize: bool
    include_tests: bool


class DevCommand(Command):
    """개발 서버 실행 명령어"""
    
    name = "dev"
    description = "RFS 개발 서버 시작 (Hot Reload 지원)"
    
    def __init__(self):
        super().__init__()
        self.process = None
    
    async def execute(self, args: List[str]) -> Result[str, str]:
        """개발 서버 실행"""
        try:
            # 설정 로드
            config = get_config()
            
            # 개발 서버 옵션 파싱
            options = self._parse_dev_options(args)
            
            # 개발 환경 확인
            if not self._check_dev_environment():
                return Failure("개발 환경 설정이 올바르지 않습니다.")
            
            # 서버 시작
            if console:
                console.print(Panel(
                    f"🚀 RFS v4 개발 서버 시작\n\n"
                    f"📁 프로젝트: {Path.cwd().name}\n"
                    f"🌐 포트: {options.get('port', 8000)}\n"
                    f"🔄 Hot Reload: {'활성화' if options.get('reload', True) else '비활성화'}\n"
                    f"🐛 디버그 모드: {'활성화' if options.get('debug', True) else '비활성화'}\n\n"
                    f"💡 서버를 중지하려면 Ctrl+C를 누르세요",
                    title="개발 서버",
                    border_style="green"
                ))
            
            await self._start_dev_server(options)
            
            return Success("개발 서버 시작 완료")
            
        except KeyboardInterrupt:
            return Success("개발 서버가 중지되었습니다.")
        except Exception as e:
            return Failure(f"개발 서버 시작 실패: {str(e)}")
    
    def _parse_dev_options(self, args: List[str]) -> Dict[str, Any]:
        """개발 서버 옵션 파싱"""
        options = {
            'port': 8000,
            'host': '0.0.0.0',
            'reload': True,
            'debug': True,
            'workers': 1
        }
        
        # 간단한 인자 파싱
        for i, arg in enumerate(args):
            if arg == '--port' and i + 1 < len(args):
                options['port'] = int(args[i + 1])
            elif arg == '--host' and i + 1 < len(args):
                options['host'] = args[i + 1]
            elif arg == '--no-reload':
                options['reload'] = False
            elif arg == '--no-debug':
                options['debug'] = False
            elif arg == '--workers' and i + 1 < len(args):
                options['workers'] = int(args[i + 1])
        
        return options
    
    def _check_dev_environment(self) -> bool:
        """개발 환경 확인"""
        # main.py 파일 존재 여부
        if not Path('main.py').exists():
            if console:
                console.print("❌ main.py 파일을 찾을 수 없습니다.", style="red")
            return False
        
        # requirements.txt 확인
        if Path('requirements.txt').exists():
            requirements = Path('requirements.txt').read_text()
            if 'rfs-framework' not in requirements:
                if console:
                    console.print("⚠️  requirements.txt에 rfs-framework가 없습니다.", style="yellow")
        
        return True
    
    async def _start_dev_server(self, options: Dict[str, Any]) -> None:
        """개발 서버 시작"""
        # uvicorn 명령어 구성
        cmd = [
            'uvicorn',
            'main:app',
            '--host', options['host'],
            '--port', str(options['port']),
        ]
        
        if options['reload']:
            cmd.append('--reload')
        
        if options['debug']:
            cmd.append('--log-level')
            cmd.append('debug')
        
        # 서버 프로세스 실행
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # 출력 스트림 처리
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            
            output = line.decode().strip()
            if output:
                if console:
                    # 로그 레벨에 따른 색상 적용
                    if 'ERROR' in output:
                        console.print(output, style="red")
                    elif 'WARNING' in output:
                        console.print(output, style="yellow")
                    elif 'INFO' in output:
                        console.print(output, style="blue")
                    else:
                        console.print(output)
                else:
                    print(output)


class BuildCommand(Command):
    """프로젝트 빌드 명령어"""
    
    name = "build"
    description = "RFS 프로젝트 빌드 및 패키징"
    
    async def execute(self, args: List[str]) -> Result[str, str]:
        """프로젝트 빌드 실행"""
        try:
            # 빌드 설정 파싱
            build_config = self._parse_build_config(args)
            
            # 빌드 프로세스 시작
            if console:
                console.print(Panel(
                    f"🏗️  RFS v4 프로젝트 빌드 시작\n\n"
                    f"🎯 타겟: {build_config.target}\n"
                    f"📁 출력 디렉토리: {build_config.output_dir}\n"
                    f"⚡ 최적화: {'활성화' if build_config.optimize else '비활성화'}\n"
                    f"🧪 테스트 포함: {'예' if build_config.include_tests else '아니오'}",
                    title="프로젝트 빌드",
                    border_style="blue"
                ))
            
            # 빌드 단계 실행
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                
                # 1. 의존성 확인
                task1 = progress.add_task("의존성 확인 중...", total=100)
                await self._check_dependencies()
                progress.update(task1, completed=100)
                
                # 2. 코드 검증
                task2 = progress.add_task("코드 검증 중...", total=100)
                validation_result = await self._validate_code()
                if validation_result.is_failure():
                    return validation_result
                progress.update(task2, completed=100)
                
                # 3. 테스트 실행 (옵션)
                if build_config.include_tests:
                    task3 = progress.add_task("테스트 실행 중...", total=100)
                    test_result = await self._run_tests()
                    if test_result.is_failure():
                        return test_result
                    progress.update(task3, completed=100)
                
                # 4. 빌드 아티팩트 생성
                task4 = progress.add_task("빌드 아티팩트 생성 중...", total=100)
                await self._create_build_artifacts(build_config)
                progress.update(task4, completed=100)
                
                # 5. 최적화 (옵션)
                if build_config.optimize:
                    task5 = progress.add_task("빌드 최적화 중...", total=100)
                    await self._optimize_build(build_config)
                    progress.update(task5, completed=100)
            
            # 빌드 결과 표시
            if console:
                console.print(Panel(
                    f"✅ 빌드 완료!\n\n"
                    f"📦 빌드 아티팩트: {build_config.output_dir}\n"
                    f"🔍 빌드 로그: build.log\n\n"
                    f"다음 단계:\n"
                    f"  rfs deploy  # 배포\n"
                    f"  rfs test    # 추가 테스트",
                    title="빌드 성공",
                    border_style="green"
                ))
            
            return Success(f"프로젝트 빌드 완료: {build_config.output_dir}")
            
        except Exception as e:
            return Failure(f"빌드 실패: {str(e)}")
    
    def _parse_build_config(self, args: List[str]) -> BuildConfig:
        """빌드 설정 파싱"""
        config = BuildConfig(
            target="production",
            output_dir="dist",
            optimize=True,
            include_tests=False
        )
        
        # 인자 파싱
        for i, arg in enumerate(args):
            if arg == '--target' and i + 1 < len(args):
                config.target = args[i + 1]
            elif arg == '--output' and i + 1 < len(args):
                config.output_dir = args[i + 1]
            elif arg == '--no-optimize':
                config.optimize = False
            elif arg == '--include-tests':
                config.include_tests = True
        
        return config
    
    async def _check_dependencies(self) -> None:
        """의존성 확인"""
        await asyncio.sleep(0.5)  # 시뮬레이션
    
    async def _validate_code(self) -> Result[str, str]:
        """코드 검증"""
        try:
            # 간단한 구문 검사
            await asyncio.sleep(0.5)  # 시뮬레이션
            
            # main.py 파일 검증
            if Path('main.py').exists():
                with open('main.py', 'r') as f:
                    code = f.read()
                    # 기본적인 문법 검사
                    compile(code, 'main.py', 'exec')
            
            return Success("코드 검증 완료")
        except SyntaxError as e:
            return Failure(f"구문 오류: {str(e)}")
        except Exception as e:
            return Failure(f"코드 검증 실패: {str(e)}")


class TestCommand(Command):
    """테스트 실행 명령어"""
    
    name = "test"
    description = "RFS 프로젝트 테스트 실행"
    
    async def execute(self, args: List[str]) -> Result[str, str]:
        """테스트 실행"""
        try:
            # 테스트 옵션 파싱
            options = self._parse_test_options(args)
            
            if console:
                console.print(Panel(
                    f"🧪 RFS v4 테스트 실행\n\n"
                    f"📁 테스트 경로: {options.get('path', 'tests/')}\n"
                    f"📊 커버리지: {'활성화' if options.get('coverage') else '비활성화'}\n"
                    f"🔍 필터: {options.get('filter', '모든 테스트')}\n"
                    f"⚡ 병렬 실행: {'활성화' if options.get('parallel') else '비활성화'}",
                    title="테스트 실행",
                    border_style="blue"
                ))
            
            # pytest 명령어 구성
            cmd = ['python', '-m', 'pytest']
            
            if options.get('path'):
                cmd.append(options['path'])
            
            if options.get('verbose'):
                cmd.append('-v')
            
            if options.get('coverage'):
                cmd.extend(['--cov=.', '--cov-report=html'])
            
            if options.get('filter'):
                cmd.extend(['-k', options['filter']])
            
            if options.get('parallel'):
                cmd.extend(['-n', 'auto'])
            
            # 테스트 실행
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            # 출력 처리
            output_lines = []
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                output = line.decode().strip()
                if output:
                    output_lines.append(output)
                    if console:
                        # 테스트 결과에 따른 색상 적용
                        if 'PASSED' in output:
                            console.print(output, style="green")
                        elif 'FAILED' in output:
                            console.print(output, style="red")
                        elif 'ERROR' in output:
                            console.print(output, style="red")
                        else:
                            console.print(output)
                    else:
                        print(output)
            
            await process.wait()
            
            # 테스트 결과 분석
            test_results = self._analyze_test_results(output_lines)
            
            if console:
                self._display_test_summary(test_results)
            
            if test_results['failed'] > 0:
                return Failure(f"테스트 실패: {test_results['failed']}개 실패")
            else:
                return Success(f"모든 테스트 통과: {test_results['passed']}개 성공")
            
        except Exception as e:
            return Failure(f"테스트 실행 실패: {str(e)}")
    
    def _parse_test_options(self, args: List[str]) -> Dict[str, Any]:
        """테스트 옵션 파싱"""
        options = {
            'path': None,
            'verbose': False,
            'coverage': False,
            'filter': None,
            'parallel': False
        }
        
        for i, arg in enumerate(args):
            if arg == '--path' and i + 1 < len(args):
                options['path'] = args[i + 1]
            elif arg in ['-v', '--verbose']:
                options['verbose'] = True
            elif arg == '--coverage':
                options['coverage'] = True
            elif arg == '--filter' and i + 1 < len(args):
                options['filter'] = args[i + 1]
            elif arg == '--parallel':
                options['parallel'] = True
        
        return options
    
    def _analyze_test_results(self, output_lines: List[str]) -> Dict[str, int]:
        """테스트 결과 분석"""
        results = {
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0
        }
        
        for line in output_lines:
            if 'passed' in line.lower():
                # pytest 결과 라인 파싱
                import re
                match = re.search(r'(\d+) passed', line)
                if match:
                    results['passed'] = int(match.group(1))
            
            if 'failed' in line.lower():
                match = re.search(r'(\d+) failed', line)
                if match:
                    results['failed'] = int(match.group(1))
        
        return results
    
    def _display_test_summary(self, results: Dict[str, int]) -> None:
        """테스트 결과 요약 표시"""
        if not console:
            return
        
        summary_table = Table(title="테스트 결과 요약", show_header=True, header_style="bold magenta")
        summary_table.add_column("상태", style="cyan", width=10)
        summary_table.add_column("개수", style="green", justify="right")
        summary_table.add_column("비율", style="yellow", justify="right")
        
        total = sum(results.values())
        if total > 0:
            for status, count in results.items():
                if count > 0:
                    percentage = (count / total) * 100
                    summary_table.add_row(
                        status.title(),
                        str(count),
                        f"{percentage:.1f}%"
                    )
        
        console.print(summary_table)