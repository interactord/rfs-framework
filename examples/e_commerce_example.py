"""
E-commerce Example using RFS Framework

전자상거래 시스템 예제:
- 주문 처리 사가
- 이벤트 기반 아키텍처  
- Reactive Streams
- State Machine
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from rfs import (
    # 함수형 패턴
    Result, Success, Failure,
    # 상태 머신
    StateMachine, State, Transition,
    # 이벤트 시스템
    EventBus, Event,
    # 핵심
    StatelessRegistry
)

# 도메인 모델들
class Order:
    def __init__(self, order_id: str, customer_id: str, items: list, total_amount: float):
        self.order_id = order_id
        self.customer_id = customer_id
        self.items = items
        self.total_amount = total_amount
        self.status = "pending"

class Payment:
    def __init__(self, payment_id: str, order_id: str, amount: float):
        self.payment_id = payment_id
        self.order_id = order_id
        self.amount = amount
        self.status = "pending"

class Inventory:
    def __init__(self):
        self.items = {
            "laptop": 10,
            "mouse": 50,
            "keyboard": 30
        }

    def reserve(self, items: list) -> Result[bool, str]:
        """재고 예약"""
        for item, quantity in items:
            if self.items.get(item, 0) < quantity:
                return Failure(f"Insufficient stock for {item}")
            
        # 재고 차감
        for item, quantity in items:
            self.items[item] -= quantity
            
        return Success(True)

    def release(self, items: list) -> Result[bool, str]:
        """재고 해제"""
        for item, quantity in items:
            self.items[item] += quantity
        return Success(True)

# 서비스들
@StatelessRegistry.register("inventory_service")
class InventoryService:
    def __init__(self):
        self.inventory = Inventory()
    
    async def reserve_items(self, items: list) -> Result[bool, str]:
        """재고 예약"""
        return self.inventory.reserve(items)
    
    async def release_items(self, items: list) -> Result[bool, str]:
        """재고 해제"""  
        return self.inventory.release(items)

@StatelessRegistry.register("payment_service")
class PaymentService:
    async def process_payment(self, payment: Payment) -> Result[Payment, str]:
        """결제 처리"""
        # 결제 로직 시뮬레이션
        await asyncio.sleep(0.1)
        
        if payment.amount > 10000:
            return Failure("Payment amount too high")
        
        payment.status = "completed"
        return Success(payment)
    
    async def refund_payment(self, payment_id: str) -> Result[bool, str]:
        """환불 처리"""
        await asyncio.sleep(0.1)
        return Success(True)

# 주문 처리 오케스트레이터
class OrderProcessingOrchestrator:
    def __init__(self, inventory_service: InventoryService, payment_service: PaymentService):
        self.inventory_service = inventory_service
        self.payment_service = payment_service
    
    async def process_order(self, order: Order) -> Result[Order, str]:
        """주문 처리 프로세스"""
        # 1단계: 재고 예약
        inventory_result = await self.inventory_service.reserve_items(order.items)
        if not inventory_result.is_success:
            return Failure("재고 예약 실패")
        
        # 2단계: 결제 처리
        payment = Payment(f"pay_{order.order_id}", order.order_id, order.total_amount)
        payment_result = await self.payment_service.process_payment(payment)
        if not payment_result.is_success:
            # 재고 해제 (보상 트랜잭션)
            await self.inventory_service.release_items(order.items)
            return Failure("결제 처리 실패")
        
        # 3단계: 주문 완료
        order.status = "completed"
        return Success(order)

# 간단한 주문 검증 서비스  
class OrderValidator:
    @staticmethod
    def validate_order(order: Order) -> Result[Order, str]:
        """주문 검증"""
        if order.total_amount <= 0:
            return Failure("주문 금액이 유효하지 않습니다")
        
        if not order.items:
            return Failure("주문 항목이 없습니다")
        
        return Success(order)

# 메인 실행 함수
async def main():
    """전자상거래 시스템 예제 실행"""
    print("🛒 RFS Framework 전자상거래 예제 시작")
    
    # 서비스 초기화
    inventory_service = InventoryService()
    payment_service = PaymentService()
    orchestrator = OrderProcessingOrchestrator(inventory_service, payment_service)
    
    # 테스트 주문 생성
    order = Order(
        order_id="order_001",
        customer_id="customer_001", 
        items=[("laptop", 1), ("mouse", 2)],
        total_amount=1500.0
    )
    
    print(f"📦 주문 생성: {order.order_id}")
    print(f"💰 주문 금액: ${order.total_amount}")
    
    # 주문 검증
    validation_result = OrderValidator.validate_order(order)
    if not validation_result.is_success:
        print(f"❌ 주문 검증 실패: {validation_result.unwrap_err()}")
        return
    
    print("✅ 주문 검증 성공")
    
    # 주문 처리
    result = await orchestrator.process_order(order)
    
    if result.is_success:
        completed_order = result.unwrap()
        print(f"🎉 주문 처리 완료!")
        print(f"📄 주문 상태: {completed_order.status}")
    else:
        print(f"❌ 주문 처리 실패: {result.unwrap_err()}")
    
    print("\n📊 RFS Framework 기능 테스트:")
    
    # Result 패턴 테스트
    success_result = Success("성공 테스트")
    failure_result = Failure("실패 테스트")
    
    print(f"✅ Success 결과: {success_result.is_success}")
    print(f"❌ Failure 결과: {failure_result.is_success}")
    
    # 상태 머신 테스트
    state_machine = StateMachine("idle")
    print(f"🔄 상태 머신 초기 상태: {state_machine.current_state}")
    
    # 새로운 기능들 테스트 (v4.0.3)
    print("\n🆕 v4.0.3 새로운 기능 테스트:")
    
    # Reactive Streams 테스트
    from rfs.reactive import Flux, Mono
    
    # 병렬 처리 테스트
    print("🔄 Reactive Streams - 병렬 처리:")
    parallel_result = await (
        Flux.from_iterable(range(10))
        .parallel(parallelism=2)
        .map(lambda x: x * 2)
        .collect_list()
    )
    print(f"   병렬 처리 결과: {parallel_result}")
    
    # 윈도우 처리 테스트
    print("📊 Reactive Streams - 윈도우 처리:")
    window_result = await (
        Flux.from_iterable(range(20))
        .window(size=5)
        .flat_map(lambda w: w.reduce(0, lambda a, b: a + b))
        .collect_list()
    )
    print(f"   윈도우 처리 결과 (5개씩 합계): {window_result}")
    
    # 스로틀링 테스트  
    print("⏱️ Reactive Streams - 스로틀링:")
    throttle_result = await (
        Flux.from_iterable(range(100))
        .throttle(elements=10, duration=0.01)  # 빠른 테스트를 위해 짧은 시간
        .take(5)  # 처음 5개만
        .collect_list()
    )
    print(f"   스로틀링 결과: {throttle_result}")
    
    print("\n🚀 전자상거래 예제 완료!")

if __name__ == "__main__":
    asyncio.run(main())