"""
RFS Readable HOF Rules Module - Comprehensive Tests

이 모듈은 규칙 적용 시스템의 모든 기능을 포괄적으로 테스트합니다.
apply_rules_to 패턴과 관련된 모든 기능을 검증합니다.
"""

import pytest
import re
from dataclasses import dataclass
from typing import Any, Optional, List

from rfs.hof.readable.rules import (
    RuleApplication, RuleProcessor, apply_rules_to,
    apply_single_rule, check_violations, count_violations
)
from rfs.hof.readable.types import ViolationInfo
from rfs.hof.readable.base import ChainableResult


class TestRuleApplication:
    """RuleApplication 클래스의 기능 테스트"""

    def test_rule_application_creation(self):
        """RuleApplication 생성 테스트"""
        target = "test data"
        app = RuleApplication(target)
        assert app.value == target

    def test_using_with_rules(self):
        """using 메서드로 규칙 적용 테스트"""
        class MockRule:
            def apply(self, target):
                return "mock violation" if "error" in target else None
        
        target = "This is an error message"
        rules = [MockRule()]
        
        app = RuleApplication(target)
        processor = app.using(rules)
        
        assert isinstance(processor, RuleProcessor)
        assert processor.value == target
        assert processor.rules == rules

    def test_using_with_empty_rules(self):
        """빈 규칙 리스트로 using 테스트"""
        target = "test"
        app = RuleApplication(target)
        processor = app.using([])
        
        assert isinstance(processor, RuleProcessor)
        assert processor.rules == []

    def test_with_rule_single(self):
        """with_rule 메서드로 단일 규칙 적용 테스트"""
        class MockRule:
            def apply(self, target):
                return None
        
        target = "test"
        rule = MockRule()
        
        app = RuleApplication(target)
        processor = app.with_rule(rule)
        
        assert isinstance(processor, RuleProcessor)
        assert len(processor.rules) == 1
        assert processor.rules[0] == rule


