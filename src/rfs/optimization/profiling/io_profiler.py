"""
RFS I/O Profiler (RFS v4.2)

I/O 성능 분석 및 프로파일링
- 디스크 I/O 모니터링
- 네트워크 I/O 추적
- 파일 시스템 사용량 분석
- I/O 병목 지점 탐지
"""

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from ...core.result import Failure, Result, Success

logger = logging.getLogger(__name__)


@dataclass
class DiskIOStats:
    """디스크 I/O 통계"""

    device: str
    read_count: int
    write_count: int
    read_bytes: int
    write_bytes: int
    read_time: int
    write_time: int
    busy_time: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "read_bytes": self.read_bytes,
            "write_bytes": self.write_bytes,
            "read_mb": self.read_bytes / 1024**2,
            "write_mb": self.write_bytes / 1024**2,
            "read_time_ms": self.read_time,
            "write_time_ms": self.write_time,
            "busy_time_ms": self.busy_time,
        }


@dataclass
class NetworkIOStats:
    """네트워크 I/O 통계"""

    interface: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface": self.interface,
            "bytes_sent": self.bytes_sent,
            "bytes_recv": self.bytes_recv,
            "mb_sent": self.bytes_sent / 1024**2,
            "mb_recv": self.bytes_recv / 1024**2,
            "packets_sent": self.packets_sent,
            "packets_recv": self.packets_recv,
            "errin": self.errin,
            "errout": self.errout,
            "dropin": self.dropin,
            "dropout": self.dropout,
        }


@dataclass
class FileSystemUsage:
    """파일 시스템 사용량"""

    mountpoint: str
    device: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mountpoint": self.mountpoint,
            "device": self.device,
            "fstype": self.fstype,
            "total_gb": self.total / 1024**3,
            "used_gb": self.used / 1024**3,
            "free_gb": self.free / 1024**3,
            "percent": self.percent,
        }


@dataclass
class ProcessIOInfo:
    """프로세스 I/O 정보"""

    pid: int
    name: str
    read_count: int
    write_count: int
    read_bytes: int
    write_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "name": self.name,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "read_mb": self.read_bytes / 1024**2,
            "write_mb": self.write_bytes / 1024**2,
        }


@dataclass
class IOSnapshot:
    """I/O 스냅샷"""

    timestamp: datetime
    disk_io: List[DiskIOStats]
    network_io: List[NetworkIOStats]
    filesystem_usage: List[FileSystemUsage]
    top_io_processes: List[ProcessIOInfo]
    total_disk_reads: int
    total_disk_writes: int
    total_network_sent: int
    total_network_recv: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "disk_io": [disk.to_dict() for disk in self.disk_io],
            "network_io": [net.to_dict() for net in self.network_io],
            "filesystem_usage": [fs.to_dict() for fs in self.filesystem_usage],
            "top_io_processes": [proc.to_dict() for proc in self.top_io_processes],
            "total_disk_reads_mb": self.total_disk_reads / 1024**2,
            "total_disk_writes_mb": self.total_disk_writes / 1024**2,
            "total_network_sent_mb": self.total_network_sent / 1024**2,
            "total_network_recv_mb": self.total_network_recv / 1024**2,
        }


@dataclass
class IOBottleneck:
    """I/O 병목 정보"""

    detection_time: datetime
    type: str
    description: str
    severity: str
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detection_time": self.detection_time.isoformat(),
            "type": self.type,
            "description": self.description,
            "severity": self.severity,
            "metrics": self.metrics,
        }


