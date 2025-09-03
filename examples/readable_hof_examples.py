"""
RFS Readable HOF 사용 예제

이 파일은 RFS Framework의 새로운 Readable HOF 모듈의 사용법을 보여줍니다.
PR 문서에서 제안된 모든 패턴들의 실제 동작 예제를 포함합니다.
"""

import re
from dataclasses import dataclass
from typing import List

# Readable HOF 모듈 import (기본 HOF에서도 사용 가능)
from rfs.hof.readable import (
    # 규칙 적용 시스템
    apply_rules_to,
    
    # 검증 DSL
    validate_config, required, range_check, format_check, email_check,
    
    # 텍스트 스캔 
    scan_for, create_security_violation,
    
    # 배치 처리
    extract_from,
    
    # 편의 함수들
    quick_validate, quick_scan
)


# 1. 규칙 적용 시스템 예제

@dataclass 
class SecurityRule:
    """보안 규칙 예제 클래스"""
    name: str
    pattern: str
    risk_level: str = "medium"
    description: str = ""
    
    def apply(self, target: str):
        """규칙을 텍스트에 적용"""
        if self.pattern.lower() in target.lower():
            return {
                'rule_name': self.name,
                'message': f"보안 위험: '{self.pattern}' 발견",
                'matched_text': self.pattern,
                'risk_level': self.risk_level,
                'description': self.description,
                'type': 'security_violation'
            }
        return None

def demo_rules_application():
    """규칙 적용 시스템 데모"""
    print("=== 규칙 적용 시스템 데모 ===")
    
    # 보안 규칙 정의
    security_rules = [
        SecurityRule("password_leak", "password", "high", "비밀번호 노출 위험"),
        SecurityRule("api_key_leak", "api_key", "critical", "API 키 노출 위험"),
        SecurityRule("secret_leak", "secret", "high", "민감정보 노출 위험")
    ]
    
    # 검사할 텍스트
    suspicious_text = """
    const config = {
        password: "my_secret_password",
        api_key: "sk-1234567890abcdef",
        database_url: "postgresql://user:pass@localhost/db"
    }
    """
    
    # 🚫 기존 방식 (명령형, 복잡)
    print("\n--- 기존 방식 ---")
    old_violations = []
    for rule in security_rules:
        result = rule.apply(suspicious_text)
        if result:
            old_violations.append(result)
    
    print(f"기존 방식으로 발견된 위반사항: {len(old_violations)}개")
    for violation in old_violations:
        print(f"  - {violation['message']}")
    
    # ✅ 새로운 방식 (선언적, 가독성)
    print("\n--- 새로운 Readable HOF 방식 ---")
    violations = (
        apply_rules_to(suspicious_text)
        .using(security_rules)
        .collect_violations()
    )
    
    print(f"Readable HOF로 발견된 위반사항: {len(violations)}개")
    for violation in violations:
        print(f"  - {violation.message} (위험도: {violation.risk_level})")
    
    # 중요한 위반사항만 필터링
    critical_violations = (
        apply_rules_to(suspicious_text)
        .using(security_rules)
        .critical_violations()
    )
    
    print(f"중요한 위반사항: {len(critical_violations)}개")
    for violation in critical_violations:
        print(f"  - {violation.message}")


# 2. 검증 DSL 예제

@dataclass
class AppConfig:
    """애플리케이션 설정 예제 클래스"""
    redis_url: str = None
    openai_api_key: str = None
    max_tokens: int = 1000
    temperature: float = None
    admin_email: str = None

