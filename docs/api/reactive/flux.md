# Flux API

Flux reactive stream API documentation for RFS Framework.

**주요 클래스:**
- `Flux`: 다중 값 비동기 스트림

## 사용 예제

### 기본 Flux 생성

```python
from rfs.reactive import Flux
import asyncio

# 리스트로부터 Flux 생성
flux = Flux.from_iterable([1, 2, 3, 4, 5])
result = await flux.collect_list()
print(result)  # [1, 2, 3, 4, 5]

# 빈 Flux 생성
empty_flux = Flux.empty()
result = await empty_flux.collect_list()
print(result)  # []

# 무한 시퀀스 생성
infinite_flux = Flux.range(1, 1000000).take(5)
result = await infinite_flux.collect_list()
print(result)  # [1, 2, 3, 4, 5]

# 에러 Flux 생성
error_flux = Flux.error(ValueError("Something went wrong"))
try:
    await error_flux.collect_list()
except ValueError as e:
    print(f"Error: {e}")
```

### 비동기 스트림 생성

```python
from rfs.reactive import Flux
import asyncio
import aiofiles

async def read_file_lines(filename: str):
    """파일의 각 라인을 비동기적으로 읽기"""
    async with aiofiles.open(filename, 'r') as f:
        async for line in f:
            yield line.strip()

# 비동기 제너레이터를 Flux로 변환
def file_lines_flux(filename: str) -> Flux[str]:
    return Flux.from_async_iterable(read_file_lines(filename))

# 사용
lines_flux = file_lines_flux("data.txt")
lines = await lines_flux.collect_list()
print(f"Read {len(lines)} lines")

# 주기적 스트림 생성
interval_flux = Flux.interval(1.0).take(5)  # 1초마다 값 방출, 5개만
values = await interval_flux.collect_list()
print(values)  # [0, 1, 2, 3, 4]
```

### Flux 변환 연산자

```python
from rfs.reactive import Flux

# map - 각 요소 변환
numbers_flux = Flux.from_iterable([1, 2, 3, 4, 5])
squared_flux = numbers_flux.map(lambda x: x ** 2)
result = await squared_flux.collect_list()
print(result)  # [1, 4, 9, 16, 25]

# flatMap - 각 요소를 Flux로 변환 후 평탄화
def expand_number(n):
    return Flux.from_iterable([n, n * 10, n * 100])

expanded_flux = (
    Flux.from_iterable([1, 2, 3])
    .flat_map(expand_number)
)
result = await expanded_flux.collect_list()
print(result)  # [1, 10, 100, 2, 20, 200, 3, 30, 300]

# filter - 조건부 필터링
even_flux = (
    Flux.range(1, 10)
    .filter(lambda x: x % 2 == 0)
)
result = await even_flux.collect_list()
print(result)  # [2, 4, 6, 8, 10]

# distinct - 중복 제거
unique_flux = (
    Flux.from_iterable([1, 2, 2, 3, 3, 3, 4])
    .distinct()
)
result = await unique_flux.collect_list()
print(result)  # [1, 2, 3, 4]
```

### 그룹화와 집계

```python
from rfs.reactive import Flux
from collections import defaultdict

# groupBy - 키별 그룹화
def group_by_length(word: str) -> int:
    return len(word)

words_flux = Flux.from_iterable(["cat", "dog", "elephant", "ant", "butterfly"])
grouped_flux = words_flux.group_by(group_by_length)

# 그룹별로 수집
groups = {}
async for length, words in grouped_flux:
    groups[length] = await words.collect_list()

print(groups)  # {3: ["cat", "dog", "ant"], 8: ["elephant"], 9: ["butterfly"]}

# reduce - 집계
sum_flux = (
    Flux.range(1, 100)
    .reduce(0, lambda acc, x: acc + x)
)
total = await sum_flux.subscribe()
print(total)  # 5050

# scan - 누적 값 방출
cumulative_flux = (
    Flux.from_iterable([1, 2, 3, 4, 5])
    .scan(0, lambda acc, x: acc + x)
)
result = await cumulative_flux.collect_list()
print(result)  # [0, 1, 3, 6, 10, 15]
```

### 병렬 처리

```python
from rfs.reactive import Flux
import asyncio
import time

# 무거운 작업 시뮬레이션
async def heavy_computation(n: int) -> int:
    await asyncio.sleep(0.1)  # 100ms 작업 시뮬레이션
    return n ** 2

# 순차 처리
start = time.time()
sequential_result = await (
    Flux.range(1, 10)
    .flat_map(lambda x: Flux.from_callable(lambda: heavy_computation(x)))
    .collect_list()
)
sequential_time = time.time() - start
print(f"Sequential: {sequential_time:.2f}s")

# 병렬 처리 (최대 4개 동시 실행)
start = time.time()
parallel_result = await (
    Flux.range(1, 10)
    .parallel(max_concurrency=4)
    .flat_map(lambda x: Flux.from_callable(lambda: heavy_computation(x)))
    .collect_list()
)
parallel_time = time.time() - start
print(f"Parallel: {parallel_time:.2f}s")  # 훨씬 빠름

print(f"Speedup: {sequential_time / parallel_time:.1f}x")
```

### 윈도우와 버퍼링

```python
from rfs.reactive import Flux

# buffer - 지정된 크기로 버퍼링
buffered_flux = (
    Flux.range(1, 12)
    .buffer(3)  # 3개씩 묶어서 처리
)
result = await buffered_flux.collect_list()
print(result)  # [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]

# window - 시간 기반 윈도우
time_windowed_flux = (
    Flux.interval(0.1)  # 100ms마다 값 방출
    .take(20)
    .window_timeout(5, 0.5)  # 최대 5개 또는 500ms마다 윈도우
)

windows = []
async for window in time_windowed_flux:
    window_data = await window.collect_list()
    windows.append(window_data)

print(f"Created {len(windows)} windows")

# sliding window - 슬라이딩 윈도우
sliding_flux = (
    Flux.from_iterable([1, 2, 3, 4, 5, 6, 7, 8])
    .sliding_window(size=3, step=1)
)
result = await sliding_flux.collect_list()
print(result)  # [[1,2,3], [2,3,4], [3,4,5], [4,5,6], [5,6,7], [6,7,8]]
```

