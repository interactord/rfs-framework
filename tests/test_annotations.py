"""
RFS v4 Annotation System Tests
어노테이션 기반 의존성 주입 시스템의 comprehensive test suite

테스트 범위:
- 기본 어노테이션 기능
- 헥사고날 아키텍처 패턴
- 의존성 주입 및 해결
- Port-Adapter 매칭
- 아키텍처 유효성 검증
- 성능 테스트
"""

import pytest
import asyncio
from typing import Any, List
from abc import ABC, abstractmethod
from unittest.mock import Mock, patch
import time

# RFS 코어 imports
from rfs.core.annotations import (
    Port, Adapter, Component, UseCase, Controller, Service, Repository,
    AnnotationMetadata, AnnotationType, ComponentScope,
    get_annotation_metadata, has_annotation, is_port, is_adapter,
    validate_hexagonal_architecture
)
from rfs.core.annotation_registry import (
    AnnotationRegistry, RegistrationResult, DependencyGraph,
    get_annotation_registry, register_classes
)
from rfs.core.annotation_processor import (
    AnnotationProcessor, ProcessingContext, ProcessingResult,
    auto_scan_package, auto_register_classes, auto_register
)


class TestAnnotationDecorators:
    """어노테이션 데코레이터 테스트"""
    
    def test_port_annotation(self):
        """@Port 어노테이션 테스트"""
        @Port(name="user_repository", description="User repository interface")
        class UserRepository(ABC):
            @abstractmethod
            def find_by_id(self, user_id: str) -> Any: pass
        
        assert has_annotation(UserRepository)
        assert is_port(UserRepository)
        
        metadata = get_annotation_metadata(UserRepository)
        assert metadata.annotation_type == AnnotationType.PORT
        assert metadata.name == "user_repository"
        assert metadata.description == "User repository interface"
        assert metadata.target_class == UserRepository
    
    def test_adapter_annotation(self):
        """@Adapter 어노테이션 테스트"""
        @Port(name="user_repository")
        class UserRepository(ABC):
            pass
        
        @Adapter(port="user_repository", name="postgres_adapter", 
                scope=ComponentScope.SINGLETON, profile="production")
        class PostgresUserRepository(UserRepository):
            pass
        
        assert has_annotation(PostgresUserRepository)
        assert is_adapter(PostgresUserRepository)
        
        metadata = get_annotation_metadata(PostgresUserRepository)
        assert metadata.annotation_type == AnnotationType.ADAPTER
        assert metadata.name == "postgres_adapter"
        assert metadata.port_name == "user_repository"
        assert metadata.scope == ComponentScope.SINGLETON
        assert metadata.profile == "production"
    
    def test_component_annotation(self):
        """@Component 어노테이션 테스트"""
        @Component(name="email_service", 
                  dependencies=["smtp_client"], 
                  scope=ComponentScope.PROTOTYPE,
                  lazy=True)
        class EmailService:
            pass
        
        metadata = get_annotation_metadata(EmailService)
        assert metadata.annotation_type == AnnotationType.COMPONENT
        assert metadata.name == "email_service"
        assert metadata.dependencies == ["smtp_client"]
        assert metadata.scope == ComponentScope.PROTOTYPE
        assert metadata.lazy is True
    
    def test_use_case_annotation(self):
        """@UseCase 어노테이션 테스트"""
        @UseCase(name="create_user", dependencies=["user_repository", "email_service"])
        class CreateUserUseCase:
            pass
        
        metadata = get_annotation_metadata(CreateUserUseCase)
        assert metadata.annotation_type == AnnotationType.USE_CASE
        assert metadata.name == "create_user"
        assert metadata.dependencies == ["user_repository", "email_service"]
    
    def test_controller_annotation(self):
        """@Controller 어노테이션 테스트"""
        @Controller(route="/api/users", 
                   name="user_controller",
                   dependencies=["create_user_use_case"])
        class UserController:
            pass
        
        metadata = get_annotation_metadata(UserController)
        assert metadata.annotation_type == AnnotationType.CONTROLLER
        assert metadata.name == "user_controller"
        assert metadata.route == "/api/users"
        assert metadata.dependencies == ["create_user_use_case"]
    
    def test_service_and_repository_aliases(self):
        """@Service, @Repository 별칭 테스트"""
        @Service(name="payment_service")
        class PaymentService:
            pass
        
        @Repository(name="order_repository")
        class OrderRepository:
            pass
        
        payment_metadata = get_annotation_metadata(PaymentService)
        order_metadata = get_annotation_metadata(OrderRepository)
        
        assert payment_metadata.annotation_type == AnnotationType.COMPONENT
        assert order_metadata.annotation_type == AnnotationType.COMPONENT


