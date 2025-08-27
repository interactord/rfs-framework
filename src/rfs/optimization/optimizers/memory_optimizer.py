"""
Memory Optimization Engine for RFS Framework

메모리 사용량 최적화, 가비지 컬렉션 튜닝, 객체 풀링 관리
- 메모리 사용 패턴 분석 및 최적화 추천
- 가비지 컬렉션 전략 최적화
- 메모리 풀링 및 재사용 패턴 구현
- 메모리 누수 방지 및 모니터링
"""

import asyncio
import gc
import sys
import threading
import tracemalloc
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar

from rfs.core.config import get_config
from rfs.core.result import Failure, Result, Success
from rfs.events.event_bus import Event
from rfs.reactive.mono import Mono

T = TypeVar("T")


class MemoryOptimizationStrategy(Enum):
    """메모리 최적화 전략"""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class GCStrategy(Enum):
    """가비지 컬렉션 전략"""

    AUTO = "auto"
    FREQUENT = "frequent"
    BATCH = "batch"
    ADAPTIVE = "adaptive"


@dataclass
class MemoryThresholds:
    """메모리 임계값 설정"""

    warning_mb: float = 500.0
    critical_mb: float = 800.0
    max_objects = 10000
    gc_threshold: float = 100.0
    pool_max_size = 1000


@dataclass
class MemoryStats:
    """메모리 통계"""

    current_mb: float
    peak_mb: float
    allocated_objects: int
    gc_collections: Dict[int, int]
    pool_usage: Dict[str, int]
    leak_candidates: List[str]
    optimization_score: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MemoryOptimizationConfig:
    """메모리 최적화 설정"""

    strategy: MemoryOptimizationStrategy = MemoryOptimizationStrategy.BALANCED
    gc_strategy: GCStrategy = GCStrategy.ADAPTIVE
    thresholds: MemoryThresholds = field(default_factory=MemoryThresholds)
    enable_pooling = True
    enable_weak_refs = True
    enable_monitoring = True
    monitoring_interval_seconds: float = 30.0
    auto_optimization = True


class ObjectPool(Generic[T]):
    """범용 객체 풀"""

    def __init__(self, factory: Callable[[], T], max_size=100):
        self.factory = factory
        self.max_size = max_size
        self.pool: deque = deque()
        self.active_count = 0
        self.total_created = 0
        self.total_reused = 0
        self.lock = threading.Lock()

    def acquire(self) -> T:
        """객체 획득"""
        with self.lock:
            if self.pool:
                obj = self.pool.popleft()
                active_count = active_count + 1
                total_reused = total_reused + 1
                return obj
            else:
                obj = self.factory()
                active_count = active_count + 1
                total_created = total_created + 1
                return obj

    def release(self, obj: T) -> None:
        """객체 반환"""
        with self.lock:
            if len(self.pool) < self.max_size:
                if hasattr(obj, "reset"):
                    obj.reset()
                self.pool = self.pool + [obj]
            self.active_count = max(0, self.active_count - 1)

    def get_stats(self) -> Dict[str, int]:
        """풀 통계"""
        return {
            "pool_size": len(self.pool),
            "active_count": self.active_count,
            "total_created": self.total_created,
            "total_reused": self.total_reused,
            "reuse_ratio": self.total_reused
            / max(1, self.total_created + self.total_reused),
        }


