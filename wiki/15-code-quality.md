# 코드 품질 관리 시스템 (Code Quality Management)

## 개요

RFS Framework의 통합 코드 품질 관리 시스템은 엔터프라이즈급 코드베이스의 품질을 자동으로 관리하고 개선하는 강력한 도구입니다. 기존 50개 이상의 개별 스크립트를 하나의 체계적인 시스템으로 통합하여, 일관된 코드 품질과 함수형 프로그래밍 패턴을 보장합니다.

## 핵심 특징

### 🎯 통합 품질 관리
- **단일 진입점**: `rfs-quality` CLI를 통한 모든 품질 관리 작업
- **17,000줄 → 2,000줄**: 88% 코드 감소로 유지보수성 극대화
- **세션 기반 관리**: 모든 변경사항을 세션으로 추적 및 관리
- **Git 독립적**: 별도의 백업 시스템으로 안전성 보장

### 🛡️ 안전 기능
- **자동 백업**: 모든 변환 전 파일 백업
- **자동 롤백**: 오류 발생 시 즉시 복구
- **체크섬 검증**: 파일 무결성 보장
- **Dry Run 모드**: 실제 변경 없이 시뮬레이션

### 🔧 변환 기능
- **구문 수정**: Python AST 기반 구문 오류 자동 수정
- **코드 포맷팅**: Black/isort 통합
- **함수형 패턴**: 불변성 원칙 적용
- **Match-Case 변환**: if-elif 체인을 현대적 패턴으로

### 📊 품질 메트릭
- **구문 검증**: Python 파서 검증
- **스타일 준수**: PEP 8 및 Black 규칙
- **함수형 위반**: 불변성 규칙 검사
- **타입 안전성**: Mypy 통합 검사

## 설치 및 설정

### 사전 요구사항

```bash
# Python 3.10 이상 필요
python --version

# 필수 패키지 설치
pip install PyYAML black isort mypy
```

### 설정 파일

`.rfs-quality/config/quality.yaml` 파일을 통해 시스템을 구성합니다:

```yaml
backup:
  enabled: true              # 백업 활성화
  auto_backup: true         # 자동 백업
  retention_days: 7         # 백업 보관 기간
  max_sessions: 10          # 최대 세션 수

quality:
  checks:
    - syntax                # 구문 검사
    - types                 # 타입 검사
    - style                 # 스타일 검사
    - functional            # 함수형 규칙

  transformations:
    safe_mode: true         # 안전 모드
    rollback_on_error: true # 오류 시 롤백
    parallel: false         # 병렬 처리

  thresholds:
    max_violations_increase: 0  # 위반 증가 허용치
    min_quality_score: 85.0     # 최소 품질 점수

  exclusions:
    functional:             # 함수형 규칙 제외 패턴
      - "**/cache*.py"
      - "**/metrics*.py"
      - "**/test_*.py"
    
    directories:            # 제외 디렉토리
      - "__pycache__"
      - ".git"
      - ".pytest_cache"
      - "venv"
```

## 명령어 상세 가이드

### 1. 품질 검사 (check)

코드베이스의 품질을 검사하고 보고서를 생성합니다.

```bash
# 기본 검사
rfs-quality check

# 특정 디렉토리 검사
rfs-quality check src/rfs/core

# 자동 백업과 함께 검사
rfs-quality check --auto-backup

# JSON 형식으로 결과 출력
rfs-quality check --format json
```

**검사 항목:**
- Python 구문 오류
- 타입 힌트 일관성
- 코드 스타일 위반
- 함수형 프로그래밍 위반
- 복잡도 메트릭

**출력 예시:**
```
🔍 품질 검사 시작: src/rfs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 구문 검사: 통과 (0 오류)
⚠️  스타일 검사: 15 위반 발견
❌ 함수형 검사: 8 위반 발견
✅ 타입 검사: 통과

📊 전체 품질 점수: 87.5/100
💡 개선 제안: rfs-quality fix --safe 실행 권장
```

### 2. 자동 수정 (fix)

코드를 자동으로 개선하고 품질 규칙을 적용합니다.

```bash
# 안전 모드로 모든 수정 적용
rfs-quality fix --safe

# 특정 변환만 적용
rfs-quality fix --type functional
rfs-quality fix --type black

# Dry run 모드 (시뮬레이션)
rfs-quality fix --dry-run

# 특정 디렉토리만 수정
rfs-quality fix src/rfs/core --safe
```

**변환 유형 상세:**

#### syntax_fix (구문 수정)
```python
# Before
def function(
    print("unclosed parenthesis"

# After  
def function():
    print("unclosed parenthesis")
```

#### isort (import 정렬)
```python
# Before
import os
from typing import List
import sys
from rfs import Result

# After
import os
import sys
from typing import List

from rfs import Result
```

#### black (코드 포맷팅)
```python
# Before
def function(a,b,c):x=a+b;y=b+c;return x+y

# After
def function(a, b, c):
    x = a + b
    y = b + c
    return x + y
```

