"""
RFS Framework CLI 유닛 테스트

개별 CLI 컴포넌트의 단위 테스트
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# 프로젝트 루트 경로 설정
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from rfs import __version__
from rfs.cli.core import Command, CommandContext, RFSCli
from rfs.core.result import Failure, Success


class TestVersionConsistency:
    """버전 일관성 테스트"""

    def test_version_number(self):
        """__version__이 올바른지 확인"""
        assert __version__ == "4.3.1"

    def test_version_in_init(self):
        """__init__.py의 버전이 올바른지 확인"""
        init_file = project_root / "src" / "rfs" / "__init__.py"
        with open(init_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert '__version__ = "4.3.1"' in content
        assert "Version: 4.3.1 (Production Ready)" in content


class TestCLICore:
    """CLI 핵심 기능 테스트"""

    def test_cli_initialization(self):
        """CLI 초기화 테스트"""
        cli = RFSCli()
        assert cli is not None
        assert cli.commands == {}
        assert cli.plugins == {}

    def test_command_registration(self):
        """명령어 등록 테스트"""
        cli = RFSCli()

        # 모의 명령어 생성
        class MockCommand(Command):
            async def execute(self, ctx):
                return Success("Test executed")

        mock_cmd = MockCommand("test", "Test command")
        cli.add_command(mock_cmd)

        assert "test" in cli.commands
        assert cli.commands["test"] == mock_cmd

    def test_command_with_aliases(self):
        """별칭이 있는 명령어 테스트"""
        cli = RFSCli()

        class MockCommand(Command):
            async def execute(self, ctx):
                return Success("Test executed")

        mock_cmd = MockCommand("test", "Test command")
        mock_cmd.add_alias("t")
        mock_cmd.add_alias("tst")

        cli.add_command(mock_cmd)

        # 모든 별칭이 등록되었는지 확인
        assert cli.commands.get("test") == mock_cmd
        assert cli.commands.get("t") == mock_cmd
        assert cli.commands.get("tst") == mock_cmd

    def test_command_context_creation(self):
        """CommandContext 생성 테스트"""
        ctx = CommandContext(
            args={"key": "value"}, verbose=True, dry_run=False, environment="test"
        )

        assert ctx.args == {"key": "value"}
        assert ctx.verbose is True
        assert ctx.dry_run is False
        assert ctx.environment == "test"

    @pytest.mark.asyncio
    async def test_global_args_parsing(self):
        """전역 인자 파싱 테스트"""
        cli = RFSCli()

        # 다양한 인자 조합 테스트
        test_cases = [
            (["--verbose", "version"], {"verbose": True}, ["version"]),
            (["--dry-run", "status"], {"dry_run": True}, ["status"]),
            (
                ["--env", "production", "config"],
                {"environment": "production"},
                ["config"],
            ),
            (["-v", "help"], {"verbose": True}, ["help"]),
        ]

        for args, expected_global, expected_command in test_cases:
            global_args, command_args = cli._parse_global_args(args)
            assert global_args == expected_global
            assert command_args == expected_command


class TestGatewayModule:
    """Gateway 모듈 테스트"""

    def test_gateway_imports(self):
        """Gateway 모듈 import 테스트"""
        from rfs.gateway import GraphQLGateway  # 플레이스홀더 클래스
        from rfs.gateway import (
            RestGateway,
            create_gateway_app,
        )

        assert RestGateway is not None
        assert create_gateway_app is not None
        assert GraphQLGateway is not None

    def test_create_gateway_app_without_fastapi(self):
        """FastAPI 없이 게이트웨이 앱 생성 테스트"""
        # 먼저 정상적으로 import
        # fastapi 모듈 import를 실패하도록 mock
        # sys.modules를 수정하여 fastapi가 없는 것처럼 만듦
        import sys

        from rfs.gateway import create_gateway_app

        original_fastapi = sys.modules.get("fastapi")

        # fastapi를 임시로 제거
        if "fastapi" in sys.modules:
            del sys.modules["fastapi"]

        try:
            with patch("builtins.print") as mock_print:
                # create_gateway_app 내부의 try-except가 ImportError를 처리
                app = create_gateway_app()
                assert app is None
                # print가 호출되었는지 확인
                assert mock_print.called
                # 올바른 메시지가 출력되었는지 확인
                print_args = mock_print.call_args[0][0]
                assert "FastAPI not installed" in print_args
                assert "pip install fastapi" in print_args
        finally:
            # fastapi 모듈 복원
            if original_fastapi is not None:
                sys.modules["fastapi"] = original_fastapi


class TestConfigCommand:
    """Config 명령어 유닛 테스트"""

    @pytest.mark.asyncio
    async def test_config_set_creates_file(self):
        """설정 파일 생성 테스트"""
        from rfs.cli.commands.basic import ConfigCommand

        cmd = ConfigCommand()
        ctx = CommandContext(
            args={"positional": ["set", "test_key", "test_value"]},
            project_root=Path("/tmp"),
            verbose=False,
        )

        mock_data = {}

        with patch("builtins.open", mock_open()) as mock_file:
            with patch("json.dump") as mock_json_dump:
                with patch("pathlib.Path.exists", return_value=False):
                    result = await cmd.execute(ctx)

                    assert result.__class__.__name__ == "Success"
                    assert "test_key" in str(result.value)
                    mock_json_dump.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_get_existing_key(self):
        """존재하는 설정 키 조회 테스트"""
        from rfs.cli.commands.basic import ConfigCommand

        cmd = ConfigCommand()
        ctx = CommandContext(
            args={"positional": ["get", "existing_key"]},
            project_root=Path("/tmp"),
            verbose=False,
        )

        mock_config = {"existing_key": "existing_value"}

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            with patch("pathlib.Path.exists", return_value=True):
                result = await cmd.execute(ctx)

                assert result.__class__.__name__ == "Success"
                assert "existing_key" in str(result.value)
                assert "existing_value" in str(result.value)

    @pytest.mark.asyncio
    async def test_config_list_empty(self):
        """빈 설정 목록 테스트"""
        from rfs.cli.commands.basic import ConfigCommand

        cmd = ConfigCommand()
        ctx = CommandContext(
            args={"positional": ["list"]}, project_root=Path("/tmp"), verbose=False
        )

        with patch("pathlib.Path.exists", return_value=False):
            result = await cmd.execute(ctx)

            assert result.__class__.__name__ == "Success"
            assert "No configuration file found" in str(result.value)


class TestResultPattern:
    """Result 패턴 테스트"""

    def test_success_creation(self):
        """Success 생성 테스트"""
        result = Success("test value")
        assert result.is_success()
        assert not result.is_failure()
        assert result.value == "test value"

    def test_failure_creation(self):
        """Failure 생성 테스트"""
        result = Failure("error message")
        assert result.is_failure()
        assert not result.is_success()
        assert result.error == "error message"

    def test_result_unwrap(self):
        """Result unwrap 테스트"""
        success = Success("value")
        assert success.unwrap() == "value"

        failure = Failure("error")
        with pytest.raises(ValueError):
            failure.unwrap()

    def test_result_unwrap_or(self):
        """Result unwrap_or 테스트"""
        success = Success("value")
        assert success.unwrap_or("default") == "value"

        failure = Failure("error")
        assert failure.unwrap_or("default") == "default"


class TestDocumentationAccuracy:
    """문서 정확성 테스트"""

    def test_cli_guide_version(self):
        """CLI_GUIDE.md의 버전이 정확한지 테스트"""
        cli_guide = project_root / "CLI_GUIDE.md"
        if cli_guide.exists():
            with open(cli_guide, "r", encoding="utf-8") as f:
                content = f.read()

            assert "v4.3.1" in content
            assert "RFS Framework v4.3.1" in content

    def test_pyproject_version(self):
        """pyproject.toml의 버전이 정확한지 테스트"""
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "r", encoding="utf-8") as f:
                content = f.read()

            assert 'version = "4.3.1"' in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
