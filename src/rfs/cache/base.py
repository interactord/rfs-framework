"""
RFS Cache Base (RFS v4.1)

캐시 기본 클래스 및 설정
"""

import asyncio
import hashlib
import json
import logging
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = get_logger(__name__)


class CacheType(str, Enum):
    """캐시 타입"""

    REDIS = "redis"
    MEMCACHED = "memcached"
    MEMORY = "memory"
    DISTRIBUTED = "distributed"


class SerializationType(str, Enum):
    """직렬화 타입"""

    JSON = "json"
    PICKLE = "pickle"
    STRING = "string"
    MSGPACK = "msgpack"


@dataclass
class CacheConfig:
    """캐시 설정"""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    cache_type: CacheType = CacheType.REDIS
    serialization: SerializationType = SerializationType.JSON
    default_ttl: int = 3600
    max_ttl: int = 86400
    min_ttl: int = 1
    pool_size: int = 20
    max_connections: int = 50
    connection_timeout: int = 5
    socket_timeout: int = 5
    max_memory: int = 100 * 1024 * 1024
    eviction_policy: str = "lru"
    cluster_nodes: List[str] = field(default_factory=list)
    consistent_hashing: bool = True
    enable_metrics: bool = True
    metrics_interval: int = 60
    namespace: str = "rfs"
    compress_threshold: int = 1024
    retry_count: int = 3
    retry_delay: float = 0.1


class CacheBackend(ABC):
    """캐시 백엔드 추상 클래스"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.namespace = config.namespace
        self._connected = False
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    @abstractmethod
    async def connect(self) -> Result[None, str]:
        """캐시 연결"""
        pass

    @abstractmethod
    async def disconnect(self) -> Result[None, str]:
        """캐시 연결 해제"""
        pass

    @abstractmethod
    async def get(self, key: str) -> Result[Optional[Any], str]:
        """값 조회"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None) -> Result[None, str]:
        """값 저장"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> Result[None, str]:
        """값 삭제"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> Result[bool, str]:
        """키 존재 확인"""
        pass

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> Result[None, str]:
        """TTL 설정"""
        pass

    @abstractmethod
    async def ttl(self, key: str) -> Result[int, str]:
        """TTL 조회"""
        pass

    @abstractmethod
    async def clear(self) -> Result[None, str]:
        """모든 키 삭제"""
        pass

    async def get_many(self, keys: List[str]) -> Result[Dict[str, Any], str]:
        """다중 조회"""
        try:
            result = {}
            for key in keys:
                get_result = await self.get(key)
                if get_result.is_success():
                    value = get_result.unwrap()
                    if value is not None:
                        result[key] = value
            return Success(result)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            return Failure(f"배치 조회 실패: {str(e)}")

    async def set_many(
        self, data: Dict[str, Any], ttl: int = None
    ) -> Result[None, str]:
        """다중 저장"""
        try:
            for key, value in data.items():
                set_result = await self.set(key, value, ttl)
                if not set_result.is_success():
                    return Failure(f"배치 저장 실패: {set_result.unwrap_err()}")
            return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            return Failure(f"배치 저장 실패: {str(e)}")

    async def delete_many(self, keys: List[str]) -> Result[None, str]:
        """다중 삭제"""
        try:
            for key in keys:
                delete_result = await self.delete(key)
                if not delete_result.is_success():
                    return Failure(f"배치 삭제 실패: {delete_result.unwrap_err()}")
            return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            return Failure(f"배치 삭제 실패: {str(e)}")

    def _make_key(self, key: str) -> str:
        """네임스페이스가 포함된 키 생성"""
        if self.namespace:
            return f"{self.namespace}:{key}"
        return key

    def _hash_key(self, key: str) -> str:
        """키 해시 생성"""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _serialize(self, value: Any) -> bytes:
        """값 직렬화"""
        try:
            match self.config.serialization:
                case SerializationType.JSON:
                    return json.dumps(value, ensure_ascii=False).encode()
                case SerializationType.PICKLE:
                    return pickle.dumps(value)
                case SerializationType.STRING:
                    return str(value).encode()
                case SerializationType.MSGPACK:
                    try:
                        import msgpack

                        return msgpack.packb(value)
                    except ImportError:
                        logger.warning("msgpack을 사용할 수 없어 JSON으로 대체합니다")
                        return json.dumps(value, ensure_ascii=False).encode()
                case _:
                    return json.dumps(value, ensure_ascii=False).encode()
        except Exception as e:
            logger.error(f"직렬화 실패: {e}")
            return b""

    def _deserialize(self, data: bytes) -> Any:
        """값 역직렬화"""
        try:
            if not data:
                return None
            match self.config.serialization:
                case SerializationType.JSON:
                    return json.loads(data.decode())
                case SerializationType.PICKLE:
                    return pickle.loads(data)
                case SerializationType.STRING:
                    return data.decode()
                case SerializationType.MSGPACK:
                    try:
                        import msgpack

                        return msgpack.unpackb(data, raw=False)
                    except ImportError:
                        return json.loads(data.decode())
                case _:
                    return json.loads(data.decode())
        except Exception as e:
            logger.error(f"역직렬화 실패: {e}")
            return None

    def _validate_ttl(self, ttl: int = None) -> int:
        """TTL 유효성 검증 및 정규화"""
        if ttl is None:
            ttl = self.config.default_ttl
        if ttl < self.config.min_ttl:
            ttl = self.config.min_ttl
        elif ttl > self.config.max_ttl:
            ttl = self.config.max_ttl
        return ttl

    def get_stats(self) -> Dict[str, int]:
        """캐시 통계 반환"""
        total_operations = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_operations if total_operations > 0 else 0
        return {
            **self._stats,
            "hit_rate": round(hit_rate, 4),
            "total_operations": total_operations,
        }

    def reset_stats(self):
        """통계 초기화"""
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    @property
    def is_connected(self) -> bool:
        """연결 상태"""
        return self._connected


