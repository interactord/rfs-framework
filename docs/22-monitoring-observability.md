# 모니터링 및 관측가능성 가이드

RFS Framework의 Result 패턴을 위한 완전한 모니터링 및 관측가능성(Observability) 시스템입니다.

## 개요

### 핵심 구성 요소

- **Result 로깅 시스템**: 구조화된 로깅과 correlation ID 추적
- **실시간 메트릭 수집**: 성능 데이터와 비즈니스 메트릭
- **알림 관리**: 임계값 기반 자동 알림
- **대시보드 API**: 운영진을 위한 모니터링 인터페이스

## Result 로깅 시스템

### 기본 로깅 설정

```python
from rfs.monitoring.result_logging import (
    configure_result_logging, 
    log_result_operation, 
    CorrelationContext,
    get_correlation_id
)

# 로깅 시스템 초기 설정
configure_result_logging(
    level=LogLevel.INFO,
    include_stack_trace=True,
    include_performance_data=True,
    correlation_header="X-Correlation-ID"
)
```

### 자동 작업 로깅

```python
@log_result_operation("user_processing")
async def process_user_data(user_id: str) -> Result[dict, str]:
    """작업 전체가 자동으로 로깅됩니다"""
    return await (
        MonoResult.from_async_result(lambda: fetch_user(user_id))
        .bind_async_result(lambda user: validate_user(user))
        .bind_async_result(lambda user: enrich_user_data(user))
        .to_result()
    )

# 로그 출력 예시:
# {
#   "timestamp": "2025-09-03T15:30:00Z",
#   "correlation_id": "req_12345",
#   "operation": "user_processing",
#   "level": "INFO",
#   "message": "Operation started",
#   "context": {"user_id": "123"}
# }
```

### MonoResult 단계별 로깅

```python
from rfs.monitoring.result_logging import create_logging_mono

async def complex_operation(data: dict) -> Result[dict, str]:
    return await (
        create_logging_mono(lambda: initial_processing(data))
        .log_step("initial_processing", "데이터 초기 처리 완료")
        .bind_async_result(lambda result: validation_step(result))
        .log_step("validation", "검증 단계 완료") 
        .bind_async_result(lambda result: transformation_step(result))
        .log_step("transformation", "변환 단계 완료")
        .log_performance("total_processing_time")
        .log_error("processing_failed")
        .to_result()
    )

# 각 단계가 자동으로 로깅됨:
# - 단계 시작/완료 시간
# - 중간 데이터 크기와 형태
# - 에러 발생 시 상세 정보
# - 성능 메트릭 (처리 시간, 메모리 사용량)
```

### Correlation ID 추적

```python
from rfs.monitoring.result_logging import with_correlation_id, CorrelationContext

# HTTP 요청에서 correlation ID 설정
async def handle_request(request_id: str):
    async with CorrelationContext(request_id):
        # 이 블록 내의 모든 로그는 동일한 correlation_id를 가짐
        result1 = await process_step_1()
        result2 = await process_step_2() 
        result3 = await process_step_3()
        
        # 분산 시스템에서 요청을 추적할 수 있음
        current_id = get_correlation_id()
        await external_service.call(headers={"X-Correlation-ID": current_id})
```

## 실시간 메트릭 수집

### 기본 메트릭 수집

```python
from rfs.monitoring.metrics import (
    collect_metric, 
    collect_result_metric,
    collect_flux_result_metric,
    MetricType,
    start_monitoring
)

# 모니터링 시작
start_monitoring()

# 수동 메트릭 수집
collect_metric("api_requests_total", 1, MetricType.COUNTER, 
              labels={"endpoint": "/users", "method": "GET"})

collect_metric("response_time_ms", 250.5, MetricType.HISTOGRAM,
              labels={"endpoint": "/users"})

collect_metric("active_connections", 45, MetricType.GAUGE)
```

### Result 패턴 전용 메트릭

```python
async def monitored_operation():
    start_time = time.time()
    
    result = await (
        MonoResult.from_async_result(lambda: some_operation())
        .timeout(5.0)
        .to_result()
    )
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Result 전용 메트릭 자동 수집
    collect_result_metric("user_processing", result, duration_ms)
    
    return result

# 자동으로 다음 메트릭들이 수집됨:
# - result_success_total (성공 카운터)
# - result_failure_total (실패 카운터) 
# - result_duration_ms (처리 시간 히스토그램)
# - result_error_by_type_total (에러 타입별 카운터)
```

### FluxResult 배치 메트릭

```python
async def batch_processing():
    start_time = time.time()
    
    flux_result = await (
        FluxResult.from_iterable_async(batch_data, process_item)
        .batch_collect(batch_size=10, max_concurrent=3)
    )
    
    duration_ms = (time.time() - start_time) * 1000
    
    # 배치 처리 전용 메트릭
    collect_flux_result_metric("batch_processing", flux_result, duration_ms)
    
    # 수집되는 메트릭들:
    # - flux_result_total_items
    # - flux_result_success_items  
    # - flux_result_failure_items
    # - flux_result_success_rate
    # - flux_result_duration_ms
```

