# 필수 준수 규칙 (Mandatory Rules)

> ⚠️ **이 문서의 규칙들은 반드시 준수해야 하는 필수 규칙입니다**
> 
> 모든 개발자와 AI 어시스턴트는 예외 없이 이 규칙들을 따라야 합니다.

## 🔴 최우선 규칙 (Critical Priority)

### 1. RFS Framework 우선 사용 원칙

**절대 규칙**: 기능 구현 전 반드시 RFS Framework 내장 기능 확인

#### 필수 확인 절차
```
1. RFS Framework 검색 → 2. 패턴 확인 → 3. 재사용 → 4. 없을 때만 신규 구현
```

#### 검색 우선순위
1. **내장 컴포넌트 확인**
   - `src/rfs/core/` - Result, Registry, Config
   - `src/rfs/hof/` - 함수형 유틸리티
   - `src/rfs/reactive/` - Mono, Flux 패턴
   - `src/rfs/state_machine/` - 상태 관리

2. **기존 패턴 검색**
   ```python
   # ❌ 잘못된 방법: 즉시 커스텀 구현
   def custom_validator(data):
       if not data:
           raise ValueError("Invalid")
   
   # ✅ 올바른 방법: Framework 패턴 사용
   from rfs.core.result import Result, Success, Failure
   
   def validate_data(data: dict) -> Result[dict, str]:
       if not data:
           return Failure("데이터가 없습니다")
       return Success(data)
   ```

3. **Framework 기능 활용 체크리스트**
   - [ ] Result 패턴으로 에러 처리하는가?
   - [ ] Registry로 의존성 주입하는가?
   - [ ] HOF 유틸리티를 활용하는가?
   - [ ] Reactive 패턴을 사용하는가?
   - [ ] 기존 패턴을 따르는가?

### 2. 한글 주석 필수 규칙

**절대 규칙**: 모든 주석은 한글로 작성

#### 적용 범위
- ✅ 모든 Python 파일의 주석
- ✅ Docstring (모듈, 클래스, 함수)
- ✅ 인라인 주석
- ✅ TODO, FIXME, NOTE 주석
- ✅ 설정 파일 주석 (YAML, JSON)

#### 필수 문서화 대상
```python
# 모든 public 함수는 반드시 한글 docstring 포함
def process_user_data(data: dict) -> Result[User, str]:
    """
    사용자 데이터를 처리하고 User 엔티티를 생성합니다.
    
    Args:
        data: 사용자 입력 데이터 딕셔너리
        
    Returns:
        Result[User, str]: 성공 시 User 객체, 실패 시 에러 메시지
        
    Raises:
        절대 예외를 발생시키지 않음 (Result 패턴 사용)
    """
    # 입력 검증: 필수 필드 확인
    if not data.get("email"):
        return Failure("이메일은 필수입니다")
    
    # 사용자 생성 및 반환
    return Success(User(**data))
```

### 3. Result 패턴 절대 규칙

**절대 규칙**: 비즈니스 로직에서 예외를 던지지 않음

#### 필수 패턴
```python
# ❌ 절대 금지: 예외 던지기
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")  # 금지!
    return a / b

# ✅ 필수: Result 패턴
def divide(a: float, b: float) -> Result[float, str]:
    if b == 0:
        return Failure("0으로 나눌 수 없습니다")
    return Success(a / b)
```

#### Result 체이닝 필수
```python
# 모든 연산은 Result 체이닝으로 연결
result = (
    fetch_user_data(user_id)
    .bind(validate_user)      # 검증
    .bind(enrich_user_data)   # 데이터 보강
    .bind(save_to_database)   # 저장
    .map_error(lambda e: f"사용자 처리 실패: {e}")
)
```

## 🟡 핵심 운영 규칙 (Core Operational)

### 파일 작업 보안
1. **Read-Before-Write**: Write/Edit 전 반드시 Read
2. **절대 경로 사용**: 상대 경로 금지
3. **배치 작업 선호**: 트랜잭션 방식 작업
4. **자동 커밋 금지**: 명시적 요청 시만 커밋

### 코드베이스 변경 절차
1. **전체 검색 필수**: 변경 전 모든 참조 검색
2. **영향 분석**: 의존성과 관계 파악
3. **계획 수립**: 변경 순서 결정
4. **검증**: 변경 후 기능 동작 확인

## 🟢 프레임워크 준수 규칙

### 1. 패턴 매칭 우선
```python
# ✅ 패턴 매칭 사용
match scope:
    case ServiceScope.SINGLETON:
        return self._get_singleton(name)
    case ServiceScope.PROTOTYPE:
        return self._create_instance(name)
    case _:
        return Failure(f"알 수 없는 스코프: {scope}")
```

### 2. 불변성 유지
```python
# ✅ 불변 업데이트
self._definitions = {**self._definitions, name: definition}
self._items = self._items + [new_item]

# ❌ 직접 수정 금지
self._definitions[name] = definition  # 금지!
self._items.append(new_item)  # 금지!
```

### 3. 타입 힌트 필수
```python
# 모든 함수는 완전한 타입 힌트 포함
def process(
    data: Dict[str, Any],
    options: Optional[Config] = None
) -> Result[ProcessedData, str]:
    pass
```

## 📋 필수 체크리스트

### 코드 작성 전
- [ ] RFS Framework에서 기존 구현 검색했는가?
- [ ] 재사용 가능한 패턴이 있는가?
- [ ] Result 패턴을 사용하는가?

### 코드 작성 중
- [ ] 모든 주석을 한글로 작성했는가?
- [ ] 예외 대신 Result를 반환하는가?
- [ ] 불변성을 유지하는가?
- [ ] 타입 힌트가 완전한가?

### 코드 작성 후
- [ ] 테스트가 Result 패턴을 사용하는가?
- [ ] 문서화가 한글로 되어 있는가?
- [ ] Framework 패턴을 따르는가?

## 🚨 위반 시 조치

### 즉시 수정 필요
1. 예외를 던지는 비즈니스 로직 → Result 패턴으로 변경
2. 영문 주석 → 한글로 번역
3. 커스텀 구현 → Framework 기능으로 대체

### 코드 리뷰 거부 사유
- RFS Framework 기능 미사용
- Result 패턴 미적용
- 한글 주석 미작성
- 불변성 위반

## 📌 영구 적용 선언

이 규칙들은 RFS Framework 프로젝트의 **영구적이고 변경 불가능한** 규칙입니다:

1. **RFS Framework 우선 사용** - 예외 없음
2. **한글 주석 필수** - 예외 없음
3. **Result 패턴 필수** - 예외 없음
4. **불변성 유지** - 예외 없음
5. **타입 안정성** - 예외 없음

> 💡 **Remember**: 이 규칙들은 코드 품질과 일관성을 위한 최소 요구사항입니다.
> 모든 기여자는 이를 준수해야 하며, AI 어시스턴트는 이를 자동으로 적용해야 합니다.