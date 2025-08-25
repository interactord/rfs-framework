# 16. Event System

RFS Framework 이벤트 시스템 및 비동기 이벤트 처리.

## 이벤트 시스템 개요

이벤트 시스템은 컴포넌트 간의 느슨한 결합을 최소화하고 비동기 통신을 가능하게 합니다.

## 기본 사용법

```python
from rfs.events import EventBus, Event

# 이벤트 버스 생성
event_bus = EventBus()

# 이벤트 수신대 등록
@event_bus.subscriber("user.created")
def on_user_created(event: Event):
    print(f"User created: {event.data}")

# 이벤트 발행
event_bus.publish("user.created", {"id": 1, "name": "John"})
```

## 비동기 이벤트 처리

```python
import asyncio
from rfs.events import AsyncEventBus

# 비동기 이벤트 버스
async_event_bus = AsyncEventBus()

# 비동기 이벤트 핸들러
@async_event_bus.subscriber("data.processed")
async def on_data_processed(event: Event):
    await asyncio.sleep(1)  # 비동기 작업
    print(f"Data processed: {event.data}")
```

## 관련 문서

- [Transactions](04-transactions.md) - 트랜잭션 시스템
- [State Machine](17-state-machine.md) - 상태 관리
- [Result Pattern](04-transactions.md) - 트랜잭션과 이벤트 연동
