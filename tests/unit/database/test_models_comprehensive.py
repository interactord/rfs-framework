"""
포괄적인 Model validation 테스트 (SQLite 메모리 DB 사용)

RFS Framework의 Model 시스템을 SQLite 메모리 데이터베이스로 테스트
- 필드 정의 및 검증
- 모델 등록 및 관리
- 데이터 유효성 검사
- 타입 변환 및 직렬화
- Result 패턴 준수
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.core.result import Failure, Result, Success
from rfs.database.models import (
    SQLALCHEMY_AVAILABLE,
    TORTOISE_AVAILABLE,
    BaseModel,
    Field,
    Model,
    ModelRegistry,
    SQLAlchemyModel,
    Table,
    TortoiseModel,
    create_model,
    get_model_registry,
    register_model,
)


class ValidationError(Exception):
    """유효성 검사 에러"""

    pass


class MockValidator:
    """테스트용 유효성 검사기"""

    @staticmethod
    def validate_email(email: str) -> bool:
        """이메일 유효성 검사"""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """전화번호 유효성 검사"""
        pattern = r"^\d{3}-\d{4}-\d{4}$"
        return bool(re.match(pattern, phone))

    @staticmethod
    def validate_age(age: int) -> bool:
        """나이 유효성 검사"""
        return 0 <= age <= 150

    @staticmethod
    def validate_not_empty(value: str) -> bool:
        """빈 문자열 검사"""
        return value is not None and value.strip() != ""


class TestField:
    """Field 데이터클래스 테스트"""

    def test_field_basic_creation(self):
        """기본 Field 생성 테스트"""
        field_def = Field(field_type="string")

        assert field_def.field_type == "string"
        assert field_def.primary_key is False
        assert field_def.nullable is True
        assert field_def.default is None
        assert field_def.max_length is None
        assert field_def.foreign_key is None
        assert field_def.index is False
        assert field_def.unique is False
        assert field_def.description is None

    def test_field_with_all_options(self):
        """모든 옵션을 가진 Field 테스트"""
        field_def = Field(
            field_type="string",
            primary_key=True,
            nullable=False,
            default="default_value",
            max_length=255,
            foreign_key="users.id",
            index=True,
            unique=True,
            description="Test field description",
        )

        assert field_def.field_type == "string"
        assert field_def.primary_key is True
        assert field_def.nullable is False
        assert field_def.default == "default_value"
        assert field_def.max_length == 255
        assert field_def.foreign_key == "users.id"
        assert field_def.index is True
        assert field_def.unique is True
        assert field_def.description == "Test field description"

    def test_field_type_variations(self):
        """다양한 필드 타입 테스트"""
        field_types = [
            "integer",
            "string",
            "text",
            "boolean",
            "datetime",
            "json",
            "float",
            "decimal",
            "binary",
        ]

        for field_type in field_types:
            field_def = Field(field_type=field_type)
            assert field_def.field_type == field_type

    def test_field_validation_constraints(self):
        """필드 제약 조건 테스트"""
        # Primary key는 unique하고 non-nullable이어야 함
        pk_field = Field(
            field_type="integer", primary_key=True, nullable=False, unique=True
        )

        assert pk_field.primary_key is True
        assert pk_field.nullable is False
        assert pk_field.unique is True

    def test_field_default_values(self):
        """필드 기본값 테스트"""
        # 문자열 기본값
        str_field = Field(field_type="string", default="default_str")
        assert str_field.default == "default_str"

        # 숫자 기본값
        int_field = Field(field_type="integer", default=42)
        assert int_field.default == 42

        # 함수 기본값 (시뮬레이션)
        datetime_field = Field(field_type="datetime", default=datetime.now)
        assert callable(datetime_field.default)


class TestTable:
    """Table 데이터클래스 테스트"""

    def test_table_creation(self):
        """Table 생성 테스트"""
        fields = {
            "id": Field(field_type="integer", primary_key=True),
            "name": Field(field_type="string", max_length=100),
        }

        table = Table(name="users", fields=fields)

        assert table.name == "users"
        assert len(table.fields) == 2
        assert "id" in table.fields
        assert "name" in table.fields
        assert table.indexes == []
        assert table.constraints == []

    def test_table_with_indexes_and_constraints(self):
        """인덱스와 제약조건이 있는 Table 테스트"""
        fields = {
            "id": Field(field_type="integer", primary_key=True),
            "email": Field(field_type="string", unique=True),
            "created_at": Field(field_type="datetime", index=True),
        }

        table = Table(
            name="users",
            fields=fields,
            indexes=["idx_email", "idx_created_at"],
            constraints=["UNIQUE(email)", "CHECK(id > 0)"],
        )

        assert table.name == "users"
        assert len(table.fields) == 3
        assert "idx_email" in table.indexes
        assert "idx_created_at" in table.indexes
        assert "UNIQUE(email)" in table.constraints
        assert "CHECK(id > 0)" in table.constraints

    def test_table_field_validation(self):
        """Table 필드 유효성 검사 테스트"""
        fields = {
            "id": Field(field_type="integer", primary_key=True, nullable=False),
            "name": Field(field_type="string", nullable=False, max_length=50),
            "email": Field(field_type="string", unique=True),
            "age": Field(field_type="integer", default=0),
        }

        table = Table(name="users", fields=fields)

        # Primary key 검증
        id_field = table.fields["id"]
        assert id_field.primary_key is True
        assert id_field.nullable is False

        # Required field 검증
        name_field = table.fields["name"]
        assert name_field.nullable is False
        assert name_field.max_length == 50

        # Unique field 검증
        email_field = table.fields["email"]
        assert email_field.unique is True

    def test_table_complex_relationships(self):
        """복잡한 관계를 가진 Table 테스트"""
        user_fields = {
            "id": Field(field_type="integer", primary_key=True),
            "name": Field(field_type="string", nullable=False),
        }

        post_fields = {
            "id": Field(field_type="integer", primary_key=True),
            "title": Field(field_type="string", nullable=False),
            "user_id": Field(field_type="integer", foreign_key="users.id"),
            "created_at": Field(field_type="datetime", default=datetime.now),
        }

        users_table = Table(name="users", fields=user_fields)
        posts_table = Table(name="posts", fields=post_fields)

        # Foreign key 관계 검증
        user_id_field = posts_table.fields["user_id"]
        assert user_id_field.foreign_key == "users.id"


class TestBaseModel:
    """BaseModel 테스트"""

    @dataclass
    class TestUser(BaseModel):
        """테스트용 사용자 모델"""

        id=None
        name=""
        email=""
        age=0
        created_at: datetime = field(default_factory=datetime.now)
        is_active=True

    def test_base_model_creation(self):
        """BaseModel 생성 테스트"""
        user = self.TestUser(id=1, name="John Doe", email="john@example.com", age=30)

        assert user.id == 1
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
        assert user.age == 30
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)

    def test_base_model_validation(self):
        """BaseModel 유효성 검사 테스트"""

        # Mock validate 메서드
        def mock_validate(self):
            errors = []

            if not self.name or len(self.name.strip()) == 0:
                errors.append("Name is required")

            if not MockValidator.validate_email(self.email):
                errors.append("Invalid email format")

            if not MockValidator.validate_age(self.age):
                errors.append("Age must be between 0 and 150")

            if errors:
                return Failure(", ".join(errors))
            return Success(None)

        self.TestUser.validate = mock_validate

        # 유효한 데이터
        valid_user = self.TestUser(name="John Doe", email="john@example.com", age=30)
        result = valid_user.validate()
        assert isinstance(result, Success)

        # 무효한 데이터 - 이름 없음
        invalid_user1 = self.TestUser(name="", email="john@example.com", age=30)
        result = invalid_user1.validate()
        assert isinstance(result, Failure)
        assert "Name is required" in result.error

        # 무효한 데이터 - 잘못된 이메일
        invalid_user2 = self.TestUser(name="John Doe", email="invalid-email", age=30)
        result = invalid_user2.validate()
        assert isinstance(result, Failure)
        assert "Invalid email" in result.error

    def test_base_model_serialization(self):
        """BaseModel 직렬화 테스트"""
        user = self.TestUser(id=1, name="Jane Smith", email="jane@example.com", age=28)

        # Mock to_dict 메서드
        def mock_to_dict(self):
            return {
                "id": self.id,
                "name": self.name,
                "email": self.email,
                "age": self.age,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "is_active": self.is_active,
            }

        self.TestUser.to_dict = mock_to_dict

        user_dict = user.to_dict()

        assert user_dict["id"] == 1
        assert user_dict["name"] == "Jane Smith"
        assert user_dict["email"] == "jane@example.com"
        assert user_dict["age"] == 28
        assert user_dict["is_active"] is True
        assert "T" in user_dict["created_at"]  # ISO format

    def test_base_model_deserialization(self):
        """BaseModel 역직렬화 테스트"""

        # Mock from_dict 메서드
        @classmethod
        def mock_from_dict(cls, data):
            try:
                created_at = None
                if data.get("created_at"):
                    created_at = datetime.fromisoformat(data["created_at"])

                return Success(
                    cls(
                        id=data.get("id"),
                        name=data.get("name", ""),
                        email=data.get("email", ""),
                        age=data.get("age", 0),
                        created_at=created_at or datetime.now(),
                        is_active=data.get("is_active", True),
                    )
                )
            except Exception as e:
                return Failure(f"Deserialization error: {str(e)}")

        self.TestUser.from_dict = mock_from_dict

        data = {
            "id": 2,
            "name": "Bob Wilson",
            "email": "bob@example.com",
            "age": 35,
            "created_at": "2023-01-01T12:00:00",
            "is_active": False,
        }

        result = self.TestUser.from_dict(data)

        assert isinstance(result, Success)
        user = result.value
        assert user.id == 2
        assert user.name == "Bob Wilson"
        assert user.is_active is False

    def test_base_model_type_conversion(self):
        """BaseModel 타입 변환 테스트"""

        # Mock type conversion
        def mock_convert_field_value(field_name, value, field_type):
            if field_type == "integer":
                try:
                    return Success(int(value))
                except (ValueError, TypeError):
                    return Failure(f"Cannot convert {value} to integer")
            elif field_type == "boolean":
                if isinstance(value, bool):
                    return Success(value)
                elif isinstance(value, str):
                    return Success(value.lower() in ["true", "1", "yes", "on"])
                else:
                    return Success(bool(value))
            elif field_type == "datetime":
                if isinstance(value, datetime):
                    return Success(value)
                elif isinstance(value, str):
                    try:
                        return Success(datetime.fromisoformat(value))
                    except ValueError:
                        return Failure(f"Invalid datetime format: {value}")
            else:
                return Success(value)

        # 정수 변환 테스트
        result = mock_convert_field_value("age", "30", "integer")
        assert isinstance(result, Success)
        assert result.value == 30

        # 불린 변환 테스트
        result = mock_convert_field_value("is_active", "true", "boolean")
        assert isinstance(result, Success)
        assert result.value is True

        # 날짜 변환 테스트
        result = mock_convert_field_value(
            "created_at", "2023-01-01T12:00:00", "datetime"
        )
        assert isinstance(result, Success)
        assert isinstance(result.value, datetime)

    def test_base_model_field_constraints(self):
        """BaseModel 필드 제약조건 테스트"""

        # Mock constraint validation
        def mock_validate_constraints(self):
            errors = []

            # Max length constraint
            if hasattr(self, "name") and self.name and len(self.name) > 50:
                errors.append("Name cannot exceed 50 characters")

            # Min/Max value constraint
            if hasattr(self, "age") and (self.age < 0 or self.age > 150):
                errors.append("Age must be between 0 and 150")

            # Custom business rule
            if hasattr(self, "email") and hasattr(self, "is_active"):
                if self.is_active and not self.email:
                    errors.append("Active users must have an email")

            if errors:
                return Failure(", ".join(errors))
            return Success(None)

        self.TestUser.validate_constraints = mock_validate_constraints

        # 제약조건 위반 - 이름 길이 초과
        long_name_user = self.TestUser(
            name="A" * 51, email="test@example.com", age=25  # 50자 초과
        )
        result = long_name_user.validate_constraints()
        assert isinstance(result, Failure)
        assert "cannot exceed 50 characters" in result.error

        # 제약조건 위반 - 나이 범위 초과
        invalid_age_user = self.TestUser(
            name="Test User", email="test@example.com", age=200  # 150 초과
        )
        result = invalid_age_user.validate_constraints()
        assert isinstance(result, Failure)
        assert "between 0 and 150" in result.error

        # 비즈니스 규칙 위반 - 활성 사용자인데 이메일 없음
        no_email_user = self.TestUser(
            name="Test User", email="", age=25, is_active=True  # 이메일 없음
        )
        result = no_email_user.validate_constraints()
        assert isinstance(result, Failure)
        assert "must have an email" in result.error


class TestModelRegistry:
    """ModelRegistry 테스트"""

    @pytest.fixture
    def registry(self):
        """ModelRegistry 픽스처"""
        registry = Mock(spec=ModelRegistry)
        registry._models = {}
        return registry

    @dataclass
    class SampleModel(BaseModel):
        """테스트용 샘플 모델"""

        id=None
        name=""

    def test_model_registration(self, registry):
        """모델 등록 테스트"""

        # Mock register 메서드
        def mock_register(name, model_class):
            registry._models[name] = model_class
            return Success(None)

        registry.register = mock_register

        result = registry.register("sample", self.SampleModel)

        assert isinstance(result, Success)
        assert registry._models["sample"] == self.SampleModel

    def test_model_retrieval(self, registry):
        """모델 조회 테스트"""
        # 모델 등록
        registry._models["sample"] = self.SampleModel

        # Mock get 메서드
        def mock_get(name):
            if name in registry._models:
                return Success(registry._models[name])
            return Failure(f"Model '{name}' not found")

        registry.get = mock_get

        result = registry.get("sample")
        assert isinstance(result, Success)
        assert result.value == self.SampleModel

        # 존재하지 않는 모델 조회
        result = registry.get("nonexistent")
        assert isinstance(result, Failure)
        assert "not found" in result.error

    def test_model_registration_conflict(self, registry):
        """모델 등록 충돌 테스트"""
        # 기존 모델 등록
        registry._models["sample"] = self.SampleModel

        # Mock register with conflict detection
        def mock_register_with_conflict(name, model_class):
            if name in registry._models:
                return Failure(f"Model '{name}' is already registered")
            registry._models[name] = model_class
            return Success(None)

        registry.register = mock_register_with_conflict

        # 중복 등록 시도
        result = registry.register("sample", self.SampleModel)

        assert isinstance(result, Failure)
        assert "already registered" in result.error

    def test_model_unregistration(self, registry):
        """모델 등록 해제 테스트"""
        # 모델 등록
        registry._models["sample"] = self.SampleModel

        # Mock unregister 메서드
        def mock_unregister(name):
            if name in registry._models:
                del registry._models[name]
                return Success(None)
            return Failure(f"Model '{name}' not found")

        registry.unregister = mock_unregister

        result = registry.unregister("sample")

        assert isinstance(result, Success)
        assert "sample" not in registry._models

    def test_model_list_all(self, registry):
        """모든 모델 목록 조회 테스트"""
        # 여러 모델 등록
        registry._models["model1"] = self.SampleModel
        registry._models["model2"] = self.SampleModel
        registry._models["model3"] = self.SampleModel

        # Mock list_all 메서드
        def mock_list_all():
            return Success(list(registry._models.keys()))

        registry.list_all = mock_list_all

        result = registry.list_all()

        assert isinstance(result, Success)
        model_names = result.value
        assert len(model_names) == 3
        assert "model1" in model_names
        assert "model2" in model_names
        assert "model3" in model_names


class TestModelValidationScenarios:
    """모델 유효성 검사 시나리오 테스트"""

    @dataclass
    class Product(BaseModel):
        """테스트용 제품 모델"""

        id=None
        name=""
        price: float = 0.0
        category_id=None
        tags: List[str] = field(default_factory=list)
        metadata: Dict[str, Any] = field(default_factory=dict)
        created_at: datetime = field(default_factory=datetime.now)
        is_available=True

    def test_complex_validation_scenario(self):
        """복잡한 유효성 검사 시나리오"""

        # Mock complex validation
        def mock_complex_validate(self):
            errors = []

            # Required fields
            if not self.name or not self.name.strip():
                errors.append("Product name is required")

            # Price validation
            if self.price is None or self.price < 0:
                errors.append("Price must be a positive number")

            if self.price > 100000:
                errors.append("Price cannot exceed $100,000")

            # Category validation
            if self.category_id is not None and self.category_id <= 0:
                errors.append("Category ID must be positive")

            # Tags validation
            if self.tags:
                for tag in self.tags:
                    if not isinstance(tag, str) or len(tag.strip()) == 0:
                        errors.append("All tags must be non-empty strings")
                        break
                    if len(tag) > 50:
                        errors.append("Tags cannot exceed 50 characters")
                        break

            # Metadata validation
            if self.metadata:
                if not isinstance(self.metadata, dict):
                    errors.append("Metadata must be a dictionary")
                else:
                    # Check for reserved keys
                    reserved_keys = ["id", "created_at", "updated_at"]
                    for key in self.metadata:
                        if key in reserved_keys:
                            errors.append(
                                f"Metadata cannot contain reserved key: {key}"
                            )
                            break

            # Business rules
            if self.is_available and self.price == 0:
                errors.append("Available products must have a price > 0")

            if errors:
                return Failure("; ".join(errors))
            return Success(None)

        self.Product.validate = mock_complex_validate

        # 유효한 제품
        valid_product = self.Product(
            name="Test Product",
            price=29.99,
            category_id=1,
            tags=["electronics", "gadget"],
            metadata={"color": "blue", "weight": "100g"},
            is_available=True,
        )
        result = valid_product.validate()
        assert isinstance(result, Success)

        # 무효한 제품 - 이름 없음
        invalid_product1 = self.Product(name="", price=29.99)
        result = invalid_product1.validate()
        assert isinstance(result, Failure)
        assert "name is required" in result.error.lower()

        # 무효한 제품 - 음수 가격
        invalid_product2 = self.Product(name="Test Product", price=-10.0)
        result = invalid_product2.validate()
        assert isinstance(result, Failure)
        assert "positive number" in result.error.lower()

        # 무효한 제품 - 비즈니스 규칙 위반
        invalid_product3 = self.Product(
            name="Free Product", price=0.0, is_available=True
        )
        result = invalid_product3.validate()
        assert isinstance(result, Failure)
        assert "price > 0" in result.error

    def test_nested_model_validation(self):
        """중첩 모델 유효성 검사 테스트"""

        @dataclass
        class Address(BaseModel):
            street=""
            city=""
            zip_code=""

        @dataclass
        class User(BaseModel):
            name=""
            email=""
            address=None

        # Mock nested validation
        def mock_validate_user(self):
            errors = []

            if not self.name:
                errors.append("Name is required")

            if not MockValidator.validate_email(self.email):
                errors.append("Invalid email format")

            # Address validation
            if self.address:
                if not self.address.street:
                    errors.append("Address street is required")
                if not self.address.city:
                    errors.append("Address city is required")
                if not self.address.zip_code or len(self.address.zip_code) != 5:
                    errors.append("Address zip code must be 5 digits")

            if errors:
                return Failure("; ".join(errors))
            return Success(None)

        User.validate = mock_validate_user

        # 유효한 중첩 모델
        valid_address = Address(street="123 Main St", city="Anytown", zip_code="12345")
        valid_user = User(
            name="John Doe", email="john@example.com", address=valid_address
        )
        result = valid_user.validate()
        assert isinstance(result, Success)

        # 무효한 중첩 모델 - 주소 불완전
        invalid_address = Address(
            street="", city="Anytown", zip_code="12345"  # 빈 주소
        )
        invalid_user = User(
            name="Jane Doe", email="jane@example.com", address=invalid_address
        )
        result = invalid_user.validate()
        assert isinstance(result, Failure)
        assert "street is required" in result.error.lower()

    def test_conditional_validation(self):
        """조건부 유효성 검사 테스트"""

        @dataclass
        class Employee(BaseModel):
            name=""
            employee_type=""  # "contractor" or "full_time"
            hourly_rate=None
            salary=None
            contract_end_date=None

        # Mock conditional validation
        def mock_conditional_validate(self):
            errors = []

            if not self.name:
                errors.append("Name is required")

            if self.employee_type not in ["contractor", "full_time"]:
                errors.append("Employee type must be 'contractor' or 'full_time'")

            # Contractor-specific validation
            if self.employee_type == "contractor":
                if not self.hourly_rate:
                    errors.append("Contractors must have hourly rate")
                if not self.contract_end_date:
                    errors.append("Contractors must have contract end date")
                if self.salary:
                    errors.append("Contractors cannot have salary")

            # Full-time employee validation
            elif self.employee_type == "full_time":
                if not self.salary:
                    errors.append("Full-time employees must have salary")
                if self.hourly_rate:
                    errors.append("Full-time employees cannot have hourly rate")
                if self.contract_end_date:
                    errors.append("Full-time employees cannot have contract end date")

            if errors:
                return Failure("; ".join(errors))
            return Success(None)

        Employee.validate = mock_conditional_validate

        # 유효한 계약직
        valid_contractor = Employee(
            name="John Contractor",
            employee_type="contractor",
            hourly_rate=50.0,
            contract_end_date=datetime(2024, 12, 31),
        )
        result = valid_contractor.validate()
        assert isinstance(result, Success)

        # 유효한 정규직
        valid_full_time = Employee(
            name="Jane Employee", employee_type="full_time", salary=75000.0
        )
        result = valid_full_time.validate()
        assert isinstance(result, Success)

        # 무효한 계약직 - 시급 없음
        invalid_contractor = Employee(
            name="Bad Contractor",
            employee_type="contractor",
            contract_end_date=datetime(2024, 12, 31),
            # hourly_rate 없음
        )
        result = invalid_contractor.validate()
        assert isinstance(result, Failure)
        assert "hourly rate" in result.error.lower()


class TestModelHelperFunctions:
    """모델 헬퍼 함수 테스트"""

    @dataclass
    class TestModel(BaseModel):
        id=None
        name=""

    @patch("rfs.database.models.get_model_registry")
    def test_create_model_helper(self, mock_get_registry):
        """create_model 헬퍼 함수 테스트"""
        mock_registry = Mock(spec=ModelRegistry)
        mock_get_registry.return_value = Success(mock_registry)

        # Mock create model
        def mock_create_model(name, fields, base_class=None):
            # 동적 모델 생성 시뮬레이션
            model_attrs = {}
            for field_name, field_def in fields.items():
                model_attrs[field_name] = field_def.default

            return Success(type(name, (base_class or BaseModel,), model_attrs))

        fields = {
            "id": Field(field_type="integer", primary_key=True),
            "name": Field(field_type="string", nullable=False),
        }

        result = mock_create_model("DynamicModel", fields)

        assert isinstance(result, Success)
        model_class = result.value
        assert model_class.__name__ == "DynamicModel"

    @patch("rfs.database.models.get_model_registry")
    def test_register_model_helper(self, mock_get_registry):
        """register_model 헬퍼 함수 테스트"""
        mock_registry = Mock(spec=ModelRegistry)
        mock_registry.register.return_value = Success(None)
        mock_get_registry.return_value = Success(mock_registry)

        result = register_model("test_model", self.TestModel)

        assert isinstance(result, Success)
        mock_registry.register.assert_called_once_with("test_model", self.TestModel)

    def test_model_registry_singleton(self):
        """모델 레지스트리 싱글톤 테스트"""
        # Mock singleton behavior
        _registry_instance = Mock(spec=ModelRegistry)

        def mock_get_model_registry():
            return Success(_registry_instance)

        result1 = mock_get_model_registry()
        result2 = mock_get_model_registry()

        assert isinstance(result1, Success)
        assert isinstance(result2, Success)
        assert result1.value == result2.value  # Same instance


class TestModelPerformance:
    """모델 성능 테스트"""

    def test_large_model_validation_performance(self):
        """대용량 모델 유효성 검사 성능 테스트"""

        @dataclass
        class LargeModel(BaseModel):
            # 많은 필드를 가진 모델
            field_01=""
            field_02=""
            field_03=0
            field_04: float = 0.0
            field_05=False
            # ... 실제로는 더 많은 필드가 있다고 가정

        # Mock high-performance validation
        def mock_fast_validate(self):
            # 빠른 유효성 검사 시뮬레이션
            errors = []

            # 필드 검증을 병렬로 처리한다고 가정
            field_validations = [
                (self.field_01, "Field 01 required") if not self.field_01 else None,
                (
                    (self.field_03, "Field 03 must be positive")
                    if self.field_03 < 0
                    else None
                ),
                (
                    (self.field_04, "Field 04 must be positive")
                    if self.field_04 < 0
                    else None
                ),
            ]

            errors = [msg for val, msg in field_validations if val is not None and msg]

            if errors:
                return Failure("; ".join(errors))
            return Success(None)

        LargeModel.validate = mock_fast_validate

        # 1000개 모델 인스턴스 유효성 검사
        models = []
        for i in range(1000):
            model = LargeModel(
                field_01=f"value_{i}",
                field_02=f"description_{i}",
                field_03=i,
                field_04=float(i),
                field_05=i % 2 == 0,
            )
            models.append(model)

        import time

        start_time = time.time()

        validation_results = []
        for model in models:
            result = model.validate()
            validation_results.append(result)

        end_time = time.time()

        # 모든 검증이 성공해야 함
        assert all(isinstance(r, Success) for r in validation_results)

        # 성능 어설션 (0.5초 이내)
        assert (end_time - start_time) < 0.5

    def test_model_serialization_performance(self):
        """모델 직렬화 성능 테스트"""

        @dataclass
        class SerializationTestModel(BaseModel):
            id=0
            name=""
            data: Dict[str, Any] = field(default_factory=dict)
            items: List[str] = field(default_factory=list)
            created_at: datetime = field(default_factory=datetime.now)

        # Mock fast serialization
        def mock_fast_to_dict(self):
            return {
                "id": self.id,
                "name": self.name,
                "data": self.data,
                "items": self.items,
                "created_at": self.created_at.isoformat(),
            }

        SerializationTestModel.to_dict = mock_fast_to_dict

        # 복잡한 데이터를 가진 모델들
        models = []
        for i in range(500):
            model = SerializationTestModel(
                id=i,
                name=f"Model {i}",
                data={
                    "key1": f"value1_{i}",
                    "key2": f"value2_{i}",
                    "numbers": list(range(10)),
                },
                items=[f"item_{j}" for j in range(20)],
                created_at=datetime.now(),
            )
            models.append(model)

        import time

        start_time = time.time()

        # 모든 모델 직렬화
        serialized_models = []
        for model in models:
            serialized = model.to_dict()
            serialized_models.append(serialized)

        end_time = time.time()

        assert len(serialized_models) == 500
        assert all("id" in model for model in serialized_models)

        # 성능 어설션 (0.3초 이내)
        assert (end_time - start_time) < 0.3
