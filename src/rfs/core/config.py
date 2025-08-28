"""
Configuration Management (RFS v4)

Pydantic v2 기반 환경 변수 및 설정 관리
"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

try:
    from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict

    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object  # type: ignore[misc,assignment]
    BaseSettings = object  # type: ignore[misc,assignment]
    Field = lambda default=None, **kwargs: default
    PYDANTIC_AVAILABLE = False


class Environment(str, Enum):
    """실행 환경"""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


if PYDANTIC_AVAILABLE:

    class RFSBaseSettings(BaseSettings):
        """RFS Framework 표준 설정 베이스 클래스

        모든 RFS Framework 기반 프로젝트에서 사용할 수 있는
        범용 설정 베이스 클래스입니다.

        주요 특징:
        - Pydantic V2 기반 타입 안전성
        - 환경 변수 자동 로드
        - 표준 검증 로직 내장
        - RFS 에러 처리 통합
        - 개발/운영 환경별 설정 지원

        Example:
            >>> class MyAppSettings(RFSBaseSettings):
            ...     app_name: str = "my-app"
            ...     debug: bool = False
            ...
            ...     @field_validator("app_name")
            ...     @classmethod
            ...     def validate_app_name(cls, v: str) -> str:
            ...         return v.lower().replace(" ", "-")
        """

        model_config = SettingsConfigDict(
            # 환경 변수 설정
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            validate_default=True,
            validate_assignment=True,
            # 추가 필드 허용 (확장성)
            extra="allow",
            # 문자열 검증 모드
            str_strip_whitespace=True,
        )

        # 기본 환경 설정
        environment: Environment = Field(
            default=Environment.DEVELOPMENT, description="애플리케이션 실행 환경"
        )

        # 로깅 설정
        log_level: str = Field(
            default="INFO",
            pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
            description="로그 레벨",
        )

        log_format: str = Field(
            default="json", pattern="^(json|text)$", description="로그 출력 형식"
        )

        # 디버그 모드 (환경별 자동 설정)
        debug: bool = Field(default=False, description="디버그 모드 활성화")

        # 확장 가능한 사용자 정의 설정
        custom_settings: Dict[str, Any] = Field(
            default_factory=dict, description="사용자 정의 설정값들"
        )

        @field_validator("environment", mode="before")
        @classmethod
        def validate_environment(cls, v: Any) -> Environment:
            """환경 값 검증 및 정규화"""
            if isinstance(v, str):
                env_mapping = {
                    "dev": Environment.DEVELOPMENT,
                    "develop": Environment.DEVELOPMENT,
                    "development": Environment.DEVELOPMENT,
                    "test": Environment.TEST,
                    "testing": Environment.TEST,
                    "prod": Environment.PRODUCTION,
                    "production": Environment.PRODUCTION,
                }
                if v.lower() in env_mapping:
                    return env_mapping[v.lower()]
                else:
                    raise ValueError(f"Invalid environment value: {v}")
            return v if isinstance(v, Environment) else Environment.DEVELOPMENT

        @field_validator("*", mode="before")
        @classmethod
        def validate_all_fields(cls, v: Any, info: Any) -> Any:
            """모든 필드에 대한 기본 검증 로직

            - 빈 문자열을 None으로 변환
            - 대소문자 정규화 처리
            - 기본 타입 변환
            """
            if isinstance(v, str):
                # 빈 문자열 처리
                if v.strip() == "":
                    return None
                # 불린 문자열 변환
                if v.lower() in ("true", "yes", "1", "on"):
                    return True
                elif v.lower() in ("false", "no", "0", "off"):
                    return False
            return v

        @model_validator(mode="after")
        def validate_settings_consistency(self) -> "RFSBaseSettings":
            """설정값들 간의 일관성 검증"""
            # 개발 환경에서는 자동으로 디버그 모드 활성화
            if self.environment == Environment.DEVELOPMENT and not self.debug:
                object.__setattr__(self, "debug", True)

            # 운영 환경에서는 디버그 모드 비활성화
            elif self.environment == Environment.PRODUCTION and self.debug:
                import warnings

                warnings.warn(
                    "운영 환경에서는 디버그 모드를 비활성화하는 것을 권장합니다."
                )

            return self

        # 편의 메서드들
        def is_development(self) -> bool:
            """개발 환경 여부 확인"""
            return self.environment == Environment.DEVELOPMENT

        def is_production(self) -> bool:
            """운영 환경 여부 확인"""
            return self.environment == Environment.PRODUCTION

        def is_test(self) -> bool:
            """테스트 환경 여부 확인"""
            return self.environment == Environment.TEST

        def get_custom_setting(self, key: str, default: Any = None) -> Any:
            """사용자 정의 설정값 가져오기"""
            return self.custom_settings.get(key, default)

        def set_custom_setting(self, key: str, value: Any) -> None:
            """사용자 정의 설정값 설정"""
            self.custom_settings[key] = value

        def to_dict(self) -> Dict[str, Any]:
            """설정을 딕셔너리로 변환"""
            return self.model_dump()

        def to_json(self) -> str:
            """설정을 JSON 문자열로 변환"""
            return self.model_dump_json(indent=2)

    class RFSConfig(RFSBaseSettings):
        """RFS Framework v4 전용 설정 클래스 (Pydantic v2 기반)

        RFS Framework의 모든 고급 기능들을 위한 설정을 제공합니다.
        RFSBaseSettings를 상속하여 기본 기능과 함께
        Cloud Run, Redis, 모니터링 등의 고급 설정을 포함합니다.
        """

        model_config = SettingsConfigDict(
            env_prefix="RFS_",  # RFS_ 접두사로 환경 변수 읽기
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            validate_default=True,
            validate_assignment=True,
            extra="allow",
        )
        default_buffer_size: int = Field(
            default=100, ge=1, le=10000, description="기본 버퍼 크기"
        )
        max_concurrency: int = Field(
            default=10, ge=1, le=1000, description="최대 동시 실행 수"
        )
        enable_cold_start_optimization: bool = Field(
            default=True, description="Cloud Run 콜드 스타트 최적화 활성화"
        )
        cloud_run_max_instances: int = Field(
            default=100, ge=1, le=3000, description="Cloud Run 최대 인스턴스 수"
        )
        cloud_run_cpu_limit: str = Field(
            default="1000m", description="Cloud Run CPU 제한"
        )
        cloud_run_memory_limit: str = Field(
            default="512Mi", description="Cloud Run 메모리 제한"
        )
        cloud_tasks_queue_name: str = Field(
            default="default-queue",
            min_length=1,
            max_length=100,
            description="Cloud Tasks 큐 이름",
        )
        redis_url: str = Field(
            default="redis://localhost:6379", description="Redis 연결 URL"
        )
        event_store_enabled: bool = Field(
            default=True, description="이벤트 스토어 활성화"
        )
        log_level: str = Field(
            default="INFO",
            pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
            description="로그 레벨",
        )
        log_format: str = Field(
            default="json", pattern="^(json|text)$", description="로그 형식"
        )
        enable_tracing: bool = Field(default=False, description="분산 추적 활성화")
        api_key_header: str = Field(
            default="X-API-Key", min_length=1, description="API 키 헤더명"
        )
        enable_performance_monitoring: bool = Field(
            default=False, description="성능 모니터링 활성화"
        )
        metrics_export_interval: int = Field(
            default=60, ge=10, le=3600, description="메트릭 내보내기 간격(초)"
        )
        custom: Dict[str, Any] = Field(default_factory=dict)

        @field_validator("environment", mode="before")
        @classmethod
        def validate_environment(cls, v: Any) -> Environment:
            """환경 값 검증 및 변환"""
            if type(v).__name__ == "str":
                match v.lower():
                    case "dev" | "develop" | "development":
                        return Environment.DEVELOPMENT
                    case "test" | "testing":
                        return Environment.TEST
                    case "prod" | "production":
                        return Environment.PRODUCTION
                    case _:
                        raise ValueError(f"Invalid environment value: {v}")
            return v if type(v).__name__ == "Environment" else Environment.DEVELOPMENT

        @field_validator("cloud_run_cpu_limit")
        @classmethod
        def validate_cpu_limit(cls, v: str) -> str:
            """Cloud Run CPU 제한 검증"""
            if not (v.endswith("m") or v.endswith("Mi")):
                raise ValueError("CPU limit must end with 'm' or 'Mi'")
            return v

        @field_validator("cloud_run_memory_limit")
        @classmethod
        def validate_memory_limit(cls, v: str) -> str:
            """Cloud Run 메모리 제한 검증"""
            if not (v.endswith("Mi") or v.endswith("Gi")):
                raise ValueError("Memory limit must end with 'Mi' or 'Gi'")
            return v

        @model_validator(mode="after")
        def validate_config_consistency(self) -> "RFSConfig":
            """설정 일관성 검증"""
            if self.environment == Environment.PRODUCTION:
                if not self.enable_tracing:
                    print("Warning: 운영 환경에서는 추적을 활성화하는 것을 권장합니다.")
                if (
                    self.enable_performance_monitoring
                    and self.metrics_export_interval > 300
                ):
                    print(
                        "Warning: 성능 모니터링 활성화 시 메트릭 간격을 300초 이하로 설정하는 것을 권장합니다."
                    )
            return self

        def is_development(self) -> bool:
            """개발 환경 여부"""
            return self.environment == Environment.DEVELOPMENT

        def is_production(self) -> bool:
            """운영 환경 여부"""
            return self.environment == Environment.PRODUCTION

        def is_test(self) -> bool:
            """테스트 환경 여부"""
            return self.environment == Environment.TEST

        def export_cloud_run_config(self) -> Dict[str, Any]:
            """Cloud Run 배포용 설정 내보내기 (v4 신규)"""
            return {
                "env_vars": {
                    "RFS_ENVIRONMENT": self.environment.value,
                    "RFS_DEFAULT_BUFFER_SIZE": str(self.default_buffer_size),
                    "RFS_MAX_CONCURRENCY": str(self.max_concurrency),
                    "RFS_ENABLE_COLD_START_OPTIMIZATION": str(
                        self.enable_cold_start_optimization
                    ).lower(),
                    "RFS_REDIS_URL": self.redis_url,
                    "RFS_LOG_LEVEL": self.log_level,
                    "RFS_ENABLE_TRACING": str(self.enable_tracing).lower(),
                },
                "resource_limits": {
                    "cpu": self.cloud_run_cpu_limit,
                    "memory": self.cloud_run_memory_limit,
                },
                "scaling": {"max_instances": self.cloud_run_max_instances},
            }

    # Pydantic 환경에서는 RFSBaseSettings를 전역에서 사용 가능하게 export
    # 이는 다른 모듈에서 조건 없이 import할 수 있도록 함
    pass

else:
    from dataclasses import dataclass, field

    # Pydantic 불가용시 더미 클래스 생성
    class RFSBaseSettings:  # type: ignore[no-redef]
        """RFSBaseSettings 더미 구현 (Pydantic 불가용 환경)"""

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def is_development(self) -> bool:
            return (
                getattr(self, "environment", Environment.DEVELOPMENT)
                == Environment.DEVELOPMENT
            )

        def is_production(self) -> bool:
            return (
                getattr(self, "environment", Environment.DEVELOPMENT)
                == Environment.PRODUCTION
            )

        def is_test(self) -> bool:
            return (
                getattr(self, "environment", Environment.DEVELOPMENT)
                == Environment.TEST
            )

    @dataclass
    class RFSConfig:  # type: ignore[no-redef]
        """RFS Framework 설정 (Fallback)"""

        environment: Environment = Environment.DEVELOPMENT
        default_buffer_size = 100
        max_concurrency = 10
        enable_cold_start_optimization = True
        cloud_run_max_instances = 100
        cloud_tasks_queue_name = "default-queue"
        redis_url = "redis://localhost:6379"
        event_store_enabled = True
        log_level = "INFO"
        log_format = "json"
        enable_tracing = False
        api_key_header = "X-API-Key"
        custom: Dict[str, Any] = field(default_factory=dict)

        def is_development(self) -> bool:
            return self.environment == Environment.DEVELOPMENT

        def is_production(self) -> bool:
            return self.environment == Environment.PRODUCTION

        def is_test(self) -> bool:
            return self.environment == Environment.TEST


class ConfigManager:
    """설정 관리자 (RFS v4 현대화)"""

    _instance: Optional["ConfigManager"] = None
    _initialized = False

    def __new__(cls, config_path: str | None = None, env_file: str | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str | None = None, env_file: str | None = None):
        if self._initialized:
            return
        self.config_path = config_path
        self.env_file = env_file or ".env"
        self._config: RFSConfig | None = None
        self._env_prefix = "RFS_"
        self._initialized = True

    def load_config(self, force_reload=False) -> RFSConfig:
        """설정 로드 (Pydantic 자동 처리 활용)"""
        if self._config is not None and (not force_reload):
            return self._config
        if PYDANTIC_AVAILABLE:
            match (self.config_path, self.env_file):
                case [str() as config_path, str() as env_file] if Path(
                    config_path
                ).exists():
                    config_data = self._load_from_file(config_path)
                    self._config = RFSConfig(**config_data)
                case [None, str() as env_file]:
                    self._config = RFSConfig()
                case _:
                    self._config = RFSConfig()
        else:
            config_dict = {}
            if self.config_path and Path(self.config_path).exists():
                config_dict = self._load_from_file(self.config_path)
            env_config = self._load_from_env()
            config_dict = {**config_dict, **env_config}
            self._config = self._create_config(config_dict)
        return self._config

    def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """파일에서 설정 로드 (JSON만 지원)"""
        path = Path(file_path)
        if path.suffix.lower() == ".json":
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        else:
            raise ValueError(
                f"Unsupported config file format: {path.suffix}. Only JSON is supported."
            )

    def _load_from_env(self) -> Dict[str, Any]:
        """환경 변수에서 설정 로드"""
        config: Dict[str, Any] = {}
        for key, value in os.environ.items():
            if key.startswith(self._env_prefix):
                config_key = key[len(self._env_prefix) :].lower()
                config = {
                    **config,
                    config_key: {config_key: self._convert_env_value(value)},
                }
        return config

    def _convert_env_value(self, value: str) -> str | int | float | bool:
        """환경 변수 값 변환 (match/case 사용)"""
        match value.lower():
            case "true" | "1" | "yes" | "on":
                return True
            case "false" | "0" | "no" | "off":
                return False
        try:
            match "." in value:
                case True:
                    return float(value)
                case False:
                    return int(value)
        except ValueError:
            pass
        return value

    def _create_config(self, config_dict: Dict[str, Any]) -> RFSConfig:
        """설정 딕셔너리를 RFSConfig로 변환"""
        # Pydantic BaseSettings는 환경 변수를 우선적으로 사용하므로
        # 딕셔너리를 직접 전달하는 대신 기본값으로 생성
        return RFSConfig()

    def get_config(self) -> RFSConfig:
        """설정 조회 (load_config의 별칭)"""
        return self.load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """설정 값 조회"""
        config = self.load_config()
        return getattr(config, key, default)

    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.load_config().is_development()

    def is_production(self) -> bool:
        """운영 환경 여부"""
        return self.load_config().is_production()

    def is_test(self) -> bool:
        """테스트 환경 여부"""
        return self.load_config().is_test()

    def reload(self) -> RFSConfig:
        """설정 재로드"""
        return self.load_config(force_reload=True)

    def set_config(self, config: RFSConfig) -> None:
        """설정 직접 설정"""
        self._config = config

    def update_config(self, **kwargs) -> None:
        """설정 부분 업데이트"""
        current_config = self.get_config()
        # Create new config with updated values
        current_dict = (
            current_config.model_dump()
            if hasattr(current_config, "model_dump")
            else vars(current_config)
        )
        updated_dict = {**current_dict, **kwargs}
        if PYDANTIC_AVAILABLE:
            self._config = RFSConfig(**updated_dict)
        else:
            # For non-Pydantic case, update attributes directly
            for key, value in kwargs.items():
                if hasattr(current_config, key):
                    setattr(current_config, key, value)

    def get_value(self, key: str, default: Any = None) -> Any:
        """특정 설정값 조회"""
        config = self.get_config()
        return getattr(config, key, default)

    def has_value(self, key: str) -> bool:
        """설정값 존재 확인"""
        config = self.get_config()
        return hasattr(config, key)

    def export_config(self, format: str = "dict") -> Dict[str, Any] | str:
        """설정 내보내기"""
        config = self.get_config()
        if hasattr(config, "model_dump"):
            config_dict = config.model_dump()
        elif hasattr(config, "to_dict"):
            config_dict = config.to_dict()
        else:
            config_dict = vars(config)

        if format == "json":
            import json

            return json.dumps(config_dict, indent=2)
        return config_dict

    def import_config(self, config_data: Dict[str, Any]) -> None:
        """설정 가져오기"""
        if PYDANTIC_AVAILABLE:
            self._config = RFSConfig(**config_data)
        else:
            # For non-Pydantic case, create basic config and update
            self._config = RFSConfig()
            for key, value in config_data.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)

    def export_cloud_run_config(self) -> Dict[str, Any]:
        """Cloud Run 전용 설정 내보내기 (v4 신규)"""
        config = self.load_config()
        if PYDANTIC_AVAILABLE and hasattr(config, "export_cloud_run_config"):
            return config.export_cloud_run_config()
        else:
            return {
                "env_vars": {
                    "RFS_ENVIRONMENT": config.environment.value,
                    "RFS_DEFAULT_BUFFER_SIZE": str(config.default_buffer_size),
                    "RFS_MAX_CONCURRENCY": str(config.max_concurrency),
                }
            }

    def validate_config(self) -> tuple[bool, list[str]]:
        """설정 유효성 검증 (v4 신규)"""
        try:
            config = self.load_config()
            return (True, [])
        except Exception as e:
            return (False, [str(e)])

    def reload_config(self) -> RFSConfig:
        """설정 강제 재로드"""
        return self.load_config(force_reload=True)


config_manager = ConfigManager()


def get_config() -> RFSConfig:
    """현재 설정 조회"""
    return config_manager.load_config()


def get(key: str, default: Any = None) -> Any:
    """설정 값 조회"""
    return config_manager.get(key, default)


def reload_config() -> RFSConfig:
    """설정 강제 재로드"""
    return config_manager.reload_config()


def is_cloud_run_environment() -> bool:
    """Cloud Run 환경 여부 확인 (v4 신규)"""
    return os.environ.get("K_SERVICE") is not None


def export_cloud_run_yaml() -> str:
    """Cloud Run service.yaml 생성 (v4 신규)"""
    config = get_config()
    cloud_config = config_manager.export_cloud_run_config()
    scaling = cloud_config.get('scaling', {})
    resource_limits = cloud_config.get('resource_limits', {})
    yaml_content = f'\napiVersion: serving.knative.dev/v1\nkind: Service\nmetadata:\n  name: rfs-service\n  annotations:\n    run.googleapis.com/ingress: all\nspec:\n  template:\n    metadata:\n      annotations:\n        autoscaling.knative.dev/maxScale: "{scaling.get('max_instances', 100)}"\n        run.googleapis.com/cpu-throttling: "false"\n        run.googleapis.com/execution-environment: gen2\n    spec:\n      containerConcurrency: {config.max_concurrency}\n      timeoutSeconds: 300\n      containers:\n      - image: gcr.io/PROJECT_ID/rfs-service:latest\n        resources:\n          limits:\n            cpu: "{resource_limits.get('cpu', '1000m')}"\n            memory: "{resource_limits.get('memory', '2Gi')}"\n        env:\n'
    env_vars = cloud_config.get("env_vars", {})
    for key, value in env_vars.items():
        yaml_content = (
            yaml_content + f'        - name: {key}\n          value: "{value}"\n'
        )
    return yaml_content.strip()


def validate_environment() -> tuple[bool, list[str]]:
    """환경 설정 유효성 검증 (v4 신규)"""
    errors: list[str] = []
    config = get_config()
    required_vars: list[str] = []
    if config.environment == Environment.PRODUCTION:
        required_vars = required_vars + ["REDIS_URL", "GOOGLE_APPLICATION_CREDENTIALS"]
    for var in required_vars:
        if not os.environ.get(var):
            errors = errors + [f"Required environment variable missing: {var}"]
    if is_cloud_run_environment():
        try:
            memory_limit = getattr(config, "cloud_run_memory_limit", "512Mi")
            memory_val = int(memory_limit.replace("Mi", "").replace("Gi", ""))
            if memory_limit.endswith("Mi") and memory_val < 256:
                errors = errors + ["Cloud Run memory limit should be at least 256Mi"]
        except (ValueError, AttributeError):
            errors = errors + ["Invalid memory limit format"]
    return (len(errors) == 0, errors)


def check_pydantic_compatibility() -> Dict[str, Any]:
    """Pydantic v2 호환성 검사 (v4 신규)"""
    return {
        "pydantic_available": PYDANTIC_AVAILABLE,
        "pydantic_version": (
            getattr(__import__("pydantic", fromlist=["VERSION"]), "VERSION", "unknown")
            if PYDANTIC_AVAILABLE
            else None
        ),
        "settings_available": "pydantic_settings" in globals(),
        "fallback_mode": not PYDANTIC_AVAILABLE,
    }
