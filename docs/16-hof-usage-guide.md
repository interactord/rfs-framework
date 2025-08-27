# RFS Framework HOF (Higher-Order Functions) 사용 가이드

## 🎯 개요

**필수**: RFS Framework의 내장된 HOF 라이브러리를 최대한 활용하여 함수형 프로그래밍 스타일로 개발하세요.

RFS Framework는 Swift, Haskell, F# 등에서 영감을 받은 강력한 HOF 라이브러리를 제공합니다. 커스텀 구현 대신 **내장된 HOF를 우선 사용**하여 코드의 일관성과 품질을 향상시킵니다.

## 🏗️ HOF 라이브러리 구조

```
src/rfs/hof/
├── core.py          # 함수 합성, 커링, 파이프
├── collections.py   # Swift 스타일 컬렉션 연산
├── monads.py        # Maybe, Either, Result 모나드
├── async_hof.py     # 비동기 HOF 유틸리티
├── combinators.py   # 함수 결합자
├── decorators.py    # 함수형 데코레이터
└── guard.py         # Guard 패턴 (Swift 스타일)
```

## 🔥 핵심 HOF 패턴

### 1. 함수 합성 (Function Composition)

**❌ 나쁜 예: 중첩된 함수 호출**
```python
# 커스텀 구현 - 피해야 할 방식
def process_user_data(data):
    cleaned = clean_data(data)
    validated = validate_data(cleaned)  
    transformed = transform_data(validated)
    return save_data(transformed)

result = process_user_data(user_input)
```

**✅ 좋은 예: RFS HOF 사용**
```python
from rfs.hof.core import pipe, compose
from rfs.core.result import Result, Success, Failure

# HOF를 활용한 함수 합성
def clean_data(data: dict) -> Result[dict, str]:
    """데이터를 정제합니다."""
    if not data:
        return Failure("빈 데이터입니다")
    # 불필요한 필드 제거
    cleaned = {k: v for k, v in data.items() if v is not None}
    return Success(cleaned)

def validate_data(data: dict) -> Result[dict, str]:
    """데이터 유효성을 검증합니다."""
    required_fields = ["name", "email"]
    for field in required_fields:
        if field not in data:
            return Failure(f"필수 필드 누락: {field}")
    return Success(data)

def transform_data(data: dict) -> Result[dict, str]:
    """데이터를 변환합니다."""
    transformed = {
        **data,
        "created_at": datetime.now().isoformat(),
        "email": data["email"].lower()
    }
    return Success(transformed)

# pipe를 사용한 함수 합성
process_user = pipe(
    clean_data,
    lambda result: result.bind(validate_data),
    lambda result: result.bind(transform_data)
)

# 사용
result = process_user(user_input)
if result.is_success():
    user = result.unwrap()
    print(f"사용자 처리 완료: {user['name']}")
```

### 2. 컬렉션 연산 (Collection Operations)

**❌ 나쁜 예: 명령형 루프**
```python
# 커스텀 구현 - 피해야 할 방식
def process_orders(orders):
    valid_orders = []
    for order in orders:
        if order.get("amount", 0) > 0:
            valid_orders.append(order)
    
    processed_orders = []
    for order in valid_orders:
        order["processed_at"] = datetime.now()
        order["tax"] = order["amount"] * 0.1
        processed_orders.append(order)
    
    # 금액별로 그룹화
    groups = {}
    for order in processed_orders:
        amount_range = "high" if order["amount"] > 1000 else "low"
        if amount_range not in groups:
            groups[amount_range] = []
        groups[amount_range].append(order)
    
    return groups
```

