"""
Transaction Decorators for RFS Framework

트랜잭션 데코레이터 - 선언적 트랜잭션 관리
"""

import asyncio
import inspect
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, List, Optional, Type, Union

from ..result import Failure, Result, Success
from .base import (
    IsolationLevel,
    PropagationLevel,
    TransactionError,
    TransactionOptions,
    TransactionRollback,
)
from .manager import get_transaction_manager


def Transactional(
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
    propagation: PropagationLevel = PropagationLevel.REQUIRED,
    timeout: Optional[Union[int, timedelta]] = None,
    read_only=False,
    rollback_on: Optional[List[Type[Exception]]] = None,
    no_rollback_on: Optional[List[Type[Exception]]] = None,
    retry=0,
    retry_delay: Union[int, timedelta] = 1,
):
    """
    트랜잭션 데코레이터

    Usage:
        @Transactional(isolation=IsolationLevel.SERIALIZABLE)
        def transfer_money(from_account: str, to_account: str, amount: float):
            # 트랜잭션 내에서 실행
            pass

        @Transactional(propagation=PropagationLevel.REQUIRES_NEW)
        async def async_operation():
            # 비동기 트랜잭션
            pass

    Args:
        isolation: 격리 수준
        propagation: 전파 수준
        timeout: 타임아웃 (초 또는 timedelta)
        read_only: 읽기 전용 여부
        rollback_on: 롤백 대상 예외
        no_rollback_on: 롤백 제외 예외
        retry: 재시도 횟수
        retry_delay: 재시도 지연 (초 또는 timedelta)
    """
    # 타임아웃 정규화
    if type(timeout).__name__ == "int":
        timeout = timedelta(seconds=timeout)

    # 재시도 지연 정규화
    if type(retry_delay).__name__ == "int":
        retry_delay = timedelta(seconds=retry_delay)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """동기 함수 래퍼"""
            manager = get_transaction_manager()
            options = TransactionOptions(
                isolation_level=isolation,
                propagation_level=propagation,
                timeout=timeout,
                read_only=read_only,
                rollback_on=rollback_on or [],
                no_rollback_on=no_rollback_on or [],
                retry_attempts=retry,
                retry_delay=retry_delay,
            )

            attempts = 0
            last_error = None

            while attempts <= retry:
                try:
                    with manager.transaction(options):
                        result = func(*args, **kwargs)

                        # Result 타입 처리
                        if type(result).__name__ == "Result":
                            if type(result).__name__ == "Failure":
                                # 실패 시 롤백
                                raise TransactionRollback(result.error)

                        return result

                except TransactionRollback:
                    # 명시적 롤백 요청
                    raise
                except Exception as e:
                    last_error = e

                    # 롤백 대상 예외 확인
                    should_rollback = True

                    if rollback_on:
                        should_rollback = any(
                            (type(e).__name__ == "exc_type") for exc_type in rollback_on
                        )

                    if no_rollback_on:
                        if any(
                            (type(e).__name__ == "exc_type")
                            for exc_type in no_rollback_on
                        ):
                            should_rollback = False

                    if should_rollback and attempts < retry:
                        # 재시도
                        attempts = attempts + 1
                        if retry_delay:
                            import time

                            time.sleep(retry_delay.total_seconds())
                        continue

                    raise

            # 모든 재시도 실패
            if last_error:
                raise last_error

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            """비동기 함수 래퍼"""
            manager = get_transaction_manager()
            options = TransactionOptions(
                isolation_level=isolation,
                propagation_level=propagation,
                timeout=timeout,
                read_only=read_only,
                rollback_on=rollback_on or [],
                no_rollback_on=no_rollback_on or [],
                retry_attempts=retry,
                retry_delay=retry_delay,
            )

            attempts = 0
            last_error = None

            while attempts <= retry:
                try:
                    async with manager.async_transaction(options):
                        result = await func(*args, **kwargs)

                        # Result 타입 처리
                        if type(result).__name__ == "Result":
                            if type(result).__name__ == "Failure":
                                # 실패 시 롤백
                                raise TransactionRollback(result.error)

                        return result

                except TransactionRollback:
                    # 명시적 롤백 요청
                    raise
                except Exception as e:
                    last_error = e

                    # 롤백 대상 예외 확인
                    should_rollback = True

                    if rollback_on:
                        should_rollback = any(
                            (type(e).__name__ == "exc_type") for exc_type in rollback_on
                        )

                    if no_rollback_on:
                        if any(
                            (type(e).__name__ == "exc_type")
                            for exc_type in no_rollback_on
                        ):
                            should_rollback = False

                    if should_rollback and attempts < retry:
                        # 재시도
                        attempts = attempts + 1
                        if retry_delay:
                            await asyncio.sleep(retry_delay.total_seconds())
                        continue

                    raise

            # 모든 재시도 실패
            if last_error:
                raise last_error

        # 함수 타입에 따라 적절한 래퍼 반환
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 별칭 (소문자)
transactional = Transactional


