"""
LLM 응답 캐싱 시스템

LLM 호출 결과를 캐싱하여 성능을 향상시키고 비용을 절감하는 모듈입니다.
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import asyncio

from rfs.core.result import Result, Success, Failure
from rfs.core.config import get_config
from rfs.hof.core import pipe, curry
from rfs.hof.collections import first


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def is_expired(self) -> bool:
        """캐시 만료 여부 확인"""
        if self.ttl_seconds is None:
            return False
        
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time
    
    def update_access(self):
        """접근 정보 업데이트"""
        self.accessed_at = datetime.now()
        self.access_count += 1


class CacheBackend(ABC):
    """캐시 백엔드 인터페이스"""
    
    @abstractmethod
    async def get(self, key: str) -> Result[Optional[CacheEntry], str]:
        """캐시 엔트리 조회"""
        pass
    
    @abstractmethod
    async def set(self, key: str, entry: CacheEntry) -> Result[None, str]:
        """캐시 엔트리 저장"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> Result[bool, str]:
        """캐시 엔트리 삭제"""
        pass
    
    @abstractmethod
    async def clear(self) -> Result[int, str]:
        """모든 캐시 엔트리 삭제"""
        pass
    
    @abstractmethod
    async def keys(self, pattern: Optional[str] = None) -> Result[List[str], str]:
        """캐시 키 목록 조회"""
        pass


