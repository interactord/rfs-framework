#!/usr/bin/env python3
"""
RFS Framework MCP Server

RFS (Reactive Functional Serverless) Framework의 문서, 예제, 패턴을 제공하는 MCP 서버
"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence
from pathlib import Path
import asyncio

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
    print("MCP not available. Install with: pip install mcp")

logger = logging.getLogger("rfs-mcp-server")

class RFSMCPServer:
    """RFS Framework MCP 서버"""
    
    def __init__(self):
        self.server = Server("rfs-framework-server")
        self.rfs_root = Path(__file__).parent
        
        # RFS Framework 구조 정보
        self.rfs_modules = {
            "reactive": {
                "flux": "0-N 비동기 스트림 처리 (Spring Reactor 패턴)",
                "mono": "0-1 비동기 값 처리 (Spring Reactor 패턴)",
            },
            "core": {
                "result": "Railway Oriented Programming - Success/Failure 패턴",
                "singleton": "Stateless Singleton - Spring Bean 스타일 DI",
            },
            "state_machine": {
                "machine": "클래스 기반 상태 머신 (Spring StateMachine 패턴)",
                "functional": "함수형 상태 머신 API",
            },
            "serverless": {
                "cloud_run": "Google Cloud Run 최적화",
                "cloud_tasks": "Google Cloud Tasks 통합",
            },
            "events": {
                "event_bus": "이벤트 버스 - Pub/Sub 패턴",
                "saga": "Saga 패턴 - 분산 트랜잭션",
                "cqrs": "CQRS 패턴 - Command/Query 분리",
            }
        }
        
        # 설정
        self.setup_resources()
        self.setup_tools()
        
    def setup_resources(self):
        """리소스 설정"""
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """RFS Framework 리소스 목록"""
            resources = []
            
            # 메인 문서들
            resources.extend([
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
                    uri="rfs://examples/complete",
                    name="Complete Examples",
                    description="전체 기능을 사용한 예제들",
                    mimeType="text/markdown"
                )
            ])
            
            # 모듈별 리소스
            for module_name, module_info in self.rfs_modules.items():
                for submodule, description in module_info.items():
                    resources.append(Resource(
                        uri=f"rfs://modules/{module_name}/{submodule}",
                        name=f"{module_name}.{submodule}",
                        description=description,
                        mimeType="text/markdown"
                    ))
            
            return resources

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """리소스 내용 반환"""
            
            if uri == "rfs://framework/overview":
                return self._get_framework_overview()
            elif uri == "rfs://patterns/reactive":
                return self._get_reactive_patterns()
            elif uri == "rfs://patterns/functional":
                return self._get_functional_patterns()
            elif uri == "rfs://patterns/serverless":
                return self._get_serverless_patterns()
            elif uri == "rfs://examples/complete":
                return self._get_complete_examples()
            elif uri.startswith("rfs://modules/"):
                parts = uri.split("/")
                module_name, submodule = parts[3], parts[4]
                return self._get_module_details(module_name, submodule)
            else:
                raise ValueError(f"Unknown resource: {uri}")

    def setup_tools(self):
        """도구 설정"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """사용 가능한 도구 목록"""
            return [
                Tool(
                    name="generate_rfs_code",
                    description="RFS Framework 패턴을 사용한 코드 생성",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "enum": ["reactive", "functional", "serverless", "state_machine", "events"],
                                "description": "사용할 RFS 패턴"
                            },
                            "use_case": {
                                "type": "string",
                                "description": "구현하려는 사용 사례"
                            },
                            "framework": {
                                "type": "string",
                                "enum": ["fastapi", "flask", "cloud_function", "standalone"],
                                "default": "standalone",
                                "description": "대상 프레임워크"
                            }
                        },
                        "required": ["pattern", "use_case"]
                    }
                ),
                Tool(
                    name="explain_rfs_pattern",
                    description="RFS Framework 패턴 설명",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "설명할 패턴 이름"
                            },
                            "detail_level": {
                                "type": "string",
                                "enum": ["basic", "detailed", "advanced"],
                                "default": "detailed",
                                "description": "설명 상세도"
                            }
                        },
                        "required": ["pattern"]
                    }
                ),
                Tool(
                    name="rfs_best_practices",
                    description="RFS Framework 모범 사례 조회",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "모범 사례를 원하는 주제"
                            },
                            "context": {
                                "type": "string",
                                "enum": ["development", "testing", "production", "migration"],
                                "default": "development",
                                "description": "적용 컨텍스트"
                            }
                        },
                        "required": ["topic"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """도구 실행"""
            
            if name == "generate_rfs_code":
                return [TextContent(
                    type="text",
                    text=self._generate_rfs_code(
                        arguments["pattern"],
                        arguments["use_case"],
                        arguments.get("framework", "standalone")
                    )
                )]
            elif name == "explain_rfs_pattern":
                return [TextContent(
                    type="text",
                    text=self._explain_rfs_pattern(
                        arguments["pattern"],
                        arguments.get("detail_level", "detailed")
                    )
                )]
            elif name == "rfs_best_practices":
                return [TextContent(
                    type="text",
                    text=self._get_best_practices(
                        arguments["topic"],
                        arguments.get("context", "development")
                    )
                )]
            else:
                raise ValueError(f"Unknown tool: {name}")

    def _get_framework_overview(self) -> str:
        """프레임워크 개요"""
        return """# RFS Framework 개요

