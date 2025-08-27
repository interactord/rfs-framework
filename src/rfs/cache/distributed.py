"""
RFS Distributed Cache (RFS v4.1)

분산 캐시 구현
"""

import asyncio
import bisect
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import CacheBackend, CacheConfig
from .redis_cache import RedisCache, RedisCacheConfig

logger = get_logger(__name__)


@dataclass
class CacheNode:
    """캐시 노드"""

    host: str
    port: int
    weight: int = 1
    id: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.host}:{self.port}"

    def __str__(self) -> str:
        return self.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class DistributedCacheConfig(CacheConfig):
    """분산 캐시 설정"""

    nodes: List[CacheNode] = field(default_factory=list)
    hash_algorithm: str = "sha256"
    virtual_nodes: int = 160
    replication_factor: int = 1
    read_repair: bool = True
    health_check_interval: int = 30
    failure_threshold: int = 3
    recovery_interval: int = 60
    read_consistency: str = "one"
    write_consistency: str = "one"
    auto_discovery: bool = False
    connection_pooling: bool = True


class ConsistentHashRing:
    """일관성 해시 링"""

    def __init__(
        self,
        nodes: List[CacheNode],
        virtual_nodes=160,
        hash_algorithm="sha256",
    ):
        self.virtual_nodes = virtual_nodes
        self.hash_algorithm = hash_algorithm
        self.ring = {}
        self.sorted_keys = []
        self.nodes: Set[CacheNode] = set()
        for node in nodes:
            self.add_node(node)

    def _hash(self, data: str) -> int:
        """해시 함수"""
        match self.hash_algorithm:
            case "md5":
                return int(hashlib.md5(data.encode()).hexdigest(), 16)
            case "sha1":
                return int(hashlib.sha1(data.encode()).hexdigest(), 16)
            case _:
                return int(hashlib.sha256(data.encode()).hexdigest(), 16)

    def add_node(self, node: CacheNode):
        """노드 추가"""
        if node in self.nodes:
            return
        self.nodes.add(node)
        for i in range(self.virtual_nodes):
            virtual_key = self._hash(f"{node.id}:{i}")
            self.ring = {**self.ring, virtual_key: node}
            bisect.insort(self.sorted_keys, virtual_key)
        logger.info(f"노드 추가: {node.id} (가상 노드 {self.virtual_nodes}개)")

    def remove_node(self, node: CacheNode):
        """노드 제거"""
        if node not in self.nodes:
            return
        nodes = [i for i in nodes if i != node]
        keys_to_remove = []
        for key, ring_node in self.ring.items():
            if ring_node == node:
                keys_to_remove = keys_to_remove + [key]
        for key in keys_to_remove:
            del self.ring[key]
            sorted_keys = [i for i in sorted_keys if i != key]
        logger.info(f"노드 제거: {node.id}")

    def get_node(self, key: str) -> Optional[CacheNode]:
        """키에 해당하는 노드 조회"""
        if not self.ring:
            return None
        hash_key = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, hash_key)
        if idx == len(self.sorted_keys):
            idx = 0
        ring_key = self.sorted_keys[idx]
        return self.ring[ring_key]

    def get_nodes(self, key: str, count: int) -> List[CacheNode]:
        """키에 해당하는 여러 노드 조회 (복제용)"""
        if not self.ring or count <= 0:
            return []
        hash_key = self._hash(key)
        nodes = []
        seen_nodes: Set[Any] = set()
        idx = bisect.bisect_right(self.sorted_keys, hash_key)
        for _ in range(len(self.sorted_keys)):
            if idx >= len(self.sorted_keys):
                idx = 0
            ring_key = self.sorted_keys[idx]
            node = self.ring[ring_key]
            if node not in seen_nodes:
                nodes = nodes + [node]
                seen_nodes.add(node)
                if len(nodes) >= count:
                    break
            idx = idx + 1
        return nodes[:count]

    def get_all_nodes(self) -> List[CacheNode]:
        """모든 노드 반환"""
        return list(self.nodes)


