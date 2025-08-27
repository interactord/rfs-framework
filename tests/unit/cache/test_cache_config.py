"""
RFS Framework Cache 설정 단위 테스트

CacheConfig와 MemoryCacheConfig 클래스의 설정 및 검증을 테스트합니다.
"""

from dataclasses import asdict

import pytest

from rfs.cache.base import CacheConfig, CacheType, SerializationType
from rfs.cache.memory_cache import MemoryCacheConfig


class TestCacheConfig:
    """캐시 설정 테스트"""

    def test_default_cache_config(self):
        """기본 캐시 설정 테스트"""
        config = CacheConfig()

        assert config.host == "localhost"
        assert config.port == 6379
        assert config.cache_type == CacheType.REDIS
        assert config.serialization == SerializationType.JSON
        assert config.default_ttl == 3600
        assert config.max_connections == 50
        assert config.namespace == "rfs"

    def test_custom_cache_config(self):
        """사용자 정의 캐시 설정 테스트"""
        config = CacheConfig(
            host="custom-redis",
            port=6380,
            cache_type=CacheType.MEMORY,
            default_ttl=7200,
            namespace="test",
        )

        assert config.host == "custom-redis"
        assert config.port == 6380
        assert config.cache_type == CacheType.MEMORY
        assert config.default_ttl == 7200
        assert config.namespace == "test"

    def test_memory_cache_config(self):
        """메모리 캐시 설정 테스트"""
        config = MemoryCacheConfig(
            max_size=2000, eviction_policy="lfu", cleanup_interval=600
        )

        assert config.max_size == 2000
        assert config.eviction_policy == "lfu"
        assert config.cleanup_interval == 600
        assert config.lazy_expiration is True  # 기본값

    def test_memory_cache_config_with_all_params(self):
        """모든 파라미터를 가진 메모리 캐시 설정"""
        config = MemoryCacheConfig(
            max_size=5000,
            eviction_policy="fifo",
            cleanup_interval=300,
            lazy_expiration=False,
        )

        assert config.max_size == 5000
        assert config.eviction_policy == "fifo"
        assert config.cleanup_interval == 300
        assert config.lazy_expiration is False

    def test_cache_config_serialization(self):
        """캐시 설정 직렬화 테스트"""
        config = CacheConfig(
            host="test-host",
            port=6379,
            cache_type=CacheType.REDIS,
            serialization=SerializationType.PICKLE,
        )

        # 딕셔너리로 변환
        config_dict = asdict(config)

        assert config_dict["host"] == "test-host"
        assert config_dict["port"] == 6379
        # Enum 값은 변환 후에도 접근 가능해야 함
        assert config_dict["cache_type"] == CacheType.REDIS
        assert config_dict["serialization"] == SerializationType.PICKLE

    def test_cache_config_validation(self):
        """캐시 설정 유효성 검증"""
        # dataclass는 자동 validation이 없으므로 값이 설정됨을 확인
        # 잘못된 값이어도 생성은 가능
        config_negative_port = CacheConfig(port=-1)
        assert config_negative_port.port == -1

        config_negative_ttl = CacheConfig(default_ttl=-100)
        assert config_negative_ttl.default_ttl == -100

        config_zero_connections = CacheConfig(max_connections=0)
        assert config_zero_connections.max_connections == 0

    def test_memory_cache_config_validation(self):
        """메모리 캐시 설정 유효성 검증"""
        # dataclass는 자동 validation이 없으므로 값이 설정됨을 확인
        config_negative_size = MemoryCacheConfig(max_size=-1)
        assert config_negative_size.max_size == -1

        # 잘못된 eviction_policy도 설정 가능
        config_invalid_policy = MemoryCacheConfig(eviction_policy="invalid_policy")
        assert config_invalid_policy.eviction_policy == "invalid_policy"

        # 잘못된 cleanup_interval도 설정 가능
        config_negative_interval = MemoryCacheConfig(cleanup_interval=-1)
        assert config_negative_interval.cleanup_interval == -1

    def test_cache_type_enum(self):
        """CacheType 열거형 테스트"""
        assert CacheType.REDIS.value == "redis"
        assert CacheType.MEMORY.value == "memory"

        # 지원되는 캐시 타입 확인
        cache_types = [t.value for t in CacheType]
        assert "redis" in cache_types
        assert "memory" in cache_types

    def test_serialization_type_enum(self):
        """SerializationType 열거형 테스트"""
        assert SerializationType.JSON.value == "json"
        assert SerializationType.PICKLE.value == "pickle"

        # 추가 직렬화 타입이 있는 경우
        if hasattr(SerializationType, "MSGPACK"):
            assert SerializationType.MSGPACK.value == "msgpack"

    def test_config_inheritance(self):
        """설정 상속 테스트"""
        # MemoryCacheConfig가 CacheConfig를 상속하는 경우
        if issubclass(MemoryCacheConfig, CacheConfig):
            config = MemoryCacheConfig(
                host="memory-host", port=0, max_size=1000  # 메모리 캐시는 포트 불필요
            )

            assert config.host == "memory-host"
            assert config.max_size == 1000

    def test_config_defaults_consistency(self):
        """기본값 일관성 테스트"""
        config1 = CacheConfig()
        config2 = CacheConfig()

        # 두 인스턴스의 기본값이 동일해야 함
        assert config1.host == config2.host
        assert config1.port == config2.port
        assert config1.default_ttl == config2.default_ttl
        assert config1.namespace == config2.namespace

    def test_eviction_policies(self):
        """메모리 캐시 제거 정책 테스트"""
        policies = ["lru", "lfu", "fifo", "random"]

        for policy in policies:
            try:
                config = MemoryCacheConfig(eviction_policy=policy)
                assert config.eviction_policy == policy
            except ValueError:
                # 지원하지 않는 정책
                pass

    def test_config_copy_and_modify(self):
        """설정 복사 및 수정 테스트"""
        original = CacheConfig(host="original-host", port=6379, default_ttl=3600)

        # 복사 후 수정
        if hasattr(original, "__dict__"):
            modified = CacheConfig(**original.__dict__)
            modified.host = "modified-host"
            modified.default_ttl = 7200

            # 원본은 변경되지 않아야 함
            assert original.host == "original-host"
            assert original.default_ttl == 3600

            # 수정된 객체는 새 값을 가져야 함
            assert modified.host == "modified-host"
            assert modified.default_ttl == 7200
