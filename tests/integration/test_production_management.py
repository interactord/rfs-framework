"""
Production Management Integration Tests
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

import pytest

from rfs.core import Failure, Success
from rfs.production.monitoring import (
    AlertSeverity,
    HealthStatus,
    get_alert_manager,
    get_health_checker,
    get_production_monitor,
)
from rfs.production.recovery import (
    BackupType,
    ComplianceStandard,
    RecoveryStrategy,
    get_backup_manager,
    get_compliance_validator,
    get_disaster_recovery_manager,
)


@pytest.mark.asyncio
class TestProductionMonitoring:
    """프로덕션 모니터링 통합 테스트"""

    async def test_production_monitor(self):
        """프로덕션 모니터 테스트"""
        monitor = get_production_monitor()

        # 모니터 시작
        start_result = await monitor.start()
        assert isinstance(start_result, Success)

        # 메트릭 수집 대기
        await asyncio.sleep(2)

        # 메트릭 조회
        metrics = monitor.get_current_metrics()
        assert "system" in metrics
        assert "cpu_percent" in metrics["system"]
        assert "memory_percent" in metrics["system"]

        # 모니터 중지
        await monitor.stop()

    async def test_alert_manager(self):
        """알림 관리자 테스트"""
        alert_manager = get_alert_manager()

        # 알림 관리자 시작
        start_result = await alert_manager.start()
        assert isinstance(start_result, Success)

        # 알림 규칙 추가
        rule_result = alert_manager.add_rule(
            rule_id="high_cpu",
            name="High CPU Usage",
            condition="cpu_percent > 80",
            level=AlertSeverity.WARNING,
            channels=["email", "slack"],
        )
        assert isinstance(rule_result, Success)

        # 알림 생성
        alert_result = await alert_manager.create_alert(
            rule_id="high_cpu",
            title="High CPU Usage Detected",
            message="CPU usage is above 80%",
            level=AlertSeverity.WARNING,
        )
        assert isinstance(alert_result, Success)

        alert = alert_result.value
        assert alert.title == "High CPU Usage Detected"
        assert alert.level == AlertSeverity.WARNING

        # 알림 확인
        ack_result = await alert_manager.acknowledge_alert(
            alert.id, acknowledged_by="test_user"
        )
        assert isinstance(ack_result, Success)

        # 알림 해결
        resolve_result = await alert_manager.resolve_alert(alert.id)
        assert isinstance(resolve_result, Success)

        # 알림 관리자 중지
        await alert_manager.stop()

    async def test_health_checker(self):
        """헬스 체커 테스트"""
        health_checker = get_health_checker()

        # 헬스 체크 추가
        health_checker.add_check(
            check_id="api_health",
            name="API Health Check",
            check_type=HealthStatus.HTTP,
            config={
                "url": "http://localhost:8000/health",
                "method": "GET",
                "timeout": 5,
            },
        )

        # 헬스 체커 시작
        start_result = await health_checker.start()
        assert isinstance(start_result, Success)

        # 체크 실행 대기
        await asyncio.sleep(2)

        # 전체 헬스 상태 조회
        health_status = health_checker.get_overall_health()
        assert "status" in health_status
        assert "checks" in health_status

        # 헬스 체커 중지
        await health_checker.stop()


@pytest.mark.asyncio
class TestDisasterRecovery:
    """재해 복구 통합 테스트"""

    async def test_disaster_recovery_manager(self):
        """재해 복구 관리자 테스트"""
        dr_manager = get_disaster_recovery_manager()

        # 복구 계획 추가
        plan_result = dr_manager.add_recovery_plan(
            plan_id="dr_plan_1",
            name="Primary DR Plan",
            strategy=RecoveryStrategy.HOT_STANDBY,
            rpo_minutes=15,
            rto_minutes=30,
        )
        assert isinstance(plan_result, Success)

        # 복구 계획 테스트
        test_result = await dr_manager.test_recovery_plan("dr_plan_1")
        assert isinstance(test_result, Success)

        test_data = test_result.value
        assert "plan_id" in test_data
        assert "test_results" in test_data

    async def test_backup_manager(self):
        """백업 관리자 테스트"""
        backup_manager = get_backup_manager()

        # 백업 관리자 시작
        start_result = await backup_manager.start()
        assert isinstance(start_result, Success)

        # 백업 정책 추가
        from rfs.production.recovery import BackupPolicy, BackupTarget

        policy = BackupPolicy(
            id="backup_policy_1",
            name="Daily Backup",
            backup_type=BackupType.FULL,
            schedule="daily",
            retention_days=30,
        )

        policy_result = backup_manager.add_policy(policy)
        assert isinstance(policy_result, Success)

        # 백업 대상 추가
        target = BackupTarget(
            id="backup_target_1",
            name="Application Data",
            type="filesystem",
            source_path="/tmp/test_data",
        )

        target_result = backup_manager.add_target(target)
        assert isinstance(target_result, Success)

        # 백업 생성
        backup_result = await backup_manager.create_backup(
            policy_id="backup_policy_1", target_id="backup_target_1", manual=True
        )
        assert isinstance(backup_result, Success)

        operation = backup_result.value
        assert operation.policy_id == "backup_policy_1"
        assert operation.target_id == "backup_target_1"

        # 백업 관리자 중지
        await backup_manager.stop()

    async def test_compliance_validator(self):
        """컴플라이언스 검증자 테스트"""
        validator = get_compliance_validator()

        # 검증자 시작
        start_result = await validator.start()
        assert isinstance(start_result, Success)

        # 표준 검증
        validation_result = await validator.validate_standard(
            ComplianceStandard.SOC2,
            context={"access_control": True, "encryption": True, "audit_logging": True},
        )
        assert isinstance(validation_result, Success)

        report = validation_result.value
        assert report.standard == ComplianceStandard.SOC2
        assert report.overall_score >= 0

        # 데이터 프라이버시 검증
        privacy_result = await validator.check_data_privacy_compliance(
            {
                "classification": True,
                "encryption": {"at_rest": True, "in_transit": True},
                "access_controls": True,
                "retention_policy": True,
            }
        )
        assert isinstance(privacy_result, Success)

        privacy_data = privacy_result.value
        assert "compliance_score" in privacy_data
        assert privacy_data["compliance_score"] >= 0

        # 검증자 중지
        await validator.stop()


@pytest.mark.asyncio
class TestIntegratedProductionFlow:
    """통합 프로덕션 플로우 테스트"""

    async def test_monitoring_to_alert_flow(self):
        """모니터링에서 알림까지의 플로우"""
        monitor = get_production_monitor()
        alert_manager = get_alert_manager()

        # 시작
        await monitor.start()
        await alert_manager.start()

        # CPU 임계값 규칙 추가
        alert_manager.add_rule(
            rule_id="cpu_threshold",
            name="CPU Threshold",
            condition="cpu_percent > 50",  # 낮은 임계값
            level=AlertSeverity.WARNING,
            channels=["email"],
        )

        # 메트릭 수집 및 알림 생성 대기
        await asyncio.sleep(3)

        # 알림 확인
        alerts = alert_manager.get_active_alerts()
        # CPU 사용량에 따라 알림이 생성될 수 있음

        # 정리
        await monitor.stop()
        await alert_manager.stop()

    async def test_health_check_to_recovery_flow(self):
        """헬스 체크에서 복구까지의 플로우"""
        health_checker = get_health_checker()
        dr_manager = get_disaster_recovery_manager()

        # 헬스 체크 실패 시뮬레이션
        health_checker.add_check(
            check_id="critical_service",
            name="Critical Service",
            check_type=HealthStatus.CUSTOM,
            config={"checker": lambda: False},  # 항상 실패
        )

        await health_checker.start()

        # 헬스 체크 실행
        await asyncio.sleep(2)

        # 헬스 상태 확인
        health = health_checker.get_overall_health()

        if health["status"] == "unhealthy":
            # 복구 계획 실행
            dr_manager.add_recovery_plan(
                plan_id="auto_recovery",
                name="Auto Recovery",
                strategy=RecoveryStrategy.WARM_STANDBY,
                rpo_minutes=5,
                rto_minutes=10,
            )

            # 복구 트리거 (시뮬레이션)
            # recovery_result = await dr_manager.trigger_recovery(
            #     plan_id="auto_recovery",
            #     disaster_type=DisasterType.SERVICE_FAILURE
            # )

        await health_checker.stop()
