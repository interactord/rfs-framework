# Readable HOF 사용 가이드

자연어에 가까운 선언적 코드 작성을 위한 Higher-Order Functions 라이브러리 완전 가이드입니다.

## 개요

Readable HOF는 복잡한 중첩 루프와 규칙 기반 로직을 읽기 쉬운 체이닝 패턴으로 변환하여 코드의 가독성과 유지보수성을 크게 향상시킵니다.

### 핵심 철학

```python
# 기존 명령형 코드
violations = []
for text in texts:
    for rule in security_rules:
        if rule.matches(text):
            violation = create_violation(text, rule)
            if violation.severity >= "medium":
                violations.append(violation)

# Readable HOF 선언적 코드
violations = (apply_rules_to(texts)
              .using(security_rules)
              .collect_violations()
              .filter_above_threshold("medium"))
```

## 시작하기

### 설치 및 임포트

```python
# 기본 임포트
from rfs.hof.readable import (
    apply_rules_to,       # 규칙 적용 시스템
    validate_config,      # 검증 DSL
    scan_for,            # 텍스트 스캔
    extract_from,        # 배치 처리
    
    # 규칙 생성자들
    required, range_check, email_check,
    
    # 결과 처리
    success, failure, from_result
)
```

### 기본 컨셉

Readable HOF는 4가지 핵심 패턴을 제공합니다:

1. **규칙 적용 (Rule Application)**: 데이터에 규칙을 적용하여 위반사항 검출
2. **검증 DSL (Validation DSL)**: 구조화된 데이터 검증
3. **스캔 시스템 (Scanning)**: 텍스트나 데이터에서 패턴 검색
4. **배치 처리 (Batch Processing)**: 대량 데이터의 효율적 처리

## 1. 규칙 적용 시스템

### 기본 사용법

```python
from rfs.hof.readable import apply_rules_to

# 보안 규칙 정의
security_rules = [
    lambda text: "password" in text.lower(),
    lambda text: "api_key" in text.lower(),
    lambda text: re.search(r'\b\d{4}-\d{4}-\d{4}-\d{4}\b', text)  # 카드번호 패턴
]

# 코드 검사
code_violations = (apply_rules_to(source_code)
                   .using(security_rules)
                   .collect_violations())

print(f"발견된 보안 위반: {len(code_violations)}개")
```

### 고급 규칙 적용

```python
# 조건부 규칙 적용
def create_environment_rules(env: str):
    base_rules = [check_sql_injection, check_xss]
    
    if env == "production":
        return base_rules + [check_debug_info, check_test_data]
    return base_rules

# 환경별 검사
production_violations = (apply_rules_to(production_code)
                        .using(create_environment_rules("production"))
                        .filter_by_severity("high")
                        .collect_violations())

# 다중 데이터소스 검사
all_violations = []
for data_source in [database_logs, api_logs, file_system]:
    violations = (apply_rules_to(data_source)
                  .using(compliance_rules)
                  .collect_violations())
    all_violations.extend(violations)
```

### 성능 최적화

```python
# 병렬 규칙 적용 (대용량 데이터)
from rfs.hof.readable import RuleProcessor

processor = RuleProcessor(max_workers=4)
violations = (processor
              .apply_rules_to(large_dataset)
              .using(security_rules)
              .parallel_process()
              .collect_violations())

# 지연 평가로 메모리 효율화
violations_iter = (apply_rules_to(huge_dataset)
                   .using(rules)
                   .lazy_collect())  # 제너레이터 반환

for violation in violations_iter:
    if violation.severity == "critical":
        handle_critical_violation(violation)
        break
```

## 2. 검증 DSL

### 기본 검증 규칙

```python
from rfs.hof.readable import validate_config, required, range_check

# API 설정 검증
api_config = {
    "host": "api.example.com",
    "port": 8080,
    "timeout": 30,
    "api_key": "secret-key-123"
}

result = validate_config(api_config).against_rules([
    required("host", "호스트가 필요합니다"),
    required("api_key", "API 키가 필요합니다"),
    range_check("port", 1, 65535, "포트는 1-65535 사이여야 합니다"),
    range_check("timeout", 1, 300, "타임아웃은 1-300초 사이여야 합니다")
])

if result.is_success():
    print("설정이 유효합니다")
    config = result.unwrap()
else:
    print(f"설정 오류: {result.unwrap_error()}")
```

