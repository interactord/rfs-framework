"""
Production Monitor for RFS Framework

프로덕션 환경 실시간 모니터링 시스템
- 시스템 메트릭 수집 및 분석
- 성능 지표 모니터링
- 임계값 기반 알림 트리거
- 대시보드 데이터 제공
"""

import asyncio
import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import psutil

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


class SystemStatus(Enum):
    """시스템 상태"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"
    UNKNOWN = "unknown"


class ServiceHealth(Enum):
    """서비스 헬스 상태"""

    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


@dataclass
class MonitoringThresholds:
    """모니터링 임계값"""

    cpu_warning_percent: float = 70.0
    cpu_critical_percent: float = 90.0
    memory_warning_percent: float = 80.0
    memory_critical_percent: float = 95.0
    disk_warning_percent: float = 85.0
    disk_critical_percent: float = 95.0
    response_time_warning_ms: float = 2000.0
    response_time_critical_ms: float = 5000.0
    error_rate_warning_percent: float = 1.0
    error_rate_critical_percent: float = 5.0
    uptime_warning_percent: float = 99.0
    uptime_critical_percent: float = 95.0


@dataclass
class ProductionMetrics:
    """프로덕션 메트릭"""

    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_available_gb: float
    network_in_mbps: float
    network_out_mbps: float
    request_count: int
    error_count: int
    avg_response_time_ms: float
    active_connections: int
    queue_size: int
    system_status: SystemStatus
    service_health: ServiceHealth
    uptime_seconds: float
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """모니터링 설정"""

    thresholds: MonitoringThresholds = field(default_factory=MonitoringThresholds)
    collection_interval_seconds: float = 30.0
    retention_days = 30
    enable_system_monitoring = True
    enable_application_monitoring = True
    enable_network_monitoring = True
    enable_custom_metrics = True
    alert_cooldown_seconds: float = 300.0
    max_metrics_history = 2880


class MetricsCollector:
    """메트릭 수집기"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.custom_collectors: Dict[str, Callable[[], float]] = {}
        self.network_baseline: Dict[str, Any] = {}
        self.process_start_time = time.time()
        self._initialize_network_baseline()

    def _initialize_network_baseline(self) -> None:
        """네트워크 베이스라인 초기화"""
        try:
            net_io = psutil.net_io_counters()
            self.network_baseline = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "last_update": time.time(),
            }
        except Exception:
            self.network_baseline = {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "last_update": time.time(),
            }

    def register_custom_collector(
        self, name: str, collector: Callable[[], float]
    ) -> None:
        """커스텀 메트릭 수집기 등록"""
        self.custom_collectors = {**self.custom_collectors, name: collector}

    async def collect_metrics(self) -> Result[ProductionMetrics, str]:
        """메트릭 수집"""
        try:
            metrics_data = {"timestamp": datetime.now(), "custom_metrics": {}}
            if self.config.enable_system_monitoring:
                system_metrics = await self._collect_system_metrics()
                metrics_data.update(system_metrics)
            if self.config.enable_application_monitoring:
                app_metrics = await self._collect_application_metrics()
                metrics_data.update(app_metrics)
            if self.config.enable_network_monitoring:
                network_metrics = await self._collect_network_metrics()
                metrics_data.update(network_metrics)
            if self.config.enable_custom_metrics:
                custom_metrics = await self._collect_custom_metrics()
                metrics_data = {
                    **metrics_data,
                    "custom_metrics": {"custom_metrics": custom_metrics},
                }
            system_status = self._determine_system_status(metrics_data)
            service_health = self._determine_service_health(metrics_data)
            metrics_data = {
                **metrics_data,
                **{
                    "system_status": system_status,
                    "service_health": service_health,
                    "uptime_seconds": time.time() - self.process_start_time,
                },
            }
            # 기본값 설정
            default_values = {
                "timestamp": datetime.now(),
                "cpu_usage_percent": 0.0,
                "memory_usage_percent": 0.0,
                "memory_available_mb": 0.0,
                "disk_usage_percent": 0.0,
                "disk_available_gb": 0.0,
                "network_in_mbps": 0.0,
                "network_out_mbps": 0.0,
                "request_count": 0,
                "error_count": 0,
                "avg_response_time_ms": 0.0,
                "active_connections": 0,
                "queue_size": 0,
                "system_status": SystemStatus.UNKNOWN,
                "service_health": ServiceHealth.UNKNOWN,
                "uptime_seconds": 0.0,
                "custom_metrics": {},
            }

            # 기본값과 수집된 메트릭 병합
            merged_metrics = {**default_values, **metrics_data}

            # ProductionMetrics 생성
            metrics = ProductionMetrics(
                **{
                    k: v
                    for k, v in merged_metrics.items()
                    if k in ProductionMetrics.__dataclass_fields__
                }
            )
            return Success(metrics)
        except Exception as e:
            return Failure(f"메트릭 수집 실패: {e}")

    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """시스템 메트릭 수집"""
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            memory_available = memory.available / (1024 * 1024)
            disk = psutil.disk_usage("/")
            disk_usage = disk.used / disk.total * 100
            disk_available = disk.free / (1024 * 1024 * 1024)
            return {
                "cpu_usage_percent": cpu_usage,
                "memory_usage_percent": memory_usage,
                "memory_available_mb": memory_available,
                "disk_usage_percent": disk_usage,
                "disk_available_gb": disk_available,
            }
        except Exception:
            return {
                "cpu_usage_percent": 0.0,
                "memory_usage_percent": 0.0,
                "memory_available_mb": 0.0,
                "disk_usage_percent": 0.0,
                "disk_available_gb": 0.0,
            }

    async def _collect_application_metrics(self) -> Dict[str, Any]:
        """애플리케이션 메트릭 수집 (플레이스홀더)"""
        return {
            "request_count": 100,
            "error_count": 1,
            "avg_response_time_ms": 150.0,
            "active_connections": 25,
            "queue_size": 5,
        }

    async def _collect_network_metrics(self) -> Dict[str, Any]:
        """네트워크 메트릭 수집"""
        try:
            net_io = psutil.net_io_counters()
            current_time = time.time()
            time_diff = current_time - self.network_baseline["last_update"]
            if time_diff > 0:
                bytes_sent_diff = (
                    net_io.bytes_sent - self.network_baseline["bytes_sent"]
                )
                bytes_recv_diff = (
                    net_io.bytes_recv - self.network_baseline["bytes_recv"]
                )
                network_in_mbps = bytes_recv_diff * 8 / (time_diff * 1024 * 1024)
                network_out_mbps = bytes_sent_diff * 8 / (time_diff * 1024 * 1024)
            else:
                network_in_mbps = 0.0
                network_out_mbps = 0.0
            self.network_baseline = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "last_update": current_time,
            }
            return {
                "network_in_mbps": max(0.0, network_in_mbps),
                "network_out_mbps": max(0.0, network_out_mbps),
            }
        except Exception:
            return {"network_in_mbps": 0.0, "network_out_mbps": 0.0}

    async def _collect_custom_metrics(self) -> Dict[str, float]:
        """커스텀 메트릭 수집"""
        custom_metrics = {}
        for name, collector in self.custom_collectors.items():
            try:
                value = collector()
                if type(value).__name__ in ["int", "float"]:
                    custom_metrics[name] = {name: float(value)}
            except Exception as e:
                logging.warning(f"Failed to collect custom metric '{name}': {e}")
                custom_metrics[name] = {name: 0.0}
        return custom_metrics

    def _determine_system_status(self, metrics_data: Dict[str, Any]) -> SystemStatus:
        """시스템 상태 결정"""
        thresholds = self.config.thresholds
        cpu = metrics_data.get("cpu_usage_percent", 0)
        memory = metrics_data.get("memory_usage_percent", 0)
        disk = metrics_data.get("disk_usage_percent", 0)
        if (
            cpu >= thresholds.cpu_critical_percent
            or memory >= thresholds.memory_critical_percent
            or disk >= thresholds.disk_critical_percent
        ):
            return SystemStatus.CRITICAL
        if (
            cpu >= thresholds.cpu_warning_percent
            or memory >= thresholds.memory_warning_percent
            or disk >= thresholds.disk_warning_percent
        ):
            return SystemStatus.WARNING
        return SystemStatus.HEALTHY

    def _determine_service_health(self, metrics_data: Dict[str, Any]) -> ServiceHealth:
        """서비스 헬스 상태 결정"""
        thresholds = self.config.thresholds
        response_time = metrics_data.get("avg_response_time_ms", 0)
        error_count = metrics_data.get("error_count", 0)
        request_count = metrics_data.get("request_count", 1)
        error_rate = error_count / max(1, request_count) * 100
        if error_rate >= thresholds.error_rate_critical_percent:
            return ServiceHealth.DOWN
        if (
            response_time >= thresholds.response_time_critical_ms
            or error_rate >= thresholds.error_rate_warning_percent
        ):
            return ServiceHealth.DEGRADED
        return ServiceHealth.UP