class TestAnnotationRegistry:
    """어노테이션 레지스트리 테스트"""
    
    def setup_method(self):
        """각 테스트 전에 실행"""
        self.registry = AnnotationRegistry(current_profile="test")
    
    def test_port_registration(self):
        """Port 등록 테스트"""
        @Port(name="test_port")
        class TestPort(ABC):
            pass
        
        result = self.registry.register_class(TestPort)
        assert result.success is True
        assert result.service_name == "test_port"
        assert result.annotation_type == AnnotationType.PORT
        
        # Port 정보 확인
        port_info = self.registry.get_port_info()
        assert "test_port" in port_info
        assert port_info["test_port"]["class"] == "TestPort"
    
    def test_adapter_registration(self):
        """Adapter 등록 테스트"""
        @Port(name="test_port")
        class TestPort(ABC):
            pass
        
        @Adapter(port="test_port", name="test_adapter")
        class TestAdapter(TestPort):
            pass
        
        # Port 먼저 등록
        self.registry.register_class(TestPort)
        
        # Adapter 등록
        result = self.registry.register_class(TestAdapter)
        assert result.success is True
        
        # Port로 Adapter 조회
        adapter_instance = self.registry.get_by_port("test_port")
        assert adapter_instance is not None
        assert isinstance(adapter_instance, TestAdapter)
    
    def test_component_registration_with_dependencies(self):
        """의존성이 있는 컴포넌트 등록 테스트"""
        @Component(name="dependency")
        class Dependency:
            pass
        
        @Component(name="main_component", dependencies=["dependency"])
        class MainComponent:
            def __init__(self, dependency: Dependency):
                self.dependency = dependency
        
        # 의존성 먼저 등록
        self.registry.register_class(Dependency)
        
        # 메인 컴포넌트 등록
        result = self.registry.register_class(MainComponent)
        assert result.success is True
        
        # 인스턴스 조회 및 의존성 주입 확인
        instance = self.registry.get("main_component")
        assert instance is not None
        assert hasattr(instance, 'dependency')
    
    def test_profile_filtering(self):
        """프로파일 기반 필터링 테스트"""
        @Component(name="dev_component", profile="development")
        class DevComponent:
            pass
        
        @Component(name="prod_component", profile="production")  
        class ProdComponent:
            pass
        
        # test 프로파일 레지스트리에서 등록
        dev_result = self.registry.register_class(DevComponent)
        prod_result = self.registry.register_class(ProdComponent)
        
        # development 프로파일 컴포넌트는 스킵되어야 함
        assert len(dev_result.warnings) > 0
        assert "profile development != test" in dev_result.warnings[0]
        
        # production 프로파일 컴포넌트도 스킵되어야 함
        assert len(prod_result.warnings) > 0
    
    def test_dependency_graph_building(self):
        """의존성 그래프 구성 테스트"""
        @Component(name="a")
        class A:
            pass
        
        @Component(name="b", dependencies=["a"])
        class B:
            pass
        
        @Component(name="c", dependencies=["a", "b"])
        class C:
            pass
        
        # 등록
        for cls in [A, B, C]:
            self.registry.register_class(cls)
        
        # 의존성 그래프 구성
        graph = self.registry.build_dependency_graph()
        
        assert "a" in graph.nodes
        assert "b" in graph.nodes  
        assert "c" in graph.nodes
        
        assert graph.edges["b"] == ["a"]
        assert set(graph.edges["c"]) == {"a", "b"}
        
        assert "b" in graph.reverse_edges["a"]
        assert "c" in graph.reverse_edges["a"]
        assert "c" in graph.reverse_edges["b"]
    
    def test_circular_dependency_detection(self):
        """순환 의존성 검출 테스트"""
        @Component(name="x", dependencies=["y"])
        class X:
            pass
        
        @Component(name="y", dependencies=["x"])
        class Y:
            pass
        
        # 등록
        self.registry.register_class(X)
        self.registry.register_class(Y)
        
        # 의존성 그래프에서 순환 의존성 검출
        graph = self.registry.build_dependency_graph()
        assert len(graph.circular_dependencies) > 0
        
        # 순환이 포함된 경로 확인
        cycle = graph.circular_dependencies[0]
        assert "x" in cycle and "y" in cycle
    
    def test_registration_stats(self):
        """등록 통계 테스트"""
        @Port(name="port1")
        class Port1(ABC):
            pass
        
        @Adapter(port="port1", name="adapter1")
        class Adapter1:
            pass
        
        @Component(name="component1")
        class Component1:
            pass
        
        # 등록
        for cls in [Port1, Adapter1, Component1]:
            self.registry.register_class(cls)
        
        stats = self.registry.get_registration_stats()
        assert stats["total_registered"] == 3
        assert stats["by_type"]["port"] == 1
        assert stats["by_type"]["adapter"] == 1
        assert stats["by_type"]["component"] == 1


