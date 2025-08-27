"""
Unit tests for HOF Guard module

Tests Swift-inspired guard statement for early returns.
"""

import pytest

from rfs.hof.guard import (
    Guard,
    GuardContext,
    GuardError,
    _GuardReturn,
    guard,
    guard_let,
    guard_not_empty,
    guard_range,
    guard_type,
    guarded,
    with_guards,
)


class TestBasicGuard:
    """Test basic guard functionality."""

    def test_guard_with_else_return(self):
        """Test guard with else_return."""

        @with_guards
        def divide(a, b):
            guard(b != 0, else_return=float("inf"))
            return a / b

        assert divide(10, 2) == 5.0
        assert divide(10, 0) == float("inf")

    def test_guard_with_else_raise(self):
        """Test guard with else_raise."""

        @with_guards
        def safe_sqrt(x):
            guard(x >= 0, else_raise=ValueError("Cannot take sqrt of negative"))
            return x**0.5

        assert safe_sqrt(4) == 2.0

        with pytest.raises(ValueError, match="Cannot take sqrt of negative"):
            safe_sqrt(-1)

    def test_guard_with_callable_condition(self):
        """Test guard with callable condition."""
        counter = [0]

        @with_guards
        def check_counter():
            guard(lambda: counter[0] > 0, else_return="Counter is zero")
            return f"Counter is {counter[0]}"

        assert check_counter() == "Counter is zero"

        counter[0] = 5
        assert check_counter() == "Counter is 5"


class TestGuardLet:
    """Test guard_let for optional unwrapping."""

    def test_guard_let_with_value(self):
        """Test guard_let with non-None value."""

        @with_guards
        def process(data):
            unwrapped = guard_let(data, else_return="No data")
            return f"Processing: {unwrapped}"

        assert process("test") == "Processing: test"
        assert process(None) == "No data"

    def test_guard_let_with_exception(self):
        """Test guard_let with exception."""

        @with_guards
        def strict_process(data):
            unwrapped = guard_let(data, else_raise=ValueError("Data required"))
            return f"Data: {unwrapped}"

        assert strict_process("value") == "Data: value"

        with pytest.raises(ValueError, match="Data required"):
            strict_process(None)


class TestGuardedDecorator:
    """Test guarded decorator."""

    def test_guarded_with_conditions(self):
        """Test guarded decorator with multiple conditions."""
        is_valid = [True]
        has_permission = [True]

        @guarded(
            lambda: is_valid[0], lambda: has_permission[0], else_return="Access denied"
        )
        def secure_operation():
            return "Operation successful"

        assert secure_operation() == "Operation successful"

        is_valid[0] = False
        assert secure_operation() == "Access denied"

        is_valid[0] = True
        has_permission[0] = False
        assert secure_operation() == "Access denied"

    def test_guarded_with_exception(self):
        """Test guarded decorator with exception."""

        @guarded(lambda: False, else_raise=PermissionError("Not allowed"))
        def restricted():
            return "Should not reach here"

        with pytest.raises(PermissionError, match="Not allowed"):
            restricted()


class TestGuardType:
    """Test guard_type for type checking."""

    def test_guard_type_success(self):
        """Test guard_type with correct type."""

        @with_guards
        def process_number(val):
            num = guard_type(val, int, else_return=0)
            return num * 2

        assert process_number(5) == 10
        assert process_number("not a number") == 0

    def test_guard_type_with_exception(self):
        """Test guard_type with exception."""

        @with_guards
        def strict_process(val):
            num = guard_type(val, int, else_raise=TypeError("Integer required"))
            return num + 10

        assert strict_process(5) == 15

        with pytest.raises(TypeError, match="Integer required"):
            strict_process("string")


