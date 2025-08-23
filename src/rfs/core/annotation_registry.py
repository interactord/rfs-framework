"""
Annotation Registry
어노테이션 기반 의존성 주입 컨테이너

기존 StatelessRegistry와 ServiceRegistry를 확장하여
헥사고날 아키텍처 패턴과 어노테이션 기반 구성을 지원
"""

from typing import Dict, Any, Type, List, Optional, Set, Callable
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime

# 기존 레지스트리 import
from .registry import ServiceRegistry, ServiceDefinition, ServiceScope
from .singleton import StatelessRegistry
from .annotations import (
    AnnotationMetadata, AnnotationType, ComponentScope,
    get_annotation_metadata, has_annotation, validate_hexagonal_architecture
)

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
    edges: Dict[str, List[str]] = field(default_factory=dict)  # service_name -> dependencies
    reverse_edges: Dict[str, List[str]] = field(default_factory=dict)  # service_name -> dependents
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
    
    def __init__(self, current_profile: str = "default"):
        super().__init__()
        self.current_profile = current_profile
        
        # 어노테이션 관련 저장소
        self._annotation_metadata: Dict[str, AnnotationMetadata] = {}
        self._ports: Dict[str, Type] = {}  # port_name -> port_class
        self._adapters_by_port: Dict[str, List[str]] = {}  # port_name -> adapter_names
        self._registration_order: List[str] = []
        
        # 통계 정보
        self._registration_stats = {
            "total_registered": 0,
            "by_type": {},
            "by_scope": {},
            "errors": []
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
                errors=[f"Class {cls.__name__} has no RFS annotations"]
            )
        
        metadata = get_annotation_metadata(cls)
        result = RegistrationResult(
            success=False,
            service_name=metadata.name,
            annotation_type=metadata.annotation_type
        )
        
        try:
            # 프로파일 검증
            if metadata.profile and metadata.profile != self.current_profile:
                result.warnings.append(
                    f"Skipping {metadata.name} - profile {metadata.profile} != {self.current_profile}"
                )
                return result
            
            # 타입별 등록 처리
            if metadata.annotation_type == AnnotationType.PORT:
                self._register_port(cls, metadata, result)
            elif metadata.annotation_type == AnnotationType.ADAPTER:
                self._register_adapter(cls, metadata, result)
            else:
                self._register_component(cls, metadata, result)
            
            if result.success:
                self._annotation_metadata[metadata.name] = metadata
                self._registration_order.append(metadata.name)
                self._update_stats(metadata)
                
                logger.debug(f"Successfully registered {metadata.annotation_type.value}: {metadata.name}")
        
        except Exception as e:
            result.errors.append(f"Registration failed: {str(e)}")
            logger.error(f"Failed to register {cls.__name__}: {e}")
        
        return result
    
    def _register_port(self, cls: Type, metadata: AnnotationMetadata, result: RegistrationResult):
        """Port 등록"""
        # Port는 인터페이스이므로 실제 인스턴스를 생성하지 않고 타입만 저장
        self._ports[metadata.name] = cls
        result.success = True
        
        # Adapter 목록 초기화
        if metadata.name not in self._adapters_by_port:
            self._adapters_by_port[metadata.name] = []
    
    def _register_adapter(self, cls: Type, metadata: AnnotationMetadata, result: RegistrationResult):
        """Adapter 등록"""
        if not metadata.port_name:
            result.errors.append("Adapter must specify a port_name")
            return
        
        # Port 존재 확인
        if metadata.port_name not in self._ports:
            result.warnings.append(f"Port {metadata.port_name} not found - will be validated later")
        
        # ServiceRegistry에 등록
        service_scope = metadata.scope.to_service_scope()
        super().register(
            name=metadata.name,
            service_class=cls,
            scope=service_scope,
            dependencies=metadata.dependencies,
            lazy=metadata.lazy
        )
        
        # Port-Adapter 매핑 추가
        if metadata.port_name in self._adapters_by_port:
            self._adapters_by_port[metadata.port_name].append(metadata.name)
        else:
            self._adapters_by_port[metadata.port_name] = [metadata.name]
        
        result.success = True
    
    def _register_component(self, cls: Type, metadata: AnnotationMetadata, result: RegistrationResult):
        """일반 Component, UseCase, Controller 등록"""
        service_scope = metadata.scope.to_service_scope()
        super().register(
            name=metadata.name,
            service_class=cls,
            scope=service_scope,
            dependencies=metadata.dependencies,
            lazy=metadata.lazy
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
        
        # 프로파일 필터링
        if profile:
            filtered_adapters = []
            for adapter_name in adapters:
                metadata = self._annotation_metadata.get(adapter_name)
                if metadata and metadata.profile == profile:
                    filtered_adapters.append(adapter_name)
            adapters = filtered_adapters
        
        if not adapters:
            raise ValueError(f"No adapters found for port '{port_name}' with profile '{profile}'")
        
        # 첫 번째 adapter 반환 (향후 우선순위 기준 개선 예정)
        return super().get(adapters[0])
    
    def auto_register_module(self, module: Any) -> List[RegistrationResult]:
        """
        모듈의 모든 어노테이션 클래스 자동 등록
        
        Args:
            module: 스캔할 모듈
            
        Returns:
            List[RegistrationResult]: 등록 결과들
        """
        results = []
        
        for name in dir(module):
            obj = getattr(module, name)
            
            # 클래스이고 어노테이션이 있는 경우만 처리
            if inspect.isclass(obj) and has_annotation(obj):
                result = self.register_class(obj)
                results.append(result)
        
        return results
    
    def validate_registrations(self) -> List[str]:
        """
        등록된 모든 서비스의 유효성 검증
        
        Returns:
            List[str]: 검증 오류 메시지들
        """
        errors = []
        
        # 1. 헥사고날 아키텍처 규칙 검증
        registered_classes = []
        for metadata in self._annotation_metadata.values():
            registered_classes.append(metadata.target_class)
        
        arch_errors = validate_hexagonal_architecture(registered_classes)
        errors.extend(arch_errors)
        
        # 2. 의존성 검증
        dependency_errors = self._validate_dependencies()
        errors.extend(dependency_errors)
        
        # 3. Port-Adapter 매칭 검증
        port_errors = self._validate_port_adapter_matching()
        errors.extend(port_errors)
        
        return errors
    
    def _validate_dependencies(self) -> List[str]:
        """의존성 유효성 검증"""
        errors = []
        
        for service_name, definition in self._definitions.items():
            for dep_name in definition.dependencies:
                if dep_name not in self._definitions and dep_name not in self._ports:
                    errors.append(f"Service '{service_name}' has unknown dependency '{dep_name}'")
        
        return errors
    
    def _validate_port_adapter_matching(self) -> List[str]:
        """Port-Adapter 매칭 검증"""
        errors = []
        
        for adapter_name, metadata in self._annotation_metadata.items():
            if metadata.annotation_type == AnnotationType.ADAPTER:
                port_name = metadata.port_name
                if port_name not in self._ports:
                    errors.append(f"Adapter '{adapter_name}' references unknown port '{port_name}'")
        
        return errors
    
    def build_dependency_graph(self) -> DependencyGraph:
        """의존성 그래프 구성"""
        graph = DependencyGraph()
        
        # 노드 추가
        for name, metadata in self._annotation_metadata.items():
            graph.nodes[name] = metadata
            graph.edges[name] = metadata.dependencies.copy()
            graph.reverse_edges[name] = []
        
        # 역방향 엣지 구성
        for service_name, dependencies in graph.edges.items():
            for dep_name in dependencies:
                if dep_name in graph.reverse_edges:
                    graph.reverse_edges[dep_name].append(service_name)
        
        # 순환 의존성 검출 (DFS)
        graph.circular_dependencies = self._detect_circular_dependencies(graph.edges)
        
        return graph
    
    def _detect_circular_dependencies(self, edges: Dict[str, List[str]]) -> List[List[str]]:
        """순환 의존성 검출"""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]):
            if node in rec_stack:
                # 순환 발견
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in edges.get(node, []):
                dfs(neighbor, path + [node])
            
            rec_stack.remove(node)
        
        for node in edges:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def _update_stats(self, metadata: AnnotationMetadata):
        """통계 정보 업데이트"""
        self._registration_stats["total_registered"] += 1
        
        # 타입별 통계
        type_name = metadata.annotation_type.value
        self._registration_stats["by_type"][type_name] = \
            self._registration_stats["by_type"].get(type_name, 0) + 1
        
        # 스코프별 통계
        scope_name = metadata.scope.value
        self._registration_stats["by_scope"][scope_name] = \
            self._registration_stats["by_scope"].get(scope_name, 0) + 1
    
    def get_registration_stats(self) -> Dict[str, Any]:
        """등록 통계 조회"""
        return {
            **self._registration_stats,
            "current_profile": self.current_profile,
            "ports": len(self._ports),
            "adapters": sum(len(adapters) for adapters in self._adapters_by_port.values()),
            "registration_order": self._registration_order.copy()
        }
    
    def get_port_info(self) -> Dict[str, Any]:
        """Port 정보 조회"""
        port_info = {}
        
        for port_name, port_class in self._ports.items():
            adapters = self._adapters_by_port.get(port_name, [])
            adapter_details = []
            
            for adapter_name in adapters:
                metadata = self._annotation_metadata.get(adapter_name)
                if metadata:
                    adapter_details.append({
                        "name": adapter_name,
                        "class": metadata.target_class.__name__,
                        "scope": metadata.scope.value,
                        "profile": metadata.profile
                    })
            
            port_info[port_name] = {
                "class": port_class.__name__,
                "adapters": adapter_details,
                "adapter_count": len(adapters)
            }
        
        return port_info
    
    def export_configuration(self) -> Dict[str, Any]:
        """현재 구성을 dict로 export"""
        return {
            "profile": self.current_profile,
            "registration_stats": self.get_registration_stats(),
            "port_info": self.get_port_info(),
            "dependency_graph": {
                "nodes": len(self._annotation_metadata),
                "edges": sum(len(deps) for deps in [
                    metadata.dependencies for metadata in self._annotation_metadata.values()
                ])
            },
            "timestamp": datetime.now().isoformat()
        }


