"""
Functional State Machine Implementation

함수형 상태 머신 구현 - 클래스 기반 설계를 순수 함수로 변환
"""

import asyncio
import copy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Union

from rfs.core.result import Failure, Result, Success

from ..hof.collections import fold_left

# Import from HOF library
from ..hof.core import compose, partial


class StateType(Enum):
    INITIAL = "initial"
    NORMAL = "normal"
    FINAL = "final"
    COMPOSITE = "composite"


class MachineState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class TransitionType(Enum):
    EXTERNAL = "external"
    INTERNAL = "internal"
    LOCAL = "local"


@dataclass(frozen=True)
class State:
    """불변 상태"""

    name: str
    state_type: StateType = StateType.NORMAL
    entry_action: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    exit_action: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    parent = None
    children: frozenset = field(default_factory=frozenset)
    enter_count = 0
    exit_count = 0
    total_time: float = 0.0
    last_entered = None
    last_exited = None


@dataclass(frozen=True)
class Transition:
    """불변 전이"""

    from_state: str
    to_state: str
    event: str
    guard: Optional[Callable[[Dict[str, Any]], bool]] = None
    action: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    transition_type: TransitionType = TransitionType.EXTERNAL
    execution_count = 0
    failure_count = 0
    total_duration_ms: float = 0.0


@dataclass(frozen=True)
class MachineEvent:
    """불변 이벤트"""

    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class StateMachineState:
    """불변 상태 머신 상태"""

    name: str
    states: Dict[str, State] = field(default_factory=dict)
    transitions: Dict[str, List[Transition]] = field(default_factory=dict)
    current_state = None
    initial_state = None
    machine_state: MachineState = MachineState.IDLE
    context: Dict[str, Any] = field(default_factory=dict)
    event_queue: Tuple[MachineEvent, ...] = field(default_factory=tuple)
    event_history: Tuple[MachineEvent, ...] = field(default_factory=tuple)
    total_transitions = 0
    failed_transitions = 0
    start_time = None


def create_state(
    name: str,
    state_type: StateType = StateType.NORMAL,
    entry_action=None,
    exit_action=None,
) -> State:
    """순수 함수: 상태 생성"""
    return State(
        name=name,
        state_type=state_type,
        entry_action=entry_action,
        exit_action=exit_action,
    )


def is_initial_state(state: State) -> bool:
    """순수 함수: 초기 상태 확인"""
    return state.state_type == StateType.INITIAL


def is_final_state(state: State) -> bool:
    """순수 함수: 최종 상태 확인"""
    return state.state_type == StateType.FINAL


def is_composite_state(state: State) -> bool:
    """순수 함수: 복합 상태 확인"""
    return state.state_type == StateType.COMPOSITE


def update_state_stats(
    state: State,
    enter_count: int = None,
    exit_count: int = None,
    total_time: float = None,
) -> State:
    """순수 함수: 상태 통계 업데이트"""
    return State(
        name=state.name,
        state_type=state.state_type,
        entry_action=state.entry_action,
        exit_action=state.exit_action,
        parent=state.parent,
        children=state.children,
        enter_count=enter_count if enter_count is not None else state.enter_count,
        exit_count=exit_count if exit_count is not None else state.exit_count,
        total_time=total_time if total_time is not None else state.total_time,
        last_entered=datetime.now() if enter_count is not None else state.last_entered,
        last_exited=datetime.now() if exit_count is not None else state.last_exited,
    )


def create_transition(
    from_state: str,
    to_state: str,
    event: str,
    guard=None,
    action=None,
    transition_type: TransitionType = TransitionType.EXTERNAL,
) -> Transition:
    """순수 함수: 전이 생성"""
    return Transition(
        from_state=from_state,
        to_state=to_state,
        event=event,
        guard=guard,
        action=action,
        transition_type=transition_type,
    )


def can_execute_transition(transition: Transition, context: Dict[str, Any]) -> bool:
    """순수 함수: 전이 실행 가능 여부"""
    if not transition.guard:
        return True
        return transition.guard(context)
        return Failure("Operation failed")


def update_transition_stats(
    transition: Transition,
    execution_count: int = None,
    failure_count: int = None,
    duration_ms: float = None,
) -> Transition:
    """순수 함수: 전이 통계 업데이트"""
    return Transition(
        from_state=transition.from_state,
        to_state=transition.to_state,
        event=transition.event,
        guard=transition.guard,
        action=transition.action,
        transition_type=transition.transition_type,
        execution_count=(
            execution_count
            if execution_count is not None
            else transition.execution_count
        ),
        failure_count=(
            failure_count if failure_count is not None else transition.failure_count
        ),
        total_duration_ms=(
            transition.total_duration_ms + duration_ms
            if duration_ms is not None
            else transition.total_duration_ms
        ),
    )


def create_state_machine(name: str) -> StateMachineState:
    """순수 함수: 상태 머신 생성"""
    return StateMachineState(name=name)


