# 핵심 패턴 (Core Patterns)

## 📌 개요

RFS Framework의 핵심은 함수형 프로그래밍의 Result 패턴입니다. 이 패턴을 통해 예외 처리 없이 안전하고 명시적인 에러 처리가 가능합니다.

## 🎯 핵심 개념

### Result 패턴
- **Result[T, E]**: 성공(Success) 또는 실패(Failure)를 나타내는 컨테이너
- **Railway Oriented Programming**: 에러를 명시적으로 처리하는 프로그래밍 패러다임
- **타입 안전성**: 컴파일 타임에 에러 처리 보장

### 모나드 (Monads)
- **Either**: 두 가지 가능한 값 중 하나
- **Maybe**: 값이 있거나 없음을 표현
- **ResultAsync**: 비동기 Result 패턴

## 📚 API 레퍼런스

### Result 클래스

```python
from rfs.core.result import Result, Success, Failure

# 타입 정의
Result[T, E]  # T: 성공 타입, E: 에러 타입
```

### 주요 메서드

| 메서드 | 설명 | 반환 타입 |
|--------|------|-----------|
| `map(func)` | 성공 값을 변환 | `Result[U, E]` |
| `bind(func)` | 체이닝 (flatMap) | `Result[U, E]` |
| `map_error(func)` | 에러 값을 변환 | `Result[T, F]` |
| `unwrap()` | 값 추출 (위험) | `T` |
| `unwrap_or(default)` | 안전한 값 추출 | `T` |
| `is_success()` | 성공 여부 확인 | `bool` |
| `is_failure()` | 실패 여부 확인 | `bool` |

## 💡 사용 예제

### 기본 사용법

```python
from rfs.core.result import Result, Success, Failure

def divide(a: float, b: float) -> Result[float, str]:
    """안전한 나눗셈"""
    if b == 0:
        return Failure("0으로 나눌 수 없습니다")
    return Success(a / b)

# 사용
result = divide(10, 2)
if result.is_success():
    print(f"결과: {result.unwrap()}")  # 결과: 5.0
else:
    print(f"에러: {result.error}")
```

### 체이닝 (Railway Pattern)

```python
from rfs.core.result import Result, Success, Failure

def parse_int(s: str) -> Result[int, str]:
    try:
        return Success(int(s))
    except ValueError:
        return Failure(f"'{s}'는 유효한 정수가 아닙니다")

def validate_positive(n: int) -> Result[int, str]:
    if n > 0:
        return Success(n)
    return Failure("양수여야 합니다")

def double(n: int) -> Result[int, str]:
    return Success(n * 2)

# 파이프라인
result = (
    parse_int("10")
    .bind(validate_positive)
    .bind(double)
)

print(result)  # Success(20)
```

### map과 bind의 차이

```python
# map: 일반 함수를 Result 내부 값에 적용
def add_10(x: int) -> int:
    return x + 10

result = Success(5).map(add_10)  # Success(15)

# bind: Result를 반환하는 함수를 체이닝
def safe_sqrt(x: float) -> Result[float, str]:
    if x < 0:
        return Failure("음수의 제곱근은 계산할 수 없습니다")
    return Success(x ** 0.5)

result = Success(16.0).bind(safe_sqrt)  # Success(4.0)
```

### Either 패턴

```python
from rfs.core.result import Either, Left, Right

def process_data(data: str) -> Either[dict, str]:
    """Left: 에러, Right: 성공"""
    if not data:
        return Left("데이터가 비어있습니다")
    
    try:
        import json
        parsed = json.loads(data)
        return Right(parsed)
    except json.JSONDecodeError as e:
        return Left(f"JSON 파싱 실패: {e}")

# 사용
result = process_data('{"name": "RFS"}')
result.map_right(lambda x: x["name"])  # Right("RFS")
```

### Maybe 패턴

```python
from rfs.core.result import Maybe, Some, Nothing

def find_user(user_id: str) -> Maybe[dict]:
    """사용자 찾기"""
    users = {
        "1": {"name": "김철수", "age": 30},
        "2": {"name": "이영희", "age": 25}
    }
    
    user = users.get(user_id)
    return Some(user) if user else Nothing()

# 사용
user = find_user("1")
name = user.map(lambda u: u["name"]).unwrap_or("Unknown")
print(name)  # 김철수
```

### ResultAsync - 비동기 처리

```python
from rfs.core.result import ResultAsync, Success, Failure
import asyncio

async def fetch_data(url: str) -> Result[dict, str]:
    """비동기 데이터 가져오기"""
    try:
        # 실제로는 aiohttp 등 사용
        await asyncio.sleep(0.1)  # 시뮬레이션
        return Success({"data": "fetched"})
    except Exception as e:
        return Failure(f"Fetch 실패: {e}")

async def process_async():
    result = await ResultAsync.from_coroutine(
        fetch_data("https://api.example.com")
    )
    
    # 비동기 체이닝
    processed = await result.map_async(
        lambda data: process_data_async(data)
    )
    
    return processed
```

### 복잡한 비즈니스 로직 예제

