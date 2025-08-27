"""
RFS Framework Core Result 패턴 포괄적 단위 테스트

이 모듈은 Result 패턴의 모든 기능에 대한 포괄적인 테스트를 제공합니다.
- 기본 Success/Failure 동작
- 함수형 프로그래밍 메서드 (map, bind, etc.)
- 비동기 Result 처리
- Either/Maybe 모나드
- 에러 케이스 및 엣지 케이스
"""

import asyncio
import os

# 직접 import하여 순환 참조 방지
import sys
from typing import Any, List, Optional
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../src"))

from rfs.core.result import (
    Either,
    Failure,
    Maybe,
    Result,
    ResultAsync,
    Success,
    async_failure,
    async_result_decorator,
    async_success,
    async_try_except,
    check_is_exception,
    combine,
    either_to_result,
    first_success,
    from_optional,
    get_error,
    get_value,
    left,
    lift,
    lift2,
    maybe_of,
    maybe_to_result,
    none,
    partition,
    pipe_results,
    result_decorator,
    result_to_either,
    right,
    sequence,
    some,
    traverse,
    try_except,
)


class TestBasicResultOperations:
    """기본 Result 연산 테스트"""

    def test_success_creation_and_properties(self):
        """Success 생성 및 속성 테스트"""
        result = Success("test_value")

        assert result.is_success() is True
        assert result.is_failure() is False
        assert result.unwrap() == "test_value"
        assert result.unwrap_or("default") == "test_value"
        assert str(result) == "Success(test_value)"

    def test_failure_creation_and_properties(self):
        """Failure 생성 및 속성 테스트"""
        error = ValueError("test_error")
        result = Failure(error)

        assert result.is_success() is False
        assert result.is_failure() is True
        assert result.unwrap_or("default") == "default"
        assert result.unwrap_error() == error
        assert str(result) == f"Failure({error})"

    def test_failure_unwrap_raises_exception(self):
        """Failure unwrap시 예외 발생 테스트"""
        error = ValueError("test_error")
        result = Failure(error)

        with pytest.raises(ValueError, match="test_error"):
            result.unwrap()

    def test_convenience_functions(self):
        """편의 함수 테스트"""
        success_result = Success("value")
        failure_result = Failure("error")

        assert success_result.is_success()
        assert failure_result.is_failure()
        assert success_result.unwrap() == "value"
        assert failure_result.unwrap_error() == "error"

    def test_equality_comparison(self):
        """동등성 비교 테스트"""
        success1 = Success("test")
        success2 = Success("test")
        success3 = Success("different")
        failure1 = Failure("error")
        failure2 = Failure("error")

        assert success1 == success2
        assert success1 != success3
        assert success1 != failure1
        assert failure1 == failure2


class TestResultFunctorOperations:
    """Result Functor 연산 테스트 (map)"""

    def test_success_map(self):
        """Success에 대한 map 연산"""
        result = Success(5)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_success()
        assert mapped.unwrap() == 10

    def test_success_map_with_exception(self):
        """Success map에서 예외 발생시 Failure로 변환"""
        result = Success(5)
        mapped = result.map(lambda x: x / 0)

        assert mapped.is_failure()
        assert isinstance(mapped.unwrap_error(), ZeroDivisionError)

    def test_failure_map_unchanged(self):
        """Failure에 대한 map은 변경되지 않음"""
        error = ValueError("original_error")
        result = Failure(error)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_failure()
        assert mapped.unwrap_error() is error

    def test_map_error_on_success(self):
        """Success에 대한 map_error는 변경되지 않음"""
        result = Success("value")
        mapped = result.map_error(lambda e: f"transformed_{e}")

        assert mapped.is_success()
        assert mapped.unwrap() == "value"

    def test_map_error_on_failure(self):
        """Failure에 대한 map_error로 에러 변환"""
        result = Failure("original_error")
        mapped = result.map_error(lambda e: f"transformed_{e}")

        assert mapped.is_failure()
        assert mapped.unwrap_error() == "transformed_original_error"

    def test_map_error_with_exception(self):
        """map_error에서 예외 발생시 Failure 유지"""
        result = Failure(10)
        mapped = result.map_error(lambda e: e / 0)

        assert mapped.is_failure()
        assert isinstance(mapped.unwrap_error(), ZeroDivisionError)


