"""
Unit tests for database models module
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from rfs.core.result import Failure, Success
from rfs.database.models import (
    BaseModel,
    Field,
    ModelRegistry,
    SQLAlchemyModel,
    Table,
    TortoiseModel,
    create_model,
    get_model_registry,
    register_model,
)


# Test base model implementation
class TestModelBase(BaseModel):
    """Test base model implementation for tests"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

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


class TestField:
    """Test Field class"""

    def test_field_creation(self):
        """Test creating field"""
        field = Field(name="username", type=str, required=True)

        assert field.name == "username"
        assert field.type == str
        assert field.required is True
        assert field.default is None
        assert field.primary_key is False
        assert field.unique is False
        assert field.index is False

    def test_field_with_defaults(self):
        """Test field with default values"""
        field = Field(name="status", type=str, default="active", required=False)

        assert field.default == "active"
        assert field.required is False

    def test_field_primary_key(self):
        """Test primary key field"""
        field = Field(name="id", type=int, primary_key=True, auto_increment=True)

        assert field.primary_key is True
        assert field.auto_increment is True

    def test_field_constraints(self):
        """Test field constraints"""
        field = Field(name="email", type=str, unique=True, index=True, max_length=255)

        assert field.unique is True
        assert field.index is True
        assert field.max_length == 255

    def test_field_foreign_key(self):
        """Test foreign key field"""
        field = Field(
            name="user_id", type=int, foreign_key="users.id", on_delete="CASCADE"
        )

        assert field.foreign_key == "users.id"
        assert field.on_delete == "CASCADE"

    def test_field_validation(self):
        """Test field validation rules"""
        field = Field(
            name="age", type=int, min_value=0, max_value=150, validators=["positive"]
        )

        assert field.min_value == 0
        assert field.max_value == 150
        assert "positive" in field.validators

    def test_field_to_dict(self):
        """Test field serialization"""
        field = Field(name="created_at", type=datetime, auto_now_add=True)

        dict_repr = field.to_dict()
        assert dict_repr["name"] == "created_at"
        assert dict_repr["type"] == "datetime"
        assert dict_repr["auto_now_add"] is True


class TestTable:
    """Test Table class"""

    def test_table_creation(self):
        """Test creating table metadata"""
        table = Table(name="users")

        assert table.name == "users"
        assert table.fields == []
        assert table.indexes == []
        assert table.constraints == []
        assert table.options == {}

    def test_table_with_fields(self):
        """Test table with fields"""
        fields = [
            Field(name="id", type=int, primary_key=True),
            Field(name="username", type=str, unique=True),
            Field(name="email", type=str, index=True),
        ]

        table = Table(name="users", fields=fields)
        assert len(table.fields) == 3
        assert table.fields[0].primary_key is True
        assert table.fields[1].unique is True
        assert table.fields[2].index is True

    def test_table_with_indexes(self):
        """Test table with custom indexes"""
        table = Table(
            name="posts",
            indexes=[
                {"fields": ["user_id", "created_at"], "unique": False},
                {"fields": ["slug"], "unique": True},
            ],
        )

        assert len(table.indexes) == 2
        assert table.indexes[0]["fields"] == ["user_id", "created_at"]
        assert table.indexes[1]["unique"] is True

    def test_table_with_constraints(self):
        """Test table with constraints"""
        table = Table(
            name="orders",
            constraints=[
                {"type": "check", "expression": "total > 0"},
                {"type": "unique", "fields": ["order_number"]},
            ],
        )

        assert len(table.constraints) == 2
        assert table.constraints[0]["type"] == "check"
        assert table.constraints[1]["fields"] == ["order_number"]

    def test_table_options(self):
        """Test table options"""
        table = Table(
            name="logs",
            options={
                "engine": "InnoDB",
                "charset": "utf8mb4",
                "collate": "utf8mb4_unicode_ci",
            },
        )

        assert table.options["engine"] == "InnoDB"
        assert table.options["charset"] == "utf8mb4"

    def test_add_field(self):
        """Test adding field to table"""
        table = Table(name="products")
        field = Field(name="name", type=str, required=True)

        table.add_field(field)
        assert len(table.fields) == 1
        assert table.fields[0] == field

    def test_get_primary_key(self):
        """Test getting primary key field"""
        fields = [
            Field(name="id", type=int, primary_key=True),
            Field(name="name", type=str),
        ]
        table = Table(name="items", fields=fields)

        pk = table.get_primary_key()
        assert pk is not None
        assert pk.name == "id"
        assert pk.primary_key is True


