"""
Service Discovery System for RFS Framework

서비스 디스커버리 - 동적 서비스 등록 및 발견
"""

from .base import (
    HealthCheck,
    HealthStatus,
    LoadBalancerType,
    ServiceEndpoint,
    ServiceHealth,
    ServiceInfo,
    ServiceMetadata,
    ServiceStatus,
)
from .client import (
    CircuitBreaker,
    LoadBalancer,
    RandomBalancer,
    RetryStrategy,
    RoundRobinBalancer,
    ServiceClient,
    WeightedBalancer,
    get_service_client,
)
from .decorators import (
    circuit_breaker,
    discoverable,
    health_check,
    load_balanced,
    service_call,
    service_endpoint,
)
from .discovery import (
    ServiceDiscovery,
    ServiceResolver,
    ServiceWatcher,
    discover_service,
    discover_services,
    get_service_discovery,
    watch_service,
)
from .health import (
    GrpcHealthCheck,
    HealthChecker,
    HealthMonitor,
    HttpHealthCheck,
    TcpHealthCheck,
    get_health_monitor,
)
from .registry import (
    ConsulRegistry,
    EtcdRegistry,
    RedisRegistry,
    ServiceRegistry,
    ZookeeperRegistry,
    get_service_registry,
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
    "service_call",
]