def demo_validation_dsl():
    """검증 DSL 데모"""
    print("\n=== 검증 DSL 데모 ===")
    
    # 테스트용 설정 객체들
    valid_config = AppConfig(
        redis_url="redis://localhost:6379",
        openai_api_key="sk-test123456",
        max_tokens=2000,
        temperature=0.7,
        admin_email="admin@example.com"
    )
    
    invalid_config = AppConfig(
        # redis_url 누락
        openai_api_key="",  # 빈 문자열
        max_tokens=50000,   # 범위 초과
        temperature=3.0,    # 범위 초과
        admin_email="invalid-email"  # 잘못된 형식
    )
    
    # 🚫 기존 방식 (반복적, 에러 취약)
    print("\n--- 기존 방식 ---")
    def old_validate(config):
        basic_rules = [
            (config.redis_url is not None, "Redis URL이 설정되지 않았습니다"),
            (config.openai_api_key is not None and config.openai_api_key.strip(), "OpenAI API 키가 설정되지 않았습니다"),
            (1 <= config.max_tokens <= 32000, "max_tokens는 1-32000 사이여야 합니다"),
            (config.temperature is None or 0 <= config.temperature <= 2, "temperature는 0-2 사이여야 합니다"),
        ]
        
        for is_valid, error_message in basic_rules:
            if not is_valid:
                return f"실패: {error_message}"
        
        return "성공"
    
    print("유효한 설정:", old_validate(valid_config))
    print("잘못된 설정:", old_validate(invalid_config))
    
    # ✅ 새로운 방식 (선언적, 재사용 가능)
    print("\n--- 새로운 Readable HOF 방식 ---")
    
    validation_rules = [
        required("redis_url", "Redis URL이 설정되지 않았습니다"),
        required("openai_api_key", "OpenAI API 키가 설정되지 않았습니다"), 
        range_check("max_tokens", 1, 32000, "max_tokens는 1-32000 사이여야 합니다"),
        range_check("temperature", 0, 2, "temperature는 0-2 사이여야 합니다") if valid_config.temperature else None,
        email_check("admin_email", "유효한 관리자 이메일이 필요합니다")
    ]
    
    # 유효한 설정 검증
    result = validate_config(valid_config).against_rules(validation_rules)
    if result.is_success():
        print("유효한 설정: ✅ 검증 통과")
    else:
        print(f"유효한 설정: ❌ {result.result.unwrap_error()}")
    
    # 잘못된 설정 검증  
    result = validate_config(invalid_config).against_rules(validation_rules)
    if result.is_success():
        print("잘못된 설정: ✅ 검증 통과")
    else:
        print(f"잘못된 설정: ❌ {result.result.unwrap_error()}")
    
    # 편의 함수 사용
    print("\n--- 편의 함수 사용 ---")
    result = quick_validate(
        valid_config,
        redis_url="required",
        max_tokens=(1, 32000),
        admin_email="email"
    )
    print("Quick validate 결과:", "✅ 성공" if result.is_success() else f"❌ {result.result.unwrap_error()}")


# 3. 텍스트 스캔 시스템 예제

