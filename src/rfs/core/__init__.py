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
    get_config, get, 
    is_cloud_run_environment, export_cloud_run_yaml,
    validate_environment, check_pydantic_compatibility
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
    
    # 설정 관리
    "RFSConfig", "ConfigManager", "Environment",
    "get_config", "get",
    "is_cloud_run_environment", "export_cloud_run_yaml",
    "validate_environment", "check_pydantic_compatibility",
    
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
__version__ = "4.0.0"
__rfs_core_features__ = [
    "Result Pattern with Either/Maybe monads",
    "Pydantic v2 Configuration System", 
    "Environment-specific Profiles",
    "Configuration Validation & Type Safety",
    "Cloud Run Optimization",
    "Modern Python 3.10+ features (match/case, union types)"
]