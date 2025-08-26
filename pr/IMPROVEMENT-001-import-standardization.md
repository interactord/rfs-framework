# IMPROVEMENT-001: Import 구문 표준화

## 📋 개선 제안

### 목적
RFS Framework 전체에서 일관된 import 구문 스타일을 적용하여 코드 가독성과 유지보수성을 향상시킵니다.

### 현재 문제점
- 일관성 없는 import 순서
- 혼재된 import 스타일 (절대/상대 import)
- 불필요한 import 존재
- typing 모듈 사용 불일치

## 🔍 현재 상태 분석

### 발견된 inconsistency 예시

#### 1. Import 순서 불일치
```python
# rfs/core/config.py (현재)
from typing import Dict, Any, Optional
from pydantic import BaseSettings
from abc import ABC, abstractmethod
import os

# 제안: PEP 8 순서 준수
import os                           # 1. 표준 라이브러리
from abc import ABC, abstractmethod

from pydantic import BaseSettings   # 2. 서드파티 패키지
from typing import Dict, Any, Optional  # (또는 표준으로 분류)
```

#### 2. 타입 import 불일치
```python
# 현재 혼재된 방식
from typing import Dict, Any
Dict[str, Any] = field(default_factory=dict)

# 제안: 일관된 방식
from typing import Dict, Any, Optional
from dataclasses import field
custom: Dict[str, Any] = field(default_factory=dict)
```

## 🎯 제안된 표준화 규칙

### 1. Import 순서 (PEP 8 준수)
```python
# 1. 표준 라이브러리 imports
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# 2. 관련된 서드파티 라이브러리 imports  
from pydantic import BaseSettings, Field
import redis

# 3. 로컬 애플리케이션/라이브러리 imports
from .base import BaseConfig
from ..utils import helper_function
```

### 2. 타입 힌트 표준화
```python
# 권장 방식
from typing import Dict, List, Optional, Union, Any, Callable
from typing import Generic, TypeVar

T = TypeVar('T')
E = TypeVar('E')

# 일관된 타입 힌트 사용
config_data: Dict[str, Any]
results: Optional[List[str]]
callback: Callable[[str], bool]
```

### 3. 조건부 import 처리
```python
# 선택적 의존성 처리
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
```

## 🛠️ 구체적 개선 사항

### 파일별 개선 대상

#### 1. `rfs/core/config.py`
```python
# Before
from typing import Dict, Any, Optional
from pydantic import BaseSettings

class RFSConfig(BaseSettings):
    custom: Dict[str, Any] = field(default_factory=dict)  # ❌ field 미정의

# After  
from typing import Dict, Any, Optional
from dataclasses import field
from pydantic import BaseSettings

class RFSConfig(BaseSettings):
    custom: Dict[str, Any] = field(default_factory=dict)  # ✅ 정상
```

#### 2. `rfs/cache/__init__.py`
```python
# 표준화된 export 구조
from .redis_cache import RedisCache
from .config import RedisCacheConfig
from .exceptions import CacheError, ConnectionError

__all__ = [
    'RedisCache',
    'RedisCacheConfig', 
    'CacheError',
    'ConnectionError'
]
```

## 📏 스타일 가이드 제안

### 1. Import 그룹 구분
- 그룹 사이에 빈 줄 하나
- 각 그룹 내에서는 알파벳 순서
- `from` import는 `import` 뒤에

### 2. 타입 힌트 규칙
- 모든 공개 함수/메서드에 타입 힌트 적용
- Generic 타입은 파일 상단에 정의
- Union 타입보다는 Optional 선호 (가능한 경우)

### 3. Import alias 규칙
```python
# 일관된 alias 사용
import redis.asyncio as aioredis
import typing as t  # 필요시에만
from dataclasses import dataclass as dc  # 충돌 방지용
```

## 🧪 검증 방법

### 1. Linting 도구 설정
```toml
# pyproject.toml
[tool.isort]
profile = "black"
line_length = 88
known_first_party = ["rfs"]
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]
```

### 2. Pre-commit 훅 추가
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
```

## 📋 구현 계획

### Phase 1: 긴급 수정
- [x] field import 오류 수정
- [ ] 핵심 모듈 import 표준화

### Phase 2: 전체 적용
- [ ] 모든 파일에 표준화 적용
- [ ] 린팅 도구 설정
- [ ] CI/CD 파이프라인 통합

### Phase 3: 문서화
- [ ] 스타일 가이드 문서 작성
- [ ] 기여자 가이드 업데이트

## 🎯 예상 효과

- **가독성**: 일관된 import 구조로 코드 이해도 향상
- **유지보수성**: 표준화된 패턴으로 수정/확장 용이
- **협업**: 팀 내 코드 스타일 통일
- **품질**: 자동화된 검증으로 실수 방지