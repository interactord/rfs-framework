"""
RFS Cache Decorators (RFS v4.1)

캐시 데코레이터 시스템
"""

import asyncio
import functools
import hashlib
import inspect
import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import CacheBackend, get_cache

logger = get_logger(__name__)


class CacheKeyBuilder:
    """캐시 키 생성기"""

    def __init__(self, prefix="", namespace="", separator=":"):
        self.prefix = prefix
        self.namespace = namespace
        self.separator = separator

    def build_key(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        custom_key=None,
    ) -> str:
        """캐시 키 생성"""
        if custom_key:
            return self._format_key(custom_key)
        func_name = f"{func.__module__}.{func.__qualname__}"
        args_hash = self._hash_args(args, kwargs)
        key_parts = [func_name, args_hash]
        return self._format_key(self.separator.join(key_parts))

    def _format_key(self, key: str) -> str:
        """키 포맷팅"""
        parts = []
        if self.namespace:
            parts = parts + [self.namespace]
        if self.prefix:
            parts = parts + [self.prefix]
        parts = parts + [key]
        return self.separator.join(parts)

    def _hash_args(self, args: tuple, kwargs: dict) -> str:
        """인자 해시 생성"""
        try:
            serializable_args = self._make_serializable(args)
            serializable_kwargs = self._make_serializable(kwargs)
            data = json.dumps(
                [serializable_args, serializable_kwargs],
                sort_keys=True,
                ensure_ascii=False,
            )
            return hashlib.sha256(data.encode()).hexdigest()[:16]
        except Exception as e:
            logger.warning(f"인자 해시 생성 실패: {e}")
            return hashlib.sha256(str((args, kwargs)).encode()).hexdigest()[:16]

    def _make_serializable(self, obj: Any) -> Any:
        """직렬화 가능한 객체로 변환"""
        if obj is None or type(obj).__name__ in ["str", "int", "float", "bool"]:
            return obj
        elif type(obj).__name__ in ["list", "tuple"]:
            return [self._make_serializable(item) for item in obj]
        elif type(obj).__name__ == "dict":
            return {str(k): self._make_serializable(v) for k, v in obj.items()}
        elif hasattr(obj, "__dict__"):
            return {
                "__class__": obj.__class__.__name__,
                "__data__": self._make_serializable(obj.__dict__),
            }
        else:
            return str(obj)


def cached(
    ttl=None,
    key: Optional[Union[str, Callable]] = None,
    cache_name=None,
    namespace=None,
    condition=None,
    unless=None,
    version=None,
):
    """캐시 데코레이터

    Args:
        ttl: TTL (초)
        key: 커스텀 키 또는 키 생성 함수
        cache_name: 사용할 캐시 인스턴스 이름
        namespace: 네임스페이스
        condition: 캐시 조건 함수
        unless: 캐시 제외 조건 함수
        version: 캐시 버전
    """

    def decorator(func: Callable) -> Callable:
        key_builder = CacheKeyBuilder(namespace=namespace or "")
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                cache_backend = get_cache(cache_name)
                if not cache_backend:
                    logger.warning(f"캐시를 찾을 수 없습니다: {cache_name}")
                    return await func(*args, **kwargs)
                if condition and (not condition(*args, **kwargs)):
                    return await func(*args, **kwargs)
                if unless and unless(*args, **kwargs):
                    return await func(*args, **kwargs)
                cache_key = _generate_cache_key(
                    key_builder, func, args, kwargs, key, version
                )
                result = await cache_backend.get(cache_key)
                if result.is_success():
                    cached_value = result.unwrap()
                    if cached_value is not None:
                        logger.debug(f"캐시 히트: {cache_key}")
                        return cached_value
                value = await func(*args, **kwargs)
                if value is not None:
                    await cache_backend.set(cache_key, value, ttl)
                    logger.debug(f"캐시 저장: {cache_key}")
                return value

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):

                async def async_func(*args, **kwargs):
                    return func(*args, **kwargs)

                return asyncio.run(async_func(*args, **kwargs))

            return sync_wrapper

    return decorator


def cache_result(
    ttl=None,
    key_func=None,
    cache_name=None,
):
    """결과 캐싱 데코레이터 (간단 버전)"""
    return cached(ttl=ttl, key=key_func, cache_name=cache_name)


