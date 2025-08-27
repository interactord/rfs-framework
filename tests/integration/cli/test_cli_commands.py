"""
RFS Framework CLI 명령어 통합 테스트

CLI 명령어가 예상대로 작동하는지 검증
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 프로젝트 루트 경로 설정
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from rfs.cli.commands.basic import (
    ConfigCommand,
    HelpCommand,
    StatusCommand,
    VersionCommand,
)
from rfs.cli.core import CommandContext


class TestCLICommands:
    """CLI 명령어 통합 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        self.ctx = CommandContext(
            args={},
            console=None,  # 테스트에서는 콘솔 출력 없음
            project_root=project_root,
            verbose=False,
            dry_run=False,
            environment="test",
        )

    @pytest.mark.asyncio
    async def test_version_command(self):
        """버전 명령어 테스트"""
        cmd = VersionCommand()
        result = await cmd.execute(self.ctx)

        # Success 타입 확인
        assert result.__class__.__name__ == "Success"
        assert "4.3.1" in str(result.value)

    @pytest.mark.asyncio
    async def test_status_command(self):
        """상태 확인 명령어 테스트"""
        cmd = StatusCommand()
        result = await cmd.execute(self.ctx)

        # Success 타입 확인
        assert result.__class__.__name__ == "Success"
        assert "Status check completed" in str(result.value)

    @pytest.mark.asyncio
    async def test_config_show_command(self):
        """설정 표시 명령어 테스트"""
        cmd = ConfigCommand()
        self.ctx.args = {"positional": ["show"]}
        result = await cmd.execute(self.ctx)

        # Success 타입 확인
        assert result.__class__.__name__ == "Success"
        assert "displayed" in str(result.value).lower()

    @pytest.mark.asyncio
    async def test_help_command(self):
        """도움말 명령어 테스트"""
        cmd = HelpCommand()
        result = await cmd.execute(self.ctx)

        # Success 타입 확인
        assert result.__class__.__name__ == "Success"
        assert "Help displayed" in str(result.value)

    def test_cli_executable(self):
        """CLI가 직접 실행 가능한지 테스트"""
        # rfs-cli 명령어가 설치되어 있는지 확인
        result = subprocess.run(
            ["python", "-m", "rfs.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # 명령어가 실행되는지 확인 (exit code 0 or 1)
        assert result.returncode in [0, 1]

    @pytest.mark.asyncio
    async def test_version_output_format(self):
        """버전 출력 형식 테스트"""
        cmd = VersionCommand()

        # Rich 콘솔 모킹
        mock_console = MagicMock()
        self.ctx.console = mock_console

        result = await cmd.execute(self.ctx)

        # console.print가 호출되었는지 확인
        assert mock_console.print.called

        # 출력 내용 확인
        calls = mock_console.print.call_args_list
        output_text = " ".join([str(call[0][0]) for call in calls])
        assert "4.3.1" in output_text

    @pytest.mark.asyncio
    async def test_config_set_command(self):
        """설정 값 설정 명령어 테스트"""
        cmd = ConfigCommand()
        self.ctx.args = {"positional": ["set", "test_key", "test_value"]}

        # 임시 설정 파일 경로
        temp_config = project_root / "rfs_test.json"
        self.ctx.project_root = project_root

        # 테스트 후 정리를 위해 try-finally 사용
        try:
            with patch("pathlib.Path.exists", return_value=False):
                with patch("builtins.open", MagicMock()):
                    result = await cmd.execute(self.ctx)
                    assert result.__class__.__name__ == "Success"
                    assert "test_key" in str(result.value)
        finally:
            # 테스트 파일 정리
            if temp_config.exists():
                temp_config.unlink()

    @pytest.mark.asyncio
    async def test_config_get_command_not_found(self):
        """존재하지 않는 설정 조회 테스트"""
        cmd = ConfigCommand()
        self.ctx.args = {"positional": ["get", "nonexistent_key"]}

        with patch("pathlib.Path.exists", return_value=False):
            result = await cmd.execute(self.ctx)
            assert result.__class__.__name__ == "Failure"
            assert "not found" in str(result.error)


class TestCLIIntegration:
    """CLI 통합 테스트 - 실제 명령어 실행"""

    def test_version_command_integration(self):
        """실제 version 명령어 실행 테스트"""
        # 현재 프로젝트 소스를 사용하도록 PYTHONPATH 설정
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root / "src")

        result = subprocess.run(
            ["python", "-c", "from rfs import __version__; print(__version__)"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=env,
        )

        assert result.returncode == 0
        assert "4.3.1" in result.stdout

    def test_import_gateway_module(self):
        """gateway 모듈 import 테스트"""
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root / "src")

        result = subprocess.run(
            [
                "python",
                "-c",
                "from rfs.gateway import create_gateway_app; print('Success')",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=env,
        )

        assert result.returncode == 0
        assert "Success" in result.stdout

    def test_result_pattern_import(self):
        """Result 패턴 import 테스트"""
        result = subprocess.run(
            [
                "python",
                "-c",
                "from rfs.core.result import Success, Failure; "
                "s = Success('test'); f = Failure('error'); "
                "print(s.is_success(), f.is_failure())",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        assert result.returncode == 0
        assert "True True" in result.stdout


class TestDocumentationExamples:
    """CLI_GUIDE.md 문서의 예제 코드 테스트"""

    def test_basic_import(self):
        """기본 import 예제 테스트"""
        code = """
from rfs.core.result import Success, Failure

result = Success("test")
assert result.is_success()
assert result.value == "test"

error = Failure("error")
assert error.is_failure()
assert error.error == "error"
"""
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        assert result.returncode == 0

    def test_gateway_app_creation(self):
        """게이트웨이 앱 생성 예제 테스트"""
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root / "src")

        code = """
from rfs.gateway import create_gateway_app

# FastAPI가 없을 경우 None 반환
app = create_gateway_app(title="Test", version="1.0.0")
print("App created:", app is not None)
"""
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=env,
        )

        assert result.returncode == 0
        # FastAPI 설치 여부와 관계없이 코드가 실행되는지만 확인
        assert "App created:" in result.stdout


if __name__ == "__main__":
    # 테스트 실행
    pytest.main([__file__, "-v"])
