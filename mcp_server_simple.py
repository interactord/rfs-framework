#!/usr/bin/env python3
"""
RFS Framework MCP Server - 간단한 버전

RFS (Reactive Functional Serverless) Framework의 문서와 패턴을 제공하는 MCP 서버
"""

import asyncio
import json
from typing import Any, Dict, List

# MCP 관련 imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Resource,
        Tool,
        TextContent,
        CallToolResult,
        ListResourcesResult,
        ReadResourceResult,
        ListToolsResult,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    raise ImportError("MCP not available. Install with: pip install mcp")


# 글로벌 서버 인스턴스
server = Server("rfs-framework")


@server.list_resources()
async def list_resources() -> ListResourcesResult:
    """사용 가능한 리소스 목록"""
    return ListResourcesResult(
        resources=[
            Resource(
                uri="rfs://framework/overview",
                name="RFS Framework 개요",
                description="Reactive Functional Serverless Framework 전체 개요",
                mimeType="text/markdown"
            ),
            Resource(
                uri="rfs://patterns/reactive",
                name="Reactive Patterns",
                description="Spring Reactor 패턴 (Flux/Mono) 사용법",
                mimeType="text/markdown"
            ),
            Resource(
                uri="rfs://patterns/functional",
                name="Functional Patterns",
                description="Railway Oriented Programming 패턴",
                mimeType="text/markdown"
            ),
            Resource(
                uri="rfs://patterns/serverless",
                name="Serverless Patterns", 
                description="서버리스 최적화 패턴",
                mimeType="text/markdown"
            ),
            Resource(
                uri="rfs://examples/basic",
                name="Basic Examples",
                description="기본 사용 예제들",
                mimeType="text/markdown"
            )
        ]
    )


@server.read_resource()
async def read_resource(uri: str) -> ReadResourceResult:
    """리소스 내용 반환"""
    
    if uri == "rfs://framework/overview":
        content = get_framework_overview()
    elif uri == "rfs://patterns/reactive":
        content = get_reactive_patterns()
    elif uri == "rfs://patterns/functional":
        content = get_functional_patterns()
    elif uri == "rfs://patterns/serverless":
        content = get_serverless_patterns()
    elif uri == "rfs://examples/basic":
        content = get_basic_examples()
    else:
        content = f"리소스를 찾을 수 없습니다: {uri}"
    
    return ReadResourceResult(
        contents=[TextContent(type="text", text=content)]
    )


@server.list_tools()
async def list_tools() -> ListToolsResult:
    """사용 가능한 도구 목록"""
    return ListToolsResult(
        tools=[
            Tool(
                name="generate_rfs_code",
                description="RFS Framework 패턴을 사용한 코드 생성",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "enum": ["reactive", "functional", "serverless", "state_machine"],
                            "description": "사용할 RFS 패턴"
                        },
                        "use_case": {
                            "type": "string",
                            "description": "구현하고자 하는 유스케이스"
                        }
                    },
                    "required": ["pattern", "use_case"]
                }
            ),
            Tool(
                name="explain_rfs_pattern",
                description="RFS 패턴 상세 설명",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "enum": ["reactive", "functional", "serverless", "state_machine", "di", "events"],
                            "description": "설명할 패턴"
                        },
                        "detail_level": {
                            "type": "string",
                            "enum": ["basic", "intermediate", "advanced"],
                            "description": "설명 수준",
                            "default": "basic"
                        }
                    },
                    "required": ["pattern"]
                }
            )
        ]
    )


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """도구 실행"""
    
    if name == "generate_rfs_code":
        pattern = arguments.get("pattern")
        use_case = arguments.get("use_case")
        
        code = generate_code_for_pattern(pattern, use_case)
        
        return CallToolResult(
            content=[TextContent(type="text", text=code)]
        )
    
    elif name == "explain_rfs_pattern":
        pattern = arguments.get("pattern")
        detail_level = arguments.get("detail_level", "basic")
        
        explanation = explain_pattern(pattern, detail_level)
        
        return CallToolResult(
            content=[TextContent(type="text", text=explanation)]
        )
    
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"알 수 없는 도구: {name}")]
        )


