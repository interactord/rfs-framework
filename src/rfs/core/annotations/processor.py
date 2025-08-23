"""
Annotation Processor for RFS Framework

애노테이션 처리 엔진 - 런타임 및 컴파일 타임 처리
"""

import ast
import inspect
import sys
from typing import Type, Any, Dict, List, Optional, Callable
from pathlib import Path

from .base import (
    ComponentMetadata,
    DependencyMetadata,
    AnnotationMetadata,
    InjectionType,
    get_component_metadata,
    set_component_metadata,
    get_annotation_metadata
)
from .registry import get_annotation_registry


class AnnotationProcessor:
    """
    애노테이션 처리기
    
    Features:
    - 런타임 애노테이션 처리
    - 의존성 분석 및 검증
    - 메타데이터 생성
    - 자동 등록
    """
    
    def __init__(self, registry=None):
        self.registry = registry or get_annotation_registry()
        self.processed_classes: Set[Type] = set()
        
    def process_class(self, cls: Type) -> ComponentMetadata:
        """
        클래스의 애노테이션 처리
        
        Args:
            cls: 처리할 클래스
            
        Returns:
            컴포넌트 메타데이터
        """
        # 이미 처리된 클래스는 스킵
        if cls in self.processed_classes:
            return get_component_metadata(cls)
        
        self.processed_classes.add(cls)
        
        # 기존 메타데이터 확인
        metadata = get_component_metadata(cls)
        if not metadata:
            # 메타데이터 생성
            metadata = self._create_metadata(cls)
        
        # 의존성 분석
        self._analyze_dependencies(cls, metadata)
        
        # 라이프사이클 콜백 분석
        self._analyze_lifecycle(cls, metadata)
        
        # 레지스트리에 등록
        self.registry._register_component(cls, metadata)
        
        return metadata
    
    def _create_metadata(self, cls: Type) -> ComponentMetadata:
        """컴포넌트 메타데이터 생성"""
        # 클래스 애노테이션 확인
        annotations = get_annotation_metadata(cls)
        
        # 기본 메타데이터 생성
        metadata = ComponentMetadata(
            component_id=cls.__name__,
            component_type=cls
        )
        
        # 애노테이션에서 정보 추출
        for annotation in annotations:
            if annotation.annotation_type == "Component":
                metadata.component_id = annotation.get_param("name", cls.__name__)
                metadata.scope = annotation.get_param("scope")
                metadata.lazy_init = annotation.get_param("lazy", False)
            elif annotation.annotation_type == "Port":
                metadata.component_id = f"port:{annotation.get_param('name', cls.__name__)}"
                metadata.metadata["type"] = "port"
            elif annotation.annotation_type == "Adapter":
                port_name = annotation.get_param("port")
                metadata.component_id = f"adapter:{cls.__name__}"
                metadata.metadata["type"] = "adapter"
                metadata.metadata["port_name"] = port_name
                metadata.scope = annotation.get_param("scope")
                metadata.primary = annotation.get_param("primary", False)
                metadata.profile = annotation.get_param("profile")
            elif annotation.annotation_type == "UseCase":
                metadata.component_id = f"use_case:{annotation.get_param('name', cls.__name__)}"
                metadata.metadata["type"] = "use_case"
                metadata.scope = annotation.get_param("scope")
            elif annotation.annotation_type == "Controller":
                metadata.component_id = f"controller:{annotation.get_param('name', cls.__name__)}"
                metadata.metadata["type"] = "controller"
                metadata.metadata["route"] = annotation.get_param("route")
                metadata.metadata["methods"] = annotation.get_param("method")
            elif annotation.annotation_type == "Service":
                metadata.component_id = f"service:{annotation.get_param('name', cls.__name__)}"
                metadata.metadata["type"] = "service"
                metadata.scope = annotation.get_param("scope")
            elif annotation.annotation_type == "Repository":
                metadata.component_id = f"repository:{annotation.get_param('name', cls.__name__)}"
                metadata.metadata["type"] = "repository"
                metadata.scope = annotation.get_param("scope")
        
        set_component_metadata(cls, metadata)
        return metadata
    
    def _analyze_dependencies(self, cls: Type, metadata: ComponentMetadata):
        """의존성 분석"""
        # 생성자 분석
        if hasattr(cls, "__init__"):
            self._analyze_constructor(cls, metadata)
        
        # 필드 분석
        self._analyze_fields(cls, metadata)
        
        # 세터 분석
        self._analyze_setters(cls, metadata)
    
    def _analyze_constructor(self, cls: Type, metadata: ComponentMetadata):
        """생성자 의존성 분석"""
        sig = inspect.signature(cls.__init__)
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            # 타입 힌트 확인
            if param.annotation != inspect.Parameter.empty:
                dep = DependencyMetadata(
                    name=param_name,
                    type=param.annotation,
                    required=param.default == inspect.Parameter.empty,
                    injection_type=InjectionType.CONSTRUCTOR
                )
                
                # 기본값이 있으면 저장
                if param.default != inspect.Parameter.empty:
                    dep.default_value = param.default
                
                metadata.add_dependency(dep)
    
    def _analyze_fields(self, cls: Type, metadata: ComponentMetadata):
        """필드 의존성 분석"""
        # 클래스 애노테이션 확인
        if hasattr(cls, "__annotations__"):
            for field_name, field_type in cls.__annotations__.items():
                # 필드 값 확인
                if hasattr(cls, field_name):
                    field_value = getattr(cls, field_name)
                    
                    # @Autowired 확인
                    if hasattr(field_value, "_autowired"):
                        dep = DependencyMetadata(
                            name=field_name,
                            type=field_type,
                            injection_type=InjectionType.FIELD,
                            qualifier=getattr(field_value, "_qualifier", None),
                            lazy=getattr(field_value, "_lazy", False)
                        )
                        metadata.add_dependency(dep)
                    
                    # @Value 확인
                    elif hasattr(field_value, "_value_key"):
                        # 설정 값 주입으로 처리
                        metadata.metadata.setdefault("config_values", {})[field_name] = {
                            "key": field_value._value_key,
                            "default": field_value._value_default
                        }
    
    def _analyze_setters(self, cls: Type, metadata: ComponentMetadata):
        """세터 의존성 분석"""
        for name, method in inspect.getmembers(cls, inspect.ismethod):
            # @Autowired 세터 메서드 확인
            if hasattr(method, "_autowired_setter"):
                sig = inspect.signature(method)
                params = list(sig.parameters.values())
                
                if len(params) == 2:  # self + parameter
                    param = params[1]
                    if param.annotation != inspect.Parameter.empty:
                        dep = DependencyMetadata(
                            name=name,
                            type=param.annotation,
                            injection_type=InjectionType.SETTER
                        )
                        metadata.add_dependency(dep)
    
    def _analyze_lifecycle(self, cls: Type, metadata: ComponentMetadata):
        """라이프사이클 콜백 분석"""
        for name, method in inspect.getmembers(cls):
            if hasattr(method, "_lifecycle_callback"):
                callback_type = method._lifecycle_callback
                
                if callback_type == "post_construct":
                    metadata.post_construct = method
                elif callback_type == "pre_destroy":
                    metadata.pre_destroy = method
    
    def process_module(self, module_name: str):
        """
        모듈의 모든 클래스 처리
        
        Args:
            module_name: 처리할 모듈 이름
        """
        try:
            module = sys.modules.get(module_name)
            if not module:
                module = __import__(module_name, fromlist=[""])
            
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj):
                    # 애노테이션이 있는 클래스만 처리
                    if get_annotation_metadata(obj) or get_component_metadata(obj):
                        self.process_class(obj)
                        
        except Exception as e:
            print(f"Failed to process module {module_name}: {e}")
    
    def validate_dependencies(self, cls: Type) -> List[str]:
        """
        의존성 검증
        
        Args:
            cls: 검증할 클래스
            
        Returns:
            검증 오류 메시지 리스트
        """
        errors = []
        metadata = get_component_metadata(cls)
        
        if not metadata:
            return errors
        
        # 순환 의존성 체크
        if self._check_circular_dependency(metadata.component_id, set()):
            errors.append(f"Circular dependency detected for {metadata.component_id}")
        
        # 필수 의존성 체크
        for dep in metadata.dependencies:
            if dep.required:
                # 의존성이 등록되어 있는지 확인
                dep_result = self.registry.get_component(dep.name)
                if not dep_result or isinstance(dep_result, Failure):
                    errors.append(f"Required dependency {dep.name} not found for {metadata.component_id}")
        
        return errors
    
    def _check_circular_dependency(
        self,
        component_id: str,
        visited: Set[str]
    ) -> bool:
        """순환 의존성 체크"""
        if component_id in visited:
            return True
        
        visited.add(component_id)
        
        # 컴포넌트의 의존성 확인
        for cls in [*self.registry.components.values(),
                    *self.registry.services.values(),
                    *self.registry.repositories.values()]:
            metadata = get_component_metadata(cls)
            if metadata and metadata.component_id == component_id:
                for dep in metadata.dependencies:
                    if self._check_circular_dependency(dep.name, visited.copy()):
                        return True
                break
        
        return False


