"""
LLM 성능 메트릭 수집기

LLM 호출의 성능, 성공률, 응답 시간 등을 수집하고 분석하는 모듈입니다.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import asyncio
from contextlib import asynccontextmanager

from rfs.core.result import Result, Success, Failure
from rfs.core.config import get_config
from rfs.hof.core import pipe, curry


@dataclass
class LLMMetrics:
    """LLM 호출 메트릭 데이터"""
    provider: str
    model: str
    timestamp: datetime
    duration_ms: float
    success: bool
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    error_type: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@dataclass
class MetricsSummary:
    """메트릭 요약 정보"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    error_distribution: Dict[str, int] = field(default_factory=dict)
    model_distribution: Dict[str, int] = field(default_factory=dict)


class LLMMetricsCollector:
    """LLM 메트릭 수집기
    
    LLM 호출의 성능 메트릭을 수집하고 분석하는 클래스입니다.
    """
    
    def __init__(self, max_history: int = 10000):
        """메트릭 수집기 초기화
        
        Args:
            max_history: 보관할 최대 메트릭 수 (메모리 관리)
        """
        self.max_history = max_history
        self.metrics: deque[LLMMetrics] = deque(maxlen=max_history)
        self._lock = asyncio.Lock()
        
        # 성능 최적화를 위한 실시간 카운터
        self._counters = defaultdict(int)
        self._running_totals = defaultdict(float)
    
    async def record_metric(self, metric: LLMMetrics) -> Result[None, str]:
        """메트릭 기록
        
        Args:
            metric: 기록할 메트릭 데이터
            
        Returns:
            Result[None, str]: 성공 시 None, 실패 시 에러 메시지
        """
        try:
            async with self._lock:
                self.metrics.append(metric)
                
                # 실시간 카운터 업데이트
                key_prefix = f"{metric.provider}:{metric.model}"
                
                self._counters[f"{key_prefix}:total"] += 1
                if metric.success:
                    self._counters[f"{key_prefix}:success"] += 1
                else:
                    self._counters[f"{key_prefix}:error"] += 1
                    if metric.error_type:
                        self._counters[f"{key_prefix}:error:{metric.error_type}"] += 1
                
                self._running_totals[f"{key_prefix}:duration"] += metric.duration_ms
                if metric.tokens_used:
                    self._running_totals[f"{key_prefix}:tokens"] += metric.tokens_used
                if metric.cost:
                    self._running_totals[f"{key_prefix}:cost"] += metric.cost
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"메트릭 기록 실패: {str(e)}")
    
    @asynccontextmanager
    async def measure_call(
        self, 
        provider: str, 
        model: str,
        track_tokens: bool = True
    ):
        """LLM 호출 측정을 위한 컨텍스트 매니저
        
        사용법:
            async with collector.measure_call("openai", "gpt-4") as measurement:
                result = await llm_call()
                if result.is_success():
                    measurement.set_success(result.unwrap())
                else:
                    measurement.set_error(result.unwrap_error())
        """
        start_time = time.perf_counter()
        measurement = CallMeasurement(provider, model, start_time, track_tokens)
        
        try:
            yield measurement
        finally:
            # 측정 완료 후 메트릭 기록
            metric = measurement.to_metric()
            await self.record_metric(metric)
    
    def get_summary(self, 
                   provider: Optional[str] = None,
                   model: Optional[str] = None,
                   since: Optional[datetime] = None) -> Result[MetricsSummary, str]:
        """메트릭 요약 정보 조회
        
        Args:
            provider: 특정 제공자로 필터링
            model: 특정 모델로 필터링
            since: 특정 시간 이후 데이터만 포함
            
        Returns:
            Result[MetricsSummary, str]: 요약 정보 또는 에러 메시지
        """
        try:
            # 필터 조건에 맞는 메트릭 선별
            filtered_metrics = self._filter_metrics(provider, model, since)
            
            if not filtered_metrics:
                return Success(MetricsSummary())
            
            # 기본 통계 계산
            total_calls = len(filtered_metrics)
            successful_calls = sum(1 for m in filtered_metrics if m.success)
            failed_calls = total_calls - successful_calls
            
            success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0.0
            
            # 평균 응답 시간
            total_duration = sum(m.duration_ms for m in filtered_metrics)
            avg_duration = total_duration / total_calls if total_calls > 0 else 0.0
            
            # 토큰 및 비용 합계
            total_tokens = sum(m.tokens_used or 0 for m in filtered_metrics)
            total_cost = sum(m.cost or 0 for m in filtered_metrics)
            
            # 에러 분포
            error_distribution = defaultdict(int)
            for m in filtered_metrics:
                if not m.success and m.error_type:
                    error_distribution[m.error_type] += 1
            
            # 모델 분포
            model_distribution = defaultdict(int)
            for m in filtered_metrics:
                key = f"{m.provider}:{m.model}"
                model_distribution[key] += 1
            
            return Success(MetricsSummary(
                total_calls=total_calls,
                successful_calls=successful_calls,
                failed_calls=failed_calls,
                success_rate=success_rate,
                avg_duration_ms=avg_duration,
                total_tokens=total_tokens,
                total_cost=total_cost,
                error_distribution=dict(error_distribution),
                model_distribution=dict(model_distribution)
            ))
            
        except Exception as e:
            return Failure(f"메트릭 요약 생성 실패: {str(e)}")
    
    def _filter_metrics(self, 
                       provider: Optional[str],
                       model: Optional[str],
                       since: Optional[datetime]) -> List[LLMMetrics]:
        """메트릭 필터링"""
        filtered = list(self.metrics)
        
        if provider:
            filtered = [m for m in filtered if m.provider == provider]
        
        if model:
            filtered = [m for m in filtered if m.model == model]
        
        if since:
            filtered = [m for m in filtered if m.timestamp >= since]
        
        return filtered
    
    def get_performance_trends(self, 
                             window_minutes: int = 60,
                             provider: Optional[str] = None) -> Result[Dict[str, Any], str]:
        """성능 추세 분석
        
        Args:
            window_minutes: 분석 시간 윈도우 (분)
            provider: 특정 제공자로 필터링
            
        Returns:
            Result[Dict[str, Any], str]: 추세 분석 결과
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            recent_metrics = self._filter_metrics(provider, None, cutoff_time)
            
            if not recent_metrics:
                return Success({
                    "window_minutes": window_minutes,
                    "data_points": 0,
                    "trends": {}
                })
            
            # 시간별 성능 분포 (10분 간격)
            interval_minutes = min(10, window_minutes // 6)
            time_buckets = defaultdict(list)
            
            for metric in recent_metrics:
                # 시간을 interval_minutes 단위로 버킷화
                bucket_time = metric.timestamp.replace(
                    minute=(metric.timestamp.minute // interval_minutes) * interval_minutes,
                    second=0,
                    microsecond=0
                )
                time_buckets[bucket_time].append(metric)
            
            # 각 버킷의 통계 계산
            trends = {}
            for bucket_time, bucket_metrics in time_buckets.items():
                success_rate = sum(1 for m in bucket_metrics if m.success) / len(bucket_metrics) * 100
                avg_duration = sum(m.duration_ms for m in bucket_metrics) / len(bucket_metrics)
                
                trends[bucket_time.isoformat()] = {
                    "success_rate": success_rate,
                    "avg_duration_ms": avg_duration,
                    "call_count": len(bucket_metrics),
                    "total_tokens": sum(m.tokens_used or 0 for m in bucket_metrics),
                    "total_cost": sum(m.cost or 0 for m in bucket_metrics)
                }
            
            return Success({
                "window_minutes": window_minutes,
                "interval_minutes": interval_minutes,
                "data_points": len(recent_metrics),
                "trends": trends
            })
            
        except Exception as e:
            return Failure(f"성능 추세 분석 실패: {str(e)}")
    
    def get_error_analysis(self, 
                          since: Optional[datetime] = None) -> Result[Dict[str, Any], str]:
        """에러 분석
        
        Args:
            since: 분석 시작 시간
            
        Returns:
            Result[Dict[str, Any], str]: 에러 분석 결과
        """
        try:
            filtered_metrics = self._filter_metrics(None, None, since)
            failed_metrics = [m for m in filtered_metrics if not m.success]
            
            if not failed_metrics:
                return Success({
                    "total_errors": 0,
                    "error_types": {},
                    "error_by_provider": {},
                    "error_by_model": {}
                })
            
            # 에러 유형별 분석
            error_types = defaultdict(lambda: {"count": 0, "examples": []})
            for metric in failed_metrics:
                if metric.error_type:
                    error_types[metric.error_type]["count"] += 1
                    if len(error_types[metric.error_type]["examples"]) < 3:
                        error_types[metric.error_type]["examples"].append({
                            "timestamp": metric.timestamp.isoformat(),
                            "provider": metric.provider,
                            "model": metric.model
                        })
            
            # 제공자별 에러
            error_by_provider = defaultdict(int)
            for metric in failed_metrics:
                error_by_provider[metric.provider] += 1
            
            # 모델별 에러
            error_by_model = defaultdict(int)
            for metric in failed_metrics:
                key = f"{metric.provider}:{metric.model}"
                error_by_model[key] += 1
            
            return Success({
                "total_errors": len(failed_metrics),
                "error_types": dict(error_types),
                "error_by_provider": dict(error_by_provider),
                "error_by_model": dict(error_by_model)
            })
            
        except Exception as e:
            return Failure(f"에러 분석 실패: {str(e)}")
    
    async def export_metrics(self, 
                           format_type: str = "json",
                           provider: Optional[str] = None,
                           since: Optional[datetime] = None) -> Result[Dict[str, Any], str]:
        """메트릭 데이터 내보내기
        
        Args:
            format_type: 내보내기 형식 (json, csv)
            provider: 특정 제공자로 필터링
            since: 시작 시간
            
        Returns:
            Result[Dict[str, Any], str]: 내보내기 데이터 또는 에러 메시지
        """
        try:
            async with self._lock:
                filtered_metrics = self._filter_metrics(provider, None, since)
            
            if format_type == "json":
                data = {
                    "export_timestamp": datetime.now().isoformat(),
                    "total_records": len(filtered_metrics),
                    "metrics": [
                        {
                            "provider": m.provider,
                            "model": m.model,
                            "timestamp": m.timestamp.isoformat(),
                            "duration_ms": m.duration_ms,
                            "success": m.success,
                            "tokens_used": m.tokens_used,
                            "cost": m.cost,
                            "error_type": m.error_type,
                            "prompt_tokens": m.prompt_tokens,
                            "completion_tokens": m.completion_tokens
                        }
                        for m in filtered_metrics
                    ]
                }
                return Success(data)
            
            else:
                return Failure(f"지원하지 않는 형식: {format_type}")
                
        except Exception as e:
            return Failure(f"메트릭 내보내기 실패: {str(e)}")
    
    async def cleanup_old_metrics(self, older_than_days: int = 7) -> Result[int, str]:
        """오래된 메트릭 정리
        
        Args:
            older_than_days: 삭제할 메트릭 기준일 수
            
        Returns:
            Result[int, str]: 삭제된 메트릭 수 또는 에러 메시지
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=older_than_days)
            
            async with self._lock:
                original_count = len(self.metrics)
                # deque을 리스트로 변환하여 필터링 후 다시 deque로 변환
                filtered_metrics = [
                    m for m in self.metrics 
                    if m.timestamp >= cutoff_time
                ]
                
                self.metrics.clear()
                self.metrics.extend(filtered_metrics)
                
                deleted_count = original_count - len(self.metrics)
            
            return Success(deleted_count)
            
        except Exception as e:
            return Failure(f"메트릭 정리 실패: {str(e)}")


