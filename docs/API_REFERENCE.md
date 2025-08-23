# RFS Framework v4.2 API Reference

## 목차

1. [성능 최적화 API](#성능-최적화-api)
2. [프로덕션 관리 API](#프로덕션-관리-api)
3. [통합 시스템 API](#통합-시스템-api)

---

## 성능 최적화 API

### System Profiler

시스템 성능을 프로파일링하고 분석합니다.

```python
from rfs.performance.profiling import get_system_profiler, ProfileLevel

# 프로파일러 초기화
profiler = get_system_profiler()

# 프로파일러 시작
await profiler.start()

# 프로파일 시작
await profiler.start_profile(
    operation_name="my_operation",
    level=ProfileLevel.DETAILED
)

# 작업 수행
# ...

# 프로파일 종료
result = await profiler.stop_profile("my_operation")
profile = result.value

# 결과 확인
print(f"Duration: {profile.duration}s")
print(f"Memory Used: {profile.memory_used} bytes")
print(f"CPU Usage: {profile.cpu_usage}%")
```

#### ProfileLevel 옵션

- `BASIC`: 기본 메트릭만 수집
- `DETAILED`: 상세 메트릭 포함
- `COMPREHENSIVE`: 모든 메트릭 수집

### Cloud Run Optimizer

Google Cloud Run 환경에 최적화된 설정을 제공합니다.

```python
from rfs.performance.optimization import get_cloud_run_optimizer

optimizer = get_cloud_run_optimizer()

# 최적화 수행
result = await optimizer.optimize()
recommendations = result.value

# 자동 스케일링 설정
await optimizer.configure_autoscaling(
    min_instances=1,
    max_instances=100,
    target_cpu_utilization=70
)

# 콜드 스타트 최적화
await optimizer.optimize_cold_start()
```

### Memory Optimizer

메모리 사용을 최적화합니다.

```python
from rfs.performance.optimization import get_memory_optimizer, OptimizationStrategy

optimizer = get_memory_optimizer()

# 메모리 분석
analysis = await optimizer.analyze()

# 최적화 수행
await optimizer.optimize(
    strategy=OptimizationStrategy.BALANCED,
    target_reduction_percent=20
)

# 가비지 컬렉션 강제 실행
await optimizer.force_garbage_collection()
```

#### OptimizationStrategy 옵션

- `CONSERVATIVE`: 안전한 최적화만 수행
- `BALANCED`: 균형잡힌 최적화
- `AGGRESSIVE`: 공격적인 최적화

---

## 프로덕션 관리 API

### Production Monitor

실시간 프로덕션 모니터링을 제공합니다.

```python
from rfs.production.monitoring import get_production_monitor

monitor = get_production_monitor()

# 모니터 시작
await monitor.start()

# 현재 메트릭 조회
metrics = monitor.get_current_metrics()

# 커스텀 메트릭 추가
monitor.add_custom_metric(
    name="api_requests",
    value=100,
    tags={"endpoint": "/api/users"}
)

# 메트릭 히스토리 조회
history = monitor.get_metrics_history(
    metric_name="cpu_percent",
    duration_minutes=60
)
```

### Alert Manager

알림 관리 및 에스컬레이션을 처리합니다.

```python
from rfs.production.monitoring import get_alert_manager, AlertLevel

alert_manager = get_alert_manager()

# 알림 규칙 추가
alert_manager.add_rule(
    rule_id="high_memory",
    name="High Memory Usage",
    condition="memory_percent > 90",
    level=AlertLevel.CRITICAL,
    channels=["email", "slack"]
)

# 알림 생성
alert = await alert_manager.create_alert(
    rule_id="high_memory",
    title="Memory Usage Critical",
    message="Memory usage is above 90%",
    level=AlertLevel.CRITICAL
)

# 알림 확인
await alert_manager.acknowledge_alert(
    alert_id=alert.value.id,
    acknowledged_by="admin"
)

# 알림 해결
await alert_manager.resolve_alert(alert.value.id)
```

#### AlertLevel 옵션

- `INFO`: 정보성 알림
- `WARNING`: 경고
- `ERROR`: 오류
- `CRITICAL`: 심각한 오류

### Health Checker

서비스 헬스 체크를 수행합니다.

```python
from rfs.production.monitoring import get_health_checker, HealthCheckType

health_checker = get_health_checker()

# HTTP 헬스 체크 추가
health_checker.add_check(
    check_id="api_health",
    name="API Health",
    check_type=HealthCheckType.HTTP,
    config={
        "url": "http://api.example.com/health",
        "method": "GET",
        "timeout": 5,
        "expected_status": 200
    }
)

# 데이터베이스 헬스 체크 추가
health_checker.add_check(
    check_id="db_health",
    name="Database Health",
    check_type=HealthCheckType.DATABASE,
    config={
        "connection_string": "postgresql://...",
        "query": "SELECT 1"
    }
)

# 헬스 체크 실행
results = await health_checker.run_all_checks()

# 전체 헬스 상태
overall_health = health_checker.get_overall_health()
```

### Disaster Recovery Manager

재해 복구 계획을 관리하고 실행합니다.

```python
from rfs.production.recovery import (
    get_disaster_recovery_manager,
    RecoveryStrategy,
    DisasterType
)

dr_manager = get_disaster_recovery_manager()

# 복구 계획 추가
dr_manager.add_recovery_plan(
    plan_id="main_recovery",
    name="Main Recovery Plan",
    strategy=RecoveryStrategy.HOT_STANDBY,
    rpo_minutes=15,  # Recovery Point Objective
    rto_minutes=30   # Recovery Time Objective
)

# 복구 계획 테스트
test_result = await dr_manager.test_recovery_plan("main_recovery")

# 재해 발생 시 복구 실행
recovery_operation = await dr_manager.trigger_recovery(
    plan_id="main_recovery",
    disaster_type=DisasterType.SERVICE_FAILURE,
    context={"affected_services": ["api", "database"]}
)
```

### Backup Manager

백업 생성 및 복원을 관리합니다.

```python
from rfs.production.recovery import (
    get_backup_manager,
    BackupPolicy,
    BackupTarget,
    BackupType,
    StorageConfig,
    StorageType
)

# 스토리지 설정
storage_config = StorageConfig(
    type=StorageType.LOCAL,
    path="/backups",
    max_size_gb=100
)

backup_manager = get_backup_manager(storage_config)

# 백업 정책 생성
policy = BackupPolicy(
    id="daily_backup",
    name="Daily Backup",
    backup_type=BackupType.INCREMENTAL,
    schedule="daily",
    retention_days=30,
    compression=True,
    encryption=True
)

backup_manager.add_policy(policy)

# 백업 대상 추가
target = BackupTarget(
    id="app_data",
    name="Application Data",
    type="filesystem",
    source_path="/app/data"
)

backup_manager.add_target(target)

# 백업 생성
backup_operation = await backup_manager.create_backup(
    policy_id="daily_backup",
    target_id="app_data"
)

# 백업 복원
restore_operation = await backup_manager.restore_backup(
    backup_id="backup_123",
    target_path="/restore/path",
    verify=True
)
```

### Compliance Validator

규정 준수를 검증합니다.

```python
from rfs.production.recovery import (
    get_compliance_validator,
    ComplianceStandard
)

validator = get_compliance_validator()

# 표준 검증
report = await validator.validate_standard(
    ComplianceStandard.SOC2,
    context={
        "access_control": True,
        "encryption": True,
        "audit_logging": True
    }
)

# 데이터 프라이버시 검증
privacy_result = await validator.check_data_privacy_compliance({
    "classification": True,
    "encryption": {"at_rest": True, "in_transit": True},
    "access_controls": True,
    "retention_policy": True
})

# 보안 컴플라이언스 검증
security_result = await validator.check_security_compliance({
    "mfa": {"enabled": True},
    "password_policy": {"min_length": 12, "complexity_required": True},
    "session_timeout": 3600,
    "audit_logging": {"enabled": True}
})
```

---

## 통합 시스템 API

### Web Integration Manager

외부 웹 서비스와의 통합을 관리합니다.

```python
from rfs.integration import (
    get_web_integration_manager,
    WebhookConfig,
    OAuthConfig
)

manager = get_web_integration_manager()

# Webhook 설정
webhook = WebhookConfig(
    id="order_webhook",
    name="Order Webhook",
    url="https://api.example.com/webhook",
    events=["order.created", "order.updated"],
    secret="webhook_secret"
)

manager.add_webhook(webhook)

# Webhook 트리거
await manager.trigger_webhook(
    webhook_id="order_webhook",
    event="order.created",
    data={"order_id": "123", "amount": 100}
)

# OAuth 설정
oauth = OAuthConfig(
    client_id="client_id",
    client_secret="client_secret",
    authorization_url="https://oauth.example.com/authorize",
    token_url="https://oauth.example.com/token",
    redirect_uri="http://localhost:8000/callback",
    scopes=["read", "write"]
)

manager.add_oauth_config("oauth_provider", oauth)

# OAuth 인증 URL 생성
auth_url = manager.get_oauth_authorization_url("oauth_provider")

# WebSocket 연결
ws_connection = await manager.connect_websocket(
    connection_id="realtime",
    url="wss://api.example.com/ws",
    message_handlers={
        "message": handle_message_function,
        "error": handle_error_function
    }
)
```

### Distributed Cache Manager

분산 캐시를 관리합니다.

```python
from rfs.integration import (
    get_distributed_cache_manager,
    CacheConfig,
    CacheBackend,
    EvictionPolicy
)

# 캐시 설정
config = CacheConfig(
    backend=CacheBackend.REDIS,
    eviction_policy=EvictionPolicy.LRU,
    max_size=10000,
    max_memory_mb=100,
    default_ttl=3600,
    enable_compression=True
)

cache_manager = get_distributed_cache_manager(config)

# 캐시 저장
await cache_manager.set(
    key="user:123",
    value={"id": "123", "name": "John Doe"},
    ttl=1800,
    tags={"users", "active"}
)

# 캐시 조회
result = await cache_manager.get("user:123")
user_data = result.value

# 캐시 파티션 생성
partition = cache_manager.create_partition(
    partition_id="session_cache",
    name="Session Cache",
    config=CacheConfig(
        backend=CacheBackend.MEMORY,
        eviction_policy=EvictionPolicy.TTL,
        max_size=1000,
        default_ttl=900
    )
)

# 태그 기반 무효화
await cache_manager.invalidate_by_tags({"users"})

# 캐시 통계
stats = cache_manager.get_statistics()
print(f"Hit Ratio: {stats.hit_ratio}%")
```

### API Gateway Enhancer

API Gateway 기능을 제공합니다.

```python
from rfs.integration import (
    get_api_gateway,
    Route,
    Backend,
    APIKey,
    RateLimitRule,
    RequestContext,
    AuthenticationMethod,
    LoadBalanceStrategy,
    RateLimitStrategy
)

gateway = get_api_gateway()

# 백엔드 서버 정의
backend1 = Backend(
    id="api_server_1",
    host="api1.example.com",
    port=8080,
    weight=2
)

backend2 = Backend(
    id="api_server_2",
    host="api2.example.com",
    port=8080,
    weight=1
)

# 라우트 설정
route = Route(
    id="user_api",
    path="/api/users",
    methods=["GET", "POST", "PUT", "DELETE"],
    backends=[backend1, backend2],
    authentication=AuthenticationMethod.JWT,
    rate_limit={"rule_id": "api_limit"},
    cache_config={"ttl": 60}
)

gateway.add_route(route)

# API 키 생성
api_key = APIKey(
    key="sk_live_123456",
    name="Production API Key",
    owner="customer_123",
    created_at=datetime.now(),
    rate_limit=RateLimitRule(
        id="key_limit",
        name="API Key Limit",
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        requests_per_second=100,
        burst_size=200,
        scope="api_key"
    )
)

gateway.add_api_key(api_key)

# 속도 제한 규칙
rate_rule = RateLimitRule(
    id="global_limit",
    name="Global Rate Limit",
    strategy=RateLimitStrategy.SLIDING_WINDOW,
    requests_per_second=1000,
    burst_size=2000,
    scope="global"
)

gateway.add_rate_limit_rule(rate_rule)

# 요청 처리
context = RequestContext(
    request_id="req_123",
    client_ip="192.168.1.1",
    method="GET",
    path="/api/users",
    headers={"Authorization": "Bearer token"},
    query_params={"page": 1, "limit": 10}
)

response = await gateway.handle_request(context)

# API 문서 생성
api_docs = await gateway.generate_api_documentation()

# 통계 조회
stats = gateway.get_statistics()
```

## 에러 처리

모든 API는 Result 타입을 반환합니다:

```python
from rfs.core import Success, Failure

result = await some_api_call()

if isinstance(result, Success):
    value = result.value
    # 성공 처리
else:
    error = result.error
    # 에러 처리
```

## 비동기 처리

모든 I/O 작업은 비동기로 처리됩니다:

```python
import asyncio

async def main():
    # 비동기 작업들
    result1 = await api_call_1()
    result2 = await api_call_2()
    
    # 병렬 처리
    results = await asyncio.gather(
        api_call_1(),
        api_call_2(),
        api_call_3()
    )

# 실행
asyncio.run(main())
```