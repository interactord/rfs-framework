"""
Scaling Optimization Engine for RFS Framework

스케일링 최적화, 자동 스케일링, 예측 스케일링
- 수평/수직 스케일링 결정
- 트래픽 패턴 기반 예측 스케일링
- 리소스 사용률 기반 자동 스케일링
- 비용 효율적인 스케일링 전략
"""

import asyncio
import json
import math
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from rfs.core.config import get_config
from rfs.core.result import Failure, Result, Success
from rfs.events.event import Event
from rfs.reactive.mono import Mono


class ScalingDirection(Enum):
    """스케일링 방향"""
    UP = "up"          # 스케일 업
    DOWN = "down"      # 스케일 다운
    STABLE = "stable"  # 안정상태

class ScalingType(Enum):
    """스케일링 유형"""
    HORIZONTAL = "horizontal"  # 수평 스케일링 (인스턴스 수)
    VERTICAL = "vertical"      # 수직 스케일링 (리소스 크기)
    HYBRID = "hybrid"          # 하이브리드 스케일링

class ScalingStrategy(Enum):
    """스케일링 전략"""
    REACTIVE = "reactive"      # 반응형 스케일링
    PREDICTIVE = "predictive"  # 예측형 스케일링
    SCHEDULED = "scheduled"    # 스케줄 기반 스케일링
    COST_OPTIMIZED = "cost"    # 비용 최적화

