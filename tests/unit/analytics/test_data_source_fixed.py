"""
RFS Analytics - DataSource 모듈 개선된 테스트

모킹 전략을 개선한 DataSource 모듈 테스트
"""

import asyncio
import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.analytics.data_source import (
    APIDataSource,
    DatabaseDataSource,
    DataQuery,
    DataSchema,
    DataSource,
    DataSourceManager,
    DataSourceType,
    FileDataSource,
    MetricsDataSource,
    create_api_source,
    create_database_source,
    create_file_source,
    create_metrics_source,
    get_data_source_manager,
    register_data_source,
)
from rfs.core.result import Failure, Success


class TestDataSourceType:
    """DataSourceType Enum 테스트"""

    def test_enum_values(self):
        """Enum 값들이 올바른지 테스트"""
        assert DataSourceType.DATABASE.value == "database"
        assert DataSourceType.FILE.value == "file"
        assert DataSourceType.API.value == "api"
        assert DataSourceType.METRICS.value == "metrics"
        assert DataSourceType.MEMORY.value == "memory"


class TestDataQuery:
    """DataQuery 데이터 클래스 테스트"""

    def test_basic_creation(self):
        """기본 DataQuery 생성 테스트"""
        query = DataQuery(query="SELECT * FROM users", parameters={})
        assert query.query == "SELECT * FROM users"
        assert query.parameters == {}
        assert query.limit is None
        assert query.offset is None
        assert query.timeout is None

    def test_full_creation(self):
        """모든 파라미터로 DataQuery 생성 테스트"""
        query = DataQuery(
            query="SELECT * FROM users WHERE id = $1",
            parameters={"id": 123},
            limit=10,
            offset=5,
            timeout=30,
        )
        assert query.query == "SELECT * FROM users WHERE id = $1"
        assert query.parameters == {"id": 123}
        assert query.limit == 10
        assert query.offset == 5
        assert query.timeout == 30


class TestDataSchema:
    """DataSchema 데이터 클래스 테스트"""

    def test_basic_creation(self):
        """기본 DataSchema 생성 테스트"""
        columns = {"id": "integer", "name": "string"}
        schema = DataSchema(columns=columns)
        assert schema.columns == columns
        assert schema.primary_key is None
        assert schema.indexes == []

    def test_post_init_with_none_indexes(self):
        """indexes가 None일 때 post_init 동작 테스트"""
        columns = {"id": "integer"}
        schema = DataSchema.__new__(DataSchema)
        schema.columns = columns
        schema.primary_key = None
        schema.indexes = None
        schema.__post_init__()
        assert schema.indexes == []


class TestDataSourceAbstract:
    """DataSource 추상 클래스 테스트"""

    @pytest.fixture
    def mock_data_source(self):
        """Mock DataSource 생성"""

        class MockDataSource(DataSource):
            async def connect(self):
                return Success(True)

            async def disconnect(self):
                return Success(True)

            async def execute_query(self, query):
                return Success([{"test": "data"}])

            async def get_schema(self):
                return Success(DataSchema(columns={"test": "string"}))

        return MockDataSource("mock_id", "Mock Source", {"test": "config"})

    def test_initialization(self, mock_data_source):
        """DataSource 초기화 테스트"""
        assert mock_data_source.source_id == "mock_id"
        assert mock_data_source.name == "Mock Source"
        assert mock_data_source.config == {"test": "config"}
        assert mock_data_source._schema is None
        assert mock_data_source._connected == False

    def test_is_connected_property(self, mock_data_source):
        """is_connected 프로퍼티 테스트"""
        assert mock_data_source.is_connected == False
        mock_data_source._connected = True
        assert mock_data_source.is_connected == True

    @pytest.mark.asyncio
    async def test_validate_connection_not_connected(self, mock_data_source):
        """연결되지 않은 상태에서 validate_connection 테스트"""
        result = await mock_data_source.validate_connection()
        assert result.is_failure()
        assert result.unwrap_error() == "Data source not connected"

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, mock_data_source):
        """연결 상태에서 validate_connection 성공 테스트"""
        mock_data_source._connected = True
        result = await mock_data_source.validate_connection()
        assert result.is_success()
        assert result.unwrap() == True


