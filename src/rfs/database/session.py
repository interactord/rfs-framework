"""
RFS Database Session (RFS v4.1)

데이터베이스 세션 관리
"""

import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, AsyncContextManager, Callable, Dict, List, Optional, Type, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta
from .base import Database, get_database

logger = get_logger(__name__)

# 컨텍스트 변수들
current_session: ContextVar[Optional["DatabaseSession"]] = ContextVar(
    "current_session", default=None
)
current_transaction: ContextVar[Optional["DatabaseTransaction"]] = ContextVar(
    "current_transaction", default=None
)


@dataclass
class SessionConfig:
    """세션 설정"""

    auto_commit = True
    auto_flush = True
    expire_on_commit = False
    isolation_level = "READ_COMMITTED"
    timeout = 30
    pool_size = 10
    max_overflow = 20


class DatabaseSession(ABC):
    """데이터베이스 세션 추상 클래스"""

    def __init__(self, database: Database, config: SessionConfig = None):
        self.database = database
        self.config = config or SessionConfig()
        self.session_id = id(self)
        self._session = None
        self._is_active = False
        self._transaction = None

    @abstractmethod
    async def begin(self) -> Result[None, str]:
        """세션 시작"""
        pass

    @abstractmethod
    async def commit(self) -> Result[None, str]:
        """트랜잭션 커밋"""
        pass

    @abstractmethod
    async def rollback(self) -> Result[None, str]:
        """트랜잭션 롤백"""
        pass

    @abstractmethod
    async def close(self) -> Result[None, str]:
        """세션 종료"""
        pass

    @abstractmethod
    async def execute(
        self, query: str, params: Dict[str, Any] = None
    ) -> Result[Any, str]:
        """쿼리 실행"""
        pass

    @property
    def is_active(self) -> bool:
        """세션 활성화 상태"""
        return self._is_active

    async def __aenter__(self):
        """컨텍스트 매니저 시작"""
        result = await self.begin()
        if not result.is_success():
            raise Exception(f"세션 시작 실패: {result.unwrap_error()}")

        # 컨텍스트 변수 설정
        current_session.set(self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            await self.close()
            current_session.set(None)


class SQLAlchemySession(DatabaseSession):
    """SQLAlchemy 세션 구현"""

    async def begin(self) -> Result[None, str]:
        """세션 시작"""
        try:
            if self._is_active:
                return Success(None)

            # SQLAlchemy 세션 생성
            self._session = await self.database.create_session()
            self._is_active = True

            logger.debug(f"SQLAlchemy 세션 시작: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"세션 시작 실패: {str(e)}")

    async def commit(self) -> Result[None, str]:
        """트랜잭션 커밋"""
        try:
            if not self._is_active or not self._session:
                return Success(None)

            await self._session.commit()
            logger.debug(f"SQLAlchemy 세션 커밋: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"커밋 실패: {str(e)}")

    async def rollback(self) -> Result[None, str]:
        """트랜잭션 롤백"""
        try:
            if not self._is_active or not self._session:
                return Success(None)

            await self._session.rollback()
            logger.debug(f"SQLAlchemy 세션 롤백: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"롤백 실패: {str(e)}")

    async def close(self) -> Result[None, str]:
        """세션 종료"""
        try:
            if not self._is_active:
                return Success(None)

            if self._session:
                await self._session.close()

            self._is_active = False
            logger.debug(f"SQLAlchemy 세션 종료: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"세션 종료 실패: {str(e)}")

    async def execute(
        self, query: str, params: Dict[str, Any] = None
    ) -> Result[Any, str]:
        """쿼리 실행"""
        try:
            if not self._is_active or not self._session:
                return Failure("세션이 활성화되지 않았습니다")

            result = await self._session.execute(query, params or {})
            return Success(result)

        except Exception as e:
            return Failure(f"쿼리 실행 실패: {str(e)}")


class TortoiseSession(DatabaseSession):
    """Tortoise ORM 세션 구현"""

    async def begin(self) -> Result[None, str]:
        """세션 시작"""
        try:
            if self._is_active:
                return Success(None)

            # Tortoise 트랜잭션 컨텍스트 생성
            self._session = await self.database.create_session()
            self._is_active = True

            logger.debug(f"Tortoise 세션 시작: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"세션 시작 실패: {str(e)}")

    async def commit(self) -> Result[None, str]:
        """트랜잭션 커밋"""
        try:
            if not self._is_active:
                return Success(None)

            # Tortoise는 자동으로 커밋됨
            logger.debug(f"Tortoise 세션 커밋: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"커밋 실패: {str(e)}")

    async def rollback(self) -> Result[None, str]:
        """트랜잭션 롤백"""
        try:
            if not self._is_active:
                return Success(None)

            # Tortoise 롤백 처리
            logger.debug(f"Tortoise 세션 롤백: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"롤백 실패: {str(e)}")

    async def close(self) -> Result[None, str]:
        """세션 종료"""
        try:
            if not self._is_active:
                return Success(None)

            self._is_active = False
            logger.debug(f"Tortoise 세션 종료: {self.session_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"세션 종료 실패: {str(e)}")

    async def execute(
        self, query: str, params: Dict[str, Any] = None
    ) -> Result[Any, str]:
        """쿼리 실행"""
        try:
            if not self._is_active:
                return Failure("세션이 활성화되지 않았습니다")

            # Tortoise에서 Raw SQL 실행
            from tortoise import connections

            connection = connections.get("default")
            result = await connection.execute_query(query, params or [])

            return Success(result)

        except Exception as e:
            return Failure(f"쿼리 실행 실패: {str(e)}")


class DatabaseTransaction:
    """데이터베이스 트랜잭션"""

    def __init__(self, session: DatabaseSession):
        self.session = session
        self.transaction_id = id(self)
        self._is_active = False

    async def begin(self) -> Result[None, str]:
        """트랜잭션 시작"""
        try:
            if not self.session.is_active:
                return Failure("세션이 활성화되지 않았습니다")

            self._is_active = True
            current_transaction.set(self)

            logger.debug(f"트랜잭션 시작: {self.transaction_id}")
            return Success(None)

        except Exception as e:
            return Failure(f"트랜잭션 시작 실패: {str(e)}")

    async def commit(self) -> Result[None, str]:
        """트랜잭션 커밋"""
        if not self._is_active:
            return Success(None)

        result = await self.session.commit()
        self._is_active = False
        current_transaction.set(None)

        if result.is_success():
            logger.debug(f"트랜잭션 커밋: {self.transaction_id}")

        return result

    async def rollback(self) -> Result[None, str]:
        """트랜잭션 롤백"""
        if not self._is_active:
            return Success(None)

        result = await self.session.rollback()
        self._is_active = False
        current_transaction.set(None)

        if result.is_success():
            logger.debug(f"트랜잭션 롤백: {self.transaction_id}")

        return result

    @property
    def is_active(self) -> bool:
        """트랜잭션 활성화 상태"""
        return self._is_active

    async def __aenter__(self):
        """컨텍스트 매니저 시작"""
        result = await self.begin()
        if not result.is_success():
            raise Exception(f"트랜잭션 시작 실패: {result.unwrap_error()}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()


class SessionManager(metaclass=SingletonMeta):
    """세션 매니저"""

    def __init__(self):
        self.config = SessionConfig()
        self._sessions = {}

    def set_config(self, config: SessionConfig):
        """세션 설정"""
        self.config = config
        logger.info("세션 설정 업데이트")

    async def create_session(
        self, database: Database = None
    ) -> Result[DatabaseSession, str]:
        """세션 생성"""
        try:
            if database is None:
                database = get_database()
                if not database:
                    return Failure("데이터베이스 연결을 찾을 수 없습니다")

            # ORM 타입에 따라 세션 생성
            from .base import SQLAlchemyDatabase, TortoiseDatabase

            if type(database).__name__ == "SQLAlchemyDatabase":
                session = SQLAlchemySession(database, self.config)
            elif type(database).__name__ == "TortoiseDatabase":
                session = TortoiseSession(database, self.config)
            else:
                # 기본 세션 (추상 클래스이므로 실제로는 에러)
                return Failure("지원되지 않는 데이터베이스 타입입니다")

            self._sessions = {**self._sessions, session.session_id: session}
            logger.info(f"세션 생성: {session.session_id}")
            return Success(session)

        except Exception as e:
            return Failure(f"세션 생성 실패: {str(e)}")

    async def close_session(self, session: DatabaseSession) -> Result[None, str]:
        """세션 종료"""
        try:
            result = await session.close()
            if result.is_success():
                self._sessions = {
                    k: v for k, v in self._sessions.items() if k != session.session_id
                }
                logger.info(f"세션 종료: {session.session_id}")

            return result

        except Exception as e:
            return Failure(f"세션 종료 실패: {str(e)}")

    async def close_all_sessions(self) -> Result[None, str]:
        """모든 세션 종료"""
        try:
            for session in list(self._sessions.values()):
                await self.close_session(session)

            logger.info("모든 세션 종료")
            return Success(None)

        except Exception as e:
            return Failure(f"세션 일괄 종료 실패: {str(e)}")

    def get_current_session(self) -> Optional[DatabaseSession]:
        """현재 세션 조회"""
        return current_session.get(None)

    def get_current_transaction(self) -> Optional[DatabaseTransaction]:
        """현재 트랜잭션 조회"""
        return current_transaction.get(None)


# 전역 세션 매니저
def get_session_manager() -> SessionManager:
    """세션 매니저 인스턴스 반환"""
    return SessionManager()


# 편의 함수들
async def create_session(database: Database = None) -> Result[DatabaseSession, str]:
    """세션 생성"""
    manager = get_session_manager()
    return await manager.create_session(database)


def get_session() -> Optional[DatabaseSession]:
    """현재 세션 조회"""
    return current_session.get(None)


def get_current_transaction() -> Optional[DatabaseTransaction]:
    """현재 트랜잭션 조회"""
    return current_transaction.get(None)


# 컨텍스트 매니저
class session_scope:
    """세션 스코프 컨텍스트 매니저"""

    def __init__(self, database: Database = None, config: SessionConfig = None):
        self.database = database
        self.config = config
        self.session = None

    async def __aenter__(self) -> DatabaseSession:
        """컨텍스트 매니저 시작"""
        manager = get_session_manager()
        if self.config:
            manager.set_config(self.config)

        result = await manager.create_session(self.database)
        if not result.is_success():
            raise Exception(f"세션 생성 실패: {result.unwrap_error()}")

        self.session = result.unwrap()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        if self.session:
            manager = get_session_manager()
            await manager.close_session(self.session)


class transaction_scope:
    """트랜잭션 스코프 컨텍스트 매니저"""

    def __init__(self, session: DatabaseSession = None):
        self.session = session
        self.transaction = None
        self._created_session = False

    async def __aenter__(self) -> DatabaseTransaction:
        """컨텍스트 매니저 시작"""
        # 세션이 없으면 새로 생성
        if self.session is None:
            manager = get_session_manager()
            result = await manager.create_session()
            if not result.is_success():
                raise Exception(f"세션 생성 실패: {result.unwrap_error()}")

            self.session = result.unwrap()
            self._created_session = True

            # 세션 시작
            begin_result = await self.session.begin()
            if not begin_result.is_success():
                raise Exception(f"세션 시작 실패: {begin_result.unwrap_error()}")

        # 트랜잭션 생성
        self.transaction = DatabaseTransaction(self.session)
        return self.transaction

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        if self.transaction:
            if exc_type is None:
                await self.transaction.commit()
            else:
                await self.transaction.rollback()

        # 세션을 새로 생성했다면 종료
        if self._created_session and self.session:
            manager = get_session_manager()
            await manager.close_session(self.session)


# 데코레이터
def with_session(
    func: Callable = None, database: Database = None, config: SessionConfig = None
):
    """세션 데코레이터"""

    def decorator(f: Callable) -> Callable:
        if asyncio.iscoroutinefunction(f):

            async def async_wrapper(*args, **kwargs):
                async with session_scope(database, config) as session:
                    return await f(*args, session=session, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                # 동기 함수는 지원하지 않음
                raise RuntimeError("동기 함수는 지원되지 않습니다")

            return sync_wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


def with_transaction(func: Callable = None, session: DatabaseSession = None):
    """트랜잭션 데코레이터"""

    def decorator(f: Callable) -> Callable:
        if asyncio.iscoroutinefunction(f):

            async def async_wrapper(*args, **kwargs):
                async with transaction_scope(session) as transaction:
                    return await f(*args, transaction=transaction, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                # 동기 함수는 지원하지 않음
                raise RuntimeError("동기 함수는 지원되지 않습니다")

            return sync_wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)
