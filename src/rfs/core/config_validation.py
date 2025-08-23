"""
Configuration Validation and Type Safety (RFS v4)

설정 검증 및 타입 안전성 강화
- 런타임 설정 검증
- 타입 안전성 보장
- 보안 설정 검사
- 성능 최적화 가이드
"""

import os
import re
import json
from typing import Dict, Any, List, Optional, Union, Type, get_type_hints
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from pydantic import ValidationError, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    ValidationError = Exception
    PYDANTIC_AVAILABLE = False

from .config import RFSConfig, Environment
from .config_profiles import ProfileManager, profile_manager

logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """검증 수준"""
    STRICT = "strict"      # 엄격한 검증 - 운영환경
    STANDARD = "standard"  # 표준 검증 - 개발/테스트
    LENIENT = "lenient"    # 관대한 검증 - 로컬 개발


class ValidationSeverity(str, Enum):
    """검증 심각도"""
    CRITICAL = "critical"  # 즉시 수정 필요
    ERROR = "error"        # 수정 권장
    WARNING = "warning"    # 주의사항
    INFO = "info"         # 정보성


@dataclass
class ValidationResult:
    """검증 결과"""
    field: str
    severity: ValidationSeverity
    message: str
    current_value: Any = None
    suggested_value: Any = None
    fix_hint: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'field': self.field,
            'severity': self.severity.value,
            'message': self.message,
            'current_value': self.current_value,
            'suggested_value': self.suggested_value,
            'fix_hint': self.fix_hint
        }


