"""
query.py 90% 커버리지 달성을 위한 최종 테스트
실제 query.py 구조에 맞춘 포괄적 테스트 구현
"""

from typing import Any, List, Type
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rfs.core.result import Failure, Result, Success
from src.rfs.database.query import (
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


class MockModel:
    """테스트용 모델 클래스"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    async def filter(cls, **kwargs):
        """Mock filter 메서드"""
        # error_test 키가 있으면 실패 시뮬레이션
        if kwargs.get("error_test") is True:
            return Failure("필터링 실패")

        # 기본 테스트 데이터 반환
        mock_data = [
            cls(id=1, name="test1", age=25, status="active"),
            cls(id=2, name="test2", age=30, status="pending"),
            cls(id=3, name="test3", age=35, status="active"),
        ]
        return Success(mock_data)


class TestOperator:
    """Operator enum 테스트"""

    def test_all_operator_values(self):
        """모든 Operator 값이 올바른지 테스트"""
        assert Operator.EQ.value == "eq"
        assert Operator.NE.value == "ne"
        assert Operator.LT.value == "lt"
        assert Operator.LE.value == "le"
        assert Operator.GT.value == "gt"
        assert Operator.GE.value == "ge"
        assert Operator.IN.value == "in"
        assert Operator.NIN.value == "nin"
        assert Operator.LIKE.value == "like"
        assert Operator.ILIKE.value == "ilike"
        assert Operator.REGEX.value == "regex"
        assert Operator.IS_NULL.value == "is_null"
        assert Operator.IS_NOT_NULL.value == "is_not_null"
        assert Operator.BETWEEN.value == "between"
        assert Operator.CONTAINS.value == "contains"

    def test_operator_enum_iteration(self):
        """Operator enum 반복 테스트"""
        all_operators = list(Operator)
        assert len(all_operators) == 15

        # 모든 연산자가 문자열 값을 가지는지 확인
        for op in all_operators:
            assert isinstance(op.value, str)
            assert len(op.value) > 0


class TestSortOrder:
    """SortOrder enum 테스트"""

    def test_sort_order_values(self):
        """SortOrder 값 테스트"""
        assert SortOrder.ASC.value == "asc"
        assert SortOrder.DESC.value == "desc"

    def test_sort_order_enum_complete(self):
        """SortOrder enum 완전성 테스트"""
        all_orders = list(SortOrder)
        assert len(all_orders) == 2

        values = [order.value for order in all_orders]
        assert "asc" in values
        assert "desc" in values


class TestFilter:
    """Filter 데이터클래스 테스트"""

    def test_filter_basic_creation(self):
        """기본 Filter 생성"""
        filter_obj = Filter("name", Operator.EQ, "test")
        assert filter_obj.field == "name"
        assert filter_obj.operator == Operator.EQ
        assert filter_obj.value == "test"

    def test_filter_with_none_value(self):
        """None 값을 가진 Filter"""
        filter_obj = Filter("deleted_at", Operator.IS_NULL)
        assert filter_obj.field == "deleted_at"
        assert filter_obj.operator == Operator.IS_NULL
        assert filter_obj.value is None

    def test_filter_with_complex_values(self):
        """복잡한 값을 가진 Filter들"""
        # 리스트 값
        filter_list = Filter("status", Operator.IN, ["active", "pending"])
        assert filter_list.value == ["active", "pending"]

        # 튜플 값 (BETWEEN)
        filter_range = Filter("age", Operator.BETWEEN, [18, 65])
        assert filter_range.value == [18, 65]

        # 패턴 값 (LIKE)
        filter_pattern = Filter("email", Operator.LIKE, "%@example.com")
        assert filter_pattern.value == "%@example.com"

    def test_filter_to_dict(self):
        """Filter to_dict 메서드 테스트"""
        filter_obj = Filter("age", Operator.GT, 21)
        result = filter_obj.to_dict()

        expected = {"field": "age", "operator": "gt", "value": 21}
        assert result == expected

    def test_filter_to_dict_with_none(self):
        """None 값을 가진 Filter의 to_dict"""
        filter_obj = Filter("deleted_at", Operator.IS_NULL, None)
        result = filter_obj.to_dict()

        expected = {"field": "deleted_at", "operator": "is_null", "value": None}
        assert result == expected

    def test_filter_to_dict_with_list(self):
        """리스트 값을 가진 Filter의 to_dict"""
        filter_obj = Filter("tags", Operator.CONTAINS, ["python", "web"])
        result = filter_obj.to_dict()

        expected = {"field": "tags", "operator": "contains", "value": ["python", "web"]}
        assert result == expected


class TestSort:
    """Sort 데이터클래스 테스트"""

    def test_sort_default_asc(self):
        """기본 오름차순 Sort 생성"""
        sort_obj = Sort("name")
        assert sort_obj.field == "name"
        assert sort_obj.order == SortOrder.ASC

    def test_sort_explicit_desc(self):
        """명시적 내림차순 Sort 생성"""
        sort_obj = Sort("created_at", SortOrder.DESC)
        assert sort_obj.field == "created_at"
        assert sort_obj.order == SortOrder.DESC

    def test_sort_to_dict(self):
        """Sort to_dict 메서드 테스트"""
        sort_obj = Sort("priority", SortOrder.DESC)
        result = sort_obj.to_dict()

        expected = {"field": "priority", "order": "desc"}
        assert result == expected

    def test_sort_to_dict_default(self):
        """기본값을 가진 Sort의 to_dict"""
        sort_obj = Sort("name")
        result = sort_obj.to_dict()

        expected = {"field": "name", "order": "asc"}
        assert result == expected


class TestPagination:
    """Pagination 데이터클래스 테스트"""

    def test_pagination_default_values(self):
        """Pagination 기본값 테스트"""
        pagination = Pagination()
        assert pagination.limit == 10
        assert pagination.offset == 0

    def test_pagination_custom_values(self):
        """Pagination 사용자 정의 값"""
        pagination = Pagination(limit=25, offset=50)
        assert pagination.limit == 25
        assert pagination.offset == 50

    def test_pagination_page_property(self):
        """page 속성 계산 테스트"""
        # 첫 번째 페이지
        pagination = Pagination(limit=10, offset=0)
        assert pagination.page == 1

        # 두 번째 페이지
        pagination = Pagination(limit=10, offset=10)
        assert pagination.page == 2

        # 세 번째 페이지 (limit 20)
        pagination = Pagination(limit=20, offset=40)
        assert pagination.page == 3

    def test_pagination_from_page_method(self):
        """from_page 클래스 메서드 테스트"""
        # 첫 번째 페이지
        pagination = Pagination.from_page(1, 10)
        assert pagination.limit == 10
        assert pagination.offset == 0

        # 두 번째 페이지
        pagination = Pagination.from_page(2, 15)
        assert pagination.limit == 15
        assert pagination.offset == 15

        # 다섯 번째 페이지
        pagination = Pagination.from_page(5, 20)
        assert pagination.limit == 20
        assert pagination.offset == 80

    def test_pagination_edge_cases(self):
        """Pagination 경계 케이스"""
        # 0 페이지
        pagination = Pagination.from_page(0, 10)
        assert pagination.offset == -10
        assert pagination.page == 0

        # 큰 페이지 번호
        pagination = Pagination.from_page(100, 25)
        assert pagination.offset == 2475  # (100-1) * 25
        assert pagination.page == 100


class TestQueryBuilderBasics:
    """QueryBuilder 기본 기능 테스트"""

    def test_query_builder_creation(self):
        """QueryBuilder 생성 테스트"""
        builder = QueryBuilder(MockModel)

        assert builder.model_class == MockModel
        assert builder.filters == []
        assert builder.sorts == []
        assert builder.pagination is None
        assert builder._select_fields == []
        assert builder._group_by == []
        assert builder._having == []
        assert builder._distinct is False
        assert builder._count_only is False

    def test_where_single_condition(self):
        """단일 WHERE 조건 추가"""
        builder = QueryBuilder(MockModel)
        result = builder.where("name", Operator.EQ, "test")

        assert result is builder  # 체이닝 확인
        assert len(builder.filters) == 1

        filter_obj = builder.filters[0]
        assert filter_obj.field == "name"
        assert filter_obj.operator == Operator.EQ
        assert filter_obj.value == "test"

    def test_where_with_kwargs(self):
        """kwargs를 사용한 WHERE 조건"""
        builder = QueryBuilder(MockModel)
        result = builder.where(name="john", age=25, active=True)

        assert len(builder.filters) == 3

        # 각 필터 확인
        fields = [f.field for f in builder.filters]
        assert "name" in fields
        assert "age" in fields
        assert "active" in fields

        # 모든 필터가 EQ 연산자 사용
        for filter_obj in builder.filters:
            assert filter_obj.operator == Operator.EQ

    def test_where_mixed_params_and_kwargs(self):
        """직접 파라미터와 kwargs 혼합 사용"""
        builder = QueryBuilder(MockModel)
        result = builder.where(
            "status", Operator.NE, "deleted", name="john", active=True
        )

        assert len(builder.filters) == 3

        # 첫 번째는 직접 파라미터
        first_filter = builder.filters[0]
        assert first_filter.field == "status"
        assert first_filter.operator == Operator.NE
        assert first_filter.value == "deleted"

        # 나머지는 kwargs (EQ 연산자)
        remaining_filters = builder.filters[1:]
        for filter_obj in remaining_filters:
            assert filter_obj.operator == Operator.EQ

    def test_where_none_value_ignored(self):
        """None 값이 있는 경우 무시되는지 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.where("name", Operator.EQ, None)

        # value가 None이면 필터가 추가되지 않음
        assert len(builder.filters) == 0

    def test_filter_method(self):
        """filter 메서드로 Filter 객체 직접 추가"""
        builder = QueryBuilder(MockModel)

        filter1 = Filter("name", Operator.LIKE, "%test%")
        filter2 = Filter("age", Operator.GT, 18)

        result = builder.filter(filter1, filter2)

        assert result is builder
        assert len(builder.filters) == 2
        assert builder.filters[0] == filter1
        assert builder.filters[1] == filter2

    def test_order_by_default_asc(self):
        """order_by 메서드 (기본 오름차순)"""
        builder = QueryBuilder(MockModel)
        result = builder.order_by("name")

        assert result is builder
        assert len(builder.sorts) == 1

        sort_obj = builder.sorts[0]
        assert sort_obj.field == "name"
        assert sort_obj.order == SortOrder.ASC

    def test_order_by_explicit_desc(self):
        """order_by 메서드 (명시적 내림차순)"""
        builder = QueryBuilder(MockModel)
        result = builder.order_by("created_at", SortOrder.DESC)

        assert len(builder.sorts) == 1
        sort_obj = builder.sorts[0]
        assert sort_obj.field == "created_at"
        assert sort_obj.order == SortOrder.DESC

    def test_sort_alias_method(self):
        """sort 메서드 (order_by의 별칭)"""
        builder = QueryBuilder(MockModel)
        result = builder.sort("priority", SortOrder.DESC)

        assert result is builder
        assert len(builder.sorts) == 1

        sort_obj = builder.sorts[0]
        assert sort_obj.field == "priority"
        assert sort_obj.order == SortOrder.DESC

    def test_multiple_sorts(self):
        """다중 정렬 조건"""
        builder = QueryBuilder(MockModel)
        result = builder.order_by("status").order_by("name", SortOrder.DESC)

        assert len(builder.sorts) == 2

        assert builder.sorts[0].field == "status"
        assert builder.sorts[0].order == SortOrder.ASC

        assert builder.sorts[1].field == "name"
        assert builder.sorts[1].order == SortOrder.DESC


class TestQueryBuilderPagination:
    """QueryBuilder 페이지네이션 테스트"""

    def test_limit_method(self):
        """limit 메서드 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.limit(25)

        assert result is builder
        assert builder.pagination is not None
        assert builder.pagination.limit == 25
        assert builder.pagination.offset == 0  # 기본값

    def test_offset_method(self):
        """offset 메서드 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.offset(50)

        assert result is builder
        assert builder.pagination is not None
        assert builder.pagination.limit == 10  # 기본값
        assert builder.pagination.offset == 50

    def test_limit_and_offset_combination(self):
        """limit과 offset 조합"""
        builder = QueryBuilder(MockModel)
        result = builder.limit(20).offset(40)

        assert builder.pagination.limit == 20
        assert builder.pagination.offset == 40

    def test_offset_and_limit_combination(self):
        """offset과 limit 순서 바뀌어도 동작"""
        builder = QueryBuilder(MockModel)
        result = builder.offset(60).limit(30)

        assert builder.pagination.limit == 30
        assert builder.pagination.offset == 60

    def test_page_method(self):
        """page 메서드 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.page(3, 20)

        assert result is builder
        assert builder.pagination is not None
        assert builder.pagination.limit == 20
        assert builder.pagination.offset == 40  # (3-1) * 20

    def test_page_overwrites_limit_offset(self):
        """page 메서드가 기존 limit/offset을 덮어쓰는지 확인"""
        builder = QueryBuilder(MockModel)
        result = builder.limit(10).offset(5).page(2, 25)

        # page 메서드 설정이 최종 적용
        assert builder.pagination.limit == 25
        assert builder.pagination.offset == 25  # (2-1) * 25


class TestQueryBuilderAdvancedFeatures:
    """QueryBuilder 고급 기능 테스트"""

    def test_select_method(self):
        """select 메서드 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.select("id", "name", "email")

        assert result is builder
        assert builder._select_fields == ["id", "name", "email"]

    def test_select_multiple_calls(self):
        """select 메서드 여러 번 호출"""
        builder = QueryBuilder(MockModel)
        result = builder.select("id", "name").select("email", "created_at")

        assert builder._select_fields == ["id", "name", "email", "created_at"]

    def test_group_by_method(self):
        """group_by 메서드 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.group_by("category", "status")

        assert result is builder
        assert builder._group_by == ["category", "status"]

    def test_group_by_multiple_calls(self):
        """group_by 메서드 여러 번 호출"""
        builder = QueryBuilder(MockModel)
        result = builder.group_by("category").group_by("status", "type")

        assert builder._group_by == ["category", "status", "type"]

    def test_having_method(self):
        """having 메서드 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.having("count", Operator.GT, 5)

        assert result is builder
        assert len(builder._having) == 1

        having_filter = builder._having[0]
        assert having_filter.field == "count"
        assert having_filter.operator == Operator.GT
        assert having_filter.value == 5

    def test_having_multiple_conditions(self):
        """having 메서드 다중 조건"""
        builder = QueryBuilder(MockModel)
        result = builder.having("count", Operator.GT, 5).having(
            "avg_score", Operator.GE, 80
        )

        assert len(builder._having) == 2

        assert builder._having[0].field == "count"
        assert builder._having[1].field == "avg_score"

    def test_distinct_method_default(self):
        """distinct 메서드 (기본값 True)"""
        builder = QueryBuilder(MockModel)
        result = builder.distinct()

        assert result is builder
        assert builder._distinct is True

    def test_distinct_method_explicit(self):
        """distinct 메서드 (명시적 값)"""
        builder = QueryBuilder(MockModel)

        # 명시적으로 True
        result = builder.distinct(True)
        assert builder._distinct is True

        # 명시적으로 False
        result = builder.distinct(False)
        assert builder._distinct is False

    def test_count_method(self):
        """count 메서드 테스트"""
        builder = QueryBuilder(MockModel)
        result = builder.count()

        assert result is builder
        assert builder._count_only is True

    def test_complex_method_chaining(self):
        """복잡한 메서드 체이닝"""
        builder = QueryBuilder(MockModel)

        result = (
            builder.select("id", "name", "status")
            .where("active", Operator.EQ, True)
            .where(category="tech", priority=1)
            .order_by("created_at", SortOrder.DESC)
            .order_by("name")
            .group_by("category")
            .having("count", Operator.GT, 2)
            .distinct()
            .limit(20)
            .offset(10)
        )

        # 모든 설정이 올바르게 적용되었는지 확인
        assert builder._select_fields == ["id", "name", "status"]
        assert len(builder.filters) == 3  # active + category + priority
        assert len(builder.sorts) == 2
        assert builder._group_by == ["category"]
        assert len(builder._having) == 1
        assert builder._distinct is True
        assert builder.pagination.limit == 20
        assert builder.pagination.offset == 10

        # 체이닝 결과가 같은 객체인지 확인
        assert result is builder


class TestQueryBuilderExecution:
    """QueryBuilder 실행 테스트"""

    @pytest.mark.asyncio
    async def test_execute_simple_select(self):
        """기본 SELECT 실행"""
        builder = QueryBuilder(MockModel)
        builder.where("status", Operator.EQ, "active")

        result = await builder.execute()

        assert result.is_success()
        data = result.unwrap()
        assert isinstance(data, list)
        assert len(data) == 3  # MockModel의 기본 데이터

    @pytest.mark.asyncio
    async def test_execute_with_sorting(self):
        """정렬 적용된 SELECT 실행"""
        builder = QueryBuilder(MockModel)
        builder.order_by("age", SortOrder.DESC)

        result = await builder.execute()

        assert result.is_success()
        data = result.unwrap()

        # 정렬 확인 (나이 내림차순)
        if len(data) > 1 and hasattr(data[0], "age"):
            ages = [item.age for item in data if hasattr(item, "age")]
            assert ages == sorted(ages, reverse=True)

    @pytest.mark.asyncio
    async def test_execute_with_pagination(self):
        """페이지네이션 적용된 SELECT 실행"""
        builder = QueryBuilder(MockModel)
        builder.limit(2).offset(1)

        result = await builder.execute()

        assert result.is_success()
        data = result.unwrap()
        assert len(data) == 2  # limit 적용

    @pytest.mark.asyncio
    async def test_execute_count_query(self):
        """COUNT 쿼리 실행"""
        builder = QueryBuilder(MockModel)
        builder.count()

        result = await builder.execute()

        assert result.is_success()
        count = result.unwrap()
        assert isinstance(count, int)
        assert count == 3  # MockModel의 기본 데이터 개수

    @pytest.mark.asyncio
    async def test_execute_model_filter_failure(self):
        """모델 필터링 실패 처리"""
        builder = QueryBuilder(MockModel)

        # MockModel의 filter 메서드가 실패를 반환하도록 패치
        with patch.object(MockModel, "filter", new_callable=AsyncMock) as mock_filter:
            mock_filter.return_value = Failure("필터링 실패")

            result = await builder.execute()

            assert result.is_failure()
            error = result.unwrap_error()
            # 실제 에러 메시지에 맞춰서 검증
            assert "SELECT 실행 실패" in error or "모델 필터링 실패" in error

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self):
        """예외 처리 테스트"""
        builder = QueryBuilder(MockModel)

        # 예외를 유발할 상황 시뮬레이션 - filter 메서드에서 예외 발생
        with patch.object(MockModel, "filter", new_callable=AsyncMock) as mock_filter:
            mock_filter.side_effect = Exception("데이터베이스 연결 오류")

            result = await builder.execute()

            assert result.is_failure()
            error = result.unwrap_error()
            assert "쿼리 실행 실패" in error or "SELECT 실행 실패" in error

    def test_apply_sorting_empty_list(self):
        """빈 리스트에 정렬 적용"""
        builder = QueryBuilder(MockModel)
        result = builder._apply_sorting([])

        assert result == []

    def test_apply_sorting_no_sorts(self):
        """정렬 조건이 없는 경우"""
        builder = QueryBuilder(MockModel)
        data = [Mock(name="b"), Mock(name="a")]

        result = builder._apply_sorting(data)

        assert result == data  # 원본 그대로 반환

    def test_apply_sorting_with_missing_attribute(self):
        """정렬 필드가 없는 객체들"""
        builder = QueryBuilder(MockModel)
        builder.order_by("nonexistent_field")

        # 속성이 없는 Mock 객체들
        data = [Mock(), Mock()]

        # 예외가 발생하더라도 원본 데이터 반환
        result = builder._apply_sorting(data)
        assert len(result) == 2


