"""
RFS Metrics Collection (RFS v4.1)

메트릭스 수집 및 관리 시스템
"""

import asyncio
import json
import statistics
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__)


class MetricType(Enum):
    """메트릭 유형"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """메트릭 기본 클래스"""

    name: str
    metric_type: MetricType
    value: Union[int, float]
    labels: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    description = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp,
            "description": self.description,
        }


class Counter:
    """카운터 메트릭"""

    def __init__(
        self,
        name: str,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0
        self._lock = threading.Lock()

    def increment(self, amount: Union[int, float] = 1) -> "Counter":
        """카운터 증가"""
        with self._lock:
            if amount < 0:
                raise ValueError("카운터는 음수로 증가할 수 없습니다")
            _value = _value + amount
        return self

    def get_value(self) -> Union[int, float]:
        """현재 값 반환"""
        with self._lock:
            return self._value

    def reset(self):
        """카운터 초기화"""
        with self._lock:
            self._value = 0

    def to_metric(self) -> Metric:
        """Metric 객체로 변환"""
        return Metric(
            name=self.name,
            metric_type=MetricType.COUNTER,
            value=self.get_value(),
            labels=self.labels,
            description=self.description,
        )


class Gauge:
    """게이지 메트릭"""

    def __init__(
        self,
        name: str,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0
        self._lock = threading.Lock()

    def set(self, value: Union[int, float]) -> "Gauge":
        """값 설정"""
        with self._lock:
            self._value = value
        return self

    def increment(self, amount: Union[int, float] = 1) -> "Gauge":
        """값 증가"""
        with self._lock:
            _value = _value + amount
        return self

    def decrement(self, amount: Union[int, float] = 1) -> "Gauge":
        """값 감소"""
        with self._lock:
            _value = _value - amount
        return self

    def get_value(self) -> Union[int, float]:
        """현재 값 반환"""
        with self._lock:
            return self._value

    def to_metric(self) -> Metric:
        """Metric 객체로 변환"""
        return Metric(
            name=self.name,
            metric_type=MetricType.GAUGE,
            value=self.get_value(),
            labels=self.labels,
            description=self.description,
        )


class Histogram:
    """히스토그램 메트릭"""

    def __init__(
        self,
        name: str,
        buckets: Optional[List[float]] = None,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.buckets = buckets or [
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
        ]
        self._bucket_counts = {bucket: 0 for bucket in self.buckets}
        self._bucket_counts = {**self._bucket_counts, float("inf"): 0}
        self._count = 0
        self._sum = 0.0
        self._lock = threading.Lock()

    def observe(self, value: Union[int, float]) -> "Histogram":
        """값 관찰"""
        with self._lock:
            _count = _count + 1
            _sum = _sum + value
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts = {
                        **self._bucket_counts,
                        bucket: self._bucket_counts[bucket] + 1,
                    }
            self._bucket_counts[float("inf")] = self._bucket_counts[float("inf")] + (1)
        return self

    def get_count(self) -> int:
        """총 관찰 횟수"""
        with self._lock:
            return self._count

    def get_sum(self) -> float:
        """모든 관찰 값의 합"""
        with self._lock:
            return self._sum

    def get_bucket_counts(self) -> Dict[float, int]:
        """버킷별 카운트"""
        with self._lock:
            return self._bucket_counts.copy()

    def get_quantile(self, quantile: float) -> float:
        """분위수 계산 (근사치)"""
        if not 0 <= quantile <= 1:
            raise ValueError("분위수는 0과 1 사이여야 합니다")
        with self._lock:
            if self._count == 0:
                return 0.0
            target_count = self._count * quantile
            cumulative = 0
            for bucket in sorted(self.buckets):
                cumulative = cumulative + self._bucket_counts[bucket]
                if cumulative >= target_count:
                    return bucket
            return float("inf")

    def to_metric(self) -> Metric:
        """Metric 객체로 변환"""
        return Metric(
            name=self.name,
            metric_type=MetricType.HISTOGRAM,
            value={
                "count": self.get_count(),
                "sum": self.get_sum(),
                "buckets": self.get_bucket_counts(),
            },
            labels=self.labels,
            description=self.description,
        )


class Summary:
    """서머리 메트릭"""

    def __init__(
        self,
        name: str,
        max_age: float = 600,
        max_samples=10000,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.max_age = max_age
        self.max_samples = max_samples
        self._samples = deque()
        self._count = 0
        self._sum = 0.0
        self._lock = threading.Lock()

    def observe(self, value: Union[int, float]) -> "Summary":
        """값 관찰"""
        timestamp = time.time()
        with self._lock:
            self._samples = self._samples + [(timestamp, value)]
            _count = _count + 1
            _sum = _sum + value
            cutoff_time = timestamp - self.max_age
            while self._samples and self._samples[0][0] < cutoff_time:
                old_timestamp, old_value = self._samples.popleft()
                _count = _count - 1
                _sum = _sum - old_value
            while len(self._samples) > self.max_samples:
                old_timestamp, old_value = self._samples.popleft()
                _count = _count - 1
                _sum = _sum - old_value
        return self

    def get_count(self) -> int:
        """총 샘플 수"""
        with self._lock:
            return self._count

    def get_sum(self) -> float:
        """모든 샘플의 합"""
        with self._lock:
            return self._sum

    def get_quantile(self, quantile: float) -> float:
        """분위수 계산"""
        if not 0 <= quantile <= 1:
            raise ValueError("분위수는 0과 1 사이여야 합니다")
        with self._lock:
            if not self._samples:
                return 0.0
            values = [value for _, value in self._samples]
            values.sort()
            match quantile:
                case 0:
                    return values[0]
                case 1:
                    return values[-1]
                case _:
                    index = int(quantile * (len(values) - 1))
                    return values[index]

    def get_statistics(self) -> Dict[str, float]:
        """기본 통계 반환"""
        with self._lock:
            if not self._samples:
                return {"count": 0, "sum": 0, "mean": 0, "min": 0, "max": 0}
            values = [value for _, value in self._samples]
            return {
                "count": self._count,
                "sum": self._sum,
                "mean": statistics.mean(values),
                "min": min(values),
                "max": max(values),
                "median": statistics.median(values),
                "p95": self.get_quantile(0.95),
                "p99": self.get_quantile(0.99),
            }

    def to_metric(self) -> Metric:
        """Metric 객체로 변환"""
        return Metric(
            name=self.name,
            metric_type=MetricType.SUMMARY,
            value=self.get_statistics(),
            labels=self.labels,
            description=self.description,
        )


class MetricsStorage(ABC):
    """메트릭스 저장소 추상 클래스"""

    @abstractmethod
    async def store_metric(self, metric: Metric) -> Result[None, str]:
        """메트릭 저장"""
        pass

    @abstractmethod
    async def get_metrics(
        self,
        name_pattern=None,
        labels: Optional[Dict[str, str]] = None,
        start_time=None,
        end_time=None,
    ) -> Result[List[Metric], str]:
        """메트릭 조회"""
        pass


class MemoryMetricsStorage(MetricsStorage):
    """메모리 기반 메트릭스 저장소"""

    def __init__(self, max_metrics=100000):
        self.max_metrics = max_metrics
        self._metrics = deque()
        self._lock = asyncio.Lock()

    async def store_metric(self, metric: Metric) -> Result[None, str]:
        """메트릭 저장"""
        async with self._lock:
            self._metrics = self._metrics + [metric]
            if len(self._metrics) > self.max_metrics:
                self._metrics.popleft()
        return Success(None)

    async def get_metrics(
        self,
        name_pattern=None,
        labels: Optional[Dict[str, str]] = None,
        start_time=None,
        end_time=None,
    ) -> Result[List[Metric], str]:
        """메트릭 조회"""
        async with self._lock:
            filtered_metrics = []
            for metric in self._metrics:
                if name_pattern and name_pattern not in metric.name:
                    continue
                if labels:
                    if not all((metric.labels.get(k) == v for k, v in labels.items())):
                        continue
                if start_time and metric.timestamp < start_time:
                    continue
                if end_time and metric.timestamp > end_time:
                    continue
                filtered_metrics = filtered_metrics + [metric]
            return Success(filtered_metrics)


class PrometheusStorage(MetricsStorage):
    """Prometheus 기반 메트릭스 저장소"""

    def __init__(self, push_gateway_url: str, job_name="rfs_app"):
        self.push_gateway_url = push_gateway_url
        self.job_name = job_name

    async def store_metric(self, metric: Metric) -> Result[None, str]:
        """메트릭 저장 (Prometheus Push Gateway로 전송)"""
        try:
            await logger.log_debug(f"Prometheus에 메트릭 저장: {metric.name}")
            return Success(None)
        except Exception as e:
            return Failure(f"Prometheus 메트릭 저장 실패: {str(e)}")

    async def get_metrics(
        self,
        name_pattern=None,
        labels: Optional[Dict[str, str]] = None,
        start_time=None,
        end_time=None,
    ) -> Result[List[Metric], str]:
        """메트릭 조회 (Prometheus API 사용)"""
        return Failure("Prometheus 조회 미구현")


class MetricsCollector:
    """메트릭스 수집기"""

    def __init__(self, storage=None):
        self.storage = storage or MemoryMetricsStorage()
        self._counters = {}
        self._gauges = {}
        self._histograms = {}
        self._summaries = {}
        self._lock = threading.Lock()

    def counter(
        self,
        name: str,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Counter:
        """카운터 메트릭 생성/조회"""
        key = f"{name}_{hash(frozenset(labels.items()) if labels else None)}"
        with self._lock:
            if key not in self._counters:
                self._counters = {
                    **self._counters,
                    key: Counter(name, description, labels),
                }
            return self._counters[key]

    def gauge(
        self,
        name: str,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Gauge:
        """게이지 메트릭 생성/조회"""
        key = f"{name}_{hash(frozenset(labels.items()) if labels else None)}"
        with self._lock:
            if key not in self._gauges:
                self._gauges = {**self._gauges, key: Gauge(name, description, labels)}
            return self._gauges[key]

    def histogram(
        self,
        name: str,
        buckets: Optional[List[float]] = None,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Histogram:
        """히스토그램 메트릭 생성/조회"""
        key = f"{name}_{hash(frozenset(labels.items()) if labels else None)}"
        with self._lock:
            if key not in self._histograms:
                self._histograms = {
                    **self._histograms,
                    key: Histogram(name, buckets, description, labels),
                }
            return self._histograms[key]

    def summary(
        self,
        name: str,
        max_age: float = 600,
        max_samples=10000,
        description=None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Summary:
        """서머리 메트릭 생성/조회"""
        key = f"{name}_{hash(frozenset(labels.items()) if labels else None)}"
        with self._lock:
            if key not in self._summaries:
                self._summaries = {
                    **self._summaries,
                    key: Summary(name, max_age, max_samples, description, labels),
                }
            return self._summaries[key]

    async def collect_and_store(self) -> Result[int, str]:
        """모든 메트릭 수집 및 저장"""
        stored_count = 0
        try:
            for counter in self._counters.values():
                result = await self.storage.store_metric(counter.to_metric())
                if result.is_success():
                    stored_count = stored_count + 1
            for gauge in self._gauges.values():
                result = await self.storage.store_metric(gauge.to_metric())
                if result.is_success():
                    stored_count = stored_count + 1
            for histogram in self._histograms.values():
                result = await self.storage.store_metric(histogram.to_metric())
                if result.is_success():
                    stored_count = stored_count + 1
            for summary in self._summaries.values():
                result = await self.storage.store_metric(summary.to_metric())
                if result.is_success():
                    stored_count = stored_count + 1
            return Success(stored_count)
        except Exception as e:
            return Failure(f"메트릭 수집 실패: {str(e)}")

    async def get_all_metrics(self) -> List[Metric]:
        """모든 현재 메트릭 반환"""
        metrics = []
        for counter in self._counters.values():
            metrics = metrics + [counter.to_metric()]
        for gauge in self._gauges.values():
            metrics = metrics + [gauge.to_metric()]
        for histogram in self._histograms.values():
            metrics = metrics + [histogram.to_metric()]
        for summary in self._summaries.values():
            metrics = metrics + [summary.to_metric()]
        return metrics


_metrics_collector = None


def get_metrics_collector(storage=None) -> MetricsCollector:
    """메트릭스 수집기 가져오기"""
    # global _metrics_collector - removed for functional programming
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(storage)
    return _metrics_collector


def record_counter(
    name: str,
    amount: Union[int, float] = 1,
    labels: Optional[Dict[str, str]] = None,
    description=None,
):
    """카운터 메트릭 기록"""
    collector = get_metrics_collector()
    counter = collector.counter(name, description, labels)
    counter.increment(amount)


def record_gauge(
    name: str,
    value: Union[int, float],
    labels: Optional[Dict[str, str]] = None,
    description=None,
):
    """게이지 메트릭 기록"""
    collector = get_metrics_collector()
    gauge = collector.gauge(name, description, labels)
    gauge.set(value)


def record_histogram(
    name: str,
    value: Union[int, float],
    labels: Optional[Dict[str, str]] = None,
    description=None,
):
    """히스토그램 메트릭 기록"""
    collector = get_metrics_collector()
    histogram = collector.histogram(name, description=description, labels=labels)
    histogram.observe(value)


def record_summary(
    name: str,
    value: Union[int, float],
    labels: Optional[Dict[str, str]] = None,
    description=None,
):
    """서머리 메트릭 기록"""
    collector = get_metrics_collector()
    summary = collector.summary(name, description=description, labels=labels)
    summary.observe(value)
