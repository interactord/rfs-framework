# RFS Framework 규칙 통합 가이드

## 개요

이 문서는 RFS Framework의 모든 규칙들이 어떻게 함께 작동하며, 프로젝트 전체에서 일관되게 적용되도록 보장하는 방법을 설명합니다.

## 🔴 규칙 우선순위 체계

### 레벨 1: 필수 규칙 (Mandatory)
절대 타협 불가능한 규칙들

1. **RFS Framework 우선 사용** (00-mandatory-rules.md)
   - 모든 구현 전 Framework 검색 필수
   - 재사용 가능한 패턴 우선 적용
   
2. **한글 주석 필수** (09-korean-comments.md)
   - 모든 주석, docstring, 문서화
   - Git 커밋 메시지 포함
   
3. **Result 패턴** (01-result-pattern.md)
   - 예외 던지기 절대 금지
   - 모든 에러는 Result로 처리

### 레벨 2: 핵심 패턴 (Core Patterns)
아키텍처의 기반이 되는 패턴들

1. **함수형 프로그래밍** (02-functional-programming.md)
   - 불변성 유지
   - 순수 함수
   - 함수 합성

2. **헥사고날 아키텍처** (04-hexagonal-architecture.md)
   - 포트-어댑터 패턴
   - 도메인 중심 설계
   - 의존성 역전

### 레벨 3: 구현 가이드 (Implementation Guides)
일관된 코드 작성을 위한 지침

1. **코드 스타일** (03-code-style.md)
   - 타입 힌트 필수
   - 패턴 매칭 우선
   - 명명 규칙

2. **테스트 패턴** (07-testing-patterns.md)
   - Given-When-Then 구조
   - Result 패턴 테스트
   - 80% 이상 커버리지

## 🔄 규칙 간 상호작용

### Result + 함수형 프로그래밍
```python
# Result 체이닝과 함수 합성
from rfs.core.result import Result
from rfs.hof.core import pipe

# 함수 합성으로 Result 파이프라인 구성
process_user = pipe(
    validate_input,      # Result[dict, str]
    bind(parse_user),    # Result[User, str]
    bind(save_to_db),    # Result[User, str]
    map(send_email)      # Result[EmailResult, str]
)

# 사용
result = process_user(user_data)
```

### 헥사고날 + 의존성 주입
```python
# 도메인 레이어 (순수 비즈니스 로직)
@dataclass(frozen=True)
class CreateUserUseCase:
    """사용자 생성 유스케이스"""
    
    repository: UserRepository  # 포트 (인터페이스)
    
    def execute(self, data: dict) -> Result[User, str]:
        """사용자를 생성하고 저장합니다."""
        return (
            validate_user_data(data)
            .bind(self._create_user)
            .bind(self.repository.save)  # 어댑터 호출
        )

# 인프라 레이어 (어댑터 구현)
@stateless
class PostgresUserRepository(UserRepository):
    """PostgreSQL 사용자 저장소 구현"""
    
    def save(self, user: User) -> Result[User, str]:
        """PostgreSQL에 사용자를 저장합니다."""
        # 실제 DB 저장 로직
        pass

# 의존성 주입으로 연결
registry.register(
    UserRepository,
    PostgresUserRepository,
    scope=ServiceScope.SINGLETON
)
```

### 리액티브 + Result
```python
# 비동기 스트림과 Result 통합
from rfs.reactive.mono import Mono

def fetch_user_async(user_id: str) -> Mono[User]:
    """비동기로 사용자를 조회합니다."""
    return (
        Mono.from_callable(lambda: fetch_from_db(user_id))
        .map(lambda data: parse_user(data))  # Result 반환
        .filter(lambda r: r.is_success())
        .map(lambda r: r.unwrap())
        .on_error_resume(lambda e: Mono.empty())
    )
```

## 📋 프로젝트 설정 체크리스트

### 1. 초기 설정
```bash
# .rfs-rules 파일 확인
cat .rfs-rules

# pre-commit 훅 설정
pip install pre-commit
pre-commit install

# 한글 주석 검증 도구 설치
pip install rfs-lint
```

### 2. 개발 환경 설정
```python
# pyproject.toml
[tool.rfs]
mandatory_rules = true
korean_comments = true
result_pattern = true
immutable_only = true

[tool.black]
line-length = 88

[tool.mypy]
strict = true
```

### 3. CI/CD 파이프라인
```yaml
# .github/workflows/ci.yml
name: RFS Framework CI

on: [push, pull_request]

jobs:
  validate-rules:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: RFS 규칙 검증
        run: |
          # 한글 주석 검증
          python scripts/validate_korean_comments.py
          
          # Result 패턴 검증
          python scripts/validate_result_pattern.py
          
          # 불변성 검증
          python scripts/validate_immutability.py
      
      - name: 테스트 실행
        run: |
          pytest --cov=src --cov-report=term-missing
          
      - name: 커버리지 검증
        run: |
          coverage report --fail-under=80
```

## 🚨 규칙 위반 감지

