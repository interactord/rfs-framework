# Configuration API

Configuration management API documentation for RFS Framework.

**주요 클래스:**
- `Config`: 기본 설정 클래스
- `ConfigLoader`: 설정 로더
- `ConfigValidator`: 설정 검증기

## 사용 예제

### 기본 설정

```python
from rfs.core.config import Config, ConfigLoader
from pydantic import BaseModel
from typing import Optional

class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    username: str
    password: str
    database: str

class AppConfig(Config):
    debug: bool = False
    database: DatabaseConfig
    api_key: Optional[str] = None
    
    class Config:
        env_prefix = "APP_"
        case_sensitive = False

# 환경 변수에서 로드
config = ConfigLoader.load(AppConfig, 
    env_file=".env",
    env_file_encoding="utf-8"
)

print(f"Debug mode: {config.debug}")
print(f"Database: {config.database.host}:{config.database.port}")
```

### 환경별 설정

```python
from rfs.core.config import Config
import os

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class AppConfig(Config):
    environment: Environment = Environment.DEVELOPMENT
    database_url: str
    redis_url: Optional[str] = None
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

# 환경에 따른 설정 로드
env = os.getenv("ENVIRONMENT", "development")
config_file = f"config/{env}.json"

config = ConfigLoader.from_file(AppConfig, config_file)

if config.is_production:
    print("Running in production mode")
```

### 설정 검증

```python
from rfs.core.config import Config, ConfigValidator
from pydantic import validator, Field
from typing import List

class ServerConfig(Config):
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    workers: int = Field(default=1, ge=1, le=16, description="Number of workers")
    allowed_hosts: List[str] = Field(default_factory=list)
    
    @validator('host')
    def validate_host(cls, v):
        if not v or v.isspace():
            raise ValueError("Host cannot be empty")
        return v.strip()
    
    @validator('allowed_hosts')
    def validate_allowed_hosts(cls, v):
        if not v:
            return ["localhost", "127.0.0.1"]
        return v

# 설정 유효성 검사
try:
    config = ServerConfig(
        host="",  # 빈 호스트는 검증 실패
        port=8080,
        workers=4
    )
except ValidationError as e:
    print(f"Configuration error: {e}")

# 올바른 설정
config = ServerConfig(
    host="localhost",
    port=8080,
    workers=4,
    allowed_hosts=["localhost", "*.example.com"]
)

# 설정 검증
validator = ConfigValidator(config)
validation_result = validator.validate()

if validation_result.is_valid:
    print("Configuration is valid")
else:
    print(f"Validation errors: {validation_result.errors}")
```

### 동적 설정 관리

```python
from rfs.core.config import Config, ConfigWatcher
import asyncio

class AppConfig(Config):
    max_connections: int = 100
    timeout: float = 30.0
    feature_flags: Dict[str, bool] = Field(default_factory=dict)
    
    def update_feature_flag(self, name: str, enabled: bool):
        self.feature_flags[name] = enabled

# 설정 파일 감시 및 자동 리로드
async def watch_config():
    config = ConfigLoader.load(AppConfig, "config.json")
    
    watcher = ConfigWatcher(config, "config.json")
    
    @watcher.on_change
    async def on_config_change(new_config: AppConfig):
        print(f"Configuration updated: {new_config.dict()}")
        # 애플리케이션 설정 업데이트
        update_application_config(new_config)
    
    await watcher.start()

# 실행
asyncio.run(watch_config())
```

## 관련 문서

- [핵심 패턴](../../01-core-patterns.md) - 설정 관리 패턴
- [환경 설정](../../03-configuration.md) - 상세 설정 가이드