# HOF Collections API

Higher-Order Functions (HOF) collections API documentation for RFS Framework.

**주요 함수:**
- `map_list`, `filter_list`: 리스트 조작
- `group_by`, `partition`: 그룹화 및 분할
- `flatten`, `chunk`: 평탄화 및 찭크화

## 사용 예제

### 리스트 변환 함수

```python
from rfs.hof.collections import map_list, filter_list, reduce_list
from typing import List

# map_list - 리스트의 각 요소에 함수 적용
numbers = [1, 2, 3, 4, 5]
squared = map_list(lambda x: x ** 2, numbers)
print(squared)  # [1, 4, 9, 16, 25]

# 문자열 변환
names = ["alice", "bob", "charlie"]
capitalized = map_list(str.capitalize, names)
print(capitalized)  # ["Alice", "Bob", "Charlie"]

# filter_list - 조건에 맞는 요소만 필터링
even_numbers = filter_list(lambda x: x % 2 == 0, numbers)
print(even_numbers)  # [2, 4]

# 길이 기준 필터링
long_names = filter_list(lambda name: len(name) > 3, names)
print(long_names)  # ["alice", "charlie"]

# reduce_list - 리스트를 단일 값으로 축약
total = reduce_list(lambda acc, x: acc + x, 0, numbers)
print(total)  # 15

# 최대값 찾기
maximum = reduce_list(
    lambda acc, x: x if x > acc else acc,
    float('-inf'),
    numbers
)
print(maximum)  # 5
```

### 고급 리스트 조작

```python
from rfs.hof.collections import (
    take, drop, take_while, drop_while,
    partition, group_by, chunk, flatten
)

# take / drop - 요소 가져오기/버리기
data = list(range(10))  # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

first_five = take(5, data)
print(first_five)  # [0, 1, 2, 3, 4]

rest = drop(5, data)
print(rest)  # [5, 6, 7, 8, 9]

# take_while / drop_while - 조건부 가져오기/버리기
less_than_five = take_while(lambda x: x < 5, data)
print(less_than_five)  # [0, 1, 2, 3, 4]

from_five = drop_while(lambda x: x < 5, data)
print(from_five)  # [5, 6, 7, 8, 9]

# partition - 조건에 따라 분할
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
evens, odds = partition(lambda x: x % 2 == 0, numbers)
print(evens)  # [2, 4, 6, 8, 10]
print(odds)   # [1, 3, 5, 7, 9]

# group_by - 키 함수로 그룹화
words = ["apple", "apricot", "banana", "blueberry", "cherry"]
by_first_letter = group_by(lambda word: word[0], words)
print(by_first_letter)
# {'a': ['apple', 'apricot'], 'b': ['banana', 'blueberry'], 'c': ['cherry']}

# chunk - 지정된 크기로 분할
data = list(range(12))
chunks = chunk(3, data)
print(chunks)  # [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]

# flatten - 중첩된 리스트 평탄화
nested = [[1, 2], [3, 4], [5, 6]]
flat = flatten(nested)
print(flat)  # [1, 2, 3, 4, 5, 6]
```

### 딕셔너리 조작

```python
from rfs.hof.collections import (
    map_dict, filter_dict, merge_dicts,
    pick, omit, transform_keys, transform_values
)

# map_dict - 딕셔너리 값에 함수 적용
scores = {"alice": 85, "bob": 92, "charlie": 78}
percentages = map_dict(lambda score: f"{score}%", scores)
print(percentages)  # {"alice": "85%", "bob": "92%", "charlie": "78%"}

# filter_dict - 조건에 맞는 항목만 필터링
high_scores = filter_dict(lambda k, v: v >= 80, scores)
print(high_scores)  # {"alice": 85, "bob": 92}

# merge_dicts - 여러 딕셔너리 병합
dict1 = {"a": 1, "b": 2}
dict2 = {"b": 3, "c": 4}
dict3 = {"c": 5, "d": 6}

merged = merge_dicts(dict1, dict2, dict3)
print(merged)  # {"a": 1, "b": 3, "c": 5, "d": 6} (나중 값이 우선)

# pick / omit - 특정 키만 선택/제외
data = {"name": "Alice", "age": 30, "email": "alice@example.com", "password": "secret"}

public_data = pick(["name", "age"], data)
print(public_data)  # {"name": "Alice", "age": 30}

safe_data = omit(["password"], data)
print(safe_data)  # {"name": "Alice", "age": 30, "email": "alice@example.com"}

# transform_keys / transform_values - 키/값 변환
user_data = {"first_name": "Alice", "last_name": "Smith", "user_age": 30}

# 키를 카멜케이스로 변환
camel_case = transform_keys(lambda k: k.replace("_", "").lower(), user_data)
print(camel_case)  # {"firstname": "Alice", "lastname": "Smith", "userage": 30}

# 모든 값을 문자열로 변환
string_values = transform_values(str, user_data)
print(string_values)  # {"first_name": "Alice", "last_name": "Smith", "user_age": "30"}
```

