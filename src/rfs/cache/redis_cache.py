"""
RFS Redis Cache (RFS v4.1)

Redis 캐시 구현
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field

try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False

from ..core.result import Result, Success, Failure
from ..core.enhanced_logging import get_logger
from .base import CacheBackend, CacheConfig

logger = get_logger(__name__)


@dataclass
class RedisCacheConfig(CacheConfig):
    """Redis 캐시 설정"""
    # Redis 전용 설정
    redis_url: Optional[str] = None
    ssl: bool = False
    ssl_cert_reqs: Optional[str] = None
    ssl_ca_certs: Optional[str] = None
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    
    # 연결 풀 설정
    pool_min_size: int = 1
    pool_max_size: int = 20
    
    # Redis 클러스터 설정
    cluster_mode: bool = False
    startup_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    # 기타 Redis 옵션
    decode_responses: bool = True
    socket_keepalive: bool = True
    socket_keepalive_options: Dict[str, int] = field(default_factory=lambda: {
        "TCP_KEEPIDLE": 1,
        "TCP_KEEPINTVL": 3,
        "TCP_KEEPCNT": 5
    })
    health_check_interval: int = 30


class RedisCache(CacheBackend):
    """Redis 캐시 구현"""
    
    def __init__(self, config: RedisCacheConfig):
        if not REDIS_AVAILABLE:
            raise ImportError("aioredis 패키지가 필요합니다: pip install aioredis")
        
        super().__init__(config)
        self.config: RedisCacheConfig = config
        self.redis: Optional[aioredis.Redis] = None
        self.pool: Optional[aioredis.ConnectionPool] = None
    
    async def connect(self) -> Result[None, str]:
        """Redis 연결"""
        try:
            if self._connected:
                return Success(None)
            
            # 연결 풀 생성
            if self.config.redis_url:
                self.pool = aioredis.ConnectionPool.from_url(
                    self.config.redis_url,
                    max_connections=self.config.pool_max_size,
                    retry_on_timeout=True,
                    decode_responses=self.config.decode_responses
                )
            else:
                self.pool = aioredis.ConnectionPool(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    max_connections=self.config.pool_max_size,
                    retry_on_timeout=True,
                    decode_responses=self.config.decode_responses,
                    socket_keepalive=self.config.socket_keepalive,
                    socket_keepalive_options=self.config.socket_keepalive_options,
                    socket_connect_timeout=self.config.connection_timeout,
                    socket_timeout=self.config.socket_timeout
                )
            
            # Redis 클라이언트 생성
            self.redis = aioredis.Redis(connection_pool=self.pool)
            
            # 연결 테스트
            await self.redis.ping()
            
            self._connected = True
            logger.info(f"Redis 연결 성공: {self.config.host}:{self.config.port}")
            return Success(None)
            
        except Exception as e:
            error_msg = f"Redis 연결 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def disconnect(self) -> Result[None, str]:
        """Redis 연결 해제"""
        try:
            if not self._connected:
                return Success(None)
            
            if self.redis:
                await self.redis.close()
            
            if self.pool:
                await self.pool.disconnect()
            
            self._connected = False
            logger.info("Redis 연결 해제")
            return Success(None)
            
        except Exception as e:
            error_msg = f"Redis 연결 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def get(self, key: str) -> Result[Optional[Any], str]:
        """값 조회"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            data = await self.redis.get(cache_key)
            
            if data is None:
                self._stats["misses"] += 1
                return Success(None)
            
            # 값 역직렬화
            if isinstance(data, bytes):
                value = self._deserialize(data)
            elif isinstance(data, str):
                value = self._deserialize(data.encode())
            else:
                value = data
            
            self._stats["hits"] += 1
            return Success(value)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis GET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def set(self, key: str, value: Any, ttl: int = None) -> Result[None, str]:
        """값 저장"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            ttl = self._validate_ttl(ttl)
            
            # 값 직렬화
            serialized_value = self._serialize(value)
            
            # Redis에 저장
            await self.redis.setex(cache_key, ttl, serialized_value)
            
            self._stats["sets"] += 1
            return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis SET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def delete(self, key: str) -> Result[None, str]:
        """값 삭제"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            await self.redis.delete(cache_key)
            
            self._stats["deletes"] += 1
            return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis DELETE 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def exists(self, key: str) -> Result[bool, str]:
        """키 존재 확인"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            exists = await self.redis.exists(cache_key)
            
            return Success(bool(exists))
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis EXISTS 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def expire(self, key: str, ttl: int) -> Result[None, str]:
        """TTL 설정"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            ttl = self._validate_ttl(ttl)
            
            await self.redis.expire(cache_key, ttl)
            
            return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis EXPIRE 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def ttl(self, key: str) -> Result[int, str]:
        """TTL 조회"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            remaining_ttl = await self.redis.ttl(cache_key)
            
            return Success(remaining_ttl)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis TTL 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def clear(self) -> Result[None, str]:
        """모든 키 삭제"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            # 네임스페이스 패턴으로 키 삭제
            if self.namespace:
                pattern = f"{self.namespace}:*"
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
            else:
                await self.redis.flushdb()
            
            return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis CLEAR 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    # Redis 전용 메서드들
    async def get_many(self, keys: List[str]) -> Result[Dict[str, Any], str]:
        """다중 조회 (Redis MGET 사용)"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_keys = [self._make_key(key) for key in keys]
            values = await self.redis.mget(cache_keys)
            
            result = {}
            for i, value in enumerate(values):
                if value is not None:
                    original_key = keys[i]
                    if isinstance(value, bytes):
                        deserialized_value = self._deserialize(value)
                    elif isinstance(value, str):
                        deserialized_value = self._deserialize(value.encode())
                    else:
                        deserialized_value = value
                    
                    if deserialized_value is not None:
                        result[original_key] = deserialized_value
                        self._stats["hits"] += 1
                    else:
                        self._stats["misses"] += 1
                else:
                    self._stats["misses"] += 1
            
            return Success(result)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis MGET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def set_many(self, data: Dict[str, Any], ttl: int = None) -> Result[None, str]:
        """다중 저장 (Redis Pipeline 사용)"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            ttl = self._validate_ttl(ttl)
            
            # Pipeline 사용
            async with self.redis.pipeline(transaction=True) as pipe:
                for key, value in data.items():
                    cache_key = self._make_key(key)
                    serialized_value = self._serialize(value)
                    pipe.setex(cache_key, ttl, serialized_value)
                
                await pipe.execute()
            
            self._stats["sets"] += len(data)
            return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis 배치 저장 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def delete_many(self, keys: List[str]) -> Result[None, str]:
        """다중 삭제"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            if not keys:
                return Success(None)
            
            cache_keys = [self._make_key(key) for key in keys]
            await self.redis.delete(*cache_keys)
            
            self._stats["deletes"] += len(keys)
            return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis 배치 삭제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def increment(self, key: str, amount: int = 1) -> Result[int, str]:
        """값 증가"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            new_value = await self.redis.incrby(cache_key, amount)
            
            return Success(new_value)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis INCREMENT 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def decrement(self, key: str, amount: int = 1) -> Result[int, str]:
        """값 감소"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")
            
            cache_key = self._make_key(key)
            new_value = await self.redis.decrby(cache_key, amount)
            
            return Success(new_value)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"Redis DECREMENT 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)


@dataclass
class RedisClusterConfig(RedisCacheConfig):
    """Redis 클러스터 설정"""
    startup_nodes: List[Dict[str, Any]] = field(default_factory=list)
    skip_full_coverage_check: bool = False
    max_connections_per_node: int = 20


class RedisClusterCache(RedisCache):
    """Redis 클러스터 캐시 구현"""
    
    def __init__(self, config: RedisClusterConfig):
        if not REDIS_AVAILABLE:
            raise ImportError("aioredis 패키지가 필요합니다: pip install aioredis")
        
        super().__init__(config)
        self.config: RedisClusterConfig = config
        self.cluster: Optional[aioredis.RedisCluster] = None
    
    async def connect(self) -> Result[None, str]:
        """Redis 클러스터 연결"""
        try:
            if self._connected:
                return Success(None)
            
            if not self.config.startup_nodes:
                return Failure("Redis 클러스터 노드가 설정되지 않았습니다")
            
            # 클러스터 연결
            self.cluster = aioredis.RedisCluster(
                startup_nodes=self.config.startup_nodes,
                decode_responses=self.config.decode_responses,
                skip_full_coverage_check=self.config.skip_full_coverage_check,
                max_connections_per_node=self.config.max_connections_per_node
            )
            
            # 연결 테스트
            await self.cluster.ping()
            
            self._connected = True
            logger.info(f"Redis 클러스터 연결 성공: {len(self.config.startup_nodes)}개 노드")
            return Success(None)
            
        except Exception as e:
            error_msg = f"Redis 클러스터 연결 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def disconnect(self) -> Result[None, str]:
        """Redis 클러스터 연결 해제"""
        try:
            if not self._connected:
                return Success(None)
            
            if self.cluster:
                await self.cluster.close()
            
            self._connected = False
            logger.info("Redis 클러스터 연결 해제")
            return Success(None)
            
        except Exception as e:
            error_msg = f"Redis 클러스터 연결 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    @property
    def redis(self) -> Optional[aioredis.RedisCluster]:
        """Redis 클러스터 인스턴스"""
        return self.cluster
    
    @redis.setter
    def redis(self, value):
        """Redis 클러스터 인스턴스 설정"""
        self.cluster = value