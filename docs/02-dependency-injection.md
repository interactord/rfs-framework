# 의존성 주입 (Dependency Injection)

## 📌 개요

RFS Framework는 헥사고날 아키텍처를 지원하는 강력한 어노테이션 기반 의존성 주입 시스템을 제공합니다. 이를 통해 느슨한 결합과 높은 응집도를 가진 클린 아키텍처를 구현할 수 있습니다.

## 🎯 핵심 개념

### 헥사고날 아키텍처
- **Port**: 비즈니스 로직의 인터페이스 (추상화)
- **Adapter**: Port의 구체적인 구현
- **UseCase**: 비즈니스 로직 (Application Service)
- **Controller**: 프레젠테이션 계층

### 서비스 생명주기
- **Singleton**: 애플리케이션 전체에서 하나의 인스턴스
- **Prototype**: 요청마다 새로운 인스턴스
- **Request**: HTTP 요청당 하나의 인스턴스

## 📚 API 레퍼런스

### 주요 데코레이터

| 데코레이터 | 용도 | 계층 |
|-----------|------|------|
| `@Port` | 도메인 인터페이스 정의 | Domain |
| `@Adapter` | Port 구현체 | Infrastructure |
| `@UseCase` | 비즈니스 로직 | Application |
| `@Controller` | HTTP 엔드포인트 | Presentation |
| `@Component` | 일반 컴포넌트 | Any |
| `@inject` | 의존성 주입 | Any |

## 💡 사용 예제

### 기본 의존성 주입

```python
from rfs.core.annotations import Component, inject
from rfs.core.registry import ServiceScope

@Component(name="logger", scope=ServiceScope.SINGLETON)
class Logger:
    def log(self, message: str):
        print(f"[LOG] {message}")

@Component(name="user_service")
class UserService:
    @inject
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def create_user(self, name: str):
        self.logger.log(f"Creating user: {name}")
        return {"id": "1", "name": name}

# 사용
from rfs.core.registry import get_registry

registry = get_registry()
user_service = registry.get("user_service")
user_service.create_user("김철수")
```

### 헥사고날 아키텍처 구현

```python
from abc import ABC, abstractmethod
from rfs.core.annotations import Port, Adapter, UseCase, Controller
from rfs.core.registry import ServiceScope
from rfs.core.result import Result, Success, Failure

# 1. Port 정의 (도메인 계층)
@Port(name="user_repository")
class UserRepository(ABC):
    """사용자 저장소 인터페이스"""
    
    @abstractmethod
    async def find_by_id(self, user_id: str) -> Result[dict, str]:
        pass
    
    @abstractmethod
    async def save(self, user: dict) -> Result[dict, str]:
        pass
    
    @abstractmethod
    async def delete(self, user_id: str) -> Result[bool, str]:
        pass

# 2. Adapter 구현 (인프라 계층)
@Adapter(port="user_repository", scope=ServiceScope.SINGLETON)
class PostgresUserRepository(UserRepository):
    """PostgreSQL 사용자 저장소 구현"""
    
    def __init__(self):
        # 실제로는 DB 연결 설정
        self.db = {}  # 시뮬레이션용
    
    async def find_by_id(self, user_id: str) -> Result[dict, str]:
        user = self.db.get(user_id)
        if user:
            return Success(user)
        return Failure(f"사용자를 찾을 수 없습니다: {user_id}")
    
    async def save(self, user: dict) -> Result[dict, str]:
        self.db[user["id"]] = user
        return Success(user)
    
    async def delete(self, user_id: str) -> Result[bool, str]:
        if user_id in self.db:
            del self.db[user_id]
            return Success(True)
        return Failure(f"삭제할 사용자를 찾을 수 없습니다: {user_id}")

# 3. UseCase 정의 (애플리케이션 계층)
@UseCase(dependencies=["user_repository", "email_service"])
class CreateUserUseCase:
    """사용자 생성 유스케이스"""
    
    def __init__(self, user_repository: UserRepository, email_service):
        self.user_repository = user_repository
        self.email_service = email_service
    
    async def execute(self, user_data: dict) -> Result[dict, str]:
        # 비즈니스 로직
        if not user_data.get("email"):
            return Failure("이메일은 필수입니다")
        
        # 사용자 저장
        user = {
            "id": self._generate_id(),
            **user_data
        }
        
        result = await self.user_repository.save(user)
        
        if result.is_success():
            # 이메일 발송
            await self.email_service.send_welcome_email(user["email"])
        
        return result
    
    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

# 4. Controller 정의 (프레젠테이션 계층)
@Controller(route="/users", method="POST")
class UserController:
    """사용자 API 컨트롤러"""
    
    def __init__(self, create_user_use_case: CreateUserUseCase):
        self.create_user_use_case = create_user_use_case
    
    async def create_user(self, request_data: dict) -> dict:
        result = await self.create_user_use_case.execute(request_data)
        
        if result.is_success():
            return {
                "status": "success",
                "data": result.unwrap()
            }
        else:
            return {
                "status": "error",
                "message": result.error
            }
```

### 프로파일 기반 설정

