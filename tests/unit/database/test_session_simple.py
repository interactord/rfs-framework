"""
Simplified unit tests for database session module
"""

import pytest
from unittest.mock import Mock, AsyncMock
from rfs.database.session import SessionConfig, DatabaseSession
from rfs.core.result import Success, Failure


class TestSessionConfig:
    """Test SessionConfig class"""
    
    def test_default_config(self):
        """Test default session configuration"""
        config = SessionConfig()
        
        assert config.auto_commit is True
        assert config.auto_flush is True
        assert config.expire_on_commit is False
        assert config.isolation_level == "READ_COMMITTED"
        assert config.timeout == 30
        assert config.pool_size == 10
        assert config.max_overflow == 20
        
    def test_custom_config(self):
        """Test custom session configuration"""
        config = SessionConfig(
            auto_commit=False,
            auto_flush=False,
            expire_on_commit=True,
            isolation_level="SERIALIZABLE",
            timeout=60,
            pool_size=20,
            max_overflow=40
        )
        
        assert config.auto_commit is False
        assert config.auto_flush is False
        assert config.expire_on_commit is True
        assert config.isolation_level == "SERIALIZABLE"
        assert config.timeout == 60
        assert config.pool_size == 20
        assert config.max_overflow == 40


class TestDatabaseSession:
    """Test DatabaseSession abstract class"""
    
    def test_abstract_class(self):
        """Test that abstract class cannot be instantiated"""
        mock_db = Mock()
        config = SessionConfig()
        
        with pytest.raises(TypeError):
            # Cannot instantiate abstract class
            DatabaseSession(mock_db, config)
            
    def test_concrete_implementation(self):
        """Test concrete session implementation"""
        mock_db = Mock()
        config = SessionConfig()
        
        class ConcreteSession(DatabaseSession):
            async def begin(self):
                return Success(None)
            async def commit(self):
                return Success(None)
            async def rollback(self):
                return Success(None)
            async def close(self):
                return Success(None)
            async def execute(self, query, params=None):
                return Success([])
                
        session = ConcreteSession(mock_db, config)
        assert session.database == mock_db
        assert session.config == config
        assert session.session_id == id(session)


class TestSessionOperations:
    """Test session operations"""
    
    @pytest.fixture
    def session(self):
        """Create test session"""
        mock_db = Mock()
        config = SessionConfig()
        
        class TestSession(DatabaseSession):
            def __init__(self, database, config=None):
                super().__init__(database, config)
                self._active = False
                self._committed = False
                self._rolled_back = False
                
            async def begin(self):
                self._active = True
                return Success(None)
                
            async def commit(self):
                if not self._active:
                    return Failure("Session not active")
                self._committed = True
                self._active = False
                return Success(None)
                
            async def rollback(self):
                if not self._active:
                    return Failure("Session not active")
                self._rolled_back = True
                self._active = False
                return Success(None)
                
            async def close(self):
                self._active = False
                return Success(None)
                
            async def execute(self, query, params=None):
                if not self._active:
                    return Failure("Session not active")
                return Success([{"result": "test"}])
                
        return TestSession(mock_db, config)
    
    @pytest.mark.asyncio
    async def test_begin_session(self, session):
        """Test beginning session"""
        result = await session.begin()
        assert result.is_success()
        assert session._active is True
        
    @pytest.mark.asyncio
    async def test_commit_session(self, session):
        """Test committing session"""
        await session.begin()
        result = await session.commit()
        
        assert result.is_success()
        assert session._committed is True
        assert session._active is False
        
    @pytest.mark.asyncio
    async def test_rollback_session(self, session):
        """Test rolling back session"""
        await session.begin()
        result = await session.rollback()
        
        assert result.is_success()
        assert session._rolled_back is True
        assert session._active is False
        
    @pytest.mark.asyncio
    async def test_execute_query(self, session):
        """Test executing query"""
        await session.begin()
        result = await session.execute("SELECT * FROM test")
        
        assert result.is_success()
        data = result.unwrap()
        assert data == [{"result": "test"}]
        
    @pytest.mark.asyncio
    async def test_execute_without_begin(self, session):
        """Test executing query without beginning session"""
        result = await session.execute("SELECT * FROM test")
        
        assert result.is_failure()
        assert "Session not active" in str(result.unwrap_error())
        
    @pytest.mark.asyncio
    async def test_close_session(self, session):
        """Test closing session"""
        await session.begin()
        result = await session.close()
        
        assert result.is_success()
        assert session._active is False


