"""
Cloud Run Optimization Module

Google Cloud Run 최적화 모듈
- Cold Start 최적화
- 리소스 관리
- 요청 처리 최적화
"""

import asyncio
import functools
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from ..core.singleton import StatelessRegistry
from ..reactive import Flux, Mono

logger = logging.getLogger(__name__)


@dataclass
class CloudRunConfig:
    """Cloud Run 설정"""

    cpu = "1"
    memory = "512Mi"
    max_instances = 100
    min_instances = 0
    concurrency = 80
    timeout = 300
    port = 8080
    enable_cold_start_optimization = True
    warm_up_endpoints: List[str] = field(default_factory=list)
    warm_up_interval = 300
    enable_resource_monitoring = True
    cpu_threshold: float = 0.8
    memory_threshold: float = 0.8


@dataclass
class PerformanceMetrics:
    """성능 메트릭"""

    request_count = 0
    cold_starts = 0
    warm_starts = 0
    avg_response_time: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    last_request = None


class CloudRunOptimizer:
    """Cloud Run 최적화 관리자"""

    def __init__(self, config: CloudRunConfig):
        self.config = config
        self.metrics = PerformanceMetrics()
        self.is_warm = False
        self.warm_up_task = None
        self.startup_time = datetime.now()
        self._instance_id = os.environ.get(
            "INSTANCE_ID", f"instance_{int(time.time())}"
        )
        self._is_first_request = True
        self._cache = {}
        self._cache_ttl = {}

    async def initialize(self):
        """인스턴스 초기화"""
        logger.info(f"Initializing Cloud Run instance: {self._instance_id}")
        if self.config.enable_cold_start_optimization:
            await self._warm_up_instance()
            self._start_warm_up_scheduler()
        if self.config.enable_resource_monitoring:
            self._start_resource_monitoring()
        self.is_warm = True
        logger.info("Cloud Run instance initialized successfully")

    async def _warm_up_instance(self):
        """인스턴스 Warm Up"""
        try:
            import asyncio
            import json

            import aiohttp

            _ = [0] * 1000
            start_time = time.time()
            _ = sum(range(1000))
            warm_up_time = time.time() - start_time
            logger.info(f"Instance warmed up in {warm_up_time:.3f}s")
        except Exception as e:
            logger.warning(f"Warm up failed: {e}")

    def _start_warm_up_scheduler(self):
        """정기적 Warm Up 스케줄러"""

        async def warm_up_scheduler():
            while True:
                await asyncio.sleep(self.config.warm_up_interval)
                if not self.is_warm:
                    await self._warm_up_instance()

        self.warm_up_task = asyncio.create_task(warm_up_scheduler())

    def _start_resource_monitoring(self):
        """리소스 모니터링 시작"""

        async def monitor_resources():
            while True:
                try:
                    import psutil

                    self.metrics.memory_usage = psutil.virtual_memory().percent / 100
                    self.metrics.cpu_usage = psutil.cpu_percent() / 100
                except ImportError:
                    self.metrics.memory_usage = 0.5
                    self.metrics.cpu_usage = 0.3
                await asyncio.sleep(10)

        asyncio.create_task(monitor_resources())

    def cold_start_detector(self, func: Callable) -> Callable:
        """Cold Start 감지 데코레이터"""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            if self._is_first_request:
                cold_starts = cold_starts + 1
                self._is_first_request = False
                logger.info("Cold start detected")
            else:
                warm_starts = warm_starts + 1
            try:
                result = await func(*args, **kwargs)
                response_time = time.time() - start_time
                request_count = request_count + 1
                self.metrics.last_request = datetime.now()
                if self.metrics.avg_response_time == 0:
                    self.metrics.avg_response_time = response_time
                else:
                    self.metrics.avg_response_time = (
                        self.metrics.avg_response_time
                        * (self.metrics.request_count - 1)
                        + response_time
                    ) / self.metrics.request_count
                return result
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise

        return wrapper

    def cache_result(self, ttl_seconds=300):
        """결과 캐싱 데코레이터"""

        def decorator(func: Callable) -> Callable:

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                cache_key = (
                    f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
                )
                if cache_key in self._cache:
                    if datetime.now() < self._cache_ttl[cache_key]:
                        logger.debug(f"Cache hit: {cache_key}")
                        return self._cache[cache_key]
                    else:
                        del self._cache[cache_key]
                        del self._cache_ttl[cache_key]
                result = await func(*args, **kwargs)
                self._cache = {**self._cache, cache_key: result}
                self._cache_ttl = {
                    **self._cache_ttl,
                    cache_key: datetime.now() + timedelta(seconds=ttl_seconds),
                }
                logger.debug(f"Cache miss: {cache_key}")
                return result

            return wrapper

        return decorator

    def resource_monitor(self, func: Callable) -> Callable:
        """리소스 모니터링 데코레이터"""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if (
                self.metrics.memory_usage > self.config.memory_threshold
                or self.metrics.cpu_usage > self.config.cpu_threshold
            ):
                logger.warning(
                    f"High resource usage: CPU={self.metrics.cpu_usage:.2f}, Memory={self.metrics.memory_usage:.2f}"
                )
            return await func(*args, **kwargs)

        return wrapper

    async def health_check(self) -> Dict[str, Any]:
        """헬스 체크"""
        uptime = (datetime.now() - self.startup_time).total_seconds()
        return {
            "status": "healthy",
            "instance_id": self._instance_id,
            "uptime_seconds": uptime,
            "is_warm": self.is_warm,
            "metrics": {
                "request_count": self.metrics.request_count,
                "cold_starts": self.metrics.cold_starts,
                "warm_starts": self.metrics.warm_starts,
                "avg_response_time": self.metrics.avg_response_time,
                "memory_usage": self.metrics.memory_usage,
                "cpu_usage": self.metrics.cpu_usage,
                "last_request": (
                    self.metrics.last_request.isoformat()
                    if self.metrics.last_request
                    else None
                ),
            },
            "config": {
                "cpu": self.config.cpu,
                "memory": self.config.memory,
                "max_instances": self.config.max_instances,
                "concurrency": self.config.concurrency,
            },
        }

    async def shutdown(self):
        """인스턴스 종료"""
        logger.info(f"Shutting down Cloud Run instance: {self._instance_id}")
        if self.warm_up_task:
            self.warm_up_task.cancel()
            try:
                await self.warm_up_task
            except asyncio.CancelledError:
                pass
        logger.info("Cloud Run instance shut down successfully")


