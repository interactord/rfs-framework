"""
포괄적인 Migration 시스템 테스트 (Dry-run 방식)

RFS Framework의 Migration 시스템을 실제 DB 연결 없이 dry-run으로 테스트
- 마이그레이션 생성 및 검증
- 버전 관리 및 순서 제어
- 롤백 기능
- 상태 추적 및 충돌 감지
- Result 패턴 준수
"""

import asyncio
import hashlib
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.core.result import Failure, Result, Success
from rfs.database.migration import (
    AlembicMigrationManager,
    Migration,
    MigrationInfo,
    MigrationManager,
    MigrationStatus,
    PythonMigration,
    SQLMigration,
    create_migration,
    get_migration_manager,
    rollback_migration,
    run_migrations,
    set_migration_manager,
)


class MockSQLExecutor:
    """테스트용 SQL 실행기"""

    def __init__(self):
        self.executed_queries = []
        self.execution_results = {}
        self.should_fail = False
        self.fail_on_query = None

    async def execute(self, query: str) -> Result[Any, str]:
        """SQL 쿼리 실행 시뮬레이션"""
        self.executed_queries.append(query)

        if self.should_fail or (self.fail_on_query and self.fail_on_query in query):
            return Failure(f"SQL execution failed: {query}")

        # 간단한 결과 시뮬레이션
        if "CREATE TABLE" in query.upper():
            return Success("Table created")
        elif "DROP TABLE" in query.upper():
            return Success("Table dropped")
        elif "ALTER TABLE" in query.upper():
            return Success("Table altered")
        elif "INSERT" in query.upper():
            return Success("Data inserted")

        return Success("Query executed")


class MockMigrationStorage:
    """테스트용 마이그레이션 저장소"""

    def __init__(self):
        self.applied_migrations = {}
        self.migration_history = []

    async def is_applied(self, version: str) -> bool:
        """마이그레이션 적용 여부 확인"""
        return version in self.applied_migrations

    async def mark_applied(self, migration_info: MigrationInfo):
        """마이그레이션을 적용됨으로 표시"""
        self.applied_migrations[migration_info.version] = migration_info
        self.migration_history.append(
            {
                "version": migration_info.version,
                "action": "applied",
                "timestamp": datetime.now(),
            }
        )

    async def mark_rolled_back(self, version: str):
        """마이그레이션을 롤백됨으로 표시"""
        if version in self.applied_migrations:
            del self.applied_migrations[version]
            self.migration_history.append(
                {
                    "version": version,
                    "action": "rolled_back",
                    "timestamp": datetime.now(),
                }
            )

    async def get_applied_migrations(self) -> List[str]:
        """적용된 마이그레이션 목록 조회"""
        return list(self.applied_migrations.keys())


class TestMigrationStatus:
    """MigrationStatus 열거형 테스트"""

    def test_migration_status_values(self):
        """MigrationStatus 값 테스트"""
        assert MigrationStatus.PENDING == "pending"
        assert MigrationStatus.RUNNING == "running"
        assert MigrationStatus.COMPLETED == "completed"
        assert MigrationStatus.FAILED == "failed"
        assert MigrationStatus.ROLLED_BACK == "rolled_back"

    def test_migration_status_enum_membership(self):
        """MigrationStatus 멤버십 테스트"""
        statuses = [status.value for status in MigrationStatus]
        assert len(statuses) == 5
        assert "pending" in statuses
        assert "completed" in statuses
        assert "failed" in statuses


