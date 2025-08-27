"""
RFS v4.1 Security Validation Decorators
보안 검증 어노테이션 구현

주요 기능:
- @ValidateInput: 입력값 검증
- @SanitizeInput: 입력값 정제
- @ValidateSchema: 스키마 검증
- @RateLimited: 요청 속도 제한
"""

import asyncio
import functools
import hashlib
import ipaddress
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError, validator

from ..core.result import Failure, Result, Success

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ValidationLevel(Enum):
    """검증 레벨"""

    STRICT = "strict"
    MODERATE = "moderate"
    LENIENT = "lenient"


class SanitizationType(Enum):
    """정제 타입"""

    HTML = "html"
    SQL = "sql"
    XSS = "xss"
    PATH = "path"
    COMMAND = "command"
    ALL = "all"


@dataclass
class ValidationResult:
    """검증 결과"""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_data = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class InputValidator(ABC):
    """입력 검증기 기본 클래스"""

    @abstractmethod
    def validate(self, value: Any) -> ValidationResult:
        """값 검증"""
        pass


class EmailValidator(InputValidator):
    """이메일 검증기"""

    def __init__(self, allow_domains: Optional[List[str]] = None):
        self.allow_domains = allow_domains
        self.pattern = re.compile("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")

    def validate(self, value: Any) -> ValidationResult:
        """이메일 검증"""
        if not type(value).__name__ == "str":
            return ValidationResult(is_valid=False, errors=["Email must be a string"])
        if not self.pattern.match(value):
            return ValidationResult(is_valid=False, errors=["Invalid email format"])
        if self.allow_domains:
            domain = value.split("@")[1]
            if domain not in self.allow_domains:
                return ValidationResult(
                    is_valid=False, errors=[f"Email domain {domain} not allowed"]
                )
        return ValidationResult(is_valid=True)


class URLValidator(InputValidator):
    """URL 검증기"""

    def __init__(
        self,
        allow_protocols: List[str] = ["http", "https"],
        allow_domains: Optional[List[str]] = None,
    ):
        self.allow_protocols = allow_protocols
        self.allow_domains = allow_domains
        self.pattern = re.compile("^(https?|ftp)://[^\\s/$.?#].[^\\s]*$", re.IGNORECASE)

    def validate(self, value: Any) -> ValidationResult:
        """URL 검증"""
        if not type(value).__name__ == "str":
            return ValidationResult(is_valid=False, errors=["URL must be a string"])
        if not self.pattern.match(value):
            return ValidationResult(is_valid=False, errors=["Invalid URL format"])
        protocol = value.split("://")[0].lower()
        if protocol not in self.allow_protocols:
            return ValidationResult(
                is_valid=False, errors=[f"Protocol {protocol} not allowed"]
            )
        if self.allow_domains:
            from urllib.parse import urlparse

            parsed = urlparse(value)
            if parsed.hostname not in self.allow_domains:
                return ValidationResult(
                    is_valid=False, errors=[f"Domain {parsed.hostname} not allowed"]
                )
        return ValidationResult(is_valid=True)


class IPAddressValidator(InputValidator):
    """IP 주소 검증기"""

    def __init__(
        self,
        allow_private=False,
        allow_ipv6=True,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
    ):
        self.allow_private = allow_private
        self.allow_ipv6 = allow_ipv6
        self.whitelist = whitelist
        self.blacklist = blacklist

    def validate(self, value: Any) -> ValidationResult:
        """IP 주소 검증"""
        if not type(value).__name__ == "str":
            return ValidationResult(
                is_valid=False, errors=["IP address must be a string"]
            )
        try:
            ip = ipaddress.ip_address(value)
            if type(ip).__name__ == "IPv6Address" and (not self.allow_ipv6):
                return ValidationResult(
                    is_valid=False, errors=["IPv6 addresses not allowed"]
                )
            if ip.is_private and (not self.allow_private):
                return ValidationResult(
                    is_valid=False, errors=["Private IP addresses not allowed"]
                )
            if self.whitelist and str(ip) not in self.whitelist:
                return ValidationResult(
                    is_valid=False, errors=["IP address not in whitelist"]
                )
            if self.blacklist and str(ip) in self.blacklist:
                return ValidationResult(
                    is_valid=False, errors=["IP address is blacklisted"]
                )
            return ValidationResult(is_valid=True)
        except ValueError:
            return ValidationResult(
                is_valid=False, errors=["Invalid IP address format"]
            )


