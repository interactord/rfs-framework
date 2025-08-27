# 리액티브 프로그래밍 가이드

## 개요

RFS Framework는 Project Reactor 스타일의 Mono/Flux 패턴을 Python에서 구현하여, 비동기 데이터 스트림을 함수형으로 처리합니다. Result 패턴과 완벽하게 통합되어 타입 안정성을 보장합니다.

## 핵심 개념

1. **Mono**: 0개 또는 1개의 요소를 비동기로 방출
2. **Flux**: 0개 이상의 요소를 비동기로 방출
3. **Backpressure**: 소비자가 처리 속도를 제어
4. **Cold vs Hot**: 구독 시점에 따른 스트림 동작 차이

## Mono 패턴

### 기본 사용법

```python
from rfs.reactive.mono import Mono
from rfs.core.result import Result, Success, Failure

# Mono 생성
mono = Mono.just(42)  # 단일 값
mono_empty = Mono.empty()  # 빈 Mono
mono_error = Mono.error("Something went wrong")  # 에러 Mono

# 비동기 작업 래핑
async def fetch_user(id: str) -> User:
    # 데이터베이스에서 사용자 조회
    return await db.get_user(id)

mono_user = Mono.from_callable(lambda: fetch_user("123"))

# Result와 통합
async def safe_fetch_user(id: str) -> Result[User, str]:
    try:
        user = await fetch_user(id)
        return Success(user)
    except Exception as e:
        return Failure(str(e))

mono_result = Mono.from_callable(lambda: safe_fetch_user("123"))
```

### 변환 연산자

```python
# map: 값 변환
mono = Mono.just(10)
    .map(lambda x: x * 2)  # 20
    .map(lambda x: str(x))  # "20"

# flatMap: Mono를 반환하는 함수 체이닝
def fetch_profile(user_id: str) -> Mono[Profile]:
    return Mono.from_callable(lambda: get_profile(user_id))

result = Mono.just("user123")
    .flat_map(fetch_profile)  # Mono[Profile]
    .map(lambda p: p.to_dict())  # dict로 변환

# filter: 조건에 맞는 값만 통과
mono = Mono.just(42)
    .filter(lambda x: x > 40)  # 통과
    .filter(lambda x: x < 30)  # 빈 Mono

# switchIfEmpty: 빈 경우 대체 Mono
result = fetch_from_cache(key)
    .switch_if_empty(fetch_from_database(key))
    .switch_if_empty(Mono.just(default_value))
```

### 에러 처리

```python
# onErrorReturn: 에러 시 기본값 반환
mono = Mono.error("Network error")
    .on_error_return(default_user)

# onErrorResume: 에러 시 다른 Mono로 복구
mono = fetch_from_primary()
    .on_error_resume(lambda e: fetch_from_backup())

# doOnError: 에러 시 부수 효과
mono = fetch_data()
    .do_on_error(lambda e: logger.error(f"Failed: {e}"))
    .on_error_return(None)

# Result 패턴과 함께
async def handle_user_request(id: str) -> Result[UserDto, str]:
    return await Mono.from_callable(lambda: fetch_user(id))
        .map(lambda u: UserDto.from_entity(u))
        .map(lambda dto: Success(dto))
        .on_error_resume(lambda e: Mono.just(Failure(str(e))))
        .block()
```

## Flux 패턴

### 기본 사용법

```python
from rfs.reactive.flux import Flux

# Flux 생성
flux = Flux.from_iterable([1, 2, 3, 4, 5])
flux_range = Flux.range(1, 100)
flux_interval = Flux.interval(1.0)  # 1초마다 값 방출

# 제너레이터에서 생성
def generate_data():
    for i in range(10):
        yield i ** 2

flux = Flux.from_generator(generate_data)

# 비동기 이터레이터
async def async_generator():
    for i in range(10):
        await asyncio.sleep(0.1)
        yield i

flux = Flux.from_async_iterable(async_generator())
```

### 변환 연산자

