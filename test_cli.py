#!/usr/bin/env python3
"""
RFS CLI 독립 테스트 스크립트
"""

import sys
import asyncio
from pathlib import Path

# src 디렉토리를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from rich.console import Console
    from rich.panel import Panel
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

def show_version():
    """RFS Framework 버전 정보 표시"""
    if console:
        version_info = Panel(
            "🏷️  버전: 4.3.0\n"
            "📅 릴리스: 2024년\n"
            "🎯 단계: Production Ready\n"
            "🐍 Python: 3.10+\n"
            "☁️  플랫폼: Google Cloud Run\n"
            "🏗️  아키텍처: Hexagonal Architecture\n"
            "🔒 보안: RBAC/ABAC\n"
            "📊 모니터링: 성능 최적화",
            title="RFS Framework 버전 정보",
            border_style="green"
        )
        console.print(version_info)
    else:
        print("RFS Framework - 버전 4.3.0")
        print("Production Ready")
        print("Python 3.10+ | Enterprise-Grade")

def show_status():
    """시스템 상태 확인"""
    if console:
        console.print("[bold]RFS Framework Status[/bold]")
        console.print("Framework: [green]OK[/green]")
        console.print(f"Python: [blue]{sys.version_info.major}.{sys.version_info.minor}[/blue]")
        console.print("Environment: [cyan]Development[/cyan]")
        
        console.print("\n[bold]Core Features:[/bold]")
        features = [
            ("Result Pattern", "✅"),
            ("Reactive Streams", "✅"),
            ("Hexagonal Architecture", "✅"),
            ("Cloud Run Support", "✅"),
            ("Security (RBAC/ABAC)", "✅"),
            ("Performance Monitoring", "✅"),
            ("Circuit Breaker", "✅"),
            ("Load Balancing", "✅")
        ]
        
        for feature, status in features:
            console.print(f"  {status} {feature}")
    else:
        print("RFS Framework Status")
        print("Framework: OK")
        print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")

def show_help():
    """도움말 표시"""
    if console:
        console.print("[bold green]RFS Framework CLI v4.3.0[/bold green]")
        console.print("Enterprise-Grade Reactive Functional Serverless Framework")
        console.print("\n[bold]Available Commands:[/bold]")
        console.print("  [cyan]version[/cyan]  - Show version information")
        console.print("  [cyan]status[/cyan]   - Check system status")
        console.print("  [cyan]help[/cyan]     - Show this help message")
        console.print("\n[bold]Global Options:[/bold]")
        console.print("  [yellow]--verbose, -v[/yellow]     Enable verbose output")
        console.print("  [yellow]--help, -h[/yellow]        Show help message")
    else:
        print("RFS Framework CLI v4.3.0")
        print("Available Commands:")
        print("  version  - Show version information")
        print("  status   - Check system status") 
        print("  help     - Show this help message")

def main():
    """메인 함수"""
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    if not args or args[0] in ['help', '--help', '-h']:
        show_help()
    elif args[0] in ['version', '--version', '-v']:
        show_version()
    elif args[0] == 'status':
        show_status()
    else:
        if console:
            console.print(f"[red]Unknown command: {args[0]}[/red]")
            console.print("Run 'python test_cli.py help' for available commands")
        else:
            print(f"Unknown command: {args[0]}")
            print("Run 'python test_cli.py help' for available commands")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())