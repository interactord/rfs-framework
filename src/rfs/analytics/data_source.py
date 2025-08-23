"""
RFS Advanced Analytics - Data Source System (RFS v4.1)

데이터 소스 연결 및 쿼리 시스템
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, AsyncIterator, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import json
import csv
import io
from pathlib import Path

from ..core.types import Result, Success, Failure
from ..core.async_result import ResultAsync


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
    parameters: Dict[str, Any]
    limit: Optional[int] = None
    offset: Optional[int] = 0
    timeout: Optional[int] = 30


@dataclass
class DataSchema:
    """데이터 스키마 정의"""
    columns: Dict[str, str]  # column_name -> data_type
    primary_key: Optional[str] = None
    indexes: List[str] = None
    
    def __post_init__(self):
        if self.indexes is None:
            self.indexes = []


class DataSource(ABC):
    """데이터 소스 추상 클래스"""
    
    def __init__(self, source_id: str, name: str, config: Dict[str, Any]):
        self.source_id = source_id
        self.name = name
        self.config = config
        self._schema: Optional[DataSchema] = None
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> Result[bool, str]:
        """데이터 소스 연결"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> Result[bool, str]:
        """데이터 소스 연결 해제"""
        pass
    
    @abstractmethod
    async def execute_query(self, query: DataQuery) -> Result[List[Dict[str, Any]], str]:
        """쿼리 실행"""
        pass
    
    @abstractmethod
    async def get_schema(self) -> Result[DataSchema, str]:
        """스키마 조회"""
        pass
    
    async def validate_connection(self) -> Result[bool, str]:
        """연결 유효성 검사"""
        if not self._connected:
            return Failure("Data source not connected")
        
        try:
            # 간단한 테스트 쿼리 실행
            test_query = DataQuery(
                query=self._get_test_query(),
                parameters={},
                limit=1
            )
            result = await self.execute_query(test_query)
            return result.map(lambda _: True)
        except Exception as e:
            return Failure(f"Connection validation failed: {str(e)}")
    
    @abstractmethod
    def _get_test_query(self) -> str:
        """연결 테스트용 쿼리"""
        pass
    
    @property
    def is_connected(self) -> bool:
        return self._connected


class DatabaseDataSource(DataSource):
    """데이터베이스 데이터 소스"""
    
    def __init__(self, source_id: str, name: str, config: Dict[str, Any]):
        super().__init__(source_id, name, config)
        self.connection_string = config.get("connection_string")
        self.driver = config.get("driver", "postgresql")
        self._connection = None
    
    async def connect(self) -> Result[bool, str]:
        """데이터베이스 연결"""
        try:
            if self.driver == "postgresql":
                import asyncpg
                self._connection = await asyncpg.connect(self.connection_string)
            elif self.driver == "mysql":
                import aiomysql
                self._connection = await aiomysql.connect(
                    host=self.config.get("host"),
                    port=self.config.get("port", 3306),
                    user=self.config.get("user"),
                    password=self.config.get("password"),
                    db=self.config.get("database")
                )
            elif self.driver == "sqlite":
                import aiosqlite
                self._connection = await aiosqlite.connect(
                    self.config.get("database", ":memory:")
                )
            else:
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
    
    async def execute_query(self, query: DataQuery) -> Result[List[Dict[str, Any]], str]:
        """데이터베이스 쿼리 실행"""
        if not self._connected:
            return Failure("Database not connected")
        
        try:
            if self.driver == "postgresql":
                rows = await self._connection.fetch(
                    query.query,
                    *query.parameters.values()
                )
                return Success([dict(row) for row in rows])
            
            elif self.driver == "mysql":
                async with self._connection.cursor() as cursor:
                    await cursor.execute(query.query, query.parameters)
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return Success([
                        dict(zip(columns, row)) for row in rows
                    ])
            
            elif self.driver == "sqlite":
                async with self._connection.execute(query.query, query.parameters) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return Success([
                        dict(zip(columns, row)) for row in rows
                    ])
            
            else:
                return Failure(f"Unsupported driver: {self.driver}")
                
        except Exception as e:
            return Failure(f"Query execution failed: {str(e)}")
    
    async def get_schema(self) -> Result[DataSchema, str]:
        """데이터베이스 스키마 조회"""
        if self._schema:
            return Success(self._schema)
        
        try:
            if self.driver == "postgresql":
                schema_query = """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = $1
                """
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
                    columns[row['column_name']] = row['data_type']
                else:
                    columns[row.get('name', row.get('Field'))] = row.get('type', row.get('Type'))
            
            self._schema = DataSchema(columns=columns)
            return Success(self._schema)
            
        except Exception as e:
            return Failure(f"Schema retrieval failed: {str(e)}")
    
    def _get_test_query(self) -> str:
        """연결 테스트용 쿼리"""
        if self.driver == "postgresql":
            return "SELECT 1"
        elif self.driver == "mysql":
            return "SELECT 1"
        elif self.driver == "sqlite":
            return "SELECT 1"
        return "SELECT 1"


