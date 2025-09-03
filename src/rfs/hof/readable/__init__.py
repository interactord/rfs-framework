"""
RFS Readable HOF Module

자연어에 가까운 선언적 코드 작성을 위한 HOF 라이브러리입니다.
복잡한 중첩 루프와 규칙 기반 로직을 읽기 쉬운 체이닝 패턴으로 변환합니다.

이 모듈은 다음과 같은 핵심 기능을 제공합니다:

1. 규칙 적용 시스템: apply_rules_to().using(rules).collect_violations()
2. 검증 DSL: validate_config().against_rules([required(), range_check()])  
3. 텍스트 스캔: scan_for(patterns).in_text().extract().filter_above_threshold()
4. 배치 처리: extract_from(data).flatten().filter_by().transform_to().collect()

사용 예:
    # 규칙 적용
    violations = apply_rules_to(text).using(security_rules).collect_violations()
    
    # 설정 검증
    result = validate_config(config).against_rules([
        required("api_key", "API 키가 필요합니다"),
        range_check("timeout", 1, 300, "타임아웃 범위 오류")
    ])
    
    # 텍스트 스캔
    results = (scan_for(patterns)
               .in_text(content)
               .extract(create_violation)
               .filter_above_threshold("medium"))
    
    # 배치 처리
    processed = (extract_from(batch_data)
                 .flatten_batches()
                 .successful_only()
                 .transform_to(create_item)
                 .collect())
"""

# 기본 플루언트 인터페이스
from .base import (
    FluentBase,
    ChainableResult,
    success,
    failure,
    from_result,
)

# 타입 정의 및 프로토콜
from .types import (
    # 타입 변수들
    T, U, V, R, E,
    
    # 프로토콜들
    Rule,
    Validator,
    Extractor,
    Config,
    
    # 데이터 클래스들
    ErrorInfo,
    ViolationInfo,
    ScanResult,
    
    # 타입 별칭들
    RiskLevel,
    ProcessorFunction,
    PredicateFunction,
    TransformFunction,
    
    # 유틸리티 함수들
    compare_risk_level,
    is_risk_above_threshold,
    RISK_LEVEL_ORDER,
)

# 규칙 적용 시스템
from .rules import (
    # 클래스들
    RuleApplication,
    RuleProcessor,
    
    # 메인 함수
    apply_rules_to,
    
    # 편의 함수들
    apply_single_rule,
    check_violations,
    count_violations,
)

# 검증 DSL
from .validation import (
    # 클래스들
    ValidationRule,
    ConfigValidator,
    
    # 메인 함수
    validate_config,
    
    # 규칙 생성 함수들
    required,
    range_check,
    format_check,
    custom_check,
    length_check,
    email_check,
    url_check,
    conditional,
    
    # 편의 함수들
    validate_fields,
    is_valid,
)

# 스캔 시스템
from .scanning import (
    # 클래스들
    Scanner,
    TextScanner,
    FileScanner,
    MultiFileScanner,
    DataScanner,
    ExtractionResult,
    
    # 메인 함수
    scan_for,
    scan_data_for,
    
    # 편의 함수들
    create_security_violation,
    create_log_entry,
    simple_extract,
)

# 배치 처리 시스템
from .processing import (
    # 클래스들
    DataExtractor,
    DataProcessor,
    ParallelDataProcessor,
    AsyncDataProcessor,
    
    # 메인 함수
    extract_from,
    extract_from_parallel,
    
    # 편의 함수들
    process_batch,
    filter_and_transform,
    quick_parallel_process,
    quick_async_process,
)

# 버전 정보
__version__ = '1.0.0'

# 공개 API 목록
__all__ = [
    # 기본 플루언트 인터페이스
    'FluentBase',
    'ChainableResult',
    'success',
    'failure', 
    'from_result',
    
    # 타입 정의
    'T', 'U', 'V', 'R', 'E',
    'Rule', 'Validator', 'Extractor', 'Config',
    'ErrorInfo', 'ViolationInfo', 'ScanResult',
    'RiskLevel', 'ProcessorFunction', 'PredicateFunction', 'TransformFunction',
    'compare_risk_level', 'is_risk_above_threshold', 'RISK_LEVEL_ORDER',
    
    # 규칙 적용 시스템
    'RuleApplication', 'RuleProcessor',
    'apply_rules_to',
    'apply_single_rule', 'check_violations', 'count_violations',
    
    # 검증 DSL
    'ValidationRule', 'ConfigValidator', 
    'validate_config',
    'required', 'range_check', 'format_check', 'custom_check',
    'length_check', 'email_check', 'url_check', 'conditional',
    'validate_fields', 'is_valid',
    
    # 스캔 시스템
    'Scanner', 'TextScanner', 'FileScanner', 'MultiFileScanner', 'DataScanner', 'ExtractionResult',
    'scan_for', 'scan_data_for',
    'create_security_violation', 'create_log_entry', 'simple_extract',
    
    # 배치 처리 시스템
    'DataExtractor', 'DataProcessor', 'ParallelDataProcessor', 'AsyncDataProcessor',
    'extract_from', 'extract_from_parallel',
    'process_batch', 'filter_and_transform', 'quick_parallel_process', 'quick_async_process',
]

