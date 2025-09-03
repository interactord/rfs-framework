"""
Function Combinators - Advanced function composition patterns

Provides combinators for conditional execution, function modification,
and control flow in a functional style.
"""

from typing import Any, Callable, List, Optional, TypeVar, Union, Tuple
from functools import wraps

T = TypeVar('T')
U = TypeVar('U')
R = TypeVar('R')


def tap(side_effect: Callable[[T], Any]) -> Callable[[T], T]:
    """
    Performs a side effect and returns the original value.
    Useful for logging or debugging in a pipeline.
    
    Args:
        side_effect: Function to execute for side effects
        
    Returns:
        Function that executes side effect and returns input
        
    Example:
        >>> from rfs.hof.core import pipe
        >>> pipeline = pipe(
        ...     lambda x: x * 2,
        ...     tap(print),  # Prints 10 but passes value through
        ...     lambda x: x + 1
        ... )
        >>> result = pipeline(5)  # Prints: 10
        >>> result
        11
    """
    def tapped(value: T) -> T:
        side_effect(value)
        return value
    return tapped


def when(
    predicate: Callable[[T], bool],
    transform: Callable[[T], T]
) -> Callable[[T], T]:
    """
    Conditionally applies a transformation.
    
    Args:
        predicate: Condition to check
        transform: Function to apply if condition is true
        
    Returns:
        Function that conditionally transforms input
        
    Example:
        >>> double_if_even = when(lambda x: x % 2 == 0, lambda x: x * 2)
        >>> double_if_even(4)
        8
        >>> double_if_even(3)
        3
    """
    def conditional(value: T) -> T:
        return transform(value) if predicate(value) else value
    return conditional


def unless(
    predicate: Callable[[T], bool],
    transform: Callable[[T], T]
) -> Callable[[T], T]:
    """
    Applies transformation unless condition is true.
    
    Args:
        predicate: Condition to check
        transform: Function to apply if condition is false
        
    Returns:
        Function that conditionally transforms input
        
    Example:
        >>> add_one_unless_zero = unless(lambda x: x == 0, lambda x: x + 1)
        >>> add_one_unless_zero(5)
        6
        >>> add_one_unless_zero(0)
        0
    """
    def conditional(value: T) -> T:
        return value if predicate(value) else transform(value)
    return conditional


def if_else(
    predicate: Callable[[T], bool],
    if_true: Callable[[T], R],
    if_false: Callable[[T], R]
) -> Callable[[T], R]:
    """
    Branching combinator - applies different functions based on condition.
    
    Args:
        predicate: Condition to check
        if_true: Function to apply if condition is true
        if_false: Function to apply if condition is false
        
    Returns:
        Function that branches based on condition
        
    Example:
        >>> sign = if_else(
        ...     lambda x: x >= 0,
        ...     lambda x: "positive",
        ...     lambda x: "negative"
        ... )
        >>> sign(5)
        'positive'
        >>> sign(-3)
        'negative'
    """
    def branched(value: T) -> R:
        return if_true(value) if predicate(value) else if_false(value)
    return branched


def cond(*conditions: Tuple[Callable[[T], bool], Callable[[T], R]]) -> Callable[[T], Optional[R]]:
    """
    Multiple condition branching (like switch/case).
    
    Args:
        *conditions: Pairs of (predicate, transform) functions
        
    Returns:
        Function that applies first matching transform
        
    Example:
        >>> grade = cond(
        ...     (lambda x: x >= 90, lambda x: 'A'),
        ...     (lambda x: x >= 80, lambda x: 'B'),
        ...     (lambda x: x >= 70, lambda x: 'C'),
        ...     (lambda x: x >= 60, lambda x: 'D'),
        ...     (lambda x: True, lambda x: 'F')  # default case
        ... )
        >>> grade(85)
        'B'
        >>> grade(45)
        'F'
    """
    def conditional(value: T) -> Optional[R]:
        for predicate, transform in conditions:
            if predicate(value):
                return transform(value)
        return None
    return conditional


def always(value: T) -> Callable[..., T]:
    """
    Creates a function that always returns the same value.
    
    Args:
        value: Value to always return
        
    Returns:
        Function that ignores input and returns value
        
    Example:
        >>> always_true = always(True)
        >>> always_true()
        True
        >>> always_true(1, 2, 3, x=4)
        True
    """
    def constant(*args, **kwargs) -> T:
        return value
    return constant


def complement(predicate: Callable[..., bool]) -> Callable[..., bool]:
    """
    Negates a predicate function.
    
    Args:
        predicate: Function returning boolean
        
    Returns:
        Negated predicate function
        
    Example:
        >>> is_even = lambda x: x % 2 == 0
        >>> is_odd = complement(is_even)
        >>> is_odd(3)
        True
        >>> is_odd(4)
        False
    """
    @wraps(predicate)
    def negated(*args, **kwargs) -> bool:
        return not predicate(*args, **kwargs)
    return negated


