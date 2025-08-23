# RFS Framework 마이그레이션 가이드

이 가이드는 이전 버전에서 RFS Framework 4.0으로의 마이그레이션 과정을 단계별로 안내합니다.

## 📋 Migration Overview

### 주요 변경사항 요약

| 영역 | 이전 버전 | 4.0 | 영향도 |
|------|-----------|-----|--------|
| **에러 핸들링** | 예외 기반 | Result 패턴 | 🔴 **높음** |
| **비동기 처리** | 선택적 async | async-first | 🔴 **높음** |
| **타입 시스템** | 선택적 타입 힌트 | 완전한 타입 안전성 | 🟡 **보통** |
| **설정 관리** | YAML 기반 | TOML 기반 | 🟡 **보통** |
| **종속성** | Python 3.8+ | Python 3.10+ | 🔴 **높음** |

### 마이그레이션 난이도
- **Small Projects** (< 1000 LOC): 1-2일
- **Medium Projects** (1000-10000 LOC): 1-2주  
- **Large Projects** (10000+ LOC): 2-4주

## 🚀 Pre-Migration Checklist

### 1. 환경 준비
```bash
# Python 버전 확인 (3.10+ 필수)
python --version

# 현재 의존성 백업
pip freeze > requirements_v3_backup.txt

# 새 가상환경 생성
python -m venv venv_v4
source venv_v4/bin/activate

# RFS Framework 설치
pip install rfs-framework
```

### 2. 코드 분석
```bash
# v3 사용 패턴 분석
grep -r "from rfs" . --include="*.py"
grep -r "import rfs" . --include="*.py"

# 동기 함수 식별
grep -r "def " . --include="*.py" | grep -v "async def"

# 예외 처리 패턴 식별
grep -r "try:" . --include="*.py"
grep -r "except" . --include="*.py"
```

## 🔧 Step-by-Step Migration

### Step 1: 의존성 업데이트

#### requirements.txt 변경
```diff
# Before (v3.x)
- rfs-framework==3.5.2
- python-dotenv==0.19.0
- pydantic==1.10.2

# After (v4.0)
+ rfs-framework-v4==4.0.0
+ python-dotenv>=1.0.0
+ pydantic>=2.5.0
```

#### pyproject.toml 사용 권장
```toml
[project]
name = "my-project"
version = "1.0.0"
dependencies = [
    "rfs-framework-v4==4.0.0",
    "pydantic>=2.5.0",
]
```

### Step 2: Import 경로 변경

#### 기본 Import 변경
```python
# Before (v3.x)
from rfs.core import BaseService
from rfs.config import Config
from rfs.utils import logger

# After (v4.0)
from rfs_v4.core import Result, Config
from rfs_v4.reactive import Mono, Flux
import logging

logger = logging.getLogger(__name__)
```

#### 주요 Import 매핑
```python
# v3.x → v4.0 Import 매핑표
v3_imports = {
    "rfs.core.BaseService": "rfs_v4.core.Result",
    "rfs.config.Config": "rfs_v4.core.Config", 
    "rfs.async_utils": "rfs_v4.reactive",
    "rfs.state": "rfs_v4.state_machine",
    "rfs.events": "rfs_v4.events",
}
```

### Step 3: Result 패턴 적용

이것이 가장 중요한 변경사항입니다. 모든 에러 처리가 예외에서 Result 패턴으로 변경됩니다.

#### 기본 함수 변경
```python
# Before (v3.x) - 예외 기반
def get_user(user_id: int) -> dict:
    if user_id < 1:
        raise ValueError("Invalid user ID")
    
    user = database.get_user(user_id)
    if not user:
        raise NotFoundError("User not found")
    
    return user

# After (v4.0) - Result 패턴
async def get_user(user_id: int) -> Result[dict, str]:
    if user_id < 1:
        return Result.failure("Invalid user ID")
    
    user_result = await database.get_user(user_id)
    if user_result.is_failure():
        return Result.failure("User not found")
    
    return Result.success(user_result.value)
```

