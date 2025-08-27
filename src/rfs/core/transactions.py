"""
RFS v4.1 Transaction Management System
트랜잭션 관리 및 어노테이션 기반 트랜잭션 데코레이터

주요 특징:
- 데이터베이스 트랜잭션 지원 (SQLAlchemy, AsyncPG)
- Redis 트랜잭션 및 파이프라인 지원
- 분산 트랜잭션 (Saga 패턴 연동)
- 자동 롤백 및 재시도 로직
- 격리 수준 및 타임아웃 설정
"""

import asyncio
import functools
import logging
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from ..core.result import Failure, Result, Success

logger = logging.getLogger(__name__)

T = TypeVar("T")
E = TypeVar("E")


class IsolationLevel(Enum):
    """트랜잭션 격리 수준"""

    READ_UNCOMMITTED = "READ_UNCOMMITTED"
    READ_COMMITTED = "READ_COMMITTED"
    REPEATABLE_READ = "REPEATABLE_READ"
    SERIALIZABLE = "SERIALIZABLE"


class TransactionStatus(Enum):
    """트랜잭션 상태"""

    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class TransactionType(Enum):
    """트랜잭션 타입"""

    DATABASE = "database"
    REDIS = "redis"
    DISTRIBUTED = "distributed"
    COMPOSITE = "composite"


@dataclass
class TransactionConfig:
    """트랜잭션 설정"""

    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    timeout_seconds = 30
    retry_count = 3
    retry_delay_seconds: float = 1.0
    rollback_for: List[type] = field(default_factory=list)
    no_rollback_for: List[type] = field(default_factory=list)
    readonly = False

    def __post_init__(self):
        if not self.rollback_for:
            self.rollback_for = [Exception]


@dataclass
class RedisTransactionConfig:
    """Redis 트랜잭션 설정"""

    ttl_seconds = None
    key_pattern = None
    watch_keys: List[str] = field(default_factory=list)
    timeout_seconds = 30
    retry_count = 3
    pipeline_mode = True


@dataclass
class DistributedTransactionConfig:
    """분산 트랜잭션 설정"""

    saga_id: str
    timeout_seconds = 300  # 5분
    retry_count = 3
    compensation_timeout = 60
    idempotent = True


@dataclass
class TransactionContext:
    """트랜잭션 컨텍스트"""

    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    transaction_type: TransactionType = TransactionType.DATABASE
    status: TransactionStatus = TransactionStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at = None
    config: Optional[
        Union[TransactionConfig, RedisTransactionConfig, DistributedTransactionConfig]
    ] = None

    # 실행 정보
    attempts = 0
    last_error = None
    rollback_reason = None

    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)


class TransactionManager(ABC):
    """트랜잭션 매니저 인터페이스"""

    @abstractmethod
    async def begin_transaction(self, context: TransactionContext) -> Result[Any, str]:
        """트랜잭션 시작"""
        pass

    @abstractmethod
    async def commit_transaction(
        self, context: TransactionContext
    ) -> Result[None, str]:
        """트랜잭션 커밋"""
        pass

    @abstractmethod
    async def rollback_transaction(
        self, context: TransactionContext, reason: str = None
    ) -> Result[None, str]:
        """트랜잭션 롤백"""
        pass

    @abstractmethod
    async def execute_in_transaction(
        self, context: TransactionContext, func: Callable[..., Any], *args, **kwargs
    ) -> Result[Any, str]:
        """트랜잭션 내에서 함수 실행"""
        pass


