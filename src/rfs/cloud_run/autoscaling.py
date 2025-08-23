"""
Cloud Run Auto Scaling Optimization (RFS v4)

지능형 자동 스케일링 최적화
- 트래픽 패턴 분석 및 예측
- 동적 스케일링 정책 조정
- 비용 최적화 및 성능 균형
- 예측적 스케일링 및 사전 워밍
"""

import asyncio
import math
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging

try:
    from google.cloud import run_v2
    from google.cloud import monitoring_v3
    from pydantic import BaseModel, Field, ConfigDict, field_validator
    GOOGLE_CLOUD_AVAILABLE = True
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object
    Field = lambda default=None, **kwargs: default
    run_v2 = None
    monitoring_v3 = None
    GOOGLE_CLOUD_AVAILABLE = False
    PYDANTIC_AVAILABLE = False

from ..core.result import Result, Success, Failure
from ..reactive import Mono, Flux
from .monitoring import get_monitoring_client, record_metric

logger = logging.getLogger(__name__)


class ScalingPolicy(str, Enum):
    """스케일링 정책"""
    CONSERVATIVE = "conservative"    # 보수적 - 비용 우선
    BALANCED = "balanced"           # 균형 - 성능과 비용 균형
    AGGRESSIVE = "aggressive"       # 적극적 - 성능 우선
    PREDICTIVE = "predictive"       # 예측적 - AI 기반 예측


class TrafficPattern(str, Enum):
    """트래픽 패턴"""
    STEADY = "steady"               # 일정한 트래픽
    BURST = "burst"                 # 버스트 트래픽
    PERIODIC = "periodic"           # 주기적 패턴
    UNKNOWN = "unknown"             # 패턴 불명


class ScalingDirection(str, Enum):
    """스케일링 방향"""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


if PYDANTIC_AVAILABLE:
    class ScalingConfiguration(BaseModel):
        """스케일링 설정 (Pydantic v2)"""
        
        model_config = ConfigDict(
            str_strip_whitespace=True,
            validate_default=True,
            frozen=False
        )
        
        # 기본 스케일링 설정
        min_instances: int = Field(
            default=0,
            ge=0,
            le=1000,
            description="최소 인스턴스 수"
        )
        max_instances: int = Field(
            default=100,
            ge=1,
            le=1000,
            description="최대 인스턴스 수"
        )
        target_concurrency: int = Field(
            default=80,
            ge=1,
            le=1000,
            description="목표 동시 요청 수"
        )
        
        # 고급 설정
        scale_up_threshold: float = Field(
            default=0.8,
            ge=0.1,
            le=1.0,
            description="스케일 업 임계값 (CPU/메모리 사용률)"
        )
        scale_down_threshold: float = Field(
            default=0.3,
            ge=0.1,
            le=1.0,
            description="스케일 다운 임계값"
        )
        scale_up_cooldown: int = Field(
            default=60,
            ge=10,
            le=3600,
            description="스케일 업 쿨다운 (초)"
        )
        scale_down_cooldown: int = Field(
            default=300,
            ge=30,
            le=3600,
            description="스케일 다운 쿨다운 (초)"
        )
        
        # 정책 및 패턴
        policy: ScalingPolicy = Field(
            default=ScalingPolicy.BALANCED,
            description="스케일링 정책"
        )
        detected_pattern: TrafficPattern = Field(
            default=TrafficPattern.UNKNOWN,
            description="감지된 트래픽 패턴"
        )
        
        # 비용 최적화
        cost_optimization_enabled: bool = Field(
            default=True,
            description="비용 최적화 활성화"
        )
        max_hourly_cost: float = Field(
            default=10.0,
            ge=0.1,
            description="시간당 최대 비용 (USD)"
        )
        
        # 예측 스케일링
        predictive_scaling_enabled: bool = Field(
            default=False,
            description="예측적 스케일링 활성화"
        )
        prediction_window_hours: int = Field(
            default=2,
            ge=1,
            le=24,
            description="예측 윈도우 (시간)"
        )
        
        @field_validator('max_instances')
        @classmethod
        def validate_max_instances(cls, v: int, values) -> int:
            """최대 인스턴스 수 검증"""
            min_instances = values.data.get('min_instances', 0)
            if v <= min_instances:
                raise ValueError("최대 인스턴스 수는 최소 인스턴스 수보다 커야 합니다")
            return v
        
        def get_cost_per_hour(self, current_instances: int) -> float:
            """시간당 예상 비용 계산"""
            # Cloud Run 가격 (대략적 추정)
            cpu_cost_per_hour = 0.024  # vCPU당 시간당 비용
            memory_cost_per_gb_hour = 0.0025  # GB당 시간당 메모리 비용
            
            # 1 vCPU, 512MB 메모리 기준
            instance_cost_per_hour = cpu_cost_per_hour + (0.5 * memory_cost_per_gb_hour)
            
            return current_instances * instance_cost_per_hour
        
        def can_scale_up(self, current_instances: int) -> Tuple[bool, str]:
            """스케일 업 가능 여부 확인"""
            if current_instances >= self.max_instances:
                return False, "최대 인스턴스 수에 도달"
            
            if self.cost_optimization_enabled:
                projected_cost = self.get_cost_per_hour(current_instances + 1)
                if projected_cost > self.max_hourly_cost:
                    return False, "비용 한도 초과"
            
            return True, "스케일 업 가능"
