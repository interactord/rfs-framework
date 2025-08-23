# 설정 관리 (Configuration Management)

## 📌 개요

RFS Framework는 환경별 설정, 동적 설정 변경, 암호화된 비밀 관리를 지원하는 강력한 설정 시스템을 제공합니다. Pydantic v2를 기반으로 타입 안전성과 자동 검증을 보장합니다.

## 🎯 핵심 개념

### 설정 계층
- **환경 프로파일**: development, staging, production, cloud_run
- **설정 소스**: 환경 변수, 파일, Secret Manager, ConfigMap
- **우선순위**: 환경 변수 > 파일 설정 > 기본값

### 타입 안전성
- **Pydantic 모델**: 자동 검증 및 타입 변환
- **환경별 검증**: 프로파일별 필수 필드 검증
- **런타임 재로딩**: 설정 변경 시 자동 재로딩

## 📚 API 레퍼런스

### ConfigManager 클래스

```python
from rfs.core.config import (
    ConfigManager,
    BaseConfig,
    EnvironmentProfile,
    ConfigSource
)
```

### 주요 설정 타입

| 타입 | 설명 | 사용 예 |
|------|------|---------|
| `BaseConfig` | 기본 설정 클래스 | 모든 설정의 부모 클래스 |
| `DatabaseConfig` | DB 연결 설정 | 연결 풀, 타임아웃 |
| `CacheConfig` | 캐시 설정 | Redis, Memcached |
| `SecurityConfig` | 보안 설정 | JWT, 암호화 키 |
| `CloudRunConfig` | Cloud Run 설정 | 자동 스케일링, 리전 |

## 💡 사용 예제

### 기본 설정 정의

```python
from pydantic import BaseSettings, Field, SecretStr
from rfs.core.config import BaseConfig, EnvironmentProfile
from typing import Optional
import os

class AppConfig(BaseConfig):
    """애플리케이션 설정"""
    
    # 기본 설정
    app_name: str = Field("RFS App", description="애플리케이션 이름")
    version: str = Field("1.0.0", description="버전")
    debug: bool = Field(False, description="디버그 모드")
    
    # 서버 설정
    host: str = Field("0.0.0.0", description="서버 호스트")
    port: int = Field(8000, description="서버 포트")
    workers: int = Field(4, description="워커 수")
    
    # 데이터베이스
    database_url: str = Field(
        "postgresql://localhost/rfs",
        description="데이터베이스 URL"
    )
    database_pool_size: int = Field(20, description="연결 풀 크기")
    
    # 보안
    secret_key: SecretStr = Field(..., description="비밀 키")
    jwt_algorithm: str = Field("HS256", description="JWT 알고리즘")
    jwt_expire_minutes: int = Field(30, description="JWT 만료 시간")
    
    # 환경별 검증
    @validator("workers")
    def validate_workers(cls, v, values):
        if values.get("profile") == EnvironmentProfile.PRODUCTION:
            if v < 2:
                raise ValueError("프로덕션에서는 최소 2개의 워커 필요")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
```

### 환경별 설정

```python
from rfs.core.config import ConfigManager, EnvironmentProfile

# 개발 환경 설정
class DevelopmentConfig(AppConfig):
    """개발 환경 설정"""
    debug: bool = True
    host: str = "localhost"
    workers: int = 1
    database_url: str = "postgresql://localhost/rfs_dev"

# 프로덕션 설정
class ProductionConfig(AppConfig):
    """프로덕션 환경 설정"""
    debug: bool = False
    workers: int = 8
    database_pool_size: int = 50
    
    # SSL 설정
    ssl_cert_path: str = Field(..., description="SSL 인증서 경로")
    ssl_key_path: str = Field(..., description="SSL 키 경로")
    
    # 모니터링
    enable_monitoring: bool = True
    metrics_port: int = 9090

# 설정 매니저 초기화
config_manager = ConfigManager()

# 환경에 따른 설정 로드
if os.getenv("ENVIRONMENT") == "production":
    config = config_manager.load(ProductionConfig)
else:
    config = config_manager.load(DevelopmentConfig)
```

### Secret Manager 통합

