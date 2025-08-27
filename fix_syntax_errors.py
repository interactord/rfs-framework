#!/usr/bin/env python3
"""
RFS Framework 문법 오류 수정 스크립트
함수 호출에서 잘못된 키워드 인자 문법을 수정합니다.

패턴: parameter: Type = default_value
수정: parameter=default_value
"""

import os
import re
import glob

def fix_syntax_errors_in_file(file_path):
    """파일의 문법 오류를 수정합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 패턴 1=[] 형태
        pattern1 = r'(\w+): List\[([^\]]+)\] = \[\]'
        replacement1 = r'\1=[]'
        content = re.sub(pattern1, replacement1, content)
        
        # 패턴 2={} 형태  
        pattern2 = r'(\w+): Dict\[([^\]]+)\] = \{\}'
        replacement2 = r'\1={}'
        content = re.sub(pattern2, replacement2, content)
        
        # 패턴 3=None 형태
        pattern3 = r'(\w+): Optional\[([^\]]+)\] = None'
        replacement3 = r'\1=None'
        content = re.sub(pattern3, replacement3, content)
        
        # 패턴 4=True/False 형태
        pattern4 = r'(\w+): bool = (True|False)'
        replacement4 = r'\1=\2'
        content = re.sub(pattern4, replacement4, content)
        
        # 패턴 5: int = number 형태
        pattern5 = r'(\w+): int = (\d+)'
        replacement5 = r'\1=\2'
        content = re.sub(pattern5, replacement5, content)
        
        # 패턴 6="string" 형태
        pattern6 = r'(\w+): str = "([^"]*)"'
        replacement6 = r'\1="\2"'
        content = re.sub(pattern6, replacement6, content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 수정됨: {file_path}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ 오류 ({file_path}): {e}")
        return False

def main():
    """메인 실행 함수"""
    base_dir = "/Users/sangbongmoon/Workspace/rfs-framework"
    
    # Python 파일 찾기
    python_files = []
    for root, dirs, files in os.walk(base_dir):
        if 'venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"총 {len(python_files)}개의 Python 파일을 검사합니다...")
    
    fixed_count = 0
    error_count = 0
    
    for file_path in python_files:
        try:
            if fix_syntax_errors_in_file(file_path):
                fixed_count += 1
        except Exception as e:
            error_count += 1
            print(f"❌ 파일 처리 실패 ({file_path}): {e}")
    
    print(f"\n✅ 완료: {fixed_count}개 파일 수정")
    if error_count > 0:
        print(f"❌ 오류: {error_count}개 파일 처리 실패")

if __name__ == "__main__":
    main()