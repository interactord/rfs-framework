"""
AsyncPipeline 성능 최적화 도구

병렬 처리, 백프레셔, 배치 처리, 캐싱 등 비동기 파이프라인의 성능을 최적화하는 도구들.
대규모 데이터 처리와 높은 동시성 환경에서 안정적인 성능을 제공합니다.
"""

import asyncio
import time
import logging
from collections import defaultdict, deque
from typing import Any, AsyncIterable, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import weakref

from .async_result import AsyncResult
from ..core.result import Success, Failure

logger = logging.getLogger(__name__)

T = TypeVar('T')
U = TypeVar('U')
E = TypeVar('E')


@dataclass
class PerformanceMetrics:
    """성능 메트릭 데이터"""
    operation_name: str
    execution_count: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    error_count: int = 0
    success_rate: float = 1.0
    avg_duration: float = 0.0
    last_executed: float = field(default_factory=time.time)
    
    def update(self, duration: float, success: bool):
        """메트릭 업데이트"""
        self.execution_count += 1
        self.total_duration += duration
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
        self.avg_duration = self.total_duration / self.execution_count
        self.last_executed = time.time()
        
        if not success:
            self.error_count += 1
        
        self.success_rate = (self.execution_count - self.error_count) / self.execution_count


class AsyncPerformanceMonitor:
    """
    비동기 성능 모니터링 시스템
    
    함수 실행 시간, 성공률, 처리량 등의 성능 지표를 추적합니다.
    """
    
    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def measure(self, operation_name: str):
        """성능 측정 컨텍스트 매니저"""
        start_time = time.time()
        success = False
        
        try:
            yield
            success = True
        finally:
            duration = time.time() - start_time
            await self._record_metric(operation_name, duration, success)
    
    async def _record_metric(self, operation_name: str, duration: float, success: bool):
        """메트릭 기록"""
        async with self._lock:
            if operation_name not in self.metrics:
                self.metrics[operation_name] = PerformanceMetrics(operation_name)
            
            self.metrics[operation_name].update(duration, success)
    
    async def get_metrics(self, operation_name: str | None = None) -> Dict[str, Any]:
        """메트릭 조회"""
        async with self._lock:
            if operation_name:
                if operation_name in self.metrics:
                    metric = self.metrics[operation_name]
                    return {
                        'operation_name': metric.operation_name,
                        'execution_count': metric.execution_count,
                        'avg_duration': metric.avg_duration,
                        'min_duration': metric.min_duration,
                        'max_duration': metric.max_duration,
                        'success_rate': metric.success_rate,
                        'error_count': metric.error_count,
                        'last_executed': metric.last_executed
                    }
                else:
                    return {}
            else:
                return {
                    name: {
                        'execution_count': metric.execution_count,
                        'avg_duration': metric.avg_duration,
                        'success_rate': metric.success_rate,
                        'error_count': metric.error_count
                    }
                    for name, metric in self.metrics.items()
                }


# 전역 성능 모니터는 get_global_monitor()를 통해 접근


async def parallel_map(
    func: Callable[[T], Awaitable[U]], 
    items: List[T], 
    max_concurrency: int = 10,
    batch_size: Optional[int] = None,
    preserve_order: bool = True
) -> List[AsyncResult[U, Exception]]:
    """
    병렬 매핑 (동시성 제한)
    
    대량의 데이터를 효율적으로 병렬 처리하면서 시스템 리소스를 보호합니다.
    
    Args:
        func: 각 항목에 적용할 비동기 함수
        items: 처리할 항목들
        max_concurrency: 최대 동시 실행 수
        batch_size: 배치 처리 크기 (None이면 단일 배치)
        preserve_order: 결과 순서 보존 여부
        
    Returns:
        List[AsyncResult[U, Exception]]: 처리 결과들
        
    Example:
        >>> async def process_item(item):
        ...     await asyncio.sleep(0.1)
        ...     return item * 2
        >>> 
        >>> results = await parallel_map(
        ...     process_item, 
        ...     list(range(100)), 
        ...     max_concurrency=10
        ... )
    """
    if not items:
        return []
    
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded_func(item_with_index):
        if preserve_order:
            index, item = item_with_index
        else:
            item = item_with_index
        
        async with semaphore:
            async with get_global_monitor().measure(f"parallel_map_{func.__name__}"):
                try:
                    result = await func(item)
                    async_result = AsyncResult.from_value(result)
                    return (index, async_result) if preserve_order else async_result
                except Exception as e:
                    async_result = AsyncResult.from_error(e)
                    return (index, async_result) if preserve_order else async_result
    
    # 인덱스와 함께 처리 (순서 보존용)
    if preserve_order:
        indexed_items = [(i, item) for i, item in enumerate(items)]
    else:
        indexed_items = items
    
    if batch_size and len(items) > batch_size:
        # 배치 처리
        results = []
        for i in range(0, len(indexed_items), batch_size):
            batch = indexed_items[i:i + batch_size]
            batch_results = await asyncio.gather(*[bounded_func(item) for item in batch])
            results.extend(batch_results)
    else:
        # 단일 배치 처리
        results = await asyncio.gather(*[bounded_func(item) for item in indexed_items])
    
    # 순서 복원
    if preserve_order:
        results.sort(key=lambda x: x[0])  # 인덱스로 정렬
        return [result for _, result in results]
    else:
        return results


