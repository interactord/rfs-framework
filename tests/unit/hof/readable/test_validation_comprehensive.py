"""
RFS Readable HOF Validation Module - Comprehensive Tests

이 모듈은 validation DSL의 모든 기능을 포괄적으로 테스트합니다.
제안서의 모든 예제와 추가적인 엣지 케이스들을 검증합니다.
"""

import re
import pytest
from dataclasses import dataclass
from typing import Optional

from rfs.hof.readable.validation import (
    ValidationRule, ConfigValidator, validate_config,
    required, range_check, format_check, length_check, 
    email_check, url_check, custom_check
)
from rfs.hof.readable.base import success, failure


class TestValidationRule:
    """ValidationRule 클래스의 단위 테스트"""

    def test_rule_creation(self):
        """기본 규칙 생성 테스트"""
        rule = ValidationRule(
            field_name="test_field",
            validator=lambda obj: getattr(obj, "test_field", None) is not None,
            error_message="Test field is required"
        )
        
        assert rule.field_name == "test_field"
        assert rule.error_message == "Test field is required"
        assert callable(rule.validator)

    def test_rule_apply_success(self):
        """규칙 적용 성공 테스트"""
        @dataclass
        class TestObj:
            value: str = "test"
        
        rule = ValidationRule(
            field_name="value",
            validator=lambda obj: obj.value == "test",
            error_message="Value must be 'test'"
        )
        
        obj = TestObj()
        result = rule.apply(obj)
        assert result is None  # 성공 시 None 반환

    def test_rule_apply_failure(self):
        """규칙 적용 실패 테스트"""
        @dataclass
        class TestObj:
            value: str = "wrong"
        
        rule = ValidationRule(
            field_name="value",
            validator=lambda obj: obj.value == "test",
            error_message="Value must be 'test'"
        )
        
        obj = TestObj()
        result = rule.apply(obj)
        assert result == "Value must be 'test'"

    def test_rule_apply_with_exception(self):
        """규칙 적용 중 예외 발생 테스트"""
        def failing_validator(obj):
            raise ValueError("Validation error")
        
        rule = ValidationRule(
            field_name="test",
            validator=failing_validator,
            error_message="Custom error"
        )
        
        result = rule.apply(object())
        assert "Custom error" in result
        assert "검증 중 오류 발생" in result


