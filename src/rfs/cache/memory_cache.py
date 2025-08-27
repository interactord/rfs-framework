"""
RFS Memory Cache (RFS v4.1)

메모리 캐시 구현
"""

import asyncio
import heapq
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import CacheBackend, CacheConfig

logger = get_logger(__name__)


@dataclass
class MemoryCacheConfig(CacheConfig):
    """메모리 캐시 설정"""

    max_size: int = 1000
    eviction_policy: str = "lru"
    cleanup_interval: int = 300
    lazy_expiration: bool = True
    memory_limit: int = 100 * 1024 * 1024
    estimate_size: bool = True
    enable_detailed_stats: bool = True


class CacheItem:
    """캐시 항목"""

    def __init__(self, key: str, value: Any, ttl: int = None):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.accessed_at = self.created_at
        self.access_count = 1
        if ttl is not None and ttl >= 0:
            self.expires_at = self.created_at + ttl
        else:
            self.expires_at = None
        self.size = self._estimate_size(value)

    def _estimate_size(self, value: Any) -> int:
        """값 크기 추정"""
        try:
            import sys

            return sys.getsizeof(value)
        except:
            return 1024

    def is_expired(self) -> bool:
        """만료 확인"""
        if self.expires_at is None:
            return False
        # TTL이 0인 경우(즉시 만료)는 항상 만료된 것으로 처리
        if self.expires_at == self.created_at:
            return True
        return time.time() > self.expires_at

    def touch(self):
        """접근 시간 업데이트"""
        self.accessed_at = time.time()
        self.access_count = self.access_count + 1

    def __lt__(self, other):
        """TTL 기반 정렬용"""
        if self.expires_at is None and other.expires_at is None:
            return self.created_at < other.created_at
        elif self.expires_at is None:
            return False
        elif other.expires_at is None:
            return True
        return self.expires_at < other.expires_at


