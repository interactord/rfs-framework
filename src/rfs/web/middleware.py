"""
RFS Web Middleware (RFS v4.1)

통합 미들웨어 시스템
"""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

from ..cloud_run.monitoring import record_metric
from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__, field)


class RFSMiddleware(ABC):
    """RFS 미들웨어 베이스 클래스"""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    @abstractmethod
    async def process_request(self, request: Any, call_next: Callable) -> Any:
        """요청 처리"""
        pass

    def enable(self):
        """미들웨어 활성화"""
        self.enabled = True

    def disable(self):
        """미들웨어 비활성화"""
        self.enabled = False


class LoggingMiddleware(RFSMiddleware):
    """로깅 미들웨어"""

    def __init__(self):
        super().__init__("logging")
        self.request_count = 0

    async def process_request(self, request: Any, call_next: Callable) -> Any:
        if not self.enabled:
            return await call_next(request)

        # 요청 ID 생성
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # 요청 정보 추출
        method = getattr(request, "method", "UNKNOWN")
        path = getattr(request, "url", {})
        path_str = (
            str(getattr(path, "path", "/")) if hasattr(path, "path") else str(path)
        )

        logger.info(
            f"요청 시작",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path_str,
                "start_time": start_time,
            },
        )

        try:
            # 다음 미들웨어/핸들러 실행
            response = await call_next(request)

            # 응답 시간 계산
            duration = time.time() - start_time
            status_code = getattr(response, "status_code", 200)

            logger.info(
                f"요청 완료",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path_str,
                    "status_code": status_code,
                    "duration_ms": duration * 1000,
                },
            )

            # 메트릭 기록
            await record_metric(
                "http_requests_total",
                1.0,
                {"method": method, "status_code": str(status_code)},
            )
            await record_metric("http_request_duration_ms", duration * 1000)

            request_count = request_count + 1

            return response

        except Exception as e:
            duration = time.time() - start_time

            logger.error(
                f"요청 실패: {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path_str,
                    "duration_ms": duration * 1000,
                    "error": str(e),
                },
            )

            # 에러 메트릭 기록
            await record_metric(
                "http_requests_total", 1.0, {"method": method, "status_code": "500"}
            )
            await record_metric("http_errors_total", 1.0)

            raise


class MetricsMiddleware(RFSMiddleware):
    """메트릭 수집 미들웨어"""

    def __init__(self):
        super().__init__("metrics")
        self.metrics = {}

    async def process_request(self, request: Any, call_next: Callable) -> Any:
        if not self.enabled:
            return await call_next(request)

        start_time = time.time()

        try:
            response = await call_next(request)

            # 성능 메트릭 수집
            duration = time.time() - start_time
            method = getattr(request, "method", "UNKNOWN")

            # 메트릭 업데이트
            metric_key = f"{method.lower()}_requests"
            self.metrics = {
                **self.metrics,
                metric_key: self.metrics.get(metric_key, 0) + 1,
            }
            self.metrics = {
                **self.metrics,
                "avg_response_time": (
                    self.metrics.get("avg_response_time", 0) * 0.9 + duration * 0.1
                ),
            }

            return response

        except Exception as e:
            self.metrics = {
                **self.metrics,
                "error_count": self.metrics.get("error_count", 0) + 1,
            }
            raise

    def get_metrics(self) -> Dict[str, float]:
        """현재 메트릭 반환"""
        return self.metrics.copy()


class SecurityMiddleware(RFSMiddleware):
    """보안 헤더 미들웨어"""

    def __init__(self):
        super().__init__("security")
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }

    async def process_request(self, request: Any, call_next: Callable) -> Any:
        if not self.enabled:
            return await call_next(request)

        response = await call_next(request)

        # 보안 헤더 추가
        if hasattr(response, "headers"):
            for header, value in self.security_headers.items():
                response.headers = {**response.headers, header: value}

        return response


class CorsMiddleware(RFSMiddleware):
    """CORS 미들웨어"""

    def __init__(
        self,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
    ):
        super().__init__("cors")
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or [
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
        ]
        self.allow_headers = allow_headers or ["*"]

    async def process_request(self, request: Any, call_next: Callable) -> Any:
        if not self.enabled:
            return await call_next(request)

        # OPTIONS 요청 처리
        method = getattr(request, "method", "GET")
        if method == "OPTIONS":
            # Preflight 응답 생성
            try:
                # FastAPI Response 생성 시도
                from fastapi import Response

                response = Response()
            except ImportError:
                try:
                    # Flask Response 생성 시도
                    from flask import make_response

                    response = make_response("", 200)
                except ImportError:
                    # 기본 응답
                    response = type(
                        "Response", (), {"headers": {}, "status_code": 200}
                    )()

            self._add_cors_headers(response, request)
            return response

        response = await call_next(request)
        self._add_cors_headers(response, request)

        return response

    def _add_cors_headers(self, response: Any, request: Any):
        """CORS 헤더 추가"""
        if hasattr(response, "headers"):
            response.headers = {
                **response.headers,
                "Access-Control-Allow-Origin": self.allow_origins[0],
            }
            response.headers = {
                **response.headers,
                "Access-Control-Allow-Methods": ", ".join(self.allow_methods),
            }
            response.headers = {
                **response.headers,
                "Access-Control-Allow-Headers": ", ".join(self.allow_headers),
            }
            response.headers = {
                **response.headers,
                "Access-Control-Allow-Credentials": "true",
            }