class TestConfigValidator:
    """ConfigValidator 클래스의 단위 테스트"""

    @dataclass
    class TestConfig:
        name: Optional[str] = None
        port: int = 8080
        enabled: bool = True

    def test_empty_rules(self):
        """빈 규칙 리스트 테스트"""
        config = self.TestConfig(name="test")
        validator = ConfigValidator(config)
        
        result = validator.against_rules([])
        assert result.is_success()
        assert result.unwrap() == config

    def test_none_rules_filtered(self):
        """None 규칙들이 필터링되는지 테스트"""
        config = self.TestConfig(name="test")
        validator = ConfigValidator(config)
        
        # None 규칙들을 포함하여 테스트
        result = validator.against_rules([
            required("name", "Name required"),
            None,  # 이 규칙은 필터링되어야 함
            None
        ])
        
        assert result.is_success()

    def test_single_rule_success(self):
        """단일 규칙 성공 테스트"""
        config = self.TestConfig(name="valid_name")
        result = validate_config(config).against_rules([
            required("name", "Name is required")
        ])
        
        assert result.is_success()
        assert result.unwrap() == config

    def test_single_rule_failure(self):
        """단일 규칙 실패 테스트"""
        config = self.TestConfig(name=None)
        result = validate_config(config).against_rules([
            required("name", "Name is required")
        ])
        
        assert result.is_failure()
        assert result.unwrap_error() == "Name is required"

    def test_multiple_rules_success(self):
        """여러 규칙 모두 성공 테스트"""
        config = self.TestConfig(name="test", port=8080, enabled=True)
        result = validate_config(config).against_rules([
            required("name", "Name is required"),
            range_check("port", 1, 65535, "Port must be 1-65535")
        ])
        
        assert result.is_success()

    def test_multiple_rules_first_failure(self):
        """여러 규칙 중 첫 번째에서 실패 테스트"""
        config = self.TestConfig(name=None, port=8080)
        result = validate_config(config).against_rules([
            required("name", "Name is required"),  # 이 규칙에서 실패
            range_check("port", 1, 65535, "Port must be 1-65535")
        ])
        
        assert result.is_failure()
        assert result.unwrap_error() == "Name is required"

    def test_multiple_rules_second_failure(self):
        """여러 규칙 중 두 번째에서 실패 테스트"""
        config = self.TestConfig(name="test", port=100000)
        result = validate_config(config).against_rules([
            required("name", "Name is required"),
            range_check("port", 1, 65535, "Port must be 1-65535")  # 이 규칙에서 실패
        ])
        
        assert result.is_failure()
        assert result.unwrap_error() == "Port must be 1-65535"

    def test_with_rule_single(self):
        """with_rule 메서드 테스트"""
        config = self.TestConfig(name="test")
        validator = ConfigValidator(config)
        
        result = validator.with_rule(required("name", "Name required"))
        assert result.is_success()

    def test_collect_all_errors_success(self):
        """모든 에러 수집 - 성공 케이스"""
        config = self.TestConfig(name="test", port=8080)
        validator = ConfigValidator(config)
        
        result = validator.collect_all_errors([
            required("name", "Name is required"),
            range_check("port", 1, 65535, "Port must be 1-65535")
        ])
        
        assert result.is_success()

    def test_collect_all_errors_multiple_failures(self):
        """모든 에러 수집 - 여러 실패"""
        config = self.TestConfig(name=None, port=100000)
        validator = ConfigValidator(config)
        
        result = validator.collect_all_errors([
            required("name", "Name is required"),
            range_check("port", 1, 65535, "Port must be 1-65535")
        ])
        
        assert result.is_failure()
        errors = result.unwrap_error()
        assert len(errors) == 2
        assert "Name is required" in errors
        assert "Port must be 1-65535" in errors


