"""
RFS Readable HOF Rules System

규칙 적용 시스템을 구현합니다.
자연스러운 체이닝 방식으로 규칙들을 데이터에 적용하고 위반 사항을 수집할 수 있게 합니다.

사용 예:
    violations = apply_rules_to(text).using(security_rules).collect_violations()
"""

from typing import Any, Callable, List, Optional
from dataclasses import dataclass

from .base import FluentBase, ChainableResult, success, failure
from .types import Rule, ViolationInfo, ErrorInfo, T, R

class RuleApplication(FluentBase[T]):
    """
    규칙 적용을 위한 플루언트 인터페이스
    
    이 클래스는 규칙을 적용할 대상 데이터를 보유하고,
    규칙들을 적용할 수 있는 메서드를 제공합니다.
    """
    
    def using(self, rules: List[Rule]) -> 'RuleProcessor[T]':
        """
        규칙들을 사용하여 처리기를 생성합니다.
        
        Args:
            rules: 적용할 규칙들의 리스트
            
        Returns:
            규칙 처리기 인스턴스
        """
        if not rules:
            # 빈 규칙 리스트인 경우 경고하지만 계속 진행
            return RuleProcessor(self._value, [])
        
        return RuleProcessor(self._value, rules)
    
    def with_rule(self, rule: Rule) -> 'RuleProcessor[T]':
        """
        단일 규칙으로 처리기를 생성합니다.
        
        Args:
            rule: 적용할 규칙
            
        Returns:
            규칙 처리기 인스턴스
        """
        return RuleProcessor(self._value, [rule])

@dataclass
class RuleProcessor(FluentBase[T]):
    """
    규칙 기반 처리를 위한 플루언트 인터페이스
    
    실제로 규칙들을 데이터에 적용하고 결과를 수집하는 메서드들을 제공합니다.
    """
    rules: List[Rule]
    
    def __init__(self, target: T, rules: List[Rule]):
        """
        규칙 처리기를 초기화합니다.
        
        Args:
            target: 규칙을 적용할 대상 데이터
            rules: 적용할 규칙들
        """
        super().__init__(target)
        self.rules = rules or []
    
    def collect_violations(self) -> List[ViolationInfo]:
        """
        모든 규칙을 적용하여 위반 사항들을 수집합니다.
        
        Returns:
            발견된 위반 사항들의 리스트
        """
        violations = []
        
        for rule in self.rules:
            try:
                # 규칙을 적용
                result = rule.apply(self._value)
                
                # 결과가 있으면 위반 사항으로 처리
                if result is not None:
                    violation = self._create_violation_from_result(rule, result)
                    if violation:
                        violations.append(violation)
                        
            except Exception as e:
                # 규칙 적용 중 오류 발생 시 에러 위반 사항 생성
                error_violation = ViolationInfo(
                    rule_name=getattr(rule, 'name', str(rule)),
                    message=f"규칙 적용 중 오류 발생: {str(e)}",
                    risk_level="high",  # 시스템 오류는 높은 위험 수준으로
                    context={'error': e, 'rule': rule}
                )
                violations.append(error_violation)
        
        return violations
    
    def collect_results(self, processor: Callable[[Rule, T], R]) -> List[R]:
        """
        각 규칙에 대해 커스텀 처리기를 적용한 결과들을 수집합니다.
        
        Args:
            processor: 규칙과 데이터로부터 결과를 생성하는 함수
            
        Returns:
            처리 결과들의 리스트
        """
        results = []
        
        for rule in self.rules:
            try:
                result = processor(rule, self._value)
                results.append(result)
            except Exception as e:
                # 처리기에서 오류 발생 시 None이나 에러 정보 추가
                error_info = ErrorInfo(
                    message=f"처리기 실행 실패: {str(e)}",
                    error_type="processor_error",
                    context={'rule': rule, 'error': e}
                )
                results.append(error_info)
        
        return results
    
    def first_violation(self) -> Optional[ViolationInfo]:
        """
        첫 번째 위반 사항을 반환합니다.
        
        Returns:
            첫 번째 위반 사항, 없으면 None
        """
        violations = self.collect_violations()
        return violations[0] if violations else None
    
    def has_violations(self) -> bool:
        """
        위반 사항이 있는지 확인합니다.
        
        Returns:
            위반 사항이 있으면 True, 없으면 False
        """
        return len(self.collect_violations()) > 0
    
    def count_violations(self) -> int:
        """
        위반 사항의 개수를 반환합니다.
        
        Returns:
            위반 사항 개수
        """
        return len(self.collect_violations())
    
    def violations_by_risk(self) -> dict:
        """
        위험 수준별로 위반 사항들을 그룹화합니다.
        
        Returns:
            위험 수준을 키로 하는 위반 사항 그룹 딕셔너리
        """
        violations = self.collect_violations()
        grouped = {}
        
        for violation in violations:
            risk_level = violation.risk_level
            if risk_level not in grouped:
                grouped[risk_level] = []
            grouped[risk_level].append(violation)
        
        return grouped
    
    def critical_violations(self) -> List[ViolationInfo]:
        """
        중요한 위반 사항들만 반환합니다.
        
        Returns:
            critical 및 high 위험 수준의 위반 사항들
        """
        violations = self.collect_violations()
        return [v for v in violations if v.risk_level in ["critical", "high"]]
    
    def to_chainable_result(self) -> ChainableResult[List[ViolationInfo]]:
        """
        위반 사항 수집 결과를 ChainableResult로 변환합니다.
        
        Returns:
            위반 사항 리스트를 담은 ChainableResult
        """
        try:
            violations = self.collect_violations()
            return success(violations)
        except Exception as e:
            return failure(f"위반 사항 수집 실패: {str(e)}")
    
    def _create_violation_from_result(self, rule: Rule, result: Any) -> Optional[ViolationInfo]:
        """
        규칙 적용 결과로부터 ViolationInfo를 생성합니다.
        
        Args:
            rule: 적용된 규칙
            result: 규칙 적용 결과
            
        Returns:
            생성된 ViolationInfo 또는 None
        """
        if result is None:
            return None
        
        # 결과가 이미 ViolationInfo인 경우
        if isinstance(result, ViolationInfo):
            return result
        
        # 결과가 딕셔너리인 경우
        if isinstance(result, dict):
            return ViolationInfo(
                rule_name=result.get('rule_name', rule.name),
                message=result.get('message', str(result)),
                risk_level=result.get('risk_level', 'medium'),
                position=result.get('position'),
                matched_text=result.get('matched_text'),
                context=result.get('context')
            )
        
        # 결과가 문자열인 경우 (간단한 에러 메시지)
        if isinstance(result, str):
            return ViolationInfo(
                rule_name=rule.name,
                message=result,
                risk_level='medium'
            )
        
        # 기타 경우 (객체를 문자열로 변환)
        return ViolationInfo(
            rule_name=rule.name,
            message=str(result),
            risk_level='medium',
            context={'original_result': result}
        )

