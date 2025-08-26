"""
Configuration Management (RFS v4)

Pydantic v2 기반 환경 변수 및 설정 관리
"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict

try:
    from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
    from pydantic_settings import BaseSettings

    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object
    BaseSettings = object
    Field = lambda default=None, **kwargs: default
    PYDANTIC_AVAILABLE = False


class Environment(str, Enum):
    """실행 환경"""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


if PYDANTIC_AVAILABLE:

    class RFSConfig(BaseSettings):
        """RFS Framework v4 설정 (Pydantic v2 기반)"""

        model_config = ConfigDict(
            env_prefix="RFS_",
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            validate_default=True,
            extra="allow",
        )
        environment: Environment = Field(
            default=Environment.DEVELOPMENT, description="실행 환경"
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
                        return Environment.DEVELOPMENT
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

else:
    from dataclasses import dataclass, field

    @dataclass
    class RFSConfig:
        """RFS Framework 설정 (Fallback)"""

        environment: Environment = Environment.DEVELOPMENT
        default_buffer_size: int = 100
        max_concurrency: int = 10
        enable_cold_start_optimization: bool = True
        cloud_run_max_instances: int = 100
        cloud_tasks_queue_name: str = "default-queue"
        redis_url: str = "redis://localhost:6379"
        event_store_enabled: bool = True
        log_level: str = "INFO"
        log_format: str = "json"
        enable_tracing: bool = False
        api_key_header: str = "X-API-Key"
        custom: Dict[str, Any] = field(default_factory=dict)

        def is_development(self) -> bool:
            return self.environment == Environment.DEVELOPMENT

        def is_production(self) -> bool:
            return self.environment == Environment.PRODUCTION

        def is_test(self) -> bool:
            return self.environment == Environment.TEST


class ConfigManager:
    """설정 관리자 (RFS v4 현대화)"""

    def __init__(self, config_path: str | None = None, env_file: str | None = None):
        self.config_path = config_path
        self.env_file = env_file or ".env"
        self._config: RFSConfig | None = None
        self._env_prefix = "RFS_"

    def load_config(self, force_reload: bool = False) -> RFSConfig:
        """설정 로드 (Pydantic 자동 처리 활용)"""
        if self._config is not None and (not force_reload):
            return self._config
        if PYDANTIC_AVAILABLE:
            match (self.config_path, self.env_file):
                case [str() as config_path, str() as env_file] if Path(
                    config_path
                ).exists():
                    config_data = self._load_from_file(config_path)
                    self._config = RFSConfig(**config_data, _env_file=env_file)
                case [None, str() as env_file]:
                    self._config = RFSConfig(_env_file=env_file)
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
                return json.load(f)
        else:
            raise ValueError(
                f"Unsupported config file format: {path.suffix}. Only JSON is supported."
            )

    def _load_from_env(self) -> Dict[str, Any]:
        """환경 변수에서 설정 로드"""
        config = {}
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
        env_str = config_dict.get("environment", "development")
        if type(env_str).__name__ == "str":
            try:
                environment = Environment(env_str.lower())
            except ValueError:
                environment = Environment.DEVELOPMENT
        else:
            environment = env_str
        return RFSConfig(
            environment=environment,
            default_buffer_size=config_dict.get("default_buffer_size", 100),
            max_concurrency=config_dict.get("max_concurrency", 10),
            enable_cold_start_optimization=config_dict.get(
                "enable_cold_start_optimization", True
            ),
            cloud_run_max_instances=config_dict.get("cloud_run_max_instances", 100),
            cloud_tasks_queue_name=config_dict.get(
                "cloud_tasks_queue_name", "default-queue"
            ),
            redis_url=config_dict.get("redis_url", "redis://localhost:6379"),
            event_store_enabled=config_dict.get("event_store_enabled", True),
            log_level=config_dict.get("log_level", "INFO"),
            log_format=config_dict.get("log_format", "json"),
            enable_tracing=config_dict.get("enable_tracing", False),
            api_key_header=config_dict.get("api_key_header", "X-API-Key"),
            custom=config_dict.get("custom", {}),
        )

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
    yaml_content = f'\napiVersion: serving.knative.dev/v1\nkind: Service\nmetadata:\n  name: rfs-service\n  annotations:\n    run.googleapis.com/ingress: all\nspec:\n  template:\n    metadata:\n      annotations:\n        autoscaling.knative.dev/maxScale: "{cloud_config.get('scaling')['max_instances']}"\n        run.googleapis.com/cpu-throttling: "false"\n        run.googleapis.com/execution-environment: gen2\n    spec:\n      containerConcurrency: {config.max_concurrency}\n      timeoutSeconds: 300\n      containers:\n      - image: gcr.io/PROJECT_ID/rfs-service:latest\n        resources:\n          limits:\n            cpu: "{cloud_config.get('resource_limits')['cpu']}"\n            memory: "{cloud_config.get('resource_limits')['memory']}"\n        env:\n'
    for key, value in cloud_config.get("env_vars").items():
        yaml_content = (
            yaml_content + f'        - name: {key}\n          value: "{value}"\n'
        )
    return yaml_content.strip()


def validate_environment() -> tuple[bool, list[str]]:
    """환경 설정 유효성 검증 (v4 신규)"""
    errors = []
    config = get_config()
    required_vars = []
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
