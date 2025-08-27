# RFS Framework HOF (Higher-Order Functions) 사용 가이드

## 🎯 개요

**필수**: RFS Framework의 내장된 HOF 라이브러리를 최대한 활용하여 함수형 프로그래밍 스타일로 개발하세요.

RFS Framework는 Swift, Haskell, F# 등에서 영감을 받은 강력한 HOF 라이브러리를 제공합니다. 커스텀 구현 대신 **내장된 HOF를 우선 사용**하여 코드의 일관성과 품질을 향상시킵니다.

### 🔧 새로운 함수형 개발 규칙 (v4.3.3)

**Rule 1: 소단위 개발** - 모든 기능을 작은 함수 단위로 분해하고 HOF를 적극적으로 활용하여 조합 가능하고 재사용 가능한 코드를 작성합니다.

**Rule 2: 파이프라인 통합** - 소단위들 간의 통합은 반드시 파이프라인 패턴(`pipe`, `compose`, 모나드 체이닝)을 사용하여 데이터 흐름을 명확하게 표현합니다.

**Rule 3: 설정/DI HOF** - 설정 관리와 의존성 주입에서도 HOF를 적극 활용하여 선언적이고 조합 가능한 패턴을 구현합니다.

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

### 0. 소단위 개발 패턴 (Rule 1)

**✅ 함수형 소단위 분해 전략**
```python
from rfs.hof.core import pipe, curry, compose
from rfs.hof.collections import compact_map, partition, first
from rfs.core.result import Result, Success, Failure

# ❌ 나쁜 예: 큰 단위 함수
def process_user_registration(user_data, config):
    # 검증, 변환, 저장, 알림까지 모든 것을 하나의 함수에서 처리
    if not user_data.get('email'):
        raise ValueError("이메일이 필요합니다")
    if '@' not in user_data['email']:
        raise ValueError("유효하지 않은 이메일")
    
    # 중복 사용자 확인
    existing = find_user_by_email(user_data['email'])
    if existing:
        raise ValueError("이미 존재하는 사용자")
    
    # 비밀번호 해시
    hashed_password = hash_password(user_data['password'])
    user_data['password'] = hashed_password
    
    # 저장
    user = save_user(user_data)
    
    # 환영 이메일 발송
    send_welcome_email(user['email'])
    
    return user

# ✅ 좋은 예: HOF를 활용한 소단위 분해
@curry
def validate_required_field(field_name: str, data: dict) -> Result[dict, str]:
    """필수 필드를 검증합니다."""
    if not data.get(field_name):
        return Failure(f"{field_name}이(가) 필요합니다")
    return Success(data)

@curry  
def validate_email_format(data: dict) -> Result[dict, str]:
    """이메일 형식을 검증합니다."""
    email = data.get('email', '')
    if '@' not in email or '.' not in email.split('@')[1]:
        return Failure("유효하지 않은 이메일 형식입니다")
    return Success(data)

def check_user_uniqueness(data: dict) -> Result[dict, str]:
    """사용자 중복을 확인합니다."""
    existing = find_user_by_email(data['email'])
    if existing:
        return Failure("이미 존재하는 사용자입니다")
    return Success(data)

def hash_user_password(data: dict) -> Result[dict, str]:
    """사용자 비밀번호를 해시합니다."""
    hashed = hash_password(data['password'])
    return Success({**data, 'password': hashed})

def persist_user(data: dict) -> Result[dict, str]:
    """사용자를 저장합니다."""
    try:
        user = save_user(data)
        return Success(user)
    except Exception as e:
        return Failure(f"저장 실패: {str(e)}")

def notify_user_welcome(user: dict) -> Result[dict, str]:
    """환영 알림을 발송합니다."""
    try:
        send_welcome_email(user['email'])
        return Success(user)
    except Exception as e:
        return Failure(f"알림 발송 실패: {str(e)}")

# 소단위들을 파이프라인으로 조합 (Rule 2)
register_user_pipeline = pipe(
    validate_required_field('email'),
    lambda result: result.bind(validate_required_field('password')),
    lambda result: result.bind(validate_email_format),
    lambda result: result.bind(check_user_uniqueness),
    lambda result: result.bind(hash_user_password),
    lambda result: result.bind(persist_user),
    lambda result: result.bind(notify_user_welcome)
)

# 사용
user_data = {"email": "user@example.com", "password": "securepass"}
result = register_user_pipeline(user_data)

if result.is_success():
    user = result.unwrap()
    print(f"사용자 등록 완료: {user['email']}")
else:
    error = result.unwrap_error()
    print(f"등록 실패: {error}")
```