class TestSessionIntegration:
    """Integration tests for session system"""
    
    @pytest.mark.asyncio
    async def test_session_lifecycle(self):
        """Test complete session lifecycle"""
        mock_db = Mock()
        config = SessionConfig(auto_commit=False)
        
        class LifecycleSession(DatabaseSession):
            def __init__(self, database, config=None):
                super().__init__(database, config)
                self._state = "closed"
                self._queries = []
                
            async def begin(self):
                self._state = "active"
                return Success(None)
                
            async def commit(self):
                if self._state != "active":
                    return Failure("Cannot commit inactive session")
                self._state = "committed"
                return Success(None)
                
            async def rollback(self):
                if self._state != "active":
                    return Failure("Cannot rollback inactive session")
                self._state = "rolled_back"
                return Success(None)
                
            async def close(self):
                self._state = "closed"
                return Success(None)
                
            async def execute(self, query, params=None):
                if self._state != "active":
                    return Failure("Session not active")
                self._queries.append((query, params))
                return Success([{"id": 1, "name": "test"}])
        
        session = LifecycleSession(mock_db, config)
        
        # Begin session
        begin_result = await session.begin()
        assert begin_result.is_success()
        assert session._state == "active"
        
        # Execute queries
        query_result = await session.execute("SELECT * FROM users", {"limit": 10})
        assert query_result.is_success()
        assert len(session._queries) == 1
        
        # Commit session
        commit_result = await session.commit()
        assert commit_result.is_success()
        assert session._state == "committed"
        
        # Close session
        close_result = await session.close()
        assert close_result.is_success()
        assert session._state == "closed"
        
    @pytest.mark.asyncio
    async def test_session_error_handling(self):
        """Test session error handling"""
        mock_db = Mock()
        config = SessionConfig()
        
        class ErrorSession(DatabaseSession):
            async def begin(self):
                return Failure("Connection failed")
            async def commit(self):
                return Failure("Commit failed")
            async def rollback(self):
                return Success(None)
            async def close(self):
                return Success(None)
            async def execute(self, query, params=None):
                return Failure("Query execution failed")
        
        session = ErrorSession(mock_db, config)
        
        # Test begin failure
        begin_result = await session.begin()
        assert begin_result.is_failure()
        assert "Connection failed" in str(begin_result.unwrap_error())
        
        # Test execute failure
        execute_result = await session.execute("SELECT 1")
        assert execute_result.is_failure()
        assert "Query execution failed" in str(execute_result.unwrap_error())
        
        # Test commit failure
        commit_result = await session.commit()
        assert commit_result.is_failure()
        assert "Commit failed" in str(commit_result.unwrap_error())


class TestSessionConfigValidation:
    """Test session configuration validation"""
    
    def test_isolation_levels(self):
        """Test different isolation levels"""
        levels = ["READ_UNCOMMITTED", "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE"]
        
        for level in levels:
            config = SessionConfig(isolation_level=level)
            assert config.isolation_level == level
            
    def test_timeout_validation(self):
        """Test timeout configuration"""
        config = SessionConfig(timeout=120)
        assert config.timeout == 120
        
        # Test edge cases
        config_zero = SessionConfig(timeout=0)
        assert config_zero.timeout == 0
        
    def test_pool_configuration(self):
        """Test pool size configuration"""
        config = SessionConfig(pool_size=50, max_overflow=100)
        assert config.pool_size == 50
        assert config.max_overflow == 100