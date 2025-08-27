"""
전자상거래 주문 처리 시스템
새로운 함수형 개발 규칙 적용 실무 예제

Rule 1: 소단위 개발 - 각 기능을 5-15줄의 순수 함수로 분해
Rule 2: 파이프라인 통합 - pipe()와 모나드 체이닝으로 연결  
Rule 3: 설정/DI HOF - 커링과 설정 기반 함수 주입
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass

from rfs.hof.core import pipe, curry, compose
from rfs.hof.collections import compact_map, partition, first, group_by
from rfs.hof.monads import Maybe, Result
from rfs.core.result import Success, Failure
from rfs.core.config import get_config


# =============================================================================
# Rule 1: 소단위 개발 - 각 함수는 단일 책임과 5-15줄 제한
# =============================================================================

@dataclass
class OrderItem:
    product_id: str
    name: str
    price: Decimal
    quantity: int
    weight: float = 0.0


@dataclass
class ShippingAddress:
    recipient: str
    address: str
    city: str
    postal_code: str
    zone: str = "domestic"


@dataclass  
class Order:
    order_id: str
    customer_id: str
    items: List[OrderItem]
    shipping_address: ShippingAddress
    payment_method: str


@curry
def validate_required_field(field_name: str, data: dict) -> Result[dict, str]:
    """필수 필드를 검증합니다."""
    if not data.get(field_name):
        return Failure(f"필수 필드 누락: {field_name}")
    return Success(data)


def validate_order_items(order_data: dict) -> Result[dict, str]:
    """주문 아이템을 검증합니다."""
    items = order_data.get('items', [])
    if not items:
        return Failure("주문 아이템이 없습니다")
    
    for item in items:
        if item.get('quantity', 0) <= 0:
            return Failure(f"잘못된 수량: {item.get('name', 'Unknown')}")
    
    return Success(order_data)


def check_inventory_availability(item: OrderItem) -> Result[OrderItem, str]:
    """재고를 확인합니다."""
    # 실제로는 데이터베이스에서 조회
    available_stock = _get_inventory_count(item.product_id)
    
    if available_stock < item.quantity:
        return Failure(f"재고 부족: {item.name} (요청: {item.quantity}, 재고: {available_stock})")
    
    return Success(item)


def calculate_item_total(item: OrderItem) -> Result[OrderItem, str]:
    """아이템 총액을 계산합니다."""
    try:
        total = item.price * item.quantity
        # OrderItem을 확장하여 total 추가 (실제로는 별도 클래스 사용)
        item_dict = {
            'product_id': item.product_id,
            'name': item.name,
            'price': item.price,
            'quantity': item.quantity,
            'weight': item.weight,
            'total': total
        }
        return Success(item_dict)
    except Exception as e:
        return Failure(f"총액 계산 실패: {str(e)}")


@curry
def apply_discount_rate(discount_rate: float, item: dict) -> Result[dict, str]:
    """할인율을 적용합니다."""
    if not (0 <= discount_rate <= 1):
        return Failure("잘못된 할인율입니다")
    
    original_total = item.get('total', 0)
    discounted_total = original_total * (1 - discount_rate)
    
    return Success({
        **item,
        'original_total': original_total,
        'discount_rate': discount_rate,
        'discounted_total': discounted_total
    })


def calculate_shipping_cost(items: List[dict], address: ShippingAddress) -> Result[Decimal, str]:
    """배송비를 계산합니다."""
    try:
        total_weight = sum(item.get('weight', 0) for item in items)
        shipping_rates = get_config('shipping.rates', {})
        
        base_rate = Decimal(str(shipping_rates.get(address.zone, 5.0)))
        weight_rate = Decimal(str(total_weight)) * Decimal('0.5')
        
        shipping_cost = base_rate + weight_rate
        return Success(shipping_cost)
    except Exception as e:
        return Failure(f"배송비 계산 실패: {str(e)}")


@curry
def calculate_tax_amount(tax_rate: float, subtotal: Decimal) -> Decimal:
    """세금을 계산합니다."""
    return subtotal * Decimal(str(tax_rate))


def process_payment(order_total: Decimal, payment_method: str) -> Result[dict, str]:
    """결제를 처리합니다."""
    try:
        # 실제로는 외부 결제 API 호출
        payment_result = _process_external_payment(order_total, payment_method)
        
        if payment_result['status'] == 'success':
            return Success({
                'transaction_id': payment_result['transaction_id'],
                'amount': order_total,
                'method': payment_method,
                'processed_at': datetime.now().isoformat()
            })
        else:
            return Failure(f"결제 실패: {payment_result.get('error', 'Unknown error')}")
    
    except Exception as e:
        return Failure(f"결제 처리 중 오류: {str(e)}")


def reserve_inventory(items: List[dict]) -> Result[List[dict], str]:
    """재고를 예약합니다."""
    try:
        for item in items:
            _reserve_stock(item['product_id'], item['quantity'])
        
        return Success([{
            **item, 
            'inventory_reserved': True,
            'reserved_at': datetime.now().isoformat()
        } for item in items])
    except Exception as e:
        return Failure(f"재고 예약 실패: {str(e)}")


def save_order_to_database(order: dict) -> Result[dict, str]:
    """주문을 데이터베이스에 저장합니다."""
    try:
        # 실제로는 데이터베이스 저장
        saved_order = {
            **order,
            'id': _generate_order_id(),
            'status': 'confirmed',
            'created_at': datetime.now().isoformat()
        }
        
        _save_to_database(saved_order)
        return Success(saved_order)
    except Exception as e:
        return Failure(f"주문 저장 실패: {str(e)}")


def send_order_confirmation(order: dict) -> Result[dict, str]:
    """주문 확인 알림을 발송합니다."""
    try:
        customer_email = _get_customer_email(order['customer_id'])
        _send_email(
            to=customer_email,
            subject=f"주문 확인 - {order['id']}",
            body=f"주문이 성공적으로 접수되었습니다. 총액: {order['final_total']}"
        )
        
        return Success({**order, 'notification_sent': True})
    except Exception as e:
        return Failure(f"알림 발송 실패: {str(e)}")


# =============================================================================
# Rule 2: 파이프라인 통합 - 소단위들을 pipe()로 연결
# =============================================================================

def create_item_processing_pipeline(discount_config: str):
    """아이템 처리 파이프라인을 생성합니다."""
    discount_rate = get_config(f'discounts.{discount_config}', 0.0)
    apply_discount = apply_discount_rate(discount_rate)
    
    def process_single_item(item: OrderItem) -> Result[dict, str]:
        """개별 아이템을 처리합니다."""
        return (
            check_inventory_availability(item)
            .bind(calculate_item_total)
            .bind(apply_discount)
        )
    
    return process_single_item


def create_order_validation_pipeline():
    """주문 검증 파이프라인을 생성합니다."""
    required_fields = ['customer_id', 'items', 'shipping_address', 'payment_method']
    
    # 각 필드를 순차적으로 검증하는 파이프라인
    validation_steps = [validate_required_field(field) for field in required_fields]
    validation_steps.append(lambda result: result.bind(validate_order_items))
    
    def validate_order(order_data: dict) -> Result[dict, str]:
        """주문 전체를 검증합니다."""
        result = Success(order_data)
        for step in validation_steps:
            result = result.bind(step)
            if result.is_failure():
                break
        return result
    
    return validate_order


def create_order_processing_pipeline(customer_type: str = "regular"):
    """고객 유형별 주문 처리 파이프라인을 생성합니다."""
    
    # Rule 3: 설정/DI HOF - 설정 기반으로 파이프라인 구성
    item_processor = create_item_processing_pipeline(f'{customer_type}_discount')
    order_validator = create_order_validation_pipeline()
    
    def process_order_items(order_data: dict) -> Result[dict, str]:
        """모든 주문 아이템을 처리합니다."""
        raw_items = [
            OrderItem(**item_data) 
            for item_data in order_data.get('items', [])
        ]
        
        # compact_map으로 실패한 아이템은 자동 제외
        def process_item_safe(item):
            result = item_processor(item)
            return result.unwrap() if result.is_success() else None
        
        processed_items = compact_map(process_item_safe, raw_items)
        
        if not processed_items:
            return Failure("처리 가능한 상품이 없습니다")
        
        return Success({**order_data, 'processed_items': processed_items})
    
    def calculate_order_totals(order_data: dict) -> Result[dict, str]:
        """주문 총액을 계산합니다."""
        items = order_data['processed_items']
        
        # 아이템별 총액 합산
        subtotal = sum(
            item.get('discounted_total', item.get('total', 0)) 
            for item in items
        )
        
        # 배송비 계산
        shipping_address = ShippingAddress(**order_data['shipping_address'])
        shipping_result = calculate_shipping_cost(items, shipping_address)
        
        if shipping_result.is_failure():
            return shipping_result
        
        shipping_cost = shipping_result.unwrap()
        
        # 세금 계산 (고객 유형별 세율 적용)
        tax_rate = get_config(f'tax_rates.{customer_type}', 0.1)
        tax_calculator = calculate_tax_amount(tax_rate)
        tax_amount = tax_calculator(Decimal(str(subtotal)))
        
        final_total = Decimal(str(subtotal)) + shipping_cost + tax_amount
        
        return Success({
            **order_data,
            'subtotal': subtotal,
            'shipping_cost': float(shipping_cost),
            'tax_rate': tax_rate,
            'tax_amount': float(tax_amount),
            'final_total': float(final_total)
        })
    
    def process_payment_and_inventory(order_data: dict) -> Result[dict, str]:
        """결제 처리 및 재고 예약을 수행합니다."""
        final_total = Decimal(str(order_data['final_total']))
        payment_method = order_data['payment_method']
        
        # 결제 처리
        payment_result = process_payment(final_total, payment_method)
        if payment_result.is_failure():
            return payment_result
        
        # 재고 예약
        inventory_result = reserve_inventory(order_data['processed_items'])
        if inventory_result.is_failure():
            # 결제 롤백 로직 (실제 구현에서는 더 복잡)
            return inventory_result
        
        return Success({
            **order_data,
            'payment_info': payment_result.unwrap(),
            'inventory_reserved': True
        })
    
    # Rule 2: 모든 단계를 하나의 파이프라인으로 통합
    return pipe(
        order_validator,
        lambda result: result.bind(process_order_items),
        lambda result: result.bind(calculate_order_totals),
        lambda result: result.bind(process_payment_and_inventory),
        lambda result: result.bind(save_order_to_database),
        lambda result: result.bind(send_order_confirmation)
    )


# =============================================================================
# Rule 3: 설정/DI HOF - 설정 기반 함수 생성 및 주입
# =============================================================================

@curry
def with_customer_config(config_key: str, func: callable, *args):
    """고객 설정과 함께 함수를 실행합니다."""
    config = get_config(f'customers.{config_key}', {})
    return func(config, *args)


@curry
def with_business_rules(rule_set: str, order_data: dict) -> Result[dict, str]:
    """비즈니스 규칙을 적용합니다."""
    rules = get_config(f'business_rules.{rule_set}', {})
    
    for rule_name, rule_config in rules.items():
        if not _check_business_rule(rule_name, rule_config, order_data):
            return Failure(f"비즈니스 규칙 위반: {rule_name}")
    
    return Success(order_data)


def create_customer_specific_pipeline(customer_id: str):
    """고객별 맞춤 주문 처리 파이프라인을 생성합니다."""
    # 고객 정보 조회
    customer_info = _get_customer_info(customer_id)
    customer_type = customer_info.get('type', 'regular')
    
    # 고객 유형별 파이프라인 생성
    base_pipeline = create_order_processing_pipeline(customer_type)
    
    # 고객별 비즈니스 규칙 적용
    business_rule_validator = with_business_rules(customer_type)
    
    def enhanced_pipeline(order_data: dict) -> Result[dict, str]:
        """고객별 향상된 파이프라인입니다."""
        # 비즈니스 규칙 먼저 검증
        rule_result = business_rule_validator(order_data)
        if rule_result.is_failure():
            return rule_result
        
        # 기본 파이프라인 실행
        return base_pipeline(order_data)
    
    return enhanced_pipeline


# =============================================================================
# 사용 예제 및 테스트
# =============================================================================

def example_usage():
    """함수형 전자상거래 시스템 사용 예제"""
    
    # 샘플 주문 데이터
    sample_order = {
        'customer_id': 'CUST123',
        'items': [
            {
                'product_id': 'PROD001',
                'name': '무선 이어폰',
                'price': 150000,
                'quantity': 1,
                'weight': 0.2
            },
            {
                'product_id': 'PROD002', 
                'name': '스마트폰 케이스',
                'price': 25000,
                'quantity': 2,
                'weight': 0.1
            }
        ],
        'shipping_address': {
            'recipient': '김고객',
            'address': '서울시 강남구 테헤란로 123',
            'city': '서울',
            'postal_code': '06141',
            'zone': 'domestic'
        },
        'payment_method': 'credit_card'
    }
    
    print("=== RFS Framework 함수형 전자상거래 시스템 ===")
    print("새로운 함수형 개발 규칙 적용 예제\n")
    
    # 고객별 맞춤 파이프라인 생성 (Rule 3)
    customer_pipeline = create_customer_specific_pipeline('CUST123')
    
    # 주문 처리 실행 (Rule 2 - 파이프라인 통합)
    print("주문 처리 중...")
    result = customer_pipeline(sample_order)
    
    if result.is_success():
        processed_order = result.unwrap()
        print(f"✅ 주문 처리 성공!")
        print(f"   주문 번호: {processed_order['id']}")
        print(f"   고객 ID: {processed_order['customer_id']}")
        print(f"   상품 수: {len(processed_order['processed_items'])}개")
        print(f"   총 금액: {processed_order['final_total']:,.0f}원")
        print(f"   결제 상태: {processed_order['payment_info']['transaction_id']}")
        print(f"   알림 발송: {'✅' if processed_order.get('notification_sent') else '❌'}")
    else:
        error = result.unwrap_error()
        print(f"❌ 주문 처리 실패: {error}")
    
    return result


# =============================================================================
# Mock functions (실제 구현에서는 별도 모듈에서 제공)
# =============================================================================

def _get_inventory_count(product_id: str) -> int:
    """재고 수량을 조회합니다 (Mock)."""
    inventory_db = {
        'PROD001': 50,
        'PROD002': 100,
        'PROD003': 0
    }
    return inventory_db.get(product_id, 10)


def _process_external_payment(amount: Decimal, method: str) -> dict:
    """외부 결제 시스템을 호출합니다 (Mock)."""
    if amount > 0:
        return {
            'status': 'success',
            'transaction_id': f'TXN_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        }
    return {'status': 'failed', 'error': 'Invalid amount'}


def _reserve_stock(product_id: str, quantity: int) -> bool:
    """재고를 예약합니다 (Mock)."""
    return True  # 항상 성공


def _generate_order_id() -> str:
    """주문 ID를 생성합니다 (Mock)."""
    return f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _save_to_database(order: dict) -> bool:
    """데이터베이스에 저장합니다 (Mock)."""
    return True  # 항상 성공


def _get_customer_email(customer_id: str) -> str:
    """고객 이메일을 조회합니다 (Mock)."""
    return f"customer_{customer_id}@example.com"


def _send_email(to: str, subject: str, body: str) -> bool:
    """이메일을 발송합니다 (Mock)."""
    print(f"📧 이메일 발송: {to} - {subject}")
    return True


def _get_customer_info(customer_id: str) -> dict:
    """고객 정보를 조회합니다 (Mock)."""
    customer_db = {
        'CUST123': {'type': 'vip', 'name': '김VIP'},
        'CUST456': {'type': 'regular', 'name': '이일반'}
    }
    return customer_db.get(customer_id, {'type': 'regular', 'name': '신규고객'})


def _check_business_rule(rule_name: str, rule_config: dict, order_data: dict) -> bool:
    """비즈니스 규칙을 검사합니다 (Mock)."""
    # 실제로는 복잡한 비즈니스 로직
    return True  # 항상 통과


if __name__ == "__main__":
    example_usage()