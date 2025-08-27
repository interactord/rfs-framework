"""
RFS Framework - 모니터링 및 관측성 예제

이 예제는 RFS Framework의 모니터링, 메트릭, 로깅, 성능 측정 기능을 통합적으로 보여줍니다:
- 성능 모니터링 데코레이터
- Prometheus 메트릭 수집
- 감사 로깅 및 구조화된 로깅
- 헬스체크 및 서비스 상태 모니터링
- 실시간 대시보드 및 알림
"""

import asyncio
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

# RFS 프레임워크 모니터링 컴포넌트
from rfs.core.result import Result, Success, Failure
from rfs.core.logging_decorators import LoggedOperation, AuditLogged, ErrorLogged
from rfs.monitoring.performance_decorators import PerformanceMonitored, Cached
from rfs.monitoring.metrics import (
    MetricsCollector, Counter, Gauge, Histogram, Summary,
    PrometheusExporter, CloudMonitoringClient
)

# 기타 필요한 컴포넌트
from rfs.core.annotations import Component
from rfs.service_discovery.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


# ================================================
# 비즈니스 메트릭 정의
# ================================================

@dataclass
class BusinessMetrics:
    """비즈니스 메트릭"""
    total_users=0
    active_sessions=0
    orders_per_hour=0
    revenue_today: float = 0.0
    conversion_rate: float = 0.0