## Reactive Functional Serverless Framework

RFS Framework는 Python에서 Spring Reactor의 반응형 패턴과 함수형 프로그래밍을 결합한 서버리스 최적화 프레임워크입니다.

### 🌟 핵심 특징

1. **Spring Reactor 패턴**
   - Flux (0-N 비동기 스트림)
   - Mono (0-1 비동기 값)
   - 백프레셔 지원

2. **Railway Oriented Programming**
   - Success/Failure 명시적 에러 처리
   - 함수 합성 및 파이프라인

3. **Stateless Singleton**
   - Spring Bean 스타일 의존성 주입
   - 자동 인스턴스 관리

4. **서버리스 최적화**
   - Google Cloud Run 최적화
   - Cold Start 감지 및 최적화
   - Cloud Tasks 통합

5. **Event-Driven Architecture**
   - Event Bus, Saga, CQRS 패턴
   - 분산 트랜잭션 지원

### 📦 설치

```bash
pip install rfs-framework

# 선택적 기능
pip install rfs-framework[cloud]      # Google Cloud
pip install rfs-framework[eventstore] # Event Sourcing
pip install rfs-framework[all]        # 모든 기능
```

### 🚀 기본 사용법

```python
from rfs import Flux, Mono, success, failure, StatelessRegistry
import asyncio

async def example():
    # Reactive Streams
    result = await Flux.from_iterable([1, 2, 3]).map(lambda x: x * 2).collect_list()
    print(result)  # [2, 4, 6]
    
    # Railway Oriented Programming
    safe_result = success("완료!").map(lambda s: s.upper())
    print(safe_result.unwrap())  # "완료!"
    
    # Dependency Injection
    registry = StatelessRegistry()
    
    @registry.register('service')
    class MyService:
        def process(self, data):
            return f"Processed: {data}"
    
    service = registry.get('service')
    print(service.process("test"))

asyncio.run(example())
```

### 🔗 링크
- PyPI: https://pypi.org/project/rfs-framework/
- 문서: 이 MCP 서버를 통해 접근 가능
"""

    def _get_reactive_patterns(self) -> str:
        """Reactive 패턴 설명"""
        return """# Reactive Patterns (Spring Reactor)

RFS Framework의 Reactive Streams는 Spring Reactor에서 영감을 받았습니다.

## Flux (0-N 스트림)

```python
from rfs import Flux
import asyncio

async def flux_examples():
    # 기본 생성
    flux = Flux.from_iterable([1, 2, 3, 4, 5])
    
    # 변환 및 필터링
    result = await (flux
                   .map(lambda x: x * 2)
                   .filter(lambda x: x > 5)
                   .collect_list())
    print(result)  # [6, 8, 10]
    
    # 병렬 처리
    parallel_result = await (Flux.from_iterable(range(100))
                           .map(lambda x: x ** 2)
                           .parallel(max_concurrency=10)
                           .sequential()
                           .collect_list())
    
    # 에러 처리
    safe_flux = (Flux.from_iterable([1, 2, 0, 3])
                .map(lambda x: 10 / x)
                .on_error_continue(lambda err: print(f"Error: {err}"))
                .collect_list())

asyncio.run(flux_examples())
```