class AuthMiddleware(RFSMiddleware):
    """인증 미들웨어"""

    def __init__(self, secret_key: str = None):
        super().__init__("auth")
        self.secret_key = secret_key or "rfs-default-secret"
        self.excluded_paths = {"/health", "/ready", "/metrics", "/"}

    async def process_request(self, request: Any, call_next: Callable) -> Any:
        if not self.enabled:
            return await call_next(request)

        # 경로 확인
        path = self._get_path(request)
        if path in self.excluded_paths:
            return await call_next(request)

        # 인증 토큰 확인
        token = self._get_auth_token(request)
        if not token:
            return self._create_unauthorized_response()

        # 토큰 검증 (간단한 예제)
        if not self._validate_token(token):
            return self._create_unauthorized_response()

        return await call_next(request)

    def _get_path(self, request: Any) -> str:
        """요청 경로 추출"""
        if hasattr(request, "url") and hasattr(request.url, "path"):
            return request.url.path
        return "/"

    def _get_auth_token(self, request: Any) -> Optional[str]:
        """인증 토큰 추출"""
        if hasattr(request, "headers"):
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
        return None

    def _validate_token(self, token: str) -> bool:
        """토큰 검증 (간단한 예제)"""
        # 실제 구현에서는 JWT 검증 등을 수행
        return token == "valid-token"

    def _create_unauthorized_response(self):
        """401 응답 생성"""
        try:
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="인증이 필요합니다")
        except ImportError:
            try:
                from flask import jsonify

                response = jsonify({"error": "인증이 필요합니다"})
                response.status_code = 401
                return response
            except ImportError:
                return type(
                    "Response",
                    (),
                    {"status_code": 401, "body": '{"error": "인증이 필요합니다"}'},
                )()


class MiddlewareStack:
    """미들웨어 스택 관리자"""

    def __init__(self):
        self.middlewares = []

    def add(self, middleware: RFSMiddleware):
        """미들웨어 추가"""
        self.middlewares = middlewares + [middleware]
        logger.info(f"미들웨어 추가됨: {middleware.name}")

    def remove(self, middleware_name: str):
        """미들웨어 제거"""
        self.middlewares = [m for m in self.middlewares if m.name != middleware_name]
        logger.info(f"미들웨어 제거됨: {middleware_name}")

    def get(self, middleware_name: str) -> Optional[RFSMiddleware]:
        """미들웨어 조회"""
        for middleware in self.middlewares:
            if middleware.name == middleware_name:
                return middleware
        return None

    def get_all(self) -> List[RFSMiddleware]:
        """모든 미들웨어 반환"""
        return self.middlewares.copy()

    async def process_request(self, request: Any, handler: Callable) -> Any:
        """요청을 모든 미들웨어를 통해 처리"""

        async def _process_middleware(index: int, req: Any) -> Any:
            if index >= len(self.middlewares):
                return await handler(req)

            middleware = self.middlewares[index]
            if not middleware.enabled:
                return await _process_middleware(index + 1, req)

            return await middleware.process_request(
                req, lambda r: _process_middleware(index + 1, r)
            )

        return await _process_middleware(0, request)


# 전역 미들웨어 스택
_middleware_stack = None


def get_middleware_stack() -> MiddlewareStack:
    """미들웨어 스택 인스턴스 반환"""
    # global _middleware_stack - removed for functional programming
    if _middleware_stack is None:
        _middleware_stack = MiddlewareStack()
    return _middleware_stack


def setup_middleware(
    enable_logging=True,
    enable_metrics=True,
    enable_security=True,
    enable_cors=True,
    enable_auth=False,
    cors_origins: List[str] = None,
    auth_secret: str = None,
) -> MiddlewareStack:
    """기본 미들웨어 스택 설정"""
    stack = get_middleware_stack()

    if enable_logging:
        stack.add(LoggingMiddleware())

    if enable_metrics:
        stack.add(MetricsMiddleware())

    if enable_security:
        stack.add(SecurityMiddleware())

    if enable_cors:
        stack.add(CorsMiddleware(allow_origins=cors_origins))

    if enable_auth:
        stack.add(AuthMiddleware(secret_key=auth_secret))

    logger.info(f"미들웨어 스택 설정 완료: {len(stack.middlewares)}개")
    return stack