@dataclass
class SystemMetrics:
    """시스템 메트릭"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    request_count=0
    error_count=0
    response_time_avg: float = 0.0


# ================================================
# 메트릭 수집기 구현
# ================================================

@Component(name="metrics_collector")
class ApplicationMetricsCollector:
    """애플리케이션 메트릭 수집기"""
    
    def __init__(self):
        self.collector = MetricsCollector()
        
        # 카운터 메트릭
        self.request_counter = self.collector.create_counter(
            "http_requests_total",
            "총 HTTP 요청 수",
            labels=["method", "endpoint", "status"]
        )
        
        self.user_registrations = self.collector.create_counter(
            "user_registrations_total",
            "총 사용자 등록 수"
        )
        
        self.orders_counter = self.collector.create_counter(
            "orders_total",
            "총 주문 수",
            labels=["status"]
        )
        
        # 게이지 메트릭
        self.active_users = self.collector.create_gauge(
            "active_users_current",
            "현재 활성 사용자 수"
        )
        
        self.system_cpu = self.collector.create_gauge(
            "system_cpu_usage_percent",
            "시스템 CPU 사용률"
        )
        
        self.system_memory = self.collector.create_gauge(
            "system_memory_usage_percent",
            "시스템 메모리 사용률"
        )
        
        # 히스토그램 메트릭
        self.request_duration = self.collector.create_histogram(
            "http_request_duration_seconds",
            "HTTP 요청 처리 시간",
            labels=["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
        )
        
        self.order_value = self.collector.create_histogram(
            "order_value_dollars",
            "주문 금액 분포",
            buckets=[10, 50, 100, 500, 1000, 5000]
        )
        
        # 요약 메트릭
        self.database_query_time = self.collector.create_summary(
            "database_query_duration_seconds",
            "데이터베이스 쿼리 시간",
            labels=["operation"]
        )
    
    def record_request(self, method: str, endpoint: str, status: str, duration: float):
        """HTTP 요청 기록"""
        self.request_counter.increment(labels={"method": method, "endpoint": endpoint, "status": status})
        self.request_duration.observe(duration, labels={"method": method, "endpoint": endpoint})
    
    def record_user_registration(self):
        """사용자 등록 기록"""
        self.user_registrations.increment()
    
    def record_order(self, status: str, value: float):
        """주문 기록"""
        self.orders_counter.increment(labels={"status": status})
        self.order_value.observe(value)
    
    def update_system_metrics(self, cpu: float, memory: float):
        """시스템 메트릭 업데이트"""
        self.system_cpu.set(cpu)
        self.system_memory.set(memory)
    
    def set_active_users(self, count: int):
        """활성 사용자 수 설정"""
        self.active_users.set(count)
    
    def record_database_query(self, operation: str, duration: float):
        """데이터베이스 쿼리 시간 기록"""
        self.database_query_time.observe(duration, labels={"operation": operation})


# ================================================
# 모니터링되는 서비스 예제
# ================================================

class UserService:
    """사용자 서비스 - 모니터링 적용 예제"""
    
    def __init__(self, metrics_collector: ApplicationMetricsCollector):
        self.metrics = metrics_collector
        self.users_db = {}
        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30
            )
        )
    
    @LoggedOperation("user_service")
    @PerformanceMonitored("user_creation")
    @AuditLogged("user_registered")
    async def create_user(self, user_data: dict) -> Result[dict, str]:
        """사용자 생성"""
        start_time = time.time()
        
        try:
            # 입력 검증
            if not user_data.get("email"):
                self.metrics.record_request("POST", "/users", "400", time.time() - start_time)
                return Failure("이메일이 필요합니다")
            
            # 중복 체크
            if user_data["email"] in self.users_db:
                self.metrics.record_request("POST", "/users", "409", time.time() - start_time)
                return Failure("이미 존재하는 사용자입니다")
            
            # 데이터베이스 저장 시뮬레이션
            await self._simulate_database_operation("user_insert", 0.1, 0.3)
            
            # 사용자 생성
            user = {
                "id": f"user_{len(self.users_db) + 1}",
                "email": user_data["email"],
                "name": user_data.get("name", ""),
                "created_at": datetime.now().isoformat()
            }
            
            self.users_db[user_data["email"]] = user
            
            # 메트릭 기록
            self.metrics.record_request("POST", "/users", "201", time.time() - start_time)
            self.metrics.record_user_registration()
            
            print(f"👤 사용자 생성: {user['email']}")
            
            return Success(user)
            
        except Exception as e:
            self.metrics.record_request("POST", "/users", "500", time.time() - start_time)
            return Failure(f"사용자 생성 실패: {str(e)}")
    
    @Cached(ttl=300)  # 5분 캐시
    @PerformanceMonitored("user_query")
    async def get_user(self, email: str) -> Result[dict, str]:
        """사용자 조회"""
        start_time = time.time()
        
        try:
            # 데이터베이스 조회 시뮬레이션
            await self._simulate_database_operation("user_select", 0.05, 0.15)
            
            if email in self.users_db:
                user = self.users_db[email]
                self.metrics.record_request("GET", "/users", "200", time.time() - start_time)
                return Success(user)
            else:
                self.metrics.record_request("GET", "/users", "404", time.time() - start_time)
                return Failure("사용자를 찾을 수 없습니다")
                
        except Exception as e:
            self.metrics.record_request("GET", "/users", "500", time.time() - start_time)
            return Failure(f"사용자 조회 실패: {str(e)}")
    
    async def _simulate_database_operation(self, operation: str, min_time: float, max_time: float):
        """데이터베이스 작업 시뮬레이션"""
        start_time = time.time()
        
        # 랜덤 지연으로 데이터베이스 작업 시뮬레이션
        delay = random.uniform(min_time, max_time)
        await asyncio.sleep(delay)
        
        # 메트릭 기록
        self.metrics.record_database_query(operation, time.time() - start_time)


class OrderService:
    """주문 서비스 - 모니터링 적용 예제"""
    
    def __init__(self, metrics_collector: ApplicationMetricsCollector):
        self.metrics = metrics_collector
        self.orders_db = {}
    
    @LoggedOperation("order_service")
    @PerformanceMonitored("order_creation")
    @AuditLogged("order_created")
    async def create_order(self, order_data: dict) -> Result[dict, str]:
        """주문 생성"""
        start_time = time.time()
        
        try:
            # 주문 데이터 검증
            if not order_data.get("user_id"):
                self.metrics.record_request("POST", "/orders", "400", time.time() - start_time)
                return Failure("사용자 ID가 필요합니다")
            
            if not order_data.get("items"):
                self.metrics.record_request("POST", "/orders", "400", time.time() - start_time)
                return Failure("주문 항목이 필요합니다")
            
            # 주문 총액 계산
            total = sum(item.get("price", 0) * item.get("quantity", 1) for item in order_data["items"])
            
            # 주문 생성
            order = {
                "id": f"order_{len(self.orders_db) + 1}",
                "user_id": order_data["user_id"],
                "items": order_data["items"],
                "total": total,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            
            # 데이터베이스 저장 시뮬레이션
            await self._simulate_order_processing(order)
            
            self.orders_db[order["id"]] = order
            
            # 메트릭 기록
            self.metrics.record_request("POST", "/orders", "201", time.time() - start_time)
            self.metrics.record_order("created", total)
            
            print(f"🛒 주문 생성: {order['id']} (${total})")
            
            return Success(order)
            
        except Exception as e:
            self.metrics.record_request("POST", "/orders", "500", time.time() - start_time)
            return Failure(f"주문 생성 실패: {str(e)}")
    
    @ErrorLogged("order_processing_error")
    async def _simulate_order_processing(self, order: dict):
        """주문 처리 시뮬레이션"""
        # 결제 처리 시뮬레이션
        await asyncio.sleep(0.2)
        
        # 10% 확률로 에러 발생
        if random.random() < 0.1:
            raise Exception("결제 처리 실패")
        
        # 재고 확인 시뮬레이션
        await asyncio.sleep(0.1)
        
        order["status"] = "confirmed"


# ================================================
# 헬스체크 및 시스템 모니터링
# ================================================

class HealthCheckService:
    """헬스체크 서비스"""
    
    def __init__(self, metrics_collector: ApplicationMetricsCollector):
        self.metrics = metrics_collector
        self.services = {}
    
    def register_service(self, name: str, health_check_func):
        """서비스 헬스체크 등록"""
        self.services[name] = health_check_func
    
    @LoggedOperation("health_check")
    async def check_all_services(self) -> dict:
        """모든 서비스 헬스체크"""
        results = {}
        overall_healthy = True
        
        for service_name, check_func in self.services.items():
            try:
                start_time = time.time()
                result = await check_func()
                duration = time.time() - start_time
                
                results[service_name] = {
                    "status": "healthy" if result else "unhealthy",
                    "response_time": duration
                }
                
                if not result:
                    overall_healthy = False
                    
            except Exception as e:
                results[service_name] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_healthy = False
        
        return {
            "overall": "healthy" if overall_healthy else "unhealthy",
            "services": results,
            "timestamp": datetime.now().isoformat()
        }


class SystemMonitor:
    """시스템 리소스 모니터"""
    
    def __init__(self, metrics_collector: ApplicationMetricsCollector):
        self.metrics = metrics_collector
        self.monitoring = True
    
    async def start_monitoring(self):
        """시스템 모니터링 시작"""
        print("📊 시스템 모니터링 시작...")
        
        while self.monitoring:
            try:
                # 시스템 메트릭 수집 (시뮬레이션)
                cpu_usage = random.uniform(10, 80)
                memory_usage = random.uniform(30, 90)
                
                # 메트릭 업데이트
                self.metrics.update_system_metrics(cpu_usage, memory_usage)
                
                # 활성 사용자 수 시뮬레이션
                active_users = random.randint(50, 200)
                self.metrics.set_active_users(active_users)
                
                print(f"📈 시스템 상태: CPU {cpu_usage:.1f}%, 메모리 {memory_usage:.1f}%, 활성 사용자 {active_users}")
                
                await asyncio.sleep(10)  # 10초마다 수집
                
            except Exception as e:
                print(f"❌ 시스템 모니터링 오류: {e}")
                await asyncio.sleep(5)
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring = False


# ================================================
# 알림 시스템
# ================================================

class AlertManager:
    """알림 관리자"""
    
    def __init__(self, metrics_collector: ApplicationMetricsCollector):
        self.metrics = metrics_collector
        self.alert_rules = []
        self.monitoring = True
    
    def add_alert_rule(self, name: str, condition_func, message: str, severity="warning"):
        """알림 규칙 추가"""
        self.alert_rules.append({
            "name": name,
            "condition": condition_func,
            "message": message,
            "severity": severity,
            "last_triggered": None
        })
    
    async def start_monitoring(self):
        """알림 모니터링 시작"""
        print("🚨 알림 시스템 시작...")
        
        while self.monitoring:
            try:
                for rule in self.alert_rules:
                    if await rule["condition"]():
                        # 중복 알림 방지 (5분 간격)
                        now = datetime.now()
                        if rule["last_triggered"] is None or \
                           now - rule["last_triggered"] > timedelta(minutes=5):
                            
                            await self.send_alert(rule["name"], rule["message"], rule["severity"])
                            rule["last_triggered"] = now
                
                await asyncio.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                print(f"❌ 알림 시스템 오류: {e}")
                await asyncio.sleep(10)
    
    async def send_alert(self, name: str, message: str, severity: str):
        """알림 발송"""
        icon = "🚨" if severity == "critical" else "⚠️" if severity == "warning" else "ℹ️"
        print(f"{icon} 알림 [{severity.upper()}] {name}: {message}")
        
        # 실제로는 이메일, Slack, PagerDuty 등으로 알림 발송
    
    def stop_monitoring(self):
        """알림 모니터링 중지"""
        self.monitoring = False


# ================================================
# 대시보드 (간단한 콘솔 출력)
# ================================================

class ConsoleDashboard:
    """콘솔 대시보드"""
    
    def __init__(self, metrics_collector: ApplicationMetricsCollector):
        self.metrics = metrics_collector
    
    async def display_metrics(self):
        """메트릭 표시"""
        print("\n" + "="*60)
        print("📊 RFS Framework 모니터링 대시보드")
        print("="*60)
        
        # HTTP 요청 통계
        print("\n🌐 HTTP 요청 통계:")
        print(f"   총 요청 수: {self.metrics.request_counter.value}")
        print(f"   평균 응답 시간: {self.metrics.request_duration.value:.3f}초")
        
        # 비즈니스 메트릭
        print("\n👥 비즈니스 메트릭:")
        print(f"   사용자 등록 수: {self.metrics.user_registrations.value}")
        print(f"   총 주문 수: {self.metrics.orders_counter.value}")
        print(f"   활성 사용자: {self.metrics.active_users.value}")
        
        # 시스템 메트릭
        print("\n🖥️  시스템 메트릭:")
        print(f"   CPU 사용률: {self.metrics.system_cpu.value:.1f}%")
        print(f"   메모리 사용률: {self.metrics.system_memory.value:.1f}%")
        
        # 데이터베이스 메트릭
        print(f"\n🗄️  데이터베이스 메트릭:")
        print(f"   평균 쿼리 시간: {self.metrics.database_query_time.value:.3f}초")
        
        print("="*60)


# ================================================
# 메인 모니터링 애플리케이션
# ================================================

class MonitoringApplication:
    """모니터링 애플리케이션"""
    
    def __init__(self):
        # 메트릭 수집기
        self.metrics = ApplicationMetricsCollector()
        
        # 서비스
        self.user_service = UserService(self.metrics)
        self.order_service = OrderService(self.metrics)
        
        # 모니터링 컴포넌트
        self.health_check = HealthCheckService(self.metrics)
        self.system_monitor = SystemMonitor(self.metrics)
        self.alert_manager = AlertManager(self.metrics)
        self.dashboard = ConsoleDashboard(self.metrics)
        
        # Prometheus 익스포터 (시뮬레이션)
        self.prometheus_exporter = PrometheusExporter(self.metrics.collector)
    
    def setup_health_checks(self):
        """헬스체크 설정"""
        self.health_check.register_service("user_service", self._user_service_health)
        self.health_check.register_service("order_service", self._order_service_health)
        self.health_check.register_service("database", self._database_health)
    
    def setup_alerts(self):
        """알림 규칙 설정"""
        # 높은 에러율 알림
        self.alert_manager.add_alert_rule(
            "high_error_rate",
            lambda: self.metrics.system_cpu.value > 80,
            "CPU 사용률이 80%를 초과했습니다",
            "warning"
        )
        
        # 메모리 부족 알림
        self.alert_manager.add_alert_rule(
            "high_memory_usage",
            lambda: self.metrics.system_memory.value > 85,
            "메모리 사용률이 85%를 초과했습니다",
            "critical"
        )
        
        # 활성 사용자 급증 알림
        self.alert_manager.add_alert_rule(
            "user_surge",
            lambda: self.metrics.active_users.value > 180,
            "활성 사용자가 급증했습니다",
            "info"
        )
    
    async def _user_service_health(self) -> bool:
        """사용자 서비스 헬스체크"""
        try:
            # 간단한 헬스체크 쿼리
            await asyncio.sleep(0.01)
            return True
        except:
            return False
    
    async def _order_service_health(self) -> bool:
        """주문 서비스 헬스체크"""
        try:
            await asyncio.sleep(0.01)
            return True
        except:
            return False
    
    async def _database_health(self) -> bool:
        """데이터베이스 헬스체크"""
        try:
            await asyncio.sleep(0.05)
            return random.random() > 0.1  # 10% 확률로 실패
        except:
            return False
    
    async def simulate_traffic(self):
        """트래픽 시뮬레이션"""
        print("🚗 트래픽 시뮬레이션 시작...")
        
        users = []
        
        for i in range(100):  # 100회 반복
            try:
                # 사용자 생성 (30% 확률)
                if random.random() < 0.3:
                    result = await self.user_service.create_user({
                        "email": f"user{i}@example.com",
                        "name": f"User {i}"
                    })
                    
                    if result.is_success():
                        users.append(result.value)
                
                # 사용자 조회 (50% 확률)
                if users and random.random() < 0.5:
                    user = random.choice(users)
                    await self.user_service.get_user(user["email"])
                
                # 주문 생성 (20% 확률)
                if users and random.random() < 0.2:
                    user = random.choice(users)
                    await self.order_service.create_order({
                        "user_id": user["id"],
                        "items": [
                            {"name": "Product A", "price": random.uniform(10, 100), "quantity": random.randint(1, 3)}
                        ]
                    })
                
                # 랜덤 지연
                await asyncio.sleep(random.uniform(0.1, 0.5))
                
                # 10회마다 대시보드 업데이트
                if i % 10 == 0:
                    await self.dashboard.display_metrics()
                
            except Exception as e:
                print(f"❌ 트래픽 시뮬레이션 오류: {e}")
        
        print("✅ 트래픽 시뮬레이션 완료")
    
    async def run_health_checks(self):
        """헬스체크 실행"""
        print("\n🏥 헬스체크 실행...")
        result = await self.health_check.check_all_services()
        
        print(f"전체 상태: {result['overall']}")
        for service, status in result['services'].items():
            icon = "✅" if status['status'] == 'healthy' else "❌"
            print(f"{icon} {service}: {status['status']}")
    
    async def start(self):
        """모니터링 애플리케이션 시작"""
        print("🚀 RFS 모니터링 시스템 시작")
        
        # 설정
        self.setup_health_checks()
        self.setup_alerts()
        
        # 백그라운드 모니터링 시작
        monitoring_tasks = [
            asyncio.create_task(self.system_monitor.start_monitoring()),
            asyncio.create_task(self.alert_manager.start_monitoring()),
        ]
        
        try:
            # 메인 시나리오 실행
            await self.simulate_traffic()
            
            # 헬스체크
            await self.run_health_checks()
            
            # 최종 대시보드
            await self.dashboard.display_metrics()
            
            # Prometheus 메트릭 내보내기 (시뮬레이션)
            print("\n📈 Prometheus 메트릭 내보내기:")
            metrics_data = await self.prometheus_exporter.export()
            print(f"내보낸 메트릭 수: {len(metrics_data)} 개")
            
        finally:
            # 모니터링 중지
            self.system_monitor.stop_monitoring()
            self.alert_manager.stop_monitoring()
            
            # 백그라운드 작업 정리
            for task in monitoring_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


async def main():
    """메인 실행"""
    app = MonitoringApplication()
    await app.start()


if __name__ == "__main__":
    print("📊 RFS Framework - 모니터링 및 관측성 예제")
    print("=" * 60)
    print("이 예제는 다음 기능들을 보여줍니다:")
    print("• 성능 모니터링 데코레이터 (@PerformanceMonitored)")
    print("• Prometheus 메트릭 수집 (Counter, Gauge, Histogram)")
    print("• 감사 로깅 (@AuditLogged, @LoggedOperation)")
    print("• 헬스체크 및 서비스 상태 모니터링")
    print("• 실시간 알림 및 대시보드")
    print("• 캐싱 및 성능 최적화")
    print("=" * 60)
    
    asyncio.run(main())