class TestRuleProcessor:
    """RuleProcessor 클래스의 기능 테스트"""

    def setUp(self):
        """테스트 설정"""
        @dataclass
        class TestRule:
            name: str
            pattern: str
            risk_level: str = "medium"
            
            def apply(self, text):
                if self.pattern in text:
                    return ViolationInfo(
                        rule_name=self.name,
                        message=f"Found pattern '{self.pattern}'",
                        risk_level=self.risk_level
                    )
                return None
        
        self.TestRule = TestRule

    def test_processor_initialization(self):
        """RuleProcessor 초기화 테스트"""
        target = "test"
        rules = []
        processor = RuleProcessor(target, rules)
        
        assert processor.value == target
        assert processor.rules == rules

    def test_collect_violations_basic(self):
        """기본 위반사항 수집 테스트"""
        self.setUp()
        
        rules = [
            self.TestRule("test_rule1", "error"),
            self.TestRule("test_rule2", "warning")
        ]
        text = "This is an error and warning message"
        
        processor = RuleProcessor(text, rules)
        violations = processor.collect_violations()
        
        assert len(violations) == 2
        for violation in violations:
            assert isinstance(violation, ViolationInfo)
            assert violation.rule_name in ["test_rule1", "test_rule2"]

    def test_collect_violations_no_matches(self):
        """매치되는 것이 없을 때 위반사항 수집 테스트"""
        self.setUp()
        
        rules = [self.TestRule("test_rule", "notfound")]
        text = "This is a normal message"
        
        processor = RuleProcessor(text, rules)
        violations = processor.collect_violations()
        
        assert len(violations) == 0

    def test_collect_violations_with_string_result(self):
        """문자열 결과를 반환하는 규칙 테스트"""
        class StringRule:
            name = "string_rule"
            
            def apply(self, text):
                return "String violation message" if "error" in text else None
        
        rules = [StringRule()]
        text = "This is an error"
        
        processor = RuleProcessor(text, rules)
        violations = processor.collect_violations()
        
        assert len(violations) == 1
        assert violations[0].message == "String violation message"
        assert violations[0].rule_name == "string_rule"

    def test_collect_violations_with_dict_result(self):
        """딕셔너리 결과를 반환하는 규칙 테스트"""
        class DictRule:
            name = "dict_rule"
            
            def apply(self, text):
                if "error" in text:
                    return {
                        'rule_name': 'custom_dict_rule',
                        'message': 'Dictionary violation',
                        'risk_level': 'high',
                        'matched_text': 'error'
                    }
                return None
        
        rules = [DictRule()]
        text = "This is an error"
        
        processor = RuleProcessor(text, rules)
        violations = processor.collect_violations()
        
        assert len(violations) == 1
        violation = violations[0]
        assert violation.rule_name == "custom_dict_rule"
        assert violation.message == "Dictionary violation"
        assert violation.risk_level == "high"

    def test_collect_violations_with_exception(self):
        """규칙 적용 중 예외 발생 테스트"""
        class FailingRule:
            name = "failing_rule"
            
            def apply(self, text):
                raise ValueError("Rule application failed")
        
        rules = [FailingRule()]
        text = "test"
        
        processor = RuleProcessor(text, rules)
        violations = processor.collect_violations()
        
        assert len(violations) == 1
        violation = violations[0]
        assert violation.rule_name == "failing_rule"
        assert "규칙 적용 중 오류 발생" in violation.message
        assert violation.risk_level == "high"

    def test_collect_results_basic(self):
        """collect_results 메서드 기본 테스트"""
        self.setUp()
        
        rules = [
            self.TestRule("rule1", "test"),
            self.TestRule("rule2", "example")
        ]
        text = "This is a test example"
        
        def custom_processor(rule, target):
            return f"Processed {rule.name} on '{target}'"
        
        processor = RuleProcessor(text, rules)
        results = processor.collect_results(custom_processor)
        
        assert len(results) == 2
        assert all("Processed" in str(result) for result in results)

    def test_collect_results_with_exception(self):
        """collect_results에서 예외 발생 테스트"""
        self.setUp()
        
        rules = [self.TestRule("rule1", "test")]
        text = "test"
        
        def failing_processor(rule, target):
            raise ValueError("Processor failed")
        
        processor = RuleProcessor(text, rules)
        results = processor.collect_results(failing_processor)
        
        assert len(results) == 1
        # 결과에 ErrorInfo가 포함되어야 함
        from rfs.hof.readable.types import ErrorInfo
        assert isinstance(results[0], ErrorInfo)

    def test_first_violation(self):
        """first_violation 메서드 테스트"""
        self.setUp()
        
        rules = [
            self.TestRule("rule1", "first"),
            self.TestRule("rule2", "second")
        ]
        text = "This contains first and second patterns"
        
        processor = RuleProcessor(text, rules)
        first_violation = processor.first_violation()
        
        assert first_violation is not None
        assert first_violation.rule_name == "rule1"  # 첫 번째 규칙의 위반사항

    def test_first_violation_none(self):
        """매치되는 위반사항이 없을 때 first_violation 테스트"""
        self.setUp()
        
        rules = [self.TestRule("rule1", "notfound")]
        text = "This is normal text"
        
        processor = RuleProcessor(text, rules)
        first_violation = processor.first_violation()
        
        assert first_violation is None

    def test_has_violations_true(self):
        """has_violations True 케이스 테스트"""
        self.setUp()
        
        rules = [self.TestRule("rule1", "error")]
        text = "This is an error message"
        
        processor = RuleProcessor(text, rules)
        assert processor.has_violations() is True

    def test_has_violations_false(self):
        """has_violations False 케이스 테스트"""
        self.setUp()
        
        rules = [self.TestRule("rule1", "notfound")]
        text = "This is normal text"
        
        processor = RuleProcessor(text, rules)
        assert processor.has_violations() is False

    def test_count_violations(self):
        """count_violations 메서드 테스트"""
        self.setUp()
        
        rules = [
            self.TestRule("rule1", "error"),
            self.TestRule("rule2", "warning"),
            self.TestRule("rule3", "info")
        ]
        text = "This has error and warning but no info messages"
        
        processor = RuleProcessor(text, rules)
        count = processor.count_violations()
        
        assert count == 2  # error, warning

    def test_violations_by_risk(self):
        """violations_by_risk 메서드 테스트"""
        self.setUp()
        
        rules = [
            self.TestRule("rule1", "critical", "critical"),
            self.TestRule("rule2", "error", "high"),
            self.TestRule("rule3", "warning", "medium"),
            self.TestRule("rule4", "info", "low")
        ]
        text = "This has critical error warning info messages"
        
        processor = RuleProcessor(text, rules)
        grouped = processor.violations_by_risk()
        
        assert "critical" in grouped
        assert "high" in grouped
        assert "medium" in grouped
        assert "low" in grouped
        
        assert len(grouped["critical"]) == 1
        assert len(grouped["high"]) == 1
        assert len(grouped["medium"]) == 1
        assert len(grouped["low"]) == 1

    def test_critical_violations(self):
        """critical_violations 메서드 테스트"""
        self.setUp()
        
        rules = [
            self.TestRule("rule1", "critical", "critical"),
            self.TestRule("rule2", "error", "high"),
            self.TestRule("rule3", "warning", "medium"),
            self.TestRule("rule4", "info", "low")
        ]
        text = "This has critical error warning info messages"
        
        processor = RuleProcessor(text, rules)
        critical = processor.critical_violations()
        
        # critical과 high만 포함되어야 함
        assert len(critical) == 2
        risk_levels = [v.risk_level for v in critical]
        assert "critical" in risk_levels
        assert "high" in risk_levels
        assert "medium" not in risk_levels
        assert "low" not in risk_levels

    def test_to_chainable_result_success(self):
        """to_chainable_result 성공 케이스 테스트"""
        self.setUp()
        
        rules = [self.TestRule("rule1", "test")]
        text = "This is a test message"
        
        processor = RuleProcessor(text, rules)
        result = processor.to_chainable_result()
        
        assert isinstance(result, ChainableResult)
        assert result.is_success()
        
        violations = result.unwrap()
        assert len(violations) == 1

    def test_to_chainable_result_with_exception(self):
        """to_chainable_result 예외 발생 케이스 테스트"""
        # 예외를 발생시키는 mock processor 생성
        class BadProcessor(RuleProcessor):
            def collect_violations(self):
                raise RuntimeError("Collection failed")
        
        processor = BadProcessor("test", [])
        result = processor.to_chainable_result()
        
        assert isinstance(result, ChainableResult)
        assert result.is_failure()
        assert "위반 사항 수집 실패" in result.unwrap_error()


