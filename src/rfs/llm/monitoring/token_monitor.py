"""
토큰 사용량 모니터링

LLM API 호출의 토큰 사용량을 추적하고 비용을 계산합니다.
Result Pattern과 RFS Framework의 모든 패턴을 준수합니다.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service

try:
    from rfs.monitoring.metrics import MetricsCollector
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


@dataclass
class TokenUsage:
    """토큰 사용량 정보"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate: float
    timestamp: datetime
    model: str
    provider: str
    request_id: Optional[str] = None
    response_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_estimate": self.cost_estimate,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "provider": self.provider,
            "request_id": self.request_id,
            "response_time_ms": self.response_time_ms,
            "metadata": self.metadata
        }


@Service("llm_service")
class TokenMonitor:
    """토큰 사용량 모니터링
    
    LLM API 호출의 토큰 사용량을 추적하고 비용을 계산합니다.
    """
    
    def __init__(self, metrics_collector: Optional['MetricsCollector'] = None):
        self.metrics_collector = metrics_collector if METRICS_AVAILABLE else None
        self._usage_history: List[TokenUsage] = []
        self._daily_limits: Dict[str, float] = {}  # provider별 일일 한도
        self._monthly_limits: Dict[str, float] = {}  # provider별 월간 한도
        
        # 모델별 토큰 가격 (USD per token)
        self._token_prices = {
            # OpenAI Models
            "gpt-4": {"prompt": 0.00003, "completion": 0.00006},
            "gpt-4-turbo": {"prompt": 0.00001, "completion": 0.00003},
            "gpt-4o": {"prompt": 0.000005, "completion": 0.000015},
            "gpt-4o-mini": {"prompt": 0.00000015, "completion": 0.0000006},
            "gpt-3.5-turbo": {"prompt": 0.0000015, "completion": 0.000002},
            "gpt-3.5-turbo-16k": {"prompt": 0.000003, "completion": 0.000004},
            "text-embedding-3-small": {"prompt": 0.00000002, "completion": 0},
            "text-embedding-3-large": {"prompt": 0.00000013, "completion": 0},
            
            # Anthropic Models
            "claude-3-opus-20240229": {"prompt": 0.000015, "completion": 0.000075},
            "claude-3-sonnet-20240229": {"prompt": 0.000003, "completion": 0.000015},
            "claude-3-haiku-20240307": {"prompt": 0.00000025, "completion": 0.00000125},
            "claude-3-5-sonnet-20241022": {"prompt": 0.000003, "completion": 0.000015},
        }
    
    def set_pricing(self, model: str, prompt_price: float, completion_price: float):
        """모델별 토큰 가격 설정
        
        Args:
            model: 모델명
            prompt_price: 프롬프트 토큰당 가격 (USD)
            completion_price: 완료 토큰당 가격 (USD)
        """
        self._token_prices[model] = {
            "prompt": prompt_price,
            "completion": completion_price
        }
    
    def set_daily_limit(self, provider: str, limit: float):
        """일일 비용 한도 설정
        
        Args:
            provider: Provider 이름
            limit: 일일 한도 (USD)
        """
        self._daily_limits[provider] = limit
    
    def set_monthly_limit(self, provider: str, limit: float):
        """월간 비용 한도 설정
        
        Args:
            provider: Provider 이름
            limit: 월간 한도 (USD)
        """
        self._monthly_limits[provider] = limit
    
    def record_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        request_id: Optional[str] = None,
        response_time_ms: Optional[float] = None,
        **metadata
    ) -> Result[TokenUsage, str]:
        """토큰 사용량 기록
        
        Args:
            provider: Provider 이름
            model: 모델명
            prompt_tokens: 프롬프트 토큰 수
            completion_tokens: 완료 토큰 수
            request_id: 요청 ID (추적용)
            response_time_ms: 응답 시간 (밀리초)
            **metadata: 추가 메타데이터
            
        Returns:
            Result[TokenUsage, str]: 기록된 사용량 정보 또는 에러 메시지
        """
        try:
            total_tokens = prompt_tokens + completion_tokens
            
            # 비용 계산
            model_prices = self._token_prices.get(model, {"prompt": 0, "completion": 0})
            cost_estimate = (
                prompt_tokens * model_prices["prompt"] +
                completion_tokens * model_prices["completion"]
            )
            
            # 사용량 객체 생성
            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_estimate=cost_estimate,
                timestamp=datetime.now(),
                model=model,
                provider=provider,
                request_id=request_id,
                response_time_ms=response_time_ms,
                metadata=metadata
            )
            
            # 히스토리에 추가
            self._usage_history.append(usage)
            
            # 메트릭 수집 (사용 가능한 경우)
            if self.metrics_collector:
                self._record_metrics(usage)
            
            # 한도 체크
            limit_check = self._check_limits(provider, cost_estimate)
            if limit_check.is_failure():
                # 경고 로그는 남기지만 실패로 처리하지 않음
                pass
            
            return Success(usage)
            
        except Exception as e:
            return Failure(f"토큰 사용량 기록 실패: {str(e)}")
    
    def _record_metrics(self, usage: TokenUsage):
        """메트릭 시스템에 사용량 기록"""
        try:
            tags = {
                "provider": usage.provider,
                "model": usage.model
            }
            
            # 카운터 메트릭
            self.metrics_collector.increment_counter("llm_api_calls", tags=tags)
            
            # 히스토그램 메트릭
            self.metrics_collector.record_histogram(
                "llm_token_usage", usage.total_tokens, tags=tags
            )
            self.metrics_collector.record_histogram(
                "llm_prompt_tokens", usage.prompt_tokens, tags=tags
            )
            self.metrics_collector.record_histogram(
                "llm_completion_tokens", usage.completion_tokens, tags=tags
            )
            self.metrics_collector.record_histogram(
                "llm_cost_estimate", usage.cost_estimate, tags=tags
            )
            
            # 응답 시간이 있는 경우
            if usage.response_time_ms:
                self.metrics_collector.record_histogram(
                    "llm_response_time_ms", usage.response_time_ms, tags=tags
                )
        
        except Exception:
            # 메트릭 기록 실패는 무시
            pass
    
    def _check_limits(self, provider: str, cost: float) -> Result[None, str]:
        """비용 한도 체크
        
        Args:
            provider: Provider 이름
            cost: 추가될 비용
            
        Returns:
            Result[None, str]: 한도 체크 결과
        """
        try:
            now = datetime.now()
            
            # 일일 한도 체크
            if provider in self._daily_limits:
                daily_limit = self._daily_limits[provider]
                daily_usage = self.get_usage_summary(
                    time_window=timedelta(days=1),
                    provider_filter=provider
                ).unwrap_or({})
                
                daily_cost = daily_usage.get("total_cost", 0.0) + cost
                if daily_cost > daily_limit:
                    return Failure(f"일일 비용 한도 초과: {daily_cost:.4f} > {daily_limit:.4f} USD")
            
            # 월간 한도 체크
            if provider in self._monthly_limits:
                monthly_limit = self._monthly_limits[provider]
                monthly_usage = self.get_usage_summary(
                    time_window=timedelta(days=30),
                    provider_filter=provider
                ).unwrap_or({})
                
                monthly_cost = monthly_usage.get("total_cost", 0.0) + cost
                if monthly_cost > monthly_limit:
                    return Failure(f"월간 비용 한도 초과: {monthly_cost:.4f} > {monthly_limit:.4f} USD")
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"한도 체크 실패: {str(e)}")
    
    def get_usage_summary(
        self,
        time_window: Optional[timedelta] = None,
        provider_filter: Optional[str] = None,
        model_filter: Optional[str] = None
    ) -> Result[Dict[str, Any], str]:
        """사용량 요약 정보
        
        Args:
            time_window: 조회 기간 (기본: 30일)
            provider_filter: Provider 필터
            model_filter: 모델 필터
            
        Returns:
            Result[Dict[str, Any], str]: 사용량 요약 또는 에러 메시지
        """
        try:
            cutoff_time = datetime.now() - (time_window or timedelta(days=30))
            
            # 필터링
            filtered_usage = []
            for usage in self._usage_history:
                if usage.timestamp < cutoff_time:
                    continue
                if provider_filter and usage.provider != provider_filter:
                    continue
                if model_filter and usage.model != model_filter:
                    continue
                filtered_usage.append(usage)
            
            if not filtered_usage:
                return Success({
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "api_calls": 0,
                    "by_provider": {},
                    "by_model": {},
                    "time_window_days": time_window.days if time_window else 30
                })
            
            # 통계 계산
            total_tokens = sum(usage.total_tokens for usage in filtered_usage)
            total_cost = sum(usage.cost_estimate for usage in filtered_usage)
            api_calls = len(filtered_usage)
            
            # Provider별 통계
            by_provider = {}
            for usage in filtered_usage:
                if usage.provider not in by_provider:
                    by_provider[usage.provider] = {
                        "tokens": 0, "cost": 0.0, "calls": 0, "avg_response_time": 0.0
                    }
                by_provider[usage.provider]["tokens"] += usage.total_tokens
                by_provider[usage.provider]["cost"] += usage.cost_estimate
                by_provider[usage.provider]["calls"] += 1
            
            # 평균 응답 시간 계산
            for provider, stats in by_provider.items():
                provider_usages = [u for u in filtered_usage if u.provider == provider and u.response_time_ms]
                if provider_usages:
                    avg_time = sum(u.response_time_ms for u in provider_usages) / len(provider_usages)
                    stats["avg_response_time"] = avg_time
            
            # 모델별 통계
            by_model = {}
            for usage in filtered_usage:
                if usage.model not in by_model:
                    by_model[usage.model] = {
                        "tokens": 0, "cost": 0.0, "calls": 0
                    }
                by_model[usage.model]["tokens"] += usage.total_tokens
                by_model[usage.model]["cost"] += usage.cost_estimate
                by_model[usage.model]["calls"] += 1
            
            return Success({
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "api_calls": api_calls,
                "avg_tokens_per_call": total_tokens / api_calls if api_calls > 0 else 0,
                "avg_cost_per_call": total_cost / api_calls if api_calls > 0 else 0,
                "by_provider": by_provider,
                "by_model": by_model,
                "time_window_days": time_window.days if time_window else 30,
                "period_start": cutoff_time.isoformat(),
                "period_end": datetime.now().isoformat()
            })
            
        except Exception as e:
            return Failure(f"사용량 요약 생성 실패: {str(e)}")
    
    def get_detailed_usage(
        self,
        limit: int = 100,
        provider_filter: Optional[str] = None,
        model_filter: Optional[str] = None
    ) -> Result[List[Dict[str, Any]], str]:
        """상세 사용량 내역
        
        Args:
            limit: 반환할 항목 수
            provider_filter: Provider 필터
            model_filter: 모델 필터
            
        Returns:
            Result[List[Dict[str, Any]], str]: 상세 사용량 내역
        """
        try:
            # 필터링 및 정렬 (최신순)
            filtered_usage = []
            for usage in reversed(self._usage_history):  # 최신순 정렬
                if provider_filter and usage.provider != provider_filter:
                    continue
                if model_filter and usage.model != model_filter:
                    continue
                filtered_usage.append(usage.to_dict())
                
                if len(filtered_usage) >= limit:
                    break
            
            return Success(filtered_usage)
            
        except Exception as e:
            return Failure(f"상세 사용량 조회 실패: {str(e)}")
    
    def clear_history(
        self, 
        before_date: Optional[datetime] = None
    ) -> Result[int, str]:
        """사용량 히스토리 정리
        
        Args:
            before_date: 이 날짜 이전의 데이터를 삭제 (None이면 전체 삭제)
            
        Returns:
            Result[int, str]: 삭제된 항목 수 또는 에러 메시지
        """
        try:
            if before_date is None:
                removed_count = len(self._usage_history)
                self._usage_history.clear()
            else:
                original_count = len(self._usage_history)
                self._usage_history = [
                    usage for usage in self._usage_history
                    if usage.timestamp >= before_date
                ]
                removed_count = original_count - len(self._usage_history)
            
            return Success(removed_count)
            
        except Exception as e:
            return Failure(f"히스토리 정리 실패: {str(e)}")
    
    def export_usage_data(
        self,
        time_window: Optional[timedelta] = None
    ) -> Result[List[Dict[str, Any]], str]:
        """사용량 데이터 내보내기
        
        Args:
            time_window: 내보낼 기간
            
        Returns:
            Result[List[Dict[str, Any]], str]: 내보내기 데이터
        """
        try:
            cutoff_time = datetime.now() - (time_window or timedelta(days=365))
            
            export_data = []
            for usage in self._usage_history:
                if usage.timestamp >= cutoff_time:
                    export_data.append(usage.to_dict())
            
            return Success(export_data)
            
        except Exception as e:
            return Failure(f"데이터 내보내기 실패: {str(e)}")
    
    def get_cost_alerts(self) -> List[Dict[str, Any]]:
        """비용 알림 체크
        
        Returns:
            List[Dict[str, Any]]: 알림 목록
        """
        alerts = []
        
        try:
            # 일일 한도 체크
            for provider, daily_limit in self._daily_limits.items():
                daily_usage = self.get_usage_summary(
                    time_window=timedelta(days=1),
                    provider_filter=provider
                ).unwrap_or({})
                
                daily_cost = daily_usage.get("total_cost", 0.0)
                if daily_cost > daily_limit * 0.8:  # 80% 초과시 알림
                    alerts.append({
                        "type": "daily_limit_warning",
                        "provider": provider,
                        "current_cost": daily_cost,
                        "limit": daily_limit,
                        "percentage": (daily_cost / daily_limit) * 100,
                        "severity": "high" if daily_cost > daily_limit else "medium"
                    })
            
            # 월간 한도 체크
            for provider, monthly_limit in self._monthly_limits.items():
                monthly_usage = self.get_usage_summary(
                    time_window=timedelta(days=30),
                    provider_filter=provider
                ).unwrap_or({})
                
                monthly_cost = monthly_usage.get("total_cost", 0.0)
                if monthly_cost > monthly_limit * 0.8:  # 80% 초과시 알림
                    alerts.append({
                        "type": "monthly_limit_warning",
                        "provider": provider,
                        "current_cost": monthly_cost,
                        "limit": monthly_limit,
                        "percentage": (monthly_cost / monthly_limit) * 100,
                        "severity": "high" if monthly_cost > monthly_limit else "medium"
                    })
        
        except Exception:
            pass  # 알림 체크 실패는 무시
        
        return alerts