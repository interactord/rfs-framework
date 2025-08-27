"""
Annotation-based Dependency Injection and Architecture Support for RFS Framework

애노테이션 기반 의존성 주입 및 헥사고날 아키텍처 지원
"""

from .base import (
    AnnotationMetadata,
    AnnotationType,
    ComponentMetadata,
    ServiceScope,
    get_annotation_metadata,
    has_annotation,
    set_annotation_metadata,
    validate_hexagonal_architecture,
)
from .di import (
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


def is_port(cls):
    """포트 인터페이스 확인"""
    return getattr(cls, "_is_port", False)


from .processor import (
    AnnotationProcessor,
    process_annotations,
    register_component,
    resolve_dependencies,
)
from .registry import (
    AnnotationRegistry,
    auto_wire,
    get_all_components,
    get_annotation_registry,
    get_component,
    scan_and_register,
)

__all__ = [
    # Base
    "ServiceScope",
    "AnnotationType",
    "AnnotationMetadata",
    "ComponentMetadata",
    "get_annotation_metadata",
    "has_annotation",
    "set_annotation_metadata",
    "validate_hexagonal_architecture",
    "is_port",
    # DI Annotations
    "Component",
    "Port",
    "Adapter",
    "UseCase",
    "Controller",
    "Service",
    "Repository",
    "Injectable",
    "Autowired",
    "Qualifier",
    "Scope",
    "Primary",
    "Lazy",
    "Value",
    "ConfigProperty",
    # Registry
    "AnnotationRegistry",
    "get_annotation_registry",
    "scan_and_register",
    "auto_wire",
    "get_component",
    "get_all_components",
    # Processor
    "AnnotationProcessor",
    "process_annotations",
    "register_component",
    "resolve_dependencies",
]
