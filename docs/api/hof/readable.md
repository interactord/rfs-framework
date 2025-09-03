# Readable HOF API Reference

자연어에 가까운 선언적 HOF 패턴을 제공하는 RFS Framework의 Readable HOF 라이브러리입니다.

## 개요

Readable HOF는 복잡한 중첩 루프와 규칙 기반 로직을 읽기 쉬운 체이닝 패턴으로 변환하는 도구 모음입니다. 다음 4가지 핵심 영역을 다룹니다:

1. **규칙 적용 시스템**: `apply_rules_to()`
2. **검증 DSL**: `validate_config()`
3. **텍스트/데이터 스캔**: `scan_for()`, `scan_data_for()`
4. **배치 처리**: `extract_from()`

## 핵심 API

### 🔍 규칙 적용 시스템

#### apply_rules_to(target)
대상에 규칙들을 적용하기 위한 시작점입니다.

**Parameters:**
- `target` (Any): 규칙을 적용할 대상 데이터

**Returns:** `RuleApplication[T]`

**Usage:**
```python
from rfs.hof.readable import apply_rules_to

# 보안 규칙 적용 예제
security_rules = [
    password_strength_rule,
    sql_injection_rule,
    xss_prevention_rule
]

violations = apply_rules_to(user_input).using(security_rules).collect_violations()

# 위반 사항이 있는지 확인
if apply_rules_to(data).using(rules).has_violations():
    print("규칙 위반이 발견되었습니다")
```

#### RuleApplication 메서드

##### using(rules: List[Rule]) -> RuleProcessor
규칙 목록을 사용하여 처리기를 생성합니다.

##### with_rule(rule: Rule) -> RuleProcessor  
단일 규칙으로 처리기를 생성합니다.

#### RuleProcessor 메서드

##### collect_violations() -> List[ViolationInfo]
모든 규칙을 적용하여 위반 사항들을 수집합니다.

##### has_violations() -> bool
위반 사항이 있는지 확인합니다.

##### count_violations() -> int
위반 사항의 개수를 반환합니다.

##### first_violation() -> Optional[ViolationInfo]
첫 번째 위반 사항을 반환합니다.

##### critical_violations() -> List[ViolationInfo]
critical 및 high 위험 수준의 위반 사항들만 반환합니다.

##### violations_by_risk() -> Dict[str, List[ViolationInfo]]
위험 수준별로 위반 사항들을 그룹화합니다.

### ✅ 검증 DSL (Domain Specific Language)

#### validate_config(config_obj)
설정 객체 검증을 위한 시작점입니다.

**Parameters:**
- `config_obj` (Any): 검증할 설정 객체

**Returns:** `ConfigValidator`

**Usage:**
```python
from rfs.hof.readable import validate_config, required, range_check, email_check

result = validate_config(config).against_rules([
    required("api_key", "API 키가 필요합니다"),
    range_check("timeout", 1, 300, "타임아웃은 1-300초 사이여야 합니다"),
    email_check("admin_email", "유효한 관리자 이메일이 필요합니다")
])

if result.is_success():
    print("설정이 유효합니다")
else:
    print(f"설정 오류: {result.unwrap_error()}")
```

#### ConfigValidator 메서드

##### against_rules(rules: List[ValidationRule]) -> ChainableResult
여러 규칙들에 대해 검증을 수행합니다.

##### with_rule(rule: ValidationRule) -> ChainableResult
단일 규칙으로 검증을 수행합니다.

##### validate_required_fields(required_fields: List[str]) -> ChainableResult
필수 필드들을 일괄 검증합니다.

#### 검증 규칙 생성 함수들

##### required(field_name: str, error_message: str) -> ValidationRule
필수 필드 검증 규칙을 생성합니다.

**Usage:**
```python
# 기본 필수 필드 검증
api_key_rule = required("api_key", "API 키가 필요합니다")

# 빈 문자열도 실패로 처리
username_rule = required("username", "사용자명이 필요합니다")  # "" → 실패
```

##### range_check(field_name: str, min_val: Union[int, float], max_val: Union[int, float], error_message: str) -> ValidationRule
숫자 범위 검증 규칙을 생성합니다.

**Usage:**
```python
# 포트 범위 검증
port_rule = range_check("port", 1, 65535, "포트는 1-65535 사이여야 합니다")

# 퍼센트 값 검증  
cpu_rule = range_check("cpu_limit", 0.0, 100.0, "CPU 제한은 0-100% 사이여야 합니다")
```

