# 로깅 데코레이터 (Logging Decorators)

## 📌 개요

RFS Framework의 로깅 시스템은 데코레이터 기반으로 작업 레벨 로깅과 감사 로깅을 제공합니다. 민감한 데이터 자동 마스킹과 구조화된 로그 포맷을 지원합니다.

## 🎯 핵심 개념

### 로깅 데코레이터 종류
- **@LoggedOperation**: 작업 레벨 로깅
- **@AuditLogged**: 감사 로그 생성
- **@ErrorLogged**: 에러 자동 로깅
- **@PerformanceLogged**: 성능 메트릭 로깅

### 로그 레벨
- **DEBUG**: 디버깅 정보
- **INFO**: 일반 정보
- **WARNING**: 경고
- **ERROR**: 에러
- **CRITICAL**: 치명적 에러

### 감사 이벤트 타입
- **CREATE/READ/UPDATE/DELETE**: CRUD 작업
- **LOGIN/LOGOUT**: 인증 이벤트
- **SECURITY_EVENT**: 보안 관련 이벤트
- **API_CALL**: API 호출

## 📚 API 레퍼런스

### @LoggedOperation 데코레이터

```python
from rfs.core.logging_decorators import LoggedOperation, LogLevel

@LoggedOperation(
    level=LogLevel.INFO,
    include_args=True,
    include_result=False,
    include_timing=True,
    include_errors=True,
    tags={"service": "user_service"}
)
```

| 매개변수 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `level` | `LogLevel` | `INFO` | 로그 레벨 |
| `include_args` | `bool` | `True` | 인자 포함 여부 |
| `include_result` | `bool` | `False` | 결과 포함 여부 |
| `include_timing` | `bool` | `True` | 실행 시간 포함 |
| `include_errors` | `bool` | `True` | 에러 포함 여부 |
| `tags` | `dict` | `None` | 추가 태그 |

### @AuditLogged 데코레이터

```python
from rfs.core.logging_decorators import AuditLogged, AuditEventType

@AuditLogged(
    event_type=AuditEventType.UPDATE,
    resource_type="user",
    include_changes=True,
    include_user_info=True,
    custom_message="사용자 정보 업데이트"
)
```

| 매개변수 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `event_type` | `AuditEventType` | 필수 | 감사 이벤트 타입 |
| `resource_type` | `str` | 필수 | 리소스 타입 |
| `include_changes` | `bool` | `True` | 변경사항 포함 |
| `include_user_info` | `bool` | `True` | 사용자 정보 포함 |
| `custom_message` | `str` | `None` | 커스텀 메시지 |

## 💡 사용 예제

### 기본 작업 로깅

```python
from rfs.core.logging_decorators import LoggedOperation, LogLevel
from rfs.core.result import Result, Success, Failure

@LoggedOperation(
    level=LogLevel.INFO,
    include_timing=True,
    tags={"module": "user_service"}
)
async def create_user(user_data: dict) -> Result[dict, str]:
    """사용자 생성"""
    try:
        # 사용자 생성 로직
        new_user = {
            "id": "user123",
            "name": user_data["name"],
            "email": user_data["email"]
        }
        return Success(new_user)
    except Exception as e:
        return Failure(f"사용자 생성 실패: {str(e)}")

# 실행 시 로그 출력:
# [abc12345] Starting operation: user_service.create_user | Args: ({'name': 'John', 'email': 'jo***@example.com'},) | Kwargs: {}
# [abc12345] Completed operation: user_service.create_user | Duration: 15.30ms
```

### 감사 로깅