# 전역 어노테이션 레지스트리 인스턴스
_default_annotation_registry: Optional[AnnotationRegistry] = None


def get_annotation_registry(profile: str = "default") -> AnnotationRegistry:
    """전역 어노테이션 레지스트리 조회"""
    global _default_annotation_registry
    
    if _default_annotation_registry is None or _default_annotation_registry.current_profile != profile:
        _default_annotation_registry = AnnotationRegistry(current_profile=profile)
    
    return _default_annotation_registry


def register_classes(*classes: Type) -> List[RegistrationResult]:
    """편의 함수: 여러 클래스를 한 번에 등록"""
    registry = get_annotation_registry()
    results = []
    
    for cls in classes:
        result = registry.register_class(cls)
        results.append(result)
    
    return results


# 기존 StatelessRegistry와의 호환성을 위한 어댑터
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


# 예제 사용법
if __name__ == "__main__":
    # 이전 annotations.py의 예제 클래스들을 사용
    from .annotations import *
    
    # 레지스트리 생성
    registry = AnnotationRegistry(current_profile="production")
    
    # 클래스들 등록 (실제로는 __init__.py나 애플리케이션 시작 시 수행)
    # results = register_classes(UserRepository, PostgresUserRepository, GetUserUseCase, UserController)
    
    # 통계 출력
    # print("Registration Stats:", registry.get_registration_stats())
    # print("Port Info:", registry.get_port_info())
    
    print("✅ AnnotationRegistry implementation complete!")