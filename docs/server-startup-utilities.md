# RFS Framework - 서버 시작 유틸리티 가이드

## 📋 개요

이 문서는 RFS Framework 4.5.1에 새롭게 추가된 **서버 시작 유틸리티**들에 대한 종합 가이드입니다.

이 유틸리티들은 실제 프로젝트에서 발견된 서버 시작 오류 패턴들을 바탕으로 개발되었으며, 다음과 같은 문제들을 해결합니다:

- ✅ **HOF 함수 누락** (`with_fallback` 등)
- ✅ **ResultAsync 확장 메서드 부족**
- ✅ **상대 경로 import 오류**
- ✅ **타입 import 누락**
- ✅ **의존성 검증 문제**

## 🎯 해결된 문제들

### 1. HOF 함수 누락 문제

**문제**: `NameError: name 'with_fallback' is not defined`

**해결**: 
```python
from rfs.hof import with_fallback, async_with_fallback

# 동기 fallback 패턴
def load_config():
    raise FileNotFoundError("Config not found")

def default_config(error):
    return {"debug": True}

safe_load = with_fallback(load_config, default_config)
config = safe_load()  # {"debug": True}

# 비동기 fallback 패턴  
async def load_remote_config():
    raise ConnectionError("Remote unavailable")

async def default_async_config(error):
    return {"debug": True, "mode": "local"}

safe_async_load = async_with_fallback(load_remote_config, default_async_config)
config = await safe_async_load()
```

### 2. ResultAsync 확장 메서드 부족

**문제**: `type object 'ResultAsync' has no attribute 'from_error'`

**해결**:
```python
from rfs.core.result import ResultAsync

# 클래스 메서드
error_result = ResultAsync.from_error("connection failed")
success_result = ResultAsync.from_value("data")

# 확장 인스턴스 메서드
async def example():
    # unwrap_or_async
    value = await error_result.unwrap_or_async("default")
    print(value)  # "default"
    
    # bind_async
    async def process_data(data):
        return Success(f"processed_{data}")
    
    processed = success_result.bind_async(process_data)
    result = await processed.to_result()
    
    # map_async
    async def transform(data):
        return data.upper()
    
    transformed = success_result.map_async(transform)
    final = await transformed.to_result()
```

### 3. 서버 시작 검증 및 자동 수정

**문제**: 다양한 import 오류, 타입 누락, 의존성 문제

**해결**:
```python
from rfs.utils.server_startup import validate_rfs_project

# 원클릭 검증 및 수정
result = validate_rfs_project("/path/to/project", auto_fix=True)

if result.is_success():
    report = result.unwrap()
    print(report)
else:
    print(f"검증 실패: {result.unwrap_error()}")
```

## 🚀 주요 기능

### 1. HOF Fallback 패턴

#### 기본 Fallback 패턴
```python
from rfs.hof import with_fallback, safe_call, retry_with_fallback

# 기본 fallback
safe_function = with_fallback(risky_function, fallback_function)

# 안전한 호출 (기본값 반환)
safe_int = safe_call(int, 0, (ValueError, TypeError))
result = safe_int("abc")  # 0

# 재시도 + fallback 조합
reliable_service = retry_with_fallback(
    flaky_service, 
    fallback_service, 
    max_attempts=3,
    delay=0.1
)
```

#### 비동기 Fallback 패턴
```python
from rfs.hof import async_with_fallback, async_retry_with_fallback, async_timeout_with_fallback

# 비동기 fallback
async_safe = async_with_fallback(async_risky, async_fallback)

# 타임아웃 + fallback
fast_service = async_timeout_with_fallback(
    slow_service,
    fast_fallback,
    timeout=5.0
)

# 비동기 재시도 + fallback
reliable_async = async_retry_with_fallback(
    async_flaky_service,
    async_fallback_service,
    max_attempts=3,
    delay=0.1
)
```

### 2. ResultAsync 확장 메서드

#### 클래스 메서드 (Static Factory)
```python
from rfs.core.result import ResultAsync

# 에러로부터 생성
error_result = ResultAsync.from_error("connection_failed")

# 값으로부터 생성  
success_result = ResultAsync.from_value("success_data")
```

