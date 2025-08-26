# IMPROVEMENT-002: 타입 힌트 개선

## 📋 개선 제안

### 목적
RFS Framework 전체에서 타입 힌트를 개선하여 코드의 안전성, 가독성, IDE 지원을 향상시킵니다.

### 현재 문제점
- 불완전한 타입 힌트 적용
- Generic 타입 사용 부족
- Optional vs Union 혼재 사용
- 반환 타입 누락
- 복잡한 타입의 명시적 정의 부족

## 🔍 현재 상태 분석

### 발견된 타입 힌트 이슈

#### 1. 반환 타입 누락
```python
# 현재 (rfs/core/config.py)
def get_config():  # ❌ 반환 타입 없음
    return RFSConfig()

# 제안
def get_config() -> RFSConfig:  # ✅ 명시적 반환 타입
    return RFSConfig()
```

#### 2. Generic 타입 미활용
```python
# 현재
from typing import Any

def process_data(data):  # ❌ 타입 힌트 없음
    return data

# 제안
from typing import TypeVar, Generic

T = TypeVar('T')

def process_data(data: T) -> T:  # ✅ Generic 활용
    return data
```

#### 3. Optional vs Union 혼재
```python
# 현재 혼재 사용
from typing import Union

config: Union[dict, None] = None  # ❌ 일관성 부족

# 제안: Optional 통일
from typing import Optional

config: Optional[dict] = None  # ✅ 일관된 스타일
```

## 🎯 제안된 타입 힌트 개선

### 1. Result 패턴 타입 정의
```python
from typing import TypeVar, Generic, Union
from abc import ABC, abstractmethod

T = TypeVar('T')  # Success value type
E = TypeVar('E')  # Error type

class Result(Generic[T, E], ABC):
    """타입 안전한 Result 모나드"""
    
    @abstractmethod
    def is_success(self) -> bool: ...
    
    @abstractmethod
    def is_failure(self) -> bool: ...
    
    @abstractmethod
    def value(self) -> T: ...
    
    @abstractmethod
    def error(self) -> E: ...

# 구체적 구현
class Success(Result[T, E]):
    def __init__(self, value: T) -> None:
        self._value = value
    
    def value(self) -> T:
        return self._value

class Failure(Result[T, E]):
    def __init__(self, error: E) -> None:
        self._error = error
    
    def error(self) -> E:
        return self._error
```

### 2. 캐시 클라이언트 타입 개선
```python
from typing import Optional, Dict, Any, List, Callable, Awaitable
from typing import Protocol, runtime_checkable

@runtime_checkable
class CacheProtocol(Protocol):
    """캐시 인터페이스 정의"""
    
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool: ...
    async def delete(self, key: str) -> bool: ...

class RedisCache:
    def __init__(self, config: RedisCacheConfig) -> None:
        self._config = config
        self._client: Optional[redis.Redis] = None
    
    async def get(self, key: str) -> Optional[str]:
        """타입 안전한 get 메서드"""
        if not self._client:
            return None
        return await self._client.get(key)
    
    async def set(
        self, 
        key: str, 
        value: str, 
        ttl: Optional[int] = None
    ) -> bool:
        """타입 안전한 set 메서드"""
        if not self._client:
            return False
        return await self._client.set(key, value, ex=ttl)
```

### 3. Reactive 패턴 타입 정의
```python
from typing import TypeVar, Generic, Callable, Awaitable, List

T = TypeVar('T')
U = TypeVar('U')

class Mono(Generic[T]):
    """타입 안전한 비동기 Mono"""
    
    def __init__(self, supplier: Callable[[], Awaitable[T]]) -> None:
        self._supplier = supplier
    
    async def execute(self) -> T:
        return await self._supplier()
    
    def map(self, mapper: Callable[[T], U]) -> 'Mono[U]':
        async def mapped_supplier() -> U:
            value = await self.execute()
            return mapper(value)
        return Mono(mapped_supplier)
    
    def flat_map(self, mapper: Callable[[T], 'Mono[U]']) -> 'Mono[U]':
        async def flat_mapped_supplier() -> U:
            value = await self.execute()
            inner_mono = mapper(value)
            return await inner_mono.execute()
        return Mono(flat_mapped_supplier)

class Flux(Generic[T]):
    """타입 안전한 비동기 Flux"""
    
    def __init__(self, supplier: Callable[[], Awaitable[List[T]]]) -> None:
        self._supplier = supplier
    
    async def collect_list(self) -> List[T]:
        return await self._supplier()
    
    def map(self, mapper: Callable[[T], U]) -> 'Flux[U]':
        async def mapped_supplier() -> List[U]:
            items = await self.collect_list()
            return [mapper(item) for item in items]
        return Flux(mapped_supplier)
```