class TestBaseModel:
    """Test BaseModel abstract class"""

    def test_abstract_class(self):
        """Test that abstract class cannot be instantiated"""
        with pytest.raises(TypeError):
            model = BaseModel()

    def test_model_meta_class(self):
        """Test model Meta class"""

        class TestModel(TestModelBase):
            id: int
            name: str

            class Meta:
                table_name = "test_table"
                indexes = [["name"]]

            def to_dict(self):
                return {"id": self.id, "name": self.name}

            @classmethod
            def from_dict(cls, data):
                return cls(**data)

        assert TestModel.Meta.table_name == "test_table"
        assert TestModel.Meta.indexes == [["name"]]


class TestModel:
    """Test Model base class"""

    def test_model_creation(self):
        """Test creating model instance"""

        class UserModel(TestModelBase):
            id: int
            username: str
            email: str
            active=True

            class Meta:
                table_name = "users"

            def to_dict(self):
                return {
                    "id": self.id,
                    "username": self.username,
                    "email": self.email,
                    "active": self.active,
                }

            @classmethod
            def from_dict(cls, data):
                return cls(**data)

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

        user = UserModel(id=1, username="john", email="john@example.com")
        assert user.id == 1
        assert user.username == "john"
        assert user.email == "john@example.com"
        assert user.active is True

    def test_model_to_dict(self):
        """Test model serialization"""

        class ProductModel(TestModelBase):
            id: int
            name: str
            price: float

            class Meta:
                table_name = "products"

        product = ProductModel(id=1, name="Widget", price=19.99)
        dict_repr = product.to_dict()

        assert dict_repr["id"] == 1
        assert dict_repr["name"] == "Widget"
        assert dict_repr["price"] == 19.99

    def test_model_from_dict(self):
        """Test model deserialization"""

        class CategoryModel(TestModelBase):
            id: int
            name: str
            parent_id=None

            class Meta:
                table_name = "categories"

        data = {"id": 1, "name": "Electronics", "parent_id": None}
        category = CategoryModel.from_dict(data)

        assert category.id == 1
        assert category.name == "Electronics"
        assert category.parent_id is None

    def test_model_validation(self):
        """Test model validation"""

        class ValidatedModel(TestModelBase):
            id: int
            email: str
            age: int

            class Meta:
                table_name = "validated"

            def validate(self):
                errors = []
                if "@" not in self.email:
                    errors.append("Invalid email format")
                if self.age < 0 or self.age > 150:
                    errors.append("Invalid age")
                return errors if errors else None

        model = ValidatedModel(id=1, email="invalid", age=200)
        errors = model.validate()
        assert len(errors) == 2
        assert "Invalid email format" in errors
        assert "Invalid age" in errors

    def test_model_equality(self):
        """Test model equality comparison"""

        class ItemModel(TestModelBase):
            id: int
            name: str

            class Meta:
                table_name = "items"

        item1 = ItemModel(id=1, name="Item1")
        item2 = ItemModel(id=1, name="Item1")
        item3 = ItemModel(id=2, name="Item2")

        assert item1 == item2
        assert item1 != item3

    def test_model_repr(self):
        """Test model string representation"""

        class TaskModel(TestModelBase):
            id: int
            title: str

            class Meta:
                table_name = "tasks"

            def __repr__(self):
                return f"<Task(id={self.id}, title='{self.title}')>"

        task = TaskModel(id=1, title="Test Task")
        assert repr(task) == "<Task(id=1, title='Test Task')>"


