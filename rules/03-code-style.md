# 코드 스타일 가이드

## 일반 규칙

### 1. 타입 힌트 필수

모든 public 함수와 메서드는 완전한 타입 힌트를 가져야 합니다:

```python
# ❌ 잘못된 방법
def process_data(data, options=None):
    return transform(data)

# ✅ 올바른 방법
from typing import Optional, Dict, Any
from rfs.core.result import Result

def process_data(
    data: Dict[str, Any], 
    options: Optional[ProcessOptions] = None
) -> Result[ProcessedData, str]:
    return transform(data, options or default_options())
```

### 2. 제네릭 타입 활용

```python
from typing import TypeVar, Generic, Protocol

T = TypeVar('T')
E = TypeVar('E')
K = TypeVar('K', bound=str)  # 제약된 타입 변수
V = TypeVar('V', covariant=True)  # 공변성

class Repository(Generic[T]):
    def get(self, id: str) -> Result[T, str]:
        ...
    
    def save(self, entity: T) -> Result[T, str]:
        ...

# 프로토콜로 구조적 타이핑
class Identifiable(Protocol):
    @property
    def id(self) -> str: ...

def process_identifiable(item: Identifiable) -> str:
    return f"Processing: {item.id}"
```

### 3. 명명 규칙

```python
# 모듈: snake_case
user_service.py
data_processor.py

# 클래스: PascalCase
class UserRepository:
    pass

# 함수/변수: snake_case
def calculate_total(items: list) -> float:
    total_amount = 0.0
    return total_amount

# 상수: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30.0

# Private: 언더스코어 prefix
class Service:
    def __init__(self):
        self._internal_state = {}
    
    def _private_method(self):
        pass
```

## 함수 작성 규칙

### 1. 단일 책임 원칙

```python
# ❌ 잘못된 방법 - 너무 많은 책임
def process_user(user_data: dict) -> Result[User, str]:
    # 유효성 검사
    if not user_data.get("email"):
        return Failure("이메일 필수")
    
    # 데이터 변환
    user = User(
        email=user_data["email"],
        name=user_data.get("name", "")
    )
    
    # 데이터베이스 저장
    db.save(user)
    
    # 이메일 발송
    send_welcome_email(user.email)
    
    return Success(user)

# ✅ 올바른 방법 - 단일 책임
def validate_user_data(data: dict) -> Result[dict, str]:
    if not data.get("email"):
        return Failure("이메일 필수")
    return Success(data)

def create_user_entity(data: dict) -> Result[User, str]:
    return Success(User(
        email=data["email"],
        name=data.get("name", "")
    ))

def save_user(user: User) -> Result[User, str]:
    return db.save(user)

def notify_user_created(user: User) -> Result[None, str]:
    return send_welcome_email(user.email)

# 합성
def process_user(user_data: dict) -> Result[User, str]:
    return (
        validate_user_data(user_data)
        .bind(create_user_entity)
        .bind(save_user)
        .bind(lambda u: notify_user_created(u).map(lambda _: u))
    )
```

### 2. Guard 절 활용

```python
# ❌ 중첩된 if
def calculate_discount(user: User, amount: float) -> float:
    if user.is_premium:
        if amount > 1000:
            return amount * 0.2
        else:
            if amount > 500:
                return amount * 0.1
            else:
                return amount * 0.05
    else:
        if amount > 1000:
            return amount * 0.05
        else:
            return 0

# ✅ Guard 절 사용
def calculate_discount(user: User, amount: float) -> float:
    if not user.is_premium:
        return amount * 0.05 if amount > 1000 else 0
    
    if amount > 1000:
        return amount * 0.2
    
    if amount > 500:
        return amount * 0.1
    
    return amount * 0.05
```

### 3. 기본 매개변수는 불변으로

```python
# ❌ 가변 기본값
def add_item(items: list = []):  # 위험!
    items.append("new")
    return items

# ✅ 불변 기본값
def add_item(items: Optional[list] = None) -> list:
    items = items or []
    return [*items, "new"]

# 더 나은 방법 - dataclass 활용
from dataclasses import dataclass, field

@dataclass
class Config:
    items: list = field(default_factory=list)
    settings: dict = field(default_factory=dict)
```