class MemoryCacheBackend(CacheBackend):
    """메모리 기반 캐시 백엔드"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Result[Optional[CacheEntry], str]:
        """캐시 엔트리 조회"""
        try:
            async with self._lock:
                entry = self._cache.get(key)
                
                if entry is None:
                    return Success(None)
                
                # 만료 확인
                if entry.is_expired():
                    del self._cache[key]
                    return Success(None)
                
                # 접근 정보 업데이트
                entry.update_access()
                return Success(entry)
                
        except Exception as e:
            return Failure(f"캐시 조회 실패: {str(e)}")
    
    async def set(self, key: str, entry: CacheEntry) -> Result[None, str]:
        """캐시 엔트리 저장"""
        try:
            async with self._lock:
                # 크기 제한 확인
                if len(self._cache) >= self.max_size and key not in self._cache:
                    await self._evict_lru()
                
                self._cache[key] = entry
                return Success(None)
                
        except Exception as e:
            return Failure(f"캐시 저장 실패: {str(e)}")
    
    async def delete(self, key: str) -> Result[bool, str]:
        """캐시 엔트리 삭제"""
        try:
            async with self._lock:
                if key in self._cache:
                    del self._cache[key]
                    return Success(True)
                return Success(False)
                
        except Exception as e:
            return Failure(f"캐시 삭제 실패: {str(e)}")
    
    async def clear(self) -> Result[int, str]:
        """모든 캐시 엔트리 삭제"""
        try:
            async with self._lock:
                count = len(self._cache)
                self._cache.clear()
                return Success(count)
                
        except Exception as e:
            return Failure(f"캐시 초기화 실패: {str(e)}")
    
    async def keys(self, pattern: Optional[str] = None) -> Result[List[str], str]:
        """캐시 키 목록 조회"""
        try:
            async with self._lock:
                keys = list(self._cache.keys())
                
                if pattern:
                    # 간단한 패턴 매칭 (와일드카드 지원)
                    import fnmatch
                    keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
                
                return Success(keys)
                
        except Exception as e:
            return Failure(f"키 목록 조회 실패: {str(e)}")
    
    async def _evict_lru(self):
        """LRU 방식으로 캐시 엔트리 제거"""
        if not self._cache:
            return
        
        # 가장 오래전에 접근된 엔트리 찾기
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].accessed_at
        )
        del self._cache[oldest_key]


class LLMResponseCache:
    """LLM 응답 캐싱 시스템
    
    LLM 호출 결과를 캐싱하여 동일한 요청에 대해 빠른 응답을 제공합니다.
    """
    
    def __init__(self, 
                 backend: Optional[CacheBackend] = None,
                 default_ttl: int = 3600,
                 enable_compression: bool = True):
        """캐시 시스템 초기화
        
        Args:
            backend: 캐시 백엔드 (기본값: MemoryCacheBackend)
            default_ttl: 기본 TTL (초)
            enable_compression: 응답 압축 활성화 여부
        """
        self.backend = backend or MemoryCacheBackend()
        self.default_ttl = default_ttl
        self.enable_compression = enable_compression
        
        # 캐시 통계
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        self._stats_lock = asyncio.Lock()
    
    def _generate_cache_key(self, 
                           provider: str,
                           model: str, 
                           prompt: str,
                           **kwargs) -> str:
        """캐시 키 생성
        
        Args:
            provider: LLM 제공자
            model: 모델명
            prompt: 프롬프트
            **kwargs: 추가 파라미터
            
        Returns:
            str: 캐시 키
        """
        # 캐시 키에 포함할 데이터
        cache_data = {
            "provider": provider,
            "model": model,
            "prompt": prompt,
            **kwargs
        }
        
        # JSON 직렬화 후 해시 생성
        cache_json = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(cache_json.encode()).hexdigest()
    
    async def get(self, 
                  provider: str,
                  model: str,
                  prompt: str,
                  **kwargs) -> Result[Optional[Any], str]:
        """캐시된 응답 조회
        
        Args:
            provider: LLM 제공자
            model: 모델명
            prompt: 프롬프트
            **kwargs: 추가 파라미터
            
        Returns:
            Result[Optional[Any], str]: 캐시된 응답 또는 None
        """
        try:
            cache_key = self._generate_cache_key(provider, model, prompt, **kwargs)
            entry_result = await self.backend.get(cache_key)
            
            if entry_result.is_failure():
                await self._update_stats("errors")
                return entry_result
            
            entry = entry_result.unwrap()
            
            if entry is None:
                await self._update_stats("misses")
                return Success(None)
            
            await self._update_stats("hits")
            
            # 압축 해제 (필요한 경우)
            value = entry.value
            if self.enable_compression and entry.metadata.get("compressed"):
                value = await self._decompress(value)
            
            return Success(value)
            
        except Exception as e:
            await self._update_stats("errors")
            return Failure(f"캐시 조회 실패: {str(e)}")
    
    async def set(self, 
                  provider: str,
                  model: str,
                  prompt: str,
                  response: Any,
                  ttl: Optional[int] = None,
                  **kwargs) -> Result[None, str]:
        """응답 캐시 저장
        
        Args:
            provider: LLM 제공자
            model: 모델명
            prompt: 프롬프트
            response: 응답 데이터
            ttl: TTL (초, None이면 기본값 사용)
            **kwargs: 추가 파라미터
            
        Returns:
            Result[None, str]: 성공 시 None, 실패 시 에러 메시지
        """
        try:
            cache_key = self._generate_cache_key(provider, model, prompt, **kwargs)
            actual_ttl = ttl if ttl is not None else self.default_ttl
            
            # 응답 압축 (필요한 경우)
            value = response
            metadata = {"compressed": False}
            
            if self.enable_compression:
                compressed_value = await self._compress(response)
                if compressed_value is not None:
                    value = compressed_value
                    metadata["compressed"] = True
            
            # 캐시 엔트리 생성
            now = datetime.now()
            entry = CacheEntry(
                key=cache_key,
                value=value,
                created_at=now,
                accessed_at=now,
                ttl_seconds=actual_ttl,
                metadata=metadata
            )
            
            # 백엔드에 저장
            result = await self.backend.set(cache_key, entry)
            
            if result.is_success():
                await self._update_stats("sets")
            else:
                await self._update_stats("errors")
            
            return result
            
        except Exception as e:
            await self._update_stats("errors")
            return Failure(f"캐시 저장 실패: {str(e)}")
    
    async def delete(self, 
                     provider: str,
                     model: str,
                     prompt: str,
                     **kwargs) -> Result[bool, str]:
        """캐시된 응답 삭제
        
        Args:
            provider: LLM 제공자
            model: 모델명
            prompt: 프롬프트
            **kwargs: 추가 파라미터
            
        Returns:
            Result[bool, str]: 삭제 성공 여부
        """
        try:
            cache_key = self._generate_cache_key(provider, model, prompt, **kwargs)
            result = await self.backend.delete(cache_key)
            
            if result.is_success():
                await self._update_stats("deletes")
            else:
                await self._update_stats("errors")
            
            return result
            
        except Exception as e:
            await self._update_stats("errors")
            return Failure(f"캐시 삭제 실패: {str(e)}")
    
    async def clear_provider_cache(self, provider: str) -> Result[int, str]:
        """특정 제공자의 캐시 삭제
        
        Args:
            provider: LLM 제공자
            
        Returns:
            Result[int, str]: 삭제된 엔트리 수
        """
        try:
            keys_result = await self.backend.keys(f"{provider}*")
            
            if keys_result.is_failure():
                return keys_result
            
            keys = keys_result.unwrap()
            deleted_count = 0
            
            for key in keys:
                delete_result = await self.backend.delete(key)
                if delete_result.is_success() and delete_result.unwrap():
                    deleted_count += 1
            
            return Success(deleted_count)
            
        except Exception as e:
            return Failure(f"제공자 캐시 삭제 실패: {str(e)}")
    
    async def get_cache_stats(self) -> Result[Dict[str, Any], str]:
        """캐시 통계 조회
        
        Returns:
            Result[Dict[str, Any], str]: 캐시 통계
        """
        try:
            async with self._stats_lock:
                stats = self._stats.copy()
            
            # 히트율 계산
            total_requests = stats["hits"] + stats["misses"]
            hit_rate = (stats["hits"] / total_requests * 100) if total_requests > 0 else 0
            
            # 백엔드 키 수 조회
            keys_result = await self.backend.keys()
            key_count = len(keys_result.unwrap()) if keys_result.is_success() else 0
            
            return Success({
                "hits": stats["hits"],
                "misses": stats["misses"],
                "sets": stats["sets"],
                "deletes": stats["deletes"],
                "errors": stats["errors"],
                "hit_rate": hit_rate,
                "total_keys": key_count
            })
            
        except Exception as e:
            return Failure(f"캐시 통계 조회 실패: {str(e)}")
    
    async def cleanup_expired(self) -> Result[int, str]:
        """만료된 캐시 엔트리 정리
        
        Returns:
            Result[int, str]: 삭제된 엔트리 수
        """
        try:
            keys_result = await self.backend.keys()
            
            if keys_result.is_failure():
                return keys_result
            
            keys = keys_result.unwrap()
            deleted_count = 0
            
            for key in keys:
                entry_result = await self.backend.get(key)
                
                if entry_result.is_success() and entry_result.unwrap():
                    entry = entry_result.unwrap()
                    if entry.is_expired():
                        delete_result = await self.backend.delete(key)
                        if delete_result.is_success() and delete_result.unwrap():
                            deleted_count += 1
            
            return Success(deleted_count)
            
        except Exception as e:
            return Failure(f"만료된 캐시 정리 실패: {str(e)}")
    
    async def _update_stats(self, stat_type: str):
        """통계 업데이트"""
        async with self._stats_lock:
            self._stats[stat_type] += 1
    
    async def _compress(self, data: Any) -> Optional[Any]:
        """데이터 압축"""
        try:
            import pickle
            import zlib
            
            # 데이터를 직렬화 후 압축
            serialized = pickle.dumps(data)
            original_size = len(serialized)
            
            # 작은 데이터는 압축하지 않음
            if original_size < 1024:
                return None
            
            compressed = zlib.compress(serialized)
            
            # 압축 효과가 미미하면 압축하지 않음
            if len(compressed) >= original_size * 0.8:
                return None
            
            return compressed
            
        except Exception:
            return None
    
    async def _decompress(self, compressed_data: Any) -> Any:
        """데이터 압축 해제"""
        try:
            import pickle
            import zlib
            
            decompressed = zlib.decompress(compressed_data)
            return pickle.loads(decompressed)
            
        except Exception as e:
            raise ValueError(f"압축 해제 실패: {str(e)}")


# 데코레이터와 HOF 유틸리티
@curry
async def with_cache(
    cache: LLMResponseCache,
    provider: str,
    model: str,
    ttl: Optional[int],
    func,
    prompt: str,
    **kwargs
):
    """캐시와 함께 LLM 함수 실행
    
    사용법:
        cache_openai = with_cache(cache, "openai", "gpt-4", 3600)
        result = await cache_openai(llm_function, "프롬프트", param=value)
    """
    # 캐시 확인
    cached_result = await cache.get(provider, model, prompt, **kwargs)
    
    if cached_result.is_success() and cached_result.unwrap() is not None:
        return Success(cached_result.unwrap())
    
    # 캐시 미스 - 실제 함수 호출
    try:
        result = await func(prompt, **kwargs)
        
        # 성공한 경우만 캐시에 저장
        if hasattr(result, 'is_success') and result.is_success():
            response_data = result.unwrap()
            await cache.set(provider, model, prompt, response_data, ttl, **kwargs)
        
        return result
        
    except Exception as e:
        return Failure(str(e))


def cached_llm_call(provider: str, 
                   model: str, 
                   ttl: Optional[int] = None,
                   cache_instance: Optional[LLMResponseCache] = None):
    """LLM 호출 캐싱 데코레이터
    
    사용법:
        @cached_llm_call("openai", "gpt-4", ttl=3600)
        async def generate_text(prompt: str, **kwargs):
            # LLM 호출 로직
            pass
    """
    def decorator(func):
        nonlocal cache_instance
        if cache_instance is None:
            cache_instance = get_response_cache()
        
        cache_func = with_cache(cache_instance, provider, model, ttl)
        
        async def wrapper(prompt: str, **kwargs):
            return await cache_func(func, prompt, **kwargs)
        
        return wrapper
    return decorator


# 전역 캐시 인스턴스
_global_response_cache: Optional[LLMResponseCache] = None


def get_response_cache() -> LLMResponseCache:
    """전역 응답 캐시 조회 또는 생성"""
    global _global_response_cache
    
    if _global_response_cache is None:
        # 설정에서 캐시 구성 로드
        cache_config = get_config("llm.cache", {})
        
        backend_type = cache_config.get("backend", "memory")
        default_ttl = cache_config.get("default_ttl", 3600)
        enable_compression = cache_config.get("compression", True)
        
        # 백엔드 생성
        if backend_type == "memory":
            max_size = cache_config.get("max_size", 1000)
            backend = MemoryCacheBackend(max_size)
        else:
            # 향후 Redis 등 다른 백엔드 지원
            backend = MemoryCacheBackend()
        
        _global_response_cache = LLMResponseCache(
            backend=backend,
            default_ttl=default_ttl,
            enable_compression=enable_compression
        )
    
    return _global_response_cache