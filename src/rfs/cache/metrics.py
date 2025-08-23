"""
RFS Cache Metrics (RFS v4.1)

캐시 메트릭스 수집 및 분석
"""

import asyncio
import functools
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

from ..core.result import Result, Success, Failure
from ..core.singleton import SingletonMeta
from ..core.enhanced_logging import get_logger
from .base import get_cache_manager, CacheBackend

logger = get_logger(__name__)


@dataclass
class CacheMetrics:
    """캐시 메트릭스"""
    # 기본 통계
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    
    # 성능 메트릭스
    avg_get_time: float = 0.0
    avg_set_time: float = 0.0
    max_get_time: float = 0.0
    max_set_time: float = 0.0
    
    # 시간별 통계
    hourly_hits: Dict[str, int] = field(default_factory=dict)
    hourly_misses: Dict[str, int] = field(default_factory=dict)
    
    # 키 패턴 분석
    key_patterns: Dict[str, int] = field(default_factory=dict)
    hot_keys: List[str] = field(default_factory=list)
    
    # 메모리 사용량 (메모리 캐시용)
    memory_usage: int = 0
    memory_limit: int = 0
    
    # 커넥션 정보 (Redis용)
    connections_active: int = 0
    connections_idle: int = 0
    
    @property
    def total_operations(self) -> int:
        """총 작업 수"""
        return self.hits + self.misses + self.sets + self.deletes
    
    @property
    def hit_rate(self) -> float:
        """히트율"""
        total_reads = self.hits + self.misses
        return (self.hits / total_reads) if total_reads > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """미스율"""
        return 1.0 - self.hit_rate
    
    @property
    def error_rate(self) -> float:
        """에러율"""
        return (self.errors / self.total_operations) if self.total_operations > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "total_operations": self.total_operations,
            "hit_rate": round(self.hit_rate, 4),
            "miss_rate": round(self.miss_rate, 4),
            "error_rate": round(self.error_rate, 4),
            "avg_get_time": round(self.avg_get_time, 4),
            "avg_set_time": round(self.avg_set_time, 4),
            "max_get_time": round(self.max_get_time, 4),
            "max_set_time": round(self.max_set_time, 4),
            "memory_usage": self.memory_usage,
            "memory_limit": self.memory_limit,
            "connections_active": self.connections_active,
            "connections_idle": self.connections_idle,
            "hourly_stats": {
                "hits": self.hourly_hits,
                "misses": self.hourly_misses
            },
            "key_analysis": {
                "patterns": self.key_patterns,
                "hot_keys": self.hot_keys[:10]  # 상위 10개만
            }
        }


