"""
Result 패턴 통합 메트릭 시스템

실시간 성능 데이터 수집, 알림 관리, 모니터링 대시보드 API를 제공합니다.
임계값 기반 자동 알림과 상세한 성능 분석을 지원합니다.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Union
import json
import logging

from rfs.core.result import Result

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """메트릭 타입"""
    COUNTER = "counter"           # 증가만 하는 값 (요청 수, 에러 수 등)
    GAUGE = "gauge"              # 현재 상태 값 (메모리 사용량, 활성 연결 수 등)
    HISTOGRAM = "histogram"       # 분포 데이터 (응답 시간, 데이터 크기 등)
    TIMER = "timer"              # 시간 측정 (작업 처리 시간)


class AlertCondition(str, Enum):
    """알림 조건"""
    GREATER_THAN = "gt"          # 초과
    LESS_THAN = "lt"             # 미만
    EQUAL = "eq"                 # 같음
    NOT_EQUAL = "ne"             # 같지 않음


@dataclass
class MetricData:
    """메트릭 데이터"""
    name: str
    type: MetricType
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "metadata": self.metadata
        }


class ResultMetricsCollector:
    """Result 패턴 메트릭 수집기"""
    
    def __init__(self, max_history_size: int = 10000):
        self.max_history_size = max_history_size
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history_size))
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()
        
        # 성능 최적화를 위한 배치 처리
        self._batch_metrics: List[MetricData] = []
        self._batch_size = 100
        self._last_flush = time.time()
        self._flush_interval = 1.0  # 1초마다 배치 플러시
    
    def collect_metric(
        self, 
        name: str, 
        value: float, 
        metric_type: MetricType,
        labels: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """메트릭 수집"""
        metric = MetricData(
            name=name,
            type=metric_type,
            value=value,
            timestamp=datetime.now(),
            labels=labels or {},
            metadata=metadata or {}
        )
        
        with self._lock:
            # 배치에 추가
            self._batch_metrics.append(metric)
            
            # 즉시 로컬 저장소 업데이트
            self._update_local_storage(metric)
            
            # 배치 플러시 확인
            if (len(self._batch_metrics) >= self._batch_size or 
                time.time() - self._last_flush > self._flush_interval):
                self._flush_batch()
    
    def _update_local_storage(self, metric: MetricData):
        """로컬 저장소 업데이트"""
        key = f"{metric.name}:{json.dumps(metric.labels, sort_keys=True)}"
        
        # 히스토리 저장
        self._metrics[key].append(metric)
        
        # 타입별 저장
        if metric.type == MetricType.COUNTER:
            self._counters[key] += metric.value
        elif metric.type == MetricType.GAUGE:
            self._gauges[key] = metric.value
        elif metric.type == MetricType.HISTOGRAM:
            self._histograms[key].append(metric.value)
            # 히스토그램 크기 제한
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
        elif metric.type == MetricType.TIMER:
            self._timers[key].append(metric.value)
            if len(self._timers[key]) > 1000:
                self._timers[key] = self._timers[key][-1000:]
    
    def _flush_batch(self):
        """배치 메트릭 플러시"""
        if not self._batch_metrics:
            return
        
        # 외부 시스템으로 메트릭 전송 (예: Prometheus, InfluxDB)
        # 여기서는 로깅으로 대체
        logger.debug(f"메트릭 배치 플러시: {len(self._batch_metrics)}개 메트릭")
        
        self._batch_metrics.clear()
        self._last_flush = time.time()
    
    def get_metric_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """최신 메트릭 값 조회"""
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        
        with self._lock:
            if key in self._counters:
                return self._counters[key]
            elif key in self._gauges:
                return self._gauges[key]
            elif key in self._metrics:
                metrics = self._metrics[key]
                return metrics[-1].value if metrics else None
        
        return None
    
    def get_metrics_summary(self, time_range_minutes: int = 60) -> Dict[str, Any]:
        """메트릭 요약 정보 조회"""
        with self._lock:
            summary = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
                "timers": {},
                "time_range_minutes": time_range_minutes,
                "generated_at": datetime.now().isoformat()
            }
            
            # 히스토그램 요약
            for key, values in self._histograms.items():
                if values:
                    sorted_values = sorted(values)
                    n = len(sorted_values)
                    summary["histograms"][key] = {
                        "count": n,
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / n,
                        "p50": sorted_values[n // 2],
                        "p90": sorted_values[int(n * 0.9)],
                        "p95": sorted_values[int(n * 0.95)],
                        "p99": sorted_values[int(n * 0.99)]
                    }
            
            # 타이머 요약
            for key, values in self._timers.items():
                if values:
                    sorted_values = sorted(values)
                    n = len(sorted_values)
                    summary["timers"][key] = {
                        "count": n,
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / n,
                        "p50": sorted_values[n // 2],
                        "p90": sorted_values[int(n * 0.9)],
                        "p95": sorted_values[int(n * 0.95)],
                        "p99": sorted_values[int(n * 0.99)]
                    }
            
            return summary
    
    def clear_metrics(self):
        """모든 메트릭 삭제"""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._batch_metrics.clear()
        
        logger.info("모든 메트릭이 삭제되었습니다")


class ResultAlertManager:
    """Result 패턴 알림 관리자"""
    
    def __init__(self, metrics_collector: ResultMetricsCollector):
        self.metrics_collector = metrics_collector
        self._alert_rules: Dict[str, Dict[str, Any]] = {}
        self._active_alerts: List[Dict[str, Any]] = []
        self._lock = Lock()
        self._monitoring_active = False
        logger.info("ResultAlertManager 초기화됨")
    
    def add_alert_rule(
        self, 
        name: str, 
        metric_name: str, 
        condition: AlertCondition, 
        threshold: float,
        callback: Optional[Callable] = None
    ):
        """알림 규칙 추가"""
        with self._lock:
            self._alert_rules[name] = {
                "metric_name": metric_name,
                "condition": condition,
                "threshold": threshold,
                "callback": callback,
                "enabled": True
            }
        
        logger.info(f"알림 규칙 추가됨: {name}")
    
    def get_alert_rules(self) -> List[Dict[str, Any]]:
        """알림 규칙 목록 조회"""
        with self._lock:
            return [
                {
                    "name": name,
                    "metric_name": rule["metric_name"],
                    "condition": rule["condition"].value if hasattr(rule["condition"], 'value') else str(rule["condition"]),
                    "threshold": rule["threshold"],
                    "enabled": rule["enabled"]
                }
                for name, rule in self._alert_rules.items()
            ]
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """활성 알림 목록 조회"""
        with self._lock:
            return self._active_alerts.copy()
    
    def start_monitoring(self):
        """모니터링 시작"""
        self._monitoring_active = True
        logger.info("알림 모니터링이 시작되었습니다")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self._monitoring_active = False
        logger.info("알림 모니터링이 중지되었습니다")


# 전역 인스턴스
_metrics_collector = ResultMetricsCollector()
_alert_manager = ResultAlertManager(_metrics_collector)


# 편의 함수들

def collect_metric(
    name: str, 
    value: float, 
    metric_type: MetricType = MetricType.GAUGE,
    labels: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """메트릭 수집 편의 함수"""
    _metrics_collector.collect_metric(name, value, metric_type, labels, metadata)


def create_alert_rule(
    name: str,
    metric_name: str,
    condition: AlertCondition,
    threshold: float,
    callback: Optional[Callable] = None
):
    """알림 규칙 생성 편의 함수"""
    _alert_manager.add_alert_rule(name, metric_name, condition, threshold, callback)


def get_metrics_summary(time_range_minutes: int = 60) -> Dict[str, Any]:
    """메트릭 요약 조회 편의 함수"""
    return _metrics_collector.get_metrics_summary(time_range_minutes)


def start_monitoring():
    """모니터링 시작 편의 함수"""
    _alert_manager.start_monitoring()


def stop_monitoring():
    """모니터링 중지 편의 함수"""
    _alert_manager.stop_monitoring()


# Result 패턴 전용 메트릭 헬퍼들

def collect_result_metric(operation_name: str, result: Result, duration_ms: float):
    """Result 전용 메트릭 수집"""
    labels = {"operation": operation_name}
    
    # 성공/실패 카운터
    if result.is_success():
        collect_metric("result_success_total", 1, MetricType.COUNTER, labels)
    else:
        collect_metric("result_failure_total", 1, MetricType.COUNTER, labels)
        
        # 에러 타입별 카운터
        error = result.unwrap_error()
        error_labels = {**labels, "error_type": type(error).__name__}
        collect_metric("result_error_by_type_total", 1, MetricType.COUNTER, error_labels)
    
    # 처리 시간 히스토그램
    collect_metric("result_duration_ms", duration_ms, MetricType.HISTOGRAM, labels)
    
    # 현재 처리 중인 작업 수 (게이지)
    collect_metric("result_operations_active", 1, MetricType.GAUGE, labels)


def collect_flux_result_metric(operation_name: str, flux_result: Any, duration_ms: float):
    """FluxResult 전용 메트릭 수집"""
    labels = {"operation": operation_name}
    
    total = flux_result.count_total()
    success = flux_result.count_success()
    failure = flux_result.count_failures()
    
    # 배치 처리 메트릭
    collect_metric("flux_result_total_items", total, MetricType.COUNTER, labels)
    collect_metric("flux_result_success_items", success, MetricType.COUNTER, labels)
    collect_metric("flux_result_failure_items", failure, MetricType.COUNTER, labels)
    collect_metric("flux_result_duration_ms", duration_ms, MetricType.HISTOGRAM, labels)
    
    # 성공률 게이지
    success_rate = success / total if total > 0 else 0
    collect_metric("flux_result_success_rate", success_rate, MetricType.GAUGE, labels)


# 사전 정의된 알림 규칙들

def setup_default_alerts():
    """기본 알림 규칙 설정"""
    
    # 높은 실패율 알림
    create_alert_rule(
        name="high_failure_rate",
        metric_name="result_failure_total",
        condition=AlertCondition.GREATER_THAN,
        threshold=10.0
    )
    
    # 느린 응답 시간 알림
    create_alert_rule(
        name="slow_response_time",
        metric_name="result_duration_ms",
        condition=AlertCondition.GREATER_THAN,
        threshold=5000.0  # 5초
    )
    
    # 낮은 배치 성공률 알림
    create_alert_rule(
        name="low_batch_success_rate",
        metric_name="flux_result_success_rate",
        condition=AlertCondition.LESS_THAN,
        threshold=0.8  # 80%
    )
    
    logger.info("기본 알림 규칙이 설정되었습니다")


# 메트릭 대시보드 API 헬퍼

def get_dashboard_data() -> Dict[str, Any]:
    """대시보드용 종합 데이터 조회"""
    return {
        "metrics_summary": get_metrics_summary(60),
        "active_alerts": _alert_manager.get_active_alerts(),
        "alert_rules": _alert_manager.get_alert_rules(),
        "system_status": {
            "monitoring_active": _alert_manager._monitoring_active,
            "total_metrics": len(_metrics_collector._metrics),
            "timestamp": datetime.now().isoformat()
        }
    }