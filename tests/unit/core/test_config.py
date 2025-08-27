"""
Configuration Management Tests
설정 관리 모듈 테스트
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from rfs.core.config import (
    PYDANTIC_AVAILABLE,
    ConfigManager,
    Environment,
    RFSConfig,
    get_config,
    reload_config,
)

if PYDANTIC_AVAILABLE:
    from pydantic import BaseModel
    try:
        from pydantic_settings import BaseSettings
    except ImportError:
        from pydantic import BaseSettings
else:
    # Pydantic이 없을 때 config 모듈의 대체 클래스 사용
    import rfs.core.config as config_module
    BaseModel = config_module.BaseModel
    BaseSettings = config_module.BaseSettings


class TestEnvironmentEnum:
    """Environment 열거형 테스트"""

    def test_environment_values(self):
        """Environment 값 확인"""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TEST.value == "test"
        assert Environment.PRODUCTION.value == "production"

    def test_environment_from_string(self):
        """문자열에서 Environment 변환"""
        assert Environment("development") == Environment.DEVELOPMENT
        assert Environment("test") == Environment.TEST
        assert Environment("production") == Environment.PRODUCTION

    def test_environment_invalid_value(self):
        """잘못된 Environment 값"""
        with pytest.raises(ValueError):
            Environment("invalid")


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestRFSConfig:
    """RFSConfig 설정 클래스 테스트"""

    def test_default_config(self):
        """기본 설정값 테스트"""
        config = RFSConfig()

        assert config.environment == Environment.DEVELOPMENT
        assert config.default_buffer_size == 100
        assert config.max_concurrency == 10
        assert config.enable_cold_start_optimization is True
        assert config.cloud_run_max_instances == 100
        assert config.cloud_run_cpu_limit == "1000m"
        assert config.cloud_run_memory_limit == "512Mi"
        assert config.cloud_tasks_queue_name == "default-queue"
        assert config.redis_url == "redis://localhost:6379"
        assert config.event_store_enabled is True
        assert config.log_level == "INFO"
        assert config.log_format == "json"
        assert config.enable_tracing is False
        assert config.api_key_header == "X-API-Key"
        assert config.enable_performance_monitoring is False
        assert config.metrics_export_interval == 60

    def test_config_from_env_vars(self):
        """환경 변수에서 설정 로드 테스트"""
        env_vars = {
            "RFS_ENVIRONMENT": "production",
            "RFS_DEFAULT_BUFFER_SIZE": "200",
            "RFS_MAX_CONCURRENCY": "20",
            "RFS_LOG_LEVEL": "DEBUG",
            "RFS_REDIS_URL": "redis://prod-redis:6379",
        }

        with patch.dict(os.environ, env_vars):
            config = RFSConfig()

            assert config.environment == Environment.PRODUCTION
            assert config.default_buffer_size == 200
            assert config.max_concurrency == 20
            assert config.log_level == "DEBUG"
            assert config.redis_url == "redis://prod-redis:6379"

    def test_config_from_env_file(self):
        """환경 파일(.env)에서 설정 로드 테스트"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("RFS_ENVIRONMENT=test\n")
            f.write("RFS_DEFAULT_BUFFER_SIZE=150\n")
            f.write("RFS_ENABLE_TRACING=true\n")
            env_file = f.name

        try:
            config = RFSConfig(_env_file=env_file)

            assert config.environment == Environment.TEST
            assert config.default_buffer_size == 150
            assert config.enable_tracing is True
        finally:
            os.unlink(env_file)

    def test_config_validation(self):
        """설정값 검증 테스트"""
        # 유효한 범위 테스트
        config = RFSConfig(default_buffer_size=5000)
        assert config.default_buffer_size == 5000

        # 범위 초과 테스트
        with pytest.raises(ValueError):
            RFSConfig(default_buffer_size=20000)  # max is 10000

        with pytest.raises(ValueError):
            RFSConfig(max_concurrency=0)  # min is 1

        # 패턴 검증 테스트
        with pytest.raises(ValueError):
            RFSConfig(log_level="INVALID")

        with pytest.raises(ValueError):
            RFSConfig(log_format="xml")  # only json or text

    def test_custom_fields(self):
        """커스텀 필드 테스트"""
        custom_data = {
            "api_version": "v2",
            "feature_flags": {"new_feature": True, "beta_feature": False},
        }

        config = RFSConfig(custom=custom_data)
        assert config.custom == custom_data
        assert config.custom["api_version"] == "v2"
        assert config.custom["feature_flags"]["new_feature"] is True

    def test_environment_validator(self):
        """Environment 검증자 테스트"""
        # 문자열로 환경 설정
        config = RFSConfig(environment="production")
        assert config.environment == Environment.PRODUCTION

        # Enum으로 환경 설정
        config = RFSConfig(environment=Environment.TEST)
        assert config.environment == Environment.TEST

        # 잘못된 환경값
        with pytest.raises(ValueError):
            RFSConfig(environment="staging")

    def test_is_production(self):
        """프로덕션 환경 확인 메서드 테스트"""
        dev_config = RFSConfig(environment=Environment.DEVELOPMENT)
        assert dev_config.is_production() is False

        prod_config = RFSConfig(environment=Environment.PRODUCTION)
        assert prod_config.is_production() is True

    def test_is_development(self):
        """개발 환경 확인 메서드 테스트"""
        dev_config = RFSConfig(environment=Environment.DEVELOPMENT)
        assert dev_config.is_development() is True

        test_config = RFSConfig(environment=Environment.TEST)
        assert test_config.is_development() is False

    def test_is_test(self):
        """테스트 환경 확인 메서드 테스트"""
        test_config = RFSConfig(environment=Environment.TEST)
        assert test_config.is_test() is True

        dev_config = RFSConfig(environment=Environment.DEVELOPMENT)
        assert dev_config.is_test() is False

    def test_model_dump(self):
        """설정을 딕셔너리로 변환 테스트"""
        config = RFSConfig(
            environment=Environment.PRODUCTION,
            default_buffer_size=200,
            enable_tracing=True,
        )

        config_dict = config.model_dump()

        assert isinstance(config_dict, dict)
        assert config_dict["environment"] == Environment.PRODUCTION
        assert config_dict["default_buffer_size"] == 200
        assert config_dict["enable_tracing"] is True

    def test_model_dump_json(self):
        """설정을 JSON으로 변환 테스트"""
        config = RFSConfig(environment=Environment.TEST, max_concurrency=15)

        config_json = config.model_dump_json()

        assert isinstance(config_json, str)
        parsed = json.loads(config_json)
        assert parsed["environment"] == "test"
        assert parsed["max_concurrency"] == 15


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestConfigManager:
    """ConfigManager 클래스 테스트"""

    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        manager1 = ConfigManager()
        manager2 = ConfigManager()

        assert manager1 is manager2

    def test_get_config(self):
        """설정 조회 테스트"""
        manager = ConfigManager()
        config = manager.get_config()

        assert isinstance(config, RFSConfig)
        assert config.environment in [
            Environment.DEVELOPMENT,
            Environment.TEST,
            Environment.PRODUCTION,
        ]

    def test_reload_config(self):
        """설정 재로드 테스트"""
        manager = ConfigManager()

        # 초기 설정
        original_config = manager.get_config()
        original_buffer_size = original_config.default_buffer_size

        # 환경 변수 변경
        with patch.dict(os.environ, {"RFS_DEFAULT_BUFFER_SIZE": "300"}):
            # 재로드
            manager.reload()
            new_config = manager.get_config()

            assert new_config.default_buffer_size == 300
            assert new_config.default_buffer_size != original_buffer_size

    def test_set_config(self):
        """설정 직접 설정 테스트"""
        manager = ConfigManager()

        # 새 설정 생성
        new_config = RFSConfig(environment=Environment.PRODUCTION, max_concurrency=50)

        # 설정 적용
        manager.set_config(new_config)

        # 확인
        current_config = manager.get_config()
        assert current_config.environment == Environment.PRODUCTION
        assert current_config.max_concurrency == 50

    def test_update_config(self):
        """설정 부분 업데이트 테스트"""
        manager = ConfigManager()

        # 초기 설정
        original_config = manager.get_config()
        original_env = original_config.environment

        # 부분 업데이트
        manager.update_config(default_buffer_size=250, enable_tracing=True)

        # 확인
        updated_config = manager.get_config()
        assert updated_config.default_buffer_size == 250
        assert updated_config.enable_tracing is True
        assert updated_config.environment == original_env  # 변경되지 않은 값 유지

    def test_get_value(self):
        """특정 설정값 조회 테스트"""
        manager = ConfigManager()

        buffer_size = manager.get_value("default_buffer_size")
        assert isinstance(buffer_size, int)
        assert 1 <= buffer_size <= 10000

        log_level = manager.get_value("log_level")
        assert log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_get_value_with_default(self):
        """기본값과 함께 설정값 조회 테스트"""
        manager = ConfigManager()

        # 존재하는 키
        buffer_size = manager.get_value("default_buffer_size", default=999)
        assert buffer_size != 999  # 실제 값 반환

        # 존재하지 않는 키
        unknown = manager.get_value("unknown_key", default="default_value")
        assert unknown == "default_value"

    def test_has_value(self):
        """설정값 존재 확인 테스트"""
        manager = ConfigManager()

        assert manager.has_value("environment") is True
        assert manager.has_value("default_buffer_size") is True
        assert manager.has_value("non_existent_key") is False

    def test_export_config(self):
        """설정 내보내기 테스트"""
        manager = ConfigManager()

        # 딕셔너리로 내보내기
        config_dict = manager.export_config()
        assert isinstance(config_dict, dict)
        assert "environment" in config_dict
        assert "default_buffer_size" in config_dict

        # JSON으로 내보내기
        config_json = manager.export_config(format="json")
        assert isinstance(config_json, str)
        parsed = json.loads(config_json)
        assert "environment" in parsed

    def test_import_config(self):
        """설정 가져오기 테스트"""
        manager = ConfigManager()

        # 설정 데이터 준비
        config_data = {
            "environment": "production",
            "default_buffer_size": 350,
            "max_concurrency": 25,
            "enable_tracing": True,
        }

        # 가져오기
        manager.import_config(config_data)

        # 확인
        config = manager.get_config()
        assert config.environment == Environment.PRODUCTION
        assert config.default_buffer_size == 350
        assert config.max_concurrency == 25
        assert config.enable_tracing is True


