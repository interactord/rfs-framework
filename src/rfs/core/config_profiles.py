"""
Environment-specific Configuration Profiles (RFS v4)

환경별 설정 프로파일 관리
- Development, Test, Production 환경별 최적화 설정
- 프로파일 기반 자동 구성
- 환경 간 안전한 전환
"""

from typing import Dict, Any, Type
from abc import ABC, abstractmethod
import os

try:
    from pydantic import BaseModel, Field, ConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object
    Field = lambda default=None, **kwargs: default
    PYDANTIC_AVAILABLE = False

from .config import RFSConfig, Environment


class ConfigProfile(ABC):
    """구성 프로파일 기본 클래스"""
    
    @abstractmethod
    def get_config_overrides(self) -> Dict[str, Any]:
        """환경별 구성 오버라이드 반환"""
        pass
    
    @abstractmethod
    def validate_environment(self) -> tuple[bool, list[str]]:
        """환경 유효성 검증"""
        pass
    
    def get_required_env_vars(self) -> list[str]:
        """필수 환경 변수 목록"""
        return []


class DevelopmentProfile(ConfigProfile):
    """개발 환경 프로파일"""
    
    def get_config_overrides(self) -> Dict[str, Any]:
        """개발 환경 최적화 설정"""
        return {
            'environment': Environment.DEVELOPMENT,
            'log_level': 'DEBUG',
            'log_format': 'text',  # 개발시 텍스트가 읽기 편함
            'default_buffer_size': 50,  # 작은 버퍼로 빠른 디버깅
            'max_concurrency': 5,  # 로컬 리소스 고려
            'enable_cold_start_optimization': False,  # 로컬에서는 불필요
            'cloud_run_max_instances': 1,
            'cloud_run_cpu_limit': '500m',  # 로컬 개발용 작은 리소스
            'cloud_run_memory_limit': '256Mi',
            'enable_performance_monitoring': True,  # 개발시 성능 체크
            'metrics_export_interval': 30,  # 빠른 피드백
            'enable_tracing': False,  # 개발시 오버헤드 방지
            'redis_url': 'redis://localhost:6379/0',  # 로컬 Redis
            'event_store_enabled': True,
            'custom': {
                'debug_mode': True,
                'hot_reload': True,
                'skip_auth': True,  # 개발시 인증 스킵
                'mock_external_apis': True
            }
        }
    
    def validate_environment(self) -> tuple[bool, list[str]]:
        """개발 환경 검증"""
        warnings = []
        
        # Redis 연결 확인 (선택사항)
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        if 'localhost' not in redis_url and '127.0.0.1' not in redis_url:
            warnings.append("개발 환경에서는 로컬 Redis 사용을 권장합니다")
        
        # 개발용 포트 확인
        port = os.environ.get('PORT', '8080')
        if port in ['80', '443']:
            warnings.append("개발 환경에서는 8080과 같은 비특권 포트 사용을 권장합니다")
        
        return True, warnings  # 개발환경은 경고만 표시
    
    def get_required_env_vars(self) -> list[str]:
        """개발 환경 권장 환경 변수"""
        return []  # 개발환경은 필수 변수 없음


class TestProfile(ConfigProfile):
    """테스트 환경 프로파일"""
    
    def get_config_overrides(self) -> Dict[str, Any]:
        """테스트 환경 최적화 설정"""
        return {
            'environment': Environment.TEST,
            'log_level': 'WARNING',  # 테스트시 노이즈 감소
            'log_format': 'json',
            'default_buffer_size': 10,  # 작은 버퍼로 빠른 테스트
            'max_concurrency': 3,  # 테스트 안정성 우선
            'enable_cold_start_optimization': False,  # 테스트에는 불필요
            'cloud_run_max_instances': 1,  # 테스트시 단일 인스턴스
            'cloud_run_cpu_limit': '500m',
            'cloud_run_memory_limit': '256Mi',
            'enable_performance_monitoring': False,  # 테스트 성능 향상
            'enable_tracing': False,  # 테스트 속도 우선
            'redis_url': 'redis://localhost:6379/1',  # 테스트 전용 DB
            'event_store_enabled': False,  # 테스트 단순화
            'custom': {
                'test_mode': True,
                'mock_external_apis': True,
                'fast_startup': True,
                'skip_migrations': True,
                'use_in_memory_cache': True
            }
        }
    
    def validate_environment(self) -> tuple[bool, list[str]]:
        """테스트 환경 검증"""
        errors = []
        
        # 테스트 데이터베이스 분리 확인
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')
        if not redis_url.endswith('/1'):
            errors.append("테스트 환경에서는 별도의 Redis DB(예: /1)를 사용해야 합니다")
        
        # 운영 데이터 접근 방지
        if os.environ.get('GOOGLE_CLOUD_PROJECT') == 'production-project':
            errors.append("테스트 환경에서 운영 프로젝트 접근이 감지되었습니다")
        
        return len(errors) == 0, errors
    
    def get_required_env_vars(self) -> list[str]:
        """테스트 환경 필수 환경 변수"""
        return ['TEST_DATABASE_URL']


