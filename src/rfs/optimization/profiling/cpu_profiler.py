"""
RFS CPU Profiler (RFS v4.2)

CPU 성능 분석 및 프로파일링
- CPU 사용률 모니터링
- 프로세스별 CPU 사용량 추적
- 코어별 사용률 분석
- CPU 바운드 작업 탐지
"""

import asyncio
import cProfile
import io
import logging
import pstats
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from ...core.result import Failure, Result, Success

logger = logging.getLogger(__name__)


@dataclass
class CPUCoreUsage:
    """CPU 코어별 사용률"""

    core_id: int
    usage_percent: float
    frequency = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "core_id": self.core_id,
            "usage_percent": self.usage_percent,
            "frequency": self.frequency,
        }


@dataclass
class ProcessCPUInfo:
    """프로세스 CPU 정보"""

    pid: int
    name: str
    cpu_percent: float
    cpu_times: Dict[str, float]
    threads: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "name": self.name,
            "cpu_percent": self.cpu_percent,
            "cpu_times": self.cpu_times,
            "threads": self.threads,
        }


@dataclass
class CPUSnapshot:
    """CPU 스냅샷"""

    timestamp: datetime
    overall_cpu_percent: float
    loadavg: Optional[List[float]]
    core_usage: List[CPUCoreUsage]
    top_processes: List[ProcessCPUInfo]
    context_switches = None
    interrupts = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_cpu_percent": self.overall_cpu_percent,
            "loadavg": self.loadavg,
            "core_usage": [core.to_dict() for core in self.core_usage],
            "top_processes": [proc.to_dict() for proc in self.top_processes],
            "context_switches": self.context_switches,
            "interrupts": self.interrupts,
        }


@dataclass
class ProfileResult:
    """프로파일링 결과"""

    function_name: str
    filename: str
    line_number: int
    total_calls: int
    total_time: float
    cumulative_time: float
    per_call_time: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function_name": self.function_name,
            "filename": self.filename,
            "line_number": self.line_number,
            "total_calls": self.total_calls,
            "total_time": self.total_time,
            "cumulative_time": self.cumulative_time,
            "per_call_time": self.per_call_time,
        }