def get_framework_overview() -> str:
    """프레임워크 개요"""
    return """# RFS Framework 개요

## 🚀 RFS (Reactive Functional Serverless) Framework

RFS Framework는 Spring 생태계에서 영감을 받은 Python 함수형 리액티브 프로그래밍 프레임워크입니다.

### 🌟 핵심 패턴

#### 1. Spring Reactor 패턴
- **Flux**: 0-N 비동기 스트림 처리
- **Mono**: 0-1 비동기 값 처리
- **Operators**: map, filter, flatMap 등 함수형 연산자

#### 2. Railway Oriented Programming
- **Result[T, E]**: Success/Failure 명시적 에러 처리
- **함수 체이닝**: 안전한 파이프라인 구성

#### 3. Stateless Singleton (Spring Bean 스타일)
- **의존성 주입**: 무상태 싱글톤 패턴
- **생명주기 관리**: 자동 리소스 관리

#### 4. Spring StateMachine
- **상태 관리**: 복잡한 비즈니스 로직의 상태 기반 모델링
- **전이와 액션**: 상태 간 전이와 사이드 이펙트 관리

#### 5. 서버리스 최적화
- **Cold Start 최적화**: Google Cloud Run 최적화
- **리소스 모니터링**: 메모리/CPU 자동 모니터링

### 📦 설치

```bash
pip install rfs-framework
```

### 🎯 주요 사용 사례

- **비동기 스트림 처리**: 대용량 데이터 파이프라인
- **마이크로서비스**: 서버리스 기반 마이크로서비스
- **이벤트 기반 아키텍처**: CQRS, Event Sourcing
- **상태 머신**: 복잡한 비즈니스 워크플로우
"""


def get_reactive_patterns() -> str:
    """리액티브 패턴"""
    return """# Reactive Patterns (Spring Reactor 스타일)

## 🌊 Flux - 0-N 비동기 스트림

### 기본 사용법

```python
from rfs.reactive import Flux

# 리스트에서 Flux 생성
flux = Flux.from_iterable([1, 2, 3, 4, 5])

# 변환 연산
result = await flux.map(lambda x: x * 2).collect_list()
# [2, 4, 6, 8, 10]

# 필터링
filtered = await flux.filter(lambda x: x % 2 == 0).collect_list()
# [2, 4]
```

### 고급 연산

```python
# flatMap으로 중첩 스트림 처리
async def process_item(item):
    return Flux.from_iterable([item, item * 2])

result = await flux.flat_map(process_item).collect_list()

# 병렬 처리
result = await flux.parallel(4).map(expensive_operation).collect_list()
```

## 🔮 Mono - 0-1 비동기 값

### 기본 사용법

```python
from rfs.reactive import Mono

# 단일 값으로 Mono 생성
mono = Mono.just("Hello World")

# 변환
result = await mono.map(str.upper).block()
# "HELLO WORLD"

# 조건부 처리
result = await mono.filter(lambda x: len(x) > 5).block()
```

### 에러 처리

```python
# 에러 복구
mono = Mono.error(Exception("Something went wrong"))
result = await mono.on_error_return("Default Value").block()

# 재시도
result = await mono.retry(3).block()
```

## 🔄 백프레셔 (Backpressure) 제어

```python
# 요청 기반 풀링
flux = Flux.create(lambda sink: 
    sink.next("item1")
    sink.next("item2") 
    sink.complete()
)

# 버퍼링
buffered = flux.buffer(10)
```

## 🎯 실제 사용 예제

### 파일 스트림 처리

```python
from rfs.reactive import Flux
import aiofiles

async def process_large_file(file_path):
    return await (
        Flux.from_file_lines(file_path)
        .map(lambda line: line.strip())
        .filter(lambda line: len(line) > 0)
        .map(process_line)
        .buffer(1000)  # 1000개씩 배치 처리
        .flat_map(save_batch)
        .count()
    )
```

### API 호출 스트림

```python
from rfs.reactive import Flux
import httpx

async def fetch_user_data(user_ids):
    async with httpx.AsyncClient() as client:
        return await (
            Flux.from_iterable(user_ids)
            .parallel(5)  # 5개 병렬 요청
            .map(lambda uid: client.get(f"/users/{uid}"))
            .map(lambda response: response.json())
            .collect_list()
        )
```
"""