### 고급 검증 패턴

```python
from rfs.hof.readable import email_check, url_check, conditional, custom_check

# 사용자 등록 데이터 검증
def validate_user_registration(user_data):
    return validate_config(user_data).against_rules([
        required("username", "사용자명이 필요합니다"),
        required("email", "이메일이 필요합니다"),
        email_check("email", "유효한 이메일 형식이 아닙니다"),
        
        # 조건부 검증: premium 사용자의 경우 추가 필드 필요
        conditional(
            condition=lambda data: data.get("account_type") == "premium",
            rules=[
                required("company", "Premium 계정은 회사명이 필요합니다"),
                url_check("website", "유효한 웹사이트 URL이 필요합니다")
            ]
        ),
        
        # 커스텀 검증 규칙
        custom_check(
            field="password",
            validator=lambda pwd: len(pwd) >= 8 and any(c.isupper() for c in pwd),
            message="비밀번호는 8자 이상이며 대문자를 포함해야 합니다"
        )
    ])

# 사용 예
registration_data = {
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "account_type": "premium",
    "company": "Tech Corp",
    "website": "https://techcorp.com"
}

validation_result = validate_user_registration(registration_data)
```

### 중첩 구조 검증

```python
# 복잡한 JSON 설정 검증
def validate_microservice_config(config):
    return validate_config(config).against_rules([
        # 기본 서비스 설정
        required("service_name"),
        required("version"),
        
        # 데이터베이스 설정 검증
        required("database"),
        validate_nested("database", [
            required("host"),
            range_check("port", 1, 65535),
            required("name"),
            conditional(
                condition=lambda db: db.get("ssl_enabled", False),
                rules=[required("ssl_cert_path")]
            )
        ]),
        
        # 로깅 설정 검증
        required("logging"),
        validate_nested("logging", [
            required("level"),
            custom_check("level", 
                       lambda level: level in ["DEBUG", "INFO", "WARN", "ERROR"],
                       "로그 레벨이 유효하지 않습니다")
        ])
    ])

microservice_config = {
    "service_name": "user-api",
    "version": "1.2.0",
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "userdb",
        "ssl_enabled": True,
        "ssl_cert_path": "/etc/ssl/cert.pem"
    },
    "logging": {
        "level": "INFO"
    }
}

result = validate_microservice_config(microservice_config)
```

## 3. 스캔 시스템

### 텍스트 패턴 스캔

```python
import re
from rfs.hof.readable import scan_for, create_security_violation

# 보안 취약점 패턴 정의
security_patterns = [
    re.compile(r'password\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'api_key\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'secret\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),  # 이메일
]

# 소스 코드 스캔
def scan_source_code(file_content: str, file_path: str):
    return (scan_for(security_patterns)
            .in_text(file_content)
            .extract(lambda match, pattern: create_security_violation(
                file_path=file_path,
                line_number=file_content[:match.start()].count('\n') + 1,
                match_text=match.group(0),
                pattern_name=get_pattern_name(pattern),
                severity="high"
            ))
            .filter_above_threshold("medium")
            .sort_by_severity()
            .collect())

# 프로젝트 전체 스캔
def scan_project(project_path: str):
    all_violations = []
    
    for file_path in glob.glob(f"{project_path}/**/*.py", recursive=True):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            violations = scan_source_code(content, file_path)
            all_violations.extend(violations)
    
    return sorted(all_violations, key=lambda v: v.severity, reverse=True)
```

### 데이터 구조 스캔

