# 서킷 브레이커 패턴 (Circuit Breaker Pattern)

## 📌 개요

RFS Framework의 서킷 브레이커는 마이크로서비스 환경에서 장애 전파를 차단하고 시스템 안정성을 보장합니다. 자동 장애 감지, 점진적 복구, 실시간 모니터링 기능을 제공합니다.

## 🎯 핵심 개념

### 서킷 브레이커 상태
- **CLOSED (닫힘)**: 정상 상태, 모든 요청 통과
- **OPEN (열림)**: 장애 상태, 요청 차단 및 즉시 실패
- **HALF_OPEN (반개방)**: 복구 테스트 상태, 제한된 요청만 통과

### 상태 전환 조건
- **CLOSED → OPEN**: 실패율 임계값 초과 또는 연속 실패 임계값 달성
- **OPEN → HALF_OPEN**: 지정된 타임아웃 시간 경과
- **HALF_OPEN → CLOSED**: 테스트 요청 모두 성공
- **HALF_OPEN → OPEN**: 테스트 요청 중 하나라도 실패

### 핵심 메트릭
- **실패율**: 전체 요청 대비 실패한 요청의 비율
- **응답 시간**: 요청 처리에 걸린 시간
- **처리량**: 단위 시간당 처리된 요청 수
- **가용성**: 서비스 가용 시간의 비율

## 📚 API 레퍼런스

### CircuitBreakerConfig 설정

```python
from rfs.service_discovery.circuit_breaker import (
    CircuitBreakerConfig, 
    CircuitBreaker,
    circuit_breaker
)

config = CircuitBreakerConfig(
    failure_threshold=5,         # 실패 임계값 (횟수)
    failure_rate_threshold=0.5,  # 실패율 임계값 (50%)
    timeout=10.0,               # 요청 타임아웃 (초)
    reset_timeout=60.0,         # OPEN 상태 유지 시간 (초)
    half_open_max_requests=3,   # HALF_OPEN 테스트 요청 수
    window_size=10,             # 슬라이딩 윈도우 크기
    window_duration=60.0        # 시간 윈도우 (초)
)
```

### 서킷 브레이커 상태

| 상태 | 설명 | 동작 |
|------|------|------|
| `CLOSED` | 정상 운영 | 모든 요청 통과, 실패 카운트 |
| `OPEN` | 장애 차단 | 요청 즉시 거부, 타임아웃 대기 |
| `HALF_OPEN` | 복구 테스트 | 제한된 테스트 요청만 허용 |

## 💡 사용 예제

### 데코레이터 방식 사용

```python
from rfs.service_discovery.circuit_breaker import circuit_breaker, CircuitBreakerConfig
from rfs.core.result import Result, Success, Failure
import asyncio
import random

# 서킷 브레이커 설정
config = CircuitBreakerConfig(
    failure_threshold=3,         # 3번 실패 시 OPEN
    failure_rate_threshold=0.6,  # 실패율 60% 초과 시 OPEN
    timeout=5.0,                # 5초 타임아웃
    reset_timeout=30.0,         # 30초 후 HALF_OPEN 시도
    half_open_max_requests=2    # HALF_OPEN에서 2번 테스트
)

@circuit_breaker(name="external_api", config=config)
async def call_external_api(url: str) -> Result[dict, str]:
    """외부 API 호출 (서킷 브레이커 적용)"""
    try:
        # 외부 API 호출 시뮬레이션
        await asyncio.sleep(0.1)
        
        # 30% 확률로 실패 시뮬레이션
        if random.random() < 0.3:
            raise Exception("API 호출 실패")
        
        return Success({"status": "success", "data": "response"})
        
    except Exception as e:
        return Failure(f"API 호출 실패: {str(e)}")

# 사용
async def main():
    # 반복 호출로 서킷 브레이커 동작 테스트
    for i in range(10):
        try:
            result = await call_external_api("https://api.example.com/data")
            
            if result.is_success():
                print(f"호출 {i+1}: 성공 - {result.unwrap()}")
            else:
                print(f"호출 {i+1}: 실패 - {result.unwrap_err()}")
                
        except Exception as e:
            print(f"호출 {i+1}: 서킷 브레이커 차단 - {e}")
        
        await asyncio.sleep(1)
    
    # 서킷 브레이커 상태 확인
    breaker = call_external_api.circuit_breaker()
    metrics = breaker.get_metrics()
    
    print(f"\n서킷 브레이커 상태: {breaker.get_state().value}")
    print(f"총 요청: {metrics.total_requests}")
    print(f"성공: {metrics.successful_requests}")
    print(f"실패: {metrics.failed_requests}")
    print(f"성공률: {metrics.success_rate:.2%}")

# 실행
asyncio.run(main())
```

