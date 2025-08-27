# RFS Framework 함수형 개발 3대 필수 규칙

## 🎯 개요

RFS Framework에서 일관된 함수형 개발 패턴을 위한 **3가지 필수 규칙**입니다. 모든 RFS Framework 개발자는 이 규칙을 반드시 준수해야 합니다.

### 📋 3대 필수 규칙

1. **작은 단위 함수형 개발**: 모든 기능을 작은 단위로 분해하고 HOF 라이브러리 적극 활용
2. **파이프라인 기반 통합**: 작은 단위들을 조합할 때 반드시 파이프라인 패턴 사용  
3. **HOF 기반 설정/주입**: 설정 관리와 의존성 주입에서 HOF 패턴 활용

---

## 🔧 규칙 1: 작은 단위 함수형 개발

### 핵심 원칙
- **단일 책임**: 각 함수는 하나의 명확한 역할만 수행
- **HOF 우선**: RFS HOF 라이브러리를 적극적으로 활용
- **불변성**: 데이터 변경 대신 새로운 데이터 생성
- **순수 함수**: 부작용(side-effect) 최소화

### ❌ 나쁜 예: 큰 덩어리 함수

```python
def process_user_registration(user_data):
    """사용자 등록을 처리하는 큰 함수 - 피해야 할 패턴"""
    
    # 데이터 검증
    if not user_data.get("email"):
        raise ValueError("이메일이 필요합니다")
    if "@" not in user_data.get("email", ""):
        raise ValueError("올바른 이메일 형식이 아닙니다")
    if len(user_data.get("password", "")) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다")
    
    # 데이터 정제
    cleaned_data = {}
    cleaned_data["email"] = user_data["email"].lower().strip()
    cleaned_data["name"] = user_data.get("name", "").strip()
    cleaned_data["phone"] = user_data.get("phone", "").replace("-", "")
    
    # 비밀번호 해싱
    import hashlib
    cleaned_data["password"] = hashlib.sha256(
        user_data["password"].encode()
    ).hexdigest()
    
    # 데이터베이스 저장
    try:
        db.users.insert(cleaned_data)
        
        # 환영 이메일 발송
        email_service.send(
            to=cleaned_data["email"],
            subject="환영합니다!",
            template="welcome",
            data={"name": cleaned_data["name"]}
        )
        
        # 로그 기록
        logger.info(f"새 사용자 등록: {cleaned_data['email']}")
        
        return {"success": True, "user_id": cleaned_data["id"]}
        
    except Exception as e:
        logger.error(f"사용자 등록 실패: {e}")
        return {"success": False, "error": str(e)}
```

### ✅ 좋은 예: 작은 단위 함수형 분해