##### format_check(field_name: str, pattern: Union[Pattern, str], error_message: str) -> ValidationRule
문자열 형식 검증 규칙을 생성합니다.

**Usage:**
```python
import re

# 전화번호 형식 검증
phone_pattern = re.compile(r'^\d{3}-\d{4}-\d{4}$')
phone_rule = format_check("phone", phone_pattern, "올바른 전화번호 형식이 아닙니다")

# UUID 형식 검증  
uuid_rule = format_check("id", r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', "유효한 UUID가 아닙니다")
```

##### email_check(field_name: str, error_message: Optional[str] = None) -> ValidationRule
이메일 형식 검증 규칙을 생성합니다.

##### url_check(field_name: str, error_message: Optional[str] = None) -> ValidationRule
URL 형식 검증 규칙을 생성합니다.

##### length_check(field_name: str, min_length: Optional[int] = None, max_length: Optional[int] = None, error_message: Optional[str] = None) -> ValidationRule
문자열이나 컬렉션의 길이를 검증하는 규칙을 생성합니다.

##### conditional(condition: Callable[[Any], bool], rule: ValidationRule) -> ValidationRule
조건부 검증 규칙을 생성합니다.

**Usage:**
```python
# SSL 활성화 시에만 인증서 경로 검증
ssl_cert_rule = conditional(
    lambda config: config.ssl_enabled,
    required("ssl_cert_path", "SSL 사용 시 인증서 경로가 필요합니다")
)

# 프로덕션 환경에서만 API 키 필수
production_api_rule = conditional(
    lambda config: config.environment == "production",
    required("api_key", "프로덕션 환경에서는 API 키가 필요합니다")
)
```

##### custom_check(field_name: str, validator_func: Callable[[Any], bool], error_message: str, description: Optional[str] = None) -> ValidationRule
커스텀 검증 규칙을 생성합니다.

**Usage:**
```python
# 비밀번호 강도 검증
def is_strong_password(password):
    return (
        len(password) >= 8 and
        any(c.isupper() for c in password) and
        any(c.islower() for c in password) and
        any(c.isdigit() for c in password)
    )

password_rule = custom_check(
    "password",
    is_strong_password,
    "비밀번호는 8자 이상, 대소문자, 숫자를 포함해야 합니다",
    "강력한 비밀번호 검증"
)
```

### 🔍 스캔 시스템

#### scan_for(patterns: Union[List[Pattern], List[str]]) -> Scanner
정규표현식 패턴들을 사용한 텍스트 스캔을 위한 시작점입니다.

**Usage:**
```python
import re
from rfs.hof.readable import scan_for, create_security_violation

# 보안 패턴 정의
security_patterns = [
    re.compile(r'password\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'api_key\s*[:=]\s*["\']([^"\']+)["\']'),
    re.compile(r'secret\s*[:=]\s*["\']([^"\']+)["\']')
]

# 코드에서 보안 위험 요소 스캔
results = (scan_for(security_patterns)
           .in_text(source_code)
           .extract(create_security_violation)
           .filter_above_threshold("medium")
           .sort_by_risk())

for violation in results.collect():
    print(f"보안 위험: {violation}")
```

#### scan_data_for(pattern_funcs: List[Callable[[Any], bool]]) -> Scanner
구조화된 데이터에서 함수 패턴을 사용한 스캔을 위한 시작점입니다.

**Usage:**
```python
from rfs.hof.readable import scan_data_for

# 데이터 패턴 함수들
def has_sensitive_data(obj):
    return hasattr(obj, 'ssn') or hasattr(obj, 'credit_card')

def is_privileged_user(obj):
    return getattr(obj, 'is_admin', False) or getattr(obj, 'is_superuser', False)

def has_expired_credentials(obj):
    return (hasattr(obj, 'expires_at') and 
            obj.expires_at < datetime.now())

# 사용자 객체들에서 보안 위험 요소 스캔
def create_security_report(user):
    risk_factors = []
    if has_sensitive_data(user):
        risk_factors.append('pii_data')
    if is_privileged_user(user):
        risk_factors.append('elevated_privileges')
    if has_expired_credentials(user):
        risk_factors.append('expired_credentials')
    
    return {
        'user_id': user.id,
        'risk_factors': risk_factors,
        'risk_level': 'high' if len(risk_factors) > 1 else 'medium' if risk_factors else 'low'
    }

# 전체 사용자 목록 스캔
security_reports = []
for user in users:
    scanner = scan_data_for([has_sensitive_data, is_privileged_user, has_expired_credentials])
    result = scanner.in_data(user).extract(create_security_report)
    if result.count() > 0:
        security_reports.extend(result.to_list())

# 고위험 사용자만 필터링
from rfs.hof.readable.scanning import ExtractionResult
high_risk_users = ExtractionResult(security_reports).filter_above_threshold('high')
```

