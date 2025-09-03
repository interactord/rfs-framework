"""
RFS Readable HOF Rules System Tests

규칙 적용 시스템의 단위 테스트입니다.
"""

import pytest
from dataclasses import dataclass

from rfs.hof.readable.rules import (
    apply_rules_to, RuleApplication, RuleProcessor,
    apply_single_rule, check_violations, count_violations
)
from rfs.hof.readable.types import ViolationInfo


@dataclass
class MockRule:
    """테스트용 가짜 규칙 클래스"""
    name: str
    should_violate: bool = False
    violation_message: str = "Mock violation"
    risk_level: str = "medium"
    
    def apply(self, target):
        if self.should_violate:
            return ViolationInfo(
                rule_name=self.name,
                message=self.violation_message,
                risk_level=self.risk_level
            )
        return None


@dataclass
class SimpleRule:
    """단순한 테스트 규칙"""
    name: str
    pattern: str
    
    def apply(self, target):
        if self.pattern in str(target):
            return {
                'rule_name': self.name,
                'message': f"Found '{self.pattern}' in text",
                'matched_text': self.pattern,
                'type': 'pattern_match'
            }
        return None


@dataclass 
class ErrorRule:
    """에러를 발생시키는 테스트 규칙"""
    name: str
    
    def apply(self, target):
        raise ValueError(f"Rule {self.name} failed")


class TestRuleApplication:
    """RuleApplication 클래스 테스트"""
    
    def test_apply_rules_to_creation(self):
        """apply_rules_to 함수 테스트"""
        target = "test_text"
        application = apply_rules_to(target)
        
        assert isinstance(application, RuleApplication)
        assert application.value == target
    
    def test_using_method_creates_processor(self):
        """using 메서드가 RuleProcessor를 생성하는지 테스트"""
        rules = [MockRule("test_rule")]
        application = apply_rules_to("target")
        processor = application.using(rules)
        
        assert isinstance(processor, RuleProcessor)
        assert processor.rules == rules
        assert processor.value == "target"
    
    def test_using_with_empty_rules(self):
        """빈 규칙 리스트로 using 테스트"""
        application = apply_rules_to("target")
        processor = application.using([])
        
        assert isinstance(processor, RuleProcessor)
        assert processor.rules == []
    
    def test_with_rule_method(self):
        """with_rule 메서드 테스트"""
        rule = MockRule("single_rule")
        application = apply_rules_to("target")
        processor = application.with_rule(rule)
        
        assert isinstance(processor, RuleProcessor)
        assert processor.rules == [rule]


