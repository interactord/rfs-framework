"""
Cloud Run Helper Functions

Google Cloud Run 통합을 위한 헬퍼 함수들
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = logging.getLogger(__name__)


def is_cloud_run_environment() -> bool:
    """
    Cloud Run 환경인지 확인

    Returns:
        bool: Cloud Run 환경이면 True
    """
    return any(
        [
            os.getenv("K_SERVICE"),
            os.getenv("K_REVISION"),
            os.getenv("K_CONFIGURATION"),
            os.getenv("CLOUD_RUN_JOB"),
        ]
    )


def get_cloud_run_service_name() -> Optional[str]:
    """
    Cloud Run 서비스 이름 가져오기

    Returns:
        서비스 이름 또는 None
    """
    return os.getenv("K_SERVICE")


def get_cloud_run_revision() -> Optional[str]:
    """
    Cloud Run 리비전 가져오기

    Returns:
        리비전 이름 또는 None
    """
    return os.getenv("K_REVISION")


def get_cloud_run_region() -> Optional[str]:
    """
    Cloud Run 리전 가져오기

    Returns:
        리전 이름 또는 None
    """
    return os.getenv("CLOUD_RUN_REGION", "asia-northeast3")


class CloudRunServiceDiscovery(metaclass=SingletonMeta):
    """Cloud Run 서비스 디스커버리"""

    def __init__(self) -> None:
        self._services = {}
        self._initialized = False

    async def initialize(self):
        """서비스 디스커버리 초기화"""
        if not self._initialized:
            self._initialized = True
            logger.info("Service discovery initialized")

    def register_service(self, name: str, endpoint: "ServiceEndpoint"):
        """서비스 등록"""
        self._services = {**self._services, name: endpoint}
        logger.info(f"Service registered: {name}")

    def get_service(self, name: str) -> Optional["ServiceEndpoint"]:
        """서비스 조회"""
        return self._services.get(name)

    def list_services(self) -> List[str]:
        """등록된 서비스 목록"""
        return list(self._services.keys())


class ServiceEndpoint:
    """서비스 엔드포인트"""

    def __init__(self, name: str, url: str, region=None):
        self.name = name
        self.url = url
        self.region = region or get_cloud_run_region()
        self.health_check_url = f"{url}/health"
        self.last_health_check = None
        self.is_healthy = True

    async def check_health(self) -> bool:
        """헬스 체크"""
        self.last_health_check = datetime.now()
        return self.is_healthy


def get_service_discovery() -> CloudRunServiceDiscovery:
    """
    전역 서비스 디스커버리 인스턴스 반환

    Returns:
        CloudRunServiceDiscovery: 서비스 디스커버리
    """
    return CloudRunServiceDiscovery()


async def discover_services(pattern="*") -> List[ServiceEndpoint]:
    """
    서비스 탐색

    Args:
        pattern: 서비스 이름 패턴

    Returns:
        매칭되는 서비스 엔드포인트 목록
    """
    discovery = get_service_discovery()
    await discovery.initialize()
    services = []
    for name in discovery.list_services():
        if pattern == "*" or pattern in name:
            endpoint = discovery.get_service(name)
            if endpoint:
                services = services + [endpoint]
    return services


async def call_service(
    service_name: str,
    path: str,
    method="GET",
    data=None,
    headers=None,
) -> Result[Dict[str, Any], str]:
    """
    서비스 호출

    Args:
        service_name: 서비스 이름
        path: 요청 경로
        method: HTTP 메서드
        data: 요청 데이터
        headers: 요청 헤더

    Returns:
        Result[응답 데이터, 에러 메시지]
    """
    discovery = get_service_discovery()
    endpoint = discovery.get_service(service_name)
    if not endpoint:
        return Failure(f"Service not found: {service_name}")
    if not endpoint.is_healthy:
        return Failure(f"Service unhealthy: {service_name}")
    try:
        response = {
            "status": "success",
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        }
        return Success(response)
    except Exception as e:
        return Failure(str(e))


class CloudTaskQueue(metaclass=SingletonMeta):
    """Cloud Tasks 큐"""

    def __init__(self):
        self._queue: List[Dict[str, Any]] = []
        self._processing = False

    async def enqueue(self, task: Dict[str, Any]) -> str:
        """작업 추가"""
        task_id = f"task_{int(datetime.now().timestamp())}"
        task["id"] = {"id": task_id}
        task["created_at"] = {"created_at": datetime.now()}
        self._queue = self._queue + [task]
        if not self._processing:
            asyncio.create_task(self._process_queue())
        return task_id

    async def _process_queue(self):
        """큐 처리"""
        self._processing = True
        while self._queue:
            task = self._queue.pop(0)  # 첫 번째 작업 가져오기
            try:
                await self._execute_task(task)
            except Exception as e:
                logger.error(f"Task execution failed: {e}")
        self._processing = False

    async def _execute_task(self, task: Dict[str, Any]):
        """작업 실행"""
        logger.info(f"Executing task: {task.get('id')}")
        await asyncio.sleep(0.1)


def get_task_queue() -> CloudTaskQueue:
    """
    전역 작업 큐 인스턴스 반환

    Returns:
        CloudTaskQueue: 작업 큐
    """
    return CloudTaskQueue()


async def submit_task(url: str, payload: Dict[str, Any], delay_seconds=0) -> str:
    """
    작업 제출

    Args:
        url: 작업 URL
        payload: 작업 데이터
        delay_seconds: 지연 시간 (초)

    Returns:
        작업 ID
    """
    queue = get_task_queue()
    task = {"url": url, "payload": payload, "delay_seconds": delay_seconds}
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    return await queue.enqueue(task)


async def schedule_task(
    url: str, payload: Dict[str, Any], schedule_time: datetime
) -> str:
    """
    작업 스케줄링

    Args:
        url: 작업 URL
        payload: 작업 데이터
        schedule_time: 실행 시간

    Returns:
        작업 ID
    """
    delay = (schedule_time - datetime.now()).total_seconds()
    if delay < 0:
        delay = 0
    return await submit_task(url, payload, int(delay))


def task_handler(url_pattern: str):
    """
    작업 핸들러 데코레이터

    Args:
        url_pattern: URL 패턴
    """

    def decorator(func):
        logger.info(f"Task handler registered: {url_pattern}")
        return func

    return decorator


class CloudMonitoringClient(metaclass=SingletonMeta):
    """Cloud Monitoring 클라이언트"""

    def __init__(self):
        self._metrics: List[Dict[str, Any]] = []
        self._logs: List[Dict[str, Any]] = []

    def record_metric(self, name: str, value: float, unit=None, labels=None):
        """메트릭 기록"""
        metric = {
            "name": name,
            "value": value,
            "unit": unit,
            "labels": labels or {},
            "timestamp": datetime.now(),
        }
        self._metrics = self._metrics + [metric]
        logger.debug(f"Metric recorded: {name}={value}")

    def log(self, level: str, message: str, **kwargs):
        """로그 기록"""
        log_entry = {
            "level": level,
            "message": message,
            "timestamp": datetime.now(),
            **kwargs,
        }
        self._logs = self._logs + [log_entry]

    def get_metrics(self) -> List[Dict[str, Any]]:
        """메트릭 조회"""
        return self._metrics.copy()

    def get_logs(self) -> List[Dict[str, Any]]:
        """로그 조회"""
        return self._logs.copy()


def get_monitoring_client() -> CloudMonitoringClient:
    """
    전역 모니터링 클라이언트 반환

    Returns:
        CloudMonitoringClient: 모니터링 클라이언트
    """
    return CloudMonitoringClient()


def record_metric(name: str, value: float, unit=None, labels=None):
    """
    메트릭 기록 헬퍼

    Args:
        name: 메트릭 이름
        value: 메트릭 값
        unit: 단위
        labels: 레이블
    """
    client = get_monitoring_client()
    client.record_metric(name, value, unit, labels)


def log_info(message: str, **kwargs):
    """INFO 로그"""
    client = get_monitoring_client()
    client.log("INFO", message, **kwargs)


def log_warning(message: str, **kwargs):
    """WARNING 로그"""
    client = get_monitoring_client()
    client.log("WARNING", message, **kwargs)


def log_error(message: str, **kwargs):
    """ERROR 로그"""
    client = get_monitoring_client()
    client.log("ERROR", message, **kwargs)


def monitor_performance(func):
    """
    성능 모니터링 데코레이터

    Args:
        func: 모니터링할 함수
    """
    import functools
    import time

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time
            record_metric(f"function.{func.__name__}.duration", elapsed * 1000, "ms")
            return result
        except Exception as e:
            log_error(f"Function {func.__name__} failed: {e}")
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            record_metric(f"function.{func.__name__}.duration", elapsed * 1000, "ms")
            return result
        except Exception as e:
            log_error(f"Function {func.__name__} failed: {e}")
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


class AutoScalingOptimizer(metaclass=SingletonMeta):
    """오토스케일링 최적화"""

    def __init__(self):
        self._config = {
            "min_instances": 0,
            "max_instances": 100,
            "target_cpu": 60,
            "target_memory": 70,
            "scale_down_delay": 300,
        }
        self._metrics = []

    def configure(self, **kwargs):
        """설정 업데이트"""
        self._config = {**self._config, **kwargs}

    def analyze_metrics(self) -> Dict[str, Any]:
        """메트릭 분석"""
        return {
            "should_scale_up": False,
            "should_scale_down": False,
            "current_instances": 1,
            "recommended_instances": 1,
        }

    def get_recommendations(self) -> List[str]:
        """스케일링 권장사항"""
        analysis = self.analyze_metrics()
        recommendations = []
        if analysis["should_scale_up"]:
            recommendations = recommendations + [
                f"Scale up to {analysis.get('recommended_instances')} instances"
            ]
        elif analysis["should_scale_down"]:
            recommendations = recommendations + [
                f"Scale down to {analysis.get('recommended_instances')} instances"
            ]
        return recommendations


def get_autoscaling_optimizer() -> AutoScalingOptimizer:
    """
    전역 오토스케일링 최적화기 반환

    Returns:
        AutoScalingOptimizer: 오토스케일링 최적화기
    """
    return AutoScalingOptimizer()


def optimize_scaling(**config):
    """
    스케일링 최적화

    Args:
        **config: 스케일링 설정
    """
    optimizer = get_autoscaling_optimizer()
    optimizer.configure(**config)
    recommendations = optimizer.get_recommendations()
    for rec in recommendations:
        logger.info(f"Scaling recommendation: {rec}")


def get_scaling_stats() -> Dict[str, Any]:
    """
    스케일링 통계 조회

    Returns:
        스케일링 통계
    """
    optimizer = get_autoscaling_optimizer()
    return optimizer.analyze_metrics()


async def initialize_cloud_run_services():
    """Cloud Run 서비스 초기화"""
    if is_cloud_run_environment():
        logger.info("Initializing Cloud Run services...")
        discovery = get_service_discovery()
        await discovery.initialize()
        monitoring = get_monitoring_client()
        monitoring.log("INFO", "Cloud Run services initialized")
        logger.info("Cloud Run services initialized successfully")
    else:
        logger.info("Not running in Cloud Run environment")


async def shutdown_cloud_run_services():
    """Cloud Run 서비스 종료"""
    logger.info("Shutting down Cloud Run services...")
    pass


def get_cloud_run_status() -> Dict[str, Any]:
    """
    Cloud Run 상태 조회

    Returns:
        Cloud Run 상태 정보
    """
    return {
        "is_cloud_run": is_cloud_run_environment(),
        "service_name": get_cloud_run_service_name(),
        "revision": get_cloud_run_revision(),
        "region": get_cloud_run_region(),
    }


__all__ = [
    "is_cloud_run_environment",
    "get_cloud_run_service_name",
    "get_cloud_run_revision",
    "get_cloud_run_region",
    "CloudRunServiceDiscovery",
    "ServiceEndpoint",
    "get_service_discovery",
    "discover_services",
    "call_service",
    "CloudTaskQueue",
    "get_task_queue",
    "submit_task",
    "schedule_task",
    "task_handler",
    "CloudMonitoringClient",
    "get_monitoring_client",
    "record_metric",
    "log_info",
    "log_warning",
    "log_error",
    "monitor_performance",
    "AutoScalingOptimizer",
    "get_autoscaling_optimizer",
    "optimize_scaling",
    "get_scaling_stats",
    "initialize_cloud_run_services",
    "shutdown_cloud_run_services",
    "get_cloud_run_status",
]
