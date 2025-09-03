"""
RFS Readable HOF Validation DSL

검증 규칙 DSL(Domain Specific Language)을 구현합니다.
자연어에 가까운 방식으로 설정이나 데이터의 검증 규칙을 정의하고 적용할 수 있습니다.

사용 예:
    result = validate_config(config).against_rules([
        required("api_key", "API 키가 필요합니다"),
        range_check("timeout", 1, 300, "타임아웃은 1-300초 사이여야 합니다")
    ])
"""

import re
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Pattern, Union

from .base import FluentBase, ChainableResult, success, failure
from .types import Validator

@dataclass
class ValidationRule:
    """
    검증 규칙을 정의하는 데이터 클래스
    
    각 규칙은 필드명, 검증 함수, 에러 메시지, 설명을 가집니다.
    """
    field_name: str
    validator: Callable[[Any], bool]
    error_message: str
    description: Optional[str] = None
    
    def apply(self, target: Any) -> Optional[str]:
        """
        규칙을 대상에 적용하여 오류 메시지를 반환합니다.
        
        Args:
            target: 검증할 대상 객체
            
        Returns:
            검증 실패 시 에러 메시지, 성공 시 None
        """
        try:
            if not self.validator(target):
                return self.error_message
            return None
        except Exception as e:
            return f"{self.error_message} (검증 중 오류 발생: {str(e)})"
    
    def __str__(self) -> str:
        return f"ValidationRule({self.field_name}: {self.description or self.error_message})"

class ConfigValidator(FluentBase[Any]):
    """
    설정 검증을 위한 플루언트 인터페이스
    
    설정 객체에 대해 여러 규칙을 연속으로 적용하고
    결과를 ChainableResult로 반환합니다.
    """
    
    def against_rules(self, rules: List[Optional[ValidationRule]]) -> ChainableResult[Any]:
        """
        여러 규칙들에 대해 검증을 수행합니다.
        
        Args:
            rules: 적용할 검증 규칙들 (None 규칙은 자동으로 건너뜀)
            
        Returns:
            검증 결과를 담은 ChainableResult
        """
        # None 규칙들을 필터링
        valid_rules = [rule for rule in rules if rule is not None]
        
        if not valid_rules:
            return success(self._value)
        
        for rule in valid_rules:
            error = rule.apply(self._value)
            if error:
                return failure(error)
        
        return success(self._value)
    
    def with_rule(self, rule: ValidationRule) -> ChainableResult[Any]:
        """
        단일 규칙으로 검증을 수행합니다.
        
        Args:
            rule: 적용할 검증 규칙
            
        Returns:
            검증 결과를 담은 ChainableResult
        """
        try:
            error = rule.apply(self._value)
            if error:
                return failure(error)
            return success(self._value)
        except Exception as e:
            return failure(f"규칙 적용 실패: {str(e)}")
    
    def check_all_rules(self, rules: List[ValidationRule]) -> List[str]:
        """
        모든 규칙을 확인하고 모든 오류 메시지를 반환합니다.
        (첫 번째 실패에서 중단하지 않음)
        
        Args:
            rules: 확인할 모든 규칙들
            
        Returns:
            모든 오류 메시지 리스트
        """
        errors = []
        
        for rule in rules:
            if rule is None:
                continue
                
            error = rule.apply(self._value)
            if error:
                errors.append(error)
        
        return errors
    
    def validate_required_fields(self, required_fields: List[str]) -> ChainableResult[Any]:
        """
        필수 필드들을 일괄 검증합니다.
        
        Args:
            required_fields: 필수 필드명 리스트
            
        Returns:
            검증 결과를 담은 ChainableResult
        """
        rules = [
            required(field, f"{field} 필드가 필요합니다") 
            for field in required_fields
        ]
        return self.against_rules(rules)

# 규칙 생성 함수들

