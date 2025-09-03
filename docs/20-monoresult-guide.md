# MonoResult/FluxResult 가이드

MonoResult와 FluxResult는 RFS Framework의 핵심 기능으로, Reactive Streams와 Result 패턴을 통합한 강력한 비동기 처리 솔루션입니다.

## 개요

### MonoResult[T, E]
단일 비동기 값을 처리하는 Mono + Result 패턴 통합 클래스입니다.

### FluxResult[T, E] 
배치 및 스트림 처리를 위한 Flux + Result 패턴 통합 클래스입니다.

## MonoResult 주요 기능

### 기본 사용법

```python
from rfs.reactive.mono_result import MonoResult
from rfs.core.result import Success, Failure

# 비동기 함수를 MonoResult로 감싸기
async def fetch_user(user_id: str) -> Result[User, str]:
    # ... 사용자 조회 로직
    return Success(user)

# MonoResult 생성 및 체이닝
result = await (
    MonoResult.from_async_result(lambda: fetch_user("123"))
    .bind_async_result(lambda user: validate_user(user))
    .map_result(lambda user: transform_user(user))
    .timeout(5.0)  # 5초 타임아웃
    .to_result()
)

if result.is_success():
    user = result.unwrap()
else:
    error = result.unwrap_error()
```

### 병렬 처리

```python
# 여러 작업을 병렬로 실행
mono_results = [
    MonoResult.from_async_result(lambda: fetch_user(f"user_{i}"))
    for i in range(10)
]

results = await MonoResult.parallel_map_async(
    mono_results, 
    max_concurrent=3  # 최대 3개 동시 실행
)

# 성공한 결과만 필터링
successful_results = [r for r in results if r.is_success()]
```

### 에러 처리 및 재시도

```python
async def process_with_retry():
    return await (
        MonoResult.from_async_result(lambda: unreliable_operation())
        .retry_on_failure(max_retries=3, delay=1.0)  # 3번 재시도, 1초 간격
        .map_error(lambda e: f"작업 실패: {str(e)}")
        .to_result()
    )
```

## FluxResult 주요 기능

### 배치 처리

```python
from rfs.reactive.flux_result import FluxResult

# 사용자 ID 목록을 배치로 처리
user_ids = ["user1", "user2", "user3", "user4", "user5"]

flux_result = await (
    FluxResult.from_iterable_async(user_ids, fetch_user)
    .filter_results(lambda user: user.is_active)  # 활성 사용자만
    .map_results(lambda user: enrich_user_profile(user))  # 프로필 보강
    .batch_collect(batch_size=2, max_concurrent=3)  # 배치 수집
)

# 결과 확인
print(f"총 {flux_result.count_total()}개 중 {flux_result.count_success()}개 성공")
print(f"성공률: {flux_result.success_rate():.2%}")
```

### 스트림 변환

```python
# 복잡한 데이터 파이프라인
pipeline_result = await (
    FluxResult.from_iterable_async(raw_data_list, parse_data)
    .map_results(validate_data)
    .filter_results(lambda data: data.quality_score > 0.8)
    .flat_map_results(lambda data: expand_data(data))
    .reduce_results(lambda acc, data: merge_data(acc, data), initial={})
)

final_result = await pipeline_result.collect_results()
```

## 실용적인 패턴들

### 웹 API 처리

```python
@app.get("/users/{user_id}")
async def get_user_endpoint(user_id: str):
    result = await (
        MonoResult.from_async_result(lambda: user_service.get_user(user_id))
        .bind_async_result(lambda user: permission_service.check_access(user))
        .map_result(lambda user: user_serializer.serialize(user))
        .timeout(10.0)
        .to_result()
    )
    
    if result.is_success():
        return {"user": result.unwrap()}
    else:
        raise HTTPException(400, detail=result.unwrap_error())
```

### 데이터베이스 트랜잭션

