"""
System Validator (RFS)

RFS 시스템 종합 검증기
- 전체 시스템 상태 점검
- 다차원 검증 실행
- 종합 리포트 생성
- 자동 수정 제안
"""

import asyncio
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ..core.config import get_config
from ..core.result import Failure, Result, Success

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class ValidationLevel(Enum):
    """검증 레벨"""

    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    CRITICAL = "critical"


class ValidationStatus(Enum):
    """검증 상태"""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"
    ERROR = "error"


class ValidationCategory(Enum):
    """검증 카테고리"""

    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"


@dataclass
class ValidationResult:
    """검증 결과"""

    category: ValidationCategory
    name: str
    status: ValidationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    severity = "info"

    @property
    def is_success(self) -> bool:
        """성공 여부"""
        return self.status in [ValidationStatus.PASS, ValidationStatus.SKIP]

    @property
    def is_critical(self) -> bool:
        """심각도 여부"""
        return self.severity == "critical" or self.status == ValidationStatus.FAIL


@dataclass
class ValidationSuite:
    """검증 스위트"""

    name: str
    description: str
    level: ValidationLevel = ValidationLevel.STANDARD
    categories: List[str] = field(default_factory=list)
    timeout = 300
    parallel = True
    continue_on_failure = True

    def should_run_category(self, category: ValidationCategory) -> bool:
        """카테고리 실행 여부"""
        return not self.categories or category in self.categories


