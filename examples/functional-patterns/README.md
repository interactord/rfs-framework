# RFS Framework 함수형 개발 패턴 실무 예제

RFS Framework v4.3.3의 새로운 함수형 개발 규칙을 적용한 실전 예제 모음입니다.

## 📋 새로운 함수형 개발 규칙 (3가지)

### Rule 1: 소단위 개발
- 모든 기능을 작은 함수 단위(5-15줄)로 분해
- 각 함수는 단일 책임 원칙을 준수
- HOF를 적극적으로 활용하여 조합 가능하고 재사용 가능한 코드 작성

### Rule 2: 파이프라인 통합  
- 소단위들 간의 통합은 반드시 파이프라인 패턴 사용
- `pipe()`, `compose()`, 모나드 체이닝으로 데이터 흐름을 명확하게 표현
- 중간 결과를 임시 변수에 저장하지 않고 파이프라인으로 연결

### Rule 3: 설정/DI HOF
- 설정 관리와 의존성 주입에서도 HOF를 적극 활용
- 선언적이고 조합 가능한 패턴으로 구현
- 환경별 설정을 함수형 패턴으로 관리

## 🎯 실무 예제 목록

### 1. 전자상거래 주문 처리 시스템 (`ecommerce_example.py`)

**적용된 함수형 패턴:**
- **소단위 개발**: 주문 검증, 재고 확인, 결제 처리를 각각 5-15줄의 순수 함수로 분해
- **파이프라인 통합**: 주문 접수부터 완료까지 전 과정을 하나의 파이프라인으로 연결
- **설정/DI HOF**: 고객 등급별 할인율, 배송비 계산 정책을 설정 기반으로 주입

**핵심 함수들:**
```python
# Rule 1: 소단위 함수
validate_order_items(order_data) -> Result[dict, str]
calculate_item_total(item) -> Result[dict, str]
apply_discount_rate(rate, item) -> Result[dict, str]

# Rule 2: 파이프라인 통합
order_processing_pipeline = pipe(
    validate_order,
    lambda r: r.bind(process_items),
    lambda r: r.bind(calculate_totals),
    lambda r: r.bind(process_payment),
    lambda r: r.bind(save_order)
)

# Rule 3: 설정/DI HOF
@curry
def with_customer_config(config_key, func, *args)
create_customer_specific_pipeline(customer_id)
```

### 2. 사용자 관리 시스템 (`user_management_example.py`)

**적용된 함수형 패턴:**
- **소단위 개발**: 이메일 검증, 비밀번호 해시, 권한 검사를 작은 함수로 분해
- **파이프라인 통합**: 회원가입부터 로그인까지 각각을 독립적인 파이프라인으로 구성
- **설정/DI HOF**: 역할별 권한, 보안 정책을 설정 파일 기반으로 동적 주입

**핵심 함수들:**
```python
# Rule 1: 소단위 함수들
validate_email_format(email) -> Result[str, str]
hash_password(password) -> Result[str, str]
check_role_permission(role, user) -> Result[User, str]

# Rule 2: 파이프라인들
registration_pipeline = pipe(
    validate_registration_data,
    lambda r: r.bind(hash_password_field),
    lambda r: r.bind(create_user_object),
    lambda r: r.bind(save_user_to_database),
    lambda r: r.bind(send_activation_email)
)

# Rule 3: 설정/DI HOF
@curry
def with_permission_policy(policy_name, check)
create_permission_checker(resource, action)
```

## 🚀 실행 방법

### 1. 개별 예제 실행
```bash
# 전자상거래 예제 실행
python examples/functional-patterns/ecommerce_example.py

# 사용자 관리 예제 실행  
python examples/functional-patterns/user_management_example.py
```

### 2. 대화형 테스트
```python
from examples.functional_patterns import ecommerce_example, user_management_example

# 전자상거래 시스템 테스트
ecommerce_example.example_usage()

# 사용자 관리 시스템 테스트
user_management_example.example_usage()
```

## 📊 함수형 패턴의 장점

### 1. 테스트 용이성
- 각 소단위 함수는 독립적으로 테스트 가능
- 순수 함수는 동일한 입력에 대해 항상 동일한 출력 보장
- Mock 없이도 단위 테스트 작성 가능