class TestHelperFunctions:
    """헬퍼 함수들 테스트"""

    def test_Q_function_success(self):
        """Q 함수 정상 사용"""
        builder = Q(MockModel)

        assert isinstance(builder, QueryBuilder)
        assert builder.model_class == MockModel

    def test_Q_function_none_model_error(self):
        """Q 함수에 None 모델 전달시 에러"""
        with pytest.raises(ValueError, match="모델 클래스가 필요합니다"):
            Q(None)

    def test_build_query_function(self):
        """build_query 함수 테스트"""
        builder = build_query(MockModel)

        assert isinstance(builder, QueryBuilder)
        assert builder.model_class == MockModel

    @pytest.mark.asyncio
    async def test_execute_query_function(self):
        """execute_query 함수 테스트"""
        builder = Q(MockModel).where("name", Operator.EQ, "test")

        result = await execute_query(builder)

        assert result.is_success()
        data = result.unwrap()
        assert isinstance(data, list)

    # 편의 함수들 테스트
    def test_eq_helper(self):
        """eq 편의 함수"""
        filter_obj = eq("name", "john")
        assert filter_obj.field == "name"
        assert filter_obj.operator == Operator.EQ
        assert filter_obj.value == "john"

    def test_ne_helper(self):
        """ne 편의 함수"""
        filter_obj = ne("status", "deleted")
        assert filter_obj.operator == Operator.NE
        assert filter_obj.value == "deleted"

    def test_comparison_helpers(self):
        """비교 연산자 편의 함수들"""
        assert lt("age", 30).operator == Operator.LT
        assert le("age", 30).operator == Operator.LE
        assert gt("age", 18).operator == Operator.GT
        assert ge("age", 18).operator == Operator.GE

    def test_in_helpers(self):
        """IN 연산자 편의 함수들"""
        values = ["active", "pending"]

        in_filter = in_("status", values)
        assert in_filter.operator == Operator.IN
        assert in_filter.value == values

        nin_filter = nin("status", values)
        assert nin_filter.operator == Operator.NIN
        assert nin_filter.value == values

    def test_like_helpers(self):
        """LIKE 연산자 편의 함수들"""
        pattern = "%test%"

        like_filter = like("name", pattern)
        assert like_filter.operator == Operator.LIKE
        assert like_filter.value == pattern

        ilike_filter = ilike("name", pattern)
        assert ilike_filter.operator == Operator.ILIKE
        assert ilike_filter.value == pattern

    def test_null_helpers(self):
        """NULL 체크 편의 함수들"""
        null_filter = is_null("deleted_at")
        assert null_filter.operator == Operator.IS_NULL
        assert null_filter.value is None

        not_null_filter = is_not_null("created_at")
        assert not_null_filter.operator == Operator.IS_NOT_NULL
        assert not_null_filter.value is None

    def test_between_helper(self):
        """between 편의 함수"""
        filter_obj = between("age", 18, 65)
        assert filter_obj.operator == Operator.BETWEEN
        assert filter_obj.value == [18, 65]

    def test_contains_helper(self):
        """contains 편의 함수"""
        filter_obj = contains("tags", "python")
        assert filter_obj.operator == Operator.CONTAINS
        assert filter_obj.value == "python"

    def test_regex_helper(self):
        """regex 편의 함수"""
        pattern = r"^\d{3}-\d{4}-\d{4}$"
        filter_obj = regex("phone", pattern)
        assert filter_obj.operator == Operator.REGEX
        assert filter_obj.value == pattern


