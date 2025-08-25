# HOF Monads API

Higher-Order Functions (HOF) monads API documentation for RFS Framework.

**주요 모나드:**
- `Maybe`: 선택적 값 모나드 (Some/Nothing)
- `Either`: 성공/실패 모나드 (Left/Right)
- `IO`: 또는 부수 효과 모나드

## 사용 예제

### Maybe 모나드

```python
from rfs.hof.monads import Maybe, Some, Nothing

# 값이 있는 경우
maybe_value = Some(42)
print(maybe_value.is_some())  # True
print(maybe_value.is_nothing())  # False
print(maybe_value.get())  # 42

# 값이 없는 경우
maybe_empty = Nothing()
print(maybe_empty.is_some())  # False
print(maybe_empty.is_nothing())  # True

# 안전한 값 추출
print(maybe_value.get_or_else(0))  # 42
print(maybe_empty.get_or_else(0))   # 0

# map을 통한 변환
doubled = maybe_value.map(lambda x: x * 2)
print(doubled.get())  # 84

# Nothing에 map을 적용하면 Nothing 반환
nothing_doubled = maybe_empty.map(lambda x: x * 2)
print(nothing_doubled.is_nothing())  # True

# flatMap으로 체이닝
def safe_divide(x: int, y: int) -> Maybe[float]:
    if y == 0:
        return Nothing()
    return Some(x / y)

result = (
    Some(10)
    .flat_map(lambda x: safe_divide(x, 2))
    .map(lambda x: round(x, 2))
)
print(result.get())  # 5.0

# 안전하지 않은 연산 체이닝
unsafe_result = (
    Some(10)
    .flat_map(lambda x: safe_divide(x, 0))  # Nothing 반환
    .map(lambda x: x * 100)  # 실행되지 않음
)
print(unsafe_result.is_nothing())  # True
```

### Maybe를 활용한 null 안전성

```python
from rfs.hof.monads import Maybe, Some, Nothing
from typing import Dict, Optional

def find_user(user_id: int) -> Maybe[Dict]:
    """사용자를 찾는 함수 (데이터베이스 시뮬레이션)"""
    users = {
        1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
        2: {"id": 2, "name": "Bob", "email": "bob@example.com"}
    }
    
    if user_id in users:
        return Some(users[user_id])
    return Nothing()

def get_user_email(user: Dict) -> Maybe[str]:
    """사용자 이메일 추출"""
    if "email" in user:
        return Some(user["email"])
    return Nothing()

def validate_email(email: str) -> Maybe[str]:
    """이메일 유효성 검사"""
    if "@" in email and "." in email:
        return Some(email)
    return Nothing()

# 안전한 사용자 이메일 처리 파이프라인
def process_user_email(user_id: int) -> str:
    result = (
        find_user(user_id)
        .flat_map(get_user_email)
        .flat_map(validate_email)
        .map(lambda email: email.lower())
    )
    
    return result.get_or_else("Invalid or missing email")

# 사용
print(process_user_email(1))  # "alice@example.com"
print(process_user_email(999))  # "Invalid or missing email"
```

### Either 모나드

```python
from rfs.hof.monads import Either, Left, Right
from typing import Union

# 성공/실패를 나타내는 Either
def parse_int(s: str) -> Either[str, int]:
    """문자열을 정수로 파싱"""
    try:
        return Right(int(s))
    except ValueError:
        return Left(f"Cannot parse '{s}' as integer")

# 나이 검증
def validate_age(age: int) -> Either[str, int]:
    """나이 유효성 검사"""
    if age < 0:
        return Left("Age cannot be negative")
    elif age > 150:
        return Left("Age seems unrealistic")
    else:
        return Right(age)

# 연산 체이닝
def process_age_input(input_str: str) -> Either[str, str]:
    return (
        parse_int(input_str)
        .flat_map(validate_age)
        .map(lambda age: f"Valid age: {age}")
    )

# 사용 예제
print(process_age_input("25"))      # Right("Valid age: 25")
print(process_age_input("abc"))     # Left("Cannot parse 'abc' as integer")
print(process_age_input("-5"))      # Left("Age cannot be negative")
print(process_age_input("200"))     # Left("Age seems unrealistic")

# 패턴 매칭을 통한 처리
result = process_age_input("30")
if result.is_left():
    print(f"Error: {result.get_left()}")
else:
    print(f"Success: {result.get_right()}")
```

### Either를 활용한 에러 누적

