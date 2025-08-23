"""
Integration Enhancement Suite for RFS Framework

통합 시스템 강화 모듈:
- 고급 웹 통합
- 분산 캐시 관리
- API Gateway 강화
"""

from .web_integration import (
    WebIntegrationManager, WebhookConfig, APIIntegration,
    OAuthConfig, GraphQLIntegration, RESTIntegration,
    get_web_integration_manager
)
from .distributed_cache import (
    DistributedCacheManager, CacheConfig, CacheBackend,
    EvictionPolicy, CacheStrategy, InvalidationStrategy,
    get_distributed_cache_manager
)
from .api_gateway import (
    APIGatewayEnhancer, Route, Backend, APIEndpoint,
    LoadBalanceStrategy, AuthenticationMethod, RateLimitStrategy,
    APIKey, RateLimitRule, RequestContext, ResponseContext,
    get_api_gateway
)

__all__ = [
    # Web Integration
    "WebIntegrationManager", "WebhookConfig", "APIIntegration",
    "OAuthConfig", "GraphQLIntegration", "RESTIntegration",
    "get_web_integration_manager",
    
    # Distributed Cache
    "DistributedCacheManager", "CacheConfig", "CacheBackend",
    "EvictionPolicy", "CacheStrategy", "InvalidationStrategy",
    "get_distributed_cache_manager",
    
    # API Gateway
    "APIGatewayEnhancer", "Route", "Backend", "APIEndpoint",
    "LoadBalanceStrategy", "AuthenticationMethod", "RateLimitStrategy",
    "APIKey", "RateLimitRule", "RequestContext", "ResponseContext",
    "get_api_gateway"
]