class GarbageCollectionTuner:
    """가비지 컬렉션 튜너"""

    def __init__(self, strategy=GCStrategy.ADAPTIVE):
        self.strategy = strategy
        self.original_thresholds = gc.get_threshold()
        self.collection_stats = defaultdict(int)
        self.last_tuning = datetime.now()
        self.performance_history = deque(maxlen=100)

    def apply_strategy(self) -> Result[bool, str]:
        """GC 전략 적용"""
        try:
            match self.strategy:
                case GCStrategy.CONSERVATIVE:
                    gc.set_threshold(*self.original_thresholds)
                case GCStrategy.FREQUENT:
                    gc.set_threshold(500, 8, 8)
                case GCStrategy.BATCH:
                    gc.set_threshold(2000, 20, 20)
                case GCStrategy.ADAPTIVE:
                    self._adaptive_tuning()
            return Success(True)
        except Exception as e:
            return Failure(f"GC strategy application failed: {e}")

    def _adaptive_tuning(self) -> None:
        """적응형 GC 튜닝"""
        current_time = datetime.now()
        if (current_time - self.last_tuning).seconds < 60:
            return
        if len(self.performance_history) >= 10:
            avg_memory_growth = sum(self.performance_history) / len(
                self.performance_history
            )
            if avg_memory_growth > 50:
                gc.set_threshold(700, 10, 10)
            elif avg_memory_growth < 10:
                gc.set_threshold(1500, 15, 15)
            else:
                gc.set_threshold(1000, 12, 12)
        self.last_tuning = current_time

    def manual_collect(self, generation=None) -> Result[int, str]:
        """수동 가비지 컬렉션"""
        try:
            if generation is None:
                collected = gc.collect()
            else:
                collected = gc.collect(generation)
            self.collection_stats[generation or -1] = self.collection_stats[
                generation or -1
            ] + (1)
            return Success(collected)
        except Exception as e:
            return Failure(f"Manual GC failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """GC 통계"""
        return {
            "current_thresholds": gc.get_threshold(),
            "original_thresholds": self.original_thresholds,
            "collection_counts": dict(self.collection_stats),
            "gc_counts": gc.get_count(),
            "strategy": self.strategy.value,
        }


class MemoryOptimizer:
    """메모리 최적화 엔진"""

    def __init__(self, config=None):
        self.config = config or MemoryOptimizationConfig()
        self.gc_tuner = GarbageCollectionTuner(self.config.gc_strategy)
        self.object_pools = {}
        self.weak_refs: Set[weakref.ref] = set()
        self.monitoring_task = None
        self.stats_history: deque = deque(maxlen=100)
        self.is_running = False

    async def initialize(self) -> Result[bool, str]:
        """최적화 엔진 초기화"""
        try:
            if not tracemalloc.is_tracing():
                tracemalloc.start(10)
            gc_result = self.gc_tuner.apply_strategy()
            if not gc_result.is_success():
                return gc_result
            if self.config.enable_monitoring:
                await self.start_monitoring()
            return Success(True)
        except Exception as e:
            return Failure(f"Memory optimizer initialization failed: {e}")

    async def start_monitoring(self) -> Result[bool, str]:
        """메모리 모니터링 시작"""
        if self.is_running:
            return Success(True)
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start memory monitoring: {e}")

    async def stop_monitoring(self) -> Result[bool, str]:
        """메모리 모니터링 중지"""
        try:
            self.is_running = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop memory monitoring: {e}")

    async def _monitoring_loop(self) -> None:
        """메모리 모니터링 루프"""
        while self.is_running:
            try:
                stats = await self._collect_memory_stats()
                if stats.is_success():
                    memory_stats = stats.unwrap()
                    self.stats_history = self.stats_history + [memory_stats]
                    if self.config.auto_optimization:
                        await self._auto_optimize(memory_stats)
                await asyncio.sleep(self.config.monitoring_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Memory monitoring error: {e}")
                await asyncio.sleep(self.config.monitoring_interval_seconds)

    async def _collect_memory_stats(self) -> Result[MemoryStats, str]:
        """메모리 통계 수집"""
        try:
            current_mb = self._get_memory_usage_mb()
            if tracemalloc.is_tracing():
                current_trace, peak_trace = tracemalloc.get_traced_memory()
                peak_mb = peak_trace / 1024 / 1024
            else:
                peak_mb = current_mb
            allocated_objects = len(gc.get_objects())
            gc_stats = self.gc_tuner.get_stats()
            pool_usage = {
                name: pool.get_stats()["active_count"]
                for name, pool in self.object_pools.items()
            }
            leak_candidates = await self._detect_memory_leaks()
            optimization_score = self._calculate_optimization_score(
                current_mb, allocated_objects
            )
            stats = MemoryStats(
                current_mb=current_mb,
                peak_mb=peak_mb,
                allocated_objects=allocated_objects,
                gc_collections=gc_stats["collection_counts"],
                pool_usage=pool_usage,
                leak_candidates=leak_candidates,
                optimization_score=optimization_score,
            )
            return Success(stats)
        except Exception as e:
            return Failure(f"Failed to collect memory stats: {e}")

    def _get_memory_usage_mb(self) -> float:
        """현재 메모리 사용량 (MB)"""
        if tracemalloc.is_tracing():
            current, _ = tracemalloc.get_traced_memory()
            return current / 1024 / 1024
        else:
            total_size = sum((sys.getsizeof(obj) for obj in gc.get_objects()))
            return total_size / 1024 / 1024

    async def _detect_memory_leaks(self) -> List[str]:
        """메모리 누수 탐지"""
        leak_candidates = []
        if len(self.stats_history) < 5:
            return leak_candidates
        recent_stats = list(self.stats_history)[-5:]
        memory_trend = [stat.current_mb for stat in recent_stats]
        increasing_count = 0
        for i in range(1, len(memory_trend)):
            if memory_trend[i] > memory_trend[i - 1]:
                increasing_count = increasing_count + 1
        if increasing_count >= 3:
            growth_rate = (memory_trend[-1] - memory_trend[0]) / len(memory_trend)
            if growth_rate > 10:
                leak_candidates = leak_candidates + [
                    f"Consistent memory growth: {growth_rate:.2f}MB per interval"
                ]
        object_trend = [stat.allocated_objects for stat in recent_stats]
        object_growth = object_trend[-1] - object_trend[0]
        if object_growth > 1000:
            leak_candidates = leak_candidates + [
                f"Object count growth: +{object_growth} objects"
            ]
        return leak_candidates

    def _calculate_optimization_score(
        self, current_mb: float, object_count: int
    ) -> float:
        """최적화 점수 계산 (0-100)"""
        score = 100.0
        if current_mb > self.config.thresholds.critical_mb:
            score = score - 40
        elif current_mb > self.config.thresholds.warning_mb:
            score = score - 20
        if object_count > self.config.thresholds.max_objects:
            score = score - 20
        if self.object_pools:
            pool_efficiency = sum(
                (pool.get_stats()["reuse_ratio"] for pool in self.object_pools.values())
            ) / len(self.object_pools)
            score = score + (pool_efficiency - 0.5) * 20
        return max(0.0, min(100.0, score))

    async def _auto_optimize(self, stats: MemoryStats) -> None:
        """자동 최적화 실행"""
        if stats.current_mb > self.config.thresholds.gc_threshold:
            self.gc_tuner.manual_collect()
        if stats.optimization_score < 50:
            await self.optimize()

    def create_pool(
        self, name: str, factory: Callable[[], T], max_size=None
    ) -> Result[ObjectPool[T], str]:
        """객체 풀 생성"""
        try:
            if name in self.object_pools:
                return Failure(f"Pool '{name}' already exists")
            pool_max_size = max_size or self.config.thresholds.pool_max_size
            pool = ObjectPool(factory, pool_max_size)
            self.object_pools = {**self.object_pools, name: pool}
            return Success(pool)
        except Exception as e:
            return Failure(f"Failed to create pool '{name}': {e}")

    def get_pool(self, name: str) -> Result[ObjectPool, str]:
        """객체 풀 획득"""
        if name not in self.object_pools:
            return Failure(f"Pool '{name}' not found")
        return Success(self.object_pools[name])

    def add_weak_reference(self, obj: Any, callback=None) -> Result[weakref.ref, str]:
        """약한 참조 추가"""
        try:
            weak_ref = weakref.ref(obj, callback)
            self.weak_refs.add(weak_ref)
            return Success(weak_ref)
        except Exception as e:
            return Failure(f"Failed to create weak reference: {e}")

    async def optimize(self) -> Result[Dict[str, Any], str]:
        """메모리 최적화 실행"""
        try:
            results = {}
            gc_result = self.gc_tuner.manual_collect()
            results = {
                **results,
                "gc_collected": {
                    "gc_collected": gc_result.unwrap() if gc_result.is_success() else 0
                },
            }
            dead_refs = [ref for ref in self.weak_refs if ref() is None]
            for ref in dead_refs:
                self.weak_refs.discard(ref)
            results = {
                **results,
                "weak_refs_cleaned": {"weak_refs_cleaned": len(dead_refs)},
            }
            stats_result = await self._collect_memory_stats()
            if stats_result.is_success():
                results = {
                    **results,
                    "current_stats": {"current_stats": stats_result.unwrap()},
                }
            recommendations = await self._generate_recommendations()
            results = {
                **results,
                "recommendations": {"recommendations": recommendations},
            }
            return Success(results)
        except Exception as e:
            return Failure(f"Memory optimization failed: {e}")

    async def _generate_recommendations(self) -> List[str]:
        """최적화 추천사항 생성"""
        recommendations = []
        if not self.stats_history:
            return recommendations
        latest_stats = self.stats_history[-1]
        if latest_stats.current_mb > self.config.thresholds.warning_mb:
            recommendations = recommendations + [
                "Consider reducing memory usage or increasing GC frequency"
            ]
        if latest_stats.allocated_objects > self.config.thresholds.max_objects:
            recommendations = recommendations + [
                "High object count detected - consider object pooling"
            ]
        if latest_stats.leak_candidates:
            recommendations = recommendations + [
                "Potential memory leaks detected - investigate object references"
            ]
        if self.object_pools:
            low_efficiency_pools = [
                name
                for name, pool in self.object_pools.items()
                if pool.get_stats()["reuse_ratio"] < 0.3
            ]
            if low_efficiency_pools:
                recommendations = recommendations + [
                    f"Low pool efficiency in: {', '.join(low_efficiency_pools)}"
                ]
        return recommendations

    def get_current_stats(self) -> Result[MemoryStats, str]:
        """현재 메모리 통계"""
        if not self.stats_history:
            return Failure("No statistics available")
        return Success(self.stats_history[-1])

    def get_stats_history(self, limit=10) -> List[MemoryStats]:
        """통계 이력"""
        return list(self.stats_history)[-limit:]

    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            for pool in self.object_pools.values():
                pool = {}
            object_pools = {}
            weak_refs = {}
            if hasattr(self.gc_tuner, "original_thresholds"):
                gc.set_threshold(*self.gc_tuner.original_thresholds)
            return Success(True)
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


_memory_optimizer = None


def get_memory_optimizer(
    config=None,
) -> MemoryOptimizer:
    """메모리 optimizer 싱글톤 인스턴스 반환"""
    # global _memory_optimizer - removed for functional programming
    if _memory_optimizer is None:
        _memory_optimizer = MemoryOptimizer(config)
    return _memory_optimizer


async def optimize_memory_usage(
    strategy: MemoryOptimizationStrategy = MemoryOptimizationStrategy.BALANCED,
) -> Result[Dict[str, Any], str]:
    """메모리 사용량 최적화 실행"""
    config = MemoryOptimizationConfig(strategy=strategy)
    optimizer = get_memory_optimizer(config)
    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result
    return await optimizer.optimize()