```python
from rfs.hof.monads import Either, Left, Right
from typing import List, Dict

def validate_name(name: str) -> Either[List[str], str]:
    """이름 유효성 검사"""
    errors = []
    
    if not name:
        errors.append("Name is required")
    elif len(name) < 2:
        errors.append("Name must be at least 2 characters")
    
    if name and not name[0].isupper():
        errors.append("Name must start with uppercase letter")
    
    return Left(errors) if errors else Right(name)

def validate_email_either(email: str) -> Either[List[str], str]:
    """이메일 유효성 검사"""
    errors = []
    
    if not email:
        errors.append("Email is required")
    elif "@" not in email:
        errors.append("Email must contain @")
    elif "." not in email.split("@")[-1]:
        errors.append("Email domain must contain .")
    
    return Left(errors) if errors else Right(email)

def validate_user_data(name: str, email: str) -> Either[List[str], Dict[str, str]]:
    """사용자 데이터 전체 유효성 검사"""
    name_result = validate_name(name)
    email_result = validate_email_either(email)
    
    # 에러 누적
    all_errors = []
    if name_result.is_left():
        all_errors.extend(name_result.get_left())
    if email_result.is_left():
        all_errors.extend(email_result.get_left())
    
    if all_errors:
        return Left(all_errors)
    
    return Right({
        "name": name_result.get_right(),
        "email": email_result.get_right()
    })

# 사용
valid_user = validate_user_data("Alice", "alice@example.com")
print(valid_user)  # Right({"name": "Alice", "email": "alice@example.com"})

invalid_user = validate_user_data("a", "invalid-email")
if invalid_user.is_left():
    for error in invalid_user.get_left():
        print(f"- {error}")
# - Name must be at least 2 characters
# - Email must contain @
```

### IO 모나드

```python
from rfs.hof.monads import IO
import json

def read_file(filename: str) -> IO[str]:
    """파일 읽기를 나타내는 IO 모나드"""
    def action():
        with open(filename, 'r') as f:
            return f.content()
    return IO(action)

def parse_json(json_str: str) -> IO[dict]:
    """JSON 파싱을 나타내는 IO 모나드"""
    def action():
        return json.loads(json_str)
    return IO(action)

def write_file(filename: str, content: str) -> IO[None]:
    """파일 쓰기를 나타내는 IO 모나드"""
    def action():
        with open(filename, 'w') as f:
            f.write(content)
        return None
    return IO(action)

# IO 연산 체이닝 (지연 실행)
file_processing = (
    read_file("config.json")
    .flat_map(parse_json)
    .map(lambda data: {**data, "processed": True})
    .map(json.dumps)
    .flat_map(lambda processed_json: write_file("output.json", processed_json))
)

# 실제 실행은 run() 호출 시에만 발생
# file_processing.run()  # 실제 파일 I/O 실행

# 순수한 계산과 부수 효과 분리
def pure_computation(data: dict) -> dict:
    """순수한 계산 함수"""
    return {
        **data,
        "timestamp": "2025-01-01T00:00:00Z",
        "version": "1.0"
    }

# IO와 순수 함수 조합
enhanced_processing = (
    read_file("input.json")
    .flat_map(parse_json)
    .map(pure_computation)  # 순수한 변환
    .map(json.dumps)
    .flat_map(lambda result: write_file("enhanced.json", result))
)
```

### 모나드 트랜스포머

