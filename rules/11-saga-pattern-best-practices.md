# Saga 패턴 베스트 프랙티스

## 개요

Saga 패턴은 분산 시스템에서 장기 실행 트랜잭션을 관리하기 위한 패턴입니다. RFS Framework는 Result 패턴과 리액티브 프로그래밍과 완벽하게 통합된 Saga 구현을 제공합니다.

## 핵심 개념

### 1. Saga란?
- **분산 트랜잭션**: 여러 서비스에 걸친 비즈니스 트랜잭션
- **보상 패턴**: 실패 시 이전 작업들을 되돌리는 역방향 작업
- **최종 일관성**: ACID 대신 최종적으로 일관된 상태를 보장

### 2. Saga vs 2PC (Two-Phase Commit)
```python
# ❌ 2PC - 모든 참여자가 동시에 잠금 (블로킹)
# ✅ Saga - 각 단계별 로컬 트랜잭션 + 보상 액션
```

## Saga 패턴 베스트 프랙티스 ⭐

### 1. Result 패턴과 통합된 안전한 Saga 설계

```python
from rfs.core.result import Result, Success, Failure
from rfs.events.saga import create_saga, SagaContext
from rfs.hof.core import pipe

# ✅ 모든 Saga 단계는 Result 반환
async def create_user_step(data: dict) -> Result[dict, str]:
    """사용자 생성 단계"""
    try:
        user = await user_service.create_user(data)
        return Success({"user_id": user.id, "email": user.email})
    except Exception as e:
        return Failure(f"사용자 생성 실패: {str(e)}")

async def compensate_create_user(data: dict) -> Result[dict, str]:
    """사용자 생성 보상 액션"""
    try:
        if "user_id" in data:
            await user_service.delete_user(data["user_id"])
        return Success({"compensated": True})
    except Exception as e:
        return Failure(f"사용자 삭제 보상 실패: {str(e)}")

async def send_welcome_email_step(data: dict) -> Result[dict, str]:
    """환영 이메일 발송 단계"""
    try:
        email_result = await email_service.send_welcome_email(
            data["user_id"], data["email"]
        )
        return Success({"email_sent": True, "email_id": email_result.id})
    except Exception as e:
        return Failure(f"이메일 발송 실패: {str(e)}")

# ✅ Result를 안전하게 처리하는 Saga 실행 래퍼
async def execute_saga_step_safe(step_func: callable, data: dict) -> dict:
    """Saga 단계를 안전하게 실행하고 Result를 언래핑"""
    result = await step_func(data)
    if result.is_failure():
        raise Exception(result.unwrap_error())
    return {**data, **result.unwrap()}

# Saga 구성
user_onboarding_saga = (
    create_saga("user_onboarding")
    .step("create_user", lambda data: execute_saga_step_safe(create_user_step, data))
    .step("send_email", lambda data: execute_saga_step_safe(send_welcome_email_step, data))
)
```

### 2. 복잡한 비즈니스 워크플로우 Saga 패턴