## 클래스 설계

### 1. 불변 데이터 클래스

```python
from dataclasses import dataclass
from typing import FrozenSet

# ✅ 불변 엔티티
@dataclass(frozen=True)
class User:
    id: str
    email: str
    roles: FrozenSet[str] = frozenset()
    
    def with_role(self, role: str) -> "User":
        """새로운 역할이 추가된 새 User 인스턴스 반환"""
        return User(
            id=self.id,
            email=self.email,
            roles=self.roles | {role}
        )
```

### 2. 의존성 주입

```python
from typing import Protocol

# 인터페이스 정의
class EmailService(Protocol):
    def send(self, to: str, subject: str, body: str) -> Result[None, str]:
        ...

# 구현
class SmtpEmailService:
    def send(self, to: str, subject: str, body: str) -> Result[None, str]:
        # SMTP 구현
        pass

# 의존성 주입
@dataclass
class UserService:
    email_service: EmailService  # 인터페이스에 의존
    
    def create_user(self, data: dict) -> Result[User, str]:
        return (
            validate(data)
            .bind(create_entity)
            .bind(lambda u: self.email_service.send(
                u.email, "Welcome", "..."
            ).map(lambda _: u))
        )
```

## 비동기 코드

### 1. async/await 규칙

```python
# ✅ Result와 함께 사용
async def fetch_user(id: str) -> Result[User, str]:
    try:
        user = await db.get_user(id)
        return Success(user)
    except DatabaseError as e:
        return Failure(f"DB 에러: {e}")

# 비동기 체이닝
from rfs.core.result import AsyncResult

async def process_async(user_id: str) -> Result[ProcessedUser, str]:
    return await (
        AsyncResult.from_coroutine(fetch_user(user_id))
        .map_async(enrich_user)
        .bind_async(validate_permissions)
        .map_async(transform_to_dto)
    )
```

### 2. 동시성 처리

```python
import asyncio
from typing import List

async def fetch_all_users(ids: List[str]) -> Result[List[User], str]:
    """병렬로 사용자 정보 가져오기"""
    tasks = [fetch_user(id) for id in ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        return Failure(f"일부 사용자 조회 실패: {errors}")
    
    return sequence(results)  # 모든 Result를 하나로 결합
```

## 에러 메시지

### 구체적이고 실용적인 메시지

```python
# ❌ 모호한 메시지
return Failure("에러 발생")
return Failure("잘못된 입력")

# ✅ 구체적인 메시지
return Failure(f"사용자 ID '{user_id}'를 찾을 수 없습니다")
return Failure(f"이메일 형식이 잘못되었습니다: '{email}'. 예: user@example.com")
return Failure(
    f"연령은 0에서 150 사이여야 합니다. 입력값: {age}"
)
```

## 테스트 코드 스타일

### 1. Given-When-Then 패턴

```python
def test_user_creation():
    # Given - 준비
    user_data = {
        "email": "test@example.com",
        "name": "Test User"
    }
    
    # When - 실행
    result = create_user(user_data)
    
    # Then - 검증
    assert result.is_success()
    user = result.unwrap()
    assert user.email == "test@example.com"
    assert user.name == "Test User"
```

### 2. 테스트 명명

```python
class TestUserService:
    """UserService 테스트"""
    
    def test_create_user_with_valid_data_returns_success(self):
        """유효한 데이터로 사용자 생성 시 성공 반환"""
        pass
    
    def test_create_user_with_duplicate_email_returns_failure(self):
        """중복 이메일로 사용자 생성 시 실패 반환"""
        pass
```

## 모범 사례

1. **Import 정리**: isort 사용, 표준 라이브러리 → 서드파티 → 로컬
2. **라인 길이**: 최대 88자 (Black 기본값)
3. **문서화**: 공개 API는 반드시 docstring 포함
4. **타입 체크**: mypy strict mode 통과
5. **포맷팅**: Black으로 자동 포맷팅
6. **보안**: 민감 정보 로깅 금지
7. **성능**: 불필요한 복사 피하기, 제너레이터 활용