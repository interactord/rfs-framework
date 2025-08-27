"""
API Gateway Enhancer for RFS Framework

API Gateway 강화 시스템:
- 요청 라우팅 및 로드 밸런싱
- API 버전 관리
- 요청/응답 변환
- 인증 및 권한 부여
- 속도 제한 및 할당량 관리
- API 문서 자동 생성
- 모니터링 및 분석
"""

import asyncio
import hashlib
import json
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Tuple, Union

try:
    import jwt
except ImportError:
    jwt = None

try:
    import yaml
except ImportError:
    yaml = None

from ..core.result import Failure, Result, Success


class LoadBalanceStrategy(Enum):
    """로드 밸런싱 전략"""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    IP_HASH = "ip_hash"
    RANDOM = "random"
    LEAST_RESPONSE_TIME = "least_response_time"


class AuthenticationMethod(Enum):
    """인증 방법"""

    NONE = "none"
    API_KEY = "api_key"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    CUSTOM = "custom"


class RateLimitStrategy(Enum):
    """속도 제한 전략"""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class TransformationType(Enum):
    """변환 타입"""

    REQUEST_HEADER = "request_header"
    REQUEST_BODY = "request_body"
    REQUEST_QUERY = "request_query"
    RESPONSE_HEADER = "response_header"
    RESPONSE_BODY = "response_body"


class APIVersion(Enum):
    """API 버전 전략"""

    URL_PATH = "url_path"
    QUERY_PARAM = "query_param"
    HEADER = "header"
    CONTENT_TYPE = "content_type"


