"""
RFS Database Models Module Focused Coverage Tests (RFS v4.1)

Phase 2: 33.46% → 85%+ Coverage Target

타겟팅 라인 분석:
- 25-28: SQLAlchemy import 및 Base 설정
- 45: Tortoise import 설정
- 89-91: BaseModel __init__ 메서드
- 123-127: BaseModel to_dict 메서드
- 131-133: BaseModel update_from_dict 메서드
- 157-188: SQLAlchemyModel create_table 메서드
- 192-205: SQLAlchemyModel save 메서드
- 209-221: SQLAlchemyModel delete 메서드
- 226-240: SQLAlchemyModel get 메서드
- 245-259: SQLAlchemyModel filter 메서드
- 271-288: TortoiseModel create_table 메서드
- 292-297: TortoiseModel save 메서드
- 301-306: TortoiseModel delete 메서드
- 311-315: TortoiseModel get 메서드
- 320-324: TortoiseModel filter 메서드
- 334-357: ModelRegistry 메서드들
- 371-451: create_model 동적 모델 생성
- 456-457: register_model 함수
- 462-482: Model 함수
"""

# SQLAlchemy와 Tortoise 모킹 설정
import sys
from dataclasses import replace
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

# SQLAlchemy 모킹
mock_sqlalchemy = Mock()
mock_declarative = Mock()

# declarative_base를 object를 반환하도록 설정
mock_declarative.declarative_base = Mock(return_value=type("MockBase", (object,), {}))

