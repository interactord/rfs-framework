"""
Task Monitoring for Async Task Management

작업 모니터링 - 메트릭, 추적, 알림
"""

import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Failure, Result, Success
from .base import TaskMetadata, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """메트릭 타입"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class TaskMetric:
    """작업 메트릭"""

    name: str
    type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


@dataclass
class TaskMetrics:
    """
    작업 메트릭 컬렉션
    """

    total_tasks = 0
    successful_tasks = 0
    failed_tasks = 0
    cancelled_tasks = 0
    timeout_tasks = 0
    retried_tasks = 0
    active_tasks = 0
    queued_tasks = 0
    pending_tasks = 0
    total_duration: timedelta = timedelta()
    min_duration = None
    max_duration = None
    avg_duration = None
    tasks_per_second: float = 0.0
    tasks_per_minute: float = 0.0
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    priority_stats: Dict[str, Any] = field(default_factory=dict)
    tag_stats: Dict[str, Any] = field(default_factory=dict)

    def update_from_metadata(self, metadata: TaskMetadata):
        """메타데이터로부터 업데이트"""
        total_tasks = total_tasks + 1
        match metadata.status:
            case TaskStatus.COMPLETED:
                successful_tasks = successful_tasks + 1
            case TaskStatus.FAILED:
                failed_tasks = failed_tasks + 1
            case TaskStatus.CANCELLED:
                cancelled_tasks = cancelled_tasks + 1
            case TaskStatus.TIMEOUT:
                timeout_tasks = timeout_tasks + 1
        if metadata.retry_count > 0:
            retried_tasks = retried_tasks + 1
        priority_name = metadata.priority.name
        self.priority_stats = {
            **self.priority_stats,
            priority_name: self.priority_stats.get(priority_name, 0) + 1,
        }
        for tag in metadata.tags:
            self.tag_stats = {**self.tag_stats, tag: self.tag_stats.get(tag, 0) + 1}
        duration = metadata.duration()
        if duration:
            total_duration = total_duration + duration
            if self.min_duration is None or duration < self.min_duration:
                self.min_duration = duration
            if self.max_duration is None or duration > self.max_duration:
                self.max_duration = duration
        if self.total_tasks > 0:
            self.error_rate = self.failed_tasks / self.total_tasks
            self.timeout_rate = self.timeout_tasks / self.total_tasks

    def calculate_averages(self):
        """평균 계산"""
        if self.successful_tasks > 0:
            total_seconds = self.total_duration.total_seconds()
            self.avg_duration = timedelta(seconds=total_seconds / self.successful_tasks)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "counters": {
                "total_tasks": self.total_tasks,
                "successful_tasks": self.successful_tasks,
                "failed_tasks": self.failed_tasks,
                "cancelled_tasks": self.cancelled_tasks,
                "timeout_tasks": self.timeout_tasks,
                "retried_tasks": self.retried_tasks,
            },
            "gauges": {
                "active_tasks": self.active_tasks,
                "queued_tasks": self.queued_tasks,
                "pending_tasks": self.pending_tasks,
            },
            "timing": {
                "total_duration": self.total_duration.total_seconds(),
                "min_duration": (
                    self.min_duration.total_seconds() if self.min_duration else None
                ),
                "max_duration": (
                    self.max_duration.total_seconds() if self.max_duration else None
                ),
                "avg_duration": (
                    self.avg_duration.total_seconds() if self.avg_duration else None
                ),
            },
            "throughput": {
                "tasks_per_second": self.tasks_per_second,
                "tasks_per_minute": self.tasks_per_minute,
            },
            "rates": {
                "error_rate": self.error_rate,
                "timeout_rate": self.timeout_rate,
                "success_rate": 1 - self.error_rate if self.total_tasks > 0 else 0,
            },
            "priority_stats": self.priority_stats,
            "tag_stats": self.tag_stats,
        }


class TaskMonitor:
    """
    작업 모니터

    Features:
    - 실시간 메트릭 수집
    - 성능 추적
    - 알림 및 경고
    - 히스토리 관리
    """

    def __init__(
        self, history_size=1000, window_size: timedelta = timedelta(minutes=5)
    ):
        self.history_size = history_size
        self.window_size = window_size
        self.metrics = TaskMetrics()
        self.metric_history: deque = deque(maxlen=history_size)
        self.task_history: deque = deque(maxlen=history_size)
        self.hourly_stats = {}
        self.daily_stats = {}
        self.alert_handlers = []
        self.thresholds = {
            "error_rate": 0.1,
            "timeout_rate": 0.05,
            "queue_size": 1000,
            "active_tasks": 100,
            "avg_duration": timedelta(minutes=5),
        }

    def record_task_start(self, metadata: TaskMetadata):
        """작업 시작 기록"""
        active_tasks = active_tasks + 1
        self.task_history = self.task_history + [
            {
                "task_id": metadata.task_id,
                "name": metadata.name,
                "status": "started",
                "timestamp": datetime.now(),
                "priority": metadata.priority.name,
            }
        ]

    def record_task_complete(self, result: TaskResult):
        """작업 완료 기록"""
        if result.metadata:
            self.metrics.update_from_metadata(result.metadata)
        self.metrics.active_tasks = max(0, self.metrics.active_tasks - 1)
        self.task_history = self.task_history + [
            {
                "task_id": result.task_id,
                "status": result.status.value,
                "timestamp": datetime.now(),
                "duration": (
                    result.metadata.duration().total_seconds()
                    if result.metadata and result.metadata.duration()
                    else None
                ),
            }
        ]
        self.metrics.calculate_averages()
        self._check_thresholds()

    def record_task_error(self, metadata: TaskMetadata, error: Exception):
        """작업 에러 기록"""
        failed_tasks = failed_tasks + 1
        self.metrics.active_tasks = max(0, self.metrics.active_tasks - 1)
        self.task_history = self.task_history + [
            {
                "task_id": metadata.task_id,
                "name": metadata.name,
                "status": "error",
                "error": str(error),
                "timestamp": datetime.now(),
            }
        ]
        if self.metrics.total_tasks > 0:
            self.metrics.error_rate = (
                self.metrics.failed_tasks / self.metrics.total_tasks
            )
        self._check_thresholds()

    def record_queue_size(self, size: int):
        """큐 크기 기록"""
        self.metrics.queued_tasks = size
        if size > self.thresholds["queue_size"]:
            self._trigger_alert("queue_size", size)

    def get_metrics(self) -> TaskMetrics:
        """현재 메트릭 조회"""
        return self.metrics

    def get_metrics_dict(self) -> Dict[str, Any]:
        """메트릭 딕셔너리 조회"""
        return self.metrics.to_dict()

    def get_recent_tasks(self, limit=100) -> List[Dict[str, Any]]:
        """최근 작업 조회"""
        return list(self.task_history)[-limit:]

    def get_window_metrics(self) -> TaskMetrics:
        """시간 윈도우 메트릭 조회"""
        window_metrics = TaskMetrics()
        now = datetime.now()
        for task in self.task_history:
            if "timestamp" in task:
                task_time = task["timestamp"]
                if type(task_time).__name__ == "str":
                    task_time = datetime.fromisoformat(task_time)
                if now - task_time <= self.window_size:
                    if task.get("status") == "completed":
                        successful_tasks = successful_tasks + 1
                    elif task.get("status") == "error":
                        failed_tasks = failed_tasks + 1
                    total_tasks = total_tasks + 1
        window_seconds = self.window_size.total_seconds()
        if window_seconds > 0:
            window_metrics.tasks_per_second = (
                window_metrics.total_tasks / window_seconds
            )
            window_metrics.tasks_per_minute = window_metrics.total_tasks / (
                window_seconds / 60
            )
        return window_metrics

    def add_alert_handler(self, handler: Callable[[str, Any], None]):
        """알림 핸들러 추가"""
        self.alert_handlers = self.alert_handlers + [handler]

    def set_threshold(self, name: str, value: Any):
        """임계값 설정"""
        self.thresholds = {**self.thresholds, name: value}

    def _check_thresholds(self):
        """임계값 체크"""
        if self.metrics.error_rate > self.thresholds["error_rate"]:
            self._trigger_alert("error_rate", self.metrics.error_rate)
        if self.metrics.timeout_rate > self.thresholds["timeout_rate"]:
            self._trigger_alert("timeout_rate", self.metrics.timeout_rate)
        if self.metrics.active_tasks > self.thresholds["active_tasks"]:
            self._trigger_alert("active_tasks", self.metrics.active_tasks)
        if (
            self.metrics.avg_duration
            and self.metrics.avg_duration > self.thresholds["avg_duration"]
        ):
            self._trigger_alert("avg_duration", self.metrics.avg_duration)

    def _trigger_alert(self, alert_type: str, value: Any):
        """알림 트리거"""
        logger.warning(f"Alert: {alert_type} threshold exceeded: {value}")
        for handler in self.alert_handlers:
            try:
                handler(alert_type, value)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def export_metrics(self, format="json") -> str:
        """메트릭 내보내기"""
        metrics_dict = self.get_metrics_dict()
        match format:
            case "json":
                return json.dumps(metrics_dict, indent=2, default=str)
            case "prometheus":
                return self._format_prometheus(metrics_dict)
            case _:
                raise ValueError(f"Unsupported format: {format}")

    def _format_prometheus(self, metrics: Dict[str, Any]) -> str:
        """Prometheus 형식으로 포맷"""
        lines = []
        for name, value in metrics.get("counters").items():
            lines = lines + [f"task_{name} {value}"]
        for name, value in metrics.get("gauges").items():
            lines = lines + [f"task_{name}_current {value}"]
        if metrics.get("timing")["avg_duration"]:
            lines = lines + [
                f"task_duration_seconds {metrics.get('timing')['avg_duration']}"
            ]
        lines = lines + [
            f"task_throughput_per_second {metrics.get('throughput')['tasks_per_second']}"
        ]
        for name, value in metrics.get("rates").items():
            lines = lines + [f"task_{name} {value}"]
        return "\n".join(lines)

    def reset_metrics(self):
        """메트릭 리셋"""
        self.metrics = TaskMetrics()
        task_history = {}
        metric_history = {}


_global_monitor = None


def get_task_monitor() -> TaskMonitor:
    """전역 작업 모니터 반환"""
    # global _global_monitor - removed for functional programming
    if _global_monitor is None:
        _global_monitor = TaskMonitor()
    return _global_monitor


def get_metrics() -> TaskMetrics:
    """메트릭 조회"""
    return get_task_monitor().get_metrics()


def export_metrics(format="json") -> str:
    """메트릭 내보내기"""
    return get_task_monitor().export_metrics(format)
