"""
RFS Database Models (RFS v4.1) - Refactored
단일 ORM 선택 방식으로 메타클래스 충돌 방지
"""

import inspect
import os
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = get_logger(__name__)

# ORM 선택 - 환경 변수로 결정 (SQLALCHEMY 또는 TORTOISE)
ORM_TYPE = os.environ.get("RFS_ORM_TYPE", "SQLALCHEMY").upper()


@dataclass
class Field:
    """필드 정의"""

    field_type: str
    primary_key: bool = False
    nullable: bool = True
    default: Any = None
    max_length: Optional[int] = None
    foreign_key: Optional[str] = None
    index: bool = False
    unique: bool = False
    description: Optional[str] = None


@dataclass
class Table:
    """테이블 정의"""

    name: str
    fields: Dict[str, Field]
    indexes: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


class BaseModel:
    """기본 모델 클래스 (메타클래스 충돌 방지를 위해 ABC 제거)"""

    __table_name__: ClassVar[Optional[str]] = None
    __fields__: ClassVar[Dict[str, Field]] = {}

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def create_table(cls) -> Table:
        """테이블 정의 생성 (기본 구현)"""
        return Table(
            name=cls.__table_name__ or cls.__name__.lower(),
            fields=cls.__fields__.copy(),
            indexes=[],
            constraints=[],
        )

    async def save(self) -> Result["BaseModel", str]:
        """모델 저장 (기본 구현)"""
        return Failure("save() 메서드가 구현되지 않았습니다")

    async def delete(self) -> Result[None, str]:
        """모델 삭제 (기본 구현)"""
        return Failure("delete() 메서드가 구현되지 않았습니다")

    @classmethod
    async def get(cls, **filters) -> Result[Optional["BaseModel"], str]:
        """단일 모델 조회 (기본 구현)"""
        return Failure("get() 메서드가 구현되지 않았습니다")

    @classmethod
    async def filter(cls, **filters) -> Result[List["BaseModel"], str]:
        """모델 목록 조회 (기본 구현)"""
        return Failure("filter() 메서드가 구현되지 않았습니다")

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            key: getattr(self, key, None)
            for key in self.__fields__.keys()
            if hasattr(self, key)
        }

    def update_from_dict(self, data: Dict[str, Any]):
        """딕셔너리에서 업데이트"""
        for key, value in data.items():
            if key in self.__fields__ and hasattr(self, key):
                setattr(self, key, value)


