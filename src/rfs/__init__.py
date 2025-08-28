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

Version: 4.3.4 (Production Ready)
"""

__version__ = "4.3.4"
__author__ = "RFS Framework Team"
__phase__ = "Production Ready"

# Task Management System (새로 구현됨)
from .async_tasks import (
    AsyncTaskManager,
    ResultStatus,
    TaskContext,
    TaskDefinition,
    TaskPriority,
    TaskResult,
    TaskResultStore,
    TaskScheduler,
    TaskStatus,
    TaskType,
    batch_task,
    create_result_analyzer,
    create_task_definition,
    get_default_result_store,
    get_task_definition,
    list_task_definitions,
    priority_task,
    realtime_task,
    scheduled_task,
)
from .cloud_run.autoscaling import ScalingConfiguration

# === Cloud Run Specialization ===
from .cloud_run.helpers import (  # Service Discovery; Task Queue; Monitoring; Auto Scaling; Lifecycle
    AutoScalingOptimizer,
    CloudMonitoringClient,
    CloudRunServiceDiscovery,
    CloudTaskQueue,
    ServiceEndpoint,
    call_service,
    discover_services,
    get_autoscaling_optimizer,
    get_cloud_run_status,
    get_monitoring_client,
    get_scaling_stats,
    get_service_discovery,
    get_task_queue,
    initialize_cloud_run_services,
    is_cloud_run_environment,
    optimize_scaling,
    schedule_task,
    shutdown_cloud_run_services,
    submit_task,
    task_handler,
)

# Monitoring System (완성됨)
from .cloud_run.monitoring import MetricDefinition

# Service Management & Annotations
# Configuration System (Pydantic v2)
# === Core Framework ===
# Result Pattern & Functional Programming
from .core import (  # Helper functions; Annotation System (NEW v4.1); Transaction Management (NEW v4.1)
    Adapter,
    AnnotationMetadata,
    AnnotationProcessor,
    AnnotationRegistry,
    AnnotationType,
    Component,
    ConfigManager,
    Controller,
    DependencyGraph,
    DistributedTransaction,
    Either,
    Environment,
    Failure,
    Maybe,
    Port,
    ProcessingContext,
    ProcessingResult,
    RedisTransaction,
    RedisTransactionManager,
    RegistrationResult,
    Repository,
    Result,
    ResultAsync,
    RFSConfig,
    Service,
    ServiceRegistry,
    ServiceScope,
    StatelessRegistry,
    Success,
    Transactional,
    TransactionalContextManager,
    TransactionManager,
    UseCase,
    auto_register,
    auto_register_classes,
    auto_scan_package,
    create_event,
    either_of,
    get,
    get_annotation_metadata,
    get_annotation_registry,
    get_config,
    get_enhanced_logger,
    get_event_bus,
    get_transaction_manager,
    has_annotation,
    log_debug,
    log_error,
    log_info,
    log_warning,
    log_with_context,
    maybe_of,
    monitor_performance,
    publish_event,
    record_metric,
    register_classes,
    result_of,
    setup_logging,
    stateless,
    transactional_context,
    validate_hexagonal_architecture,
    with_transaction,
)
from .core.config_profiles import (
    ProfileManager,
    create_profile_config,
    detect_current_environment,
)
from .core.config_validation import quick_validate, validate_config, validate_security

# Enhanced Logging System (새로 구현됨)
from .core.enhanced_logging import (
    EnhancedLogger,
    LogContext,
    LogEntry,
    LogLevel,
    get_default_logger,
    get_log_context,
    get_logger,
    log_critical,
)
from .core.enhanced_logging import log_debug as enhanced_log_debug
from .core.enhanced_logging import log_error as enhanced_log_error
from .core.enhanced_logging import (
    log_execution,
)
from .core.enhanced_logging import log_info as enhanced_log_info
from .core.enhanced_logging import log_warning as enhanced_log_warning
from .core.enhanced_logging import (
    set_log_context,
    with_log_context,
)

# === Database Helpers ===
from .database.helpers import (
    close_test_connection,
    create_test_connection,
    get_database_config,
    get_tortoise_url,
)

# === Events System ===
from .events import (
    Command,
    CommandBus,
    CommandResult,
    Event,
    EventBus,
    EventFilter,
    EventHandler,
    EventSubscription,
    Query,
    QueryBus,
    QueryResult,
    Saga,
    SagaManager,
    event_handler,
    saga_step,
)

# Event Handler System (새로 구현됨)
from .events.event_handler import (
    EventHandler,
    EventProcessor,
    FunctionEventHandler,
    HandlerChain,
    HandlerMetadata,
    HandlerMode,
    HandlerPriority,
    HandlerRegistry,
    get_default_event_processor,
    get_default_handler_registry,
    process_event,
    register_handler,
)

# === Reactive Streams ===
from .reactive import Flux, Mono

# === State Machine ===
from .state_machine import (
    State,
    StateMachine,
    StateType,
    Transition,
    create_state_machine,
    transition_to,
)

# 기본값으로 설정 (누락된 클래스들 - 향후 구현 예정)


# === Legacy Serverless (v3 호환) ===
# 임시로 기본값 설정
LegacyCloudRunOptimizer = None
CloudRunConfig = None
get_optimizer = None

# === Standard Library Integration (stdlib.py) ===
from . import stdlib
from .optimization import (  # Cold Start Optimizer (NEW)
    CacheWarmupStrategy,
    ColdStartConfig,
    ColdStartOptimizer,
    MemoryOptimizationStrategy,
    OptimizationCategory,
    OptimizationPhase,
    OptimizationResult,
    OptimizationSuite,
    OptimizationType,
    PerformanceOptimizer,
    PreloadingStrategy,
    get_default_cold_start_optimizer,
    measure_cold_start_time,
    optimize_cold_start,
)
from .production import (
    DeploymentConfig,
    DeploymentResult,
    DeploymentStatus,
    DeploymentStrategy,
    ProductionDeployer,
    ProductionReadinessChecker,
    ReadinessLevel,
    ReadinessReport,
    RollbackManager,
)
from .security import (
    HardeningResult,
    SecurityHardening,
    SecurityPolicy,
    SecurityScanner,
    ThreatLevel,
    VulnerabilityReport,
)

# === Production Framework ===
from .validation import (
    SystemValidator,
    ValidationCategory,
    ValidationResult,
    ValidationSuite,
)

# v4 통합 exports
__all__ = [
    # === Core Framework ===
    # Result Pattern
    "Result",
    "Success",
    "Failure",
    "ResultAsync",
    "Either",
    "Maybe",
    "result_of",
    "maybe_of",
    "either_of",
    # Configuration System
    "RFSConfig",
    "ConfigManager",
    "Environment",
    "get_config",
    "get",
    "ProfileManager",
    "detect_current_environment",
    "create_profile_config",
    "validate_config",
    "quick_validate",
    "validate_security",
    # Service Management & Annotations
    "StatelessRegistry",
    "stateless",
    "ServiceRegistry",
    # Annotation System (NEW v4.1)
    "Port",
    "Adapter",
    "Component",
    "UseCase",
    "Controller",
    "Service",
    "Repository",
    "AnnotationMetadata",
    "AnnotationType",
    "ServiceScope",
    "get_annotation_metadata",
    "has_annotation",
    "validate_hexagonal_architecture",
    "AnnotationRegistry",
    "RegistrationResult",
    "DependencyGraph",
    "get_annotation_registry",
    "register_classes",
    "AnnotationProcessor",
    "ProcessingContext",
    "ProcessingResult",
    "auto_scan_package",
    "auto_register_classes",
    "auto_register",
    # Transaction Management (NEW v4.1)
    "DatabaseTransactionManager",
    "RedisTransactionManager",
    "DistributedTransactionManager",
    "TransactionConfig",
    "RedisTransactionConfig",
    "DistributedTransactionConfig",
    "TransactionManager",
    "get_default_transaction_manager",
    "Transactional",
    "RedisTransaction",
    "DistributedTransaction",
    "TransactionalContextManager",
    "transactional_context",
    "with_transaction",
    # === Reactive Streams ===
    "Mono",
    "Flux",
    # === State Machine ===
    "StateMachine",
    "State",
    "Transition",
    "StateType",
    "create_state_machine",
    "transition_to",
    # === Events System ===
    "Event",
    "EventBus",
    "EventHandler",
    "EventFilter",
    "EventSubscription",
    "get_event_bus",
    "create_event",
    "event_handler",
    "CommandBus",
    "QueryBus",
    "Command",
    "Query",
    "CommandResult",
    "QueryResult",
    "Saga",
    "SagaManager",
    "saga_step",
    # === Cloud Run Specialization ===
    # Service Discovery
    "CloudRunServiceDiscovery",
    "ServiceEndpoint",
    "get_service_discovery",
    "discover_services",
    "call_service",
    # Task Queue & Task Management System
    "CloudTaskQueue",
    "get_task_queue",
    "submit_task",
    "schedule_task",
    "task_handler",
    "TaskDefinition",
    "TaskScheduler",
    "TaskResult",
    "TaskResultStore",
    "TaskContext",
    "TaskType",
    "ResultStatus",
    "AsyncTaskManager",
    "TaskPriority",
    "TaskStatus",
    "create_task_definition",
    "get_task_definition",
    "list_task_definitions",
    "batch_task",
    "scheduled_task",
    "realtime_task",
    "priority_task",
    "get_default_result_store",
    "create_result_analyzer",
    # Enhanced Logging System
    "EnhancedLogger",
    "LogLevel",
    "LogContext",
    "LogEntry",
    "get_logger",
    "get_default_logger",
    "set_log_context",
    "get_log_context",
    "enhanced_log_info",
    "enhanced_log_warning",
    "enhanced_log_error",
    "enhanced_log_debug",
    "log_critical",
    "log_execution",
    "with_log_context",
    # Event Handler System
    "EventHandler",
    "HandlerRegistry",
    "EventProcessor",
    "HandlerChain",
    "HandlerPriority",
    "HandlerMode",
    "HandlerMetadata",
    "FunctionEventHandler",
    "get_default_handler_registry",
    "get_default_event_processor",
    "register_handler",
    "process_event",
    # Monitoring (완성됨)
    "CloudMonitoringClient",
    "MetricDefinition",
    "get_monitoring_client",
    "record_metric",
    "log_info",
    "log_warning",
    "log_error",
    "log_debug",
    "get_enhanced_logger",
    "log_with_context",
    "monitor_performance",
    # === Database Helpers ===
    "get_tortoise_url",
    "create_test_connection",
    "get_database_config",
    "close_test_connection",
    # Auto Scaling
    "AutoScalingOptimizer",
    "ScalingConfiguration",
    "get_autoscaling_optimizer",
    "optimize_scaling",
    "get_scaling_stats",
    # Cloud Run Utilities
    "initialize_cloud_run_services",
    "shutdown_cloud_run_services",
    "get_cloud_run_status",
    "is_cloud_run_environment",
    # === Production Framework ===
    # Validation
    "SystemValidator",
    "ValidationSuite",
    "ValidationResult",
    "ValidationCategory",
    # Optimization
    "PerformanceOptimizer",
    "OptimizationSuite",
    "OptimizationResult",
    "OptimizationType",
    "OptimizationCategory",
    # Cold Start Optimizer (NEW)
    "ColdStartOptimizer",
    "ColdStartConfig",
    "OptimizationPhase",
    "PreloadingStrategy",
    "CacheWarmupStrategy",
    "MemoryOptimizationStrategy",
    "get_default_cold_start_optimizer",
    "optimize_cold_start",
    "measure_cold_start_time",
    # Security
    "SecurityScanner",
    "VulnerabilityReport",
    "ThreatLevel",
    "SecurityHardening",
    "SecurityPolicy",
    "HardeningResult",
    # Production Readiness
    "ProductionReadinessChecker",
    "ReadinessReport",
    "ReadinessLevel",
    "ProductionDeployer",
    "DeploymentStrategy",
    "DeploymentStatus",
    "DeploymentConfig",
    "DeploymentResult",
    "RollbackManager",
    # === Legacy Support ===
    "LegacyCloudRunOptimizer",
    "CloudRunConfig",
    "get_optimizer",
    # === Standard Library Integration ===
    "stdlib",
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
    "❄️ Cold Start Optimization",
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
    "Validation & Optimization": "✅ Complete",
}

# 버전 호환성 정보
__compatibility__ = {
    "python": ">=3.10",
    "pydantic": ">=2.0.0",
    "google-cloud-run": ">=0.8.0",
    "google-cloud-tasks": ">=2.14.0",
    "google-cloud-monitoring": ">=2.14.0",
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
        "production_ready": True,
    }