class MetricType(Enum):
    """메트릭 유형"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    REQUEST_RATE = "request_rate"
    RESPONSE_TIME = "response_time"
    QUEUE_DEPTH = "queue_depth"
    ERROR_RATE = "error_rate"
    CUSTOM = "custom"

@dataclass
class ScalingThresholds:
    """스케일링 임계값"""
    cpu_scale_up_percent: float = 70.0        # CPU 스케일업 임계값
    cpu_scale_down_percent: float = 30.0      # CPU 스케일다운 임계값
    memory_scale_up_percent: float = 80.0     # 메모리 스케일업 임계값
    memory_scale_down_percent: float = 40.0   # 메모리 스케일다운 임계값
    request_rate_scale_up: float = 1000.0     # 요청률 스케일업 임계값
    response_time_scale_up_ms: float = 2000.0 # 응답시간 스케일업 임계값
    error_rate_scale_up_percent: float = 5.0  # 에러율 스케일업 임계값
    min_instances: int = 1                    # 최소 인스턴스 수
    max_instances: int = 10                   # 최대 인스턴스 수
    scale_up_cooldown_seconds: float = 300.0  # 스케일업 쿨다운
    scale_down_cooldown_seconds: float = 600.0 # 스케일다운 쿨다운

@dataclass
class ResourceMetrics:
    """리소스 메트릭"""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    request_rate_per_second: float
    avg_response_time_ms: float
    error_rate_percent: float
    queue_depth: int
    active_connections: int
    instance_count: int
    custom_metrics: Dict[str, float] = field(default_factory=dict)

@dataclass
class ScalingDecision:
    """스케일링 결정"""
    direction: ScalingDirection
    scaling_type: ScalingType
    current_instances: int
    target_instances: int
    reason: str
    confidence_score: float
    estimated_cost_impact: float
    estimated_performance_impact: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class AutoScalingConfig:
    """자동 스케일링 설정"""
    strategy: ScalingStrategy = ScalingStrategy.REACTIVE
    scaling_type: ScalingType = ScalingType.HORIZONTAL
    thresholds: ScalingThresholds = field(default_factory=ScalingThresholds)
    enable_predictive_scaling: bool = True
    enable_cost_optimization: bool = True
    monitoring_interval_seconds: float = 30.0
    decision_window_minutes: int = 5
    confidence_threshold: float = 0.7

class MetricCollector:
    """메트릭 수집기"""
    
    def __init__(self):
        self.metrics_history: deque = deque(maxlen=1000)
        self.custom_collectors: Dict[str, Callable] = {}
        self.lock = threading.Lock()
    
    def add_metric(self, metrics: ResourceMetrics) -> None:
        """메트릭 추가"""
        with self.lock:
            self.metrics_history = metrics_history + [metrics]
    
    def register_custom_collector(self, name: str, collector_func: Callable[[], float]) -> None:
        """커스텀 메트릭 수집기 등록"""
        self.custom_collectors = {**self.custom_collectors, name: collector_func}
    
    def get_recent_metrics(self, minutes: int = 5) -> List[ResourceMetrics]:
        """최근 메트릭 조회"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self.lock:
            return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_metric_trend(self, metric_type: MetricType, minutes: int = 10) -> List[float]:
        """메트릭 트렌드 분석"""
        recent_metrics = self.get_recent_metrics(minutes)
        
        values = []
        for metric in recent_metrics:
            match metric_type:
                case MetricType.CPU_USAGE:
                    values = values + [metric.cpu_usage_percent]
                case MetricType.MEMORY_USAGE:                values = values + [metric.memory_usage_percent]
                case MetricType.REQUEST_RATE:                values = values + [metric.request_rate_per_second]
                case MetricType.RESPONSE_TIME:                values = values + [metric.avg_response_time_ms]
                case MetricType.ERROR_RATE:                values = values + [metric.error_rate_percent]
                case MetricType.QUEUE_DEPTH:                values = values + [float(metric.queue_depth])
        
        return values
    
    def calculate_metric_statistics(self, metric_type: MetricType, minutes: int = 5) -> Dict[str, float]:
        """메트릭 통계 계산"""
        values = self.get_metric_trend(metric_type, minutes)
        
        if not values:
            return {}
        
        return {
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'min': min(values),
            'max': max(values),
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0.0,
            'trend': self._calculate_trend(values)
        }
    
    def _calculate_trend(self, values: List[float]) -> float:
        """트렌드 계산 (선형 회귀 기울기)"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        # 선형 회귀 기울기
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        return slope

class PredictiveScaling:
    """예측 스케일링"""
    
    def __init__(self):
        self.historical_patterns: Dict[str, List[float]] = defaultdict(list)
        self.seasonal_patterns: Dict[int, List[float]] = defaultdict(list)  # hour -> values
        self.weekly_patterns: Dict[int, List[float]] = defaultdict(list)    # weekday -> values
        self.prediction_accuracy: deque = deque(maxlen=100)
    
    def learn_from_metrics(self, metrics: ResourceMetrics) -> None:
        """메트릭에서 패턴 학습"""
        hour = metrics.timestamp.hour
        weekday = metrics.timestamp.weekday()
        
        # 시간대별 패턴
        self.seasonal_patterns[hour] = seasonal_patterns[hour] + [metrics.cpu_usage_percent]
        if len(self.seasonal_patterns[hour]) > 100:  # 최근 100개만 유지
            self.seasonal_patterns = {**self.seasonal_patterns, hour: self.seasonal_patterns[hour][-100:]}
        
        # 요일별 패턴
        self.weekly_patterns[weekday] = weekly_patterns[weekday] + [metrics.request_rate_per_second]
        if len(self.weekly_patterns[weekday]) > 100:
            self.weekly_patterns = {**self.weekly_patterns, weekday: self.weekly_patterns[weekday][-100:]}
    
    def predict_future_load(self, minutes_ahead: int = 15) -> Dict[str, float]:
        """미래 부하 예측"""
        future_time = datetime.now() + timedelta(minutes=minutes_ahead)
        future_hour = future_time.hour
        future_weekday = future_time.weekday()
        
        predictions = {}
        
        # CPU 사용률 예측 (시간대 기반)
        if future_hour in self.seasonal_patterns:
            cpu_values = self.seasonal_patterns[future_hour]
            if cpu_values:
                predictions['cpu_usage_percent'] = statistics.mean(cpu_values)
        
        # 요청률 예측 (요일 기반)
        if future_weekday in self.weekly_patterns:
            request_values = self.weekly_patterns[future_weekday]
            if request_values:
                predictions['request_rate_per_second'] = statistics.mean(request_values)
        
        return predictions
    
    def calculate_prediction_confidence(self, metric_type: str) -> float:
        """예측 신뢰도 계산"""
        if metric_type == 'cpu_usage_percent':
            current_hour = datetime.now().hour
            if current_hour in self.seasonal_patterns:
                values = self.seasonal_patterns[current_hour]
                if len(values) > 10:
                    std_dev = statistics.stdev(values)
                    mean_val = statistics.mean(values)
                    # 변동계수의 역수로 신뢰도 계산
                    cv = std_dev / max(mean_val, 1.0)
                    confidence = max(0.0, min(1.0, 1.0 - cv))
                    return confidence
        
        return 0.5  # 기본 신뢰도

class ScalingDecisionEngine:
    """스케일링 결정 엔진"""
    
    def __init__(self, config: AutoScalingConfig):
        self.config = config
        self.last_scale_up_time: Optional[datetime] = None
        self.last_scale_down_time: Optional[datetime] = None
        self.decision_history: deque = deque(maxlen=100)
    
    def make_scaling_decision(self, current_metrics: ResourceMetrics, 
                            metric_stats: Dict[MetricType, Dict[str, float]],
                            predictions: Dict = {str, float: None) -> ScalingDecision:}
        """스케일링 결정 생성"""
        
        # 쿨다운 체크
        if not self._can_scale():
            return ScalingDecision(
                direction=ScalingDirection.STABLE,
                scaling_type=self.config.scaling_type,
                current_instances=current_metrics.instance_count,
                target_instances=current_metrics.instance_count,
                reason="In cooldown period",
                confidence_score=1.0,
                estimated_cost_impact=0.0,
                estimated_performance_impact=0.0
            )
        
        # 스케일링 필요성 분석
        scale_up_signals = self._analyze_scale_up_signals(current_metrics, metric_stats, predictions)
        scale_down_signals = self._analyze_scale_down_signals(current_metrics, metric_stats, predictions)
        
        # 결정 생성
        if scale_up_signals['score'] > scale_down_signals['score']:
            direction = ScalingDirection.UP
            target_instances = min(
                current_metrics.instance_count + 1,
                self.config.thresholds.max_instances
            )
            reason = f"Scale up: {scale_up_signals['reason']}"
            confidence = scale_up_signals['confidence']
        elif scale_down_signals['score'] > 0.7:  # 스케일 다운은 더 신중하게
            direction = ScalingDirection.DOWN
            target_instances = max(
                current_metrics.instance_count - 1,
                self.config.thresholds.min_instances
            )
            reason = f"Scale down: {scale_down_signals['reason']}"
            confidence = scale_down_signals['confidence']
        else:
            direction = ScalingDirection.STABLE
            target_instances = current_metrics.instance_count
            reason = "No scaling needed"
            confidence = 1.0
        
        # 비용 및 성능 영향 추정
        cost_impact = self._estimate_cost_impact(current_metrics.instance_count, target_instances)
        performance_impact = self._estimate_performance_impact(direction, current_metrics)
        
        decision = ScalingDecision(
            direction=direction,
            scaling_type=self.config.scaling_type,
            current_instances=current_metrics.instance_count,
            target_instances=target_instances,
            reason=reason,
            confidence_score=confidence,
            estimated_cost_impact=cost_impact,
            estimated_performance_impact=performance_impact
        )
        
        self.decision_history = decision_history + [decision]
        return decision
    
    def _can_scale(self) -> bool:
        """스케일링 가능 여부 확인 (쿨다운)"""
        now = datetime.now()
        
        if (self.last_scale_up_time and 
            (now - self.last_scale_up_time).total_seconds() < self.config.thresholds.scale_up_cooldown_seconds):
            return False
        
        if (self.last_scale_down_time and 
            (now - self.last_scale_down_time).total_seconds() < self.config.thresholds.scale_down_cooldown_seconds):
            return False
        
        return True
    
    def _analyze_scale_up_signals(self, metrics: ResourceMetrics, 
                                metric_stats: Dict[MetricType, Dict[str, float]],
                                predictions: Dict = {str, float: None) -> Dict[str, Any]:}
        """스케일업 신호 분석"""
        signals = []
        reasons = []
        
        # CPU 사용률 체크
        cpu_stats = metric_stats.get(MetricType.CPU_USAGE, {})
        if cpu_stats.get('mean', 0) > self.config.thresholds.cpu_scale_up_percent:
            signals = signals + [0.8]
            reasons = reasons + [f"High CPU usage: {cpu_stats.get('mean', 0]:.1f}%")
        
        # 메모리 사용률 체크
        memory_stats = metric_stats.get(MetricType.MEMORY_USAGE, {})
        if memory_stats.get('mean', 0) > self.config.thresholds.memory_scale_up_percent:
            signals = signals + [0.7]
            reasons = reasons + [f"High memory usage: {memory_stats.get('mean', 0]:.1f}%")
        
        # 응답 시간 체크
        response_stats = metric_stats.get(MetricType.RESPONSE_TIME, {})\n        if response_stats.get('mean', 0) > self.config.thresholds.response_time_scale_up_ms:\n            signals = signals + [0.9]\n            reasons = reasons + [f\"High response time: {response_stats.get('mean', 0]:.1f}ms\")\n        \n        # 에러율 체크\n        error_stats = metric_stats.get(MetricType.ERROR_RATE, {})\n        if error_stats.get('mean', 0) > self.config.thresholds.error_rate_scale_up_percent:\n            signals = signals + [0.95]\n            reasons = reasons + [f\"High error rate: {error_stats.get('mean', 0]:.1f}%\")\n        \n        # 큐 깊이 체크\n        if metrics.queue_depth > 50:  # 임계값\n            signals = signals + [0.8]\n            reasons = reasons + [f\"High queue depth: {metrics.queue_depth}\"]\n        \n        # 예측 기반 신호\n        if predictions and self.config.enable_predictive_scaling:\n            predicted_cpu = predictions.get('cpu_usage_percent', 0)\n            if predicted_cpu > self.config.thresholds.cpu_scale_up_percent:\n                signals = signals + [0.6]  # 예측은 낮은 가중치\n                reasons = reasons + [f\"Predicted high CPU: {predicted_cpu:.1f}%\"]\n        \n        # 트렌드 기반 신호\n        cpu_trend = cpu_stats.get('trend', 0)\n        if cpu_trend > 5:  # 급격한 증가 트렌드\n            signals = signals + [0.5]\n            reasons = reasons + [\"Increasing CPU trend\"]\n        \n        if not signals:\n            return {'score': 0.0, 'confidence': 0.0, 'reason': 'No scale up signals'}\n        \n        score = max(signals)  # 가장 강한 신호 사용\n        confidence = sum(signals) / len(signals)  # 평균 신뢰도\n        reason = '; '.join(reasons[:2])  # 상위 2개 이유\n        \n        return {'score': score, 'confidence': confidence, 'reason': reason}\n    \n    def _analyze_scale_down_signals(self, metrics: ResourceMetrics,\n                                  metric_stats: Dict[MetricType, Dict[str, float]],\n                                  predictions: Dict[str, float] = None) -> Dict[str, Any]:\n        \"\"\"스케일다운 신호 분석\"\"\"\n        signals = []\n        reasons = []\n        \n        # 최소 인스턴스 수 체크\n        if metrics.instance_count <= self.config.thresholds.min_instances:\n            return {'score': 0.0, 'confidence': 0.0, 'reason': 'At minimum instances'}\n        \n        # CPU 사용률 체크\n        cpu_stats = metric_stats.get(MetricType.CPU_USAGE, {})\n        if cpu_stats.get('mean', 100) < self.config.thresholds.cpu_scale_down_percent:\n            signals = signals + [0.7]\n            reasons = reasons + [f\"Low CPU usage: {cpu_stats.get('mean', 0]:.1f}%\")\n        \n        # 메모리 사용률 체크\n        memory_stats = metric_stats.get(MetricType.MEMORY_USAGE, {})\n        if memory_stats.get('mean', 100) < self.config.thresholds.memory_scale_down_percent:\n            signals = signals + [0.6]\n            reasons = reasons + [f\"Low memory usage: {memory_stats.get('mean', 0]:.1f}%\")\n        \n        # 요청률이 낮은 경우\n        request_stats = metric_stats.get(MetricType.REQUEST_RATE, {})\n        if request_stats.get('mean', float('inf')) < self.config.thresholds.request_rate_scale_up / 2:\n            signals = signals + [0.5]\n            reasons = reasons + [\"Low request rate\"]\n        \n        # 응답 시간이 충분히 낮은 경우\n        response_stats = metric_stats.get(MetricType.RESPONSE_TIME, {})\n        if response_stats.get('mean', float('inf')) < self.config.thresholds.response_time_scale_up_ms / 2:\n            signals = signals + [0.4]\n            reasons = reasons + [\"Low response time\"]\n        \n        # 모든 메트릭이 안정적인 경우\n        all_stable = (\n            cpu_stats.get('std_dev', float('inf')) < 10 and  # 낮은 변동성\n            memory_stats.get('std_dev', float('inf')) < 10 and\n            response_stats.get('std_dev', float('inf')) < 500\n        )\n        if all_stable:\n            signals = signals + [0.3]\n            reasons = reasons + [\"All metrics stable\"]\n        \n        if not signals:\n            return {'score': 0.0, 'confidence': 0.0, 'reason': 'No scale down signals'}\n        \n        # 스케일 다운은 더 보수적으로\n        score = min(max(signals), 0.8)  # 최대 0.8로 제한\n        confidence = sum(signals) / len(signals)\n        reason = '; '.join(reasons[:2])\n        \n        return {'score': score, 'confidence': confidence, 'reason': reason}\n    \n    def _estimate_cost_impact(self, current_instances: int, target_instances: int) -> float:\n        \"\"\"비용 영향 추정\"\"\"\n        instance_diff = target_instances - current_instances\n        \n        # 인스턴스당 시간당 비용 (예시: $0.10)\n        cost_per_instance_per_hour = 0.10\n        \n        # 시간당 비용 변화\n        hourly_cost_change = instance_diff * cost_per_instance_per_hour\n        \n        # 일일 비용 변화로 반환\n        return hourly_cost_change * 24\n    \n    def _estimate_performance_impact(self, direction: ScalingDirection, \n                                   metrics: ResourceMetrics) -> float:\n        \"\"\"성능 영향 추정 (0-100, 양수는 개선, 음수는 저하)\"\"\"\n        if direction == ScalingDirection.UP:\n            # 스케일 업 시 성능 개선 추정\n            current_cpu = metrics.cpu_usage_percent\n            if current_cpu > 80:\n                return 30.0  # 높은 개선\n            elif current_cpu > 60:\n                return 20.0  # 중간 개선\n            else:\n                return 10.0  # 낮은 개선\n                \n        elif direction == ScalingDirection.DOWN:\n            # 스케일 다운 시 성능 저하 위험 추정\n            current_cpu = metrics.cpu_usage_percent\n            if current_cpu < 20:\n                return -5.0   # 낮은 위험\n            elif current_cpu < 40:\n                return -10.0  # 중간 위험\n            else:\n                return -20.0  # 높은 위험\n        \n        return 0.0  # 안정 상태\n    \n    def record_scaling_action(self, direction: ScalingDirection) -> None:\n        \"\"\"스케일링 액션 기록\"\"\"\n        now = datetime.now()\n        if direction == ScalingDirection.UP:\n            self.last_scale_up_time = now\n        elif direction == ScalingDirection.DOWN:\n            self.last_scale_down_time = now\n    \n    def get_decision_statistics(self) -> Dict[str, Any]:\n        \"\"\"결정 통계\"\"\"\n        if not self.decision_history:\n            return {}\n        \n        total_decisions = len(self.decision_history)\n        scale_up_count = sum(1 for d in self.decision_history if d.direction == ScalingDirection.UP)\n        scale_down_count = sum(1 for d in self.decision_history if d.direction == ScalingDirection.DOWN)\n        stable_count = total_decisions - scale_up_count - scale_down_count\n        \n        avg_confidence = sum(d.confidence_score for d in self.decision_history) / total_decisions\n        \n        return {\n            'total_decisions': total_decisions,\n            'scale_up_count': scale_up_count,\n            'scale_down_count': scale_down_count,\n            'stable_count': stable_count,\n            'avg_confidence': avg_confidence,\n            'scale_up_ratio': scale_up_count / total_decisions,\n            'scale_down_ratio': scale_down_count / total_decisions\n        }\n\nclass ResourcePrediction:\n    \"\"\"리소스 예측\"\"\"\n    \n    def __init__(self):\n        self.prediction_models: Dict[str, Any] = {}\n        self.prediction_history: deque = deque(maxlen=1000)\n        self.accuracy_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))\n    \n    def predict_resource_needs(self, current_metrics: ResourceMetrics,\n                             historical_metrics: List[ResourceMetrics],\n                             time_horizon_minutes: int = 15) -> Dict[str, Any]:\n        \"\"\"리소스 요구사항 예측\"\"\"\n        \n        predictions = {\n            'cpu_usage_percent': self._predict_cpu_usage(historical_metrics, time_horizon_minutes),\n            'memory_usage_percent': self._predict_memory_usage(historical_metrics, time_horizon_minutes),\n            'request_rate_per_second': self._predict_request_rate(historical_metrics, time_horizon_minutes),\n            'recommended_instances': self._predict_instance_count(current_metrics, historical_metrics)\n        }\n        \n        # 예측 신뢰도 계산\n        predictions['confidence'] = self._calculate_prediction_confidence(predictions)\n        \n        # 예측 기록\n        prediction_record = {\n            'timestamp': datetime.now(),\n            'predictions': predictions,\n            'current_metrics': current_metrics\n        }\n        self.prediction_history = prediction_history + [prediction_record]\n        \n        return predictions\n    \n    def _predict_cpu_usage(self, historical_metrics: List[ResourceMetrics], \n                          time_horizon_minutes: int) -> float:\n        \"\"\"CPU 사용률 예측\"\"\"\n        if len(historical_metrics) < 3:\n            return historical_metrics[-1].cpu_usage_percent if historical_metrics else 50.0\n        \n        # 단순 선형 예측\n        recent_values = [m.cpu_usage_percent for m in historical_metrics[-10:]]\n        \n        # 이동 평균과 트렌드 계산\n        if len(recent_values) >= 2:\n            trend = (recent_values[-1] - recent_values[0]) / len(recent_values)\n            predicted_value = recent_values[-1] + (trend * time_horizon_minutes / 5)  # 5분 간격 가정\n            return max(0.0, min(100.0, predicted_value))\n        \n        return recent_values[-1] if recent_values else 50.0\n    \n    def _predict_memory_usage(self, historical_metrics: List[ResourceMetrics],\n                             time_horizon_minutes: int) -> float:\n        \"\"\"메모리 사용률 예측\"\"\"\n        if len(historical_metrics) < 3:\n            return historical_metrics[-1].memory_usage_percent if historical_metrics else 50.0\n        \n        # 메모리는 보통 더 안정적이므로 이동 평균 사용\n        recent_values = [m.memory_usage_percent for m in historical_metrics[-5:]]\n        return statistics.mean(recent_values) if recent_values else 50.0\n    \n    def _predict_request_rate(self, historical_metrics: List[ResourceMetrics],\n                             time_horizon_minutes: int) -> float:\n        \"\"\"요청률 예측\"\"\"\n        if len(historical_metrics) < 3:\n            return historical_metrics[-1].request_rate_per_second if historical_metrics else 100.0\n        \n        # 요청률은 변동이 클 수 있으므로 가중 이동 평균 사용\n        recent_values = [m.request_rate_per_second for m in historical_metrics[-10:]]\n        \n        if len(recent_values) >= 2:\n            # 가중치: 최근 값에 더 높은 가중치\n            weights = [i + 1 for i in range(len(recent_values))]\n            weighted_avg = sum(v * w for v, w in zip(recent_values, weights)) / sum(weights)\n            return max(0.0, weighted_avg)\n        \n        return recent_values[-1] if recent_values else 100.0\n    \n    def _predict_instance_count(self, current_metrics: ResourceMetrics,\n                              historical_metrics: List[ResourceMetrics]) -> int:\n        \"\"\"인스턴스 수 예측\"\"\"\n        # CPU와 메모리 예측값을 기반으로 필요한 인스턴스 수 계산\n        predicted_cpu = self._predict_cpu_usage(historical_metrics, 15)\n        predicted_memory = self._predict_memory_usage(historical_metrics, 15)\n        \n        # 현재 인스턴스당 평균 부하\n        current_instances = current_metrics.instance_count\n        if current_instances == 0:\n            return 1\n        \n        # 예측된 부하를 기준으로 필요한 인스턴스 수 계산\n        cpu_based_instances = math.ceil(predicted_cpu / 70.0 * current_instances)  # 70% 목표\n        memory_based_instances = math.ceil(predicted_memory / 80.0 * current_instances)  # 80% 목표\n        \n        # 더 높은 값 선택 (안전한 쪽)\n        recommended = max(cpu_based_instances, memory_based_instances)\n        return max(1, min(recommended, 20))  # 1-20 범위로 제한\n    \n    def _calculate_prediction_confidence(self, predictions: Dict[str, Any]) -> float:\n        \"\"\"예측 신뢰도 계산\"\"\"\n        # 과거 예측 정확도를 기반으로 신뢰도 계산\n        if not self.prediction_history:\n            return 0.5  # 기본 신뢰도\n        \n        # 최근 예측들의 정확도 평균\n        accuracies = []\n        for metric_type in ['cpu_usage_percent', 'memory_usage_percent', 'request_rate_per_second']:\n            if metric_type in self.accuracy_metrics:\n                recent_accuracies = list(self.accuracy_metrics[metric_type])[-10:]\n                if recent_accuracies:\n                    accuracies = accuracies + [statistics.mean(recent_accuracies])\n        \n        if accuracies:\n            return statistics.mean(accuracies)\n        \n        return 0.5\n    \n    def evaluate_prediction_accuracy(self, actual_metrics: ResourceMetrics) -> None:\n        \"\"\"예측 정확도 평가\"\"\"\n        if not self.prediction_history:\n            return\n        \n        # 15분 전 예측과 현재 실제값 비교\n        target_time = datetime.now() - timedelta(minutes=15)\n        \n        for record in reversed(self.prediction_history):\n            if abs((record['timestamp'] - target_time).total_seconds()) < 300:  # 5분 오차 허용\n                predictions = record['predictions']\n                \n                # CPU 예측 정확도\n                if 'cpu_usage_percent' in predictions:\n                    predicted = predictions['cpu_usage_percent']\n                    actual = actual_metrics.cpu_usage_percent\n                    accuracy = 1.0 - abs(predicted - actual) / 100.0\n                    self.accuracy_metrics['cpu_usage_percent'] = accuracy_metrics['cpu_usage_percent'] + [max(0.0, accuracy])\n                \n                # 메모리 예측 정확도\n                if 'memory_usage_percent' in predictions:\n                    predicted = predictions['memory_usage_percent']\n                    actual = actual_metrics.memory_usage_percent\n                    accuracy = 1.0 - abs(predicted - actual) / 100.0\n                    self.accuracy_metrics['memory_usage_percent'] = accuracy_metrics['memory_usage_percent'] + [max(0.0, accuracy])\n                \n                break\n    \n    def get_prediction_accuracy_stats(self) -> Dict[str, float]:\n        \"\"\"예측 정확도 통계\"\"\"\n        stats = {}\n        for metric_type, accuracies in self.accuracy_metrics.items():\n            if accuracies:\n                stats[metric_type] = {\n                    'avg_accuracy': statistics.mean(accuracies),\n                    'min_accuracy': min(accuracies),\n                    'max_accuracy': max(accuracies),\n                    'sample_count': len(accuracies)\n                }\n        return stats\n\nclass ScalingOptimizer:\n    \"\"\"스케일링 최적화 엔진\"\"\"\n    \n    def __init__(self, config: Optional[AutoScalingConfig] = None):\n        self.config = config or AutoScalingConfig()\n        \n        self.metric_collector = MetricCollector()\n        self.predictive_scaling = PredictiveScaling()\n        self.decision_engine = ScalingDecisionEngine(self.config)\n        self.resource_prediction = ResourcePrediction()\n        \n        self.monitoring_task: Optional[asyncio.Task] = None\n        self.scaling_actions: deque = deque(maxlen=100)\n        self.is_running = False\n        \n        # 스케일링 콜백\n        self.scale_up_callback: Optional[Callable[[int], Any]] = None\n        self.scale_down_callback: Optional[Callable[[int], Any]] = None\n    \n    async def initialize(self) -> Result[bool, str]:\n        \"\"\"스케일링 최적화 엔진 초기화\"\"\"\n        try:\n            if self.config.monitoring_interval_seconds > 0:\n                await self.start_monitoring()\n            \n            return Success(True)\n            \n        except Exception as e:\n            return Failure(f\"Scaling optimizer initialization failed: {e}\")\n    \n    def register_scaling_callbacks(self, scale_up_callback: Callable[[int], Any],\n                                 scale_down_callback: Callable[[int], Any]) -> None:\n        \"\"\"스케일링 콜백 등록\"\"\"\n        self.scale_up_callback = scale_up_callback\n        self.scale_down_callback = scale_down_callback\n    \n    async def start_monitoring(self) -> Result[bool, str]:\n        \"\"\"스케일링 모니터링 시작\"\"\"\n        if self.is_running:\n            return Success(True)\n            \n        try:\n            self.is_running = True\n            self.monitoring_task = asyncio.create_task(self._monitoring_loop())\n            return Success(True)\n            \n        except Exception as e:\n            return Failure(f\"Failed to start scaling monitoring: {e}\")\n    \n    async def stop_monitoring(self) -> Result[bool, str]:\n        \"\"\"스케일링 모니터링 중지\"\"\"\n        try:\n            self.is_running = False\n            if self.monitoring_task:\n                self.monitoring_task.cancel()\n                try:\n                    await self.monitoring_task\n                except asyncio.CancelledError:\n                    pass\n                self.monitoring_task = None\n            \n            return Success(True)\n            \n        except Exception as e:\n            return Failure(f\"Failed to stop scaling monitoring: {e}\")\n    \n    async def _monitoring_loop(self) -> None:\n        \"\"\"스케일링 모니터링 루프\"\"\"\n        while self.is_running:\n            try:\n                # 현재 메트릭 수집 (실제로는 외부 시스템에서 수집)\n                current_metrics = await self._collect_current_metrics()\n                if not current_metrics:\n                    await asyncio.sleep(self.config.monitoring_interval_seconds)\n                    continue\n                \n                # 메트릭 저장\n                self.metric_collector.add_metric(current_metrics)\n                \n                # 패턴 학습\n                self.predictive_scaling.learn_from_metrics(current_metrics)\n                \n                # 예측 정확도 평가\n                self.resource_prediction.evaluate_prediction_accuracy(current_metrics)\n                \n                # 스케일링 결정\n                await self._make_scaling_decision(current_metrics)\n                \n                await asyncio.sleep(self.config.monitoring_interval_seconds)\n                \n            except asyncio.CancelledError:\n                break\n            except Exception as e:\n                print(f\"Scaling monitoring error: {e}\")\n                await asyncio.sleep(self.config.monitoring_interval_seconds)\n    \n    async def _collect_current_metrics(self) -> Optional[ResourceMetrics]:\n        \"\"\"현재 메트릭 수집 (플레이스홀더)\"\"\"\n        # 실제 구현에서는 시스템 메트릭을 수집\n        # 여기서는 예시 데이터 생성\n        import random\n        \n        return ResourceMetrics(\n            timestamp=datetime.now(),\n            cpu_usage_percent=random.uniform(20, 90),\n            memory_usage_percent=random.uniform(30, 85),\n            request_rate_per_second=random.uniform(50, 500),\n            avg_response_time_ms=random.uniform(100, 3000),\n            error_rate_percent=random.uniform(0, 10),\n            queue_depth=random.randint(0, 100),\n            active_connections=random.randint(10, 200),\n            instance_count=3  # 현재 인스턴스 수\n        )\n    \n    async def _make_scaling_decision(self, current_metrics: ResourceMetrics) -> None:\n        \"\"\"스케일링 결정 생성 및 실행\"\"\"\n        # 메트릭 통계 계산\n        metric_stats = {}\n        for metric_type in MetricType:\n            stats = self.metric_collector.calculate_metric_statistics(\n                metric_type, self.config.decision_window_minutes\n            )\n            if stats:\n                metric_stats[metric_type] = stats\n        \n        # 예측 생성 (예측 스케일링이 활성화된 경우)\n        predictions = None\n        if self.config.enable_predictive_scaling:\n            historical_metrics = self.metric_collector.get_recent_metrics(30)\n            predictions = self.predictive_scaling.predict_future_load(15)\n        \n        # 스케일링 결정\n        decision = self.decision_engine.make_scaling_decision(\n            current_metrics, metric_stats, predictions\n        )\n        \n        # 결정 실행\n        if decision.confidence_score >= self.config.confidence_threshold:\n            await self._execute_scaling_decision(decision)\n    \n    async def _execute_scaling_decision(self, decision: ScalingDecision) -> None:\n        \"\"\"스케일링 결정 실행\"\"\"\n        try:\n            if decision.direction == ScalingDirection.UP:\n                if self.scale_up_callback:\n                    await self._safe_callback_execution(\n                        self.scale_up_callback, decision.target_instances\n                    )\n                self.decision_engine.record_scaling_action(ScalingDirection.UP)\n                print(f\"Scaled UP to {decision.target_instances} instances: {decision.reason}\")\n                \n            elif decision.direction == ScalingDirection.DOWN:\n                if self.scale_down_callback:\n                    await self._safe_callback_execution(\n                        self.scale_down_callback, decision.target_instances\n                    )\n                self.decision_engine.record_scaling_action(ScalingDirection.DOWN)\n                print(f\"Scaled DOWN to {decision.target_instances} instances: {decision.reason}\")\n            \n            # 액션 기록\n            self.scaling_actions = scaling_actions + [{\n                'timestamp': datetime.now(],\n                'decision': decision,\n                'executed': True\n            })\n            \n        except Exception as e:\n            print(f\"Failed to execute scaling decision: {e}\")\n            self.scaling_actions = scaling_actions + [{\n                'timestamp': datetime.now(],\n                'decision': decision,\n                'executed': False,\n                'error': str(e)\n            })\n    \n    async def _safe_callback_execution(self, callback: Callable, *args) -> None:\n        \"\"\"안전한 콜백 실행\"\"\"\n        try:\n            if asyncio.iscoroutinefunction(callback):\n                await callback(*args)\n            else:\n                callback(*args)\n        except Exception as e:\n            print(f\"Callback execution failed: {e}\")\n            raise\n    \n    def add_custom_metric_collector(self, name: str, collector_func: Callable[[], float]) -> None:\n        \"\"\"커스텀 메트릭 수집기 추가\"\"\"\n        self.metric_collector.register_custom_collector(name, collector_func)\n    \n    async def optimize(self) -> Result[Dict[str, Any], str]:\n        \"\"\"스케일링 최적화 실행\"\"\"\n        try:\n            # 현재 메트릭 수집\n            current_metrics = await self._collect_current_metrics()\n            if not current_metrics:\n                return Failure(\"Failed to collect current metrics\")\n            \n            # 최근 메트릭 분석\n            recent_metrics = self.metric_collector.get_recent_metrics(30)\n            \n            # 리소스 예측\n            predictions = self.resource_prediction.predict_resource_needs(\n                current_metrics, recent_metrics, 15\n            )\n            \n            # 결정 통계\n            decision_stats = self.decision_engine.get_decision_statistics()\n            \n            # 예측 정확도 통계\n            prediction_accuracy = self.resource_prediction.get_prediction_accuracy_stats()\n            \n            # 최적화 추천사항\n            recommendations = self._generate_optimization_recommendations(\n                current_metrics, recent_metrics, predictions\n            )\n            \n            results = {\n                'current_metrics': current_metrics,\n                'predictions': predictions,\n                'decision_statistics': decision_stats,\n                'prediction_accuracy': prediction_accuracy,\n                'recent_scaling_actions': list(self.scaling_actions)[-10:],\n                'recommendations': recommendations,\n                'optimization_summary': {\n                    'current_efficiency': self._calculate_efficiency_score(current_metrics),\n                    'predicted_efficiency': self._calculate_predicted_efficiency(predictions),\n                    'scaling_frequency': len(self.scaling_actions) / max(1, len(self.scaling_actions) / 24),  # per day\n                    'prediction_confidence': predictions.get('confidence', 0.0)\n                }\n            }\n            \n            return Success(results)\n            \n        except Exception as e:\n            return Failure(f\"Scaling optimization failed: {e}\")\n    \n    def _generate_optimization_recommendations(self, current_metrics: ResourceMetrics,\n                                             recent_metrics: List[ResourceMetrics],\n                                             predictions: Dict[str, Any]) -> List[str]:\n        \"\"\"최적화 추천사항 생성\"\"\"\n        recommendations = []\n        \n        # 리소스 효율성 분석\n        if current_metrics.cpu_usage_percent < 30 and current_metrics.memory_usage_percent < 40:\n            recommendations = recommendations + [\"Low resource utilization - consider scaling down or using smaller instances\"]\n        \n        if current_metrics.cpu_usage_percent > 80 or current_metrics.memory_usage_percent > 85:\n            recommendations = recommendations + [\"High resource utilization - consider scaling up\"]\n        \n        # 예측 신뢰도 분석\n        prediction_confidence = predictions.get('confidence', 0.0)\n        if prediction_confidence < 0.5:\n            recommendations = recommendations + [\"Low prediction confidence - gather more historical data\"]\n        \n        # 응답 시간 분석\n        if current_metrics.avg_response_time_ms > 2000:\n            recommendations = recommendations + [\"High response time - consider horizontal scaling\"]\n        \n        # 에러율 분석\n        if current_metrics.error_rate_percent > 5:\n            recommendations = recommendations + [\"High error rate - investigate before scaling\"]\n        \n        # 큐 깊이 분석\n        if current_metrics.queue_depth > 50:\n            recommendations = recommendations + [\"High queue depth - immediate scaling may be needed\"]\n        \n        # 스케일링 패턴 분석\n        decision_stats = self.decision_engine.get_decision_statistics()\n        if decision_stats.get('scale_up_ratio', 0) > 0.7:\n            recommendations = recommendations + [\"Frequent scale-ups detected - consider higher baseline capacity\"]\n        \n        if decision_stats.get('scale_down_ratio', 0) > 0.5:\n            recommendations = recommendations + [\"Frequent scale-downs detected - consider lower baseline capacity\"]\n        \n        return recommendations\n    \n    def _calculate_efficiency_score(self, metrics: ResourceMetrics) -> float:\n        \"\"\"효율성 점수 계산 (0-100)\"\"\"\n        score = 100.0\n        \n        # CPU 효율성 (60-80% 사용률이 최적)\n        cpu_efficiency = 100 - abs(metrics.cpu_usage_percent - 70)\n        score = (score + cpu_efficiency) / 2\n        \n        # 메모리 효율성 (70-85% 사용률이 최적)\n        memory_efficiency = 100 - abs(metrics.memory_usage_percent - 77.5) * 1.3\n        score = (score + memory_efficiency) / 2\n        \n        # 응답 시간 효율성\n        if metrics.avg_response_time_ms < 500:\n            response_efficiency = 100\n        elif metrics.avg_response_time_ms < 1000:\n            response_efficiency = 80\n        elif metrics.avg_response_time_ms < 2000:\n            response_efficiency = 60\n        else:\n            response_efficiency = 40\n        \n        score = (score + response_efficiency) / 2\n        \n        # 에러율 패널티\n        error_penalty = metrics.error_rate_percent * 10\n        score = score - error_penalty\n        \n        return max(0.0, min(100.0, score))\n    \n    def _calculate_predicted_efficiency(self, predictions: Dict[str, Any]) -> float:\n        \"\"\"예측 효율성 계산\"\"\"\n        predicted_cpu = predictions.get('cpu_usage_percent', 70)\n        predicted_memory = predictions.get('memory_usage_percent', 77.5)\n        \n        # 예측된 값으로 효율성 계산\n        cpu_efficiency = 100 - abs(predicted_cpu - 70)\n        memory_efficiency = 100 - abs(predicted_memory - 77.5) * 1.3\n        \n        predicted_efficiency = (cpu_efficiency + memory_efficiency) / 2\n        return max(0.0, min(100.0, predicted_efficiency))\n    \n    def get_current_status(self) -> Dict[str, Any]:\n        \"\"\"현재 상태 조회\"\"\"\n        recent_metrics = self.metric_collector.get_recent_metrics(5)\n        latest_metrics = recent_metrics[-1] if recent_metrics else None\n        \n        return {\n            'is_monitoring': self.is_running,\n            'latest_metrics': latest_metrics,\n            'recent_actions_count': len(self.scaling_actions),\n            'config': {\n                'strategy': self.config.strategy.value,\n                'scaling_type': self.config.scaling_type.value,\n                'min_instances': self.config.thresholds.min_instances,\n                'max_instances': self.config.thresholds.max_instances\n            }\n        }\n    \n    async def cleanup(self) -> Result[bool, str]:\n        \"\"\"리소스 정리\"\"\"\n        try:\n            await self.stop_monitoring()\n            return Success(True)\n            \n        except Exception as e:\n            return Failure(f\"Cleanup failed: {e}\")\n\n# 전역 optimizer 인스턴스\n_scaling_optimizer: Optional[ScalingOptimizer] = None\n\ndef get_scaling_optimizer(config: Optional[AutoScalingConfig] = None) -> ScalingOptimizer:\n    \"\"\"스케일링 optimizer 싱글톤 인스턴스 반환\"\"\"\n    global _scaling_optimizer\n    if _scaling_optimizer is None:\n        _scaling_optimizer = ScalingOptimizer(config)\n    return _scaling_optimizer\n\nasync def optimize_scaling_strategy(strategy: ScalingStrategy = ScalingStrategy.REACTIVE) -> Result[Dict[str, Any], str]:\n    \"\"\"스케일링 전략 최적화 실행\"\"\"\n    config = AutoScalingConfig(strategy=strategy)\n    optimizer = get_scaling_optimizer(config)\n    \n    init_result = await optimizer.initialize()\n    if not init_result.is_success():\n        return init_result\n    \n    return await optimizer.optimize()
