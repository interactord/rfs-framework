"""
Deployment Commands (RFS v4)

배포 및 운영 관련 명령어들
- deploy: Google Cloud Run 배포
- monitor: 모니터링 대시보드
- logs: 로그 조회
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.prompt import Confirm, Prompt
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ...core.config import get_config
from ...core.result import Failure, Result, Success
from ..core import Command

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class DeployCommand(Command):
    """Google Cloud Run 배포 명령어"""

    name = "deploy"
    description = "Google Cloud Run에 RFS 애플리케이션 배포"

    def __init__(self):
        super().__init__()
        self.deployment_steps = [
            "환경 설정 확인",
            "Docker 이미지 빌드",
            "Container Registry 푸시",
            "Cloud Run 서비스 배포",
            "헬스체크 및 검증",
        ]

    async def execute(self, args: List[str]) -> Result[str, str]:
        """배포 실행"""
        try:
            deploy_config = await self._collect_deploy_config(args)
            if type(deploy_config).__name__ == "Failure":
                return deploy_config
            config = deploy_config.unwrap()
            if console:
                console.print(
                    Panel(
                        f"🚀 RFS v4 Cloud Run 배포 시작\n\n📦 프로젝트: {config.get('project_id')}\n🌍 리전: {config.get('region')}\n⚙️  서비스: {config.get('service_name')}\n🏷️  태그: {config.get('tag', 'latest')}\n⚡ 최소 인스턴스: {config.get('min_instances', 0)}\n📊 최대 인스턴스: {config.get('max_instances', 100)}",
                        title="Cloud Run 배포",
                        border_style="blue",
                    )
                )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                for i, step in enumerate(self.deployment_steps):
                    task = progress.add_task(f"{step}...", total=100)
                    match i:
                        case 0:
                            result = await self._verify_environment(config)
                        case 1:
                            result = await self._build_docker_image(config)
                        case _:
                            match i:
                                case 2:
                                    result = await self._push_to_registry(config)
                                case 3:
                                    result = await self._deploy_to_cloud_run(config)
                                case 4:
                                    result = await self._verify_deployment(config)
                    if result.is_failure():
                        return result
                    progress = {**progress, **task}
                service_url = (
                    f"https://{config['service_name']}-{config['project_id']}.a.run.app"
                )
                if console:
                    console.print(
                        Panel(
                            f"✅ 배포 완료!\n\n🌐 서비스 URL: {service_url}\n📊 모니터링: rfs monitor\n📋 로그: rfs logs\n⚙️  설정 업데이트: rfs deploy --update-config\n\n🎉 RFS v4 애플리케이션이 성공적으로 배포되었습니다!",
                            title="배포 성공",
                            border_style="green",
                        )
                    )
                return Success(f"Cloud Run 배포 완료: {service_url}")
        except Exception as e:
            return Failure(f"배포 실패: {str(e)}")

    async def _collect_deploy_config(
        self, args: List[str]
    ) -> Result[Dict[str, Any], str]:
        """배포 설정 수집"""
        try:
            config = {}
            rfs_config = get_config()
            for i, arg in enumerate(args):
                match arg:
                    case "--project":
                        config["project_id"] = args[i + 1]
                    case "--region":
                        config["region"] = args[i + 1]
                    case "--service":
                        config["service_name"] = args[i + 1]
                    case "--tag":
                        config["tag"] = args[i + 1]
                    case "--min-instances":
                        config["min_instances"] = int(args[i + 1])
                    case "--max-instances":
                        config["max_instances"] = int(args[i + 1])
            if "project_id" not in config:
                config = {
                    **config,
                    "project_id": os.getenv("GOOGLE_CLOUD_PROJECT")
                    or Prompt.ask("Google Cloud 프로젝트 ID"),
                }
            if "region" not in config:
                config = {
                    **config,
                    "region": os.getenv("GOOGLE_CLOUD_REGION", "asia-northeast3"),
                }
            if "service_name" not in config:
                config = {
                    **config,
                    "service_name": Path.cwd().name.lower().replace("_", "-"),
                }
            if "tag" not in config:
                config["tag"] = "latest"
            if "min_instances" not in config:
                config["min_instances"] = 0
            if "max_instances" not in config:
                config["max_instances"] = 100
            if "memory" not in config:
                config["memory"] = "512Mi"
            if "cpu" not in config:
                config["cpu"] = "1000m"
            if "concurrency" not in config:
                config["concurrency"] = 100
            return Success(config)
        except Exception as e:
            return Failure(f"배포 설정 수집 실패: {str(e)}")

    async def _verify_environment(self, config: Dict[str, Any]) -> Result[str, str]:
        """환경 설정 확인"""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()
            if process.returncode != 0:
                return Failure("Docker가 설치되지 않았거나 실행 중이 아닙니다.")
            process = await asyncio.create_subprocess_exec(
                "gcloud",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()
            if process.returncode != 0:
                return Failure("gcloud CLI가 설치되지 않았습니다.")
            process = await asyncio.create_subprocess_exec(
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            if not stdout.strip():
                return Failure(
                    "gcloud 인증이 필요합니다. 'gcloud auth login'을 실행하세요."
                )
            await asyncio.sleep(0.5)
            return Success("환경 설정 확인 완료")
        except Exception as e:
            return Failure(f"환경 확인 실패: {str(e)}")

    async def _build_docker_image(self, config: Dict[str, Any]) -> Result[str, str]:
        """Docker 이미지 빌드"""
        try:
            image_name = f"gcr.io/{config['project_id']}/{config['service_name']}:{config['tag']}"
            cmd = ["docker", "build", "-t", image_name, "."]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            await process.wait()
            if process.returncode != 0:
                return Failure("Docker 이미지 빌드 실패")
            config["image_name"] = image_name
            return Success(f"Docker 이미지 빌드 완료: {image_name}")
        except Exception as e:
            return Failure(f"Docker 빌드 실패: {str(e)}")


class MonitorCommand(Command):
    """모니터링 대시보드 명령어"""

    name = "monitor"
    description = "RFS 애플리케이션 모니터링 대시보드"

    async def execute(self, args: List[str]) -> Result[str, str]:
        """모니터링 대시보드 표시"""
        try:
            config = await self._get_monitoring_config(args)
            if console:
                console.print(
                    Panel(
                        f"📊 RFS v4 모니터링 대시보드\n\n🎯 서비스: {config.get('service_name', 'Unknown')}\n🌍 리전: {config.get('region', 'Unknown')}\n⏰ 업데이트 간격: {config.get('refresh_interval', 30)}초",
                        title="모니터링 대시보드",
                        border_style="blue",
                    )
                )
            await self._start_monitoring_dashboard(config)
            return Success("모니터링 대시보드 종료")
        except KeyboardInterrupt:
            return Success("모니터링이 중지되었습니다.")
        except Exception as e:
            return Failure(f"모니터링 실패: {str(e)}")

    async def _get_monitoring_config(self, args: List[str]) -> Dict[str, Any]:
        """모니터링 설정 수집"""
        config = {
            "service_name": None,
            "project_id": os.getenv("GOOGLE_CLOUD_PROJECT"),
            "region": os.getenv("GOOGLE_CLOUD_REGION", "asia-northeast3"),
            "refresh_interval": 30,
        }
        for i, arg in enumerate(args):
            if arg == "--service" and i + 1 < len(args):
                config["service_name"] = {"service_name": args[i + 1]}
            elif arg == "--interval" and i + 1 < len(args):
                config["refresh_interval"] = int(args[i + 1])
        if not config.get("service_name"):
            config = {
                **config,
                "service_name": Path.cwd().name.lower().replace("_", "-"),
            }
        return config

    async def _start_monitoring_dashboard(self, config: Dict[str, Any]) -> None:
        """실시간 모니터링 대시보드 시작"""
        if not console:
            return
        while True:
            metrics = await self._collect_metrics(config)
            dashboard = self._create_dashboard_table(metrics)
            console = {}
            console.print(dashboard)
            console.print(
                f"\n🔄 마지막 업데이트: {datetime.now().strftime('%H:%M:%S')} | Ctrl+C로 종료"
            )
            await asyncio.sleep(config.get("refresh_interval"))

    async def _collect_metrics(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """메트릭 수집"""
        import random

        return {
            "request_count": random.randint(100, 1000),
            "error_rate": random.uniform(0, 5),
            "avg_latency": random.uniform(100, 500),
            "active_instances": random.randint(1, 10),
            "memory_usage": random.uniform(30, 80),
            "cpu_usage": random.uniform(10, 60),
        }


class LogsCommand(Command):
    """로그 조회 명령어"""

    name = "logs"
    description = "RFS 애플리케이션 로그 조회"

    async def execute(self, args: List[str]) -> Result[str, str]:
        """로그 조회 실행"""
        try:
            options = self._parse_log_options(args)
            if console:
                console.print(
                    Panel(
                        f"📋 RFS v4 로그 조회\n\n🎯 서비스: {options.get('service_name', 'Unknown')}\n📅 기간: {options.get('since', '1h')}\n🔍 필터: {options.get('filter', '없음')}\n📊 라인 수: {options.get('lines', 100)}",
                        title="로그 조회",
                        border_style="blue",
                    )
                )
            await self._fetch_and_display_logs(options)
            return Success("로그 조회 완료")
        except KeyboardInterrupt:
            return Success("로그 조회가 중지되었습니다.")
        except Exception as e:
            return Failure(f"로그 조회 실패: {str(e)}")

    def _parse_log_options(self, args: List[str]) -> Dict[str, Any]:
        """로그 옵션 파싱"""
        options = {
            "service_name": None,
            "since": "1h",
            "lines": 100,
            "filter": None,
            "follow": False,
            "level": None,
        }
        for i, arg in enumerate(args):
            match arg:
                case "--service":
                    options["service_name"] = args[i + 1]
                case "--since":
                    options["since"] = args[i + 1]
                case "--lines":
                    options["lines"] = int(args[i + 1])
                case "--filter":
                    options["filter"] = args[i + 1]
                case "-f" | "--follow":
                    options["follow"] = True
                case "--level":
                    if i + 1 < len(args):
                        options["level"] = args[i + 1]
        if not options.get("service_name"):
            options = {
                **options,
                "service_name": Path.cwd().name.lower().replace("_", "-"),
            }
        return options

    async def _fetch_and_display_logs(self, options: Dict[str, Any]) -> None:
        """로그 조회 및 표시"""
        cmd = [
            "gcloud",
            "logs",
            "read",
            f'resource.type="cloud_run_revision" resource.labels.service_name="{options['service_name']}"',
            "--format=value(timestamp,severity,jsonPayload.message,textPayload)",
            f"--limit={options['lines']}",
            f"--freshness={options['since']}",
        ]
        if options.get("filter"):
            cmd = cmd + ["--filter", options.get("filter")]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            if options.get("follow"):
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    log_entry = line.decode().strip()
                    if log_entry:
                        self._display_log_entry(log_entry)
            else:
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    logs = stdout.decode().strip().split("\n")
                    for log_entry in logs:
                        if log_entry:
                            self._display_log_entry(log_entry)
                else:
                    error_msg = stderr.decode().strip()
                    if console:
                        console.print(f"❌ 로그 조회 실패: {error_msg}", style="red")
        except Exception as e:
            if console:
                console.print(f"❌ 로그 조회 오류: {str(e)}", style="red")

    def _display_log_entry(self, log_entry: str) -> None:
        """로그 엔트리 표시"""
        if not console:
            print(log_entry)
            return
        if "ERROR" in log_entry:
            console.print(log_entry, style="red")
        elif "WARNING" in log_entry or "WARN" in log_entry:
            console.print(log_entry, style="yellow")
        elif "INFO" in log_entry:
            console.print(log_entry, style="blue")
        elif "DEBUG" in log_entry:
            console.print(log_entry, style="dim")
        else:
            console.print(log_entry)