class SystemValidator:
    """시스템 종합 검증기"""

    def __init__(self, project_path=None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.validation_results = []
        self.start_time = None
        self.end_time = None
        self._initialize_validators()

    def _initialize_validators(self):
        """검증기들 초기화"""
        try:
            from .compatibility import CompatibilityValidator
            from .functional import FunctionalValidator
            from .integration import IntegrationValidator
            from .performance import PerformanceValidator
            from .security import SecurityValidator

            self.functional_validator = FunctionalValidator(self.project_path)
            self.integration_validator = IntegrationValidator(self.project_path)
            self.performance_validator = PerformanceValidator(self.project_path)
            self.security_validator = SecurityValidator(self.project_path)
            self.compatibility_validator = CompatibilityValidator(self.project_path)
        except ImportError as e:
            if console:
                console.print(f"⚠️  일부 검증기 로드 실패: {str(e)}", style="yellow")

    async def run_validation(
        self, suite: ValidationSuite
    ) -> Result[Dict[str, Any], str]:
        """검증 스위트 실행"""
        try:
            self.start_time = datetime.now()
            self.validation_results = []
            if console:
                console.print(
                    Panel(
                        f"🔍 RFS v4 시스템 검증 시작\n\n📋 검증 스위트: {suite.name}\n🎯 검증 레벨: {suite.level.value}\n📁 프로젝트 경로: {self.project_path}\n⚡ 병렬 실행: {('예' if suite.parallel else '아니오')}\n🔄 실패시 계속: {('예' if suite.continue_on_failure else '아니오')}",
                        title="시스템 검증",
                        border_style="blue",
                    )
                )
            validation_tasks = []
            if suite.should_run_category(ValidationCategory.FUNCTIONAL):
                validation_tasks = validation_tasks + [
                    self._run_category_validation(
                        "기능 검증", self._run_functional_validation, suite
                    )
                ]
            if suite.should_run_category(ValidationCategory.INTEGRATION):
                validation_tasks = validation_tasks + [
                    self._run_category_validation(
                        "통합 검증", self._run_integration_validation, suite
                    )
                ]
            if suite.should_run_category(ValidationCategory.PERFORMANCE):
                validation_tasks = validation_tasks + [
                    self._run_category_validation(
                        "성능 검증", self._run_performance_validation, suite
                    )
                ]
            if suite.should_run_category(ValidationCategory.SECURITY):
                validation_tasks = validation_tasks + [
                    self._run_category_validation(
                        "보안 검증", self._run_security_validation, suite
                    )
                ]
            if suite.should_run_category(ValidationCategory.COMPATIBILITY):
                validation_tasks = validation_tasks + [
                    self._run_category_validation(
                        "호환성 검증", self._run_compatibility_validation, suite
                    )
                ]
            if suite.parallel:
                await asyncio.gather(*validation_tasks, return_exceptions=True)
            else:
                for task in validation_tasks:
                    await task
            self.end_time = datetime.now()
            validation_report = await self._generate_validation_report(suite)
            if console:
                await self._display_validation_results(validation_report)
            return Success(validation_report)
        except Exception as e:
            return Failure(f"시스템 검증 실패: {str(e)}")

    async def _run_category_validation(
        self, category_name: str, validation_func, suite: ValidationSuite
    ):
        """카테고리별 검증 실행"""
        try:
            if console:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"{category_name} 실행 중...", total=None)
                    start_time = time.time()
                    results = await validation_func(suite)
                    execution_time = time.time() - start_time
                    progress.remove_task(task)
                    if results:
                        for result in results:
                            result.execution_time = execution_time / len(results)
                        self.validation_results = self.validation_results + results
            else:
                results = await validation_func(suite)
                if results:
                    self.validation_results = self.validation_results + results
        except Exception as e:
            error_result = ValidationResult(
                category=ValidationCategory.FUNCTIONAL,
                name=category_name,
                status=ValidationStatus.ERROR,
                message=f"검증 실행 오류: {str(e)}",
                severity="error",
            )
            self.validation_results = self.validation_results + [error_result]

    async def _run_functional_validation(
        self, suite: ValidationSuite
    ) -> List[ValidationResult]:
        """기능 검증 실행"""
        results = []
        try:
            core_modules = [
                "rfs.core",
                "rfs.cloud_run",
                "rfs.reactive",
                "rfs.events",
                "rfs.cli",
            ]
            for module_name in core_modules:
                try:
                    __import__(module_name)
                    results = results + [
                        ValidationResult(
                            category=ValidationCategory.FUNCTIONAL,
                            name=f"모듈 임포트: {module_name}",
                            status=ValidationStatus.PASS,
                            message="모듈 임포트 성공",
                            severity="info",
                        )
                    ]
                except ImportError as e:
                    results = results + [
                        ValidationResult(
                            category=ValidationCategory.FUNCTIONAL,
                            name=f"모듈 임포트: {module_name}",
                            status=ValidationStatus.FAIL,
                            message=f"모듈 임포트 실패: {str(e)}",
                            severity="error",
                            recommendations=[
                                f"{module_name} 모듈의 의존성을 확인하세요"
                            ],
                        )
                    ]
            try:
                from ..core.result import Failure, Result, Success

                success_result = Success("test")
                failure_result = Failure("error")
                assert success_result.is_success()
                assert not failure_result.is_success()
                assert success_result.unwrap() == "test"
                assert failure_result.unwrap_err() == "error"
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.FUNCTIONAL,
                        name="Result 패턴 동작",
                        status=ValidationStatus.PASS,
                        message="Result 패턴이 정상적으로 동작합니다",
                        severity="info",
                    )
                ]
            except Exception as e:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.FUNCTIONAL,
                        name="Result 패턴 동작",
                        status=ValidationStatus.FAIL,
                        message=f"Result 패턴 검증 실패: {str(e)}",
                        severity="critical",
                        recommendations=["Result 패턴 구현을 재검토하세요"],
                    )
                ]
            try:
                config = get_config()
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.FUNCTIONAL,
                        name="설정 시스템",
                        status=ValidationStatus.PASS,
                        message="설정 시스템이 정상적으로 로드됩니다",
                        details={
                            "environment": getattr(config, "environment", "unknown")
                        },
                        severity="info",
                    )
                ]
            except Exception as e:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.FUNCTIONAL,
                        name="설정 시스템",
                        status=ValidationStatus.FAIL,
                        message=f"설정 시스템 검증 실패: {str(e)}",
                        severity="error",
                        recommendations=["RFS 설정 파일을 확인하세요"],
                    )
                ]
        except Exception as e:
            results = results + [
                ValidationResult(
                    category=ValidationCategory.FUNCTIONAL,
                    name="기능 검증",
                    status=ValidationStatus.ERROR,
                    message=f"기능 검증 중 오류: {str(e)}",
                    severity="error",
                )
            ]
        return results

    async def _run_integration_validation(
        self, suite: ValidationSuite
    ) -> List[ValidationResult]:
        """통합 검증 실행"""
        results = []
        try:
            try:
                from ..cli.core import RFSCli

                cli = RFSCli()
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.INTEGRATION,
                        name="CLI 시스템 통합",
                        status=ValidationStatus.PASS,
                        message="CLI 시스템이 정상적으로 통합되었습니다",
                        severity="info",
                    )
                ]
            except Exception as e:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.INTEGRATION,
                        name="CLI 시스템 통합",
                        status=ValidationStatus.FAIL,
                        message=f"CLI 통합 실패: {str(e)}",
                        severity="error",
                        recommendations=["CLI 모듈의 의존성을 확인하세요"],
                    )
                ]
            try:
                from ..cloud_run import get_cloud_run_status, is_cloud_run_environment

                is_cloud_run = is_cloud_run_environment()
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.INTEGRATION,
                        name="Cloud Run 모듈 통합",
                        status=ValidationStatus.PASS,
                        message="Cloud Run 모듈이 정상적으로 통합되었습니다",
                        details={"is_cloud_run_environment": is_cloud_run},
                        severity="info",
                    )
                ]
            except Exception as e:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.INTEGRATION,
                        name="Cloud Run 모듈 통합",
                        status=ValidationStatus.FAIL,
                        message=f"Cloud Run 통합 실패: {str(e)}",
                        severity="warning",
                        recommendations=["Cloud Run 모듈 설정을 확인하세요"],
                    )
                ]
        except Exception as e:
            results = results + [
                ValidationResult(
                    category=ValidationCategory.INTEGRATION,
                    name="통합 검증",
                    status=ValidationStatus.ERROR,
                    message=f"통합 검증 중 오류: {str(e)}",
                    severity="error",
                )
            ]
        return results

    async def _run_performance_validation(
        self, suite: ValidationSuite
    ) -> List[ValidationResult]:
        """성능 검증 실행"""
        results = []
        try:
            import time

            start_time = time.time()
            from .. import core

            import_time = time.time() - start_time
            if import_time < 0.5:
                status = ValidationStatus.PASS
                severity = "info"
                message = f"모듈 임포트 성능 양호: {import_time:.3f}초"
            elif import_time < 1.0:
                status = ValidationStatus.WARNING
                severity = "warning"
                message = f"모듈 임포트 성능 보통: {import_time:.3f}초"
            else:
                status = ValidationStatus.FAIL
                severity = "error"
                message = f"모듈 임포트 성능 불량: {import_time:.3f}초"
            results = results + [
                ValidationResult(
                    category=ValidationCategory.PERFORMANCE,
                    name="모듈 임포트 성능",
                    status=status,
                    message=message,
                    details={"import_time_seconds": import_time},
                    severity=severity,
                    recommendations=(
                        ["임포트 시간이 긴 모듈을 최적화하세요"]
                        if import_time > 0.5
                        else []
                    ),
                )
            ]
            try:
                import os

                import psutil

                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                if memory_mb < 50:
                    status = ValidationStatus.PASS
                    severity = "info"
                elif memory_mb < 100:
                    status = ValidationStatus.WARNING
                    severity = "warning"
                else:
                    status = ValidationStatus.FAIL
                    severity = "error"
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.PERFORMANCE,
                        name="메모리 사용량",
                        status=status,
                        message=f"현재 메모리 사용량: {memory_mb:.1f}MB",
                        details={"memory_mb": memory_mb},
                        severity=severity,
                    )
                ]
            except ImportError:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.PERFORMANCE,
                        name="메모리 사용량",
                        status=ValidationStatus.SKIP,
                        message="psutil 모듈이 없어 메모리 검사를 건너뜁니다",
                        severity="info",
                    )
                ]
        except Exception as e:
            results = results + [
                ValidationResult(
                    category=ValidationCategory.PERFORMANCE,
                    name="성능 검증",
                    status=ValidationStatus.ERROR,
                    message=f"성능 검증 중 오류: {str(e)}",
                    severity="error",
                )
            ]
        return results

    async def _run_security_validation(
        self, suite: ValidationSuite
    ) -> List[ValidationResult]:
        """보안 검증 실행"""
        results = []
        try:
            import os

            sensitive_vars = []
            for key, value in os.environ.items():
                if any(
                    (
                        keyword in key.upper()
                        for keyword in ["SECRET", "KEY", "TOKEN", "PASSWORD"]
                    )
                ):
                    if value and len(value) > 0:
                        sensitive_vars = sensitive_vars + [key]
            if sensitive_vars:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.SECURITY,
                        name="환경 변수 보안",
                        status=ValidationStatus.WARNING,
                        message=f"민감한 환경 변수 {len(sensitive_vars)}개 감지",
                        details={"sensitive_vars": sensitive_vars},
                        severity="warning",
                        recommendations=[
                            "민감한 정보는 별도의 시크릿 관리 시스템을 사용하세요",
                            "환경 변수 로깅을 비활성화하세요",
                        ],
                    )
                ]
            else:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.SECURITY,
                        name="환경 변수 보안",
                        status=ValidationStatus.PASS,
                        message="민감한 환경 변수가 감지되지 않았습니다",
                        severity="info",
                    )
                ]
            sensitive_files = [".env", "secrets.json", "credentials.json"]
            for filename in sensitive_files:
                file_path = self.project_path / filename
                if file_path.exists():
                    try:
                        import stat

                        file_stat = file_path.stat()
                        permissions = stat.filemode(file_stat.st_mode)
                        if file_stat.st_mode & stat.S_IROTH:
                            results = results + [
                                ValidationResult(
                                    category=ValidationCategory.SECURITY,
                                    name=f"파일 권한: {filename}",
                                    status=ValidationStatus.FAIL,
                                    message=f"파일 권한이 안전하지 않습니다: {permissions}",
                                    severity="error",
                                    recommendations=[
                                        f"chmod 600 {filename} 실행을 권장합니다"
                                    ],
                                )
                            ]
                        else:
                            results = results + [
                                ValidationResult(
                                    category=ValidationCategory.SECURITY,
                                    name=f"파일 권한: {filename}",
                                    status=ValidationStatus.PASS,
                                    message=f"파일 권한이 안전합니다: {permissions}",
                                    severity="info",
                                )
                            ]
                    except Exception as e:
                        results = results + [
                            ValidationResult(
                                category=ValidationCategory.SECURITY,
                                name=f"파일 권한: {filename}",
                                status=ValidationStatus.WARNING,
                                message=f"권한 검사 실패: {str(e)}",
                                severity="warning",
                            )
                        ]
        except Exception as e:
            results = results + [
                ValidationResult(
                    category=ValidationCategory.SECURITY,
                    name="보안 검증",
                    status=ValidationStatus.ERROR,
                    message=f"보안 검증 중 오류: {str(e)}",
                    severity="error",
                )
            ]
        return results

    async def _run_compatibility_validation(
        self, suite: ValidationSuite
    ) -> List[ValidationResult]:
        """호환성 검증 실행"""
        results = []
        try:
            python_version = sys.version_info
            if python_version >= (3, 10):
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.COMPATIBILITY,
                        name="Python 버전 호환성",
                        status=ValidationStatus.PASS,
                        message=f"Python {python_version.major}.{python_version.minor}.{python_version.micro} 지원됨",
                        details={
                            "python_version": f"{python_version.major}.{python_version.minor}.{python_version.micro}"
                        },
                        severity="info",
                    )
                ]
            else:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.COMPATIBILITY,
                        name="Python 버전 호환성",
                        status=ValidationStatus.FAIL,
                        message=f"Python {python_version.major}.{python_version.minor} 미지원 (3.10+ 필요)",
                        severity="critical",
                        recommendations=["Python 3.10 이상으로 업그레이드하세요"],
                    )
                ]
            current_platform = platform.system()
            supported_platforms = ["Linux", "Darwin", "Windows"]
            if current_platform in supported_platforms:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.COMPATIBILITY,
                        name="플랫폼 호환성",
                        status=ValidationStatus.PASS,
                        message=f"{current_platform} 플랫폼 지원됨",
                        details={"platform": current_platform},
                        severity="info",
                    )
                ]
            else:
                results = results + [
                    ValidationResult(
                        category=ValidationCategory.COMPATIBILITY,
                        name="플랫폼 호환성",
                        status=ValidationStatus.WARNING,
                        message=f"{current_platform} 플랫폼 미검증",
                        severity="warning",
                        recommendations=["지원되는 플랫폼에서 테스트하세요"],
                    )
                ]
        except Exception as e:
            results = results + [
                ValidationResult(
                    category=ValidationCategory.COMPATIBILITY,
                    name="호환성 검증",
                    status=ValidationStatus.ERROR,
                    message=f"호환성 검증 중 오류: {str(e)}",
                    severity="error",
                )
            ]
        return results

    async def _generate_validation_report(
        self, suite: ValidationSuite
    ) -> Dict[str, Any]:
        """검증 리포트 생성"""
        total_duration = (
            (self.end_time - self.start_time).total_seconds()
            if self.start_time and self.end_time
            else 0
        )
        total_tests = len(self.validation_results)
        passed_tests = len(
            [r for r in self.validation_results if r.status == ValidationStatus.PASS]
        )
        failed_tests = len(
            [r for r in self.validation_results if r.status == ValidationStatus.FAIL]
        )
        warning_tests = len(
            [r for r in self.validation_results if r.status == ValidationStatus.WARNING]
        )
        error_tests = len(
            [r for r in self.validation_results if r.status == ValidationStatus.ERROR]
        )
        critical_issues = len([r for r in self.validation_results if r.is_critical])
        category_stats = {}
        for category in ValidationCategory:
            category_results = [
                r for r in self.validation_results if r.category == category
            ]
            if category_results:
                category_stats = {
                    **category_stats,
                    category.value: {
                        category.value: {
                            "total": len(category_results),
                            "passed": len(
                                [
                                    r
                                    for r in category_results
                                    if r.status == ValidationStatus.PASS
                                ]
                            ),
                            "failed": len(
                                [
                                    r
                                    for r in category_results
                                    if r.status == ValidationStatus.FAIL
                                ]
                            ),
                            "warnings": len(
                                [
                                    r
                                    for r in category_results
                                    if r.status == ValidationStatus.WARNING
                                ]
                            ),
                            "success_rate": len(
                                [r for r in category_results if r.is_success]
                            )
                            / len(category_results)
                            * 100,
                        }
                    },
                }
        all_recommendations = []
        for result in self.validation_results:
            all_recommendations = all_recommendations + result.recommendations
        success_rate = passed_tests / total_tests * 100 if total_tests > 0 else 0
        overall_status = "PASS"
        if critical_issues > 0:
            overall_status = "CRITICAL"
        elif failed_tests > 0:
            overall_status = "FAIL"
        elif warning_tests > 0:
            overall_status = "WARNING"
        report = {
            "suite_info": {
                "name": suite.name,
                "description": suite.description,
                "level": suite.level.value,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": total_duration,
            },
            "summary": {
                "overall_status": overall_status,
                "success_rate": success_rate,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "warning_tests": warning_tests,
                "error_tests": error_tests,
                "critical_issues": critical_issues,
            },
            "category_stats": category_stats,
            "detailed_results": [
                {
                    "category": result.category.value,
                    "name": result.name,
                    "status": result.status.value,
                    "message": result.message,
                    "severity": result.severity,
                    "execution_time": result.execution_time,
                    "details": result.details,
                    "recommendations": result.recommendations,
                }
                for result in self.validation_results
            ],
            "recommendations": list(set(all_recommendations)),
            "system_info": {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": platform.system(),
                "project_path": str(self.project_path),
            },
        }
        return report

    async def _display_validation_results(self, report: Dict[str, Any]) -> None:
        """검증 결과 표시"""
        if not console:
            return
        summary = report["summary"]
        summary_table = Table(
            title="검증 결과 요약", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("항목", style="cyan", width=20)
        summary_table.add_column("값", style="white", justify="right")
        summary_table.add_column("상태", style="white", justify="center")
        status_colors = {
            "PASS": "green",
            "WARNING": "yellow",
            "FAIL": "red",
            "CRITICAL": "bright_red",
        }
        status_color = status_colors.get(summary["overall_status"], "white")
        summary_table.add_row(
            "전체 상태",
            summary.get("overall_status"),
            f"[{status_color}]●[/{status_color}]",
        )
        summary_table.add_row("성공률", f"{summary.get('success_rate'):.1f}%", "")
        summary_table.add_row("총 테스트", str(summary.get("total_tests")), "")
        summary_table.add_row(
            "통과", str(summary.get("passed_tests")), "[green]✅[/green]"
        )
        if summary.get("failed_tests") > 0:
            summary_table.add_row(
                "실패", str(summary.get("failed_tests")), "[red]❌[/red]"
            )
        if summary.get("warning_tests") > 0:
            summary_table.add_row(
                "경고", str(summary.get("warning_tests")), "[yellow]⚠️[/yellow]"
            )
        if summary.get("critical_issues") > 0:
            summary_table.add_row(
                "심각",
                str(summary.get("critical_issues")),
                "[bright_red]🚨[/bright_red]",
            )
        console.print(summary_table)
        if report.get("category_stats"):
            console.print("\n")
            category_table = Table(
                title="카테고리별 결과", show_header=True, header_style="bold blue"
            )
            category_table.add_column("카테고리", style="cyan")
            category_table.add_column("총계", justify="right")
            category_table.add_column("통과", justify="right")
            category_table.add_column("실패", justify="right")
            category_table.add_column("성공률", justify="right")
            for category, stats in report.get("category_stats").items():
                success_rate_color = (
                    "green"
                    if stats["success_rate"] >= 90
                    else "yellow" if stats["success_rate"] >= 70 else "red"
                )
                category_table.add_row(
                    category.title(),
                    str(stats.get("total")),
                    str(stats.get("passed")),
                    str(stats.get("failed")) if stats.get("failed") > 0 else "-",
                    f"[{success_rate_color}]{stats.get('success_rate'):.1f}%[/{success_rate_color}]",
                )
            console.print(category_table)
        failed_results = [
            r for r in report["detailed_results"] if r["status"] in ["fail", "error"]
        ]
        if failed_results:
            console.print("\n")
            failure_tree = Tree("❌ 실패한 검증 항목")
            for result in failed_results:
                severity_colors = {
                    "error": "red",
                    "critical": "bright_red",
                    "warning": "yellow",
                }
                color = severity_colors.get(result["severity"], "white")
                test_node = failure_tree.add(
                    f"[{color}]{result['name']}[/{color}] ({result['category']})"
                )
                test_node.add(f"메시지: {result.get('message')}")
                if result.get("recommendations"):
                    rec_node = test_node.add("권장사항:")
                    for rec in result.get("recommendations"):
                        rec_node.add(f"• {rec}")
            console.print(failure_tree)
        if report.get("recommendations"):
            console.print("\n")
            recommendations_panel = Panel(
                "\n".join([f"• {rec}" for rec in report.get("recommendations")]),
                title="🎯 종합 권장사항",
                border_style="yellow",
            )
            console.print(recommendations_panel)
        duration = report["suite_info"]["duration_seconds"]
        if summary.get("overall_status") == "PASS":
            console.print(
                Panel(
                    f"✅ 모든 검증 통과!\n\n🎯 성공률: {summary.get('success_rate'):.1f}%\n⏱️  실행 시간: {duration:.2f}초\n🏆 RFS v4 시스템이 프로덕션 준비 상태입니다!",
                    title="검증 성공",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"⚠️  검증에서 {summary.get('failed_tests') + summary.get('error_tests')}개 이슈 발견\n\n🎯 성공률: {summary.get('success_rate'):.1f}%\n⏱️  실행 시간: {duration:.2f}초\n\n💡 위의 권장사항을 검토하고 수정 후 다시 검증하세요.",
                    title="검증 결과",
                    border_style=(
                        "red"
                        if summary["overall_status"] in ["FAIL", "CRITICAL"]
                        else "yellow"
                    ),
                )
            )

    async def save_report(
        self, report: Dict[str, Any], output_path=None
    ) -> Result[str, str]:
        """검증 리포트 저장"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"validation_report_{timestamp}.json"
            report_file = Path(output_path)
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return Success(str(report_file.absolute()))
        except Exception as e:
            return Failure(f"리포트 저장 실패: {str(e)}")

    def get_validation_results(self) -> List[ValidationResult]:
        """검증 결과 조회"""
        return self.validation_results.copy()