```python
# ✅ 전자상거래 주문 처리 Saga
class OrderProcessingSaga:
    """주문 처리를 위한 복합 Saga"""
    
    def __init__(self, order_service, payment_service, inventory_service):
        self.order_service = order_service
        self.payment_service = payment_service
        self.inventory_service = inventory_service
    
    async def create_order_saga(self, order_data: dict) -> Saga:
        """주문 처리 Saga 생성"""
        
        saga = create_saga("order_processing", "전자상거래 주문 처리")
        
        return (saga
            .step("validate_order", self._validate_order_step, self._compensate_validate_order)
            .step("reserve_inventory", self._reserve_inventory_step, self._release_inventory_compensation)
            .step("process_payment", self._process_payment_step, self._refund_payment_compensation)
            .step("create_order", self._create_order_step, self._cancel_order_compensation)
            .step("send_confirmation", self._send_confirmation_step, self._send_cancellation_compensation)
        )
    
    # 주문 검증 단계
    async def _validate_order_step(self, data: dict) -> dict:
        """주문 데이터 검증"""
        result = await self._safe_validate_order(data)
        if result.is_failure():
            raise Exception(result.unwrap_error())
        
        validated_data = result.unwrap()
        return {**data, **validated_data}
    
    async def _safe_validate_order(self, data: dict) -> Result[dict, str]:
        """안전한 주문 검증"""
        try:
            # 상품 존재 여부 확인
            items = data.get("items", [])
            if not items:
                return Failure("주문 항목이 비어있습니다")
            
            # 각 상품 검증
            validated_items = []
            total_amount = 0
            
            for item in items:
                product_result = await self.inventory_service.get_product(item["product_id"])
                if product_result.is_failure():
                    return Failure(f"상품 조회 실패: {product_result.unwrap_error()}")
                
                product = product_result.unwrap()
                if product["stock"] < item["quantity"]:
                    return Failure(f"재고 부족: {product['name']}")
                
                item_total = product["price"] * item["quantity"]
                validated_items.append({
                    **item,
                    "price": product["price"],
                    "total": item_total
                })
                total_amount += item_total
            
            return Success({
                "validated_items": validated_items,
                "total_amount": total_amount,
                "validation_timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            return Failure(f"주문 검증 중 오류: {str(e)}")
    
    async def _compensate_validate_order(self, data: dict) -> dict:
        """주문 검증 보상 (로깅만)"""
        logger.info(f"주문 검증 단계 보상: {data.get('correlation_id')}")
        return data
    
    # 재고 예약 단계
    async def _reserve_inventory_step(self, data: dict) -> dict:
        """재고 예약"""
        reservation_ids = []
        
        try:
            for item in data["validated_items"]:
                result = await self.inventory_service.reserve_stock(
                    item["product_id"], 
                    item["quantity"]
                )
                if result.is_failure():
                    # 이미 예약된 항목들 해제
                    await self._release_reservations(reservation_ids)
                    raise Exception(result.unwrap_error())
                
                reservation_ids.append(result.unwrap()["reservation_id"])
            
            return {**data, "reservation_ids": reservation_ids}
            
        except Exception as e:
            raise Exception(f"재고 예약 실패: {str(e)}")
    
    async def _release_inventory_compensation(self, data: dict) -> dict:
        """재고 예약 해제 보상"""
        if "reservation_ids" in data:
            await self._release_reservations(data["reservation_ids"])
        return data
    
    async def _release_reservations(self, reservation_ids: list):
        """예약 해제 헬퍼"""
        for reservation_id in reservation_ids:
            try:
                await self.inventory_service.release_reservation(reservation_id)
            except Exception as e:
                logger.error(f"예약 해제 실패 {reservation_id}: {e}")
    
    # 결제 처리 단계
    async def _process_payment_step(self, data: dict) -> dict:
        """결제 처리"""
        result = await self.payment_service.process_payment({
            "amount": data["total_amount"],
            "currency": data.get("currency", "KRW"),
            "payment_method": data["payment_method"],
            "customer_id": data["customer_id"]
        })
        
        if result.is_failure():
            raise Exception(result.unwrap_error())
        
        payment_info = result.unwrap()
        return {**data, "payment_id": payment_info["payment_id"]}
    
    async def _refund_payment_compensation(self, data: dict) -> dict:
        """결제 환불 보상"""
        if "payment_id" in data:
            try:
                await self.payment_service.refund_payment(data["payment_id"])
            except Exception as e:
                logger.error(f"환불 실패 {data['payment_id']}: {e}")
        return data
```

### 3. 이벤트 기반 Saga 오케스트레이션