class TestGuardRange:
    """Test guard_range for range checking."""

    def test_guard_range_in_bounds(self):
        """Test guard_range with value in bounds."""

        @with_guards
        def process_percentage(val):
            pct = guard_range(val, 0, 100, else_return=50)
            return f"{pct}%"

        assert process_percentage(75) == "75%"
        assert process_percentage(150) == "50%"
        assert process_percentage(-10) == "50%"

    def test_guard_range_with_none_bounds(self):
        """Test guard_range with None bounds."""

        @with_guards
        def process_positive(val):
            num = guard_range(val, min_val=0, max_val=None, else_return=0)
            return num

        assert process_positive(10) == 10
        assert process_positive(-5) == 0

        @with_guards
        def process_max(val):
            num = guard_range(val, min_val=None, max_val=100, else_return=100)
            return num

        assert process_max(50) == 50
        assert process_max(150) == 100


class TestGuardNotEmpty:
    """Test guard_not_empty for collection checking."""

    def test_guard_not_empty_list(self):
        """Test guard_not_empty with lists."""

        @with_guards
        def process_list(items):
            lst = guard_not_empty(items, else_return=["default"])
            return lst[0]

        assert process_list([1, 2, 3]) == 1
        assert process_list([]) == "default"

    def test_guard_not_empty_string(self):
        """Test guard_not_empty with strings."""

        @with_guards
        def process_string(text):
            s = guard_not_empty(text, else_return="empty")
            return f"Text: {s}"

        assert process_string("hello") == "Text: hello"
        assert process_string("") == "Text: empty"

    def test_guard_not_empty_dict(self):
        """Test guard_not_empty with dictionaries."""

        @with_guards
        def process_dict(data):
            d = guard_not_empty(data, else_return={"default": True})
            return list(d.keys())[0]

        assert process_dict({"key": "value"}) == "key"
        assert process_dict({}) == "default"


class TestGuardContext:
    """Test GuardContext for multiple checks."""

    def test_guard_context_all_pass(self):
        """Test GuardContext when all checks pass."""

        @with_guards
        def process(value, data):
            with GuardContext() as guard:
                guard.check(value > 0, "Value must be positive")
                guard.check_not_none(data, "Data is required")
                guard.else_return("Failed")

            return f"Success: {value}, {data}"

        assert process(5, "test") == "Success: 5, test"

    def test_guard_context_check_fails(self):
        """Test GuardContext when check fails."""

        @with_guards
        def process(value, data):
            with GuardContext() as guard:
                guard.check(value > 0, "Value must be positive")
                guard.check_not_none(data, "Data is required")
                guard.else_return("Failed")

            return f"Success: {value}, {data}"

        assert process(-1, "test") == "Failed"
        assert process(5, None) == "Failed"

    def test_guard_context_type_check(self):
        """Test GuardContext with type checking."""

        @with_guards
        def process(value):
            with GuardContext() as guard:
                guard.check_type(value, int, "Must be integer")
                guard.check(lambda: value > 0, "Must be positive")
                guard.else_return(0)

            return value * 2

        assert process(5) == 10
        assert process("string") == 0
        assert process(-5) == 0

    def test_guard_context_with_exception(self):
        """Test GuardContext with exception."""

        @with_guards
        def strict_process(value):
            with GuardContext() as guard:
                guard.check(value > 0, "Value must be positive")
                guard.else_raise(ValueError("Validation failed"))

            return value

        assert strict_process(5) == 5

        with pytest.raises(ValueError, match="Validation failed"):
            strict_process(-1)


class TestGuardClass:
    """Test Guard class context manager."""

    def test_guard_class_basic(self):
        """Test basic Guard class usage."""

        @with_guards
        def process(value):
            with Guard(value > 0, "Value must be positive") as g:
                if not g.condition:
                    g.else_return(-1)
            return value * 2

        assert process(5) == 10
        assert process(-1) == -1

    def test_guard_class_with_exception(self):
        """Test Guard class with exception."""

        @with_guards
        def process(value):
            with Guard(value > 0) as g:
                if not g.condition:
                    g.else_raise(ValueError("Invalid value"))
            return value

        assert process(5) == 5

        with pytest.raises(ValueError, match="Invalid value"):
            process(-1)