## 🛠️ 구체적 개선 사항

### 1. 설정 클래스 타입 개선
```python
from typing import Dict, Any, Optional, List
from pydantic import BaseSettings, Field
from dataclasses import dataclass, field

@dataclass
class RedisConfig:
    """타입 안전한 Redis 설정"""
    host: str = field(default="localhost")
    port: int = field(default=6379)
    db: int = field(default=0)
    password: Optional[str] = field(default=None)
    ssl: bool = field(default=False)
    timeout: float = field(default=30.0)
    
    def to_url(self) -> str:
        """Redis URL 생성"""
        protocol = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"

class RFSConfig(BaseSettings):
    """타입 안전한 RFS 설정"""
    
    # 기본 설정
    debug: bool = Field(default=False, description="디버그 모드")
    log_level: str = Field(default="INFO", description="로그 레벨")
    
    # Redis 설정
    redis: RedisConfig = Field(default_factory=RedisConfig)
    
    # 커스텀 설정
    custom: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        env_prefix = "RFS_"
        case_sensitive = False
```

### 2. 에러 처리 타입 개선
```python
from typing import Union, Type, Optional
from enum import Enum

class ErrorCode(Enum):
    """에러 코드 정의"""
    CONFIG_ERROR = "CONFIG_001"
    CACHE_ERROR = "CACHE_001"
    CONNECTION_ERROR = "CONNECTION_001"

class RFSException(Exception):
    """타입 안전한 RFS 예외"""
    
    def __init__(
        self, 
        message: str, 
        code: ErrorCode, 
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.cause = cause
    
    def __str__(self) -> str:
        return f"[{self.code.value}] {super().__str__()}"

# 구체적 예외 타입들
class ConfigError(RFSException):
    def __init__(self, message: str, cause: Optional[Exception] = None) -> None:
        super().__init__(message, ErrorCode.CONFIG_ERROR, cause)

class CacheError(RFSException):
    def __init__(self, message: str, cause: Optional[Exception] = None) -> None:
        super().__init__(message, ErrorCode.CACHE_ERROR, cause)
```

## 📏 타입 힌트 가이드라인

### 1. 기본 원칙
- 모든 공개 함수/메서드에 타입 힌트 적용
- 복잡한 타입은 Type Alias로 정의
- Generic을 적극 활용하여 타입 안전성 확보

### 2. 네이밍 컨벤션
```python
# Type Variables
T = TypeVar('T')           # Generic type
K = TypeVar('K')           # Key type  
V = TypeVar('V')           # Value type
E = TypeVar('E')           # Error type

# Type Aliases
ConfigDict = Dict[str, Any]
ResultType = Union[Success[T], Failure[str]]
AsyncHandler = Callable[[str], Awaitable[bool]]
```

### 3. Protocol 활용
```python
from typing import Protocol

class Serializable(Protocol):
    """직렬화 가능한 객체 인터페이스"""
    
    def serialize(self) -> Dict[str, Any]: ...
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'Serializable': ...
```

## 🧪 검증 방법

### 1. mypy 설정
```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
strict_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
```

### 2. 타입 체킹 CI
```yaml
# .github/workflows/type-check.yml
- name: Run mypy
  run: mypy src/ --strict
```

## 📋 마이그레이션 계획

### Phase 1: 핵심 모듈
- [x] Result 패턴 타입 정의
- [ ] 캐시 모듈 타입 개선
- [ ] 설정 모듈 타입 개선

### Phase 2: 확장 모듈
- [ ] 유틸리티 함수 타입 개선
- [ ] 예외 처리 타입 개선
- [ ] 테스트 코드 타입 적용

### Phase 3: 검증 및 문서화
- [ ] mypy 설정 및 CI 통합
- [ ] 타입 힌트 가이드 문서화
- [ ] IDE 지원 개선 확인

## 🎯 예상 효과

- **안전성**: 컴파일 타임 에러 검출로 런타임 오류 감소
- **가독성**: 명확한 타입 정보로 코드 이해도 향상  
- **IDE 지원**: 자동완성, 리팩토링 지원 개선
- **개발 생산성**: 타입 기반 개발로 버그 감소