class TestResultMonadOperations:
    """Result Monad 연산 테스트 (bind)"""

    def test_success_bind(self):
        """Success에 대한 bind 연산"""
        result = Success(5)
        bound = result.bind(lambda x: Success(x * 2))

        assert bound.is_success()
        assert bound.unwrap() == 10

    def test_success_bind_to_failure(self):
        """Success bind에서 Failure 반환"""
        result = Success(5)
        bound = result.bind(lambda x: Failure("error"))

        assert bound.is_failure()
        assert bound.unwrap_error() == "error"

    def test_success_bind_with_exception(self):
        """Success bind에서 예외 발생시 Failure로 변환"""
        result = Success(5)
        bound = result.bind(lambda x: x / 0)  # 예외 발생

        assert bound.is_failure()
        assert isinstance(bound.unwrap_error(), ZeroDivisionError)

    def test_failure_bind_unchanged(self):
        """Failure에 대한 bind는 변경되지 않음"""
        error = ValueError("original_error")
        result = Failure(error)
        bound = result.bind(lambda x: Success(x * 2))

        assert bound.is_failure()
        assert bound.unwrap_error() is error

    def test_result_chaining(self):
        """Result 체이닝 테스트"""

        def add_one(x: int) -> Result[int, str]:
            return Success(x + 1)

        def multiply_two(x: int) -> Result[int, str]:
            return Success(x * 2)

        def fail_if_even(x: int) -> Result[int, str]:
            return Failure("even") if x % 2 == 0 else Success(x)

        # 성공 케이스
        result = Success(5).bind(add_one).bind(multiply_two)
        assert result.is_success()
        assert result.unwrap() == 12

        # 중간에 실패 케이스
        result = Success(3).bind(add_one).bind(fail_if_even)
        assert result.is_failure()
        assert result.unwrap_error() == "even"


class TestResultUtilityFunctions:
    """Result 유틸리티 함수 테스트"""

    def test_try_except_success(self):
        """try_except 성공 케이스"""
        result = try_except(lambda: 10 / 2)

        assert result.is_success()
        assert result.unwrap() == 5.0

    def test_try_except_failure(self):
        """try_except 실패 케이스"""
        result = try_except(lambda: 10 / 0)

        assert result.is_failure()
        assert isinstance(result.unwrap_error(), ZeroDivisionError)

    @pytest.mark.asyncio
    async def test_async_try_except_success(self):
        """비동기 try_except 성공 케이스"""

        async def async_func():
            await asyncio.sleep(0.01)
            return "Success"

        result = await async_try_except(async_func)

        assert result.is_success()
        assert result.unwrap() == "Success"

    @pytest.mark.asyncio
    async def test_async_try_except_failure(self):
        """비동기 try_except 실패 케이스"""

        async def async_func():
            await asyncio.sleep(0.01)
            raise ValueError("async_error")

        result = await async_try_except(async_func)

        assert result.is_failure()
        assert isinstance(result.unwrap_error(), ValueError)

    def test_from_optional_with_value(self):
        """Optional에서 Result 변환 - 값 있음"""
        result = from_optional("value")

        assert result.is_success()
        assert result.unwrap() == "value"

    def test_from_optional_with_none(self):
        """Optional에서 Result 변환 - None"""
        result = from_optional(None, "custom_error")

        assert result.is_failure()
        assert result.unwrap_error() == "custom_error"

    def test_from_optional_with_none_default_error(self):
        """Optional에서 Result 변환 - None (기본 에러)"""
        result = from_optional(None)

        assert result.is_failure()
        assert isinstance(result.unwrap_error(), ValueError)


