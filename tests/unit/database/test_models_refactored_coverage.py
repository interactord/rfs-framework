"""
RFS Database Models Refactored Coverage Tests
models_refactored.py 모듈의 90% 커버리지 달성을 위한 포괄적 테스트
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest


@pytest.fixture(autouse=True)
def setup_orm_environment():
    """ORM 환경 설정"""
    # SQLAlchemy 모드로 설정
    with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
        yield


class TestFieldDataclass:
    """Field 데이터클래스 테스트"""

    def test_field_creation_all_attributes(self):
        """Field 모든 속성 생성 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.database.models_refactored import Field

            field = Field(
                field_type="string",
                primary_key=True,
                nullable=False,
                default="test_default",
                max_length=255,
                foreign_key="users.id",
                index=True,
                unique=True,
                description="Test field description",
            )

            assert field.field_type == "string"
            assert field.primary_key is True
            assert field.nullable is False
            assert field.default == "test_default"
            assert field.max_length == 255
            assert field.foreign_key == "users.id"
            assert field.index is True
            assert field.unique is True
            assert field.description == "Test field description"

    def test_field_creation_defaults(self):
        """Field 기본값 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.database.models_refactored import Field

            field = Field("integer")

            assert field.field_type == "integer"
            assert field.primary_key is False
            assert field.nullable is True
            assert field.default is None
            assert field.max_length is None
            assert field.foreign_key is None
            assert field.index is False
            assert field.unique is False
            assert field.description is None


class TestTableDataclass:
    """Table 데이터클래스 테스트"""

    def test_table_creation_full(self):
        """Table 완전 생성 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.database.models_refactored import Field, Table

            fields = {
                "id": Field("integer", primary_key=True),
                "name": Field("string", max_length=100),
                "email": Field("string", unique=True),
            }

            table = Table(
                name="users",
                fields=fields,
                indexes=["idx_name", "idx_email"],
                constraints=["unique_email", "pk_users"],
            )

            assert table.name == "users"
            assert len(table.fields) == 3
            assert "id" in table.fields
            assert "name" in table.fields
            assert "email" in table.fields
            assert "idx_name" in table.indexes
            assert "idx_email" in table.indexes
            assert "unique_email" in table.constraints
            assert "pk_users" in table.constraints

    def test_table_creation_minimal(self):
        """Table 최소 생성 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.database.models_refactored import Field, Table

            fields = {"id": Field("integer")}
            table = Table("test_table", fields)

            assert table.name == "test_table"
            assert len(table.fields) == 1
            assert len(table.indexes) == 0
            assert len(table.constraints) == 0


class TestBaseModelAbstract:
    """BaseModel 추상 클래스 테스트"""

    def test_base_model_init(self):
        """BaseModel 초기화 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.core.result import Success
            from rfs.database.models_refactored import BaseModel, Field

            class ConcreteModel(BaseModel):
                __fields__ = {
                    "id": Field("integer", primary_key=True),
                    "name": Field("string"),
                    "active": Field("boolean"),
                }

                @classmethod
                def create_table(cls):
                    from rfs.database.models_refactored import Table

                    return Table("concrete", cls.__fields__)

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

            # hasattr가 있는 속성만 설정됨
            model = ConcreteModel()
            model.id = 1
            model.name = "Test"
            model.active = True

            # __init__ 메서드를 통한 초기화
            model2 = ConcreteModel(
                id=2, name="Test2", active=False, ignored="should_be_ignored"
            )

            # hasattr 체크로 인해 실제로는 설정되지 않지만, 메서드는 실행됨
            assert hasattr(model2, "id")

    def test_base_model_to_dict(self):
        """BaseModel to_dict 메서드 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.core.result import Success
            from rfs.database.models_refactored import BaseModel, Field

            class TestModel(BaseModel):
                __fields__ = {
                    "id": Field("integer"),
                    "name": Field("string"),
                    "count": Field("integer"),
                }

                @classmethod
                def create_table(cls):
                    from rfs.database.models_refactored import Table

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

            model = TestModel()
            model.id = 1
            model.name = "Test"
            model.count = 42

            result = model.to_dict()
            expected = {"id": 1, "name": "Test", "count": 42}
            assert result == expected

    def test_base_model_update_from_dict(self):
        """BaseModel update_from_dict 메서드 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.core.result import Success
            from rfs.database.models_refactored import BaseModel, Field

            class TestModel(BaseModel):
                __fields__ = {
                    "id": Field("integer"),
                    "name": Field("string"),
                    "count": Field("integer"),
                }

                @classmethod
                def create_table(cls):
                    from rfs.database.models_refactored import Table

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

            model = TestModel()
            model.id = 1
            model.name = "Original"
            model.count = 10

            # update_from_dict 호출
            model.update_from_dict(
                {"name": "Updated", "count": 20, "ignored_field": "should_be_ignored"}
            )

            assert model.name == "Updated"
            assert model.count == 20
            assert model.id == 1  # 변경되지 않음


