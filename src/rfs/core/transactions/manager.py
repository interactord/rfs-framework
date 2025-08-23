"""
Transaction Manager for RFS Framework

통합 트랜잭션 매니저 - 로컬 및 분산 트랜잭션 관리
"""

import asyncio
import threading
from typing import Optional, Dict, List, Any, Callable, Type, Union
from datetime import datetime, timedelta
from contextlib import contextmanager, asynccontextmanager
import logging

from ..core import Result, Success, Failure
from .base import (
    TransactionContext,
    TransactionStatus,
    TransactionMetadata,
    TransactionOptions,
    TransactionResource,
    TransactionCallback,
    TransactionError,
    TransactionTimeout,
    TransactionRollback,
    TransactionSynchronization,
    PropagationLevel,
    IsolationLevel
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
        self.resources: Dict[str, TransactionResource] = {}
        self.callbacks: List[TransactionCallback] = []
        self.synchronizations: Dict[str, TransactionSynchronization] = {}
        self._lock = threading.RLock()
        
    def register_resource(
        self,
        name: str,
        resource: TransactionResource
    ) -> Result[None, str]:
        """리소스 등록"""
        with self._lock:
            if name in self.resources:
                return Failure(f"Resource {name} already registered")
            self.resources[name] = resource
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
        self.callbacks.append(callback)
    
    def begin(
        self,
        options: Optional[TransactionOptions] = None
    ) -> Result[TransactionMetadata, str]:
        """
        트랜잭션 시작
        
        Args:
            options: 트랜잭션 옵션
        
        Returns:
            트랜잭션 메타데이터
        """
        options = options or TransactionOptions()
        
        # 전파 레벨 처리
        current = self.context.get_current()
        
        if options.propagation_level == PropagationLevel.NEVER:
            if current and current.is_active():
                return Failure("Transaction exists but NEVER propagation specified")
        
        if options.propagation_level == PropagationLevel.MANDATORY:
            if not current or not current.is_active():
                return Failure("No existing transaction but MANDATORY propagation specified")
        
        if options.propagation_level == PropagationLevel.NOT_SUPPORTED:
            if current and current.is_active():
                # 현재 트랜잭션 일시 중단
                return self._suspend_current()
        
        if options.propagation_level == PropagationLevel.SUPPORTS:
            if not current or not current.is_active():
                # 트랜잭션 없이 실행
                return Success(None)
        
        if options.propagation_level == PropagationLevel.REQUIRES_NEW:
            # 새 트랜잭션 생성 (현재 트랜잭션 일시 중단)
            if current and current.is_active():
                suspend_result = self._suspend_current()
                if isinstance(suspend_result, Failure):
                    return suspend_result
        
        if options.propagation_level == PropagationLevel.REQUIRED:
            if current and current.is_active():
                # 기존 트랜잭션 사용
                return Success(current)
        
        # 새 트랜잭션 생성
        metadata = TransactionMetadata(
            parent_id=current.transaction_id if current else None,
            options=options
        )
        
        # 콜백 실행
        for callback in self.callbacks:
            try:
                callback.before_begin(metadata)
            except Exception as e:
                logger.error(f"Callback error before begin: {e}")
        
        # 리소스별 트랜잭션 시작
        for name, resource in self.resources.items():
            result = resource.begin(metadata)
            if isinstance(result, Failure):
                # 롤백 필요
                self._rollback_resources(metadata, list(self.resources.keys())[:list(self.resources.keys()).index(name)])
                return Failure(f"Failed to begin transaction on resource {name}: {result.error}")
        
        # 동기화 객체 생성
        self.synchronizations[metadata.transaction_id] = TransactionSynchronization()
        
        # 컨텍스트 설정
        self.context.set_current(metadata)
        
        # 콜백 실행
        for callback in self.callbacks:
            try:
                callback.after_begin(metadata)
            except Exception as e:
                logger.error(f"Callback error after begin: {e}")
        
        # 타임아웃 설정
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
        
        # 동기화 - 커밋 전
        sync = self.synchronizations.get(current.transaction_id)
        if sync:
            sync.trigger_before_commit()
        
        # 콜백 실행
        for callback in self.callbacks:
            try:
                callback.before_commit(current)
            except Exception as e:
                logger.error(f"Callback error before commit: {e}")
        
        # 리소스별 커밋
        committed_resources = []
        for name, resource in self.resources.items():
            result = resource.commit(current)
            if isinstance(result, Failure):
                # 부분 커밋 상태 - 롤백 시도
                logger.error(f"Commit failed on resource {name}, attempting rollback")
                self._rollback_resources(current, committed_resources)
                current.status = TransactionStatus.FAILED
                return Failure(f"Failed to commit transaction on resource {name}: {result.error}")
            committed_resources.append(name)
        
        current.status = TransactionStatus.COMMITTED
        current.ended_at = datetime.now()
        
        # 동기화 - 커밋 후
        if sync:
            sync.trigger_after_commit()
            sync.trigger_after_completion()
        
        # 콜백 실행
        for callback in self.callbacks:
            try:
                callback.after_commit(current)
            except Exception as e:
                logger.error(f"Callback error after commit: {e}")
        
        # 컨텍스트 클리어
        self.context.clear()
        
        # 동기화 객체 제거
        if current.transaction_id in self.synchronizations:
            del self.synchronizations[current.transaction_id]
        
        return Success(None)
    
    def rollback(self, reason: Optional[str] = None) -> Result[None, str]:
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
        
        # 콜백 실행
        for callback in self.callbacks:
            try:
                callback.before_rollback(current)
            except Exception as e:
                logger.error(f"Callback error before rollback: {e}")
        
        # 리소스별 롤백
        self._rollback_resources(current, list(self.resources.keys()))
        
        current.status = TransactionStatus.ROLLED_BACK
        current.ended_at = datetime.now()
        
        # 동기화 - 롤백 후
        sync = self.synchronizations.get(current.transaction_id)
        if sync:
            sync.trigger_after_rollback()
            sync.trigger_after_completion()
        
        # 콜백 실행
        for callback in self.callbacks:
            try:
                callback.after_rollback(current)
            except Exception as e:
                logger.error(f"Callback error after rollback: {e}")
        
        # 컨텍스트 클리어
        self.context.clear()
        
        # 동기화 객체 제거
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
        
        # 리소스별 세이브포인트 생성
        for resource_name, resource in self.resources.items():
            result = resource.savepoint(name)
            if isinstance(result, Failure):
                return Failure(f"Failed to create savepoint on resource {resource_name}: {result.error}")
        
        current.savepoints.append(name)
        return Success(None)
    
    def rollback_to_savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트로 롤백"""
        current = self.context.get_current()
        if not current or not current.is_active():
            return Failure("No active transaction")
        
        if name not in current.savepoints:
            return Failure(f"Savepoint {name} not found")
        
        # 리소스별 세이브포인트 롤백
        for resource_name, resource in self.resources.items():
            result = resource.rollback_to_savepoint(name)
            if isinstance(result, Failure):
                return Failure(f"Failed to rollback to savepoint on resource {resource_name}: {result.error}")
        
        # 롤백된 세이브포인트 이후의 세이브포인트 제거
        index = current.savepoints.index(name)
        current.savepoints = current.savepoints[:index + 1]
        
        return Success(None)
    
    def get_current_transaction(self) -> Optional[TransactionMetadata]:
        """현재 트랜잭션 조회"""
        return self.context.get_current()
    
    def is_in_transaction(self) -> bool:
        """트랜잭션 내부인지 확인"""
        return self.context.is_in_transaction()
    
    def register_synchronization(
        self,
        before_commit: Optional[Callable] = None,
        after_commit: Optional[Callable] = None,
        after_rollback: Optional[Callable] = None,
        after_completion: Optional[Callable] = None
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
    def transaction(self, options: Optional[TransactionOptions] = None):
        """트랜잭션 컨텍스트 매니저"""
        result = self.begin(options)
        if isinstance(result, Failure):
            raise TransactionError(result.error)
        
        metadata = result.value
        try:
            yield metadata
            commit_result = self.commit()
            if isinstance(commit_result, Failure):
                raise TransactionError(commit_result.error)
        except Exception as e:
            rollback_result = self.rollback(str(e))
            if isinstance(rollback_result, Failure):
                logger.error(f"Failed to rollback: {rollback_result.error}")
            
            # 롤백 대상 예외 확인
            if options and options.rollback_on:
                for exc_type in options.rollback_on:
                    if isinstance(e, exc_type):
                        raise
            
            # 롤백 제외 예외 확인
            if options and options.no_rollback_on:
                for exc_type in options.no_rollback_on:
                    if isinstance(e, exc_type):
                        # 커밋 시도
                        commit_result = self.commit()
                        if isinstance(commit_result, Failure):
                            raise TransactionError(commit_result.error)
                        return
            
            raise
    
    @asynccontextmanager
    async def async_transaction(self, options: Optional[TransactionOptions] = None):
        """비동기 트랜잭션 컨텍스트 매니저"""
        result = self.begin(options)
        if isinstance(result, Failure):
            raise TransactionError(result.error)
        
        metadata = result.value
        try:
            yield metadata
            commit_result = self.commit()
            if isinstance(commit_result, Failure):
                raise TransactionError(commit_result.error)
        except Exception as e:
            rollback_result = self.rollback(str(e))
            if isinstance(rollback_result, Failure):
                logger.error(f"Failed to rollback: {rollback_result.error}")
            raise
    
    def _rollback_resources(self, metadata: TransactionMetadata, resource_names: List[str]):
        """리소스 롤백"""
        for name in resource_names:
            if name in self.resources:
                resource = self.resources[name]
                result = resource.rollback(metadata)
                if isinstance(result, Failure):
                    logger.error(f"Failed to rollback resource {name}: {result.error}")
    
    def _suspend_current(self) -> Result[TransactionMetadata, str]:
        """현재 트랜잭션 일시 중단"""
        current = self.context.get_current()
        if not current:
            return Success(None)
        
        suspended_resources = {}
        for name, resource in self.resources.items():
            result = resource.suspend()
            if isinstance(result, Failure):
                # 이미 중단된 리소스 복구
                for res_name, suspended in suspended_resources.items():
                    self.resources[res_name].resume(suspended)
                return Failure(f"Failed to suspend resource {name}: {result.error}")
            suspended_resources[name] = result.value
        
        current.status = TransactionStatus.SUSPENDED
        current.resources["suspended"] = suspended_resources
        self.context.clear()
        
        return Success(current)
    
    def _resume_transaction(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 재개"""
        if metadata.status != TransactionStatus.SUSPENDED:
            return Failure("Transaction is not suspended")
        
        suspended_resources = metadata.resources.get("suspended", {})
        for name, suspended in suspended_resources.items():
            if name in self.resources:
                result = self.resources[name].resume(suspended)
                if isinstance(result, Failure):
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
        metadata.resources["timeout_timer"] = timer


# 전역 트랜잭션 매니저
_global_manager: Optional[TransactionManager] = None


def get_transaction_manager() -> TransactionManager:
    """전역 트랜잭션 매니저 반환"""
    global _global_manager
    if _global_manager is None:
        _global_manager = TransactionManager()
    return _global_manager


def begin_transaction(
    options: Optional[TransactionOptions] = None
) -> Result[TransactionMetadata, str]:
    """트랜잭션 시작"""
    return get_transaction_manager().begin(options)


def commit_transaction() -> Result[None, str]:
    """트랜잭션 커밋"""
    return get_transaction_manager().commit()


def rollback_transaction(reason: Optional[str] = None) -> Result[None, str]:
    """트랜잭션 롤백"""
    return get_transaction_manager().rollback(reason)


def get_current_transaction() -> Optional[TransactionMetadata]:
    """현재 트랜잭션 조회"""
    return get_transaction_manager().get_current_transaction()


def is_in_transaction() -> bool:
    """트랜잭션 내부인지 확인"""
    return get_transaction_manager().is_in_transaction()