```python
from rfs.core.config import SecretManager
from google.cloud import secretmanager
import json

class CloudSecretManager(SecretManager):
    """Google Cloud Secret Manager 통합"""
    
    def __init__(self, project_id: str):
        self.client = secretmanager.SecretManagerServiceClient()
        self.project_id = project_id
    
    async def get_secret(self, secret_id: str) -> str:
        """비밀 값 가져오기"""
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
        response = self.client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    async def set_secret(self, secret_id: str, value: str):
        """비밀 값 설정"""
        parent = f"projects/{self.project_id}"
        secret = self.client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}}
            }
        )
        
        self.client.add_secret_version(
            request={
                "parent": secret.name,
                "payload": {"data": value.encode("UTF-8")}
            }
        )

# 사용 예제
async def load_secure_config():
    secret_manager = CloudSecretManager("my-project")
    
    # 비밀 값 로드
    db_password = await secret_manager.get_secret("db-password")
    api_key = await secret_manager.get_secret("api-key")
    
    # 설정에 적용
    config = AppConfig(
        database_url=f"postgresql://user:{db_password}@host/db",
        secret_key=api_key
    )
    
    return config
```

### 동적 설정 재로딩

```python
from rfs.core.config import ConfigReloader, ConfigWatcher
import asyncio

class DynamicConfigManager:
    """동적 설정 관리자"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
        self.reloader = ConfigReloader()
        self.watcher = ConfigWatcher(config_path)
        self.callbacks = []
    
    async def start(self):
        """설정 감시 시작"""
        # 초기 로드
        self.config = await self.load_config()
        
        # 변경 감시
        self.watcher.on_change(self.on_config_change)
        await self.watcher.start()
    
    async def load_config(self) -> AppConfig:
        """설정 파일 로드"""
        import yaml
        
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        
        return AppConfig(**data)
    
    async def on_config_change(self, event):
        """설정 변경 처리"""
        print(f"설정 파일 변경 감지: {event}")
        
        try:
            # 새 설정 로드
            new_config = await self.load_config()
            
            # 검증
            if self.validate_config(new_config):
                old_config = self.config
                self.config = new_config
                
                # 콜백 실행
                for callback in self.callbacks:
                    await callback(old_config, new_config)
                
                print("설정 재로딩 완료")
            else:
                print("설정 검증 실패")
                
        except Exception as e:
            print(f"설정 재로딩 실패: {e}")
    
    def validate_config(self, config: AppConfig) -> bool:
        """설정 검증"""
        # 커스텀 검증 로직
        if config.workers < 1:
            return False
        
        if config.port < 1024 and not config.debug:
            return False
        
        return True
    
    def on_reload(self, callback):
        """재로딩 콜백 등록"""
        self.callbacks.append(callback)

# 사용 예제
async def main():
    manager = DynamicConfigManager("config.yaml")
    
    # 재로딩 콜백 등록
    async def on_config_reload(old, new):
        print(f"설정 변경: {old.workers} -> {new.workers} workers")
        # 워커 재시작 등의 작업
    
    manager.on_reload(on_config_reload)
    
    # 감시 시작
    await manager.start()
    
    # 애플리케이션 실행
    while True:
        print(f"현재 설정: {manager.config.app_name}")
        await asyncio.sleep(10)
```

### Feature Flags (기능 플래그)