#### Scanner 메서드

##### in_text(text: str) -> TextScanner
텍스트에서 스캔을 수행합니다.

##### in_file(file_path: str, encoding: str = 'utf-8') -> FileScanner
파일에서 스캔을 수행합니다.

##### in_data(data: Any) -> DataScanner
구조화된 데이터에서 스캔을 수행합니다.

#### DataScanner 클래스

##### extract(extractor: Callable) -> ExtractionResult
데이터에서 패턴 매칭을 통해 정보를 추출합니다.

#### ExtractionResult 클래스
추출된 결과를 처리하기 위한 풍부한 메서드를 제공합니다.

##### Basic Operations
- `count() -> int`: 항목 개수 반환
- `to_list() -> List[Any]`: 리스트로 변환
- `to_result() -> ChainableResult`: Result 패턴으로 변환

##### Filtering & Selection
- `filter_by(predicate: Callable) -> ExtractionResult`: 조건에 따라 필터링
- `filter_above_threshold(threshold: str) -> ExtractionResult`: 위험도 임계값 이상 필터링
- `take(count: int) -> ExtractionResult`: 처음 N개 항목만 선택

##### Grouping & Sorting
- `group_by(key_func: Callable) -> Dict[str, List]`: 키 함수에 따라 그룹화
- `group_by_risk() -> Dict[str, List]`: 위험 수준별 그룹화 (편의 함수)
- `sort_by(key_func: Callable, reverse: bool = False) -> ExtractionResult`: 정렬

##### Transformation
- `transform(transformer: Callable) -> ExtractionResult`: 결과 변환

**Usage:**
```python
# 로그 분석 예제
log_patterns = [
    re.compile(r'ERROR.*?(\w+Exception)'),
    re.compile(r'WARN.*?(timeout|connection)'),
    re.compile(r'FATAL.*?(.+)')
]

def create_log_analysis(match, pattern):
    return {
        'level': 'ERROR' if 'ERROR' in match.group(0) else 'WARN' if 'WARN' in match.group(0) else 'FATAL',
        'message': match.group(1) if match.groups() else match.group(0),
        'risk_level': 'critical' if 'FATAL' in match.group(0) else 'high' if 'ERROR' in match.group(0) else 'medium',
        'timestamp': datetime.now()
    }

analysis = (scan_for(log_patterns)
           .in_file('/var/log/app.log')
           .extract(create_log_analysis)
           .filter_above_threshold('medium')
           .group_by_risk())

# 심각한 오류들만 확인
critical_errors = analysis.get('critical', [])
for error in critical_errors:
    print(f"Critical: {error['message']}")
```

### 🔄 배치 처리 시스템

#### extract_from(data) -> DataExtractor
배치 데이터 처리를 위한 시작점입니다.

**Usage:**
```python
from rfs.hof.readable import extract_from

# API 응답 배치 처리
api_responses = [
    {'status': 'success', 'data': {'user_id': 1, 'name': 'Alice'}},
    {'status': 'error', 'error': 'User not found'},
    {'status': 'success', 'data': {'user_id': 2, 'name': 'Bob'}},
]

processed_users = (extract_from(api_responses)
                   .flatten_batches()
                   .successful_only()
                   .extract_content()
                   .transform_to(create_user_object)
                   .collect())

def create_user_object(response_data):
    return User(
        id=response_data['user_id'],
        name=response_data['name']
    )

for user in processed_users:
    print(f"Processed user: {user.name}")
```

## 편의 함수들

### quick_validate(obj, **field_rules)
빠른 검증을 위한 편의 함수입니다.