```python
from rfs.hof.monads import Maybe, Either, Left, Right, Some, Nothing
from typing import TypeVar, Generic, Callable

T = TypeVar('T')
U = TypeVar('U')
E = TypeVar('E')

class MaybeT(Generic[T]):
    """Maybe Transformer - Maybe를 다른 모나드와 조합"""
    
    def __init__(self, wrapped_maybe):
        self.wrapped_maybe = wrapped_maybe
    
    def map(self, f: Callable[[T], U]) -> 'MaybeT[U]':
        return MaybeT(
            self.wrapped_maybe.map(
                lambda maybe: maybe.map(f)
            )
        )
    
    def flat_map(self, f: Callable[[T], 'MaybeT[U]']) -> 'MaybeT[U]':
        def inner_flat_map(maybe):
            if maybe.is_nothing():
                return maybe
            return f(maybe.get()).wrapped_maybe
        
        return MaybeT(
            self.wrapped_maybe.flat_map(inner_flat_map)
        )

# 데이터베이스 조회 시뮬레이션 (비동기적이고 실패할 수 있음)
def find_user_async(user_id: int) -> Either[str, Maybe[Dict]]:
    """사용자를 비동기적으로 찾기 (실패할 수 있음)"""
    if user_id < 0:
        return Left("Invalid user ID")
    elif user_id == 1:
        return Right(Some({"id": 1, "name": "Alice"}))
    elif user_id == 2:
        return Right(Some({"id": 2, "name": "Bob"}))
    else:
        return Right(Nothing())  # 사용자를 찾을 수 없음

def get_user_permissions(user: Dict) -> Either[str, Maybe[List[str]]]:
    """사용자 권한 조회"""
    permissions_db = {
        1: ["read", "write"],
        2: ["read"]
    }
    
    user_id = user["id"]
    if user_id in permissions_db:
        return Right(Some(permissions_db[user_id]))
    else:
        return Right(Nothing())

# 복합 연산: 사용자 찾기 + 권한 조회
def get_user_with_permissions(user_id: int) -> Either[str, Maybe[Dict]]:
    user_result = find_user_async(user_id)
    
    if user_result.is_left():
        return user_result
    
    maybe_user = user_result.get_right()
    if maybe_user.is_nothing():
        return Right(Nothing())
    
    user = maybe_user.get()
    permissions_result = get_user_permissions(user)
    
    if permissions_result.is_left():
        return permissions_result
    
    maybe_permissions = permissions_result.get_right()
    if maybe_permissions.is_nothing():
        return Right(Some({**user, "permissions": []}))
    
    return Right(Some({
        **user,
        "permissions": maybe_permissions.get()
    }))

# 사용
result = get_user_with_permissions(1)
if result.is_left():
    print(f"Error: {result.get_left()}")
elif result.get_right().is_nothing():
    print("User not found")
else:
    user_with_perms = result.get_right().get()
    print(f"User: {user_with_perms}")
```

### 실제 사용 예제: API 응답 처리

```python
from rfs.hof.monads import Maybe, Either, Left, Right, Some, Nothing
import json
from typing import Dict, List
import requests

def safe_json_parse(response_text: str) -> Either[str, dict]:
    """안전한 JSON 파싱"""
    try:
        return Right(json.loads(response_text))
    except json.JSONDecodeError as e:
        return Left(f"JSON parse error: {e}")

def extract_user_data(api_response: dict) -> Either[str, Dict]:
    """API 응답에서 사용자 데이터 추출"""
    if "data" not in api_response:
        return Left("Missing 'data' field in response")
    
    user_data = api_response["data"]
    required_fields = ["id", "name", "email"]
    
    for field in required_fields:
        if field not in user_data:
            return Left(f"Missing required field: {field}")
    
    return Right(user_data)

def validate_user_response(user: Dict) -> Either[str, Dict]:
    """사용자 데이터 유효성 검사"""
    if not isinstance(user["id"], int):
        return Left("User ID must be an integer")
    
    if not user["email"] or "@" not in user["email"]:
        return Left("Invalid email address")
    
    return Right(user)

# API 응답 처리 파이프라인
def process_api_response(response_text: str) -> Either[str, Dict]:
    """API 응답을 안전하게 처리"""
    return (
        safe_json_parse(response_text)
        .flat_map(extract_user_data)
        .flat_map(validate_user_response)
        .map(lambda user: {
            **user,
            "processed_at": "2025-01-01T00:00:00Z"
        })
    )

# 사용 예제
valid_response = '{"data": {"id": 1, "name": "Alice", "email": "alice@example.com"}}'
invalid_response = '{"data": {"id": "not-a-number", "name": "Bob"}}'
malformed_json = '{"data": invalid json}'

# 각각 처리
for response in [valid_response, invalid_response, malformed_json]:
    result = process_api_response(response)
    
    if result.is_left():
        print(f"Error: {result.get_left()}")
    else:
        print(f"Success: {result.get_right()}")

# 배치 처리
responses = [valid_response, invalid_response, malformed_json]
results = [process_api_response(resp) for resp in responses]

successful_users = [r.get_right() for r in results if r.is_right()]
errors = [r.get_left() for r in results if r.is_left()]

print(f"Processed {len(successful_users)} users successfully")
print(f"Encountered {len(errors)} errors")
```

## 관련 문서

- [Result Pattern](../core/result.md) - Result 모나드 (Either의 특수한 형태)
- [HOF Core](core.md) - 핵심 고차 함수들
- [HOF Collections](collections.md) - 컬렉션 처리 함수들
- [함수형 프로그래밍](../../01-core-patterns.md#functional-programming) - 함수형 패턴 개념