def required(field_name: str, error_message: str) -> ValidationRule:
    """
    필수 필드 검증 규칙을 생성합니다.
    
    Args:
        field_name: 검증할 필드명
        error_message: 실패 시 표시할 메시지
        
    Returns:
        필수 필드 검증 규칙
    """
    def validator(obj):
        value = getattr(obj, field_name, None)
        if value is None:
            return False
        # 문자열인 경우 공백 문자열도 실패로 처리
        if isinstance(value, str) and not value.strip():
            return False
        # 컬렉션인 경우 빈 컬렉션도 실패로 처리
        if hasattr(value, '__len__') and len(value) == 0:
            return False
        return True
    
    return ValidationRule(
        field_name=field_name,
        validator=validator,
        error_message=error_message,
        description=f"{field_name} 필드 필수 값 검증"
    )

def range_check(field_name: str, min_val: Union[int, float], max_val: Union[int, float], error_message: str) -> ValidationRule:
    """
    숫자 범위 검증 규칙을 생성합니다.
    
    Args:
        field_name: 검증할 필드명
        min_val: 최소값 (포함)
        max_val: 최대값 (포함)
        error_message: 실패 시 표시할 메시지
        
    Returns:
        범위 검증 규칙
    """
    def validator(obj):
        value = getattr(obj, field_name, None)
        if value is None:
            return True  # None은 범위 검사에서 제외 (required와 별도로 체크)
        
        try:
            # 숫자로 변환 시도
            num_value = float(value) if not isinstance(value, (int, float)) else value
            return min_val <= num_value <= max_val
        except (ValueError, TypeError):
            return False  # 숫자로 변환할 수 없으면 실패
    
    return ValidationRule(
        field_name=field_name,
        validator=validator,
        error_message=error_message,
        description=f"{field_name} 값 범위 검증 ({min_val}-{max_val})"
    )

def format_check(field_name: str, pattern: Union[Pattern, str], error_message: str) -> ValidationRule:
    """
    문자열 형식 검증 규칙을 생성합니다.
    
    Args:
        field_name: 검증할 필드명
        pattern: 검증에 사용할 정규표현식 (Pattern 객체 또는 문자열)
        error_message: 실패 시 표시할 메시지
        
    Returns:
        형식 검증 규칙
    """
    # 문자열인 경우 Pattern 객체로 변환
    if isinstance(pattern, str):
        regex_pattern = re.compile(pattern)
    else:
        regex_pattern = pattern
    
    def validator(obj):
        value = getattr(obj, field_name, None)
        if value is None:
            return True  # None은 형식 검사에서 제외
        
        try:
            str_value = str(value)
            return bool(regex_pattern.match(str_value))
        except Exception:
            return False
    
    return ValidationRule(
        field_name=field_name,
        validator=validator,
        error_message=error_message,
        description=f"{field_name} 형식 검증"
    )

def custom_check(field_name: str, validator_func: Callable[[Any], bool], error_message: str, description: Optional[str] = None) -> ValidationRule:
    """
    커스텀 검증 규칙을 생성합니다.
    
    Args:
        field_name: 검증할 필드명
        validator_func: 검증 함수 (필드 값을 받아 bool 반환)
        error_message: 실패 시 표시할 메시지
        description: 규칙에 대한 설명
        
    Returns:
        커스텀 검증 규칙
    """
    def validator(obj):
        value = getattr(obj, field_name, None)
        try:
            return validator_func(value)
        except Exception:
            return False
    
    return ValidationRule(
        field_name=field_name,
        validator=validator,
        error_message=error_message,
        description=description or f"{field_name} 커스텀 검증"
    )

def length_check(field_name: str, min_length: Optional[int] = None, max_length: Optional[int] = None, error_message: Optional[str] = None) -> ValidationRule:
    """
    문자열이나 컬렉션의 길이를 검증하는 규칙을 생성합니다.
    
    Args:
        field_name: 검증할 필드명
        min_length: 최소 길이 (None이면 검사하지 않음)
        max_length: 최대 길이 (None이면 검사하지 않음)
        error_message: 커스텀 에러 메시지
        
    Returns:
        길이 검증 규칙
    """
    if error_message is None:
        if min_length is not None and max_length is not None:
            error_message = f"{field_name}의 길이는 {min_length}-{max_length} 사이여야 합니다"
        elif min_length is not None:
            error_message = f"{field_name}의 길이는 최소 {min_length}이어야 합니다"
        elif max_length is not None:
            error_message = f"{field_name}의 길이는 최대 {max_length}이어야 합니다"
        else:
            error_message = f"{field_name}의 길이가 유효하지 않습니다"
    
    def validator(obj):
        value = getattr(obj, field_name, None)
        if value is None:
            return True  # None은 길이 검사에서 제외
        
        try:
            length = len(value)
            if min_length is not None and length < min_length:
                return False
            if max_length is not None and length > max_length:
                return False
            return True
        except TypeError:
            return False  # len()을 적용할 수 없는 객체
    
    return ValidationRule(
        field_name=field_name,
        validator=validator,
        error_message=error_message,
        description=f"{field_name} 길이 검증"
    )

