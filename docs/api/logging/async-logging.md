# AsyncResult 로깅 API

RFS Framework의 AsyncResult 로깅 시스템 API 레퍼런스입니다.

## 모듈 임포트

```python
from rfs.logging.async_logging import (
    AsyncResultLogger,
    AsyncResultLogEntry,
    AsyncResultLogContext,
    LogLevel,
    log_async_chain,
    configure_async_result_logging,
    get_async_result_logger
)
```

## 주요 클래스

### AsyncResultLogger

AsyncResult 전용 로거 클래스입니다.

```python
class AsyncResultLogger:
    def __init__(
        self,
        name: str = "AsyncResultLogger",
        log_level: LogLevel = LogLevel.INFO,
        mask_sensitive: bool = True,
        collect_metrics: bool = True,
        output_format: str = "json"
    )
```

#### 매개변수

- `name`: 로거 이름
- `log_level`: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
- `mask_sensitive`: 민감 데이터 마스킹 활성화
- `collect_metrics`: 성능 메트릭 수집 활성화
- `output_format`: 출력 형식 ("json", "text")

#### 메서드

##### log_chain

AsyncResult 체인에 로깅을 적용합니다.

```python
def log_chain(
    self, 
    operation_name: str, 
    log_level: LogLevel = LogLevel.INFO
):
    def decorator(async_result: AsyncResult[T, E]) -> AsyncResult[T, E]:
        # 로깅이 적용된 AsyncResult 반환
        ...
```

##### log_start

작업 시작을 로깅합니다.

```python
def log_start(
    self,
    operation_name: str,
    context: Optional[Dict[str, Any]] = None
) -> str  # 작업 ID 반환
```

##### log_success

성공 결과를 로깅합니다.

```python
def log_success(
    self,
    operation_name: str,
    result: Any,
    duration_ms: float,
    operation_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
)
```

##### log_error

에러를 로깅합니다.

```python
def log_error(
    self,
    operation_name: str,
    error: Any,
    duration_ms: float,
    operation_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
)
```

#### 사용 예시

```python
# 로거 생성
logger = AsyncResultLogger(
    name="UserService",
    mask_sensitive=True,
    collect_metrics=True
)

# 데코레이터로 체인 로깅
@logger.log_chain("user_registration", LogLevel.INFO)
async def register_user(user_data: dict):
    return await (
        validate_user_data(user_data)
        .bind(hash_password)
        .bind(save_to_database)
        .bind(send_welcome_email)
    )

# 수동 로깅
async def manual_logging_example():
    operation_id = logger.log_start("data_processing")
    
    try:
        result = await process_data()
        logger.log_success("data_processing", result, 150.0, operation_id)
        return result
    except Exception as e:
        logger.log_error("data_processing", str(e), 150.0, operation_id)
        raise
```

### AsyncResultLogEntry

로그 엔트리를 나타내는 데이터 클래스입니다.

```python
@dataclass
class AsyncResultLogEntry:
    timestamp: datetime
    operation_name: str
    operation_id: str
    status: str  # "started", "success", "error"
    duration_ms: Optional[float]
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    context: Optional[Dict[str, Any]]
    metrics: Optional[Dict[str, Any]]
```

#### 속성

- `timestamp`: 로그 생성 시간
- `operation_name`: 작업 이름
- `operation_id`: 고유 작업 ID
- `status`: 작업 상태
- `duration_ms`: 수행 시간 (밀리초)
- `data`: 로그 데이터 (민감 정보 마스킹 적용)
- `error`: 에러 메시지
- `context`: 추가 컨텍스트 정보
- `metrics`: 성능 메트릭

#### 사용 예시

```python
# 로그 엔트리 생성
entry = AsyncResultLogEntry(
    timestamp=datetime.utcnow(),
    operation_name="user_login",
    operation_id="op_123456",
    status="success",
    duration_ms=85.5,
    data={"user_id": 12345, "login_method": "email"},
    error=None,
    context={"ip_address": "192.168.1.1", "user_agent": "..."},
    metrics={"memory_usage": 45.2, "cpu_usage": 12.1}
)

# JSON 직렬화
entry_json = entry.to_json()
```

### AsyncResultLogContext

로그 컨텍스트 관리 클래스입니다.