def both(
    pred1: Callable[[T], bool],
    pred2: Callable[[T], bool]
) -> Callable[[T], bool]:
    """
    Combines two predicates with AND logic.
    
    Args:
        pred1: First predicate
        pred2: Second predicate
        
    Returns:
        Combined predicate (AND)
        
    Example:
        >>> is_positive = lambda x: x > 0
        >>> is_even = lambda x: x % 2 == 0
        >>> is_positive_even = both(is_positive, is_even)
        >>> is_positive_even(4)
        True
        >>> is_positive_even(-2)
        False
    """
    def combined(value: T) -> bool:
        return pred1(value) and pred2(value)
    return combined


def either(
    pred1: Callable[[T], bool],
    pred2: Callable[[T], bool]
) -> Callable[[T], bool]:
    """
    Combines two predicates with OR logic.
    
    Args:
        pred1: First predicate
        pred2: Second predicate
        
    Returns:
        Combined predicate (OR)
        
    Example:
        >>> is_zero = lambda x: x == 0
        >>> is_negative = lambda x: x < 0
        >>> is_non_positive = either(is_zero, is_negative)
        >>> is_non_positive(0)
        True
        >>> is_non_positive(-5)
        True
        >>> is_non_positive(3)
        False
    """
    def combined(value: T) -> bool:
        return pred1(value) or pred2(value)
    return combined


def all_pass(predicates: List[Callable[[T], bool]]) -> Callable[[T], bool]:
    """
    Combines multiple predicates with AND logic.
    
    Args:
        predicates: List of predicates
        
    Returns:
        Combined predicate (all must pass)
        
    Example:
        >>> checks = all_pass([
        ...     lambda x: x > 0,
        ...     lambda x: x < 100,
        ...     lambda x: x % 2 == 0
        ... ])
        >>> checks(50)
        True
        >>> checks(101)
        False
    """
    def combined(value: T) -> bool:
        return all(pred(value) for pred in predicates)
    return combined


def any_pass(predicates: List[Callable[[T], bool]]) -> Callable[[T], bool]:
    """
    Combines multiple predicates with OR logic.
    
    Args:
        predicates: List of predicates
        
    Returns:
        Combined predicate (any must pass)
        
    Example:
        >>> checks = any_pass([
        ...     lambda x: x < 0,
        ...     lambda x: x > 100,
        ...     lambda x: x == 50
        ... ])
        >>> checks(50)
        True
        >>> checks(25)
        False
    """
    def combined(value: T) -> bool:
        return any(pred(value) for pred in predicates)
    return combined


def converge(
    converter: Callable[..., R],
    *branches: Callable[[T], Any]
) -> Callable[[T], R]:
    """
    Applies multiple functions to the same input and combines results.
    
    Args:
        converter: Function to combine branch results
        *branches: Functions to apply to input
        
    Returns:
        Function that converges branch results
        
    Example:
        >>> average = converge(
        ...     lambda total, count: total / count,
        ...     sum,
        ...     len
        ... )
        >>> average([1, 2, 3, 4, 5])
        3.0
    """
    def converged(value: T) -> R:
        results = [branch(value) for branch in branches]
        return converter(*results)
    return converged


def juxt(*functions: Callable[[T], Any]) -> Callable[[T], List[Any]]:
    """
    Applies multiple functions to the same input and returns all results.
    
    Args:
        *functions: Functions to apply
        
    Returns:
        Function that returns list of all results
        
    Example:
        >>> process = juxt(
        ...     lambda x: x * 2,
        ...     lambda x: x + 10,
        ...     lambda x: x ** 2
        ... )
        >>> process(5)
        [10, 15, 25]
    """
    def juxtaposed(value: T) -> List[Any]:
        return [func(value) for func in functions]
    return juxtaposed


def fork(
    join: Callable[[U, U], R],
    f: Callable[[T], U],
    g: Callable[[T], U]
) -> Callable[[T], R]:
    """
    Applies two functions to the same input and joins the results.
    
    Args:
        join: Function to combine results
        f: First function
        g: Second function
        
    Returns:
        Function that forks and joins
        
    Example:
        >>> mean = fork(
        ...     lambda x, y: x / y,
        ...     sum,
        ...     len
        ... )
        >>> mean([2, 4, 6, 8])
        5.0
    """
    def forked(value: T) -> R:
        return join(f(value), g(value))
    return forked


def on(
    binary_op: Callable[[U, U], R],
    unary_op: Callable[[T], U]
) -> Callable[[T, T], R]:
    """
    Applies unary function to both arguments before binary operation.
    
    Args:
        binary_op: Binary operation
        unary_op: Unary operation to apply first
        
    Returns:
        Combined function
        
    Example:
        >>> import operator
        >>> compare_lengths = on(operator.eq, len)
        >>> compare_lengths("hello", "world")
        True
        >>> compare_lengths("hi", "world")
        False
    """
    def combined(x: T, y: T) -> R:
        return binary_op(unary_op(x), unary_op(y))
    return combined


