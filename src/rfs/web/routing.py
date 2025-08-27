"""
RFS Web Routing (RFS v4.1)

통합 라우팅 시스템
"""

import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = get_logger(__name__, field)


class HTTPMethod(str, Enum):
    """HTTP 메소드"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class Route:
    """라우트 정의"""

    path: str
    method: HTTPMethod
    handler: Callable
    name = None
    tags: List[str] = field(default_factory=list)
    summary = None
    description = None
    middleware: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.middleware is None:
            self.middleware = []
        if self.name is None:
            self.name = (
                f"{self.method.lower()}_{self.path.replace('/', '_').strip('_')}"
            )


class RouteGroup:
    """라우트 그룹"""

    def __init__(self, prefix="", tags: List[str] = None, middleware: List[str] = None):
        self.prefix = prefix
        self.tags = tags or []
        self.middleware = middleware or []
        self.routes = []

    def add_route(
        self, path: str, method: HTTPMethod, handler: Callable, **kwargs
    ) -> Route:
        """라우트 추가"""
        full_path = f"{self.prefix.rstrip('/')}/{path.lstrip('/')}"
        if full_path.endswith("/") and full_path != "/":
            full_path = full_path.rstrip("/")
        route_tags = kwargs.get("tags", [])
        route_middleware = kwargs.get("middleware", [])
        kwargs["tags"] = {"tags": self.tags + route_tags}
        kwargs = {
            **kwargs,
            "middleware": {"middleware": self.middleware + route_middleware},
        }
        route = Route(path=full_path, method=method, handler=handler, **kwargs)
        self.routes = self.routes + [route]
        return route

    def get(self, path: str, **kwargs) -> Callable:
        """GET 라우트 데코레이터"""

        def decorator(handler: Callable):
            self.add_route(path, HTTPMethod.GET, handler, **kwargs)
            return handler

        return decorator

    def post(self, path: str, **kwargs) -> Callable:
        """POST 라우트 데코레이터"""

        def decorator(handler: Callable):
            self.add_route(path, HTTPMethod.POST, handler, **kwargs)
            return handler

        return decorator

    def put(self, path: str, **kwargs) -> Callable:
        """PUT 라우트 데코레이터"""

        def decorator(handler: Callable):
            self.add_route(path, HTTPMethod.PUT, handler, **kwargs)
            return handler

        return decorator

    def delete(self, path: str, **kwargs) -> Callable:
        """DELETE 라우트 데코레이터"""

        def decorator(handler: Callable):
            self.add_route(path, HTTPMethod.DELETE, handler, **kwargs)
            return handler

        return decorator

    def patch(self, path: str, **kwargs) -> Callable:
        """PATCH 라우트 데코레이터"""

        def decorator(handler: Callable):
            self.add_route(path, HTTPMethod.PATCH, handler, **kwargs)
            return handler

        return decorator


class Router:
    """메인 라우터"""

    def __init__(self):
        self.routes = []
        self.groups = []

    def add_route(
        self, path: str, method: HTTPMethod, handler: Callable, **kwargs
    ) -> Route:
        """라우트 추가"""
        route = Route(path=path, method=method, handler=handler, **kwargs)
        self.routes = self.routes + [route]
        logger.info(f"라우트 등록: {method.value} {path}")
        return route

    def include_group(self, group: RouteGroup):
        """라우트 그룹 포함"""
        self.groups = self.groups + [group]
        routes = [route for route in group.routes]
        logger.info(f"라우트 그룹 포함: {len(group.routes)}개 라우트")

    def get_routes(self) -> List[Route]:
        """모든 라우트 반환"""
        return self.routes.copy()

    def find_route(self, path: str, method: HTTPMethod) -> Optional[Route]:
        """라우트 찾기"""
        for route in self.routes:
            if route.path == path and route.method == method:
                return route
        return None

    def route(self, path: str, method: HTTPMethod, **kwargs) -> Callable:
        """범용 라우트 데코레이터"""

        def decorator(handler: Callable):
            self.add_route(path, method, handler, **kwargs)
            return handler

        return decorator

    def get(self, path: str, **kwargs) -> Callable:
        """GET 라우트 데코레이터"""
        return self.route(path, HTTPMethod.GET, **kwargs)

    def post(self, path: str, **kwargs) -> Callable:
        """POST 라우트 데코레이터"""
        return self.route(path, HTTPMethod.POST, **kwargs)

    def put(self, path: str, **kwargs) -> Callable:
        """PUT 라우트 데코레이터"""
        return self.route(path, HTTPMethod.PUT, **kwargs)

    def delete(self, path: str, **kwargs) -> Callable:
        """DELETE 라우트 데코레이터"""
        return self.route(path, HTTPMethod.DELETE, **kwargs)

    def patch(self, path: str, **kwargs) -> Callable:
        """PATCH 라우트 데코레이터"""
        return self.route(path, HTTPMethod.PATCH, **kwargs)


class RouteRegistry(metaclass=SingletonMeta):
    """라우트 레지스트리"""

    def __init__(self):
        self.router = Router()
        self._registered = False

    def register_route(
        self, path: str, method: HTTPMethod, handler: Callable, **kwargs
    ) -> Route:
        """라우트 등록"""
        return self.router.add_route(path, method, handler, **kwargs)

    def register_group(self, group: RouteGroup):
        """라우트 그룹 등록"""
        self.router.include_group(group)

    def get_all_routes(self) -> List[Route]:
        """모든 등록된 라우트 반환"""
        return self.router.get_routes()

    def apply_to_fastapi(self, app):
        """FastAPI 앱에 라우트 적용"""
        try:
            from fastapi import APIRouter

            api_router = APIRouter()
            for route in self.router.get_routes():
                match route.method:
                    case HTTPMethod.GET:
                        api_router.get(
                            route.path,
                            summary=route.summary,
                            description=route.description,
                            tags=route.tags,
                        )(route.handler)
                    case HTTPMethod.POST:
                        api_router.post(
                            route.path,
                            summary=route.summary,
                            description=route.description,
                            tags=route.tags,
                        )(route.handler)
                    case HTTPMethod.PUT:
                        api_router.put(
                            route.path,
                            summary=route.summary,
                            description=route.description,
                            tags=route.tags,
                        )(route.handler)
                    case HTTPMethod.DELETE:
                        api_router.delete(
                            route.path,
                            summary=route.summary,
                            description=route.description,
                            tags=route.tags,
                        )(route.handler)
                    case HTTPMethod.PATCH:
                        api_router.patch(
                            route.path,
                            summary=route.summary,
                            description=route.description,
                            tags=route.tags,
                        )(route.handler)
            app.include_router(api_router)
            logger.info(f"FastAPI에 {len(self.router.routes)}개 라우트 적용")
        except ImportError:
            logger.warning("FastAPI를 찾을 수 없어 라우트 적용을 건너뜁니다")

    def apply_to_flask(self, app):
        """Flask 앱에 라우트 적용"""
        try:
            for route in self.router.get_routes():
                methods = [route.method.value]
                app.add_url_rule(route.path, route.name, route.handler, methods=methods)
            logger.info(f"Flask에 {len(self.router.routes)}개 라우트 적용")
        except Exception as e:
            logger.warning(f"Flask 라우트 적용 실패: {e}")


def get_route_registry() -> RouteRegistry:
    """라우트 레지스트리 인스턴스 반환"""
    return RouteRegistry()


def register_routes(router_or_group: Union[Router, RouteGroup]):
    """라우트 등록"""
    registry = get_route_registry()
    if type(router_or_group).__name__ == "RouteGroup":
        registry.register_group(router_or_group)
    else:
        for route in router_or_group.get_routes():
            registry.register_route(
                route.path,
                route.method,
                route.handler,
                name=route.name,
                tags=route.tags,
                summary=route.summary,
                description=route.description,
            )


_global_router = Router()


def route(path: str, method: HTTPMethod, **kwargs) -> Callable:
    """글로벌 라우트 데코레이터"""

    def decorator(handler: Callable):
        registry = get_route_registry()
        registry.register_route(path, method, handler, **kwargs)
        return handler

    return decorator


def get(path: str, **kwargs) -> Callable:
    """글로벌 GET 데코레이터"""
    return route(path, HTTPMethod.GET, **kwargs)


def post(path: str, **kwargs) -> Callable:
    """글로벌 POST 데코레이터"""
    return route(path, HTTPMethod.POST, **kwargs)


def put(path: str, **kwargs) -> Callable:
    """글로벌 PUT 데코레이터"""
    return route(path, HTTPMethod.PUT, **kwargs)


def delete(path: str, **kwargs) -> Callable:
    """글로벌 DELETE 데코레이터"""
    return route(path, HTTPMethod.DELETE, **kwargs)


def patch(path: str, **kwargs) -> Callable:
    """글로벌 PATCH 데코레이터"""
    return route(path, HTTPMethod.PATCH, **kwargs)