```python
from rfs.core.annotations import Adapter, Component
from rfs.core.registry import ServiceScope

# 개발 환경용 어댑터
@Adapter(
    port="payment_gateway",
    scope=ServiceScope.SINGLETON,
    profile="development"
)
class MockPaymentGateway:
    async def process_payment(self, amount: float) -> Result:
        print(f"[MOCK] Processing payment: ${amount}")
        return Success({"transaction_id": "mock_123"})

# 프로덕션 환경용 어댑터
@Adapter(
    port="payment_gateway",
    scope=ServiceScope.SINGLETON,
    profile="production"
)
class StripePaymentGateway:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def process_payment(self, amount: float) -> Result:
        # 실제 Stripe API 호출
        return Success({"transaction_id": "stripe_abc"})

# 환경에 따라 자동으로 올바른 구현체 선택
import os
os.environ["PROFILE"] = "development"  # 또는 "production"
```

### 고급 의존성 주입 패턴

```python
from rfs.core.annotations import Component, inject
from typing import List

# 1. 팩토리 패턴
@Component(name="database_factory")
class DatabaseFactory:
    def create_connection(self, db_type: str):
        if db_type == "postgres":
            return PostgresConnection()
        elif db_type == "mongodb":
            return MongoConnection()
        else:
            raise ValueError(f"Unknown database type: {db_type}")

# 2. 데코레이터 패턴
@Component(name="cached_user_service")
class CachedUserService:
    @inject
    def __init__(self, user_service: UserService, cache_service):
        self.user_service = user_service
        self.cache = cache_service
    
    async def get_user(self, user_id: str) -> Result:
        # 캐시 확인
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return Success(cached)
        
        # 캐시 미스 시 실제 서비스 호출
        result = await self.user_service.get_user(user_id)
        if result.is_success():
            await self.cache.set(f"user:{user_id}", result.value)
        
        return result

# 3. 다중 의존성 주입
@Component(name="notification_service")
class NotificationService:
    @inject
    def __init__(
        self,
        email_service,
        sms_service,
        push_service,
        user_preference_service
    ):
        self.email = email_service
        self.sms = sms_service
        self.push = push_service
        self.preferences = user_preference_service
    
    async def notify(self, user_id: str, message: str):
        prefs = await self.preferences.get(user_id)
        
        tasks = []
        if prefs.email_enabled:
            tasks.append(self.email.send(user_id, message))
        if prefs.sms_enabled:
            tasks.append(self.sms.send(user_id, message))
        if prefs.push_enabled:
            tasks.append(self.push.send(user_id, message))
        
        await asyncio.gather(*tasks)
```

### 순환 의존성 해결

```python
from rfs.core.annotations import Component, inject
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service_b import ServiceB

@Component(name="service_a")
class ServiceA:
    def __init__(self):
        self._service_b = None
    
    @property
    def service_b(self) -> 'ServiceB':
        if not self._service_b:
            from rfs.core.registry import get_registry
            self._service_b = get_registry().get("service_b")
        return self._service_b
    
    def do_something(self):
        return "A"
```

### 조건부 의존성 주입

```python
from rfs.core.annotations import Component
from rfs.core.registry import ConditionalRegistration

@Component(
    name="feature_service",
    condition=lambda: os.getenv("FEATURE_ENABLED") == "true"
)
class FeatureService:
    """특정 기능이 활성화된 경우에만 등록"""
    pass

# 또는 프로그래밍 방식으로
registry = get_registry()

if config.is_premium_tier:
    registry.register(
        "premium_service",
        PremiumService,
        scope=ServiceScope.SINGLETON
    )
```

## 🎨 베스트 프랙티스

### 1. 인터페이스 분리 원칙 (ISP)

```python
# ❌ 나쁜 예 - 너무 큰 인터페이스
@Port(name="user_service")
class UserService(ABC):
    @abstractmethod
    def create_user(self, data): pass
    @abstractmethod
    def delete_user(self, id): pass
    @abstractmethod
    def send_email(self, user): pass  # SRP 위반
    @abstractmethod
    def generate_report(self): pass  # 관련 없는 기능

# ✅ 좋은 예 - 분리된 인터페이스
@Port(name="user_repository")
class UserRepository(ABC):
    @abstractmethod
    def create(self, data): pass
    @abstractmethod
    def delete(self, id): pass

@Port(name="email_service")
class EmailService(ABC):
    @abstractmethod
    def send(self, to, subject, body): pass
```

### 2. 의존성 역전 원칙 (DIP)

```python
# ✅ 좋은 예 - 추상화에 의존
@UseCase(dependencies=["user_repository"])  # Port에 의존
class GetUserUseCase:
    def __init__(self, user_repository: UserRepository):  # 인터페이스
        self.repo = user_repository
```

### 3. 테스트 용이성

```python
# 테스트용 Mock Adapter
@Adapter(port="user_repository", profile="test")
class MockUserRepository(UserRepository):
    def __init__(self):
        self.users = {}
    
    async def find_by_id(self, user_id: str) -> Result:
        return Success(self.users.get(user_id))

# 테스트
async def test_create_user():
    registry = get_registry()
    registry.set_profile("test")
    
    use_case = registry.get("create_user_use_case")
    result = await use_case.execute({"name": "테스트"})
    
    assert result.is_success()
```

## ⚠️ 주의사항

### 1. 순환 의존성
- 순환 의존성 발생 시 지연 로딩 사용
- 가능하면 설계를 재검토하여 순환 의존성 제거

### 2. 스코프 관리
- Singleton은 상태를 가지지 않도록 주의
- Request 스코프는 웹 컨텍스트에서만 사용

### 3. 메모리 누수
- 이벤트 리스너 등록 시 적절한 해제
- 큰 객체는 WeakRef 사용 고려

## 🔗 관련 문서
- [핵심 패턴](./01-core-patterns.md)
- [설정 관리](./03-configuration.md)
- [트랜잭션](./04-transactions.md)