def apply_rules_to(target: T) -> RuleApplication[T]:
    """
    규칙을 대상에 적용하기 위한 시작점입니다.
    
    이 함수는 readable HOF의 핵심 진입점 중 하나로,
    자연스러운 체이닝을 통해 규칙을 적용할 수 있게 합니다.
    
    Args:
        target: 규칙을 적용할 대상 데이터
        
    Returns:
        RuleApplication 인스턴스
        
    Example:
        >>> violations = apply_rules_to(text).using(security_rules).collect_violations()
        >>> critical_issues = apply_rules_to(config).using(validation_rules).critical_violations()
    """
    return RuleApplication(target)

# 편의 함수들
def apply_single_rule(target: T, rule: Rule) -> List[ViolationInfo]:
    """
    단일 규칙을 적용하여 위반 사항을 반환합니다.
    
    Args:
        target: 규칙을 적용할 대상
        rule: 적용할 규칙
        
    Returns:
        위반 사항 리스트
    """
    return apply_rules_to(target).with_rule(rule).collect_violations()

def check_violations(target: T, rules: List[Rule]) -> bool:
    """
    위반 사항이 있는지만 간단히 확인합니다.
    
    Args:
        target: 확인할 대상
        rules: 적용할 규칙들
        
    Returns:
        위반 사항이 있으면 True
    """
    return apply_rules_to(target).using(rules).has_violations()

def count_violations(target: T, rules: List[Rule]) -> int:
    """
    위반 사항의 개수를 반환합니다.
    
    Args:
        target: 확인할 대상  
        rules: 적용할 규칙들
        
    Returns:
        위반 사항 개수
    """
    return apply_rules_to(target).using(rules).count_violations()