"""
Task Monitoring for Async Task Management

작업 모니터링 - 메트릭, 추적, 알림
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import logging
from enum import Enum

from ..core import Result, Success, Failure
from .base import TaskStatus, TaskMetadata, TaskResult

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """메트릭 타입"""
    COUNTER = "counter"  # 카운터
    GAUGE = "gauge"  # 게이지
    HISTOGRAM = "histogram"  # 히스토그램
    SUMMARY = "summary"  # 요약


@dataclass
class TaskMetric:
    """작업 메트릭"""
    name: str
    type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'name': self.name,
            'type': self.type.value,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'labels': self.labels
        }


@dataclass
class TaskMetrics:
    """
    작업 메트릭 컬렉션
    """
    # 카운터
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    timeout_tasks: int = 0
    retried_tasks: int = 0
    
    # 게이지
    active_tasks: int = 0
    queued_tasks: int = 0
    pending_tasks: int = 0
    
    # 타이밍
    total_duration: timedelta = timedelta()
    min_duration: Optional[timedelta] = None
    max_duration: Optional[timedelta] = None
    avg_duration: Optional[timedelta] = None
    
    # 처리량
    tasks_per_second: float = 0.0
    tasks_per_minute: float = 0.0
    
    # 에러율
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    
    # 우선순위별 통계
    priority_stats: Dict[str, int] = field(default_factory=dict)
    
    # 태그별 통계
    tag_stats: Dict[str, int] = field(default_factory=dict)
    
    def update_from_metadata(self, metadata: TaskMetadata):
        """메타데이터로부터 업데이트"""
        self.total_tasks += 1
        
        if metadata.status == TaskStatus.COMPLETED:
            self.successful_tasks += 1
        elif metadata.status == TaskStatus.FAILED:
            self.failed_tasks += 1
        elif metadata.status == TaskStatus.CANCELLED:
            self.cancelled_tasks += 1
        elif metadata.status == TaskStatus.TIMEOUT:
            self.timeout_tasks += 1
        
        if metadata.retry_count > 0:
            self.retried_tasks += 1
        
        # 우선순위 통계
        priority_name = metadata.priority.name
        self.priority_stats[priority_name] = self.priority_stats.get(priority_name, 0) + 1
        
        # 태그 통계
        for tag in metadata.tags:
            self.tag_stats[tag] = self.tag_stats.get(tag, 0) + 1
        
        # 실행 시간 통계
        duration = metadata.duration()
        if duration:
            self.total_duration += duration
            
            if self.min_duration is None or duration < self.min_duration:
                self.min_duration = duration
            
            if self.max_duration is None or duration > self.max_duration:
                self.max_duration = duration
        
        # 에러율 계산
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
            'counters': {
                'total_tasks': self.total_tasks,
                'successful_tasks': self.successful_tasks,
                'failed_tasks': self.failed_tasks,
                'cancelled_tasks': self.cancelled_tasks,
                'timeout_tasks': self.timeout_tasks,
                'retried_tasks': self.retried_tasks
            },
            'gauges': {
                'active_tasks': self.active_tasks,
                'queued_tasks': self.queued_tasks,
                'pending_tasks': self.pending_tasks
            },
            'timing': {
                'total_duration': self.total_duration.total_seconds(),
                'min_duration': self.min_duration.total_seconds() if self.min_duration else None,
                'max_duration': self.max_duration.total_seconds() if self.max_duration else None,
                'avg_duration': self.avg_duration.total_seconds() if self.avg_duration else None
            },
            'throughput': {
                'tasks_per_second': self.tasks_per_second,
                'tasks_per_minute': self.tasks_per_minute
            },
            'rates': {
                'error_rate': self.error_rate,
                'timeout_rate': self.timeout_rate,
                'success_rate': 1 - self.error_rate if self.total_tasks > 0 else 0
            },
            'priority_stats': self.priority_stats,
            'tag_stats': self.tag_stats
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
        self,
        history_size: int = 1000,
        window_size: timedelta = timedelta(minutes=5)
    ):
        self.history_size = history_size
        self.window_size = window_size
        
        # 메트릭
        self.metrics = TaskMetrics()
        self.metric_history: deque = deque(maxlen=history_size)
        
        # 작업 히스토리
        self.task_history: deque = deque(maxlen=history_size)
        
        # 시간별 통계
        self.hourly_stats: Dict[str, TaskMetrics] = {}
        self.daily_stats: Dict[str, TaskMetrics] = {}
        
        # 알림 핸들러
        self.alert_handlers: List[Callable] = []
        
        # 임계값
        self.thresholds = {
            'error_rate': 0.1,  # 10% 에러율
            'timeout_rate': 0.05,  # 5% 타임아웃율
            'queue_size': 1000,  # 큐 크기
            'active_tasks': 100,  # 활성 작업 수
            'avg_duration': timedelta(minutes=5)  # 평균 실행 시간
        }
    
    def record_task_start(self, metadata: TaskMetadata):
        """작업 시작 기록"""
        self.metrics.active_tasks += 1
        
        # 히스토리 추가
        self.task_history.append({
            'task_id': metadata.task_id,
            'name': metadata.name,
            'status': 'started',
            'timestamp': datetime.now(),
            'priority': metadata.priority.name
        })
    
    def record_task_complete(self, result: TaskResult):
        """작업 완료 기록"""
        if result.metadata:
            self.metrics.update_from_metadata(result.metadata)
        
        self.metrics.active_tasks = max(0, self.metrics.active_tasks - 1)
        
        # 히스토리 추가
        self.task_history.append({
            'task_id': result.task_id,
            'status': result.status.value,
            'timestamp': datetime.now(),
            'duration': result.metadata.duration().total_seconds() if result.metadata and result.metadata.duration() else None
        })
        
        # 평균 계산
        self.metrics.calculate_averages()
        
        # 임계값 체크
        self._check_thresholds()
    
    def record_task_error(self, metadata: TaskMetadata, error: Exception):
        """작업 에러 기록"""
        self.metrics.failed_tasks += 1
        self.metrics.active_tasks = max(0, self.metrics.active_tasks - 1)
        
        # 히스토리 추가
        self.task_history.append({
            'task_id': metadata.task_id,
            'name': metadata.name,
            'status': 'error',
            'error': str(error),
            'timestamp': datetime.now()
        })
        
        # 에러율 업데이트
        if self.metrics.total_tasks > 0:
            self.metrics.error_rate = self.metrics.failed_tasks / self.metrics.total_tasks
        
        # 임계값 체크
        self._check_thresholds()
    
    def record_queue_size(self, size: int):
        """큐 크기 기록"""
        self.metrics.queued_tasks = size
        
        # 임계값 체크
        if size > self.thresholds['queue_size']:
            self._trigger_alert('queue_size', size)
    
    def get_metrics(self) -> TaskMetrics:
        """현재 메트릭 조회"""
        return self.metrics
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """메트릭 딕셔너리 조회"""
        return self.metrics.to_dict()
    
    def get_recent_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 작업 조회"""
        return list(self.task_history)[-limit:]
    
    def get_window_metrics(self) -> TaskMetrics:
        """시간 윈도우 메트릭 조회"""
        window_metrics = TaskMetrics()
        now = datetime.now()
        
        for task in self.task_history:
            if 'timestamp' in task:
                task_time = task['timestamp']
                if isinstance(task_time, str):
                    task_time = datetime.fromisoformat(task_time)
                
                if now - task_time <= self.window_size:
                    # 윈도우 내 작업만 포함
                    if task['status'] == 'completed':
                        window_metrics.successful_tasks += 1
                    elif task['status'] == 'error':
                        window_metrics.failed_tasks += 1
                    
                    window_metrics.total_tasks += 1
        
        # 처리량 계산
        window_seconds = self.window_size.total_seconds()
        if window_seconds > 0:
            window_metrics.tasks_per_second = window_metrics.total_tasks / window_seconds
            window_metrics.tasks_per_minute = window_metrics.total_tasks / (window_seconds / 60)
        
        return window_metrics
    
    def add_alert_handler(self, handler: Callable[[str, Any], None]):
        """알림 핸들러 추가"""
        self.alert_handlers.append(handler)
    
    def set_threshold(self, name: str, value: Any):
        """임계값 설정"""
        self.thresholds[name] = value
    
    def _check_thresholds(self):
        """임계값 체크"""
        # 에러율 체크
        if self.metrics.error_rate > self.thresholds['error_rate']:
            self._trigger_alert('error_rate', self.metrics.error_rate)
        
        # 타임아웃율 체크
        if self.metrics.timeout_rate > self.thresholds['timeout_rate']:
            self._trigger_alert('timeout_rate', self.metrics.timeout_rate)
        
        # 활성 작업 수 체크
        if self.metrics.active_tasks > self.thresholds['active_tasks']:
            self._trigger_alert('active_tasks', self.metrics.active_tasks)
        
        # 평균 실행 시간 체크
        if self.metrics.avg_duration and self.metrics.avg_duration > self.thresholds['avg_duration']:
            self._trigger_alert('avg_duration', self.metrics.avg_duration)
    
    def _trigger_alert(self, alert_type: str, value: Any):
        """알림 트리거"""
        logger.warning(f"Alert: {alert_type} threshold exceeded: {value}")
        
        for handler in self.alert_handlers:
            try:
                handler(alert_type, value)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
    
    def export_metrics(self, format: str = 'json') -> str:
        """메트릭 내보내기"""
        metrics_dict = self.get_metrics_dict()
        
        if format == 'json':
            return json.dumps(metrics_dict, indent=2, default=str)
        elif format == 'prometheus':
            return self._format_prometheus(metrics_dict)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _format_prometheus(self, metrics: Dict[str, Any]) -> str:
        """Prometheus 형식으로 포맷"""
        lines = []
        
        # 카운터
        for name, value in metrics['counters'].items():
            lines.append(f"task_{name} {value}")
        
        # 게이지
        for name, value in metrics['gauges'].items():
            lines.append(f"task_{name}_current {value}")
        
        # 타이밍
        if metrics['timing']['avg_duration']:
            lines.append(f"task_duration_seconds {metrics['timing']['avg_duration']}")
        
        # 처리량
        lines.append(f"task_throughput_per_second {metrics['throughput']['tasks_per_second']}")
        
        # 비율
        for name, value in metrics['rates'].items():
            lines.append(f"task_{name} {value}")
        
        return '\n'.join(lines)
    
    def reset_metrics(self):
        """메트릭 리셋"""
        self.metrics = TaskMetrics()
        self.task_history.clear()
        self.metric_history.clear()


# 전역 모니터
_global_monitor: Optional[TaskMonitor] = None


def get_task_monitor() -> TaskMonitor:
    """전역 작업 모니터 반환"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = TaskMonitor()
    return _global_monitor


def get_metrics() -> TaskMetrics:
    """메트릭 조회"""
    return get_task_monitor().get_metrics()


def export_metrics(format: str = 'json') -> str:
    """메트릭 내보내기"""
    return get_task_monitor().export_metrics(format)