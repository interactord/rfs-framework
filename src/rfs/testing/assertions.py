"""
RFS Test Assertions (RFS v4.1)

테스트 어설션 라이브러리
"""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Collection, Optional, Type, Union

from ..core.result import Result


class AssertionError(Exception):
    """어설션 오류"""

    pass


def _format_assertion_message(expected: Any, actual: Any, message=None) -> str:
    """어설션 메시지 포맷팅"""
    base_message = f"Expected: {expected}, but was: {actual}"
    if message:
        return f"{message}: {base_message}"
    return base_message


# 기본 어설션들
def assert_equal(expected: Any, actual: Any, message=None):
    """값이 같은지 확인"""
    if expected != actual:
        raise AssertionError(_format_assertion_message(expected, actual, message))


def assert_not_equal(expected: Any, actual: Any, message=None):
    """값이 다른지 확인"""
    if expected == actual:
        raise AssertionError(
            f"Values should not be equal: {expected}"
            + (f": {message}" if message else "")
        )


def assert_true(value: Any, message=None):
    """값이 True인지 확인"""
    if not value:
        raise AssertionError(
            f"Expected True, but was: {value}" + (f": {message}" if message else "")
        )


def assert_false(value: Any, message=None):
    """값이 False인지 확인"""
    if value:
        raise AssertionError(
            f"Expected False, but was: {value}" + (f": {message}" if message else "")
        )


def assert_none(value: Any, message=None):
    """값이 None인지 확인"""
    if value is not None:
        raise AssertionError(
            f"Expected None, but was: {value}" + (f": {message}" if message else "")
        )


def assert_not_none(value: Any, message=None):
    """값이 None이 아닌지 확인"""
    if value is None:
        raise AssertionError(
            f"Expected not None, but was None" + (f": {message}" if message else "")
        )


# 컬렉션 어설션들
def assert_in(item: Any, collection: Collection, message=None):
    """아이템이 컬렉션에 있는지 확인"""
    if item not in collection:
        raise AssertionError(
            f"Expected {item} to be in {collection}"
            + (f": {message}" if message else "")
        )


def assert_not_in(item: Any, collection: Collection, message=None):
    """아이템이 컬렉션에 없는지 확인"""
    if item in collection:
        raise AssertionError(
            f"Expected {item} not to be in {collection}"
            + (f": {message}" if message else "")
        )


def assert_empty(collection: Collection, message=None):
    """컬렉션이 비어있는지 확인"""
    if len(collection) != 0:
        raise AssertionError(
            f"Expected empty collection, but has {len(collection)} items"
            + (f": {message}" if message else "")
        )


def assert_not_empty(collection: Collection, message=None):
    """컬렉션이 비어있지 않은지 확인"""
    if len(collection) == 0:
        raise AssertionError(
            f"Expected non-empty collection, but was empty"
            + (f": {message}" if message else "")
        )


def assert_length(collection: Collection, expected_length: int, message=None):
    """컬렉션의 길이 확인"""
    actual_length = len(collection)
    if actual_length != expected_length:
        raise AssertionError(
            f"Expected length {expected_length}, but was {actual_length}"
            + (f": {message}" if message else "")
        )


# 예외 어설션들
def assert_raises(
    expected_exception: Type[Exception],
    callable_obj: Callable,
    *args,
    message=None,
):
    """예외가 발생하는지 확인"""
    try:
        callable_obj(*args, **kwargs)
        raise AssertionError(
            f"Expected {expected_exception.__name__} to be raised"
            + (f": {message}" if message else "")
        )
    except expected_exception:
        pass  # 예상한 예외가 발생함
    except Exception as e:
        raise AssertionError(
            f"Expected {expected_exception.__name__}, but {type(e).__name__} was raised: {str(e)}"
            + (f": {message}" if message else "")
        )


def assert_not_raises(
    unexpected_exception: Type[Exception],
    callable_obj: Callable,
    *args,
    message=None,
    **kwargs,
):
    """특정 예외가 발생하지 않는지 확인"""
    try:
        result = callable_obj(*args, **kwargs)
        return result
    except unexpected_exception as e:
        raise AssertionError(
            f"Unexpected {unexpected_exception.__name__} was raised: {str(e)}"
            + (f": {message}" if message else "")
        )


# Result 패턴 어설션들
def assert_success(result: Result, message=None):
    """Result가 성공인지 확인"""
    if result.is_failure():
        raise AssertionError(
            f"Expected success, but was failure: {result.unwrap_error()}"
            + (f": {message}" if message else "")
        )


def assert_failure(result: Result, message=None):
    """Result가 실패인지 확인"""
    if result.is_success():
        raise AssertionError(
            f"Expected failure, but was success: {result.unwrap()}"
            + (f": {message}" if message else "")
        )


def assert_result_value(result: Result, expected_value: Any, message=None):
    """Result의 성공 값 확인"""
    assert_success(result, message)
    actual_value = result.unwrap()
    if actual_value != expected_value:
        raise AssertionError(
            _format_assertion_message(expected_value, actual_value, message)
        )


def assert_result_error(result: Result, expected_error: Any, message=None):
    """Result의 오류 값 확인"""
    assert_failure(result, message)
    actual_error = result.unwrap_error()
    if actual_error != expected_error:
        raise AssertionError(
            _format_assertion_message(expected_error, actual_error, message)
        )