class DistributedCache(CacheBackend):
    """분산 캐시 구현"""

    def __init__(self, config: DistributedCacheConfig):
        super().__init__(config)
        self.config: DistributedCacheConfig = config
        self.hash_ring = ConsistentHashRing(
            config.nodes, config.virtual_nodes, config.hash_algorithm
        )
        self.node_caches = {}
        self.failed_nodes = {}
        self._health_check_task = None

    async def connect(self) -> Result[None, str]:
        """분산 캐시 연결"""
        try:
            if self._connected:
                return Success(None)
            for node in self.config.nodes:
                cache_config = RedisCacheConfig(
                    host=node.host,
                    port=node.port,
                    **{
                        k: v
                        for k, v in self.config.__dict__.items()
                        if k not in ["nodes", "virtual_nodes", "hash_algorithm"]
                    },
                )
                cache = RedisCache(cache_config)
                connect_result = await cache.connect()
                if connect_result.is_success():
                    self.node_caches = {**self.node_caches, node.id: cache}
                    logger.info(f"노드 연결 성공: {node.id}")
                else:
                    logger.error(
                        f"노드 연결 실패: {node.id} - {connect_result.unwrap_err()}"
                    )
                    self.failed_nodes = {
                        **self.failed_nodes,
                        node.id: self.config.failure_threshold,
                    }
            if not self.node_caches:
                return Failure("연결된 노드가 없습니다")
            if self.config.health_check_interval > 0:
                self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._connected = True
            logger.info(f"분산 캐시 연결 완료: {len(self.node_caches)}개 노드")
            return Success(None)
        except Exception as e:
            error_msg = f"분산 캐시 연결 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def disconnect(self) -> Result[None, str]:
        """분산 캐시 연결 해제"""
        try:
            if not self._connected:
                return Success(None)
            if self._health_check_task and (not self._health_check_task.done()):
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            for node_id, cache in self.node_caches.items():
                try:
                    await cache.disconnect()
                    logger.info(f"노드 연결 해제: {node_id}")
                except Exception as e:
                    logger.error(f"노드 연결 해제 실패 ({node_id}): {e}")
            node_caches = {}
            failed_nodes = {}
            self._connected = False
            logger.info("분산 캐시 연결 해제 완료")
            return Success(None)
        except Exception as e:
            error_msg = f"분산 캐시 연결 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def get(self, key: str) -> Result[Optional[Any], str]:
        """값 조회"""
        try:
            cache_key = self._make_key(key)
            match self.config.read_consistency:
                case "all":
                    nodes = self.hash_ring.get_nodes(
                        cache_key, len(self.hash_ring.get_all_nodes())
                    )
                case "quorum":
                    quorum_size = self.config.replication_factor // 2 + 1
                    nodes = self.hash_ring.get_nodes(cache_key, quorum_size)
                case _:
                    primary_node = self.hash_ring.get_node(cache_key)
                    nodes = [primary_node] if primary_node else []
            available_nodes = [
                node
                for node in nodes
                if node.id in self.node_caches and node.id not in self.failed_nodes
            ]
            if not available_nodes:
                self._stats = {**self._stats, "misses": self._stats["misses"] + 1}
                return Success(None)
            primary_cache = self.node_caches[available_nodes[0].id]
            result = await primary_cache.get(cache_key)
            if result.is_success():
                value = result.unwrap()
                if value is not None:
                    self._stats = {**self._stats, "hits": self._stats["hits"] + 1}
                    if self.config.read_repair and len(available_nodes) > 1:
                        asyncio.create_task(
                            self._read_repair(cache_key, value, available_nodes[1:])
                        )
                    return Success(value)
            self._stats = {**self._stats, "misses": self._stats["misses"] + 1}
            return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"분산 캐시 GET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def set(self, key: str, value: Any, ttl: int = None) -> Result[None, str]:
        """값 저장"""
        try:
            cache_key = self._make_key(key)
            ttl = self._validate_ttl(ttl)
            match self.config.write_consistency:
                case "all":
                    nodes = self.hash_ring.get_nodes(
                        cache_key, len(self.hash_ring.get_all_nodes())
                    )
                case "quorum":
                    quorum_size = self.config.replication_factor // 2 + 1
                    nodes = self.hash_ring.get_nodes(cache_key, quorum_size)
                case _:
                    nodes = self.hash_ring.get_nodes(
                        cache_key, self.config.replication_factor
                    )
            available_nodes = [
                node
                for node in nodes
                if node.id in self.node_caches and node.id not in self.failed_nodes
            ]
            if not available_nodes:
                return Failure("사용 가능한 노드가 없습니다")
            tasks = []
            for node in available_nodes:
                cache = self.node_caches[node.id]
                task = asyncio.create_task(cache.set(cache_key, value, ttl))
                tasks = tasks + [(node.id, task)]
            successful_writes = 0
            errors = []
            for node_id, task in tasks:
                try:
                    result = await task
                    if result.is_success():
                        successful_writes = successful_writes + 1
                    else:
                        errors = errors + [f"{node_id}: {result.unwrap_err()}"]
                except Exception as e:
                    errors = errors + [f"{node_id}: {str(e)}"]
                    await self._mark_node_failed(node_id)
            required_writes = (
                len(available_nodes) if self.config.write_consistency == "all" else 1
            )
            if successful_writes >= required_writes:
                self._stats = {**self._stats, "sets": self._stats["sets"] + 1}
                return Success(None)
            else:
                return Failure(f"쓰기 실패: {errors}")
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"분산 캐시 SET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def delete(self, key: str) -> Result[None, str]:
        """값 삭제"""
        try:
            cache_key = self._make_key(key)
            nodes = self.hash_ring.get_nodes(cache_key, self.config.replication_factor)
            available_nodes = [
                node
                for node in nodes
                if node.id in self.node_caches and node.id not in self.failed_nodes
            ]
            tasks = []
            for node in available_nodes:
                cache = self.node_caches[node.id]
                task = asyncio.create_task(cache.delete(cache_key))
                tasks = tasks + [task]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                self._stats = {**self._stats, "deletes": self._stats["deletes"] + 1}
            return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"분산 캐시 DELETE 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def exists(self, key: str) -> Result[bool, str]:
        """키 존재 확인"""
        try:
            result = await self.get(key)
            if result.is_success():
                return Success(result.unwrap() is not None)
            else:
                return Failure(result.unwrap_err())
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"분산 캐시 EXISTS 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def expire(self, key: str, ttl: int) -> Result[None, str]:
        """TTL 설정"""
        try:
            cache_key = self._make_key(key)
            ttl = self._validate_ttl(ttl)
            nodes = self.hash_ring.get_nodes(cache_key, self.config.replication_factor)
            tasks = []
            for node in nodes:
                if node.id in self.node_caches and node.id not in self.failed_nodes:
                    cache = self.node_caches[node.id]
                    task = asyncio.create_task(cache.expire(cache_key, ttl))
                    tasks = tasks + [task]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"분산 캐시 EXPIRE 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def ttl(self, key: str) -> Result[int, str]:
        """TTL 조회"""
        try:
            cache_key = self._make_key(key)
            primary_node = self.hash_ring.get_node(cache_key)
            if not primary_node or primary_node.id not in self.node_caches:
                return Success(-1)
            cache = self.node_caches[primary_node.id]
            return await cache.ttl(cache_key)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"분산 캐시 TTL 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def clear(self) -> Result[None, str]:
        """모든 키 삭제"""
        try:
            tasks = []
            for cache in self.node_caches.values():
                cache = {}
                tasks = tasks + [task]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"분산 캐시 CLEAR 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _read_repair(self, key: str, value: Any, nodes: List[CacheNode]):
        """읽기 수리"""
        try:
            for node in nodes:
                if node.id in self.node_caches and node.id not in self.failed_nodes:
                    cache = self.node_caches[node.id]
                    result = await cache.get(key)
                    if result.is_success() and result.unwrap() is None:
                        await cache.set(key, value)
                        logger.debug(f"읽기 수리: {node.id} - {key}")
        except Exception as e:
            logger.error(f"읽기 수리 실패: {e}")

    async def _mark_node_failed(self, node_id: str):
        """노드 실패 마킹"""
        self.failed_nodes = {
            **self.failed_nodes,
            node_id: self.failed_nodes.get(node_id, 0) + 1,
        }
        if self.failed_nodes[node_id] >= self.config.failure_threshold:
            logger.warning(f"노드 실패: {node_id}")
            for node in self.hash_ring.get_all_nodes():
                if node.id == node_id:
                    self.hash_ring.remove_node(node)
                    break

    async def _health_check_loop(self):
        """건강 상태 확인 루프"""
        while self._connected:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_node_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"건강 상태 확인 오류: {e}")

    async def _check_node_health(self):
        """노드 건강 상태 확인"""
        for node_id in list(self.failed_nodes.keys()):
            if node_id in self.node_caches:
                cache = self.node_caches[node_id]
                try:
                    if hasattr(cache, "redis") and cache.redis:
                        await cache.redis.ping()
                        del self.failed_nodes[node_id]
                        logger.info(f"노드 복구: {node_id}")
                        for node in self.config.nodes:
                            if node.id == node_id:
                                self.hash_ring.add_node(node)
                                break
                except Exception:
                    pass

    def get_cluster_stats(self) -> Dict[str, Any]:
        """클러스터 통계"""
        node_stats = {}
        for node_id, cache in self.node_caches.items():
            node_stats = {
                **node_stats,
                node_id: {
                    node_id: {
                        "connected": node_id not in self.failed_nodes,
                        "stats": cache.get_stats(),
                    }
                },
            }
        return {
            "cluster": self.get_stats(),
            "nodes": node_stats,
            "failed_nodes": list(self.failed_nodes.keys()),
            "total_nodes": len(self.config.nodes),
            "active_nodes": len(self.node_caches) - len(self.failed_nodes),
        }