```python
from rfs.hof.readable import scan_data_for, DataScanner

# 로그 데이터에서 이상 패턴 탐지
log_patterns = {
    "suspicious_login": lambda entry: entry.get("failed_attempts", 0) > 5,
    "unusual_access": lambda entry: entry.get("access_time_hour") not in range(9, 18),
    "privilege_escalation": lambda entry: "sudo" in entry.get("command", "").lower(),
}

# 로그 분석
def analyze_security_logs(log_entries: list):
    scanner = DataScanner(patterns=log_patterns)
    
    return (scan_data_for(log_patterns)
            .in_data(log_entries)
            .extract(lambda entry, pattern_name: {
                "timestamp": entry.get("timestamp"),
                "user": entry.get("user"),
                "alert_type": pattern_name,
                "severity": calculate_severity(pattern_name),
                "details": entry
            })
            .filter_above_threshold("low")
            .group_by_user()
            .collect())

# 실시간 모니터링
def setup_realtime_monitoring():
    def process_log_stream(log_stream):
        for log_entry in log_stream:
            alerts = (scan_data_for(log_patterns)
                     .in_single_entry(log_entry)
                     .extract_alerts()
                     .filter_above_threshold("medium"))
            
            for alert in alerts:
                send_security_alert(alert)

    return process_log_stream
```

### 다중 파일 스캔

```python
from rfs.hof.readable import MultiFileScanner

# 전체 프로젝트 스캔
def comprehensive_project_scan(project_root: str):
    scanner = MultiFileScanner(
        file_patterns=["*.py", "*.js", "*.jsx", "*.ts", "*.tsx"],
        exclude_patterns=["node_modules/*", "venv/*", "*.min.js"]
    )
    
    # 파일 타입별 다른 패턴 적용
    patterns_by_type = {
        ".py": python_security_patterns,
        ".js": javascript_security_patterns,
        ".jsx": react_security_patterns,
        ".ts": typescript_security_patterns,
    }
    
    return (scanner
            .scan_directory(project_root)
            .apply_patterns_by_extension(patterns_by_type)
            .extract_violations()
            .group_by_severity()
            .generate_report())

# 사용
scan_results = comprehensive_project_scan("/path/to/project")
print(f"총 {scan_results.total_violations}개의 위반사항 발견")
```

## 4. 배치 처리 시스템

### 기본 배치 처리

```python
from rfs.hof.readable import extract_from

# API 응답 배치 처리
api_responses = [
    {"status": "success", "data": {"id": 1, "name": "Alice"}},
    {"status": "error", "message": "Not found"},
    {"status": "success", "data": {"id": 2, "name": "Bob"}},
]

# 성공한 응답만 추출하고 변환
users = (extract_from(api_responses)
         .flatten_batches()
         .successful_only()
         .extract_content()
         .transform_to(lambda item: {
             "user_id": item["id"],
             "display_name": item["name"].title(),
             "created_at": datetime.now()
         })
         .collect())

print(f"처리된 사용자: {len(users)}명")
```

### 고급 배치 처리 패턴

```python
# 복잡한 데이터 변환 파이프라인
def create_user_processing_pipeline():
    return (extract_from
            .flatten_batches()
            .filter_by(lambda user: user.get("active", True))
            .transform_to(normalize_user_data)
            .filter_by(lambda user: validate_user(user).is_success())
            .transform_to(enrich_user_profile)
            .group_by(lambda user: user["department"])
            .collect())

# 에러 처리가 포함된 배치 처리
def robust_batch_processing(raw_data):
    results = []
    errors = []
    
    processed = (extract_from(raw_data)
                 .flatten_batches()
                 .transform_with_error_handling(
                     transform_func=process_user_data,
                     error_handler=lambda item, error: errors.append({
                         "item": item,
                         "error": str(error),
                         "timestamp": datetime.now()
                     })
                 )
                 .successful_only()
                 .collect())
    
    return {
        "processed": processed,
        "errors": errors,
        "success_rate": len(processed) / len(raw_data) if raw_data else 0
    }
```

### 병렬 배치 처리

