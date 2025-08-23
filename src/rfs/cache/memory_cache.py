"""
RFS Memory Cache (RFS v4.1)

메모리 캐시 구현
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from threading import RLock
import heapq

from ..core.result import Result, Success, Failure
from ..core.enhanced_logging import get_logger
from .base import CacheBackend, CacheConfig

logger = get_logger(__name__)


@dataclass
class MemoryCacheConfig(CacheConfig):
    """메모리 캐시 설정"""
    # 메모리 캐시 전용 설정
    max_size: int = 1000  # 최대 항목 수
    eviction_policy: str = "lru"  # lru, lfu, fifo, ttl
    
    # TTL 관리
    cleanup_interval: int = 300  # TTL 정리 주기 (초)
    lazy_expiration: bool = True  # 지연 만료 (접근 시 확인)
    
    # 메모리 제한
    memory_limit: int = 100 * 1024 * 1024  # 100MB
    estimate_size: bool = True  # 크기 추정 활성화
    
    # 통계
    enable_detailed_stats: bool = True


class CacheItem:
    """캐시 항목"""
    
    def __init__(self, key: str, value: Any, ttl: int = None):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.accessed_at = self.created_at
        self.access_count = 1
        
        if ttl and ttl > 0:
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
            return 1024  # 기본값
    
    def is_expired(self) -> bool:
        """만료 확인"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self):
        """접근 시간 업데이트"""
        self.accessed_at = time.time()
        self.access_count += 1
    
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
        
        # 저장소
        self._data: Dict[str, CacheItem] = {}
        self._access_order: OrderedDict = OrderedDict()  # LRU용
        self._frequency: Dict[str, int] = {}  # LFU용
        self._insertion_order: List[str] = []  # FIFO용
        self._ttl_heap: List[Tuple[float, str]] = []  # TTL 정리용
        
        # 동기화
        self._lock = RLock()
        
        # 통계
        self._current_size = 0
        self._current_memory = 0
        
        # 정리 태스크
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> Result[None, str]:
        """캐시 초기화"""
        try:
            if self._connected:
                return Success(None)
            
            # TTL 정리 태스크 시작
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
            
            # 정리 태스크 종료
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # 데이터 정리
            with self._lock:
                self._data.clear()
                self._access_order.clear()
                self._frequency.clear()
                self._insertion_order.clear()
                self._ttl_heap.clear()
                
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
                    self._stats["misses"] += 1
                    return Success(None)
                
                # 만료 확인
                if self.config.lazy_expiration and item.is_expired():
                    self._remove_item(cache_key)
                    self._stats["misses"] += 1
                    return Success(None)
                
                # 접근 정보 업데이트
                item.touch()
                self._update_access_tracking(cache_key)
                
                self._stats["hits"] += 1
                return Success(item.value)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"메모리 캐시 GET 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def set(self, key: str, value: Any, ttl: int = None) -> Result[None, str]:
        """값 저장"""
        try:
            cache_key = self._make_key(key)
            ttl = self._validate_ttl(ttl) if ttl else None
            
            with self._lock:
                # 기존 항목 제거
                if cache_key in self._data:
                    self._remove_item(cache_key)
                
                # 새 항목 생성
                item = CacheItem(cache_key, value, ttl)
                
                # 공간 확보
                self._ensure_space(item.size)
                
                # 저장
                self._data[cache_key] = item
                self._current_size += 1
                self._current_memory += item.size
                
                # 접근 추적 업데이트
                self._update_insertion_tracking(cache_key)
                
                # TTL 힙 업데이트
                if item.expires_at:
                    heapq.heappush(self._ttl_heap, (item.expires_at, cache_key))
                
                self._stats["sets"] += 1
                return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
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
                    self._stats["deletes"] += 1
                
                return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
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
                
                # 만료 확인
                if self.config.lazy_expiration and item.is_expired():
                    self._remove_item(cache_key)
                    return Success(False)
                
                return Success(True)
            
        except Exception as e:
            self._stats["errors"] += 1
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
                
                # TTL 업데이트
                item.expires_at = time.time() + ttl
                
                # TTL 힙 업데이트
                heapq.heappush(self._ttl_heap, (item.expires_at, cache_key))
                
                return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"메모리 캐시 EXPIRE 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def ttl(self, key: str) -> Result[int, str]:
        """TTL 조회"""
        try:
            cache_key = self._make_key(key)
            
            with self._lock:
                item = self._data.get(cache_key)
                
                if item is None or item.expires_at is None:
                    return Success(-1)  # 키 없음 또는 TTL 없음
                
                remaining = int(item.expires_at - time.time())
                return Success(max(0, remaining))
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"메모리 캐시 TTL 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def clear(self) -> Result[None, str]:
        """모든 키 삭제"""
        try:
            with self._lock:
                if self.namespace:
                    # 네임스페이스 키만 삭제
                    keys_to_delete = []
                    prefix = f"{self.namespace}:"
                    
                    for key in self._data.keys():
                        if key.startswith(prefix):
                            keys_to_delete.append(key)
                    
                    for key in keys_to_delete:
                        self._remove_item(key)
                else:
                    # 모든 키 삭제
                    self._data.clear()
                    self._access_order.clear()
                    self._frequency.clear()
                    self._insertion_order.clear()
                    self._ttl_heap.clear()
                    
                    self._current_size = 0
                    self._current_memory = 0
                
                return Success(None)
            
        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"메모리 캐시 CLEAR 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    def _ensure_space(self, needed_size: int):
        """공간 확보"""
        # 크기 제한 확인
        while (self._current_size >= self.config.max_size or 
               self._current_memory + needed_size > self.config.memory_limit):
            
            if not self._data:
                break
            
            # 제거 정책에 따라 항목 제거
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
        
        if policy == "lru":
            return self._select_lru_victim()
        elif policy == "lfu":
            return self._select_lfu_victim()
        elif policy == "fifo":
            return self._select_fifo_victim()
        elif policy == "ttl":
            return self._select_ttl_victim()
        else:
            return next(iter(self._data.keys()))  # 임의 선택
    
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
        
        # 만료된 항목 우선 제거
        for key, item in self._data.items():
            if item.expires_at and item.expires_at <= current_time:
                return key
        
        # 가장 빨리 만료되는 항목
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
        
        # 데이터 제거
        del self._data[key]
        self._current_size -= 1
        self._current_memory -= item.size
        
        # 추적 정보 제거
        self._access_order.pop(key, None)
        self._frequency.pop(key, None)
        
        if key in self._insertion_order:
            self._insertion_order.remove(key)
    
    def _update_access_tracking(self, key: str):
        """접근 추적 업데이트"""
        # LRU 업데이트
        if key in self._access_order:
            self._access_order.move_to_end(key)
        else:
            self._access_order[key] = True
        
        # LFU 업데이트
        self._frequency[key] = self._frequency.get(key, 0) + 1
    
    def _update_insertion_tracking(self, key: str):
        """삽입 추적 업데이트"""
        # FIFO 업데이트
        if key not in self._insertion_order:
            self._insertion_order.append(key)
        
        # 접근 추적도 업데이트
        self._update_access_tracking(key)
    
    async def _cleanup_expired_items(self):
        """만료된 항목 정리"""
        while self._connected:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                
                current_time = time.time()
                expired_keys = []
                
                with self._lock:
                    # TTL 힙에서 만료된 항목 찾기
                    while self._ttl_heap:
                        expires_at, key = self._ttl_heap[0]
                        
                        if expires_at <= current_time:
                            heapq.heappop(self._ttl_heap)
                            if key in self._data:
                                item = self._data[key]
                                if item.is_expired():
                                    expired_keys.append(key)
                        else:
                            break
                    
                    # 만료된 항목 제거
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
                "eviction_policy": self.config.eviction_policy
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