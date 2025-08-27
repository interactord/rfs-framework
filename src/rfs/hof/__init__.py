"""
RFS Higher-Order Functions (HOF) Library

A comprehensive collection of functional programming utilities for Python,
providing composable, reusable, and type-safe higher-order functions.

Modules:
    - core: Essential HOF patterns (compose, pipe, curry, partial)
    - monads: Monadic patterns (Maybe, Either, Result)
    - combinators: Function combinators (identity, constant, flip)
    - decorators: Function decorators (memoize, throttle, debounce, retry)
    - collections: Collection operations (map, filter, reduce, fold)
    - async_hof: Async HOF patterns (async_compose, async_pipe)
"""

from .async_hof import (
    async_compose,
    async_filter,
    async_map,
    async_parallel,
    async_pipe,
    async_reduce,
    async_retry,
    async_sequential,
    async_timeout,
)
from .collections import (
    chunk,
    drop,
    drop_while,
    filter_indexed,
    flat_map,
    flatten,
    fold,
    fold_left,
    fold_right,
    group_by,
    map_indexed,
    partition,
    reduce_indexed,
    safe_map,
    scan,
    take,
    take_while,
    zip_with,
)
from .combinators import (
    always,
    complement,
    cond,
    if_else,
    tap,
    unless,
    when,
)
from .core import (
    apply,
    compose,
    constant,
    curry,
    flip,
    identity,
    partial,
    pipe,
)
from .decorators import (
    circuit_breaker,
    debounce,
    memoize,
    rate_limit,
    retry,
    throttle,
    timeout,
)
from .monads import (
    Either,
    Maybe,
    Result,
    bind,
    lift,
    sequence,
    traverse,
)

__all__ = [
    # Core
    "compose",
    "pipe",
    "curry",
    "partial",
    "identity",
    "constant",
    "flip",
    "apply",
    # Monads
    "Maybe",
    "Either",
    "Result",
    "bind",
    "lift",
    "sequence",
    "traverse",
    # Combinators
    "tap",
    "when",
    "unless",
    "if_else",
    "cond",
    "always",
    "complement",
    # Decorators
    "memoize",
    "throttle",
    "debounce",
    "retry",
    "timeout",
    "rate_limit",
    "circuit_breaker",
    # Collections
    "map_indexed",
    "filter_indexed",
    "reduce_indexed",
    "fold",
    "fold_left",
    "fold_right",
    "scan",
    "partition",
    "group_by",
    "chunk",
    "flatten",
    "flat_map",
    "safe_map",
    "zip_with",
    "take",
    "drop",
    "take_while",
    "drop_while",
    # Async
    "async_compose",
    "async_pipe",
    "async_map",
    "async_filter",
    "async_reduce",
    "async_retry",
    "async_timeout",
    "async_parallel",
    "async_sequential",
]

__version__ = "1.0.0"
