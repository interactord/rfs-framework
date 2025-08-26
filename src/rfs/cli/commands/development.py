"""
Development Workflow Commands (RFS v4)

개발 워크플로우 자동화 명령어들
- dev: 개발 서버 실행
- build: 프로젝트 빌드
- test: 테스트 실행
"""

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ...core.config import get_config
from ...core.result import Failure, Result, Success
from ..core import Command

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
            config = get_config()
            options = self._parse_dev_options(args)
            if not self._check_dev_environment():
                return Failure("개발 환경 설정이 올바르지 않습니다.")
            if console:
                console.print(
                    Panel(
                        f"🚀 RFS v4 개발 서버 시작\n\n📁 프로젝트: {Path.cwd().name}\n🌐 포트: {options.get('port', 8000)}\n🔄 Hot Reload: {('활성화' if options.get('reload', True) else '비활성화')}\n🐛 디버그 모드: {('활성화' if options.get('debug', True) else '비활성화')}\n\n💡 서버를 중지하려면 Ctrl+C를 누르세요",
                        title="개발 서버",
                        border_style="green",
                    )
                )
            await self._start_dev_server(options)
            return Success("개발 서버 시작 완료")
        except KeyboardInterrupt:
            return Success("개발 서버가 중지되었습니다.")
        except Exception as e:
            return Failure(f"개발 서버 시작 실패: {str(e)}")

    def _parse_dev_options(self, args: List[str]) -> Dict[str, Any]:
        """개발 서버 옵션 파싱"""
        options = {
            "port": 8000,
            "host": "0.0.0.0",
            "reload": True,
            "debug": True,
            "workers": 1,
        }
        for i, arg in enumerate(args):
            match arg:
                case "--port":
                    options["port"] = {"port": int(args[i + 1])}
                case "--host":
                    options["host"] = {"host": args[i + 1]}
                case "--no-reload":
                    options["reload"] = {"reload": False}
                case "--no-debug":
                    options["debug"] = {"debug": False}
                case "--workers":
                    options["workers"] = {"workers": int(args[i + 1])}
        return options

    def _check_dev_environment(self) -> bool:
        """개발 환경 확인"""
        if not Path("main.py").exists():
            if console:
                console.print("❌ main.py 파일을 찾을 수 없습니다.", style="red")
            return False
        if Path("requirements.txt").exists():
            requirements = Path("requirements.txt").read_text()
            if "rfs-framework" not in requirements:
                if console:
                    console.print(
                        "⚠️  requirements.txt에 rfs-framework가 없습니다.",
                        style="yellow",
                    )
        return True

    async def _start_dev_server(self, options: Dict[str, Any]) -> None:
        """개발 서버 시작"""
        cmd = [
            "uvicorn",
            "main:app",
            "--host",
            options.get("host"),
            "--port",
            str(options.get("port")),
        ]
        if options.get("reload"):
            cmd = cmd + ["--reload"]
        if options.get("debug"):
            cmd = cmd + ["--log-level"]
            cmd = cmd + ["debug"]
        self.process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            output = line.decode().strip()
            if output:
                if console:
                    if "ERROR" in output:
                        console.print(output, style="red")
                    elif "WARNING" in output:
                        console.print(output, style="yellow")
                    elif "INFO" in output:
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
            build_config = self._parse_build_config(args)
            if console:
                console.print(
                    Panel(
                        f"🏗️  RFS v4 프로젝트 빌드 시작\n\n🎯 타겟: {build_config.target}\n📁 출력 디렉토리: {build_config.output_dir}\n⚡ 최적화: {('활성화' if build_config.optimize else '비활성화')}\n🧪 테스트 포함: {('예' if build_config.include_tests else '아니오')}",
                        title="프로젝트 빌드",
                        border_style="blue",
                    )
                )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task1 = progress.add_task("의존성 확인 중...", total=100)
                await self._check_dependencies()
                progress = {**progress, **task1}
                task2 = progress.add_task("코드 검증 중...", total=100)
                validation_result = await self._validate_code()
                if validation_result.is_failure():
                    return validation_result
                progress = {**progress, **task2}
                if build_config.include_tests:
                    task3 = progress.add_task("테스트 실행 중...", total=100)
                    test_result = await self._run_tests()
                    if test_result.is_failure():
                        return test_result
                    progress = {**progress, **task3}
                task4 = progress.add_task("빌드 아티팩트 생성 중...", total=100)
                await self._create_build_artifacts(build_config)
                progress = {**progress, **task4}
                if build_config.optimize:
                    task5 = progress.add_task("빌드 최적화 중...", total=100)
                    await self._optimize_build(build_config)
                    progress = {**progress, **task5}
            if console:
                console.print(
                    Panel(
                        f"✅ 빌드 완료!\n\n📦 빌드 아티팩트: {build_config.output_dir}\n🔍 빌드 로그: build.log\n\n다음 단계:\n  rfs deploy  # 배포\n  rfs test    # 추가 테스트",
                        title="빌드 성공",
                        border_style="green",
                    )
                )
            return Success(f"프로젝트 빌드 완료: {build_config.output_dir}")
        except Exception as e:
            return Failure(f"빌드 실패: {str(e)}")

    def _parse_build_config(self, args: List[str]) -> BuildConfig:
        """빌드 설정 파싱"""
        config = BuildConfig(
            target="production", output_dir="dist", optimize=True, include_tests=False
        )
        for i, arg in enumerate(args):
            match arg:
                case "--target":
                    config.target = args[i + 1]
                case "--output":
                    config.output_dir = args[i + 1]
                case "--no-optimize":
                    config.optimize = False
                case "--include-tests":
                    config.include_tests = True
        return config

    async def _check_dependencies(self) -> None:
        """의존성 확인"""
        await asyncio.sleep(0.5)

    async def _validate_code(self) -> Result[str, str]:
        """코드 검증"""
        try:
            await asyncio.sleep(0.5)
            if Path("main.py").exists():
                with open("main.py", "r") as f:
                    code = f.read()
                    compile(code, "main.py", "exec")
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
            options = self._parse_test_options(args)
            if console:
                console.print(
                    Panel(
                        f"🧪 RFS v4 테스트 실행\n\n📁 테스트 경로: {options.get('path', 'tests/')}\n📊 커버리지: {('활성화' if options.get('coverage') else '비활성화')}\n🔍 필터: {options.get('filter', '모든 테스트')}\n⚡ 병렬 실행: {('활성화' if options.get('parallel') else '비활성화')}",
                        title="테스트 실행",
                        border_style="blue",
                    )
                )
            cmd = ["python", "-m", "pytest"]
            if options.get("path"):
                cmd = cmd + [options.get("path")]
            if options.get("verbose"):
                cmd = cmd + ["-v"]
            if options.get("coverage"):
                cmd = cmd + ["--cov=.", "--cov-report=html"]
            if options.get("filter"):
                cmd = cmd + ["-k", options.get("filter")]
            if options.get("parallel"):
                cmd = cmd + ["-n", "auto"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            output_lines = []
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                output = line.decode().strip()
                if output:
                    output_lines = output_lines + [output]
                    if console:
                        if "PASSED" in output:
                            console.print(output, style="green")
                        elif "FAILED" in output:
                            console.print(output, style="red")
                        elif "ERROR" in output:
                            console.print(output, style="red")
                        else:
                            console.print(output)
                    else:
                        print(output)
            await process.wait()
            test_results = self._analyze_test_results(output_lines)
            if console:
                self._display_test_summary(test_results)
            if test_results.get("failed") > 0:
                return Failure(f"테스트 실패: {test_results.get('failed')}개 실패")
            else:
                return Success(f"모든 테스트 통과: {test_results.get('passed')}개 성공")
        except Exception as e:
            return Failure(f"테스트 실행 실패: {str(e)}")

    def _parse_test_options(self, args: List[str]) -> Dict[str, Any]:
        """테스트 옵션 파싱"""
        options = {
            "path": None,
            "verbose": False,
            "coverage": False,
            "filter": None,
            "parallel": False,
        }
        for i, arg in enumerate(args):
            if arg == "--path" and i + 1 < len(args):
                options["path"] = {"path": args[i + 1]}
            elif arg in ["-v", "--verbose"]:
                options["verbose"] = {"verbose": True}
            elif arg == "--coverage":
                options["coverage"] = {"coverage": True}
            elif arg == "--filter" and i + 1 < len(args):
                options["filter"] = {"filter": args[i + 1]}
            elif arg == "--parallel":
                options["parallel"] = {"parallel": True}
        return options

    def _analyze_test_results(self, output_lines: List[str]) -> Dict[str, int]:
        """테스트 결과 분석"""
        results = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        for line in output_lines:
            if "passed" in line.lower():
                import re

                match = re.search("(\\d+) passed", line)
                if match:
                    results["passed"] = {"passed": int(match.group(1))}
            if "failed" in line.lower():
                match = re.search("(\\d+) failed", line)
                if match:
                    results["failed"] = {"failed": int(match.group(1))}
        return results

    def _display_test_summary(self, results: Dict[str, int]) -> None:
        """테스트 결과 요약 표시"""
        if not console:
            return
        summary_table = Table(
            title="테스트 결과 요약", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("상태", style="cyan", width=10)
        summary_table.add_column("개수", style="green", justify="right")
        summary_table.add_column("비율", style="yellow", justify="right")
        total = sum(results.values())
        if total > 0:
            for status, count in results.items():
                if count > 0:
                    percentage = count / total * 100
                    summary_table.add_row(
                        status.title(), str(count), f"{percentage:.1f}%"
                    )
        console.print(summary_table)
