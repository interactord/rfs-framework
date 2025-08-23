"""
Annotation Processor
어노테이션 처리 및 자동 등록 시스템

특징:
- Import time에 어노테이션 클래스 자동 감지 및 등록
- 패키지/모듈 스캔 기능
- 조건부 등록 (프로파일, 환경 기반)
- 등록 순서 최적화 (의존성 순서)
"""

import os
import sys
import importlib
import pkgutil
import inspect
from typing import Dict, Any, Type, List, Optional, Set, Callable, Union, Iterator
from pathlib import Path
import logging
from dataclasses import dataclass
from collections import defaultdict, deque

from .annotations import (
    AnnotationMetadata, AnnotationType, 
    get_annotation_metadata, has_annotation,
    validate_hexagonal_architecture
)
from .annotation_registry import AnnotationRegistry, RegistrationResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """처리 컨텍스트"""
    profile: str = "default"
    base_packages: List[str] = None
    exclude_patterns: List[str] = None
    auto_register: bool = True
    validate_architecture: bool = True
    resolve_dependencies: bool = True


@dataclass 
class ProcessingResult:
    """처리 결과"""
    total_scanned: int = 0
    total_registered: int = 0
    successful_registrations: List[str] = None
    failed_registrations: List[str] = None
    validation_errors: List[str] = None
    warnings: List[str] = None
    processing_time_ms: float = 0.0
    
    def __post_init__(self):
        if self.successful_registrations is None:
            self.successful_registrations = []
        if self.failed_registrations is None:
            self.failed_registrations = []
        if self.validation_errors is None:
            self.validation_errors = []
        if self.warnings is None:
            self.warnings = []


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
        self._discovered_classes: Dict[str, Type] = {}
        self._processing_cache: Dict[str, bool] = {}
        
    def scan_package(self, package_name: str, context: ProcessingContext) -> ProcessingResult:
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
            # 패키지 import
            package = importlib.import_module(package_name)
            package_path = package.__path__
            
            # 모든 모듈 찾기
            discovered_modules = []
            for importer, modname, ispkg in pkgutil.walk_packages(
                package_path, 
                prefix=f"{package_name}.",
                onerror=lambda x: None
            ):
                # 제외 패턴 확인
                if self._should_exclude_module(modname, context.exclude_patterns or []):
                    continue
                    
                try:
                    module = importlib.import_module(modname)
                    discovered_modules.append(module)
                except Exception as e:
                    result.warnings.append(f"Failed to import module {modname}: {e}")
                    
            # 각 모듈에서 클래스 발견
            for module in discovered_modules:
                module_classes = self._discover_classes_in_module(module)
                self._discovered_classes.update(module_classes)
                result.total_scanned += len(module_classes)
            
            # 자동 등록
            if context.auto_register:
                registration_results = self._register_discovered_classes(context)
                self._process_registration_results(registration_results, result)
            
            # 아키텍처 검증
            if context.validate_architecture:
                validation_errors = self._validate_architecture()
                result.validation_errors.extend(validation_errors)
                
        except Exception as e:
            result.validation_errors.append(f"Package scan failed: {e}")
            logger.error(f"Failed to scan package {package_name}: {e}")
        
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result
        
    def scan_modules(self, modules: List[Union[str, Any]], context: ProcessingContext) -> ProcessingResult:
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
                # 모듈 객체 얻기
                if isinstance(module_item, str):
                    module = importlib.import_module(module_item)
                else:
                    module = module_item
                
                # 클래스 발견
                module_classes = self._discover_classes_in_module(module)
                self._discovered_classes.update(module_classes)
                result.total_scanned += len(module_classes)
                
            except Exception as e:
                result.warnings.append(f"Failed to process module {module_item}: {e}")
        
        # 자동 등록
        if context.auto_register:
            registration_results = self._register_discovered_classes(context)
            self._process_registration_results(registration_results, result)
        
        # 아키텍처 검증
        if context.validate_architecture:
            validation_errors = self._validate_architecture()
            result.validation_errors.extend(validation_errors)
            
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result
    
    def process_classes(self, classes: List[Type], context: ProcessingContext) -> ProcessingResult:
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
        
        # 어노테이션 클래스만 필터링
        annotated_classes = {}
        for cls in classes:
            if has_annotation(cls):
                annotated_classes[cls.__name__] = cls
                
        self._discovered_classes.update(annotated_classes)
        result.total_scanned = len(annotated_classes)
        
        # 자동 등록
        if context.auto_register:
            registration_results = self._register_discovered_classes(context)
            self._process_registration_results(registration_results, result)
        
        # 아키텍처 검증
        if context.validate_architecture:
            validation_errors = self._validate_architecture()
            result.validation_errors.extend(validation_errors)
            
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result
    
    def _discover_classes_in_module(self, module: Any) -> Dict[str, Type]:
        """모듈에서 어노테이션 클래스들 발견"""
        discovered = {}
        
        for name in dir(module):
            try:
                obj = getattr(module, name)
                
                # 클래스이고 어노테이션이 있는지 확인
                if (inspect.isclass(obj) and 
                    has_annotation(obj) and
                    obj.__module__ == module.__name__):  # 해당 모듈에서 정의된 클래스만
                    
                    discovered[obj.__name__] = obj
                    
            except Exception as e:
                logger.debug(f"Failed to inspect {name} in {module.__name__}: {e}")
                
        return discovered
    
    def _register_discovered_classes(self, context: ProcessingContext) -> List[RegistrationResult]:
        """발견된 클래스들을 등록"""
        results = []
        
        if context.resolve_dependencies:
            # 의존성 순서로 등록
            ordered_classes = self._resolve_registration_order()
        else:
            # 발견 순서로 등록
            ordered_classes = list(self._discovered_classes.values())
        
        for cls in ordered_classes:
            # 프로파일 필터링
            metadata = get_annotation_metadata(cls)
            if metadata and metadata.profile and metadata.profile != context.profile:
                continue
                
            result = self.registry.register_class(cls)
            results.append(result)
            
        return results
    
    def _resolve_registration_order(self) -> List[Type]:
        """
        의존성을 고려한 등록 순서 해결 (Topological Sort)
        """
        # 의존성 그래프 구성
        dependency_graph = defaultdict(list)
        in_degree = defaultdict(int)
        class_by_name = {}
        
        for cls in self._discovered_classes.values():
            metadata = get_annotation_metadata(cls)
            if not metadata:
                continue
                
            class_by_name[metadata.name] = cls
            
            # Port는 의존성이 없으므로 먼저 처리
            if metadata.annotation_type == AnnotationType.PORT:
                in_degree[metadata.name] = 0
            else:
                in_degree[metadata.name] = len(metadata.dependencies)
                
                for dep in metadata.dependencies:
                    dependency_graph[dep].append(metadata.name)
        
        # Topological Sort (Kahn's algorithm)
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        ordered_names = []
        
        while queue:
            current = queue.popleft()
            ordered_names.append(current)
            
            for neighbor in dependency_graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 순환 의존성 검사
        if len(ordered_names) != len(class_by_name):
            remaining = set(class_by_name.keys()) - set(ordered_names)
            logger.warning(f"Circular dependencies detected in: {remaining}")
            # 순환 의존성이 있는 클래스들도 추가 (순서 보장 안됨)
            ordered_names.extend(remaining)
        
        # 클래스 객체로 변환
        ordered_classes = []
        for name in ordered_names:
            if name in class_by_name:
                ordered_classes.append(class_by_name[name])
                
        return ordered_classes
    
    def _validate_architecture(self) -> List[str]:
        """아키텍처 유효성 검증"""
        classes = list(self._discovered_classes.values())
        return validate_hexagonal_architecture(classes)
    
    def _should_exclude_module(self, module_name: str, exclude_patterns: List[str]) -> bool:
        """모듈 제외 여부 확인"""
        for pattern in exclude_patterns:
            if pattern in module_name:
                return True
        return False
    
    def _process_registration_results(self, results: List[RegistrationResult], 
                                    processing_result: ProcessingResult):
        """등록 결과를 ProcessingResult에 반영"""
        for result in results:
            if result.success:
                processing_result.successful_registrations.append(result.service_name)
                processing_result.total_registered += 1
            else:
                processing_result.failed_registrations.append(result.service_name)
                processing_result.validation_errors.extend(result.errors)
            
            processing_result.warnings.extend(result.warnings)
    
    def get_discovered_classes(self) -> Dict[str, Type]:
        """발견된 클래스들 조회"""
        return self._discovered_classes.copy()
    
    def clear_cache(self):
        """캐시 정리"""
        self._discovered_classes.clear()
        self._processing_cache.clear()