```python
from rfs.core.result import Result, Success, Failure
from dataclasses import dataclass
from typing import List

@dataclass
class Order:
    id: str
    items: List[str]
    total: float

class OrderService:
    def create_order(self, data: dict) -> Result[Order, str]:
        """주문 생성 with 검증"""
        return (
            self._validate_order_data(data)
            .bind(self._check_inventory)
            .bind(self._calculate_price)
            .bind(self._create_order_entity)
            .bind(self._save_to_database)
        )
    
    def _validate_order_data(self, data: dict) -> Result[dict, str]:
        if not data.get("items"):
            return Failure("주문 항목이 없습니다")
        if len(data["items"]) > 10:
            return Failure("한 번에 10개 이상 주문할 수 없습니다")
        return Success(data)
    
    def _check_inventory(self, data: dict) -> Result[dict, str]:
        # 재고 확인 로직
        for item in data["items"]:
            if not self._has_stock(item):
                return Failure(f"{item}의 재고가 부족합니다")
        return Success(data)
    
    def _calculate_price(self, data: dict) -> Result[dict, str]:
        total = sum(self._get_price(item) for item in data["items"])
        data["total"] = total
        return Success(data)
    
    def _create_order_entity(self, data: dict) -> Result[Order, str]:
        order = Order(
            id=self._generate_id(),
            items=data["items"],
            total=data["total"]
        )
        return Success(order)
    
    def _save_to_database(self, order: Order) -> Result[Order, str]:
        # DB 저장 로직
        try:
            # save to db
            return Success(order)
        except Exception as e:
            return Failure(f"DB 저장 실패: {e}")
```

## 🎨 베스트 프랙티스

### 1. 예외 대신 Result 사용

```python
# ❌ 나쁜 예
def get_user(id: str) -> dict:
    user = db.find(id)
    if not user:
        raise UserNotFoundError(f"User {id} not found")
    return user

# ✅ 좋은 예
def get_user(id: str) -> Result[dict, str]:
    user = db.find(id)
    if not user:
        return Failure(f"User {id} not found")
    return Success(user)
```

### 2. 에러 타입 명시

```python
from enum import Enum

class ErrorType(Enum):
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"

@dataclass
class AppError:
    type: ErrorType
    message: str
    details: dict = None

def process(data: dict) -> Result[dict, AppError]:
    if not data:
        return Failure(AppError(
            type=ErrorType.VALIDATION_ERROR,
            message="데이터가 비어있습니다"
        ))
    return Success(data)
```

### 3. 파이프라인 구성

```python
from rfs.core.result import pipe

# 함수 파이프라인
result = pipe(
    input_data,
    validate,
    transform,
    save_to_db,
    send_notification
)

# 또는 메서드 체이닝
result = (
    validate(input_data)
    .bind(transform)
    .bind(save_to_db)
    .bind(send_notification)
)
```

## ⚠️ 주의사항

### 1. unwrap() 사용 주의
- `unwrap()`은 실패 시 예외를 발생시킴
- 항상 `is_success()` 확인 또는 `unwrap_or()` 사용 권장

### 2. 에러 정보 보존
- 에러 체이닝 시 원래 에러 정보 유지
- 디버깅을 위한 충분한 컨텍스트 제공

### 3. 타입 힌트 활용
- 항상 Result의 타입 파라미터 명시
- IDE의 자동완성과 타입 체크 활용

## 🧮 Functional Programming

RFS Framework는 함수형 프로그래밍 패러다임을 지원하며, 고차 함수와 모나드 패턴을 제공합니다.

### 핵심 개념

- **Pure Functions**: 부수 효과 없는 순수 함수
- **Immutability**: 불변성 보장
- **Higher-Order Functions**: 함수를 인자로 받거나 반환하는 함수
- **Monads**: 함수형 프로그래밍의 핵심 패턴

### 고차 함수 (Higher-Order Functions)

```python
from rfs.hof import map_list, filter_list, reduce_list

# 리스트 변환
numbers = [1, 2, 3, 4, 5]
squared = map_list(lambda x: x ** 2, numbers)  # [1, 4, 9, 16, 25]

# 필터링
evens = filter_list(lambda x: x % 2 == 0, numbers)  # [2, 4]

# 축약
total = reduce_list(lambda acc, x: acc + x, 0, numbers)  # 15
```

### 모나드 패턴

```python
from rfs.hof.monads import Maybe, Either, Some, Nothing, Left, Right

# Maybe 모나드
def safe_divide(a: int, b: int) -> Maybe[float]:
    if b == 0:
        return Nothing()
    return Some(a / b)

result = safe_divide(10, 2).map(lambda x: x * 2)  # Some(10.0)

# Either 모나드
def validate_age(age: int) -> Either[str, int]:
    if age < 0:
        return Left("Age cannot be negative")
    return Right(age)

result = validate_age(25).map(lambda age: f"Age: {age}")  # Right("Age: 25")
```

## 🌊 Reactive Programming

리액티브 프로그래밍은 비동기 데이터 스트림을 다루는 패러다임입니다.

### 핵심 개념

- **Observable Streams**: 시간에 따라 변하는 데이터 스트림
- **Operators**: 스트림을 변환하고 조작하는 함수들
- **Backpressure**: 데이터 생산과 소비 속도 조절
- **Schedulers**: 비동기 작업 실행 환경

### Mono와 Flux

```python
from rfs.reactive import Mono, Flux

# Mono - 단일 값 스트림
mono = Mono.just(42).map(lambda x: x * 2)
result = mono.block()  # 84

# Flux - 다중 값 스트림
flux = Flux.from_iterable([1, 2, 3, 4, 5])
even_numbers = flux.filter(lambda x: x % 2 == 0).collect_list().block()  # [2, 4]
```

### 비동기 처리

```python
import asyncio
from rfs.reactive import Mono, Flux

async def async_operation(value: int) -> int:
    await asyncio.sleep(0.1)
    return value * 2

# 비동기 변환
mono = Mono.just(21).flat_map(lambda x: Mono.from_future(async_operation(x)))
result = await mono.to_future()  # 42
```

## 🔗 관련 문서
- [HOF Library](./16-hot-library.md) - Higher-Order Functions와 함수형 프로그래밍 유틸리티
- [의존성 주입](./02-dependency-injection.md)
- [트랜잭션 관리](./04-transactions.md)
- [에러 처리 패턴](./11-security.md)