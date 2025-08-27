# 한글 주석 작성 규칙

## 개요

RFS Framework 프로젝트의 모든 코드 주석은 한글로 작성합니다. 이는 팀원 간의 원활한 소통과 코드 이해도를 높이기 위함입니다.

## 기본 원칙

### 1. 한글 우선 정책
- 모든 주석, 문서화 문자열(docstring), TODO 주석을 한글로 작성
- 기술 용어는 영문 그대로 사용 가능
  - 예: API, HTTP, JSON, JWT, Result, Mono, Flux 등
- 코드 자체는 영문 유지 (변수명, 함수명, 클래스명 등)

### 2. 명확성과 간결성
- 불필요한 설명 제거
- 코드가 충분히 명확한 경우 주석 생략 가능
- 복잡한 비즈니스 로직이나 알고리즘은 상세히 설명

### 3. 일관성 유지
- 프로젝트 전체에서 동일한 용어 사용
- 문서화 스타일 통일

## Python 주석 규칙

### 모듈 레벨 문서화
```python
"""
서비스 레지스트리 모듈

서비스 등록 및 검색을 위한 레지스트리 시스템.
의존성 주입과 생명주기 관리를 담당합니다.
"""

from dataclasses import dataclass
from typing import Dict, Any
```

### 클래스 문서화
```python
@dataclass(frozen=True)
class User:
    """
    사용자 엔티티
    
    불변 데이터 클래스로 사용자 정보를 표현합니다.
    모든 속성 변경은 새로운 인스턴스를 생성합니다.
    
    Attributes:
        id: 사용자 고유 식별자
        email: 이메일 주소
        name: 사용자 이름
        roles: 사용자 권한 집합
    """
    id: str
    email: str
    name: str
    roles: FrozenSet[str] = field(default_factory=frozenset)
```

### 함수/메서드 문서화
```python
def create_user(
    email: str, 
    password: str, 
    name: str
) -> Result[User, str]:
    """
    새로운 사용자를 생성합니다.
    
    이메일 중복 검사와 패스워드 검증을 수행한 후
    사용자 엔티티를 생성하여 저장소에 저장합니다.
    
    Args:
        email: 사용자 이메일 주소
        password: 평문 패스워드 (8자 이상)
        name: 사용자 이름
        
    Returns:
        Result[User, str]: 성공 시 User 객체, 실패 시 에러 메시지
        
    Example:
        >>> result = create_user("user@example.com", "password123", "홍길동")
        >>> if result.is_success():
        ...     user = result.unwrap()
        ...     print(f"사용자 생성됨: {user.name}")
    """
    # 이메일 형식 검증
    if "@" not in email:
        return Failure("올바른 이메일 형식이 아닙니다")
    
    # 패스워드 길이 검증
    if len(password) < 8:
        return Failure("패스워드는 8자 이상이어야 합니다")
    
    # 사용자 생성 및 저장
    user = User(
        id=generate_id(),
        email=email,
        name=name
    )
    
    return Success(user)
```

### 인라인 주석
```python
def process_data(items: List[dict]) -> Result[List[dict], str]:
    # 빈 리스트 체크
    if not items:
        return Success([])
    
    results = []
    for item in items:
        # 유효성 검사: 필수 필드 확인
        if "id" not in item:
            return Failure(f"ID가 없는 항목: {item}")
        
        # 데이터 변환: 타임스탬프 추가
        processed = {
            **item,
            "processed_at": datetime.now()
        }
        
        # 불변 리스트 업데이트
        results = results + [processed]
    
    return Success(results)
```

### TODO 주석
```python
# TODO: 캐시 기능 구현 필요 (2024-01-15)
# FIXME: 동시성 문제 해결 필요 - 락 메커니즘 추가
# NOTE: 이 메서드는 성능상 이유로 동기적으로 실행됨
# HACK: 임시 해결책 - 추후 리팩토링 필요
# XXX: 더 이상 사용하지 않음 - 다음 릴리즈에서 제거 예정
```

## 패턴별 주석 예시

### Result 패턴
```python
def divide(a: float, b: float) -> Result[float, str]:
    """
    두 수를 나눕니다.
    
    0으로 나누기를 시도하면 Failure를 반환합니다.
    """
    if b == 0:
        return Failure("0으로 나눌 수 없습니다")
    return Success(a / b)

# 체이닝 예제
result = (
    get_user_input()
    .bind(validate_input)  # 입력 검증
    .bind(parse_number)    # 숫자로 변환
    .map(lambda x: x * 2)  # 값을 두 배로
    .map_error(lambda e: f"처리 실패: {e}")  # 에러 메시지 포맷팅
)
```

### 패턴 매칭
```python
def handle_response(response: Response) -> str:
    """HTTP 응답을 처리하고 적절한 메시지를 반환합니다."""
    
    match response.status_code:
        case 200:
            return "요청 성공"
        case 404:
            return "리소스를 찾을 수 없습니다"
        case 500:
            return "서버 내부 오류"
        case code if 400 <= code < 500:
            return f"클라이언트 오류: {code}"
        case _:
            return f"알 수 없는 상태 코드: {response.status_code}"
```

### 불변성 패턴
```python
class ServiceRegistry:
    """
    서비스 레지스트리
    
    불변성을 유지하면서 서비스를 등록하고 관리합니다.
    """
    
    def register(self, name: str, service: Any) -> None:
        """
        새로운 서비스를 등록합니다.
        
        기존 딕셔너리를 수정하지 않고 새로운 딕셔너리를 생성합니다.
        """
        # ❌ 잘못된 방법: 직접 수정
        # self._services[name] = service
        
        # ✅ 올바른 방법: 새 딕셔너리 생성
        self._services = {**self._services, name: service}
```