def get_functional_patterns() -> str:
    """함수형 패턴"""
    return """# Functional Patterns (Railway Oriented Programming)

## 🚂 Result[T, E] - 명시적 에러 처리

### 기본 개념

```python
from rfs.core import Result, success, failure

def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return failure("Division by zero")
    return success(a / b)

# 사용법
result = divide(10, 2)
if result.is_success():
    print(f"결과: {result.unwrap()}")  # 5.0
else:
    print(f"에러: {result.unwrap_error()}")
```

### 함수 체이닝

```python
def calculate_and_format(a: int, b: int) -> Result[str, str]:
    return (divide(a, b)
            .map(lambda x: x * 100)  # 백분율 변환
            .map(lambda x: f"{x:.2f}%"))  # 포맷팅

result = calculate_and_format(1, 4)  # Success("25.00%")
```

### bind (flatMap) 패턴

```python
def safe_sqrt(x: float) -> Result[float, str]:
    if x < 0:
        return failure("Negative number")
    return success(x ** 0.5)

def process_number(x: int) -> Result[str, str]:
    return (success(x)
            .bind(lambda n: divide(100, n))  # 100/x
            .bind(safe_sqrt)  # sqrt 적용
            .map(lambda r: f"결과: {r:.2f}"))

result = process_number(4)  # Success("결과: 5.00")
```

## 🔗 파이프라인 패턴

### pipe_results 사용

```python
from rfs.core import pipe_results

def validate_age(age: int) -> Result[int, str]:
    if age < 0:
        return failure("나이는 0보다 커야 합니다")
    if age > 150:
        return failure("나이가 너무 많습니다")
    return success(age)

def calculate_retirement_years(age: int) -> Result[int, str]:
    retirement_age = 65
    if age >= retirement_age:
        return failure("이미 은퇴 나이입니다")
    return success(retirement_age - age)

def format_years(years: int) -> Result[str, str]:
    return success(f"{years}년 후 은퇴")

# 파이프라인 구성
process_age = pipe_results(
    validate_age,
    calculate_retirement_years,
    format_years
)

result = process_age(30)  # Success("35년 후 은퇴")
```

## 🔄 고급 패턴

### traverse - 리스트 처리

```python
from rfs.core import traverse

def safe_parse_int(s: str) -> Result[int, str]:
    try:
        return success(int(s))
    except ValueError:
        return failure(f"'{s}'는 숫자가 아닙니다")

numbers = ["1", "2", "3", "invalid", "5"]
result = traverse(numbers, safe_parse_int)
# Failure("'invalid'는 숫자가 아닙니다")

valid_numbers = ["1", "2", "3", "4", "5"]  
result = traverse(valid_numbers, safe_parse_int)
# Success([1, 2, 3, 4, 5])
```

### combine_results - 여러 Result 결합

```python
from rfs.core import combine_results

name_result = success("Alice")
age_result = success(30)
email_result = success("alice@example.com")

combined = combine_results(name_result, age_result, email_result)
# Success(("Alice", 30, "alice@example.com"))

# 하나라도 실패하면 전체 실패
age_result = failure("나이가 유효하지 않음")
combined = combine_results(name_result, age_result, email_result)
# Failure("나이가 유효하지 않음")
```

## 🎯 실제 사용 예제

### API 요청 처리

```python
import httpx
from rfs.core import Result, success, failure, async_try_except

async def fetch_user(user_id: int) -> Result[dict, str]:
    async def make_request():
        async with httpx.AsyncClient() as client:
            response = await client.get(f"/api/users/{user_id}")
            response.raise_for_status()
            return response.json()
    
    return await async_try_except(make_request)

async def validate_user(user: dict) -> Result[dict, str]:
    if not user.get("email"):
        return failure("이메일이 없습니다")
    if not user.get("name"):
        return failure("이름이 없습니다")
    return success(user)

async def process_user(user_id: int) -> Result[str, str]:
    result = await fetch_user(user_id)
    return (result
            .bind(lambda user: validate_user(user))
            .map(lambda user: f"사용자: {user['name']} ({user['email']})"))
```

### 파일 처리 파이프라인

```python
from pathlib import Path
from rfs.core import Result, success, failure

def read_config_file(path: str) -> Result[str, str]:
    try:
        return success(Path(path).read_text())
    except FileNotFoundError:
        return failure(f"파일을 찾을 수 없습니다: {path}")
    except Exception as e:
        return failure(f"파일 읽기 실패: {e}")

def parse_json(content: str) -> Result[dict, str]:
    try:
        import json
        return success(json.loads(content))
    except json.JSONDecodeError as e:
        return failure(f"JSON 파싱 실패: {e}")

def validate_config(config: dict) -> Result[dict, str]:
    required_fields = ["database_url", "api_key"]
    for field in required_fields:
        if field not in config:
            return failure(f"필수 설정이 없습니다: {field}")
    return success(config)

# 설정 파일 처리 파이프라인
def load_config(config_path: str) -> Result[dict, str]:
    return (read_config_file(config_path)
            .bind(parse_json)
            .bind(validate_config))
```
"""