class MetricsCollector(metaclass=SingletonMeta):
    """메트릭스 수집기"""
    
    def __init__(self):
        self.collectors: Dict[str, Callable] = {}
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1440))  # 24시간 분 단위
        self.key_access_count: Dict[str, int] = defaultdict(int)
        self.operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 수집 태스크
        self._collection_task: Optional[asyncio.Task] = None
        self._collection_interval = 60  # 1분
        
        # 알림 설정
        self.alert_thresholds = {
            "hit_rate_min": 0.8,      # 히트율 최소값
            "error_rate_max": 0.01,   # 에러율 최대값
            "response_time_max": 1.0  # 응답시간 최대값 (초)
        }
        self.alert_callbacks: List[Callable] = []
    
    def start_collection(self, interval: int = 60):
        """메트릭스 수집 시작"""
        self._collection_interval = interval
        
        if not self._collection_task or self._collection_task.done():
            self._collection_task = asyncio.create_task(self._collection_loop())
            logger.info(f"메트릭스 수집 시작: {interval}초 간격")
    
    def stop_collection(self):
        """메트릭스 수집 중지"""
        if self._collection_task and not self._collection_task.done():
            self._collection_task.cancel()
            logger.info("메트릭스 수집 중지")
    
    async def _collection_loop(self):
        """메트릭스 수집 루프"""
        while True:
            try:
                await asyncio.sleep(self._collection_interval)
                await self.collect_all_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"메트릭스 수집 오류: {e}")
    
    async def collect_all_metrics(self):
        """모든 캐시의 메트릭스 수집"""
        try:
            cache_manager = get_cache_manager()
            current_time = datetime.now()
            
            for cache_name, cache_backend in cache_manager.caches.items():
                metrics = await self.collect_cache_metrics(cache_name, cache_backend)
                
                # 히스토리에 저장
                time_key = current_time.strftime("%Y-%m-%d %H:%M")
                self.metrics_history[cache_name].append({
                    "timestamp": time_key,
                    "metrics": metrics.to_dict()
                })
                
                # 알림 확인
                await self._check_alerts(cache_name, metrics)
            
        except Exception as e:
            logger.error(f"전체 메트릭스 수집 실패: {e}")
    
    async def collect_cache_metrics(self, cache_name: str, cache_backend: CacheBackend) -> CacheMetrics:
        """개별 캐시 메트릭스 수집"""
        try:
            # 기본 통계
            stats = cache_backend.get_stats()
            metrics = CacheMetrics(
                hits=stats.get("hits", 0),
                misses=stats.get("misses", 0),
                sets=stats.get("sets", 0),
                deletes=stats.get("deletes", 0),
                errors=stats.get("errors", 0)
            )
            
            # 성능 메트릭스 계산
            operation_times = self.operation_times.get(cache_name, deque())
            if operation_times:
                get_times = [t for t in operation_times if t.get('operation') == 'get']
                set_times = [t for t in operation_times if t.get('operation') == 'set']
                
                if get_times:
                    get_durations = [t['duration'] for t in get_times]
                    metrics.avg_get_time = sum(get_durations) / len(get_durations)
                    metrics.max_get_time = max(get_durations)
                
                if set_times:
                    set_durations = [t['duration'] for t in set_times]
                    metrics.avg_set_time = sum(set_durations) / len(set_durations)
                    metrics.max_set_time = max(set_durations)
            
            # 시간별 통계
            current_hour = datetime.now().strftime("%H")
            metrics.hourly_hits[current_hour] = stats.get("hits", 0)
            metrics.hourly_misses[current_hour] = stats.get("misses", 0)
            
            # Hot keys 분석
            metrics.hot_keys = self._get_hot_keys(cache_name)
            
            # 메모리 사용량 (메모리 캐시용)
            if hasattr(cache_backend, '_current_memory'):
                metrics.memory_usage = cache_backend._current_memory
                metrics.memory_limit = cache_backend.config.max_memory
            
            # Redis 연결 정보
            if hasattr(cache_backend, 'redis') and cache_backend.redis:
                try:
                    info = await cache_backend.redis.info()
                    metrics.connections_active = info.get('connected_clients', 0)
                except:
                    pass
            
            return metrics
            
        except Exception as e:
            logger.error(f"캐시 메트릭스 수집 실패 ({cache_name}): {e}")
            return CacheMetrics()
    
    def record_operation(self, cache_name: str, operation: str, key: str, duration: float):
        """작업 기록"""
        # 키 접근 횟수 기록
        self.key_access_count[f"{cache_name}:{key}"] += 1
        
        # 작업 시간 기록
        self.operation_times[cache_name].append({
            "operation": operation,
            "key": key,
            "duration": duration,
            "timestamp": time.time()
        })
    
    def _get_hot_keys(self, cache_name: str, limit: int = 10) -> List[str]:
        """Hot keys 추출"""
        cache_keys = {k: v for k, v in self.key_access_count.items() 
                     if k.startswith(f"{cache_name}:")}
        
        sorted_keys = sorted(cache_keys.items(), key=lambda x: x[1], reverse=True)
        return [k.split(":", 1)[1] for k, _ in sorted_keys[:limit]]
    
    async def _check_alerts(self, cache_name: str, metrics: CacheMetrics):
        """알림 확인"""
        alerts = []
        
        # 히트율 확인
        if metrics.hit_rate < self.alert_thresholds["hit_rate_min"]:
            alerts.append({
                "type": "low_hit_rate",
                "cache": cache_name,
                "value": metrics.hit_rate,
                "threshold": self.alert_thresholds["hit_rate_min"],
                "message": f"캐시 히트율이 낮습니다: {metrics.hit_rate:.2%}"
            })
        
        # 에러율 확인
        if metrics.error_rate > self.alert_thresholds["error_rate_max"]:
            alerts.append({
                "type": "high_error_rate",
                "cache": cache_name,
                "value": metrics.error_rate,
                "threshold": self.alert_thresholds["error_rate_max"],
                "message": f"캐시 에러율이 높습니다: {metrics.error_rate:.2%}"
            })
        
        # 응답시간 확인
        max_response_time = max(metrics.avg_get_time, metrics.avg_set_time)
        if max_response_time > self.alert_thresholds["response_time_max"]:
            alerts.append({
                "type": "high_response_time",
                "cache": cache_name,
                "value": max_response_time,
                "threshold": self.alert_thresholds["response_time_max"],
                "message": f"캐시 응답시간이 느립니다: {max_response_time:.3f}s"
            })
        
        # 알림 콜백 실행
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
                except Exception as e:
                    logger.error(f"알림 콜백 실행 실패: {e}")
    
    def add_alert_callback(self, callback: Callable):
        """알림 콜백 추가"""
        self.alert_callbacks.append(callback)
    
    def set_alert_threshold(self, metric: str, threshold: float):
        """알림 임계값 설정"""
        self.alert_thresholds[metric] = threshold
    
    def get_metrics_history(self, cache_name: str, hours: int = 24) -> List[Dict]:
        """메트릭스 히스토리 조회"""
        history = self.metrics_history.get(cache_name, deque())
        
        # 시간 필터링
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_history = []
        
        for entry in history:
            entry_time = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M")
            if entry_time >= cutoff_time:
                filtered_history.append(entry)
        
        return filtered_history
    
    def generate_report(self, cache_name: str = None) -> Dict[str, Any]:
        """메트릭스 보고서 생성"""
        try:
            cache_manager = get_cache_manager()
            
            if cache_name:
                # 특정 캐시 보고서
                cache_backend = cache_manager.get_cache(cache_name)
                if not cache_backend:
                    return {"error": f"캐시를 찾을 수 없습니다: {cache_name}"}
                
                metrics = asyncio.run(self.collect_cache_metrics(cache_name, cache_backend))
                return {
                    "cache_name": cache_name,
                    "metrics": metrics.to_dict(),
                    "history": self.get_metrics_history(cache_name, 1)[-10:],  # 최근 10분
                    "hot_keys": metrics.hot_keys
                }
            else:
                # 전체 캐시 보고서
                report = {
                    "summary": {},
                    "caches": {},
                    "alerts": []
                }
                
                total_metrics = CacheMetrics()
                
                for name, cache_backend in cache_manager.caches.items():
                    metrics = asyncio.run(self.collect_cache_metrics(name, cache_backend))
                    report["caches"][name] = metrics.to_dict()
                    
                    # 전체 합계
                    total_metrics.hits += metrics.hits
                    total_metrics.misses += metrics.misses
                    total_metrics.sets += metrics.sets
                    total_metrics.deletes += metrics.deletes
                    total_metrics.errors += metrics.errors
                
                report["summary"] = total_metrics.to_dict()
                return report
                
        except Exception as e:
            logger.error(f"보고서 생성 실패: {e}")
            return {"error": str(e)}


