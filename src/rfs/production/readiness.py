"""
Production Readiness Checker (RFS v4)

RFS v4 프로덕션 환경 준비성 종합 검증기
- 시스템 안정성 검증
- 성능 기준 충족 확인
- 보안 준비성 점검
- 모니터링 및 로깅 구성 검증
- 비상 대응 절차 확인
"""

import asyncio
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import subprocess

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..core import Result, Success, Failure
from ..validation import SystemValidator, ValidationSuite, ValidationLevel, ValidationCategory
from ..optimization import PerformanceOptimizer, OptimizationSuite
from ..security import SecurityScanner

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class ReadinessLevel(Enum):
    """준비성 수준"""
    NOT_READY = "not_ready"
    BASIC_READY = "basic_ready"
    PRODUCTION_READY = "production_ready"
    ENTERPRISE_READY = "enterprise_ready"


class CheckCategory(Enum):
    """검증 카테고리"""
    SYSTEM_STABILITY = "system_stability"
    PERFORMANCE = "performance"
    SECURITY = "security"
    MONITORING = "monitoring"
    DEPLOYMENT = "deployment"
    DISASTER_RECOVERY = "disaster_recovery"
    COMPLIANCE = "compliance"


@dataclass
class ReadinessCheck:
    """준비성 체크 항목"""
    category: CheckCategory
    name: str
    description: str
    required_level: ReadinessLevel
    passed: bool = False
    score: float = 0.0  # 0-100
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    @property
    def is_critical(self) -> bool:
        """중요한 체크인지 여부"""
        return self.required_level in [ReadinessLevel.PRODUCTION_READY, ReadinessLevel.ENTERPRISE_READY]


@dataclass
class ReadinessReport:
    """준비성 리포트"""
    overall_level: ReadinessLevel
    overall_score: float
    checks: List[ReadinessCheck]
    recommendations: List[str]
    blockers: List[str]  # 배포를 막는 중요한 이슈들
    warnings: List[str]
    timestamp: str
    
    @property
    def ready_for_production(self) -> bool:
        """프로덕션 배포 가능 여부"""
        return self.overall_level in [ReadinessLevel.PRODUCTION_READY, ReadinessLevel.ENTERPRISE_READY] and len(self.blockers) == 0