## 알림 시스템

### 기본 알림 규칙 설정

```python
from rfs.monitoring.metrics import (
    create_alert_rule,
    AlertCondition,
    setup_default_alerts,
    start_monitoring
)

# 기본 알림 규칙 설정
setup_default_alerts()

# 커스텀 알림 규칙 추가
create_alert_rule(
    name="high_error_rate",
    metric_name="result_failure_total", 
    condition=AlertCondition.GREATER_THAN,
    threshold=50.0,
    callback=lambda alert: send_slack_notification(alert)
)

create_alert_rule(
    name="slow_api_response",
    metric_name="result_duration_ms",
    condition=AlertCondition.GREATER_THAN, 
    threshold=5000.0,  # 5초
    callback=lambda alert: escalate_to_oncall(alert)
)
```

### 커스텀 알림 콜백

```python
async def custom_alert_handler(alert_data: dict):
    """커스텀 알림 처리기"""
    alert_info = {
        "metric": alert_data["metric_name"],
        "current_value": alert_data["current_value"],
        "threshold": alert_data["threshold"],
        "timestamp": alert_data["timestamp"]
    }
    
    # 다중 채널로 알림 발송
    await send_email_alert(alert_info)
    await send_slack_alert(alert_info)
    await create_incident_ticket(alert_info)

create_alert_rule(
    name="critical_system_failure",
    metric_name="result_failure_total",
    condition=AlertCondition.GREATER_THAN,
    threshold=100.0,
    callback=custom_alert_handler
)
```

## 대시보드 및 모니터링 API

### 메트릭 조회 API

```python
from rfs.monitoring.metrics import get_metrics_summary, get_dashboard_data

# 메트릭 요약 정보 조회
metrics = get_metrics_summary(time_range_minutes=60)

print(f"지난 1시간 메트릭:")
print(f"- 총 성공 작업: {metrics['counters']['result_success_total']}")
print(f"- 총 실패 작업: {metrics['counters']['result_failure_total']}")

# 응답 시간 분포 확인
response_times = metrics['histograms']['result_duration_ms']
print(f"- 평균 응답시간: {response_times['mean']:.2f}ms")
print(f"- 95백분위수: {response_times['p95']:.2f}ms")
print(f"- 최대 응답시간: {response_times['max']:.2f}ms")
```

### 종합 대시보드 데이터

```python
dashboard = get_dashboard_data()

# 대시보드 구조:
# {
#   "metrics_summary": {...},        # 메트릭 요약
#   "active_alerts": [...],          # 활성 알림 목록
#   "alert_rules": [...],            # 설정된 알림 규칙
#   "system_status": {               # 시스템 상태
#     "monitoring_active": True,
#     "total_metrics": 1250,
#     "timestamp": "2025-09-03T15:30:00Z"
#   }
# }
```

### FastAPI 모니터링 엔드포인트

```python
from fastapi import FastAPI
from rfs.monitoring.metrics import get_dashboard_data, get_metrics_summary

app = FastAPI()

@app.get("/monitoring/health")
async def health_check():
    """시스템 헬스 체크"""
    dashboard = get_dashboard_data()
    
    is_healthy = (
        dashboard["system_status"]["monitoring_active"] and
        len(dashboard["active_alerts"]) == 0
    )
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "active_alerts": len(dashboard["active_alerts"]),
        "timestamp": dashboard["system_status"]["timestamp"]
    }

@app.get("/monitoring/metrics")
async def get_metrics(hours: int = 1):
    """메트릭 데이터 조회"""
    return get_metrics_summary(time_range_minutes=hours * 60)

@app.get("/monitoring/dashboard")
async def monitoring_dashboard():
    """전체 대시보드 데이터"""
    return get_dashboard_data()
```

## 실용적인 모니터링 패턴

### 서비스별 메트릭 분리

```python
class UserService:
    def __init__(self):
        self.service_name = "user_service"
    
    @log_result_operation("user_service.get_user")
    async def get_user(self, user_id: str) -> Result[User, str]:
        start_time = time.time()
        
        result = await self._fetch_user_from_db(user_id)
        
        # 서비스별 메트릭 수집
        duration = (time.time() - start_time) * 1000
        collect_result_metric(
            f"{self.service_name}.get_user", 
            result, 
            duration,
            labels={"service": self.service_name}
        )
        
        return result
```

### 비즈니스 메트릭 추적

