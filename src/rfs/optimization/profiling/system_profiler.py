"""
RFS System Profiler (RFS v4.2)

시스템 리소스 모니터링 및 프로파일링
- CPU, 메모리, 디스크, 네트워크 사용량 추적
- 시스템 성능 메트릭 수집
- 실시간 리소스 모니터링
"""

import asyncio
import logging
import platform
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from ...core.result import Failure, Result, Success

logger = logging.getLogger(__name__)


@dataclass
class ResourceUsage:
    """리소스 사용량 정보"""

    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    network_io: Dict[str, int]
    process_count: int
    load_average: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_usage_percent": self.disk_usage_percent,
            "network_io": self.network_io,
            "process_count": self.process_count,
            "load_average": self.load_average,
        }


@dataclass
class SystemInfo:
    """시스템 정보"""

    platform: str
    platform_version: str
    processor: str
    cpu_count: int
    cpu_freq: Dict[str, float]
    memory_total: int
    disk_total: int
    boot_time: datetime
    python_version: str

    @classmethod
    def collect(cls) -> "SystemInfo":
        """시스템 정보 수집"""
        cpu_freq = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {}
        return cls(
            platform=platform.system(),
            platform_version=platform.release(),
            processor=platform.processor(),
            cpu_count=psutil.cpu_count(),
            cpu_freq=cpu_freq,
            memory_total=psutil.virtual_memory().total,
            disk_total=psutil.disk_usage("/").total,
            boot_time=datetime.fromtimestamp(psutil.boot_time()),
            python_version=platform.python_version(),
        )


