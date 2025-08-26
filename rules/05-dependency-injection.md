# 의존성 주입 (Dependency Injection) 가이드

## 개요

RFS Framework는 함수형 프로그래밍 원칙에 따라 불변성을 유지하면서 의존성을 관리합니다. Registry 기반 DI 시스템을 통해 서비스 생명주기를 관리하고, 순환 의존성을 방지합니다.

## 핵심 원칙

1. **불변 레지스트리**: 서비스 등록 시 새로운 레지스트리 반환
2. **명시적 의존성**: 생성자 주입으로 의존성 명확화
3. **인터페이스 의존**: 구현체가 아닌 프로토콜/추상 클래스 의존
4. **순환 의존성 방지**: 자동 감지 및 방지

## 서비스 스코프

### 1. SINGLETON (싱글톤)

애플리케이션 생명주기 동안 단일 인스턴스:

```python
from rfs.core.registry import ServiceRegistry, ServiceScope

registry = ServiceRegistry()

# 싱글톤 서비스 등록
registry.register(
    name="database",
    service_class=DatabaseConnection,
    scope=ServiceScope.SINGLETON
)

# 같은 인스턴스 반환
db1 = registry.get("database")
db2 = registry.get("database")
assert db1 is db2  # True
```

### 2. PROTOTYPE (프로토타입)

요청할 때마다 새 인스턴스 생성:

```python
registry.register(
    name="request_handler",
    service_class=RequestHandler,
    scope=ServiceScope.PROTOTYPE
)

# 매번 새 인스턴스
handler1 = registry.get("request_handler")
handler2 = registry.get("request_handler")
assert handler1 is not handler2  # True
```

### 3. REQUEST (요청 스코프)

HTTP 요청 단위로 인스턴스 관리:

```python
registry.register(
    name="request_context",
    service_class=RequestContext,
    scope=ServiceScope.REQUEST
)

# 동일 요청 내에서는 같은 인스턴스
# 다른 요청에서는 다른 인스턴스
```

## 함수형 레지스트리 패턴

### 불변 업데이트

```python
# ❌ 잘못된 방법 - 직접 수정
registry._definitions["service"] = definition

# ✅ 올바른 방법 - 새 딕셔너리 생성
self._definitions = {**self._definitions, name: definition}
```

### 패턴 매칭 활용

```python
def get(self, name: str) -> Any:
    """서비스 인스턴스 가져오기"""
    if name not in self._definitions:
        raise ValueError(f"Service '{name}' not registered")
    
    definition = self._definitions[name]
    
    match definition.scope:
        case ServiceScope.SINGLETON:
            return self._get_singleton(name)
        case ServiceScope.PROTOTYPE:
            return self._create_instance(name)
        case ServiceScope.REQUEST:
            return self._get_request_scoped(name)
        case _:
            raise ValueError(f"Unknown scope: {definition.scope}")
```

## 의존성 선언

### 1. 생성자 주입

```python
from typing import Protocol

# 인터페이스 정의
class EmailService(Protocol):
    def send(self, to: str, subject: str, body: str) -> Result[None, str]:
        ...

class UserRepository(Protocol):
    def save(self, user: User) -> Result[User, str]:
        ...

# 서비스 구현
class UserService:
    """생성자 주입 패턴"""
    
    def __init__(
        self, 
        email_service: EmailService,
        user_repository: UserRepository
    ):
        self._email_service = email_service
        self._user_repository = user_repository
    
    def create_user(self, data: dict) -> Result[User, str]:
        return (
            validate_user_data(data)
            .bind(self._user_repository.save)
            .bind(self._send_welcome_email)
        )
    
    def _send_welcome_email(self, user: User) -> Result[User, str]:
        return self._email_service.send(
            user.email,
            "Welcome!",
            f"Hello {user.name}"
        ).map(lambda _: user)
```

### 2. 데코레이터 기반 주입

```python
from rfs.core.decorators import inject, Injected

@dataclass
class NotificationService:
    @inject
    def __init__(
        self, 
        email_service: EmailService = Injected,
        sms_service: SmsService = Injected,
        push_service: PushService = Injected
    ):
        self._email = email_service
        self._sms = sms_service
        self._push = push_service
    
    def notify(self, user: User, message: str) -> Result[None, str]:
        """모든 채널로 알림 발송"""
        return sequence([
            self._email.send(user.email, "Notification", message),
            self._sms.send(user.phone, message),
            self._push.send(user.device_id, message)
        ]).map(lambda _: None)
```

## 순환 의존성 방지

### 감지 메커니즘

```python
class ServiceRegistry:
    def __init__(self):
        self._definitions = {}
        self._instances = {}
        self._creating = set()  # 생성 중인 서비스 추적
    
    def _create_instance(self, name: str) -> Any:
        """순환 의존성 감지하며 인스턴스 생성"""
        if name in self._creating:
            raise ValueError(f"Circular dependency detected: {name}")
        
        self._creating.add(name)
        try:
            definition = self._definitions[name]
            dependencies = self._resolve_dependencies(definition.dependencies)
            instance = definition.service_class(**dependencies)
            return instance
        finally:
            self._creating.discard(name)
```

### 해결 방법

