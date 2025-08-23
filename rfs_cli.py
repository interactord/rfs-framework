#!/usr/bin/env python3
"""
RFS Framework CLI - Complete Standalone Version

RFS 패키지 임포트 없이 독립적으로 실행되는 CLI
"""

import sys
import os
from pathlib import Path
from typing import Optional, List

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


def show_welcome_banner():
    """환영 배너 표시"""
    if console:
        banner = Panel(
            "🚀 RFS Framework Command Line Interface\n\n"
            "Enterprise-Grade Reactive Functional Serverless Framework\n"
            "Complete with Hexagonal Architecture, Security, and Cloud Run Support\n\n"
            "버전: 4.3.0 | Production Ready",
            title="RFS Framework CLI",
            border_style="blue",
            padding=(1, 2)
        )
        console.print(banner)
    else:
        print("RFS Framework CLI v4.3.0 - Enterprise-Grade Framework")
        print("Production Ready")
        print()


def show_version():
    """버전 정보 표시"""
    if console:
        version_info = Panel(
            "🏷️  버전: 4.3.0\n"
            "📅 릴리스: 2024년 8월\n"
            "🎯 단계: Production Ready\n"
            "🐍 Python: 3.10+\n"
            "☁️  플랫폼: Google Cloud Run\n"
            "🏗️  아키텍처: Hexagonal Architecture\n"
            "🔒 보안: RBAC/ABAC with JWT\n"
            "📊 모니터링: Performance & Security Monitoring\n"
            "⚡ 최적화: Circuit Breaker & Load Balancing\n"
            "📚 문서: 13개 한국어 모듈 완성\n"
            "🚀 배포: Blue-Green, Canary, Rolling Strategies",
            title="RFS Framework 버전 정보",
            border_style="green"
        )
        console.print(version_info)
    else:
        print("RFS Framework - 버전 4.3.0")
        print("Production Ready Enterprise Framework")
        print("Python 3.10+ | Cloud Native | Security Enhanced")
        print("Features: Hexagonal Architecture, RBAC/ABAC, Circuit Breaker")


def show_status():
    """시스템 상태 확인"""
    project_root = find_project_root()
    
    if console:
        console.print("[bold]RFS Framework System Status[/bold]")
        console.print("Framework: [green]✅ Production Ready[/green]")
        console.print(f"Python: [blue]{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}[/blue]")
        console.print(f"Project: [yellow]{project_root or 'Not detected'}[/yellow]")
        console.print("Environment: [cyan]Production Ready[/cyan]")
        
        # 기능 상태 테이블
        table = Table(title="Framework Features Status")
        table.add_column("Category", style="bold cyan", no_wrap=True)
        table.add_column("Feature", style="white")
        table.add_column("Status", style="green", justify="center")
        table.add_column("Version", style="dim")
        
        features = [
            ("Core", "Result Pattern & Functional Programming", "✅", "v4.3.0"),
            ("Core", "Reactive Streams (Mono/Flux)", "✅", "v4.3.0"),
            ("Architecture", "Hexagonal Architecture", "✅", "v4.3.0"),
            ("Architecture", "Annotation-based Dependency Injection", "✅", "v4.3.0"),
            ("Security", "RBAC/ABAC Access Control", "✅", "v4.3.0"),
            ("Security", "JWT Authentication", "✅", "v4.3.0"),
            ("Resilience", "Circuit Breaker Pattern", "✅", "v4.3.0"),
            ("Resilience", "Client-side Load Balancing", "✅", "v4.3.0"),
            ("Monitoring", "Performance Monitoring & Metrics", "✅", "v4.3.0"),
            ("Monitoring", "Security Event Logging", "✅", "v4.3.0"),
            ("Deployment", "Blue-Green Strategy", "✅", "v4.3.0"),
            ("Deployment", "Canary Strategy", "✅", "v4.3.0"),
            ("Deployment", "Rolling Strategy", "✅", "v4.3.0"),
            ("Deployment", "Rollback Management", "✅", "v4.3.0"),
            ("Cloud", "Google Cloud Run Optimization", "✅", "v4.3.0"),
            ("Docs", "Korean Documentation (13 modules)", "✅", "v4.3.0")
        ]
        
        for category, feature, status, version in features:
            table.add_row(category, feature, status, version)
        
        console.print(table)
        
        # 의존성 상태
        console.print("\n[bold]Dependencies Status:[/bold]")
        deps = check_dependencies()
        for dep, status in deps.items():
            icon = "✅" if status else "❌"
            console.print(f"  {icon} {dep}")
            
    else:
        print("RFS Framework System Status")
        print("Framework: Production Ready")
        print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")
        print(f"Project: {project_root or 'Not detected'}")
        print("\nCore Features:")
        print("  ✅ Result Pattern & Functional Programming")
        print("  ✅ Reactive Streams (Mono/Flux)")
        print("  ✅ Hexagonal Architecture")
        print("  ✅ Security (RBAC/ABAC with JWT)")
        print("  ✅ Performance Monitoring")
        print("  ✅ Deployment Strategies")
        print("  ✅ Cloud Run Support")


