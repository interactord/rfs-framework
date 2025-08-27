"""
Cloud Run Module (RFS v4)

Google Cloud Run 전문화 모듈
- 서비스 자동 검색 및 통신 최적화
- Cloud Tasks 기반 비동기 작업 큐
- Cloud Monitoring 통합 모니터링
- 지능형 Auto Scaling 최적화

Phase 2: Cloud Run 전문화 완료
"""

from typing import Any, Dict, List

from .autoscaling import (
    AutoScalingOptimizer,
    MetricSnapshot,
    ScalingConfiguration,
    ScalingDirection,
    ScalingPolicy,
    TrafficPattern,
    TrafficPatternAnalyzer,
    get_autoscaling_optimizer,
    get_scaling_stats,
    optimize_scaling,
)
from .helpers import AutoScalingOptimizer as _AutoScalingOptimizer
from .helpers import CloudMonitoringClient as _CloudMonitoringClient
from .helpers import CloudRunServiceDiscovery as _CloudRunServiceDiscovery
from .helpers import CloudTaskQueue as _CloudTaskQueue
from .helpers import ServiceEndpoint as _ServiceEndpoint
from .helpers import call_service as _call_service
from .helpers import discover_services as _discover_services
from .helpers import get_autoscaling_optimizer as _get_autoscaling_optimizer
from .helpers import (
    get_cloud_run_region,
    get_cloud_run_revision,
    get_cloud_run_service_name,
)
from .helpers import get_cloud_run_status as _get_cloud_run_status
from .helpers import get_monitoring_client as _get_monitoring_client
from .helpers import get_scaling_stats as _get_scaling_stats
from .helpers import get_service_discovery as _get_service_discovery
from .helpers import get_task_queue as _get_task_queue
from .helpers import initialize_cloud_run_services as _initialize_cloud_run_services
from .helpers import is_cloud_run_environment as _is_cloud_run_env
from .helpers import log_error as _log_error
from .helpers import log_info as _log_info
from .helpers import log_warning as _log_warning
from .helpers import monitor_performance as _monitor_performance
from .helpers import optimize_scaling as _optimize_scaling
from .helpers import record_metric as _record_metric
from .helpers import schedule_task as _schedule_task
from .helpers import shutdown_cloud_run_services as _shutdown_cloud_run_services
from .helpers import submit_task as _submit_task
from .helpers import task_handler as _task_handler
from .monitoring import (
    AlertSeverity,
    CloudMonitoringClient,
    LogEntry,
    LogLevel,
    MetricDefinition,
    MetricType,
    PerformanceMonitor,
    get_monitoring_client,
    log_error,
    log_info,
    log_warning,
    monitor_performance,
    record_metric,
)
from .service_discovery import (
    CircuitBreaker,
    CircuitBreakerState,
    CloudRunServiceDiscovery,
    LoadBalancingStrategy,
    ServiceEndpoint,
    ServiceStatus,
    call_service,
    discover_services,
    get_service_discovery,
    health_check_all,
)
from .task_queue import (
    CloudTaskQueue,
    TaskDefinition,
    TaskPriority,
    TaskScheduler,
    TaskStatus,
    get_task_queue,
    schedule_task,
    submit_task,
    task_handler,
)

__all__ = [
    "CloudRunServiceDiscovery",
    "ServiceEndpoint",
    "CircuitBreaker",
    "ServiceStatus",
    "LoadBalancingStrategy",
    "CircuitBreakerState",
    "get_service_discovery",
    "discover_services",
    "call_service",
    "health_check_all",
    "CloudTaskQueue",
    "TaskDefinition",
    "TaskScheduler",
    "TaskPriority",
    "TaskStatus",
    "get_task_queue",
    "submit_task",
    "schedule_task",
    "task_handler",
    "CloudMonitoringClient",
    "PerformanceMonitor",
    "MetricDefinition",
    "LogEntry",
    "MetricType",
    "LogLevel",
    "AlertSeverity",
    "get_monitoring_client",
    "record_metric",
    "log_info",
    "log_warning",
    "log_error",
    "monitor_performance",
    "AutoScalingOptimizer",
    "ScalingConfiguration",
    "TrafficPatternAnalyzer",
    "ScalingPolicy",
    "TrafficPattern",
    "ScalingDirection",
    "MetricSnapshot",
    "get_autoscaling_optimizer",
    "optimize_scaling",
    "get_scaling_stats",
]
__version__ = "4.0.0"
__cloud_run_features__ = [
    "Service Discovery with Circuit Breakers",
    "Cloud Tasks Queue System",
    "Integrated Cloud Monitoring",
    "Intelligent Auto Scaling",
    "Load Balancing Strategies",
    "Predictive Traffic Analysis",
    "Cost-Optimized Scaling",
]
import os


def is_cloud_run_environment() -> bool:
    """Cloud Run 환경 여부 확인"""
    return os.environ.get("K_SERVICE") is not None


def get_cloud_run_metadata() -> dict:
    """Cloud Run 메타데이터 조회"""
    return {
        "service_name": os.environ.get("K_SERVICE", "unknown"),
        "revision": os.environ.get("K_REVISION", "unknown"),
        "configuration": os.environ.get("K_CONFIGURATION", "unknown"),
        "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", "unknown"),
        "region": os.environ.get("GOOGLE_CLOUD_REGION", "unknown"),
        "port": os.environ.get("PORT", "8080"),
    }


