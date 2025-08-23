"""
RFS Framework - Enterprise-Grade Reactive Functional Serverless

현대적인 엔터프라이즈급 Python 애플리케이션을 위한 종합적인 프레임워크:
- Python 3.10+ 현대적 기능 (match/case, union types)
- Pydantic v2 기반 타입 안전 설정 시스템
- Result/Either/Maybe 모나드 패턴
- Reactive Streams (Mono/Flux) with Result integration
- Cloud Run 전문화 및 최적화
- 지능형 Auto Scaling & Monitoring
- 환경별 자동 설정 프로파일

Version: 4.0.0 (Production Ready)
"""

__version__ = "4.1.0"
__author__ = "RFS Framework Team"
__phase__ = "Production Ready"

# === Core Framework ===
# Result Pattern & Functional Programming
from .core import (
    Result, Success, Failure, ResultAsync,
    Either, Maybe,
    result_of, maybe_of, either_of
)

# Configuration System (Pydantic v2)
from .core import (
    RFSConfig, ConfigManager, Environment,
    get_config, get,
    # Helper functions
    get_event_bus, create_event, publish_event,
    setup_logging, log_info, log_warning, log_error, log_debug,
    get_enhanced_logger, log_with_context,
    monitor_performance, record_metric
)
from .core.config_profiles import (
    ProfileManager, detect_current_environment, create_profile_config
)
from .core.config_validation import (
    validate_config, quick_validate, validate_security
)

# Service Management & Annotations
from .core import StatelessRegistry, stateless, ServiceRegistry
from .core import (
    # Annotation System (NEW v4.1)
    Port, Adapter, Component, UseCase, Controller, Service, Repository,
    AnnotationMetadata, AnnotationType, ComponentScope,
    get_annotation_metadata, has_annotation, is_port, is_adapter,
    is_use_case, is_controller, validate_hexagonal_architecture,
    AnnotationRegistry, RegistrationResult, DependencyGraph,
    get_annotation_registry, register_classes,
    AnnotationProcessor, ProcessingContext, ProcessingResult,
    auto_scan_package, auto_register_classes, auto_register,
    # Transaction Management (NEW v4.1)
    DatabaseTransactionManager, RedisTransactionManager, DistributedTransactionManager,
    TransactionConfig, RedisTransactionConfig, DistributedTransactionConfig,
    TransactionManager, get_default_transaction_manager,
    Transactional, RedisTransaction, DistributedTransaction,
    TransactionalContextManager, transactional_context, with_transaction
)

# === Reactive Streams ===
from .reactive import Mono, Flux

# === State Machine ===
from .state_machine import (
    StateMachine, State, Transition, StateType,
    create_state_machine, transition_to
)

# === Events System ===
from .events import (
    Event, EventBus, event_handler,
    EventHandler, EventFilter, EventSubscription,
    CommandBus, QueryBus, Command, Query,
    CommandResult, QueryResult
)

# 기본값으로 설정 (누락된 클래스들 - 향후 구현 예정)

# === Cloud Run Specialization ===
from .cloud_run.helpers import (
    # Service Discovery
    CloudRunServiceDiscovery,
    ServiceEndpoint,
    get_service_discovery,
    discover_services,
    call_service,
    # Task Queue
    CloudTaskQueue,
    get_task_queue,
    submit_task,
    schedule_task,
    task_handler,
    # Monitoring
    CloudMonitoringClient,
    get_monitoring_client,
    # Auto Scaling
    AutoScalingOptimizer,
    get_autoscaling_optimizer,
    optimize_scaling,
    get_scaling_stats,
    # Lifecycle
    initialize_cloud_run_services,
    shutdown_cloud_run_services,
    get_cloud_run_status,
    is_cloud_run_environment,
)

# Task Management System (새로 구현됨)
from .async_tasks import (
    TaskDefinition, TaskScheduler, TaskResult, TaskResultStore, TaskContext,
    TaskType, ResultStatus, AsyncTaskManager, TaskPriority, TaskStatus,
    create_task_definition, get_task_definition, list_task_definitions,
    batch_task, scheduled_task, realtime_task, priority_task,
    get_default_result_store, create_result_analyzer
)

# Enhanced Logging System (새로 구현됨)
from .core.enhanced_logging import (
    EnhancedLogger, LogLevel, LogContext, LogEntry,
    get_logger, get_default_logger, set_log_context, get_log_context,
    log_info as enhanced_log_info, log_warning as enhanced_log_warning, 
    log_error as enhanced_log_error, log_debug as enhanced_log_debug,
    log_critical, log_execution, with_log_context
)

