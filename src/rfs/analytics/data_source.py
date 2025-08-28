"""
RFS Advanced Analytics - Data Source System (RFS v4.1)

데이터 소스 연결 및 쿼리 시스템
"""

import asyncio
import csv
import io
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

from ..core.result import Failure, Result, ResultAsync, Success


class DataSourceType(Enum):
    DATABASE = "database"
    FILE = "file"
    API = "api"
    METRICS = "metrics"
    MEMORY = "memory"


@dataclass
class DataQuery:
    """데이터 쿼리 정의"""

    query: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    limit: Optional[int] = None
    offset: Optional[int] = None
    timeout: Optional[float] = None


@dataclass
class DataSchema:
    """데이터 스키마 정의"""

    columns: Dict[str, str] = field(default_factory=dict)
    primary_key = None
    indexes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.indexes is None:
            self.indexes = []


class DataSource(ABC):
    """데이터 소스 추상 클래스"""

    def __init__(self, source_id: str, name: str, config: Dict[str, Any]) -> None:
        self.source_id = source_id
        self.name = name
        self.config = config
        self._schema = None
        self._connected = False

    @abstractmethod
    async def connect(self) -> Result[bool, str]:
        """데이터 소스 연결

        Returns:
            Result[bool, str]: 연결 성공 여부 또는 오류
        """
        raise NotImplementedError("Subclasses must implement connect method")

    @abstractmethod
    async def disconnect(self) -> Result[bool, str]:
        """데이터 소스 연결 해제

        Returns:
            Result[bool, str]: 연결 해제 성공 여부 또는 오류
        """
        raise NotImplementedError("Subclasses must implement disconnect method")

    @abstractmethod
    async def execute_query(
        self, query: DataQuery
    ) -> Result[List[Dict[str, Any]], str]:
        """쿼리 실행

        Args:
            query: 실행할 쿼리

        Returns:
            Result[List[Dict[str, Any]], str]: 쿼리 결과 또는 오류
        """
        raise NotImplementedError("Subclasses must implement execute_query method")

    @abstractmethod
    async def get_schema(self) -> Result[DataSchema, str]:
        """스키마 조회

        Returns:
            Result[DataSchema, str]: 데이터 스키마 또는 오류
        """
        raise NotImplementedError("Subclasses must implement get_schema method")

    async def validate_connection(self) -> Result[bool, str]:
        """연결 유효성 검사"""
        if not self._connected:
            return Failure("Data source not connected")
        try:
            test_query = DataQuery(query=self._get_test_query(), parameters={}, limit=1)
            result = await self.execute_query(test_query)
            return result.map(lambda _: True)
        except Exception as e:
            return Failure(f"Connection validation failed: {str(e)}")

    def _get_test_query(self) -> str:
        """연결 테스트용 쿼리

        Returns:
            str: 테스트 쿼리 문자열
        """
        # 기본 테스트 쿼리
        return "SELECT 1"  # 대부분의 데이터베이스에서 사용 가능

    @property
    def is_connected(self) -> bool:
        return self._connected