```python
from rfs.hof.core import pipe, curry
from rfs.hof.collections import compact_map, first
from rfs.hof.monads import Maybe, Result
from rfs.core.result import Success, Failure
from typing import Dict, Any

# 1. 검증 함수들 (작은 단위)
def validate_email(email: str) -> Result[str, str]:
    """이메일 유효성을 검증합니다."""
    if not email:
        return Failure("이메일이 필요합니다")
    if "@" not in email:
        return Failure("올바른 이메일 형식이 아닙니다")
    return Success(email)

def validate_password(password: str) -> Result[str, str]:
    """비밀번호 유효성을 검증합니다."""
    if len(password) < 8:
        return Failure("비밀번호는 8자 이상이어야 합니다")
    return Success(password)

def validate_name(name: str) -> Result[str, str]:
    """이름 유효성을 검증합니다."""
    cleaned_name = name.strip()
    if not cleaned_name:
        return Failure("이름이 필요합니다")
    return Success(cleaned_name)

# 2. 데이터 정제 함수들 (작은 단위)
def normalize_email(email: str) -> str:
    """이메일을 정규화합니다."""
    return email.lower().strip()

def normalize_phone(phone: str) -> str:
    """전화번호를 정규화합니다."""
    return phone.replace("-", "").replace(" ", "")

def hash_password(password: str) -> str:
    """비밀번호를 해시화합니다."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

# 3. 비즈니스 로직 함수들 (작은 단위)
def create_user_record(user_data: dict) -> dict:
    """사용자 레코드를 생성합니다."""
    return {
        "email": normalize_email(user_data["email"]),
        "name": user_data["name"].strip(),
        "phone": normalize_phone(user_data.get("phone", "")),
        "password": hash_password(user_data["password"]),
        "created_at": datetime.now().isoformat()
    }

# HOF를 사용한 검증 체인
@curry
def validate_user_field(validator: callable, field_name: str, user_data: dict) -> Result[dict, str]:
    """사용자 데이터의 특정 필드를 검증합니다."""
    field_value = user_data.get(field_name, "")
    return validator(field_value).map(lambda _: user_data)

# 4. 통합 검증 함수 (HOF 활용)
def validate_user_data(user_data: dict) -> Result[dict, str]:
    """사용자 데이터를 종합적으로 검증합니다."""
    # curry를 활용한 부분 적용
    validate_email_field = validate_user_field(validate_email, "email")
    validate_password_field = validate_user_field(validate_password, "password")
    validate_name_field = validate_user_field(validate_name, "name")
    
    # 검증 체인 구성
    return (
        Success(user_data)
        .bind(validate_email_field)
        .bind(validate_password_field) 
        .bind(validate_name_field)
    )

def save_user_to_db(user_record: dict) -> Result[str, str]:
    """사용자를 데이터베이스에 저장합니다."""
    try:
        user_id = db.users.insert(user_record)
        return Success(user_id)
    except Exception as e:
        return Failure(f"저장 실패: {str(e)}")

def send_welcome_email(user_record: dict) -> Result[bool, str]:
    """환영 이메일을 발송합니다."""
    try:
        email_service.send(
            to=user_record["email"],
            subject="환영합니다!",
            template="welcome",
            data={"name": user_record["name"]}
        )
        return Success(True)
    except Exception as e:
        return Failure(f"이메일 발송 실패: {str(e)}")

def log_user_registration(user_record: dict) -> Result[dict, str]:
    """사용자 등록을 로깅합니다."""
    logger.info(f"새 사용자 등록: {user_record['email']}")
    return Success(user_record)
```

---

## 🔗 규칙 2: 파이프라인 기반 통합

### 핵심 원칙
- **pipe() 필수**: 작은 함수들을 조합할 때 반드시 `pipe()` 사용
- **순차 처리**: 데이터가 파이프라인을 통해 단계별로 변환
- **에러 전파**: Result 패턴으로 에러가 안전하게 전파
- **가독성**: 데이터 플로우가 명확하게 표현

### ❌ 나쁜 예: 중첩된 함수 호출

```python
def process_user_registration_bad(user_data):
    """중첩된 함수 호출 - 피해야 할 패턴"""
    
    # 깊은 중첩으로 가독성 저하
    validation_result = validate_user_data(user_data)
    if validation_result.is_failure():
        return validation_result
    
    user_record = create_user_record(validation_result.unwrap())
    
    save_result = save_user_to_db(user_record)
    if save_result.is_failure():
        return save_result
    
    user_id = save_result.unwrap()
    user_record["id"] = user_id
    
    email_result = send_welcome_email(user_record)
    if email_result.is_failure():
        # 이메일 실패는 전체 실패로 처리하지 않음
        logger.warning(f"환영 이메일 실패: {email_result.unwrap_error()}")
    
    log_result = log_user_registration(user_record)
    if log_result.is_failure():
        logger.warning(f"로깅 실패: {log_result.unwrap_error()}")
    
    return Success({"user_id": user_id, "email": user_record["email"]})
```

### ✅ 좋은 예: pipe를 사용한 파이프라인

