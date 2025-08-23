"""
RFS CLI Main Entry Point (RFS v4)

RFS v4 명령행 도구의 메인 진입점
- 전역 CLI 인터페이스
- 명령어 라우팅
- 에러 핸들링
- 도움말 시스템
"""

import sys
import asyncio
from typing import List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .core import RFSCli
from ..core import Result, Success, Failure

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


def show_welcome_banner():
    """환영 배너 표시"""
    if console:
        banner = Panel(
            "🚀 RFS v4 Command Line Interface\n\n"
            "Reactive Functional Serverless Framework\n"
            "Google Cloud Run 전용 현대적 Python 프레임워크\n\n"
            "버전: 4.0.0 | Phase 3: Developer Experience",
            title="RFS CLI",
            border_style="blue",
            padding=(1, 2)
        )
        console.print(banner)
    else:
        print("RFS v4 CLI - Reactive Functional Serverless Framework")
        print("버전: 4.0.0 | Phase 3: Developer Experience")
        print()


def show_help():
    """도움말 표시"""
    if console:
        help_table = Table(title="RFS v4 CLI 명령어", show_header=True, header_style="bold magenta")
        help_table.add_column("명령어", style="cyan", width=15)
        help_table.add_column("설명", style="white")
        help_table.add_column("예시", style="green")
        
        commands = [
            ("init", "새 RFS 프로젝트 초기화", "rfs init my-project"),
            ("new", "새 컴포넌트 생성", "rfs new service UserService"),
            ("dev", "개발 서버 시작", "rfs dev --port 8080"),
            ("build", "프로젝트 빌드", "rfs build --target production"),
            ("test", "테스트 실행", "rfs test --coverage"),
            ("deploy", "Cloud Run 배포", "rfs deploy --region asia-northeast3"),
            ("monitor", "모니터링 대시보드", "rfs monitor --interval 30"),
            ("logs", "로그 조회", "rfs logs --follow"),
            ("debug", "디버깅 도구", "rfs debug profile main.py"),
            ("status", "시스템 상태 확인", "rfs status"),
            ("health", "헬스체크 실행", "rfs health --timeout 30"),
            ("config", "설정 관리", "rfs config show"),
            ("docs", "문서 생성", "rfs docs --all"),
            ("workflow", "워크플로우 자동화", "rfs workflow start"),
        ]
        
        for cmd, desc, example in commands:
            help_table.add_row(cmd, desc, example)
        
        console.print(help_table)
        
        console.print("\n💡 각 명령어의 자세한 도움말: rfs <명령어> --help")
        console.print("📚 문서: https://rfs-v4.readthedocs.io")
        console.print("🐛 이슈 리포트: https://github.com/rfs-framework/rfs-v4/issues")
    
    else:
        print("RFS v4 CLI 명령어:")
        print()
        print("  init     - 새 RFS 프로젝트 초기화")
        print("  new      - 새 컴포넌트 생성")
        print("  dev      - 개발 서버 시작")
        print("  build    - 프로젝트 빌드")
        print("  test     - 테스트 실행")
        print("  deploy   - Cloud Run 배포")
        print("  monitor  - 모니터링 대시보드")
        print("  logs     - 로그 조회")
        print("  debug    - 디버깅 도구")
        print("  status   - 시스템 상태 확인")
        print("  health   - 헬스체크 실행")
        print("  config   - 설정 관리")
        print("  docs     - 문서 생성")
        print("  workflow - 워크플로우 자동화")
        print()
        print("자세한 도움말: rfs <명령어> --help")


def show_version():
    """버전 정보 표시"""
    if console:
        version_info = Panel(
            "🏷️  버전: 4.0.0\n"
            "📅 릴리스: 2024년\n"
            "🎯 단계: Phase 3 - Developer Experience\n"
            "🐍 Python: 3.10+\n"
            "☁️  플랫폼: Google Cloud Run",
            title="RFS v4 버전 정보",
            border_style="green"
        )
        console.print(version_info)
    else:
        print("RFS v4 - 버전 4.0.0")
        print("Phase 3: Developer Experience")
        print("Python 3.10+ | Google Cloud Run")


async def main_async(args: Optional[List[str]] = None) -> int:
    """비동기 메인 함수"""
    try:
        # 인자가 없으면 sys.argv 사용
        if args is None:
            args = sys.argv[1:]
        
        # 인자 없음 - 환영 메시지 및 도움말
        if not args:
            show_welcome_banner()
            show_help()
            return 0
        
        # 전역 옵션 처리
        if args[0] in ['--help', '-h', 'help']:
            show_help()
            return 0
        
        if args[0] in ['--version', '-v', 'version']:
            show_version()
            return 0
        
        # RFS CLI 인스턴스 생성 및 실행
        cli = RFSCli()
        
        result = await cli.run(args)
        
        if isinstance(result, int):
            return result
        else:
            # Result 타입인 경우
            if hasattr(result, 'is_success') and result.is_success():
                return 0
            else:
                if console:
                    console.print(f"❌ CLI 실행 실패: {result.unwrap_err()}", style="red")
                else:
                    print(f"CLI 실행 실패: {result.unwrap_err()}")
                return 1
        
    except KeyboardInterrupt:
        if console:
            console.print("\n🛑 사용자에 의해 중단됨", style="yellow")
        else:
            print("\n사용자에 의해 중단됨")
        return 130  # SIGINT exit code
    
    except Exception as e:
        if console:
            console.print(f"❌ 예상치 못한 오류: {str(e)}", style="red")
        else:
            print(f"예상치 못한 오류: {str(e)}")
        
        # 디버그 모드인 경우 전체 스택 트레이스 출력
        import os
        if os.getenv('RFS_DEBUG') == 'true':
            import traceback
            traceback.print_exc()
        
        return 1


def main(args: Optional[List[str]] = None) -> int:
    """동기 메인 함수 (진입점)"""
    try:
        # Python 3.10+ 확인
        if sys.version_info < (3, 10):
            if console:
                console.print("❌ RFS v4는 Python 3.10 이상이 필요합니다.", style="red")
                console.print(f"현재 버전: {sys.version_info.major}.{sys.version_info.minor}")
            else:
                print("RFS v4는 Python 3.10 이상이 필요합니다.")
                print(f"현재 버전: {sys.version_info.major}.{sys.version_info.minor}")
            return 1
        
        # 이벤트 루프 실행
        try:
            # Python 3.11+에서는 현재 이벤트 루프 확인
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            
            if loop is not None:
                # 이미 이벤트 루프가 실행 중인 경우 (예: Jupyter)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(main_async(args)))
                    return future.result()
            else:
                # 일반적인 경우
                return asyncio.run(main_async(args))
                
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                # 중첩된 이벤트 루프 해결
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(main_async(args))
            else:
                raise
    
    except Exception as e:
        if console:
            console.print(f"❌ CLI 초기화 실패: {str(e)}", style="red")
        else:
            print(f"CLI 초기화 실패: {str(e)}")
        return 1


# CLI 진입점
if __name__ == "__main__":
    sys.exit(main())