"""
RFS Framework 표준 라이브러리 및 Import 가이드

RFS Framework를 사용하는 프로젝트에서 자주 사용되는
표준 타입들과 유틸리티들을 통합된 방식으로 제공합니다.

이 모듈은 PR 문서에서 제안된 "표준화된 import 템플릿"을 구현합니다.
일관성 있는 개발 경험과 코드 품질 향상을 목표로 합니다.

주요 특징:
- 표준 타입 및 제네릭 타입들의 통합 import
- RFS Framework 핵심 패턴들의 편의 import
- HOF 라이브러리의 자주 사용되는 함수들
- 에러 처리 및 설정 관리 클래스들
- 개발자 생산성을 위한 편의 함수들

사용 예시:
    >>> from rfs.stdlib import *
    >>> # 모든 표준 타입과 RFS 유틸리티 사용 가능
    >>>
    >>> # 또는 선택적 import
    >>> from rfs.stdlib import (
    ...     # 타입들
    ...     Dict, List, Optional,
    ...     # RFS 핵심
    ...     Result, Success, Failure,
    ...     # HOF 함수들
    ...     pipe, compose, safe_map
    ... )
"""

# =============================================================================
# 표준 Python 타입들 (타입 힌팅용)
# =============================================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import partial, wraps
from pathlib import Path
from typing import (  # 기본 타입들; 함수 및 제네릭 타입들; 컬렉션 관련 타입들; 고급 타입들; 타입 체크 관련
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Coroutine,
    Dict,
    Final,
    Generic,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

# 설정 관리
from .core.config import RFSBaseSettings  # PR 문서에서 제안된 범용 설정 클래스
from .core.config import (
    Environment,
    RFSConfig,
)

# 에러 처리 (PR 문서에서 제안된 표준 에러 클래스들)
from .core.errors import (  # 편의 생성 함수들
    BusinessLogicError,
    ConfigurationError,
    IntegrationError,
    RFSError,
    ValidationError,
    business_error,
    config_error,
    integration_error,
    validation_error,
)

# Either/Maybe 모나드
# Result 패턴 (Railway Oriented Programming)
from .core.result import (  # Result 생성 헬퍼들; Result 변환 함수들
    Either,
    Failure,
    Maybe,
    Result,
    ResultAsync,
    Success,
    async_pipe_chain,
    either_of,
    maybe_of,
    pipe_results,
    result_of,
)

# 비동기 HOF
from .hof.async_hof import (
    async_filter,
    async_map,
    async_parallel,
    async_pipe,
    async_retry,
)

# 컬렉션 연산 (Swift-inspired)
from .hof.collections import safe_map  # PR 문서에서 제안된 함수
from .hof.collections import (
    chunk,
    compact_map,
    first,
    flat_map,
    group_by,
    last,
    partition,
)

# 조건부 실행
from .hof.combinators import (
    cond,
    tap,
    unless,
    when,
)

# 함수 합성
from .hof.core import (
    compose,
    constant,
    curry,
    identity,
    partial,
    pipe,
)

# 데코레이터
from .hof.decorators import (
    debounce,
    memoize,
    retry,
    throttle,
    timeout,
)

# 모나드 패턴
from .hof.monads import (
    Either,
    Maybe,
)
from .hof.monads import Result as HOFResult  # HOF 버전의 Result (alias로 구분)
from .hof.monads import (
    bind,
    lift,
)

# =============================================================================
# RFS Framework 핵심 패턴들
# =============================================================================





# =============================================================================
# HOF (Higher-Order Functions) 라이브러리 - 자주 사용되는 함수들
# =============================================================================







# =============================================================================
# 테스트 유틸리티
# =============================================================================

try:
    from .testing_utils import (
        RFSTestCase,
        async_test_decorator,
        performance_test,
    )
except ImportError:
    # 테스트 유틸리티가 없을 경우 None으로 설정
    RFSTestCase = None
    async_test_decorator = None
    performance_test = None

# =============================================================================
# 편의 함수들 및 상수들
# =============================================================================

# 자주 사용되는 상수들
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_BUFFER_SIZE = 100

# 타입 별칭들 (가독성 향상)
JSON = Dict[str, Any]
Headers = Dict[str, str]
QueryParams = Dict[str, Union[str, int, bool]]
ErrorMessage = str
StatusCode = int

# 편의 타입 변수들
T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")

# =============================================================================
# HOF 패턴을 위한 믹스인 클래스 (PR 문서에서 제안)
# =============================================================================


class HOFMixin:
    """HOF 패턴을 위한 표준 믹스인 클래스

    클래스에 함수형 프로그래밍 패턴을 쉽게 적용할 수 있도록
    도와주는 믹스인 클래스입니다.

    Example:
        >>> class MyService(HOFMixin):
        ...     def process(self, data):
        ...         return self.pipe(
        ...             self.validate,
        ...             self.transform,
        ...             self.save
        ...         )(data)
    """

    @staticmethod
    def pipe(*functions: Callable) -> Callable:
        """함수 파이프라인 생성"""
        return pipe(*functions)

    @staticmethod
    def compose(*functions: Callable) -> Callable:
        """함수 컴포지션 생성"""
        return compose(*functions)

    @staticmethod
    def safe_apply(func: Callable[[T], U], value: T) -> Result[U, str]:
        """안전한 함수 적용"""
        try:
            return Success(func(value))
        except Exception as e:
            return Failure(str(e))

    @staticmethod
    def when_condition(
        predicate: Callable[[T], bool], then_func: Callable[[T], T]
    ) -> Callable[[T], T]:
        """조건부 함수 적용"""
        return when(predicate, then_func)


# =============================================================================
# 개발자 편의 함수들
# =============================================================================


def rfs_info() -> Dict[str, Any]:
    """RFS Framework 정보 조회"""
    try:
        from . import __version__, get_framework_info

        return get_framework_info()
    except ImportError:
        return {
            "error": "RFS Framework information not available",
            "suggestion": "Make sure RFS Framework is properly installed",
        }


def validate_rfs_environment() -> Result[Dict[str, Any], str]:
    """RFS Framework 환경 검증"""
    try:
        # 핵심 모듈들 import 테스트
        from .core import config, result
        from .hof import core as hof_core

        # 기본 설정 로드 테스트
        config_instance = RFSConfig()

        return Success(
            {
                "status": "ok",
                "environment": config_instance.environment.value,
                "modules_available": [
                    "core.result",
                    "core.config",
                    "core.errors",
                    "hof.core",
                    "hof.collections",
                    "hof.monads",
                ],
                "version": rfs_info().get("version", "unknown"),
            }
        )
    except Exception as e:
        return Failure(f"RFS Framework 환경 검증 실패: {str(e)}")


def create_standard_result(
    operation: Callable[[], T], error_message: str = "Operation failed"
) -> Result[T, str]:
    """표준 Result 생성 헬퍼"""
    try:
        return Success(operation())
    except Exception as e:
        return Failure(f"{error_message}: {str(e)}")


# =============================================================================
# __all__ 정의 - 외부에서 import 가능한 모든 심볼들
# =============================================================================

__all__ = [
    # === 표준 Python 타입들 ===
    "Any",
    "Dict",
    "List",
    "Set",
    "Tuple",
    "Optional",
    "Union",
    "Callable",
    "Generic",
    "TypeVar",
    "Iterable",
    "Iterator",
    "Sequence",
    "Mapping",
    "Awaitable",
    "Coroutine",
    "Protocol",
    "ClassVar",
    "Final",
    "TYPE_CHECKING",
    "cast",
    "overload",
    "ABC",
    "abstractmethod",
    "dataclass",
    "field",
    "Enum",
    "Path",
    "wraps",
    "partial",
    # === RFS Framework 핵심 ===
    # Result 패턴
    "Result",
    "Success",
    "Failure",
    "ResultAsync",
    "result_of",
    "pipe_results",
    "async_pipe_chain",
    # Either/Maybe
    "Either",
    "Maybe",
    "either_of",
    "maybe_of",
    # 설정 관리
    "RFSConfig",
    "RFSBaseSettings",
    "Environment",
    # 에러 처리
    "RFSError",
    "ValidationError",
    "ConfigurationError",
    "IntegrationError",
    "BusinessLogicError",
    "validation_error",
    "config_error",
    "integration_error",
    "business_error",
    # === HOF 라이브러리 ===
    # 함수 합성
    "pipe",
    "compose",
    "curry",
    "identity",
    "constant",
    # 컬렉션 연산
    "first",
    "last",
    "compact_map",
    "safe_map",
    "flat_map",
    "partition",
    "group_by",
    "chunk",
    # 모나드 패턴
    "HOFResult",
    "bind",
    "lift",
    # 조건부 실행
    "when",
    "unless",
    "tap",
    "cond",
    # 데코레이터
    "memoize",
    "retry",
    "timeout",
    "throttle",
    "debounce",
    # 비동기 HOF
    "async_pipe",
    "async_map",
    "async_filter",
    "async_retry",
    "async_parallel",
    # === 테스트 유틸리티 ===
    "RFSTestCase",
    "async_test_decorator",
    "performance_test",
    # === 편의 기능들 ===
    # 상수들
    "DEFAULT_TIMEOUT",
    "DEFAULT_RETRY_COUNT",
    "DEFAULT_BUFFER_SIZE",
    # 타입 별칭들
    "JSON",
    "Headers",
    "QueryParams",
    "ErrorMessage",
    "StatusCode",
    # 타입 변수들
    "T",
    "U",
    "E",
    # 믹스인 클래스
    "HOFMixin",
    # 편의 함수들
    "rfs_info",
    "validate_rfs_environment",
    "create_standard_result",
]

# =============================================================================
# 모듈 초기화 및 검증
# =============================================================================

# 모듈 로드 시 기본 검증 수행
_validation_result = validate_rfs_environment()
if _validation_result.is_failure() and not globals().get("_RFS_STDLIB_QUIET", False):
    import warnings

    warnings.warn(
        f"RFS Framework stdlib 초기화 경고: {_validation_result.unwrap_error()}",
        ImportWarning,
    )

# 개발자를 위한 팁 메시지 (개발 환경에서만)
if globals().get("_RFS_STDLIB_TIPS", True):
    try:
        config = RFSConfig()
        if config.is_development():
            print("💡 RFS Framework stdlib이 로드되었습니다!")
            print(
                "   사용 예시: from rfs.stdlib import Result, Success, pipe, safe_map"
            )
            print("   전체 import: from rfs.stdlib import *")
            print("   환경 정보: rfs_info()")
    except:
        pass  # 조용히 무시