@dataclass
class IOMetrics:
    """I/O 메트릭"""

    snapshots: List[str] = field(default_factory=list)
    detected_bottlenecks: List[str] = field(default_factory=list)

    def add_snapshot(self, snapshot: IOSnapshot):
        """스냅샷 추가"""
        self.snapshots = self.snapshots + [snapshot]
        if len(self.snapshots) > 1000:
            self.snapshots = self.snapshots[-1000:]

    def get_recent_snapshots(self, minutes=10) -> List[IOSnapshot]:
        """최근 N분간의 스냅샷 반환"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            snapshot for snapshot in self.snapshots if snapshot.timestamp >= cutoff_time
        ]

    def calculate_io_rates(self, minutes=1) -> Dict[str, float]:
        """I/O 속도 계산 (초당)"""
        recent = self.get_recent_snapshots(minutes)
        if len(recent) < 2:
            return {}
        first = recent[0]
        last = recent[-1]
        time_diff = (last.timestamp - first.timestamp).total_seconds()
        if time_diff <= 0:
            return {}
        return {
            "disk_read_rate_mbps": (last.total_disk_reads - first.total_disk_reads)
            / 1024**2
            / time_diff,
            "disk_write_rate_mbps": (last.total_disk_writes - first.total_disk_writes)
            / 1024**2
            / time_diff,
            "network_send_rate_mbps": (
                last.total_network_sent - first.total_network_sent
            )
            / 1024**2
            / time_diff,
            "network_recv_rate_mbps": (
                last.total_network_recv - first.total_network_recv
            )
            / 1024**2
            / time_diff,
        }


class IOProfiler:
    """I/O 프로파일러"""

    def __init__(self, collection_interval=2.0, top_processes_count=10):
        self.collection_interval = collection_interval
        self.top_processes_count = top_processes_count
        self.metrics = IOMetrics()
        self.is_running = False
        self.collection_task = None
        self.start_time = datetime.now()
        self.bottleneck_thresholds = {
            "disk_usage_percent": 90.0,
            "disk_io_wait_time_ms": 100.0,
            "network_error_rate": 0.01,
            "filesystem_usage_percent": 95.0,
        }
        self.alert_callbacks = []
        self.prev_disk_counters: Optional[Dict[str, Any]] = None
        self.prev_network_counters: Optional[Dict[str, Any]] = None

    async def start(self) -> Result[bool, str]:
        """I/O 프로파일링 시작"""
        try:
            if self.is_running:
                return Failure("I/O profiler is already running")
            self.is_running = True
            self.start_time = datetime.now()
            self.collection_task = asyncio.create_task(self._collection_loop())
            logger.info("I/O profiler started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start I/O profiler: {str(e)}")

    async def stop(self) -> Result[bool, str]:
        """I/O 프로파일링 중지"""
        try:
            if not self.is_running:
                return Failure("I/O profiler is not running")
            self.is_running = False
            if self.collection_task:
                self.collection_task.cancel()
                try:
                    await self.collection_task
                except asyncio.CancelledError:
                    pass
                self.collection_task = None
            logger.info("I/O profiler stopped")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop I/O profiler: {str(e)}")

    async def _collection_loop(self):
        """I/O 정보 수집 루프"""
        try:
            while self.is_running:
                snapshot = await self._collect_io_snapshot()
                if snapshot:
                    self.metrics.add_snapshot(snapshot)
                    await self._detect_io_bottlenecks(snapshot)
                    await self._check_io_alerts(snapshot)
                await asyncio.sleep(self.collection_interval)
        except asyncio.CancelledError:
            logger.debug("I/O profiler collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in I/O profiler collection loop: {e}")

    async def _collect_io_snapshot(self) -> Optional[IOSnapshot]:
        """I/O 스냅샷 수집"""
        try:
            disk_io_stats = []
            total_disk_reads = 0
            total_disk_writes = 0
            try:
                disk_io = psutil.disk_io_counters(perdisk=True)
                if disk_io:
                    for device, stats in disk_io.items():
                        disk_stat = DiskIOStats(
                            device=device,
                            read_count=stats.read_count,
                            write_count=stats.write_count,
                            read_bytes=stats.read_bytes,
                            write_bytes=stats.write_bytes,
                            read_time=stats.read_time,
                            write_time=stats.write_time,
                            busy_time=getattr(stats, "busy_time", 0),
                        )
                        disk_io_stats = disk_io_stats + [disk_stat]
                        total_disk_reads = total_disk_reads + stats.read_bytes
                        total_disk_writes = total_disk_writes + stats.write_bytes
            except Exception as e:
                logger.warning(f"Failed to collect disk I/O stats: {e}")
            network_io_stats = []
            total_network_sent = 0
            total_network_recv = 0
            try:
                network_io = psutil.net_io_counters(pernic=True)
                if network_io:
                    for interface, stats in network_io.items():
                        network_stat = NetworkIOStats(
                            interface=interface,
                            bytes_sent=stats.bytes_sent,
                            bytes_recv=stats.bytes_recv,
                            packets_sent=stats.packets_sent,
                            packets_recv=stats.packets_recv,
                            errin=stats.errin,
                            errout=stats.errout,
                            dropin=stats.dropin,
                            dropout=stats.dropout,
                        )
                        network_io_stats = network_io_stats + [network_stat]
                        total_network_sent = total_network_sent + stats.bytes_sent
                        total_network_recv = total_network_recv + stats.bytes_recv
            except Exception as e:
                logger.warning(f"Failed to collect network I/O stats: {e}")
            filesystem_usage = []
            try:
                partitions = psutil.disk_partitions()
                for partition in partitions:
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        fs_usage = FileSystemUsage(
                            mountpoint=partition.mountpoint,
                            device=partition.device,
                            fstype=partition.fstype,
                            total=usage.total,
                            used=usage.used,
                            free=usage.free,
                            percent=usage.percent,
                        )
                        filesystem_usage = filesystem_usage + [fs_usage]
                    except (OSError, PermissionError):
                        continue
            except Exception as e:
                logger.warning(f"Failed to collect filesystem usage: {e}")
            top_io_processes = []
            try:
                processes = []
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        io_info = proc.io_counters()
                        if io_info and (
                            io_info.read_bytes > 0 or io_info.write_bytes > 0
                        ):
                            processes = processes + [
                                {
                                    "pid": proc.info["pid"],
                                    "name": proc.info["name"],
                                    "io_info": io_info,
                                }
                            ]
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                processes.sort(
                    key=lambda x: x["io_info"].read_bytes + x["io_info"].write_bytes,
                    reverse=True,
                )
                for proc_info in processes[: self.top_processes_count]:
                    io_info = proc_info["io_info"]
                    top_io_processes = top_io_processes + [
                        ProcessIOInfo(
                            pid=proc_info["pid"],
                            name=proc_info["name"] or "unknown",
                            read_count=io_info.read_count,
                            write_count=io_info.write_count,
                            read_bytes=io_info.read_bytes,
                            write_bytes=io_info.write_bytes,
                        )
                    ]
            except Exception as e:
                logger.warning(f"Failed to collect process I/O info: {e}")
            return IOSnapshot(
                timestamp=datetime.now(),
                disk_io=disk_io_stats,
                network_io=network_io_stats,
                filesystem_usage=filesystem_usage,
                top_io_processes=top_io_processes,
                total_disk_reads=total_disk_reads,
                total_disk_writes=total_disk_writes,
                total_network_sent=total_network_sent,
                total_network_recv=total_network_recv,
            )
        except Exception as e:
            logger.error(f"Failed to collect I/O snapshot: {e}")
            return None

    async def _detect_io_bottlenecks(self, snapshot: IOSnapshot):
        """I/O 병목 탐지"""
        try:
            bottlenecks = []
            for fs in snapshot.filesystem_usage:
                if fs.percent > self.bottleneck_thresholds["filesystem_usage_percent"]:
                    bottleneck = IOBottleneck(
                        detection_time=datetime.now(),
                        type="filesystem",
                        description=f"High disk usage on {fs.mountpoint}: {fs.percent:.1f}%",
                        severity="critical" if fs.percent > 98 else "high",
                        metrics={
                            "mountpoint": fs.mountpoint,
                            "usage_percent": fs.percent,
                            "free_gb": fs.free / 1024**3,
                        },
                    )
                    bottlenecks = bottlenecks + [bottleneck]
            for disk in snapshot.disk_io:
                if disk.read_time > self.bottleneck_thresholds["disk_io_wait_time_ms"]:
                    bottleneck = IOBottleneck(
                        detection_time=datetime.now(),
                        type="disk",
                        description=f"High disk read wait time on {disk.device}: {disk.read_time}ms",
                        severity="medium" if disk.read_time < 200 else "high",
                        metrics={
                            "device": disk.device,
                            "read_time_ms": disk.read_time,
                            "write_time_ms": disk.write_time,
                        },
                    )
                    bottlenecks = bottlenecks + [bottleneck]
                if disk.write_time > self.bottleneck_thresholds["disk_io_wait_time_ms"]:
                    bottleneck = IOBottleneck(
                        detection_time=datetime.now(),
                        type="disk",
                        description=f"High disk write wait time on {disk.device}: {disk.write_time}ms",
                        severity="medium" if disk.write_time < 200 else "high",
                        metrics={
                            "device": disk.device,
                            "read_time_ms": disk.read_time,
                            "write_time_ms": disk.write_time,
                        },
                    )
                    bottlenecks = bottlenecks + [bottleneck]
            for network in snapshot.network_io:
                total_packets = network.packets_sent + network.packets_recv
                if total_packets > 0:
                    error_rate = (network.errin + network.errout) / total_packets
                    if error_rate > self.bottleneck_thresholds["network_error_rate"]:
                        bottleneck = IOBottleneck(
                            detection_time=datetime.now(),
                            type="network",
                            description=f"High network error rate on {network.interface}: {error_rate:.2%}",
                            severity="high" if error_rate > 0.05 else "medium",
                            metrics={
                                "interface": network.interface,
                                "error_rate": error_rate,
                                "errors_in": network.errin,
                                "errors_out": network.errout,
                            },
                        )
                        bottlenecks = bottlenecks + [bottleneck]
            for bottleneck in bottlenecks:
                self.metrics.detected_bottlenecks = (
                    self.metrics.detected_bottlenecks + [bottleneck]
                )
                await self._notify_bottleneck_detected(bottleneck)
        except Exception as e:
            logger.error(f"Error in I/O bottleneck detection: {e}")

    async def _check_io_alerts(self, snapshot: IOSnapshot):
        """I/O 알림 확인"""
        try:
            alerts = []
            for fs in snapshot.filesystem_usage:
                if fs.percent > 90.0:
                    alerts = alerts + [
                        f"High disk usage on {fs.mountpoint}: {fs.percent:.1f}%"
                    ]
            for network in snapshot.network_io:
                if network.errin + network.errout > 0:
                    total_packets = network.packets_sent + network.packets_recv
                    if total_packets > 0:
                        error_rate = (network.errin + network.errout) / total_packets
                        if error_rate > 0.01:
                            alerts = alerts + [
                                f"Network errors on {network.interface}: {error_rate:.2%}"
                            ]
            if len(self.metrics.snapshots) > 1:
                prev = self.metrics.snapshots[-2]
                time_diff = (snapshot.timestamp - prev.timestamp).total_seconds()
                if time_diff > 0:
                    disk_read_rate = (
                        (snapshot.total_disk_reads - prev.total_disk_reads)
                        / time_diff
                        / 1024**2
                    )
                    disk_write_rate = (
                        (snapshot.total_disk_writes - prev.total_disk_writes)
                        / time_diff
                        / 1024**2
                    )
                    if disk_read_rate > 100:
                        alerts = alerts + [
                            f"High disk read rate: {disk_read_rate:.1f} MB/s"
                        ]
                    if disk_write_rate > 100:
                        alerts = alerts + [
                            f"High disk write rate: {disk_write_rate:.1f} MB/s"
                        ]
            if alerts:
                for callback in self.alert_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alerts, snapshot)
                        else:
                            callback(alerts, snapshot)
                    except Exception as e:
                        logger.error(f"Error in I/O alert callback: {e}")
        except Exception as e:
            logger.error(f"Error checking I/O alerts: {e}")

    async def _notify_bottleneck_detected(self, bottleneck: IOBottleneck):
        """I/O 병목 탐지 알림"""
        try:
            alert_msg = f"I/O bottleneck detected: {bottleneck.description}"
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback([alert_msg], bottleneck)
                    else:
                        callback([alert_msg], bottleneck)
                except Exception as e:
                    logger.error(f"Error in I/O bottleneck callback: {e}")
        except Exception as e:
            logger.error(f"Error notifying I/O bottleneck: {e}")

    def add_alert_callback(self, callback: callable):
        """알림 콜백 추가"""
        self.alert_callbacks = self.alert_callbacks + [callback]

    def set_bottleneck_thresholds(self, **thresholds):
        """병목 탐지 임계값 설정"""
        self.bottleneck_thresholds = {**bottleneck_thresholds, **thresholds}

    def get_current_snapshot(self) -> Optional[IOSnapshot]:
        """현재 I/O 스냅샷 반환"""
        if not self.metrics.snapshots:
            return None
        return self.metrics.snapshots[-1]

    def get_metrics(self) -> IOMetrics:
        """I/O 메트릭 반환"""
        return self.metrics

    def get_detected_bottlenecks(self, minutes=60) -> List[IOBottleneck]:
        """최근 N분간 탐지된 병목들 반환"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            bottleneck
            for bottleneck in self.metrics.detected_bottlenecks
            if bottleneck.detection_time >= cutoff_time
        ]

    async def analyze_io_patterns(self, minutes=10) -> Dict[str, Any]:
        """I/O 패턴 분석"""
        try:
            recent = self.metrics.get_recent_snapshots(minutes)
            if len(recent) < 2:
                return {"error": "Insufficient data"}
            rates = self.metrics.calculate_io_rates(minutes)
            analysis = {
                "period_minutes": minutes,
                "snapshots_analyzed": len(recent),
                "io_rates": rates,
                "bottlenecks_detected": len(self.get_detected_bottlenecks(minutes)),
                "filesystem_analysis": {},
                "network_analysis": {},
            }
            if recent[-1].filesystem_usage:
                for fs in recent[-1].filesystem_usage:
                    analysis = {
                        **analysis,
                        "filesystem_analysis": {
                            **analysis["filesystem_analysis"],
                            fs.mountpoint: {
                                "usage_percent": fs.percent,
                                "free_gb": fs.free / 1024**3,
                                "fstype": fs.fstype,
                            },
                        },
                    }
            if recent[-1].network_io:
                for network in recent[-1].network_io:
                    total_packets = network.packets_sent + network.packets_recv
                    error_rate = 0.0
                    if total_packets > 0:
                        error_rate = (network.errin + network.errout) / total_packets
                    analysis = {
                        **analysis,
                        "network_analysis": {
                            **analysis["network_analysis"],
                            network.interface: {
                                "mb_sent": network.bytes_sent / 1024**2,
                                "mb_recv": network.bytes_recv / 1024**2,
                                "error_rate": error_rate,
                                "packet_loss_rate": (
                                    (network.dropin + network.dropout) / total_packets
                                    if total_packets > 0
                                    else 0.0
                                ),
                            },
                        },
                    }
            return analysis
        except Exception as e:
            logger.error(f"Failed to analyze I/O patterns: {e}")
            return {"error": str(e)}


def create_io_profiler(
    collection_interval: float = 2.0, top_processes_count=10
) -> IOProfiler:
    """I/O 프로파일러 생성"""
    return IOProfiler(
        collection_interval=collection_interval, top_processes_count=top_processes_count
    )


async def get_io_snapshot() -> IOSnapshot:
    """현재 I/O 스냅샷 반환"""
    profiler = IOProfiler()
    snapshot = await profiler._collect_io_snapshot()
    return snapshot or IOSnapshot(
        timestamp=datetime.now(),
        disk_io=[],
        network_io=[],
        filesystem_usage=[],
        top_io_processes=[],
        total_disk_reads=0,
        total_disk_writes=0,
        total_network_sent=0,
        total_network_recv=0,
    )


def monitor_file_operations(file_path: str) -> Dict[str, Any]:
    """파일 작업 모니터링"""
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": "File does not exist"}
        stat = path.stat()
        return {
            "file_path": str(path),
            "size_bytes": stat.st_size,
            "size_mb": stat.st_size / 1024**2,
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "last_accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            "permissions": oct(stat.st_mode)[-3:],
            "is_symlink": path.is_symlink(),
            "parent_directory": str(path.parent),
        }
    except Exception as e:
        return {"error": str(e)}