```python
from rfs.hof.core import pipe, compose
from rfs.hof.collections import compact_map

def process_user_registration(user_data: dict) -> Result[dict, str]:
    """파이프라인을 사용한 사용자 등록 처리"""
    
    # 메인 등록 파이프라인
    registration_pipeline = pipe(
        validate_user_data,                    # 1. 데이터 검증
        lambda result: result.map(create_user_record),  # 2. 사용자 레코드 생성
        lambda result: result.bind(save_user_to_db_with_record),  # 3. DB 저장
        lambda result: result.bind(handle_post_registration)      # 4. 후속 처리
    )
    
    return registration_pipeline(user_data)

def save_user_to_db_with_record(user_record: dict) -> Result[dict, str]:
    """사용자 레코드를 저장하고 ID를 포함한 완전한 레코드를 반환합니다."""
    return (
        save_user_to_db(user_record)
        .map(lambda user_id: {**user_record, "id": user_id})
    )

def handle_post_registration(user_record: dict) -> Result[dict, str]:
    """등록 후 처리를 담당하는 파이프라인"""
    
    # 후속 처리 파이프라인 (실패해도 전체가 실패하지 않음)
    post_processing_pipeline = pipe(
        send_welcome_email_safe,  # 이메일 발송 (실패 허용)
        log_user_registration,    # 로그 기록
    )
    
    # 후속 처리 실행 (실패해도 메인 결과에 영향 없음)
    post_result = post_processing_pipeline(user_record)
    if post_result.is_failure():
        logger.warning(f"후속 처리 실패: {post_result.unwrap_error()}")
    
    # 메인 결과 반환
    return Success({
        "user_id": user_record["id"],
        "email": user_record["email"]
    })

def send_welcome_email_safe(user_record: dict) -> Result[dict, str]:
    """안전한 이메일 발송 (실패해도 파이프라인 중단 안됨)"""
    email_result = send_welcome_email(user_record)
    if email_result.is_failure():
        logger.warning(f"환영 이메일 실패: {email_result.unwrap_error()}")
    
    # 이메일 실패와 관계없이 사용자 레코드 계속 전달
    return Success(user_record)

# 복잡한 데이터 처리 파이프라인 예제
def process_user_batch(user_list: list) -> Result[list, str]:
    """배치 사용자 처리 파이프라인"""
    
    batch_processing_pipeline = pipe(
        lambda users: compact_map(
            lambda user: process_user_registration(user)
                        .map(lambda result: result)
                        .unwrap_or(None),  # 실패한 사용자는 None으로
            users
        ),
        lambda successful_users: Success(successful_users),
        lambda result: result.map(
            lambda users: group_by(lambda u: u.get("department", "기타"), users)
        )
    )
    
    return batch_processing_pipeline(user_list)

# 설정 기반 파이프라인 구성
def create_user_processing_pipeline(config: dict):
    """설정에 따라 동적으로 파이프라인을 구성합니다."""
    
    steps = [validate_user_data]  # 기본 검증은 항상 포함
    
    # 설정에 따라 단계 추가
    if config.get("enable_enrichment"):
        steps.append(lambda result: result.map(enrich_user_data))
    
    if config.get("enable_duplication_check"):
        steps.append(lambda result: result.bind(check_duplicate_user))
    
    steps.extend([
        lambda result: result.map(create_user_record),
        lambda result: result.bind(save_user_to_db_with_record)
    ])
    
    if config.get("send_welcome_email"):
        steps.append(lambda result: result.bind(handle_post_registration))
    
    # 동적으로 구성된 파이프라인 반환
    return pipe(*steps)
```

---

## ⚙️ 규칙 3: HOF 기반 설정/주입

### 핵심 원칙
- **함수형 설정**: 설정 값들을 함수형 방식으로 조합
- **커링 활용**: 설정 값들을 부분 적용으로 주입
- **불변 설정**: 설정 객체를 직접 변경하지 않고 새로운 설정 생성
- **타입 안전성**: 설정 값들의 타입 안전성 보장

### ❌ 나쁜 예: 명령형 설정 관리

```python
# 명령형 설정 - 피해야 할 패턴
class DatabaseConfig:
    def __init__(self):
        self.host = "localhost"
        self.port = 5432
        self.database = "myapp"
        self.username = None
        self.password = None
        self.ssl_enabled = False
        self.pool_size = 10
    
    def apply_environment_overrides(self):
        """환경 변수로 설정 덮어쓰기 - 가변성으로 인한 문제 발생 가능"""
        if os.getenv("DB_HOST"):
            self.host = os.getenv("DB_HOST")
        if os.getenv("DB_PORT"):
            self.port = int(os.getenv("DB_PORT"))
        if os.getenv("DB_NAME"):
            self.database = os.getenv("DB_NAME")
        # ... 계속해서 가변 상태 변경
    
    def validate(self):
        """검증 로직이 설정 클래스에 강결합"""
        errors = []
        if not self.username:
            errors.append("사용자명이 필요합니다")
        if not self.password:
            errors.append("비밀번호가 필요합니다")
        if self.pool_size <= 0:
            errors.append("연결 풀 크기는 양수여야 합니다")
        
        if errors:
            raise ValueError("; ".join(errors))

# 의존성 주입도 명령형으로 처리
def create_database_service():
    config = DatabaseConfig()
    config.apply_environment_overrides()
    config.validate()
    return DatabaseService(config)
```

