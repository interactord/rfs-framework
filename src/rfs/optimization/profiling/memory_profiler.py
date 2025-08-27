"""
RFS Memory Profiler (RFS v4.2)

메모리 사용량 분석 및 프로파일링
- 메모리 사용 패턴 추적
- 메모리 누수 탐지
- 객체별 메모리 사용량 분석
- 가비지 컬렉션 모니터링
"""

import asyncio
import gc
import logging
import sys
import threading
import tracemalloc
import weakref
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from ...core.result import Failure, Result, Success

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """메모리 스냅샷"""

    timestamp: datetime
    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    swap_total: int
    swap_used: int
    swap_percent: float
    rss: int
    vms: int
    shared: int
    gc_counts: List[int]
    gc_stats: Dict[str, Any]
    traced_memory: Optional[Tuple[int, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_memory": self.total_memory,
            "available_memory": self.available_memory,
            "used_memory": self.used_memory,
            "memory_percent": self.memory_percent,
            "swap_total": self.swap_total,
            "swap_used": self.swap_used,
            "swap_percent": self.swap_percent,
            "rss": self.rss,
            "vms": self.vms,
            "shared": self.shared,
            "gc_counts": self.gc_counts,
            "gc_stats": self.gc_stats,
            "traced_memory": self.traced_memory,
        }


@dataclass
class ObjectTypeInfo:
    """객체 타입 정보"""

    type_name: str
    count: int
    total_size: int
    avg_size: float

    def __post_init__(self):
        if self.count > 0:
            self.avg_size = self.total_size / self.count
        else:
            self.avg_size = 0.0


@dataclass
class MemoryLeak:
    """메모리 누수 정보"""

    detection_time: datetime
    object_type: str
    count_increase: int
    size_increase: int
    growth_rate: float
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detection_time": self.detection_time.isoformat(),
            "object_type": self.object_type,
            "count_increase": self.count_increase,
            "size_increase": self.size_increase,
            "growth_rate": self.growth_rate,
            "confidence": self.confidence,
        }