class TestResultCollectionOperations:
    """Result 컬렉션 연산 테스트"""

    def test_sequence_all_success(self):
        """sequence - 모든 결과가 성공"""
        results = [Success(1), Success(2), Success(3)]
        sequenced = sequence(results)

        assert sequenced.is_success()
        assert sequenced.unwrap() == [1, 2, 3]

    def test_sequence_with_failure(self):
        """sequence - 실패가 포함된 경우"""
        results = [Success(1), Failure("error"), Success(3)]
        sequenced = sequence(results)

        assert sequenced.is_failure()
        assert sequenced.unwrap_error() == "error"

    def test_sequence_empty_list(self):
        """sequence - 빈 리스트"""
        results = []
        sequenced = sequence(results)

        assert sequenced.is_success()
        assert sequenced.unwrap() == []

    def test_traverse_all_success(self):
        """traverse - 모든 변환이 성공"""

        def safe_divide(x: int) -> Result[float, str]:
            return Success(x / 2.0)

        result = traverse([2, 4, 6], safe_divide)

        assert result.is_success()
        assert result.unwrap() == [1.0, 2.0, 3.0]

    def test_traverse_with_failure(self):
        """traverse - 변환 중 실패"""

        def safe_divide(x: int) -> Result[float, str]:
            return Failure("divide_error") if x == 0 else Success(x / 2.0)

        result = traverse([2, 0, 6], safe_divide)

        assert result.is_failure()
        assert result.unwrap_error() == "divide_error"

    def test_combine_all_success(self):
        """combine - 모든 결과가 성공"""
        result = combine(Success(1), Success("test"), Success(True))

        assert result.is_success()
        assert result.unwrap() == (1, "test", True)

    def test_combine_with_failure(self):
        """combine - 실패가 포함된 경우"""
        result = combine(Success(1), Failure("error"), Success(True))

        assert result.is_failure()
        assert result.unwrap_error() == "error"

    def test_first_success_found(self):
        """first_success - 첫 번째 성공 찾기"""
        result = first_success(Failure("error1"), Success("Success"), Failure("error2"))

        assert result.is_success()
        assert result.unwrap() == "Success"

    def test_first_success_all_failures(self):
        """first_success - 모든 결과가 실패"""
        result = first_success(Failure("error1"), Failure("error2"), Failure("error3"))

        assert result.is_failure()
        assert result.unwrap_error() == ["error1", "error2", "error3"]

    def test_partition(self):
        """partition - 성공과 실패 분리"""
        results = [
            Success(1),
            Failure("error1"),
            Success(2),
            Failure("error2"),
            Success(3),
        ]

        successes, failures = partition(results)

        assert successes == [1, 2, 3]
        assert failures == ["error1", "error2"]


