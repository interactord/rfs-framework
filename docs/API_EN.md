# RFS Framework API Reference

## Table of Contents
- [Core Module](#core-module)
- [Reactive Module](#reactive-module)
- [State Machine Module](#state-machine-module)
- [Events Module](#events-module)
- [Serverless Module](#serverless-module)
- [Production Module](#production-module)

## Core Module

### Result Pattern

The Result pattern provides Railway Oriented Programming for safe error handling.

```python
from rfs import Result, Success, Failure
```

#### `Result[T, E]`
Generic container for success or failure values.

**Methods:**
- `is_success() -> bool`: Check if result is successful
- `is_failure() -> bool`: Check if result is failure
- `unwrap() -> T`: Get success value (raises if failure)
- `unwrap_err() -> E`: Get error value (raises if success)
- `unwrap_or(default: T) -> T`: Get value or default
- `map(fn: Callable[[T], U]) -> Result[U, E]`: Transform success value
- `bind(fn: Callable[[T], Result[U, E]]) -> Result[U, E]`: Chain operations
- `map_err(fn: Callable[[E], F]) -> Result[T, F]`: Transform error value

**Example:**
```python
def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Failure("Division by zero")
    return Success(a / b)

result = divide(10, 2)
doubled = result.map(lambda x: x * 2)  # Success(10.0)
```

#### `Success[T]`
Represents successful computation result.

```python
success = Success(42)
assert success.is_success == True
assert success.unwrap() == 42
```

#### `Failure[E]`
Represents failed computation with error.

```python
failure = Failure("Error occurred")
assert failure.is_failure == True
assert failure.unwrap_err() == "Error occurred"
```

### Either Pattern

Either type for values that can be Left or Right.

```python
from rfs import Either, Left, Right
```

#### `Either[L, R]`
Container that holds either Left (typically error) or Right (typically success) value.

**Methods:**
- `is_left() -> bool`: Check if Left
- `is_right() -> bool`: Check if Right
- `map_left(fn) -> Either`: Transform Left value
- `map_right(fn) -> Either`: Transform Right value
- `fold(left_fn, right_fn) -> Any`: Pattern match on Either

**Example:**
```python
def validate_age(age: int) -> Either[str, int]:
    if age < 0:
        return Left("Age cannot be negative")
    if age > 150:
        return Left("Age seems unrealistic")
    return Right(age)

result = validate_age(25)
message = result.fold(
    lambda err: f"Error: {err}",
    lambda age: f"Valid age: {age}"
)
```

### Maybe Pattern

Optional value container similar to Option/Optional.

```python
from rfs import Maybe, Just, Nothing
```

#### `Maybe[T]`
Container for optional values.

**Methods:**
- `is_just() -> bool`: Check if has value
- `is_nothing() -> bool`: Check if empty
- `unwrap() -> T`: Get value (raises if Nothing)
- `unwrap_or(default: T) -> T`: Get value or default
- `map(fn: Callable[[T], U]) -> Maybe[U]`: Transform value
- `bind(fn: Callable[[T], Maybe[U]]) -> Maybe[U]`: Chain operations
- `filter(pred: Callable[[T], bool]) -> Maybe[T]`: Filter by predicate

**Example:**
```python
def find_user(id: int) -> Maybe[User]:
    user = database.get(id)
    if user:
        return Just(user)
    return Nothing()

user = find_user(123)
name = user.map(lambda u: u.name).unwrap_or("Unknown")
```

### Configuration Management

Pydantic v2-based configuration system with environment support.

```python
from rfs import RFSConfig, ConfigManager, Environment, get_config
```

#### `RFSConfig`
Main configuration class using Pydantic BaseModel.

**Fields:**
- `environment: Environment`: Current environment (development/staging/production)
- `app_name: str`: Application name
- `debug: bool`: Debug mode flag
- `database: DatabaseConfig`: Database configuration
- `redis: RedisConfig`: Redis configuration
- `cloud_run: CloudRunConfig`: Cloud Run settings

**Example:**
```python
config = get_config()  # Auto-loads from environment
print(f"Environment: {config.environment}")
print(f"Database URL: {config.database.url}")
```

#### `ConfigManager`
Manages configuration loading and validation.

**Methods:**
- `load_config(path: str) -> RFSConfig`: Load from file
- `from_env() -> RFSConfig`: Load from environment variables
- `validate() -> bool`: Validate configuration

### Service Registry

Dependency injection container for stateless services.

```python
from rfs import StatelessRegistry, stateless
```

#### `StatelessRegistry`
Spring Bean-style singleton registry.

**Methods:**
- `register(name: str) -> Callable`: Decorator to register service
- `get(name: str) -> Any`: Get service instance
- `has(name: str) -> bool`: Check if service registered
- `list() -> List[str]`: List all registered services

**Example:**
```python
registry = StatelessRegistry()

@registry.register("user_service")
@stateless
class UserService:
    def get_user(self, id: int):
        return {"id": id, "name": "John"}

# Usage
service = registry.get("user_service")
user = service.get_user(123)
```

## Reactive Module

Spring Reactor-inspired reactive streams for Python.

### Flux

Represents a reactive stream of 0-N elements.

```python
from rfs import Flux
```

#### Creating Flux

```python
# From iterable
flux = Flux.from_iterable([1, 2, 3, 4, 5])

# From async generator
async def generate():
    for i in range(5):
        yield i

flux = Flux.from_async_iterable(generate())

# Empty flux
empty = Flux.empty()

# Single error
error = Flux.error(Exception("Error"))
```

#### Flux Operators

**Transformation:**
- `map(fn) -> Flux`: Transform each element
- `flat_map(fn) -> Flux`: Transform and flatten
- `filter(predicate) -> Flux`: Filter elements
- `take(n) -> Flux`: Take first n elements
- `skip(n) -> Flux`: Skip first n elements
- `distinct() -> Flux`: Remove duplicates

**Aggregation:**
- `collect_list() -> List`: Collect to list
- `reduce(fn, initial) -> Any`: Reduce to single value
- `count() -> int`: Count elements
- `sum() -> Number`: Sum numeric elements

**Error Handling:**
- `on_error_return(value) -> Flux`: Return value on error
- `on_error_continue(handler) -> Flux`: Continue on error
- `on_error_map(fn) -> Flux`: Transform errors
- `retry(times) -> Flux`: Retry on error

**Backpressure:**
- `buffer(size) -> Flux`: Buffer elements
- `window(size) -> Flux[Flux]`: Window elements
- `sample(duration) -> Flux`: Sample at intervals
- `throttle(elements, duration) -> Flux`: Rate limiting

**Example:**
```python
import asyncio
from rfs import Flux

async def process_data():
    result = await (
        Flux.from_iterable(range(100))
        .map(lambda x: x * 2)
        .filter(lambda x: x % 3 == 0)
        .take(10)
        .buffer(5)
        .collect_list()
    )
    return result

# Run: asyncio.run(process_data())
```

### Mono

Represents a reactive stream of 0-1 element.

```python
from rfs import Mono
```

#### Creating Mono

```python
# From value
mono = Mono.just("value")

# From callable
mono = Mono.from_callable(lambda: expensive_operation())

# From future
mono = Mono.from_future(async_operation())

# Empty mono
empty = Mono.empty()

# Error mono
error = Mono.error(Exception("Error"))
```

#### Mono Operators

**Transformation:**
- `map(fn) -> Mono`: Transform value
- `flat_map(fn) -> Mono`: Transform to another Mono
- `filter(predicate) -> Mono`: Filter by predicate

**Combination:**
- `zip_with(other) -> Mono`: Combine with another Mono
- `then(other) -> Mono`: Chain with another Mono

**Error Handling:**
- `on_error_return(value) -> Mono`: Return value on error
- `on_error_map(fn) -> Mono`: Transform error
- `retry(times) -> Mono`: Retry on error

**Blocking:**
- `block() -> T`: Block and get value
- `block_optional() -> Optional[T]`: Block and get optional

**Example:**
```python
import asyncio
from rfs import Mono

async def fetch_user(id: int):
    return {"id": id, "name": "Alice"}

async def process():
    user = await (
        Mono.from_callable(lambda: fetch_user(123))
        .map(lambda u: u["name"])
        .map(lambda name: name.upper())
        .on_error_return("UNKNOWN")
        .block()
    )
    return user

# Run: asyncio.run(process())
```

## State Machine Module

Functional and class-based state machines.

```python
from rfs import StateMachine, State, Transition, StateType
```

### StateMachine

Core state machine implementation.

**Constructor:**
```python
machine = StateMachine(
    initial_state="draft",
    states=["draft", "review", "published", "archived"]
)
```

**Methods:**
- `current_state: str`: Get current state
- `transition_to(state: str) -> bool`: Transition to state
- `can_transition_to(state: str) -> bool`: Check if transition allowed
- `add_transition(from_state, to_state, condition)`: Add transition rule
- `get_history() -> List[str]`: Get state history

**Example:**
```python
from rfs import StateMachine

# Document workflow
doc_machine = StateMachine(
    initial_state="draft",
    states=["draft", "review", "published", "archived"]
)

# Add transitions
doc_machine.add_transition("draft", "review", lambda: True)
doc_machine.add_transition("review", "published", lambda: approved)
doc_machine.add_transition("published", "archived", lambda: True)

# Use
doc_machine.transition_to("review")  # True
doc_machine.transition_to("archived")  # False (not allowed from review)
```

### State

Represents a state with optional entry/exit actions.

```python
state = State(
    name="processing",
    on_enter=lambda: print("Entering processing"),
    on_exit=lambda: print("Exiting processing"),
    metadata={"timeout": 30}
)
```

### Transition

Represents a state transition with optional guard and action.

```python
transition = Transition(
    from_state="pending",
    to_state="processing",
    guard=lambda ctx: ctx.get("validated") == True,
    action=lambda ctx: notify_user(ctx)
)
```

## Events Module

Event-driven architecture components.

```python
from rfs import Event, EventBus, event_handler
```

### EventBus

Central event bus for publish-subscribe pattern.

**Methods:**
- `publish(event: Event) -> None`: Publish event
- `subscribe(event_type: str, handler: Callable)`: Subscribe to events
- `unsubscribe(event_type: str, handler: Callable)`: Unsubscribe
- `get_handlers(event_type: str) -> List[Callable]`: Get handlers

**Example:**
```python
from rfs import EventBus, Event

bus = EventBus()

# Subscribe
@bus.subscribe("user.created")
async def handle_user_created(event: Event):
    print(f"User created: {event.data}")

# Publish
await bus.publish(Event(
    type="user.created",
    data={"id": 123, "name": "Alice"},
    metadata={"timestamp": "2024-01-01"}
))
```

### Event

Event data structure.

**Fields:**
- `type: str`: Event type/name
- `data: Any`: Event payload
- `metadata: Dict`: Event metadata
- `timestamp: datetime`: Event timestamp
- `id: str`: Unique event ID

### Event Patterns

#### CQRS (Command Query Responsibility Segregation)

```python
from rfs.events import CommandBus, QueryBus

# Commands (write)
command_bus = CommandBus()

@command_bus.handler("CreateUser")
async def create_user(command):
    # Create user logic
    return Success(user_id)

# Queries (read)
query_bus = QueryBus()

@query_bus.handler("GetUser")
async def get_user(query):
    # Fetch user logic
    return Success(user)
```

#### Saga Pattern

```python
from rfs.events import Saga

class OrderSaga(Saga):
    def __init__(self):
        super().__init__("order_processing")
        
        self.step("reserve_inventory", 
                 self.reserve, 
                 self.release)  # Compensating action
        self.step("charge_payment",
                 self.charge,
                 self.refund)   # Compensating action
        self.step("send_notification",
                 self.notify)
    
    async def reserve(self, ctx):
        # Reserve inventory
        pass
    
    async def release(self, ctx):
        # Release inventory (compensation)
        pass
    
    async def charge(self, ctx):
        # Charge payment
        pass
    
    async def refund(self, ctx):
        # Refund payment (compensation)
        pass

# Execute saga
saga = OrderSaga()
result = await saga.execute(context)
```

## Serverless Module

Google Cloud Platform serverless optimization.

### CloudRunOptimizer

Optimizations for Google Cloud Run.

```python
from rfs.serverless import CloudRunOptimizer

optimizer = CloudRunOptimizer()
```

**Decorators:**
- `@optimizer.cold_start_detector`: Detect and optimize cold starts
- `@optimizer.cached_response(ttl=300)`: Cache responses
- `@optimizer.resource_monitor`: Monitor resource usage
- `@optimizer.metrics_collector`: Collect metrics
- `@optimizer.health_check`: Health check endpoint

**Methods:**
- `get_memory_usage() -> float`: Get memory usage percentage
- `get_cpu_usage() -> float`: Get CPU usage percentage
- `get_uptime() -> float`: Get service uptime
- `trigger_garbage_collection()`: Force garbage collection

**Example:**
```python
from rfs.serverless import CloudRunOptimizer

optimizer = CloudRunOptimizer()

@optimizer.cold_start_detector
@optimizer.cached_response(ttl=300)
async def optimized_handler(request):
    # Automatically detects cold starts
    # Caches response for 5 minutes
    result = await process_request(request)
    return result

@optimizer.resource_monitor
async def monitored_endpoint():
    if optimizer.get_memory_usage() > 0.8:
        await optimizer.trigger_garbage_collection()
    
    return {"status": "ok"}
```

### CloudTasksClient

Integration with Google Cloud Tasks.

```python
from rfs.serverless import CloudTasksClient

client = CloudTasksClient(
    project_id="my-project",
    location="asia-northeast3",
    queue_name="my-queue"
)
```

**Methods:**
- `enqueue_task(task: Dict) -> Result`: Enqueue single task
- `enqueue_batch(tasks: List[Dict]) -> List[Result]`: Enqueue multiple tasks
- `create_http_task(url, payload, delay_seconds)`: Create HTTP task
- `list_tasks() -> List[Task]`: List queue tasks
- `purge_queue()`: Purge all tasks

**Example:**
```python
# Enqueue task
result = await client.enqueue_task({
    "url": "/api/process",
    "payload": {"data": "important"},
    "delay_seconds": 60  # Execute after 1 minute
})

# Batch enqueue
tasks = [
    {"url": "/api/process", "payload": {"id": i}}
    for i in range(100)
]
results = await client.enqueue_batch(tasks)
```

## Production Module

Production readiness tools.

### SystemValidator

Comprehensive system validation.

```python
from rfs import SystemValidator, ValidationResult

validator = SystemValidator()
result = validator.validate_system()
```

**Validation Categories:**
- Configuration validation
- Security validation
- Performance validation
- Code quality validation
- Dependency validation

**Example:**
```python
validator = SystemValidator()

# Full validation
result = validator.validate_system()
print(f"Valid: {result.is_valid}")
print(f"Score: {result.score}/100")

# Specific validation
security_result = validator.validate_security()
perf_result = validator.validate_performance()
```

### PerformanceOptimizer

Performance optimization engine.

```python
from rfs import PerformanceOptimizer

optimizer = PerformanceOptimizer()
```

**Methods:**
- `analyze() -> OptimizationResult`: Analyze performance
- `optimize() -> Result`: Apply optimizations
- `benchmark(fn) -> BenchmarkResult`: Benchmark function
- `profile(fn) -> ProfileResult`: Profile function

**Example:**
```python
optimizer = PerformanceOptimizer()

# Analyze current performance
analysis = optimizer.analyze()
print(f"Bottlenecks: {analysis.bottlenecks}")
print(f"Recommendations: {analysis.recommendations}")

# Apply optimizations
result = optimizer.optimize()
if result.is_success:
    print(f"Improved by {result.improvement}%")
```

### SecurityScanner

Security vulnerability scanner.

```python
from rfs import SecurityScanner

scanner = SecurityScanner()
```

**Methods:**
- `scan() -> VulnerabilityReport`: Full security scan
- `scan_dependencies() -> List[Vulnerability]`: Scan dependencies
- `scan_code() -> List[Issue]`: Scan source code
- `check_compliance(standard: str) -> ComplianceResult`: Check compliance

**Example:**
```python
scanner = SecurityScanner()

# Full scan
report = scanner.scan()
print(f"Vulnerabilities: {report.vulnerability_count}")
print(f"Threat level: {report.threat_level}")

# Check OWASP compliance
owasp = scanner.check_compliance("OWASP")
print(f"OWASP compliant: {owasp.is_compliant}")
```

### ProductionReadinessChecker

Production deployment readiness verification.

```python
from rfs import ProductionReadinessChecker

checker = ProductionReadinessChecker()
```

**Methods:**
- `check() -> ReadinessReport`: Full readiness check
- `check_infrastructure() -> Result`: Check infrastructure
- `check_monitoring() -> Result`: Check monitoring
- `check_security() -> Result`: Check security
- `check_performance() -> Result`: Check performance

**Example:**
```python
checker = ProductionReadinessChecker()

report = checker.check()
if report.is_ready:
    print("Ready for production!")
else:
    print(f"Issues found: {report.issues}")
    print(f"Recommendations: {report.recommendations}")
```

## Usage Examples

### Complete E-commerce Order Processing

```python
import asyncio
from rfs import (
    Flux, Mono, Result, Success, Failure,
    StatelessRegistry, StateMachine,
    EventBus, Event, Saga
)

# Setup
registry = StatelessRegistry()
event_bus = EventBus()

@registry.register("order_service")
class OrderService:
    def __init__(self):
        self.state_machine = StateMachine(
            initial_state="pending",
            states=["pending", "paid", "shipped", "delivered", "cancelled"]
        )
    
    async def process_order(self, order_data):
        # Validate order
        validation = self.validate_order(order_data)
        if validation.is_failure:
            return validation
        
        # Process payment
        payment_result = await self.process_payment(order_data)
        if payment_result.is_failure:
            return payment_result
        
        # Update state
        self.state_machine.transition_to("paid")
        
        # Publish event
        await event_bus.publish(Event(
            type="order.paid",
            data={"order_id": order_data["id"]}
        ))
        
        return Success({"order_id": order_data["id"], "status": "paid"})
    
    def validate_order(self, order_data):
        if not order_data.get("items"):
            return Failure("No items in order")
        if order_data.get("total", 0) <= 0:
            return Failure("Invalid total amount")
        return Success(order_data)
    
    async def process_payment(self, order_data):
        # Simulate payment processing
        await asyncio.sleep(0.1)
        return Success({"transaction_id": "txn_123"})

# Usage
async def main():
    service = registry.get("order_service")
    
    # Process multiple orders
    orders = [
        {"id": 1, "items": ["item1"], "total": 100},
        {"id": 2, "items": ["item2"], "total": 200},
        {"id": 3, "items": [], "total": 0},  # Will fail
    ]
    
    results = await Flux.from_iterable(orders) \
        .map(lambda order: service.process_order(order)) \
        .collect_list()
    
    for result in results:
        if result.is_success:
            print(f"Order processed: {result.unwrap()}")
        else:
            print(f"Order failed: {result.unwrap_err()}")

asyncio.run(main())
```

### Real-time Data Pipeline

```python
import asyncio
from rfs import Flux, Mono, EventBus, Event
from rfs.serverless import CloudRunOptimizer

optimizer = CloudRunOptimizer()
event_bus = EventBus()

@optimizer.cold_start_detector
async def data_pipeline(data_stream):
    """Process real-time data stream"""
    
    # Subscribe to events
    @event_bus.subscribe("data.processed")
    async def on_processed(event: Event):
        print(f"Processed: {event.data}")
    
    @event_bus.subscribe("data.error")
    async def on_error(event: Event):
        print(f"Error: {event.data}")
    
    # Process stream
    results = await (
        Flux.from_iterable(data_stream)
        .map(lambda x: validate_data(x))
        .filter(lambda r: r.is_success)
        .map(lambda r: r.unwrap())
        .buffer(10)  # Process in batches
        .flat_map(lambda batch: process_batch(batch))
        .on_error_continue(lambda err: 
            event_bus.publish(Event("data.error", {"error": str(err)}))
        )
        .collect_list()
    )
    
    # Publish completion
    await event_bus.publish(Event(
        "pipeline.complete",
        {"processed": len(results)}
    ))
    
    return results

def validate_data(data):
    if data.get("value", 0) < 0:
        return Failure("Negative value")
    return Success(data)

async def process_batch(batch):
    # Simulate batch processing
    await asyncio.sleep(0.01)
    return [{"processed": item} for item in batch]

# Usage
async def main():
    test_data = [
        {"value": 10},
        {"value": -5},  # Will be filtered
        {"value": 20},
        {"value": 30},
    ]
    
    results = await data_pipeline(test_data)
    print(f"Processed {len(results)} items")

asyncio.run(main())
```

## Best Practices

1. **Error Handling**: Always use Result pattern for operations that can fail
2. **Async Operations**: Use Mono/Flux for async operations
3. **State Management**: Use StateMachine for complex workflows
4. **Dependency Injection**: Use StatelessRegistry for service management
5. **Event-Driven**: Use EventBus for decoupled communication
6. **Serverless**: Use CloudRunOptimizer for production deployments
7. **Testing**: Validate with SystemValidator before production
8. **Performance**: Profile with PerformanceOptimizer
9. **Security**: Scan with SecurityScanner regularly
10. **Documentation**: Keep API documentation up-to-date