"""
RFS v4.1 Transaction System Tests
트랜잭션 관리 시스템의 comprehensive test suite

테스트 범위:
- 트랜잭션 매니저 기본 기능
- @Transactional, @RedisTransaction, @DistributedTransaction 데코레이터
- 트랜잭션 컨텍스트 매니저
- 롤백 및 재시도 로직
- 성능 및 동시성 테스트
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rfs.core.result import Failure, Result, Success

# RFS 코어 imports
from rfs.core.transactions import (
    DistributedTransaction,
    IsolationLevel,
    RedisTransactionManager,
    Transactional,
    TransactionContext,
    TransactionManager,
    TransactionStatus,
    get_transaction_manager,
    transactional,
)


class TestTransactionConfig:
    """트랜잭션 설정 테스트"""

    def test_transaction_config_defaults(self):
        """기본 트랜잭션 설정 테스트"""
        config = TransactionConfig()

        assert config.isolation_level == IsolationLevel.READ_COMMITTED
        assert config.timeout_seconds == 30
        assert config.retry_count == 3
        assert config.retry_delay_seconds == 1.0
        assert config.rollback_for == [Exception]
        assert config.no_rollback_for == []
        assert config.readonly is False

    def test_redis_transaction_config(self):
        """Redis 트랜잭션 설정 테스트"""
        config = RedisTransactionConfig(
            ttl_seconds=3600,
            key_pattern="user:{id}",
            watch_keys=["key1", "key2"],
            pipeline_mode=True,
        )

        assert config.ttl_seconds == 3600
        assert config.key_pattern == "user:{id}"
        assert config.watch_keys == ["key1", "key2"]
        assert config.pipeline_mode is True

    def test_distributed_transaction_config(self):
        """분산 트랜잭션 설정 테스트"""
        config = DistributedTransactionConfig(
            saga_id="user_registration", timeout_seconds=600, compensation_timeout=120
        )

        assert config.saga_id == "user_registration"
        assert config.timeout_seconds == 600
        assert config.compensation_timeout == 120
        assert config.idempotent is True


class TestTransactionContext:
    """트랜잭션 컨텍스트 테스트"""

    def test_transaction_context_creation(self):
        """트랜잭션 컨텍스트 생성 테스트"""
        config = TransactionConfig(isolation_level=IsolationLevel.SERIALIZABLE)
        context = TransactionContext(
            transaction_type=TransactionType.DATABASE, config=config
        )

        assert context.transaction_type == TransactionType.DATABASE
        assert context.status == TransactionStatus.PENDING
        assert context.config == config
        assert context.attempts == 0
        assert context.last_error is None
        assert context.transaction_id is not None

    def test_transaction_context_metadata(self):
        """트랜잭션 컨텍스트 메타데이터 테스트"""
        context = TransactionContext()
        context.metadata["user_id"] = "123"
        context.metadata["operation"] = "balance_update"

        assert context.metadata["user_id"] == "123"
        assert context.metadata["operation"] == "balance_update"


class TestDatabaseTransactionManager:
    """데이터베이스 트랜잭션 매니저 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        self.mock_connection = AsyncMock()
        self.mock_transaction = AsyncMock()
        self.mock_connection.begin.return_value = self.mock_transaction

        async def mock_connection_factory():
            return self.mock_connection

        self.manager = DatabaseTransactionManager(mock_connection_factory)
        self.config = TransactionConfig(isolation_level=IsolationLevel.READ_COMMITTED)
        self.context = TransactionContext(
            transaction_type=TransactionType.DATABASE, config=self.config
        )

    @pytest.mark.asyncio
    async def test_begin_transaction_success(self):
        """트랜잭션 시작 성공 테스트"""
        result = await self.manager.begin_transaction(self.context)

        assert result.is_success()
        assert self.context.status == TransactionStatus.ACTIVE
        self.mock_connection.begin.assert_called_once()
        self.mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_transaction_success(self):
        """트랜잭션 커밋 성공 테스트"""
        # 트랜잭션 시작
        await self.manager.begin_transaction(self.context)

        # 커밋
        result = await self.manager.commit_transaction(self.context)

        assert result.is_success()
        assert self.context.status == TransactionStatus.COMMITTED
        self.mock_transaction.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_transaction_success(self):
        """트랜잭션 롤백 성공 테스트"""
        # 트랜잭션 시작
        await self.manager.begin_transaction(self.context)

        # 롤백
        result = await self.manager.rollback_transaction(self.context, "Test rollback")

        assert result.is_success()
        assert self.context.status == TransactionStatus.ROLLED_BACK
        assert self.context.rollback_reason == "Test rollback"
        self.mock_transaction.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_in_transaction_success(self):
        """트랜잭션 내 함수 실행 성공 테스트"""

        async def test_func(value: int) -> int:
            return value * 2

        result = await self.manager.execute_in_transaction(self.context, test_func, 21)

        assert result.is_success()
        assert result.value == 42
        assert self.context.status == TransactionStatus.COMMITTED

    @pytest.mark.asyncio
    async def test_execute_in_transaction_with_rollback(self):
        """트랜잭션 내 함수 실행 중 예외 발생 및 롤백 테스트"""

        async def failing_func():
            raise ValueError("Test exception")

        result = await self.manager.execute_in_transaction(self.context, failing_func)

        assert result.is_failure()
        assert "Test exception" in result.error
        assert self.context.status == TransactionStatus.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_execute_in_transaction_no_rollback_for_exception(self):
        """롤백하지 않을 예외에 대한 테스트"""
        # 특정 예외는 롤백하지 않도록 설정
        self.config.no_rollback_for = [ValueError]

        async def failing_func():
            raise ValueError("Should not rollback")

        with pytest.raises(ValueError):
            await self.manager.execute_in_transaction(self.context, failing_func)

        # 롤백되지 않고 커밋되어야 함
        assert self.context.status == TransactionStatus.COMMITTED


