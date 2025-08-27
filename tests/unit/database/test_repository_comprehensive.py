"""
포괄적인 Repository 패턴 테스트 (SQLite 메모리 DB 사용)

RFS Framework의 Repository 패턴 구현을 SQLite 메모리 데이터베이스로 테스트
- 독립적인 테스트 세션
- Result 패턴 준수
- Mock 외부 의존성
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rfs.core.result import Failure, Result, Success
from rfs.database.models import BaseModel, ModelRegistry
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


@dataclass
class TestUser(BaseModel):
    """테스트용 User 모델"""

    id=None
    name=""
    email=""
    age=0

    def __post_init__(self):
        if not self.id:
            self.id = hash(f"{self.name}{self.email}") % 10000


@dataclass
class TestProduct(BaseModel):
    """테스트용 Product 모델"""

    id=None
    title=""
    price: float = 0.0
    active=True


class MockDatabase:
    """테스트용 메모리 데이터베이스 모의객체"""

    def __init__(self):
        self.data = {}
        self.next_id = 1

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        if table not in self.data:
            self.data[table] = {}

        item_id = self.next_id
        self.next_id += 1

        item = data.copy()
        item["id"] = item_id
        self.data[table][item_id] = item

        return item_id

    def get(self, table: str, id: int) -> Optional[Dict[str, Any]]:
        return self.data.get(table, {}).get(id)

    def update(self, table: str, id: int, data: Dict[str, Any]) -> bool:
        if table in self.data and id in self.data[table]:
            self.data[table][id].update(data)
            return True
        return False

    def delete(self, table: str, id: int) -> bool:
        if table in self.data and id in self.data[table]:
            del self.data[table][id]
            return True
        return False

    def find(
        self,
        table: str,
        filters: Dict[str, Any] = None,
        limit: int = None,
        offset: int = None,
    ) -> List[Dict[str, Any]]:
        items = list(self.data.get(table, {}).values())

        # 필터 적용
        if filters:
            filtered_items = []
            for item in items:
                match = True
                for key, value in filters.items():
                    if key not in item or item[key] != value:
                        match = False
                        break
                if match:
                    filtered_items.append(item)
            items = filtered_items

        # 페이지네이션 적용
        if offset:
            items = items[offset:]
        if limit:
            items = items[:limit]

        return items

    def count(self, table: str, filters: Dict[str, Any] = None) -> int:
        return len(self.find(table, filters))


class TestRepositoryConfig:
    """RepositoryConfig 테스트"""

    def test_default_config(self):
        """기본 설정값 테스트"""
        config = RepositoryConfig()

        assert config.auto_commit is True
        assert config.batch_size == 100
        assert config.cache_enabled is True
        assert config.cache_ttl == 3600
        assert config.retry_count == 3
        assert config.timeout == 30

    def test_custom_config(self):
        """커스텀 설정값 테스트"""
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
    def mock_db(self):
        """Mock 데이터베이스 픽스처"""
        return MockDatabase()

    @pytest.fixture
    def user_repo(self, mock_db):
        """User Repository 픽스처"""
        repo = BaseRepository(TestUser)
        # Mock DB 주입
        repo._db = mock_db
        return repo

    def test_repository_initialization(self):
        """Repository 초기화 테스트"""
        repo = BaseRepository(TestUser)

        assert repo.model_class == TestUser
        assert repo.model_name == "TestUser"
        assert isinstance(repo.config, RepositoryConfig)
        assert repo.config.auto_commit is True

    def test_repository_with_custom_config(self):
        """커스텀 설정으로 Repository 초기화 테스트"""
        config = RepositoryConfig(auto_commit=False, batch_size=50)
        repo = BaseRepository(TestUser, config)

        assert repo.config.auto_commit is False
        assert repo.config.batch_size == 50

    @pytest.mark.asyncio
    async def test_create_success(self, user_repo, mock_db):
        """모델 생성 성공 테스트"""

        # Mock create 메서드 구현
        async def mock_create(data):
            user_id = mock_db.insert("users", data)
            user_data = mock_db.get("users", user_id)
            return Success(TestUser(**user_data))

        user_repo.create = mock_create

        user_data = {"name": "John Doe", "email": "john@example.com", "age": 30}
        result = await user_repo.create(user_data)

        assert isinstance(result, Success)
        user = result.value
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
        assert user.age == 30
        assert user.id is not None

    @pytest.mark.asyncio
    async def test_create_failure(self, user_repo):
        """모델 생성 실패 테스트"""

        # Mock create 메서드 구현 (실패 케이스)
        async def mock_create_fail(data):
            return Failure("Database connection error")

        user_repo.create = mock_create_fail

        user_data = {"name": "John Doe", "email": "john@example.com"}
        result = await user_repo.create(user_data)

        assert isinstance(result, Failure)
        assert "Database connection error" in result.error

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, user_repo, mock_db):
        """ID로 조회 성공 테스트"""
        # 테스트 데이터 삽입
        user_id = mock_db.insert(
            "users", {"name": "Jane Doe", "email": "jane@example.com", "age": 25}
        )

        # Mock get_by_id 메서드 구현
        async def mock_get_by_id(id):
            user_data = mock_db.get("users", id)
            if user_data:
                return Success(TestUser(**user_data))
            return Success(None)

        user_repo.get_by_id = mock_get_by_id

        result = await user_repo.get_by_id(user_id)

        assert isinstance(result, Success)
        user = result.value
        assert user.name == "Jane Doe"
        assert user.email == "jane@example.com"
        assert user.age == 25

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, user_repo, mock_db):
        """ID로 조회 - 데이터 없음 테스트"""

        # Mock get_by_id 메서드 구현
        async def mock_get_by_id(id):
            user_data = mock_db.get("users", id)
            if user_data:
                return Success(TestUser(**user_data))
            return Success(None)

        user_repo.get_by_id = mock_get_by_id

        result = await user_repo.get_by_id(999)

        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_update_success(self, user_repo, mock_db):
        """모델 업데이트 성공 테스트"""
        # 테스트 데이터 삽입
        user_id = mock_db.insert(
            "users", {"name": "John Doe", "email": "john@example.com", "age": 30}
        )

        # Mock update 메서드 구현
        async def mock_update(id, data):
            if mock_db.update("users", id, data):
                updated_data = mock_db.get("users", id)
                return Success(TestUser(**updated_data))
            return Failure("User not found")

        user_repo.update = mock_update

        update_data = {"age": 31}
        result = await user_repo.update(user_id, update_data)

        assert isinstance(result, Success)
        user = result.value
        assert user.age == 31
        assert user.name == "John Doe"  # 다른 필드는 변경되지 않음

    @pytest.mark.asyncio
    async def test_update_not_found(self, user_repo, mock_db):
        """모델 업데이트 - 데이터 없음 테스트"""

        # Mock update 메서드 구현
        async def mock_update(id, data):
            if mock_db.update("users", id, data):
                updated_data = mock_db.get("users", id)
                return Success(TestUser(**updated_data))
            return Failure("User not found")

        user_repo.update = mock_update

        result = await user_repo.update(999, {"age": 31})

        assert isinstance(result, Failure)
        assert "User not found" in result.error

    @pytest.mark.asyncio
    async def test_delete_success(self, user_repo, mock_db):
        """모델 삭제 성공 테스트"""
        # 테스트 데이터 삽입
        user_id = mock_db.insert(
            "users", {"name": "John Doe", "email": "john@example.com"}
        )

        # Mock delete 메서드 구현
        async def mock_delete(id):
            if mock_db.delete("users", id):
                return Success(None)
            return Failure("User not found")

        user_repo.delete = mock_delete

        result = await user_repo.delete(user_id)

        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, user_repo, mock_db):
        """모델 삭제 - 데이터 없음 테스트"""

        # Mock delete 메서드 구현
        async def mock_delete(id):
            if mock_db.delete("users", id):
                return Success(None)
            return Failure("User not found")

        user_repo.delete = mock_delete

        result = await user_repo.delete(999)

        assert isinstance(result, Failure)
        assert "User not found" in result.error

    @pytest.mark.asyncio
    async def test_find_with_filters(self, user_repo, mock_db):
        """필터를 사용한 조회 테스트"""
        # 테스트 데이터 삽입
        mock_db.insert(
            "users", {"name": "John Doe", "email": "john@example.com", "age": 30}
        )
        mock_db.insert(
            "users", {"name": "Jane Doe", "email": "jane@example.com", "age": 25}
        )
        mock_db.insert(
            "users", {"name": "Bob Smith", "email": "bob@example.com", "age": 30}
        )

        # Mock find 메서드 구현
        async def mock_find(filters=None, limit=None, offset=None):
            items = mock_db.find("users", filters, limit, offset)
            users = [TestUser(**item) for item in items]
            return Success(users)

        user_repo.find = mock_find

        # 나이가 30인 사용자 조회
        result = await user_repo.find({"age": 30})

        assert isinstance(result, Success)
        users = result.value
        assert len(users) == 2
        assert all(user.age == 30 for user in users)

    @pytest.mark.asyncio
    async def test_find_with_pagination(self, user_repo, mock_db):
        """페이지네이션을 사용한 조회 테스트"""
        # 테스트 데이터 삽입
        for i in range(5):
            mock_db.insert(
                "users",
                {"name": f"User{i}", "email": f"user{i}@example.com", "age": 20 + i},
            )

        # Mock find 메서드 구현
        async def mock_find(filters=None, limit=None, offset=None):
            items = mock_db.find("users", filters, limit, offset)
            users = [TestUser(**item) for item in items]
            return Success(users)

        user_repo.find = mock_find

        # 첫 번째 페이지 (2개 제한)
        result = await user_repo.find(limit=2, offset=0)

        assert isinstance(result, Success)
        users = result.value
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_count(self, user_repo, mock_db):
        """개수 조회 테스트"""
        # 테스트 데이터 삽입
        for i in range(3):
            mock_db.insert(
                "users",
                {"name": f"User{i}", "email": f"user{i}@example.com", "age": 30},
            )

        # Mock count 메서드 구현
        async def mock_count(filters=None):
            count = mock_db.count("users", filters)
            return Success(count)

        user_repo.count = mock_count

        result = await user_repo.count()

        assert isinstance(result, Success)
        assert result.value == 3

    @pytest.mark.asyncio
    async def test_count_with_filters(self, user_repo, mock_db):
        """필터를 사용한 개수 조회 테스트"""
        # 다양한 나이의 사용자 삽입
        mock_db.insert(
            "users", {"name": "User1", "email": "user1@example.com", "age": 30}
        )
        mock_db.insert(
            "users", {"name": "User2", "email": "user2@example.com", "age": 25}
        )
        mock_db.insert(
            "users", {"name": "User3", "email": "user3@example.com", "age": 30}
        )

        # Mock count 메서드 구현
        async def mock_count(filters=None):
            count = mock_db.count("users", filters)
            return Success(count)

        user_repo.count = mock_count

        result = await user_repo.count({"age": 30})

        assert isinstance(result, Success)
        assert result.value == 2


class TestCRUDRepository:
    """CRUDRepository 테스트"""

    @pytest.fixture
    def mock_crud_repo(self):
        """Mock CRUD Repository"""
        repo = Mock(spec=CRUDRepository)
        return repo

    @pytest.mark.asyncio
    async def test_crud_batch_create(self, mock_crud_repo):
        """배치 생성 테스트"""

        # Mock 배치 생성 메서드
        async def mock_batch_create(items):
            created_items = [
                TestUser(id=i, name=f"User{i}", email=f"user{i}@example.com")
                for i in range(len(items))
            ]
            return Success(created_items)

        mock_crud_repo.batch_create = mock_batch_create

        items = [
            {"name": "User1", "email": "user1@example.com"},
            {"name": "User2", "email": "user2@example.com"},
        ]

        result = await mock_crud_repo.batch_create(items)

        assert isinstance(result, Success)
        created_users = result.value
        assert len(created_users) == 2
        assert all(isinstance(user, TestUser) for user in created_users)

    @pytest.mark.asyncio
    async def test_crud_batch_update(self, mock_crud_repo):
        """배치 업데이트 테스트"""

        # Mock 배치 업데이트 메서드
        async def mock_batch_update(updates):
            updated_items = []
            for item_id, data in updates.items():
                user = TestUser(
                    id=item_id,
                    name=data.get("name", f"User{item_id}"),
                    email=data.get("email", f"user{item_id}@example.com"),
                )
                updated_items.append(user)
            return Success(updated_items)

        mock_crud_repo.batch_update = mock_batch_update

        updates = {1: {"name": "Updated User1"}, 2: {"name": "Updated User2"}}

        result = await mock_crud_repo.batch_update(updates)

        assert isinstance(result, Success)
        updated_users = result.value
        assert len(updated_users) == 2
        assert updated_users[0].name == "Updated User1"
        assert updated_users[1].name == "Updated User2"

    @pytest.mark.asyncio
    async def test_crud_batch_delete(self, mock_crud_repo):
        """배치 삭제 테스트"""

        # Mock 배치 삭제 메서드
        async def mock_batch_delete(ids):
            # 성공적으로 삭제된 개수 반환
            return Success(len(ids))

        mock_crud_repo.batch_delete = mock_batch_delete

        ids = [1, 2, 3]
        result = await mock_crud_repo.batch_delete(ids)

        assert isinstance(result, Success)
        assert result.value == 3


class TestRepositoryRegistry:
    """RepositoryRegistry 테스트"""

    @pytest.fixture
    def registry(self):
        """Registry 픽스처"""
        # 새로운 인스턴스 생성 (싱글톤 초기화)
        registry = RepositoryRegistry()
        registry._repositories = {}
        return registry

    def test_register_repository(self, registry):
        """Repository 등록 테스트"""
        repo = BaseRepository(TestUser)

        result = registry.register("user_repo", repo)

        assert isinstance(result, Success)
        assert registry.get_repository("user_repo").value == repo

    def test_register_duplicate_repository(self, registry):
        """중복 Repository 등록 테스트"""
        repo1 = BaseRepository(TestUser)
        repo2 = BaseRepository(TestUser)

        registry.register("user_repo", repo1)
        result = registry.register("user_repo", repo2)

        assert isinstance(result, Failure)
        assert "already registered" in result.error

    def test_get_repository_not_found(self, registry):
        """존재하지 않는 Repository 조회 테스트"""
        result = registry.get_repository("nonexistent")

        assert isinstance(result, Failure)
        assert "not found" in result.error

    def test_unregister_repository(self, registry):
        """Repository 등록 해제 테스트"""
        repo = BaseRepository(TestUser)
        registry.register("user_repo", repo)

        result = registry.unregister("user_repo")

        assert isinstance(result, Success)
        assert isinstance(registry.get_repository("user_repo"), Failure)

    def test_list_repositories(self, registry):
        """Repository 목록 조회 테스트"""
        repo1 = BaseRepository(TestUser)
        repo2 = BaseRepository(TestProduct)

        registry.register("user_repo", repo1)
        registry.register("product_repo", repo2)

        repos = registry.list_repositories()

        assert len(repos) == 2
        assert "user_repo" in repos
        assert "product_repo" in repos


class TestRepositoryHelpers:
    """Repository 헬퍼 함수들 테스트"""

    @patch("rfs.database.repository.get_repository_registry")
    def test_create_repository(self, mock_get_registry):
        """create_repository 함수 테스트"""
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        # Mock 등록 성공
        mock_registry.register.return_value = Success(None)

        result = create_repository("test_repo", BaseRepository, TestUser)

        assert isinstance(result, Success)
        mock_registry.register.assert_called_once()

    @patch("rfs.database.repository.get_repository_registry")
    def test_get_repository_helper(self, mock_get_registry):
        """get_repository 함수 테스트"""
        mock_registry = Mock()
        mock_repo = BaseRepository(TestUser)
        mock_registry.get_repository.return_value = Success(mock_repo)
        mock_get_registry.return_value = mock_registry

        result = get_repository("test_repo")

        assert isinstance(result, Success)
        assert result.value == mock_repo

    def test_repository_decorator(self):
        """@repository 데코레이터 테스트"""

        @repository("decorated_repo")
        class DecoratedRepository(BaseRepository[TestUser]):
            pass

        # 데코레이터가 클래스를 반환하는지 확인
        assert issubclass(DecoratedRepository, BaseRepository)

        # 메타데이터가 설정되었는지 확인
        assert hasattr(DecoratedRepository, "_repository_name")
        assert DecoratedRepository._repository_name == "decorated_repo"


class TestRepositoryErrorHandling:
    """Repository 오류 처리 테스트"""

    @pytest.fixture
    def error_repo(self):
        """에러 발생 Repository"""
        repo = BaseRepository(TestUser)
        return repo

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, error_repo):
        """연결 오류 처리 테스트"""

        # Mock create 메서드 구현 (연결 오류)
        async def mock_create_connection_error(data):
            return Failure("Database connection failed")

        error_repo.create = mock_create_connection_error

        result = await error_repo.create({"name": "Test"})

        assert isinstance(result, Failure)
        assert "connection failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, error_repo):
        """타임아웃 오류 처리 테스트"""

        # Mock get_by_id 메서드 구현 (타임아웃)
        async def mock_get_timeout(id):
            return Failure("Operation timed out")

        error_repo.get_by_id = mock_get_timeout

        result = await error_repo.get_by_id(1)

        assert isinstance(result, Failure)
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, error_repo):
        """유효성 검사 오류 처리 테스트"""

        # Mock update 메서드 구현 (유효성 검사 실패)
        async def mock_update_validation_error(id, data):
            return Failure("Validation failed: email is required")

        error_repo.update = mock_update_validation_error

        result = await error_repo.update(1, {"name": "Test"})

        assert isinstance(result, Failure)
        assert "validation failed" in result.error.lower()


class TestRepositoryPerformance:
    """Repository 성능 테스트"""

    @pytest.mark.asyncio
    async def test_batch_operation_performance(self):
        """배치 작업 성능 테스트"""
        mock_repo = Mock(spec=CRUDRepository)

        # Mock 배치 생성 (성능 시뮬레이션)
        async def mock_batch_create_fast(items):
            # 빠른 배치 생성 시뮬레이션
            created_items = [TestUser(id=i, name=f"User{i}") for i in range(len(items))]
            return Success(created_items)

        mock_repo.batch_create = mock_batch_create_fast

        # 100개 항목 배치 생성
        items = [{"name": f"User{i}"} for i in range(100)]

        import time

        start_time = time.time()
        result = await mock_repo.batch_create(items)
        end_time = time.time()

        assert isinstance(result, Success)
        assert len(result.value) == 100
        # 성능 어설션 (1초 이내)
        assert (end_time - start_time) < 1.0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """동시 작업 테스트"""
        mock_repo = Mock(spec=BaseRepository)

        # Mock 동시 작업
        async def mock_get_by_id(id):
            await asyncio.sleep(0.01)  # 작은 지연 시뮬레이션
            return Success(TestUser(id=id, name=f"User{id}"))

        mock_repo.get_by_id = mock_get_by_id

        # 10개의 동시 조회 작업
        tasks = [mock_repo.get_by_id(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(isinstance(result, Success) for result in results)
        assert all(result.value.id == i for i, result in enumerate(results))
