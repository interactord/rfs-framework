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
    with_fallback,
    safe_call,
    retry_with_fallback,
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
    async_with_fallback,
    async_safe_call,
    async_retry_with_fallback,
    async_timeout_with_fallback,
)

# Readable HOF - 자연어에 가까운 선언적 패턴들 (선택적 import)
try:
    from .readable import (
        # 핵심 함수들
        apply_rules_to,
        validate_config,
        scan_for,
        extract_from,
        
        # 유틸리티 함수들
        quick_validate,
        quick_scan,
        quick_process,
        
        # 규칙 생성 함수들
        required,
        range_check,
        format_check,
        email_check,
        url_check,
        
        # 기본 클래스들
        ChainableResult,
        success,
        failure,
    )
    
    _READABLE_AVAILABLE = True
    
except ImportError:
    # readable 모듈이 없어도 기본 HOF는 동작하도록 함
    _READABLE_AVAILABLE = False

# 기본 __all__ 리스트
_base_all = [
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
    'with_fallback',
    'safe_call',
    'retry_with_fallback',
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
    'async_with_fallback',
    'async_safe_call',
    'async_retry_with_fallback',
    'async_timeout_with_fallback',
]

# Readable HOF가 사용 가능한 경우 추가
_readable_all = [
    # Readable HOF - 핵심 함수들
    'apply_rules_to',
    'validate_config', 
    'scan_for',
    'extract_from',
    
    # 유틸리티 함수들
    'quick_validate',
    'quick_scan',
    'quick_process',
    
    # 규칙 생성 함수들
    'required',
    'range_check',
    'format_check',
    'email_check',
    'url_check',
    
    # 기본 클래스들
    'ChainableResult',
    'success',
    'failure',
]

# 최종 __all__ 구성
if _READABLE_AVAILABLE:
    __all__ = _base_all + _readable_all
else:
    __all__ = _base_all

__version__ = '1.0.0'