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
import re
import time
import hashlib
from typing import Any, Callable, Optional, Dict, List, Union, Type, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict
import ipaddress
import json
from abc import ABC, abstractmethod

from pydantic import BaseModel, ValidationError, validator
from ..core.result import Result, Success, Failure

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ValidationLevel(Enum):
    """검증 레벨"""
    STRICT = "strict"       # 엄격한 검증
    MODERATE = "moderate"   # 보통 검증
    LENIENT = "lenient"    # 관대한 검증


class SanitizationType(Enum):
    """정제 타입"""
    HTML = "html"           # HTML 태그 제거
    SQL = "sql"            # SQL 인젝션 방지
    XSS = "xss"            # XSS 공격 방지
    PATH = "path"          # 경로 조작 방지
    COMMAND = "command"    # 명령어 인젝션 방지
    ALL = "all"            # 모든 정제 적용


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_data: Optional[Any] = None
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
        self.pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
    
    def validate(self, value: Any) -> ValidationResult:
        """이메일 검증"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                errors=["Email must be a string"]
            )
        
        if not self.pattern.match(value):
            return ValidationResult(
                is_valid=False,
                errors=["Invalid email format"]
            )
        
        if self.allow_domains:
            domain = value.split('@')[1]
            if domain not in self.allow_domains:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Email domain {domain} not allowed"]
                )
        
        return ValidationResult(is_valid=True)


class URLValidator(InputValidator):
    """URL 검증기"""
    
    def __init__(
        self,
        allow_protocols: List[str] = ["http", "https"],
        allow_domains: Optional[List[str]] = None
    ):
        self.allow_protocols = allow_protocols
        self.allow_domains = allow_domains
        self.pattern = re.compile(
            r'^(https?|ftp)://[^\s/$.?#].[^\s]*$',
            re.IGNORECASE
        )
    
    def validate(self, value: Any) -> ValidationResult:
        """URL 검증"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                errors=["URL must be a string"]
            )
        
        if not self.pattern.match(value):
            return ValidationResult(
                is_valid=False,
                errors=["Invalid URL format"]
            )
        
        # 프로토콜 체크
        protocol = value.split('://')[0].lower()
        if protocol not in self.allow_protocols:
            return ValidationResult(
                is_valid=False,
                errors=[f"Protocol {protocol} not allowed"]
            )
        
        # 도메인 체크
        if self.allow_domains:
            from urllib.parse import urlparse
            parsed = urlparse(value)
            if parsed.hostname not in self.allow_domains:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Domain {parsed.hostname} not allowed"]
                )
        
        return ValidationResult(is_valid=True)


