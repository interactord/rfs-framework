"""
RFS v4.1 Performance Monitoring Decorators
성능 모니터링 어노테이션 구현

주요 기능:
- @PerformanceMonitored: 성능 메트릭 자동 수집
- @Cached: 결과 캐싱
- @RateLimited: 요청 속도 제한
- @Profiled: 프로파일링
"""

import asyncio
import functools
import hashlib
import logging
import pickle
import threading
import time
import tracemalloc
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

import psutil

from ..cloud_run.monitoring import CloudMonitoringClient, MetricType
from ..core.result import Failure, Result, Success

logger = logging.getLogger(__name__)
T = TypeVar("T")


class PerformanceLevel(Enum):
    """성능 레벨"""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    SLOW = "slow"
    CRITICAL = "critical"


@dataclass
class PerformanceMetrics:
    """성능 메트릭"""

    function_name: str
    start_time: datetime
    end_time = None
    duration_ms: float = 0.0
    cpu_percent_before: float = 0.0
    cpu_percent_after: float = 0.0
    cpu_delta: float = 0.0
    memory_mb_before: float = 0.0
    memory_mb_after: float = 0.0
    memory_delta_mb: float = 0.0
    io_read_bytes = 0
    io_write_bytes = 0
    success = True
    error_message = None
    performance_level: PerformanceLevel = PerformanceLevel.GOOD
    tags: Dict[str, Any] = field(default_factory=dict)

    def calculate_performance_level(self) -> PerformanceLevel:
        """성능 레벨 계산"""
        if self.duration_ms < 100:
            return PerformanceLevel.EXCELLENT
        elif self.duration_ms < 500:
            return PerformanceLevel.GOOD
        elif self.duration_ms < 1000:
            return PerformanceLevel.ACCEPTABLE
        elif self.duration_ms < 3000:
            return PerformanceLevel.SLOW
        else:
            return PerformanceLevel.CRITICAL


class PerformanceMonitor:
    """성능 모니터"""

    def __init__(self, project_id=None):
        self.metrics_history: deque = deque(maxlen=1000)
        self.aggregated_metrics: Dict[str, List[PerformanceMetrics]] = defaultdict(list)
        self.monitoring_client = None
        if project_id:
            try:
                self.monitoring_client = CloudMonitoringClient(project_id)
            except Exception as e:
                logger.warning(f"Failed to initialize CloudMonitoringClient: {e}")
        self.total_calls = 0
        self.total_errors = 0
        self.total_duration_ms = 0.0
        self.alert_thresholds = {
            "duration_ms": 3000,
            "memory_delta_mb": 100,
            "cpu_delta": 50,
            "error_rate": 0.05,
        }

    def record(self, metrics: PerformanceMetrics) -> None:
        """메트릭 기록"""
        self.metrics_history = self.metrics_history + [metrics]
        self.aggregated_metrics[metrics.function_name] = self.aggregated_metrics[
            metrics.function_name
        ] + [metrics]
        total_calls = total_calls + 1
        total_duration_ms = total_duration_ms + metrics.duration_ms
        if not metrics.success:
            total_errors = total_errors + 1
        self._check_alerts(metrics)
        if self.monitoring_client:
            asyncio.create_task(self._send_to_monitoring(metrics))

    async def _send_to_monitoring(self, metrics: PerformanceMetrics) -> None:
        """Cloud Monitoring으로 메트릭 전송"""
        try:
            await self.monitoring_client.send_metric(
                metric_name=f"function_duration/{metrics.function_name}",
                value=metrics.duration_ms,
                metric_type=MetricType.GAUGE,
                labels={
                    "function": metrics.function_name,
                    "performance_level": metrics.performance_level.value,
                    "success": str(metrics.success),
                },
            )
            await self.monitoring_client.send_metric(
                metric_name=f"function_memory/{metrics.function_name}",
                value=metrics.memory_delta_mb,
                metric_type=MetricType.GAUGE,
                labels={"function": metrics.function_name},
            )
        except Exception as e:
            logger.debug(f"Failed to send metrics to monitoring: {e}")

    def _check_alerts(self, metrics: PerformanceMetrics) -> None:
        """알림 체크"""
        alerts = []
        if metrics.duration_ms > self.alert_thresholds["duration_ms"]:
            alerts = alerts + [f"Slow performance: {metrics.duration_ms:.2f}ms"]
        if metrics.memory_delta_mb > self.alert_thresholds["memory_delta_mb"]:
            alerts = alerts + [f"High memory usage: {metrics.memory_delta_mb:.2f}MB"]
        if metrics.cpu_delta > self.alert_thresholds["cpu_delta"]:
            alerts = alerts + [f"High CPU usage: {metrics.cpu_delta:.1f}%"]
        error_rate = self.total_errors / max(self.total_calls, 1)
        if error_rate > self.alert_thresholds["error_rate"]:
            alerts = alerts + [f"High error rate: {error_rate:.2%}"]
        if alerts:
            logger.warning(
                f"Performance alerts for {metrics.function_name}: {', '.join(alerts)}"
            )

    def get_statistics(self, function_name=None) -> Dict[str, Any]:
        """통계 조회"""
        if function_name:
            metrics_list = self.aggregated_metrics.get(function_name, [])
        else:
            metrics_list = list(self.metrics_history)
        if not metrics_list:
            return {}
        durations = [m.duration_ms for m in metrics_list]
        memory_deltas = [m.memory_delta_mb for m in metrics_list]
        cpu_deltas = [m.cpu_delta for m in metrics_list]
        errors = sum((1 for m in metrics_list if not m.success))
        return {
            "total_calls": len(metrics_list),
            "total_errors": errors,
            "error_rate": errors / len(metrics_list),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "avg_memory_delta_mb": sum(memory_deltas) / len(memory_deltas),
            "max_memory_delta_mb": max(memory_deltas),
            "avg_cpu_delta": sum(cpu_deltas) / len(cpu_deltas),
            "max_cpu_delta": max(cpu_deltas),
        }