**✅ 좋은 예: RFS HOF 사용**
```python
from rfs.hof.collections import (
    compact_map, group_by, first, partition
)
from rfs.hof.core import pipe, curry
from rfs.core.result import Result, Success

@curry
def add_tax_and_timestamp(tax_rate: float, order: dict) -> dict:
    """주문에 세금과 타임스탬프를 추가합니다."""
    return {
        **order,
        "processed_at": datetime.now().isoformat(),
        "tax": order["amount"] * tax_rate
    }

def validate_order(order: dict) -> Optional[dict]:
    """주문을 검증하고 유효한 경우 반환합니다."""
    return order if order.get("amount", 0) > 0 else None

def categorize_by_amount(order: dict) -> str:
    """주문 금액에 따라 카테고리를 반환합니다."""
    match order["amount"]:
        case amount if amount > 1000:
            return "high"
        case amount if amount > 100:
            return "medium"
        case _:
            return "low"

# HOF를 사용한 함수형 파이프라인
process_orders = pipe(
    # 유효한 주문만 필터링 (compact_map 사용)
    lambda orders: compact_map(validate_order, orders),
    # 세금과 타임스탬프 추가 (커링 활용)
    lambda orders: list(map(add_tax_and_timestamp(0.1), orders)),
    # 금액별로 그룹화
    lambda orders: group_by(categorize_by_amount, orders)
)

# 사용
result = process_orders(orders)
```

### 3. 모나드 활용 (Monads)

**❌ 나쁜 예: 중첩된 예외 처리**
```python
# 커스텀 구현 - 피해야 할 방식
def get_user_profile(user_id):
    try:
        user = fetch_user(user_id)
        if user is None:
            return None
        
        try:
            profile = fetch_profile(user.profile_id)
            if profile is None:
                return None
                
            try:
                preferences = fetch_preferences(profile.id)
                return {
                    "user": user,
                    "profile": profile, 
                    "preferences": preferences
                }
            except Exception:
                return None
        except Exception:
            return None
    except Exception:
        return None
```

**✅ 좋은 예: RFS HOF 모나드 사용**
```python
from rfs.hof.monads import Maybe, Result
from rfs.hof.core import pipe

def fetch_user_safe(user_id: str) -> Maybe[User]:
    """사용자를 안전하게 조회합니다."""
    try:
        user = fetch_user(user_id)
        return Maybe.just(user) if user else Maybe.nothing()
    except Exception:
        return Maybe.nothing()

def fetch_profile_safe(user: User) -> Maybe[Profile]:
    """프로필을 안전하게 조회합니다."""
    try:
        profile = fetch_profile(user.profile_id)
        return Maybe.just(profile) if profile else Maybe.nothing()
    except Exception:
        return Maybe.nothing()

def fetch_preferences_safe(profile: Profile) -> Maybe[dict]:
    """설정을 안전하게 조회합니다."""
    try:
        preferences = fetch_preferences(profile.id)
        return Maybe.just(preferences)
    except Exception:
        return Maybe.nothing()

def build_user_profile(user: User, profile: Profile, preferences: dict) -> dict:
    """사용자 프로필을 구성합니다."""
    return {
        "user": user,
        "profile": profile,
        "preferences": preferences
    }

# 모나드 체이닝을 사용한 안전한 파이프라인
def get_user_profile(user_id: str) -> Maybe[dict]:
    """사용자 전체 프로필을 조회합니다."""
    return (
        fetch_user_safe(user_id)
        .bind(lambda user: 
            fetch_profile_safe(user)
            .bind(lambda profile:
                fetch_preferences_safe(profile)
                .map(lambda prefs: build_user_profile(user, profile, prefs))
            )
        )
    )

# 사용
result = get_user_profile("user123")
if result.is_just():
    profile = result.unwrap()
    print(f"프로필 로드 완료: {profile['user'].name}")
else:
    print("프로필을 찾을 수 없습니다")
```

### 4. Swift 스타일 컬렉션 연산

**❌ 나쁜 예: 명령형 검색과 변환**
```python
# 커스텀 구현 - 피해야 할 방식
def find_and_process_products(products, category, min_price):
    # 첫 번째 매칭 제품 찾기
    target_product = None
    for product in products:
        if product.category == category and product.price >= min_price:
            target_product = product
            break
    
    if not target_product:
        return []
    
    # 관련 제품들 변환
    related = []
    for product in products:
        if (product.category == category and 
            product.id != target_product.id and 
            product.price > 0):
            discounted = product.price * 0.9
            related.append({
                "id": product.id,
                "name": product.name,
                "original_price": product.price,
                "discounted_price": discounted
            })
    
    return related
```