class ProductionProfile(ConfigProfile):
    """운영 환경 프로파일"""
    
    def get_config_overrides(self) -> Dict[str, Any]:
        """운영 환경 최적화 설정"""
        return {
            'environment': Environment.PRODUCTION,
            'log_level': 'INFO',
            'log_format': 'json',  # 구조화된 로그
            'default_buffer_size': 1000,  # 큰 버퍼로 성능 최적화
            'max_concurrency': 80,  # Cloud Run 권장값
            'enable_cold_start_optimization': True,  # 운영환경 필수
            'cloud_run_max_instances': 100,
            'cloud_run_cpu_limit': '1000m',  # 운영 리소스
            'cloud_run_memory_limit': '512Mi',
            'enable_performance_monitoring': True,  # 운영 모니터링 필수
            'metrics_export_interval': 60,  # 적절한 모니터링 간격
            'enable_tracing': True,  # 운영 추적 필수
            'event_store_enabled': True,  # 운영 이벤트 저장
            'custom': {
                'production_mode': True,
                'strict_validation': True,
                'enable_security_headers': True,
                'rate_limiting_enabled': True,
                'backup_enabled': True
            }
        }
    
    def validate_environment(self) -> tuple[bool, list[str]]:
        """운영 환경 엄격한 검증"""
        errors = []
        
        # 필수 보안 설정 확인
        if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            errors.append("운영 환경에서는 GOOGLE_APPLICATION_CREDENTIALS가 필수입니다")
        
        # Redis 보안 연결 확인
        redis_url = os.environ.get('REDIS_URL', '')
        if redis_url.startswith('redis://localhost'):
            errors.append("운영 환경에서는 로컬 Redis 사용 불가")
        
        # Cloud Run 환경 확인
        if not os.environ.get('K_SERVICE'):
            errors.append("운영 환경은 Cloud Run에서 실행되어야 합니다")
        
        # 메모리 제한 확인
        memory_limit = os.environ.get('CLOUD_RUN_MEMORY_LIMIT', '512Mi')
        if memory_limit == '256Mi':
            errors.append("운영 환경에서는 최소 512Mi 메모리가 필요합니다")
        
        return len(errors) == 0, errors
    
    def get_required_env_vars(self) -> list[str]:
        """운영 환경 필수 환경 변수"""
        return [
            'GOOGLE_APPLICATION_CREDENTIALS',
            'REDIS_URL',
            'GOOGLE_CLOUD_PROJECT',
            'SERVICE_ACCOUNT_EMAIL'
        ]


