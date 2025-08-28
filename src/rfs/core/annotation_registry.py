"""
Annotation Registry
어노테이션 기반 의존성 주입 컨테이너

기존 StatelessRegistry와 ServiceRegistry를 확장하여
헥사고날 아키텍처 패턴과 어노테이션 기반 구성을 지원
"""

import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime
from functools import reduce
from typing import Any, Callable, Dict, List, Optional, Set, Type

from .annotations import (
    AnnotationMetadata,
)
from .annotations.base import (
    AnnotationType,
    ServiceScope,
    get_component_metadata,
    has_annotation,
)
from .registry import ServiceDefinition, ServiceRegistry
from .singleton import StatelessRegistry

logger = logging.getLogger(__name__)


@dataclass
class RegistrationResult:
    """등록 결과 정보"""

    success: bool
    service_name: str
    annotation_type: AnnotationType
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class DependencyGraph:
    """의존성 그래프 정보"""

    nodes: Dict[str, AnnotationMetadata] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)
    reverse_edges: Dict[str, List[str]] = field(default_factory=dict)
    circular_dependencies: List[List[str]] = field(default_factory=list)


class AnnotationRegistry(ServiceRegistry):
    """
    어노테이션 기반 의존성 주입 레지스트리

    기존 ServiceRegistry를 확장하여 어노테이션 처리 기능 추가:
    - 헥사고날 아키텍처 패턴 지원
    - 자동 의존성 해결
    - Port-Adapter 바인딩
    - 프로파일 기반 구성
    """

    def __init__(self, current_profile="default"):
        super().__init__()
        self.current_profile = current_profile
        self._annotation_metadata = {}
        self._ports = {}
        self._adapters_by_port: Dict[str, List[str]] = {}
        self._registration_order = []
        self._registration_stats = {
            "total_registered": 0,
            "by_type": {},
            "by_scope": {},
            "errors": [],
        }

    def register_class(self, cls: Type) -> RegistrationResult:
        """
        어노테이션이 있는 클래스를 자동 등록

        Args:
            cls: 등록할 클래스

        Returns:
            RegistrationResult: 등록 결과
        """
        if not has_annotation(cls):
            return RegistrationResult(
                success=False,
                service_name=cls.__name__,
                annotation_type=AnnotationType.COMPONENT,
                errors=[f"Class {cls.__name__} has no RFS annotations"],
            )
        component_metadata = get_component_metadata(cls)
        if not component_metadata:
            return RegistrationResult(
                success=False,
                service_name=cls.__name__,
                annotation_type=AnnotationType.COMPONENT,
                errors=[f"Class {cls.__name__} has no component metadata"],
            )

        # Extract the annotation type from metadata
        annotation_type = AnnotationType.COMPONENT
        if component_metadata.metadata.get("type") == "port":
            annotation_type = AnnotationType.PORT
        elif component_metadata.metadata.get("type") == "adapter":
            annotation_type = AnnotationType.ADAPTER
        elif component_metadata.metadata.get("type") == "use_case":
            annotation_type = AnnotationType.USE_CASE
        elif component_metadata.metadata.get("type") == "controller":
            annotation_type = AnnotationType.CONTROLLER
        elif component_metadata.metadata.get("type") == "service":
            annotation_type = AnnotationType.SERVICE
        elif component_metadata.metadata.get("type") == "repository":
            annotation_type = AnnotationType.REPOSITORY

        result = RegistrationResult(
            success=False,
            service_name=component_metadata.component_id,
            annotation_type=annotation_type,
        )
        try:
            if (
                component_metadata.profile
                and component_metadata.profile != self.current_profile
            ):
                result.warnings = result.warnings + [
                    f"Skipping {component_metadata.component_id} - profile {component_metadata.profile} != {self.current_profile}"
                ]
                return result
            match annotation_type:
                case AnnotationType.PORT:
                    self._register_port(cls, component_metadata, result)
                case AnnotationType.ADAPTER:
                    self._register_adapter(cls, component_metadata, result)
                case _:
                    self._register_component(cls, component_metadata, result)
            if result.success:
                # Store component metadata for future reference
                self._annotation_metadata[component_metadata.component_id] = (
                    component_metadata
                )
                self._registration_order = self._registration_order + [
                    component_metadata.component_id
                ]
                self._update_stats(component_metadata, annotation_type)
                logger.debug(
                    f"Successfully registered {annotation_type.value}: {component_metadata.component_id}"
                )
        except Exception as e:
            result.errors = result.errors + [f"Registration failed: {str(e)}"]
            logger.error(f"Failed to register {cls.__name__}: {e}")
        return result

    def _register_port(self, cls: Type, component_metadata, result: RegistrationResult):
        """Port 등록"""
        port_name = component_metadata.component_id
        self._ports = {**self._ports, port_name: cls}
        result.success = True
        if port_name not in self._adapters_by_port:
            self._adapters_by_port = {**self._adapters_by_port, port_name: []}

    def _register_adapter(
        self, cls: Type, component_metadata, result: RegistrationResult
    ):
        """Adapter 등록 - 함수형 패턴 적용"""
        port_name = component_metadata.metadata.get("port_name")
        if not port_name:
            result.errors = result.errors + ["Adapter must specify a port_name"]
            return
        if port_name not in self._ports:
            result.warnings = result.warnings + [
                f"Port {port_name} not found - will be validated later"
            ]

        dependencies = [dep.name for dep in component_metadata.dependencies]
        super().register(
            name=component_metadata.component_id,
            service_class=cls,
            scope=component_metadata.scope,
            dependencies=dependencies,
            lazy=component_metadata.lazy_init,
        )

        # 함수형 패턴: 조건부 업데이트를 삼항 연산자와 스프레드로 처리
        existing_adapters = self._adapters_by_port.get(port_name, [])
        self._adapters_by_port = {
            **self._adapters_by_port,
            port_name: existing_adapters + [component_metadata.component_id],
        }
        result.success = True

    def _register_component(
        self, cls: Type, component_metadata, result: RegistrationResult
    ):
        """일반 Component, UseCase, Controller 등록"""
        dependencies = [dep.name for dep in component_metadata.dependencies]
        super().register(
            name=component_metadata.component_id,
            service_class=cls,
            scope=component_metadata.scope,
            dependencies=dependencies,
            lazy=component_metadata.lazy_init,
        )
        result.success = True

    def get_by_port(self, port_name: str, profile: str = None) -> Any:
        """
        Port 이름으로 Adapter 인스턴스 조회

        Args:
            port_name: Port 이름
            profile: 프로파일 필터 (선택사항)

        Returns:
            Adapter 인스턴스
        """
        adapters = self._adapters_by_port.get(port_name, [])
        if not adapters:
            raise ValueError(f"No adapters found for port '{port_name}'")
        if profile:
            # 함수형 패턴: filter를 사용한 어댑터 필터링
            filtered_adapters = list(
                filter(
                    lambda adapter_name: (
                        (metadata := self._annotation_metadata.get(adapter_name))
                        and metadata.profile == profile
                    ),
                    adapters,
                )
            )
            adapters = filtered_adapters
        if not adapters:
            raise ValueError(
                f"No adapters found for port '{port_name}' with profile '{profile}'"
            )
        return super().get(adapters[0])

    def auto_register_module(self, module: Any) -> List[RegistrationResult]:
        """
        모듈의 모든 어노테이션 클래스 자동 등록

        Args:
            module: 스캔할 모듈

        Returns:
            List[RegistrationResult]: 등록 결과들
        """
        # 함수형 패턴: map과 filter 조합
        module_objects = map(lambda name: getattr(module, name), dir(module))
        annotated_classes = filter(
            lambda obj: inspect.isclass(obj) and has_annotation(obj), module_objects
        )
        results = list(map(self.register_class, annotated_classes))
        return results

    def validate_registrations(self) -> List[str]:
        """
        등록된 모든 서비스의 유효성 검증

        Returns:
            List[str]: 검증 오류 메시지들
        """
        # 함수형 패턴: map을 사용한 클래스 추출
        registered_classes = list(
            map(
                lambda metadata: metadata.target_class,
                self._annotation_metadata.values(),
            )
        )

        # 각 검증 함수의 결과를 함수형으로 결합
        validation_functions = [
            lambda: validate_hexagonal_architecture(registered_classes),
            self._validate_dependencies,
            self._validate_port_adapter_matching,
        ]

        # reduce를 사용한 에러 메시지 결합
        from functools import reduce

        errors = reduce(lambda acc, fn: acc + fn(), validation_functions, [])
        return errors

    def _validate_dependencies(self) -> List[str]:
        """의존성 유효성 검증"""

        # 함수형 패턴: 중첩된 리스트 컴프리헨션을 filter와 map으로 변환
        def validate_dependency(service_name: str, dep_name: str) -> Optional[str]:
            if dep_name not in self._definitions and dep_name not in self._ports:
                return f"Service '{service_name}' has unknown dependency '{dep_name}'"
            return None

        # 모든 서비스와 의존성 조합 생성
        dependency_pairs = [
            (service_name, dep_name)
            for service_name, definition in self._definitions.items()
            for dep_name in definition.dependencies
        ]

        # 에러 메시지 필터링
        errors = list(
            filter(
                lambda x: x is not None,
                map(lambda pair: validate_dependency(*pair), dependency_pairs),
            )
        )
        return errors

    def _validate_port_adapter_matching(self) -> List[str]:
        """Port-Adapter 매칭 검증"""
        # 함수형 패턴: filter와 map 조합
        adapter_items = filter(
            lambda item: item[1].annotation_type == AnnotationType.ADAPTER,
            self._annotation_metadata.items(),
        )

        errors = list(
            filter(
                lambda x: x is not None,
                map(
                    lambda item: (
                        f"Adapter '{item[0]}' references unknown port '{item[1].port_name}'"
                        if item[1].port_name not in self._ports
                        else None
                    ),
                    adapter_items,
                ),
            )
        )
        return errors

    def build_dependency_graph(self) -> DependencyGraph:
        """의존성 그래프 구성"""
        graph = DependencyGraph()

        # 함수형 패턴: reduce를 사용한 그래프 노드 구성
        from functools import reduce

        def add_node(acc, item):
            name, metadata = item
            acc["nodes"][name] = metadata
            acc["edges"][name] = metadata.dependencies.copy()
            acc["reverse_edges"][name] = []
            return acc

        initial_graph = {"nodes": {}, "edges": {}, "reverse_edges": {}}
        graph_data = reduce(add_node, self._annotation_metadata.items(), initial_graph)

        graph.nodes = graph_data["nodes"]
        graph.edges = graph_data["edges"]
        graph.reverse_edges = graph_data["reverse_edges"]

        # reverse_edges 구성을 함수형으로
        for service_name, dependencies in graph.edges.items():
            for dep_name in dependencies:
                if dep_name in graph.reverse_edges:
                    graph.reverse_edges[dep_name] = graph.reverse_edges[dep_name] + [
                        service_name
                    ]

        graph.circular_dependencies = self._detect_circular_dependencies(graph.edges)
        return graph

    def _detect_circular_dependencies(
        self, edges: Dict[str, List[str]]
    ) -> List[List[str]]:
        """순환 의존성 검출"""
        visited: Set[Any] = set()
        rec_stack: Set[Any] = set()
        cycles = []

        def dfs(node: str, path: List[str]):
            nonlocal cycles  # cycles를 외부 스코프에서 수정
            if node in rec_stack:
                cycle_start = path.index(node)
                cycles = cycles + [path[cycle_start:] + [node]]
                return
            if node in visited:
                return
            visited.add(node)
            rec_stack.add(node)
            for neighbor in edges.get(node, []):
                dfs(neighbor, path + [node])
            rec_stack.remove(node)  # set의 remove 메서드 사용

        for node in edges:
            if node not in visited:
                dfs(node, [])
        return cycles

    def _update_stats(self, component_metadata, annotation_type: AnnotationType):
        """통계 정보 업데이트"""
        # 함수형 패턴: 불변성을 유지하면서 업데이트
        type_name = annotation_type.value
        scope_name = component_metadata.scope.value

        # 함수형 업데이트 헬퍼
        def update_counter(counter_dict: dict, key: str) -> dict:
            return {**counter_dict, key: counter_dict.get(key, 0) + 1}

        self._registration_stats = {
            **self._registration_stats,
            "total_registered": self._registration_stats["total_registered"] + 1,
            "by_type": update_counter(self._registration_stats["by_type"], type_name),
            "by_scope": update_counter(
                self._registration_stats["by_scope"], scope_name
            ),
        }

    def get_registration_stats(self) -> Dict[str, Any]:
        """등록 통계 조회"""
        return {
            **self._registration_stats,
            "current_profile": self.current_profile,
            "ports": len(self._ports),
            "adapters": sum(
                (len(adapters) for adapters in self._adapters_by_port.values())
            ),
            "registration_order": self._registration_order.copy(),
        }

    def get_port_info(self) -> Dict[str, Any]:
        """Port 정보 조회"""

        # 함수형 패턴: map과 filter를 사용한 포트 정보 구성
        def build_adapter_detail(adapter_name: str) -> Optional[dict]:
            metadata = self._annotation_metadata.get(adapter_name)
            if metadata:
                return {
                    "name": adapter_name,
                    "class": metadata.target_class.__name__,
                    "scope": metadata.scope.value,
                    "profile": metadata.profile,
                }
            return None

        def build_port_entry(port_item: tuple) -> tuple:
            port_name, port_class = port_item
            adapters = self._adapters_by_port.get(port_name, [])

            # adapter_details를 함수형으로 구성
            adapter_details = list(
                filter(lambda x: x is not None, map(build_adapter_detail, adapters))
            )

            return (
                port_name,
                {
                    "class": port_class.__name__,
                    "adapters": adapter_details,
                    "adapter_count": len(adapters),
                },
            )

        # 전체 port_info를 함수형으로 구성
        port_info = dict(map(build_port_entry, self._ports.items()))
        return port_info

    def export_configuration(self) -> Dict[str, Any]:
        """현재 구성을 dict로 export"""
        # 함수형 패턴: map을 사용한 의존성 카운트
        edge_count = sum(
            map(
                lambda metadata: len(metadata.dependencies),
                self._annotation_metadata.values(),
            )
        )

        return {
            "profile": self.current_profile,
            "registration_stats": self.get_registration_stats(),
            "port_info": self.get_port_info(),
            "dependency_graph": {
                "nodes": len(self._annotation_metadata),
                "edges": edge_count,
            },
            "timestamp": datetime.now().isoformat(),
        }