class ConfigValidator:
    """설정 검증기 (RFS v4)"""
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        self.validation_level = validation_level
        self.results: List[ValidationResult] = []
        self.profile_manager = profile_manager
    
    def validate_config(self, config: RFSConfig) -> List[ValidationResult]:
        """전체 설정 검증"""
        self.results.clear()
        
        # 기본 타입 검증
        self._validate_types(config)
        
        # 환경별 검증
        self._validate_environment_specific(config)
        
        # 보안 설정 검증
        self._validate_security(config)
        
        # 성능 설정 검증
        self._validate_performance(config)
        
        # Cloud Run 전용 검증
        self._validate_cloud_run(config)
        
        # 의존성 검증
        self._validate_dependencies(config)
        
        return self.results.copy()
    
    def _validate_types(self, config: RFSConfig) -> None:
        """타입 검증"""
        if not PYDANTIC_AVAILABLE:
            # Pydantic 없는 경우 기본 타입 체크
            self._basic_type_validation(config)
            return
        
        try:
            # Pydantic이 이미 타입 검증을 수행
            if hasattr(config, 'model_validate'):
                config.model_validate(config.model_dump())
        except ValidationError as e:
            for error in e.errors():
                self.results.append(ValidationResult(
                    field='.'.join(str(x) for x in error['loc']),
                    severity=ValidationSeverity.ERROR,
                    message=f"Type validation failed: {error['msg']}",
                    current_value=error.get('input'),
                    fix_hint="Check data type and format"
                ))
    
    def _basic_type_validation(self, config: RFSConfig) -> None:
        """기본 타입 검증 (Pydantic 없는 경우)"""
        # 정수 필드 검증
        int_fields = ['default_buffer_size', 'max_concurrency', 'cloud_run_max_instances', 'metrics_export_interval']
        for field in int_fields:
            value = getattr(config, field, None)
            if value is not None and not isinstance(value, int):
                self.results.append(ValidationResult(
                    field=field,
                    severity=ValidationSeverity.ERROR,
                    message=f"Expected integer, got {type(value).__name__}",
                    current_value=value,
                    fix_hint="Convert to integer"
                ))
        
        # 부울 필드 검증
        bool_fields = ['enable_cold_start_optimization', 'event_store_enabled', 'enable_tracing']
        for field in bool_fields:
            value = getattr(config, field, None)
            if value is not None and not isinstance(value, bool):
                self.results.append(ValidationResult(
                    field=field,
                    severity=ValidationSeverity.ERROR,
                    message=f"Expected boolean, got {type(value).__name__}",
                    current_value=value,
                    fix_hint="Use true/false"
                ))
    
    def _validate_environment_specific(self, config: RFSConfig) -> None:
        """환경별 특수 검증"""
        match config.environment:
            case Environment.PRODUCTION:
                self._validate_production_settings(config)
            case Environment.TEST:
                self._validate_test_settings(config)
            case Environment.DEVELOPMENT:
                self._validate_development_settings(config)
    
    def _validate_production_settings(self, config: RFSConfig) -> None:
        """운영 환경 설정 검증"""
        # 로그 레벨 검증
        if config.log_level == "DEBUG":
            self.results.append(ValidationResult(
                field="log_level",
                severity=ValidationSeverity.WARNING,
                message="DEBUG 로그는 운영환경에서 성능에 영향을 줄 수 있습니다",
                current_value=config.log_level,
                suggested_value="INFO",
                fix_hint="RFS_LOG_LEVEL=INFO 설정"
            ))
        
        # 추적 활성화 확인
        if not config.enable_tracing:
            self.results.append(ValidationResult(
                field="enable_tracing",
                severity=ValidationSeverity.WARNING,
                message="운영환경에서는 분산 추적 활성화를 권장합니다",
                current_value=False,
                suggested_value=True,
                fix_hint="RFS_ENABLE_TRACING=true 설정"
            ))
        
        # 성능 모니터링 확인
        if not getattr(config, 'enable_performance_monitoring', False):
            self.results.append(ValidationResult(
                field="enable_performance_monitoring",
                severity=ValidationSeverity.WARNING,
                message="운영환경에서는 성능 모니터링을 권장합니다",
                current_value=False,
                suggested_value=True,
                fix_hint="RFS_ENABLE_PERFORMANCE_MONITORING=true 설정"
            ))
    
    def _validate_test_settings(self, config: RFSConfig) -> None:
        """테스트 환경 설정 검증"""
        # 테스트용 Redis DB 확인
        if hasattr(config, 'redis_url') and 'localhost' in config.redis_url:
            if not config.redis_url.endswith(('/1', '/2', '/15')):  # 테스트 DB들
                self.results.append(ValidationResult(
                    field="redis_url",
                    severity=ValidationSeverity.WARNING,
                    message="테스트 환경에서는 별도 Redis DB를 사용하세요",
                    current_value=config.redis_url,
                    suggested_value=config.redis_url.rstrip('/0') + '/1',
                    fix_hint="Redis URL 끝에 /1 추가"
                ))
        
        # 이벤트 스토어 비활성화 권장
        if config.event_store_enabled:
            self.results.append(ValidationResult(
                field="event_store_enabled",
                severity=ValidationSeverity.INFO,
                message="테스트 성능 향상을 위해 이벤트 스토어 비활성화를 고려하세요",
                current_value=True,
                suggested_value=False,
                fix_hint="RFS_EVENT_STORE_ENABLED=false 설정"
            ))
    
    def _validate_development_settings(self, config: RFSConfig) -> None:
        """개발 환경 설정 검증"""
        # 개발용 메모리 제한 확인
        if hasattr(config, 'cloud_run_memory_limit'):
            if config.cloud_run_memory_limit in ['1Gi', '2Gi']:
                self.results.append(ValidationResult(
                    field="cloud_run_memory_limit",
                    severity=ValidationSeverity.INFO,
                    message="로컬 개발시에는 작은 메모리 제한을 권장합니다",
                    current_value=config.cloud_run_memory_limit,
                    suggested_value="256Mi",
                    fix_hint="개발용 리소스 절약"
                ))
    
    def _validate_security(self, config: RFSConfig) -> None:
        """보안 설정 검증"""
        # API 키 헤더 검증
        if hasattr(config, 'api_key_header'):
            if config.api_key_header.lower() in ['api-key', 'apikey', 'key']:
                self.results.append(ValidationResult(
                    field="api_key_header",
                    severity=ValidationSeverity.WARNING,
                    message="일반적인 API 키 헤더명은 보안상 권장되지 않습니다",
                    current_value=config.api_key_header,
                    suggested_value="X-Custom-API-Key",
                    fix_hint="커스텀 헤더명 사용"
                ))
        
        # Redis URL 보안 확인
        if hasattr(config, 'redis_url'):
            if config.redis_url.startswith('redis://') and '@' not in config.redis_url:
                if config.environment == Environment.PRODUCTION:
                    self.results.append(ValidationResult(
                        field="redis_url",
                        severity=ValidationSeverity.CRITICAL,
                        message="운영환경에서는 Redis 인증을 필수로 사용해야 합니다",
                        current_value="redis://localhost:6379",
                        suggested_value="redis://user:pass@host:port",
                        fix_hint="Redis 인증 설정 추가"
                    ))
    
    def _validate_performance(self, config: RFSConfig) -> None:
        """성능 설정 검증"""
        # 버퍼 크기 최적화 확인
        if config.default_buffer_size > 5000:
            self.results.append(ValidationResult(
                field="default_buffer_size",
                severity=ValidationSeverity.WARNING,
                message="큰 버퍼 크기는 메모리 사용량을 증가시킬 수 있습니다",
                current_value=config.default_buffer_size,
                suggested_value=1000,
                fix_hint="용도에 맞는 적절한 버퍼 크기 설정"
            ))
        
        # 동시성 설정 확인
        if config.max_concurrency > 100:
            self.results.append(ValidationResult(
                field="max_concurrency",
                severity=ValidationSeverity.WARNING,
                message="높은 동시성 설정은 리소스 부족을 야기할 수 있습니다",
                current_value=config.max_concurrency,
                suggested_value=80,
                fix_hint="Cloud Run 권장값 80 사용"
            ))
        
        # 메트릭 내보내기 간격 확인
        if hasattr(config, 'metrics_export_interval'):
            if config.metrics_export_interval < 30:
                self.results.append(ValidationResult(
                    field="metrics_export_interval",
                    severity=ValidationSeverity.INFO,
                    message="너무 짧은 메트릭 간격은 성능에 영향을 줄 수 있습니다",
                    current_value=config.metrics_export_interval,
                    suggested_value=60,
                    fix_hint="60초 이상 권장"
                ))
    
    def _validate_cloud_run(self, config: RFSConfig) -> None:
        """Cloud Run 전용 검증"""
        if not self._is_cloud_run_environment():
            return
        
        # CPU 제한 검증
        if hasattr(config, 'cloud_run_cpu_limit'):
            cpu_limit = config.cloud_run_cpu_limit
            if cpu_limit.endswith('m'):
                cpu_value = int(cpu_limit[:-1])
                if cpu_value < 500:
                    self.results.append(ValidationResult(
                        field="cloud_run_cpu_limit",
                        severity=ValidationSeverity.WARNING,
                        message="낮은 CPU 제한은 성능 저하를 야기할 수 있습니다",
                        current_value=cpu_limit,
                        suggested_value="1000m",
                        fix_hint="최소 500m 이상 권장"
                    ))
        
        # 메모리 제한 검증
        if hasattr(config, 'cloud_run_memory_limit'):
            memory_limit = config.cloud_run_memory_limit
            if memory_limit == "128Mi":
                self.results.append(ValidationResult(
                    field="cloud_run_memory_limit",
                    severity=ValidationSeverity.ERROR,
                    message="128Mi는 RFS 프레임워크 실행에 부족합니다",
                    current_value=memory_limit,
                    suggested_value="256Mi",
                    fix_hint="최소 256Mi 필요"
                ))
        
        # 인스턴스 수 검증
        if config.cloud_run_max_instances > 1000:
            self.results.append(ValidationResult(
                field="cloud_run_max_instances",
                severity=ValidationSeverity.WARNING,
                message="과도한 최대 인스턴스 수는 비용 증가를 야기할 수 있습니다",
                current_value=config.cloud_run_max_instances,
                suggested_value=100,
                fix_hint="용도에 맞는 적절한 인스턴스 수 설정"
            ))
    
    def _validate_dependencies(self, config: RFSConfig) -> None:
        """의존성 검증"""
        # Cold start 최적화와 성능 모니터링 연관성
        if config.enable_cold_start_optimization and not getattr(config, 'enable_performance_monitoring', False):
            self.results.append(ValidationResult(
                field="enable_performance_monitoring",
                severity=ValidationSeverity.INFO,
                message="Cold start 최적화 활성화시 성능 모니터링도 함께 활성화를 권장합니다",
                current_value=False,
                suggested_value=True,
                fix_hint="성능 최적화 효과 측정을 위한 모니터링 활성화"
            ))
        
        # 이벤트 스토어와 Redis 의존성
        if config.event_store_enabled and hasattr(config, 'redis_url'):
            if not config.redis_url or config.redis_url == "redis://localhost:6379":
                if config.environment == Environment.PRODUCTION:
                    self.results.append(ValidationResult(
                        field="redis_url",
                        severity=ValidationSeverity.CRITICAL,
                        message="이벤트 스토어 사용시 운영용 Redis 설정이 필요합니다",
                        current_value=config.redis_url,
                        fix_hint="운영용 Redis 클라우드 서비스 URL 설정"
                    ))
    
    def _is_cloud_run_environment(self) -> bool:
        """Cloud Run 환경 여부 확인"""
        return os.environ.get('K_SERVICE') is not None
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """검증 요약 정보"""
        severity_counts = {}
        for severity in ValidationSeverity:
            severity_counts[severity.value] = len([r for r in self.results if r.severity == severity])
        
        return {
            'total_issues': len(self.results),
            'severity_breakdown': severity_counts,
            'validation_level': self.validation_level.value,
            'critical_issues': [r.to_dict() for r in self.results if r.severity == ValidationSeverity.CRITICAL],
            'error_issues': [r.to_dict() for r in self.results if r.severity == ValidationSeverity.ERROR]
        }