@dataclass
class MemoryMetrics:
    """메모리 메트릭"""

    snapshots: List[MemorySnapshot] = field(default_factory=list)
    object_history: Dict[str, List[ObjectTypeInfo]] = field(default_factory=dict)
    detected_leaks: List[MemoryLeak] = field(default_factory=list)
    peak_memory = 0

    def add_snapshot(self, snapshot: MemorySnapshot):
        """스냅샷 추가"""
        self.snapshots = self.snapshots + [snapshot]
        if len(self.snapshots) > 1000:
            self.snapshots = self.snapshots[-1000:]
        if snapshot.used_memory > self.peak_memory:
            self.peak_memory = snapshot.used_memory

    def get_recent_snapshots(self, minutes=10) -> List[MemorySnapshot]:
        """최근 N분간의 스냅샷 반환"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            snapshot for snapshot in self.snapshots if snapshot.timestamp >= cutoff_time
        ]

    def detect_memory_trends(self, minutes=5) -> Dict[str, str]:
        """메모리 사용 트렌드 분석"""
        recent = self.get_recent_snapshots(minutes)
        if len(recent) < 2:
            return {"trend": "insufficient_data"}
        memory_values = [s.used_memory for s in recent]
        n = len(memory_values)
        if n < 2:
            return {"trend": "stable"}
        x_values = list(range(n))
        x_mean = sum(x_values) / n
        y_mean = sum(memory_values) / n
        numerator = sum(
            ((x_values[i] - x_mean) * (memory_values[i] - y_mean) for i in range(n))
        )
        denominator = sum(((x_values[i] - x_mean) ** 2 for i in range(n)))
        if denominator == 0:
            return {"trend": "stable"}
        slope = numerator / denominator
        if slope > 1000000:
            return {"trend": "rapidly_increasing", "slope": slope}
        elif slope > 100000:
            return {"trend": "increasing", "slope": slope}
        elif slope < -100000:
            return {"trend": "decreasing", "slope": slope}
        else:
            return {"trend": "stable", "slope": slope}


class MemoryProfiler:
    """메모리 프로파일러"""

    def __init__(self, collection_interval=2.0, enable_tracemalloc=True):
        self.collection_interval = collection_interval
        self.enable_tracemalloc = enable_tracemalloc
        self.metrics = MemoryMetrics()
        self.is_running = False
        self.collection_task = None
        self.start_time = datetime.now()
        self.leak_detection_enabled = True
        self.leak_detection_window = 50
        self.leak_threshold_growth = 1.5
        self.tracked_types: Set[str] = set()
        self.object_refs: Dict[str, List[weakref.ref]] = defaultdict(list)
        self.alert_callbacks = []
        if self.enable_tracemalloc and (not tracemalloc.is_tracing()):
            tracemalloc.start(25)

    async def start(self) -> Result[bool, str]:
        """메모리 프로파일링 시작"""
        try:
            if self.is_running:
                return Failure("Memory profiler is already running")
            self.is_running = True
            self.start_time = datetime.now()
            self.collection_task = asyncio.create_task(self._collection_loop())
            logger.info("Memory profiler started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start memory profiler: {str(e)}")

    async def stop(self) -> Result[bool, str]:
        """메모리 프로파일링 중지"""
        try:
            if not self.is_running:
                return Failure("Memory profiler is not running")
            self.is_running = False
            if self.collection_task:
                self.collection_task.cancel()
                try:
                    await self.collection_task
                except asyncio.CancelledError:
                    pass
                self.collection_task = None
            logger.info("Memory profiler stopped")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop memory profiler: {str(e)}")

    async def _collection_loop(self):
        """메모리 정보 수집 루프"""
        try:
            while self.is_running:
                snapshot = await self._collect_memory_snapshot()
                if snapshot:
                    self.metrics.add_snapshot(snapshot)
                    if self.leak_detection_enabled:
                        await self._detect_memory_leaks()
                    await self._check_memory_alerts(snapshot)
                await asyncio.sleep(self.collection_interval)
        except asyncio.CancelledError:
            logger.debug("Memory profiler collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in memory profiler collection loop: {e}")

    async def _collect_memory_snapshot(self) -> Optional[MemorySnapshot]:
        """메모리 스냅샷 수집"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            process = psutil.Process()
            process_memory = process.memory_info()
            gc_counts = list(gc.get_count())
            gc_stats = {}
            try:
                if hasattr(gc, "get_stats"):
                    gc_stats = {
                        f"generation_{i}": stats
                        for i, stats in enumerate(gc.get_stats())
                    }
            except:
                pass
            traced_memory = None
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                traced_memory = (current, peak)
            return MemorySnapshot(
                timestamp=datetime.now(),
                total_memory=memory.total,
                available_memory=memory.available,
                used_memory=memory.used,
                memory_percent=memory.percent,
                swap_total=swap.total,
                swap_used=swap.used,
                swap_percent=swap.percent,
                rss=process_memory.rss,
                vms=process_memory.vms,
                shared=getattr(process_memory, "shared", 0),
                gc_counts=gc_counts,
                gc_stats=gc_stats,
                traced_memory=traced_memory,
            )
        except Exception as e:
            logger.error(f"Failed to collect memory snapshot: {e}")
            return None

    async def _detect_memory_leaks(self):
        """메모리 누수 탐지"""
        try:
            if len(self.metrics.snapshots) < self.leak_detection_window:
                return
            recent_snapshots = self.metrics.snapshots[-self.leak_detection_window :]
            memory_values = [s.used_memory for s in recent_snapshots]
            start_memory = memory_values[0]
            end_memory = memory_values[-1]
            growth_ratio = end_memory / start_memory if start_memory > 0 else 1.0
            if growth_ratio > self.leak_detection_threshold_growth:
                time_span = (
                    recent_snapshots[-1].timestamp - recent_snapshots[0].timestamp
                ).total_seconds()
                growth_rate = (
                    (end_memory - start_memory) / time_span if time_span > 0 else 0
                )
                confidence = min(1.0, (growth_ratio - 1.0) * 2)
                leak = MemoryLeak(
                    detection_time=datetime.now(),
                    object_type="unknown",
                    count_increase=0,
                    size_increase=end_memory - start_memory,
                    growth_rate=growth_rate,
                    confidence=confidence,
                )
                self.metrics.detected_leaks = self.metrics.detected_leaks + [leak]
                await self._notify_leak_detected(leak)
        except Exception as e:
            logger.error(f"Error in memory leak detection: {e}")

    async def _check_memory_alerts(self, snapshot: MemorySnapshot):
        """메모리 알림 확인"""
        try:
            alerts = []
            if snapshot.memory_percent > 85.0:
                alerts = alerts + [f"High memory usage: {snapshot.memory_percent:.1f}%"]
            if snapshot.swap_percent > 50.0:
                alerts = alerts + [f"High swap usage: {snapshot.swap_percent:.1f}%"]
            if len(self.metrics.snapshots) > 1:
                prev_rss = self.metrics.snapshots[-2].rss
                current_rss = snapshot.rss
                if current_rss > prev_rss * 1.2:
                    alerts = alerts + [
                        f"Rapid memory increase: {(current_rss - prev_rss) / 1024 / 1024:.1f} MB"
                    ]
            if alerts:
                for callback in self.alert_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alerts, snapshot)
                        else:
                            callback(alerts, snapshot)
                    except Exception as e:
                        logger.error(f"Error in memory alert callback: {e}")
        except Exception as e:
            logger.error(f"Error checking memory alerts: {e}")

    async def _notify_leak_detected(self, leak: MemoryLeak):
        """메모리 누수 탐지 알림"""
        try:
            alert_msg = f"Potential memory leak detected: {leak.size_increase / 1024 / 1024:.1f} MB increase"
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback([alert_msg], leak)
                    else:
                        callback([alert_msg], leak)
                except Exception as e:
                    logger.error(f"Error in leak detection callback: {e}")
        except Exception as e:
            logger.error(f"Error notifying leak detection: {e}")

    def add_alert_callback(self, callback: callable):
        """알림 콜백 추가"""
        self.alert_callbacks = self.alert_callbacks + [callback]

    def get_current_snapshot(self) -> Optional[MemorySnapshot]:
        """현재 메모리 스냅샷 반환"""
        if not self.metrics.snapshots:
            return None
        return self.metrics.snapshots[-1]

    def get_metrics(self) -> MemoryMetrics:
        """메모리 메트릭 반환"""
        return self.metrics

    def get_peak_memory(self) -> int:
        """최대 메모리 사용량 반환"""
        return self.metrics.peak_memory

    async def analyze_object_growth(self, minutes=5) -> Dict[str, Any]:
        """객체 증가 패턴 분석"""
        try:
            recent = self.metrics.get_recent_snapshots(minutes)
            if len(recent) < 2:
                return {"error": "Insufficient data"}
            analysis = {
                "period_minutes": minutes,
                "snapshots_analyzed": len(recent),
                "memory_growth": recent[-1].used_memory - recent[0].used_memory,
                "gc_collections": {},
                "trends": self.metrics.detect_memory_trends(minutes),
            }
            if recent[0].gc_counts and recent[-1].gc_counts:
                for i, (start, end) in enumerate(
                    zip(recent[0].gc_counts, recent[-1].gc_counts)
                ):
                    analysis = {
                        **analysis,
                        "gc_collections": {
                            **analysis["gc_collections"],
                            f"generation_{i}": end - start,
                        },
                    }
            return analysis
        except Exception as e:
            logger.error(f"Failed to analyze object growth: {e}")
            return {"error": str(e)}

    async def force_garbage_collection(self) -> Dict[str, Any]:
        """가비지 컬렉션 강제 실행"""
        try:
            before = self.get_current_snapshot()
            collected = []
            for generation in range(gc.get_count().__len__()):
                collected = collected + [gc.collect(generation)]
            await asyncio.sleep(0.1)
            after = await self._collect_memory_snapshot()
            if before and after:
                freed_memory = before.used_memory - after.used_memory
                return {
                    "collected_objects": collected,
                    "freed_memory_bytes": freed_memory,
                    "freed_memory_mb": freed_memory / 1024 / 1024,
                    "before_snapshot": before.to_dict(),
                    "after_snapshot": after.to_dict(),
                }
            else:
                return {"collected_objects": collected}
        except Exception as e:
            return {"error": str(e)}

    def get_tracemalloc_statistics(self, limit=10) -> Optional[List[Dict[str, Any]]]:
        """tracemalloc 통계 정보 반환"""
        if not tracemalloc.is_tracing():
            return None
        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")[:limit]
            return [
                {
                    "filename": (
                        stat.traceback.format()[-1] if stat.traceback else "unknown"
                    ),
                    "size_bytes": stat.size,
                    "size_mb": stat.size / 1024 / 1024,
                    "count": stat.count,
                }
                for stat in top_stats
            ]
        except Exception as e:
            logger.error(f"Failed to get tracemalloc statistics: {e}")
            return None


