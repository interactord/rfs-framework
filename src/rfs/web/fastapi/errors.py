"""
FastAPI 통합용 에러 클래스 시스템

APIError 클래스와 표준 에러 코드를 제공하여 
Result 패턴과 HTTP 응답 간의 완벽한 매핑을 지원합니다.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """표준 API 에러 코드"""
    
    # Client Errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    
    # Server Errors (5xx)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"


@dataclass
class APIError:
    """웹 API 전용 에러 클래스
    
    Result 패턴의 에러를 HTTP 응답으로 변환하기 위한 표준 에러 클래스입니다.
    자동 HTTP 상태 코드 매핑과 구조화된 에러 응답을 제공합니다.
    """
    
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = field(default_factory=dict)
    status_code: int = 500
    
    def __post_init__(self):
        """상태 코드 자동 매핑"""
        if self.status_code == 500:  # 기본값인 경우에만 자동 매핑
            self.status_code = self._get_default_status_code()
    
    def _get_default_status_code(self) -> int:
        """에러 코드에 따른 기본 HTTP 상태 코드 매핑"""
        code_to_status = {
            ErrorCode.VALIDATION_ERROR: 400,
            ErrorCode.UNAUTHORIZED: 401,
            ErrorCode.FORBIDDEN: 403,
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.CONFLICT: 409,
            ErrorCode.REQUEST_TIMEOUT: 408,
            ErrorCode.PAYLOAD_TOO_LARGE: 413,
            ErrorCode.RATE_LIMITED: 429,
            ErrorCode.INTERNAL_SERVER_ERROR: 500,
            ErrorCode.SERVICE_UNAVAILABLE: 503,
            ErrorCode.TIMEOUT_ERROR: 504,
            ErrorCode.DATABASE_ERROR: 500,
            ErrorCode.EXTERNAL_SERVICE_ERROR: 502,
        }
        return code_to_status.get(self.code, 500)
    
    # === 클래스 메서드 팩토리들 ===
    
    @classmethod
    def not_found(cls, resource: str, resource_id: Optional[str] = None) -> "APIError":
        """리소스를 찾을 수 없는 경우
        
        Args:
            resource: 리소스 이름 (예: "사용자", "주문")
            resource_id: 리소스 ID (옵션)
            
        Returns:
            APIError: NOT_FOUND 에러
        """
        message = f"{resource}을(를) 찾을 수 없습니다"
        details = {"resource": resource}
        if resource_id:
            details["resource_id"] = resource_id
        
        return cls(
            code=ErrorCode.NOT_FOUND,
            message=message,
            details=details
        )
    
    @classmethod
    def validation_error(cls, field_errors: Dict[str, str]) -> "APIError":
        """입력값 검증 실패
        
        Args:
            field_errors: 필드별 에러 메시지 딕셔너리
            
        Returns:
            APIError: VALIDATION_ERROR 에러
        """
        return cls(
            code=ErrorCode.VALIDATION_ERROR,
            message="입력값이 유효하지 않습니다",
            details={"field_errors": field_errors}
        )
    
    @classmethod
    def unauthorized(cls, reason: Optional[str] = None) -> "APIError":
        """인증 실패
        
        Args:
            reason: 실패 이유 (옵션)
            
        Returns:
            APIError: UNAUTHORIZED 에러
        """
        message = "인증이 필요합니다"
        details = {}
        if reason:
            details["reason"] = reason
        
        return cls(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            details=details
        )
    
    @classmethod
    def forbidden(cls, resource: str, action: str) -> "APIError":
        """권한 부족
        
        Args:
            resource: 리소스 이름
            action: 수행하려는 작업
            
        Returns:
            APIError: FORBIDDEN 에러
        """
        return cls(
            code=ErrorCode.FORBIDDEN,
            message=f"{resource}에 대한 {action} 권한이 없습니다",
            details={"resource": resource, "action": action}
        )
    
    @classmethod
    def conflict(cls, resource: str, reason: str) -> "APIError":
        """리소스 충돌
        
        Args:
            resource: 리소스 이름
            reason: 충돌 이유
            
        Returns:
            APIError: CONFLICT 에러
        """
        return cls(
            code=ErrorCode.CONFLICT,
            message=f"{resource} 충돌이 발생했습니다: {reason}",
            details={"resource": resource, "reason": reason}
        )
    
    @classmethod
    def rate_limited(cls, limit: int, window: str) -> "APIError":
        """요청 한도 초과
        
        Args:
            limit: 허용 요청 수
            window: 시간 창 (예: "1분", "1시간")
            
        Returns:
            APIError: RATE_LIMITED 에러
        """
        return cls(
            code=ErrorCode.RATE_LIMITED,
            message=f"요청 한도를 초과했습니다 ({limit}회/{window})",
            details={"limit": limit, "window": window}
        )
    
    @classmethod
    def internal_server_error(cls, message: str = "내부 서버 오류가 발생했습니다") -> "APIError":
        """내부 서버 에러
        
        Args:
            message: 에러 메시지
            
        Returns:
            APIError: INTERNAL_SERVER_ERROR 에러
        """
        return cls(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message
        )
    
    @classmethod
    def timeout_error(cls, operation: str, timeout_seconds: float) -> "APIError":
        """타임아웃 에러
        
        Args:
            operation: 타임아웃된 작업
            timeout_seconds: 타임아웃 시간 (초)
            
        Returns:
            APIError: TIMEOUT_ERROR 에러
        """
        return cls(
            code=ErrorCode.TIMEOUT_ERROR,
            message=f"{operation} 작업이 시간 초과되었습니다 ({timeout_seconds}초)",
            details={"operation": operation, "timeout_seconds": timeout_seconds}
        )
    
    @classmethod
    def database_error(cls, operation: str, details: Optional[str] = None) -> "APIError":
        """데이터베이스 에러
        
        Args:
            operation: 데이터베이스 작업
            details: 추가 상세 정보
            
        Returns:
            APIError: DATABASE_ERROR 에러
        """
        message = f"데이터베이스 {operation} 작업 중 오류가 발생했습니다"
        error_details = {"operation": operation}
        if details:
            error_details["details"] = details
        
        return cls(
            code=ErrorCode.DATABASE_ERROR,
            message=message,
            details=error_details
        )
    
    @classmethod
    def external_service_error(cls, service: str, reason: Optional[str] = None) -> "APIError":
        """외부 서비스 에러
        
        Args:
            service: 외부 서비스 이름
            reason: 실패 이유 (옵션)
            
        Returns:
            APIError: EXTERNAL_SERVICE_ERROR 에러
        """
        message = f"외부 서비스({service}) 호출 중 오류가 발생했습니다"
        details = {"service": service}
        if reason:
            details["reason"] = reason
        
        return cls(
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            message=message,
            details=details
        )
    
    @classmethod
    def from_exception(cls, exception: Exception) -> "APIError":
        """일반 예외를 APIError로 변환
        
        Args:
            exception: 변환할 예외
            
        Returns:
            APIError: 적절한 APIError 인스턴스
        """
        error_type = type(exception).__name__
        error_message = str(exception)
        
        # 특정 예외 타입에 따른 매핑
        if "NotFound" in error_type or "DoesNotExist" in error_type:
            return cls.not_found("리소스", error_message)
        elif "ValidationError" in error_type or "ValueError" in error_type:
            return cls.validation_error({"general": error_message})
        elif "PermissionError" in error_type or "Forbidden" in error_type:
            return cls.forbidden("리소스", "접근")
        elif "TimeoutError" in error_type:
            return cls.timeout_error("요청", 30.0)
        elif "DatabaseError" in error_type or "IntegrityError" in error_type:
            return cls.database_error("조회", error_message)
        elif "ConnectionError" in error_type or "RequestException" in error_type:
            return cls.external_service_error("외부 API", error_message)
        else:
            # 일반적인 예외는 내부 서버 에러로 처리
            logger.exception(f"Unexpected exception converted to APIError: {exception}")
            return cls.internal_server_error(f"예상치 못한 오류: {error_message}")
    
    @classmethod
    def from_service_error(cls, error: Any) -> "APIError":
        """서비스 레이어 에러를 APIError로 변환
        
        Args:
            error: 서비스 레이어에서 발생한 에러
            
        Returns:
            APIError: 변환된 APIError
        """
        if isinstance(error, APIError):
            return error
        elif isinstance(error, Exception):
            return cls.from_exception(error)
        elif isinstance(error, str):
            return cls.internal_server_error(error)
        else:
            return cls.internal_server_error(f"알 수 없는 에러: {str(error)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)
        
        Returns:
            Dict[str, Any]: 직렬화 가능한 딕셔너리
        """
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code
        }
    
    def __str__(self) -> str:
        """문자열 표현"""
        return f"APIError({self.code.value}: {self.message})"
    
    def __repr__(self) -> str:
        """디버깅용 문자열 표현"""
        return f"APIError(code={self.code.value}, message='{self.message}', status_code={self.status_code})"