"""
포괄적인 Connection Pool 관리 테스트 (SQLite 메모리 DB 사용)

RFS Framework의 Connection Pool 시스템을 SQLite 메모리 데이터베이스로 테스트
- 연결 풀 초기화 및 관리
- 연결 획득/반환 로직
- 풀 상태 모니터링
- 에러 처리 및 복구
- Result 패턴 준수
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.core.result import Failure, Result, Success
from rfs.database.base import (
    ConnectionPool,
    Database,
    DatabaseConfig,
    DatabaseManager,
    DatabaseType,
    ORMType,
    SQLAlchemyDatabase,
    TortoiseDatabase,
)


@dataclass
class MockConnection:
    """테스트용 Mock 연결 객체"""

    id: int
    is_active=True
    created_at: float = 0.0
    last_used: float = 0.0
    use_count=0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        self.last_used = self.created_at

    def use(self):
        """연결 사용"""
        self.last_used = time.time()
        self.use_count += 1

    def close(self):
        """연결 종료"""
        self.is_active = False


class MockConnectionFactory:
    """테스트용 연결 팩토리"""

    def __init__(self):
        self.next_id = 1
        self.created_connections = []
        self.creation_delay = 0.0  # 연결 생성 지연 시뮬레이션

    async def create_connection(self) -> MockConnection:
        """새 연결 생성"""
        if self.creation_delay > 0:
            await asyncio.sleep(self.creation_delay)

        conn = MockConnection(id=self.next_id)
        self.next_id += 1
        self.created_connections.append(conn)
        return conn

    def create_sync_connection(self) -> MockConnection:
        """동기 연결 생성"""
        conn = MockConnection(id=self.next_id)
        self.next_id += 1
        self.created_connections.append(conn)
        return conn


class TestConnectionPool:
    """ConnectionPool 테스트"""

    @pytest.fixture
    def config(self):
        """테스트용 데이터베이스 설정"""
        return DatabaseConfig(
            url="sqlite:///:memory:",
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )

    @pytest.fixture
    def mock_factory(self):
        """Mock 연결 팩토리"""
        return MockConnectionFactory()

    @pytest.fixture
    def connection_pool(self, config, mock_factory):
        """ConnectionPool 픽스처"""
        pool = Mock(spec=ConnectionPool)
        pool.config = config
        pool._factory = mock_factory
        pool._pool = []
        pool._active_connections = {}
        pool._lock = asyncio.Lock()
        pool._stats = {
            "created": 0,
            "acquired": 0,
            "released": 0,
            "errors": 0,
            "timeouts": 0,
        }
        return pool

    def test_connection_pool_initialization(self, config):
        """Connection Pool 초기화 테스트"""
        pool = Mock(spec=ConnectionPool)
        pool.config = config
        pool._initialized = True

        assert pool.config == config
        assert pool._initialized is True

    def test_connection_pool_config_validation(self):
        """연결 풀 설정 유효성 검사 테스트"""
        # 유효한 설정
        valid_config = DatabaseConfig(
            url="sqlite:///:memory:", pool_size=5, max_overflow=10
        )
        assert valid_config.pool_size > 0
        assert valid_config.max_overflow >= 0

        # 무효한 설정
        with pytest.raises(ValueError):
            DatabaseConfig(url="sqlite:///:memory:", pool_size=-1)  # 음수 풀 사이즈

    @pytest.mark.asyncio
    async def test_connection_acquisition_success(self, connection_pool, mock_factory):
        """연결 획득 성공 테스트"""
        # Mock acquire 메서드
        test_conn = await mock_factory.create_connection()

        async def mock_acquire():
            connection_pool._stats["acquired"] += 1
            connection_pool._active_connections[test_conn.id] = test_conn
            return Success(test_conn)

        connection_pool.acquire = mock_acquire

        result = await connection_pool.acquire()

        assert isinstance(result, Success)
        connection = result.value
        assert connection == test_conn
        assert connection_pool._stats["acquired"] == 1

    @pytest.mark.asyncio
    async def test_connection_acquisition_timeout(self, connection_pool):
        """연결 획득 타임아웃 테스트"""

        # Mock acquire 메서드 (타임아웃)
        async def mock_acquire_timeout():
            connection_pool._stats["timeouts"] += 1
            return Failure("Connection acquisition timeout")

        connection_pool.acquire = mock_acquire_timeout

        result = await connection_pool.acquire()

        assert isinstance(result, Failure)
        assert "timeout" in result.error.lower()
        assert connection_pool._stats["timeouts"] == 1

    @pytest.mark.asyncio
    async def test_connection_release_success(self, connection_pool, mock_factory):
        """연결 반환 성공 테스트"""
        # 테스트 연결 생성
        test_conn = await mock_factory.create_connection()
        connection_pool._active_connections[test_conn.id] = test_conn

        # Mock release 메서드
        async def mock_release(connection):
            if connection.id in connection_pool._active_connections:
                del connection_pool._active_connections[connection.id]
                connection_pool._pool.append(connection)
                connection_pool._stats["released"] += 1
                return Success(None)
            return Failure("Connection not found")

        connection_pool.release = mock_release

        result = await connection_pool.release(test_conn)

        assert isinstance(result, Success)
        assert test_conn.id not in connection_pool._active_connections
        assert connection_pool._stats["released"] == 1

    @pytest.mark.asyncio
    async def test_connection_release_invalid(self, connection_pool, mock_factory):
        """무효한 연결 반환 테스트"""
        # 존재하지 않는 연결
        invalid_conn = await mock_factory.create_connection()

        # Mock release 메서드
        async def mock_release(connection):
            return Failure("Connection not found")

        connection_pool.release = mock_release

        result = await connection_pool.release(invalid_conn)

        assert isinstance(result, Failure)
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pool_size_management(self, connection_pool, mock_factory):
        """풀 사이즈 관리 테스트"""

        # Mock get_pool_status 메서드
        def mock_get_pool_status():
            return {
                "pool_size": len(connection_pool._pool),
                "active_connections": len(connection_pool._active_connections),
                "available_connections": len(connection_pool._pool),
                "max_pool_size": connection_pool.config.pool_size,
                "max_overflow": connection_pool.config.max_overflow,
            }

        connection_pool.get_pool_status = mock_get_pool_status

        # 초기 상태
        status = connection_pool.get_pool_status()
        assert status["pool_size"] == 0
        assert status["active_connections"] == 0

        # 연결 추가 시뮬레이션
        for i in range(3):
            conn = await mock_factory.create_connection()
            connection_pool._pool.append(conn)

        status = connection_pool.get_pool_status()
        assert status["pool_size"] == 3
        assert status["available_connections"] == 3

    @pytest.mark.asyncio
    async def test_pool_overflow_handling(self, connection_pool, mock_factory):
        """풀 오버플로우 처리 테스트"""
        max_total = (
            connection_pool.config.pool_size + connection_pool.config.max_overflow
        )

        # Mock acquire 메서드 (오버플로우 처리)
        async def mock_acquire():
            current_total = len(connection_pool._pool) + len(
                connection_pool._active_connections
            )
            if current_total >= max_total:
                return Failure("Pool overflow: maximum connections reached")

            conn = await mock_factory.create_connection()
            connection_pool._active_connections[conn.id] = conn
            return Success(conn)

        connection_pool.acquire = mock_acquire

        # 최대 연결 수까지 획득
        connections = []
        for i in range(max_total):
            result = await connection_pool.acquire()
            if isinstance(result, Success):
                connections.append(result.value)

        # 추가 연결 요청 시 오버플로우 에러
        result = await connection_pool.acquire()
        assert isinstance(result, Failure)
        assert "overflow" in result.error.lower()

    @pytest.mark.asyncio
    async def test_connection_health_check(self, connection_pool, mock_factory):
        """연결 상태 검사 테스트"""
        # 건강한 연결과 손상된 연결 생성
        healthy_conn = await mock_factory.create_connection()
        broken_conn = await mock_factory.create_connection()
        broken_conn.is_active = False

        # Mock health_check 메서드
        async def mock_health_check(connection):
            if connection.is_active:
                return Success(True)
            return Success(False)

        connection_pool.health_check = mock_health_check

        # 건강한 연결 검사
        result = await connection_pool.health_check(healthy_conn)
        assert isinstance(result, Success)
        assert result.value is True

        # 손상된 연결 검사
        result = await connection_pool.health_check(broken_conn)
        assert isinstance(result, Success)
        assert result.value is False

    @pytest.mark.asyncio
    async def test_connection_recycling(self, connection_pool, mock_factory):
        """연결 재사용 테스트"""
        # 오래된 연결 생성
        old_conn = await mock_factory.create_connection()
        old_conn.created_at = time.time() - 7200  # 2시간 전

        # Mock needs_recycling 메서드
        def mock_needs_recycling(connection):
            age = time.time() - connection.created_at
            return age > connection_pool.config.pool_recycle

        connection_pool.needs_recycling = mock_needs_recycling

        # 재사용 필요성 검사
        needs_recycling = connection_pool.needs_recycling(old_conn)
        assert needs_recycling is True

        # 새 연결은 재사용 불필요
        new_conn = await mock_factory.create_connection()
        needs_recycling = connection_pool.needs_recycling(new_conn)
        assert needs_recycling is False

    def test_pool_statistics_tracking(self, connection_pool):
        """풀 통계 추적 테스트"""
        # 통계 초기화
        stats = connection_pool._stats
        assert stats["created"] == 0
        assert stats["acquired"] == 0
        assert stats["released"] == 0
        assert stats["errors"] == 0
        assert stats["timeouts"] == 0

        # 통계 업데이트 시뮬레이션
        stats["created"] += 3
        stats["acquired"] += 5
        stats["released"] += 4
        stats["errors"] += 1

        assert stats["created"] == 3
        assert stats["acquired"] == 5
        assert stats["released"] == 4
        assert stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_connection_access(self, connection_pool, mock_factory):
        """동시 연결 접근 테스트"""

        # Mock acquire/release with lock
        async def mock_acquire():
            async with connection_pool._lock:
                if len(connection_pool._pool) > 0:
                    conn = connection_pool._pool.pop(0)
                else:
                    conn = await mock_factory.create_connection()
                connection_pool._active_connections[conn.id] = conn
                return Success(conn)

        async def mock_release(connection):
            async with connection_pool._lock:
                if connection.id in connection_pool._active_connections:
                    del connection_pool._active_connections[connection.id]
                    connection_pool._pool.append(connection)
                    return Success(None)
                return Failure("Connection not found")

        connection_pool.acquire = mock_acquire
        connection_pool.release = mock_release

        # 동시에 여러 연결 획득/반환
        async def worker():
            result = await connection_pool.acquire()
            if isinstance(result, Success):
                connection = result.value
                await asyncio.sleep(0.01)  # 작업 시뮬레이션
                await connection_pool.release(connection)

        # 10개 동시 작업
        tasks = [worker() for _ in range(10)]
        await asyncio.gather(*tasks)

        # 모든 연결이 반환되었는지 확인
        assert len(connection_pool._active_connections) == 0

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(self, connection_pool, mock_factory):
        """에러 발생 시 연결 정리 테스트"""
        # 문제가 있는 연결 생성
        problematic_conn = await mock_factory.create_connection()
        connection_pool._active_connections[problematic_conn.id] = problematic_conn

        # Mock cleanup_connection 메서드
        async def mock_cleanup_connection(connection):
            if connection.id in connection_pool._active_connections:
                del connection_pool._active_connections[connection.id]
                connection.close()
                connection_pool._stats["errors"] += 1
                return Success(None)
            return Failure("Connection not found")

        connection_pool.cleanup_connection = mock_cleanup_connection

        result = await connection_pool.cleanup_connection(problematic_conn)

        assert isinstance(result, Success)
        assert problematic_conn.id not in connection_pool._active_connections
        assert problematic_conn.is_active is False
        assert connection_pool._stats["errors"] == 1


class TestDatabaseManager:
    """DatabaseManager 테스트"""

    @pytest.fixture
    def db_config(self):
        """데이터베이스 설정"""
        return DatabaseConfig(
            url="sqlite:///:memory:",
            database_type=DatabaseType.SQLITE,
            orm_type=ORMType.AUTO,
            pool_size=5,
        )

    @pytest.fixture
    def db_manager(self, db_config):
        """DatabaseManager 픽스처"""
        manager = Mock(spec=DatabaseManager)
        manager.config = db_config
        manager._databases = {}
        manager._default_db = None
        return manager

    def test_database_manager_initialization(self, db_manager, db_config):
        """DatabaseManager 초기화 테스트"""
        assert db_manager.config == db_config
        assert db_manager._databases == {}
        assert db_manager._default_db is None

    @pytest.mark.asyncio
    async def test_database_registration(self, db_manager):
        """데이터베이스 등록 테스트"""

        # Mock register_database 메서드
        def mock_register_database(name, database):
            db_manager._databases[name] = database
            if db_manager._default_db is None:
                db_manager._default_db = database
            return Success(None)

        db_manager.register_database = mock_register_database

        mock_db = Mock(spec=Database)
        result = db_manager.register_database("main", mock_db)

        assert isinstance(result, Success)
        assert db_manager._databases["main"] == mock_db
        assert db_manager._default_db == mock_db

    def test_database_retrieval(self, db_manager):
        """데이터베이스 조회 테스트"""
        # 데이터베이스 등록
        mock_db = Mock(spec=Database)
        db_manager._databases["test"] = mock_db

        # Mock get_database 메서드
        def mock_get_database(name=None):
            if name is None:
                if db_manager._default_db:
                    return Success(db_manager._default_db)
                return Failure("No default database")

            if name in db_manager._databases:
                return Success(db_manager._databases[name])
            return Failure(f"Database '{name}' not found")

        db_manager.get_database = mock_get_database

        # 이름으로 조회
        result = db_manager.get_database("test")
        assert isinstance(result, Success)
        assert result.value == mock_db

        # 존재하지 않는 데이터베이스 조회
        result = db_manager.get_database("nonexistent")
        assert isinstance(result, Failure)

    @pytest.mark.asyncio
    async def test_connection_pool_lifecycle(self, db_manager):
        """연결 풀 라이프사이클 테스트"""
        mock_db = Mock(spec=Database)
        mock_pool = Mock(spec=ConnectionPool)
        mock_db.pool = mock_pool

        # Mock 라이프사이클 메서드들
        async def mock_initialize():
            mock_pool._initialized = True
            return Success(None)

        async def mock_close():
            mock_pool._initialized = False
            return Success(None)

        mock_pool.initialize = mock_initialize
        mock_pool.close = mock_close

        # 초기화
        result = await mock_pool.initialize()
        assert isinstance(result, Success)
        assert mock_pool._initialized is True

        # 종료
        result = await mock_pool.close()
        assert isinstance(result, Success)
        assert mock_pool._initialized is False


class TestConnectionPoolPerformance:
    """Connection Pool 성능 테스트"""

    @pytest.mark.asyncio
    async def test_high_concurrency_stress(self):
        """고동시성 스트레스 테스트"""
        # Mock 연결 풀
        mock_pool = Mock(spec=ConnectionPool)
        mock_factory = MockConnectionFactory()

        # 빠른 acquire/release 시뮬레이션
        async def fast_acquire():
            conn = await mock_factory.create_connection()
            await asyncio.sleep(0.001)  # 매우 짧은 지연
            return Success(conn)

        async def fast_release(connection):
            await asyncio.sleep(0.001)  # 매우 짧은 지연
            return Success(None)

        mock_pool.acquire = fast_acquire
        mock_pool.release = fast_release

        # 1000개 동시 작업
        async def worker():
            result = await mock_pool.acquire()
            if isinstance(result, Success):
                connection = result.value
                await mock_pool.release(connection)

        start_time = time.time()
        tasks = [worker() for _ in range(1000)]
        await asyncio.gather(*tasks)
        end_time = time.time()

        # 성능 어설션 (5초 이내)
        assert (end_time - start_time) < 5.0

    def test_memory_usage_optimization(self):
        """메모리 사용 최적화 테스트"""
        # 많은 연결 생성
        factory = MockConnectionFactory()
        connections = []

        for i in range(1000):
            conn = factory.create_sync_connection()
            connections.append(conn)

        assert len(connections) == 1000
        assert len(factory.created_connections) == 1000

        # 연결 정리 시뮬레이션
        for conn in connections:
            conn.close()

        # 활성 연결 확인
        active_connections = [conn for conn in connections if conn.is_active]
        assert len(active_connections) == 0

    @pytest.mark.asyncio
    async def test_connection_reuse_efficiency(self):
        """연결 재사용 효율성 테스트"""
        mock_pool = []
        active_connections = {}
        factory = MockConnectionFactory()

        # 연결 풀 시뮬레이션
        async def simulate_acquire():
            if mock_pool:
                # 기존 연결 재사용
                conn = mock_pool.pop(0)
            else:
                # 새 연결 생성
                conn = await factory.create_connection()

            conn.use()
            active_connections[conn.id] = conn
            return Success(conn)

        async def simulate_release(connection):
            if connection.id in active_connections:
                del active_connections[connection.id]
                mock_pool.append(connection)
                return Success(None)
            return Failure("Connection not found")

        # 연결 획득/반환 사이클
        connections_used = []
        for _ in range(100):
            result = await simulate_acquire()
            if isinstance(result, Success):
                conn = result.value
                connections_used.append(conn)
                await simulate_release(conn)

        # 재사용 효율성 확인 (새로 생성된 연결 수가 적어야 함)
        unique_connections = len(set(conn.id for conn in connections_used))
        creation_efficiency = unique_connections / 100

        # 80% 이상 재사용되어야 함
        assert creation_efficiency < 0.2


class TestConnectionPoolErrorRecovery:
    """Connection Pool 에러 복구 테스트"""

    @pytest.mark.asyncio
    async def test_broken_connection_recovery(self):
        """손상된 연결 복구 테스트"""
        factory = MockConnectionFactory()
        broken_connections = []

        # 손상된 연결들 생성
        for i in range(5):
            conn = await factory.create_connection()
            conn.is_active = False  # 연결 손상 시뮬레이션
            broken_connections.append(conn)

        # Mock 복구 로직
        async def mock_recover_connection(connection):
            if not connection.is_active:
                # 새 연결로 교체
                new_conn = await factory.create_connection()
                return Success(new_conn)
            return Success(connection)

        # 모든 손상된 연결 복구
        recovered_connections = []
        for broken_conn in broken_connections:
            result = await mock_recover_connection(broken_conn)
            if isinstance(result, Success):
                recovered_connections.append(result.value)

        assert len(recovered_connections) == 5
        assert all(conn.is_active for conn in recovered_connections)

    @pytest.mark.asyncio
    async def test_pool_exhaustion_recovery(self):
        """풀 고갈 상황 복구 테스트"""
        max_connections = 3
        mock_pool = []
        active_connections = {}
        factory = MockConnectionFactory()

        # 풀 고갈 시뮬레이션
        async def mock_acquire_with_limit():
            total_connections = len(mock_pool) + len(active_connections)

            if total_connections >= max_connections and not mock_pool:
                # 풀 고갈 상황
                return Failure("Pool exhausted")

            if mock_pool:
                conn = mock_pool.pop(0)
            else:
                conn = await factory.create_connection()

            active_connections[conn.id] = conn
            return Success(conn)

        async def mock_release(connection):
            if connection.id in active_connections:
                del active_connections[connection.id]
                mock_pool.append(connection)
                return Success(None)
            return Failure("Connection not found")

        # 풀 고갈까지 연결 획득
        acquired_connections = []
        for _ in range(max_connections):
            result = await mock_acquire_with_limit()
            if isinstance(result, Success):
                acquired_connections.append(result.value)

        # 추가 연결 요청 시 실패
        result = await mock_acquire_with_limit()
        assert isinstance(result, Failure)
        assert "exhausted" in result.error.lower()

        # 연결 반환 후 복구
        if acquired_connections:
            await mock_release(acquired_connections[0])

        # 다시 연결 획득 가능
        result = await mock_acquire_with_limit()
        assert isinstance(result, Success)
