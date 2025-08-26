# 헥사고날 아키텍처 가이드

## 개요

헥사고날 아키텍처(Hexagonal Architecture) 또는 포트-어댑터 패턴은 비즈니스 로직을 외부 시스템으로부터 격리하여 테스트 가능하고 유지보수가 쉬운 시스템을 만드는 아키텍처 패턴입니다.

## 핵심 원칙

1. **도메인 중심**: 비즈니스 로직이 아키텍처의 중심
2. **의존성 역전**: 외부 시스템이 도메인에 의존, 도메인은 외부를 모름
3. **포트와 어댑터**: 명확한 경계와 인터페이스
4. **테스트 용이성**: 외부 의존성 없이 도메인 테스트 가능

## 레이어 구조

```
┌─────────────────────────────────────────────────┐
│                  Infrastructure                  │
│  (Adapters: DB, HTTP, Message Queue, File...)   │
├─────────────────────────────────────────────────┤
│                  Application                     │
│  (Use Cases, Application Services, DTOs)        │
├─────────────────────────────────────────────────┤
│                    Domain                        │
│  (Entities, Value Objects, Domain Services)     │
└─────────────────────────────────────────────────┘

의존성 방향: Infrastructure → Application → Domain
```

## 도메인 레이어

### 1. 엔티티 (Entities)

비즈니스 개념을 표현하는 핵심 객체:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from rfs.core.result import Result, Success, Failure

@dataclass(frozen=True)
class UserId:
    """값 객체: 사용자 ID"""
    value: str
    
    def __post_init__(self):
        if not self.value or len(self.value) < 3:
            raise ValueError("UserId must be at least 3 characters")

@dataclass(frozen=True)
class Email:
    """값 객체: 이메일"""
    value: str
    
    def __post_init__(self):
        if "@" not in self.value:
            raise ValueError("Invalid email format")

@dataclass(frozen=True)
class User:
    """도메인 엔티티: 사용자"""
    id: UserId
    email: Email
    name: str
    created_at: datetime
    verified: bool = False
    
    def verify(self) -> "User":
        """이메일 검증 - 새 인스턴스 반환"""
        return User(
            id=self.id,
            email=self.email,
            name=self.name,
            created_at=self.created_at,
            verified=True
        )
    
    def change_email(self, new_email: Email) -> Result["User", str]:
        """이메일 변경 - 비즈니스 규칙 적용"""
        if self.verified:
            return Failure("검증된 사용자의 이메일은 변경할 수 없습니다")
        
        return Success(User(
            id=self.id,
            email=new_email,
            name=self.name,
            created_at=self.created_at,
            verified=False
        ))
```

### 2. 도메인 서비스

엔티티에 속하지 않는 도메인 로직:

```python
from typing import Protocol

class PasswordHasher(Protocol):
    """패스워드 해싱 인터페이스 (포트)"""
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hash: str) -> bool: ...

class UserDomainService:
    """도메인 서비스: 사용자 관련 비즈니스 로직"""
    
    def __init__(self, hasher: PasswordHasher):
        self._hasher = hasher
    
    def create_user(
        self, 
        email: str, 
        password: str, 
        name: str
    ) -> Result[User, str]:
        """사용자 생성 비즈니스 로직"""
        
        # 이메일 검증
        try:
            email_vo = Email(email)
        except ValueError as e:
            return Failure(str(e))
        
        # 패스워드 검증
        if len(password) < 8:
            return Failure("패스워드는 8자 이상이어야 합니다")
        
        # 사용자 생성
        user = User(
            id=UserId(self._generate_id()),
            email=email_vo,
            name=name,
            created_at=datetime.now(),
            verified=False
        )
        
        return Success(user)
    
    def _generate_id(self) -> str:
        """ID 생성 로직"""
        import uuid
        return str(uuid.uuid4())
```

## 애플리케이션 레이어

### 1. 포트 정의 (Interfaces)

```python
from typing import Protocol, Optional
from abc import ABC, abstractmethod

# Inbound Port (외부에서 애플리케이션으로)
class CreateUserUseCase(Protocol):
    """사용자 생성 유스케이스 인터페이스"""
    
    def execute(self, request: CreateUserRequest) -> Result[UserDto, str]:
        ...

