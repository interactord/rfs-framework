"""
Cloud Run Module (RFS v4)

Google Cloud Run 전문화 모듈
- 서비스 자동 검색 및 통신 최적화
- Cloud Tasks 기반 비동기 작업 큐
- Cloud Monitoring 통합 모니터링
- 지능형 Auto Scaling 최적화

Phase 2: Cloud Run 전문화 완료
"""

# Service Discovery & Communication
from .service_discovery import (
    CloudRunServiceDiscovery, ServiceEndpoint, CircuitBreaker,
    ServiceStatus, LoadBalancingStrategy, CircuitBreakerState,
    get_service_discovery, discover_services, call_service, health_check_all
)

# Task Queue System
from .task_queue import (
    CloudTaskQueue, TaskDefinition, TaskScheduler,
    TaskPriority, TaskStatus,
    get_task_queue, submit_task, schedule_task, task_handler
)

# Monitoring & Logging
from .monitoring import (
    CloudMonitoringClient, PerformanceMonitor,
    MetricDefinition, LogEntry, MetricType, LogLevel, AlertSeverity,
    get_monitoring_client, record_metric, 
    log_info, log_warning, log_error, monitor_performance
)

# Auto Scaling Optimization
from .autoscaling import (
    AutoScalingOptimizer, ScalingConfiguration, TrafficPatternAnalyzer,
    ScalingPolicy, TrafficPattern, ScalingDirection, MetricSnapshot,
    get_autoscaling_optimizer, optimize_scaling, get_scaling_stats
)

# Cloud Run 전용 exports
__all__ = [
    # Service Discovery
    "CloudRunServiceDiscovery", "ServiceEndpoint", "CircuitBreaker",
    "ServiceStatus", "LoadBalancingStrategy", "CircuitBreakerState",
    "get_service_discovery", "discover_services", "call_service", "health_check_all",
    
    # Task Queue
    "CloudTaskQueue", "TaskDefinition", "TaskScheduler",
    "TaskPriority", "TaskStatus", 
    "get_task_queue", "submit_task", "schedule_task", "task_handler",
    
    # Monitoring
    "CloudMonitoringClient", "PerformanceMonitor",
    "MetricDefinition", "LogEntry", "MetricType", "LogLevel", "AlertSeverity",
    "get_monitoring_client", "record_metric",
    "log_info", "log_warning", "log_error", "monitor_performance",
    
    # Auto Scaling
    "AutoScalingOptimizer", "ScalingConfiguration", "TrafficPatternAnalyzer", 
    "ScalingPolicy", "TrafficPattern", "ScalingDirection", "MetricSnapshot",
    "get_autoscaling_optimizer", "optimize_scaling", "get_scaling_stats"
]

# Cloud Run 모듈 정보
__version__ = "4.0.0"
__cloud_run_features__ = [
    "Service Discovery with Circuit Breakers",
    "Cloud Tasks Queue System",
    "Integrated Cloud Monitoring",
    "Intelligent Auto Scaling",
    "Load Balancing Strategies",
    "Predictive Traffic Analysis",
    "Cost-Optimized Scaling"
]

# Cloud Run 환경 감지
import os

def is_cloud_run_environment() -> bool:
    """Cloud Run 환경 여부 확인"""
    return os.environ.get('K_SERVICE') is not None

def get_cloud_run_metadata() -> dict:
    """Cloud Run 메타데이터 조회"""
    return {
        'service_name': os.environ.get('K_SERVICE', 'unknown'),
        'revision': os.environ.get('K_REVISION', 'unknown'),
        'configuration': os.environ.get('K_CONFIGURATION', 'unknown'),
        'project_id': os.environ.get('GOOGLE_CLOUD_PROJECT', 'unknown'),
        'region': os.environ.get('GOOGLE_CLOUD_REGION', 'unknown'),
        'port': os.environ.get('PORT', '8080')
    }