class FileDataSource(DataSource):
    """파일 데이터 소스 (CSV, JSON, Excel)"""
    
    def __init__(self, source_id: str, name: str, config: Dict[str, Any]):
        super().__init__(source_id, name, config)
        self.file_path = Path(config["file_path"])
        self.file_type = config.get("file_type", "csv")
        self.encoding = config.get("encoding", "utf-8")
        self._data: List[Dict[str, Any]] = []
    
    async def connect(self) -> Result[bool, str]:
        """파일 읽기"""
        try:
            if not self.file_path.exists():
                return Failure(f"File not found: {self.file_path}")
            
            if self.file_type == "csv":
                await self._load_csv()
            elif self.file_type == "json":
                await self._load_json()
            elif self.file_type == "excel":
                await self._load_excel()
            else:
                return Failure(f"Unsupported file type: {self.file_type}")
            
            self._connected = True
            return Success(True)
            
        except Exception as e:
            return Failure(f"File loading failed: {str(e)}")
    
    async def _load_csv(self):
        """CSV 파일 로드"""
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            reader = csv.DictReader(f)
            self._data = list(reader)
    
    async def _load_json(self):
        """JSON 파일 로드"""
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            data = json.load(f)
            if isinstance(data, list):
                self._data = data
            else:
                self._data = [data]
    
    async def _load_excel(self):
        """Excel 파일 로드"""
        try:
            import pandas as pd
            df = pd.read_excel(self.file_path)
            self._data = df.to_dict('records')
        except ImportError:
            raise ImportError("pandas required for Excel support")
    
    async def disconnect(self) -> Result[bool, str]:
        """파일 데이터 해제"""
        self._data = []
        self._connected = False
        return Success(True)
    
    async def execute_query(self, query: DataQuery) -> Result[List[Dict[str, Any]], str]:
        """파일 데이터 쿼리 (간단한 필터링)"""
        if not self._connected:
            return Failure("File not loaded")
        
        try:
            # 간단한 쿼리 파싱 및 실행
            result_data = self._data
            
            # 필터링 적용
            if query.parameters:
                result_data = [
                    row for row in result_data
                    if all(
                        str(row.get(k, '')).lower() == str(v).lower()
                        for k, v in query.parameters.items()
                        if k in row
                    )
                ]
            
            # 페이지네이션
            if query.offset:
                result_data = result_data[query.offset:]
            if query.limit:
                result_data = result_data[:query.limit]
            
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
            # 첫 번째 행에서 컬럼과 타입 추론
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
    
    def __init__(self, source_id: str, name: str, config: Dict[str, Any]):
        super().__init__(source_id, name, config)
        self.base_url = config["base_url"]
        self.headers = config.get("headers", {})
        self.auth = config.get("auth", {})
        self._session = None
    
    async def connect(self) -> Result[bool, str]:
        """API 연결 설정"""
        try:
            import aiohttp
            
            auth = None
            if self.auth.get("type") == "basic":
                auth = aiohttp.BasicAuth(
                    self.auth["username"],
                    self.auth["password"]
                )
            
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=30)
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
    
    async def execute_query(self, query: DataQuery) -> Result[List[Dict[str, Any]], str]:
        """API 호출 실행"""
        if not self._connected:
            return Failure("API not connected")
        
        try:
            url = f"{self.base_url.rstrip('/')}/{query.query.lstrip('/')}"
            
            async with self._session.get(url, params=query.parameters) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # 데이터 정규화
                    if isinstance(data, dict):
                        if 'data' in data:
                            result_data = data['data']
                        elif 'results' in data:
                            result_data = data['results']
                        else:
                            result_data = [data]
                    else:
                        result_data = data
                    
                    # 리스트가 아닌 경우 리스트로 변환
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
            # 샘플 데이터 조회
            sample_query = DataQuery(
                query=self.config.get("schema_endpoint", ""),
                parameters={},
                limit=1
            )
            
            result = await self.execute_query(sample_query)
            if result.is_failure():
                return result
            
            data = result.unwrap()
            if not data:
                return Failure("No sample data available")
            
            # 스키마 추론
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
    
    def __init__(self, source_id: str, name: str, config: Dict[str, Any]):
        super().__init__(source_id, name, config)
        self.metrics_config = config.get("metrics", {})
        self._metrics_data: Dict[str, List[Dict[str, Any]]] = {}
    
    async def connect(self) -> Result[bool, str]:
        """메트릭 수집 초기화"""
        try:
            # 메트릭 수집기 초기화
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
    
    async def execute_query(self, query: DataQuery) -> Result[List[Dict[str, Any]], str]:
        """메트릭 쿼리 실행"""
        if not self._connected:
            return Failure("Metrics not connected")
        
        try:
            metric_name = query.query
            time_range = query.parameters.get("time_range", "1h")
            
            # 메트릭 데이터 수집
            metrics = await self._collect_metrics(metric_name, time_range)
            
            return Success(metrics)
            
        except Exception as e:
            return Failure(f"Metrics query failed: {str(e)}")
    
    async def _collect_metrics(self, metric_name: str, time_range: str) -> List[Dict[str, Any]]:
        """메트릭 데이터 수집"""
        # 시간 범위 파싱
        duration = self._parse_time_range(time_range)
        end_time = datetime.now()
        start_time = end_time - duration
        
        # 메트릭 데이터 생성 (실제로는 모니터링 시스템에서 가져옴)
        import random
        data = []
        current_time = start_time
        
        while current_time <= end_time:
            data.append({
                "timestamp": current_time.isoformat(),
                "metric_name": metric_name,
                "value": random.uniform(0, 100),
                "labels": {"instance": "server-1", "region": "us-west-2"}
            })
            current_time += timedelta(minutes=5)
        
        return data
    
    def _parse_time_range(self, time_range: str) -> timedelta:
        """시간 범위 파싱"""
        if time_range.endswith('m'):
            return timedelta(minutes=int(time_range[:-1]))
        elif time_range.endswith('h'):
            return timedelta(hours=int(time_range[:-1]))
        elif time_range.endswith('d'):
            return timedelta(days=int(time_range[:-1]))
        else:
            return timedelta(hours=1)
    
    async def get_schema(self) -> Result[DataSchema, str]:
        """메트릭 스키마"""
        columns = {
            "timestamp": "datetime",
            "metric_name": "string",
            "value": "float",
            "labels": "object"
        }
        
        self._schema = DataSchema(columns=columns)
        return Success(self._schema)
    
    def _get_test_query(self) -> str:
        """테스트 쿼리"""
        return "system_cpu_usage"