# Outbound Port (애플리케이션에서 외부로)
class UserRepository(Protocol):
    """사용자 저장소 인터페이스"""
    
    def save(self, user: User) -> Result[User, str]:
        ...
    
    def find_by_id(self, id: UserId) -> Result[Optional[User], str]:
        ...
    
    def find_by_email(self, email: Email) -> Result[Optional[User], str]:
        ...

class EventPublisher(Protocol):
    """이벤트 발행 인터페이스"""
    
    def publish(self, event: DomainEvent) -> Result[None, str]:
        ...
```

### 2. 유스케이스 구현

```python
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    """사용자 생성 요청 DTO"""
    email: str
    password: str
    name: str

@dataclass
class UserDto:
    """사용자 응답 DTO"""
    id: str
    email: str
    name: str
    verified: bool

class CreateUserUseCaseImpl:
    """사용자 생성 유스케이스 구현"""
    
    def __init__(
        self,
        user_service: UserDomainService,
        user_repository: UserRepository,
        event_publisher: EventPublisher,
        password_hasher: PasswordHasher
    ):
        self._user_service = user_service
        self._user_repository = user_repository
        self._event_publisher = event_publisher
        self._password_hasher = password_hasher
    
    def execute(self, request: CreateUserRequest) -> Result[UserDto, str]:
        """유스케이스 실행"""
        
        # 1. 도메인 서비스로 사용자 생성
        user_result = self._user_service.create_user(
            email=request.email,
            password=request.password,
            name=request.name
        )
        
        if user_result.is_failure():
            return Failure(user_result.unwrap_error())
        
        user = user_result.unwrap()
        
        # 2. 중복 체크
        existing = self._user_repository.find_by_email(user.email)
        if existing.is_success() and existing.unwrap() is not None:
            return Failure("이미 존재하는 이메일입니다")
        
        # 3. 패스워드 해싱 및 저장
        hashed_password = self._password_hasher.hash(request.password)
        # 실제로는 User에 password 필드 추가 필요
        
        # 4. 저장소에 저장
        save_result = self._user_repository.save(user)
        if save_result.is_failure():
            return Failure(f"사용자 저장 실패: {save_result.unwrap_error()}")
        
        # 5. 이벤트 발행
        event = UserCreatedEvent(user.id.value, user.email.value)
        self._event_publisher.publish(event)
        
        # 6. DTO 변환 및 반환
        return Success(UserDto(
            id=user.id.value,
            email=user.email.value,
            name=user.name,
            verified=user.verified
        ))
```

## 인프라스트럭처 레이어

### 1. 어댑터 구현

```python
# 데이터베이스 어댑터
class PostgresUserRepository:
    """PostgreSQL 사용자 저장소 어댑터"""
    
    def __init__(self, connection_pool):
        self._pool = connection_pool
    
    def save(self, user: User) -> Result[User, str]:
        try:
            query = """
                INSERT INTO users (id, email, name, created_at, verified)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    verified = EXCLUDED.verified
            """
            
            with self._pool.connection() as conn:
                conn.execute(query, (
                    user.id.value,
                    user.email.value,
                    user.name,
                    user.created_at,
                    user.verified
                ))
            
            return Success(user)
        except Exception as e:
            return Failure(f"Database error: {e}")
    
    def find_by_id(self, id: UserId) -> Result[Optional[User], str]:
        try:
            query = "SELECT * FROM users WHERE id = %s"
            
            with self._pool.connection() as conn:
                row = conn.fetchone(query, (id.value,))
                
                if not row:
                    return Success(None)
                
                user = User(
                    id=UserId(row['id']),
                    email=Email(row['email']),
                    name=row['name'],
                    created_at=row['created_at'],
                    verified=row['verified']
                )
                
                return Success(user)
        except Exception as e:
            return Failure(f"Database error: {e}")