def add_state_to_machine(machine: StateMachineState, state: State) -> StateMachineState:
    """순수 함수: 상태 머신에 상태 추가"""
    new_states = {**machine.states, state.name: state}
    new_initial_state = machine.initial_state
    if is_initial_state(state) and (not machine.initial_state):
        new_initial_state = state.name
    return StateMachineState(
        name=machine.name,
        states=new_states,
        transitions=machine.transitions,
        current_state=machine.current_state,
        initial_state=new_initial_state,
        machine_state=machine.machine_state,
        context=machine.context,
        event_queue=machine.event_queue,
        event_history=machine.event_history,
        total_transitions=machine.total_transitions,
        failed_transitions=machine.failed_transitions,
        start_time=machine.start_time,
    )


def add_transition_to_machine(
    machine: StateMachineState, transition: Transition
) -> StateMachineState:
    """순수 함수: 상태 머신에 전이 추가"""
    key = f"{transition.from_state}:{transition.event}"
    new_transitions = copy.deepcopy(machine.transitions)
    if key not in new_transitions:
        new_transitions[key] = {key: []}
    new_transitions[key] = new_transitions[key] + [transition]
    return StateMachineState(
        name=machine.name,
        states=machine.states,
        transitions=new_transitions,
        current_state=machine.current_state,
        initial_state=machine.initial_state,
        machine_state=machine.machine_state,
        context=machine.context,
        event_queue=machine.event_queue,
        event_history=machine.event_history,
        total_transitions=machine.total_transitions,
        failed_transitions=machine.failed_transitions,
        start_time=machine.start_time,
    )


def start_state_machine(machine: StateMachineState) -> StateMachineState:
    """순수 함수: 상태 머신 시작"""
    if machine.machine_state != MachineState.IDLE or not machine.initial_state:
        return machine
    return StateMachineState(
        name=machine.name,
        states=machine.states,
        transitions=machine.transitions,
        current_state=machine.initial_state,
        initial_state=machine.initial_state,
        machine_state=MachineState.RUNNING,
        context=machine.context,
        event_queue=machine.event_queue,
        event_history=machine.event_history,
        total_transitions=machine.total_transitions,
        failed_transitions=machine.failed_transitions,
        start_time=datetime.now(),
    )


def stop_state_machine(machine: StateMachineState) -> StateMachineState:
    """순수 함수: 상태 머신 정지"""
    if machine.machine_state != MachineState.RUNNING:
        return machine
    return StateMachineState(
        name=machine.name,
        states=machine.states,
        transitions=machine.transitions,
        current_state=machine.current_state,
        initial_state=machine.initial_state,
        machine_state=MachineState.STOPPED,
        context=machine.context,
        event_queue=machine.event_queue,
        event_history=machine.event_history,
        total_transitions=machine.total_transitions,
        failed_transitions=machine.failed_transitions,
        start_time=machine.start_time,
    )


def add_event_to_queue(
    machine: StateMachineState, event: MachineEvent
) -> StateMachineState:
    """순수 함수: 이벤트 큐에 이벤트 추가"""
    if machine.machine_state != MachineState.RUNNING:
        return machine
    new_event_queue = machine.event_queue + (event,)
    new_event_history = machine.event_history + (event,)
    if len(new_event_history) > 100:
        new_event_history = new_event_history[-50:]
    return StateMachineState(
        name=machine.name,
        states=machine.states,
        transitions=machine.transitions,
        current_state=machine.current_state,
        initial_state=machine.initial_state,
        machine_state=machine.machine_state,
        context=machine.context,
        event_queue=new_event_queue,
        event_history=new_event_history,
        total_transitions=machine.total_transitions,
        failed_transitions=machine.failed_transitions,
        start_time=machine.start_time,
    )


def process_next_event(machine: StateMachineState) -> StateMachineState:
    """순수 함수: 다음 이벤트 처리"""
    if not machine.event_queue or not machine.current_state:
        return machine
    event = machine.event_queue[0]
    remaining_queue = machine.event_queue[1:]
    key = f"{machine.current_state}:{event.name}"
    transitions = machine.transitions.get(key, [])
    event_context = {**machine.context, **event.data}
    executable_transition = None
    for transition in transitions:
        if can_execute_transition(transition, event_context):
            executable_transition = transition
            break
    if not executable_transition:
        return StateMachineState(
            name=machine.name,
            states=machine.states,
            transitions=machine.transitions,
            current_state=machine.current_state,
            initial_state=machine.initial_state,
            machine_state=machine.machine_state,
            context=machine.context,
            event_queue=remaining_queue,
            event_history=machine.event_history,
            total_transitions=machine.total_transitions,
            failed_transitions=machine.failed_transitions + 1,
            start_time=machine.start_time,
        )
    new_context = event_context
    if executable_transition.action:
        try:
            action_result = executable_transition.action(new_context)
            if type(action_result).__name__ == "dict":
                new_context = {**new_context, **action_result}
        except:
            pass
    new_current_state = machine.current_state
    if executable_transition.transition_type == TransitionType.EXTERNAL:
        new_current_state = executable_transition.to_state
    return StateMachineState(
        name=machine.name,
        states=machine.states,
        transitions=machine.transitions,
        current_state=new_current_state,
        initial_state=machine.initial_state,
        machine_state=machine.machine_state,
        context=new_context,
        event_queue=remaining_queue,
        event_history=machine.event_history,
        total_transitions=machine.total_transitions + 1,
        failed_transitions=machine.failed_transitions,
        start_time=machine.start_time,
    )


