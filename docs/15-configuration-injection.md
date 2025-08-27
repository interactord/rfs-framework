# RFS Framework 설정 주입 가이드

## 개요

RFS Framework에서 설정(Configuration) 값을 구현체(Implementation)에 주입하는 다양한 패턴과 방법을 설명합니다.

## 🔧 주요 주입 패턴

### 1. 직접 가져오기 패턴 (Direct Import Pattern)

가장 간단하고 직접적인 방식으로, 필요한 곳에서 설정을 직접 가져옵니다.

```python
from rfs.core.config import get_config
from rfs.hof.core import pipe
from rfs.hof.collections import first

class MyService:
    def __init__(self):
        """생성자에서 설정을 직접 가져옵니다."""
        self.config = get_config()
        self.database_url = self.config.redis_url
        self.max_retries = self.config.max_concurrency
    
    def process_data(self, data: dict) -> Result[dict, str]:
        """설정값을 사용하여 데이터를 처리합니다."""
        if self.config.is_development():
            # 개발 환경에서만 디버그 로그
            logger.debug(f"Processing: {data}")
        
        # HOF를 활용한 데이터 처리 파이프라인
        return pipe(
            self._validate_data_size,
            lambda result: result.bind(self._process_internal)
        )(data)
    
    def _validate_data_size(self, data: dict) -> Result[dict, str]:
        """데이터 크기를 검증합니다."""
        if len(data) > self.max_retries:
            return Failure("데이터 크기가 최대 처리량을 초과합니다")
        return Success(data)
```

**장점**: 간단하고 명확함
**단점**: 테스트하기 어려움, 의존성이 숨겨져 있음

### 2. 헬퍼 함수 패턴 (Helper Function Pattern)

점 표기법을 지원하는 헬퍼 함수를 통해 설정값을 가져옵니다.

```python
from rfs.core.helpers import get, get_config

class DatabaseService:
    def __init__(self):
        """헬퍼 함수를 사용하여 설정을 가져옵니다."""
        # 점 표기법으로 중첩된 설정 접근
        self.host = get("database.host", "localhost")
        self.port = get("database.port", 5432)
        self.timeout = get("database.connection_timeout", 30)
        
        # 전체 설정 객체도 가져올 수 있음
        self.config = get_config()
    
    def connect(self) -> Result[Connection, str]:
        """설정을 사용하여 데이터베이스 연결을 생성합니다."""
        try:
            conn = create_connection(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            return Success(conn)
        except ConnectionError as e:
            return Failure(f"데이터베이스 연결 실패: {e}")

# 사용 예시
service = DatabaseService()
result = service.connect()
```

**장점**: 유연한 설정 접근, 기본값 지원
**단점**: 런타임 오류 가능성

### 3. 생성자 주입 패턴 (Constructor Injection)

의존성을 명시적으로 생성자를 통해 주입받는 패턴입니다.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ServiceConfig:
    """서비스별 설정 클래스"""
    api_endpoint: str = "https://api.example.com"
    timeout: int = 30
    max_retries: int = 3
    debug_mode: bool = False

class APIService:
    def __init__(self, config: Optional[ServiceConfig] = None):
        """설정을 생성자로 주입받습니다."""
        self.config = config or ServiceConfig()
        
        # 글로벌 설정과 병합 가능
        global_config = get_config()
        if global_config.is_development():
            self.config.debug_mode = True
    
    def call_api(self, endpoint: str, data: dict) -> Result[dict, str]:
        """설정된 값으로 API를 호출합니다."""
        url = f"{self.config.api_endpoint}/{endpoint}"
        
        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(
                    url, 
                    json=data, 
                    timeout=self.config.timeout
                )
                
                if self.config.debug_mode:
                    logger.debug(f"API 호출 성공: {url}")
                
                return Success(response.json())
            except requests.Timeout:
                if attempt == self.config.max_retries - 1:
                    return Failure(f"API 호출 타임아웃: {url}")
                continue

# 사용 예시
# 기본 설정으로 생성
service = APIService()

# 커스텀 설정으로 생성
custom_config = ServiceConfig(
    api_endpoint="https://custom-api.com",
    timeout=60,
    max_retries=5
)
service_with_custom = APIService(custom_config)
```

**장점**: 테스트하기 쉬움, 의존성이 명확함
**단점**: 보일러플레이트 코드 증가

### 4. 의존성 주입 패턴 (Dependency Injection)

데코레이터를 통해 의존성을 자동으로 주입받는 패턴입니다.

```python
from rfs.core.registry import default_registry, stateless
from rfs.core.singleton import inject