### 자동 검증 스크립트
```python
# scripts/validate_rules.py
"""RFS Framework 규칙 검증 스크립트"""

from pathlib import Path
import ast
import sys

def check_result_pattern(file_path: Path) -> list[str]:
    """Result 패턴 사용을 검증합니다."""
    violations = []
    
    with open(file_path) as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        # raise 문 감지
        if isinstance(node, ast.Raise):
            violations.append(
                f"{file_path}:{node.lineno} - "
                f"예외 발생 감지. Result 패턴을 사용하세요."
            )
    
    return violations

def check_korean_comments(file_path: Path) -> list[str]:
    """한글 주석 사용을 검증합니다."""
    violations = []
    
    with open(file_path, encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            # 영문 주석 감지
            if '#' in line:
                comment = line.split('#', 1)[1].strip()
                if comment and not any(ord(c) > 127 for c in comment):
                    violations.append(
                        f"{file_path}:{line_no} - "
                        f"영문 주석 감지. 한글로 작성하세요."
                    )
    
    return violations

def main():
    """모든 Python 파일을 검증합니다."""
    src_path = Path("src")
    all_violations = []
    
    for py_file in src_path.rglob("*.py"):
        violations = []
        violations.extend(check_result_pattern(py_file))
        violations.extend(check_korean_comments(py_file))
        
        if violations:
            all_violations.extend(violations)
    
    if all_violations:
        print("❌ RFS Framework 규칙 위반:")
        for violation in all_violations:
            print(f"  - {violation}")
        sys.exit(1)
    else:
        print("✅ 모든 RFS Framework 규칙 준수")

if __name__ == "__main__":
    main()
```

## 🎯 통합 예제: 완전한 기능 구현

### 모든 규칙을 적용한 사용자 관리 시스템
```python
"""
사용자 관리 모듈

RFS Framework의 모든 규칙을 준수하는 예제 구현입니다.
"""

from dataclasses import dataclass
from typing import Protocol
from rfs.core.result import Result, Success, Failure
from rfs.core.registry import Registry, stateless, inject, Injected
from rfs.hof.core import pipe, curry
from rfs.reactive.mono import Mono

# 헥사고날 아키텍처: 포트 정의
class UserRepository(Protocol):
    """사용자 저장소 인터페이스"""
    
    def find_by_email(self, email: str) -> Result[User, str]:
        """이메일로 사용자를 조회합니다."""
        ...
    
    def save(self, user: User) -> Result[User, str]:
        """사용자를 저장합니다."""
        ...

# 도메인 엔티티 (불변)
@dataclass(frozen=True)
class User:
    """사용자 엔티티"""
    id: str
    email: str
    name: str
    
    def with_name(self, name: str) -> "User":
        """새로운 이름으로 사용자를 업데이트합니다."""
        # 불변성 유지: 새 인스턴스 생성
        return User(id=self.id, email=self.email, name=name)

# 유스케이스 (순수 함수형)
@stateless
class CreateUserUseCase:
    """사용자 생성 유스케이스"""
    
    @inject
    def __init__(self, repository: UserRepository = Injected):
        """의존성 주입으로 저장소를 받습니다."""
        self.repository = repository
    
    def execute(self, email: str, name: str) -> Result[User, str]:
        """
        새로운 사용자를 생성합니다.
        
        Args:
            email: 사용자 이메일
            name: 사용자 이름
            
        Returns:
            Result[User, str]: 성공 시 사용자, 실패 시 에러 메시지
        """
        # Result 패턴: 예외 대신 Failure 반환
        return (
            self._validate_email(email)
            .bind(lambda _: self._check_duplicate(email))
            .bind(lambda _: self._create_user(email, name))
            .bind(self.repository.save)
        )
    
    def _validate_email(self, email: str) -> Result[str, str]:
        """이메일 형식을 검증합니다."""
        # 패턴 매칭 사용
        match email:
            case str() if "@" in email and "." in email:
                return Success(email)
            case _:
                return Failure("올바른 이메일 형식이 아닙니다")
    
    def _check_duplicate(self, email: str) -> Result[None, str]:
        """이메일 중복을 확인합니다."""
        result = self.repository.find_by_email(email)
        
        # 패턴 매칭으로 Result 처리
        match result:
            case Failure(_):
                # 사용자가 없으면 성공
                return Success(None)
            case Success(_):
                return Failure("이미 등록된 이메일입니다")
    
    def _create_user(self, email: str, name: str) -> Result[User, str]:
        """사용자 객체를 생성합니다."""
        import uuid
        
        # 불변 객체 생성
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name
        )
        return Success(user)

# 리액티브 확장
class ReactiveUserService:
    """리액티브 사용자 서비스"""
    
    def __init__(self, use_case: CreateUserUseCase):
        """유스케이스를 주입받습니다."""
        self.use_case = use_case
    
    def create_user_async(self, email: str, name: str) -> Mono[User]:
        """
        비동기로 사용자를 생성합니다.
        
        백프레셔와 재시도 로직을 포함합니다.
        """
        return (
            Mono.from_callable(
                lambda: self.use_case.execute(email, name)
            )
            .map(lambda result: result.unwrap_or_raise())
            .retry(3)  # 3번 재시도
            .on_error_resume(
                lambda e: Mono.error(f"사용자 생성 실패: {e}")
            )
        )

# 함수 합성 예제
def create_and_notify_user(
    email: str, 
    name: str,
    use_case: CreateUserUseCase,
    notifier: EmailNotifier
) -> Result[str, str]:
    """사용자를 생성하고 알림을 발송합니다."""
    
    # 함수 합성으로 파이프라인 구성
    process = pipe(
        use_case.execute,
        bind(lambda user: notifier.send_welcome(user)),
        map(lambda _: "사용자 생성 및 알림 발송 완료")
    )
    
    return process(email, name)
```