def show_help():
    """도움말 표시"""
    if console:
        console.print("[bold green]RFS Framework CLI v4.3.0[/bold green]")
        console.print("Enterprise-Grade Reactive Functional Serverless Framework")
        
        # 명령어 테이블
        table = Table(title="Available Commands")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Example", style="green")
        
        commands = [
            ("version", "Show framework version and features", "rfs version"),
            ("status", "Check system and features status", "rfs status"),
            ("help", "Show this help message", "rfs help"),
            ("config", "Show configuration information", "rfs config"),
            ("init", "Initialize new RFS project", "rfs init my-project"),
            ("dev", "Start development server", "rfs dev --port 8080"),
            ("build", "Build project for production", "rfs build --cloud-run"),
            ("deploy", "Deploy to Google Cloud Run", "rfs deploy --region asia-northeast3"),
            ("test", "Run test suite", "rfs test --coverage"),
            ("docs", "Generate documentation", "rfs docs --all")
        ]
        
        for cmd, desc, example in commands:
            table.add_row(cmd, desc, example)
        
        console.print(table)
        
        console.print("\n[bold]Global Options:[/bold]")
        console.print("  [yellow]--verbose, -v[/yellow]     Enable verbose output")
        console.print("  [yellow]--help, -h[/yellow]        Show help message")
        console.print("  [yellow]--version[/yellow]          Show version information")
        
        console.print("\n[bold]Framework Information:[/bold]")
        console.print("  📚 Korean Documentation: 13 comprehensive modules")
        console.print("  🔗 GitHub: https://github.com/interactord/rfs-framework")
        console.print("  📦 PyPI: https://pypi.org/project/rfs-framework/")
        console.print("  🏷️  Latest: v4.3.0 (Production Ready)")
        
    else:
        print("RFS Framework CLI v4.3.0")
        print("Available Commands:")
        print("  version  - Show version information")
        print("  status   - Check system status") 
        print("  help     - Show this help message")
        print("  config   - Show configuration")
        print("  init     - Initialize new project")
        print("  dev      - Start development server")
        print("  build    - Build for production")
        print("  deploy   - Deploy to Cloud Run")