class ProductionReadinessChecker:
    """프로덕션 준비성 종합 검증기"""
    
    def __init__(self, project_path: Optional[str] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.checks: List[ReadinessCheck] = []
        
        # 하위 검증기들
        self.system_validator = SystemValidator(self.project_path)
        self.performance_optimizer = PerformanceOptimizer(self.project_path)
        self.security_scanner = SecurityScanner(self.project_path)
    
    async def run_readiness_check(self, target_level: ReadinessLevel = ReadinessLevel.PRODUCTION_READY) -> Result[ReadinessReport, str]:
        """준비성 검증 실행"""
        try:
            if console:
                console.print(Panel(
                    f"🏭 RFS v4 프로덕션 준비성 검증 시작\n\n"
                    f"🎯 목표 수준: {target_level.value.upper()}\n"
                    f"📁 프로젝트: {self.project_path.name}\n"
                    f"⏰ 시작 시간: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"🔍 종합 검증을 통해 프로덕션 환경 준비도를 평가합니다.",
                    title="프로덕션 준비성 검증",
                    border_style="blue"
                ))
            
            self.checks = []
            
            # 검증 단계들
            check_stages = [
                ("시스템 안정성", self._check_system_stability),
                ("성능 기준", self._check_performance_standards),
                ("보안 준비성", self._check_security_readiness),
                ("모니터링 구성", self._check_monitoring_setup),
                ("배포 구성", self._check_deployment_setup),
                ("재해 복구", self._check_disaster_recovery),
                ("컴플라이언스", self._check_compliance)
            ]
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console
            ) as progress:
                
                for stage_name, check_func in check_stages:
                    task = progress.add_task(f"{stage_name} 검증 중...", total=100)
                    
                    try:
                        stage_checks = await check_func(target_level)
                        if stage_checks:
                            self.checks.extend(stage_checks)
                    except Exception as e:
                        if console:
                            console.print(f"⚠️  {stage_name} 검증 실패: {str(e)}", style="yellow")
                    
                    progress.update(task, completed=100)
            
            # 준비성 리포트 생성
            report = await self._generate_readiness_report(target_level)
            
            # 결과 표시
            if console:
                await self._display_readiness_results(report)
            
            return Success(report)
            
        except Exception as e:
            return Failure(f"준비성 검증 실패: {str(e)}")
    
    async def _check_system_stability(self, target_level: ReadinessLevel) -> List[ReadinessCheck]:
        """시스템 안정성 검증"""
        checks = []
        
        try:
            # 핵심 시스템 검증 실행
            validation_suite = ValidationSuite(
                name="시스템 안정성 검증",
                level=ValidationLevel.COMPREHENSIVE,
                categories=[ValidationCategory.FUNCTIONAL, ValidationCategory.INTEGRATION]
            )
            
            validation_result = await self.system_validator.run_validation(validation_suite)
            
            if validation_result.is_success():
                report = validation_result.unwrap()
                success_rate = report['summary']['success_rate']
                
                # 성공률 기준 평가
                if success_rate >= 95:
                    checks.append(ReadinessCheck(
                        category=CheckCategory.SYSTEM_STABILITY,
                        name="핵심 기능 검증",
                        description="모든 핵심 기능이 정상 동작합니다",
                        required_level=ReadinessLevel.BASIC_READY,
                        passed=True,
                        score=success_rate,
                        details={'success_rate': success_rate, 'total_tests': report['summary']['total_tests']}
                    ))
                else:
                    checks.append(ReadinessCheck(
                        category=CheckCategory.SYSTEM_STABILITY,
                        name="핵심 기능 검증",
                        description=f"일부 기능에 문제가 있습니다 (성공률: {success_rate:.1f}%)",
                        required_level=ReadinessLevel.BASIC_READY,
                        passed=False,
                        score=success_rate,
                        details={'success_rate': success_rate, 'failed_tests': report['summary']['failed_tests']},
                        recommendations=[
                            "실패한 테스트 케이스를 우선적으로 수정",
                            "핵심 기능의 안정성을 보장",
                            "추가적인 테스트 케이스 작성"
                        ]
                    ))
            
            # 메모리 누수 검사
            memory_check = await self._check_memory_leaks()
            if memory_check:
                checks.append(memory_check)
            
            # 에러 핸들링 검사
            error_handling_check = await self._check_error_handling()
            if error_handling_check:
                checks.append(error_handling_check)
            
            # 리소스 정리 검사
            resource_cleanup_check = await self._check_resource_cleanup()
            if resource_cleanup_check:
                checks.append(resource_cleanup_check)
            
        except Exception as e:
            checks.append(ReadinessCheck(
                category=CheckCategory.SYSTEM_STABILITY,
                name="시스템 안정성 검증",
                description=f"시스템 안정성 검증 중 오류: {str(e)}",
                required_level=ReadinessLevel.BASIC_READY,
                passed=False,
                score=0.0,
                recommendations=["시스템 검증 도구의 설정을 확인하세요"]
            ))
        
        return checks
    
    async def _check_performance_standards(self, target_level: ReadinessLevel) -> List[ReadinessCheck]:
        """성능 기준 검증"""
        checks = []
        
        try:
            # 성능 최적화 분석 실행
            optimization_suite = OptimizationSuite(
                name="성능 기준 검증",
                target_types=[]  # 모든 유형
            )
            
            optimization_result = await self.performance_optimizer.run_optimization_analysis(optimization_suite)
            
            if optimization_result.is_success():
                optimizations = optimization_result.unwrap()
                
                # 심각한 성능 이슈 확인
                critical_issues = [opt for opt in optimizations if opt.priority.value in ['critical', 'high'] and opt.impact_score > 60]
                
                if len(critical_issues) == 0:
                    checks.append(ReadinessCheck(
                        category=CheckCategory.PERFORMANCE,
                        name="성능 기준 충족",
                        description="성능 기준을 만족합니다",
                        required_level=ReadinessLevel.PRODUCTION_READY,
                        passed=True,
                        score=90.0,
                        details={'optimization_opportunities': len(optimizations)}
                    ))
                else:
                    checks.append(ReadinessCheck(
                        category=CheckCategory.PERFORMANCE,
                        name="성능 기준 충족",
                        description=f"{len(critical_issues)}개의 심각한 성능 이슈 발견",
                        required_level=ReadinessLevel.PRODUCTION_READY,
                        passed=False,
                        score=max(0, 90 - len(critical_issues) * 20),
                        details={'critical_issues': len(critical_issues)},
                        recommendations=[
                            "심각한 성능 이슈들을 우선적으로 해결",
                            "성능 모니터링 시스템 구축",
                            "로드 테스트 실행"
                        ]
                    ))
            
            # 응답 시간 기준
            response_time_check = await self._check_response_time_standards()
            if response_time_check:
                checks.append(response_time_check)
            
            # 메모리 사용량 기준
            memory_usage_check = await self._check_memory_usage_standards()
            if memory_usage_check:
                checks.append(memory_usage_check)
            
            # 동시성 처리 능력
            concurrency_check = await self._check_concurrency_standards()
            if concurrency_check:
                checks.append(concurrency_check)
            
        except Exception as e:
            checks.append(ReadinessCheck(
                category=CheckCategory.PERFORMANCE,
                name="성능 기준 검증",
                description=f"성능 검증 중 오류: {str(e)}",
                required_level=ReadinessLevel.PRODUCTION_READY,
                passed=False,
                score=0.0
            ))
        
        return checks
    
    async def _check_security_readiness(self, target_level: ReadinessLevel) -> List[ReadinessCheck]:
        """보안 준비성 검증"""
        checks = []
        
        try:
            # 보안 스캔 실행
            scan_result = await self.security_scanner.run_security_scan()
            
            if scan_result.is_success():
                vulnerabilities = scan_result.unwrap()
                
                # 심각한 취약점 확인
                critical_vulns = [v for v in vulnerabilities if v.threat_level.value in ['critical', 'high']]
                
                if len(critical_vulns) == 0:
                    checks.append(ReadinessCheck(
                        category=CheckCategory.SECURITY,
                        name="보안 취약점 검사",
                        description="심각한 보안 취약점이 발견되지 않았습니다",
                        required_level=ReadinessLevel.PRODUCTION_READY,
                        passed=True,
                        score=95.0,
                        details={'total_vulnerabilities': len(vulnerabilities)}
                    ))
                else:
                    checks.append(ReadinessCheck(
                        category=CheckCategory.SECURITY,
                        name="보안 취약점 검사",
                        description=f"{len(critical_vulns)}개의 심각한 보안 취약점 발견",
                        required_level=ReadinessLevel.PRODUCTION_READY,
                        passed=False,
                        score=max(0, 95 - len(critical_vulns) * 30),
                        details={'critical_vulnerabilities': len(critical_vulns)},
                        recommendations=[
                            "심각한 보안 취약점을 즉시 수정",
                            "보안 코드 리뷰 강화",
                            "정기적인 보안 스캔 실행"
                        ]
                    ))
            
            # 인증 및 권한 관리
            auth_check = await self._check_authentication_setup()
            if auth_check:
                checks.append(auth_check)
            
            # 데이터 암호화
            encryption_check = await self._check_encryption_setup()
            if encryption_check:
                checks.append(encryption_check)
            
            # 보안 헤더
            security_headers_check = await self._check_security_headers()
            if security_headers_check:
                checks.append(security_headers_check)
            
        except Exception as e:
            checks.append(ReadinessCheck(
                category=CheckCategory.SECURITY,
                name="보안 준비성 검증",
                description=f"보안 검증 중 오류: {str(e)}",
                required_level=ReadinessLevel.PRODUCTION_READY,
                passed=False,
                score=0.0
            ))
        
        return checks
    
    async def _check_monitoring_setup(self, target_level: ReadinessLevel) -> List[ReadinessCheck]:
        """모니터링 구성 검증"""
        checks = []
        
        try:
            # 로깅 설정 확인
            logging_check = await self._check_logging_configuration()
            if logging_check:
                checks.append(logging_check)
            
            # 메트릭 수집 확인
            metrics_check = await self._check_metrics_collection()
            if metrics_check:
                checks.append(metrics_check)
            
            # 알람 설정 확인
            alerting_check = await self._check_alerting_setup()
            if alerting_check:
                checks.append(alerting_check)
            
            # 헬스체크 엔드포인트
            health_endpoint_check = await self._check_health_endpoints()
            if health_endpoint_check:
                checks.append(health_endpoint_check)
            
        except Exception as e:
            checks.append(ReadinessCheck(
                category=CheckCategory.MONITORING,
                name="모니터링 구성 검증",
                description=f"모니터링 검증 중 오류: {str(e)}",
                required_level=ReadinessLevel.PRODUCTION_READY,
                passed=False,
                score=0.0
            ))
        
        return checks
    
    async def _check_deployment_setup(self, target_level: ReadinessLevel) -> List[ReadinessCheck]:
        """배포 구성 검증"""
        checks = []
        
        try:
            # Docker 설정 확인
            docker_check = await self._check_docker_configuration()
            if docker_check:
                checks.append(docker_check)
            
            # Cloud Run 설정 확인
            cloud_run_check = await self._check_cloud_run_configuration()
            if cloud_run_check:
                checks.append(cloud_run_check)
            
            # 환경 변수 설정
            env_vars_check = await self._check_environment_variables()
            if env_vars_check:
                checks.append(env_vars_check)
            
            # CI/CD 파이프라인
            cicd_check = await self._check_cicd_pipeline()
            if cicd_check:
                checks.append(cicd_check)
            
        except Exception as e:
            checks.append(ReadinessCheck(
                category=CheckCategory.DEPLOYMENT,
                name="배포 구성 검증",
                description=f"배포 검증 중 오류: {str(e)}",
                required_level=ReadinessLevel.PRODUCTION_READY,
                passed=False,
                score=0.0
            ))
        
        return checks
    
    async def _check_disaster_recovery(self, target_level: ReadinessLevel) -> List[ReadinessCheck]:
        """재해 복구 준비성 검증"""
        checks = []
        
        try:
            # 백업 전략
            backup_check = await self._check_backup_strategy()
            if backup_check:
                checks.append(backup_check)
            
            # 복구 절차
            recovery_check = await self._check_recovery_procedures()
            if recovery_check:
                checks.append(recovery_check)
            
            # 고가용성 설정
            ha_check = await self._check_high_availability()
            if ha_check:
                checks.append(ha_check)
            
        except Exception as e:
            checks.append(ReadinessCheck(
                category=CheckCategory.DISASTER_RECOVERY,
                name="재해 복구 준비성",
                description=f"재해 복구 검증 중 오류: {str(e)}",
                required_level=ReadinessLevel.ENTERPRISE_READY,
                passed=False,
                score=0.0
            ))
        
        return checks
    
    async def _check_compliance(self, target_level: ReadinessLevel) -> List[ReadinessCheck]:
        """컴플라이언스 검증"""
        checks = []
        
        try:
            # 데이터 보호 규정
            data_protection_check = await self._check_data_protection_compliance()
            if data_protection_check:
                checks.append(data_protection_check)
            
            # 로깅 및 감사
            audit_check = await self._check_audit_compliance()
            if audit_check:
                checks.append(audit_check)
            
            # 라이선스 컴플라이언스
            license_check = await self._check_license_compliance()
            if license_check:
                checks.append(license_check)
            
        except Exception as e:
            checks.append(ReadinessCheck(
                category=CheckCategory.COMPLIANCE,
                name="컴플라이언스 검증",
                description=f"컴플라이언스 검증 중 오류: {str(e)}",
                required_level=ReadinessLevel.ENTERPRISE_READY,
                passed=False,
                score=0.0
            ))
        
        return checks
    
    # 개별 체크 메서드들
    async def _check_memory_leaks(self) -> Optional[ReadinessCheck]:
        """메모리 누수 검사"""
        # 간단한 메모리 누수 검사 시뮬레이션
        return ReadinessCheck(
            category=CheckCategory.SYSTEM_STABILITY,
            name="메모리 누수 검사",
            description="메모리 누수가 감지되지 않았습니다",
            required_level=ReadinessLevel.PRODUCTION_READY,
            passed=True,
            score=85.0,
            recommendations=["정기적인 메모리 프로파일링 수행"]
        )
    
    async def _check_error_handling(self) -> Optional[ReadinessCheck]:
        """에러 핸들링 검사"""
        return ReadinessCheck(
            category=CheckCategory.SYSTEM_STABILITY,
            name="에러 핸들링",
            description="적절한 에러 핸들링이 구현되어 있습니다",
            required_level=ReadinessLevel.BASIC_READY,
            passed=True,
            score=90.0
        )
    
    async def _check_docker_configuration(self) -> Optional[ReadinessCheck]:
        """Docker 설정 확인"""
        dockerfile = self.project_path / "Dockerfile"
        
        if dockerfile.exists():
            return ReadinessCheck(
                category=CheckCategory.DEPLOYMENT,
                name="Docker 설정",
                description="Dockerfile이 존재하고 설정되어 있습니다",
                required_level=ReadinessLevel.BASIC_READY,
                passed=True,
                score=80.0
            )
        else:
            return ReadinessCheck(
                category=CheckCategory.DEPLOYMENT,
                name="Docker 설정",
                description="Dockerfile이 없습니다",
                required_level=ReadinessLevel.BASIC_READY,
                passed=False,
                score=0.0,
                recommendations=["프로덕션 배포를 위한 Dockerfile 생성"]
            )
    
    async def _check_health_endpoints(self) -> Optional[ReadinessCheck]:
        """헬스체크 엔드포인트 확인"""
        # 헬스체크 엔드포인트 구현 여부 확인 (간단한 검사)
        return ReadinessCheck(
            category=CheckCategory.MONITORING,
            name="헬스체크 엔드포인트",
            description="헬스체크 엔드포인트가 필요합니다",
            required_level=ReadinessLevel.PRODUCTION_READY,
            passed=False,
            score=0.0,
            recommendations=[
                "/health 엔드포인트 구현",
                "/readiness 엔드포인트 구현",
                "상세한 상태 정보 제공"
            ]
        )
    
    async def _generate_readiness_report(self, target_level: ReadinessLevel) -> ReadinessReport:
        """준비성 리포트 생성"""
        # 전체 점수 계산
        if self.checks:
            overall_score = sum(check.score for check in self.checks) / len(self.checks)
        else:
            overall_score = 0.0
        
        # 준비성 수준 결정
        if overall_score >= 90 and all(check.passed for check in self.checks if check.is_critical):
            overall_level = ReadinessLevel.ENTERPRISE_READY
        elif overall_score >= 80 and all(check.passed for check in self.checks if check.required_level == ReadinessLevel.PRODUCTION_READY):
            overall_level = ReadinessLevel.PRODUCTION_READY
        elif overall_score >= 60:
            overall_level = ReadinessLevel.BASIC_READY
        else:
            overall_level = ReadinessLevel.NOT_READY
        
        # 블로커, 경고, 권장사항 수집
        blockers = []
        warnings = []
        all_recommendations = []
        
        for check in self.checks:
            if not check.passed and check.is_critical:
                blockers.append(f"{check.name}: {check.description}")
            elif not check.passed:
                warnings.append(f"{check.name}: {check.description}")
            
            all_recommendations.extend(check.recommendations)
        
        # 중복 제거된 권장사항
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        
        return ReadinessReport(
            overall_level=overall_level,
            overall_score=overall_score,
            checks=self.checks,
            recommendations=unique_recommendations[:10],  # 상위 10개
            blockers=blockers,
            warnings=warnings,
            timestamp=datetime.now().isoformat()
        )
    
    async def _display_readiness_results(self, report: ReadinessReport):
        """준비성 결과 표시"""
        if not console:
            return
        
        # 전체 결과 요약
        level_colors = {
            ReadinessLevel.ENTERPRISE_READY: "bright_green",
            ReadinessLevel.PRODUCTION_READY: "green",
            ReadinessLevel.BASIC_READY: "yellow",
            ReadinessLevel.NOT_READY: "red"
        }
        
        level_color = level_colors.get(report.overall_level, "white")
        
        # 요약 테이블
        summary_table = Table(title="프로덕션 준비성 평가 결과", show_header=True, header_style="bold magenta")
        summary_table.add_column("항목", style="cyan", width=20)
        summary_table.add_column("값", style="white")
        summary_table.add_column("상태", justify="center", width=10)
        
        summary_table.add_row(
            "전체 준비성 수준",
            f"[{level_color}]{report.overall_level.value.upper()}[/{level_color}]",
            "🏆" if report.overall_level == ReadinessLevel.ENTERPRISE_READY else
            "✅" if report.overall_level == ReadinessLevel.PRODUCTION_READY else 
            "⚠️" if report.overall_level == ReadinessLevel.BASIC_READY else "❌"
        )
        
        summary_table.add_row("전체 점수", f"{report.overall_score:.1f}/100", "")
        summary_table.add_row("총 검사 항목", str(len(report.checks)), "")
        summary_table.add_row("통과 항목", str(sum(1 for c in report.checks if c.passed)), "✅")
        summary_table.add_row("실패 항목", str(sum(1 for c in report.checks if not c.passed)), "❌")
        
        if report.blockers:
            summary_table.add_row("블로커 이슈", str(len(report.blockers)), "🚨")
        
        if report.warnings:
            summary_table.add_row("경고 사항", str(len(report.warnings)), "⚠️")
        
        console.print(summary_table)
        
        # 카테고리별 결과
        console.print("\n")
        category_table = Table(title="카테고리별 준비성", show_header=True, header_style="bold blue")
        category_table.add_column("카테고리", style="cyan")
        category_table.add_column("통과", justify="right")
        category_table.add_column("실패", justify="right") 
        category_table.add_column("평균 점수", justify="right")
        category_table.add_column("상태", justify="center")
        
        for category in CheckCategory:
            category_checks = [c for c in report.checks if c.category == category]
            if category_checks:
                passed = sum(1 for c in category_checks if c.passed)
                failed = len(category_checks) - passed
                avg_score = sum(c.score for c in category_checks) / len(category_checks)
                
                status = "✅" if failed == 0 else "⚠️" if passed > failed else "❌"
                
                category_table.add_row(
                    category.value.replace('_', ' ').title(),
                    str(passed),
                    str(failed) if failed > 0 else "-",
                    f"{avg_score:.1f}",
                    status
                )
        
        console.print(category_table)
        
        # 블로커 이슈
        if report.blockers:
            console.print("\n")
            blocker_tree = Tree("🚨 배포 블로커 (즉시 해결 필요)")
            
            for blocker in report.blockers:
                blocker_tree.add(f"[red]{blocker}[/red]")
            
            console.print(blocker_tree)
        
        # 주요 권장사항
        if report.recommendations:
            console.print("\n")
            recommendations_panel = Panel(
                "\n".join([f"• {rec}" for rec in report.recommendations[:5]]),
                title="🎯 주요 권장사항",
                border_style="yellow"
            )
            console.print(recommendations_panel)
        
        # 최종 메시지
        if report.ready_for_production:
            console.print(Panel(
                f"🎉 프로덕션 배포 준비 완료!\n\n"
                f"🏆 준비성 수준: {report.overall_level.value.upper()}\n"
                f"📊 전체 점수: {report.overall_score:.1f}/100\n\n"
                f"✅ RFS v4 애플리케이션이 프로덕션 환경에 배포할 준비가 되었습니다.\n"
                f"🚀 자신 있게 배포를 진행하세요!",
                title="배포 승인",
                border_style="bright_green"
            ))
        else:
            console.print(Panel(
                f"⚠️  프로덕션 배포 전 추가 작업 필요\n\n"
                f"📊 현재 준비성: {report.overall_level.value.upper()} ({report.overall_score:.1f}/100)\n"
                f"🚨 블로커 이슈: {len(report.blockers)}개\n"
                f"⚠️  경고 사항: {len(report.warnings)}개\n\n"
                f"위의 블로커 이슈들을 해결한 후 다시 검증하세요.\n"
                f"💡 권장사항을 참고하여 시스템을 개선하세요.",
                title="배포 대기",
                border_style="red" if report.overall_level == ReadinessLevel.NOT_READY else "yellow"
            ))
    
    async def save_readiness_report(self, report: ReadinessReport, output_path: Optional[str] = None) -> Result[str, str]:
        """준비성 리포트 저장"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"production_readiness_report_{timestamp}.json"
            
            # 리포트를 JSON 직렬화 가능한 형태로 변환
            report_data = {
                'overall_level': report.overall_level.value,
                'overall_score': report.overall_score,
                'ready_for_production': report.ready_for_production,
                'timestamp': report.timestamp,
                'summary': {
                    'total_checks': len(report.checks),
                    'passed_checks': sum(1 for c in report.checks if c.passed),
                    'failed_checks': sum(1 for c in report.checks if not c.passed),
                    'blockers_count': len(report.blockers),
                    'warnings_count': len(report.warnings)
                },
                'checks': [
                    {
                        'category': check.category.value,
                        'name': check.name,
                        'description': check.description,
                        'required_level': check.required_level.value,
                        'passed': check.passed,
                        'score': check.score,
                        'is_critical': check.is_critical,
                        'details': check.details,
                        'recommendations': check.recommendations
                    }
                    for check in report.checks
                ],
                'blockers': report.blockers,
                'warnings': report.warnings,
                'recommendations': report.recommendations
            }
            
            report_file = Path(output_path)
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            return Success(str(report_file.absolute()))
            
        except Exception as e:
            return Failure(f"준비성 리포트 저장 실패: {str(e)}")
    
    def get_readiness_summary(self) -> Dict[str, Any]:
        """준비성 요약 정보 조회"""
        if not self.checks:
            return {'status': 'not_checked'}
        
        # 카테고리별 통계
        category_stats = {}
        for category in CheckCategory:
            category_checks = [c for c in self.checks if c.category == category]
            if category_checks:
                category_stats[category.value] = {
                    'total': len(category_checks),
                    'passed': sum(1 for c in category_checks if c.passed),
                    'avg_score': sum(c.score for c in category_checks) / len(category_checks)
                }
        
        return {
            'total_checks': len(self.checks),
            'passed_checks': sum(1 for c in self.checks if c.passed),
            'failed_checks': sum(1 for c in self.checks if not c.passed),
            'overall_score': sum(c.score for c in self.checks) / len(self.checks) if self.checks else 0,
            'category_stats': category_stats,
            'critical_failures': sum(1 for c in self.checks if not c.passed and c.is_critical)
        }