class SecurityValidator:
    """보안 설정 전용 검증기 (RFS v4)"""
    
    @staticmethod
    def validate_sensitive_data(config: RFSConfig) -> List[ValidationResult]:
        """민감한 데이터 검증"""
        results = []
        
        # Redis URL에서 비밀번호 노출 확인
        if hasattr(config, 'redis_url') and config.redis_url:
            if re.search(r'redis://[^:]+:[^@]+@', config.redis_url):
                results.append(ValidationResult(
                    field="redis_url",
                    severity=ValidationSeverity.CRITICAL,
                    message="Redis URL에 비밀번호가 평문으로 포함되어 있습니다",
                    current_value="[HIDDEN]",
                    fix_hint="환경 변수나 secret manager 사용"
                ))
        
        # 커스텀 설정에서 민감한 키워드 검색
        if hasattr(config, 'custom') and isinstance(config.custom, dict):
            sensitive_keywords = ['password', 'secret', 'key', 'token', 'credential']
            for key, value in config.custom.items():
                if any(keyword in key.lower() for keyword in sensitive_keywords):
                    if isinstance(value, str) and len(value) > 8:
                        results.append(ValidationResult(
                            field=f"custom.{key}",
                            severity=ValidationSeverity.WARNING,
                            message="민감한 정보가 설정에 직접 포함되어 있을 수 있습니다",
                            current_value="[HIDDEN]",
                            fix_hint="환경 변수나 secret manager 사용"
                        ))
        
        return results
    
    @staticmethod
    def check_environment_exposure() -> List[ValidationResult]:
        """환경 변수 노출 위험 검사"""
        results = []
        
        # 환경 변수에서 민감한 정보 확인
        sensitive_patterns = [
            (r'password', 'PASSWORD found in environment'),
            (r'secret', 'SECRET found in environment'),
            (r'private_key', 'PRIVATE_KEY found in environment'),
            (r'api_key', 'API_KEY found in environment')
        ]
        
        for key in os.environ:
            key_lower = key.lower()
            for pattern, message in sensitive_patterns:
                if pattern in key_lower:
                    # RFS_ 접두사가 있는 것만 체크
                    if key.startswith('RFS_'):
                        results.append(ValidationResult(
                            field=key,
                            severity=ValidationSeverity.WARNING,
                            message=f"환경 변수에 민감한 정보가 노출되어 있습니다: {message}",
                            fix_hint="Secret Manager나 별도 보안 저장소 사용"
                        ))
        
        return results


