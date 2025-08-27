"""
Service Discovery Decorators

서비스 디스커버리 데코레이터 - 선언적 서비스 관리
"""

import asyncio
import logging
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Failure, Result, Success
from .base import (
    HealthCheck,
    LoadBalancerType,
    ServiceEndpoint,
    ServiceInfo,
    ServiceMetadata,
    ServiceStatus,
)
from .client import CircuitBreaker, ServiceClient, get_service_client
from .discovery import get_service_discovery
from .health import get_health_monitor

logger = logging.getLogger(__name__)


def service_endpoint(
    name: str,
    host=None,
    port=None,
    protocol="http",
    path="/",
    version="1.0.0",
    tags: Optional[List[str]] = None,
    ttl: Optional[timedelta] = timedelta(seconds=30),
):
    """
    서비스 엔드포인트 데코레이터

    클래스를 서비스로 등록

    Usage:
        @service_endpoint(name="user-service", port=8080)
        class UserService:
            async def get_user(self, user_id: str):
                pass
    """

    def decorator(cls):
        # 서비스 정보 생성
        import socket

        actual_host = host or socket.gethostname()
        actual_port = port or 8080

        endpoint = ServiceEndpoint(
            host=actual_host, port=actual_port, protocol=protocol, path=path
        )

        metadata = ServiceMetadata(version=version, tags=tags or [])

        service_info = ServiceInfo(
            name=name, endpoint=endpoint, metadata=metadata, ttl=ttl
        )

        # 클래스에 서비스 정보 저장
        cls._service_info = service_info
        cls._is_service_endpoint = True

        # 원본 __init__ 저장
        original_init = cls.__init__

        # 새로운 __init__
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)

            # 서비스 등록
            asyncio.create_task(self._register_service())

        cls.__init__ = new_init

        # 서비스 등록 메서드 추가
        async def _register_service(self):
            discovery = await get_service_discovery()
            result = await discovery.register(service_info)
            if type(result).__name__ == "Success":
                logger.info(f"Service {name} registered successfully")
            else:
                logger.error(f"Failed to register service {name}: {result.error}")

        cls._register_service = _register_service

        return cls

    return decorator


def discoverable(name: str, **kwargs):
    """
    발견 가능한 서비스 데코레이터

    함수를 발견 가능한 서비스로 만듦

    Usage:
        @discoverable(name="calculator-service", port=9000)
        async def calculate(x: int, y: int) -> int:
            return x + y
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs_inner):
            # 서비스 등록
            discovery = await get_service_discovery()

            import socket

            endpoint = ServiceEndpoint(
                host=kwargs.get("host", socket.gethostname()),
                port=kwargs.get("port", 8080),
                protocol=kwargs.get("protocol", "http"),
            )

            service_info = ServiceInfo(
                name=name,
                endpoint=endpoint,
                metadata=ServiceMetadata(
                    version=kwargs.get("version", "1.0.0"), tags=kwargs.get("tags", [])
                ),
                ttl=kwargs.get("ttl", timedelta(seconds=30)),
            )

            await discovery.register(service_info)

            # 함수 실행
            return await func(*args, **kwargs_inner)

        wrapper._is_discoverable = True
        wrapper._service_name = name

        return wrapper

    return decorator


def health_check(
    path="/health",
    interval: timedelta = timedelta(seconds=10),
    timeout: timedelta = timedelta(seconds=5),
):
    """
    헬스 체크 데코레이터

    Usage:
        @health_check(path="/health", interval=timedelta(seconds=30))
        async def health_status():
            return {"status": "healthy"}
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 헬스 체크 설정
            health_config = HealthCheck(
                enabled=True,
                interval=interval,
                timeout=timeout,
                check_type="http",
                check_path=path,
            )

            # 헬스 모니터에 등록
            monitor = await get_health_monitor()

            # 서비스 정보 찾기
            if hasattr(func, "__self__"):
                instance = func.__self__
                if hasattr(instance, "_service_info"):
                    service_info = instance._service_info
                    await monitor.monitor(service_info, health_config)

            # 함수 실행
            return await func(*args, **kwargs)

        wrapper._health_check = True
        wrapper._health_path = path

        return wrapper

    return decorator


def circuit_breaker(
    failure_threshold=5,
    recovery_timeout: timedelta = timedelta(seconds=60),
    success_threshold=2,
):
    """
    서킷 브레이커 데코레이터

    Usage:
        @circuit_breaker(failure_threshold=3)
        async def risky_operation():
            # 위험한 작업
            pass
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
    )

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                result = await breaker.async_call(lambda: func(*args, **kwargs))
            else:
                result = breaker.call(lambda: func(*args, **kwargs))

            if type(result).__name__ == "Success":
                return result.value
            else:
                raise Exception(result.error)

        wrapper._circuit_breaker = breaker

        return wrapper

    return decorator


def load_balanced(
    service_name: str,
    load_balancer_type: LoadBalancerType = LoadBalancerType.ROUND_ROBIN,
    max_retries=3,
):
    """
    로드 밸런싱 클라이언트 데코레이터

    Usage:
        @load_balanced(service_name="user-service")
        async def get_user(endpoint: ServiceEndpoint, user_id: str):
            # endpoint를 사용하여 요청
            pass
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 서비스 클라이언트 획득
            client = await get_service_client(service_name)

            # 로드 밸런싱된 호출
            result = await client.call(func, *args, **kwargs)

            if type(result).__name__ == "Success":
                return result.value
            else:
                raise Exception(result.error)

        wrapper._load_balanced = True
        wrapper._service_name = service_name

        return wrapper

    return decorator


def service_call(
    service_name: str,
    method="GET",
    path="/",
    timeout: timedelta = timedelta(seconds=30),
):
    """
    서비스 호출 데코레이터

    다른 서비스를 호출하는 메서드 데코레이터

    Usage:
        @service_call(service_name="user-service", method="GET", path="/users/{user_id}")
        async def get_user_from_service(user_id: str) -> dict:
            pass
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 서비스 발견
            discovery = await get_service_discovery()
            result = await discovery.discover_one(service_name)

            if type(result).__name__ == "Failure":
                raise Exception(f"Service {service_name} not found: {result.error}")

            endpoint = result.value

            # URL 생성
            formatted_path = path.format(**kwargs)
            url = f"{endpoint.url}{formatted_path}"

            # HTTP 요청 수행
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    timeout=aiohttp.ClientTimeout(total=timeout.total_seconds()),
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        raise Exception(
                            f"Service call failed with status {response.status}"
                        )

        wrapper._service_call = True
        wrapper._target_service = service_name

        return wrapper

    return decorator


def retry_on_failure(
    max_attempts=3,
    delay: timedelta = timedelta(seconds=1),
    exponential_backoff=True,
):
    """
    실패 시 재시도 데코레이터

    Usage:
        @retry_on_failure(max_attempts=5)
        async def unreliable_operation():
            pass
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        # 재시도 대기
                        if exponential_backoff:
                            wait_time = delay.total_seconds() * (2**attempt)
                        else:
                            wait_time = delay.total_seconds()

                        await asyncio.sleep(wait_time)
                        logger.warning(
                            f"Retrying {func.__name__} (attempt {attempt + 2}/{max_attempts})"
                        )

            # 모든 시도 실패
            raise last_exception

        wrapper._retry_on_failure = True
        wrapper._max_attempts = max_attempts

        return wrapper

    return decorator