#### 확장 인스턴스 메서드
```python
# unwrap_or_async - 비동기 안전한 언래핑
async def safe_unwrap_example():
    success_result = ResultAsync.from_value("data")
    error_result = ResultAsync.from_error("error")
    
    success_value = await success_result.unwrap_or_async("default")  # "data"
    error_value = await error_result.unwrap_or_async("default")      # "default"

# bind_async - 비동기 Result 반환 함수와 바인딩
async def bind_example():
    async def process_async(data: str) -> Result[str, str]:
        if len(data) > 0:
            return Success(f"processed_{data}")
        return Failure("empty_data")
    
    result = ResultAsync.from_value("test")
    processed = result.bind_async(process_async)
    final = await processed.to_result()  # Success("processed_test")

# map_async - 비동기 변환 함수와 매핑
async def map_example():
    async def transform_async(data: str) -> str:
        await asyncio.sleep(0.1)
        return data.upper()
    
    result = ResultAsync.from_value("hello")
    transformed = result.map_async(transform_async)
    final = await transformed.to_result()  # Success("HELLO")
```

#### 체이닝 사용 패턴
```python
async def complex_pipeline_example():
    result = await (
        ResultAsync.from_value("input")
        .map_async(async_transform)
        .bind_async(async_validate)
        .map_async(async_format)
        .unwrap_or_async("fallback_result")
    )
    return result
```

### 3. 서버 시작 검증 유틸리티

#### 기본 검증
```python
from rfs.web.startup_utils import validate_imports, check_missing_types, safe_import

# Import 검증
result = validate_imports(
    'myapp.services.user_service',
    ['typing.Dict', 'myapp.models.User', 'rfs.core.result.Result']
)

if result.is_success():
    status = result.unwrap()
    print(f"All imports valid: {all(status.values())}")

# 타입 누락 체크
missing_result = check_missing_types('./src/services/user_service.py')
if missing_result.is_success():
    missing_types = missing_result.unwrap()
    if missing_types:
        print(f"Missing types: {missing_types}")

# 안전한 Import
module_result = safe_import('some.optional.module', fallback_value=None)
if module_result.is_success():
    module = module_result.unwrap()
    # 모듈 사용
```

#### 종합 서버 검증
```python
from rfs.utils.server_startup import ServerStartupConfig, ServerStartupManager

# 설정 생성
config = ServerStartupConfig(
    project_root="/path/to/project",
    project_name="My RFS Project",
    core_modules=['rfs.core.result', 'rfs.hof'],
    optional_modules=['rfs.web.server', 'rfs.reactive'],
    required_types=['Dict', 'List', 'Optional'],
    required_packages=['rfs', 'fastapi'],
    enable_auto_fix=True,
    auto_fix_imports=True
)

# 검증 실행
manager = ServerStartupManager(config)
result = manager.validate_all()

if result.is_success():
    validation_data = result.unwrap()
    if validation_data['overall_status']:
        print("✅ 서버 시작 준비 완료!")
    else:
        print("⚠️ 일부 문제 발견됨")
        for error in validation_data['errors']:
            print(f"오류: {error}")
        for warning in validation_data['warnings']:
            print(f"경고: {warning}")
```

#### 원클릭 검증 및 수정
```python
from rfs.utils.server_startup import validate_rfs_project

# 기본 검증
result = validate_rfs_project("/path/to/project")

# 자동 수정 포함
result = validate_rfs_project("/path/to/project", auto_fix=True)

print(result.unwrap())  # 상세한 검증 보고서 출력
```

### 4. CLI 도구

```bash
# 기본 검증
python -m rfs.utils.server_startup /path/to/project

# 자동 수정 포함
python -m rfs.utils.server_startup /path/to/project --auto-fix

# 엄격 모드 (모든 검사 통과 필요)
python -m rfs.utils.server_startup /path/to/project --strict

# 조용한 모드
python -m rfs.utils.server_startup /path/to/project --quiet
```

## 🎛️ 고급 사용법

### 1. 커스텀 설정으로 서버 검증

