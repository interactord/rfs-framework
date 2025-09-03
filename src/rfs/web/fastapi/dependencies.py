"""
FastAPI 의존성 주입 시스템

Result 패턴과 FastAPI의 의존성 주입을 완벽하게 통합하여
타입 안전한 서비스 의존성 관리를 제공합니다.
"""

from typing import Callable, Any, Optional, Union, Type, TypeVar, Generic, get_type_hints
from functools import wraps
import inspect
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException
from rfs.core.result import Result, Success, Failure
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult
from .errors import APIError
from .types import FastAPIResult, FastAPIMonoResult, FastAPIFluxResult

T = TypeVar('T')
E = TypeVar('E')

logger = logging.getLogger(__name__)


class ResultDependency(Generic[T]):
    """
    Result 패턴 기반 의존성 주입 컨테이너
    
    서비스 인스턴스를 Result로 래핑하여 의존성 생성 실패를 
    타입 안전하게 처리할 수 있습니다.
    
    Example:
        >>> user_service_dep = ResultDependency(UserService)
        >>> 
        >>> @app.get("/users/{user_id}")
        >>> @handle_result
        >>> async def get_user(
        ...     user_id: str,
        ...     user_service: UserService = Depends(user_service_dep)
        ... ) -> FastAPIResult[User]:
        ...     return await user_service.get_user(user_id)
    """
    
    def __init__(
        self,
        dependency_factory: Union[Callable[[], T], Callable[[], Result[T, APIError]], Type[T]],
        singleton: bool = True,
        async_factory: bool = False
    ):
        """
        Args:
            dependency_factory: 의존성을 생성하는 팩토리 함수 또는 클래스
            singleton: 싱글톤 인스턴스로 관리할지 여부
            async_factory: 비동기 팩토리 함수인지 여부
        """
        self.dependency_factory = dependency_factory
        self.singleton = singleton
        self.async_factory = async_factory
        self._cached_instance: Optional[T] = None
        self._creation_failed = False
    
    async def __call__(self) -> T:
        """
        의존성 인스턴스를 생성하고 반환합니다.
        
        Returns:
            T: 생성된 의존성 인스턴스
            
        Raises:
            HTTPException: 의존성 생성 실패 시
        """
        # 싱글톤이고 이미 생성된 인스턴스가 있다면 반환
        if self.singleton and self._cached_instance is not None:
            return self._cached_instance
        
        # 이전에 생성 실패했다면 캐시된 에러 반환
        if self.singleton and self._creation_failed:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "DEPENDENCY_CREATION_FAILED",
                    "message": "의존성 생성이 실패했습니다",
                    "details": {"dependency": str(self.dependency_factory)}
                }
            )
        
        try:
            # 의존성 인스턴스 생성
            if self.async_factory:
                instance = await self._create_async_instance()
            else:
                instance = self._create_sync_instance()
            
            # 싱글톤인 경우 캐시
            if self.singleton:
                self._cached_instance = instance
            
            return instance
            
        except Exception as e:
            logger.exception(f"의존성 생성 실패: {self.dependency_factory}")
            
            # 실패 상태 캐시 (싱글톤인 경우)
            if self.singleton:
                self._creation_failed = True
            
            # API 에러로 변환
            api_error = APIError.from_exception(e)
            raise HTTPException(
                status_code=api_error.status_code,
                detail=api_error.to_dict()
            )
    
    def _create_sync_instance(self) -> T:
        """동기 팩토리 함수로 인스턴스 생성"""
        if inspect.isclass(self.dependency_factory):
            # 클래스인 경우 인스턴스 생성
            instance = self.dependency_factory()
        else:
            # 함수인 경우 호출
            result = self.dependency_factory()
            
            # Result를 반환하는지 확인
            if hasattr(result, 'is_success'):
                if result.is_success():
                    instance = result.unwrap()
                else:
                    error = result.unwrap_error()
                    if isinstance(error, APIError):
                        raise HTTPException(
                            status_code=error.status_code,
                            detail=error.to_dict()
                        )
                    else:
                        raise Exception(str(error))
            else:
                instance = result
        
        return instance
    
    async def _create_async_instance(self) -> T:
        """비동기 팩토리 함수로 인스턴스 생성"""
        result = await self.dependency_factory()
        
        # Result를 반환하는지 확인
        if hasattr(result, 'is_success'):
            if result.is_success():
                return result.unwrap()
            else:
                error = result.unwrap_error()
                if isinstance(error, APIError):
                    raise HTTPException(
                        status_code=error.status_code,
                        detail=error.to_dict()
                    )
                else:
                    raise Exception(str(error))
        else:
            return result


