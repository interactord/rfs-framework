"""
Repository 모듈 커버리지 향상을 위한 집중 테스트

RFS Framework Database Repository 시스템의 미커버 코드 라인들을 테스트
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rfs.core.result import Failure, Success
from rfs.database.query import Sort, SortOrder
from rfs.database.repository import (
    BaseRepository,
    CRUDRepository,
    Repository,
    RepositoryConfig,
    RepositoryRegistry,
    create_repository,
    get_repository,
    get_repository_registry,
    repository,
)


class MockModel:
    """테스트용 Mock 모델"""

    __name__ = "MockModel"
    __fields__ = {
        "id": Mock(primary_key=True),
        "name": Mock(primary_key=False),
        "email": Mock(primary_key=False),
    }

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def update_from_dict(self, data: Dict[str, Any]):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    async def save(self):
        return Success(self)

    async def delete(self):
        return Success(None)

    @classmethod
    async def get(cls, **filters):
        if "id" in filters and filters["id"] == 999:
            return Success(None)  # Not found
        return Success(cls(**filters))

    @classmethod
    async def filter(cls, **filters):
        return Success([cls(id=1, name="Test"), cls(id=2, name="Test2")])


class TestRepositoryConfig:
    """RepositoryConfig 테스트"""

    def test_default_config(self):
        """기본 설정 테스트"""
        config = RepositoryConfig()

        assert config.auto_commit is True
        assert config.batch_size == 100
        assert config.cache_enabled is True
        assert config.cache_ttl == 3600
        assert config.retry_count == 3
        assert config.timeout == 30

    def test_custom_config(self):
        """커스텀 설정 테스트"""
        config = RepositoryConfig(
            auto_commit=False,
            batch_size=50,
            cache_enabled=False,
            cache_ttl=1800,
            retry_count=5,
            timeout=60,
        )

        assert config.auto_commit is False
        assert config.batch_size == 50
        assert config.cache_enabled is False
        assert config.cache_ttl == 1800
        assert config.retry_count == 5
        assert config.timeout == 60


class TestBaseRepository:
    """BaseRepository 테스트"""

    @pytest.fixture
    def config(self):
        return RepositoryConfig(batch_size=50, timeout=60)

    @pytest.fixture
    def repository(self, config):
        return BaseRepository(MockModel, config)

    def test_repository_initialization(self, repository, config):
        """Repository 초기화 테스트"""
        assert repository.model_class == MockModel
        assert repository.config == config
        assert repository.model_name == "MockModel"

    def test_repository_with_default_config(self):
        """기본 설정으로 Repository 초기화"""
        repo = BaseRepository(MockModel)

        assert repo.model_class == MockModel
        assert isinstance(repo.config, RepositoryConfig)
        assert repo.model_name == "MockModel"

    @pytest.mark.asyncio
    async def test_create_success(self, repository):
        """모델 생성 성공 테스트"""
        data = {"name": "John", "email": "john@example.com"}

        result = await repository.create(data)

        assert result.is_success()
        model = result.unwrap()
        assert model.name == "John"
        assert model.email == "john@example.com"

    @pytest.mark.asyncio
    async def test_create_save_failure(self, repository):
        """모델 저장 실패 테스트"""
        data = {"name": "John"}

        # Mock save to return failure
        with patch.object(MockModel, "save", return_value=Failure("Save error")):
            result = await repository.create(data)

            assert not result.is_success()
            assert "모델 저장 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_create_exception(self, repository):
        """모델 생성 중 예외 발생"""
        data = {"name": "John"}

        # Mock model creation to raise exception
        with patch.object(
            MockModel, "__init__", side_effect=Exception("Creation error")
        ):
            result = await repository.create(data)

            assert not result.is_success()
            assert "모델 생성 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repository):
        """ID로 조회 성공 테스트"""
        result = await repository.get_by_id(1)

        assert result.is_success()
        model = result.unwrap()
        assert model.id == 1

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """ID로 조회 시 결과 없음"""
        result = await repository.get_by_id(999)  # MockModel에서 None 반환

        assert result.is_success()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_get_by_id_exception(self, repository):
        """ID로 조회 중 예외 발생"""
        with patch.object(MockModel, "get", side_effect=Exception("Get error")):
            result = await repository.get_by_id(1)

            assert not result.is_success()
            assert "모델 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_get_by_id_with_custom_pk_field(self, repository):
        """커스텀 기본키 필드로 조회"""

        # Mock model with custom primary key
        class CustomModel:
            __name__ = "CustomModel"
            __fields__ = {
                "uuid": Mock(primary_key=True),
                "name": Mock(primary_key=False),
            }

            @classmethod
            async def get(cls, **filters):
                return Success(cls())

        repo = BaseRepository(CustomModel)
        result = await repo.get_by_id("custom-uuid")

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_update_success(self, repository):
        """모델 업데이트 성공 테스트"""
        update_data = {"name": "Updated Name"}

        result = await repository.update(1, update_data)

        assert result.is_success()
        model = result.unwrap()
        assert hasattr(model, "name")

    @pytest.mark.asyncio
    async def test_update_not_found(self, repository):
        """업데이트할 모델이 없음"""
        update_data = {"name": "Updated Name"}

        result = await repository.update(999, update_data)  # MockModel에서 None 반환

        assert not result.is_success()
        assert "모델을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_update_get_failure(self, repository):
        """업데이트 시 조회 실패"""
        update_data = {"name": "Updated Name"}

        with patch.object(repository, "get_by_id", return_value=Failure("Get failed")):
            result = await repository.update(1, update_data)

            assert not result.is_success()
            assert "Get failed" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_update_save_failure(self, repository):
        """업데이트 저장 실패"""
        update_data = {"name": "Updated Name"}

        with patch.object(MockModel, "save", return_value=Failure("Save failed")):
            result = await repository.update(1, update_data)

            assert not result.is_success()
            assert "모델 업데이트 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_update_exception(self, repository):
        """업데이트 중 예외 발생"""
        update_data = {"name": "Updated Name"}

        with patch.object(
            repository, "get_by_id", side_effect=Exception("Update error")
        ):
            result = await repository.update(1, update_data)

            assert not result.is_success()
            assert "모델 업데이트 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_delete_success(self, repository):
        """모델 삭제 성공 테스트"""
        result = await repository.delete(1)

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, repository):
        """삭제할 모델이 없음"""
        result = await repository.delete(999)  # MockModel에서 None 반환

        assert not result.is_success()
        assert "모델을 찾을 수 없습니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_delete_get_failure(self, repository):
        """삭제 시 조회 실패"""
        with patch.object(repository, "get_by_id", return_value=Failure("Get failed")):
            result = await repository.delete(1)

            assert not result.is_success()

    @pytest.mark.asyncio
    async def test_delete_model_failure(self, repository):
        """모델 삭제 실패"""
        with patch.object(MockModel, "delete", return_value=Failure("Delete failed")):
            result = await repository.delete(1)

            assert not result.is_success()
            assert "모델 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_delete_exception(self, repository):
        """삭제 중 예외 발생"""
        with patch.object(
            repository, "get_by_id", side_effect=Exception("Delete error")
        ):
            result = await repository.delete(1)

            assert not result.is_success()
            assert "모델 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_find_success(self, repository):
        """모델 목록 조회 성공"""
        filters = {"status": "active"}

        result = await repository.find(filters, limit=10, offset=0)

        assert result.is_success()
        models = result.unwrap()
        assert len(models) == 2

    @pytest.mark.asyncio
    async def test_find_query_failure(self, repository):
        """모델 목록 조회 시 쿼리 실패"""
        # Mock query builder execute to fail
        with patch.object(
            repository._query_builder, "execute", return_value=Failure("Query failed")
        ):
            result = await repository.find()

            assert not result.is_success()
            assert "모델 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_find_exception(self, repository):
        """모델 목록 조회 중 예외"""
        with patch.object(
            repository._query_builder, "where", side_effect=Exception("Find error")
        ):
            result = await repository.find({"name": "test"})

            assert not result.is_success()
            assert "모델 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_count_success(self, repository):
        """모델 개수 조회 성공"""
        result = await repository.count()

        assert result.is_success()
        count = result.unwrap()
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_count_with_filters(self, repository):
        """필터와 함께 개수 조회"""
        filters = {"status": "active"}

        result = await repository.count(filters)

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_count_query_failure(self, repository):
        """개수 조회 쿼리 실패"""
        with patch.object(
            repository._query_builder, "execute", return_value=Failure("Count failed")
        ):
            result = await repository.count()

            assert not result.is_success()
            assert "개수 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_count_exception(self, repository):
        """개수 조회 중 예외"""
        with patch.object(
            repository._query_builder, "count", side_effect=Exception("Count error")
        ):
            result = await repository.count()

            assert not result.is_success()
            assert "개수 조회 실패" in result.unwrap_error()


class TestCRUDRepository:
    """CRUDRepository 테스트"""

    @pytest.fixture
    def repository(self):
        config = RepositoryConfig(batch_size=2)  # 작은 배치 사이즈로 테스트
        return CRUDRepository(MockModel, config)

    @pytest.mark.asyncio
    async def test_bulk_create_success(self, repository):
        """대량 생성 성공 테스트"""
        data_list = [
            {"name": "User1", "email": "user1@example.com"},
            {"name": "User2", "email": "user2@example.com"},
            {"name": "User3", "email": "user3@example.com"},
        ]

        result = await repository.bulk_create(data_list)

        assert result.is_success()
        models = result.unwrap()
        assert len(models) == 3

    @pytest.mark.asyncio
    async def test_bulk_create_failure(self, repository):
        """대량 생성 중 실패"""
        data_list = [{"name": "User1"}, {"name": "User2"}]

        with patch.object(repository, "create", return_value=Failure("Create failed")):
            result = await repository.bulk_create(data_list)

            assert not result.is_success()
            assert "배치 생성 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_bulk_create_exception(self, repository):
        """대량 생성 중 예외"""
        data_list = [{"name": "User1"}]

        with patch.object(repository, "create", side_effect=Exception("Create error")):
            result = await repository.bulk_create(data_list)

            assert not result.is_success()
            assert "대량 생성 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_bulk_update_success(self, repository):
        """대량 업데이트 성공 테스트"""
        updates = [
            {"id": 1, "name": "Updated1"},
            {"id": 2, "name": "Updated2"},
            {"id": 3, "name": "Updated3"},
        ]

        result = await repository.bulk_update(updates)

        assert result.is_success()
        models = result.unwrap()
        assert len(models) == 3

    @pytest.mark.asyncio
    async def test_bulk_update_missing_id(self, repository):
        """대량 업데이트 시 ID 누락"""
        updates = [{"name": "Updated"}]  # id 없음

        result = await repository.bulk_update(updates)

        assert not result.is_success()
        assert "업데이트 데이터에 id가 필요합니다" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_bulk_update_failure(self, repository):
        """대량 업데이트 중 실패"""
        updates = [{"id": 1, "name": "Updated"}]

        with patch.object(repository, "update", return_value=Failure("Update failed")):
            result = await repository.bulk_update(updates)

            assert not result.is_success()
            assert "배치 업데이트 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_bulk_update_exception(self, repository):
        """대량 업데이트 중 예외"""
        updates = [{"id": 1, "name": "Updated"}]

        with patch.object(repository, "update", side_effect=Exception("Update error")):
            result = await repository.bulk_update(updates)

            assert not result.is_success()
            assert "대량 업데이트 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_bulk_delete_success(self, repository):
        """대량 삭제 성공 테스트"""
        ids = [1, 2, 3]

        result = await repository.bulk_delete(ids)

        assert result.is_success()

    @pytest.mark.asyncio
    async def test_bulk_delete_failure(self, repository):
        """대량 삭제 중 실패"""
        ids = [1, 2]

        with patch.object(repository, "delete", return_value=Failure("Delete failed")):
            result = await repository.bulk_delete(ids)

            assert not result.is_success()
            assert "배치 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_bulk_delete_exception(self, repository):
        """대량 삭제 중 예외"""
        ids = [1]

        with patch.object(repository, "delete", side_effect=Exception("Delete error")):
            result = await repository.bulk_delete(ids)

            assert not result.is_success()
            assert "대량 삭제 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_find_paginated_success(self, repository):
        """페이지네이션 조회 성공"""
        with patch.object(repository, "count", return_value=Success(25)):
            result = await repository.find_paginated(
                page=2,
                page_size=10,
                filters={"status": "active"},
                sort=[Sort("created_at", SortOrder.DESC)],
            )

            assert result.is_success()
            data = result.unwrap()
            assert "data" in data
            assert "pagination" in data

            pagination = data["pagination"]
            assert pagination["page"] == 2
            assert pagination["page_size"] == 10
            assert pagination["total_count"] == 25
            assert pagination["total_pages"] == 3
            assert pagination["has_next"] is True
            assert pagination["has_prev"] is True

    @pytest.mark.asyncio
    async def test_find_paginated_first_page(self, repository):
        """페이지네이션 첫 페이지"""
        with patch.object(repository, "count", return_value=Success(5)):
            result = await repository.find_paginated(page=1, page_size=10)

            assert result.is_success()
            data = result.unwrap()
            pagination = data["pagination"]
            assert pagination["has_prev"] is False
            assert pagination["has_next"] is False

    @pytest.mark.asyncio
    async def test_find_paginated_query_failure(self, repository):
        """페이지네이션 쿼리 실패"""
        with patch.object(
            repository._query_builder, "execute", return_value=Failure("Query failed")
        ):
            result = await repository.find_paginated()

            assert not result.is_success()
            assert "페이지네이션 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_find_paginated_count_failure(self, repository):
        """페이지네이션 개수 조회 실패"""
        with patch.object(repository, "count", return_value=Failure("Count failed")):
            result = await repository.find_paginated()

            assert not result.is_success()
            assert "개수 조회 실패" in result.unwrap_error()

    @pytest.mark.asyncio
    async def test_find_paginated_exception(self, repository):
        """페이지네이션 중 예외"""
        with patch.object(
            repository._query_builder,
            "where",
            side_effect=Exception("Pagination error"),
        ):
            result = await repository.find_paginated(filters={"name": "test"})

            assert not result.is_success()
            assert "페이지네이션 조회 실패" in result.unwrap_error()


class TestRepositoryRegistry:
    """RepositoryRegistry 테스트"""

    @pytest.fixture
    def registry(self):
        # 새로운 레지스트리 인스턴스 생성
        registry = RepositoryRegistry()
        registry.repositories = {}
        registry.configs = {}
        return registry

    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        registry1 = RepositoryRegistry()
        registry2 = RepositoryRegistry()

        assert registry1 is registry2

    def test_register_repository_default(self, registry):
        """기본 Repository 등록"""
        registry.register_repository(MockModel)

        assert "MockModel" in registry.repositories
        repository = registry.repositories["MockModel"]
        assert isinstance(repository, CRUDRepository)
        assert repository.model_class == MockModel

    def test_register_repository_with_custom_class(self, registry):
        """커스텀 Repository 클래스로 등록"""
        custom_config = RepositoryConfig(batch_size=50)

        registry.register_repository(MockModel, BaseRepository, custom_config)

        assert "MockModel" in registry.repositories
        repository = registry.repositories["MockModel"]
        assert isinstance(repository, BaseRepository)
        assert "MockModel" in registry.configs
        assert registry.configs["MockModel"] == custom_config

    def test_get_repository_existing(self, registry):
        """기존 Repository 조회"""
        registry.register_repository(MockModel)

        repository = registry.get_repository("MockModel")

        assert repository is not None
        assert isinstance(repository, CRUDRepository)

    def test_get_repository_not_found(self, registry):
        """존재하지 않는 Repository 조회"""
        repository = registry.get_repository("NonExistentModel")

        assert repository is None

    def test_get_all_repositories(self, registry):
        """모든 Repository 조회"""
        registry.register_repository(MockModel)

        all_repos = registry.get_all_repositories()

        assert len(all_repos) == 1
        assert "MockModel" in all_repos
        assert isinstance(all_repos, dict)


class TestGlobalFunctions:
    """전역 함수 테스트"""

    def test_get_repository_registry_singleton(self):
        """get_repository_registry 싱글톤 테스트"""
        registry1 = get_repository_registry()
        registry2 = get_repository_registry()

        assert registry1 is registry2
        assert isinstance(registry1, RepositoryRegistry)

    def test_get_repository_by_name(self):
        """이름으로 Repository 조회"""
        # Registry에 Repository 등록
        registry = get_repository_registry()
        registry.register_repository(MockModel)

        repository = get_repository("MockModel")

        assert repository is not None
        assert isinstance(repository, Repository)

    def test_get_repository_by_class(self):
        """클래스로 Repository 조회"""
        # Registry에 Repository 등록
        registry = get_repository_registry()
        registry.register_repository(MockModel)

        repository = get_repository(MockModel)

        assert repository is not None
        assert isinstance(repository, Repository)

    def test_create_repository_function(self):
        """create_repository 함수 테스트"""
        config = RepositoryConfig(batch_size=25)

        repository = create_repository(MockModel, BaseRepository, config)

        assert repository is not None
        assert isinstance(repository, BaseRepository)
        assert repository.config.batch_size == 25

    def test_create_repository_default_class(self):
        """기본 클래스로 Repository 생성"""
        repository = create_repository(MockModel)

        assert repository is not None
        assert isinstance(repository, CRUDRepository)


class TestRepositoryDecorator:
    """Repository 데코레이터 테스트"""

    def test_repository_decorator_on_class(self):
        """클래스에 repository 데코레이터 적용"""

        @repository(MockModel)
        class CustomRepository(BaseRepository):
            pass

        # Registry에서 확인
        registry = get_repository_registry()
        repo = registry.get_repository("MockModel")

        assert repo is not None
        assert isinstance(repo, CustomRepository)

    def test_repository_decorator_invalid_target(self):
        """잘못된 대상에 데코레이터 적용"""
        with pytest.raises(
            ValueError, match="Repository 데코레이터는 클래스에만 사용할 수 있습니다"
        ):

            @repository(MockModel)
            def invalid_function():
                pass

    def test_repository_decorator_without_model(self):
        """모델 클래스 없이 데코레이터 적용"""

        @repository()
        class TestRepository(BaseRepository):
            pass

        # 모델이 없으면 등록되지 않음
        assert isinstance(TestRepository, type)


class TestRepositoryEdgeCases:
    """Repository 엣지 케이스 테스트"""

    def test_repository_with_none_config(self):
        """None config로 Repository 생성"""
        repo = BaseRepository(MockModel, None)

        assert repo.config is not None
        assert isinstance(repo.config, RepositoryConfig)

    @pytest.mark.asyncio
    async def test_crud_operations_integration(self):
        """CRUD 작업 통합 테스트"""
        repo = CRUDRepository(MockModel)

        # Create
        create_result = await repo.create({"name": "Test User"})
        assert create_result.is_success()

        # Read
        read_result = await repo.get_by_id(1)
        assert read_result.is_success()

        # Update
        update_result = await repo.update(1, {"name": "Updated User"})
        assert update_result.is_success()

        # Delete
        delete_result = await repo.delete(1)
        assert delete_result.is_success()

    def test_repository_model_name_extraction(self):
        """Repository에서 모델 이름 추출 테스트"""

        class CustomModelName:
            __name__ = "CustomModelName"

        repo = BaseRepository(CustomModelName)

        assert repo.model_name == "CustomModelName"

    @pytest.mark.asyncio
    async def test_bulk_operations_with_different_batch_sizes(self):
        """다양한 배치 크기로 대량 작업 테스트"""
        # 배치 크기 1로 설정
        config = RepositoryConfig(batch_size=1)
        repo = CRUDRepository(MockModel, config)

        data_list = [{"name": f"User{i}"} for i in range(3)]

        result = await repo.bulk_create(data_list)

        assert result.is_success()
        models = result.unwrap()
        assert len(models) == 3

    def test_registry_model_name_handling(self):
        """Registry에서 모델 이름 처리 테스트"""
        registry = get_repository_registry()

        # 다른 이름의 모델들 등록
        class ModelA:
            __name__ = "ModelA"

        class ModelB:
            __name__ = "ModelB"

        registry.register_repository(ModelA)
        registry.register_repository(ModelB)

        assert registry.get_repository("ModelA") is not None
        assert registry.get_repository("ModelB") is not None
        assert registry.get_repository("ModelC") is None