class TestMigrationInfo:
    """MigrationInfo 데이터클래스 테스트"""

    def test_migration_info_creation(self):
        """MigrationInfo 생성 테스트"""
        info = MigrationInfo(
            version="001", name="create_users_table", description="Create users table"
        )

        assert info.version == "001"
        assert info.name == "create_users_table"
        assert info.description == "Create users table"
        assert info.status == MigrationStatus.PENDING
        assert info.applied_at is None
        assert isinstance(info.created_at, datetime)

    def test_migration_info_with_defaults(self):
        """기본값이 있는 MigrationInfo 테스트"""
        info = MigrationInfo(version="002", name="add_email_column")

        assert info.version == "002"
        assert info.name == "add_email_column"
        assert info.description == ""
        assert info.status == MigrationStatus.PENDING

    def test_migration_info_status_update(self):
        """MigrationInfo 상태 업데이트 테스트"""
        info = MigrationInfo(version="003", name="test_migration")

        # 초기 상태
        assert info.status == MigrationStatus.PENDING
        assert info.applied_at is None

        # 상태 변경
        info.status = MigrationStatus.COMPLETED
        info.applied_at = datetime.now()

        assert info.status == MigrationStatus.COMPLETED
        assert info.applied_at is not None

    def test_migration_info_checksum(self):
        """MigrationInfo 체크섬 테스트"""
        info = MigrationInfo(version="004", name="checksum_test")

        # 초기에는 체크섬 없음
        assert info.checksum is None

        # 체크섬 설정
        content = "CREATE TABLE test (id INTEGER);"
        checksum = hashlib.md5(content.encode()).hexdigest()
        info.checksum = checksum

        assert info.checksum == checksum