def get_serverless_patterns() -> str:
    """서버리스 패턴"""
    return """# Serverless Patterns (Google Cloud Run 최적화)

## ❄️ Cold Start 최적화

### Global Instance Pattern

```python
from rfs.serverless import ColdStartOptimizer, global_instance

# 글로벌 인스턴스로 초기화 비용 최소화
@global_instance
class DatabaseConnection:
    def __init__(self):
        self.pool = create_connection_pool()
    
    def get_connection(self):
        return self.pool.get_connection()

# 사용법
db = DatabaseConnection()  # 첫 호출에만 초기화
```

### Instance Warming

```python
from rfs.serverless import InstanceWarmer

warmer = InstanceWarmer(
    warm_up_endpoints=["/health", "/ready"],
    interval_minutes=5
)

@warmer.keep_warm
async def expensive_initialization():
    # 비용이 큰 초기화 작업
    load_ml_model()
    initialize_cache()
```

## 📊 Resource Monitoring

### Memory & CPU 모니터링

```python
from rfs.serverless import ResourceMonitor

monitor = ResourceMonitor()

@monitor.track_resources
async def process_request(data):
    # 리소스 사용량 자동 추적
    result = await heavy_computation(data)
    
    # 메모리 사용량이 임계치를 넘으면 자동 정리
    if monitor.memory_usage > 0.8:
        await cleanup_cache()
    
    return result
```

### Auto Scaling 최적화

```python
from rfs.serverless import ScalingOptimizer

optimizer = ScalingOptimizer(
    max_concurrent_requests=10,
    target_cpu_utilization=0.7
)

@optimizer.optimize_scaling
async def handle_request(request):
    # 동시 요청 수 제한
    async with optimizer.concurrency_limiter():
        return await process_request(request)
```

## 🗄️ State Management

### Stateless Pattern

```python
from rfs.core.singleton import StatelessSingleton

@StatelessSingleton
class ConfigManager:
    def __init__(self):
        self._config = None
    
    @property 
    def config(self):
        if self._config is None:
            self._config = load_from_env()
        return self._config
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)

# 어디서든 같은 인스턴스 사용
config = ConfigManager()
```

### External State Pattern

```python
from rfs.serverless import ExternalStateManager
import aioredis

class RedisStateManager(ExternalStateManager):
    def __init__(self):
        self.redis = None
    
    async def get_redis(self):
        if self.redis is None:
            self.redis = await aioredis.from_url("redis://...")
        return self.redis
    
    async def get_state(self, key: str):
        redis = await self.get_redis()
        return await redis.get(key)
    
    async def set_state(self, key: str, value: str):
        redis = await self.get_redis()
        await redis.set(key, value)
```

## ⚡ Performance Optimization

### Response Caching

```python
from rfs.serverless import ResponseCache

cache = ResponseCache(ttl_seconds=300)

@cache.cached_response
async def get_user_profile(user_id: int):
    # 비용이 큰 DB 조회
    return await db.fetch_user(user_id)
```

### Lazy Loading

```python
from rfs.serverless import LazyLoader

class MLModelService:
    def __init__(self):
        self._model = LazyLoader(self._load_model)
    
    def _load_model(self):
        # 모델은 실제 사용될 때 로드
        return load_expensive_ml_model()
    
    async def predict(self, data):
        model = await self._model.get()
        return model.predict(data)
```

## 🔄 Event-Driven Patterns

### Cloud Tasks Integration

```python
from rfs.serverless import CloudTasksManager

tasks = CloudTasksManager(
    project_id="my-project",
    queue_name="default"
)

@tasks.background_task
async def process_upload(file_path: str):
    # 백그라운드에서 처리될 작업
    await process_file(file_path)
    await notify_completion(file_path)

# 사용법
await tasks.enqueue("process_upload", file_path="/tmp/upload.jpg")
```

### Event Bus Pattern

```python
from rfs.events import EventBus

bus = EventBus()

@bus.subscribe("user.created")
async def send_welcome_email(event):
    user = event.data
    await email_service.send_welcome(user.email)

@bus.subscribe("user.created")
async def create_user_profile(event):
    user = event.data
    await profile_service.create(user.id)

# 이벤트 발행
await bus.publish("user.created", {"id": 123, "email": "user@example.com"})
```

## 🎯 실제 사용 예제

### FastAPI + RFS Integration

```python
from fastapi import FastAPI
from rfs.serverless import ColdStartOptimizer, ResourceMonitor
from rfs.core.singleton import StatelessSingleton

app = FastAPI()
optimizer = ColdStartOptimizer()
monitor = ResourceMonitor()

@StatelessSingleton
class DatabaseService:
    def __init__(self):
        self.pool = create_async_pool()

@app.on_event("startup")
async def startup():
    await optimizer.warm_up()

@app.post("/process")
@monitor.track_resources
async def process_data(data: dict):
    db = DatabaseService()
    
    # 리소스 모니터링하며 처리
    async with monitor.memory_tracker():
        result = await db.process_heavy_data(data)
    
    return result
```

### Batch Processing

```python
from rfs.reactive import Flux
from rfs.serverless import ResourceMonitor

monitor = ResourceMonitor()

async def process_large_dataset(items):
    return await (
        Flux.from_iterable(items)
        .buffer(100)  # 100개씩 배치
        .map(lambda batch: process_batch_with_monitoring(batch))
        .collect_list()
    )

async def process_batch_with_monitoring(batch):
    if monitor.memory_usage > 0.8:
        # 메모리 부족 시 가비지 컬렉션
        import gc
        gc.collect()
    
    return await process_batch(batch)
```
"""