class DataSourceManager:
    """데이터 소스 관리자"""
    
    def __init__(self):
        self._sources: Dict[str, DataSource] = {}
        self._connected_sources: Dict[str, DataSource] = {}
    
    def register_source(self, source: DataSource) -> Result[bool, str]:
        """데이터 소스 등록"""
        if source.source_id in self._sources:
            return Failure(f"Data source already registered: {source.source_id}")
        
        self._sources[source.source_id] = source
        return Success(True)
    
    def unregister_source(self, source_id: str) -> Result[bool, str]:
        """데이터 소스 등록 해제"""
        if source_id not in self._sources:
            return Failure(f"Data source not found: {source_id}")
        
        # 연결된 소스면 연결 해제
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
            self._connected_sources[source_id] = source
        
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
    
    async def execute_query(self, source_id: str, query: DataQuery) -> Result[List[Dict[str, Any]], str]:
        """데이터 소스에서 쿼리 실행"""
        if source_id not in self._connected_sources:
            return Failure(f"Data source not connected: {source_id}")
        
        source = self._connected_sources[source_id]
        return await source.execute_query(query)
    
    async def validate_all_connections(self) -> Dict[str, Result[bool, str]]:
        """모든 연결된 데이터 소스 검증"""
        results = {}
        
        for source_id, source in self._connected_sources.items():
            results[source_id] = await source.validate_connection()
        
        return results


# 전역 데이터 소스 매니저
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


# 팩토리 함수들
def create_database_source(source_id: str, name: str, connection_string: str, 
                          driver: str = "postgresql") -> DatabaseDataSource:
    """데이터베이스 데이터 소스 생성"""
    config = {
        "connection_string": connection_string,
        "driver": driver
    }
    return DatabaseDataSource(source_id, name, config)


def create_file_source(source_id: str, name: str, file_path: str, 
                      file_type: str = "csv") -> FileDataSource:
    """파일 데이터 소스 생성"""
    config = {
        "file_path": file_path,
        "file_type": file_type
    }
    return FileDataSource(source_id, name, config)


def create_api_source(source_id: str, name: str, base_url: str,
                     headers: Optional[Dict[str, str]] = None) -> APIDataSource:
    """API 데이터 소스 생성"""
    config = {
        "base_url": base_url,
        "headers": headers or {}
    }
    return APIDataSource(source_id, name, config)


def create_metrics_source(source_id: str, name: str) -> MetricsDataSource:
    """메트릭 데이터 소스 생성"""
    config = {"metrics": {}}
    return MetricsDataSource(source_id, name, config)