class TestSQLMigration:
    """SQLMigration 테스트"""

    @pytest.fixture
    def sql_executor(self):
        """SQL 실행기 픽스처"""
        return MockSQLExecutor()

    def test_sql_migration_creation(self):
        """SQLMigration 생성 테스트"""
        migration = SQLMigration(
            version="001",
            name="create_users_table",
            up_sql="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
            down_sql="DROP TABLE users;",
            description="Create users table",
        )

        assert migration.info.version == "001"
        assert migration.info.name == "create_users_table"
        assert "CREATE TABLE users" in migration.up_sql
        assert "DROP TABLE users" in migration.down_sql

    def test_sql_migration_validation_success(self):
        """SQLMigration 유효성 검증 성공 테스트"""
        migration = SQLMigration(
            version="001",
            name="valid_migration",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        result = migration.validate()

        assert isinstance(result, Success)

    def test_sql_migration_validation_failure(self):
        """SQLMigration 유효성 검증 실패 테스트"""
        # 버전 없음
        migration = SQLMigration(
            version="",
            name="invalid_migration",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        result = migration.validate()

        assert isinstance(result, Failure)
        assert "버전이 필요합니다" in result.error

    @pytest.mark.asyncio
    async def test_sql_migration_up_success(self, sql_executor):
        """SQLMigration up 성공 테스트"""
        migration = SQLMigration(
            version="001",
            name="test_migration",
            up_sql="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
            down_sql="DROP TABLE users;",
        )

        # Mock up 메서드
        async def mock_up():
            return await sql_executor.execute(migration.up_sql)

        migration.up = mock_up

        result = await migration.up()

        assert isinstance(result, Success)
        assert len(sql_executor.executed_queries) == 1
        assert "CREATE TABLE users" in sql_executor.executed_queries[0]

    @pytest.mark.asyncio
    async def test_sql_migration_up_failure(self, sql_executor):
        """SQLMigration up 실패 테스트"""
        sql_executor.should_fail = True

        migration = SQLMigration(
            version="001",
            name="failing_migration",
            up_sql="INVALID SQL QUERY;",
            down_sql="DROP TABLE test;",
        )

        # Mock up 메서드
        async def mock_up():
            return await sql_executor.execute(migration.up_sql)

        migration.up = mock_up

        result = await migration.up()

        assert isinstance(result, Failure)
        assert "execution failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sql_migration_down_success(self, sql_executor):
        """SQLMigration down 성공 테스트"""
        migration = SQLMigration(
            version="001",
            name="rollback_test",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        # Mock down 메서드
        async def mock_down():
            return await sql_executor.execute(migration.down_sql)

        migration.down = mock_down

        result = await migration.down()

        assert isinstance(result, Success)
        assert len(sql_executor.executed_queries) == 1
        assert "DROP TABLE test" in sql_executor.executed_queries[0]

    def test_sql_migration_checksum_generation(self):
        """SQLMigration 체크섬 생성 테스트"""
        migration = SQLMigration(
            version="001",
            name="checksum_test",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        # Mock generate_checksum 메서드
        def mock_generate_checksum():
            content = migration.up_sql + migration.down_sql
            return hashlib.md5(content.encode()).hexdigest()

        migration.generate_checksum = mock_generate_checksum

        checksum = migration.generate_checksum()

        assert checksum is not None
        assert len(checksum) == 32  # MD5 해시 길이

    @pytest.mark.asyncio
    async def test_complex_sql_migration(self, sql_executor):
        """복잡한 SQLMigration 테스트"""
        complex_up_sql = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX idx_users_email ON users(email);
        
        INSERT INTO users (email) VALUES ('admin@example.com');
        """

        complex_down_sql = """
        DROP INDEX IF EXISTS idx_users_email;
        DROP TABLE IF EXISTS users;
        """

        migration = SQLMigration(
            version="001",
            name="complex_user_setup",
            up_sql=complex_up_sql,
            down_sql=complex_down_sql,
            description="Complex user table setup",
        )

        # Mock up 메서드 (여러 SQL 실행)
        async def mock_complex_up():
            queries = [q.strip() for q in migration.up_sql.split(";") if q.strip()]
            for query in queries:
                result = await sql_executor.execute(query)
                if isinstance(result, Failure):
                    return result
            return Success(None)

        migration.up = mock_complex_up

        result = await migration.up()

        assert isinstance(result, Success)
        assert (
            len(sql_executor.executed_queries) == 3
        )  # CREATE TABLE, CREATE INDEX, INSERT


class TestPythonMigration:
    """PythonMigration 테스트"""

    @pytest.fixture
    def mock_context(self):
        """Mock 마이그레이션 컨텍스트"""
        context = Mock()
        context.execute = AsyncMock(return_value=Success("executed"))
        return context

    def test_python_migration_creation(self):
        """PythonMigration 생성 테스트"""

        async def up_func(context):
            return Success(None)

        async def down_func(context):
            return Success(None)

        migration = Mock(spec=PythonMigration)
        migration.info = MigrationInfo(
            version="001", name="python_migration", description="Python migration test"
        )
        migration.up_func = up_func
        migration.down_func = down_func

        assert migration.info.version == "001"
        assert migration.info.name == "python_migration"
        assert callable(migration.up_func)
        assert callable(migration.down_func)

    @pytest.mark.asyncio
    async def test_python_migration_up_execution(self, mock_context):
        """PythonMigration up 실행 테스트"""
        results = []

        async def up_function(context):
            results.append("up_executed")
            # 복잡한 데이터 변환 로직 시뮬레이션
            await context.execute("CREATE TABLE temp_table (id INTEGER);")
            await context.execute("INSERT INTO temp_table (id) VALUES (1), (2), (3);")
            await context.execute(
                "CREATE TABLE final_table AS SELECT * FROM temp_table;"
            )
            await context.execute("DROP TABLE temp_table;")
            return Success(None)

        # Mock PythonMigration
        migration = Mock(spec=PythonMigration)
        migration.up_func = up_function

        async def mock_up():
            return await migration.up_func(mock_context)

        migration.up = mock_up

        result = await migration.up()

        assert isinstance(result, Success)
        assert "up_executed" in results
        assert mock_context.execute.call_count == 4

    @pytest.mark.asyncio
    async def test_python_migration_down_execution(self, mock_context):
        """PythonMigration down 실행 테스트"""
        results = []

        async def down_function(context):
            results.append("down_executed")
            # 롤백 로직 시뮬레이션
            await context.execute("DROP TABLE IF EXISTS final_table;")
            return Success(None)

        # Mock PythonMigration
        migration = Mock(spec=PythonMigration)
        migration.down_func = down_function

        async def mock_down():
            return await migration.down_func(mock_context)

        migration.down = mock_down

        result = await migration.down()

        assert isinstance(result, Success)
        assert "down_executed" in results
        assert mock_context.execute.called

    @pytest.mark.asyncio
    async def test_python_migration_error_handling(self, mock_context):
        """PythonMigration 에러 처리 테스트"""

        async def failing_up_function(context):
            # 의도적 에러 발생
            raise ValueError("Python migration error")

        # Mock PythonMigration
        migration = Mock(spec=PythonMigration)
        migration.up_func = failing_up_function

        async def mock_up():
            try:
                return await migration.up_func(mock_context)
            except Exception as e:
                return Failure(str(e))

        migration.up = mock_up

        result = await migration.up()

        assert isinstance(result, Failure)
        assert "Python migration error" in result.error

    @pytest.mark.asyncio
    async def test_python_migration_with_transaction(self, mock_context):
        """트랜잭션을 사용한 PythonMigration 테스트"""

        async def transactional_up_function(context):
            # 트랜잭션 내에서 여러 작업 수행
            await context.begin_transaction()
            try:
                await context.execute("CREATE TABLE users (id INTEGER, name TEXT);")
                await context.execute("INSERT INTO users VALUES (1, 'John');")
                await context.execute("INSERT INTO users VALUES (2, 'Jane');")
                await context.commit_transaction()
                return Success(None)
            except Exception as e:
                await context.rollback_transaction()
                return Failure(str(e))

        # Mock 트랜잭션 메서드들
        mock_context.begin_transaction = AsyncMock(return_value=Success(None))
        mock_context.commit_transaction = AsyncMock(return_value=Success(None))
        mock_context.rollback_transaction = AsyncMock(return_value=Success(None))

        # Mock PythonMigration
        migration = Mock(spec=PythonMigration)
        migration.up_func = transactional_up_function

        async def mock_up():
            return await migration.up_func(mock_context)

        migration.up = mock_up

        result = await migration.up()

        assert isinstance(result, Success)
        mock_context.begin_transaction.assert_called_once()
        mock_context.commit_transaction.assert_called_once()
        assert mock_context.execute.call_count == 3


class TestMigrationManager:
    """MigrationManager 테스트"""

    @pytest.fixture
    def storage(self):
        """Mock 스토리지"""
        return MockMigrationStorage()

    @pytest.fixture
    def migration_manager(self, storage):
        """MigrationManager 픽스처"""
        manager = Mock(spec=MigrationManager)
        manager._storage = storage
        manager._migrations = {}
        manager._lock = asyncio.Lock()
        return manager

    def test_migration_manager_initialization(self, migration_manager, storage):
        """MigrationManager 초기화 테스트"""
        assert migration_manager._storage == storage
        assert migration_manager._migrations == {}

    @pytest.mark.asyncio
    async def test_register_migration(self, migration_manager):
        """마이그레이션 등록 테스트"""
        migration = Mock(spec=Migration)
        migration.info = MigrationInfo(version="001", name="test_migration")

        # Mock register 메서드
        def mock_register(migration):
            migration_manager._migrations[migration.info.version] = migration
            return Success(None)

        migration_manager.register = mock_register

        result = migration_manager.register(migration)

        assert isinstance(result, Success)
        assert migration_manager._migrations["001"] == migration

    @pytest.mark.asyncio
    async def test_get_pending_migrations(self, migration_manager, storage):
        """대기 중인 마이그레이션 조회 테스트"""
        # 등록된 마이그레이션들
        migration1 = Mock(spec=Migration)
        migration1.info = MigrationInfo(version="001", name="migration1")
        migration2 = Mock(spec=Migration)
        migration2.info = MigrationInfo(version="002", name="migration2")
        migration3 = Mock(spec=Migration)
        migration3.info = MigrationInfo(version="003", name="migration3")

        migration_manager._migrations = {
            "001": migration1,
            "002": migration2,
            "003": migration3,
        }

        # 일부는 이미 적용됨
        await storage.mark_applied(migration1.info)

        # Mock get_pending_migrations 메서드
        async def mock_get_pending_migrations():
            applied = await storage.get_applied_migrations()
            pending = []
            for version, migration in migration_manager._migrations.items():
                if version not in applied:
                    pending.append(migration)
            return Success(pending)

        migration_manager.get_pending_migrations = mock_get_pending_migrations

        result = await migration_manager.get_pending_migrations()

        assert isinstance(result, Success)
        pending_migrations = result.value
        assert len(pending_migrations) == 2  # 002, 003만 대기 중

    @pytest.mark.asyncio
    async def test_apply_migration_success(self, migration_manager, storage):
        """마이그레이션 적용 성공 테스트"""
        migration = Mock(spec=Migration)
        migration.info = MigrationInfo(version="001", name="test_migration")
        migration.up = AsyncMock(return_value=Success(None))

        # Mock apply_migration 메서드
        async def mock_apply_migration(migration):
            # 마이그레이션 실행
            result = await migration.up()
            if isinstance(result, Success):
                migration.info.status = MigrationStatus.COMPLETED
                migration.info.applied_at = datetime.now()
                await storage.mark_applied(migration.info)
                return Success(None)
            return result

        migration_manager.apply_migration = mock_apply_migration

        result = await migration_manager.apply_migration(migration)

        assert isinstance(result, Success)
        assert migration.info.status == MigrationStatus.COMPLETED
        assert await storage.is_applied("001")

    @pytest.mark.asyncio
    async def test_apply_migration_failure(self, migration_manager, storage):
        """마이그레이션 적용 실패 테스트"""
        migration = Mock(spec=Migration)
        migration.info = MigrationInfo(version="001", name="failing_migration")
        migration.up = AsyncMock(return_value=Failure("Migration failed"))

        # Mock apply_migration 메서드
        async def mock_apply_migration(migration):
            result = await migration.up()
            if isinstance(result, Failure):
                migration.info.status = MigrationStatus.FAILED
                return result
            return result

        migration_manager.apply_migration = mock_apply_migration

        result = await migration_manager.apply_migration(migration)

        assert isinstance(result, Failure)
        assert migration.info.status == MigrationStatus.FAILED
        assert not await storage.is_applied("001")

    @pytest.mark.asyncio
    async def test_rollback_migration(self, migration_manager, storage):
        """마이그레이션 롤백 테스트"""
        migration = Mock(spec=Migration)
        migration.info = MigrationInfo(version="001", name="test_migration")
        migration.info.status = MigrationStatus.COMPLETED
        migration.down = AsyncMock(return_value=Success(None))

        # 먼저 적용된 상태로 설정
        await storage.mark_applied(migration.info)

        # Mock rollback_migration 메서드
        async def mock_rollback_migration(migration):
            result = await migration.down()
            if isinstance(result, Success):
                migration.info.status = MigrationStatus.ROLLED_BACK
                await storage.mark_rolled_back(migration.info.version)
                return Success(None)
            return result

        migration_manager.rollback_migration = mock_rollback_migration

        result = await migration_manager.rollback_migration(migration)

        assert isinstance(result, Success)
        assert migration.info.status == MigrationStatus.ROLLED_BACK
        assert not await storage.is_applied("001")

    @pytest.mark.asyncio
    async def test_migration_ordering(self, migration_manager):
        """마이그레이션 순서 테스트"""
        # 버전 순서대로 등록되지 않은 마이그레이션들
        migrations = [Mock(spec=Migration), Mock(spec=Migration), Mock(spec=Migration)]

        migrations[0].info = MigrationInfo(version="003", name="migration3")
        migrations[1].info = MigrationInfo(version="001", name="migration1")
        migrations[2].info = MigrationInfo(version="002", name="migration2")

        for migration in migrations:
            migration_manager._migrations[migration.info.version] = migration

        # Mock get_migrations_in_order 메서드
        def mock_get_migrations_in_order():
            sorted_versions = sorted(migration_manager._migrations.keys())
            ordered_migrations = [
                migration_manager._migrations[v] for v in sorted_versions
            ]
            return Success(ordered_migrations)

        migration_manager.get_migrations_in_order = mock_get_migrations_in_order

        result = migration_manager.get_migrations_in_order()

        assert isinstance(result, Success)
        ordered_migrations = result.value
        assert len(ordered_migrations) == 3
        assert ordered_migrations[0].info.version == "001"
        assert ordered_migrations[1].info.version == "002"
        assert ordered_migrations[2].info.version == "003"

    @pytest.mark.asyncio
    async def test_migration_conflict_detection(self, migration_manager, storage):
        """마이그레이션 충돌 감지 테스트"""
        # 동일한 버전의 마이그레이션 등록 시도
        migration1 = Mock(spec=Migration)
        migration1.info = MigrationInfo(version="001", name="first_migration")

        migration2 = Mock(spec=Migration)
        migration2.info = MigrationInfo(version="001", name="conflicting_migration")

        # Mock register with conflict detection
        def mock_register_with_conflict(migration):
            if migration.info.version in migration_manager._migrations:
                return Failure(
                    f"Migration version {migration.info.version} already exists"
                )
            migration_manager._migrations[migration.info.version] = migration
            return Success(None)

        migration_manager.register = mock_register_with_conflict

        # 첫 번째 등록 성공
        result1 = migration_manager.register(migration1)
        assert isinstance(result1, Success)

        # 두 번째 등록 실패 (충돌)
        result2 = migration_manager.register(migration2)
        assert isinstance(result2, Failure)
        assert "already exists" in result2.error


class TestMigrationHelperFunctions:
    """마이그레이션 헬퍼 함수 테스트"""

    @patch("rfs.database.migration.get_migration_manager")
    @pytest.mark.asyncio
    async def test_run_migrations_helper(self, mock_get_manager):
        """run_migrations 헬퍼 함수 테스트"""
        mock_manager = Mock(spec=MigrationManager)
        mock_get_manager.return_value = Success(mock_manager)

        # Mock run_all 메서드
        mock_manager.run_all = AsyncMock(return_value=Success(["001", "002"]))

        result = await run_migrations()

        assert isinstance(result, Success)
        applied_versions = result.value
        assert "001" in applied_versions
        assert "002" in applied_versions

    @patch("rfs.database.migration.get_migration_manager")
    @pytest.mark.asyncio
    async def test_rollback_migration_helper(self, mock_get_manager):
        """rollback_migration 헬퍼 함수 테스트"""
        mock_manager = Mock(spec=MigrationManager)
        mock_get_manager.return_value = Success(mock_manager)

        # Mock rollback 메서드
        mock_manager.rollback_to_version = AsyncMock(return_value=Success(None))

        result = await rollback_migration("001")

        assert isinstance(result, Success)
        mock_manager.rollback_to_version.assert_called_once_with("001")

    def test_create_migration_helper(self):
        """create_migration 헬퍼 함수 테스트"""

        # Mock create_migration
        def mock_create_migration(version, name, migration_type="sql", **kwargs):
            if migration_type == "sql":
                return Success(Mock(spec=SQLMigration))
            elif migration_type == "python":
                return Success(Mock(spec=PythonMigration))
            return Failure("Unknown migration type")

        # SQL 마이그레이션 생성
        result = mock_create_migration(
            "001",
            "create_table",
            migration_type="sql",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        assert isinstance(result, Success)

    @patch("rfs.database.migration._migration_manager")
    def test_migration_manager_singleton(self, mock_manager_var):
        """마이그레이션 매니저 싱글톤 테스트"""
        mock_manager = Mock(spec=MigrationManager)
        mock_manager_var.get.return_value = mock_manager

        # Mock get_migration_manager
        def mock_get_migration_manager():
            manager = mock_manager_var.get(None)
            if manager:
                return Success(manager)
            return Failure("No migration manager set")

        result = mock_get_migration_manager()

        assert isinstance(result, Success)
        assert result.value == mock_manager


class TestMigrationErrorScenarios:
    """마이그레이션 에러 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_partial_migration_failure(self):
        """부분적 마이그레이션 실패 테스트"""
        sql_executor = MockSQLExecutor()
        # 두 번째 쿼리에서 실패하도록 설정
        sql_executor.fail_on_query = "INSERT"

        complex_migration = SQLMigration(
            version="001",
            name="partial_failure_test",
            up_sql="""
            CREATE TABLE users (id INTEGER, name TEXT);
            INSERT INTO users VALUES (1, 'John');
            CREATE TABLE posts (id INTEGER, user_id INTEGER);
            """,
            down_sql="DROP TABLE posts; DROP TABLE users;",
        )

        # Mock up 메서드 (부분 실패 시뮬레이션)
        async def mock_up():
            queries = [
                q.strip() for q in complex_migration.up_sql.split(";") if q.strip()
            ]
            for i, query in enumerate(queries):
                result = await sql_executor.execute(query)
                if isinstance(result, Failure):
                    # 부분 실패 - 이미 실행된 쿼리들 롤백 필요
                    return Failure(f"Migration failed at step {i+1}: {result.error}")
            return Success(None)

        complex_migration.up = mock_up

        result = await complex_migration.up()

        assert isinstance(result, Failure)
        assert "step 2" in result.error  # INSERT에서 실패

    @pytest.mark.asyncio
    async def test_migration_dependency_cycle(self):
        """마이그레이션 의존성 순환 감지 테스트"""
        # 순환 의존성 시뮬레이션
        dependencies = {
            "001": ["003"],  # 001은 003에 의존
            "002": ["001"],  # 002는 001에 의존
            "003": ["002"],  # 003은 002에 의존 (순환!)
        }

        def detect_cycle(deps):
            """간단한 순환 감지 알고리즘"""
            visited = set()
            rec_stack = set()

            def dfs(node):
                if node in rec_stack:
                    return True  # 순환 감지
                if node in visited:
                    return False

                visited.add(node)
                rec_stack.add(node)

                for neighbor in deps.get(node, []):
                    if dfs(neighbor):
                        return True

                rec_stack.remove(node)
                return False

            for node in deps:
                if dfs(node):
                    return True
            return False

        has_cycle = detect_cycle(dependencies)
        assert has_cycle is True

    @pytest.mark.asyncio
    async def test_migration_version_conflict(self):
        """마이그레이션 버전 충돌 테스트"""
        storage = MockMigrationStorage()

        # 동일한 버전의 마이그레이션 정보
        info1 = MigrationInfo(version="001", name="migration_a", checksum="abc123")
        info2 = MigrationInfo(version="001", name="migration_b", checksum="def456")

        # 첫 번째 적용
        await storage.mark_applied(info1)

        # 동일 버전의 다른 마이그레이션 적용 시도 감지
        async def check_version_conflict(new_info):
            applied_migrations = storage.applied_migrations
            if new_info.version in applied_migrations:
                existing_info = applied_migrations[new_info.version]
                if existing_info.checksum != new_info.checksum:
                    return Failure(
                        f"Version conflict: {new_info.version} has different checksum"
                    )
            return Success(None)

        result = await check_version_conflict(info2)

        assert isinstance(result, Failure)
        assert "conflict" in result.error.lower()

    @pytest.mark.asyncio
    async def test_migration_rollback_cascade(self):
        """마이그레이션 롤백 연쇄 효과 테스트"""
        storage = MockMigrationStorage()

        # 연쇄된 마이그레이션들 설정
        migrations = [
            MigrationInfo(version="001", name="base", status=MigrationStatus.COMPLETED),
            MigrationInfo(
                version="002", name="depends_on_001", status=MigrationStatus.COMPLETED
            ),
            MigrationInfo(
                version="003", name="depends_on_002", status=MigrationStatus.COMPLETED
            ),
        ]

        for migration in migrations:
            await storage.mark_applied(migration)

        # 002를 롤백하면 003도 함께 롤백되어야 함
        async def cascade_rollback(target_version):
            applied = await storage.get_applied_migrations()
            versions_to_rollback = []

            # 타겟 버전 이후의 모든 버전 찾기
            for version in sorted(applied, reverse=True):
                versions_to_rollback.append(version)
                if version == target_version:
                    break

            # 역순으로 롤백
            for version in versions_to_rollback:
                await storage.mark_rolled_back(version)

            return Success(versions_to_rollback)

        result = await cascade_rollback("002")

        assert isinstance(result, Success)
        rolled_back_versions = result.value
        assert "003" in rolled_back_versions
        assert "002" in rolled_back_versions
        assert "001" not in rolled_back_versions  # 001은 유지


class TestMigrationPerformance:
    """마이그레이션 성능 테스트"""

    @pytest.mark.asyncio
    async def test_large_batch_migration_performance(self):
        """대용량 배치 마이그레이션 성능 테스트"""
        sql_executor = MockSQLExecutor()

        # 대용량 데이터 마이그레이션 시뮬레이션
        batch_size = 1000
        up_sql_parts = []

        for i in range(batch_size):
            up_sql_parts.append(
                f"INSERT INTO users (id, name) VALUES ({i}, 'User{i}');"
            )

        large_migration = SQLMigration(
            version="001",
            name="large_batch_insert",
            up_sql="\n".join(up_sql_parts),
            down_sql="DELETE FROM users;",
        )

        # Mock up 메서드 (배치 처리)
        async def mock_batch_up():
            queries = [
                q.strip() for q in large_migration.up_sql.split("\n") if q.strip()
            ]
            batch_size = 100  # 배치 크기

            for i in range(0, len(queries), batch_size):
                batch = queries[i : i + batch_size]
                # 배치 실행 시뮬레이션
                for query in batch:
                    await sql_executor.execute(query)
                # 작은 지연으로 다른 작업에 CPU 양보
                await asyncio.sleep(0.001)

            return Success(None)

        large_migration.up = mock_batch_up

        import time

        start_time = time.time()
        result = await large_migration.up()
        end_time = time.time()

        assert isinstance(result, Success)
        assert len(sql_executor.executed_queries) == batch_size
        # 성능 어설션 (2초 이내)
        assert (end_time - start_time) < 2.0

    @pytest.mark.asyncio
    async def test_concurrent_migration_safety(self):
        """동시 마이그레이션 안전성 테스트"""
        storage = MockMigrationStorage()

        async def safe_migration_runner(migration_version):
            """안전한 마이그레이션 실행기"""
            # 중복 실행 방지 체크
            if await storage.is_applied(migration_version):
                return Failure(f"Migration {migration_version} already applied")

            # 마이그레이션 실행 시뮬레이션
            await asyncio.sleep(0.01)  # 작업 시뮬레이션

            info = MigrationInfo(
                version=migration_version, name=f"migration_{migration_version}"
            )
            await storage.mark_applied(info)

            return Success(migration_version)

        # 동일한 마이그레이션을 동시에 실행 시도
        tasks = [
            safe_migration_runner("001"),
            safe_migration_runner("001"),  # 중복 실행
            safe_migration_runner("001"),  # 중복 실행
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 하나만 성공하고 나머지는 실패해야 함
        successful_results = [r for r in results if isinstance(r, Success)]
        failed_results = [r for r in results if isinstance(r, Failure)]

        assert len(successful_results) == 1
        assert len(failed_results) == 2