class TestAnnotationProcessor:
    """어노테이션 프로세서 테스트"""
    
    def setup_method(self):
        self.registry = AnnotationRegistry(current_profile="test")
        self.processor = AnnotationProcessor(self.registry)
    
    def test_class_discovery_and_processing(self):
        """클래스 발견 및 처리 테스트"""
        @Port(name="discovery_port")
        class DiscoveryPort(ABC):
            pass
        
        @Adapter(port="discovery_port", name="discovery_adapter")
        class DiscoveryAdapter:
            pass
        
        @Component(name="discovery_component", dependencies=["discovery_adapter"])
        class DiscoveryComponent:
            pass
        
        classes = [DiscoveryPort, DiscoveryAdapter, DiscoveryComponent]
        context = ProcessingContext(profile="test", resolve_dependencies=True)
        
        result = self.processor.process_classes(classes, context)
        
        assert result.total_scanned == 3
        assert result.total_registered == 3
        assert len(result.successful_registrations) == 3
        assert len(result.validation_errors) == 0
    
    def test_dependency_resolution_order(self):
        """의존성 해결 순서 테스트"""
        @Component(name="leaf", dependencies=["middle"])
        class Leaf:
            pass
        
        @Component(name="middle", dependencies=["root"])
        class Middle:
            pass
        
        @Component(name="root")
        class Root:
            pass
        
        # 역순으로 제공 (의존성 해결이 필요)
        classes = [Leaf, Middle, Root]
        context = ProcessingContext(profile="test", resolve_dependencies=True)
        
        result = self.processor.process_classes(classes, context)
        
        assert result.total_registered == 3
        assert len(result.validation_errors) == 0
        
        # 등록 순서가 의존성 순서여야 함 (root -> middle -> leaf)
        registration_order = self.registry.get_registration_stats()["registration_order"]
        assert registration_order.index("root") < registration_order.index("middle")
        assert registration_order.index("middle") < registration_order.index("leaf")
    
    def test_architecture_validation(self):
        """아키텍처 검증 테스트"""
        @Adapter(port="nonexistent_port", name="bad_adapter")
        class BadAdapter:
            pass
        
        classes = [BadAdapter]
        context = ProcessingContext(profile="test", validate_architecture=True)
        
        result = self.processor.process_classes(classes, context)
        
        # 존재하지 않는 port를 참조하는 adapter이므로 검증 오류 발생
        assert len(result.validation_errors) > 0
        assert any("unknown port" in error.lower() for error in result.validation_errors)
    
    @pytest.mark.asyncio
    async def test_performance_benchmarking(self):
        """성능 벤치마킹 테스트"""
        # 많은 수의 컴포넌트 생성
        classes = []
        for i in range(100):
            @Component(name=f"component_{i}")
            class DynamicComponent:
                pass
            
            # 클래스 이름을 동적으로 설정
            DynamicComponent.__name__ = f"Component{i}"
            classes.append(DynamicComponent)
        
        context = ProcessingContext(profile="test")
        
        start_time = time.time()
        result = self.processor.process_classes(classes, context)
        processing_time = time.time() - start_time
        
        assert result.total_registered == 100
        assert result.processing_time_ms < 1000  # 1초 이내
        assert processing_time < 1.0  # 실제 처리 시간도 1초 이내
        
        print(f"Performance: {result.total_registered} classes in {result.processing_time_ms:.2f}ms")


class TestHexagonalArchitectureValidation:
    """헥사고날 아키텍처 검증 테스트"""
    
    def test_valid_hexagonal_architecture(self):
        """올바른 헥사고날 아키텍처 검증"""
        @Port(name="user_repository")
        class UserRepository(ABC):
            pass
        
        @Adapter(port="user_repository", name="postgres_user_repository")
        class PostgresUserRepository(UserRepository):
            pass
        
        @UseCase(dependencies=["user_repository"])
        class GetUserUseCase:
            pass
        
        @Controller(route="/users", dependencies=["get_user_use_case"])
        class UserController:
            pass
        
        classes = [UserRepository, PostgresUserRepository, GetUserUseCase, UserController]
        errors = validate_hexagonal_architecture(classes)
        
        assert len(errors) == 0  # 검증 오류 없어야 함
    
    def test_invalid_port_reference(self):
        """잘못된 port 참조 검증"""
        @Adapter(port="nonexistent_port", name="bad_adapter")
        class BadAdapter:
            pass
        
        classes = [BadAdapter]
        errors = validate_hexagonal_architecture(classes)
        
        assert len(errors) > 0
        assert any("unknown port" in error.lower() for error in errors)