## Mono (0-1 값)

```python
from rfs import Mono
import asyncio

async def mono_examples():
    # 기본 생성
    mono = Mono.just("Hello")
    
    # 체이닝
    result = await (mono
                   .map(lambda s: s.upper())
                   .map(lambda s: f"{s}, World!")
                   .block())
    print(result)  # "HELLO, World!"
    
    # 조건부 처리
    conditional = await (Mono.just(5)
                        .filter(lambda x: x > 3)
                        .default_if_empty(0)
                        .block())
    print(conditional)  # 5
    
    # 에러 처리
    safe_mono = (Mono.from_callable(lambda: 10 / 0)
                .on_error_return("Error occurred")
                .block())

asyncio.run(mono_examples())
```

## 고급 패턴

### 백프레셔 (Backpressure)

```python
# 버퍼링을 통한 백프레셔 제어
buffered = await (Flux.from_iterable(range(1000))
                 .buffer(50)  # 50개씩 배치 처리
                 .map(lambda batch: len(batch))
                 .collect_list())
```

### 조합 연산

```python
# zip_with를 통한 결합
flux1 = Flux.from_iterable([1, 2, 3])
flux2 = Flux.from_iterable(['a', 'b', 'c'])

combined = await flux1.zip_with(flux2).collect_list()
print(combined)  # [(1, 'a'), (2, 'b'), (3, 'c')]
```
"""

    def _get_functional_patterns(self) -> str:
        """함수형 패턴 설명"""
        return """# Functional Patterns (Railway Oriented Programming)

RFS Framework는 Railway Oriented Programming을 통해 안전한 에러 처리를 제공합니다.

## Result 타입

```python
from rfs import success, failure, Result
import asyncio

def divide(a, b):
    if b == 0:
        return failure("Division by zero")
    return success(a / b)

def sqrt(x):
    if x < 0:
        return failure("Negative number")
    return success(x ** 0.5)

# 체이닝
result = (divide(10, 2)
         .bind(sqrt)  # Success인 경우만 실행
         .map(lambda x: round(x, 2)))

if result.is_success():
    print(f"Result: {result.unwrap()}")  # Result: 2.24
else:
    print(f"Error: {result.unwrap_error()}")
```

## 함수 합성

```python
from rfs import lift

# 일반 함수를 Result 컨텍스트로 리프트
safe_multiply = lift(lambda x: x * 2)
safe_add = lift(lambda x: x + 1)

# 파이프라인 구성
pipeline = (success(5)
           .bind(safe_multiply)
           .bind(safe_add))

print(pipeline.unwrap())  # 11
```

## 비동기 Result

```python
import asyncio
from rfs import Result

async def async_divide(a, b):
    await asyncio.sleep(0.1)  # 비동기 작업 시뮬레이션
    if b == 0:
        return failure("Division by zero")
    return success(a / b)

async def process_numbers():
    result = await async_divide(10, 2)
    return result.map(lambda x: x * 2)

# 사용
async def main():
    result = await process_numbers()
    print(result.unwrap())  # 10.0

asyncio.run(main())
```

## 복합 연산

```python
# 여러 Result를 결합
def combine_results(r1, r2, r3):
    if r1.is_failure():
        return r1
    if r2.is_failure():
        return r2  
    if r3.is_failure():
        return r3
    
    return success((r1.unwrap(), r2.unwrap(), r3.unwrap()))

# 사용 예제
results = combine_results(
    divide(10, 2),
    divide(8, 4), 
    divide(6, 3)
)
print(results.unwrap())  # (5.0, 2.0, 2.0)
```

## Reactive + Functional 결합