class DatabaseTransactionManager(TransactionManager):
    """데이터베이스 트랜잭션 매니저"""

    def __init__(self, connection_factory: Callable = None):
        self.connection_factory = connection_factory
        self._active_transactions = {}

    async def begin_transaction(self, context: TransactionContext) -> Result[Any, str]:
        """데이터베이스 트랜잭션 시작"""
        try:
            if not self.connection_factory:
                return Failure("No database connection factory configured")

            # 연결 획득
            connection = await self.connection_factory()

            # 트랜잭션 시작
            if hasattr(connection, "begin"):
                transaction = await connection.begin()
            else:
                # SQLAlchemy style
                transaction = connection.begin()

            # 격리 수준 설정
            if (
                hasattr(context.config, "__class__")
                and context.config.__class__.__name__ == "TransactionConfig"
            ):
                isolation_sql = f"SET TRANSACTION ISOLATION LEVEL {context.config.isolation_level.value}"
                await connection.execute(isolation_sql)

            self._active_transactions = {
                **self._active_transactions,
                context.transaction_id: {
                    "connection": connection,
                    "transaction": transaction,
                    "context": context,
                },
            }

            context.status = TransactionStatus.ACTIVE
            logger.debug(f"Database transaction {context.transaction_id} started")

            return Success(transaction)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to begin database transaction: {str(e)}")

    async def commit_transaction(
        self, context: TransactionContext
    ) -> Result[None, str]:
        """데이터베이스 트랜잭션 커밋"""
        try:
            transaction_info = self._active_transactions.get(context.transaction_id)
            if not transaction_info:
                return Failure(f"Transaction {context.transaction_id} not found")

            transaction = transaction_info["transaction"]

            # 커밋 실행
            if hasattr(transaction, "commit"):
                await transaction.commit()
            else:
                transaction.commit()

            context.status = TransactionStatus.COMMITTED
            context.completed_at = datetime.now()

            # 정리
            connection = transaction_info["connection"]
            if hasattr(connection, "close"):
                await connection.close()

            del self._active_transactions[context.transaction_id]

            logger.debug(f"Database transaction {context.transaction_id} committed")
            return Success(None)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to commit transaction: {str(e)}")

    async def rollback_transaction(
        self, context: TransactionContext, reason: str = None
    ) -> Result[None, str]:
        """데이터베이스 트랜잭션 롤백"""
        try:
            transaction_info = self._active_transactions.get(context.transaction_id)
            if not transaction_info:
                return Failure(f"Transaction {context.transaction_id} not found")

            transaction = transaction_info["transaction"]

            # 롤백 실행
            if hasattr(transaction, "rollback"):
                await transaction.rollback()
            else:
                transaction.rollback()

            context.status = TransactionStatus.ROLLED_BACK
            context.completed_at = datetime.now()
            context.rollback_reason = reason

            # 정리
            connection = transaction_info["connection"]
            if hasattr(connection, "close"):
                await connection.close()

            del self._active_transactions[context.transaction_id]

            logger.debug(
                f"Database transaction {context.transaction_id} rolled back: {reason}"
            )
            return Success(None)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to rollback transaction: {str(e)}")

    async def execute_in_transaction(
        self, context: TransactionContext, func: Callable[..., Any], *args, **kwargs
    ) -> Result[Any, str]:
        """데이터베이스 트랜잭션 내에서 함수 실행"""
        begin_result = await self.begin_transaction(context)
        if begin_result.is_failure():
            return begin_result

        try:
            # 함수 실행
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 커밋
            commit_result = await self.commit_transaction(context)
            if commit_result.is_failure():
                return commit_result

            return Success(result)

        except Exception as e:
            # 롤백 결정
            should_rollback = self._should_rollback(e, context.config)

            if should_rollback:
                await self.rollback_transaction(context, str(e))
                return Failure(f"Transaction rolled back due to: {str(e)}")
            else:
                # 롤백하지 않고 커밋
                commit_result = await self.commit_transaction(context)
                if commit_result.is_failure():
                    return commit_result
                raise e

    def _should_rollback(
        self, exception: Exception, config: Optional[TransactionConfig]
    ) -> bool:
        """롤백 여부 결정"""
        if not config:
            return True

        # no_rollback_for에 포함된 예외는 롤백하지 않음
        for exc_type in config.no_rollback_for:
            if type(exception).__name__ == "exc_type":
                return False

        # rollback_for에 포함된 예외는 롤백
        for exc_type in config.rollback_for:
            if type(exception).__name__ == "exc_type":
                return True

        return False