```python
@dataclass
class AsyncResultLogContext:
    operation_id: str
    operation_name: str
    start_time: datetime
    context: Dict[str, Any]
    parent_operation_id: Optional[str] = None
```

#### 사용 예시

```python
# 컨텍스트 생성 및 관리
async def with_logging_context():
    context = AsyncResultLogContext(
        operation_id="op_789",
        operation_name="order_processing",
        start_time=datetime.utcnow(),
        context={"customer_id": 456, "order_type": "premium"}
    )
    
    async with async_result_log_context(context):
        # 이 블록 내의 모든 로깅은 컨텍스트를 포함
        result = await process_order()
        return result
```

### LogLevel

로그 레벨을 정의하는 열거형입니다.

```python
class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
```

## 주요 함수

### log_async_chain

AsyncResult 체인에 로깅을 적용하는 데코레이터 함수입니다.

```python
def log_async_chain(
    logger: AsyncResultLogger,
    operation_name: str,
    log_level: LogLevel = LogLevel.INFO,
    include_args: bool = False,
    mask_args: bool = True
):
    def decorator(func: Callable[..., Awaitable[AsyncResult[T, E]]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 로깅이 적용된 함수 실행
            ...
```

#### 매개변수

- `logger`: 사용할 AsyncResultLogger 인스턴스
- `operation_name`: 작업 이름
- `log_level`: 로그 레벨
- `include_args`: 함수 인수 포함 여부
- `mask_args`: 인수 마스킹 적용 여부

#### 사용 예시

```python
logger = AsyncResultLogger()

@log_async_chain(logger, "payment_processing", LogLevel.INFO, include_args=True)
async def process_payment(amount: float, card_number: str, cvv: str):
    """결제 처리 (민감 정보 자동 마스킹)"""
    return await (
        validate_card(card_number, cvv)
        .bind(lambda _: charge_amount(amount))
        .bind(lambda charge_id: create_payment_record(charge_id, amount))
    )

# 실제 로그 출력:
# {
#   "operation_name": "payment_processing",
#   "status": "started",
#   "args": {"amount": 100.0, "card_number": "****", "cvv": "***"},
#   "timestamp": "2025-01-01T12:00:00Z"
# }
```

### configure_async_result_logging

AsyncResult 로깅 시스템을 전역적으로 설정합니다.

```python
def configure_async_result_logging(
    log_level: Union[str, LogLevel] = LogLevel.INFO,
    mask_sensitive: bool = True,
    collect_metrics: bool = True,
    output_format: str = "json",
    sensitive_keys: Optional[List[str]] = None,
    log_handler: Optional[logging.Handler] = None
) -> None
```

#### 매개변수

- `log_level`: 전역 로그 레벨
- `mask_sensitive`: 민감 데이터 마스킹 활성화
- `collect_metrics`: 성능 메트릭 수집 활성화
- `output_format`: 출력 형식
- `sensitive_keys`: 마스킹할 추가 키 목록
- `log_handler`: 커스텀 로그 핸들러

#### 사용 예시

```python
# 애플리케이션 시작 시 로깅 설정
configure_async_result_logging(
    log_level=LogLevel.INFO,
    mask_sensitive=True,
    collect_metrics=True,
    output_format="json",
    sensitive_keys=["api_key", "session_token", "private_data"]
)
```

### get_async_result_logger

전역 AsyncResult 로거를 가져옵니다.

```python
def get_async_result_logger(name: str = "default") -> AsyncResultLogger
```

#### 사용 예시

```python
# 전역 로거 사용
logger = get_async_result_logger("payment_service")

@log_async_chain(logger, "refund_processing")
async def process_refund(payment_id: str, amount: float):
    return await handle_refund_logic(payment_id, amount)
```

## 고급 기능

### 민감 데이터 마스킹

자동으로 민감한 데이터를 마스킹합니다.

```python
# 기본 마스킹 키워드
DEFAULT_SENSITIVE_KEYS = [
    "password", "token", "key", "secret", "auth",
    "credential", "private", "card_number", "cvv",
    "ssn", "social_security", "bank_account"
]

# 커스텀 마스킹 규칙
def custom_mask_function(key: str, value: Any) -> str:
    if "email" in key.lower():
        # 이메일 부분 마스킹: test@example.com -> t***@example.com
        email_str = str(value)
        if "@" in email_str:
            local, domain = email_str.split("@")
            masked_local = local[0] + "*" * (len(local) - 1)
            return f"{masked_local}@{domain}"
    
    # 기본 마스킹
    return "*" * len(str(value))
```

