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
    get_annotation_metadata,
    get_component_metadata,
    set_annotation_metadata,
    set_component_metadata,
)

# ============================================================================
# Hexagonal Architecture Annotations
# ============================================================================


def Port(name=None, dependencies: Optional[List[str]] = None):
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
            name=port_name,
            scope=ServiceScope.SINGLETON,
        )

        # 애노테이션 메타데이터 추가
        from .base import AnnotationType

        annotation = AnnotationMetadata(
            name=port_name,
            annotation_type=AnnotationType.PORT,
            scope=ServiceScope.SINGLETON,
            target_class=cls,
            dependencies=dependencies or [],
        )

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
    profile=None,
    primary=False,
    name=None,
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
        if isinstance(port, str):
            port_name = port
        else:
            port_name = getattr(port, "_port_name", port.__name__)

        adapter_name = name or cls.__name__

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            name=adapter_name,
            scope=scope,
            primary=primary,
        )

        # 애노테이션 메타데이터 추가
        from .base import AnnotationType

        annotation = AnnotationMetadata(
            name=adapter_name,
            annotation_type=AnnotationType.ADAPTER,
            scope=scope,
            target_class=cls,
            profile=profile,
            port_name=port_name,
        )

        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        # 어댑터임을 표시
        cls._is_adapter = True
        cls._port_name = port_name
        cls._adapter_name = adapter_name

        return cls

    return decorator


def UseCase(
    name=None,
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
            name=use_case_name,
            scope=scope,
        )

        # 애노테이션 메타데이터 추가
        from .base import AnnotationType

        annotation = AnnotationMetadata(
            name=use_case_name,
            annotation_type=AnnotationType.USE_CASE,
            scope=scope,
            target_class=cls,
            dependencies=dependencies or [],
        )

        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        # 유즈케이스임을 표시
        cls._is_use_case = True
        cls._use_case_name = use_case_name

        return cls

    return decorator


def Controller(
    route=None,
    method: Union[str, List[str]] = "GET",
    name=None,
    dependencies: Optional[List[str]] = None,
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
            name=controller_name,
            scope=ServiceScope.REQUEST,  # Controller는 REQUEST 스코프가 기본
        )

        # 애노테이션 메타데이터 추가
        from .base import AnnotationType

        annotation = AnnotationMetadata(
            name=controller_name,
            annotation_type=AnnotationType.CONTROLLER,
            scope=ServiceScope.REQUEST,  # Controller는 REQUEST 스코프가 기본
            target_class=cls,
            dependencies=dependencies or [],
        )

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
    name: str,
    scope: ServiceScope = ServiceScope.SINGLETON,
    lazy=False,
    dependencies: Optional[List[str]] = None,
    profile=None,
    primary=False,
    qualifier=None,
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

        # 스코프 타입 검증
        if not isinstance(scope, ServiceScope):
            raise AttributeError(
                f"scope must be a ServiceScope enum, not {type(scope)}"
            )

        # 기존 더 구체적인 애노테이션이 있는지 확인
        from .base import AnnotationType

        existing_annotation = get_annotation_metadata(cls)
        if (
            existing_annotation
            and existing_annotation.annotation_type != AnnotationType.COMPONENT
        ):
            # 더 구체적인 데코레이터가 이미 적용된 경우, Component는 오버라이드하지 않음
            # 단, 펜딩 속성들만 정리
            for attr in ["_pending_scope", "_pending_lazy", "_pending_primary"]:
                if hasattr(cls, attr):
                    delattr(cls, attr)
            return cls

        # 다른 데코레이터에서 설정된 값들 확인
        pending_scope = getattr(cls, "_pending_scope", scope)
        pending_lazy = getattr(cls, "_pending_lazy", lazy)
        pending_primary = getattr(cls, "_pending_primary", primary)

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            name=component_name,
            scope=pending_scope,
            lazy=pending_lazy,
            dependencies=dependencies or [],
            primary=pending_primary,
            qualifier=qualifier,
        )

        # 애노테이션 메타데이터 생성
        annotation = AnnotationMetadata(
            name=component_name,
            annotation_type=AnnotationType.COMPONENT,
            scope=pending_scope,
            target_class=cls,
            dependencies=dependencies or [],
            lazy=pending_lazy,
            profile=profile,
        )

        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        cls._is_component = True
        cls._component_name = component_name

        # 펜딩 속성들 정리
        for attr in ["_pending_scope", "_pending_lazy", "_pending_primary"]:
            if hasattr(cls, attr):
                delattr(cls, attr)

        return cls

    return decorator