class RedisTransactionManager(TransactionManager):
    """Redis 트랜잭션 매니저"""

    def __init__(self, redis_client_factory: Callable = None):
        self.redis_client_factory = redis_client_factory
        self._active_transactions = {}

    async def begin_transaction(self, context: TransactionContext) -> Result[Any, str]:
        """Redis 트랜잭션 시작"""
        try:
            if not self.redis_client_factory:
                return Failure("No Redis client factory configured")

            client = await self.redis_client_factory()

            # 파이프라인 생성
            if (
                hasattr(context.config, "__class__")
                and context.config.__class__.__name__ == "RedisTransactionConfig"
            ) and context.config.pipeline_mode:
                pipeline = client.pipeline(transaction=True)

                # WATCH 키 설정
                if context.config.watch_keys:
                    await pipeline.watch(*context.config.watch_keys)

                # MULTI 시작
                pipeline.multi()
            else:
                pipeline = client

            self._active_transactions = {
                **self._active_transactions,
                context.transaction_id: {
                    "client": client,
                    "pipeline": pipeline,
                    "context": context,
                },
            }

            context.status = TransactionStatus.ACTIVE
            logger.debug(f"Redis transaction {context.transaction_id} started")

            return Success(pipeline)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to begin Redis transaction: {str(e)}")

    async def commit_transaction(
        self, context: TransactionContext
    ) -> Result[None, str]:
        """Redis 트랜잭션 커밋"""
        try:
            transaction_info = self._active_transactions.get(context.transaction_id)
            if not transaction_info:
                return Failure(f"Transaction {context.transaction_id} not found")

            pipeline = transaction_info["pipeline"]

            # 파이프라인 실행
            if hasattr(pipeline, "execute"):
                await pipeline.execute()

            context.status = TransactionStatus.COMMITTED
            context.completed_at = datetime.now()

            # 정리
            del self._active_transactions[context.transaction_id]

            logger.debug(f"Redis transaction {context.transaction_id} committed")
            return Success(None)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to commit Redis transaction: {str(e)}")

    async def rollback_transaction(
        self, context: TransactionContext, reason: str = None
    ) -> Result[None, str]:
        """Redis 트랜잭션 롤백"""
        try:
            transaction_info = self._active_transactions.get(context.transaction_id)
            if not transaction_info:
                return Failure(f"Transaction {context.transaction_id} not found")

            pipeline = transaction_info["pipeline"]

            # 파이프라인 취소
            if hasattr(pipeline, "discard"):
                await pipeline.discard()
            elif hasattr(pipeline, "reset"):
                pipeline.reset()

            context.status = TransactionStatus.ROLLED_BACK
            context.completed_at = datetime.now()
            context.rollback_reason = reason

            # 정리
            del self._active_transactions[context.transaction_id]

            logger.debug(
                f"Redis transaction {context.transaction_id} rolled back: {reason}"
            )
            return Success(None)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to rollback Redis transaction: {str(e)}")

    async def execute_in_transaction(
        self, context: TransactionContext, func: Callable[..., Any], *args, **kwargs
    ) -> Result[Any, str]:
        """Redis 트랜잭션 내에서 함수 실행"""
        begin_result = await self.begin_transaction(context)
        if begin_result.is_failure():
            return begin_result

        try:
            # 함수 실행
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 커밋
            commit_result = await self.commit_transaction(context)
            if commit_result.is_failure():
                return commit_result

            return Success(result)

        except Exception as e:
            # Redis는 일반적으로 항상 롤백
            await self.rollback_transaction(context, str(e))
            return Failure(f"Redis transaction rolled back due to: {str(e)}")


class DistributedTransactionManager(TransactionManager):
    """분산 트랜잭션 매니저 (Saga 패턴 연동)"""

    def __init__(self, saga_manager=None):
        self.saga_manager = saga_manager
        self._active_transactions = {}

    async def begin_transaction(self, context: TransactionContext) -> Result[Any, str]:
        """분산 트랜잭션 시작"""
        try:
            if not self.saga_manager:
                return Failure("No Saga manager configured")

            config = context.config
            if not (type(config).__name__ == "DistributedTransactionConfig"):
                return Failure("Invalid distributed transaction configuration")

            # Saga 인스턴스 생성
            saga = await self.saga_manager.create_saga(config.saga_id)

            self._active_transactions = {
                **self._active_transactions,
                context.transaction_id: {"saga": saga, "context": context},
            }

            context.status = TransactionStatus.ACTIVE
            logger.debug(
                f"Distributed transaction {context.transaction_id} started with saga {config.saga_id}"
            )

            return Success(saga)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to begin distributed transaction: {str(e)}")

    async def commit_transaction(
        self, context: TransactionContext
    ) -> Result[None, str]:
        """분산 트랜잭션 커밋"""
        try:
            transaction_info = self._active_transactions.get(context.transaction_id)
            if not transaction_info:
                return Failure(f"Transaction {context.transaction_id} not found")

            saga = transaction_info["saga"]

            # Saga 실행 완료
            result = await saga.complete()
            if result.is_failure():
                return result

            context.status = TransactionStatus.COMMITTED
            context.completed_at = datetime.now()

            # 정리
            del self._active_transactions[context.transaction_id]

            logger.debug(f"Distributed transaction {context.transaction_id} committed")
            return Success(None)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to commit distributed transaction: {str(e)}")

    async def rollback_transaction(
        self, context: TransactionContext, reason: str = None
    ) -> Result[None, str]:
        """분산 트랜잭션 롤백 (보상 트랜잭션)"""
        try:
            transaction_info = self._active_transactions.get(context.transaction_id)
            if not transaction_info:
                return Failure(f"Transaction {context.transaction_id} not found")

            saga = transaction_info["saga"]

            # Saga 보상 트랜잭션 실행
            result = await saga.compensate()
            if result.is_failure():
                logger.error(
                    f"Compensation failed for saga {saga.saga_id}: {result.error}"
                )

            context.status = TransactionStatus.ROLLED_BACK
            context.completed_at = datetime.now()
            context.rollback_reason = reason

            # 정리
            del self._active_transactions[context.transaction_id]

            logger.debug(
                f"Distributed transaction {context.transaction_id} rolled back: {reason}"
            )
            return Success(None)

        except Exception as e:
            context.status = TransactionStatus.FAILED
            context.last_error = e
            return Failure(f"Failed to rollback distributed transaction: {str(e)}")

    async def execute_in_transaction(
        self, context: TransactionContext, func: Callable[..., Any], *args, **kwargs
    ) -> Result[Any, str]:
        """분산 트랜잭션 내에서 함수 실행"""
        begin_result = await self.begin_transaction(context)
        if begin_result.is_failure():
            return begin_result

        try:
            # 함수 실행
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 커밋
            commit_result = await self.commit_transaction(context)
            if commit_result.is_failure():
                return commit_result

            return Success(result)

        except Exception as e:
            # 보상 트랜잭션 실행
            await self.rollback_transaction(context, str(e))
            return Failure(f"Distributed transaction compensated due to: {str(e)}")


