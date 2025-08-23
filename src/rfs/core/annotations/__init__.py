"""
Annotation-based Dependency Injection and Architecture Support for RFS Framework

애노테이션 기반 의존성 주입 및 헥사고날 아키텍처 지원
"""

from .base import (
    ServiceScope,
    AnnotationMetadata,
    AnnotationType,
    ComponentMetadata,
    get_annotation_metadata,
    set_annotation_metadata
)

from .di import (
    Component,
    Port,
    Adapter,
    UseCase,
    Controller,
    Service,
    Repository,
    Injectable,
    Autowired,
    Qualifier,
    Scope,
    Primary,
    Lazy,
    Value,
    ConfigProperty
)

from .registry import (
    AnnotationRegistry,
    get_annotation_registry,
    scan_and_register,
    auto_wire,
    get_component,
    get_all_components
)

from .processor import (
    AnnotationProcessor,
    process_annotations,
    register_component,
    resolve_dependencies
)

__all__ = [
    # Base
    "ServiceScope",
    "AnnotationMetadata",
    "ComponentMetadata",
    "get_annotation_metadata",
    "set_annotation_metadata",
    
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
    "resolve_dependencies"
]