class TestValidationRuleFunctions:
    """검증 규칙 생성 함수들 테스트"""

    @dataclass
    class TestObj:
        name: Optional[str] = None
        count: int = 0
        email: str = ""
        url: str = ""
        text: str = ""

    def test_required_rule(self):
        """required 규칙 테스트"""
        rule = required("name", "Name is required")
        
        # 성공 케이스
        obj_with_name = self.TestObj(name="test")
        assert rule.apply(obj_with_name) is None
        
        # 실패 케이스
        obj_without_name = self.TestObj(name=None)
        assert rule.apply(obj_without_name) == "Name is required"

    def test_range_check_rule(self):
        """range_check 규칙 테스트"""
        rule = range_check("count", 1, 10, "Count must be 1-10")
        
        # 성공 케이스들
        assert rule.apply(self.TestObj(count=5)) is None
        assert rule.apply(self.TestObj(count=1)) is None  # 경계값
        assert rule.apply(self.TestObj(count=10)) is None  # 경계값
        
        # 실패 케이스들
        assert rule.apply(self.TestObj(count=0)) == "Count must be 1-10"
        assert rule.apply(self.TestObj(count=11)) == "Count must be 1-10"

    def test_format_check_rule(self):
        """format_check 규칙 테스트"""
        # 이메일 패턴
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        rule = format_check("email", email_pattern, "Invalid email format")
        
        # 성공 케이스
        assert rule.apply(self.TestObj(email="test@example.com")) is None
        
        # 실패 케이스
        assert rule.apply(self.TestObj(email="invalid-email")) == "Invalid email format"

    def test_length_check_rule(self):
        """length_check 규칙 테스트"""
        rule = length_check("text", 3, 10, "Text must be 3-10 characters")
        
        # 성공 케이스들
        assert rule.apply(self.TestObj(text="test")) is None
        assert rule.apply(self.TestObj(text="abc")) is None  # 최소 길이
        assert rule.apply(self.TestObj(text="1234567890")) is None  # 최대 길이
        
        # 실패 케이스들
        assert rule.apply(self.TestObj(text="ab")) == "Text must be 3-10 characters"
        assert rule.apply(self.TestObj(text="12345678901")) == "Text must be 3-10 characters"

    def test_email_check_rule(self):
        """email_check 규칙 테스트"""
        rule = email_check("email")
        
        # 성공 케이스들
        valid_emails = [
            "user@example.com",
            "test.email@domain.org",
            "user+tag@example.co.uk"
        ]
        
        for email in valid_emails:
            assert rule.apply(self.TestObj(email=email)) is None, f"Failed for valid email: {email}"
        
        # 실패 케이스들
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "user@",
            "user.example.com"
        ]
        
        for email in invalid_emails:
            result = rule.apply(self.TestObj(email=email))
            assert result is not None, f"Should have failed for invalid email: {email}"
            assert "이메일" in result

    def test_url_check_rule(self):
        """url_check 규칙 테스트"""
        rule = url_check("url")
        
        # 성공 케이스들
        valid_urls = [
            "https://example.com",
            "http://www.example.com",
            "https://example.com/path?query=value"
        ]
        
        for url in valid_urls:
            assert rule.apply(self.TestObj(url=url)) is None, f"Failed for valid URL: {url}"
        
        # 실패 케이스들
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",  # 지원되지 않는 프로토콜
            "example.com"  # 프로토콜 없음
        ]
        
        for url in invalid_urls:
            result = rule.apply(self.TestObj(url=url))
            assert result is not None, f"Should have failed for invalid URL: {url}"
            assert "URL" in result

    def test_custom_check_rule(self):
        """custom_check 규칙 테스트"""
        def is_even(obj):
            return obj.count % 2 == 0
        
        rule = custom_check("count", is_even, "Count must be even")
        
        # 성공 케이스
        assert rule.apply(self.TestObj(count=4)) is None
        
        # 실패 케이스
        assert rule.apply(self.TestObj(count=5)) == "Count must be even"

    def test_custom_check_with_exception(self):
        """custom_check에서 예외 발생 테스트"""
        def failing_check(obj):
            raise ValueError("Custom validation error")
        
        rule = custom_check("test", failing_check, "Custom check failed")
        
        result = rule.apply(self.TestObj())
        assert "Custom check failed" in result
        assert "검증 중 오류" in result


class TestProposalExamples:
    """제안서의 구체적인 예제들 테스트"""

    def test_database_config_example(self):
        """제안서의 DatabaseConfig 예제 테스트"""
        @dataclass
        class DatabaseConfig:
            host: Optional[str] = None
            port: int = 5432
            username: Optional[str] = None
            password: Optional[str] = None
            ssl_enabled: bool = False
            ssl_cert_path: Optional[str] = None
        
        # 성공 케이스
        valid_config = DatabaseConfig(
            host="localhost",
            port=5432,
            username="user",
            password="secret"
        )
        
        result = validate_config(valid_config).against_rules([
            required("host", "데이터베이스 호스트가 필요합니다"),
            required("username", "사용자명이 필요합니다"),
            required("password", "비밀번호가 필요합니다"),
            range_check("port", 1, 65535, "포트는 1-65535 사이여야 합니다"),
            format_check("host", re.compile(r'^[\w\.-]+$'), "유효하지 않은 호스트명 형식")
        ])
        
        assert result.is_success()
        
        # 실패 케이스
        invalid_config = DatabaseConfig(
            host=None,
            username="user",
            password="secret"
        )
        
        result = validate_config(invalid_config).against_rules([
            required("host", "데이터베이스 호스트가 필요합니다"),
            required("username", "사용자명이 필요합니다"),
            required("password", "비밀번호가 필요합니다")
        ])
        
        assert result.is_failure()
        assert "호스트가 필요합니다" in result.unwrap_error()

    def test_conditional_validation_pattern(self):
        """조건부 검증 패턴 테스트"""
        @dataclass
        class ServiceConfig:
            cache_enabled: bool = False
            redis_url: Optional[str] = None
            ssl_enabled: bool = False
            ssl_cert_path: Optional[str] = None
        
        # 조건부 규칙 구현 (conditional 함수가 없으므로 직접 구현)
        def conditional_rule(condition_func, rule):
            """조건부 규칙 헬퍼"""
            def conditional_validator(obj):
                if not condition_func(obj):
                    return True  # 조건이 맞지 않으면 통과
                return rule.validator(obj)
            
            return ValidationRule(
                field_name=rule.field_name,
                validator=conditional_validator,
                error_message=rule.error_message
            )
        
        # 캐시가 활성화된 경우
        cache_enabled_config = ServiceConfig(
            cache_enabled=True,
            redis_url="redis://localhost:6379"
        )
        
        redis_required_if_cache = conditional_rule(
            lambda config: config.cache_enabled,
            required("redis_url", "캐시 사용 시 Redis URL이 필요합니다")
        )
        
        result = validate_config(cache_enabled_config).against_rules([
            redis_required_if_cache
        ])
        
        assert result.is_success()
        
        # 캐시가 활성화되었지만 Redis URL이 없는 경우
        invalid_cache_config = ServiceConfig(
            cache_enabled=True,
            redis_url=None
        )
        
        result = validate_config(invalid_cache_config).against_rules([
            redis_required_if_cache
        ])
        
        assert result.is_failure()
        assert "Redis URL이 필요합니다" in result.unwrap_error()
        
        # 캐시가 비활성화된 경우 (Redis URL 없어도 통과해야 함)
        cache_disabled_config = ServiceConfig(
            cache_enabled=False,
            redis_url=None
        )
        
        result = validate_config(cache_disabled_config).against_rules([
            redis_required_if_cache
        ])
        
        assert result.is_success()


