"""
Dependency Injection Annotations Tests
의존성 주입 어노테이션 테스트
"""

from typing import Any, Optional

import pytest

from rfs.core.annotations.base import (
    AnnotationType,
    ServiceScope,
    get_annotation_metadata,
)
from rfs.core.annotations.di import (
    Adapter,
    Autowired,
    Component,
    ConfigProperty,
    Controller,
    Injectable,
    Lazy,
    Port,
    Primary,
    Qualifier,
    Repository,
    Scope,
    Service,
    UseCase,
    Value,
)


class TestComponentDecorator:
    """@Component 데코레이터 테스트"""

    def test_component_basic(self):
        """기본 Component 데코레이터 테스트"""

        @Component(name="test_component")
        class TestComponent:
            pass

        metadata = get_annotation_metadata(TestComponent)
        assert metadata is not None
        assert metadata.name == "test_component"
        assert metadata.annotation_type == AnnotationType.COMPONENT
        assert metadata.scope == ServiceScope.SINGLETON  # 기본값

    def test_component_with_scope(self):
        """스코프 지정된 Component 테스트"""

        @Component(name="scoped_component", scope=ServiceScope.PROTOTYPE)
        class ScopedComponent:
            pass

        metadata = get_annotation_metadata(ScopedComponent)
        assert metadata.scope == ServiceScope.PROTOTYPE

    def test_component_with_dependencies(self):
        """의존성이 있는 Component 테스트"""

        @Component(name="dependent", dependencies=["service1", "service2"])
        class DependentComponent:
            pass

        metadata = get_annotation_metadata(DependentComponent)
        assert metadata.dependencies == ["service1", "service2"]

    def test_component_with_lazy(self):
        """Lazy 로딩 Component 테스트"""

        @Component(name="lazy_component", lazy=True)
        class LazyComponent:
            pass

        metadata = get_annotation_metadata(LazyComponent)
        assert metadata.lazy is True

    def test_component_with_profile(self):
        """프로파일 지정 Component 테스트"""

        @Component(name="profile_component", profile="production")
        class ProfileComponent:
            pass

        metadata = get_annotation_metadata(ProfileComponent)
        assert metadata.profile == "production"


class TestPortDecorator:
    """@Port 데코레이터 테스트"""

    def test_port_basic(self):
        """기본 Port 데코레이터 테스트"""

        @Port(name="user_port")
        class UserPort:
            def get_user(self, user_id: str):
                pass

        metadata = get_annotation_metadata(UserPort)
        assert metadata is not None
        assert metadata.name == "user_port"
        assert metadata.annotation_type == AnnotationType.PORT

    def test_port_with_dependencies(self):
        """의존성이 있는 Port 테스트"""

        @Port(name="payment_port", dependencies=["transaction_manager"])
        class PaymentPort:
            pass

        metadata = get_annotation_metadata(PaymentPort)
        assert metadata.dependencies == ["transaction_manager"]


class TestAdapterDecorator:
    """@Adapter 데코레이터 테스트"""

    def test_adapter_basic(self):
        """기본 Adapter 데코레이터 테스트"""

        @Adapter(port="user_port", name="user_adapter")
        class UserAdapter:
            pass

        metadata = get_annotation_metadata(UserAdapter)
        assert metadata is not None
        assert metadata.name == "user_adapter"
        assert metadata.annotation_type == AnnotationType.ADAPTER
        assert metadata.port_name == "user_port"

    def test_adapter_with_profile(self):
        """프로파일별 Adapter 테스트"""

        @Adapter(port="db_port", name="mysql_adapter", profile="mysql")
        class MySQLAdapter:
            pass

        @Adapter(port="db_port", name="postgres_adapter", profile="postgres")
        class PostgresAdapter:
            pass

        mysql_metadata = get_annotation_metadata(MySQLAdapter)
        postgres_metadata = get_annotation_metadata(PostgresAdapter)

        assert mysql_metadata.profile == "mysql"
        assert postgres_metadata.profile == "postgres"
        assert mysql_metadata.port_name == postgres_metadata.port_name == "db_port"


class TestUseCaseDecorator:
    """@UseCase 데코레이터 테스트"""

    def test_use_case_basic(self):
        """기본 UseCase 데코레이터 테스트"""

        @UseCase(name="create_user")
        class CreateUserUseCase:
            def execute(self, data: dict):
                pass

        metadata = get_annotation_metadata(CreateUserUseCase)
        assert metadata is not None
        assert metadata.name == "create_user"
        assert metadata.annotation_type == AnnotationType.USE_CASE
        assert metadata.scope == ServiceScope.PROTOTYPE  # UseCase 기본 스코프

    def test_use_case_with_dependencies(self):
        """포트 의존성이 있는 UseCase 테스트"""

        @UseCase(
            name="transfer_money", dependencies=["account_port", "transaction_port"]
        )
        class TransferMoneyUseCase:
            pass

        metadata = get_annotation_metadata(TransferMoneyUseCase)
        assert metadata.dependencies == ["account_port", "transaction_port"]