class TestGlobalFunctions:
    """전역 함수 테스트"""

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_get_config(self):
        """get_config 전역 함수 테스트"""
        config = get_config()

        assert isinstance(config, RFSConfig)
        assert hasattr(config, "environment")
        assert hasattr(config, "default_buffer_size")

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_reload_config(self):
        """reload_config 전역 함수 테스트"""
        # 초기 설정
        original_config = get_config()
        original_buffer_size = original_config.default_buffer_size

        # 환경 변수 변경
        with patch.dict(os.environ, {"RFS_DEFAULT_BUFFER_SIZE": "400"}):
            # 재로드
            reload_config()
            new_config = get_config()

            assert new_config.default_buffer_size == 400


class TestEdgeCasesAndErrors:
    """엣지 케이스와 에러 테스트"""

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_invalid_config_values(self):
        """잘못된 설정값 테스트"""
        # 범위 초과
        with pytest.raises(ValueError):
            RFSConfig(default_buffer_size=-1)

        with pytest.raises(ValueError):
            RFSConfig(max_concurrency=10001)

        # 잘못된 패턴
        with pytest.raises(ValueError):
            RFSConfig(log_format="yaml")

        # 빈 문자열
        with pytest.raises(ValueError):
            RFSConfig(cloud_tasks_queue_name="")

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_config_immutability(self):
        """설정 불변성 테스트"""
        config = RFSConfig()

        # Pydantic 모델은 기본적으로 변경 가능
        config.default_buffer_size = 200
        assert config.default_buffer_size == 200

        # 하지만 검증은 여전히 수행됨
        with pytest.raises(ValueError):
            config.default_buffer_size = -1

    @pytest.mark.skipif(PYDANTIC_AVAILABLE, reason="Testing without Pydantic")
    def test_without_pydantic(self):
        """Pydantic 없이 실행 테스트"""
        # Pydantic이 없을 때도 기본 동작 확인
        assert not PYDANTIC_AVAILABLE

        # 기본 클래스들이 정의되어 있어야 함
        assert BaseModel is not None
        assert BaseSettings is not None