#### 예외 처리를 Result로 변환
```python
# Before (v3.x)
def process_order(order_data: dict) -> dict:
    try:
        # 주문 검증
        if not order_data.get('items'):
            raise ValueError("No items in order")
        
        # 재고 확인
        for item in order_data['items']:
            stock = inventory.check_stock(item['id'])
            if stock < item['quantity']:
                raise InsufficientStockError(f"Not enough stock for {item['name']}")
        
        # 주문 생성
        order = Order.create(order_data)
        return order.to_dict()
        
    except ValueError as e:
        raise BadRequestError(str(e))
    except InsufficientStockError as e:
        raise ConflictError(str(e))

# After (v4.0)
async def process_order(order_data: dict) -> Result[dict, str]:
    # 주문 검증
    if not order_data.get('items'):
        return Result.failure("No items in order")
    
    # 재고 확인을 반응형 스트림으로 처리
    stock_check = await (
        Flux.from_iterable(order_data['items'])
        .flat_map(lambda item: check_item_stock(item))
        .collect_list()
        .to_result()
    )
    
    if stock_check.is_failure():
        return stock_check
    
    # 주문 생성
    order_result = await Order.create_async(order_data)
    return order_result.map(lambda order: order.to_dict())

async def check_item_stock(item: dict) -> Result[dict, str]:
    stock_result = await inventory.check_stock_async(item['id'])
    if stock_result.is_failure():
        return stock_result
    
    if stock_result.value < item['quantity']:
        return Result.failure(f"Not enough stock for {item['name']}")
    
    return Result.success(item)
```

### Step 4: 비동기화 (Async-First)

모든 공개 메서드를 비동기로 변경해야 합니다.

#### 서비스 클래스 변경
```python
# Before (v3.x)
class UserService(BaseService):
    def get_user(self, user_id: int) -> dict:
        return self.db.query("SELECT * FROM users WHERE id = ?", user_id)
    
    def create_user(self, user_data: dict) -> dict:
        user_id = self.db.insert("users", user_data)
        return self.get_user(user_id)
    
    def update_user(self, user_id: int, updates: dict) -> dict:
        self.db.update("users", user_id, updates)
        return self.get_user(user_id)

# After (v4.0)
class UserService:
    def __init__(self, db_pool):
        self.db = db_pool
    
    async def get_user(self, user_id: int) -> Result[dict, str]:
        if user_id < 1:
            return Result.failure("Invalid user ID")
        
        query_result = await self.db.query_one(
            "SELECT * FROM users WHERE id = $1", user_id
        )
        
        if not query_result:
            return Result.failure("User not found")
        
        return Result.success(dict(query_result))
    
    async def create_user(self, user_data: dict) -> Result[dict, str]:
        # 입력 검증을 반응형으로 처리
        validation_result = await self._validate_user_data(user_data)
        if validation_result.is_failure():
            return validation_result
        
        # 사용자 생성
        user_id_result = await self.db.insert("users", user_data)
        if user_id_result.is_failure():
            return Result.failure("Failed to create user")
        
        # 생성된 사용자 조회
        return await self.get_user(user_id_result.value)
    
    async def update_user(self, user_id: int, updates: dict) -> Result[dict, str]:
        # 사용자 존재 확인
        user_result = await self.get_user(user_id)
        if user_result.is_failure():
            return user_result
        
        # 업데이트 실행
        update_result = await self.db.update("users", user_id, updates)
        if update_result.is_failure():
            return Result.failure("Failed to update user")
        
        # 업데이트된 사용자 조회
        return await self.get_user(user_id)
    
    async def _validate_user_data(self, data: dict) -> Result[dict, str]:
        return await (
            Mono.just(data)
            .map(self._validate_email)
            .flat_map(self._validate_username)
            .to_result()
        )
    
    def _validate_email(self, data: dict) -> dict:
        if not data.get('email') or '@' not in data['email']:
            raise ValueError("Invalid email")
        return data
    
    async def _validate_username(self, data: dict) -> dict:
        username = data.get('username')
        if not username or len(username) < 3:
            raise ValueError("Username too short")
        
        # 중복 확인
        existing = await self.db.query_one(
            "SELECT id FROM users WHERE username = $1", username
        )
        if existing:
            raise ValueError("Username already exists")
        
        return data
```

### Step 5: 설정 파일 변경

