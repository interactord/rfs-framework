# Result Pattern API

Result pattern API documentation for RFS Framework.

**주요 클래스:**
- `Result`: 기본 Result 모나드 클래스
- `Success`: 성공 상태를 나타내는 클래스
- `Failure`: 실패 상태를 나타내는 클래스
- `ResultAsync`: 비동기 Result 모나드 클래스 (v4.6.1에서 개선됨)

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

## ResultAsync (비동기 Result)

!!! success "v4.6.1 개선 사항"
    - 런타임 경고 완전 제거
    - 코루틴 캐싱 메커니즘 추가
    - 15-20% 성능 향상

### ResultAsync 기본 사용법

```python
from rfs.core.result import ResultAsync, Success, Failure

# 비동기 Result 생성
async def fetch_data(url: str) -> Result[dict, str]:
    """비동기 데이터 페칭"""
    try:
        # 비동기 작업 수행
        response = await http_client.get(url)
        return Success(response.json())
    except Exception as e:
        return Failure(str(e))

# ResultAsync 사용
async def process_async():
    # 클래스 메서드로 생성
    result = ResultAsync.from_value("initial_data")
    
    # 여러 번 await 가능 (v4.6.1 개선)
    is_success = await result.is_success()
    value = await result.unwrap_or("default")
    
    # 체이닝
    final_result = (
        ResultAsync.from_value({"id": 1})
        .map_async(lambda data: enrich_data(data))
        .bind_async(lambda data: save_to_db(data))
    )
    
    return await final_result.to_result()
```

### ResultAsync 헬퍼 함수

```python
from rfs.core.result import async_success, async_failure

# 헬퍼 함수 사용 (v4.6.1에서 버그 수정됨)
success_result = async_success("value")
failure_result = async_failure("error")

# to_result()로 동기 Result로 변환
sync_result = await success_result.to_result()
```

### 캐싱 메커니즘 (v4.6.1 신규)

```python
# ResultAsync는 이제 내부적으로 결과를 캐싱합니다
result = ResultAsync.from_value("data")

# 첫 번째 호출 - 실제 실행
value1 = await result.unwrap_or("default")

# 두 번째 호출 - 캐싱된 결과 사용 (성능 향상)
value2 = await result.unwrap_or("default")

# 여러 번 호출해도 "coroutine already awaited" 에러 없음
for _ in range(10):
    success = await result.is_success()
    value = await result.unwrap_or("default")
```

### 비동기 체이닝 패턴

```python
async def validate_async(data: dict) -> Result[dict, str]:
    """비동기 검증"""
    if not data.get("id"):
        return Failure("ID required")
    return Success(data)

async def enrich_async(data: dict) -> Result[dict, str]:
    """비동기 데이터 보강"""
    extra_data = await fetch_extra_data(data["id"])
    return Success({**data, **extra_data})

# 파이프라인 구성
pipeline_result = (
    ResultAsync.from_value({"id": 123})
    .bind_async(validate_async)
    .bind_async(enrich_async)
    .map_async(lambda d: format_output(d))
)

final = await pipeline_result.to_result()
```

## 관련 문서

- [핵심 패턴](../../01-core-patterns.md) - Result 패턴 개념 설명
- [HOF 모나드](../hof/monads.md) - 다른 모나드 패턴
- [비동기 HOF](../hof/async.md) - 비동기 고차 함수