# Event Handler System (새로 구현됨)  
from .events.event_handler import (
    EventHandler, HandlerRegistry, EventProcessor, HandlerChain,
    HandlerPriority, HandlerMode, HandlerMetadata, FunctionEventHandler,
    get_default_handler_registry, get_default_event_processor,
    register_handler, process_event
)

# Monitoring System (완성됨)
from .cloud_run.monitoring import MetricDefinition
from .cloud_run.autoscaling import ScalingConfiguration

# === Legacy Serverless (v3 호환) ===
# 임시로 기본값 설정
LegacyCloudRunOptimizer = None
CloudRunConfig = None
get_optimizer = None

# === Production Framework ===
from .validation import (
    SystemValidator, ValidationSuite, ValidationResult, ValidationCategory
)

from .optimization import (
    PerformanceOptimizer, OptimizationSuite, OptimizationResult, 
    OptimizationType, OptimizationCategory,
    # Cold Start Optimizer (NEW)
    ColdStartOptimizer, ColdStartConfig, OptimizationPhase,
    PreloadingStrategy, CacheWarmupStrategy, MemoryOptimizationStrategy,
    get_default_cold_start_optimizer, optimize_cold_start, measure_cold_start_time
)

from .security import (
    SecurityScanner, VulnerabilityReport, ThreatLevel,
    SecurityHardening, SecurityPolicy, HardeningResult
)

from .production import (
    ProductionReadinessChecker, ReadinessReport, ReadinessLevel,
    ProductionDeployer, DeploymentStrategy, DeploymentStatus,
    DeploymentConfig, DeploymentResult, RollbackManager
)

# v4 통합 exports
__all__ = [
    # === Core Framework ===
    # Result Pattern
    "Result", "Success", "Failure", "ResultAsync",
    "Either", "Maybe",
    "result_of", "maybe_of", "either_of",
    
    # Configuration System
    "RFSConfig", "ConfigManager", "Environment",
    "get_config", "get",
    "ProfileManager", "detect_current_environment", "create_profile_config",
    "validate_config", "quick_validate", "validate_security",
    
    # Service Management & Annotations
    "StatelessRegistry", "stateless", "ServiceRegistry",
    
    # Annotation System (NEW v4.1)
    "Port", "Adapter", "Component", "UseCase", "Controller", "Service", "Repository",
    "AnnotationMetadata", "AnnotationType", "ComponentScope",
    "get_annotation_metadata", "has_annotation", "is_port", "is_adapter",
    "is_use_case", "is_controller", "validate_hexagonal_architecture",
    "AnnotationRegistry", "RegistrationResult", "DependencyGraph",
    "get_annotation_registry", "register_classes",
    "AnnotationProcessor", "ProcessingContext", "ProcessingResult",
    "auto_scan_package", "auto_register_classes", "auto_register",
    
    # Transaction Management (NEW v4.1)
    "DatabaseTransactionManager", "RedisTransactionManager", "DistributedTransactionManager",
    "TransactionConfig", "RedisTransactionConfig", "DistributedTransactionConfig",
    "TransactionManager", "get_default_transaction_manager",
    "Transactional", "RedisTransaction", "DistributedTransaction",
    "TransactionalContextManager", "transactional_context", "with_transaction",
    
    # === Reactive Streams ===
    "Mono", "Flux",
    
    # === State Machine ===
    "StateMachine", "State", "Transition", "StateType",
    "create_state_machine", "transition_to",
    
    # === Events System ===
    "Event", "EventBus", "EventHandler", "EventFilter", "EventSubscription",
    "get_event_bus", "create_event", "event_handler",
    "CommandBus", "QueryBus", "Command", "Query", "CommandResult", "QueryResult",
    
    # === Cloud Run Specialization ===
    # Service Discovery
    "CloudRunServiceDiscovery", "ServiceEndpoint",
    "get_service_discovery", "discover_services", "call_service",
    
    # Task Queue & Task Management System
    "CloudTaskQueue", "get_task_queue", "submit_task", "schedule_task", "task_handler",
    "TaskDefinition", "TaskScheduler", "TaskResult", "TaskResultStore", "TaskContext",
    "TaskType", "ResultStatus", "AsyncTaskManager", "TaskPriority", "TaskStatus",
    "create_task_definition", "get_task_definition", "list_task_definitions",
    "batch_task", "scheduled_task", "realtime_task", "priority_task",
    "get_default_result_store", "create_result_analyzer",
    
    # Enhanced Logging System
    "EnhancedLogger", "LogLevel", "LogContext", "LogEntry",
    "get_logger", "get_default_logger", "set_log_context", "get_log_context",
    "enhanced_log_info", "enhanced_log_warning", "enhanced_log_error", "enhanced_log_debug",
    "log_critical", "log_execution", "with_log_context",
    
    # Event Handler System
    "EventHandler", "HandlerRegistry", "EventProcessor", "HandlerChain",
    "HandlerPriority", "HandlerMode", "HandlerMetadata", "FunctionEventHandler",
    "get_default_handler_registry", "get_default_event_processor",
    "register_handler", "process_event",
    
    # Monitoring (완성됨)
    "CloudMonitoringClient", "MetricDefinition",
    "get_monitoring_client", "record_metric", 
    "log_info", "log_warning", "log_error", "log_debug",
    "get_enhanced_logger", "log_with_context", "monitor_performance",
    
    # Auto Scaling  
    "AutoScalingOptimizer", "ScalingConfiguration",
    "get_autoscaling_optimizer", "optimize_scaling", "get_scaling_stats",
    
    # Cloud Run Utilities
    "initialize_cloud_run_services", "shutdown_cloud_run_services",
    "get_cloud_run_status", "is_cloud_run_environment",
    
    # === Production Framework ===
    # Validation
    "SystemValidator", "ValidationSuite", "ValidationResult", "ValidationCategory",
    
    # Optimization  
    "PerformanceOptimizer", "OptimizationSuite", "OptimizationResult",
    "OptimizationType", "OptimizationCategory",
    # Cold Start Optimizer (NEW)
    "ColdStartOptimizer", "ColdStartConfig", "OptimizationPhase",
    "PreloadingStrategy", "CacheWarmupStrategy", "MemoryOptimizationStrategy",
    "get_default_cold_start_optimizer", "optimize_cold_start", "measure_cold_start_time",
    
    # Security
    "SecurityScanner", "VulnerabilityReport", "ThreatLevel",
    "SecurityHardening", "SecurityPolicy", "HardeningResult",
    
    # Production Readiness
    "ProductionReadinessChecker", "ReadinessReport", "ReadinessLevel",
    "ProductionDeployer", "DeploymentStrategy", "DeploymentStatus",
    "DeploymentConfig", "DeploymentResult", "RollbackManager",
    
    # === Legacy Support ===
    "LegacyCloudRunOptimizer", "CloudRunConfig", "get_optimizer"
]