### 수동 서킷 브레이커 관리

```python
from rfs.service_discovery.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

class DatabaseService:
    """데이터베이스 서비스 (서킷 브레이커 적용)"""
    
    def __init__(self):
        # 각 데이터베이스별 서킷 브레이커
        self.primary_db_breaker = CircuitBreaker(
            name="primary_db",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                failure_rate_threshold=0.5,
                timeout=3.0,
                reset_timeout=60.0
            )
        )
        
        self.replica_db_breaker = CircuitBreaker(
            name="replica_db", 
            config=CircuitBreakerConfig(
                failure_threshold=3,
                failure_rate_threshold=0.7,
                timeout=2.0,
                reset_timeout=30.0
            )
        )
    
    async def get_user(self, user_id: str) -> Result[dict, str]:
        """사용자 조회 (Primary DB → Replica DB 순서로 시도)"""
        
        # Primary DB 시도
        if not self.primary_db_breaker.is_open():
            try:
                result = await self.primary_db_breaker.call_async(
                    self._query_primary_db, 
                    f"SELECT * FROM users WHERE id = '{user_id}'"
                )
                return Success(result)
                
            except Exception as e:
                print(f"Primary DB 실패: {e}")
        
        # Replica DB 폴백
        if not self.replica_db_breaker.is_open():
            try:
                result = await self.replica_db_breaker.call_async(
                    self._query_replica_db,
                    f"SELECT * FROM users WHERE id = '{user_id}'"
                )
                return Success(result)
                
            except Exception as e:
                print(f"Replica DB도 실패: {e}")
        
        return Failure("모든 데이터베이스가 사용 불가능합니다")
    
    async def _query_primary_db(self, query: str) -> dict:
        """Primary DB 쿼리"""
        # 실제로는 데이터베이스 연결 및 쿼리
        await asyncio.sleep(0.05)
        
        # 20% 확률로 실패
        if random.random() < 0.2:
            raise Exception("Primary DB 연결 실패")
        
        return {"id": "user123", "name": "John", "source": "primary"}
    
    async def _query_replica_db(self, query: str) -> dict:
        """Replica DB 쿼리"""
        await asyncio.sleep(0.1)
        
        # 10% 확률로 실패
        if random.random() < 0.1:
            raise Exception("Replica DB 연결 실패")
        
        return {"id": "user123", "name": "John", "source": "replica"}
    
    def get_status(self) -> dict:
        """서비스 상태 조회"""
        return {
            "primary_db": {
                "state": self.primary_db_breaker.get_state().value,
                "metrics": self.primary_db_breaker.get_metrics().__dict__
            },
            "replica_db": {
                "state": self.replica_db_breaker.get_state().value,
                "metrics": self.replica_db_breaker.get_metrics().__dict__
            }
        }

# 사용
async def test_database_service():
    db_service = DatabaseService()
    
    # 반복 호출로 폴백 동작 테스트
    for i in range(15):
        result = await db_service.get_user("user123")
        
        if result.is_success():
            data = result.unwrap()
            print(f"조회 {i+1}: 성공 - {data['name']} (출처: {data['source']})")
        else:
            print(f"조회 {i+1}: 실패 - {result.unwrap_err()}")
        
        await asyncio.sleep(0.5)
    
    # 최종 상태 출력
    status = db_service.get_status()
    print(f"\n최종 상태:")
    print(f"Primary DB: {status['primary_db']['state']}")
    print(f"Replica DB: {status['replica_db']['state']}")

asyncio.run(test_database_service())
```

### 마이크로서비스 간 통신