class TestControllerDecorator:
    """@Controller 데코레이터 테스트"""

    def test_controller_basic(self):
        """기본 Controller 데코레이터 테스트"""

        @Controller(name="user_controller")
        class UserController:
            pass

        metadata = get_annotation_metadata(UserController)
        assert metadata is not None
        assert metadata.name == "user_controller"
        assert metadata.annotation_type == AnnotationType.CONTROLLER
        assert metadata.scope == ServiceScope.REQUEST  # Controller 기본 스코프

    def test_controller_with_use_cases(self):
        """UseCase 의존성이 있는 Controller 테스트"""

        @Controller(
            name="order_controller", dependencies=["create_order", "cancel_order"]
        )
        class OrderController:
            pass

        metadata = get_annotation_metadata(OrderController)
        assert metadata.dependencies == ["create_order", "cancel_order"]


class TestServiceDecorator:
    """@Service 데코레이터 테스트"""

    def test_service_basic(self):
        """기본 Service 데코레이터 테스트"""

        @Service(name="email_service")
        class EmailService:
            def send_email(self, to: str, subject: str, body: str):
                pass

        metadata = get_annotation_metadata(EmailService)
        assert metadata is not None
        assert metadata.name == "email_service"
        assert metadata.annotation_type == AnnotationType.SERVICE
        assert metadata.scope == ServiceScope.SINGLETON

    def test_service_with_scope(self):
        """스코프 지정 Service 테스트"""

        @Service(name="session_service", scope=ServiceScope.REQUEST)
        class SessionService:
            pass

        metadata = get_annotation_metadata(SessionService)
        assert metadata.scope == ServiceScope.REQUEST


class TestRepositoryDecorator:
    """@Repository 데코레이터 테스트"""

    def test_repository_basic(self):
        """기본 Repository 데코레이터 테스트"""

        @Repository(name="user_repository")
        class UserRepository:
            def find_by_id(self, user_id: str):
                pass

        metadata = get_annotation_metadata(UserRepository)
        assert metadata is not None
        assert metadata.name == "user_repository"
        assert metadata.annotation_type == AnnotationType.REPOSITORY
        assert metadata.scope == ServiceScope.SINGLETON

    def test_repository_with_dependencies(self):
        """데이터베이스 의존성이 있는 Repository 테스트"""

        @Repository(name="order_repository", dependencies=["database_connection"])
        class OrderRepository:
            pass

        metadata = get_annotation_metadata(OrderRepository)
        assert metadata.dependencies == ["database_connection"]


class TestInjectableDecorator:
    """@Injectable 데코레이터 테스트"""

    def test_injectable_basic(self):
        """기본 Injectable 데코레이터 테스트"""

        @Injectable
        class SimpleService:
            pass

        metadata = get_annotation_metadata(SimpleService)
        assert metadata is not None
        assert metadata.name == "SimpleService"  # 클래스 이름 사용
        assert metadata.annotation_type == AnnotationType.COMPONENT

    def test_injectable_with_custom_name(self):
        """커스텀 이름의 Injectable 테스트"""

        @Injectable(name="custom_service")
        class CustomService:
            pass

        metadata = get_annotation_metadata(CustomService)
        assert metadata.name == "custom_service"


class TestAutowiredDecorator:
    """@Autowired 데코레이터 테스트"""

    def test_autowired_property(self):
        """Autowired 프로퍼티 테스트"""

        class TestService:
            @Autowired("logger")
            def logger(self):
                pass

            @Autowired("database")
            def database(self):
                pass

        # Autowired는 프로퍼티/메서드 레벨 데코레이터
        # 실제 의존성 주입은 컨테이너에서 처리
        assert hasattr(TestService, "logger")
        assert hasattr(TestService, "database")

    def test_autowired_with_qualifier(self):
        """Qualifier와 함께 사용하는 Autowired 테스트"""

        class ServiceWithQualifiedDeps:
            @Autowired("cache")
            @Qualifier("redis")
            def cache(self):
                pass

        assert hasattr(ServiceWithQualifiedDeps, "cache")


class TestQualifierDecorator:
    """@Qualifier 데코레이터 테스트"""

    def test_qualifier_basic(self):
        """기본 Qualifier 테스트"""

        @Component(name="redis_cache")
        @Qualifier("redis")
        class RedisCache:
            pass

        @Component(name="memory_cache")
        @Qualifier("memory")
        class MemoryCache:
            pass

        # Qualifier는 메타데이터에 저장되어야 함
        redis_metadata = get_annotation_metadata(RedisCache)
        memory_metadata = get_annotation_metadata(MemoryCache)

        assert redis_metadata is not None
        assert memory_metadata is not None


