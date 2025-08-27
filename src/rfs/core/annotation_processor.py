"""
Annotation Processor
어노테이션 처리 및 자동 등록 시스템

특징:
- Import time에 어노테이션 클래스 자동 감지 및 등록
- 패키지/모듈 스캔 기능
- 조건부 등록 (프로파일, 환경 기반)
- 등록 순서 최적화 (의존성 순서)
"""

import importlib
import inspect
import logging
import os
import pkgutil
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Type, Union

from .annotation_registry import AnnotationRegistry, RegistrationResult
from .annotations import (
    AnnotationMetadata,
    AnnotationType,
    has_annotation,
    validate_hexagonal_architecture,
)
from .annotations.base import get_component_metadata

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """처리 컨텍스트"""

    profile = "default"
    base_packages: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    auto_register = True
    validate_architecture = True
    resolve_dependencies = True


@dataclass
class ProcessingResult:
    """처리 결과"""

    total_scanned = 0
    total_registered = 0
    successful_registrations: List[str] = field(default_factory=list)
    failed_registrations: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class AnnotationProcessor:
    """
    어노테이션 프로세서

    주요 기능:
    1. 패키지/모듈 자동 스캔
    2. 어노테이션 클래스 감지 및 등록
    3. 의존성 순서 해결
    4. 조건부 등록 (프로파일, 환경)
    5. 아키텍처 유효성 검증
    """

    def __init__(self, registry: AnnotationRegistry = None):
        self.registry = registry or AnnotationRegistry()
        self._discovered_classes = {}
        self._processing_cache = {}

    def scan_package(
        self, package_name: str, context: ProcessingContext
    ) -> ProcessingResult:
        """
        패키지 전체 스캔 및 처리

        Args:
            package_name: 스캔할 패키지 이름
            context: 처리 컨텍스트

        Returns:
            ProcessingResult: 처리 결과
        """
        import time

        start_time = time.time()
        result = ProcessingResult()
        try:
            package = importlib.import_module(package_name)
            package_path = package.__path__
            discovered_modules = []
            for importer, modname, ispkg in pkgutil.walk_packages(
                package_path, prefix=f"{package_name}.", onerror=lambda x: None
            ):
                if self._should_exclude_module(modname, context.exclude_patterns or []):
                    continue
                try:
                    module = importlib.import_module(modname)
                    discovered_modules = discovered_modules + [module]
                except Exception as e:
                    result.warnings = result.warnings + [
                        f"Failed to import module {modname}: {e}"
                    ]
            for module in discovered_modules:
                module_classes = self._discover_classes_in_module(module)
                # 함수형 패턴: update 대신 스프레드 연산자 사용
                self._discovered_classes = {
                    **self._discovered_classes,
                    **module_classes,
                }
                total_scanned = total_scanned + len(module_classes)
            if context.auto_register:
                registration_results = self._register_discovered_classes(context)
                self._process_registration_results(registration_results, result)
            if context.validate_architecture:
                validation_errors = self._validate_architecture()
                result.validation_errors = result.validation_errors + validation_errors
        except Exception as e:
            result.validation_errors = result.validation_errors + [
                f"Package scan failed: {e}"
            ]
            logger.error(f"Failed to scan package {package_name}: {e}")
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def scan_modules(
        self, modules: List[Union[str, Any]], context: ProcessingContext
    ) -> ProcessingResult:
        """
        특정 모듈들 스캔 및 처리

        Args:
            modules: 스캔할 모듈들 (이름 문자열 또는 모듈 객체)
            context: 처리 컨텍스트

        Returns:
            ProcessingResult: 처리 결과
        """
        import time

        start_time = time.time()
        result = ProcessingResult()
        for module_item in modules:
            try:
                if type(module_item).__name__ == "str":
                    module = importlib.import_module(module_item)
                else:
                    module = module_item
                module_classes = self._discover_classes_in_module(module)
                # 함수형 패턴: update 대신 스프레드 연산자 사용
                self._discovered_classes = {
                    **self._discovered_classes,
                    **module_classes,
                }
                total_scanned = total_scanned + len(module_classes)
            except Exception as e:
                result.warnings = result.warnings + [
                    f"Failed to process module {module_item}: {e}"
                ]
        if context.auto_register:
            registration_results = self._register_discovered_classes(context)
            self._process_registration_results(registration_results, result)
        if context.validate_architecture:
            validation_errors = self._validate_architecture()
            result.validation_errors = result.validation_errors + validation_errors
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def process_classes(
        self, classes: List[Type], context: ProcessingContext
    ) -> ProcessingResult:
        """
        특정 클래스들 직접 처리

        Args:
            classes: 처리할 클래스 목록
            context: 처리 컨텍스트

        Returns:
            ProcessingResult: 처리 결과
        """
        import time

        start_time = time.time()
        result = ProcessingResult()
        annotated_classes = {}
        for cls in classes:
            if has_annotation(cls):
                annotated_classes = {
                    **annotated_classes,
                    cls.__name__: {cls.__name__: cls},
                }
        # 함수형 패턴: update 대신 스프레드 연산자 사용
        self._discovered_classes = {**self._discovered_classes, **annotated_classes}
        result.total_scanned = len(annotated_classes)
        if context.auto_register:
            registration_results = self._register_discovered_classes(context)
            self._process_registration_results(registration_results, result)
        if context.validate_architecture:
            validation_errors = self._validate_architecture()
            result.validation_errors = result.validation_errors + validation_errors
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def _discover_classes_in_module(self, module: Any) -> Dict[str, Type]:
        """모듈에서 어노테이션 클래스들 발견"""
        discovered = {}
        for name in dir(module):
            try:
                obj = getattr(module, name)
                if (
                    inspect.isclass(obj)
                    and has_annotation(obj)
                    and (obj.__module__ == module.__name__)
                ):
                    discovered[obj.__name__] = {obj.__name__: obj}
            except Exception as e:
                logger.debug(f"Failed to inspect {name} in {module.__name__}: {e}")
        return discovered

    def _register_discovered_classes(
        self, context: ProcessingContext
    ) -> List[RegistrationResult]:
        """발견된 클래스들을 등록"""
        results = []
        if context.resolve_dependencies:
            ordered_classes = self._resolve_registration_order()
        else:
            ordered_classes = list(self._discovered_classes.values())
        for cls in ordered_classes:
            component_metadata = get_component_metadata(cls)
            if (
                component_metadata
                and component_metadata.profile
                and (component_metadata.profile != context.profile)
            ):
                continue
            result = self.registry.register_class(cls)
            results = results + [result]
        return results

    def _resolve_registration_order(self) -> List[Type]:
        """
        의존성을 고려한 등록 순서 해결 (Topological Sort)
        """
        dependency_graph = defaultdict(list)
        in_degree = defaultdict(int)
        class_by_name = {}
        for cls in self._discovered_classes.values():
            component_metadata = get_component_metadata(cls)
            if not component_metadata:
                continue
            name = component_metadata.component_id
            class_by_name[name] = cls
            # Check if it's a port by looking at metadata
            if component_metadata.metadata.get("type") == "port":
                in_degree[name] = 0
            else:
                deps = [dep.name for dep in component_metadata.dependencies]
                in_degree[name] = len(deps)
                for dep in deps:
                    dependency_graph[dep] = dependency_graph[dep] + [name]
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        ordered_names = []
        while queue:
            current = queue.popleft()
            ordered_names = ordered_names + [current]
            for neighbor in dependency_graph[current]:
                in_degree[neighbor] = in_degree[neighbor] - 1
                if in_degree[neighbor] == 0:
                    queue = queue + [neighbor]
        if len(ordered_names) != len(class_by_name):
            remaining = set(class_by_name.keys()) - set(ordered_names)
            logger.warning(f"Circular dependencies detected in: {remaining}")
            ordered_names = ordered_names + remaining
        ordered_classes = []
        for name in ordered_names:
            if name in class_by_name:
                ordered_classes = ordered_classes + [class_by_name[name]]
        return ordered_classes

    def _validate_architecture(self) -> List[str]:
        """아키텍처 유효성 검증"""
        classes = list(self._discovered_classes.values())
        return validate_hexagonal_architecture(classes)

    def _should_exclude_module(
        self, module_name: str, exclude_patterns: List[str]
    ) -> bool:
        """모듈 제외 여부 확인"""
        for pattern in exclude_patterns:
            if pattern in module_name:
                return True
        return False

    def _process_registration_results(
        self, results: List[RegistrationResult], processing_result: ProcessingResult
    ):
        """등록 결과를 ProcessingResult에 반영"""
        for result in results:
            if result.success:
                processing_result.successful_registrations = (
                    processing_result.successful_registrations + [result.service_name]
                )
                total_registered = total_registered + 1
            else:
                processing_result.failed_registrations = (
                    processing_result.failed_registrations + [result.service_name]
                )
                processing_result.validation_errors = (
                    processing_result.validation_errors + result.errors
                )
            processing_result.warnings = processing_result.warnings + result.warnings

    def get_discovered_classes(self) -> Dict[str, Type]:
        """발견된 클래스들 조회"""
        return self._discovered_classes.copy()

    def clear_cache(self):
        """캐시 정리"""
        self._discovered_classes = {}
        self._processing_cache = {}


