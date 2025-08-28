"""
Base Annotation Definitions and Metadata for RFS Framework

기본 애노테이션 정의 및 메타데이터 관리
"""

import inspect
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type


class ServiceScope(Enum):
    """서비스 스코프 정의"""

    SINGLETON = "singleton"
    PROTOTYPE = "prototype"
    REQUEST = "request"
    SESSION = "session"

    def to_service_scope(self) -> "ServiceScope":
        """ServiceScope로 변환 (이미 ServiceScope인 경우 자기 자신 반환)"""
        return self


class InjectionType(Enum):
    """주입 타입"""

    CONSTRUCTOR = "constructor"
    SETTER = "setter"
    FIELD = "field"


class AnnotationType(Enum):
    """어노테이션 타입"""

    COMPONENT = "component"
    PORT = "port"
    ADAPTER = "adapter"
    USE_CASE = "use_case"
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    VALUE = "value"
    CONFIG = "config"


@dataclass
class AnnotationMetadata:
    """애노테이션 메타데이터"""

    name: str
    annotation_type: AnnotationType
    scope: ServiceScope
    target_class: Any
    dependencies: List[str] = field(default_factory=list)
    lazy: bool = False
    profile: Optional[str] = None
    port_name: Optional[str] = None
    config_key: Optional[str] = None


@dataclass
class DependencyMetadata:
    """의존성 메타데이터"""

    name: str
    type: Type
    qualifier: Optional[str] = None
    required: bool = True
    lazy: bool = False
    injection_type: InjectionType = InjectionType.CONSTRUCTOR
    default_value: Any = None


@dataclass
class ComponentMetadata:
    """컴포넌트 메타데이터"""

    name: str
    scope: ServiceScope
    dependencies: List[str] = field(default_factory=list)
    lazy: bool = False
    primary: bool = False
    qualifier: Optional[str] = None

    def to_service_scope(self) -> ServiceScope:
        """ServiceScope 반환"""
        return self.scope


_component_metadata: Dict[Type, ComponentMetadata] = {}
_annotation_metadata: Dict[Any, List[AnnotationMetadata]] = {}


def get_component_metadata(component_type: Type) -> Optional[ComponentMetadata]:
    """컴포넌트 메타데이터 조회"""
    return _component_metadata.get(component_type)


def set_component_metadata(component_type: Type, metadata: ComponentMetadata):
    """컴포넌트 메타데이터 저장"""
    global _component_metadata
    _component_metadata[component_type] = metadata


def get_annotation_metadata(target: Any) -> Optional[AnnotationMetadata]:
    """애노테이션 메타데이터 조회"""
    if target is None:
        raise AttributeError("Cannot get annotation metadata from None")
    metadata_list = _annotation_metadata.get(target, [])
    return metadata_list[0] if metadata_list else None


def has_annotation(target: Any) -> bool:
    """애노테이션 존재 여부 확인"""
    if target is None:
        raise AttributeError("Cannot check annotation on None")
    return target in _annotation_metadata and len(_annotation_metadata[target]) > 0


def validate_hexagonal_architecture(classes: List[Type]) -> List[str]:
    """헥사고날 아키텍처 검증

    Returns:
        List[str]: 검증 오류 메시지들
    """
    errors = []

    for cls in classes:
        metadata = get_annotation_metadata(cls)
        if not metadata:
            continue

        # 어댑터는 포트 이름이 있어야 함
        if metadata.annotation_type == AnnotationType.ADAPTER:
            if not metadata.port_name:
                errors.append(f"Adapter {metadata.name} must specify a port_name")

        # 유스케이스는 포트에만 의존해야 함 (어댑터, 리포지토리 직접 의존 금지)
        if metadata.annotation_type == AnnotationType.USE_CASE:
            for dependency in metadata.dependencies:
                if (
                    "adapter" in dependency.lower()
                    or "repository" in dependency.lower()
                ):
                    errors.append(
                        f"UseCase {metadata.name} should depend on ports, not {dependency}"
                    )

    return errors


