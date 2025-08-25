# 18. Database

RFS Framework 데이터베이스 연동 및 ORM 시스템.

## 데이터베이스 연동 개요

RFS Framework는 다양한 데이터베이스와의 연동을 지원하며, 단순한 ORM 인터페이스를 제공합니다.

## 지원 데이터베이스

- **PostgreSQL**: 주요 관계형 데이터베이스
- **SQLite**: 개발 및 테스트용
- **MySQL**: 레거시 시스템 지원
- **Redis**: 캐시용

## 기본 사용법

```python
from rfs.database import DatabaseManager, Model

# 데이터베이스 연결 설정
db = DatabaseManager("postgresql://user:pass@localhost/db")

# 모델 정의
class User(Model):
    id: int
    name: str
    email: str
    
    class Meta:
        table_name = "users"
        primary_key = "id"

# CRUD 작업
user = User.create(name="John", email="john@example.com")
users = User.find_all()
User.update(user.id, name="John Doe")
User.delete(user.id)
```

## 트랜잭션 지원

```python
from rfs.database import transaction

@transaction
def transfer_money(from_user_id: int, to_user_id: int, amount: float):
    from_user = User.find(from_user_id)
    to_user = User.find(to_user_id)
    
    from_user.balance -= amount
    to_user.balance += amount
    
    from_user.save()
    to_user.save()
```

## 관련 문서

- [Transactions](04-transactions.md) - 트랜잭션 시스템
- [Result Pattern](01-core-patterns.md) - 안전한 데이터베이스 조작
- [Configuration](03-configuration.md) - 데이터베이스 설정