def result_dependency(
    dependency_factory: Union[Callable[[], T], Callable[[], Result[T, APIError]], Type[T]],
    singleton: bool = True,
    async_factory: bool = False
) -> ResultDependency[T]:
    """
    Result 기반 의존성 주입을 생성하는 헬퍼 함수
    
    Args:
        dependency_factory: 의존성을 생성하는 팩토리 함수 또는 클래스
        singleton: 싱글톤 인스턴스로 관리할지 여부
        async_factory: 비동기 팩토리 함수인지 여부
    
    Returns:
        ResultDependency[T]: 의존성 주입 컨테이너
    
    Example:
        >>> # 클래스 기반 의존성
        >>> user_service_dep = result_dependency(UserService)
        >>> 
        >>> # 팩토리 함수 기반 의존성
        >>> def create_user_service() -> Result[UserService, APIError]:
        ...     try:
        ...         return Success(UserService(db_connection))
        ...     except Exception as e:
        ...         return Failure(APIError.from_exception(e))
        >>> 
        >>> user_service_dep = result_dependency(create_user_service)
        >>> 
        >>> # 비동기 팩토리 함수
        >>> async def create_async_service() -> Result[AsyncService, APIError]:
        ...     service = AsyncService()
        ...     await service.initialize()
        ...     return Success(service)
        >>> 
        >>> async_service_dep = result_dependency(
        ...     create_async_service,
        ...     async_factory=True
        ... )
    """
    return ResultDependency(dependency_factory, singleton, async_factory)


class ServiceRegistry:
    """
    서비스 인스턴스를 관리하는 레지스트리
    
    중앙화된 서비스 관리와 라이프사이클을 제공합니다.
    """
    
    def __init__(self):
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable] = {}
        self._singletons: set[str] = set()
    
    def register_service(
        self,
        name: str,
        factory: Union[Callable[[], T], Callable[[], Result[T, APIError]]],
        singleton: bool = True
    ):
        """
        서비스를 레지스트리에 등록합니다.
        
        Args:
            name: 서비스 이름
            factory: 서비스 생성 팩토리 함수
            singleton: 싱글톤으로 관리할지 여부
        """
        self._factories[name] = factory
        if singleton:
            self._singletons.add(name)
        
        logger.info(f"서비스 등록됨: {name} (singleton: {singleton})")
    
    async def get_service(self, name: str) -> Result[Any, APIError]:
        """
        서비스 인스턴스를 조회합니다.
        
        Args:
            name: 서비스 이름
            
        Returns:
            Result[Any, APIError]: 서비스 인스턴스 또는 에러
        """
        if name not in self._factories:
            return Failure(APIError.not_found("서비스", name))
        
        # 싱글톤이고 이미 생성된 경우
        if name in self._singletons and name in self._services:
            return Success(self._services[name])
        
        try:
            # 서비스 인스턴스 생성
            factory = self._factories[name]
            
            if inspect.iscoroutinefunction(factory):
                result = await factory()
            else:
                result = factory()
            
            # Result를 반환하는 팩토리인지 확인
            if hasattr(result, 'is_success'):
                if result.is_failure():
                    return result
                instance = result.unwrap()
            else:
                instance = result
            
            # 싱글톤인 경우 캐시
            if name in self._singletons:
                self._services[name] = instance
            
            return Success(instance)
            
        except Exception as e:
            logger.exception(f"서비스 생성 실패: {name}")
            return Failure(APIError.from_exception(e))
    
    def clear_cache(self, name: Optional[str] = None):
        """
        캐시된 서비스 인스턴스를 정리합니다.
        
        Args:
            name: 특정 서비스 이름 (None이면 모든 캐시 정리)
        """
        if name:
            self._services.pop(name, None)
            logger.info(f"서비스 캐시 정리됨: {name}")
        else:
            self._services.clear()
            logger.info("모든 서비스 캐시가 정리됨")