```python
import httpx
from typing import Optional

class MicroserviceClient:
    """마이크로서비스 클라이언트 (서킷 브레이커 적용)"""
    
    def __init__(self, service_name: str, base_url: str):
        self.service_name = service_name
        self.base_url = base_url
        
        # 서비스별 서킷 브레이커 설정
        self.circuit_breaker = CircuitBreaker(
            name=f"service_{service_name}",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                failure_rate_threshold=0.5,
                timeout=10.0,
                reset_timeout=60.0,
                exclude_exceptions=[httpx.HTTPStatusError]  # 4xx 에러는 제외
            )
        )
    
    async def get(self, endpoint: str, **kwargs) -> Result[dict, str]:
        """GET 요청"""
        return await self._request("GET", endpoint, **kwargs)
    
    async def post(self, endpoint: str, json_data: dict, **kwargs) -> Result[dict, str]:
        """POST 요청"""
        return await self._request("POST", endpoint, json=json_data, **kwargs)
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Result[dict, str]:
        """HTTP 요청 (서킷 브레이커 적용)"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.circuit_breaker.call_async(
                self._http_call,
                method,
                url,
                **kwargs
            )
            
            return Success(response)
            
        except Exception as e:
            return Failure(f"{self.service_name} 서비스 호출 실패: {str(e)}")
    
    async def _http_call(self, method: str, url: str, **kwargs) -> dict:
        """실제 HTTP 호출"""
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)
            
            # 5xx 에러는 서킷 브레이커 트리거
            if response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"Server error: {response.status_code}",
                    request=response.request,
                    response=response
                )
            
            # 4xx 에러는 클라이언트 오류로 처리
            response.raise_for_status()
            
            return response.json()
    
    def get_health(self) -> dict:
        """서킷 브레이커 상태 조회"""
        metrics = self.circuit_breaker.get_metrics()
        
        return {
            "service": self.service_name,
            "circuit_breaker": {
                "state": self.circuit_breaker.get_state().value,
                "total_requests": metrics.total_requests,
                "success_rate": metrics.success_rate,
                "average_response_time": metrics.average_response_time
            }
        }

# 서비스 클라이언트들
class ServiceRegistry:
    """서비스 레지스트리"""
    
    def __init__(self):
        self.clients = {
            "user_service": MicroserviceClient("user", "http://user-service:8001"),
            "order_service": MicroserviceClient("order", "http://order-service:8002"),
            "payment_service": MicroserviceClient("payment", "http://payment-service:8003"),
            "notification_service": MicroserviceClient("notification", "http://notification-service:8004")
        }
    
    async def create_order(self, order_data: dict) -> Result[dict, str]:
        """주문 생성 (여러 서비스 조합)"""
        try:
            # 1. 사용자 검증
            user_result = await self.clients["user_service"].get(
                f"/users/{order_data['user_id']}"
            )
            if user_result.is_failure():
                return user_result
            
            # 2. 주문 생성
            order_result = await self.clients["order_service"].post(
                "/orders",
                json_data=order_data
            )
            if order_result.is_failure():
                return order_result
            
            order = order_result.unwrap()
            
            # 3. 결제 처리
            payment_result = await self.clients["payment_service"].post(
                "/payments",
                json_data={
                    "order_id": order["id"],
                    "amount": order["total"],
                    "payment_method": order_data["payment_method"]
                }
            )
            if payment_result.is_failure():
                # 주문 취소 (보상 트랜잭션)
                await self._cancel_order(order["id"])
                return payment_result
            
            # 4. 알림 발송 (실패해도 주문은 유지)
            notification_result = await self.clients["notification_service"].post(
                "/notifications",
                json_data={
                    "user_id": order_data["user_id"],
                    "type": "order_confirmed",
                    "order_id": order["id"]
                }
            )
            if notification_result.is_failure():
                print(f"알림 발송 실패: {notification_result.unwrap_err()}")
            
            return Success(order)
            
        except Exception as e:
            return Failure(f"주문 생성 중 오류: {str(e)}")
    
    async def _cancel_order(self, order_id: str) -> None:
        """주문 취소 (보상 트랜잭션)"""
        try:
            await self.clients["order_service"].post(
                f"/orders/{order_id}/cancel",
                json_data={}
            )
        except Exception as e:
            print(f"주문 취소 실패: {e}")
    
    def get_system_health(self) -> dict:
        """전체 시스템 상태"""
        health = {
            "overall_status": "healthy",
            "services": {}
        }
        
        unhealthy_count = 0
        
        for name, client in self.clients.items():
            service_health = client.get_health()
            health["services"][name] = service_health
            
            # 서킷 브레이커가 열려있으면 비정상
            if service_health["circuit_breaker"]["state"] == "open":
                unhealthy_count += 1
        
        # 전체 상태 결정
        if unhealthy_count == 0:
            health["overall_status"] = "healthy"
        elif unhealthy_count < len(self.clients) / 2:
            health["overall_status"] = "degraded"
        else:
            health["overall_status"] = "unhealthy"
        
        return health

# 사용
async def test_microservice_communication():
    registry = ServiceRegistry()
    
    # 주문 생성 테스트
    order_data = {
        "user_id": "user123",
        "items": [{"product_id": "prod1", "quantity": 2}],
        "payment_method": "credit_card"
    }
    
    for i in range(10):
        result = await registry.create_order(order_data)
        
        if result.is_success():
            order = result.unwrap()
            print(f"주문 {i+1}: 성공 - ID {order['id']}")
        else:
            print(f"주문 {i+1}: 실패 - {result.unwrap_err()}")
        
        await asyncio.sleep(2)
    
    # 시스템 전체 상태 확인
    health = registry.get_system_health()
    print(f"\n시스템 상태: {health['overall_status']}")
    
    for service_name, service_health in health["services"].items():
        cb_state = service_health["circuit_breaker"]["state"]
        success_rate = service_health["circuit_breaker"]["success_rate"]
        print(f"{service_name}: {cb_state} (성공률: {success_rate:.2%})")

# 실행
asyncio.run(test_microservice_communication())
```

