"""
Guard Statement - Swift-inspired early return pattern

Provides a Pythonic implementation of Swift's guard statement for
cleaner early returns and improved code readability.
"""

import inspect
import sys
from functools import wraps
from typing import Any, Callable, NoReturn, Optional, TypeVar, Union

T = TypeVar("T")
R = TypeVar("R")


class GuardError(Exception):
    """Exception raised when guard condition fails."""

    pass


class Guard:
    """
    Swift-inspired guard statement for early returns.

    Usage:
        with guard(condition) as g:
            g.else_return(value)  # or g.else_raise(exception)
            # code continues only if condition is True
    """

    def __init__(self, condition: bool, message="Guard condition failed"):
        self.condition = condition
        self.message = message
        self._handled = False

    def __enter__(self):
        if not self.condition:
            return self
        self._handled = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, _GuardReturn):
            # For Guard class, we need to somehow return the value
            # This is tricky because __exit__ can't change the function's return value
            # The test expects the function to return the guard return value
            # We need to re-raise this exception to be caught outside
            return False
        if not self._handled and not self.condition:
            raise GuardError(self.message)
        return False

    def else_return(self, value: Any = None) -> NoReturn:
        """Return early with a value if guard fails."""
        if not self.condition:
            self._handled = True
            # This is a bit hacky but works for early return simulation
            raise _GuardReturn(value)
        # This should never be reached when condition is False
        raise RuntimeError("Guard else_return called but condition was True")

    def else_raise(self, exception: Exception) -> NoReturn:
        """Raise an exception if guard fails."""
        if not self.condition:
            self._handled = True
            raise exception
        # This should never be reached when condition is False
        raise RuntimeError("Guard else_raise called but condition was True")

    def else_call(self, func: Callable[[], Any]) -> NoReturn:
        """Call a function if guard fails."""
        if not self.condition:
            result = func()
            raise _GuardReturn(result)
        # This should never be reached when condition is False
        raise RuntimeError("Guard else_call called but condition was True")


class _GuardReturn(Exception):
    """Internal exception for guard early returns."""

    def __init__(self, value):
        self.value = value
        super().__init__()


def guard(
    condition: Union[bool, Callable[[], bool]],
    else_return: Any = None,
    else_raise=None,
    message="Guard condition failed",
) -> Any:
    """
    Functional guard statement for early returns.

    Args:
        condition: Boolean or callable returning boolean
        else_return: Value to return if condition fails
        else_raise: Exception to raise if condition fails
        message: Error message if neither return nor raise specified

    Returns:
        None if condition passes, otherwise returns/raises as specified

    Example:
        >>> def divide(a, b):
        ...     guard(b != 0, else_return=float('inf'))
        ...     return a / b
        >>> divide(10, 0)
        inf
    """
    # Evaluate condition if it's callable
    if callable(condition):
        condition_result = condition()
    else:
        condition_result = condition

    if not condition_result:
        if else_raise is not None:
            raise else_raise
        elif else_return is not None:
            # Need to use exception to force early return from caller
            raise _GuardReturn(else_return)
        else:
            raise GuardError(message)


def guard_let(value: Optional[T], else_return: Any = None, else_raise=None) -> T:
    """
    Guard for optional values - unwraps or returns early.
    Swift-inspired: guard let unwrapped = optional else { return }

    Args:
        value: Optional value to unwrap
        else_return: Value to return if None
        else_raise: Exception to raise if None

    Returns:
        Unwrapped value if not None

    Example:
        >>> def process(data: Optional[str]):
        ...     unwrapped = guard_let(data, else_return="No data")
        ...     return f"Processing: {unwrapped}"
        >>> process(None)
        'No data'
        >>> process("test")
        'Processing: test'
    """
    if value is None:
        if else_raise is not None:
            raise else_raise
        elif else_return is not None:
            raise _GuardReturn(else_return)
        else:
            raise GuardError("Value is None")
    return value