def create_memory_profiler(
    collection_interval: float = 2.0, enable_tracemalloc=True
) -> MemoryProfiler:
    """메모리 프로파일러 생성"""
    return MemoryProfiler(
        collection_interval=collection_interval, enable_tracemalloc=enable_tracemalloc
    )


async def get_memory_snapshot() -> MemorySnapshot:
    """현재 메모리 스냅샷 반환"""
    profiler = MemoryProfiler(enable_tracemalloc=False)
    snapshot = await profiler._collect_memory_snapshot()
    return snapshot or MemorySnapshot(
        timestamp=datetime.now(),
        total_memory=0,
        available_memory=0,
        used_memory=0,
        memory_percent=0.0,
        swap_total=0,
        swap_used=0,
        swap_percent=0.0,
        rss=0,
        vms=0,
        shared=0,
        gc_counts=[],
        gc_stats={},
    )


def analyze_memory_usage() -> Dict[str, Any]:
    """현재 메모리 사용량 분석"""
    try:
        import sys

        memory = psutil.virtual_memory()
        process = psutil.Process()
        process_memory = process.memory_info()
        analysis = {
            "system_memory": {
                "total_gb": memory.total / 1024**3,
                "available_gb": memory.available / 1024**3,
                "used_percent": memory.percent,
            },
            "process_memory": {
                "rss_mb": process_memory.rss / 1024**2,
                "vms_mb": process_memory.vms / 1024**2,
            },
            "python_objects": {
                "gc_counts": gc.get_count(),
                "reference_count": len(gc.get_referrers()),
            },
        }
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            analysis = {
                **analysis,
                "traced_memory": {
                    "traced_memory": {
                        "current_mb": current / 1024**2,
                        "peak_mb": peak / 1024**2,
                    }
                },
            }
        return analysis
    except Exception as e:
        return {"error": str(e)}
