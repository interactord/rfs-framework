"""
RFS Cache System (RFS v4.1)

통합 캐시 시스템
- Redis/Memcached 지원
- 분산 캐시 최적화
- TTL 및 만료 정책 관리
- 캐시 히트/미스 메트릭스
"""

from .base import CacheBackend, CacheConfig, CacheType, get_cache, get_cache_manager
from .decorators import (
    cache_key,
    cache_namespace,
    cache_result,
    cache_ttl,
    cached,
    invalidate_cache,
)
from .distributed import (
    CacheNode,
    ConsistentHashRing,
    DistributedCache,
    DistributedCacheConfig,
)
from .memory_cache import LFUCache, LRUCache, MemoryCache, MemoryCacheConfig
from .metrics import (
    CacheMetrics,
    MetricsCollector,
    get_cache_metrics,
    reset_cache_metrics,
)
from .redis_cache import (
    RedisCache,
    RedisCacheConfig,
    RedisClusterCache,
    RedisClusterConfig,
)

__all__ = [
    # Cache Core
    "CacheConfig",
    "CacheType",
    "CacheBackend",
    "get_cache",
    "get_cache_manager",
    # Redis Cache
    "RedisCache",
    "RedisCacheConfig",
    "RedisClusterCache",
    "RedisClusterConfig",
    # Memory Cache
    "MemoryCache",
    "MemoryCacheConfig",
    "LRUCache",
    "LFUCache",
    # Distributed Cache
    "DistributedCache",
    "DistributedCacheConfig",
    "ConsistentHashRing",
    "CacheNode",
    # Decorators
    "cached",
    "cache_result",
    "invalidate_cache",
    "cache_key",
    "cache_ttl",
    "cache_namespace",
    # Metrics
    "CacheMetrics",
    "MetricsCollector",
    "get_cache_metrics",
    "reset_cache_metrics",
]

__version__ = "4.1.0"
__cache_features__ = [
    "Redis/Memcached 통합",
    "분산 캐시 지원",
    "자동 TTL 관리",
    "캐시 메트릭스",
    "LRU/LFU 정책",
    "일관성 해싱",
    "캐시 데코레이터",
    "클러스터 지원",
]