### 에러 처리와 회복

```python
from rfs.reactive import Flux
import random

# 에러가 발생할 수 있는 연산
def risky_operation(n: int) -> int:
    if random.random() < 0.3:  # 30% 확률로 에러
        raise RuntimeError(f"Error processing {n}")
    return n * 2

# onErrorContinue - 에러 무시하고 계속
safe_flux = (
    Flux.range(1, 20)
    .map(risky_operation)
    .on_error_continue(lambda error, value: print(f"Skipping {value} due to {error}"))
)
result = await safe_flux.collect_list()
print(f"Processed {len(result)} items successfully")

# retry - 전체 스트림 재시도
def unreliable_source():
    return Flux.from_iterable([1, 2, 3]).map(risky_operation)

reliable_flux = (
    Flux.defer(unreliable_source)  # 지연 실행
    .retry(max_attempts=3, delay=0.5)
    .on_error_return([])  # 최종 실패 시 빈 리스트
)

result = await reliable_flux.collect_list()
print(result)
```

### 백프레셔와 플로우 제어

```python
from rfs.reactive import Flux
import asyncio

# 빠른 생산자와 느린 소비자
async def slow_consumer(item):
    await asyncio.sleep(0.1)  # 느린 처리
    return f"Processed: {item}"

# 백프레셔 처리
controlled_flux = (
    Flux.range(1, 1000)  # 빠른 생산자
    .on_backpressure_buffer(max_size=10)  # 버퍼 크기 제한
    .flat_map(
        lambda x: Flux.from_callable(lambda: slow_consumer(x)),
        max_concurrency=3  # 최대 3개 동시 처리
    )
)

# 처리된 항목 수집
result = await controlled_flux.take(20).collect_list()
print(f"Processed {len(result)} items with backpressure control")

# 샘플링 - 일정 간격으로 샘플링
sampled_flux = (
    Flux.interval(0.01)  # 10ms마다 값 생성
    .take(1000)
    .sample(0.1)  # 100ms마다 샘플링
)
samples = await sampled_flux.collect_list()
print(f"Sampled {len(samples)} items from 1000")
```

### 복합 스트림 조합

```python
from rfs.reactive import Flux

# merge - 여러 스트림 병합
stream1 = Flux.from_iterable([1, 3, 5]).delay_elements(0.1)
stream2 = Flux.from_iterable([2, 4, 6]).delay_elements(0.15)
stream3 = Flux.from_iterable([7, 8, 9]).delay_elements(0.05)

merged_flux = Flux.merge(stream1, stream2, stream3)
result = await merged_flux.collect_list()
print(f"Merged result: {sorted(result)}")

# zip - 스트림 결합
names = Flux.from_iterable(["Alice", "Bob", "Charlie"])
ages = Flux.from_iterable([25, 30, 35])
cities = Flux.from_iterable(["New York", "London", "Tokyo"])

people_flux = Flux.zip(
    names, ages, cities,
    lambda name, age, city: {"name": name, "age": age, "city": city}
)
people = await people_flux.collect_list()
print(people)

# combineLatest - 최신 값 조합
temperature = Flux.interval(1.0).map(lambda x: 20 + x)  # 온도 센서
humidity = Flux.interval(1.5).map(lambda x: 40 + x * 2)  # 습도 센서

weather_flux = (
    Flux.combine_latest(temperature, humidity)
    .map(lambda temp, hum: f"Temperature: {temp}°C, Humidity: {hum}%")
    .take(5)
)

weather_data = await weather_flux.collect_list()
for reading in weather_data:
    print(reading)
```

### 고급 연산자

```python
from rfs.reactive import Flux

# switchMap - 새 스트림으로 전환
def search_results(query: str) -> Flux[str]:
    # 검색 결과 시뮬레이션
    return Flux.from_iterable([f"Result {i} for '{query}'" for i in range(3)])

search_queries = Flux.from_iterable(["python", "java", "javascript"])
latest_results = search_queries.switch_map(search_results)
result = await latest_results.collect_list()
print(result)

# takeWhile / skipWhile - 조건부 제어
numbers = Flux.from_iterable([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

# 5 미만인 동안만 가져오기
taken = await numbers.take_while(lambda x: x < 5).collect_list()
print(f"Taken: {taken}")  # [1, 2, 3, 4]

# 5 미만인 동안 건너뛰기
skipped = await numbers.skip_while(lambda x: x < 5).collect_list()
print(f"After skip: {skipped}")  # [5, 6, 7, 8, 9, 10]

# concatMap - 순서 보장 평탄화
def process_batch(n: int) -> Flux[str]:
    return Flux.from_iterable([f"batch-{n}-item-{i}" for i in range(3)])

ordered_flux = (
    Flux.from_iterable([1, 2, 3])
    .concat_map(process_batch)  # 순서 보장
)
ordered_result = await ordered_flux.collect_list()
print(ordered_result)  # batch-1 항목들이 먼저, 그 다음 batch-2, batch-3
```

## 관련 문서

- [Mono API](mono.md) - 단일 값 반응형 스트림
- [반응형 프로그래밍](../../01-core-patterns.md#reactive-programming) - 반응형 패턴 개념
- [비동기 처리](../../16-hot-library.md) - 함수형 반응형 유틸리티