"""
Distributed Cache Manager for RFS Framework

분산 캐시 관리 시스템:
- 멀티 레벨 캐싱 (L1: 로컬, L2: 분산)
- Redis, Memcached 지원
- 캐시 무효화 전략
- 캐시 워밍 및 프리페칭
- 캐시 통계 및 모니터링
"""

import asyncio
import hashlib
import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
import statistics

from ..core import Result, Success, Failure


class CacheBackend(Enum):
    """캐시 백엔드"""
    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"
    HYBRID = "hybrid"  # Memory + Redis/Memcached


class EvictionPolicy(Enum):
    """캐시 제거 정책"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live based
    RANDOM = "random"


class CacheStrategy(Enum):
    """캐싱 전략"""
    CACHE_ASIDE = "cache_aside"  # Lazy loading
    READ_THROUGH = "read_through"  # 캐시가 데이터 로드 책임
    WRITE_THROUGH = "write_through"  # 캐시와 DB 동시 쓰기
    WRITE_BEHIND = "write_behind"  # 캐시 먼저, DB는 비동기
    REFRESH_AHEAD = "refresh_ahead"  # 만료 전 미리 갱신


class InvalidationStrategy(Enum):
    """캐시 무효화 전략"""
    TTL_BASED = "ttl_based"  # 시간 기반
    EVENT_BASED = "event_based"  # 이벤트 기반
    VERSION_BASED = "version_based"  # 버전 기반
    TAG_BASED = "tag_based"  # 태그 기반


@dataclass
class CacheConfig:
    """캐시 설정"""
    backend: CacheBackend
    eviction_policy: EvictionPolicy
    max_size: int  # 최대 항목 수
    max_memory_mb: int  # 최대 메모리 사용량 (MB)
    default_ttl: int  # 기본 TTL (초)
    enable_compression: bool = False
    compression_threshold: int = 1024  # bytes
    enable_statistics: bool = True
    connection_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    key: str
    value: Any
    ttl: int
    created_at: float
    accessed_at: float
    access_count: int = 0
    size_bytes: int = 0
    tags: Set[str] = field(default_factory=set)
    version: int = 1
    compressed: bool = False


@dataclass
class CacheStatistics:
    """캐시 통계"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired: int = 0
    total_requests: int = 0
    total_size_bytes: int = 0
    average_hit_time_ms: float = 0.0
    average_miss_time_ms: float = 0.0
    hit_ratio: float = 0.0
    
    def update_hit_ratio(self):
        """히트율 업데이트"""
        if self.total_requests > 0:
            self.hit_ratio = self.hits / self.total_requests * 100


@dataclass
class CachePartition:
    """캐시 파티션"""
    id: str
    name: str
    config: CacheConfig
    entries: Dict[str, CacheEntry] = field(default_factory=dict)
    statistics: CacheStatistics = field(default_factory=CacheStatistics)
    access_order: OrderedDict = field(default_factory=OrderedDict)  # LRU
    frequency_count: Dict[str, int] = field(default_factory=dict)  # LFU