### 집합 연산

```python
from rfs.hof.collections import (
    union, intersection, difference, symmetric_difference,
    is_subset, is_superset, cartesian_product
)

set_a = {1, 2, 3, 4, 5}
set_b = {4, 5, 6, 7, 8}
set_c = {1, 2, 3}

# 집합 연산
union_result = union(set_a, set_b)
print(union_result)  # {1, 2, 3, 4, 5, 6, 7, 8}

intersection_result = intersection(set_a, set_b)
print(intersection_result)  # {4, 5}

difference_result = difference(set_a, set_b)
print(difference_result)  # {1, 2, 3}

sym_diff = symmetric_difference(set_a, set_b)
print(sym_diff)  # {1, 2, 3, 6, 7, 8}

# 집합 관계 확인
print(is_subset(set_c, set_a))    # True
print(is_superset(set_a, set_c))  # True

# 카르테지안 곱
colors = ["red", "blue"]
sizes = ["S", "M", "L"]
products = cartesian_product(colors, sizes)
print(list(products))  # [("red", "S"), ("red", "M"), ("red", "L"), ("blue", "S"), ("blue", "M"), ("blue", "L")]
```

### 함수형 컬렉션 연산자

```python
from rfs.hof.collections import (
    any_match, all_match, none_match,
    find, find_index, count_where,
    max_by, min_by, sort_by
)

numbers = [1, 3, 5, 7, 8, 10, 12]

# 조건 매칭
has_even = any_match(lambda x: x % 2 == 0, numbers)
print(has_even)  # True

all_positive = all_match(lambda x: x > 0, numbers)
print(all_positive)  # True

no_negative = none_match(lambda x: x < 0, numbers)
print(no_negative)  # True

# 요소 찾기
first_even = find(lambda x: x % 2 == 0, numbers)
print(first_even)  # 8

first_even_index = find_index(lambda x: x % 2 == 0, numbers)
print(first_even_index)  # 4

even_count = count_where(lambda x: x % 2 == 0, numbers)
print(even_count)  # 3

# 사용자 데이터로 예제
users = [
    {"name": "Alice", "age": 30, "score": 85},
    {"name": "Bob", "age": 25, "score": 92},
    {"name": "Charlie", "age": 35, "score": 78}
]

# 최대/최소값 찾기 (키 함수 기준)
youngest = min_by(lambda user: user["age"], users)
print(youngest)  # {"name": "Bob", "age": 25, "score": 92}

highest_score = max_by(lambda user: user["score"], users)
print(highest_score)  # {"name": "Bob", "age": 25, "score": 92}

# 정렬
by_age = sort_by(lambda user: user["age"], users)
print([user["name"] for user in by_age])  # ["Bob", "Alice", "Charlie"]

by_score_desc = sort_by(lambda user: -user["score"], users)
print([user["name"] for user in by_score_desc])  # ["Bob", "Alice", "Charlie"]
```

### 지연 평가와 이터레이터

```python
from rfs.hof.collections import (
    lazy_map, lazy_filter, lazy_take,
    iterate, cycle, repeat, range_infinite
)

# lazy_map - 지연 평가 맵
def expensive_computation(x):
    print(f"Computing {x}")
    return x ** 2

numbers = [1, 2, 3, 4, 5]
lazy_squares = lazy_map(expensive_computation, numbers)

# 아직 계산되지 않음
print("Created lazy iterator")

# 첫 3개만 사용
first_three = list(lazy_take(3, lazy_squares))
print(first_three)  # [1, 4, 9] (1, 2, 3만 계산됨)

# lazy_filter - 지연 평가 필터
large_numbers = range(1000000)  # 큰 데이터셋
lazy_evens = lazy_filter(lambda x: x % 2 == 0, large_numbers)
first_five_evens = list(lazy_take(5, lazy_evens))
print(first_five_evens)  # [0, 2, 4, 6, 8]

# iterate - 함수를 반복 적용하여 무한 시퀀스 생성
powers_of_two = iterate(lambda x: x * 2, 1)
first_ten_powers = list(lazy_take(10, powers_of_two))
print(first_ten_powers)  # [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]

# cycle - 컬렉션을 무한 반복
colors = ["red", "green", "blue"]
color_cycle = cycle(colors)
first_seven_colors = list(lazy_take(7, color_cycle))
print(first_seven_colors)  # ["red", "green", "blue", "red", "green", "blue", "red"]

# repeat - 값을 무한 반복
default_value = repeat(42)
five_defaults = list(lazy_take(5, default_value))
print(five_defaults)  # [42, 42, 42, 42, 42]
```

