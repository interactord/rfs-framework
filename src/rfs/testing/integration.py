"""
RFS Testing Framework - Integration Testing Module
통합 테스트 지원 모듈
"""

import asyncio
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.result import Failure, Result, Success


@dataclass
class TestEnvironment:
    """테스트 환경 설정"""

    name = "test"
    config: Dict[str, Any] = field(default_factory=dict)
    services: Dict[str, Any] = field(default_factory=dict)
    temp_dir = None

    def setup(self) -> Result[None, str]:
        """환경 설정"""
        try:
            # 임시 디렉토리 생성
            if self.temp_dir is None:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="rfs_test_"))

            # 서비스 시작
            for service_name, service in self.services.items():
                if hasattr(service, "start"):
                    service.start()

            return Success(None)
        except Exception as e:
            return Failure(f"Failed to setup environment: {str(e)}")

    def teardown(self) -> Result[None, str]:
        """환경 정리"""
        try:
            # 서비스 중지
            for service_name, service in self.services.items():
                if hasattr(service, "stop"):
                    service.stop()

            # 임시 디렉토리 삭제
            if self.temp_dir and self.temp_dir.exists():
                import shutil

                shutil.rmtree(self.temp_dir)

            return Success(None)
        except Exception as e:
            return Failure(f"Failed to teardown environment: {str(e)}")


class IntegrationTest(ABC):
    """통합 테스트 베이스 클래스"""

    def __init__(self, environment=None):
        """초기화"""
        self.environment = environment or TestEnvironment()
        self.is_setup = False

    def setup(self) -> Result[None, str]:
        """테스트 셋업"""
        if self.is_setup:
            return Success(None)

        result = self.environment.setup()
        if isinstance(result, Success):
            self.is_setup = True
            return self.setup_test()
        return result

    def teardown(self) -> Result[None, str]:
        """테스트 티어다운"""
        if not self.is_setup:
            return Success(None)

        teardown_result = self.teardown_test()
        env_result = self.environment.teardown()

        self.is_setup = False

        if isinstance(teardown_result, Failure):
            return teardown_result
        return env_result

    @abstractmethod
    def setup_test(self) -> Result[None, str]:
        """테스트별 셋업"""
        pass

    @abstractmethod
    def teardown_test(self) -> Result[None, str]:
        """테스트별 티어다운"""
        pass


class DatabaseIntegrationTest(IntegrationTest):
    """데이터베이스 통합 테스트"""

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        """초기화"""
        super().__init__()
        self.db_config = db_config or {"driver": "sqlite", "database": ":memory:"}
        self.database = None

    def setup_test(self) -> Result[None, str]:
        """데이터베이스 셋업"""
        try:
            from ..database.base import Database

            self.database = Database(self.db_config)
            self.database.connect()
            self.database.create_tables()

            return Success(None)
        except Exception as e:
            return Failure(f"Database setup failed: {str(e)}")

    def teardown_test(self) -> Result[None, str]:
        """데이터베이스 티어다운"""
        try:
            if self.database:
                self.database.drop_tables()
                self.database.disconnect()

            return Success(None)
        except Exception as e:
            return Failure(f"Database teardown failed: {str(e)}")


class WebIntegrationTest(IntegrationTest):
    """웹 통합 테스트"""

    def __init__(self, base_url="http://localhost:8000"):
        """초기화"""
        super().__init__()
        self.base_url = base_url
        self.client = None

    def setup_test(self) -> Result[None, str]:
        """웹 클라이언트 셋업"""
        try:
            import httpx

            self.client = httpx.AsyncClient(base_url=self.base_url)
            return Success(None)
        except Exception as e:
            return Failure(f"Web client setup failed: {str(e)}")

    def teardown_test(self) -> Result[None, str]:
        """웹 클라이언트 티어다운"""
        try:
            if self.client:
                asyncio.run(self.client.aclose())
            return Success(None)
        except Exception as e:
            return Failure(f"Web client teardown failed: {str(e)}")


class MessageIntegrationTest(IntegrationTest):
    """메시지 브로커 통합 테스트"""

    def __init__(self, broker_config: Optional[Dict[str, Any]] = None):
        """초기화"""
        super().__init__()
        self.broker_config = broker_config or {"type": "memory"}
        self.broker = None

    def setup_test(self) -> Result[None, str]:
        """메시지 브로커 셋업"""
        try:
            from ..messaging.broker import MessageBroker

            self.broker = MessageBroker(self.broker_config)
            self.broker.connect()

            return Success(None)
        except Exception as e:
            return Failure(f"Message broker setup failed: {str(e)}")

    def teardown_test(self) -> Result[None, str]:
        """메시지 브로커 티어다운"""
        try:
            if self.broker:
                self.broker.disconnect()

            return Success(None)
        except Exception as e:
            return Failure(f"Message broker teardown failed: {str(e)}")


@dataclass
class TestDataFactory:
    """테스트 데이터 팩토리"""

    templates: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def register_template(self, name: str, template: Dict[str, Any]) -> None:
        """템플릿 등록"""
        self.templates[name] = template

    def create(self, template_name: str, **overrides) -> Dict[str, Any]:
        """데이터 생성"""
        if template_name not in self.templates:
            return {}

        data = self.templates[template_name].copy()
        data.update(overrides)
        return data

    def create_many(
        self, template_name: str, count: int, **overrides
    ) -> List[Dict[str, Any]]:
        """여러 데이터 생성"""
        return [
            self.create(template_name, id=i, **overrides) for i in range(1, count + 1)
        ]


# 글로벌 테스트 환경
_test_environment = None


def setup_test_environment(
    config: Optional[Dict[str, Any]] = None,
) -> Result[TestEnvironment, str]:
    """테스트 환경 설정"""
    global _test_environment

    if _test_environment is None:
        _test_environment = TestEnvironment(config=config or {})

    result = _test_environment.setup()
    if isinstance(result, Success):
        return Success(_test_environment)
    return result


def cleanup_test_environment() -> Result[None, str]:
    """테스트 환경 정리"""
    global _test_environment

    if _test_environment is None:
        return Success(None)

    result = _test_environment.teardown()
    _test_environment = None
    return result


def create_test_data(
    factory: TestDataFactory, template: str, **kwargs
) -> Dict[str, Any]:
    """테스트 데이터 생성"""
    return factory.create(template, **kwargs)


def cleanup_test_data(data: Any) -> Result[None, str]:
    """테스트 데이터 정리"""
    try:
        # 데이터 타입에 따른 정리
        if hasattr(data, "delete"):
            data.delete()
        elif isinstance(data, list):
            for item in data:
                if hasattr(item, "delete"):
                    item.delete()

        return Success(None)
    except Exception as e:
        return Failure(f"Failed to cleanup test data: {str(e)}")


__all__ = [
    "TestEnvironment",
    "IntegrationTest",
    "DatabaseIntegrationTest",
    "WebIntegrationTest",
    "MessageIntegrationTest",
    "TestDataFactory",
    "setup_test_environment",
    "cleanup_test_environment",
    "create_test_data",
    "cleanup_test_data",
]
