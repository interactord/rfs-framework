"""
Transition definitions for State Machine

상태 전이 정의 및 관리
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .state import State


class TransitionType(Enum):
    """전이 타입"""

    EXTERNAL = "external"  # 외부 전이 (상태 탈출/진입)
    INTERNAL = "internal"  # 내부 전이 (상태 유지)
    LOCAL = "local"  # 지역 전이 (복합 상태 내부)


@dataclass
class TransitionResult:
    """전이 결과"""

    success: bool
    from_state: str
    to_state: Optional[str]
    event: str
    context: Dict[str, Any] = field(default_factory=dict)
    error = None
    duration_ms: float = 0.0


class Transition:
    """
    상태 전이 클래스

    Spring StateMachine의 Transition 개념을 구현
    """

    def __init__(
        self,
        from_state: "State",
        to_state: "State",
        event: str,
        guard: Optional[Callable[[Dict[str, Any]], bool]] = None,
        action: Optional[Callable[[Dict[str, Any]], None]] = None,
        transition_type: TransitionType = TransitionType.EXTERNAL,
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.event = event
        self.guard = guard
        self.action = action
        self.transition_type = transition_type

        # 통계
        self.execution_count = 0
        self.failure_count = 0
        self.total_duration_ms = 0.0

    async def can_execute(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """전이 실행 가능 여부 확인 (Guard 조건)"""
        if not self.guard:
            return True

        try:
            if context is None:
                context = {}

            # Guard가 비동기 함수인지 확인
            if asyncio.iscoroutinefunction(self.guard):
                return await self.guard(context)
            else:
                return self.guard(context)

        except Exception as e:
            print(
                f"Guard execution failed for transition {self.from_state.name} -> {self.to_state.name}: {e}"
            )
            return False

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> TransitionResult:
        """전이 실행"""
        import time

        start_time = time.time()

        if context is None:
            context = {}

        try:
            # Guard 조건 확인
            if not await self.can_execute(context):
                return TransitionResult(
                    success=False,
                    from_state=self.from_state.name,
                    to_state=self.to_state.name,
                    event=self.event,
                    context=context,
                    error=Exception("Guard condition failed"),
                )

            # 외부 전이인 경우 상태 탈출
            if self.transition_type == TransitionType.EXTERNAL:
                await self.from_state.exit(context)

            # 전이 액션 실행
            if self.action:
                await self._execute_action(self.action, context)

            # 외부 전이인 경우 상태 진입
            if self.transition_type == TransitionType.EXTERNAL:
                await self.to_state.enter(context)

            # 성공 통계 업데이트
            execution_count = execution_count + 1
            duration_ms = (time.time() - start_time) * 1000
            total_duration_ms = total_duration_ms + duration_ms

            return TransitionResult(
                success=True,
                from_state=self.from_state.name,
                to_state=self.to_state.name,
                event=self.event,
                context=context,
                duration_ms=duration_ms,
            )

        except Exception as e:
            # 실패 통계 업데이트
            failure_count = failure_count + 1
            duration_ms = (time.time() - start_time) * 1000

            return TransitionResult(
                success=False,
                from_state=self.from_state.name,
                to_state=self.to_state.name,
                event=self.event,
                context=context,
                error=e,
                duration_ms=duration_ms,
            )

    async def _execute_action(self, action, context: Dict[str, Any]):
        """액션 실행"""
        try:
            # 비동기 함수인지 확인
            if asyncio.iscoroutinefunction(action):
                await action(context)
            else:
                action(context)

        except Exception as e:
            print(
                f"Action execution failed for transition {self.from_state.name} -> {self.to_state.name}: {e}"
            )
            raise

    def get_stats(self) -> Dict[str, Any]:
        """전이 통계"""
        return {
            "from_state": self.from_state.name,
            "to_state": self.to_state.name,
            "event": self.event,
            "type": self.transition_type.value,
            "execution_count": self.execution_count,
            "failure_count": self.failure_count,
            "success_rate": (self.execution_count - self.failure_count)
            / max(self.execution_count, 1),
            "average_duration_ms": self.total_duration_ms
            / max(self.execution_count, 1),
        }

    def __str__(self) -> str:
        return (
            f"Transition({self.from_state.name} --{self.event}--> {self.to_state.name})"
        )

    def __repr__(self) -> str:
        return self.__str__()


class TransitionBuilder:
    """전이 빌더 (플루언트 인터페이스)"""

    def __init__(self):
        self.from_state = None
        self.to_state = None
        self.event = None
        self.guard = None
        self.action = None
        self.transition_type = TransitionType.EXTERNAL

    def source(self, state: "State") -> "TransitionBuilder":
        """출발 상태 설정"""
        self.from_state = state
        return self

    def target(self, state: "State") -> "TransitionBuilder":
        """도착 상태 설정"""
        self.to_state = state
        return self

    def event(self, event_name: str) -> "TransitionBuilder":
        """이벤트 설정"""
        self.event = event_name
        return self

    def guard(
        self, guard_func: Callable[[Dict[str, Any]], bool]
    ) -> "TransitionBuilder":
        """가드 조건 설정"""
        self.guard = guard_func
        return self

    def action(
        self, action_func: Callable[[Dict[str, Any]], None]
    ) -> "TransitionBuilder":
        """액션 설정"""
        self.action = action_func
        return self

    def internal(self) -> "TransitionBuilder":
        """내부 전이로 설정"""
        self.transition_type = TransitionType.INTERNAL
        return self

    def external(self) -> "TransitionBuilder":
        """외부 전이로 설정"""
        self.transition_type = TransitionType.EXTERNAL
        return self

    def local(self) -> "TransitionBuilder":
        """지역 전이로 설정"""
        self.transition_type = TransitionType.LOCAL
        return self

    def build(self) -> Transition:
        """전이 생성"""
        if not all([self.from_state, self.to_state, self.event]):
            raise ValueError("From state, to state, and event must be specified")

        return Transition(
            from_state=self.from_state,
            to_state=self.to_state,
            event=self.event,
            guard=self.guard,
            action=self.action,
            transition_type=self.transition_type,
        )


# 편의 함수들
def transition() -> TransitionBuilder:
    """전이 빌더 생성"""
    return TransitionBuilder()


def external_transition() -> TransitionBuilder:
    """외부 전이 빌더 생성"""
    return TransitionBuilder().external()


def internal_transition() -> TransitionBuilder:
    """내부 전이 빌더 생성"""
    return TransitionBuilder().internal()


def local_transition() -> TransitionBuilder:
    """지역 전이 빌더 생성"""
    return TransitionBuilder().local()