# 비동기 어설션들
async def assert_eventually(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    message=None,
):
    """조건이 결국 True가 되는지 확인"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            if condition():
                return
        except Exception:
            pass

        await asyncio.sleep(interval)

    raise AssertionError(
        f"Condition did not become true within {timeout} seconds"
        + (f": {message}" if message else "")
    )


async def assert_timeout(
    coro_or_callable: Union[Callable, Any],
    timeout: float,
    message=None,
):
    """함수/코루틴이 타임아웃 내에 완료되는지 확인"""
    try:
        if asyncio.iscoroutine(coro_or_callable):
            await asyncio.wait_for(coro_or_callable, timeout=timeout)
        elif callable(coro_or_callable):
            if asyncio.iscoroutinefunction(coro_or_callable):
                await asyncio.wait_for(coro_or_callable(), timeout=timeout)
            else:
                # 동기 함수를 별도 스레드에서 실행
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, coro_or_callable), timeout=timeout
                )
        else:
            raise ValueError("coro_or_callable must be a coroutine or callable")

    except asyncio.TimeoutError:
        raise AssertionError(
            f"Operation did not complete within {timeout} seconds"
            + (f": {message}" if message else "")
        )


# 숫자 어설션들
def assert_greater(
    value: Union[int, float],
    threshold: Union[int, float],
    message=None,
):
    """값이 임계값보다 큰지 확인"""
    if value <= threshold:
        raise AssertionError(
            f"Expected {value} > {threshold}" + (f": {message}" if message else "")
        )


def assert_greater_equal(
    value: Union[int, float],
    threshold: Union[int, float],
    message=None,
):
    """값이 임계값보다 크거나 같은지 확인"""
    if value < threshold:
        raise AssertionError(
            f"Expected {value} >= {threshold}" + (f": {message}" if message else "")
        )


def assert_less(
    value: Union[int, float],
    threshold: Union[int, float],
    message=None,
):
    """값이 임계값보다 작은지 확인"""
    if value >= threshold:
        raise AssertionError(
            f"Expected {value} < {threshold}" + (f": {message}" if message else "")
        )


def assert_less_equal(
    value: Union[int, float],
    threshold: Union[int, float],
    message=None,
):
    """값이 임계값보다 작거나 같은지 확인"""
    if value > threshold:
        raise AssertionError(
            f"Expected {value} <= {threshold}" + (f": {message}" if message else "")
        )


def assert_almost_equal(first: float, second: float, places=7, message=None):
    """부동소수점 근사 비교"""
    if round(abs(second - first), places) != 0:
        raise AssertionError(
            f"Expected {first} ≈ {second} (within {places} decimal places)"
            + (f": {message}" if message else "")
        )


# 문자열 어설션들
def assert_starts_with(string: str, prefix: str, message=None):
    """문자열이 특정 접두사로 시작하는지 확인"""
    if not string.startswith(prefix):
        raise AssertionError(
            f"Expected '{string}' to start with '{prefix}'"
            + (f": {message}" if message else "")
        )


def assert_ends_with(string: str, suffix: str, message=None):
    """문자열이 특정 접미사로 끝나는지 확인"""
    if not string.endswith(suffix):
        raise AssertionError(
            f"Expected '{string}' to end with '{suffix}'"
            + (f": {message}" if message else "")
        )


def assert_contains(string: str, substring: str, message=None):
    """문자열에 부분 문자열이 포함되어 있는지 확인"""
    if substring not in string:
        raise AssertionError(
            f"Expected '{string}' to contain '{substring}'"
            + (f": {message}" if message else "")
        )


def assert_matches_regex(string: str, pattern: str, message=None):
    """문자열이 정규식 패턴과 일치하는지 확인"""
    import re

    if not re.search(pattern, string):
        raise AssertionError(
            f"Expected '{string}' to match pattern '{pattern}'"
            + (f": {message}" if message else "")
        )


# 커스텀 어설션 생성 헬퍼
def create_assertion(
    name: str,
    condition_func: Callable[[Any], bool],
    error_message_func: Callable[[Any], str],
):
    """커스텀 어설션 생성"""

    def assertion(value: Any, message=None):
        if not condition_func(value):
            error_msg = error_message_func(value)
            raise AssertionError(error_msg + (f": {message}" if message else ""))

    assertion.__name__ = name
    return assertion


# 컨텍스트 매니저 어설션들
class assert_raises_context:
    """예외 발생 확인을 위한 컨텍스트 매니저"""

    def __init__(self, expected_exception: Type[Exception], message=None):
        self.expected_exception = expected_exception
        self.message = message
        self.exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(
                f"Expected {self.expected_exception.__name__} to be raised"
                + (f": {self.message}" if self.message else "")
            )

        if not issubclass(exc_type, self.expected_exception):
            # 다른 예외가 발생한 경우, 원래 예외를 다시 raise
            return False

        self.exception = exc_val
        return True  # 예외를 처리했음을 나타냄


# 성능 어설션들
def assert_execution_time(max_time: float, message=None):
    """실행 시간 확인을 위한 데코레이터"""

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
            finally:
                execution_time = time.time() - start_time
                if execution_time > max_time:
                    raise AssertionError(
                        f"Execution took {execution_time:.3f}s, expected < {max_time}s"
                        + (f": {message}" if message else "")
                    )
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
            finally:
                execution_time = time.time() - start_time
                if execution_time > max_time:
                    raise AssertionError(
                        f"Execution took {execution_time:.3f}s, expected < {max_time}s"
                        + (f": {message}" if message else "")
                    )
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
