"""
State Machine module

Spring StateMachine 영감을 받은 상태 머신 프레임워크
"""

from .actions import Action, Guard
from .machine import StateMachine, StateMachineBuilder
from .persistence import StatePersistence
from .states import State, StateType
from .transitions import Transition, TransitionBuilder


# 편의 함수들
def create_state_machine(initial_state: State) -> StateMachine:
    """상태 머신 생성 헬퍼 함수"""
    return StateMachineBuilder().initial_state(initial_state).build()


def transition_to(
    from_state: State, to_state: State, trigger: str = None
) -> Transition:
    """상태 전환 생성 헬퍼 함수"""
    builder = TransitionBuilder().from_state(from_state).to_state(to_state)
    if trigger:
        builder = builder.trigger(trigger)
    return builder.build()


__all__ = [
    "State",
    "StateType",
    "Transition",
    "TransitionBuilder",
    "StateMachine",
    "StateMachineBuilder",
    "Action",
    "Guard",
    "StatePersistence",
    "create_state_machine",
    "transition_to",
]
