"""
Dependency Injection Annotations for RFS Framework

의존성 주입 애노테이션 - Hexagonal Architecture 지원
"""

import inspect
from functools import wraps
from typing import Any, List, Optional, Type, Union

from .base import (
    AnnotationMetadata,
    AutowiredField,
    ComponentMetadata,
    DependencyMetadata,
    InjectionType,
    ServiceScope,
    create_annotation_decorator,
    extract_dependencies,
    get_component_metadata,
    set_annotation_metadata,
    set_component_metadata,
)

# ============================================================================
# Hexagonal Architecture Annotations
# ============================================================================


def Port(name: Optional[str] = None):
    """
    도메인 포트 정의 (인터페이스)

    Usage:
        @Port(name="user_repository")
        class UserRepository(ABC):
            @abstractmethod
            def find_by_id(self, user_id: str) -> Result[User, Error]:
                pass
    """

    def decorator(cls):
        port_name = name or cls.__name__

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            component_id=f"port:{port_name}",
            component_type=cls,
            scope=ServiceScope.SINGLETON,
            metadata={"port_name": port_name, "type": "port"},
        )

        # 애노테이션 메타데이터 추가
        annotation = AnnotationMetadata(
            annotation_type="Port",
            parameters={"name": port_name},
            target=cls,
            target_type="class",
        )

        metadata.add_annotation(annotation)
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        # 포트임을 표시
        cls._is_port = True
        cls._port_name = port_name

        return cls

    return decorator


def Adapter(
    port: Union[str, Type],
    scope: ServiceScope = ServiceScope.SINGLETON,
    profile: Optional[str] = None,
    primary: bool = False,
):
    """
    인프라스트럭처 어댑터 정의 (구현체)

    Usage:
        @Adapter(port=UserRepository, scope=ServiceScope.SINGLETON)
        class PostgresUserRepository(UserRepository):
            def find_by_id(self, user_id: str) -> Result[User, Error]:
                # PostgreSQL implementation
                pass
    """

    def decorator(cls):
        # 포트 이름 추출
        if type(port).__name__ == "str":
            port_name = port
        else:
            port_name = getattr(port, "_port_name", port.__name__)

        adapter_name = cls.__name__

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            component_id=f"adapter:{adapter_name}",
            component_type=cls,
            scope=scope,
            primary=primary,
            profile=profile,
            metadata={
                "adapter_name": adapter_name,
                "port_name": port_name,
                "type": "adapter",
            },
        )

        # 의존성 추출
        dependencies = extract_dependencies(cls)
        for dep in dependencies:
            metadata.add_dependency(dep)

        # 애노테이션 메타데이터 추가
        annotation = AnnotationMetadata(
            annotation_type="Adapter",
            parameters={
                "port": port_name,
                "scope": scope,
                "profile": profile,
                "primary": primary,
            },
            target=cls,
            target_type="class",
        )

        metadata.add_annotation(annotation)
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        # 어댑터임을 표시
        cls._is_adapter = True
        cls._port_name = port_name
        cls._adapter_name = adapter_name

        return cls

    return decorator


def UseCase(
    name: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
    scope: ServiceScope = ServiceScope.PROTOTYPE,
):
    """
    애플리케이션 유즈케이스 정의

    Usage:
        @UseCase(dependencies=["user_repository", "email_service"])
        class RegisterUserUseCase:
            def __init__(self, user_repository: UserRepository, email_service: EmailService):
                self.user_repository = user_repository
                self.email_service = email_service

            def execute(self, command: RegisterUserCommand) -> Result[User, Error]:
                # Business logic
                pass
    """

    def decorator(cls):
        use_case_name = name or cls.__name__

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            component_id=f"use_case:{use_case_name}",
            component_type=cls,
            scope=scope,
            metadata={
                "use_case_name": use_case_name,
                "type": "use_case",
                "dependencies": dependencies or [],
            },
        )

        # 의존성 추출
        deps = extract_dependencies(cls)
        for dep in deps:
            metadata.add_dependency(dep)

        # 애노테이션 메타데이터 추가
        annotation = AnnotationMetadata(
            annotation_type="UseCase",
            parameters={
                "name": use_case_name,
                "dependencies": dependencies,
                "scope": scope,
            },
            target=cls,
            target_type="class",
        )

        metadata.add_annotation(annotation)
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        # 유즈케이스임을 표시
        cls._is_use_case = True
        cls._use_case_name = use_case_name

        return cls

    return decorator