def email_check(field_name: str, error_message: Optional[str] = None) -> ValidationRule:
    """
    이메일 형식 검증 규칙을 생성합니다.
    
    Args:
        field_name: 검증할 필드명
        error_message: 커스텀 에러 메시지
        
    Returns:
        이메일 형식 검증 규칙
    """
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    return format_check(
        field_name=field_name,
        pattern=email_pattern,
        error_message=error_message or f"{field_name}이 유효한 이메일 형식이 아닙니다"
    )

def url_check(field_name: str, error_message: Optional[str] = None) -> ValidationRule:
    """
    URL 형식 검증 규칙을 생성합니다.
    
    Args:
        field_name: 검증할 필드명
        error_message: 커스텀 에러 메시지
        
    Returns:
        URL 형식 검증 규칙
    """
    url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    
    return format_check(
        field_name=field_name,
        pattern=url_pattern,
        error_message=error_message or f"{field_name}이 유효한 URL 형식이 아닙니다"
    )

def validate_config(config_obj: Any) -> ConfigValidator:
    """
    설정 객체 검증을 위한 시작점입니다.
    
    이 함수는 validation DSL의 핵심 진입점으로,
    자연스러운 체이닝을 통해 검증 규칙을 적용할 수 있게 합니다.
    
    Args:
        config_obj: 검증할 설정 객체
        
    Returns:
        ConfigValidator 인스턴스
        
    Example:
        >>> result = validate_config(config).against_rules([
        ...     required("api_key", "API 키가 필요합니다"),
        ...     range_check("timeout", 1, 300, "타임아웃은 1-300초 사이여야 합니다")
        ... ])
    """
    return ConfigValidator(config_obj)

# 편의 함수들
def validate_fields(obj: Any, rules: List[ValidationRule]) -> List[str]:
    """
    객체의 필드들을 검증하고 모든 오류 메시지를 반환합니다.
    
    Args:
        obj: 검증할 객체
        rules: 적용할 검증 규칙들
        
    Returns:
        모든 오류 메시지 리스트
    """
    return ConfigValidator(obj).check_all_rules(rules)

def conditional(condition: Callable[[Any], bool], rule: ValidationRule) -> Optional[ValidationRule]:
    """
    조건부 검증 규칙을 생성합니다.
    
    조건이 True일 때만 해당 규칙을 적용하고, False일 때는 규칙을 건너뜁니다.
    
    Args:
        condition: 조건을 확인하는 함수
        rule: 조건부로 적용할 검증 규칙
        
    Returns:
        조건부 검증 규칙 또는 None
        
    Example:
        >>> ssl_cert_rule = conditional(
        ...     lambda config: config.ssl_enabled,
        ...     required("ssl_cert_path", "SSL 사용 시 인증서 경로가 필요합니다")
        ... )
    """
    def conditional_validator(obj):
        # 조건을 먼저 확인
        try:
            if not condition(obj):
                return True  # 조건이 맞지 않으면 통과
            # 조건이 맞으면 원래 검증자 실행
            return rule.validator(obj)
        except Exception:
            # 조건 확인 중 오류가 발생하면 검증 실패
            return False
    
    return ValidationRule(
        field_name=rule.field_name,
        validator=conditional_validator,
        error_message=rule.error_message,
        description=rule.description
    )

def is_valid(obj: Any, rules: List[ValidationRule]) -> bool:
    """
    객체가 모든 검증 규칙을 통과하는지 확인합니다.
    
    Args:
        obj: 검증할 객체
        rules: 적용할 검증 규칙들
        
    Returns:
        모든 규칙을 통과하면 True
    """
    return validate_config(obj).against_rules(rules).is_success()