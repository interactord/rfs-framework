#!/usr/bin/env python3
"""
룰즈 기반 RFS 적용 배치 생성기

프로젝트 규칙에 따른 우선순위로 RFS 프레임워크 적용 배치를 생성합니다.
- 함수형 프로그래밍 원칙 우선
- SingleDispatch 패턴 적용
- 코드 품질 표준 준수
"""

import json
import ast
from typing import List, Dict, Any, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

class RulePriority(Enum):
    """규칙 기반 우선순위"""
    CRITICAL = 1    # 필수 준수 사항 (빌드 차단)
    HIGH = 2        # 함수형 프로그래밍 핵심 원칙
    MEDIUM = 3      # 코드 품질 향상
    LOW = 4         # 일반적인 개선

@dataclass
class RuleBasedOpportunity:
    """규칙 기반 RFS 적용 기회"""
    file_path: str
    line_number: int
    rule_category: str
    rule_priority: RulePriority
    description: str
    rfs_solution: str
    impact_score: float
    effort_hours: float
    code_snippet: str = ""
    rule_reference: str = ""

@dataclass
class RuleBatch:
    """규칙 기반 배치"""
    batch_id: int
    rule_focus: str
    priority: RulePriority
    opportunities: List[RuleBasedOpportunity] = field(default_factory=list)
    total_impact: float = 0.0
    total_effort: float = 0.0
    roi_score: float = 0.0

