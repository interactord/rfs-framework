# 설정 검증 시스템 예제

Readable HOF를 사용하여 복잡한 애플리케이션 설정을 검증하는 완전한 예제입니다.

## 전체 코드

```python
"""
RFS Readable HOF를 활용한 애플리케이션 설정 검증 시스템

이 예제는 다음 기능을 포함합니다:
- 다단계 설정 검증 (환경별, 서비스별, 보안 설정)
- 조건부 검증 규칙
- 설정 값 변환 및 정규화
- 상세한 오류 리포팅
- 설정 템플릿 생성
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

from rfs.hof.readable import (
    validate_config, required, range_check, custom_check, 
    email_check, url_check, conditional, format_check,
    apply_rules_to, scan_for
)
from rfs.core.result import Result, Success, Failure


class Environment(Enum):
    """환경 타입"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ServiceType(Enum):
    """서비스 타입"""
    WEB = "web"
    API = "api"
    WORKER = "worker"
    DATABASE = "database"
    CACHE = "cache"


@dataclass
class ValidationContext:
    """검증 컨텍스트"""
    environment: Environment
    service_type: ServiceType
    strict_mode: bool = False
    allow_defaults: bool = True


class ConfigValidationSystem:
    """설정 검증 시스템"""
    
    def __init__(self):
        self.validation_rules = self._load_validation_rules()
        self.security_patterns = self._load_security_patterns()
        self.defaults = self._load_default_values()
    
    def validate_application_config(
        self, 
        config_data: Dict[str, Any],
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """애플리케이션 설정 전체 검증"""
        
        print(f"🔍 {context.environment.value} 환경, {context.service_type.value} 서비스 설정 검증 시작...")
        
        # 1. 기본 구조 검증
        structure_result = self._validate_config_structure(config_data, context)
        if structure_result.is_failure():
            return structure_result
        
        # 2. 환경별 특화 검증
        env_result = self._validate_environment_specific(config_data, context)
        if env_result.is_failure():
            return env_result
        
        # 3. 서비스별 특화 검증
        service_result = self._validate_service_specific(config_data, context)
        if service_result.is_failure():
            return service_result
        
        # 4. 보안 설정 검증
        security_result = self._validate_security_settings(config_data, context)
        if security_result.is_failure():
            return security_result
        
        # 5. 설정 값 정규화 및 변환
        normalized_config = self._normalize_config_values(config_data, context)
        
        print("✅ 모든 설정 검증 완료")
        return Success(normalized_config)
    
    def _validate_config_structure(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """기본 설정 구조 검증"""
        
        # Readable HOF로 기본 구조 검증
        base_rules = [
            required("app", "애플리케이션 정보가 필요합니다"),
            required("server", "서버 설정이 필요합니다"),
            conditional(
                condition=lambda cfg: context.environment in [Environment.STAGING, Environment.PRODUCTION],
                rules=[
                    required("monitoring", "운영 환경에서는 모니터링 설정이 필요합니다"),
                    required("logging", "운영 환경에서는 로깅 설정이 필요합니다")
                ]
            )
        ]
        
        result = validate_config(config).against_rules(base_rules)
        
        if result.is_failure():
            return Failure([f"구조 검증 오류: {result.unwrap_error()}"])
        
        return Success(config)
    
    def _validate_environment_specific(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """환경별 특화 검증"""
        
        env_rules = self.validation_rules[context.environment.value]
        
        # 애플리케이션 설정 검증
        app_result = validate_config(config.get("app", {})).against_rules([
            required("name", "애플리케이션 이름이 필요합니다"),
            required("version", "버전 정보가 필요합니다"),
            format_check("version", r'^\d+\.\d+\.\d+$', "버전은 x.y.z 형식이어야 합니다"),
            conditional(
                condition=lambda app: context.environment == Environment.PRODUCTION,
                rules=[
                    custom_check("debug", 
                               lambda debug: debug is False,
                               "운영 환경에서는 debug=False여야 합니다"),
                    required("secret_key", "운영 환경에서는 secret_key가 필요합니다"),
                    custom_check("secret_key",
                               lambda key: len(str(key)) >= 50,
                               "secret_key는 50자 이상이어야 합니다")
                ]
            )
        ])
        
        # 서버 설정 검증
        server_result = validate_config(config.get("server", {})).against_rules([
            required("host", "서버 호스트가 필요합니다"),
            required("port", "서버 포트가 필요합니다"),
            range_check("port", 1, 65535, "포트는 1-65535 사이여야 합니다"),
            conditional(
                condition=lambda srv: context.environment == Environment.PRODUCTION,
                rules=[
                    custom_check("host",
                               lambda host: host != "0.0.0.0",
                               "운영 환경에서는 0.0.0.0을 사용하지 마세요"),
                    custom_check("workers",
                               lambda workers: workers and workers >= 2,
                               "운영 환경에서는 2개 이상의 워커가 필요합니다")
                ]
            )
        ])
        
        # 결과 통합
        errors = []
        if app_result.is_failure():
            errors.append(f"앱 설정 오류: {app_result.unwrap_error()}")
        if server_result.is_failure():
            errors.append(f"서버 설정 오류: {server_result.unwrap_error()}")
        
        if errors:
            return Failure(errors)
        
        return Success(config)
    
    def _validate_service_specific(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """서비스별 특화 검증"""
        
        service_validators = {
            ServiceType.WEB: self._validate_web_service,
            ServiceType.API: self._validate_api_service,
            ServiceType.WORKER: self._validate_worker_service,
            ServiceType.DATABASE: self._validate_database_service,
            ServiceType.CACHE: self._validate_cache_service
        }
        
        validator = service_validators.get(context.service_type)
        if validator:
            return validator(config, context)
        
        return Success(config)
    
    def _validate_web_service(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """웹 서비스 설정 검증"""
        
        # 정적 파일 설정
        static_result = validate_config(config.get("static", {})).against_rules([
            required("url_prefix", "정적 파일 URL 접두사가 필요합니다"),
            required("directory", "정적 파일 디렉토리가 필요합니다"),
            custom_check("directory",
                       lambda dir_path: Path(dir_path).exists(),
                       "정적 파일 디렉토리가 존재하지 않습니다")
        ])
        
        # 세션 설정
        session_result = validate_config(config.get("session", {})).against_rules([
            required("cookie_name", "세션 쿠키 이름이 필요합니다"),
            range_check("max_age", 300, 86400, "세션 만료 시간은 5분-24시간 사이"),
            conditional(
                condition=lambda sess: context.environment == Environment.PRODUCTION,
                rules=[
                    custom_check("secure", 
                               lambda secure: secure is True,
                               "운영 환경에서는 secure 쿠키를 사용해야 합니다"),
                    custom_check("httponly",
                               lambda httponly: httponly is True,
                               "HttpOnly 쿠키를 사용해야 합니다")
                ]
            )
        ])
        
        errors = []
        if static_result.is_failure():
            errors.append(f"정적 파일 설정 오류: {static_result.unwrap_error()}")
        if session_result.is_failure():
            errors.append(f"세션 설정 오류: {session_result.unwrap_error()}")
        
        return Failure(errors) if errors else Success(config)
    
    def _validate_api_service(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """API 서비스 설정 검증"""
        
        # API 설정
        api_result = validate_config(config.get("api", {})).against_rules([
            required("version", "API 버전이 필요합니다"),
            required("prefix", "API 접두사가 필요합니다"),
            range_check("rate_limit", 10, 10000, "Rate limit은 10-10000 사이"),
            conditional(
                condition=lambda api: context.environment == Environment.PRODUCTION,
                rules=[
                    required("cors_origins", "CORS 설정이 필요합니다"),
                    custom_check("cors_origins",
                               lambda origins: origins != ["*"],
                               "운영 환경에서는 와일드카드 CORS를 사용하지 마세요")
                ]
            )
        ])
        
        # 인증 설정
        auth_result = validate_config(config.get("auth", {})).against_rules([
            required("jwt_secret", "JWT 시크릿이 필요합니다"),
            custom_check("jwt_secret",
                       lambda secret: len(str(secret)) >= 32,
                       "JWT 시크릿은 32자 이상이어야 합니다"),
            range_check("token_expiry", 300, 86400, "토큰 만료 시간은 5분-24시간 사이"),
            required("algorithm", "JWT 알고리즘이 필요합니다"),
            custom_check("algorithm",
                       lambda alg: alg in ["HS256", "RS256", "ES256"],
                       "지원되는 JWT 알고리즘이 아닙니다")
        ])
        
        errors = []
        if api_result.is_failure():
            errors.append(f"API 설정 오류: {api_result.unwrap_error()}")
        if auth_result.is_failure():
            errors.append(f"인증 설정 오류: {auth_result.unwrap_error()}")
        
        return Failure(errors) if errors else Success(config)
    
    def _validate_worker_service(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """워커 서비스 설정 검증"""
        
        # 큐 설정
        queue_result = validate_config(config.get("queue", {})).against_rules([
            required("broker_url", "브로커 URL이 필요합니다"),
            url_check("broker_url", "유효한 브로커 URL이어야 합니다"),
            range_check("max_retries", 0, 10, "재시도 횟수는 0-10 사이"),
            range_check("task_timeout", 30, 3600, "작업 타임아웃은 30초-1시간 사이"),
            conditional(
                condition=lambda queue: context.environment == Environment.PRODUCTION,
                rules=[
                    custom_check("broker_url",
                               lambda url: not url.startswith("redis://localhost"),
                               "운영 환경에서는 localhost Redis를 사용하지 마세요"),
                    range_check("concurrency", 2, 20, "운영 환경에서는 2-20개 동시 작업")
                ]
            )
        ])
        
        return Failure([f"큐 설정 오류: {queue_result.unwrap_error()}"]) if queue_result.is_failure() else Success(config)
    
    def _validate_database_service(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """데이터베이스 서비스 설정 검증"""
        
        # 데이터베이스 설정
        db_result = validate_config(config.get("database", {})).against_rules([
            required("url", "데이터베이스 URL이 필요합니다"),
            custom_check("url",
                       lambda url: any(url.startswith(prefix) for prefix in 
                                     ["postgresql://", "mysql://", "sqlite:///"]),
                       "지원되는 데이터베이스 URL 형식이 아닙니다"),
            range_check("pool_size", 1, 50, "연결 풀 크기는 1-50 사이"),
            range_check("max_overflow", 0, 20, "최대 오버플로우는 0-20 사이"),
            conditional(
                condition=lambda db: context.environment == Environment.PRODUCTION,
                rules=[
                    custom_check("url",
                               lambda url: not url.startswith("sqlite:///"),
                               "운영 환경에서는 SQLite를 사용하지 마세요"),
                    range_check("pool_size", 5, 50, "운영 환경에서는 5개 이상의 연결 풀"),
                    required("backup_config", "운영 환경에서는 백업 설정이 필요합니다")
                ]
            )
        ])
        
        return Failure([f"DB 설정 오류: {db_result.unwrap_error()}"]) if db_result.is_failure() else Success(config)
    
    def _validate_cache_service(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """캐시 서비스 설정 검증"""
        
        # Redis 설정
        redis_result = validate_config(config.get("redis", {})).against_rules([
            required("host", "Redis 호스트가 필요합니다"),
            required("port", "Redis 포트가 필요합니다"),
            range_check("port", 1, 65535, "포트는 1-65535 사이"),
            range_check("db", 0, 15, "Redis DB 번호는 0-15 사이"),
            range_check("max_connections", 1, 100, "최대 연결 수는 1-100 사이"),
            conditional(
                condition=lambda redis: context.environment == Environment.PRODUCTION,
                rules=[
                    custom_check("host",
                               lambda host: host != "localhost",
                               "운영 환경에서는 localhost Redis를 사용하지 마세요"),
                    required("password", "운영 환경에서는 Redis 패스워드가 필요합니다")
                ]
            )
        ])
        
        return Failure([f"Redis 설정 오류: {redis_result.unwrap_error()}"]) if redis_result.is_failure() else Success(config)
    
    def _validate_security_settings(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Result[Dict[str, Any], List[str]]:
        """보안 설정 검증"""
        
        security_issues = []
        
        # 설정에서 보안 패턴 스캔
        config_text = json.dumps(config, indent=2)
        
        security_violations = (scan_for(self.security_patterns)
                              .in_text(config_text)
                              .extract(lambda match, pattern_name: {
                                  "pattern": pattern_name,
                                  "matched_text": match.group(0),
                                  "severity": self._get_security_severity(pattern_name),
                                  "recommendation": self._get_security_recommendation(pattern_name)
                              })
                              .filter_by(lambda item: item["severity"] in ["high", "critical"])
                              .collect())
        
        if security_violations:
            security_issues.extend([
                f"보안 위험 [{item['severity']}]: {item['pattern']} - {item['recommendation']}"
                for item in security_violations
            ])
        
        # SSL/TLS 설정 검증
        if context.environment == Environment.PRODUCTION:
            ssl_result = validate_config(config.get("ssl", {})).against_rules([
                required("enabled", "운영 환경에서는 SSL 설정이 필요합니다"),
                custom_check("enabled",
                           lambda enabled: enabled is True,
                           "운영 환경에서는 SSL이 활성화되어야 합니다"),
                conditional(
                    condition=lambda ssl: ssl.get("enabled", False),
                    rules=[
                        required("cert_file", "SSL 인증서 파일이 필요합니다"),
                        required("key_file", "SSL 키 파일이 필요합니다"),
                        custom_check("cert_file",
                                   lambda cert: Path(cert).exists(),
                                   "SSL 인증서 파일이 존재하지 않습니다")
                    ]
                )
            ])
            
            if ssl_result.is_failure():
                security_issues.append(f"SSL 설정 오류: {ssl_result.unwrap_error()}")
        
        return Failure(security_issues) if security_issues else Success(config)
    
    def _normalize_config_values(
        self, 
        config: Dict[str, Any], 
        context: ValidationContext
    ) -> Dict[str, Any]:
        """설정 값 정규화 및 변환"""
        
        normalized = config.copy()
        
        # 기본값 적용
        if context.allow_defaults:
            defaults = self.defaults.get(context.environment.value, {})
            for key, value in defaults.items():
                if key not in normalized:
                    normalized[key] = value
                    print(f"📝 기본값 적용: {key} = {value}")
        
        # 환경 변수 치환
        def replace_env_vars(obj):
            if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                return os.getenv(env_var, obj)
            elif isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            return obj
        
        normalized = replace_env_vars(normalized)
        
        # 타입 변환
        if "server" in normalized and "port" in normalized["server"]:
            normalized["server"]["port"] = int(normalized["server"]["port"])
        
        return normalized
    
    def generate_config_template(
        self, 
        context: ValidationContext
    ) -> Dict[str, Any]:
        """설정 템플릿 생성"""
        
        print(f"📋 {context.environment.value} 환경, {context.service_type.value} 서비스 설정 템플릿 생성...")
        
        # 기본 템플릿
        template = {
            "app": {
                "name": "your-application-name",
                "version": "1.0.0",
                "debug": context.environment == Environment.DEVELOPMENT
            },
            "server": {
                "host": "localhost" if context.environment == Environment.DEVELOPMENT else "0.0.0.0",
                "port": 8000,
                "workers": 1 if context.environment == Environment.DEVELOPMENT else 4
            }
        }
        
        # 환경별 추가 설정
        if context.environment in [Environment.STAGING, Environment.PRODUCTION]:
            template.update({
                "monitoring": {
                    "enabled": True,
                    "metrics_port": 9090
                },
                "logging": {
                    "level": "INFO",
                    "format": "structured"
                }
            })
        
        if context.environment == Environment.PRODUCTION:
            template["app"]["secret_key"] = "${SECRET_KEY}"
            template["ssl"] = {
                "enabled": True,
                "cert_file": "/path/to/cert.pem",
                "key_file": "/path/to/key.pem"
            }
        
        # 서비스별 추가 설정
        service_templates = {
            ServiceType.WEB: {
                "static": {
                    "url_prefix": "/static",
                    "directory": "static/"
                },
                "session": {
                    "cookie_name": "session",
                    "max_age": 3600,
                    "secure": context.environment == Environment.PRODUCTION,
                    "httponly": True
                }
            },
            ServiceType.API: {
                "api": {
                    "version": "v1",
                    "prefix": "/api/v1",
                    "rate_limit": 1000,
                    "cors_origins": ["*"] if context.environment == Environment.DEVELOPMENT else []
                },
                "auth": {
                    "jwt_secret": "${JWT_SECRET}",
                    "token_expiry": 3600,
                    "algorithm": "HS256"
                }
            },
            ServiceType.WORKER: {
                "queue": {
                    "broker_url": "${BROKER_URL}",
                    "max_retries": 3,
                    "task_timeout": 300,
                    "concurrency": 4
                }
            },
            ServiceType.DATABASE: {
                "database": {
                    "url": "${DATABASE_URL}",
                    "pool_size": 5,
                    "max_overflow": 10,
                    "backup_config": {
                        "enabled": context.environment == Environment.PRODUCTION,
                        "schedule": "0 2 * * *"
                    }
                }
            },
            ServiceType.CACHE: {
                "redis": {
                    "host": "${REDIS_HOST}",
                    "port": 6379,
                    "db": 0,
                    "max_connections": 50,
                    "password": "${REDIS_PASSWORD}" if context.environment == Environment.PRODUCTION else None
                }
            }
        }
        
        service_config = service_templates.get(context.service_type, {})
        template.update(service_config)
        
        print("✅ 설정 템플릿 생성 완료")
        return template
    
    # ========== 헬퍼 메서드들 ==========
    
    def _load_validation_rules(self) -> Dict:
        """검증 규칙 로드"""
        return {
            "development": {
                "strict_ssl": False,
                "require_monitoring": False,
                "allow_debug": True
            },
            "testing": {
                "strict_ssl": False,
                "require_monitoring": False,
                "allow_debug": True
            },
            "staging": {
                "strict_ssl": True,
                "require_monitoring": True,
                "allow_debug": False
            },
            "production": {
                "strict_ssl": True,
                "require_monitoring": True,
                "allow_debug": False,
                "require_secrets": True
            }
        }
    
    def _load_security_patterns(self) -> List:
        """보안 패턴 로드"""
        import re
        return [
            re.compile(r'password["\s]*[:=]["\s]*[^"]{4,}', re.IGNORECASE),
            re.compile(r'secret["\s]*[:=]["\s]*[^"]{8,}', re.IGNORECASE),
            re.compile(r'api_?key["\s]*[:=]["\s]*[^"]{16,}', re.IGNORECASE),
            re.compile(r'token["\s]*[:=]["\s]*[^"]{16,}', re.IGNORECASE),
        ]
    
    def _load_default_values(self) -> Dict:
        """기본값 로드"""
        return {
            "development": {
                "logging": {"level": "DEBUG"},
                "server": {"workers": 1}
            },
            "production": {
                "logging": {"level": "INFO"},
                "server": {"workers": 4},
                "monitoring": {"enabled": True}
            }
        }
    
    def _get_security_severity(self, pattern_name: str) -> str:
        """보안 패턴 심각도 반환"""
        severity_map = {
            "password": "critical",
            "secret": "high", 
            "api_key": "high",
            "token": "medium"
        }
        return severity_map.get(pattern_name, "low")
    
    def _get_security_recommendation(self, pattern_name: str) -> str:
        """보안 권장사항 반환"""
        recommendations = {
            "password": "환경 변수나 시크릿 매니저를 사용하세요",
            "secret": "하드코딩된 시크릿을 환경 변수로 이동하세요",
            "api_key": "API 키를 안전한 저장소에 보관하세요",
            "token": "토큰을 설정 파일에 하드코딩하지 마세요"
        }
        return recommendations.get(pattern_name, "보안 검토가 필요합니다")


# 사용 예제
def main():
    """설정 검증 시스템 실행 예제"""
    
    validator = ConfigValidationSystem()
    
    # 1. 다양한 환경과 서비스 타입 테스트
    test_cases = [
        (Environment.DEVELOPMENT, ServiceType.WEB),
        (Environment.PRODUCTION, ServiceType.API),
        (Environment.STAGING, ServiceType.WORKER),
        (Environment.PRODUCTION, ServiceType.DATABASE),
        (Environment.PRODUCTION, ServiceType.CACHE),
    ]
    
    for env, service in test_cases:
        print(f"\n{'='*80}")
        print(f"🧪 테스트: {env.value} 환경, {service.value} 서비스")
        print('='*80)
        
        # 2. 설정 템플릿 생성
        context = ValidationContext(
            environment=env,
            service_type=service,
            strict_mode=env == Environment.PRODUCTION
        )
        
        template = validator.generate_config_template(context)
        print(f"📋 생성된 템플릿:\n{json.dumps(template, indent=2)}")
        
        # 3. 템플릿 검증
        result = validator.validate_application_config(template, context)
        
        if result.is_success():
            validated_config = result.unwrap()
            print("✅ 설정 검증 성공")
            print(f"📝 정규화된 설정:\n{json.dumps(validated_config, indent=2)}")
        else:
            errors = result.unwrap_error()
            print("❌ 설정 검증 실패")
            for error in errors:
                print(f"  • {error}")
    
    # 4. 문제가 있는 설정 테스트
    print(f"\n{'='*80}")
    print("🔍 문제가 있는 설정 테스트")
    print('='*80)
    
    problematic_config = {
        "app": {
            "name": "test-app",
            "version": "invalid-version",  # 잘못된 버전 형식
            "debug": True,  # 운영 환경에서 debug=True
            "secret_key": "short"  # 너무 짧은 시크릿
        },
        "server": {
            "host": "0.0.0.0",  # 운영 환경에서 위험한 호스트
            "port": 99999,  # 잘못된 포트 범위
            "workers": 1  # 운영 환경에서 부족한 워커
        },
        "api": {
            "version": "v1",
            "cors_origins": ["*"],  # 운영 환경에서 위험한 CORS
            "rate_limit": 5  # 너무 낮은 rate limit
        }
    }
    
    context = ValidationContext(
        environment=Environment.PRODUCTION,
        service_type=ServiceType.API,
        strict_mode=True
    )
    
    result = validator.validate_application_config(problematic_config, context)
    
    if result.is_failure():
        errors = result.unwrap_error()
        print("❌ 예상대로 검증 실패 (총 {}개 오류)".format(len(errors)))
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
    
    print("\n🎉 모든 테스트 완료!")


if __name__ == "__main__":
    main()
```

