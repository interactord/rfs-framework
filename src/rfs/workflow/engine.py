"""
RFS Workflow Engine (RFS v4.1)

워크플로우 실행 엔진
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..events import Event, get_event_bus

logger = get_logger(__name__)


class WorkflowStatus(Enum):
    """워크플로우 상태"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """스텝 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowContext:
    """워크플로우 실행 컨텍스트"""

    workflow_id: str
    instance_id: str
    variables: Dict[str, Any] = field(default_factory=dict)
    step_outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_variable(self, name: str, default: Any = None) -> Any:
        """변수 조회"""
        return self.variables.get(name, default)

    def set_variable(self, name: str, value: Any):
        """변수 설정"""
        self.variables = {**self.variables, name: value}

    def get_step_output(
        self, step_id: str, key: str = None, default: Any = None
    ) -> Any:
        """스텝 출력 조회"""
        step_output = self.step_outputs.get(step_id, {})
        if key:
            return step_output.get(key, default)
        return step_output


@dataclass
class StepExecution:
    """스텝 실행 정보"""

    step_id: str
    step_name: str
    status: StepStatus
    start_time = None
    end_time = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message = None

    @property
    def duration(self) -> Optional[float]:
        """실행 시간 계산"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass
class WorkflowInstance:
    """워크플로우 인스턴스"""

    instance_id: str
    workflow_id: str
    definition: "WorkflowDefinition"
    status: WorkflowStatus
    context: WorkflowContext
    current_step = None
    start_time = None
    end_time = None
    step_executions: List[str] = field(default_factory=list)

    @property
    def duration(self) -> Optional[float]:
        """실행 시간 계산"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass
class WorkflowEvent(Event):
    """워크플로우 이벤트"""

    instance_id: str
    workflow_id: str
    event_type: str
    step_id = None
    data: Optional[Dict[str, Any]] = None


