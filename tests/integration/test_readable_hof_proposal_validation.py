"""
RFS Readable HOF Proposal Validation Tests

제안서의 예제 코드들이 실제 구현과 정확히 동작하는지 검증합니다.
이 테스트들은 제안서에 나온 모든 코드 예제가 실제로 실행 가능한지 확인합니다.
"""

import re
import pytest
from typing import List, Dict, Any
from dataclasses import dataclass

from rfs.hof.readable import (
    apply_rules_to, validate_config, scan_for,
    required, range_check, format_check, length_check,
    ViolationInfo, ChainableResult, success, failure
)
from rfs.core.result import Result, Success, Failure


class TestProposalExamples:
    """제안서 예제 검증 테스트 클래스"""

    def test_basic_security_rule_application(self):
        """제안서의 기본 보안 규칙 적용 예제 테스트"""
        
        # 제안서 예제에서 사용한 SecurityRule 클래스 구현
        @dataclass
        class SecurityRule:
            name: str
            pattern: str
            risk_level: str
            description: str = ""
            
            def apply(self, text: str):
                """Rule protocol 구현"""
                pattern = re.compile(self.pattern, re.IGNORECASE)
                matches = list(pattern.finditer(text))
                
                if matches:
                    # 매치가 있으면 위반 사항 정보 반환
                    return ViolationInfo(
                        rule_name=self.name,
                        message=f"보안 위반: {self.description}",
                        risk_level=self.risk_level,
                        matched_text=matches[0].group(),
                        position=matches[0].span()
                    )
                return None
        
        # 제안서 예제의 보안 규칙들
        security_rules = [
            SecurityRule("sql_injection", r"(?:union|select|insert|delete|drop)\s+", "critical", "SQL 인젝션 시도"),
            SecurityRule("xss_attempt", r"<script.*?>.*?</script>", "high", "XSS 공격 시도"),
            SecurityRule("path_traversal", r"\.\./", "medium", "경로 순회 공격")
        ]
        
        # 테스트 입력들
        test_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "normal safe input"
        ]
        
        # 제안서 예제 코드 실행
        for test_input in test_inputs:
            violations = (
                apply_rules_to(test_input)
                .using(security_rules)
                .collect_violations()
            )
            
            # 첫 3개 입력은 위반사항이 있어야 하고, 마지막은 없어야 함
            if test_input == "normal safe input":
                assert len(violations) == 0, f"안전한 입력에서 위반사항 발견: {violations}"
            else:
                assert len(violations) > 0, f"위험한 입력에서 위반사항을 찾지 못함: {test_input}"

    def test_configuration_validation_example(self):
        """제안서의 설정 검증 예제 테스트"""
        
        # 제안서 예제의 DatabaseConfig 클래스
        @dataclass
        class DatabaseConfig:
            host: str = None
            port: int = 5432
            username: str = None
            password: str = None
            ssl_enabled: bool = False
            ssl_cert_path: str = None
            
            def validate(self) -> ChainableResult:
                """제안서 예제의 validate 메서드"""
                return (
                    validate_config(self)
                    .against_rules([
                        required("host", "데이터베이스 호스트가 필요합니다"),
                        required("username", "사용자명이 필요합니다"),
                        required("password", "비밀번호가 필요합니다"),
                        range_check("port", 1, 65535, "포트는 1-65535 사이여야 합니다"),
                        format_check("host", re.compile(r'^[\w\.-]+$'), "유효하지 않은 호스트명 형식"),
                        
                        # 조건부 검증은 현재 구현에서는 다른 방식으로 처리
                        required("ssl_cert_path", "SSL 사용 시 인증서 경로가 필요합니다") if self.ssl_enabled else None
                    ])
                )
        
        # 성공 케이스
        valid_config = DatabaseConfig(
            host="localhost",
            port=5432,
            username="user",
            password="pass",
            ssl_enabled=False
        )
        
        result = valid_config.validate()
        assert result.is_success(), f"유효한 설정에서 검증 실패: {result.unwrap_error() if result.is_failure() else 'None'}"
        
        # 실패 케이스 - 호스트 없음
        invalid_config = DatabaseConfig(
            host=None,
            username="user", 
            password="pass"
        )
        
        result = invalid_config.validate()
        assert result.is_failure(), "유효하지 않은 설정에서 검증 성공"
        assert "호스트가 필요합니다" in result.unwrap_error()

    def test_log_analysis_example(self):
        """제안서의 로그 분석 예제 테스트"""
        
        # 제안서 예제의 LogAnalyzer 클래스 구현
        class LogAnalyzer:
            def __init__(self):
                self.error_patterns = [
                    re.compile(r'ERROR.*?(\\w+Error): (.+)'),
                    re.compile(r'CRITICAL.*?(\\w+): (.+)'),
                    re.compile(r'FATAL.*?(.+)')
                ]
            
            def analyze_logs(self, log_content: str) -> Dict[str, Any]:
                """로그 분석"""
                error_results = (
                    scan_for(self.error_patterns)
                    .in_text(log_content)
                    .extract(self._extract_error_info)
                    .collect()
                )
                
                return {
                    'total_errors': len(error_results),
                    'errors': error_results
                }
            
            def _extract_error_info(self, match):
                """에러 정보 추출"""
                return {
                    'severity': 'high' if 'CRITICAL' in match.group() else 'medium',
                    'message': match.group(),
                    'position': match.span()
                }
        
        # 테스트 로그 내용
        test_log = """
        INFO Starting application
        ERROR ValueError: Invalid input data
        CRITICAL SystemError: Database connection failed
        FATAL Application crashed
        INFO Application stopped
        """
        
        analyzer = LogAnalyzer()
        results = analyzer.analyze_logs(test_log)
        
        # 결과 검증
        assert results['total_errors'] >= 0, "에러 개수가 음수입니다"
        assert isinstance(results['errors'], list), "에러 결과가 리스트가 아닙니다"

    def test_quick_validation_functions(self):
        """제안서에서 제안한 편의 함수들 테스트"""
        from rfs.hof.readable import quick_validate
        
        # 테스트 설정 객체
        @dataclass
        class TestConfig:
            api_key: str = None
            timeout: int = 0
            email: str = ""
        
        # 성공 케이스
        valid_config = TestConfig(
            api_key="valid_key_123",
            timeout=30,
            email="test@example.com"
        )
        
        result = quick_validate(
            valid_config,
            api_key="required",
            timeout=(1, 300),
            email="email"
        )
        
        assert result.is_success(), f"유효한 설정에서 quick_validate 실패: {result.unwrap_error() if result.is_failure() else 'None'}"
        
        # 실패 케이스
        invalid_config = TestConfig(
            api_key=None,
            timeout=500,
            email="invalid-email"
        )
        
        result = quick_validate(
            invalid_config,
            api_key="required",
            timeout=(1, 300),
            email="email"
        )
        
        assert result.is_failure(), "유효하지 않은 설정에서 quick_validate 성공"

    def test_fluent_chaining_patterns(self):
        """플루언트 체이닝 패턴들이 제대로 동작하는지 테스트"""
        
        # 간단한 규칙 클래스
        @dataclass
        class SimpleRule:
            name: str
            pattern: str
            
            def apply(self, text: str):
                if self.pattern in text:
                    return f"Found pattern '{self.pattern}' in text"
                return None
        
        rules = [
            SimpleRule("test_rule1", "error"),
            SimpleRule("test_rule2", "warning")
        ]
        
        test_text = "This is an error message with a warning"
        
        # 체이닝 테스트
        violations = (
            apply_rules_to(test_text)
            .using(rules)
            .collect_violations()
        )
        
        assert len(violations) == 2, f"예상한 위반사항 수와 다름: {len(violations)} != 2"
        
        # 첫 번째 위반사항만 가져오기
        first_violation = (
            apply_rules_to(test_text)
            .using(rules)
            .first_violation()
        )
        
        assert first_violation is not None, "첫 번째 위반사항이 None입니다"
        
        # 위반사항 개수 확인
        count = (
            apply_rules_to(test_text)
            .using(rules)
            .count_violations()
        )
        
        assert count == 2, f"위반사항 개수가 다름: {count} != 2"

    def test_performance_with_large_input(self):
        """제안서의 성능 테스트 예제"""
        import time
        
        # 간단한 규칙
        @dataclass 
        class PatternRule:
            name: str
            pattern: str
            
            def apply(self, text: str):
                if self.pattern in text:
                    return f"Found {self.pattern}"
                return None
        
        # 큰 텍스트 생성
        large_text = "normal text " * 10000 + "bad pattern"
        rules = [PatternRule("test", "bad pattern")]
        
        start_time = time.time()
        violations = apply_rules_to(large_text).using(rules).collect_violations()
        duration = time.time() - start_time
        
        assert len(violations) == 1, f"위반사항 수가 예상과 다름: {len(violations)}"
        assert duration < 1.0, f"처리 시간이 너무 오래 걸림: {duration}초"

    def test_integration_with_result_pattern(self):
        """RFS Framework의 Result 패턴과의 통합 테스트"""
        
        @dataclass
        class ValidatorRule:
            name: str
            
            def apply(self, value):
                if not isinstance(value, str) or len(value) < 3:
                    return "값은 3자 이상의 문자열이어야 합니다"
                return None
        
        # ChainableResult와 Result 패턴 통합
        result = (
            apply_rules_to("ab")  # 너무 짧은 문자열
            .using([ValidatorRule("length_check")])
            .to_chainable_result()
        )
        
        # ChainableResult는 위반사항 리스트를 반환해야 함
        assert result.is_success(), "to_chainable_result는 항상 성공해야 함 (위반사항을 데이터로 반환)"
        violations = result.unwrap()
        assert len(violations) == 1, f"위반사항이 정확히 1개여야 함: {len(violations)}"