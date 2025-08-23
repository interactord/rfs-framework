"""
Deployment Commands (RFS v4)

배포 및 운영 관련 명령어들
- deploy: Google Cloud Run 배포
- monitor: 모니터링 대시보드
- logs: 로그 조회
"""

import os
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.prompt import Prompt, Confirm
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..core import Command
from ...core import Result, Success, Failure, get_config

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
            "헬스체크 및 검증"
        ]
    
    async def execute(self, args: List[str]) -> Result[str, str]:
        """배포 실행"""
        try:
            # 배포 설정 수집
            deploy_config = await self._collect_deploy_config(args)
            if isinstance(deploy_config, Failure):
                return deploy_config
            
            config = deploy_config.unwrap()
            
            if console:
                console.print(Panel(
                    f"🚀 RFS v4 Cloud Run 배포 시작\n\n"
                    f"📦 프로젝트: {config['project_id']}\n"
                    f"🌍 리전: {config['region']}\n"
                    f"⚙️  서비스: {config['service_name']}\n"
                    f"🏷️  태그: {config.get('tag', 'latest')}\n"
                    f"⚡ 최소 인스턴스: {config.get('min_instances', 0)}\n"
                    f"📊 최대 인스턴스: {config.get('max_instances', 100)}",
                    title="Cloud Run 배포",
                    border_style="blue"
                ))
            
            # 배포 프로세스 실행
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                
                for i, step in enumerate(self.deployment_steps):
                    task = progress.add_task(f"{step}...", total=100)
                    
                    if i == 0:  # 환경 설정 확인
                        result = await self._verify_environment(config)
                    elif i == 1:  # Docker 이미지 빌드
                        result = await self._build_docker_image(config)
                    elif i == 2:  # Registry 푸시
                        result = await self._push_to_registry(config)
                    elif i == 3:  # Cloud Run 배포
                        result = await self._deploy_to_cloud_run(config)
                    elif i == 4:  # 헬스체크
                        result = await self._verify_deployment(config)
                    
                    if result.is_failure():
                        return result
                    
                    progress.update(task, completed=100)
            
            # 배포 성공 메시지
            service_url = f"https://{config['service_name']}-{config['project_id']}.a.run.app"
            
            if console:
                console.print(Panel(
                    f"✅ 배포 완료!\n\n"
                    f"🌐 서비스 URL: {service_url}\n"
                    f"📊 모니터링: rfs monitor\n"
                    f"📋 로그: rfs logs\n"
                    f"⚙️  설정 업데이트: rfs deploy --update-config\n\n"
                    f"🎉 RFS v4 애플리케이션이 성공적으로 배포되었습니다!",
                    title="배포 성공",
                    border_style="green"
                ))
            
            return Success(f"Cloud Run 배포 완료: {service_url}")
            
        except Exception as e:
            return Failure(f"배포 실패: {str(e)}")
    
    async def _collect_deploy_config(self, args: List[str]) -> Result[Dict[str, Any], str]:
        """배포 설정 수집"""
        try:
            config = {}
            
            # 기본 설정 로드
            rfs_config = get_config()
            
            # 명령행 인자 파싱
            for i, arg in enumerate(args):
                if arg == '--project' and i + 1 < len(args):
                    config['project_id'] = args[i + 1]
                elif arg == '--region' and i + 1 < len(args):
                    config['region'] = args[i + 1]
                elif arg == '--service' and i + 1 < len(args):
                    config['service_name'] = args[i + 1]
                elif arg == '--tag' and i + 1 < len(args):
                    config['tag'] = args[i + 1]
                elif arg == '--min-instances' and i + 1 < len(args):
                    config['min_instances'] = int(args[i + 1])
                elif arg == '--max-instances' and i + 1 < len(args):
                    config['max_instances'] = int(args[i + 1])
            
            # 기본값 설정
            if 'project_id' not in config:
                config['project_id'] = os.getenv('GOOGLE_CLOUD_PROJECT') or Prompt.ask("Google Cloud 프로젝트 ID")
            
            if 'region' not in config:
                config['region'] = os.getenv('GOOGLE_CLOUD_REGION', 'asia-northeast3')
            
            if 'service_name' not in config:
                config['service_name'] = Path.cwd().name.lower().replace('_', '-')
            
            if 'tag' not in config:
                config['tag'] = 'latest'
            
            config.setdefault('min_instances', 0)
            config.setdefault('max_instances', 100)
            config.setdefault('memory', '512Mi')
            config.setdefault('cpu', '1000m')
            config.setdefault('concurrency', 100)
            
            return Success(config)
            
        except Exception as e:
            return Failure(f"배포 설정 수집 실패: {str(e)}")
    
    async def _verify_environment(self, config: Dict[str, Any]) -> Result[str, str]:
        """환경 설정 확인"""
        try:
            # Docker 설치 확인
            process = await asyncio.create_subprocess_exec(
                'docker', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            
            if process.returncode != 0:
                return Failure("Docker가 설치되지 않았거나 실행 중이 아닙니다.")
            
            # gcloud CLI 확인
            process = await asyncio.create_subprocess_exec(
                'gcloud', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            
            if process.returncode != 0:
                return Failure("gcloud CLI가 설치되지 않았습니다.")
            
            # 인증 확인
            process = await asyncio.create_subprocess_exec(
                'gcloud', 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            
            if not stdout.strip():
                return Failure("gcloud 인증이 필요합니다. 'gcloud auth login'을 실행하세요.")
            
            await asyncio.sleep(0.5)  # UI 효과
            return Success("환경 설정 확인 완료")
            
        except Exception as e:
            return Failure(f"환경 확인 실패: {str(e)}")
    
    async def _build_docker_image(self, config: Dict[str, Any]) -> Result[str, str]:
        """Docker 이미지 빌드"""
        try:
            image_name = f"gcr.io/{config['project_id']}/{config['service_name']}:{config['tag']}"
            
            # Docker 빌드 명령어
            cmd = [
                'docker', 'build',
                '-t', image_name,
                '.'
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            await process.wait()
            
            if process.returncode != 0:
                return Failure("Docker 이미지 빌드 실패")
            
            config['image_name'] = image_name
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
            # 모니터링 설정
            config = await self._get_monitoring_config(args)
            
            if console:
                console.print(Panel(
                    f"📊 RFS v4 모니터링 대시보드\n\n"
                    f"🎯 서비스: {config.get('service_name', 'Unknown')}\n"
                    f"🌍 리전: {config.get('region', 'Unknown')}\n"
                    f"⏰ 업데이트 간격: {config.get('refresh_interval', 30)}초",
                    title="모니터링 대시보드",
                    border_style="blue"
                ))
            
            # 실시간 모니터링 시작
            await self._start_monitoring_dashboard(config)
            
            return Success("모니터링 대시보드 종료")
            
        except KeyboardInterrupt:
            return Success("모니터링이 중지되었습니다.")
        except Exception as e:
            return Failure(f"모니터링 실패: {str(e)}")
    
    async def _get_monitoring_config(self, args: List[str]) -> Dict[str, Any]:
        """모니터링 설정 수집"""
        config = {
            'service_name': None,
            'project_id': os.getenv('GOOGLE_CLOUD_PROJECT'),
            'region': os.getenv('GOOGLE_CLOUD_REGION', 'asia-northeast3'),
            'refresh_interval': 30
        }
        
        # 인자 파싱
        for i, arg in enumerate(args):
            if arg == '--service' and i + 1 < len(args):
                config['service_name'] = args[i + 1]
            elif arg == '--interval' and i + 1 < len(args):
                config['refresh_interval'] = int(args[i + 1])
        
        if not config['service_name']:
            config['service_name'] = Path.cwd().name.lower().replace('_', '-')
        
        return config
    
    async def _start_monitoring_dashboard(self, config: Dict[str, Any]) -> None:
        """실시간 모니터링 대시보드 시작"""
        if not console:
            return
        
        while True:
            # 메트릭 수집
            metrics = await self._collect_metrics(config)
            
            # 대시보드 테이블 생성
            dashboard = self._create_dashboard_table(metrics)
            
            # 화면 갱신
            console.clear()
            console.print(dashboard)
            console.print(f"\n🔄 마지막 업데이트: {datetime.now().strftime('%H:%M:%S')} | Ctrl+C로 종료")
            
            # 대기
            await asyncio.sleep(config['refresh_interval'])
    
    async def _collect_metrics(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """메트릭 수집"""
        # 시뮬레이션된 메트릭 (실제로는 Cloud Monitoring API 사용)
        import random
        
        return {
            'request_count': random.randint(100, 1000),
            'error_rate': random.uniform(0, 5),
            'avg_latency': random.uniform(100, 500),
            'active_instances': random.randint(1, 10),
            'memory_usage': random.uniform(30, 80),
            'cpu_usage': random.uniform(10, 60)
        }


class LogsCommand(Command):
    """로그 조회 명령어"""
    
    name = "logs"
    description = "RFS 애플리케이션 로그 조회"
    
    async def execute(self, args: List[str]) -> Result[str, str]:
        """로그 조회 실행"""
        try:
            # 로그 옵션 파싱
            options = self._parse_log_options(args)
            
            if console:
                console.print(Panel(
                    f"📋 RFS v4 로그 조회\n\n"
                    f"🎯 서비스: {options.get('service_name', 'Unknown')}\n"
                    f"📅 기간: {options.get('since', '1h')}\n"
                    f"🔍 필터: {options.get('filter', '없음')}\n"
                    f"📊 라인 수: {options.get('lines', 100)}",
                    title="로그 조회",
                    border_style="blue"
                ))
            
            # 로그 조회 및 표시
            await self._fetch_and_display_logs(options)
            
            return Success("로그 조회 완료")
            
        except KeyboardInterrupt:
            return Success("로그 조회가 중지되었습니다.")
        except Exception as e:
            return Failure(f"로그 조회 실패: {str(e)}")
    
    def _parse_log_options(self, args: List[str]) -> Dict[str, Any]:
        """로그 옵션 파싱"""
        options = {
            'service_name': None,
            'since': '1h',
            'lines': 100,
            'filter': None,
            'follow': False,
            'level': None
        }
        
        for i, arg in enumerate(args):
            if arg == '--service' and i + 1 < len(args):
                options['service_name'] = args[i + 1]
            elif arg == '--since' and i + 1 < len(args):
                options['since'] = args[i + 1]
            elif arg == '--lines' and i + 1 < len(args):
                options['lines'] = int(args[i + 1])
            elif arg == '--filter' and i + 1 < len(args):
                options['filter'] = args[i + 1]
            elif arg in ['-f', '--follow']:
                options['follow'] = True
            elif arg == '--level' and i + 1 < len(args):
                options['level'] = args[i + 1]
        
        if not options['service_name']:
            options['service_name'] = Path.cwd().name.lower().replace('_', '-')
        
        return options
    
    async def _fetch_and_display_logs(self, options: Dict[str, Any]) -> None:
        """로그 조회 및 표시"""
        # gcloud logs 명령어 구성
        cmd = [
            'gcloud', 'logs', 'read',
            f'resource.type="cloud_run_revision" resource.labels.service_name="{options["service_name"]}"',
            '--format=value(timestamp,severity,jsonPayload.message,textPayload)',
            f'--limit={options["lines"]}',
            f'--freshness={options["since"]}'
        ]
        
        if options.get('filter'):
            cmd.extend(['--filter', options['filter']])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            if options['follow']:
                # 실시간 로그 스트리밍
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    
                    log_entry = line.decode().strip()
                    if log_entry:
                        self._display_log_entry(log_entry)
            else:
                # 한번에 로그 조회
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logs = stdout.decode().strip().split('\n')
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
        
        # 로그 레벨에 따른 색상 적용
        if 'ERROR' in log_entry:
            console.print(log_entry, style="red")
        elif 'WARNING' in log_entry or 'WARN' in log_entry:
            console.print(log_entry, style="yellow")
        elif 'INFO' in log_entry:
            console.print(log_entry, style="blue")
        elif 'DEBUG' in log_entry:
            console.print(log_entry, style="dim")
        else:
            console.print(log_entry)