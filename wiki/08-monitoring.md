# 성능 모니터링 (Performance Monitoring)

## 📌 개요

RFS Framework의 모니터링 시스템은 메트릭스 수집, 성능 측정, 알림 기능을 제공합니다. Prometheus와 호환되며 실시간 성능 데이터를 수집하고 분석할 수 있습니다.

## 🎯 핵심 개념

### 메트릭 유형
- **Counter**: 단조 증가하는 누적 메트릭 (요청 수, 에러 수)
- **Gauge**: 증가/감소 가능한 순간값 (메모리 사용량, 연결 수)
- **Histogram**: 분포를 측정하는 메트릭 (응답 시간 분포)
- **Summary**: 분위수를 제공하는 메트릭 (P95, P99 응답 시간)

### 성능 메트릭
- **응답 시간**: API 응답 시간, 함수 실행 시간
- **처리량**: 초당 요청 수, 처리된 작업 수
- **에러율**: 실패한 요청의 비율
- **리소스 사용량**: CPU, 메모리, 디스크, 네트워크

### 저장소 유형
- **메모리 저장소**: 개발/테스트용 휘발성 저장소
- **Prometheus**: 프로덕션용 시계열 데이터베이스
- **파일 저장소**: 로컬 파일 기반 저장

## 📚 API 레퍼런스

### 메트릭 수집기

```python
from rfs.monitoring.metrics import MetricsCollector, MemoryMetricsStorage

# 메트릭 수집기 생성
collector = MetricsCollector(storage=MemoryMetricsStorage())
```

### 메트릭 타입별 API

#### Counter (카운터)

```python
# 카운터 생성
counter = collector.counter(
    name="http_requests_total",
    description="총 HTTP 요청 수",
    labels={"method": "GET", "endpoint": "/api/users"}
)

# 값 증가
counter.increment()        # 1씩 증가
counter.increment(5)       # 5만큼 증가

# 현재 값 조회
current_value = counter.get_value()
```

#### Gauge (게이지)

```python
# 게이지 생성
gauge = collector.gauge(
    name="active_connections",
    description="활성 연결 수",
    labels={"service": "database"}
)

# 값 설정
gauge.set(10)              # 값을 10으로 설정
gauge.increment(2)         # 2만큼 증가
gauge.decrement(1)         # 1만큼 감소
```

#### Histogram (히스토그램)

```python
# 히스토그램 생성
histogram = collector.histogram(
    name="response_time_seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    description="응답 시간 분포"
)

# 값 관찰
histogram.observe(0.25)    # 250ms 응답 시간 기록

# 분위수 계산
p95 = histogram.get_quantile(0.95)  # 95번째 백분위수
```

#### Summary (서머리)

```python
# 서머리 생성
summary = collector.summary(
    name="request_duration_seconds",
    max_age=600,           # 10분간 데이터 보관
    max_samples=10000,     # 최대 10,000개 샘플
    description="요청 처리 시간"
)

# 값 관찰
summary.observe(0.123)

# 통계 조회
stats = summary.get_statistics()
# {'count': 1000, 'sum': 123.45, 'mean': 0.123, 'p95': 0.5, 'p99': 0.8}
```

## 💡 사용 예제

### 기본 메트릭 수집

```python
from rfs.monitoring.metrics import (
    get_metrics_collector,
    record_counter,
    record_gauge,
    record_histogram
)

# 간단한 메트릭 기록
record_counter("user_logins", labels={"method": "oauth"})
record_gauge("memory_usage_bytes", 1024 * 1024 * 512)
record_histogram("api_response_time", 0.25)

# 메트릭 조회
collector = get_metrics_collector()
all_metrics = await collector.get_all_metrics()

for metric in all_metrics:
    print(f"{metric.name}: {metric.value}")
```

### 성능 데코레이터 활용