```python
# ✅ 이벤트 주도 Saga 패턴
class EventDrivenSagaOrchestrator:
    """이벤트 기반 Saga 오케스트레이터"""
    
    def __init__(self, event_bus, saga_manager):
        self.event_bus = event_bus
        self.saga_manager = saga_manager
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """이벤트 핸들러 설정"""
        self.event_bus.subscribe("order_created", self._handle_order_created)
        self.event_bus.subscribe("payment_completed", self._handle_payment_completed)
        self.event_bus.subscribe("payment_failed", self._handle_payment_failed)
        self.event_bus.subscribe("shipping_completed", self._handle_shipping_completed)
    
    async def _handle_order_created(self, event: Event):
        """주문 생성 이벤트 처리"""
        order_data = event.data
        
        # Saga 컨텍스트 생성
        context = SagaContext(
            saga_id="order_fulfillment",
            correlation_id=f"order_{order_data['order_id']}",
            data=order_data
        )
        
        # 주문 이행 Saga 시작
        try:
            await self.saga_manager.start_saga("order_fulfillment", context)
        except Exception as e:
            logger.error(f"주문 이행 Saga 시작 실패: {e}")
            await self._publish_saga_failed_event(context, str(e))
    
    async def _handle_payment_completed(self, event: Event):
        """결제 완료 이벤트 처리"""
        payment_data = event.data
        
        # 해당 주문의 다음 단계 (배송) 진행
        await self._trigger_next_saga_step(
            f"order_{payment_data['order_id']}", 
            "proceed_to_shipping",
            payment_data
        )
    
    async def _handle_payment_failed(self, event: Event):
        """결제 실패 이벤트 처리"""
        payment_data = event.data
        
        # 해당 주문의 Saga 실패 처리
        await self._trigger_saga_compensation(
            f"order_{payment_data['order_id']}",
            "payment_failed",
            payment_data
        )
    
    async def _trigger_next_saga_step(self, correlation_id: str, step: str, data: dict):
        """다음 Saga 단계 트리거"""
        try:
            # 실행 중인 Saga 찾기
            running_sagas = self.saga_manager.get_running_sagas()
            if correlation_id in running_sagas:
                # 다음 단계 실행을 위한 이벤트 발행
                await self.event_bus.publish(Event(
                    event_type=f"saga_step_{step}",
                    data={
                        "correlation_id": correlation_id,
                        "step": step,
                        "data": data
                    }
                ))
        except Exception as e:
            logger.error(f"Saga 다음 단계 트리거 실패: {e}")
    
    async def _trigger_saga_compensation(self, correlation_id: str, reason: str, data: dict):
        """Saga 보상 트리거"""
        try:
            await self.event_bus.publish(Event(
                event_type="saga_compensation_required",
                data={
                    "correlation_id": correlation_id,
                    "reason": reason,
                    "data": data
                }
            ))
        except Exception as e:
            logger.error(f"Saga 보상 트리거 실패: {e}")
```

### 4. Saga 상태 관리 및 모니터링