**🎯 소단위 분해 체크리스트**
- [ ] 각 함수는 단일 책임을 가짐 (한 가지만 수행)
- [ ] 함수는 5-15줄 내외로 간결함
- [ ] 모든 함수는 Result 타입을 반환하여 에러 처리 명시
- [ ] 커링을 활용하여 재사용 가능한 검증/변환 함수 작성
- [ ] 부수 효과(side effect)를 명확히 분리
- [ ] 함수 이름은 동사형으로 명확한 의도 표현

### 1. 파이프라인 통합 패턴 (Rule 2)

**❌ 나쁜 예: 절차적 통합 (Rule 2 위반)**
```python
# 절차적 연결 - 피해야 할 방식 (파이프라인 없음)
def process_user_data(data):
    # 단계별로 직접 호출, 에러 처리 불명확
    cleaned = clean_data(data)
    if not cleaned:
        return None
    
    validated = validate_data(cleaned)
    if not validated:
        return None
        
    transformed = transform_data(validated)
    if not transformed:
        return None
        
    return save_data(transformed)

# 호출하는 곳에서도 에러 처리 어려움
result = process_user_data(user_input)
if not result:
    print("어디서 실패했는지 알 수 없음")
```

**✅ 좋은 예: 파이프라인 통합 (Rule 2 적용)**
```python
from rfs.hof.core import pipe, compose
from rfs.core.result import Result, Success, Failure
from datetime import datetime

# 각 단계는 소단위로 분리 (Rule 1)
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

def save_data(data: dict) -> Result[dict, str]:
    """데이터를 저장합니다."""
    try:
        # 실제 저장 로직
        saved_user = {**data, "id": "generated_id"}
        return Success(saved_user)
    except Exception as e:
        return Failure(f"저장 실패: {str(e)}")

# 파이프라인을 통한 소단위 통합 (Rule 2)
process_user_pipeline = pipe(
    clean_data,
    lambda result: result.bind(validate_data),
    lambda result: result.bind(transform_data),
    lambda result: result.bind(save_data)
)

# 고급 파이프라인: 조건부 분기도 함수형으로
def create_conditional_pipeline(is_premium: bool):
    """조건에 따라 다른 파이프라인을 반환합니다."""
    base_steps = [
        clean_data,
        lambda result: result.bind(validate_data),
        lambda result: result.bind(transform_data)
    ]
    
    if is_premium:
        premium_steps = [
            lambda result: result.bind(add_premium_features),
            lambda result: result.bind(send_premium_notification)
        ]
        return pipe(*base_steps, *premium_steps, lambda result: result.bind(save_data))
    else:
        return pipe(*base_steps, lambda result: result.bind(save_data))

# 사용 - 명확한 에러 추적과 처리
result = process_user_pipeline(user_input)
if result.is_success():
    user = result.unwrap()
    print(f"사용자 처리 완료: {user['name']} (ID: {user['id']})")
else:
    error = result.unwrap_error()
    print(f"처리 실패: {error}")
    # 에러 메시지로 어느 단계에서 실패했는지 명확히 알 수 있음
```

**🔄 파이프라인 통합 패턴 종류**

1. **순차 파이프라인**: `pipe(f1, f2, f3)` - 데이터가 순서대로 흐름
2. **모나드 체이닝**: `result.bind(f1).bind(f2).bind(f3)` - Result 타입 유지
3. **분기 파이프라인**: 조건에 따라 다른 경로
4. **병합 파이프라인**: 여러 소스를 하나로 합성
5. **비동기 파이프라인**: `async_pipe()` 비동기 작업 연결

**📊 파이프라인 통합 체크리스트**
- [ ] 모든 단계 간 연결은 `pipe()` 또는 모나드 체이닝 사용
- [ ] 중간 결과를 임시 변수에 저장하지 않음
- [ ] 에러 처리가 파이프라인을 통해 자동으로 전파
- [ ] 각 파이프라인은 단일 책임을 가짐 (한 가지 워크플로우)
- [ ] 조건부 로직도 함수형 패턴으로 표현
- [ ] 파이프라인 자체가 재사용 가능한 단위

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

