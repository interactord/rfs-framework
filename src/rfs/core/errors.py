"""
RFS Framework 표준 에러 처리 시스템

RFS Framework의 표준화된 예외 처리 및 에러 컨텍스트 관리를 위한
기본 에러 클래스들을 제공합니다.

주요 특징:
- 컨텍스트 정보를 포함한 구조화된 에러 처리
- 계층적 에러 분류 시스템
- Result 패턴과의 완전한 통합
- 디버깅을 위한 상세한 에러 정보 제공
"""

import json
import traceback
from abc import ABC
from typing import Any, Dict, List, Optional, Union


class RFSError(Exception, ABC):
    """RFS Framework 기본 에러 클래스

    모든 RFS Framework 에러의 베이스 클래스로,
    구조화된 에러 정보와 컨텍스트를 제공합니다.

    특징:
    - 에러 컨텍스트 정보 저장
    - JSON 직렬화 가능한 에러 데이터
    - 디버깅을 위한 상세 정보 제공
    - Result 패턴과 완전 호환
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """RFS 에러 초기화

        Args:
            message: 에러 메시지
            context: 에러 발생 컨텍스트 정보
            error_code: 에러 코드 (분류용)
            cause: 원인이 된 예외 (체이닝용)
        """
        self.message = message
        self.context = context or {}
        self.error_code = error_code or self.__class__.__name__
        self.cause = cause
        self.traceback_info = traceback.format_exc() if cause else None

        # 계층적 에러 정보 구성
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """에러 메시지 포맷팅"""
        parts = [f"[{self.error_code}] {self.message}"]

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"Context: {context_str}")

        if self.cause:
            parts.append(f"Caused by: {self.cause}")

        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """에러 정보를 딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
            "traceback": self.traceback_info,
        }

    def to_json(self) -> str:
        """에러 정보를 JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def with_context(self, **additional_context: Any) -> "RFSError":
        """추가 컨텍스트 정보와 함께 새로운 에러 인스턴스 생성"""
        new_context = {**self.context, **additional_context}
        return self.__class__(
            message=self.message,
            context=new_context,
            error_code=self.error_code,
            cause=self.cause,
        )


class ValidationError(RFSError):
    """데이터 검증 에러

    입력 데이터 검증 실패, 타입 검증 오류,
    비즈니스 규칙 위반 등의 검증 관련 에러를 처리합니다.

    Example:
        >>> raise ValidationError(
        ...     "이메일 형식이 올바르지 않습니다",
        ...     context={"email": "invalid-email", "field": "email"}
        ... )
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        expected_type: Optional[type] = None,
        validation_rules: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """ValidationError 초기화

        Args:
            message: 검증 에러 메시지
            field: 검증 실패한 필드명
            value: 검증 실패한 값
            expected_type: 예상 타입
            validation_rules: 위반된 검증 규칙들
            **kwargs: 추가 컨텍스트 정보
        """
        context = kwargs.pop("context", {})

        # 검증 관련 컨텍스트 정보 추가
        if field is not None:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)[:100]  # 값이 너무 길면 잘라냄
        if expected_type is not None:
            context["expected_type"] = expected_type.__name__
        if validation_rules:
            context["validation_rules"] = validation_rules

        super().__init__(
            message=message, context=context, error_code="VALIDATION_ERROR", **kwargs
        )