```python
# ✅ 영속적 Saga 상태 관리
class PersistentSagaManager:
    """영속적 Saga 관리자"""
    
    def __init__(self, repository, event_bus):
        self.repository = repository
        self.event_bus = event_bus
        self.saga_registry = {}
    
    async def register_saga_definition(self, saga_id: str, saga_builder: callable):
        """Saga 정의 등록"""
        self.saga_registry[saga_id] = saga_builder
        logger.info(f"Saga 정의 등록: {saga_id}")
    
    async def start_saga_with_persistence(
        self, 
        saga_id: str, 
        context: SagaContext
    ) -> Result[SagaContext, str]:
        """영속성을 가진 Saga 시작"""
        try:
            # Saga 정의 조회
            if saga_id not in self.saga_registry:
                return Failure(f"등록되지 않은 Saga: {saga_id}")
            
            # Saga 인스턴스 생성
            saga_builder = self.saga_registry[saga_id]
            saga = await saga_builder(context.data)
            
            # 초기 상태 저장
            await self._save_saga_state(context, "STARTED", current_step=0)
            
            # Saga 실행
            result_context = await self._execute_saga_with_checkpoints(saga, context)
            
            return Success(result_context)
            
        except Exception as e:
            logger.error(f"Saga 시작 실패 {saga_id}: {e}")
            await self._save_saga_state(context, "FAILED", error=str(e))
            return Failure(str(e))
    
    async def _execute_saga_with_checkpoints(
        self, 
        saga: Saga, 
        context: SagaContext
    ) -> SagaContext:
        """체크포인트를 포함한 Saga 실행"""
        
        for i, step in enumerate(saga.steps):
            try:
                # 단계 시작 체크포인트
                await self._save_saga_state(
                    context, 
                    "RUNNING", 
                    current_step=i,
                    current_step_name=step.step_id
                )
                
                # 단계 실행
                step_result = await self._execute_step_with_monitoring(step, context)
                context = context.with_data(**step_result)
                
                # 단계 완료 체크포인트
                await self._save_saga_state(
                    context, 
                    "STEP_COMPLETED", 
                    current_step=i,
                    completed_steps=context.completed_steps + [step.step_id]
                )
                
            except Exception as e:
                logger.error(f"Saga 단계 {step.step_id} 실패: {e}")
                
                # 실패 상태 저장
                await self._save_saga_state(
                    context, 
                    "STEP_FAILED", 
                    current_step=i,
                    failed_step=step.step_id,
                    error=str(e)
                )
                
                # 보상 실행
                compensation_context = await self._execute_compensation_with_checkpoints(
                    saga, context, i
                )
                
                return compensation_context
        
        # 모든 단계 성공
        await self._save_saga_state(context, "COMPLETED")
        return context
    
    async def _execute_compensation_with_checkpoints(
        self,
        saga: Saga,
        context: SagaContext,
        failed_step_index: int
    ) -> SagaContext:
        """체크포인트를 포함한 보상 실행"""
        
        await self._save_saga_state(context, "COMPENSATION_STARTED")
        
        # 완료된 단계들을 역순으로 보상
        for i in range(failed_step_index - 1, -1, -1):
            step = saga.steps[i]
            
            if step.compensation:
                try:
                    await self._save_saga_state(
                        context,
                        "COMPENSATING_STEP",
                        compensating_step=step.step_id
                    )
                    
                    await step.compensation(context.data)
                    
                    await self._save_saga_state(
                        context,
                        "STEP_COMPENSATED",
                        compensated_step=step.step_id
                    )
                    
                except Exception as e:
                    logger.error(f"보상 실패 {step.step_id}: {e}")
                    await self._save_saga_state(
                        context,
                        "COMPENSATION_FAILED",
                        failed_compensation_step=step.step_id,
                        compensation_error=str(e)
                    )
        
        await self._save_saga_state(context, "COMPENSATED")
        return context
    
    async def _save_saga_state(self, context: SagaContext, status: str, **metadata):
        """Saga 상태 저장"""
        state_data = {
            "saga_id": context.saga_id,
            "correlation_id": context.correlation_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "context_data": context.data,
            **metadata
        }
        
        await self.repository.save_saga_state(context.correlation_id, state_data)
        
        # 상태 변경 이벤트 발행
        await self.event_bus.publish(Event(
            event_type="saga_state_changed",
            data=state_data
        ))
```

### 5. Saga 성능 최적화 및 모니터링