class TestAdvancedQueryBuilder:
    """AdvancedQueryBuilder 테스트"""

    def test_advanced_builder_creation(self):
        """AdvancedQueryBuilder 생성 테스트"""
        builder = AdvancedQueryBuilder(MockModel)

        assert isinstance(builder, QueryBuilder)  # 상속 확인
        assert builder.model_class == MockModel
        assert hasattr(builder, "_joins")
        assert hasattr(builder, "_subqueries")
        assert hasattr(builder, "_union_queries")

    def test_join_method(self):
        """JOIN 메서드 테스트"""
        builder = AdvancedQueryBuilder(MockModel)

        class RelatedModel:
            pass

        result = builder.join(RelatedModel, "user.id = profile.user_id", "inner")

        assert result is builder  # 체이닝 확인
        assert len(builder._joins) == 1

        join = builder._joins[0]
        assert join["model_class"] == RelatedModel
        assert join["on"] == "user.id = profile.user_id"
        assert join["type"] == "inner"

    def test_join_type_specific_methods(self):
        """특정 JOIN 타입 메서드들"""
        builder = AdvancedQueryBuilder(MockModel)

        class RelatedModel:
            pass

        # LEFT JOIN
        builder.left_join(RelatedModel, "condition")
        assert builder._joins[-1]["type"] == "left"

        # RIGHT JOIN
        builder.right_join(RelatedModel, "condition")
        assert builder._joins[-1]["type"] == "right"

        # INNER JOIN
        builder.inner_join(RelatedModel, "condition")
        assert builder._joins[-1]["type"] == "inner"

    def test_subquery_method(self):
        """서브쿼리 메서드 테스트"""
        builder = AdvancedQueryBuilder(MockModel)
        subquery = AdvancedQueryBuilder(MockModel)

        result = builder.subquery(subquery, "sub_alias")

        assert result is builder
        assert len(builder._subqueries) == 1
        assert builder._subqueries[0] == subquery
        assert hasattr(subquery, "_alias")
        assert subquery._alias == "sub_alias"

    def test_union_method(self):
        """UNION 메서드 테스트"""
        builder = AdvancedQueryBuilder(MockModel)
        union_query = AdvancedQueryBuilder(MockModel)

        result = builder.union(union_query)

        assert result is builder
        assert len(builder._union_queries) == 1
        assert builder._union_queries[0] == union_query

    def test_raw_method(self):
        """Raw SQL 메서드 테스트 (로그 경고만 확인)"""
        builder = AdvancedQueryBuilder(MockModel)

        result = builder.raw("SELECT * FROM users", {"param": "value"})

        # 현재는 경고 로그만 출력하고 체이닝 반환
        assert result is builder