class RuleBasedBatchGenerator:
    """규칙 기반 배치 생성기"""
    
    def __init__(self, target_dir: str = "app/services/v2"):
        self.target_dir = Path(target_dir)
        self.opportunities: List[RuleBasedOpportunity] = []
        
    def analyze_rule_violations(self) -> None:
        """규칙 위반 사항 분석 및 RFS 적용 기회 탐지"""
        print("🔍 규칙 기반 분석 시작...")
        
        # 1. isinstance 사용 위반 (Critical - 빌드 차단)
        self._find_isinstance_violations()
        
        # 2. 불변성 위반 (High - 함수형 핵심)
        self._find_mutability_violations()
        
        # 3. 순수함수 위반 (High - 함수형 핵심)
        self._find_impure_function_violations()
        
        # 4. Map/Filter 패턴 미적용 (Medium - 코드 품질)
        self._find_imperative_loop_violations()
        
        # 5. HOF 미사용 (Medium - 코드 품질)
        self._find_hof_opportunities()
        
        # 6. 서비스 패턴 미적용 (Low - 일반 개선)
        self._find_service_pattern_opportunities()
        
        print(f"✅ 총 {len(self.opportunities)}개의 규칙 기반 기회 발견")
    
    def _find_isinstance_violations(self) -> None:
        """isinstance 사용 위반 탐지 (Critical)"""
        print("  🚨 isinstance 사용 위반 검사...")
        
        for py_file in self.target_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if (isinstance(node.func, ast.Name) and 
                            node.func.id == 'isinstance'):
                            
                            line_num = getattr(node, 'lineno', 0)
                            snippet = self._get_code_snippet(content, line_num)
                            
                            # 상대 경로 변환 시도, 실패하면 절대 경로 사용
                            try:
                                relative_path = str(py_file.relative_to(Path.cwd()))
                            except ValueError:
                                relative_path = str(py_file)
                            
                            opportunity = RuleBasedOpportunity(
                                file_path=relative_path,
                                line_number=line_num,
                                rule_category="SingleDispatch 패턴",
                                rule_priority=RulePriority.CRITICAL,
                                description="isinstance 사용을 SingleDispatch 패턴으로 변경 필요",
                                rfs_solution="@service_method with @singledispatch 적용",
                                impact_score=9.0,
                                effort_hours=2.0,
                                code_snippet=snippet,
                                rule_reference="rules/07-singledispatch-pattern.md"
                            )
                            self.opportunities.append(opportunity)
                            
            except Exception as e:
                print(f"  ⚠️ {py_file} 분석 실패: {e}")
    
    def _find_mutability_violations(self) -> None:
        """불변성 위반 탐지 (High)"""
        print("  🔧 불변성 위반 검사...")
        
        mutability_patterns = [
            (r'(\w+)\.append\(', "리스트에 직접 append 호출"),
            (r'(\w+)\.extend\(', "리스트에 직접 extend 호출"), 
            (r'(\w+)\.update\(', "딕셔너리에 직접 update 호출"),
            (r'(\w+)\[[^\]]+\]\s*=', "딕셔너리/리스트 인덱스 직접 할당"),
            (r'del\s+(\w+)\[', "딕셔너리/리스트 요소 직접 삭제"),
        ]
        
        for py_file in self.target_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in mutability_patterns:
                        import re
                        match = re.search(pattern, line)
                        if match:
                            # 주석이나 문자열 내부는 제외
                            if line.strip().startswith('#') or line.strip().startswith('"""') or line.strip().startswith("'''"):
                                continue
                            
                            # 실제 코드에서 mutation 발생하는지 확인
                            variable_name = match.group(1)
                            
                            # 상대 경로 변환 시도, 실패하면 절대 경로 사용
                            try:
                                relative_path = str(py_file.relative_to(Path.cwd()))
                            except ValueError:
                                relative_path = str(py_file)
                            
                            opportunity = RuleBasedOpportunity(
                                file_path=relative_path,
                                line_number=i,
                                rule_category="불변성 원칙",
                                rule_priority=RulePriority.HIGH,
                                description=f"{description}: {variable_name}",
                                rfs_solution="@immutable_operation with functional patterns",
                                impact_score=7.5,
                                effort_hours=1.5,
                                code_snippet=line.strip(),
                                rule_reference="rules/04-functional-programming.md"
                            )
                            self.opportunities.append(opportunity)
                            break
                            
            except Exception as e:
                print(f"  ⚠️ {py_file} 분석 실패: {e}")
    
    def _find_impure_function_violations(self) -> None:
        """순수함수 위반 탐지 (High)"""
        print("  🎯 순수함수 위반 검사...")
        
        for py_file in self.target_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # global 변수 사용 함수 탐지
                        for child in ast.walk(node):
                            if isinstance(child, ast.Global):
                                line_num = getattr(node, 'lineno', 0)
                                snippet = self._get_code_snippet(content, line_num)
                                
                                opportunity = RuleBasedOpportunity(
                                    file_path=str(py_file.relative_to(Path.cwd())),
                                    line_number=line_num,
                                    rule_category="순수함수 원칙",
                                    rule_priority=RulePriority.HIGH,
                                    description=f"함수 '{node.name}'에서 global 변수 사용",
                                    rfs_solution="@pure_function with dependency injection",
                                    impact_score=8.0,
                                    effort_hours=2.5,
                                    code_snippet=snippet,
                                    rule_reference="rules/04-functional-programming.md"
                                )
                                self.opportunities.append(opportunity)
                                
            except Exception as e:
                print(f"  ⚠️ {py_file} 분석 실패: {e}")
    
    def _find_imperative_loop_violations(self) -> None:
        """명령형 루프 위반 탐지 (Medium)"""
        print("  🔄 명령형 루프 패턴 검사...")
        
        for py_file in self.target_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.For):
                        # 결과 리스트 축적 패턴 탐지
                        has_append = False
                        for child in ast.walk(node):
                            if (isinstance(child, ast.Call) and 
                                isinstance(child.func, ast.Attribute) and
                                child.func.attr == 'append'):
                                has_append = True
                                break
                        
                        if has_append:
                            line_num = getattr(node, 'lineno', 0)
                            snippet = self._get_code_snippet(content, line_num)
                            
                            # 상대 경로 변환 시도, 실패하면 절대 경로 사용
                            try:
                                relative_path = str(py_file.relative_to(Path.cwd()))
                            except ValueError:
                                relative_path = str(py_file)
                            
                            opportunity = RuleBasedOpportunity(
                                file_path=relative_path,
                                line_number=line_num,
                                rule_category="Map/Filter 패턴",
                                rule_priority=RulePriority.MEDIUM,
                                description="명령형 루프를 map/filter 패턴으로 변경",
                                rfs_solution="@functional_transform with map/filter chain",
                                impact_score=6.0,
                                effort_hours=1.0,
                                code_snippet=snippet,
                                rule_reference="rules/04-functional-programming.md"
                            )
                            self.opportunities.append(opportunity)
                            
            except Exception as e:
                print(f"  ⚠️ {py_file} 분석 실패: {e}")
    
    def _find_hof_opportunities(self) -> None:
        """고차함수 적용 기회 탐지 (Medium)"""
        print("  🎭 고차함수 적용 기회 검사...")
        
        # 중복 제거 패턴 탐지
        for py_file in self.target_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 단순한 중복 제거 패턴 탐지
                if 'seen = set()' in content or 'unique = []' in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if 'seen = set()' in line or 'unique = []' in line:
                            # 상대 경로 변환 시도, 실패하면 절대 경로 사용
                            try:
                                relative_path = str(py_file.relative_to(Path.cwd()))
                            except ValueError:
                                relative_path = str(py_file)
                            
                            opportunity = RuleBasedOpportunity(
                                file_path=relative_path,
                                line_number=i,
                                rule_category="고차함수 패턴",
                                rule_priority=RulePriority.MEDIUM,
                                description="수동 중복제거를 deduplicate_with_merge HOF로 변경",
                                rfs_solution="@higher_order_function with deduplicate_with_merge",
                                impact_score=5.5,
                                effort_hours=1.5,
                                code_snippet=line.strip(),
                                rule_reference="rules/04-functional-programming.md"
                            )
                            self.opportunities.append(opportunity)
                            
            except Exception as e:
                print(f"  ⚠️ {py_file} 분석 실패: {e}")
    
    def _find_service_pattern_opportunities(self) -> None:
        """서비스 패턴 적용 기회 탐지 (Low)"""
        print("  🏗️ 서비스 패턴 적용 기회 검사...")
        
        for py_file in self.target_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Service나 Manager 클래스 탐지
                        if (node.name.endswith('Service') or 
                            node.name.endswith('Manager') or
                            node.name.endswith('Handler')):
                            
                            line_num = getattr(node, 'lineno', 0)
                            snippet = self._get_code_snippet(content, line_num)
                            
                            # 상대 경로 변환 시도, 실패하면 절대 경로 사용
                            try:
                                relative_path = str(py_file.relative_to(Path.cwd()))
                            except ValueError:
                                relative_path = str(py_file)
                            
                            opportunity = RuleBasedOpportunity(
                                file_path=relative_path,
                                line_number=line_num,
                                rule_category="서비스 패턴",
                                rule_priority=RulePriority.LOW,
                                description=f"클래스 '{node.name}'을 RFS 서비스 패턴으로 변경",
                                rfs_solution="StatelessService extension with @service_method",
                                impact_score=4.0,
                                effort_hours=3.0,
                                code_snippet=snippet,
                                rule_reference="rules/05-v2-architecture.md"
                            )
                            self.opportunities.append(opportunity)
                            
            except Exception as e:
                print(f"  ⚠️ {py_file} 분석 실패: {e}")
    
    def _get_code_snippet(self, content: str, line_num: int, context_lines: int = 2) -> str:
        """코드 스니펫 추출"""
        lines = content.split('\n')
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        return '\n'.join(lines[start:end])
    
    def create_rule_based_batches(self) -> List[RuleBatch]:
        """규칙 기반 배치 생성"""
        print("\n📦 규칙 기반 배치 생성 중...")
        
        # 우선순위별로 기회들을 그룹화
        priority_groups = {}
        for opp in self.opportunities:
            priority = opp.rule_priority
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(opp)
        
        batches = []
        batch_id = 1
        
        # Critical 우선순위 배치 (빌드 차단 요소)
        if RulePriority.CRITICAL in priority_groups:
            critical_opps = priority_groups[RulePriority.CRITICAL]
            batch = self._create_batch(
                batch_id, "Critical - 빌드 차단 요소 해결", 
                RulePriority.CRITICAL, critical_opps
            )
            batches.append(batch)
            batch_id += 1
        
        # High 우선순위 배치들 (함수형 프로그래밍 핵심)
        if RulePriority.HIGH in priority_groups:
            high_opps = priority_groups[RulePriority.HIGH]
            
            # 불변성 배치
            immutability_opps = [o for o in high_opps if "불변성" in o.rule_category]
            if immutability_opps:
                batch = self._create_batch(
                    batch_id, "High - 불변성 원칙 적용", 
                    RulePriority.HIGH, immutability_opps[:10]
                )
                batches.append(batch)
                batch_id += 1
            
            # 순수함수 배치
            pure_func_opps = [o for o in high_opps if "순수함수" in o.rule_category]
            if pure_func_opps:
                batch = self._create_batch(
                    batch_id, "High - 순수함수 원칙 적용", 
                    RulePriority.HIGH, pure_func_opps[:10]
                )
                batches.append(batch)
                batch_id += 1
        
        # Medium 우선순위 배치들 (코드 품질 향상)
        if RulePriority.MEDIUM in priority_groups:
            medium_opps = priority_groups[RulePriority.MEDIUM]
            
            # Map/Filter 패턴 배치
            map_filter_opps = [o for o in medium_opps if "Map/Filter" in o.rule_category]
            if map_filter_opps:
                batch = self._create_batch(
                    batch_id, "Medium - Map/Filter 패턴 적용", 
                    RulePriority.MEDIUM, map_filter_opps[:10]
                )
                batches.append(batch)
                batch_id += 1
            
            # 고차함수 배치
            hof_opps = [o for o in medium_opps if "고차함수" in o.rule_category]
            if hof_opps:
                batch = self._create_batch(
                    batch_id, "Medium - 고차함수 패턴 적용", 
                    RulePriority.MEDIUM, hof_opps[:10]
                )
                batches.append(batch)
                batch_id += 1
        
        # Low 우선순위 배치들 (일반적인 개선)
        if RulePriority.LOW in priority_groups:
            low_opps = priority_groups[RulePriority.LOW]
            
            # 10개씩 나누어 배치 생성
            for i in range(0, len(low_opps), 10):
                batch_opps = low_opps[i:i+10]
                batch = self._create_batch(
                    batch_id, f"Low - 서비스 패턴 적용 #{(i//10)+1}", 
                    RulePriority.LOW, batch_opps
                )
                batches.append(batch)
                batch_id += 1
        
        return batches
    
    def _create_batch(self, batch_id: int, focus: str, priority: RulePriority, 
                     opportunities: List[RuleBasedOpportunity]) -> RuleBatch:
        """배치 생성"""
        batch = RuleBatch(
            batch_id=batch_id,
            rule_focus=focus,
            priority=priority,
            opportunities=opportunities
        )
        
        # 배치 메트릭 계산
        batch.total_impact = sum(o.impact_score for o in opportunities)
        batch.total_effort = sum(o.effort_hours for o in opportunities)
        batch.roi_score = (batch.total_impact / batch.total_effort) if batch.total_effort > 0 else 0
        
        return batch
    
    def generate_batch_report(self, batches: List[RuleBatch]) -> None:
        """배치 리포트 생성"""
        print("\n" + "="*80)
        print("📋 규칙 기반 RFS 적용 배치 리포트")
        print("="*80)
        
        # 전체 통계
        total_opportunities = sum(len(b.opportunities) for b in batches)
        total_impact = sum(b.total_impact for b in batches)
        total_effort = sum(b.total_effort for b in batches)
        avg_roi = (total_impact / total_effort) if total_effort > 0 else 0
        
        print(f"\n📊 전체 통계:")
        print(f"   • 총 배치 수: {len(batches)}개")
        print(f"   • 총 기회 수: {total_opportunities}개")
        print(f"   • 총 임팩트: {total_impact:.1f}")
        print(f"   • 총 소요시간: {total_effort:.1f}시간")
        print(f"   • 평균 ROI: {avg_roi:.2f}")
        
        # 우선순위별 통계
        priority_stats = {}
        for batch in batches:
            priority = batch.priority
            if priority not in priority_stats:
                priority_stats[priority] = {
                    'count': 0, 'opportunities': 0, 'impact': 0.0, 'effort': 0.0
                }
            
            priority_stats[priority]['count'] += 1
            priority_stats[priority]['opportunities'] += len(batch.opportunities)
            priority_stats[priority]['impact'] += batch.total_impact
            priority_stats[priority]['effort'] += batch.total_effort
        
        print(f"\n🎯 우선순위별 통계:")
        for priority in RulePriority:
            if priority in priority_stats:
                stats = priority_stats[priority]
                roi = (stats['impact'] / stats['effort']) if stats['effort'] > 0 else 0
                print(f"   • {priority.name}: {stats['count']}배치, "
                      f"{stats['opportunities']}기회, "
                      f"ROI {roi:.2f}")
        
        # 배치별 상세 정보
        print(f"\n📦 배치별 상세 정보:")
        for i, batch in enumerate(batches[:5], 1):  # 상위 5개만 출력
            print(f"\n   {batch.batch_id}. {batch.rule_focus}")
            print(f"      우선순위: {batch.priority.name}")
            print(f"      기회 수: {len(batch.opportunities)}개")
            print(f"      임팩트: {batch.total_impact:.1f}")
            print(f"      소요시간: {batch.total_effort:.1f}시간")
            print(f"      ROI: {batch.roi_score:.2f}")
            
            # 주요 기회 3개 출력
            top_opps = sorted(batch.opportunities, 
                            key=lambda x: x.impact_score, reverse=True)[:3]
            for opp in top_opps:
                print(f"        • {Path(opp.file_path).name}:{opp.line_number} - "
                      f"{opp.description} (임팩트: {opp.impact_score:.1f})")
        
        if len(batches) > 5:
            print(f"\n   ... 및 추가 {len(batches) - 5}개 배치")
    
    def save_batches_to_json(self, batches: List[RuleBatch], 
                           output_file: str = "rule_based_rfs_batches.json") -> None:
        """배치를 JSON 파일로 저장"""
        output_path = Path(output_file)
        
        # 직렬화 가능한 형태로 변환
        batches_data = []
        for batch in batches:
            batch_data = {
                'batch_id': batch.batch_id,
                'rule_focus': batch.rule_focus,
                'priority': batch.priority.name,
                'total_impact': batch.total_impact,
                'total_effort': batch.total_effort,
                'roi_score': batch.roi_score,
                'opportunities': []
            }
            
            for opp in batch.opportunities:
                opp_data = {
                    'file_path': opp.file_path,
                    'line_number': opp.line_number,
                    'rule_category': opp.rule_category,
                    'priority': opp.rule_priority.name,
                    'description': opp.description,
                    'rfs_solution': opp.rfs_solution,
                    'impact_score': opp.impact_score,
                    'effort_hours': opp.effort_hours,
                    'code_snippet': opp.code_snippet,
                    'rule_reference': opp.rule_reference
                }
                batch_data['opportunities'].append(opp_data)
            
            batches_data.append(batch_data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(batches_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 배치 데이터가 {output_path}에 저장되었습니다.")

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="규칙 기반 RFS 배치 생성기")
    parser.add_argument('--target-dir', default='app/services/v2',
                       help='분석할 대상 디렉토리')
    parser.add_argument('--output', default='rule_based_rfs_batches.json',
                       help='출력 JSON 파일명')
    parser.add_argument('--show-critical-only', action='store_true',
                       help='Critical 우선순위만 표시')
    
    args = parser.parse_args()
    
    generator = RuleBasedBatchGenerator(args.target_dir)
    
    # 분석 실행
    generator.analyze_rule_violations()
    
    # 배치 생성
    batches = generator.create_rule_based_batches()
    
    # Critical 우선순위만 필터링 (옵션)
    if args.show_critical_only:
        batches = [b for b in batches if b.priority == RulePriority.CRITICAL]
    
    # 리포트 생성
    generator.generate_batch_report(batches)
    
    # JSON 저장
    generator.save_batches_to_json(batches, args.output)
    
    return batches

if __name__ == "__main__":
    main()