class LocalCache:
    """로컬 인메모리 캐시 (L1)"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.entries: Dict[str, CacheEntry] = {}
        self.access_order = OrderedDict()  # LRU tracking
        self.frequency_count: Dict[str, int] = {}  # LFU tracking
        self.statistics = CacheStatistics()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시 조회"""
        async with self._lock:
            start_time = time.time()
            
            if key in self.entries:
                entry = self.entries[key]
                
                # TTL 확인
                if self._is_expired(entry):
                    await self._remove_entry(key)
                    self.statistics.misses += 1
                    self.statistics.expired += 1
                    return None
                
                # 접근 정보 업데이트
                entry.accessed_at = time.time()
                entry.access_count += 1
                
                # 정책별 추적 업데이트
                if self.config.eviction_policy == EvictionPolicy.LRU:
                    self.access_order.move_to_end(key)
                elif self.config.eviction_policy == EvictionPolicy.LFU:
                    self.frequency_count[key] = entry.access_count
                
                # 통계 업데이트
                self.statistics.hits += 1
                elapsed_ms = (time.time() - start_time) * 1000
                self._update_hit_time(elapsed_ms)
                
                # 압축 해제
                value = entry.value
                if entry.compressed:
                    value = self._decompress(value)
                
                return value
            
            self.statistics.misses += 1
            elapsed_ms = (time.time() - start_time) * 1000
            self._update_miss_time(elapsed_ms)
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        tags: Set[str] = None
    ) -> bool:
        """캐시 저장"""
        async with self._lock:
            # 크기 확인 및 제거
            if len(self.entries) >= self.config.max_size:
                await self._evict()
            
            # 값 압축
            compressed = False
            size_bytes = len(pickle.dumps(value))
            
            if self.config.enable_compression and size_bytes > self.config.compression_threshold:
                value = self._compress(value)
                compressed = True
                size_bytes = len(value)
            
            # 엔트리 생성
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl or self.config.default_ttl,
                created_at=time.time(),
                accessed_at=time.time(),
                size_bytes=size_bytes,
                tags=tags or set(),
                compressed=compressed
            )
            
            self.entries[key] = entry
            
            # 정책별 추적 업데이트
            if self.config.eviction_policy == EvictionPolicy.LRU:
                self.access_order[key] = True
            elif self.config.eviction_policy == EvictionPolicy.LFU:
                self.frequency_count[key] = 1
            
            # 통계 업데이트
            self.statistics.total_size_bytes += size_bytes
            
            return True
    
    async def delete(self, key: str) -> bool:
        """캐시 삭제"""
        async with self._lock:
            if key in self.entries:
                await self._remove_entry(key)
                return True
            return False
    
    async def clear(self) -> int:
        """전체 캐시 클리어"""
        async with self._lock:
            count = len(self.entries)
            self.entries.clear()
            self.access_order.clear()
            self.frequency_count.clear()
            self.statistics.total_size_bytes = 0
            return count
    
    async def invalidate_by_tags(self, tags: Set[str]) -> int:
        """태그 기반 무효화"""
        async with self._lock:
            keys_to_remove = []
            
            for key, entry in self.entries.items():
                if entry.tags & tags:  # 교집합이 있으면
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                await self._remove_entry(key)
            
            return len(keys_to_remove)
    
    def get_statistics(self) -> CacheStatistics:
        """통계 반환"""
        self.statistics.total_requests = self.statistics.hits + self.statistics.misses
        self.statistics.update_hit_ratio()
        return self.statistics
    
    async def _evict(self):
        """캐시 제거"""
        if not self.entries:
            return
        
        key_to_remove = None
        
        if self.config.eviction_policy == EvictionPolicy.LRU:
            # 가장 오래 사용하지 않은 항목 제거
            key_to_remove = next(iter(self.access_order))
            
        elif self.config.eviction_policy == EvictionPolicy.LFU:
            # 가장 적게 사용된 항목 제거
            if self.frequency_count:
                key_to_remove = min(self.frequency_count, key=self.frequency_count.get)
                
        elif self.config.eviction_policy == EvictionPolicy.FIFO:
            # 가장 오래된 항목 제거
            oldest_key = None
            oldest_time = float('inf')
            
            for key, entry in self.entries.items():
                if entry.created_at < oldest_time:
                    oldest_time = entry.created_at
                    oldest_key = key
            
            key_to_remove = oldest_key
            
        elif self.config.eviction_policy == EvictionPolicy.RANDOM:
            # 무작위 제거
            import random
            key_to_remove = random.choice(list(self.entries.keys()))
        
        if key_to_remove:
            await self._remove_entry(key_to_remove)
            self.statistics.evictions += 1
    
    async def _remove_entry(self, key: str):
        """엔트리 제거"""
        if key in self.entries:
            entry = self.entries[key]
            self.statistics.total_size_bytes -= entry.size_bytes
            del self.entries[key]
            
            if key in self.access_order:
                del self.access_order[key]
            
            if key in self.frequency_count:
                del self.frequency_count[key]
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """만료 확인"""
        return (time.time() - entry.created_at) > entry.ttl
    
    def _compress(self, value: Any) -> bytes:
        """압축"""
        import zlib
        return zlib.compress(pickle.dumps(value))
    
    def _decompress(self, data: bytes) -> Any:
        """압축 해제"""
        import zlib
        return pickle.loads(zlib.decompress(data))
    
    def _update_hit_time(self, elapsed_ms: float):
        """히트 시간 업데이트"""
        if self.statistics.hits == 1:
            self.statistics.average_hit_time_ms = elapsed_ms
        else:
            # 이동 평균
            self.statistics.average_hit_time_ms = (
                (self.statistics.average_hit_time_ms * (self.statistics.hits - 1) + elapsed_ms) /
                self.statistics.hits
            )
    
    def _update_miss_time(self, elapsed_ms: float):
        """미스 시간 업데이트"""
        if self.statistics.misses == 1:
            self.statistics.average_miss_time_ms = elapsed_ms
        else:
            # 이동 평균
            self.statistics.average_miss_time_ms = (
                (self.statistics.average_miss_time_ms * (self.statistics.misses - 1) + elapsed_ms) /
                self.statistics.misses
            )