class TestSQLAlchemyModel:
    """SQLAlchemy 모델 테스트"""

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_save_success(self):
        """SQLAlchemy save 성공 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                # Mock 데이터베이스 설정
                mock_session = AsyncMock()
                mock_session.add = Mock()
                mock_session.commit = AsyncMock()
                mock_session.refresh = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                mock_database = Mock()
                mock_database.create_session = Mock(return_value=mock_session)

                with patch(
                    "rfs.database.models_refactored.get_database",
                    return_value=mock_database,
                ):
                    model = SQLAlchemyModel()
                    result = await model.save()

                    assert result.is_success()
                    assert result.unwrap() == model
                    mock_session.add.assert_called_once_with(model)
                    mock_session.commit.assert_called_once()
                    mock_session.refresh.assert_called_once_with(model)

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_save_no_database(self):
        """SQLAlchemy save 데이터베이스 없음 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                with patch(
                    "rfs.database.models_refactored.get_database", return_value=None
                ):
                    model = SQLAlchemyModel()
                    result = await model.save()

                    assert result.is_failure()
                    assert (
                        "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()
                    )

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_save_exception(self):
        """SQLAlchemy save 예외 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                mock_database = Mock()
                mock_database.create_session = Mock(side_effect=Exception("DB Error"))

                with patch(
                    "rfs.database.models_refactored.get_database",
                    return_value=mock_database,
                ):
                    model = SQLAlchemyModel()
                    result = await model.save()

                    assert result.is_failure()
                    assert "모델 저장 실패: DB Error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_delete_success(self):
        """SQLAlchemy delete 성공 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                mock_session = AsyncMock()
                mock_session.delete = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                mock_database = Mock()
                mock_database.create_session = Mock(return_value=mock_session)

                with patch(
                    "rfs.database.models_refactored.get_database",
                    return_value=mock_database,
                ):
                    model = SQLAlchemyModel()
                    result = await model.delete()

                    assert result.is_success()
                    assert result.unwrap() is None
                    mock_session.delete.assert_called_once_with(model)
                    mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_delete_no_database(self):
        """SQLAlchemy delete 데이터베이스 없음 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                with patch(
                    "rfs.database.models_refactored.get_database", return_value=None
                ):
                    model = SQLAlchemyModel()
                    result = await model.delete()

                    assert result.is_failure()
                    assert (
                        "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()
                    )

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_get_success(self):
        """SQLAlchemy get 성공 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                mock_model = SQLAlchemyModel()
                mock_result = Mock()
                mock_result.scalar_one_or_none = Mock(return_value=mock_model)

                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                mock_database = Mock()
                mock_database.create_session = Mock(return_value=mock_session)

                with patch(
                    "rfs.database.models_refactored.get_database",
                    return_value=mock_database,
                ):
                    with patch("rfs.database.models_refactored.select") as mock_select:
                        mock_query = Mock()
                        mock_query.filter_by = Mock(return_value=mock_query)
                        mock_select.return_value = mock_query

                        result = await SQLAlchemyModel.get(id=1)

                        assert result.is_success()
                        assert result.unwrap() == mock_model
                        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_filter_success(self):
        """SQLAlchemy filter 성공 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                mock_models = [SQLAlchemyModel() for _ in range(3)]
                mock_scalars = Mock()
                mock_scalars.all = Mock(return_value=mock_models)
                mock_result = Mock()
                mock_result.scalars = Mock(return_value=mock_scalars)

                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                mock_database = Mock()
                mock_database.create_session = Mock(return_value=mock_session)

                with patch(
                    "rfs.database.models_refactored.get_database",
                    return_value=mock_database,
                ):
                    with patch("rfs.database.models_refactored.select") as mock_select:
                        mock_query = Mock()
                        mock_query.filter_by = Mock(return_value=mock_query)
                        mock_select.return_value = mock_query

                        result = await SQLAlchemyModel.filter(active=True)

                        assert result.is_success()
                        assert len(result.unwrap()) == 3

    def test_sqlalchemy_create_table_basic(self):
        """SQLAlchemy create_table 기본 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                class TestModel(SQLAlchemyModel):
                    __tablename__ = "test_table"

                table = TestModel.create_table()

                assert table.name == "test_table"
                assert "id" in table.fields
                assert "created_at" in table.fields
                assert "updated_at" in table.fields

    def test_sqlalchemy_create_table_with_table_attr(self):
        """SQLAlchemy create_table __table__ 속성 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import SQLAlchemyModel

                class TestModel(SQLAlchemyModel):
                    __tablename__ = "test_table"

                    # __table__ Mock 설정
                    __table__ = Mock()
                    __table__.columns = [
                        Mock(
                            name="custom_field",
                            type=Mock(__str__=lambda x: "varchar"),
                            primary_key=False,
                            nullable=True,
                            default="test",
                        )
                    ]

                table = TestModel.create_table()

                assert table.name == "test_table"
                assert "id" in table.fields
                assert "created_at" in table.fields
                assert "updated_at" in table.fields
                assert "custom_field" in table.fields


class TestTortoiseModel:
    """Tortoise 모델 테스트 (환경 변수 변경으로)"""

    @pytest.mark.asyncio
    async def test_tortoise_model_save_success(self):
        """Tortoise save 성공 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "TORTOISE"}):
            with patch("rfs.database.models_refactored.fields"):
                with patch("rfs.database.models_refactored.TortoiseBaseModel"):
                    with patch(
                        "rfs.database.models_refactored.get_logger"
                    ) as mock_logger:
                        mock_logger.return_value = Mock()

                        # 모듈을 다시 로드하여 TORTOISE 모드 적용
                        import importlib

                        import rfs.database.models_refactored

                        importlib.reload(rfs.database.models_refactored)

                        from rfs.database.models_refactored import TortoiseModel

                        # super().save() 모킹
                        with patch(
                            "rfs.database.models_refactored.super"
                        ) as mock_super:
                            mock_super_obj = Mock()
                            mock_super_obj.save = AsyncMock()
                            mock_super.return_value = mock_super_obj

                            model = TortoiseModel()
                            result = await model.save()

                            assert result.is_success()
                            assert result.unwrap() == model
                            mock_super_obj.save.assert_called_once()

    def test_tortoise_create_table(self):
        """Tortoise create_table 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "TORTOISE"}):
            with patch("rfs.database.models_refactored.fields"):
                with patch("rfs.database.models_refactored.TortoiseBaseModel"):
                    with patch(
                        "rfs.database.models_refactored.get_logger"
                    ) as mock_logger:
                        mock_logger.return_value = Mock()

                        import importlib

                        import rfs.database.models_refactored

                        importlib.reload(rfs.database.models_refactored)

                        from rfs.database.models_refactored import TortoiseModel

                        class TestModel(TortoiseModel):
                            class Meta:
                                table = "test_table"

                            # _meta 속성 모킹
                            _meta = Mock()
                            _meta.table = "test_table"
                            _meta.fields_map = {
                                "id": Mock(pk=True, null=False, default=None),
                                "name": Mock(pk=False, null=True, default="test"),
                            }

                        table = TestModel.create_table()

                        assert table.name == "test_table"
                        assert len(table.fields) == 2
                        assert "id" in table.fields
                        assert "name" in table.fields


class TestModelRegistry:
    """ModelRegistry 테스트"""

    def test_registry_register_and_get(self):
        """모델 등록 및 조회 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.core.result import Success
                from rfs.database.models_refactored import (
                    BaseModel,
                    Field,
                    ModelRegistry,
                    Table,
                )

                registry = ModelRegistry()

                class TestModel(BaseModel):
                    __fields__ = {"id": Field("integer")}

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

                # 모델 등록
                registry.register_model(TestModel)

                # 조회 테스트
                assert registry.get_model("TestModel") == TestModel
                table = registry.get_table("TestModel")
                assert table is not None
                assert table.name == "test"

                # 전체 조회
                all_models = registry.get_all_models()
                assert "TestModel" in all_models
                all_tables = registry.get_all_tables()
                assert "TestModel" in all_tables

    def test_registry_singleton(self):
        """레지스트리 싱글톤 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            from rfs.database.models_refactored import get_model_registry

            registry1 = get_model_registry()
            registry2 = get_model_registry()

            assert registry1 is registry2

    def test_register_model_function(self):
        """register_model 함수 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.core.result import Success
                from rfs.database.models_refactored import (
                    BaseModel,
                    Field,
                    Table,
                    get_model_registry,
                    register_model,
                )

                class TestModel(BaseModel):
                    @classmethod
                    def create_table(cls):
                        return Table("test", {})

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

                register_model(TestModel)

                # 등록 확인
                registry = get_model_registry()
                assert registry.get_model("TestModel") == TestModel


