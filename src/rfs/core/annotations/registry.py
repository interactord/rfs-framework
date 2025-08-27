"""
Annotation Registry - Extended DI Container for RFS Framework

확장된 의존성 주입 컨테이너 - 애노테이션 기반 자동 등록 및 주입
"""

import asyncio
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from ..registry import StatelessRegistry
from ..result import Failure, Result, Success
from .base import (
    ComponentMetadata,
    DependencyMetadata,
    InjectionType,
    ServiceScope,
    _component_metadata,
    get_component_metadata,
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
        self.ports = {}
        self.adapters: Dict[str, List[Type]] = {}
        self.use_cases = {}
        self.controllers = {}
        self.services = {}
        self.repositories = {}
        self.components = {}
        self.singletons = {}
        self.prototypes = {}
        self.request_scoped = {}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.profiles: Set[str] = {"default"}
        self.active_profile = "default"

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
            module = importlib.import_module(module_path)
            if hasattr(module, "__path__"):
                for importer, modname, ispkg in pkgutil.walk_packages(
                    module.__path__, prefix=f"{module_path}."
                ):
                    try:
                        submodule = importlib.import_module(modname)
                        self._register_module_components(submodule)
                    except Exception as e:
                        print(f"Failed to import {modname}: {e}")
            self._register_module_components(module)
        except ImportError as e:
            print(f"Failed to import module {module_path}: {e}")

    def _register_module_components(self, module):
        """모듈 내 컴포넌트 등록"""
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                metadata = get_component_metadata(obj)
                if metadata:
                    self._register_component(obj, metadata)

    def _register_component(self, cls: Type, metadata: ComponentMetadata):
        """컴포넌트 등록"""
        if metadata.profile and metadata.profile not in self.profiles:
            return
        component_id = metadata.component_id
        component_type = metadata.metadata.get("type", "component")
        match component_type:
            case "port":
                self.ports = {**self.ports, component_id: cls}
            case "adapter":
                port_name = metadata.metadata.get("port_name")
                if port_name:
                    # 함수형 패턴: 조건부 업데이트를 한 번의 스프레드 연산으로 처리
                    existing_adapters = self.adapters.get(port_name, [])
                    self.adapters = {
                        **self.adapters,
                        port_name: existing_adapters + [cls],
                    }
            case "use_case":
                self.use_cases = {**self.use_cases, component_id: cls}
            case "controller":
                self.controllers = {**self.controllers, component_id: cls}
            case "service":
                self.services = {**self.services, component_id: cls}
            case "repository":
                self.repositories = {**self.repositories, component_id: cls}
            case _:
                self.components = {**self.components, component_id: cls}
        if metadata.scope == ServiceScope.SINGLETON:
            pass
        elif metadata.scope == ServiceScope.PROTOTYPE:
            self.prototypes = {**self.prototypes, component_id: cls}
        self.dependency_graph = {**self.dependency_graph, component_id: set()}
        for dep in metadata.dependencies:
            self.dependency_graph[component_id].add(dep.name)

    def get_component(self, component_id: str, qualifier=None) -> Result[Any, str]:
        """
        컴포넌트 인스턴스 획득

        Args:
            component_id: 컴포넌트 ID 또는 타입 이름
            qualifier: 한정자 (여러 구현체가 있을 때)

        Returns:
            컴포넌트 인스턴스
        """
        try:
            if component_id in self.singletons:
                return Success(self.singletons[component_id])
            cls = self._find_component_class(component_id, qualifier)
            if not cls:
                return Failure(f"Component not found: {component_id}")
            if self._has_circular_dependency(component_id):
                return Failure(f"Circular dependency detected for {component_id}")
            instance = self._create_instance(cls)
            metadata = get_component_metadata(cls)
            if metadata:
                if metadata.scope == ServiceScope.SINGLETON:
                    self.singletons = {**self.singletons, component_id: instance}
                if metadata.post_construct:
                    metadata.post_construct(instance)
            return Success(instance)
        except Exception as e:
            return Failure(f"Failed to get component {component_id}: {e}")

    def _find_component_class(
        self, component_id: str, qualifier=None
    ) -> Optional[Type]:
        """컴포넌트 클래스 찾기"""
        for storage in [
            self.ports,
            self.use_cases,
            self.controllers,
            self.services,
            self.repositories,
            self.components,
        ]:
            if component_id in storage:
                return storage[component_id]
        if component_id in self.adapters:
            adapters = self.adapters[component_id]
            if qualifier:
                for adapter in adapters:
                    metadata = get_component_metadata(adapter)
                    if metadata and metadata.metadata.get("qualifier") == qualifier:
                        return adapter
            for adapter in adapters:
                metadata = get_component_metadata(adapter)
                if metadata and metadata.primary:
                    return adapter
            if adapters:
                return adapters[0]
        for cls in _component_metadata.keys():
            if cls.__name__ == component_id:
                return cls
        return None

    def _create_instance(self, cls: Type) -> Any:
        """인스턴스 생성 및 의존성 주입"""
        metadata = get_component_metadata(cls)
        if not metadata:
            return cls()
        constructor_deps = {}
        for dep in metadata.constructor_dependencies:
            dep_instance = self.get_component(dep.name, dep.qualifier)
            if type(dep_instance).__name__ == "Success":
                constructor_deps = {
                    **constructor_deps,
                    dep.name: {dep.name: dep_instance.value},
                }
            elif dep.required:
                raise ComponentNotFoundError(
                    f"Required dependency {dep.name} not found"
                )
            else:
                constructor_deps = {
                    **constructor_deps,
                    dep.name: {dep.name: dep.default_value},
                }
        instance = cls(**constructor_deps)
        for field_name, dep in metadata.field_dependencies.items():
            dep_instance = self.get_component(dep.name, dep.qualifier)
            if type(dep_instance).__name__ == "Success":
                setattr(instance, field_name, dep_instance.value)
            elif dep.required:
                raise ComponentNotFoundError(
                    f"Required field dependency {dep.name} not found"
                )
        for setter_name, dep in metadata.setter_dependencies.items():
            dep_instance = self.get_component(dep.name, dep.qualifier)
            if type(dep_instance).__name__ == "Success":
                setter = getattr(instance, setter_name)
                setter(dep_instance.value)
        return instance

    def _has_circular_dependency(
        self, component_id: str, visited: Optional[Set[str]] = None
    ) -> bool:
        """순환 의존성 체크"""
        if visited is None:
            visited: Set[Any] = set()
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
            if hasattr(cls, "__annotations__"):
                for field_name, field_type in cls.__annotations__.items():
                    if hasattr(cls, field_name):
                        field_value = getattr(cls, field_name)
                        if hasattr(field_value, "_autowired"):
                            qualifier = getattr(field_value, "_qualifier", None)
                            dep_instance = self.get_component(
                                field_type.__name__, qualifier
                            )
                            if type(dep_instance).__name__ == "Success":
                                setattr(obj, f"_{field_name}", dep_instance.value)
            return Success(obj)
        except Exception as e:
            return Failure(f"Failed to auto-wire object: {e}")

    def get_all_components(self, component_type=None) -> List[Any]:
        """
        특정 타입의 모든 컴포넌트 조회

        Args:
            component_type: 컴포넌트 타입 ("port", "adapter", "use_case", etc.)

        Returns:
            컴포넌트 인스턴스 리스트
        """
        components = []
        match component_type:
            case "port":
                storage = self.ports
            case "adapter":
                storage = {}
                for adapters in self.adapters.values():
                    for adapter in adapters:
                        metadata = get_component_metadata(adapter)
                        if metadata:
                            storage = {
                                **storage,
                                metadata.component_id: {metadata.component_id: adapter},
                            }
            case "use_case":
                storage = self.use_cases
            case "controller":
                storage = self.controllers
            case "service":
                storage = self.services
            case "repository":
                storage = self.repositories
            case _:
                storage = self.components
        for component_id, cls in storage.items():
            result = self.get_component(component_id)
            if type(result).__name__ == "Success":
                components = components + [result.value]
        return components

    def set_active_profile(self, profile: str):
        """활성 프로필 설정"""
        self.active_profile = profile
        self.profiles.add(profile)

    def clear_request_scope(self):
        """요청 스코프 클리어"""
        request_scoped = {}

    def destroy(self):
        """컨테이너 종료 및 리소스 정리"""
        for instance in self.singletons.values():
            cls = type(instance)
            metadata = get_component_metadata(cls)
            if metadata and metadata.pre_destroy:
                metadata.pre_destroy(instance)
        singletons = {}
        request_scoped = {}


_annotation_registry = None


def get_annotation_registry() -> AnnotationRegistry:
    """전역 애노테이션 레지스트리 인스턴스 반환"""
    # global _annotation_registry - removed for functional programming
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


def get_component(component_id: str, qualifier=None) -> Result[Any, str]:
    """컴포넌트 획득 헬퍼"""
    registry = get_annotation_registry()
    return registry.get_component(component_id, qualifier)


def get_all_components(component_type=None) -> List[Any]:
    """모든 컴포넌트 조회 헬퍼"""
    registry = get_annotation_registry()
    return registry.get_all_components(component_type)
