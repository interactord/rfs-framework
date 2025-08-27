"""
Service Discovery Implementation

서비스 디스커버리 구현 - 서비스 발견 및 해결
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from ..core.result import Failure, Result, Success
from .base import (
    LoadBalancerType,
    ServiceEndpoint,
    ServiceInfo,
    ServiceMetadata,
    ServiceNotFoundError,
    ServiceStatus,
)
from .registry import ServiceRegistry, get_service_registry

logger = logging.getLogger(__name__)


class ServiceResolver:
    """
    서비스 리졸버

    서비스 이름을 엔드포인트로 해결
    """

    def __init__(self, registry=None):
        self.registry = registry or get_service_registry()
        self.cache: Dict[str, List[ServiceInfo]] = {}
        self.cache_ttl = timedelta(seconds=30)
        self.cache_timestamps = {}

    async def resolve(
        self,
        service_name: str,
        tags: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Result[List[ServiceEndpoint], str]:
        """
        서비스 이름을 엔드포인트로 해결

        Args:
            service_name: 서비스 이름
            tags: 필터링할 태그
            labels: 필터링할 레이블

        Returns:
            서비스 엔드포인트 목록
        """
        # 캐시 확인
        if self._is_cache_valid(service_name):
            services = self.cache[service_name]
        else:
            # 레지스트리에서 조회
            result = await self.registry.get_services(service_name)
            if type(result).__name__ == "Failure":
                return Failure(
                    f"Failed to resolve service {service_name}: {result.error}"
                )

            services = result.value

            # 캐시 업데이트
            self.cache = {**self.cache, service_name: services}
            self.cache_timestamps = {
                **self.cache_timestamps,
                service_name: datetime.now(),
            }

        # 필터링
        filtered_services = self._filter_services(services, tags, labels)

        # 사용 가능한 서비스만 선택
        available_services = [s for s in filtered_services if s.is_available]

        if not available_services:
            return Failure(f"No available services found for {service_name}")

        # 엔드포인트 추출
        endpoints = [s.endpoint for s in available_services]

        return Success(endpoints)

    async def resolve_one(
        self,
        service_name: str,
        tags: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        load_balancer: LoadBalancerType = LoadBalancerType.ROUND_ROBIN,
    ) -> Result[ServiceEndpoint, str]:
        """
        단일 서비스 엔드포인트 해결

        Args:
            service_name: 서비스 이름
            tags: 필터링할 태그
            labels: 필터링할 레이블
            load_balancer: 로드 밸런서 타입

        Returns:
            선택된 서비스 엔드포인트
        """
        result = await self.resolve(service_name, tags, labels)
        if type(result).__name__ == "Failure":
            return result

        endpoints = result.value

        if not endpoints:
            return Failure(f"No endpoints found for service {service_name}")

        # 로드 밸런싱
        if load_balancer == LoadBalancerType.RANDOM:
            endpoint = random.choice(endpoints)
        else:
            # 기본: 첫 번째 엔드포인트
            endpoint = endpoints[0]

        return Success(endpoint)

    def _is_cache_valid(self, service_name: str) -> bool:
        """캐시 유효성 확인"""
        if service_name not in self.cache:
            return False

        timestamp = self.cache_timestamps.get(service_name)
        if not timestamp:
            return False

        return datetime.now() - timestamp < self.cache_ttl

    def _filter_services(
        self,
        services: List[ServiceInfo],
        tags: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> List[ServiceInfo]:
        """서비스 필터링"""
        filtered = services

        if tags:
            filtered = [s for s in filtered if s.metadata.matches_tags(tags)]

        if labels:
            filtered = [s for s in filtered if s.metadata.matches_labels(labels)]

        return filtered

    def clear_cache(self, service_name=None):
        """캐시 클리어"""
        if service_name:
            cache = {k: v for k, v in cache.items() if k != "service_name, None"}
            cache_timestamps = {
                k: v for k, v in cache_timestamps.items() if k != "service_name, None"
            }
        else:
            cache = {}
            cache_timestamps = {}


class ServiceWatcher:
    """
    서비스 워처

    서비스 변경 감시 및 알림
    """

    def __init__(self, registry=None):
        self.registry = registry or get_service_registry()
        self.callbacks: Dict[str, List[Callable]] = {}
        self.watch_tasks = {}
        self._running = False

    async def start(self):
        """워처 시작"""
        self._running = True
        logger.info("ServiceWatcher started")

    async def stop(self):
        """워처 중지"""
        self._running = False

        # 모든 감시 태스크 취소
        for task in self.watch_tasks.values():
            task.cancel()

        # 태스크 완료 대기
        if self.watch_tasks:
            await asyncio.gather(*self.watch_tasks.values(), return_exceptions=True)

        watch_tasks = {}
        logger.info("ServiceWatcher stopped")

    async def watch(
        self,
        service_name: str,
        callback: Callable[[str, ServiceInfo], None],
        interval: timedelta = timedelta(seconds=5),
    ):
        """
        서비스 변경 감시

        Args:
            service_name: 감시할 서비스 이름
            callback: 변경 시 호출할 콜백
            interval: 감시 간격
        """
        # 콜백 등록
        if service_name not in self.callbacks:
            self.callbacks = {**self.callbacks, service_name: []}
        self.callbacks[service_name] = callbacks[service_name] + [callback]

        # 감시 태스크 시작
        if service_name not in self.watch_tasks:
            task = asyncio.create_task(self._watch_loop(service_name, interval))
            self.watch_tasks = {**self.watch_tasks, service_name: task}

        # 레지스트리 워치 등록
        await self.registry.watch(service_name, self._handle_registry_event)

        logger.info(f"Watching service {service_name}")

    async def unwatch(self, service_name: str):
        """서비스 감시 중지"""
        # 콜백 제거
        callbacks = {k: v for k, v in callbacks.items() if k != "service_name, None"}

        # 감시 태스크 취소
        if service_name in self.watch_tasks:
            self.watch_tasks[service_name].cancel()
            del self.watch_tasks[service_name]

        logger.info(f"Stopped watching service {service_name}")

    async def _watch_loop(self, service_name: str, interval: timedelta):
        """감시 루프"""
        previous_services = {}

        while self._running:
            try:
                # 현재 서비스 목록 조회
                result = await self.registry.get_services(service_name)
                if type(result).__name__ == "Success":
                    current_services = {s.service_id: s for s in result.value}

                    # 변경 감지
                    await self._detect_changes(
                        service_name, previous_services, current_services
                    )

                    previous_services = current_services

                # 대기
                await asyncio.sleep(interval.total_seconds())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watch loop error for {service_name}: {e}")
                await asyncio.sleep(interval.total_seconds())

    async def _detect_changes(
        self,
        service_name: str,
        previous: Dict[str, ServiceInfo],
        current: Dict[str, ServiceInfo],
    ):
        """변경 감지"""
        # 추가된 서비스
        added = set(current.keys()) - set(previous.keys())
        for service_id in added:
            await self._notify_callbacks(service_name, "added", current[service_id])

        # 제거된 서비스
        removed = set(previous.keys()) - set(current.keys())
        for service_id in removed:
            await self._notify_callbacks(service_name, "removed", previous[service_id])

        # 변경된 서비스
        for service_id in set(previous.keys()) & set(current.keys()):
            prev = previous[service_id]
            curr = current[service_id]

            # 상태 변경 확인
            if prev.status != curr.status:
                await self._notify_callbacks(service_name, "status_changed", curr)

            # 헬스 변경 확인
            if prev.health.status != curr.health.status:
                await self._notify_callbacks(service_name, "health_changed", curr)

    async def _handle_registry_event(self, event: str, service: ServiceInfo):
        """레지스트리 이벤트 처리"""
        await self._notify_callbacks(service.name, event, service)

    async def _notify_callbacks(
        self, service_name: str, event: str, service: ServiceInfo
    ):
        """콜백 알림"""
        if service_name in self.callbacks:
            for callback in self.callbacks[service_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event, service)
                    else:
                        callback(event, service)
                except Exception as e:
                    logger.error(f"Callback error: {e}")


class ServiceDiscovery:
    """
    서비스 디스커버리

    통합 서비스 발견 및 관리
    """

    def __init__(
        self,
        registry=None,
        enable_caching=True,
        enable_watching=True,
    ):
        self.registry = registry or get_service_registry()
        self.resolver = ServiceResolver(self.registry)
        self.watcher = ServiceWatcher(self.registry) if enable_watching else None
        self.enable_caching = enable_caching

        # 로컬 서비스 정보
        self.local_services = {}

    async def start(self):
        """디스커버리 시작"""
        if self.watcher:
            await self.watcher.start()
        logger.info("ServiceDiscovery started")

    async def stop(self):
        """디스커버리 중지"""
        # 로컬 서비스 등록 해제
        for service_id in list(self.local_services.keys()):
            await self.deregister(service_id)

        if self.watcher:
            await self.watcher.stop()

        logger.info("ServiceDiscovery stopped")

    async def register(self, service: ServiceInfo) -> Result[None, str]:
        """서비스 등록"""
        result = await self.registry.register(service)

        if type(result).__name__ == "Success":
            self.local_services = {**self.local_services, service.service_id: service}

            # 하트비트 시작
            asyncio.create_task(self._heartbeat_loop(service.service_id))

        return result

    async def deregister(self, service_id: str) -> Result[None, str]:
        """서비스 등록 해제"""
        result = await self.registry.deregister(service_id)

        if type(result).__name__ == "Success":
            local_services = {
                k: v for k, v in local_services.items() if k != "service_id, None"
            }

        return result

    async def discover(
        self,
        service_name: str,
        tags: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Result[List[ServiceEndpoint], str]:
        """서비스 발견"""
        return await self.resolver.resolve(service_name, tags, labels)

    async def discover_one(
        self,
        service_name: str,
        tags: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        load_balancer: LoadBalancerType = LoadBalancerType.ROUND_ROBIN,
    ) -> Result[ServiceEndpoint, str]:
        """단일 서비스 발견"""
        return await self.resolver.resolve_one(
            service_name, tags, labels, load_balancer
        )

    async def watch(
        self, service_name: str, callback: Callable[[str, ServiceInfo], None]
    ):
        """서비스 변경 감시"""
        if self.watcher:
            await self.watcher.watch(service_name, callback)

    async def unwatch(self, service_name: str):
        """서비스 감시 중지"""
        if self.watcher:
            await self.watcher.unwatch(service_name)

    async def _heartbeat_loop(self, service_id: str):
        """하트비트 루프"""
        service = self.local_services.get(service_id)
        if not service or not service.ttl:
            return

        # 하트비트 주기 (TTL의 절반)
        interval = service.ttl.total_seconds() / 2

        while service_id in self.local_services:
            try:
                await asyncio.sleep(interval)

                # 하트비트 전송
                result = await self.registry.heartbeat(service_id)
                if type(result).__name__ == "Failure":
                    logger.error(f"Heartbeat failed for {service_id}: {result.error}")

                    # 재등록 시도
                    service = self.local_services.get(service_id)
                    if service:
                        await self.registry.register(service)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error for {service_id}: {e}")


# 전역 디스커버리
_global_discovery = None


async def get_service_discovery() -> ServiceDiscovery:
    """전역 서비스 디스커버리 반환"""
    # global _global_discovery - removed for functional programming
    if _global_discovery is None:
        _global_discovery = ServiceDiscovery()
        await _global_discovery.start()
    return _global_discovery


async def discover_service(service_name: str, **kwargs) -> Result[ServiceEndpoint, str]:
    """서비스 발견 헬퍼"""
    discovery = await get_service_discovery()
    return await discovery.discover_one(service_name, **kwargs)


async def discover_services(
    service_name: str, **kwargs
) -> Result[List[ServiceEndpoint], str]:
    """서비스 목록 발견 헬퍼"""
    discovery = await get_service_discovery()
    return await discovery.discover(service_name, **kwargs)


async def watch_service(service_name: str, callback: Callable):
    """서비스 감시 헬퍼"""
    discovery = await get_service_discovery()
    await discovery.watch(service_name, callback)