class IPAddressValidator(InputValidator):
    """IP 주소 검증기"""
    
    def __init__(
        self,
        allow_private: bool = False,
        allow_ipv6: bool = True,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None
    ):
        self.allow_private = allow_private
        self.allow_ipv6 = allow_ipv6
        self.whitelist = whitelist
        self.blacklist = blacklist
    
    def validate(self, value: Any) -> ValidationResult:
        """IP 주소 검증"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                errors=["IP address must be a string"]
            )
        
        try:
            ip = ipaddress.ip_address(value)
            
            # IPv6 체크
            if isinstance(ip, ipaddress.IPv6Address) and not self.allow_ipv6:
                return ValidationResult(
                    is_valid=False,
                    errors=["IPv6 addresses not allowed"]
                )
            
            # Private IP 체크
            if ip.is_private and not self.allow_private:
                return ValidationResult(
                    is_valid=False,
                    errors=["Private IP addresses not allowed"]
                )
            
            # 화이트리스트 체크
            if self.whitelist and str(ip) not in self.whitelist:
                return ValidationResult(
                    is_valid=False,
                    errors=["IP address not in whitelist"]
                )
            
            # 블랙리스트 체크
            if self.blacklist and str(ip) in self.blacklist:
                return ValidationResult(
                    is_valid=False,
                    errors=["IP address is blacklisted"]
                )
            
            return ValidationResult(is_valid=True)
            
        except ValueError:
            return ValidationResult(
                is_valid=False,
                errors=["Invalid IP address format"]
            )


class InputSanitizer:
    """입력값 정제기"""
    
    @staticmethod
    def sanitize_html(value: str) -> str:
        """HTML 태그 제거"""
        # 기본 HTML 태그 제거
        clean = re.sub(r'<[^>]+>', '', value)
        # HTML 엔티티 디코딩
        clean = clean.replace('&lt;', '<').replace('&gt;', '>')
        clean = clean.replace('&amp;', '&').replace('&quot;', '"')
        return clean
    
    @staticmethod
    def sanitize_sql(value: str) -> str:
        """SQL 인젝션 방지"""
        # 위험한 SQL 키워드 제거
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'EXEC',
            'EXECUTE', 'UNION', 'SELECT', '--', '/*', '*/'
        ]
        
        clean = value
        for keyword in dangerous_keywords:
            clean = re.sub(rf'\b{keyword}\b', '', clean, flags=re.IGNORECASE)
        
        # 특수 문자 이스케이프
        clean = clean.replace("'", "''")
        clean = clean.replace('"', '""')
        clean = clean.replace('\\', '\\\\')
        
        return clean
    
    @staticmethod
    def sanitize_xss(value: str) -> str:
        """XSS 공격 방지"""
        # 스크립트 태그 제거
        clean = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'javascript:', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'on\w+\s*=', '', clean, flags=re.IGNORECASE)
        
        # 위험한 속성 제거
        clean = re.sub(r'<iframe[^>]*>.*?</iframe>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<object[^>]*>.*?</object>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<embed[^>]*>', '', clean, flags=re.IGNORECASE)
        
        return clean
    
    @staticmethod
    def sanitize_path(value: str) -> str:
        """경로 조작 방지"""
        # 상위 디렉토리 접근 방지
        clean = value.replace('../', '').replace('..\\', '')
        
        # 절대 경로 제거
        clean = re.sub(r'^[/\\]', '', clean)
        
        # 위험한 문자 제거
        clean = re.sub(r'[<>:"|?*]', '', clean)
        
        # 숨김 파일 접근 방지
        clean = re.sub(r'^\.', '', clean)
        
        return clean
    
    @staticmethod
    def sanitize_command(value: str) -> str:
        """명령어 인젝션 방지"""
        # 위험한 문자 제거
        dangerous_chars = [';', '|', '&', '$', '`', '\n', '\r', '(', ')', '<', '>', '\\']
        
        clean = value
        for char in dangerous_chars:
            clean = clean.replace(char, '')
        
        # 위험한 명령어 제거
        dangerous_commands = ['rm', 'del', 'format', 'shutdown', 'reboot', 'kill']
        for cmd in dangerous_commands:
            clean = re.sub(rf'\b{cmd}\b', '', clean, flags=re.IGNORECASE)
        
        return clean


def ValidateInput(
    validators: Optional[List[InputValidator]] = None,
    level: ValidationLevel = ValidationLevel.MODERATE,
    fail_fast: bool = False,
    custom_validators: Optional[Dict[str, Callable]] = None
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
            
            # 기본 검증
            if level == ValidationLevel.STRICT:
                # 타입 체크
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    if param.annotation != param.empty:
                        if param_name in kwargs:
                            value = kwargs[param_name]
                            if not isinstance(value, param.annotation):
                                error = f"Parameter {param_name} must be {param.annotation}"
                                if fail_fast:
                                    raise TypeError(error)
                                errors.append(error)
            
            # 커스텀 검증기 실행
            if validators:
                for validator in validators:
                    for key, value in kwargs.items():
                        result = validator.validate(value)
                        if not result.is_valid:
                            if fail_fast:
                                raise ValueError(f"Validation failed for {key}: {result.errors}")
                            errors.extend(result.errors)
            
            # 커스텀 검증 함수 실행
            if custom_validators:
                for param_name, validator_func in custom_validators.items():
                    if param_name in kwargs:
                        try:
                            if not validator_func(kwargs[param_name]):
                                error = f"Custom validation failed for {param_name}"
                                if fail_fast:
                                    raise ValueError(error)
                                errors.append(error)
                        except Exception as e:
                            error = f"Custom validation error for {param_name}: {str(e)}"
                            if fail_fast:
                                raise ValueError(error)
                            errors.append(error)
            
            if errors:
                logger.warning(f"Validation errors in {func.__name__}: {errors}")
                if level == ValidationLevel.STRICT:
                    raise ValueError(f"Validation failed: {errors}")
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            errors = []
            
            # 기본 검증
            if level == ValidationLevel.STRICT:
                import inspect
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    if param.annotation != param.empty:
                        if param_name in kwargs:
                            value = kwargs[param_name]
                            if not isinstance(value, param.annotation):
                                error = f"Parameter {param_name} must be {param.annotation}"
                                if fail_fast:
                                    raise TypeError(error)
                                errors.append(error)
            
            # 검증기 실행
            if validators:
                for validator in validators:
                    for key, value in kwargs.items():
                        result = validator.validate(value)
                        if not result.is_valid:
                            if fail_fast:
                                raise ValueError(f"Validation failed for {key}: {result.errors}")
                            errors.extend(result.errors)
            
            # 커스텀 검증 함수 실행
            if custom_validators:
                for param_name, validator_func in custom_validators.items():
                    if param_name in kwargs:
                        try:
                            if not validator_func(kwargs[param_name]):
                                error = f"Custom validation failed for {param_name}"
                                if fail_fast:
                                    raise ValueError(error)
                                errors.append(error)
                        except Exception as e:
                            error = f"Custom validation error for {param_name}: {str(e)}"
                            if fail_fast:
                                raise ValueError(error)
                            errors.append(error)
            
            if errors:
                logger.warning(f"Validation errors in {func.__name__}: {errors}")
                if level == ValidationLevel.STRICT:
                    raise ValueError(f"Validation failed: {errors}")
            
            return func(*args, **kwargs)
        
        # 비동기/동기 함수 구분
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def SanitizeInput(
    sanitize_types: List[SanitizationType] = [SanitizationType.ALL],
    parameters: Optional[List[str]] = None,
    custom_sanitizers: Optional[Dict[str, Callable]] = None
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
            
            # 정제할 파라미터 결정
            params_to_sanitize = parameters if parameters else kwargs.keys()
            
            # 각 파라미터 정제
            for param_name in params_to_sanitize:
                if param_name in kwargs and isinstance(kwargs[param_name], str):
                    value = kwargs[param_name]
                    
                    # 정제 타입별 처리
                    for sanitize_type in sanitize_types:
                        if sanitize_type == SanitizationType.HTML or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_html(value)
                        if sanitize_type == SanitizationType.SQL or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_sql(value)
                        if sanitize_type == SanitizationType.XSS or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_xss(value)
                        if sanitize_type == SanitizationType.PATH or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_path(value)
                        if sanitize_type == SanitizationType.COMMAND or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_command(value)
                    
                    # 커스텀 정제 함수 실행
                    if custom_sanitizers and param_name in custom_sanitizers:
                        value = custom_sanitizers[param_name](value)
                    
                    kwargs[param_name] = value
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            sanitizer = InputSanitizer()
            
            # 정제할 파라미터 결정
            params_to_sanitize = parameters if parameters else kwargs.keys()
            
            # 각 파라미터 정제
            for param_name in params_to_sanitize:
                if param_name in kwargs and isinstance(kwargs[param_name], str):
                    value = kwargs[param_name]
                    
                    # 정제 타입별 처리
                    for sanitize_type in sanitize_types:
                        if sanitize_type == SanitizationType.HTML or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_html(value)
                        if sanitize_type == SanitizationType.SQL or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_sql(value)
                        if sanitize_type == SanitizationType.XSS or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_xss(value)
                        if sanitize_type == SanitizationType.PATH or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_path(value)
                        if sanitize_type == SanitizationType.COMMAND or sanitize_type == SanitizationType.ALL:
                            value = sanitizer.sanitize_command(value)
                    
                    # 커스텀 정제 함수 실행
                    if custom_sanitizers and param_name in custom_sanitizers:
                        value = custom_sanitizers[param_name](value)
                    
                    kwargs[param_name] = value
            
            return func(*args, **kwargs)
        
        # 비동기/동기 함수 구분
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def ValidateSchema(
    schema: Type[BaseModel],
    parameter: str = "data",
    coerce: bool = False
):
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
                    # 스키마 검증
                    if isinstance(data, dict):
                        validated = schema(**data)
                    elif isinstance(data, BaseModel):
                        validated = schema.validate(data)
                    else:
                        validated = schema(data)
                    
                    # 검증된 데이터로 교체
                    kwargs[parameter] = validated
                    
                except ValidationError as e:
                    logger.error(f"Schema validation failed: {e}")
                    raise ValueError(f"Invalid {parameter}: {e.errors()}")
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if parameter in kwargs:
                data = kwargs[parameter]
                
                try:
                    # 스키마 검증
                    if isinstance(data, dict):
                        validated = schema(**data)
                    elif isinstance(data, BaseModel):
                        validated = schema.validate(data)
                    else:
                        validated = schema(data)
                    
                    # 검증된 데이터로 교체
                    kwargs[parameter] = validated
                    
                except ValidationError as e:
                    logger.error(f"Schema validation failed: {e}")
                    raise ValueError(f"Invalid {parameter}: {e.errors()}")
            
            return func(*args, **kwargs)
        
        # 비동기/동기 함수 구분
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RateLimiter:
    """요청 속도 제한기"""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(lambda: deque())
        self.blocked_until: Dict[str, datetime] = {}
    
    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        block_duration: Optional[int] = None
    ) -> bool:
        """요청 허용 여부 확인"""
        now = datetime.now()
        
        # 차단 확인
        if key in self.blocked_until:
            if now < self.blocked_until[key]:
                return False
            else:
                del self.blocked_until[key]
        
        # 시간 윈도우 내 요청 기록
        request_times = self.requests[key]
        cutoff_time = now - timedelta(seconds=window_seconds)
        
        # 오래된 요청 제거
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        
        # 요청 수 확인
        if len(request_times) >= max_requests:
            # 차단 설정
            if block_duration:
                self.blocked_until[key] = now + timedelta(seconds=block_duration)
            return False
        
        # 요청 기록
        request_times.append(now)
        return True


# 글로벌 속도 제한기
_rate_limiter = RateLimiter()


def RateLimited(
    max_requests: int = 60,
    window_seconds: int = 60,
    key_func: Optional[Callable] = None,
    block_duration: Optional[int] = None
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
            # 키 생성
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # 기본: 함수 이름 + 첫 번째 인자 (보통 user_id나 IP)
                key = func.__name__
                if args:
                    key = f"{key}:{args[0]}"
            
            # 속도 제한 확인
            if not _rate_limiter.is_allowed(key, max_requests, window_seconds, block_duration):
                logger.warning(f"Rate limit exceeded for {key}")
                raise Exception(f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds")
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 키 생성
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = func.__name__
                if args:
                    key = f"{key}:{args[0]}"
            
            # 속도 제한 확인
            if not _rate_limiter.is_allowed(key, max_requests, window_seconds, block_duration):
                logger.warning(f"Rate limit exceeded for {key}")
                raise Exception(f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds")
            
            return func(*args, **kwargs)
        
        # 비동기/동기 함수 구분
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 미리 정의된 검증기들
email_validator = EmailValidator()
url_validator = URLValidator()
ip_validator = IPAddressValidator()

# Export
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
    "ip_validator"
]