class DatabaseDataSource(DataSource):
    """데이터베이스 데이터 소스"""

    def __init__(self, source_id: str, name: str, config: Dict[str, Any]) -> None:
        super().__init__(source_id, name, config)
        self.connection_string: Optional[str] = config.get("connection_string")
        self.driver: str = config.get("driver", "postgresql")
        self._connection = None

    async def connect(self) -> Result[bool, str]:
        """데이터베이스 연결"""
        try:
            match self.driver:
                case "postgresql":
                    import asyncpg

                    self._connection = await asyncpg.connect(self.connection_string)
                case "mysql":
                    import aiomysql

                    self._connection = await aiomysql.connect(
                        host=self.config.get("host"),
                        port=self.config.get("port", 3306),
                        user=self.config.get("user"),
                        password=self.config.get("password"),
                        db=self.config.get("database"),
                    )
                case "sqlite":
                    import aiosqlite

                    self._connection = await aiosqlite.connect(
                        self.config.get("database", ":memory:")
                    )
                case _:
                    return Failure(f"Unsupported database driver: {self.driver}")
            self._connected = True
            return Success(True)
        except Exception as e:
            return Failure(f"Database connection failed: {str(e)}")

    async def disconnect(self) -> Result[bool, str]:
        """데이터베이스 연결 해제"""
        try:
            if self._connection:
                await self._connection.close()
                self._connection = None
            self._connected = False
            return Success(True)
        except Exception as e:
            return Failure(f"Database disconnection failed: {str(e)}")

    async def execute_query(
        self, query: DataQuery
    ) -> Result[List[Dict[str, Any]], str]:
        """데이터베이스 쿼리 실행"""
        if not self._connected:
            return Failure("Database not connected")
        try:
            match self.driver:
                case "postgresql":
                    rows = await self._connection.fetch(
                        query.query, *query.parameters.values()
                    )
                    return Success([dict(row) for row in rows])
                case "mysql":
                    async with self._connection.cursor() as cursor:
                        await cursor.execute(query.query, query.parameters)
                        rows = await cursor.fetchall()
                        columns = [desc[0] for desc in cursor.description]
                        return Success([dict(zip(columns, row)) for row in rows])
                case "sqlite":
                    async with self._connection.execute(
                        query.query, query.parameters
                    ) as cursor:
                        rows = await cursor.fetchall()
                        columns = [desc[0] for desc in cursor.description]
                        return Success([dict(zip(columns, row)) for row in rows])
                case _:
                    return Failure(f"Unsupported driver: {self.driver}")
        except Exception as e:
            return Failure(f"Query execution failed: {str(e)}")

    async def get_schema(self) -> Result[DataSchema, str]:
        """데이터베이스 스키마 조회"""
        if self._schema:
            return Success(self._schema)
        try:
            if self.driver == "postgresql":
                schema_query = "\n                SELECT column_name, data_type \n                FROM information_schema.columns \n                WHERE table_name = $1\n                "
                table_name = self.config.get("table", "data")
                rows = await self._connection.fetch(schema_query, table_name)
            elif self.driver in ["mysql", "sqlite"]:
                schema_query = f"PRAGMA table_info({self.config.get('table', 'data')})"
                rows = await self.execute_query(DataQuery(schema_query, {}))
                if rows.is_failure():
                    return rows
                rows = rows.unwrap()
            columns = {}
            for row in rows:
                if self.driver == "postgresql":
                    columns = {
                        **columns,
                        row.get("column_name"): {
                            row.get("column_name"): row["data_type"]
                        },
                    }
                else:
                    columns = {
                        **columns,
                        row.get("name", row.get("Field")): {
                            row.get("name", row.get("Field")): row.get(
                                "type", row.get("Type")
                            )
                        },
                    }
            self._schema = DataSchema(columns=columns)
            return Success(self._schema)
        except Exception as e:
            return Failure(f"Schema retrieval failed: {str(e)}")

    def _get_test_query(self) -> str:
        """연결 테스트용 쿼리"""
        match self.driver:
            case "postgresql":
                return "SELECT 1"
            case "mysql":
                return "SELECT 1"
            case "sqlite":
                return "SELECT 1"
        return "SELECT 1"


