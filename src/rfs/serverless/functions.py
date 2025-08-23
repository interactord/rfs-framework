"""
Serverless Functions Module

서버리스 함수 정의 및 관리 모듈
- 함수 라이프사이클 관리
- 이벤트 트리거
- HTTP 핸들러
"""

import json
import asyncio
import functools
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from ..reactive import Mono, Flux
from ..core.singleton import StatelessRegistry

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
    methods: List[HttpMethod] = field(default_factory=lambda: [HttpMethod.POST])
    cors: bool = True
    security_level: str = "SECURE_ALWAYS"

@dataclass
class PubSubTrigger:
    """Pub/Sub 트리거"""
    topic: str
    subscription: Optional[str] = None

@dataclass
class FunctionConfig:
    """서버리스 함수 설정"""
    name: str
    runtime: str = "python311"
    memory: str = "256MB" 
    timeout: int = 60
    environment_variables: Dict[str, str] = field(default_factory=dict)
    trigger: Optional[Union[HttpTrigger, PubSubTrigger]] = None
    
    # Cold start 최적화
    min_instances: int = 0
    max_instances: int = 100
    ingress_settings: str = "ALLOW_ALL"

@dataclass
class FunctionContext:
    """함수 실행 컨텍스트"""
    function_name: str
    execution_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    trigger_type: Optional[TriggerType] = None
    request_id: Optional[str] = None
    
    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)

class ServerlessFunction:
    """서버리스 함수 클래스"""
    
    def __init__(self, config: FunctionConfig, handler: Callable):
        self.config = config
        self.handler = handler
        self.execution_count = 0
        self.error_count = 0
        self.last_execution: Optional[datetime] = None
        
        # 미들웨어 체인
        self.middlewares: List[Callable] = []
    
    def add_middleware(self, middleware: Callable):
        """미들웨어 추가"""
        self.middlewares.append(middleware)
    
    async def execute(self, event: Dict[str, Any], context: FunctionContext) -> Any:
        """함수 실행"""
        self.execution_count += 1
        self.last_execution = datetime.now()
        
        try:
            # 미들웨어 체인 실행
            processed_event = event
            for middleware in self.middlewares:
                if asyncio.iscoroutinefunction(middleware):
                    processed_event = await middleware(processed_event, context)
                else:
                    processed_event = middleware(processed_event, context)
            
            # 핸들러 실행
            if asyncio.iscoroutinefunction(self.handler):
                result = await self.handler(processed_event, context)
            else:
                result = self.handler(processed_event, context)
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Function {self.config.name} failed: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """함수 통계"""
        return {
            "name": self.config.name,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.execution_count, 1),
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "middleware_count": len(self.middlewares)
        }

class FunctionRegistry:
    """함수 레지스트리"""
    
    def __init__(self):
        self.functions: Dict[str, ServerlessFunction] = {}
    
    def register(self, function: ServerlessFunction):
        """함수 등록"""
        self.functions[function.config.name] = function
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
                name: func.get_stats() 
                for name, func in self.functions.items()
            }
        }

class FunctionManager:
    """함수 관리자"""
    
    def __init__(self):
        self.registry = FunctionRegistry()
        self.global_middlewares: List[Callable] = []
    
    def add_global_middleware(self, middleware: Callable):
        """전역 미들웨어 추가"""
        self.global_middlewares.append(middleware)
    
    def create_function(self, config: FunctionConfig, handler: Callable) -> ServerlessFunction:
        """함수 생성"""
        function = ServerlessFunction(config, handler)
        
        # 전역 미들웨어 적용
        for middleware in self.global_middlewares:
            function.add_middleware(middleware)
        
        self.registry.register(function)
        return function
    
    async def invoke_function(self, function_name: str, 
                            event: Dict[str, Any],
                            context: Optional[FunctionContext] = None) -> Any:
        """함수 호출"""
        function = self.registry.get_function(function_name)
        if not function:
            raise ValueError(f"Function not found: {function_name}")
        
        if context is None:
            context = FunctionContext(
                function_name=function_name,
                execution_id=f"exec_{int(datetime.now().timestamp())}"
            )
        
        return await function.execute(event, context)

# 전역 함수 관리자
_manager: Optional[FunctionManager] = None

def get_manager() -> FunctionManager:
    """함수 관리자 인스턴스 획득"""
    global _manager
    if _manager is None:
        _manager = FunctionManager()
    return _manager