### 서킷 브레이커 모니터링

```python
from rfs.service_discovery.circuit_breaker import get_all_circuit_breakers
from rfs.monitoring.metrics import get_metrics_collector

class CircuitBreakerMonitor:
    """서킷 브레이커 모니터링"""
    
    def __init__(self):
        self.metrics_collector = get_metrics_collector()
        
        # 서킷 브레이커 메트릭
        self.state_counter = self.metrics_collector.counter(
            "circuit_breaker_state_changes_total",
            description="서킷 브레이커 상태 변경 횟수"
        )
        
        self.request_counter = self.metrics_collector.counter(
            "circuit_breaker_requests_total", 
            description="서킷 브레이커를 통한 총 요청 수"
        )
        
        self.rejection_counter = self.metrics_collector.counter(
            "circuit_breaker_rejected_requests_total",
            description="서킷 브레이커에 의해 거부된 요청 수"
        )
        
        self.response_time_histogram = self.metrics_collector.histogram(
            "circuit_breaker_response_time_seconds",
            description="서킷 브레이커를 통한 응답 시간"
        )
    
    def collect_metrics(self):
        """모든 서킷 브레이커 메트릭 수집"""
        all_breakers = get_all_circuit_breakers()
        
        for name, breaker in all_breakers.items():
            metrics = breaker.get_metrics()
            labels = {"circuit_breaker": name}
            
            # 요청 수 메트릭
            self.request_counter.increment(
                metrics.total_requests,
                labels={**labels, "type": "total"}
            )
            
            self.request_counter.increment(
                metrics.successful_requests,
                labels={**labels, "type": "success"}
            )
            
            self.request_counter.increment(
                metrics.failed_requests,
                labels={**labels, "type": "failure"}
            )
            
            # 거부 수 메트릭
            self.rejection_counter.increment(
                metrics.rejected_requests,
                labels=labels
            )
            
            # 응답 시간 메트릭 (성공한 요청만)
            if metrics.successful_requests > 0:
                avg_response_time = metrics.average_response_time
                self.response_time_histogram.observe(
                    avg_response_time,
                    labels=labels
                )
            
            # 상태 변경 메트릭
            for timestamp, old_state, new_state in metrics.state_changes:
                self.state_counter.increment(
                    1,
                    labels={
                        **labels,
                        "from_state": old_state.value,
                        "to_state": new_state.value
                    }
                )
    
    def generate_dashboard_data(self) -> dict:
        """대시보드용 데이터 생성"""
        all_breakers = get_all_circuit_breakers()
        
        dashboard = {
            "summary": {
                "total_breakers": len(all_breakers),
                "open_breakers": 0,
                "half_open_breakers": 0,
                "closed_breakers": 0
            },
            "breakers": []
        }
        
        for name, breaker in all_breakers.items():
            state = breaker.get_state()
            metrics = breaker.get_metrics()
            
            # 요약 카운트 업데이트
            if state.value == "open":
                dashboard["summary"]["open_breakers"] += 1
            elif state.value == "half_open":
                dashboard["summary"]["half_open_breakers"] += 1
            else:
                dashboard["summary"]["closed_breakers"] += 1
            
            # 개별 브레이커 정보
            breaker_info = {
                "name": name,
                "state": state.value,
                "metrics": {
                    "total_requests": metrics.total_requests,
                    "success_rate": metrics.success_rate,
                    "failure_rate": metrics.failure_rate,
                    "average_response_time": metrics.average_response_time,
                    "rejected_requests": metrics.rejected_requests
                },
                "health_score": self._calculate_health_score(metrics)
            }
            
            dashboard["breakers"].append(breaker_info)
        
        # 건강도 기준으로 정렬 (낮은 순서대로)
        dashboard["breakers"].sort(key=lambda b: b["health_score"])
        
        return dashboard
    
    def _calculate_health_score(self, metrics) -> float:
        """건강도 점수 계산 (0-100)"""
        if metrics.total_requests == 0:
            return 100.0
        
        # 성공률 기반 점수 (70%)
        success_score = metrics.success_rate * 70
        
        # 응답 시간 기반 점수 (30%)
        # 1초 이하면 만점, 5초 이상이면 0점
        response_time_score = max(0, min(30, (5 - metrics.average_response_time) * 6))
        
        return success_score + response_time_score
    
    async def alert_on_threshold(self, failure_rate_threshold: float = 0.5):
        """임계값 기반 알림"""
        all_breakers = get_all_circuit_breakers()
        
        alerts = []
        
        for name, breaker in all_breakers.items():
            state = breaker.get_state()
            metrics = breaker.get_metrics()
            
            # OPEN 상태 알림
            if state.value == "open":
                alerts.append({
                    "severity": "critical",
                    "message": f"서킷 브레이커 '{name}'이 OPEN 상태입니다",
                    "details": {
                        "failure_rate": metrics.failure_rate,
                        "total_requests": metrics.total_requests
                    }
                })
            
            # 높은 실패율 경고
            elif metrics.failure_rate > failure_rate_threshold:
                alerts.append({
                    "severity": "warning", 
                    "message": f"서킷 브레이커 '{name}'의 실패율이 높습니다",
                    "details": {
                        "failure_rate": metrics.failure_rate,
                        "threshold": failure_rate_threshold
                    }
                })
        
        return alerts

# 사용
monitor = CircuitBreakerMonitor()

# 메트릭 수집
monitor.collect_metrics()

# 대시보드 데이터
dashboard = monitor.generate_dashboard_data()
print(f"총 서킷 브레이커: {dashboard['summary']['total_breakers']}개")
print(f"OPEN 상태: {dashboard['summary']['open_breakers']}개")

# 건강도 낮은 순으로 표시
for breaker in dashboard["breakers"][:5]:
    print(f"{breaker['name']}: {breaker['state']} (건강도: {breaker['health_score']:.1f})")

# 알림 확인
alerts = await monitor.alert_on_threshold(failure_rate_threshold=0.3)
for alert in alerts:
    print(f"[{alert['severity'].upper()}] {alert['message']}")
```