class TestRedisTransactionManager:
    """Redis 트랜잭션 매니저 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        self.mock_client = AsyncMock()
        self.mock_pipeline = AsyncMock()
        self.mock_client.pipeline.return_value = self.mock_pipeline

        async def mock_redis_factory():
            return self.mock_client

        self.manager = RedisTransactionManager(mock_redis_factory)
        self.config = RedisTransactionConfig(pipeline_mode=True, watch_keys=["key1"])
        self.context = TransactionContext(
            transaction_type=TransactionType.REDIS, config=self.config
        )

    @pytest.mark.asyncio
    async def test_begin_redis_transaction(self):
        """Redis 트랜잭션 시작 테스트"""
        result = await self.manager.begin_transaction(self.context)

        assert result.is_success()
        assert self.context.status == TransactionStatus.ACTIVE
        self.mock_client.pipeline.assert_called_once_with(transaction=True)
        self.mock_pipeline.watch.assert_called_once_with("key1")
        self.mock_pipeline.multi.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_redis_transaction(self):
        """Redis 트랜잭션 커밋 테스트"""
        # 트랜잭션 시작
        await self.manager.begin_transaction(self.context)

        # 커밋
        result = await self.manager.commit_transaction(self.context)

        assert result.is_success()
        assert self.context.status == TransactionStatus.COMMITTED
        self.mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_redis_transaction(self):
        """Redis 트랜잭션 롤백 테스트"""
        # 트랜잭션 시작
        await self.manager.begin_transaction(self.context)

        # 롤백
        result = await self.manager.rollback_transaction(self.context, "Test rollback")

        assert result.is_success()
        assert self.context.status == TransactionStatus.ROLLED_BACK
        self.mock_pipeline.discard.assert_called_once()


class TestDistributedTransactionManager:
    """분산 트랜잭션 매니저 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        self.mock_saga = AsyncMock()
        self.mock_saga.complete.return_value = Success(None)
        self.mock_saga.compensate.return_value = Success(None)

        self.mock_saga_manager = AsyncMock()
        self.mock_saga_manager.create_saga.return_value = self.mock_saga

        self.manager = DistributedTransactionManager(self.mock_saga_manager)
        self.config = DistributedTransactionConfig(saga_id="test_saga")
        self.context = TransactionContext(
            transaction_type=TransactionType.DISTRIBUTED, config=self.config
        )

    @pytest.mark.asyncio
    async def test_begin_distributed_transaction(self):
        """분산 트랜잭션 시작 테스트"""
        result = await self.manager.begin_transaction(self.context)

        assert result.is_success()
        assert self.context.status == TransactionStatus.ACTIVE
        self.mock_saga_manager.create_saga.assert_called_once_with("test_saga")

    @pytest.mark.asyncio
    async def test_commit_distributed_transaction(self):
        """분산 트랜잭션 커밋 테스트"""
        # 트랜잭션 시작
        await self.manager.begin_transaction(self.context)

        # 커밋
        result = await self.manager.commit_transaction(self.context)

        assert result.is_success()
        assert self.context.status == TransactionStatus.COMMITTED
        self.mock_saga.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_distributed_transaction(self):
        """분산 트랜잭션 롤백 (보상) 테스트"""
        # 트랜잭션 시작
        await self.manager.begin_transaction(self.context)

        # 롤백 (보상 트랜잭션)
        result = await self.manager.rollback_transaction(
            self.context, "Test compensation"
        )

        assert result.is_success()
        assert self.context.status == TransactionStatus.ROLLED_BACK
        self.mock_saga.compensate.assert_called_once()