```python
from rfs.core.logging_decorators import AuditLogged, AuditEventType

@AuditLogged(
    event_type=AuditEventType.UPDATE,
    resource_type="user",
    include_changes=True
)
async def update_user(user_id: str, updates: dict, user_id: str) -> Result[dict, str]:
    """사용자 정보 업데이트"""
    try:
        # 기존 사용자 조회
        existing_user = await get_user(user_id)
        
        # 업데이트 실행
        updated_user = await update_user_in_db(user_id, updates)
        
        return Success(updated_user)
    except Exception as e:
        return Failure(f"사용자 업데이트 실패: {str(e)}")

# 감사 로그 생성:
# {
#   "audit_id": "550e8400-e29b-41d4-a716-446655440000",
#   "timestamp": "2024-01-15T10:30:00Z",
#   "event_type": "UPDATE",
#   "user_id": "user123",
#   "resource_type": "user",
#   "resource_id": "target_user456",
#   "action": "update_user",
#   "result": "SUCCESS",
#   "changes": {"updated_fields": ["name", "email"]}
# }
```

### 에러 자동 로깅

```python
from rfs.core.logging_decorators import ErrorLogged, LogLevel

@ErrorLogged(
    include_stack_trace=True,
    notify=True,  # 알림 필요
    severity=LogLevel.ERROR
)
async def critical_operation() -> Result[str, str]:
    """중요한 작업"""
    try:
        # 중요한 로직 실행
        result = await perform_critical_task()
        return Success(result)
    except Exception as e:
        # 자동으로 에러 로그 생성됨
        return Failure(str(e))

# 에러 발생 시 로그:
# ERROR: Error ID: def67890 | Function: service.critical_operation | Error: Database connection failed
# DEBUG: [def67890] Stack trace: ...
# CRITICAL: NOTIFICATION REQUIRED: Error ID: def67890 | Function: service.critical_operation | Error: Database connection failed
```

### 복합 로깅 시스템

```python
from rfs.core.logging_decorators import (
    LoggedOperation, 
    AuditLogged, 
    ErrorLogged,
    LogLevel, 
    AuditEventType
)

class UserService:
    @LoggedOperation(
        level=LogLevel.INFO,
        include_timing=True,
        tags={"service": "user", "version": "v1"}
    )
    @AuditLogged(
        event_type=AuditEventType.CREATE,
        resource_type="user",
        include_changes=False
    )
    @ErrorLogged(
        include_stack_trace=True,
        severity=LogLevel.ERROR
    )
    async def register_user(
        self, 
        registration_data: dict,
        user_id: str = None  # 감사 로그용
    ) -> Result[dict, str]:
        """사용자 등록 (다중 로깅 적용)"""
        try:
            # 유효성 검사
            validation_result = await self._validate_registration(registration_data)
            if validation_result.is_failure():
                return validation_result
            
            # 사용자 생성
            user = await self._create_user_in_db(registration_data)
            
            # 환영 이메일 발송
            await self._send_welcome_email(user)
            
            return Success(user)
            
        except Exception as e:
            # ErrorLogged가 자동으로 에러 로깅
            return Failure(f"사용자 등록 실패: {str(e)}")
```

### 민감한 데이터 마스킹

```python
from rfs.core.logging_decorators import LoggedOperation

@LoggedOperation(
    include_args=True,
    include_result=True
)
async def login_user(email: str, password: str, api_key: str) -> Result[dict, str]:
    """사용자 로그인 (민감한 데이터 자동 마스킹)"""
    try:
        # 로그인 로직
        user_token = await authenticate_user(email, password, api_key)
        return Success({"token": user_token, "email": email})
    except Exception as e:
        return Failure(str(e))

# 로그 출력 (자동 마스킹):
# [xyz98765] Starting operation: auth.login_user | Args: ('us***@example.com', '***MASKED***', '***MASKED***')
# [xyz98765] Completed operation: auth.login_user | Result: {'token': '***MASKED***', 'email': 'us***@example.com'}
```

### 감사 로그 조회

