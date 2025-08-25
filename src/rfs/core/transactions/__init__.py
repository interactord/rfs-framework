"""
Transaction Management System for RFS Framework

통합 트랜잭션 관리 - 로컬 및 분산 트랜잭션 지원
"""

from .base import (
    DistributedTransactionConfig,
    IsolationLevel,
    PropagationLevel,
    RedisTransactionConfig,
    TransactionCallback,
    TransactionConfig,
    TransactionContext,
    TransactionError,
    TransactionMetadata,
    TransactionOptions,
    TransactionRollback,
    TransactionStatus,
    TransactionTimeout,
)
from .decorator import (
    Isolation,
    Propagation,
    ReadOnly,
    RequiresNew,
    Rollback,
    Timeout,
    Transactional,
    transactional,
)
from .distributed import (
    CompensationAction,
    DistributedTransaction,
    SagaTransaction,
    TwoPhaseCommit,
    compensate,
    distributed_transaction,
    saga_step,
)
from .manager import (
    TransactionManager,
    begin_transaction,
    commit_transaction,
    get_current_transaction,
    get_transaction_manager,
    is_in_transaction,
    rollback_transaction,
)
from .redis_tx import (
    RedisLock,
    RedisTransactionManager,
    redis_atomic,
    redis_pipeline,
    redis_transactional,
)

__all__ = [
    # Base
    "TransactionConfig",
    "RedisTransactionConfig",
    "DistributedTransactionConfig",
    "TransactionContext",
    "TransactionStatus",
    "IsolationLevel",
    "PropagationLevel",
    "TransactionOptions",
    "TransactionMetadata",
    "TransactionCallback",
    "TransactionError",
    "TransactionTimeout",
    "TransactionRollback",
    # Manager
    "TransactionManager",
    "get_transaction_manager",
    "begin_transaction",
    "commit_transaction",
    "rollback_transaction",
    "get_current_transaction",
    "is_in_transaction",
    # Decorator
    "Transactional",
    "transactional",
    "ReadOnly",
    "RequiresNew",
    "Propagation",
    "Isolation",
    "Timeout",
    "Rollback",
    # Distributed
    "DistributedTransaction",
    "TwoPhaseCommit",
    "SagaTransaction",
    "CompensationAction",
    "distributed_transaction",
    "saga_step",
    "compensate",
    # Redis
    "RedisTransactionManager",
    "redis_transactional",
    "RedisLock",
    "redis_atomic",
    "redis_pipeline",
]