**✅ 좋은 예: RFS HOF Swift 스타일 사용**
```python
from rfs.hof.collections import (
    first, compact_map, partition, group_by
)

def find_and_process_products(products, category: str, min_price: float):
    """제품을 찾고 관련 제품들을 처리합니다."""
    
    # first를 사용하여 조건에 맞는 첫 번째 제품 찾기 (Swift 스타일)
    target_product = first(
        products, 
        lambda p: p.category == category and p.price >= min_price
    )
    
    if not target_product:
        return []
    
    # compact_map을 사용하여 변환과 필터링을 동시에 (Swift 스타일)
    def transform_related_product(product) -> Optional[dict]:
        """관련 제품을 변환합니다. None이면 필터링됩니다."""
        if (product.category == category and 
            product.id != target_product.id and 
            product.price > 0):
            return {
                "id": product.id,
                "name": product.name,
                "original_price": product.price,
                "discounted_price": product.price * 0.9
            }
        return None  # 조건에 맞지 않으면 None 반환
    
    return compact_map(transform_related_product, products)

# 고급 예제: 제품 분류 및 통계
def analyze_product_categories(products):
    """제품을 분석하고 카테고리별 통계를 생성합니다."""
    
    # partition을 사용하여 재고가 있는 제품과 없는 제품으로 분리
    in_stock, out_of_stock = partition(lambda p: p.stock > 0, products)
    
    # group_by를 사용하여 카테고리별로 그룹화
    categories = group_by(lambda p: p.category, in_stock)
    
    # 각 카테고리별 통계 계산
    stats = {}
    for category, items in categories.items():
        stats[category] = {
            "count": len(items),
            "avg_price": sum(p.price for p in items) / len(items),
            "total_stock": sum(p.stock for p in items),
            "premium_items": len([p for p in items if p.price > 100])
        }
    
    return {
        "in_stock_count": len(in_stock),
        "out_of_stock_count": len(out_of_stock),
        "categories": stats
    }
```

### 5. 비동기 HOF 활용

**❌ 나쁜 예: 수동 비동기 처리**
```python
# 커스텀 구현 - 피해야 할 방식
async def fetch_user_data_batch(user_ids):
    results = []
    for user_id in user_ids:
        try:
            user = await fetch_user(user_id)
            if user:
                try:
                    profile = await fetch_profile(user.profile_id)
                    results.append({"user": user, "profile": profile})
                except Exception:
                    results.append({"user": user, "profile": None})
        except Exception:
            pass
    return results
```

**✅ 좋은 예: RFS HOF 비동기 사용**
```python
from rfs.hof.async_hof import async_map, async_filter, async_retry
from rfs.hof.monads import Result
import asyncio

@async_retry(max_retries=3)
async def fetch_user_with_profile(user_id: str) -> Result[dict, str]:
    """사용자와 프로필을 함께 조회합니다."""
    try:
        # 사용자 조회
        user = await fetch_user(user_id)
        if not user:
            return Failure(f"사용자를 찾을 수 없습니다: {user_id}")
        
        # 프로필 조회
        profile = await fetch_profile(user.profile_id)
        
        return Success({
            "user": user,
            "profile": profile,
            "user_id": user_id
        })
    except Exception as e:
        return Failure(f"조회 실패 ({user_id}): {str(e)}")

async def fetch_user_data_batch(user_ids: list[str]) -> list[dict]:
    """사용자 배치 데이터를 비동기로 조회합니다."""
    
    # async_map을 사용하여 병렬 처리
    results = await async_map(fetch_user_with_profile, user_ids)
    
    # 성공한 결과만 필터링하고 추출
    successful_results = [
        result.unwrap() for result in results 
        if result.is_success()
    ]
    
    return successful_results

# 사용 예제
async def main():
    user_ids = ["user1", "user2", "user3", "user4", "user5"]
    batch_results = await fetch_user_data_batch(user_ids)
    print(f"성공적으로 조회된 사용자: {len(batch_results)}명")
```

## 🎯 실제 프로덕션 활용 예제

### 1. API 응답 처리 파이프라인