@dataclass
class SystemMetrics:
    """시스템 메트릭"""

    system_info: SystemInfo
    resource_history: List[str] = field(default_factory=list)
    uptime: timedelta = field(default_factory=lambda: timedelta(0))

    def add_usage(self, usage: ResourceUsage):
        """리소스 사용량 추가"""
        self.resource_history = self.resource_history + [usage]
        if len(self.resource_history) > 1000:
            self.resource_history = self.resource_history[-1000:]
        self.uptime = datetime.now() - self.system_info.boot_time

    def get_recent_usage(self, minutes=10) -> List[ResourceUsage]:
        """최근 N분간의 사용량 반환"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            usage for usage in self.resource_history if usage.timestamp >= cutoff_time
        ]

    def get_average_usage(self, minutes=10) -> Optional[ResourceUsage]:
        """최근 N분간의 평균 사용량 반환"""
        recent = self.get_recent_usage(minutes)
        if not recent:
            return None
        avg_cpu = sum((u.cpu_percent for u in recent)) / len(recent)
        avg_memory = sum((u.memory_percent for u in recent)) / len(recent)
        avg_disk = sum((u.disk_usage_percent for u in recent)) / len(recent)
        avg_network = {
            "bytes_sent": sum((u.network_io.get("bytes_sent", 0) for u in recent))
            / len(recent),
            "bytes_recv": sum((u.network_io.get("bytes_recv", 0) for u in recent))
            / len(recent),
        }
        avg_processes = sum((u.process_count for u in recent)) / len(recent)
        return ResourceUsage(
            timestamp=datetime.now(),
            cpu_percent=avg_cpu,
            memory_percent=avg_memory,
            disk_usage_percent=avg_disk,
            network_io=avg_network,
            process_count=int(avg_processes),
            load_average=recent[-1].load_average if recent else None,
        )


class SystemProfiler:
    """시스템 프로파일러"""

    def __init__(self, collection_interval=1.0):
        self.collection_interval = collection_interval
        self.metrics = SystemMetrics(system_info=SystemInfo.collect())
        self.is_running = False
        self.collection_task = None
        self.start_time = datetime.now()
        self.alert_thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_usage_percent": 90.0,
        }
        self.alert_callbacks = []

    async def start(self) -> Result[bool, str]:
        """프로파일링 시작"""
        try:
            if self.is_running:
                return Failure("System profiler is already running")
            self.is_running = True
            self.start_time = datetime.now()
            self.collection_task = asyncio.create_task(self._collection_loop())
            logger.info("System profiler started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start system profiler: {str(e)}")

    async def stop(self) -> Result[bool, str]:
        """프로파일링 중지"""
        try:
            if not self.is_running:
                return Failure("System profiler is not running")
            self.is_running = False
            if self.collection_task:
                self.collection_task.cancel()
                try:
                    await self.collection_task
                except asyncio.CancelledError:
                    pass
                self.collection_task = None
            logger.info("System profiler stopped")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop system profiler: {str(e)}")

    async def _collection_loop(self):
        """리소스 사용량 수집 루프"""
        try:
            while self.is_running:
                usage = await self._collect_usage()
                if usage:
                    self.metrics.add_usage(usage)
                    await self._check_alerts(usage)
                await asyncio.sleep(self.collection_interval)
        except asyncio.CancelledError:
            logger.debug("System profiler collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in system profiler collection loop: {e}")

    async def _collect_usage(self) -> Optional[ResourceUsage]:
        """현재 리소스 사용량 수집"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            disk = psutil.disk_usage("/")
            disk_usage_percent = disk.used / disk.total * 100
            network = psutil.net_io_counters()
            network_io = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv,
            }
            process_count = len(psutil.pids())
            load_average = None
            if hasattr(psutil, "getloadavg"):
                try:
                    load_average = list(psutil.getloadavg())
                except (OSError, AttributeError):
                    pass
            return ResourceUsage(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage_percent=disk_usage_percent,
                network_io=network_io,
                process_count=process_count,
                load_average=load_average,
            )
        except Exception as e:
            logger.error(f"Failed to collect resource usage: {e}")
            return None

    async def _check_alerts(self, usage: ResourceUsage):
        """알림 조건 검사"""
        try:
            alerts = []
            if usage.cpu_percent > self.alert_thresholds["cpu_percent"]:
                alerts = alerts + [f"High CPU usage: {usage.cpu_percent:.1f}%"]
            if usage.memory_percent > self.alert_thresholds["memory_percent"]:
                alerts = alerts + [f"High memory usage: {usage.memory_percent:.1f}%"]
            if usage.disk_usage_percent > self.alert_thresholds["disk_usage_percent"]:
                alerts = alerts + [f"High disk usage: {usage.disk_usage_percent:.1f}%"]
            if alerts:
                for callback in self.alert_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alerts, usage)
                        else:
                            callback(alerts, usage)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")

    def add_alert_callback(self, callback: callable):
        """알림 콜백 추가"""
        self.alert_callbacks = self.alert_callbacks + [callback]

    def set_alert_thresholds(self, **thresholds):
        """알림 임계값 설정"""
        self.alert_thresholds = {**self.alert_thresholds, **thresholds}

    def get_current_usage(self) -> Optional[ResourceUsage]:
        """현재 리소스 사용량 반환"""
        if not self.metrics.resource_history:
            return None
        return self.metrics.resource_history[-1]

    def get_system_info(self) -> SystemInfo:
        """시스템 정보 반환"""
        return self.metrics.system_info

    def get_metrics(self) -> SystemMetrics:
        """전체 메트릭 반환"""
        return self.metrics

    def get_uptime(self) -> timedelta:
        """프로파일러 가동 시간 반환"""
        return datetime.now() - self.start_time

    async def get_performance_summary(self, minutes=10) -> Dict[str, Any]:
        """성능 요약 정보 반환"""
        try:
            current = self.get_current_usage()
            average = self.metrics.get_average_usage(minutes)
            recent = self.metrics.get_recent_usage(minutes)
            summary = {
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": self.get_uptime().total_seconds(),
                "system_info": self.metrics.system_info.__dict__,
                "current_usage": current.to_dict() if current else None,
                "average_usage": average.to_dict() if average else None,
                "data_points": len(recent),
                "collection_interval": self.collection_interval,
                "is_running": self.is_running,
                "alert_thresholds": self.alert_thresholds,
            }
            if len(recent) > 1:
                cpu_trend = "stable"
                memory_trend = "stable"
                if len(recent) >= 5:
                    recent_5 = recent[-5:]
                    cpu_values = [u.cpu_percent for u in recent_5]
                    memory_values = [u.memory_percent for u in recent_5]
                    if cpu_values[-1] > cpu_values[0] * 1.1:
                        cpu_trend = "increasing"
                    elif cpu_values[-1] < cpu_values[0] * 0.9:
                        cpu_trend = "decreasing"
                    if memory_values[-1] > memory_values[0] * 1.05:
                        memory_trend = "increasing"
                    elif memory_values[-1] < memory_values[0] * 0.95:
                        memory_trend = "decreasing"
                summary = {
                    **summary,
                    "trends": {"cpu": cpu_trend, "memory": memory_trend},
                }
            return summary
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}

    async def export_metrics(self, format="json") -> Result[Dict[str, Any], str]:
        """메트릭 내보내기"""
        try:
            if format == "json":
                data = {
                    "system_info": self.metrics.system_info.__dict__,
                    "resource_history": [
                        usage.to_dict() for usage in self.metrics.resource_history
                    ],
                    "uptime": self.metrics.uptime.total_seconds(),
                    "profiler_uptime": self.get_uptime().total_seconds(),
                    "export_timestamp": datetime.now().isoformat(),
                }
                return Success(data)
            else:
                return Failure(f"Unsupported export format: {format}")
        except Exception as e:
            return Failure(f"Failed to export metrics: {str(e)}")


def create_system_profiler(collection_interval: float = 1.0) -> SystemProfiler:
    """시스템 프로파일러 생성"""
    return SystemProfiler(collection_interval=collection_interval)


async def get_system_snapshot() -> ResourceUsage:
    """현재 시스템 스냅샷 반환"""
    profiler = SystemProfiler()
    usage = await profiler._collect_usage()
    return usage or ResourceUsage(
        timestamp=datetime.now(),
        cpu_percent=0.0,
        memory_percent=0.0,
        disk_usage_percent=0.0,
        network_io={},
        process_count=0,
    )
