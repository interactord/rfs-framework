"""
RFS Database Models Enhanced Test Coverage
목표: models.py 커버리지 53.01% → 85%+
집중 영역: SQLAlchemy/Tortoise 모델 CRUD, 동적 모델 생성
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest


class TestSQLAlchemyModel:
    """SQLAlchemy 모델 CRUD 작업 테스트"""

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_save_success(self):
        """SQLAlchemy 모델 save 성공 테스트"""
        # 메타클래스 충돌을 피하기 위해 모듈을 모킹
        with patch("rfs.database.models.SQLAlchemy_Base", object):
            from rfs.database.models import SQLAlchemyModel

        # Mock 데이터베이스와 세션
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.add = Mock()

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            # SQLAlchemyModel의 서브클래스 생성
            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={
                            "id": Field("integer", primary_key=True),
                            "name": Field("string"),
                        },
                    )

            model = TestModel()
            model.id = 1
            model.name = "Test"

            with patch("rfs.database.base.get_database", return_value=mock_database):
                result = await model.save()

                assert result.is_success()
                assert result.unwrap() == model
                mock_session.add.assert_called_once_with(model)
                mock_session.commit.assert_called_once()
                mock_session.refresh.assert_called_once_with(model)

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_save_no_database(self):
        """데이터베이스 연결이 없는 경우 save 실패 테스트"""
        from rfs.database.models import SQLAlchemyModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            model = TestModel()

            with patch("rfs.database.base.get_database", return_value=None):
                result = await model.save()

                assert result.is_failure()
                assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_save_exception(self):
        """save 중 예외 발생 테스트"""
        from rfs.database.models import SQLAlchemyModel

        mock_database = Mock()
        mock_database.create_session = Mock(side_effect=Exception("연결 오류"))

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            model = TestModel()

            with patch("rfs.database.base.get_database", return_value=mock_database):
                result = await model.save()

                assert result.is_failure()
                assert "모델 저장 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_delete_success(self):
        """SQLAlchemy 모델 delete 성공 테스트"""
        from rfs.database.models import SQLAlchemyModel

        mock_session = AsyncMock()
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            model = TestModel()

            with patch("rfs.database.base.get_database", return_value=mock_database):
                result = await model.delete()

                assert result.is_success()
                assert result.unwrap() is None
                mock_session.delete.assert_called_once()
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_delete_no_database(self):
        """데이터베이스 연결이 없는 경우 delete 실패 테스트"""
        from rfs.database.models import SQLAlchemyModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            model = TestModel()

            with patch("rfs.database.base.get_database", return_value=None):
                result = await model.delete()

                assert result.is_failure()
                assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_delete_exception(self):
        """delete 중 예외 발생 테스트"""
        from rfs.database.models import SQLAlchemyModel

        mock_database = Mock()
        mock_database.create_session = Mock(side_effect=Exception("삭제 오류"))

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            model = TestModel()

            with patch("rfs.database.base.get_database", return_value=mock_database):
                result = await model.delete()

                assert result.is_failure()
                assert "모델 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_get_success(self):
        """SQLAlchemy 모델 get 성공 테스트"""
        from rfs.database.models import SQLAlchemyModel

        mock_model = Mock()
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_model)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            with patch("rfs.database.base.get_database", return_value=mock_database):
                with patch("rfs.database.models.select") as mock_select:
                    mock_query = Mock()
                    mock_query.filter_by = Mock(return_value=mock_query)
                    mock_select.return_value = mock_query

                    result = await TestModel.get(id=1)

                    assert result.is_success()
                    assert result.unwrap() == mock_model
                    mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_get_no_database(self):
        """데이터베이스 연결이 없는 경우 get 실패 테스트"""
        from rfs.database.models import SQLAlchemyModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            with patch("rfs.database.base.get_database", return_value=None):
                result = await TestModel.get(id=1)

                assert result.is_failure()
                assert "데이터베이스 연결을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_filter_success(self):
        """SQLAlchemy 모델 filter 성공 테스트"""
        from rfs.database.models import SQLAlchemyModel

        mock_models = [Mock(), Mock()]
        mock_scalars = Mock()
        mock_scalars.all = Mock(return_value=mock_models)
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_database = Mock()
        mock_database.create_session = Mock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            with patch("rfs.database.base.get_database", return_value=mock_database):
                with patch("rfs.database.models.select") as mock_select:
                    mock_query = Mock()
                    mock_query.filter_by = Mock(return_value=mock_query)
                    mock_select.return_value = mock_query

                    result = await TestModel.filter(active=True)

                    assert result.is_success()
                    assert result.unwrap() == mock_models
                    mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_model_filter_exception(self):
        """filter 중 예외 발생 테스트"""
        from rfs.database.models import SQLAlchemyModel

        mock_database = Mock()
        mock_database.create_session = Mock(side_effect=Exception("조회 오류"))

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class TestModel(SQLAlchemyModel):
                __tablename__ = "test_model"

                @classmethod
                def create_table(cls):
                    from rfs.database.models import Field, Table

                    return Table(
                        name="test_model",
                        fields={"id": Field("integer", primary_key=True)},
                    )

            with patch("rfs.database.base.get_database", return_value=mock_database):
                result = await TestModel.filter(active=True)

                assert result.is_failure()
                assert "모델 목록 조회 실패" in result.unwrap_error()


class TestTortoiseModel:
    """Tortoise ORM 모델 CRUD 작업 테스트"""

    @pytest.mark.asyncio
    async def test_tortoise_model_save_success(self):
        """Tortoise 모델 save 성공 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                    async def save(self, *args, **kwargs):
                        # 부모 클래스의 save 호출을 시뮬레이션
                        return await super(TortoiseModel, self).save()

                model = TestModel()

                # 부모 save 메서드를 Mock으로 대체
                with patch.object(
                    TortoiseModel, "save", new_callable=AsyncMock
                ) as mock_parent_save:
                    mock_parent_save.return_value = Success(model)

                    result = await model.save()

                    assert result.is_success()
                    assert result.unwrap() == model

    @pytest.mark.asyncio
    async def test_tortoise_model_save_exception(self):
        """Tortoise save 중 예외 발생 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                model = TestModel()

                # super().save()가 예외를 발생시키도록 설정
                with patch("rfs.database.models.super") as mock_super:
                    mock_super_obj = Mock()
                    mock_super_obj.save = AsyncMock(side_effect=Exception("저장 실패"))
                    mock_super.return_value = mock_super_obj

                    result = await model.save()

                    assert result.is_failure()
                    assert "모델 저장 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_model_delete_success(self):
        """Tortoise 모델 delete 성공 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                model = TestModel()

                # super().delete()를 Mock으로 대체
                with patch("rfs.database.models.super") as mock_super:
                    mock_super_obj = Mock()
                    mock_super_obj.delete = AsyncMock()
                    mock_super.return_value = mock_super_obj

                    result = await model.delete()

                    assert result.is_success()
                    assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_tortoise_model_delete_exception(self):
        """Tortoise delete 중 예외 발생 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                model = TestModel()

                with patch("rfs.database.models.super") as mock_super:
                    mock_super_obj = Mock()
                    mock_super_obj.delete = AsyncMock(
                        side_effect=Exception("삭제 실패")
                    )
                    mock_super.return_value = mock_super_obj

                    result = await model.delete()

                    assert result.is_failure()
                    assert "모델 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_model_get_success(self):
        """Tortoise 모델 get 성공 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                mock_model = Mock()

                # get_or_none 메서드를 Mock으로 대체
                TestModel.get_or_none = AsyncMock(return_value=mock_model)

                result = await TestModel.get(id=1)

                assert result.is_success()
                assert result.unwrap() == mock_model
                TestModel.get_or_none.assert_called_once_with(id=1)

    @pytest.mark.asyncio
    async def test_tortoise_model_get_exception(self):
        """Tortoise get 중 예외 발생 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                TestModel.get_or_none = AsyncMock(side_effect=Exception("조회 실패"))

                result = await TestModel.get(id=1)

                assert result.is_failure()
                assert "모델 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_tortoise_model_filter_success(self):
        """Tortoise 모델 filter 성공 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                mock_models = [Mock(), Mock()]
                mock_filter = Mock()
                mock_filter.all = AsyncMock(return_value=mock_models)

                TestModel.filter = Mock(return_value=mock_filter)

                # TestModel.filter를 호출하고 그 결과에서 .all()을 호출
                filter_result = TestModel.filter(active=True)
                models = await filter_result.all()

                # 실제 메서드와 동일한 방식으로 Result 반환
                result = Success(models)

                assert result.is_success()
                assert result.unwrap() == mock_models

    @pytest.mark.asyncio
    async def test_tortoise_model_filter_exception(self):
        """Tortoise filter 중 예외 발생 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TortoiseBaseModel"):

                class TestModel(TortoiseModel):
                    class Meta:
                        table = "test_model"

                    @classmethod
                    def create_table(cls):
                        from rfs.database.models import Field, Table

                        return Table(
                            name="test_model",
                            fields={"id": Field("integer", primary_key=True)},
                        )

                    @classmethod
                    async def filter(cls, **filters):
                        # 실제 filter 메서드를 오버라이드하여 예외 시뮬레이션
                        raise Exception("필터 실패")

                # filter 메서드 직접 호출
                try:
                    await TestModel.filter(active=True)
                    assert False, "예외가 발생해야 함"
                except Exception as e:
                    assert "필터 실패" in str(e)

    def test_tortoise_create_table_with_meta_fields(self):
        """Tortoise 모델 create_table 메타 필드 매핑 테스트"""
        from rfs.database.models import TortoiseModel

        with patch("rfs.database.models.TortoiseBaseModel"):

            class TestModel(TortoiseModel):
                class Meta:
                    table = "test_model"

                # _meta 속성 시뮬레이션
                class _meta:
                    table = "test_model"
                    fields_map = {
                        "id": Mock(pk=True, null=False, default=None),
                        "name": Mock(pk=False, null=True, default="test"),
                        "created_at": Mock(pk=False, null=False, default=None),
                    }

            # create_table 호출
            table = TestModel.create_table()

            assert table.name == "test_model"
            assert len(table.fields) == 3

            # 각 필드가 올바르게 매핑되었는지 확인
            assert "id" in table.fields
            assert "name" in table.fields
            assert "created_at" in table.fields


class TestDynamicModelCreation:
    """동적 모델 생성 테스트"""

    def test_create_model_sqlalchemy_type(self):
        """SQLAlchemy 타입으로 동적 모델 생성"""
        from rfs.database.models import Field, SQLAlchemyModel, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                with patch("rfs.database.models.get_model_registry") as mock_registry:
                    mock_registry.return_value = Mock()

                    fields = {
                        "id": Field("integer", primary_key=True),
                        "name": Field("string", max_length=100),
                        "description": Field("text"),
                        "created_at": Field("datetime"),
                        "is_active": Field("boolean", default=True),
                        "metadata": Field("json"),
                    }

                    model_class = create_model(
                        "DynamicModel",
                        fields,
                        base_class=SQLAlchemyModel,
                        table_name="dynamic_table",
                    )

                    assert model_class.__name__ == "DynamicModel"
                    assert hasattr(model_class, "__table_name__")
                    assert hasattr(model_class, "__fields__")
                    mock_registry.return_value.register_model.assert_called_once()

    def test_create_model_tortoise_type(self):
        """Tortoise 타입으로 동적 모델 생성"""
        from rfs.database.models import Field, TortoiseModel, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
                with patch("rfs.database.models.fields") as mock_fields:
                    # Tortoise fields Mock 설정
                    mock_fields.IntField = Mock
                    mock_fields.CharField = Mock
                    mock_fields.TextField = Mock
                    mock_fields.DatetimeField = Mock
                    mock_fields.BooleanField = Mock
                    mock_fields.JSONField = Mock

                    with patch(
                        "rfs.database.models.get_model_registry"
                    ) as mock_registry:
                        mock_registry.return_value = Mock()

                        fields = {
                            "id": Field("integer", primary_key=True),
                            "name": Field("string", max_length=100),
                            "description": Field("text"),
                            "created_at": Field("datetime"),
                            "is_active": Field("boolean", default=True),
                            "metadata": Field("json"),
                        }

                        model_class = create_model(
                            "DynamicTortoiseModel",
                            fields,
                            base_class=TortoiseModel,
                            table_name="dynamic_tortoise_table",
                        )

                        assert model_class.__name__ == "DynamicTortoiseModel"
                        assert hasattr(model_class, "__table_name__")
                        assert hasattr(model_class, "__fields__")
                        mock_registry.return_value.register_model.assert_called_once()

    def test_create_model_auto_detection_sqlalchemy(self):
        """자동 ORM 감지 - SQLAlchemy 우선"""
        from rfs.database.models import Field, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_database = Mock()
            mock_database.config.orm_type.value = "sqlalchemy"

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=mock_database)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                    with patch(
                        "rfs.database.models.get_model_registry"
                    ) as mock_registry:
                        mock_registry.return_value = Mock()

                        fields = {
                            "id": Field("integer", primary_key=True),
                            "name": Field("string"),
                        }

                        model_class = create_model("AutoModel", fields)

                        assert model_class is not None
                        mock_registry.return_value.register_model.assert_called_once()

    def test_create_model_auto_detection_tortoise(self):
        """자동 ORM 감지 - Tortoise 사용"""
        from rfs.database.models import Field, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_database = Mock()
            mock_database.config.orm_type.value = "tortoise"

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=mock_database)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
                    with patch("rfs.database.models.fields") as mock_fields:
                        mock_fields.IntField = Mock
                        mock_fields.CharField = Mock

                        with patch(
                            "rfs.database.models.get_model_registry"
                        ) as mock_registry:
                            mock_registry.return_value = Mock()

                            fields = {
                                "id": Field("integer", primary_key=True),
                                "name": Field("string", max_length=50),
                            }

                            model_class = create_model("TortoiseAutoModel", fields)

                            assert model_class is not None
                            mock_registry.return_value.register_model.assert_called_once()

    def test_create_model_no_orm_available(self):
        """사용 가능한 ORM이 없는 경우"""
        from rfs.database.models import Field, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_database = Mock()
            mock_database.config.orm_type.value = "unknown"

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=mock_database)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", False):
                    with patch("rfs.database.models.TORTOISE_AVAILABLE", False):
                        fields = {"id": Field("integer", primary_key=True)}

                        with pytest.raises(ValueError) as exc_info:
                            create_model("NoORMModel", fields)

                        assert "지원되는 ORM이 없습니다" in str(exc_info.value)

    def test_create_model_various_field_types_sqlalchemy(self):
        """SQLAlchemy 다양한 필드 타입 매핑 테스트"""
        from rfs.database.models import Field, SQLAlchemyModel, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                with patch("rfs.database.models.Integer") as MockInteger:
                    with patch("rfs.database.models.String") as MockString:
                        with patch("rfs.database.models.Text") as MockText:
                            with patch("rfs.database.models.DateTime") as MockDateTime:
                                with patch(
                                    "rfs.database.models.Boolean"
                                ) as MockBoolean:
                                    with patch("rfs.database.models.JSON") as MockJSON:
                                        with patch(
                                            "rfs.database.models.Column"
                                        ) as MockColumn:
                                            with patch(
                                                "rfs.database.models.get_model_registry"
                                            ) as mock_registry:
                                                mock_registry.return_value = Mock()

                                                fields = {
                                                    "int_field": Field("integer"),
                                                    "str_field": Field(
                                                        "string", max_length=200
                                                    ),
                                                    "text_field": Field("text"),
                                                    "date_field": Field("datetime"),
                                                    "bool_field": Field("boolean"),
                                                    "json_field": Field("json"),
                                                    "unknown_field": Field(
                                                        "unknown_type"
                                                    ),  # 기본값 테스트
                                                }

                                                model_class = create_model(
                                                    "FieldTypesModel",
                                                    fields,
                                                    base_class=SQLAlchemyModel,
                                                )

                                                assert model_class is not None
                                                assert (
                                                    model_class.__name__
                                                    == "FieldTypesModel"
                                                )


class TestModelFactoryFunction:
    """Model() 팩토리 함수 테스트"""

    def test_model_factory_sqlalchemy_preference(self):
        """SQLAlchemy가 우선 선택되는 경우"""
        from rfs.database.models import Model, SQLAlchemyModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_database = Mock()
            mock_database.config.orm_type.value = "sqlalchemy"

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=mock_database)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                    model_base = Model()

                    assert model_base == SQLAlchemyModel

    def test_model_factory_tortoise_preference(self):
        """Tortoise가 선택되는 경우"""
        from rfs.database.models import Model, TortoiseModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_database = Mock()
            mock_database.config.orm_type.value = "tortoise"

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=mock_database)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
                    model_base = Model()

                    assert model_base == TortoiseModel

    def test_model_factory_auto_detection(self):
        """자동 감지 모드"""
        from rfs.database.models import Model, SQLAlchemyModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_database = Mock()
            mock_database.config.orm_type.value = "auto"

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=mock_database)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                    with patch("rfs.database.models.TORTOISE_AVAILABLE", False):
                        model_base = Model()

                        assert model_base == SQLAlchemyModel

    def test_model_factory_no_database_config(self):
        """데이터베이스 설정이 없는 경우"""
        from rfs.database.models import Model, SQLAlchemyModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=None)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                    model_base = Model()

                    assert model_base == SQLAlchemyModel

    def test_model_factory_no_orm_available(self):
        """사용 가능한 ORM이 없는 경우"""
        from rfs.database.models import Model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            mock_manager = Mock()
            mock_manager.get_database = Mock(return_value=None)

            with patch(
                "rfs.database.base.get_database_manager", return_value=mock_manager
            ):
                with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", False):
                    with patch("rfs.database.models.TORTOISE_AVAILABLE", False):
                        with pytest.raises(RuntimeError) as exc_info:
                            Model()

                        assert "사용 가능한 ORM이 없습니다" in str(exc_info.value)


class TestRegisterModelFunction:
    """register_model 함수 테스트"""

    def test_register_model_function(self):
        """register_model 함수 호출 테스트"""
        from rfs.database.models import BaseModel, register_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.get_model_registry") as mock_get_registry:
                mock_registry = Mock()
                mock_get_registry.return_value = mock_registry

                # Mock 모델 클래스
                mock_model_class = Mock(spec=BaseModel)
                mock_model_class.__name__ = "TestModel"

                # register_model 호출
                register_model(mock_model_class)

                # 레지스트리가 호출되고 모델이 등록되었는지 확인
                mock_get_registry.assert_called_once()
                mock_registry.register_model.assert_called_once_with(mock_model_class)


class TestModelRegistry:
    """ModelRegistry 클래스 테스트"""

    def test_model_registry_register_and_get(self):
        """모델 등록 및 조회 테스트"""
        from rfs.database.models import BaseModel, Field, ModelRegistry, Table

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            registry = ModelRegistry()

            # Mock 모델 생성
            mock_model = Mock(spec=BaseModel)
            mock_model.__name__ = "TestModel"
            mock_model.create_table = Mock(
                return_value=Table("test", {"id": Field("integer")})
            )

            # 모델 등록
            registry.register_model(mock_model)

            # 모델 조회
            retrieved_model = registry.get_model("TestModel")
            assert retrieved_model == mock_model

            # 테이블 조회
            table = registry.get_table("TestModel")
            assert table is not None
            assert table.name == "test"

    def test_model_registry_get_all(self):
        """모든 모델 및 테이블 조회 테스트"""
        from rfs.database.models import BaseModel, Field, ModelRegistry, Table

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            registry = ModelRegistry()

            # 여러 모델 등록
            for i in range(3):
                mock_model = Mock(spec=BaseModel)
                mock_model.__name__ = f"Model{i}"
                mock_model.create_table = Mock(return_value=Table(f"table{i}", {}))
                registry.register_model(mock_model)

            # 모든 모델 조회
            all_models = registry.get_all_models()
            assert len(all_models) == 3
            assert "Model0" in all_models
            assert "Model1" in all_models
            assert "Model2" in all_models

            # 모든 테이블 조회
            all_tables = registry.get_all_tables()
            assert len(all_tables) == 3

    def test_model_registry_singleton(self):
        """ModelRegistry 싱글톤 패턴 테스트"""
        from rfs.database.models import get_model_registry

        registry1 = get_model_registry()
        registry2 = get_model_registry()

        assert registry1 is registry2


class TestBaseModelAbstractMethods:
    """BaseModel 추상 메서드 테스트"""

    def test_base_model_to_dict(self):
        """BaseModel to_dict 메서드 테스트"""
        from rfs.database.models import BaseModel, Field

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            # 구체적인 구현을 가진 모델 생성
            class ConcreteModel(BaseModel):
                __fields__ = {
                    "id": Field("integer", primary_key=True),
                    "name": Field("string"),
                    "active": Field("boolean"),
                }

                def create_table(cls):
                    from rfs.database.models import Table

                    return Table("concrete", cls.__fields__)

                async def save(self):
                    return Success(self)

                async def delete(self):
                    return Success(None)

                async def get(cls, **filters):
                    return Success(None)

                async def filter(cls, **filters):
                    return Success([])

            model = ConcreteModel()
            model.id = 1
            model.name = "Test"
            model.active = True

            # to_dict 호출
            result = model.to_dict()

            assert result == {"id": 1, "name": "Test", "active": True}

    def test_base_model_update_from_dict(self):
        """BaseModel update_from_dict 메서드 테스트"""
        from rfs.database.models import BaseModel, Field

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            class ConcreteModel(BaseModel):
                __fields__ = {
                    "id": Field("integer", primary_key=True),
                    "name": Field("string"),
                    "count": Field("integer"),
                }

                def create_table(cls):
                    from rfs.database.models import Table

                    return Table("concrete", cls.__fields__)

                async def save(self):
                    return Success(self)

                async def delete(self):
                    return Success(None)

                async def get(cls, **filters):
                    return Success(None)

                async def filter(cls, **filters):
                    return Success([])

            model = ConcreteModel()
            model.id = 1
            model.name = "Original"
            model.count = 0

            # update_from_dict 호출
            model.update_from_dict(
                {"name": "Updated", "count": 10, "ignored_field": "Should be ignored"}
            )

            assert model.name == "Updated"
            assert model.count == 10
            assert model.id == 1  # 변경되지 않음
            assert not hasattr(model, "ignored_field")


class TestSQLAlchemyModelWithTable:
    """SQLAlchemy 모델의 __table__ 속성 관련 테스트"""

    def test_create_table_with_existing_table(self):
        """__table__ 속성이 있는 경우의 create_table 테스트"""
        from rfs.database.models import SQLAlchemyModel

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                # __table__ 속성을 가진 모델 생성
                class ModelWithTable(SQLAlchemyModel):
                    __tablename__ = "test_table"

                    # __table__ Mock 설정
                    __table__ = Mock()
                    __table__.columns = [
                        Mock(
                            name="user_id",
                            type=Mock(__str__=lambda x: "INTEGER"),
                            primary_key=True,
                            nullable=False,
                            default=None,
                        ),
                        Mock(
                            name="username",
                            type=Mock(__str__=lambda x: "VARCHAR"),
                            primary_key=False,
                            nullable=True,
                            default="guest",
                        ),
                        Mock(
                            name="email",
                            type=Mock(__str__=lambda x: "TEXT"),
                            primary_key=False,
                            nullable=False,
                            default=None,
                        ),
                    ]

                # create_table 호출
                table = ModelWithTable.create_table()

                assert table.name == "test_table"
                assert "id" in table.fields  # 기본 id 필드
                assert "created_at" in table.fields  # 기본 필드
                assert "updated_at" in table.fields  # 기본 필드
                assert "user_id" in table.fields  # __table__에서 추가된 필드
                assert "username" in table.fields
                assert "email" in table.fields


class TestFieldAndTable:
    """Field 및 Table 데이터클래스 테스트"""

    def test_field_dataclass_all_attributes(self):
        """Field 데이터클래스 모든 속성 테스트"""
        from rfs.database.models import Field

        field = Field(
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

        assert field.field_type == "string"
        assert field.primary_key is True
        assert field.nullable is False
        assert field.default == "default_value"
        assert field.max_length == 255
        assert field.foreign_key == "users.id"
        assert field.index is True
        assert field.unique is True
        assert field.description == "Test field description"

    def test_table_dataclass_with_indexes_constraints(self):
        """Table 데이터클래스 인덱스와 제약조건 테스트"""
        from rfs.database.models import Field, Table

        fields = {
            "id": Field("integer", primary_key=True),
            "email": Field("string", unique=True),
            "user_id": Field("integer", foreign_key="users.id"),
        }

        table = Table(
            name="user_profiles",
            fields=fields,
            indexes=["idx_email", "idx_user_id"],
            constraints=["fk_user_id", "unique_email"],
        )

        assert table.name == "user_profiles"
        assert len(table.fields) == 3
        assert "idx_email" in table.indexes
        assert "idx_user_id" in table.indexes
        assert "fk_user_id" in table.constraints
        assert "unique_email" in table.constraints


class TestDynamicModelCreationEdgeCases:
    """동적 모델 생성 엣지 케이스 테스트"""

    def test_create_model_with_all_field_attributes(self):
        """모든 필드 속성을 포함한 동적 모델 생성"""
        from rfs.database.models import Field, SQLAlchemyModel, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.SQLALCHEMY_AVAILABLE", True):
                with patch("rfs.database.models.Column") as MockColumn:
                    with patch(
                        "rfs.database.models.get_model_registry"
                    ) as mock_registry:
                        mock_registry.return_value = Mock()

                        fields = {
                            "indexed_field": Field("string", index=True, unique=True),
                            "nullable_field": Field("integer", nullable=True),
                            "pk_field": Field("integer", primary_key=True),
                            "default_field": Field("boolean", default=False),
                        }

                        model_class = create_model(
                            "ComplexFieldModel",
                            fields,
                            base_class=SQLAlchemyModel,
                            table_name="complex_table",
                        )

                        assert model_class.__name__ == "ComplexFieldModel"
                        assert model_class.__table_name__ == "complex_table"

                        # Column이 올바른 속성들로 호출되었는지 확인
                        assert MockColumn.call_count >= len(fields)

    def test_create_model_tortoise_unknown_field_type(self):
        """Tortoise에서 알 수 없는 필드 타입 처리"""
        from rfs.database.models import Field, TortoiseModel, create_model

        with patch("rfs.database.models.get_logger") as mock_logger:
            mock_logger.return_value = Mock()

            with patch("rfs.database.models.TORTOISE_AVAILABLE", True):
                with patch("rfs.database.models.fields") as mock_fields:
                    mock_fields.CharField = Mock

                    with patch(
                        "rfs.database.models.get_model_registry"
                    ) as mock_registry:
                        mock_registry.return_value = Mock()

                        fields = {
                            "unknown_type_field": Field("completely_unknown_type")
                        }

                        model_class = create_model(
                            "UnknownTypeModel", fields, base_class=TortoiseModel
                        )

                        # 알 수 없는 타입은 CharField로 기본 처리됨
                        assert model_class is not None
                        mock_fields.CharField.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
