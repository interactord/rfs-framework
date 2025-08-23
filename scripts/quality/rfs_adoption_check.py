#!/usr/bin/env python3
"""
RFS Framework Adoption Checker

V2 코드베이스에서 RFS 프레임워크 기능을 사용할 수 있지만 
사용하지 않는 부분을 검사하는 스크립트

This script analyzes the V2 codebase to identify opportunities to adopt
RFS (React Functional Services) framework features.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import json
import argparse
import math
from datetime import datetime, timedelta


@dataclass
class RFSOpportunity:
    """RFS 프레임워크 적용 기회"""
    file_path: str
    line_number: int
    opportunity_type: str
    description: str
    suggestion: str
    severity: str  # 'high', 'medium', 'low'
    
    def to_dict(self) -> dict:
        return {
            'file': self.file_path,
            'line': self.line_number,
            'type': self.opportunity_type,
            'description': self.description,
            'suggestion': self.suggestion,
            'severity': self.severity
        }


@dataclass
class FileAnalysisResult:
    """파일 분석 결과"""
    file_path: str
    opportunities: List[RFSOpportunity] = field(default_factory=list)
    rfs_score: float = 0.0  # 0-100 scale
    
    def calculate_score(self) -> None:
        """RFS 적용 점수 계산"""
        # 기본 점수 100에서 기회당 감점
        base_score = 100
        for opp in self.opportunities:
            if opp.severity == 'high':
                base_score -= 10
            elif opp.severity == 'medium':
                base_score -= 5
            else:
                base_score -= 2
        self.rfs_score = max(0, base_score)


@dataclass
class CategoryScore:
    """카테고리별 점수"""
    name: str
    current: int
    total: int
    percentage: float
    weight: float
    weighted_score: float


@dataclass
class OverallMetrics:
    """전체 메트릭"""
    overall_score: float
    grade: str
    maturity_level: int
    category_scores: List[CategoryScore]
    estimated_hours: float
    total_batches: int
    trend_direction: str = "stable"
    trend_percentage: float = 0.0


class RFSScoreCalculator:
    """RFS 프레임워크 종합 스코어 계산기"""
    
    # 카테고리별 가중치 (총합 1.0)
    CATEGORY_WEIGHTS = {
        'stateless_service': 0.25,      # 가장 중요
        'service_method_decorator': 0.20,
        'cache_decorator': 0.15,
        'performance_decorator': 0.15,
        'validation_decorator': 0.10,
        'logging_decorator': 0.05,
        'retry_decorator': 0.05,
        'railway_pattern': 0.03,
        'result_type': 0.02
    }
    
    # 성숙도 레벨 임계값
    MATURITY_THRESHOLDS = [
        (90, 5, "Expert"),
        (75, 4, "Advanced"),
        (60, 3, "Intermediate"),
        (40, 2, "Growing"),
        (0, 1, "Beginner")
    ]
    
    def __init__(self, results: List[FileAnalysisResult], statistics: Dict):
        self.results = results
        self.statistics = statistics
        self.baseline_file = "scripts/quality/rfs_baseline.json"
        
    def calculate_comprehensive_score(self) -> OverallMetrics:
        """종합 점수 계산"""
        category_scores = self._calculate_category_scores()
        overall_score = self._calculate_weighted_score(category_scores)
        grade = self._calculate_grade(overall_score)
        maturity_level, maturity_name = self._calculate_maturity(overall_score)
        estimated_hours = self._estimate_completion_time()
        total_batches = math.ceil(self.statistics['total_opportunities'] / 10)
        
        # 트렌드 분석
        trend_direction, trend_percentage = self._analyze_trend(overall_score)
        
        return OverallMetrics(
            overall_score=overall_score,
            grade=grade,
            maturity_level=maturity_level,
            category_scores=category_scores,
            estimated_hours=estimated_hours,
            total_batches=total_batches,
            trend_direction=trend_direction,
            trend_percentage=trend_percentage
        )
    
    def _calculate_category_scores(self) -> List[CategoryScore]:
        """카테고리별 점수 계산"""
        category_scores = []
        
        for category, weight in self.CATEGORY_WEIGHTS.items():
            current = self.statistics.get(category, 0)
            total = self._estimate_total_possible(category)
            percentage = (1 - current / max(total, 1)) * 100  # 기회가 적을수록 높은 점수
            weighted_score = percentage * weight
            
            category_scores.append(CategoryScore(
                name=category,
                current=current,
                total=total,
                percentage=percentage,
                weight=weight,
                weighted_score=weighted_score
            ))
            
        return category_scores
    
    def _estimate_total_possible(self, category: str) -> int:
        """각 카테고리의 총 가능한 수 추정"""
        # 실제 코드베이스 분석을 통한 추정값
        estimates = {
            'stateless_service': 20,      # 서비스 클래스 수
            'service_method_decorator': 150,  # 공개 메서드 수
            'cache_decorator': 300,       # 캐시 가능한 메서드 수
            'performance_decorator': 200,  # 성능 측정 대상 메서드
            'validation_decorator': 400,   # 유효성 검증 필요 메서드
            'logging_decorator': 250,     # 로깅 대상 메서드
            'retry_decorator': 50,        # 재시도 필요 메서드
            'railway_pattern': 500,       # try-catch 블록 수
            'result_type': 600           # 예외 발생 지점 수
        }
        return estimates.get(category, 100)
    
    def _calculate_weighted_score(self, category_scores: List[CategoryScore]) -> float:
        """가중 평균 점수 계산"""
        return sum(score.weighted_score for score in category_scores)
    
    def _calculate_grade(self, score: float) -> str:
        """점수를 등급으로 변환"""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "A-"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "B-"
        elif score >= 65:
            return "C+"
        elif score >= 60:
            return "C"
        elif score >= 55:
            return "C-"
        elif score >= 50:
            return "D+"
        elif score >= 45:
            return "D"
        else:
            return "F"
    
    def _calculate_maturity(self, score: float) -> Tuple[int, str]:
        """성숙도 레벨 계산"""
        for threshold, level, name in self.MATURITY_THRESHOLDS:
            if score >= threshold:
                return level, name
        return 1, "Beginner"
    
    def _estimate_completion_time(self) -> float:
        """완료 예상 시간 계산 (시간 단위)"""
        # 기회 유형별 예상 소요 시간 (분)
        time_estimates = {
            'stateless_service': 30,      # 30분
            'service_method_decorator': 5,
            'cache_decorator': 15,
            'performance_decorator': 10,
            'validation_decorator': 8,
            'logging_decorator': 5,
            'retry_decorator': 20,
            'railway_pattern': 15,
            'result_type': 10
        }
        
        total_minutes = 0
        for opportunity_type, count in self.statistics.items():
            if opportunity_type in time_estimates:
                total_minutes += count * time_estimates[opportunity_type]
                
        return total_minutes / 60  # 시간으로 변환
    
    def _analyze_trend(self, current_score: float) -> Tuple[str, float]:
        """트렌드 분석"""
        try:
            if os.path.exists(self.baseline_file):
                with open(self.baseline_file, 'r', encoding='utf-8') as f:
                    baseline = json.load(f)
                    
                previous_score = baseline.get('overall_score', current_score)
                difference = current_score - previous_score
                
                if abs(difference) < 1:
                    return "stable", 0.0
                elif difference > 0:
                    return "improving", difference
                else:
                    return "declining", abs(difference)
        except:
            pass
            
        return "unknown", 0.0
    
    def save_baseline(self, metrics: OverallMetrics) -> None:
        """현재 결과를 기준선으로 저장"""
        baseline_data = {
            'timestamp': datetime.now().isoformat(),
            'overall_score': metrics.overall_score,
            'grade': metrics.grade,
            'maturity_level': metrics.maturity_level,
            'total_opportunities': self.statistics['total_opportunities'],
            'category_scores': {
                score.name: {
                    'current': score.current,
                    'total': score.total,
                    'percentage': score.percentage
                }
                for score in metrics.category_scores
            }
        }
        
        # 디렉토리 생성
        os.makedirs(os.path.dirname(self.baseline_file), exist_ok=True)
        
        with open(self.baseline_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, indent=2, ensure_ascii=False)


@dataclass
class ApplicationBatch:
    """적용 배치"""
    batch_id: int
    opportunities: List[RFSOpportunity]
    priority: str  # 'high', 'medium', 'low'
    estimated_time: float  # 시간 단위
    complexity: str  # 'easy', 'medium', 'complex'
    roi_score: float  # Return on Investment 점수


class BatchApplicator:
    """배치 단위 적용기"""
    
    # ROI 계산 가중치
    ROI_WEIGHTS = {
        'severity': {'high': 10, 'medium': 5, 'low': 2},
        'impact': {'high': 8, 'medium': 4, 'low': 1},
        'effort': {'easy': 8, 'medium': 4, 'complex': 1}  # 낮은 노력이 높은 점수
    }
    
    def __init__(self, opportunities: List[RFSOpportunity], batch_size: int = 10):
        self.opportunities = opportunities
        self.batch_size = batch_size
        self.batches: List[ApplicationBatch] = []
        
    def create_batches(self) -> List[ApplicationBatch]:
        """우선순위 기반 배치 생성"""
        # ROI 점수로 정렬
        sorted_opportunities = self._sort_by_roi(self.opportunities)
        
        # 배치로 분할
        self.batches = []
        for i in range(0, len(sorted_opportunities), self.batch_size):
            batch_opportunities = sorted_opportunities[i:i + self.batch_size]
            
            batch = ApplicationBatch(
                batch_id=len(self.batches) + 1,
                opportunities=batch_opportunities,
                priority=self._determine_batch_priority(batch_opportunities),
                estimated_time=self._estimate_batch_time(batch_opportunities),
                complexity=self._determine_batch_complexity(batch_opportunities),
                roi_score=self._calculate_batch_roi(batch_opportunities)
            )
            
            self.batches.append(batch)
            
        return self.batches
    
    def _sort_by_roi(self, opportunities: List[RFSOpportunity]) -> List[RFSOpportunity]:
        """ROI 점수 기반 정렬"""
        def calculate_roi(opp: RFSOpportunity) -> float:
            severity_score = self.ROI_WEIGHTS['severity'][opp.severity]
            impact_score = self._calculate_impact_score(opp)
            effort_score = self._calculate_effort_score(opp)
            
            return severity_score * 0.4 + impact_score * 0.4 + effort_score * 0.2
        
        return sorted(opportunities, key=calculate_roi, reverse=True)
    
    def _calculate_impact_score(self, opp: RFSOpportunity) -> float:
        """영향도 점수 계산"""
        # 기회 유형별 영향도
        impact_map = {
            'stateless_service': 'high',
            'service_method_decorator': 'medium',
            'cache_decorator': 'high',
            'performance_decorator': 'high',
            'validation_decorator': 'medium',
            'logging_decorator': 'low',
            'retry_decorator': 'medium',
            'railway_pattern': 'low',
            'result_type': 'low'
        }
        
        impact_level = impact_map.get(opp.opportunity_type, 'medium')
        return self.ROI_WEIGHTS['impact'][impact_level]
    
    def _calculate_effort_score(self, opp: RFSOpportunity) -> float:
        """노력도 점수 계산"""
        # 기회 유형별 구현 복잡도
        effort_map = {
            'stateless_service': 'medium',
            'service_method_decorator': 'easy',
            'cache_decorator': 'medium',
            'performance_decorator': 'easy',
            'validation_decorator': 'easy',
            'logging_decorator': 'easy',
            'retry_decorator': 'medium',
            'railway_pattern': 'complex',
            'result_type': 'complex'
        }
        
        effort_level = effort_map.get(opp.opportunity_type, 'medium')
        return self.ROI_WEIGHTS['effort'][effort_level]
    
    def _determine_batch_priority(self, opportunities: List[RFSOpportunity]) -> str:
        """배치 우선순위 결정"""
        high_count = sum(1 for opp in opportunities if opp.severity == 'high')
        medium_count = sum(1 for opp in opportunities if opp.severity == 'medium')
        
        if high_count > 0:
            return 'high'
        elif medium_count >= len(opportunities) * 0.7:  # 70% 이상이 medium
            return 'medium'
        else:
            return 'low'
    
    def _estimate_batch_time(self, opportunities: List[RFSOpportunity]) -> float:
        """배치 예상 소요 시간 계산"""
        time_estimates = {
            'stateless_service': 0.5,      # 30분
            'service_method_decorator': 0.08,  # 5분
            'cache_decorator': 0.25,       # 15분
            'performance_decorator': 0.17,  # 10분
            'validation_decorator': 0.13,   # 8분
            'logging_decorator': 0.08,     # 5분
            'retry_decorator': 0.33,       # 20분
            'railway_pattern': 0.25,       # 15분
            'result_type': 0.17           # 10분
        }
        
        total_time = 0
        for opp in opportunities:
            total_time += time_estimates.get(opp.opportunity_type, 0.17)
            
        return total_time
    
    def _determine_batch_complexity(self, opportunities: List[RFSOpportunity]) -> str:
        """배치 복잡도 결정"""
        complex_types = ['railway_pattern', 'result_type', 'stateless_service']
        complex_count = sum(1 for opp in opportunities 
                          if opp.opportunity_type in complex_types)
        
        if complex_count >= len(opportunities) * 0.5:  # 50% 이상 복잡함
            return 'complex'
        elif complex_count > 0:
            return 'medium'
        else:
            return 'easy'
    
    def _calculate_batch_roi(self, opportunities: List[RFSOpportunity]) -> float:
        """배치 ROI 점수 계산"""
        if not opportunities:
            return 0.0
            
        total_roi = 0
        for opp in opportunities:
            severity_score = self.ROI_WEIGHTS['severity'][opp.severity]
            impact_score = self._calculate_impact_score(opp)
            effort_score = self._calculate_effort_score(opp)
            
            roi = severity_score * 0.4 + impact_score * 0.4 + effort_score * 0.2
            total_roi += roi
            
        return total_roi / len(opportunities)
    
    def get_batch_by_id(self, batch_id: int) -> Optional[ApplicationBatch]:
        """배치 ID로 배치 조회"""
        for batch in self.batches:
            if batch.batch_id == batch_id:
                return batch
        return None
    
    def generate_batch_summary(self) -> str:
        """배치 요약 생성"""
        if not self.batches:
            return "No batches created yet."
            
        lines = []
        lines.append(f"📦 RFS Adoption Batches ({len(self.opportunities)} opportunities → {len(self.batches)} batches)")
        lines.append("")
        
        for batch in self.batches[:5]:  # 상위 5개 배치만 표시
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[batch.priority]
            complexity_emoji = {"complex": "🔴", "medium": "🟡", "easy": "🟢"}[batch.complexity]
            
            lines.append(f"Batch #{batch.batch_id} ({priority_emoji} {batch.priority.upper()}, "
                        f"{complexity_emoji} {batch.complexity}, "
                        f"Est. {batch.estimated_time:.1f}h)")
            lines.append("─" * 60)
            
            for i, opp in enumerate(batch.opportunities[:3], 1):  # 상위 3개만 표시
                lines.append(f"{i}. {opp.file_path}:{opp.line_number}")
                lines.append(f"   ➜ {opp.description} ({opp.severity.upper()})")
                
            if len(batch.opportunities) > 3:
                lines.append(f"   ... and {len(batch.opportunities) - 3} more items")
                
            lines.append("")
            
        if len(self.batches) > 5:
            lines.append(f"... and {len(self.batches) - 5} more batches")
            lines.append("")
            
        lines.append("💡 Run with --apply-batch [N] to apply a specific batch")
        lines.append("💡 Run with --show-batches to see all batches")
        
        return "\n".join(lines)


class RFSAdoptionChecker:
    """RFS 프레임워크 적용 검사기"""
    
    # RFS 데코레이터 목록
    RFS_DECORATORS = {
        'service_method': 'Service method marking and metrics',
        'transactional': 'Transaction management',
        'cache_result': 'Result caching',
        'log_execution': 'Execution logging',
        'measure_performance': 'Performance measurement',
        'retry': 'Automatic retry on failure',
        'validate_args': 'Argument validation'
    }
    
    # 에러 처리 패턴
    ERROR_PATTERNS = {
        'try_except': 'Could use Railway Pattern',
        'raise_exception': 'Could return Result type',
        'none_check': 'Could use Option/Maybe pattern'
    }
    
    def __init__(self, target_dir: str = "app/services/v2"):
        self.target_dir = Path(target_dir)
        self.results: List[FileAnalysisResult] = []
        self.statistics = defaultdict(int)
        
    def analyze(self) -> None:
        """V2 디렉토리 분석"""
        print(f"🔍 Analyzing RFS adoption in {self.target_dir}...")
        
        py_files = list(self.target_dir.rglob("*.py"))
        for py_file in py_files:
            if self._should_skip_file(py_file):
                continue
                
            result = self._analyze_file(py_file)
            if result.opportunities:
                self.results.append(result)
                
        self._calculate_statistics()
        
    def _should_skip_file(self, file_path: Path) -> bool:
        """스킵할 파일 확인"""
        skip_patterns = [
            '__pycache__',
            'test_',
            '_test.py',
            'mock',
            '__init__.py',
            'config/',
            'di/',  # DI 관련 파일은 이미 프레임워크 적용됨
        ]
        
        str_path = str(file_path)
        return any(pattern in str_path for pattern in skip_patterns)
        
    def _analyze_file(self, file_path: Path) -> FileAnalysisResult:
        """파일 분석"""
        # 상대 경로로 변환
        try:
            rel_path = file_path.relative_to(Path.cwd())
            result = FileAnalysisResult(file_path=str(rel_path))
        except ValueError:
            result = FileAnalysisResult(file_path=str(file_path))
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
                tree = ast.parse(source)
                
            # 각 검사 수행
            self._check_stateless_service(tree, source, result)
            self._check_decorator_opportunities(tree, source, result)
            self._check_error_handling(tree, source, result)
            self._check_manual_caching(tree, source, result)
            self._check_manual_retry(tree, source, result)
            self._check_manual_validation(tree, source, result)
            self._check_logging_opportunities(tree, source, result)
            self._check_performance_monitoring(tree, source, result)
            
            result.calculate_score()
            
        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")
            
        return result
        
    def _check_stateless_service(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """StatelessService 상속 기회 검사"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Service, Manager, Processor 등의 이름을 가진 클래스
                if any(pattern in node.name for pattern in ['Service', 'Manager', 'Processor', 'Handler']):
                    # StatelessService를 상속하지 않는 경우
                    if not self._inherits_stateless_service(node):
                        result.opportunities.append(RFSOpportunity(
                            file_path=result.file_path,
                            line_number=node.lineno,
                            opportunity_type='stateless_service',
                            description=f"Class '{node.name}' could extend StatelessService",
                            suggestion=f"Make '{node.name}' extend StatelessService for automatic service management",
                            severity='high'
                        ))
                        
    def _inherits_stateless_service(self, node: ast.ClassDef) -> bool:
        """StatelessService 상속 여부 확인"""
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == 'StatelessService':
                return True
            elif isinstance(base, ast.Attribute) and base.attr == 'StatelessService':
                return True
        return False
        
    def _check_decorator_opportunities(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """데코레이터 사용 기회 검사"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 공개 메서드인 경우
                if not node.name.startswith('_'):
                    decorators = [d.id if isinstance(d, ast.Name) else 
                                 (d.attr if isinstance(d, ast.Attribute) else None) 
                                 for d in node.decorator_list]
                    
                    # service_method 데코레이터 미사용
                    if 'service_method' not in decorators:
                        # 클래스 메서드이고 서비스 관련 메서드인 경우
                        if self._is_service_method(node):
                            result.opportunities.append(RFSOpportunity(
                                file_path=result.file_path,
                                line_number=node.lineno,
                                opportunity_type='service_method_decorator',
                                description=f"Method '{node.name}' could use @service_method decorator",
                                suggestion="Add @service_method for automatic metrics and error handling",
                                severity='medium'
                            ))
                            
    def _is_service_method(self, node: ast.FunctionDef) -> bool:
        """서비스 메서드인지 확인"""
        # self 파라미터가 있는 인스턴스 메서드
        if node.args.args and node.args.args[0].arg == 'self':
            # 일반적인 서비스 메서드 패턴
            service_patterns = [
                'process', 'handle', 'execute', 'perform',
                'analyze', 'enhance', 'translate', 'extract',
                'validate', 'transform', 'convert', 'generate'
            ]
            return any(pattern in node.name.lower() for pattern in service_patterns)
        return False
        
    def _check_error_handling(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """에러 처리 패턴 검사"""
        for node in ast.walk(tree):
            # try-except 블록
            if isinstance(node, ast.Try):
                # Railway Pattern 대신 사용 가능
                result.opportunities.append(RFSOpportunity(
                    file_path=result.file_path,
                    line_number=node.lineno,
                    opportunity_type='railway_pattern',
                    description="Try-except block could use Railway Pattern",
                    suggestion="Consider using Result[T, E] type with success/failure for functional error handling",
                    severity='low'
                ))
                
            # raise 문
            elif isinstance(node, ast.Raise):
                result.opportunities.append(RFSOpportunity(
                    file_path=result.file_path,
                    line_number=node.lineno,
                    opportunity_type='result_type',
                    description="Exception raising could use Result type",
                    suggestion="Return failure(error) instead of raising exceptions",
                    severity='low'
                ))
                
    def _check_manual_caching(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """수동 캐싱 패턴 검사"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 함수 내에서 캐시 관련 코드 찾기
                for inner_node in ast.walk(node):
                    if isinstance(inner_node, ast.Name):
                        if 'cache' in inner_node.id.lower():
                            # @cache_result 데코레이터 사용 가능
                            decorators = [d.id if isinstance(d, ast.Name) else 
                                        (d.attr if isinstance(d, ast.Attribute) else None) 
                                        for d in node.decorator_list]
                            
                            if 'cache_result' not in decorators:
                                result.opportunities.append(RFSOpportunity(
                                    file_path=result.file_path,
                                    line_number=node.lineno,
                                    opportunity_type='cache_decorator',
                                    description=f"Method '{node.name}' has manual caching",
                                    suggestion="Use @cache_result decorator for automatic caching",
                                    severity='medium'
                                ))
                                break
                                
    def _check_manual_retry(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """수동 재시도 패턴 검사"""
        for node in ast.walk(tree):
            if isinstance(node, ast.For) or isinstance(node, ast.While):
                # 재시도 패턴 찾기
                for inner_node in ast.walk(node):
                    if isinstance(inner_node, ast.Name):
                        if any(word in inner_node.id.lower() for word in ['retry', 'attempt', 'tries']):
                            result.opportunities.append(RFSOpportunity(
                                file_path=result.file_path,
                                line_number=node.lineno,
                                opportunity_type='retry_decorator',
                                description="Manual retry logic detected",
                                suggestion="Use @retry decorator for automatic retry handling",
                                severity='medium'
                            ))
                            break
                            
    def _check_manual_validation(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """수동 유효성 검증 패턴 검사"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 함수 시작 부분에서 유효성 검증 코드 찾기
                validation_found = False
                for i, stmt in enumerate(node.body[:5]):  # 처음 5개 문장만 확인
                    if isinstance(stmt, ast.If):
                        # 파라미터 검증 패턴
                        for inner_node in ast.walk(stmt):
                            if isinstance(inner_node, ast.Compare):
                                validation_found = True
                                break
                                
                if validation_found:
                    decorators = [d.id if isinstance(d, ast.Name) else 
                                (d.attr if isinstance(d, ast.Attribute) else None) 
                                for d in node.decorator_list]
                    
                    if 'validate_args' not in decorators:
                        result.opportunities.append(RFSOpportunity(
                            file_path=result.file_path,
                            line_number=node.lineno,
                            opportunity_type='validation_decorator',
                            description=f"Method '{node.name}' has manual validation",
                            suggestion="Use @validate_args decorator for argument validation",
                            severity='low'
                        ))
                        
    def _check_logging_opportunities(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """로깅 기회 검사"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 로깅 코드 찾기
                has_logging = False
                for inner_node in ast.walk(node):
                    if isinstance(inner_node, ast.Attribute):
                        if inner_node.attr in ['info', 'debug', 'warning', 'error']:
                            has_logging = True
                            break
                            
                if has_logging:
                    decorators = [d.id if isinstance(d, ast.Name) else 
                                (d.attr if isinstance(d, ast.Attribute) else None) 
                                for d in node.decorator_list]
                    
                    if 'log_execution' not in decorators:
                        result.opportunities.append(RFSOpportunity(
                            file_path=result.file_path,
                            line_number=node.lineno,
                            opportunity_type='logging_decorator',
                            description=f"Method '{node.name}' has manual logging",
                            suggestion="Use @log_execution decorator for automatic logging",
                            severity='low'
                        ))
                        
    def _check_performance_monitoring(self, tree: ast.AST, source: str, result: FileAnalysisResult) -> None:
        """성능 모니터링 기회 검사"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # time 관련 코드 찾기
                has_timing = False
                for inner_node in ast.walk(node):
                    if isinstance(inner_node, ast.Name):
                        if 'time' in inner_node.id.lower():
                            has_timing = True
                            break
                            
                if has_timing:
                    decorators = [d.id if isinstance(d, ast.Name) else 
                                (d.attr if isinstance(d, ast.Attribute) else None) 
                                for d in node.decorator_list]
                    
                    if 'measure_performance' not in decorators:
                        result.opportunities.append(RFSOpportunity(
                            file_path=result.file_path,
                            line_number=node.lineno,
                            opportunity_type='performance_decorator',
                            description=f"Method '{node.name}' has manual performance monitoring",
                            suggestion="Use @measure_performance decorator for automatic metrics",
                            severity='medium'
                        ))
                        
    def _calculate_statistics(self) -> None:
        """통계 계산"""
        for result in self.results:
            for opp in result.opportunities:
                self.statistics[opp.opportunity_type] += 1
                self.statistics[f"severity_{opp.severity}"] += 1
                
        self.statistics['total_files'] = len(self.results)
        self.statistics['total_opportunities'] = sum(
            len(r.opportunities) for r in self.results
        )
        
        # 평균 점수 계산
        if self.results:
            self.statistics['average_score'] = sum(
                r.rfs_score for r in self.results
            ) / len(self.results)
        else:
            self.statistics['average_score'] = 100.0
    
    def _get_all_opportunities(self) -> List[RFSOpportunity]:
        """모든 기회 목록 반환"""
        all_opportunities = []
        for result in self.results:
            all_opportunities.extend(result.opportunities)
        return all_opportunities
            
    def generate_report(self, format: str = 'text', dashboard: bool = False, 
                       show_batches: bool = False) -> str:
        """보고서 생성"""
        if dashboard:
            return self._generate_dashboard_report()
        elif show_batches:
            return self._generate_batch_report()
        elif format == 'json':
            return self._generate_json_report()
        elif format == 'markdown':
            return self._generate_markdown_report()
        else:
            return self._generate_text_report()
    
    def _generate_dashboard_report(self) -> str:
        """대시보드 스타일 보고서 생성"""
        # 종합 메트릭 계산
        calculator = RFSScoreCalculator(self.results, self.statistics)
        metrics = calculator.calculate_comprehensive_score()
        
        lines = []
        lines.append("═" * 80)
        lines.append("            RFS Framework Adoption Dashboard")
        lines.append("═" * 80)
        lines.append("")
        
        # 전체 건강도 점수
        trend_emoji = {
            "improving": "📈",
            "declining": "📉", 
            "stable": "📊",
            "unknown": "❓"
        }[metrics.trend_direction]
        
        lines.append(f"🏆 Overall Health Score: {metrics.overall_score:.1f}/100 (Grade: {metrics.grade})")
        if metrics.trend_direction != "unknown":
            lines.append(f"{trend_emoji} Improvement Trend: {metrics.trend_direction.title()}")
            if metrics.trend_percentage > 0:
                sign = "+" if metrics.trend_direction == "improving" else "-"
                lines.append(f"   {sign}{metrics.trend_percentage:.1f}% from last run")
        lines.append("")
        
        # 카테고리별 진행률 바
        lines.append("Category Scores:")
        lines.append("┌─────────────────────────────────────────────────────────┐")
        
        category_names = {
            'stateless_service': 'StatelessService',
            'service_method_decorator': 'Service Methods',
            'cache_decorator': 'Caching',
            'performance_decorator': 'Performance',
            'validation_decorator': 'Validation',
            'logging_decorator': 'Logging',
            'retry_decorator': 'Retry Logic',
            'railway_pattern': 'Error Handling',
            'result_type': 'Result Types'
        }
        
        for score in metrics.category_scores:
            name = category_names.get(score.name, score.name)
            # 진행률 바 생성 (10단계)
            progress = int((score.percentage / 100) * 10)
            bar = "█" * progress + "░" * (10 - progress)
            
            # 현재/총 계산 (기회가 적을수록 좋음)
            completed = score.total - score.current
            
            lines.append(f"│ {name:<16} [{bar}] {score.percentage:.0f}% "
                        f"({completed}/{score.total}){'':>8}│")
        
        lines.append("└─────────────────────────────────────────────────────────┘")
        lines.append("")
        
        # 성숙도 및 예상 시간
        maturity_stars = "★" * metrics.maturity_level + "☆" * (5 - metrics.maturity_level)
        lines.append(f"📊 Maturity Level: {metrics.maturity_level}/5 ({maturity_stars})")
        lines.append(f"⏱️ Estimated Full Adoption: {metrics.estimated_hours:.0f} hours "
                    f"({metrics.total_batches} batches × {metrics.estimated_hours/metrics.total_batches:.1f}h/batch)")
        lines.append("")
        
        # 우선순위 권장사항
        lines.append("🎯 Priority Recommendations:")
        lines.append("-" * 40)
        
        high_priority = [result for result in self.results 
                        for opp in result.opportunities if opp.severity == 'high']
        
        if high_priority:
            lines.append(f"🔴 HIGH: {len(high_priority)} critical improvements needed")
            lines.append("   Focus on StatelessService extensions first")
        
        medium_priority = self.statistics.get('severity_medium', 0)
        if medium_priority > 0:
            lines.append(f"🟡 MEDIUM: {medium_priority} performance optimizations available")
            lines.append("   Consider caching and performance decorators")
            
        low_priority = self.statistics.get('severity_low', 0)
        if low_priority > 0:
            lines.append(f"🟢 LOW: {low_priority} code quality improvements possible")
            lines.append("   Railway Pattern and Result types when time permits")
        
        lines.append("")
        lines.append("💡 Run with --show-batches to see implementation plan")
        lines.append("💡 Run with --apply-batch 1 to start with highest priority items")
        lines.append("═" * 80)
        
        return "\n".join(lines)
    
    def _generate_batch_report(self) -> str:
        """배치 보고서 생성"""
        all_opportunities = self._get_all_opportunities()
        
        if not all_opportunities:
            return "No opportunities found to create batches."
        
        batch_applicator = BatchApplicator(all_opportunities, batch_size=10)
        batches = batch_applicator.create_batches()
        
        return batch_applicator.generate_batch_summary()
            
    def _generate_text_report(self) -> str:
        """텍스트 보고서 생성"""
        lines = []
        lines.append("=" * 80)
        lines.append("RFS Framework Adoption Report")
        lines.append("=" * 80)
        lines.append("")
        
        # 요약
        lines.append("📊 Summary")
        lines.append("-" * 40)
        lines.append(f"Total files analyzed: {self.statistics['total_files']}")
        lines.append(f"Total opportunities: {self.statistics['total_opportunities']}")
        lines.append(f"Average RFS score: {self.statistics['average_score']:.1f}/100")
        lines.append("")
        
        # 심각도별 분포
        lines.append("🎯 Severity Distribution")
        lines.append("-" * 40)
        for severity in ['high', 'medium', 'low']:
            count = self.statistics.get(f'severity_{severity}', 0)
            lines.append(f"  {severity.upper()}: {count}")
        lines.append("")
        
        # 기회 유형별 분포
        lines.append("📈 Opportunity Types")
        lines.append("-" * 40)
        opportunity_types = [
            ('stateless_service', 'StatelessService Extension'),
            ('service_method_decorator', '@service_method Decorator'),
            ('cache_decorator', '@cache_result Decorator'),
            ('retry_decorator', '@retry Decorator'),
            ('validation_decorator', '@validate_args Decorator'),
            ('logging_decorator', '@log_execution Decorator'),
            ('performance_decorator', '@measure_performance Decorator'),
            ('railway_pattern', 'Railway Pattern'),
            ('result_type', 'Result Type Usage')
        ]
        
        for opp_type, description in opportunity_types:
            count = self.statistics.get(opp_type, 0)
            if count > 0:
                lines.append(f"  {description}: {count}")
        lines.append("")
        
        # 파일별 상세
        if self.results:
            lines.append("📁 File Details")
            lines.append("-" * 40)
            
            # 점수가 낮은 순으로 정렬
            sorted_results = sorted(self.results, key=lambda r: r.rfs_score)
            
            for result in sorted_results[:10]:  # 상위 10개만
                try:
                    rel_path = Path(result.file_path).relative_to(Path.cwd())
                except ValueError:
                    rel_path = result.file_path
                lines.append(f"\n  {rel_path} (Score: {result.rfs_score:.0f}/100)")
                
                # 심각도별로 그룹화
                high_opps = [o for o in result.opportunities if o.severity == 'high']
                medium_opps = [o for o in result.opportunities if o.severity == 'medium']
                low_opps = [o for o in result.opportunities if o.severity == 'low']
                
                if high_opps:
                    lines.append("    🔴 High Priority:")
                    for opp in high_opps[:3]:
                        lines.append(f"      L{opp.line_number}: {opp.description}")
                        
                if medium_opps:
                    lines.append("    🟡 Medium Priority:")
                    for opp in medium_opps[:3]:
                        lines.append(f"      L{opp.line_number}: {opp.description}")
                        
                if low_opps and len(high_opps) + len(medium_opps) < 5:
                    lines.append("    🟢 Low Priority:")
                    for opp in low_opps[:2]:
                        lines.append(f"      L{opp.line_number}: {opp.description}")
                        
            if len(self.results) > 10:
                lines.append(f"\n  ... and {len(self.results) - 10} more files")
                
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
        
    def _generate_json_report(self) -> str:
        """JSON 보고서 생성"""
        report = {
            'summary': {
                'total_files': self.statistics['total_files'],
                'total_opportunities': self.statistics['total_opportunities'],
                'average_score': self.statistics['average_score']
            },
            'statistics': dict(self.statistics),
            'files': []
        }
        
        for result in self.results:
            file_info = {
                'path': result.file_path,
                'score': result.rfs_score,
                'opportunities': [opp.to_dict() for opp in result.opportunities]
            }
            report['files'].append(file_info)
            
        return json.dumps(report, indent=2, ensure_ascii=False)
        
    def _generate_markdown_report(self) -> str:
        """Markdown 보고서 생성"""
        lines = []
        lines.append("# RFS Framework Adoption Report")
        lines.append("")
        
        lines.append("## 📊 Summary")
        lines.append("")
        lines.append(f"- **Files Analyzed**: {self.statistics['total_files']}")
        lines.append(f"- **Total Opportunities**: {self.statistics['total_opportunities']}")
        lines.append(f"- **Average Score**: {self.statistics['average_score']:.1f}/100")
        lines.append("")
        
        lines.append("## 🎯 Recommendations")
        lines.append("")
        
        # 높은 우선순위 추천
        high_priority = []
        for result in self.results:
            for opp in result.opportunities:
                if opp.severity == 'high':
                    high_priority.append((result, opp))
                    
        if high_priority:
            lines.append("### High Priority")
            lines.append("")
            for result, opp in high_priority[:5]:
                try:
                    rel_path = Path(result.file_path).relative_to(Path.cwd())
                except ValueError:
                    rel_path = result.file_path
                lines.append(f"- **{rel_path}:{opp.line_number}**")
                lines.append(f"  - Issue: {opp.description}")
                lines.append(f"  - Solution: {opp.suggestion}")
                lines.append("")
                
        return "\n".join(lines)
        
    def apply_fixes(self, auto_fix: bool = False) -> None:
        """자동 수정 적용 (향후 구현)"""
        if not auto_fix:
            print("Auto-fix is not implemented yet. Please apply suggestions manually.")
            return
            
        # TODO: 자동 수정 구현
        # - StatelessService 상속 추가
        # - 데코레이터 자동 추가
        # - import 문 추가
        pass


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='Check RFS framework adoption in V2 codebase'
    )
    parser.add_argument(
        '--target-dir',
        default='app/services/v2',
        help='Target directory to analyze'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'markdown'],
        default='text',
        help='Output format'
    )
    parser.add_argument(
        '--output',
        help='Output file (default: stdout)'
    )
    
    # 스코어링 및 대시보드 옵션
    parser.add_argument(
        '--dashboard',
        action='store_true',
        help='Show dashboard-style comprehensive scoring report'
    )
    parser.add_argument(
        '--baseline',
        action='store_true',
        help='Save current results as baseline for trend analysis'
    )
    
    # 배치 관리 옵션
    parser.add_argument(
        '--show-batches',
        action='store_true',
        help='Show batch application plan (10 items per batch)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of items per batch (default: 10)'
    )
    parser.add_argument(
        '--apply-batch',
        type=int,
        metavar='N',
        help='Apply specific batch number (not implemented yet)'
    )
    parser.add_argument(
        '--priority',
        choices=['high', 'medium', 'low'],
        help='Filter opportunities by priority level'
    )
    
    # 기존 옵션들
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Apply automatic fixes (not implemented yet)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # 검사 실행
    checker = RFSAdoptionChecker(args.target_dir)
    checker.analyze()
    
    # 우선순위 필터링
    if args.priority:
        filtered_results = []
        for result in checker.results:
            filtered_opportunities = [
                opp for opp in result.opportunities 
                if opp.severity == args.priority
            ]
            if filtered_opportunities:
                filtered_result = FileAnalysisResult(
                    file_path=result.file_path,
                    opportunities=filtered_opportunities,
                    rfs_score=result.rfs_score
                )
                filtered_results.append(filtered_result)
        checker.results = filtered_results
        checker._calculate_statistics()
    
    # 기준선 저장
    if args.baseline:
        calculator = RFSScoreCalculator(checker.results, checker.statistics)
        metrics = calculator.calculate_comprehensive_score()
        calculator.save_baseline(metrics)
        print(f"✅ Baseline saved for trend analysis")
    
    # 보고서 생성
    report = checker.generate_report(
        format=args.format,
        dashboard=args.dashboard,
        show_batches=args.show_batches
    )
    
    # 출력
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ Report saved to {args.output}")
    else:
        print(report)
    
    # 배치 적용 (향후 구현)
    if args.apply_batch:
        print(f"⚠️ Batch application not implemented yet. Would apply batch #{args.apply_batch}")
        print(f"💡 Use scripts/quality/rfs_apply_batch.py when available")
        
    # 자동 수정
    if args.fix:
        checker.apply_fixes(auto_fix=True)
        
    # 종료 코드
    if checker.statistics['total_opportunities'] > 0:
        if checker.statistics.get('severity_high', 0) > 0:
            sys.exit(2)  # High severity issues found
        else:
            sys.exit(1)  # Medium/Low severity issues found
    else:
        sys.exit(0)  # No issues found


if __name__ == '__main__':
    main()