# 설정 서비스를 레지스트리에 등록
@stateless
class ConfigService:
    """설정 관리 서비스"""
    
    def __init__(self):
        self.config = get_config()
    
    def get_database_config(self) -> dict:
        """데이터베이스 설정을 반환합니다."""
        return {
            "url": self.config.redis_url,
            "timeout": 30,
            "pool_size": self.config.max_concurrency
        }
    
    def get_cache_config(self) -> dict:
        """캐시 설정을 반환합니다."""
        return {
            "enabled": True,
            "ttl": 3600,
            "max_size": 1000
        }

# 설정 서비스를 레지스트리에 등록
default_registry.register("config_service", ConfigService)

# 의존성 주입을 통해 사용
class UserService:
    
    @inject("config_service")
    def create_user(self, user_data: dict, config_service: ConfigService) -> Result[User, str]:
        """사용자를 생성합니다."""
        db_config = config_service.get_database_config()
        
        # 데이터베이스 설정을 사용하여 연결
        conn = create_db_connection(**db_config)
        
        try:
            user = User(**user_data)
            save_user(conn, user)
            return Success(user)
        except Exception as e:
            return Failure(f"사용자 생성 실패: {e}")
    
    @inject("config_service")
    def get_user_cached(self, user_id: str, config_service: ConfigService) -> Result[User, str]:
        """캐시를 사용하여 사용자를 조회합니다."""
        cache_config = config_service.get_cache_config()
        
        if cache_config["enabled"]:
            # 캐시에서 먼저 확인
            cached_user = get_from_cache(user_id, ttl=cache_config["ttl"])
            if cached_user:
                return Success(cached_user)
        
        # 데이터베이스에서 조회
        return self._get_user_from_db(user_id)
```

**장점**: 깔끔한 코드, 자동 의존성 해결
**단점**: 마법같은 동작, 디버깅 어려움

### 5. 레지스트리 기반 주입 (Registry-based Injection)

서비스 레지스트리를 통해 설정이 포함된 서비스를 관리합니다.

```python
from rfs.core.registry import ServiceRegistry, ServiceScope, ServiceDefinition

# 설정이 포함된 서비스 정의
class DatabaseConfiguration:
    """데이터베이스 설정 서비스"""
    
    def __init__(self):
        config = get_config()
        self.connection_string = config.redis_url
        self.pool_size = config.max_concurrency
        self.timeout = 30
    
    def get_connection_params(self) -> dict:
        """연결 매개변수를 반환합니다."""
        return {
            "connection_string": self.connection_string,
            "pool_size": self.pool_size,
            "timeout": self.timeout
        }

class CacheConfiguration:
    """캐시 설정 서비스"""
    
    def __init__(self):
        config = get_config()
        self.enabled = not config.is_test()  # 테스트 환경에서는 캐시 비활성화
        self.ttl = 3600
        self.max_entries = 10000
    
    def is_cache_enabled(self) -> bool:
        """캐시 활성화 여부를 반환합니다."""
        return self.enabled

# 서비스 레지스트리에 등록
registry = ServiceRegistry()
registry.register(
    "db_config", 
    DatabaseConfiguration, 
    scope=ServiceScope.SINGLETON
)
registry.register(
    "cache_config", 
    CacheConfiguration, 
    scope=ServiceScope.SINGLETON
)

# 의존성이 있는 서비스 등록
class DataService:
    def __init__(self, db_config: DatabaseConfiguration, cache_config: CacheConfiguration):
        """설정 서비스들을 주입받습니다."""
        self.db_config = db_config
        self.cache_config = cache_config
        self._connection = None
    
    def get_data(self, key: str) -> Result[dict, str]:
        """데이터를 조회합니다."""
        # 캐시 확인
        if self.cache_config.is_cache_enabled():
            cached = self._get_from_cache(key)
            if cached:
                return Success(cached)
        
        # 데이터베이스 조회
        conn_params = self.db_config.get_connection_params()
        return self._fetch_from_db(key, conn_params)

# 의존성과 함께 등록
registry.register(
    "data_service",
    DataService,
    dependencies=["db_config", "cache_config"],
    scope=ServiceScope.SINGLETON
)