def auto_scan_package(
    package_name: str, profile="default", exclude_patterns: List[str] = None
) -> ProcessingResult:
    """
    패키지 자동 스캔 편의 함수

    Args:
        package_name: 스캔할 패키지 이름
        profile: 사용할 프로파일
        exclude_patterns: 제외할 패턴들

    Returns:
        ProcessingResult: 처리 결과
    """
    from .annotation_registry import get_annotation_registry

    registry = get_annotation_registry(profile)
    processor = AnnotationProcessor(registry)
    context = ProcessingContext(
        profile=profile,
        exclude_patterns=exclude_patterns or ["test", "__pycache__", ".pyc"],
    )
    return processor.scan_package(package_name, context)


def auto_register_classes(*classes: Type, profile="default") -> ProcessingResult:
    """
    클래스들 자동 등록 편의 함수

    Args:
        classes: 등록할 클래스들
        profile: 사용할 프로파일

    Returns:
        ProcessingResult: 처리 결과
    """
    from .annotation_registry import get_annotation_registry

    registry = get_annotation_registry(profile)
    processor = AnnotationProcessor(registry)
    context = ProcessingContext(profile=profile)
    return processor.process_classes(list(classes), context)


def auto_register(registry: AnnotationRegistry = None):
    """
    클래스 데코레이터: import 시점에 자동 등록

    Example:
        @auto_register()
        @Component(name="email_service")
        class EmailService:
            pass
    """

    def decorator(cls: Type) -> Type:
        if not registry:
            from .annotation_registry import get_annotation_registry

            current_registry = get_annotation_registry()
        else:
            current_registry = registry
        result = current_registry.register_class(cls)
        if not result.success:
            logger.warning(
                f"Auto registration failed for {cls.__name__}: {result.errors}"
            )
        return cls

    return decorator


if __name__ == "__main__":
    from .annotations import *

    @Port(name="test_port")
    class TestPort:
        pass

    @Adapter(port="test_port", name="test_adapter")
    class TestAdapter:
        pass

    @Component(name="test_component", dependencies=["test_adapter"])
    class TestComponent:

        def __init__(self, test_adapter):
            self.test_adapter = test_adapter

    from .annotation_registry import AnnotationRegistry

    registry = AnnotationRegistry()
    processor = AnnotationProcessor(registry)
    context = ProcessingContext(profile="default")
    result = processor.process_classes([TestPort, TestAdapter, TestComponent], context)
    print(
        f"✅ Processed {result.total_scanned} classes, registered {result.total_registered}"
    )
    print(f"Processing time: {result.processing_time_ms:.2f}ms")
    if result.validation_errors:
        print(f"❌ Validation errors: {result.validation_errors}")
    else:
        print("✅ No validation errors")