class TestApplyRulesToFunction:
    """apply_rules_to 함수의 기능 테스트"""

    def test_apply_rules_to_basic(self):
        """apply_rules_to 기본 기능 테스트"""
        target = "test data"
        app = apply_rules_to(target)
        
        assert isinstance(app, RuleApplication)
        assert app.value == target

    def test_apply_rules_to_chaining(self):
        """apply_rules_to 체이닝 테스트"""
        class MockRule:
            name = "mock_rule"
            
            def apply(self, target):
                return ViolationInfo(
                    rule_name=self.name,
                    message="Mock violation",
                    risk_level="medium"
                ) if "error" in target else None
        
        target = "This is an error message"
        rules = [MockRule()]
        
        violations = (
            apply_rules_to(target)
            .using(rules)
            .collect_violations()
        )
        
        assert len(violations) == 1
        assert violations[0].rule_name == "mock_rule"


class TestConvenienceFunctions:
    """편의 함수들의 테스트"""

    def setUp(self):
        """테스트 설정"""
        @dataclass
        class TestRule:
            name: str
            pattern: str
            
            def apply(self, text):
                return f"Found {self.pattern}" if self.pattern in text else None
        
        self.TestRule = TestRule

    def test_apply_single_rule(self):
        """apply_single_rule 함수 테스트"""
        self.setUp()
        
        rule = self.TestRule("test_rule", "error")
        target = "This is an error message"
        
        violations = apply_single_rule(target, rule)
        
        assert len(violations) == 1

    def test_check_violations_true(self):
        """check_violations True 케이스 테스트"""
        self.setUp()
        
        rules = [self.TestRule("rule1", "error")]
        target = "This is an error message"
        
        has_violations = check_violations(target, rules)
        assert has_violations is True

    def test_check_violations_false(self):
        """check_violations False 케이스 테스트"""
        self.setUp()
        
        rules = [self.TestRule("rule1", "notfound")]
        target = "This is a normal message"
        
        has_violations = check_violations(target, rules)
        assert has_violations is False

    def test_count_violations_function(self):
        """count_violations 함수 테스트"""
        self.setUp()
        
        rules = [
            self.TestRule("rule1", "error"),
            self.TestRule("rule2", "warning")
        ]
        target = "This has error and warning messages"
        
        count = count_violations(target, rules)
        assert count == 2


