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


class InjectionType(Enum):
    """주입 타입"""

    CONSTRUCTOR = "constructor"
    SETTER = "setter"
    FIELD = "field"


class AnnotationType(Enum):
    """어노테이션 타입"""

    PORT = "port"
    ADAPTER = "adapter"
    USE_CASE = "use_case"
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    COMPONENT = "component"


@dataclass
class AnnotationMetadata:
    """애노테이션 메타데이터"""

    annotation_type: str
    parameters: Dict[str, Any]
    target: Any
    target_type: str

    def get_param(self, key: str, default: Any = None) -> Any:
        """파라미터 조회"""
        return self.parameters.get(key, default)

    def has_param(self, key: str) -> bool:
        """파라미터 존재 여부"""
        return key in self.parameters


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

    component_id: str
    component_type: Type
    scope: ServiceScope = ServiceScope.SINGLETON
    primary: bool = False
    lazy_init: bool = False
    profile: Optional[str] = None
    annotations: List[AnnotationMetadata] = field(default_factory=list)
    dependencies: List[DependencyMetadata] = field(default_factory=list)
    constructor_dependencies: List[DependencyMetadata] = field(default_factory=list)
    field_dependencies: Dict[str, DependencyMetadata] = field(default_factory=dict)
    setter_dependencies: Dict[str, DependencyMetadata] = field(default_factory=dict)
    post_construct: Optional[Callable] = None
    pre_destroy: Optional[Callable] = None
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_annotation(self, annotation: AnnotationMetadata):
        """애노테이션 추가"""
        self.annotations = self.annotations + [annotation]

    def add_dependency(self, dependency: DependencyMetadata):
        """의존성 추가"""
        self.dependencies = self.dependencies + [dependency]
        match dependency.injection_type:
            case InjectionType.CONSTRUCTOR:
                self.constructor_dependencies = self.constructor_dependencies + [
                    dependency
                ]
            case InjectionType.FIELD:
                self.field_dependencies = {
                    **self.field_dependencies,
                    dependency.name: dependency,
                }
            case InjectionType.SETTER:
                self.setter_dependencies = {
                    **self.setter_dependencies,
                    dependency.name: dependency,
                }

    def get_dependencies_by_type(
        self, injection_type: InjectionType
    ) -> List[DependencyMetadata]:
        """주입 타입별 의존성 조회"""
        match injection_type:
            case InjectionType.CONSTRUCTOR:
                return self.constructor_dependencies
            case InjectionType.FIELD:
                return list(self.field_dependencies.values())
            case InjectionType.SETTER:
                return list(self.setter_dependencies.values())
        return []


_component_metadata: Dict[Type, ComponentMetadata] = {}
_annotation_metadata: Dict[Any, List[AnnotationMetadata]] = {}


def get_component_metadata(component_type: Type) -> Optional[ComponentMetadata]:
    """컴포넌트 메타데이터 조회"""
    return _component_metadata.get(component_type)


def set_component_metadata(component_type: Type, metadata: ComponentMetadata):
    """컴포넌트 메타데이터 저장"""
    global _component_metadata
    _component_metadata[component_type] = metadata


def get_annotation_metadata(target: Any) -> List[AnnotationMetadata]:
    """애노테이션 메타데이터 조회"""
    return _annotation_metadata.get(target, [])


def has_annotation(target: Any) -> bool:
    """애노테이션 존재 여부 확인"""
    return target in _annotation_metadata and len(_annotation_metadata[target]) > 0


def validate_hexagonal_architecture(classes: List[Type]) -> List[str]:
    """헥사고날 아키텍처 검증
    
    Returns:
        List[str]: 검증 오류 메시지들
    """
    # 간단한 구현 - 실제로는 더 복잡한 검증이 필요함
    return []


def set_annotation_metadata(target: Any, metadata: AnnotationMetadata):
    """애노테이션 메타데이터 저장"""
    global _annotation_metadata
    if target not in _annotation_metadata:
        _annotation_metadata[target] = []
    _annotation_metadata[target].append(metadata)


def create_annotation_decorator(
    annotation_type: str, target_types: List[str] = None
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
                    f"@{annotation_type} cannot be applied to {target_type}"
                )
            metadata = AnnotationMetadata(
                annotation_type=annotation_type,
                parameters=params,
                target=target,
                target_type=target_type,
            )
            set_annotation_metadata(target, metadata)
            if target_type == "class":
                component_metadata = get_component_metadata(target)
                if not component_metadata:
                    component_metadata = ComponentMetadata(
                        component_id=params.get("name", target.__name__),
                        component_type=target,
                        scope=params.get("scope", ServiceScope.SINGLETON),
                    )
                    set_component_metadata(target, component_metadata)
                component_metadata.add_annotation(metadata)
            return target

        return wrapper

    return decorator


def extract_dependencies(cls: Type) -> List[DependencyMetadata]:
    """클래스에서 의존성 추출"""
    dependencies = []
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

    def __init__(
        self, field_type: Type = None, qualifier: str = None, lazy: bool = False
    ):
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
