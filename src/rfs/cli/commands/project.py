"""
Project Management Commands (RFS v4)

프로젝트 초기화, 생성, 설정 관리 명령어들
- init: RFS 프로젝트 초기화
- new: 새 컴포넌트/서비스 생성
- config: 설정 관리
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..core import Command
from ...core import Result, Success, Failure, RFSConfig, ConfigManager

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


@dataclass
class ProjectTemplate:
    """프로젝트 템플릿 정의"""
    name: str
    description: str
    files: Dict[str, str]  # 파일 경로 -> 템플릿 내용
    dependencies: List[str]


class InitCommand(Command):
    """RFS 프로젝트 초기화 명령어"""
    
    name = "init"
    description = "RFS v4 프로젝트 초기화"
    
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
                    "rfs.yaml": self._get_config_template()
                },
                dependencies=["rfs-v4>=4.0.0", "pydantic>=2.0.0"]
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
                    "cloudbuild.yaml": self._get_cloudbuild_template()
                },
                dependencies=[
                    "rfs-v4>=4.0.0", "pydantic>=2.0.0",
                    "google-cloud-run>=0.8.0",
                    "google-cloud-tasks>=2.14.0",
                    "google-cloud-monitoring>=2.14.0"
                ]
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
                    "docs/README.md": self._get_readme_template()
                },
                dependencies=[
                    "rfs-v4>=4.0.0", "pydantic>=2.0.0",
                    "google-cloud-run>=0.8.0",
                    "google-cloud-tasks>=2.14.0", 
                    "google-cloud-monitoring>=2.14.0",
                    "pytest>=7.0.0", "pytest-asyncio>=0.21.0"
                ]
            )
        }
    
    async def execute(self, args: List[str]) -> Result[str, str]:
        """프로젝트 초기화 실행"""
        try:
            # 인터랙티브 모드로 설정 수집
            project_config = await self._collect_project_config(args)
            if isinstance(project_config, Failure):
                return project_config
                
            config = project_config.unwrap()
            
            # 프로젝트 디렉토리 생성
            project_path = Path(config["name"])
            if project_path.exists():
                if not Confirm.ask(f"디렉토리 '{config['name']}'가 이미 존재합니다. 계속하시겠습니까?"):
                    return Failure("프로젝트 초기화가 취소되었습니다.")
            else:
                project_path.mkdir(parents=True, exist_ok=True)
            
            # 템플릿 파일들 생성
            template = self.templates[config["template"]]
            await self._create_project_files(project_path, template, config)
            
            # 성공 메시지 출력
            if console:
                success_panel = Panel(
                    f"✅ RFS v4 프로젝트 '{config['name']}' 생성 완료!\n\n"
                    f"📁 프로젝트 경로: {project_path.absolute()}\n"
                    f"🎯 템플릿: {template.name}\n"
                    f"🚀 Cloud Run 최적화: {'예' if config.get('cloud_run') else '아니오'}\n\n"
                    f"다음 단계:\n"
                    f"  cd {config['name']}\n"
                    f"  pip install -r requirements.txt\n"
                    f"  rfs dev  # 개발 서버 시작",
                    title="프로젝트 초기화 완료",
                    border_style="green"
                )
                console.print(success_panel)
            
            return Success(f"RFS v4 프로젝트 '{config['name']}' 생성 완료")
            
        except Exception as e:
            return Failure(f"프로젝트 초기화 실패: {str(e)}")
    
    async def _collect_project_config(self, args: List[str]) -> Result[Dict[str, Any], str]:
        """프로젝트 설정 수집 (인터랙티브)"""
        try:
            config = {}
            
            # 프로젝트 이름
            if args and len(args) > 0:
                config["name"] = args[0]
            else:
                config["name"] = Prompt.ask("프로젝트 이름을 입력하세요", default="my-rfs-project")
            
            # 템플릿 선택
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
                default="cloud-run"
            )
            config["template"] = template_choice
            
            # Cloud Run 설정
            if template_choice in ["cloud-run", "full"]:
                config["cloud_run"] = True
                config["project_id"] = Prompt.ask("Google Cloud 프로젝트 ID", default="my-project")
                config["region"] = Prompt.ask("배포 리전", default="asia-northeast3")
                config["service_name"] = Prompt.ask("서비스 이름", default=config["name"])
            
            # 추가 기능 선택
            config["monitoring"] = Confirm.ask("모니터링 활성화?", default=True)
            config["task_queue"] = Confirm.ask("Task Queue 사용?", default=True)
            
            return Success(config)
            
        except Exception as e:
            return Failure(f"설정 수집 실패: {str(e)}")
    
    async def _create_project_files(self, project_path: Path, template: ProjectTemplate, config: Dict[str, Any]) -> None:
        """프로젝트 파일들 생성"""
        for file_path, content in template.files.items():
            full_path = project_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 템플릿 변수 치환
            processed_content = content.format(**config)
            full_path.write_text(processed_content, encoding="utf-8")
    
    def _get_minimal_main_template(self) -> str:
        return '''"""
RFS v4 Minimal Application

최소 구성 RFS 애플리케이션
"""

import asyncio
from rfs_v4 import RFSConfig, get_config, result_of

async def main():
    """메인 애플리케이션 진입점"""
    config = get_config()
    print(f"🚀 RFS v4 애플리케이션 시작 - {{name}}")
    print(f"⚙️  환경: {{config.environment}}")
    
    # 여기에 비즈니스 로직 추가
    result = result_of(lambda: "Hello, RFS v4!")
    
    if result.is_success():
        print(f"✅ 결과: {{result.unwrap()}}")
    else:
        print(f"❌ 오류: {{result.unwrap_err()}}")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    def _get_cloudrun_main_template(self) -> str:
        return '''"""