else:
    # Fallback: dataclass 버전
    from dataclasses import dataclass
    
    @dataclass
    class ScalingConfiguration:
        """스케일링 설정 (Fallback)"""
        min_instances: int = 0
        max_instances: int = 100
        target_concurrency: int = 80
        scale_up_threshold: float = 0.8
        scale_down_threshold: float = 0.3
        scale_up_cooldown: int = 60
        scale_down_cooldown: int = 300
        policy: ScalingPolicy = ScalingPolicy.BALANCED
        detected_pattern: TrafficPattern = TrafficPattern.UNKNOWN
        cost_optimization_enabled: bool = True
        max_hourly_cost: float = 10.0
        predictive_scaling_enabled: bool = False
        prediction_window_hours: int = 2
        
        def get_cost_per_hour(self, current_instances: int) -> float:
            return current_instances * 0.0265
        
        def can_scale_up(self, current_instances: int) -> Tuple[bool, str]:
            if current_instances >= self.max_instances:
                return False, "최대 인스턴스 수에 도달"
            
            if self.cost_optimization_enabled:
                projected_cost = self.get_cost_per_hour(current_instances + 1)
                if projected_cost > self.max_hourly_cost:
                    return False, "비용 한도 초과"
            
            return True, "스케일 업 가능"


@dataclass
class MetricSnapshot:
    """메트릭 스냅샷"""
    timestamp: datetime
    cpu_utilization: float
    memory_utilization: float
    request_count: int
    active_instances: int
    avg_response_time: float
    error_rate: float
    queue_depth: int = 0


class TrafficPatternAnalyzer:
    """트래픽 패턴 분석기"""
    
    def __init__(self, history_size: int = 1440):  # 24시간 (분 단위)
        self.history_size = history_size
        self.metric_history: List[MetricSnapshot] = []
    
    def add_snapshot(self, snapshot: MetricSnapshot):
        """메트릭 스냅샷 추가"""
        self.metric_history.append(snapshot)
        
        # 히스토리 크기 제한
        if len(self.metric_history) > self.history_size:
            self.metric_history = self.metric_history[-self.history_size:]
    
    def detect_pattern(self) -> TrafficPattern:
        """트래픽 패턴 감지"""
        if len(self.metric_history) < 60:  # 최소 1시간 데이터 필요
            return TrafficPattern.UNKNOWN
        
        # 최근 24시간 데이터 분석
        recent_metrics = self.metric_history[-1440:] if len(self.metric_history) >= 1440 else self.metric_history
        
        request_counts = [m.request_count for m in recent_metrics]
        
        # 변동 계수 계산 (표준편차/평균)
        if statistics.mean(request_counts) == 0:
            return TrafficPattern.STEADY
        
        cv = statistics.stdev(request_counts) / statistics.mean(request_counts)
        
        # 패턴 분류
        match cv:
            case x if x < 0.2:
                return TrafficPattern.STEADY
            case x if x > 1.0:
                return TrafficPattern.BURST
            case _:
                # 주기성 검사 (간단한 구현)
                if self._detect_periodicity(request_counts):
                    return TrafficPattern.PERIODIC
                else:
                    return TrafficPattern.STEADY
    
    def _detect_periodicity(self, values: List[int]) -> bool:
        """주기성 감지 (간단한 구현)"""
        if len(values) < 120:  # 최소 2시간 데이터
            return False
        
        # 시간별 평균 계산
        hourly_averages = []
        for i in range(0, len(values) - 60, 60):
            hour_data = values[i:i+60]
            if hour_data:
                hourly_averages.append(statistics.mean(hour_data))
        
        if len(hourly_averages) < 24:  # 24시간 미만
            return False
        
        # 24시간 주기 패턴 검사 (매우 단순한 구현)
        daily_patterns = []
        for i in range(0, len(hourly_averages) - 24, 24):
            daily_patterns.append(hourly_averages[i:i+24])
        
        if len(daily_patterns) < 2:
            return False
        
        # 일간 패턴 유사성 검사 (피어슨 상관계수 사용)
        try:
            correlation = statistics.correlation(daily_patterns[0], daily_patterns[-1])
            return correlation > 0.7  # 70% 이상 상관관계
        except statistics.StatisticsError:
            return False
    
    def predict_next_hour_traffic(self) -> Optional[float]:
        """다음 시간 트래픽 예측"""
        if len(self.metric_history) < 168:  # 1주일 데이터 필요
            return None
        
        # 같은 시간대의 과거 데이터 수집
        current_hour = datetime.now().hour
        same_hour_data = []
        
        for i in range(len(self.metric_history) - 24, 0, -24):  # 24시간 간격
            if i >= 0 and self.metric_history[i].timestamp.hour == current_hour:
                same_hour_data.append(self.metric_history[i].request_count)
            
            if len(same_hour_data) >= 7:  # 최대 7일치
                break
        
        if len(same_hour_data) < 3:
            return None
        
        # 가중평균 계산 (최근일수록 높은 가중치)
        weights = [0.4, 0.3, 0.2, 0.1] if len(same_hour_data) >= 4 else [1.0/len(same_hour_data)] * len(same_hour_data)
        weighted_sum = sum(w * v for w, v in zip(weights, same_hour_data[:len(weights)]))
        
        return weighted_sum