```python
from rfs.hof.core import pipe, curry
from rfs.hof.collections import compact_map, group_by, first
from rfs.hof.monads import Result
from rfs.core.result import Success, Failure

@curry
def validate_api_response(schema: dict, response: dict) -> Result[dict, str]:
    """API 응답을 스키마로 검증합니다."""
    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in response:
            return Failure(f"필수 필드 누락: {field}")
    return Success(response)

def normalize_response(response: dict) -> Result[dict, str]:
    """응답을 정규화합니다."""
    normalized = {
        "id": response.get("id"),
        "name": response.get("name", "").strip(),
        "email": response.get("email", "").lower(),
        "created_at": response.get("created_at"),
        "metadata": response.get("metadata", {})
    }
    return Success(normalized)

def enrich_with_cache(response: dict) -> Result[dict, str]:
    """캐시에서 추가 정보로 보강합니다."""
    user_id = response["id"]
    cached_data = get_from_cache(f"user:{user_id}")
    
    enriched = {
        **response,
        "permissions": cached_data.get("permissions", []) if cached_data else [],
        "last_login": cached_data.get("last_login") if cached_data else None
    }
    return Success(enriched)

# 파이프라인 구성
def create_api_processor(schema: dict):
    """API 처리 파이프라인을 생성합니다."""
    return pipe(
        validate_api_response(schema),  # 커링된 함수 사용
        lambda result: result.bind(normalize_response),
        lambda result: result.bind(enrich_with_cache)
    )

# 사용
user_schema = {
    "required": ["id", "name", "email"],
    "optional": ["created_at", "metadata"]
}

process_user_response = create_api_processor(user_schema)

# API 응답 처리
api_response = {
    "id": "123",
    "name": "  김철수  ",
    "email": "KIM@EXAMPLE.COM",
    "created_at": "2024-01-15T10:00:00Z"
}

result = process_user_response(api_response)
if result.is_success():
    processed_user = result.unwrap()
    print(f"처리 완료: {processed_user['name']} ({processed_user['email']})")
```

### 2. 데이터 분석 파이프라인

```python
from rfs.hof.collections import (
    group_by, partition, compact_map, fold_left,
    first, last, drop_while, take_while
)
from rfs.hof.core import compose, curry

@curry
def calculate_metrics(metric_type: str, orders: list) -> dict:
    """주문 리스트에서 지표를 계산합니다."""
    match metric_type:
        case "revenue":
            return {
                "total": sum(o["amount"] for o in orders),
                "average": sum(o["amount"] for o in orders) / len(orders) if orders else 0,
                "count": len(orders)
            }
        case "frequency":
            customer_orders = group_by(lambda o: o["customer_id"], orders)
            return {
                "unique_customers": len(customer_orders),
                "repeat_customers": len([c for c, ords in customer_orders.items() if len(ords) > 1]),
                "avg_orders_per_customer": len(orders) / len(customer_orders) if customer_orders else 0
            }
        case _:
            return {}

def analyze_sales_trends(orders: list) -> dict:
    """매출 트렌드를 분석합니다."""
    
    # 날짜별로 주문 그룹화
    daily_orders = group_by(
        lambda o: o["created_at"][:10],  # YYYY-MM-DD만 추출
        orders
    )
    
    # 고가치 vs 저가치 주문 분리
    high_value, low_value = partition(lambda o: o["amount"] > 1000, orders)
    
    # 최근 30일 주문만 필터링 (take_while 사용)
    sorted_orders = sorted(orders, key=lambda o: o["created_at"], reverse=True)
    recent_orders = take_while(
        lambda o: is_within_days(o["created_at"], 30),
        sorted_orders
    )
    
    # 각 세그먼트별 메트릭 계산 (커링 활용)
    calculate_revenue = calculate_metrics("revenue")
    calculate_frequency = calculate_metrics("frequency")
    
    return {
        "daily_trends": {
            date: calculate_revenue(day_orders)
            for date, day_orders in daily_orders.items()
        },
        "segments": {
            "high_value": {
                "revenue": calculate_revenue(high_value),
                "frequency": calculate_frequency(high_value)
            },
            "low_value": {
                "revenue": calculate_revenue(low_value),
                "frequency": calculate_frequency(low_value)
            }
        },
        "recent_performance": calculate_revenue(recent_orders),
        "peak_day": max(daily_orders.items(), key=lambda x: len(x[1]))[0] if daily_orders else None
    }

def is_within_days(date_str: str, days: int) -> bool:
    """날짜가 지정된 일수 내에 있는지 확인합니다."""
    from datetime import datetime, timedelta
    order_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    cutoff = datetime.now() - timedelta(days=days)
    return order_date >= cutoff
```

