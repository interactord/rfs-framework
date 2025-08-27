"""
Debug and Utility Commands (RFS v4)

디버깅 및 유틸리티 명령어들
- debug: 디버깅 도구
- status: 시스템 상태 확인
- health: 헬스체크
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.tree import Tree

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


class DebugCommand(Command):
    """디버깅 도구 명령어"""

    name = "debug"
    description = "RFS 애플리케이션 디버깅 도구"

    def __init__(self):
        super().__init__()
        self.debug_tools = {
            "trace": "실행 추적",
            "profile": "성능 프로파일링",
            "memory": "메모리 사용량 분석",
            "config": "설정 정보 확인",
            "dependencies": "의존성 확인",
            "logs": "로그 분석",
        }

    async def execute(self, args: List[str]) -> Result[str, str]:
        """디버깅 도구 실행"""
        try:
            if not args:
                return await self._show_debug_menu()
            tool = args[0].lower()
            if tool not in self.debug_tools:
                return Failure(f"지원하지 않는 디버깅 도구: {tool}")
            if console:
                console.print(
                    Panel(
                        f"🔍 {self.debug_tools[tool]} 실행 중...",
                        title=f"디버깅 도구: {tool}",
                        border_style="yellow",
                    )
                )
            if tool == "trace":
                return await self._debug_trace(args[1:])
            else:
                match tool:
                    case "profile":
                        return await self._debug_profile(args[1:])
                    case "memory":
                        return await self._debug_memory(args[1:])
                    case "config":
                        return await self._debug_config(args[1:])
                    case "dependencies":
                        return await self._debug_dependencies(args[1:])
                    case "logs":
                        return await self._debug_logs(args[1:])
                    case _:
                        return Failure(f"지원하지 않는 디버깅 도구: {tool}")
        except Exception as e:
            return Failure(f"디버깅 실패: {str(e)}")

    async def _show_debug_menu(self) -> Result[str, str]:
        """디버깅 도구 메뉴 표시"""
        if console:
            console.print(
                Panel(
                    "🔍 RFS v4 디버깅 도구", title="디버깅 도구", border_style="yellow"
                )
            )
            debug_table = Table(show_header=True, header_style="bold magenta")
            debug_table.add_column("도구", style="cyan", width=15)
            debug_table.add_column("설명", style="white")
            debug_table.add_column("사용법", style="green")
            for tool, description in self.debug_tools.items():
                debug_table.add_row(tool, description, f"rfs debug {tool}")
            console.print(debug_table)
        return Success("디버깅 도구 메뉴 표시 완료")

    async def _debug_trace(self, args: List[str]) -> Result[str, str]:
        """실행 추적"""
        try:
            target = args[0] if args else "main.py"
            if not Path(target).exists():
                return Failure(f"대상 파일을 찾을 수 없습니다: {target}")
            if console:
                console.print(f"📊 실행 추적 시작: {target}")
            cmd = ["python", "-m", "trace", "--trace", target]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                trace_output = stdout.decode()
                if console:
                    syntax = Syntax(
                        trace_output[:2000],
                        "python",
                        theme="monokai",
                        line_numbers=True,
                    )
                    console.print(Panel(syntax, title="실행 추적 결과"))
                else:
                    print(trace_output[:2000])
                return Success("실행 추적 완료")
            else:
                error_msg = stderr.decode()
                return Failure(f"추적 실행 실패: {error_msg}")
        except Exception as e:
            return Failure(f"추적 실패: {str(e)}")

    async def _debug_profile(self, args: List[str]) -> Result[str, str]:
        """성능 프로파일링"""
        try:
            target = args[0] if args else "main.py"
            if not Path(target).exists():
                return Failure(f"대상 파일을 찾을 수 없습니다: {target}")
            if console:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("성능 프로파일링 실행 중...", total=None)
                    cmd = ["python", "-m", "cProfile", "-s", "cumtime", target]
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await process.communicate()
                    progress.remove_task(task)
                if process.returncode == 0:
                    profile_output = stdout.decode()
                    if console:
                        lines = profile_output.split("\n")
                        profile_table = Table(
                            title="성능 프로파일링 결과", show_header=True
                        )
                        profile_table.add_column("호출 횟수", justify="right")
                        profile_table.add_column("누적 시간", justify="right")
                        profile_table.add_column("함수")
                        for line in lines[5:15]:
                            if line.strip():
                                parts = line.split()
                                if len(parts) >= 6:
                                    profile_table.add_row(
                                        parts[0], parts[3], " ".join(parts[5:])
                                    )
                        console.print(profile_table)
                    else:
                        print(profile_output[:1000])
                    return Success("성능 프로파일링 완료")
                else:
                    error_msg = stderr.decode()
                    return Failure(f"프로파일링 실패: {error_msg}")
        except Exception as e:
            return Failure(f"프로파일링 실패: {str(e)}")


class StatusCommand(Command):
    """시스템 상태 확인 명령어"""

    name = "status"
    description = "RFS 시스템 상태 및 환경 정보 확인"

    async def execute(self, args: List[str]) -> Result[str, str]:
        """시스템 상태 확인"""
        try:
            if console:
                console.print(
                    Panel(
                        "📊 RFS v4 시스템 상태 확인",
                        title="시스템 상태",
                        border_style="blue",
                    )
                )
            status_info = await self._collect_status_info()
            await self._display_status_info(status_info)
            return Success("시스템 상태 확인 완료")
        except Exception as e:
            return Failure(f"상태 확인 실패: {str(e)}")

    async def _collect_status_info(self) -> Dict[str, Any]:
        """시스템 상태 정보 수집"""
        status = {}
        try:
            status = {
                **status,
                "system": {
                    "platform": os.name,
                    "python_version": os.sys.version.split()[0],
                    "cwd": str(Path.cwd()),
                    "timestamp": datetime.now().isoformat(),
                },
            }
            if hasattr(psutil, "virtual_memory"):
                memory = psutil.virtual_memory()
                status = {
                    **status,
                    "resources": {
                        "cpu_percent": psutil.cpu_percent(interval=1),
                        "memory_percent": memory.percent,
                        "memory_total": f"{memory.total / 1024 ** 3:.1f}GB",
                        "memory_used": f"{memory.used / 1024 ** 3:.1f}GB",
                    },
                }
            try:
                config = get_config()
                status = {
                    **status,
                    "rfs_config": {
                        "environment": getattr(config, "environment", "Unknown"),
                        "debug": getattr(config, "debug", False),
                        "log_level": getattr(config, "log_level", "INFO"),
                    },
                }
            except Exception:
                status = {**status, "rfs_config": {"error": "RFS 설정 로드 실패"}}
            status = {
                **status,
                "project": {
                    "name": Path.cwd().name,
                    "main_py_exists": Path("main.py").exists(),
                    "requirements_exists": Path("requirements.txt").exists(),
                    "docker_exists": Path("Dockerfile").exists(),
                    "rfs_config_exists": Path("rfs.yaml").exists(),
                },
            }
            status = {
                **status,
                "dependencies": await self._check_dependencies(),
            }
        except Exception as e:
            status["error"] = str(e)
        return status

    async def _check_dependencies(self) -> Dict[str, Any]:
        """의존성 확인"""
        deps = {}
        try:
            import pkg_resources

            required_packages = ["rfs-framework", "pydantic", "rich"]
            for package in required_packages:
                try:
                    version = pkg_resources.get_distribution(package).version
                    deps[package] = {"version": version, "status": "installed"}
                except pkg_resources.DistributionNotFound:
                    deps[package] = {"version": None, "status": "missing"}

            # Docker 체크
            try:
                process = await asyncio.create_subprocess_exec(
                    "docker",
                    "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                if process.returncode == 0:
                    version_info = stdout.decode().strip()
                    deps["docker"] = {"version": version_info, "status": "available"}
                else:
                    deps["docker"] = {"version": None, "status": "unavailable"}
            except:
                deps["docker"] = {"version": None, "status": "unavailable"}

            # GCloud 체크
            try:
                process = await asyncio.create_subprocess_exec(
                    "gcloud",
                    "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
                deps["gcloud"] = {
                    "version": "installed" if process.returncode == 0 else None,
                    "status": "available" if process.returncode == 0 else "unavailable",
                }
            except:
                deps["gcloud"] = {"version": None, "status": "unavailable"}
        except Exception as e:
            deps["error"] = str(e)
        return deps

    async def _display_status_info(self, status: Dict[str, Any]) -> None:
        """상태 정보 표시"""
        if not console:
            for section, data in status.items():
                print(f"\n{section.upper()}:")
                if isinstance(data, dict):
                    for key, value in data.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {data}")
            return

        if "system" in status:
            system_table = Table(title="시스템 정보", show_header=False)
            system_table.add_column("항목", style="cyan")
            system_table.add_column("값", style="white")
            for key, value in status.get("system", {}).items():
                system_table.add_row(key.replace("_", " ").title(), str(value))
            console.print(system_table)

        if "resources" in status:
            resource_table = Table(title="시스템 리소스", show_header=False)
            resource_table.add_column("리소스", style="cyan")
            resource_table.add_column("사용량", style="white")
            for key, value in status.get("resources", {}).items():
                resource_table.add_row(key.replace("_", " ").title(), str(value))
            console.print(resource_table)

        if "dependencies" in status and isinstance(status.get("dependencies"), dict):
            deps_table = Table(
                title="의존성 상태", show_header=True, header_style="bold magenta"
            )
            deps_table.add_column("패키지", style="cyan")
            deps_table.add_column("버전", style="green")
            deps_table.add_column("상태", style="yellow")
            for package, info in status.get("dependencies", {}).items():
                if isinstance(info, dict) and "status" in info:
                    version = info.get("version", "N/A")
                    status_text = info.get("status", "unknown")
                    if status_text in ["installed", "available"]:
                        status_style = "green"
                    elif status_text in ["missing", "unavailable"]:
                        status_style = "red"
                    else:
                        status_style = "yellow"
                    deps_table.add_row(
                        package,
                        str(version),
                        f"[{status_style}]{status_text}[/{status_style}]",
                    )
            console.print(deps_table)


class HealthCommand(Command):
    """헬스체크 명령어"""

    name = "health"
    description = "RFS 애플리케이션 헬스체크"

    async def execute(self, args: List[str]) -> Result[str, str]:
        """헬스체크 실행"""
        try:
            options = self._parse_health_options(args)
            if console:
                console.print(
                    Panel(
                        f"🏥 RFS v4 헬스체크 실행\n\n🎯 대상: {options.get('target', 'local')}\n🔍 체크 항목: {len(self._get_health_checks())}개\n⚡ 타임아웃: {options.get('timeout', 30)}초",
                        title="헬스체크",
                        border_style="green",
                    )
                )
            health_results = await self._run_health_checks(options)
            await self._display_health_results(health_results)
            all_passed = all(
                result["status"] == "pass" for result in health_results.values()
            )
            if all_passed:
                return Success("모든 헬스체크 통과")
            else:
                failed_checks = [
                    name
                    for name, result in health_results.items()
                    if result.get("status") != "pass"
                ]
                return Failure(f"헬스체크 실패: {', '.join(failed_checks)}")
        except Exception as e:
            return Failure(f"헬스체크 실패: {str(e)}")

    def _parse_health_options(self, args: List[str]) -> Dict[str, Any]:
        """헬스체크 옵션 파싱"""
        options = {"target": "local", "timeout": 30, "detailed": False}
        for i, arg in enumerate(args):
            if arg == "--target" and i + 1 < len(args):
                options["target"] = args[i + 1]
            elif arg == "--timeout" and i + 1 < len(args):
                options["timeout"] = int(args[i + 1])
            elif arg in ["--detailed", "-v"]:
                options["detailed"] = True
        return options

    def _get_health_checks(self) -> List[str]:
        """헬스체크 항목 목록"""
        return [
            "python_environment",
            "rfs_configuration",
            "file_system",
            "memory_usage",
            "dependencies",
            "network_connectivity",
        ]

    async def _run_health_checks(
        self, options: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """헬스체크 실행"""
        results = {}
        checks = self._get_health_checks()
        for check in checks:
            try:
                match check:
                    case "python_environment":
                        result = await self._check_python_environment()
                    case "rfs_configuration":
                        result = await self._check_rfs_configuration()
                    case "file_system":
                        result = await self._check_file_system()
                    case "memory_usage":
                        result = await self._check_memory_usage()
                    case "dependencies":
                        result = await self._check_dependencies_health()
                    case "network_connectivity":
                        result = await self._check_network_connectivity()
                    case _:
                        result = {
                            "status": "skip",
                            "message": "Unknown check",
                        }
                results[check] = result
            except Exception as e:
                results[check] = {
                    "status": "fail",
                    "message": f"Check failed: {str(e)}",
                }
        return results

    async def _check_python_environment(self) -> Dict[str, Any]:
        """Python 환경 체크"""
        import sys

        version = sys.version_info
        if version.major >= 3 and version.minor >= 10:
            return {
                "status": "pass",
                "message": f"Python {version.major}.{version.minor}.{version.micro}",
            }
        else:
            return {
                "status": "fail",
                "message": f"Python 3.10+ 필요 (현재: {version.major}.{version.minor}.{version.micro})",
            }

    async def _display_health_results(self, results: Dict[str, Dict[str, Any]]) -> None:
        """헬스체크 결과 표시"""
        if not console:
            for check, result in results.items():
                status = result["status"].upper()
                message = result["message"]
                print(f"{check}: {status} - {message}")
            return
        health_table = Table(
            title="헬스체크 결과", show_header=True, header_style="bold magenta"
        )
        health_table.add_column("체크 항목", style="cyan", width=20)
        health_table.add_column("상태", style="white", width=10, justify="center")
        health_table.add_column("메시지", style="white")
        for check, result in results.items():
            status = result["status"]
            message = result["message"]
            if status == "pass":
                status_display = "[green]✅ PASS[/green]"
            else:
                match status:
                    case "fail":
                        status_display = "[red]❌ FAIL[/red]"
                    case "warn":
                        status_display = "[yellow]⚠️ WARN[/yellow]"
                    case _:
                        status_display = "[dim]➖ SKIP[/dim]"
            health_table.add_row(
                check.replace("_", " ").title(), status_display, message
            )
        console.print(health_table)
