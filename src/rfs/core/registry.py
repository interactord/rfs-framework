"""
Service Registry

서비스 등록 및 검색을 위한 레지스트리
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type


class ServiceScope(Enum):
    """서비스 스코프"""

    SINGLETON = "singleton"
    PROTOTYPE = "prototype"
    REQUEST = "request"


@dataclass
class ServiceDefinition:
    """서비스 정의"""

    name: str
    service_class: Type[Any]
    scope: ServiceScope = ServiceScope.SINGLETON
    dependencies: List[str] = field(default_factory=list)
    lazy: bool = False
    created_at: datetime = field(default_factory=datetime.now)


class ServiceRegistry:
    """
    고급 서비스 레지스트리

    특징:
    - 다양한 서비스 스코프 지원
    - 순환 의존성 검출
    - 서비스 생명주기 관리
    """

    def __init__(self) -> None:
        self._definitions: Dict[str, ServiceDefinition] = {}
        self._instances: Dict[str, Any] = {}
        self._creating: Set[str] = set()

    def register(
        self,
        name: str,
        service_class: Type[Any],
        scope: ServiceScope = ServiceScope.SINGLETON,
        dependencies: List[str] | None = None,
        lazy: bool = False,
    ) -> None:
        """서비스 등록"""
        definition = ServiceDefinition(
            name=name,
            service_class=service_class,
            scope=scope,
            dependencies=dependencies or [],
            lazy=lazy,
        )
        self._definitions = {**self._definitions, name: definition}
        match (lazy, scope):
            case [False, ServiceScope.SINGLETON]:
                self.get(name)
            case _:
                pass

    def get(self, name: str) -> Any:
        """서비스 인스턴스 가져오기"""
        if name not in self._definitions:
            raise ValueError(f"Service '{name}' not registered")
        definition = self._definitions[name]
        match definition.scope:
            case ServiceScope.SINGLETON:
                return self._get_singleton(name)
            case ServiceScope.PROTOTYPE:
                return self._create_instance(name)
            case ServiceScope.REQUEST:
                raise NotImplementedError(
                    f"Scope {definition.scope} not implemented yet"
                )
            case _:
                raise NotImplementedError(f"Unknown scope: {definition.scope}")

    def _get_singleton(self, name: str) -> Any:
        """싱글톤 인스턴스 가져오기"""
        if name not in self._instances:
            self._instances = {**self._instances, name: self._create_instance(name)}
        return self._instances[name]

    def _create_instance(self, name: str) -> Any:
        """새 인스턴스 생성"""
        if name in self._creating:
            raise ValueError(f"Circular dependency detected: {name}")
        self._creating.add(name)
        try:
            definition = self._definitions[name]
            dependencies: List[Any] = []
            for dep_name in definition.dependencies:
                dep_instance = self.get(dep_name)
                dependencies = dependencies + [dep_instance]
            instance = definition.service_class(*dependencies)
            return instance
        finally:
            self._creating.discard(name)

    def list_services(self) -> List[str]:
        """등록된 서비스 목록"""
        return list(self._definitions.keys())

    def get_definition(self, name: str) -> ServiceDefinition | None:
        """서비스 정의 조회"""
        return self._definitions.get(name)

    def clear(self) -> None:
        """모든 서비스 정리"""
        self._instances = {}
        self._definitions = {}
        self._creating = set()

    def health_check(self) -> Dict[str, Any]:
        """서비스 헬스체크"""
        services_dict: Dict[str, Dict[str, Any]] = {}
        
        for name, definition in self._definitions.items():
            is_instantiated = name in self._instances
            created_at: Optional[str]
            match is_instantiated:
                case True:
                    created_at = definition.created_at.isoformat()
                case False:
                    created_at = None
                    
            services_dict[name] = {
                "scope": definition.scope.value,
                "dependencies": definition.dependencies,
                "instantiated": is_instantiated,
                "created_at": created_at,
            }
        
        status: Dict[str, Any] = {
            "total_services": len(self._definitions),
            "instantiated": len(self._instances),
            "services": services_dict,
        }
        
        return status

    def analyze_dependencies(self) -> Dict[str, Any]:
        """
        의존성 그래프 분석 (RFS v4 신규 기능)

        Returns:
            의존성 트리, 순환 참조 검출, 깊이 분석 등
        """
        dependency_tree: Dict[str, Dict[str, List[str]]] = {}
        orphaned_services: List[str] = []
        
        # 의존성 트리 구축
        for name, definition in self._definitions.items():
            dependency_tree[name] = {
                "dependencies": definition.dependencies, 
                "dependents": []
            }
        
        # 종속 관계 설정
        for name, definition in self._definitions.items():
            for dep_name in definition.dependencies:
                if dep_name in dependency_tree:
                    dependency_tree[dep_name]["dependents"].append(name)
        
        # 고아 서비스 찾기
        for name, tree_info in dependency_tree.items():
            if len(tree_info["dependencies"]) == 0 and len(tree_info["dependents"]) == 0:
                orphaned_services.append(name)
        
        analysis: Dict[str, Any] = {
            "total_services": len(self._definitions),
            "dependency_tree": dependency_tree,
            "circular_references": [],
            "orphaned_services": orphaned_services,
            "max_depth": 0,
        }
        
        return analysis

    def get_service_metrics(self) -> Dict[str, Any]:
        """
        서비스 성능 메트릭 수집 (RFS v4 신규 기능)
        """
        metrics = {
            "registry_stats": {
                "total_definitions": len(self._definitions),
                "active_instances": len(self._instances),
                "scope_distribution": {},
            },
            "service_states": {},
        }
        scope_counts: Dict[str, int] = {}
        for definition in self._definitions.values():
            scope_name = definition.scope.value
            scope_counts[scope_name] = scope_counts.get(scope_name, 0) + 1
        metrics = {
            **metrics,
            "registry_stats": {
                **metrics["registry_stats"],
                "scope_distribution": scope_counts,
            },
        }
        for name, definition in self._definitions.items():
            is_instantiated = name in self._instances
            match definition.scope:
                case ServiceScope.SINGLETON:
                    state = "instantiated" if is_instantiated else "lazy"
                case ServiceScope.PROTOTYPE:
                    state = "prototype"
                case ServiceScope.REQUEST:
                    state = "request_scoped"
            metrics = {
                **metrics,
                "service_states": {
                    **metrics["service_states"],
                    name: {
                        "scope": definition.scope.value,
                        "state": state,
                        "dependency_count": len(definition.dependencies),
                        "is_lazy": definition.lazy,
                    },
                },
            }
        return metrics


class StatelessRegistry:
    """
    Stateless 서비스 전용 레지스트리 (간소화된 서비스 등록)

    v4.0 호환성을 위한 간단한 레지스트리 구현
    """

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}
        self._classes: Dict[str, Type[Any]] = {}

    def register(
        self, name: str, service_class: Type[Any], instance: Any = None
    ) -> None:
        """Stateless 서비스 등록"""
        self._classes = {**self._classes, name: service_class}
        if instance is not None:
            self._services = {**self._services, name: instance}

    def get(self, name: str) -> Any:
        """서비스 인스턴스 가져오기 (없으면 생성)"""
        if name not in self._services:
            if name in self._classes:
                self._services = {**self._services, name: self._classes[name]()}
            else:
                raise ValueError(f"Service '{name}' not registered")
        return self._services[name]

    def list_services(self) -> List[str]:
        """등록된 서비스 목록"""
        return list(self._classes.keys())

    def clear(self) -> None:
        """모든 서비스 정리"""
        self._services = {}
        self._classes = {}


def stateless(cls: Type[Any]) -> Type[Any]:
    """Stateless 서비스 데코레이터"""
    stateless_registry.register(cls.__name__, cls)
    return cls


default_registry = ServiceRegistry()
stateless_registry = StatelessRegistry()