```python
from rfs import Flux, success, failure

async def safe_processing():
    # Flux와 Result 결합
    results = await (Flux.from_iterable([1, 2, 0, 4, 5])
                    .map(lambda x: divide(10, x))  # Result 반환
                    .filter(lambda r: r.is_success())  # 성공만 필터
                    .map(lambda r: r.unwrap())  # 값 추출
                    .collect_list())
    
    return results

asyncio.run(safe_processing())
```
"""

    def _get_serverless_patterns(self) -> str:
        """서버리스 패턴 설명"""
        return """# Serverless Patterns

RFS Framework는 Google Cloud Run과 Cloud Tasks에 최적화되어 있습니다.

## Cloud Run 최적화

```python
from rfs.serverless import CloudRunOptimizer
from rfs import Flux, StatelessRegistry
import asyncio

# Cloud Run 최적화 적용
optimizer = CloudRunOptimizer()

@optimizer.cold_start_detector
async def optimized_handler(request):
    \"\"\"Cold Start 감지 및 최적화\"\"\"
    
    # 캐싱된 처리
    @optimizer.cached_response(ttl=300)  # 5분 캐시
    async def expensive_operation(data):
        return await process_heavy_data(data)
    
    result = await expensive_operation(request.data)
    return {"result": result}

# 리소스 모니터링
@optimizer.resource_monitor
async def monitored_function():
    \"\"\"리소스 사용량 모니터링\"\"\"
    memory_usage = optimizer.get_memory_usage()
    cpu_usage = optimizer.get_cpu_usage()
    
    if memory_usage > 0.8:  # 80% 이상
        await optimizer.trigger_garbage_collection()
    
    return {"memory": memory_usage, "cpu": cpu_usage}
```

## Cloud Tasks 통합

```python
from rfs.serverless import CloudTasksClient
from rfs import success, failure
import asyncio

async def task_examples():
    client = CloudTasksClient(
        project_id="my-project",
        location="asia-northeast3",
        queue_name="my-queue"
    )
    
    # 단일 작업 추가
    task_result = await client.enqueue_task({
        "url": "/api/process",
        "payload": {"data": "important_data"},
        "delay_seconds": 60  # 1분 후 실행
    })
    
    if task_result.is_success():
        print(f"Task enqueued: {task_result.unwrap()}")
    
    # 배치 작업
    tasks = [
        {"url": "/api/process", "payload": {"id": i}}
        for i in range(100)
    ]
    
    batch_result = await client.enqueue_batch(tasks)
    successful_tasks = [r.unwrap() for r in batch_result if r.is_success()]
    
    print(f"Enqueued {len(successful_tasks)} tasks")

asyncio.run(task_examples())
```

## 서버리스 함수 패턴

```python
from rfs import Flux, StatelessRegistry
from rfs.serverless import serverless_function

# 의존성 주입 설정
registry = StatelessRegistry()

@registry.register("data_processor")
class DataProcessor:
    async def process_batch(self, items):
        return await Flux.from_iterable(items).map(self.process_item).collect_list()
    
    def process_item(self, item):
        return {"processed": item, "timestamp": "2024-01-01"}

@serverless_function
async def cloud_function(request):
    \"\"\"Cloud Function 핸들러\"\"\"
    
    processor = registry.get("data_processor")
    
    # 요청 데이터 처리
    items = request.get("items", [])
    
    # 병렬 처리
    results = await processor.process_batch(items)
    
    return {
        "success": True,
        "processed_count": len(results),
        "results": results
    }
```

## 성능 최적화 패턴

```python
from rfs import Flux, Mono
from rfs.serverless import performance_optimized

@performance_optimized(
    max_memory_mb=512,
    timeout_seconds=300
)
async def optimized_pipeline(data):
    \"\"\"성능 최적화된 처리 파이프라인\"\"\"
    
    # 메모리 효율적인 스트림 처리
    return await (Flux.from_iterable(data)
                 .buffer(100)  # 100개씩 배치
                 .map(lambda batch: process_batch_efficiently(batch))
                 .reduce(lambda acc, batch: acc + batch, []))

def process_batch_efficiently(batch):
    \"\"\"배치 단위로 효율적 처리\"\"\"
    return [item * 2 for item in batch]
```