```python
from rfs.core.logging_decorators import get_audit_logger, AuditEventType
from datetime import datetime, timedelta

# 감사 로거 가져오기
audit_logger = get_audit_logger()

# 특정 사용자의 감사 로그 조회
user_logs = audit_logger.get_logs(
    user_id="user123",
    start_time=datetime.now() - timedelta(days=7),
    limit=50
)

# 특정 이벤트 타입의 로그 조회
create_logs = audit_logger.get_logs(
    event_type=AuditEventType.CREATE,
    limit=100
)

# 감사 로그 파일 설정
from rfs.core.logging_decorators import set_audit_log_file
set_audit_log_file("/var/log/rfs/audit.log")
```

### 커스텀 로깅 컨텍스트

```python
from rfs.core.logging_decorators import LoggedOperation, OperationContext
from datetime import datetime

@LoggedOperation(
    level=LogLevel.INFO,
    tags={"component": "payment"}
)
async def process_payment(
    payment_data: dict,
    trace_id: str = None  # 분산 트레이싱용
) -> Result[dict, str]:
    """결제 처리"""
    # 컨텍스트 정보는 자동으로 로그에 포함됨
    try:
        result = await execute_payment(payment_data)
        return Success(result)
    except Exception as e:
        return Failure(str(e))

# 실행
await process_payment(
    {"amount": 1000, "currency": "KRW"},
    trace_id="trace-123"
)
```

## 🎨 베스트 프랙티스

### 1. 로깅 레벨 선택

```python
# ✅ 좋은 예 - 적절한 레벨 사용
@LoggedOperation(level=LogLevel.INFO)  # 일반적인 비즈니스 로직
async def get_user_profile(user_id: str):
    pass

@LoggedOperation(level=LogLevel.WARNING)  # 잠재적 문제
async def retry_failed_operation():
    pass

@LoggedOperation(level=LogLevel.ERROR)  # 중요한 실패
async def handle_critical_error():
    pass
```

### 2. 감사 로그 적절한 사용

```python
# ✅ 좋은 예 - 중요한 작업만 감사 로그
@AuditLogged(
    event_type=AuditEventType.DELETE,
    resource_type="user_data",
    include_changes=True
)
async def delete_user_data(user_id: str):
    """중요한 데이터 삭제 - 감사 필요"""
    pass

# ❌ 나쁜 예 - 단순한 조회에 감사 로그
@AuditLogged(event_type=AuditEventType.READ, resource_type="user")
async def get_user_list():
    """단순 조회 - 감사 불필요"""
    pass
```

### 3. 성능 고려사항

```python
# ✅ 좋은 예 - 성능 영향 최소화
@LoggedOperation(
    include_result=False,  # 큰 결과는 제외
    include_args=False     # 민감한 대용량 인자 제외
)
async def process_large_dataset(data: list):
    pass
```

### 4. 태그 활용

```python
# ✅ 좋은 예 - 의미있는 태그 사용
@LoggedOperation(tags={
    "service": "user_management",
    "version": "v2",
    "feature": "registration",
    "environment": "production"
})
async def register_user(user_data: dict):
    pass
```

## ⚠️ 주의사항

### 1. 민감한 데이터 보호
- 비밀번호, API 키, 개인정보는 자동으로 마스킹됨
- 추가 민감 필드가 있다면 마스킹 로직 확장 필요

### 2. 로그 저장소 용량 관리
- 감사 로그는 지속적으로 누적됨
- 정기적인 아카이브 및 정리 정책 수립 필요

### 3. 성능 영향 고려
- `include_result=True`는 성능에 영향을 줄 수 있음
- 대용량 데이터 처리 시 로깅 최소화

### 4. 비동기 함수 지원
- 동기/비동기 함수 모두 지원
- 컨텍스트 관리가 자동으로 처리됨

## 🔗 관련 문서
- [핵심 패턴](./01-core-patterns.md) - Result 패턴과 로깅 통합
- [모니터링](./08-monitoring.md) - 성능 메트릭 로깅
- [보안](./11-security.md) - 보안 감사 로깅
- [접근 제어](./10-access-control.md) - 인증/인가 이벤트 로깅