def Controller(
    route: Optional[str] = None,
    method: Union[str, List[str]] = "GET",
    name: Optional[str] = None,
):
    """
    프레젠테이션 레이어 컨트롤러 정의

    Usage:
        @Controller(route="/api/users", method=["GET", "POST"])
        class UserController:
            def __init__(self, get_user_use_case: GetUserUseCase):
                self.get_user_use_case = get_user_use_case

            async def get_user(self, user_id: str) -> Result[UserDTO, Error]:
                result = await self.get_user_use_case.execute(user_id)
                return result.map(UserDTO.from_domain)
    """

    def decorator(cls):
        controller_name = name or cls.__name__
        methods = method if (type(method).__name__ == "list") else [method]

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            component_id=f"controller:{controller_name}",
            component_type=cls,
            scope=ServiceScope.SINGLETON,
            metadata={
                "controller_name": controller_name,
                "route": route,
                "methods": methods,
                "type": "controller",
            },
        )

        # 의존성 추출
        dependencies = extract_dependencies(cls)
        for dep in dependencies:
            metadata.add_dependency(dep)

        # 애노테이션 메타데이터 추가
        annotation = AnnotationMetadata(
            annotation_type="Controller",
            parameters={"route": route, "method": methods, "name": controller_name},
            target=cls,
            target_type="class",
        )

        metadata.add_annotation(annotation)
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        # 컨트롤러임을 표시
        cls._is_controller = True
        cls._controller_name = controller_name
        cls._route = route
        cls._methods = methods

        return cls

    return decorator


# ============================================================================
# General DI Annotations
# ============================================================================


def Component(
    name: Optional[str] = None,
    scope: ServiceScope = ServiceScope.SINGLETON,
    lazy: bool = False,
):
    """
    일반 컴포넌트 정의

    Usage:
        @Component(name="email_service", scope=ServiceScope.SINGLETON)
        class EmailService:
            def send_email(self, to: str, subject: str, body: str) -> Result[None, Error]:
                pass
    """

    def decorator(cls):
        component_name = name or cls.__name__

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            component_id=component_name,
            component_type=cls,
            scope=scope,
            lazy_init=lazy,
            metadata={"type": "component"},
        )

        # 의존성 추출
        dependencies = extract_dependencies(cls)
        for dep in dependencies:
            metadata.add_dependency(dep)

        # 애노테이션 메타데이터 추가
        annotation = AnnotationMetadata(
            annotation_type="Component",
            parameters={"name": component_name, "scope": scope, "lazy": lazy},
            target=cls,
            target_type="class",
        )

        metadata.add_annotation(annotation)
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        cls._is_component = True
        cls._component_name = component_name

        return cls

    return decorator


def Service(name: Optional[str] = None, scope: ServiceScope = ServiceScope.SINGLETON):
    """
    서비스 레이어 컴포넌트

    Usage:
        @Service(name="user_service")
        class UserService:
            def __init__(self, user_repository: UserRepository):
                self.user_repository = user_repository
    """

    def decorator(cls):
        service_name = name or cls.__name__

        # Component와 동일하지만 타입이 다름
        metadata = ComponentMetadata(
            component_id=f"service:{service_name}",
            component_type=cls,
            scope=scope,
            metadata={"type": "service", "service_name": service_name},
        )

        # 의존성 추출
        dependencies = extract_dependencies(cls)
        for dep in dependencies:
            metadata.add_dependency(dep)

        # 애노테이션 메타데이터 추가
        annotation = AnnotationMetadata(
            annotation_type="Service",
            parameters={"name": service_name, "scope": scope},
            target=cls,
            target_type="class",
        )

        metadata.add_annotation(annotation)
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        cls._is_service = True
        cls._service_name = service_name

        return cls

    return decorator