class FileDataSource(DataSource):
    """파일 데이터 소스 (CSV, JSON, Excel)"""

    def __init__(self, source_id: str, name: str, config: Dict[str, Any]) -> None:
        super().__init__(source_id, name, config)
        self.file_path: Path = Path(config["file_path"])
        self.file_type: str = config.get("file_type", "csv")
        self.encoding: str = config.get("encoding", "utf-8")
        self._data: List[Dict[str, Any]] = []

    async def connect(self) -> Result[bool, str]:
        """파일 읽기"""
        try:
            if not self.file_path.exists():
                return Failure(f"File not found: {self.file_path}")
            match self.file_type:
                case "csv":
                    await self._load_csv()
                case "json":
                    await self._load_json()
                case "excel":
                    await self._load_excel()
                case _:
                    return Failure(f"Unsupported file type: {self.file_type}")
            self._connected = True
            return Success(True)
        except Exception as e:
            return Failure(f"File loading failed: {str(e)}")

    async def _load_csv(self) -> None:
        """CSV 파일 로드"""
        with open(self.file_path, "r", encoding=self.encoding) as f:
            reader = csv.DictReader(f)
            self._data = list(reader)

    async def _load_json(self) -> None:
        """JSON 파일 로드"""
        with open(self.file_path, "r", encoding=self.encoding) as f:
            data = json.load(f)
            if isinstance(data, list):
                self._data = data
            else:
                self._data = [data]

    async def _load_excel(self) -> None:
        """Excel 파일 로드"""
        try:
            import pandas as pd

            df = pd.read_excel(self.file_path)
            self._data = df.to_dict("records")
        except ImportError:
            raise ImportError("pandas required for Excel support")

    async def disconnect(self) -> Result[bool, str]:
        """파일 데이터 해제"""
        self._data = []
        self._connected = False
        return Success(True)

    async def execute_query(
        self, query: DataQuery
    ) -> Result[List[Dict[str, Any]], str]:
        """파일 데이터 쿼리 (간단한 필터링)"""
        if not self._connected:
            return Failure("File not loaded")
        try:
            result_data = self._data
            if query.parameters:
                result_data = [
                    row
                    for row in result_data
                    if all(
                        (
                            str(row.get(k, "")).lower() == str(v).lower()
                            for k, v in query.parameters.items()
                            if k in row
                        )
                    )
                ]
            if query.offset:
                result_data = result_data[query.offset :]
            if query.limit:
                result_data = result_data[: query.limit]
            return Success(result_data)
        except Exception as e:
            return Failure(f"File query failed: {str(e)}")

    async def get_schema(self) -> Result[DataSchema, str]:
        """파일 스키마 추론"""
        if self._schema:
            return Success(self._schema)
        if not self._data:
            return Failure("No data loaded")
        try:
            sample_row = self._data[0]
            columns = {}
            for key, value in sample_row.items():
                if isinstance(value, int):
                    columns[key] = "integer"
                elif isinstance(value, float):
                    columns[key] = "float"
                elif isinstance(value, bool):
                    columns[key] = "boolean"
                else:
                    columns[key] = "string"
            self._schema = DataSchema(columns=columns)
            return Success(self._schema)
        except Exception as e:
            return Failure(f"Schema inference failed: {str(e)}")

    def _get_test_query(self) -> str:
        """테스트 쿼리"""
        return "SELECT * LIMIT 1"


class APIDataSource(DataSource):
    """API 데이터 소스"""

    def __init__(self, source_id: str, name: str, config: Dict[str, Any]) -> None:
        super().__init__(source_id, name, config)
        self.base_url: str = config["base_url"]
        self.headers: Dict[str, str] = config.get("headers", {})
        self.auth: Dict[str, Any] = config.get("auth", {})
        self._session = None

    async def connect(self) -> Result[bool, str]:
        """API 연결 설정"""
        try:
            import aiohttp

            auth = None
            if self.auth.get("type") == "basic":
                auth = aiohttp.BasicAuth(self.auth["username"], self.auth["password"])
            self._session = aiohttp.ClientSession(
                headers=self.headers, auth=auth, timeout=aiohttp.ClientTimeout(total=30)
            )
            self._connected = True
            return Success(True)
        except Exception as e:
            return Failure(f"API connection failed: {str(e)}")

    async def disconnect(self) -> Result[bool, str]:
        """API 세션 해제"""
        try:
            if self._session:
                await self._session.close()
                self._session = None
            self._connected = False
            return Success(True)
        except Exception as e:
            return Failure(f"API disconnection failed: {str(e)}")

    async def execute_query(
        self, query: DataQuery
    ) -> Result[List[Dict[str, Any]], str]:
        """API 호출 실행"""
        if not self._connected:
            return Failure("API not connected")
        try:
            url = f"{self.base_url.rstrip('/')}/{query.query.lstrip('/')}"
            async with self._session.get(url, params=query.parameters) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict):
                        if "data" in data:
                            result_data = data["data"]
                        elif "results" in data:
                            result_data = data["results"]
                        else:
                            result_data = [data]
                    else:
                        result_data = data
                    if not isinstance(result_data, list):
                        result_data = [result_data]
                    return Success(result_data)
                else:
                    return Failure(f"API request failed: {response.status}")
        except Exception as e:
            return Failure(f"API query failed: {str(e)}")

    async def get_schema(self) -> Result[DataSchema, str]:
        """API 스키마 추론 (샘플 데이터 기반)"""
        if self._schema:
            return Success(self._schema)
        try:
            sample_query = DataQuery(
                query=self.config.get("schema_endpoint", ""), parameters={}, limit=1
            )
            result = await self.execute_query(sample_query)
            if result.is_failure():
                return result
            data = result.unwrap()
            if not data:
                return Failure("No sample data available")
            sample_row = data[0]
            columns = {}
            for key, value in sample_row.items():
                if isinstance(value, int):
                    columns[key] = "integer"
                elif isinstance(value, float):
                    columns[key] = "float"
                elif isinstance(value, bool):
                    columns[key] = "boolean"
                elif isinstance(value, list):
                    columns[key] = "array"
                elif isinstance(value, dict):
                    columns[key] = "object"
                else:
                    columns[key] = "string"
            self._schema = DataSchema(columns=columns)
            return Success(self._schema)
        except Exception as e:
            return Failure(f"API schema inference failed: {str(e)}")

    def _get_test_query(self) -> str:
        """테스트 쿼리"""
        return self.config.get("health_endpoint", "health")