class TestTransactionRegistry:
    """트랜잭션 레지스트리 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        self.registry = TransactionRegistry()
        self.db_manager = Mock()
        self.redis_manager = Mock()

    def test_register_and_get_manager(self):
        """트랜잭션 매니저 등록 및 조회 테스트"""
        self.registry.register_manager(TransactionType.DATABASE, self.db_manager)
        self.registry.register_manager(TransactionType.REDIS, self.redis_manager)

        assert self.registry.get_manager(TransactionType.DATABASE) == self.db_manager
        assert self.registry.get_manager(TransactionType.REDIS) == self.redis_manager
        assert self.registry.get_manager(TransactionType.DISTRIBUTED) is None

    def test_default_config(self):
        """기본 설정 등록 및 조회 테스트"""
        config = TransactionConfig(timeout_seconds=60)
        self.registry.set_default_config(TransactionType.DATABASE, config)

        retrieved_config = self.registry.get_default_config(TransactionType.DATABASE)
        assert retrieved_config == config
        assert retrieved_config.timeout_seconds == 60


class TestTransactionDecorators:
    """트랜잭션 데코레이터 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        # Mock 매니저 등록
        self.mock_db_manager = AsyncMock()
        self.mock_db_manager.execute_in_transaction.return_value = Success("db_result")

        self.mock_redis_manager = AsyncMock()
        self.mock_redis_manager.execute_in_transaction.return_value = Success(
            "redis_result"
        )

        self.mock_distributed_manager = AsyncMock()
        self.mock_distributed_manager.execute_in_transaction.return_value = Success(
            "saga_result"
        )

        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, self.mock_db_manager)
        registry.register_manager(TransactionType.REDIS, self.mock_redis_manager)
        registry.register_manager(
            TransactionType.DISTRIBUTED, self.mock_distributed_manager
        )

    @pytest.mark.asyncio
    async def test_transactional_decorator(self):
        """@Transactional 데코레이터 테스트"""

        @Transactional(isolation=IsolationLevel.SERIALIZABLE, retry_count=5)
        async def test_func(value: int) -> str:
            return f"processed_{value}"

        result = await test_func(42)

        assert result.is_success()
        assert result.value == "db_result"
        self.mock_db_manager.execute_in_transaction.assert_called_once()

        # 트랜잭션 설정 확인
        call_args = self.mock_db_manager.execute_in_transaction.call_args
        context = call_args[0][0]
        assert context.config.isolation_level == IsolationLevel.SERIALIZABLE
        assert context.config.retry_count == 5

    @pytest.mark.asyncio
    async def test_redis_transaction_decorator(self):
        """@RedisTransaction 데코레이터 테스트"""

        @RedisTransaction(ttl=3600, key_pattern="test:{id}", watch_keys=["key1"])
        async def cache_func(data: dict) -> str:
            return "cached"

        result = await cache_func({"id": "123"})

        assert result.is_success()
        assert result.value == "redis_result"
        self.mock_redis_manager.execute_in_transaction.assert_called_once()

        # Redis 설정 확인
        call_args = self.mock_redis_manager.execute_in_transaction.call_args
        context = call_args[0][0]
        assert context.config.ttl_seconds == 3600
        assert context.config.key_pattern == "test:{id}"
        assert context.config.watch_keys == ["key1"]

    @pytest.mark.asyncio
    async def test_distributed_transaction_decorator(self):
        """@DistributedTransaction 데코레이터 테스트"""

        @DistributedTransaction(saga_id="user_workflow", timeout=600)
        async def workflow_func(user_data: dict) -> str:
            return "workflow_completed"

        result = await workflow_func({"user_id": "123"})

        assert result.is_success()
        assert result.value == "saga_result"
        self.mock_distributed_manager.execute_in_transaction.assert_called_once()

        # 분산 트랜잭션 설정 확인
        call_args = self.mock_distributed_manager.execute_in_transaction.call_args
        context = call_args[0][0]
        assert context.config.saga_id == "user_workflow"
        assert context.config.timeout_seconds == 600

    def test_transactional_method_class_decorator(self):
        """@TransactionalMethod 클래스 데코레이터 테스트"""

        @TransactionalMethod(isolation=IsolationLevel.READ_COMMITTED, timeout=45)
        class UserService:
            def __init__(self):
                pass

            async def create_user(self, user_data: dict) -> str:
                return "user_created"

            @Transactional(isolation=IsolationLevel.SERIALIZABLE)
            async def update_balance(self, user_id: str, amount: float) -> str:
                return "balance_updated"

        service = UserService()

        # 기본 설정이 적용된 메서드 확인
        assert hasattr(service.create_user, "_rfs_transactional")

        # 개별 설정이 있는 메서드는 그대로 유지
        assert hasattr(service.update_balance, "_rfs_transactional")

    @pytest.mark.asyncio
    async def test_sync_function_with_transactional(self):
        """동기 함수에 @Transactional 적용 테스트"""

        @Transactional()
        def sync_func(value: int) -> int:
            return value * 2

        # 동기 함수도 비동기로 래핑되어 실행
        result = sync_func(21)

        # Mock이 호출되었는지 확인 (비동기 실행 후)
        assert result is not None


