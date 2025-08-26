# 함수형 프로그래밍 작성 규칙

## 핵심 원칙

1. **불변성(Immutability)**: 데이터는 변경하지 않고 새로운 데이터를 생성
2. **순수 함수(Pure Functions)**: 부작용 없이 동일 입력에 동일 출력
3. **함수 합성(Function Composition)**: 작은 함수들을 조합하여 복잡한 로직 구성
4. **타입 안정성(Type Safety)**: 완전한 타입 힌트로 컴파일 타임 안정성 확보

## 불변성 규칙

### 1. 데이터 구조는 불변으로

```python
# ❌ 잘못된 방법 - 가변 데이터
class User:
    def __init__(self, name: str):
        self.name = name
        self.roles = []  # 가변 리스트
    
    def add_role(self, role: str):
        self.roles.append(role)  # 직접 수정

# ✅ 올바른 방법 - 불변 데이터
from dataclasses import dataclass, field
from typing import FrozenSet

@dataclass(frozen=True)
class User:
    name: str
    roles: FrozenSet[str] = field(default_factory=frozenset)
    
    def with_role(self, role: str) -> "User":
        return User(
            name=self.name,
            roles=self.roles | {role}  # 새 집합 생성
        )
```

### 2. 리스트 연산은 새 리스트 반환

```python
# ❌ 잘못된 방법
def add_item(items: list, item):
    items.append(item)  # 원본 수정
    return items

# ✅ 올바른 방법
def add_item(items: list, item) -> list:
    return items + [item]  # 새 리스트 반환

# 또는 스프레드 연산자 스타일
def add_item(items: list, item) -> list:
    return [*items, item]
```

### 3. 딕셔너리 업데이트

```python
# ❌ 잘못된 방법
def update_config(config: dict, key: str, value):
    config[key] = value
    return config

# ✅ 올바른 방법
def update_config(config: dict, key: str, value) -> dict:
    return {**config, key: value}  # 새 딕셔너리 반환
```

## 순수 함수 규칙

### 1. 부작용 제거

```python
# ❌ 잘못된 방법 - 부작용 있음
total = 0
def add_to_total(value: int) -> int:
    global total
    total += value  # 외부 상태 변경
    return total

# ✅ 올바른 방법 - 순수 함수
def add(a: int, b: int) -> int:
    return a + b

# 상태 관리는 함수형 방식으로
from functools import reduce
values = [1, 2, 3, 4, 5]
total = reduce(add, values, 0)
```

### 2. I/O는 Result로 격리

```python
# ❌ 잘못된 방법 - 직접 I/O
def save_user(user: User):
    with open("users.json", "w") as f:
        json.dump(user.__dict__, f)

# ✅ 올바른 방법 - Result로 격리
def save_user(user: User) -> Result[None, str]:
    try:
        with open("users.json", "w") as f:
            json.dump(asdict(user), f)
        return Success(None)
    except IOError as e:
        return Failure(f"파일 저장 실패: {e}")
```

## 고차 함수 활용

### 1. 함수 합성 (Composition)

```python
from rfs.hof.core import compose, pipe

# compose: 오른쪽에서 왼쪽으로
add_one = lambda x: x + 1
multiply_two = lambda x: x * 2
square = lambda x: x ** 2

# (x + 1) * 2 ^ 2
process = compose(square, multiply_two, add_one)
result = process(5)  # ((5 + 1) * 2) ^ 2 = 144

# pipe: 왼쪽에서 오른쪽으로 (더 직관적)
process = pipe(add_one, multiply_two, square)
result = process(5)  # 동일한 결과
```

### 2. 커링 (Currying)

```python
from rfs.hof.core import curry

# 일반 함수
def add(a: int, b: int, c: int) -> int:
    return a + b + c

# 커링된 함수
curried_add = curry(add, 3)
add_5 = curried_add(5)  # 부분 적용
add_5_10 = add_5(10)  # 또 부분 적용
result = add_5_10(15)  # 30

# 실용적인 예제
@curry
def filter_by_field(field: str, value: Any, items: list) -> list:
    return [item for item in items if getattr(item, field) == value]

# 재사용 가능한 필터 생성
filter_active = filter_by_field("status", "active")
active_users = filter_active(users)
active_orders = filter_active(orders)
```

### 3. 부분 적용 (Partial Application)

```python
from functools import partial
from rfs.hof.core import partial as rfs_partial

# 설정된 로거 생성
def log(level: str, module: str, message: str):
    print(f"[{level}] {module}: {message}")

info_log = partial(log, "INFO")
error_log = partial(log, "ERROR")

user_info = partial(info_log, "UserModule")
user_error = partial(error_log, "UserModule")

user_info("User created")  # [INFO] UserModule: User created
user_error("User creation failed")  # [ERROR] UserModule: User creation failed
```

## 컬렉션 함수형 처리

### 1. map/filter/reduce 패턴

