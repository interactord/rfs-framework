"""
Annotation Registry - Extended DI Container for RFS Framework

확장된 의존성 주입 컨테이너 - 애노테이션 기반 자동 등록 및 주입
"""

import asyncio
import importlib
import inspect
import pkgutil
from typing import Type, Any, Dict, List, Optional, Set, Callable, Union
from pathlib import Path

from ...core import Result, Success, Failure
from ..registry import StatelessRegistry
from .base import (
    ServiceScope,
    InjectionType,
    ComponentMetadata,
    DependencyMetadata,
    get_component_metadata,
    _component_metadata
)


class CircularDependencyError(Exception):
    """순환 의존성 에러"""
    pass


class ComponentNotFoundError(Exception):
    """컴포넌트를 찾을 수 없음"""
    pass


class AnnotationRegistry(StatelessRegistry):
    """
    애노테이션 기반 확장 DI 컨테이너
    
    Features:
    - 자동 컴포넌트 스캔 및 등록
    - 의존성 자동 주입
    - Hexagonal Architecture 지원
    - 라이프사이클 관리
    """
    
    def __init__(self):
        super().__init__()
        
        # Component storage by type
        self.ports: Dict[str, Type] = {}  # Port interfaces
        self.adapters: Dict[str, List[Type]] = {}  # Port -> Adapters mapping
        self.use_cases: Dict[str, Type] = {}  # Use cases
        self.controllers: Dict[str, Type] = {}  # Controllers
        self.services: Dict[str, Type] = {}  # Services
        self.repositories: Dict[str, Type] = {}  # Repositories
        self.components: Dict[str, Type] = {}  # General components
        
        # Instance cache
        self.singletons: Dict[str, Any] = {}  # Singleton instances
        self.prototypes: Dict[str, Type] = {}  # Prototype classes
        self.request_scoped: Dict[str, Any] = {}  # Request-scoped instances
        
        # Dependency graph
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        # Configuration
        self.profiles: Set[str] = {"default"}
        self.active_profile: str = "default"
        
    def scan_and_register(self, *module_paths: str):
        """
        모듈 경로를 스캔하여 애노테이션이 있는 클래스 자동 등록
        
        Args:
            module_paths: 스캔할 모듈 경로들 (예: "myapp.services", "myapp.repositories")
        """
        for module_path in module_paths:
            self._scan_module(module_path)
    
    def _scan_module(self, module_path: str):
        """모듈 스캔 및 컴포넌트 등록"""
        try:
            # 모듈 임포트
            module = importlib.import_module(module_path)
            
            # 서브모듈 찾기
            if hasattr(module, "__path__"):
                for importer, modname, ispkg in pkgutil.walk_packages(
                    module.__path__,
                    prefix=f"{module_path}."
                ):
                    try:
                        submodule = importlib.import_module(modname)
                        self._register_module_components(submodule)
                    except Exception as e:
                        print(f"Failed to import {modname}: {e}")
            
            # 현재 모듈의 컴포넌트 등록
            self._register_module_components(module)
            
        except ImportError as e:
            print(f"Failed to import module {module_path}: {e}")
    
    def _register_module_components(self, module):
        """모듈 내 컴포넌트 등록"""
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                # 컴포넌트 메타데이터 확인
                metadata = get_component_metadata(obj)
                if metadata:
                    self._register_component(obj, metadata)
    
    def _register_component(self, cls: Type, metadata: ComponentMetadata):
        """컴포넌트 등록"""
        # 프로필 확인
        if metadata.profile and metadata.profile not in self.profiles:
            return  # 활성 프로필이 아니면 스킵
        
        component_id = metadata.component_id
        component_type = metadata.metadata.get("type", "component")
        
        # 타입별 저장소에 등록
        if component_type == "port":
            self.ports[component_id] = cls
        elif component_type == "adapter":
            port_name = metadata.metadata.get("port_name")
            if port_name:
                if port_name not in self.adapters:
                    self.adapters[port_name] = []
                self.adapters[port_name].append(cls)
        elif component_type == "use_case":
            self.use_cases[component_id] = cls
        elif component_type == "controller":
            self.controllers[component_id] = cls
        elif component_type == "service":
            self.services[component_id] = cls
        elif component_type == "repository":
            self.repositories[component_id] = cls
        else:
            self.components[component_id] = cls
        
        # 스코프별 저장
        if metadata.scope == ServiceScope.SINGLETON:
            # 나중에 인스턴스 생성
            pass
        elif metadata.scope == ServiceScope.PROTOTYPE:
            self.prototypes[component_id] = cls
        
        # 의존성 그래프 구성
        self.dependency_graph[component_id] = set()
        for dep in metadata.dependencies:
            self.dependency_graph[component_id].add(dep.name)
    
    def get_component(
        self,
        component_id: str,
        qualifier: Optional[str] = None
    ) -> Result[Any, str]:
        """
        컴포넌트 인스턴스 획득
        
        Args:
            component_id: 컴포넌트 ID 또는 타입 이름
            qualifier: 한정자 (여러 구현체가 있을 때)
        
        Returns:
            컴포넌트 인스턴스
        """
        try:
            # 이미 생성된 싱글톤 확인
            if component_id in self.singletons:
                return Success(self.singletons[component_id])
            
            # 컴포넌트 클래스 찾기
            cls = self._find_component_class(component_id, qualifier)
            if not cls:
                return Failure(f"Component not found: {component_id}")
            
            # 순환 의존성 체크
            if self._has_circular_dependency(component_id):
                return Failure(f"Circular dependency detected for {component_id}")
            
            # 인스턴스 생성
            instance = self._create_instance(cls)
            
            # 메타데이터 확인
            metadata = get_component_metadata(cls)
            if metadata:
                # 싱글톤인 경우 캐시
                if metadata.scope == ServiceScope.SINGLETON:
                    self.singletons[component_id] = instance
                
                # 라이프사이클 콜백 실행
                if metadata.post_construct:
                    metadata.post_construct(instance)
            
            return Success(instance)
            
        except Exception as e:
            return Failure(f"Failed to get component {component_id}: {e}")
    
    def _find_component_class(
        self,
        component_id: str,
        qualifier: Optional[str] = None
    ) -> Optional[Type]:
        """컴포넌트 클래스 찾기"""
        # 직접 ID로 찾기
        for storage in [
            self.ports, self.use_cases, self.controllers,
            self.services, self.repositories, self.components
        ]:
            if component_id in storage:
                return storage[component_id]
        
        # 어댑터에서 찾기 (포트 이름으로)
        if component_id in self.adapters:
            adapters = self.adapters[component_id]
            
            if qualifier:
                # 한정자로 필터링
                for adapter in adapters:
                    metadata = get_component_metadata(adapter)
                    if metadata and metadata.metadata.get("qualifier") == qualifier:
                        return adapter
            
            # Primary 찾기
            for adapter in adapters:
                metadata = get_component_metadata(adapter)
                if metadata and metadata.primary:
                    return adapter
            
            # 첫 번째 어댑터 반환
            if adapters:
                return adapters[0]
        
        # 타입 이름으로 찾기
        for cls in _component_metadata.keys():
            if cls.__name__ == component_id:
                return cls
        
        return None
    
    def _create_instance(self, cls: Type) -> Any:
        """인스턴스 생성 및 의존성 주입"""
        metadata = get_component_metadata(cls)
        if not metadata:
            # 메타데이터 없으면 단순 생성
            return cls()
        
        # 생성자 의존성 해결
        constructor_deps = {}
        for dep in metadata.constructor_dependencies:
            dep_instance = self.get_component(dep.name, dep.qualifier)
            if isinstance(dep_instance, Success):
                constructor_deps[dep.name] = dep_instance.value
            elif dep.required:
                raise ComponentNotFoundError(f"Required dependency {dep.name} not found")
            else:
                constructor_deps[dep.name] = dep.default_value
        
        # 인스턴스 생성
        instance = cls(**constructor_deps)
        
        # 필드 주입
        for field_name, dep in metadata.field_dependencies.items():
            dep_instance = self.get_component(dep.name, dep.qualifier)
            if isinstance(dep_instance, Success):
                setattr(instance, field_name, dep_instance.value)
            elif dep.required:
                raise ComponentNotFoundError(f"Required field dependency {dep.name} not found")
        
        # 세터 주입
        for setter_name, dep in metadata.setter_dependencies.items():
            dep_instance = self.get_component(dep.name, dep.qualifier)
            if isinstance(dep_instance, Success):
                setter = getattr(instance, setter_name)
                setter(dep_instance.value)
        
        return instance
    
    def _has_circular_dependency(
        self,
        component_id: str,
        visited: Optional[Set[str]] = None
    ) -> bool:
        """순환 의존성 체크"""
        if visited is None:
            visited = set()
        
        if component_id in visited:
            return True
        
        visited.add(component_id)
        
        if component_id in self.dependency_graph:
            for dep_id in self.dependency_graph[component_id]:
                if self._has_circular_dependency(dep_id, visited.copy()):
                    return True
        
        return False
    
    def auto_wire(self, obj: Any) -> Result[Any, str]:
        """
        객체의 @Autowired 필드 자동 주입
        
        Args:
            obj: 주입할 객체
        
        Returns:
            주입된 객체
        """
        try:
            cls = type(obj)
            
            # 필드 애노테이션 확인
            if hasattr(cls, "__annotations__"):
                for field_name, field_type in cls.__annotations__.items():
                    if hasattr(cls, field_name):
                        field_value = getattr(cls, field_name)
                        
                        # @Autowired 확인
                        if hasattr(field_value, "_autowired"):
                            # 의존성 주입
                            qualifier = getattr(field_value, "_qualifier", None)
                            dep_instance = self.get_component(
                                field_type.__name__,
                                qualifier
                            )
                            
                            if isinstance(dep_instance, Success):
                                setattr(obj, f"_{field_name}", dep_instance.value)
            
            return Success(obj)
            
        except Exception as e:
            return Failure(f"Failed to auto-wire object: {e}")
    
    def get_all_components(self, component_type: Optional[str] = None) -> List[Any]:
        """
        특정 타입의 모든 컴포넌트 조회
        
        Args:
            component_type: 컴포넌트 타입 ("port", "adapter", "use_case", etc.)
        
        Returns:
            컴포넌트 인스턴스 리스트
        """
        components = []
        
        if component_type == "port":
            storage = self.ports
        elif component_type == "adapter":
            # 모든 어댑터 수집
            storage = {}
            for adapters in self.adapters.values():
                for adapter in adapters:
                    metadata = get_component_metadata(adapter)
                    if metadata:
                        storage[metadata.component_id] = adapter
        elif component_type == "use_case":
            storage = self.use_cases
        elif component_type == "controller":
            storage = self.controllers
        elif component_type == "service":
            storage = self.services
        elif component_type == "repository":
            storage = self.repositories
        else:
            storage = self.components
        
        for component_id, cls in storage.items():
            result = self.get_component(component_id)
            if isinstance(result, Success):
                components.append(result.value)
        
        return components
    
    def set_active_profile(self, profile: str):
        """활성 프로필 설정"""
        self.active_profile = profile
        self.profiles.add(profile)
    
    def clear_request_scope(self):
        """요청 스코프 클리어"""
        self.request_scoped.clear()
    
    def destroy(self):
        """컨테이너 종료 및 리소스 정리"""
        # PreDestroy 콜백 실행
        for instance in self.singletons.values():
            cls = type(instance)
            metadata = get_component_metadata(cls)
            if metadata and metadata.pre_destroy:
                metadata.pre_destroy(instance)
        
        # 캐시 클리어
        self.singletons.clear()
        self.request_scoped.clear()


# 전역 레지스트리 인스턴스
_annotation_registry: Optional[AnnotationRegistry] = None


def get_annotation_registry() -> AnnotationRegistry:
    """전역 애노테이션 레지스트리 인스턴스 반환"""
    global _annotation_registry
    if _annotation_registry is None:
        _annotation_registry = AnnotationRegistry()
    return _annotation_registry


def scan_and_register(*module_paths: str):
    """모듈 스캔 및 자동 등록 헬퍼"""
    registry = get_annotation_registry()
    registry.scan_and_register(*module_paths)


def auto_wire(obj: Any) -> Result[Any, str]:
    """객체 자동 주입 헬퍼"""
    registry = get_annotation_registry()
    return registry.auto_wire(obj)


def get_component(
    component_id: str,
    qualifier: Optional[str] = None
) -> Result[Any, str]:
    """컴포넌트 획득 헬퍼"""
    registry = get_annotation_registry()
    return registry.get_component(component_id, qualifier)


def get_all_components(component_type: Optional[str] = None) -> List[Any]:
    """모든 컴포넌트 조회 헬퍼"""
    registry = get_annotation_registry()
    return registry.get_all_components(component_type)