# SQLAlchemy 구현
if ORM_TYPE == "SQLALCHEMY":
    try:
        from sqlalchemy import (
            JSON,
            Boolean,
            Column,
            DateTime,
            ForeignKey,
            Integer,
            String,
            Text,
        )
        from sqlalchemy.orm import declarative_base, relationship

        SQLAlchemy_Base = declarative_base()
        SQLALCHEMY_AVAILABLE = True
        logger.info("SQLAlchemy ORM 활성화됨")
    except ImportError:
        raise ImportError(
            "SQLAlchemy가 설치되지 않았습니다. pip install sqlalchemy를 실행하세요."
        )

    class SQLAlchemyModel(BaseModel, SQLAlchemy_Base):
        """SQLAlchemy 모델 베이스"""

        __abstract__ = True
        id = Column(Integer, primary_key=True, autoincrement=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        @classmethod
        def create_table(cls) -> Table:
            """SQLAlchemy 테이블 정의"""
            fields = {
                "id": Field("integer", primary_key=True),
                "created_at": Field("datetime", default=datetime.utcnow),
                "updated_at": Field("datetime", default=datetime.utcnow),
            }

            if hasattr(cls, "__table__") and cls.__table__ is not None:
                for column in cls.__table__.columns:
                    if column.name not in fields:
                        fields[column.name] = Field(
                            field_type=str(column.type).lower(),
                            primary_key=column.primary_key,
                            nullable=column.nullable,
                            default=column.default,
                        )

            return Table(
                name=getattr(cls, "__tablename__", cls.__name__.lower()), fields=fields
            )

        async def save(self) -> Result["SQLAlchemyModel", str]:
            """SQLAlchemy 모델 저장"""
            try:
                from .base import get_database

                database = get_database()
                if not database:
                    return Failure("데이터베이스 연결을 찾을 수 없습니다")

                async with database.create_session() as session:
                    session.add(self)
                    await session.commit()
                    await session.refresh(self)
                    logger.info(f"모델 저장 완료: {self.__class__.__name__}")
                    return Success(self)
            except Exception as e:
                return Failure(f"모델 저장 실패: {str(e)}")

        async def delete(self) -> Result[None, str]:
            """SQLAlchemy 모델 삭제"""
            try:
                from .base import get_database

                database = get_database()
                if not database:
                    return Failure("데이터베이스 연결을 찾을 수 없습니다")

                async with database.create_session() as session:
                    await session.delete(self)
                    await session.commit()
                    logger.info(f"모델 삭제 완료: {self.__class__.__name__}")
                    return Success(None)
            except Exception as e:
                return Failure(f"모델 삭제 실패: {str(e)}")

        @classmethod
        async def get(cls, **filters) -> Result[Optional["SQLAlchemyModel"], str]:
            """SQLAlchemy 모델 단일 조회"""
            try:
                from sqlalchemy import select

                from .base import get_database

                database = get_database()
                if not database:
                    return Failure("데이터베이스 연결을 찾을 수 없습니다")

                async with database.create_session() as session:
                    query = select(cls).filter_by(**filters)
                    result = await session.execute(query)
                    model = result.scalar_one_or_none()
                    return Success(model)
            except Exception as e:
                return Failure(f"모델 조회 실패: {str(e)}")

        @classmethod
        async def filter(cls, **filters) -> Result[List["SQLAlchemyModel"], str]:
            """SQLAlchemy 모델 목록 조회"""
            try:
                from sqlalchemy import select

                from .base import get_database

                database = get_database()
                if not database:
                    return Failure("데이터베이스 연결을 찾을 수 없습니다")

                async with database.create_session() as session:
                    query = select(cls).filter_by(**filters)
                    result = await session.execute(query)
                    models = result.scalars().all()
                    return Success(list(models))
            except Exception as e:
                return Failure(f"모델 목록 조회 실패: {str(e)}")

    # 기본 Model 클래스를 SQLAlchemyModel로 설정
    Model = SQLAlchemyModel

# Tortoise ORM 구현
elif ORM_TYPE == "TORTOISE":
    try:
        from tortoise import fields
        from tortoise.models import Model as TortoiseBaseModel

        TORTOISE_AVAILABLE = True
        logger.info("Tortoise ORM 활성화됨")
    except ImportError:
        raise ImportError(
            "Tortoise-ORM이 설치되지 않았습니다. pip install tortoise-orm을 실행하세요."
        )

    class TortoiseModel(BaseModel, TortoiseBaseModel):
        """Tortoise ORM 모델 베이스"""

        class Meta:
            abstract = True

        @classmethod
        def create_table(cls) -> Table:
            """Tortoise 테이블 정의"""
            fields_dict = {}
            if hasattr(cls, "_meta") and hasattr(cls._meta, "fields_map"):
                for field_name, field_obj in cls._meta.fields_map.items():
                    fields_dict[field_name] = Field(
                        field_type=field_obj.__class__.__name__.lower(),
                        primary_key=getattr(field_obj, "pk", False),
                        nullable=getattr(field_obj, "null", True),
                        default=getattr(field_obj, "default", None),
                    )

            return Table(
                name=cls._meta.table if hasattr(cls, "_meta") else cls.__name__.lower(),
                fields=fields_dict,
            )

        async def save(self) -> Result["TortoiseModel", str]:
            """Tortoise 모델 저장"""
            try:
                await super().save()
                logger.info(f"모델 저장 완료: {self.__class__.__name__}")
                return Success(self)
            except Exception as e:
                return Failure(f"모델 저장 실패: {str(e)}")

        async def delete(self) -> Result[None, str]:
            """Tortoise 모델 삭제"""
            try:
                await super().delete()
                logger.info(f"모델 삭제 완료: {self.__class__.__name__}")
                return Success(None)
            except Exception as e:
                return Failure(f"모델 삭제 실패: {str(e)}")

        @classmethod
        async def get(cls, **filters) -> Result[Optional["TortoiseModel"], str]:
            """Tortoise 모델 단일 조회"""
            try:
                model = await cls.get_or_none(**filters)
                return Success(model)
            except Exception as e:
                return Failure(f"모델 조회 실패: {str(e)}")

        @classmethod
        async def filter(cls, **filters) -> Result[List["TortoiseModel"], str]:
            """Tortoise 모델 목록 조회"""
            try:
                models = await cls.filter(**filters).all()
                return Success(models)
            except Exception as e:
                return Failure(f"모델 목록 조회 실패: {str(e)}")

    # 기본 Model 클래스를 TortoiseModel로 설정
    Model = TortoiseModel

else:
    raise ValueError(
        f"지원되지 않는 ORM 타입: {ORM_TYPE}. SQLALCHEMY 또는 TORTOISE를 사용하세요."
    )


class ModelRegistry(metaclass=SingletonMeta):
    """모델 레지스트리"""

    def __init__(self):
        self.models: Dict[str, Type[BaseModel]] = {}
        self.tables = {}

    def register_model(self, model_class: Type[BaseModel]):
        """모델 등록"""
        model_name = model_class.__name__
        self.models[model_name] = model_class
        table = model_class.create_table()
        self.tables[model_name] = table
        logger.info(f"모델 등록: {model_name}")

    def get_model(self, model_name: str) -> Optional[Type[BaseModel]]:
        """모델 조회"""
        return self.models.get(model_name)

    def get_table(self, model_name: str) -> Optional[Table]:
        """테이블 정의 조회"""
        return self.tables.get(model_name)

    def get_all_models(self) -> Dict[str, Type[BaseModel]]:
        """모든 모델 반환"""
        return self.models.copy()

    def get_all_tables(self) -> Dict[str, Table]:
        """모든 테이블 정의 반환"""
        return self.tables.copy()


def get_model_registry() -> ModelRegistry:
    """모델 레지스트리 인스턴스 반환"""
    return ModelRegistry()


def register_model(model_class: Type[BaseModel]):
    """모델 레지스트리에 등록"""
    registry = get_model_registry()
    registry.register_model(model_class)


def create_model(
    name: str,
    fields: Dict[str, Field],
    base_class: Type[BaseModel] = None,
    table_name: str = None,
) -> Type[BaseModel]:
    """동적 모델 생성"""

    if base_class is None:
        base_class = Model

    attrs = {"__table_name__": table_name or name.lower(), "__fields__": fields}

    if ORM_TYPE == "SQLALCHEMY" and base_class.__name__ == "SQLAlchemyModel":
        attrs["__tablename__"] = table_name or name.lower()

        for field_name, field_def in fields.items():
            column_type = None
            if field_def.field_type == "integer":
                column_type = Integer
            elif field_def.field_type == "string":
                column_type = String(field_def.max_length or 255)
            elif field_def.field_type == "text":
                column_type = Text
            elif field_def.field_type == "datetime":
                column_type = DateTime
            elif field_def.field_type == "boolean":
                column_type = Boolean
            elif field_def.field_type == "json":
                column_type = JSON
            else:
                column_type = String(255)

            attrs[field_name] = Column(
                column_type,
                primary_key=field_def.primary_key,
                nullable=field_def.nullable,
                default=field_def.default,
                index=field_def.index,
                unique=field_def.unique,
            )

    elif ORM_TYPE == "TORTOISE" and base_class.__name__ == "TortoiseModel":
        for field_name, field_def in fields.items():
            if field_def.field_type == "integer":
                field_obj = fields.IntField(pk=field_def.primary_key)
            elif field_def.field_type == "string":
                field_obj = fields.CharField(
                    max_length=field_def.max_length or 255, null=field_def.nullable
                )
            elif field_def.field_type == "text":
                field_obj = fields.TextField(null=field_def.nullable)
            elif field_def.field_type == "datetime":
                field_obj = fields.DatetimeField(
                    auto_now_add=True if field_def.default else False
                )
            elif field_def.field_type == "boolean":
                field_obj = fields.BooleanField(default=field_def.default)
            elif field_def.field_type == "json":
                field_obj = fields.JSONField(default=field_def.default)
            else:
                field_obj = fields.CharField(max_length=255, null=field_def.nullable)

            attrs[field_name] = field_obj

    model_class = type(name, (base_class,), attrs)
    registry = get_model_registry()
    registry.register_model(model_class)

    return model_class
