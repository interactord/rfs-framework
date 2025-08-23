"""
RFS Database Query (RFS v4.1)

Query Builder 시스템
"""

from typing import Dict, Any, List, Optional, Type, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import operator

from ..core.result import Result, Success, Failure
from ..core.enhanced_logging import get_logger

logger = get_logger(__name__)


class Operator(str, Enum):
    """쿼리 연산자"""
    EQ = "eq"          # equals
    NE = "ne"          # not equals
    LT = "lt"          # less than
    LE = "le"          # less than or equal
    GT = "gt"          # greater than
    GE = "ge"          # greater than or equal
    IN = "in"          # in list
    NIN = "nin"        # not in list
    LIKE = "like"      # SQL LIKE
    ILIKE = "ilike"    # Case insensitive LIKE
    REGEX = "regex"    # Regular expression
    IS_NULL = "is_null"    # IS NULL
    IS_NOT_NULL = "is_not_null"  # IS NOT NULL
    BETWEEN = "between"    # BETWEEN
    CONTAINS = "contains"  # Contains (for arrays/JSON)


class SortOrder(str, Enum):
    """정렬 순서"""
    ASC = "asc"
    DESC = "desc"


@dataclass
class Filter:
    """쿼리 필터"""
    field: str
    operator: Operator
    value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value
        }


@dataclass
class Sort:
    """정렬 조건"""
    field: str
    order: SortOrder = SortOrder.ASC
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "field": self.field,
            "order": self.order.value
        }