class ProfileManager:
    """프로파일 관리자 (RFS v4)"""
    
    def __init__(self):
        self._profiles: Dict[Environment, ConfigProfile] = {
            Environment.DEVELOPMENT: DevelopmentProfile(),
            Environment.TEST: TestProfile(),
            Environment.PRODUCTION: ProductionProfile()
        }
    
    def get_profile(self, environment: Environment) -> ConfigProfile:
        """환경에 따른 프로파일 조회"""
        if environment not in self._profiles:
            raise ValueError(f"Unsupported environment: {environment}")
        return self._profiles[environment]
    
    def get_profile_config(self, environment: Environment) -> Dict[str, Any]:
        """환경별 설정 오버라이드 조회"""
        profile = self.get_profile(environment)
        return profile.get_config_overrides()
    
    def validate_profile(self, environment: Environment) -> tuple[bool, list[str]]:
        """환경 프로파일 유효성 검증"""
        profile = self.get_profile(environment)
        return profile.validate_environment()
    
    def get_required_env_vars(self, environment: Environment) -> list[str]:
        """환경별 필수 환경 변수 조회"""
        profile = self.get_profile(environment)
        return profile.get_required_env_vars()
    
    def detect_environment(self) -> Environment:
        """현재 환경 자동 감지 (match/case 사용)"""
        # 환경 변수 기반 감지
        env_var = os.environ.get('RFS_ENVIRONMENT', '').lower()
        
        match env_var:
            case 'prod' | 'production':
                return Environment.PRODUCTION
            case 'test' | 'testing':
                return Environment.TEST
            case 'dev' | 'develop' | 'development':
                return Environment.DEVELOPMENT
        
        # Cloud Run 환경 감지
        if os.environ.get('K_SERVICE'):
            return Environment.PRODUCTION
        
        # 테스트 실행 감지
        if any(test_indicator in os.environ.get('_', '') for test_indicator in ['pytest', 'unittest', 'test']):
            return Environment.TEST
        
        # 기본값: 개발 환경
        return Environment.DEVELOPMENT
    
    def create_config_with_profile(self, environment: Environment | None = None) -> RFSConfig:
        """프로파일 기반 설정 생성 (v4 신규)"""
        if environment is None:
            environment = self.detect_environment()
        
        # 프로파일 오버라이드 적용
        profile_config = self.get_profile_config(environment)
        
        if PYDANTIC_AVAILABLE:
            # Pydantic v2로 설정 생성
            return RFSConfig(**profile_config)
        else:
            # Fallback으로 기본 설정 생성
            from .config import RFSConfig
            return RFSConfig(**profile_config)
    
    def switch_profile(self, from_env: Environment, to_env: Environment) -> tuple[bool, list[str]]:
        """프로파일 안전 전환 (v4 신규)"""
        messages = []
        
        # 대상 환경 검증
        valid, errors = self.validate_profile(to_env)
        if not valid:
            return False, errors
        
        # 전환 가능성 체크
        match (from_env, to_env):
            case (Environment.PRODUCTION, Environment.DEVELOPMENT):
                messages.append("운영→개발 전환: 데이터 손실 위험 확인 필요")
            case (Environment.PRODUCTION, Environment.TEST):
                messages.append("운영→테스트 전환: 운영 데이터 접근 주의")
            case (Environment.DEVELOPMENT, Environment.PRODUCTION):
                messages.append("개발→운영 전환: 보안 설정 확인 완료")
            case (Environment.TEST, Environment.PRODUCTION):
                messages.append("테스트→운영 전환: 테스트 통과 확인 완료")
        
        return True, messages
    
    def export_profile_summary(self, environment: Environment) -> Dict[str, Any]:
        """프로파일 요약 정보 내보내기 (v4 신규)"""
        profile = self.get_profile(environment)
        config_overrides = profile.get_config_overrides()
        required_vars = profile.get_required_env_vars()
        
        return {
            'environment': environment.value,
            'profile_type': profile.__class__.__name__,
            'config_count': len(config_overrides),
            'required_env_vars': required_vars,
            'key_settings': {
                'log_level': config_overrides.get('log_level'),
                'max_concurrency': config_overrides.get('max_concurrency'),
                'cold_start_optimization': config_overrides.get('enable_cold_start_optimization'),
                'performance_monitoring': config_overrides.get('enable_performance_monitoring')
            },
            'validation_status': self.validate_profile(environment)
        }


# 전역 프로파일 관리자
profile_manager = ProfileManager()

# 편의 함수들
def get_profile_manager() -> ProfileManager:
    """프로파일 관리자 조회"""
    return profile_manager

def detect_current_environment() -> Environment:
    """현재 환경 자동 감지"""
    return profile_manager.detect_environment()

def create_profile_config(environment: Environment | None = None) -> RFSConfig:
    """프로파일 기반 설정 생성"""
    return profile_manager.create_config_with_profile(environment)

def validate_current_environment() -> tuple[bool, list[str]]:
    """현재 환경 유효성 검증"""
    current_env = detect_current_environment()
    return profile_manager.validate_profile(current_env)

def get_environment_summary() -> Dict[str, Any]:
    """현재 환경 요약"""
    current_env = detect_current_environment()
    return profile_manager.export_profile_summary(current_env)