RFS v4 Cloud Run Application

Google Cloud Run 최적화 RFS 애플리케이션
"""

import asyncio
from rfs_v4 import (
    RFSConfig, get_config,
    initialize_cloud_run_services,
    get_cloud_run_status,
    result_of
)

async def main():
    """메인 애플리케이션 진입점"""
    config = get_config()
    print(f"🚀 RFS v4 Cloud Run 애플리케이션 시작 - {{name}}")
    
    # Cloud Run 서비스 초기화
    init_result = await initialize_cloud_run_services(
        project_id="{project_id}",
        service_name="{service_name}",
        enable_monitoring={monitoring},
        enable_task_queue={task_queue}
    )
    
    if init_result.get("success"):
        print("✅ Cloud Run 서비스 초기화 완료")
        
        # 상태 확인
        status = await get_cloud_run_status()
        print(f"📊 서비스 상태: {{len(status.get('services', {{}})}}개 서비스 활성화")
        
        # 여기에 비즈니스 로직 추가
        result = result_of(lambda: "Hello, Cloud Run!")
        
        if result.is_success():
            print(f"✅ 결과: {{result.unwrap()}}")
        else:
            print(f"❌ 오류: {{result.unwrap_err()}}")
    else:
        print(f"❌ Cloud Run 서비스 초기화 실패: {{init_result.get('error')}}")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    def _get_minimal_requirements(self) -> str:
        return '''# RFS v4 Minimal Requirements
rfs-v4>=4.0.0
pydantic>=2.0.0
'''
    
    def _get_cloudrun_requirements(self) -> str:
        return '''# RFS v4 Cloud Run Requirements
rfs-v4>=4.0.0
pydantic>=2.0.0
google-cloud-run>=0.8.0
google-cloud-tasks>=2.14.0
google-cloud-monitoring>=2.14.0
uvicorn[standard]>=0.23.0
'''
    
    def _get_env_template(self) -> str:
        return '''# RFS v4 환경 변수
RFS_ENVIRONMENT=development
RFS_DEBUG=true
RFS_LOG_LEVEL=INFO

# Google Cloud (Cloud Run 사용 시)
GOOGLE_CLOUD_PROJECT={project_id}
GOOGLE_CLOUD_REGION={region}
'''


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
            elif component_type == "handler":
                return await self._create_handler(name)
            elif component_type == "task":
                return await self._create_task_handler(name)
            else:
                return Failure(f"지원하지 않는 컴포넌트 타입: {component_type}")
                
        except Exception as e:
            return Failure(f"컴포넌트 생성 실패: {str(e)}")
    
    async def _create_service(self, name: str) -> Result[str, str]:
        """서비스 클래스 생성"""
        service_content = f'''"""
{name.title()} Service

{name} 서비스 구현
"""

from typing import Any, Dict, List, Optional
from rfs_v4 import Result, Success, Failure, stateless


@stateless
class {name.title()}Service:
    """
    {name.title()} 서비스
    
    비즈니스 로직을 구현하세요.
    """
    
    async def process(self, data: Dict[str, Any]) -> Result[Dict[str, Any], str]:
        """
        주요 처리 로직
        
        Args:
            data: 입력 데이터
            
        Returns:
            Result[Dict[str, Any], str]: 처리 결과 또는 오류
        """
        try:
            # TODO: 비즈니스 로직 구현
            result = {{
                "service": "{name}",
                "status": "success",
                "data": data
            }}
            
            return Success(result)
            
        except Exception as e:
            return Failure(f"{name} 서비스 처리 실패: {{str(e)}}")
    
    async def validate(self, data: Dict[str, Any]) -> Result[bool, str]:
        """
        데이터 검증
        
        Args:
            data: 검증할 데이터
            
        Returns:
            Result[bool, str]: 검증 결과
        """
        try:
            # TODO: 검증 로직 구현
            if not data:
                return Failure("데이터가 비어있습니다")
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"데이터 검증 실패: {{str(e)}}")


# 서비스 인스턴스
{name}_service = {name.title()}Service()
'''
        
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
            if action == "show":
                return await self._show_config()
            elif action == "set":
                if len(args) < 3:
                    return Failure("사용법: rfs config set <키> <값>")
                return await self._set_config(args[1], args[2])
            elif action == "get":
                if len(args) < 2:
                    return Failure("사용법: rfs config get <키>")
                return await self._get_config(args[1])
            elif action == "validate":
                return await self._validate_config()
            else:
                return Failure(f"지원하지 않는 액션: {action}")
                
        except Exception as e:
            return Failure(f"설정 관리 실패: {str(e)}")
    
    async def _show_config(self) -> Result[str, str]:
        """현재 설정 표시"""
        try:
            config = get_config()
            
            if console:
                config_table = Table(title="RFS v4 설정", show_header=True, header_style="bold magenta")
                config_table.add_column("키", style="cyan", width=20)
                config_table.add_column("값", style="green")
                config_table.add_column("타입", style="yellow", width=12)
                
                # 설정 항목들 표시
                config_dict = config.model_dump()
                for key, value in config_dict.items():
                    config_table.add_row(
                        key,
                        str(value) if value is not None else "None",
                        type(value).__name__
                    )
                
                console.print(config_table)
            
            return Success("설정 표시 완료")
            
        except Exception as e:
            return Failure(f"설정 조회 실패: {str(e)}")