### 의존성 주입
```python
@dataclass
class UserService:
    """
    사용자 서비스
    
    생성자 주입을 통해 의존성을 관리합니다.
    """
    
    # 의존성은 인터페이스(Protocol)로 선언
    repository: UserRepository
    email_service: EmailService
    
    def create_user(self, data: dict) -> Result[User, str]:
        """
        사용자를 생성하고 환영 이메일을 발송합니다.
        
        트랜잭션 패턴을 사용하여 모든 작업이 성공해야
        최종 결과를 반환합니다.
        """
        return (
            validate_user_data(data)
            .bind(self.repository.save)     # 저장소에 저장
            .bind(self._send_welcome_email)  # 환영 이메일 발송
        )
```

## 테스트 코드 주석

```python
class TestUserService:
    """UserService 통합 테스트"""
    
    def test_create_user_with_valid_data(self):
        """
        유효한 데이터로 사용자 생성 시 Success를 반환한다.
        
        Given: 유효한 사용자 데이터
        When: create_user 메서드 호출
        Then: Success(User) 반환
        """
        # Given - 테스트 데이터 준비
        user_data = {
            "email": "test@example.com",
            "name": "테스트 사용자"
        }
        
        # When - 실행
        result = self.service.create_user(user_data)
        
        # Then - 검증
        assert result.is_success()
        assert result.unwrap().email == "test@example.com"
```

## 설정 파일 주석

### YAML 파일
```yaml
# RFS Framework 설정 파일
# 환경별 설정을 관리합니다

database:
  # 데이터베이스 연결 설정
  host: localhost  # 호스트 주소
  port: 5432       # PostgreSQL 기본 포트
  name: rfs_db     # 데이터베이스 이름
  
  # 연결 풀 설정
  pool:
    min_size: 5    # 최소 연결 수
    max_size: 20   # 최대 연결 수
    timeout: 30    # 연결 타임아웃 (초)

# 로깅 설정
logging:
  level: INFO      # 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
  format: json     # 로그 형식 (json, text)
```

### JSON 파일
```json
{
  "name": "rfs-framework",
  "version": "4.3.0",
  "description": "엔터프라이즈급 리액티브 함수형 서버리스 프레임워크",
  "scripts": {
    "dev": "개발 서버 실행",
    "test": "테스트 실행",
    "build": "프로덕션 빌드"
  }
}
```

## 특수한 경우

### 1. 외부 라이브러리 오버라이드
```python
class CustomAsyncIterator(AsyncIterator):
    """
    기본 AsyncIterator를 확장한 커스텀 구현
    
    원본 클래스의 동작을 확장하여 Result 패턴을
    지원하도록 수정했습니다.
    """
    
    async def __anext__(self):
        """다음 요소를 가져옵니다 (원본 메서드 오버라이드)"""
        # 원본 동작 호출
        value = await super().__anext__()
        # Result로 래핑
        return Success(value)
```

### 2. 자동 생성 코드
```python
# 이 파일은 자동으로 생성되었습니다.
# 수동으로 수정하지 마세요.
# 생성 도구: protoc-gen-python
# 생성 일시: 2024-01-15 10:30:00

class GeneratedClass:
    """자동 생성된 클래스"""
    pass
```

### 3. API 문서
```python
@app.post("/users", response_model=UserResponse)
async def create_user(request: UserRequest):
    """
    사용자 생성 API
    
    새로운 사용자를 생성하고 JWT 토큰을 발급합니다.
    
    Request Body:
        - email: 이메일 주소
        - password: 패스워드 (8자 이상)
        - name: 사용자 이름
        
    Returns:
        201: 사용자 생성 성공
        400: 잘못된 요청
        409: 이메일 중복
    """
    pass
```

## 주석 작성 체크리스트

### 작성 전 확인사항
- [ ] 한글로 작성되었는가?
- [ ] 의미 있는 정보를 제공하는가?
- [ ] 코드와 일치하는가?
- [ ] 너무 장황하지 않은가?

### 문서화 필수 항목
- [ ] 모든 public 클래스
- [ ] 모든 public 함수/메서드
- [ ] 복잡한 알고리즘
- [ ] 비즈니스 로직
- [ ] 해결 방법이 명확하지 않은 버그 수정

### 피해야 할 주석
- [ ] 코드를 그대로 설명하는 주석
- [ ] 오래되어 틀린 정보
- [ ] 주석 처리된 코드
- [ ] 개인적인 메모

## 예외 사항

### 오픈소스 공개
오픈소스로 공개할 모듈은 영문 주석을 허용하되, 별도 브랜치에서 관리:
```python
"""
Open source module for external use.
This module uses English comments for international collaboration.
"""
```

### 외부 협업
외부 팀과 협업하는 모듈은 사전 협의 후 영문 주석 사용 가능

## 마이그레이션 가이드

### 기존 영문 주석 변환
1. 파일 단위로 점진적 변환
2. 기능 수정 시 해당 부분만 변환
3. 자동 번역 도구 사용 후 검토

### 변환 우선순위
1. 비즈니스 로직 관련 주석
2. 복잡한 알고리즘 설명
3. API 문서
4. 단순 설명 주석