### ✅ 좋은 예: HOF를 활용한 함수형 설정

```python
from rfs.hof.core import pipe, curry, compose
from rfs.hof.collections import compact_map, fold_left
from rfs.hof.monads import Maybe, Result
from rfs.core.result import Success, Failure
from dataclasses import dataclass
from typing import Dict, Any, Callable

@dataclass(frozen=True)  # 불변 설정 객체
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_enabled: bool = False
    pool_size: int = 10
    timeout: int = 30

# 1. 설정 생성 함수들 (작은 단위)
def create_default_database_config() -> DatabaseConfig:
    """기본 데이터베이스 설정을 생성합니다."""
    return DatabaseConfig(
        host="localhost",
        port=5432,
        database="myapp",
        username="user",
        password="password"
    )

@curry
def override_config_field(field_name: str, new_value: Any, config: DatabaseConfig) -> DatabaseConfig:
    """설정 필드를 함수형으로 덮어씁니다."""
    return dataclasses.replace(config, **{field_name: new_value})

def load_env_value(env_key: str, converter: Callable = str) -> Maybe[Any]:
    """환경 변수를 안전하게 로드합니다."""
    env_value = os.getenv(env_key)
    if env_value is None:
        return Maybe.nothing()
    
    try:
        return Maybe.just(converter(env_value))
    except (ValueError, TypeError):
        return Maybe.nothing()

# 2. 설정 검증 함수들 (작은 단위)
@curry
def validate_config_field(field_name: str, validator: Callable, config: DatabaseConfig) -> Result[DatabaseConfig, str]:
    """설정 필드를 검증합니다."""
    field_value = getattr(config, field_name)
    if not validator(field_value):
        return Failure(f"잘못된 {field_name}: {field_value}")
    return Success(config)

def is_valid_host(host: str) -> bool:
    """호스트명 유효성을 검사합니다."""
    return bool(host and len(host.strip()) > 0)

def is_valid_port(port: int) -> bool:
    """포트 번호 유효성을 검사합니다."""
    return isinstance(port, int) and 1 <= port <= 65535

def is_positive_int(value: int) -> bool:
    """양의 정수인지 검사합니다."""
    return isinstance(value, int) and value > 0

# 3. 환경 변수 적용 파이프라인
def apply_environment_overrides(config: DatabaseConfig) -> DatabaseConfig:
    """환경 변수를 함수형으로 적용합니다."""
    
    # 환경 변수 매핑과 변환기 정의
    env_mappings = [
        ("DB_HOST", "host", str),
        ("DB_PORT", "port", int),
        ("DB_NAME", "database", str),
        ("DB_USER", "username", str),
        ("DB_PASSWORD", "password", str),
        ("DB_SSL", "ssl_enabled", lambda x: x.lower() == 'true'),
        ("DB_POOL_SIZE", "pool_size", int),
        ("DB_TIMEOUT", "timeout", int),
    ]
    
    # 환경 변수 적용 파이프라인
    def apply_env_override(config: DatabaseConfig, mapping: tuple) -> DatabaseConfig:
        env_key, field_name, converter = mapping
        
        env_value = load_env_value(env_key, converter)
        if env_value.is_just():
            return override_config_field(field_name, env_value.unwrap(), config)
        return config
    
    # fold_left를 사용하여 모든 환경 변수를 순차적으로 적용
    return fold_left(apply_env_override, config, env_mappings)

# 4. 설정 검증 파이프라인
def validate_database_config(config: DatabaseConfig) -> Result[DatabaseConfig, str]:
    """데이터베이스 설정을 종합적으로 검증합니다."""
    
    validation_pipeline = pipe(
        validate_config_field("host", is_valid_host),
        lambda result: result.bind(validate_config_field("port", is_valid_port)),
        lambda result: result.bind(validate_config_field("pool_size", is_positive_int)),
        lambda result: result.bind(validate_config_field("timeout", is_positive_int)),
    )
    
    return validation_pipeline(config)

# 5. 설정 로드 마스터 파이프라인
def load_database_config() -> Result[DatabaseConfig, str]:
    """데이터베이스 설정을 로드하는 전체 파이프라인"""
    
    config_pipeline = pipe(
        create_default_database_config,     # 기본 설정 생성
        apply_environment_overrides,        # 환경 변수 적용
        validate_database_config,           # 검증
    )
    
    return config_pipeline()

# 6. 커링을 활용한 의존성 주입
@curry
def create_service_with_config(service_factory: Callable, config: DatabaseConfig):
    """설정을 주입하여 서비스를 생성합니다."""
    return service_factory(config)

@curry  
def create_database_service(config: DatabaseConfig) -> Result[DatabaseService, str]:
    """데이터베이스 서비스를 생성합니다."""
    try:
        return Success(DatabaseService(config))
    except Exception as e:
        return Failure(f"서비스 생성 실패: {str(e)}")

@curry
def create_cache_service(config: DatabaseConfig) -> Result[CacheService, str]:
    """캐시 서비스를 생성합니다."""
    # 데이터베이스 설정을 기반으로 캐시 설정 추출
    cache_config = CacheConfig(
        host=config.host,
        port=config.port + 1000,  # 캐시는 DB 포트 + 1000
        timeout=config.timeout
    )
    
    try:
        return Success(CacheService(cache_config))
    except Exception as e:
        return Failure(f"캐시 서비스 생성 실패: {str(e)}")

# 7. 서비스 초기화 파이프라인
def initialize_services() -> Result[dict, str]:
    """모든 서비스를 초기화하는 파이프라인"""
    
    def create_all_services(config: DatabaseConfig) -> Result[dict, str]:
        """설정을 기반으로 모든 서비스를 생성합니다."""
        
        # 커링을 활용한 서비스 팩토리들
        db_service_factory = create_service_with_config(create_database_service)
        cache_service_factory = create_service_with_config(create_cache_service)
        
        # 각 서비스 생성
        db_result = db_service_factory(config)
        cache_result = cache_service_factory(config)
        
        # 모든 서비스가 성공적으로 생성되었는지 확인
        if db_result.is_failure():
            return db_result
        if cache_result.is_failure():
            return cache_result
        
        return Success({
            "database": db_result.unwrap(),
            "cache": cache_result.unwrap()
        })
    
    # 전체 초기화 파이프라인
    initialization_pipeline = pipe(
        load_database_config,               # 설정 로드
        lambda result: result.bind(create_all_services),  # 서비스 생성
    )
    
    return initialization_pipeline()

# 8. 동적 설정 업데이트 (함수형 방식)
@curry
def update_config_section(section_updates: Dict[str, Any], config: DatabaseConfig) -> DatabaseConfig:
    """설정의 여러 필드를 한번에 업데이트합니다."""
    return dataclasses.replace(config, **section_updates)

def apply_runtime_config_updates(config: DatabaseConfig, updates: list) -> DatabaseConfig:
    """런타임 설정 업데이트를 적용합니다."""
    
    # 업데이트 함수들의 파이프라인을 동적으로 구성
    update_pipeline = pipe(*[
        update_config_section(update_dict) 
        for update_dict in updates
    ])
    
    return update_pipeline(config)

# 실제 사용 예제
def example_usage():
    """설정 및 주입 시스템 사용 예제"""
    
    # 1. 서비스 초기화
    services_result = initialize_services()
    
    if services_result.is_failure():
        logger.error(f"서비스 초기화 실패: {services_result.unwrap_error()}")
        return
    
    services = services_result.unwrap()
    db_service = services["database"]
    cache_service = services["cache"]
    
    # 2. 런타임 설정 업데이트 예제
    runtime_updates = [
        {"pool_size": 20},       # 연결 풀 크기 증가
        {"timeout": 45},         # 타임아웃 증가
    ]
    
    updated_config = apply_runtime_config_updates(
        db_service.config, 
        runtime_updates
    )
    
    # 3. 업데이트된 설정으로 새 서비스 생성
    new_service_result = create_database_service(updated_config)
    if new_service_result.is_success():
        db_service = new_service_result.unwrap()
        logger.info("설정이 업데이트된 서비스로 교체되었습니다")
```