# 편의 함수들
def auto_scan_package(package_name: str, profile: str = "default", 
                     exclude_patterns: List[str] = None) -> ProcessingResult:
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
        exclude_patterns=exclude_patterns or ['test', '__pycache__', '.pyc']
    )
    
    return processor.scan_package(package_name, context)


def auto_register_classes(*classes: Type, profile: str = "default") -> ProcessingResult:
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


# 데코레이터 기반 자동 등록
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
            
        # import 시점에 등록
        result = current_registry.register_class(cls)
        
        if not result.success:
            logger.warning(f"Auto registration failed for {cls.__name__}: {result.errors}")
        
        return cls
    return decorator


# 예제 및 테스트
if __name__ == "__main__":
    # 테스트용 임시 클래스들
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
    
    # 프로세서 테스트
    from .annotation_registry import AnnotationRegistry
    
    registry = AnnotationRegistry()
    processor = AnnotationProcessor(registry)
    
    context = ProcessingContext(profile="default")
    result = processor.process_classes([TestPort, TestAdapter, TestComponent], context)
    
    print(f"✅ Processed {result.total_scanned} classes, registered {result.total_registered}")
    print(f"Processing time: {result.processing_time_ms:.2f}ms")
    
    if result.validation_errors:
        print(f"❌ Validation errors: {result.validation_errors}")
    else:
        print("✅ No validation errors")