class TestScopeDecorator:
    """@Scope 데코레이터 테스트"""

    def test_scope_override(self):
        """Scope 오버라이드 테스트"""

        @Component(name="test")
        @Scope(ServiceScope.PROTOTYPE)
        class PrototypeComponent:
            pass

        metadata = get_annotation_metadata(PrototypeComponent)
        # @Scope가 @Component의 기본 스코프를 오버라이드
        assert metadata.scope == ServiceScope.PROTOTYPE


class TestPrimaryDecorator:
    """@Primary 데코레이터 테스트"""

    def test_primary_component(self):
        """Primary 컴포넌트 테스트"""

        @Component(name="primary_service")
        @Primary
        class PrimaryService:
            pass

        @Component(name="secondary_service")
        class SecondaryService:
            pass

        # Primary는 여러 구현체 중 기본으로 선택되어야 함
        primary_metadata = get_annotation_metadata(PrimaryService)
        secondary_metadata = get_annotation_metadata(SecondaryService)

        assert primary_metadata is not None
        assert secondary_metadata is not None


class TestLazyDecorator:
    """@Lazy 데코레이터 테스트"""

    def test_lazy_initialization(self):
        """Lazy 초기화 테스트"""

        @Component(name="heavy_service")
        @Lazy
        class HeavyService:
            def __init__(self):
                # 무거운 초기화 작업
                pass

        metadata = get_annotation_metadata(HeavyService)
        assert metadata.lazy is True


class TestValueDecorator:
    """@Value 데코레이터 테스트"""

    def test_value_injection(self):
        """Value 주입 테스트"""

        @Component(name="config_service")
        class ConfigService:
            @Value("${app.name}")
            def app_name(self):
                pass

            @Value("${app.version:1.0.0}")  # 기본값 포함
            def app_version(self):
                pass

        assert hasattr(ConfigService, "app_name")
        assert hasattr(ConfigService, "app_version")


class TestConfigPropertyDecorator:
    """@ConfigProperty 데코레이터 테스트"""

    def test_config_property(self):
        """ConfigProperty 테스트"""

        @Component(name="settings")
        class Settings:
            @ConfigProperty("database.host")
            def db_host(self):
                pass

            @ConfigProperty("database.port", default=5432)
            def db_port(self):
                pass

        assert hasattr(Settings, "db_host")
        assert hasattr(Settings, "db_port")


class TestDecoratorCombinations:
    """데코레이터 조합 테스트"""

    def test_multiple_decorators(self):
        """여러 데코레이터 조합 테스트"""

        @Service(name="complex_service")
        @Scope(ServiceScope.REQUEST)
        @Primary
        @Lazy
        class ComplexService:
            @Autowired("logger")
            @Qualifier("async")
            def logger(self):
                pass

            @Value("${service.timeout:30}")
            def timeout(self):
                pass

        metadata = get_annotation_metadata(ComplexService)
        assert metadata.name == "complex_service"
        assert metadata.annotation_type == AnnotationType.SERVICE
        assert metadata.scope == ServiceScope.REQUEST
        assert metadata.lazy is True

    def test_port_adapter_combination(self):
        """Port-Adapter 패턴 테스트"""

        @Port(name="payment_port")
        class PaymentPort:
            def process_payment(self, amount: float):
                raise NotImplementedError

        @Adapter(port="payment_port", name="stripe_adapter")
        class StripeAdapter(PaymentPort):
            def process_payment(self, amount: float):
                return f"Processed ${amount} via Stripe"

        @Adapter(port="payment_port", name="paypal_adapter", profile="paypal")
        class PayPalAdapter(PaymentPort):
            def process_payment(self, amount: float):
                return f"Processed ${amount} via PayPal"

        stripe_metadata = get_annotation_metadata(StripeAdapter)
        paypal_metadata = get_annotation_metadata(PayPalAdapter)

        assert stripe_metadata.port_name == "payment_port"
        assert paypal_metadata.port_name == "payment_port"
        assert paypal_metadata.profile == "paypal"


class TestEdgeCasesAndErrors:
    """엣지 케이스와 에러 테스트"""

    def test_component_without_name(self):
        """이름 없는 Component 테스트"""
        with pytest.raises(TypeError):

            @Component()  # name은 필수 파라미터
            class NoNameComponent:
                pass

    def test_adapter_without_port(self):
        """포트 없는 Adapter 테스트"""
        with pytest.raises(TypeError):

            @Adapter(name="invalid_adapter")  # port는 필수
            class InvalidAdapter:
                pass

    def test_duplicate_annotations(self):
        """중복 어노테이션 테스트"""

        @Component(name="test1")
        @Service(name="test2")  # 둘 다 컴포넌트 타입
        class DuplicateAnnotations:
            pass

        metadata = get_annotation_metadata(DuplicateAnnotations)
        # 마지막 데코레이터가 우선
        assert metadata.annotation_type == AnnotationType.SERVICE
        assert metadata.name == "test2"

    def test_invalid_scope(self):
        """잘못된 스코프 테스트"""
        with pytest.raises(AttributeError):

            @Component(name="test", scope="invalid_scope")  # 문자열 대신 Enum 사용
            class InvalidScopeComponent:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
