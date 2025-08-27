"""
Alert Manager for RFS Framework

지능형 알림 관리 시스템
- 다양한 알림 채널 지원 (이메일, 슬랙, 웹훅 등)
- 알림 규칙 및 정책 관리
- 알림 에스컬레이션 및 그룹화
- 알림 히스토리 및 통계
"""

import asyncio
import json
import logging
import re
import smtplib
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

try:
    import aiohttp
except ImportError:
    aiohttp = None

from rfs.core.config import get_config
from rfs.core.result import Failure, Result, Success
from rfs.events.event_bus import Event
from rfs.reactive.mono import Mono


class AlertSeverity(Enum):
    """알림 심각도"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(Enum):
    """알림 상태"""

    ACTIVE = "active"
    ACKNOWLEDGED = "ack"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"


class ChannelType(Enum):
    """알림 채널 유형"""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    DISCORD = "discord"
    TEAMS = "teams"
    PAGERDUTY = "pagerduty"


class EscalationLevel(Enum):
    """에스컬레이션 레벨"""

    L1 = "level1"
    L2 = "level2"
    L3 = "level3"
    EXECUTIVE = "executive"


@dataclass
class AlertCondition:
    """알림 조건"""

    metric_name: str
    operator: str
    threshold: float
    duration_minutes: float = 5.0
    comparison_type = "absolute"


@dataclass
class AlertRule:
    """알림 규칙"""

    id: str
    name: str
    description: str
    conditions: List[AlertCondition]
    severity: AlertSeverity
    enabled = True
    tags: Dict[str, Any] = field(default_factory=dict)
    runbook_url = None
    silence_duration_minutes: float = 60.0


@dataclass
class NotificationChannel:
    """알림 채널"""

    id: str
    name: str
    channel_type: ChannelType
    config: Dict[str, Any]
    enabled = True
    severity_filter: List[str] = field(default_factory=list)
    tags_filter: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertPolicy:
    """알림 정책"""

    id: str
    name: str
    rules: List[str]
    channels: List[str]
    escalation_rules: List[Dict[str, Any]] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    group_wait_minutes: float = 5.0
    group_interval_minutes: float = 30.0
    repeat_interval_minutes: float = 240.0


@dataclass
class Alert:
    """알림"""

    id: str
    rule_id: str
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    source: str
    labels: Dict[str, Any] = field(default_factory=dict)
    annotations: Dict[str, Any] = field(default_factory=dict)
    resolved_at = None
    acknowledged_at = None
    acknowledged_by = None
    escalation_level: EscalationLevel = EscalationLevel.L1


class AlertChannel:
    """알림 채널 추상 클래스"""

    def __init__(self, channel_config: NotificationChannel):
        self.config = channel_config

    async def send_alert(self, alert: Alert, context=None) -> Result[bool, str]:
        """알림 전송 (서브클래스에서 구현)"""
        raise NotImplementedError


class EmailChannel(AlertChannel):
    """이메일 알림 채널"""

    async def send_alert(self, alert: Alert, context=None) -> Result[bool, str]:
        """이메일 알림 전송"""
        try:
            config = self.config.config
            smtp_server = config.get("smtp_server", "localhost")
            smtp_port = config.get("smtp_port", 587)
            username = config.get("username")
            password = config.get("password")
            from_email = config.get("from_email")
            to_emails = config.get("to_emails", [])
            if not to_emails:
                return Failure("No recipient email addresses configured")
            subject = f"[{alert.severity.value.upper()}] {alert.title}"
            body = self._format_email_body(alert, context)
            msg = MIMEMultipart()
            msg["From"] = {"From": from_email}
            msg["To"] = {"To": ", ".join(to_emails)}
            msg["Subject"] = {"Subject": subject}
            msg.attach(MIMEText(body, "html"))
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                if username and password:
                    server.login(username, password)
                text = msg.as_string()
                server.sendmail(from_email, to_emails, text)
            return Success(True)
        except Exception as e:
            return Failure(f"Email sending failed: {e}")

    def _format_email_body(self, alert: Alert, context=None) -> str:
        """이메일 본문 포맷"""
        severity_color = {
            AlertSeverity.CRITICAL: "#FF0000",
            AlertSeverity.HIGH: "#FF6600",
            AlertSeverity.MEDIUM: "#FFAA00",
            AlertSeverity.LOW: "#00AA00",
            AlertSeverity.INFO: "#0066FF",
        }.get(alert.severity, "#666666")
        body = f'\n        <html>\n        <body style="font-family: Arial, sans-serif;">\n            <div style="border-left: 4px solid {severity_color}; padding: 10px; margin: 10px 0;">\n                <h2 style="color: {severity_color}; margin: 0;">{alert.title}</h2>\n                <p><strong>Severity:</strong> {alert.severity.value.upper()}</p>\n                <p><strong>Status:</strong> {alert.status.value.upper()}</p>\n                <p><strong>Created:</strong> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>\n                <p><strong>Source:</strong> {alert.source}</p>\n            </div>\n            \n            <div style="background-color: #f5f5f5; padding: 15px; margin: 10px 0;">\n                <h3>Message:</h3>\n                <p>{alert.message}</p>\n            </div>\n            \n            {self._format_labels_section(alert)}\n            {self._format_context_section(context)}\n        </body>\n        </html>\n        '
        return body

    def _format_labels_section(self, alert: Alert) -> str:
        """레이블 섹션 포맷"""
        if not alert.labels:
            return ""
        labels_html = "<div style='margin: 10px 0;'><h4>Labels:</h4><ul>"
        for key, value in alert.labels.items():
            labels_html = labels_html + f"<li><strong>{key}:</strong> {value}</li>"
        labels_html = labels_html + "</ul></div>"
        return labels_html

    def _format_context_section(self, context: Dict[str, Any]) -> str:
        """컨텍스트 섹션 포맷"""
        if not context:
            return ""
        context_html = "<div style='margin: 10px 0;'><h4>Additional Context:</h4><ul>"
        for key, value in context.items():
            context_html = context_html + f"<li><strong>{key}:</strong> {value}</li>"
        context_html = context_html + "</ul></div>"
        return context_html


class SlackChannel(AlertChannel):
    """슬랙 알림 채널"""

    async def send_alert(self, alert: Alert, context=None) -> Result[bool, str]:
        """슬랙 알림 전송"""
        try:
            config = self.config.config
            webhook_url = config.get("webhook_url")
            if not webhook_url:
                return Failure("Slack webhook URL not configured")
            payload = self._format_slack_message(alert, context)
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        return Success(True)
                    else:
                        return Failure(f"Slack API error: {response.status}")
        except Exception as e:
            return Failure(f"Slack sending failed: {e}")

    def _format_slack_message(self, alert: Alert, context=None) -> Dict[str, Any]:
        """슬랙 메시지 포맷"""
        severity_emoji = {
            AlertSeverity.CRITICAL: ":fire:",
            AlertSeverity.HIGH: ":warning:",
            AlertSeverity.MEDIUM: ":large_orange_diamond:",
            AlertSeverity.LOW: ":information_source:",
            AlertSeverity.INFO: ":memo:",
        }.get(alert.severity, ":grey_question:")
        severity_color = {
            AlertSeverity.CRITICAL: "danger",
            AlertSeverity.HIGH: "warning",
            AlertSeverity.MEDIUM: "#FFAA00",
            AlertSeverity.LOW: "good",
            AlertSeverity.INFO: "#0066FF",
        }.get(alert.severity, "#666666")
        fields = [
            {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
            {"title": "Status", "value": alert.status.value.upper(), "short": True},
            {
                "title": "Created",
                "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "short": True,
            },
            {"title": "Source", "value": alert.source, "short": True},
        ]
        if alert.labels:
            labels_text = "\\n".join([f"*{k}:* {v}" for k, v in alert.labels.items()])
            fields = fields + [
                {"title": "Labels", "value": labels_text, "short": False}
            ]
        attachment = {
            "color": severity_color,
            "title": f"{severity_emoji} {alert.title}",
            "text": alert.message,
            "fields": fields,
            "footer": "RFS Alert Manager",
            "ts": int(alert.created_at.timestamp()),
        }
        return {"text": f"Alert: {alert.title}", "attachments": [attachment]}


class WebhookChannel(AlertChannel):
    """웹훅 알림 채널"""

    async def send_alert(self, alert: Alert, context=None) -> Result[bool, str]:
        """웹훅 알림 전송"""
        try:
            config = self.config.config
            webhook_url = config.get("url")
            headers = config.get("headers", {})
            method = config.get("method", "POST").upper()
            if not webhook_url:
                return Failure("Webhook URL not configured")
            payload = self._format_webhook_payload(alert, context)
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(
                        webhook_url, headers=headers, params=payload
                    ) as response:
                        if 200 <= response.status < 300:
                            return Success(True)
                        else:
                            return Failure(f"Webhook error: {response.status}")
                else:
                    async with session.post(
                        webhook_url, json=payload, headers=headers
                    ) as response:
                        if 200 <= response.status < 300:
                            return Success(True)
                        else:
                            return Failure(f"Webhook error: {response.status}")
        except Exception as e:
            return Failure(f"Webhook sending failed: {e}")

    def _format_webhook_payload(self, alert: Alert, context=None) -> Dict[str, Any]:
        """웹훅 페이로드 포맷"""
        payload = {
            "alert": {
                "id": alert.id,
                "rule_id": alert.rule_id,
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat(),
                "updated_at": alert.updated_at.isoformat(),
                "source": alert.source,
                "labels": alert.labels,
                "annotations": alert.annotations,
                "escalation_level": alert.escalation_level.value,
            },
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
        }
        if alert.resolved_at:
            payload = {
                **payload,
                "alert": {
                    **payload["alert"],
                    "resolved_at": alert.resolved_at.isoformat(),
                },
            }
        if alert.acknowledged_at:
            payload = {
                **payload,
                "alert": {
                    **payload["alert"],
                    "acknowledged_at": alert.acknowledged_at.isoformat(),
                },
            }
            payload = {
                **payload,
                "alert": {**payload["alert"], "acknowledged_by": alert.acknowledged_by},
            }
        return payload


class AlertGrouping:
    """알림 그룹화"""

    def __init__(self):
        self.groups: Dict[str, List[Alert]] = defaultdict(list)
        self.group_timers = {}

    def add_alert(self, alert: Alert, group_by: List[str]) -> str:
        """알림을 그룹에 추가"""
        group_key = self._generate_group_key(alert, group_by)
        self.groups[group_key] = groups[group_key] + [alert]
        if group_key not in self.group_timers:
            self.group_timers = {**self.group_timers, group_key: datetime.now()}
        return group_key

    def _generate_group_key(self, alert: Alert, group_by: List[str]) -> str:
        """그룹 키 생성"""
        if not group_by:
            return alert.rule_id
        key_parts = []
        for field in group_by:
            if field in alert.labels:
                key_parts = key_parts + [f"{field}={alert.labels[field]}"]
            elif hasattr(alert, field):
                key_parts = key_parts + [f"{field}={getattr(alert, field)}"]
        return "|".join(key_parts) if key_parts else alert.rule_id

    def get_ready_groups(self, wait_minutes: float) -> Dict[str, List[Alert]]:
        """전송 준비된 그룹 조회"""
        ready_groups = {}
        current_time = datetime.now()
        for group_key, timer in list(self.group_timers.items()):
            if (current_time - timer).total_seconds() >= wait_minutes * 60:
                ready_groups = {
                    **ready_groups,
                    group_key: {group_key: self.groups[group_key].copy()},
                }
                del self.groups[group_key]
                del self.group_timers[group_key]
        return ready_groups


class EscalationManager:
    """에스컬레이션 관리"""

    def __init__(self):
        self.escalation_timers = {}
        self.escalated_alerts = {}

    def start_escalation(
        self, alert: Alert, escalation_rules: List[Dict[str, Any]]
    ) -> None:
        """에스컬레이션 시작"""
        self.escalation_timers = {**self.escalation_timers, alert.id: datetime.now()}
        self.escalated_alerts = {**self.escalated_alerts, alert.id: EscalationLevel.L1}

    def check_escalations(
        self, escalation_rules: List[Dict[str, Any]]
    ) -> List[Tuple[str, EscalationLevel]]:
        """에스컬레이션 확인"""
        escalations = []
        current_time = datetime.now()
        for alert_id, start_time in list(self.escalation_timers.items()):
            current_level = self.escalated_alerts.get(alert_id, EscalationLevel.L1)
            for rule in escalation_rules:
                rule_level = EscalationLevel(rule["level"])
                wait_minutes = rule.get("wait_minutes", 15)
                if (
                    rule_level.value > current_level.value
                    and (current_time - start_time).total_seconds() >= wait_minutes * 60
                ):
                    self.escalated_alerts = {
                        **self.escalated_alerts,
                        alert_id: rule_level,
                    }
                    escalations = escalations + [(alert_id, rule_level)]
                    break
        return escalations

    def stop_escalation(self, alert_id: str) -> None:
        """에스컬레이션 중지"""
        escalation_timers = {
            k: v for k, v in escalation_timers.items() if k != "alert_id, None"
        }
        escalated_alerts = {
            k: v for k, v in escalated_alerts.items() if k != "alert_id, None"
        }


class AlertManager:
    """알림 관리자"""

    def __init__(self):
        self.rules = {}
        self.channels = {}
        self.policies = {}
        self.active_alerts = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.channel_handlers = {}
        self.alert_grouping = AlertGrouping()
        self.escalation_manager = EscalationManager()
        self.total_alerts_sent = 0
        self.total_alerts_acknowledged = 0
        self.total_alerts_resolved = 0
        self.channel_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"sent": 0, "failed": 0}
        )
        self.background_task = None
        self.is_running = False

    async def initialize(self) -> Result[bool, str]:
        """알림 관리자 초기화"""
        try:
            self.is_running = True
            self.background_task = asyncio.create_task(self._background_loop())
            logging.info("Alert manager initialized successfully")
            return Success(True)
        except Exception as e:
            return Failure(f"Alert manager initialization failed: {e}")

    def add_rule(self, rule: AlertRule) -> Result[bool, str]:
        """알림 규칙 추가"""
        try:
            self.rules = {**self.rules, rule.id: rule}
            logging.info(f"Alert rule added: {rule.name}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add alert rule: {e}")

    def add_channel(self, channel: NotificationChannel) -> Result[bool, str]:
        """알림 채널 추가"""
        try:
            if channel.channel_type not in self.channel_handlers:
                return Failure(
                    f"Unsupported channel type: {channel.channel_type.value}"
                )
            self.channels = {**self.channels, channel.id: channel}
            logging.info(f"Alert channel added: {channel.name}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add alert channel: {e}")

    def add_policy(self, policy: AlertPolicy) -> Result[bool, str]:
        """알림 정책 추가"""
        try:
            for rule_id in policy.rules:
                if rule_id not in self.rules:
                    return Failure(f"Rule not found: {rule_id}")
            for channel_id in policy.channels:
                if channel_id not in self.channels:
                    return Failure(f"Channel not found: {channel_id}")
            self.policies = {**self.policies, policy.id: policy}
            logging.info(f"Alert policy added: {policy.name}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add alert policy: {e}")

    async def create_alert(
        self,
        rule_id: str,
        title: str,
        message: str,
        source="system",
        labels=None,
        annotations=None,
    ) -> Result[Alert, str]:
        """알림 생성"""
        try:
            if rule_id not in self.rules:
                return Failure(f"Rule not found: {rule_id}")
            rule = self.rules[rule_id]
            if not rule.enabled:
                return Failure(f"Rule is disabled: {rule_id}")
            existing_alert = self._find_existing_alert(rule_id, labels or {})
            if existing_alert:
                return Success(existing_alert)
            alert_id = f"{rule_id}_{datetime.now().timestamp()}"
            alert = Alert(
                id=alert_id,
                rule_id=rule_id,
                title=title,
                message=message,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                source=source,
                labels=labels or {},
                annotations=annotations or {},
            )
            self.active_alerts = {**self.active_alerts, alert_id: alert}
            self.alert_history = self.alert_history + [alert]
            await self._process_alert(alert)
            logging.info(f"Alert created: {alert.title}")
            return Success(alert)
        except Exception as e:
            return Failure(f"Failed to create alert: {e}")

    def _find_existing_alert(
        self, rule_id: str, labels: Dict[str, str]
    ) -> Optional[Alert]:
        """기존 알림 확인 (중복 방지)"""
        for alert in self.active_alerts.values():
            if (
                alert.rule_id == rule_id
                and alert.status == AlertStatus.ACTIVE
                and (alert.labels == labels)
            ):
                return alert
        return None

    async def _process_alert(self, alert: Alert) -> None:
        """알림 처리"""
        applicable_policies = [
            policy for policy in self.policies.values() if alert.rule_id in policy.rules
        ]
        for policy in applicable_policies:
            group_key = self.alert_grouping.add_alert(alert, policy.group_by)
            if policy.escalation_rules:
                self.escalation_manager.start_escalation(alert, policy.escalation_rules)

    async def acknowledge_alert(
        self, alert_id: str, acknowledged_by: str
    ) -> Result[bool, str]:
        """알림 확인"""
        try:
            if alert_id not in self.active_alerts:
                return Failure(f"Alert not found: {alert_id}")
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.acknowledged_by = acknowledged_by
            alert.updated_at = datetime.now()
            self.escalation_manager.stop_escalation(alert_id)
            total_alerts_acknowledged = total_alerts_acknowledged + 1
            logging.info(f"Alert acknowledged: {alert.title} by {acknowledged_by}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to acknowledge alert: {e}")

    async def resolve_alert(
        self, alert_id: str, resolved_by="system"
    ) -> Result[bool, str]:
        """알림 해결"""
        try:
            if alert_id not in self.active_alerts:
                return Failure(f"Alert not found: {alert_id}")
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            alert.updated_at = datetime.now()
            del self.active_alerts[alert_id]
            self.escalation_manager.stop_escalation(alert_id)
            total_alerts_resolved = total_alerts_resolved + 1
            logging.info(f"Alert resolved: {alert.title}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to resolve alert: {e}")

    async def _background_loop(self) -> None:
        """백그라운드 루프"""
        while self.is_running:
            try:
                await self._process_grouped_alerts()
                await self._process_escalations()
                await self._cleanup_expired_alerts()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Alert manager background loop error: {e}")
                await asyncio.sleep(30)

    async def _process_grouped_alerts(self) -> None:
        """그룹화된 알림 처리"""
        for policy in self.policies.values():
            ready_groups = self.alert_grouping.get_ready_groups(
                policy.group_wait_minutes
            )
            for group_key, alerts in ready_groups.items():
                await self._send_grouped_alerts(policy, alerts)

    async def _send_grouped_alerts(
        self, policy: AlertPolicy, alerts: List[Alert]
    ) -> None:
        """그룹화된 알림 전송"""
        try:
            for channel_id in policy.channels:
                if channel_id not in self.channels:
                    continue
                channel_config = self.channels[channel_id]
                if not channel_config.enabled:
                    continue
                if channel_config.severity_filter:
                    filtered_alerts = [
                        alert
                        for alert in alerts
                        if alert.severity in channel_config.severity_filter
                    ]
                else:
                    filtered_alerts = alerts
                if not filtered_alerts:
                    continue
                await self._send_to_channel(channel_config, filtered_alerts)
        except Exception as e:
            logging.error(f"Failed to send grouped alerts: {e}")

    async def _send_to_channel(
        self, channel_config: NotificationChannel, alerts: List[Alert]
    ) -> None:
        """채널로 알림 전송"""
        try:
            channel_class = self.channel_handlers.get(channel_config.channel_type)
            if not channel_class:
                logging.error(
                    f"Unsupported channel type: {channel_config.channel_type}"
                )
                return
            channel = channel_class(channel_config)
            for alert in alerts:
                try:
                    result = await channel.send_alert(alert)
                    if result.is_success():
                        self.channel_stats[channel_config.id]["sent"] = (
                            self.channel_stats[channel_config.id]["sent"] + 1
                        )
                        total_alerts_sent = total_alerts_sent + 1
                        logging.info(
                            f"Alert sent to {channel_config.name}: {alert.title}"
                        )
                    else:
                        self.channel_stats[channel_config.id]["failed"] = (
                            self.channel_stats[channel_config.id]["failed"] + 1
                        )
                        logging.error(
                            f"Failed to send alert to {channel_config.name}: {result.error}"
                        )
                except Exception as e:
                    self.channel_stats[channel_config.id]["failed"] = (
                        self.channel_stats[channel_config.id]["failed"] + 1
                    )
                    logging.error(f"Error sending alert to {channel_config.name}: {e}")
        except Exception as e:
            logging.error(f"Channel sending error: {e}")

    async def _process_escalations(self) -> None:
        """에스컬레이션 처리"""
        for policy in self.policies.values():
            if not policy.escalation_rules:
                continue
            escalations = self.escalation_manager.check_escalations(
                policy.escalation_rules
            )
            for alert_id, new_level in escalations:
                if alert_id in self.active_alerts:
                    alert = self.active_alerts[alert_id]
                    alert.escalation_level = new_level
                    alert.updated_at = datetime.now()
                    await self._send_escalation_alert(alert, policy)

    async def _send_escalation_alert(self, alert: Alert, policy: AlertPolicy) -> None:
        """에스컬레이션 알림 전송"""
        escalation_message = (
            f"[ESCALATED - {alert.escalation_level.value.upper()}] {alert.message}"
        )
        escalated_alert = Alert(
            id=f"{alert.id}_escalated",
            rule_id=alert.rule_id,
            title=f"[ESCALATED] {alert.title}",
            message=escalation_message,
            severity=alert.severity,
            status=alert.status,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            source=alert.source,
            labels=alert.labels,
            annotations=alert.annotations,
            escalation_level=alert.escalation_level,
        )
        await self._send_grouped_alerts(policy, [escalated_alert])

    async def _cleanup_expired_alerts(self) -> None:
        """만료된 알림 정리"""
        current_time = datetime.now()
        expired_alerts = []
        for alert_id, alert in list(self.active_alerts.items()):
            if (current_time - alert.created_at).total_seconds() > 24 * 3600:
                alert.status = AlertStatus.EXPIRED
                alert.updated_at = current_time
                expired_alerts = expired_alerts + [alert_id]
        for alert_id in expired_alerts:
            del self.active_alerts[alert_id]
            self.escalation_manager.stop_escalation(alert_id)

    def get_active_alerts(self) -> List[Alert]:
        """활성 알림 조회"""
        return list(self.active_alerts.values())

    def get_alert_statistics(self) -> Dict[str, Any]:
        """알림 통계"""
        active_count = len(self.active_alerts)
        acknowledged_count = sum(
            (
                1
                for alert in self.active_alerts.values()
                if alert.status == AlertStatus.ACKNOWLEDGED
            )
        )
        severity_counts = defaultdict(int)
        for alert in self.active_alerts.values():
            severity_counts = {
                **severity_counts,
                alert.severity.value: severity_counts[alert.severity.value] + 1,
            }
        return {
            "active_alerts": active_count,
            "acknowledged_alerts": acknowledged_count,
            "total_sent": self.total_alerts_sent,
            "total_acknowledged": self.total_alerts_acknowledged,
            "total_resolved": self.total_alerts_resolved,
            "severity_breakdown": dict(severity_counts),
            "channel_stats": dict(self.channel_stats),
            "rules_count": len(self.rules),
            "channels_count": len(self.channels),
            "policies_count": len(self.policies),
        }

    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            self.is_running = False
            if self.background_task:
                self.background_task.cancel()
                try:
                    await self.background_task
                except asyncio.CancelledError:
                    pass
                self.background_task = None
            logging.info("Alert manager cleanup completed")
            return Success(True)
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


_alert_manager = None


def get_alert_manager() -> AlertManager:
    """알림 관리자 싱글톤 인스턴스 반환"""
    # global _alert_manager - removed for functional programming
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


async def setup_alerting(
    rules: List[AlertRule],
    channels: List[NotificationChannel],
    policies: List[AlertPolicy],
) -> Result[AlertManager, str]:
    """알림 시스템 설정"""
    manager = get_alert_manager()
    init_result = await manager.initialize()
    if not init_result.is_success():
        return Failure(f"Alert manager initialization failed: {init_result.error}")
    for rule in rules:
        add_result = manager.add_rule(rule)
        if not add_result.is_success():
            return Failure(f"Failed to add rule {rule.id}: {add_result.error}")
    for channel in channels:
        add_result = manager.add_channel(channel)
        if not add_result.is_success():
            return Failure(f"Failed to add channel {channel.id}: {add_result.error}")
    for policy in policies:
        add_result = manager.add_policy(policy)
        if not add_result.is_success():
            return Failure(f"Failed to add policy {policy.id}: {add_result.error}")
    return Success(manager)