### 3. 설정 관리 시스템

```python
from rfs.hof.core import pipe, curry, partial
from rfs.hof.collections import compact_map, merging
from rfs.hof.monads import Maybe, Result
from rfs.core.result import Success, Failure

@curry
def validate_config_field(field_name: str, validator: callable, config: dict) -> Result[dict, str]:
    """설정 필드를 검증합니다."""
    if field_name not in config:
        return Failure(f"필수 설정 누락: {field_name}")
    
    value = config[field_name]
    if not validator(value):
        return Failure(f"잘못된 설정 값: {field_name} = {value}")
    
    return Success(config)

def load_config_from_env() -> dict:
    """환경 변수에서 설정을 로드합니다."""
    import os
    env_config = {}
    
    # RFS_ 접두사가 있는 환경 변수만 수집
    rfs_vars = {k: v for k, v in os.environ.items() if k.startswith("RFS_")}
    
    for key, value in rfs_vars.items():
        config_key = key[4:].lower()  # RFS_ 제거하고 소문자로
        
        # 타입 변환
        if value.lower() in ('true', 'false'):
            env_config[config_key] = value.lower() == 'true'
        elif value.isdigit():
            env_config[config_key] = int(value)
        else:
            env_config[config_key] = value
    
    return env_config

def apply_config_defaults(config: dict) -> dict:
    """기본 설정을 적용합니다."""
    defaults = {
        "debug": False,
        "port": 8080,
        "max_connections": 100,
        "timeout": 30,
        "log_level": "INFO"
    }
    
    # merging을 사용하여 기본값과 병합 (기존값 우선)
    return merging(defaults, config, lambda default, current: current)

def transform_config_values(config: dict) -> Result[dict, str]:
    """설정값을 변환합니다."""
    transformed = {}
    
    for key, value in config.items():
        match key:
            case "port":
                if not (1 <= value <= 65535):
                    return Failure(f"잘못된 포트 번호: {value}")
                transformed[key] = value
            case "log_level":
                if value.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                    return Failure(f"지원하지 않는 로그 레벨: {value}")
                transformed[key] = value.upper()
            case "timeout":
                if value <= 0:
                    return Failure(f"타임아웃은 양수여야 합니다: {value}")
                transformed[key] = value
            case _:
                transformed[key] = value
    
    return Success(transformed)

# 검증 함수들 정의 (커링에서 사용)
is_positive_int = lambda x: isinstance(x, int) and x > 0
is_valid_log_level = lambda x: isinstance(x, str) and x.upper() in ["DEBUG", "INFO", "WARNING", "ERROR"]
is_boolean = lambda x: isinstance(x, bool)

# 설정 로드 파이프라인 구성
load_and_validate_config = pipe(
    load_config_from_env,
    apply_config_defaults,
    transform_config_values,
    lambda result: result.bind(validate_config_field("port", is_positive_int)),
    lambda result: result.bind(validate_config_field("debug", is_boolean)),
    lambda result: result.bind(validate_config_field("log_level", is_valid_log_level))
)

# 사용
config_result = load_and_validate_config()
if config_result.is_success():
    config = config_result.unwrap()
    print(f"설정 로드 완료: 포트 {config['port']}, 디버그 {config['debug']}")
else:
    error = config_result.unwrap_error()
    print(f"설정 로드 실패: {error}")
```

## 📋 HOF 사용 체크리스트

### ✅ 우선 사용해야 하는 HOF들

#### 함수 합성
- [ ] `pipe()` - 왼쪽에서 오른쪽으로 함수 연결
- [ ] `compose()` - 오른쪽에서 왼쪽으로 함수 연결
- [ ] `curry()` - 부분 적용을 위한 커링
- [ ] `partial()` - 인수 부분 적용