class TestSQLAlchemyModel:
    """Test SQLAlchemy model implementation"""

    @pytest.mark.skipif(
        not pytest.importorskip("sqlalchemy", reason="SQLAlchemy not installed"),
        reason="SQLAlchemy not installed",
    )
    def test_sqlalchemy_model_creation(self):
        """Test creating SQLAlchemy model"""
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.ext.declarative import declarative_base

        Base = declarative_base()

        class User(Base, SQLAlchemyModel):
            __tablename__ = "users"

            id = Column(Integer, primary_key=True)
            username = Column(String(50), unique=True, nullable=False)
            email = Column(String(120), unique=True, nullable=False)

        user = User(username="john", email="john@example.com")
        assert user.username == "john"
        assert user.email == "john@example.com"

    @pytest.mark.skipif(
        not pytest.importorskip("sqlalchemy", reason="SQLAlchemy not installed"),
        reason="SQLAlchemy not installed",
    )
    def test_sqlalchemy_model_relationships(self):
        """Test SQLAlchemy model relationships"""
        from sqlalchemy import Column, ForeignKey, Integer, String
        from sqlalchemy.ext.declarative import declarative_base
        from sqlalchemy.orm import relationship

        Base = declarative_base()

        class Post(Base, SQLAlchemyModel):
            __tablename__ = "posts"

            id = Column(Integer, primary_key=True)
            title = Column(String(200))
            user_id = Column(Integer, ForeignKey("users.id"))
            user = relationship("User", back_populates="posts")

        # Relationships would be tested with actual database


class TestTortoiseModel:
    """Test Tortoise ORM model implementation"""

    @pytest.mark.skipif(
        not pytest.importorskip("tortoise", reason="Tortoise ORM not installed"),
        reason="Tortoise ORM not installed",
    )
    def test_tortoise_model_creation(self):
        """Test creating Tortoise model"""
        from tortoise import fields
        from tortoise.models import Model as TortoiseBaseModel

        class User(TortoiseBaseModel, TortoiseModel):
            id = fields.IntField(pk=True)
            username = fields.CharField(max_length=50, unique=True)
            email = fields.CharField(max_length=120, unique=True)
            created_at = fields.DatetimeField(auto_now_add=True)

            class Meta:
                table = "users"

        # Model would be tested with actual database connection


class TestModelRegistry:
    """Test ModelRegistry singleton"""

    def test_singleton_pattern(self):
        """Test singleton pattern implementation"""
        registry1 = ModelRegistry()
        registry2 = ModelRegistry()
        assert registry1 is registry2

    def test_register_model(self):
        """Test model registration"""
        registry = ModelRegistry()
        registry.clear()

        class TestModel(TestModelBase):
            id: int
            name: str

            class Meta:
                table_name = "test"

        result = registry.register("test_model", TestModel)
        assert result.is_success()
        assert "test_model" in registry._models

    def test_register_duplicate(self):
        """Test duplicate registration"""
        registry = ModelRegistry()
        registry.clear()

        class Model1(TestModelBase):
            id: int

        class Model2(TestModelBase):
            id: int

        registry.register("model", Model1)
        result = registry.register("model", Model2)
        assert result.is_failure()
        assert "already registered" in str(result.unwrap_err())

    def test_get_model(self):
        """Test getting registered model"""
        registry = ModelRegistry()
        registry.clear()

        class UserModel(TestModelBase):
            id: int
            username: str

        registry.register("user", UserModel)

        result = registry.get("user")
        assert result.is_success()
        assert result.unwrap() == UserModel

    def test_get_nonexistent(self):
        """Test getting non-existent model"""
        registry = ModelRegistry()
        registry.clear()

        result = registry.get("nonexistent")
        assert result.is_failure()
        assert "not found" in str(result.unwrap_err())

    def test_remove_model(self):
        """Test removing model"""
        registry = ModelRegistry()
        registry.clear()

        class TestModel(TestModelBase):
            id: int

        registry.register("test", TestModel)
        result = registry.remove("test")
        assert result.is_success()
        assert "test" not in registry._models

    def test_list_models(self):
        """Test listing registered models"""
        registry = ModelRegistry()
        registry.clear()

        class Model1(TestModelBase):
            id: int

        class Model2(TestModelBase):
            id: int

        registry.register("model1", Model1)
        registry.register("model2", Model2)

        models = registry.list_models()
        assert "model1" in models
        assert "model2" in models
        assert len(models) == 2

    def test_get_by_table_name(self):
        """Test getting model by table name"""
        registry = ModelRegistry()
        registry.clear()

        class ProductModel(TestModelBase):
            id: int
            name: str

            class Meta:
                table_name = "products"

        registry.register("product", ProductModel)

        result = registry.get_by_table_name("products")
        assert result.is_success()
        assert result.unwrap() == ProductModel


