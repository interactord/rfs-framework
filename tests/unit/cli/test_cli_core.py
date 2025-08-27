"""
Tests for CLI core functionality
"""

import asyncio
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest

from rfs.cli.core import Command, CommandContext, CommandGroup, RFSCli
from rfs.core.result import Failure, Success


class MockCommand(Command):
    """테스트용 Mock 명령어"""

    def __init__(self, name="test", description="Test command", should_fail=False):
        super().__init__(name, description)
        self.should_fail = should_fail
        self.executed = False

    async def execute(self, ctx: CommandContext):
        self.executed = True
        if self.should_fail:
            return Failure("Test failure")
        return Success("Test success")


class TestCommandContext:
    """명령어 컨텍스트 테스트"""

    def test_command_context_creation(self):
        """명령어 컨텍스트 생성 테스트"""
        ctx = CommandContext(
            args={"test": "value"},
            verbose=True,
            dry_run=False,
            environment="test",
        )

        assert ctx.args == {"test": "value"}
        assert ctx.verbose is True
        assert ctx.dry_run is False
        assert ctx.environment == "test"

    def test_command_context_defaults(self):
        """명령어 컨텍스트 기본값 테스트"""
        ctx = CommandContext()

        assert ctx.args == {}
        assert ctx.console is None
        assert ctx.project_root is None
        assert ctx.verbose is False
        assert ctx.dry_run is False
        assert ctx.environment == "development"


class TestCommand:
    """명령어 기본 클래스 테스트"""

    def test_command_creation(self):
        """명령어 생성 테스트"""
        cmd = MockCommand("test", "Test description")

        assert cmd.name == "test"
        assert cmd.description == "Test description"
        assert cmd.aliases == []
        assert cmd.options == {}
        assert cmd.subcommands == {}

    def test_command_add_option(self):
        """명령어 옵션 추가 테스트"""
        cmd = MockCommand()
        result = cmd.add_option("verbose", type=bool, default=False)

        assert result is cmd  # 체이닝 확인
        assert "verbose" in cmd.options
        assert cmd.options["verbose"]["type"] == bool

    def test_command_add_alias(self):
        """명령어 별칭 추가 테스트"""
        cmd = MockCommand()
        result = cmd.add_alias("t")

        assert result is cmd  # 체이닝 확인
        assert "t" in cmd.aliases

    def test_command_add_subcommand(self):
        """서브 명령어 추가 테스트"""
        cmd = MockCommand("parent")
        sub_cmd = MockCommand("child")
        sub_cmd.add_alias("c")

        result = cmd.add_subcommand(sub_cmd)

        assert result is cmd  # 체이닝 확인
        assert "child" in cmd.subcommands
        assert "c" in cmd.subcommands
        assert cmd.subcommands["child"] is sub_cmd
        assert cmd.subcommands["c"] is sub_cmd

    @pytest.mark.asyncio
    async def test_command_execute_success(self):
        """명령어 실행 성공 테스트"""
        cmd = MockCommand()
        ctx = CommandContext()

        result = await cmd.execute(ctx)

        assert isinstance(result, Success)
        assert result.value == "Test success"
        assert cmd.executed is True

    @pytest.mark.asyncio
    async def test_command_execute_failure(self):
        """명령어 실행 실패 테스트"""
        cmd = MockCommand(should_fail=True)
        ctx = CommandContext()

        result = await cmd.execute(ctx)

        assert isinstance(result, Failure)
        assert result.error == "Test failure"


class TestCommandGroup:
    """명령어 그룹 테스트"""

    def test_command_group_creation(self):
        """명령어 그룹 생성 테스트"""
        group = CommandGroup("test-group", "Test group")

        assert group.name == "test-group"
        assert group.description == "Test group"
        assert group._commands == {}

    def test_command_group_add_command(self):
        """명령어 그룹에 명령어 추가 테스트"""
        group = CommandGroup("group")
        cmd = MockCommand("test")
        cmd.add_alias("t")

        result = group.add_command(cmd)

        assert result is group  # 체이닝 확인
        assert "test" in group._commands
        assert "t" in group._commands
        assert group._commands["test"] is cmd
        assert group._commands["t"] is cmd

    def test_command_group_get_command(self):
        """명령어 그룹에서 명령어 조회 테스트"""
        group = CommandGroup("group")
        cmd = MockCommand("test")
        group.add_command(cmd)

        found_cmd = group.get_command("test")
        not_found = group.get_command("nonexistent")

        assert found_cmd is cmd
        assert not_found is None

    @pytest.mark.asyncio
    async def test_command_group_execute_with_console(self):
        """콘솔 있는 명령어 그룹 실행 테스트"""
        group = CommandGroup("group", "Test group")
        mock_console = Mock()
        ctx = CommandContext(console=mock_console)

        result = await group.execute(ctx)

        assert isinstance(result, Success)
        assert result.value == "Help displayed"
        mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_command_group_execute_no_console(self):
        """콘솔 없는 명령어 그룹 실행 테스트"""
        group = CommandGroup("group")
        ctx = CommandContext(console=None)

        with patch("builtins.print") as mock_print:
            result = await group.execute(ctx)

            assert isinstance(result, Success)
            mock_print.assert_called()