## 모니터링 및 관찰성

```python
from rfs.serverless import CloudRunOptimizer

optimizer = CloudRunOptimizer()

# 메트릭 수집
@optimizer.metrics_collector
async def monitored_endpoint(request):
    \"\"\"메트릭이 자동 수집되는 엔드포인트\"\"\"
    
    # 처리 시간, 메모리 사용량, 응답 크기 등 자동 수집
    result = await process_request(request)
    
    return result

# 헬스 체크
@optimizer.health_check
async def health_check():
    \"\"\"서비스 상태 확인\"\"\"
    return {
        "status": "healthy",
        "memory_usage": optimizer.get_memory_usage(),
        "uptime": optimizer.get_uptime()
    }
```
"""

    def _get_complete_examples(self) -> str:
        """완전한 예제들"""
        return """# Complete Examples

RFS Framework의 모든 기능을 활용한 실전 예제들입니다.

## E-commerce Order Processing

```python
from rfs import Flux, Mono, success, failure, StatelessRegistry
from rfs.events import EventBus, Saga
from rfs.serverless import CloudRunOptimizer
import asyncio

# 의존성 주입 설정
registry = StatelessRegistry()

@registry.register("inventory_service")
class InventoryService:
    def __init__(self):
        self.stock = {"item1": 10, "item2": 5}
    
    async def reserve(self, item_id, quantity):
        if self.stock.get(item_id, 0) >= quantity:
            self.stock[item_id] -= quantity
            return success(f"Reserved {quantity} of {item_id}")
        return failure(f"Insufficient stock for {item_id}")
    
    async def release(self, item_id, quantity):
        self.stock[item_id] += quantity
        return success(f"Released {quantity} of {item_id}")

@registry.register("payment_service") 
class PaymentService:
    async def charge(self, amount, card_token):
        # 실제로는 외부 결제 API 호출
        await asyncio.sleep(0.1)
        if card_token == "invalid":
            return failure("Invalid card token")
        return success(f"Charged ${amount}")
    
    async def refund(self, transaction_id):
        return success(f"Refunded transaction {transaction_id}")

# Saga 패턴으로 분산 트랜잭션 처리
class OrderSaga(Saga):
    def __init__(self):
        super().__init__("order_processing")
        
        self.step("validate_order", self.validate_order)
        self.step("reserve_inventory", 
                 self.reserve_inventory, 
                 self.release_inventory)  # 보상 액션
        self.step("process_payment",
                 self.process_payment,
                 self.refund_payment)     # 보상 액션
        self.step("confirm_order", self.confirm_order)
    
    async def validate_order(self, context):
        order = context.get("order")
        if not order or not order.get("items"):
            return failure("Invalid order")
        return success(context)
    
    async def reserve_inventory(self, context):
        inventory_service = registry.get("inventory_service")
        order = context["order"]
        
        # 모든 아이템 예약
        reservations = []
        for item in order["items"]:
            result = await inventory_service.reserve(
                item["id"], item["quantity"]
            )
            if result.is_failure():
                # 이전 예약들 롤백
                for prev_item in reservations:
                    await inventory_service.release(
                        prev_item["id"], prev_item["quantity"]
                    )
                return result
            reservations.append(item)
        
        context["reservations"] = reservations
        return success(context)
    
    async def release_inventory(self, context):
        \"\"\"보상 액션: 재고 해제\"\"\"
        inventory_service = registry.get("inventory_service")
        reservations = context.get("reservations", [])
        
        for item in reservations:
            await inventory_service.release(item["id"], item["quantity"])
        
        return success(context)
    
    async def process_payment(self, context):
        payment_service = registry.get("payment_service")
        order = context["order"]
        
        result = await payment_service.charge(
            order["total"], order["card_token"]
        )
        
        if result.is_success():
            context["transaction_id"] = "txn_123"
        
        return result.map(lambda _: context)
    
    async def refund_payment(self, context):
        \"\"\"보상 액션: 결제 환불\"\"\"
        payment_service = registry.get("payment_service")
        transaction_id = context.get("transaction_id")
        
        if transaction_id:
            await payment_service.refund(transaction_id)
        
        return success(context)
    
    async def confirm_order(self, context):
        order_id = context["order"]["id"]
        print(f"Order {order_id} confirmed successfully!")
        return success(context)

# Cloud Run 최적화된 주문 처리 API
optimizer = CloudRunOptimizer()

@optimizer.cold_start_detector
async def process_orders(orders_batch):
    \"\"\"주문 배치 처리\"\"\"
    
    saga = OrderSaga()
    
    # 병렬로 여러 주문 처리
    results = await Flux.from_iterable(orders_batch).map(
        lambda order: saga.execute({"order": order})
    ).collect_list()
    
    successful_orders = [r.unwrap() for r in results if r.is_success()]
    failed_orders = [r.unwrap_error() for r in results if r.is_failure()]
    
    return {
        "successful": len(successful_orders),
        "failed": len(failed_orders),
        "details": {
            "successful_orders": successful_orders,
            "failed_orders": failed_orders
        }
    }

# 사용 예제
async def main():
    # 테스트 주문들
    test_orders = [
        {
            "id": "order_1",
            "items": [{"id": "item1", "quantity": 2}],
            "total": 100.0,
            "card_token": "valid_token"
        },
        {
            "id": "order_2", 
            "items": [{"id": "item2", "quantity": 1}],
            "total": 50.0,
            "card_token": "invalid"  # 실패하는 주문
        }
    ]
    
    result = await process_orders(test_orders)
    print(f"Processing result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 실시간 데이터 파이프라인

```python
from rfs import Flux, Mono, StatelessRegistry
from rfs.events import EventBus, Event
import asyncio
import json