```python
from rfs.utils.server_startup import ServerStartupConfig, ServerStartupManager

# 커스텀 설정
config = ServerStartupConfig(
    project_root="/path/to/my/project",
    project_name="Enterprise API Server",
    
    # 핵심 모듈들 (반드시 있어야 함)
    core_modules=[
        'rfs.core.result',
        'rfs.core.config',
        'rfs.hof',
        'myapp.core.database',
        'myapp.core.auth'
    ],
    
    # 선택적 모듈들 (없어도 됨)
    optional_modules=[
        'rfs.web.server',
        'rfs.reactive',
        'myapp.integrations.external_api',
        'myapp.features.analytics'
    ],
    
    # 필수 타입들
    required_types=['Dict', 'List', 'Optional', 'Union', 'Any', 'Callable'],
    
    # 필수 패키지들
    required_packages=['rfs', 'fastapi', 'uvicorn', 'pydantic'],
    
    # 선택적 패키지들
    optional_packages=['redis', 'celery', 'boto3'],
    
    # 검증 옵션
    strict_mode=True,          # 엄격 모드
    enable_auto_fix=True,      # 자동 수정 허용
    auto_fix_imports=True,     # import 자동 수정
    verbose_logging=True,      # 상세 로그
    create_report=True         # 보고서 생성
)

# 검증 실행
manager = ServerStartupManager(config)
result = manager.validate_all()

# 결과 분석
if result.is_success():
    validation_data = result.unwrap()
    
    # 통계 정보
    stats = validation_data['stats']
    print(f"총 모듈 검사: {stats['total_modules_checked']}")
    print(f"핵심 모듈 통과: {stats['core_modules_passed']}")
    print(f"선택적 모듈 통과: {stats['optional_modules_passed']}")
    print(f"발견된 의존성: {stats['dependencies_found']}")
    print(f"타입 문제: {stats['type_issues_found']}")
    print(f"총 오류: {stats['total_errors']}")
    print(f"총 경고: {stats['total_warnings']}")
```

### 2. 비동기 검증

```python
import asyncio
from rfs.utils.server_startup import ServerStartupManager

async def async_validation_example():
    config = create_default_config("/path/to/project")
    manager = ServerStartupManager(config)
    
    # 비동기 검증 실행
    result = await manager.validate_all_async()
    
    if result.is_success():
        print("✅ 비동기 검증 완료")
    else:
        print(f"❌ 비동기 검증 실패: {result.unwrap_error()}")

# 실행
asyncio.run(async_validation_example())
```

### 3. 프로덕션 환경에서의 사용

```python
from rfs.utils.server_startup import quick_server_check_async
from rfs.hof import async_with_fallback

async def production_startup_check():
    """프로덕션 환경에서의 안전한 서버 시작 체크"""
    
    async def check_server_readiness():
        # 빠른 체크 수행
        result = await quick_server_check_async(
            project_root=os.getcwd(),
            strict_mode=False,  # 프로덕션에서는 관대하게
            verbose_logging=False  # 로그 최소화
        )
        
        if result.is_failure():
            raise RuntimeError(f"서버 준비 체크 실패: {result.unwrap_error()}")
        
        ready = result.unwrap()
        if not ready:
            raise RuntimeError("서버가 시작할 준비가 되지 않았습니다")
        
        return "ready"
    
    async def emergency_fallback(error):
        """체크 실패 시 기본 설정으로 시작"""
        logger.warning(f"정상 체크 실패, 기본 설정 사용: {error}")
        
        # 최소한의 안전 체크만 수행
        import os, sys
        if 'rfs' not in sys.modules:
            import rfs
        
        return "ready_with_minimal_config"
    
    # Fallback 패턴으로 안전한 시작
    safe_startup_check = async_with_fallback(
        check_server_readiness,
        emergency_fallback
    )
    
    status = await safe_startup_check()
    return status == "ready"

# FastAPI 앱에서 사용
@app.on_event("startup")
async def startup_event():
    is_ready = await production_startup_check()
    if is_ready:
        logger.info("🚀 서버가 성공적으로 시작되었습니다")
    else:
        logger.warning("⚠️ 서버가 최소 모드로 시작되었습니다")
```

## 🔧 문제 해결 가이드

### 자주 발생하는 문제들

#### 1. Import 오류
```python
# 문제: ModuleNotFoundError: No module named 'some_module'
from rfs.web.startup_utils import safe_import

# 해결
result = safe_import('some_module', fallback_value={'mock': True})
if result.is_success():
    module = result.unwrap()
    # 모듈 또는 fallback 값 사용
```

#### 2. 타입 Import 누락
```python
# 문제: NameError: name 'Dict' is not defined
from rfs.web.startup_utils import auto_fix_missing_imports

# 해결 (dry run으로 먼저 확인)
result = auto_fix_missing_imports('./myfile.py', dry_run=True)
if result.is_success():
    changes = result.unwrap()
    for change in changes:
        print(f"수정 예정: {change}")
    
    # 실제 수정 실행
    auto_fix_missing_imports('./myfile.py', dry_run=False)
```

