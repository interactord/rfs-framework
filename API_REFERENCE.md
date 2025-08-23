# RFS Framework - API Reference

> **RFS Framework 4.0.0 완전한 API 문서**

## 📋 Table of Contents

- [Core Framework](#-core-framework)
  - [Result Pattern](#result-pattern)
  - [Configuration Management](#configuration-management)
  - [Service Registry](#service-registry)
- [Reactive Programming](#-reactive-programming)
  - [Mono](#mono)
  - [Flux](#flux)
  - [Operators](#operators)
- [State Management](#-state-management)
  - [State Machine](#state-machine)
  - [Actions](#actions)
- [Event System](#-event-system)
  - [Event Bus](#event-bus)
  - [Event Handlers](#event-handlers)
- [Cloud Native](#-cloud-native)
  - [Service Discovery](#service-discovery)
  - [Task Queue](#task-queue)
  - [Monitoring](#monitoring)
  - [Auto Scaling](#auto-scaling)
- [Production Framework](#-production-framework)
  - [System Validation](#system-validation)
  - [Performance Optimization](#performance-optimization)
  - [Security Scanning](#security-scanning)
  - [Production Readiness](#production-readiness)

---

## 🔧 Core Framework

### Result Pattern

함수형 에러 핸들링을 위한 Result 패턴 구현.

#### `Result[T, E]`

```python
from rfs import Result, Success, Failure

# 성공 케이스
success = Success("Hello World")
assert success.is_success
assert success.unwrap() == "Hello World"

# 실패 케이스
failure = Result.failure("Something went wrong")
assert failure.is_failure()
assert failure.error == "Something went wrong"
```

#### Methods

##### `Result.success(value: T) -> Result[T, E]`
성공 결과를 생성합니다.

```python
result = Result.success(42)
print(result.value)  # 42
```

##### `Result.failure(error: E) -> Result[T, E]`
실패 결과를 생성합니다.

```python
result = Result.failure("Error message")
print(result.error)  # Error message
```

##### `is_success() -> bool`
성공 여부를 확인합니다.

##### `is_failure() -> bool`
실패 여부를 확인합니다.

##### `map(func: Callable[[T], U]) -> Result[U, E]`
성공한 경우에만 값을 변환합니다.

```python
result = Result.success(5).map(lambda x: x * 2)
assert result.value == 10
```

##### `flat_map(func: Callable[[T], Result[U, E]]) -> Result[U, E]`
성공한 경우에만 다른 Result를 반환하는 함수를 적용합니다.

```python
def divide(x, y):
    if y == 0:
        return Result.failure("Division by zero")
    return Result.success(x / y)

result = Result.success(10).flat_map(lambda x: divide(x, 2))
assert result.value == 5.0
```

##### `match(on_success: Callable, on_failure: Callable) -> U`
패턴 매칭을 통해 결과를 처리합니다.

```python
result = Result.success("Hello")
output = result.match(
    on_success=lambda x: f"Success: {x}",
    on_failure=lambda e: f"Error: {e}"
)
assert output == "Success: Hello"
```

### Configuration Management

환경별 설정 관리 시스템.

#### `RFSConfig`

```python
from rfs_v4.core import RFSConfig, Environment

class MyAppConfig(RFSConfig):
    database_url: str
    redis_url: str
    debug: bool = False
    
    class Config:
        env_prefix = "MYAPP_"
```

#### `ConfigManager`

```python
from rfs_v4.core import ConfigManager

# 설정 로드
config = ConfigManager.load("config.toml", MyAppConfig)

# 환경별 설정
dev_config = ConfigManager.load_profile("development", MyAppConfig)
prod_config = ConfigManager.load_profile("production", MyAppConfig)
```

#### Environment Detection

```python
from rfs_v4.core import detect_current_environment, Environment

env = detect_current_environment()
if env == Environment.PRODUCTION:
    # 프로덕션 설정
    pass
elif env == Environment.DEVELOPMENT:
    # 개발 설정
    pass
```

### Service Registry

의존성 주입을 위한 서비스 레지스트리.

#### `ServiceRegistry`

```python
from rfs_v4.core import ServiceRegistry, stateless

registry = ServiceRegistry()

# 서비스 등록
@stateless
class DatabaseService:
    def get_connection(self):
        return "database connection"

registry.register(DatabaseService)

# 서비스 조회
db_service = registry.get(DatabaseService)
```

---

## ⚡ Reactive Programming

### Mono

단일 값 반응형 스트림.

#### Creation

```python
from rfs_v4.reactive import Mono

# 값으로 생성
mono = Mono.just("Hello")

# 빈 스트림
empty = Mono.empty()

# 에러 스트림
error = Mono.error(Exception("Something went wrong"))

# 지연 생성
lazy = Mono.from_callable(lambda: expensive_operation())
```

#### Transformation

```python
# map: 값 변환
result = await Mono.just(5).map(lambda x: x * 2).to_result()
assert result.value == 10

# filter: 조건 필터링
result = await Mono.just(5).filter(lambda x: x > 3).to_result()
assert result.is_success()

# flat_map: 중첩된 Mono 펼치기
result = await (
    Mono.just(5)
    .flat_map(lambda x: Mono.just(x * 2))
    .to_result()
)
assert result.value == 10
```

#### Error Handling

```python
# on_error_resume: 에러 시 대체값 제공
result = await (
    Mono.error(Exception("Error"))
    .on_error_resume(lambda e: Mono.just("Default"))
    .to_result()
)
assert result.value == "Default"

# retry: 재시도
result = await (
    Mono.from_callable(unreliable_operation)
    .retry(max_attempts=3)
    .to_result()
)
```

### Flux

다중 값 반응형 스트림.

#### Creation

```python
from rfs_v4.reactive import Flux

# 이터러블로 생성
flux = Flux.from_iterable([1, 2, 3, 4, 5])

# 범위 생성
range_flux = Flux.range(1, 10)

# 간격 생성
interval = Flux.interval(1.0)  # 1초마다
```

#### Transformation

```python
# map: 각 값 변환
result = await (
    Flux.from_iterable([1, 2, 3])
    .map(lambda x: x * 2)
    .collect_list()
    .to_result()
)
assert result.value == [2, 4, 6]

# filter: 조건 필터링
result = await (
    Flux.from_iterable([1, 2, 3, 4, 5])
    .filter(lambda x: x % 2 == 0)
    .collect_list()
    .to_result()
)
assert result.value == [2, 4]

# flat_map: 중첩된 스트림 펼치기
result = await (
    Flux.from_iterable([1, 2, 3])
    .flat_map(lambda x: Flux.from_iterable([x, x * 10]))
    .collect_list()
    .to_result()
)
assert result.value == [1, 10, 2, 20, 3, 30]
```

#### Aggregation

```python
# reduce: 값 축약
result = await (
    Flux.from_iterable([1, 2, 3, 4, 5])
    .reduce(lambda acc, x: acc + x, 0)
    .to_result()
)
assert result.value == 15

# count: 개수 세기
result = await (
    Flux.from_iterable([1, 2, 3, 4, 5])
    .count()
    .to_result()
)
assert result.value == 5
```

#### Combination

```python
# merge: 여러 스트림 병합
flux1 = Flux.from_iterable([1, 3, 5])
flux2 = Flux.from_iterable([2, 4, 6])

result = await (
    Flux.merge(flux1, flux2)
    .collect_list()
    .to_result()
)
# 순서는 보장되지 않음

# zip: 스트림 조합
result = await (
    Flux.zip(flux1, flux2, lambda a, b: (a, b))
    .collect_list()
    .to_result()
)
assert result.value == [(1, 2), (3, 4), (5, 6)]
```

### Operators

스트림 변환을 위한 연산자들.

#### Core Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `map` | 값 변환 | `map(lambda x: x * 2)` |
| `filter` | 조건 필터링 | `filter(lambda x: x > 0)` |
| `flat_map` | 중첩 스트림 펼치기 | `flat_map(lambda x: Mono.just(x))` |
| `distinct` | 중복 제거 | `distinct()` |
| `take` | 처음 N개 선택 | `take(5)` |
| `skip` | 처음 N개 건너뛰기 | `skip(2)` |

#### Utility Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `cache` | 결과 캐싱 | `cache(ttl=3600)` |
| `timeout` | 타임아웃 설정 | `timeout(5.0)` |
| `retry` | 재시도 | `retry(max_attempts=3)` |
| `delay` | 지연 실행 | `delay(1.0)` |

---

## 🎭 State Management

### State Machine

함수형 상태 머신 구현.

#### Basic Usage

```python
from rfs_v4.state_machine import StateMachine, State, Transition

# 상태 정의
IDLE = State("idle")
PROCESSING = State("processing")
COMPLETED = State("completed")
FAILED = State("failed")

# 상태 머신 생성
machine = StateMachine(
    initial_state=IDLE,
    states=[IDLE, PROCESSING, COMPLETED, FAILED],
    transitions=[
        Transition(IDLE, "start", PROCESSING),
        Transition(PROCESSING, "complete", COMPLETED),
        Transition(PROCESSING, "fail", FAILED),
        Transition(COMPLETED, "reset", IDLE),
        Transition(FAILED, "retry", PROCESSING),
    ]
)

# 상태 전환
result = await machine.dispatch("start")
assert machine.current_state == PROCESSING
```

#### Advanced Features

```python
# 조건부 전환
def can_process(context):
    return context.get("ready", False)

transition = Transition(
    from_state=IDLE,
    event="start",
    to_state=PROCESSING,
    guard=can_process
)

# 액션 실행
def on_start(context):
    print("Starting processing...")
    return context

transition = Transition(
    from_state=IDLE,
    event="start", 
    to_state=PROCESSING,
    action=on_start
)
```

### Actions

상태 변경을 위한 액션 시스템.

#### Action Definition

```python
from rfs_v4.state_machine import Action

class StartProcessingAction(Action):
    def execute(self, context: dict) -> dict:
        return {
            **context,
            "processing_started": True,
            "start_time": time.time()
        }

class CompleteProcessingAction(Action):
    def execute(self, context: dict) -> dict:
        return {
            **context,
            "processing_completed": True,
            "end_time": time.time()
        }
```

---

## 📡 Event System

### Event Bus

이벤트 기반 통신을 위한 이벤트 버스.

#### Basic Usage

```python
from rfs_v4.events import EventBus, Event, event_handler

bus = EventBus()

# 이벤트 정의
@dataclass
class UserCreated(Event):
    user_id: str
    email: str

# 이벤트 핸들러
@event_handler(UserCreated)
async def send_welcome_email(event: UserCreated):
    await email_service.send_welcome(event.email)

@event_handler(UserCreated) 
async def create_user_profile(event: UserCreated):
    await profile_service.create(event.user_id)

# 이벤트 발행
await bus.publish(UserCreated(user_id="123", email="user@example.com"))
```

#### Event Filtering

```python
from rfs_v4.events import EventFilter

# 조건부 핸들러
@event_handler(UserCreated, filter=lambda e: e.email.endswith("@company.com"))
async def handle_company_user(event: UserCreated):
    # 회사 이메일 사용자만 처리
    pass
```

### Event Handlers

이벤트 처리를 위한 핸들러 시스템.

#### Async Handlers

```python
@event_handler(OrderPlaced)
async def process_payment(event: OrderPlaced):
    payment_result = await payment_service.charge(
        amount=event.total_amount,
        card_token=event.card_token
    )
    
    if payment_result.is_success():
        await bus.publish(PaymentCompleted(order_id=event.order_id))
    else:
        await bus.publish(PaymentFailed(
            order_id=event.order_id,
            reason=payment_result.error
        ))
```

#### Error Handling

```python
@event_handler(OrderPlaced, retry_attempts=3, retry_delay=1.0)
async def unreliable_handler(event: OrderPlaced):
    # 실패 시 자동 재시도
    result = await external_service.call()
    if not result.success:
        raise Exception("Service unavailable")
```

---

## ☁️ Cloud Native

### Service Discovery

마이크로서비스 디스커버리 및 통신.

#### Service Registration

```python
from rfs_v4.cloud_run import CloudRunServiceDiscovery, ServiceEndpoint

discovery = CloudRunServiceDiscovery()

# 서비스 등록
endpoint = ServiceEndpoint(
    name="user-service",
    url="https://user-service-hash-uc.a.run.app",
    region="us-central1",
    health_check_path="/health"
)

await discovery.register_service(endpoint)
```

#### Service Discovery

```python
# 서비스 조회
services = await discovery.discover_services("user-service")
user_service = services[0]

# 서비스 호출
response = await discovery.call_service(
    service_name="user-service",
    method="GET",
    path="/users/123"
)
```

#### Load Balancing

```python
# 라운드 로빈 로드 밸런싱
response = await discovery.call_service(
    service_name="user-service",
    method="POST", 
    path="/users",
    json={"name": "John", "email": "john@example.com"},
    load_balancing="round_robin"
)
```

### Task Queue

비동기 작업 처리를 위한 태스크 큐.

#### Task Definition

```python
from rfs_v4.cloud_run import CloudTaskQueue, TaskDefinition, task_handler

queue = CloudTaskQueue(
    project_id="my-project",
    location="us-central1",
    queue_name="default-queue"
)

# 태스크 정의
@task_handler("send-email")
async def send_email_task(payload: dict):
    email = payload["email"]
    subject = payload["subject"]
    body = payload["body"]
    
    await email_service.send(email, subject, body)
    return {"status": "sent", "email": email}
```

#### Task Submission

```python
# 즉시 실행
task_id = await queue.submit_task(
    task_type="send-email",
    payload={
        "email": "user@example.com",
        "subject": "Welcome!",
        "body": "Welcome to our service!"
    }
)

# 지연 실행
from datetime import datetime, timedelta

schedule_time = datetime.utcnow() + timedelta(hours=1)
task_id = await queue.schedule_task(
    task_type="send-email",
    payload={"email": "user@example.com", "subject": "Reminder"},
    schedule_time=schedule_time
)
```

### Monitoring

시스템 모니터링 및 메트릭 수집.

#### Metrics Collection

```python
from rfs_v4.cloud_run import CloudMonitoringClient, record_metric

monitoring = CloudMonitoringClient()

# 기본 메트릭
await record_metric("request_count", 1, labels={"endpoint": "/users"})
await record_metric("response_time", 0.150, labels={"endpoint": "/users"})

# 커스텀 메트릭
await monitoring.record_custom_metric(
    metric_name="business/orders_processed",
    value=1,
    labels={"region": "us-west", "product": "premium"}
)
```

#### Performance Monitoring

```python
from rfs_v4.cloud_run import monitor_performance

@monitor_performance
async def expensive_operation():
    # 자동으로 실행 시간과 리소스 사용량 측정
    result = await complex_computation()
    return result

# 수동 모니터링
async with monitoring.track_performance("database_query"):
    result = await database.query("SELECT * FROM large_table")
```

#### Logging

```python
from rfs_v4.cloud_run import log_info, log_warning, log_error

# 구조화된 로깅
await log_info("User login", extra={
    "user_id": "123",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
})

await log_warning("Rate limit approaching", extra={
    "current_requests": 900,
    "limit": 1000,
    "window": "1m"
})

await log_error("Database connection failed", extra={
    "error": str(exception),
    "retry_count": 3,
    "database_host": "db.example.com"
})
```

### Auto Scaling

자동 스케일링 및 리소스 최적화.

#### Scaling Configuration

```python
from rfs_v4.cloud_run import AutoScalingOptimizer, ScalingConfiguration

optimizer = AutoScalingOptimizer()

config = ScalingConfiguration(
    min_instances=1,
    max_instances=100,
    target_cpu_utilization=70,
    target_memory_utilization=80,
    max_concurrent_requests=100,
    scale_up_threshold=0.8,
    scale_down_threshold=0.3
)

await optimizer.configure_scaling(config)
```

#### Predictive Scaling

```python
# 트래픽 패턴 분석
traffic_pattern = await optimizer.analyze_traffic_pattern(days=30)

# 예측 기반 스케일링
await optimizer.enable_predictive_scaling(
    pattern=traffic_pattern,
    scale_ahead_minutes=5
)
```

---

## 🔒 Production Framework

### System Validation

포괄적인 시스템 검증 프레임워크.

#### Validation Suite Setup

```python
from rfs_v4.validation import SystemValidator, ValidationSuite, ValidationCategory

validator = SystemValidator()

# 검증 스위트 정의
suite = ValidationSuite(
    categories=[
        ValidationCategory.FUNCTIONAL,
        ValidationCategory.INTEGRATION,
        ValidationCategory.PERFORMANCE,
        ValidationCategory.SECURITY,
        ValidationCategory.COMPATIBILITY
    ],
    target_directories=["./src", "./tests"],
    config_files=["config.toml", "requirements.txt"]
)
```

#### Running Validations

```python
# 전체 검증 실행
validation_result = await validator.run_validation(suite)

if validation_result.is_success():
    report = validation_result.value
    print(f"Validation Score: {report.overall_score}/100")
    
    for category, results in report.category_results.items():
        print(f"{category}: {len(results)} checks")
        for result in results:
            if result.severity == "high" and not result.passed:
                print(f"  ❌ {result.check_name}: {result.message}")
else:
    print(f"Validation failed: {validation_result.error}")
```

#### Custom Validation Rules

```python
from rfs_v4.validation import ValidationRule

class DatabaseConnectionRule(ValidationRule):
    async def check(self, context: dict) -> bool:
        try:
            db = context.get("database")
            await db.ping()
            return True
        except Exception:
            return False
    
    @property
    def name(self) -> str:
        return "Database Connection Check"
    
    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.FUNCTIONAL

# 커스텀 룰 등록
validator.add_rule(DatabaseConnectionRule())
```

### Performance Optimization

시스템 성능 분석 및 최적화.

#### Optimization Suite

```python
from rfs_v4.optimization import (
    PerformanceOptimizer, OptimizationSuite, OptimizationType
)

optimizer = PerformanceOptimizer()

suite = OptimizationSuite(
    types=[
        OptimizationType.MEMORY,
        OptimizationType.CPU,
        OptimizationType.IO,
        OptimizationType.CLOUD_RUN
    ],
    target_directories=["./src"],
    profiling_duration=60  # 60초간 프로파일링
)
```

#### Running Optimization Analysis

```python
# 최적화 분석 실행
optimization_result = await optimizer.run_optimization_analysis(suite)

if optimization_result.is_success():
    results = optimization_result.value
    
    for result in results:
        print(f"\n{result.optimization_type} Optimization:")
        print(f"Current Score: {result.current_score}/100")
        print(f"Potential Improvement: {result.improvement_potential}%")
        print(f"ROI Score: {result.roi_score}")
        
        for suggestion in result.suggestions:
            print(f"  • {suggestion}")
```

#### Memory Optimization

```python
# 메모리 사용량 분석
memory_report = await optimizer.analyze_memory_usage(
    target_directories=["./src"],
    profiling_duration=30
)

# 메모리 누수 탐지
leaks = await optimizer.detect_memory_leaks(
    test_duration=60,
    threshold_mb=10
)
```

#### CPU Optimization

```python
# CPU 프로파일링
cpu_profile = await optimizer.profile_cpu_usage(
    target_functions=["process_data", "handle_request"],
    duration=30
)

# 병목 지점 식별
bottlenecks = await optimizer.identify_cpu_bottlenecks(
    threshold_percent=80
)
```

### Security Scanning

보안 취약점 탐지 및 보안 강화.

#### Security Scanner

```python
from rfs_v4.security import SecurityScanner, ThreatLevel

scanner = SecurityScanner()

# 전체 보안 스캔
scan_result = await scanner.scan_directory("./src")

if scan_result.is_success():
    vulnerabilities = scan_result.value
    
    # 심각도별 분류
    critical = [v for v in vulnerabilities if v.threat_level == ThreatLevel.CRITICAL]
    high = [v for v in vulnerabilities if v.threat_level == ThreatLevel.HIGH]
    
    print(f"Critical: {len(critical)}, High: {len(high)}")
    
    for vuln in critical:
        print(f"🚨 {vuln.vulnerability_type}: {vuln.description}")
        print(f"   File: {vuln.file_path}:{vuln.line_number}")
        print(f"   CWE: {vuln.cwe_id}, CVSS: {vuln.cvss_score}")
```

#### Specific Security Checks

```python
# SQL 인젝션 검사
sql_issues = await scanner.check_sql_injection("./src")

# 하드코딩된 시크릿 검사  
secret_issues = await scanner.check_hardcoded_secrets("./src")

# 경로 순회 공격 검사
path_issues = await scanner.check_path_traversal("./src")

# 의존성 취약점 검사
dependency_issues = await scanner.check_dependency_vulnerabilities()
```

#### Security Hardening

```python
from rfs_v4.security import SecurityHardening, SecurityPolicy

hardening = SecurityHardening()

# 보안 정책 정의
policy = SecurityPolicy(
    enforce_https=True,
    require_authentication=True,
    enable_rate_limiting=True,
    max_request_size=1024 * 1024,  # 1MB
    allowed_file_types=[".jpg", ".png", ".pdf"],
    password_min_length=12
)

# 보안 강화 적용
hardening_result = await hardening.apply_security_policy(policy)
```

### Production Readiness

프로덕션 배포 준비성 검증.

#### Readiness Checker

```python
from rfs_v4.production import ProductionReadinessChecker, ReadinessLevel

checker = ProductionReadinessChecker()

# 프로덕션 준비성 검사
readiness_result = await checker.run_readiness_check(
    target_level=ReadinessLevel.PRODUCTION_READY
)

if readiness_result.is_success():
    report = readiness_result.value
    
    print(f"Overall Readiness: {report.overall_score}/100")
    print(f"Ready for Production: {'Yes' if report.is_ready else 'No'}")
    
    # 카테고리별 점검 결과
    for category, checks in report.category_results.items():
        passed = sum(1 for c in checks if c.passed)
        total = len(checks)
        print(f"{category}: {passed}/{total} passed")
        
        # 실패한 검사 표시
        failed = [c for c in checks if not c.passed and c.severity == "high"]
        for check in failed:
            print(f"  ❌ {check.check_name}: {check.message}")
```

#### Custom Readiness Checks

```python
from rfs_v4.production import ReadinessCheck

class LoadTestCheck(ReadinessCheck):
    async def execute(self) -> bool:
        # 부하 테스트 실행
        result = await run_load_test(
            target_url="https://api.example.com",
            duration=60,
            concurrent_users=100
        )
        
        return (
            result.avg_response_time < 200 and
            result.error_rate < 0.1 and
            result.throughput > 100
        )
    
    @property
    def name(self) -> str:
        return "Load Test Validation"
    
    @property 
    def description(self) -> str:
        return "Validates system performance under load"
    
    @property
    def category(self) -> str:
        return "performance"

# 커스텀 체크 추가
checker.add_check(LoadTestCheck())
```

#### Deployment Pipeline

```python
from rfs_v4.production import ProductionDeployer, DeploymentStrategy

deployer = ProductionDeployer()

# 카나리 배포 전략
strategy = DeploymentStrategy.CANARY(
    canary_percentage=10,
    validation_duration=300,  # 5분
    rollback_threshold=0.05   # 5% 에러율
)

# 배포 실행
deployment_result = await deployer.deploy(
    version="v1.2.0",
    strategy=strategy,
    health_check_url="/health",
    readiness_check_url="/ready"
)

if deployment_result.is_success():
    deployment_id = deployment_result.value["deployment_id"]
    
    # 배포 상태 모니터링
    status = await deployer.get_deployment_status(deployment_id)
    print(f"Deployment Status: {status}")
```

---

## 📊 Performance Benchmarks

### Framework Overhead

| Operation | Time (μs) | Memory (KB) |
|-----------|-----------|-------------|
| Result.success() | 0.8 | 0.1 |
| Result.map() | 1.2 | 0.1 |
| Mono.just() | 2.5 | 0.3 |
| Flux.from_iterable(100) | 15.0 | 2.1 |
| Event publish | 12.0 | 1.5 |
| State transition | 8.5 | 0.8 |

### Reactive Streams Performance

```python
# 1M 요소 처리 벤치마크
items = list(range(1_000_000))

# 동기 처리
start = time.time()
result = [x * 2 for x in items if x % 2 == 0]
sync_time = time.time() - start

# 반응형 처리
start = time.time()
result = await (
    Flux.from_iterable(items)
    .filter(lambda x: x % 2 == 0)
    .map(lambda x: x * 2)
    .collect_list()
    .to_result()
)
reactive_time = time.time() - start

print(f"Sync: {sync_time:.3f}s")
print(f"Reactive: {reactive_time:.3f}s") 
print(f"Improvement: {((sync_time - reactive_time) / sync_time * 100):.1f}%")
```

---

## 🔍 Type Annotations

RFS Framework v4는 완전한 타입 안전성을 제공합니다.

### Generic Types

```python
from typing import TypeVar, Generic
from rfs_v4.core import Result

T = TypeVar('T')
E = TypeVar('E')

def process_data(data: list[T]) -> Result[list[T], str]:
    if not data:
        return Result.failure("Empty data")
    
    processed = [item for item in data if item is not None]
    return Result.success(processed)

# 타입 체크 통과
result: Result[list[int], str] = process_data([1, 2, 3])
```

### Protocol Support

```python
from typing import Protocol
from rfs_v4.reactive import Mono

class Serializable(Protocol):
    def to_dict(self) -> dict: ...

def serialize_items(items: list[Serializable]) -> Mono[list[dict]]:
    return Mono.just([item.to_dict() for item in items])
```

---

## 🐛 Error Handling Patterns

### Result Pattern Best Practices

```python
# ✅ 좋은 예: 체이닝 사용
async def process_user(user_id: int) -> Result[dict, str]:
    return await (
        get_user(user_id)
        .flat_map(lambda user: validate_user(user))
        .flat_map(lambda user: enrich_user_data(user))
        .map(lambda user: format_user_response(user))
    )

# ❌ 나쁜 예: 중첩된 if문
async def process_user_bad(user_id: int) -> Result[dict, str]:
    user_result = await get_user(user_id)
    if user_result.is_failure():
        return user_result
    
    validation_result = await validate_user(user_result.value)
    if validation_result.is_failure():
        return validation_result
    
    # ... 중첩 계속
```

### Error Aggregation

```python
from rfs_v4.core import ResultList

async def validate_order(order_data: dict) -> Result[dict, list[str]]:
    validations = [
        validate_customer(order_data.get("customer")),
        validate_items(order_data.get("items")), 
        validate_payment(order_data.get("payment")),
        validate_shipping(order_data.get("shipping"))
    ]
    
    results = await ResultList.all(validations)
    
    if results.is_success():
        return Result.success(order_data)
    else:
        return Result.failure(results.errors)
```

---

## 📚 Additional Resources

- **[Examples Repository](./examples/)** - Complete working examples
- **[Migration Guide](./MIGRATION_GUIDE.md)** - Upgrading from v3.x
- **[Performance Guide](./docs/performance.md)** - Optimization techniques
- **[Security Guide](./docs/security.md)** - Security best practices
- **[Cloud Run Guide](./docs/cloud-run.md)** - Cloud deployment guide

---

**API Reference v4.0.0** | **Generated: 2025-08-23** | **[RFS Framework](https://rfs-framework.dev)**