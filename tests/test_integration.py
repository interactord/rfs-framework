"""
RFS Framework Integration Tests

전체 프레임워크 통합 테스트
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from rfs import (
    Flux, Mono,
    Result, success, failure,
    StatelessRegistry,
    EventBus, Event, Saga,
    CloudRunOptimizer
)

class TestIntegration:
    """통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_reactive_with_result(self):
        """Reactive와 Result 통합 테스트"""
        
        def divide_safe(x: int) -> Result[float, str]:
            if x == 0:
                return failure("Division by zero")
            return success(10.0 / x)
        
        # Flux with Result
        results = await (
            Flux.from_iterable([1, 2, 0, 5])
            .map(divide_safe)
            .filter(lambda r: r.is_success())
            .map(lambda r: r.unwrap())
            .to_list()
        )
        
        assert len(results) == 3
        assert 10.0 in results
        assert 5.0 in results
        assert 2.0 in results
    
    @pytest.mark.asyncio
    async def test_event_bus_integration(self):
        """이벤트 버스 통합 테스트"""
        received_events = []
        
        async def event_handler(event: Event):
            received_events.append(event.data)
        
        from rfs.events import get_event_bus
        event_bus = await get_event_bus()
        
        # 핸들러 등록
        subscription_id = event_bus.subscribe(event_handler, ["test_event"])
        
        # 이벤트 발행
        await event_bus.publish(Event(
            event_type="test_event",
            data={"message": "Hello World"},
            source="test"
        ))
        
        # 이벤트 처리 대기
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0]["message"] == "Hello World"
        
        # 구독 해제
        assert event_bus.unsubscribe(subscription_id) is True
    
    @pytest.mark.asyncio
    async def test_saga_integration(self):
        """사가 통합 테스트"""
        
        # 사가 스텝들
        async def step1(data: Dict[str, Any]) -> Dict[str, Any]:
            data["step1_completed"] = True
            return data
        
        async def step2(data: Dict[str, Any]) -> Dict[str, Any]:
            data["step2_completed"] = True
            return data
        
        async def compensate1(data: Dict[str, Any]) -> Dict[str, Any]:
            data["step1_compensated"] = True
            return data
        
        # 사가 생성
        saga = Saga("test_saga", "Test Saga")
        saga.step("step1", step1, compensate1)
        saga.step("step2", step2)
        
        # 사가 실행
        from rfs.events.saga import SagaContext
        context = SagaContext(
            saga_id="test_saga",
            correlation_id="test_correlation",
            data={"initial": True}
        )
        
        result_context = await saga.execute(context)
        
        assert result_context.data["step1_completed"] is True
        assert result_context.data["step2_completed"] is True
        assert saga.status.value == "completed"
    
    @pytest.mark.asyncio
    async def test_stateless_registry(self):
        """스테이트리스 레지스트리 테스트"""
        
        @StatelessRegistry.register("test_service")
        class TestService:
            def __init__(self):
                self.value = 42
            
            def get_value(self) -> int:
                return self.value
        
        # 서비스 조회
        service = StatelessRegistry.get_instance("test_service")
        assert service is not None
        assert service.get_value() == 42
        
        # 싱글톤 확인
        service2 = StatelessRegistry.get_instance("test_service")
        assert service is service2
    
    @pytest.mark.asyncio
    async def test_cloud_run_optimizer(self):
        """Cloud Run 최적화 테스트"""
        from rfs.serverless.cloud_run import CloudRunConfig, CloudRunOptimizer
        
        config = CloudRunConfig(
            cpu="1",
            memory="512Mi",
            enable_cold_start_optimization=True
        )
        
        optimizer = CloudRunOptimizer(config)
        await optimizer.initialize()
        
        # Cold Start 감지 테스트
        @optimizer.cold_start_detector
        async def test_function():
            return "Hello World"
        
        result = await test_function()
        assert result == "Hello World"
        assert optimizer.metrics.request_count == 1
        
        # 헬스 체크
        health = await optimizer.health_check()
        assert health["status"] == "healthy"
        assert health["is_warm"] is True
        
        await optimizer.shutdown()
    
    @pytest.mark.asyncio 
    async def test_functional_state_machine(self):
        """함수형 상태 머신 테스트"""
        from rfs.state_machine.functional import (
            create_state_machine, add_state_to_machine, add_transition_to_machine,
            create_state, create_transition, StateType, TransitionType,
            start_state_machine, add_event_to_queue, process_all_events,
            MachineEvent
        )
        
        # 상태 생성
        initial = create_state("start", StateType.INITIAL)
        middle = create_state("middle", StateType.NORMAL)
        final = create_state("end", StateType.FINAL)
        
        # 전이 생성
        transition1 = create_transition("start", "middle", "next")
        transition2 = create_transition("middle", "end", "finish")
        
        # 상태 머신 빌드
        machine = create_state_machine("test_machine")
        machine = add_state_to_machine(machine, initial)
        machine = add_state_to_machine(machine, middle)
        machine = add_state_to_machine(machine, final)
        machine = add_transition_to_machine(machine, transition1)
        machine = add_transition_to_machine(machine, transition2)
        
        # 상태 머신 시작
        machine = start_state_machine(machine)
        assert machine.current_state == "start"
        
        # 이벤트 처리
        machine = add_event_to_queue(machine, MachineEvent("next"))
        machine = add_event_to_queue(machine, MachineEvent("finish"))
        machine = process_all_events(machine)
        
        assert machine.current_state == "end"
        assert machine.total_transitions == 2
    
    @pytest.mark.asyncio
    async def test_reactive_error_handling(self):
        """Reactive 에러 처리 테스트"""
        
        def risky_operation(x: int) -> int:
            if x == 3:
                raise ValueError("Something went wrong")
            return x * 2
        
        # Flux 에러 처리
        results = await (
            Flux.from_iterable([1, 2, 3, 4, 5])
            .map(risky_operation)
            .on_error_continue(lambda e: print(f"Error: {e}"))
            .to_list()
        )
        
        # 3은 에러로 제외되고 나머지만 처리됨
        assert len(results) == 4
        assert 2 in results  # 1 * 2
        assert 4 in results  # 2 * 2
        assert 8 in results  # 4 * 2
        assert 10 in results  # 5 * 2
    
    def test_result_composition(self):
        """Result 컴포지션 테스트"""
        
        def add_one(x: int) -> Result[int, str]:
            return success(x + 1)
        
        def multiply_two(x: int) -> Result[int, str]:
            return success(x * 2)
        
        def fail_if_ten(x: int) -> Result[int, str]:
            if x == 10:
                return failure("Cannot be 10")
            return success(x)
        
        # 성공 케이스
        result = (success(4)
                 .bind(add_one)  # 5
                 .bind(multiply_two)  # 10
                 .bind(fail_if_ten))  # Failure
        
        assert result.is_failure()
        assert result.unwrap_error() == "Cannot be 10"
        
        # 성공 케이스 2
        result2 = (success(3)
                  .bind(add_one)  # 4
                  .bind(multiply_two)  # 8
                  .bind(fail_if_ten))  # Success
        
        assert result2.is_success()
        assert result2.unwrap() == 8
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """전체 워크플로우 테스트"""
        
        # 1. 데이터 준비
        data_items = [1, 2, 3, 4, 5]
        processed_results = []
        
        # 2. 이벤트 핸들러
        async def process_complete_handler(event: Event):
            processed_results.append(event.data["result"])
        
        # 3. 이벤트 버스 설정
        from rfs.events import get_event_bus
        event_bus = await get_event_bus()
        event_bus.subscribe(process_complete_handler, ["process_complete"])
        
        # 4. Reactive 처리
        def process_item(x: int) -> Result[int, str]:
            if x % 2 == 0:
                return success(x * x)  # 짝수는 제곱
            return success(x * 2)     # 홀수는 2배
        
        results = await (
            Flux.from_iterable(data_items)
            .map(process_item)
            .filter(lambda r: r.is_success())
            .map(lambda r: r.unwrap())
            .to_list()
        )
        
        # 5. 결과를 이벤트로 발행
        for result in results:
            await event_bus.publish(Event(
                event_type="process_complete",
                data={"result": result},
                source="workflow_test"
            ))
        
        # 6. 이벤트 처리 대기
        await asyncio.sleep(0.1)
        
        # 7. 검증
        expected_results = [2, 4, 6, 16, 10]  # [1*2, 2*2, 3*2, 4*4, 5*2]
        assert len(processed_results) == 5
        assert set(processed_results) == set(expected_results)
    
    def test_result_sequence(self):
        """Result 시퀀스 테스트"""
        from rfs.core.result import sequence
        
        # 성공 케이스
        results = [success(1), success(2), success(3)]
        combined = sequence(results)
        
        assert combined.is_success()
        assert combined.unwrap() == [1, 2, 3]
        
        # 실패 케이스
        results_with_failure = [success(1), failure("error"), success(3)]
        combined_fail = sequence(results_with_failure)
        
        assert combined_fail.is_failure()
        assert combined_fail.unwrap_error() == "error"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])