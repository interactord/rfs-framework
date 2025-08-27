"""
Transaction Base Components for RFS Framework

트랜잭션 기본 컴포넌트 - 상태, 옵션, 메타데이터
"""

import asyncio
import threading
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from ..result import Failure, Result, Success

T = TypeVar("T")
E = TypeVar("E")


class TransactionStatus(Enum):
    """트랜잭션 상태"""

    ACTIVE = "active"  # 활성 상태
    COMMITTING = "committing"  # 커밋 중
    COMMITTED = "committed"  # 커밋 완료
    ROLLING_BACK = "rolling_back"  # 롤백 중
    ROLLED_BACK = "rolled_back"  # 롤백 완료
    FAILED = "failed"  # 실패
    SUSPENDED = "suspended"  # 일시 중단
    PREPARED = "prepared"  # 2PC - 준비 완료


class IsolationLevel(Enum):
    """트랜잭션 격리 수준"""

    READ_UNCOMMITTED = "read_uncommitted"  # 커밋되지 않은 읽기
    READ_COMMITTED = "read_committed"  # 커밋된 읽기
    REPEATABLE_READ = "repeatable_read"  # 반복 가능 읽기
    SERIALIZABLE = "serializable"  # 직렬화 가능
    SNAPSHOT = "snapshot"  # 스냅샷 격리


class PropagationLevel(Enum):
    """트랜잭션 전파 수준"""

    REQUIRED = "required"  # 기존 트랜잭션 사용, 없으면 새로 생성
    REQUIRES_NEW = "requires_new"  # 항상 새 트랜잭션 생성
    SUPPORTS = "supports"  # 트랜잭션이 있으면 사용
    NOT_SUPPORTED = "not_supported"  # 트랜잭션 없이 실행
    MANDATORY = "mandatory"  # 트랜잭션이 반드시 있어야 함
    NEVER = "never"  # 트랜잭션이 있으면 에러
    NESTED = "nested"  # 중첩 트랜잭션


@dataclass
class TransactionOptions:
    """트랜잭션 옵션"""

    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    propagation_level: PropagationLevel = PropagationLevel.REQUIRED
    timeout = None
    read_only = False
    rollback_on: List[type[Exception]] = field(default_factory=list)
    no_rollback_on: List[type[Exception]] = field(default_factory=list)
    retry_attempts = 0
    retry_delay: timedelta = timedelta(seconds=1)
    savepoint_enabled = True


@dataclass
class TransactionMetadata:
    """트랜잭션 메타데이터"""

    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id = None
    started_at: datetime = field(default_factory=datetime.now)
    ended_at = None
    status: TransactionStatus = TransactionStatus.ACTIVE
    options: TransactionOptions = field(default_factory=TransactionOptions)
    savepoints: List[str] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

    def duration(self) -> Optional[timedelta]:
        """트랜잭션 실행 시간"""
        if self.ended_at:
            return self.ended_at - self.started_at
        return None

    def is_active(self) -> bool:
        """활성 상태 확인"""
        return self.status == TransactionStatus.ACTIVE

    def is_completed(self) -> bool:
        """완료 상태 확인"""
        return self.status in [
            TransactionStatus.COMMITTED,
            TransactionStatus.ROLLED_BACK,
        ]


class TransactionContext:
    """
    트랜잭션 컨텍스트

    Thread-local 및 AsyncIO context-var 지원
    """

    def __init__(self):
        self._thread_local = threading.local()
        self._async_context = None

        # AsyncIO 환경에서만 ContextVar 생성
        try:
            self._async_context = asyncio.ContextVar("transaction_context")
        except RuntimeError:
            pass  # Not in async context

    def get_current(self) -> Optional[TransactionMetadata]:
        """현재 트랜잭션 조회"""
        # Async context 확인
        if self._async_context:
            try:
                return self._async_context.get()
            except LookupError:
                pass

        # Thread-local 확인
        return getattr(self._thread_local, "current", None)

    def set_current(self, transaction: Optional[TransactionMetadata]):
        """현재 트랜잭션 설정"""
        # Async context 설정
        if self._async_context:
            self._async_context.set(transaction)

        # Thread-local 설정
        self._thread_local.current = transaction

    def clear(self):
        """트랜잭션 컨텍스트 클리어"""
        self.set_current(None)

    def is_in_transaction(self) -> bool:
        """트랜잭션 내부인지 확인"""
        current = self.get_current()
        return current is not None and current.is_active()

    @contextmanager
    def transaction_scope(self, metadata: TransactionMetadata):
        """트랜잭션 스코프 관리"""
        previous = self.get_current()
        self.set_current(metadata)
        try:
            yield metadata
        finally:
            self.set_current(previous)