```python
# map: 각 요소 변환
flux = Flux.from_iterable([1, 2, 3])
    .map(lambda x: x * 2)  # [2, 4, 6]

# flatMap: 각 요소를 Flux로 변환 후 평탄화
def fetch_orders(user_id: str) -> Flux[Order]:
    return Flux.from_callable(lambda: get_orders(user_id))

flux = Flux.from_iterable(user_ids)
    .flat_map(fetch_orders)  # 모든 사용자의 주문을 하나의 스트림으로

# filter: 조건 필터링
flux = Flux.range(1, 10)
    .filter(lambda x: x % 2 == 0)  # [2, 4, 6, 8]

# take/skip: 요소 제한
flux = Flux.range(1, 100)
    .skip(10)  # 처음 10개 건너뛰기
    .take(5)   # 5개만 가져오기

# distinct: 중복 제거
flux = Flux.from_iterable([1, 2, 2, 3, 3, 3])
    .distinct()  # [1, 2, 3]

# window: 윈도우 단위로 그룹화
flux = Flux.range(1, 100)
    .window(10)  # 10개씩 묶어서 Flux[Flux[int]]

# buffer: 버퍼링
flux = Flux.interval(0.1)
    .buffer(10)  # 10개씩 모아서 리스트로
```

### 집계 연산자

```python
# reduce: 누적 연산
total = await Flux.from_iterable([1, 2, 3, 4, 5])
    .reduce(0, lambda acc, x: acc + x)  # 15
    .block()

# collect: 리스트로 수집
items = await Flux.from_iterable(range(10))
    .filter(lambda x: x % 2 == 0)
    .collect()  # [0, 2, 4, 6, 8]

# count: 개수 세기
count = await Flux.from_iterable(items)
    .filter(is_valid)
    .count()

# all/any: 조건 검사
all_valid = await Flux.from_iterable(items)
    .all(lambda x: x > 0)  # 모두 양수인가?

has_error = await Flux.from_iterable(results)
    .any(lambda r: r.is_failure())  # 실패가 하나라도 있는가?
```

## Backpressure 처리

### 기본 전략

```python
from rfs.reactive.backpressure import BackpressureStrategy

# BUFFER: 모든 요소를 버퍼에 저장 (메모리 주의)
flux = source.on_backpressure_buffer(1000)  # 최대 1000개 버퍼

# DROP: 처리 못하는 요소는 버림
flux = source.on_backpressure_drop()

# LATEST: 최신 요소만 유지
flux = source.on_backpressure_latest()

# ERROR: 백프레셔 발생 시 에러
flux = source.on_backpressure_error()
```

### Rate Limiting

```python
# 처리 속도 제한
flux = Flux.interval(0.01)  # 10ms마다 생성
    .limit_rate(10)  # 초당 최대 10개 처리
    .map(process_item)

# 배치 처리
flux = Flux.from_async_iterable(stream)
    .buffer_timeout(100, 1.0)  # 100개 또는 1초마다 배치
    .flat_map(process_batch)
```

## Hot vs Cold Streams

### Cold Stream (기본)

```python
# Cold: 구독할 때마다 처음부터 시작
cold = Flux.from_callable(fetch_data)

# 각 구독자가 독립적인 데이터 받음
subscription1 = cold.subscribe(lambda x: print(f"Sub1: {x}"))
await asyncio.sleep(1)
subscription2 = cold.subscribe(lambda x: print(f"Sub2: {x}"))
```

### Hot Stream (공유)

```python
# Hot: 모든 구독자가 같은 스트림 공유
hot = Flux.interval(1.0).share()  # 공유 스트림

# 구독 시점부터 데이터 받음
subscription1 = hot.subscribe(lambda x: print(f"Sub1: {x}"))
await asyncio.sleep(3)
subscription2 = hot.subscribe(lambda x: print(f"Sub2: {x}"))  # 3초 후 데이터부터

# replay: 최근 N개 재생
hot = Flux.interval(1.0)
    .replay(3)  # 최근 3개 저장
    .auto_connect(2)  # 2명 구독 시 시작
```

## 병렬 처리

### 병렬 Flux

```python
from rfs.reactive.parallel import ParallelFlux

# 병렬 처리
parallel = Flux.range(1, 1000)
    .parallel(4)  # 4개 스레드로 병렬화
    .run_on(Schedulers.parallel())
    .map(expensive_operation)
    .sequential()  # 다시 순차 스트림으로

# 비동기 병렬 처리
async def process_parallel(items: list) -> list:
    tasks = [
        Flux.just(item)
            .map(heavy_computation)
            .block_async()
        for item in items
    ]
    
    results = await asyncio.gather(*tasks)
    return results
```