```python
async def transfer_money(from_account: str, to_account: str, amount: float):
    return await (
        MonoResult.from_async_result(lambda: begin_transaction())
        .bind_async_result(lambda tx: debit_account(tx, from_account, amount))
        .bind_async_result(lambda tx: credit_account(tx, to_account, amount))
        .bind_async_result(lambda tx: commit_transaction(tx))
        .map_error(lambda e: rollback_and_return_error(e))
        .to_result()
    )
```

### 외부 API 통합

```python
async def aggregate_user_data(user_id: str):
    # 여러 외부 서비스에서 동시에 데이터 수집
    profile_mono = MonoResult.from_async_result(lambda: profile_service.get_profile(user_id))
    orders_mono = MonoResult.from_async_result(lambda: order_service.get_orders(user_id))
    preferences_mono = MonoResult.from_async_result(lambda: preference_service.get_preferences(user_id))
    
    # 모든 결과를 병렬로 수집
    results = await MonoResult.parallel_map_async([
        profile_mono, orders_mono, preferences_mono
    ], max_concurrent=3)
    
    # 결과 통합
    if all(r.is_success() for r in results):
        profile, orders, preferences = [r.unwrap() for r in results]
        return Success({
            "profile": profile,
            "orders": orders, 
            "preferences": preferences
        })
    else:
        errors = [r.unwrap_error() for r in results if r.is_failure()]
        return Failure(f"데이터 수집 실패: {', '.join(errors)}")
```

## 성능 최적화 팁

### 1. 적절한 동시성 제어
```python
# 너무 많은 동시 요청은 시스템 부하를 증가시킴
await MonoResult.parallel_map_async(tasks, max_concurrent=5)  # 적절한 수준
```

### 2. 타임아웃 설정
```python
# 응답성을 위해 적절한 타임아웃 설정
mono.timeout(30.0)  # 30초 타임아웃
```

### 3. 배치 크기 최적화
```python
# 메모리 사용량과 처리 속도의 균형
flux.batch_collect(batch_size=100, max_concurrent=10)
```

## 디버깅 및 모니터링

### 로깅 활용
```python
# 각 단계별 로깅
result = await (
    MonoResult.from_async_result(lambda: fetch_data())
    .inspect(lambda data: logger.info(f"데이터 조회 완료: {len(data)}개"))
    .bind_async_result(lambda data: process_data(data))
    .inspect(lambda processed: logger.info(f"처리 완료: {processed.status}"))
    .to_result()
)
```

### 에러 추적
```python
# 상세한 에러 정보 포함
result = await (
    mono
    .map_error(lambda e: {
        "error": str(e),
        "timestamp": datetime.now().isoformat(),
        "operation": "data_processing"
    })
    .to_result()
)
```

## 마이그레이션 가이드

### 기존 async/await 코드에서 마이그레이션

**Before (기존 코드):**
```python
async def process_user(user_id: str):
    try:
        user = await fetch_user(user_id)
        validated_user = await validate_user(user)
        processed_user = await process_user_data(validated_user)
        return processed_user
    except Exception as e:
        logger.error(f"사용자 처리 실패: {e}")
        raise e
```

**After (MonoResult 사용):**
```python
async def process_user(user_id: str) -> Result[User, str]:
    return await (
        MonoResult.from_async_result(lambda: fetch_user(user_id))
        .bind_async_result(lambda user: validate_user(user))
        .bind_async_result(lambda user: process_user_data(user))
        .map_error(lambda e: f"사용자 처리 실패: {str(e)}")
        .to_result()
    )
```

## 모범 사례

1. **일관된 에러 타입 사용**: 프로젝트 전체에서 통일된 에러 타입 사용
2. **적절한 타임아웃**: 모든 외부 호출에 타임아웃 설정
3. **명시적 에러 처리**: `map_error`를 사용하여 에러를 의미 있는 메시지로 변환
4. **로깅과 모니터링**: `inspect` 메서드로 중간 단계 추적
5. **리소스 관리**: 적절한 동시성 제어로 시스템 리소스 보호

## 추가 자료

- [Result 패턴 가이드](01-core-patterns.md)
- [Reactive Streams API](api/reactive/mono.md)
- [예제 코드 모음](examples/)