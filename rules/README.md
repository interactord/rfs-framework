# RFS Framework 개발 규칙

RFS Framework를 사용하여 개발할 때 따라야 할 핵심 규칙과 패턴들을 정리한 문서입니다.

## 🔴 필수 준수 규칙

### **[⚠️ 필수 준수 규칙 (Mandatory Rules)](./00-mandatory-rules.md)** 
**모든 개발자와 AI는 반드시 이 규칙을 먼저 읽고 준수해야 합니다:**
- RFS Framework 우선 사용 원칙
- 한글 주석 필수 규칙
- Result 패턴 절대 규칙
- 불변성 및 타입 안정성

## 📚 문서 목록

### 핵심 패턴
1. **[Result Pattern 및 에러 처리](./01-result-pattern.md)**
   - Railway Oriented Programming
   - 명시적 에러 처리
   - Result/Success/Failure 패턴
   - 비동기 Result 처리
   - 다중 Result 조합

2. **[함수형 프로그래밍 작성 규칙](./02-functional-programming.md)**
   - 불변성(Immutability) 원칙
   - 순수 함수(Pure Functions)
   - 고차 함수(Higher-Order Functions)
   - 함수 합성(Composition)
   - 모나드 패턴 (Maybe, Either)
   - 패턴 매칭 활용

### 코드 작성
3. **[코드 스타일 가이드](./03-code-style.md)**
   - 타입 힌트 규칙
   - 명명 규칙
   - 함수 작성 원칙
   - 클래스 설계
   - 비동기 코드 패턴
   - 에러 메시지 작성

4. **[한글 주석 작성 규칙](./09-korean-comments.md)** 🆕
   - 한글 주석 원칙
   - 문서화 스타일
   - 파일별 주석 규칙
   - 패턴별 주석 예시

### 아키텍처
5. **[헥사고날 아키텍처](./04-hexagonal-architecture.md)**
   - 포트-어댑터 패턴
   - 도메인 중심 설계
   - 레이어 분리
   - 의존성 역전
   - 어댑터 구현 패턴

6. **[의존성 주입](./05-dependency-injection.md)**
   - Registry 기반 DI
   - 서비스 스코프 관리
   - 순환 의존성 방지
   - 함수형 레지스트리 패턴
   - 모듈 패턴

7. **[리액티브 프로그래밍](./06-reactive-programming.md)**
   - Mono/Flux 패턴
   - Backpressure 처리
   - Hot vs Cold 스트림
   - 병렬 처리
   - 에러 처리 및 복구

### 개발 프로세스
8. **[테스트 패턴](./07-testing-patterns.md)**
   - Result 패턴 테스트
   - Given-When-Then 구조
   - 비동기 테스트
   - 목 객체 활용
   - 프로퍼티 기반 테스트

9. **[Git 커밋 메시지 작성 규칙](./08-git-commit.md)** 🆕
   - 커밋 타입 및 구조
   - 한글 커밋 메시지 작성법
   - 커밋 분리 원칙
   - Claude 사이니지 제거

## 🎯 핵심 원칙

### 1. 절대 예외를 던지지 마세요
```python
# ❌ 잘못된 방법
if error:
    raise Exception("Error occurred")

# ✅ 올바른 방법
if error:
    return Failure("Error occurred")
```

### 2. 불변성을 유지하세요
```python
# ❌ 잘못된 방법
items.append(new_item)

# ✅ 올바른 방법
new_items = items + [new_item]
```

### 3. 패턴 매칭을 활용하세요
```python
# ❌ if-elif-else 체인
if isinstance(value, int):
    if value > 0:
        return "positive"
    else:
        return "non-positive"

# ✅ 패턴 매칭
match value:
    case int(x) if x > 0:
        return "positive"
    case int(x):
        return "non-positive"
    case _:
        return "not a number"
```

### 4. 타입 힌트는 필수입니다
```python
# ❌ 타입 힌트 없음
def process(data):
    return transform(data)

# ✅ 완전한 타입 힌트
def process(data: Dict[str, Any]) -> Result[ProcessedData, str]:
    return transform(data)
```