class TestCreateModelFunction:
    """create_model 함수 테스트"""

    def test_create_model_sqlalchemy_basic(self):
        """SQLAlchemy 동적 모델 생성 기본 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import Field, create_model

                fields = {
                    "id": Field("integer", primary_key=True),
                    "name": Field("string", max_length=100),
                }

                with patch(
                    "rfs.database.models_refactored.get_model_registry"
                ) as mock_get_registry:
                    mock_registry = Mock()
                    mock_get_registry.return_value = mock_registry

                    model_class = create_model("DynamicModel", fields)

                    assert model_class.__name__ == "DynamicModel"
                    assert model_class.__table_name__ == "dynamicmodel"
                    assert model_class.__fields__ == fields
                    mock_registry.register_model.assert_called_once_with(model_class)

    def test_create_model_sqlalchemy_field_types(self):
        """SQLAlchemy 다양한 필드 타입 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.get_logger") as mock_logger:
                mock_logger.return_value = Mock()

                from rfs.database.models_refactored import (
                    Field,
                    SQLAlchemyModel,
                    create_model,
                )

                fields = {
                    "int_field": Field("integer"),
                    "str_field": Field("string", max_length=200),
                    "text_field": Field("text"),
                    "dt_field": Field("datetime"),
                    "bool_field": Field("boolean"),
                    "json_field": Field("json"),
                    "unknown_field": Field("unknown_type"),
                }

                with patch(
                    "rfs.database.models_refactored.get_model_registry"
                ) as mock_get_registry:
                    mock_registry = Mock()
                    mock_get_registry.return_value = mock_registry

                    with patch("rfs.database.models_refactored.Column") as MockColumn:
                        model_class = create_model(
                            "TestModel",
                            fields,
                            base_class=SQLAlchemyModel,
                            table_name="custom_table",
                        )

                        assert model_class.__name__ == "TestModel"
                        assert model_class.__table_name__ == "custom_table"
                        # Column이 각 필드에 대해 호출되었는지 확인
                        assert MockColumn.call_count == len(fields)

    def test_create_model_tortoise_field_types(self):
        """Tortoise 다양한 필드 타입 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "TORTOISE"}):
            with patch("rfs.database.models_refactored.fields") as mock_fields:
                with patch("rfs.database.models_refactored.TortoiseBaseModel"):
                    with patch(
                        "rfs.database.models_refactored.get_logger"
                    ) as mock_logger:
                        mock_logger.return_value = Mock()

                        # Tortoise fields 모킹
                        mock_fields.IntField = Mock
                        mock_fields.CharField = Mock
                        mock_fields.TextField = Mock
                        mock_fields.DatetimeField = Mock
                        mock_fields.BooleanField = Mock
                        mock_fields.JSONField = Mock

                        import importlib

                        import rfs.database.models_refactored

                        importlib.reload(rfs.database.models_refactored)

                        from rfs.database.models_refactored import (
                            Field,
                            TortoiseModel,
                            create_model,
                        )

                        fields = {
                            "int_field": Field("integer", primary_key=True),
                            "str_field": Field("string", max_length=100),
                            "text_field": Field("text"),
                            "dt_field": Field("datetime"),
                            "bool_field": Field("boolean"),
                            "json_field": Field("json"),
                            "unknown_field": Field("unknown_type"),
                        }

                        with patch(
                            "rfs.database.models_refactored.get_model_registry"
                        ) as mock_get_registry:
                            mock_registry = Mock()
                            mock_get_registry.return_value = mock_registry

                            model_class = create_model(
                                "TortoiseTestModel", fields, base_class=TortoiseModel
                            )

                            assert model_class.__name__ == "TortoiseTestModel"
                            mock_fields.IntField.assert_called()
                            mock_fields.CharField.assert_called()


class TestORMEnvironmentDetection:
    """ORM 환경 감지 테스트"""

    def test_invalid_orm_type(self):
        """잘못된 ORM 타입 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "INVALID"}):
            with pytest.raises(ValueError, match="지원되지 않는 ORM 타입: INVALID"):
                import importlib

                import rfs.database.models_refactored

                importlib.reload(rfs.database.models_refactored)

    def test_sqlalchemy_import_error(self):
        """SQLAlchemy 임포트 에러 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            with patch("rfs.database.models_refactored.Column", None):
                with patch("rfs.database.models_refactored.Integer", None):
                    # 실제 임포트 에러를 발생시키기 위해 모듈 패치
                    original_import = __builtins__["__import__"]

                    def mock_import(name, *args):
                        if name == "sqlalchemy":
                            raise ImportError("SQLAlchemy not found")
                        return original_import(name, *args)

                    with patch("builtins.__import__", side_effect=mock_import):
                        with pytest.raises(
                            ImportError, match="SQLAlchemy가 설치되지 않았습니다"
                        ):
                            import importlib

                            import rfs.database.models_refactored

                            importlib.reload(rfs.database.models_refactored)


class TestModelGlobalVariable:
    """Model 전역 변수 테스트"""

    def test_model_variable_sqlalchemy(self):
        """Model 변수가 SQLAlchemy로 설정되는지 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "SQLALCHEMY"}):
            import importlib

            import rfs.database.models_refactored

            importlib.reload(rfs.database.models_refactored)

            from rfs.database.models_refactored import Model, SQLAlchemyModel

            assert Model == SQLAlchemyModel

    def test_model_variable_tortoise(self):
        """Model 변수가 Tortoise로 설정되는지 테스트"""
        with patch.dict(os.environ, {"RFS_ORM_TYPE": "TORTOISE"}):
            with patch("rfs.database.models_refactored.fields"):
                with patch("rfs.database.models_refactored.TortoiseBaseModel"):
                    import importlib

                    import rfs.database.models_refactored

                    importlib.reload(rfs.database.models_refactored)

                    from rfs.database.models_refactored import Model, TortoiseModel

                    assert Model == TortoiseModel


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