## 📊 규칙 적용 메트릭

### 측정 지표
1. **Result 패턴 적용률**: 95% 이상
2. **한글 주석 비율**: 100%
3. **불변성 준수율**: 90% 이상
4. **테스트 커버리지**: 80% 이상
5. **패턴 매칭 사용률**: 70% 이상

### 측정 도구
```python
# scripts/measure_compliance.py
"""규칙 준수 메트릭 측정 스크립트"""

def measure_compliance(project_path: Path) -> dict:
    """프로젝트의 규칙 준수도를 측정합니다."""
    return {
        "result_pattern": calculate_result_usage(),
        "korean_comments": calculate_korean_ratio(),
        "immutability": calculate_immutable_usage(),
        "test_coverage": get_test_coverage(),
        "pattern_matching": calculate_match_usage(),
    }
```

## 🔧 도구 및 자동화

### VSCode 설정
```json
{
  "rfs.enableRuleValidation": true,
  "rfs.enforceKoreanComments": true,
  "rfs.enforceResultPattern": true,
  "python.linting.enabled": true,
  "python.linting.pylintArgs": [
    "--load-plugins=rfs_lint"
  ]
}
```

### Pre-commit 훅
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: rfs-rules
        name: RFS Framework Rules
        entry: python scripts/validate_rules.py
        language: python
        files: \.py$
        
      - id: korean-comments
        name: Korean Comments Check
        entry: python scripts/check_korean_comments.py
        language: python
        files: \.py$
```

## 🚀 마이그레이션 가이드

### 기존 코드 변환
1. **예외 처리 → Result 패턴**
   ```python
   # Before
   def process(data):
       if not data:
           raise ValueError("No data")
       return transform(data)
   
   # After
   def process(data) -> Result[Any, str]:
       if not data:
           return Failure("데이터가 없습니다")
       return Success(transform(data))
   ```

2. **영문 주석 → 한글 주석**
   ```python
   # Before
   # Process user data
   
   # After
   # 사용자 데이터를 처리합니다
   ```

3. **if-elif → 패턴 매칭**
   ```python
   # Before
   if isinstance(value, int):
       return "integer"
   elif isinstance(value, str):
       return "string"
   
   # After
   match value:
       case int():
           return "정수"
       case str():
           return "문자열"
   ```

## 📝 규칙 업데이트 프로세스

### 새로운 규칙 제안
1. Issue 생성 with 'rule-proposal' 라벨
2. 토론 및 검토
3. PR 작성 with 예제 코드
4. 승인 및 병합
5. 자동화 도구 업데이트

### 규칙 버전 관리
- 모든 규칙은 버전 관리됨
- 변경 사항은 CHANGELOG에 기록
- 하위 호환성 유지

## 🎓 교육 및 온보딩

### 신규 개발자 체크리스트
- [ ] 필수 규칙 문서 읽기 (00-mandatory-rules.md)
- [ ] Result 패턴 이해 (01-result-pattern.md)
- [ ] 함수형 프로그래밍 학습 (02-functional-programming.md)
- [ ] 예제 코드 실행 및 분석
- [ ] 첫 PR 작성 with 멘토 리뷰

### 학습 리소스
- [RFS Framework Wiki](/wiki)
- [예제 프로젝트](/examples)
- [비디오 튜토리얼](https://rfs-framework.dev/tutorials)

## 💡 베스트 프랙티스

### DO
- ✅ 모든 함수에 Result 타입 사용
- ✅ 데이터 구조를 불변으로 설계
- ✅ 패턴 매칭으로 명확한 분기 처리
- ✅ 한글로 의미 있는 주석 작성
- ✅ Framework 기능 우선 사용

### DON'T
- ❌ 비즈니스 로직에서 예외 던지기
- ❌ 직접 상태 변경
- ❌ 긴 if-elif 체인
- ❌ 영문 주석이나 주석 없는 코드
- ❌ Framework 기능 재구현

## 🔮 향후 계획

### 단기 (1-3개월)
- 자동화 도구 강화
- IDE 플러그인 개발
- 규칙 검증 성능 개선

### 중기 (3-6개월)
- AI 기반 코드 리뷰
- 실시간 규칙 제안
- 팀 대시보드

### 장기 (6개월+)
- 규칙 기반 코드 생성
- 자동 리팩토링
- 커스텀 규칙 지원

---

*이 문서는 RFS Framework v4.3.0 기준으로 작성되었습니다.*
*최신 업데이트: 2024-01-15*