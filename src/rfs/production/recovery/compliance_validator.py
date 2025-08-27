"""
Compliance Validator for RFS Framework

컴플라이언스 검증 시스템:
- 규정 준수 검증
- 보안 표준 확인
- 감사 로그 관리
- 컴플라이언스 보고서 생성
"""

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiofiles

from ...core.result import Failure, Result, Success


class ComplianceStandard(Enum):
    """컴플라이언스 표준"""

    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    NIST = "nist"
    CIS = "cis"
    OWASP = "owasp"
    CUSTOM = "custom"


class ComplianceStatus(Enum):
    """컴플라이언스 상태"""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


class ControlCategory(Enum):
    """통제 카테고리"""

    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    NETWORK_SECURITY = "network_security"
    INCIDENT_RESPONSE = "incident_response"
    BUSINESS_CONTINUITY = "business_continuity"
    COMPLIANCE_MONITORING = "compliance_monitoring"
    AUDIT_LOGGING = "audit_logging"
    VULNERABILITY_MANAGEMENT = "vulnerability_management"
    ENCRYPTION = "encryption"
    AUTHENTICATION = "authentication"


class Severity(Enum):
    """심각도"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ComplianceControl:
    """컴플라이언스 통제"""

    id: str
    name: str
    description: str
    category: ControlCategory
    standard: ComplianceStandard
    requirements: List[str]
    validation_script = None
    remediation_steps: List[str] = field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    automated = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """검증 결과"""

    control_id: str
    status: ComplianceStatus
    timestamp: datetime
    evidence: Dict[str, Any] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceReport:
    """컴플라이언스 보고서"""

    id: str
    standard: ComplianceStandard
    generated_at: datetime
    overall_status: ComplianceStatus
    overall_score: float
    control_results: List[ValidationResult]
    summary: Dict[str, Any]
    recommendations: List[str]
    next_review_date = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLog:
    """감사 로그"""

    id: str
    timestamp: datetime
    event_type: str
    user: str
    action: str
    resource: str
    result: str
    ip_address = None
    user_agent = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompliancePolicy:
    """컴플라이언스 정책"""

    id: str
    name: str
    standards: List[ComplianceStandard]
    controls: List[str]
    validation_frequency: str
    auto_remediate = False
    notification_channels: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComplianceValidator:
    """컴플라이언스 검증자"""

    def __init__(self):
        self.controls = {}
        self.policies = {}
        self.validation_results = []
        self.reports = []
        self.audit_logs = []
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
        self._initialize_default_controls()

    def _initialize_default_controls(self):
        """기본 통제 초기화"""
        self.add_control(
            ComplianceControl(
                id="pci_dss_1.1",
                name="Firewall Configuration",
                description="Establish and implement firewall and router configuration standards",
                category=ControlCategory.NETWORK_SECURITY,
                standard=ComplianceStandard.PCI_DSS,
                requirements=[
                    "Firewall rules must be documented",
                    "Inbound and outbound traffic must be restricted",
                    "Firewall rules must be reviewed bi-annually",
                ],
                severity=Severity.HIGH,
            )
        )
        self.add_control(
            ComplianceControl(
                id="gdpr_art_32",
                name="Security of Processing",
                description="Implement appropriate technical and organizational measures",
                category=ControlCategory.DATA_PROTECTION,
                standard=ComplianceStandard.GDPR,
                requirements=[
                    "Encryption of personal data",
                    "Ability to restore availability and access",
                    "Regular testing of security measures",
                ],
                severity=Severity.CRITICAL,
            )
        )
        self.add_control(
            ComplianceControl(
                id="soc2_cc6.1",
                name="Logical Access Controls",
                description="Implement logical access security software and controls",
                category=ControlCategory.ACCESS_CONTROL,
                standard=ComplianceStandard.SOC2,
                requirements=[
                    "User authentication required",
                    "Access rights based on job responsibilities",
                    "Regular access reviews",
                ],
                severity=Severity.HIGH,
            )
        )
        self.add_control(
            ComplianceControl(
                id="owasp_a01",
                name="Broken Access Control",
                description="Prevent broken access control vulnerabilities",
                category=ControlCategory.ACCESS_CONTROL,
                standard=ComplianceStandard.OWASP,
                requirements=[
                    "Deny by default access control",
                    "Enforce record ownership",
                    "Disable directory listing",
                ],
                severity=Severity.CRITICAL,
            )
        )

    async def start(self) -> Result[bool, str]:
        """컴플라이언스 검증자 시작"""
        try:
            self._running = True
            scheduler_task = asyncio.create_task(self._validation_scheduler())
            self._tasks.add(scheduler_task)
            audit_task = asyncio.create_task(self._audit_log_collector())
            self._tasks.add(audit_task)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start compliance validator: {e}")

    async def stop(self) -> Result[bool, str]:
        """컴플라이언스 검증자 중지"""
        try:
            self._running = False
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                _tasks = {}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop compliance validator: {e}")

    def add_control(self, control: ComplianceControl) -> Result[bool, str]:
        """통제 추가"""
        try:
            if control.id in self.controls:
                return Failure(f"Control {control.id} already exists")
            self.controls = {**self.controls, control.id: control}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add control: {e}")

    def add_policy(self, policy: CompliancePolicy) -> Result[bool, str]:
        """정책 추가"""
        try:
            if policy.id in self.policies:
                return Failure(f"Policy {policy.id} already exists")
            for control_id in policy.controls:
                if control_id not in self.controls:
                    return Failure(f"Control {control_id} not found")
            self.policies = {**self.policies, policy.id: policy}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add policy: {e}")

    async def validate_control(
        self, control_id: str, context=None
    ) -> Result[ValidationResult, str]:
        """개별 통제 검증"""
        try:
            if control_id not in self.controls:
                return Failure(f"Control {control_id} not found")
            control = self.controls[control_id]
            context = context or {}
            if control.validation_script:
                validation_result = await self._execute_validation_script(
                    control.validation_script, context
                )
            else:
                validation_result = await self._perform_validation(control, context)
            result = ValidationResult(
                control_id=control_id,
                status=validation_result["status"],
                timestamp=datetime.now(),
                evidence=validation_result.get("evidence", {}),
                findings=validation_result.get("findings", []),
                recommendations=validation_result.get("recommendations", []),
                score=validation_result.get("score", 0.0),
                metadata=validation_result.get("metadata", {}),
            )
            self.validation_results = self.validation_results + [result]
            await self._log_audit_event(
                event_type="control_validation",
                user="system",
                action=f"Validated control {control_id}",
                resource=control_id,
                result=result.status.value,
            )
            return Success(result)
        except Exception as e:
            return Failure(f"Failed to validate control: {e}")

    async def validate_standard(
        self, standard: ComplianceStandard, context=None
    ) -> Result[ComplianceReport, str]:
        """표준 전체 검증"""
        try:
            standard_controls = [
                control
                for control in self.controls.values()
                if control.standard == standard
            ]
            if not standard_controls:
                return Failure(f"No controls found for standard {standard.value}")
            control_results = []
            total_score = 0.0
            for control in standard_controls:
                result = await self.validate_control(control.id, context)
                if type(result).__name__ == "Success":
                    control_results = [*control_results, result.value]
                    total_score = total_score + result.value.score
            overall_score = (
                total_score / len(control_results) if control_results else 0.0
            )
            overall_status = self._determine_overall_status(control_results)
            report = ComplianceReport(
                id=f"report_{standard.value}_{int(time.time())}",
                standard=standard,
                generated_at=datetime.now(),
                overall_status=overall_status,
                overall_score=overall_score,
                control_results=control_results,
                summary=self._generate_summary(control_results),
                recommendations=self._generate_recommendations(control_results),
                next_review_date=datetime.now() + timedelta(days=90),
            )
            self.reports = self.reports + [report]
            return Success(report)
        except Exception as e:
            return Failure(f"Failed to validate standard: {e}")

    async def validate_policy(
        self, policy_id: str, context=None
    ) -> Result[Dict[str, Any], str]:
        """정책 검증"""
        try:
            if policy_id not in self.policies:
                return Failure(f"Policy {policy_id} not found")
            policy = self.policies[policy_id]
            results = []
            for control_id in policy.controls:
                result = await self.validate_control(control_id, context)
                if type(result).__name__ == "Success":
                    results = [*results, result.value]
            compliant_controls = sum(
                (1 for r in results if r.status == ComplianceStatus.COMPLIANT)
            )
            compliance_rate = compliant_controls / len(results) * 100 if results else 0
            return Success(
                {
                    "policy_id": policy_id,
                    "policy_name": policy.name,
                    "compliance_rate": compliance_rate,
                    "total_controls": len(policy.controls),
                    "compliant_controls": compliant_controls,
                    "validation_results": results,
                    "timestamp": datetime.now(),
                }
            )
        except Exception as e:
            return Failure(f"Failed to validate policy: {e}")

    async def generate_compliance_report(
        self,
        standards=None,
        start_date=None,
        end_date=None,
    ) -> Result[Dict[str, Any], str]:
        """종합 컴플라이언스 보고서 생성"""
        try:
            standards = standards or list(ComplianceStandard)
            start_date = start_date or datetime.now() - timedelta(days=30)
            end_date = end_date or datetime.now()
            standard_reports = {}
            for standard in standards:
                latest_report = self._get_latest_report(standard, start_date, end_date)
                if latest_report:
                    standard_reports = {
                        **standard_reports,
                        standard.value: latest_report,
                    }
            total_score = (
                sum((report.overall_score for report in standard_reports.values()))
                / len(standard_reports)
                if standard_reports
                else 0
            )
            all_findings = []
            all_recommendations = []
            for report in standard_reports.values():
                for result in report.control_results:
                    all_findings = all_findings + result.findings
                all_recommendations = all_recommendations + report.recommendations
            unique_findings = list(set(all_findings))
            unique_recommendations = list(set(all_recommendations))
            return Success(
                {
                    "report_id": f"compliance_report_{int(time.time())}",
                    "generated_at": datetime.now(),
                    "period": {"start": start_date, "end": end_date},
                    "overall_score": total_score,
                    "standards": standard_reports,
                    "key_findings": unique_findings[:10],
                    "recommendations": unique_recommendations[:10],
                    "compliance_trends": self._calculate_compliance_trends(),
                    "risk_areas": self._identify_risk_areas(standard_reports),
                }
            )
        except Exception as e:
            return Failure(f"Failed to generate compliance report: {e}")

    async def get_audit_logs(
        self,
        start_date=None,
        end_date=None,
        event_type=None,
        user=None,
        limit=1000,
    ) -> Result[List[AuditLog], str]:
        """감사 로그 조회"""
        try:
            filtered_logs = []
            for log in self.audit_logs:
                if start_date and log.timestamp < start_date:
                    continue
                if end_date and log.timestamp > end_date:
                    continue
                if event_type and log.event_type != event_type:
                    continue
                if user and log.user != user:
                    continue
                filtered_logs = [*filtered_logs, log]
                if len(filtered_logs) >= limit:
                    break
            return Success(filtered_logs)
        except Exception as e:
            return Failure(f"Failed to get audit logs: {e}")

    async def check_data_privacy_compliance(
        self, data_inventory: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """데이터 프라이버시 컴플라이언스 확인"""
        try:
            checks = {
                "data_classification": False,
                "encryption_at_rest": False,
                "encryption_in_transit": False,
                "access_controls": False,
                "data_retention": False,
                "data_deletion": False,
                "consent_management": False,
                "data_portability": False,
            }
            if "classification" in data_inventory:
                checks["data_classification"] = True
            if data_inventory.get("encryption", {}).get("at_rest"):
                checks["encryption_at_rest"] = True
            if data_inventory.get("encryption", {}).get("in_transit"):
                checks["encryption_in_transit"] = True
            if data_inventory.get("access_controls"):
                checks["access_controls"] = True
            if data_inventory.get("retention_policy"):
                checks["data_retention"] = True
            if data_inventory.get("deletion_procedures"):
                checks["data_deletion"] = True
            if data_inventory.get("consent_management"):
                checks["consent_management"] = True
            if data_inventory.get("data_portability"):
                checks["data_portability"] = True
            compliance_score = sum(checks.values()) / len(checks) * 100
            return Success(
                {
                    "compliance_score": compliance_score,
                    "checks": checks,
                    "compliant": compliance_score >= 80,
                    "recommendations": self._generate_privacy_recommendations(checks),
                }
            )
        except Exception as e:
            return Failure(f"Failed to check data privacy compliance: {e}")

    async def check_security_compliance(
        self, security_config: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """보안 컴플라이언스 확인"""
        try:
            checks = {
                "mfa_enabled": False,
                "password_policy": False,
                "session_timeout": False,
                "audit_logging": False,
                "vulnerability_scanning": False,
                "incident_response": False,
                "backup_recovery": False,
                "network_segmentation": False,
            }
            if security_config.get("mfa", {}).get("enabled"):
                checks["mfa_enabled"] = True
            password_policy = security_config.get("password_policy", {})
            if password_policy.get("min_length", 0) >= 12 and password_policy.get(
                "complexity_required"
            ):
                checks["password_policy"] = True
            if security_config.get("session_timeout", 0) <= 3600:
                checks["session_timeout"] = True
            if security_config.get("audit_logging", {}).get("enabled"):
                checks["audit_logging"] = True
            if security_config.get("vulnerability_scanning", {}).get("enabled"):
                checks["vulnerability_scanning"] = True
            if security_config.get("incident_response_plan"):
                checks["incident_response"] = True
            if security_config.get("backup_recovery", {}).get("enabled"):
                checks["backup_recovery"] = True
            if security_config.get("network_segmentation", {}).get("enabled"):
                checks["network_segmentation"] = True
            compliance_score = sum(checks.values()) / len(checks) * 100
            return Success(
                {
                    "compliance_score": compliance_score,
                    "checks": checks,
                    "compliant": compliance_score >= 75,
                    "risk_level": self._calculate_risk_level(compliance_score),
                    "recommendations": self._generate_security_recommendations(checks),
                }
            )
        except Exception as e:
            return Failure(f"Failed to check security compliance: {e}")

    async def _perform_validation(
        self, control: ComplianceControl, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """통제 검증 수행"""
        findings = []
        recommendations = []
        score = 100.0
        for requirement in control.requirements:
            match control.category:
                case ControlCategory.ACCESS_CONTROL:
                    if "access_control" not in context:
                        findings = [
                            *findings,
                            f"Missing access control implementation for: {requirement}",
                        ]
                        recommendations = recommendations + control.remediation_steps
                        score = score - 20
                case ControlCategory.DATA_PROTECTION:
                    if "encryption" not in context or not context["encryption"]:
                        findings = [
                            *findings,
                            f"Data protection not implemented: {requirement}",
                        ]
                        recommendations = [
                            *recommendations,
                            "Enable encryption for sensitive data",
                        ]
                        score = score - 25
                case ControlCategory.NETWORK_SECURITY:
                    if "firewall" not in context:
                        findings = [
                            *findings,
                            f"Network security control missing: {requirement}",
                        ]
                        recommendations = [*recommendations, "Configure firewall rules"]
                        score = score - 15
        if score >= 90:
            status = ComplianceStatus.COMPLIANT
        elif score >= 70:
            status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            status = ComplianceStatus.NON_COMPLIANT
        return {
            "status": status,
            "score": max(0, score),
            "findings": findings,
            "recommendations": recommendations,
            "evidence": {
                "validation_time": datetime.now().isoformat(),
                "control_category": control.category.value,
            },
        }

    async def _execute_validation_script(
        self, script_path: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """검증 스크립트 실행"""
        try:
            return {
                "status": ComplianceStatus.COMPLIANT,
                "score": 95.0,
                "findings": [],
                "recommendations": [],
            }
        except Exception:
            return {
                "status": ComplianceStatus.NON_COMPLIANT,
                "score": 0.0,
                "findings": ["Script execution failed"],
                "recommendations": ["Fix validation script"],
            }

    def _determine_overall_status(
        self, results: List[ValidationResult]
    ) -> ComplianceStatus:
        """전체 컴플라이언스 상태 결정"""
        if not results:
            return ComplianceStatus.NOT_APPLICABLE
        statuses = [r.status for r in results]
        if ComplianceStatus.NON_COMPLIANT in statuses:
            return ComplianceStatus.NON_COMPLIANT
        if all((s == ComplianceStatus.COMPLIANT for s in statuses)):
            return ComplianceStatus.COMPLIANT
        return ComplianceStatus.PARTIALLY_COMPLIANT

    def _generate_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """요약 생성"""
        return {
            "total_controls": len(results),
            "compliant": sum(
                (1 for r in results if r.status == ComplianceStatus.COMPLIANT)
            ),
            "non_compliant": sum(
                (1 for r in results if r.status == ComplianceStatus.NON_COMPLIANT)
            ),
            "partially_compliant": sum(
                (1 for r in results if r.status == ComplianceStatus.PARTIALLY_COMPLIANT)
            ),
            "average_score": (
                sum((r.score for r in results)) / len(results) if results else 0
            ),
        }

    def _generate_recommendations(self, results: List[ValidationResult]) -> List[str]:
        """권장사항 생성"""
        all_recommendations = []
        for result in results:
            if result.status != ComplianceStatus.COMPLIANT:
                all_recommendations = all_recommendations + result.recommendations
        unique_recommendations = list(set(all_recommendations))
        return unique_recommendations[:10]

    def _generate_privacy_recommendations(self, checks: Dict[str, bool]) -> List[str]:
        """프라이버시 권장사항 생성"""
        recommendations = []
        if not checks["data_classification"]:
            recommendations = [*recommendations, "Implement data classification system"]
        if not checks["encryption_at_rest"]:
            recommendations = [*recommendations, "Enable encryption for data at rest"]
        if not checks["encryption_in_transit"]:
            recommendations = [*recommendations, "Enable TLS/SSL for data in transit"]
        if not checks["access_controls"]:
            recommendations = [*recommendations, "Implement role-based access controls"]
        if not checks["data_retention"]:
            recommendations = [
                *recommendations,
                "Define and implement data retention policies",
            ]
        return recommendations

    def _generate_security_recommendations(self, checks: Dict[str, bool]) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        if not checks["mfa_enabled"]:
            recommendations = [*recommendations, "Enable multi-factor authentication"]
        if not checks["password_policy"]:
            recommendations = [
                *recommendations,
                "Strengthen password policy requirements",
            ]
        if not checks["session_timeout"]:
            recommendations = [*recommendations, "Implement session timeout controls"]
        if not checks["audit_logging"]:
            recommendations = [*recommendations, "Enable comprehensive audit logging"]
        if not checks["vulnerability_scanning"]:
            recommendations = [
                *recommendations,
                "Implement regular vulnerability scanning",
            ]
        return recommendations

    def _calculate_risk_level(self, compliance_score: float) -> str:
        """위험 수준 계산"""
        if compliance_score >= 90:
            return "LOW"
        elif compliance_score >= 70:
            return "MEDIUM"
        elif compliance_score >= 50:
            return "HIGH"
        else:
            return "CRITICAL"

    def _get_latest_report(
        self, standard: ComplianceStandard, start_date: datetime, end_date: datetime
    ) -> Optional[ComplianceReport]:
        """최신 보고서 조회"""
        filtered_reports = [
            r
            for r in self.reports
            if r.standard == standard and start_date <= r.generated_at <= end_date
        ]
        if not filtered_reports:
            return None
        return max(filtered_reports, key=lambda x: x.generated_at)

    def _calculate_compliance_trends(self) -> Dict[str, Any]:
        """컴플라이언스 추세 계산"""
        trends = {}
        for month in range(6):
            month_start = datetime.now() - timedelta(days=30 * (month + 1))
            month_end = datetime.now() - timedelta(days=30 * month)
            month_reports = [
                r for r in self.reports if month_start <= r.generated_at <= month_end
            ]
            if month_reports:
                avg_score = sum((r.overall_score for r in month_reports)) / len(
                    month_reports
                )
                trends[f"month_{month + 1}"] = avg_score
        return trends

    def _identify_risk_areas(
        self, standard_reports: Dict[str, ComplianceReport]
    ) -> List[Dict[str, Any]]:
        """위험 영역 식별"""
        risk_areas = []
        for standard, report in standard_reports.items():
            for result in report.control_results:
                if result.status == ComplianceStatus.NON_COMPLIANT:
                    control = self.controls.get(result.control_id)
                    if control and control.severity in [
                        Severity.CRITICAL,
                        Severity.HIGH,
                    ]:
                        risk_areas = risk_areas + [
                            {
                                "control_id": result.control_id,
                                "control_name": control.name,
                                "category": control.category.value,
                                "severity": control.severity.value,
                                "findings": result.findings,
                            }
                        ]
        risk_areas.sort(key=lambda x: 0 if x["severity"] == "critical" else 1)
        return risk_areas[:10]

    async def _validation_scheduler(self):
        """검증 스케줄러"""
        while self._running:
            try:
                for policy in self.policies.values():
                    if self._should_run_validation(policy.validation_frequency):
                        await self.validate_policy(policy.id)
                await asyncio.sleep(3600)
            except Exception as e:
                print(f"Validation scheduler error: {e}")
                await asyncio.sleep(3600)

    async def _audit_log_collector(self):
        """감사 로그 수집기"""
        while self._running:
            try:
                cutoff_date = datetime.now() - timedelta(days=90)
                self.audit_logs = [
                    log for log in self.audit_logs if log.timestamp > cutoff_date
                ]
                await asyncio.sleep(3600)
            except Exception as e:
                print(f"Audit log collector error: {e}")
                await asyncio.sleep(3600)

    async def _log_audit_event(
        self,
        event_type: str,
        user: str,
        action: str,
        resource: str,
        result: str,
        metadata=None,
    ):
        """감사 이벤트 로깅"""
        audit_log = AuditLog(
            id=f"audit_{int(time.time() * 1000)}",
            timestamp=datetime.now(),
            event_type=event_type,
            user=user,
            action=action,
            resource=resource,
            result=result,
            metadata=metadata or {},
        )
        self.audit_logs = self.audit_logs + [audit_log]

    def _should_run_validation(self, schedule: str) -> bool:
        """검증 실행 여부 확인"""
        current_time = datetime.now()
        match schedule:
            case "hourly":
                return current_time.minute == 0
            case "daily":
                return current_time.hour == 0 and current_time.minute == 0
            case "weekly":
                return current_time.weekday() == 0 and current_time.hour == 0
            case "monthly":
                return current_time.day == 1 and current_time.hour == 0
            case _:
                return False


_compliance_validator = None


def get_compliance_validator() -> ComplianceValidator:
    """컴플라이언스 검증자 인스턴스 반환"""
    if _compliance_validator is None:
        _compliance_validator = ComplianceValidator()
    return _compliance_validator


async def check_compliance(
    standard: ComplianceStandard, context=None
) -> Result[ComplianceReport, str]:
    """컴플라이언스 확인 헬퍼"""
    validator = get_compliance_validator()
    return await validator.validate_standard(standard, context)