class TestTransactionalQueryBuilder:
    """TransactionalQueryBuilder 테스트"""

    def test_transactional_builder_creation(self):
        """TransactionalQueryBuilder 생성"""
        mock_transaction_manager = Mock()
        builder = TransactionalQueryBuilder(MockModel, mock_transaction_manager)

        assert isinstance(builder, AdvancedQueryBuilder)
        assert builder.transaction_manager == mock_transaction_manager

    def test_transactional_builder_no_manager(self):
        """트랜잭션 매니저 없이 생성"""
        builder = TransactionalQueryBuilder(MockModel)

        assert builder.transaction_manager is None

    @pytest.mark.asyncio
    async def test_execute_with_transaction_manager(self):
        """트랜잭션 매니저와 함께 실행"""
        mock_manager = Mock()
        mock_transaction = AsyncMock()
        mock_manager.transaction.return_value = mock_transaction

        builder = TransactionalQueryBuilder(MockModel, mock_manager)
        builder.where("name", Operator.EQ, "test")

        result = await builder.execute()

        # 트랜잭션이 사용되었는지 확인
        mock_manager.transaction.assert_called_once()
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_execute_without_transaction_manager(self):
        """트랜잭션 매니저 없이 실행"""
        builder = TransactionalQueryBuilder(MockModel)
        builder.where("name", Operator.EQ, "test")

        result = await builder.execute()

        # 일반 실행과 동일
        assert result.is_success()

    @pytest.mark.asyncio
    async def test_execute_batch_with_transaction(self):
        """배치 실행 (트랜잭션 포함)"""
        mock_manager = Mock()
        mock_transaction = AsyncMock()
        mock_manager.transaction.return_value = mock_transaction

        builder = TransactionalQueryBuilder(MockModel, mock_manager)

        # 배치용 쿼리들
        query1 = QueryBuilder(MockModel).where("id", Operator.EQ, 1)
        query2 = QueryBuilder(MockModel).where("id", Operator.EQ, 2)

        result = await builder.execute_batch([query1, query2])

        assert result.is_success()
        results = result.unwrap()
        assert len(results) == 2

        # 트랜잭션이 사용되었는지 확인
        mock_manager.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_batch_without_transaction(self):
        """배치 실행 (트랜잭션 없음)"""
        builder = TransactionalQueryBuilder(MockModel)

        query1 = QueryBuilder(MockModel).where("id", Operator.EQ, 1)
        query2 = QueryBuilder(MockModel).where("id", Operator.EQ, 2)

        result = await builder.execute_batch([query1, query2])

        assert result.is_success()
        results = result.unwrap()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_batch_partial_failure(self):
        """배치 실행 중 일부 실패"""
        builder = TransactionalQueryBuilder(MockModel)

        # 성공 쿼리와 실패 쿼리 생성
        success_query = QueryBuilder(MockModel).where("id", Operator.EQ, 1)
        fail_query = Mock()
        fail_query.execute = AsyncMock(return_value=Failure("실행 실패"))

        result = await builder.execute_batch([success_query, fail_query])

        assert result.is_failure()
        error = result.unwrap_error()
        # 실제 에러 메시지에 맞춰서 검증
        assert "배치 쿼리 실패" in error or "배치 쿼리 실행 실패" in error

    @pytest.mark.asyncio
    async def test_execute_batch_exception_handling(self):
        """배치 실행 예외 처리"""
        builder = TransactionalQueryBuilder(MockModel)

        # 예외를 유발할 잘못된 쿼리
        invalid_query = Mock()
        invalid_query.execute = AsyncMock(side_effect=Exception("테스트 예외"))

        result = await builder.execute_batch([invalid_query])

        assert result.is_failure()
        error = result.unwrap_error()
        assert "배치 쿼리 실행 실패" in error