### 3. 설정/DI HOF 패턴 (Rule 3)

**✅ 설정 관리에서 HOF 활용**

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

## 🏗️ 고급 패턴: 소단위 + 파이프라인 + 설정/DI

### 통합 예제: 전자상거래 주문 처리 시스템

```python
from rfs.hof.core import pipe, curry, compose
from rfs.hof.collections import compact_map, partition, first, group_by
from rfs.hof.monads import Maybe, Result
from rfs.core.result import Success, Failure
from rfs.core.config import get_config

# Rule 3: 설정/DI에서도 HOF 활용
@curry
def with_config(config_key: str, func: callable, *args):
    """설정값과 함께 함수를 실행합니다."""
    config_value = get_config(config_key)
    return func(config_value, *args)

@curry
def validate_with_rules(rule_set: str, data: dict) -> Result[dict, str]:
    """설정된 규칙으로 데이터를 검증합니다."""
    rules = get_config(f"validation.{rule_set}")
    
    for rule_name, rule_func in rules.items():
        if not rule_func(data):
            return Failure(f"검증 실패: {rule_name}")
    
    return Success(data)

# Rule 1: 소단위 함수들
def calculate_item_total(item: dict) -> Result[dict, str]:
    """상품 총액을 계산합니다."""
    try:
        total = item['price'] * item['quantity']
        return Success({**item, 'total': total})
    except KeyError as e:
        return Failure(f"필수 필드 누락: {e}")

def apply_item_discount(discount_rate: float, item: dict) -> Result[dict, str]:
    """상품에 할인을 적용합니다."""
    if 0 <= discount_rate <= 1:
        discounted_total = item['total'] * (1 - discount_rate)
        return Success({**item, 'discounted_total': discounted_total})
    return Failure("잘못된 할인율입니다")

def validate_inventory(item: dict) -> Result[dict, str]:
    """재고를 확인합니다."""
    available_stock = get_inventory_count(item['product_id'])
    if available_stock >= item['quantity']:
        return Success(item)
    return Failure(f"재고 부족: {item['product_id']}")

def calculate_shipping(items: list, address: dict) -> Result[float, str]:
    """배송비를 계산합니다."""
    total_weight = sum(item.get('weight', 0) for item in items)
    shipping_rates = get_config('shipping.rates')
    
    base_rate = shipping_rates.get(address['zone'], shipping_rates['default'])
    shipping_cost = base_rate + (total_weight * 0.5)
    
    return Success(shipping_cost)

def apply_tax_rate(tax_rate: float, total: float) -> float:
    """세금을 적용합니다."""
    return total * (1 + tax_rate)

# Rule 2: 파이프라인으로 소단위들 통합
# 상품 처리 파이프라인
process_order_item = pipe(
    calculate_item_total,
    lambda result: result.bind(with_config('discount.member_rate', apply_item_discount)),
    lambda result: result.bind(validate_inventory)
)

# 주문 전체 처리 파이프라인
def create_order_pipeline(customer_type: str):
    """고객 타입에 따른 주문 처리 파이프라인을 생성합니다."""
    
    def process_order_items(order: dict) -> Result[dict, str]:
        """모든 상품을 처리합니다."""
        items = order.get('items', [])
        
        # compact_map으로 각 상품 처리, 실패한 것은 자동으로 제외
        def process_item_safe(item):
            result = process_order_item(item)
            return result.unwrap() if result.is_success() else None
        
        processed_items = compact_map(process_item_safe, items)
        
        if not processed_items:
            return Failure("처리 가능한 상품이 없습니다")
        
        return Success({**order, 'items': processed_items})
    
    def calculate_order_totals(order: dict) -> Result[dict, str]:
        """주문 총액을 계산합니다."""
        items_total = sum(item.get('discounted_total', item['total']) for item in order['items'])
        
        # 배송비 계산
        shipping_result = calculate_shipping(order['items'], order['shipping_address'])
        if not shipping_result.is_success():
            return Failure(shipping_result.unwrap_error())
        
        shipping_cost = shipping_result.unwrap()
        
        # 세금 계산 (고객 타입별 차등 적용)
        tax_rate = get_config(f'tax.{customer_type}', 0.1)  # 기본 10%
        final_total = apply_tax_rate(tax_rate, items_total + shipping_cost)
        
        return Success({
            **order,
            'subtotal': items_total,
            'shipping_cost': shipping_cost,
            'tax_rate': tax_rate,
            'final_total': final_total
        })
    
    def validate_payment_method(order: dict) -> Result[dict, str]:
        """결제 방법을 검증합니다."""
        return validate_with_rules(f'payment.{customer_type}', order)
    
    def reserve_inventory(order: dict) -> Result[dict, str]:
        """재고를 예약합니다."""
        try:
            for item in order['items']:
                reserve_stock(item['product_id'], item['quantity'])
            return Success({**order, 'inventory_reserved': True})
        except Exception as e:
            return Failure(f"재고 예약 실패: {str(e)}")
    
    # 고객 타입별 맞춤형 파이프라인
    return pipe(
        process_order_items,
        lambda result: result.bind(calculate_order_totals),
        lambda result: result.bind(validate_payment_method),
        lambda result: result.bind(reserve_inventory)
    )

# 사용 예제
order_data = {
    'customer_id': 'CUST123',
    'items': [
        {'product_id': 'P001', 'price': 100, 'quantity': 2, 'weight': 1.5},
        {'product_id': 'P002', 'price': 50, 'quantity': 1, 'weight': 0.8}
    ],
    'shipping_address': {'zone': 'domestic'},
    'payment_method': 'credit_card'
}

# VIP 고객용 파이프라인
vip_order_pipeline = create_order_pipeline('vip')
result = vip_order_pipeline(order_data)

if result.is_success():
    processed_order = result.unwrap()
    print(f"주문 처리 완료: 총액 {processed_order['final_total']}원")
else:
    print(f"주문 처리 실패: {result.unwrap_error()}")

# 일반 고객용 파이프라인은 다른 규칙 적용
regular_order_pipeline = create_order_pipeline('regular')
```

