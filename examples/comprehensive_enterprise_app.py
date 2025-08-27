"""
RFS Framework v4 - 통합 엔터프라이즈 애플리케이션 예제

이 예제는 RFS Framework의 모든 주요 기능들을 통합한 완전한 엔터프라이즈 애플리케이션을 보여줍니다:
- Result Pattern과 함수형 에러 핸들링
- 헥사고날 아키텍처와 의존성 주입
- 반응형 프로그래밍 (Mono/Flux)
- 보안 및 접근 제어 (RBAC/ABAC)
- 성능 모니터링 및 메트릭
- 배포 전략과 롤백 관리
- 서킷 브레이커와 로드 밸런싱
- 감사 로깅과 트랜잭션 관리
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# RFS 프레임워크 핵심 컴포넌트
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Port, Adapter, UseCase, Controller, Component
from rfs.core.registry import ServiceScope, get_registry
from rfs.core.logging_decorators import LoggedOperation, AuditLogged
from rfs.core.transactions import TransactionManager, transactional

# 반응형 프로그래밍
from rfs.reactive import Mono, Flux

# 보안
from rfs.security.access_control import RequiresRole, RequiresPermission, RequiresAuthentication
from rfs.security.validation_decorators import ValidateInput, SanitizeInput, RateLimited

# 모니터링
from rfs.monitoring.performance_decorators import PerformanceMonitored, Cached

# 프로덕션
from rfs.production.strategies import DeploymentStrategyFactory, DeploymentType, DeploymentConfig
from rfs.production.rollback import RollbackManager
from rfs.service_discovery.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from rfs.service_discovery.load_balancer import LoadBalancer, LoadBalancingAlgorithm


# ================================================
# 도메인 모델 (Domain Models)
# ================================================

class User:
    def __init__(self, user_id: str, email: str, name: str, role="user"):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.role = role
        self.created_at = datetime.now()


class Order:
    def __init__(self, order_id: str, user_id: str, items: List[dict], total: float):
        self.order_id = order_id
        self.user_id = user_id
        self.items = items
        self.total = total
        self.status = "pending"
        self.created_at = datetime.now()


class Product:
    def __init__(self, product_id: str, name: str, price: float, stock: int):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.stock = stock


# ================================================
# Port 정의 (헥사고날 아키텍처)
# ================================================

@Port(name="user_repository")
class UserRepository:
    async def find_by_id(self, user_id: str) -> Result[Optional[User], str]:
        pass
    
    async def find_by_email(self, email: str) -> Result[Optional[User], str]:
        pass
    
    async def save(self, user: User) -> Result[User, str]:
        pass


@Port(name="order_repository")
class OrderRepository:
    async def find_by_id(self, order_id: str) -> Result[Optional[Order], str]:
        pass
    
    async def save(self, order: Order) -> Result[Order, str]:
        pass
    
    async def find_by_user_id(self, user_id: str) -> Result[List[Order], str]:
        pass


@Port(name="product_repository")
class ProductRepository:
    async def find_by_id(self, product_id: str) -> Result[Optional[Product], str]:
        pass
    
    async def update_stock(self, product_id: str, quantity: int) -> Result[bool, str]:
        pass


@Port(name="notification_service")
class NotificationService:
    async def send_email(self, to: str, subject: str, body: str) -> Result[bool, str]:
        pass
    
    async def send_sms(self, phone: str, message: str) -> Result[bool, str]:
        pass


@Port(name="payment_service")
class PaymentService:
    async def process_payment(self, amount: float, payment_method: dict) -> Result[dict, str]:
        pass


# ================================================
# Adapter 구현 (인프라스트럭처)
# ================================================

@Adapter(port="user_repository", scope=ServiceScope.SINGLETON)
class PostgresUserRepository(UserRepository):
    def __init__(self):
        self.users = {}  # 실제로는 PostgreSQL 연결
    
    @LoggedOperation("database")
    @PerformanceMonitored("user_repository")
    async def find_by_id(self, user_id: str) -> Result[Optional[User], str]:
        if user_id in self.users:
            return Success(self.users[user_id])
        return Success(None)
    
    async def find_by_email(self, email: str) -> Result[Optional[User], str]:
        for user in self.users.values():
            if user.email == email:
                return Success(user)
        return Success(None)
    
    @AuditLogged("user_created")
    async def save(self, user: User) -> Result[User, str]:
        self.users[user.user_id] = user
        return Success(user)


@Adapter(port="order_repository", scope=ServiceScope.SINGLETON)
class PostgresOrderRepository(OrderRepository):
    def __init__(self):
        self.orders = {}
        self.user_orders = {}
    
    @PerformanceMonitored("order_repository")
    async def find_by_id(self, order_id: str) -> Result[Optional[Order], str]:
        if order_id in self.orders:
            return Success(self.orders[order_id])
        return Success(None)
    
    @AuditLogged("order_created")
    async def save(self, order: Order) -> Result[Order, str]:
        self.orders[order.order_id] = order
        if order.user_id not in self.user_orders:
            self.user_orders[order.user_id] = []
        self.user_orders[order.user_id].append(order)
        return Success(order)
    
    async def find_by_user_id(self, user_id: str) -> Result[List[Order], str]:
        orders = self.user_orders.get(user_id, [])
        return Success(orders)


@Adapter(port="product_repository", scope=ServiceScope.SINGLETON)
class InMemoryProductRepository(ProductRepository):
    def __init__(self):
        self.products = {
            "1": Product("1", "MacBook Pro", 2499.99, 10),
            "2": Product("2", "iPhone 15", 999.99, 50),
            "3": Product("3", "iPad Air", 599.99, 30)
        }
    
    @Cached(ttl=300)  # 5분 캐시
    async def find_by_id(self, product_id: str) -> Result[Optional[Product], str]:
        if product_id in self.products:
            return Success(self.products[product_id])
        return Success(None)
    
    @transactional
    async def update_stock(self, product_id: str, quantity: int) -> Result[bool, str]:
        if product_id not in self.products:
            return Failure(f"제품을 찾을 수 없습니다: {product_id}")
        
        product = self.products[product_id]
        if product.stock < quantity:
            return Failure("재고 부족")
        
        product.stock -= quantity
        return Success(True)


@Adapter(port="notification_service", scope=ServiceScope.SINGLETON)
class EmailNotificationService(NotificationService):
    def __init__(self):
        # 서킷 브레이커로 외부 서비스 보호
        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30,
                expected_exception=Exception
            )
        )
    
    @RateLimited(max_calls=10, period=timedelta(seconds=60))
    async def send_email(self, to: str, subject: str, body: str) -> Result[bool, str]:
        async def _send():
            # 실제로는 이메일 서비스 API 호출
            print(f"📧 이메일 발송: {to} - {subject}")
            return Success(True)
        
        return await self.circuit_breaker.execute(_send)
    
    async def send_sms(self, phone: str, message: str) -> Result[bool, str]:
        print(f"📱 SMS 발송: {phone} - {message}")
        return Success(True)


@Adapter(port="payment_service", scope=ServiceScope.SINGLETON)
class StripePaymentService(PaymentService):
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60,
                expected_exception=Exception
            )
        )
    
    @PerformanceMonitored("payment_processing")
    async def process_payment(self, amount: float, payment_method: dict) -> Result[dict, str]:
        async def _process():
            # Stripe API 호출 시뮬레이션
            print(f"💳 결제 처리: ${amount}")
            return Success({
                "transaction_id": f"txn_{datetime.now().timestamp()}",
                "amount": amount,
                "status": "completed"
            })
        
        return await self.circuit_breaker.execute(_process)


# ================================================
# UseCase 정의 (애플리케이션 계층)
# ================================================

@UseCase(dependencies=["user_repository", "notification_service"])
class CreateUserUseCase:
    def __init__(self, user_repository: UserRepository, notification_service: NotificationService):
        self.user_repository = user_repository
        self.notification_service = notification_service
    
    @ValidateInput({
        "email": {"type": "email", "required": True},
        "name": {"type": "string", "min_length": 2, "required": True},
        "role": {"type": "string", "choices": ["user", "admin"], "default": "user"}
    })
    @AuditLogged("user_registration")
    async def execute(self, user_data: dict) -> Result[User, str]:
        # 중복 이메일 체크
        existing_user = await self.user_repository.find_by_email(user_data["email"])
        if existing_user.is_success() and existing_user.value:
            return Failure("이미 등록된 이메일입니다")
        
        # 사용자 생성
        user = User(
            user_id=f"user_{datetime.now().timestamp()}",
            email=user_data["email"],
            name=user_data["name"],
            role=user_data.get("role", "user")
        )
        
        # 저장
        save_result = await self.user_repository.save(user)
        if save_result.is_failure():
            return save_result
        
        # 환영 이메일 발송 (비동기로 처리)
        asyncio.create_task(
            self.notification_service.send_email(
                user.email,
                "환영합니다!",
                f"안녕하세요 {user.name}님, 가입을 축하드립니다!"
            )
        )
        
        return Success(user)


@UseCase(dependencies=["order_repository", "product_repository", "payment_service", "notification_service"])
class CreateOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        product_repository: ProductRepository,
        payment_service: PaymentService,
        notification_service: NotificationService
    ):
        self.order_repository = order_repository
        self.product_repository = product_repository
        self.payment_service = payment_service
        self.notification_service = notification_service
        self.transaction_manager = TransactionManager()
    
    @ValidateInput({
        "user_id": {"type": "string", "required": True},
        "items": {"type": "array", "required": True, "min_items": 1},
        "payment_method": {"type": "object", "required": True}
    })
    @transactional
    @PerformanceMonitored("order_creation")
    @AuditLogged("order_created")
    async def execute(self, order_data: dict) -> Result[Order, str]:
        """주문 생성 - 반응형 스트림으로 처리"""
        
        # 1. 제품 검증 및 가격 계산 (Flux 사용)
        product_validation_result = await (
            Flux.from_iterable(order_data["items"])
            .flat_map(self._validate_and_calculate_item)
            .collect_list()
        )
        
        if any(item.get("error") for item in product_validation_result):
            errors = [item["error"] for item in product_validation_result if item.get("error")]
            return Failure(f"제품 검증 실패: {', '.join(errors)}")
        
        # 2. 총 금액 계산
        total_amount = sum(item["total_price"] for item in product_validation_result)
        
        # 3. 결제 처리
        payment_result = await self.payment_service.process_payment(
            total_amount,
            order_data["payment_method"]
        )
        
        if payment_result.is_failure():
            return Failure(f"결제 실패: {payment_result.error}")
        
        # 4. 재고 업데이트 (트랜잭션 내에서)
        for item in order_data["items"]:
            stock_result = await self.product_repository.update_stock(
                item["product_id"],
                item["quantity"]
            )
            if stock_result.is_failure():
                return Failure(f"재고 업데이트 실패: {stock_result.error}")
        
        # 5. 주문 생성
        order = Order(
            order_id=f"order_{datetime.now().timestamp()}",
            user_id=order_data["user_id"],
            items=product_validation_result,
            total=total_amount
        )
        order.status = "paid"
        
        # 6. 주문 저장
        save_result = await self.order_repository.save(order)
        if save_result.is_failure():
            return save_result
        
        # 7. 주문 확인 알림 (비동기)
        asyncio.create_task(
            self._send_order_confirmation(order)
        )
        
        return Success(order)
    
    async def _validate_and_calculate_item(self, item: dict) -> dict:
        """개별 아이템 검증 및 가격 계산"""
        product_result = await self.product_repository.find_by_id(item["product_id"])
        
        if product_result.is_failure():
            return {"error": f"제품 조회 실패: {product_result.error}"}
        
        product = product_result.value
        if not product:
            return {"error": f"제품을 찾을 수 없습니다: {item['product_id']}"}
        
        if product.stock < item["quantity"]:
            return {"error": f"재고 부족: {product.name}"}
        
        return {
            "product_id": product.product_id,
            "product_name": product.name,
            "price": product.price,
            "quantity": item["quantity"],
            "total_price": product.price * item["quantity"]
        }
    
    async def _send_order_confirmation(self, order: Order):
        """주문 확인 알림 발송"""
        await self.notification_service.send_email(
            f"user@example.com",  # 실제로는 사용자 이메일
            "주문 확인",
            f"주문 {order.order_id}이 성공적으로 처리되었습니다. 총 금액: ${order.total}"
        )


@UseCase(dependencies=["user_repository", "order_repository"])
class GetUserOrdersUseCase:
    def __init__(self, user_repository: UserRepository, order_repository: OrderRepository):
        self.user_repository = user_repository
        self.order_repository = order_repository
    
    @Cached(ttl=60)  # 1분 캐시
    @PerformanceMonitored("user_orders_query")
    async def execute(self, user_id: str) -> Result[List[dict], str]:
        """사용자 주문 목록 조회 - 반응형 스트림으로 처리"""
        
        # 사용자 존재 확인
        user_result = await self.user_repository.find_by_id(user_id)
        if user_result.is_failure():
            return user_result
        
        if not user_result.value:
            return Failure("사용자를 찾을 수 없습니다")
        
        # 주문 목록 조회 및 변환
        orders_result = await self.order_repository.find_by_user_id(user_id)
        if orders_result.is_failure():
            return orders_result
        
        # 반응형 스트림으로 주문 데이터 변환
        transformed_orders = await (
            Flux.from_iterable(orders_result.value)
            .map(self._transform_order)
            .sort(key=lambda order: order["created_at"], reverse=True)
            .collect_list()
        )
        
        return Success(transformed_orders)
    
    def _transform_order(self, order: Order) -> dict:
        """주문 데이터 변환"""
        return {
            "order_id": order.order_id,
            "status": order.status,
            "total": order.total,
            "items_count": len(order.items),
            "created_at": order.created_at.isoformat()
        }


# ================================================
# Controller 정의 (프레젠테이션 계층)
# ================================================

@Controller(route="/api/users", method="POST")
class UserController:
    def __init__(self, create_user_use_case: CreateUserUseCase):
        self.create_user_use_case = create_user_use_case
    
    @RequiresPermission("user:create")
    @SanitizeInput(["email", "name"])
    @RateLimited(max_calls=5, period=timedelta(minutes=1))
    async def create_user(self, request_data: dict) -> dict:
        result = await self.create_user_use_case.execute(request_data)
        
        if result.is_success():
            user = result.value
            return {
                "status": "success",
                "data": {
                    "user_id": user.user_id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                    "created_at": user.created_at.isoformat()
                }
            }
        else:
            return {
                "status": "error",
                "message": result.error
            }


@Controller(route="/api/orders", method="POST")
class OrderController:
    def __init__(self, create_order_use_case: CreateOrderUseCase, get_user_orders_use_case: GetUserOrdersUseCase):
        self.create_order_use_case = create_order_use_case
        self.get_user_orders_use_case = get_user_orders_use_case
    
    @RequiresAuthentication()
    @RequiresRole("user")
    @RateLimited(max_calls=10, period=timedelta(minutes=1))
    async def create_order(self, request_data: dict) -> dict:
        result = await self.create_order_use_case.execute(request_data)
        
        if result.is_success():
            order = result.value
            return {
                "status": "success",
                "data": {
                    "order_id": order.order_id,
                    "status": order.status,
                    "total": order.total,
                    "items": order.items
                }
            }
        else:
            return {
                "status": "error",
                "message": result.error
            }
    
    @RequiresAuthentication()
    async def get_user_orders(self, user_id: str) -> dict:
        result = await self.get_user_orders_use_case.execute(user_id)
        
        if result.is_success():
            return {
                "status": "success",
                "data": {
                    "orders": result.value
                }
            }
        else:
            return {
                "status": "error",
                "message": result.error
            }


# ================================================
# 애플리케이션 설정 및 실행
# ================================================

@Component(name="load_balancer", scope=ServiceScope.SINGLETON)
class ApplicationLoadBalancer:
    """애플리케이션 로드 밸런서"""
    
    def __init__(self):
        self.load_balancer = LoadBalancer(
            algorithm=LoadBalancingAlgorithm.CONSISTENT_HASH,
            health_check_enabled=True,
            health_check_interval=30
        )
        
        # 서비스 인스턴스 등록
        self.load_balancer.add_service("user-service", "http://user-service-1:8001", weight=1.0)
        self.load_balancer.add_service("user-service", "http://user-service-2:8002", weight=1.0)
        self.load_balancer.add_service("order-service", "http://order-service-1:8003", weight=1.5)
        self.load_balancer.add_service("order-service", "http://order-service-2:8004", weight=1.0)
    
    async def route_request(self, service_name: str, request_data: dict) -> Result[dict, str]:
        """요청을 적절한 서비스 인스턴스로 라우팅"""
        instance = await self.load_balancer.select_instance(service_name)
        if instance.is_failure():
            return instance
        
        # 실제로는 HTTP 클라이언트로 요청
        print(f"🔄 요청 라우팅: {service_name} -> {instance.value}")
        return Success({"routed_to": instance.value})


class EnterpriseApplication:
    """통합 엔터프라이즈 애플리케이션"""
    
    def __init__(self):
        self.registry = get_registry()
        self.rollback_manager = RollbackManager()
        self.deployment_manager = None
        
    async def initialize(self):
        """애플리케이션 초기화"""
        print("🚀 RFS Enterprise Application 초기화 중...")
        
        # 서비스 등록 완료 확인
        user_controller = self.registry.get("user_controller")
        order_controller = self.registry.get("order_controller")
        load_balancer = self.registry.get("load_balancer")
        
        print("✅ 모든 서비스 컴포넌트 등록 완료")
        
        # 배포 전략 설정
        deployment_config = DeploymentConfig(
            deployment_type=DeploymentType.BLUE_GREEN,
            health_check_interval=30,
            auto_rollback=True,
            rollback_on_error_rate=0.05
        )
        
        self.deployment_manager = DeploymentStrategyFactory.create(
            DeploymentType.BLUE_GREEN,
            deployment_config
        )
        
        print("✅ 배포 전략 설정 완료")
    
    async def deploy_new_version(self, version: str):
        """새 버전 배포"""
        print(f"📦 새 버전 배포 시작: {version}")
        
        # 1. 체크포인트 생성
        checkpoint_result = await self.rollback_manager.create_checkpoint(
            deployment_id=f"deploy_{version}",
            metadata={
                "version": version,
                "timestamp": datetime.now().isoformat(),
                "strategy": "blue_green"
            }
        )
        
        if checkpoint_result.is_failure():
            print(f"❌ 체크포인트 생성 실패: {checkpoint_result.error}")
            return
        
        # 2. Blue-Green 배포 실행
        deployment_result = await self.deployment_manager.deploy(
            service_name="enterprise-app",
            new_version=version
        )
        
        if deployment_result.is_success():
            print(f"✅ 배포 성공: {version}")
            metrics = deployment_result.value
            print(f"📊 배포 메트릭:")
            print(f"   - 소요 시간: {metrics.deployment_duration}")
            print(f"   - 성공률: {metrics.success_rate:.2%}")
        else:
            print(f"❌ 배포 실패: {deployment_result.error}")
            
            # 자동 롤백 실행
            print("🔄 자동 롤백 시작...")
            rollback_result = await self.rollback_manager.rollback_to_checkpoint(
                checkpoint_result.value,
                reason="deployment_failure"
            )
            
            if rollback_result.is_success():
                print("✅ 롤백 완료")
            else:
                print(f"❌ 롤백 실패: {rollback_result.error}")
    
    async def demonstrate_features(self):
        """주요 기능 데모"""
        print("\n🎯 RFS Framework 주요 기능 데모")
        print("=" * 50)
        
        # 1. 사용자 생성
        print("\n1. 사용자 생성 (Result Pattern + 검증 + 감사 로깅)")
        user_controller = self.registry.get("user_controller")
        
        user_result = await user_controller.create_user({
            "email": "john@example.com",
            "name": "John Doe",
            "role": "user"
        })
        
        print(f"사용자 생성 결과: {user_result['status']}")
        if user_result['status'] == 'success':
            print(f"생성된 사용자 ID: {user_result['data']['user_id']}")
        
        # 2. 주문 생성
        print("\n2. 주문 생성 (트랜잭션 + 반응형 스트림 + 서킷 브레이커)")
        order_controller = self.registry.get("order_controller")
        
        order_result = await order_controller.create_order({
            "user_id": user_result['data']['user_id'],
            "items": [
                {"product_id": "1", "quantity": 1},  # MacBook Pro
                {"product_id": "2", "quantity": 2}   # iPhone 15
            ],
            "payment_method": {
                "type": "credit_card",
                "card_number": "****-****-****-1234"
            }
        })
        
        print(f"주문 생성 결과: {order_result['status']}")
        if order_result['status'] == 'success':
            print(f"주문 ID: {order_result['data']['order_id']}")
            print(f"주문 총액: ${order_result['data']['total']}")
        
        # 3. 사용자 주문 목록 조회
        print("\n3. 사용자 주문 목록 조회 (캐싱 + 성능 모니터링)")
        
        orders_result = await order_controller.get_user_orders(user_result['data']['user_id'])
        print(f"주문 목록 조회 결과: {orders_result['status']}")
        if orders_result['status'] == 'success':
            print(f"주문 개수: {len(orders_result['data']['orders'])}")
        
        # 4. 로드 밸런싱
        print("\n4. 로드 밸런싱 데모")
        load_balancer = self.registry.get("load_balancer")
        
        for i in range(3):
            route_result = await load_balancer.route_request("user-service", {"request_id": i})
            if route_result.is_success():
                print(f"요청 {i}: {route_result.value['routed_to']}")
        
        # 5. 배포 데모
        print("\n5. Blue-Green 배포 데모")
        await self.deploy_new_version("v2.1.0")
        
        print("\n✅ 모든 기능 데모 완료!")


async def main():
    """메인 애플리케이션 실행"""
    app = EnterpriseApplication()
    
    try:
        # 애플리케이션 초기화
        await app.initialize()
        
        # 기능 데모 실행
        await app.demonstrate_features()
        
    except Exception as e:
        print(f"❌ 애플리케이션 오류: {e}")


if __name__ == "__main__":
    print("🏢 RFS Framework v4 - 통합 엔터프라이즈 애플리케이션 예제")
    print("=" * 60)
    print("이 예제는 다음 기능들을 통합하여 보여줍니다:")
    print("• Result Pattern과 함수형 에러 핸들링")
    print("• 헥사고날 아키텍처와 의존성 주입")
    print("• 보안 및 접근 제어 (RBAC/ABAC)")
    print("• 성능 모니터링 및 캐싱")
    print("• 감사 로깅과 트랜잭션 관리")
    print("• 반응형 프로그래밍 (Mono/Flux)")
    print("• 서킷 브레이커와 로드 밸런싱")
    print("• Blue-Green 배포와 롤백 관리")
    print("=" * 60)
    
    asyncio.run(main())