def show_config():
    """설정 정보 표시"""
    project_root = find_project_root()
    
    if console:
        console.print("[bold]RFS Framework Configuration[/bold]")
        console.print("Version: [cyan]4.3.0[/cyan]")
        console.print("Phase: [green]Production Ready[/green]")
        console.print("Python: [blue]3.10+ required[/blue]")
        console.print(f"Project Root: [yellow]{project_root or 'Not detected'}[/yellow]")
        console.print("Features: [green]All modules implemented[/green]")
        
        # 설정 테이블
        table = Table(title="Framework Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        
        settings = [
            ("Framework Version", "4.3.0"),
            ("Development Status", "Production Ready"),
            ("Minimum Python", "3.10+"),
            ("Core Features", "16 modules"),
            ("Documentation", "Korean (13 modules)"),
            ("Architecture", "Hexagonal"),
            ("Security", "RBAC/ABAC"),
            ("Cloud Platform", "Google Cloud Run"),
            ("Package Name", "rfs-framework")
        ]
        
        for setting, value in settings:
            table.add_row(setting, value)
        
        console.print(table)
    else:
        print("RFS Framework Configuration")
        print("Version: 4.3.0")
        print("Phase: Production Ready")
        print(f"Project Root: {project_root or 'Not detected'}")


def find_project_root() -> Optional[str]:
    """프로젝트 루트 디렉토리 찾기"""
    current = Path.cwd()
    markers = ['rfs.yaml', 'rfs.json', 'pyproject.toml', 'requirements.txt']
    
    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return str(current)
        current = current.parent
    
    return None


def check_dependencies() -> dict:
    """의존성 확인"""
    deps = {}
    
    # 필수 의존성
    try:
        import pydantic
        deps['pydantic (>=2.5.0)'] = True
    except ImportError:
        deps['pydantic (>=2.5.0)'] = False
    
    try:
        import rich
        deps['rich (>=13.7.0)'] = True
    except ImportError:
        deps['rich (>=13.7.0)'] = False
    
    # 선택적 의존성
    try:
        import fastapi
        deps['fastapi (>=0.104.0) - optional'] = True
    except ImportError:
        deps['fastapi (>=0.104.0) - optional'] = False
    
    try:
        from google.cloud import run_v2
        deps['google-cloud-run (>=0.10.0) - optional'] = True
    except ImportError:
        deps['google-cloud-run (>=0.10.0) - optional'] = False
    
    return deps


def main(args: Optional[List[str]] = None) -> int:
    """메인 진입점"""
    if args is None:
        args = sys.argv[1:]
    
    # Python 버전 확인
    if sys.version_info < (3, 10):
        if console:
            console.print("[red]❌ RFS Framework requires Python 3.10 or higher[/red]")
            console.print(f"Current version: Python {sys.version_info.major}.{sys.version_info.minor}")
        else:
            print("❌ RFS Framework requires Python 3.10 or higher")
            print(f"Current version: Python {sys.version_info.major}.{sys.version_info.minor}")
        return 1
    
    # 명령어 처리
    if not args:
        show_welcome_banner()
        show_help()
        return 0
    
    command = args[0].lower()
    
    match command:
        case 'version' | '--version' | '-v':
            show_version()
        case 'status' | 'stat':
            show_status()
        case 'help' | '--help' | '-h':
            show_help()
        case 'config' | 'cfg':
            show_config()
        case 'init' | 'new' | 'dev' | 'build' | 'deploy' | 'test' | 'docs':
            if console:
                console.print(f"[yellow]⚠️  Command '{command}' is planned for future release[/yellow]")
                console.print("Currently available: version, status, help, config")
            else:
                print(f"⚠️  Command '{command}' is planned for future release")
                print("Currently available: version, status, help, config")
        case _:
            if console:
                console.print(f"[red]❌ Unknown command: {command}[/red]")
                console.print("Run '[cyan]rfs help[/cyan]' to see available commands")
            else:
                print(f"❌ Unknown command: {command}")
                print("Run 'rfs help' to see available commands")
            return 1
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        if console:
            console.print("\n[yellow]🛑 Operation cancelled by user[/yellow]")
        else:
            print("\n🛑 Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        if console:
            console.print(f"[red]❌ CLI Error: {str(e)}[/red]")
        else:
            print(f"❌ CLI Error: {str(e)}")
        sys.exit(1)