#### YAML에서 TOML로 변경
```yaml
# Before (config.yaml)
database:
  host: localhost
  port: 5432
  name: myapp
  
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
cache:
  redis_url: redis://localhost:6379
  ttl: 3600
```

```toml
# After (config.toml)
[database]
host = "localhost"
port = 5432
name = "myapp"

[logging]
level = "INFO"
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

[cache]
redis_url = "redis://localhost:6379"
ttl = 3600

# 환경별 설정
[development]
extends = "base"
log_level = "DEBUG"

[production] 
extends = "base"
log_level = "INFO"
```

#### 설정 로딩 변경
```python
# Before (v3.x)
from rfs.config import Config

config = Config.load("config.yaml")
db_host = config.database.host

# After (v4.0)
from rfs_v4.core import Config, ConfigProfile

config = Config.load("config.toml")
db_config = config.get_section("database")
db_host = db_config["host"]
```

### Step 6: 반응형 프로그래밍 활용

v4.0의 핵심 기능인 반응형 프로그래밍을 활용하여 비동기 처리를 개선합니다.

#### 데이터 스트림 처리
```python
# Before (v3.x) - 순차 처리
def process_users(user_ids: List[int]) -> List[dict]:
    results = []
    for user_id in user_ids:
        try:
            user = get_user(user_id)
            processed = process_user_data(user)
            results.append(processed)
        except Exception as e:
            logger.error(f"Failed to process user {user_id}: {e}")
    return results

# After (v4.0) - 반응형 스트림
async def process_users(user_ids: List[int]) -> Result[List[dict], str]:
    return await (
        Flux.from_iterable(user_ids)
        .flat_map(lambda user_id: get_user(user_id))  # 병렬 처리
        .map(lambda user: process_user_data(user))
        .filter(lambda result: result.is_success())  # 성공한 것만 필터링
        .map(lambda result: result.value)
        .collect_list()
        .to_result()
    )
```

#### 에러 처리 체인
```python
# Before (v3.x)
def create_order_workflow(order_data: dict) -> dict:
    try:
        # 1. 검증
        validated_data = validate_order(order_data)
        
        # 2. 재고 확인
        check_inventory(validated_data['items'])
        
        # 3. 결제 처리
        payment = process_payment(validated_data['payment'])
        
        # 4. 주문 생성
        order = create_order(validated_data)
        
        # 5. 재고 차감
        update_inventory(validated_data['items'])
        
        # 6. 이메일 발송
        send_confirmation_email(order)
        
        return order
        
    except Exception as e:
        logger.error(f"Order creation failed: {e}")
        raise

# After (v4.0) - 반응형 체인
async def create_order_workflow(order_data: dict) -> Result[dict, str]:
    return await (
        Mono.just(order_data)
        .flat_map(lambda data: validate_order_async(data))
        .flat_map(lambda data: check_inventory_async(data))
        .flat_map(lambda data: process_payment_async(data))
        .flat_map(lambda data: create_order_async(data))
        .flat_map(lambda order: update_inventory_async(order))
        .flat_map(lambda order: send_confirmation_email_async(order))
        .on_error_resume(lambda error: handle_order_error(error))
        .to_result()
    )

async def handle_order_error(error: Exception) -> Result[dict, str]:
    logger.error(f"Order workflow failed: {error}")
    # 보상 트랜잭션 실행
    await rollback_order_changes()
    return Result.failure(f"Order creation failed: {str(error)}")
```

### Step 7: 상태 머신 활용

복잡한 비즈니스 로직을 상태 머신으로 변환합니다.

