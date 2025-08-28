"""
Railway Oriented Programming을 위한 Result 타입

Success/Failure를 명시적으로 처리하는 함수형 에러 처리 패턴
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from functools import singledispatch
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    TypeVar,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
V = TypeVar("V")
F = TypeVar("F")


class Result(ABC, Generic[T, E]):
    """Result 추상 클래스 - Success 또는 Failure"""

    @abstractmethod
    def is_success(self) -> bool:
        """성공 여부 확인"""
        pass

    @abstractmethod
    def is_failure(self) -> bool:
        """실패 여부 확인"""
        pass

    @abstractmethod
    def unwrap(self) -> T:
        """값 추출 (실패시 예외)"""
        pass

    @abstractmethod
    def unwrap_or(self, default: T) -> T:
        """값 추출 (실패시 기본값)"""
        pass

    @abstractmethod
    def map(self, func: Callable[[T], U]) -> "Result[U, E]":
        """값 변환"""
        pass

    @abstractmethod
    def bind(self, func: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        """결과 연결 (flatMap)"""
        pass

    @abstractmethod
    def map_error(self, func: Callable[[E], U]) -> "Result[T, U]":
        """에러 변환"""
        pass


class Success(Result[T, E]):
    """성공 결과"""

    def __init__(self, value: T):
        self.value = value

    def is_success(self) -> bool:
        return True

    def is_failure(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value

    def get(self) -> T:
        """값 추출 (unwrap의 별칭)"""
        return self.value

    def get_error(self) -> None:
        """에러 값 추출 - Success는 None 반환"""
        return None

    def map(self, func: Callable[[T], U]) -> 'Result[U, E]':
        try:
            return Success(func(self.value))
        except Exception as e:
            return Failure(e)  # type: ignore[arg-type]

    def bind(self, func: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        try:
            return func(self.value)
        except Exception as e:
            return Failure(e)  # type: ignore[arg-type]

    def map_error(self, func: Callable[[E], U]) -> 'Result[T, U]':
        return Success(self.value)

    def flat_map(self, func: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        """flat_map alias for bind"""
        return self.bind(func)

    def or_else(self, alternative: Callable[[], 'Result[T, E]']) -> 'Result[T, E]':
        """Return self on Success"""
        return self

    def filter(self, predicate: Callable[[T], bool], error: E) -> 'Result[T, E]':
        """Filter success value with predicate"""
        try:
            if predicate(self.value):
                return self
            else:
                return Failure(error)
        except Exception as e:
            return Failure(e)  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"Success({self.value})"

    def __eq__(self, other: Any) -> bool:
        # 함수형 패턴: isinstance 대신 type 비교
        return type(other).__name__ == "Success" and self.value == other.value


class Failure(Result[T, E]):
    """실패 결과"""

    def __init__(self, error: E):
        self.error = error

    def is_success(self) -> bool:
        return False

    def is_failure(self) -> bool:
        return True

    def unwrap(self) -> T:
        # 함수형 패턴: isinstance 대신 type 비교
        if isinstance(self.error, Exception):
            raise self.error
        raise ValueError(f"Failure unwrap: {self.error}")

    def unwrap_error(self) -> E:
        """에러 값 추출"""
        return self.error

    def unwrap_err(self) -> E:
        """에러 값 추출 (unwrap_error의 별칭)"""
        return self.error

    def get_error(self) -> E:
        """에러 값 추출 (unwrap_error의 별칭)"""
        return self.error

    def unwrap_or(self, default: T) -> T:
        return default

    def get(self) -> None:
        """값 추출 - Failure는 None 반환"""
        return None

    def map(self, func: Callable[[T], U]) -> 'Result[U, E]':
        return Failure(self.error)

    def bind(self, func: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        return Failure(self.error)

    def map_error(self, func: Callable[[E], U]) -> 'Result[T, U]':
        try:
            return Failure(func(self.error))
        except Exception as e:
            return Failure(e)  # type: ignore[arg-type]

    def flat_map(self, func: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        """flat_map alias for bind"""
        return self.bind(func)

    def or_else(self, alternative: Callable[[], 'Result[T, E]']) -> 'Result[T, E]':
        """Return alternative on Failure"""
        try:
            return alternative()
        except Exception as e:
            return Failure(e)  # type: ignore[arg-type]

    def filter(self, predicate: Callable[[T], bool], error: E) -> 'Result[T, E]':
        """Filter returns self (Failure) unchanged"""
        return self

    def __repr__(self) -> str:
        return f"Failure({self.error})"

    def __eq__(self, other: Any) -> bool:
        # 함수형 패턴: isinstance 대신 type 비교
        return type(other).__name__ == "Failure" and self.error == other.error


# Monad 패턴 구현 (고급 함수형 프로그래밍)
class ResultM(Result[T, E]):
    """Monad 인터페이스를 구현한 Result - Haskell 스타일"""

    @classmethod
    def pure(cls, value: T) -> "Result[T, Any]":
        """Monad의 return/pure - 값을 Result 컨텍스트로 리프트"""
        return Success(value)

    @classmethod
    def wrap(cls, result: Result[T, E]) -> "ResultM[T, E]":
        """기존 Result를 ResultM으로 변환"""
        if result.is_success():
            return cls.pure(result.unwrap())
        return Failure(result.unwrap_error())

    def kleisli_compose(
        self, f: Callable[[T], "Result[U, E]"], g: Callable[[U], "Result[V, E]"]
    ) -> Callable[[T], "Result[V, E]"]:
        """Kleisli 화살표 합성 (>=>) - f >=> g"""
        return lambda x: f(x).bind(g)

    @classmethod
    def lift_a2(
        cls, func: Callable[[T, U], V], ra: "Result[T, E]", rb: "Result[U, E]"
    ) -> "Result[V, E]":
        """Applicative의 liftA2 - 2개의 Result에 함수 적용"""
        return ra.bind(lambda a: rb.map(lambda b: func(a, b)))

    @classmethod
    def ap(
        cls, rf: "Result[Callable[[T], U], E]", ra: "Result[T, E]"
    ) -> "Result[U, E]":
        """Applicative의 <*> (ap) - Result 안의 함수를 Result 안의 값에 적용"""
        return rf.bind(lambda f: ra.map(f))

    @classmethod
    def traverse_a(
        cls, func: Callable[[T], "Result[U, E]"], items: List[T]
    ) -> "Result[List[U], E]":
        """Applicative traverse - 더 효율적인 버전"""
        if not items:
            return cls.pure([])

        # Applicative 스타일: 순차적이지만 효율적
        results = [func(item) for item in items]
        return sequence_m(results)

    @classmethod
    def fold_m(
        cls, func: Callable[[U, T], "Result[U, E]"], init: U, items: List[T]
    ) -> "Result[U, E]":
        """Monadic fold - 누적 연산 with early termination"""
        acc = cls.pure(init)
        for item in items:
            acc = acc.bind(lambda a: func(a, item))
            if acc.is_failure():
                break  # Early termination
        return acc


# 편의 함수들
def success(value: T) -> "Result[T, Any]":
    """Success 생성"""
    return Success(value)


def failure(error: E) -> "Result[Any, E]":
    """Failure 생성"""
    return Failure(error)


def try_except(func: Callable[[], T]) -> Result[T, Exception]:
    """함수 실행을 Result로 래핑"""
    try:
        return Success(func())
    except Exception as e:
        return Failure(e)


async def async_try_except(
    func: Callable[[], T] | Callable[[], Awaitable[T]],
) -> "Result[T, Exception]":
    """비동기 함수 실행을 Result로 래핑"""
    try:
        if hasattr(func, "__call__"):
            result = func()
            if hasattr(result, "__await__"):
                result = await result
            return Success(result)
        return Success(await func)
    except Exception as e:
        return Failure(e)


def pipe_results(
    *funcs: Callable[[Any], Result[Any, Any]]
) -> Callable[[Any], Result[Any, Any]]:
    """Result를 반환하는 함수들을 파이프라인으로 연결"""

    def pipeline(value: Any) -> Result[Any, Any]:
        result = success(value)
        for func in funcs:
            if result.is_failure():
                break
            result = result.bind(func)
        return result

    return pipeline


async def async_pipe_results(
    *funcs: Callable[[Any], Result[Any, Any]]
) -> Callable[[Any], Result[Any, Any]]:
    """비동기 Result를 반환하는 함수들을 파이프라인으로 연결"""

    async def pipeline(value: Any) -> Result[Any, Any]:
        result = success(value)
        for func in funcs:
            if result.is_failure():
                break
            if hasattr(func, "__call__"):
                next_result = func(result.unwrap())
                if hasattr(next_result, "__await__"):
                    next_result = await next_result
                result = next_result
        return result

    return pipeline


async def async_pipe_chain(
    *operations: Callable[[T], Result[U, E]] | Callable[[T], Awaitable[Result[U, E]]]
) -> Callable[[T], Awaitable[Result[U, E]]]:
    """비동기 Result 체이닝 파이프라인 - 에러 컨텍스트 보존"""

    async def chain_pipeline(initial_value: T) -> Result[U, E]:
        """
        파이프라인 실행기 - 단계별 실행 및 에러 추적

        Args:
            initial_value: 초기 입력 값

        Returns:
            Result[U, E]: 최종 실행 결과 또는 첫 번째 실패 결과
        """
        current_result: Result[Any, Any] = Success(initial_value)
        operation_index: int = 0

        for operation in operations:
            if current_result.is_failure():
                # 이전 단계에서 실패한 경우 체이닝 중단
                break

            try:
                # 현재 성공 값을 다음 연산에 전달
                current_value = current_result.unwrap()
                next_result = operation(current_value)

                # 비동기 연산인지 확인하고 await 처리
                if hasattr(next_result, "__await__"):
                    next_result = await next_result

                current_result = next_result
                operation_index += 1

            except Exception as e:
                # 연산 중 예외 발생시 컨텍스트 정보 포함하여 Failure 반환
                error_message = f"Pipeline step {operation_index} failed: {str(e)}"
                return Failure(error_message)

        return current_result

    return chain_pipeline


def with_context(operation_name: str, context: Dict[str, Any] = None) -> Callable:
    """
    연산에 컨텍스트 정보를 추가하는 데코레이터

    Args:
        operation_name: 연산 이름
        context: 추가 컨텍스트 정보

    Returns:
        Callable: 컨텍스트가 추가된 연산 함수
    """

    def decorator(func: Callable[[T], Result[U, E]]) -> Callable[[T], Result[U, E]]:
        def wrapper(value: T) -> Result[U, E]:
            try:
                result = func(value)
                if result.is_failure():
                    # 실패시 컨텍스트 정보 추가
                    enhanced_error = {
                        "operation": operation_name,
                        "original_error": result.unwrap_error(),
                        "context": context or {},
                        "input_value": str(value)[:100],  # 입력 값의 일부만 포함
                    }
                    return Failure(enhanced_error)
                return result
            except Exception as e:
                # 예외 발생시 컨텍스트 정보 포함
                enhanced_error = {
                    "operation": operation_name,
                    "exception": str(e),
                    "exception_type": type(e).__name__,
                    "context": context or {},
                    "input_value": str(value)[:100],
                }
                return Failure(enhanced_error)

        return wrapper

    return decorator


def is_success(result: "Result[Any, Any]") -> bool:
    """성공 여부 확인"""
    return result.is_success()


def is_failure(result: "Result[Any, Any]") -> bool:
    """실패 여부 확인"""
    return result.is_failure()


def from_optional(value: Optional[T], error: E | None = None) -> "Result[T, E]":
    """Optional에서 Result로 변환"""
    match value:
        case None:
            return Failure(error or ValueError("None value"))
        case _:
            return Success(value)


def sequence(results: List["Result[T, E]"]) -> "Result[List[T], E]":
    """Result 리스트를 리스트 Result로 변환 - 함수형 패턴 적용"""
    values: list[T] = []
    for result in results:
        match result:
            case Success() as s:
                # 함수형 패턴: append 대신 리스트 연결
                values = values + [s.value]
            case Failure() as f:
                return f
    return Success(values)


async def sequence_async(results: List["Result[T, E]"]) -> "Result[List[T], E]":
    """비동기 Result 리스트를 리스트 Result로 변환 - 함수형 패턴 적용"""
    values: list[T] = []
    for result in results:
        match result:
            case Success() as s:
                # 함수형 패턴: append 대신 리스트 연결
                values = values + [s.value]
            case Failure() as f:
                return f
    return Success(values)


def traverse(items: List[T], func: Callable[[T], Result[U, E]]) -> Result[List[U], E]:
    """리스트의 각 아이템에 함수를 적용하고 Result 리스트로 변환"""
    results = [func(item) for item in items]
    return sequence(results)


async def traverse_async(
    items: List[T], func: Callable[[T], Result[U, E]]
) -> Result[List[U], E]:
    """비동기 traverse - 함수형 패턴 적용"""
    # 함수형 패턴: List comprehension으로 tasks 생성
    tasks = [
        (
            func(item)
            if asyncio.iscoroutinefunction(func)
            else asyncio.create_task(asyncio.coroutine(lambda i=item: func(i))())
        )
        for item in items
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 예외를 Failure로 변환 - 함수형 패턴 적용
    processed_results = []
    for result in results:
        # 함수형 패턴: isinstance 대신 type 비교 및 hasattr 사용
        # 함수형 패턴: append 대신 리스트 연결
        if hasattr(result, "__class__") and issubclass(result.__class__, Exception):
            processed_results = processed_results + [failure(result)]
        elif hasattr(result, "is_success") and hasattr(result, "is_failure"):
            processed_results = processed_results + [result]
        else:
            processed_results = processed_results + [success(result)]

    return await sequence_async(processed_results)


# 고차 함수들
def lift(func: Callable[[T], U]) -> Callable[["Result[T, E]"], "Result[U, E]"]:
    """일반 함수를 Result 컨텍스트로 리프트"""
    return lambda result: result.map(func)


def lift2(
    func: Callable[[T, U], V],
) -> Callable[["Result[T, E]", "Result[U, E]"], "Result[V, E]"]:
    """2개 인자 함수를 Result 컨텍스트로 리프트"""

    def lifted(result1: "Result[T, E]", result2: "Result[U, E]") -> "Result[V, E]":
        match (result1, result2):
            case (Success() as s1, Success() as s2):
                return Success(func(s1.value, s2.value))
            case (Failure() as f, _):
                return f
            case (_, Failure() as f):
                return f
            case _:
                return result2

    return lifted


# 데코레이터들
def result_decorator(func: Callable[..., T]) -> Callable[..., "Result[T, Exception]"]:
    """함수를 Result를 반환하도록 래핑"""

    def wrapper(*args: Any, **kwargs: Any) -> "Result[T, Exception]":
        try:
            return Success(func(*args, **kwargs))
        except Exception as e:
            return Failure(e)

    return wrapper


def async_result_decorator(
    func: Callable[..., T | Awaitable[T]],
) -> Callable[..., Awaitable["Result[T, Exception]"]]:
    """비동기 함수를 Result를 반환하도록 래핑"""

    async def wrapper(*args: Any, **kwargs: Any) -> "Result[T, Exception]":
        try:
            result = func(*args, **kwargs)
            if hasattr(result, "__await__"):
                result = await result
            return Success(result)
        except Exception as e:
            return Failure(e)

    return wrapper


# 함수형 조합자들
def combine(*results: "Result[Any, E]") -> "Result[tuple[Any, ...], E]":
    """여러 Result를 하나의 Result로 결합 - 함수형 패턴 적용"""
    # 함수형 패턴: 리스트 연결 사용 (early return 유지)
    values = []
    for result in results:
        match result:
            case Success() as s:
                values = values + [s.value]  # 함수형 패턴: 리스트 연결
            case Failure() as f:
                return result
    return Success(tuple(values))


def first_success(*results: "Result[T, E]") -> "Result[T, List[E]]":
    """첫 번째 성공한 Result 반환 - 함수형 패턴 적용"""
    # Early return을 유지하면서 함수형 스타일 적용
    for result in results:
        if result.is_success():
            return result

    # 함수형 패턴: list comprehension으로 에러 수집
    errors = [r.error for r in results if r.is_failure()]
    return Failure(errors)


def partition(results: List["Result[T, E]"]) -> tuple[List[T], List[E]]:
    """Result 리스트를 성공과 실패로 분할 - 함수형 패턴 적용"""
    # 함수형 패턴: filter와 list comprehension 사용
    successes = [r.value for r in results if r.is_success()]
    failures = [r.error for r in results if r.is_failure()]

    return successes, failures


# 고급 함수형 조합자 (Higher-Order Functions)
def take_until_failure(
    func: Callable[[List[T], T], List[T]], results: List["Result[T, E]"]
) -> "Result[List[T], E]":
    """첫 Failure까지만 처리하는 fold - Haskell 스타일"""
    from functools import reduce

    def folder(
        result: "Result[T, E]", acc: "Result[List[T], E]"
    ) -> "Result[List[T], E]":
        # Early termination: 이미 실패한 경우 그대로 반환
        if acc.is_failure():
            return acc

        match result:
            case Success() as s:
                # acc가 Success인 경우만 여기 도달
                return Success(func(acc.value, value))
            case Failure() as f:
                return result

    return reduce(folder, results, Success([]))


def sequence_m(results: List["Result[T, E]"]) -> "Result[List[T], E]":
    """Monadic bind를 이용한 sequence - early termination 자동 지원"""
    from functools import reduce

    def bind_append(
        acc: "Result[List[T], E]", result: "Result[T, E]"
    ) -> "Result[List[T], E]":
        # Monadic bind: acc가 Failure면 자동으로 전파
        return acc.bind(lambda xs: result.map(lambda x: xs + [x]))

    return reduce(bind_append, results, Success([]))


def traverse_m(
    func: Callable[[T], "Result[U, E]"], items: List[T]
) -> "Result[List[U], E]":
    """Monadic traverse - Haskell 스타일"""
    if not items:
        return Success([])

    head, *tail = items
    # 재귀적 구조로 early termination 지원
    return func(head).bind(lambda h: traverse_m(func, tail).map(lambda t: [h] + t))


# 호환성 함수들 (기존 Cosmos V2 API)
def get_value(result: "Result[T, Any]", default: T | None = None) -> T | None:
    """값 추출 (실패시 기본값) - 기존 V2 API 유지"""
    match result:
        case Success() as s:
            return s.value
        case Failure() as f:
            return default


def get_error(result: "Result[Any, E]") -> E | None:
    """에러 추출 - 기존 V2 API 유지"""
    match result:
        case Failure() as f:
            return f.error
        case Success() as s:
            return None


@singledispatch
def check_is_exception(obj: Any) -> bool:
    """예외 타입 확인 - 기존 V2 API 유지"""
    return False


@check_is_exception.register(Exception)
def _(obj: Exception) -> bool:
    """Exception 타입 확인"""
    return True


@singledispatch
def check_is_result_type(obj: Any) -> bool:
    """Result 타입 확인 - 기존 V2 API 유지"""
    return False


@check_is_result_type.register(Success)
def _(obj: Success) -> bool:
    """Success 타입 확인"""
    return True


@check_is_result_type.register(Failure)
def _(obj: Failure) -> bool:
    """Failure 타입 확인"""
    return True


# === RFS Framework 새로운 기능들 ===


class ResultAsync(Generic[T, E]):
    """
    비동기 전용 Result 타입 (RFS Framework)

    특징:
    - 모든 연산이 비동기
    - 자동 에러 핸들링
    - 체이닝 최적화
    """

    def __init__(self, result: Awaitable["Result[T, E]"]):
        self._result_awaitable = result
        self._cached_result: Optional["Result[T, E]"] = None

    async def _get_result(self) -> "Result[T, E]":
        """결과를 캐시하여 반환"""
        if self._cached_result is None:
            self._cached_result = await self._result_awaitable
        return self._cached_result

    async def is_success(self) -> bool:
        """비동기 성공 여부 확인"""
        result = await self._get_result()
        return result.is_success()

    async def is_failure(self) -> bool:
        """비동기 실패 여부 확인"""
        result = await self._get_result()
        return result.is_failure()

    async def unwrap(self) -> T:
        """비동기 값 추출"""
        result = await self._get_result()
        return result.unwrap()

    async def unwrap_or(self, default: T) -> T:
        """비동기 값 추출 (기본값 포함)"""
        result = await self._get_result()
        return result.unwrap_or(default)

    def map(
        self, func: Callable[[T], U] | Callable[[T], Awaitable[U]]
    ) -> "ResultAsync[U, E]":
        """비동기 값 변환"""

        async def mapped() -> "Result[U, E]":
            result = await self._get_result()
            match result:
                case Success() as s:
                    try:
                        mapped_value = func(s.value)
                        if hasattr(mapped_value, "__await__"):
                            mapped_value = await mapped_value
                        return Success(mapped_value)
                    except Exception as e:
                        return Failure(e)
                case Failure() as f:
                    return Failure(f.error)

        return ResultAsync(mapped())

    def bind(
        self, func: Callable[[T], "ResultAsync[U, E]"] | Callable[[T], "Result[U, E]"]
    ) -> "ResultAsync[U, E]":
        """비동기 결과 연결"""

        async def bound() -> "Result[U, E]":
            result = await self._get_result()
            match result:
                case Success() as s:
                    try:
                        next_result = func(s.value)
                        # 함수형 패턴: isinstance 대신 type 비교
                        if type(next_result).__name__ == "ResultAsync":
                            return await next_result._get_result()
                        elif hasattr(next_result, "__await__"):
                            return await next_result
                        else:
                            return next_result
                    except Exception as e:
                        return Failure(e)
                case Failure() as f:
                    return Failure(f.error)

        return ResultAsync(bound())

    async def to_result(self) -> "Result[T, E]":
        """동기 Result로 변환"""
        return await self._get_result()


def async_success(value: T) -> "ResultAsync[T, Any]":
    """비동기 Success 생성"""

    async def create() -> "Result[T, Any]":
        return Success(value)

    return ResultAsync(create())


def async_failure(error: E) -> "ResultAsync[Any, E]":
    """비동기 Failure 생성"""

    async def create() -> "Result[Any, E]":
        return Failure(error)

    return ResultAsync(create())


def from_awaitable(awaitable: Awaitable[T]) -> "ResultAsync[T, Exception]":
    """Awaitable을 ResultAsync로 변환"""

    async def convert() -> "Result[T, Exception]":
        try:
            result = await awaitable
            return Success(result)
        except Exception as e:
            return Failure(e)

    return ResultAsync(convert())


async def sequence_async_v4(
    results: List["ResultAsync[T, E]"],
) -> "ResultAsync[List[T], E]":
    """비동기 시퀀스 (성능 최적화)"""

    async def sequence() -> "Result[List[T], E]":
        values = []

        # 병렬 처리를 위한 모든 결과 수집
        result_awaitables = [r._result_awaitable for r in results]
        resolved_results = await asyncio.gather(
            *result_awaitables, return_exceptions=False
        )

        for result in resolved_results:
            match result:
                case Success() as s:
                    values.append(s.value)
                case Failure() as f:
                    return result

        return Success(values)

    return ResultAsync(sequence())


# === 함수형 프로그래밍 모나드 (RFS Framework) ===


class Either(Generic[T, E]):
    """
    Either 모나드 - Result의 함수형 대안

    특징:
    - Left: 에러 값 (Failure와 유사)
    - Right: 성공 값 (Success와 유사)
    - Railway Oriented Programming 지원
    """

    def __init__(self, is_right: bool, value: T | E):
        self._is_right = is_right
        self._value = value

    @classmethod
    def left(cls, error: E) -> "Either[T, E]":
        """Left (에러) 생성"""
        return cls(False, error)

    @classmethod
    def right(cls, value: T) -> "Either[T, E]":
        """Right (성공) 생성"""
        return cls(True, value)

    def is_left(self) -> bool:
        """Left (에러) 여부"""
        return not self._is_right

    def is_right(self) -> bool:
        """Right (성공) 여부"""
        return self._is_right

    def fold(self, left_func: Callable[[E], U], right_func: Callable[[T], U]) -> U:
        """Either를 단일 값으로 변환"""
        match self._is_right:
            case True:
                return right_func(self._value)
            case False:
                return left_func(self._value)

    def map(self, func: Callable[[T], U]) -> "Either[U, E]":
        """Right 값에만 함수 적용"""
        match self._is_right:
            case True:
                try:
                    return Either.right(func(self._value))
                except Exception as e:
                    return Either.left(e)
            case False:
                return Either.left(self._value)

    def flat_map(self, func: Callable[[T], "Either[U, E]"]) -> "Either[U, E]":
        """모나딕 연결"""
        match self._is_right:
            case True:
                try:
                    return func(self._value)
                except Exception as e:
                    return Either.left(e)
            case False:
                return Either.left(self._value)

    def map_left(self, func: Callable[[E], F]) -> "Either[T, F]":
        """Left 값에만 함수 적용"""
        match self._is_right:
            case True:
                return Either.right(self._value)
            case False:
                try:
                    return Either.left(func(self._value))
                except Exception as e:
                    return Either.left(e)

    def swap(self) -> "Either[E, T]":
        """Left ↔ Right 교환"""
        return Either(not self._is_right, self._value)

    def to_result(self) -> "Result[T, E]":
        """Result 타입으로 변환"""
        match self._is_right:
            case True:
                return Success(self._value)
            case False:
                return Failure(self._value)

    def __repr__(self) -> str:
        side = "Right" if self._is_right else "Left"
        return f"Either.{side}({self._value})"


class Maybe(Generic[T]):
    """
    Maybe 모나드 - Option/Optional의 함수형 대안

    특징:
    - Some: 값이 있는 경우
    - None_: 값이 없는 경우 (Python None과 구분)
    - Null-safe 연산 지원
    """

    def __init__(self, value: T | None):
        self._value = value

    @classmethod
    def some(cls, value: T) -> "Maybe[T]":
        """Some (값 있음) 생성"""
        if value is None:
            raise ValueError("Some cannot contain None")
        return cls(value)

    @classmethod
    def none(cls) -> "Maybe[T]":
        """None_ (값 없음) 생성"""
        return cls(None)

    @classmethod
    def of(cls, value: T | None) -> "Maybe[T]":
        """값으로부터 Maybe 생성"""
        return cls.some(value) if value is not None else cls.none()

    def is_some(self) -> bool:
        """값 존재 여부"""
        return self._value is not None

    def is_none(self) -> bool:
        """값 부재 여부"""
        return self._value is None

    def get(self) -> T:
        """값 추출 (None일 경우 예외)"""
        if self._value is None:
            raise ValueError("Cannot get value from None")
        return self._value

    def get_or_else(self, default: T) -> T:
        """값 추출 (None일 경우 기본값)"""
        return self._value if self._value is not None else default

    def map(self, func: Callable[[T], U]) -> "Maybe[U]":
        """값에 함수 적용"""
        match self._value:
            case None:
                return Maybe.none()
            case value:
                try:
                    return Maybe.some(func(value))
                except Exception:
                    return Maybe.none()

    def flat_map(self, func: Callable[[T], "Maybe[U]"]) -> "Maybe[U]":
        """모나딕 연결"""
        match self._value:
            case None:
                return Maybe.none()
            case value:
                try:
                    return func(value)
                except Exception:
                    return Maybe.none()

    def filter(self, predicate: Callable[[T], bool]) -> "Maybe[T]":
        """조건에 맞는 값만 유지"""
        match self._value:
            case None:
                return Maybe.none()
            case value if predicate(value):
                return self
            case _:
                return Maybe.none()

    def or_else(self, alternative: "Maybe[T]") -> "Maybe[T]":
        """값이 없을 경우 대안 제공"""
        return self if self.is_some() else alternative

    def to_result(self, error: E) -> "Result[T, E]":
        """Result로 변환"""
        match self._value:
            case None:
                return Failure(error)
            case value:
                return Success(value)

    def to_either(self, error: E) -> "Either[T, E]":
        """Either로 변환"""
        match self._value:
            case None:
                return Either.left(error)
            case value:
                return Either.right(value)

    def __repr__(self) -> str:
        return f"Maybe.Some({self._value})" if self.is_some() else "Maybe.None"


# Either/Maybe 편의 함수들
def left(error: E) -> "Either[Any, E]":
    """Either.Left 생성"""
    return Either.left(error)


def right(value: T) -> "Either[T, Any]":
    """Either.Right 생성"""
    return Either.right(value)


def some(value: T) -> "Maybe[T]":
    """Maybe.Some 생성"""
    return Maybe.some(value)


def none() -> "Maybe[Any]":
    """Maybe.None 생성"""
    return Maybe.none()


def maybe_of(value: T | None) -> "Maybe[T]":
    """값으로부터 Maybe 생성"""
    return Maybe.of(value)


# 고급 함수형 조합자들 (Day 3-4)
def sequence_either(eithers: List[Either[T, E]]) -> Either[List[T], E]:
    """Either 리스트를 리스트 Either로 변환"""
    values = []

    for either in eithers:
        match either:
            case Either() if either.is_left():
                return either.map_left(lambda e: e)  # 첫 번째 에러 반환
            case Either() if either.is_right():
                values.append(either._value)

    return Either.right(values)


def sequence_maybe(maybes: List[Maybe[T]]) -> Maybe[List[T]]:
    """Maybe 리스트를 리스트 Maybe로 변환"""
    values = []

    for maybe in maybes:
        match maybe.is_some():
            case True:
                values.append(maybe.get())
            case False:
                return Maybe.none()

    return Maybe.some(values)


def traverse_either(
    items: List[T], func: Callable[[T], Either[U, E]]
) -> Either[List[U], E]:
    """리스트 각 아이템에 Either 반환 함수 적용"""
    eithers = [func(item) for item in items]
    return sequence_either(eithers)


def traverse_maybe(items: List[T], func: Callable[[T], Maybe[U]]) -> Maybe[List[U]]:
    """리스트 각 아이템에 Maybe 반환 함수 적용"""
    maybes = [func(item) for item in items]
    return sequence_maybe(maybes)


# Result ↔ Either ↔ Maybe 상호 변환
def result_to_either(result: Result[T, E]) -> Either[T, E]:
    """Result를 Either로 변환"""
    match result:
        case Success() as s:
            return Either.right(s.value)
        case Failure() as f:
            return Either.left(f.error)


def either_to_result(either: Either[T, E]) -> Result[T, E]:
    """Either를 Result로 변환"""
    return either.to_result()


def maybe_to_result(maybe: Maybe[T], error: E) -> Result[T, E]:
    """Maybe를 Result로 변환"""
    return maybe.to_result(error)


def result_to_maybe(result: Result[T, E]) -> Maybe[T]:
    """Result를 Maybe로 변환"""
    match result:
        case Success() as s:
            return some(s.value)
        case Failure():
            return none()


# 헬퍼 함수들
def result_of(func: Callable[[], T]) -> Result[T, Exception]:
    """함수 실행 결과를 Result로 감싸기"""
    try:
        return Success(func())
    except Exception as e:
        return Failure(e)


def maybe_of_optional(value: Optional[T]) -> "Maybe[T]":
    """Optional 값을 Maybe로 변환"""
    return Maybe.some(value) if value is not None else Maybe.none()


def either_of(value: T, error: Optional[E] = None) -> "Either[T, E]":
    """값 또는 에러로 Either 생성"""
    return Either.left(error) if error is not None else Either.right(value)
