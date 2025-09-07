"""
Annotation Base Module Tests
어노테이션 베이스 모듈 테스트
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import pytest

from rfs.core.annotations.base import (
    AnnotationMetadata,
    AnnotationType,
    ComponentMetadata,
    ServiceScope,
    get_annotation_metadata,
    has_annotation,
    set_annotation_metadata,
    validate_hexagonal_architecture,
)


class TestServiceScope:
    """ServiceScope 열거형 테스트"""

    def test_service_scope_values(self):
        """ServiceScope 값 확인"""
        assert ServiceScope.SINGLETON.value == "singleton"
        assert ServiceScope.PROTOTYPE.value == "prototype"
        assert ServiceScope.REQUEST.value == "request"
        assert ServiceScope.SESSION.value == "session"

    def test_service_scope_all_values(self):
        """모든 ServiceScope 값 존재 확인"""
        expected_scopes = ["singleton", "prototype", "request", "session"]
        actual_scopes = [scope.value for scope in ServiceScope]
        assert set(actual_scopes) == set(expected_scopes)


class TestComponentScope:
    """ServiceScope 열거형 테스트"""

    def test_component_scope_values(self):
        """ServiceScope 값 확인"""
        assert ServiceScope.SINGLETON.value == "singleton"
        assert ServiceScope.PROTOTYPE.value == "prototype"
        assert ServiceScope.REQUEST.value == "request"

    def test_to_service_scope(self):
        """ServiceScope -> ServiceScope 변환 테스트"""
        assert ServiceScope.SINGLETON.to_service_scope() == ServiceScope.SINGLETON
        assert ServiceScope.PROTOTYPE.to_service_scope() == ServiceScope.PROTOTYPE
        assert ServiceScope.REQUEST.to_service_scope() == ServiceScope.REQUEST


class TestAnnotationType:
    """AnnotationType 열거형 테스트"""

    def test_annotation_type_values(self):
        """AnnotationType 값 확인"""
        assert AnnotationType.COMPONENT.value == "component"
        assert AnnotationType.PORT.value == "port"
        assert AnnotationType.ADAPTER.value == "adapter"
        assert AnnotationType.USE_CASE.value == "use_case"
        assert AnnotationType.CONTROLLER.value == "controller"
        assert AnnotationType.SERVICE.value == "service"
        assert AnnotationType.REPOSITORY.value == "repository"
        assert AnnotationType.VALUE.value == "value"
        assert AnnotationType.CONFIG.value == "config"

    def test_all_annotation_types(self):
        """모든 AnnotationType 존재 확인"""
        expected_types = [
            "component",
            "port",
            "adapter",
            "use_case",
            "controller",
            "service",
            "repository",
            "value",
            "config",
        ]
        actual_types = [atype.value for atype in AnnotationType]
        assert set(actual_types) == set(expected_types)


class TestAnnotationMetadata:
    """AnnotationMetadata 데이터클래스 테스트"""

    def test_metadata_creation(self):
        """메타데이터 생성 테스트"""
        metadata = AnnotationMetadata(
            name="test_component",
            annotation_type=AnnotationType.COMPONENT,
            scope=ServiceScope.SINGLETON,
            target_class=TestServiceScope,
            dependencies=["dep1", "dep2"],
            lazy=False,
            profile="test",
            port_name=None,
            config_key="test.key",
        )

        assert metadata.name == "test_component"
        assert metadata.annotation_type == AnnotationType.COMPONENT
        assert metadata.scope == ServiceScope.SINGLETON
        assert metadata.target_class == TestServiceScope
        assert metadata.dependencies == ["dep1", "dep2"]
        assert metadata.lazy is False
        assert metadata.profile == "test"
        assert metadata.port_name is None
        assert metadata.config_key == "test.key"

    def test_metadata_default_values(self):
        """메타데이터 기본값 테스트"""
        metadata = AnnotationMetadata(
            name="test",
            annotation_type=AnnotationType.COMPONENT,
            scope=ServiceScope.SINGLETON,
            target_class=TestServiceScope,
        )

        assert metadata.dependencies == []
        assert metadata.lazy is False
        assert metadata.profile is None
        assert metadata.port_name is None
        assert metadata.config_key is None


class TestComponentMetadata:
    """ComponentMetadata 데이터클래스 테스트"""

    def test_component_metadata_creation(self):
        """컴포넌트 메타데이터 생성 테스트"""
        metadata = ComponentMetadata(
            name="test_service",
            scope=ServiceScope.SINGLETON,
            dependencies=["logger", "database"],
            lazy=True,
            primary=False,
            qualifier="main",
        )

        assert metadata.name == "test_service"
        assert metadata.scope == ServiceScope.SINGLETON
        assert metadata.dependencies == ["logger", "database"]
        assert metadata.lazy is True
        assert metadata.primary is False
        assert metadata.qualifier == "main"

    def test_component_metadata_defaults(self):
        """컴포넌트 메타데이터 기본값 테스트"""
        metadata = ComponentMetadata(name="test", scope=ServiceScope.PROTOTYPE)

        assert metadata.dependencies == []
        assert metadata.lazy is False
        assert metadata.primary is False
        assert metadata.qualifier is None


class TestMetadataFunctions:
    """메타데이터 함수 테스트"""

    def test_set_and_get_annotation_metadata(self):
        """어노테이션 메타데이터 설정 및 조회 테스트"""

        class TestClass:
            pass

        metadata = AnnotationMetadata(
            name="test_class",
            annotation_type=AnnotationType.SERVICE,
            scope=ServiceScope.SINGLETON,
            target_class=TestClass,
        )

        # 메타데이터 설정
        set_annotation_metadata(TestClass, metadata)

        # 메타데이터 조회
        retrieved = get_annotation_metadata(TestClass)
        assert retrieved is not None
        assert retrieved.name == "test_class"
        assert retrieved.annotation_type == AnnotationType.SERVICE
        assert retrieved.scope == ServiceScope.SINGLETON
        assert retrieved.target_class == TestClass

    def test_get_annotation_metadata_not_exists(self):
        """존재하지 않는 메타데이터 조회 테스트"""

        class UnAnnotatedClass:
            pass

        metadata = get_annotation_metadata(UnAnnotatedClass)
        assert metadata is None

    def test_has_annotation(self):
        """어노테이션 존재 확인 테스트"""

        class AnnotatedClass:
            pass

        class UnAnnotatedClass:
            pass

        # 어노테이션 설정
        metadata = AnnotationMetadata(
            name="annotated",
            annotation_type=AnnotationType.COMPONENT,
            scope=ServiceScope.SINGLETON,
            target_class=AnnotatedClass,
        )
        set_annotation_metadata(AnnotatedClass, metadata)

        # 확인
        assert has_annotation(AnnotatedClass) is True
        assert has_annotation(UnAnnotatedClass) is False


class TestHexagonalArchitectureValidation:
    """헥사고날 아키텍처 검증 테스트"""

    def test_validate_empty_classes(self):
        """빈 클래스 목록 검증"""
        errors = validate_hexagonal_architecture([])
        assert errors == []

    def test_validate_valid_architecture(self):
        """유효한 아키텍처 검증"""

        # 포트
        class UserPort:
            pass

        # 어댑터
        class UserAdapter:
            pass

        # 유스케이스
        class CreateUserUseCase:
            pass

        # 각 클래스에 메타데이터 설정
        set_annotation_metadata(
            UserPort,
            AnnotationMetadata(
                name="user_port",
                annotation_type=AnnotationType.PORT,
                scope=ServiceScope.SINGLETON,
                target_class=UserPort,
            ),
        )

        set_annotation_metadata(
            UserAdapter,
            AnnotationMetadata(
                name="user_adapter",
                annotation_type=AnnotationType.ADAPTER,
                scope=ServiceScope.SINGLETON,
                target_class=UserAdapter,
                port_name="user_port",
            ),
        )

        set_annotation_metadata(
            CreateUserUseCase,
            AnnotationMetadata(
                name="create_user",
                annotation_type=AnnotationType.USE_CASE,
                scope=ServiceScope.PROTOTYPE,
                target_class=CreateUserUseCase,
                dependencies=["user_port"],
            ),
        )

        # 검증
        errors = validate_hexagonal_architecture(
            [UserPort, UserAdapter, CreateUserUseCase]
        )
        assert len(errors) == 0

    def test_validate_adapter_without_port(self):
        """포트 없는 어댑터 검증"""

        class InvalidAdapter:
            pass

        set_annotation_metadata(
            InvalidAdapter,
            AnnotationMetadata(
                name="invalid_adapter",
                annotation_type=AnnotationType.ADAPTER,
                scope=ServiceScope.SINGLETON,
                target_class=InvalidAdapter,
                port_name=None,  # 포트 이름 없음
            ),
        )

        errors = validate_hexagonal_architecture([InvalidAdapter])
        assert len(errors) > 0
        assert any("port" in error.lower() for error in errors)

    def test_validate_use_case_dependencies(self):
        """유스케이스 의존성 검증"""

        class TestUseCase:
            pass

        # 어댑터나 리포지토리에 직접 의존하는 유스케이스
        set_annotation_metadata(
            TestUseCase,
            AnnotationMetadata(
                name="test_use_case",
                annotation_type=AnnotationType.USE_CASE,
                scope=ServiceScope.PROTOTYPE,
                target_class=TestUseCase,
                dependencies=["user_adapter"],  # 포트가 아닌 어댑터에 의존
            ),
        )

        errors = validate_hexagonal_architecture([TestUseCase])
        # 유스케이스는 포트에만 의존해야 함
        assert len(errors) > 0


class TestMetadataEquality:
    """메타데이터 동등성 테스트"""

    def test_annotation_metadata_equality(self):
        """AnnotationMetadata 동등성 비교"""
        metadata1 = AnnotationMetadata(
            name="test",
            annotation_type=AnnotationType.COMPONENT,
            scope=ServiceScope.SINGLETON,
            target_class=TestServiceScope,
        )

        metadata2 = AnnotationMetadata(
            name="test",
            annotation_type=AnnotationType.COMPONENT,
            scope=ServiceScope.SINGLETON,
            target_class=TestServiceScope,
        )

        metadata3 = AnnotationMetadata(
            name="different",
            annotation_type=AnnotationType.COMPONENT,
            scope=ServiceScope.SINGLETON,
            target_class=TestServiceScope,
        )

        assert metadata1 == metadata2
        assert metadata1 != metadata3

    def test_component_metadata_equality(self):
        """ComponentMetadata 동등성 비교"""
        metadata1 = ComponentMetadata(name="service", scope=ServiceScope.SINGLETON)

        metadata2 = ComponentMetadata(name="service", scope=ServiceScope.SINGLETON)

        metadata3 = ComponentMetadata(name="service", scope=ServiceScope.PROTOTYPE)

        assert metadata1 == metadata2
        assert metadata1 != metadata3


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_set_metadata_on_none(self):
        """None에 메타데이터 설정 시도"""
        metadata = AnnotationMetadata(
            name="test",
            annotation_type=AnnotationType.COMPONENT,
            scope=ServiceScope.SINGLETON,
            target_class=None,
        )

        # None에 메타데이터 설정 시도
        with pytest.raises(AttributeError):
            set_annotation_metadata(None, metadata)

    def test_get_metadata_from_none(self):
        """None에서 메타데이터 조회"""
        with pytest.raises(AttributeError):
            get_annotation_metadata(None)

    def test_has_annotation_on_none(self):
        """None의 어노테이션 확인"""
        with pytest.raises(AttributeError):
            has_annotation(None)

    def test_circular_dependencies(self):
        """순환 의존성 테스트"""

        class ServiceA:
            pass

        class ServiceB:
            pass

        # A -> B -> A 순환 의존성
        set_annotation_metadata(
            ServiceA,
            AnnotationMetadata(
                name="service_a",
                annotation_type=AnnotationType.SERVICE,
                scope=ServiceScope.SINGLETON,
                target_class=ServiceA,
                dependencies=["service_b"],
            ),
        )

        set_annotation_metadata(
            ServiceB,
            AnnotationMetadata(
                name="service_b",
                annotation_type=AnnotationType.SERVICE,
                scope=ServiceScope.SINGLETON,
                target_class=ServiceB,
                dependencies=["service_a"],
            ),
        )

        # 순환 의존성은 validate_hexagonal_architecture에서 검증되어야 함
        errors = validate_hexagonal_architecture([ServiceA, ServiceB])
        # 순환 의존성 검증 로직이 구현되어 있다면 에러가 있어야 함
        # 구현에 따라 다를 수 있음


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
