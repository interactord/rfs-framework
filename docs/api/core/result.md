# Result Pattern API

Result pattern API documentation for RFS Framework.

**주요 클래스:**
- `Result`: 기본 Result 모나드 클래스
- `Success`: 성공 상태를 나타내는 클래스
- `Failure`: 실패 상태를 나타내는 클래스

## 사용 예제

### 기본 사용법

```python
from rfs.core.result import Result, Success, Failure

def divide(a: float, b: float) -> Result[float, str]:
    """안전한 나눗셈 함수"""
    if b == 0:
        return Failure("Division by zero")
    return Success(a / b)

# 사용
result = divide(10, 2)
if result.is_success():
    print(f"Result: {result.unwrap()}")  # Result: 5.0
else:
    print(f"Error: {result.unwrap_err()}")
```

### 체이닝

```python
def validate_positive(x: float) -> Result[float, str]:
    if x <= 0:
        return Failure("Must be positive")
    return Success(x)

def square_root(x: float) -> Result[float, str]:
    import math
    return Success(math.sqrt(x))

# 체이닝
result = (
    Success(16.0)
    .bind(validate_positive)
    .bind(square_root)
    .map(lambda x: round(x, 2))
)

print(result.unwrap())  # 4.0
```

### 에러 처리

```python
from typing import Union
from enum import Enum

class ValidationError(Enum):
    EMPTY_INPUT = "empty_input"
    INVALID_FORMAT = "invalid_format" 
    OUT_OF_RANGE = "out_of_range"

def validate_email(email: str) -> Result[str, ValidationError]:
    if not email:
        return Failure(ValidationError.EMPTY_INPUT)
    
    if "@" not in email:
        return Failure(ValidationError.INVALID_FORMAT)
    
    if len(email) > 255:
        return Failure(ValidationError.OUT_OF_RANGE)
    
    return Success(email.lower())

# 사용
result = validate_email("user@example.com")
match result:
    case Success(email):
        print(f"Valid email: {email}")
    case Failure(error):
        print(f"Validation error: {error.value}")
```

## 관련 문서

- [핵심 패턴](../../01-core-patterns.md) - Result 패턴 개념 설명
- [HOF 모나드](../hof/monads.md) - 다른 모나드 패턴