### 성능 메트릭 수집

자동으로 성능 메트릭을 수집합니다.

```python
# 수집되는 메트릭
metrics_collected = {
    "execution_time_ms": 150.5,
    "memory_usage_mb": 45.2,
    "cpu_usage_percent": 12.1,
    "gc_collections": 2,
    "thread_count": 8,
    # 분위수 통계 (100회 실행 후)
    "p50_ms": 120.0,
    "p90_ms": 180.0,
    "p95_ms": 200.0,
    "p99_ms": 250.0,
    "max_ms": 320.0,
    "min_ms": 85.0,
    "avg_ms": 145.3,
    "success_rate": 0.95
}
```

### 분산 추적 통합

분산 시스템에서의 추적을 지원합니다.

```python
import opentelemetry.trace as trace
from opentelemetry.trace import set_span_in_context

def with_distributed_tracing():
    tracer = trace.get_tracer(__name__)
    
    @log_async_chain(logger, "distributed_operation")
    async def traced_operation(data: dict):
        # OpenTelemetry 스팬과 함께 로깅
        with tracer.start_as_current_span("process_data") as span:
            span.set_attribute("operation.type", "data_processing")
            span.set_attribute("data.size", len(data))
            
            result = await process_data_async(data)
            
            if result.is_success():
                span.set_status(trace.Status(trace.StatusCode.OK))
            else:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
            
            return result
```

### 구조화된 로깅

JSON 형태의 구조화된 로그를 생성합니다.

```json
{
  "timestamp": "2025-01-01T12:00:00.123Z",
  "level": "INFO",
  "logger": "UserService",
  "operation_name": "user_registration",
  "operation_id": "op_abc123",
  "status": "success",
  "duration_ms": 150.5,
  "data": {
    "user_id": 12345,
    "email": "u***@example.com",
    "registration_type": "email"
  },
  "context": {
    "request_id": "req_xyz789",
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.1"
  },
  "metrics": {
    "memory_usage_mb": 45.2,
    "execution_time_ms": 150.5,
    "cpu_usage_percent": 12.1
  },
  "trace": {
    "trace_id": "abc123def456",
    "span_id": "def456ghi789",
    "parent_span_id": "ghi789jkl012"
  }
}
```

## 에러 처리

### 로깅 에러 처리

```python
class LoggingError(Exception):
    """로깅 관련 에러"""
    pass

class SensitiveDataExposureError(LoggingError):
    """민감 데이터 노출 에러"""
    pass

# 에러 처리 예시
try:
    logger.log_success("operation", sensitive_data)
except SensitiveDataExposureError as e:
    # 민감 데이터가 마스킹되지 않은 경우
    logger.log_error("logging_error", str(e), 0)
    # 안전한 로깅 수행
    safe_logger.log_warning("sensitive_data_detected", {"operation": "masked"})
```

## 성능 최적화

### 비동기 로깅

```python
import asyncio
from asyncio import Queue

class AsyncBatchLogger:
    def __init__(self, batch_size: int = 100, flush_interval: int = 5):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.log_queue = Queue()
        self._start_background_logging()
    
    async def log(self, entry: AsyncResultLogEntry):
        await self.log_queue.put(entry)
    
    async def _background_logger(self):
        batch = []
        while True:
            try:
                # 배치 수집
                entry = await asyncio.wait_for(
                    self.log_queue.get(), 
                    timeout=self.flush_interval
                )
                batch.append(entry)
                
                if len(batch) >= self.batch_size:
                    await self._flush_batch(batch)
                    batch = []
                    
            except asyncio.TimeoutError:
                if batch:
                    await self._flush_batch(batch)
                    batch = []
    
    async def _flush_batch(self, batch: List[AsyncResultLogEntry]):
        # 배치로 로그 기록
        for entry in batch:
            logging.getLogger().info(entry.to_json())
```

---

이 API를 통해 AsyncResult의 실행 과정을 상세하게 로깅하고 모니터링할 수 있습니다. 자세한 사용 예시는 [AsyncResult Web Integration 가이드](../26-asyncresult-web-integration.md)를 참조하세요.