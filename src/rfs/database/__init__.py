"""
RFS Database Abstraction (RFS v4.1)

통합 데이터베이스 추상화 레이어
- SQLAlchemy/Tortoise ORM 지원
- 트랜잭션 관리 통합
- 연결 풀링 및 최적화
- Cloud SQL 통합
"""

from .base import (
    DatabaseConfig, DatabaseType, ORMType, ConnectionPool,
    Database, SQLAlchemyDatabase, TortoiseDatabase,
    DatabaseManager, get_database, get_database_manager
)
from .models import (
    BaseModel, SQLAlchemyModel, TortoiseModel, 
    Field, Table, Model, ModelRegistry,
    create_model, register_model, get_model_registry
)
from .repository import (
    Repository, BaseRepository, CRUDRepository, RepositoryConfig, RepositoryRegistry,
    repository, get_repository, create_repository, get_repository_registry
)
from .query import (
    Query, QueryBuilder, AdvancedQueryBuilder, TransactionalQueryBuilder,
    Filter, Sort, Pagination, Operator, SortOrder,
    Q, build_query, execute_query,
    # 필터 편의 함수들
    eq, ne, lt, le, gt, ge, in_, nin, like, ilike, regex,
    is_null, is_not_null, between, contains
)
from .migration import (
    Migration, SQLMigration, PythonMigration, MigrationStatus, MigrationInfo,
    MigrationManager, AlembicMigrationManager,
    create_migration, run_migrations, rollback_migration,
    get_migration_manager, set_migration_manager
)
from .session import (
    DatabaseSession, SQLAlchemySession, TortoiseSession, DatabaseTransaction,
    SessionConfig, SessionManager, session_scope, transaction_scope,
    get_session, create_session, get_session_manager, get_current_transaction,
    with_session, with_transaction
)

__all__ = [
    # Database Core
    "DatabaseConfig", "DatabaseType", "ORMType", "ConnectionPool",
    "Database", "SQLAlchemyDatabase", "TortoiseDatabase",
    "DatabaseManager", "get_database", "get_database_manager",
    
    # Models
    "BaseModel", "SQLAlchemyModel", "TortoiseModel",
    "Field", "Table", "Model", "ModelRegistry",
    "create_model", "register_model", "get_model_registry",
    
    # Repository Pattern
    "Repository", "BaseRepository", "CRUDRepository", "RepositoryConfig", "RepositoryRegistry",
    "repository", "get_repository", "create_repository", "get_repository_registry",
    
    # Query System
    "Query", "QueryBuilder", "AdvancedQueryBuilder", "TransactionalQueryBuilder",
    "Filter", "Sort", "Pagination", "Operator", "SortOrder",
    "Q", "build_query", "execute_query",
    # 필터 편의 함수들
    "eq", "ne", "lt", "le", "gt", "ge", "in_", "nin", "like", "ilike", "regex",
    "is_null", "is_not_null", "between", "contains",
    
    # Migration
    "Migration", "SQLMigration", "PythonMigration", "MigrationStatus", "MigrationInfo",
    "MigrationManager", "AlembicMigrationManager",
    "create_migration", "run_migrations", "rollback_migration",
    "get_migration_manager", "set_migration_manager",
    
    # Session Management
    "DatabaseSession", "SQLAlchemySession", "TortoiseSession", "DatabaseTransaction",
    "SessionConfig", "SessionManager", "session_scope", "transaction_scope",
    "get_session", "create_session", "get_session_manager", "get_current_transaction",
    "with_session", "with_transaction"
]

__version__ = "4.1.0"
__db_features__ = [
    "SQLAlchemy/Tortoise ORM 통합",
    "자동 연결 풀링",
    "트랜잭션 관리 통합",
    "Repository 패턴",
    "Query Builder",
    "Migration 시스템",
    "Cloud SQL 최적화",
    "세션 관리",
    "Context Manager 지원",
    "컨텍스트 변수 지원",
    "배치 처리",
    "페이지네이션"
]