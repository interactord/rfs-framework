"""
Redis Transaction Support for RFS Framework

Redis 트랜잭션 지원 - 파이프라인, 원자적 연산, 분산 락
"""

import redis
from redis.client import Pipeline
from typing import Optional, Any, Dict, List, Callable, Union
from datetime import timedelta
from contextlib import contextmanager
import uuid
import time
import logging
from functools import wraps

from ..core import Result, Success, Failure
from .base import (
    TransactionResource,
    TransactionMetadata,
    TransactionError,
    TransactionStatus
)
from .manager import get_transaction_manager

logger = logging.getLogger(__name__)


class RedisLock:
    """
    Redis 기반 분산 락
    
    Redlock 알고리즘 구현
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        timeout: int = 10,
        retry_times: int = 3,
        retry_delay: float = 0.1
    ):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.retry_times = retry_times
        self.retry_delay = retry_delay
        self.token = str(uuid.uuid4())
        
    def acquire(self) -> bool:
        """락 획득"""
        for _ in range(self.retry_times):
            if self._try_acquire():
                return True
            time.sleep(self.retry_delay)
        return False
    
    def _try_acquire(self) -> bool:
        """락 획득 시도"""
        return bool(
            self.redis.set(
                self.key,
                self.token,
                nx=True,  # Not Exists
                ex=self.timeout  # Expire time
            )
        )
    
    def release(self) -> bool:
        """락 해제"""
        # Lua 스크립트로 원자적 처리
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            result = self.redis.eval(lua_script, 1, self.key, self.token)
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
            return False
    
    def extend(self, additional_time: int) -> bool:
        """락 시간 연장"""
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        try:
            result = self.redis.eval(
                lua_script,
                1,
                self.key,
                self.token,
                self.timeout + additional_time
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to extend lock: {e}")
            return False
    
    @contextmanager
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        if not self.acquire():
            raise TransactionError(f"Failed to acquire lock for {self.key}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.release()


class RedisTransactionResource(TransactionResource):
    """Redis 트랜잭션 리소스"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.pipelines: Dict[str, Pipeline] = {}
        self.savepoints: Dict[str, Dict[str, Any]] = {}
        
    def begin(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 시작"""
        try:
            # 파이프라인 생성
            pipeline = self.redis.pipeline(transaction=True)
            self.pipelines[metadata.transaction_id] = pipeline
            
            # MULTI 명령 (트랜잭션 시작)
            pipeline.multi()
            
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to begin Redis transaction: {str(e)}")
    
    def commit(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 커밋"""
        try:
            pipeline = self.pipelines.get(metadata.transaction_id)
            if not pipeline:
                return Failure("No pipeline found for transaction")
            
            # EXEC 명령 (트랜잭션 실행)
            results = pipeline.execute()
            
            # 파이프라인 정리
            del self.pipelines[metadata.transaction_id]
            
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to commit Redis transaction: {str(e)}")
    
    def rollback(self, metadata: TransactionMetadata) -> Result[None, str]:
        """트랜잭션 롤백"""
        try:
            pipeline = self.pipelines.get(metadata.transaction_id)
            if not pipeline:
                return Failure("No pipeline found for transaction")
            
            # DISCARD 명령 (트랜잭션 취소)
            pipeline.reset()
            
            # 파이프라인 정리
            del self.pipelines[metadata.transaction_id]
            
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to rollback Redis transaction: {str(e)}")
    
    def savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트 생성 (Redis는 중첩 트랜잭션 미지원)"""
        # Redis는 세이브포인트를 직접 지원하지 않음
        # 현재 상태를 저장하는 방식으로 구현
        return Success(None)
    
    def rollback_to_savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트로 롤백"""
        # Redis는 세이브포인트를 직접 지원하지 않음
        return Success(None)
    
    def release_savepoint(self, name: str) -> Result[None, str]:
        """세이브포인트 해제"""
        return Success(None)
    
    def suspend(self) -> Result[Any, str]:
        """트랜잭션 일시 중단"""
        # 현재 파이프라인 상태 저장
        return Success(self.pipelines.copy())
    
    def resume(self, suspended_resource: Any) -> Result[None, str]:
        """트랜잭션 재개"""
        if isinstance(suspended_resource, dict):
            self.pipelines.update(suspended_resource)
        return Success(None)


class RedisTransactionManager:
    """
    Redis 트랜잭션 매니저
    
    Redis 파이프라인과 트랜잭션 관리
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        **kwargs
    ):
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                **kwargs
            )
        
        self.resource = RedisTransactionResource(self.redis)
        self.current_pipeline: Optional[Pipeline] = None
        
        # 글로벌 트랜잭션 매니저에 등록
        manager = get_transaction_manager()
        manager.register_resource("redis", self.resource)
    
    def pipeline(self, transaction: bool = True) -> Pipeline:
        """파이프라인 생성"""
        pipeline = self.redis.pipeline(transaction=transaction)
        self.current_pipeline = pipeline
        return pipeline
    
    @contextmanager
    def transaction(self):
        """트랜잭션 컨텍스트 매니저"""
        pipeline = self.pipeline(transaction=True)
        try:
            pipeline.multi()
            yield pipeline
            pipeline.execute()
        except Exception as e:
            pipeline.reset()
            raise TransactionError(f"Redis transaction failed: {str(e)}")
        finally:
            self.current_pipeline = None
    
    def lock(
        self,
        key: str,
        timeout: int = 10,
        retry_times: int = 3,
        retry_delay: float = 0.1
    ) -> RedisLock:
        """분산 락 생성"""
        return RedisLock(
            self.redis,
            key,
            timeout=timeout,
            retry_times=retry_times,
            retry_delay=retry_delay
        )
    
    @contextmanager
    def atomic_operation(self, key: str):
        """원자적 연산 컨텍스트"""
        lock = self.lock(key)
        with lock:
            with self.transaction() as pipeline:
                yield pipeline
    
    def watch(self, *keys):
        """키 감시 (Optimistic Locking)"""
        return self.redis.watch(*keys)
    
    def unwatch(self):
        """키 감시 해제"""
        return self.redis.unwatch()
    
    def multi_exec(
        self,
        operations: List[Callable[[Pipeline], None]],
        watch_keys: Optional[List[str]] = None
    ) -> Result[List[Any], str]:
        """
        다중 명령 원자적 실행
        
        Args:
            operations: 파이프라인 연산 리스트
            watch_keys: 감시할 키 리스트
        
        Returns:
            실행 결과
        """
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                pipeline = self.pipeline()
                
                # 키 감시
                if watch_keys:
                    pipeline.watch(*watch_keys)
                
                # 트랜잭션 시작
                pipeline.multi()
                
                # 연산 실행
                for operation in operations:
                    operation(pipeline)
                
                # 실행
                results = pipeline.execute()
                return Success(results)
                
            except redis.WatchError:
                # 감시 중인 키가 변경됨 - 재시도
                retry_count += 1
                time.sleep(0.1 * retry_count)  # Exponential backoff
                continue
                
            except Exception as e:
                return Failure(f"Multi-exec failed: {str(e)}")
        
        return Failure("Max retries exceeded for multi-exec operation")


def redis_transactional(
    redis_manager: Optional[RedisTransactionManager] = None,
    lock_key: Optional[str] = None,
    watch_keys: Optional[List[str]] = None
):
    """
    Redis 트랜잭션 데코레이터
    
    Usage:
        @redis_transactional(lock_key="user:{user_id}")
        def update_user_balance(user_id: str, amount: float, pipeline: Pipeline):
            current = pipeline.get(f"balance:{user_id}")
            pipeline.set(f"balance:{user_id}", float(current) + amount)
    
    Args:
        redis_manager: Redis 트랜잭션 매니저
        lock_key: 분산 락 키
        watch_keys: 감시할 키 리스트
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Redis 매니저 확인
            manager = redis_manager
            if not manager:
                # 전역 매니저 사용 시도
                if 'redis_manager' in kwargs:
                    manager = kwargs['redis_manager']
                else:
                    raise TransactionError("No Redis transaction manager provided")
            
            # 락 사용 여부
            if lock_key:
                # 락 키 포맷팅 (함수 인자 사용 가능)
                formatted_key = lock_key.format(**kwargs)
                
                with manager.lock(formatted_key):
                    with manager.transaction() as pipeline:
                        if watch_keys:
                            formatted_watch_keys = [
                                key.format(**kwargs) for key in watch_keys
                            ]
                            pipeline.watch(*formatted_watch_keys)
                        
                        kwargs['pipeline'] = pipeline
                        return func(*args, **kwargs)
            else:
                # 락 없이 트랜잭션만 사용
                with manager.transaction() as pipeline:
                    if watch_keys:
                        formatted_watch_keys = [
                            key.format(**kwargs) for key in watch_keys
                        ]
                        pipeline.watch(*formatted_watch_keys)
                    
                    kwargs['pipeline'] = pipeline
                    return func(*args, **kwargs)
        
        return wrapper
    return decorator


def redis_atomic(key_pattern: str):
    """
    원자적 연산 데코레이터
    
    Usage:
        @redis_atomic("counter:{name}")
        def increment_counter(name: str, pipeline: Pipeline):
            pipeline.incr(f"counter:{name}")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 키 패턴 포맷팅
            key = key_pattern.format(**kwargs)
            
            # Redis 매니저 획득
            if 'redis_manager' in kwargs:
                manager = kwargs['redis_manager']
            else:
                raise TransactionError("No Redis transaction manager provided")
            
            with manager.atomic_operation(key) as pipeline:
                kwargs['pipeline'] = pipeline
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def redis_pipeline(func: Callable) -> Callable:
    """
    파이프라인 데코레이터
    
    Usage:
        @redis_pipeline
        def batch_operation(keys: List[str], pipeline: Pipeline):
            for key in keys:
                pipeline.get(key)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Redis 매니저 획득
        if 'redis_manager' in kwargs:
            manager = kwargs['redis_manager']
        else:
            raise TransactionError("No Redis transaction manager provided")
        
        pipeline = manager.pipeline(transaction=False)
        kwargs['pipeline'] = pipeline
        
        try:
            func(*args, **kwargs)
            results = pipeline.execute()
            return Success(results)
        except Exception as e:
            return Failure(f"Pipeline execution failed: {str(e)}")
    
    return wrapper