# 전역 서비스 레지스트리
_service_registry = ServiceRegistry()


def register_service(
    name: str,
    factory: Union[Callable[[], T], Callable[[], Result[T, APIError]]],
    singleton: bool = True
):
    """
    전역 서비스 레지스트리에 서비스를 등록합니다.
    
    Args:
        name: 서비스 이름
        factory: 서비스 생성 팩토리 함수
        singleton: 싱글톤으로 관리할지 여부
    """
    _service_registry.register_service(name, factory, singleton)


def inject_result_service(service_name: str):
    """
    서비스를 Result로 래핑하여 주입하는 데코레이터
    
    Args:
        service_name: 주입할 서비스 이름
        
    Returns:
        Callable: 데코레이터 함수
    
    Example:
        >>> # 서비스 등록
        >>> register_service("user_service", UserService)
        >>> 
        >>> @app.get("/users/{user_id}")
        >>> @handle_result
        >>> @inject_result_service("user_service")
        >>> async def get_user(
        ...     user_id: str, 
        ...     user_service: UserService
        ... ) -> FastAPIResult[User]:
        ...     return await user_service.get_user(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 서비스 인스턴스 조회
            service_result = await _service_registry.get_service(service_name)
            
            if service_result.is_failure():
                # 서비스 조회 실패
                error = service_result.unwrap_error()
                raise HTTPException(
                    status_code=error.status_code,
                    detail=error.to_dict()
                )
            
            # 함수 시그니처 분석하여 서비스 주입
            service_instance = service_result.unwrap()
            sig = inspect.signature(func)
            
            # 첫 번째 매개변수가 서비스인 경우 주입
            param_names = list(sig.parameters.keys())
            if param_names and param_names[0] not in kwargs:
                # 위치 인수로 주입
                args = (service_instance,) + args
            else:
                # 키워드 인수로 주입
                kwargs[param_names[0]] = service_instance
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# 편의 함수들

async def get_service_instance(service_name: str) -> Result[Any, APIError]:
    """
    서비스 인스턴스를 조회하는 편의 함수
    
    Args:
        service_name: 서비스 이름
        
    Returns:
        Result[Any, APIError]: 서비스 인스턴스 또는 에러
    """
    return await _service_registry.get_service(service_name)


def clear_service_cache(service_name: Optional[str] = None):
    """
    서비스 캐시를 정리하는 편의 함수
    
    Args:
        service_name: 서비스 이름 (None이면 모든 캐시 정리)
    """
    _service_registry.clear_cache(service_name)


@asynccontextmanager
async def service_scope():
    """
    서비스 스코프 컨텍스트 매니저
    
    스코프 종료 시 모든 서비스 캐시를 정리합니다.
    
    Example:
        >>> async with service_scope():
        ...     # 서비스 사용
        ...     user_service = await get_service_instance("user_service")
        ...     # 스코프 종료 시 자동으로 캐시 정리됨
    """
    try:
        yield
    finally:
        clear_service_cache()


# 타입 힌트 헬퍼

class InjectService:
    """
    서비스 주입을 위한 타입 힌트 헬퍼
    
    Example:
        >>> async def get_user(
        ...     user_id: str,
        ...     user_service: UserService = InjectService("user_service")
        ... ):
        ...     # user_service가 자동으로 주입됨
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
    
    async def __call__(self):
        service_result = await _service_registry.get_service(self.service_name)
        if service_result.is_failure():
            error = service_result.unwrap_error()
            raise HTTPException(
                status_code=error.status_code,
                detail=error.to_dict()
            )
        return service_result.unwrap()


def inject_service(service_name: str) -> Any:
    """
    서비스 주입 헬퍼 함수
    
    Args:
        service_name: 서비스 이름
        
    Returns:
        Any: 의존성 주입 객체
    
    Example:
        >>> async def get_user(
        ...     user_id: str,
        ...     user_service: UserService = Depends(inject_service("user_service"))
        ... ):
        ...     return await user_service.get_user(user_id)
    """
    return InjectService(service_name)