**🎯 통합 패턴의 장점**

1. **조합 가능성**: 각 소단위가 독립적이라 다양한 조합 가능
2. **테스트 용이성**: 각 함수를 개별적으로 테스트 가능
3. **재사용성**: 파이프라인을 다른 컨텍스트에서도 재사용
4. **에러 추적**: 파이프라인을 통해 정확한 실패 지점 파악
5. **설정 주도**: 코드 변경 없이 설정으로 동작 제어

## 📋 HOF 사용 체크리스트

### ✅ 새로운 함수형 개발 규칙 체크리스트

#### Rule 1: 소단위 개발 체크리스트
- [ ] 각 함수는 5-15줄 내외로 작성
- [ ] 함수당 하나의 명확한 책임만 수행
- [ ] 모든 함수가 Result 타입 반환으로 에러 처리 명시
- [ ] 부수 효과(side effect) 최소화 및 명시적 분리
- [ ] 순수 함수 우선, 필요시에만 불순 함수 사용
- [ ] 커링과 부분 적용으로 재사용성 향상
- [ ] 함수 이름으로 의도와 동작 명확히 표현

#### Rule 2: 파이프라인 통합 체크리스트
- [ ] 소단위 간 연결은 `pipe()` 또는 모나드 체이닝만 사용
- [ ] 중간 결과를 임시 변수에 저장하지 않음
- [ ] 조건부 로직도 함수형 패턴으로 표현
- [ ] 에러가 파이프라인을 통해 자동으로 전파됨
- [ ] 각 파이프라인이 하나의 완전한 워크플로우 표현
- [ ] 파이프라인 자체가 재사용 가능한 단위로 설계
- [ ] 비동기 작업도 `async_pipe` 패턴 사용

#### Rule 3: 설정/DI HOF 체크리스트
- [ ] 설정 로드와 검증에 HOF 파이프라인 사용
- [ ] 의존성 주입에서 커링과 부분 적용 활용
- [ ] 설정 기반 조건부 로직을 HOF로 추상화
- [ ] 환경별 설정을 함수형 패턴으로 관리
- [ ] 설정 변경이 코드 수정 없이 동작 변경 가능
- [ ] 설정 검증과 변환도 파이프라인으로 처리
- [ ] DI 컨테이너보다 HOF 기반 주입 우선 사용

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

