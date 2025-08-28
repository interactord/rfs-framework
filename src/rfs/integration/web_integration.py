"""
Web Integration Manager for RFS Framework

고급 웹 통합 관리자:
- REST API 통합
- GraphQL 통합
- WebSocket 지원
- OAuth 2.0 / OpenID Connect
- Webhook 관리
- API 버전 관리
"""

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.parse import parse_qs, urlencode

import aiohttp
import jwt

from ..core.result import Failure, Result, Success


class IntegrationType(Enum):
    """통합 타입"""

    REST = "rest"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    WEBHOOK = "webhook"


class AuthType(Enum):
    """인증 타입"""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    JWT = "jwt"
    HMAC = "hmac"


class HTTPMethod(Enum):
    """HTTP 메소드"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class WebSocketState(Enum):
    """웹소켓 상태"""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class OAuthConfig:
    """OAuth 설정"""

    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    redirect_uri: str
    scopes: List[str] = field(default_factory=list)
    grant_type = "authorization_code"
    use_pkce = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookConfig:
    """Webhook 설정"""

    id: str
    name: str
    url: str
    events: List[str]
    secret = None
    headers: Dict[str, str] = field(default_factory=dict)
    retry_policy: Dict[str, Any] = field(
        default_factory=lambda: {
            "max_retries": 3,
            "initial_delay": 1,
            "max_delay": 60,
            "exponential_base": 2,
        }
    )
    active = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIEndpoint:
    """API 엔드포인트"""

    id: str
    name: str
    url: str
    method: HTTPMethod
    auth_type: AuthType
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, Any] = field(default_factory=dict)
    body_template: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    timeout = 30
    retry_count = 3
    cache_ttl = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIIntegration:
    """API 통합"""

    id: str
    name: str
    base_url: str
    integration_type: IntegrationType
    auth_config: Dict[str, Any]
    endpoints: Dict[str, APIEndpoint] = field(default_factory=dict)
    rate_limit: Optional[Dict[str, Any]] = None
    circuit_breaker: Dict[str, Any] = field(
        default_factory=lambda: {
            "failure_threshold": 5,
            "recovery_timeout": 60,
            "expected_exception": Exception,
        }
    )
    version = "v1"
    active = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphQLIntegration:
    """GraphQL 통합"""

    id: str
    name: str
    endpoint: str
    auth_type: AuthType
    auth_config: Dict[str, Any]
    schema: Optional[Dict[str, Any]] = None
    queries: Dict[str, str] = field(default_factory=dict)
    mutations: Dict[str, str] = field(default_factory=dict)
    subscriptions: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RESTIntegration:
    """REST API 통합"""

    id: str
    name: str
    base_url: str
    auth_type: AuthType
    auth_config: Dict[str, Any]
    resources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    api_version = "v1"
    use_hypermedia = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebSocketConnection:
    """WebSocket 연결"""

    id: str
    url: str
    state: WebSocketState
    session = None
    websocket = None
    heartbeat_interval = 30
    reconnect_attempts = 0
    max_reconnect_attempts = 5
    message_handlers: Dict[str, Callable] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimiter:
    """Rate Limiter"""

    requests_per_second: float
    burst_size: int
    current_tokens: float
    last_update: float = field(default_factory=time.time)

    def can_make_request(self) -> bool:
        """요청 가능 여부 확인"""
        now = time.time()
        time_passed = now - self.last_update
        self.current_tokens = min(
            self.burst_size,
            self.current_tokens + time_passed * self.requests_per_second,
        )
        self.last_update = now
        if self.current_tokens >= 1:
            self.current_tokens = self.current_tokens - 1
            return True
        return False


class CircuitBreaker:
    """Circuit Breaker 패턴 구현"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"

    def call(self, func, *args, **kwargs):
        """함수 호출"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception:
            self._on_failure()
            raise

    async def async_call(self, func, *args, **kwargs):
        """비동기 함수 호출"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """리셋 시도 여부"""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """성공 처리"""
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        """실패 처리"""
        failure_count = failure_count + 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class WebIntegrationManager:
    """웹 통합 관리자"""

    def __init__(self):
        self.integrations = {}
        self.webhooks = {}
        self.oauth_configs = {}
        self.websocket_connections = {}
        self.graphql_integrations = {}
        self.rest_integrations = {}
        self.rate_limiters = {}
        self.circuit_breakers = {}
        self._session = None
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._running = False
        self._tasks: Set[asyncio.Task] = set()

    async def start(self) -> Result[bool, str]:
        """통합 관리자 시작"""
        try:
            self._running = True
            if not self._session:
                self._session = aiohttp.ClientSession()
            cache_cleanup_task = asyncio.create_task(self._cache_cleanup())
            self._tasks.add(cache_cleanup_task)
            reconnect_task = asyncio.create_task(self._websocket_reconnector())
            self._tasks.add(reconnect_task)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start integration manager: {e}")

    async def stop(self) -> Result[bool, str]:
        """통합 관리자 중지"""
        try:
            self._running = False
            for conn in self.websocket_connections.values():
                await self.disconnect_websocket(conn.id)
            if self._session:
                await self._session.close()
                self._session = None
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                _tasks = {}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop integration manager: {e}")

    def add_integration(self, integration: APIIntegration) -> Result[bool, str]:
        """API 통합 추가"""
        try:
            if integration.id in self.integrations:
                return Failure(f"Integration {integration.id} already exists")
            self.integrations = {**self.integrations, integration.id: integration}
            if integration.rate_limit:
                self.rate_limiters = {
                    **self.rate_limiters,
                    integration.id: RateLimiter(
                        requests_per_second=integration.rate_limit.get(
                            "requests_per_second", 10
                        ),
                        burst_size=integration.rate_limit.get("burst_size", 20),
                    ),
                }
            if integration.circuit_breaker:
                self.circuit_breakers = {
                    **self.circuit_breakers,
                    integration.id: CircuitBreaker(
                        failure_threshold=integration.circuit_breaker.get(
                            "failure_threshold", 5
                        ),
                        recovery_timeout=integration.circuit_breaker.get(
                            "recovery_timeout", 60
                        ),
                    ),
                }
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add integration: {e}")

    def add_webhook(self, webhook: WebhookConfig) -> Result[bool, str]:
        """Webhook 추가"""
        try:
            if webhook.id in self.webhooks:
                return Failure(f"Webhook {webhook.id} already exists")
            self.webhooks = {**self.webhooks, webhook.id: webhook}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add webhook: {e}")

    def add_oauth_config(self, oauth_id: str, config: OAuthConfig) -> Result[bool, str]:
        """OAuth 설정 추가"""
        try:
            if oauth_id in self.oauth_configs:
                return Failure(f"OAuth config {oauth_id} already exists")
            self.oauth_configs = {**self.oauth_configs, oauth_id: config}
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add OAuth config: {e}")

    async def call_api(
        self,
        integration_id: str,
        endpoint_id: str,
        params: Dict[str, Any] = None,
        body: Dict[str, Any] = None,
    ) -> Result[Dict[str, Any], str]:
        """API 호출"""
        try:
            if integration_id not in self.integrations:
                return Failure(f"Integration {integration_id} not found")
            integration = self.integrations[integration_id]
            if endpoint_id not in integration.endpoints:
                return Failure(f"Endpoint {endpoint_id} not found")
            endpoint = integration.endpoints[endpoint_id]
            if integration_id in self.rate_limiters:
                limiter = self.rate_limiters[integration_id]
                if not limiter.can_make_request():
                    return Failure("Rate limit exceeded")
            cache_key = self._get_cache_key(integration_id, endpoint_id, params, body)
            if endpoint.cache_ttl > 0:
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    return Success(cached_result)
            if integration_id in self.circuit_breakers:
                breaker = self.circuit_breakers[integration_id]
                try:
                    result = await breaker.async_call(
                        self._make_http_request, integration, endpoint, params, body
                    )
                except Exception as e:
                    return Failure(f"Circuit breaker triggered: {e}")
            else:
                result = await self._make_http_request(
                    integration, endpoint, params, body
                )
            if type(result).__name__ == "Failure":
                return result
            if endpoint.cache_ttl > 0:
                self._cache_result(cache_key, result.value, endpoint.cache_ttl)
            return result
        except Exception as e:
            return Failure(f"Failed to call API: {e}")

    async def call_graphql(
        self,
        integration_id: str,
        query: str,
        variables: Dict[str, Any] = None,
        operation_name: str = None,
    ) -> Result[Dict[str, Any], str]:
        """GraphQL 호출"""
        try:
            if integration_id not in self.graphql_integrations:
                return Failure(f"GraphQL integration {integration_id} not found")
            integration = self.graphql_integrations[integration_id]
            request_body = {"query": query, "variables": variables or {}}
            if operation_name:
                request_body = {
                    **request_body,
                    "operationName": {"operationName": operation_name},
                }
            headers = await self._get_auth_headers(
                integration.auth_type, integration.auth_config
            )
            async with self._session.post(
                integration.endpoint, json=request_body, headers=headers
            ) as response:
                if response.status != 200:
                    return Failure(f"GraphQL request failed: {response.status}")
                data = await response.json()
                if "errors" in data:
                    return Failure(f"GraphQL errors: {data.get('errors')}")
                return Success(data.get("data", {}))
        except Exception as e:
            return Failure(f"Failed to call GraphQL: {e}")

    async def trigger_webhook(
        self, webhook_id: str, event: str, data: Dict[str, Any]
    ) -> Result[bool, str]:
        """Webhook 트리거"""
        try:
            if webhook_id not in self.webhooks:
                return Failure(f"Webhook {webhook_id} not found")
            webhook = self.webhooks[webhook_id]
            if not webhook.active:
                return Failure(f"Webhook {webhook_id} is not active")
            if event not in webhook.events:
                return Failure(f"Event {event} not configured for webhook")
            payload = {
                "webhook_id": webhook_id,
                "event": event,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            headers = dict(webhook.headers)
            if webhook.secret:
                signature = self._generate_webhook_signature(
                    json.dumps(payload), webhook.secret
                )
                headers = {
                    **headers,
                    "X-Webhook-Signature": {"X-Webhook-Signature": signature},
                }
            retry_policy = webhook.retry_policy
            for attempt in range(retry_policy["max_retries"] + 1):
                try:
                    async with self._session.post(
                        webhook.url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status < 300:
                            return Success(True)
                        if attempt < retry_policy["max_retries"]:
                            delay = min(
                                retry_policy["initial_delay"]
                                * retry_policy["exponential_base"] ** attempt,
                                retry_policy["max_delay"],
                            )
                            await asyncio.sleep(delay)
                        else:
                            return Failure(
                                f"Webhook failed after {retry_policy.get('max_retries')} retries"
                            )
                except Exception as e:
                    if attempt < retry_policy["max_retries"]:
                        delay = min(
                            retry_policy["initial_delay"]
                            * retry_policy["exponential_base"] ** attempt,
                            retry_policy["max_delay"],
                        )
                        await asyncio.sleep(delay)
                    else:
                        return Failure(f"Webhook failed: {e}")
            return Failure("Webhook failed")
        except Exception as e:
            return Failure(f"Failed to trigger webhook: {e}")

    async def connect_websocket(
        self, connection_id: str, url: str, message_handlers: Dict[str, Callable] = None
    ) -> Result[WebSocketConnection, str]:
        """WebSocket 연결"""
        try:
            if connection_id in self.websocket_connections:
                return Failure(f"WebSocket connection {connection_id} already exists")
            connection = WebSocketConnection(
                id=connection_id,
                url=url,
                state=WebSocketState.CONNECTING,
                message_handlers=message_handlers or {},
            )
            self.websocket_connections = {
                **self.websocket_connections,
                connection_id: connection,
            }
            connect_result = await self._establish_websocket_connection(connection)
            if type(connect_result).__name__ == "Failure":
                del self.websocket_connections[connection_id]
                return connect_result
            message_task = asyncio.create_task(
                self._handle_websocket_messages(connection)
            )
            self._tasks.add(message_task)
            heartbeat_task = asyncio.create_task(self._websocket_heartbeat(connection))
            self._tasks.add(heartbeat_task)
            return Success(connection)
        except Exception as e:
            return Failure(f"Failed to connect WebSocket: {e}")

    async def disconnect_websocket(self, connection_id: str) -> Result[bool, str]:
        """WebSocket 연결 해제"""
        try:
            if connection_id not in self.websocket_connections:
                return Failure(f"WebSocket connection {connection_id} not found")
            connection = self.websocket_connections[connection_id]
            connection.state = WebSocketState.DISCONNECTING
            if connection.websocket:
                await connection.websocket.close()
            if connection.session:
                await connection.session.close()
            connection.state = WebSocketState.DISCONNECTED
            del self.websocket_connections[connection_id]
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to disconnect WebSocket: {e}")

    async def send_websocket_message(
        self, connection_id: str, message: Union[str, Dict[str, Any]]
    ) -> Result[bool, str]:
        """WebSocket 메시지 전송"""
        try:
            if connection_id not in self.websocket_connections:
                return Failure(f"WebSocket connection {connection_id} not found")
            connection = self.websocket_connections[connection_id]
            if connection.state != WebSocketState.CONNECTED:
                return Failure(f"WebSocket not connected: {connection.state}")
            if type(message).__name__ == "dict":
                message = json.dumps(message)
            await connection.websocket.send_str(message)
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to send WebSocket message: {e}")

    async def get_oauth_token(
        self, oauth_id: str, authorization_code: str = None
    ) -> Result[Dict[str, Any], str]:
        """OAuth 토큰 획득"""
        try:
            if oauth_id not in self.oauth_configs:
                return Failure(f"OAuth config {oauth_id} not found")
            config = self.oauth_configs[oauth_id]
            token_data = {
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "redirect_uri": config.redirect_uri,
                "grant_type": config.grant_type,
            }
            if authorization_code:
                token_data["code"] = {"code": authorization_code}
            async with self._session.post(
                config.token_url, data=token_data
            ) as response:
                if response.status != 200:
                    return Failure(f"Failed to get OAuth token: {response.status}")
                token_info = await response.json()
                return Success(token_info)
        except Exception as e:
            return Failure(f"Failed to get OAuth token: {e}")

    def get_oauth_authorization_url(
        self, oauth_id: str, state: str = None
    ) -> Result[str, str]:
        """OAuth 인증 URL 생성"""
        try:
            if oauth_id not in self.oauth_configs:
                return Failure(f"OAuth config {oauth_id} not found")
            config = self.oauth_configs[oauth_id]
            params = {
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(config.scopes),
            }
            if state:
                params["state"] = {"state": state}
            if config.use_pkce:
                params["code_challenge"] = {"code_challenge": "challenge"}
                params = {
                    **params,
                    "code_challenge_method": {"code_challenge_method": "S256"},
                }
            authorization_url = f"{config.authorization_url}?{urlencode(params)}"
            return Success(authorization_url)
        except Exception as e:
            return Failure(f"Failed to generate OAuth URL: {e}")

    async def _make_http_request(
        self,
        integration: APIIntegration,
        endpoint: APIEndpoint,
        params: Dict[str, Any] = None,
        body: Dict[str, Any] = None,
    ) -> Result[Dict[str, Any], str]:
        """HTTP 요청 실행"""
        try:
            url = f"{integration.base_url}/{endpoint.url}".replace("//", "/").replace(
                ":/", "://"
            )
            headers = await self._get_auth_headers(
                endpoint.auth_type, integration.auth_config
            )
            headers = {**headers, **endpoint.headers}
            query_params = dict(endpoint.query_params)
            if params:
                query_params = {**query_params, **params}
            request_body = None
            if body or endpoint.body_template:
                request_body = dict(endpoint.body_template or {})
                if body:
                    request_body = {**request_body, **body}
            async with self._session.request(
                method=endpoint.method.value,
                url=url,
                params=query_params,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=endpoint.timeout),
            ) as response:
                if response.status >= 400:
                    return Failure(f"HTTP request failed: {response.status}")
                data = await response.json()
                return Success(data)
        except Exception as e:
            return Failure(f"HTTP request failed: {e}")

    async def _get_auth_headers(
        self, auth_type: AuthType, auth_config: Dict[str, Any]
    ) -> Dict[str, str]:
        """인증 헤더 생성"""
        headers = {}
        match auth_type:
            case AuthType.API_KEY:
                headers = {
                    **headers,
                    auth_config.get("header_name", "X-API-Key"): auth_config["api_key"],
                }
            case AuthType.BEARER_TOKEN:
                headers = {**headers, "Authorization": f"Bearer {auth_config['token']}"}
            case AuthType.BASIC:
                import base64

                credentials = base64.b64encode(
                    f"{auth_config.get('username')}:{auth_config.get('password')}".encode()
                ).decode()
                headers = {**headers, "Authorization": f"Basic {credentials}"}
            case AuthType.JWT:
                token = jwt.encode(
                    auth_config.get("payload", {}),
                    auth_config["secret"],
                    algorithm=auth_config.get("algorithm", "HS256"),
                )
                headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _establish_websocket_connection(
        self, connection: WebSocketConnection
    ) -> Result[bool, str]:
        """WebSocket 연결 수립"""
        try:
            connection.session = aiohttp.ClientSession()
            connection.websocket = await connection.session.ws_connect(connection.url)
            connection.state = WebSocketState.CONNECTED
            connection.reconnect_attempts = 0
            return Success(True)
        except Exception as e:
            connection.state = WebSocketState.ERROR
            return Failure(f"Failed to establish WebSocket connection: {e}")

    async def _handle_websocket_messages(self, connection: WebSocketConnection):
        """WebSocket 메시지 처리"""
        try:
            while self._running and connection.state == WebSocketState.CONNECTED:
                msg = await connection.websocket.receive()
                match msg.type:
                    case aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        for pattern, handler in connection.message_handlers.items():
                            if pattern in str(data):
                                await handler(data)
                    case aiohttp.WSMsgType.ERROR:
                        connection.state = WebSocketState.ERROR
                        break
                    case aiohttp.WSMsgType.CLOSED:
                        connection.state = WebSocketState.DISCONNECTED
                        break
        except Exception as e:
            print(f"WebSocket message handling error: {e}")
            connection.state = WebSocketState.ERROR

    async def _websocket_heartbeat(self, connection: WebSocketConnection):
        """WebSocket 하트비트"""
        try:
            while self._running and connection.state == WebSocketState.CONNECTED:
                await asyncio.sleep(connection.heartbeat_interval)
                if connection.websocket:
                    await connection.websocket.ping()
        except Exception as e:
            print(f"WebSocket heartbeat error: {e}")
            connection.state = WebSocketState.ERROR

    async def _websocket_reconnector(self):
        """WebSocket 재연결 관리"""
        while self._running:
            try:
                for connection in list(self.websocket_connections.values()):
                    if connection.state == WebSocketState.ERROR:
                        if (
                            connection.reconnect_attempts
                            < connection.max_reconnect_attempts
                        ):
                            reconnect_attempts = reconnect_attempts + 1
                            print(
                                f"Attempting WebSocket reconnection {connection.reconnect_attempts}/{connection.max_reconnect_attempts}"
                            )
                            await self._establish_websocket_connection(connection)
                            if connection.state == WebSocketState.CONNECTED:
                                message_task = asyncio.create_task(
                                    self._handle_websocket_messages(connection)
                                )
                                self._tasks.add(message_task)
                await asyncio.sleep(10)
            except Exception as e:
                print(f"WebSocket reconnector error: {e}")
                await asyncio.sleep(10)

    async def _cache_cleanup(self):
        """캐시 정리"""
        while self._running:
            try:
                current_time = time.time()
                expired_keys = [
                    key
                    for key, (_, expiry) in self._cache.items()
                    if expiry < current_time
                ]
                for key in expired_keys:
                    del self._cache[key]
                await asyncio.sleep(60)
            except Exception as e:
                print(f"Cache cleanup error: {e}")
                await asyncio.sleep(60)

    def _get_cache_key(
        self,
        integration_id: str,
        endpoint_id: str,
        params: Dict[str, Any] = None,
        body: Dict[str, Any] = None,
    ) -> str:
        """캐시 키 생성"""
        key_parts = [integration_id, endpoint_id]
        if params:
            key_parts = key_parts + [json.dumps(params, sort_keys=True)]
        if body:
            key_parts = key_parts + [json.dumps(body, sort_keys=True)]
        return hashlib.sha256("_".join(key_parts).encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """캐시된 결과 조회"""
        if cache_key in self._cache:
            data, expiry = self._cache[cache_key]
            if expiry > time.time():
                return data
            else:
                del self._cache[cache_key]
        return None

    def _cache_result(self, cache_key: str, data: Any, ttl: int):
        """결과 캐싱"""
        expiry = time.time() + ttl
        self._cache = {**self._cache, cache_key: (data, expiry)}

    def _generate_webhook_signature(self, payload: str, secret: str) -> str:
        """Webhook 서명 생성"""
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


_web_integration_manager = None


def get_web_integration_manager() -> WebIntegrationManager:
    """웹 통합 관리자 인스턴스 반환"""
    # global _web_integration_manager - removed for functional programming
    if _web_integration_manager is None:
        _web_integration_manager = WebIntegrationManager()
    return _web_integration_manager