@dataclass
class Pagination:
    """페이지네이션"""
    limit: int = 10
    offset: int = 0
    
    @property
    def page(self) -> int:
        """현재 페이지 번호 (1부터 시작)"""
        return (self.offset // self.limit) + 1
    
    @classmethod
    def from_page(cls, page: int, page_size: int) -> 'Pagination':
        """페이지 번호로 생성"""
        offset = (page - 1) * page_size
        return cls(limit=page_size, offset=offset)


class Query(ABC):
    """쿼리 추상 클래스"""
    
    def __init__(self, model_class: Type):
        self.model_class = model_class
        self.filters: List[Filter] = []
        self.sorts: List[Sort] = []
        self.pagination: Optional[Pagination] = None
        self._select_fields: List[str] = []
        self._group_by: List[str] = []
        self._having: List[Filter] = []
        self._distinct: bool = False
        self._count_only: bool = False
    
    @abstractmethod
    async def execute(self) -> Result[Union[List[Any], int], str]:
        """쿼리 실행"""
        pass
    
    def where(self, field: str = None, operator: Operator = Operator.EQ, value: Any = None, **kwargs) -> 'Query':
        """WHERE 조건 추가"""
        if field and operator and value is not None:
            self.filters.append(Filter(field, operator, value))
        
        # 키워드 인자로 간단한 equals 필터 추가
        for field_name, field_value in kwargs.items():
            self.filters.append(Filter(field_name, Operator.EQ, field_value))
        
        return self
    
    def filter(self, *filters: Filter) -> 'Query':
        """필터 추가"""
        self.filters.extend(filters)
        return self
    
    def order_by(self, field: str, order: SortOrder = SortOrder.ASC) -> 'Query':
        """정렬 조건 추가"""
        self.sorts.append(Sort(field, order))
        return self
    
    def sort(self, field: str, order: SortOrder = SortOrder.ASC) -> 'Query':
        """정렬 조건 추가 (order_by 별칭)"""
        return self.order_by(field, order)
    
    def limit(self, limit: int) -> 'Query':
        """LIMIT 설정"""
        if self.pagination is None:
            self.pagination = Pagination()
        self.pagination.limit = limit
        return self
    
    def offset(self, offset: int) -> 'Query':
        """OFFSET 설정"""
        if self.pagination is None:
            self.pagination = Pagination()
        self.pagination.offset = offset
        return self
    
    def page(self, page: int, page_size: int = 10) -> 'Query':
        """페이지 설정"""
        self.pagination = Pagination.from_page(page, page_size)
        return self
    
    def select(self, *fields: str) -> 'Query':
        """SELECT 필드 지정"""
        self._select_fields.extend(fields)
        return self
    
    def group_by(self, *fields: str) -> 'Query':
        """GROUP BY 추가"""
        self._group_by.extend(fields)
        return self
    
    def having(self, field: str, operator: Operator, value: Any) -> 'Query':
        """HAVING 조건 추가"""
        self._having.append(Filter(field, operator, value))
        return self
    
    def distinct(self, enable: bool = True) -> 'Query':
        """DISTINCT 설정"""
        self._distinct = enable
        return self
    
    def count(self) -> 'Query':
        """COUNT 쿼리로 변경"""
        self._count_only = True
        return self


class QueryBuilder(Query):
    """기본 QueryBuilder 구현"""
    
    def __init__(self, model_class: Type):
        super().__init__(model_class)
    
    async def execute(self) -> Result[Union[List[Any], int], str]:
        """쿼리 실행"""
        try:
            if self._count_only:
                return await self._execute_count()
            else:
                return await self._execute_select()
            
        except Exception as e:
            error_msg = f"쿼리 실행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def _execute_select(self) -> Result[List[Any], str]:
        """SELECT 쿼리 실행"""
        try:
            # 모델의 filter 메서드 사용
            filter_dict = {}
            for filter_item in self.filters:
                if filter_item.operator == Operator.EQ:
                    filter_dict[filter_item.field] = filter_item.value
                # 다른 연산자들은 모델별로 구현 필요
            
            result = await self.model_class.filter(**filter_dict)
            if not result.is_success():
                return Failure(f"모델 필터링 실패: {result.unwrap_err()}")
            
            models = result.unwrap()
            
            # 정렬 적용 (메모리에서)
            if self.sorts:
                models = self._apply_sorting(models)
            
            # 페이지네이션 적용 (메모리에서)
            if self.pagination:
                start = self.pagination.offset
                end = start + self.pagination.limit
                models = models[start:end]
            
            return Success(models)
            
        except Exception as e:
            return Failure(f"SELECT 실행 실패: {str(e)}")
    
    async def _execute_count(self) -> Result[int, str]:
        """COUNT 쿼리 실행"""
        try:
            # 필터링된 결과 조회
            result = await self._execute_select()
            if not result.is_success():
                return Failure(result.unwrap_err())
            
            models = result.unwrap()
            return Success(len(models))
            
        except Exception as e:
            return Failure(f"COUNT 실행 실패: {str(e)}")
    
    def _apply_sorting(self, models: List[Any]) -> List[Any]:
        """메모리에서 정렬 적용"""
        if not self.sorts:
            return models
        
        try:
            for sort_item in reversed(self.sorts):  # 역순으로 정렬하여 우선순위 적용
                reverse = sort_item.order == SortOrder.DESC
                
                models.sort(
                    key=lambda m: getattr(m, sort_item.field, None),
                    reverse=reverse
                )
            
            return models
            
        except Exception as e:
            logger.warning(f"정렬 적용 실패: {e}")
            return models


# 쿼리 빌더 팩토리
def Q(model_class: Type = None) -> QueryBuilder:
    """QueryBuilder 생성"""
    if model_class is None:
        raise ValueError("모델 클래스가 필요합니다")
    
    return QueryBuilder(model_class)


# 필터 생성 편의 함수들
def eq(field: str, value: Any) -> Filter:
    """Equals 필터"""
    return Filter(field, Operator.EQ, value)


def ne(field: str, value: Any) -> Filter:
    """Not Equals 필터"""
    return Filter(field, Operator.NE, value)


def lt(field: str, value: Any) -> Filter:
    """Less Than 필터"""
    return Filter(field, Operator.LT, value)


def le(field: str, value: Any) -> Filter:
    """Less Than or Equal 필터"""
    return Filter(field, Operator.LE, value)


def gt(field: str, value: Any) -> Filter:
    """Greater Than 필터"""
    return Filter(field, Operator.GT, value)


def ge(field: str, value: Any) -> Filter:
    """Greater Than or Equal 필터"""
    return Filter(field, Operator.GE, value)


def in_(field: str, values: List[Any]) -> Filter:
    """IN 필터"""
    return Filter(field, Operator.IN, values)


def nin(field: str, values: List[Any]) -> Filter:
    """Not IN 필터"""
    return Filter(field, Operator.NIN, values)


def like(field: str, pattern: str) -> Filter:
    """LIKE 필터"""
    return Filter(field, Operator.LIKE, pattern)


def ilike(field: str, pattern: str) -> Filter:
    """Case Insensitive LIKE 필터"""
    return Filter(field, Operator.ILIKE, pattern)


def regex(field: str, pattern: str) -> Filter:
    """Regular Expression 필터"""
    return Filter(field, Operator.REGEX, pattern)


def is_null(field: str) -> Filter:
    """IS NULL 필터"""
    return Filter(field, Operator.IS_NULL)


def is_not_null(field: str) -> Filter:
    """IS NOT NULL 필터"""
    return Filter(field, Operator.IS_NOT_NULL)


def between(field: str, start: Any, end: Any) -> Filter:
    """BETWEEN 필터"""
    return Filter(field, Operator.BETWEEN, [start, end])


def contains(field: str, value: Any) -> Filter:
    """CONTAINS 필터 (배열/JSON용)"""
    return Filter(field, Operator.CONTAINS, value)


# 쿼리 빌더 편의 함수
def build_query(model_class: Type) -> QueryBuilder:
    """QueryBuilder 생성"""
    return Q(model_class)


async def execute_query(query: Query) -> Result[Union[List[Any], int], str]:
    """쿼리 실행"""
    return await query.execute()


# 고급 쿼리 빌더
class AdvancedQueryBuilder(QueryBuilder):
    """고급 QueryBuilder"""
    
    def __init__(self, model_class: Type):
        super().__init__(model_class)
        self._joins: List[Dict[str, Any]] = []
        self._subqueries: List['AdvancedQueryBuilder'] = []
        self._union_queries: List['AdvancedQueryBuilder'] = []
    
    def join(self, model_class: Type, on: str, join_type: str = "inner") -> 'AdvancedQueryBuilder':
        """JOIN 추가"""
        self._joins.append({
            "model_class": model_class,
            "on": on,
            "type": join_type
        })
        return self
    
    def left_join(self, model_class: Type, on: str) -> 'AdvancedQueryBuilder':
        """LEFT JOIN 추가"""
        return self.join(model_class, on, "left")
    
    def right_join(self, model_class: Type, on: str) -> 'AdvancedQueryBuilder':
        """RIGHT JOIN 추가"""
        return self.join(model_class, on, "right")
    
    def inner_join(self, model_class: Type, on: str) -> 'AdvancedQueryBuilder':
        """INNER JOIN 추가"""
        return self.join(model_class, on, "inner")
    
    def subquery(self, query: 'AdvancedQueryBuilder', alias: str) -> 'AdvancedQueryBuilder':
        """서브쿼리 추가"""
        query._alias = alias
        self._subqueries.append(query)
        return self
    
    def union(self, query: 'AdvancedQueryBuilder') -> 'AdvancedQueryBuilder':
        """UNION 추가"""
        self._union_queries.append(query)
        return self
    
    def raw(self, sql: str, params: Dict[str, Any] = None) -> 'AdvancedQueryBuilder':
        """Raw SQL 실행 (ORM별로 구현 필요)"""
        # ORM별 구현에서 재정의
        logger.warning("Raw SQL은 ORM별로 구현이 필요합니다")
        return self


# 트랜잭션 지원 쿼리 빌더
class TransactionalQueryBuilder(AdvancedQueryBuilder):
    """트랜잭션 지원 QueryBuilder"""
    
    def __init__(self, model_class: Type, transaction_manager=None):
        super().__init__(model_class)
        self.transaction_manager = transaction_manager
    
    async def execute(self) -> Result[Union[List[Any], int], str]:
        """트랜잭션 내에서 쿼리 실행"""
        if self.transaction_manager:
            async with self.transaction_manager.transaction():
                return await super().execute()
        else:
            return await super().execute()
    
    async def execute_batch(self, queries: List[Query]) -> Result[List[Any], str]:
        """배치 쿼리 실행"""
        try:
            results = []
            
            if self.transaction_manager:
                async with self.transaction_manager.transaction():
                    for query in queries:
                        result = await query.execute()
                        if not result.is_success():
                            return Failure(f"배치 쿼리 실패: {result.unwrap_err()}")
                        results.append(result.unwrap())
            else:
                for query in queries:
                    result = await query.execute()
                    if not result.is_success():
                        return Failure(f"배치 쿼리 실패: {result.unwrap_err()}")
                    results.append(result.unwrap())
            
            logger.info(f"배치 쿼리 완료: {len(queries)}개")
            return Success(results)
            
        except Exception as e:
            error_msg = f"배치 쿼리 실행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)