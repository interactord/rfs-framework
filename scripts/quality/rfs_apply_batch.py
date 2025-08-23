#!/usr/bin/env python3
"""
RFS Framework Batch Applicator

RFS 프레임워크 적용 기회를 배치 단위로 실제 코드에 적용하는 스크립트

This script applies RFS framework opportunities to the actual codebase
in batches of 10 items, with validation and rollback capabilities.
"""

import ast
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import json
import argparse
import tempfile
import shutil
from datetime import datetime
from enum import Enum

# rfs_adoption_check.py에서 클래스들을 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rfs_adoption_check import (
    RFSAdoptionChecker, RFSOpportunity, ApplicationBatch, 
    BatchApplicator, FileAnalysisResult
)

class RulePriority(Enum):
    """규칙 기반 우선순위"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class ApplyResult:
    """적용 결과"""
    success: bool
    file_path: str
    changes_made: List[str]
    error_message: Optional[str] = None
    rollback_data: Optional[str] = None


class RuleBatchLoader:
    """규칙 기반 배치 로더"""
    
    def load_rule_batches(self, batch_file: str = "updated_rule_batches.json") -> List[ApplicationBatch]:
        """규칙 기반 배치를 ApplicationBatch 형태로 로드"""
        batch_path = Path(batch_file)
        if not batch_path.exists():
            print(f"⚠️ 규칙 기반 배치 파일을 찾을 수 없습니다: {batch_file}")
            return []
        
        with open(batch_path, 'r', encoding='utf-8') as f:
            rule_batches_data = json.load(f)
        
        application_batches = []
        
        for batch_data in rule_batches_data:
            # RFS 기회로 변환
            opportunities = []
            for opp_data in batch_data['opportunities']:
                opportunity = RFSOpportunity(
                    file_path=opp_data['file_path'],
                    line_number=opp_data['line_number'],
                    opportunity_type=opp_data['rule_category'],
                    description=opp_data['description'],
                    suggestion=opp_data['rfs_solution'],
                    severity='high' if batch_data['priority'] in ['CRITICAL', 'HIGH'] else 'medium'
                )
                opportunities.append(opportunity)
            
            # ApplicationBatch로 변환
            app_batch = ApplicationBatch(
                batch_id=batch_data['batch_id'],
                opportunities=opportunities,
                priority=batch_data['priority'].lower(),  # CRITICAL -> critical
                estimated_time=batch_data['total_effort'],
                complexity='complex' if batch_data['priority'] in ['CRITICAL', 'HIGH'] else 'medium',
                roi_score=batch_data['roi_score']
            )
            
            # 추가 정보
            app_batch.description = batch_data['rule_focus']
            app_batch.total_impact = batch_data['total_impact']
            application_batches.append(app_batch)
        
        return application_batches


class CodeModifier:
    """코드 수정 엔진"""
    
    def __init__(self):
        self.backup_dir = None
        
    def apply_opportunity(self, opportunity: RFSOpportunity) -> ApplyResult:
        """기회를 실제 코드에 적용"""
        file_path = opportunity.file_path
        
        # 백업 생성
        backup_content = self._create_backup(file_path)
        
        try:
            if opportunity.opportunity_type == 'stateless_service':
                return self._apply_stateless_service(opportunity, backup_content)
            elif opportunity.opportunity_type == 'service_method_decorator':
                return self._apply_service_method_decorator(opportunity, backup_content)
            elif opportunity.opportunity_type == 'cache_decorator':
                return self._apply_cache_decorator(opportunity, backup_content)
            elif opportunity.opportunity_type == 'performance_decorator':
                return self._apply_performance_decorator(opportunity, backup_content)
            elif opportunity.opportunity_type == 'validation_decorator':
                return self._apply_validation_decorator(opportunity, backup_content)
            elif opportunity.opportunity_type == 'logging_decorator':
                return self._apply_logging_decorator(opportunity, backup_content)
            elif opportunity.opportunity_type == 'retry_decorator':
                return self._apply_retry_decorator(opportunity, backup_content)
            else:
                return ApplyResult(
                    success=False,
                    file_path=file_path,
                    changes_made=[],
                    error_message=f"Unsupported opportunity type: {opportunity.opportunity_type}"
                )
                
        except Exception as e:
            # 롤백
            self._restore_backup(file_path, backup_content)
            return ApplyResult(
                success=False,
                file_path=file_path,
                changes_made=[],
                error_message=str(e),
                rollback_data=backup_content
            )
    
    def _create_backup(self, file_path: str) -> str:
        """파일 백업 생성"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _restore_backup(self, file_path: str, backup_content: str) -> None:
        """백업에서 복원"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(backup_content)
    
    def _apply_stateless_service(self, opportunity: RFSOpportunity, backup: str) -> ApplyResult:
        """StatelessService 상속 적용"""
        file_path = opportunity.file_path
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            lines = content.splitlines()
            changes_made = []
            
            # StatelessService import 추가
            import_added = False
            for i, line in enumerate(lines):
                if line.strip().startswith('from') and 'app.rfs' in line:
                    import_added = True
                    break
                elif line.strip().startswith('import') and not line.strip().startswith('from'):
                    # import 섹션 끝에 추가
                    lines.insert(i + 1, "from app.rfs import ServiceRegistry, StatelessService")
                    import_added = True
                    changes_made.append("Added StatelessService import")
                    break
            
            if not import_added:
                # 파일 시작 부분에 추가
                lines.insert(0, "from app.rfs import ServiceRegistry, StatelessService")
                changes_made.append("Added StatelessService import at top")
            
            # 클래스 상속 수정
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if any(pattern in node.name for pattern in ['Service', 'Manager', 'Processor', 'Handler']):
                        # 해당 라인 찾기
                        for i, line in enumerate(lines):
                            if f"class {node.name}" in line and ":" in line:
                                if "StatelessService" not in line:
                                    if "(" in line:
                                        # 기존 상속이 있는 경우
                                        lines[i] = line.replace(":", ", StatelessService:")
                                    else:
                                        # 상속이 없는 경우
                                        lines[i] = line.replace(":", "(StatelessService):")
                                    changes_made.append(f"Added StatelessService inheritance to {node.name}")
                                break
            
            # 파일 저장
            modified_content = '\n'.join(lines)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            return ApplyResult(
                success=True,
                file_path=file_path,
                changes_made=changes_made,
                rollback_data=backup
            )
            
        except Exception as e:
            return ApplyResult(
                success=False,
                file_path=file_path,
                changes_made=[],
                error_message=f"Error applying StatelessService: {e}",
                rollback_data=backup
            )
    
    def _apply_service_method_decorator(self, opportunity: RFSOpportunity, backup: str) -> ApplyResult:
        """@service_method 데코레이터 적용"""
        file_path = opportunity.file_path
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.splitlines()
            changes_made = []
            
            # 데코레이터 import 추가
            import_added = False
            for i, line in enumerate(lines):
                if 'from app.rfs.services.decorators import' in line:
                    if 'service_method' not in line:
                        lines[i] = line.replace('import', 'import service_method,')
                        changes_made.append("Added service_method to existing import")
                    import_added = True
                    break
                elif line.strip().startswith('from app.rfs'):
                    lines.insert(i + 1, "from app.rfs.services.decorators import service_method")
                    import_added = True
                    changes_made.append("Added service_method import")
                    break
            
            if not import_added:
                # import 섹션에 추가
                for i, line in enumerate(lines):
                    if line.strip().startswith('import') or line.strip().startswith('from'):
                        continue
                    lines.insert(i, "from app.rfs.services.decorators import service_method")
                    changes_made.append("Added service_method import")
                    break
            
            # 메서드에 데코레이터 추가 (라인 번호 기반)
            target_line = opportunity.line_number - 1  # 0-based index
            if target_line < len(lines):
                method_line = lines[target_line]
                if 'def ' in method_line and '@service_method' not in lines[target_line - 1]:
                    # 인덴테이션 맞춤
                    indent = len(method_line) - len(method_line.lstrip())
                    decorator_line = ' ' * indent + '@service_method'
                    lines.insert(target_line, decorator_line)
                    changes_made.append(f"Added @service_method decorator at line {opportunity.line_number}")
            
            # 파일 저장
            modified_content = '\n'.join(lines)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            return ApplyResult(
                success=True,
                file_path=file_path,
                changes_made=changes_made,
                rollback_data=backup
            )
            
        except Exception as e:
            return ApplyResult(
                success=False,
                file_path=file_path,
                changes_made=[],
                error_message=f"Error applying @service_method: {e}",
                rollback_data=backup
            )
    
    def _apply_cache_decorator(self, opportunity: RFSOpportunity, backup: str) -> ApplyResult:
        """@cache_result 데코레이터 적용"""
        # 유사한 구현...
        return ApplyResult(
            success=False,
            file_path=opportunity.file_path,
            changes_made=[],
            error_message="Cache decorator application not implemented yet"
        )
    
    def _apply_performance_decorator(self, opportunity: RFSOpportunity, backup: str) -> ApplyResult:
        """@measure_performance 데코레이터 적용"""
        # 유사한 구현...
        return ApplyResult(
            success=False,
            file_path=opportunity.file_path,
            changes_made=[],
            error_message="Performance decorator application not implemented yet"
        )
    
    def _apply_validation_decorator(self, opportunity: RFSOpportunity, backup: str) -> ApplyResult:
        """@validate_args 데코레이터 적용"""
        # 유사한 구현...
        return ApplyResult(
            success=False,
            file_path=opportunity.file_path,
            changes_made=[],
            error_message="Validation decorator application not implemented yet"
        )
    
    def _apply_logging_decorator(self, opportunity: RFSOpportunity, backup: str) -> ApplyResult:
        """@log_execution 데코레이터 적용"""
        # 유사한 구현...
        return ApplyResult(
            success=False,
            file_path=opportunity.file_path,
            changes_made=[],
            error_message="Logging decorator application not implemented yet"
        )
    
    def _apply_retry_decorator(self, opportunity: RFSOpportunity, backup: str) -> ApplyResult:
        """@retry 데코레이터 적용"""
        # 유사한 구현...
        return ApplyResult(
            success=False,
            file_path=opportunity.file_path,
            changes_made=[],
            error_message="Retry decorator application not implemented yet"
        )


class BatchProcessor:
    """배치 처리기"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.modifier = CodeModifier()
        self.results: List[ApplyResult] = []
        
    def apply_batch(self, batch: ApplicationBatch) -> Tuple[bool, List[ApplyResult]]:
        """배치 적용"""
        print(f"📦 Applying Batch #{batch.batch_id} ({len(batch.opportunities)} items)")
        print(f"   Priority: {batch.priority}, Complexity: {batch.complexity}")
        print(f"   Estimated time: {batch.estimated_time:.1f}h")
        print()
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No actual changes will be made")
            return self._simulate_batch(batch)
        
        results = []
        successful_count = 0
        
        for i, opportunity in enumerate(batch.opportunities, 1):
            print(f"  {i:2}/{len(batch.opportunities)} Processing {opportunity.file_path}:{opportunity.line_number}")
            print(f"      ➜ {opportunity.description}")
            
            result = self.modifier.apply_opportunity(opportunity)
            results.append(result)
            
            if result.success:
                successful_count += 1
                print(f"      ✅ Success: {', '.join(result.changes_made)}")
            else:
                print(f"      ❌ Failed: {result.error_message}")
                
                # 실패 시 롤백 여부 확인
                if not self._should_continue_on_error():
                    print("🔄 Rolling back all changes in this batch...")
                    self._rollback_batch_changes(results)
                    return False, results
            
            print()
        
        success_rate = successful_count / len(batch.opportunities) * 100
        print(f"📊 Batch #{batch.batch_id} Results:")
        print(f"   ✅ Successful: {successful_count}/{len(batch.opportunities)} ({success_rate:.1f}%)")
        print(f"   ❌ Failed: {len(batch.opportunities) - successful_count}")
        
        # 테스트 실행
        if successful_count > 0:
            print("\n🧪 Running validation tests...")
            if self._run_validation_tests():
                print("✅ All tests passed")
                return True, results
            else:
                print("❌ Tests failed - rolling back changes")
                self._rollback_batch_changes(results)
                return False, results
        
        return successful_count == len(batch.opportunities), results
    
    def _simulate_batch(self, batch: ApplicationBatch) -> Tuple[bool, List[ApplyResult]]:
        """배치 시뮬레이션"""
        results = []
        
        for i, opportunity in enumerate(batch.opportunities, 1):
            print(f"  {i:2}/{len(batch.opportunities)} Would process {opportunity.file_path}:{opportunity.line_number}")
            print(f"      ➜ {opportunity.description}")
            print(f"      📝 Would apply: {opportunity.opportunity_type}")
            
            # 시뮬레이션 결과
            result = ApplyResult(
                success=True,
                file_path=opportunity.file_path,
                changes_made=[f"Would apply {opportunity.opportunity_type}"],
                error_message=None
            )
            results.append(result)
            print()
        
        print(f"✅ Dry run completed - {len(batch.opportunities)} changes would be made")
        return True, results
    
    def _should_continue_on_error(self) -> bool:
        """에러 발생 시 계속 진행할지 확인"""
        # 향후 대화형 모드에서 사용자 입력 받기
        return False  # 기본적으로 중단
    
    def _rollback_batch_changes(self, results: List[ApplyResult]) -> None:
        """배치 변경사항 롤백"""
        for result in results:
            if result.success and result.rollback_data:
                try:
                    with open(result.file_path, 'w', encoding='utf-8') as f:
                        f.write(result.rollback_data)
                    print(f"🔄 Rolled back {result.file_path}")
                except Exception as e:
                    print(f"❌ Failed to rollback {result.file_path}: {e}")
    
    def _run_validation_tests(self) -> bool:
        """유효성 검사 테스트 실행"""
        try:
            # 타입 체킹
            result = subprocess.run(['python', '-m', 'py_compile'], 
                                  capture_output=True, text=True, cwd=Path.cwd())
            if result.returncode != 0:
                print(f"❌ Syntax check failed: {result.stderr}")
                return False
            
            # 기본 import 테스트
            result = subprocess.run(['python', '-c', 'import app.rfs'], 
                                  capture_output=True, text=True, cwd=Path.cwd())
            if result.returncode != 0:
                print(f"❌ Import test failed: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Validation test error: {e}")
            return False


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='Apply RFS framework opportunities in batches'
    )
    parser.add_argument(
        '--target-dir',
        default='app/services/v2',
        help='Target directory to analyze and apply changes'
    )
    parser.add_argument(
        '--batch-id',
        type=int,
        required=True,
        help='Batch ID to apply (1, 2, 3, ...)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of items per batch (default: 10)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--priority',
        choices=['high', 'medium', 'low'],
        help='Filter by priority level'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive mode with user confirmations'
    )
    
    args = parser.parse_args()
    
    print("🔍 Analyzing RFS adoption opportunities...")
    
    # 기회 분석
    checker = RFSAdoptionChecker(args.target_dir)
    checker.analyze()
    
    # 규칙 기반 배치 로드
    rule_loader = RuleBatchLoader()
    rule_batches = rule_loader.load_rule_batches()
    
    # 기존 분석 결과를 배치로 변환
    analysis_batches = []
    if checker.results:
        all_opportunities = []
        for result in checker.results:
            all_opportunities.extend(result.opportunities)
        
        # 10개씩 배치로 나누기
        batch_size = args.batch_size
        for i in range(0, len(all_opportunities), batch_size):
            batch_opportunities = all_opportunities[i:i+batch_size]
            analysis_batch = ApplicationBatch(
                batch_id=len(rule_batches) + (i // batch_size) + 1,
                opportunities=batch_opportunities,
                priority="medium",
                estimated_time=10.0,  # 기본값
                complexity="medium",
                roi_score=0.0
            )
            analysis_batch.description = f"Analysis-based RFS adoption #{(i//batch_size)+1}"
            analysis_batch.total_impact = 50.0  # 기본값
            analysis_batch.priority = "medium"  # 기본 우선순위
            analysis_batches.append(analysis_batch)
    
    # 모든 배치 통합
    all_batches = rule_batches + analysis_batches
    
    if not all_batches:
        print("✅ No opportunities found - RFS framework is fully adopted!")
        return 0
    
    # 우선순위별 정렬
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    all_batches.sort(key=lambda b: (
        priority_order.get(getattr(b, 'priority', 'low'), 4),
        -getattr(b, 'total_impact', 0)
    ))
    
    # 배치 ID로 필터링
    target_batch = None
    for batch in all_batches:
        if batch.batch_id == args.batch_id:
            target_batch = batch
            break
    
    if not target_batch:
        print(f"❌ Batch {args.batch_id} not found")
        print(f"Available batches: {[b.batch_id for b in all_batches]}")
        return 1
    
    # 모든 기회 수집 (하위 호환성)
    all_opportunities = target_batch.opportunities
    
    # 우선순위 필터링
    if args.priority:
        all_opportunities = [
            opp for opp in all_opportunities 
            if opp.severity == args.priority
        ]
    
    if not all_opportunities:
        print(f"No {args.priority} priority opportunities found.")
        return 0
    
    # 배치 생성
    batch_applicator = BatchApplicator(all_opportunities, args.batch_size)
    batches = batch_applicator.create_batches()
    
    if args.batch_id > len(batches):
        print(f"❌ Batch #{args.batch_id} does not exist. Available batches: 1-{len(batches)}")
        return 1
    
    target_batch = batches[args.batch_id - 1]
    
    # 배치 적용
    processor = BatchProcessor(dry_run=args.dry_run)
    
    if args.interactive:
        print(f"\n📋 Batch #{target_batch.batch_id} Summary:")
        print(f"   Items: {len(target_batch.opportunities)}")
        print(f"   Priority: {target_batch.priority}")
        print(f"   Complexity: {target_batch.complexity}")
        print(f"   Estimated time: {target_batch.estimated_time:.1f}h")
        print()
        
        response = input("Continue with this batch? [y/N]: ").strip().lower()
        if response != 'y':
            print("❌ Aborted by user")
            return 1
    
    success, results = processor.apply_batch(target_batch)
    
    # 결과 요약
    if success:
        print("\n🎉 Batch application completed successfully!")
        if not args.dry_run:
            print("💡 Consider running tests to verify the changes")
            print("💡 Don't forget to commit your changes")
        return 0
    else:
        print("\n❌ Batch application failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())