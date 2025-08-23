"""
Core module (RFS v4)

핵심 유틸리티와 패턴들
- Result 패턴 (Either, Maybe 모나드 포함)
- 싱글톤 및 서비스 레지스트리
- Pydantic v2 기반 설정 관리 시스템
- 환경별 설정 프로파일
- 설정 검증 및 타입 안전성
"""

# Result 패턴 및 함수형 프로그래밍
from .result import (
    Result, Success, Failure, ResultAsync,
    Either, Maybe,
    result_of, maybe_of, either_of
)

# 싱글톤 및 레지스트리
from .singleton import StatelessRegistry, stateless
from .registry import ServiceRegistry

# 설정 관리 시스템 (v4 통합)
from .config import (
    RFSConfig, ConfigManager, Environment,
    is_cloud_run_environment, export_cloud_run_yaml,
    validate_environment, check_pydantic_compatibility
)

# 어노테이션 시스템 (RFS v4.1 신규)
from .annotations import (
    Port, Adapter, Component, UseCase, Controller, Service, Repository,
    AnnotationMetadata, AnnotationType, ComponentScope,
    get_annotation_metadata, has_annotation, is_port, is_adapter,
    is_use_case, is_controller, validate_hexagonal_architecture
)

from .annotation_registry import (
    AnnotationRegistry, RegistrationResult, DependencyGraph,
    get_annotation_registry, register_classes
)

from .annotation_processor import (
    AnnotationProcessor, ProcessingContext, ProcessingResult,
    auto_scan_package, auto_register_classes, auto_register
)

# 헬퍼 함수들
from .helpers import (
    get_config, get,
    get_event_bus, create_event, publish_event,
    setup_logging, log_info, log_warning, log_error, log_debug,
    get_enhanced_logger, log_with_context,
    monitor_performance, record_metric
)

# Enhanced Logging System (NEW v4.1)
from .enhanced_logging import (
    EnhancedLogger, LogLevel, LogContext, LogEntry,
    get_logger, get_default_logger, set_log_context, get_log_context,
    log_info as enhanced_log_info, log_warning as enhanced_log_warning,
    log_error as enhanced_log_error, log_debug as enhanced_log_debug,
    log_critical, log_execution, with_log_context
)

# Transaction Management System (NEW v4.1)
from .transactions import (
    DatabaseTransactionManager, RedisTransactionManager, DistributedTransactionManager,
    TransactionConfig, RedisTransactionConfig, DistributedTransactionConfig,
    TransactionManager, get_default_transaction_manager
)
from .transaction_decorators import (
    Transactional, RedisTransaction, DistributedTransaction,
    TransactionalContextManager, transactional_context, with_transaction
)

# 환경별 설정 프로파일
from .config_profiles import (
    ProfileManager, ConfigProfile,
    DevelopmentProfile, TestProfile, ProductionProfile,
    profile_manager,
    detect_current_environment, create_profile_config,
    validate_current_environment, get_environment_summary
)

# 설정 검증 시스템
from .config_validation import (
    ConfigValidator, SecurityValidator,
    ValidationLevel, ValidationSeverity, ValidationResult,
    validate_config, quick_validate, validate_security,
    export_validation_report
)

# v4 핵심 exports
__all__ = [
    # Result 패턴
    "Result", "Success", "Failure", "ResultAsync",
    "Either", "Maybe",
    "result_of", "maybe_of", "either_of",
    
    # 서비스 관리
    "StatelessRegistry", "stateless", "ServiceRegistry",
    
    # 어노테이션 시스템 (v4.1 신규)
    "Port", "Adapter", "Component", "UseCase", "Controller", "Service", "Repository",
    "AnnotationMetadata", "AnnotationType", "ComponentScope",
    "get_annotation_metadata", "has_annotation", "is_port", "is_adapter",
    "is_use_case", "is_controller", "validate_hexagonal_architecture",
    "AnnotationRegistry", "RegistrationResult", "DependencyGraph",
    "get_annotation_registry", "register_classes",
    "AnnotationProcessor", "ProcessingContext", "ProcessingResult",
    "auto_scan_package", "auto_register_classes", "auto_register",
    
    # 설정 관리
    "RFSConfig", "ConfigManager", "Environment",
    "get_config", "get",
    "is_cloud_run_environment", "export_cloud_run_yaml",
    "validate_environment", "check_pydantic_compatibility",
    
    # 헬퍼 함수
    "get_event_bus", "create_event", "publish_event",
    "setup_logging", "log_info", "log_warning", "log_error", "log_debug",
    "get_enhanced_logger", "log_with_context",
    "monitor_performance", "record_metric",
    
    # Enhanced Logging System (NEW v4.1)
    "EnhancedLogger", "LogLevel", "LogContext", "LogEntry",
    "get_logger", "get_default_logger", "set_log_context", "get_log_context",
    "enhanced_log_info", "enhanced_log_warning", "enhanced_log_error", "enhanced_log_debug",
    "log_critical", "log_execution", "with_log_context",
    
    # Transaction Management System (NEW v4.1)
    "DatabaseTransactionManager", "RedisTransactionManager", "DistributedTransactionManager",
    "TransactionConfig", "RedisTransactionConfig", "DistributedTransactionConfig",
    "TransactionManager", "get_default_transaction_manager",
    "Transactional", "RedisTransaction", "DistributedTransaction",
    "TransactionalContextManager", "transactional_context", "with_transaction",
    
    # 설정 프로파일
    "ProfileManager", "ConfigProfile",
    "DevelopmentProfile", "TestProfile", "ProductionProfile",
    "profile_manager",
    "detect_current_environment", "create_profile_config", 
    "validate_current_environment", "get_environment_summary",
    
    # 설정 검증
    "ConfigValidator", "SecurityValidator",
    "ValidationLevel", "ValidationSeverity", "ValidationResult",
    "validate_config", "quick_validate", "validate_security",
    "export_validation_report"
]

# v4 버전 정보
__version__ = "4.1.0"
__rfs_core_features__ = [
    "Result Pattern with Either/Maybe monads",
    "Annotation-based Dependency Injection (NEW v4.1)",
    "Hexagonal Architecture Support (NEW v4.1)",
    "Pydantic v2 Configuration System", 
    "Environment-specific Profiles",
    "Configuration Validation & Type Safety",
    "Cloud Run Optimization",
    "Modern Python 3.10+ features (match/case, union types)"
]