```python
# ✅ 성능 최적화된 Saga 실행
class HighPerformanceSagaExecutor:
    """고성능 Saga 실행기"""
    
    def __init__(self, config: dict):
        self.config = config
        self.metrics_collector = MetricsCollector()
        self.circuit_breakers = {}
    
    async def execute_saga_with_optimization(
        self, 
        saga: Saga, 
        context: SagaContext
    ) -> Result[SagaContext, str]:
        """최적화된 Saga 실행"""
        
        start_time = time.time()
        saga_metrics = SagaMetrics(saga.saga_id, context.correlation_id)
        
        try:
            # 병렬 실행 가능한 단계 분석
            execution_plan = self._analyze_execution_dependencies(saga)
            
            # 최적화된 실행
            result_context = await self._execute_with_plan(saga, context, execution_plan)
            
            # 메트릭 수집
            execution_time = time.time() - start_time
            saga_metrics.record_success(execution_time)
            await self.metrics_collector.record_saga_metrics(saga_metrics)
            
            return Success(result_context)
            
        except Exception as e:
            execution_time = time.time() - start_time
            saga_metrics.record_failure(execution_time, str(e))
            await self.metrics_collector.record_saga_metrics(saga_metrics)
            
            return Failure(str(e))
    
    def _analyze_execution_dependencies(self, saga: Saga) -> ExecutionPlan:
        """실행 종속성 분석"""
        
        # 각 단계의 입력/출력 데이터 의존성 분석
        dependency_graph = {}
        parallel_groups = []
        
        for i, step in enumerate(saga.steps):
            dependencies = self._analyze_step_dependencies(step, saga.steps[:i])
            dependency_graph[step.step_id] = dependencies
            
            # 의존성이 없는 단계들을 병렬 그룹으로 묶기
            if not dependencies:
                parallel_groups.append([step.step_id])
            else:
                # 의존성이 있는 단계는 순차 실행
                parallel_groups.append([step.step_id])
        
        return ExecutionPlan(dependency_graph, parallel_groups)
    
    async def _execute_with_plan(
        self, 
        saga: Saga, 
        context: SagaContext, 
        plan: ExecutionPlan
    ) -> SagaContext:
        """실행 계획에 따른 Saga 실행"""
        
        for group in plan.parallel_groups:
            if len(group) == 1:
                # 순차 실행
                step = next(s for s in saga.steps if s.step_id == group[0])
                context = await self._execute_step_with_circuit_breaker(step, context)
            else:
                # 병렬 실행
                parallel_tasks = []
                for step_id in group:
                    step = next(s for s in saga.steps if s.step_id == step_id)
                    task = asyncio.create_task(
                        self._execute_step_with_circuit_breaker(step, context)
                    )
                    parallel_tasks.append((step_id, task))
                
                # 병렬 실행 결과 수집
                for step_id, task in parallel_tasks:
                    try:
                        step_result = await task
                        context = context.with_data(**step_result)
                    except Exception as e:
                        # 다른 병렬 태스크 취소
                        for _, other_task in parallel_tasks:
                            if not other_task.done():
                                other_task.cancel()
                        raise e
        
        return context
    
    async def _execute_step_with_circuit_breaker(
        self, 
        step: SagaStep, 
        context: SagaContext
    ) -> dict:
        """서킷 브레이커를 사용한 단계 실행"""
        
        circuit_breaker = self._get_circuit_breaker(step.step_id)
        
        if circuit_breaker.is_open():
            raise Exception(f"서킷 브레이커가 열려있음: {step.step_id}")
        
        try:
            result = await step.action(context.data)
            circuit_breaker.record_success()
            return result
            
        except Exception as e:
            circuit_breaker.record_failure()
            raise e
    
    def _get_circuit_breaker(self, step_id: str) -> CircuitBreaker:
        """단계별 서킷 브레이커 조회/생성"""
        if step_id not in self.circuit_breakers:
            self.circuit_breakers[step_id] = CircuitBreaker(
                failure_threshold=self.config.get('circuit_breaker_threshold', 5),
                timeout_seconds=self.config.get('circuit_breaker_timeout', 60)
            )
        return self.circuit_breakers[step_id]


# ✅ 실시간 Saga 모니터링
class SagaMonitoringDashboard:
    """Saga 모니터링 대시보드"""
    
    def __init__(self, saga_manager, metrics_collector):
        self.saga_manager = saga_manager
        self.metrics_collector = metrics_collector
    
    async def get_saga_health_metrics(self) -> dict:
        """Saga 상태 메트릭"""
        
        stats = self.saga_manager.get_stats()
        recent_metrics = await self.metrics_collector.get_recent_metrics(hours=24)
        
        return {
            "overview": {
                "total_sagas": stats["total_sagas"],
                "running_sagas": stats["running_sagas"],
                "success_rate": stats["success_rate"],
                "compensation_rate": stats["compensation_rate"]
            },
            "performance": {
                "avg_execution_time": recent_metrics.get("avg_execution_time", 0),
                "p95_execution_time": recent_metrics.get("p95_execution_time", 0),
                "throughput_per_minute": recent_metrics.get("throughput_per_minute", 0)
            },
            "health_indicators": {
                "circuit_breaker_trips": recent_metrics.get("circuit_breaker_trips", 0),
                "compensation_triggers": recent_metrics.get("compensation_triggers", 0),
                "timeout_failures": recent_metrics.get("timeout_failures", 0)
            }
        }
    
    async def get_saga_execution_details(self, correlation_id: str) -> dict:
        """특정 Saga 실행 상세 정보"""
        
        execution_history = await self.metrics_collector.get_saga_execution_history(
            correlation_id
        )
        
        return {
            "correlation_id": correlation_id,
            "execution_timeline": execution_history.get("timeline", []),
            "step_details": execution_history.get("steps", []),
            "performance_metrics": execution_history.get("metrics", {}),
            "compensation_history": execution_history.get("compensations", [])
        }
```

