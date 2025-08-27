"""
Tests for CLI basic commands
"""

import asyncio
import sys
from unittest.mock import Mock, patch

import pytest

from rfs.cli.commands.basic import (
    ConfigCommand,
    HelpCommand,
    StatusCommand,
    VersionCommand,
)
from rfs.cli.core import CommandContext
from rfs.core.result import Failure, Success


@pytest.fixture
def mock_console():
    """Mock Rich console"""
    return Mock()


@pytest.fixture
def mock_context(mock_console):
    """Mock command context"""
    return CommandContext(
        args={},
        console=mock_console,
        project_root=None,
        verbose=False,
        dry_run=False,
        environment="development",
    )


class TestVersionCommand:
    """버전 명령어 테스트"""

    @pytest.mark.asyncio
    async def test_version_command_success(self, mock_context):
        """버전 명령어 성공 테스트"""
        with patch("rfs.get_framework_info") as mock_info:
            mock_info.return_value = {
                "version": "4.3.0",
                "phase": "Production Ready",
                "total_modules": 16,
                "production_ready": True,
                "cloud_run_ready": True,
            }

            cmd = VersionCommand()
            result = await cmd.execute(mock_context)

            assert isinstance(result, Success)
            assert "v4.3.0" in result.value
            mock_context.console.print.assert_called()

    @pytest.mark.asyncio
    async def test_version_command_no_console(self):
        """콘솔 없이 버전 명령어 테스트"""
        context = CommandContext(
            args={}, console=None, verbose=False, environment="development"
        )

        with (
            patch("rfs.get_framework_info") as mock_info,
            patch("builtins.print") as mock_print,
        ):
            mock_info.return_value = {
                "version": "4.3.0",
                "phase": "Production Ready",
                "total_modules": 16,
                "production_ready": True,
                "cloud_run_ready": True,
            }

            cmd = VersionCommand()
            result = await cmd.execute(context)

            assert isinstance(result, Success)
            mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_version_command_exception(self, mock_context):
        """버전 명령어 예외 처리 테스트"""
        with patch(
            "rfs.get_framework_info",
            side_effect=Exception("Import error"),
        ):
            cmd = VersionCommand()
            result = await cmd.execute(mock_context)

            assert isinstance(result, Failure)
            assert "Failed to get version info" in result.error


class TestStatusCommand:
    """상태 명령어 테스트"""

    @pytest.mark.asyncio
    async def test_status_command_success(self, mock_context):
        """상태 명령어 성공 테스트"""
        cmd = StatusCommand()
        result = await cmd.execute(mock_context)

        assert isinstance(result, Success)
        assert "Status check completed" in result.value
        mock_context.console.print.assert_called()

    @pytest.mark.asyncio
    async def test_status_command_no_console(self):
        """콘솔 없이 상태 명령어 테스트"""
        context = CommandContext(
            args={}, console=None, verbose=False, environment="development"
        )

        with patch("builtins.print") as mock_print:
            cmd = StatusCommand()
            result = await cmd.execute(context)

            assert isinstance(result, Success)
            mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_status_dependencies_check(self, mock_context):
        """의존성 체크 테스트"""
        cmd = StatusCommand()
        deps = cmd._check_dependencies()

        # 기본적으로 설치된 의존성들 확인
        assert "pydantic" in deps
        assert "rich" in deps


class TestConfigCommand:
    """설정 명령어 테스트"""

    @pytest.mark.asyncio
    async def test_config_show_default(self, mock_context):
        """기본 설정 표시 테스트"""
        cmd = ConfigCommand()
        result = await cmd.execute(mock_context)

        assert isinstance(result, Success)
        assert "Configuration displayed" in result.value

    @pytest.mark.asyncio
    async def test_config_show_explicit(self, mock_context):
        """명시적 설정 표시 테스트"""
        mock_context.args = {"positional": ["show"]}
        cmd = ConfigCommand()
        result = await cmd.execute(mock_context)

        assert isinstance(result, Success)

    @pytest.mark.asyncio
    async def test_config_set_requires_args(self, mock_context):
        """설정 설정 기능 인자 필요 테스트"""
        mock_context.args = {"positional": ["set"]}
        cmd = ConfigCommand()
        result = await cmd.execute(mock_context)

        assert isinstance(result, Failure)
        assert "Usage: config set" in result.error

    @pytest.mark.asyncio
    async def test_config_unknown_action(self, mock_context):
        """알 수 없는 설정 액션 테스트"""
        mock_context.args = {"positional": ["unknown"]}
        cmd = ConfigCommand()
        result = await cmd.execute(mock_context)

        assert isinstance(result, Failure)
        assert "Unknown config action" in result.error


class TestHelpCommand:
    """도움말 명령어 테스트"""

    @pytest.mark.asyncio
    async def test_help_command_success(self, mock_context):
        """도움말 명령어 성공 테스트"""
        cmd = HelpCommand()
        result = await cmd.execute(mock_context)

        assert isinstance(result, Success)
        assert "Help displayed" in result.value
        mock_context.console.print.assert_called()

    @pytest.mark.asyncio
    async def test_help_command_no_console(self):
        """콘솔 없이 도움말 명령어 테스트"""
        context = CommandContext(
            args={}, console=None, verbose=False, environment="development"
        )

        with patch("builtins.print") as mock_print:
            cmd = HelpCommand()
            result = await cmd.execute(context)

            assert isinstance(result, Success)
            mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_help_command_exception(self, mock_context):
        """도움말 명령어 예외 처리 테스트"""
        mock_context.console.print.side_effect = Exception("Console error")

        cmd = HelpCommand()
        result = await cmd.execute(mock_context)

        assert isinstance(result, Failure)
        assert "Help display failed" in result.error


class TestCommandAliases:
    """명령어 별칭 테스트"""

    def test_version_aliases(self):
        """버전 명령어 별칭 테스트"""
        cmd = VersionCommand()
        assert "v" in cmd.aliases

    def test_status_aliases(self):
        """상태 명령어 별칭 테스트"""
        cmd = StatusCommand()
        assert "stat" in cmd.aliases

    def test_config_aliases(self):
        """설정 명령어 별칭 테스트"""
        cmd = ConfigCommand()
        assert "cfg" in cmd.aliases

    def test_help_aliases(self):
        """도움말 명령어 별칭 테스트"""
        cmd = HelpCommand()
        assert "h" in cmd.aliases