```python
from rfs.monitoring.performance_decorators import (
    PerformanceMonitored,
    TimingMetric,
    CounterMetric
)

@PerformanceMonitored(
    timing_metric=TimingMetric("user_service_create_time"),
    counter_metric=CounterMetric("user_service_create_total"),
    error_counter=CounterMetric("user_service_create_errors"),
    labels={"service": "user", "version": "v1"}
)
async def create_user(user_data: dict) -> Result[dict, str]:
    """사용자 생성 (성능 모니터링 포함)"""
    try:
        # 사용자 생성 로직
        user = await save_user_to_db(user_data)
        return Success(user)
    except Exception as e:
        return Failure(str(e))

# 실행 시 자동으로 메트릭 수집:
# - user_service_create_time: 실행 시간 히스토그램
# - user_service_create_total: 총 호출 수 카운터
# - user_service_create_errors: 에러 발생 수 카운터
```

### 웹 애플리케이션 모니터링

```python
from rfs.monitoring.metrics import get_metrics_collector
from rfs.core.result import Result, Success
import time

class WebService:
    def __init__(self):
        self.collector = get_metrics_collector()
        
        # 메트릭 정의
        self.request_counter = self.collector.counter(
            "http_requests_total",
            description="총 HTTP 요청 수",
            labels={"service": "web"}
        )
        
        self.response_time = self.collector.histogram(
            "http_request_duration_seconds",
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            description="HTTP 응답 시간"
        )
        
        self.active_requests = self.collector.gauge(
            "http_requests_active",
            description="활성 HTTP 요청 수"
        )
    
    async def handle_request(self, request) -> Result[dict, str]:
        """HTTP 요청 처리 (메트릭 수집 포함)"""
        start_time = time.time()
        
        # 활성 요청 수 증가
        self.active_requests.increment()
        
        try:
            # 요청 카운터 증가
            self.request_counter.increment()
            
            # 실제 요청 처리
            response = await self._process_request(request)
            
            # 성공 메트릭 기록
            duration = time.time() - start_time
            self.response_time.observe(duration)
            
            return Success(response)
            
        except Exception as e:
            # 에러 메트릭 기록
            error_counter = self.collector.counter(
                "http_errors_total",
                labels={"error_type": type(e).__name__}
            )
            error_counter.increment()
            
            return Failure(str(e))
            
        finally:
            # 활성 요청 수 감소
            self.active_requests.decrement()
```

### 데이터베이스 연결 모니터링

```python
from rfs.monitoring.metrics import get_metrics_collector
import asyncio
import time

class DatabasePool:
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.collector = get_metrics_collector()
        
        # 연결 메트릭
        self.connection_pool_size = self.collector.gauge(
            "db_connection_pool_size",
            description="데이터베이스 연결 풀 크기"
        )
        
        self.active_connections = self.collector.gauge(
            "db_connections_active",
            description="활성 데이터베이스 연결 수"
        )
        
        self.query_duration = self.collector.histogram(
            "db_query_duration_seconds",
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            description="데이터베이스 쿼리 실행 시간"
        )
        
        self.connection_errors = self.collector.counter(
            "db_connection_errors_total",
            description="데이터베이스 연결 에러 수"
        )
        
        # 초기 메트릭 설정
        self.connection_pool_size.set(max_connections)
    
    async def execute_query(self, query: str) -> Result[list, str]:
        """쿼리 실행 (성능 모니터링 포함)"""
        start_time = time.time()
        
        # 활성 연결 수 증가
        self.active_connections.increment()
        
        try:
            # 쿼리 실행 시뮬레이션
            await asyncio.sleep(0.05)  # 50ms 시뮬레이션
            result = [{"id": 1, "name": "test"}]
            
            # 성능 메트릭 기록
            duration = time.time() - start_time
            self.query_duration.observe(duration)
            
            return Success(result)
            
        except Exception as e:
            self.connection_errors.increment()
            return Failure(str(e))
            
        finally:
            # 활성 연결 수 감소
            self.active_connections.decrement()
```

