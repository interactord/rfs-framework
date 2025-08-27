"""
RFS v4 Annotation System
헥사고날 아키텍처를 위한 어노테이션 기반 의존성 주입 시스템

주요 특징:
- 헥사고날 아키텍처 패턴 지원 (@Port, @Adapter, @UseCase, @Controller)
- 컴포넌트 생명주기 관리 (scope: singleton, prototype, request)
- 타입 안전성과 런타임 검증
- 기존 StatelessRegistry와의 하위 호환성
"""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, Union

from .registry import ServiceDefinition, ServiceScope


class AnnotationType(Enum):
    """어노테이션 타입"""

    PORT = "port"
    ADAPTER = "adapter"
    COMPONENT = "component"
    USE_CASE = "use_case"
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"


class ComponentScope(Enum):
    """컴포넌트 스코프 (ServiceScope와 호환)"""

    SINGLETON = "singleton"
    PROTOTYPE = "prototype"
    REQUEST = "request"

    def to_service_scope(self) -> ServiceScope:
        """ServiceScope로 변환"""
        mapping = {
            ComponentScope.SINGLETON: ServiceScope.SINGLETON,
            ComponentScope.PROTOTYPE: ServiceScope.PROTOTYPE,
            ComponentScope.REQUEST: ServiceScope.REQUEST,
        }
        return mapping[self]


@dataclass
class AnnotationMetadata:
    """어노테이션 메타데이터"""

    annotation_type: AnnotationType
    name: str
    target_class: Type[Any]
    dependencies: List[str] = field(default_factory=list)
    scope: ComponentScope = ComponentScope.SINGLETON
    lazy = False
    profile = None
    port_name = None
    route = None
    created_at: datetime = field(default_factory=datetime.now)
    description = None
    version = "1.0.0"


class PortProtocol(Protocol):
    """Port 인터페이스를 위한 프로토콜"""

    pass


def Port(name: str, description: str = None) -> Callable[[Type], Type]:
    """
    헥사고날 아키텍처의 Port(인터페이스) 정의 어노테이션

    Args:
        name: Port 이름
        description: Port 설명

    Example:
        @Port(name="user_repository", description="사용자 저장소 인터페이스")
        class UserRepository(ABC):
            @abstractmethod
            def find_by_id(self, user_id: str) -> Result[User, Error]: ...
    """

    def decorator(cls: Type) -> Type:
        metadata = AnnotationMetadata(
            annotation_type=AnnotationType.PORT,
            name=name,
            target_class=cls,
            description=description,
        )
        setattr(cls, "_rfs_annotation_metadata", metadata)
        setattr(cls, "_rfs_port_name", name)
        return cls

    return decorator


def Adapter(
    port: str,
    name: str = None,
    scope: ComponentScope = ComponentScope.SINGLETON,
    profile: str = None,
) -> Callable[[Type], Type]:
    """
    헥사고날 아키텍처의 Adapter(구현체) 정의 어노테이션

    Args:
        port: 구현할 Port 이름
        name: Adapter 이름 (기본값: 클래스명)
        scope: 컴포넌트 스코프
        profile: 환경별 프로파일

    Example:
        @Adapter(port="user_repository", scope=ComponentScope.SINGLETON, profile="production")
        class PostgresUserRepository(UserRepository):
            def find_by_id(self, user_id: str) -> Result[User, Error]: ...
    """

    def decorator(cls: Type) -> Type:
        adapter_name = name or cls.__name__
        metadata = AnnotationMetadata(
            annotation_type=AnnotationType.ADAPTER,
            name=adapter_name,
            target_class=cls,
            port_name=port,
            scope=scope,
            profile=profile,
        )
        setattr(cls, "_rfs_annotation_metadata", metadata)
        return cls

    return decorator


def Component(
    name: str = None,
    scope: ComponentScope = ComponentScope.SINGLETON,
    dependencies: List[str] = None,
    lazy=False,
    profile: str = None,
) -> Callable[[Type], Type]:
    """
    일반적인 컴포넌트 정의 어노테이션

    Args:
        name: 컴포넌트 이름 (기본값: 클래스명)
        scope: 컴포넌트 스코프
        dependencies: 의존성 목록
        lazy: 지연 초기화 여부
        profile: 환경별 프로파일

    Example:
        @Component(name="email_service", dependencies=["smtp_client"])
        class EmailService:
            def __init__(self, smtp_client: SMTPClient): ...
    """

    def decorator(cls: Type) -> Type:
        component_name = name or cls.__name__
        metadata = AnnotationMetadata(
            annotation_type=AnnotationType.COMPONENT,
            name=component_name,
            target_class=cls,
            dependencies=dependencies or [],
            scope=scope,
            lazy=lazy,
            profile=profile,
        )
        setattr(cls, "_rfs_annotation_metadata", metadata)
        return cls

    return decorator


def UseCase(
    name: str = None,
    dependencies: List[str] = None,
    scope: ComponentScope = ComponentScope.SINGLETON,
) -> Callable[[Type], Type]:
    """
    헥사고날 아키텍처의 UseCase(애플리케이션 서비스) 정의 어노테이션

    Args:
        name: UseCase 이름 (기본값: 클래스명)
        dependencies: 의존성 목록 (주로 Port들)
        scope: 컴포넌트 스코프

    Example:
        @UseCase(dependencies=["user_repository", "email_service"])
        class CreateUserUseCase:
            def execute(self, user_data: UserData) -> Result[User, Error]: ...
    """

    def decorator(cls: Type) -> Type:
        usecase_name = name or cls.__name__
        metadata = AnnotationMetadata(
            annotation_type=AnnotationType.USE_CASE,
            name=usecase_name,
            target_class=cls,
            dependencies=dependencies or [],
            scope=scope,
        )
        setattr(cls, "_rfs_annotation_metadata", metadata)
        return cls

    return decorator