# 프레임워크 기능
__rfs_features__ = [
    "🚀 Python 3.10+ Modern Features (match/case, union types)",
    "🔧 Pydantic v2 Configuration System",  
    "🧮 Result/Either/Maybe Monad Patterns",
    "🌊 Reactive Streams with Result Integration",
    "☁️  Cloud Run Native Integration",
    "📊 Intelligent Auto Scaling & Monitoring", 
    "🎯 Environment-aware Configuration Profiles",
    "⚡ Performance-optimized Cold Start Handling",
    "🔄 Circuit Breakers & Load Balancing",
    "📈 Predictive Traffic Analysis",
    "🛠️  Rich CLI Tools & Developer Experience",
    "🔬 Advanced Testing & Debugging Framework",
    "📚 Automated Documentation Generation",
    "🤖 Workflow Automation & CI/CD Integration",
    "✅ System Validation Framework",
    "⚡ Performance Optimization Engine", 
    "🛡️ Security Scanning & Hardening",
    "🚀 Production Readiness Verification",
    # NEW v4.1 Features
    "🏗️ Annotation-based Dependency Injection",
    "🔷 Hexagonal Architecture Support",
    "🔄 Comprehensive Transaction Management",
    "📝 Enhanced Structured Logging",
    "🎯 Event Handler Registry & Processing",
    "📋 Async Task Management & Scheduling",
    "❄️ Cold Start Optimization"
]

# 개발 상태
__development_status__ = {
    "Core Framework": "✅ Complete",
    "Annotation System": "✅ Complete (v4.1)",
    "Transaction Management": "✅ Complete (v4.1)",
    "Enhanced Logging": "✅ Complete (v4.1)",
    "Task Management": "✅ Complete (v4.1)",
    "Event Handler System": "✅ Complete (v4.1)",
    "Cold Start Optimization": "✅ Complete (v4.1)",
    "Cloud Run Specialization": "✅ Complete",
    "Monitoring & Logging System": "✅ Complete (v4.1)",
    "Developer Experience": "✅ Complete",
    "Validation & Optimization": "✅ Complete"
}

# 버전 호환성 정보
__compatibility__ = {
    "python": ">=3.10",
    "pydantic": ">=2.0.0",
    "google-cloud-run": ">=0.8.0",
    "google-cloud-tasks": ">=2.14.0",
    "google-cloud-monitoring": ">=2.14.0"
}

def get_framework_info() -> dict:
    """RFS Framework 정보 조회"""
    return {
        "version": __version__,
        "phase": __phase__,
        "features": __rfs_features__,
        "development_status": __development_status__,
        "compatibility": __compatibility__,
        "total_modules": len(__all__),
        "cloud_run_ready": True,
        "production_ready": True
    }