#### 3. 의존성 누락
```python
# 문제: ImportError: No module named 'some_package'
from rfs.web.startup_utils import check_dependencies

# 해결
result = check_dependencies(['required_package'])
if result.is_failure():
    missing = result.unwrap_error()
    print(f"설치 필요한 패키지: {missing}")
    # pip install 안내 또는 fallback 로직 실행
```

### 디버깅 팁

1. **상세 로깅 활성화**
```python
config.verbose_logging = True
```

2. **단계별 검증**
```python
# 모듈별 개별 검증
for module in ['rfs.core', 'rfs.hof', 'myapp.main']:
    result = safe_import(module)
    print(f"{module}: {'✅' if result.is_success() else '❌'}")
```

3. **Dry Run으로 안전한 테스트**
```python
# 실제 수정하기 전에 미리 확인
result = auto_fix_missing_imports(file_path, dry_run=True)
```

## 📚 마이그레이션 가이드

### 기존 프로젝트 적용하기

#### 1. 기존 코드에서 HOF 패턴 적용

**Before (PR에서 발견된 문제)**:
```python
# ❌ 문제가 있던 코드
try:
    result = primary_function()
except Exception as e:
    result = fallback_function(e)
```

**After (개선된 코드)**:
```python
# ✅ HOF 패턴 사용
from rfs.hof import with_fallback

safe_function = with_fallback(primary_function, fallback_function)
result = safe_function()
```

#### 2. ResultAsync 확장 메서드 활용

**Before**:
```python
# ❌ 복잡한 비동기 Result 처리
async def complex_async_handling():
    try:
        primary_result = await some_async_operation()
        if primary_result.is_success():
            value = primary_result.unwrap()
            processed = await process_value(value)
            return Success(processed)
        else:
            return Failure("fallback_error")
    except Exception as e:
        return Failure(str(e))
```

**After**:
```python
# ✅ 확장 메서드 체이닝 사용
async def simplified_async_handling():
    return await (
        ResultAsync.from_async_result(some_async_operation)
        .bind_async(lambda value: process_value_async(value))
        .unwrap_or_async("fallback_error")
    )
```

#### 3. 서버 시작 검증 통합

**Before**:
```python
# ❌ 수동 검증
import sys
import importlib

def manual_startup_check():
    try:
        importlib.import_module('myapp.core')
        importlib.import_module('myapp.services')
        # ... 많은 수동 체크들
    except ImportError as e:
        print(f"Startup failed: {e}")
        sys.exit(1)
```

**After**:
```python
# ✅ 자동화된 검증
from rfs.utils.server_startup import validate_rfs_project

@app.on_event("startup")
async def startup_event():
    result = validate_rfs_project(
        project_root=os.getcwd(),
        auto_fix=False  # 프로덕션에서는 수정 비활성화
    )
    
    if result.is_failure():
        logger.error(f"Startup validation failed: {result.unwrap_error()}")
        # 적절한 처리 (graceful degradation, 알림 등)
```

## 🚀 베스트 프랙티스

### 1. 개발 환경에서
- `auto_fix=True`로 자동 수정 활용
- `verbose_logging=True`로 상세 정보 확인
- 정기적인 `validate_rfs_project` 실행

### 2. CI/CD 파이프라인에서
```yaml
# .github/workflows/validation.yml
- name: RFS 프로젝트 검증
  run: |
    python -m rfs.utils.server_startup . --strict --quiet
```

### 3. 프로덕션 환경에서
- `strict_mode=False`로 유연한 검증
- `auto_fix=False`로 수정 방지
- fallback 패턴으로 graceful degradation

### 4. 모니터링 통합
```python
from rfs.utils.server_startup import quick_server_check

@app.middleware("http")
async def health_check_middleware(request, call_next):
    if request.url.path == "/health":
        is_healthy = quick_server_check(os.getcwd())
        if is_healthy:
            return JSONResponse({"status": "healthy"})
        else:
            return JSONResponse({"status": "degraded"}, status_code=503)
    
    return await call_next(request)
```

---

## 📞 지원 및 기여

이 유틸리티들에 대한 문제 보고, 기능 제안, 또는 기여는 RFS Framework 저장소에서 환영합니다.

**추가 리소스**:
- [RFS Framework 문서](../README.md)
- [HOF 라이브러리 가이드](./16-hof-usage-guide.md)
- [결과 패턴 가이드](./01-core-patterns.md)

---
*이 가이드는 실제 프로덕션 환경에서 발견된 문제들을 바탕으로 작성되었으며, 지속적으로 업데이트됩니다.*