_performance_monitor = PerformanceMonitor()


def PerformanceMonitored(
    track_memory=True,
    track_cpu=True,
    track_io=False,
    alert_on_slow=True,
    threshold_ms: float = 1000,
    tags: Optional[Dict[str, Any]] = None,
):
    """
    성능 모니터링 데코레이터

    Args:
        track_memory: 메모리 사용량 추적
        track_cpu: CPU 사용량 추적
        track_io: I/O 추적
        alert_on_slow: 느린 실행 알림
        threshold_ms: 임계값 (밀리초)
        tags: 추가 태그
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics = PerformanceMetrics(
                function_name=f"{func.__module__}.{func.__name__}",
                start_time=datetime.now(),
                tags=tags or {},
            )
            process = psutil.Process()
            if track_memory:
                memory_info = process.memory_info()
                metrics.memory_mb_before = memory_info.rss / 1024 / 1024
            if track_cpu:
                metrics.cpu_percent_before = process.cpu_percent()
            if track_io:
                io_counters_before = (
                    process.io_counters() if hasattr(process, "io_counters") else None
                )
            try:
                start_time = time.perf_counter()
                result = await func(*args, **kwargs)
                execution_time = (time.perf_counter() - start_time) * 1000
                metrics.duration_ms = execution_time
                metrics.end_time = datetime.now()
                metrics.success = True
                if track_memory:
                    memory_info = process.memory_info()
                    metrics.memory_mb_after = memory_info.rss / 1024 / 1024
                    metrics.memory_delta_mb = (
                        metrics.memory_mb_after - metrics.memory_mb_before
                    )
                if track_cpu:
                    metrics.cpu_percent_after = process.cpu_percent()
                    metrics.cpu_delta = (
                        metrics.cpu_percent_after - metrics.cpu_percent_before
                    )
                if track_io and io_counters_before:
                    io_counters_after = process.io_counters()
                    metrics.io_read_bytes = (
                        io_counters_after.read_bytes - io_counters_before.read_bytes
                    )
                    metrics.io_write_bytes = (
                        io_counters_after.write_bytes - io_counters_before.write_bytes
                    )
                metrics.performance_level = metrics.calculate_performance_level()
                if alert_on_slow and execution_time > threshold_ms:
                    logger.warning(
                        f"Slow execution detected: {metrics.function_name} took {execution_time:.2f}ms (threshold: {threshold_ms}ms)"
                    )
                _performance_monitor.record(metrics)
                return result
            except Exception as e:
                metrics.end_time = datetime.now()
                metrics.duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.success = False
                metrics.error_message = str(e)
                _performance_monitor.record(metrics)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics = PerformanceMetrics(
                function_name=f"{func.__module__}.{func.__name__}",
                start_time=datetime.now(),
                tags=tags or {},
            )
            process = psutil.Process()
            if track_memory:
                memory_info = process.memory_info()
                metrics.memory_mb_before = memory_info.rss / 1024 / 1024
            if track_cpu:
                metrics.cpu_percent_before = process.cpu_percent()
            if track_io:
                io_counters_before = (
                    process.io_counters() if hasattr(process, "io_counters") else None
                )
            try:
                start_time = time.perf_counter()
                result = func(*args, **kwargs)
                execution_time = (time.perf_counter() - start_time) * 1000
                metrics.duration_ms = execution_time
                metrics.end_time = datetime.now()
                metrics.success = True
                if track_memory:
                    memory_info = process.memory_info()
                    metrics.memory_mb_after = memory_info.rss / 1024 / 1024
                    metrics.memory_delta_mb = (
                        metrics.memory_mb_after - metrics.memory_mb_before
                    )
                if track_cpu:
                    metrics.cpu_percent_after = process.cpu_percent()
                    metrics.cpu_delta = (
                        metrics.cpu_percent_after - metrics.cpu_percent_before
                    )
                if track_io and io_counters_before:
                    io_counters_after = process.io_counters()
                    metrics.io_read_bytes = (
                        io_counters_after.read_bytes - io_counters_before.read_bytes
                    )
                    metrics.io_write_bytes = (
                        io_counters_after.write_bytes - io_counters_before.write_bytes
                    )
                metrics.performance_level = metrics.calculate_performance_level()
                if alert_on_slow and execution_time > threshold_ms:
                    logger.warning(
                        f"Slow execution detected: {metrics.function_name} took {execution_time:.2f}ms (threshold: {threshold_ms}ms)"
                    )
                _performance_monitor.record(metrics)
                return result
            except Exception as e:
                metrics.end_time = datetime.now()
                metrics.duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.success = False
                metrics.error_message = str(e)
                _performance_monitor.record(metrics)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class SimpleCache:
    """간단한 캐시 구현"""

    def __init__(self, max_size=100, ttl_seconds=300):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 가져오기"""
        with self.lock:
            if key in self.cache:
                if datetime.now() - self.timestamps[key] < timedelta(
                    seconds=self.ttl_seconds
                ):
                    hits = hits + 1
                    return self.cache[key]
                else:
                    del self.cache[key]
                    del self.timestamps[key]
            misses = misses + 1
            return None

    def set(self, key: str, value: Any) -> None:
        """캐시에 값 저장"""
        with self.lock:
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.timestamps, key=self.timestamps.get)
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            self.cache = {**self.cache, key: value}
            self.timestamps = {**self.timestamps, key: datetime.now()}

    def clear(self) -> None:
        """캐시 초기화"""
        with self.lock:
            cache = {}
            timestamps = {}

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        total = self.hits + self.misses
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0,
        }


def Cached(ttl_seconds=300, max_size=100, key_func=None):
    """
    결과 캐싱 데코레이터

    Args:
        ttl_seconds: 캐시 유효 시간 (초)
        max_size: 최대 캐시 크기
        key_func: 캐시 키 생성 함수
    """
    cache = SimpleCache(max_size=max_size, ttl_seconds=ttl_seconds)

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_data = (args, tuple(sorted(kwargs.items())))
                cache_key = hashlib.md5(pickle.dumps(key_data)).hexdigest()
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_data = (args, tuple(sorted(kwargs.items())))
                cache_key = hashlib.md5(pickle.dumps(key_data)).hexdigest()
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.cache_stats = cache.get_stats
        wrapper.cache_clear = cache.clear
        return wrapper

    return decorator


def get_performance_monitor() -> PerformanceMonitor:
    """글로벌 성능 모니터 반환"""
    return _performance_monitor


def get_performance_statistics(function_name=None) -> Dict[str, Any]:
    """성능 통계 조회"""
    return _performance_monitor.get_statistics(function_name)


def set_alert_thresholds(thresholds: Dict[str, float]) -> None:
    """알림 임계값 설정"""
    _performance_monitor.alert_thresholds = {**alert_thresholds, **thresholds}