## 실전 예제

### 1. API 데이터 수집

```python
async def fetch_paginated_data(api_url: str) -> Flux[dict]:
    """페이지네이션 API 데이터 수집"""
    
    def fetch_page(page: int) -> Mono[list]:
        return Mono.from_callable(
            lambda: requests.get(f"{api_url}?page={page}").json()
        )
    
    return Flux.range(1, 100)  # 최대 100 페이지
        .flat_map(fetch_page)  # 각 페이지 조회
        .take_while(lambda data: len(data) > 0)  # 빈 페이지면 중단
        .flat_map(lambda page: Flux.from_iterable(page))  # 각 항목으로 평탄화
        .filter(lambda item: item.get("status") == "active")  # 활성 항목만
        .map(transform_item)  # 데이터 변환
        .on_error_resume(lambda e: {
            logger.error(f"Failed: {e}")
            return Flux.empty()
        })
```

### 2. 실시간 데이터 처리

```python
async def process_real_time_stream(stream_url: str):
    """실시간 스트림 처리"""
    
    return Flux.from_stream(stream_url)
        .window_timeout(100, 5.0)  # 100개 또는 5초 윈도우
        .flat_map(lambda window: 
            window.collect()
                .map(aggregate_data)  # 윈도우 데이터 집계
                .flat_map(save_to_database)  # DB 저장
        )
        .retry(3)  # 실패 시 3회 재시도
        .do_on_error(lambda e: alert_admin(e))  # 에러 알림
        .subscribe(
            on_next=lambda x: logger.info(f"Processed: {x}"),
            on_error=lambda e: logger.error(f"Stream error: {e}"),
            on_complete=lambda: logger.info("Stream completed")
        )
```

### 3. 배치 처리 파이프라인

```python
async def batch_processing_pipeline(input_files: list) -> Result[int, str]:
    """배치 처리 파이프라인"""
    
    return await Flux.from_iterable(input_files)
        .flat_map(read_file, concurrency=4)  # 병렬로 파일 읽기
        .flat_map(lambda content: 
            Flux.from_iterable(content.split("\n")))  # 라인 단위로
        .filter(lambda line: line.strip())  # 빈 라인 제거
        .map(parse_record)  # 레코드 파싱
        .filter(validate_record)  # 유효성 검사
        .buffer(1000)  # 1000개씩 배치
        .flat_map(lambda batch:
            Mono.from_callable(lambda: bulk_insert(batch)))  # 벌크 삽입
        .count()  # 처리된 배치 수
        .map(lambda count: Success(count))
        .on_error_return(lambda e: Failure(str(e)))
        .block()
```

## 테스트 전략

### 1. StepVerifier 사용

```python
from rfs.reactive.test import StepVerifier

def test_flux_transformation():
    flux = Flux.from_iterable([1, 2, 3])
        .map(lambda x: x * 2)
        .filter(lambda x: x > 2)
    
    StepVerifier.create(flux)
        .expect_next(4)
        .expect_next(6)
        .verify_complete()

def test_error_handling():
    flux = Flux.just(1, 2, 0, 3)
        .map(lambda x: 10 / x)
        .on_error_return(-1)
    
    StepVerifier.create(flux)
        .expect_next(10.0)
        .expect_next(5.0)
        .expect_next(-1)
        .verify_complete()
```

### 2. 가상 시간 테스트

```python
def test_interval_flux():
    with VirtualTimeScheduler() as scheduler:
        flux = Flux.interval(1.0, scheduler=scheduler)
            .take(3)
        
        StepVerifier.create(flux)
            .expect_no_event(1.0)
            .expect_next(0)
            .then_await(1.0)
            .expect_next(1)
            .then_await(1.0)
            .expect_next(2)
            .verify_complete()
```

## 모범 사례

1. **Cold 기본 사용**: Hot은 필요한 경우만 (실시간 데이터)
2. **Backpressure 고려**: 생산/소비 속도 차이 대비
3. **에러 복구**: onErrorResume으로 graceful degradation
4. **리소스 관리**: using 연산자로 자동 정리
5. **병렬 처리**: CPU 바운드는 parallel(), I/O는 flatMap
6. **테스트 우선**: StepVerifier로 스트림 동작 검증
7. **타임아웃 설정**: 네트워크 작업은 항상 타임아웃