class CallMeasurement:
    """LLM 호출 측정 헬퍼 클래스"""
    
    def __init__(self, provider: str, model: str, start_time: float, track_tokens: bool):
        self.provider = provider
        self.model = model
        self.start_time = start_time
        self.track_tokens = track_tokens
        
        self.success = False
        self.tokens_used: Optional[int] = None
        self.cost: Optional[float] = None
        self.error_type: Optional[str] = None
        self.prompt_tokens: Optional[int] = None
        self.completion_tokens: Optional[int] = None
    
    def set_success(self, response_data: Dict[str, Any]):
        """성공 결과 설정"""
        self.success = True
        
        if self.track_tokens:
            # 토큰 정보 추출
            if "usage" in response_data:
                usage = response_data["usage"]
                self.prompt_tokens = usage.get("prompt_tokens")
                self.completion_tokens = usage.get("completion_tokens")
                self.tokens_used = usage.get("total_tokens")
            
            # 비용 계산 (간단한 추정)
            if self.tokens_used:
                self.cost = self._estimate_cost()
    
    def set_error(self, error_message: str):
        """에러 결과 설정"""
        self.success = False
        
        # 에러 유형 분류
        error_lower = error_message.lower()
        if "rate limit" in error_lower or "quota" in error_lower:
            self.error_type = "rate_limit"
        elif "auth" in error_lower or "api key" in error_lower:
            self.error_type = "authentication"
        elif "timeout" in error_lower:
            self.error_type = "timeout"
        elif "network" in error_lower or "connection" in error_lower:
            self.error_type = "network"
        else:
            self.error_type = "unknown"
    
    def to_metric(self) -> LLMMetrics:
        """메트릭 객체 생성"""
        end_time = time.perf_counter()
        duration_ms = (end_time - self.start_time) * 1000
        
        return LLMMetrics(
            provider=self.provider,
            model=self.model,
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            success=self.success,
            tokens_used=self.tokens_used,
            cost=self.cost,
            error_type=self.error_type,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens
        )
    
    def _estimate_cost(self) -> Optional[float]:
        """비용 추정 (간단한 버전)"""
        if not self.tokens_used:
            return None
        
        # 기본적인 토큰당 비용 (실제로는 더 정확한 모델별 가격 필요)
        cost_per_1k_tokens = {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.002,
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003
        }
        
        base_cost = cost_per_1k_tokens.get(self.model, 0.01)
        return (self.tokens_used / 1000) * base_cost


