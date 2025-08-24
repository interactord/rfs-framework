"""
RFS CLI Module (RFS v4)

개발자 경험 혁신을 위한 CLI 도구 모음
- 프로젝트 초기화 및 스캐폴딩
- 개발 워크플로우 자동화
- 배포 및 모니터링 도구
- 디버깅 및 테스팅 지원
"""

from .commands import (  # 프로젝트 관리; 개발 워크플로우; 배포 및 운영; 디버깅 및 유틸리티
    BuildCommand,
    ConfigCommand,
    DebugCommand,
    DeployCommand,
    DevCommand,
    HealthCommand,
    InitCommand,
    LogsCommand,
    MonitorCommand,
    NewCommand,
    StatusCommand,
    TestCommand,
)
from .core import Command, CommandGroup, RFSCli

__all__ = [
    "RFSCli",
    "Command",
    "CommandGroup",
    "InitCommand",
    "NewCommand",
    "ConfigCommand",
    "DevCommand",
    "BuildCommand",
    "TestCommand",
    "DeployCommand",
    "MonitorCommand",
    "LogsCommand",
    "DebugCommand",
    "StatusCommand",
    "HealthCommand",
]

__version__ = "4.0.0"
__cli_features__ = [
    "🚀 Interactive Project Initialization",
    "⚡ Hot Reload Development Server",
    "🔧 Configuration Management",
    "☁️  One-Click Cloud Run Deployment",
    "📊 Real-time Monitoring Dashboard",
    "🐛 Integrated Debugging Tools",
    "🧪 Automated Testing Pipeline",
    "📚 Auto-generated Documentation",
]