class MetricsDataSource(DataSource):
    """메트릭 데이터 소스"""

    def __init__(self, source_id: str, name: str, config: Dict[str, Any]) -> None:
        super().__init__(source_id, name, config)
        self.metrics_config: Dict[str, Any] = config.get("metrics", {})
        self._metrics_data: Dict[str, List[Dict[str, Any]]] = {}
        self.collector = None

    async def connect(self) -> Result[bool, str]:
        """메트릭 수집 초기화"""
        try:
            from ..monitoring.metrics import get_metrics_collector

            self.collector = get_metrics_collector()
            self._connected = True
            return Success(True)
        except Exception as e:
            return Failure(f"Metrics connection failed: {str(e)}")

    async def disconnect(self) -> Result[bool, str]:
        """메트릭 수집 해제"""
        self._metrics_data = {}
        self._connected = False
        return Success(True)

    async def execute_query(
        self, query: DataQuery
    ) -> Result[List[Dict[str, Any]], str]:
        """메트릭 쿼리 실행"""
        if not self._connected:
            return Failure("Metrics not connected")
        try:
            metric_name = query.query
            time_range = query.parameters.get("time_range", "1h")
            metrics = await self._collect_metrics(metric_name, time_range)
            return Success(metrics)
        except Exception as e:
            return Failure(f"Metrics query failed: {str(e)}")

    async def _collect_metrics(
        self, metric_name: str, time_range: str
    ) -> List[Dict[str, Any]]:
        """메트릭 데이터 수집"""
        duration = self._parse_time_range(time_range)
        end_time = datetime.now()
        start_time = end_time - duration
        import random

        data = []
        current_time = start_time
        while current_time <= end_time:
            data = data + [
                {
                    "timestamp": current_time.isoformat(),
                    "metric_name": metric_name,
                    "value": random.uniform(0, 100),
                    "labels": {"instance": "server-1", "region": "us-west-2"},
                }
            ]
            current_time = current_time + timedelta(minutes=5)
        return data

    def _parse_time_range(self, time_range: str) -> timedelta:
        """시간 범위 파싱"""
        try:
            match time_range[-1]:
                case "m":
                    return timedelta(minutes=int(time_range[:-1]))
                case "h":
                    return timedelta(hours=int(time_range[:-1]))
                case "d":
                    return timedelta(days=int(time_range[:-1]))
                case _:
                    return timedelta(hours=1)
        except (ValueError, TypeError, IndexError):
            return timedelta(hours=1)

    async def get_schema(self) -> Result[DataSchema, str]:
        """메트릭 스키마"""
        columns = {
            "timestamp": "datetime",
            "metric_name": "string",
            "value": "float",
            "labels": "object",
        }
        self._schema = DataSchema(columns=columns)
        return Success(self._schema)

    def _get_test_query(self) -> str:
        """테스트 쿼리"""
        return "system_cpu_usage"


