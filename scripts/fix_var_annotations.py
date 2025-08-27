#!/usr/bin/env python3
"""
var-annotated 오류를 자동으로 수정하는 스크립트

변수에 타입 어노테이션을 추가합니다.
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple


def fix_var_annotations(file_path: Path) -> int:
    """파일의 var-annotated 오류를 수정합니다."""
    
    # 일반적인 패턴과 타입 매핑
    type_patterns = {
        r'(\w+)\s*=\s*\[\]': (r'\1=[]', 'from typing import Any, List'),
        r'(\w+)\s*=\s*\{\}': (r'\1={}', 'from typing import Any, Dict'),
        r'(\w+)\s*=\s*set\(\)': (r'\1: Set[Any] = set()', 'from typing import Any, Set'),
        r'errors\s*=\s*\[\]': ('errors=[]', 'from typing import List'),
        r'results\s*=\s*\[\]': ('results=[]', 'from typing import Any, List'),
        r'dependencies\s*=\s*\[\]': ('dependencies=[]', 'from typing import List'),
        r'config\s*=\s*\{\}': ('config={}', 'from typing import Any, Dict'),
        r'warnings\s*=\s*\[\]': ('warnings=[]', 'from typing import List'),
        r'messages\s*=\s*\[\]': ('messages=[]', 'from typing import List'),
        r'_instances\s*=\s*\{\}': ('_instances={}', 'from typing import Any, Dict'),
        r'_factories\s*=\s*\{\}': ('_factories={}', 'from typing import Any, Dict'),
    }
    
    content = file_path.read_text()
    original_content = content
    imports_added = set()
    changes = 0
    
    # 각 패턴에 대해 수정 적용
    for pattern, (replacement, import_needed) in type_patterns.items():
        if re.search(pattern, content):
            content = re.sub(pattern, replacement[0] if isinstance(replacement, tuple) else replacement, content)
            if import_needed:
                imports_added.add(import_needed)
            changes += 1
    
    # 필요한 import 추가
    if imports_added and content != original_content:
        # typing import가 이미 있는지 확인
        has_typing_import = 'from typing import' in content or 'import typing' in content
        
        if not has_typing_import:
            # 첫 번째 import 문 찾기
            import_match = re.search(r'^(import |from )', content, re.MULTILINE)
            if import_match:
                insert_pos = import_match.start()
                # 모든 필요한 imports 수집
                all_types = set()
                for imp in imports_added:
                    types = re.findall(r'import (.+)$', imp)
                    if types:
                        all_types.update(types[0].split(', '))
                
                if all_types:
                    import_line = f"from typing import {', '.join(sorted(all_types))}\n"
                    content = content[:insert_pos] + import_line + content[insert_pos:]
    
    # 변경사항이 있으면 파일 저장
    if content != original_content:
        file_path.write_text(content)
        return changes
    
    return 0


def main():
    """메인 함수"""
    print("🔧 var-annotated 오류 자동 수정 시작...")
    
    # src/rfs 디렉토리의 모든 Python 파일
    src_path = Path("src/rfs")
    total_changes = 0
    fixed_files = []
    
    for py_file in src_path.rglob("*.py"):
        # 테스트 파일 제외
        if "test" in str(py_file):
            continue
            
        changes = fix_var_annotations(py_file)
        if changes > 0:
            fixed_files.append(py_file)
            total_changes += changes
            print(f"  ✓ {py_file}: {changes} 수정")
    
    print(f"\n📊 수정 완료:")
    print(f"  - 수정된 파일: {len(fixed_files)}개")
    print(f"  - 총 수정 사항: {total_changes}개")
    
    if fixed_files:
        print("\n수정된 파일 목록:")
        for f in fixed_files[:10]:  # 최대 10개만 표시
            print(f"  - {f}")
        if len(fixed_files) > 10:
            print(f"  ... 외 {len(fixed_files) - 10}개")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())