def ReadOnly(func: Callable) -> Callable:
    """
    읽기 전용 트랜잭션 데코레이터

    Usage:
        @ReadOnly
        def get_user(user_id: str):
            # 읽기 전용 트랜잭션
            pass
    """
    return Transactional(read_only=True)(func)


def RequiresNew(func: Callable) -> Callable:
    """
    새 트랜잭션 요구 데코레이터

    Usage:
        @RequiresNew
        def audit_log(action: str):
            # 항상 새 트랜잭션에서 실행
            pass
    """
    return Transactional(propagation=PropagationLevel.REQUIRES_NEW)(func)


def Propagation(level: PropagationLevel):
    """
    전파 수준 지정 데코레이터

    Usage:
        @Propagation(PropagationLevel.NESTED)
        def nested_operation():
            pass
    """

    def decorator(func: Callable) -> Callable:
        return Transactional(propagation=level)(func)

    return decorator


def Isolation(level: IsolationLevel):
    """
    격리 수준 지정 데코레이터

    Usage:
        @Isolation(IsolationLevel.SERIALIZABLE)
        def critical_operation():
            pass
    """

    def decorator(func: Callable) -> Callable:
        return Transactional(isolation=level)(func)

    return decorator


def Timeout(seconds: int):
    """
    타임아웃 지정 데코레이터

    Usage:
        @Timeout(30)
        def long_operation():
            pass
    """

    def decorator(func: Callable) -> Callable:
        return Transactional(timeout=timedelta(seconds=seconds))(func)

    return decorator


def Rollback(
    on: Optional[List[Type[Exception]]] = None,
    exclude: Optional[List[Type[Exception]]] = None,
):
    """
    롤백 조건 지정 데코레이터

    Usage:
        @Rollback(on=[ValueError, KeyError])
        def operation():
            pass

        @Rollback(exclude=[WarningException])
        def tolerant_operation():
            pass
    """

    def decorator(func: Callable) -> Callable:
        return Transactional(rollback_on=on, no_rollback_on=exclude)(func)

    return decorator


class TransactionalClass:
    """
    클래스 레벨 트랜잭션 지원

    Usage:
        @TransactionalClass(isolation=IsolationLevel.REPEATABLE_READ)
        class UserService:
            def create_user(self, name: str):
                # 자동으로 트랜잭션 적용
                pass
    """

    def __init__(
        self,
        isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
        propagation: PropagationLevel = PropagationLevel.REQUIRED,
        timeout: Optional[Union[int, timedelta]] = None,
        read_only=False,
        methods: Optional[List[str]] = None,
        exclude_methods: Optional[List[str]] = None,
    ):
        self.isolation = isolation
        self.propagation = propagation
        self.timeout = timeout
        self.read_only = read_only
        self.methods = methods
        self.exclude_methods = exclude_methods or []

    def __call__(self, cls):
        """클래스 데코레이터 적용"""
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            # 특수 메서드 제외
            if name.startswith("_"):
                continue

            # 제외 메서드 확인
            if name in self.exclude_methods:
                continue

            # 포함 메서드 확인
            if self.methods and name not in self.methods:
                continue

            # 트랜잭션 데코레이터 적용
            decorated = Transactional(
                isolation=self.isolation,
                propagation=self.propagation,
                timeout=self.timeout,
                read_only=self.read_only,
            )(method)

            setattr(cls, name, decorated)

        return cls


def with_savepoint(name: str):
    """
    세이브포인트 데코레이터

    Usage:
        @Transactional()
        def main_operation():
            nested_operation()

        @with_savepoint("before_risky")
        def nested_operation():
            # 세이브포인트 생성 후 실행
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_transaction_manager()

            # 세이브포인트 생성
            result = manager.savepoint(name)
            if type(result).__name__ == "Failure":
                raise TransactionError(f"Failed to create savepoint: {result.error}")

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 세이브포인트로 롤백
                rollback_result = manager.rollback_to_savepoint(name)
                if type(rollback_result).__name__ == "Failure":
                    raise TransactionError(
                        f"Failed to rollback to savepoint: {rollback_result.error}"
                    )
                raise

        return wrapper

    return decorator


def transactional_method(
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
    propagation: PropagationLevel = PropagationLevel.REQUIRED,
):
    """
    메서드용 트랜잭션 데코레이터

    클래스 메서드에 트랜잭션을 적용

    Usage:
        class UserRepository:
            @transactional_method()
            def save(self, user):
                pass
    """

    def decorator(method: Callable) -> Callable:
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            # self를 포함하여 원본 메서드 호출
            tx_func = Transactional(isolation=isolation, propagation=propagation)(
                lambda: method(self, *args, **kwargs)
            )
            return tx_func()

        return wrapper

    return decorator