```python
# 1. 인터페이스 분리
class UserReader(Protocol):
    def find_user(self, id: str) -> Result[User, str]: ...

class UserWriter(Protocol):
    def save_user(self, user: User) -> Result[User, str]: ...

# 2. 지연 주입
class LazyService:
    def __init__(self, registry: ServiceRegistry):
        self._registry = registry
        self._service = None
    
    @property
    def service(self):
        if self._service is None:
            self._service = self._registry.get("dependent_service")
        return self._service

# 3. 이벤트 기반 분리
class OrderService:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
    
    def create_order(self, data: dict) -> Result[Order, str]:
        order = Order(**data)
        # UserService 직접 호출 대신 이벤트 발행
        self._event_bus.publish(OrderCreatedEvent(order))
        return Success(order)
```

## 고급 패턴

### 1. Factory 패턴

```python
from typing import Protocol, Type

class ServiceFactory(Protocol):
    """서비스 팩토리 인터페이스"""
    def create(self, config: dict) -> Any:
        ...

class DatabaseFactory:
    """데이터베이스 연결 팩토리"""
    
    def create(self, config: dict) -> DatabaseConnection:
        match config["type"]:
            case "postgres":
                return PostgresConnection(**config["params"])
            case "mysql":
                return MySQLConnection(**config["params"])
            case "sqlite":
                return SQLiteConnection(**config["params"])
            case _:
                raise ValueError(f"Unknown database type: {config['type']}")

# 팩토리 등록
registry.register(
    name="db_factory",
    service_class=DatabaseFactory,
    scope=ServiceScope.SINGLETON
)

# 사용
factory = registry.get("db_factory")
db = factory.create({"type": "postgres", "params": {...}})
```

### 2. Decorator 패턴

```python
class LoggingDecorator:
    """로깅 데코레이터"""
    
    def __init__(self, service: Any):
        self._service = service
    
    def __getattr__(self, name):
        """메서드 호출 위임 및 로깅"""
        attr = getattr(self._service, name)
        
        if callable(attr):
            def wrapper(*args, **kwargs):
                logger.info(f"Calling {name} with args={args}, kwargs={kwargs}")
                result = attr(*args, **kwargs)
                logger.info(f"Result: {result}")
                return result
            return wrapper
        
        return attr

# 데코레이터 적용
def create_logged_service(registry: ServiceRegistry, name: str) -> Any:
    service = registry.get(name)
    return LoggingDecorator(service)
```

### 3. Module 패턴

```python
@dataclass
class DatabaseModule:
    """데이터베이스 모듈"""
    
    def configure(self, registry: ServiceRegistry) -> ServiceRegistry:
        """모듈 구성"""
        return (
            registry
            .register("db_config", DatabaseConfig, ServiceScope.SINGLETON)
            .register("db_pool", ConnectionPool, ServiceScope.SINGLETON, ["db_config"])
            .register("user_repo", UserRepository, ServiceScope.SINGLETON, ["db_pool"])
            .register("order_repo", OrderRepository, ServiceScope.SINGLETON, ["db_pool"])
        )

@dataclass
class AuthModule:
    """인증 모듈"""
    
    def configure(self, registry: ServiceRegistry) -> ServiceRegistry:
        return (
            registry
            .register("jwt_service", JwtService, ServiceScope.SINGLETON)
            .register("auth_service", AuthService, ServiceScope.SINGLETON, ["jwt_service"])
        )

# 모듈 조합
def configure_application() -> ServiceRegistry:
    registry = ServiceRegistry()
    
    modules = [
        DatabaseModule(),
        AuthModule(),
        EmailModule(),
        CacheModule()
    ]
    
    for module in modules:
        registry = module.configure(registry)
    
    return registry
```

## 테스트 전략

### 1. 목 객체 주입

```python
from unittest.mock import Mock

def test_user_service():
    # 목 객체 생성
    mock_email = Mock(spec=EmailService)
    mock_email.send.return_value = Success(None)
    
    mock_repo = Mock(spec=UserRepository)
    mock_repo.save.return_value = Success(user)
    
    # 서비스 생성 (의존성 주입)
    service = UserService(mock_email, mock_repo)
    
    # 테스트 실행
    result = service.create_user({"name": "Test"})
    
    # 검증
    assert result.is_success()
    mock_email.send.assert_called_once()
    mock_repo.save.assert_called_once()
```

### 2. 테스트 레지스트리

```python
def create_test_registry() -> ServiceRegistry:
    """테스트용 레지스트리 생성"""
    registry = ServiceRegistry()
    
    # 테스트용 구현체 등록
    registry.register("email", MockEmailService, ServiceScope.PROTOTYPE)
    registry.register("database", InMemoryDatabase, ServiceScope.SINGLETON)
    
    return registry

def test_integration():
    registry = create_test_registry()
    service = registry.get("user_service")
    
    # 통합 테스트 실행
    result = service.create_user(test_data)
    assert result.is_success()
```

## 모범 사례

1. **인터페이스 우선**: 구현체가 아닌 Protocol/ABC에 의존
2. **명시적 의존성**: 생성자에 모든 의존성 명시
3. **불변 레지스트리**: 함수형 업데이트 패턴 사용
4. **스코프 적절히**: 상태 있으면 PROTOTYPE, 없으면 SINGLETON
5. **순환 방지**: 이벤트나 지연 로딩으로 순환 의존성 해결
6. **모듈화**: 관련 서비스를 모듈로 그룹화
7. **테스트 용이성**: 목 객체 쉽게 주입할 수 있는 구조