def Controller(
    route: str = None,
    name: str = None,
    dependencies: List[str] = None,
    scope: ComponentScope = ComponentScope.SINGLETON,
) -> Callable[[Type], Type]:
    """
    헥사고날 아키텍처의 Controller(프레젠테이션 계층) 정의 어노테이션

    Args:
        route: 라우트 정보
        name: Controller 이름 (기본값: 클래스명)
        dependencies: 의존성 목록 (주로 UseCase들)
        scope: 컴포넌트 스코프

    Example:
        @Controller(route="/api/users", dependencies=["create_user_use_case"])
        class UserController:
            def create_user(self, user_data: UserData) -> Response: ...
    """

    def decorator(cls: Type) -> Type:
        controller_name = name or cls.__name__
        metadata = AnnotationMetadata(
            annotation_type=AnnotationType.CONTROLLER,
            name=controller_name,
            target_class=cls,
            dependencies=dependencies or [],
            scope=scope,
            route=route,
        )
        setattr(cls, "_rfs_annotation_metadata", metadata)
        return cls

    return decorator


def Service(
    name: str = None,
    scope: ComponentScope = ComponentScope.SINGLETON,
    dependencies: List[str] = None,
    lazy=False,
) -> Callable[[Type], Type]:
    """@Component의 별칭 - 서비스 레이어용"""
    return Component(name=name, scope=scope, dependencies=dependencies, lazy=lazy)


def Repository(
    name: str = None,
    scope: ComponentScope = ComponentScope.SINGLETON,
    dependencies: List[str] = None,
) -> Callable[[Type], Type]:
    """@Component의 별칭 - 저장소 레이어용"""
    return Component(name=name, scope=scope, dependencies=dependencies)


def get_annotation_metadata(cls: Type) -> Optional[AnnotationMetadata]:
    """클래스의 어노테이션 메타데이터 조회"""
    return getattr(cls, "_rfs_annotation_metadata", None)


def has_annotation(cls: Type) -> bool:
    """클래스가 RFS 어노테이션을 가지고 있는지 확인"""
    return hasattr(cls, "_rfs_annotation_metadata")


def is_port(cls: Type) -> bool:
    """클래스가 Port인지 확인"""
    metadata = get_annotation_metadata(cls)
    return metadata is not None and metadata.annotation_type == AnnotationType.PORT


def is_adapter(cls: Type) -> bool:
    """클래스가 Adapter인지 확인"""
    metadata = get_annotation_metadata(cls)
    return metadata is not None and metadata.annotation_type == AnnotationType.ADAPTER


def is_use_case(cls: Type) -> bool:
    """클래스가 UseCase인지 확인"""
    metadata = get_annotation_metadata(cls)
    return metadata is not None and metadata.annotation_type == AnnotationType.USE_CASE


def is_controller(cls: Type) -> bool:
    """클래스가 Controller인지 확인"""
    metadata = get_annotation_metadata(cls)
    return (
        metadata is not None and metadata.annotation_type == AnnotationType.CONTROLLER
    )


def validate_hexagonal_architecture(classes: List[Type]) -> List[str]:
    """
    헥사고날 아키텍처 규칙 검증

    Returns:
        List[str]: 검증 오류 메시지들
    """
    errors = []
    ports = {}
    adapters = {}
    for cls in classes:
        metadata = get_annotation_metadata(cls)
        if not metadata:
            continue
        if metadata.annotation_type == AnnotationType.PORT:
            ports[metadata.name] = {metadata.name: cls}
        elif metadata.annotation_type == AnnotationType.ADAPTER:
            adapters[metadata.name] = {metadata.name: metadata.port_name}
    for adapter_name, port_name in adapters.items():
        if port_name not in ports:
            errors = errors + [
                f"Adapter '{adapter_name}' references unknown port '{port_name}'"
            ]
    return errors


if __name__ == "__main__":
    from abc import ABC, abstractmethod

    @Port(name="user_repository", description="사용자 저장소 인터페이스")
    class UserRepository(ABC):

        @abstractmethod
        def find_by_id(self, user_id: str) -> Any: ...

        @abstractmethod
        def save(self, user: Any) -> Any: ...

    @Adapter(port="user_repository", profile="production")
    class PostgresUserRepository(UserRepository):

        def find_by_id(self, user_id: str) -> Any:
            return f"Found user {user_id} from PostgreSQL"

        def save(self, user: Any) -> Any:
            return f"Saved user to PostgreSQL"

    @UseCase(dependencies=["user_repository"])
    class GetUserUseCase:

        def __init__(self, user_repository: UserRepository):
            self.user_repository = user_repository

        def execute(self, user_id: str) -> Any:
            return self.user_repository.find_by_id(user_id)

    @Controller(route="/api/users", dependencies=["get_user_use_case"])
    class UserController:

        def __init__(self, get_user_use_case: GetUserUseCase):
            self.get_user_use_case = get_user_use_case

        def get_user(self, user_id: str) -> Any:
            return self.get_user_use_case.execute(user_id)

    classes = [UserRepository, PostgresUserRepository, GetUserUseCase, UserController]
    for cls in classes:
        metadata = get_annotation_metadata(cls)
        if metadata:
            print(f"{cls.__name__}: {metadata.annotation_type.value} - {metadata.name}")
    errors = validate_hexagonal_architecture(classes)
    if errors:
        print("Architecture validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✅ Hexagonal architecture validation passed!")
