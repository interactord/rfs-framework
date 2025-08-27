"""
Workflow Automation Engine (RFS v4)

워크플로우 자동화 핵심 엔진
- 트리거 기반 자동화
- 액션 실행 관리
- 워크플로우 오케스트레이션
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

try:
    from rich.console import Console
    from rich.progress import Progress, TaskID

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ...core.result import Failure, Result, Success

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class TriggerType(Enum):
    """트리거 유형"""

    FILE_CHANGE = "file_change"
    GIT_PUSH = "git_push"
    TIME_SCHEDULE = "time_schedule"
    MANUAL = "manual"
    WEBHOOK = "webhook"
    TEST_FAILURE = "test_failure"


class ActionType(Enum):
    """액션 유형"""

    COMMAND = "command"
    SCRIPT = "script"
    HTTP_REQUEST = "http_request"
    NOTIFICATION = "notification"
    GIT_OPERATION = "git_operation"
    DEPLOYMENT = "deployment"


@dataclass
class WorkflowTrigger:
    """워크플로우 트리거 정의"""

    name: str
    trigger_type: TriggerType
    conditions: Dict[str, Any]
    enabled = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, event: Dict[str, Any]) -> bool:
        """이벤트가 트리거 조건과 일치하는지 확인"""
        if not self.enabled:
            return False
        event_type = event.get("type")
        if event_type != self.trigger_type.value:
            return False
        for condition_key, condition_value in self.conditions.items():
            if condition_key not in event:
                return False
            event_value = event[condition_key]
            if type(condition_value).__name__ == "str" and "*" in condition_value:
                import fnmatch

                if not fnmatch.fnmatch(str(event_value), condition_value):
                    return False
            elif event_value != condition_value:
                return False
        return True


@dataclass
class ActionRunner:
    """액션 실행기"""

    name: str
    action_type: ActionType
    config: Dict[str, Any]
    timeout = 300
    retry_count = 0
    on_failure = None

    async def execute(self, context: Dict[str, Any]) -> Result[Dict[str, Any], str]:
        """액션 실행"""
        try:
            if console:
                console.print(f"🎯 액션 실행: {self.name} ({self.action_type.value})")
            match self.action_type:
                case ActionType.COMMAND:
                    return await self._execute_command(context)
                case ActionType.SCRIPT:
                    return await self._execute_script(context)
                case ActionType.HTTP_REQUEST:
                    return await self._execute_http_request(context)
                case ActionType.NOTIFICATION:
                    return await self._execute_notification(context)
                case ActionType.GIT_OPERATION:
                    return await self._execute_git_operation(context)
                case ActionType.DEPLOYMENT:
                    return await self._execute_deployment(context)
                case _:
                    return Failure(f"지원하지 않는 액션 유형: {self.action_type}")
        except Exception as e:
            return Failure(f"액션 실행 실패: {str(e)}")

    async def _execute_command(
        self, context: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """명령어 실행"""
        try:
            command = self.config.get("command")
            if not command:
                return Failure("명령어가 지정되지 않았습니다")
            formatted_command = command.format(**context)
            process = await asyncio.create_subprocess_shell(
                formatted_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return Failure(f"명령어 실행 시간 초과: {self.timeout}초")
            result = {
                "return_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
            if process.returncode == 0:
                return Success(result)
            else:
                return Failure(
                    f"명령어 실행 실패 (코드: {process.returncode}): {result.get('stderr')}"
                )
        except Exception as e:
            return Failure(f"명령어 실행 오류: {str(e)}")

    async def _execute_script(
        self, context: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """스크립트 실행"""
        try:
            script_path = self.config.get("script_path")
            if not script_path:
                return Failure("스크립트 경로가 지정되지 않았습니다")
            script_file = Path(script_path)
            if not script_file.exists():
                return Failure(f"스크립트 파일을 찾을 수 없습니다: {script_path}")
            args = self.config.get("args", [])
            formatted_args = [arg.format(**context) for arg in args]
            process = await asyncio.create_subprocess_exec(
                str(script_file),
                *formatted_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return Failure(f"스크립트 실행 시간 초과: {self.timeout}초")
            result = {
                "return_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
            if process.returncode == 0:
                return Success(result)
            else:
                return Failure(f"스크립트 실행 실패: {result.get('stderr')}")
        except Exception as e:
            return Failure(f"스크립트 실행 오류: {str(e)}")


class AutomationEngine:
    """워크플로우 자동화 엔진"""

    def __init__(self, config_path=None):
        self.config_path = config_path or "rfs-workflows.yaml"
        self.triggers = []
        self.workflows: Dict[str, List[ActionRunner]] = {}
        self.running = False
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.execution_history: List[Dict[str, Any]] = []

    async def initialize(self) -> Result[str, str]:
        """자동화 엔진 초기화"""
        try:
            await self._load_configuration()
            if console:
                console.print(f"🤖 RFS v4 워크플로우 자동화 엔진 초기화 완료")
                console.print(f"📊 트리거: {len(self.triggers)}개")
                console.print(f"🔧 워크플로우: {len(self.workflows)}개")
            return Success("자동화 엔진 초기화 완료")
        except Exception as e:
            return Failure(f"자동화 엔진 초기화 실패: {str(e)}")

    async def _load_configuration(self) -> None:
        """설정 파일 로드"""
        config_file = Path(self.config_path)
        if not config_file.exists():
            await self._create_default_configuration()
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        for trigger_config in config.get("triggers", []):
            trigger = WorkflowTrigger(
                name=trigger_config["name"],
                trigger_type=TriggerType(trigger_config["type"]),
                conditions=trigger_config.get("conditions", {}),
                enabled=trigger_config.get("enabled", True),
                metadata=trigger_config.get("metadata", {}),
            )
            self.triggers = self.triggers + [trigger]
        for workflow_name, actions_config in config.get("workflows", {}).items():
            actions = []
            for action_config in actions_config:
                action = ActionRunner(
                    name=action_config["name"],
                    action_type=ActionType(action_config["type"]),
                    config=action_config.get("config", {}),
                    timeout=action_config.get("timeout", 300),
                    retry_count=action_config.get("retry_count", 0),
                    on_failure=action_config.get("on_failure"),
                )
                actions = actions + [action]
            self.workflows = {**self.workflows, workflow_name: actions}

    async def _create_default_configuration(self) -> None:
        """기본 설정 파일 생성"""
        default_config = {
            "triggers": [
                {
                    "name": "git_push_main",
                    "type": "git_push",
                    "conditions": {"branch": "main"},
                    "enabled": True,
                    "metadata": {"description": "main 브랜치 푸시 시 CI/CD 실행"},
                },
                {
                    "name": "file_change_src",
                    "type": "file_change",
                    "conditions": {"path_pattern": "src/**/*.py"},
                    "enabled": True,
                    "metadata": {"description": "소스 코드 변경 시 테스트 실행"},
                },
            ],
            "workflows": {
                "ci_pipeline": [
                    {
                        "name": "run_tests",
                        "type": "command",
                        "config": {"command": "python -m pytest tests/ -v"},
                        "timeout": 300,
                    },
                    {
                        "name": "code_quality_check",
                        "type": "command",
                        "config": {"command": "ruff check . && black --check ."},
                        "timeout": 120,
                    },
                    {
                        "name": "build_docker_image",
                        "type": "command",
                        "config": {"command": "docker build -t rfs-app:latest ."},
                        "timeout": 600,
                    },
                ],
                "deploy_pipeline": [
                    {
                        "name": "deploy_to_cloud_run",
                        "type": "command",
                        "config": {
                            "command": "gcloud run deploy --source . --region=asia-northeast3"
                        },
                        "timeout": 900,
                    },
                    {
                        "name": "health_check",
                        "type": "http_request",
                        "config": {
                            "url": "{service_url}/health",
                            "method": "GET",
                            "expected_status": 200,
                        },
                        "timeout": 60,
                    },
                ],
            },
        }
        config_file = Path(self.config_path)
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)

    async def start(self) -> Result[str, str]:
        """자동화 엔진 시작"""
        try:
            if self.running:
                return Failure("자동화 엔진이 이미 실행 중입니다")
            self.running = True
            if console:
                console.print("🚀 워크플로우 자동화 엔진 시작")
            asyncio.create_task(self._event_processor())
            return Success("자동화 엔진 시작 완료")
        except Exception as e:
            return Failure(f"자동화 엔진 시작 실패: {str(e)}")

    async def stop(self) -> Result[str, str]:
        """자동화 엔진 중지"""
        try:
            self.running = False
            if console:
                console.print("⏹️  워크플로우 자동화 엔진 중지")
            return Success("자동화 엔진 중지 완료")
        except Exception as e:
            return Failure(f"자동화 엔진 중지 실패: {str(e)}")

    async def trigger_event(self, event: Dict[str, Any]) -> Result[str, str]:
        """이벤트 트리거"""
        try:
            await self.event_queue.put(event)
            return Success(f"이벤트 트리거됨: {event.get('type', 'unknown')}")
        except Exception as e:
            return Failure(f"이벤트 트리거 실패: {str(e)}")

    async def _event_processor(self) -> None:
        """이벤트 처리기"""
        while self.running:
            try:
                try:
                    event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                matched_triggers = [
                    trigger for trigger in self.triggers if trigger.matches(event)
                ]
                if matched_triggers:
                    if console:
                        console.print(
                            f"🎯 이벤트 매칭: {len(matched_triggers)}개 트리거"
                        )
                    for trigger in matched_triggers:
                        workflow_name = trigger.metadata.get("workflow")
                        if workflow_name and workflow_name in self.workflows:
                            await self._execute_workflow(workflow_name, event, trigger)
            except Exception as e:
                if console:
                    console.print(f"❌ 이벤트 처리 오류: {str(e)}", style="red")

    async def _execute_workflow(
        self, workflow_name: str, event: Dict[str, Any], trigger: WorkflowTrigger
    ) -> None:
        """워크플로우 실행"""
        try:
            actions = self.workflows[workflow_name]
            if console:
                console.print(f"🔧 워크플로우 실행 시작: {workflow_name}")
            execution_context = {
                "event": event,
                "trigger": trigger.name,
                "workflow": workflow_name,
                "timestamp": datetime.now().isoformat(),
                **event,
            }
            execution_result = {
                "workflow_name": workflow_name,
                "trigger_name": trigger.name,
                "start_time": datetime.now(),
                "actions_executed": [],
                "success": True,
                "error_message": None,
            }
            for action in actions:
                action_start = datetime.now()
                result = await action.execute(execution_context)
                action_result = {
                    "name": action.name,
                    "type": action.action_type.value,
                    "start_time": action_start,
                    "duration": (datetime.now() - action_start).total_seconds(),
                    "success": result.is_success(),
                    "result": (
                        result.unwrap() if result.is_success() else result.unwrap_err()
                    ),
                }
                execution_result["actions_executed"] = execution_result.get(
                    "actions_executed"
                ) + [action_result]
                if result.is_failure():
                    execution_result = {
                        **execution_result,
                        "success": {"success": False},
                    }
                    execution_result = {
                        **execution_result,
                        "error_message": {"error_message": result.unwrap_err()},
                    }
                    if console:
                        console.print(f"❌ 액션 실패: {action.name}", style="red")
                    if action.on_failure:
                        if console:
                            console.print(
                                f"🔄 실패 처리 액션 실행: {action.on_failure}"
                            )
                    break
                elif console:
                    console.print(f"✅ 액션 성공: {action.name}", style="green")
            execution_result = {
                **execution_result,
                "end_time": {"end_time": datetime.now()},
            }
            execution_result = {
                **execution_result,
                "total_duration": {
                    "total_duration": (
                        execution_result.get("end_time")
                        - execution_result.get("start_time")
                    ).total_seconds()
                },
            }
            self.execution_history = self.execution_history + [execution_result]
            if console:
                if execution_result.get("success"):
                    console.print(f"✅ 워크플로우 완료: {workflow_name}", style="green")
                else:
                    console.print(f"❌ 워크플로우 실패: {workflow_name}", style="red")
        except Exception as e:
            if console:
                console.print(f"❌ 워크플로우 실행 오류: {str(e)}", style="red")

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """실행 이력 조회"""
        return self.execution_history.copy()

    def get_workflow_status(self) -> Dict[str, Any]:
        """워크플로우 상태 조회"""
        return {
            "running": self.running,
            "triggers_count": len(self.triggers),
            "workflows_count": len(self.workflows),
            "executions_count": len(self.execution_history),
            "last_execution": (
                self.execution_history[-1] if self.execution_history else None
            ),
        }