### 트랜스듀서 패턴

```python
from rfs.hof.collections import transduce, compose_transducers

# 트랜스듀서 정의
def mapping(transform_fn):
    def transducer(reducing_fn):
        def reducer(acc, item):
            transformed = transform_fn(item)
            return reducing_fn(acc, transformed)
        return reducer
    return transducer

def filtering(predicate_fn):
    def transducer(reducing_fn):
        def reducer(acc, item):
            if predicate_fn(item):
                return reducing_fn(acc, item)
            return acc
        return reducer
    return transducer

# 컬렉션 처리
data = range(1, 11)  # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# 트랜스듀서 합성
xform = compose_transducers(
    filtering(lambda x: x % 2 == 0),  # 짝수만
    mapping(lambda x: x ** 2),        # 제곱
    filtering(lambda x: x > 10)       # 10보다 큰 것만
)

# 트랜스듀서 적용
result = transduce(xform, list, data)
print(result)  # [16, 36, 64, 100]

# 다른 reducing 함수 사용
sum_result = transduce(xform, lambda acc, x: acc + x, 0, data)
print(sum_result)  # 216 (16 + 36 + 64 + 100)
```

### 실제 사용 예제: 데이터 분석

```python
from rfs.hof.collections import *
import json
from datetime import datetime

# 샘플 사용자 데이터
users = [
    {"id": 1, "name": "Alice", "age": 28, "department": "Engineering", "salary": 75000, "join_date": "2020-01-15"},
    {"id": 2, "name": "Bob", "age": 32, "department": "Engineering", "salary": 85000, "join_date": "2019-03-20"},
    {"id": 3, "name": "Charlie", "age": 25, "department": "Marketing", "salary": 55000, "join_date": "2021-06-10"},
    {"id": 4, "name": "Diana", "age": 35, "department": "Engineering", "salary": 95000, "join_date": "2018-08-05"},
    {"id": 5, "name": "Eve", "age": 29, "department": "Sales", "salary": 60000, "join_date": "2020-11-12"}
]

# 데이터 분석 파이프라인
def analyze_users(users):
    # 부서별 그룹화
    by_department = group_by(lambda u: u["department"], users)
    
    # 각 부서별 통계
    department_stats = map_dict(
        lambda employees: {
            "count": len(employees),
            "avg_salary": sum(emp["salary"] for emp in employees) / len(employees),
            "avg_age": sum(emp["age"] for emp in employees) / len(employees),
            "total_salary": sum(emp["salary"] for emp in employees)
        },
        by_department
    )
    
    # 고연봉자 찾기 (상위 20%)
    salary_threshold = sorted([u["salary"] for u in users], reverse=True)[1]  # 상위 20%
    high_earners = filter_list(lambda u: u["salary"] >= salary_threshold, users)
    
    # 경력별 그룹화 (입사년도 기준)
    def get_tenure_group(user):
        join_year = int(user["join_date"][:4])
        if join_year <= 2018:
            return "Senior (2018 or earlier)"
        elif join_year <= 2020:
            return "Mid (2019-2020)"
        else:
            return "Junior (2021+)"
    
    by_tenure = group_by(get_tenure_group, users)
    
    return {
        "total_employees": len(users),
        "department_stats": department_stats,
        "high_earners": [pick(["name", "department", "salary"], u) for u in high_earners],
        "tenure_distribution": map_dict(len, by_tenure)
    }

# 분석 실행
analysis = analyze_users(users)
print(json.dumps(analysis, indent=2))
```

## 관련 문서

- [HOF Core](core.md) - 핵심 고차 함수들
- [HOF Monads](monads.md) - 모나드 패턴 구현
- [함수형 프로그래밍](../../01-core-patterns.md#functional-programming) - 함수형 패턴 개념