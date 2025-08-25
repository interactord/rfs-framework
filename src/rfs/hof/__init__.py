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

from .core import (
    compose,
    pipe,
    curry,
    partial,
    identity,
    constant,
    flip,
    apply,
)

from .monads import (
    Maybe,
    Either,
    Result,
    bind,
    lift,
    sequence,
    traverse,
)

from .combinators import (
    tap,
    when,
    unless,
    if_else,
    cond,
    always,
    complement,
)

from .decorators import (
    memoize,
    throttle,
    debounce,
    retry,
    timeout,
    rate_limit,
    circuit_breaker,
)

from .collections import (
    map_indexed,
    filter_indexed,
    reduce_indexed,
    fold,
    fold_left,
    fold_right,
    scan,
    partition,
    group_by,
    chunk,
    flatten,
    flat_map,
    zip_with,
    take,
    drop,
    take_while,
    drop_while,
)

from .async_hof import (
    async_compose,
    async_pipe,
    async_map,
    async_filter,
    async_reduce,
    async_retry,
    async_timeout,
    async_parallel,
    async_sequential,
)

__all__ = [
    # Core
    'compose',
    'pipe',
    'curry',
    'partial',
    'identity',
    'constant',
    'flip',
    'apply',
    # Monads
    'Maybe',
    'Either',
    'Result',
    'bind',
    'lift',
    'sequence',
    'traverse',
    # Combinators
    'tap',
    'when',
    'unless',
    'if_else',
    'cond',
    'always',
    'complement',
    # Decorators
    'memoize',
    'throttle',
    'debounce',
    'retry',
    'timeout',
    'rate_limit',
    'circuit_breaker',
    # Collections
    'map_indexed',
    'filter_indexed',
    'reduce_indexed',
    'fold',
    'fold_left',
    'fold_right',
    'scan',
    'partition',
    'group_by',
    'chunk',
    'flatten',
    'flat_map',
    'zip_with',
    'take',
    'drop',
    'take_while',
    'drop_while',
    # Async
    'async_compose',
    'async_pipe',
    'async_map',
    'async_filter',
    'async_reduce',
    'async_retry',
    'async_timeout',
    'async_parallel',
    'async_sequential',
]

__version__ = '1.0.0'