class DistributedCacheManager:
    """분산 캐시 관리자"""
    
    def __init__(self, default_config: CacheConfig = None):
        self.default_config = default_config or CacheConfig(
            backend=CacheBackend.MEMORY,
            eviction_policy=EvictionPolicy.LRU,
            max_size=10000,
            max_memory_mb=100,
            default_ttl=3600
        )
        
        # 캐시 파티션 (네임스페이스)
        self.partitions: Dict[str, CachePartition] = {}
        
        # L1 캐시 (로컬)
        self.l1_cache = LocalCache(self.default_config)
        
        # L2 캐시 (분산) - Redis/Memcached 연결
        self.l2_cache: Optional[Any] = None
        
        # 캐시 워머
        self.warmup_tasks: Dict[str, Callable] = {}
        
        # 프리페처
        self.prefetch_patterns: Dict[str, Dict[str, Any]] = {}
        
        # 통계
        self.global_statistics = CacheStatistics()
        
        # 무효화 리스너
        self.invalidation_listeners: List[Callable] = []
        
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
    
    async def start(self) -> Result[bool, str]:
        """캐시 관리자 시작"""
        try:
            self._running = True
            
            # L2 캐시 연결 (Redis/Memcached)
            if self.default_config.backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
                await self._connect_redis()
            elif self.default_config.backend == CacheBackend.MEMCACHED:
                await self._connect_memcached()
            
            # TTL 정리 작업 시작
            cleanup_task = asyncio.create_task(self._ttl_cleanup())
            self._tasks.add(cleanup_task)
            
            # 캐시 워밍 작업 시작
            warmup_task = asyncio.create_task(self._cache_warmer())
            self._tasks.add(warmup_task)
            
            # 통계 수집 작업 시작
            stats_task = asyncio.create_task(self._statistics_collector())
            self._tasks.add(stats_task)
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to start cache manager: {e}")
    
    async def stop(self) -> Result[bool, str]:
        """캐시 관리자 중지"""
        try:
            self._running = False
            
            # 실행 중인 작업 대기
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                self._tasks.clear()
            
            # L2 캐시 연결 종료
            if self.l2_cache:
                # Redis/Memcached 연결 종료
                pass
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to stop cache manager: {e}")
    
    def create_partition(
        self,
        partition_id: str,
        name: str,
        config: CacheConfig = None
    ) -> Result[CachePartition, str]:
        """캐시 파티션 생성"""
        try:
            if partition_id in self.partitions:
                return Failure(f"Partition {partition_id} already exists")
            
            partition = CachePartition(
                id=partition_id,
                name=name,
                config=config or self.default_config
            )
            
            self.partitions[partition_id] = partition
            return Success(partition)
            
        except Exception as e:
            return Failure(f"Failed to create partition: {e}")
    
    async def get(
        self,
        key: str,
        partition_id: str = None,
        loader: Callable = None
    ) -> Result[Any, str]:
        """캐시 조회 (L1 -> L2 -> Loader)"""
        try:
            # L1 캐시 확인
            value = await self.l1_cache.get(key)
            if value is not None:
                self.global_statistics.hits += 1
                return Success(value)
            
            # L2 캐시 확인 (있는 경우)
            if self.l2_cache:
                value = await self._get_from_l2(key)
                if value is not None:
                    # L1에 복사
                    await self.l1_cache.set(key, value)
                    self.global_statistics.hits += 1
                    return Success(value)
            
            # 파티션 캐시 확인
            if partition_id and partition_id in self.partitions:
                partition = self.partitions[partition_id]
                if key in partition.entries:
                    entry = partition.entries[key]
                    if not self._is_expired(entry):
                        self.global_statistics.hits += 1
                        return Success(entry.value)
            
            # 캐시 미스
            self.global_statistics.misses += 1
            
            # Loader 사용 (Read-Through)
            if loader:
                value = await loader(key)
                if value is not None:
                    await self.set(key, value, partition_id=partition_id)
                    return Success(value)
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"Failed to get from cache: {e}")
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        partition_id: str = None,
        tags: Set[str] = None,
        write_through: bool = False,
        writer: Callable = None
    ) -> Result[bool, str]:
        """캐시 저장"""
        try:
            # L1 캐시 저장
            await self.l1_cache.set(key, value, ttl, tags)
            
            # L2 캐시 저장 (있는 경우)
            if self.l2_cache:
                await self._set_to_l2(key, value, ttl)
            
            # 파티션 캐시 저장
            if partition_id and partition_id in self.partitions:
                partition = self.partitions[partition_id]
                entry = CacheEntry(
                    key=key,
                    value=value,
                    ttl=ttl or partition.config.default_ttl,
                    created_at=time.time(),
                    accessed_at=time.time(),
                    tags=tags or set()
                )
                partition.entries[key] = entry
            
            # Write-Through (동기 쓰기)
            if write_through and writer:
                await writer(key, value)
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to set cache: {e}")
    
    async def delete(
        self,
        key: str,
        partition_id: str = None,
        cascade: bool = True
    ) -> Result[bool, str]:
        """캐시 삭제"""
        try:
            deleted = False
            
            # L1 캐시 삭제
            if await self.l1_cache.delete(key):
                deleted = True
            
            # L2 캐시 삭제
            if cascade and self.l2_cache:
                await self._delete_from_l2(key)
                deleted = True
            
            # 파티션 캐시 삭제
            if partition_id and partition_id in self.partitions:
                partition = self.partitions[partition_id]
                if key in partition.entries:
                    del partition.entries[key]
                    deleted = True
            
            # 무효화 리스너 호출
            for listener in self.invalidation_listeners:
                await listener(key)
            
            return Success(deleted)
            
        except Exception as e:
            return Failure(f"Failed to delete from cache: {e}")
    
    async def invalidate_by_tags(
        self,
        tags: Set[str],
        partition_id: str = None
    ) -> Result[int, str]:
        """태그 기반 무효화"""
        try:
            total_invalidated = 0
            
            # L1 캐시 무효화
            total_invalidated += await self.l1_cache.invalidate_by_tags(tags)
            
            # 파티션 캐시 무효화
            if partition_id and partition_id in self.partitions:
                partition = self.partitions[partition_id]
                keys_to_remove = []
                
                for key, entry in partition.entries.items():
                    if entry.tags & tags:
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    del partition.entries[key]
                    total_invalidated += 1
            
            return Success(total_invalidated)
            
        except Exception as e:
            return Failure(f"Failed to invalidate by tags: {e}")
    
    async def clear(self, partition_id: str = None) -> Result[int, str]:
        """캐시 클리어"""
        try:
            total_cleared = 0
            
            if partition_id:
                # 특정 파티션만 클리어
                if partition_id in self.partitions:
                    partition = self.partitions[partition_id]
                    total_cleared = len(partition.entries)
                    partition.entries.clear()
            else:
                # 전체 클리어
                total_cleared += await self.l1_cache.clear()
                
                if self.l2_cache:
                    # L2 캐시 클리어
                    pass
                
                for partition in self.partitions.values():
                    total_cleared += len(partition.entries)
                    partition.entries.clear()
            
            return Success(total_cleared)
            
        except Exception as e:
            return Failure(f"Failed to clear cache: {e}")
    
    def add_warmup_task(
        self,
        task_id: str,
        loader: Callable,
        keys: List[str],
        schedule: str = "startup"  # startup, periodic
    ):
        """캐시 워밍 작업 추가"""
        self.warmup_tasks[task_id] = {
            "loader": loader,
            "keys": keys,
            "schedule": schedule
        }
    
    def add_prefetch_pattern(
        self,
        pattern_id: str,
        key_pattern: str,
        loader: Callable,
        related_keys: Callable  # 관련 키 생성 함수
    ):
        """프리페치 패턴 추가"""
        self.prefetch_patterns[pattern_id] = {
            "key_pattern": key_pattern,
            "loader": loader,
            "related_keys": related_keys
        }
    
    def add_invalidation_listener(self, listener: Callable):
        """무효화 리스너 추가"""
        self.invalidation_listeners.append(listener)
    
    def get_statistics(self, partition_id: str = None) -> CacheStatistics:
        """통계 조회"""
        if partition_id and partition_id in self.partitions:
            return self.partitions[partition_id].statistics
        
        # 전체 통계
        self.global_statistics.total_requests = (
            self.global_statistics.hits + self.global_statistics.misses
        )
        self.global_statistics.update_hit_ratio()
        
        # L1 통계 병합
        l1_stats = self.l1_cache.get_statistics()
        self.global_statistics.hits += l1_stats.hits
        self.global_statistics.misses += l1_stats.misses
        self.global_statistics.evictions += l1_stats.evictions
        
        return self.global_statistics
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """메모리 사용량 조회"""
        try:
            l1_size = self.l1_cache.statistics.total_size_bytes
            
            partition_sizes = {}
            for pid, partition in self.partitions.items():
                total_size = sum(
                    entry.size_bytes 
                    for entry in partition.entries.values()
                )
                partition_sizes[pid] = total_size
            
            return {
                "l1_cache_bytes": l1_size,
                "l1_cache_mb": l1_size / (1024 * 1024),
                "partitions": partition_sizes,
                "total_bytes": l1_size + sum(partition_sizes.values()),
                "total_mb": (l1_size + sum(partition_sizes.values())) / (1024 * 1024)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _connect_redis(self):
        """Redis 연결"""
        # Redis 클라이언트 연결 (aioredis 사용)
        pass
    
    async def _connect_memcached(self):
        """Memcached 연결"""
        # Memcached 클라이언트 연결 (aiomemcache 사용)
        pass
    
    async def _get_from_l2(self, key: str) -> Optional[Any]:
        """L2 캐시에서 조회"""
        # Redis/Memcached에서 조회
        return None
    
    async def _set_to_l2(self, key: str, value: Any, ttl: int = None):
        """L2 캐시에 저장"""
        # Redis/Memcached에 저장
        pass
    
    async def _delete_from_l2(self, key: str):
        """L2 캐시에서 삭제"""
        # Redis/Memcached에서 삭제
        pass
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """만료 확인"""
        return (time.time() - entry.created_at) > entry.ttl
    
    async def _ttl_cleanup(self):
        """TTL 기반 정리"""
        while self._running:
            try:
                # L1 캐시 정리
                current_time = time.time()
                expired_keys = []
                
                for key, entry in self.l1_cache.entries.items():
                    if self._is_expired(entry):
                        expired_keys.append(key)
                
                for key in expired_keys:
                    await self.l1_cache.delete(key)
                    self.l1_cache.statistics.expired += 1
                
                # 파티션 캐시 정리
                for partition in self.partitions.values():
                    expired_keys = []
                    
                    for key, entry in partition.entries.items():
                        if self._is_expired(entry):
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        del partition.entries[key]
                        partition.statistics.expired += 1
                
                # 60초마다 정리
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"TTL cleanup error: {e}")
                await asyncio.sleep(60)
    
    async def _cache_warmer(self):
        """캐시 워밍"""
        # 시작 시 워밍
        for task_id, task in self.warmup_tasks.items():
            if task["schedule"] == "startup":
                loader = task["loader"]
                for key in task["keys"]:
                    try:
                        value = await loader(key)
                        if value is not None:
                            await self.set(key, value)
                    except Exception as e:
                        print(f"Cache warming error for key {key}: {e}")
        
        # 주기적 워밍
        while self._running:
            try:
                for task_id, task in self.warmup_tasks.items():
                    if task["schedule"] == "periodic":
                        loader = task["loader"]
                        for key in task["keys"]:
                            try:
                                value = await loader(key)
                                if value is not None:
                                    await self.set(key, value)
                            except Exception as e:
                                print(f"Cache warming error for key {key}: {e}")
                
                # 5분마다 워밍
                await asyncio.sleep(300)
                
            except Exception as e:
                print(f"Cache warmer error: {e}")
                await asyncio.sleep(300)
    
    async def _statistics_collector(self):
        """통계 수집"""
        while self._running:
            try:
                # 통계 계산 및 로깅
                stats = self.get_statistics()
                memory_usage = await self.get_memory_usage()
                
                # 통계 로깅 (실제로는 모니터링 시스템에 전송)
                if stats.total_requests > 0:
                    print(f"Cache Stats - Hit Ratio: {stats.hit_ratio:.2f}%, "
                          f"Total Requests: {stats.total_requests}, "
                          f"Memory: {memory_usage['total_mb']:.2f} MB")
                
                # 5분마다 수집
                await asyncio.sleep(300)
                
            except Exception as e:
                print(f"Statistics collector error: {e}")
                await asyncio.sleep(300)


# 전역 분산 캐시 관리자 인스턴스
_distributed_cache_manager: Optional[DistributedCacheManager] = None


def get_distributed_cache_manager(
    config: CacheConfig = None
) -> DistributedCacheManager:
    """분산 캐시 관리자 인스턴스 반환"""
    global _distributed_cache_manager
    
    if _distributed_cache_manager is None:
        _distributed_cache_manager = DistributedCacheManager(config)
    
    return _distributed_cache_manager