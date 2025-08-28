"""
RFS Database Models (RFS v4.1)

통합 데이터베이스 모델 시스템
"""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type, Union

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
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import relationship

    SQLAlchemy_Base = declarative_base()
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    Column = None  # type: ignore[misc,assignment]
    Integer = None  # type: ignore[misc,assignment]
    String = None  # type: ignore[misc,assignment]
    DateTime = None  # type: ignore[misc,assignment]
    Boolean = None  # type: ignore[misc,assignment]
    Text = None  # type: ignore[misc,assignment]
    JSON = None  # type: ignore[misc,assignment]
    ForeignKey = None  # type: ignore[misc,assignment]
    relationship = None  # type: ignore[misc,assignment]
    SQLAlchemy_Base = object  # type: ignore[misc,assignment]
    SQLALCHEMY_AVAILABLE = False
try:
    from tortoise import fields as tortoise_fields
    from tortoise.models import Model as TortoiseBaseModel

    TORTOISE_AVAILABLE = True
except ImportError:
    TortoiseBaseModel = object  # type: ignore[misc,assignment]
    tortoise_fields = None  # type: ignore[misc,assignment]
    TORTOISE_AVAILABLE = False
from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta

logger = get_logger(__name__)


@dataclass
class Field:
    """필드 정의"""

    field_type: str
    primary_key = False
    nullable = True
    default: Any = None
    max_length = None
    foreign_key = None
    index = False
    unique = False
    description = None


@dataclass
class Table:
    """테이블 정의"""

    name: str
    fields: Dict[str, Field]
    indexes: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


class BaseModel(ABC):
    """기본 모델 추상 클래스"""

    __table_name__: ClassVar[Optional[str]] = None
    __fields__: ClassVar[Dict[str, Field]] = {}

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    @abstractmethod
    def create_table(cls) -> Table:
        """테이블 정의 생성"""
        pass

    @abstractmethod
    async def save(self) -> Result["BaseModel", str]:
        """모델 저장"""
        pass

    @abstractmethod
    async def delete(self) -> Result[None, str]:
        """모델 삭제"""
        pass

    @classmethod
    @abstractmethod
    async def get(cls, **filters) -> Result[Optional["BaseModel"], str]:
        """단일 모델 조회"""
        pass

    @classmethod
    @abstractmethod
    async def filter(cls, **filters) -> Result[List["BaseModel"], str]:
        """모델 목록 조회"""
        pass

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