def get_basic_examples() -> str:
    """기본 예제"""
    return """# RFS Framework 기본 예제

## 🚀 시작하기

### 1. 기본 설치 및 설정

```bash
pip install rfs-framework
```

### 2. Reactive Stream 기본 예제

```python
from rfs.reactive import Flux, Mono
import asyncio

async def basic_flux_example():
    # 숫자 스트림 생성
    numbers = Flux.from_iterable([1, 2, 3, 4, 5])
    
    # 변환 및 수집
    result = await numbers.map(lambda x: x * 2).collect_list()
    print(result)  # [2, 4, 6, 8, 10]

async def basic_mono_example():
    # 단일 값 처리
    greeting = Mono.just("Hello")
    result = await greeting.map(lambda x: x + " World!").block()
    print(result)  # "Hello World!"

# 실행
asyncio.run(basic_flux_example())
asyncio.run(basic_mono_example())
```

### 3. Railway Oriented Programming 기본 예제

```python
from rfs.core import Result, success, failure

def safe_divide(a: float, b: float) -> Result[float, str]:
    if b == 0:
        return failure("0으로 나눌 수 없습니다")
    return success(a / b)

# 성공 케이스
result = safe_divide(10, 2)
if result.is_success():
    print(f"결과: {result.unwrap()}")  # 결과: 5.0

# 실패 케이스
result = safe_divide(10, 0)
if result.is_failure():
    print(f"에러: {result.unwrap_error()}")  # 에러: 0으로 나눌 수 없습니다
```

### 4. Stateless Singleton 기본 예제

```python
from rfs.core.singleton import StatelessSingleton

@StatelessSingleton
class ConfigManager:
    def __init__(self):
        self.settings = {"database_url": "sqlite:///app.db"}
    
    def get(self, key: str):
        return self.settings.get(key)

# 어디서든 같은 인스턴스
config1 = ConfigManager()
config2 = ConfigManager()
print(config1 is config2)  # True
```

## 🔄 조합된 패턴 예제

### File Processing Pipeline

```python
from rfs.reactive import Flux
from rfs.core import Result, success, failure
import aiofiles
import json

async def process_json_files(file_paths):
    \"\"\"JSON 파일들을 스트림으로 처리\"\"\"
    
    async def read_and_parse(file_path):
        try:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                data = json.loads(content)
                return success({"file": file_path, "data": data})
        except Exception as e:
            return failure(f"파일 처리 실패 {file_path}: {e}")
    
    # Reactive + Functional 패턴 결합
    results = await (
        Flux.from_iterable(file_paths)
        .map(read_and_parse)
        .filter(lambda result: result.is_success())  # 성공한 것만 필터링
        .map(lambda result: result.unwrap())  # 값 추출
        .collect_list()
    )
    
    return results
```

### Web API with Error Handling

```python
from fastapi import FastAPI, HTTPException
from rfs.core import Result, success, failure
from rfs.core.singleton import StatelessSingleton

app = FastAPI()

@StatelessSingleton
class UserService:
    def __init__(self):
        self.users = {1: {"name": "Alice", "email": "alice@example.com"}}
    
    def get_user(self, user_id: int) -> Result[dict, str]:
        user = self.users.get(user_id)
        if user:
            return success(user)
        return failure(f"사용자를 찾을 수 없습니다: {user_id}")

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    service = UserService()
    result = service.get_user(user_id)
    
    if result.is_success():
        return result.unwrap()
    else:
        raise HTTPException(status_code=404, detail=result.unwrap_error())
```

### Event-Driven Processing

```python
from rfs.events import EventBus
from rfs.reactive import Flux

# 이벤트 버스 설정
bus = EventBus()

@bus.subscribe("data.received")
async def process_data(event):
    data = event.data
    print(f"데이터 처리 중: {data}")
    
    # 스트림으로 처리
    if isinstance(data, list):
        result = await (
            Flux.from_iterable(data)
            .map(lambda item: item * 2)
            .collect_list()
        )
        print(f"처리 결과: {result}")

# 이벤트 발행
async def main():
    await bus.publish("data.received", [1, 2, 3, 4, 5])

import asyncio
asyncio.run(main())
```

## 🎯 실전 사용 패턴

### 1. 데이터 파이프라인

```python
from rfs.reactive import Flux
from rfs.core import Result, pipe_results

async def data_pipeline(raw_data):
    \"\"\"데이터 파이프라인 예제\"\"\"
    
    # 검증 함수들
    def validate_not_empty(data) -> Result[list, str]:
        if not data:
            return failure("데이터가 비어있습니다")
        return success(data)
    
    def validate_all_numbers(data) -> Result[list, str]:
        if not all(isinstance(x, (int, float)) for x in data):
            return failure("모든 데이터가 숫자여야 합니다")
        return success(data)
    
    # 파이프라인 구성
    validate_pipeline = pipe_results(
        validate_not_empty,
        validate_all_numbers
    )
    
    # 검증
    validation_result = validate_pipeline(raw_data)
    if validation_result.is_failure():
        return validation_result.unwrap_error()
    
    # 스트림 처리
    processed = await (
        Flux.from_iterable(validation_result.unwrap())
        .filter(lambda x: x > 0)  # 양수만
        .map(lambda x: x ** 2)    # 제곱
        .collect_list()
    )
    
    return processed

# 사용 예제
import asyncio

async def main():
    # 성공 케이스
    result1 = await data_pipeline([1, 2, 3, 4, 5])
    print(f"결과1: {result1}")  # [1, 4, 9, 16, 25]
    
    # 실패 케이스
    result2 = await data_pipeline([])
    print(f"결과2: {result2}")  # "데이터가 비어있습니다"

asyncio.run(main())
```

### 2. 마이크로서비스 패턴

```python
from fastapi import FastAPI
from rfs.core.singleton import StatelessSingleton
from rfs.serverless import ResourceMonitor
from rfs.core import Result, success, failure

app = FastAPI()
monitor = ResourceMonitor()

@StatelessSingleton
class OrderService:
    def __init__(self):
        self.orders = {}
        self.next_id = 1
    
    def create_order(self, user_id: int, items: list) -> Result[dict, str]:
        if not items:
            return failure("주문 항목이 없습니다")
        
        order = {
            "id": self.next_id,
            "user_id": user_id,
            "items": items,
            "status": "created"
        }
        
        self.orders[self.next_id] = order
        self.next_id += 1
        
        return success(order)

@app.post("/orders")
@monitor.track_resources
async def create_order(user_id: int, items: list):
    service = OrderService()
    result = service.create_order(user_id, items)
    
    if result.is_success():
        return result.unwrap()
    else:
        return {"error": result.unwrap_error()}
```

이러한 예제들을 통해 RFS Framework의 다양한 패턴들을 조합하여 실전에서 활용할 수 있습니다.
"""