# 이벤트 기반 실시간 파이프라인
registry = StatelessRegistry()
event_bus = EventBus()

@registry.register("data_transformer")
class DataTransformer:
    async def transform(self, raw_data):
        \"\"\"데이터 변환\"\"\"
        return {
            "processed_at": "2024-01-01T00:00:00Z",
            "value": raw_data["value"] * 2,
            "source": raw_data.get("source", "unknown")
        }

@registry.register("data_validator")
class DataValidator:
    def validate(self, data):
        \"\"\"데이터 검증\"\"\"
        if data.get("value", 0) < 0:
            return failure("Negative value not allowed")
        if not data.get("source"):
            return failure("Source is required")
        return success(data)

# 이벤트 핸들러들
@event_bus.subscribe("data_received")
async def handle_data_received(event: Event):
    \"\"\"데이터 수신 이벤트 처리\"\"\"
    transformer = registry.get("data_transformer")
    validator = registry.get("data_validator")
    
    # 데이터 변환 및 검증 파이프라인
    result = await (Mono.just(event.data)
                   .flat_map(lambda data: Mono.just(transformer.transform(data)))
                   .map(validator.validate)
                   .block())
    
    if result.is_success():
        # 처리 완료 이벤트 발행
        await event_bus.publish(Event(
            "data_processed",
            result.unwrap(),
            {"original_event_id": event.id}
        ))
    else:
        # 에러 이벤트 발행
        await event_bus.publish(Event(
            "data_error",
            {"error": result.unwrap_error(), "data": event.data}
        ))

@event_bus.subscribe("data_processed")
async def handle_data_processed(event: Event):
    print(f"Data processed successfully: {event.data}")

@event_bus.subscribe("data_error")
async def handle_data_error(event: Event):
    print(f"Data processing failed: {event.data}")

# 실시간 스트림 처리
async def stream_processor():
    \"\"\"실시간 스트림 처리\"\"\"
    
    # 시뮬레이션된 데이터 스트림
    data_stream = [
        {"value": 10, "source": "sensor1"},
        {"value": -5, "source": "sensor2"},  # 실패할 데이터
        {"value": 20, "source": "sensor3"},
        {"value": 15},  # source 없음 - 실패
    ]
    
    # 스트림을 이벤트로 변환하여 발행
    await Flux.from_iterable(data_stream).map(
        lambda data: Event("data_received", data)
    ).subscribe(
        lambda event: event_bus.publish(event)
    )
    
    # 이벤트 처리 대기
    await asyncio.sleep(1)

