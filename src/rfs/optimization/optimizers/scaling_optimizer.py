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
from rfs.events.event_bus import Event
from rfs.reactive.mono import Mono


class ScalingDirection(Enum):
    """스케일링 방향"""

    UP = "up"  # 스케일 업
    DOWN = "down"  # 스케일 다운
    STABLE = "stable"  # 안정상태


class ScalingType(Enum):
    """스케일링 유형"""

    HORIZONTAL = "horizontal"  # 수평 스케일링 (인스턴스 수)
    VERTICAL = "vertical"  # 수직 스케일링 (리소스 크기)
    HYBRID = "hybrid"  # 하이브리드 스케일링


class ScalingStrategy(Enum):
    """스케일링 전략"""

    REACTIVE = "reactive"  # 반응형 스케일링
    PREDICTIVE = "predictive"  # 예측형 스케일링
    SCHEDULED = "scheduled"  # 스케줄 기반 스케일링
    COST_OPTIMIZED = "cost"  # 비용 최적화


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

    cpu_scale_up_percent: float = 70.0  # CPU 스케일업 임계값
    cpu_scale_down_percent: float = 30.0  # CPU 스케일다운 임계값
    memory_scale_up_percent: float = 80.0  # 메모리 스케일업 임계값
    memory_scale_down_percent: float = 40.0  # 메모리 스케일다운 임계값
    request_rate_scale_up: float = 1000.0  # 요청률 스케일업 임계값
    response_time_scale_up_ms: float = 2000.0  # 응답시간 스케일업 임계값
    error_rate_scale_up_percent: float = 5.0  # 에러율 스케일업 임계값
    min_instances = 1  # 최소 인스턴스 수
    max_instances = 10  # 최대 인스턴스 수
    scale_up_cooldown_seconds: float = 300.0  # 스케일업 쿨다운
    scale_down_cooldown_seconds: float = 600.0  # 스케일다운 쿨다운


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
    enable_predictive_scaling = True
    enable_cost_optimization = True
    monitoring_interval_seconds: float = 30.0
    decision_window_minutes = 5
    confidence_threshold: float = 0.7


