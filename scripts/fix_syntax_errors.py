#!/usr/bin/env python3
"""
구문 오류를 자동으로 수정하는 스크립트

특히 잘못된 타입 힌트 구문을 수정합니다.
"""

import re
import sys
from pathlib import Path
from typing import List


def fix_syntax_errors(file_path: Path) -> int:
    """파일의 구문 오류를 수정합니다."""
    
    content = file_path.read_text()
    original_content = content
    changes = 0
    
    # 잘못된 패턴: function(arg, param: Type = value)
    # 올바른 패턴: function(arg, param=value)
    
    # Pattern 1: parameters={}
    pattern1 = r'(parameters):\s*Dict\[str,\s*Any\]\s*=\s*\{\}'
    content = re.sub(pattern1, r'\1={}', content)
    
    # Pattern 2: labels=[]
    pattern2 = r'(\w+):\s*List\[Any\]\s*=\s*\[\](?=,|\))'
    content = re.sub(pattern2, r'\1=[]', content)
    
    # Pattern 3: datasets=[]
    pattern3 = r'(\w+):\s*List\[.*?\]\s*=\s*\[\](?=,|\))'
    content = re.sub(pattern3, r'\1=[]', content)
    
    # Pattern 4: general keyword argument syntax error
    # Match: name: Type = value in function calls
    pattern4 = r'(\w+):\s*(?:Dict|List|Set|Tuple)\[.*?\]\s*=\s*(?:\{\}|\[\]|set\(\))(?=,|\))'
    content = re.sub(pattern4, lambda m: f"{m.group(1)}={{}}" if "Dict" in m.group(0) else f"{m.group(1)}=[]", content)
    
    # Pattern 5: Fix any remaining syntax issues
    pattern5 = r',\s*(\w+):\s*\w+(?:\[.*?\])?\s*=\s*([^,\)]+)'
    content = re.sub(pattern5, r', \1=\2', content)
    
    # 변경사항이 있으면 파일 저장
    if content != original_content:
        file_path.write_text(content)
        changes = 1
    
    return changes


def main():
    """메인 함수"""
    print("🔧 구문 오류 자동 수정 시작...")
    
    # src/rfs 디렉토리의 모든 Python 파일
    src_path = Path("src/rfs")
    total_changes = 0
    fixed_files = []
    
    # analytics 모듈의 파일들부터 수정
    for module in ["analytics", "production", "cloud_run", "optimization"]:
        module_path = src_path / module
        if module_path.exists():
            for py_file in module_path.rglob("*.py"):
                changes = fix_syntax_errors(py_file)
                if changes > 0:
                    fixed_files.append(py_file)
                    total_changes += changes
                    print(f"  ✓ {py_file}")
    
    print(f"\n📊 수정 완료:")
    print(f"  - 수정된 파일: {len(fixed_files)}개")
    print(f"  - 총 수정 사항: {total_changes}개")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())