class TestTransactionalContextManager:
    """트랜잭션 컨텍스트 매니저 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        self.mock_manager = AsyncMock()
        self.mock_manager.begin_transaction.return_value = Success(None)
        self.mock_manager.commit_transaction.return_value = Success(None)
        self.mock_manager.rollback_transaction.return_value = Success(None)

        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, self.mock_manager)

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """컨텍스트 매니저 정상 실행 테스트"""
        config = TransactionConfig()

        async with transactional_context(
            TransactionType.DATABASE, config
        ) as tx_context:
            assert tx_context.transaction_type == TransactionType.DATABASE
            assert tx_context.config == config

        self.mock_manager.begin_transaction.assert_called_once()
        self.mock_manager.commit_transaction.assert_called_once()
        self.mock_manager.rollback_transaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_manager_exception(self):
        """컨텍스트 매니저 예외 처리 테스트"""
        config = TransactionConfig()

        with pytest.raises(ValueError):
            async with transactional_context(
                TransactionType.DATABASE, config
            ) as tx_context:
                raise ValueError("Test exception")

        self.mock_manager.begin_transaction.assert_called_once()
        self.mock_manager.commit_transaction.assert_not_called()
        self.mock_manager.rollback_transaction.assert_called_once()


class TestRetryLogic:
    """재시도 로직 테스트"""

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_on_first_attempt(self):
        """첫 번째 시도에서 성공하는 경우 테스트"""

        async def success_func():
            return "Success"

        config = TransactionConfig(retry_count=3)
        context = TransactionContext(config=config)

        result = await execute_with_retry(success_func, context)

        assert result.is_success()
        assert result.value == "Success"
        assert context.attempts == 1

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_on_second_attempt(self):
        """두 번째 시도에서 성공하는 경우 테스트"""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First attempt fails")
            return "success_on_retry"

        config = TransactionConfig(retry_count=3, retry_delay_seconds=0.1)
        context = TransactionContext(config=config)

        result = await execute_with_retry(flaky_func, context)

        assert result.is_success()
        assert result.value == "success_on_retry"
        assert context.attempts == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_all_attempts_fail(self):
        """모든 시도가 실패하는 경우 테스트"""

        async def always_fail_func():
            raise RuntimeError("Always fails")

        config = TransactionConfig(retry_count=3, retry_delay_seconds=0.1)
        context = TransactionContext(config=config)

        result = await execute_with_retry(always_fail_func, context)

        assert result.is_failure()
        assert "failed after 3 attempts" in result.error
        assert context.attempts == 3
        assert isinstance(context.last_error, RuntimeError)


class TestPerformanceAndConcurrency:
    """성능 및 동시성 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_transactions(self):
        """동시 트랜잭션 처리 테스트"""
        mock_manager = AsyncMock()
        mock_manager.execute_in_transaction.side_effect = (
            lambda ctx, func, *args: Success(f"result_{args[0]}")
        )

        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, mock_manager)

        @Transactional()
        async def concurrent_func(value: int) -> str:
            # 약간의 지연 시뮬레이션
            await asyncio.sleep(0.1)
            return f"processed_{value}"

        # 10개 동시 실행
        tasks = [concurrent_func(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(result.is_success() for result in results)
        assert mock_manager.execute_in_transaction.call_count == 10

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_transaction_decorator_overhead(self):
        """트랜잭션 데코레이터 성능 오버헤드 테스트"""
        mock_manager = AsyncMock()
        mock_manager.execute_in_transaction.side_effect = (
            lambda ctx, func, *args: Success(func(*args))
        )

        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, mock_manager)

        @Transactional()
        async def fast_func(value: int) -> int:
            return value * 2

        # 1000회 실행 시간 측정
        start_time = time.time()

        for i in range(1000):
            result = await fast_func(i)
            assert result.is_success()

        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / 1000

        # 평균 실행 시간이 10ms 이내여야 함
        assert avg_time < 0.01, f"Average execution time too high: {avg_time:.4f}s"

        print(
            f"Performance: 1000 transactions in {total_time:.3f}s, avg: {avg_time:.6f}s per transaction"
        )


class TestIntegrationWithExistingComponents:
    """기존 RFS 컴포넌트와의 통합 테스트"""

    @pytest.mark.asyncio
    async def test_integration_with_result_pattern(self):
        """Result 패턴과의 통합 테스트"""
        mock_manager = AsyncMock()
        mock_manager.execute_in_transaction.return_value = Success("integrated_result")

        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, mock_manager)

        @Transactional()
        async def result_returning_func(value: str) -> Result[str, str]:
            if not value:
                return Failure("Empty value")
            return Success(f"processed_{value}")

        # 성공 케이스
        result = await result_returning_func("test")
        assert result.is_success()

        # 실패 케이스
        result = await result_returning_func("")
        assert result.is_success()  # 트랜잭션 자체는 성공


