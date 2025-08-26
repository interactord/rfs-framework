# RFS Framework 기반 엔터프라이즈 서버 아키텍처 가이드

## 목차
1. [개요](#개요)
2. [핵심 원칙](#핵심-원칙)
3. [폴더 구조](#폴더-구조)
4. [레이어별 상세 설명](#레이어별-상세-설명)
5. [구현 예제](#구현-예제)
6. [배포 구조](#배포-구조)
7. [모범 사례](#모범-사례)

## 개요

RFS Framework를 기반으로 한 엔터프라이즈 서버는 함수형 프로그래밍, 반응형 스트림, 헥사고날 아키텍처를 핵심으로 하는 확장 가능한 마이크로서비스 아키텍처입니다.

### 아키텍처 특징
- **Result Pattern**: 명시적 에러 핸들링으로 예외 없는 시스템
- **Reactive Streams**: Mono/Flux 패턴으로 백프레셔 지원
- **Hexagonal Architecture**: 포트-어댑터 패턴으로 도메인 격리
- **Cloud Native**: Google Cloud Run 최적화 및 서버리스 지원
- **Type Safety**: 완전한 타입 힌트와 Pydantic 검증

## 핵심 원칙

### 1. Domain-Driven Design (DDD)
- 도메인 모델 중심의 설계
- Bounded Context로 서비스 분리
- Ubiquitous Language 사용

### 2. Clean Architecture
- 의존성 역전 원칙 (DIP)
- 레이어 간 단방향 의존성
- 인터페이스 분리 원칙 (ISP)

### 3. Functional Programming
- 불변성 (Immutability)
- 순수 함수 (Pure Functions)
- 모나드 패턴 (Result, Maybe, Either)

### 4. Reactive Programming
- 비동기 논블로킹 I/O
- 백프레셔 관리
- 이벤트 기반 아키텍처

## 폴더 구조

```
enterprise-server/
├── src/                          # 소스 코드 루트
│   ├── api/                     # API 레이어 (진입점)
│   │   ├── rest/                # REST API 엔드포인트
│   │   │   ├── v1/              # API 버전 관리
│   │   │   │   ├── controllers/ # HTTP 컨트롤러
│   │   │   │   ├── routes/      # 라우팅 정의
│   │   │   │   └── middleware/  # API 미들웨어
│   │   │   └── v2/
│   │   ├── graphql/             # GraphQL 엔드포인트
│   │   │   ├── schema/          # GraphQL 스키마
│   │   │   ├── resolvers/       # GraphQL 리졸버
│   │   │   └── dataloaders/     # DataLoader 구현
│   │   └── grpc/                # gRPC 서비스
│   │       ├── proto/           # Protocol Buffer 정의
│   │       └── services/        # gRPC 서비스 구현
│   │
│   ├── application/             # 애플리케이션 레이어
│   │   ├── use_cases/           # 비즈니스 유스케이스
│   │   │   ├── commands/        # Command 처리 (CQRS)
│   │   │   ├── queries/         # Query 처리 (CQRS)
│   │   │   └── sagas/           # Saga 패턴 구현
│   │   ├── services/            # 애플리케이션 서비스
│   │   ├── dto/                 # Data Transfer Objects
│   │   └── mappers/             # DTO-도메인 매핑
│   │
│   ├── domain/                  # 도메인 레이어 (핵심 비즈니스)
│   │   ├── models/              # 도메인 모델
│   │   │   ├── entities/        # 엔티티
│   │   │   ├── value_objects/   # 값 객체
│   │   │   └── aggregates/      # 애그리게이트
│   │   ├── repositories/        # 리포지토리 인터페이스
│   │   ├── services/            # 도메인 서비스
│   │   ├── events/              # 도메인 이벤트
│   │   └── specifications/      # 비즈니스 규칙 명세
│   │
│   ├── infrastructure/          # 인프라 레이어
│   │   ├── persistence/         # 데이터 영속성
│   │   │   ├── repositories/    # 리포지토리 구현
│   │   │   ├── migrations/      # DB 마이그레이션
│   │   │   ├── seeders/         # 시드 데이터
│   │   │   └── models/          # ORM 모델
│   │   ├── messaging/           # 메시징 시스템
│   │   │   ├── publishers/      # 이벤트 발행
│   │   │   ├── subscribers/     # 이벤트 구독
│   │   │   └── brokers/         # 메시지 브로커
│   │   ├── external/            # 외부 서비스 연동
│   │   │   ├── clients/         # HTTP/gRPC 클라이언트
│   │   │   ├── adapters/        # 외부 API 어댑터
│   │   │   └── webhooks/        # 웹훅 처리
│   │   ├── cache/               # 캐싱 레이어
│   │   │   ├── memory/          # 인메모리 캐시
│   │   │   └── distributed/     # 분산 캐시 (Redis)
│   │   └── monitoring/          # 모니터링 인프라
│   │       ├── metrics/         # 메트릭 수집
│   │       ├── tracing/         # 분산 추적
│   │       └── logging/         # 로깅 설정
│   │
│   ├── shared/                  # 공유 모듈
│   │   ├── kernel/              # 공유 커널
│   │   │   ├── result/          # Result 패턴 구현
│   │   │   ├── monads/          # 모나드 구현
│   │   │   └── guards/          # Guard 절 구현
│   │   ├── exceptions/          # 커스텀 예외 (Result로 변환)
│   │   ├── constants/           # 상수 정의
│   │   ├── utils/               # 유틸리티 함수
│   │   └── types/               # 타입 정의
│   │
│   └── config/                  # 설정 관리
│       ├── environments/        # 환경별 설정
│       │   ├── development.py
│       │   ├── staging.py
│       │   └── production.py
│       ├── security/            # 보안 설정
│       │   ├── cors.py
│       │   ├── auth.py
│       │   └── rbac.py
│       └── dependencies.py      # 의존성 주입 설정
│
├── tests/                       # 테스트 코드
│   ├── unit/                    # 단위 테스트
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── integration/             # 통합 테스트
│   │   ├── api/
│   │   ├── persistence/
│   │   └── messaging/
│   ├── e2e/                     # End-to-End 테스트
│   │   ├── scenarios/
│   │   └── performance/
│   ├── fixtures/                # 테스트 픽스처
│   └── mocks/                   # 목 객체
│
├── scripts/                     # 운영 스크립트
│   ├── deployment/              # 배포 스크립트
│   │   ├── docker/
│   │   ├── kubernetes/
│   │   └── cloud_run/
│   ├── migration/               # 마이그레이션 스크립트
│   ├── monitoring/              # 모니터링 스크립트
│   └── backup/                  # 백업 스크립트
│
├── docs/                        # 문서화
│   ├── api/                     # API 문서
│   │   ├── openapi.yaml
│   │   └── postman/
│   ├── architecture/            # 아키텍처 문서
│   │   ├── adr/                # Architecture Decision Records
│   │   ├── diagrams/            # 아키텍처 다이어그램
│   │   └── patterns/            # 패턴 가이드
│   ├── development/             # 개발 가이드
│   └── operations/              # 운영 가이드
│
├── .github/                     # GitHub 설정
│   ├── workflows/               # GitHub Actions
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── docker/                      # Docker 설정
│   ├── Dockerfile.dev
│   ├── Dockerfile.prod
│   └── docker-compose.yaml
│
├── kubernetes/                  # Kubernetes 매니페스트
│   ├── base/
│   ├── overlays/
│   └── kustomization.yaml
│
├── terraform/                   # Infrastructure as Code
│   ├── modules/
│   ├── environments/
│   └── main.tf
│
├── .env.example                 # 환경 변수 예제
├── .gitignore
├── pyproject.toml              # Python 프로젝트 설정
├── poetry.lock                 # 의존성 잠금 파일
├── Makefile                    # 빌드 자동화
└── README.md

```

## 레이어별 상세 설명

### 1. API 레이어 (`src/api/`)

진입점 역할을 하며 HTTP, GraphQL, gRPC 등 다양한 프로토콜 지원

```python
# src/api/rest/v1/controllers/user_controller.py
from rfs.core import Result, Controller
from rfs.security import RequiresAuthentication
from rfs.monitoring import PerformanceMonitored

@Controller("/api/v1/users")
class UserController:
    def __init__(self, user_service: UserService):
        self._service = user_service
    
    @RequiresAuthentication
    @PerformanceMonitored
    async def get_user(self, user_id: str) -> Result[UserDTO, APIError]:
        return await self._service.get_user(user_id)
```

### 2. Application 레이어 (`src/application/`)

비즈니스 유스케이스를 조율하는 레이어

```python
# src/application/use_cases/commands/create_order_command.py
from rfs.core import Result, UseCase
from rfs.reactive import Mono

@UseCase
class CreateOrderCommand:
    def __init__(self, 
                 order_repo: OrderRepository,
                 payment_service: PaymentService,
                 notification_service: NotificationService):
        self._order_repo = order_repo
        self._payment_service = payment_service
        self._notification_service = notification_service
    
    async def execute(self, request: CreateOrderRequest) -> Result[OrderResponse, str]:
        return await (
            Mono.from_result(self._validate_request(request))
            .flat_map(lambda r: self._process_payment(r))
            .flat_map(lambda r: self._create_order(r))
            .flat_map(lambda r: self._send_notification(r))
            .to_result()
        )
```

### 3. Domain 레이어 (`src/domain/`)

핵심 비즈니스 로직과 규칙을 포함

```python
# src/domain/models/aggregates/order_aggregate.py
from rfs.core import Result
from typing import List

class OrderAggregate:
    def __init__(self, order_id: str, customer_id: str):
        self._order_id = order_id
        self._customer_id = customer_id
        self._items: List[OrderItem] = []
        self._status = OrderStatus.PENDING
        self._domain_events = []
    
    def add_item(self, product: Product, quantity: int) -> Result[None, str]:
        if quantity <= 0:
            return Failure("Quantity must be positive")
        
        if not product.is_available(quantity):
            return Failure(f"Insufficient stock for {product.name}")
        
        self._items.append(OrderItem(product, quantity))
        self._domain_events.append(
            OrderItemAdded(self._order_id, product.id, quantity)
        )
        return Success(None)
```

### 4. Infrastructure 레이어 (`src/infrastructure/`)

외부 시스템과의 통합을 담당

```python
# src/infrastructure/persistence/repositories/order_repository_impl.py
from rfs.core import Result, Adapter
from rfs.database import transactional

@Adapter(implements=OrderRepository)
class OrderRepositoryImpl:
    def __init__(self, session_factory: SessionFactory):
        self._session_factory = session_factory
    
    @transactional
    async def save(self, order: OrderAggregate) -> Result[str, str]:
        async with self._session_factory.create() as session:
            try:
                db_order = self._to_db_model(order)
                session.add(db_order)
                await session.commit()
                return Success(db_order.id)
            except Exception as e:
                return Failure(f"Failed to save order: {str(e)}")
```

## 구현 예제

### 완전한 유스케이스 구현

```python
# src/application/use_cases/commands/process_payment_command.py
from rfs.core import Result, UseCase, transactional
from rfs.reactive import Flux, Mono
from rfs.service_discovery import CircuitBreaker
from rfs.monitoring import PerformanceMonitored
from rfs.security import RequiresRole

@UseCase
class ProcessPaymentCommand:
    def __init__(self,
                 payment_gateway: PaymentGateway,
                 order_repository: OrderRepository,
                 audit_service: AuditService,
                 circuit_breaker: CircuitBreaker):
        self._payment_gateway = payment_gateway
        self._order_repository = order_repository
        self._audit_service = audit_service
        self._circuit_breaker = circuit_breaker
    
    @RequiresRole("PAYMENT_PROCESSOR")
    @PerformanceMonitored(threshold_ms=1000)
    @transactional
    async def execute(self, payment_request: PaymentRequest) -> Result[PaymentResponse, str]:
        # 1. 주문 조회
        order_result = await self._order_repository.find_by_id(payment_request.order_id)
        if order_result.is_failure():
            return order_result
        
        order = order_result.value
        
        # 2. 결제 검증
        validation_result = self._validate_payment(order, payment_request)
        if validation_result.is_failure():
            await self._audit_service.log_failed_payment(payment_request, validation_result.error)
            return validation_result
        
        # 3. 외부 결제 게이트웨이 호출 (서킷 브레이커 적용)
        payment_result = await self._circuit_breaker.call(
            lambda: self._payment_gateway.process(payment_request)
        )
        
        if payment_result.is_success():
            # 4. 주문 상태 업데이트
            order.mark_as_paid(payment_result.value.transaction_id)
            await self._order_repository.save(order)
            
            # 5. 감사 로그
            await self._audit_service.log_successful_payment(payment_request, payment_result.value)
            
            return Success(PaymentResponse(
                order_id=order.id,
                transaction_id=payment_result.value.transaction_id,
                status="SUCCESS"
            ))
        
        return Failure(f"Payment failed: {payment_result.error}")
    
    def _validate_payment(self, order: Order, request: PaymentRequest) -> Result[None, str]:
        if order.is_paid():
            return Failure("Order already paid")
        
        if request.amount != order.total_amount:
            return Failure("Payment amount mismatch")
        
        if order.is_expired():
            return Failure("Order has expired")
        
        return Success(None)
```

### 반응형 스트림 처리

```python
# src/application/services/order_processing_service.py
from rfs.reactive import Flux, Mono
from rfs.core import Result

class OrderProcessingService:
    def __init__(self,
                 order_repository: OrderRepository,
                 inventory_service: InventoryService,
                 shipping_service: ShippingService):
        self._order_repository = order_repository
        self._inventory_service = inventory_service
        self._shipping_service = shipping_service
    
    async def process_bulk_orders(self, order_ids: List[str]) -> Result[List[ProcessedOrder], str]:
        return await (
            Flux.from_iterable(order_ids)
            .parallel(workers=4)  # 병렬 처리
            .flat_map(lambda id: self._process_single_order(id))
            .filter(lambda result: result.is_success())  # 성공한 주문만 필터링
            .map(lambda result: result.value)
            .collect_list()
            .map(lambda orders: Success(orders))
            .on_error_return(lambda e: Failure(str(e)))
            .to_result()
        )
    
    async def _process_single_order(self, order_id: str) -> Mono[Result[ProcessedOrder, str]]:
        return (
            Mono.from_coroutine(self._order_repository.find_by_id(order_id))
            .flat_map(lambda order: self._check_inventory(order))
            .flat_map(lambda order: self._allocate_shipping(order))
            .map(lambda order: Success(ProcessedOrder.from_order(order)))
            .on_error_return(lambda e: Failure(f"Failed to process order {order_id}: {str(e)}"))
        )
```

## 배포 구조

### Docker 컨테이너화

```dockerfile
# docker/Dockerfile.prod
FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/
COPY config/ ./config/

ENV RFS_ENV=production
ENV PORT=8080

CMD ["python", "-m", "src.main"]
```

### Kubernetes 배포

```yaml
# kubernetes/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: enterprise-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: enterprise-server
  template:
    metadata:
      labels:
        app: enterprise-server
    spec:
      containers:
      - name: app
        image: gcr.io/project/enterprise-server:latest
        ports:
        - containerPort: 8080
        env:
        - name: RFS_ENV
          value: production
        - name: DB_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: connection-string
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
```

### Google Cloud Run 배포

```yaml
# scripts/deployment/cloud_run/service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: enterprise-server
  annotations:
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "100"
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 100
      timeoutSeconds: 300
      containers:
      - image: gcr.io/project/enterprise-server:latest
        resources:
          limits:
            cpu: "2"
            memory: "2Gi"
        env:
        - name: RFS_ENV
          value: cloud_run
```

## 모범 사례

### 1. Result Pattern 활용

```python
# ✅ Good - Result Pattern 사용
async def get_user(self, user_id: str) -> Result[User, str]:
    user = await self._repository.find_by_id(user_id)
    if not user:
        return Failure(f"User {user_id} not found")
    return Success(user)

# ❌ Bad - 예외 발생
async def get_user(self, user_id: str) -> User:
    user = await self._repository.find_by_id(user_id)
    if not user:
        raise UserNotFoundException(f"User {user_id} not found")
    return user
```

### 2. 의존성 주입

```python
# ✅ Good - 의존성 주입 사용
@UseCase
class CreateUserUseCase:
    def __init__(self, 
                 user_repository: UserRepository,
                 email_service: EmailService):
        self._user_repository = user_repository
        self._email_service = email_service

# ❌ Bad - 직접 인스턴스 생성
class CreateUserUseCase:
    def __init__(self):
        self._user_repository = UserRepositoryImpl()  # 직접 생성
        self._email_service = EmailServiceImpl()      # 직접 생성
```

### 3. 레이어 분리

```python
# ✅ Good - 도메인 로직이 도메인 레이어에 있음
# src/domain/models/user.py
class User:
    def change_email(self, new_email: str) -> Result[None, str]:
        if not self._is_valid_email(new_email):
            return Failure("Invalid email format")
        self.email = new_email
        return Success(None)

# ❌ Bad - 도메인 로직이 컨트롤러에 있음
# src/api/controllers/user_controller.py
class UserController:
    def change_email(self, user_id: str, new_email: str):
        if "@" not in new_email:  # 도메인 로직이 컨트롤러에
            return BadRequest("Invalid email")
        # ...
```

### 4. 테스트 구조

```python
# tests/unit/domain/test_order_aggregate.py
import pytest
from src.domain.models.aggregates import OrderAggregate

class TestOrderAggregate:
    def test_add_item_with_sufficient_stock(self):
        # Given
        order = OrderAggregate("order-1", "customer-1")
        product = Product("product-1", "Test Product", 100.0, stock=10)
        
        # When
        result = order.add_item(product, quantity=5)
        
        # Then
        assert result.is_success()
        assert len(order.items) == 1
        assert order.items[0].quantity == 5
```

## 프로젝트 초기 설정

### 1. 프로젝트 생성

```bash
# Poetry를 사용한 프로젝트 초기화
poetry new enterprise-server
cd enterprise-server

# RFS Framework 설치
poetry add rfs-framework

# 개발 의존성 설치
poetry add --dev pytest pytest-asyncio pytest-cov black isort mypy
```

### 2. 환경 설정

```python
# src/config/environments/development.py
from rfs.core import RFSConfig, Environment

class DevelopmentConfig(RFSConfig):
    environment = Environment.DEVELOPMENT
    debug = True
    
    # Database
    db_url = "postgresql://localhost/enterprise_dev"
    db_pool_size = 5
    
    # Redis
    redis_url = "redis://localhost:6379"
    
    # Security
    jwt_secret = "dev-secret-key"
    cors_origins = ["http://localhost:3000"]
```

### 3. 메인 애플리케이션

```python
# src/main.py
from rfs.web import create_app
from src.config import get_config
from src.api import create_api_router
from src.infrastructure import setup_infrastructure

async def main():
    config = get_config()
    
    # 인프라 설정
    await setup_infrastructure(config)
    
    # API 라우터 생성
    router = create_api_router()
    
    # 애플리케이션 생성 및 실행
    app = create_app(config, router)
    await app.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## 참고 자료

- [RFS Framework 문서](https://github.com/yourusername/rfs-framework)
- [헥사고날 아키텍처](https://alistair.cockburn.us/hexagonal-architecture/)
- [Domain-Driven Design](https://dddcommunity.org/)
- [Reactive Streams](https://www.reactive-streams.org/)
- [Google Cloud Run 베스트 프랙티스](https://cloud.google.com/run/docs/best-practices)