class SQLAlchemyModel(BaseModel):
    """SQLAlchemy 모델 베이스"""

    __abstract__ = True

    # SQLAlchemy Base를 컴포지션으로 사용
    if SQLALCHEMY_AVAILABLE:
        _sa_base = SQLAlchemy_Base
    id = (
        Column(Integer, primary_key=True, autoincrement=True)
        if SQLALCHEMY_AVAILABLE
        else None
    )
    created_at = (
        Column(DateTime, default=datetime.utcnow) if SQLALCHEMY_AVAILABLE else None
    )
    updated_at = (
        Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        if SQLALCHEMY_AVAILABLE
        else None
    )

    @classmethod
    def create_table(cls) -> Table:
        """SQLAlchemy 테이블 정의"""
        fields = {}
        fields["id"] = {"id": Field("integer", primary_key=True)}
        fields = {
            **fields,
            "created_at": {"created_at": Field("datetime", default=datetime.utcnow)},
        }
        fields = {
            **fields,
            "updated_at": {"updated_at": Field("datetime", default=datetime.utcnow)},
        }
        if hasattr(cls, "__table__") and cls.__table__ is not None:
            for column in cls.__table__.columns:
                if column.name not in fields:
                    fields = {
                        **fields,
                        column.name: {
                            column.name: Field(
                                field_type=str(column.type).lower(),
                                primary_key=column.primary_key,
                                nullable=column.nullable,
                                default=column.default,
                            )
                        },
                    }
        return Table(
            name=(
                cls.__tablename__
                if hasattr(cls, "__tablename__")
                else cls.__name__.lower()
            ),
            fields=fields,
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
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            async with database.create_session() as session:
                from sqlalchemy import select

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
            from .base import get_database

            database = get_database()
            if not database:
                return Failure("데이터베이스 연결을 찾을 수 없습니다")
            async with database.create_session() as session:
                from sqlalchemy import select

                query = select(cls).filter_by(**filters)
                result = await session.execute(query)
                models = result.scalars().all()
                return Success(list(models))
        except Exception as e:
            return Failure(f"모델 목록 조회 실패: {str(e)}")


class TortoiseModel(BaseModel):
    """Tortoise ORM 모델 베이스"""

    class Meta:
        abstract = True

    # Tortoise Base를 컴포지션으로 사용
    if TORTOISE_AVAILABLE:
        _tortoise_base = TortoiseBaseModel

    @classmethod
    def create_table(cls) -> Table:
        """Tortoise 테이블 정의"""
        fields: Dict[str, Dict[str, Field]] = {}
        if hasattr(cls, "_meta") and hasattr(cls._meta, "fields_map"):
            for field_name, field_obj in cls._meta.fields_map.items():
                fields = {
                    **fields,
                    field_name: {
                        field_name: Field(
                            field_type=field_obj.__class__.__name__.lower(),
                            primary_key=getattr(field_obj, "pk", False),
                            nullable=getattr(field_obj, "null", True),
                            default=getattr(field_obj, "default", None),
                        )
                    },
                }
        return Table(
            name=cls._meta.table if hasattr(cls, "_meta") else cls.__name__.lower(),
            fields=fields,
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
            # Use Tortoise ORM's filter method directly to avoid recursion
            queryset = super().filter(**filters)  # type: ignore[misc]
            models = await queryset.all()  # type: ignore[attr-defined]
            return Success(models)
        except Exception as e:
            return Failure(f"모델 목록 조회 실패: {str(e)}")


class ModelRegistry(metaclass=SingletonMeta):
    """모델 레지스트리"""

    def __init__(self):
        self.models: Dict[str, Type[BaseModel]] = {}
        self.tables = {}

    def register_model(self, model_class: Type[BaseModel]):
        """모델 등록"""
        model_name = model_class.__name__
        self.models = {**self.models, model_name: model_class}
        table = model_class.create_table()
        self.tables = {**self.tables, model_name: table}
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


def create_model(
    name: str,
    fields: Dict[str, Field],
    base_class: Optional[Type[BaseModel]] = None,
    table_name: Optional[str] = None,
) -> Type[BaseModel]:
    """동적 모델 생성"""
    from .base import get_database_manager

    if base_class is None:
        manager = get_database_manager()
        database = manager.get_database()
        if database and hasattr(database, "config"):
            if (
                database.config.orm_type.value in ["sqlalchemy", "auto"]
                and SQLALCHEMY_AVAILABLE
            ):
                base_class = SQLAlchemyModel
            elif (
                database.config.orm_type.value in ["tortoise", "auto"]
                and TORTOISE_AVAILABLE
            ):
                base_class = TortoiseModel
            else:
                raise ValueError("지원되는 ORM이 없습니다")
    attrs = {"__table_name__": table_name or name.lower(), "__fields__": fields}
    if base_class == SQLAlchemyModel and SQLALCHEMY_AVAILABLE:
        attrs = {
            **attrs,
            "__tablename__": {"__tablename__": table_name or name.lower()},
        }
        for field_name, field_def in fields.items():
            column_type: Any
            match field_def.field_type:
                case "integer":
                    column_type = Integer
                case "string":
                    column_type = String(field_def.max_length or 255)
                case "text":
                    column_type = Text
                case "datetime":
                    column_type = DateTime
                case "boolean":
                    column_type = Boolean
                case "json":
                    column_type = JSON
                case _:
                    column_type = String(255)
            attrs = {
                **attrs,
                field_name: {
                    field_name: Column(
                        column_type,
                        primary_key=field_def.primary_key,
                        nullable=field_def.nullable,
                        default=field_def.default,
                        index=field_def.index,
                        unique=field_def.unique,
                    )
                },
            }
    elif base_class == TortoiseModel and TORTOISE_AVAILABLE and tortoise_fields is not None:
        for field_name, field_def in fields.items():
            field_obj: Any
            match field_def.field_type:
                case "integer":
                    field_obj = tortoise_fields.IntField(pk=field_def.primary_key)  # type: ignore[attr-defined]
                case "string":
                    field_obj = tortoise_fields.CharField(  # type: ignore[attr-defined]
                        max_length=field_def.max_length or 255, null=field_def.nullable
                    )
                case "text":
                    field_obj = tortoise_fields.TextField(null=field_def.nullable)  # type: ignore[attr-defined]
                case "datetime":
                    field_obj = tortoise_fields.DatetimeField(  # type: ignore[attr-defined]
                        auto_now_add=True if field_def.default else False
                    )
                case "boolean":
                    field_obj = tortoise_fields.BooleanField(default=field_def.default)  # type: ignore[attr-defined]
                case "json":
                    field_obj = tortoise_fields.JSONField(default=field_def.default)  # type: ignore[attr-defined]
                case _:
                    field_obj = tortoise_fields.CharField(  # type: ignore[attr-defined]
                        max_length=255, null=field_def.nullable
                    )
            attrs[field_name] = {field_name: field_obj}
    model_class = type(name, (base_class,) if base_class else (), attrs)  # type: ignore[arg-type]
    registry = get_model_registry()
    registry.register_model(model_class)
    return model_class


def register_model(model_class: Type[BaseModel]):
    """모델 레지스트리에 등록"""
    registry = get_model_registry()
    registry.register_model(model_class)


def Model(*args, **kwargs) -> Type[BaseModel]:
    """현재 ORM 설정에 따른 모델 베이스 반환"""
    from .base import get_database_manager

    manager = get_database_manager()
    database = manager.get_database()
    if database and hasattr(database, "config"):
        if (
            database.config.orm_type.value in ["sqlalchemy", "auto"]
            and SQLALCHEMY_AVAILABLE
        ):
            return SQLAlchemyModel
        elif (
            database.config.orm_type.value in ["tortoise", "auto"]
            and TORTOISE_AVAILABLE
        ):
            return TortoiseModel
    if SQLALCHEMY_AVAILABLE:
        return SQLAlchemyModel
    elif TORTOISE_AVAILABLE:
        return TortoiseModel
    else:
        raise RuntimeError("사용 가능한 ORM이 없습니다")