# 전역 메트릭스 수집기
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """메트릭스 수집기 인스턴스 반환"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_cache_metrics(cache_name: str = None) -> Result[Dict[str, Any], str]:
    """캐시 메트릭스 조회"""
    try:
        collector = get_metrics_collector()
        report = collector.generate_report(cache_name)
        
        if "error" in report:
            return Failure(report["error"])
        
        return Success(report)
        
    except Exception as e:
        return Failure(f"메트릭스 조회 실패: {str(e)}")


def reset_cache_metrics(cache_name: str = None) -> Result[None, str]:
    """캐시 메트릭스 초기화"""
    try:
        cache_manager = get_cache_manager()
        
        if cache_name:
            cache_backend = cache_manager.get_cache(cache_name)
            if cache_backend:
                cache_backend.reset_stats()
        else:
            for cache_backend in cache_manager.caches.values():
                cache_backend.reset_stats()
        
        # 수집기 데이터도 초기화
        collector = get_metrics_collector()
        if cache_name:
            collector.metrics_history.pop(cache_name, None)
            collector.operation_times.pop(cache_name, None)
            
            # 키 접근 카운트 초기화
            keys_to_remove = [k for k in collector.key_access_count.keys() 
                            if k.startswith(f"{cache_name}:")]
            for key in keys_to_remove:
                del collector.key_access_count[key]
        else:
            collector.metrics_history.clear()
            collector.operation_times.clear()
            collector.key_access_count.clear()
        
        return Success(None)
        
    except Exception as e:
        return Failure(f"메트릭스 초기화 실패: {str(e)}")


# 메트릭스 데코레이터
def track_cache_operation(cache_name: str = None):
    """캐시 작업 추적 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            operation = func.__name__
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # 메트릭스 기록
                if len(args) >= 2:  # self, key
                    key = str(args[1])
                    collector = get_metrics_collector()
                    collector.record_operation(cache_name or "default", operation, key, duration)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"캐시 작업 실패 ({operation}): {e}")
                raise
        
        return wrapper
    
    return decorator