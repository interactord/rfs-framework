"""
Project Management Commands (RFS Framework)

프로젝트 초기화, 생성, 설정 관리 명령어들
- init: RFS 프로젝트 초기화
- new: 새 컴포넌트/서비스 생성
- config: 설정 관리
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ...core.config import ConfigManager, RFSConfig
from ...core.result import Failure, Result, Success
from ..core import Command

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


@dataclass
class ProjectTemplate:
    """프로젝트 템플릿 정의"""

    name: str
    description: str
    files: Dict[str, str]
    dependencies: List[str]


class InitCommand(Command):
    """RFS 프로젝트 초기화 명령어"""

    name = "init"
    description = "RFS Framework 프로젝트 초기화"

    def __init__(self):
        super().__init__()
        self.templates = {
            "minimal": ProjectTemplate(
                name="Minimal",
                description="최소 구성 RFS 프로젝트",
                files={
                    "main.py": self._get_minimal_main_template(),
                    "requirements.txt": self._get_minimal_requirements(),
                    ".env": self._get_env_template(),
                    "rfs.yaml": self._get_config_template(),
                },
                dependencies=["rfs-framework>=4.0.0", "pydantic>=2.0.0"],
            ),
            "cloud-run": ProjectTemplate(
                name="Cloud Run",
                description="Google Cloud Run 최적화 프로젝트",
                files={
                    "main.py": self._get_cloudrun_main_template(),
                    "requirements.txt": self._get_cloudrun_requirements(),
                    "Dockerfile": self._get_dockerfile_template(),
                    ".env": self._get_env_template(),
                    "rfs.yaml": self._get_cloudrun_config_template(),
                    "cloudbuild.yaml": self._get_cloudbuild_template(),
                },
                dependencies=[
                    "rfs-framework>=4.0.0",
                    "pydantic>=2.0.0",
                    "google-cloud-run>=0.8.0",
                    "google-cloud-tasks>=2.14.0",
                    "google-cloud-monitoring>=2.14.0",
                ],
            ),
            "full": ProjectTemplate(
                name="Full Stack",
                description="모든 기능이 포함된 전체 구성",
                files={
                    "main.py": self._get_full_main_template(),
                    "requirements.txt": self._get_full_requirements(),
                    "Dockerfile": self._get_dockerfile_template(),
                    ".env": self._get_env_template(),
                    "rfs.yaml": self._get_full_config_template(),
                    "tests/test_main.py": self._get_test_template(),
                    "docs/README.md": self._get_readme_template(),
                },
                dependencies=[
                    "rfs-framework>=4.0.0",
                    "pydantic>=2.0.0",
                    "google-cloud-run>=0.8.0",
                    "google-cloud-tasks>=2.14.0",
                    "google-cloud-monitoring>=2.14.0",
                    "pytest>=7.0.0",
                    "pytest-asyncio>=0.21.0",
                ],
            ),
        }

    async def execute(self, args: List[str]) -> Result[str, str]:
        """프로젝트 초기화 실행"""
        try:
            project_config = await self._collect_project_config(args)
            if type(project_config).__name__ == "Failure":
                return project_config
            config = project_config.unwrap()
            project_path = Path(config["name"])
            if project_path.exists():
                if not Confirm.ask(
                    f"디렉토리 '{config.get('name')}'가 이미 존재합니다. 계속하시겠습니까?"
                ):
                    return Failure("프로젝트 초기화가 취소되었습니다.")
            else:
                project_path.mkdir(parents=True, exist_ok=True)
            template = self.templates[config["template"]]
            await self._create_project_files(project_path, template, config)
            if console:
                success_panel = Panel(
                    f"✅ RFS Framework 프로젝트 '{config.get('name')}' 생성 완료!\n\n📁 프로젝트 경로: {project_path.absolute()}\n🎯 템플릿: {template.name}\n🚀 Cloud Run 최적화: {('예' if config.get('cloud_run') else '아니오')}\n\n다음 단계:\n  cd {config.get('name')}\n  pip install -r requirements.txt\n  rfs dev  # 개발 서버 시작",
                    title="프로젝트 초기화 완료",
                    border_style="green",
                )
                console.print(success_panel)
            return Success(f"RFS Framework 프로젝트 '{config.get('name')}' 생성 완료")
        except Exception as e:
            return Failure(f"프로젝트 초기화 실패: {str(e)}")

    async def _collect_project_config(
        self, args: List[str]
    ) -> Result[Dict[str, Any], str]:
        """프로젝트 설정 수집 (인터랙티브)"""
        try:
            config = {}
            if args and len(args) > 0:
                config["name"] = {"name": args[0]}
            else:
                config = {
                    **config,
                    "name": {
                        "name": Prompt.ask(
                            "프로젝트 이름을 입력하세요", default="my-rfs-project"
                        )
                    },
                }
            if console:
                console.print("\n🎯 템플릿 선택:")
                template_table = Table(show_header=True, header_style="bold magenta")
                template_table.add_column("선택", style="cyan", width=8)
                template_table.add_column("템플릿", style="green")
                template_table.add_column("설명", style="white")
                for key, template in self.templates.items():
                    template_table.add_row(key, template.name, template.description)
                console.print(template_table)
            template_choice = Prompt.ask(
                "템플릿을 선택하세요",
                choices=list(self.templates.keys()),
                default="cloud-run",
            )
            config["template"] = {"template": template_choice}
            if template_choice in ["cloud-run", "full"]:
                config["cloud_run"] = {"cloud_run": True}
                config = {
                    **config,
                    "project_id": {
                        "project_id": Prompt.ask(
                            "Google Cloud 프로젝트 ID", default="my-project"
                        )
                    },
                }
                config = {
                    **config,
                    "region": {
                        "region": Prompt.ask("배포 리전", default="asia-northeast3")
                    },
                }
                config = {
                    **config,
                    "service_name": {
                        "service_name": Prompt.ask(
                            "서비스 이름", default=config["name"]
                        )
                    },
                }
            config = {
                **config,
                "monitoring": {
                    "monitoring": Confirm.ask("모니터링 활성화?", default=True)
                },
            }
            config = {
                **config,
                "task_queue": {
                    "task_queue": Confirm.ask("Task Queue 사용?", default=True)
                },
            }
            return Success(config)
        except Exception as e:
            return Failure(f"설정 수집 실패: {str(e)}")

    async def _create_project_files(
        self, project_path: Path, template: ProjectTemplate, config: Dict[str, Any]
    ) -> None:
        """프로젝트 파일들 생성"""
        for file_path, content in template.files.items():
            full_path = project_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            processed_content = content.format(**config)
            full_path.write_text(processed_content, encoding="utf-8")

    def _get_minimal_main_template(self) -> str:
        return '"""\nRFS Framework Minimal Application\n\n최소 구성 RFS 애플리케이션\n"""\n\nimport asyncio\nfrom rfs import RFSConfig, get_config, result_of\n\nasync def main():\n    """메인 애플리케이션 진입점"""\n    config = get_config()\n    print(f"🚀 RFS Framework 애플리케이션 시작 - {{name}}")\n    print(f"⚙️  환경: {{config.environment}}")\n    \n    # 여기에 비즈니스 로직 추가\n    result = result_of(lambda: "Hello, RFS Framework!")\n    \n    if result.is_success():\n        print(f"✅ 결과: {{result.unwrap()}}")\n    else:\n        print(f"❌ 오류: {{result.unwrap_err()}}")\n\nif __name__ == "__main__":\n    asyncio.run(main())\n'

    def _get_cloudrun_main_template(self) -> str:
        return '"""\nRFS Framework Cloud Run Application\n\nGoogle Cloud Run 최적화 RFS 애플리케이션\n"""\n\nimport asyncio\nfrom rfs import (\n    RFSConfig, get_config,\n    initialize_cloud_run_services,\n    get_cloud_run_status,\n    result_of\n)\n\nasync def main():\n    """메인 애플리케이션 진입점"""\n    config = get_config()\n    print(f"🚀 RFS Framework Cloud Run 애플리케이션 시작 - {{name}}")\n    \n    # Cloud Run 서비스 초기화\n    init_result = await initialize_cloud_run_services(\n        project_id="{project_id}",\n        service_name="{service_name}",\n        enable_monitoring={monitoring},\n        enable_task_queue={task_queue}\n    )\n    \n    if init_result.get("success"):\n        print("✅ Cloud Run 서비스 초기화 완료")\n        \n        # 상태 확인\n        status = await get_cloud_run_status()\n        print(f"📊 서비스 상태: {{len(status.get(\'services\', {{}})}}개 서비스 활성화")\n        \n        # 여기에 비즈니스 로직 추가\n        result = result_of(lambda: "Hello, Cloud Run!")\n        \n        if result.is_success():\n            print(f"✅ 결과: {{result.unwrap()}}")\n        else:\n            print(f"❌ 오류: {{result.unwrap_err()}}")\n    else:\n        print(f"❌ Cloud Run 서비스 초기화 실패: {{init_result.get(\'error\')}}")\n\nif __name__ == "__main__":\n    asyncio.run(main())\n'

    def _get_minimal_requirements(self) -> str:
        return "# RFS Framework Minimal Requirements\nrfs-framework>=4.0.0\npydantic>=2.0.0\n"

    def _get_cloudrun_requirements(self) -> str:
        return "# RFS Framework Cloud Run Requirements\nrfs-framework>=4.0.0\npydantic>=2.0.0\ngoogle-cloud-run>=0.8.0\ngoogle-cloud-tasks>=2.14.0\ngoogle-cloud-monitoring>=2.14.0\nuvicorn[standard]>=0.23.0\n"

    def _get_env_template(self) -> str:
        return "# RFS Framework 환경 변수\nRFS_ENVIRONMENT=development\nRFS_DEBUG=true\nRFS_LOG_LEVEL=INFO\n\n# Google Cloud (Cloud Run 사용 시)\nGOOGLE_CLOUD_PROJECT={project_id}\nGOOGLE_CLOUD_REGION={region}\n"


class NewCommand(Command):
    """새 컴포넌트/서비스 생성 명령어"""

    name = "new"
    description = "새 컴포넌트, 서비스, 또는 핸들러 생성"

    async def execute(self, args: List[str]) -> Result[str, str]:
        """새 컴포넌트 생성 실행"""
        if not args:
            return Failure("컴포넌트 타입을 지정해주세요 (service, handler, task)")
        component_type = args[0].lower()
        name = args[1] if len(args) > 1 else None
        if not name:
            name = Prompt.ask(f"{component_type} 이름을 입력하세요")
        try:
            if component_type == "service":
                return await self._create_service(name)
            else:
                match component_type:
                    case "handler":
                        return await self._create_handler(name)
                    case "task":
                        return await self._create_task_handler(name)
                    case _:
                        return Failure(f"지원하지 않는 컴포넌트 타입: {component_type}")
        except Exception as e:
            return Failure(f"컴포넌트 생성 실패: {str(e)}")

    async def _create_service(self, name: str) -> Result[str, str]:
        """서비스 클래스 생성"""
        service_content = f'"""\n{name.title()} Service\n\n{name} 서비스 구현\n"""\n\nfrom typing import Any, Dict, List, Optional\nfrom rfs import Result, Success, Failure, stateless\n\n\n@stateless\nclass {name.title()}Service:\n    """\n    {name.title()} 서비스\n    \n    비즈니스 로직을 구현하세요.\n    """\n    \n    async def process(self, data: Dict[str, Any]) -> Result[Dict[str, Any], str]:\n        """\n        주요 처리 로직\n        \n        Args:\n            data: 입력 데이터\n            \n        Returns:\n            Result[Dict[str, Any], str]: 처리 결과 또는 오류\n        """\n        try:\n            # TODO: 비즈니스 로직 구현\n            result = {{\n                "service": "{name}",\n                "status": "success",\n                "data": data\n            }}\n            \n            return Success(result)\n            \n        except Exception as e:\n            return Failure(f"{name} 서비스 처리 실패: {{str(e)}}")\n    \n    async def validate(self, data: Dict[str, Any]) -> Result[bool, str]:\n        """\n        데이터 검증\n        \n        Args:\n            data: 검증할 데이터\n            \n        Returns:\n            Result[bool, str]: 검증 결과\n        """\n        try:\n            # TODO: 검증 로직 구현\n            if not data:\n                return Failure("데이터가 비어있습니다")\n            \n            return Success(True)\n            \n        except Exception as e:\n            return Failure(f"데이터 검증 실패: {{str(e)}}")\n\n\n# 서비스 인스턴스\n{name}_service = {name.title()}Service()\n'
        service_path = Path(f"services/{name}_service.py")
        service_path.parent.mkdir(parents=True, exist_ok=True)
        service_path.write_text(service_content, encoding="utf-8")
        return Success(f"서비스 '{name}' 생성 완료: {service_path}")


class ConfigCommand(Command):
    """설정 관리 명령어"""

    name = "config"
    description = "RFS 프로젝트 설정 관리"

    async def execute(self, args: List[str]) -> Result[str, str]:
        """설정 관리 실행"""
        if not args:
            return await self._show_config()
        action = args[0].lower()
        try:
            match action:
                case "show":
                    return await self._show_config()
                case "set":
                    if len(args) < 3:
                        return Failure("사용법: rfs config set <키> <값>")
                    return await self._set_config(args[1], args[2])
                case "get":
                    if len(args) < 2:
                        return Failure("사용법: rfs config get <키>")
                    return await self._get_config(args[1])
                case "validate":
                    return await self._validate_config()
                case _:
                    return Failure(f"지원하지 않는 액션: {action}")
        except Exception as e:
            return Failure(f"설정 관리 실패: {str(e)}")

    async def _show_config(self) -> Result[str, str]:
        """현재 설정 표시"""
        try:
            config = get_config()
            if console:
                config_table = Table(
                    title="RFS v4 설정", show_header=True, header_style="bold magenta"
                )
                config_table.add_column("키", style="cyan", width=20)
                config_table.add_column("값", style="green")
                config_table.add_column("타입", style="yellow", width=12)
                config_dict = config.model_dump()
                for key, value in config_dict.items():
                    config_table.add_row(
                        key,
                        str(value) if value is not None else "None",
                        type(value).__name__,
                    )
                console.print(config_table)
                return Success("설정 표시 완료")
        except Exception as e:
            return Failure(f"설정 조회 실패: {str(e)}")