def Repository(
    name: Optional[str] = None, scope: ServiceScope = ServiceScope.SINGLETON
):
    """
    리포지토리 컴포넌트

    Usage:
        @Repository(name="user_repository")
        class UserRepositoryImpl:
            def find_by_id(self, user_id: str) -> Result[User, Error]:
                pass
    """

    def decorator(cls):
        repo_name = name or cls.__name__

        metadata = ComponentMetadata(
            component_id=f"repository:{repo_name}",
            component_type=cls,
            scope=scope,
            metadata={"type": "repository", "repository_name": repo_name},
        )

        # 의존성 추출
        dependencies = extract_dependencies(cls)
        for dep in dependencies:
            metadata.add_dependency(dep)

        # 애노테이션 메타데이터 추가
        annotation = AnnotationMetadata(
            annotation_type="Repository",
            parameters={"name": repo_name, "scope": scope},
            target=cls,
            target_type="class",
        )

        metadata.add_annotation(annotation)
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        cls._is_repository = True
        cls._repository_name = repo_name

        return cls

    return decorator


# ============================================================================
# Dependency Injection Annotations
# ============================================================================


def Injectable(cls):
    """
    주입 가능한 클래스 표시

    Usage:
        @Injectable
        class DatabaseClient:
            pass
    """
    # Component와 유사하지만 이름 자동 생성
    return Component()(cls)


def Autowired(
    qualifier: Optional[str] = None, lazy: bool = False, required: bool = True
):
    """
    자동 주입 필드

    Usage:
        class UserService:
            @Autowired(qualifier="postgres")
            user_repository: UserRepository
    """

    def decorator(field):
        # AutowiredField 디스크립터 반환
        return AutowiredField(
            field_type=field if inspect.isclass(field) else None,
            qualifier=qualifier,
            lazy=lazy,
        )

    # 필드 데코레이터로도 사용 가능
    if qualifier is None and not lazy and required:
        # @Autowired 형태로 사용된 경우
        return AutowiredField()

    return decorator


def Qualifier(name: str):
    """
    한정자 지정

    Usage:
        @Qualifier("postgres")
        @Adapter(port=UserRepository)
        class PostgresUserRepository(UserRepository):
            pass
    """

    def decorator(cls):
        metadata = get_component_metadata(cls)
        if metadata:
            metadata.metadata = {**metadata.metadata, "qualifier": name}

        cls._qualifier = name
        return cls

    return decorator


def Scope(scope: ServiceScope):
    """
    스코프 지정

    Usage:
        @Scope(ServiceScope.PROTOTYPE)
        @Component
        class RequestHandler:
            pass
    """

    def decorator(cls):
        metadata = get_component_metadata(cls)
        if metadata:
            metadata.scope = scope

        cls._scope = scope
        return cls

    return decorator


def Primary(cls):
    """
    기본 구현체 지정

    Usage:
        @Primary
        @Adapter(port=UserRepository)
        class DefaultUserRepository(UserRepository):
            pass
    """
    metadata = get_component_metadata(cls)
    if metadata:
        metadata.primary = True

    cls._primary = True
    return cls


def Lazy(cls):
    """
    지연 초기화

    Usage:
        @Lazy
        @Component
        class ExpensiveService:
            pass
    """
    metadata = get_component_metadata(cls)
    if metadata:
        metadata.lazy_init = True

    cls._lazy_init = True
    return cls


def Value(key: str, default: Any = None):
    """
    설정 값 주입

    Usage:
        class DatabaseConfig:
            @Value("database.host", default="localhost")
            host: str

            @Value("database.port", default=5432)
            port: int
    """

    def decorator(field):
        field._value_key = key
        field._value_default = default
        return field

    return decorator


def ConfigProperty(prefix: str = ""):
    """
    설정 프로퍼티 클래스

    Usage:
        @ConfigProperty(prefix="database")
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432
            username: str
            password: str
    """

    def decorator(cls):
        cls._config_prefix = prefix
        cls._is_config_property = True

        # Component로도 등록
        return Component(name=f"config:{prefix or cls.__name__}")(cls)

    return decorator
