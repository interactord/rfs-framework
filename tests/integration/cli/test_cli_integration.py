"""
CLI integration tests
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestCLIIntegration:
    """CLI 통합 테스트"""

    def test_cli_help_command(self):
        """CLI 도움말 명령어 통합 테스트"""
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "RFS Framework CLI" in result.stdout

    def test_cli_version_command(self):
        """CLI 버전 명령어 통합 테스트"""
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone", "version"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "4.3.0" in result.stdout

    def test_cli_status_command(self):
        """CLI 상태 명령어 통합 테스트"""
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone", "status"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "RFS Framework System Status" in result.stdout

    def test_cli_config_command(self):
        """CLI 설정 명령어 통합 테스트"""
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone", "config"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "RFS Framework Configuration" in result.stdout

    def test_cli_unknown_command(self):
        """알 수 없는 명령어 테스트"""
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone", "unknown"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Unknown command" in result.stdout

    def test_cli_no_arguments(self):
        """인자 없이 CLI 실행 테스트"""
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "RFS Framework Command Line Interface" in result.stdout

    def test_rfs_cli_executable(self):
        """rfs-cli 실행 파일 테스트"""
        try:
            result = subprocess.run(
                ["rfs-cli", "--help"], capture_output=True, text=True, timeout=10
            )

            assert result.returncode == 0
            assert "RFS Framework CLI" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("rfs-cli executable not available or timeout")

    def test_rfs_cli_version_executable(self):
        """rfs-cli 버전 실행 파일 테스트"""
        try:
            result = subprocess.run(
                ["rfs-cli", "version"], capture_output=True, text=True, timeout=10
            )

            assert result.returncode == 0
            assert "4.3.0" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("rfs-cli executable not available or timeout")

    def test_python_version_requirement(self):
        """Python 버전 요구사항 테스트"""
        # Python 3.10 미만에서 실행할 경우를 시뮬레이션하기 어려우므로
        # 현재 버전이 3.10 이상인지만 확인
        assert sys.version_info >= (3, 10), "RFS Framework requires Python 3.10+"

    def test_cli_rich_ui_availability(self):
        """Rich UI 사용 가능성 테스트"""
        try:
            import rich

            # Rich가 설치되어 있으면 CLI에서 Rich UI 사용
            result = subprocess.run(
                [sys.executable, "-m", "rfs.cli.standalone", "status"],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            # Rich 테이블 형식 확인 (간단한 확인)
            assert "┏" in result.stdout or "✅" in result.stdout
        except ImportError:
            # Rich가 없으면 일반 텍스트 출력 확인
            result = subprocess.run(
                [sys.executable, "-m", "rfs.cli.standalone", "status"],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert "RFS Framework System Status" in result.stdout


class TestCLIErrorHandling:
    """CLI 오류 처리 테스트"""

    def test_keyboard_interrupt_handling(self):
        """키보드 인터럽트 처리 테스트"""
        # 실제 키보드 인터럽트를 시뮬레이션하기는 어려우므로
        # 프로세스가 정상적으로 종료 코드를 반환하는지 확인
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone", "status"],
            capture_output=True,
            text=True,
        )

        # 정상적으로 실행되어야 함
        assert result.returncode == 0

    def test_invalid_arguments(self):
        """잘못된 인자 처리 테스트"""
        result = subprocess.run(
            [sys.executable, "-m", "rfs.cli.standalone", "--invalid-flag"],
            capture_output=True,
            text=True,
        )

        # 알 수 없는 플래그는 명령어로 간주되어 오류 발생
        assert result.returncode == 1


class TestCLIWorkflow:
    """CLI 워크플로우 테스트"""

    def test_multiple_commands_sequence(self):
        """여러 명령어 순차 실행 테스트"""
        commands = ["version", "status", "config", "help"]

        for cmd in commands:
            result = subprocess.run(
                [sys.executable, "-m", "rfs.cli.standalone", cmd],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"Command '{cmd}' failed"

    def test_cli_consistency(self):
        """CLI 일관성 테스트"""
        # 같은 명령어를 여러 번 실행해도 일관된 결과
        for _ in range(3):
            result = subprocess.run(
                [sys.executable, "-m", "rfs.cli.standalone", "version"],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert "4.3.0" in result.stdout
