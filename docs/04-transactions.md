# 트랜잭션 관리 (Transaction Management)

## 📌 개요

RFS Framework는 데이터베이스 트랜잭션, 분산 트랜잭션, Saga 패턴을 지원하는 포괄적인 트랜잭션 관리 시스템을 제공합니다. Result 패턴과 통합되어 안전하고 명시적인 트랜잭션 처리가 가능합니다.

## 🎯 핵심 개념

### 트랜잭션 패턴
- **로컬 트랜잭션**: 단일 데이터베이스 ACID 보장
- **분산 트랜잭션**: 2PC (Two-Phase Commit) 프로토콜
- **Saga 패턴**: 이벤트 기반 보상 트랜잭션
- **Outbox 패턴**: 트랜잭션과 이벤트 발행 일관성

### ACID 속성
- **Atomicity**: 모두 성공하거나 모두 실패
- **Consistency**: 데이터 무결성 유지
- **Isolation**: 트랜잭션 간 격리
- **Durability**: 영구 저장 보장

## 📚 API 레퍼런스

### TransactionManager 클래스

```python
from rfs.core.transactions import (
    TransactionManager,
    Transaction,
    TransactionScope,
    IsolationLevel,
    TransactionResult
)
```

### 주요 격리 수준

| 레벨 | 설명 | 사용 시기 |
|------|------|-----------|
| `READ_UNCOMMITTED` | 커밋되지 않은 데이터 읽기 가능 | 거의 사용 안 함 |
| `READ_COMMITTED` | 커밋된 데이터만 읽기 | 기본값 |
| `REPEATABLE_READ` | 트랜잭션 중 같은 데이터 보장 | 일관성 중요 |
| `SERIALIZABLE` | 완전한 격리 | 최고 수준 격리 |

## 💡 사용 예제

### 기본 트랜잭션 관리

```python
from rfs.core.transactions import TransactionManager, transactional
from rfs.core.result import Result, Success, Failure
from typing import Optional
import asyncpg

class DatabaseTransaction:
    """데이터베이스 트랜잭션 관리"""
    
    def __init__(self, connection_pool):
        self.pool = connection_pool
        self.transaction_manager = TransactionManager()
    
    @transactional
    async def transfer_money(
        self,
        from_account: str,
        to_account: str,
        amount: float
    ) -> Result[dict, str]:
        """계좌 이체 트랜잭션"""
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # 1. 출금 계좌 확인
                    sender = await conn.fetchrow(
                        "SELECT balance FROM accounts WHERE id = $1",
                        from_account
                    )
                    
                    if not sender:
                        return Failure("출금 계좌를 찾을 수 없습니다")
                    
                    if sender['balance'] < amount:
                        return Failure("잔액 부족")
                    
                    # 2. 출금
                    await conn.execute(
                        "UPDATE accounts SET balance = balance - $1 WHERE id = $2",
                        amount, from_account
                    )
                    
                    # 3. 입금
                    await conn.execute(
                        "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
                        amount, to_account
                    )
                    
                    # 4. 거래 기록
                    transaction_id = await conn.fetchval(
                        """INSERT INTO transactions 
                           (from_account, to_account, amount, status)
                           VALUES ($1, $2, $3, 'completed')
                           RETURNING id""",
                        from_account, to_account, amount
                    )
                    
                    return Success({
                        "transaction_id": transaction_id,
                        "amount": amount,
                        "status": "completed"
                    })
                    
                except Exception as e:
                    # 자동 롤백
                    return Failure(f"트랜잭션 실패: {str(e)}")
```

### 분산 트랜잭션 (2PC)

```python
from rfs.core.transactions import DistributedTransaction, Participant
from enum import Enum

class TransactionPhase(Enum):
    PREPARE = "prepare"
    COMMIT = "commit"
    ROLLBACK = "rollback"

class TwoPhaseCommitManager:
    """2PC 분산 트랜잭션 관리자"""
    
    def __init__(self):
        self.participants = []
        self.transaction_log = []
    
    async def execute_distributed_transaction(
        self,
        operations: list
    ) -> Result[dict, str]:
        """분산 트랜잭션 실행"""
        
        transaction_id = self.generate_transaction_id()
        prepared_participants = []
        
        try:
            # Phase 1: Prepare
            for operation in operations:
                participant = operation['participant']
                action = operation['action']
                
                prepare_result = await participant.prepare(
                    transaction_id,
                    action
                )
                
                if prepare_result.is_failure():
                    # Prepare 실패 - 모두 롤백
                    await self._rollback_all(prepared_participants, transaction_id)
                    return Failure(f"Prepare 실패: {prepare_result.error}")
                
                prepared_participants.append(participant)
                self.log_phase(transaction_id, participant, TransactionPhase.PREPARE)
            
            # Phase 2: Commit
            commit_results = []
            for participant in prepared_participants:
                commit_result = await participant.commit(transaction_id)
                
                if commit_result.is_failure():
                    # Commit 실패 - 보상 트랜잭션 필요
                    return await self._handle_commit_failure(
                        transaction_id,
                        prepared_participants,
                        participant
                    )
                
                commit_results.append(commit_result.value)
                self.log_phase(transaction_id, participant, TransactionPhase.COMMIT)
            
            return Success({
                "transaction_id": transaction_id,
                "status": "committed",
                "results": commit_results
            })
            
        except Exception as e:
            await self._rollback_all(prepared_participants, transaction_id)
            return Failure(f"분산 트랜잭션 실패: {str(e)}")
    
    async def _rollback_all(
        self,
        participants: list,
        transaction_id: str
    ):
        """모든 참여자 롤백"""
        for participant in participants:
            try:
                await participant.rollback(transaction_id)
                self.log_phase(transaction_id, participant, TransactionPhase.ROLLBACK)
            except Exception as e:
                # 롤백 실패 로깅
                print(f"롤백 실패: {participant.name} - {e}")
    
    def generate_transaction_id(self) -> str:
        import uuid
        return str(uuid.uuid4())
    
    def log_phase(
        self,
        transaction_id: str,
        participant,
        phase: TransactionPhase
    ):
        """트랜잭션 로그 기록"""
        self.transaction_log.append({
            "transaction_id": transaction_id,
            "participant": participant.name,
            "phase": phase.value,
            "timestamp": datetime.now()
        })
```