def process_all_events(machine: StateMachineState) -> StateMachineState:
    """순수 함수: 모든 이벤트 처리"""
    current_machine = machine
    while (
        current_machine.event_queue
        and current_machine.machine_state == MachineState.RUNNING
    ):
        current_machine = process_next_event(current_machine)
    return current_machine


def is_in_state(machine: StateMachineState, state_name: str) -> bool:
    """순수 함수: 특정 상태에 있는지 확인"""
    return machine.current_state == state_name


def can_fire_event(machine: StateMachineState, event_name: str) -> bool:
    """순수 함수: 이벤트 발생 가능 여부"""
    if not machine.current_state:
        return False
    key = f"{machine.current_state}:{event_name}"
    return key in machine.transitions


def get_machine_stats(machine: StateMachineState) -> Dict[str, Any]:
    """순수 함수: 상태 머신 통계"""
    uptime = 0.0
    if machine.start_time:
        uptime = (datetime.now() - machine.start_time).total_seconds()
    return {
        "name": machine.name,
        "machine_state": machine.machine_state.value,
        "current_state": machine.current_state,
        "total_states": len(machine.states),
        "total_transitions_defined": sum(
            (len(trans) for trans in machine.transitions.values())
        ),
        "total_transitions_executed": machine.total_transitions,
        "failed_transitions": machine.failed_transitions,
        "success_rate": (machine.total_transitions - machine.failed_transitions)
        / max(machine.total_transitions, 1),
        "uptime_seconds": uptime,
        "events_in_queue": len(machine.event_queue),
        "events_in_history": len(machine.event_history),
    }


def map_states(
    machine: StateMachineState, mapper: Callable[[State], State]
) -> StateMachineState:
    """고차 함수: 모든 상태에 함수 적용"""
    new_states = {name: mapper(state) for name, state in machine.states.items()}
    return StateMachineState(
        name=machine.name,
        states=new_states,
        transitions=machine.transitions,
        current_state=machine.current_state,
        initial_state=machine.initial_state,
        machine_state=machine.machine_state,
        context=machine.context,
        event_queue=machine.event_queue,
        event_history=machine.event_history,
        total_transitions=machine.total_transitions,
        failed_transitions=machine.failed_transitions,
        start_time=machine.start_time,
    )


def filter_transitions(
    machine: StateMachineState, predicate: Callable[[Transition], bool]
) -> StateMachineState:
    """고차 함수: 전이 필터링"""
    new_transitions = {}
    for key, transitions in machine.transitions.items():
        filtered = [t for t in transitions if predicate(t)]
        if filtered:
            new_transitions[key] = {key: filtered}
    return StateMachineState(
        name=machine.name,
        states=machine.states,
        transitions=new_transitions,
        current_state=machine.current_state,
        initial_state=machine.initial_state,
        machine_state=machine.machine_state,
        context=machine.context,
        event_queue=machine.event_queue,
        event_history=machine.event_history,
        total_transitions=machine.total_transitions,
        failed_transitions=machine.failed_transitions,
        start_time=machine.start_time,
    )


def fold_events(
    machine: StateMachineState, folder: Callable[[Any, MachineEvent], Any], initial: Any
) -> Any:
    """고차 함수: 이벤트 히스토리 폴드"""
    return fold_left(folder, initial, machine.event_history)


def build_state_machine(name: str) -> Callable:
    """함수형 상태 머신 빌더"""

    def builder(machine=None):
        if machine is None:
            machine = create_state_machine(name)

        def with_state(state: State):
            return builder(add_state_to_machine(machine, state))

        def with_transition(transition: Transition):
            return builder(add_transition_to_machine(machine, transition))

        def with_states(*states: State):
            new_machine = machine
            for state in states:
                new_machine = add_state_to_machine(new_machine, state)
            return builder(new_machine)

        def with_transitions(*transitions: Transition):
            new_machine = machine
            for transition in transitions:
                new_machine = add_transition_to_machine(new_machine, transition)
            return builder(new_machine)

        def build():
            return machine

        builder.with_state = with_state
        builder.with_transition = with_transition
        builder.with_states = with_states
        builder.with_transitions = with_transitions
        builder.build = build
        return builder

    return builder()


def initial_state(name: str) -> State:
    """초기 상태 생성"""
    return create_state(name, StateType.INITIAL)


def final_state(name: str) -> State:
    """최종 상태 생성"""
    return create_state(name, StateType.FINAL)


def normal_state(name: str) -> State:
    """일반 상태 생성"""
    return create_state(name, StateType.NORMAL)


def composite_state(name: str) -> State:
    """복합 상태 생성"""
    return create_state(name, StateType.COMPOSITE)