**Usage:**
```python
from rfs.hof.readable import quick_validate

# 간단한 필드 검증
result = quick_validate(config, 
                       api_key="required",
                       timeout=(1, 300),  # range check
                       email="email",
                       website="url")

if result.is_success():
    print("모든 검증 통과")
else:
    print(f"검증 실패: {result.unwrap_error()}")
```

### quick_scan(text, patterns, extractor=None)
빠른 스캔을 위한 편의 함수입니다.

### quick_process(data, *operations)
빠른 데이터 처리를 위한 편의 함수입니다.

## 타입 정의

### ViolationInfo
규칙 위반 정보를 담는 데이터 클래스입니다.

**Attributes:**
- `rule_name: str` - 위반된 규칙명
- `message: str` - 위반 메시지
- `risk_level: str` - 위험 수준 ('low', 'medium', 'high', 'critical')
- `position: Optional[int]` - 위반 위치 (텍스트 스캔 시)
- `matched_text: Optional[str]` - 매칭된 텍스트
- `context: Optional[Dict]` - 추가 컨텍스트 정보

### ValidationRule
검증 규칙을 정의하는 데이터 클래스입니다.

**Attributes:**
- `field_name: str` - 검증할 필드명
- `validator: Callable[[Any], bool]` - 검증 함수
- `error_message: str` - 실패 시 메시지
- `description: Optional[str]` - 규칙 설명

### ChainableResult[T]
체이닝 가능한 결과 객체입니다.

**Methods:**
- `is_success() -> bool` - 성공 여부 확인
- `unwrap() -> T` - 성공 값 추출
- `unwrap_error() -> str` - 에러 메시지 추출
- `map(func: Callable) -> ChainableResult` - 값 변환
- `bind(func: Callable) -> ChainableResult` - 모나드 바인드

## 실제 사용 예제

### 종합적인 설정 검증 시스템

```python
from rfs.hof.readable import validate_config, required, range_check, conditional, email_check

class AppConfig:
    def __init__(self):
        self.environment = "production" 
        self.debug = False
        self.api_key = "secret-key-123"
        self.database_url = "postgresql://localhost:5432/mydb"
        self.redis_url = "redis://localhost:6379"
        self.admin_email = "admin@example.com"
        self.max_connections = 100
        self.timeout = 30
        self.ssl_enabled = True
        self.ssl_cert_path = "/path/to/cert.pem"
        self.feature_flags = {'new_ui': True, 'beta_api': False}

def validate_app_config(config):
    """종합적인 애플리케이션 설정 검증"""
    
    # 기본 검증 규칙들
    basic_rules = [
        required("environment", "환경 설정이 필요합니다"),
        required("api_key", "API 키가 필요합니다"),
        required("database_url", "데이터베이스 URL이 필요합니다"),
        email_check("admin_email", "유효한 관리자 이메일이 필요합니다"),
        range_check("max_connections", 1, 1000, "연결 수는 1-1000 사이여야 합니다"),
        range_check("timeout", 1, 300, "타임아웃은 1-300초 사이여야 합니다")
    ]
    
    # 조건부 검증 규칙들
    conditional_rules = [
        # SSL 사용 시에만 인증서 경로 필수
        conditional(
            lambda cfg: cfg.ssl_enabled,
            required("ssl_cert_path", "SSL 사용 시 인증서 경로가 필요합니다")
        ),
        
        # 프로덕션 환경에서는 디버그 모드 비활성화 필요
        conditional(
            lambda cfg: cfg.environment == "production",
            lambda cfg: not cfg.debug,
            "프로덕션 환경에서는 디버그 모드를 비활성화해야 합니다"
        )
    ]
    
    # 전체 검증 실행
    result = validate_config(config).against_rules(basic_rules + conditional_rules)
    
    return result

# 사용
config = AppConfig()
validation_result = validate_app_config(config)

if validation_result.is_success():
    print("✅ 설정이 모두 유효합니다")
    validated_config = validation_result.unwrap()
else:
    print(f"❌ 설정 오류: {validation_result.unwrap_error()}")
```

### 보안 코드 스캔 시스템

