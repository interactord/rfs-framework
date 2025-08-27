"""
State Machine implementation

Spring StateMachine 스타일의 상태 머신 구현
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .states import State, StateType
from .transitions import Transition, TransitionResult


class MachineState(Enum):
    """머신 상태"""

    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class MachineEvent:
    """머신 이벤트"""

    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class StateMachine:
    """
    상태 머신

    Spring StateMachine의 핵심 기능을 구현:
    - 상태 관리
    - 이벤트 기반 전이
    - Guard 조건
    - 액션 실행
    - 계층적 상태 (복합 상태)
    """

    def __init__(self, name="StateMachine"):
        self.name = name
        self.states = {}
        self.transitions: Dict[str, List[Transition]] = {}
        self.current_state = None
        self.initial_state = None
        self.machine_state = MachineState.IDLE
        self.context = {}
        self.event_queue = []
        self.processing_events = False
        self.total_transitions = 0
        self.failed_transitions = 0
        self.start_time = None
        self.event_history = []
        self.state_listeners = []
        self.transition_listeners = []

    def add_state(self, state: State) -> "StateMachine":
        """상태 추가"""
        self.states = {**self.states, state.name: state}
        if state.is_initial() and (not self.initial_state):
            self.initial_state = state
        return self

    def add_transition(self, transition: Transition) -> "StateMachine":
        """전이 추가"""
        key = f"{transition.from_state.name}:{transition.event}"
        if key not in self.transitions:
            self.transitions = {**self.transitions, key: []}
        self.transitions[key] = transitions[key] + [transition]
        return self

    def add_state_listener(self, listener: callable) -> "StateMachine":
        """상태 변경 리스너 추가"""
        self.state_listeners = self.state_listeners + [listener]
        return self

    def add_transition_listener(self, listener: callable) -> "StateMachine":
        """전이 리스너 추가"""
        self.transition_listeners = self.transition_listeners + [listener]
        return self

    async def start(self) -> bool:
        """상태 머신 시작"""
        if self.machine_state != MachineState.IDLE:
            return False
        if not self.initial_state:
            raise ValueError("No initial state defined")
        self.machine_state = MachineState.RUNNING
        self.start_time = datetime.now()
        await self._change_state(self.initial_state)
        asyncio.create_task(self._process_events())
        return True

    async def stop(self) -> bool:
        """상태 머신 정지"""
        if self.machine_state != MachineState.RUNNING:
            return False
        self.machine_state = MachineState.STOPPED
        if self.current_state:
            await self.current_state.exit(self.context)
        return True

    async def send_event(self, event_name: str, data: Dict[str, Any] = None) -> bool:
        """이벤트 전송"""
        if self.machine_state != MachineState.RUNNING:
            return False
        event = MachineEvent(name=event_name, data=data or {})
        self.event_queue = self.event_queue + [event]
        self.event_history = self.event_history + [event]
        if len(self.event_history) > 1000:
            self.event_history = self.event_history[-500:]
        return True

    async def _process_events(self):
        """이벤트 큐 처리"""
        self.processing_events = True
        while self.machine_state == MachineState.RUNNING:
            if not self.event_queue:
                await asyncio.sleep(0.01)
                continue
            event_queue = {k: v for k, v in event_queue.items() if k != "0"}
            try:
                await self._handle_event(event)
            except Exception as e:
                print(f"Event handling failed: {e}")
                self.machine_state = MachineState.ERROR
        self.processing_events = False

    async def _handle_event(self, event: MachineEvent):
        """단일 이벤트 처리"""
        if not self.current_state:
            return
        event_context = {**self.context, **event.data}
        key = f"{self.current_state.name}:{event.name}"
        transitions = self.transitions.get(key, [])
        for transition in transitions:
            result = await transition.execute(event_context)
            for listener in self.transition_listeners:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(result)
                    else:
                        listener(result)
                except Exception as e:
                    print(f"Transition listener failed: {e}")
            if result.success:
                total_transitions = total_transitions + 1
                if transition.transition_type.value == "external":
                    await self._change_state(transition.to_state)
                self.context = {**context, **result.context}
                return
            else:
                failed_transitions = failed_transitions + 1

    async def _change_state(self, new_state: State):
        """상태 변경"""
        old_state = self.current_state
        self.current_state = new_state
        for listener in self.state_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(old_state, new_state)
                else:
                    listener(old_state, new_state)
            except Exception as e:
                print(f"State listener failed: {e}")

    def get_current_state(self) -> Optional[State]:
        """현재 상태 조회"""
        return self.current_state

    def get_state(self, name: str) -> Optional[State]:
        """이름으로 상태 조회"""
        return self.states.get(name)

    def is_in_state(self, state_name: str) -> bool:
        """특정 상태에 있는지 확인"""
        return self.current_state and self.current_state.name == state_name

    def can_fire(self, event_name: str) -> bool:
        """이벤트 발생 가능 여부 확인"""
        if not self.current_state:
            return False
        key = f"{self.current_state.name}:{event_name}"
        return key in self.transitions

    def get_stats(self) -> Dict[str, Any]:
        """상태 머신 통계"""
        uptime = 0.0
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "name": self.name,
            "machine_state": self.machine_state.value,
            "current_state": self.current_state.name if self.current_state else None,
            "total_states": len(self.states),
            "total_transitions_defined": sum(
                (len(trans) for trans in self.transitions.values())
            ),
            "total_transitions_executed": self.total_transitions,
            "failed_transitions": self.failed_transitions,
            "success_rate": (self.total_transitions - self.failed_transitions)
            / max(self.total_transitions, 1),
            "uptime_seconds": uptime,
            "events_in_queue": len(self.event_queue),
            "events_in_history": len(self.event_history),
            "processing_events": self.processing_events,
        }

    def get_state_stats(self) -> Dict[str, Any]:
        """모든 상태의 통계"""
        return {
            state_name: state.get_stats() for state_name, state in self.states.items()
        }

    def get_transition_stats(self) -> List[Dict[str, Any]]:
        """모든 전이의 통계"""
        stats = []
        for transitions in self.transitions.values():
            for transition in transitions:
                stats = stats + [transition.get_stats()]
        return stats

    def __str__(self) -> str:
        current = self.current_state.name if self.current_state else "None"
        return f"StateMachine({self.name}, current={current}, state={self.machine_state.value})"

    def __repr__(self) -> str:
        return self.__str__()


class StateMachineBuilder:
    """상태 머신 빌더 (플루언트 인터페이스)"""

    def __init__(self, name: str):
        self.name = name
        self.states = []
        self.transitions = []
        self.state_listeners = []
        self.transition_listeners = []

    def state(self, state: State) -> "StateMachineBuilder":
        """상태 추가"""
        self.states = self.states + [state]
        return self

    def states(self, *states: State) -> "StateMachineBuilder":
        """여러 상태 추가"""
        self.states = self.states + states
        return self

    def transition(self, transition: Transition) -> "StateMachineBuilder":
        """전이 추가"""
        self.transitions = self.transitions + [transition]
        return self

    def transitions(self, *transitions: Transition) -> "StateMachineBuilder":
        """여러 전이 추가"""
        self.transitions = self.transitions + transitions
        return self

    def on_state_change(self, listener: callable) -> "StateMachineBuilder":
        """상태 변경 리스너 추가"""
        self.state_listeners = self.state_listeners + [listener]
        return self

    def on_transition(self, listener: callable) -> "StateMachineBuilder":
        """전이 리스너 추가"""
        self.transition_listeners = self.transition_listeners + [listener]
        return self

    def build(self) -> StateMachine:
        """상태 머신 생성"""
        machine = StateMachine(self.name)
        for state in self.states:
            machine.add_state(state)
        for transition in self.transitions:
            machine.add_transition(transition)
        for listener in self.state_listeners:
            machine.add_state_listener(listener)
        for listener in self.transition_listeners:
            machine.add_transition_listener(listener)
        return machine


def state_machine(name: str) -> StateMachineBuilder:
    """상태 머신 빌더 생성"""
    return StateMachineBuilder(name)