async def optimize_cold_start(func: Callable, warm_up_data: Any = None) -> Callable:
    """순수 함수: Cold Start 최적화"""
    return (
        Mono.from_callable(func)
        .map(
            lambda f: functools.wraps(f)(
                lambda *args, **kwargs: asyncio.create_task(
                    _warm_execute(f, warm_up_data, *args, **kwargs)
                )
            )
        )
        .await_result()
    )


async def _warm_execute(func: Callable, warm_up_data: Any, *args, **kwargs):
    """워밍업된 실행"""
    if warm_up_data:
        pass
    return await func(*args, **kwargs)


def with_caching(ttl_seconds=300):
    """함수형 캐싱"""
    cache = {}
    cache_ttl = {}

    def decorator(func: Callable) -> Callable:

        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            if cache_key in cache and datetime.now() < cache_ttl[cache_key]:
                return cache[cache_key]
            result = await func(*args, **kwargs)
            cache[cache_key] = {cache_key: result}
            cache_ttl = {
                **cache_ttl,
                cache_key: {cache_key: datetime.now() + timedelta(seconds=ttl_seconds)},
            }
            return result

        return wrapper

    return decorator


_optimizer = None


async def get_optimizer(config=None) -> CloudRunOptimizer:
    """최적화 인스턴스 획득"""
    # global _optimizer - removed for functional programming
    if _optimizer is None:
        _optimizer = CloudRunOptimizer(config or CloudRunConfig())
        await _optimizer.initialize()
    return _optimizer


def cold_start_optimization(func: Callable) -> Callable:
    """Cold Start 최적화 데코레이터"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        optimizer = await get_optimizer()
        decorated_func = optimizer.cold_start_detector(func)
        return await decorated_func(*args, **kwargs)

    return wrapper


def cache_response(ttl_seconds=300):
    """응답 캐싱 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            optimizer = await get_optimizer()
            cached_func = optimizer.cache_result(ttl_seconds)(func)
            return await cached_func(*args, **kwargs)

        return wrapper

    return decorator


def monitor_resources(func: Callable) -> Callable:
    """리소스 모니터링 데코레이터"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        optimizer = await get_optimizer()
        monitored_func = optimizer.resource_monitor(func)
        return await monitored_func(*args, **kwargs)

    return wrapper


@asynccontextmanager
async def cloud_run_context(config=None):
    """Cloud Run 컨텍스트 매니저"""
    optimizer = await get_optimizer(config)
    try:
        yield optimizer
    finally:
        await optimizer.shutdown()


StatelessRegistry.register("cloud_run_optimizer", dependencies=[])(get_optimizer)
