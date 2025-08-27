# 코드 품질 관리 시스템 (Code Quality Management)

## 개요

RFS Framework의 통합 코드 품질 관리 시스템은 엔터프라이즈급 코드베이스의 품질을 체계적으로 관리하고 개선하는 포괄적인 가이드라인입니다. 함수형 프로그래밍 패턴, Result 모나드, 반응형 스트림 등 현대적인 프로그래밍 패러다임을 통해 안전하고 유지보수가 쉬운 코드를 작성할 수 있도록 지원합니다.

## 핵심 품질 원칙

### 🎯 코드 품질 철학
- **함수형 프로그래밍 우선**: 불변성, 순수 함수, 함수 합성
- **타입 안전성**: 완전한 타입 힌트와 정적 타입 검사
- **명시적 오류 처리**: Result 패턴을 통한 예외 없는 에러 핸들링
- **선언적 프로그래밍**: 명령형보다 선언적 스타일 선호

### 🛡️ 안전성 보장
- **불변성 원칙**: 데이터 수정 대신 새로운 객체 생성
- **Railway Oriented Programming**: Result 타입을 통한 오류 전파
- **타입 체크**: Mypy를 통한 정적 타입 검증
- **테스트 우선**: TDD 접근법과 80% 이상 커버리지

### 🔧 코드 스타일
- **PEP 8 준수**: Python 표준 스타일 가이드
- **Black 포맷팅**: 일관된 코드 포맷
- **isort**: 체계적인 import 정렬
- **명확한 네이밍**: 의도가 명확한 변수/함수명

### 📊 품질 메트릭
- **코드 커버리지**: 최소 80% 테스트 커버리지
- **복잡도 관리**: 순환 복잡도 10 이하
- **중복 제거**: DRY 원칙 준수
- **문서화**: 모든 공개 API 문서화

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
rfs-quality backup rollback --session session_20250824_143022

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
│   │   ├── session_20250824_143022/
│   │   │   ├── manifest.yaml      # 세션 메타데이터
│   │   │   ├── files/            # 백업된 파일들
│   │   │   └── checksums.json    # 무결성 검증
│   │   └── session_20250824_150135/
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
  "session_id": "session_20250824_143022",
  "description": "함수형 패턴 적용",
  "timestamp": "2025-08-24T14:30:22",
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

## RFS Framework 코드 품질 표준

### 아키텍처 패턴

#### 1. Result 패턴 (Railway Oriented Programming)
```python
from rfs import Result, Success, Failure

def process_data(data: dict) -> Result[ProcessedData, str]:
    """
    모든 함수는 Result 타입을 반환하여 오류를 명시적으로 처리
    """
    return (
        validate_data(data)
        .bind(transform_data)
        .bind(enrich_data)
        .map(lambda x: ProcessedData(x))
    )
```

#### 2. 반응형 스트림 (Reactive Streams)
```python
from rfs.reactive import Flux, Mono

async def process_stream(items: List[Item]) -> List[ProcessedItem]:
    """
    반응형 스트림을 사용한 비동기 데이터 처리
    """
    return await (
        Flux.from_iterable(items)
        .filter(lambda x: x.is_valid)
        .map(process_item)
        .flat_map(enrich_item)
        .collect_list()
    )
```

#### 3. 의존성 주입 (Dependency Injection)
```python
from rfs.core import inject, stateless

@stateless
class UserService:
    """
    상태가 없는 서비스 컴포넌트
    """
    
    @inject
    def __init__(self, repository: UserRepository):
        self.repository = repository
    
    def get_user(self, user_id: str) -> Result[User, str]:
        return self.repository.find_by_id(user_id)
```

## 함수형 프로그래밍 규칙

RFS Framework는 엄격한 함수형 프로그래밍 원칙을 따릅니다:

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

### 4. 순수 함수 원칙
```python
# ❌ Bad - 부수 효과가 있는 함수
global_state = []

def add_item(item):
    global_state.append(item)  # 전역 상태 변경
    return item

# ✅ Good - 순수 함수
def add_item(items: List[Item], item: Item) -> List[Item]:
    return [*items, item]  # 새로운 리스트 반환
```

### 5. 고차 함수 활용
```python
# ❌ Bad - 명령형 루프
results = []
for item in items:
    if validate(item):
        processed = process(item)
        results.append(processed)

# ✅ Good - 함수형 체이닝
from rfs import pipe, filter_m, map_m

results = pipe(
    items,
    filter_m(validate),
    map_m(process),
    list
)

# HOF 라이브러리 활용 예제
from rfs.hof import compose, curry

transform = compose(
    normalize_data,
    validate_schema,
    enrich_metadata
)
# 더 많은 HOF 패턴은 [HOF Library](22-hot-library.md) 참조

# ✅ Better - 반응형 스트림
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
- [HOF Library](22-hot-library.md) - Higher-Order Functions와 함수형 유틸리티
- [Configuration Management](03-configuration.md) 
- [CLI Interface](14-cli-interface.md)
- [Implementation Status & TBD](99-implementation-status.md)
- [HOF Library](22-hot-library.md) - 함수형 프로그래밍 유틸리티
- [Core Patterns](01-core-patterns.md) - Result 패턴 및 함수형 원칙

## 코드 품질 체크리스트

### 필수 검증 항목
- [ ] 모든 함수가 Result 타입을 반환하는가?
- [ ] 타입 힌트가 완전한가?
- [ ] 테스트 커버리지가 80% 이상인가?
- [ ] 순환 복잡도가 10 이하인가?
- [ ] 모든 공개 API가 문서화되어 있는가?
- [ ] Black/isort 포맷팅이 적용되었는가?
- [ ] Mypy 타입 체크를 통과하는가?
- [ ] 함수형 프로그래밍 원칙을 준수하는가?

### 품질 개선 도구

#### 자동화 도구
```bash
# 코드 포맷팅
black src/
isort src/

# 타입 체크
mypy src/

# 테스트 커버리지
pytest --cov=rfs --cov-report=term-missing

# 보안 스캔
bandit -r src/

# 통합 품질 체크
rfs-cli dev lint
```

#### CI/CD 통합
```yaml
# .github/workflows/quality.yml
name: Code Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -e ".[dev]"
      - run: black --check src/
      - run: isort --check src/
      - run: mypy src/
      - run: pytest --cov=rfs --cov-fail-under=80
      - run: bandit -r src/
```

## 요약

RFS Framework의 코드 품질 관리 시스템은 현대적인 Python 개발의 모범 사례를 체계화한 포괄적인 가이드라인입니다. 함수형 프로그래밍, Result 패턴, 반응형 스트림 등의 고급 패러다임을 통해 안전하고 유지보수가 쉬운 엔터프라이즈급 애플리케이션을 구축할 수 있습니다.

### 핵심 원칙
1. **함수형 프로그래밍**: 불변성, 순수 함수, 함수 합성 ([HOF Library](22-hot-library.md) 참조)
2. **타입 안전성**: 완전한 타입 힌트와 정적 검증
3. **명시적 오류 처리**: Result 패턴으로 예외 없는 프로그래밍
4. **테스트 우선**: TDD와 80% 이상 커버리지
5. **코드 일관성**: Black, isort를 통한 자동 포맷팅

### 도구와 명령어
- `black src/`: 코드 포맷팅
- `mypy src/`: 타입 체크
- `pytest --cov`: 테스트 실행 및 커버리지
- `rfs-cli dev lint`: 통합 품질 검사

이러한 원칙과 도구를 통해 RFS Framework는 엔터프라이즈 환경에서 요구되는 높은 수준의 코드 품질을 보장합니다.