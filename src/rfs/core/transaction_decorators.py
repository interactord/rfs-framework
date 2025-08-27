"""
RFS v4.1 Transaction Decorators
어노테이션 기반 트랜잭션 관리 데코레이터

주요 데코레이터:
- @Transactional: 데이터베이스 트랜잭션
- @RedisTransaction: Redis 트랜잭션
- @DistributedTransaction: 분산 트랜잭션 (Saga)
- @TransactionalMethod: 메서드별 트랜잭션
"""

import asyncio
import functools
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .result import Failure, Result, Success
from .transactions import (
    IsolationLevel,
    TransactionContext,
    TransactionManager,
    get_transaction_manager,
)

logger = logging.getLogger(__name__)

# Temporary definitions until properly implemented
from enum import Enum


class TransactionType(Enum):
    DATABASE = "database"
    REDIS = "redis"
    DISTRIBUTED = "distributed"


@dataclass
class TransactionConfig:
    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    timeout = 30
    retry_count = 3
    retry_delay: float = 0.1


@dataclass
class RedisTransactionConfig:
    watch_keys: List[str] = field(default_factory=list)
    timeout = 30
    retry_count = 3


@dataclass
class DistributedTransactionConfig:
    saga_steps: List[str] = field(default_factory=list)
    timeout = 60
    compensation_enabled = True


def get_transaction_registry():
    return None


def execute_with_retry(func, config, transaction_type, *args, **kwargs):
    return func(*args, **kwargs)