### Saga 패턴 구현

```python
from rfs.core.transactions import Saga, SagaStep, CompensationAction
from typing import List, Callable
import asyncio

class OrderSaga:
    """주문 처리 Saga"""
    
    def __init__(self):
        self.steps: List[SagaStep] = []
        self.compensation_stack = []
    
    async def execute_order(
        self,
        order_data: dict
    ) -> Result[dict, str]:
        """주문 Saga 실행"""
        
        # Saga 단계 정의
        self.steps = [
            SagaStep(
                name="reserve_inventory",
                action=self.reserve_inventory,
                compensation=self.cancel_inventory_reservation
            ),
            SagaStep(
                name="process_payment",
                action=self.process_payment,
                compensation=self.refund_payment
            ),
            SagaStep(
                name="create_shipment",
                action=self.create_shipment,
                compensation=self.cancel_shipment
            ),
            SagaStep(
                name="send_notification",
                action=self.send_notification,
                compensation=None  # 보상 불필요
            )
        ]
        
        context = {"order": order_data}
        
        # Saga 실행
        for step in self.steps:
            result = await step.action(context)
            
            if result.is_success():
                # 성공 - 보상 액션 스택에 추가
                if step.compensation:
                    self.compensation_stack.append(
                        (step.compensation, context.copy())
                    )
                
                # 컨텍스트 업데이트
                context.update(result.value)
            else:
                # 실패 - 보상 트랜잭션 실행
                await self.compensate()
                return Failure(f"Saga 실패: {step.name} - {result.error}")
        
        return Success({
            "order_id": context.get("order_id"),
            "status": "completed",
            "details": context
        })
    
    async def compensate(self):
        """보상 트랜잭션 실행"""
        print("보상 트랜잭션 시작...")
        
        # 역순으로 보상 실행
        while self.compensation_stack:
            compensation_action, context = self.compensation_stack.pop()
            try:
                await compensation_action(context)
                print(f"보상 완료: {compensation_action.__name__}")
            except Exception as e:
                print(f"보상 실패: {compensation_action.__name__} - {e}")
                # 보상 실패는 로깅하고 계속 진행
    
    # Saga 액션들
    async def reserve_inventory(self, context: dict) -> Result:
        """재고 예약"""
        order = context["order"]
        # 재고 서비스 호출
        print(f"재고 예약: {order['product_id']}")
        return Success({"reservation_id": "res_123"})
    
    async def cancel_inventory_reservation(self, context: dict):
        """재고 예약 취소"""
        reservation_id = context.get("reservation_id")
        print(f"재고 예약 취소: {reservation_id}")
    
    async def process_payment(self, context: dict) -> Result:
        """결제 처리"""
        order = context["order"]
        print(f"결제 처리: {order['amount']}")
        return Success({"payment_id": "pay_456"})
    
    async def refund_payment(self, context: dict):
        """결제 환불"""
        payment_id = context.get("payment_id")
        print(f"결제 환불: {payment_id}")
    
    async def create_shipment(self, context: dict) -> Result:
        """배송 생성"""
        print("배송 준비")
        return Success({"shipment_id": "ship_789"})
    
    async def cancel_shipment(self, context: dict):
        """배송 취소"""
        shipment_id = context.get("shipment_id")
        print(f"배송 취소: {shipment_id}")
    
    async def send_notification(self, context: dict) -> Result:
        """알림 발송"""
        print("주문 완료 알림 발송")
        return Success({"notification_sent": True})
```

### Outbox 패턴