class TestModelFactory:
    """Test model factory functions"""

    def test_create_model(self):
        """Test creating model dynamically"""
        fields = {
            "id": Field(name="id", type=int, primary_key=True),
            "name": Field(name="name", type=str, required=True),
            "active": Field(name="active", type=bool, default=True),
        }

        result = create_model("DynamicModel", fields, table_name="dynamic")
        assert result.is_success()

        ModelClass = result.unwrap()
        instance = ModelClass(id=1, name="Test")
        assert instance.id == 1
        assert instance.name == "Test"
        assert instance.active is True

    def test_create_model_with_methods(self):
        """Test creating model with custom methods"""
        fields = {
            "id": Field(name="id", type=int),
            "value": Field(name="value", type=float),
        }

        def calculate_total(self):
            return self.value * 1.1

        methods = {"calculate_total": calculate_total}

        result = create_model("CalculatedModel", fields, methods=methods)
        assert result.is_success()

        ModelClass = result.unwrap()
        instance = ModelClass(id=1, value=100.0)
        assert instance.calculate_total() == 110.0

    def test_register_model_function(self):
        """Test register_model helper function"""
        registry = get_model_registry()
        registry.clear()

        class TestModel(TestModelBase):
            id: int

        result = register_model("test", TestModel)
        assert result.is_success()

        # Verify registration
        get_result = registry.get("test")
        assert get_result.is_success()
        assert get_result.unwrap() == TestModel

    def test_get_model_registry_singleton(self):
        """Test getting model registry singleton"""
        registry1 = get_model_registry()
        registry2 = get_model_registry()
        assert registry1 is registry2


class TestModelIntegration:
    """Integration tests for model system"""

    def test_model_workflow(self):
        """Test complete model workflow"""

        # Define model
        class OrderModel(TestModelBase):
            id: int
            customer_id: int
            total: float
            status="pending"

            class Meta:
                table_name = "orders"
                indexes = [["customer_id"], ["status"]]

            def validate(self):
                if self.total < 0:
                    return ["Total cannot be negative"]
                return None

        # Register model
        registry = get_model_registry()
        registry.clear()
        registry.register("order", OrderModel)

        # Create instance
        order = OrderModel(id=1, customer_id=100, total=99.99)
        assert order.status == "pending"

        # Validate
        errors = order.validate()
        assert errors is None

        # Serialize
        data = order.to_dict()
        assert data["id"] == 1
        assert data["total"] == 99.99

        # Deserialize
        restored = OrderModel.from_dict(data)
        assert restored.id == order.id
        assert restored.total == order.total

        # Get from registry
        model_class = registry.get("order").unwrap()
        assert model_class == OrderModel

    def test_model_inheritance(self):
        """Test model inheritance"""

        class BaseEntity(TestModelBase):
            id: int
            created_at: datetime
            updated_at: datetime

            class Meta:
                abstract = True

        class User(BaseEntity):
            username: str
            email: str

            class Meta:
                table_name = "users"

        class Post(BaseEntity):
            title: str
            content: str
            author_id: int

            class Meta:
                table_name = "posts"

        # Create instances
        user = User(
            id=1,
            username="john",
            email="john@example.com",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        post = Post(
            id=1,
            title="Test Post",
            content="Content",
            author_id=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Both should have base fields
        assert hasattr(user, "created_at")
        assert hasattr(post, "created_at")

        # And their own fields
        assert hasattr(user, "username")
        assert hasattr(post, "title")
