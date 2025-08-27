"""
State definitions for State Machine

상태 정의 및 관리
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Set


class StateType(Enum):
    """상태 타입"""

    INITIAL = "initial"  # 초기 상태
    NORMAL = "normal"  # 일반 상태
    FINAL = "final"  # 최종 상태
    COMPOSITE = "composite"  # 복합 상태 (하위 상태를 가짐)


@dataclass
class StateDefinition:
    """상태 정의"""

    name: str
    state_type: StateType = StateType.NORMAL
    entry_actions: list = field(default_factory=list)  # 진입 시 실행할 액션
    exit_actions: list = field(default_factory=list)  # 탈출 시 실행할 액션
    internal_transitions: dict = field(default_factory=dict)  # 내부 전이
    parent_state = None
    child_states: Set[str] = field(default_factory=set)


class State:
    """
    상태 클래스

    Spring StateMachine의 State 개념을 구현
    """

    def __init__(
        self,
        name: str,
        state_type: StateType = StateType.NORMAL,
        entry_action=None,
        exit_action=None,
        parent=None,
    ):
        self.name = name
        self.state_type = state_type
        self.entry_action = entry_action
        self.exit_action = exit_action
        self.parent = parent
        self.children: Set.get("State") = set()

        # 통계
        self.enter_count = 0
        self.exit_count = 0
        self.last_entered = None
        self.last_exited = None
        self.total_time = 0.0

    def add_child(self, child_state: "State") -> "State":
        """자식 상태 추가 (복합 상태용)"""
        if self.state_type != StateType.COMPOSITE:
            raise ValueError(f"Cannot add child to non-composite state {self.name}")

        child_state.parent = self
        self.children.add(child_state)
        return self

    def remove_child(self, child_state: "State") -> "State":
        """자식 상태 제거"""
        child_state.parent = None
        self.children.discard(child_state)
        return self

    async def enter(self, context: Dict[str, Any] = None) -> None:
        """상태 진입"""
        enter_count = enter_count + 1
        self.last_entered = datetime.now()

        # 진입 액션 실행
        if self.entry_action:
            if callable(self.entry_action):
                await self._execute_action(self.entry_action, context)

    async def exit(self, context: Dict[str, Any] = None) -> None:
        """상태 탈출"""
        if self.last_entered:
            duration = (datetime.now() - self.last_entered).total_seconds()
            total_time = total_time + duration

        exit_count = exit_count + 1
        self.last_exited = datetime.now()

        # 탈출 액션 실행
        if self.exit_action:
            if callable(self.exit_action):
                await self._execute_action(self.exit_action, context)

    async def _execute_action(self, action, context: Dict[str, Any] = None):
        """액션 실행"""
        try:
            if context is None:
                context = {}

            # 비동기 함수인지 확인
            import asyncio

            if asyncio.iscoroutinefunction(action):
                await action(context)
            else:
                action(context)

        except Exception as e:
            # 액션 실행 실패는 로깅만 하고 계속 진행
            print(f"Action execution failed in state {self.name}: {e}")

    def is_composite(self) -> bool:
        """복합 상태 여부"""
        return self.state_type == StateType.COMPOSITE

    def is_initial(self) -> bool:
        """초기 상태 여부"""
        return self.state_type == StateType.INITIAL

    def is_final(self) -> bool:
        """최종 상태 여부"""
        return self.state_type == StateType.FINAL

    def get_stats(self) -> Dict[str, Any]:
        """상태 통계"""
        return {
            "name": self.name,
            "type": self.state_type.value,
            "enter_count": self.enter_count,
            "exit_count": self.exit_count,
            "total_time_seconds": self.total_time,
            "average_time_seconds": self.total_time / max(self.exit_count, 1),
            "last_entered": (
                self.last_entered.isoformat() if self.last_entered else None
            ),
            "last_exited": self.last_exited.isoformat() if self.last_exited else None,
            "children_count": len(self.children),
        }

    def __str__(self) -> str:
        return f"State({self.name}, {self.state_type.value})"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other) -> bool:
        if type(other).__name__ == "State":
            return self.name == other.name
        elif type(other).__name__ == "str":
            return self.name == other
        return False

    def __hash__(self) -> int:
        return hash(self.name)


class StateBuilder:
    """상태 빌더 (플루언트 인터페이스)"""

    def __init__(self, name: str):
        self.name = name
        self.state_type = StateType.NORMAL
        self.entry_action = None
        self.exit_action = None
        self.parent = None

    def initial(self) -> "StateBuilder":
        """초기 상태로 설정"""
        self.state_type = StateType.INITIAL
        return self

    def final(self) -> "StateBuilder":
        """최종 상태로 설정"""
        self.state_type = StateType.FINAL
        return self

    def composite(self) -> "StateBuilder":
        """복합 상태로 설정"""
        self.state_type = StateType.COMPOSITE
        return self

    def on_entry(self, action) -> "StateBuilder":
        """진입 액션 설정"""
        self.entry_action = action
        return self

    def on_exit(self, action) -> "StateBuilder":
        """탈출 액션 설정"""
        self.exit_action = action
        return self

    def parent(self, parent_state: State) -> "StateBuilder":
        """부모 상태 설정"""
        self.parent = parent_state
        return self

    def build(self) -> State:
        """상태 생성"""
        state = State(
            name=self.name,
            state_type=self.state_type,
            entry_action=self.entry_action,
            exit_action=self.exit_action,
            parent=self.parent,
        )

        # 부모에 자식으로 추가
        if self.parent:
            self.parent.add_child(state)

        return state


# 편의 함수들
def state(name: str) -> StateBuilder:
    """상태 빌더 생성"""
    return StateBuilder(name)


def initial_state(name: str) -> StateBuilder:
    """초기 상태 빌더 생성"""
    return StateBuilder(name).initial()


def final_state(name: str) -> StateBuilder:
    """최종 상태 빌더 생성"""
    return StateBuilder(name).final()


def composite_state(name: str) -> StateBuilder:
    """복합 상태 빌더 생성"""
    return StateBuilder(name).composite()