#### 주문 상태 관리
```python
# Before (v3.x) - if/else 기반
class Order:
    def __init__(self, data):
        self.status = "pending"
        self.data = data
    
    def process_payment(self):
        if self.status != "pending":
            raise InvalidStateError("Cannot process payment")
        
        # 결제 처리 로직
        self.status = "paid"
    
    def ship_order(self):
        if self.status != "paid":
            raise InvalidStateError("Cannot ship unpaid order")
        
        # 배송 처리 로직
        self.status = "shipped"

# After (v4.0) - 상태 머신 
from rfs_v4.state_machine import StateMachine, State, Transition

class OrderStateMachine:
    def __init__(self):
        self.machine = StateMachine(
            initial_state=State("pending"),
            states=[
                State("pending"),
                State("paid"), 
                State("shipped"),
                State("delivered"),
                State("cancelled")
            ],
            transitions=[
                Transition("pending", "pay", "paid"),
                Transition("paid", "ship", "shipped"), 
                Transition("shipped", "deliver", "delivered"),
                Transition("pending", "cancel", "cancelled"),
                Transition("paid", "cancel", "cancelled")
            ]
        )
    
    async def process_payment(self, order_id: str) -> Result[str, str]:
        # 결제 로직
        payment_result = await self._process_payment_logic(order_id)
        if payment_result.is_failure():
            return payment_result
        
        # 상태 전환
        transition_result = await self.machine.dispatch("pay")
        if transition_result.is_failure():
            return Result.failure("Invalid state for payment")
        
        return Result.success("Payment processed successfully")
```

## 🧪 Testing Migration

테스트 코드도 함께 마이그레이션해야 합니다.

### 테스트 프레임워크 변경
```python
# Before (v3.x)
import unittest
from unittest.mock import Mock, patch

class TestUserService(unittest.TestCase):
    def setUp(self):
        self.service = UserService()
    
    def test_get_user_success(self):
        user = self.service.get_user(1)
        self.assertIsInstance(user, dict)
        self.assertEqual(user['id'], 1)
    
    def test_get_user_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.get_user(999)

# After (v4.0)
import pytest
import asyncio
from unittest.mock import AsyncMock

class TestUserService:
    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        return UserService(mock_db)
    
    async def test_get_user_success(self, service):
        service.db.query_one.return_value = {"id": 1, "name": "John"}
        
        result = await service.get_user(1)
        
        assert result.is_success()
        assert result.value['id'] == 1
    
    async def test_get_user_not_found(self, service):
        service.db.query_one.return_value = None
        
        result = await service.get_user(999)
        
        assert result.is_failure()
        assert "not found" in result.error
```

### 반응형 스트림 테스트
```python
# v4.0 반응형 스트림 테스트
async def test_process_users_reactive():
    user_ids = [1, 2, 3, 4, 5]
    
    result = await (
        Flux.from_iterable(user_ids)
        .map(lambda x: x * 2)
        .filter(lambda x: x % 4 == 0)
        .collect_list()
        .to_result()
    )
    
    assert result.is_success()
    assert result.value == [4, 8]  # 2*2=4, 4*2=8
```

## 🚀 Performance Optimization

마이그레이션 후 성능을 최적화하는 방법입니다.

### 반응형 스트림 최적화
```python
# 병렬 처리 최적화
async def process_large_dataset(items: List[dict]) -> Result[List[dict], str]:
    return await (
        Flux.from_iterable(items)
        .buffer(100)  # 배치 처리로 메모리 절약
        .flat_map(
            lambda batch: Flux.from_iterable(batch)
            .map(process_item)
            .parallel(max_concurrency=10)  # 병렬 처리
        )
        .collect_list()
        .timeout(30)  # 타임아웃 설정
        .to_result()
    )
```

### 캐싱 활용
```python
from rfs_v4.core import Cache

@Cache.memoize(ttl=3600)  # 1시간 캐시
async def expensive_calculation(params: dict) -> Result[dict, str]:
    # 비용이 큰 연산
    pass
```

## 📊 Migration Checklist

### 코드 변경사항 체크리스트

- [ ] **Import 경로**: 모든 `rfs` import를 `rfs_v4`로 변경
- [ ] **Result 패턴**: 모든 예외 처리를 Result 패턴으로 변경
- [ ] **비동기화**: 모든 공개 메서드를 async로 변경
- [ ] **타입 힌트**: 완전한 타입 어노테이션 추가
- [ ] **설정 파일**: YAML을 TOML로 변경
- [ ] **테스트 코드**: async 테스트로 변경

### 기능별 체크리스트

#### Core 기능
- [ ] Result 패턴 구현 완료
- [ ] 설정 관리 시스템 마이그레이션
- [ ] 의존성 주입 패턴 적용