```python
@log_result_operation("order_processing")
async def process_order(order: Order) -> Result[dict, str]:
    result = await (
        MonoResult.from_async_result(lambda: validate_order(order))
        .bind_async_result(lambda o: charge_payment(o))
        .bind_async_result(lambda o: update_inventory(o))
        .bind_async_result(lambda o: send_confirmation(o))
        .to_result()
    )
    
    if result.is_success():
        # 비즈니스 메트릭 수집
        collect_metric("orders_processed_total", 1, MetricType.COUNTER)
        collect_metric("revenue_total", order.amount, MetricType.COUNTER) 
        collect_metric("order_value", order.amount, MetricType.HISTOGRAM)
        
        # 카테고리별 분석
        collect_metric(
            "orders_by_category", 1, MetricType.COUNTER,
            labels={"category": order.category}
        )
    
    return result
```

### 성능 프로파일링

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def performance_tracker(operation_name: str):
    """성능 추적 컨텍스트 매니저"""
    start_time = time.time()
    start_memory = get_memory_usage()
    
    try:
        yield
    finally:
        end_time = time.time()
        end_memory = get_memory_usage()
        
        duration_ms = (end_time - start_time) * 1000
        memory_delta = end_memory - start_memory
        
        collect_metric(f"{operation_name}.duration_ms", duration_ms, MetricType.HISTOGRAM)
        collect_metric(f"{operation_name}.memory_usage_mb", memory_delta, MetricType.HISTOGRAM)

async def heavy_computation():
    async with performance_tracker("heavy_computation"):
        # 무거운 연산 작업
        result = await complex_calculation()
        return result
```

## 프로덕션 모니터링 모범 사례

### 1. 계층화된 모니터링

```python
# 인프라 레벨 메트릭
collect_metric("system.cpu_usage", cpu_percent, MetricType.GAUGE)
collect_metric("system.memory_usage", memory_percent, MetricType.GAUGE)

# 애플리케이션 레벨 메트릭
collect_metric("app.requests_per_second", rps, MetricType.GAUGE)
collect_metric("app.error_rate", error_rate, MetricType.GAUGE)

# 비즈니스 레벨 메트릭
collect_metric("business.active_users", active_users, MetricType.GAUGE)
collect_metric("business.transactions_total", transactions, MetricType.COUNTER)
```

### 2. SLA 모니터링

```python
# SLA 메트릭 정의
SLA_TARGETS = {
    "availability": 99.9,      # 99.9% 가용성
    "response_time_p95": 1000, # 95백분위수 1초 이하
    "error_rate": 0.1          # 에러율 0.1% 이하
}

@log_result_operation("sla_check")
async def check_sla_compliance():
    metrics = get_metrics_summary(time_range_minutes=60)
    
    # 가용성 체크
    total_requests = metrics['counters']['result_success_total'] + metrics['counters']['result_failure_total']
    error_rate = (metrics['counters']['result_failure_total'] / total_requests) * 100 if total_requests > 0 else 0
    
    sla_violations = []
    
    if error_rate > SLA_TARGETS["error_rate"]:
        sla_violations.append(f"Error rate {error_rate:.2f}% exceeds target {SLA_TARGETS['error_rate']}%")
    
    # SLA 위반 시 알림
    if sla_violations:
        await send_sla_violation_alert(sla_violations)
    
    return Success({"sla_compliant": len(sla_violations) == 0})
```

### 3. 장애 상황 대응

```python
@log_result_operation("circuit_breaker_check")
async def circuit_breaker_monitoring():
    """서킷 브레이커 상태 모니터링"""
    recent_metrics = get_metrics_summary(time_range_minutes=5)
    
    failure_rate = calculate_failure_rate(recent_metrics)
    
    if failure_rate > 50:  # 50% 이상 실패
        # 서킷 브레이커 활성화
        await activate_circuit_breaker("user_service")
        
        create_alert_rule(
            name="circuit_breaker_activated",
            metric_name="circuit_breaker_status",
            condition=AlertCondition.EQUAL,
            threshold=1.0,
            callback=lambda alert: notify_incident_team(alert)
        )
```

## 디버깅 및 트러블슈팅

### 로그 분석

```python
# Correlation ID로 요청 추적
correlation_id = "req_12345"
logs = query_logs_by_correlation_id(correlation_id)

for log_entry in logs:
    print(f"[{log_entry.timestamp}] {log_entry.operation}: {log_entry.message}")
    if log_entry.error:
        print(f"  Error: {log_entry.error.message}")
        print(f"  Stack trace: {log_entry.error.stack_trace}")
```

### 성능 분석

```python
# 느린 작업 식별
slow_operations = get_metrics_summary()['histograms']
for operation, stats in slow_operations.items():
    if stats['p95'] > 5000:  # 5초 초과
        print(f"Slow operation detected: {operation}")
        print(f"  P95: {stats['p95']:.2f}ms")
        print(f"  Max: {stats['max']:.2f}ms")
        print(f"  Count: {stats['count']}")
```

## 추가 자료

- [Result 패턴 가이드](01-core-patterns.md)
- [FastAPI 통합](21-fastapi-integration.md)
- [테스팅 가이드](23-testing-guide.md)