def set_annotation_metadata(target: Any, metadata: AnnotationMetadata):
    """애노테이션 메타데이터 저장"""
    if target is None:
        raise AttributeError("Cannot set annotation metadata on None")
    global _annotation_metadata
    if target not in _annotation_metadata:
        _annotation_metadata[target] = []
    _annotation_metadata[target] = [metadata]  # 리스트로 저장하지만 하나만


def create_annotation_decorator(
    annotation_type: AnnotationType, target_types: Optional[List[str]] = None
) -> Callable:
    """애노테이션 데코레이터 생성 헬퍼"""
    if target_types is None:
        target_types = ["class", "method", "field"]

    def decorator(**params):

        def wrapper(target):
            if inspect.isclass(target):
                target_type = "class"
            elif inspect.ismethod(target) or inspect.isfunction(target):
                target_type = "method"
            else:
                target_type = "field"
            if target_type not in target_types:
                raise ValueError(
                    f"@{annotation_type.value} cannot be applied to {target_type}"
                )

            metadata = AnnotationMetadata(
                name=params.get("name", target.__name__),
                annotation_type=annotation_type,
                scope=params.get("scope", ServiceScope.SINGLETON),
                target_class=target,
                dependencies=params.get("dependencies", []),
                lazy=params.get("lazy", False),
                profile=params.get("profile"),
                port_name=params.get("port_name"),
                config_key=params.get("config_key"),
            )
            set_annotation_metadata(target, metadata)

            if target_type == "class":
                component_metadata = get_component_metadata(target)
                if not component_metadata:
                    component_metadata = ComponentMetadata(
                        name=params.get("name", target.__name__),
                        scope=params.get("scope", ServiceScope.SINGLETON),
                        dependencies=params.get("dependencies", []),
                        lazy=params.get("lazy", False),
                        primary=params.get("primary", False),
                        qualifier=params.get("qualifier"),
                    )
                    set_component_metadata(target, component_metadata)
            return target

        return wrapper

    return decorator


def extract_dependencies(cls: Type) -> List[DependencyMetadata]:
    """클래스에서 의존성 추출"""
    dependencies: List[DependencyMetadata] = []
    if hasattr(cls, "__init__"):
        sig = inspect.signature(cls.__init__)
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.annotation != inspect.Parameter.empty:
                dep = DependencyMetadata(
                    name=param_name,
                    type=param.annotation,
                    required=param.default == inspect.Parameter.empty,
                    injection_type=InjectionType.CONSTRUCTOR,
                )
                dependencies = dependencies + [dep]
    if hasattr(cls, "__annotations__"):
        for field_name, field_type in cls.__annotations__.items():
            if hasattr(cls, field_name):
                field_value = getattr(cls, field_name)
                if hasattr(field_value, "_autowired"):
                    dep = DependencyMetadata(
                        name=field_name,
                        type=field_type,
                        injection_type=InjectionType.FIELD,
                        qualifier=getattr(field_value, "_qualifier", None),
                        lazy=getattr(field_value, "_lazy", False),
                    )
                    dependencies = dependencies + [dep]
    return dependencies


class AutowiredField:
    """Autowired 필드를 위한 디스크립터"""

    def __init__(self, field_type: Optional[Type] = None, qualifier: Optional[str] = None, lazy=False):
        self.field_type = field_type
        self.qualifier = qualifier
        self.lazy = lazy
        self._autowired = True
        self._qualifier = qualifier
        self._lazy = lazy

    def __set_name__(self, owner, name):
        self.name = name
        self.owner = owner

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, f"_{self.name}", None)

    def __set__(self, obj, value):
        setattr(obj, f"_{self.name}", value)


def lifecycle_callback(callback_type: str):
    """라이프사이클 콜백 데코레이터"""

    def decorator(method):
        method._lifecycle_callback = callback_type
        return method

    return decorator


def PostConstruct(method):
    """생성 후 콜백"""
    return lifecycle_callback("post_construct")(method)


def PreDestroy(method):
    """소멸 전 콜백"""
    return lifecycle_callback("pre_destroy")(method)
