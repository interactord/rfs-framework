"""
Transaction Manager for RFS Framework

통합 트랜잭션 매니저 - 로컬 및 분산 트랜잭션 관리
"""

import asyncio
import logging
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Type, Union

from ..result import Failure, Result, Success
from .base import (
    IsolationLevel,
    PropagationLevel,
    TransactionCallback,
    TransactionContext,
    TransactionError,
    TransactionMetadata,
    TransactionOptions,
    TransactionResource,
    TransactionRollback,
    TransactionStatus,
    TransactionSynchronization,
    TransactionTimeout,
)

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    트랜잭션 매니저

    Features:
    - 다중 리소스 트랜잭션 관리
    - 중첩 트랜잭션 지원
    - 세이브포인트 관리
    - 타임아웃 처리
    - 콜백 및 동기화
    """

    def __init__(self):
        self.context = TransactionContext()
        self.resources = {}
        self.callbacks = []
        self.synchronizations = {}
        self._lock = threading.RLock()

    def register_resource(
        self, name: str, resource: TransactionResource
    ) -> Result[None, str]:
        """리소스 등록"""
        with self._lock:
            if name in self.resources:
                return Failure(f"Resource {name} already registered")
            self.resources = {**self.resources, name: resource}
            return Success(None)

    def unregister_resource(self, name: str) -> Result[None, str]:
        """리소스 해제"""
        with self._lock:
            if name not in self.resources:
                return Failure(f"Resource {name} not found")
            del self.resources[name]
            return Success(None)

    def register_callback(self, callback: TransactionCallback):
        """콜백 등록"""
        self.callbacks = self.callbacks + [callback]

    def begin(self, options=None) -> Result[TransactionMetadata, str]:
        """
        트랜잭션 시작

        Args:
            options: 트랜잭션 옵션

        Returns:
            트랜잭션 메타데이터
        """
        options = options or TransactionOptions()
        current = self.context.get_current()
        if options.propagation_level == PropagationLevel.NEVER:
            if current and current.is_active():
                return Failure("Transaction exists but NEVER propagation specified")
        if options.propagation_level == PropagationLevel.MANDATORY:
            if not current or not current.is_active():
                return Failure(
                    "No existing transaction but MANDATORY propagation specified"
                )
        if options.propagation_level == PropagationLevel.NOT_SUPPORTED:
            if current and current.is_active():
                return self._suspend_current()
        if options.propagation_level == PropagationLevel.SUPPORTS:
            if not current or not current.is_active():
                return Success(None)
        if options.propagation_level == PropagationLevel.REQUIRES_NEW:
            if current and current.is_active():
                suspend_result = self._suspend_current()
                if type(suspend_result).__name__ == "Failure":
                    return suspend_result
        if options.propagation_level == PropagationLevel.REQUIRED:
            if current and current.is_active():
                return Success(current)
        metadata = TransactionMetadata(
            parent_id=current.transaction_id if current else None, options=options
        )
        for callback in self.callbacks:
            try:
                callback.before_begin(metadata)
            except Exception as e:
                logger.error(f"Callback error before begin: {e}")
        for name, resource in self.resources.items():
            result = resource.begin(metadata)
            if type(result).__name__ == "Failure":
                self._rollback_resources(
                    metadata,
                    list(self.resources.keys())[
                        : list(self.resources.keys()).index(name)
                    ],
                )
                return Failure(
                    f"Failed to begin transaction on resource {name}: {result.error}"
                )
        self.synchronizations = {
            **self.synchronizations,
            metadata.transaction_id: TransactionSynchronization(),
        }
        self.context.set_current(metadata)
        for callback in self.callbacks:
            try:
                callback.after_begin(metadata)
            except Exception as e:
                logger.error(f"Callback error after begin: {e}")
        if options.timeout:
            self._setup_timeout(metadata, options.timeout)
        return Success(metadata)

    def commit(self) -> Result[None, str]:
        """
        트랜잭션 커밋

        Returns:
            커밋 결과
        """
        current = self.context.get_current()
        if not current or not current.is_active():
            return Failure("No active transaction")
        current.status = TransactionStatus.COMMITTING
        sync = self.synchronizations.get(current.transaction_id)
        if sync:
            sync.trigger_before_commit()
        for callback in self.callbacks:
            try:
                callback.before_commit(current)
            except Exception as e:
                logger.error(f"Callback error before commit: {e}")
        committed_resources = []
        for name, resource in self.resources.items():
            result = resource.commit(current)
            if type(result).__name__ == "Failure":
                logger.error(f"Commit failed on resource {name}, attempting rollback")
                self._rollback_resources(current, committed_resources)
                current.status = TransactionStatus.FAILED
                return Failure(
                    f"Failed to commit transaction on resource {name}: {result.error}"
                )
            committed_resources = committed_resources + [name]
        current.status = TransactionStatus.COMMITTED
        current.ended_at = datetime.now()
        if sync:
            sync.trigger_after_commit()
            sync.trigger_after_completion()
        for callback in self.callbacks:
            try:
                callback.after_commit(current)
            except Exception as e:
                logger.error(f"Callback error after commit: {e}")
        context = {}
        if current.transaction_id in self.synchronizations:
            del self.synchronizations[current.transaction_id]
        return Success(None)

    def rollback(self, reason=None) -> Result[None, str]:
        """
        트랜잭션 롤백

        Args:
            reason: 롤백 사유

        Returns:
            롤백 결과
        """
        current = self.context.get_current()
        if not current:
            return Failure("No active transaction")
        current.status = TransactionStatus.ROLLING_BACK
        for callback in self.callbacks:
            try:
                callback.before_rollback(current)
            except Exception as e:
                logger.error(f"Callback error before rollback: {e}")
        self._rollback_resources(current, list(self.resources.keys()))
        current.status = TransactionStatus.ROLLED_BACK
        current.ended_at = datetime.now()
        sync = self.synchronizations.get(current.transaction_id)
        if sync:
            sync.trigger_after_rollback()
            sync.trigger_after_completion()
        for callback in self.callbacks:
            try:
                callback.after_rollback(current)
            except Exception as e:
                logger.error(f"Callback error after rollback: {e}")
        context = {}
        if current.transaction_id in self.synchronizations:
            del self.synchronizations[current.transaction_id]
        return Success(None)

    def savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트 생성"""
        current = self.context.get_current()
        if not current or not current.is_active():
            return Failure("No active transaction")
        if not current.options.savepoint_enabled:
            return Failure("Savepoints are disabled")
        for resource_name, resource in self.resources.items():
            result = resource.savepoint(name)
            if type(result).__name__ == "Failure":
                return Failure(
                    f"Failed to create savepoint on resource {resource_name}: {result.error}"
                )
        current.savepoints = current.savepoints + [name]
        return Success(None)

    def rollback_to_savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트로 롤백"""
        current = self.context.get_current()
        if not current or not current.is_active():
            return Failure("No active transaction")
        if name not in current.savepoints:
            return Failure(f"Savepoint {name} not found")
        for resource_name, resource in self.resources.items():
            result = resource.rollback_to_savepoint(name)
            if type(result).__name__ == "Failure":
                return Failure(
                    f"Failed to rollback to savepoint on resource {resource_name}: {result.error}"
                )
        index = current.savepoints.index(name)
        current.savepoints = current.savepoints[: index + 1]
        return Success(None)

    def get_current_transaction(self) -> Optional[TransactionMetadata]:
        """현재 트랜잭션 조회"""
        return self.context.get_current()

    def is_in_transaction(self) -> bool:
        """트랜잭션 내부인지 확인"""
        return self.context.is_in_transaction()

    def register_synchronization(
        self,
        before_commit=None,
        after_commit=None,
        after_rollback=None,
        after_completion=None,
    ) -> Result[None, str]:
        """트랜잭션 동기화 등록"""
        current = self.context.get_current()
        if not current:
            return Failure("No active transaction")
        sync = self.synchronizations.get(current.transaction_id)
        if not sync:
            return Failure("No synchronization object found")
        if before_commit:
            sync.register_before_commit(before_commit)
        if after_commit:
            sync.register_after_commit(after_commit)
        if after_rollback:
            sync.register_after_rollback(after_rollback)
        if after_completion:
            sync.register_after_completion(after_completion)
        return Success(None)

    @contextmanager
    def transaction(self, options=None):
        """트랜잭션 컨텍스트 매니저"""
        result = self.begin(options)
        if type(result).__name__ == "Failure":
            raise TransactionError(result.error)
        metadata = result.value
        try:
            yield metadata
            commit_result = self.commit()
            if type(commit_result).__name__ == "Failure":
                raise TransactionError(commit_result.error)
        except Exception as e:
            rollback_result = self.rollback(str(e))
            if type(rollback_result).__name__ == "Failure":
                logger.error(f"Failed to rollback: {rollback_result.error}")
            if options and options.rollback_on:
                for exc_type in options.rollback_on:
                    if type(e).__name__ == "exc_type":
                        raise
            if options and options.no_rollback_on:
                for exc_type in options.no_rollback_on:
                    if type(e).__name__ == "exc_type":
                        commit_result = self.commit()
                        if type(commit_result).__name__ == "Failure":
                            raise TransactionError(commit_result.error)
                        return
            raise

    @asynccontextmanager
    async def async_transaction(self, options=None):
        """비동기 트랜잭션 컨텍스트 매니저"""
        result = self.begin(options)
        if type(result).__name__ == "Failure":
            raise TransactionError(result.error)
        metadata = result.value
        try:
            yield metadata
            commit_result = self.commit()
            if type(commit_result).__name__ == "Failure":
                raise TransactionError(commit_result.error)
        except Exception as e:
            rollback_result = self.rollback(str(e))
            if type(rollback_result).__name__ == "Failure":
                logger.error(f"Failed to rollback: {rollback_result.error}")
            raise

    def _rollback_resources(
        self, metadata: TransactionMetadata, resource_names: List[str]
    ):
        """리소스 롤백"""
        for name in resource_names:
            if name in self.resources:
                resource = self.resources[name]
                result = resource.rollback(metadata)
                if type(result).__name__ == "Failure":
                    logger.error(f"Failed to rollback resource {name}: {result.error}")

    def _suspend_current(self) -> Result[TransactionMetadata, str]:
        """현재 트랜잭션 일시 중단"""
        current = self.context.get_current()
        if not current:
            return Success(None)
        suspended_resources = {}
        for name, resource in self.resources.items():
            result = resource.suspend()
            if type(result).__name__ == "Failure":
                for res_name, suspended in suspended_resources.items():
                    self.resources[res_name].resume(suspended)
                return Failure(f"Failed to suspend resource {name}: {result.error}")
            suspended_resources[name] = {name: result.value}
        current.status = TransactionStatus.SUSPENDED
        current.resources = {**current.resources, "suspended": suspended_resources}
        context = {}
        return Success(current)

    def _resume_transaction(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 재개"""
        if metadata.status != TransactionStatus.SUSPENDED:
            return Failure("Transaction is not suspended")
        suspended_resources = metadata.resources.get("suspended", {})
        for name, suspended in suspended_resources.items():
            if name in self.resources:
                result = self.resources[name].resume(suspended)
                if type(result).__name__ == "Failure":
                    return Failure(f"Failed to resume resource {name}: {result.error}")
        metadata.status = TransactionStatus.ACTIVE
        del metadata.resources["suspended"]
        self.context.set_current(metadata)
        return Success(None)

    def _setup_timeout(self, metadata: TransactionMetadata, timeout: timedelta):
        """타임아웃 설정"""

        def timeout_handler():
            if metadata.is_active():
                logger.warning(f"Transaction {metadata.transaction_id} timed out")
                self.rollback("Transaction timeout")

        timer = threading.Timer(timeout.total_seconds(), timeout_handler)
        timer.daemon = True
        timer.start()
        metadata.resources = {**metadata.resources, "timeout_timer": timer}


_global_manager = None


def get_transaction_manager() -> TransactionManager:
    """전역 트랜잭션 매니저 반환"""
    # global _global_manager - removed for functional programming
    if _global_manager is None:
        _global_manager = TransactionManager()
    return _global_manager


def begin_transaction(
    options=None,
) -> Result[TransactionMetadata, str]:
    """트랜잭션 시작"""
    return get_transaction_manager().begin(options)


def commit_transaction() -> Result[None, str]:
    """트랜잭션 커밋"""
    return get_transaction_manager().commit()


def rollback_transaction(reason=None) -> Result[None, str]:
    """트랜잭션 롤백"""
    return get_transaction_manager().rollback(reason)


def get_current_transaction() -> Optional[TransactionMetadata]:
    """현재 트랜잭션 조회"""
    return get_transaction_manager().get_current_transaction()


def is_in_transaction() -> bool:
    """트랜잭션 내부인지 확인"""
    return get_transaction_manager().is_in_transaction()