# 초기화 헬퍼 함수
async def initialize_cloud_run_services(
    project_id: str = None,
    service_name: str = None,
    enable_service_discovery: bool = True,
    enable_task_queue: bool = True, 
    enable_monitoring: bool = True,
    enable_autoscaling: bool = True
) -> dict:
    """Cloud Run 서비스들 일괄 초기화"""
    
    initialized_services = {}
    
    try:
        # 프로젝트 정보 자동 감지
        if project_id is None:
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT 환경 변수가 설정되지 않았습니다")
        
        if service_name is None:
            service_name = os.environ.get('K_SERVICE', 'rfs-service')
        
        # Service Discovery 초기화
        if enable_service_discovery:
            service_discovery = await get_service_discovery(project_id)
            initialized_services['service_discovery'] = service_discovery
        
        # Task Queue 초기화  
        if enable_task_queue:
            task_queue = await get_task_queue(project_id)
            initialized_services['task_queue'] = task_queue
        
        # Monitoring 초기화
        if enable_monitoring:
            monitoring_client = await get_monitoring_client(project_id)
            initialized_services['monitoring'] = monitoring_client
        
        # Auto Scaling 초기화
        if enable_autoscaling:
            autoscaling_optimizer = await get_autoscaling_optimizer(project_id, service_name)
            initialized_services['autoscaling'] = autoscaling_optimizer
        
        # 성공 로그
        if enable_monitoring:
            await log_info(
                "RFS Cloud Run 서비스 초기화 완료",
                project_id=project_id,
                service_name=service_name,
                initialized_services=list(initialized_services.keys())
            )
        
        return {
            'success': True,
            'project_id': project_id,
            'service_name': service_name,
            'initialized_services': initialized_services,
            'cloud_run_metadata': get_cloud_run_metadata()
        }
        
    except Exception as e:
        error_msg = f"Cloud Run 서비스 초기화 실패: {str(e)}"
        
        # 에러 로그 (가능한 경우)
        if enable_monitoring and 'monitoring' in initialized_services:
            await log_error(error_msg, error=str(e))
        
        return {
            'success': False,
            'error': error_msg,
            'initialized_services': initialized_services
        }

# 종료 헬퍼 함수
async def shutdown_cloud_run_services():
    """Cloud Run 서비스들 일괄 종료"""
    global _service_discovery, _task_queue, _monitoring_client, _autoscaling_optimizer
    
    try:
        # 각 서비스 종료
        from .service_discovery import _service_discovery
        from .task_queue import _task_queue  
        from .monitoring import _monitoring_client
        from .autoscaling import _autoscaling_optimizer
        
        shutdown_tasks = []
        
        if _service_discovery:
            shutdown_tasks.append(_service_discovery.shutdown())
        
        if _monitoring_client:
            shutdown_tasks.append(_monitoring_client.shutdown())
        
        if _autoscaling_optimizer:
            shutdown_tasks.append(_autoscaling_optimizer.shutdown())
        
        # 병렬 종료
        if shutdown_tasks:
            import asyncio
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        # 전역 인스턴스 초기화
        _service_discovery = None
        _task_queue = None
        _monitoring_client = None
        _autoscaling_optimizer = None
        
        print("✅ RFS Cloud Run 서비스 종료 완료")
        
    except Exception as e:
        print(f"❌ Cloud Run 서비스 종료 중 오류: {e}")

# 종합 상태 확인
async def get_cloud_run_status() -> dict:
    """Cloud Run 모듈 전체 상태 확인"""
    
    status = {
        'environment': {
            'is_cloud_run': is_cloud_run_environment(),
            'metadata': get_cloud_run_metadata()
        },
        'services': {}
    }
    
    try:
        # Service Discovery 상태
        try:
            from .service_discovery import _service_discovery
            if _service_discovery:
                stats = _service_discovery.get_service_stats()
                status['services']['service_discovery'] = {
                    'initialized': True,
                    'stats': stats
                }
            else:
                status['services']['service_discovery'] = {'initialized': False}
        except Exception as e:
            status['services']['service_discovery'] = {'error': str(e)}
        
        # Task Queue 상태
        try:
            from .task_queue import _task_queue
            if _task_queue:
                stats = _task_queue.get_overall_stats()
                status['services']['task_queue'] = {
                    'initialized': True,
                    'stats': stats
                }
            else:
                status['services']['task_queue'] = {'initialized': False}
        except Exception as e:
            status['services']['task_queue'] = {'error': str(e)}
        
        # Auto Scaling 상태
        try:
            from .autoscaling import _autoscaling_optimizer
            if _autoscaling_optimizer:
                stats = _autoscaling_optimizer.get_scaling_stats()
                status['services']['autoscaling'] = {
                    'initialized': True,
                    'stats': stats
                }
            else:
                status['services']['autoscaling'] = {'initialized': False}
        except Exception as e:
            status['services']['autoscaling'] = {'error': str(e)}
        
        # Monitoring 상태
        try:
            from .monitoring import _monitoring_client
            if _monitoring_client:
                status['services']['monitoring'] = {
                    'initialized': True,
                    'registered_metrics': len(_monitoring_client.registered_metrics),
                    'buffer_sizes': {
                        'metrics': len(_monitoring_client.metrics_buffer),
                        'logs': len(_monitoring_client.logs_buffer)
                    }
                }
            else:
                status['services']['monitoring'] = {'initialized': False}
        except Exception as e:
            status['services']['monitoring'] = {'error': str(e)}
            
    except Exception as e:
        status['error'] = str(e)
    
    return status