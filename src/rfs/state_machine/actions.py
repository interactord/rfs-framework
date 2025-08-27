"""
Action definitions for State Machine

상태 머신 액션 정의 및 관리
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ActionType(Enum):
    """액션 타입"""

    ENTRY = "entry"  # 상태 진입 액션
    EXIT = "exit"  # 상태 탈출 액션
    TRANSITION = "transition"  # 전이 액션
    GUARD = "guard"  # 가드 액션


@dataclass
class ActionResult:
    """액션 실행 결과"""

    success: bool
    action_type: ActionType
    action_name: str
    context_changes: Dict[str, Any] = field(default_factory=dict)
    error = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class Action:
    """
    상태 머신 액션 클래스

    Spring StateMachine의 Action 개념을 구현
    """

    def __init__(
        self,
        name: str,
        action_type: ActionType,
        action_func: Callable[[Dict[str, Any]], Any],
        async_action=False,
    ):
        self.name = name
        self.action_type = action_type
        self.action_func = action_func
        self.async_action = async_action

        # 통계
        self.execution_count = 0
        self.failure_count = 0
        self.total_duration_ms = 0.0
        self.last_executed = None

    async def execute(self, context: Dict[str, Any] = None) -> ActionResult:
        """액션 실행"""
        import time

        start_time = time.time()

        if context is None:
            context = {}

        try:
            self.last_executed = datetime.now()

            # 액션 실행
            if self.async_action:
                if asyncio.iscoroutinefunction(self.action_func):
                    result = await self.action_func(context)
                else:
                    result = self.action_func(context)
            else:
                if asyncio.iscoroutinefunction(self.action_func):
                    result = await self.action_func(context)
                else:
                    result = self.action_func(context)

            # 성공 통계 업데이트
            execution_count = execution_count + 1
            duration_ms = (time.time() - start_time) * 1000
            total_duration_ms = total_duration_ms + duration_ms

            # 컨텍스트 변경사항 추출
            context_changes = {}
            if type(result).__name__ == "dict":
                context_changes = result

            return ActionResult(
                success=True,
                action_type=self.action_type,
                action_name=self.name,
                context_changes=context_changes,
                duration_ms=duration_ms,
            )

        except Exception as e:
            # 실패 통계 업데이트
            failure_count = failure_count + 1
            duration_ms = (time.time() - start_time) * 1000

            return ActionResult(
                success=False,
                action_type=self.action_type,
                action_name=self.name,
                error=e,
                duration_ms=duration_ms,
            )

    def get_stats(self) -> Dict[str, Any]:
        """액션 통계"""
        return {
            "name": self.name,
            "type": self.action_type.value,
            "execution_count": self.execution_count,
            "failure_count": self.failure_count,
            "success_rate": (self.execution_count - self.failure_count)
            / max(self.execution_count, 1),
            "average_duration_ms": self.total_duration_ms
            / max(self.execution_count, 1),
            "last_executed": (
                self.last_executed.isoformat() if self.last_executed else None
            ),
        }

    def __str__(self) -> str:
        return f"Action({self.name}, {self.action_type.value})"

    def __repr__(self) -> str:
        return self.__str__()


class Guard:
    """
    상태 머신 가드 조건 클래스

    Spring StateMachine의 Guard 개념을 구현
    """

    def __init__(
        self,
        name: str,
        guard_func: Callable[[Dict[str, Any]], bool],
        description="",
    ):
        self.name = name
        self.guard_func = guard_func
        self.description = description

        # 통계
        self.evaluation_count = 0
        self.true_count = 0
        self.false_count = 0
        self.error_count = 0
        self.total_duration_ms = 0.0

    async def evaluate(self, context: Dict[str, Any] = None) -> bool:
        """가드 조건 평가"""
        import time

        start_time = time.time()

        if context is None:
            context = {}

        try:
            evaluation_count = evaluation_count + 1

            # 가드 함수 실행
            if asyncio.iscoroutinefunction(self.guard_func):
                result = await self.guard_func(context)
            else:
                result = self.guard_func(context)

            # 결과 통계 업데이트
            if result:
                true_count = true_count + 1
            else:
                false_count = false_count + 1

            duration_ms = (time.time() - start_time) * 1000
            total_duration_ms = total_duration_ms + duration_ms

            return bool(result)

        except Exception as e:
            error_count = error_count + 1
            print(f"Guard evaluation failed for {self.name}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """가드 통계"""
        return {
            "name": self.name,
            "description": self.description,
            "evaluation_count": self.evaluation_count,
            "true_count": self.true_count,
            "false_count": self.false_count,
            "error_count": self.error_count,
            "true_rate": self.true_count / max(self.evaluation_count, 1),
            "error_rate": self.error_count / max(self.evaluation_count, 1),
            "average_duration_ms": self.total_duration_ms
            / max(self.evaluation_count, 1),
        }

    def __str__(self) -> str:
        return f"Guard({self.name})"

    def __repr__(self) -> str:
        return self.__str__()


class ActionBuilder:
    """액션 빌더 (플루언트 인터페이스)"""

    def __init__(self):
        self.name = None
        self.action_type = ActionType.TRANSITION
        self.action_func = None
        self.async_action = False

    def name(self, name: str) -> "ActionBuilder":
        """액션 이름 설정"""
        self.name = name
        return self

    def entry_action(self) -> "ActionBuilder":
        """진입 액션으로 설정"""
        self.action_type = ActionType.ENTRY
        return self

    def exit_action(self) -> "ActionBuilder":
        """탈출 액션으로 설정"""
        self.action_type = ActionType.EXIT
        return self

    def transition_action(self) -> "ActionBuilder":
        """전이 액션으로 설정"""
        self.action_type = ActionType.TRANSITION
        return self

    def guard_action(self) -> "ActionBuilder":
        """가드 액션으로 설정"""
        self.action_type = ActionType.GUARD
        return self

    def action(self, action_func: Callable[[Dict[str, Any]], Any]) -> "ActionBuilder":
        """액션 함수 설정"""
        self.action_func = action_func
        return self

    def async_mode(self, async_action=True) -> "ActionBuilder":
        """비동기 모드 설정"""
        self.async_action = async_action
        return self

    def build(self) -> Action:
        """액션 생성"""
        if not all([self.name, self.action_func]):
            raise ValueError("Name and action function must be specified")

        return Action(
            name=self.name,
            action_type=self.action_type,
            action_func=self.action_func,
            async_action=self.async_action,
        )


class GuardBuilder:
    """가드 빌더 (플루언트 인터페이스)"""

    def __init__(self):
        self.name = None
        self.guard_func = None
        self.description = ""

    def name(self, name: str) -> "GuardBuilder":
        """가드 이름 설정"""
        self.name = name
        return self

    def condition(self, guard_func: Callable[[Dict[str, Any]], bool]) -> "GuardBuilder":
        """가드 조건 설정"""
        self.guard_func = guard_func
        return self

    def description(self, description: str) -> "GuardBuilder":
        """가드 설명 설정"""
        self.description = description
        return self

    def build(self) -> Guard:
        """가드 생성"""
        if not all([self.name, self.guard_func]):
            raise ValueError("Name and guard function must be specified")

        return Guard(
            name=self.name, guard_func=self.guard_func, description=self.description
        )


# 편의 함수들
def action() -> ActionBuilder:
    """액션 빌더 생성"""
    return ActionBuilder()


def entry_action() -> ActionBuilder:
    """진입 액션 빌더 생성"""
    return ActionBuilder().entry_action()


def exit_action() -> ActionBuilder:
    """탈출 액션 빌더 생성"""
    return ActionBuilder().exit_action()


def transition_action() -> ActionBuilder:
    """전이 액션 빌더 생성"""
    return ActionBuilder().transition_action()


def guard() -> GuardBuilder:
    """가드 빌더 생성"""
    return GuardBuilder()


# 미리 정의된 가드들
def always_true_guard() -> Guard:
    """항상 참인 가드"""
    return guard().name("always_true").condition(lambda ctx: True).build()


def always_false_guard() -> Guard:
    """항상 거짓인 가드"""
    return guard().name("always_false").condition(lambda ctx: False).build()


def context_has_key_guard(key: str) -> Guard:
    """컨텍스트에 특정 키가 있는지 확인하는 가드"""
    return guard().name(f"has_{key}").condition(lambda ctx: key in ctx).build()


def context_value_equals_guard(key: str, value: Any) -> Guard:
    """컨텍스트 값이 특정 값과 같은지 확인하는 가드"""
    return (
        guard()
        .name(f"{key}_equals_{value}")
        .condition(lambda ctx: ctx.get(key) == value)
        .build()
    )