```python
from functools import reduce
from rfs.hof.collections import compact_map, flat_map

# 전통적인 map/filter/reduce
numbers = [1, 2, 3, 4, 5]
result = reduce(
    lambda acc, x: acc + x,
    filter(lambda x: x % 2 == 0,
           map(lambda x: x * 2, numbers)),
    0
)

# pipe를 활용한 체이닝
from rfs.hof.core import pipe

process = pipe(
    lambda xs: map(lambda x: x * 2, xs),
    lambda xs: filter(lambda x: x % 2 == 0, xs),
    lambda xs: reduce(lambda acc, x: acc + x, xs, 0)
)
result = process(numbers)

# compact_map: None 제거하며 매핑
def parse_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        return None

strings = ["1", "2", "abc", "4"]
numbers = compact_map(parse_int, strings)  # [1, 2, 4]

# flat_map: 중첩 리스트 평탄화
def duplicate(x: int) -> list[int]:
    return [x, x]

result = flat_map(duplicate, [1, 2, 3])  # [1, 1, 2, 2, 3, 3]
```

### 2. fold (reduce의 함수형 버전)

```python
from rfs.hof.collections import fold_left, fold_right

# fold_left: 왼쪽에서 오른쪽으로
numbers = [1, 2, 3, 4]
sum_result = fold_left(lambda acc, x: acc + x, 0, numbers)  # 10

# fold_right: 오른쪽에서 왼쪽으로 (게으른 평가에 유용)
concat = fold_right(lambda x, acc: f"{x},{acc}", "", ["a", "b", "c"])
# "a,b,c,"
```

## 패턴 매칭 활용

### match vs if-else

```python
# ❌ 복잡한 if-elif-else
def process_value(value):
    if isinstance(value, int):
        if value > 0:
            return f"양수: {value}"
        elif value < 0:
            return f"음수: {value}"
        else:
            return "영"
    elif isinstance(value, str):
        if len(value) > 0:
            return f"문자열: {value}"
        else:
            return "빈 문자열"
    elif value is None:
        return "null 값"
    else:
        return "알 수 없는 타입"

# ✅ 패턴 매칭 사용
def process_value(value) -> str:
    match value:
        case int(x) if x > 0:
            return f"양수: {x}"
        case int(x) if x < 0:
            return f"음수: {x}"
        case 0:
            return "영"
        case str(s) if len(s) > 0:
            return f"문자열: {s}"
        case "":
            return "빈 문자열"
        case None:
            return "null 값"
        case _:
            return "알 수 없는 타입"
```

### Result 패턴 매칭

```python
def handle_result(result: Result[int, str]) -> str:
    match result:
        case Success(value) if value > 100:
            return f"큰 성공: {value}"
        case Success(value):
            return f"성공: {value}"
        case Failure(error) if "timeout" in error:
            return "시간 초과 에러"
        case Failure(error):
            return f"실패: {error}"
```

### 구조 분해와 패턴 매칭

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

@dataclass
class Circle:
    center: Point
    radius: float

def describe_shape(shape):
    match shape:
        case Point(0, 0):
            return "원점"
        case Point(x, 0):
            return f"X축 상의 점: x={x}"
        case Point(0, y):
            return f"Y축 상의 점: y={y}"
        case Point(x, y):
            return f"좌표: ({x}, {y})"
        case Circle(Point(0, 0), r):
            return f"원점 중심의 원, 반지름={r}"
        case Circle(center, radius):
            return f"원: 중심={center}, 반지름={radius}"
        case _:
            return "알 수 없는 도형"
```

## 모나드 패턴

### Maybe 모나드

```python
from rfs.hof.monads import Maybe, Some, Nothing

def safe_divide(a: float, b: float) -> Maybe[float]:
    if b == 0:
        return Nothing()
    return Some(a / b)

# 체이닝
result = Some(10)
    .bind(lambda x: safe_divide(x, 2))  # Some(5)
    .bind(lambda x: safe_divide(x, 0))  # Nothing()
    .get_or_else(0)  # 0
```

### Either 모나드

```python
from rfs.hof.monads import Either, Left, Right

def validate_age(age: int) -> Either[str, int]:
    if age < 0:
        return Left("나이는 음수일 수 없습니다")
    if age > 150:
        return Left("비현실적인 나이입니다")
    return Right(age)

# 체이닝
result = Right(25)
    .bind(validate_age)
    .map(lambda x: x * 2)
    .get_or_else(0)
```

## 모범 사례

1. **작은 함수 우선**: 한 가지 일만 하는 작은 순수 함수 작성
2. **타입 힌트 필수**: 모든 함수에 완전한 타입 힌트 추가
3. **불변 기본값**: 함수 매개변수 기본값은 불변 타입 사용
4. **함수 합성 활용**: 복잡한 로직은 작은 함수들의 합성으로
5. **부작용 격리**: I/O와 부작용은 프로그램 경계에서만
6. **패턴 매칭 선호**: if-else 대신 match 문 사용
7. **모나드로 안전성**: Maybe/Either/Result로 null 안전성 확보