### 비즈니스 메트릭 모니터링

```python
from rfs.monitoring.metrics import get_metrics_collector

class OrderService:
    def __init__(self):
        self.collector = get_metrics_collector()
        
        # 비즈니스 메트릭
        self.orders_total = self.collector.counter(
            "orders_created_total",
            description="생성된 주문 수"
        )
        
        self.order_value = self.collector.histogram(
            "order_value_distribution",
            buckets=[10, 50, 100, 500, 1000, 5000, 10000],
            description="주문 금액 분포"
        )
        
        self.payment_success_rate = self.collector.gauge(
            "payment_success_rate",
            description="결제 성공률"
        )
        
        self.inventory_levels = self.collector.gauge(
            "inventory_remaining",
            description="재고 수준"
        )
    
    async def create_order(self, order_data: dict) -> Result[dict, str]:
        """주문 생성 (비즈니스 메트릭 수집)"""
        try:
            # 주문 생성
            order = await self._create_order_in_db(order_data)
            
            # 비즈니스 메트릭 업데이트
            self.orders_total.increment()
            self.order_value.observe(order["amount"])
            
            # 재고 수준 업데이트
            remaining_inventory = await self._get_inventory_count(order["product_id"])
            self.inventory_levels.set(
                remaining_inventory,
                labels={"product_id": order["product_id"]}
            )
            
            return Success(order)
            
        except Exception as e:
            return Failure(str(e))
```

### Prometheus 통합

```python
from rfs.monitoring.metrics import PrometheusStorage, MetricsCollector

# Prometheus Push Gateway 설정
prometheus_storage = PrometheusStorage(
    push_gateway_url="http://pushgateway:9091",
    job_name="rfs_application"
)

# 메트릭 수집기 생성
collector = MetricsCollector(storage=prometheus_storage)

# 메트릭 정의 및 사용
request_counter = collector.counter(
    "app_requests_total",
    labels={"service": "api", "version": "v1"}
)

# 주기적으로 메트릭을 Prometheus로 전송
import asyncio

async def push_metrics_periodically():
    """메트릭을 주기적으로 Prometheus로 전송"""
    while True:
        try:
            result = await collector.collect_and_store()
            if result.is_success():
                print(f"메트릭 {result.unwrap()}개 전송 완료")
            else:
                print(f"메트릭 전송 실패: {result.unwrap_err()}")
        except Exception as e:
            print(f"메트릭 전송 중 에러: {e}")
        
        await asyncio.sleep(30)  # 30초마다 전송
```

### 실시간 대시보드 데이터

```python
from rfs.monitoring.metrics import get_metrics_collector
import json

class MetricsDashboard:
    def __init__(self):
        self.collector = get_metrics_collector()
    
    async def get_dashboard_data(self) -> dict:
        """대시보드용 실시간 데이터 조회"""
        all_metrics = await self.collector.get_all_metrics()
        
        dashboard_data = {
            "system": {
                "uptime": self._get_uptime_metric(all_metrics),
                "memory_usage": self._get_memory_metric(all_metrics),
                "cpu_usage": self._get_cpu_metric(all_metrics)
            },
            "application": {
                "requests_per_second": self._calculate_rps(all_metrics),
                "error_rate": self._calculate_error_rate(all_metrics),
                "response_time_p95": self._get_response_time_p95(all_metrics)
            },
            "business": {
                "orders_today": self._get_orders_today(all_metrics),
                "revenue_today": self._get_revenue_today(all_metrics),
                "active_users": self._get_active_users(all_metrics)
            }
        }
        
        return dashboard_data
    
    def _get_uptime_metric(self, metrics):
        """시스템 가동 시간"""
        for metric in metrics:
            if metric.name == "system_uptime_seconds":
                return metric.value
        return 0
    
    def _calculate_rps(self, metrics):
        """초당 요청 수 계산"""
        # 구현 로직...
        return 0
    
    async def export_metrics_json(self) -> str:
        """메트릭을 JSON으로 내보내기"""
        all_metrics = await self.collector.get_all_metrics()
        
        metrics_data = []
        for metric in all_metrics:
            metrics_data.append({
                "name": metric.name,
                "type": metric.metric_type.value,
                "value": metric.value,
                "labels": metric.labels,
                "timestamp": metric.timestamp,
                "description": metric.description
            })
        
        return json.dumps(metrics_data, indent=2)
```