class TestDatabaseDataSource:
    """DatabaseDataSource 테스트 (외부 의존성 제거)"""

    @pytest.fixture
    def db_config(self):
        """데이터베이스 설정"""
        return {
            "connection_string": "postgresql://user:pass@localhost:5432/testdb",
            "driver": "postgresql",
        }

    @pytest.fixture
    def db_source(self, db_config):
        """DatabaseDataSource 인스턴스"""
        return DatabaseDataSource("db_test", "Test DB", db_config)

    def test_initialization(self, db_source, db_config):
        """DatabaseDataSource 초기화 테스트"""
        assert db_source.source_id == "db_test"
        assert db_source.name == "Test DB"
        assert db_source.config == db_config
        assert db_source.connection_string == db_config["connection_string"]
        assert db_source.driver == "postgresql"
        assert db_source._connection is None

    @pytest.mark.asyncio
    async def test_connect_postgresql_success(self, db_source):
        """PostgreSQL 연결 성공 테스트"""
        mock_connection = Mock()
        mock_asyncpg = Mock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_connection)

        with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
            result = await db_source.connect()
            assert result.is_success()
            assert result.unwrap() == True
            assert db_source._connected == True
            assert db_source._connection == mock_connection

    @pytest.mark.asyncio
    async def test_connect_unsupported_driver(self):
        """지원하지 않는 드라이버 테스트"""
        config = {"driver": "oracle", "connection_string": "test"}
        db_source = DatabaseDataSource("oracle_test", "Oracle Test", config)

        result = await db_source.connect()
        assert result.is_failure()
        assert result.unwrap_error() == "Unsupported database driver: oracle"
        assert db_source._connected == False

    @pytest.mark.asyncio
    async def test_connect_failure(self, db_source):
        """연결 실패 테스트"""
        mock_asyncpg = Mock()
        mock_asyncpg.connect = AsyncMock(side_effect=Exception("Connection failed"))

        with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
            result = await db_source.connect()
            assert result.is_failure()
            assert (
                "Database connection failed: Connection failed" in result.unwrap_error()
            )
            assert db_source._connected == False

    @pytest.mark.asyncio
    async def test_disconnect_success(self, db_source):
        """연결 해제 성공 테스트"""
        mock_connection = AsyncMock()
        db_source._connection = mock_connection
        db_source._connected = True

        result = await db_source.disconnect()
        assert result.is_success()
        assert result.unwrap() == True
        assert db_source._connected == False
        assert db_source._connection is None
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_not_connected(self, db_source):
        """연결되지 않은 상태에서 쿼리 실행 테스트"""
        query = DataQuery(query="SELECT 1", parameters={})
        result = await db_source.execute_query(query)
        assert result.is_failure()
        assert result.unwrap_error() == "Database not connected"

    @pytest.mark.asyncio
    async def test_execute_query_postgresql(self, db_source):
        """PostgreSQL 쿼리 실행 테스트"""
        mock_connection = AsyncMock()
        mock_row = {"id": 1, "name": "test"}
        mock_connection.fetch.return_value = [mock_row]

        db_source._connection = mock_connection
        db_source._connected = True

        query = DataQuery(query="SELECT * FROM users", parameters={"id": 1})
        result = await db_source.execute_query(query)

        assert result.is_success()
        data = result.unwrap()
        assert len(data) == 1
        assert data[0] == {"id": 1, "name": "test"}
        mock_connection.fetch.assert_called_once_with("SELECT * FROM users", 1)

    def test_get_test_query(self, db_source):
        """테스트 쿼리 테스트"""
        assert db_source._get_test_query() == "SELECT 1"


