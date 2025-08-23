"""
Service Discovery System for RFS Framework

서비스 디스커버리 - 동적 서비스 등록 및 발견
"""

from .base import (
    ServiceInfo,
    ServiceStatus,
    ServiceHealth,
    ServiceEndpoint,
    ServiceMetadata,
    HealthCheck,
    HealthStatus,
    LoadBalancerType
)

from .registry import (
    ServiceRegistry,
    ConsulRegistry,
    EtcdRegistry,
    ZookeeperRegistry,
    RedisRegistry,
    get_service_registry
)

from .discovery import (
    ServiceDiscovery,
    ServiceResolver,
    ServiceWatcher,
    get_service_discovery,
    discover_service,
    discover_services,
    watch_service
)

from .client import (
    ServiceClient,
    CircuitBreaker,
    RetryStrategy,
    LoadBalancer,
    RoundRobinBalancer,
    RandomBalancer,
    WeightedBalancer,
    get_service_client
)

from .health import (
    HealthChecker,
    HealthMonitor,
    HttpHealthCheck,
    TcpHealthCheck,
    GrpcHealthCheck,
    get_health_monitor
)

from .decorators import (
    service_endpoint,
    discoverable,
    health_check,
    circuit_breaker,
    load_balanced,
    service_call
)

__all__ = [
    # Base
    "ServiceInfo",
    "ServiceStatus",
    "ServiceHealth",
    "ServiceEndpoint",
    "ServiceMetadata",
    "HealthCheck",
    "HealthStatus",
    "LoadBalancerType",
    
    # Registry
    "ServiceRegistry",
    "ConsulRegistry",
    "EtcdRegistry",
    "ZookeeperRegistry",
    "RedisRegistry",
    "get_service_registry",
    
    # Discovery
    "ServiceDiscovery",
    "ServiceResolver",
    "ServiceWatcher",
    "get_service_discovery",
    "discover_service",
    "discover_services",
    "watch_service",
    
    # Client
    "ServiceClient",
    "CircuitBreaker",
    "RetryStrategy",
    "LoadBalancer",
    "RoundRobinBalancer",
    "RandomBalancer",
    "WeightedBalancer",
    "get_service_client",
    
    # Health
    "HealthChecker",
    "HealthMonitor",
    "HttpHealthCheck",
    "TcpHealthCheck",
    "GrpcHealthCheck",
    "get_health_monitor",
    
    # Decorators
    "service_endpoint",
    "discoverable",
    "health_check",
    "circuit_breaker",
    "load_balanced",
    "service_call"
]