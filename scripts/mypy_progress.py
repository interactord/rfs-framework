#!/usr/bin/env python3
"""
mypy 오류 진행 상황 추적 스크립트

이 스크립트는 mypy 오류를 카테고리별로 분석하고
개선 진행 상황을 추적합니다.
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import re


def run_mypy_analysis() -> Tuple[int, Dict[str, int], List[str]]:
    """mypy를 실행하고 오류를 분석합니다."""
    # mypy를 실제 검사 모드로 실행 (설정 파일 사용)
    cmd = ["mypy", "src/rfs", "--config-file", "mypy.ini", "--show-error-codes", "--no-error-summary"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout + result.stderr
    except subprocess.CalledProcessError as e:
        output = e.stdout + e.stderr
    
    # 오류 패턴 분석
    error_pattern = r'\[([a-z-]+)\]'
    errors = re.findall(error_pattern, output)
    
    # 오류 카테고리별 집계
    error_categories = {}
    for error in errors:
        error_categories[error] = error_categories.get(error, 0) + 1
    
    # 파일별 오류 수집
    file_errors = []
    for line in output.split('\n'):
        if '.py:' in line and 'error:' in line:
            file_errors.append(line)
    
    total_errors = len(file_errors)
    
    return total_errors, error_categories, file_errors[:10]  # 샘플로 10개만


def update_progress_report(phase: int, total_errors: int, categories: Dict[str, int]):
    """진행 상황 보고서를 업데이트합니다."""
    report_path = Path("MYPY_PROGRESS_REPORT.md")
    
    # 기존 보고서 읽기 또는 새로 생성
    if report_path.exists():
        content = report_path.read_text()
    else:
        content = """# mypy 타입 개선 진행 상황

## 📊 진행 추적

| Phase | 날짜 | 총 오류 | 주요 카테고리 | 상태 |
|-------|------|---------|--------------|------|
"""
    
    # 새 항목 추가
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
    category_str = ", ".join([f"{cat}({cnt})" for cat, cnt in top_categories])
    
    new_line = f"| {phase} | {date_str} | {total_errors} | {category_str} | 진행중 |\n"
    
    # 중복 제거 후 추가
    lines = content.split('\n')
    if not any(f"| {phase} |" in line for line in lines):
        content += new_line
    
    report_path.write_text(content)
    return report_path


def main():
    """메인 실행 함수"""
    print("🔍 mypy 오류 분석 중...")
    
    # 현재 Phase 결정 (mypy.ini 파일 내용으로 판단)
    mypy_ini = Path("mypy.ini")
    if mypy_ini.exists():
        content = mypy_ini.read_text()
        if "ignore_errors = True" in content:
            phase = 1
        else:
            phase = 2  # 기본값
    else:
        phase = 0
    
    # mypy 분석 실행
    total_errors, categories, sample_errors = run_mypy_analysis()
    
    print(f"\n📊 Phase {phase} 분석 결과:")
    print(f"총 오류 수: {total_errors}")
    
    if categories:
        print("\n오류 카테고리별 분포:")
        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_errors * 100) if total_errors > 0 else 0
            print(f"  - {category}: {count}개 ({percentage:.1f}%)")
        
        print("\n샘플 오류 (최대 10개):")
        for i, error in enumerate(sample_errors, 1):
            print(f"  {i}. {error[:120]}...")
    else:
        print("✅ 오류가 없습니다!")
    
    # 진행 상황 보고서 업데이트
    report_path = update_progress_report(phase, total_errors, categories)
    print(f"\n📄 진행 상황이 {report_path}에 기록되었습니다.")
    
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())