class TestResultHigherOrderFunctions:
    """Result 고차 함수 테스트"""

    def test_lift_function(self):
        """lift 함수 테스트"""

        def double(x: int) -> int:
            return x * 2

        lifted_double = lift(double)

        success_result = lifted_double(Success(5))
        assert success_result.is_success()
        assert success_result.unwrap() == 10

        failure_result = lifted_double(Failure("error"))
        assert failure_result.is_failure()
        assert failure_result.unwrap_error() == "error"

    def test_lift2_function(self):
        """lift2 함수 테스트"""

        def add(x: int, y: int) -> int:
            return x + y

        lifted_add = lift2(add)

        # 둘 다 성공
        result = lifted_add(Success(3), Success(4))
        assert result.is_success()
        assert result.unwrap() == 7

        # 첫 번째 실패
        result = lifted_add(Failure("error"), Success(4))
        assert result.is_failure()
        assert result.unwrap_error() == "error"

        # 두 번째 실패
        result = lifted_add(Success(3), Failure("error"))
        assert result.is_failure()
        assert result.unwrap_error() == "error"

    def test_result_decorator(self):
        """result_decorator 테스트"""

        @result_decorator
        def divide(x: float, y: float) -> float:
            return x / y

        success_result = divide(10, 2)
        assert success_result.is_success()
        assert success_result.unwrap() == 5.0

        failure_result = divide(10, 0)
        assert failure_result.is_failure()
        assert isinstance(failure_result.unwrap_error(), ZeroDivisionError)

    @pytest.mark.asyncio
    async def test_async_result_decorator(self):
        """async_result_decorator 테스트"""

        @async_result_decorator
        async def async_divide(x: float, y: float) -> float:
            await asyncio.sleep(0.01)
            return x / y

        success_result = await async_divide(10, 2)
        assert success_result.is_success()
        assert success_result.unwrap() == 5.0

        failure_result = await async_divide(10, 0)
        assert failure_result.is_failure()
        assert isinstance(failure_result.unwrap_error(), ZeroDivisionError)

    def test_pipe_results(self):
        """pipe_results 파이프라인 테스트"""

        def add_one(x: int) -> Result[int, str]:
            return Success(x + 1)

        def multiply_two(x: int) -> Result[int, str]:
            return Success(x * 2)

        def fail_if_greater_than_10(x: int) -> Result[int, str]:
            return Failure("too_large") if x > 10 else Success(x)

        pipeline = pipe_results(add_one, multiply_two, fail_if_greater_than_10)

        # 성공 케이스
        result = pipeline(4)  # (4+1)*2 = 10
        assert result.is_success()
        assert result.unwrap() == 10

        # 실패 케이스
        result = pipeline(5)  # (5+1)*2 = 12 > 10
        assert result.is_failure()
        assert result.unwrap_error() == "too_large"