```python
from rfs.hof.readable import extract_from_parallel

# CPU 집약적 작업의 병렬 처리
def parallel_data_processing(large_dataset):
    return (extract_from_parallel(large_dataset)
            .parallel_transform(
                func=cpu_intensive_processing,
                max_workers=4,
                use_processes=True  # CPU 집약적 작업에는 프로세스 사용
            )
            .parallel_filter(
                predicate=lambda item: item["score"] > 0.8,
                max_workers=2
            )
            .collect())

# I/O 집약적 작업의 병렬 처리
def parallel_api_calls(api_endpoints):
    return (extract_from_parallel(api_endpoints)
            .parallel_transform(
                func=call_external_api,
                max_workers=10,  # I/O 작업은 더 많은 스레드 사용
                use_processes=False
            )
            .successful_only()
            .collect())

# 사용
processed_data = parallel_data_processing(large_dataset)
api_results = parallel_api_calls(["api1", "api2", "api3"])
```

## 실전 활용 예제

### 예제 1: 보안 감사 시스템

```python
"""
전체 프로젝트의 보안 감사를 수행하는 완전한 시스템
"""

class SecurityAuditSystem:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.security_rules = self._load_security_rules()
        self.scan_patterns = self._load_scan_patterns()
    
    def perform_comprehensive_audit(self) -> dict:
        """포괄적인 보안 감사 수행"""
        
        # 1. 코드 규칙 검사
        code_violations = self._check_code_rules()
        
        # 2. 보안 패턴 스캔
        security_issues = self._scan_security_patterns()
        
        # 3. 설정 파일 검증
        config_issues = self._validate_configurations()
        
        # 4. 의존성 검사
        dependency_issues = self._check_dependencies()
        
        return self._generate_audit_report({
            "code_violations": code_violations,
            "security_issues": security_issues,
            "config_issues": config_issues,
            "dependency_issues": dependency_issues
        })
    
    def _check_code_rules(self) -> list:
        """코드 규칙 위반 검사"""
        all_violations = []
        
        for file_path in self._get_source_files():
            with open(file_path, 'r') as f:
                content = f.read()
                
            violations = (apply_rules_to(content)
                         .using(self.security_rules)
                         .with_context({"file_path": file_path})
                         .collect_violations()
                         .filter_above_threshold("low"))
            
            all_violations.extend(violations)
        
        return all_violations
    
    def _scan_security_patterns(self) -> list:
        """보안 패턴 스캔"""
        return (scan_for(self.scan_patterns)
                .in_directory(self.project_path)
                .extract(create_security_violation)
                .filter_above_threshold("medium")
                .sort_by_risk()
                .collect())
    
    def _validate_configurations(self) -> list:
        """설정 파일 검증"""
        config_issues = []
        
        for config_file in self._get_config_files():
            config_data = self._load_config(config_file)
            
            result = validate_config(config_data).against_rules([
                required("database.host", "데이터베이스 호스트 필요"),
                required("api.secret_key", "API 시크릿 키 필요"),
                range_check("server.port", 1, 65535),
                custom_check(
                    field="api.secret_key",
                    validator=lambda key: len(key) >= 32,
                    message="API 키는 32자 이상이어야 합니다"
                )
            ])
            
            if result.is_failure():
                config_issues.append({
                    "file": config_file,
                    "errors": result.unwrap_error()
                })
        
        return config_issues
```

### 예제 2: 데이터 파이프라인 모니터링