# 전역 메트릭 수집기 인스턴스 (옵션)
_global_metrics_collector: Optional[LLMMetricsCollector] = None


def get_metrics_collector() -> LLMMetricsCollector:
    """전역 메트릭 수집기 조회 또는 생성"""
    global _global_metrics_collector
    
    if _global_metrics_collector is None:
        max_history = get_config("llm.monitoring.max_history", 10000)
        _global_metrics_collector = LLMMetricsCollector(max_history)
    
    return _global_metrics_collector


# HOF 유틸리티
@curry
async def with_metrics_collection(provider: str, model: str, func, *args, **kwargs):
    """메트릭 수집과 함께 함수 실행
    
    사용법:
        collect_openai_metrics = with_metrics_collection("openai", "gpt-4")
        result = await collect_openai_metrics(some_llm_function, arg1, arg2)
    """
    collector = get_metrics_collector()
    
    async with collector.measure_call(provider, model) as measurement:
        try:
            result = await func(*args, **kwargs)
            
            if hasattr(result, 'is_success') and result.is_success():
                response_data = result.unwrap()
                measurement.set_success(response_data)
            elif hasattr(result, 'is_failure') and result.is_failure():
                error_msg = result.unwrap_error()
                measurement.set_error(error_msg)
            else:
                # 일반 성공 응답으로 처리
                measurement.set_success({})
            
            return result
            
        except Exception as e:
            measurement.set_error(str(e))
            raise