# 편의 함수들
def validate_config(config: RFSConfig, level: ValidationLevel = ValidationLevel.STANDARD) -> List[ValidationResult]:
    """설정 검증"""
    validator = ConfigValidator(level)
    return validator.validate_config(config)

def quick_validate(config: RFSConfig) -> tuple[bool, int, int]:
    """빠른 검증 (성공 여부, 에러 수, 경고 수)"""
    results = validate_config(config)
    
    errors = len([r for r in results if r.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]])
    warnings = len([r for r in results if r.severity == ValidationSeverity.WARNING])
    
    return errors == 0, errors, warnings

def validate_security(config: RFSConfig) -> List[ValidationResult]:
    """보안 전용 검증"""
    security_validator = SecurityValidator()
    results = security_validator.validate_sensitive_data(config)
    results.extend(security_validator.check_environment_exposure())
    return results

def export_validation_report(config: RFSConfig, filepath: str) -> None:
    """검증 리포트 JSON 파일로 내보내기"""
    validator = ConfigValidator()
    results = validator.validate_config(config)
    summary = validator.get_validation_summary()
    
    report = {
        'config_validation_report': {
            'timestamp': os.popen('date -Iseconds').read().strip(),
            'environment': config.environment.value,
            'summary': summary,
            'detailed_results': [r.to_dict() for r in results]
        }
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Validation report exported to {filepath}")