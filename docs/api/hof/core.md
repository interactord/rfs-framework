# HOF Core Functions API

Higher-Order Functions (HOF) core API documentation for RFS Framework.

**주요 함수:**
- `compose`, `pipe`: 함수 합성
- `curry`, `partial`: 커링 및 부분 적용
- `memoize`: 결과 캐싱

## 사용 예제

### 함수 합성 (Composition)

```python
from rfs.hof import compose, pipe

# compose - 함수들을 오른쪽에서 왼쪽으로 합성
def add_one(x: int) -> int:
    return x + 1

def multiply_by_two(x: int) -> int:
    return x * 2

def to_string(x: int) -> str:
    return str(x)

# 함수 합성: f(g(h(x)))
composed = compose(to_string, multiply_by_two, add_one)
result = composed(5)  # str(((5 + 1) * 2)) = "12"
print(result)

# pipe - 함수들을 왼쪽에서 오른쪽으로 파이프
piped = pipe(
    add_one,
    multiply_by_two,
    to_string
)
result = piped(5)  # 같은 결과: "12"
print(result)

# 실용적인 예제: 데이터 변환 파이프라인
from typing import List, Dict

def parse_csv_line(line: str) -> List[str]:
    return line.strip().split(',')

def to_user_dict(fields: List[str]) -> Dict[str, str]:
    return {
        'name': fields[0],
        'email': fields[1],
        'age': fields[2]
    }

def validate_user(user: Dict[str, str]) -> Dict[str, str]:
    if '@' not in user['email']:
        raise ValueError(f"Invalid email: {user['email']}")
    return user

# CSV 라인을 검증된 사용자 딕셔너리로 변환
csv_to_user = pipe(
    parse_csv_line,
    to_user_dict,
    validate_user
)

user = csv_to_user("John Doe,john@example.com,30")
print(user)  # {'name': 'John Doe', 'email': 'john@example.com', 'age': '30'}
```

### 커링 (Currying)

```python
from rfs.hof import curry, partial

# curry - 함수를 커리된 버전으로 변환
@curry
def add_three(a: int, b: int, c: int) -> int:
    return a + b + c

# 부분 적용
add_10_and = add_three(10)  # a=10으로 부분 적용
add_10_20_and = add_10_and(20)  # b=20으로 부분 적용
result = add_10_20_and(5)  # c=5로 완전 적용
print(result)  # 35

# 한 번에 여러 인자 적용
result = add_three(10, 20, 5)  # 직접 적용도 가능
print(result)  # 35

# partial - 부분 적용을 위한 유틸리티
def greet(greeting: str, name: str, punctuation: str = "!") -> str:
    return f"{greeting}, {name}{punctuation}"

# 인사말을 미리 설정
say_hello = partial(greet, "Hello")
say_goodbye = partial(greet, "Goodbye", punctuation=".")

print(say_hello("Alice"))      # "Hello, Alice!"
print(say_goodbye("Bob"))      # "Goodbye, Bob."

# 실용적인 커링 예제: 설정 기반 함수
@curry
def make_http_request(base_url: str, headers: dict, endpoint: str, params: dict = None):
    # HTTP 요청 시뮬레이션
    url = f"{base_url}/{endpoint}"
    return {
        'url': url,
        'headers': headers,
        'params': params or {}
    }

# API 클라이언트 설정
api_headers = {'Authorization': 'Bearer token123', 'Content-Type': 'application/json'}
api_client = make_http_request('https://api.example.com', api_headers)

# 특정 엔드포인트 함수들
get_users = api_client('users')
get_posts = api_client('posts')

users_request = get_users({'page': 1, 'limit': 10})
posts_request = get_posts({'author_id': 123})
```

### 함수 변환 유틸리티

```python
from rfs.hof import flip, const, identity, memoize

# flip - 인자 순서를 뒤바꾸기
def divide(a: float, b: float) -> float:
    return a / b

# 일반적인 나눗셈
print(divide(10, 2))  # 5.0

# 순서를 뒤바꾼 나눗셈
divide_flipped = flip(divide)
print(divide_flipped(2, 10))  # 5.0 (인자가 뒤바뀜)

# const - 항상 같은 값을 반환하는 함수
always_42 = const(42)
print(always_42())      # 42
print(always_42(1, 2))  # 42 (인자 무시)

# identity - 입력값을 그대로 반환
print(identity(5))        # 5
print(identity("hello"))  # "hello"

# memoize - 함수 결과 캐싱
@memoize
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# 첫 번째 호출은 계산함
result1 = fibonacci(30)  # 느림

# 두 번째 호출은 캐시된 결과 사용
result2 = fibonacci(30)  # 빠름
print(result1 == result2)  # True

# 캐시 상태 확인
print(f"Cache size: {fibonacci.cache_info().currsize}")
```

### 함수 결합 패턴

