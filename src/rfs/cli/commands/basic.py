"""
Basic CLI Commands - 기본 CLI 명령어들

RFS Framework의 기본적인 CLI 명령어 구현
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

from ...core.result import Failure, Result, Success
from ..core import Command, CommandContext


class VersionCommand(Command):
    """버전 정보 표시"""

    def __init__(self):
        super().__init__("version", "Show RFS Framework version information")
        self.add_alias("v")

    async def execute(self, ctx: CommandContext) -> Result[str, str]:
        """버전 정보 실행"""
        try:
            from ... import __version__, get_framework_info

            info = get_framework_info()
            if ctx.console:
                ctx.console.print(
                    f"[bold green]RFS Framework v{info.get('version')}[/bold green]"
                )
                ctx.console.print(f"Phase: {info.get('phase')}")
                ctx.console.print(
                    f"Python: {sys.version_info.major}.{sys.version_info.minor}"
                )
                ctx.console.print(f"Modules: {info.get('total_modules')}")
                ctx.console.print(
                    f"Production Ready: {('✅' if info.get('production_ready') else '❌')}"
                )
                ctx.console.print(
                    f"Cloud Run Ready: {('✅' if info.get('cloud_run_ready') else '❌')}"
                )
            else:
                print(f"RFS Framework v{info.get('version')}")
                print(f"Phase: {info.get('phase')}")
                print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")
            return Success(f"RFS Framework v{info.get('version')}")
        except Exception as e:
            return Failure(f"Failed to get version info: {str(e)}")


class StatusCommand(Command):
    """시스템 상태 확인"""

    def __init__(self):
        super().__init__("status", "Check RFS Framework system status")
        self.add_alias("stat")

    async def execute(self, ctx: CommandContext) -> Result[str, str]:
        """상태 확인 실행"""
        try:
            status = {
                "framework": "OK",
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "project_root": (
                    str(ctx.project_root) if ctx.project_root else "Not detected"
                ),
                "environment": ctx.environment,
                "dependencies": self._check_dependencies(),
            }
            if ctx.console:
                ctx.console.print("[bold]RFS Framework Status[/bold]")
                ctx.console.print(
                    f"Framework: [green]{status.get('framework')}[/green]"
                )
                ctx.console.print(
                    f"Python: [blue]{status.get('python_version')}[/blue]"
                )
                ctx.console.print(
                    f"Project: [yellow]{status.get('project_root')}[/yellow]"
                )
                ctx.console.print(
                    f"Environment: [cyan]{status.get('environment')}[/cyan]"
                )
                ctx.console.print("\n[bold]Dependencies:[/bold]")
                for dep, available in status.get("dependencies").items():
                    icon = "✅" if available else "❌"
                    ctx.console.print(f"  {icon} {dep}")
            else:
                print("RFS Framework Status")
                print(f"Framework: {status.get('framework')}")
                print(f"Python: {status.get('python_version')}")
                print(f"Project: {status.get('project_root')}")
            return Success("Status check completed")
        except Exception as e:
            return Failure(f"Status check failed: {str(e)}")

    def _check_dependencies(self) -> Dict[str, bool]:
        """의존성 확인"""
        deps = {}
        try:
            import pydantic

            deps["pydantic"] = {"pydantic": True}
        except ImportError:
            deps["pydantic"] = {"pydantic": False}
        try:
            import rich

            deps["rich"] = {"rich": True}
        except ImportError:
            deps["rich"] = {"rich": False}
        try:
            import fastapi

            deps["fastapi"] = {"fastapi": True}
        except ImportError:
            deps["fastapi"] = {"fastapi": False}
        try:
            from google.cloud import run_v2

            deps["google-cloud-run"] = {"google-cloud-run": True}
        except ImportError:
            deps["google-cloud-run"] = {"google-cloud-run": False}
        return deps


class ConfigCommand(Command):
    """설정 관리"""

    def __init__(self):
        super().__init__("config", "Manage RFS Framework configuration")
        self.add_alias("cfg")

    async def execute(self, ctx: CommandContext) -> Result[str, str]:
        """설정 명령어 실행"""
        try:
            action = (
                ctx.args.get("positional", ["show"])[0]
                if ctx.args.get("positional")
                else "show"
            )
            match action:
                case "show":
                    return await self._show_config(ctx)
                case "set":
                    return await self._set_config(ctx)
                case "get":
                    return await self._get_config(ctx)
                case "list":
                    return await self._list_config(ctx)
                case _:
                    return Failure(f"Unknown config action: {action}")
        except Exception as e:
            return Failure(f"Config command failed: {str(e)}")

    async def _show_config(self, ctx: CommandContext) -> Result[str, str]:
        """설정 표시"""
        try:
            if ctx.console:
                ctx.console.print("[bold]RFS Configuration[/bold]")
                ctx.console.print(f"Environment: [cyan]{ctx.environment}[/cyan]")
                ctx.console.print(
                    f"Project Root: [yellow]{ctx.project_root or 'None'}[/yellow]"
                )
                ctx.console.print(f"Verbose: [green]{ctx.verbose}[/green]")
                ctx.console.print(f"Dry Run: [yellow]{ctx.dry_run}[/yellow]")
            else:
                print("RFS Configuration")
                print(f"Environment: {ctx.environment}")
                print(f"Project Root: {ctx.project_root or 'None'}")
            return Success("Configuration displayed")
        except Exception as e:
            return Failure(f"Failed to show config: {str(e)}")

    async def _set_config(self, ctx: CommandContext) -> Result[str, str]:
        """설정 값 설정"""
        try:
            args = ctx.args.get("positional", [])
            if len(args) < 3:  # set key value 형태
                return Failure("Usage: config set <key> <value>")

            key = args[1]
            value = args[2]

            # 설정 파일 경로 결정
            config_file = (
                ctx.project_root / "rfs.json" if ctx.project_root else Path("rfs.json")
            )

            # 기존 설정 로드
            config_data = {}
            if config_file.exists():
                import json

                with open(config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

            # 설정 값 업데이트
            config_data[key] = value

            # 설정 파일 저장
            with open(config_file, "w", encoding="utf-8") as f:
                import json

                json.dump(config_data, f, indent=2, ensure_ascii=False)

            if ctx.console:
                ctx.console.print(f"[green]✓ Set {key} = {value}[/green]")
            else:
                print(f"✓ Set {key} = {value}")

            return Success(f"Configuration '{key}' set to '{value}'")
        except Exception as e:
            return Failure(f"Failed to set config: {str(e)}")

    async def _get_config(self, ctx: CommandContext) -> Result[str, str]:
        """설정 값 조회"""
        try:
            args = ctx.args.get("positional", [])
            if len(args) < 2:  # get key 형태
                return Failure("Usage: config get <key>")

            key = args[1]

            # 설정 파일에서 값 조회
            config_file = (
                ctx.project_root / "rfs.json" if ctx.project_root else Path("rfs.json")
            )

            if not config_file.exists():
                return Failure(f"Configuration file not found: {config_file}")

            import json

            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            if key not in config_data:
                return Failure(f"Configuration key '{key}' not found")

            value = config_data[key]

            if ctx.console:
                ctx.console.print(f"[cyan]{key}[/cyan] = [yellow]{value}[/yellow]")
            else:
                print(f"{key} = {value}")

            return Success(f"Configuration '{key}' = '{value}'")
        except Exception as e:
            return Failure(f"Failed to get config: {str(e)}")

    async def _list_config(self, ctx: CommandContext) -> Result[str, str]:
        """설정 목록 표시"""
        try:
            # 설정 파일에서 모든 설정 조회
            config_file = (
                ctx.project_root / "rfs.json" if ctx.project_root else Path("rfs.json")
            )

            if not config_file.exists():
                if ctx.console:
                    ctx.console.print("[yellow]No configuration file found[/yellow]")
                else:
                    print("No configuration file found")
                return Success("No configuration file found")

            import json

            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            if not config_data:
                if ctx.console:
                    ctx.console.print("[yellow]Configuration file is empty[/yellow]")
                else:
                    print("Configuration file is empty")
                return Success("Configuration file is empty")

            if ctx.console:
                from rich.table import Table

                table = Table(title="RFS Configuration")
                table.add_column("Key", style="cyan", no_wrap=True)
                table.add_column("Value", style="yellow")

                for key, value in config_data.items():
                    table.add_row(key, str(value))

                ctx.console.print(table)
            else:
                print("RFS Configuration:")
                for key, value in config_data.items():
                    print(f"  {key} = {value}")

            return Success(f"Listed {len(config_data)} configuration items")
        except Exception as e:
            return Failure(f"Failed to list config: {str(e)}")


class HelpCommand(Command):
    """도움말 표시"""

    def __init__(self):
        super().__init__("help", "Show help information")
        self.add_alias("h")

    async def execute(self, ctx: CommandContext) -> Result[str, str]:
        """도움말 실행"""
        try:
            if ctx.console:
                ctx.console.print("[bold green]RFS Framework CLI v4.3.0[/bold green]")
                ctx.console.print(
                    "Enterprise-Grade Reactive Functional Serverless Framework"
                )
                ctx.console.print("\n[bold]Available Commands:[/bold]")
                ctx.console.print("  [cyan]version[/cyan]  - Show version information")
                ctx.console.print("  [cyan]status[/cyan]   - Check system status")
                ctx.console.print("  [cyan]config[/cyan]   - Manage configuration")
                ctx.console.print("  [cyan]help[/cyan]     - Show this help message")
                ctx.console.print("\n[bold]Global Options:[/bold]")
                ctx.console.print(
                    "  [yellow]--verbose, -v[/yellow]     Enable verbose output"
                )
                ctx.console.print(
                    "  [yellow]--dry-run[/yellow]         Show what would be done"
                )
                ctx.console.print(
                    "  [yellow]--env ENV[/yellow]         Set environment"
                )
            else:
                print("RFS Framework CLI v4.3.0")
                print("Available Commands:")
                print("  version  - Show version information")
                print("  status   - Check system status")
                print("  config   - Manage configuration")
                print("  help     - Show this help message")
            return Success("Help displayed")
        except Exception as e:
            return Failure(f"Help display failed: {str(e)}")