class WorkflowEngine:
    """워크플로우 엔진"""

    def __init__(self):
        self.running_instances = {}
        self.task_executors = {}
        self.event_bus = get_event_bus()
        self._lock = asyncio.Lock()

    def register_task_executor(self, task_type: str, executor: "TaskExecutor"):
        """태스크 실행기 등록"""
        self.task_executors = {**self.task_executors, task_type: executor}

    async def start_workflow(
        self,
        workflow_definition: "WorkflowDefinition",
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Result[WorkflowInstance, str]:
        """워크플로우 시작"""
        instance_id = str(uuid.uuid4())
        context = WorkflowContext(
            workflow_id=workflow_definition.id,
            instance_id=instance_id,
            variables=input_data or {},
            metadata={"created_at": time.time(), "created_by": "system"},
        )
        instance = WorkflowInstance(
            instance_id=instance_id,
            workflow_id=workflow_definition.id,
            definition=workflow_definition,
            status=WorkflowStatus.PENDING,
            context=context,
            start_time=time.time(),
        )
        async with self._lock:
            self.running_instances = {**self.running_instances, instance_id: instance}
        await self._emit_event(
            WorkflowEvent(
                instance_id=instance_id,
                workflow_id=workflow_definition.id,
                event_type="started",
                data={"input_data": input_data},
            )
        )
        asyncio.create_task(self._execute_workflow(instance))
        return Success(instance)

    async def pause_workflow(self, instance_id: str) -> Result[None, str]:
        """워크플로우 일시 정지"""
        async with self._lock:
            if instance_id not in self.running_instances:
                return Failure(f"실행 중인 인스턴스를 찾을 수 없음: {instance_id}")
            instance = self.running_instances[instance_id]
            if instance.status == WorkflowStatus.RUNNING:
                instance.status = WorkflowStatus.PAUSED
                await self._emit_event(
                    WorkflowEvent(
                        instance_id=instance_id,
                        workflow_id=instance.workflow_id,
                        event_type="paused",
                    )
                )
                return Success(None)
            else:
                return Failure(f"인스턴스가 실행 중이 아님: {instance.status}")

    async def resume_workflow(self, instance_id: str) -> Result[None, str]:
        """워크플로우 재개"""
        async with self._lock:
            if instance_id not in self.running_instances:
                return Failure(f"실행 중인 인스턴스를 찾을 수 없음: {instance_id}")
            instance = self.running_instances[instance_id]
            if instance.status == WorkflowStatus.PAUSED:
                instance.status = WorkflowStatus.RUNNING
                await self._emit_event(
                    WorkflowEvent(
                        instance_id=instance_id,
                        workflow_id=instance.workflow_id,
                        event_type="resumed",
                    )
                )
                asyncio.create_task(self._execute_workflow(instance))
                return Success(None)
            else:
                return Failure(f"인스턴스가 일시 정지 상태가 아님: {instance.status}")

    async def stop_workflow(self, instance_id: str) -> Result[None, str]:
        """워크플로우 중단"""
        async with self._lock:
            if instance_id not in self.running_instances:
                return Failure(f"실행 중인 인스턴스를 찾을 수 없음: {instance_id}")
            instance = self.running_instances[instance_id]
            instance.status = WorkflowStatus.CANCELLED
            instance.end_time = time.time()
            await self._emit_event(
                WorkflowEvent(
                    instance_id=instance_id,
                    workflow_id=instance.workflow_id,
                    event_type="cancelled",
                )
            )
            del self.running_instances[instance_id]
            return Success(None)

    async def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """워크플로우 인스턴스 조회"""
        return self.running_instances.get(instance_id)

    async def list_instances(
        self, workflow_id=None, status=None
    ) -> List[WorkflowInstance]:
        """워크플로우 인스턴스 목록"""
        instances = list(self.running_instances.values())
        if workflow_id:
            instances = [i for i in instances if i.workflow_id == workflow_id]
        if status:
            instances = [i for i in instances if i.status == status]
        return instances

    async def _execute_workflow(self, instance: WorkflowInstance):
        """워크플로우 실행"""
        try:
            instance.status = WorkflowStatus.RUNNING
            for step in instance.definition.steps:
                if instance.status in [WorkflowStatus.PAUSED, WorkflowStatus.CANCELLED]:
                    return
                step_result = await self._execute_step(instance, step)
                if step_result.is_failure():
                    instance.status = WorkflowStatus.FAILED
                    instance.end_time = time.time()
                    await self._emit_event(
                        WorkflowEvent(
                            instance_id=instance.instance_id,
                            workflow_id=instance.workflow_id,
                            event_type="failed",
                            data={"error": step_result.unwrap_err()},
                        )
                    )
                    async with self._lock:
                        if instance.instance_id in self.running_instances:
                            del self.running_instances[instance.instance_id]
                    return
                instance.current_step = step.id
            instance.status = WorkflowStatus.COMPLETED
            instance.end_time = time.time()
            await self._emit_event(
                WorkflowEvent(
                    instance_id=instance.instance_id,
                    workflow_id=instance.workflow_id,
                    event_type="completed",
                    data={"duration": instance.duration},
                )
            )
            async with self._lock:
                if instance.instance_id in self.running_instances:
                    del self.running_instances[instance.instance_id]
        except Exception as e:
            await logger.log_error(f"워크플로우 실행 오류: {str(e)}")
            instance.status = WorkflowStatus.FAILED
            instance.end_time = time.time()
            await self._emit_event(
                WorkflowEvent(
                    instance_id=instance.instance_id,
                    workflow_id=instance.workflow_id,
                    event_type="error",
                    data={"error": str(e)},
                )
            )
            async with self._lock:
                if instance.instance_id in self.running_instances:
                    del self.running_instances[instance.instance_id]

    async def _execute_step(
        self, instance: WorkflowInstance, step: "WorkflowStep"
    ) -> Result[Any, str]:
        """워크플로우 스텝 실행"""
        step_execution = StepExecution(
            step_id=step.id,
            step_name=step.name,
            status=StepStatus.RUNNING,
            start_time=time.time(),
        )
        instance.step_executions = instance.step_executions + [step_execution]
        try:
            await logger.log_info(f"스텝 실행 시작: {step.name} ({step.id})")
            if step.task_type not in self.task_executors:
                error_msg = f"태스크 실행기를 찾을 수 없음: {step.task_type}"
                step_execution.status = StepStatus.FAILED
                step_execution.error_message = error_msg
                step_execution.end_time = time.time()
                return Failure(error_msg)
            executor = self.task_executors[step.task_type]
            input_data = self._prepare_step_input(instance, step)
            step_execution.input_data = input_data
            result = await executor.execute(step.config, input_data, instance.context)
            if result.is_success():
                output_data = result.unwrap()
                step_execution.status = StepStatus.COMPLETED
                step_execution.output_data = output_data
                step_execution.end_time = time.time()
                instance.context.step_outputs = {
                    **instance.context.step_outputs,
                    step.id: output_data,
                }
                await self._emit_event(
                    WorkflowEvent(
                        instance_id=instance.instance_id,
                        workflow_id=instance.workflow_id,
                        event_type="step_completed",
                        step_id=step.id,
                        data={"output": output_data},
                    )
                )
                await logger.log_info(
                    f"스텝 실행 완료: {step.name} ({step_execution.duration:.3f}s)"
                )
                return result
            else:
                error_msg = result.unwrap_err()
                step_execution.status = StepStatus.FAILED
                step_execution.error_message = error_msg
                step_execution.end_time = time.time()
                await self._emit_event(
                    WorkflowEvent(
                        instance_id=instance.instance_id,
                        workflow_id=instance.workflow_id,
                        event_type="step_failed",
                        step_id=step.id,
                        data={"error": error_msg},
                    )
                )
                return result
        except Exception as e:
            error_msg = f"스텝 실행 오류: {str(e)}"
            step_execution.status = StepStatus.FAILED
            step_execution.error_message = error_msg
            step_execution.end_time = time.time()
            await logger.log_error(f"스텝 실행 오류: {step.name} - {error_msg}")
            return Failure(error_msg)

    def _prepare_step_input(
        self, instance: WorkflowInstance, step: "WorkflowStep"
    ) -> Dict[str, Any]:
        """스텝 입력 데이터 준비"""
        input_data = {}
        if hasattr(step, "input_mapping") and step.input_mapping:
            for output_key, input_expr in step.input_mapping.items():
                if input_expr.startswith("${") and input_expr.endswith("}"):
                    expr = input_expr[2:-1]
                    if expr.startswith("variables."):
                        var_name = expr[10:]
                        input_data = {
                            **input_data,
                            output_key: {
                                output_key: instance.context.get_variable(var_name)
                            },
                        }
                    elif expr.startswith("steps."):
                        parts = expr[6:].split(".", 1)
                        if len(parts) == 2:
                            step_id, key = parts
                            input_data = {
                                **input_data,
                                output_key: {
                                    output_key: instance.context.get_step_output(
                                        step_id, key
                                    )
                                },
                            }
                        else:
                            step_id = parts[0]
                            input_data = {
                                **input_data,
                                output_key: {
                                    output_key: instance.context.get_step_output(
                                        step_id
                                    )
                                },
                            }
                else:
                    input_data[output_key] = {output_key: input_expr}
        return input_data

    async def _emit_event(self, event: WorkflowEvent):
        """워크플로우 이벤트 발생"""
        try:
            await self.event_bus.publish(event)
        except Exception as e:
            await logger.log_warning(f"워크플로우 이벤트 발생 실패: {str(e)}")


_workflow_engine = None


def get_workflow_engine() -> WorkflowEngine:
    """워크플로우 엔진 가져오기"""
    # global _workflow_engine - removed for functional programming
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine


async def start_workflow(
    workflow_definition: "WorkflowDefinition",
    input_data: Optional[Dict[str, Any]] = None,
) -> Result[WorkflowInstance, str]:
    """워크플로우 시작"""
    engine = get_workflow_engine()
    return await engine.start_workflow(workflow_definition, input_data)


async def execute_workflow(
    workflow_definition: "WorkflowDefinition",
    input_data: Optional[Dict[str, Any]] = None,
) -> Result[WorkflowInstance, str]:
    """워크플로우 실행 (시작과 동일)"""
    return await start_workflow(workflow_definition, input_data)


async def pause_workflow(instance_id: str) -> Result[None, str]:
    """워크플로우 일시 정지"""
    engine = get_workflow_engine()
    return await engine.pause_workflow(instance_id)


async def resume_workflow(instance_id: str) -> Result[None, str]:
    """워크플로우 재개"""
    engine = get_workflow_engine()
    return await engine.resume_workflow(instance_id)


async def stop_workflow(instance_id: str) -> Result[None, str]:
    """워크플로우 중단"""
    engine = get_workflow_engine()
    return await engine.stop_workflow(instance_id)
