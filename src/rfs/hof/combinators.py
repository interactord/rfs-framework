"""
Function Combinators - Advanced function composition patterns

Provides combinators for conditional execution, function modification,
and control flow in a functional style.
"""

from functools import wraps
from typing import Any, Callable, List, Optional, Tuple, TypeVar, Union

T = TypeVar("T")
U = TypeVar("U")
R = TypeVar("R")


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
    predicate: Callable[[T], bool], transform: Callable[[T], T]
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
    predicate: Callable[[T], bool], transform: Callable[[T], T]
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
    if_false: Callable[[T], R],
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


def cond(
    *conditions: Tuple[Callable[[T], bool], Callable[[T], R]]
) -> Callable[[T], Optional[R]]:
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


def both(pred1: Callable[[T], bool], pred2: Callable[[T], bool]) -> Callable[[T], bool]:
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
    pred1: Callable[[T], bool], pred2: Callable[[T], bool]
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
    converter: Callable[..., R], *branches: Callable[[T], Any]
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
    join: Callable[[U, U], R], f: Callable[[T], U], g: Callable[[T], U]
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
    binary_op: Callable[[U, U], R], unary_op: Callable[[T], U]
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
    predicate: Callable[[T], bool], transform: Callable[[T], T]
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


def iterate(n: int, func: Callable[[T], T]) -> Callable[[T], T]:
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