#### functional (함수형 패턴)
```python
# Before
result = []
for item in items:
    if item > 0:
        result.append(item * 2)

# After
result = [item * 2 for item in items if item > 0]
# 또는
result = list(map(lambda x: x * 2, filter(lambda x: x > 0, items)))
```

#### match_case (패턴 매칭)
```python
# Before
if command == "start":
    start_service()
elif command == "stop":
    stop_service()
elif command == "restart":
    restart_service()
else:
    print("Unknown command")

# After
match command:
    case "start":
        start_service()
    case "stop":
        stop_service()
    case "restart":
        restart_service()
    case _:
        print("Unknown command")
```

### 3. 백업 관리 (backup)

변경 전후의 코드를 안전하게 관리합니다.

```bash
# 백업 세션 생성
rfs-quality backup create --description "대규모 리팩토링 전"

# 백업 목록 확인
rfs-quality backup list

# 현재 세션 상태
rfs-quality backup status

# 이전 상태로 롤백
rfs-quality backup rollback

# 특정 세션으로 롤백
rfs-quality backup rollback --session session_20240824_143022

# 오래된 백업 정리
rfs-quality backup clear --old

# 모든 백업 삭제 (주의!)
rfs-quality backup clear --all
```

**백업 세션 구조:**
```
.rfs-quality/
├── backups/
│   ├── sessions/
│   │   ├── session_20240824_143022/
│   │   │   ├── manifest.yaml      # 세션 메타데이터
│   │   │   ├── files/            # 백업된 파일들
│   │   │   └── checksums.json    # 무결성 검증
│   │   └── session_20240824_150135/
│   ├── snapshots/                # 스냅샷
│   └── archive/                  # 아카이브
```

### 4. 세션 관리 (session)

작업 세션을 관리하고 메트릭을 추적합니다.

```bash
# 세션 정보 확인
rfs-quality session info

# 세션 메트릭 확인
rfs-quality session metrics

# 세션 내보내기
rfs-quality session export
```

**세션 정보 예시:**
```json
{
  "session_id": "session_20240824_143022",
  "description": "함수형 패턴 적용",
  "timestamp": "2024-08-24T14:30:22",
  "status": "active",
  "files": 45,
  "size_mb": 2.34,
  "metrics": {
    "syntax_errors_fixed": 3,
    "style_violations_fixed": 127,
    "functional_patterns_applied": 18,
    "quality_score_before": 72.5,
    "quality_score_after": 91.3
  }
}
```

## 함수형 프로그래밍 규칙

RFS Framework는 함수형 프로그래밍 원칙을 강제합니다:

### 1. isinstance 사용 금지
```python
# ❌ Bad
if isinstance(obj, str):
    process_string(obj)
elif isinstance(obj, int):
    process_number(obj)

# ✅ Good - SingleDispatch 패턴
from functools import singledispatch

@singledispatch
def process(obj):
    raise NotImplementedError

@process.register(str)
def _(obj: str):
    process_string(obj)

@process.register(int)
def _(obj: int):
    process_number(obj)
```

### 2. 불변성 원칙
```python
# ❌ Bad - 직접 수정
data = {"key": "value"}
data["new_key"] = "new_value"

# ✅ Good - 새 객체 생성
data = {"key": "value"}
new_data = {**data, "new_key": "new_value"}
```

### 3. Result 패턴 사용
```python
# ❌ Bad - Exception 사용
def divide(a, b):
    if b == 0:
        raise ValueError("Division by zero")
    return a / b

# ✅ Good - Result 패턴
from rfs import Result, Success, Failure

def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Failure("Division by zero")
    return Success(a / b)
```

### 4. 반응형 스트림 활용
```python
# ❌ Bad - 명령형 루프
results = []
for item in items:
    if validate(item):
        processed = process(item)
        results.append(processed)

# ✅ Good - 반응형 스트림
from rfs.reactive import Flux

results = await (
    Flux.from_iterable(items)
    .filter(validate)
    .map(process)
    .collect_list()
)
```

## 워크플로우 예시

### 1. 일일 품질 체크
```bash
#!/bin/bash
# daily_quality_check.sh

echo "🔍 일일 품질 체크 시작"

# 1. 백업 생성
rfs-quality backup create --description "일일 품질 체크"

# 2. 품질 검사
rfs-quality check --format json > quality_report.json

# 3. 자동 수정 시도
rfs-quality fix --safe

# 4. 결과 확인
rfs-quality session metrics

# 5. 문제 발생 시 롤백
if [ $? -ne 0 ]; then
    echo "❌ 품질 개선 실패, 롤백 중..."
    rfs-quality backup rollback
fi
```

