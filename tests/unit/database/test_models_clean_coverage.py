"""
RFS Database Models Comprehensive Test Coverage
Phase 2: Clean approach without ORM metaclass conflicts
Target: 33.46% → 85%+ coverage
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
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
    Table,
    create_model,
    get_model_registry,
    register_model,
)


class TestField:
    """Field 클래스 테스트"""

    def test_field_creation_basic(self):
        """기본 필드 생성"""
        field = Field(field_type="string")
        assert field.field_type == "string"
        assert field.primary_key is False
        assert field.nullable is True
        assert field.default is None
        assert field.max_length is None
        assert field.foreign_key is None
        assert field.index is False
        assert field.unique is False
        assert field.description is None

    def test_field_creation_with_all_params(self):
        """모든 매개변수를 포함한 필드 생성"""
        field = Field(
            field_type="string",
            primary_key=True,
            nullable=False,
            default="test",
            max_length=255,
            foreign_key="users.id",
            index=True,
            unique=True,
            description="Test field",
        )
        assert field.field_type == "string"
        assert field.primary_key is True
        assert field.nullable is False
        assert field.default == "test"
        assert field.max_length == 255
        assert field.foreign_key == "users.id"
        assert field.index is True
        assert field.unique is True
        assert field.description == "Test field"

    def test_field_integer_type(self):
        """정수 타입 필드"""
        field = Field(field_type="integer", primary_key=True)
        assert field.field_type == "integer"
        assert field.primary_key is True

    def test_field_datetime_type(self):
        """날짜시간 타입 필드"""
        field = Field(field_type="datetime", default=datetime.utcnow)
        assert field.field_type == "datetime"
        assert callable(field.default)

    def test_field_boolean_type(self):
        """불린 타입 필드"""
        field = Field(field_type="boolean", default=False)
        assert field.field_type == "boolean"
        assert field.default is False


class TestTable:
    """Table 클래스 테스트"""

    def test_table_creation_basic(self):
        """기본 테이블 생성"""
        fields = {
            "id": Field("integer", primary_key=True),
            "name": Field("string", max_length=100),
        }
        table = Table(name="users", fields=fields)
        assert table.name == "users"
        assert len(table.fields) == 2
        assert "id" in table.fields
        assert "name" in table.fields
        assert table.indexes == []
        assert table.constraints == []

    def test_table_creation_with_indexes(self):
        """인덱스를 포함한 테이블 생성"""
        fields = {"name": Field("string")}
        indexes = ["idx_name"]
        table = Table(name="users", fields=fields, indexes=indexes)
        assert table.indexes == ["idx_name"]

    def test_table_creation_with_constraints(self):
        """제약조건을 포함한 테이블 생성"""
        fields = {"email": Field("string", unique=True)}
        constraints = ["UNIQUE(email)"]
        table = Table(name="users", fields=fields, constraints=constraints)
        assert table.constraints == ["UNIQUE(email)"]

    def test_table_complex_structure(self):
        """복잡한 테이블 구조"""
        fields = {
            "id": Field("integer", primary_key=True),
            "name": Field("string", max_length=100, nullable=False),
            "email": Field("string", max_length=255, unique=True, index=True),
            "created_at": Field("datetime", default=datetime.utcnow),
            "updated_at": Field("datetime", default=datetime.utcnow),
        }
        indexes = ["idx_name", "idx_email"]
        constraints = ["UNIQUE(email)", "CHECK(name != '')"]

        table = Table(
            name="users", fields=fields, indexes=indexes, constraints=constraints
        )

        assert table.name == "users"
        assert len(table.fields) == 5
        assert table.indexes == ["idx_name", "idx_email"]
        assert table.constraints == ["UNIQUE(email)", "CHECK(name != '')"]


class TestBaseModel:
    """BaseModel 추상 클래스 테스트를 위한 구체 클래스"""

    def test_basemodel_abstract_nature(self):
        """BaseModel은 추상 클래스로 직접 인스턴스화할 수 없음"""
        with pytest.raises(TypeError):
            BaseModel()

    def test_basemodel_subclass_init(self):
        """BaseModel 서브클래스 초기화 테스트"""

        # 테스트용 구체 클래스 생성
        class ConcreteModel(BaseModel):
            __fields__ = {"name": Field("string"), "age": Field("integer")}

            def __init__(self, **kwargs):
                self.name = None
                self.age = None
                super().__init__(**kwargs)

            @classmethod
            def create_table(cls):
                return Table("test", cls.__fields__)

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        # kwargs로 초기화
        model = ConcreteModel(name="John", age=30)
        assert model.name == "John"
        assert model.age == 30

    def test_basemodel_to_dict(self):
        """to_dict 메서드 테스트"""

        class TestModel(BaseModel):
            __fields__ = {
                "id": Field("integer"),
                "name": Field("string"),
                "email": Field("string"),
            }

            def __init__(self, **kwargs):
                self.id = None
                self.name = None
                self.email = None
                super().__init__(**kwargs)

            @classmethod
            def create_table(cls):
                return Table("test", cls.__fields__)

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        model = TestModel(id=1, name="John", email="john@example.com")
        data = model.to_dict()

        assert isinstance(data, dict)
        assert data["id"] == 1
        assert data["name"] == "John"
        assert data["email"] == "john@example.com"

    def test_basemodel_to_dict_partial(self):
        """부분적으로 설정된 모델의 to_dict 테스트"""

        class TestModel(BaseModel):
            __fields__ = {
                "id": Field("integer"),
                "name": Field("string"),
                "email": Field("string"),
            }

            def __init__(self, **kwargs):
                self.id = None
                self.name = None
                # email은 의도적으로 속성을 설정하지 않음
                super().__init__(**kwargs)

            @classmethod
            def create_table(cls):
                return Table("test", cls.__fields__)

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        model = TestModel(id=1, name="John")
        data = model.to_dict()

        assert data["id"] == 1
        assert data["name"] == "John"
        # email 속성이 없으므로 키 자체가 딕셔너리에 포함되지 않음
        assert "email" not in data

    def test_basemodel_update_from_dict(self):
        """update_from_dict 메서드 테스트"""

        class TestModel(BaseModel):
            __fields__ = {
                "id": Field("integer"),
                "name": Field("string"),
                "email": Field("string"),
            }

            def __init__(self, **kwargs):
                self.id = None
                self.name = None
                self.email = None
                super().__init__(**kwargs)

            @classmethod
            def create_table(cls):
                return Table("test", cls.__fields__)

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        model = TestModel(id=1, name="John")

        # 업데이트 데이터
        update_data = {
            "name": "Jane",
            "email": "jane@example.com",
            "invalid_field": "should_be_ignored",  # __fields__에 없는 필드
        }

        model.update_from_dict(update_data)

        assert model.name == "Jane"
        assert model.email == "jane@example.com"
        assert not hasattr(model, "invalid_field")

    def test_basemodel_update_from_dict_nonexistent_attr(self):
        """존재하지 않는 속성에 대한 update_from_dict 테스트"""

        class TestModel(BaseModel):
            __fields__ = {
                "id": Field("integer"),
                "name": Field("string"),
                "missing_attr": Field("string"),  # 필드는 정의되어 있지만 속성은 없음
            }

            def __init__(self, **kwargs):
                self.id = None
                self.name = None
                # missing_attr 속성은 의도적으로 생성하지 않음
                super().__init__(**kwargs)

            @classmethod
            def create_table(cls):
                return Table("test", cls.__fields__)

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        model = TestModel(id=1, name="John")

        # missing_attr 필드는 __fields__에 있지만 hasattr로 체크하면 False
        update_data = {"name": "Jane", "missing_attr": "should_be_ignored"}

        model.update_from_dict(update_data)

        assert model.name == "Jane"
        assert not hasattr(model, "missing_attr")


class TestModelRegistry:
    """ModelRegistry 테스트"""

    def test_registry_singleton(self):
        """레지스트리 싱글톤 패턴 테스트"""
        registry1 = ModelRegistry()
        registry2 = ModelRegistry()
        assert registry1 is registry2

    def test_get_model_registry(self):
        """get_model_registry 함수 테스트"""
        registry1 = get_model_registry()
        registry2 = get_model_registry()
        assert registry1 is registry2
        assert isinstance(registry1, ModelRegistry)

    def test_registry_initialization(self):
        """레지스트리 초기화 테스트"""
        registry = ModelRegistry()
        assert hasattr(registry, "models")
        assert hasattr(registry, "tables")
        assert isinstance(registry.models, dict)
        assert isinstance(registry.tables, dict)

    @patch("rfs.database.models.logger")
    def test_register_model(self, mock_logger):
        """모델 등록 테스트"""

        class TestModel(BaseModel):
            __fields__ = {"id": Field("integer", primary_key=True)}

            @classmethod
            def create_table(cls):
                return Table("test_model", cls.__fields__)

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        registry = ModelRegistry()
        # 초기 상태 확인
        initial_models_count = len(registry.models)
        initial_tables_count = len(registry.tables)

        registry.register_model(TestModel)

        # 등록 후 상태 확인
        assert len(registry.models) == initial_models_count + 1
        assert len(registry.tables) == initial_tables_count + 1
        assert "TestModel" in registry.models
        assert "TestModel" in registry.tables
        assert registry.models["TestModel"] == TestModel

        # 로깅 확인
        mock_logger.info.assert_called_once_with("모델 등록: TestModel")

        # 테이블 정의 확인
        table = registry.tables["TestModel"]
        assert isinstance(table, Table)
        assert table.name == "test_model"

    def test_get_model_existing(self):
        """존재하는 모델 조회 테스트"""

        class ExistingModel(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("existing", {})

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        registry = ModelRegistry()
        registry.register_model(ExistingModel)

        result = registry.get_model("ExistingModel")
        assert result == ExistingModel

    def test_get_model_nonexistent(self):
        """존재하지 않는 모델 조회 테스트"""
        registry = ModelRegistry()
        result = registry.get_model("NonExistentModel")
        assert result is None

    def test_get_table_existing(self):
        """존재하는 테이블 정의 조회 테스트"""

        class TableModel(BaseModel):
            __fields__ = {"id": Field("integer")}

            @classmethod
            def create_table(cls):
                return Table("table_model", cls.__fields__)

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        registry = ModelRegistry()
        registry.register_model(TableModel)

        table = registry.get_table("TableModel")
        assert isinstance(table, Table)
        assert table.name == "table_model"

    def test_get_table_nonexistent(self):
        """존재하지 않는 테이블 정의 조회 테스트"""
        registry = ModelRegistry()
        result = registry.get_table("NonExistentTable")
        assert result is None

    def test_get_all_models(self):
        """모든 모델 반환 테스트"""

        class Model1(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("model1", {})

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        class Model2(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("model2", {})

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        registry = ModelRegistry()
        initial_count = len(registry.get_all_models())

        registry.register_model(Model1)
        registry.register_model(Model2)

        all_models = registry.get_all_models()
        assert isinstance(all_models, dict)
        assert len(all_models) == initial_count + 2
        assert "Model1" in all_models
        assert "Model2" in all_models

        # 원본과 다른 객체인지 확인 (copy 확인)
        all_models["Model1"] = None
        assert registry.models["Model1"] is not None

    def test_get_all_tables(self):
        """모든 테이블 정의 반환 테스트"""

        class TableModel1(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("table1", {})

            async def save(self):
                return Success(self)

            async def delete(self):
                return Success(None)

            @classmethod
            async def get(cls, **filters):
                return Success(None)

            @classmethod
            async def filter(cls, **filters):
                return Success([])

        registry = ModelRegistry()
        initial_count = len(registry.get_all_tables())

        registry.register_model(TableModel1)

        all_tables = registry.get_all_tables()
        assert isinstance(all_tables, dict)
        assert len(all_tables) == initial_count + 1
        assert "TableModel1" in all_tables

        # 원본과 다른 객체인지 확인 (copy 확인)
        all_tables["TableModel1"] = None
        assert registry.tables["TableModel1"] is not None


class TestRegisterModelFunction:
    """register_model 함수 테스트"""

    @patch("rfs.database.models.get_model_registry")
    def test_register_model_function(self, mock_get_registry):
        """register_model 전역 함수 테스트"""

        # Mock 레지스트리 설정
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        class TestModel(BaseModel):
            pass

        register_model(TestModel)

        # get_model_registry가 호출되었는지 확인
        mock_get_registry.assert_called_once()

        # 레지스트리의 register_model이 호출되었는지 확인
        mock_registry.register_model.assert_called_once_with(TestModel)


class TestCreateModelFunction:
    """create_model 동적 모델 생성 함수 테스트 - 간소화"""

    def test_create_model_function_exists(self):
        """create_model 함수가 존재하고 호출 가능한지 확인"""
        from rfs.database.models import create_model

        assert callable(create_model)

        # 함수 시그니처 확인
        import inspect

        sig = inspect.signature(create_model)
        params = list(sig.parameters.keys())
        assert "name" in params
        assert "fields" in params
        assert "base_class" in params
        assert "table_name" in params


class TestModelFunction:
    """Model 함수 테스트 (현재 ORM 설정에 따른 모델 베이스 반환) - 간소화"""

    def test_model_function_exists(self):
        """Model 함수가 존재하고 호출 가능한지 확인"""
        from rfs.database.models import Model

        assert callable(Model)


class TestORMAvailability:
    """ORM 가용성 테스트"""

    def test_sqlalchemy_availability_flag(self):
        """SQLAlchemy 가용성 플래그 테스트"""
        # SQLALCHEMY_AVAILABLE은 import 시점에 결정됨
        assert isinstance(SQLALCHEMY_AVAILABLE, bool)

    def test_tortoise_availability_flag(self):
        """Tortoise 가용성 플래그 테스트"""
        # TORTOISE_AVAILABLE은 import 시점에 결정됨
        assert isinstance(TORTOISE_AVAILABLE, bool)


class TestAsyncModelMethods:
    """BaseModel의 비동기 메서드 테스트 (구체 클래스 필요)"""

    def test_abstract_methods_signature(self):
        """추상 메서드 시그니처 테스트"""

        # BaseModel의 추상 메서드들이 올바른 시그니처를 가지는지 확인
        from inspect import signature

        # save 메서드 시그니처 확인
        save_sig = signature(BaseModel.save)
        assert len(save_sig.parameters) == 1  # self

        # delete 메서드 시그니처 확인
        delete_sig = signature(BaseModel.delete)
        assert len(delete_sig.parameters) == 1  # self

        # get 클래스 메서드 시그니처 확인
        get_sig = signature(BaseModel.get)
        assert len(get_sig.parameters) == 1  # **filters (cls는 자동 제외)

        # filter 클래스 메서드 시그니처 확인
        filter_sig = signature(BaseModel.filter)
        assert len(filter_sig.parameters) == 1  # **filters (cls는 자동 제외)


class TestSQLAlchemyModel:
    """SQLAlchemy 모델 베이스 클래스 테스트"""

    def test_sqlalchemy_model_availability(self):
        """SQLAlchemy 모델 클래스 가용성 확인"""
        if SQLALCHEMY_AVAILABLE:
            from rfs.database.models import SQLAlchemyModel

            assert SQLAlchemyModel is not None
            assert hasattr(SQLAlchemyModel, "__abstract__")
            assert SQLAlchemyModel.__abstract__ is True

    def test_sqlalchemy_model_fields(self):
        """SQLAlchemy 모델 기본 필드 확인"""
        if SQLALCHEMY_AVAILABLE:
            from rfs.database.models import SQLAlchemyModel

            # 기본 필드들이 존재하는지 확인
            assert hasattr(SQLAlchemyModel, "id")
            assert hasattr(SQLAlchemyModel, "created_at")
            assert hasattr(SQLAlchemyModel, "updated_at")

            # 추상 메서드들이 존재하는지 확인
            assert hasattr(SQLAlchemyModel, "create_table")
            assert hasattr(SQLAlchemyModel, "save")
            assert hasattr(SQLAlchemyModel, "delete")
            assert hasattr(SQLAlchemyModel, "get")
            assert hasattr(SQLAlchemyModel, "filter")

    def test_sqlalchemy_create_table_structure(self):
        """SQLAlchemy create_table 메서드 구조 확인"""
        if SQLALCHEMY_AVAILABLE:
            from rfs.database.models import SQLAlchemyModel

            # create_table이 클래스 메서드인지 확인
            assert hasattr(SQLAlchemyModel.create_table, "__self__")

            # 메서드 시그니처 확인
            import inspect

            sig = inspect.signature(SQLAlchemyModel.create_table)
            assert len(sig.parameters) == 0  # cls는 자동으로 제외됨


class TestTortoiseModel:
    """Tortoise 모델 베이스 클래스 테스트"""

    def test_tortoise_model_availability(self):
        """Tortoise 모델 클래스 가용성 확인"""
        if TORTOISE_AVAILABLE:
            from rfs.database.models import TortoiseModel

            assert TortoiseModel is not None
            assert hasattr(TortoiseModel, "Meta")
            assert TortoiseModel.Meta.abstract is True

    def test_tortoise_model_methods(self):
        """Tortoise 모델 메서드 확인"""
        if TORTOISE_AVAILABLE:
            from rfs.database.models import TortoiseModel

            # 추상 메서드들이 존재하는지 확인
            assert hasattr(TortoiseModel, "create_table")
            assert hasattr(TortoiseModel, "save")
            assert hasattr(TortoiseModel, "delete")
            assert hasattr(TortoiseModel, "get")
            assert hasattr(TortoiseModel, "filter")

    def test_tortoise_create_table_structure(self):
        """Tortoise create_table 메서드 구조 확인"""
        if TORTOISE_AVAILABLE:
            from rfs.database.models import TortoiseModel

            # create_table이 클래스 메서드인지 확인
            assert hasattr(TortoiseModel.create_table, "__self__")


class TestModelAvailabilityChecks:
    """모델 가용성 관련 내부 로직 테스트"""

    def test_sqlalchemy_base_creation(self):
        """SQLAlchemy_Base 객체 생성 테스트"""
        if SQLALCHEMY_AVAILABLE:
            from rfs.database.models import SQLAlchemy_Base

            assert SQLAlchemy_Base is not None
            # declarative_base로 생성된 객체인지 확인
            assert hasattr(SQLAlchemy_Base, "metadata")

    def test_tortoise_base_availability(self):
        """TortoiseBaseModel 가용성 테스트"""
        if TORTOISE_AVAILABLE:
            from rfs.database.models import TortoiseBaseModel

            assert TortoiseBaseModel is not None
        else:
            # Tortoise를 사용할 수 없는 경우 object여야 함
            from rfs.database.models import TortoiseBaseModel

            assert TortoiseBaseModel == object


class TestFieldTypeHandling:
    """필드 타입 처리 관련 테스트"""

    def test_field_types_comprehensive(self):
        """다양한 필드 타입 테스트"""

        # 모든 지원되는 타입 테스트
        field_types = [
            "integer",
            "string",
            "text",
            "datetime",
            "boolean",
            "json",
            "float",
            "decimal",
        ]

        for field_type in field_types:
            field = Field(field_type=field_type)
            assert field.field_type == field_type

    def test_field_constraints_combinations(self):
        """필드 제약조건 조합 테스트"""

        # 다양한 조합 테스트
        combinations = [
            {"primary_key": True, "nullable": False},
            {"unique": True, "index": True},
            {"foreign_key": "users.id", "nullable": True},
            {"max_length": 255, "default": "test"},
        ]

        for combo in combinations:
            field = Field(field_type="string", **combo)
            for key, value in combo.items():
                assert getattr(field, key) == value

    def test_table_with_complex_fields(self):
        """복잡한 필드 조합을 가진 테이블 테스트"""

        fields = {
            "id": Field("integer", primary_key=True, nullable=False),
            "username": Field("string", max_length=50, unique=True, nullable=False),
            "email": Field("string", max_length=255, unique=True, index=True),
            "password_hash": Field("string", max_length=255, nullable=False),
            "is_active": Field("boolean", default=True),
            "profile_data": Field("json", default={}),
            "created_at": Field("datetime", default=datetime.utcnow),
            "updated_at": Field("datetime", default=datetime.utcnow),
            "parent_id": Field("integer", foreign_key="users.id", nullable=True),
        }

        indexes = ["idx_username", "idx_email", "idx_active"]
        constraints = [
            "UNIQUE(username)",
            "CHECK(email LIKE '%@%')",
            "CHECK(LENGTH(password_hash) >= 8)",
        ]

        table = Table(
            name="users", fields=fields, indexes=indexes, constraints=constraints
        )

        assert table.name == "users"
        assert len(table.fields) == 9
        assert len(table.indexes) == 3
        assert len(table.constraints) == 3

        # 특정 필드 확인
        assert table.fields["id"].primary_key is True
        assert table.fields["username"].unique is True
        assert table.fields["email"].index is True
        assert table.fields["parent_id"].foreign_key == "users.id"


class TestSQLAlchemyCreateTable:
    """SQLAlchemy create_table 메서드 세부 테스트"""

    def test_sqlalchemy_create_table_basic_structure(self):
        """SQLAlchemy create_table 기본 구조 확인"""
        if SQLALCHEMY_AVAILABLE:
            from rfs.database.models import SQLAlchemyModel

            # Mock 테이블 클래스 생성
            class MockTable:
                def __init__(self):
                    self.columns = []

            class TestSQLModel(SQLAlchemyModel):
                __tablename__ = "test_table"
                __table__ = None  # 테이블이 없는 경우

            table = TestSQLModel.create_table()

            # 기본 필드들이 포함되어야 함
            assert isinstance(table, Table)
            assert table.name == "test_table"

            # 기본 필드들 확인
            expected_fields = ["id", "created_at", "updated_at"]
            for field_name in expected_fields:
                assert field_name in table.fields

    def test_sqlalchemy_create_table_with_custom_tablename(self):
        """커스텀 테이블명을 가진 SQLAlchemy 모델"""
        if SQLALCHEMY_AVAILABLE:
            from rfs.database.models import SQLAlchemyModel

            class CustomTableModel(SQLAlchemyModel):
                __tablename__ = "custom_users"
                __table__ = None

            table = CustomTableModel.create_table()

            assert table.name == "custom_users"

    def test_sqlalchemy_create_table_default_name(self):
        """기본 테이블명을 사용하는 SQLAlchemy 모델"""
        if SQLALCHEMY_AVAILABLE:
            from rfs.database.models import SQLAlchemyModel

            class NoTablenameModel(SQLAlchemyModel):
                # __tablename__ 속성이 없는 경우
                __table__ = None

            table = NoTablenameModel.create_table()

            # 클래스명의 소문자 버전이 사용되어야 함
            assert table.name == "notablenamemodel"


class TestTortoiseCreateTable:
    """Tortoise create_table 메서드 세부 테스트"""

    def test_tortoise_create_table_basic_structure(self):
        """Tortoise create_table 기본 구조 확인"""
        if TORTOISE_AVAILABLE:
            from rfs.database.models import TortoiseModel

            class TestTortoiseModel(TortoiseModel):
                class Meta:
                    table = "test_tortoise_table"
                    abstract = False

                # _meta 속성이 없는 경우를 시뮬레이션
                _meta = None

            table = TestTortoiseModel.create_table()

            assert isinstance(table, Table)
            # _meta가 없는 경우 클래스명의 소문자 버전 사용
            assert table.name == "testtortoisemodel"

    def test_tortoise_create_table_with_meta(self):
        """Meta 정보를 가진 Tortoise 모델"""
        if TORTOISE_AVAILABLE:
            from rfs.database.models import TortoiseModel

            # Mock Meta 객체
            class MockMeta:
                table = "tortoise_users"
                fields_map = {}

            class MetaTortoiseModel(TortoiseModel):
                _meta = MockMeta()

                class Meta:
                    abstract = False

            table = MetaTortoiseModel.create_table()

            assert table.name == "tortoise_users"
            assert isinstance(table.fields, dict)


class TestDynamicFieldHandling:
    """동적 필드 처리 관련 테스트"""

    def test_field_type_edge_cases(self):
        """필드 타입 엣지 케이스 테스트"""

        # None 기본값
        field1 = Field("string", default=None)
        assert field1.default is None

        # 빈 문자열 기본값
        field2 = Field("string", default="")
        assert field2.default == ""

        # 0 기본값
        field3 = Field("integer", default=0)
        assert field3.default == 0

        # False 기본값
        field4 = Field("boolean", default=False)
        assert field4.default is False

        # 빈 리스트 기본값
        field5 = Field("json", default=[])
        assert field5.default == []

    def test_field_description_handling(self):
        """필드 설명 처리 테스트"""

        field_with_desc = Field("string", description="사용자 이름 필드")
        assert field_with_desc.description == "사용자 이름 필드"

        field_without_desc = Field("string")
        assert field_without_desc.description is None

    def test_complex_foreign_key_handling(self):
        """복잡한 외래키 처리 테스트"""

        # 다양한 외래키 패턴
        fk_patterns = [
            "users.id",
            "organizations.uuid",
            "auth.users.user_id",
            "public.accounts.account_number",
        ]

        for fk_pattern in fk_patterns:
            field = Field("integer", foreign_key=fk_pattern)
            assert field.foreign_key == fk_pattern

            # 외래키가 있는 필드는 보통 nullable이어야 함
            field_nullable = Field("integer", foreign_key=fk_pattern, nullable=True)
            assert field_nullable.nullable is True

    def test_max_length_variations(self):
        """max_length 다양한 값 테스트"""

        max_lengths = [1, 50, 100, 255, 1000, 4000, None]

        for max_len in max_lengths:
            field = Field("string", max_length=max_len)
            assert field.max_length == max_len

    def test_index_and_unique_combinations(self):
        """인덱스와 유니크 제약조건 조합 테스트"""

        # 다양한 조합
        combinations = [
            {"index": True, "unique": False},
            {"index": False, "unique": True},
            {"index": True, "unique": True},  # 유니크는 자동으로 인덱스
            {"index": False, "unique": False},
        ]

        for combo in combinations:
            field = Field("string", **combo)
            assert field.index == combo["index"]
            assert field.unique == combo["unique"]


class TestImportErrorHandling:
    """Import 에러 처리 관련 테스트"""

    def test_sqlalchemy_import_flags(self):
        """SQLAlchemy import 플래그 검증"""
        # SQLALCHEMY_AVAILABLE 플래그가 실제 import 상태와 일치하는지 확인
        try:
            import sqlalchemy

            expected = True
        except ImportError:
            expected = False

        assert SQLALCHEMY_AVAILABLE == expected

    def test_tortoise_import_flags(self):
        """Tortoise import 플래그 검증"""
        # TORTOISE_AVAILABLE 플래그가 실제 import 상태와 일치하는지 확인
        try:
            import tortoise

            expected = True
        except ImportError:
            expected = False

        assert TORTOISE_AVAILABLE == expected

    def test_module_imports_when_unavailable(self):
        """모듈이 사용 불가능한 경우 import 처리"""

        # SQLAlchemy가 없는 경우의 처리 확인
        if not SQLALCHEMY_AVAILABLE:
            from rfs.database.models import Column, Integer, String

            assert Column is None
            assert Integer is None
            assert String is None

        # Tortoise가 없는 경우의 처리 확인
        if not TORTOISE_AVAILABLE:
            from rfs.database.models import TortoiseBaseModel, fields

            assert fields is None
            assert TortoiseBaseModel == object


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