#### Reactive Programming
- [ ] Mono/Flux 스트림 활용
- [ ] 에러 처리 체인 구현  
- [ ] 병렬 처리 최적화

#### State Management
- [ ] 상태 머신 패턴 적용
- [ ] 액션 기반 상태 변경
- [ ] 상태 영속화 구현

#### Cloud Native
- [ ] Cloud Run 설정 업데이트
- [ ] 헬스체크 엔드포인트 추가
- [ ] 모니터링 메트릭 설정

### 테스트 체크리스트

- [ ] **단위 테스트**: 모든 테스트를 async로 변경
- [ ] **통합 테스트**: Result 패턴 검증 추가
- [ ] **성능 테스트**: 반응형 스트림 성능 검증
- [ ] **E2E 테스트**: 전체 워크플로우 검증

## 🐛 Common Migration Issues

### 자주 발생하는 문제들과 해결책

#### 1. "Cannot use Result in sync context"
```python
# 잘못된 사용
def sync_function():
    result = get_user_async(1)  # async 함수를 sync에서 호출
    return result.value

# 올바른 사용  
async def async_function():
    result = await get_user_async(1)
    return result.value
```

#### 2. "Missing await in Result chain"
```python
# 잘못된 사용
result = (
    Mono.just(data)
    .map(process_data)
    .to_result()  # await 누락
)

# 올바른 사용
result = await (
    Mono.just(data)
    .map(process_data)
    .to_result()
)
```

#### 3. "Type annotation conflicts"
```python
# Python 3.10+ 문법 사용
from typing import Union

# 잘못된 사용 (Python 3.8)
def process(data: dict | None) -> str | None:
    pass

# 올바른 사용 (Python 3.10+)
def process(data: dict | None) -> str | None:
    pass

# 또는 하위 호환성을 위해
def process(data: Union[dict, None]) -> Union[str, None]:
    pass
```

## 🔍 Validation Steps

마이그레이션 완료 후 검증 단계입니다.

### 1. 코드 품질 검사
```bash
# 타입 체크
mypy src/

# 린터 검사  
black --check src/
isort --check-only src/
flake8 src/

# 보안 스캔
bandit -r src/
```

### 2. 테스트 실행
```bash
# 모든 테스트 실행
pytest --cov=src tests/

# 커버리지 확인 (90% 이상 권장)
pytest --cov=src --cov-report=html tests/
```

### 3. 성능 벤치마크
```python
import time
import asyncio

async def benchmark_old_vs_new():
    # 기존 방식
    start = time.time()
    old_result = process_users_sync(user_ids)
    old_time = time.time() - start
    
    # 새 방식  
    start = time.time()
    new_result = await process_users_async(user_ids)
    new_time = time.time() - start
    
    print(f"Old: {old_time:.3f}s, New: {new_time:.3f}s")
    print(f"Improvement: {((old_time - new_time) / old_time * 100):.1f}%")
```

## 🎉 Post-Migration

마이그레이션 완료 후 수행할 작업들입니다.

### 1. 성능 모니터링 설정
```python
from rfs_v4.monitoring import MetricsCollector

metrics = MetricsCollector()

# 비즈니스 메트릭 추가
@metrics.track_performance
async def critical_business_function():
    pass

# 에러율 모니터링
@metrics.track_errors
async def error_prone_function():
    pass
```

### 2. 문서 업데이트
- API 문서 업데이트
- 개발 가이드라인 수정
- 배포 가이드 업데이트
- 모니터링 대시보드 설정

### 3. 팀 교육
- Result 패턴 사용법 교육
- 반응형 프로그래밍 패러다임 교육
- 새로운 테스트 방법론 교육
- 성능 최적화 기법 공유

## 📞 Support

마이그레이션 중 문제가 발생하면 다음 리소스를 활용하세요:

- **📖 Documentation**: [docs.rfs-framework.dev](https://docs.rfs-framework.dev)
- **💬 Community**: [Discord](https://discord.gg/rfs-framework)
- **🐛 Issues**: [GitHub Issues](https://github.com/interactord/rfs-framework/issues)
- **📧 Email**: migration-help@rfs-framework.dev

---

**성공적인 마이그레이션을 응원합니다! 🚀**