# 싱글톤 패턴을 클래스 속성으로 구현
class RegistryManager:
    """레지스트리 관리자 - 함수형 싱글톤 패턴"""

    _instances: Dict[str, Any] = {}

    @classmethod
    def get_registry(cls, profile="default") -> AnnotationRegistry:
        """프로파일별 레지스트리 조회 또는 생성"""
        if profile not in cls._instances:
            cls._instances[profile] = AnnotationRegistry(current_profile=profile)
        return cls._instances[profile]

    @classmethod
    def clear_registry(cls, profile: str = None):
        """레지스트리 초기화"""
        if profile:
            cls._instances.pop(profile, None)
        else:
            cls._instances.clear()


def get_annotation_registry(profile="default") -> AnnotationRegistry:
    """전역 어노테이션 레지스트리 조회"""
    return RegistryManager.get_registry(profile)


def register_classes(*classes: Type) -> List[RegistrationResult]:
    """편의 함수: 여러 클래스를 한 번에 등록"""
    registry = get_annotation_registry()
    # 함수형 패턴: map을 사용한 등록
    results = list(map(registry.register_class, classes))
    return results


class StatelessRegistryAdapter:
    """기존 StatelessRegistry API와의 호환성 제공"""

    def __init__(self, annotation_registry: AnnotationRegistry):
        self.annotation_registry = annotation_registry

    def get(self, name: str) -> Any:
        """기존 StatelessRegistry.get과 호환"""
        return self.annotation_registry.get(name)

    def list_services(self) -> List[str]:
        """기존 StatelessRegistry.list_services와 호환"""
        return self.annotation_registry.list_services()


if __name__ == "__main__":
    from .annotations import *

    registry = AnnotationRegistry(current_profile="production")
    print("✅ AnnotationRegistry implementation complete!")