class TransactionRegistry:
    """트랜잭션 매니저 레지스트리"""

    def __init__(self):
        self._managers = {}
        self._default_configs = {}

    def register_manager(
        self, transaction_type: TransactionType, manager: TransactionManager
    ):
        """트랜잭션 매니저 등록"""
        self._managers = {**self._managers, transaction_type: manager}
        logger.info(f"Registered transaction manager for {transaction_type.value}")

    def get_manager(
        self, transaction_type: TransactionType
    ) -> Optional[TransactionManager]:
        """트랜잭션 매니저 조회"""
        return self._managers.get(transaction_type)

    def set_default_config(self, transaction_type: TransactionType, config: Any):
        """기본 설정 등록"""
        self._default_configs = {**self._default_configs, transaction_type: config}

    def get_default_config(self, transaction_type: TransactionType) -> Optional[Any]:
        """기본 설정 조회"""
        return self._default_configs.get(transaction_type)


# 전역 트랜잭션 레지스트리
_transaction_registry = TransactionRegistry()


def get_transaction_registry() -> TransactionRegistry:
    """전역 트랜잭션 레지스트리 조회"""
    return _transaction_registry


async def execute_with_retry(
    func: Callable[..., Any], context: TransactionContext, *args, **kwargs
) -> Result[Any, str]:
    """재시도 로직을 포함한 함수 실행"""
    last_error = None

    for attempt in range(1, context.config.retry_count + 1):
        context.attempts = attempt

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return Success(result)

        except Exception as e:
            last_error = e
            context.last_error = e

            if attempt < context.config.retry_count:
                delay = context.config.retry_delay_seconds * (
                    2 ** (attempt - 1)
                )  # Exponential backoff
                logger.warning(
                    f"Transaction attempt {attempt} failed, retrying in {delay}s: {e}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Transaction failed after {attempt} attempts: {e}")

    return Failure(
        f"Transaction failed after {context.config.retry_count} attempts: {str(last_error)}"
    )


# 편의 함수
def get_default_transaction_manager() -> DatabaseTransactionManager:
    """기본 트랜잭션 매니저 반환"""
    return DatabaseTransactionManager()


# 예제 및 테스트
if __name__ == "__main__":

    async def test_transaction_system():
        """트랜잭션 시스템 테스트"""
        print("🧪 Testing Transaction System...")

        # 트랜잭션 설정
        db_config = TransactionConfig(
            isolation_level=IsolationLevel.READ_COMMITTED,
            timeout_seconds=30,
            retry_count=3,
        )

        redis_config = RedisTransactionConfig(ttl_seconds=3600, pipeline_mode=True)

        # 트랜잭션 컨텍스트
        db_context = TransactionContext(
            transaction_type=TransactionType.DATABASE, config=db_config
        )

        redis_context = TransactionContext(
            transaction_type=TransactionType.REDIS, config=redis_config
        )

        print(f"✅ DB Transaction Context: {db_context.transaction_id}")
        print(f"✅ Redis Transaction Context: {redis_context.transaction_id}")

        # 트랜잭션 매니저 테스트 (모킹)
        class MockDatabaseManager(DatabaseTransactionManager):
            async def begin_transaction(self, context):
                context.status = TransactionStatus.ACTIVE
                return Success("mock_transaction")

            async def commit_transaction(self, context):
                context.status = TransactionStatus.COMMITTED
                return Success(None)

        # 매니저 등록
        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, MockDatabaseManager())

        manager = registry.get_manager(TransactionType.DATABASE)
        if manager:
            result = await manager.begin_transaction(db_context)
            print(f"✅ Begin transaction result: {result.is_success()}")

            if result.is_success():
                commit_result = await manager.commit_transaction(db_context)
                print(f"✅ Commit transaction result: {commit_result.is_success()}")

        print("🎉 Transaction system test completed!")

    asyncio.run(test_transaction_system())