class MetricCollector:
    """메트릭 수집기"""

    def __init__(self):
        self.metrics_history: deque = deque(maxlen=1000)
        self.custom_collectors = {}
        self.lock = threading.Lock()

    def add_metric(self, metrics: ResourceMetrics) -> None:
        """메트릭 추가"""
        with self.lock:
            self.metrics_history.append(metrics)

    def register_custom_collector(
        self, name: str, collector_func: Callable[[], float]
    ) -> None:
        """커스텀 메트릭 수집기 등록"""
        self.custom_collectors = {**self.custom_collectors, name: collector_func}

    def get_recent_metrics(self, minutes=5) -> List[ResourceMetrics]:
        """최근 메트릭 조회"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        with self.lock:
            return [m for m in self.metrics_history if m.timestamp >= cutoff_time]

    def get_metric_trend(self, metric_type: MetricType, minutes=10) -> List[float]:
        """메트릭 트렌드 분석"""
        recent_metrics = self.get_recent_metrics(minutes)

        values = []
        for metric in recent_metrics:
            match metric_type:
                case MetricType.CPU_USAGE:
                    values.append(metric.cpu_usage_percent)
                case MetricType.MEMORY_USAGE:
                    values.append(metric.memory_usage_percent)
                case MetricType.REQUEST_RATE:
                    values.append(metric.request_rate_per_second)
                case MetricType.RESPONSE_TIME:
                    values.append(metric.avg_response_time_ms)
                case MetricType.ERROR_RATE:
                    values.append(metric.error_rate_percent)
                case MetricType.QUEUE_DEPTH:
                    values.append(float(metric.queue_depth))

        return values

    def calculate_metric_statistics(
        self, metric_type: MetricType, minutes=5
    ) -> Dict[str, float]:
        """메트릭 통계 계산"""
        values = self.get_metric_trend(metric_type, minutes)

        if not values:
            return {}

        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "trend": self._calculate_trend(values),
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
        self.seasonal_patterns: Dict[int, List[float]] = defaultdict(
            list
        )  # hour -> values
        self.weekly_patterns: Dict[int, List[float]] = defaultdict(
            list
        )  # weekday -> values
        self.prediction_accuracy: deque = deque(maxlen=100)

    def learn_from_metrics(self, metrics: ResourceMetrics) -> None:
        """메트릭에서 패턴 학습"""
        hour = metrics.timestamp.hour
        weekday = metrics.timestamp.weekday()

        # 시간대별 패턴
        self.seasonal_patterns[hour].append(metrics.cpu_usage_percent)
        if len(self.seasonal_patterns[hour]) > 100:  # 최근 100개만 유지
            self.seasonal_patterns[hour] = self.seasonal_patterns[hour][-100:]

        # 요일별 패턴
        self.weekly_patterns[weekday].append(metrics.request_rate_per_second)
        if len(self.weekly_patterns[weekday]) > 100:
            self.weekly_patterns[weekday] = self.weekly_patterns[weekday][-100:]

    def predict_future_load(self, minutes_ahead=15) -> Dict[str, float]:
        """미래 부하 예측"""
        future_time = datetime.now() + timedelta(minutes=minutes_ahead)
        future_hour = future_time.hour
        future_weekday = future_time.weekday()

        predictions = {}

        # CPU 사용률 예측 (시간대 기반)
        if future_hour in self.seasonal_patterns:
            cpu_values = self.seasonal_patterns[future_hour]
            if cpu_values:
                predictions["cpu_usage_percent"] = statistics.mean(cpu_values)

        # 요청률 예측 (요일 기반)
        if future_weekday in self.weekly_patterns:
            request_values = self.weekly_patterns[future_weekday]
            if request_values:
                predictions["request_rate_per_second"] = statistics.mean(request_values)

        return predictions

    def calculate_prediction_confidence(self, metric_type: str) -> float:
        """예측 신뢰도 계산"""
        if metric_type == "cpu_usage_percent":
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
        self.last_scale_up_time = None
        self.last_scale_down_time = None
        self.decision_history: deque = deque(maxlen=100)

    def make_scaling_decision(
        self,
        current_metrics: ResourceMetrics,
        metric_stats: Dict[MetricType, Dict[str, float]],
        predictions=None,
    ) -> ScalingDecision:
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
                estimated_performance_impact=0.0,
            )

        # 스케일링 필요성 분석
        scale_up_signals = self._analyze_scale_up_signals(
            current_metrics, metric_stats, predictions
        )
        scale_down_signals = self._analyze_scale_down_signals(
            current_metrics, metric_stats, predictions
        )

        # 결정 생성
        if scale_up_signals["score"] > scale_down_signals["score"]:
            direction = ScalingDirection.UP
            target_instances = min(
                current_metrics.instance_count + 1, self.config.thresholds.max_instances
            )
            reason = f"Scale up: {scale_up_signals['reason']}"
            confidence = scale_up_signals["confidence"]
        elif scale_down_signals["score"] > 0.7:  # 스케일 다운은 더 신중하게
            direction = ScalingDirection.DOWN
            target_instances = max(
                current_metrics.instance_count - 1, self.config.thresholds.min_instances
            )
            reason = f"Scale down: {scale_down_signals['reason']}"
            confidence = scale_down_signals["confidence"]
        else:
            direction = ScalingDirection.STABLE
            target_instances = current_metrics.instance_count
            reason = "No scaling needed"
            confidence = 1.0

        # 비용 및 성능 영향 추정
        cost_impact = self._estimate_cost_impact(
            current_metrics.instance_count, target_instances
        )
        performance_impact = self._estimate_performance_impact(
            direction, current_metrics
        )

        decision = ScalingDecision(
            direction=direction,
            scaling_type=self.config.scaling_type,
            current_instances=current_metrics.instance_count,
            target_instances=target_instances,
            reason=reason,
            confidence_score=confidence,
            estimated_cost_impact=cost_impact,
            estimated_performance_impact=performance_impact,
        )

        self.decision_history = decision_history + [decision]
        return decision

    def _can_scale(self) -> bool:
        """스케일링 가능 여부 확인 (쿨다운)"""
        now = datetime.now()

        if (
            self.last_scale_up_time
            and (now - self.last_scale_up_time).total_seconds()
            < self.config.thresholds.scale_up_cooldown_seconds
        ):
            return False

        if (
            self.last_scale_down_time
            and (now - self.last_scale_down_time).total_seconds()
            < self.config.thresholds.scale_down_cooldown_seconds
        ):
            return False

        return True

    def _analyze_scale_up_signals(
        self,
        metrics: ResourceMetrics,
        metric_stats: Dict[MetricType, Dict[str, float]],
        predictions=None,
    ) -> Dict[str, Any]:
        """스케일업 신호 분석"""
        signals = []
        reasons = []

        # CPU 사용률 체크
        cpu_stats = metric_stats.get(MetricType.CPU_USAGE, {})
        if cpu_stats.get("mean", 0) > self.config.thresholds.cpu_scale_up_percent:
            signals.append(0.8)
            reasons.append("High CPU usage")
            reasons = reasons + [f"High CPU usage: {cpu_stats.get('mean', 0):.1f}%"]

        # 메모리 사용률 체크
        memory_stats = metric_stats.get(MetricType.MEMORY_USAGE, {})
        if memory_stats.get("mean", 0) > self.config.thresholds.memory_scale_up_percent:
            signals = signals + [0.7]
            reasons = reasons + [
                f"High memory usage: {memory_stats.get('mean', 0):.1f}%"
            ]

        # 응답 시간 체크
        response_stats = metric_stats.get(MetricType.RESPONSE_TIME, {})
        if (
            response_stats.get("mean", 0)
            > self.config.thresholds.response_time_scale_up_ms
        ):
            signals = signals + [0.9]
            reasons = reasons + [
                f"High response time: {response_stats.get('mean', 0):.1f}ms"
            ]

        # 에러율 체크
        error_stats = metric_stats.get(MetricType.ERROR_RATE, {})
        if (
            error_stats.get("mean", 0)
            > self.config.thresholds.error_rate_scale_up_percent
        ):
            signals = signals + [0.95]
            reasons = reasons + [f"High error rate: {error_stats.get('mean', 0):.1f}%"]

        # 큐 깊이 체크
        if metrics.queue_depth > 50:  # 임계값
            signals = signals + [0.8]
            reasons = reasons + [f"High queue depth: {metrics.queue_depth}"]

        # 예측 기반 신호
        if predictions and self.config.enable_predictive_scaling:
            predicted_cpu = predictions.get("cpu_usage_percent", 0)
            if predicted_cpu > self.config.thresholds.cpu_scale_up_percent:
                signals = signals + [0.6]  # 예측은 낮은 가중치
                reasons = reasons + [f"Predicted high CPU: {predicted_cpu:.1f}%"]

        # 트렌드 기반 신호
        cpu_trend = cpu_stats.get("trend", 0)
        if cpu_trend > 5:  # 급격한 증가 트렌드
            signals = signals + [0.5]
            reasons = reasons + ["Increasing CPU trend"]

        if not signals:
            return {"score": 0.0, "confidence": 0.0, "reason": "No scale up signals"}

        score = max(signals)  # 가장 강한 신호 사용
        confidence = sum(signals) / len(signals)  # 평균 신뢰도
        reason = "; ".join(reasons[:2])  # 상위 2개 이유

        return {"score": score, "confidence": confidence, "reason": reason}

    def _analyze_scale_down_signals(
        self,
        metrics: ResourceMetrics,
        metric_stats: Dict[MetricType, Dict[str, float]],
        predictions=None,
    ) -> Dict[str, Any]:
        """스케일다운 신호 분석"""
        signals = []
        reasons = []

        # 최소 인스턴스 수 체크
        if metrics.instance_count <= self.config.thresholds.min_instances:
            return {"score": 0.0, "confidence": 0.0, "reason": "At minimum instances"}

        # CPU 사용률 체크
        cpu_stats = metric_stats.get(MetricType.CPU_USAGE, {})
        if cpu_stats.get("mean", 100) < self.config.thresholds.cpu_scale_down_percent:
            signals.append(0.7)
            reasons.append("Low CPU usage")
            reasons = reasons + [f"Low CPU usage: {cpu_stats.get('mean', 0):.1f}%"]

        # 메모리 사용률 체크
        memory_stats = metric_stats.get(MetricType.MEMORY_USAGE, {})
        if (
            memory_stats.get("mean", 100)
            < self.config.thresholds.memory_scale_down_percent
        ):
            signals = signals + [0.6]
            reasons = reasons + [
                f"Low memory usage: {memory_stats.get('mean', 0):.1f}%"
            ]

        # 요청률이 낮은 경우
        request_stats = metric_stats.get(MetricType.REQUEST_RATE, {})
        if (
            request_stats.get("mean", float("inf"))
            < self.config.thresholds.request_rate_scale_up / 2
        ):
            signals = signals + [0.5]
            reasons = reasons + ["Low request rate"]

        # 응답 시간이 충분히 낮은 경우
        response_stats = metric_stats.get(MetricType.RESPONSE_TIME, {})
        if (
            response_stats.get("mean", float("inf"))
            < self.config.thresholds.response_time_scale_up_ms / 2
        ):
            signals = signals + [0.4]
            reasons = reasons + ["Low response time"]

        # 모든 메트릭이 안정적인 경우
        all_stable = (
            cpu_stats.get("std_dev", float("inf")) < 10  # 낮은 변동성
            and memory_stats.get("std_dev", float("inf")) < 10
            and response_stats.get("std_dev", float("inf")) < 500
        )
        if all_stable:
            signals = signals + [0.3]
            reasons = reasons + ["All metrics stable"]

        if not signals:
            return {"score": 0.0, "confidence": 0.0, "reason": "No scale down signals"}

        # 스케일 다운은 더 보수적으로
        score = min(max(signals), 0.8)  # 최대 0.8로 제한
        confidence = sum(signals) / len(signals)
        reason = "; ".join(reasons[:2])

        return {"score": score, "confidence": confidence, "reason": reason}

    def _estimate_cost_impact(
        self, current_instances: int, target_instances: int
    ) -> float:
        """비용 영향 추정"""
        instance_diff = target_instances - current_instances

        # 인스턴스당 시간당 비용 (예시: $0.10)
        cost_per_instance_per_hour = 0.10

        # 시간당 비용 변화
        hourly_cost_change = instance_diff * cost_per_instance_per_hour

        # 일일 비용 변화로 반환
        return hourly_cost_change * 24

    def _estimate_performance_impact(
        self, direction: ScalingDirection, metrics: ResourceMetrics
    ) -> float:
        """Estimate performance impact (0-100, positive is improvement, negative is degradation)"""
        if direction == ScalingDirection.UP:
            # 스케일 업 시 성능 개선 추정
            current_cpu = metrics.cpu_usage_percent
            if current_cpu > 80:
                return 30.0  # 높은 개선
            elif current_cpu > 60:
                return 20.0  # 중간 개선
            else:
                return 10.0  # 낮은 개선

        elif direction == ScalingDirection.DOWN:
            # 스케일 다운 시 성능 저하 위험 추정
            current_cpu = metrics.cpu_usage_percent
            if current_cpu < 20:
                return -5.0  # 낮은 위험
            elif current_cpu < 40:
                return -10.0  # 중간 위험
            else:
                return -20.0  # 높은 위험

        return 0.0  # 안정 상태

    def record_scaling_action(self, direction: ScalingDirection) -> None:
        """스케일링 액션 기록"""
        now = datetime.now()
        if direction == ScalingDirection.UP:
            self.last_scale_up_time = now
        elif direction == ScalingDirection.DOWN:
            self.last_scale_down_time = now

    def get_decision_statistics(self) -> Dict[str, Any]:
        """결정 통계"""
        if not self.decision_history:
            return {}

        total_decisions = len(self.decision_history)
        scale_up_count = sum(
            1 for d in self.decision_history if d.direction == ScalingDirection.UP
        )
        scale_down_count = sum(
            1 for d in self.decision_history if d.direction == ScalingDirection.DOWN
        )
        stable_count = total_decisions - scale_up_count - scale_down_count

        avg_confidence = (
            sum(d.confidence_score for d in self.decision_history) / total_decisions
        )

        return {
            "total_decisions": total_decisions,
            "scale_up_count": scale_up_count,
            "scale_down_count": scale_down_count,
            "stable_count": stable_count,
            "avg_confidence": avg_confidence,
            "scale_up_ratio": scale_up_count / total_decisions,
            "scale_down_ratio": scale_down_count / total_decisions,
        }


class ResourcePrediction:
    """리소스 예측"""

    def __init__(self):
        self.prediction_models = {}
        self.prediction_history: deque = deque(maxlen=1000)
        self.accuracy_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

    def predict_resource_needs(
        self,
        current_metrics: ResourceMetrics,
        historical_metrics: List[ResourceMetrics],
        time_horizon_minutes=15,
    ) -> Dict[str, Any]:
        """리소스 요구사항 예측"""

        predictions = {
            "cpu_usage_percent": self._predict_cpu_usage(
                historical_metrics, time_horizon_minutes
            ),
            "memory_usage_percent": self._predict_memory_usage(
                historical_metrics, time_horizon_minutes
            ),
            "request_rate_per_second": self._predict_request_rate(
                historical_metrics, time_horizon_minutes
            ),
            "recommended_instances": self._predict_instance_count(
                current_metrics, historical_metrics
            ),
        }

        # 예측 신뢰도 계산
        predictions["confidence"] = self._calculate_prediction_confidence(predictions)

        # 예측 기록
        prediction_record = {
            "timestamp": datetime.now(),
            "predictions": predictions,
            "current_metrics": current_metrics,
        }
        self.prediction_history = self.prediction_history + [prediction_record]

        return predictions

    def _predict_cpu_usage(
        self, historical_metrics: List[ResourceMetrics], time_horizon_minutes: int
    ) -> float:
        """CPU 사용률 예측"""
        if len(historical_metrics) < 3:
            return (
                historical_metrics[-1].cpu_usage_percent if historical_metrics else 50.0
            )

        # 단순 선형 예측
        recent_values = [m.cpu_usage_percent for m in historical_metrics[-10:]]

        # 이동 평균과 트렌드 계산
        if len(recent_values) >= 2:
            trend = (recent_values[-1] - recent_values[0]) / len(recent_values)
            predicted_value = recent_values[-1] + (
                trend * time_horizon_minutes / 5
            )  # 5분 간격 가정
            return max(0.0, min(100.0, predicted_value))

        return recent_values[-1] if recent_values else 50.0

    def _predict_memory_usage(
        self, historical_metrics: List[ResourceMetrics], time_horizon_minutes: int
    ) -> float:
        """메모리 사용률 예측"""
        if len(historical_metrics) < 3:
            return (
                historical_metrics[-1].memory_usage_percent
                if historical_metrics
                else 50.0
            )

        # 메모리는 보통 더 안정적이므로 이동 평균 사용
        recent_values = [m.memory_usage_percent for m in historical_metrics[-5:]]
        return statistics.mean(recent_values) if recent_values else 50.0

    def _predict_request_rate(
        self, historical_metrics: List[ResourceMetrics], time_horizon_minutes: int
    ) -> float:
        """요청률 예측"""
        if len(historical_metrics) < 3:
            return (
                historical_metrics[-1].request_rate_per_second
                if historical_metrics
                else 100.0
            )

        # 요청률은 변동이 클 수 있으므로 가중 이동 평균 사용
        recent_values = [m.request_rate_per_second for m in historical_metrics[-10:]]

        if len(recent_values) >= 2:
            # 가중치: 최근 값에 더 높은 가중치
            weights = [i + 1 for i in range(len(recent_values))]
            weighted_avg = sum(v * w for v, w in zip(recent_values, weights)) / sum(
                weights
            )
            return max(0.0, weighted_avg)

        return recent_values[-1] if recent_values else 100.0

    def _predict_instance_count(
        self,
        current_metrics: ResourceMetrics,
        historical_metrics: List[ResourceMetrics],
    ) -> int:
        """인스턴스 수 예측"""
        # CPU와 메모리 예측값을 기반으로 필요한 인스턴스 수 계산
        predicted_cpu = self._predict_cpu_usage(historical_metrics, 15)
        predicted_memory = self._predict_memory_usage(historical_metrics, 15)

        # 현재 인스턴스당 평균 부하
        current_instances = current_metrics.instance_count
        if current_instances == 0:
            return 1

        # 예측된 부하를 기준으로 필요한 인스턴스 수 계산
        cpu_based_instances = math.ceil(
            predicted_cpu / 70.0 * current_instances
        )  # 70% 목표
        memory_based_instances = math.ceil(
            predicted_memory / 80.0 * current_instances
        )  # 80% 목표

        # 더 높은 값 선택 (안전한 쪽)
        recommended = max(cpu_based_instances, memory_based_instances)
        return max(1, min(recommended, 20))  # 1-20 범위로 제한

    def _calculate_prediction_confidence(self, predictions: Dict[str, Any]) -> float:
        """예측 신뢰도 계산"""
        # 과거 예측 정확도를 기반으로 신뢰도 계산
        if not self.prediction_history:
            return 0.5  # 기본 신뢰도

        # 최근 예측들의 정확도 평균
        accuracies = []
        for metric_type in [
            "cpu_usage_percent",
            "memory_usage_percent",
            "request_rate_per_second",
        ]:
            if metric_type in self.accuracy_metrics:
                recent_accuracies = list(self.accuracy_metrics[metric_type])[-10:]
                if recent_accuracies:
                    accuracies = accuracies + [statistics.mean(recent_accuracies)]

        if accuracies:
            return statistics.mean(accuracies)

        return 0.5

    def evaluate_prediction_accuracy(self, actual_metrics: ResourceMetrics) -> None:
        """예측 정확도 평가"""
        if not self.prediction_history:
            return

        # 15분 전 예측과 현재 실제값 비교
        target_time = datetime.now() - timedelta(minutes=15)

        for record in reversed(self.prediction_history):
            if (
                abs((record["timestamp"] - target_time).total_seconds()) < 300
            ):  # 5분 오차 허용
                predictions = record["predictions"]

                # CPU 예측 정확도
                if "cpu_usage_percent" in predictions:
                    predicted = predictions["cpu_usage_percent"]
                    actual = actual_metrics.cpu_usage_percent
                    accuracy = 1.0 - abs(predicted - actual) / 100.0
                    self.accuracy_metrics["cpu_usage_percent"] = self.accuracy_metrics[
                        "cpu_usage_percent"
                    ] + [max(0.0, accuracy)]

                # 메모리 예측 정확도
                if "memory_usage_percent" in predictions:
                    predicted = predictions["memory_usage_percent"]
                    actual = actual_metrics.memory_usage_percent
                    accuracy = 1.0 - abs(predicted - actual) / 100.0
                    self.accuracy_metrics["memory_usage_percent"] = (
                        self.accuracy_metrics["memory_usage_percent"]
                        + [max(0.0, accuracy)]
                    )

                break

    def get_prediction_accuracy_stats(self) -> Dict[str, float]:
        """예측 정확도 통계"""
        stats = {}
        for metric_type, accuracies in self.accuracy_metrics.items():
            if accuracies:
                stats[metric_type] = {
                    "avg_accuracy": statistics.mean(accuracies),
                    "min_accuracy": min(accuracies),
                    "max_accuracy": max(accuracies),
                    "sample_count": len(accuracies),
                }
        return stats


class ScalingOptimizer:
    """스케일링 최적화 엔진"""

    def __init__(self, config=None):
        self.config = config or AutoScalingConfig()

        self.metric_collector = MetricCollector()
        self.predictive_scaling = PredictiveScaling()
        self.decision_engine = ScalingDecisionEngine(self.config)
        self.resource_prediction = ResourcePrediction()

        self.monitoring_task = None
        self.scaling_actions: deque = deque(maxlen=100)
        self.is_running = False

        # 스케일링 콜백
        self.scale_up_callback: Optional[Callable[[int], Any]] = None
        self.scale_down_callback: Optional[Callable[[int], Any]] = None

    async def initialize(self) -> Result[bool, str]:
        """스케일링 최적화 엔진 초기화"""
        try:
            if self.config.monitoring_interval_seconds > 0:
                await self.start_monitoring()

            return Success(True)

        except Exception as e:
            return Failure(f"Scaling optimizer initialization failed: {e}")

    def register_scaling_callbacks(
        self,
        scale_up_callback: Callable[[int], Any],
        scale_down_callback: Callable[[int], Any],
    ) -> None:
        """스케일링 콜백 등록"""
        self.scale_up_callback = scale_up_callback
        self.scale_down_callback = scale_down_callback

    async def start_monitoring(self) -> Result[bool, str]:
        """스케일링 모니터링 시작"""
        if self.is_running:
            return Success(True)

        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            return Success(True)

        except Exception as e:
            return Failure(f"Failed to start scaling monitoring: {e}")

    async def stop_monitoring(self) -> Result[bool, str]:
        """스케일링 모니터링 중지"""
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
            return Failure(f"Failed to stop scaling monitoring: {e}")

    async def _monitoring_loop(self) -> None:
        """스케일링 모니터링 루프"""
        while self.is_running:
            try:
                # 현재 메트릭 수집 (실제로는 외부 시스템에서 수집)
                current_metrics = await self._collect_current_metrics()
                if not current_metrics:
                    await asyncio.sleep(self.config.monitoring_interval_seconds)
                    continue

                # 메트릭 저장
                self.metric_collector.add_metric(current_metrics)

                # 패턴 학습
                self.predictive_scaling.learn_from_metrics(current_metrics)

                # 예측 정확도 평가
                self.resource_prediction.evaluate_prediction_accuracy(current_metrics)

                # 스케일링 결정
                await self._make_scaling_decision(current_metrics)

                await asyncio.sleep(self.config.monitoring_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Scaling monitoring error: {e}")
                await asyncio.sleep(self.config.monitoring_interval_seconds)

    async def _collect_current_metrics(self) -> Optional[ResourceMetrics]:
        """현재 메트릭 수집 (플레이스홀더)"""
        # 실제 구현에서는 시스템 메트릭을 수집
        # 여기서는 예시 데이터 생성
        import random

        return ResourceMetrics(
            timestamp=datetime.now(),
            cpu_usage_percent=random.uniform(20, 90),
            memory_usage_percent=random.uniform(30, 85),
            request_rate_per_second=random.uniform(50, 500),
            avg_response_time_ms=random.uniform(100, 3000),
            error_rate_percent=random.uniform(0, 10),
            queue_depth=random.randint(0, 100),
            active_connections=random.randint(10, 200),
            instance_count=3,  # 현재 인스턴스 수
        )

    async def _make_scaling_decision(self, current_metrics: ResourceMetrics) -> None:
        """스케일링 결정 생성 및 실행"""
        # 메트릭 통계 계산
        metric_stats = {}
        for metric_type in MetricType:
            stats = self.metric_collector.calculate_metric_statistics(
                metric_type, self.config.decision_window_minutes
            )
            if stats:
                metric_stats[metric_type] = stats

        # 예측 생성 (예측 스케일링이 활성화된 경우)
        predictions = None
        if self.config.enable_predictive_scaling:
            historical_metrics = self.metric_collector.get_recent_metrics(30)
            predictions = self.predictive_scaling.predict_future_load(15)

        # 스케일링 결정
        decision = self.decision_engine.make_scaling_decision(
            current_metrics, metric_stats, predictions
        )

        # 결정 실행
        if decision.confidence_score >= self.config.confidence_threshold:
            await self._execute_scaling_decision(decision)

    async def _execute_scaling_decision(self, decision: ScalingDecision) -> None:
        """스케일링 결정 실행"""
        try:
            if decision.direction == ScalingDirection.UP:
                if self.scale_up_callback:
                    await self._safe_callback_execution(
                        self.scale_up_callback, decision.target_instances
                    )
                self.decision_engine.record_scaling_action(ScalingDirection.UP)
                print(
                    f"Scaled UP to {decision.target_instances} instances: {decision.reason}"
                )

            elif decision.direction == ScalingDirection.DOWN:
                if self.scale_down_callback:
                    await self._safe_callback_execution(
                        self.scale_down_callback, decision.target_instances
                    )
                self.decision_engine.record_scaling_action(ScalingDirection.DOWN)
                print(
                    f"Scaled DOWN to {decision.target_instances} instances: {decision.reason}"
                )

            # 액션 기록
            self.scaling_actions = self.scaling_actions + [
                {"timestamp": datetime.now(), "decision": decision, "executed": True}
            ]

        except Exception as e:
            print(f"Failed to execute scaling decision: {e}")
            self.scaling_actions = self.scaling_actions + [
                {
                    "timestamp": datetime.now(),
                    "decision": decision,
                    "executed": False,
                    "error": str(e),
                }
            ]

    async def _safe_callback_execution(self, callback: Callable, *args) -> None:
        """안전한 콜백 실행"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            print(f"Callback execution failed: {e}")
            raise

    def add_custom_metric_collector(
        self, name: str, collector_func: Callable[[], float]
    ) -> None:
        """커스텀 메트릭 수집기 추가"""
        self.metric_collector.register_custom_collector(name, collector_func)

    async def optimize(self) -> Result[Dict[str, Any], str]:
        """스케일링 최적화 실행"""
        try:
            # 현재 메트릭 수집
            current_metrics = await self._collect_current_metrics()
            if not current_metrics:
                return Failure("Failed to collect current metrics")

            # 최근 메트릭 분석
            recent_metrics = self.metric_collector.get_recent_metrics(30)

            # 리소스 예측
            predictions = self.resource_prediction.predict_resource_needs(
                current_metrics, recent_metrics, 15
            )

            # 결정 통계
            decision_stats = self.decision_engine.get_decision_statistics()

            # 예측 정확도 통계
            prediction_accuracy = (
                self.resource_prediction.get_prediction_accuracy_stats()
            )

            # 최적화 추천사항
            recommendations = self._generate_optimization_recommendations(
                current_metrics, recent_metrics, predictions
            )

            results = {
                "current_metrics": current_metrics,
                "predictions": predictions,
                "decision_statistics": decision_stats,
                "prediction_accuracy": prediction_accuracy,
                "recent_scaling_actions": list(self.scaling_actions)[-10:],
                "recommendations": recommendations,
                "optimization_summary": {
                    "current_efficiency": self._calculate_efficiency_score(
                        current_metrics
                    ),
                    "predicted_efficiency": self._calculate_predicted_efficiency(
                        predictions
                    ),
                    "scaling_frequency": len(self.scaling_actions)
                    / max(1, len(self.scaling_actions) / 24),  # per day
                    "prediction_confidence": predictions.get("confidence", 0.0),
                },
            }

            return Success(results)

        except Exception as e:
            return Failure(f"Scaling optimization failed: {e}")

    def _generate_optimization_recommendations(
        self,
        current_metrics: ResourceMetrics,
        recent_metrics: List[ResourceMetrics],
        predictions: Dict[str, Any],
    ) -> List[str]:
        """최적화 추천사항 생성"""
        recommendations = []

        # 리소스 효율성 분석
        if (
            current_metrics.cpu_usage_percent < 30
            and current_metrics.memory_usage_percent < 40
        ):
            recommendations = recommendations + [
                "Low resource utilization - consider scaling down or using smaller instances"
            ]

        if (
            current_metrics.cpu_usage_percent > 80
            or current_metrics.memory_usage_percent > 85
        ):
            recommendations = recommendations + [
                "High resource utilization - consider scaling up"
            ]

        # 예측 신뢰도 분석
        prediction_confidence = predictions.get("confidence", 0.0)
        if prediction_confidence < 0.5:
            recommendations = recommendations + [
                "Low prediction confidence - gather more historical data"
            ]

        # 응답 시간 분석
        if current_metrics.avg_response_time_ms > 2000:
            recommendations = recommendations + [
                "High response time - consider horizontal scaling"
            ]

        # 에러율 분석
        if current_metrics.error_rate_percent > 5:
            recommendations = recommendations + [
                "High error rate - investigate before scaling"
            ]

        # 큐 깊이 분석
        if current_metrics.queue_depth > 50:
            recommendations = recommendations + [
                "High queue depth - immediate scaling may be needed"
            ]

        # 스케일링 패턴 분석
        decision_stats = self.decision_engine.get_decision_statistics()
        if decision_stats.get("scale_up_ratio", 0) > 0.7:
            recommendations = recommendations + [
                "Frequent scale-ups detected - consider higher baseline capacity"
            ]

        if decision_stats.get("scale_down_ratio", 0) > 0.5:
            recommendations = recommendations + [
                "Frequent scale-downs detected - consider lower baseline capacity"
            ]

        return recommendations

    def _calculate_efficiency_score(self, metrics: ResourceMetrics) -> float:
        """효율성 점수 계산 (0-100)"""
        score = 100.0

        # CPU 효율성 (60-80% 사용률이 최적)
        cpu_efficiency = 100 - abs(metrics.cpu_usage_percent - 70)
        score = (score + cpu_efficiency) / 2

        # 메모리 효율성 (70-85% 사용률이 최적)
        memory_efficiency = 100 - abs(metrics.memory_usage_percent - 77.5) * 1.3
        score = (score + memory_efficiency) / 2

        # 응답 시간 효율성
        if metrics.avg_response_time_ms < 500:
            response_efficiency = 100
        elif metrics.avg_response_time_ms < 1000:
            response_efficiency = 80
        elif metrics.avg_response_time_ms < 2000:
            response_efficiency = 60
        else:
            response_efficiency = 40

        score = (score + response_efficiency) / 2

        # 에러율 패널티
        error_penalty = metrics.error_rate_percent * 10
        score = score - error_penalty

        return max(0.0, min(100.0, score))

    def _calculate_predicted_efficiency(self, predictions: Dict[str, Any]) -> float:
        """예측 효율성 계산"""
        predicted_cpu = predictions.get("cpu_usage_percent", 70)
        predicted_memory = predictions.get("memory_usage_percent", 77.5)

        # 예측된 값으로 효율성 계산
        cpu_efficiency = 100 - abs(predicted_cpu - 70)
        memory_efficiency = 100 - abs(predicted_memory - 77.5) * 1.3

        predicted_efficiency = (cpu_efficiency + memory_efficiency) / 2
        return max(0.0, min(100.0, predicted_efficiency))

    def get_current_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        recent_metrics = self.metric_collector.get_recent_metrics(5)
        latest_metrics = recent_metrics[-1] if recent_metrics else None

        return {
            "is_monitoring": self.is_running,
            "latest_metrics": latest_metrics,
            "recent_actions_count": len(self.scaling_actions),
            "config": {
                "strategy": self.config.strategy.value,
                "scaling_type": self.config.scaling_type.value,
                "min_instances": self.config.thresholds.min_instances,
                "max_instances": self.config.thresholds.max_instances,
            },
        }

    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            return Success(True)

        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


# 전역 optimizer 인스턴스
_scaling_optimizer = None


def get_scaling_optimizer(
    config=None,
) -> ScalingOptimizer:
    """스케일링 optimizer 싱글톤 인스턴스 반환"""
    global _scaling_optimizer
    if _scaling_optimizer is None:
        _scaling_optimizer = ScalingOptimizer(config)
    return _scaling_optimizer


async def optimize_scaling_strategy(
    strategy: ScalingStrategy = ScalingStrategy.REACTIVE,
) -> Result[Dict[str, Any], str]:
    """스케일링 전략 최적화 실행"""
    config = AutoScalingConfig(strategy=strategy)
    optimizer = get_scaling_optimizer(config)

    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result

    return await optimizer.optimize()