class TestRFSCli:
    """RFS CLI 메인 애플리케이션 테스트"""

    def test_rfs_cli_creation(self):
        """RFS CLI 생성 테스트"""
        cli = RFSCli()

        assert cli.commands == {}
        assert cli.plugins == {}
        assert cli.state["command_history"] == []

    @patch("rfs.cli.core.Path.cwd")
    def test_find_project_root_found(self, mock_cwd):
        """프로젝트 루트 찾기 성공 테스트"""
        mock_project_dir = Mock()
        mock_project_dir.parent = Mock()
        mock_project_dir.__truediv__ = Mock(
            side_effect=lambda x: Mock(exists=Mock(return_value=x == "pyproject.toml"))
        )
        mock_cwd.return_value = mock_project_dir

        cli = RFSCli()
        # _find_project_root 메서드를 직접 호출
        result = cli._find_project_root()

        assert result == mock_project_dir

    def test_add_command(self):
        """명령어 추가 테스트"""
        cli = RFSCli()
        cmd = MockCommand("test")
        cmd.add_alias("t")

        result = cli.add_command(cmd)

        assert result is cli  # 체이닝 확인
        assert "test" in cli.commands
        assert "t" in cli.commands
        assert cli.commands["test"] is cmd
        assert cli.commands["t"] is cmd

    def test_add_command_group(self):
        """명령어 그룹 추가 테스트"""
        cli = RFSCli()
        group = CommandGroup("group")

        result = cli.add_command_group(group)

        assert result is cli
        assert "group" in cli.commands

    @pytest.mark.asyncio
    async def test_run_no_args_show_help(self):
        """인자 없이 실행 시 도움말 표시 테스트"""
        cli = RFSCli()

        with patch.object(cli, "_show_main_help", return_value=0) as mock_help:
            result = await cli.run([])

            assert result == 0
            mock_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_command_success(self):
        """명령어 실행 성공 테스트"""
        cli = RFSCli()
        cmd = MockCommand("test")
        cli.add_command(cmd)

        with patch("rfs.cli.core.get_config"), patch("os.chdir"):
            result = await cli.run(["test"])

            assert result == 0
            assert cmd.executed is True

    @pytest.mark.asyncio
    async def test_run_command_failure(self):
        """명령어 실행 실패 테스트"""
        cli = RFSCli()
        cmd = MockCommand("test", should_fail=True)
        cli.add_command(cmd)

        with patch("rfs.cli.core.get_config"), patch("os.chdir"):
            result = await cli.run(["test"])

            assert result == 1

    @pytest.mark.asyncio
    async def test_run_command_not_found(self):
        """존재하지 않는 명령어 실행 테스트"""
        cli = RFSCli()

        with patch.object(
            cli, "_show_command_not_found", return_value=1
        ) as mock_not_found:
            result = await cli.run(["nonexistent"])

            assert result == 1
            mock_not_found.assert_called_with("nonexistent", ANY)

    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(self):
        """키보드 인터럽트 테스트"""
        cli = RFSCli()
        cmd = MockCommand("test")
        cli.add_command(cmd)

        async def raise_keyboard_interrupt(ctx):
            raise KeyboardInterrupt()

        cmd.execute = raise_keyboard_interrupt

        with patch("rfs.cli.core.get_config"), patch("os.chdir"):
            result = await cli.run(["test"])

            assert result == 130

    def test_parse_global_args(self):
        """전역 인자 파싱 테스트"""
        cli = RFSCli()

        global_args, command_args = cli._parse_global_args(
            ["--verbose", "--env", "test", "command", "arg1"]
        )

        assert "verbose" in global_args
        assert "environment" in global_args
        assert command_args == ["command", "arg1"]

    def test_parse_command_args(self):
        """명령어 인자 파싱 테스트"""
        cli = RFSCli()
        cmd = MockCommand("test")

        parsed = cli._parse_command_args(cmd, ["--option", "value", "pos1", "pos2"])

        assert "option" in parsed
        assert "positional" in parsed
        assert parsed["positional"] == ["pos1", "pos2"]

    def test_find_similar_commands(self):
        """유사 명령어 찾기 테스트"""
        cli = RFSCli()
        cli.add_command(MockCommand("status"))
        cli.add_command(MockCommand("start"))

        similar = cli._find_similar_commands("stat")

        # Levenshtein distance 알고리즘에 의한 유사 명령어 확인
        assert len(similar) > 0
        assert "status" in similar or "start" in similar

    def test_register_plugin(self):
        """플러그인 등록 테스트"""
        cli = RFSCli()
        mock_plugin = Mock()
        mock_plugin.register_commands = Mock()

        cli.register_plugin("test_plugin", mock_plugin)

        assert "test_plugin" in cli.plugins
        assert cli.plugins["test_plugin"] is mock_plugin
        mock_plugin.register_commands.assert_called_once_with(cli)

    def test_get_state(self):
        """CLI 상태 조회 테스트"""
        cli = RFSCli()
        state = cli.get_state()

        assert "project_root" in state
        assert "commands_count" in state
        assert "plugins_count" in state
        assert state["commands_count"] == 0
        assert state["plugins_count"] == 0