@dataclass
class Backend:
    """백엔드 서버"""

    id: str
    host: str
    port: int
    weight = 1
    healthy = True
    active_connections = 0
    response_times: List[float] = field(default_factory=list)
    last_health_check = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def average_response_time(self) -> float:
        """평균 응답 시간"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times[-100:]) / len(self.response_times[-100:])


@dataclass
class Route:
    """API 라우트"""

    id: str
    path: str
    methods: List[str]
    backends: List[Backend]
    authentication: AuthenticationMethod
    rate_limit: Optional[Dict[str, Any]] = None
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    cache_config: Optional[Dict[str, Any]] = None
    cors_config: Optional[Dict[str, Any]] = None
    timeout = 30
    retry_count = 3
    circuit_breaker: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIEndpoint:
    """API 엔드포인트"""

    id: str
    path: str
    method: str
    version: str
    route: Route
    documentation: Optional[Dict[str, Any]] = None
    deprecated = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitRule:
    """속도 제한 규칙"""

    id: str
    name: str
    strategy: RateLimitStrategy
    requests_per_second: float
    burst_size: int
    scope: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKey:
    """API 키"""

    key: str
    name: str
    owner: str
    created_at: datetime
    expires_at = None
    rate_limit = None
    allowed_ips: List[str] = field(default_factory=list)
    allowed_routes: List[str] = field(default_factory=list)
    usage_quota = None
    current_usage = 0
    active = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestContext:
    """요청 컨텍스트"""

    request_id: str
    client_ip: str
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, Any]
    body = None
    user_id = None
    api_key = None
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponseContext:
    """응답 컨텍스트"""

    status_code: int
    headers: Dict[str, str]
    body: Any
    elapsed_time: float
    backend_used = None
    cached = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenBucket:
    """토큰 버킷 속도 제한"""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()

    def can_consume(self, tokens=1) -> bool:
        """토큰 소비 가능 여부"""
        self._refill()
        if self.tokens >= tokens:
            tokens = tokens - tokens
            return True
        return False

    def _refill(self):
        """토큰 리필"""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now


class RateLimiter:
    """속도 제한기"""

    def __init__(self):
        self.buckets = {}
        self.fixed_windows: Dict[str, Dict[str, int]] = defaultdict(dict)
        self.sliding_windows: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(self, rule: RateLimitRule, identifier: str) -> bool:
        """속도 제한 확인"""
        match rule.strategy:
            case RateLimitStrategy.TOKEN_BUCKET:
                return self._check_token_bucket(rule, identifier)
            case RateLimitStrategy.FIXED_WINDOW:
                return self._check_fixed_window(rule, identifier)
            case RateLimitStrategy.SLIDING_WINDOW:
                return self._check_sliding_window(rule, identifier)
        return True

    def _check_token_bucket(self, rule: RateLimitRule, identifier: str) -> bool:
        """토큰 버킷 확인"""
        bucket_key = f"{rule.id}:{identifier}"
        if bucket_key not in self.buckets:
            self.buckets = {
                **self.buckets,
                bucket_key: TokenBucket(
                    rate=rule.requests_per_second, capacity=rule.burst_size
                ),
            }
        return self.buckets[bucket_key].can_consume()

    def _check_fixed_window(self, rule: RateLimitRule, identifier: str) -> bool:
        """고정 윈도우 확인"""
        window_key = f"{rule.id}:{identifier}"
        current_window = int(time.time())
        if current_window not in self.fixed_windows[window_key]:
            self.fixed_windows[window_key] = []
            self.fixed_windows = {
                **self.fixed_windows,
                window_key: {**self.fixed_windows[window_key], current_window: 0},
            }
        if self.fixed_windows[window_key][current_window] >= rule.requests_per_second:
            return False
        self.fixed_windows[window_key][current_window] = (
            self.fixed_windows[window_key][current_window] + 1
        )
        return True

    def _check_sliding_window(self, rule: RateLimitRule, identifier: str) -> bool:
        """슬라이딩 윈도우 확인"""
        window_key = f"{rule.id}:{identifier}"
        now = time.time()
        window_start = now - 1.0
        self.sliding_windows[window_key] = [
            t for t in self.sliding_windows[window_key] if t > window_start
        ]
        if len(self.sliding_windows[window_key]) >= rule.requests_per_second:
            return False
        self.sliding_windows[window_key] = sliding_windows[window_key] + [now]
        return True


class LoadBalancer:
    """로드 밸런서"""

    def __init__(self, strategy: LoadBalanceStrategy):
        self.strategy = strategy
        self.round_robin_indexes = {}

    def select_backend(
        self, route_id: str, backends: List[Backend], client_ip: str = None
    ) -> Optional[Backend]:
        """백엔드 선택"""
        healthy_backends = [b for b in backends if b.healthy]
        if not healthy_backends:
            return None
        match self.strategy:
            case LoadBalanceStrategy.ROUND_ROBIN:
                return self._round_robin(route_id, healthy_backends)
            case LoadBalanceStrategy.LEAST_CONNECTIONS:
                return self._least_connections(healthy_backends)
            case LoadBalanceStrategy.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin(route_id, healthy_backends)
            case LoadBalanceStrategy.IP_HASH:
                return self._ip_hash(healthy_backends, client_ip)
            case LoadBalanceStrategy.RANDOM:
                return self._random(healthy_backends)
            case LoadBalanceStrategy.LEAST_RESPONSE_TIME:
                return self._least_response_time(healthy_backends)
        return healthy_backends[0]

    def _round_robin(self, route_id: str, backends: List[Backend]) -> Backend:
        """라운드 로빈"""
        if route_id not in self.round_robin_indexes:
            self.round_robin_indexes = {**self.round_robin_indexes, route_id: 0}
        index = self.round_robin_indexes[route_id]
        backend = backends[index % len(backends)]
        self.round_robin_indexes = {
            **self.round_robin_indexes,
            route_id: (index + 1) % len(backends),
        }
        return backend

    def _least_connections(self, backends: List[Backend]) -> Backend:
        """최소 연결"""
        return min(backends, key=lambda b: b.active_connections)

    def _weighted_round_robin(self, route_id: str, backends: List[Backend]) -> Backend:
        """가중치 라운드 로빈"""
        weighted_backends = []
        for backend in backends:
            weighted_backends = weighted_backends + [backend] * backend.weight
        return self._round_robin(route_id, weighted_backends)

    def _ip_hash(self, backends: List[Backend], client_ip: str) -> Backend:
        """IP 해시"""
        if not client_ip:
            return backends[0]
        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        return backends[hash_value % len(backends)]

    def _random(self, backends: List[Backend]) -> Backend:
        """무작위"""
        import random

        return random.choice(backends)

    def _least_response_time(self, backends: List[Backend]) -> Backend:
        """최소 응답 시간"""
        return min(backends, key=lambda b: b.average_response_time)


class APIGatewayEnhancer:
    """API Gateway 강화기"""

    def __init__(self):
        self.routes = {}
        self.endpoints = {}
        self.api_keys = {}
        self.rate_rules = {}
        self.rate_limiter = RateLimiter()
        self.load_balancer = LoadBalancer(LoadBalanceStrategy.ROUND_ROBIN)
        self.request_middlewares = []
        self.response_middlewares = []
        self.transformers = {}
        self.request_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self._response_cache: Dict[str, Tuple[ResponseContext, float]] = {}
        self._running = False
        self._tasks: Set[asyncio.Task] = set()

    async def start(self) -> Result[bool, str]:
        """게이트웨이 시작"""
        try:
            self._running = True
            health_check_task = asyncio.create_task(self._health_checker())
            self._tasks.add(health_check_task)
            cache_cleanup_task = asyncio.create_task(self._cache_cleanup())
            self._tasks.add(cache_cleanup_task)
            stats_task = asyncio.create_task(self._statistics_collector())
            self._tasks.add(stats_task)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start API gateway: {e}")

    async def stop(self) -> Result[bool, str]:
        """게이트웨이 중지"""
        try:
            self._running = False
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                _tasks = {}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop API gateway: {e}")

    def add_route(self, route: Route) -> Result[bool, str]:
        """라우트 추가"""
        try:
            if route.id in self.routes:
                return Failure(f"Route {route.id} already exists")
            self.routes = {**self.routes, route.id: route}
            for method in route.methods:
                endpoint = APIEndpoint(
                    id=f"{route.id}_{method}",
                    path=route.path,
                    method=method,
                    version="v1",
                    route=route,
                )
                self.endpoints = {**self.endpoints, endpoint.id: endpoint}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add route: {e}")

    def add_api_key(self, api_key: APIKey) -> Result[bool, str]:
        """API 키 추가"""
        try:
            if api_key.key in self.api_keys:
                return Failure(f"API key already exists")
            self.api_keys = {**self.api_keys, api_key.key: api_key}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add API key: {e}")

    def add_rate_limit_rule(self, rule: RateLimitRule) -> Result[bool, str]:
        """속도 제한 규칙 추가"""
        try:
            if rule.id in self.rate_rules:
                return Failure(f"Rate limit rule {rule.id} already exists")
            self.rate_rules = {**self.rate_rules, rule.id: rule}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add rate limit rule: {e}")

    def add_request_middleware(self, middleware: Callable):
        """요청 미들웨어 추가"""
        self.request_middlewares = self.request_middlewares + [middleware]

    def add_response_middleware(self, middleware: Callable):
        """응답 미들웨어 추가"""
        self.response_middlewares = self.response_middlewares + [middleware]

    def add_transformer(self, name: str, transformer: Callable):
        """변환기 추가"""
        self.transformers = {**self.transformers, name: transformer}

    async def handle_request(
        self, context: RequestContext
    ) -> Result[ResponseContext, str]:
        """요청 처리"""
        try:
            request_count = request_count + 1
            route = self._match_route(context.path, context.method)
            if not route:
                return Failure(f"No route found for {context.method} {context.path}")
            auth_result = await self._authenticate(route, context)
            if type(auth_result).__name__ == "Failure":
                return auth_result
            rate_limit_result = await self._check_rate_limit(route, context)
            if type(rate_limit_result).__name__ == "Failure":
                return rate_limit_result
            for middleware in self.request_middlewares:
                context = await middleware(context)
            context = await self._transform_request(route, context)
            if route.cache_config:
                cached_response = self._get_cached_response(route, context)
                if cached_response:
                    return Success(cached_response)
            backend = self.load_balancer.select_backend(
                route.id, route.backends, context.client_ip
            )
            if not backend:
                return Failure("No healthy backend available")
            start_time = time.time()
            active_connections = active_connections + 1
            try:
                response = await self._call_backend(backend, route, context)
                elapsed = time.time() - start_time
                backend.response_times = backend.response_times + [elapsed]
                total_response_time = total_response_time + elapsed
            finally:
                active_connections = active_connections - 1
            response = await self._transform_response(route, response)
            for middleware in self.response_middlewares:
                response = await middleware(response)
            if route.cache_config and response.status_code == 200:
                self._cache_response(route, context, response)
            return Success(response)
        except Exception as e:
            error_count = error_count + 1
            return Failure(f"Request handling failed: {e}")

    async def _authenticate(
        self, route: Route, context: RequestContext
    ) -> Result[bool, str]:
        """인증 처리"""
        if route.authentication == AuthenticationMethod.NONE:
            return Success(True)
        match route.authentication:
            case AuthenticationMethod.API_KEY:
                api_key = context.headers.get("X-API-Key")
                if not api_key or api_key not in self.api_keys:
                    return Failure("Invalid API key")
                key_obj = self.api_keys[api_key]
                if key_obj.expires_at and datetime.now() > key_obj.expires_at:
                    return Failure("API key expired")
                if not key_obj.active:
                    return Failure("API key is inactive")
                if key_obj.allowed_ips and context.client_ip not in key_obj.allowed_ips:
                    return Failure("IP not allowed")
                if key_obj.allowed_routes and route.id not in key_obj.allowed_routes:
                    return Failure("Route not allowed")
                if key_obj.usage_quota and key_obj.current_usage >= key_obj.usage_quota:
                    return Failure("Usage quota exceeded")
                key_obj.current_usage = key_obj.current_usage + 1
                context.api_key = api_key
            case AuthenticationMethod.JWT:
                auth_header = context.headers.get("Authorization", "")
                if not auth_header.startswith("Bearer "):
                    return Failure("Missing or invalid JWT token")
                token = auth_header[7:]
                try:
                    payload = jwt.decode(token, "secret", algorithms=["HS256"])
                    context.user_id = payload.get("user_id")
                except jwt.InvalidTokenError:
                    return Failure("Invalid JWT token")
            case AuthenticationMethod.BASIC:
                auth_header = context.headers.get("Authorization", "")
                if not auth_header.startswith("Basic "):
                    return Failure("Missing or invalid Basic auth")
                import base64

                try:
                    credentials = base64.b64decode(auth_header[6:]).decode()
                    username, password = credentials.split(":", 1)
                    context.user_id = username
                except Exception:
                    return Failure("Invalid Basic auth credentials")
        return Success(True)

    async def _check_rate_limit(
        self, route: Route, context: RequestContext
    ) -> Result[bool, str]:
        """속도 제한 확인"""
        if not route.rate_limit:
            return Success(True)
        rule_id = route.rate_limit.get("rule_id")
        if rule_id not in self.rate_rules:
            return Success(True)
        rule = self.rate_rules[rule_id]
        identifier = ""
        match rule.scope:
            case "global":
                identifier = "global"
            case "ip":
                identifier = context.client_ip
            case "user":
                identifier = context.user_id or context.client_ip
            case "api_key":
                identifier = context.api_key or context.client_ip
        if not self.rate_limiter.check_rate_limit(rule, identifier):
            return Failure("Rate limit exceeded")
        return Success(True)

    async def _transform_request(
        self, route: Route, context: RequestContext
    ) -> RequestContext:
        """요청 변환"""
        for transformation in route.transformations:
            if transformation["type"] == TransformationType.REQUEST_HEADER.value:
                if "add" in transformation:
                    context.headers = {**headers, **transformation["add"]}
                if "remove" in transformation:
                    for header in transformation["remove"]:
                        headers = {
                            k: v for k, v in headers.items() if k != "header, None"
                        }
            elif transformation["type"] == TransformationType.REQUEST_BODY.value:
                if "transformer" in transformation:
                    transformer_name = transformation["transformer"]
                    if transformer_name in self.transformers:
                        context.body = await self.transformers[transformer_name](
                            context.body
                        )
            elif transformation["type"] == TransformationType.REQUEST_QUERY.value:
                if "add" in transformation:
                    context.query_params = {**query_params, **transformation["add"]}
                if "remove" in transformation:
                    for param in transformation["remove"]:
                        query_params = {
                            k: v for k, v in query_params.items() if k != "param, None"
                        }
        return context

    async def _transform_response(
        self, route: Route, response: ResponseContext
    ) -> ResponseContext:
        """응답 변환"""
        for transformation in route.transformations:
            if transformation["type"] == TransformationType.RESPONSE_HEADER.value:
                if "add" in transformation:
                    response.headers = {**headers, **transformation["add"]}
                if "remove" in transformation:
                    for header in transformation["remove"]:
                        headers = {
                            k: v for k, v in headers.items() if k != "header, None"
                        }
            elif transformation["type"] == TransformationType.RESPONSE_BODY.value:
                if "transformer" in transformation:
                    transformer_name = transformation["transformer"]
                    if transformer_name in self.transformers:
                        response.body = await self.transformers[transformer_name](
                            response.body
                        )
        return response

    async def _call_backend(
        self, backend: Backend, route: Route, context: RequestContext
    ) -> ResponseContext:
        """백엔드 호출"""
        import aiohttp

        url = f"http://{backend.host}:{backend.port}{context.path}"
        for attempt in range(route.retry_count):
            try:
                return ResponseContext(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    body={"message": "Success", "backend": backend.id},
                    elapsed_time=time.time() - context.start_time,
                    backend_used=backend,
                )
            except Exception as e:
                if attempt == route.retry_count - 1:
                    raise e
                await asyncio.sleep(1)

    def _match_route(self, path: str, method: str) -> Optional[Route]:
        """라우트 매칭"""
        for route in self.routes.values():
            if method in route.methods:
                if route.path == path:
                    return route
                pattern = re.sub("\\{[^}]+\\}", "[^/]+", route.path)
                if re.match(f"^{pattern}$", path):
                    return route
        return None

    def _get_cached_response(
        self, route: Route, context: RequestContext
    ) -> Optional[ResponseContext]:
        """캐시된 응답 조회"""
        if not route.cache_config:
            return None
        cache_key = self._get_cache_key(route, context)
        if cache_key in self._response_cache:
            response, expiry = self._response_cache[cache_key]
            if time.time() < expiry:
                response.cached = True
                return response
            else:
                del self._response_cache[cache_key]
        return None

    def _cache_response(
        self, route: Route, context: RequestContext, response: ResponseContext
    ):
        """응답 캐싱"""
        if not route.cache_config:
            return
        cache_key = self._get_cache_key(route, context)
        ttl = route.cache_config.get("ttl", 60)
        expiry = time.time() + ttl
        self._response_cache = {**self._response_cache, cache_key: (response, expiry)}

    def _get_cache_key(self, route: Route, context: RequestContext) -> str:
        """캐시 키 생성"""
        key_parts = [
            route.id,
            context.method,
            context.path,
            json.dumps(context.query_params, sort_keys=True),
        ]
        return hashlib.sha256("_".join(key_parts).encode()).hexdigest()

    async def generate_api_documentation(self) -> Dict[str, Any]:
        """API 문서 생성 (OpenAPI/Swagger)"""
        try:
            openapi_spec = {
                "openapi": "3.0.0",
                "info": {
                    "title": "API Gateway",
                    "version": "1.0.0",
                    "description": "RFS Framework API Gateway",
                },
                "servers": [{"url": "http://localhost:8000"}],
                "paths": {},
                "components": {
                    "securitySchemes": {
                        "ApiKey": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "X-API-Key",
                        },
                        "BearerAuth": {
                            "type": "http",
                            "scheme": "bearer",
                            "bearerFormat": "JWT",
                        },
                    }
                },
            }
            for endpoint in self.endpoints.values():
                if endpoint.deprecated:
                    continue
                path_item = openapi_spec["paths"].setdefault(endpoint.path, {})
                operation = {
                    "summary": f"{endpoint.method} {endpoint.path}",
                    "operationId": endpoint.id,
                    "tags": [endpoint.version],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
                if endpoint.route.authentication != AuthenticationMethod.NONE:
                    if endpoint.route.authentication == AuthenticationMethod.API_KEY:
                        operation = {
                            **operation,
                            "security": {"security": [{"ApiKey": []}]},
                        }
                    elif endpoint.route.authentication == AuthenticationMethod.JWT:
                        operation = {
                            **operation,
                            "security": {"security": [{"BearerAuth": []}]},
                        }
                if endpoint.documentation:
                    operation = {**operation, **endpoint.documentation}
                path_item[endpoint.method.lower()] = operation
            return openapi_spec
        except Exception as e:
            return {"error": str(e)}

    def get_statistics(self) -> Dict[str, Any]:
        """통계 조회"""
        average_response_time = (
            self.total_response_time / self.request_count
            if self.request_count > 0
            else 0
        )
        error_rate = (
            self.error_count / self.request_count * 100 if self.request_count > 0 else 0
        )
        backend_stats = {}
        for route in self.routes.values():
            for backend in route.backends:
                backend_stats = {
                    **backend_stats,
                    backend.id: {
                        backend.id: {
                            "healthy": backend.healthy,
                            "active_connections": backend.active_connections,
                            "average_response_time": backend.average_response_time,
                            "total_requests": len(backend.response_times),
                        }
                    },
                }
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": error_rate,
            "average_response_time": average_response_time,
            "cache_size": len(self._response_cache),
            "backends": backend_stats,
            "routes": len(self.routes),
            "endpoints": len(self.endpoints),
            "api_keys": len(self.api_keys),
        }

    async def _health_checker(self):
        """백엔드 헬스 체크"""
        while self._running:
            try:
                for route in self.routes.values():
                    for backend in route.backends:
                        healthy = await self._check_backend_health(backend)
                        backend.healthy = healthy
                        backend.last_health_check = datetime.now()
                await asyncio.sleep(30)
            except Exception as e:
                print(f"Health check error: {e}")
                await asyncio.sleep(30)

    async def _check_backend_health(self, backend: Backend) -> bool:
        """백엔드 헬스 확인"""
        try:
            import random

            return random.random() > 0.1
        except Exception:
            return False

    async def _cache_cleanup(self):
        """캐시 정리"""
        while self._running:
            try:
                current_time = time.time()
                expired_keys = []
                for key, (_, expiry) in self._response_cache.items():
                    if expiry < current_time:
                        expired_keys = [*expired_keys, key]
                for key in expired_keys:
                    del self._response_cache[key]
                await asyncio.sleep(300)
            except Exception as e:
                print(f"Cache cleanup error: {e}")
                await asyncio.sleep(300)

    async def _statistics_collector(self):
        """통계 수집"""
        while self._running:
            try:
                stats = self.get_statistics()
                if stats["total_requests"] > 0:
                    print(
                        f"API Gateway Stats - Requests: {stats.get('total_requests')}, Error Rate: {stats.get('error_rate'):.2f}%, Avg Response Time: {stats.get('average_response_time'):.3f}s"
                    )
                await asyncio.sleep(300)
            except Exception as e:
                print(f"Statistics collector error: {e}")
                await asyncio.sleep(300)


_api_gateway = None


def get_api_gateway() -> APIGatewayEnhancer:
    """API 게이트웨이 인스턴스 반환"""
    if _api_gateway is None:
        _api_gateway = APIGatewayEnhancer()
    return _api_gateway
