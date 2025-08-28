"""
RFS REST API Gateway (RFS v4.1)

REST API 게이트웨이 구현
"""

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Union
from urllib.parse import parse_qs, urlparse

from rfs.core.result import Failure, Result, Success

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..security.auth import User, UserSession
from ..security.jwt import JWTService

logger = get_logger(__name__)


class HttpMethod(Enum):
    """HTTP 메소드"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ContentType(Enum):
    """콘텐츠 타입"""

    JSON = "application/json"
    XML = "application/xml"
    FORM = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    TEXT = "text/plain"
    HTML = "text/html"


@dataclass
class RestRequest:
    """REST 요청"""

    method: HttpMethod
    path: str
    headers: Dict[str, Any] = field(default_factory=dict)
    query_params: Dict[str, List[str]] = field(default_factory=dict)
    body = None
    json_body: Optional[Dict[str, Any]] = None
    path_params: Dict[str, Any] = field(default_factory=dict)
    remote_addr = None
    user_agent = None

    @property
    def content_type(self) -> Optional[str]:
        """콘텐츠 타입 반환"""
        return self.headers.get("content-type") or self.headers.get("Content-Type")

    def get_header(self, name: str) -> Optional[str]:
        """헤더 값 가져오기"""
        return self.headers.get(name) or self.headers.get(name.lower())

    def get_query_param(self, name: str, default=None) -> Optional[str]:
        """쿼리 파라미터 가져오기"""
        values = self.query_params.get(name, [])
        return values[0] if values else default

    def get_query_params(self, name: str) -> List[str]:
        """쿼리 파라미터 리스트 가져오기"""
        return self.query_params.get(name, [])

    def get_json(self) -> Optional[Dict[str, Any]]:
        """JSON 바디 파싱"""
        if self.json_body:
            return self.json_body
        if self.body and self.content_type == ContentType.JSON.value:
            self.json_body = json.loads(self.body.decode("utf-8"))
            return self.json_body
            return Failure("Operation failed")
        return None


@dataclass
class RestResponse:
    """REST 응답"""

    status_code = 200
    headers: Dict[str, Any] = field(default_factory=dict)
    body = None
    json_body: Optional[Dict[str, Any]] = None

    def set_json(self, data: Any):
        """JSON 응답 설정"""
        self.json_body = data
        self.body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.headers = {**self.headers, "Content-Type": ContentType.JSON.value}

    def set_text(self, text: str):
        """텍스트 응답 설정"""
        self.body = text.encode("utf-8")
        self.headers = {**self.headers, "Content-Type": ContentType.TEXT.value}

    def set_html(self, html: str):
        """HTML 응답 설정"""
        self.body = html.encode("utf-8")
        self.headers = {**self.headers, "Content-Type": ContentType.HTML.value}

    def set_header(self, name: str, value: str):
        """헤더 설정"""
        self.headers = {**self.headers, name: value}


class RestHandler(ABC):
    """REST 핸들러 추상 클래스"""

    @abstractmethod
    async def handle(self, request: RestRequest) -> Result[RestResponse, str]:
        """요청 처리"""
        pass


class JsonHandler(RestHandler):
    """JSON 응답 핸들러"""

    def __init__(self, handler_func: Callable[[RestRequest], Any]) -> None:
        self.handler_func = handler_func

    async def handle(self, request: RestRequest) -> Result[RestResponse, str]:
        """JSON 응답 처리"""
        try:
            if asyncio.iscoroutinefunction(self.handler_func):
                result = await self.handler_func(request)
            else:
                result = self.handler_func(request)
            response = RestResponse()
            response.set_json(result)
            return Success(response)
        except Exception as e:
            await logger.log_error(f"핸들러 실행 실패: {str(e)}")
            return Failure(f"핸들러 실행 실패: {str(e)}")


@dataclass
class RoutePattern:
    """라우트 패턴"""

    pattern: str
    regex: Pattern[str]
    param_names: List[str]

    @classmethod
    def create(cls, pattern: str) -> "RoutePattern":
        """패턴에서 RoutePattern 생성"""
        param_names: List[str] = []
        regex_pattern = pattern
        import re

        param_regex = re.compile("\\{([^}]+)\\}")
        for match in param_regex.finditer(pattern):
            param_name = match.group(1)
            param_names = param_names + [param_name]
            regex_pattern = regex_pattern.replace(
                f"{{{param_name}}}", f"(?P<{param_name}>[^/]+)"
            )
        regex_pattern = f"^{regex_pattern}$"
        return cls(
            pattern=pattern, regex=re.compile(regex_pattern), param_names=param_names
        )

    def match(self, path: str) -> Optional[Dict[str, str]]:
        """경로와 패턴 매칭"""
        match = self.regex.match(path)
        if match:
            return match.groupdict()
        return None


@dataclass
class RestRoute:
    """REST 라우트"""

    method: HttpMethod
    pattern: RoutePattern
    handler: RestHandler
    middleware: List["RestMiddleware"] = field(default_factory=list)

    def match(self, method: HttpMethod, path: str) -> Optional[Dict[str, str]]:
        """요청과 라우트 매칭"""
        if self.method == method:
            return self.pattern.match(path)
        return None


class RestMiddleware(ABC):
    """REST 미들웨어 추상 클래스"""

    @abstractmethod
    async def process_request(
        self, request: RestRequest
    ) -> Result[RestRequest, RestResponse]:
        """요청 전처리"""
        return Success(request)

    @abstractmethod
    async def process_response(
        self, request: RestRequest, response: RestResponse
    ) -> Result[RestResponse, str]:
        """응답 후처리"""
        return Success(response)


class CorsMiddleware(RestMiddleware):
    """CORS 미들웨어"""

    def __init__(
        self,
        allowed_origins: Optional[List[str]] = None,
        allowed_methods: Optional[List[str]] = None,
        allowed_headers: Optional[List[str]] = None,
        allow_credentials=False,
    ):
        self.allowed_origins = allowed_origins or ["*"]
        self.allowed_methods = allowed_methods or [
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
        ]
        self.allowed_headers = allowed_headers or ["Content-Type", "Authorization"]
        self.allow_credentials = allow_credentials

    async def process_request(
        self, request: RestRequest
    ) -> Result[RestRequest, RestResponse]:
        """CORS preflight 처리"""
        if request.method == HttpMethod.OPTIONS:
            response = RestResponse(status_code=200)
            response.set_header("Access-Control-Allow-Origin", self.allowed_origins[0])
            response.set_header(
                "Access-Control-Allow-Methods", ", ".join(self.allowed_methods)
            )
            response.set_header(
                "Access-Control-Allow-Headers", ", ".join(self.allowed_headers)
            )
            if self.allow_credentials:
                response.set_header("Access-Control-Allow-Credentials", "true")
            return Failure(response)
        return Success(request)

    async def process_response(
        self, request: RestRequest, response: RestResponse
    ) -> Result[RestResponse, str]:
        """CORS 헤더 추가"""
        origin = request.get_header("Origin")
        if origin and (origin in self.allowed_origins or "*" in self.allowed_origins):
            response.set_header("Access-Control-Allow-Origin", origin)
        elif "*" in self.allowed_origins:
            response.set_header("Access-Control-Allow-Origin", "*")
        if self.allow_credentials:
            response.set_header("Access-Control-Allow-Credentials", "true")
        return Success(response)


class LoggingMiddleware(RestMiddleware):
    """로깅 미들웨어"""

    async def process_request(
        self, request: RestRequest
    ) -> Result[RestRequest, RestResponse]:
        """요청 로깅"""
        await logger.log_info(
            f"{request.method.value} {request.path} - {request.remote_addr}"
        )
        request._start_time = time.time()
        return Success(request)

    async def process_response(
        self, request: RestRequest, response: RestResponse
    ) -> Result[RestResponse, str]:
        """응답 로깅"""
        duration = time.time() - getattr(request, "_start_time", time.time())
        await logger.log_info(
            f"{request.method.value} {request.path} - {response.status_code} - {duration:.3f}s"
        )
        return Success(response)


class AuthenticationMiddleware(RestMiddleware):
    """JWT 인증 미들웨어"""

    def __init__(
        self,
        jwt_service=None,
        exclude_paths: Optional[List[str]] = None,
        required_roles: Optional[List[str]] = None,
        required_permissions: Optional[List[tuple[str, str]]] = None,
    ):
        """인증 미들웨어 초기화

        Args:
            jwt_service: JWT 서비스 인스턴스
            exclude_paths: 인증을 제외할 경로 패턴 리스트
            required_roles: 필요한 역할 리스트
            required_permissions: 필요한 권한 리스트 (resource, action) 튜플
        """
        self.jwt_service = jwt_service or JWTService()
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/auth/login",
            "/auth/register",
        ]
        self.required_roles = required_roles or []
        self.required_permissions = required_permissions or []

    def _is_excluded_path(self, path: str) -> bool:
        """경로가 인증 제외 대상인지 확인"""
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return True
        return False

    async def process_request(
        self, request: RestRequest
    ) -> Result[RestRequest, RestResponse]:
        """JWT 토큰 검증 및 사용자 정보 추출"""

        # 제외 경로 확인
        if self._is_excluded_path(request.path):
            return Success(request)

        # Authorization 헤더 확인
        auth_header = request.get_header("Authorization")
        if not auth_header:
            error_response = RestResponse(status_code=401)
            error_response.set_json({"error": "Authorization header required"})
            return Failure(error_response)

        # Bearer 토큰 추출
        if not auth_header.startswith("Bearer "):
            error_response = RestResponse(status_code=401)
            error_response.set_json({"error": "Invalid authorization format"})
            return Failure(error_response)

        token = auth_header[7:]  # "Bearer " 제거

        # JWT 토큰 검증
        decode_result = await self.jwt_service.verify_token(token)
        if decode_result.is_failure():
            error_response = RestResponse(status_code=401)
            error_response.set_json({"error": "Invalid or expired token"})
            return Failure(error_response)

        payload = decode_result.value

        # 사용자 정보를 request에 추가
        request.user = payload.get("user")
        request.user_id = payload.get("user_id")
        request.roles = payload.get("roles", [])
        request.permissions = payload.get("permissions", [])

        # 역할 확인
        if self.required_roles:
            user_roles = set(request.roles)
            required_roles = set(self.required_roles)
            if not required_roles.intersection(user_roles):
                error_response = RestResponse(status_code=403)
                error_response.set_json({"error": "Insufficient role privileges"})
                return Failure(error_response)

        # 권한 확인
        if self.required_permissions:
            user_perms = set(map(tuple, request.permissions))
            required_perms = set(self.required_permissions)
            if not required_perms.issubset(user_perms):
                error_response = RestResponse(status_code=403)
                error_response.set_json({"error": "Insufficient permissions"})
                return Failure(error_response)

        return Success(request)

    async def process_response(
        self, request: RestRequest, response: RestResponse
    ) -> Result[RestResponse, str]:
        """응답에 사용자 정보 헤더 추가 (선택적)"""
        if hasattr(request, "user_id"):
            response.set_header("X-User-Id", str(request.user_id))
        return Success(response)


class RateLimitMiddleware(RestMiddleware):
    """레이트 리미팅 미들웨어"""

    def __init__(
        self,
        requests_per_minute=60,
        requests_per_hour=1000,
        by_user=True,
    ):
        """레이트 리미팅 미들웨어 초기화

        Args:
            requests_per_minute: 분당 최대 요청 수
            requests_per_hour: 시간당 최대 요청 수
            by_user: 사용자별 리미팅 여부 (False면 IP 기준)
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.by_user = by_user
        self._request_counts: Dict[str, List[float]] = {}

    def _get_identifier(self, request: RestRequest) -> str:
        """요청자 식별자 추출"""
        if self.by_user and hasattr(request, "user_id"):
            return f"user:{request.user_id}"
        return f"ip:{request.remote_addr or 'unknown'}"

    def _is_rate_limited(self, identifier: str) -> bool:
        """레이트 리미팅 확인"""
        current_time = time.time()

        # 요청 기록 초기화
        if identifier not in self._request_counts:
            self._request_counts[identifier] = []

        # 오래된 기록 제거 (1시간 이상)
        self._request_counts[identifier] = [
            t for t in self._request_counts[identifier] if current_time - t < 3600
        ]

        # 분당 제한 확인
        recent_minute = [
            t for t in self._request_counts[identifier] if current_time - t < 60
        ]
        if len(recent_minute) >= self.requests_per_minute:
            return True

        # 시간당 제한 확인
        if len(self._request_counts[identifier]) >= self.requests_per_hour:
            return True

        # 현재 요청 기록
        self._request_counts[identifier].append(current_time)
        return False

    async def process_request(
        self, request: RestRequest
    ) -> Result[RestRequest, RestResponse]:
        """레이트 리미팅 확인"""
        identifier = self._get_identifier(request)

        if self._is_rate_limited(identifier):
            error_response = RestResponse(status_code=429)
            error_response.set_json({"error": "Rate limit exceeded"})
            error_response.set_header("Retry-After", "60")
            return Failure(error_response)

        return Success(request)

    async def process_response(
        self, request: RestRequest, response: RestResponse
    ) -> Result[RestResponse, str]:
        """응답에 레이트 리미팅 정보 헤더 추가"""
        identifier = self._get_identifier(request)
        current_time = time.time()

        if identifier in self._request_counts:
            # 남은 요청 수 계산
            recent_minute = [
                t for t in self._request_counts[identifier] if current_time - t < 60
            ]
            remaining_minute = max(0, self.requests_per_minute - len(recent_minute))

            recent_hour = self._request_counts[identifier]
            remaining_hour = max(0, self.requests_per_hour - len(recent_hour))

            response.set_header(
                "X-RateLimit-Limit-Minute", str(self.requests_per_minute)
            )
            response.set_header("X-RateLimit-Remaining-Minute", str(remaining_minute))
            response.set_header("X-RateLimit-Limit-Hour", str(self.requests_per_hour))
            response.set_header("X-RateLimit-Remaining-Hour", str(remaining_hour))

        return Success(response)