class TestRealWorldScenarios:
    """실제 사용 시나리오 테스트"""

    def test_security_validation_scenario(self):
        """보안 검증 시나리오 테스트"""
        @dataclass
        class SecurityRule:
            name: str
            pattern: str
            risk_level: str
            description: str = ""
            
            def apply(self, text):
                import re
                pattern = re.compile(self.pattern, re.IGNORECASE)
                matches = list(pattern.finditer(text))
                
                if matches:
                    return ViolationInfo(
                        rule_name=self.name,
                        message=f"보안 위반: {self.description}",
                        risk_level=self.risk_level,
                        matched_text=matches[0].group(),
                        position=matches[0].span()
                    )
                return None
        
        security_rules = [
            SecurityRule("sql_injection", r"(?:union|select|insert|delete|drop)\s+", "critical", "SQL 인젝션 시도"),
            SecurityRule("xss_attempt", r"<script.*?>.*?</script>", "high", "XSS 공격 시도"),
            SecurityRule("path_traversal", r"\.\./", "medium", "경로 순회 공격")
        ]
        
        # 위험한 입력들
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "normal safe input"
        ]
        
        for input_text in malicious_inputs:
            violations = (
                apply_rules_to(input_text)
                .using(security_rules)
                .collect_violations()
            )
            
            # 마지막 입력(normal safe input)을 제외하고는 위반사항이 있어야 함
            if input_text == "normal safe input":
                assert len(violations) == 0
            else:
                assert len(violations) > 0
                # 위험 수준별로 그룹화하여 검증
                processor = apply_rules_to(input_text).using(security_rules)
                grouped = processor.violations_by_risk()
                assert len(grouped) > 0

    def test_code_quality_validation_scenario(self):
        """코드 품질 검증 시나리오 테스트"""
        class CodeQualityRule:
            def __init__(self, name, pattern, severity):
                self.name = name
                self.pattern = pattern
                self.severity = severity
            
            def apply(self, code):
                import re
                matches = list(re.finditer(self.pattern, code, re.IGNORECASE | re.MULTILINE))
                
                results = []
                for match in matches:
                    results.append(ViolationInfo(
                        rule_name=self.name,
                        message=f"코드 품질 이슈: {match.group()}",
                        risk_level=self.severity,
                        matched_text=match.group(),
                        position=match.span()
                    ))
                
                return results if results else None
        
        quality_rules = [
            CodeQualityRule("todo_found", r"TODO[:\s]+.*", "low"),
            CodeQualityRule("fixme_found", r"FIXME[:\s]+.*", "medium"),
            CodeQualityRule("hack_found", r"HACK[:\s]+.*", "high"),
            CodeQualityRule("magic_number", r"\b\d{3,}\b", "medium")  # 3자리 이상 숫자
        ]
        
        source_code = """
        def process_data(items):
            # TODO: Add input validation
            if len(items) > 1000:  # Magic number
                # FIXME: This should use proper pagination
                items = items[:1000]
            
            # HACK: Quick workaround for empty lists
            if not items:
                return []
            
            return [item * 2 for item in items]
        """
        
        # 각 규칙을 개별적으로 적용 (위의 Rule은 리스트를 반환할 수 있으므로)
        all_violations = []
        for rule in quality_rules:
            result = rule.apply(source_code)
            if result:
                if isinstance(result, list):
                    all_violations.extend(result)
                else:
                    all_violations.append(result)
        
        # TODO, FIXME, HACK, 매직넘버(1000) 발견되어야 함
        assert len(all_violations) >= 4
        
        # 위험 수준별 분류 확인
        risk_levels = [v.risk_level for v in all_violations]
        assert "low" in risk_levels      # TODO
        assert "medium" in risk_levels   # FIXME, 매직넘버
        assert "high" in risk_levels     # HACK

    def test_configuration_validation_scenario(self):
        """설정 검증 시나리오 테스트"""
        @dataclass
        class ConfigRule:
            name: str
            field: str
            validator: callable
            message: str
            
            def apply(self, config):
                try:
                    if not self.validator(getattr(config, self.field, None)):
                        return ViolationInfo(
                            rule_name=self.name,
                            message=self.message,
                            risk_level="high"  # 설정 오류는 심각함
                        )
                except Exception as e:
                    return ViolationInfo(
                        rule_name=self.name,
                        message=f"{self.message} (검증 오류: {str(e)})",
                        risk_level="critical"
                    )
                return None
        
        @dataclass
        class AppConfig:
            database_url: str = None
            api_key: str = None
            port: int = 8080
            debug: bool = False
        
        config_rules = [
            ConfigRule("db_url_required", "database_url", 
                      lambda x: x is not None and x.startswith(('mysql://', 'postgresql://')),
                      "데이터베이스 URL이 필요하고 올바른 형식이어야 합니다"),
            ConfigRule("api_key_required", "api_key", 
                      lambda x: x is not None and len(x) >= 10,
                      "API 키가 필요하고 최소 10자 이상이어야 합니다"),
            ConfigRule("port_valid", "port", 
                      lambda x: isinstance(x, int) and 1 <= x <= 65535,
                      "포트는 1-65535 사이의 정수여야 합니다"),
            ConfigRule("debug_production", "debug", 
                      lambda x: x is False,  # 프로덕션에서는 debug가 False여야 함
                      "프로덕션 환경에서는 debug 모드를 비활성화해야 합니다")
        ]
        
        # 유효하지 않은 설정
        invalid_config = AppConfig(
            database_url="invalid_url",
            api_key="short",
            port=70000,  # 범위 초과
            debug=True   # 프로덕션에서 위험
        )
        
        violations = (
            apply_rules_to(invalid_config)
            .using(config_rules)
            .collect_violations()
        )
        
        # 모든 규칙에서 위반사항이 발견되어야 함
        assert len(violations) == 4
        
        # 모든 위반사항이 높은 위험 수준을 가져야 함
        for violation in violations:
            assert violation.risk_level in ["high", "critical"]

    def test_performance_with_many_rules(self):
        """많은 규칙에 대한 성능 테스트"""
        import time
        
        # 많은 규칙 생성
        class SimpleRule:
            def __init__(self, name, keyword):
                self.name = name
                self.keyword = keyword
            
            def apply(self, text):
                return f"Found {self.keyword}" if self.keyword in text.lower() else None
        
        # 100개의 규칙 생성
        rules = [SimpleRule(f"rule_{i}", f"keyword{i}") for i in range(100)]
        
        # 테스트 텍스트 (일부 키워드 포함)
        test_text = "This text contains keyword5 and keyword50 and keyword99"
        
        start_time = time.time()
        violations = (
            apply_rules_to(test_text)
            .using(rules)
            .collect_violations()
        )
        duration = time.time() - start_time
        
        assert len(violations) == 3  # keyword5, keyword50, keyword99
        assert duration < 1.0  # 1초 내에 완료되어야 함


if __name__ == "__main__":
    pytest.main([__file__, "-v"])