class AlertGenerator:
    """알림 생성기"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.last_alerts: Dict[str, float] = {}
        self.alert_callbacks: List[Callable] = []

    def register_alert_callback(self, callback: Callable) -> None:
        """알림 콜백 등록"""
        self.alert_callbacks = self.alert_callbacks + [callback]

    def check_thresholds(self, metrics: ProductionMetrics) -> List[Dict[str, Any]]:
        """임계값 확인 및 알림 생성"""
        alerts = []
        thresholds = self.config.thresholds
        current_time = datetime.now()
        alerts = alerts + self._check_cpu_thresholds(metrics, thresholds, current_time)
        alerts = alerts + self._check_memory_thresholds(
            metrics, thresholds, current_time
        )
        alerts = alerts + self._check_disk_thresholds(metrics, thresholds, current_time)
        alerts = alerts + self._check_response_time_thresholds(
            metrics, thresholds, current_time
        )
        alerts = alerts + self._check_error_rate_thresholds(
            metrics, thresholds, current_time
        )
        alerts = alerts + self._check_system_status_alerts(metrics, current_time)
        for alert in alerts:
            self._trigger_alert_callbacks(alert)
        return alerts

    def _check_cpu_thresholds(
        self,
        metrics: ProductionMetrics,
        thresholds: MonitoringThresholds,
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """CPU 임계값 확인"""
        alerts = []
        cpu_usage = metrics.cpu_usage_percent
        if cpu_usage >= thresholds.cpu_critical_percent:
            alert_key = "cpu_critical"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "cpu_usage",
                        "severity": AlertSeverity.CRITICAL,
                        "message": f"Critical CPU usage: {cpu_usage:.1f}%",
                        "value": cpu_usage,
                        "threshold": thresholds.cpu_critical_percent,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        elif cpu_usage >= thresholds.cpu_warning_percent:
            alert_key = "cpu_warning"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "cpu_usage",
                        "severity": AlertSeverity.HIGH,
                        "message": f"High CPU usage: {cpu_usage:.1f}%",
                        "value": cpu_usage,
                        "threshold": thresholds.cpu_warning_percent,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        return alerts

    def _check_memory_thresholds(
        self,
        metrics: ProductionMetrics,
        thresholds: MonitoringThresholds,
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """메모리 임계값 확인"""
        alerts = []
        memory_usage = metrics.memory_usage_percent
        if memory_usage >= thresholds.memory_critical_percent:
            alert_key = "memory_critical"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "memory_usage",
                        "severity": AlertSeverity.CRITICAL,
                        "message": f"Critical memory usage: {memory_usage:.1f}%",
                        "value": memory_usage,
                        "threshold": thresholds.memory_critical_percent,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        elif memory_usage >= thresholds.memory_warning_percent:
            alert_key = "memory_warning"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "memory_usage",
                        "severity": AlertSeverity.HIGH,
                        "message": f"High memory usage: {memory_usage:.1f}%",
                        "value": memory_usage,
                        "threshold": thresholds.memory_warning_percent,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        return alerts

    def _check_disk_thresholds(
        self,
        metrics: ProductionMetrics,
        thresholds: MonitoringThresholds,
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """디스크 임계값 확인"""
        alerts = []
        disk_usage = metrics.disk_usage_percent
        if disk_usage >= thresholds.disk_critical_percent:
            alert_key = "disk_critical"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "disk_usage",
                        "severity": AlertSeverity.CRITICAL,
                        "message": f"Critical disk usage: {disk_usage:.1f}%",
                        "value": disk_usage,
                        "threshold": thresholds.disk_critical_percent,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        elif disk_usage >= thresholds.disk_warning_percent:
            alert_key = "disk_warning"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "disk_usage",
                        "severity": AlertSeverity.HIGH,
                        "message": f"High disk usage: {disk_usage:.1f}%",
                        "value": disk_usage,
                        "threshold": thresholds.disk_warning_percent,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        return alerts

    def _check_response_time_thresholds(
        self,
        metrics: ProductionMetrics,
        thresholds: MonitoringThresholds,
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """응답 시간 임계값 확인"""
        alerts = []
        response_time = metrics.avg_response_time_ms
        if response_time >= thresholds.response_time_critical_ms:
            alert_key = "response_time_critical"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "response_time",
                        "severity": AlertSeverity.CRITICAL,
                        "message": f"Critical response time: {response_time:.1f}ms",
                        "value": response_time,
                        "threshold": thresholds.response_time_critical_ms,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        elif response_time >= thresholds.response_time_warning_ms:
            alert_key = "response_time_warning"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "response_time",
                        "severity": AlertSeverity.HIGH,
                        "message": f"High response time: {response_time:.1f}ms",
                        "value": response_time,
                        "threshold": thresholds.response_time_warning_ms,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        return alerts

    def _check_error_rate_thresholds(
        self,
        metrics: ProductionMetrics,
        thresholds: MonitoringThresholds,
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """에러율 임계값 확인"""
        alerts = []
        if metrics.request_count > 0:
            error_rate = metrics.error_count / metrics.request_count * 100
            if error_rate >= thresholds.error_rate_critical_percent:
                alert_key = "error_rate_critical"
                if self._should_send_alert(alert_key, current_time):
                    alerts = alerts + [
                        {
                            "type": "error_rate",
                            "severity": AlertSeverity.CRITICAL,
                            "message": f"Critical error rate: {error_rate:.1f}%",
                            "value": error_rate,
                            "threshold": thresholds.error_rate_critical_percent,
                            "timestamp": current_time,
                            "metrics": metrics,
                        }
                    ]
            elif error_rate >= thresholds.error_rate_warning_percent:
                alert_key = "error_rate_warning"
                if self._should_send_alert(alert_key, current_time):
                    alerts = alerts + [
                        {
                            "type": "error_rate",
                            "severity": AlertSeverity.HIGH,
                            "message": f"High error rate: {error_rate:.1f}%",
                            "value": error_rate,
                            "threshold": thresholds.error_rate_warning_percent,
                            "timestamp": current_time,
                            "metrics": metrics,
                        }
                    ]
        return alerts

    def _check_system_status_alerts(
        self, metrics: ProductionMetrics, current_time: datetime
    ) -> List[Dict[str, Any]]:
        """시스템 상태 알림 확인"""
        alerts = []
        if metrics.system_status == SystemStatus.CRITICAL:
            alert_key = "system_critical"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "system_status",
                        "severity": AlertSeverity.CRITICAL,
                        "message": "System status is CRITICAL",
                        "value": metrics.system_status.value,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        elif metrics.system_status == SystemStatus.WARNING:
            alert_key = "system_warning"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "system_status",
                        "severity": AlertSeverity.HIGH,
                        "message": "System status is WARNING",
                        "value": metrics.system_status.value,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        if metrics.service_health == ServiceHealth.DOWN:
            alert_key = "service_down"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "service_health",
                        "severity": AlertSeverity.CRITICAL,
                        "message": "Service is DOWN",
                        "value": metrics.service_health.value,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        elif metrics.service_health == ServiceHealth.DEGRADED:
            alert_key = "service_degraded"
            if self._should_send_alert(alert_key, current_time):
                alerts = alerts + [
                    {
                        "type": "service_health",
                        "severity": AlertSeverity.HIGH,
                        "message": "Service is DEGRADED",
                        "value": metrics.service_health.value,
                        "timestamp": current_time,
                        "metrics": metrics,
                    }
                ]
        return alerts

    def _should_send_alert(self, alert_key: str, current_time: datetime) -> bool:
        """알림 쿨다운 확인"""
        if alert_key in self.last_alerts:
            time_diff = (current_time - self.last_alerts[alert_key]).total_seconds()
            if time_diff < self.config.alert_cooldown_seconds:
                return False
        self.last_alerts = {**self.last_alerts, alert_key: current_time}
        return True

    def _trigger_alert_callbacks(self, alert: Dict[str, Any]) -> None:
        """알림 콜백 실행"""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(alert))
                else:
                    callback(alert)
            except Exception as e:
                logging.error(f"Alert callback failed: {e}")


class ProductionMonitor:
    """프로덕션 모니터"""

    def __init__(self, config=None):
        self.config = config or MonitoringConfig()
        self.metrics_collector = MetricsCollector(self.config)
        self.alert_generator = AlertGenerator(self.config)
        self.monitoring_task = None
        self.metrics_history: deque = deque(maxlen=self.config.max_metrics_history)
        self.alerts_history: deque = deque(maxlen=1000)
        self.is_running = False
        self.total_metrics_collected = 0
        self.total_alerts_generated = 0
        self.start_time = datetime.now()

    async def initialize(self) -> Result[bool, str]:
        """모니터 초기화"""
        try:
            initial_metrics = await self.metrics_collector.collect_metrics()
            if initial_metrics.is_success():
                self.metrics_history = self.metrics_history + [initial_metrics.unwrap()]
                total_metrics_collected = total_metrics_collected + 1
            logging.info("Production monitor initialized successfully")
            return Success(True)
        except Exception as e:
            return Failure(f"Production monitor initialization failed: {e}")

    async def collect_metrics(self) -> Result[ProductionMetrics, str]:
        """메트릭 수집 - MetricsCollector에 위임"""
        return await self.metrics_collector.collect_metrics()

    async def start_monitoring(self) -> Result[bool, str]:
        """모니터링 시작"""
        if self.is_running:
            return Success(True)
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            logging.info("Production monitoring started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start production monitoring: {e}")

    async def stop_monitoring(self) -> Result[bool, str]:
        """모니터링 중지"""
        try:
            self.is_running = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            logging.info("Production monitoring stopped")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop production monitoring: {e}")

    async def _monitoring_loop(self) -> None:
        """모니터링 루프"""
        while self.is_running:
            try:
                metrics_result = await self.metrics_collector.collect_metrics()
                if metrics_result.is_success():
                    metrics = metrics_result.unwrap()
                    self.metrics_history = self.metrics_history + [metrics]
                    total_metrics_collected = total_metrics_collected + 1
                    alerts = self.alert_generator.check_thresholds(metrics)
                    for alert in alerts:
                        self.alerts_history = self.alerts_history + [alert]
                        total_alerts_generated = total_alerts_generated + 1
                await asyncio.sleep(self.config.collection_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.config.collection_interval_seconds)

    def register_custom_metric_collector(
        self, name: str, collector: Callable[[], float]
    ) -> None:
        """커스텀 메트릭 수집기 등록"""
        self.metrics_collector.register_custom_collector(name, collector)

    def register_alert_callback(self, callback: Callable) -> None:
        """알림 콜백 등록"""
        self.alert_generator.register_alert_callback(callback)

    def get_current_metrics(self) -> Optional[ProductionMetrics]:
        """현재 메트릭 조회"""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None

    def get_metrics_history(self, minutes=60) -> List[ProductionMetrics]:
        """메트릭 이력 조회"""
        if not self.metrics_history:
            return []
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]

    def get_recent_alerts(self, count=10) -> List[Dict[str, Any]]:
        """최근 알림 조회"""
        return list(self.alerts_history)[-count:]

    def get_system_summary(self) -> Dict[str, Any]:
        """시스템 요약 정보"""
        current_metrics = self.get_current_metrics()
        if not current_metrics:
            return {}
        recent_alerts = self.get_recent_alerts(5)
        uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        return {
            "system_status": current_metrics.system_status.value,
            "service_health": current_metrics.service_health.value,
            "uptime_hours": uptime_hours,
            "cpu_usage_percent": current_metrics.cpu_usage_percent,
            "memory_usage_percent": current_metrics.memory_usage_percent,
            "disk_usage_percent": current_metrics.disk_usage_percent,
            "avg_response_time_ms": current_metrics.avg_response_time_ms,
            "total_metrics_collected": self.total_metrics_collected,
            "total_alerts_generated": self.total_alerts_generated,
            "recent_alerts_count": len(recent_alerts),
            "monitoring_active": self.is_running,
        }

    def get_performance_trends(self, hours=24) -> Dict[str, Any]:
        """성능 트렌드 분석"""
        metrics_list = self.get_metrics_history(hours * 60)
        if len(metrics_list) < 2:
            return {}
        cpu_values = [m.cpu_usage_percent for m in metrics_list]
        memory_values = [m.memory_usage_percent for m in metrics_list]
        response_values = [m.avg_response_time_ms for m in metrics_list]
        return {
            "cpu_trend": {
                "min": min(cpu_values),
                "max": max(cpu_values),
                "avg": sum(cpu_values) / len(cpu_values),
                "current": cpu_values[-1],
            },
            "memory_trend": {
                "min": min(memory_values),
                "max": max(memory_values),
                "avg": sum(memory_values) / len(memory_values),
                "current": memory_values[-1],
            },
            "response_time_trend": {
                "min": min(response_values),
                "max": max(response_values),
                "avg": sum(response_values) / len(response_values),
                "current": response_values[-1],
            },
            "sample_count": len(metrics_list),
            "time_range_hours": hours,
        }

    async def get_health_report(self) -> Dict[str, Any]:
        """헬스 리포트 생성"""
        current_metrics = self.get_current_metrics()
        if not current_metrics:
            return {"status": "unknown", "message": "No metrics available"}
        performance_trends = self.get_performance_trends(1)
        recent_alerts = self.get_recent_alerts(10)
        health_score = self._calculate_health_score(current_metrics, recent_alerts)
        return {
            "timestamp": datetime.now().isoformat(),
            "health_score": health_score,
            "system_status": current_metrics.system_status.value,
            "service_health": current_metrics.service_health.value,
            "current_metrics": {
                "cpu_usage": current_metrics.cpu_usage_percent,
                "memory_usage": current_metrics.memory_usage_percent,
                "disk_usage": current_metrics.disk_usage_percent,
                "response_time": current_metrics.avg_response_time_ms,
                "uptime": current_metrics.uptime_seconds,
            },
            "performance_trends": performance_trends,
            "recent_alerts": recent_alerts,
            "recommendations": self._generate_recommendations(
                current_metrics, recent_alerts
            ),
        }

    def _calculate_health_score(
        self, metrics: ProductionMetrics, recent_alerts: List[Dict[str, Any]]
    ) -> float:
        """헬스 점수 계산"""
        score = 100.0
        if metrics.system_status == SystemStatus.CRITICAL:
            score = score - 50
        elif metrics.system_status == SystemStatus.WARNING:
            score = score - 25
        if metrics.service_health == ServiceHealth.DOWN:
            score = score - 40
        elif metrics.service_health == ServiceHealth.DEGRADED:
            score = score - 20
        if metrics.cpu_usage_percent > 90:
            score = score - 15
        elif metrics.cpu_usage_percent > 70:
            score = score - 5
        if metrics.memory_usage_percent > 95:
            score = score - 15
        elif metrics.memory_usage_percent > 80:
            score = score - 5
        critical_alerts = [
            a for a in recent_alerts if a.get("severity") == AlertSeverity.CRITICAL
        ]
        score = score - len(critical_alerts) * 5
        return max(0.0, min(100.0, score))

    def _generate_recommendations(
        self, metrics: ProductionMetrics, recent_alerts: List[Dict[str, Any]]
    ) -> List[str]:
        """추천사항 생성"""
        recommendations = []
        if metrics.cpu_usage_percent > 80:
            recommendations = recommendations + [
                "High CPU usage detected - consider scaling up or optimizing processes"
            ]
        if metrics.memory_usage_percent > 90:
            recommendations = recommendations + [
                "High memory usage detected - check for memory leaks or increase memory allocation"
            ]
        if metrics.disk_usage_percent > 90:
            recommendations = recommendations + [
                "High disk usage detected - clean up unused files or increase storage capacity"
            ]
        if metrics.avg_response_time_ms > 2000:
            recommendations = recommendations + [
                "High response time detected - optimize database queries or add caching"
            ]
        if metrics.request_count > 0:
            error_rate = metrics.error_count / metrics.request_count * 100
            if error_rate > 1:
                recommendations = recommendations + [
                    f"High error rate ({error_rate:.1f}%) - investigate error logs and fix issues"
                ]
        critical_alerts = [
            a for a in recent_alerts if a.get("severity") == AlertSeverity.CRITICAL
        ]
        if critical_alerts:
            recommendations = recommendations + [
                f"Address {len(critical_alerts)} critical alerts immediately"
            ]
        return recommendations

    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            metrics_history = []
            alerts_history = []
            logging.info("Production monitor cleanup completed")
            return Success(True)
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


_production_monitor = None


def get_production_monitor(
    config=None,
) -> ProductionMonitor:
    """프로덕션 모니터 싱글톤 인스턴스 반환"""
    # global _production_monitor - removed for functional programming
    if _production_monitor is None:
        _production_monitor = ProductionMonitor(config)
    return _production_monitor


async def start_production_monitoring(
    config=None,
) -> Result[ProductionMonitor, str]:
    """프로덕션 모니터링 시작"""
    monitor = get_production_monitor(config)
    init_result = await monitor.initialize()
    if not init_result.is_success():
        return Failure(f"Monitor initialization failed: {init_result.error}")
    start_result = await monitor.start_monitoring()
    if not start_result.is_success():
        return Failure(f"Monitor start failed: {start_result.error}")
    return Success(monitor)