class TestCloudRunSpecificConfig:
    """Cloud Run 관련 설정 테스트"""

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_cloud_run_config(self):
        """Cloud Run 설정 테스트"""
        config = RFSConfig(
            enable_cold_start_optimization=True,
            cloud_run_max_instances=500,
            cloud_run_cpu_limit="2000m",
            cloud_run_memory_limit="1Gi",
        )

        assert config.enable_cold_start_optimization is True
        assert config.cloud_run_max_instances == 500
        assert config.cloud_run_cpu_limit == "2000m"
        assert config.cloud_run_memory_limit == "1Gi"

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_cloud_run_production_settings(self):
        """프로덕션 Cloud Run 설정 테스트"""
        config = RFSConfig(
            environment=Environment.PRODUCTION,
            cloud_run_max_instances=1000,
            cloud_run_cpu_limit="4000m",
            cloud_run_memory_limit="4Gi",
            enable_performance_monitoring=True,
        )

        assert config.is_production() is True
        assert config.cloud_run_max_instances == 1000
        assert config.enable_performance_monitoring is True


class TestMonitoringConfig:
    """모니터링 관련 설정 테스트"""

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_monitoring_config(self):
        """모니터링 설정 테스트"""
        config = RFSConfig(
            enable_tracing=True,
            enable_performance_monitoring=True,
            metrics_export_interval=30,
        )

        assert config.enable_tracing is True
        assert config.enable_performance_monitoring is True
        assert config.metrics_export_interval == 30

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
    def test_logging_config(self):
        """로깅 설정 테스트"""
        config = RFSConfig(log_level="DEBUG", log_format="text")

        assert config.log_level == "DEBUG"
        assert config.log_format == "text"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