```python
"""
실시간 데이터 파이프라인 모니터링 및 품질 검사
"""

class DataPipelineMonitor:
    def __init__(self):
        self.quality_rules = self._load_quality_rules()
        self.anomaly_patterns = self._load_anomaly_patterns()
    
    def monitor_data_stream(self, data_stream):
        """데이터 스트림 실시간 모니터링"""
        
        for batch in data_stream:
            # 1. 데이터 품질 검사
            quality_issues = self._check_data_quality(batch)
            
            # 2. 이상 패턴 탐지
            anomalies = self._detect_anomalies(batch)
            
            # 3. 배치 처리 상태 확인
            processing_status = self._check_processing_status(batch)
            
            # 4. 알림 발송
            if quality_issues or anomalies:
                self._send_alerts({
                    "quality_issues": quality_issues,
                    "anomalies": anomalies,
                    "batch_id": batch.get("id"),
                    "timestamp": datetime.now()
                })
    
    def _check_data_quality(self, batch) -> list:
        """배치 데이터 품질 검사"""
        
        return (apply_rules_to(batch["records"])
                .using(self.quality_rules)
                .collect_violations()
                .filter_by(lambda v: v.severity in ["high", "critical"])
                .collect())
    
    def _detect_anomalies(self, batch) -> list:
        """이상 패턴 탐지"""
        
        return (scan_data_for(self.anomaly_patterns)
                .in_data(batch["records"])
                .extract(lambda record, pattern: {
                    "record_id": record.get("id"),
                    "pattern": pattern,
                    "anomaly_score": calculate_anomaly_score(record),
                    "timestamp": record.get("timestamp")
                })
                .filter_by(lambda item: item["anomaly_score"] > 0.7)
                .collect())
    
    def _generate_daily_report(self, date: str):
        """일일 모니터링 리포트 생성"""
        
        daily_data = self._load_daily_data(date)
        
        return (extract_from(daily_data)
                .flatten_batches()
                .group_by(lambda record: record["source"])
                .transform_to(lambda group: {
                    "source": group["key"],
                    "total_records": len(group["items"]),
                    "quality_score": calculate_quality_score(group["items"]),
                    "anomaly_count": count_anomalies(group["items"]),
                    "processing_time": calculate_avg_processing_time(group["items"])
                })
                .sort_by(lambda item: item["quality_score"])
                .collect())
```

## 성능 최적화 팁

### 1. 지연 평가 활용

```python
# 대용량 데이터 처리시 메모리 효율성
def process_large_dataset(dataset):
    # collect() 대신 lazy_collect() 사용
    result_iterator = (extract_from(dataset)
                      .filter_by(is_valid)
                      .transform_to(expensive_transformation)
                      .lazy_collect())  # 지연 평가
    
    # 필요한 만큼만 처리
    processed_count = 0
    for item in result_iterator:
        process_item(item)
        processed_count += 1
        if processed_count >= 1000:  # 필요한 만큼만
            break
```

### 2. 병렬 처리 최적화

```python
# CPU vs I/O 작업에 따른 최적화
def optimize_parallel_processing(data, operation_type="io"):
    if operation_type == "cpu":
        # CPU 집약적: 프로세스 사용, 코어 수만큼 워커
        return (extract_from_parallel(data)
                .parallel_transform(
                    cpu_intensive_func,
                    max_workers=os.cpu_count(),
                    use_processes=True
                ))
    else:
        # I/O 집약적: 스레드 사용, 더 많은 워커
        return (extract_from_parallel(data)
                .parallel_transform(
                    io_intensive_func,
                    max_workers=20,
                    use_processes=False
                ))
```

### 3. 캐싱 전략

```python
from functools import lru_cache

# 비용이 큰 규칙이나 패턴은 캐싱
@lru_cache(maxsize=128)
def get_compiled_patterns(pattern_type: str):
    return compile_security_patterns(pattern_type)

# 규칙 적용시 캐시된 패턴 사용
def cached_security_scan(content, pattern_type):
    patterns = get_compiled_patterns(pattern_type)
    return (scan_for(patterns)
            .in_text(content)
            .extract(create_security_violation)
            .collect())
```

## 디버깅 및 트러블슈팅

### 1. 단계별 디버깅

```python
# 파이프라인 각 단계 검사
def debug_pipeline(data):
    # 중간 결과 확인
    step1 = extract_from(data).flatten_batches()
    print(f"Step 1 - Flattened: {len(step1._items)} items")
    
    step2 = step1.successful_only()
    print(f"Step 2 - Successful: {len(step2._items)} items")
    
    step3 = step2.transform_to(transform_func)
    print(f"Step 3 - Transformed: {len(step3._items)} items")
    
    return step3.collect()
```

### 2. 에러 핸들링