```python
from rfs.core.transactions import OutboxPattern
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class OutboxEvent:
    """Outbox 이벤트"""
    id: str
    aggregate_id: str
    event_type: str
    payload: dict
    created_at: datetime
    processed: bool = False

class TransactionalOutbox:
    """트랜잭셔널 아웃박스 패턴"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    async def execute_with_events(
        self,
        business_logic: Callable,
        events: List[dict]
    ) -> Result[dict, str]:
        """비즈니스 로직과 이벤트를 트랜잭션으로 처리"""
        
        async with self.conn.transaction():
            try:
                # 1. 비즈니스 로직 실행
                result = await business_logic()
                
                if result.is_failure():
                    raise Exception(result.error)
                
                # 2. Outbox에 이벤트 저장
                for event in events:
                    await self.conn.execute(
                        """INSERT INTO outbox_events 
                           (id, aggregate_id, event_type, payload, created_at)
                           VALUES ($1, $2, $3, $4, $5)""",
                        event['id'],
                        event['aggregate_id'],
                        event['event_type'],
                        json.dumps(event['payload']),
                        datetime.now()
                    )
                
                return Success({
                    "result": result.value,
                    "events_queued": len(events)
                })
                
            except Exception as e:
                # 트랜잭션 자동 롤백
                return Failure(f"트랜잭션 실패: {str(e)}")
    
    async def process_outbox_events(self):
        """Outbox 이벤트 처리 (별도 프로세스)"""
        
        while True:
            # 미처리 이벤트 조회
            events = await self.conn.fetch(
                """SELECT * FROM outbox_events 
                   WHERE processed = false 
                   ORDER BY created_at 
                   LIMIT 100"""
            )
            
            for event in events:
                try:
                    # 이벤트 발행
                    await self.publish_event(event)
                    
                    # 처리 완료 표시
                    await self.conn.execute(
                        "UPDATE outbox_events SET processed = true WHERE id = $1",
                        event['id']
                    )
                    
                except Exception as e:
                    print(f"이벤트 발행 실패: {event['id']} - {e}")
                    # 재시도 로직
            
            await asyncio.sleep(1)  # 1초 대기
    
    async def publish_event(self, event):
        """이벤트 발행"""
        # 메시지 큐에 발행
        print(f"이벤트 발행: {event['event_type']}")
```

### 트랜잭션 스코프

```python
from rfs.core.transactions import TransactionScope, transaction_scope
from contextlib import asynccontextmanager

class TransactionalService:
    """트랜잭셔널 서비스"""
    
    def __init__(self, db_pool):
        self.pool = db_pool
    
    @asynccontextmanager
    async def transaction_scope(
        self,
        isolation_level=IsolationLevel.READ_COMMITTED
    ):
        """트랜잭션 스코프 관리"""
        conn = await self.pool.acquire()
        transaction = conn.transaction(isolation=isolation_level)
        
        try:
            await transaction.start()
            yield conn
            await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise
        finally:
            await self.pool.release(conn)
    
    async def complex_operation(self) -> Result:
        """복잡한 트랜잭션 작업"""
        
        async with self.transaction_scope() as conn:
            # 여러 작업을 하나의 트랜잭션으로
            
            # 1. 사용자 생성
            user_id = await conn.fetchval(
                "INSERT INTO users (name) VALUES ($1) RETURNING id",
                "홍길동"
            )
            
            # 2. 프로필 생성
            await conn.execute(
                "INSERT INTO profiles (user_id, bio) VALUES ($1, $2)",
                user_id, "안녕하세요"
            )
            
            # 3. 기본 설정 생성
            await conn.execute(
                "INSERT INTO settings (user_id, theme) VALUES ($1, $2)",
                user_id, "dark"
            )
            
            return Success({"user_id": user_id})
```

## 🎨 베스트 프랙티스

### 1. 트랜잭션 범위 최소화

```python
# ❌ 나쁜 예 - 긴 트랜잭션
async with transaction():
    data = await fetch_external_api()  # 외부 API 호출
    await process_data(data)
    await save_to_db(data)

# ✅ 좋은 예 - 짧은 트랜잭션
data = await fetch_external_api()
processed = await process_data(data)

async with transaction():
    await save_to_db(processed)
```

### 2. 적절한 격리 수준 선택

```python
# 읽기 전용 작업
async with transaction(isolation=IsolationLevel.READ_COMMITTED):
    data = await read_data()

# 일관성이 중요한 작업
async with transaction(isolation=IsolationLevel.SERIALIZABLE):
    await critical_update()
```

### 3. 데드락 방지

```python
# 항상 같은 순서로 테이블 접근
async def transfer(from_id: int, to_id: int):
    # ID 순서로 정렬하여 데드락 방지
    if from_id > to_id:
        from_id, to_id = to_id, from_id
    
    async with transaction():
        await lock_account(from_id)
        await lock_account(to_id)
        # 이체 처리
```

## ⚠️ 주의사항

### 1. 트랜잭션 타임아웃
- 긴 트랜잭션은 타임아웃 설정
- 데드락 감지 및 재시도 메커니즘

### 2. 분산 트랜잭션
- 네트워크 분할 고려
- 보상 트랜잭션 준비
- 이벤트 순서 보장

### 3. 성능 고려사항
- 배치 처리 활용
- 비동기 처리 고려
- 인덱스 최적화

## 🔗 관련 문서
- [이벤트 시스템](./16-event-system.md)
- [상태 머신](./17-state-machine.md)
- [데이터베이스 패턴](./18-database.md)