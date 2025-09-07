"""
Complete test coverage for query.py to achieve 100%
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from rfs.core.result import Failure, Success
from rfs.database.models import BaseModel
from rfs.database.query import (
    AdvancedQueryBuilder,
    Filter,
    Operator,
    Pagination,
    Q,
    Query,
    QueryBuilder,
    Sort,
    SortOrder,
    TransactionalQueryBuilder,
    between,
    build_query,
    contains,
    eq,
    execute_query,
    ge,
    gt,
    ilike,
    in_,
    is_not_null,
    is_null,
    le,
    like,
    lt,
    ne,
    nin,
    regex,
)


class TestModel(BaseModel):
    """Test model for query tests"""

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

    @classmethod
    def create_table(cls):
        from rfs.database.models import Field, Table

        return Table("test_table", [])


class TestQueryAbstractMethods:
    """Test Query abstract class behavior"""

    def test_query_abstract_execute(self):
        """Test that Query.execute is abstract"""
        # Query is abstract and cannot be instantiated
        with pytest.raises(TypeError):
            Query(TestModel)

    def test_concrete_query_must_implement_execute(self):
        """Test that concrete Query must implement execute"""

        class IncompleteQuery(Query):
            pass

        # Cannot instantiate without implementing execute
        with pytest.raises(TypeError):
            IncompleteQuery(TestModel)

    def test_query_abstract_class_coverage(self):
        """Test Query abstract class is properly defined"""
        # Ensure Query is abstract
        assert Query.__abstractmethods__ == frozenset({"execute"})

        # Test that we can create a proper implementation
        class ValidQuery(Query):
            async def execute(self):
                return Success([])

        # Should instantiate successfully
        query = ValidQuery(TestModel)
        assert query.model_class == TestModel


class TestQueryBuilderEdgeCases:
    """Test edge cases and uncovered lines in QueryBuilder"""

    @pytest.fixture
    def query_builder(self):
        return QueryBuilder(TestModel)

    def test_filter_method_proper_usage(self, query_builder):
        """Test filter method returns self (line 130)"""
        # Initialize filters as tuple to match actual implementation
        query_builder.filters = ()

        filter1 = Filter("field", Operator.EQ, "value")
        filter2 = Filter("other", Operator.NE, "test")

        # The filter method concatenates tuple with tuple
        result = query_builder.filter(filter1, filter2)

        # Should return self for chaining
        assert result is query_builder
        assert len(query_builder.filters) == 2

    def test_select_method_returns_self(self, query_builder):
        """Test select method returns self (line 163)"""
        # Initialize _select_fields as tuple to match implementation
        query_builder._select_fields = ()

        result = query_builder.select("field1", "field2", "field3")

        # Should return self for chaining
        assert result is query_builder
        assert query_builder._select_fields == ("field1", "field2", "field3")

    def test_group_by_method_returns_self(self, query_builder):
        """Test group_by method returns self (line 168)"""
        # Initialize _group_by as tuple to match implementation
        query_builder._group_by = ()

        result = query_builder.group_by("category", "status")

        # Should return self for chaining
        assert result is query_builder
        assert query_builder._group_by == ("category", "status")

    @pytest.mark.asyncio
    async def test_execute_with_non_eq_filter(self, query_builder):
        """Test execute with non-EQ filters (lines 209-210)"""
        # Add a non-EQ filter that won't be included in filter_dict
        query_builder.filters = [
            Filter("status", Operator.NE, "deleted"),  # This won't be in filter_dict
            Filter("active", Operator.EQ, True),  # This will be in filter_dict
        ]

        # Mock model_class.filter
        async def mock_filter(**kwargs):
            # Should only receive EQ filters
            assert "active" in kwargs
            assert "status" not in kwargs
            return Success([TestModel(id=1)])

        query_builder.model_class.filter = mock_filter

        result = await query_builder.execute()
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_execute_select_with_filter_failure(self, query_builder):
        """Test _execute_select when model.filter returns Failure (lines 215-216)"""
        query_builder.filters = [Filter("id", Operator.EQ, 1)]

        # Mock model_class.filter to return Failure
        async def mock_filter(**kwargs):
            return Failure("Database connection error")

        query_builder.model_class.filter = mock_filter

        result = await query_builder.execute()
        assert result.is_failure()
        assert "모델 필터링 실패" in str(result.unwrap_error())
        assert "Database connection error" in str(result.unwrap_error())

    @pytest.mark.asyncio
    async def test_execute_select_with_sorting_and_pagination(self, query_builder):
        """Test _execute_select with sorting and pagination (lines 218-223)"""
        # Create test models
        models = [TestModel(id=i, name=f"Model{i}") for i in range(10)]

        # Add sorting and pagination
        query_builder.sorts = [Sort("id", SortOrder.DESC)]
        query_builder.pagination = Pagination(limit=3, offset=2)

        # Mock model_class.filter
        async def mock_filter(**kwargs):
            return Success(models)

        query_builder.model_class.filter = mock_filter

        result = await query_builder.execute()
        assert result.is_success()

        # Verify sorted and paginated
        results = result.unwrap()
        assert len(results) == 3  # limit=3
        # After DESC sort by id and offset=2, we should get ids 7,6,5
        assert results[0].id == 7
        assert results[1].id == 6
        assert results[2].id == 5

    @pytest.mark.asyncio
    async def test_execute_count_with_failure(self, query_builder):
        """Test _execute_count when _execute_select fails (line 233)"""
        query_builder._count_only = True

        # Mock _execute_select to return Failure
        async def mock_execute_select():
            return Failure("SELECT query failed")

        with patch.object(query_builder, "_execute_select", mock_execute_select):
            result = await query_builder.execute()
            assert result.is_failure()
            assert "SELECT query failed" in str(result.unwrap_error())

    @pytest.mark.asyncio
    async def test_execute_count_with_exception(self, query_builder):
        """Test _execute_count with exception (lines 236-237)"""
        query_builder._count_only = True

        # Mock _execute_select to raise exception
        async def mock_execute_select():
            raise ValueError("Unexpected error in count")

        with patch.object(query_builder, "_execute_select", mock_execute_select):
            result = await query_builder.execute()
            assert result.is_failure()
            assert "COUNT 실행 실패" in str(result.unwrap_error())

    def test_apply_sorting_empty_models(self, query_builder):
        """Test _apply_sorting with empty models list (lines 241-242)"""
        query_builder.sorts = []
        models = []

        result = query_builder._apply_sorting(models)
        assert result == []

    def test_apply_sorting_no_sorts(self, query_builder):
        """Test _apply_sorting when no sorts defined (lines 241-242)"""
        models = [TestModel(id=1), TestModel(id=2)]

        # No sorts defined
        query_builder.sorts = []

        result = query_builder._apply_sorting(models)
        assert result == models  # Should return unchanged

    def test_apply_sorting_multiple_sorts(self, query_builder):
        """Test _apply_sorting with multiple sort fields (lines 244-248)"""
        models = [
            TestModel(category="B", priority=1),
            TestModel(category="A", priority=2),
            TestModel(category="A", priority=1),
        ]

        # Multiple sorts - should apply in reverse order
        query_builder.sorts = [
            Sort("category", SortOrder.ASC),
            Sort("priority", SortOrder.ASC),
        ]

        result = query_builder._apply_sorting(models)

        # Should be sorted by category first, then priority
        assert result[0].category == "A" and result[0].priority == 1
        assert result[1].category == "A" and result[1].priority == 2
        assert result[2].category == "B" and result[2].priority == 1

    def test_apply_sorting_with_none_values(self, query_builder):
        """Test _apply_sorting with None attribute values (lines 247)"""
        models = [
            TestModel(id=3, name="C"),
            TestModel(id=1, name=None),  # None value
            TestModel(id=2, name="B"),
        ]

        query_builder.sorts = [Sort("name", SortOrder.ASC)]

        result = query_builder._apply_sorting(models)

        # With the warning, sorting fails and returns original order
        assert len(result) == 3
        assert result[0].id == 3  # Original order preserved
        assert result[1].id == 1
        assert result[2].id == 2

    def test_apply_sorting_with_exception_handling(self, query_builder):
        """Test _apply_sorting exception handling (lines 250-252)"""
        models = [TestModel(id=1)]
        query_builder.sorts = [Sort("nonexistent_field", SortOrder.ASC)]

        # When the field doesn't exist, AttributeError is caught and warning is logged
        result = query_builder._apply_sorting(models)

        # Should return original models when exception occurs
        assert result == models

    @pytest.mark.asyncio
    async def test_execute_general_exception(self, query_builder):
        """Test execute method with general exception (lines 199-202)"""

        # Mock _execute_select to raise exception
        async def mock_execute():
            raise RuntimeError("Unexpected database error")

        with patch.object(query_builder, "_execute_select", mock_execute):
            result = await query_builder.execute()
            assert result.is_failure()
            assert "쿼리 실행 실패" in str(result.unwrap_error())
            assert "Unexpected database error" in str(result.unwrap_error())


class TestTransactionalQueryBuilderEdgeCases:
    """Test edge cases in TransactionalQueryBuilder"""

    @pytest.mark.asyncio
    async def test_execute_batch_without_transaction_failure(self):
        """Test execute_batch without transaction manager and with failure (line 426)"""
        # Create query without transaction manager
        query = TransactionalQueryBuilder(TestModel, None)

        # Create mock queries
        mock_query1 = Mock()
        mock_query1.execute = AsyncMock(return_value=Success("result1"))

        mock_query2 = Mock()
        mock_query2.execute = AsyncMock(return_value=Failure("Query 2 failed"))

        queries = [mock_query1, mock_query2]

        result = await query.execute_batch(queries)

        assert result.is_failure()
        assert "배치 쿼리 실패" in str(result.unwrap_error())
        assert "Query 2 failed" in str(result.unwrap_error())

    @pytest.mark.asyncio
    async def test_execute_batch_with_exception(self):
        """Test execute_batch with exception (lines 430-433)"""
        query = TransactionalQueryBuilder(TestModel, None)

        # Create mock query that raises exception
        mock_query = Mock()
        mock_query.execute = AsyncMock(side_effect=RuntimeError("Database crashed"))

        queries = [mock_query]

        result = await query.execute_batch(queries)

        assert result.is_failure()
        assert "배치 쿼리 실행 실패" in str(result.unwrap_error())
        assert "Database crashed" in str(result.unwrap_error())


class TestAdvancedQueryBuilderCompleteCoverage:
    """Complete coverage for AdvancedQueryBuilder"""

    def test_advanced_query_initialization_with_lists(self):
        """Test AdvancedQueryBuilder initialization and list attributes"""
        query = AdvancedQueryBuilder(TestModel)

        # Test the incorrectly typed attributes (List.get syntax)
        assert hasattr(query, "_joins")
        assert hasattr(query, "_subqueries")
        assert hasattr(query, "_union_queries")
        assert query._joins == []

    def test_subquery_with_alias_assignment(self):
        """Test subquery method sets _alias attribute"""
        main_query = AdvancedQueryBuilder(TestModel)
        sub_query = AdvancedQueryBuilder(TestModel)

        result = main_query.subquery(sub_query, "subq1")

        assert hasattr(sub_query, "_alias")
        assert sub_query._alias == "subq1"
        assert result is main_query


class TestQueryHelperFunctionsComplete:
    """Complete coverage for all helper functions"""

    def test_all_filter_helper_functions(self):
        """Test all filter creation helper functions are properly covered"""
        # Test each helper function
        assert eq("field", "value").operator == Operator.EQ
        assert ne("field", "value").operator == Operator.NE
        assert lt("field", 10).operator == Operator.LT
        assert le("field", 10).operator == Operator.LE
        assert gt("field", 10).operator == Operator.GT
        assert ge("field", 10).operator == Operator.GE
        assert in_("field", [1, 2, 3]).operator == Operator.IN
        assert nin("field", [1, 2, 3]).operator == Operator.NIN
        assert like("field", "%pattern%").operator == Operator.LIKE
        assert ilike("field", "%pattern%").operator == Operator.ILIKE
        assert regex("field", r"\d+").operator == Operator.REGEX
        assert is_null("field").operator == Operator.IS_NULL
        assert is_not_null("field").operator == Operator.IS_NOT_NULL
        assert between("field", 1, 10).operator == Operator.BETWEEN
        assert contains("field", "value").operator == Operator.CONTAINS

    def test_build_query_function(self):
        """Test build_query helper function"""
        query = build_query(TestModel)
        assert isinstance(query, QueryBuilder)
        assert query.model_class == TestModel

    @pytest.mark.asyncio
    async def test_execute_query_function(self):
        """Test execute_query helper function"""
        mock_query = AsyncMock()
        mock_query.execute.return_value = Success(["result"])

        result = await execute_query(mock_query)
        assert result.is_success()
        assert result.unwrap() == ["result"]
        mock_query.execute.assert_called_once()
