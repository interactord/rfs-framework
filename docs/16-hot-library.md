# RFS Higher-Order Functions (HOF) Library

## 개요

RFS HOF 라이브러리는 Python에서 함수형 프로그래밍을 위한 포괄적인 유틸리티 모음입니다. Swift, Haskell, Scala 등의 함수형 프로그래밍 언어에서 영감을 받아 만들어졌으며, 타입 안전하고 재사용 가능한 제네릭 함수들을 제공합니다.

## 목차

1. [Core Functions](#core-functions)
2. [Collections](#collections)
3. [Monads](#monads)
4. [Guard Statement](#guard-statement)
5. [Combinators](#combinators)
6. [Decorators](#decorators)
7. [Async HOF](#async-hof)
8. [Readable HOF](#readable-hof)

---

## Core Functions

### compose
함수를 오른쪽에서 왼쪽으로 합성합니다.

```python
from rfs.hof.core import compose

add_one = lambda x: x + 1
multiply_two = lambda x: x * 2

# (3 * 2) + 1 = 7
composed = compose(add_one, multiply_two)
result = composed(3)  # 7
```

### pipe
함수를 왼쪽에서 오른쪽으로 연결합니다.

```python
from rfs.hof.core import pipe

add_one = lambda x: x + 1
multiply_two = lambda x: x * 2

# (3 + 1) * 2 = 8
piped = pipe(add_one, multiply_two)
result = piped(3)  # 8
```

### curry
함수를 커링하여 부분 적용을 가능하게 합니다.

```python
from rfs.hof.core import curry

@curry
def add(a, b, c):
    return a + b + c

# 다양한 방법으로 호출 가능
result1 = add(1)(2)(3)  # 6
result2 = add(1, 2)(3)  # 6
result3 = add(1)(2, 3)  # 6

# 부분 적용
add_one = add(1)
add_one_two = add_one(2)
result4 = add_one_two(3)  # 6
```

### partial
함수의 일부 인자를 미리 고정합니다.

```python
from rfs.hof.core import partial

def greet(greeting, name):
    return f"{greeting}, {name}!"

say_hello = partial(greet, "Hello")
result = say_hello("World")  # "Hello, World!"
```

---

## Collections

### Swift-Inspired Functions

#### first
조건에 맞는 첫 번째 요소를 반환합니다.

```python
from rfs.hof.collections import first

numbers = [1, 2, 3, 4, 5]

# 첫 번째 요소
first_num = first(numbers)  # 1

# 조건에 맞는 첫 번째 요소
first_gt_3 = first(numbers, lambda x: x > 3)  # 4
```

#### compactMap
변환과 None 필터링을 동시에 수행합니다.

```python
from rfs.hof.collections import compact_map

# None이 아닌 값만 변환
result = compact_map(
    lambda x: x * 2 if x > 2 else None,
    [1, 2, 3, 4]
)  # [6, 8]
```

#### flatMap
각 요소를 컬렉션으로 변환하고 평탄화합니다.

```python
from rfs.hof.collections import flat_map

# 각 숫자를 [n, n*2]로 변환
result = flat_map(
    lambda x: [x, x * 2],
    [1, 2, 3]
)  # [1, 2, 2, 4, 3, 6]
```

#### dropLast
끝에서부터 요소를 제거합니다.

```python
from rfs.hof.collections import drop_last

numbers = [1, 2, 3, 4, 5]

# 마지막 2개 제거
result1 = drop_last(numbers, 2)  # [1, 2, 3]

# 조건에 맞는 마지막 요소들 제거
result2 = drop_last(numbers, predicate=lambda x: x > 3)  # [1, 2, 3]
```

#### merging
충돌 해결 함수와 함께 딕셔너리를 병합합니다.

```python
from rfs.hof.collections import merging

dict1 = {'a': 1, 'b': 2}
dict2 = {'b': 3, 'c': 4}

# 값 더하기
result1 = merging(dict1, dict2, lambda old, new: old + new)
# {'a': 1, 'b': 5, 'c': 4}

# 새 값으로 대체
result2 = merging(dict1, dict2, lambda old, new: new)
# {'a': 1, 'b': 3, 'c': 4}
```

### Functional Operations

#### fold / reduce
컬렉션을 단일 값으로 축약합니다.

```python
from rfs.hof.collections import fold, fold_right

numbers = [1, 2, 3, 4]

# 왼쪽에서 오른쪽으로
sum_result = fold(lambda acc, x: acc + x, 0, numbers)  # 10

# 오른쪽에서 왼쪽으로
string_result = fold_right(
    lambda x, acc: f"({x}{acc})",
    "",
    ['a', 'b', 'c']
)  # "(a(b(c)))"
```

#### scan
fold의 모든 중간 결과를 반환합니다.

```python
from rfs.hof.collections import scan

numbers = [1, 2, 3, 4]
running_sum = scan(lambda acc, x: acc + x, 0, numbers)
# [0, 1, 3, 6, 10]
```

#### partition
조건에 따라 컬렉션을 두 그룹으로 나눕니다.

```python
from rfs.hof.collections import partition

numbers = [1, 2, 3, 4, 5]
evens, odds = partition(lambda x: x % 2 == 0, numbers)
# evens: [2, 4], odds: [1, 3, 5]
```

#### groupBy
키 함수에 따라 요소를 그룹화합니다.

```python
from rfs.hof.collections import group_by

numbers = [1, 2, 3, 4, 5, 6]
grouped = group_by(lambda x: x % 3, numbers)
# {1: [1, 4], 2: [2, 5], 0: [3, 6]}
```

---

## Monads

### Maybe Monad
옵셔널 값을 안전하게 처리합니다.

```python
from rfs.hof.monads import Maybe

# 값이 있는 경우
maybe_value = Maybe.just(5)
result = maybe_value.map(lambda x: x * 2)  # Maybe(10)

# 값이 없는 경우
empty = Maybe.nothing()
result = empty.map(lambda x: x * 2)  # Maybe(None)

# 체이닝
def safe_div(x):
    return Maybe.just(10 / x) if x != 0 else Maybe.nothing()

result = Maybe.just(2).bind(safe_div)  # Maybe(5.0)
result = Maybe.just(0).bind(safe_div)  # Maybe(None)

# 기본값 제공
value = Maybe.nothing().unwrap_or(42)  # 42
```

### Either Monad
두 가지 가능한 타입을 처리합니다.

```python
from rfs.hof.monads import Either

# 성공 케이스 (Right)
success = Either.right(42)
result = success.map(lambda x: x * 2)  # Either(right=84)

# 실패 케이스 (Left)
failure = Either.left("error message")
result = failure.map(lambda x: x * 2)  # Either(left='error message')

# 패턴 매칭
def process(either):
    if either.is_right():
        return f"Success: {either.unwrap()}"
    else:
        return f"Error: {either.unwrap_left()}"
```

### Result Monad
성공/실패를 명시적으로 처리합니다.

```python
from rfs.hof.monads import Result

# 예외를 Result로 변환
def divide(a, b):
    if b == 0:
        return Result.failure("Division by zero")
    return Result.success(a / b)

result = divide(10, 2)  # Result(success=5.0)
result = divide(10, 0)  # Result(error='Division by zero')

# 체이닝
result = (
    Result.success(10)
    .map(lambda x: x * 2)
    .bind(lambda x: divide(x, 5))
)  # Result(success=4.0)

# from_try 패턴
result = Result.from_try(lambda: 10 / 0)  # Result(error=ZeroDivisionError)
```

---

## Guard Statement

Swift 스타일의 guard 문으로 조기 반환을 구현합니다.

### 기본 사용법

```python
from rfs.hof.guard import guard, with_guards

@with_guards
def divide(a, b):
    guard(b != 0, else_return=float('inf'))
    return a / b

result = divide(10, 0)  # inf (조기 반환)
result = divide(10, 2)  # 5.0
```

### guard_let (옵셔널 언래핑)

```python
from rfs.hof.guard import guard_let, with_guards

@with_guards
def process(data):
    unwrapped = guard_let(data, else_return="No data")
    return f"Processing: {unwrapped}"

result = process(None)  # "No data"
result = process("test")  # "Processing: test"
```

### guard_type (타입 체크)

```python
from rfs.hof.guard import guard_type, with_guards

@with_guards
def process_number(val):
    num = guard_type(val, int, else_return=0)
    return num * 2

result = process_number(5)  # 10
result = process_number("not a number")  # 0
```

### guard_range (범위 체크)

```python
from rfs.hof.guard import guard_range, with_guards

@with_guards
def process_percentage(val):
    pct = guard_range(val, 0, 100, else_return=50)
    return f"{pct}%"

result = process_percentage(75)  # "75%"
result = process_percentage(150)  # "50%" (범위 초과)
```

### GuardContext (복수 체크)

```python
from rfs.hof.guard import GuardContext, with_guards

@with_guards
def process(value, data):
    with GuardContext() as guard:
        guard.check(value > 0, "Value must be positive")
        guard.check_not_none(data, "Data is required")
        guard.check_type(value, int, "Must be integer")
        guard.else_return("Validation failed")
    
    return f"Success: {value}, {data}"

result = process(5, "test")  # "Success: 5, test"
result = process(-1, "test")  # "Validation failed"
```

---

## Combinators

### tap (사이드 이펙트)
값을 변경하지 않고 사이드 이펙트를 실행합니다.

```python
from rfs.hof.combinators import tap
from rfs.hof.core import pipe

pipeline = pipe(
    lambda x: x * 2,
    tap(print),  # 10을 출력하지만 값은 통과
    lambda x: x + 1
)
result = pipeline(5)  # 11
```

### when / unless (조건부 변환)

```python
from rfs.hof.combinators import when, unless

# 조건이 참일 때만 변환
double_if_even = when(lambda x: x % 2 == 0, lambda x: x * 2)
result = double_if_even(4)  # 8
result = double_if_even(3)  # 3

# 조건이 거짓일 때만 변환
add_one_unless_zero = unless(lambda x: x == 0, lambda x: x + 1)
result = add_one_unless_zero(5)  # 6
result = add_one_unless_zero(0)  # 0
```

### cond (다중 조건 분기)

```python
from rfs.hof.combinators import cond

grade = cond(
    (lambda x: x >= 90, lambda x: 'A'),
    (lambda x: x >= 80, lambda x: 'B'),
    (lambda x: x >= 70, lambda x: 'C'),
    (lambda x: x >= 60, lambda x: 'D'),
    (lambda x: True, lambda x: 'F')  # 기본값
)

result = grade(85)  # 'B'
result = grade(45)  # 'F'
```

### converge (결과 수렴)

```python
from rfs.hof.combinators import converge

# 평균 계산: sum / len
average = converge(
    lambda total, count: total / count,
    sum,
    len
)
result = average([1, 2, 3, 4, 5])  # 3.0
```

---

## Decorators

### memoize (메모이제이션)

```python
from rfs.hof.decorators import memoize
from datetime import timedelta
import time

@memoize(maxsize=100, ttl=timedelta(minutes=5))
def expensive_computation(x, y):
    time.sleep(1)  # 비싼 연산 시뮬레이션
    return x ** y

result1 = expensive_computation(2, 10)  # 1초 소요
result2 = expensive_computation(2, 10)  # 즉시 반환 (캐시됨)
```

### throttle (스로틀링)

```python
from rfs.hof.decorators import throttle

@throttle(rate=3, per=1.0)  # 초당 최대 3회 호출
def api_call():
    print(f"Called at {time.time()}")

# 5번 호출해도 처음 3번만 즉시 실행
for _ in range(5):
    api_call()
```

### debounce (디바운싱)

```python
from rfs.hof.decorators import debounce

@debounce(wait=0.5)
def save_document():
    print("Document saved")

# 빠른 연속 호출은 마지막 호출 후 0.5초 뒤에 한 번만 실행
for _ in range(10):
    save_document()
    time.sleep(0.1)
```

### retry (재시도)

```python
from rfs.hof.decorators import retry

@retry(max_attempts=3, delay=1.0, backoff=2.0)
def unreliable_network_call():
    # 때때로 실패할 수 있는 네트워크 호출
    import random
    if random.random() < 0.7:
        raise ConnectionError("Network error")
    return "Success"
```

### circuit_breaker (서킷 브레이커)

```python
from rfs.hof.decorators import circuit_breaker

@circuit_breaker(failure_threshold=3, recovery_timeout=30)
def external_service_call():
    # 외부 서비스 호출
    # 3번 실패하면 30초 동안 서킷이 열림
    pass
```

---

## Async HOF

### async_compose / async_pipe

```python
from rfs.hof.async_hof import async_compose, async_pipe

async def add_one(x):
    return x + 1

async def multiply_two(x):
    return x * 2

# 합성
composed = async_compose(add_one, multiply_two)
result = await composed(3)  # 7

# 파이프
piped = async_pipe(add_one, multiply_two)
result = await piped(3)  # 8
```

### async_map / async_filter

```python
from rfs.hof.async_hof import async_map, async_filter

async def async_double(x):
    await asyncio.sleep(0.1)
    return x * 2

# 비동기 맵
results = await async_map(async_double, [1, 2, 3])  # [2, 4, 6]

async def is_even(x):
    await asyncio.sleep(0.1)
    return x % 2 == 0

# 비동기 필터
results = await async_filter(is_even, [1, 2, 3, 4, 5])  # [2, 4]
```

### async_parallel / async_sequential

```python
from rfs.hof.async_hof import async_parallel, async_sequential

async def task1():
    await asyncio.sleep(1)
    return 1

async def task2():
    await asyncio.sleep(1)
    return 2

# 병렬 실행 (1초)
results = await async_parallel(task1(), task2())  # [1, 2]

# 순차 실행 (2초)
results = await async_sequential(task1(), task2())  # [1, 2]
```

### async_retry

```python
from rfs.hof.async_hof import async_retry

@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def unreliable_async_call():
    # 재시도 로직이 적용된 비동기 함수
    pass
```

### async_throttle

```python
from rfs.hof.async_hof import async_throttle

async def api_call(x):
    return x * 2

# 초당 3개씩 처리
results = await async_throttle(
    api_call,
    range(10),
    rate=3,
    per=1.0
)
```

---

## 사용 예제

### 함수형 파이프라인 구성

```python
from rfs.hof import pipe, tap, when, Maybe
from rfs.hof.collections import first, filter_indexed, group_by

# 데이터 처리 파이프라인
pipeline = pipe(
    # 1. 필터링
    lambda data: filter_indexed(
        lambda i, x: i % 2 == 0 and x > 0,
        data
    ),
    # 2. 변환
    lambda data: [x * 2 for x in data],
    # 3. 로깅 (사이드 이펙트)
    tap(lambda x: print(f"Processing: {x}")),
    # 4. 그룹화
    lambda data: group_by(lambda x: x % 10, data),
    # 5. Maybe로 래핑
    Maybe.just
)

result = pipeline([1, -2, 3, -4, 5, 6, 7, 8, 9, 10])
```

### 에러 처리 체인

```python
from rfs.hof.monads import Result
from rfs.hof.guard import with_guards, guard_type, guard_range

@with_guards
def process_data(data):
    # 타입 체크
    validated = guard_type(data, dict, else_return=Result.failure("Invalid type"))
    
    # 범위 체크
    value = validated.get('value', 0)
    checked = guard_range(value, 0, 100, else_return=Result.failure("Out of range"))
    
    # 처리
    return Result.success(checked * 2)

# 사용
result = process_data({'value': 50})
if result.is_success():
    print(f"Success: {result.unwrap()}")
else:
    print(f"Error: {result.unwrap_error()}")
```

### 비동기 작업 조합

```python
from rfs.hof.async_hof import async_pipe, async_map, async_parallel
from rfs.hof.decorators import memoize

@memoize(maxsize=100)
async def fetch_user(user_id):
    # API 호출 시뮬레이션
    await asyncio.sleep(1)
    return {'id': user_id, 'name': f'User{user_id}'}

async def enrich_users(user_ids):
    # 파이프라인 구성
    pipeline = async_pipe(
        # 1. 사용자 정보 가져오기 (병렬)
        lambda ids: async_map(fetch_user, ids),
        # 2. 활성 사용자만 필터
        lambda users: async_filter(
            lambda u: u.get('active', True),
            users
        ),
        # 3. 추가 정보 병합
        lambda users: async_map(
            lambda u: {**u, 'timestamp': time.time()},
            users
        )
    )
    
    return await pipeline(user_ids)

# 실행
users = await enrich_users([1, 2, 3, 4, 5])
```

---

## 모범 사례

1. **불변성 유지**: HOF를 사용할 때는 항상 불변성을 유지하세요.
2. **순수 함수 작성**: 사이드 이펙트를 최소화하고 예측 가능한 함수를 작성하세요.
3. **타입 힌트 사용**: 타입 안전성을 위해 타입 힌트를 적극 활용하세요.
4. **적절한 모나드 선택**: Maybe는 옵셔널 값, Either는 분기 처리, Result는 에러 처리에 사용하세요.
5. **Guard 패턴 활용**: 복잡한 검증 로직은 guard 패턴으로 단순화하세요.
6. **메모이제이션 활용**: 비싼 연산은 memoize로 최적화하세요.
7. **비동기 조합**: 비동기 작업은 async_parallel로 병렬화하여 성능을 향상시키세요.

---

---

## Readable HOF

Readable HOF는 자연어에 가까운 선언적 코드 작성을 위한 고차 함수 라이브러리입니다. 복잡한 중첩 루프와 규칙 기반 로직을 읽기 쉬운 체이닝 패턴으로 변환합니다.

### 핵심 구성 요소

#### 1. Rule Application System
데이터에 규칙을 적용하고 위반사항을 검출하는 시스템입니다.

```python
from rfs.hof.readable import apply_rules_to

# 보안 규칙 정의
security_rules = [
    lambda text: "password" in text.lower(),
    lambda text: "api_key" in text.lower(),
]

# 자연어 같은 규칙 적용
violations = (apply_rules_to(source_code)
              .using(security_rules)
              .collect_violations())

print(f"발견된 보안 위반: {len(violations)}개")
```

#### 2. Validation DSL
구조화된 데이터 검증을 위한 Domain Specific Language입니다.

```python
from rfs.hof.readable import validate_config, required, range_check, email_check

# 선언적 설정 검증
config = {"api_key": "secret", "timeout": 30, "email": "user@example.com"}

result = validate_config(config).against_rules([
    required("api_key", "API 키가 필요합니다"),
    range_check("timeout", 1, 300, "타임아웃은 1-300초 사이"),
    email_check("email", "유효한 이메일이 필요합니다")
])

if result.is_success():
    print("✅ 설정이 유효합니다")
```

#### 3. Scanning System
텍스트나 데이터에서 패턴을 검색하는 시스템입니다.

```python
import re
from rfs.hof.readable import scan_for, create_security_violation

# 보안 패턴 스캔
patterns = [
    re.compile(r'password\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'api_key\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
]

results = (scan_for(patterns)
           .in_text(code_content)
           .extract(create_security_violation)
           .filter_above_threshold("medium")
           .sort_by_risk())

for violation in results.collect():
    print(f"🚨 보안 위험: {violation}")
```

#### 4. Batch Processing
대량 데이터의 효율적 처리를 위한 시스템입니다.

```python
from rfs.hof.readable import extract_from

# API 응답 배치 처리
api_responses = [
    {"status": "success", "data": {"id": 1, "name": "Alice"}},
    {"status": "error", "message": "Not found"},
    {"status": "success", "data": {"id": 2, "name": "Bob"}},
]

# 자연어 같은 배치 처리
users = (extract_from(api_responses)
         .flatten_batches()
         .successful_only()
         .extract_content()
         .transform_to(lambda item: {
             "user_id": item["id"],
             "display_name": item["name"].title()
         })
         .collect())

print(f"처리된 사용자: {len(users)}명")
```

### 실전 활용 예제

#### 종합 보안 감사 시스템
```python
from rfs.hof.readable import apply_rules_to, scan_for, validate_config

def comprehensive_security_audit(project_path: str):
    """프로젝트 전체 보안 감사"""
    
    # 1. 코드 규칙 검사
    code_violations = (apply_rules_to(source_files)
                      .using(security_rules)
                      .collect_violations()
                      .filter_above_threshold("medium"))
    
    # 2. 패턴 스캔
    security_issues = (scan_for(vulnerability_patterns)
                      .in_directory(project_path)
                      .extract(create_security_violation)
                      .sort_by_severity())
    
    # 3. 설정 검증
    config_issues = validate_config(app_config).against_rules([
        required("database.host"),
        required("api.secret_key"),
        custom_check("api.secret_key", 
                    lambda key: len(key) >= 32,
                    "API 키는 32자 이상")
    ])
    
    return {
        "code_violations": code_violations.collect(),
        "security_issues": security_issues.collect(),
        "config_valid": config_issues.is_success()
    }
```

### 장점

1. **가독성**: 자연어에 가까운 선언적 표현
2. **재사용성**: 작은 함수들의 조합으로 복잡한 로직 구성
3. **타입 안전성**: Result 패턴과 통합된 안전한 에러 처리
4. **성능**: 지연 평가와 병렬 처리 지원
5. **테스트 용이성**: 각 단계를 독립적으로 테스트 가능

### 관련 문서

- [Readable HOF 완전 가이드](19-readable-hof-guide.md)
- [Readable HOF API 레퍼런스](api/hof/readable.md)
- [함수형 개발 규칙](01-core-patterns.md)

---

## 성능 고려사항

1. **메모이제이션 크기**: 캐시 크기를 적절히 설정하여 메모리 사용을 제어하세요.
2. **스로틀링/디바운싱**: API 호출이나 UI 이벤트에는 적절한 제한을 두세요.
3. **병렬 처리**: async_parallel을 사용할 때는 동시 실행 수를 제한하세요.
4. **지연 평가**: 큰 데이터셋은 제너레이터나 지연 평가를 활용하세요.

---

## 마이그레이션 가이드

기존 코드를 HOF 라이브러리로 마이그레이션하는 방법:

### Before (기존 코드)
```python
from functools import reduce

def compose(*functions):
    return reduce(lambda f, g: lambda x: f(g(x)), functions, lambda x: x)

result = []
for item in items:
    if item > 0:
        result.append(item * 2)
```

### After (HOF 사용)
```python
from rfs.hof import compose, pipe
from rfs.hof.collections import filter_indexed, map_indexed

# 함수 합성
composed = compose(func1, func2, func3)

# 컬렉션 처리
result = pipe(
    lambda items: filter_indexed(lambda i, x: x > 0, items),
    lambda items: map_indexed(lambda i, x: x * 2, items)
)(items)
```

---

## 추가 리소스

- [함수형 프로그래밍 개념](https://en.wikipedia.org/wiki/Functional_programming)
- [Swift 함수형 프로그래밍](https://docs.swift.org/swift-book/LanguageGuide/Closures.html)
- [Haskell 영감](https://wiki.haskell.org/Higher_order_function)
- [Python functools](https://docs.python.org/3/library/functools.html)