class AsyncBackpressureController:
    """
    백프레셔 제어 시스템
    
    생산자와 소비자 간의 처리 속도 차이를 조절하여 메모리 오버플로우를 방지합니다.
    """
    
    def __init__(
        self,
        buffer_size: int = 100,
        high_water_mark: float = 0.8,
        low_water_mark: float = 0.3,
        backpressure_delay: float = 0.01
    ):
        """
        Args:
            buffer_size: 버퍼 크기
            high_water_mark: 백프레셔 활성화 임계점 (비율)
            low_water_mark: 백프레셔 해제 임계점 (비율)
            backpressure_delay: 백프레셔 시 지연 시간
        """
        self.buffer_size = buffer_size
        self.high_water_mark = int(buffer_size * high_water_mark)
        self.low_water_mark = int(buffer_size * low_water_mark)
        self.backpressure_delay = backpressure_delay
        
        self.queue = asyncio.Queue(buffer_size)
        self.is_backpressure_active = False
        self._stats = {
            'items_processed': 0,
            'backpressure_events': 0,
            'avg_queue_size': 0.0
        }
    
    async def put(self, item: T) -> bool:
        """
        항목을 버퍼에 추가 (백프레셔 적용)
        
        Returns:
            bool: 성공적으로 추가되었는지 여부
        """
        current_size = self.queue.qsize()
        
        # 백프레셔 확인
        if current_size >= self.high_water_mark:
            if not self.is_backpressure_active:
                self.is_backpressure_active = True
                self._stats['backpressure_events'] += 1
                logger.warning(f"백프레셔 활성화 - 큐 크기: {current_size}")
            
            # 백프레셔 지연
            await asyncio.sleep(self.backpressure_delay)
            return False
        
        # 백프레셔 해제 확인
        if self.is_backpressure_active and current_size <= self.low_water_mark:
            self.is_backpressure_active = False
            logger.info(f"백프레셔 해제 - 큐 크기: {current_size}")
        
        try:
            self.queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            return False
    
    async def get(self) -> T:
        """버퍼에서 항목 가져오기"""
        item = await self.queue.get()
        self._stats['items_processed'] += 1
        self._update_avg_queue_size()
        return item
    
    def _update_avg_queue_size(self):
        """평균 큐 크기 업데이트"""
        current_size = self.queue.qsize()
        processed = self._stats['items_processed']
        if processed > 1:
            prev_avg = self._stats['avg_queue_size']
            self._stats['avg_queue_size'] = (prev_avg * (processed - 1) + current_size) / processed
        else:
            self._stats['avg_queue_size'] = current_size
    
    def get_stats(self) -> Dict[str, Any]:
        """백프레셔 통계 반환"""
        return {
            'buffer_size': self.buffer_size,
            'current_queue_size': self.queue.qsize(),
            'is_backpressure_active': self.is_backpressure_active,
            **self._stats
        }