```python
from rfs.core.config import FeatureFlags
from enum import Enum
from typing import Dict, Any

class Feature(str, Enum):
    """기능 플래그 정의"""
    NEW_UI = "new_ui"
    BETA_API = "beta_api"
    ADVANCED_SEARCH = "advanced_search"
    DARK_MODE = "dark_mode"

class FeatureFlagManager:
    """기능 플래그 관리"""
    
    def __init__(self):
        self.flags: Dict[Feature, bool] = {}
        self.user_overrides: Dict[str, Dict[Feature, bool]] = {}
        self.rollout_percentages: Dict[Feature, int] = {}
    
    def set_flag(self, feature: Feature, enabled: bool):
        """전역 플래그 설정"""
        self.flags[feature] = enabled
    
    def set_rollout(self, feature: Feature, percentage: int):
        """점진적 롤아웃 설정"""
        self.rollout_percentages[feature] = percentage
    
    def is_enabled(
        self,
        feature: Feature,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """기능 활성화 여부 확인"""
        
        # 사용자별 오버라이드 확인
        if user_id and user_id in self.user_overrides:
            if feature in self.user_overrides[user_id]:
                return self.user_overrides[user_id][feature]
        
        # 롤아웃 퍼센티지 확인
        if feature in self.rollout_percentages:
            percentage = self.rollout_percentages[feature]
            if user_id:
                # 사용자 ID 기반 해시로 일관된 롤아웃
                import hashlib
                hash_val = int(hashlib.md5(
                    f"{feature}:{user_id}".encode()
                ).hexdigest(), 16)
                return (hash_val % 100) < percentage
        
        # 전역 플래그 확인
        return self.flags.get(feature, False)
    
    def enable_for_user(self, user_id: str, feature: Feature):
        """특정 사용자에게 기능 활성화"""
        if user_id not in self.user_overrides:
            self.user_overrides[user_id] = {}
        self.user_overrides[user_id][feature] = True

# 사용 예제
flags = FeatureFlagManager()

# 전역 설정
flags.set_flag(Feature.DARK_MODE, True)

# 점진적 롤아웃 (30% 사용자)
flags.set_rollout(Feature.NEW_UI, 30)

# 베타 테스터에게만 활성화
flags.enable_for_user("beta_user_123", Feature.BETA_API)

# 확인
if flags.is_enabled(Feature.NEW_UI, user_id="user_456"):
    print("새 UI 표시")
else:
    print("기존 UI 표시")
```

### 설정 검증 및 스키마

```python
from pydantic import validator, root_validator
from typing import Optional

class ValidatedConfig(BaseConfig):
    """검증된 설정"""
    
    # 필드 정의
    email: str
    url: str
    port: int
    rate_limit: int
    
    # 이메일 검증
    @validator("email")
    def validate_email(cls, v):
        import re
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, v):
            raise ValueError(f"유효하지 않은 이메일: {v}")
        return v
    
    # URL 검증
    @validator("url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"유효하지 않은 URL: {v}")
        return v
    
    # 포트 범위 검증
    @validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError(f"포트는 1-65535 범위여야 함: {v}")
        return v
    
    # 복합 검증
    @root_validator
    def validate_combination(cls, values):
        port = values.get("port")
        url = values.get("url")
        
        if port and url:
            if port < 1024 and not url.startswith("https://"):
                raise ValueError("1024 미만 포트는 HTTPS 필요")
        
        return values
```

## 🎨 베스트 프랙티스

### 1. 환경 분리

```python
# 환경별 설정 파일
# config/
#   ├── base.py      # 공통 설정
#   ├── dev.py       # 개발 환경
#   ├── staging.py   # 스테이징
#   └── prod.py      # 프로덕션

# base.py
class BaseConfig:
    APP_NAME = "RFS"
    VERSION = "1.0.0"

# dev.py
from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    DATABASE_URL = "sqlite:///dev.db"

# prod.py
from .base import BaseConfig

class ProductionConfig(BaseConfig):
    DEBUG = False
    DATABASE_URL = os.getenv("DATABASE_URL")
```

### 2. 비밀 관리

```python
# ❌ 나쁜 예 - 하드코딩
API_KEY = "sk-1234567890abcdef"

# ✅ 좋은 예 - 환경 변수/Secret Manager
API_KEY = os.getenv("API_KEY")
# 또는
API_KEY = await secret_manager.get_secret("api-key")
```

### 3. 설정 캐싱

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """설정 싱글톤"""
    return AppConfig()

# 사용
config = get_config()
```

## ⚠️ 주의사항

### 1. 비밀 노출 방지
- 절대 비밀 키를 코드에 하드코딩하지 않음
- .env 파일을 .gitignore에 추가
- 로그에 비밀 정보 출력 금지

### 2. 타입 안전성
- 모든 설정 필드에 타입 힌트 사용
- Pydantic 검증 활용
- 런타임 타입 체크

### 3. 설정 재로딩
- 재로딩 시 서비스 중단 최소화
- 롤백 메커니즘 준비
- 설정 변경 이력 관리

## 🔗 관련 문서
- [환경 프로파일](./17-profiles.md)
- [비밀 관리](./11-security.md)
- [모니터링](./08-monitoring.md)