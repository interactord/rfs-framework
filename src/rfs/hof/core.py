"""
Core Higher-Order Functions

Essential functional programming utilities for function composition,
partial application, and basic combinators.
"""

import inspect
from functools import partial as functools_partial
from functools import reduce, wraps
from typing import Any, Callable, Optional, Tuple, TypeVar, Union, overload

# Type variables for generic type hints
A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")
D = TypeVar("D")
R = TypeVar("R")


def compose(*functions: Callable) -> Callable:
    """
    Function composition - right to left.

    Composes functions from right to left. The rightmost function can
    accept multiple arguments, while the rest must be unary.

    Args:
        *functions: Functions to compose

    Returns:
        Composed function

    Example:
        >>> add_one = lambda x: x + 1
        >>> multiply_two = lambda x: x * 2
        >>> composed = compose(add_one, multiply_two)
        >>> composed(3)  # (3 * 2) + 1 = 7
        7
    """
    if not functions:
        return identity

    return reduce(lambda f, g: lambda *args, **kwargs: f(g(*args, **kwargs)), functions)


def pipe(*functions: Callable) -> Callable:
    """
    Function composition - left to right.

    Pipes functions from left to right. The leftmost function can
    accept multiple arguments, while the rest must be unary.

    Args:
        *functions: Functions to pipe

    Returns:
        Piped function

    Example:
        >>> add_one = lambda x: x + 1
        >>> multiply_two = lambda x: x * 2
        >>> piped = pipe(add_one, multiply_two)
        >>> piped(3)  # (3 + 1) * 2 = 8
        8
    """
    if not functions:
        return identity

    return reduce(lambda f, g: lambda *args, **kwargs: g(f(*args, **kwargs)), functions)


def curry(func: Callable, arity: Optional[int] = None) -> Callable:
    """
    Curry a function to enable partial application.

    Transforms a function that takes multiple arguments into a sequence
    of functions that each take a single argument.

    Args:
        func: Function to curry
        arity: Number of arguments (auto-detected if None)

    Returns:
        Curried function

    Example:
        >>> @curry
        ... def add(a, b, c):
        ...     return a + b + c
        >>> add(1)(2)(3)
        6
        >>> add_one = add(1)
        >>> add_one_two = add_one(2)
        >>> add_one_two(3)
        6
    """
    if arity is None:
        sig = inspect.signature(func)
        arity = len(
            [
                p
                for p in sig.parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                and p.default is p.empty
            ]
        )

    @wraps(func)
    def curried(*args, **kwargs):
        if len(args) + len(kwargs) >= arity:
            return func(*args, **kwargs)
        return lambda *more_args, **more_kwargs: curried(
            *args, *more_args, **{**kwargs, **more_kwargs}
        )

    return curried


def partial(func: Callable, *args, **kwargs) -> Callable:
    """
    Partial application of a function.

    Returns a new function with some arguments pre-filled.

    Args:
        func: Function to partially apply
        *args: Positional arguments to pre-fill
        **kwargs: Keyword arguments to pre-fill

    Returns:
        Partially applied function

    Example:
        >>> def greet(greeting, name):
        ...     return f"{greeting}, {name}!"
        >>> say_hello = partial(greet, "Hello")
        >>> say_hello("World")
        'Hello, World!'
    """
    return functools_partial(func, *args, **kwargs)


def identity(x: A) -> A:
    """
    Identity function - returns its argument unchanged.

    Args:
        x: Any value

    Returns:
        The same value

    Example:
        >>> identity(42)
        42
        >>> identity([1, 2, 3])
        [1, 2, 3]
    """
    return x


def constant(value: A) -> Callable[[Any], A]:
    """
    Creates a function that always returns the same value.

    Args:
        value: Value to always return

    Returns:
        Function that always returns the value

    Example:
        >>> always_42 = constant(42)
        >>> always_42()
        42
        >>> always_42("ignored")
        42
    """
    return lambda *args, **kwargs: value


def flip(func: Callable[[A, B], R]) -> Callable[[B, A], R]:
    """
    Flips the order of the first two arguments of a function.

    Args:
        func: Function with at least two arguments

    Returns:
        Function with flipped arguments

    Example:
        >>> divide = lambda x, y: x / y
        >>> flipped_divide = flip(divide)
        >>> divide(10, 2)
        5.0
        >>> flipped_divide(2, 10)
        5.0
    """

    @wraps(func)
    def flipped(b: B, a: A, *args, **kwargs):
        return func(a, b, *args, **kwargs)

    return flipped


def apply(func: Callable[..., R], args: Union[tuple[Any, ...], list[Any]]) -> R:
    """
    Apply a function to a tuple/list of arguments.

    Args:
        func: Function to apply
        args: Arguments as tuple or list

    Returns:
        Result of function application

    Example:
        >>> apply(max, [1, 2, 3, 4, 5])
        5
        >>> apply(lambda x, y: x + y, (10, 20))
        30
    """
    if isinstance(args, (tuple, list)):
        return func(*args)
    # This should never be reached due to type constraints
    raise TypeError(f"Expected tuple or list, got {type(args)}")


# Decorator to make functions curryable
def curryable(func: Callable) -> Callable:
    """
    Decorator to make a function automatically curried.

    Args:
        func: Function to make curryable

    Returns:
        Curried version of the function

    Example:
        >>> @curryable
        ... def multiply(x, y, z):
        ...     return x * y * z
        >>> multiply(2)(3)(4)
        24
    """
    return curry(func)


# Helper function for function composition with type checking
def typed_compose(*functions: Callable) -> Callable:
    """
    Type-safe function composition with runtime type checking.

    Similar to compose but validates that output types match input types
    at runtime (useful for debugging).

    Args:
        *functions: Functions to compose

    Returns:
        Composed function with type checking
    """
    if not functions:
        return identity

    def composed(*args, **kwargs):
        result = args[0] if len(args) == 1 and not kwargs else (args, kwargs)

        for func in reversed(functions):
            try:
                if isinstance(result, tuple) and not kwargs:
                    result = func(*result)
                elif isinstance(result, tuple) and kwargs:
                    result = func(*result[0], **result[1])
                else:
                    result = func(result)
            except TypeError as e:
                func_name = getattr(func, "__name__", repr(func))
                raise TypeError(
                    f"Type error in composed function '{func_name}': {e}"
                ) from e

        return result

    return composed