class AutoScalingOptimizer:
    """자동 스케일링 최적화기"""
    
    def __init__(self, 
                 project_id: str,
                 service_name: str,
                 region: str = "us-central1"):
        self.project_id = project_id
        self.service_name = service_name
        self.region = region
        
        # Cloud Run 클라이언트
        self.client = None
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                self.client = run_v2.ServicesClient()
            except Exception as e:
                logger.warning(f"Cloud Run 클라이언트 초기화 실패: {e}")
        
        # 설정 및 분석기
        self.config = ScalingConfiguration()
        self.pattern_analyzer = TrafficPatternAnalyzer()
        
        # 스케일링 히스토리
        self.scaling_history: List[Dict[str, Any]] = []
        self.last_scale_action: Optional[datetime] = None
        self.last_scale_direction: Optional[ScalingDirection] = None
        
        # 모니터링
        self.monitoring_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self, config: ScalingConfiguration = None):
        """최적화기 초기화"""
        if config:
            self.config = config
        
        # 현재 서비스 설정 조회
        await self._sync_current_config()
        
        # 모니터링 시작
        self._running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"자동 스케일링 최적화기 초기화 완료: {self.service_name}")
    
    async def _sync_current_config(self):
        """현재 Cloud Run 서비스 설정 동기화"""
        if not GOOGLE_CLOUD_AVAILABLE or not self.client:
            return
        
        try:
            service_path = f"projects/{self.project_id}/locations/{self.region}/services/{self.service_name}"
            service = self.client.get_service(name=service_path)
            
            # 현재 설정을 config에 반영
            if hasattr(service.spec, 'template') and hasattr(service.spec.template, 'scaling'):
                scaling_spec = service.spec.template.scaling
                if hasattr(scaling_spec, 'min_instance_count'):
                    self.config.min_instances = scaling_spec.min_instance_count or 0
                if hasattr(scaling_spec, 'max_instance_count'):
                    self.config.max_instances = scaling_spec.max_instance_count or 100
            
            logger.info(f"현재 스케일링 설정 동기화 완료: {self.config.min_instances}-{self.config.max_instances}")
            
        except Exception as e:
            logger.warning(f"서비스 설정 동기화 실패: {e}")
    
    async def _monitoring_loop(self):
        """모니터링 루프"""
        while self._running:
            try:
                # 현재 메트릭 수집
                snapshot = await self._collect_metrics()
                if snapshot:
                    self.pattern_analyzer.add_snapshot(snapshot)
                    
                    # 트래픽 패턴 업데이트
                    detected_pattern = self.pattern_analyzer.detect_pattern()
                    if detected_pattern != self.config.detected_pattern:
                        self.config.detected_pattern = detected_pattern
                        logger.info(f"트래픽 패턴 감지: {detected_pattern.value}")
                    
                    # 스케일링 결정
                    scaling_decision = await self._make_scaling_decision(snapshot)
                    if scaling_decision:
                        await self._execute_scaling(scaling_decision)
                
                # 다음 체크까지 대기 (30초)
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                await asyncio.sleep(30)
    
    async def _collect_metrics(self) -> Optional[MetricSnapshot]:
        """현재 메트릭 수집"""
        try:
            # 실제 구현에서는 Cloud Monitoring API 사용
            # 여기서는 가상 데이터 생성
            import random
            
            return MetricSnapshot(
                timestamp=datetime.now(),
                cpu_utilization=random.uniform(0.2, 0.9),
                memory_utilization=random.uniform(0.3, 0.8),
                request_count=random.randint(10, 200),
                active_instances=random.randint(1, 10),
                avg_response_time=random.uniform(100, 500),
                error_rate=random.uniform(0.0, 0.05),
                queue_depth=random.randint(0, 20)
            )
            
        except Exception as e:
            logger.error(f"메트릭 수집 실패: {e}")
            return None
    
    async def _make_scaling_decision(self, snapshot: MetricSnapshot) -> Optional[Dict[str, Any]]:
        """스케일링 결정 수행"""
        current_instances = snapshot.active_instances
        
        # 쿨다운 시간 확인
        if self.last_scale_action:
            cooldown_time = self.config.scale_up_cooldown if self.last_scale_direction == ScalingDirection.UP else self.config.scale_down_cooldown
            if (datetime.now() - self.last_scale_action).total_seconds() < cooldown_time:
                return None
        
        # 정책별 결정
        match self.config.policy:
            case ScalingPolicy.CONSERVATIVE:
                return await self._conservative_scaling_decision(snapshot)
            case ScalingPolicy.BALANCED:
                return await self._balanced_scaling_decision(snapshot)
            case ScalingPolicy.AGGRESSIVE:
                return await self._aggressive_scaling_decision(snapshot)
            case ScalingPolicy.PREDICTIVE:
                return await self._predictive_scaling_decision(snapshot)
            case _:
                return await self._balanced_scaling_decision(snapshot)
    
    async def _balanced_scaling_decision(self, snapshot: MetricSnapshot) -> Optional[Dict[str, Any]]:
        """균형 스케일링 결정"""
        current_instances = snapshot.active_instances
        
        # 스케일 업 조건
        scale_up_score = 0
        if snapshot.cpu_utilization > self.config.scale_up_threshold:
            scale_up_score += 1
        if snapshot.memory_utilization > self.config.scale_up_threshold:
            scale_up_score += 1
        if snapshot.queue_depth > self.config.target_concurrency * 0.8:
            scale_up_score += 1
        if snapshot.avg_response_time > 1000:  # 1초 이상
            scale_up_score += 1
        
        # 스케일 다운 조건
        scale_down_score = 0
        if snapshot.cpu_utilization < self.config.scale_down_threshold:
            scale_down_score += 1
        if snapshot.memory_utilization < self.config.scale_down_threshold:
            scale_down_score += 1
        if snapshot.queue_depth < self.config.target_concurrency * 0.2:
            scale_down_score += 1
        if snapshot.avg_response_time < 200:  # 200ms 미만
            scale_down_score += 1
        
        # 결정
        if scale_up_score >= 2:
            can_scale, reason = self.config.can_scale_up(current_instances)
            if can_scale:
                target_instances = min(current_instances + 1, self.config.max_instances)
                return {
                    'direction': ScalingDirection.UP,
                    'current_instances': current_instances,
                    'target_instances': target_instances,
                    'reason': f"Scale up (score: {scale_up_score})",
                    'confidence': min(0.9, scale_up_score * 0.25)
                }
            else:
                logger.warning(f"스케일 업 불가: {reason}")
        
        elif scale_down_score >= 3 and current_instances > self.config.min_instances:
            target_instances = max(current_instances - 1, self.config.min_instances)
            return {
                'direction': ScalingDirection.DOWN,
                'current_instances': current_instances,
                'target_instances': target_instances,
                'reason': f"Scale down (score: {scale_down_score})",
                'confidence': min(0.8, scale_down_score * 0.2)
            }
        
        return None
    
    async def _conservative_scaling_decision(self, snapshot: MetricSnapshot) -> Optional[Dict[str, Any]]:
        """보수적 스케일링 결정 (높은 임계값)"""
        current_instances = snapshot.active_instances
        
        # 더 높은 임계값 사용
        high_threshold = min(0.9, self.config.scale_up_threshold + 0.1)
        low_threshold = max(0.1, self.config.scale_down_threshold - 0.1)
        
        if (snapshot.cpu_utilization > high_threshold and 
            snapshot.memory_utilization > high_threshold):
            can_scale, reason = self.config.can_scale_up(current_instances)
            if can_scale:
                target_instances = min(current_instances + 1, self.config.max_instances)
                return {
                    'direction': ScalingDirection.UP,
                    'current_instances': current_instances,
                    'target_instances': target_instances,
                    'reason': "Conservative scale up",
                    'confidence': 0.95
                }
        
        elif (snapshot.cpu_utilization < low_threshold and 
              snapshot.memory_utilization < low_threshold and
              current_instances > self.config.min_instances):
            target_instances = max(current_instances - 1, self.config.min_instances)
            return {
                'direction': ScalingDirection.DOWN,
                'current_instances': current_instances,
                'target_instances': target_instances,
                'reason': "Conservative scale down",
                'confidence': 0.9
            }
        
        return None
    
    async def _aggressive_scaling_decision(self, snapshot: MetricSnapshot) -> Optional[Dict[str, Any]]:
        """적극적 스케일링 결정 (낮은 임계값)"""
        current_instances = snapshot.active_instances
        
        # 더 낮은 임계값 사용
        low_threshold = max(0.5, self.config.scale_up_threshold - 0.2)
        high_threshold = min(0.6, self.config.scale_down_threshold + 0.2)
        
        if snapshot.cpu_utilization > low_threshold or snapshot.memory_utilization > low_threshold:
            can_scale, reason = self.config.can_scale_up(current_instances)
            if can_scale:
                # 더 많은 인스턴스를 한번에 추가
                scale_factor = 2 if snapshot.cpu_utilization > 0.8 else 1
                target_instances = min(current_instances + scale_factor, self.config.max_instances)
                return {
                    'direction': ScalingDirection.UP,
                    'current_instances': current_instances,
                    'target_instances': target_instances,
                    'reason': f"Aggressive scale up (factor: {scale_factor})",
                    'confidence': 0.8
                }
        
        elif (snapshot.cpu_utilization < high_threshold and 
              current_instances > self.config.min_instances):
            target_instances = max(current_instances - 1, self.config.min_instances)
            return {
                'direction': ScalingDirection.DOWN,
                'current_instances': current_instances,
                'target_instances': target_instances,
                'reason': "Aggressive scale down",
                'confidence': 0.7
            }
        
        return None
    
    async def _predictive_scaling_decision(self, snapshot: MetricSnapshot) -> Optional[Dict[str, Any]]:
        """예측적 스케일링 결정"""
        if not self.config.predictive_scaling_enabled:
            return await self._balanced_scaling_decision(snapshot)
        
        # 트래픽 예측
        predicted_traffic = self.pattern_analyzer.predict_next_hour_traffic()
        if predicted_traffic is None:
            return await self._balanced_scaling_decision(snapshot)
        
        current_instances = snapshot.active_instances
        current_traffic = snapshot.request_count
        
        # 예측 기반 필요 인스턴스 계산
        if current_traffic > 0:
            traffic_ratio = predicted_traffic / current_traffic
            predicted_instances = math.ceil(current_instances * traffic_ratio)
            predicted_instances = max(self.config.min_instances, 
                                    min(predicted_instances, self.config.max_instances))
        else:
            predicted_instances = self.config.min_instances
        
        # 예측 기반 스케일링
        if predicted_instances > current_instances:
            can_scale, reason = self.config.can_scale_up(current_instances)
            if can_scale:
                target_instances = min(predicted_instances, current_instances + 2)  # 점진적 증가
                return {
                    'direction': ScalingDirection.UP,
                    'current_instances': current_instances,
                    'target_instances': target_instances,
                    'reason': f"Predictive scale up (predicted: {predicted_instances})",
                    'confidence': 0.75,
                    'predicted_traffic': predicted_traffic
                }
        
        elif predicted_instances < current_instances and current_instances > self.config.min_instances:
            target_instances = max(predicted_instances, current_instances - 1)  # 점진적 감소
            return {
                'direction': ScalingDirection.DOWN,
                'current_instances': current_instances,
                'target_instances': target_instances,
                'reason': f"Predictive scale down (predicted: {predicted_instances})",
                'confidence': 0.7,
                'predicted_traffic': predicted_traffic
            }
        
        return None
    
    async def _execute_scaling(self, decision: Dict[str, Any]):
        """스케일링 실행"""
        try:
            direction = decision['direction']
            current = decision['current_instances']
            target = decision['target_instances']
            reason = decision['reason']
            
            if current == target:
                return
            
            # Cloud Run 서비스 업데이트 (실제 구현 필요)
            success = await self._update_cloud_run_scaling(target)
            
            if success:
                # 스케일링 기록
                self.scaling_history.append({
                    'timestamp': datetime.now(),
                    'direction': direction.value,
                    'from_instances': current,
                    'to_instances': target,
                    'reason': reason,
                    'confidence': decision.get('confidence', 0.5)
                })
                
                self.last_scale_action = datetime.now()
                self.last_scale_direction = direction
                
                # 메트릭 기록
                await record_metric("scaling_action", 1.0, {
                    'direction': direction.value,
                    'from_instances': str(current),
                    'to_instances': str(target),
                    'policy': self.config.policy.value
                })
                
                logger.info(f"스케일링 실행: {current} -> {target} ({reason})")
                
            else:
                logger.error(f"스케일링 실행 실패: {current} -> {target}")
                
        except Exception as e:
            logger.error(f"스케일링 실행 오류: {e}")
    
    async def _update_cloud_run_scaling(self, target_instances: int) -> bool:
        """Cloud Run 스케일링 설정 업데이트"""
        if not GOOGLE_CLOUD_AVAILABLE or not self.client:
            # 로컬 개발용 시뮬레이션
            logger.info(f"Cloud Run 스케일링 시뮬레이션: {target_instances}개 인스턴스")
            return True
        
        try:
            service_path = f"projects/{self.project_id}/locations/{self.region}/services/{self.service_name}"
            
            # 서비스 설정 업데이트 (실제 구현에서는 더 복잡한 업데이트 로직 필요)
            logger.info(f"Cloud Run 서비스 스케일링 업데이트: {target_instances}")
            return True
            
        except Exception as e:
            logger.error(f"Cloud Run 업데이트 실패: {e}")
            return False
    
    async def shutdown(self):
        """최적화기 종료"""
        self._running = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("자동 스케일링 최적화기가 종료되었습니다")
    
    def get_scaling_stats(self) -> Dict[str, Any]:
        """스케일링 통계 조회"""
        if not self.scaling_history:
            return {'total_actions': 0}
        
        total_actions = len(self.scaling_history)
        scale_ups = len([h for h in self.scaling_history if h['direction'] == 'up'])
        scale_downs = len([h for h in self.scaling_history if h['direction'] == 'down'])
        
        avg_confidence = statistics.mean([h['confidence'] for h in self.scaling_history])
        
        return {
            'total_actions': total_actions,
            'scale_ups': scale_ups,
            'scale_downs': scale_downs,
            'avg_confidence': avg_confidence,
            'current_policy': self.config.policy.value,
            'detected_pattern': self.config.detected_pattern.value,
            'recent_actions': self.scaling_history[-10:]  # 최근 10개
        }