```python
from rfs.hof import apply, tap, when, unless

# apply - 함수를 값에 적용
def square(x: int) -> int:
    return x * x

result = apply(square, 5)
print(result)  # 25

# 여러 함수를 순차적으로 적용
def double(x: int) -> int:
    return x * 2

def add_ten(x: int) -> int:
    return x + 10

transforms = [square, double, add_ten]
result = 5
for transform in transforms:
    result = apply(transform, result)
print(result)  # ((5² * 2) + 10) = 60

# tap - 부수 효과를 위한 함수 (값은 그대로 통과)
def log_value(x):
    print(f"Current value: {x}")
    return x

result = pipe(
    lambda x: x + 1,
    tap(log_value),  # 값을 로깅하지만 변경하지 않음
    lambda x: x * 2,
    tap(log_value)
)(5)
# 출력:
# Current value: 6
# Current value: 12
print(f"Final result: {result}")  # 12

# when/unless - 조건부 함수 적용
def is_even(x: int) -> bool:
    return x % 2 == 0

def halve(x: int) -> int:
    return x // 2

# 짝수일 때만 반으로 나누기
conditional_halve = when(is_even, halve)
print(conditional_halve(8))  # 4 (짝수이므로 halve 적용)
print(conditional_halve(7))  # 7 (홀수이므로 그대로)

# 짝수가 아닐 때만 두 배로 만들기
conditional_double = unless(is_even, double)
print(conditional_double(7))  # 14 (홀수이므로 double 적용)
print(conditional_double(8))  # 8 (짝수이므로 그대로)
```

### 고차 함수 패턴

```python
from rfs.hof import bifunctor, contramap, fmap
from typing import Tuple, Callable

# bifunctor - 두 개의 타입 파라미터를 가진 함수에 동시 적용
def process_pair(f: Callable, g: Callable, pair: Tuple):
    return bifunctor(f, g, pair)

pair = (5, "hello")
result = process_pair(
    lambda x: x * 2,      # 첫 번째 요소에 적용
    lambda s: s.upper(),  # 두 번째 요소에 적용
    pair
)
print(result)  # (10, "HELLO")

# contramap - 입력을 변환한 후 함수 적용
def string_length(s: str) -> int:
    return len(s)

# 숫자를 문자열로 변환한 후 길이 계산
number_to_length = contramap(str, string_length)
result = number_to_length(12345)
print(result)  # 5

# fmap - 컨테이너 내부의 값에 함수 적용
from typing import Optional

def safe_divide(a: float, b: float) -> Optional[float]:
    return a / b if b != 0 else None

# Optional 내부 값에 함수 적용
def double_if_exists(optional_value: Optional[float]) -> Optional[float]:
    return fmap(lambda x: x * 2, optional_value)

result1 = double_if_exists(safe_divide(10, 2))  # Some(10.0)
result2 = double_if_exists(safe_divide(10, 0))  # None
print(result1, result2)
```

### 실제 사용 예제: 데이터 처리 파이프라인

```python
from rfs.hof import pipe, curry, memoize, when
import json
from typing import Dict, List

# 사용자 데이터 처리 파이프라인
@memoize
def fetch_user_data(user_id: str) -> Dict:
    # 실제로는 DB나 API에서 가져옴
    return {
        'id': user_id,
        'name': f'User {user_id}',
        'email': f'user{user_id}@example.com',
        'preferences': {'notifications': True, 'theme': 'dark'}
    }

@curry
def transform_user(formatter: Callable, validator: Callable, user: Dict) -> Dict:
    return pipe(
        formatter,
        validator,
        when(lambda u: u.get('valid', True), 
             lambda u: {**u, 'processed': True})
    )(user)

def format_user(user: Dict) -> Dict:
    return {
        **user,
        'display_name': user['name'].title(),
        'email_domain': user['email'].split('@')[1]
    }

def validate_user(user: Dict) -> Dict:
    is_valid = (
        '@' in user['email'] and
        len(user['name']) > 0 and
        'preferences' in user
    )
    return {**user, 'valid': is_valid}

# 사용자 처리 파이프라인 구성
process_user = pipe(
    fetch_user_data,
    transform_user(format_user, validate_user)
)

# 사용
processed_user = process_user('123')
print(json.dumps(processed_user, indent=2))
```

### 성능 최적화 패턴

```python
from rfs.hof import debounce, throttle, once
import asyncio
import time

# debounce - 연속 호출을 지연시켜 마지막 호출만 실행
@debounce(delay=1.0)
def search_api(query: str):
    print(f"Searching for: {query}")
    return f"Results for {query}"

# 빠른 연속 호출
search_api("python")
search_api("pytho")  
search_api("python")  # 이것만 1초 후 실행됨

# throttle - 지정된 간격으로만 함수 실행
@throttle(interval=2.0)
def log_event(event: str):
    print(f"[{time.time():.2f}] Event: {event}")

# 연속 호출해도 2초 간격으로만 실행
for i in range(5):
    log_event(f"Event {i}")
    time.sleep(0.5)

# once - 한 번만 실행되는 함수
@once
def initialize_system():
    print("System initialized")
    return "initialization_complete"

# 여러 번 호출해도 한 번만 실행
result1 = initialize_system()  # "System initialized" 출력
result2 = initialize_system()  # 출력 없음, 캐시된 결과 반환
print(result1 == result2)  # True
```

## 관련 문서

- [HOF Collections](collections.md) - 컬렉션 처리 함수들
- [HOF Monads](monads.md) - 모나드 패턴 구현
- [함수형 프로그래밍](../../01-core-patterns.md#functional-programming) - 함수형 패턴 개념