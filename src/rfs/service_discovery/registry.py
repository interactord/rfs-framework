"""
Service Registry Implementation

서비스 레지스트리 구현 - Consul, Etcd, Zookeeper, Redis
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Set
from abc import ABC, abstractmethod
import logging
from datetime import datetime, timedelta

from ..core import Result, Success, Failure
from .base import (
    ServiceInfo,
    ServiceStatus,
    ServiceEndpoint,
    ServiceMetadata,
    ServiceHealth,
    HealthStatus,
    RegistrationError,
    ServiceNotFoundError
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
    async def get_services(self, name: Optional[str] = None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        pass
    
    @abstractmethod
    async def update_health(self, service_id: str, health: ServiceHealth) -> Result[None, str]:
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
        self.services: Dict[str, ServiceInfo] = {}
        self.service_names: Dict[str, Set[str]] = {}  # name -> service_ids
        self.watchers: Dict[str, List[callable]] = {}
        self._lock = asyncio.Lock()
    
    async def register(self, service: ServiceInfo) -> Result[None, str]:
        """서비스 등록"""
        async with self._lock:
            # 기존 서비스 확인
            if service.service_id in self.services:
                # 업데이트
                self.services[service.service_id] = service
            else:
                # 신규 등록
                self.services[service.service_id] = service
                
                # 이름별 인덱스 업데이트
                if service.name not in self.service_names:
                    self.service_names[service.name] = set()
                self.service_names[service.name].add(service.service_id)
            
            # 워처 알림
            await self._notify_watchers(service.name, 'registered', service)
            
            logger.info(f"Service {service.name} ({service.service_id}) registered")
            return Success(None)
    
    async def deregister(self, service_id: str) -> Result[None, str]:
        """서비스 등록 해제"""
        async with self._lock:
            if service_id not in self.services:
                return Failure(f"Service {service_id} not found")
            
            service = self.services[service_id]
            del self.services[service_id]
            
            # 이름별 인덱스 업데이트
            if service.name in self.service_names:
                self.service_names[service.name].discard(service_id)
                if not self.service_names[service.name]:
                    del self.service_names[service.name]
            
            # 워처 알림
            await self._notify_watchers(service.name, 'deregistered', service)
            
            logger.info(f"Service {service.name} ({service_id}) deregistered")
            return Success(None)
    
    async def get_service(self, service_id: str) -> Result[ServiceInfo, str]:
        """서비스 조회"""
        async with self._lock:
            if service_id not in self.services:
                return Failure(f"Service {service_id} not found")
            
            service = self.services[service_id]
            
            # 만료 확인
            if service.is_expired:
                del self.services[service_id]
                return Failure(f"Service {service_id} expired")
            
            return Success(service)
    
    async def get_services(self, name: Optional[str] = None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        async with self._lock:
            if name:
                # 특정 이름의 서비스들
                if name not in self.service_names:
                    return Success([])
                
                service_ids = self.service_names[name]
                services = []
                
                for service_id in list(service_ids):
                    if service_id in self.services:
                        service = self.services[service_id]
                        
                        # 만료 확인
                        if service.is_expired:
                            del self.services[service_id]
                            service_ids.discard(service_id)
                        else:
                            services.append(service)
                
                return Success(services)
            else:
                # 모든 서비스
                services = []
                expired_ids = []
                
                for service_id, service in self.services.items():
                    if service.is_expired:
                        expired_ids.append(service_id)
                    else:
                        services.append(service)
                
                # 만료된 서비스 제거
                for service_id in expired_ids:
                    del self.services[service_id]
                
                return Success(services)
    
    async def update_health(self, service_id: str, health: ServiceHealth) -> Result[None, str]:
        """헬스 상태 업데이트"""
        async with self._lock:
            if service_id not in self.services:
                return Failure(f"Service {service_id} not found")
            
            service = self.services[service_id]
            service.health = health
            service.refresh()
            
            # 상태 변경 시 워처 알림
            if health.status == HealthStatus.CRITICAL:
                await self._notify_watchers(service.name, 'unhealthy', service)
            
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
            self.watchers[name] = []
        self.watchers[name].append(callback)
        
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
    
    def __init__(self, redis_client, key_prefix: str = "service:"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.watchers: Dict[str, List[callable]] = {}
        self._watch_task: Optional[asyncio.Task] = None
    
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
            
            # 서비스 정보 저장
            service_data = json.dumps(service.to_dict())
            
            # TTL 설정
            ttl = int(service.ttl.total_seconds()) if service.ttl else None
            
            # Redis 트랜잭션
            pipe = self.redis.pipeline()
            
            # 서비스 데이터 저장
            if ttl:
                pipe.setex(key, ttl, service_data)
            else:
                pipe.set(key, service_data)
            
            # 이름별 인덱스 추가
            pipe.sadd(name_key, service.service_id)
            
            # 글로벌 서비스 목록에 추가
            pipe.sadd(f"{self.key_prefix}all", service.service_id)
            
            pipe.execute()
            
            # 워처 알림
            await self._notify_watchers(service.name, 'registered', service)
            
            logger.info(f"Service {service.name} ({service.service_id}) registered to Redis")
            return Success(None)
            
        except Exception as e:
            return Failure(f"Failed to register service: {str(e)}")
    
    async def deregister(self, service_id: str) -> Result[None, str]:
        """서비스 등록 해제"""
        try:
            key = self._make_key(service_id)
            
            # 서비스 정보 조회
            service_data = self.redis.get(key)
            if not service_data:
                return Failure(f"Service {service_id} not found")
            
            service = ServiceInfo.from_dict(json.loads(service_data))
            name_key = self._make_name_key(service.name)
            
            # Redis 트랜잭션
            pipe = self.redis.pipeline()
            
            # 서비스 데이터 삭제
            pipe.delete(key)
            
            # 이름별 인덱스에서 제거
            pipe.srem(name_key, service_id)
            
            # 글로벌 서비스 목록에서 제거
            pipe.srem(f"{self.key_prefix}all", service_id)
            
            pipe.execute()
            
            # 워처 알림
            await self._notify_watchers(service.name, 'deregistered', service)
            
            logger.info(f"Service {service.name} ({service_id}) deregistered from Redis")
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
    
    async def get_services(self, name: Optional[str] = None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        try:
            if name:
                # 특정 이름의 서비스들
                name_key = self._make_name_key(name)
                service_ids = self.redis.smembers(name_key)
            else:
                # 모든 서비스
                service_ids = self.redis.smembers(f"{self.key_prefix}all")
            
            services = []
            for service_id in service_ids:
                if isinstance(service_id, bytes):
                    service_id = service_id.decode('utf-8')
                
                result = await self.get_service(service_id)
                if isinstance(result, Success):
                    services.append(result.value)
            
            return Success(services)
            
        except Exception as e:
            return Failure(f"Failed to get services: {str(e)}")
    
    async def update_health(self, service_id: str, health: ServiceHealth) -> Result[None, str]:
        """헬스 상태 업데이트"""
        try:
            # 서비스 조회
            result = await self.get_service(service_id)
            if isinstance(result, Failure):
                return result
            
            service = result.value
            service.health = health
            service.refresh()
            
            # 업데이트된 정보 저장
            return await self.register(service)
            
        except Exception as e:
            return Failure(f"Failed to update health: {str(e)}")
    
    async def heartbeat(self, service_id: str) -> Result[None, str]:
        """하트비트"""
        try:
            key = self._make_key(service_id)
            
            # TTL 갱신
            result = await self.get_service(service_id)
            if isinstance(result, Failure):
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
            self.watchers[name] = []
        self.watchers[name].append(callback)
        
        # 감시 태스크 시작
        if not self._watch_task:
            self._watch_task = asyncio.create_task(self._watch_loop())
        
        logger.info(f"Watching service {name} in Redis")
    
    async def _watch_loop(self):
        """Redis 변경 감시 루프"""
        # Redis Pub/Sub 사용
        pubsub = self.redis.pubsub()
        pubsub.subscribe(f"{self.key_prefix}events")
        
        while True:
            try:
                message = pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    # 이벤트 파싱
                    event_data = json.loads(message['data'])
                    await self._handle_event(event_data)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Watch loop error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_event(self, event_data: Dict[str, Any]):
        """이벤트 처리"""
        event = event_data.get('event')
        service_data = event_data.get('service')
        
        if service_data:
            service = ServiceInfo.from_dict(service_data)
            await self._notify_watchers(service.name, event, service)
    
    async def _notify_watchers(self, name: str, event: str, service: ServiceInfo):
        """워처에게 알림"""
        # Redis Pub/Sub으로 이벤트 발행
        event_data = {
            'event': event,
            'service': service.to_dict()
        }
        self.redis.publish(f"{self.key_prefix}events", json.dumps(event_data))
        
        # 로컬 워처 알림
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
            # Consul 서비스 등록 포맷
            service_def = {
                'ID': service.service_id,
                'Name': service.name,
                'Tags': service.metadata.tags,
                'Address': service.endpoint.host,
                'Port': service.endpoint.port,
                'Meta': service.metadata.labels,
                'Check': {
                    'HTTP': f"{service.endpoint.url}/health",
                    'Interval': '10s',
                    'Timeout': '5s'
                }
            }
            
            # TTL 설정
            if service.ttl:
                service_def['Check']['TTL'] = f"{int(service.ttl.total_seconds())}s"
            
            # Consul에 등록
            success = self.consul.agent.service.register(service_def)
            
            if success:
                logger.info(f"Service {service.name} ({service.service_id}) registered to Consul")
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
            # 서비스 조회
            _, services = self.consul.health.service(service_id, passing=True)
            
            if not services:
                return Failure(f"Service {service_id} not found")
            
            # Consul 데이터를 ServiceInfo로 변환
            consul_service = services[0]
            service = self._consul_to_service_info(consul_service)
            
            return Success(service)
            
        except Exception as e:
            return Failure(f"Failed to get service: {str(e)}")
    
    async def get_services(self, name: Optional[str] = None) -> Result[List[ServiceInfo], str]:
        """서비스 목록 조회"""
        try:
            if name:
                # 특정 이름의 서비스들
                _, services = self.consul.health.service(name, passing=True)
            else:
                # 모든 서비스
                _, services = self.consul.agent.services()
            
            service_list = []
            for consul_service in services:
                service = self._consul_to_service_info(consul_service)
                service_list.append(service)
            
            return Success(service_list)
            
        except Exception as e:
            return Failure(f"Failed to get services: {str(e)}")
    
    async def update_health(self, service_id: str, health: ServiceHealth) -> Result[None, str]:
        """헬스 상태 업데이트"""
        try:
            # Consul 헬스 체크 업데이트
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
            # TTL 갱신
            self.consul.agent.check.ttl_pass(f"service:{service_id}")
            return Success(None)
            
        except Exception as e:
            return Failure(f"Failed to send heartbeat: {str(e)}")
    
    async def watch(self, name: str, callback: callable):
        """서비스 변경 감시"""
        # Consul watch 구현
        pass
    
    def _consul_to_service_info(self, consul_service) -> ServiceInfo:
        """Consul 서비스를 ServiceInfo로 변환"""
        # 변환 로직
        pass


# 전역 레지스트리
_global_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """전역 서비스 레지스트리 반환"""
    global _global_registry
    if _global_registry is None:
        _global_registry = InMemoryRegistry()
    return _global_registry