class TestFileDataSource:
    """FileDataSource 테스트"""

    @pytest.fixture
    def temp_dir(self):
        """임시 디렉토리 생성"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def csv_file(self, temp_dir):
        """CSV 파일 생성"""
        csv_path = temp_dir / "test.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "age"])
            writer.writerow(["1", "John", "30"])
            writer.writerow(["2", "Jane", "25"])
        return csv_path

    @pytest.fixture
    def json_file(self, temp_dir):
        """JSON 파일 생성"""
        json_path = temp_dir / "test.json"
        data = [
            {"id": 1, "name": "John", "age": 30},
            {"id": 2, "name": "Jane", "age": 25},
        ]
        with open(json_path, "w") as f:
            json.dump(data, f)
        return json_path

    def test_initialization(self, csv_file):
        """FileDataSource 초기화 테스트"""
        config = {"file_path": str(csv_file), "file_type": "csv"}
        file_source = FileDataSource("file_test", "Test File", config)

        assert file_source.source_id == "file_test"
        assert file_source.name == "Test File"
        assert file_source.file_path == csv_file
        assert file_source.file_type == "csv"
        assert file_source.encoding == "utf-8"
        assert file_source._data == []

    @pytest.mark.asyncio
    async def test_connect_csv_success(self, csv_file):
        """CSV 파일 연결 성공 테스트"""
        config = {"file_path": str(csv_file), "file_type": "csv"}
        file_source = FileDataSource("csv_test", "CSV Test", config)

        result = await file_source.connect()
        assert result.is_success()
        assert result.unwrap() == True
        assert file_source._connected == True
        assert len(file_source._data) == 2
        assert file_source._data[0] == {"id": "1", "name": "John", "age": "30"}

    @pytest.mark.asyncio
    async def test_connect_json_success(self, json_file):
        """JSON 리스트 파일 연결 성공 테스트"""
        config = {"file_path": str(json_file), "file_type": "json"}
        file_source = FileDataSource("json_test", "JSON Test", config)

        result = await file_source.connect()
        assert result.is_success()
        assert result.unwrap() == True
        assert file_source._connected == True
        assert len(file_source._data) == 2
        assert file_source._data[0] == {"id": 1, "name": "John", "age": 30}

    @pytest.mark.asyncio
    async def test_connect_file_not_found(self, temp_dir):
        """존재하지 않는 파일 연결 테스트"""
        non_existent_file = temp_dir / "nonexistent.csv"
        config = {"file_path": str(non_existent_file), "file_type": "csv"}
        file_source = FileDataSource("missing_test", "Missing Test", config)

        result = await file_source.connect()
        assert result.is_failure()
        assert f"File not found: {non_existent_file}" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_connect_unsupported_file_type(self, csv_file):
        """지원하지 않는 파일 타입 테스트"""
        config = {"file_path": str(csv_file), "file_type": "xml"}
        file_source = FileDataSource("xml_test", "XML Test", config)

        result = await file_source.connect()
        assert result.is_failure()
        assert result.unwrap_error() == "Unsupported file type: xml"

    @pytest.mark.asyncio
    async def test_execute_query_not_connected(self, csv_file):
        """연결되지 않은 상태에서 쿼리 실행 테스트"""
        config = {"file_path": str(csv_file), "file_type": "csv"}
        file_source = FileDataSource("csv_test", "CSV Test", config)

        query = DataQuery(query="SELECT *", parameters={})
        result = await file_source.execute_query(query)
        assert result.is_failure()
        assert result.unwrap_error() == "File not loaded"

    @pytest.mark.asyncio
    async def test_execute_query_with_filter(self, csv_file):
        """필터가 있는 쿼리 실행 테스트"""
        config = {"file_path": str(csv_file), "file_type": "csv"}
        file_source = FileDataSource("csv_test", "CSV Test", config)

        await file_source.connect()
        query = DataQuery(query="SELECT *", parameters={"name": "john"})
        result = await file_source.execute_query(query)

        assert result.is_success()
        data = result.unwrap()
        assert len(data) == 1
        assert data[0]["name"] == "John"

    @pytest.mark.asyncio
    async def test_get_schema_no_data(self, csv_file):
        """데이터가 없을 때 스키마 조회 테스트"""
        config = {"file_path": str(csv_file), "file_type": "csv"}
        file_source = FileDataSource("csv_test", "CSV Test", config)

        result = await file_source.get_schema()
        assert result.is_failure()
        assert result.unwrap_error() == "No data loaded"


class TestAPIDataSource:
    """APIDataSource 테스트 (외부 의존성 제거)"""

    @pytest.fixture
    def api_config(self):
        """API 설정"""
        return {
            "base_url": "https://api.example.com",
            "headers": {"Content-Type": "application/json"},
            "auth": {"type": "basic", "username": "user", "password": "pass"},
        }

    @pytest.fixture
    def api_source(self, api_config):
        """APIDataSource 인스턴스"""
        return APIDataSource("api_test", "Test API", api_config)

    def test_initialization(self, api_source, api_config):
        """APIDataSource 초기화 테스트"""
        assert api_source.source_id == "api_test"
        assert api_source.name == "Test API"
        assert api_source.base_url == "https://api.example.com"
        assert api_source.headers == {"Content-Type": "application/json"}
        assert api_source.auth == {
            "type": "basic",
            "username": "user",
            "password": "pass",
        }
        assert api_source._session is None

    @pytest.mark.asyncio
    async def test_connect_success(self, api_source):
        """API 연결 성공 테스트"""
        mock_session = Mock()
        mock_basic_auth = Mock()

        mock_aiohttp = Mock()
        mock_aiohttp.ClientSession = Mock(return_value=mock_session)
        mock_aiohttp.BasicAuth = Mock(return_value=mock_basic_auth)
        mock_aiohttp.ClientTimeout = Mock(return_value=Mock())

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await api_source.connect()
            assert result.is_success()
            assert result.unwrap() == True
            assert api_source._connected == True
            assert api_source._session == mock_session

    @pytest.mark.asyncio
    async def test_disconnect_success(self, api_source):
        """API 연결 해제 성공 테스트"""
        mock_session = AsyncMock()
        api_source._session = mock_session
        api_source._connected = True

        result = await api_source.disconnect()
        assert result.is_success()
        assert result.unwrap() == True
        assert api_source._connected == False
        assert api_source._session is None
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_not_connected(self, api_source):
        """연결되지 않은 상태에서 쿼리 실행 테스트"""
        query = DataQuery(query="users", parameters={})
        result = await api_source.execute_query(query)
        assert result.is_failure()
        assert result.unwrap_error() == "API not connected"

    def test_get_test_query(self, api_source):
        """테스트 쿼리 테스트"""
        assert api_source._get_test_query() == "health"


class TestMetricsDataSource:
    """MetricsDataSource 테스트 (외부 의존성 제거)"""

    @pytest.fixture
    def metrics_source(self):
        """MetricsDataSource 인스턴스"""
        config = {"metrics": {"cpu": {"interval": "5m"}}}
        return MetricsDataSource("metrics_test", "Test Metrics", config)

    def test_initialization(self, metrics_source):
        """MetricsDataSource 초기화 테스트"""
        assert metrics_source.source_id == "metrics_test"
        assert metrics_source.name == "Test Metrics"
        assert metrics_source._metrics_data == {}

    @pytest.mark.asyncio
    async def test_connect_success(self, metrics_source):
        """메트릭 연결 성공 테스트"""
        mock_collector = Mock()
        mock_metrics_module = Mock()
        mock_metrics_module.get_metrics_collector = Mock(return_value=mock_collector)

        with patch.dict("sys.modules", {"rfs.monitoring.metrics": mock_metrics_module}):
            result = await metrics_source.connect()
            assert result.is_success()
            assert result.unwrap() == True
            assert metrics_source._connected == True
            assert metrics_source.collector == mock_collector

    @pytest.mark.asyncio
    async def test_disconnect_success(self, metrics_source):
        """메트릭 연결 해제 성공 테스트"""
        metrics_source._metrics_data = {"cpu": [{"value": 50}]}
        metrics_source._connected = True

        result = await metrics_source.disconnect()
        assert result.is_success()
        assert result.unwrap() == True
        assert metrics_source._connected == False
        assert metrics_source._metrics_data == {}

    @pytest.mark.asyncio
    async def test_execute_query_not_connected(self, metrics_source):
        """연결되지 않은 상태에서 쿼리 실행 테스트"""
        query = DataQuery(query="cpu_usage", parameters={})
        result = await metrics_source.execute_query(query)
        assert result.is_failure()
        assert result.unwrap_error() == "Metrics not connected"

    def test_parse_time_range_minutes(self, metrics_source):
        """분 단위 시간 범위 파싱 테스트"""
        from datetime import timedelta

        result = metrics_source._parse_time_range("30m")
        assert result == timedelta(minutes=30)

    def test_parse_time_range_hours(self, metrics_source):
        """시간 단위 시간 범위 파싱 테스트"""
        from datetime import timedelta

        result = metrics_source._parse_time_range("2h")
        assert result == timedelta(hours=2)

    def test_parse_time_range_days(self, metrics_source):
        """일 단위 시간 범위 파싱 테스트"""
        from datetime import timedelta

        result = metrics_source._parse_time_range("7d")
        assert result == timedelta(days=7)

    def test_parse_time_range_default(self, metrics_source):
        """기본 시간 범위 파싱 테스트"""
        from datetime import timedelta

        result = metrics_source._parse_time_range("invalid")
        assert result == timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_get_schema(self, metrics_source):
        """메트릭 스키마 조회 테스트"""
        result = await metrics_source.get_schema()
        assert result.is_success()
        schema = result.unwrap()
        assert isinstance(schema, DataSchema)
        assert "timestamp" in schema.columns
        assert "metric_name" in schema.columns
        assert "value" in schema.columns
        assert "labels" in schema.columns


class TestDataSourceManager:
    """DataSourceManager 테스트"""

    @pytest.fixture
    def manager(self):
        """DataSourceManager 인스턴스"""
        return DataSourceManager()

    @pytest.fixture
    def mock_source(self):
        """Mock DataSource"""
        mock = Mock(spec=DataSource)
        mock.source_id = "test_source"
        mock.connect = AsyncMock(return_value=Success(True))
        mock.disconnect = AsyncMock(return_value=Success(True))
        mock.execute_query = AsyncMock(return_value=Success([{"test": "data"}]))
        mock.validate_connection = AsyncMock(return_value=Success(True))
        return mock

    def test_initialization(self, manager):
        """DataSourceManager 초기화 테스트"""
        assert manager._sources == {}
        assert manager._connected_sources == {}

    def test_register_source_success(self, manager, mock_source):
        """데이터 소스 등록 성공 테스트"""
        result = manager.register_source(mock_source)
        assert result.is_success()
        assert result.unwrap() == True
        assert "test_source" in manager._sources
        assert manager._sources["test_source"] == mock_source

    def test_register_source_already_exists(self, manager, mock_source):
        """이미 존재하는 데이터 소스 등록 테스트"""
        manager.register_source(mock_source)

        result = manager.register_source(mock_source)
        assert result.is_failure()
        assert result.unwrap_error() == "Data source already registered: test_source"

    @pytest.mark.asyncio
    async def test_connect_source_success(self, manager, mock_source):
        """데이터 소스 연결 성공 테스트"""
        manager.register_source(mock_source)

        result = await manager.connect_source("test_source")
        assert result.is_success()
        assert result.unwrap() == True
        assert "test_source" in manager._connected_sources
        mock_source.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_source_not_found(self, manager):
        """존재하지 않는 데이터 소스 연결 테스트"""
        result = await manager.connect_source("nonexistent")
        assert result.is_failure()
        assert result.unwrap_error() == "Data source not found: nonexistent"

    def test_get_source_success(self, manager, mock_source):
        """데이터 소스 조회 성공 테스트"""
        manager.register_source(mock_source)

        result = manager.get_source("test_source")
        assert result.is_success()
        assert result.unwrap() == mock_source

    def test_list_sources(self, manager, mock_source):
        """모든 데이터 소스 목록 조회 테스트"""
        manager.register_source(mock_source)

        sources = manager.list_sources()
        assert len(sources) == 1
        assert "test_source" in sources
        assert sources["test_source"] == mock_source


class TestHelperFunctions:
    """헬퍼 함수들 테스트"""

    def test_get_data_source_manager_singleton(self):
        """전역 데이터 소스 매니저 싱글톤 테스트"""
        manager1 = get_data_source_manager()
        manager2 = get_data_source_manager()
        assert manager1 is manager2
        assert isinstance(manager1, DataSourceManager)

    def test_create_database_source(self):
        """데이터베이스 소스 생성 함수 테스트"""
        source = create_database_source(
            "db_test",
            "Test Database",
            "postgresql://user:pass@localhost/db",
            "postgresql",
        )

        assert isinstance(source, DatabaseDataSource)
        assert source.source_id == "db_test"
        assert source.name == "Test Database"
        assert source.connection_string == "postgresql://user:pass@localhost/db"
        assert source.driver == "postgresql"

    def test_create_file_source(self):
        """파일 소스 생성 함수 테스트"""
        source = create_file_source(
            "file_test", "Test File", "/path/to/file.csv", "csv"
        )

        assert isinstance(source, FileDataSource)
        assert source.source_id == "file_test"
        assert source.name == "Test File"
        assert source.file_path == Path("/path/to/file.csv")
        assert source.file_type == "csv"

    def test_create_api_source(self):
        """API 소스 생성 함수 테스트"""
        headers = {"Authorization": "Bearer token"}
        source = create_api_source(
            "api_test", "Test API", "https://api.example.com", headers
        )

        assert isinstance(source, APIDataSource)
        assert source.source_id == "api_test"
        assert source.name == "Test API"
        assert source.base_url == "https://api.example.com"
        assert source.headers == headers

    def test_create_metrics_source(self):
        """메트릭 소스 생성 함수 테스트"""
        source = create_metrics_source("metrics_test", "Test Metrics")

        assert isinstance(source, MetricsDataSource)
        assert source.source_id == "metrics_test"
        assert source.name == "Test Metrics"
        assert source.config == {"metrics": {}}