## 모범 사례 요약

### ✅ DO (해야 할 것)
1. **Result 패턴 통합**: 모든 Saga 단계에서 Result 타입 사용
2. **멱등성 보장**: 각 단계와 보상 액션이 여러 번 실행되어도 안전하도록 설계
3. **타임아웃 설정**: 모든 단계에 적절한 타임아웃 설정
4. **상태 영속화**: 장기 실행 Saga의 상태를 지속적으로 저장
5. **보상 액션 필수**: 모든 비즈니스 단계에 대응하는 보상 액션 구현
6. **모니터링**: 실행 상태, 성능 지표, 실패율 모니터링
7. **서킷 브레이커**: 외부 서비스 호출에 서킷 브레이커 패턴 적용

### ❌ DON'T (하지 말아야 할 것)
1. **긴 단일 트랜잭션**: 모든 작업을 하나의 긴 트랜잭션으로 처리
2. **보상 없는 단계**: 보상 불가능한 단계를 Saga에 포함
3. **상태 공유**: Saga 간 상태 공유 (각 Saga는 독립적)
4. **동기 블로킹**: 긴 시간 동기적으로 대기하는 단계
5. **예외 던지기**: Result 패턴 대신 예외를 사용한 에러 처리
6. **무한 재시도**: 재시도 횟수 제한 없이 무한 재시도
7. **복잡한 의존성**: 너무 복잡한 단계 간 의존성 설계

## 실전 적용 가이드

### 1. Saga 설계 체크리스트
- [ ] 각 단계가 독립적인 로컬 트랜잭션인가?
- [ ] 모든 단계에 보상 액션이 정의되어 있는가?
- [ ] 보상 액션이 멱등성을 보장하는가?
- [ ] 타임아웃과 재시도 정책이 적절한가?
- [ ] 상태 저장 및 복구 메커니즘이 있는가?

### 2. 성능 고려사항
- [ ] 병렬 실행 가능한 단계를 식별했는가?
- [ ] 외부 서비스 호출에 서킷 브레이커를 적용했는가?
- [ ] 적절한 백프레셔 메커니즘이 있는가?
- [ ] 메트릭 수집 및 모니터링이 구현되어 있는가?

### 3. 장애 처리
- [ ] 부분 실패 시나리오를 고려했는가?
- [ ] 보상 실패 시 처리 방안이 있는가?
- [ ] 데드레터 큐 또는 수동 개입 프로세스가 있는가?
- [ ] 알림 및 로깅 메커니즘이 구현되어 있는가?