### 5. 함수 합성을 활용하세요
```python
# ❌ 중첩된 함수 호출
result = function3(function2(function1(data)))

# ✅ RFS Framework 내장 HOF 사용
from rfs.hof.core import pipe

process = pipe(function1, function2, function3)
result = process(data)
```

### 6. 내장 HOF를 우선 사용하세요 ⭐
```python
# ❌ 커스텀 루프 구현
filtered_items = []
for item in items:
    if condition(item):
        filtered_items.append(transform(item))

# ✅ RFS Framework 내장 HOF 사용
from rfs.hof.collections import compact_map

filtered_items = compact_map(
    lambda item: transform(item) if condition(item) else None,
    items
)
```

## 🚀 빠른 시작

### 프로젝트 설정

```bash
# 프로젝트 생성
mkdir my-project && cd my-project

# RFS Framework 설치
pip install rfs-framework

# 개발 도구 설치
pip install pytest pytest-asyncio pytest-cov black mypy isort
```

### 기본 구조

```
my-project/
├── src/
│   ├── domain/          # 도메인 레이어
│   │   ├── entities/
│   │   ├── services/
│   │   └── value_objects/
│   ├── application/      # 애플리케이션 레이어
│   │   ├── use_cases/
│   │   └── dto/
│   └── infrastructure/   # 인프라 레이어
│       ├── adapters/
│       └── repositories/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── pyproject.toml
```

### 예제 코드

```python
from rfs.core.result import Result, Success, Failure
from rfs.hof.core import pipe
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str

def validate_email(email: str) -> Result[str, str]:
    if "@" not in email:
        return Failure("Invalid email format")
    return Success(email)

def create_user(email: str, name: str) -> Result[User, str]:
    return validate_email(email).map(
        lambda valid_email: User(
            id=generate_id(),
            email=valid_email,
            name=name
        )
    )

# 사용
result = create_user("user@example.com", "John Doe")
if result.is_success():
    user = result.unwrap()
    print(f"User created: {user.name}")
else:
    print(f"Error: {result.unwrap_error()}")
```

## 📋 체크리스트

개발 시 확인해야 할 사항들:

- [ ] 모든 함수가 Result 타입을 반환하는가?
- [ ] 데이터 구조가 불변으로 설계되었는가?
- [ ] 타입 힌트가 완전한가?
- [ ] 패턴 매칭을 활용했는가?
- [ ] **RFS Framework 내장 HOF를 우선 사용했는가?** ⭐
- [ ] `pipe()`, `compose()`, `curry()` 등을 활용했는가?
- [ ] `compact_map()`, `first()`, `partition()` 등을 사용했는가?
- [ ] 의존성이 인터페이스에 의존하는가?
- [ ] 테스트 커버리지가 80% 이상인가?
- [ ] 함수가 순수 함수인가?
- [ ] 에러 메시지가 구체적인가?

## 🔧 개발 도구

### 코드 품질 검사

```bash
# 포맷팅
black src/ tests/
isort src/ tests/

# 타입 체크
mypy src/

# 테스트 실행
pytest --cov=src --cov-report=term-missing

# 모든 검사 실행
make check  # Makefile 설정 필요
```

### pre-commit 설정

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
```

## 📖 추가 리소스

- [RFS Framework 공식 문서](https://rfs-framework.dev)
- [함수형 프로그래밍 in Python](https://github.com/rfs-framework/examples)
- [Railway Oriented Programming](https://fsharpforfunandprofit.com/rop/)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)

## 🤝 기여 가이드

1. 이 규칙들을 숙지하고 따라주세요
2. 새로운 패턴 제안 시 Issue를 먼저 생성해주세요
3. 코드 리뷰 시 이 규칙을 기준으로 검토합니다
4. 규칙 개선 제안은 언제나 환영합니다

---

*이 문서는 RFS Framework v4.3.0 기준으로 작성되었습니다.*