```python
# 안전한 파이프라인 구성
def safe_processing_pipeline(data):
    try:
        return (extract_from(data)
                .with_error_handling(
                    on_error=lambda item, error: log_error(item, error)
                )
                .flatten_batches()
                .successful_only()
                .collect())
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return []
```

## 모범 사례

### 1. 함수 구성의 원칙

```python
# ✅ 좋은 예: 작은 단위 함수들의 조합
def validate_user_input(user_data):
    return validate_config(user_data).against_rules([
        required("email"),
        email_check("email"),
        required("password"),
        custom_check("password", is_strong_password)
    ])

# ❌ 피해야 할 예: 복잡한 단일 함수
def validate_user_input_bad(user_data):
    errors = []
    if not user_data.get("email"):
        errors.append("Email required")
    elif "@" not in user_data["email"]:
        errors.append("Invalid email")
    # ... 복잡한 검증 로직
    return errors
```

### 2. 재사용 가능한 컴포넌트

```python
# 재사용 가능한 규칙 세트 정의
common_validation_rules = [
    required("id", "ID가 필요합니다"),
    required("created_at", "생성일시가 필요합니다"),
]

user_validation_rules = common_validation_rules + [
    required("email"),
    email_check("email")
]

product_validation_rules = common_validation_rules + [
    required("name"),
    range_check("price", 0, float('inf'))
]
```

### 3. 테스트 가능한 구조

```python
# 테스트하기 쉬운 구조
class SecurityScanner:
    def __init__(self, patterns, rules):
        self.patterns = patterns
        self.rules = rules
    
    def scan_content(self, content):
        return (scan_for(self.patterns)
                .in_text(content)
                .extract(create_security_violation)
                .collect())
    
    def validate_content(self, content):
        return (apply_rules_to(content)
                .using(self.rules)
                .collect_violations())

# 테스트
def test_security_scanner():
    scanner = SecurityScanner(test_patterns, test_rules)
    violations = scanner.scan_content("password = 'secret'")
    assert len(violations) == 1
```

## 마이그레이션 가이드

기존 명령형 코드를 Readable HOF로 전환하는 단계별 가이드:

### 1단계: 간단한 루프 변환

```python
# 기존 코드
results = []
for item in items:
    if condition(item):
        results.append(transform(item))

# Readable HOF 변환
results = (extract_from(items)
          .filter_by(condition)
          .transform_to(transform)
          .collect())
```

### 2단계: 중첩 루프 변환

```python
# 기존 코드
violations = []
for text in texts:
    for rule in rules:
        if rule.check(text):
            violations.append(create_violation(text, rule))

# Readable HOF 변환
violations = (apply_rules_to(texts)
             .using(rules)
             .collect_violations())
```

### 3단계: 에러 처리 개선

```python
# 기존 코드
results = []
errors = []
for item in items:
    try:
        result = process(item)
        results.append(result)
    except Exception as e:
        errors.append((item, e))

# Readable HOF 변환
processing_result = (extract_from(items)
                    .transform_with_error_handling(
                        process,
                        error_handler=lambda item, e: errors.append((item, e))
                    )
                    .successful_only()
                    .collect())
```

## 결론

Readable HOF는 복잡한 데이터 처리 로직을 직관적이고 유지보수하기 쉬운 선언적 코드로 변환하는 강력한 도구입니다. 

### 핵심 이점

1. **가독성 향상**: 자연어에 가까운 코드 작성
2. **재사용성**: 작은 함수들의 조합으로 다양한 시나리오 구성
3. **테스트 용이성**: 각 단계를 독립적으로 테스트 가능
4. **성능 최적화**: 병렬 처리와 지연 평가 지원
5. **에러 처리**: 명시적이고 안전한 에러 핸들링

Readable HOF를 통해 더 나은 코드를 작성하고, 복잡한 비즈니스 로직을 명확하게 표현해보세요.

## 참고 자료

- [Readable HOF API 레퍼런스](api/hof/readable.md)
- [HOF 핵심 라이브러리](16-hot-library.md)
- [함수형 개발 규칙](01-core-patterns.md)
- [Result 패턴 가이드](01-core-patterns.md#result-pattern)