def generate_code_for_pattern(pattern: str, use_case: str) -> str:
    """패턴별 코드 생성"""
    
    if pattern == "reactive":
        return f"""# Reactive Stream 코드: {use_case}

from rfs.reactive import Flux, Mono
import asyncio

async def process_stream():
    # {use_case}을 위한 리액티브 스트림
    
    # 데이터 스트림 생성
    stream = Flux.from_iterable(range(1, 11))
    
    # 스트림 처리 파이프라인
    result = await (stream
                   .map(lambda x: x * 2)  # 변환
                   .filter(lambda x: x > 5)  # 필터링
                   .take(5)  # 상위 5개
                   .collect_list())  # 수집
    
    return result

# 실행
if __name__ == "__main__":
    result = asyncio.run(process_stream())
    print(f"{use_case} 결과: {{result}}")
"""
    
    elif pattern == "functional":
        return f"""# Functional Programming 코드: {use_case}

from rfs.core import Result, success, failure, pipe_results

def validate_input(data) -> Result[dict, str]:
    \"""입력 데이터 검증\"""
    if not data:
        return failure("데이터가 없습니다")
    return success(data)

def process_data(data) -> Result[dict, str]:
    \"""{use_case} 데이터 처리\"""
    try:
        # 실제 처리 로직
        processed = {{"result": data, "status": "processed"}}
        return success(processed)
    except Exception as e:
        return failure(f"처리 실패: {{e}}")

def format_output(data) -> Result[str, str]:
    \"""출력 포맷팅\"""
    return success(f"{use_case} 완료: {{data['result']}}")

# 파이프라인 구성
process_pipeline = pipe_results(
    validate_input,
    process_data,
    format_output
)

# 사용 예제
if __name__ == "__main__":
    result = process_pipeline({{"input": "sample data"}})
    
    if result.is_success():
        print(result.unwrap())
    else:
        print(f"오류: {{result.unwrap_error()}}")
"""
    
    elif pattern == "serverless":
        return f"""# Serverless 최적화 코드: {use_case}

from rfs.serverless import ColdStartOptimizer, ResourceMonitor
from rfs.core.singleton import StatelessSingleton
from fastapi import FastAPI

app = FastAPI()
optimizer = ColdStartOptimizer()
monitor = ResourceMonitor()

@StatelessSingleton
class {use_case.title().replace(' ', '')}Service:
    def __init__(self):
        # 비용이 큰 초기화 작업
        self.initialized = True
    
    async def process(self, data):
        \"""{use_case} 처리\"""
        # 실제 비즈니스 로직
        return {{"processed": data, "service": "{use_case}"}}

@app.on_event("startup")
async def startup():
    await optimizer.warm_up()

@app.post("/{use_case.lower().replace(' ', '-')}")
@monitor.track_resources
async def handle_request(data: dict):
    service = {use_case.title().replace(' ', '')}Service()
    
    # 리소스 모니터링
    if monitor.memory_usage > 0.8:
        import gc
        gc.collect()
    
    result = await service.process(data)
    return result

# Cloud Run에 최적화된 설정
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""
    
    elif pattern == "state_machine":
        return f"""# State Machine 코드: {use_case}