class TestAsyncResultOperations:
    """비동기 Result 연산 테스트"""

    @pytest.mark.asyncio
    async def test_result_async_creation(self):
        """ResultAsync 생성 및 기본 연산"""
        result = async_success("test_value")

        assert await result.is_success()
        assert not await result.is_failure()
        assert await result.unwrap() == "test_value"
        assert await result.unwrap_or("default") == "test_value"

    @pytest.mark.asyncio
    async def test_result_async_failure(self):
        """ResultAsync 실패 케이스"""
        result = async_failure("error")

        assert not await result.is_success()
        assert await result.is_failure()
        assert await result.unwrap_or("default") == "default"

    @pytest.mark.asyncio
    async def test_result_async_map(self):
        """ResultAsync map 연산"""
        result = async_success(5)
        mapped = result.map(lambda x: x * 2)

        final_result = await mapped.to_result()
        assert final_result.is_success()
        assert final_result.unwrap() == 10

    @pytest.mark.asyncio
    async def test_result_async_map_with_async_function(self):
        """ResultAsync map에 비동기 함수 사용"""

        async def async_multiply(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        result = async_success(5)
        mapped = result.map(async_multiply)

        final_result = await mapped.to_result()
        assert final_result.is_success()
        assert final_result.unwrap() == 10

    @pytest.mark.asyncio
    async def test_result_async_bind(self):
        """ResultAsync bind 연산"""

        def create_async_result(x: int) -> ResultAsync[int, str]:
            return async_success(x * 2)

        result = async_success(5)
        bound = result.bind(create_async_result)

        final_result = await bound.to_result()
        assert final_result.is_success()
        assert final_result.unwrap() == 10

    @pytest.mark.asyncio
    async def test_from_awaitable_success(self):
        """from_awaitable 성공 케이스"""

        async def async_operation():
            await asyncio.sleep(0.01)
            return "Success"

        result_async = await async_operation()
        result = await async_success(result_async).to_result()

        assert result.is_success()
        assert result.unwrap() == "Success"

    @pytest.mark.asyncio
    async def test_from_awaitable_failure(self):
        """from_awaitable 실패 케이스"""

        async def failing_operation():
            await asyncio.sleep(0.01)
            raise ValueError("async_error")

        try:
            await failing_operation()
        except Exception as e:
            result = await async_failure(e).to_result()
            assert result.is_failure()
            assert isinstance(result.unwrap_error(), ValueError)


class TestEitherMonad:
    """Either 모나드 테스트"""

    def test_either_left_creation(self):
        """Either Left 생성"""
        either = Either.left("error")

        assert either.is_left()
        assert not either.is_right()

    def test_either_right_creation(self):
        """Either Right 생성"""
        either = Either.right("value")

        assert either.is_right()
        assert not either.is_left()

    def test_either_fold(self):
        """Either fold 연산"""
        left_either = Either.left("error")
        right_either = Either.right(42)

        left_result = left_either.fold(lambda e: f"Error: {e}", lambda v: f"Value: {v}")
        assert left_result == "Error: error"

        right_result = right_either.fold(
            lambda e: f"Error: {e}", lambda v: f"Value: {v}"
        )
        assert right_result == "Value: 42"

    def test_either_map_right(self):
        """Either Right에 map 연산"""
        either = Either.right(5)
        mapped = either.map(lambda x: x * 2)

        assert mapped.is_right()
        assert mapped._value == 10

    def test_either_map_left(self):
        """Either Left에 map 연산"""
        either = Either.left("error")
        mapped = either.map(lambda x: x * 2)

        assert mapped.is_left()
        assert mapped._value == "error"

    def test_either_flat_map(self):
        """Either flat_map 연산"""
        either = Either.right(5)

        def double_if_positive(x):
            return Either.right(x * 2) if x > 0 else Either.left("negative")

        result = either.flat_map(double_if_positive)
        assert result.is_right()
        assert result._value == 10

    def test_either_map_left_operation(self):
        """Either map_left 연산"""
        either = Either.left("original_error")
        mapped = either.map_left(lambda e: f"transformed_{e}")

        assert mapped.is_left()
        assert mapped._value == "transformed_original_error"

    def test_either_swap(self):
        """Either swap 연산"""
        right_either = Either.right("value")
        left_either = Either.left("error")

        swapped_right = right_either.swap()
        assert swapped_right.is_left()
        assert swapped_right._value == "value"

        swapped_left = left_either.swap()
        assert swapped_left.is_right()
        assert swapped_left._value == "error"

    def test_either_to_result(self):
        """Either를 Result로 변환"""
        right_either = Either.right("value")
        left_either = Either.left("error")

        right_result = right_either.to_result()
        assert right_result.is_success()
        assert right_result.unwrap() == "value"

        left_result = left_either.to_result()
        assert left_result.is_failure()
        assert left_result.unwrap_error() == "error"

    def test_convenience_functions_either(self):
        """Either 편의 함수 테스트"""
        left_val = left("error")
        right_val = right("value")

        assert left_val.is_left()
        assert right_val.is_right()


class TestMaybeMonad:
    """Maybe 모나드 테스트"""

    def test_maybe_some_creation(self):
        """Maybe Some 생성"""
        maybe = Maybe.some("value")

        assert maybe.is_some()
        assert not maybe.is_none()
        assert maybe.get() == "value"

    def test_maybe_none_creation(self):
        """Maybe None 생성"""
        maybe = Maybe.none()

        assert maybe.is_none()
        assert not maybe.is_some()

    def test_maybe_some_with_none_value_raises_error(self):
        """Maybe.some에 None 값 전달시 오류"""
        with pytest.raises(ValueError, match="Some cannot contain None"):
            Maybe.some(None)

    def test_maybe_of_factory(self):
        """Maybe.of 팩토리 메서드"""
        some_maybe = Maybe.of("value")
        none_maybe = Maybe.of(None)

        assert some_maybe.is_some()
        assert some_maybe.get() == "value"

        assert none_maybe.is_none()

    def test_maybe_get_or_else(self):
        """Maybe get_or_else 메서드"""
        some_maybe = Maybe.some("value")
        none_maybe = Maybe.none()

        assert some_maybe.get_or_else("default") == "value"
        assert none_maybe.get_or_else("default") == "default"

    def test_maybe_get_from_none_raises_error(self):
        """Maybe None에서 get 호출시 오류"""
        maybe = Maybe.none()

        with pytest.raises(ValueError, match="Cannot get value from None"):
            maybe.get()

    def test_maybe_map_some(self):
        """Maybe Some에 map 연산"""
        maybe = Maybe.some(5)
        mapped = maybe.map(lambda x: x * 2)

        assert mapped.is_some()
        assert mapped.get() == 10

    def test_maybe_map_none(self):
        """Maybe None에 map 연산"""
        maybe = Maybe.none()
        mapped = maybe.map(lambda x: x * 2)

        assert mapped.is_none()

    def test_maybe_map_with_exception(self):
        """Maybe map에서 예외 발생시 None으로 변환"""
        maybe = Maybe.some(5)
        mapped = maybe.map(lambda x: x / 0)

        assert mapped.is_none()

    def test_maybe_flat_map(self):
        """Maybe flat_map 연산"""
        maybe = Maybe.some(5)

        def half_if_even(x):
            return Maybe.some(x // 2) if x % 2 == 0 else Maybe.none()

        result = maybe.flat_map(half_if_even)
        assert result.is_none()  # 5는 홀수이므로

    def test_maybe_filter(self):
        """Maybe filter 연산"""
        some_maybe = Maybe.some(10)
        none_maybe = Maybe.none()

        # 조건을 만족하는 경우
        filtered_some = some_maybe.filter(lambda x: x > 5)
        assert filtered_some.is_some()
        assert filtered_some.get() == 10

        # 조건을 만족하지 않는 경우
        filtered_none = some_maybe.filter(lambda x: x < 5)
        assert filtered_none.is_none()

        # None에 filter 적용
        filtered_none_original = none_maybe.filter(lambda x: x > 5)
        assert filtered_none_original.is_none()

    def test_maybe_or_else(self):
        """Maybe or_else 연산"""
        some_maybe = Maybe.some("value")
        none_maybe = Maybe.none()
        alternative = Maybe.some("alternative")

        assert some_maybe.or_else(alternative).get() == "value"
        assert none_maybe.or_else(alternative).get() == "alternative"

    def test_maybe_to_result(self):
        """Maybe를 Result로 변환"""
        some_maybe = Maybe.some("value")
        none_maybe = Maybe.none()

        some_result = some_maybe.to_result("error")
        assert some_result.is_success()
        assert some_result.unwrap() == "value"

        none_result = none_maybe.to_result("error")
        assert none_result.is_failure()
        assert none_result.unwrap_error() == "error"

    def test_maybe_to_either(self):
        """Maybe를 Either로 변환"""
        some_maybe = Maybe.some("value")
        none_maybe = Maybe.none()

        some_either = some_maybe.to_either("error")
        assert some_either.is_right()
        assert some_either._value == "value"

        none_either = none_maybe.to_either("error")
        assert none_either.is_left()
        assert none_either._value == "error"

    def test_convenience_functions_maybe(self):
        """Maybe 편의 함수 테스트"""
        some_val = some("value")
        none_val = none()
        maybe_val = maybe_of("value")
        maybe_none = maybe_of(None)

        assert some_val.is_some()
        assert none_val.is_none()
        assert maybe_val.is_some()
        assert maybe_none.is_none()


class TestMonadConversions:
    """모나드 간 변환 테스트"""

    def test_result_to_either_conversion(self):
        """Result를 Either로 변환"""
        success_result = Success("value")
        failure_result = Failure("error")

        success_either = result_to_either(success_result)
        assert success_either.is_right()
        assert success_either._value == "value"

        failure_either = result_to_either(failure_result)
        assert failure_either.is_left()
        assert failure_either._value == "error"

    def test_either_to_result_conversion(self):
        """Either를 Result로 변환"""
        right_either = Either.right("value")
        left_either = Either.left("error")

        right_result = either_to_result(right_either)
        assert right_result.is_success()
        assert right_result.unwrap() == "value"

        left_result = either_to_result(left_either)
        assert left_result.is_failure()
        assert left_result.unwrap_error() == "error"

    def test_maybe_to_result_conversion(self):
        """Maybe를 Result로 변환"""
        some_maybe = Maybe.some("value")
        none_maybe = Maybe.none()

        some_result = maybe_to_result(some_maybe, "error")
        assert some_result.is_success()
        assert some_result.unwrap() == "value"

        none_result = maybe_to_result(none_maybe, "error")
        assert none_result.is_failure()
        assert none_result.unwrap_error() == "error"


class TestResultEdgeCases:
    """Result 엣지 케이스 테스트"""

    def test_nested_result_operations(self):
        """중첩된 Result 연산"""

        def create_nested_result(x):
            return Success(Success(x * 2))

        result = Success(5)
        nested = result.bind(create_nested_result)

        assert nested.is_success()
        inner_result = nested.unwrap()
        assert inner_result.is_success()
        assert inner_result.unwrap() == 10

    def test_result_with_none_values(self):
        """None 값을 포함하는 Result"""
        success_with_none = Success(None)

        assert success_with_none.is_success()
        assert success_with_none.unwrap() is None
        assert success_with_none.unwrap_or("default") is None

    def test_result_with_complex_types(self, sample_data):
        """복잡한 타입을 포함하는 Result"""
        complex_data = {
            "users": sample_data["users"],
            "nested": {"deep": {"value": 42}},
        }

        result = Success(complex_data)

        assert result.is_success()
        unwrapped = result.unwrap()
        assert len(unwrapped["users"]) == 3
        assert unwrapped["nested"]["deep"]["value"] == 42

    def test_result_with_large_data(self, edge_case_data):
        """대용량 데이터를 포함하는 Result"""
        large_string = edge_case_data["large_values"]["string"]

        result = Success(large_string)
        mapped = result.map(len)

        assert mapped.is_success()
        assert mapped.unwrap() == 10000

    def test_result_with_unicode(self, edge_case_data):
        """유니코드 문자를 포함하는 Result"""
        unicode_values = edge_case_data["unicode_values"]

        for value in unicode_values:
            result = Success(value)
            mapped = result.map(lambda x: f"processed_{x}")

            assert mapped.is_success()
            assert mapped.unwrap().startswith("processed_")

    @pytest.mark.parametrize("concurrency_level", [1, 5, 10])
    @pytest.mark.asyncio
    async def test_concurrent_result_operations(self, concurrency_level):
        """동시 Result 연산 테스트"""

        async def async_operation(x):
            await asyncio.sleep(0.001)  # 매우 짧은 지연
            return Success(x * 2)

        tasks = [async_operation(i) for i in range(concurrency_level)]
        results = await asyncio.gather(*tasks)

        assert len(results) == concurrency_level
        for i, result in enumerate(results):
            assert result.is_success()
            assert result.unwrap() == i * 2

    def test_compatibility_functions(self):
        """호환성 함수 테스트"""
        success_result = Success("value")
        failure_result = Failure("error")

        # get_value 함수
        assert get_value(success_result) == "value"
        assert get_value(failure_result) is None
        assert get_value(failure_result, "default") == "default"

        # get_error 함수
        assert get_error(success_result) is None
        assert get_error(failure_result) == "error"

        # check_is_exception 함수
        exception = ValueError("test")
        non_exception = "not_exception"

        assert check_is_exception(exception) is True
        assert check_is_exception(non_exception) is False