class CacheManager(metaclass=SingletonMeta):
    """캐시 매니저"""

    def __init__(self):
        self.caches = {}
        self.default_cache = None

    async def add_cache(self, name: str, cache: CacheBackend) -> Result[None, str]:
        """캐시 추가"""
        try:
            connect_result = await cache.connect()
            if not connect_result.is_success():
                return Failure(f"캐시 연결 실패: {connect_result.unwrap_err()}")
            self.caches = {**self.caches, name: cache}
            if not self.default_cache:
                self.default_cache = name
            logger.info(f"캐시 추가: {name}")
            return Success(None)
        except Exception as e:
            return Failure(f"캐시 추가 실패: {str(e)}")

    def get_cache(self, name: str = None) -> Optional[CacheBackend]:
        """캐시 조회"""
        if name is None:
            name = self.default_cache
        return self.caches.get(name) if name else None

    async def remove_cache(self, name: str) -> Result[None, str]:
        """캐시 제거"""
        try:
            if name not in self.caches:
                return Success(None)
            cache = self.caches[name]
            disconnect_result = await cache.disconnect()
            if not disconnect_result.is_success():
                logger.warning(f"캐시 연결 해제 실패: {disconnect_result.unwrap_err()}")
            del self.caches[name]
            if self.default_cache == name:
                self.default_cache = (
                    next(iter(self.caches.keys())) if self.caches else None
                )
            logger.info(f"캐시 제거: {name}")
            return Success(None)
        except Exception as e:
            return Failure(f"캐시 제거 실패: {str(e)}")

    async def close_all(self) -> Result[None, str]:
        """모든 캐시 연결 해제"""
        try:
            for name, cache in list(self.caches.items()):
                await self.remove_cache(name)
            logger.info("모든 캐시 연결 해제")
            return Success(None)
        except Exception as e:
            return Failure(f"캐시 일괄 해제 실패: {str(e)}")

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """모든 캐시 통계"""
        return {name: cache.get_stats() for name, cache in self.caches.items()}


def get_cache_manager() -> CacheManager:
    """캐시 매니저 인스턴스 반환"""
    return CacheManager()


def get_cache(name: str = None) -> Optional[CacheBackend]:
    """캐시 인스턴스 반환"""
    manager = get_cache_manager()
    return manager.get_cache(name)


async def create_cache(
    config: CacheConfig, name="default"
) -> Result[CacheBackend, str]:
    """캐시 생성"""
    try:
        match config.cache_type:
            case CacheType.REDIS:
                from .redis_cache import RedisCache

                cache = RedisCache(config)
            case CacheType.MEMORY:
                from .memory_cache import MemoryCache

                cache = MemoryCache(config)
            case CacheType.DISTRIBUTED:
                from .distributed import DistributedCache

                cache = DistributedCache(config)
            case _:
                return Failure(f"지원되지 않는 캐시 타입: {config.cache_type}")
        manager = get_cache_manager()
        add_result = await manager.add_cache(name, cache)
        if not add_result.is_success():
            return Failure(add_result.unwrap_err())
        return Success(cache)
    except Exception as e:
        return Failure(f"캐시 생성 실패: {str(e)}")


class Cache:
    """고수준 캐시 인터페이스"""

    def __init__(self, cache_name: str = None):
        self.cache_name = cache_name

    @property
    def backend(self) -> Optional[CacheBackend]:
        """캐시 백엔드"""
        return get_cache(self.cache_name)

    async def get(self, key: str, default: Any = None) -> Any:
        """값 조회"""
        backend = self.backend
        if not backend:
            return default
        result = await backend.get(key)
        if result.is_success():
            value = result.unwrap()
            return value if value is not None else default
        return default

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """값 저장"""
        backend = self.backend
        if not backend:
            return False
        result = await backend.set(key, value, ttl)
        return result.is_success()

    async def delete(self, key: str) -> bool:
        """값 삭제"""
        backend = self.backend
        if not backend:
            return False
        result = await backend.delete(key)
        return result.is_success()

    async def exists(self, key: str) -> bool:
        """키 존재 확인"""
        backend = self.backend
        if not backend:
            return False
        result = await backend.exists(key)
        return result.unwrap() if result.is_success() else False

    async def clear(self) -> bool:
        """모든 키 삭제"""
        backend = self.backend
        if not backend:
            return False
        backend = {}
        return result.is_success()


_default_cache = Cache()


def cache() -> Cache:
    """기본 캐시 인스턴스 반환"""
    return _default_cache
