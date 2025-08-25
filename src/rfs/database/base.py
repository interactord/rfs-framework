"""
RFS Database Base (RFS v4.1)

데이터베이스 기본 클래스 및 설정
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

try:
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import declarative_base, sessionmaker
    from sqlalchemy.pool import QueuePool

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    create_engine = None
    create_async_engine = None
    AsyncSession = None
    sessionmaker = None
    declarative_base = None
    QueuePool = None
    MetaData = None
    SQLALCHEMY_AVAILABLE = False

try:
    from tortoise import Tortoise
    from tortoise.connection import connections
    from tortoise.transactions import in_transaction

    TORTOISE_AVAILABLE = True
except ImportError:
    Tortoise = None
    connections = None
    in_transaction = None
    TORTOISE_AVAILABLE = False

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta
from ..core.transactions import TransactionManager

logger = get_logger(__name__)


class DatabaseType(str, Enum):
    """데이터베이스 타입"""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    CLOUD_SQL = "cloud_sql"


class ORMType(str, Enum):
    """ORM 타입"""

    SQLALCHEMY = "sqlalchemy"
    TORTOISE = "tortoise"
    AUTO = "auto"


@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""

    # 기본 연결 정보
    url: str
    database_type: DatabaseType = DatabaseType.POSTGRESQL
    orm_type: ORMType = ORMType.AUTO

    # 연결 풀 설정
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True

    # 트랜잭션 설정
    auto_commit: bool = False
    isolation_level: str = "READ_COMMITTED"

    # Cloud SQL 설정
    cloud_sql_instance: Optional[str] = None
    cloud_sql_project: Optional[str] = None
    cloud_sql_region: Optional[str] = None

    # 추가 옵션
    echo: bool = False
    echo_pool: bool = False
    future: bool = True
    extra_options: Dict[str, Any] = field(default_factory=dict)

    def get_sqlalchemy_url(self) -> str:
        """SQLAlchemy URL 생성"""
        if self.database_type == DatabaseType.CLOUD_SQL and self.cloud_sql_instance:
            # Cloud SQL Proxy 연결 문자열
            return f"postgresql+asyncpg://user:password@/dbname?host=/cloudsql/{self.cloud_sql_project}:{self.cloud_sql_region}:{self.cloud_sql_instance}"
        return self.url

    def get_tortoise_config(self) -> Dict[str, Any]:
        """Tortoise ORM 설정 생성"""
        config = {
            "connections": {
                "default": {
                    "engine": (
                        "tortoise.backends.asyncpg"
                        if "postgresql" in self.url
                        else "tortoise.backends.aiosqlite"
                    ),
                    "credentials": {
                        "database": (
                            self.url.split("/")[-1] if "/" in self.url else self.url
                        ),
                        "host": "localhost",
                        "port": 5432,
                        "user": "postgres",
                        "password": "",
                        "minsize": 1,
                        "maxsize": self.pool_size,
                        **self.extra_options,
                    },
                }
            },
            "apps": {
                "models": {"models": ["__main__"], "default_connection": "default"}
            },
        }
        return config


class ConnectionPool:
    """연결 풀 관리자"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None

    async def initialize(self) -> Result[None, str]:
        """연결 풀 초기화"""
        try:
            if self.config.orm_type == ORMType.SQLALCHEMY or (
                self.config.orm_type == ORMType.AUTO and SQLALCHEMY_AVAILABLE
            ):
                await self._initialize_sqlalchemy()
            elif self.config.orm_type == ORMType.TORTOISE or (
                self.config.orm_type == ORMType.AUTO and TORTOISE_AVAILABLE
            ):
                await self._initialize_tortoise()
            else:
                return Failure("사용 가능한 ORM이 없습니다")

            logger.info(
                f"데이터베이스 연결 풀 초기화 완료: {self.config.database_type}"
            )
            return Success(None)

        except Exception as e:
            error_msg = f"연결 풀 초기화 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _initialize_sqlalchemy(self):
        """SQLAlchemy 엔진 초기화"""
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SQLAlchemy가 설치되지 않았습니다")

        # 비동기 엔진 생성
        self._async_engine = create_async_engine(
            self.config.get_sqlalchemy_url(),
            echo=self.config.echo,
            echo_pool=self.config.echo_pool,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=self.config.pool_pre_ping,
            future=self.config.future,
            **self.config.extra_options,
        )

        # 세션 팩토리 생성
        self._async_session_factory = sessionmaker(
            self._async_engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info("SQLAlchemy 비동기 엔진 초기화 완료")

    async def _initialize_tortoise(self):
        """Tortoise ORM 초기화"""
        if not TORTOISE_AVAILABLE:
            raise RuntimeError("Tortoise ORM이 설치되지 않았습니다")

        config = self.config.get_tortoise_config()
        await Tortoise.init(config=config)

        logger.info("Tortoise ORM 초기화 완료")

    def get_engine(self):
        """엔진 반환"""
        return self._async_engine or self._engine

    def get_session_factory(self):
        """세션 팩토리 반환"""
        return self._async_session_factory or self._session_factory

    async def close(self):
        """연결 풀 종료"""
        try:
            if self._async_engine:
                await self._async_engine.dispose()
            if self._engine:
                self._engine.dispose()

            if TORTOISE_AVAILABLE and Tortoise._inited:
                await Tortoise.close_connections()

            logger.info("데이터베이스 연결 풀 종료")

        except Exception as e:
            logger.error(f"연결 풀 종료 실패: {e}")


class Database(ABC):
    """데이터베이스 추상 클래스"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection_pool = ConnectionPool(config)
        self._initialized = False

    async def initialize(self) -> Result[None, str]:
        """데이터베이스 초기화"""
        if self._initialized:
            return Success(None)

        result = await self.connection_pool.initialize()
        if result.is_success():
            self._initialized = True
            logger.info("데이터베이스 초기화 완료")

        return result

    @abstractmethod
    async def execute_query(
        self, query: str, params: Dict[str, Any] = None
    ) -> Result[Any, str]:
        """쿼리 실행"""
        pass

    @abstractmethod
    async def create_session(self):
        """세션 생성"""
        pass

    async def close(self):
        """데이터베이스 연결 종료"""
        if self.connection_pool:
            await self.connection_pool.close()
        self._initialized = False


class SQLAlchemyDatabase(Database):
    """SQLAlchemy 데이터베이스"""

    async def execute_query(
        self, query: str, params: Dict[str, Any] = None
    ) -> Result[Any, str]:
        """SQLAlchemy 쿼리 실행"""
        try:
            async with self.create_session() as session:
                result = await session.execute(query, params or {})
                await session.commit()
                return Success(result.fetchall())

        except Exception as e:
            return Failure(f"쿼리 실행 실패: {str(e)}")

    async def create_session(self):
        """SQLAlchemy 세션 생성"""
        session_factory = self.connection_pool.get_session_factory()
        return session_factory()


class TortoiseDatabase(Database):
    """Tortoise ORM 데이터베이스"""

    async def execute_query(
        self, query: str, params: Dict[str, Any] = None
    ) -> Result[Any, str]:
        """Tortoise 쿼리 실행"""
        try:
            connection = connections.get("default")
            result = await connection.execute_query(query, params or [])
            return Success(result)

        except Exception as e:
            return Failure(f"쿼리 실행 실패: {str(e)}")

    async def create_session(self):
        """Tortoise 트랜잭션 컨텍스트 반환"""
        return in_transaction()


class DatabaseManager(metaclass=SingletonMeta):
    """데이터베이스 매니저"""

    def __init__(self):
        self.databases: Dict[str, Database] = {}
        self.default_database: Optional[str] = None

    async def add_database(
        self, name: str, config: DatabaseConfig
    ) -> Result[None, str]:
        """데이터베이스 추가"""
        try:
            # ORM 타입에 따라 데이터베이스 생성
            if config.orm_type == ORMType.SQLALCHEMY or (
                config.orm_type == ORMType.AUTO and SQLALCHEMY_AVAILABLE
            ):
                database = SQLAlchemyDatabase(config)
            elif config.orm_type == ORMType.TORTOISE or (
                config.orm_type == ORMType.AUTO and TORTOISE_AVAILABLE
            ):
                database = TortoiseDatabase(config)
            else:
                return Failure("지원되는 ORM이 없습니다")

            # 데이터베이스 초기화
            result = await database.initialize()
            if not result.is_success():
                return result

            self.databases = {**self.databases, name: database}

            # 첫 번째 데이터베이스를 기본으로 설정
            if not self.default_database:
                self.default_database = name

            logger.info(f"데이터베이스 추가: {name}")
            return Success(None)

        except Exception as e:
            return Failure(f"데이터베이스 추가 실패: {str(e)}")

    def get_database(self, name: str = None) -> Optional[Database]:
        """데이터베이스 조회"""
        if name is None:
            name = self.default_database

        return self.databases.get(name) if name else None

    async def close_all(self):
        """모든 데이터베이스 연결 종료"""
        for name, database in self.databases.items():
            try:
                await database.close()
                logger.info(f"데이터베이스 종료: {name}")
            except Exception as e:
                logger.error(f"데이터베이스 종료 실패 ({name}): {e}")

        databases = {}
        self.default_database = None


# 전역 데이터베이스 매니저
def get_database_manager() -> DatabaseManager:
    """데이터베이스 매니저 인스턴스 반환"""
    return DatabaseManager()


def get_database(name: str = None) -> Optional[Database]:
    """데이터베이스 인스턴스 반환"""
    manager = get_database_manager()
    return manager.get_database(name)