class AsyncStreamProcessor:
    """
    비동기 스트림 처리기
    
    대용량 데이터 스트림을 효율적으로 처리하면서 백프레셔를 적용합니다.
    """
    
    def __init__(
        self,
        processor_func: Callable[[T], Awaitable[U]],
        buffer_size: int = 100,
        max_concurrency: int = 10,
        batch_processing: bool = False,
        batch_size: int = 10
    ):
        """
        Args:
            processor_func: 각 항목을 처리할 함수
            buffer_size: 내부 버퍼 크기
            max_concurrency: 최대 동시 처리 수
            batch_processing: 배치 처리 활성화 여부
            batch_size: 배치 크기
        """
        self.processor_func = processor_func
        self.max_concurrency = max_concurrency
        self.batch_processing = batch_processing
        self.batch_size = batch_size
        
        self.backpressure_controller = AsyncBackpressureController(buffer_size)
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.results_queue = asyncio.Queue()
        
        self._processing_tasks = set()
        self._is_stopped = False
    
    async def process_stream(
        self,
        producer: Callable[[], AsyncIterable[T]]
    ) -> AsyncResult[List[U], Exception]:
        """
        스트림 처리 (백프레셔 적용)
        
        Args:
            producer: 데이터를 생성하는 비동기 이터레이터 함수
            
        Returns:
            AsyncResult[List[U], Exception]: 처리된 결과들
        """
        try:
            # 생산자 태스크 시작
            producer_task = asyncio.create_task(self._produce_items(producer))
            
            # 소비자 태스크 시작
            consumer_task = asyncio.create_task(self._consume_items())
            
            # 결과 수집 태스크 시작
            collector_task = asyncio.create_task(self._collect_results())
            
            # 모든 태스크 완료 대기
            await producer_task
            await consumer_task
            results = await collector_task
            
            return AsyncResult.from_value(results)
            
        except Exception as e:
            self._is_stopped = True
            return AsyncResult.from_error(e)
        finally:
            # 정리 작업
            await self._cleanup()
    
    async def _produce_items(self, producer: Callable[[], AsyncIterable[T]]):
        """아이템 생성"""
        try:
            async for item in producer():
                while not await self.backpressure_controller.put(item):
                    # 백프레셔가 활성화된 경우 잠시 대기 후 재시도
                    await asyncio.sleep(0.01)
                    
                if self._is_stopped:
                    break
        finally:
            # 생산 완료 마커
            await self.backpressure_controller.put(None)
    
    async def _consume_items(self):
        """아이템 소비 및 처리"""
        while not self._is_stopped:
            try:
                item = await self.backpressure_controller.get()
                
                # 종료 마커 확인
                if item is None:
                    break
                
                if self.batch_processing:
                    # 배치 처리
                    await self._process_batch_item(item)
                else:
                    # 개별 처리
                    task = asyncio.create_task(self._process_single_item(item))
                    self._processing_tasks.add(task)
                    task.add_done_callback(self._processing_tasks.discard)
                
            except Exception as e:
                logger.error(f"아이템 처리 중 에러: {e}")
        
        # 모든 처리 태스크 완료 대기
        if self._processing_tasks:
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)
        
        # 결과 수집 완료 마커
        await self.results_queue.put(None)
    
    async def _process_single_item(self, item: T):
        """단일 아이템 처리"""
        async with self.semaphore:
            try:
                result = await self.processor_func(item)
                await self.results_queue.put(result)
            except Exception as e:
                await self.results_queue.put(e)
    
    async def _process_batch_item(self, item: T):
        """배치 아이템 수집 (실제 배치 처리는 별도 구현 필요)"""
        # 단순히 개별 처리로 폴백
        await self._process_single_item(item)
    
    async def _collect_results(self) -> List[U]:
        """결과 수집"""
        results = []
        
        while True:
            result = await self.results_queue.get()
            
            # 종료 마커 확인
            if result is None:
                break
            
            # 에러가 아닌 경우만 결과에 추가
            if not isinstance(result, Exception):
                results.append(result)
        
        return results
    
    async def _cleanup(self):
        """정리 작업"""
        self._is_stopped = True
        
        # 남은 태스크들 정리
        if self._processing_tasks:
            for task in self._processing_tasks:
                task.cancel()
            
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)