class TestIntegration:
    """통합 테스트"""
    
    def test_complete_hexagonal_architecture_flow(self):
        """완전한 헥사고날 아키텍처 플로우 테스트"""
        # Domain layer (Port)
        @Port(name="user_repository", description="User data access port")
        class UserRepository(ABC):
            @abstractmethod
            def save(self, user: dict) -> dict: pass
            
            @abstractmethod
            def find_by_id(self, user_id: str) -> dict: pass
        
        # Infrastructure layer (Adapter)
        @Adapter(port="user_repository", name="memory_user_repository")
        class MemoryUserRepository(UserRepository):
            def __init__(self):
                self.users = {}
            
            def save(self, user: dict) -> dict:
                self.users[user['id']] = user
                return user
            
            def find_by_id(self, user_id: str) -> dict:
                return self.users.get(user_id)
        
        # Application layer (Use Case)
        @UseCase(name="create_user_use_case", dependencies=["user_repository"])
        class CreateUserUseCase:
            def __init__(self, user_repository: UserRepository):
                self.user_repository = user_repository
            
            def execute(self, user_data: dict) -> dict:
                return self.user_repository.save(user_data)
        
        # Presentation layer (Controller)
        @Controller(route="/api/users", dependencies=["create_user_use_case"])
        class UserController:
            def __init__(self, create_user_use_case: CreateUserUseCase):
                self.create_user_use_case = create_user_use_case
            
            def create_user(self, user_data: dict) -> dict:
                return self.create_user_use_case.execute(user_data)
        
        # 자동 등록 및 실행
        registry = AnnotationRegistry()
        processor = AnnotationProcessor(registry)
        
        classes = [UserRepository, MemoryUserRepository, CreateUserUseCase, UserController]
        context = ProcessingContext(resolve_dependencies=True, validate_architecture=True)
        
        result = processor.process_classes(classes, context)
        
        # 모든 컴포넌트가 성공적으로 등록되어야 함
        assert result.total_registered == 4
        assert len(result.validation_errors) == 0
        
        # 실제 사용 시나리오 테스트
        controller = registry.get("UserController")
        assert controller is not None
        
        test_user = {"id": "123", "name": "Test User"}
        created_user = controller.create_user(test_user)
        
        assert created_user == test_user
        assert created_user["id"] == "123"


class TestConvenienceFunctions:
    """편의 함수 테스트"""
    
    def test_auto_register_classes(self):
        """auto_register_classes 편의 함수 테스트"""
        @Component(name="test_component1")
        class TestComponent1:
            pass
        
        @Component(name="test_component2")
        class TestComponent2:
            pass
        
        result = auto_register_classes(TestComponent1, TestComponent2)
        
        assert result.total_registered == 2
        assert len(result.successful_registrations) == 2
    
    def test_auto_register_decorator(self):
        """@auto_register 데코레이터 테스트"""
        # 레지스트리 설정
        registry = AnnotationRegistry()
        
        @auto_register(registry)
        @Component(name="auto_registered_component")
        class AutoRegisteredComponent:
            pass
        
        # 자동 등록되었는지 확인
        instance = registry.get("auto_registered_component")
        assert instance is not None
        assert isinstance(instance, AutoRegisteredComponent)


# 성능 테스트
class TestPerformance:
    """성능 테스트"""
    
    @pytest.mark.performance
    def test_annotation_processing_overhead(self):
        """어노테이션 처리 오버헤드 테스트"""
        # 어노테이션 있는 클래스
        @Component(name="annotated_class")
        class AnnotatedClass:
            pass
        
        # 어노테이션 없는 클래스
        class PlainClass:
            pass
        
        # 어노테이션 처리 시간 측정
        start = time.time()
        for _ in range(1000):
            has_annotation(AnnotatedClass)
            get_annotation_metadata(AnnotatedClass)
        annotated_time = time.time() - start
        
        # 일반 클래스 처리 시간 측정
        start = time.time()
        for _ in range(1000):
            has_annotation(PlainClass)
            get_annotation_metadata(PlainClass)
        plain_time = time.time() - start
        
        # 오버헤드는 5배 이내여야 함
        overhead_ratio = annotated_time / plain_time if plain_time > 0 else 1
        assert overhead_ratio < 5.0
        
        print(f"Annotation overhead: {overhead_ratio:.2f}x")


if __name__ == "__main__":
    # 테스트 실행
    pytest.main([__file__, "-v", "--tb=short"])