# 모듈 수준 편의 함수들
def quick_validate(obj, **field_rules):
    """
    빠른 검증을 위한 편의 함수입니다.
    
    Args:
        obj: 검증할 객체
        **field_rules: 필드별 검증 규칙들
        
    Example:
        >>> result = quick_validate(config, 
        ...                        api_key="required",
        ...                        timeout=(1, 300),
        ...                        email="email")
    
    Returns:
        검증 결과 ChainableResult
    """
    rules = []
    
    for field_name, rule_spec in field_rules.items():
        if rule_spec == "required":
            rules.append(required(field_name, f"{field_name}이(가) 필요합니다"))
        elif isinstance(rule_spec, tuple) and len(rule_spec) == 2:
            min_val, max_val = rule_spec
            rules.append(range_check(field_name, min_val, max_val, f"{field_name}이(가) {min_val}-{max_val} 범위를 벗어났습니다"))
        elif rule_spec == "email":
            rules.append(email_check(field_name))
        elif rule_spec == "url":
            rules.append(url_check(field_name))
    
    return validate_config(obj).against_rules(rules)

def quick_scan(text, patterns, extractor=None):
    """
    빠른 스캔을 위한 편의 함수입니다.
    
    Args:
        text: 스캔할 텍스트
        patterns: 검색할 패턴들
        extractor: 추출 함수 (기본값: simple_extract)
        
    Returns:
        스캔 결과
    """
    if extractor is None:
        extractor = simple_extract
    
    return scan_for(patterns).in_text(text).extract(extractor).collect()

def quick_process(data, *operations):
    """
    빠른 데이터 처리를 위한 편의 함수입니다.
    
    Args:
        data: 처리할 데이터
        *operations: 적용할 연산들
        
    Returns:
        처리된 결과
    """
    processor = extract_from(data)
    
    for operation in operations:
        if operation == "flatten":
            processor = processor.flatten_batches()
        elif operation == "success_only":
            processor = DataProcessor(processor._value).successful_only()
        elif callable(operation):
            processor = DataProcessor(processor._value).filter_by(operation)
    
    if isinstance(processor, DataExtractor):
        return processor._value
    else:
        return processor.collect()

# 모듈 정보
__author__ = "RFS Framework Team"
__email__ = "rfs@example.com"
__description__ = "자연어에 가까운 선언적 HOF 라이브러리"
__license__ = "MIT"

# 사용 가이드 문서화
def get_usage_examples():
    """사용 예제들을 반환합니다."""
    return {
        "rules": """
# 규칙 적용 시스템 사용 예제
from rfs.hof.readable import apply_rules_to

# 보안 규칙 적용
violations = apply_rules_to(user_input).using(security_rules).collect_violations()

# 위반 사항 확인
if apply_rules_to(data).using(rules).has_violations():
    print("규칙 위반이 발견되었습니다")
        """,
        
        "validation": """
# 검증 DSL 사용 예제
from rfs.hof.readable import validate_config, required, range_check, email_check

result = validate_config(config).against_rules([
    required("api_key", "API 키가 필요합니다"),
    range_check("timeout", 1, 300, "타임아웃은 1-300초 사이여야 합니다"),
    email_check("admin_email", "유효한 관리자 이메일이 필요합니다")
])

if result.is_success():
    print("설정이 유효합니다")
else:
    print(f"설정 오류: {result.result.unwrap_error()}")
        """,
        
        "scanning": """
# 텍스트 스캔 사용 예제
import re
from rfs.hof.readable import scan_for, create_security_violation

patterns = [
    re.compile(r'password\\s*=\\s*["\']([^"\']+)["\']'),
    re.compile(r'api_key\\s*[:=]\\s*["\']([^"\']+)["\']')
]

results = (scan_for(patterns)
           .in_text(code_content)
           .extract(create_security_violation)
           .filter_above_threshold("medium")
           .sort_by_risk())

for violation in results.collect():
    print(f"보안 위험: {violation}")
        """,
        
        "processing": """
# 배치 처리 사용 예제
from rfs.hof.readable import extract_from

processed_items = (extract_from(batch_results)
                   .flatten_batches()
                   .successful_only()
                   .extract_content()
                   .flatten_text_chunks()
                   .filter_by(lambda x: len(x.strip()) > 10)
                   .transform_to(create_processed_item)
                   .collect())

print(f"처리된 항목 수: {len(processed_items)}")
        """,
        
        "parallel_processing": """
# 병렬 처리 사용 예제
from rfs.hof.readable import extract_from_parallel, quick_parallel_process

# 대용량 데이터 병렬 처리
large_dataset = [{"id": i, "data": f"item_{i}"} for i in range(10000)]

# ThreadPoolExecutor를 사용한 병렬 처리
parallel_results = (extract_from_parallel(large_dataset)
                   .parallel_transform(lambda x: process_item(x), max_workers=4)
                   .parallel_filter(lambda x: x['score'] > 0.5, max_workers=2)
                   .collect())

# ProcessPoolExecutor를 사용한 CPU 집약적 작업
cpu_intensive_results = (extract_from_parallel(large_dataset)
                        .parallel_transform(compute_heavy_task, 
                                          max_workers=2, 
                                          use_processes=True)
                        .collect())

# 간단한 병렬 처리
quick_results = quick_parallel_process(
    data=large_dataset,
    operations=['transform', 'filter'],
    max_workers=4
)

print(f"병렬 처리된 항목 수: {len(parallel_results)}")
        """,
        
        "async_processing": """
# 비동기 처리 사용 예제  
from rfs.hof.readable import quick_async_process
import asyncio

async def async_process_items():
    # 비동기 API 호출을 포함한 처리
    async_results = await quick_async_process(
        data=api_endpoints,
        operations=[
            lambda x: fetch_data_async(x),
            lambda x: validate_async(x),
            lambda x: save_async(x)
        ],
        max_concurrent=10
    )
    
    print(f"비동기 처리된 항목 수: {len(async_results)}")
    return async_results

# 사용
results = asyncio.run(async_process_items())
        """
    }