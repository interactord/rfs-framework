"""
CI/CD Pipeline Management (RFS v4)

지속적 통합 및 배포 파이프라인 관리
- GitHub Actions 통합
- Google Cloud Build 지원
- 자동화된 테스트 및 배포
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ...core.result import Failure, Result, Success

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class DeploymentStrategy(Enum):
    """배포 전략"""

    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    IMMEDIATE = "immediate"


class PipelineStage(Enum):
    """파이프라인 단계"""

    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    QUALITY_CHECK = "quality_check"
    DEPLOY = "deploy"
    SMOKE_TEST = "smoke_test"
    ROLLBACK = "rollback"


@dataclass
class PipelineConfig:
    """파이프라인 설정"""

    name: str
    trigger_branches: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
    deployment_strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    environment_configs: Dict[str, Any] = field(default_factory=dict)
    notifications: Dict[str, Any] = field(default_factory=dict)


class CICDManager:
    """CI/CD 파이프라인 매니저"""

    def __init__(self, project_path=None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.github_actions_path = self.project_path / ".github" / "workflows"
        self.cloudbuild_path = self.project_path / "cloudbuild.yaml"

    async def initialize_github_actions(
        self, config: PipelineConfig
    ) -> Result[str, str]:
        """GitHub Actions 워크플로우 초기화"""
        try:
            self.github_actions_path.mkdir(parents=True, exist_ok=True)
            ci_workflow = self._generate_ci_workflow(config)
            ci_path = self.github_actions_path / "ci.yml"
            with open(ci_path, "w", encoding="utf-8") as f:
                yaml.dump(ci_workflow, f, default_flow_style=False)
            cd_workflow = self._generate_cd_workflow(config)
            cd_path = self.github_actions_path / "cd.yml"
            with open(cd_path, "w", encoding="utf-8") as f:
                yaml.dump(cd_workflow, f, default_flow_style=False)
            if console:
                console.print(
                    Panel(
                        f"✅ GitHub Actions 워크플로우 생성 완료\n\n📁 CI 워크플로우: {ci_path}\n📁 CD 워크플로우: {cd_path}\n🎯 트리거 브랜치: {', '.join(config.trigger_branches)}\n🚀 배포 전략: {config.deployment_strategy.value}",
                        title="GitHub Actions 설정",
                        border_style="green",
                    )
                )
            return Success("GitHub Actions 워크플로우 초기화 완료")
        except Exception as e:
            return Failure(f"GitHub Actions 초기화 실패: {str(e)}")

    def _generate_ci_workflow(self, config: PipelineConfig) -> Dict[str, Any]:
        """CI 워크플로우 생성"""
        workflow = {
            "name": f"CI - {config.name}",
            "on": {
                "push": {"branches": config.trigger_branches},
                "pull_request": {"branches": config.trigger_branches},
            },
            "jobs": {
                "ci": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4", "name": "Checkout code"},
                        {
                            "uses": "actions/setup-python@v4",
                            "with": {"python-version": "3.11"},
                            "name": "Set up Python",
                        },
                    ],
                }
            },
        }
        steps = workflow["jobs"]["ci"]["steps"]
        if PipelineStage.BUILD in config.stages:
            steps = steps + [
                {
                    "name": "Install dependencies",
                    "run": "pip install -r requirements.txt",
                },
                {
                    "name": "Build application",
                    "run": 'python setup.py build || echo "No setup.py found, skipping build"',
                },
            ]
        if PipelineStage.TEST in config.stages:
            steps = steps + [
                {
                    "name": "Run tests",
                    "run": "python -m pytest tests/ -v --cov=. --cov-report=xml",
                },
                {
                    "name": "Upload coverage",
                    "uses": "codecov/codecov-action@v3",
                    "with": {"file": "./coverage.xml"},
                },
            ]
        if PipelineStage.QUALITY_CHECK in config.stages:
            steps = steps + [
                {
                    "name": "Code quality check",
                    "run": "ruff check . && black --check .",
                },
                {
                    "name": "Type checking",
                    "run": 'mypy . || echo "mypy not configured, skipping type check"',
                },
            ]
        if PipelineStage.SECURITY_SCAN in config.stages:
            steps = steps + [
                {
                    "name": "Security scan",
                    "run": "safety check || pip install safety && safety check",
                },
                {
                    "name": "Dependency vulnerability scan",
                    "run": "pip-audit || pip install pip-audit && pip-audit",
                },
            ]
        return workflow

    def _generate_cd_workflow(self, config: PipelineConfig) -> Dict[str, Any]:
        """CD 워크플로우 생성"""
        workflow = {
            "name": f"CD - {config.name}",
            "on": {
                "push": {"branches": ["main"]},
                "workflow_run": {
                    "workflows": [f"CI - {config.name}"],
                    "types": ["completed"],
                    "branches": ["main"],
                },
            },
            "jobs": {
                "deploy": {
                    "runs-on": "ubuntu-latest",
                    "if": "${{ github.event.workflow_run.conclusion == 'success' }}",
                    "steps": [
                        {"uses": "actions/checkout@v4", "name": "Checkout code"},
                        {
                            "name": "Set up Google Cloud SDK",
                            "uses": "google-github-actions/setup-gcloud@v1",
                            "with": {
                                "project_id": "${{ secrets.GCP_PROJECT_ID }}",
                                "service_account_key": "${{ secrets.GCP_SA_KEY }}",
                                "export_default_credentials": True,
                            },
                        },
                    ],
                }
            },
        }
        steps = workflow["jobs"]["deploy"]["steps"]
        if config.deployment_strategy == DeploymentStrategy.ROLLING:
            steps = steps + [
                {
                    "name": "Deploy to Cloud Run (Rolling)",
                    "run": "gcloud run deploy ${{ secrets.SERVICE_NAME }} --source . --region=${{ secrets.GCP_REGION }} --allow-unauthenticated --max-instances=10",
                }
            ]
        elif config.deployment_strategy == DeploymentStrategy.BLUE_GREEN:
            steps = steps + [
                {
                    "name": "Deploy to Cloud Run (Blue-Green)",
                    "run": "\n                        # 새 리비전 배포 (트래픽 0%)\n                        gcloud run deploy ${{ secrets.SERVICE_NAME }} --source . --region=${{ secrets.GCP_REGION }} --no-traffic --tag=green\n                        \n                        # 헬스체크\n                        sleep 30\n                        curl -f https://green---${{ secrets.SERVICE_NAME }}-${{ secrets.GCP_PROJECT_ID }}.a.run.app/health || exit 1\n                        \n                        # 트래픽 전환\n                        gcloud run services update-traffic ${{ secrets.SERVICE_NAME }} --to-tags=green=100 --region=${{ secrets.GCP_REGION }}\n                    ",
                }
            ]
        if PipelineStage.SMOKE_TEST in config.stages:
            steps = steps + [
                {
                    "name": "Smoke test",
                    "run": '\n                    sleep 30\n                    curl -f https://${{ secrets.SERVICE_NAME }}-${{ secrets.GCP_PROJECT_ID }}.a.run.app/health\n                    echo "Smoke test passed!"\n                ',
                }
            ]
        return workflow

    async def initialize_cloud_build(self, config: PipelineConfig) -> Result[str, str]:
        """Google Cloud Build 설정 초기화"""
        try:
            cloudbuild_config = self._generate_cloudbuild_config(config)
            with open(self.cloudbuild_path, "w", encoding="utf-8") as f:
                yaml.dump(cloudbuild_config, f, default_flow_style=False)
            if console:
                console.print(
                    Panel(
                        f"✅ Google Cloud Build 설정 생성 완료\n\n📁 설정 파일: {self.cloudbuild_path}\n🔧 단계: {len(config.stages)}개\n🚀 배포 전략: {config.deployment_strategy.value}",
                        title="Cloud Build 설정",
                        border_style="blue",
                    )
                )
            return Success("Cloud Build 설정 초기화 완료")
        except Exception as e:
            return Failure(f"Cloud Build 초기화 실패: {str(e)}")

    def _generate_cloudbuild_config(self, config: PipelineConfig) -> Dict[str, Any]:
        """Cloud Build 설정 생성"""
        steps = []
        if PipelineStage.BUILD in config.stages:
            steps = steps + [
                {
                    "name": "python:3.11",
                    "entrypoint": "pip",
                    "args": ["install", "-r", "requirements.txt"],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": [
                        "build",
                        "-t",
                        "gcr.io/$PROJECT_ID/${_SERVICE_NAME}:$COMMIT_SHA",
                        "-t",
                        "gcr.io/$PROJECT_ID/${_SERVICE_NAME}:latest",
                        ".",
                    ],
                },
            ]
        if PipelineStage.TEST in config.stages:
            steps = steps + [
                {
                    "name": "python:3.11",
                    "entrypoint": "python",
                    "args": ["-m", "pytest", "tests/", "-v"],
                }
            ]
        if PipelineStage.QUALITY_CHECK in config.stages:
            steps = steps + [
                {
                    "name": "python:3.11",
                    "entrypoint": "pip",
                    "args": ["install", "ruff", "black", "mypy"],
                },
                {
                    "name": "python:3.11",
                    "entrypoint": "bash",
                    "args": ["-c", "ruff check . && black --check . && mypy . || true"],
                },
            ]
        steps = steps + [
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["push", "--all-tags", "gcr.io/$PROJECT_ID/${_SERVICE_NAME}"],
            }
        ]
        if PipelineStage.DEPLOY in config.stages:
            deploy_args = [
                "run",
                "deploy",
                "${_SERVICE_NAME}",
                "--image",
                "gcr.io/$PROJECT_ID/${_SERVICE_NAME}:$COMMIT_SHA",
                "--region",
                "${_REGION}",
                "--platform",
                "managed",
                "--allow-unauthenticated",
            ]
            if config.deployment_strategy == DeploymentStrategy.CANARY:
                deploy_args = deploy_args + ["--traffic", "${_TRAFFIC_PERCENT}"]
            steps = steps + [
                {
                    "name": "gcr.io/google.com/cloudsdktool/cloud-sdk",
                    "entrypoint": "gcloud",
                    "args": deploy_args,
                }
            ]
        cloudbuild_config = {
            "steps": steps,
            "substitutions": {
                "_SERVICE_NAME": config.name.lower().replace("_", "-"),
                "_REGION": "asia-northeast3",
                "_TRAFFIC_PERCENT": "10",
            },
            "options": {
                "logging": "CLOUD_LOGGING_ONLY",
                "substitution_option": "ALLOW_LOOSE",
            },
        }
        return cloudbuild_config

    async def create_deployment_config(
        self, config: PipelineConfig
    ) -> Result[str, str]:
        """배포 설정 파일 생성"""
        try:
            k8s_config = self._generate_kubernetes_config(config)
            k8s_path = self.project_path / "k8s-deployment.yaml"
            with open(k8s_path, "w", encoding="utf-8") as f:
                yaml.dump(k8s_config, f, default_flow_style=False)
            compose_config = self._generate_docker_compose_config(config)
            compose_path = self.project_path / "docker-compose.yml"
            with open(compose_path, "w", encoding="utf-8") as f:
                yaml.dump(compose_config, f, default_flow_style=False)
            if console:
                console.print(
                    Panel(
                        f"✅ 배포 설정 파일 생성 완료\n\n☸️  Kubernetes: {k8s_path}\n🐳 Docker Compose: {compose_path}",
                        title="배포 설정",
                        border_style="cyan",
                    )
                )
            return Success("배포 설정 파일 생성 완료")
        except Exception as e:
            return Failure(f"배포 설정 생성 실패: {str(e)}")

    def _generate_kubernetes_config(self, config: PipelineConfig) -> Dict[str, Any]:
        """Kubernetes 배포 설정 생성"""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": config.name,
                "labels": {"app": config.name, "version": "v1"},
            },
            "spec": {
                "replicas": 3,
                "selector": {"matchLabels": {"app": config.name}},
                "template": {
                    "metadata": {"labels": {"app": config.name}},
                    "spec": {
                        "containers": [
                            {
                                "name": config.name,
                                "image": f"gcr.io/PROJECT_ID/{config.name}:latest",
                                "ports": [{"containerPort": 8080}],
                                "env": [
                                    {"name": "RFS_ENVIRONMENT", "value": "production"}
                                ],
                                "resources": {
                                    "limits": {"memory": "512Mi", "cpu": "500m"},
                                    "requests": {"memory": "256Mi", "cpu": "250m"},
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": 8080},
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                },
                            }
                        ]
                    },
                },
            },
        }

    def _generate_docker_compose_config(self, config: PipelineConfig) -> Dict[str, Any]:
        """Docker Compose 설정 생성"""
        return {
            "version": "3.8",
            "services": {
                config.name: {
                    "build": ".",
                    "ports": ["8080:8080"],
                    "environment": ["RFS_ENVIRONMENT=development", "RFS_DEBUG=true"],
                    "volumes": [".:/app", "/app/__pycache__"],
                    "restart": "unless-stopped",
                    "healthcheck": {
                        "test": ["CMD", "curl", "-f", "http://localhost:8080/health"],
                        "interval": "30s",
                        "timeout": "10s",
                        "retries": 3,
                    },
                }
            },
        }

    async def get_pipeline_status(self) -> Result[Dict[str, Any], str]:
        """파이프라인 상태 조회"""
        try:
            status = {
                "github_actions": {
                    "configured": self.github_actions_path.exists(),
                    "workflows": [],
                },
                "cloud_build": {"configured": self.cloudbuild_path.exists()},
                "deployment_configs": {
                    "kubernetes": (self.project_path / "k8s-deployment.yaml").exists(),
                    "docker_compose": (
                        self.project_path / "docker-compose.yml"
                    ).exists(),
                },
            }
            if self.github_actions_path.exists():
                for workflow_file in self.github_actions_path.glob("*.yml"):
                    status.get("github_actions")["workflows"] = get("github_actions")[
                        "workflows"
                    ] + [workflow_file.name]
            return Success(status)
        except Exception as e:
            return Failure(f"파이프라인 상태 조회 실패: {str(e)}")