class AsyncCache:
    """
    비동기 캐시 시스템
    
    TTL, LRU 방식을 지원하는 고성능 비동기 캐시입니다.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 3600.0,  # 1시간
        cleanup_interval: float = 300.0  # 5분
    ):
        """
        Args:
            max_size: 최대 캐시 크기
            default_ttl: 기본 TTL (초)
            cleanup_interval: 정리 작업 간격 (초)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order = deque()  # LRU용
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0
        }
        
        # 백그라운드 정리 태스크 시작
        self._start_cleanup_task()
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        async with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[key]
            current_time = time.time()
            
            # TTL 확인
            if current_time > entry['expires_at']:
                del self._cache[key]
                self._remove_from_access_order(key)
                self._stats['misses'] += 1
                self._stats['expirations'] += 1
                return None
            
            # LRU 업데이트
            self._update_access_order(key)
            self._stats['hits'] += 1
            
            return entry['value']
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """캐시에 값 저장"""
        async with self._lock:
            expires_at = time.time() + (ttl or self.default_ttl)
            
            # 기존 키 업데이트
            if key in self._cache:
                self._cache[key] = {
                    'value': value,
                    'expires_at': expires_at,
                    'created_at': time.time()
                }
                self._update_access_order(key)
                return
            
            # 캐시 크기 확인 및 LRU 제거
            if len(self._cache) >= self.max_size:
                await self._evict_lru()
            
            # 새 항목 추가
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            self._access_order.append(key)
    
    async def delete(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._remove_from_access_order(key)
                return True
            return False
    
    async def clear(self) -> None:
        """캐시 전체 삭제"""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def _update_access_order(self, key: str):
        """LRU 접근 순서 업데이트"""
        # 기존 항목을 끝으로 이동
        try:
            self._access_order.remove(key)
        except ValueError:
            pass
        self._access_order.append(key)
    
    def _remove_from_access_order(self, key: str):
        """LRU 접근 순서에서 제거"""
        try:
            self._access_order.remove(key)
        except ValueError:
            pass
    
    async def _evict_lru(self):
        """LRU 항목 제거"""
        if self._access_order:
            lru_key = self._access_order.popleft()
            if lru_key in self._cache:
                del self._cache[lru_key]
                self._stats['evictions'] += 1
    
    def _start_cleanup_task(self):
        """정리 태스크 시작"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """주기적 정리 작업"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"캐시 정리 중 에러: {e}")
    
    async def _cleanup_expired(self):
        """만료된 항목 정리"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if current_time > entry['expires_at']
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self._remove_from_access_order(key)
                self._stats['expirations'] += 1
    
    async def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        async with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': hit_rate,
                **self._stats
            }
    
    def __del__(self):
        """소멸자 - 정리 태스크 정리"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()


# === 성능 최적화 데코레이터 ===

def async_cached(
    cache: Optional[AsyncCache] = None,
    ttl: Optional[float] = None,
    key_func: Optional[Callable[..., str]] = None
):
    """
    비동기 캐싱 데코레이터
    
    Args:
        cache: 사용할 캐시 인스턴스
        ttl: 캐시 TTL
        key_func: 캐시 키 생성 함수
    """
    if cache is None:
        cache = AsyncCache()
    
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # 캐시 확인
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 함수 실행
            result = await func(*args, **kwargs)
            
            # 캐시 저장
            await cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator


def async_rate_limited(calls_per_second: float):
    """
    비동기 레이트 제한 데코레이터
    
    Args:
        calls_per_second: 초당 호출 제한 수
    """
    interval = 1.0 / calls_per_second
    last_call_times = defaultdict(float)
    lock = asyncio.Lock()
    
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs):
            async with lock:
                current_time = time.time()
                key = id(func)  # 함수별로 구분
                
                elapsed = current_time - last_call_times[key]
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)
                
                last_call_times[key] = time.time()
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# === 전역 캐시 및 모니터 인스턴스 (Lazy initialization) ===
_global_cache: Optional[AsyncCache] = None

def get_global_cache() -> AsyncCache:
    """전역 AsyncCache 인스턴스를 반환합니다. 필요시 생성합니다."""
    global _global_cache
    if _global_cache is None:
        _global_cache = AsyncCache()
    return _global_cache

_global_monitor: Optional[AsyncPerformanceMonitor] = None

def get_global_monitor() -> AsyncPerformanceMonitor:
    """전역 AsyncPerformanceMonitor 인스턴스를 반환합니다. 필요시 생성합니다."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = AsyncPerformanceMonitor()
    return _global_monitor