class MemoryCache(CacheBackend):
    """메모리 캐시 구현"""

    def __init__(self, config: MemoryCacheConfig):
        super().__init__(config)
        self.config: MemoryCacheConfig = config
        self._data = {}
        self._access_order: OrderedDict = OrderedDict()
        self._frequency = {}
        self._insertion_order = []
        self._ttl_heap: List[Tuple[float, str]] = []
        self._lock = RLock()
        self._current_size = 0
        self._current_memory = 0
        self._cleanup_task = None

    async def connect(self) -> Result[None, str]:
        """캐시 초기화"""
        try:
            if self._connected:
                return Success(None)
            if self.config.cleanup_interval > 0:
                self._cleanup_task = asyncio.create_task(self._cleanup_expired_items())
            self._connected = True
            logger.info("메모리 캐시 초기화 완료")
            return Success(None)
        except Exception as e:
            error_msg = f"메모리 캐시 초기화 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def disconnect(self) -> Result[None, str]:
        """캐시 정리"""
        try:
            if not self._connected:
                return Success(None)
            if self._cleanup_task and (not self._cleanup_task.done()):
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            with self._lock:
                self._data = {}
                self._access_order = OrderedDict()
                self._frequency = {}
                self._insertion_order = []
                self._ttl_heap = []
                self._current_size = 0
                self._current_memory = 0
            self._connected = False
            logger.info("메모리 캐시 정리 완료")
            return Success(None)
        except Exception as e:
            error_msg = f"메모리 캐시 정리 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def get(self, key: str) -> Result[Optional[Any], str]:
        """값 조회"""
        try:
            cache_key = self._make_key(key)
            with self._lock:
                item = self._data.get(cache_key)
                if item is None:
                    self._stats = {**self._stats, "misses": self._stats["misses"] + 1}
                    return Success(None)
                # TTL=0 (즉시 만료) 체크는 lazy_expiration 설정과 관계없이 항상 처리
                if item.is_expired():
                    if (
                        item.expires_at is not None
                        and item.expires_at == item.created_at
                    ) or self.config.lazy_expiration:
                        self._remove_item(cache_key)
                        self._stats = {
                            **self._stats,
                            "misses": self._stats["misses"] + 1,
                        }
                        return Success(None)
                item.touch()
                self._update_access_tracking(cache_key)
                self._stats = {**self._stats, "hits": self._stats["hits"] + 1}
                return Success(item.value)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 GET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def set(self, key: str, value: Any, ttl: int = None) -> Result[None, str]:
        """값 저장"""
        try:
            cache_key = self._make_key(key)
            ttl = self._validate_ttl(ttl) if ttl is not None else None
            with self._lock:
                if cache_key in self._data:
                    self._remove_item(cache_key)
                item = CacheItem(cache_key, value, ttl)
                self._ensure_space(item.size)
                self._data[cache_key] = item
                self._current_size = self._current_size + 1
                self._current_memory = self._current_memory + item.size
                self._update_insertion_tracking(cache_key)
                if item.expires_at:
                    heapq.heappush(self._ttl_heap, (item.expires_at, cache_key))
                self._stats = {**self._stats, "sets": self._stats["sets"] + 1}
                return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 SET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def delete(self, key: str) -> Result[None, str]:
        """값 삭제"""
        try:
            cache_key = self._make_key(key)
            with self._lock:
                if cache_key in self._data:
                    self._remove_item(cache_key)
                    self._stats = {**self._stats, "deletes": self._stats["deletes"] + 1}
                return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 DELETE 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def exists(self, key: str) -> Result[bool, str]:
        """키 존재 확인"""
        try:
            cache_key = self._make_key(key)
            with self._lock:
                item = self._data.get(cache_key)
                if item is None:
                    return Success(False)
                if self.config.lazy_expiration and item.is_expired():
                    self._remove_item(cache_key)
                    return Success(False)
                return Success(True)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 EXISTS 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def expire(self, key: str, ttl: int) -> Result[None, str]:
        """TTL 설정"""
        try:
            cache_key = self._make_key(key)
            ttl = self._validate_ttl(ttl)
            with self._lock:
                item = self._data.get(cache_key)
                if item is None:
                    return Success(None)
                item.expires_at = time.time() + ttl
                heapq.heappush(self._ttl_heap, (item.expires_at, cache_key))
                return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 EXPIRE 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def ttl(self, key: str) -> Result[int, str]:
        """TTL 조회"""
        try:
            cache_key = self._make_key(key)
            with self._lock:
                item = self._data.get(cache_key)
                if item is None:
                    return Success(-2)  # 키가 존재하지 않음
                if item.expires_at is None:
                    return Success(-1)  # 키가 존재하지만 TTL이 설정되지 않음
                remaining = int(item.expires_at - time.time())
                return Success(max(0, remaining))
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 TTL 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def refresh_ttl(self, key: str, ttl: int = None) -> Result[None, str]:
        """TTL 갱신 - 지정된 TTL로 갱신하거나 원래 TTL로 재설정"""
        try:
            cache_key = self._make_key(key)
            # TTL=0일 때는 validate하지 않음 (즉시 만료용)
            validated_ttl = (
                self._validate_ttl(ttl) if ttl is not None and ttl != 0 else ttl
            )
            with self._lock:
                item = self._data.get(cache_key)
                if item is None:
                    return Failure("키가 존재하지 않음")

                # TTL이 지정되지 않은 경우, 원래 TTL을 사용
                if validated_ttl is None:
                    if item.expires_at is None:
                        return Success(None)  # 원래 TTL이 없으면 변경 없음
                    # 원래 TTL 계산
                    original_ttl = int(item.expires_at - item.created_at)
                    validated_ttl = original_ttl

                # TTL 갱신
                if validated_ttl is not None and validated_ttl >= 0:
                    if validated_ttl == 0:
                        # TTL=0: 즉시 만료
                        item.expires_at = (
                            time.time() - 1
                        )  # 과거 시간으로 설정하여 즉시 만료
                    else:
                        # TTL>0: 지정된 시간 후 만료
                        item.expires_at = time.time() + validated_ttl
                    heapq.heappush(self._ttl_heap, (item.expires_at, cache_key))
                else:
                    item.expires_at = None  # TTL 제거

                return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 TTL 갱신 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def persist(self, key: str) -> Result[None, str]:
        """TTL 제거 - 키를 영구적으로 만듦"""
        try:
            cache_key = self._make_key(key)
            with self._lock:
                item = self._data.get(cache_key)
                if item is None:
                    return Failure("키가 존재하지 않음")

                item.expires_at = None  # TTL 제거
                return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 PERSIST 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def clear(self) -> Result[None, str]:
        """모든 키 삭제"""
        try:
            with self._lock:
                if self.namespace:
                    keys_to_delete = []
                    prefix = f"{self.namespace}:"
                    for key in self._data.keys():
                        if key.startswith(prefix):
                            keys_to_delete = keys_to_delete + [key]
                    for key in keys_to_delete:
                        self._remove_item(key)
                else:
                    self._data = {}
                    self._access_order = OrderedDict()
                    self._frequency = {}
                    self._insertion_order = []
                    self._ttl_heap = []
                    self._current_size = 0
                    self._current_memory = 0
                return Success(None)
        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 캐시 CLEAR 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    def _make_key(self, key: str) -> str:
        """네임스페이스를 포함한 키 생성"""
        if hasattr(self.config, "namespace") and self.config.namespace:
            return f"{self.config.namespace}:{key}"
        return key

    def _validate_ttl(self, ttl: int) -> int:
        """TTL 유효성 검증"""
        if ttl is None:
            return None
        if ttl < 0:
            return None
        if ttl == 0:
            return 0  # TTL 0은 즉시 만료를 의미
        if hasattr(self.config, "min_ttl") and ttl < self.config.min_ttl:
            return self.config.min_ttl
        if hasattr(self.config, "max_ttl") and ttl > self.config.max_ttl:
            return self.config.max_ttl
        return ttl

    def _ensure_space(self, needed_size: int):
        """공간 확보"""
        while (
            self._current_size >= self.config.max_size
            or self._current_memory + needed_size > self.config.memory_limit
        ):
            if not self._data:
                break
            victim_key = self._select_victim()
            if victim_key:
                self._remove_item(victim_key)
            else:
                break

    def _select_victim(self) -> Optional[str]:
        """제거할 항목 선택"""
        if not self._data:
            return None
        policy = self.config.eviction_policy.lower()
        match policy:
            case "lru":
                return self._select_lru_victim()
            case "lfu":
                return self._select_lfu_victim()
            case _:
                match policy:
                    case "fifo":
                        return self._select_fifo_victim()
                    case "ttl":
                        return self._select_ttl_victim()
                    case _:
                        return next(iter(self._data.keys()))

    def _select_lru_victim(self) -> Optional[str]:
        """LRU 희생자 선택"""
        if not self._access_order:
            return None
        return next(iter(self._access_order))

    def _select_lfu_victim(self) -> Optional[str]:
        """LFU 희생자 선택"""
        if not self._frequency:
            return None
        min_freq = min(self._frequency.values())
        for key, freq in self._frequency.items():
            if freq == min_freq:
                return key
        return None

    def _select_fifo_victim(self) -> Optional[str]:
        """FIFO 희생자 선택"""
        if not self._insertion_order:
            return None
        return self._insertion_order[0]

    def _select_ttl_victim(self) -> Optional[str]:
        """TTL 기반 희생자 선택"""
        current_time = time.time()
        for key, item in self._data.items():
            if item.expires_at and item.expires_at <= current_time:
                return key
        min_expires = None
        victim = None
        for key, item in self._data.items():
            if item.expires_at:
                if min_expires is None or item.expires_at < min_expires:
                    min_expires = item.expires_at
                    victim = key
        return victim or next(iter(self._data.keys()))

    def _remove_item(self, key: str):
        """항목 제거"""
        if key not in self._data:
            return
        item = self._data[key]
        del self._data[key]
        self._current_size = self._current_size - 1
        self._current_memory = self._current_memory - item.size
        if key in self._access_order:
            del self._access_order[key]
        if key in self._frequency:
            del self._frequency[key]
        if key in self._insertion_order:
            self._insertion_order = [i for i in self._insertion_order if i != key]

    def _update_access_tracking(self, key: str):
        """접근 추적 업데이트"""
        if key in self._access_order:
            self._access_order.move_to_end(key)
        else:
            self._access_order[key] = True
        self._frequency = {**self._frequency, key: self._frequency.get(key, 0) + 1}

    def _update_insertion_tracking(self, key: str):
        """삽입 추적 업데이트"""
        if key not in self._insertion_order:
            self._insertion_order = self._insertion_order + [key]
        self._update_access_tracking(key)

    async def _cleanup_expired_items(self):
        """만료된 항목 정리"""
        while self._connected:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                current_time = time.time()
                expired_keys = []
                with self._lock:
                    while self._ttl_heap:
                        expires_at, key = self._ttl_heap[0]
                        if expires_at <= current_time:
                            heapq.heappop(self._ttl_heap)
                            if key in self._data:
                                item = self._data[key]
                                if item.is_expired():
                                    expired_keys = expired_keys + [key]
                        else:
                            break
                    for key in expired_keys:
                        self._remove_item(key)
                    if expired_keys:
                        logger.debug(f"만료된 항목 {len(expired_keys)}개 정리")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TTL 정리 오류: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """상세 통계"""
        base_stats = super().get_stats()
        with self._lock:
            memory_stats = {
                "current_size": self._current_size,
                "max_size": self.config.max_size,
                "current_memory": self._current_memory,
                "max_memory": self.config.memory_limit,
                "eviction_policy": self.config.eviction_policy,
            }
            return {**base_stats, **memory_stats}


class LRUCache(MemoryCache):
    """LRU 전용 캐시"""

    def __init__(self, config: MemoryCacheConfig):
        config.eviction_policy = "lru"
        super().__init__(config)


class LFUCache(MemoryCache):
    """LFU 전용 캐시"""

    def __init__(self, config: MemoryCacheConfig):
        config.eviction_policy = "lfu"
        super().__init__(config)