---

## 📋 실무 적용 체크리스트

### ✅ 규칙 1: 작은 단위 함수형 개발
- [ ] 각 함수가 **단일 책임**을 가지고 있는가?
- [ ] 함수의 길이가 **20줄 이하**인가?
- [ ] **RFS HOF 라이브러리**를 적극 활용했는가?
- [ ] **부작용(side-effect)**이 최소화되었는가?
- [ ] 함수가 **순수함수**에 가까운가?
- [ ] **불변 데이터**를 사용하고 있는가?

### ✅ 규칙 2: 파이프라인 기반 통합
- [ ] 작은 함수들을 조합할 때 **pipe()**를 사용했는가?
- [ ] 데이터가 **단계별로 변환**되고 있는가?
- [ ] **Result 패턴**으로 에러가 안전하게 전파되는가?
- [ ] 파이프라인의 **데이터 플로우**가 명확한가?
- [ ] 중첩된 함수 호출을 **피했는가**?
- [ ] 복잡한 로직이 **여러 단계로 분해**되었는가?

### ✅ 규칙 3: HOF 기반 설정/주입
- [ ] **커링(curry)**을 설정/주입에 활용했는가?
- [ ] 설정 객체가 **불변(immutable)**한가?
- [ ] 설정 검증에 **함수형 패턴**을 사용했는가?
- [ ] 환경 변수 처리가 **안전하게** 구현되었는가?
- [ ] 의존성 주입이 **타입 안전**한가?
- [ ] 설정 업데이트가 **함수형으로** 구현되었는가?