@dataclass
class RouterConfig:
    """라우터 설정"""

    base_path = ""
    middleware: List[str] = field(default_factory=list)
    error_handler = None


class RestGateway:
    """REST API 게이트웨이"""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or RouterConfig()
        self.routes = []
        self.global_middleware = []

    def add_route(
        self,
        method: HttpMethod,
        pattern: str,
        handler: RestHandler,
        middleware: Optional[List[RestMiddleware]] = None,
    ):
        """라우트 추가"""
        full_pattern = self.config.base_path + pattern
        route_pattern = RoutePattern.create(full_pattern)
        route = RestRoute(
            method=method,
            pattern=route_pattern,
            handler=handler,
            middleware=middleware or [],
        )
        self.routes = self.routes + [route]

    def get(
        self,
        pattern: str,
        handler: Union[RestHandler, Callable],
        middleware: Optional[List[RestMiddleware]] = None,
    ):
        """GET 라우트 등록"""
        if not type(handler).__name__ == "RestHandler":
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.GET, pattern, handler, middleware)

    def post(
        self,
        pattern: str,
        handler: Union[RestHandler, Callable],
        middleware: Optional[List[RestMiddleware]] = None,
    ):
        """POST 라우트 등록"""
        if not type(handler).__name__ == "RestHandler":
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.POST, pattern, handler, middleware)

    def put(
        self,
        pattern: str,
        handler: Union[RestHandler, Callable],
        middleware: Optional[List[RestMiddleware]] = None,
    ):
        """PUT 라우트 등록"""
        if not type(handler).__name__ == "RestHandler":
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.PUT, pattern, handler, middleware)

    def delete(
        self,
        pattern: str,
        handler: Union[RestHandler, Callable],
        middleware: Optional[List[RestMiddleware]] = None,
    ):
        """DELETE 라우트 등록"""
        if not type(handler).__name__ == "RestHandler":
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.DELETE, pattern, handler, middleware)

    def find_route(
        self, method: HttpMethod, path: str
    ) -> Optional[tuple[RestRoute, Dict[str, str]]]:
        """라우트 찾기"""
        for route in self.routes:
            path_params = route.match(method, path)
            if path_params is not None:
                return (route, path_params)
        return None

    async def handle_request(self, request: RestRequest) -> Result[RestResponse, str]:
        """요청 처리"""
        try:
            route_match = self.find_route(request.method, request.path)
            if not route_match:
                error_response = RestResponse(status_code=404)
                error_response.set_json({"error": "Not Found"})
                return Success(error_response)
            route, path_params = route_match
            request.path_params = path_params
            all_middleware = self.global_middleware + route.middleware
            for middleware in all_middleware:
                result = await middleware.process_request(request)
                if result.is_failure():
                    return Success(result.unwrap_err())
                request = result.unwrap()
            handler_result = await route.handler.handle(request)
            if handler_result.is_failure():
                error_response = RestResponse(status_code=500)
                error_response.set_json({"error": handler_result.unwrap_err()})
                response = error_response
            else:
                response = handler_result.unwrap()
            for middleware in reversed(all_middleware):
                result = await middleware.process_response(request, response)
                if result.is_failure():
                    await logger.log_error(
                        f"미들웨어 응답 처리 실패: {result.unwrap_err()}"
                    )
                else:
                    response = result.unwrap()
            return Success(response)
        except Exception as e:
            await logger.log_error(f"요청 처리 실패: {str(e)}")
            error_response = RestResponse(status_code=500)
            error_response.set_json({"error": "Internal Server Error"})
            return Success(error_response)


def create_rest_gateway(
    base_path="", middleware: Optional[List[RestMiddleware]] = None
) -> RestGateway:
    """REST 게이트웨이 생성"""
    config = RouterConfig(base_path=base_path, middleware=middleware or [])
    return RestGateway(config)
