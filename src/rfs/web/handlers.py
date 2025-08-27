"""
RFS Web Handlers (RFS v4.1)

요청 핸들러 시스템
"""

import asyncio
import inspect
import logging
import traceback
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Type, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from ..events import create_event, publish_event

logger = get_logger(__name__)


class RequestHandler(ABC):
    """요청 핸들러 베이스 클래스"""

    def __init__(self, handler_id: str = None):
        self.handler_id = handler_id or self.__class__.__name__

    @abstractmethod
    async def handle(self, request: Any, **kwargs) -> Any:
        """요청 처리"""
        pass

    async def before_handle(self, request: Any) -> Result[None, str]:
        """핸들링 전 처리"""
        return Success(None)

    async def after_handle(self, request: Any, response: Any) -> Result[None, str]:
        """핸들링 후 처리"""
        return Success(None)

    async def on_error(self, request: Any, error: Exception) -> Any:
        """에러 처리"""
        logger.error(f"핸들러 에러: {error}", extra={"handler": self.handler_id})
        return await self.create_error_response(error)

    async def create_error_response(self, error: Exception) -> Any:
        """에러 응답 생성"""
        return {
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
                "handler": self.handler_id,
            }
        }


class AsyncRequestHandler(RequestHandler):
    """비동기 요청 핸들러"""

    def __init__(self, handler_func: Callable, handler_id: str = None):
        super().__init__(handler_id or handler_func.__name__)
        self.handler_func = handler_func
        if not asyncio.iscoroutinefunction(handler_func):
            raise ValueError("핸들러 함수는 비동기 함수여야 합니다")

    async def handle(self, request: Any, **kwargs) -> Any:
        """비동기 요청 처리"""
        try:
            before_result = await self.before_handle(request)
            if not before_result.is_success():
                return await self.create_error_response(
                    Exception(before_result.unwrap_err())
                )
            if inspect.iscoroutinefunction(self.handler_func):
                response = await self.handler_func(request, **kwargs)
            else:
                response = self.handler_func(request, **kwargs)
            after_result = await self.after_handle(request, response)
            if not after_result.is_success():
                logger.warning(f"사후 처리 실패: {after_result.unwrap_err()}")
            return response
        except Exception as e:
            return await self.on_error(request, e)


class SyncRequestHandler(RequestHandler):
    """동기 요청 핸들러"""

    def __init__(self, handler_func: Callable, handler_id: str = None):
        super().__init__(handler_id or handler_func.__name__)
        self.handler_func = handler_func

    async def handle(self, request: Any, **kwargs) -> Any:
        """동기 요청 처리 (비동기 래퍼)"""
        try:
            before_result = await self.before_handle(request)
            if not before_result.is_success():
                return await self.create_error_response(
                    Exception(before_result.unwrap_err())
                )
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.handler_func(request, **kwargs)
            )
            after_result = await self.after_handle(request, response)
            if not after_result.is_success():
                logger.warning(f"사후 처리 실패: {after_result.unwrap_err()}")
            return response
        except Exception as e:
            return await self.on_error(request, e)