# 전역 프로세서 인스턴스
_processor: Optional[AnnotationProcessor] = None


def get_annotation_processor() -> AnnotationProcessor:
    """전역 애노테이션 프로세서 인스턴스 반환"""
    global _processor
    if _processor is None:
        _processor = AnnotationProcessor()
    return _processor


def process_annotations(cls: Type) -> ComponentMetadata:
    """클래스 애노테이션 처리 헬퍼"""
    processor = get_annotation_processor()
    return processor.process_class(cls)


def register_component(cls: Type):
    """컴포넌트 등록 헬퍼"""
    processor = get_annotation_processor()
    metadata = processor.process_class(cls)
    return cls


def resolve_dependencies(obj: Any) -> Result[Any, str]:
    """의존성 해결 헬퍼"""
    from .registry import auto_wire
    return auto_wire(obj)


def validate_configuration() -> List[str]:
    """
    전체 설정 검증
    
    Returns:
        검증 오류 메시지 리스트
    """
    errors = []
    processor = get_annotation_processor()
    registry = get_annotation_registry()
    
    # 모든 컴포넌트 검증
    all_components = []
    for storage in [
        registry.components,
        registry.services,
        registry.repositories,
        registry.use_cases,
        registry.controllers
    ]:
        all_components.extend(storage.values())
    
    for cls in all_components:
        component_errors = processor.validate_dependencies(cls)
        errors.extend(component_errors)
    
    return errors