class TestRuleProcessor:
    """RuleProcessor 클래스 테스트"""
    
    def test_collect_violations_with_violations(self):
        """위반 사항이 있는 경우 테스트"""
        rules = [
            MockRule("rule1", should_violate=True, violation_message="First violation"),
            MockRule("rule2", should_violate=True, violation_message="Second violation")
        ]
        text = "test text"
        
        violations = apply_rules_to(text).using(rules).collect_violations()
        
        assert len(violations) == 2
        assert any("First violation" in str(v) for v in violations)
        assert any("Second violation" in str(v) for v in violations)
    
    def test_collect_violations_without_violations(self):
        """위반 사항이 없는 경우 테스트"""
        rules = [
            MockRule("rule1", should_violate=False),
            MockRule("rule2", should_violate=False)
        ]
        text = "safe content"
        
        violations = apply_rules_to(text).using(rules).collect_violations()
        
        assert len(violations) == 0
    
    def test_collect_violations_with_mixed_results(self):
        """일부만 위반하는 경우 테스트"""
        rules = [
            MockRule("rule1", should_violate=True, violation_message="Violation found"),
            MockRule("rule2", should_violate=False),
            MockRule("rule3", should_violate=True, violation_message="Another violation")
        ]
        
        violations = apply_rules_to("test").using(rules).collect_violations()
        
        assert len(violations) == 2
        violation_messages = [str(v) for v in violations]
        assert any("Violation found" in msg for msg in violation_messages)
        assert any("Another violation" in msg for msg in violation_messages)
    
    def test_collect_violations_with_error_rule(self):
        """규칙 적용 중 오류 발생 테스트"""
        rules = [
            MockRule("good_rule", should_violate=True, violation_message="Good violation"),
            ErrorRule("error_rule")
        ]
        
        violations = apply_rules_to("test").using(rules).collect_violations()
        
        assert len(violations) == 2
        # 정상 규칙의 위반사항
        assert any("Good violation" in str(v) for v in violations)
        # 에러 규칙의 오류 위반사항
        assert any("규칙 적용 중 오류 발생" in str(v) for v in violations)
    
    def test_collect_results_with_processor(self):
        """processor를 사용한 collect_results 테스트"""
        rules = [
            SimpleRule("rule1", "test"),
            SimpleRule("rule2", "example")
        ]
        text = "This is a test example"
        
        def custom_processor(rule, target):
            return f"Processed {rule.name} on '{target}'"
        
        results = apply_rules_to(text).using(rules).collect_results(custom_processor)
        
        assert len(results) == 2
        assert results[0] == f"Processed rule1 on '{text}'"
        assert results[1] == f"Processed rule2 on '{text}'"
    
    def test_collect_results_with_error_in_processor(self):
        """processor에서 오류 발생 테스트"""
        rules = [MockRule("test_rule")]
        
        def failing_processor(rule, target):
            raise ValueError("Processor failed")
        
        results = apply_rules_to("test").using(rules).collect_results(failing_processor)
        
        assert len(results) == 1
        # 오류 정보가 결과에 포함되어야 함
        from rfs.hof.readable.types import ErrorInfo
        assert isinstance(results[0], ErrorInfo)
        assert "처리기 실행 실패" in results[0].message
    
    def test_first_violation(self):
        """첫 번째 위반 사항 반환 테스트"""
        rules = [
            MockRule("rule1", should_violate=False),
            MockRule("rule2", should_violate=True, violation_message="First found violation"),
            MockRule("rule3", should_violate=True, violation_message="Second violation")
        ]
        
        first = apply_rules_to("test").using(rules).first_violation()
        
        assert first is not None
        assert "First found violation" in str(first)
    
    def test_first_violation_with_no_violations(self):
        """위반사항이 없을 때 first_violation 테스트"""
        rules = [MockRule("rule1", should_violate=False)]
        
        first = apply_rules_to("test").using(rules).first_violation()
        
        assert first is None
    
    def test_has_violations_true(self):
        """위반 사항이 있는 경우 has_violations 테스트"""
        rules = [MockRule("rule1", should_violate=True)]
        
        has_violations = apply_rules_to("test").using(rules).has_violations()
        
        assert has_violations is True
    
    def test_has_violations_false(self):
        """위반 사항이 없는 경우 has_violations 테스트"""
        rules = [MockRule("rule1", should_violate=False)]
        
        has_violations = apply_rules_to("test").using(rules).has_violations()
        
        assert has_violations is False
    
    def test_count_violations(self):
        """위반 사항 개수 테스트"""
        rules = [
            MockRule("rule1", should_violate=True),
            MockRule("rule2", should_violate=False),
            MockRule("rule3", should_violate=True),
            MockRule("rule4", should_violate=True)
        ]
        
        count = apply_rules_to("test").using(rules).count_violations()
        
        assert count == 3
    
    def test_violations_by_risk(self):
        """위험도별 위반사항 그룹화 테스트"""
        rules = [
            MockRule("rule1", should_violate=True, risk_level="high"),
            MockRule("rule2", should_violate=True, risk_level="low"),
            MockRule("rule3", should_violate=True, risk_level="high"),
            MockRule("rule4", should_violate=True, risk_level="critical")
        ]
        
        grouped = apply_rules_to("test").using(rules).violations_by_risk()
        
        assert len(grouped["high"]) == 2
        assert len(grouped["low"]) == 1
        assert len(grouped["critical"]) == 1
    
    def test_critical_violations(self):
        """중요한 위반사항만 반환 테스트"""
        rules = [
            MockRule("rule1", should_violate=True, risk_level="critical"),
            MockRule("rule2", should_violate=True, risk_level="low"),
            MockRule("rule3", should_violate=True, risk_level="high"),
            MockRule("rule4", should_violate=True, risk_level="medium")
        ]
        
        critical = apply_rules_to("test").using(rules).critical_violations()
        
        # critical과 high 위험도만 반환되어야 함
        assert len(critical) == 2
        risk_levels = [v.risk_level for v in critical]
        assert "critical" in risk_levels
        assert "high" in risk_levels
        assert "low" not in risk_levels
        assert "medium" not in risk_levels
    
    def test_to_chainable_result(self):
        """ChainableResult 변환 테스트"""
        rules = [MockRule("rule1", should_violate=True)]
        
        result = apply_rules_to("test").using(rules).to_chainable_result()
        
        assert result.is_success()
        violations = result.result.unwrap()
        assert len(violations) == 1