## 🎨 베스트 프랙티스

### 1. 적절한 임계값 설정

```python
# ✅ 좋은 예 - 서비스 특성에 맞는 설정
def get_circuit_breaker_config(service_type: str) -> CircuitBreakerConfig:
    """서비스 타입별 서킷 브레이커 설정"""
    
    if service_type == "database":
        # 데이터베이스: 빠른 복구, 낮은 임계값
        return CircuitBreakerConfig(
            failure_threshold=3,
            failure_rate_threshold=0.3,
            timeout=2.0,
            reset_timeout=30.0
        )
    
    elif service_type == "external_api":
        # 외부 API: 더 관대한 설정
        return CircuitBreakerConfig(
            failure_threshold=5,
            failure_rate_threshold=0.6,
            timeout=10.0,
            reset_timeout=60.0
        )
    
    elif service_type == "critical_service":
        # 중요 서비스: 매우 민감한 설정
        return CircuitBreakerConfig(
            failure_threshold=2,
            failure_rate_threshold=0.2,
            timeout=1.0,
            reset_timeout=15.0
        )
    
    else:
        # 기본 설정
        return CircuitBreakerConfig()
```

### 2. 폴백 패턴 구현

```python
# ✅ 좋은 예 - 적절한 폴백 전략
@circuit_breaker(name="user_service")
async def get_user_info(user_id: str) -> Result[dict, str]:
    """사용자 정보 조회"""
    # 실제 서비스 호출
    return await call_user_service(user_id)

async def get_user_with_fallback(user_id: str) -> Result[dict, str]:
    """폴백이 있는 사용자 정보 조회"""
    try:
        # 주 서비스 시도
        result = await get_user_info(user_id)
        if result.is_success():
            return result
    
    except Exception:
        pass  # 서킷 브레이커가 열려있음
    
    # 폴백 1: 캐시에서 조회
    cached_user = await get_user_from_cache(user_id)
    if cached_user:
        return Success(cached_user)
    
    # 폴백 2: 기본 정보 반환
    return Success({
        "id": user_id,
        "name": "Unknown User",
        "cached": True
    })
```