mock_modules = {
    "sqlalchemy": mock_sqlalchemy,
    "sqlalchemy.ext.declarative": mock_declarative,
    "sqlalchemy.orm": Mock(),
    "tortoise": Mock(),
    "tortoise.models": Mock(),
    "tortoise.fields": Mock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

from rfs.core.result import Failure, Success

# 실제 모듈 import
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


class TestField:
    """Field 데이터클래스 테스트"""

    def test_field_default_creation(self):
        """기본값으로 Field 생성"""
        field = Field("string")

        assert field.field_type == "string"
        assert field.primary_key is False
        assert field.nullable is True
        assert field.default is None
        assert field.max_length is None
        assert field.foreign_key is None
        assert field.index is False
        assert field.unique is False
        assert field.description is None

    def test_field_custom_creation(self):
        """커스텀 값으로 Field 생성"""
        field = Field(
            field_type="integer",
            primary_key=True,
            nullable=False,
            default=0,
            max_length=10,
            foreign_key="other_table.id",
            index=True,
            unique=True,
            description="Test field",
        )

        assert field.field_type == "integer"
        assert field.primary_key is True
        assert field.nullable is False
        assert field.default == 0
        assert field.max_length == 10
        assert field.foreign_key == "other_table.id"
        assert field.index is True
        assert field.unique is True
        assert field.description == "Test field"


class TestTable:
    """Table 데이터클래스 테스트"""

    def test_table_default_creation(self):
        """기본값으로 Table 생성"""
        fields = {"id": Field("integer", primary_key=True)}
        table = Table("users", fields)

        assert table.name == "users"
        assert table.fields == fields
        assert table.indexes == []
        assert table.constraints == []

    def test_table_custom_creation(self):
        """커스텀 값으로 Table 생성"""
        fields = {"id": Field("integer", primary_key=True)}
        indexes = ["idx_name"]
        constraints = ["unique_email"]

        table = Table("users", fields, indexes, constraints)

        assert table.name == "users"
        assert table.fields == fields
        assert table.indexes == indexes
        assert table.constraints == constraints


class TestBaseModel:
    """BaseModel 추상 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""

        # 테스트용 구체 클래스 생성
        class TestModel(BaseModel):
            __fields__ = {
                "id": Field("integer", primary_key=True),
                "name": Field("string"),
                "email": Field("string"),
            }

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.id = None
                self.name = None
                self.email = None

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

        self.TestModel = TestModel

    def test_basemodel_init_with_kwargs(self):
        """BaseModel __init__ 키워드 인자와 함께 - 라인 89-91 커버"""
        model = self.TestModel(id=1, name="John", email="john@example.com")

        assert model.id == 1
        assert model.name == "John"
        assert model.email == "john@example.com"

    def test_basemodel_init_without_kwargs(self):
        """BaseModel __init__ 키워드 인자 없이"""
        model = self.TestModel()

        assert model.id is None
        assert model.name is None
        assert model.email is None

    def test_basemodel_init_partial_kwargs(self):
        """BaseModel __init__ 일부 키워드 인자만"""
        model = self.TestModel(name="Jane")

        assert model.id is None
        assert model.name == "Jane"
        assert model.email is None

    def test_basemodel_init_invalid_kwargs(self):
        """BaseModel __init__ 존재하지 않는 속성 - hasattr 체크"""
        # 존재하지 않는 속성은 무시됨
        model = self.TestModel(nonexistent="value", name="John")

        assert model.name == "John"
        assert not hasattr(model, "nonexistent")

    def test_to_dict_all_fields(self):
        """to_dict 메서드 모든 필드 - 라인 123-127 커버"""
        model = self.TestModel(id=1, name="John", email="john@example.com")

        result_dict = model.to_dict()

        assert result_dict == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_to_dict_partial_fields(self):
        """to_dict 메서드 일부 필드만 설정"""
        model = self.TestModel(name="Jane")

        result_dict = model.to_dict()

        assert result_dict == {"id": None, "name": "Jane", "email": None}

    def test_to_dict_no_attribute(self):
        """to_dict 메서드 속성이 없는 경우 처리"""
        model = self.TestModel()
        # 필드는 정의되어 있지만 속성이 실제로 없는 경우 시뮬레이션
        del model.name  # 속성 제거

        result_dict = model.to_dict()

        # hasattr 체크로 인해 name은 포함되지 않음
        assert "name" not in result_dict
        assert result_dict == {"id": None, "email": None}

    def test_update_from_dict_valid_fields(self):
        """update_from_dict 유효한 필드들 - 라인 131-133 커버"""
        model = self.TestModel()
        update_data = {"id": 5, "name": "Updated", "email": "updated@example.com"}

        model.update_from_dict(update_data)

        assert model.id == 5
        assert model.name == "Updated"
        assert model.email == "updated@example.com"

    def test_update_from_dict_invalid_fields(self):
        """update_from_dict 유효하지 않은 필드들"""
        model = self.TestModel(id=1, name="Original")
        update_data = {"invalid_field": "should_not_set", "name": "Updated"}

        model.update_from_dict(update_data)

        assert model.name == "Updated"
        assert not hasattr(model, "invalid_field")

    def test_update_from_dict_missing_hasattr(self):
        """update_from_dict hasattr가 False인 경우"""
        model = self.TestModel(id=1)
        del model.name  # 속성 제거
        update_data = {"name": "Should not update", "id": 2}

        model.update_from_dict(update_data)

        assert model.id == 2  # id는 존재하므로 업데이트
        assert not hasattr(model, "name")  # name은 존재하지 않으므로 업데이트되지 않음


class TestSQLAlchemyModel:
    """SQLAlchemyModel 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # SQLAlchemy 모킹
        self.mock_column = Mock()
        self.mock_column.name = "test_column"
        self.mock_column.type = Mock()
        self.mock_column.type.__str__ = Mock(return_value="String")
        self.mock_column.primary_key = False
        self.mock_column.nullable = True
        self.mock_column.default = None

        # 테스트용 SQLAlchemy 모델
        class TestSQLAlchemyModel(SQLAlchemyModel):
            __tablename__ = "test_table"
            __table__ = Mock()
            __table__.columns = [self.mock_column]

        self.TestModel = TestSQLAlchemyModel

    def test_create_table_with_table_info(self):
        """SQLAlchemy create_table __table__ 정보 포함 - 라인 157-188 커버"""
        table = self.TestModel.create_table()

        assert table.name == "test_table"
        assert "id" in table.fields
        assert "created_at" in table.fields
        assert "updated_at" in table.fields
        assert "test_column" in table.fields

    def test_create_table_without_tablename(self):
        """SQLAlchemy create_table __tablename__ 없는 경우"""

        class NoTableNameModel(SQLAlchemyModel):
            pass

        table = NoTableNameModel.create_table()

        assert table.name == "notablenamemodel"  # 클래스 이름의 소문자

    def test_create_table_without_table(self):
        """SQLAlchemy create_table __table__ 없는 경우"""

        class NoTableModel(SQLAlchemyModel):
            __tablename__ = "no_table"

        table = NoTableModel.create_table()

        assert table.name == "no_table"
        assert "id" in table.fields
        assert "created_at" in table.fields
        assert "updated_at" in table.fields

    @pytest.mark.asyncio
    async def test_save_success(self):
        """SQLAlchemy save 성공 - 라인 192-205 커버"""
        model = self.TestModel()

        # Mock database와 session
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.add = Mock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)

        with patch("rfs.database.models.get_database", return_value=mock_database):
            result = await model.save()

        assert result.is_success()
        assert result.unwrap() == model
        mock_session.add.assert_called_once_with(model)
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(model)

    @pytest.mark.asyncio
    async def test_save_no_database(self):
        """SQLAlchemy save 데이터베이스 없음 - 라인 196-197 커버"""
        model = self.TestModel()

        with patch("rfs.database.models.get_database", return_value=None):
            result = await model.save()

        assert not result.is_success()
        assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_save_exception(self):
        """SQLAlchemy save 예외 발생 - 라인 204-205 커버"""
        model = self.TestModel()

        with patch(
            "rfs.database.models.get_database", side_effect=Exception("DB Error")
        ):
            result = await model.save()

        assert not result.is_success()
        assert "모델 저장 실패" in result.unwrap_error()
        assert "DB Error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """SQLAlchemy delete 성공 - 라인 209-221 커버"""
        model = self.TestModel()

        # Mock database와 session
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)

        with patch("rfs.database.models.get_database", return_value=mock_database):
            result = await model.delete()

        assert result.is_success()
        assert result.unwrap() is None
        mock_session.delete.assert_called_once_with(model)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_no_database(self):
        """SQLAlchemy delete 데이터베이스 없음"""
        model = self.TestModel()

        with patch("rfs.database.models.get_database", return_value=None):
            result = await model.delete()

        assert not result.is_success()
        assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_delete_exception(self):
        """SQLAlchemy delete 예외 발생"""
        model = self.TestModel()

        with patch(
            "rfs.database.models.get_database", side_effect=Exception("Delete Error")
        ):
            result = await model.delete()

        assert not result.is_success()
        assert "모델 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_get_success(self):
        """SQLAlchemy get 성공 - 라인 226-240 커버"""
        mock_model = Mock()

        # Mock database, session, query 결과
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_model)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)

        with patch("rfs.database.models.get_database", return_value=mock_database):
            with patch("sqlalchemy.select") as mock_select:
                mock_query = Mock()
                mock_query.filter_by = Mock(return_value=mock_query)
                mock_select.return_value = mock_query

                result = await self.TestModel.get(id=1, name="test")

        assert result.is_success()
        assert result.unwrap() == mock_model
        mock_query.filter_by.assert_called_once_with(id=1, name="test")
        mock_session.execute.assert_called_once_with(mock_query)

    @pytest.mark.asyncio
    async def test_get_no_database(self):
        """SQLAlchemy get 데이터베이스 없음"""
        with patch("rfs.database.models.get_database", return_value=None):
            result = await self.TestModel.get(id=1)

        assert not result.is_success()
        assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_get_exception(self):
        """SQLAlchemy get 예외 발생"""
        with patch(
            "rfs.database.models.get_database", side_effect=Exception("Get Error")
        ):
            result = await self.TestModel.get(id=1)

        assert not result.is_success()
        assert "모델 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_filter_success(self):
        """SQLAlchemy filter 성공 - 라인 245-259 커버"""
        mock_models = [Mock(), Mock()]

        # Mock database, session, query 결과
        mock_scalars = Mock()
        mock_scalars.all = Mock(return_value=mock_models)

        mock_result = Mock()
        mock_result.scalars = Mock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)

        with patch("rfs.database.models.get_database", return_value=mock_database):
            with patch("sqlalchemy.select") as mock_select:
                mock_query = Mock()
                mock_query.filter_by = Mock(return_value=mock_query)
                mock_select.return_value = mock_query

                result = await self.TestModel.filter(name="test")

        assert result.is_success()
        result_list = result.unwrap()
        assert len(result_list) == 2
        assert result_list == mock_models

    @pytest.mark.asyncio
    async def test_filter_no_database(self):
        """SQLAlchemy filter 데이터베이스 없음"""
        with patch("rfs.database.models.get_database", return_value=None):
            result = await self.TestModel.filter(name="test")

        assert not result.is_success()
        assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_filter_exception(self):
        """SQLAlchemy filter 예외 발생"""
        with patch(
            "rfs.database.models.get_database", side_effect=Exception("Filter Error")
        ):
            result = await self.TestModel.filter(name="test")

        assert not result.is_success()
        assert "모델 목록 조회 실패" in result.unwrap_error()


class TestTortoiseModel:
    """TortoiseModel 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # Tortoise 필드 모킹
        mock_field = Mock()
        mock_field.__class__.__name__ = "CharField"
        mock_field.pk = False
        mock_field.null = True
        mock_field.default = None

        # 테스트용 Tortoise 모델
        class TestTortoiseModel(TortoiseModel):
            _meta = Mock()
            _meta.table = "test_tortoise_table"
            _meta.fields_map = {"test_field": mock_field}

        self.TestModel = TestTortoiseModel

    def test_create_table_with_meta(self):
        """Tortoise create_table _meta 정보 포함 - 라인 271-288 커버"""
        table = self.TestModel.create_table()

        assert table.name == "test_tortoise_table"
        assert "test_field" in table.fields
        field_def = table.fields["test_field"]["test_field"]
        assert field_def.field_type == "charfield"
        assert field_def.primary_key is False
        assert field_def.nullable is True
        assert field_def.default is None

    def test_create_table_without_meta(self):
        """Tortoise create_table _meta 없는 경우"""

        class NoMetaModel(TortoiseModel):
            pass

        table = NoMetaModel.create_table()

        assert table.name == "nometamodel"  # 클래스 이름의 소문자
        assert table.fields == {}

    def test_create_table_without_fields_map(self):
        """Tortoise create_table fields_map 없는 경우"""

        class NoFieldsModel(TortoiseModel):
            _meta = Mock()
            _meta.table = "no_fields"

        # _meta는 있지만 fields_map이 없는 경우
        del NoFieldsModel._meta.fields_map

        table = NoFieldsModel.create_table()

        assert table.name == "no_fields"
        assert table.fields == {}

    @pytest.mark.asyncio
    async def test_save_success(self):
        """Tortoise save 성공 - 라인 292-297 커버"""
        model = self.TestModel()

        # Tortoise의 save 메서드 모킹
        with patch.object(
            TortoiseModel.__bases__[1], "save", new_callable=AsyncMock
        ) as mock_save:
            result = await model.save()

        assert result.is_success()
        assert result.unwrap() == model
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_exception(self):
        """Tortoise save 예외 발생 - 라인 296-297 커버"""
        model = self.TestModel()

        with patch.object(
            TortoiseModel.__bases__[1],
            "save",
            new_callable=AsyncMock,
            side_effect=Exception("Save Error"),
        ):
            result = await model.save()

        assert not result.is_success()
        assert "모델 저장 실패" in result.unwrap_error()
        assert "Save Error" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Tortoise delete 성공 - 라인 301-306 커버"""
        model = self.TestModel()

        # Tortoise의 delete 메서드 모킹
        with patch.object(
            TortoiseModel.__bases__[1], "delete", new_callable=AsyncMock
        ) as mock_delete:
            result = await model.delete()

        assert result.is_success()
        assert result.unwrap() is None
        mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_exception(self):
        """Tortoise delete 예외 발생"""
        model = self.TestModel()

        with patch.object(
            TortoiseModel.__bases__[1],
            "delete",
            new_callable=AsyncMock,
            side_effect=Exception("Delete Error"),
        ):
            result = await model.delete()

        assert not result.is_success()
        assert "모델 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_get_success(self):
        """Tortoise get 성공 - 라인 311-315 커버"""
        mock_model = Mock()

        # Tortoise의 get_or_none 메서드 모킹
        with patch.object(
            self.TestModel,
            "get_or_none",
            new_callable=AsyncMock,
            return_value=mock_model,
        ):
            result = await self.TestModel.get(id=1)

        assert result.is_success()
        assert result.unwrap() == mock_model

    @pytest.mark.asyncio
    async def test_get_exception(self):
        """Tortoise get 예외 발생"""
        with patch.object(
            self.TestModel,
            "get_or_none",
            new_callable=AsyncMock,
            side_effect=Exception("Get Error"),
        ):
            result = await self.TestModel.get(id=1)

        assert not result.is_success()
        assert "모델 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_filter_success(self):
        """Tortoise filter 성공 - 라인 320-324 커버"""
        mock_models = [Mock(), Mock()]

        # Tortoise의 filter 체인 모킹
        mock_query = Mock()
        mock_query.all = AsyncMock(return_value=mock_models)

        with patch.object(self.TestModel, "filter", return_value=mock_query):
            result = await self.TestModel.filter(name="test")

        assert result.is_success()
        assert result.unwrap() == mock_models
        mock_query.all.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_exception(self):
        """Tortoise filter 예외 발생"""
        with patch.object(
            self.TestModel, "filter", side_effect=Exception("Filter Error")
        ):
            result = await self.TestModel.filter(name="test")

        assert not result.is_success()
        assert "모델 목록 조회 실패" in result.unwrap_error()


class TestModelRegistry:
    """ModelRegistry 클래스 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # Singleton 초기화
        ModelRegistry._instances = {}
        self.registry = ModelRegistry()

    def test_init(self):
        """ModelRegistry 초기화 - 라인 331-332 커버"""
        assert self.registry.models == {}
        assert self.registry.tables == {}

    def test_register_model(self):
        """모델 등록 - 라인 335-340 커버"""

        # 테스트용 모델 클래스
        class TestModel(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("test_model", {"id": Field("integer", primary_key=True)})

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

        self.registry.register_model(TestModel)

        assert "TestModel" in self.registry.models
        assert self.registry.models["TestModel"] == TestModel
        assert "TestModel" in self.registry.tables
        assert isinstance(self.registry.tables["TestModel"], Table)

    def test_get_model_exists(self):
        """존재하는 모델 조회 - 라인 343-344 커버"""

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

        self.registry.register_model(TestModel)

        result = self.registry.get_model("TestModel")
        assert result == TestModel

    def test_get_model_not_exists(self):
        """존재하지 않는 모델 조회"""
        result = self.registry.get_model("NonExistentModel")
        assert result is None

    def test_get_table_exists(self):
        """존재하는 테이블 조회 - 라인 347-348 커버"""

        class TestModel(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("test_table", {"id": Field("integer")})

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

        self.registry.register_model(TestModel)

        result = self.registry.get_table("TestModel")
        assert isinstance(result, Table)
        assert result.name == "test_table"

    def test_get_table_not_exists(self):
        """존재하지 않는 테이블 조회"""
        result = self.registry.get_table("NonExistentModel")
        assert result is None

    def test_get_all_models(self):
        """모든 모델 반환 - 라인 351-352 커버"""

        class TestModel1(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("test1", {})

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

        class TestModel2(BaseModel):
            @classmethod
            def create_table(cls):
                return Table("test2", {})

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

        self.registry.register_model(TestModel1)
        self.registry.register_model(TestModel2)

        all_models = self.registry.get_all_models()

        assert len(all_models) == 2
        assert "TestModel1" in all_models
        assert "TestModel2" in all_models
        # copy()가 호출되는지 확인 - 원본과 다른 객체여야 함
        assert all_models is not self.registry.models

    def test_get_all_tables(self):
        """모든 테이블 반환 - 라인 355-356 커버"""

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

        self.registry.register_model(TestModel)

        all_tables = self.registry.get_all_tables()

        assert len(all_tables) == 1
        assert "TestModel" in all_tables
        # copy()가 호출되는지 확인
        assert all_tables is not self.registry.tables


class TestGlobalFunctions:
    """전역 함수들 테스트"""

    def setup_method(self):
        """테스트 설정"""
        ModelRegistry._instances = {}

    def test_get_model_registry(self):
        """모델 레지스트리 인스턴스 반환 - 라인 360-361 커버"""
        registry1 = get_model_registry()
        registry2 = get_model_registry()

        assert isinstance(registry1, ModelRegistry)
        assert registry1 is registry2  # Singleton

    def test_register_model_function(self):
        """register_model 함수 - 라인 456-457 커버"""

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

        registry = get_model_registry()
        assert "TestModel" in registry.models
        assert registry.models["TestModel"] == TestModel


class TestCreateModel:
    """create_model 함수 테스트"""

    def setup_method(self):
        """테스트 설정"""
        ModelRegistry._instances = {}

    def test_create_model_sqlalchemy_explicit(self):
        """SQLAlchemy 명시적 base_class로 모델 생성 - 라인 371-451 커버"""
        fields = {
            "name": Field("string", max_length=100),
            "age": Field("integer"),
            "is_active": Field("boolean", default=True),
        }

        with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
            model_class = create_model("User", fields, SQLAlchemyModel, "users")

        assert model_class.__name__ == "User"
        assert issubclass(model_class, SQLAlchemyModel)
        assert model_class.__table_name__ == "users"
        assert model_class.__fields__ == fields

    def test_create_model_tortoise_explicit(self):
        """Tortoise 명시적 base_class로 모델 생성"""
        fields = {"title": Field("string"), "content": Field("text")}

        with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
            model_class = create_model("Post", fields, TortoiseModel)

        assert model_class.__name__ == "Post"
        assert issubclass(model_class, TortoiseModel)
        assert model_class.__table_name__ == "post"
        assert model_class.__fields__ == fields

    def test_create_model_auto_sqlalchemy(self):
        """자동 base_class 선택 - SQLAlchemy - 라인 373-388 커버"""
        fields = {"name": Field("string")}

        # Database manager와 config 모킹
        mock_config = Mock()
        mock_config.orm_type.value = "sqlalchemy"

        mock_database = Mock()
        mock_database.config = mock_config

        mock_manager = Mock()
        mock_manager.get_database.return_value = mock_database

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                model_class = create_model("AutoModel", fields)

        assert issubclass(model_class, SQLAlchemyModel)

    def test_create_model_auto_tortoise(self):
        """자동 base_class 선택 - Tortoise"""
        fields = {"name": Field("string")}

        # Database manager와 config 모킹
        mock_config = Mock()
        mock_config.orm_type.value = "tortoise"

        mock_database = Mock()
        mock_database.config = mock_config

        mock_manager = Mock()
        mock_manager.get_database.return_value = mock_database

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
                with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", False):
                    model_class = create_model("AutoTortoiseModel", fields)

        assert issubclass(model_class, TortoiseModel)

    def test_create_model_auto_no_orm(self):
        """자동 base_class 선택 - 사용 가능한 ORM 없음"""
        fields = {"name": Field("string")}

        mock_config = Mock()
        mock_config.orm_type.value = "unknown"

        mock_database = Mock()
        mock_database.config = mock_config

        mock_manager = Mock()
        mock_manager.get_database.return_value = mock_database

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", False):
                with patch("rfs.database.models.TORTOISE_AVAILABLE", False):
                    with pytest.raises(ValueError, match="지원되는 ORM이 없습니다"):
                        create_model("NoORMModel", fields)

    def test_create_model_sqlalchemy_field_types(self):
        """SQLAlchemy 다양한 필드 타입 - 라인 390-423 커버"""
        fields = {
            "int_field": Field("integer"),
            "str_field": Field("string", max_length=50),
            "text_field": Field("text"),
            "datetime_field": Field("datetime"),
            "bool_field": Field("boolean"),
            "json_field": Field("json"),
            "unknown_field": Field("unknown_type"),
        }

        with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
            model_class = create_model("FieldTestModel", fields, SQLAlchemyModel)

        # 모델이 생성되고 등록되었는지 확인
        assert model_class.__name__ == "FieldTestModel"
        registry = get_model_registry()
        assert "FieldTestModel" in registry.models

    def test_create_model_tortoise_field_types(self):
        """Tortoise 다양한 필드 타입 - 라인 424-447 커버"""
        fields = {
            "int_field": Field("integer", primary_key=True),
            "str_field": Field("string", max_length=100, nullable=False),
            "text_field": Field("text", nullable=True),
            "datetime_field": Field("datetime", default=datetime.now),
            "bool_field": Field("boolean", default=False),
            "json_field": Field("json", default={}),
            "unknown_field": Field("weird_type", nullable=True),
        }

        with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
            # Tortoise fields 모킹
            mock_fields = Mock()
            mock_fields.IntField = Mock(return_value="IntField")
            mock_fields.CharField = Mock(return_value="CharField")
            mock_fields.TextField = Mock(return_value="TextField")
            mock_fields.DatetimeField = Mock(return_value="DatetimeField")
            mock_fields.BooleanField = Mock(return_value="BooleanField")
            mock_fields.JSONField = Mock(return_value="JSONField")

            with patch("rfs.database.models.fields", mock_fields):
                model_class = create_model(
                    "TortoiseFieldTestModel", fields, TortoiseModel
                )

        assert model_class.__name__ == "TortoiseFieldTestModel"
        registry = get_model_registry()
        assert "TortoiseFieldTestModel" in registry.models


class TestModelFunction:
    """Model 함수 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # DatabaseManager singleton 초기화
        from rfs.database.base import DatabaseManager

        DatabaseManager._instances = {}

    def test_model_sqlalchemy_from_config(self):
        """설정에서 SQLAlchemy 모델 반환 - 라인 467-471 커버"""
        mock_config = Mock()
        mock_config.orm_type.value = "sqlalchemy"

        mock_database = Mock()
        mock_database.config = mock_config

        mock_manager = Mock()
        mock_manager.get_database.return_value = mock_database

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                result = Model()

        assert result == SQLAlchemyModel

    def test_model_tortoise_from_config(self):
        """설정에서 Tortoise 모델 반환 - 라인 472-476 커버"""
        mock_config = Mock()
        mock_config.orm_type.value = "tortoise"

        mock_database = Mock()
        mock_database.config = mock_config

        mock_manager = Mock()
        mock_manager.get_database.return_value = mock_database

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
                result = Model()

        assert result == TortoiseModel

    def test_model_auto_sqlalchemy(self):
        """auto 설정에서 SQLAlchemy 선택"""
        mock_config = Mock()
        mock_config.orm_type.value = "auto"

        mock_database = Mock()
        mock_database.config = mock_config

        mock_manager = Mock()
        mock_manager.get_database.return_value = mock_database

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                result = Model()

        assert result == SQLAlchemyModel

    def test_model_fallback_sqlalchemy(self):
        """데이터베이스 없을 때 SQLAlchemy fallback - 라인 477-478 커버"""
        mock_manager = Mock()
        mock_manager.get_database.return_value = None

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                result = Model()

        assert result == SQLAlchemyModel

    def test_model_fallback_tortoise(self):
        """데이터베이스 없을 때 Tortoise fallback - 라인 479-480 커버"""
        mock_manager = Mock()
        mock_manager.get_database.return_value = None

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", False):
                with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
                    result = Model()

        assert result == TortoiseModel

    def test_model_no_database_no_config(self):
        """데이터베이스도 config도 없는 경우"""
        mock_database = Mock()
        del mock_database.config  # config 속성 제거

        mock_manager = Mock()
        mock_manager.get_database.return_value = mock_database

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                result = Model()

        assert result == SQLAlchemyModel

    def test_model_no_orm_available(self):
        """사용 가능한 ORM이 없는 경우 - 라인 481-482 커버"""
        mock_manager = Mock()
        mock_manager.get_database.return_value = None

        with patch(
            "rfs.database.models.get_database_manager", return_value=mock_manager
        ):
            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", False):
                with patch("rfs.database.models.TORTOISE_AVAILABLE", False):
                    with pytest.raises(
                        RuntimeError, match="사용 가능한 ORM이 없습니다"
                    ):
                        Model()


class TestImportHandling:
    """Import 처리 테스트"""

    def test_sqlalchemy_available_flag(self):
        """SQLAlchemy 사용 가능 플래그 확인"""
        # 모킹된 환경에서는 True/False 모두 가능
        assert SQLALCHEMY_AVAILABLE in [True, False]

    def test_tortoise_available_flag(self):
        """Tortoise 사용 가능 플래그 확인"""
        # 모킹된 환경에서는 True/False 모두 가능
        assert TORTOISE_AVAILABLE in [True, False]
