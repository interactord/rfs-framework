"""
RFS CLI Main Entry Point (RFS v4.3.0)

RFS Framework 명령행 도구의 메인 진입점
- Standalone CLI 구현으로 임포트 오류 방지
- Rich UI 지원
- 완전한 기능 구현
"""

import sys
from typing import List, Optional

from .standalone import main as standalone_main


def main(args: Optional[List[str]] = None) -> int:
    """
    RFS CLI 메인 진입점

    Args:
        args: CLI 인자 리스트 (None이면 sys.argv 사용)

    Returns:
        int: 종료 코드 (0: 성공, 1+: 오류)
    """
    try:
        return standalone_main(args)
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        return 130
    except Exception as e:
        print(f"❌ CLI Error: {str(e)}")
        return 1


# CLI 진입점
if __name__ == "__main__":
    sys.exit(main())