## 🎯 새로운 함수형 개발 규칙 적용 가이드

### 기존 코드를 함수형 규칙으로 변환

**1단계: 소단위로 분해 (Rule 1)**
- 큰 함수를 단일 책임 원칙에 따라 분해
- 각 단위가 독립적으로 테스트 가능하도록 분리
- Result 타입으로 에러 처리 명시화

**2단계: 파이프라인으로 통합 (Rule 2)**  
- 분해된 소단위들을 `pipe()` 또는 모나드 체이닝으로 연결
- 중간 상태 변수 제거, 데이터 흐름 명시화
- 조건부 로직을 함수형 분기 패턴으로 변환

**3단계: 설정/DI HOF 적용 (Rule 3)**
- 하드코딩된 값들을 설정 기반으로 전환
- 의존성 주입을 커링과 부분 적용으로 대체
- 환경별 동작을 HOF 기반 추상화로 관리

### 점진적 도입 전략 (v4.3.3)

**Phase 1: 새로운 기능 개발**
- [ ] 모든 신규 기능을 3가지 규칙 적용하여 개발
- [ ] 기존 패턴과 비교하여 효과 측정
- [ ] 팀원들에게 새로운 패턴 교육

**Phase 2: 핫픽스 및 리팩토링**
- [ ] 버그 수정 시 해당 함수를 소단위로 분해
- [ ] 기존 로직을 파이프라인 패턴으로 변환
- [ ] 설정 하드코딩 발견 시 HOF 패턴 적용

**Phase 3: 레거시 모듈 전환**
- [ ] 복잡한 레거시 모듈을 규칙에 따라 재구성
- [ ] 기존 인터페이스 유지하면서 내부 구조만 변경
- [ ] A/B 테스트로 성능 및 유지보수성 검증

**Phase 4: 프로젝트 전체 표준화**
- [ ] 모든 새로운 코드가 3가지 규칙을 준수
- [ ] 코드 리뷰에서 규칙 준수 여부 검토
- [ ] 자동화 도구로 패턴 준수 검사

### 팀 도입 체크리스트

**개발자 교육**
- [ ] 함수형 프로그래밍 기본 개념 교육
- [ ] RFS HOF 라이브러리 사용법 교육  
- [ ] 새로운 3가지 규칙 워크샵 실시
- [ ] 실전 예제를 통한 hands-on 연습

**코드 품질 관리**
- [ ] 코드 리뷰 가이드라인에 규칙 반영
- [ ] 린터/타입체커에 HOF 사용 검사 추가
- [ ] CI/CD 파이프라인에 함수형 패턴 검증 단계 추가
- [ ] 메트릭 수집: 함수 길이, 파이프라인 사용율, 에러 처리 명시율

**성과 측정**
- [ ] 버그 발생률 변화 추적
- [ ] 코드 리뷰 시간 단축 측정
- [ ] 테스트 커버리지 향상도 확인
- [ ] 개발 속도 및 유지보수성 개선도 평가

---

**결론**: RFS Framework v4.3.3의 새로운 함수형 개발 규칙을 통해 **소단위 개발**, **파이프라인 통합**, **설정/DI HOF**를 체계적으로 적용하세요. 이를 통해 **조합 가능하고, 테스트하기 쉽고, 유지보수가 쉬운** 진정한 함수형 스타일의 코드를 작성할 수 있습니다.

### 📈 기대 효과

**코드 품질 향상**
- 🎯 함수의 평균 길이 50% 단축 (소단위 개발)
- 🔄 복잡도 30% 감소 (파이프라인 통합)
- ⚙️ 설정 변경에 따른 코드 수정 80% 감소 (설정/DI HOF)

**개발 생산성 증대**
- ✅ 단위 테스트 작성 시간 40% 단축
- 🐛 버그 추적 및 수정 시간 60% 단축  
- 🔧 새로운 기능 개발 시 기존 코드 재사용률 70% 증가

**유지보수성 개선**
- 📖 코드 가독성 및 이해도 향상
- 🔄 변경 영향도 최소화
- 📋 문서화 자동화 (함수형 패턴 자체가 문서)

**새로운 함수형 개발 규칙을 지금부터 적용하여 차세대 RFS 애플리케이션을 구축하세요!**