## 🎨 베스트 프랙티스

### 1. 메트릭 명명 규칙

```python
# ✅ 좋은 예 - 명확한 네임스페이스와 의미
collector.counter("http_requests_total", labels={"method": "GET"})
collector.histogram("database_query_duration_seconds")
collector.gauge("memory_usage_bytes")

# ❌ 나쁜 예 - 모호한 이름
collector.counter("requests")
collector.histogram("time")
collector.gauge("mem")
```

### 2. 라벨 사용

```python
# ✅ 좋은 예 - 적절한 라벨 사용
collector.counter(
    "api_requests_total",
    labels={
        "method": "POST",
        "endpoint": "/api/users",
        "status_code": "200",
        "service": "user_service"
    }
)

# ❌ 나쁜 예 - 과도한 라벨 (카디널리티 폭발)
collector.counter(
    "requests",
    labels={
        "user_id": "user123",  # 높은 카디널리티
        "timestamp": "2024-01-15T10:30:00Z",  # 매우 높은 카디널리티
        "request_id": "req-456"  # 매우 높은 카디널리티
    }
)
```

### 3. 히스토그램 버킷 설정

```python
# ✅ 좋은 예 - 적절한 버킷 범위
response_time_histogram = collector.histogram(
    "api_response_time_seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    description="API 응답 시간 분포"
)

# 데이터베이스 쿼리용 (더 작은 범위)
db_query_histogram = collector.histogram(
    "db_query_duration_seconds",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    description="데이터베이스 쿼리 시간"
)
```

### 4. 성능 최적화

```python
# ✅ 좋은 예 - 메트릭 인스턴스 재사용
class ServiceMetrics:
    def __init__(self):
        self.collector = get_metrics_collector()
        self.request_counter = self.collector.counter("requests_total")
        self.response_histogram = self.collector.histogram("response_time")
    
    def record_request(self):
        self.request_counter.increment()  # 빠름 - 인스턴스 재사용

# ❌ 나쁜 예 - 매번 새로운 메트릭 생성
def record_request():
    collector = get_metrics_collector()
    counter = collector.counter("requests_total")  # 느림 - 매번 생성
    counter.increment()
```

## ⚠️ 주의사항

### 1. 메트릭 카디널리티 관리
- 라벨 값의 수가 많을수록 메모리 사용량 증가
- 사용자 ID, 타임스탬프 등 높은 카디널리티 데이터 라벨 사용 금지

### 2. 성능 영향 최소화
- 메트릭 수집이 애플리케이션 성능에 미치는 영향 모니터링
- 불필요한 메트릭 수집 지양

### 3. 메트릭 저장소 용량
- 히스토그램과 서머리는 많은 저장 공간 사용
- 적절한 보관 기간 설정 및 정리 정책 수립

### 4. 알림 임계값 설정
- 적절한 임계값 설정으로 불필요한 알림 방지
- 비즈니스 요구사항에 맞는 SLA 기반 알림

## 🔗 관련 문서
- [로깅](./07-logging.md) - 구조화된 로깅과 메트릭 연동
- [배포](./05-deployment.md) - 프로덕션 환경 모니터링 설정
- [보안](./11-security.md) - 보안 메트릭 및 이상 탐지
- [서킷 브레이커](./12-circuit-breaker.md) - 장애 격리 메트릭