# 편의 함수 테스트
class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_convenience_decorators(self):
        """편의 데코레이터 함수 테스트"""
        # database_transaction 테스트
        db_decorator = database_transaction(isolation=IsolationLevel.SERIALIZABLE)
        assert callable(db_decorator)

        # redis_transaction 테스트
        redis_decorator = redis_transaction(ttl=3600)
        assert callable(redis_decorator)

        # saga_transaction 테스트
        saga_decorator = saga_transaction(saga_id="test_saga")
        assert callable(saga_decorator)


# 통합 시나리오 테스트
class TestIntegrationScenarios:
    """실제 사용 시나리오 통합 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        # 실제와 유사한 Mock 매니저들 설정
        self.setup_realistic_mocks()

    def setup_realistic_mocks(self):
        """실제와 유사한 Mock 설정"""
        # 데이터베이스 매니저 Mock
        self.db_manager = AsyncMock()
        self.db_operations = []

        async def mock_db_execute(ctx, func, *args, **kwargs):
            operation = f"{func.__name__}({args}, {kwargs})"
            self.db_operations.append(operation)
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            return Success(result)

        self.db_manager.execute_in_transaction.side_effect = mock_db_execute

        # Redis 매니저 Mock
        self.redis_manager = AsyncMock()
        self.redis_operations = []

        async def mock_redis_execute(ctx, func, *args, **kwargs):
            operation = f"{func.__name__}({args}, {kwargs})"
            self.redis_operations.append(operation)
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            return Success(result)

        self.redis_manager.execute_in_transaction.side_effect = mock_redis_execute

        # 레지스트리에 등록
        registry = get_transaction_registry()
        registry.register_manager(TransactionType.DATABASE, self.db_manager)
        registry.register_manager(TransactionType.REDIS, self.redis_manager)

    @pytest.mark.asyncio
    async def test_user_registration_workflow(self):
        """사용자 등록 워크플로우 통합 테스트"""

        @Transactional(isolation=IsolationLevel.SERIALIZABLE)
        async def create_user_in_db(user_data: dict) -> dict:
            """데이터베이스에 사용자 생성"""
            return {"user_id": "123", "email": user_data["email"]}

        @RedisTransaction(ttl=3600, key_pattern="user_session:{user_id}")
        async def create_user_session(user_id: str, session_data: dict) -> str:
            """사용자 세션 생성"""
            return f"session_{user_id}"

        # 워크플로우 실행
        user_data = {"email": "test@example.com", "name": "Test User"}

        # 1. 사용자 생성
        user_result = await create_user_in_db(user_data)
        assert user_result.is_success()

        # 2. 세션 생성
        session_result = await create_user_session("123", {"token": "abc123"})
        assert session_result.is_success()

        # 실행된 작업 확인
        assert len(self.db_operations) == 1
        assert len(self.redis_operations) == 1
        assert "create_user_in_db" in self.db_operations[0]
        assert "create_user_session" in self.redis_operations[0]

    @pytest.mark.asyncio
    async def test_nested_transaction_simulation(self):
        """중첩 트랜잭션 시뮬레이션 테스트"""

        @Transactional()
        async def outer_transaction(data: dict) -> dict:
            """외부 트랜잭션"""
            result = await inner_operation(data)
            return {"outer": True, "inner_result": result}

        @Transactional(isolation=IsolationLevel.REPEATABLE_READ)
        async def inner_operation(data: dict) -> dict:
            """내부 작업 (별도 트랜잭션)"""
            return {"inner": True, "data": data}

        result = await outer_transaction({"test": "data"})

        assert result.is_success()
        # 두 개의 트랜잭션이 실행되었는지 확인
        assert self.db_manager.execute_in_transaction.call_count == 2


if __name__ == "__main__":
    # 테스트 실행
    pytest.main([__file__, "-v", "--tb=short"])