def until(
    predicate: Callable[[T], bool],
    transform: Callable[[T], T]
) -> Callable[[T], T]:
    """
    Repeatedly applies transformation until predicate is true.
    
    Args:
        predicate: Condition to stop
        transform: Transformation to apply
        
    Returns:
        Function that transforms until condition met
        
    Example:
        >>> increment_until_ten = until(lambda x: x >= 10, lambda x: x + 1)
        >>> increment_until_ten(7)
        10
    """
    def repeated(value: T) -> T:
        current = value
        while not predicate(current):
            current = transform(current)
        return current
    return repeated


def iterate(
    n: int,
    func: Callable[[T], T]
) -> Callable[[T], T]:
    """
    Applies a function n times.
    
    Args:
        n: Number of times to apply
        func: Function to iterate
        
    Returns:
        Function that applies n times
        
    Example:
        >>> double_three_times = iterate(3, lambda x: x * 2)
        >>> double_three_times(5)
        40  # 5 * 2 * 2 * 2
    """
    def iterated(value: T) -> T:
        result = value
        for _ in range(n):
            result = func(result)
        return result
    return iterated


def with_fallback(
    primary: Callable[..., T],
    fallback: Callable[[Exception], T]
) -> Callable[..., T]:
    """
    주 함수가 실패하면 폴백 함수를 실행하는 고차함수.
    
    서버 초기화나 중요한 연산에서 graceful degradation을 구현할 때 유용합니다.
    
    Args:
        primary: 먼저 실행할 주 함수
        fallback: 주 함수 실패 시 실행할 폴백 함수 (Exception을 인자로 받음)
        
    Returns:
        주 함수를 시도하고 실패 시 폴백을 실행하는 함수
        
    Example:
        >>> def load_config():
        ...     raise FileNotFoundError("Config not found")
        >>> def default_config(error):
        ...     print(f"Using default config due to: {error}")
        ...     return {"debug": True}
        >>> safe_load = with_fallback(load_config, default_config)
        >>> config = safe_load()
        Using default config due to: Config not found
        >>> config
        {'debug': True}
        
        # 파이프라인에서 사용
        >>> from rfs.hof.core import pipe
        >>> pipeline = pipe(
        ...     with_fallback(load_external_data, lambda e: []),
        ...     lambda data: len(data)
        ... )
    """
    @wraps(primary)
    def with_fallback_wrapper(*args, **kwargs) -> T:
        try:
            return primary(*args, **kwargs)
        except Exception as e:
            return fallback(e)
    return with_fallback_wrapper


def safe_call(
    func: Callable[..., T],
    default: T,
    exceptions: tuple = (Exception,)
) -> Callable[..., T]:
    """
    함수 호출을 안전하게 감싸서 예외 발생 시 기본값을 반환.
    
    Args:
        func: 호출할 함수
        default: 예외 발생 시 반환할 기본값
        exceptions: 처리할 예외 타입들 (기본: 모든 예외)
        
    Returns:
        안전하게 감싸진 함수
        
    Example:
        >>> safe_int = safe_call(int, 0, (ValueError, TypeError))
        >>> safe_int("123")
        123
        >>> safe_int("abc")
        0
        >>> safe_int(None)
        0
    """
    @wraps(func)
    def safe_wrapper(*args, **kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except exceptions:
            return default
    return safe_wrapper


def retry_with_fallback(
    primary: Callable[..., T],
    fallback: Callable[[Exception], T],
    max_attempts: int = 3,
    delay: float = 0.1
) -> Callable[..., T]:
    """
    재시도 로직과 폴백을 결합한 고차함수.
    
    Args:
        primary: 재시도할 주 함수
        fallback: 모든 재시도 실패 후 실행할 폴백 함수
        max_attempts: 최대 시도 횟수
        delay: 재시도 간 지연 시간 (초)
        
    Returns:
        재시도 로직과 폴백이 적용된 함수
        
    Example:
        >>> import time
        >>> attempt_count = 0
        >>> def flaky_service():
        ...     global attempt_count
        ...     attempt_count += 1
        ...     if attempt_count < 3:
        ...         raise ConnectionError("Service unavailable")
        ...     return "success"
        >>> def fallback_service(error):
        ...     return "fallback_result"
        >>> reliable_service = retry_with_fallback(flaky_service, fallback_service, 5)
        >>> result = reliable_service()
        >>> result
        'success'
    """
    import time
    
    @wraps(primary)
    def retry_wrapper(*args, **kwargs) -> T:
        last_exception = None
        for attempt in range(max_attempts):
            try:
                return primary(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_attempts - 1:  # 마지막 시도가 아니라면 지연
                    time.sleep(delay)
        
        # 모든 재시도 실패 시 폴백 실행
        return fallback(last_exception)
    
    return retry_wrapper