class ConfigurationError(RFSError):
    """설정 관련 에러

    설정 파일 오류, 환경 변수 누락,
    설정 값 검증 실패 등의 설정 관련 에러를 처리합니다.

    Example:
        >>> raise ConfigurationError(
        ...     "필수 환경 변수가 설정되지 않았습니다",
        ...     context={"env_var": "DATABASE_URL", "config_file": ".env"}
        ... )
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
        expected_value: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """ConfigurationError 초기화

        Args:
            message: 설정 에러 메시지
            config_key: 문제가 된 설정 키
            config_file: 설정 파일 경로
            expected_value: 예상 값 설명
            **kwargs: 추가 컨텍스트 정보
        """
        context = kwargs.pop("context", {})

        # 설정 관련 컨텍스트 정보 추가
        if config_key is not None:
            context["config_key"] = config_key
        if config_file is not None:
            context["config_file"] = config_file
        if expected_value is not None:
            context["expected_value"] = expected_value

        super().__init__(
            message=message, context=context, error_code="CONFIGURATION_ERROR", **kwargs
        )


class IntegrationError(RFSError):
    """외부 시스템 통합 에러

    외부 API 호출 실패, 데이터베이스 연결 오류,
    서드파티 서비스 장애 등의 통합 관련 에러를 처리합니다.

    Example:
        >>> raise IntegrationError(
        ...     "외부 API 응답 시간 초과",
        ...     context={"api_endpoint": "/users", "timeout": 30, "service": "user-api"}
        ... )
    """

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """IntegrationError 초기화

        Args:
            message: 통합 에러 메시지
            service_name: 서비스명
            endpoint: API 엔드포인트
            status_code: HTTP 응답 코드
            response_data: 응답 데이터
            **kwargs: 추가 컨텍스트 정보
        """
        context = kwargs.pop("context", {})

        # 통합 관련 컨텍스트 정보 추가
        if service_name is not None:
            context["service_name"] = service_name
        if endpoint is not None:
            context["endpoint"] = endpoint
        if status_code is not None:
            context["status_code"] = status_code
        if response_data is not None:
            # 응답 데이터가 크면 요약
            context["response_data"] = str(response_data)[:200]

        super().__init__(
            message=message, context=context, error_code="INTEGRATION_ERROR", **kwargs
        )


class BusinessLogicError(RFSError):
    """비즈니스 로직 에러

    비즈니스 규칙 위반, 권한 부족,
    상태 전이 오류 등의 비즈니스 로직 관련 에러를 처리합니다.

    Example:
        >>> raise BusinessLogicError(
        ...     "잔액이 부족하여 결제할 수 없습니다",
        ...     context={"user_id": "123", "required_amount": 10000, "current_balance": 5000}
        ... )
    """

    def __init__(
        self,
        message: str,
        rule_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[Union[str, int]] = None,
        **kwargs: Any,
    ) -> None:
        """BusinessLogicError 초기화

        Args:
            message: 비즈니스 로직 에러 메시지
            rule_name: 위반된 비즈니스 규칙명
            entity_type: 관련 엔터티 타입
            entity_id: 관련 엔터티 ID
            **kwargs: 추가 컨텍스트 정보
        """
        context = kwargs.pop("context", {})

        # 비즈니스 로직 관련 컨텍스트 정보 추가
        if rule_name is not None:
            context["rule_name"] = rule_name
        if entity_type is not None:
            context["entity_type"] = entity_type
        if entity_id is not None:
            context["entity_id"] = str(entity_id)

        super().__init__(
            message=message,
            context=context,
            error_code="BUSINESS_LOGIC_ERROR",
            **kwargs,
        )


# 편의용 에러 생성 함수들
def validation_error(message: str, **context: Any) -> ValidationError:
    """ValidationError 생성 편의 함수"""
    return ValidationError(message, context=context)


def config_error(message: str, **context: Any) -> ConfigurationError:
    """ConfigurationError 생성 편의 함수"""
    return ConfigurationError(message, context=context)


def integration_error(message: str, **context: Any) -> IntegrationError:
    """IntegrationError 생성 편의 함수"""
    return IntegrationError(message, context=context)


def business_error(message: str, **context: Any) -> BusinessLogicError:
    """BusinessLogicError 생성 편의 함수"""
    return BusinessLogicError(message, context=context)


# 에러 처리를 위한 데코레이터 및 유틸리티
from functools import wraps
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def handle_errors(
    error_mapping: Optional[Dict[type, type]] = None, default_error: type = RFSError
) -> Callable[[F], F]:
    """예외를 RFS 에러로 변환하는 데코레이터

    Args:
        error_mapping: 예외 타입별 RFS 에러 매핑
        default_error: 기본 RFS 에러 타입

    Example:
        >>> @handle_errors({ValueError: ValidationError})
        ... def process_data(data: str) -> str:
        ...     return data.upper()
    """
    if error_mapping is None:
        error_mapping = {}

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except RFSError:
                # RFS 에러는 그대로 재발생
                raise
            except Exception as e:
                # 매핑된 에러 타입으로 변환
                error_type = error_mapping.get(type(e), default_error)
                raise error_type(
                    message=f"{func.__name__} 실행 중 오류 발생: {str(e)}",
                    context={
                        "function": func.__name__,
                        "args": str(args)[:100],
                        "kwargs": str(kwargs)[:100],
                    },
                    cause=e,
                )

        return wrapper  # type: ignore

    return decorator
