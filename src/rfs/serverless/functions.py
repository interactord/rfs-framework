"""
Serverless Functions Module

서버리스 함수 정의 및 관리 모듈
- 함수 라이프사이클 관리
- 이벤트 트리거
- HTTP 핸들러
"""

import asyncio
import functools
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.singleton import StatelessRegistry
from ..reactive import Flux, Mono

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """트리거 타입"""

    HTTP = "http"
    PUBSUB = "pubsub"
    STORAGE = "storage"
    FIRESTORE = "firestore"
    SCHEDULER = "scheduler"
    TASKS = "tasks"


class HttpMethod(Enum):
    """HTTP 메서드"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


@dataclass
class HttpTrigger:
    """HTTP 트리거"""

    methods: List[str] = field(default_factory=list)
    cors = True
    security_level = "SECURE_ALWAYS"


@dataclass
class PubSubTrigger:
    """Pub/Sub 트리거"""

    topic: str
    subscription = None


@dataclass
class FunctionConfig:
    """서버리스 함수 설정"""

    name: str
    runtime = "python311"
    memory = "256MB"
    timeout = 60
    environment_variables: Dict[str, Any] = field(default_factory=dict)
    trigger: Optional[Union[HttpTrigger, PubSubTrigger]] = None
    min_instances = 0
    max_instances = 100
    ingress_settings = "ALLOW_ALL"


@dataclass
class FunctionContext:
    """함수 실행 컨텍스트"""

    function_name: str
    execution_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    trigger_type = None
    request_id = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ServerlessFunction:
    """서버리스 함수 클래스"""

    def __init__(self, config: FunctionConfig, handler: Callable):
        self.config = config
        self.handler = handler
        self.execution_count = 0
        self.error_count = 0
        self.last_execution = None
        self.middlewares = []

    def add_middleware(self, middleware: Callable):
        """미들웨어 추가"""
        self.middlewares = self.middlewares + [middleware]

    async def execute(self, event: Dict[str, Any], context: FunctionContext) -> Any:
        """함수 실행"""
        execution_count = execution_count + 1
        self.last_execution = datetime.now()
        try:
            processed_event = event
            for middleware in self.middlewares:
                if asyncio.iscoroutinefunction(middleware):
                    processed_event = await middleware(processed_event, context)
                else:
                    processed_event = middleware(processed_event, context)
            if asyncio.iscoroutinefunction(self.handler):
                result = await self.handler(processed_event, context)
            else:
                result = self.handler(processed_event, context)
            return result
        except Exception as e:
            error_count = error_count + 1
            logger.error(f"Function {self.config.name} failed: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """함수 통계"""
        return {
            "name": self.config.name,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.execution_count, 1),
            "last_execution": (
                self.last_execution.isoformat() if self.last_execution else None
            ),
            "middleware_count": len(self.middlewares),
        }


class FunctionRegistry:
    """함수 레지스트리"""

    def __init__(self):
        self.functions = {}

    def register(self, function: ServerlessFunction):
        """함수 등록"""
        self.functions = {**self.functions, function.config.name: function}
        logger.info(f"Function registered: {function.config.name}")

    def get_function(self, name: str) -> Optional[ServerlessFunction]:
        """함수 조회"""
        return self.functions.get(name)

    def list_functions(self) -> List[str]:
        """등록된 함수 목록"""
        return list(self.functions.keys())

    def get_stats(self) -> Dict[str, Any]:
        """전체 통계"""
        return {
            "total_functions": len(self.functions),
            "functions": {
                name: func.get_stats() for name, func in self.functions.items()
            },
        }


class FunctionManager:
    """함수 관리자"""

    def __init__(self):
        self.registry = FunctionRegistry()
        self.global_middlewares = []

    def add_global_middleware(self, middleware: Callable):
        """전역 미들웨어 추가"""
        self.global_middlewares = self.global_middlewares + [middleware]

    def create_function(
        self, config: FunctionConfig, handler: Callable
    ) -> ServerlessFunction:
        """함수 생성"""
        function = ServerlessFunction(config, handler)
        for middleware in self.global_middlewares:
            function.add_middleware(middleware)
        self.registry.register(function)
        return function

    async def invoke_function(
        self,
        function_name: str,
        event: Dict[str, Any],
        context=None,
    ) -> Any:
        """함수 호출"""
        function = self.registry.get_function(function_name)
        if not function:
            raise ValueError(f"Function not found: {function_name}")
        if context is None:
            context = FunctionContext(
                function_name=function_name,
                execution_id=f"exec_{int(datetime.now().timestamp())}",
            )
        return await function.execute(event, context)


_manager = None


def get_manager() -> FunctionManager:
    """함수 관리자 인스턴스 획득"""
    # global _manager - removed for functional programming
    if _manager is None:
        _manager = FunctionManager()
    return _manager


def serverless_handler(config: FunctionConfig):
    """서버리스 핸들러 데코레이터"""

    def decorator(func: Callable) -> Callable:
        manager = get_manager()
        function = manager.create_function(config, func)

        @functools.wraps(func)
        async def wrapper(event: Dict[str, Any], context=None):
            if context is None:
                context = FunctionContext(
                    function_name=config.name,
                    execution_id=f"exec_{int(datetime.now().timestamp())}",
                )
            return await function.execute(event, context)

        wrapper._rfs_function = function
        wrapper._rfs_config = config
        return wrapper

    return decorator


def http_function(
    name: str,
    methods: List[HttpMethod] = None,
    memory="256MB",
    timeout=60,
):
    """HTTP 함수 데코레이터"""
    if methods is None:
        methods = [HttpMethod.POST]
    config = FunctionConfig(
        name=name, memory=memory, timeout=timeout, trigger=HttpTrigger(methods=methods)
    )
    return serverless_handler(config)


def pubsub_function(name: str, topic: str, memory="256MB", timeout=60):
    """Pub/Sub 함수 데코레이터"""
    config = FunctionConfig(
        name=name, memory=memory, timeout=timeout, trigger=PubSubTrigger(topic=topic)
    )
    return serverless_handler(config)


def middleware(func: Callable) -> Callable:
    """미들웨어 데코레이터"""

    @functools.wraps(func)
    async def wrapper(event: Dict[str, Any], context: FunctionContext):
        return (
            await func(event, context)
            if asyncio.iscoroutinefunction(func)
            else func(event, context)
        )

    get_manager().add_global_middleware(wrapper)
    return wrapper


@middleware
def logging_middleware(
    event: Dict[str, Any], context: FunctionContext
) -> Dict[str, Any]:
    """로깅 미들웨어"""
    logger.info(
        f"Function {context.function_name} called with execution_id: {context.execution_id}"
    )
    return event


@middleware
def cors_middleware(event: Dict[str, Any], context: FunctionContext) -> Dict[str, Any]:
    """CORS 미들웨어"""
    if context.trigger_type == TriggerType.HTTP:
        pass
    return event


@middleware
async def auth_middleware(
    event: Dict[str, Any], context: FunctionContext
) -> Dict[str, Any]:
    """인증 미들웨어"""
    auth_header = event.get("headers", {}).get("Authorization")
    if not auth_header:
        raise ValueError("Authorization header required")
    context.metadata = {**context.metadata, "authenticated": True}
    return event


def create_http_response(
    status_code=200, body: Any = None, headers: Dict[str, str] = None
) -> Dict[str, Any]:
    """HTTP 응답 생성"""
    response = {
        "statusCode": status_code,
        "headers": headers or {"Content-Type": "application/json"},
    }
    if body is not None:
        if type(body).__name__ in ["dict", "list"]:
            response["body"] = {"body": json.dumps(body)}
        else:
            response["body"] = {"body": str(body)}
    return response


def parse_http_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP 이벤트 파싱"""
    return {
        "method": event.get("httpMethod", "POST"),
        "path": event.get("path", "/"),
        "query_params": event.get("queryStringParameters", {}),
        "headers": event.get("headers", {}),
        "body": json.loads(event.get("body", "{}")) if event.get("body") else {},
    }


def parse_pubsub_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Pub/Sub 이벤트 파싱"""
    message = event.get("message", {})
    data = message.get("data", "")
    import base64

    try:
        decoded_data = base64.b64decode(data).decode("utf-8")
        return json.loads(decoded_data)
    except:
        return {"raw_data": data}


def function_chain(*functions: ServerlessFunction) -> Callable:
    """함수 체인"""

    async def chain_executor(event: Dict[str, Any], context: FunctionContext):
        result = event
        for function in functions:
            result = await function.execute(result, context)
        return result

    return chain_executor


async def reactive_function_handler(handler: Callable) -> Callable:
    """Reactive 함수 핸들러"""

    async def wrapper(event: Dict[str, Any], context: FunctionContext):
        return (
            await Mono.from_callable(lambda: handler(event, context))
            .map(lambda result: result)
            .on_error_return(lambda e: create_http_response(500, {"error": str(e)}))
            .await_result()
        )

    return wrapper


StatelessRegistry.register("function_manager", dependencies=[])(get_manager)
