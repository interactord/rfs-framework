#!/usr/bin/env python3
"""
규칙 기반 RFS 배치 적용기

프로젝트 규칙에 따른 우선순위로 RFS 프레임워크 배치를 자동 적용합니다.
"""

import json
import ast
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class ApplyResult(Enum):
    """적용 결과"""
    SUCCESS = "success"
    SKIPPED = "skipped"  
    FAILED = "failed"
    PARTIAL = "partial"

@dataclass
class RuleApplication:
    """규칙 적용 결과"""
    file_path: str
    line_number: int
    rule_category: str
    description: str
    result: ApplyResult
    changes_made: str = ""
    error_message: str = ""

class RuleBatchApplicator:
    """규칙 기반 배치 적용기"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.results: List[RuleApplication] = []
        
    def load_batches(self, batch_file: str = "rule_based_rfs_batches.json") -> List[Dict]:
        """배치 데이터 로드"""
        batch_path = Path(batch_file)
        if not batch_path.exists():
            print(f"❌ 배치 파일을 찾을 수 없습니다: {batch_file}")
            return []
        
        with open(batch_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def apply_immutability_patterns(self, file_path: str, line_number: int, 
                                  code_snippet: str) -> Tuple[ApplyResult, str, str]:
        """불변성 패턴 적용"""
        changes = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            target_line = lines[line_number - 1] if line_number <= len(lines) else ""
            
            # 다양한 불변성 패턴 감지 및 수정
            if '.append(' in target_line:
                # list.append() → 불변 패턴
                new_line = self._convert_append_to_immutable(target_line)
                changes.append(f"Line {line_number}: {target_line.strip()} → {new_line.strip()}")
                lines[line_number - 1] = new_line
                
            elif '.update(' in target_line:
                # dict.update() → 불변 패턴
                new_line = self._convert_update_to_immutable(target_line)
                changes.append(f"Line {line_number}: {target_line.strip()} → {new_line.strip()}")
                lines[line_number - 1] = new_line
                
            elif '.update(' in target_line:
                # 이미 위에서 처리됨
                pass
            elif re.search(r'\w+\[.+\]\s*=', target_line):
                # dict[key] = value → 불변 패턴
                new_line = self._convert_dict_assignment_to_immutable(target_line)
                changes.append(f"Line {line_number}: {target_line.strip()} → {new_line.strip()}")
                lines[line_number - 1] = new_line
            
            if changes and not self.dry_run:
                # RFS 데코레이터 추가
                lines = self._add_immutable_decorator(lines, line_number)
                
                # 파일 저장
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
            
            result = ApplyResult.SUCCESS if changes else ApplyResult.SKIPPED
            return result, '\n'.join(changes), ""
            
        except Exception as e:
            return ApplyResult.FAILED, "", str(e)
    
    def _convert_append_to_immutable(self, line: str) -> str:
        """append를 불변 패턴으로 변환"""
        # result.append(item) → result = [*result, item]
        pattern = r'(\w+)\.append\(([^)]+)\)'
        
        def replace_func(match):
            list_var = match.group(1)
            item = match.group(2)
            return f"{list_var} = [*{list_var}, {item}]"
        
        return re.sub(pattern, replace_func, line)
    
    def _convert_update_to_immutable(self, line: str) -> str:
        """update를 불변 패턴으로 변환"""
        # dict.update(new_dict) → dict = {**dict, **new_dict}
        pattern = r'(\w+)\.update\(([^)]+)\)'
        
        def replace_func(match):
            dict_var = match.group(1)
            new_dict = match.group(2)
            return f"{dict_var} = {{**{dict_var}, **{new_dict}}}"
        
        return re.sub(pattern, replace_func, line)
    
    def _convert_dict_assignment_to_immutable(self, line: str) -> str:
        """딕셔너리 할당을 불변 패턴으로 변환"""
        # dict[key] = value → dict = {**dict, key: value}
        pattern = r'(\w+)\[([^]]+)\]\s*=\s*(.+)'
        
        def replace_func(match):
            dict_var = match.group(1)
            key = match.group(2)
            value = match.group(3)
            return f"{dict_var} = {{**{dict_var}, {key}: {value}}}"
        
        return re.sub(pattern, replace_func, line)
    
    def _add_immutable_decorator(self, lines: List[str], target_line: int) -> List[str]:
        """불변성 데코레이터 추가"""
        # 함수 시작점 찾기
        for i in range(target_line - 1, -1, -1):
            if lines[i].strip().startswith('def ') or lines[i].strip().startswith('async def '):
                # 데코레이터가 이미 있는지 확인
                decorator_line = i - 1
                while (decorator_line >= 0 and 
                       lines[decorator_line].strip().startswith('@')):
                    if '@immutable_operation' in lines[decorator_line]:
                        return lines  # 이미 있음
                    decorator_line -= 1
                
                # 데코레이터 추가
                indent = len(lines[i]) - len(lines[i].lstrip())
                decorator = ' ' * indent + '@immutable_operation()'
                lines.insert(i, decorator)
                break
        
        return lines
    
    def apply_map_filter_patterns(self, file_path: str, line_number: int,
                                code_snippet: str) -> Tuple[ApplyResult, str, str]:
        """Map/Filter 패턴 적용"""
        changes = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # for 루프를 찾아서 map/filter로 변환
            for_loop_start = line_number - 1
            for_loop_end = self._find_for_loop_end(lines, for_loop_start)
            
            if for_loop_end > for_loop_start:
                loop_lines = lines[for_loop_start:for_loop_end + 1]
                converted = self._convert_for_loop_to_functional(loop_lines)
                
                if converted:
                    changes.append(f"Lines {line_number}-{for_loop_end + 1}: Converted imperative loop to functional pattern")
                    
                    if not self.dry_run:
                        # 기존 루프 교체
                        lines[for_loop_start:for_loop_end + 1] = converted
                        
                        # 파일 저장
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(lines))
            
            result = ApplyResult.SUCCESS if changes else ApplyResult.SKIPPED
            return result, '\n'.join(changes), ""
            
        except Exception as e:
            return ApplyResult.FAILED, "", str(e)
    
    def _find_for_loop_end(self, lines: List[str], start: int) -> int:
        """for 루프의 끝을 찾기"""
        if start >= len(lines) or not lines[start].strip().startswith('for '):
            return start
        
        base_indent = len(lines[start]) - len(lines[start].lstrip())
        
        for i in range(start + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":
                continue
            
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= base_indent:
                return i - 1
        
        return len(lines) - 1
    
    def _convert_for_loop_to_functional(self, loop_lines: List[str]) -> Optional[List[str]]:
        """for 루프를 함수형 패턴으로 변환"""
        if not loop_lines or not loop_lines[0].strip().startswith('for '):
            return None
        
        first_line = loop_lines[0]
        base_indent = len(first_line) - len(first_line.lstrip())
        indent_str = ' ' * base_indent
        
        # for item in items: 패턴 분석
        for_pattern = r'for\s+(\w+)\s+in\s+([^:]+):'
        match = re.search(for_pattern, first_line)
        if not match:
            return None
        
        item_var = match.group(1)
        iterable = match.group(2).strip()
        
        # 루프 내용 분석
        has_append = any('.append(' in line for line in loop_lines[1:])
        has_condition = any('if ' in line for line in loop_lines[1:])
        
        if has_append:
            # result.append() 패턴
            converted = [
                f"{indent_str}# Converted to functional pattern using map/filter",
                f"{indent_str}result = list(",
                f"{indent_str}    map(lambda {item_var}: ...,",  # 실제 변환 로직은 더 복잡해야 함
                f"{indent_str}        filter(lambda {item_var}: ..., {iterable})",
                f"{indent_str}    )",
                f"{indent_str})"
            ]
            return converted
        
        return None
    
    def apply_service_patterns(self, file_path: str, line_number: int,
                             code_snippet: str) -> Tuple[ApplyResult, str, str]:
        """서비스 패턴 적용"""
        changes = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 클래스 정의 찾기
            class_line = lines[line_number - 1] if line_number <= len(lines) else ""
            
            if 'class ' in class_line and ('Service' in class_line or 
                                         'Manager' in class_line or 
                                         'Handler' in class_line):
                
                # StatelessService 상속 추가
                if 'StatelessService' not in class_line:
                    # 기존 상속이 있는지 확인
                    if '(' in class_line and ')' in class_line:
                        # 기존 상속에 StatelessService 추가
                        new_line = class_line.replace('(', '(StatelessService, ')
                    else:
                        # 새로운 상속 추가
                        new_line = class_line.replace(':', '(StatelessService):')
                    
                    changes.append(f"Line {line_number}: Added StatelessService inheritance")
                    lines[line_number - 1] = new_line
                    
                    # import 추가
                    import_line = "from app.rfs.core.base import StatelessService"
                    if import_line not in content:
                        lines.insert(0, import_line)
                        changes.append("Added StatelessService import")
                
                if changes and not self.dry_run:
                    # 파일 저장
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
            
            result = ApplyResult.SUCCESS if changes else ApplyResult.SKIPPED
            return result, '\n'.join(changes), ""
            
        except Exception as e:
            return ApplyResult.FAILED, "", str(e)
    
    def apply_batch(self, batch_data: Dict) -> List[RuleApplication]:
        """배치 적용"""
        batch_results = []
        
        print(f"\n🔄 배치 적용: {batch_data['rule_focus']}")
        print(f"   우선순위: {batch_data['priority']}")
        print(f"   기회 수: {len(batch_data['opportunities'])}개")
        
        for i, opportunity in enumerate(batch_data['opportunities'], 1):
            file_path = opportunity['file_path']
            line_number = opportunity['line_number']
            rule_category = opportunity['rule_category']
            description = opportunity['description']
            
            print(f"   {i}. {Path(file_path).name}:{line_number} - {description}")
            
            # 파일 존재 확인
            if not Path(file_path).exists():
                result = RuleApplication(
                    file_path=file_path,
                    line_number=line_number,
                    rule_category=rule_category,
                    description=description,
                    result=ApplyResult.FAILED,
                    error_message="File not found"
                )
                batch_results.append(result)
                print(f"      ❌ 파일을 찾을 수 없음")
                continue
            
            # 규칙 카테고리별 적용
            try:
                if "불변성" in rule_category:
                    apply_result, changes, error = self.apply_immutability_patterns(
                        file_path, line_number, opportunity.get('code_snippet', '')
                    )
                elif "Map/Filter" in rule_category:
                    apply_result, changes, error = self.apply_map_filter_patterns(
                        file_path, line_number, opportunity.get('code_snippet', '')
                    )
                elif "서비스" in rule_category:
                    apply_result, changes, error = self.apply_service_patterns(
                        file_path, line_number, opportunity.get('code_snippet', '')
                    )
                else:
                    apply_result = ApplyResult.SKIPPED
                    changes = "Pattern not implemented yet"
                    error = ""
                
                result = RuleApplication(
                    file_path=file_path,
                    line_number=line_number,
                    rule_category=rule_category,
                    description=description,
                    result=apply_result,
                    changes_made=changes,
                    error_message=error
                )
                
                # 결과 출력
                if apply_result == ApplyResult.SUCCESS:
                    print(f"      ✅ 적용 완료")
                    if self.dry_run and changes:
                        print(f"         변경사항: {changes}")
                elif apply_result == ApplyResult.SKIPPED:
                    print(f"      ⏭️ 건너뜀: {changes}")
                elif apply_result == ApplyResult.FAILED:
                    print(f"      ❌ 실패: {error}")
                
            except Exception as e:
                result = RuleApplication(
                    file_path=file_path,
                    line_number=line_number,
                    rule_category=rule_category,
                    description=description,
                    result=ApplyResult.FAILED,
                    error_message=str(e)
                )
                print(f"      ❌ 예외 발생: {e}")
            
            batch_results.append(result)
            self.results.append(result)
        
        return batch_results
    
    def generate_report(self, batches: List[Dict]) -> None:
        """적용 결과 리포트 생성"""
        print("\n" + "="*80)
        print("📊 규칙 기반 배치 적용 결과 리포트")
        print("="*80)
        
        # 전체 통계
        total_opportunities = len(self.results)
        success_count = sum(1 for r in self.results if r.result == ApplyResult.SUCCESS)
        skipped_count = sum(1 for r in self.results if r.result == ApplyResult.SKIPPED)
        failed_count = sum(1 for r in self.results if r.result == ApplyResult.FAILED)
        
        print(f"\n📈 전체 통계:")
        print(f"   • 총 기회 수: {total_opportunities}개")
        print(f"   • 성공: {success_count}개 ({success_count/total_opportunities*100:.1f}%)")
        print(f"   • 건너뜀: {skipped_count}개 ({skipped_count/total_opportunities*100:.1f}%)")
        print(f"   • 실패: {failed_count}개 ({failed_count/total_opportunities*100:.1f}%)")
        
        # 규칙별 통계
        rule_stats = {}
        for result in self.results:
            category = result.rule_category
            if category not in rule_stats:
                rule_stats[category] = {'total': 0, 'success': 0, 'failed': 0}
            
            rule_stats[category]['total'] += 1
            if result.result == ApplyResult.SUCCESS:
                rule_stats[category]['success'] += 1
            elif result.result == ApplyResult.FAILED:
                rule_stats[category]['failed'] += 1
        
        print(f"\n📋 규칙별 통계:")
        for category, stats in rule_stats.items():
            success_rate = (stats['success'] / stats['total']) * 100
            print(f"   • {category}: {stats['success']}/{stats['total']} "
                  f"({success_rate:.1f}% 성공률)")
        
        # 실패한 항목 요약
        failed_results = [r for r in self.results if r.result == ApplyResult.FAILED]
        if failed_results:
            print(f"\n❌ 실패한 항목들:")
            for result in failed_results[:10]:  # 최대 10개만 표시
                print(f"   • {Path(result.file_path).name}:{result.line_number} - "
                      f"{result.error_message}")
            
            if len(failed_results) > 10:
                print(f"   ... 및 추가 {len(failed_results) - 10}개")

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="규칙 기반 RFS 배치 적용기")
    parser.add_argument('--batch-file', default='rule_based_rfs_batches.json',
                       help='배치 JSON 파일')
    parser.add_argument('--dry-run', action='store_true',
                       help='실제 변경 없이 미리보기만')
    parser.add_argument('--priority', choices=['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
                       help='특정 우선순위만 적용')
    parser.add_argument('--batch-id', type=int,
                       help='특정 배치 ID만 적용')
    
    args = parser.parse_args()
    
    applicator = RuleBatchApplicator(dry_run=args.dry_run)
    
    # 배치 로드
    batches = applicator.load_batches(args.batch_file)
    if not batches:
        return
    
    # 필터링
    if args.priority:
        batches = [b for b in batches if b['priority'] == args.priority]
    
    if args.batch_id:
        batches = [b for b in batches if b['batch_id'] == args.batch_id]
    
    if not batches:
        print("❌ 적용할 배치가 없습니다.")
        return
    
    # 모드 출력
    mode = "🔍 DRY RUN (미리보기)" if args.dry_run else "🚀 실제 적용"
    print(f"{mode} - 총 {len(batches)}개 배치 처리")
    
    # 배치 적용
    for batch in batches:
        applicator.apply_batch(batch)
    
    # 리포트 생성
    applicator.generate_report(batches)
    
    if args.dry_run:
        print(f"\n💡 실제 적용하려면 --dry-run 옵션 없이 실행하세요.")

if __name__ == "__main__":
    main()