class TestEdgeCases:
    """엣지 케이스 및 에러 상황 테스트"""

    def test_missing_field(self):
        """존재하지 않는 필드에 대한 검증"""
        class EmptyObj:
            pass
        
        obj = EmptyObj()
        rule = required("nonexistent_field", "Field required")
        
        result = rule.apply(obj)
        assert result == "Field required"

    def test_none_object(self):
        """None 객체에 대한 검증"""
        rule = required("field", "Field required")
        
        # None 객체에 대해서도 안전하게 처리되어야 함
        result = rule.apply(None)
        assert result == "Field required"

    def test_complex_object_validation(self):
        """복잡한 객체 구조 검증"""
        @dataclass
        class NestedConfig:
            db_host: str = "localhost"
            db_port: int = 5432
        
        @dataclass
        class AppConfig:
            app_name: str = "test_app"
            database: NestedConfig = None
        
        # 중첩 객체 검증을 위한 커스텀 규칙
        def nested_required(field_path, error_message):
            def validator(obj):
                parts = field_path.split('.')
                current = obj
                for part in parts:
                    current = getattr(current, part, None)
                    if current is None:
                        return False
                return True
            
            return ValidationRule(
                field_name=field_path,
                validator=validator,
                error_message=error_message
            )
        
        config = AppConfig(
            app_name="test",
            database=NestedConfig(db_host="localhost", db_port=5432)
        )
        
        result = validate_config(config).against_rules([
            required("app_name", "App name required"),
            nested_required("database.db_host", "Database host required"),
            nested_required("database.db_port", "Database port required")
        ])
        
        assert result.is_success()

    def test_performance_with_many_rules(self):
        """많은 규칙에 대한 성능 테스트"""
        @dataclass
        class TestObj:
            field1: str = "value1"
            field2: str = "value2"
            field3: int = 42
        
        # 많은 규칙 생성
        rules = []
        for i in range(100):
            rules.append(required(f"field1", f"Field1 required {i}"))
            rules.append(required(f"field2", f"Field2 required {i}"))
            rules.append(range_check(f"field3", 0, 100, f"Field3 range error {i}"))
        
        obj = TestObj()
        
        import time
        start_time = time.time()
        result = validate_config(obj).against_rules(rules)
        duration = time.time() - start_time
        
        assert result.is_success()
        assert duration < 1.0  # 1초 내에 완료되어야 함


if __name__ == "__main__":
    pytest.main([__file__, "-v"])