# 사용
data_service = registry.get("data_service")
result = data_service.get_data("user:123")
```

**장점**: 완전한 의존성 관리, 생명주기 제어
**단점**: 복잡성 증가, 학습 곡선

## 🚀 실제 사용 예제

### Cloud Run 환경 최적화 예제

```python
from rfs.core.config import get_config
from rfs.web.server import RFSWebServer, WebServerConfig

class CloudRunOptimizedService:
    """Cloud Run 환경에 최적화된 서비스"""
    
    def __init__(self):
        # RFS 글로벌 설정 가져오기
        self.rfs_config = get_config()
        
        # 웹 서버 설정을 환경에 맞게 조정
        self.web_config = WebServerConfig(
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),  # Cloud Run 포트
            debug=self.rfs_config.is_development(),
            cloud_run_optimized=True,
            request_timeout=self.rfs_config.cloud_run_cpu_limit,
            enable_cors=True
        )
        
        # 서버 인스턴스 생성
        self.server = RFSWebServer(self.web_config)
    
    def configure_for_environment(self) -> None:
        """환경별 추가 설정을 적용합니다."""
        if self.rfs_config.is_production():
            # 프로덕션 환경 최적화
            self.web_config.enable_metrics = True
            self.web_config.enable_security_headers = True
            
        elif self.rfs_config.is_development():
            # 개발 환경 디버깅
            self.web_config.debug = True
            self.web_config.enable_logging = True

# 사용
service = CloudRunOptimizedService()
service.configure_for_environment()
app = service.server.app
```

### 다중 데이터 소스 설정 예제

```python
from typing import Dict, Any
from rfs.core.config import get_config, RFSConfig

class MultiDataSourceConfig:
    """다중 데이터 소스 설정 관리"""
    
    def __init__(self, rfs_config: RFSConfig = None):
        self.config = rfs_config or get_config()
        
        # 기본 데이터 소스 설정
        self.primary_db = {
            "url": self.config.redis_url,
            "pool_size": self.config.max_concurrency,
            "timeout": 30
        }
        
        # 캐시 설정
        self.cache = {
            "enabled": not self.config.is_test(),
            "redis_url": self.config.redis_url,
            "ttl": 3600
        }
        
        # 환경별 추가 설정
        self._configure_environment_specific()
    
    def _configure_environment_specific(self):
        """환경별 특화 설정을 적용합니다."""
        match self.config.environment:
            case Environment.DEVELOPMENT:
                self.cache["ttl"] = 60  # 개발환경에서는 짧은 TTL
                self.primary_db["pool_size"] = 5
                
            case Environment.PRODUCTION:
                self.cache["ttl"] = 7200  # 프로덕션에서는 긴 TTL
                self.primary_db["pool_size"] = self.config.max_concurrency
                
                # 백업 데이터 소스 추가
                self.backup_db = {
                    "url": self.config.custom.get("backup_redis_url"),
                    "pool_size": self.config.max_concurrency // 2,
                    "timeout": 60
                }
                
            case Environment.TEST:
                self.cache["enabled"] = False
                self.primary_db = {
                    "url": "redis://localhost:6380",  # 테스트 전용 인스턴스
                    "pool_size": 2,
                    "timeout": 10
                }
    
    def get_database_config(self, source: str = "primary") -> Dict[str, Any]:
        """데이터베이스 설정을 반환합니다."""
        match source:
            case "primary":
                return self.primary_db
            case "backup" if hasattr(self, 'backup_db'):
                return self.backup_db
            case _:
                return self.primary_db
    
    def get_cache_config(self) -> Dict[str, Any]:
        """캐시 설정을 반환합니다."""
        return self.cache

# 사용 예제
class DataAccessLayer:
    def __init__(self, config: MultiDataSourceConfig = None):
        self.config = config or MultiDataSourceConfig()
        
        # 데이터베이스 연결 설정
        self.primary_conn = self._create_connection(
            self.config.get_database_config("primary")
        )
        
        # 백업 연결 (프로덕션에서만)
        if hasattr(self.config, 'backup_db'):
            self.backup_conn = self._create_connection(
                self.config.get_database_config("backup")
            )
        
        # 캐시 설정
        cache_config = self.config.get_cache_config()
        self.cache_enabled = cache_config["enabled"]
    
    def get_user_data(self, user_id: str) -> Result[dict, str]:
        """사용자 데이터를 조회합니다."""
        # 캐시 확인
        if self.cache_enabled:
            cached = self._get_from_cache(user_id)
            if cached:
                return Success(cached)
        
        # 주 데이터베이스에서 조회
        try:
            data = self._query_database(self.primary_conn, user_id)
            return Success(data)
        except ConnectionError:
            # 백업 데이터베이스 시도 (있는 경우)
            if hasattr(self, 'backup_conn'):
                try:
                    data = self._query_database(self.backup_conn, user_id)
                    return Success(data)
                except ConnectionError:
                    pass
            
            return Failure("모든 데이터베이스 연결에 실패했습니다")