async def initialize_cloud_run_services(
    project_id: str = None,
    service_name=None,
    enable_service_discovery=True,
    enable_task_queue=True,
    enable_monitoring=True,
    enable_autoscaling=True,
) -> dict:
    """Cloud Run 서비스들 일괄 초기화"""
    initialized_services = {}
    try:
        if project_id is None:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT 환경 변수가 설정되지 않았습니다")
        if service_name is None:
            service_name = os.environ.get("K_SERVICE", "rfs-service")
        if enable_service_discovery:
            service_discovery = await get_service_discovery(project_id)
            initialized_services = {
                **initialized_services,
                "service_discovery": {"service_discovery": service_discovery},
            }
        if enable_task_queue:
            task_queue = await get_task_queue(project_id)
            initialized_services = {
                **initialized_services,
                "task_queue": {"task_queue": task_queue},
            }
        if enable_monitoring:
            monitoring_client = await get_monitoring_client(project_id)
            initialized_services = {
                **initialized_services,
                "monitoring": {"monitoring": monitoring_client},
            }
        if enable_autoscaling:
            autoscaling_optimizer = await get_autoscaling_optimizer(
                project_id, service_name
            )
            initialized_services = {
                **initialized_services,
                "autoscaling": {"autoscaling": autoscaling_optimizer},
            }
        if enable_monitoring:
            await log_info(
                "RFS Cloud Run 서비스 초기화 완료",
                project_id=project_id,
                service_name=service_name,
                initialized_services=list(initialized_services.keys()),
            )
        return {
            "success": True,
            "project_id": project_id,
            "service_name": service_name,
            "initialized_services": initialized_services,
            "cloud_run_metadata": get_cloud_run_metadata(),
        }
    except Exception as e:
        error_msg = f"Cloud Run 서비스 초기화 실패: {str(e)}"
        if enable_monitoring and "monitoring" in initialized_services:
            await log_error(error_msg, error=str(e))
        return {
            "success": False,
            "error": error_msg,
            "initialized_services": initialized_services,
        }


async def shutdown_cloud_run_services():
    """Cloud Run 서비스들 일괄 종료"""
    # global _service_discovery, _task_queue, _monitoring_client, _autoscaling_optimizer - removed for functional programming
    try:
        from .autoscaling import _autoscaling_optimizer
        from .monitoring import _monitoring_client
        from .service_discovery import _service_discovery
        from .task_queue import _task_queue

        shutdown_tasks = []
        if _service_discovery:
            shutdown_tasks = shutdown_tasks + [_service_discovery.shutdown()]
        if _monitoring_client:
            shutdown_tasks = shutdown_tasks + [_monitoring_client.shutdown()]
        if _autoscaling_optimizer:
            shutdown_tasks = shutdown_tasks + [_autoscaling_optimizer.shutdown()]
        if shutdown_tasks:
            import asyncio

            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        _service_discovery = None
        _task_queue = None
        _monitoring_client = None
        _autoscaling_optimizer = None
        print("✅ RFS Cloud Run 서비스 종료 완료")
    except Exception as e:
        print(f"❌ Cloud Run 서비스 종료 중 오류: {e}")


async def get_cloud_run_status() -> dict:
    """Cloud Run 모듈 전체 상태 확인"""
    status = {
        "environment": {
            "is_cloud_run": is_cloud_run_environment(),
            "metadata": get_cloud_run_metadata(),
        },
        "services": {},
    }
    try:
        try:
            from .service_discovery import _service_discovery

            if _service_discovery:
                stats = _service_discovery.get_service_stats()
                services = status.get("services", {})
                status["services"] = {
                    **services,
                    "service_discovery": {"initialized": True, "stats": stats},
                }
            else:
                services = status.get("services", {})
                status["services"] = {
                    **services,
                    "service_discovery": {"initialized": False},
                }
        except Exception as e:
            services = status.get("services", {})
            status["services"] = {**services, "service_discovery": {"error": str(e)}}
        try:
            from .task_queue import _task_queue

            if _task_queue:
                stats = _task_queue.get_overall_stats()
                status["services"] = {
                    **status.get("services"),
                    "task_queue": {"initialized": True, "stats": stats},
                }
            else:
                status["services"] = {
                    **status.get("services"),
                    "task_queue": {"initialized": False},
                }
        except Exception as e:
            status["services"] = {
                **status.get("services"),
                "task_queue": {"error": str(e)},
            }
        try:
            from .autoscaling import _autoscaling_optimizer

            if _autoscaling_optimizer:
                stats = _autoscaling_optimizer.get_scaling_stats()
                status["services"] = {
                    **status.get("services"),
                    "autoscaling": {"initialized": True, "stats": stats},
                }
            else:
                status["services"] = {
                    **status.get("services"),
                    "autoscaling": {"initialized": False},
                }
        except Exception as e:
            status["services"] = {
                **status.get("services"),
                "autoscaling": {"error": str(e)},
            }
        try:
            from .monitoring import _monitoring_client

            if _monitoring_client:
                status["services"] = {
                    **status.get("services"),
                    "monitoring": {
                        "initialized": True,
                        "registered_metrics": len(
                            _monitoring_client.registered_metrics
                        ),
                        "buffer_sizes": {
                            "metrics": len(_monitoring_client.metrics_buffer),
                            "logs": len(_monitoring_client.logs_buffer),
                        },
                    },
                }
            else:
                status["services"] = {
                    **status.get("services"),
                    "monitoring": {"initialized": False},
                }
        except Exception as e:
            status["services"] = {
                **status.get("services"),
                "monitoring": {"error": str(e)},
            }
    except Exception as e:
        status["error"] = {"error": str(e)}
    return status