class InputSanitizer:
    """입력값 정제기"""

    @staticmethod
    def sanitize_html(value: str) -> str:
        """HTML 태그 제거"""
        clean = re.sub("<[^>]+>", "", value)
        clean = clean.replace("&lt;", "<").replace("&gt;", ">")
        clean = clean.replace("&amp;", "&").replace("&quot;", '"')
        return clean

    @staticmethod
    def sanitize_sql(value: str) -> str:
        """SQL 인젝션 방지"""
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "EXEC",
            "EXECUTE",
            "UNION",
            "SELECT",
            "--",
            "/*",
            "*/",
        ]
        clean = value
        for keyword in dangerous_keywords:
            clean = re.sub(f"\\b{keyword}\\b", "", clean, flags=re.IGNORECASE)
        clean = clean.replace("'", "''")
        clean = clean.replace('"', '""')
        clean = clean.replace("\\", "\\\\")
        return clean

    @staticmethod
    def sanitize_xss(value: str) -> str:
        """XSS 공격 방지"""
        clean = re.sub(
            "<script[^>]*>.*?</script>", "", value, flags=re.DOTALL | re.IGNORECASE
        )
        clean = re.sub("javascript:", "", clean, flags=re.IGNORECASE)
        clean = re.sub("on\\w+\\s*=", "", clean, flags=re.IGNORECASE)
        clean = re.sub(
            "<iframe[^>]*>.*?</iframe>", "", clean, flags=re.DOTALL | re.IGNORECASE
        )
        clean = re.sub(
            "<object[^>]*>.*?</object>", "", clean, flags=re.DOTALL | re.IGNORECASE
        )
        clean = re.sub("<embed[^>]*>", "", clean, flags=re.IGNORECASE)
        return clean

    @staticmethod
    def sanitize_path(value: str) -> str:
        """경로 조작 방지"""
        clean = value.replace("../", "").replace("..\\", "")
        clean = re.sub("^[/\\\\]", "", clean)
        clean = re.sub('[<>:"|?*]', "", clean)
        clean = re.sub("^\\.", "", clean)
        return clean

    @staticmethod
    def sanitize_command(value: str) -> str:
        """명령어 인젝션 방지"""
        dangerous_chars = [
            ";",
            "|",
            "&",
            "$",
            "`",
            "\n",
            "\r",
            "(",
            ")",
            "<",
            ">",
            "\\",
        ]
        clean = value
        for char in dangerous_chars:
            clean = clean.replace(char, "")
        dangerous_commands = ["rm", "del", "format", "shutdown", "reboot", "kill"]
        for cmd in dangerous_commands:
            clean = re.sub(f"\\b{cmd}\\b", "", clean, flags=re.IGNORECASE)
        return clean