```

## 📋 패턴 선택 가이드

### 언제 어떤 패턴을 사용할까요?

| 상황 | 권장 패턴 | 이유 |
|------|----------|------|
| 간단한 스크립트 | 직접 가져오기 | 빠르고 간단함 |
| 유연한 설정 접근 필요 | 헬퍼 함수 | 점 표기법과 기본값 지원 |
| 테스트 가능한 클래스 | 생성자 주입 | 명확한 의존성, 테스트 용이 |
| 복잡한 서비스 | 의존성 주입 | 자동화된 의존성 관리 |
| 대규모 애플리케이션 | 레지스트리 기반 | 완전한 생명주기 관리 |

### 🎯 베스트 프랙티스

1. **환경별 설정 분리**
   ```python
   match config.environment:
       case Environment.DEVELOPMENT:
           # 개발 환경 설정
       case Environment.PRODUCTION:
           # 프로덕션 환경 설정
   ```

2. **설정 검증**
   ```python
   @field_validator("redis_url")
   @classmethod
   def validate_redis_url(cls, v: str) -> str:
       if not v.startswith("redis://"):
           raise ValueError("올바른 Redis URL이 아닙니다")
       return v
   ```

3. **기본값 제공**
   ```python
   timeout: int = get("api.timeout", 30)
   max_retries: int = get("api.max_retries", 3)
   ```

4. **타입 안전성**
   ```python
   class APIConfig(BaseModel):
       endpoint: str = Field(..., description="API 엔드포인트")
       timeout: int = Field(30, ge=1, le=300)
       api_key: str = Field(..., min_length=10)
   ```

## 🔧 고급 활용

### 동적 설정 업데이트

```python
class ConfigurableService:
    """런타임에 설정을 업데이트할 수 있는 서비스"""
    
    def __init__(self):
        self.config = get_config()
        self._settings_cache = {}
        
    def update_setting(self, key: str, value: Any) -> Result[None, str]:
        """설정을 동적으로 업데이트합니다."""
        try:
            # 설정 검증
            self._validate_setting(key, value)
            
            # 캐시 업데이트
            self._settings_cache[key] = value
            
            # 설정 적용
            self._apply_setting_change(key, value)
            
            return Success(None)
        except ValueError as e:
            return Failure(f"설정 업데이트 실패: {e}")
    
    def get_effective_setting(self, key: str, default: Any = None) -> Any:
        """캐시된 설정을 우선으로 설정값을 반환합니다."""
        # 동적 설정이 있으면 우선
        if key in self._settings_cache:
            return self._settings_cache[key]
        
        # 글로벌 설정에서 가져오기
        return get(key, default)
```

### 설정 프로파일링

```python
class ConfigProfiler:
    """설정 사용 패턴을 분석하는 프로파일러"""
    
    def __init__(self):
        self.access_count: Dict[str, int] = {}
        self.last_accessed: Dict[str, datetime] = {}
    
    def track_access(self, key: str) -> None:
        """설정 접근을 추적합니다."""
        self.access_count[key] = self.access_count.get(key, 0) + 1
        self.last_accessed[key] = datetime.now()
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """설정 사용 통계를 반환합니다."""
        return {
            "most_accessed": max(self.access_count.items(), key=lambda x: x[1]),
            "total_accesses": sum(self.access_count.values()),
            "unique_keys": len(self.access_count),
            "recent_accesses": [
                key for key, time in self.last_accessed.items()
                if (datetime.now() - time).seconds < 3600
            ]
        }
```

이 가이드를 통해 RFS Framework에서 설정 값을 효과적으로 주입하고 관리할 수 있습니다. 각 패턴의 장단점을 고려하여 프로젝트 요구사항에 맞는 방법을 선택하세요.