# 데코레이터들
def serverless_handler(config: FunctionConfig):
    """서버리스 핸들러 데코레이터"""
    def decorator(func: Callable) -> Callable:
        manager = get_manager()
        function = manager.create_function(config, func)
        
        @functools.wraps(func)
        async def wrapper(event: Dict[str, Any], context: Optional[FunctionContext] = None):
            if context is None:
                context = FunctionContext(
                    function_name=config.name,
                    execution_id=f"exec_{int(datetime.now().timestamp())}"
                )
            
            return await function.execute(event, context)
        
        # 함수에 메타데이터 추가
        wrapper._rfs_function = function
        wrapper._rfs_config = config
        
        return wrapper
    return decorator

def http_function(name: str, 
                 methods: List[HttpMethod] = None,
                 memory: str = "256MB",
                 timeout: int = 60):
    """HTTP 함수 데코레이터"""
    if methods is None:
        methods = [HttpMethod.POST]
    
    config = FunctionConfig(
        name=name,
        memory=memory,
        timeout=timeout,
        trigger=HttpTrigger(methods=methods)
    )
    
    return serverless_handler(config)

def pubsub_function(name: str,
                   topic: str,
                   memory: str = "256MB", 
                   timeout: int = 60):
    """Pub/Sub 함수 데코레이터"""
    config = FunctionConfig(
        name=name,
        memory=memory,
        timeout=timeout,
        trigger=PubSubTrigger(topic=topic)
    )
    
    return serverless_handler(config)

def middleware(func: Callable) -> Callable:
    """미들웨어 데코레이터"""
    @functools.wraps(func)
    async def wrapper(event: Dict[str, Any], context: FunctionContext):
        return await func(event, context) if asyncio.iscoroutinefunction(func) else func(event, context)
    
    # 전역 미들웨어로 등록
    get_manager().add_global_middleware(wrapper)
    return wrapper

# 미들웨어 함수들
@middleware
def logging_middleware(event: Dict[str, Any], context: FunctionContext) -> Dict[str, Any]:
    """로깅 미들웨어"""
    logger.info(f"Function {context.function_name} called with execution_id: {context.execution_id}")
    return event

@middleware
def cors_middleware(event: Dict[str, Any], context: FunctionContext) -> Dict[str, Any]:
    """CORS 미들웨어"""
    if context.trigger_type == TriggerType.HTTP:
        # CORS 헤더 추가 로직
        pass
    return event

@middleware
async def auth_middleware(event: Dict[str, Any], context: FunctionContext) -> Dict[str, Any]:
    """인증 미들웨어"""
    # 인증 검사 로직
    auth_header = event.get('headers', {}).get('Authorization')
    if not auth_header:
        raise ValueError("Authorization header required")
    
    # 토큰 검증 로직
    context.metadata['authenticated'] = True
    return event

# 함수형 헬퍼들
def create_http_response(status_code: int = 200,
                        body: Any = None,
                        headers: Dict[str, str] = None) -> Dict[str, Any]:
    """HTTP 응답 생성"""
    response = {
        "statusCode": status_code,
        "headers": headers or {"Content-Type": "application/json"}
    }
    
    if body is not None:
        if isinstance(body, (dict, list)):
            response["body"] = json.dumps(body)
        else:
            response["body"] = str(body)
    
    return response

def parse_http_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP 이벤트 파싱"""
    return {
        "method": event.get("httpMethod", "POST"),
        "path": event.get("path", "/"),
        "query_params": event.get("queryStringParameters", {}),
        "headers": event.get("headers", {}),
        "body": json.loads(event.get("body", "{}")) if event.get("body") else {}
    }

def parse_pubsub_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Pub/Sub 이벤트 파싱"""
    message = event.get("message", {})
    data = message.get("data", "")
    
    # Base64 디코딩
    import base64
    try:
        decoded_data = base64.b64decode(data).decode('utf-8')
        return json.loads(decoded_data)
    except:
        return {"raw_data": data}

# 함수형 체이닝
def function_chain(*functions: ServerlessFunction) -> Callable:
    """함수 체인"""
    async def chain_executor(event: Dict[str, Any], context: FunctionContext):
        result = event
        for function in functions:
            result = await function.execute(result, context)
        return result
    
    return chain_executor

# Reactive 통합
async def reactive_function_handler(handler: Callable) -> Callable:
    """Reactive 함수 핸들러"""
    async def wrapper(event: Dict[str, Any], context: FunctionContext):
        return await (
            Mono.from_callable(lambda: handler(event, context))
            .map(lambda result: result)
            .on_error_return(lambda e: create_http_response(500, {"error": str(e)}))
            .await_result()
        )
    
    return wrapper

# Singleton 등록
StatelessRegistry.register("function_manager", dependencies=[])(get_manager)