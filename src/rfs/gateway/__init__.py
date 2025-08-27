"""
RFS API Gateway (RFS v4.1)

API 게이트웨이 - REST/GraphQL 지원
"""

from .rest import (  # REST API 게이트웨이; REST 핸들러; REST 요청/응답; REST 라우팅
    JsonHandler,
    RestGateway,
    RestHandler,
    RestMiddleware,
    RestRequest,
    RestResponse,
    RestRoute,
    RoutePattern,
    RouterConfig,
    create_rest_gateway,
)


# 향후 구현 예정 모듈들 - 임시 클래스 정의
# GraphQL Gateway (계획됨)
class GraphQLGateway:
    pass


class GraphQLSchema:
    pass


class GraphQLResolver:
    pass


class GraphQLType:
    pass


class GraphQLField:
    pass


class GraphQLQuery:
    pass


class GraphQLMutation:
    pass


def create_graphql_gateway(*args, **kwargs):
    pass


def execute_graphql(*args, **kwargs):
    pass


# Middleware (계획됨)
class GatewayMiddleware:
    pass


class AuthMiddleware:
    pass


class RateLimitMiddleware:
    pass


class CorsMiddleware:
    pass


class LoggingMiddleware:
    pass


class MiddlewareChain:
    pass


def create_middleware_chain(*args, **kwargs):
    pass


# Monitoring (계획됨)
class GatewayMonitor:
    pass


class RequestMetrics:
    pass


class ResponseMetrics:
    pass


class MonitoringMiddleware:
    pass


def collect_request_metrics(*args, **kwargs):
    pass


def collect_response_metrics(*args, **kwargs):
    pass


# Proxy Gateway (계획됨)
class ProxyGateway:
    pass


class ProxyRule:
    pass


class LoadBalancer:
    pass


class BalancingStrategy:
    pass


class RoundRobinBalancer:
    pass


class WeightedBalancer:
    pass


class HealthBasedBalancer:
    pass


class ProxyConfig:
    pass


class UpstreamServer:
    pass


def create_proxy_gateway(*args, **kwargs):
    pass


# Security (계획됨)
class SecurityMiddleware:
    pass


class JwtSecurityMiddleware:
    pass


class ApiKeySecurityMiddleware:
    pass


class SecurityPolicy:
    pass


class RateLimitPolicy:
    pass


class CorsPolicy:
    pass


def create_security_middleware(*args, **kwargs):
    pass


def create_gateway_app(title="RFS Gateway", version="1.0.0", **kwargs):
    """
    간단한 게이트웨이 앱 생성 함수
    FastAPI가 설치된 경우 FastAPI 앱을 반환하고, 그렇지 않으면 None 반환
    """
    try:
        from fastapi import FastAPI

        app = FastAPI(title=title, version=version, **kwargs)
        return app
    except ImportError:
        # FastAPI가 설치되지 않은 경우 대안 제공
        print(f"FastAPI not installed. Install with: pip install fastapi[all]")
        return None


__all__ = [
    # REST Gateway
    "RestGateway",
    "RestRoute",
    "RestMiddleware",
    "RestHandler",
    "JsonHandler",
    "RestRequest",
    "RestResponse",
    "RouterConfig",
    "RoutePattern",
    "create_rest_gateway",
    # GraphQL Gateway
    "GraphQLGateway",
    "GraphQLSchema",
    "GraphQLResolver",
    "GraphQLType",
    "GraphQLField",
    "GraphQLQuery",
    "GraphQLMutation",
    "execute_graphql",
    "create_graphql_gateway",
    # Proxy Gateway
    "ProxyGateway",
    "ProxyRule",
    "LoadBalancer",
    "BalancingStrategy",
    "RoundRobinBalancer",
    "WeightedBalancer",
    "HealthBasedBalancer",
    "ProxyConfig",
    "UpstreamServer",
    "create_proxy_gateway",
    # Middleware
    "GatewayMiddleware",
    "AuthMiddleware",
    "RateLimitMiddleware",
    "CorsMiddleware",
    "LoggingMiddleware",
    "MiddlewareChain",
    "create_middleware_chain",
    # Security
    "SecurityMiddleware",
    "JwtSecurityMiddleware",
    "ApiKeySecurityMiddleware",
    "SecurityPolicy",
    "RateLimitPolicy",
    "CorsPolicy",
    "create_security_middleware",
    # Monitoring
    "GatewayMonitor",
    "RequestMetrics",
    "ResponseMetrics",
    "MonitoringMiddleware",
    "collect_request_metrics",
    "collect_response_metrics",
    # Helper Functions
    "create_gateway_app",
]