class TestEdgeCasesAndErrors:
    """경계 케이스 및 에러 처리 테스트"""

    def test_empty_query_execution_ready(self):
        """필터 없는 빈 쿼리도 실행 가능해야 함"""
        builder = QueryBuilder(MockModel)

        # 필터 없이도 쿼리 빌더 생성 가능
        assert len(builder.filters) == 0
        assert len(builder.sorts) == 0

    def test_multiple_pagination_overrides(self):
        """페이지네이션 여러 번 설정시 최신 값 적용"""
        builder = QueryBuilder(MockModel)

        # 여러 번 설정
        builder.limit(10).offset(5)
        builder.page(3, 20)  # 이것이 최종 적용

        assert builder.pagination.limit == 20
        assert builder.pagination.offset == 40  # (3-1) * 20

    def test_filter_with_various_data_types(self):
        """다양한 데이터 타입으로 필터 생성"""
        builder = QueryBuilder(MockModel)

        # 문자열, 숫자, 불린, 리스트 (None은 제외 - where 메서드에서 무시됨)
        builder.where("name", Operator.EQ, "test")
        builder.where("age", Operator.GT, 25)
        builder.where("active", Operator.EQ, True)
        builder.where("tags", Operator.IN, ["python", "web"])

        # Filter 객체로 직접 추가 (None 값 포함)
        builder.filter(Filter("deleted_at", Operator.IS_NULL))

        assert len(builder.filters) == 5

        # 타입 검증
        values = [f.value for f in builder.filters]
        assert "test" in values
        assert 25 in values
        assert True in values
        assert ["python", "web"] in values
        assert None in values

    def test_sort_field_with_special_characters(self):
        """특수 문자가 포함된 필드명으로 정렬"""
        builder = QueryBuilder(MockModel)

        builder.order_by("user_profile.created_at")
        builder.order_by("metadata->>'type'")

        assert len(builder.sorts) == 2
        assert builder.sorts[0].field == "user_profile.created_at"
        assert builder.sorts[1].field == "metadata->>'type'"

    @pytest.mark.asyncio
    async def test_execute_with_all_features(self):
        """모든 기능을 조합한 복합 쿼리 실행"""
        builder = QueryBuilder(MockModel)

        # 모든 기능 조합
        result = (
            builder.select("id", "name", "status")
            .where("active", Operator.EQ, True)
            .where("category", Operator.IN, ["tech", "news"])
            .order_by("priority", SortOrder.DESC)
            .order_by("name")
            .group_by("status")
            .having("count", Operator.GT, 1)
            .distinct()
            .limit(5)
            .offset(10)
        )

        execution_result = await builder.execute()

        # 복합 쿼리도 정상 실행
        assert execution_result.is_success()

    def test_large_number_of_filters(self):
        """많은 수의 필터 처리"""
        builder = QueryBuilder(MockModel)

        # 100개의 필터 추가
        for i in range(100):
            builder.where(f"field_{i}", Operator.EQ, f"value_{i}")

        assert len(builder.filters) == 100

        # 모든 필터가 올바르게 추가되었는지 확인
        field_names = [f.field for f in builder.filters]
        assert "field_0" in field_names
        assert "field_99" in field_names

    def test_performance_with_many_sorts(self):
        """많은 정렬 조건 처리"""
        builder = QueryBuilder(MockModel)

        # 50개의 정렬 조건
        for i in range(50):
            order = SortOrder.ASC if i % 2 == 0 else SortOrder.DESC
            builder.order_by(f"sort_field_{i}", order)

        assert len(builder.sorts) == 50

        # 정렬 순서가 올바르게 설정되었는지 확인
        asc_count = sum(1 for s in builder.sorts if s.order == SortOrder.ASC)
        desc_count = sum(1 for s in builder.sorts if s.order == SortOrder.DESC)

        assert asc_count == 25  # 짝수 인덱스
        assert desc_count == 25  # 홀수 인덱스


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
