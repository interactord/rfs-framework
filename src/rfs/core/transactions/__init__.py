"""
Transaction Management System for RFS Framework

통합 트랜잭션 관리 - 로컬 및 분산 트랜잭션 지원
"""

from .base import (
    TransactionContext,
    TransactionStatus,
    IsolationLevel,
    PropagationLevel,
    TransactionOptions,
    TransactionMetadata,
    TransactionCallback,
    TransactionError,
    TransactionTimeout,
    TransactionRollback
)

from .manager import (
    TransactionManager,
    get_transaction_manager,
    begin_transaction,
    commit_transaction,
    rollback_transaction,
    get_current_transaction,
    is_in_transaction
)

from .decorator import (
    Transactional,
    transactional,
    ReadOnly,
    RequiresNew,
    Propagation,
    Isolation,
    Timeout,
    Rollback
)

from .distributed import (
    DistributedTransaction,
    TwoPhaseCommit,
    SagaTransaction,
    CompensationAction,
    distributed_transaction,
    saga_step,
    compensate
)

from .redis_tx import (
    RedisTransactionManager,
    redis_transactional,
    RedisLock,
    redis_atomic,
    redis_pipeline
)

__all__ = [
    # Base
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
    "redis_pipeline"
]