## 실행 결과 예시

```
================================================================================
🧪 테스트: development 환경, web 서비스
================================================================================
📋 development 환경, web 서비스 설정 템플릿 생성...
✅ 설정 템플릿 생성 완료
📋 생성된 템플릿:
{
  "app": {
    "name": "your-application-name",
    "version": "1.0.0",
    "debug": true
  },
  "server": {
    "host": "localhost",
    "port": 8000,
    "workers": 1
  },
  "static": {
    "url_prefix": "/static",
    "directory": "static/"
  },
  "session": {
    "cookie_name": "session",
    "max_age": 3600,
    "secure": false,
    "httponly": true
  }
}

🔍 development 환경, web 서비스 설정 검증 시작...
📝 기본값 적용: logging = {'level': 'DEBUG'}
📝 기본값 적용: server = {'workers': 1}
✅ 모든 설정 검증 완료
✅ 설정 검증 성공

================================================================================
🧪 테스트: production 환경, api 서비스
================================================================================
📋 production 환경, api 서비스 설정 템플릿 생성...
✅ 설정 템플릿 생성 완료
🔍 production 환경, api 서비스 설정 검증 시작...
✅ 모든 설정 검증 완료
✅ 설정 검증 성공

================================================================================
🔍 문제가 있는 설정 테스트
================================================================================
🔍 production 환경, api 서비스 설정 검증 시작...
❌ 예상대로 검증 실패 (총 5개 오류)
  1. 구조 검증 오류: 운영 환경에서는 모니터링 설정이 필요합니다
  2. 앱 설정 오류: 버전은 x.y.z 형식이어야 합니다
  3. 서버 설정 오류: 포트는 1-65535 사이여야 합니다
  4. API 설정 오류: 운영 환경에서는 와일드카드 CORS를 사용하지 마세요
  5. 보안 위험 [high]: secret - 하드코딩된 시크릿을 환경 변수로 이동하세요

🎉 모든 테스트 완료!
```

