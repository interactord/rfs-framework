"""
CLI Application Setup - CLI 애플리케이션 설정

RFS Framework CLI 애플리케이션의 명령어 등록 및 설정
"""

from .commands.basic import ConfigCommand, HelpCommand, StatusCommand, VersionCommand
from .core import RFSCli


def create_cli_app() -> RFSCli:
    """CLI 애플리케이션 생성 및 설정"""

    cli = RFSCli()

    # 기본 명령어들 등록
    cli.add_command(VersionCommand())
    cli.add_command(StatusCommand())
    cli.add_command(ConfigCommand())
    cli.add_command(HelpCommand())

    return cli


# 전역 CLI 애플리케이션 인스턴스
cli_app = create_cli_app()