def Transactional(
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
    timeout=30,
    retry_count=3,
    retry_delay: float = 1.0,
    rollback_for: List[Type[Exception]] = None,
    no_rollback_for: List[Type[Exception]] = None,
    readonly=False,
    propagation="REQUIRED",
) -> Callable:
    """
    데이터베이스 트랜잭션 데코레이터

    Args:
        isolation: 트랜잭션 격리 수준
        timeout: 타임아웃 (초)
        retry_count: 재시도 횟수
        retry_delay: 재시도 지연 시간 (초)
        rollback_for: 롤백을 유발하는 예외 타입들
        no_rollback_for: 롤백하지 않을 예외 타입들
        readonly: 읽기 전용 트랜잭션 여부
        propagation: 트랜잭션 전파 설정

    Example:
        @Transactional(isolation=IsolationLevel.REPEATABLE_READ, retry_count=5)
        async def update_user_profile(user_id: str, profile_data: dict) -> Result[User, str]:
            # 데이터베이스 업데이트 로직
            return Success(updated_user)
    """
    config = TransactionConfig(
        isolation_level=isolation,
        timeout_seconds=timeout,
        retry_count=retry_count,
        retry_delay_seconds=retry_delay,
        rollback_for=rollback_for or [Exception],
        no_rollback_for=no_rollback_for or [],
        readonly=readonly,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await _execute_transactional(
                func, config, TransactionType.DATABASE, *args, **kwargs
            )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return asyncio.run(
                _execute_transactional(
                    func, config, TransactionType.DATABASE, *args, **kwargs
                )
            )

        # 함수가 async인지 확인하여 적절한 wrapper 반환
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def RedisTransaction(
    ttl=None,
    key_pattern=None,
    watch_keys: List[str] = None,
    timeout=30,
    retry_count=3,
    pipeline=True,
) -> Callable:
    """
    Redis 트랜잭션 데코레이터

    Args:
        ttl: TTL 시간 (초)
        key_pattern: 키 패턴
        watch_keys: 감시할 키들
        timeout: 타임아웃 (초)
        retry_count: 재시도 횟수
        pipeline: 파이프라인 모드 사용 여부

    Example:
        @RedisTransaction(ttl=3600, key_pattern="user:{user_id}", watch_keys=["user:123"])
        async def cache_user_data(user_id: str, data: dict) -> Result[None, str]:
            # Redis 캐싱 로직
            return Success(None)
    """
    config = RedisTransactionConfig(
        ttl_seconds=ttl,
        key_pattern=key_pattern,
        watch_keys=watch_keys or [],
        timeout_seconds=timeout,
        retry_count=retry_count,
        pipeline_mode=pipeline,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await _execute_transactional(
                func, config, TransactionType.REDIS, *args, **kwargs
            )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return asyncio.run(
                _execute_transactional(
                    func, config, TransactionType.REDIS, *args, **kwargs
                )
            )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def DistributedTransaction(
    saga_id: str,
    timeout=300,
    retry_count=3,
    compensation_timeout=60,
    idempotent=True,
) -> Callable:
    """
    분산 트랜잭션 데코레이터 (Saga 패턴)

    Args:
        saga_id: Saga ID
        timeout: 타임아웃 (초)
        retry_count: 재시도 횟수
        compensation_timeout: 보상 트랜잭션 타임아웃 (초)
        idempotent: 멱등성 여부

    Example:
        @DistributedTransaction(saga_id="user_registration", timeout=600)
        async def register_user_workflow(user_data: dict) -> Result[User, str]:
            # 분산 사용자 등록 워크플로우
            return Success(registered_user)
    """
    config = DistributedTransactionConfig(
        saga_id=saga_id,
        timeout_seconds=timeout,
        retry_count=retry_count,
        compensation_timeout=compensation_timeout,
        idempotent=idempotent,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await _execute_transactional(
                func, config, TransactionType.DISTRIBUTED, *args, **kwargs
            )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return asyncio.run(
                _execute_transactional(
                    func, config, TransactionType.DISTRIBUTED, *args, **kwargs
                )
            )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


async def _execute_transactional(
    func: Callable,
    config: Union[
        TransactionConfig, RedisTransactionConfig, DistributedTransactionConfig
    ],
    transaction_type: TransactionType,
    *args,
    **kwargs,
) -> Any:
    """트랜잭션 실행 핵심 로직"""

    # 트랜잭션 컨텍스트 생성
    context = TransactionContext(transaction_type=transaction_type, config=config)

    # 트랜잭션 매니저 조회
    registry = get_transaction_registry()
    manager = registry.get_manager(transaction_type)

    if not manager:
        error_msg = f"No transaction manager registered for {transaction_type.value}"
        logger.error(error_msg)
        return Failure(error_msg)

    # 재시도를 포함한 트랜잭션 실행
    async def transaction_func():
        return await manager.execute_in_transaction(context, func, *args, **kwargs)

    result = await execute_with_retry(transaction_func, context)

    # 실행 결과 로깅
    if result.is_success():
        logger.info(f"Transaction {context.transaction_id} completed successfully")
    else:
        logger.error(f"Transaction {context.transaction_id} failed: {result.error}")

    return result


class TransactionalMethod:
    """
        메서드별 트랜잭션 설정을 위한 클래스 데코레이터

        이 클래스를 사용하면 클래스 전체에 기본 트랜잭션 설정을 적용하고
        개별 메서드에서 세부 설정을 오버라이드할 수 있습니다.

        Example:
            @TransactionalMethod(isolation=IsolationLevel.READ_COMMITTED)
            @dataclass
    class UserService:
        user_repository: Any            @Transactional(isolation=IsolationLevel.SERIALIZABLE)
                async def create_user(self, user_data: dict) -> Result[User, str]:
                    # 높은 격리 수준이 필요한 생성 로직
                    return await self.user_repository.save(user_data)

                # 기본 설정 사용
                async def get_user(self, user_id: str) -> Result[User, str]:
                    return await self.user_repository.find_by_id(user_id)
    """

    def __init__(
        self,
        isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
        timeout=30,
        retry_count=3,
        readonly=False,
    ):
        self.default_config = TransactionConfig(
            isolation_level=isolation,
            timeout_seconds=timeout,
            retry_count=retry_count,
            readonly=readonly,
        )

    def __call__(self, cls: type) -> type:
        """클래스 데코레이터 적용"""

        # 클래스의 모든 메서드 검사
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)

            # 메서드이고 @Transactional이 없는 경우 기본 설정 적용
            if (
                inspect.isfunction(attr) or inspect.ismethod(attr)
            ) and not attr_name.startswith("_"):
                if not hasattr(attr, "_rfs_transactional"):
                    # 기본 트랜잭션 데코레이터 적용
                    decorated_method = Transactional(
                        isolation=self.default_config.isolation_level,
                        timeout=self.default_config.timeout_seconds,
                        retry_count=self.default_config.retry_count,
                        readonly=self.default_config.readonly,
                    )(attr)

                    # 마커 추가
                    decorated_method._rfs_transactional = True
                    setattr(cls, attr_name, decorated_method)

        return cls


def transactional_context(
    transaction_type: TransactionType,
    config: Union[
        TransactionConfig, RedisTransactionConfig, DistributedTransactionConfig
    ],
):
    """
    컨텍스트 매니저를 통한 트랜잭션 관리

    Example:
        async with transactional_context(TransactionType.DATABASE, db_config) as tx:
            # 트랜잭션 내 작업
            result = await some_database_operation()
            if result.is_failure():
                raise Exception("Operation failed")
            return result
    """
    return TransactionalContextManager(transaction_type, config)


class TransactionalContextManager:
    """트랜잭션 컨텍스트 매니저"""

    def __init__(
        self,
        transaction_type: TransactionType,
        config: Union[
            TransactionConfig, RedisTransactionConfig, DistributedTransactionConfig
        ],
    ):
        self.transaction_type = transaction_type
        self.config = config
        self.context = None
        self.manager = None

    async def __aenter__(self):
        """컨텍스트 진입"""
        self.context = TransactionContext(
            transaction_type=self.transaction_type, config=self.config
        )

        registry = get_transaction_registry()
        self.manager = registry.get_manager(self.transaction_type)

        if not self.manager:
            raise RuntimeError(
                f"No transaction manager for {self.transaction_type.value}"
            )

        result = await self.manager.begin_transaction(self.context)
        if result.is_failure():
            raise RuntimeError(f"Failed to begin transaction: {result.error}")

        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료"""
        if exc_type is None:
            # 정상 완료 - 커밋
            result = await self.manager.commit_transaction(self.context)
            if result.is_failure():
                logger.error(f"Failed to commit transaction: {result.error}")
        else:
            # 예외 발생 - 롤백
            result = await self.manager.rollback_transaction(self.context, str(exc_val))
            if result.is_failure():
                logger.error(f"Failed to rollback transaction: {result.error}")


# 편의 함수들
def database_transaction(**kwargs):
    """데이터베이스 트랜잭션 편의 함수"""
    return Transactional(**kwargs)


def redis_transaction(**kwargs):
    """Redis 트랜잭션 편의 함수"""
    return RedisTransaction(**kwargs)


def saga_transaction(**kwargs):
    """Saga 트랜잭션 편의 함수"""
    return DistributedTransaction(**kwargs)


# 트랜잭션 상태 확인 유틸리티
class TransactionStatus:
    """트랜잭션 상태 추적 유틸리티"""

    _active_transactions = {}

    @classmethod
    def register_transaction(cls, context: TransactionContext):
        """트랜잭션 등록"""
        cls._active_transactions = {
            **cls._active_transactions,
            context.transaction_id: context,
        }

    @classmethod
    def unregister_transaction(cls, transaction_id: str):
        """트랜잭션 등록 해제"""
        _active_transactions = {
            k: v for k, v in _active_transactions.items() if k != "transaction_id, None"
        }

    @classmethod
    def get_active_transactions(cls) -> Dict[str, TransactionContext]:
        """활성 트랜잭션 조회"""
        return cls._active_transactions.copy()

    @classmethod
    def get_transaction_stats(cls) -> Dict[str, Any]:
        """트랜잭션 통계"""
        stats = {
            "active_count": len(cls._active_transactions),
            "by_type": {},
            "by_status": {},
        }

        for context in cls._active_transactions.values():
            # 타입별 통계
            type_name = context.transaction_type.value
            stats = {
                **stats,
                "by_type": {
                    **stats["by_type"],
                    type_name: stats["by_type"].get(type_name, 0) + 1,
                },
            }

            # 상태별 통계
            status_name = context.status.value
            stats = {
                **stats,
                "by_status": {
                    **stats["by_status"],
                    status_name: stats["by_status"].get(status_name, 0) + 1,
                },
            }

        return stats


# 편의 함수
def with_transaction(transaction_type: TransactionType = TransactionType.DATABASE):
    """트랜잭션과 함께 실행하는 데코레이터"""
    return Transactional(transaction_type=transaction_type)


# 예제 사용법
if __name__ == "__main__":

    # 데이터베이스 트랜잭션 예제
    @Transactional(isolation=IsolationLevel.REPEATABLE_READ, retry_count=5)
    async def update_user_balance(user_id: str, amount: float) -> Result[dict, str]:
        """사용자 잔액 업데이트"""
        print(f"Updating balance for user {user_id}: ${amount}")
        # 실제 데이터베이스 업데이트 로직
        return Success({"user_id": user_id, "new_balance": amount})

    # Redis 트랜잭션 예제
    @RedisTransaction(ttl=3600, key_pattern="user_session:{user_id}")
    async def cache_user_session(user_id: str, session_data: dict) -> Result[None, str]:
        """사용자 세션 캐싱"""
        print(f"Caching session for user {user_id}")
        # 실제 Redis 캐싱 로직
        return Success(None)

    # 분산 트랜잭션 예제
    @DistributedTransaction(saga_id="user_onboarding", timeout=600)
    async def onboard_new_user(user_data: dict) -> Result[dict, str]:
        """신규 사용자 온보딩 워크플로우"""
        print(f"Starting onboarding for {user_data.get('email')}")
        # 실제 분산 트랜잭션 로직
        return Success({"user_id": "123", "status": "onboarded"})

    # 컨텍스트 매니저 예제
    async def example_context_manager():
        """컨텍스트 매니저 사용 예제"""
        db_config = TransactionConfig(isolation_level=IsolationLevel.READ_COMMITTED)

        try:
            async with transactional_context(TransactionType.DATABASE, db_config):
                # 트랜잭션 내 작업
                result = await update_user_balance("user123", 1000.0)
                if result.is_failure():
                    raise Exception("Balance update failed")
                print("✅ Transaction completed successfully")
        except Exception as e:
            print(f"❌ Transaction failed: {e}")

    # 테스트 실행
    async def main():
        print("🧪 Testing Transaction Decorators...")

        # Mock 매니저들 등록 (실제 구현에서는 실제 매니저 사용)
        from .transactions import DatabaseTransactionManager

        class MockManager(DatabaseTransactionManager):
            async def execute_in_transaction(self, context, func, *args, **kwargs):
                print(
                    f"Executing {func.__name__} in transaction {context.transaction_id}"
                )
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, MockManager())
        registry.register_manager(TransactionType.REDIS, MockManager())
        registry.register_manager(TransactionType.DISTRIBUTED, MockManager())

        # 테스트 실행
        result1 = await update_user_balance("user123", 1500.0)
        print(f"DB Transaction result: {result1.is_success()}")

        result2 = await cache_user_session("user123", {"token": "abc123"})
        print(f"Redis Transaction result: {result2.is_success()}")

        result3 = await onboard_new_user({"email": "test@example.com"})
        print(f"Distributed Transaction result: {result3.is_success()}")

        # 컨텍스트 매니저 테스트
        await example_context_manager()

        print("🎉 Transaction decorator tests completed!")

    asyncio.run(main())
