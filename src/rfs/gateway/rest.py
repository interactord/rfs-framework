"""
RFS REST API Gateway (RFS v4.1)

REST API 게이트웨이 구현
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union, Callable, Pattern
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import re
from urllib.parse import parse_qs, urlparse

from ..core.result import Result, Success, Failure
from ..core.enhanced_logging import get_logger

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
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, List[str]] = field(default_factory=dict)
    body: Optional[bytes] = None
    json_body: Optional[Dict[str, Any]] = None
    path_params: Dict[str, str] = field(default_factory=dict)
    remote_addr: Optional[str] = None
    user_agent: Optional[str] = None
    
    @property
    def content_type(self) -> Optional[str]:
        """콘텐츠 타입 반환"""
        return self.headers.get("content-type") or self.headers.get("Content-Type")
    
    def get_header(self, name: str) -> Optional[str]:
        """헤더 값 가져오기"""
        return self.headers.get(name) or self.headers.get(name.lower())
    
    def get_query_param(self, name: str, default: Optional[str] = None) -> Optional[str]:
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
            try:
                self.json_body = json.loads(self.body.decode('utf-8'))
                return self.json_body
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        
        return None


@dataclass
class RestResponse:
    """REST 응답"""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[bytes] = None
    json_body: Optional[Dict[str, Any]] = None
    
    def set_json(self, data: Any):
        """JSON 응답 설정"""
        self.json_body = data
        self.body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.headers["Content-Type"] = ContentType.JSON.value
    
    def set_text(self, text: str):
        """텍스트 응답 설정"""
        self.body = text.encode('utf-8')
        self.headers["Content-Type"] = ContentType.TEXT.value
    
    def set_html(self, html: str):
        """HTML 응답 설정"""
        self.body = html.encode('utf-8')
        self.headers["Content-Type"] = ContentType.HTML.value
    
    def set_header(self, name: str, value: str):
        """헤더 설정"""
        self.headers[name] = value


class RestHandler(ABC):
    """REST 핸들러 추상 클래스"""
    
    @abstractmethod
    async def handle(self, request: RestRequest) -> Result[RestResponse, str]:
        """요청 처리"""
        pass


class JsonHandler(RestHandler):
    """JSON 응답 핸들러"""
    
    def __init__(self, handler_func: Callable[[RestRequest], Any]):
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
    def create(cls, pattern: str) -> 'RoutePattern':
        """패턴에서 RoutePattern 생성"""
        # URL 패턴을 정규식으로 변환
        param_names = []
        regex_pattern = pattern
        
        # {param} 형태의 파라미터를 정규식으로 변환
        import re
        param_regex = re.compile(r'\{([^}]+)\}')
        
        for match in param_regex.finditer(pattern):
            param_name = match.group(1)
            param_names.append(param_name)
            regex_pattern = regex_pattern.replace(
                f"{{{param_name}}}", 
                f"(?P<{param_name}>[^/]+)"
            )
        
        # 정확한 매치를 위해 ^ $ 추가
        regex_pattern = f"^{regex_pattern}$"
        
        return cls(
            pattern=pattern,
            regex=re.compile(regex_pattern),
            param_names=param_names
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
    middleware: List['RestMiddleware'] = field(default_factory=list)
    
    def match(self, method: HttpMethod, path: str) -> Optional[Dict[str, str]]:
        """요청과 라우트 매칭"""
        if self.method == method:
            return self.pattern.match(path)
        return None


class RestMiddleware(ABC):
    """REST 미들웨어 추상 클래스"""
    
    @abstractmethod
    async def process_request(self, request: RestRequest) -> Result[RestRequest, RestResponse]:
        """요청 전처리"""
        pass
    
    @abstractmethod
    async def process_response(self, request: RestRequest, response: RestResponse) -> Result[RestResponse, str]:
        """응답 후처리"""
        pass


class CorsMiddleware(RestMiddleware):
    """CORS 미들웨어"""
    
    def __init__(self, allowed_origins: List[str] = None, 
                 allowed_methods: List[str] = None,
                 allowed_headers: List[str] = None,
                 allow_credentials: bool = False):
        self.allowed_origins = allowed_origins or ["*"]
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        self.allowed_headers = allowed_headers or ["Content-Type", "Authorization"]
        self.allow_credentials = allow_credentials
    
    async def process_request(self, request: RestRequest) -> Result[RestRequest, RestResponse]:
        """CORS preflight 처리"""
        if request.method == HttpMethod.OPTIONS:
            response = RestResponse(status_code=200)
            response.set_header("Access-Control-Allow-Origin", self.allowed_origins[0])
            response.set_header("Access-Control-Allow-Methods", ", ".join(self.allowed_methods))
            response.set_header("Access-Control-Allow-Headers", ", ".join(self.allowed_headers))
            
            if self.allow_credentials:
                response.set_header("Access-Control-Allow-Credentials", "true")
            
            return Failure(response)  # 응답을 바로 반환
        
        return Success(request)
    
    async def process_response(self, request: RestRequest, response: RestResponse) -> Result[RestResponse, str]:
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
    
    async def process_request(self, request: RestRequest) -> Result[RestRequest, RestResponse]:
        """요청 로깅"""
        await logger.log_info(
            f"{request.method.value} {request.path} - {request.remote_addr}"
        )
        request._start_time = time.time()
        return Success(request)
    
    async def process_response(self, request: RestRequest, response: RestResponse) -> Result[RestResponse, str]:
        """응답 로깅"""
        duration = time.time() - getattr(request, '_start_time', time.time())
        
        await logger.log_info(
            f"{request.method.value} {request.path} - "
            f"{response.status_code} - {duration:.3f}s"
        )
        
        return Success(response)


@dataclass
class RouterConfig:
    """라우터 설정"""
    base_path: str = ""
    middleware: List[RestMiddleware] = field(default_factory=list)
    error_handler: Optional[Callable] = None


class RestGateway:
    """REST API 게이트웨이"""
    
    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()
        self.routes: List[RestRoute] = []
        self.global_middleware: List[RestMiddleware] = self.config.middleware
    
    def add_route(self, method: HttpMethod, pattern: str, handler: RestHandler,
                 middleware: Optional[List[RestMiddleware]] = None):
        """라우트 추가"""
        full_pattern = self.config.base_path + pattern
        route_pattern = RoutePattern.create(full_pattern)
        
        route = RestRoute(
            method=method,
            pattern=route_pattern,
            handler=handler,
            middleware=middleware or []
        )
        
        self.routes.append(route)
    
    def get(self, pattern: str, handler: Union[RestHandler, Callable],
           middleware: Optional[List[RestMiddleware]] = None):
        """GET 라우트 등록"""
        if not isinstance(handler, RestHandler):
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.GET, pattern, handler, middleware)
    
    def post(self, pattern: str, handler: Union[RestHandler, Callable],
            middleware: Optional[List[RestMiddleware]] = None):
        """POST 라우트 등록"""
        if not isinstance(handler, RestHandler):
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.POST, pattern, handler, middleware)
    
    def put(self, pattern: str, handler: Union[RestHandler, Callable],
           middleware: Optional[List[RestMiddleware]] = None):
        """PUT 라우트 등록"""
        if not isinstance(handler, RestHandler):
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.PUT, pattern, handler, middleware)
    
    def delete(self, pattern: str, handler: Union[RestHandler, Callable],
              middleware: Optional[List[RestMiddleware]] = None):
        """DELETE 라우트 등록"""
        if not isinstance(handler, RestHandler):
            handler = JsonHandler(handler)
        self.add_route(HttpMethod.DELETE, pattern, handler, middleware)
    
    def find_route(self, method: HttpMethod, path: str) -> Optional[tuple[RestRoute, Dict[str, str]]]:
        """라우트 찾기"""
        for route in self.routes:
            path_params = route.match(method, path)
            if path_params is not None:
                return route, path_params
        
        return None
    
    async def handle_request(self, request: RestRequest) -> Result[RestResponse, str]:
        """요청 처리"""
        try:
            # 라우트 찾기
            route_match = self.find_route(request.method, request.path)
            
            if not route_match:
                error_response = RestResponse(status_code=404)
                error_response.set_json({"error": "Not Found"})
                return Success(error_response)
            
            route, path_params = route_match
            request.path_params = path_params
            
            # 미들웨어 체인 구성
            all_middleware = self.global_middleware + route.middleware
            
            # 요청 전처리
            for middleware in all_middleware:
                result = await middleware.process_request(request)
                if result.is_failure():
                    # 미들웨어에서 응답을 반환한 경우
                    return Success(result.unwrap_err())
                request = result.unwrap()
            
            # 핸들러 실행
            handler_result = await route.handler.handle(request)
            
            if handler_result.is_failure():
                error_response = RestResponse(status_code=500)
                error_response.set_json({"error": handler_result.unwrap_err()})
                response = error_response
            else:
                response = handler_result.unwrap()
            
            # 응답 후처리
            for middleware in reversed(all_middleware):
                result = await middleware.process_response(request, response)
                if result.is_failure():
                    await logger.log_error(f"미들웨어 응답 처리 실패: {result.unwrap_err()}")
                else:
                    response = result.unwrap()
            
            return Success(response)
            
        except Exception as e:
            await logger.log_error(f"요청 처리 실패: {str(e)}")
            
            error_response = RestResponse(status_code=500)
            error_response.set_json({"error": "Internal Server Error"})
            
            return Success(error_response)


def create_rest_gateway(base_path: str = "", middleware: Optional[List[RestMiddleware]] = None) -> RestGateway:
    """REST 게이트웨이 생성"""
    config = RouterConfig(
        base_path=base_path,
        middleware=middleware or []
    )
    
    return RestGateway(config)