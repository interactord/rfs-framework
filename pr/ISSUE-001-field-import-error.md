# ISSUE-001: `NameError: name 'field' is not defined` 버그

## 📋 이슈 설명

### 문제
`rfs/core/config.py` 파일의 97번째 줄에서 `field` 함수가 정의되지 않았다는 오류가 발생합니다.

```python
# 현재 코드 (rfs/core/config.py:97)
custom: Dict[str, Any] = field(default_factory=dict)
                         ^^^^^
NameError: name 'field' is not defined. Did you mean: 'Field'?
```

### 발생 조건
- RFS Framework를 import할 때
- 특히 `from rfs.cache import RedisCache, RedisCacheConfig` 호출 시
- Python 3.12 환경에서 확인됨

### 영향
- **심각도**: Critical
- **영향 범위**: RFS Framework를 사용하는 모든 애플리케이션
- **증상**: 서버 시작 불가, import 오류로 인한 애플리케이션 크래시

## 🔍 원인 분석

### 근본 원인
`dataclasses.field` 함수가 import되지 않았음에도 불구하고 사용되고 있습니다.

### 코드 분석
```python
# rfs/core/config.py 상단
from typing import Dict, Any, Optional
from pydantic import BaseSettings
# dataclasses.field import 누락!

class RFSConfig(BaseSettings):
    # ... 기타 필드들
    custom: Dict[str, Any] = field(default_factory=dict)  # ❌ field가 정의되지 않음
```

## 🛠️ 수정 방안

### 해결책 1: dataclasses.field import 추가 (권장)
```python
# rfs/core/config.py 상단에 추가
from dataclasses import field

class RFSConfig(BaseSettings):
    # ... 기타 필드들
    custom: Dict[str, Any] = field(default_factory=dict)  # ✅ 정상 작동
```

### 해결책 2: Pydantic Field 사용 (대안)
```python
# rfs/core/config.py 상단에 추가
from pydantic import Field

class RFSConfig(BaseSettings):
    # ... 기타 필드들
    custom: Dict[str, Any] = Field(default_factory=dict)  # ✅ Pydantic 방식
```

## 🧪 테스트 케이스

### 재현 테스트
```python
# tests/test_config_import.py
def test_rfs_config_import():
    """RFS Config import가 정상적으로 작동하는지 테스트"""
    try:
        from rfs.core.config import RFSConfig
        config = RFSConfig()
        assert hasattr(config, 'custom')
        assert isinstance(config.custom, dict)
    except NameError as e:
        assert False, f"Import failed: {e}"
```

### 회귀 테스트
```python
def test_field_functionality():
    """field 기능이 정상적으로 작동하는지 테스트"""
    from rfs.core.config import RFSConfig
    
    config = RFSConfig()
    config.custom['test_key'] = 'test_value'
    assert config.custom['test_key'] == 'test_value'
```

## 📋 체크리스트

- [x] 문제 재현 확인
- [x] 원인 분석 완료
- [x] 수정 방안 검토
- [x] 수정 코드 작성
- [x] 테스트 케이스 작성
- [x] 코드 리뷰
- [ ] PR 생성

## ✅ 수정 완료

### 적용된 수정사항
**파일**: `src/rfs/core/config.py:97`
**변경**: `field(default_factory=dict)` → `Field(default_factory=dict)`

**수정 이유**: Pydantic 코드 경로에서는 `Field`를 사용하는 것이 일관성 있고 올바른 접근법

### 검증 결과
- ✅ Fallback 경로 (dataclass) 정상 동작 확인
- ✅ Pydantic 경로 시뮬레이션 성공
- ✅ 기존 기능 정상 동작 확인
- ✅ 테스트 케이스 작성 및 검증 완료

### 테스트 파일
- `test_field_fix.py`: 수정 검증 스크립트 생성
- 양방향 코드 경로 테스트 포함

## 📝 PR 제출 정보

**브랜치명**: `fix/field-import-error`
**PR 제목**: `Fix NameError: name 'field' is not defined in config.py`
**라벨**: `bug`, `high-priority`, `fixed`

## 🔗 관련 링크

- **Stack Trace**: [전체 에러 로그](./stacktrace-field-error.txt)
- **환경 정보**: Python 3.12, rfs-framework 버전
- **재현 스크립트**: [reproduce-field-error.py](./tests/reproduce-field-error.py)