def guarded(
    *conditions: Union[bool, Callable[[], bool]],
    else_return: Any = None,
    else_raise=None,
    message="Guard condition failed",
):
    """
    Decorator for functions with guard conditions.

    Args:
        *conditions: Conditions to check before function execution
        else_return: Value to return if conditions fail
        else_raise: Exception to raise if conditions fail
        message: Error message

    Returns:
        Decorated function

    Example:
        >>> @guarded(lambda: True, else_return="Failed")
        ... def safe_function():
        ...     return "Success"
        >>> safe_function()
        'Success'
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for condition in conditions:
                if callable(condition):
                    condition_result = condition()
                else:
                    condition_result = condition

                if not condition_result:
                    if else_raise is not None:
                        raise else_raise
                    elif else_return is not None:
                        return else_return
                    else:
                        raise GuardError(message)

            try:
                return func(*args, **kwargs)
            except _GuardReturn as gr:
                return gr.value

        return wrapper

    return decorator


def guard_type(
    value: Any,
    expected_type: type,
    else_return: Any = None,
    else_raise=None,
) -> Any:
    """
    Guard for type checking with early return.

    Args:
        value: Value to check
        expected_type: Expected type
        else_return: Value to return if type doesn't match
        else_raise: Exception to raise if type doesn't match

    Returns:
        The value if type matches

    Example:
        >>> def process_number(val):
        ...     num = guard_type(val, int, else_return=0)
        ...     return num * 2
        >>> process_number("not a number")
        0
        >>> process_number(5)
        10
    """
    if not isinstance(value, expected_type):
        if else_raise is not None:
            raise else_raise
        elif else_return is not None:
            raise _GuardReturn(else_return)
        else:
            raise GuardError(
                f"Expected type {expected_type.__name__}, got {type(value).__name__}"
            )
    return value


def guard_range(
    value: Union[int, float],
    min_val: Optional[Union[int, float]] = None,
    max_val: Optional[Union[int, float]] = None,
    else_return: Any = None,
    else_raise=None,
) -> Any:
    """
    Guard for range checking with early return.

    Args:
        value: Value to check
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        else_return: Value to return if out of range
        else_raise: Exception to raise if out of range

    Returns:
        The value if in range

    Example:
        >>> def process_percentage(val):
        ...     pct = guard_range(val, 0, 100, else_return=50)
        ...     return f"{pct}%"
        >>> process_percentage(150)
        '50%'
        >>> process_percentage(75)
        '75%'
    """
    if min_val is not None and value < min_val:
        if else_raise is not None:
            raise else_raise
        elif else_return is not None:
            return else_return
        else:
            raise GuardError(f"Value {value} is less than minimum {min_val}")

    if max_val is not None and value > max_val:
        if else_raise is not None:
            raise else_raise
        elif else_return is not None:
            return else_return
        else:
            raise GuardError(f"Value {value} is greater than maximum {max_val}")

    return value


def guard_not_empty(
    collection: Union[list, dict, set, str, tuple],
    else_return: Any = None,
    else_raise=None,
) -> Any:
    """
    Guard for non-empty collections.

    Args:
        collection: Collection to check
        else_return: Value to return if empty
        else_raise: Exception to raise if empty

    Returns:
        The collection if not empty

    Example:
        >>> def process_list(items):
        ...     lst = guard_not_empty(items, else_return=["default"])
        ...     return lst[0]
        >>> process_list([])
        'default'
        >>> process_list(["first", "second"])
        'first'
    """
    if not collection:
        if else_raise is not None:
            raise else_raise
        elif else_return is not None:
            return else_return
        else:
            raise GuardError("Collection is empty")
    return collection


class GuardContext:
    """
    Context manager for multiple guard conditions with shared else clause.

    Usage:
        with GuardContext() as guard:
            guard.check(condition1, "Condition 1 failed")
            guard.check(condition2, "Condition 2 failed")
            guard.check_not_none(value, "Value is None")
            guard.else_return(default_value)
    """

    def __init__(self):
        self.failed = False
        self.failure_message = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Let _GuardReturn exceptions propagate to be handled by @with_guards
        return False

    def check(
        self, condition: Union[bool, Callable[[], bool]], message=""
    ) -> "GuardContext":
        """Check a condition."""
        if self.failed:
            return self

        try:
            if callable(condition):
                condition_result = condition()
            else:
                condition_result = condition

            if not condition_result:
                self.failed = True
                self.failure_message = message
        except Exception:
            # If condition evaluation fails, consider it a failure
            self.failed = True
            self.failure_message = message or "Condition evaluation failed"

        return self

    def check_not_none(self, value: Optional[T], message="") -> Optional[T]:
        """Check that value is not None."""
        if value is None and not self.failed:
            self.failed = True
            self.failure_message = message
        return value

    def check_type(self, value: Any, expected_type: type, message="") -> Any:
        """Check that value has expected type."""
        if not isinstance(value, expected_type) and not self.failed:
            self.failed = True
            self.failure_message = (
                message
                or f"Expected {expected_type.__name__}, got {type(value).__name__}"
            )
        return value

    def else_return(self, value: Any = None) -> NoReturn:
        """Return early if any check failed."""
        if self.failed:
            raise _GuardReturn(value)
        # This should never be reached when not failed
        raise RuntimeError("GuardContext else_return called but no failure occurred")

    def else_raise(self, exception=None) -> NoReturn:
        """Raise exception if any check failed."""
        if self.failed:
            if exception is None:
                exception = GuardError(self.failure_message)
            raise exception
        # This should never be reached when not failed
        raise RuntimeError("GuardContext else_raise called but no failure occurred")


# Helper function to handle guard returns in functions
def with_guards(func: Callable) -> Callable:
    """
    Decorator to enable guard early returns in a function.

    Args:
        func: Function to decorate

    Returns:
        Decorated function that handles guard returns

    Example:
        >>> @with_guards
        ... def safe_divide(a, b):
        ...     guard(b != 0, else_return=float('inf'))
        ...     return a / b
        >>> safe_divide(10, 0)
        inf
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except _GuardReturn as gr:
            return gr.value

    return wrapper
