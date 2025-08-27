"""
Service Registry Implementation

서비스 레지스트리 구현 - Consul, Etcd, Zookeeper, Redis
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from ..core.result import Failure, Result, Success
from .base import (
    HealthStatus,
    RegistrationError,
    ServiceEndpoint,
    ServiceHealth,
    ServiceInfo,
    ServiceMetadata,
    ServiceNotFoundError,
    ServiceStatus,
)

logger = logging.getLogger(__name__)


class ServiceRegistry(ABC):
    """서비스 레지스트리 인터페이스"""

    @abstractmethod
    async def register(self, service: ServiceInfo) -> Result[None, str]:
        """서비스 등록"""
        pass

    @abstractmethod
    async def deregister(self, service_id: str) -> Result[None, str]:
        """서비스 등록 해제"""
        pass

    @abstractmethod
    async def get_service(self, service_id: str) -> Result[ServiceInfo, str]:
        """서비스 조회"""
        pass

    @abstractmethod
    async def get_services(self, name=None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        pass

    @abstractmethod
    async def update_health(
        self, service_id: str, health: ServiceHealth
    ) -> Result[None, str]:
        """헬스 상태 업데이트"""
        pass

    @abstractmethod
    async def heartbeat(self, service_id: str) -> Result[None, str]:
        """하트비트"""
        pass

    @abstractmethod
    async def watch(self, name: str, callback: callable):
        """서비스 변경 감시"""
        pass


class InMemoryRegistry(ServiceRegistry):
    """
    메모리 기반 레지스트리 (개발/테스트용)
    """

    def __init__(self):
        self.services = {}
        self.service_names: Dict[str, Set[str]] = {}
        self.watchers: Dict[str, List[callable]] = {}
        self._lock = asyncio.Lock()

    async def register(self, service: ServiceInfo) -> Result[None, str]:
        """서비스 등록"""
        async with self._lock:
            if service.service_id in self.services:
                self.services = {**self.services, service.service_id: service}
            else:
                self.services = {**self.services, service.service_id: service}
                if service.name not in self.service_names:
                    self.service_names = {**self.service_names, service.name: set()}
                self.service_names[service.name].add(service.service_id)
            await self._notify_watchers(service.name, "registered", service)
            logger.info(f"Service {service.name} ({service.service_id}) registered")
            return Success(None)

    async def deregister(self, service_id: str) -> Result[None, str]:
        """서비스 등록 해제"""
        async with self._lock:
            if service_id not in self.services:
                return Failure(f"Service {service_id} not found")
            service = self.services[service_id]
            del self.services[service_id]
            if service.name in self.service_names:
                self.service_names[service.name].discard(service_id)
                if not self.service_names[service.name]:
                    del self.service_names[service.name]
            await self._notify_watchers(service.name, "deregistered", service)
            logger.info(f"Service {service.name} ({service_id}) deregistered")
            return Success(None)

    async def get_service(self, service_id: str) -> Result[ServiceInfo, str]:
        """서비스 조회"""
        async with self._lock:
            if service_id not in self.services:
                return Failure(f"Service {service_id} not found")
            service = self.services[service_id]
            if service.is_expired:
                del self.services[service_id]
                return Failure(f"Service {service_id} expired")
            return Success(service)

    async def get_services(self, name=None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        async with self._lock:
            if name:
                if name not in self.service_names:
                    return Success([])
                service_ids = self.service_names[name]
                services = []
                for service_id in list(service_ids):
                    if service_id in self.services:
                        service = self.services[service_id]
                        if service.is_expired:
                            del self.services[service_id]
                            service_ids.discard(service_id)
                        else:
                            services = services + [service]
                return Success(services)
            else:
                services = []
                expired_ids = []
                for service_id, service in self.services.items():
                    if service.is_expired:
                        expired_ids = expired_ids + [service_id]
                    else:
                        services = services + [service]
                for service_id in expired_ids:
                    del self.services[service_id]
                return Success(services)

    async def update_health(
        self, service_id: str, health: ServiceHealth
    ) -> Result[None, str]:
        """헬스 상태 업데이트"""
        async with self._lock:
            if service_id not in self.services:
                return Failure(f"Service {service_id} not found")
            service = self.services[service_id]
            service.health = health
            service.refresh()
            if health.status == HealthStatus.CRITICAL:
                await self._notify_watchers(service.name, "unhealthy", service)
            return Success(None)

    async def heartbeat(self, service_id: str) -> Result[None, str]:
        """하트비트"""
        async with self._lock:
            if service_id not in self.services:
                return Failure(f"Service {service_id} not found")
            self.services[service_id].refresh()
            return Success(None)

    async def watch(self, name: str, callback: callable):
        """서비스 변경 감시"""
        if name not in self.watchers:
            self.watchers = {**self.watchers, name: []}
        self.watchers[name] = watchers[name] + [callback]
        logger.info(f"Watching service {name}")

    async def _notify_watchers(self, name: str, event: str, service: ServiceInfo):
        """워처에게 알림"""
        if name in self.watchers:
            for callback in self.watchers[name]:
                try:
                    await callback(event, service)
                except Exception as e:
                    logger.error(f"Watcher callback error: {e}")


class RedisRegistry(ServiceRegistry):
    """
    Redis 기반 레지스트리
    """

    def __init__(self, redis_client, key_prefix="service:"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.watchers: Dict[str, List[callable]] = {}
        self._watch_task = None

    def _make_key(self, service_id: str) -> str:
        """키 생성"""
        return f"{self.key_prefix}{service_id}"

    def _make_name_key(self, name: str) -> str:
        """이름 키 생성"""
        return f"{self.key_prefix}name:{name}"

    async def register(self, service: ServiceInfo) -> Result[None, str]:
        """서비스 등록"""
        try:
            key = self._make_key(service.service_id)
            name_key = self._make_name_key(service.name)
            service_data = json.dumps(service.to_dict())
            ttl = int(service.ttl.total_seconds()) if service.ttl else None
            pipe = self.redis.pipeline()
            if ttl:
                pipe.setex(key, ttl, service_data)
            else:
                pipe.set(key, service_data)
            pipe.sadd(name_key, service.service_id)
            pipe.sadd(f"{self.key_prefix}all", service.service_id)
            pipe.execute()
            await self._notify_watchers(service.name, "registered", service)
            logger.info(
                f"Service {service.name} ({service.service_id}) registered to Redis"
            )
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to register service: {str(e)}")

    async def deregister(self, service_id: str) -> Result[None, str]:
        """서비스 등록 해제"""
        try:
            key = self._make_key(service_id)
            service_data = self.redis.get(key)
            if not service_data:
                return Failure(f"Service {service_id} not found")
            service = ServiceInfo.from_dict(json.loads(service_data))
            name_key = self._make_name_key(service.name)
            pipe = self.redis.pipeline()
            pipe.delete(key)
            pipe.srem(name_key, service_id)
            pipe.srem(f"{self.key_prefix}all", service_id)
            pipe.execute()
            await self._notify_watchers(service.name, "deregistered", service)
            logger.info(
                f"Service {service.name} ({service_id}) deregistered from Redis"
            )
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to deregister service: {str(e)}")

    async def get_service(self, service_id: str) -> Result[ServiceInfo, str]:
        """서비스 조회"""
        try:
            key = self._make_key(service_id)
            service_data = self.redis.get(key)
            if not service_data:
                return Failure(f"Service {service_id} not found")
            service = ServiceInfo.from_dict(json.loads(service_data))
            return Success(service)
        except Exception as e:
            return Failure(f"Failed to get service: {str(e)}")

    async def get_services(self, name=None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        try:
            if name:
                name_key = self._make_name_key(name)
                service_ids = self.redis.smembers(name_key)
            else:
                service_ids = self.redis.smembers(f"{self.key_prefix}all")
            services = []
            for service_id in service_ids:
                if type(service_id).__name__ == "bytes":
                    service_id = service_id.decode("utf-8")
                result = await self.get_service(service_id)
                if type(result).__name__ == "Success":
                    services = services + [result.value]
            return Success(services)
        except Exception as e:
            return Failure(f"Failed to get services: {str(e)}")

    async def update_health(
        self, service_id: str, health: ServiceHealth
    ) -> Result[None, str]:
        """헬스 상태 업데이트"""
        try:
            result = await self.get_service(service_id)
            if type(result).__name__ == "Failure":
                return result
            service = result.value
            service.health = health
            service.refresh()
            return await self.register(service)
        except Exception as e:
            return Failure(f"Failed to update health: {str(e)}")

    async def heartbeat(self, service_id: str) -> Result[None, str]:
        """하트비트"""
        try:
            key = self._make_key(service_id)
            result = await self.get_service(service_id)
            if type(result).__name__ == "Failure":
                return result
            service = result.value
            if service.ttl:
                ttl = int(service.ttl.total_seconds())
                self.redis.expire(key, ttl)
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to send heartbeat: {str(e)}")

    async def watch(self, name: str, callback: callable):
        """서비스 변경 감시"""
        if name not in self.watchers:
            self.watchers = {**self.watchers, name: []}
        self.watchers[name] = watchers[name] + [callback]
        if not self._watch_task:
            self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info(f"Watching service {name} in Redis")

    async def _watch_loop(self):
        """Redis 변경 감시 루프"""
        pubsub = self.redis.pubsub()
        pubsub.subscribe(f"{self.key_prefix}events")
        while True:
            try:
                message = pubsub.get_message(timeout=1.0)
                if message and message.get("type") == "message":
                    event_data = json.loads(message["data"])
                    await self._handle_event(event_data)
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Watch loop error: {e}")
                await asyncio.sleep(1)

    async def _handle_event(self, event_data: Dict[str, Any]):
        """이벤트 처리"""
        event = event_data.get("event")
        service_data = event_data.get("service")
        if service_data:
            service = ServiceInfo.from_dict(service_data)
            await self._notify_watchers(service.name, event, service)

    async def _notify_watchers(self, name: str, event: str, service: ServiceInfo):
        """워처에게 알림"""
        event_data = {"event": event, "service": service.to_dict()}
        self.redis.publish(f"{self.key_prefix}events", json.dumps(event_data))
        if name in self.watchers:
            for callback in self.watchers[name]:
                try:
                    await callback(event, service)
                except Exception as e:
                    logger.error(f"Watcher callback error: {e}")


class ConsulRegistry(ServiceRegistry):
    """
    Consul 기반 레지스트리
    """

    def __init__(self, consul_client):
        self.consul = consul_client
        self.watchers: Dict[str, List[callable]] = {}

    async def register(self, service: ServiceInfo) -> Result[None, str]:
        """서비스 등록"""
        try:
            service_def = {
                "ID": service.service_id,
                "Name": service.name,
                "Tags": service.metadata.tags,
                "Address": service.endpoint.host,
                "Port": service.endpoint.port,
                "Meta": service.metadata.labels,
                "Check": {
                    "HTTP": f"{service.endpoint.url}/health",
                    "Interval": "10s",
                    "Timeout": "5s",
                },
            }
            if service.ttl:
                service_def["Check"] = {
                    **service_def.get("Check"),
                    "TTL": f"{int(service.ttl.total_seconds())}s",
                }
            success = self.consul.agent.service.register(service_def)
            if success:
                logger.info(
                    f"Service {service.name} ({service.service_id}) registered to Consul"
                )
                return Success(None)
            else:
                return Failure("Failed to register service to Consul")
        except Exception as e:
            return Failure(f"Failed to register service: {str(e)}")

    async def deregister(self, service_id: str) -> Result[None, str]:
        """서비스 등록 해제"""
        try:
            success = self.consul.agent.service.deregister(service_id)
            if success:
                logger.info(f"Service {service_id} deregistered from Consul")
                return Success(None)
            else:
                return Failure(f"Failed to deregister service {service_id}")
        except Exception as e:
            return Failure(f"Failed to deregister service: {str(e)}")

    async def get_service(self, service_id: str) -> Result[ServiceInfo, str]:
        """서비스 조회"""
        try:
            _, services = self.consul.health.service(service_id, passing=True)
            if not services:
                return Failure(f"Service {service_id} not found")
            consul_service = services[0]
            service = self._consul_to_service_info(consul_service)
            return Success(service)
        except Exception as e:
            return Failure(f"Failed to get service: {str(e)}")

    async def get_services(self, name=None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        try:
            if name:
                _, services = self.consul.health.service(name, passing=True)
            else:
                _, services = self.consul.agent.services()
            service_list = []
            for consul_service in services:
                service = self._consul_to_service_info(consul_service)
                service_list = service_list + [service]
            return Success(service_list)
        except Exception as e:
            return Failure(f"Failed to get services: {str(e)}")

    async def update_health(
        self, service_id: str, health: ServiceHealth
    ) -> Result[None, str]:
        """헬스 상태 업데이트"""
        try:
            if health.is_healthy:
                self.consul.agent.check.ttl_pass(f"service:{service_id}")
            else:
                self.consul.agent.check.ttl_fail(f"service:{service_id}")
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to update health: {str(e)}")

    async def heartbeat(self, service_id: str) -> Result[None, str]:
        """하트비트"""
        try:
            self.consul.agent.check.ttl_pass(f"service:{service_id}")
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to send heartbeat: {str(e)}")

    async def watch(self, name: str, callback: callable):
        """서비스 변경 감시"""
        pass

    def _consul_to_service_info(self, consul_service) -> ServiceInfo:
        """Consul 서비스를 ServiceInfo로 변환"""
        pass


_global_registry = None


def get_service_registry() -> ServiceRegistry:
    """전역 서비스 레지스트리 반환"""
    # global _global_registry - removed for functional programming
    if _global_registry is None:
        _global_registry = InMemoryRegistry()
    return _global_registry
