"""
RFS Web Server Core (RFS v4.1)

통합 웹 서버 구현체
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

try:
    from fastapi import FastAPI, Request, Response
    from fastapi.middleware.cors import CORSMiddleware

    FASTAPI_AVAILABLE = True
except ImportError:
    FastAPI = None
    Request = None
    Response = None
    CORSMiddleware = None
    FASTAPI_AVAILABLE = False

try:
    from flask import Flask, jsonify, request
    from flask_cors import CORS

    FLASK_AVAILABLE = True
except ImportError:
    Flask = None
    request = None
    jsonify = None
    CORS = None
    FLASK_AVAILABLE = False

from ..cloud_run.monitoring import record_metric
from ..core.config import get_config
from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = get_logger(__name__)


class WebFramework(str, Enum):
    """웹 프레임워크 타입"""

    FASTAPI = "fastapi"
    FLASK = "flask"
    AUTO = "auto"


@dataclass
class WebServerConfig:
    """웹 서버 설정"""

    framework: WebFramework = WebFramework.AUTO
    host = "0.0.0.0"
    port = 8080
    debug = False

    # CORS 설정
    enable_cors = True
    cors_origins: List[str] = field(default_factory=list)
    cors_methods: List[str] = field(default_factory=list)
    cors_headers: List[str] = field(default_factory=list)

    # 미들웨어 설정
    enable_logging = True
    enable_metrics = True
    enable_security_headers = True

    # Cloud Run 최적화
    cloud_run_optimized = True
    request_timeout = 300
    max_request_size = 32 * 1024 * 1024  # 32MB

    # 추가 설정
    extra_config: Dict[str, Any] = field(default_factory=dict)


class RFSWebServer:
    """RFS 통합 웹 서버"""

    def __init__(self, config: WebServerConfig = None):
        self.config = config or WebServerConfig()
        self.app: Optional[Union[FastAPI, Flask]] = None
        self.framework = None
        self._server_task = None
        self._startup_handlers = []
        self._shutdown_handlers = []

        # 프레임워크 결정
        self._determine_framework()

        # 앱 생성
        self._create_app()

    def _determine_framework(self):
        """사용할 프레임워크 결정"""
        match self.config.framework:
            case WebFramework.FASTAPI:
                if not FASTAPI_AVAILABLE:
                    raise RuntimeError(
                        "FastAPI가 설치되지 않았습니다. pip install fastapi[all] 실행"
                    )
                self.framework = WebFramework.FASTAPI
            case WebFramework.FLASK:
                if not FLASK_AVAILABLE:
                    raise RuntimeError(
                        "Flask가 설치되지 않았습니다. pip install flask flask-cors 실행"
                    )
                self.framework = WebFramework.FLASK
            case _:
                if FASTAPI_AVAILABLE:
                    self.framework = WebFramework.FASTAPI
                elif FLASK_AVAILABLE:
                    self.framework = WebFramework.FLASK
                else:
                    raise RuntimeError(
                        "FastAPI 또는 Flask 중 하나가 설치되어야 합니다."
                    )

        logger.info(f"웹 프레임워크 선택: {self.framework.value}")

    def _create_app(self):
        """웹 앱 생성"""
        if self.framework == WebFramework.FASTAPI:
            self.app = self._create_fastapi_app()
        else:
            self.app = self._create_flask_app()

    def _create_fastapi_app(self) -> FastAPI:
        """FastAPI 앱 생성"""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # 시작 시 실행
            await self._run_startup_handlers()
            yield
            # 종료 시 실행
            await self._run_shutdown_handlers()

        app = FastAPI(
            title="RFS Application",
            description="RFS Framework로 구축된 애플리케이션",
            version="1.0.0",
            debug=self.config.debug,
            lifespan=lifespan,
        )

        # CORS 설정
        if self.config.enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self.config.cors_origins,
                allow_credentials=True,
                allow_methods=self.config.cors_methods,
                allow_headers=self.config.cors_headers,
            )

        # 기본 엔드포인트
        self._setup_default_routes_fastapi(app)

        return app

    def _create_flask_app(self) -> Flask:
        """Flask 앱 생성"""
        app = Flask(__name__)
        app.config = {**app.config, "DEBUG": self.config.debug}

        # CORS 설정
        if self.config.enable_cors:
            CORS(app, origins=self.config.cors_origins)

        # 시작/종료 핸들러
        @app.before_first_request
        def startup():
            asyncio.create_task(self._run_startup_handlers())

        @app.teardown_appcontext
        def shutdown(exception):
            asyncio.create_task(self._run_shutdown_handlers())

        # 기본 엔드포인트
        self._setup_default_routes_flask(app)

        return app

    def _setup_default_routes_fastapi(self, app: FastAPI):
        """FastAPI 기본 라우트 설정"""

        @app.get("/")
        async def root():
            return {"message": "RFS Framework Application", "version": "4.1.0"}

        @app.get("/health")
        async def health():
            return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}

        @app.get("/ready")
        async def ready():
            return {"status": "ready", "timestamp": asyncio.get_event_loop().time()}

        @app.get("/metrics")
        async def metrics():
            # 간단한 메트릭 반환
            return {"requests_total": 0, "memory_usage": 0, "cpu_usage": 0}

    def _setup_default_routes_flask(self, app: Flask):
        """Flask 기본 라우트 설정"""

        @app.route("/")
        def root():
            return jsonify({"message": "RFS Framework Application", "version": "4.1.0"})

        @app.route("/health")
        def health():
            import time

            return jsonify({"status": "healthy", "timestamp": time.time()})

        @app.route("/ready")
        def ready():
            import time

            return jsonify({"status": "ready", "timestamp": time.time()})

        @app.route("/metrics")
        def metrics():
            return jsonify({"requests_total": 0, "memory_usage": 0, "cpu_usage": 0})

    async def _run_startup_handlers(self):
        """시작 핸들러 실행"""
        for handler in self._startup_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"시작 핸들러 실행 실패: {e}")

    async def _run_shutdown_handlers(self):
        """종료 핸들러 실행"""
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"종료 핸들러 실행 실패: {e}")

    def add_startup_handler(self, handler: Callable):
        """시작 핸들러 추가"""
        self._startup_handlers = self._startup_handlers + [handler]

    def add_shutdown_handler(self, handler: Callable):
        """종료 핸들러 추가"""
        self._shutdown_handlers = self._shutdown_handlers + [handler]

    async def start(self) -> Result[None, str]:
        """서버 시작"""
        try:
            if self.framework == WebFramework.FASTAPI:
                import uvicorn

                config = uvicorn.Config(
                    self.app,
                    host=self.config.host,
                    port=self.config.port,
                    log_level="debug" if self.config.debug else "info",
                    timeout_graceful_shutdown=30,
                )
                server = uvicorn.Server(config)
                self._server_task = asyncio.create_task(server.serve())
                await self._server_task

            else:  # Flask
                # Flask는 동기 서버이므로 별도 스레드에서 실행
                import threading

                def run_flask():
                    self.app.run(
                        host=self.config.host,
                        port=self.config.port,
                        debug=self.config.debug,
                        threaded=True,
                    )

                thread = threading.Thread(target=run_flask, daemon=True)
                thread.start()

                logger.info(f"웹 서버 시작: {self.config.host}:{self.config.port}")
                await record_metric("web_server_started", 1.0)

            return Success(None)

        except Exception as e:
            error_msg = f"서버 시작 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def stop(self) -> Result[None, str]:
        """서버 정지"""
        try:
            if self._server_task:
                self._server_task.cancel()
                try:
                    await self._server_task
                except asyncio.CancelledError:
                    pass

            logger.info("웹 서버 정지")
            await record_metric("web_server_stopped", 1.0)

            return Success(None)

        except Exception as e:
            error_msg = f"서버 정지 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    def get_app(self):
        """앱 인스턴스 반환"""
        return self.app


# 전역 서버 인스턴스
_web_server = None


def get_web_server(config: WebServerConfig = None) -> RFSWebServer:
    """웹 서버 인스턴스 반환"""
    global _web_server
    if _web_server is None:
        _web_server = RFSWebServer(config)
    return _web_server


def create_fastapi_app(config: WebServerConfig = None) -> FastAPI:
    """FastAPI 앱 생성"""
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI가 설치되지 않았습니다.")

    config = config or WebServerConfig(framework=WebFramework.FASTAPI)
    server = RFSWebServer(config)
    return server.get_app()


def create_flask_app(config: WebServerConfig = None) -> Flask:
    """Flask 앱 생성"""
    if not FLASK_AVAILABLE:
        raise RuntimeError("Flask가 설치되지 않았습니다.")

    config = config or WebServerConfig(framework=WebFramework.FLASK)
    server = RFSWebServer(config)
    return server.get_app()


async def start_server(config: WebServerConfig = None) -> Result[None, str]:
    """서버 시작"""
    server = get_web_server(config)
    return await server.start()


async def shutdown_server() -> Result[None, str]:
    """서버 종료"""
    global _web_server
    if _web_server:
        result = await _web_server.stop()
        _web_server = None
        return result
    return Success(None)


# Cloud Run 환경 감지 및 자동 설정
def _detect_cloud_run_config() -> WebServerConfig:
    """Cloud Run 환경에서 자동 설정 감지"""
    config = WebServerConfig()

    # Cloud Run 포트 감지
    port = os.environ.get("PORT")
    if port:
        config.port = int(port)

    # 프로덕션 환경 감지
    if os.environ.get("K_SERVICE"):
        config.debug = False
        config.cloud_run_optimized = True

    return config


# 자동 설정
if os.environ.get("K_SERVICE"):  # Cloud Run 환경
    _default_config = _detect_cloud_run_config()
else:
    _default_config = WebServerConfig()