from rfs.state_machine import StateMachine, State, Transition, Guard, Action
from enum import Enum

class {use_case.title().replace(' ', '')}States(Enum):
    INITIAL = "initial"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class {use_case.title().replace(' ', '')}Events(Enum):
    START = "start"
    PROCESS = "process"
    COMPLETE = "complete"
    FAIL = "fail"
    RESET = "reset"

# 가드 조건
class ValidDataGuard(Guard):
    def evaluate(self, context: dict) -> bool:
        return context.get("data") is not None

# 액션
class ProcessDataAction(Action):
    async def execute(self, context: dict):
        print(f"{use_case}: 데이터 처리 중...")
        context["processed_at"] = "2024-01-01"

# 상태 머신 구성
def create_{use_case.lower().replace(' ', '_')}_machine():
    machine = StateMachine("{use_case}")
    
    # 상태 정의
    initial = State({use_case.title().replace(' ', '')}States.INITIAL)
    processing = State({use_case.title().replace(' ', '')}States.PROCESSING) 
    completed = State({use_case.title().replace(' ', '')}States.COMPLETED)
    failed = State({use_case.title().replace(' ', '')}States.FAILED)
    
    # 전이 정의
    machine.add_transition(Transition(
        from_state=initial,
        to_state=processing,
        event={use_case.title().replace(' ', '')}Events.START,
        guard=ValidDataGuard(),
        action=ProcessDataAction()
    ))
    
    machine.add_transition(Transition(
        from_state=processing,
        to_state=completed,
        event={use_case.title().replace(' ', '')}Events.COMPLETE
    ))
    
    machine.add_transition(Transition(
        from_state=processing,
        to_state=failed,
        event={use_case.title().replace(' ', '')}Events.FAIL
    ))
    
    return machine

# 사용 예제
if __name__ == "__main__":
    import asyncio
    
    async def main():
        machine = create_{use_case.lower().replace(' ', '_')}_machine()
        
        # 초기 컨텍스트
        machine.context = {{"data": "sample_data"}}
        
        # 상태 전이 실행
        await machine.send_event({use_case.title().replace(' ', '')}Events.START)
        print(f"현재 상태: {{machine.current_state.name}}")
        
        await machine.send_event({use_case.title().replace(' ', '')}Events.COMPLETE)
        print(f"최종 상태: {{machine.current_state.name}}")
    
    asyncio.run(main())
"""
    
    else:
        return f"""# {pattern.title()} 패턴 코드: {use_case}

# 요청하신 '{pattern}' 패턴에 대한 기본 템플릿입니다.
# {use_case}에 맞게 수정하여 사용하세요.

from rfs.core import Result, success, failure

def process_{use_case.lower().replace(' ', '_')}(data):
    \"""{use_case} 처리 함수\"""
    try:
        # 여기에 실제 로직을 구현하세요
        result = f"{use_case} 처리 완료: {{data}}"
        return success(result)
    except Exception as e:
        return failure(f"처리 실패: {{e}}")

# 사용 예제
if __name__ == "__main__":
    result = process_{use_case.lower().replace(' ', '_')}("테스트 데이터")
    
    if result.is_success():
        print(result.unwrap())
    else:
        print(f"오류: {{result.unwrap_error()}}")
"""