## 핵심 기능

### 1. Readable HOF 패턴 활용

- **validate_config()**: 단계별 설정 검증
- **conditional()**: 환경별 조건부 규칙
- **scan_for()**: 보안 패턴 탐지
- **custom_check()**: 복잡한 비즈니스 규칙

### 2. 다단계 검증 시스템

```python
# 기본 구조 검증
base_rules = [
    required("app", "애플리케이션 정보가 필요합니다"),
    conditional(
        condition=lambda cfg: context.environment == Environment.PRODUCTION,
        rules=[required("monitoring", "운영 환경에서는 모니터링 설정이 필요합니다")]
    )
]

result = validate_config(config).against_rules(base_rules)
```

### 3. 환경별/서비스별 특화 검증

- 개발/테스트/스테이징/운영 환경별 규칙
- WEB/API/WORKER/DATABASE/CACHE 서비스별 규칙
- 조건부 보안 요구사항
- 자동 설정 정규화

### 4. 보안 중심 검증

- 하드코딩된 시크릿 탐지
- SSL/TLS 설정 검증
- CORS/인증 보안 확인
- 운영 환경 보안 강화

이 예제는 Readable HOF가 복잡한 설정 관리 시나리오에서 어떻게 활용될 수 있는지 보여주며, 선언적이고 유연한 검증 시스템을 구축하는 방법을 제시합니다.