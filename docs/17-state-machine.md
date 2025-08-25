# 17. State Machine

RFS Framework 상태 머신 시스템 및 오케스트레이션.

## 상태 머신 개요

상태 머신은 복잡한 비즈니스 로직의 상태 전이와 행위를 체계적으로 관리할 수 있는 시스템입니다.

## 기본 사용법

```python
from rfs.state_machine import StateMachine, State, Transition

# 주문 상태 머신 정의
order_machine = StateMachine(
    initial_state="pending",
    states=[
        State("pending", on_enter=lambda: print("Order pending")),
        State("paid", on_enter=lambda: print("Payment received")),
        State("shipped", on_enter=lambda: print("Order shipped")),
        State("delivered", on_enter=lambda: print("Order delivered"))
    ],
    transitions=[
        Transition("pending", "paid", trigger="pay"),
        Transition("paid", "shipped", trigger="ship"),
        Transition("shipped", "delivered", trigger="deliver")
    ]
)

# 상태 전이 실행
order_machine.trigger("pay")
order_machine.trigger("ship")
```

## 조건부 전이

```python
def can_ship(order):
    return order.payment_confirmed and order.items_available

# 조건부 전이 설정
Transition(
    "paid", "shipped", 
    trigger="ship", 
    condition=can_ship
)
```

## 관련 문서

- [Event System](16-event-system.md) - 이벤트 시스템
- [Transactions](04-transactions.md) - 트랜잭션 시스템
- [HOF Library](16-hot-library.md) - 함수형 상태 관리 패턴