@dataclass
class CPUMetrics:
    """CPU 메트릭"""

    snapshots: List[str] = field(default_factory=list)
    profile_results: List[str] = field(default_factory=list)
    cpu_bound_detections: List[Dict[str, Any]] = field(default_factory=list)

    def add_snapshot(self, snapshot: CPUSnapshot):
        """스냅샷 추가"""
        self.snapshots = self.snapshots + [snapshot]
        if len(self.snapshots) > 1000:
            self.snapshots = self.snapshots[-1000:]

    def get_recent_snapshots(self, minutes=10) -> List[CPUSnapshot]:
        """최근 N분간의 스냅샷 반환"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            snapshot for snapshot in self.snapshots if snapshot.timestamp >= cutoff_time
        ]

    def get_average_cpu_usage(self, minutes=10) -> float:
        """최근 N분간의 평균 CPU 사용률"""
        recent = self.get_recent_snapshots(minutes)
        if not recent:
            return 0.0
        return sum((s.overall_cpu_percent for s in recent)) / len(recent)


class CPUProfiler:
    """CPU 프로파일러"""

    def __init__(self, collection_interval=1.0, top_processes_count=10):
        self.collection_interval = collection_interval
        self.top_processes_count = top_processes_count
        self.metrics = CPUMetrics()
        self.is_running = False
        self.collection_task = None
        self.start_time = datetime.now()
        self.cpu_bound_threshold = 80.0
        self.cpu_bound_duration = 5.0
        self.profiling_enabled = False
        self.current_profiler = None
        self.profiling_results = []
        self.alert_callbacks = []
        self.cpu_count = psutil.cpu_count() if PSUTIL_AVAILABLE else 1
        self.cpu_freq_base = None
        if PSUTIL_AVAILABLE:
            try:
                freq = psutil.cpu_freq()
                if freq:
                    self.cpu_freq_base = freq.current
            except:
                pass

    async def start(self) -> Result[bool, str]:
        """CPU 프로파일링 시작"""
        try:
            if self.is_running:
                return Failure("CPU profiler is already running")
            self.is_running = True
            self.start_time = datetime.now()
            self.collection_task = asyncio.create_task(self._collection_loop())
            logger.info("CPU profiler started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start CPU profiler: {str(e)}")

    async def stop(self) -> Result[bool, str]:
        """CPU 프로파일링 중지"""
        try:
            if not self.is_running:
                return Failure("CPU profiler is not running")
            self.is_running = False
            if self.collection_task:
                self.collection_task.cancel()
                try:
                    await self.collection_task
                except asyncio.CancelledError:
                    pass
                self.collection_task = None
            if self.profiling_enabled:
                await self.stop_profiling()
            logger.info("CPU profiler stopped")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop CPU profiler: {str(e)}")

    async def _collection_loop(self):
        """CPU 정보 수집 루프"""
        try:
            while self.is_running:
                snapshot = await self._collect_cpu_snapshot()
                if snapshot:
                    self.metrics.add_snapshot(snapshot)
                    await self._detect_cpu_bound_tasks(snapshot)
                    await self._check_cpu_alerts(snapshot)
                await asyncio.sleep(self.collection_interval)
        except asyncio.CancelledError:
            logger.debug("CPU profiler collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in CPU profiler collection loop: {e}")

    async def _collect_cpu_snapshot(self) -> Optional[CPUSnapshot]:
        """CPU 스냅샷 수집"""
        if not PSUTIL_AVAILABLE:
            # Return a minimal snapshot when psutil is not available
            return CPUSnapshot(
                timestamp=datetime.now(),
                overall_cpu_percent=0.0,
                loadavg=None,
                core_usage=[],
                top_processes=[],
                context_switches=None,
                interrupts=None,
            )

        try:
            overall_cpu = psutil.cpu_percent(interval=0.1)
            loadavg = None
            if hasattr(psutil, "getloadavg"):
                try:
                    loadavg = list(psutil.getloadavg())
                except (OSError, AttributeError):
                    pass
            core_percentages = psutil.cpu_percent(percpu=True, interval=0.1)
            core_usage = []
            cpu_freq = None
            try:
                cpu_freq = psutil.cpu_freq(percpu=True)
            except:
                pass
            for i, usage in enumerate(core_percentages):
                freq = None
                if cpu_freq and i < len(cpu_freq) and cpu_freq[i]:
                    freq = cpu_freq[i].current
                core_usage = core_usage + [
                    CPUCoreUsage(core_id=i, usage_percent=usage, frequency=freq)
                ]
            top_processes = []
            try:
                processes = []
                for proc in psutil.process_iter(
                    ["pid", "name", "cpu_percent", "cpu_times", "num_threads"]
                ):
                    try:
                        info = proc.info
                        if info.get("cpu_percent") and info.get("cpu_percent") > 0:
                            processes = processes + [info]
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
                for proc_info in processes[: self.top_processes_count]:
                    cpu_times_dict = {}
                    if proc_info.get("cpu_times"):
                        cpu_times_dict = proc_info["cpu_times"]._asdict()
                    top_processes = top_processes + [
                        ProcessCPUInfo(
                            pid=proc_info["pid"],
                            name=proc_info["name"] or "unknown",
                            cpu_percent=proc_info["cpu_percent"],
                            cpu_times=cpu_times_dict,
                            threads=proc_info["num_threads"] or 0,
                        )
                    ]
            except Exception as e:
                logger.warning(f"Failed to collect process CPU info: {e}")
            context_switches = None
            interrupts = None
            try:
                cpu_stats = psutil.cpu_stats()
                context_switches = cpu_stats.ctx_switches
                interrupts = cpu_stats.interrupts
            except:
                pass
            return CPUSnapshot(
                timestamp=datetime.now(),
                overall_cpu_percent=overall_cpu,
                loadavg=loadavg,
                core_usage=core_usage,
                top_processes=top_processes,
                context_switches=context_switches,
                interrupts=interrupts,
            )
        except Exception as e:
            logger.error(f"Failed to collect CPU snapshot: {e}")
            return None

    async def _detect_cpu_bound_tasks(self, snapshot: CPUSnapshot):
        """CPU 바운드 작업 탐지"""
        try:
            if snapshot.overall_cpu_percent > self.cpu_bound_threshold:
                recent_snapshots = self.metrics.get_recent_snapshots(1)
                if (
                    len(recent_snapshots)
                    >= self.cpu_bound_duration / self.collection_interval
                ):
                    high_cpu_count = sum(
                        (
                            1
                            for s in recent_snapshots[
                                -int(
                                    self.cpu_bound_duration / self.collection_interval
                                ) :
                            ]
                            if s.overall_cpu_percent > self.cpu_bound_threshold
                        )
                    )
                    if (
                        high_cpu_count
                        >= self.cpu_bound_duration / self.collection_interval * 0.8
                    ):
                        detection = {
                            "timestamp": datetime.now(),
                            "duration_seconds": self.cpu_bound_duration,
                            "avg_cpu_percent": sum(
                                (s.overall_cpu_percent for s in recent_snapshots)
                            )
                            / len(recent_snapshots),
                            "top_processes": [
                                proc.to_dict() for proc in snapshot.top_processes[:5]
                            ],
                        }
                        self.metrics.cpu_bound_detections = (
                            self.metrics.cpu_bound_detections + [detection]
                        )
                        await self._notify_cpu_bound_detected(detection)
        except Exception as e:
            logger.error(f"Error in CPU bound task detection: {e}")

    async def _check_cpu_alerts(self, snapshot: CPUSnapshot):
        """CPU 알림 확인"""
        try:
            alerts = []
            if snapshot.overall_cpu_percent > 85.0:
                alerts = alerts + [
                    f"High CPU usage: {snapshot.overall_cpu_percent:.1f}%"
                ]
            if snapshot.loadavg and len(snapshot.loadavg) > 0:
                load_1min = snapshot.loadavg[0]
                if load_1min > self.cpu_count * 1.5:
                    alerts = alerts + [
                        f"High load average: {load_1min:.2f} (cores: {self.cpu_count})"
                    ]
            if len(snapshot.core_usage) > 1:
                usage_values = [core.usage_percent for core in snapshot.core_usage]
                max_usage = max(usage_values)
                min_usage = min(usage_values)
                if max_usage - min_usage > 50.0:
                    alerts = alerts + [
                        f"Unbalanced core usage: {max_usage:.1f}% - {min_usage:.1f}%"
                    ]
            if alerts:
                for callback in self.alert_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alerts, snapshot)
                        else:
                            callback(alerts, snapshot)
                    except Exception as e:
                        logger.error(f"Error in CPU alert callback: {e}")
        except Exception as e:
            logger.error(f"Error checking CPU alerts: {e}")

    async def _notify_cpu_bound_detected(self, detection: Dict[str, Any]):
        """CPU 바운드 작업 탐지 알림"""
        try:
            alert_msg = f"CPU bound task detected: {detection['avg_cpu_percent']:.1f}% for {detection['duration_seconds']}s"
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback([alert_msg], detection)
                    else:
                        callback([alert_msg], detection)
                except Exception as e:
                    logger.error(f"Error in CPU bound detection callback: {e}")
        except Exception as e:
            logger.error(f"Error notifying CPU bound detection: {e}")

    async def start_profiling(self) -> Result[bool, str]:
        """함수 수준 프로파일링 시작"""
        try:
            if self.profiling_enabled:
                return Failure("Profiling is already running")
            self.current_profiler = cProfile.Profile()
            self.current_profiler.enable()
            self.profiling_enabled = True
            logger.info("CPU function profiling started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start profiling: {str(e)}")

    async def stop_profiling(self) -> Result[List[ProfileResult], str]:
        """함수 수준 프로파일링 중지 및 결과 반환"""
        try:
            if not self.profiling_enabled or not self.current_profiler:
                return Failure("Profiling is not running")
            self.current_profiler.disable()
            self.profiling_enabled = False
            s = io.StringIO()
            stats = pstats.Stats(self.current_profiler, stream=s)
            stats.sort_stats("cumulative")
            results = []
            for func_info, (
                total_calls,
                _,
                total_time,
                cumulative_time,
            ) in stats.stats.items():
                filename, line_number, function_name = func_info
                per_call_time = total_time / total_calls if total_calls > 0 else 0
                result = ProfileResult(
                    function_name=function_name,
                    filename=filename,
                    line_number=line_number,
                    total_calls=total_calls,
                    total_time=total_time,
                    cumulative_time=cumulative_time,
                    per_call_time=per_call_time,
                )
                results = results + [result]
            results.sort(key=lambda x: x.cumulative_time, reverse=True)
            self.profiling_results = results[:100]
            self.metrics.profile_results = self.profiling_results
            self.current_profiler = None
            logger.info(
                f"CPU function profiling stopped. Analyzed {len(results)} functions"
            )
            return Success(results)
        except Exception as e:
            self.profiling_enabled = False
            self.current_profiler = None
            return Failure(f"Failed to stop profiling: {str(e)}")

    def add_alert_callback(self, callback: callable):
        """알림 콜백 추가"""
        self.alert_callbacks = self.alert_callbacks + [callback]

    def get_current_snapshot(self) -> Optional[CPUSnapshot]:
        """현재 CPU 스냅샷 반환"""
        if not self.metrics.snapshots:
            return None
        return self.metrics.snapshots[-1]

    def get_metrics(self) -> CPUMetrics:
        """CPU 메트릭 반환"""
        return self.metrics

    async def analyze_cpu_patterns(self, minutes=10) -> Dict[str, Any]:
        """CPU 사용 패턴 분석"""
        try:
            recent = self.metrics.get_recent_snapshots(minutes)
            if len(recent) < 2:
                return {"error": "Insufficient data"}
            cpu_values = [s.overall_cpu_percent for s in recent]
            analysis = {
                "period_minutes": minutes,
                "snapshots_analyzed": len(recent),
                "avg_cpu_percent": sum(cpu_values) / len(cpu_values),
                "max_cpu_percent": max(cpu_values),
                "min_cpu_percent": min(cpu_values),
                "cpu_variance": self._calculate_variance(cpu_values),
                "cpu_bound_detections": len(self.metrics.cpu_bound_detections),
                "core_analysis": {},
            }
            if recent[0].core_usage:
                core_count = len(recent[0].core_usage)
                for core_id in range(core_count):
                    core_values = []
                    for snapshot in recent:
                        if core_id < len(snapshot.core_usage):
                            core_values = core_values + [
                                snapshot.core_usage[core_id].usage_percent
                            ]
                    if core_values:
                        analysis = {
                            **analysis,
                            "core_analysis": {
                                **analysis["core_analysis"],
                                f"core_{core_id}": {
                                    "avg_percent": sum(core_values) / len(core_values),
                                    "max_percent": max(core_values),
                                    "min_percent": min(core_values),
                                },
                            },
                        }
            return analysis
        except Exception as e:
            logger.error(f"Failed to analyze CPU patterns: {e}")
            return {"error": str(e)}

    def _calculate_variance(self, values: List[float]) -> float:
        """분산 계산"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum(((x - mean) ** 2 for x in values)) / (len(values) - 1)
        return variance

    async def get_top_cpu_consumers(self, limit=10) -> List[Dict[str, Any]]:
        """CPU 사용량이 높은 함수들 반환 (프로파일링 결과 기반)"""
        try:
            if not self.profiling_results:
                return []
            return [result.to_dict() for result in self.profiling_results[:limit]]
        except Exception as e:
            logger.error(f"Failed to get top CPU consumers: {e}")
            return []


def create_cpu_profiler(
    collection_interval: float = 1.0, top_processes_count=10
) -> CPUProfiler:
    """CPU 프로파일러 생성"""
    return CPUProfiler(
        collection_interval=collection_interval, top_processes_count=top_processes_count
    )


async def get_cpu_snapshot() -> CPUSnapshot:
    """현재 CPU 스냅샷 반환"""
    profiler = CPUProfiler()
    snapshot = await profiler._collect_cpu_snapshot()
    return snapshot or CPUSnapshot(
        timestamp=datetime.now(),
        overall_cpu_percent=0.0,
        loadavg=None,
        core_usage=[],
        top_processes=[],
    )


def profile_function(func: Callable) -> Callable:
    """함수 프로파일링 데코레이터"""

    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            profiler.disable()
            s = io.StringIO()
            stats = pstats.Stats(profiler, stream=s)
            stats.sort_stats("cumulative")
            stats.print_stats(10)
            logger.info(f"Profiling result for {func.__name__}:\n{s.getvalue()}")

    return wrapper