```

### 2. HTTP 어댑터

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# HTTP 요청/응답 모델
class CreateUserHttpRequest(BaseModel):
    email: str
    password: str
    name: str

class UserHttpResponse(BaseModel):
    id: str
    email: str
    name: str
    verified: bool

# HTTP 어댑터
class UserHttpAdapter:
    """HTTP REST API 어댑터"""
    
    def __init__(self, create_user_usecase: CreateUserUseCase):
        self._create_user = create_user_usecase
    
    def register_routes(self, app: FastAPI):
        """라우트 등록"""
        
        @app.post("/users", response_model=UserHttpResponse)
        async def create_user(request: CreateUserHttpRequest):
            # HTTP 요청을 애플리케이션 요청으로 변환
            app_request = CreateUserRequest(
                email=request.email,
                password=request.password,
                name=request.name
            )
            
            # 유스케이스 실행
            result = self._create_user.execute(app_request)
            
            # 결과 처리
            if result.is_failure():
                raise HTTPException(status_code=400, detail=result.unwrap_error())
            
            # DTO를 HTTP 응답으로 변환
            user_dto = result.unwrap()
            return UserHttpResponse(
                id=user_dto.id,
                email=user_dto.email,
                name=user_dto.name,
                verified=user_dto.verified
            )
```

## 의존성 주입 설정

```python
from rfs.core.registry import ServiceRegistry, ServiceScope

def configure_services() -> ServiceRegistry:
    """서비스 설정"""
    registry = ServiceRegistry()
    
    # 인프라스트럭처 등록
    registry.register(
        "db_pool",
        PostgresConnectionPool,
        scope=ServiceScope.SINGLETON
    )
    
    registry.register(
        "password_hasher",
        BcryptPasswordHasher,
        scope=ServiceScope.SINGLETON
    )
    
    # 저장소 등록
    registry.register(
        "user_repository",
        PostgresUserRepository,
        scope=ServiceScope.SINGLETON,
        dependencies=["db_pool"]
    )
    
    # 도메인 서비스 등록
    registry.register(
        "user_domain_service",
        UserDomainService,
        scope=ServiceScope.SINGLETON,
        dependencies=["password_hasher"]
    )
    
    # 유스케이스 등록
    registry.register(
        "create_user_usecase",
        CreateUserUseCaseImpl,
        scope=ServiceScope.PROTOTYPE,
        dependencies=[
            "user_domain_service",
            "user_repository",
            "event_publisher",
            "password_hasher"
        ]
    )
    
    return registry
```

## 테스트 전략

### 1. 도메인 테스트 (단위 테스트)

```python
def test_user_email_change():
    """도메인 로직 테스트 - 외부 의존성 없음"""
    user = User(
        id=UserId("123"),
        email=Email("old@example.com"),
        name="Test User",
        created_at=datetime.now(),
        verified=False
    )
    
    # 검증되지 않은 사용자는 이메일 변경 가능
    result = user.change_email(Email("new@example.com"))
    assert result.is_success()
    assert result.unwrap().email.value == "new@example.com"
    
    # 검증된 사용자는 이메일 변경 불가
    verified_user = user.verify()
    result = verified_user.change_email(Email("another@example.com"))
    assert result.is_failure()
```

### 2. 유스케이스 테스트 (통합 테스트)

```python
from unittest.mock import Mock

def test_create_user_usecase():
    """유스케이스 테스트 - 목 객체 사용"""
    
    # 목 객체 생성
    mock_repo = Mock(spec=UserRepository)
    mock_repo.find_by_email.return_value = Success(None)
    mock_repo.save.return_value = Success(None)
    
    mock_publisher = Mock(spec=EventPublisher)
    mock_hasher = Mock(spec=PasswordHasher)
    mock_hasher.hash.return_value = "hashed_password"
    
    # 유스케이스 실행
    usecase = CreateUserUseCaseImpl(
        UserDomainService(mock_hasher),
        mock_repo,
        mock_publisher,
        mock_hasher
    )
    
    request = CreateUserRequest(
        email="test@example.com",
        password="password123",
        name="Test User"
    )
    
    result = usecase.execute(request)
    
    # 검증
    assert result.is_success()
    assert mock_repo.save.called
    assert mock_publisher.publish.called
```

## 모범 사례

1. **도메인 순수성**: 도메인 레이어는 프레임워크, 데이터베이스, HTTP 등을 모름
2. **인터페이스 정의**: 포트는 도메인/애플리케이션에, 어댑터는 인프라에
3. **의존성 방향**: 항상 안쪽으로 (인프라 → 애플리케이션 → 도메인)
4. **테스트 우선**: 도메인 로직은 단위 테스트로, 통합은 목 객체로
5. **불변성**: 엔티티와 값 객체는 불변으로 설계
6. **명시적 에러**: Result 패턴으로 모든 에러 명시적 처리