def demo_text_scanning():
    """텍스트 스캔 시스템 데모"""
    print("\n=== 텍스트 스캔 시스템 데모 ===")
    
    # 보안 패턴들
    security_patterns = [
        re.compile(r'password\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'api[_-]?key\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'secret\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
    ]
    
    # 스캔할 코드
    code_content = """
    const config = {
        password: "super_secret_password",
        api_key: "sk-abc123def456ghi789",
        database_secret: "db_password_123",
        public_key: "not_sensitive_data"
    }
    
    const headers = {
        'Authorization': 'Bearer sk-another-api-key-here'
    }
    """
    
    # ✅ Readable HOF 방식
    print("--- Readable HOF 스캔 방식 ---")
    
    results = (
        scan_for(security_patterns)
        .in_text(code_content)
        .extract(create_security_violation)
        .filter_above_threshold("medium")
        .sort_by_risk()
    )
    
    print(f"발견된 보안 위험: {results.count()}개")
    for item in results.collect():
        if isinstance(item, dict):
            print(f"  - {item.get('description', item.get('rule_name', 'Unknown'))}: '{item.get('matched_text', 'N/A')}'")
    
    # 위험도별 그룹화
    grouped = results.group_by_risk()
    print(f"\n위험도별 분류:")
    for risk_level, items in grouped.items():
        print(f"  - {risk_level}: {len(items)}개")
    
    # 편의 함수 사용
    print("\n--- 편의 함수 사용 ---")
    quick_results = quick_scan(code_content, [r'password', r'secret', r'key'])
    print(f"Quick scan 결과: {len(quick_results)}개 매치")


# 4. 배치 처리 시스템 예제

@dataclass
class BatchResult:
    """배치 결과 예제"""
    url: str
    success: bool
    content: List[str] = None
    processing_time_ms: int = 0

def demo_batch_processing():
    """배치 처리 시스템 데모"""
    print("\n=== 배치 처리 시스템 데모 ===")
    
    # 테스트 배치 결과 데이터
    batch_results = [
        BatchResult("http://example.com/1", True, ["첫 번째 텍스트", "두 번째 텍스트", ""], 100),
        BatchResult("http://example.com/2", False, None, 0),  # 실패 케이스
        BatchResult("http://example.com/3", True, ["긴 텍스트입니다 - 유효함", "짧음"], 150),
        BatchResult("http://example.com/4", True, ["", "   ", "유효한 긴 텍스트 내용"], 80),
    ]
    
    # 🚫 기존 방식 (중첩 루프, 복잡)
    print("--- 기존 방식 ---")
    old_processed_items = []
    min_text_length = 10
    
    for result in batch_results:
        if result.success and result.content:
            for text_chunk in result.content:
                if len(text_chunk.strip()) > min_text_length:
                    old_processed_items.append({
                        'url': result.url,
                        'text': text_chunk.strip(),
                        'length': len(text_chunk.strip()),
                        'processing_time': result.processing_time_ms
                    })
    
    print(f"기존 방식 처리 결과: {len(old_processed_items)}개")
    for item in old_processed_items:
        print(f"  - {item['url']}: '{item['text'][:30]}...' ({item['length']}자)")
    
    # ✅ 새로운 방식 (체이닝, 선언적)
    print("\n--- 새로운 Readable HOF 방식 ---")
    
    def create_processed_item(text_and_result):
        """텍스트와 결과 정보로부터 처리된 아이템 생성"""
        text, result = text_and_result
        return {
            'url': result.url,
            'text': text.strip(),
            'length': len(text.strip()),
            'processing_time': result.processing_time_ms
        }
    
    # 체이닝으로 데이터 처리
    processed_items = []
    
    for result in batch_results:
        if result.success and result.content:
            items = (
                extract_from([(text, result) for text in result.content])
                .flatten_items()
                .transform_to(create_processed_item)
                .filter_by(lambda item: len(item['text']) > min_text_length)
                .collect()
            )
            processed_items.extend(items)
    
    print(f"Readable HOF 처리 결과: {len(processed_items)}개")
    for item in processed_items:
        print(f"  - {item['url']}: '{item['text'][:30]}...' ({item['length']}자)")


def main():
    """모든 데모 실행"""
    print("🚀 RFS Readable HOF 사용 예제")
    print("=" * 50)
    
    demo_rules_application()
    demo_validation_dsl()
    demo_text_scanning()
    demo_batch_processing()
    
    print("\n" + "=" * 50)
    print("✅ 모든 예제가 완료되었습니다!")
    
    # 성과 요약
    print("\n📊 Readable HOF의 장점:")
    print("  • 코드 가독성 향상: 자연어에 가까운 표현")
    print("  • 선언적 프로그래밍: 무엇을 할지에 집중")
    print("  • 재사용성: 규칙과 패턴의 모듈화")
    print("  • 체이닝: 복잡한 로직을 간단한 연결로")
    print("  • 타입 안전성: Result 패턴과 완벽 통합")


if __name__ == "__main__":
    main()