### 3. 모니터링 및 알림

```python
# ✅ 좋은 예 - 포괄적인 모니터링
def setup_circuit_breaker_monitoring():
    """서킷 브레이커 모니터링 설정"""
    
    # 상태 변경 콜백 등록
    def on_state_change(breaker_name: str, old_state, new_state):
        if new_state.value == "open":
            # 즉시 알림
            send_alert(f"CRITICAL: {breaker_name} 서킷 브레이커 OPEN")
        
        elif old_state.value == "open" and new_state.value == "half_open":
            # 복구 시도 알림
            send_notification(f"INFO: {breaker_name} 서킷 브레이커 복구 시도 중")
    
    # 모든 서킷 브레이커에 콜백 등록
    for breaker in get_all_circuit_breakers().values():
        breaker.on_state_change = lambda old, new: on_state_change(breaker.name, old, new)
```

### 4. 테스트 전략

```python
# ✅ 좋은 예 - 서킷 브레이커 테스트
import pytest

class TestCircuitBreaker:
    
    @pytest.fixture
    def test_breaker(self):
        """테스트용 서킷 브레이커"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            reset_timeout=1.0,
            half_open_max_requests=1
        )
        return CircuitBreaker("test", config)
    
    async def test_circuit_breaker_opens_on_failures(self, test_breaker):
        """연속 실패 시 OPEN 상태 전환"""
        
        async def failing_function():
            raise Exception("Test failure")
        
        # 연속 실패로 OPEN 상태 만들기
        for _ in range(3):
            try:
                await test_breaker.call_async(failing_function)
            except:
                pass
        
        assert test_breaker.is_open()
    
    async def test_circuit_breaker_half_open_recovery(self, test_breaker):
        """HALF_OPEN에서 복구 테스트"""
        
        # OPEN 상태로 만들기
        await self._make_breaker_open(test_breaker)
        
        # 타임아웃 대기
        await asyncio.sleep(1.1)
        
        # 성공하는 함수로 복구 테스트
        async def success_function():
            return "success"
        
        result = await test_breaker.call_async(success_function)
        assert result == "success"
        assert test_breaker.is_closed()
```

## ⚠️ 주의사항

### 1. 임계값 설정
- 너무 낮은 임계값: 불필요한 차단으로 가용성 저하
- 너무 높은 임계값: 장애 전파 방지 효과 감소
- 서비스 특성과 SLA를 고려한 설정 필요

### 2. 폴백 전략
- 폴백 로직도 실패할 수 있음을 고려
- 폴백 데이터의 일관성 관리
- 폴백 성능이 시스템에 미치는 영향 고려

### 3. 상태 전환 타이밍
- 너무 빠른 복구 시도: 불안정한 서비스에 부하 증가
- 너무 늦은 복구: 가용성 저하 시간 증가
- 지수 백오프나 점진적 복구 고려

### 4. 메모리 사용량
- 슬라이딩 윈도우 크기 관리
- 메트릭 데이터 누적으로 인한 메모리 리크 방지
- 정기적인 메트릭 정리 또는 순환 버퍼 사용

## 🔗 관련 문서
- [로드 밸런싱](./13-load-balancing.md) - 로드 밸런서와 서킷 브레이커 통합
- [모니터링](./08-monitoring.md) - 서킷 브레이커 메트릭 수집
- [보안](./11-security.md) - DDoS 방어와 서킷 브레이커
- [배포](./05-deployment.md) - 무중단 배포와 서킷 브레이커