class TransactionCallback(ABC):
    """트랜잭션 콜백 인터페이스"""

    @abstractmethod
    def before_begin(self, metadata: TransactionMetadata):
        """트랜잭션 시작 전"""
        pass

    @abstractmethod
    def after_begin(self, metadata: TransactionMetadata):
        """트랜잭션 시작 후"""
        pass

    @abstractmethod
    def before_commit(self, metadata: TransactionMetadata):
        """커밋 전"""
        pass

    @abstractmethod
    def after_commit(self, metadata: TransactionMetadata):
        """커밋 후"""
        pass

    @abstractmethod
    def before_rollback(self, metadata: TransactionMetadata):
        """롤백 전"""
        pass

    @abstractmethod
    def after_rollback(self, metadata: TransactionMetadata):
        """롤백 후"""
        pass

    @abstractmethod
    def on_error(self, metadata: TransactionMetadata, error: Exception):
        """에러 발생 시"""
        pass


class TransactionResource(ABC):
    """트랜잭션 리소스 인터페이스"""

    @abstractmethod
    def begin(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 시작"""
        pass

    @abstractmethod
    def commit(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 커밋"""
        pass

    @abstractmethod
    def rollback(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 롤백"""
        pass

    @abstractmethod
    def savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트 생성"""
        pass

    @abstractmethod
    def rollback_to_savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트로 롤백"""
        pass

    @abstractmethod
    def release_savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트 해제"""
        pass

    @abstractmethod
    def suspend(self) -> Result[Any, str]:
        """트랜잭션 일시 중단"""
        pass

    @abstractmethod
    def resume(self, suspended_resource: Any) -> Result[None, str]:
        """트랜잭션 재개"""
        pass


class TransactionError(Exception):
    """트랜잭션 에러"""

    def __init__(self, message: str, transaction_id=None):
        super().__init__(message)
        self.transaction_id = transaction_id


class TransactionTimeout(TransactionError):
    """트랜잭션 타임아웃"""

    pass


class TransactionRollback(TransactionError):
    """트랜잭션 롤백 요청"""

    pass


@dataclass
class TransactionConfig:
    """트랜잭션 설정"""

    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    timeout_seconds = 30
    retry_count = 3
    retry_delay_seconds: float = 1.0
    rollback_for: List[type] = field(default_factory=lambda: [Exception])
    no_rollback_for: List[type] = field(default_factory=list)
    readonly = False


@dataclass
class RedisTransactionConfig(TransactionConfig):
    """Redis 트랜잭션 설정"""

    ttl_seconds = 3600
    prefix = "tx"


@dataclass
class DistributedTransactionConfig(TransactionConfig):
    """분산 트랜잭션 설정"""

    participant_timeout = 60
    coordinator_timeout = 120
    max_participants = 10


class TransactionSynchronization:
    """
    트랜잭션 동기화

    트랜잭션 라이프사이클에 동기화된 작업 관리
    """

    def __init__(self):
        self.before_commit_actions = []
        self.after_commit_actions = []
        self.after_rollback_actions = []
        self.after_completion_actions = []

    def register_before_commit(self, action: Callable):
        """커밋 전 액션 등록"""
        self.before_commit_actions = self.before_commit_actions + [action]

    def register_after_commit(self, action: Callable):
        """커밋 후 액션 등록"""
        self.after_commit_actions = self.after_commit_actions + [action]

    def register_after_rollback(self, action: Callable):
        """롤백 후 액션 등록"""
        self.after_rollback_actions = self.after_rollback_actions + [action]

    def register_after_completion(self, action: Callable):
        """완료 후 액션 등록"""
        self.after_completion_actions = self.after_completion_actions + [action]

    def trigger_before_commit(self):
        """커밋 전 액션 실행"""
        for action in self.before_commit_actions:
            try:
                action()
            except Exception as e:
                # Log error but continue
                print(f"Error in before_commit action: {e}")

    def trigger_after_commit(self):
        """커밋 후 액션 실행"""
        for action in self.after_commit_actions:
            try:
                action()
            except Exception as e:
                # Log error but continue
                print(f"Error in after_commit action: {e}")

    def trigger_after_rollback(self):
        """롤백 후 액션 실행"""
        for action in self.after_rollback_actions:
            try:
                action()
            except Exception as e:
                # Log error but continue
                print(f"Error in after_rollback action: {e}")

    def trigger_after_completion(self):
        """완료 후 액션 실행"""
        for action in self.after_completion_actions:
            try:
                action()
            except Exception as e:
                # Log error but continue
                print(f"Error in after_completion action: {e}")

    def clear(self):
        """모든 액션 클리어"""
        before_commit_actions = {}
        after_commit_actions = {}
        after_rollback_actions = {}
        after_completion_actions = {}