def explain_pattern(pattern: str, detail_level: str) -> str:
    """패턴 설명"""
    
    explanations = {
        "reactive": {
            "basic": """# Reactive Patterns 기본 설명

Reactive Patterns는 Spring Reactor에서 영감을 받은 비동기 스트림 처리 패턴입니다.

## 핵심 개념
- **Flux**: 0-N개의 비동기 데이터 스트림
- **Mono**: 0-1개의 비동기 값
- **Operators**: map, filter, flatMap 등의 함수형 연산자

## 기본 사용법
```python
from rfs.reactive import Flux

numbers = Flux.from_iterable([1, 2, 3, 4, 5])
result = await numbers.map(lambda x: x * 2).collect_list()
```

## 언제 사용하나요?
- 대용량 데이터 스트림 처리
- 비동기 파이프라인 구성
- 백프레셔가 필요한 상황
""",
            "intermediate": """# Reactive Patterns 중급 설명

## 고급 연산자들

### flatMap - 중첩 스트림 평면화
```python
async def expand_item(item):
    return Flux.from_iterable([item, item * 2, item * 3])

result = await flux.flat_map(expand_item).collect_list()
```

### 병렬 처리
```python
result = await flux.parallel(4).map(heavy_computation).collect_list()
```

### 에러 처리
```python
result = await flux.on_error_resume(lambda e: Flux.just("default")).collect_list()
```

## 백프레셔 관리
- buffer(): 버퍼링으로 압력 조절
- sample(): 샘플링으로 데이터 양 조절
- throttle(): 속도 제한

## 실전 활용
- 실시간 데이터 처리
- 이벤트 스트림 처리
- API 호출 체인
""",
            "advanced": """# Reactive Patterns 고급 설명

## 커스텀 연산자 생성
```python
def custom_operator(upstream):
    def operator(sink):
        async def on_next(item):
            # 커스텀 로직
            transformed = await custom_transform(item)
            await sink.next(transformed)
        
        async def on_error(error):
            await sink.error(error)
        
        async def on_complete():
            await sink.complete()
        
        return upstream.subscribe(on_next, on_error, on_complete)
    return operator
```

## Hot vs Cold Streams
- **Cold**: 구독시마다 새로운 데이터
- **Hot**: 모든 구독자가 같은 데이터 공유

## 스케줄러 활용
```python
flux = (Flux.from_iterable(data)
        .subscribe_on(io_scheduler)  # I/O 작업용 스케줄러
        .observe_on(computation_scheduler))  # CPU 작업용 스케줄러
```

## 성능 최적화
- 올바른 버퍼 크기 설정
- 메모리 누수 방지
- 리소스 정리
"""
        },
        "functional": {
            "basic": """# Functional Patterns 기본 설명

Railway Oriented Programming은 명시적 에러 처리를 위한 함수형 패턴입니다.

## 핵심 개념
- **Result[T, E]**: 성공(Success) 또는 실패(Failure)를 명시적으로 표현
- **함수 체이닝**: 안전한 연산 체인 구성
- **에러 전파**: 에러가 자동으로 전파됨

## 기본 사용법
```python
from rfs.core import Result, success, failure

def safe_divide(a, b) -> Result[float, str]:
    if b == 0:
        return failure("Division by zero")
    return success(a / b)
```

## 언제 사용하나요?
- 에러가 예상되는 연산
- 안전한 데이터 파이프라인
- 명시적 에러 처리가 필요한 상황
""",
            "intermediate": """# Functional Patterns 중급 설명

## bind (flatMap) 패턴
```python
result = (divide(a, b)
         .bind(lambda x: sqrt(x))  # 연쇄 연산
         .map(lambda x: x * 100))  # 변환
```

## traverse 패턴
```python
# 리스트의 모든 요소를 안전하게 처리
results = traverse(items, safe_process)
```

## combine_results 패턴
```python
# 여러 Result를 하나로 결합
combined = combine_results(result1, result2, result3)
```

## 고차 함수 활용
```python
# 함수를 Result 컨텍스트로 리프트
lifted_func = lift(normal_function)
result = lifted_func(result_value)
```

## 실전 패턴
- API 호출 체인
- 설정 파일 처리
- 데이터 변환 파이프라인
""",
            "advanced": """# Functional Patterns 고급 설명

## 커스텀 Result 타입
```python
class ValidationResult(Result[T, List[str]]):
    def add_error(self, error: str):
        if self.is_failure():
            self.error.append(error)
        else:
            self.error = [error]
```

## 모나드 법칙 준수
1. **Left Identity**: `return a >>= f ≡ f a`
2. **Right Identity**: `m >>= return ≡ m`  
3. **Associativity**: `(m >>= f) >>= g ≡ m >>= (\\x -> f x >>= g)`

## 성능 최적화
```python
# 지연 평가로 불필요한 연산 방지
def lazy_computation():
    return expensive_operation()

result = success(42).map(lazy_computation)  # 지연 실행
```

## 타입 안전성
- 제네릭 타입으로 컴파일 타임 검증
- MyPy 활용한 정적 타입 검사
- 런타임 타입 검증
"""
        }
    }
    
    return explanations.get(pattern, {}).get(detail_level, f"{pattern} 패턴에 대한 {detail_level} 수준의 설명을 준비 중입니다.")


async def main():
    """메인 함수"""
    async with stdio_server() as streams:
        await server.run(
            streams[0], 
            streams[1], 
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())