def invalidate_cache(
    key: Optional[Union[str, Callable]] = None,
    cache_name=None,
    namespace=None,
    pattern=None,
):
    """캐시 무효화 데코레이터"""

    def decorator(func: Callable) -> Callable:
        key_builder = CacheKeyBuilder(namespace=namespace or "")
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                cache_backend = get_cache(cache_name)
                if cache_backend:
                    if pattern:
                        await _invalidate_pattern(cache_backend, pattern)
                    else:
                        cache_key = _generate_cache_key(
                            key_builder, func, args, kwargs, key
                        )
                        await cache_backend.delete(cache_key)
                        logger.debug(f"캐시 무효화: {cache_key}")
                return result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):

                async def async_func(*args, **kwargs):
                    result = func(*args, **kwargs)
                    cache_backend = get_cache(cache_name)
                    if cache_backend:
                        if pattern:
                            await _invalidate_pattern(cache_backend, pattern)
                        else:
                            cache_key = _generate_cache_key(
                                key_builder, func, args, kwargs, key
                            )
                            await cache_backend.delete(cache_key)
                    return result

                return asyncio.run(async_func(*args, **kwargs))

            return sync_wrapper

    return decorator


def cache_key(func: Callable) -> Callable:
    """캐시 키 생성 함수 데코레이터"""

    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.__is_cache_key_func__ = True
    return wrapper


def cache_ttl(seconds: int):
    """TTL 설정 데코레이터"""

    def decorator(func: Callable) -> Callable:
        func.__cache_ttl__ = seconds
        return func

    return decorator


def cache_namespace(namespace: str):
    """네임스페이스 설정 데코레이터"""

    def decorator(func: Callable) -> Callable:
        func.__cache_namespace__ = namespace
        return func

    return decorator


def _generate_cache_key(
    key_builder: CacheKeyBuilder,
    func: Callable,
    args: tuple,
    kwargs: dict,
    custom_key: Optional[Union[str, Callable]] = None,
    version=None,
) -> str:
    """캐시 키 생성"""
    if callable(custom_key):
        if hasattr(custom_key, "__is_cache_key_func__"):
            generated_key = custom_key(*args, **kwargs)
        else:
            generated_key = custom_key(*args, **kwargs)
    elif type(custom_key).__name__ == "str":
        generated_key = custom_key
    else:
        generated_key = None
    base_key = key_builder.build_key(func, args, kwargs, generated_key)
    if version:
        base_key = f"{base_key}:v{version}"
    return base_key


async def _invalidate_pattern(cache_backend: CacheBackend, pattern: str):
    """패턴 기반 캐시 무효화"""
    try:
        if hasattr(cache_backend, "redis") and cache_backend.redis:
            keys = await cache_backend.redis.keys(pattern)
            if keys:
                await cache_backend.redis.delete(*keys)
                logger.debug(f"패턴 캐시 무효화: {pattern} ({len(keys)}개)")
        else:
            logger.warning(f"패턴 무효화를 지원하지 않는 캐시: {type(cache_backend)}")
    except Exception as e:
        logger.error(f"패턴 캐시 무효화 실패: {e}")


def cached_method(
    ttl=None,
    key_attr=None,
    cache_name=None,
):
    """메서드 캐시 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            cache_backend = get_cache(cache_name)
            if not cache_backend:
                return await func(self, *args, **kwargs)
            instance_id = getattr(self, key_attr) if key_attr else id(self)
            key_builder = CacheKeyBuilder(prefix=f"method_{instance_id}")
            cache_key = key_builder.build_key(func, args, kwargs)
            result = await cache_backend.get(cache_key)
            if result.is_success():
                cached_value = result.unwrap()
                if cached_value is not None:
                    return cached_value
            value = await func(self, *args, **kwargs)
            if value is not None:
                await cache_backend.set(cache_key, value, ttl)
            return value

        return wrapper

    return decorator


def cache_warming(warm_keys: List[tuple], ttl=None, cache_name=None):
    """캐시 워밍 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            cache_backend = get_cache(cache_name)
            if cache_backend:
                key_builder = CacheKeyBuilder()
                for warm_args, warm_kwargs in warm_keys:
                    try:
                        warm_result = await func(*warm_args, **warm_kwargs)
                        warm_key = key_builder.build_key(func, warm_args, warm_kwargs)
                        await cache_backend.set(warm_key, warm_result, ttl)
                        logger.debug(f"캐시 워밍: {warm_key}")
                    except Exception as e:
                        logger.warning(f"캐시 워밍 실패: {e}")
            return result

        return wrapper

    return decorator


def cache_stats(cache_name=None):
    """캐시 통계 추적 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = await func(*args, **kwargs)
                cache_backend = get_cache(cache_name)
                if cache_backend and hasattr(cache_backend, "_stats"):
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.debug(f"함수 실행 시간: {func.__name__} - {duration:.3f}s")
                return result
            except Exception as e:
                logger.error(f"함수 실행 실패: {func.__name__} - {e}")
                raise

        return wrapper

    return decorator