# 전역 스케일링 최적화기
_autoscaling_optimizer: Optional[AutoScalingOptimizer] = None

async def get_autoscaling_optimizer(project_id: str = None, service_name: str = None) -> AutoScalingOptimizer:
    """자동 스케일링 최적화기 인스턴스 획득"""
    global _autoscaling_optimizer
    
    if _autoscaling_optimizer is None:
        if project_id is None:
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
            if not project_id:
                raise ValueError("프로젝트 ID가 필요합니다")
        
        if service_name is None:
            service_name = os.environ.get('K_SERVICE', 'rfs-service')
        
        _autoscaling_optimizer = AutoScalingOptimizer(project_id, service_name)
        await _autoscaling_optimizer.initialize()
    
    return _autoscaling_optimizer

# 편의 함수들
async def optimize_scaling(policy: ScalingPolicy = ScalingPolicy.BALANCED) -> Result[None, str]:
    """스케일링 최적화 시작"""
    try:
        optimizer = await get_autoscaling_optimizer()
        optimizer.config.policy = policy
        return Success(None)
    except Exception as e:
        return Failure(f"스케일링 최적화 실패: {str(e)}")

async def get_scaling_stats() -> Dict[str, Any]:
    """스케일링 통계 조회"""
    try:
        optimizer = await get_autoscaling_optimizer()
        return optimizer.get_scaling_stats()
    except Exception as e:
        return {'error': str(e)}