class DataSourceManager:
    """데이터 소스 관리자"""

    def __init__(self) -> None:
        self._sources = {}
        self._connected_sources = {}

    def register_source(self, source: DataSource) -> Result[bool, str]:
        """데이터 소스 등록"""
        if source.source_id in self._sources:
            return Failure(f"Data source already registered: {source.source_id}")
        self._sources = {**self._sources, source.source_id: source}
        return Success(True)

    def unregister_source(self, source_id: str) -> Result[bool, str]:
        """데이터 소스 등록 해제"""
        if source_id not in self._sources:
            return Failure(f"Data source not found: {source_id}")
        if source_id in self._connected_sources:
            asyncio.create_task(self._sources[source_id].disconnect())
            del self._connected_sources[source_id]
        del self._sources[source_id]
        return Success(True)

    async def connect_source(self, source_id: str) -> Result[bool, str]:
        """데이터 소스 연결"""
        if source_id not in self._sources:
            return Failure(f"Data source not found: {source_id}")
        source = self._sources[source_id]
        result = await source.connect()
        if result.is_success():
            self._connected_sources = {**self._connected_sources, source_id: source}
        return result

    async def disconnect_source(self, source_id: str) -> Result[bool, str]:
        """데이터 소스 연결 해제"""
        if source_id not in self._connected_sources:
            return Failure(f"Data source not connected: {source_id}")
        source = self._connected_sources[source_id]
        result = await source.disconnect()
        if result.is_success():
            del self._connected_sources[source_id]
        return result

    def get_source(self, source_id: str) -> Result[DataSource, str]:
        """데이터 소스 조회"""
        if source_id not in self._sources:
            return Failure(f"Data source not found: {source_id}")
        return Success(self._sources[source_id])

    def list_sources(self) -> Dict[str, DataSource]:
        """모든 데이터 소스 목록"""
        return self._sources.copy()

    def list_connected_sources(self) -> Dict[str, DataSource]:
        """연결된 데이터 소스 목록"""
        return self._connected_sources.copy()

    async def execute_query(
        self, source_id: str, query: DataQuery
    ) -> Result[List[Dict[str, Any]], str]:
        """데이터 소스에서 쿼리 실행"""
        if source_id not in self._connected_sources:
            return Failure(f"Data source not connected: {source_id}")
        source = self._connected_sources[source_id]
        return await source.execute_query(query)

    async def validate_all_connections(self) -> Dict[str, Result[bool, str]]:
        """모든 연결된 데이터 소스 검증"""
        results: Dict[str, Result[bool, str]] = {}
        for source_id, source in self._connected_sources.items():
            results[source_id] = await source.validate_connection()
        return results


_global_data_source_manager = None


def get_data_source_manager() -> DataSourceManager:
    """전역 데이터 소스 매니저 가져오기"""
    global _global_data_source_manager
    if _global_data_source_manager is None:
        _global_data_source_manager = DataSourceManager()
    return _global_data_source_manager


def register_data_source(source: DataSource) -> Result[bool, str]:
    """데이터 소스 등록 헬퍼 함수"""
    manager = get_data_source_manager()
    return manager.register_source(source)


def create_database_source(
    source_id: str, name: str, connection_string: str, driver="postgresql"
) -> DatabaseDataSource:
    """데이터베이스 데이터 소스 생성"""
    config = {"connection_string": connection_string, "driver": driver}
    return DatabaseDataSource(source_id, name, config)


def create_file_source(
    source_id: str, name: str, file_path: str, file_type="csv"
) -> FileDataSource:
    """파일 데이터 소스 생성"""
    config = {"file_path": file_path, "file_type": file_type}
    return FileDataSource(source_id, name, config)


def create_api_source(
    source_id: str, name: str, base_url: str, headers=None
) -> APIDataSource:
    """API 데이터 소스 생성"""
    config = {"base_url": base_url, "headers": headers or {}}
    return APIDataSource(source_id, name, config)


def create_metrics_source(source_id: str, name: str) -> MetricsDataSource:
    """메트릭 데이터 소스 생성"""
    config = {"metrics": {}}
    return MetricsDataSource(source_id, name, config)
