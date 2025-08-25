# Registry API

Registry and dependency injection API documentation for RFS Framework.

**주요 클래스:**
- `Registry`: 기본 레지스트리 클래스
- `ServiceRegistry`: 서비스 레지스트리
- `DependencyInjector`: 의존성 주입기

## 사용 예제

### 기본 레지스트리 사용

```python
from rfs.core.registry import Registry
from abc import ABC, abstractmethod

# 인터페이스 정의
class Repository(ABC):
    @abstractmethod
    def save(self, entity): ...
    
    @abstractmethod
    def find_by_id(self, id: str): ...

class UserRepository(Repository):
    def __init__(self, db_connection):
        self.db = db_connection
    
    def save(self, user):
        return self.db.insert("users", user)
    
    def find_by_id(self, user_id: str):
        return self.db.query("users", {"id": user_id})

# 레지스트리 등록
registry = Registry()

# 서비스 등록
registry.register("user_repository", UserRepository)
registry.register("database", DatabaseConnection)

# 의존성 주입
@registry.inject("user_repository")
def create_user(user_data, user_repo: UserRepository):
    return user_repo.save(user_data)

# 사용
user = create_user({"name": "John", "email": "john@example.com"})
```

### 서비스 레지스트리

```python
from rfs.core.registry import ServiceRegistry
from rfs.core.annotations import Service, Inject
from typing import Protocol

class NotificationService(Protocol):
    def send(self, message: str, recipient: str) -> bool: ...

@Service("email_service")
class EmailService:
    def __init__(self, smtp_host: str = "localhost"):
        self.smtp_host = smtp_host
    
    def send(self, message: str, recipient: str) -> bool:
        print(f"Sending email to {recipient}: {message}")
        return True

@Service("sms_service") 
class SMSService:
    def send(self, message: str, recipient: str) -> bool:
        print(f"Sending SMS to {recipient}: {message}")
        return True

@Service("user_service")
class UserService:
    def __init__(self, 
                 email_service: NotificationService = Inject("email_service"),
                 sms_service: NotificationService = Inject("sms_service")):
        self.email_service = email_service
        self.sms_service = sms_service
    
    def register_user(self, email: str, phone: str):
        # 사용자 등록 로직
        print(f"Registering user: {email}")
        
        # 알림 서비스 사용
        self.email_service.send("Welcome!", email)
        self.sms_service.send("Welcome!", phone)

# 서비스 레지스트리 생성 및 사용
registry = ServiceRegistry()
registry.auto_discover("app.services")  # 서비스 자동 발견

# 서비스 인스턴스 가져오기
user_service = registry.get("user_service")
user_service.register_user("user@example.com", "+1234567890")
```

### 스코프와 라이프사이클 관리

```python
from rfs.core.registry import Registry, Scope
from enum import Enum

class ServiceScope(Enum):
    SINGLETON = "singleton"
    SCOPED = "scoped" 
    TRANSIENT = "transient"

@Service("cache_service", scope=ServiceScope.SINGLETON)
class CacheService:
    def __init__(self):
        self.cache = {}
    
    def get(self, key: str):
        return self.cache.get(key)
    
    def set(self, key: str, value):
        self.cache[key] = value

@Service("request_service", scope=ServiceScope.SCOPED)
class RequestService:
    def __init__(self):
        self.request_id = generate_request_id()
    
    def get_request_id(self):
        return self.request_id

@Service("logger", scope=ServiceScope.TRANSIENT)
class Logger:
    def __init__(self, name: str = None):
        self.name = name or "default"
    
    def info(self, message: str):
        print(f"[{self.name}] INFO: {message}")

# 스코프별 인스턴스 관리
registry = ServiceRegistry()

# 싱글톤: 항상 같은 인스턴스
cache1 = registry.get("cache_service")
cache2 = registry.get("cache_service")
assert cache1 is cache2

# 스코프드: 스코프 내에서 같은 인스턴스
with registry.create_scope() as scope:
    req1 = scope.get("request_service")
    req2 = scope.get("request_service")
    assert req1 is req2
    assert req1.get_request_id() == req2.get_request_id()

# 트랜지언트: 항상 새로운 인스턴스
logger1 = registry.get("logger")
logger2 = registry.get("logger")
assert logger1 is not logger2
```

### 설정 기반 의존성 주입

```python
from rfs.core.registry import ConfigurableRegistry
from rfs.core.config import Config

class ServiceConfig(Config):
    database_url: str
    cache_ttl: int = 3600
    notification_providers: List[str] = ["email", "sms"]

@Service("data_service")
class DataService:
    def __init__(self, 
                 db_url: str = Inject("config.database_url"),
                 cache_ttl: int = Inject("config.cache_ttl")):
        self.db_url = db_url
        self.cache_ttl = cache_ttl

# 설정 기반 레지스트리
config = ServiceConfig(
    database_url="postgresql://localhost/mydb",
    cache_ttl=7200
)

registry = ConfigurableRegistry(config)
data_service = registry.get("data_service")

print(f"Database URL: {data_service.db_url}")
print(f"Cache TTL: {data_service.cache_ttl}")
```

### 조건부 등록과 프로파일

```python
from rfs.core.registry import ConditionalRegistry
from rfs.core.annotations import Profile, ConditionalOnProperty

@Service("dev_database")
@Profile("development")
class DevDatabaseService:
    def connect(self):
        return "Connected to development database"

@Service("prod_database") 
@Profile("production")
class ProdDatabaseService:
    def connect(self):
        return "Connected to production database"

@Service("feature_service")
@ConditionalOnProperty("features.advanced", having_value="true")
class AdvancedFeatureService:
    def process(self):
        return "Processing with advanced features"

# 프로파일 기반 레지스트리
registry = ConditionalRegistry(active_profiles=["development"])

# 개발 프로파일에서만 등록됨
dev_db = registry.get("dev_database")  # 성공
try:
    prod_db = registry.get("prod_database")  # 실패
except ServiceNotFoundError:
    print("Production database not available in dev profile")

# 속성 기반 조건부 등록
registry.set_property("features.advanced", "true")
feature_service = registry.get("feature_service")  # 성공
```

## 관련 문서

- [의존성 주입](../../02-dependency-injection.md) - DI 패턴 상세 설명
- [설정 관리](../../03-configuration.md) - 설정 연동
- [Core 어노테이션](../../core/annotations.md) - 서비스 어노테이션