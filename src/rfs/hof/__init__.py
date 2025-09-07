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
    - readable: 자연어에 가까운 선언적 HOF 패턴 (apply_rules_to, validate_config, scan_for)
"""

from .async_hof import (
    async_compose,
    async_filter,
    async_map,
    async_parallel,
    async_pipe,
    async_reduce,
    async_retry,
    async_retry_with_fallback,
    async_safe_call,
    async_sequential,
    async_timeout,
    async_timeout_with_fallback,
    async_with_fallback,
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
    retry_with_fallback,
    safe_call,
    tap,
    unless,
    when,
    with_fallback,
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

# Readable HOF - 자연어에 가까운 선언적 패턴들 (선택적 import)
try:
    from .readable import (  # 핵심 함수들; 유틸리티 함수들; 규칙 생성 함수들; 기본 클래스들
        ChainableResult,
        apply_rules_to,
        email_check,
        extract_from,
        failure,
        format_check,
        quick_process,
        quick_scan,
        quick_validate,
        range_check,
        required,
        scan_for,
        success,
        url_check,
        validate_config,
    )

    _READABLE_AVAILABLE = True

except ImportError:
    # readable 모듈이 없어도 기본 HOF는 동작하도록 함
    _READABLE_AVAILABLE = False

# 기본 __all__ 리스트
_base_all = [
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
    "with_fallback",
    "safe_call",
    "retry_with_fallback",
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
    "async_with_fallback",
    "async_safe_call",
    "async_retry_with_fallback",
    "async_timeout_with_fallback",
]

# Readable HOF가 사용 가능한 경우 추가
_readable_all = [
    # Readable HOF - 핵심 함수들
    "apply_rules_to",
    "validate_config",
    "scan_for",
    "extract_from",
    # 유틸리티 함수들
    "quick_validate",
    "quick_scan",
    "quick_process",
    # 규칙 생성 함수들
    "required",
    "range_check",
    "format_check",
    "email_check",
    "url_check",
    # 기본 클래스들
    "ChainableResult",
    "success",
    "failure",
]

# 최종 __all__ 구성
if _READABLE_AVAILABLE:
    __all__ = _base_all + _readable_all
else:
    __all__ = _base_all

__version__ = "1.0.0"