def Service(name: str, scope: ServiceScope = ServiceScope.SINGLETON):
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

        # 다른 데코레이터에서 설정된 값들 확인
        pending_scope = getattr(cls, "_pending_scope", scope)
        pending_lazy = getattr(cls, "_pending_lazy", False)
        pending_primary = getattr(cls, "_pending_primary", False)

        # Component와 동일하지만 타입이 다름
        metadata = ComponentMetadata(
            name=service_name,
            scope=pending_scope,
            lazy=pending_lazy,
            primary=pending_primary,
        )

        # 애노테이션 메타데이터 추가
        from .base import AnnotationType

        annotation = AnnotationMetadata(
            name=service_name,
            annotation_type=AnnotationType.SERVICE,
            scope=pending_scope,
            target_class=cls,
            lazy=pending_lazy,
        )
        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        cls._is_service = True
        cls._service_name = service_name

        # 펜딩 속성들 정리
        for attr in ["_pending_scope", "_pending_lazy", "_pending_primary"]:
            if hasattr(cls, attr):
                delattr(cls, attr)

        return cls

    return decorator


def Repository(
    name=None,
    scope: ServiceScope = ServiceScope.SINGLETON,
    dependencies: Optional[List[str]] = None,
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

        # 컴포넌트 메타데이터 생성
        metadata = ComponentMetadata(
            name=repo_name,
            scope=scope,
        )

        # 애노테이션 메타데이터 추가
        from .base import AnnotationType

        annotation = AnnotationMetadata(
            name=repo_name,
            annotation_type=AnnotationType.REPOSITORY,
            scope=scope,
            target_class=cls,
            dependencies=dependencies or [],
        )

        set_component_metadata(cls, metadata)
        set_annotation_metadata(cls, annotation)

        cls._is_repository = True
        cls._repository_name = repo_name

        return cls

    return decorator


# ============================================================================
# Dependency Injection Annotations
# ============================================================================


def Injectable(cls=None, *, name=None):
    """
    주입 가능한 클래스 표시

    Usage:
        @Injectable
        class DatabaseClient:
            pass

        @Injectable(name="custom_service")
        class CustomService:
            pass
    """

    def decorator(target_cls):
        component_name = name or target_cls.__name__
        return Component(name=component_name)(target_cls)

    # 파라미터 없이 사용된 경우 (@Injectable)
    if cls is not None:
        return decorator(cls)

    # 파라미터와 함께 사용된 경우 (@Injectable(name="..."))
    return decorator


def Autowired(qualifier=None, lazy=False, required=True):
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
        # ComponentMetadata 업데이트 (이미 있는 경우)
        metadata = get_component_metadata(cls)
        if metadata:
            metadata.scope = scope

        # AnnotationMetadata 업데이트 (이미 있는 경우)
        annotation = get_annotation_metadata(cls)
        if annotation:
            annotation.scope = scope

        # 메타데이터가 없는 경우 펜딩 속성으로 저장
        if not metadata and not annotation:
            cls._pending_scope = scope

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
    # ComponentMetadata 업데이트 (이미 있는 경우)
    metadata = get_component_metadata(cls)
    if metadata:
        metadata.primary = True

    # 메타데이터가 없는 경우 펜딩 속성으로 저장
    if not metadata:
        cls._pending_primary = True

    # Primary 속성은 AnnotationMetadata에는 없음, ComponentMetadata에만 있음
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
    # ComponentMetadata 업데이트 (이미 있는 경우)
    metadata = get_component_metadata(cls)
    if metadata:
        metadata.lazy = True

    # AnnotationMetadata 업데이트 (이미 있는 경우)
    annotation = get_annotation_metadata(cls)
    if annotation:
        annotation.lazy = True

    # 메타데이터가 없는 경우 펜딩 속성으로 저장
    if not metadata and not annotation:
        cls._pending_lazy = True

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


def ConfigProperty(key: str, default: Any = None):
    """
    설정 프로퍼티 데코레이터

    Usage:
        class DatabaseConfig:
            @ConfigProperty("database.host")
            def db_host(self):
                pass

            @ConfigProperty("database.port", default=5432)
            def db_port(self):
                pass
    """

    def decorator(field):
        field._config_key = key
        field._config_default = default
        return field

    return decorator
