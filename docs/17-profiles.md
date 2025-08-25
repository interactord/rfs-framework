# 17. Profiles

RFS Framework 프로필 설정 및 관리 시스템.

## 프로필 개요

프로필은 다양한 환경과 사용 사례에 맞게 RFS Framework의 동작을 구성할 수 있는 시스템입니다.

### 기본 프로필

- **development**: 개발 환경용 설정
- **production**: 운영 환경용 설정
- **testing**: 테스트 환경용 설정

## 프로필 설정

```python
from rfs.core.config import get_config

# 프로필 기반 설정 로드
config = get_config(profile="development")
```

## 관련 문서

- [Configuration](03-configuration.md) - 기본 설정 시스템
- [Environment Variables](api/core/config.md) - 환경 변수 설정
