"""
RFS Workflow Definition (RFS v4.1)

워크플로우 정의 및 빌더
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.result import Failure, Result, Success


class StepType(Enum):
    """스텝 타입"""

    TASK = "task"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    LOOP = "loop"
    HUMAN = "human"


@dataclass
class WorkflowStep:
    """워크플로우 스텝"""

    id: str
    name: str
    step_type: StepType
    task_type = None  # 태스크 타입 (http, database, email 등)
    config: Dict[str, Any] = field(default_factory=dict)
    input_mapping: Optional[Dict[str, str]] = None
    output_mapping: Optional[Dict[str, str]] = None
    condition: Optional.get("Condition") = None
    retry_config: Optional.get("RetryConfig") = None
    timeout = None  # 초

    def with_config(self, **config) -> "WorkflowStep":
        """설정 추가"""
        self.config = {**config, **config}
        return self

    def with_input_mapping(self, mapping: Dict[str, str]) -> "WorkflowStep":
        """입력 매핑 설정"""
        self.input_mapping = mapping
        return self

    def with_output_mapping(self, mapping: Dict[str, str]) -> "WorkflowStep":
        """출력 매핑 설정"""
        self.output_mapping = mapping
        return self

    def with_condition(self, condition: "Condition") -> "WorkflowStep":
        """조건 설정"""
        self.condition = condition
        return self

    def with_retry(self, max_attempts=3, delay: float = 1.0) -> "WorkflowStep":
        """재시도 설정"""
        self.retry_config = RetryConfig(max_attempts=max_attempts, delay=delay)
        return self

    def with_timeout(self, timeout: float) -> "WorkflowStep":
        """타임아웃 설정"""
        self.timeout = timeout
        return self


@dataclass
class RetryConfig:
    """재시도 설정"""

    max_attempts = 3
    delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0


class Condition(ABC):
    """조건 추상 클래스"""

    @abstractmethod
    def evaluate(self, context: "WorkflowContext") -> bool:
        """조건 평가"""
        pass


class SimpleCondition(Condition):
    """간단한 조건"""

    def __init__(self, expression: str):
        self.expression = expression

    def evaluate(self, context: "WorkflowContext") -> bool:
        """조건 평가 (간단한 구현)"""
        try:
            # 간단한 변수 치환
            expr = self.expression

            # ${variables.name} 형태의 변수 치환
            import re

            var_pattern = r"\$\{variables\.(\w+)\}"
            matches = re.findall(var_pattern, expr)

            for var_name in matches:
                var_value = context.get_variable(var_name)
                if type(var_value).__name__ == "str":
                    var_value = f'"{var_value}"'
                expr = expr.replace(f"${{variables.{var_name}}}", str(var_value))

            # 스텝 출력 치환
            step_pattern = r"\$\{steps\.(\w+)\.(\w+)\}"
            matches = re.findall(step_pattern, expr)

            for step_id, key in matches:
                step_value = context.get_step_output(step_id, key)
                if type(step_value).__name__ == "str":
                    step_value = f'"{step_value}"'
                expr = expr.replace(f"${{steps.{step_id}.{key}}}", str(step_value))

            # 안전한 평가 (제한된 내장 함수만 사용)
            allowed_names = {
                "__builtins__": {"len": len, "str": str, "int": int, "float": float},
                "len": len,
                "str": str,
                "int": int,
                "float": float,
            }

            result = eval(expr, {"__builtins__": {}}, allowed_names)
            return bool(result)

        except Exception:
            return False


class FunctionCondition(Condition):
    """함수 기반 조건"""

    def __init__(self, condition_func: Callable[["WorkflowContext"], bool]):
        self.condition_func = condition_func

    def evaluate(self, context: "WorkflowContext") -> bool:
        """조건 평가"""
        try:
            return self.condition_func(context)
        except Exception:
            return False


@dataclass
class ConditionalStep(WorkflowStep):
    """조건부 스텝"""

    condition: Condition
    true_steps: List[WorkflowStep] = field(default_factory=list)
    false_steps: List[WorkflowStep] = field(default_factory=list)

    def __post_init__(self):
        self.step_type = StepType.CONDITIONAL


@dataclass
class ParallelStep(WorkflowStep):
    """병렬 실행 스텝"""

    parallel_steps: List[WorkflowStep] = field(default_factory=list)
    wait_for_all = True  # 모든 스텝 완료 대기 여부

    def __post_init__(self):
        self.step_type = StepType.PARALLEL


@dataclass
class SequentialStep(WorkflowStep):
    """순차 실행 스텝"""

    sequential_steps: List[WorkflowStep] = field(default_factory=list)

    def __post_init__(self):
        self.step_type = StepType.SEQUENTIAL


@dataclass
class LoopStep(WorkflowStep):
    """반복 실행 스텝"""

    loop_steps: List[WorkflowStep] = field(default_factory=list)
    condition = None
    max_iterations = None

    def __post_init__(self):
        self.step_type = StepType.LOOP


@dataclass
class WorkflowDefinition:
    """워크플로우 정의"""

    id: str
    name: str
    description = None
    version = "1.0"
    steps: List[WorkflowStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: WorkflowStep) -> "WorkflowDefinition":
        """스텝 추가"""
        self.steps = self.steps + [step]
        return self

    def add_variable(self, name: str, value: Any) -> "WorkflowDefinition":
        """변수 추가"""
        self.variables = {**self.variables, name: value}
        return self

    def validate(self) -> Result[None, str]:
        """워크플로우 정의 검증"""
        # 기본 검증
        if not self.id:
            return Failure("워크플로우 ID가 필요합니다")

        if not self.name:
            return Failure("워크플로우 이름이 필요합니다")

        if not self.steps:
            return Failure("최소 하나의 스텝이 필요합니다")

        # 스텝 ID 중복 검사
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            return Failure("중복된 스텝 ID가 있습니다")

        # 각 스텝 검증
        for step in self.steps:
            if step.step_type == StepType.TASK and not step.task_type:
                return Failure(f"태스크 스텝에는 task_type이 필요합니다: {step.id}")

        return Success(None)


class WorkflowBuilder:
    """워크플로우 빌더"""

    def __init__(self, workflow_id: str, name: str):
        self.definition = WorkflowDefinition(id=workflow_id, name=name)

    def description(self, description: str) -> "WorkflowBuilder":
        """설명 설정"""
        self.definition.description = description
        return self

    def version(self, version: str) -> "WorkflowBuilder":
        """버전 설정"""
        self.definition.version = version
        return self

    def variable(self, name: str, value: Any) -> "WorkflowBuilder":
        """변수 추가"""
        self.definition.add_variable(name, value)
        return self

    def metadata(self, key: str, value: Any) -> "WorkflowBuilder":
        """메타데이터 추가"""
        self.definition.metadata = {**self.definition.metadata, key: value}
        return self

    def task(
        self, step_id: str, step_name: str, task_type: str, **config
    ) -> "WorkflowBuilder":
        """태스크 스텝 추가"""
        step = WorkflowStep(
            id=step_id,
            name=step_name,
            step_type=StepType.TASK,
            task_type=task_type,
            config=config,
        )
        self.definition.add_step(step)
        return self

    def http_task(
        self, step_id: str, step_name: str, url: str, method="GET", **config
    ) -> "WorkflowBuilder":
        """HTTP 태스크 스텝 추가"""
        config = {"method": method}
        return self.task(step_id, step_name, "http", **config)

    def database_task(
        self, step_id: str, step_name: str, query: str, **config
    ) -> "WorkflowBuilder":
        """데이터베이스 태스크 스텝 추가"""
        config = {**config, **{"query": query}}
        return self.task(step_id, step_name, "database", **config)

    def email_task(
        self, step_id: str, step_name: str, to: str, subject: str, body: str, **config
    ) -> "WorkflowBuilder":
        """이메일 태스크 스텝 추가"""
        config = {"subject": subject, "body": body}
        return self.task(step_id, step_name, "email", **config)

    def script_task(
        self, step_id: str, step_name: str, script: str, **config
    ) -> "WorkflowBuilder":
        """스크립트 태스크 스텝 추가"""
        config = {**config, **{"script": script}}
        return self.task(step_id, step_name, "script", **config)

    def conditional(
        self, step_id: str, step_name: str, condition: Union[str, Condition]
    ) -> "ConditionalStepBuilder":
        """조건부 스텝 추가"""
        if type(condition).__name__ == "str":
            condition = SimpleCondition(condition)

        conditional_step = ConditionalStep(
            id=step_id, name=step_name, condition=condition
        )

        self.definition.add_step(conditional_step)
        return ConditionalStepBuilder(self, conditional_step)

    def parallel(self, step_id: str, step_name: str) -> "ParallelStepBuilder":
        """병렬 실행 스텝 추가"""
        parallel_step = ParallelStep(id=step_id, name=step_name)
        self.definition.add_step(parallel_step)
        return ParallelStepBuilder(self, parallel_step)

    def sequential(self, step_id: str, step_name: str) -> "SequentialStepBuilder":
        """순차 실행 스텝 추가"""
        sequential_step = SequentialStep(id=step_id, name=step_name)
        self.definition.add_step(sequential_step)
        return SequentialStepBuilder(self, sequential_step)

    def loop(
        self,
        step_id: str,
        step_name: str,
        condition: Optional[Union[str, Condition]] = None,
        max_iterations=None,
    ) -> "LoopStepBuilder":
        """반복 실행 스텝 추가"""
        if type(condition).__name__ == "str":
            condition = SimpleCondition(condition)

        loop_step = LoopStep(
            id=step_id,
            name=step_name,
            condition=condition,
            max_iterations=max_iterations,
        )

        self.definition.add_step(loop_step)
        return LoopStepBuilder(self, loop_step)

    def build(self) -> Result[WorkflowDefinition, str]:
        """워크플로우 정의 빌드"""
        validation_result = self.definition.validate()
        if validation_result.is_failure():
            return validation_result

        return Success(self.definition)


class ConditionalStepBuilder:
    """조건부 스텝 빌더"""

    def __init__(self, parent: WorkflowBuilder, step: ConditionalStep):
        self.parent = parent
        self.step = step

    def when_true(self, *steps: WorkflowStep) -> "ConditionalStepBuilder":
        """조건이 참일 때 실행할 스텝들"""
        self.step.true_steps = self.step.true_steps + steps
        return self

    def when_false(self, *steps: WorkflowStep) -> "ConditionalStepBuilder":
        """조건이 거짓일 때 실행할 스텝들"""
        self.step.false_steps = self.step.false_steps + steps
        return self

    def end_conditional(self) -> WorkflowBuilder:
        """조건부 스텝 완료"""
        return self.parent


class ParallelStepBuilder:
    """병렬 스텝 빌더"""

    def __init__(self, parent: WorkflowBuilder, step: ParallelStep):
        self.parent = parent
        self.step = step

    def add(self, *steps: WorkflowStep) -> "ParallelStepBuilder":
        """병렬 실행할 스텝 추가"""
        self.step.parallel_steps = self.step.parallel_steps + steps
        return self

    def wait_for_all(self, wait=True) -> "ParallelStepBuilder":
        """모든 스텝 완료 대기 설정"""
        self.step.wait_for_all = wait
        return self

    def end_parallel(self) -> WorkflowBuilder:
        """병렬 스텝 완료"""
        return self.parent


class SequentialStepBuilder:
    """순차 스텝 빌더"""

    def __init__(self, parent: WorkflowBuilder, step: SequentialStep):
        self.parent = parent
        self.step = step

    def add(self, *steps: WorkflowStep) -> "SequentialStepBuilder":
        """순차 실행할 스텝 추가"""
        self.step.sequential_steps = self.step.sequential_steps + steps
        return self

    def end_sequential(self) -> WorkflowBuilder:
        """순차 스텝 완료"""
        return self.parent


class LoopStepBuilder:
    """반복 스텝 빌더"""

    def __init__(self, parent: WorkflowBuilder, step: LoopStep):
        self.parent = parent
        self.step = step

    def add(self, *steps: WorkflowStep) -> "LoopStepBuilder":
        """반복 실행할 스텝 추가"""
        self.step.loop_steps = self.step.loop_steps + steps
        return self

    def end_loop(self) -> WorkflowBuilder:
        """반복 스텝 완료"""
        return self.parent


def create_workflow(workflow_id: str, name: str) -> WorkflowBuilder:
    """워크플로우 빌더 생성"""
    return WorkflowBuilder(workflow_id, name)