### 2. 대규모 리팩토링
```bash
# 1단계: 현재 상태 백업
rfs-quality backup create --description "대규모 리팩토링 시작"

# 2단계: Dry run으로 변경사항 확인
rfs-quality fix --dry-run --type all

# 3단계: 단계별 적용
rfs-quality fix --type syntax_fix --safe
rfs-quality fix --type isort --safe
rfs-quality fix --type black --safe
rfs-quality fix --type functional --safe
rfs-quality fix --type match_case --safe

# 4단계: 최종 검증
rfs-quality check

# 5단계: 문제 시 전체 롤백
rfs-quality backup rollback --session [세션ID]
```

### 3. CI/CD 통합
```yaml
# .github/workflows/quality.yml
name: Code Quality Check

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install PyYAML black isort mypy
          pip install -e .
      
      - name: Run quality check
        run: |
          rfs-quality check --format json > quality_report.json
          
      - name: Upload report
        uses: actions/upload-artifact@v2
        with:
          name: quality-report
          path: quality_report.json
          
      - name: Fail if quality score is low
        run: |
          score=$(python -c "import json; print(json.load(open('quality_report.json'))['summary']['quality_score'])")
          if (( $(echo "$score < 85.0" | bc -l) )); then
            echo "❌ Quality score too low: $score"
            exit 1
          fi
```

## 문제 해결

### 일반적인 문제

#### 1. 백업 공간 부족
```bash
# 오래된 백업 정리
rfs-quality backup clear --old

# 아카이브로 이동
find .rfs-quality/backups/sessions -type d -mtime +30 -exec tar czf {}.tar.gz {} \;
```

#### 2. 변환 실패
```bash
# Safe 모드 사용
rfs-quality fix --safe

# 특정 파일 제외
echo "problematic_file.py" >> .rfs-quality/exclusions.txt
```

#### 3. 메모리 부족
```bash
# 디렉토리별로 처리
for dir in src/rfs/*; do
    rfs-quality fix "$dir" --safe
done
```

### 디버깅

```bash
# 상세 로그 활성화
export RFS_QUALITY_DEBUG=1
rfs-quality check

# 로그 파일 확인
tail -f .rfs-quality/logs/quality.log
```

## 성능 최적화

### 병렬 처리
```yaml
# .rfs-quality/config/quality.yaml
quality:
  transformations:
    parallel: true          # 병렬 처리 활성화
    max_workers: 4         # 워커 수
```

### 캐싱
```yaml
cache:
  enabled: true
  ttl: 3600               # 1시간
  max_size_mb: 100
```

### 증분 검사
```bash
# 변경된 파일만 검사
git diff --name-only | xargs rfs-quality check
```

## 모범 사례

### 1. 정기적인 품질 체크
- 일일 자동 검사 설정
- PR 시 품질 게이트 적용
- 월간 품질 보고서 생성

### 2. 단계적 개선
- 한 번에 모든 규칙 적용 지양
- 팀과 합의된 규칙부터 적용
- 점진적 품질 목표 상향

### 3. 백업 전략
- 중요 변경 전 항상 백업
- 세션 설명 명확히 작성
- 정기적인 백업 정리

### 4. 팀 협업
- 품질 설정 파일 공유
- 제외 규칙 문서화
- 품질 메트릭 대시보드 구성

## 고급 설정

### 커스텀 변환기 추가

```python
# unified/transformers.py에 추가
class CustomTransformer(BaseTransformer):
    """커스텀 변환기"""
    
    def transform(self, source: str) -> str:
        # 변환 로직 구현
        return transformed_source
    
    def validate(self, source: str) -> bool:
        # 검증 로직
        return True
```

### 품질 규칙 커스터마이징

```json
// rfs_functional_rules.json 수정
{
  "custom_rule": {
    "enabled": true,
    "severity": "warning",
    "message": "커스텀 규칙 위반",
    "suggestion": "개선 제안",
    "autofix": true
  }
}
```

## 관련 자료

- [RFS Framework Core Patterns](01-core-patterns.md)
- [Configuration Management](03-configuration.md) 
- [CLI Interface](14-cli-interface.md)
- [함수형 프로그래밍 규칙](../scripts/quality/rfs_functional_rules.json)
- [품질 관리 시스템 README](../scripts/quality/README.md)

## 요약

RFS Framework의 코드 품질 관리 시스템은 엔터프라이즈급 Python 프로젝트의 품질을 체계적으로 관리하는 강력한 도구입니다. 자동 백업, 안전한 롤백, 그리고 함수형 프로그래밍 패턴 적용을 통해 코드베이스의 일관성과 품질을 보장합니다.

핵심 명령어:
- `rfs-quality check`: 품질 검사
- `rfs-quality fix --safe`: 안전한 자동 수정
- `rfs-quality backup`: 백업 관리
- `rfs-quality session`: 세션 추적

이 시스템을 통해 17,000줄 이상의 개별 스크립트를 2,000줄의 통합 시스템으로 축소하여 88%의 코드 감소와 함께 유지보수성을 극대화했습니다.