class TestConvenienceFunctions:
    """편의 함수들 테스트"""
    
    def test_apply_single_rule(self):
        """단일 규칙 적용 테스트"""
        rule = MockRule("test_rule", should_violate=True, violation_message="Single rule violation")
        
        violations = apply_single_rule("test target", rule)
        
        assert len(violations) == 1
        assert "Single rule violation" in str(violations[0])
    
    def test_check_violations_true(self):
        """위반사항 존재 확인 테스트 (True)"""
        rules = [MockRule("rule1", should_violate=True)]
        
        has_violations = check_violations("test", rules)
        
        assert has_violations is True
    
    def test_check_violations_false(self):
        """위반사항 존재 확인 테스트 (False)"""
        rules = [MockRule("rule1", should_violate=False)]
        
        has_violations = check_violations("test", rules)
        
        assert has_violations is False
    
    def test_count_violations_function(self):
        """위반사항 개수 함수 테스트"""
        rules = [
            MockRule("rule1", should_violate=True),
            MockRule("rule2", should_violate=False),
            MockRule("rule3", should_violate=True)
        ]
        
        count = count_violations("test", rules)
        
        assert count == 2


class TestViolationCreation:
    """위반사항 생성 로직 테스트"""
    
    def test_create_violation_from_violation_info(self):
        """ViolationInfo 객체 반환 테스트"""
        violation = ViolationInfo("test_rule", "Test message", "high")
        
        class ViolationRule:
            name = "test_rule"
            
            def apply(self, target):
                return violation
        
        rule = ViolationRule()
        violations = apply_rules_to("test").using([rule]).collect_violations()
        
        assert len(violations) == 1
        assert violations[0] == violation
    
    def test_create_violation_from_dict(self):
        """딕셔너리 결과로부터 위반사항 생성 테스트"""
        class DictRule:
            name = "dict_rule"
            
            def apply(self, target):
                return {
                    'rule_name': 'custom_name',
                    'message': 'Dictionary violation',
                    'risk_level': 'high',
                    'position': (0, 5)
                }
        
        rule = DictRule()
        violations = apply_rules_to("test").using([rule]).collect_violations()
        
        assert len(violations) == 1
        violation = violations[0]
        assert violation.rule_name == 'custom_name'
        assert violation.message == 'Dictionary violation'
        assert violation.risk_level == 'high'
        assert violation.position == (0, 5)
    
    def test_create_violation_from_string(self):
        """문자열 결과로부터 위반사항 생성 테스트"""
        class StringRule:
            name = "string_rule"
            
            def apply(self, target):
                return "Simple string error message"
        
        rule = StringRule()
        violations = apply_rules_to("test").using([rule]).collect_violations()
        
        assert len(violations) == 1
        violation = violations[0]
        assert violation.rule_name == "string_rule"
        assert violation.message == "Simple string error message"
        assert violation.risk_level == "medium"  # 기본값
    
    def test_create_violation_from_other_object(self):
        """기타 객체로부터 위반사항 생성 테스트"""
        class ObjectRule:
            name = "object_rule"
            
            def apply(self, target):
                return 12345  # 숫자 객체
        
        rule = ObjectRule()
        violations = apply_rules_to("test").using([rule]).collect_violations()
        
        assert len(violations) == 1
        violation = violations[0]
        assert violation.rule_name == "object_rule"
        assert violation.message == "12345"
        assert violation.risk_level == "medium"
        assert violation.context['original_result'] == 12345