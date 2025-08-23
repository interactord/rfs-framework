#!/usr/bin/env python3
"""
RFS Framework MCP 서버 설치 스크립트
"""

import json
import os
import platform
import sys
from pathlib import Path


def get_claude_desktop_config_path():
    """Claude Desktop 설정 파일 경로 반환"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json"
    elif system == "Linux":
        return Path.home() / ".config/Claude/claude_desktop_config.json"
    else:
        raise ValueError(f"지원하지 않는 운영체제: {system}")


def get_rfs_framework_path():
    """RFS Framework 경로 반환"""
    return Path(__file__).parent.absolute()


def install_mcp_server():
    """MCP 서버를 Claude Desktop에 설치"""
    
    print("🚀 RFS Framework MCP 서버 설치를 시작합니다...")
    
    # Claude Desktop 설정 파일 경로
    config_path = get_claude_desktop_config_path()
    print(f"📍 설정 파일 경로: {config_path}")
    
    # RFS Framework 경로
    rfs_path = get_rfs_framework_path()
    mcp_server_path = rfs_path / "mcp_server_simple.py"
    
    if not mcp_server_path.exists():
        print(f"❌ MCP 서버 파일을 찾을 수 없습니다: {mcp_server_path}")
        return False
    
    # 설정 디렉토리 생성
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 기존 설정 읽기
    config = {}
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ 기존 설정 파일이 손상되어 있습니다. 새로 생성합니다.")
            config = {}
    
    # MCP 서버 설정 추가
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    config["mcpServers"]["rfs-framework"] = {
        "command": sys.executable,  # 현재 Python 인터프리터
        "args": [str(mcp_server_path)],
        "env": {},
        "cwd": str(rfs_path)
    }
    
    # 설정 파일 저장
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("✅ RFS Framework MCP 서버가 성공적으로 설치되었습니다!")
        print(f"📝 설정 파일: {config_path}")
        print(f"🔧 서버 경로: {mcp_server_path}")
        print()
        print("📋 다음 단계:")
        print("1. Claude Desktop을 재시작하세요")
        print("2. '@rfs-framework'로 서버를 호출할 수 있습니다")
        print()
        print("💡 사용 예시:")
        print("  @rfs-framework 리액티브 스트림 코드 생성해줘")
        print("  @rfs-framework 함수형 패턴으로 바꿔줘")
        
        return True
        
    except Exception as e:
        print(f"❌ 설정 파일 저장 실패: {e}")
        return False


def test_mcp_server():
    """MCP 서버 테스트"""
    print("\n🧪 MCP 서버 테스트를 시작합니다...")
    
    rfs_path = get_rfs_framework_path()
    mcp_server_path = rfs_path / "mcp_server.py"
    
    try:
        # MCP 서버 임포트 테스트
        sys.path.insert(0, str(rfs_path))
        from mcp_server_simple import server
        
        print("✅ MCP 서버 초기화 성공")
        
        # 기본 정보 출력
        print(f"📚 RFS Framework MCP 서버")
        print(f"  - 서버 이름: {server.name}")
        print(f"  - 리소스: 프레임워크 개요, 패턴 설명, 예제")
        print(f"  - 도구: 코드 생성, 패턴 설명")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP 서버 테스트 실패: {e}")
        return False


def main():
    """메인 함수"""
    print("=" * 60)
    print("🔧 RFS Framework MCP 서버 설치 도구")
    print("=" * 60)
    
    # MCP 서버 테스트
    if not test_mcp_server():
        print("\n❌ MCP 서버 테스트에 실패했습니다.")
        return
    
    # MCP 서버 설치
    if not install_mcp_server():
        print("\n❌ MCP 서버 설치에 실패했습니다.")
        return
    
    print("\n🎉 설치가 완료되었습니다!")
    print("\n📖 자세한 사용법은 README-MCP.md를 참조하세요.")


if __name__ == "__main__":
    main()