#### 컬렉션 연산 (Swift 스타일 우선)
- [ ] `first()` - 조건에 맞는 첫 번째 요소
- [ ] `compact_map()` - 변환 + None 필터링
- [ ] `flat_map()` - 변환 + 평면화
- [ ] `partition()` - 조건으로 분할
- [ ] `group_by()` - 키로 그룹화
- [ ] `fold_left()` / `fold_right()` - 축약 연산

#### 모나드 패턴
- [ ] `Maybe` - 옵셔널 값 처리
- [ ] `Result` - 에러가 있는 연산
- [ ] `Either` - 두 가지 타입 중 하나

#### 비동기 HOF  
- [ ] `async_map()` - 비동기 매핑
- [ ] `async_filter()` - 비동기 필터링
- [ ] `async_retry()` - 재시도 데코레이터

### ❌ 피해야 할 안티패턴

1. **반복적인 루프 대신 HOF 사용**
   ```python
   # ❌ 피할 것
   result = []
   for item in items:
       if condition(item):
           result.append(transform(item))
   
   # ✅ HOF 사용
   result = compact_map(
       lambda item: transform(item) if condition(item) else None, 
       items
   )
   ```

2. **중첩된 예외 처리 대신 모나드 사용**
   ```python
   # ❌ 피할 것
   try:
       result1 = operation1()
       try:
           result2 = operation2(result1)
           return result2
       except Exception:
           return None
   except Exception:
       return None
   
   # ✅ 모나드 사용
   return (
       Maybe.from_try(operation1)
       .bind(lambda r1: Maybe.from_try(lambda: operation2(r1)))
   )
   ```

3. **커스텀 함수 합성 대신 pipe 사용**
   ```python
   # ❌ 피할 것
   def process(data):
       return step3(step2(step1(data)))
   
   # ✅ pipe 사용
   process = pipe(step1, step2, step3)
   ```

## 🚀 성능 최적화 팁

### 1. 지연 평가 활용
```python
from rfs.hof.collections import take, drop_while
from itertools import islice

# 큰 데이터셋에서 조건에 맞는 처음 10개만 처리
def find_first_matches(large_dataset, condition):
    return take(10, filter(condition, large_dataset))
```

### 2. 메모리 효율적인 파이프라인
```python
from rfs.hof.core import pipe
from rfs.hof.collections import chunk

# 대용량 데이터를 청크 단위로 처리
process_large_data = pipe(
    lambda data: chunk(data, 1000),  # 1000개씩 청크
    lambda chunks: map(process_chunk, chunks),
    list
)
```

### 3. 병렬 처리와 HOF 결합
```python
from concurrent.futures import ProcessPoolExecutor
from rfs.hof.collections import partition

def parallel_process_with_hof(data, num_workers=4):
    # 작업을 균등하게 분할
    chunks = chunk(data, len(data) // num_workers)
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # 각 청크를 병렬로 처리
        futures = [executor.submit(process_chunk_with_hof, chunk) for chunk in chunks]
        results = [f.result() for f in futures]
    
    # 결과를 평면화
    return flatten(results)
```

## 🎯 마이그레이션 가이드

### 기존 명령형 코드를 HOF로 변환

1. **루프 → map/filter/reduce**
2. **조건문 → partition/first/compact_map**  
3. **예외 처리 → Maybe/Result 모나드**
4. **함수 호출 체인 → pipe/compose**
5. **중첩 구조 → flat_map/flatten**

### 점진적 도입 전략

1. **1단계**: 새로운 코드에서 HOF 사용
2. **2단계**: 리팩토링 시 HOF로 변환
3. **3단계**: 복잡한 로직을 HOF 파이프라인으로 재구성
4. **4단계**: 팀 전체로 HOF 패턴 확산

---

**결론**: RFS Framework의 내장된 HOF를 적극적으로 활용하여 **읽기 쉽고, 테스트하기 쉽고, 유지보수가 쉬운** 함수형 스타일의 코드를 작성하세요. 커스텀 구현보다는 검증된 HOF 패턴을 우선 사용하여 코드의 일관성과 품질을 향상시킵니다.