"""
RFS Web Server Integration (RFS v4.1)

현대적 웹 서버 통합 및 추상화 레이어
- FastAPI/Flask 통합 지원
- 자동 미들웨어 설정
- Cloud Run 최적화
- 비동기/동기 핸들러 지원
"""

from .handlers import (
    AsyncRequestHandler,
    ErrorHandler,
    RequestHandler,
    ResponseHandler,
    SyncRequestHandler,
    handle_error,
    handle_request,
)
from .middleware import (
    AuthMiddleware,
    CorsMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
    RFSMiddleware,
    SecurityMiddleware,
    get_middleware_stack,
    setup_middleware,
)
from .routing import (
    Route,
    RouteGroup,
    Router,
    RouteRegistry,
    delete,
    get,
    get_route_registry,
    patch,
    post,
    put,
    register_routes,
    route,
)
from .server import (
    RFSWebServer,
    WebFramework,
    WebServerConfig,
    create_fastapi_app,
    create_flask_app,
    get_web_server,
    shutdown_server,
    start_server,
)

__all__ = [
    # Server Core
    "RFSWebServer",
    "WebServerConfig",
    "WebFramework",
    "create_fastapi_app",
    "create_flask_app",
    "get_web_server",
    "start_server",
    "shutdown_server",
    # Middleware
    "RFSMiddleware",
    "CorsMiddleware",
    "AuthMiddleware",
    "LoggingMiddleware",
    "MetricsMiddleware",
    "SecurityMiddleware",
    "setup_middleware",
    "get_middleware_stack",
    # Routing
    "Router",
    "Route",
    "RouteGroup",
    "RouteRegistry",
    "route",
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "register_routes",
    "get_route_registry",
    # Handlers
    "RequestHandler",
    "ResponseHandler",
    "ErrorHandler",
    "AsyncRequestHandler",
    "SyncRequestHandler",
    "handle_request",
    "handle_error",
]

__version__ = "4.1.0"
__web_features__ = [
    "FastAPI/Flask 통합 지원",
    "자동 미들웨어 스택",
    "Cloud Run 최적화",
    "비동기/동기 핸들러",
    "자동 문서 생성",
    "메트릭 수집",
    "보안 헤더",
    "CORS 처리",
]