```python
from rfs.hof.readable import scan_for, create_security_violation
import re

def setup_security_scanner():
    """보안 스캔 패턴 설정"""
    
    patterns = [
        # 하드코딩된 비밀번호/키 패턴
        re.compile(r'password\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'api_key\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'secret\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'token\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
        
        # SQL 인젝션 위험 패턴
        re.compile(r'SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*\+.*', re.IGNORECASE),
        re.compile(r'INSERT\s+INTO\s+.*\s+VALUES\s*\(.*\+.*\)', re.IGNORECASE),
        
        # XSS 위험 패턴
        re.compile(r'innerHTML\s*=\s*.*\+.*', re.IGNORECASE),
        re.compile(r'document\.write\s*\(.*\+.*\)', re.IGNORECASE),
    ]
    
    return patterns

def create_detailed_security_violation(match, pattern):
    """상세한 보안 위반 정보 생성"""
    
    pattern_str = pattern.pattern
    matched_text = match.group(0)
    
    # 위험도 결정
    if 'password' in pattern_str.lower() or 'secret' in pattern_str.lower():
        risk_level = 'critical'
        category = 'credential_exposure'
    elif 'sql' in pattern_str.lower() or 'SELECT' in pattern_str:
        risk_level = 'high' 
        category = 'sql_injection'
    elif 'innerHTML' in pattern_str or 'document.write' in pattern_str:
        risk_level = 'high'
        category = 'xss_vulnerability'
    else:
        risk_level = 'medium'
        category = 'general_security'
    
    return {
        'rule_name': f'security_scan_{category}',
        'message': f'잠재적 보안 위험 발견: {matched_text[:50]}...',
        'risk_level': risk_level,
        'category': category,
        'matched_text': matched_text,
        'position': match.start(),
        'context': {
            'pattern': pattern_str,
            'line_context': matched_text,
            'recommendations': get_security_recommendations(category)
        }
    }

def get_security_recommendations(category):
    """카테고리별 보안 권장사항"""
    recommendations = {
        'credential_exposure': [
            '환경 변수나 설정 파일 사용',
            '비밀 관리 서비스 활용',
            '코드에 하드코딩 금지'
        ],
        'sql_injection': [
            'Prepared Statement 사용', 
            'ORM 라이브러리 사용',
            '사용자 입력 검증 및 이스케이핑'
        ],
        'xss_vulnerability': [
            '사용자 입력 검증',
            'XSS 방어 라이브러리 사용',
            'Content Security Policy 적용'
        ]
    }
    return recommendations.get(category, ['코드 리뷰 및 보안 검증 필요'])

def scan_codebase_security(directory_path):
    """전체 코드베이스 보안 스캔"""
    
    security_patterns = setup_security_scanner()
    all_violations = []
    
    # Python 파일들을 스캔
    import os
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                
                # 파일별 보안 스캔
                violations = (scan_for(security_patterns)
                             .in_file(file_path)
                             .extract(create_detailed_security_violation)
                             .to_list())
                
                # 파일 정보 추가
                for violation in violations:
                    violation['file_path'] = file_path
                    violation['file_name'] = file
                
                all_violations.extend(violations)
    
    # 결과 분석
    from rfs.hof.readable.scanning import ExtractionResult
    security_report = ExtractionResult(all_violations)
    
    # 위험도별 그룹화
    by_risk = security_report.group_by_risk()
    
    # 카테고리별 그룹화  
    by_category = security_report.group_by(lambda v: v['category'])
    
    # 고위험 문제만 필터링
    critical_issues = security_report.filter_above_threshold('high')
    
    return {
        'total_violations': security_report.count(),
        'by_risk_level': by_risk,
        'by_category': by_category,
        'critical_issues': critical_issues.to_list(),
        'summary': {
            'critical': len(by_risk.get('critical', [])),
            'high': len(by_risk.get('high', [])),
            'medium': len(by_risk.get('medium', [])),
            'low': len(by_risk.get('low', []))
        }
    }

# 사용 예제
security_results = scan_codebase_security('./src')

print(f"🔍 보안 스캔 완료 - 총 {security_results['total_violations']}개 이슈 발견")
print("\n📊 위험도별 분포:")
for risk_level, count in security_results['summary'].items():
    print(f"  {risk_level.upper()}: {count}개")

print("\n🚨 긴급 수정 필요:")
for issue in security_results['critical_issues']:
    print(f"  - {issue['file_name']}: {issue['message']}")
```

## 관련 문서

- [Readable HOF 사용 가이드](../../19-readable-hof-guide.md) - 상세한 사용법과 패턴
- [HOF Core Functions](core.md) - 기본 고차 함수들
- [함수형 프로그래밍 패턴](../../01-core-patterns.md) - RFS의 함수형 프로그래밍 철학