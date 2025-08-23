"""
RFS Database Repository (RFS v4.1)

Repository 패턴 구현
"""

import asyncio
from typing import Dict, Any, List, Optional, Type, Union, Generic, TypeVar
from abc import ABC, abstractmethod
import inspect
from dataclasses import dataclass, field

from ..core.result import Result, Success, Failure
from ..core.singleton import SingletonMeta
from ..core.enhanced_logging import get_logger
from .models import BaseModel, ModelRegistry, get_model_registry
from .query import QueryBuilder, Filter, Sort, Pagination

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseModel)


@dataclass
class RepositoryConfig:
    """Repository 설정"""
    auto_commit: bool = True
    batch_size: int = 100
    cache_enabled: bool = True
    cache_ttl: int = 3600
    retry_count: int = 3
    timeout: int = 30


class Repository(Generic[T], ABC):
    """Repository 기본 인터페이스"""
    
    def __init__(self, model_class: Type[T], config: RepositoryConfig = None):
        self.model_class = model_class
        self.config = config or RepositoryConfig()
        self.model_name = model_class.__name__
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Result[T, str]:
        """모델 생성"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: Any) -> Result[Optional[T], str]:
        """ID로 조회"""
        pass
    
    @abstractmethod
    async def update(self, id: Any, data: Dict[str, Any]) -> Result[T, str]:
        """모델 업데이트"""
        pass
    
    @abstractmethod
    async def delete(self, id: Any) -> Result[None, str]:
        """모델 삭제"""
        pass
    
    @abstractmethod
    async def find(self, filters: Dict[str, Any] = None, limit: int = None, offset: int = None) -> Result[List[T], str]:
        """모델 목록 조회"""
        pass
    
    @abstractmethod
    async def count(self, filters: Dict[str, Any] = None) -> Result[int, str]:
        """모델 개수 조회"""
        pass


class BaseRepository(Repository[T]):
    """기본 Repository 구현"""
    
    def __init__(self, model_class: Type[T], config: RepositoryConfig = None):
        super().__init__(model_class, config)
        self._query_builder = QueryBuilder(model_class)
    
    async def create(self, data: Dict[str, Any]) -> Result[T, str]:
        """모델 생성"""
        try:
            # 모델 인스턴스 생성
            instance = self.model_class(**data)
            
            # 저장
            save_result = await instance.save()
            if not save_result.is_success():
                return Failure(f"모델 저장 실패: {save_result.unwrap_err()}")
            
            model = save_result.unwrap()
            logger.info(f"모델 생성 완료: {self.model_name}")
            return Success(model)
            
        except Exception as e:
            error_msg = f"모델 생성 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def get_by_id(self, id: Any) -> Result[Optional[T], str]:
        """ID로 조회"""
        try:
            # 기본 키 필드명 추정 (id 또는 pk)
            pk_field = 'id'
            if hasattr(self.model_class, '__fields__'):
                for field_name, field_info in self.model_class.__fields__.items():
                    if field_info.primary_key:
                        pk_field = field_name
                        break
            
            result = await self.model_class.get(**{pk_field: id})
            return result
            
        except Exception as e:
            error_msg = f"모델 조회 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def update(self, id: Any, data: Dict[str, Any]) -> Result[T, str]:
        """모델 업데이트"""
        try:
            # 모델 조회
            get_result = await self.get_by_id(id)
            if not get_result.is_success():
                return Failure(get_result.unwrap_err())
            
            model = get_result.unwrap()
            if not model:
                return Failure(f"모델을 찾을 수 없습니다: {id}")
            
            # 업데이트
            model.update_from_dict(data)
            
            # 저장
            save_result = await model.save()
            if not save_result.is_success():
                return Failure(f"모델 업데이트 실패: {save_result.unwrap_err()}")
            
            updated_model = save_result.unwrap()
            logger.info(f"모델 업데이트 완료: {self.model_name} (ID: {id})")
            return Success(updated_model)
            
        except Exception as e:
            error_msg = f"모델 업데이트 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def delete(self, id: Any) -> Result[None, str]:
        """모델 삭제"""
        try:
            # 모델 조회
            get_result = await self.get_by_id(id)
            if not get_result.is_success():
                return Failure(get_result.unwrap_err())
            
            model = get_result.unwrap()
            if not model:
                return Failure(f"모델을 찾을 수 없습니다: {id}")
            
            # 삭제
            delete_result = await model.delete()
            if not delete_result.is_success():
                return Failure(f"모델 삭제 실패: {delete_result.unwrap_err()}")
            
            logger.info(f"모델 삭제 완료: {self.model_name} (ID: {id})")
            return Success(None)
            
        except Exception as e:
            error_msg = f"모델 삭제 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def find(self, filters: Dict[str, Any] = None, limit: int = None, offset: int = None) -> Result[List[T], str]:
        """모델 목록 조회"""
        try:
            # 쿼리 빌더 사용
            query = self._query_builder
            
            if filters:
                query = query.where(**filters)
            
            if limit:
                query = query.limit(limit)
            
            if offset:
                query = query.offset(offset)
            
            # 실행
            result = await query.execute()
            if not result.is_success():
                return Failure(f"모델 조회 실패: {result.unwrap_err()}")
            
            models = result.unwrap()
            logger.info(f"모델 조회 완료: {self.model_name} ({len(models)}개)")
            return Success(models)
            
        except Exception as e:
            error_msg = f"모델 조회 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def count(self, filters: Dict[str, Any] = None) -> Result[int, str]:
        """모델 개수 조회"""
        try:
            # 쿼리 빌더 사용
            query = self._query_builder.count()
            
            if filters:
                query = query.where(**filters)
            
            # 실행
            result = await query.execute()
            if not result.is_success():
                return Failure(f"개수 조회 실패: {result.unwrap_err()}")
            
            count = result.unwrap()
            return Success(count)
            
        except Exception as e:
            error_msg = f"개수 조회 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)


class CRUDRepository(BaseRepository[T]):
    """CRUD Repository with additional methods"""
    
    async def bulk_create(self, data_list: List[Dict[str, Any]]) -> Result[List[T], str]:
        """대량 생성"""
        try:
            models = []
            batch_size = self.config.batch_size
            
            # 배치별로 처리
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i + batch_size]
                batch_models = []
                
                for data in batch:
                    create_result = await self.create(data)
                    if not create_result.is_success():
                        return Failure(f"배치 생성 실패: {create_result.unwrap_err()}")
                    
                    batch_models.append(create_result.unwrap())
                
                models.extend(batch_models)
                logger.info(f"배치 처리 완료: {len(batch)}개")
            
            logger.info(f"대량 생성 완료: {self.model_name} ({len(models)}개)")
            return Success(models)
            
        except Exception as e:
            error_msg = f"대량 생성 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def bulk_update(self, updates: List[Dict[str, Any]]) -> Result[List[T], str]:
        """대량 업데이트"""
        try:
            models = []
            batch_size = self.config.batch_size
            
            # 배치별로 처리
            for i in range(0, len(updates), batch_size):
                batch = updates[i:i + batch_size]
                batch_models = []
                
                for update_data in batch:
                    if 'id' not in update_data:
                        return Failure("업데이트 데이터에 id가 필요합니다")
                    
                    id_value = update_data.pop('id')
                    update_result = await self.update(id_value, update_data)
                    
                    if not update_result.is_success():
                        return Failure(f"배치 업데이트 실패: {update_result.unwrap_err()}")
                    
                    batch_models.append(update_result.unwrap())
                
                models.extend(batch_models)
                logger.info(f"업데이트 배치 처리 완료: {len(batch)}개")
            
            logger.info(f"대량 업데이트 완료: {self.model_name} ({len(models)}개)")
            return Success(models)
            
        except Exception as e:
            error_msg = f"대량 업데이트 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def bulk_delete(self, ids: List[Any]) -> Result[None, str]:
        """대량 삭제"""
        try:
            batch_size = self.config.batch_size
            
            # 배치별로 처리
            for i in range(0, len(ids), batch_size):
                batch = ids[i:i + batch_size]
                
                for id_value in batch:
                    delete_result = await self.delete(id_value)
                    if not delete_result.is_success():
                        return Failure(f"배치 삭제 실패: {delete_result.unwrap_err()}")
                
                logger.info(f"삭제 배치 처리 완료: {len(batch)}개")
            
            logger.info(f"대량 삭제 완료: {self.model_name} ({len(ids)}개)")
            return Success(None)
            
        except Exception as e:
            error_msg = f"대량 삭제 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def find_paginated(
        self, 
        page: int = 1, 
        page_size: int = 10, 
        filters: Dict[str, Any] = None,
        sort: List[Sort] = None
    ) -> Result[Dict[str, Any], str]:
        """페이지네이션 조회"""
        try:
            offset = (page - 1) * page_size
            
            # 쿼리 빌더 사용
            query = self._query_builder
            
            if filters:
                query = query.where(**filters)
            
            if sort:
                for sort_item in sort:
                    query = query.sort(sort_item.field, sort_item.order)
            
            query = query.limit(page_size).offset(offset)
            
            # 데이터 조회
            data_result = await query.execute()
            if not data_result.is_success():
                return Failure(f"페이지네이션 조회 실패: {data_result.unwrap_err()}")
            
            # 전체 개수 조회
            count_result = await self.count(filters)
            if not count_result.is_success():
                return Failure(f"개수 조회 실패: {count_result.unwrap_err()}")
            
            data = data_result.unwrap()
            total_count = count_result.unwrap()
            total_pages = (total_count + page_size - 1) // page_size
            
            result = {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
            
            logger.info(f"페이지네이션 조회 완료: {self.model_name} (페이지 {page}/{total_pages})")
            return Success(result)
            
        except Exception as e:
            error_msg = f"페이지네이션 조회 실패 ({self.model_name}): {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)


class RepositoryRegistry(metaclass=SingletonMeta):
    """Repository 레지스트리"""
    
    def __init__(self):
        self.repositories: Dict[str, Repository] = {}
        self.configs: Dict[str, RepositoryConfig] = {}
    
    def register_repository(
        self, 
        model_class: Type[BaseModel], 
        repository_class: Type[Repository] = None,
        config: RepositoryConfig = None
    ):
        """Repository 등록"""
        model_name = model_class.__name__
        
        # 기본 Repository 클래스 사용
        if repository_class is None:
            repository_class = CRUDRepository
        
        # Repository 인스턴스 생성
        repository = repository_class(model_class, config)
        self.repositories[model_name] = repository
        
        if config:
            self.configs[model_name] = config
        
        logger.info(f"Repository 등록: {model_name}")
    
    def get_repository(self, model_name: str) -> Optional[Repository]:
        """Repository 조회"""
        return self.repositories.get(model_name)
    
    def get_all_repositories(self) -> Dict[str, Repository]:
        """모든 Repository 반환"""
        return self.repositories.copy()


# 전역 Repository 레지스트리
def get_repository_registry() -> RepositoryRegistry:
    """Repository 레지스트리 인스턴스 반환"""
    return RepositoryRegistry()


# 편의 함수들
def repository(
    model_class: Type[BaseModel] = None,
    repository_class: Type[Repository] = None,
    config: RepositoryConfig = None
):
    """Repository 데코레이터"""
    def decorator(cls_or_func):
        if inspect.isclass(cls_or_func) and issubclass(cls_or_func, Repository):
            # Repository 클래스 데코레이터
            if model_class:
                registry = get_repository_registry()
                registry.register_repository(model_class, cls_or_func, config)
            return cls_or_func
        else:
            # 함수 데코레이터 (미지원)
            raise ValueError("Repository 데코레이터는 클래스에만 사용할 수 있습니다")
    
    return decorator


def get_repository(model_class_or_name: Union[Type[BaseModel], str]) -> Optional[Repository]:
    """Repository 조회"""
    registry = get_repository_registry()
    
    if isinstance(model_class_or_name, str):
        return registry.get_repository(model_class_or_name)
    else:
        model_name = model_class_or_name.__name__
        return registry.get_repository(model_name)


def create_repository(
    model_class: Type[BaseModel],
    repository_class: Type[Repository] = None,
    config: RepositoryConfig = None
) -> Repository:
    """Repository 생성 및 등록"""
    registry = get_repository_registry()
    registry.register_repository(model_class, repository_class, config)
    return registry.get_repository(model_class.__name__)