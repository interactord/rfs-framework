# Annotations System

RFS Framework 어노테이션 시스템 및 데코레이터 가이드.

## 어노테이션 개요

어노테이션 시스템은 코드에 메타데이터를 추가하여 기능을 확장하고 자동화할 수 있게 합니다.

### 지원되는 어노테이션

- `@service`: 서비스 컴포넌트 등록
- `@repository`: 데이터 액세스 계층
- `@component`: 일반 컴포넌트
- `@configuration`: 설정 클래스
- `@autowired`: 의존성 주입

## 기본 사용법

### 서비스 등록

```python
from rfs.core.annotations import service
from rfs.core.result import Result

@service
class UserService:
    def create_user(self, name: str, email: str) -> Result[dict, str]:
        # 비즈니스 로직
        return Success({"id": 1, "name": name, "email": email})
```

### 레포지토리 패턴

```python
from rfs.core.annotations import repository
from typing import List, Optional

@repository
class UserRepository:
    def find_by_id(self, user_id: int) -> Optional[dict]:
        # 데이터 액세스 로직
        pass
    
    def find_all(self) -> List[dict]:
        # 모든 사용자 조회
        pass
```

### 의존성 주입

```python
from rfs.core.annotations import service, autowired
from rfs.core.registry import Registry

@service
class OrderService:
    @autowired
    def __init__(self, user_service: UserService):
        self.user_service = user_service
    
    def create_order(self, user_id: int, items: List[str]):
        # 주문 생성 로직
        pass
```

## 고급 기능

### 스코프 설정

```python
from rfs.core.annotations import service, Scope

# 싱글톤 스코프
@service(scope=Scope.SINGLETON)
class ConfigService:
    def __init__(self):
        self.config = self._load_config()

# 프로토타입 스코프
@service(scope=Scope.PROTOTYPE)
class RequestHandler:
    def handle(self, request):
        # 요청별로 새 인스턴스 생성
        pass
```

### 조건부 빈 등록

```python
from rfs.core.annotations import conditional

@service
@conditional(lambda: os.getenv("ENABLE_CACHE") == "true")
class CacheService:
    """ENABLE_CACHE 환경변수가 true일 때만 등록"""
    pass
```

## 어노테이션 처리기

### 커스텀 어노테이션 생성

```python
from rfs.core.annotations.base import BaseAnnotation
from typing import Type, Any

class cache(BaseAnnotation):
    """...로그 어노테이션"""
    
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
    
    def process(self, target: Type[Any]) -> Type[Any]:
        # 캐싱 로직 적용
        original_methods = {}
        for name, method in inspect.getmembers(target, inspect.isfunction):
            original_methods[name] = method
            setattr(target, name, self._wrap_with_cache(method))
        return target
    
    def _wrap_with_cache(self, method):
        def wrapper(*args, **kwargs):
            # 캐시 로직
            cache_key = f"{method.__name__}_{hash((args, tuple(kwargs.items())))}"
            if cache_key in self.cache:
                return self.cache[cache_key]
            
            result = method(*args, **kwargs)
            self.cache[cache_key] = result
            return result
        return wrapper

# 사용 예제
@service
class DataService:
    @cache(ttl=1800)  # 30분 캐싱
    def get_expensive_data(self, key: str) -> dict:
        # 비용이 높은 데이터 조회
        pass
```

## 레지스트리 연동

어노테이션 시스템은 레지스트리와 긴밀하게 연동되어 의존성 주입을 자동화합니다.

```python
from rfs.core.registry import get_registry
from rfs.core.annotations import scan_components

# 컴포넌트 스캔
scan_components("myapp.services")  # 패키지 스캔

# 빈 사용
registry = get_registry()
user_service = registry.get(UserService)
```

## 관련 문서

- [Registry](../api/core/registry.md) - 의존성 주입 레지스트리
- [Dependency Injection](../02-dependency-injection.md) - 의존성 주입 가이드
- [Configuration](../api/core/config.md) - 설정 어노테이션
