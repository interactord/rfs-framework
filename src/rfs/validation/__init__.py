"""
System Validation Framework (RFS)

RFS 시스템 종합 검증 프레임워크
- 기능 검증 (Functional Validation)
- 통합 검증 (Integration Validation)
- 성능 검증 (Performance Validation)
- 보안 검증 (Security Validation)
- 호환성 검증 (Compatibility Validation)
"""

from .validator import (
    SystemValidator,
    ValidationCategory,
    ValidationLevel,
    ValidationResult,
    ValidationSuite,
)

# 임시로 기본값 설정 (구현 중)
FunctionalValidator = None
ComponentValidator = None
APIValidator = None

IntegrationValidator = None
ServiceIntegrationValidator = None
CloudRunValidator = None

PerformanceValidator = None
LoadValidator = None
ScalabilityValidator = None

SecurityValidator = None
VulnerabilityScanner = None
ComplianceValidator = None

CompatibilityValidator = None
VersionValidator = None
EnvironmentValidator = None

__all__ = [
    # 핵심 검증 시스템
    "SystemValidator",
    "ValidationSuite",
    "ValidationResult",
    "ValidationCategory",
    "ValidationLevel",
    # 기능 검증
    "FunctionalValidator",
    "ComponentValidator",
    "APIValidator",
    # 통합 검증
    "IntegrationValidator",
    "ServiceIntegrationValidator",
    "CloudRunValidator",
    # 성능 검증
    "PerformanceValidator",
    "LoadValidator",
    "ScalabilityValidator",
    # 보안 검증
    "SecurityValidator",
    "VulnerabilityScanner",
    "ComplianceValidator",
    # 호환성 검증
    "CompatibilityValidator",
    "VersionValidator",
    "EnvironmentValidator",
]