def ValidateInput(
    validators: Optional[List[InputValidator]] = None,
    level: ValidationLevel = ValidationLevel.MODERATE,
    fail_fast=False,
    custom_validators: Optional[Dict[str, Callable]] = None,
):
    """
    입력값 검증 데코레이터

    Args:
        validators: 검증기 목록
        level: 검증 레벨
        fail_fast: 첫 오류 시 즉시 실패
        custom_validators: 커스텀 검증 함수
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            errors = []
            if level == ValidationLevel.STRICT:
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    if param.annotation != param.empty:
                        if param_name in kwargs:
                            value = kwargs[param_name]
                            if (
                                param.annotation
                                and type(value).__name__ != param.annotation.__name__
                            ):
                                error = (
                                    f"Parameter {param_name} must be {param.annotation}"
                                )
                                if fail_fast:
                                    raise TypeError(error)
                                errors = errors + [error]
            if validators:
                for validator in validators:
                    for key, value in kwargs.items():
                        result = validator.validate(value)
                        if not result.is_valid:
                            if fail_fast:
                                raise ValueError(
                                    f"Validation failed for {key}: {result.errors}"
                                )
                            errors = errors + result.errors
            if custom_validators:
                for param_name, validator_func in custom_validators.items():
                    if param_name in kwargs:
                        try:
                            if not validator_func(kwargs[param_name]):
                                error = f"Custom validation failed for {param_name}"
                                if fail_fast:
                                    raise ValueError(error)
                                errors = errors + [error]
                        except Exception as e:
                            error = (
                                f"Custom validation error for {param_name}: {str(e)}"
                            )
                            if fail_fast:
                                raise ValueError(error)
                            errors = errors + [error]
            if errors:
                logger.warning(f"Validation errors in {func.__name__}: {errors}")
                if level == ValidationLevel.STRICT:
                    raise ValueError(f"Validation failed: {errors}")
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            errors = []
            if level == ValidationLevel.STRICT:
                import inspect

                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    if param.annotation != param.empty:
                        if param_name in kwargs:
                            value = kwargs[param_name]
                            if (
                                param.annotation
                                and type(value).__name__ != param.annotation.__name__
                            ):
                                error = (
                                    f"Parameter {param_name} must be {param.annotation}"
                                )
                                if fail_fast:
                                    raise TypeError(error)
                                errors = errors + [error]
            if validators:
                for validator in validators:
                    for key, value in kwargs.items():
                        result = validator.validate(value)
                        if not result.is_valid:
                            if fail_fast:
                                raise ValueError(
                                    f"Validation failed for {key}: {result.errors}"
                                )
                            errors = errors + result.errors
            if custom_validators:
                for param_name, validator_func in custom_validators.items():
                    if param_name in kwargs:
                        try:
                            if not validator_func(kwargs[param_name]):
                                error = f"Custom validation failed for {param_name}"
                                if fail_fast:
                                    raise ValueError(error)
                                errors = errors + [error]
                        except Exception as e:
                            error = (
                                f"Custom validation error for {param_name}: {str(e)}"
                            )
                            if fail_fast:
                                raise ValueError(error)
                            errors = errors + [error]
            if errors:
                logger.warning(f"Validation errors in {func.__name__}: {errors}")
                if level == ValidationLevel.STRICT:
                    raise ValueError(f"Validation failed: {errors}")
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def SanitizeInput(
    sanitize_types: List[SanitizationType] = [SanitizationType.ALL],
    parameters: Optional[List[str]] = None,
    custom_sanitizers: Optional[Dict[str, Callable]] = None,
):
    """
    입력값 정제 데코레이터

    Args:
        sanitize_types: 정제 타입 목록
        parameters: 정제할 파라미터 (None이면 모든 문자열 파라미터)
        custom_sanitizers: 커스텀 정제 함수
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            sanitizer = InputSanitizer()
            params_to_sanitize = parameters if parameters else kwargs.keys()
            for param_name in params_to_sanitize:
                if param_name in kwargs and (
                    hasattr(kwargs[param_name], "__class__")
                    and kwargs[param_name].__class__.__name__ == "str"
                ):
                    value = kwargs[param_name]
                    for sanitize_type in sanitize_types:
                        if (
                            sanitize_type == SanitizationType.HTML
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_html(value)
                        if (
                            sanitize_type == SanitizationType.SQL
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_sql(value)
                        if (
                            sanitize_type == SanitizationType.XSS
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_xss(value)
                        if (
                            sanitize_type == SanitizationType.PATH
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_path(value)
                        if (
                            sanitize_type == SanitizationType.COMMAND
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_command(value)
                    if custom_sanitizers and param_name in custom_sanitizers:
                        value = custom_sanitizers[param_name](value)
                    kwargs[param_name] = {param_name: value}
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            sanitizer = InputSanitizer()
            params_to_sanitize = parameters if parameters else kwargs.keys()
            for param_name in params_to_sanitize:
                if param_name in kwargs and (
                    hasattr(kwargs[param_name], "__class__")
                    and kwargs[param_name].__class__.__name__ == "str"
                ):
                    value = kwargs[param_name]
                    for sanitize_type in sanitize_types:
                        if (
                            sanitize_type == SanitizationType.HTML
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_html(value)
                        if (
                            sanitize_type == SanitizationType.SQL
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_sql(value)
                        if (
                            sanitize_type == SanitizationType.XSS
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_xss(value)
                        if (
                            sanitize_type == SanitizationType.PATH
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_path(value)
                        if (
                            sanitize_type == SanitizationType.COMMAND
                            or sanitize_type == SanitizationType.ALL
                        ):
                            value = sanitizer.sanitize_command(value)
                    if custom_sanitizers and param_name in custom_sanitizers:
                        value = custom_sanitizers[param_name](value)
                    kwargs[param_name] = {param_name: value}
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def ValidateSchema(schema: Type[BaseModel], parameter="data", coerce=False):
    """
    Pydantic 스키마 검증 데코레이터

    Args:
        schema: Pydantic 모델
        parameter: 검증할 파라미터 이름
        coerce: 타입 강제 변환 여부
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if parameter in kwargs:
                data = kwargs[parameter]
                try:
                    if type(data).__name__ == "dict":
                        validated = schema(**data)
                    elif type(data).__name__ == "BaseModel":
                        validated = schema.validate(data)
                    else:
                        validated = schema(data)
                    kwargs[parameter] = {parameter: validated}
                except ValidationError as e:
                    logger.error(f"Schema validation failed: {e}")
                    raise ValueError(f"Invalid {parameter}: {e.errors()}")
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if parameter in kwargs:
                data = kwargs[parameter]
                try:
                    if type(data).__name__ == "dict":
                        validated = schema(**data)
                    elif type(data).__name__ == "BaseModel":
                        validated = schema.validate(data)
                    else:
                        validated = schema(data)
                    kwargs[parameter] = {parameter: validated}
                except ValidationError as e:
                    logger.error(f"Schema validation failed: {e}")
                    raise ValueError(f"Invalid {parameter}: {e.errors()}")
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class RateLimiter:
    """요청 속도 제한기"""

    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(lambda: deque())
        self.blocked_until = {}

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        block_duration=None,
    ) -> bool:
        """요청 허용 여부 확인"""
        now = datetime.now()
        if key in self.blocked_until:
            if now < self.blocked_until[key]:
                return False
            else:
                del self.blocked_until[key]
        request_times = self.requests[key]
        cutoff_time = now - timedelta(seconds=window_seconds)
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        if len(request_times) >= max_requests:
            if block_duration:
                self.blocked_until = {
                    **self.blocked_until,
                    key: now + timedelta(seconds=block_duration),
                }
            return False
        request_times = request_times + [now]
        return True


_rate_limiter = RateLimiter()


def RateLimited(
    max_requests=60,
    window_seconds=60,
    key_func=None,
    block_duration=None,
):
    """
    요청 속도 제한 데코레이터

    Args:
        max_requests: 최대 요청 수
        window_seconds: 시간 윈도우 (초)
        key_func: 키 생성 함수 (기본: 함수 이름)
        block_duration: 차단 기간 (초)
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = func.__name__
                if args:
                    key = f"{key}:{args[0]}"
            if not _rate_limiter.is_allowed(
                key, max_requests, window_seconds, block_duration
            ):
                logger.warning(f"Rate limit exceeded for {key}")
                raise Exception(
                    f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds"
                )
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = func.__name__
                if args:
                    key = f"{key}:{args[0]}"
            if not _rate_limiter.is_allowed(
                key, max_requests, window_seconds, block_duration
            ):
                logger.warning(f"Rate limit exceeded for {key}")
                raise Exception(
                    f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds"
                )
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


email_validator = EmailValidator()
url_validator = URLValidator()
ip_validator = IPAddressValidator()
__all__ = [
    "ValidateInput",
    "SanitizeInput",
    "ValidateSchema",
    "RateLimited",
    "ValidationLevel",
    "SanitizationType",
    "ValidationResult",
    "InputValidator",
    "EmailValidator",
    "URLValidator",
    "IPAddressValidator",
    "InputSanitizer",
    "RateLimiter",
    "email_validator",
    "url_validator",
    "ip_validator",
]