```python
def test_validate_email_format():
    # Given
    valid_email = "test@example.com"
    invalid_email = "invalid-email"
    
    # When & Then
    assert validate_email_format(valid_email).is_success()
    assert validate_email_format(invalid_email).is_failure()
```

### 2. 조합 가능성
- 작은 함수들을 레고 블록처럼 조합
- 새로운 요구사항에 기존 함수들을 재조합하여 대응
- 코드 중복 최소화

```python
# 기존 함수들을 조합하여 새로운 파이프라인 생성
vip_order_pipeline = pipe(
    apply_vip_validation,  # 새로운 함수
    *base_order_steps,     # 기존 단계들 재사용
    send_vip_notification  # 새로운 함수
)
```

### 3. 에러 처리의 명확성
- Result 타입으로 성공/실패가 명시적
- 파이프라인에서 에러 자동 전파
- 각 단계에서 발생한 에러의 정확한 추적 가능

```python
result = order_pipeline(order_data)
if result.is_failure():
    error_message = result.unwrap_error()
    # 어느 단계에서 실패했는지 명확히 알 수 있음
```

### 4. 설정 기반 유연성
- 하드코딩된 값 없이 모든 정책을 설정으로 관리
- 환경별로 다른 동작을 코드 변경 없이 구현
- A/B 테스트나 기능 토글 쉽게 적용 가능

```python
# 설정만 변경하면 동작이 바뀜
# config/production.yaml
discounts:
  regular_discount: 0.05
  vip_discount: 0.15

# config/test.yaml  
discounts:
  regular_discount: 0.20
  vip_discount: 0.30
```

## 🛠️ 확장 가능한 아키텍처

이 예제들은 다음과 같은 방식으로 확장할 수 있습니다:

### 1. 새로운 비즈니스 규칙 추가
```python
# 새로운 검증 함수만 추가
def validate_bulk_order(order) -> Result[dict, str]:
    if len(order['items']) > 100:
        return Failure("대량 주문은 별도 승인이 필요합니다")
    return Success(order)

# 기존 파이프라인에 삽입
enhanced_pipeline = pipe(
    validate_order,
    lambda r: r.bind(validate_bulk_order),  # 새로운 단계 추가
    lambda r: r.bind(process_items),
    # ... 기존 단계들
)
```

### 2. 새로운 결제 방식 지원
```python
@curry
def process_cryptocurrency_payment(crypto_config, order_total):
    # 암호화폐 결제 로직
    pass

# 설정 기반으로 결제 방식 선택
payment_processor = with_payment_config(
    f"payment.{payment_method}", 
    process_payment
)
```

### 3. 멀티테넌트 지원
```python
@curry
def with_tenant_context(tenant_id, func, *args):
    tenant_config = get_config(f"tenants.{tenant_id}")
    return func(tenant_config, *args)

# 테넌트별로 다른 정책 적용
tenant_pipeline = with_tenant_context(
    "tenant_123", 
    create_order_pipeline
)
```

## 📚 관련 문서

- [함수형 개발 규칙 가이드](../../docs/17-functional-development-rules.md)
- [HOF 사용 가이드](../../docs/16-hof-usage-guide.md)
- [CLAUDE.md 개발 가이드](../../CLAUDE.md)

## 🔄 마이그레이션 가이드

기존 명령형 코드를 함수형 패턴으로 마이그레이션하는 단계:

### Phase 1: 소단위로 분해 (Rule 1)
1. 큰 함수를 단일 책임 원칙에 따라 분해
2. 각 함수가 5-15줄 내외가 되도록 조정
3. 모든 함수가 Result 타입을 반환하도록 변경

### Phase 2: 파이프라인으로 연결 (Rule 2)  
1. 분해된 함수들을 pipe()로 연결
2. 중간 변수들을 제거하고 모나드 체이닝 적용
3. 조건부 로직을 함수형 분기 패턴으로 변경

### Phase 3: 설정 기반으로 개선 (Rule 3)
1. 하드코딩된 값들을 설정으로 추출
2. 커링을 활용한 설정 주입 패턴 적용
3. 환경별 설정 파일로 동작 제어

이러한 단계적 접근을 통해 기존 코드를 점진적으로 함수형으로 전환할 수 있습니다.

---

**새로운 함수형 개발 규칙을 지금부터 적용하여 차세대 RFS 애플리케이션을 구축하세요!** 🚀