class ResponseHandler:
    """응답 처리기"""

    @staticmethod
    async def create_success_response(
        data: Any, status_code=200, headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """성공 응답 생성"""
        response = {"success": True, "data": data, "status_code": status_code}
        if headers:
            response["headers"] = {"headers": headers}
        return response

    @staticmethod
    async def create_error_response(
        error_message: str,
        error_code="INTERNAL_ERROR",
        status_code=500,
        details: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """에러 응답 생성"""
        response = {
            "success": False,
            "error": {
                "code": error_code,
                "message": error_message,
                "status_code": status_code,
            },
        }
        if details:
            response["error"] = {**response["error"], "details": details}
        return response

    @staticmethod
    async def create_validation_error_response(
        validation_errors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """검증 에러 응답 생성"""
        return await ResponseHandler.create_error_response(
            error_message="입력 데이터 검증 실패",
            error_code="VALIDATION_ERROR",
            status_code=400,
            details={"validation_errors": validation_errors},
        )


class ErrorHandler:
    """에러 처리기"""

    def __init__(self):
        self.error_handlers: Dict[Type[Exception], Callable] = {}
        self.global_error_handler = None

    def register_handler(self, exception_type: Type[Exception], handler: Callable):
        """특정 예외 타입에 대한 핸들러 등록"""
        self.error_handlers = {**self.error_handlers, exception_type: handler}
        logger.info(f"에러 핸들러 등록: {exception_type.__name__}")

    def set_global_handler(self, handler: Callable):
        """전역 에러 핸들러 설정"""
        self.global_error_handler = handler
        logger.info("전역 에러 핸들러 설정")

    async def handle_error(self, error: Exception, request: Any = None) -> Any:
        """에러 처리"""
        error_type = type(error)
        if error_type in self.error_handlers:
            handler = self.error_handlers[error_type]
            try:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(error, request)
                else:
                    return handler(error, request)
            except Exception as handler_error:
                logger.error(f"에러 핸들러 실행 실패: {handler_error}")
        if self.global_error_handler:
            try:
                if asyncio.iscoroutinefunction(self.global_error_handler):
                    return await self.global_error_handler(error, request)
                else:
                    return self.global_error_handler(error, request)
            except Exception as handler_error:
                logger.error(f"전역 에러 핸들러 실행 실패: {handler_error}")
        return await self._default_error_handler(error, request)

    async def _default_error_handler(
        self, error: Exception, request: Any = None
    ) -> Any:
        """기본 에러 처리"""
        logger.error(f"처리되지 않은 에러: {error}")
        logger.error(traceback.format_exc())
        try:
            await publish_event(
                "error.unhandled",
                data={
                    "error_type": error.__class__.__name__,
                    "error_message": str(error),
                    "request_info": self._extract_request_info(request),
                },
            )
        except Exception as event_error:
            logger.error(f"에러 이벤트 발행 실패: {event_error}")
        return await ResponseHandler.create_error_response(
            error_message="서버 내부 오류가 발생했습니다",
            error_code="INTERNAL_SERVER_ERROR",
            status_code=500,
            details={
                "error_type": error.__class__.__name__,
                "timestamp": asyncio.get_event_loop().time(),
            },
        )

    def _extract_request_info(self, request: Any) -> Dict[str, Any]:
        """요청 정보 추출"""
        if not request:
            return {}
        info = {}
        try:
            if hasattr(request, "method"):
                info["method"] = {"method": request.method}
            if hasattr(request, "url"):
                info["url"] = {"url": str(request.url)}
            if hasattr(request, "headers"):
                safe_headers = {}
                for key, value in request.headers.items():
                    if key.lower() not in ["authorization", "cookie", "x-api-key"]:
                        safe_headers[key] = {key: value}
                info["headers"] = {"headers": safe_headers}
        except Exception as e:
            logger.warning(f"요청 정보 추출 실패: {e}")
        return info


_global_error_handler = None


def get_error_handler() -> ErrorHandler:
    """전역 에러 핸들러 인스턴스 반환"""
    # global _global_error_handler - removed for functional programming
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


async def handle_request(handler_func: Callable, request: Any, **kwargs) -> Any:
    """요청 처리"""
    try:
        if asyncio.iscoroutinefunction(handler_func):
            handler = AsyncRequestHandler(handler_func)
        else:
            handler = SyncRequestHandler(handler_func)
        return await handler.handle(request, **kwargs)
    except Exception as e:
        error_handler = get_error_handler()
        return await error_handler.handle_error(e, request)


async def handle_error(error: Exception, request: Any = None) -> Any:
    """에러 처리"""
    error_handler = get_error_handler()
    return await error_handler.handle_error(error, request)


def error_handler(exception_type: Type[Exception]):
    """에러 핸들러 데코레이터"""

    def decorator(handler_func: Callable):
        error_handler_instance = get_error_handler()
        error_handler_instance.register_handler(exception_type, handler_func)
        return handler_func

    return decorator


def global_error_handler(handler_func: Callable):
    """전역 에러 핸들러 데코레이터"""
    error_handler_instance = get_error_handler()
    error_handler_instance.set_global_handler(handler_func)
    return handler_func