---

## 🚫 금지 패턴 (Anti-Patterns)

### 1. 큰 덩어리 함수
```python
# ❌ 금지: 여러 책임을 가진 큰 함수
def process_everything(data):
    # 100줄 이상의 복잡한 로직
    pass
```

### 2. 중첩된 조건문/예외처리
```python
# ❌ 금지: 깊은 중첩
try:
    result = operation1()
    try:
        result2 = operation2(result)
        try:
            result3 = operation3(result2)
        except:
            pass
    except:
        pass
except:
    pass
```

### 3. 가변 상태 남용
```python
# ❌ 금지: 가변 상태 직접 변경
config.host = "new_host"
config.port = 5433
config.validate()  # 상태 변경 후 검증
```

### 4. HOF 미활용
```python
# ❌ 금지: HOF 대신 명령형 루프
results = []
for item in items:
    if condition(item):
        results.append(transform(item))
```

---

## 🎯 팀 개발 가이드라인

### 코드 리뷰 시 확인사항
1. **3대 규칙 준수 여부** 확인
2. **HOF 활용도** 점검  
3. **파이프라인 구성** 적절성 검토
4. **함수 분해** 수준 평가

### 신규 기능 개발 프로세스
1. **기능을 작은 단위로 분해** 계획
2. **각 단위별 HOF 패턴** 적용 설계
3. **파이프라인 구조** 설계
4. **구현 및 테스트**
5. **3대 규칙 준수** 검증

### 레거시 코드 리팩토링
1. **현재 코드 분석** 및 문제점 파악
2. **작은 단위로 분해** 가능한 부분 식별
3. **HOF 패턴 적용** 계획 수립
4. **단계적 리팩토링** 실행
5. **테스트를 통한 검증**

---

## 🔍 예외 상황 처리

### 언제 규칙을 유연하게 적용할 수 있는가?

1. **성능이 매우 중요한 핫스팟** 코드
2. **외부 라이브러리와의 인터페이스** 부분
3. **레거시 시스템과의 통합** 지점
4. **프로토타이핑이나 실험적 코드**

### 예외 적용 시 주의사항
- **명확한 주석**으로 예외 사유 기록
- **기술 부채** 이슈로 등록하여 추후 개선 계획
- **팀 전체 논의**를 통한 예외 승인
- **가능한 한 빠른 시일 내** 규칙 준수 코드로 리팩토링

---

## 📚 추가 학습 자료

### RFS Framework 관련 문서
- [HOF 사용 가이드](./16-hof-usage-guide.md)
- [Result 패턴 가이드](./result-pattern-guide.md)
- [파이프라인 설계 패턴](./pipeline-patterns.md)

### 함수형 프로그래밍 참고 자료
- **Swift 표준 라이브러리** 함수형 메서드들
- **Haskell** 함수 합성 패턴
- **F#** 파이프라인 연산자
- **Clojure** 불변 데이터 구조

---

**결론**: 이 3가지 필수 규칙을 통해 RFS Framework에서 **일관되고 유지보수하기 쉬운 함수형 코드**를 작성할 수 있습니다. 모든 개발자는 이 규칙을 숙지하고 일상적인 개발에 적용해야 합니다.