# 실행
async def main():
    await stream_processor()
    
    # 이벤트 버스 통계
    stats = event_bus.get_statistics()
    print(f"Event bus stats: {stats}")

if __name__ == "__main__":
    asyncio.run(main())
```

이 예제들은 RFS Framework의 모든 핵심 기능을 실전에서 활용하는 방법을 보여줍니다:
- Reactive Streams (Flux/Mono)
- Railway Oriented Programming (Result)
- Dependency Injection (StatelessRegistry)
- Event-Driven Architecture (EventBus, Saga)
- Serverless Optimization (CloudRunOptimizer)
"""

    def _get_module_details(self, module_name: str, submodule: str) -> str:
        """모듈별 상세 정보"""
        return f"""# {module_name}.{submodule}

{self.rfs_modules.get(module_name, {}).get(submodule, "모듈 정보를 찾을 수 없습니다.")}

## 사용법

```python
from rfs.{module_name} import {submodule}

# 기본 사용 예제
# TODO: 각 모듈별 구체적인 예제 구현
```

자세한 사용법은 `generate_rfs_code` 도구를 사용하여 코드를 생성해보세요.
"""

    def _generate_rfs_code(self, pattern: str, use_case: str, framework: str) -> str:
        """RFS 코드 생성"""
        templates = {
            "reactive": f"""# Reactive Pattern: {use_case}

from rfs import Flux, Mono
import asyncio

async def {use_case.lower().replace(' ', '_')}():
    # Flux 예제 (0-N 스트림)
    flux_result = await (Flux.from_iterable([1, 2, 3, 4, 5])
                        .map(lambda x: x * 2)
                        .filter(lambda x: x > 5)
                        .collect_list())
    
    # Mono 예제 (0-1 값)
    mono_result = await (Mono.just("data")
                        .map(lambda s: s.upper())
                        .block())
    
    return {{"flux": flux_result, "mono": mono_result}}

# 실행
if __name__ == "__main__":
    result = asyncio.run({use_case.lower().replace(' ', '_')}())
    print(result)
""",
            "functional": f"""# Functional Pattern: {use_case}

from rfs import success, failure, Result
import asyncio

def safe_operation(data):
    \"\"\"안전한 연산\"\"\"
    try:
        # {use_case} 구현
        result = data * 2  # 실제 비즈니스 로직
        return success(result)
    except Exception as e:
        return failure(str(e))

def process_pipeline(data):
    \"\"\"처리 파이프라인\"\"\"
    return (safe_operation(data)
           .bind(lambda x: safe_operation(x))  # 체이닝
           .map(lambda x: x + 1))

# 사용
result = process_pipeline(5)
if result.is_success():
    print(f"Result: {{result.unwrap()}}")
else:
    print(f"Error: {{result.unwrap_error()}}")
""",
            "serverless": f"""# Serverless Pattern: {use_case}

from rfs.serverless import CloudRunOptimizer
from rfs import Flux, StatelessRegistry
import asyncio

# 최적화 설정
optimizer = CloudRunOptimizer()
registry = StatelessRegistry()

@registry.register("{use_case.lower().replace(' ', '_')}_service")
class {use_case.replace(' ', '')}Service:
    async def process(self, data):
        \"\"\"비즈니스 로직 처리\"\"\"
        return await Flux.from_iterable(data).map(self.transform_item).collect_list()
    
    def transform_item(self, item):
        return {{"processed": item, "timestamp": "2024-01-01"}}

@optimizer.cold_start_detector
async def {framework}_handler(request):
    \"\"\"{"FastAPI" if framework == "fastapi" else framework.title()} 핸들러\"\"\"
    
    service = registry.get("{use_case.lower().replace(' ', '_')}_service")
    
    # 요청 처리
    data = request.get("data", [])
    result = await service.process(data)
    
    return {{"success": True, "result": result}}

# {"FastAPI 라우터" if framework == "fastapi" else "사용 예제"}
{self._get_framework_integration(framework)}
""",
        }
        
        return templates.get(pattern, f"# {pattern.title()} Pattern\n\n구현 예정: {use_case}")

    def _get_framework_integration(self, framework: str) -> str:
        """프레임워크별 통합 코드"""
        if framework == "fastapi":
            return """
# FastAPI 통합
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/process")
async def process_endpoint(request: dict):
    result = await fastapi_handler(request)
    return JSONResponse(result)
"""
        elif framework == "flask":
            return """
# Flask 통합
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/process', methods=['POST'])
async def process_endpoint():
    data = request.get_json()
    result = await flask_handler(data)
    return jsonify(result)
"""
        elif framework == "cloud_function":
            return """
# Google Cloud Function
def cloud_function(request):
    import asyncio
    
    data = request.get_json()
    result = asyncio.run(cloud_function_handler(data))
    return result
"""
        else:
            return """
# 단독 실행
if __name__ == "__main__":
    import asyncio
    
    test_data = {"data": [1, 2, 3, 4, 5]}
    result = asyncio.run(standalone_handler(test_data))
    print(result)
"""

    def _explain_rfs_pattern(self, pattern: str, detail_level: str) -> str:
        """패턴 설명"""
        explanations = {
            "flux": {
                "basic": "Flux는 0-N개의 비동기 아이템을 처리하는 스트림입니다.",
                "detailed": """Flux는 Spring Reactor의 핵심 타입으로, 0개에서 N개의 아이템을 비동기적으로 처리합니다.

주요 특징:
- 백프레셔 지원
- 지연 평가 (Lazy evaluation)
- 함수형 변환 연산자 (map, filter, flatMap 등)
- 에러 처리 및 복구
- 병렬 처리 지원

기본 사용법:
```python
flux = Flux.from_iterable([1, 2, 3])
result = await flux.map(lambda x: x * 2).collect_list()
```""",
                "advanced": """Flux 고급 사용법과 내부 구조...
[상세한 구현 설명, 성능 최적화, 메모리 관리 등]"""
            }
        }
        
        return explanations.get(pattern, {}).get(detail_level, f"{pattern} 패턴에 대한 설명이 준비되지 않았습니다.")

    def _get_best_practices(self, topic: str, context: str) -> str:
        """모범 사례"""
        practices = {
            "error_handling": {
                "development": """RFS Framework 에러 처리 모범 사례:

1. **Railway Oriented Programming 사용**
   ```python
   from rfs import success, failure
   
   def safe_divide(a, b):
       if b == 0:
           return failure("Division by zero")
       return success(a / b)
   
   # 체이닝으로 안전한 연산
   result = (safe_divide(10, 2)
            .bind(lambda x: safe_divide(x, 2))
            .map(lambda x: round(x, 2)))
   ```

2. **Reactive Streams 에러 처리**
   ```python
   from rfs import Flux
   
   # 에러 발생시 계속 진행
   flux = (Flux.from_iterable([1, 0, 3])
          .map(lambda x: 10 / x)
          .on_error_continue(lambda err: print(f"Error: {err}"))
          .collect_list())
   ```

3. **서버리스에서의 에러 처리**
   ```python
   from rfs.serverless import CloudRunOptimizer
   
   optimizer = CloudRunOptimizer()
   
   @optimizer.error_handler
   async def safe_handler(request):
       try:
           return await process_request(request)
       except Exception as e:
           return {"error": str(e), "success": False}
   ```
""",
                "production": """프로덕션 환경 에러 처리:

1. **구조화된 로깅**
2. **메트릭 수집**
3. **알림 시스템 통합**
4. **자동 복구 메커니즘**
"""
            }
        }
        
        return practices.get(topic, {}).get(context, f"{topic}에 대한 {context} 컨텍스트 모범 사례가 준비되지 않았습니다.")

    async def run(self):
        """MCP 서버 실행"""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP가 설치되지 않았습니다. pip install mcp로 설치하세요.")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="rfs-framework-server",
                    server_version="1.0.2",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities={}
                    )
                )
            )

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RFS Framework MCP Server")
    parser.add_argument("--debug", action="store_true", help="디버그 모드")
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    server = RFSMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()