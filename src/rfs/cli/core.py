"""
RFS CLI Core System (RFS v4)

CLI 프레임워크 핵심 구현
- 명령어 시스템 및 라우팅
- 인터랙티브 UI 컴포넌트
- 설정 관리 및 상태 추적
- 플러그인 아키텍처
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

try:
    import click
    import rich
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, TaskID
    from rich.prompt import Confirm, Prompt
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None
    click = None
try:
    from pydantic import BaseModel, ConfigDict, Field

    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object
    Field = lambda default=None, **kwargs: default
    PYDANTIC_AVAILABLE = False
from ..core.config import get_config
from ..core.config_profiles import detect_current_environment
from ..core.result import Failure, Result, Success

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """명령어 실행 컨텍스트"""

    args: Dict[str, Any] = field(default_factory=dict)
    config: Any = None
    console: Any = None
    project_root = None
    verbose = False
    dry_run = False
    environment = "development"


class Command(ABC):
    """CLI 명령어 기본 클래스"""

    def __init__(self, name: str, description=""):
        self.name = name
        self.description = description
        self.aliases = []
        self.options = {}
        self.subcommands = {}

    @abstractmethod
    async def execute(self, ctx: CommandContext) -> Result[Any, str]:
        """명령어 실행"""
        pass

    def add_option(self, name: str, **kwargs):
        """옵션 추가"""
        self.options = {**self.options, name: kwargs}
        return self

    def add_alias(self, alias: str):
        """별칭 추가"""
        self.aliases = self.aliases + [alias]
        return self

    def add_subcommand(self, command: "Command"):
        """서브 명령어 추가"""
        self.subcommands = {**self.subcommands, command.name: command}
        for alias in command.aliases:
            self.subcommands = {**self.subcommands, alias: command}
        return self


class CommandGroup(Command):
    """명령어 그룹"""

    def __init__(self, name: str, description=""):
        super().__init__(name, description)
        self._commands = {}

    async def execute(self, ctx: CommandContext) -> Result[Any, str]:
        """그룹 실행 - 도움말 표시"""
        if ctx.console:
            self._show_help(ctx.console)
        else:
            print(f"Available commands in {self.name}:")
            for cmd_name, cmd in self._commands.items():
                print(f"  {cmd_name}: {cmd.description}")
        return Success("Help displayed")

    def add_command(self, command: Command):
        """명령어 추가"""
        self._commands = {**self._commands, command.name: command}
        for alias in command.aliases:
            self._commands = {**self._commands, alias: command}
        return self

    def get_command(self, name: str) -> Optional[Command]:
        """명령어 조회"""
        return self._commands.get(name)

    def _show_help(self, console: Console):
        """도움말 표시"""
        table = Table(title=f"{self.name.upper()} Commands")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Aliases", style="dim")
        for cmd_name, cmd in self._commands.items():
            if cmd_name == cmd.name:
                aliases = ", ".join(cmd.aliases) if cmd.aliases else ""
                table.add_row(cmd_name, cmd.description, aliases)
        console.print(table)


class RFSCli:
    """RFS CLI 메인 애플리케이션"""

    def __init__(self):
        self.commands = {}
        self.console = Console() if RICH_AVAILABLE else None
        self.config = None
        self.project_root = self._find_project_root()
        self.plugins = {}
        self.state = {
            "last_command": None,
            "session_start": datetime.now(),
            "command_history": [],
        }

    def _find_project_root(self) -> Optional[Path]:
        """프로젝트 루트 디렉토리 찾기"""
        current = Path.cwd()
        markers = ["rfs.yaml", "rfs.json", "pyproject.toml", "requirements.txt"]
        while current != current.parent:
            for marker in markers:
                if (current / marker).exists():
                    return current
            current = current.parent
        return None

    def add_command(self, command: Command):
        """명령어 등록"""
        self.commands = {**self.commands, command.name: command}
        for alias in command.aliases:
            self.commands = {**self.commands, alias: command}
        return self

    def add_command_group(self, group: CommandGroup):
        """명령어 그룹 등록"""
        return self.add_command(group)

    async def run(self, args: List[str] = None) -> int:
        """CLI 실행"""
        if args is None:
            args = sys.argv[1:]
        if not args:
            return await self._show_main_help()
        global_args, command_args = self._parse_global_args(args)
        ctx = CommandContext(
            args={},
            console=self.console,
            project_root=self.project_root,
            verbose=global_args.get("verbose", False),
            dry_run=global_args.get("dry_run", False),
            environment=global_args.get("environment", "development"),
        )
        try:
            if self.project_root:
                os.chdir(self.project_root)
            ctx.config = get_config()
        except Exception as e:
            if ctx.console:
                ctx.console.print(
                    f"[yellow]Warning: Could not load config: {e}[/yellow]"
                )
        if not command_args:
            return await self._show_main_help()
        command_name = command_args[0]
        command = self.commands.get(command_name)
        if not command:
            return await self._show_command_not_found(command_name, ctx)
        if len(command_args) > 1 and hasattr(command, "get_command"):
            subcommand_name = command_args[1]
            subcommand = command.get_command(subcommand_name)
            if subcommand:
                command = subcommand
                command_args = command_args[2:]
            else:
                command_args = command_args[1:]
        else:
            command_args = command_args[1:]
        ctx.args = self._parse_command_args(command, command_args)
        try:
            self.state = {**self.state, "last_command": command.name}
            self.state["command_history"] = self.state.get("command_history", []) + [
                {"command": command.name, "args": ctx.args, "timestamp": datetime.now()}
            ]
            result = await command.execute(ctx)
            if isinstance(result, Success):
                if ctx.verbose and result.value:
                    if ctx.console:
                        ctx.console.print(f"[green]✓ {result.value}[/green]")
                return 0
            elif isinstance(result, Failure):
                if ctx.console:
                    ctx.console.print(f"[red]✗ Error: {result.error}[/red]")
                else:
                    print(f"Error: {result.error}")
                return 1
        except KeyboardInterrupt:
            if ctx.console:
                ctx.console.print("\n[yellow]Operation cancelled by user[/yellow]")
            else:
                print("\nOperation cancelled by user")
            return 130
        except Exception as e:
            if ctx.console:
                ctx.console.print(f"[red]✗ Unexpected error: {e}[/red]")
            else:
                print(f"Unexpected error: {e}")
            if ctx.verbose:
                import traceback

                traceback.print_exc()
            return 1

    def _parse_global_args(self, args: List[str]) -> tuple[Dict[str, Any], List[str]]:
        """전역 인자 파싱"""
        global_args = {}
        command_args = []
        i = 0
        while i < len(args):
            arg = args[i]
            match arg:
                case "--verbose" | "-v":
                    global_args["verbose"] = True
                case "--dry-run":
                    global_args["dry_run"] = True
                case "--env" | "--environment":
                    if i + 1 < len(args):
                        global_args["environment"] = args[i + 1]
                        i = i + 1
                    else:
                        raise ValueError("--environment requires a value")
                case _:
                    if arg.startswith("-"):
                        command_args = command_args + args[i:]
                        break
                    else:
                        command_args = command_args + args[i:]
                        break
            i = i + 1
        return (global_args, command_args)

    def _parse_command_args(self, command: Command, args: List[str]) -> Dict[str, Any]:
        """명령어 인자 파싱"""
        parsed_args = {}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("--"):
                option_name = arg[2:]
                if i + 1 < len(args) and (not args[i + 1].startswith("-")):
                    parsed_args[option_name] = args[i + 1]
                    i = i + 1
                else:
                    parsed_args[option_name] = True
            elif arg.startswith("-"):
                option_name = arg[1:]
                if i + 1 < len(args) and (not args[i + 1].startswith("-")):
                    parsed_args[option_name] = args[i + 1]
                    i = i + 1
                else:
                    parsed_args[option_name] = True
            else:
                if "positional" not in parsed_args:
                    parsed_args["positional"] = []
                parsed_args["positional"].append(arg)
            i = i + 1
        return parsed_args

    async def _show_main_help(self) -> int:
        """메인 도움말 표시"""
        if self.console:
            self._show_rich_help()
        else:
            self._show_plain_help()
        return 0

    def _show_rich_help(self):
        """Rich를 사용한 도움말"""
        logo = Text("RFS Framework v4.3.0", style="bold blue")
        self.console.print(Panel(logo, title="🚀 RFS Framework CLI"))
        table = Table(title="Available Commands")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Aliases", style="dim")
        for cmd_name, cmd in self.commands.items():
            if cmd_name == cmd.name:
                aliases = ", ".join(cmd.aliases) if cmd.aliases else ""
                table.add_row(cmd_name, cmd.description, aliases)
        self.console.print(table)
        self.console.print("\n[bold]Global Options:[/bold]")
        self.console.print("  --verbose, -v     Enable verbose output")
        self.console.print(
            "  --dry-run         Show what would be done without executing"
        )
        self.console.print(
            "  --env ENV         Set environment (development, test, production)"
        )
        if self.project_root:
            self.console.print(f"\n[dim]Project root: {self.project_root}[/dim]")
        else:
            self.console.print(
                f"\n[yellow]No RFS project detected in current directory[/yellow]"
            )

    def _show_plain_help(self):
        """일반 텍스트 도움말"""
        print("RFS Framework v4.3.0 CLI")
        print("=" * 25)
        print("\nAvailable Commands:")
        for cmd_name, cmd in self.commands.items():
            if cmd_name == cmd.name:
                print(f"  {cmd_name:<15} {cmd.description}")
        print("\nGlobal Options:")
        print("  --verbose, -v     Enable verbose output")
        print("  --dry-run         Show what would be done without executing")
        print("  --env ENV         Set environment")
        if self.project_root:
            print(f"\nProject root: {self.project_root}")

    async def _show_command_not_found(
        self, command_name: str, ctx: CommandContext
    ) -> int:
        """명령어를 찾을 수 없을 때"""
        similar_commands = self._find_similar_commands(command_name)
        if ctx.console:
            ctx.console.print(f"[red]✗ Command '{command_name}' not found[/red]")
            if similar_commands:
                ctx.console.print(f"\n[yellow]Did you mean:[/yellow]")
                for cmd in similar_commands:
                    ctx.console.print(f"  {cmd}")
            ctx.console.print(
                f"\n[dim]Run 'rfs --help' to see all available commands[/dim]"
            )
        else:
            print(f"Command '{command_name}' not found")
            if similar_commands:
                print("\nDid you mean:")
                for cmd in similar_commands:
                    print(f"  {cmd}")
        return 1

    def _find_similar_commands(self, command_name: str) -> List[str]:
        """유사한 명령어 찾기 (Levenshtein distance 사용)"""

        def levenshtein_distance(s1: str, s2: str) -> int:
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)
            previous_row = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]

        similar = []
        for cmd_name in self.commands.keys():
            if cmd_name != command_name:
                distance = levenshtein_distance(command_name.lower(), cmd_name.lower())
                if distance <= 2:
                    similar.append(cmd_name)
        return similar[:3]

    def register_plugin(self, name: str, plugin: Any):
        """플러그인 등록"""
        self.plugins = {**self.plugins, name: plugin}
        if hasattr(plugin, "register_commands"):
            plugin.register_commands(self)

    def get_state(self) -> Dict[str, Any]:
        """CLI 상태 조회"""
        return {
            **self.state,
            "project_root": str(self.project_root) if self.project_root else None,
            "commands_count": len(self.commands),
            "plugins_count": len(self.plugins),
        }


def create_progress_bar() -> Optional[Progress]:
    """진행률 표시줄 생성"""
    if RICH_AVAILABLE:
        return Progress()
    return None


def prompt_user(message: str, default: str = None) -> str:
    """사용자 입력 받기"""
    if RICH_AVAILABLE:
        return Prompt.ask(message, default=default)
    else:
        prompt_text = f"{message}"
        if default:
            prompt_text = prompt_text + f" [{default}]"
        prompt_text = prompt_text + ": "
        response = input(prompt_text).strip()
        return response or default or ""


def confirm_user(message: str, default=False) -> bool:
    """사용자 확인 받기"""
    if RICH_AVAILABLE:
        return Confirm.ask(message, default=default)
    else:
        prompt_text = f'{message} ({"Y/n" if default else "y/N"}): '
        response = input(prompt_text).strip().lower()
        if not response:
            return default
        return response in ["y", "yes", "true", "1"]


def print_success(message: str, console: Console = None):
    """성공 메시지 출력"""
    if console and RICH_AVAILABLE:
        console.print(f"[green]✓ {message}[/green]")
    else:
        print(f"✓ {message}")


def print_error(message: str, console: Console = None):
    """에러 메시지 출력"""
    if console and RICH_AVAILABLE:
        console.print(f"[red]✗ {message}[/red]")
    else:
        print(f"✗ {message}")


def print_warning(message: str, console: Console = None):
    """경고 메시지 출력"""
    if console and RICH_AVAILABLE:
        console.print(f"[yellow]⚠ {message}[/yellow]")
    else:
        print(f"⚠ {message}")


def print_info(message: str, console: Console = None):
    """정보 메시지 출력"""
    if console and RICH_AVAILABLE:
        console.print(f"[blue]ℹ {message}[/blue]")
    else:
        print(f"ℹ {message}")


cli_app = RFSCli()
