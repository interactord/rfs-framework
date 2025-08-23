"""
RFS v4.1 Async Task Manager
비동기 작업 관리 시스템

주요 기능:
- 비동기 작업 제출 및 관리
- 작업 상태 추적 및 모니터링
- 작업 취소 및 타임아웃 처리
- 우선순위 기반 작업 처리
- 결과 조회 및 콜백 지원
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Callable, Any, Union, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import logging
import weakref
from concurrent.futures import ThreadPoolExecutor
import time

from ..core.result import Result, Success, Failure

logger = logging.getLogger(__name__)

T = TypeVar('T')
E = TypeVar('E')


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"          # 대기 중
    QUEUED = "queued"           # 큐에 대기
    RUNNING = "running"         # 실행 중
    COMPLETED = "completed"     # 완료
    FAILED = "failed"           # 실패
    CANCELLED = "cancelled"     # 취소됨
    TIMEOUT = "timeout"         # 타임아웃


class TaskPriority(Enum):
    """작업 우선순위"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskInfo:
    """작업 정보"""
    id: str
    name: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # 시간 정보
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 실행 정보
    function_name: Optional[str] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    
    # 결과 및 오류
    result: Any = None
    error: Optional[Exception] = None
    error_message: Optional[str] = None
    
    # 설정
    timeout_seconds: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 0
    
    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    @property
    def execution_time(self) -> Optional[float]:
        """실행 시간 계산 (초)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def total_time(self) -> float:
        """총 처리 시간 계산 (초)"""
        end_time = self.completed_at or datetime.now()
        return (end_time - self.created_at).total_seconds()
    
    @property
    def is_finished(self) -> bool:
        """작업 완료 여부"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, 
                              TaskStatus.CANCELLED, TaskStatus.TIMEOUT]


class TaskCallback(ABC):
    """작업 콜백 인터페이스"""
    
    @abstractmethod
    async def on_started(self, task_info: TaskInfo) -> None:
        """작업 시작 시 호출"""
        pass
    
    @abstractmethod
    async def on_completed(self, task_info: TaskInfo, result: Any) -> None:
        """작업 완료 시 호출"""
        pass
    
    @abstractmethod
    async def on_failed(self, task_info: TaskInfo, error: Exception) -> None:
        """작업 실패 시 호출"""
        pass
    
    @abstractmethod
    async def on_cancelled(self, task_info: TaskInfo) -> None:
        """작업 취소 시 호출"""
        pass


class SimpleTaskCallback(TaskCallback):
    """간단한 작업 콜백 구현"""
    
    def __init__(self, 
                 on_started: Optional[Callable] = None,
                 on_completed: Optional[Callable] = None,
                 on_failed: Optional[Callable] = None,
                 on_cancelled: Optional[Callable] = None):
        self.started_callback = on_started
        self.completed_callback = on_completed
        self.failed_callback = on_failed
        self.cancelled_callback = on_cancelled
    
    async def on_started(self, task_info: TaskInfo) -> None:
        if self.started_callback:
            if asyncio.iscoroutinefunction(self.started_callback):
                await self.started_callback(task_info)
            else:
                self.started_callback(task_info)
    
    async def on_completed(self, task_info: TaskInfo, result: Any) -> None:
        if self.completed_callback:
            if asyncio.iscoroutinefunction(self.completed_callback):
                await self.completed_callback(task_info, result)
            else:
                self.completed_callback(task_info, result)
    
    async def on_failed(self, task_info: TaskInfo, error: Exception) -> None:
        if self.failed_callback:
            if asyncio.iscoroutinefunction(self.failed_callback):
                await self.failed_callback(task_info, error)
            else:
                self.failed_callback(task_info, error)
    
    async def on_cancelled(self, task_info: TaskInfo) -> None:
        if self.cancelled_callback:
            if asyncio.iscoroutinefunction(self.cancelled_callback):
                await self.cancelled_callback(task_info)
            else:
                self.cancelled_callback(task_info)


@dataclass
class TaskManagerConfig:
    """작업 매니저 설정"""
    max_workers: int = 10                    # 최대 동시 작업 수
    max_queue_size: int = 1000               # 최대 큐 크기
    default_timeout: Optional[float] = 300   # 기본 타임아웃 (5분)
    default_max_retries: int = 3             # 기본 최대 재시도 횟수
    
    # 성능 설정
    enable_result_caching: bool = True       # 결과 캐싱 활성화
    result_cache_ttl: int = 3600            # 결과 캐시 TTL (초)
    cleanup_interval: int = 300              # 정리 간격 (초)
    
    # 모니터링 설정
    enable_detailed_logging: bool = False    # 상세 로깅
    collect_metrics: bool = True             # 메트릭 수집
    metrics_interval: int = 60               # 메트릭 수집 간격 (초)


class AsyncTaskManager:
    """
    비동기 작업 관리자
    
    주요 기능:
    - 비동기 작업 제출 및 관리
    - 우선순위 기반 작업 처리
    - 작업 상태 추적 및 모니터링
    - 작업 취소 및 타임아웃 처리
    - 콜백 지원
    
    사용법:
        manager = AsyncTaskManager()
        task_id = await manager.submit(my_async_function, arg1, arg2)
        result = await manager.get_result(task_id)
    """
    
    def __init__(self, config: TaskManagerConfig = None):
        self.config = config or TaskManagerConfig()
        
        # 작업 관리
        self.tasks: Dict[str, TaskInfo] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.pending_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.config.max_queue_size
        )
        
        # 동시성 제어
        self.semaphore = asyncio.Semaphore(self.config.max_workers)
        
        # 콜백 관리
        self.callbacks: Dict[str, List[TaskCallback]] = {}
        self.global_callbacks: List[TaskCallback] = []
        
        # 상태 관리
        self.is_running = False
        self.worker_tasks: List[asyncio.Task] = []
        
        # 메트릭
        self.metrics = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "average_execution_time": 0.0,
            "current_queue_size": 0,
            "active_tasks": 0
        }
        
        # 정리 및 모니터링 태스크
        self.cleanup_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """작업 매니저 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 워커 태스크들 시작
        for i in range(self.config.max_workers):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
        
        # 정리 태스크 시작
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # 메트릭 수집 태스크 시작
        if self.config.collect_metrics:
            self.metrics_task = asyncio.create_task(self._metrics_loop())
        
        logger.info(f"AsyncTaskManager started with {self.config.max_workers} workers")
    
    async def stop(self) -> None:
        """작업 매니저 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 모든 실행 중인 작업 취소
        cancel_tasks = []
        for task_id in list(self.running_tasks.keys()):
            cancel_tasks.append(self.cancel_task(task_id))
        
        if cancel_tasks:
            await asyncio.gather(*cancel_tasks, return_exceptions=True)
        
        # 워커 태스크들 취소
        for worker_task in self.worker_tasks:
            worker_task.cancel()
        
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        # 정리 및 메트릭 태스크 취소
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        if self.metrics_task:
            self.metrics_task.cancel()
        
        logger.info("AsyncTaskManager stopped")
    
    async def submit(self, 
                    func: Callable,
                    *args,
                    task_id: Optional[str] = None,
                    name: Optional[str] = None,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    timeout: Optional[float] = None,
                    max_retries: int = None,
                    callback: Optional[TaskCallback] = None,
                    metadata: Optional[Dict[str, Any]] = None,
                    tags: Optional[List[str]] = None,
                    **kwargs) -> str:
        """
        비동기 작업 제출
        
        Args:
            func: 실행할 함수
            *args: 함수 인자
            task_id: 작업 ID (선택사항)
            name: 작업 이름
            priority: 작업 우선순위
            timeout: 타임아웃 (초)
            max_retries: 최대 재시도 횟수
            callback: 작업 콜백
            metadata: 메타데이터
            tags: 태그
            **kwargs: 함수 키워드 인자
            
        Returns:
            str: 작업 ID
        """
        if not self.is_running:
            await self.start()
        
        # 작업 ID 생성
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 중복 확인
        if task_id in self.tasks:
            raise ValueError(f"Task with ID {task_id} already exists")
        
        # 작업 정보 생성
        task_info = TaskInfo(
            id=task_id,
            name=name or getattr(func, '__name__', str(func)),
            status=TaskStatus.PENDING,
            priority=priority,
            function_name=getattr(func, '__name__', str(func)),
            args=args,
            kwargs=kwargs,
            timeout_seconds=timeout or self.config.default_timeout,
            max_retries=max_retries or self.config.default_max_retries,
            metadata=metadata or {},
            tags=tags or []
        )
        
        # 작업 등록
        self.tasks[task_id] = task_info
        
        # 콜백 등록
        if callback:
            self.register_callback(task_id, callback)
        
        # 큐에 추가 (우선순위 고려)
        priority_value = -priority.value  # 높은 우선순위가 먼저 처리되도록
        await self.pending_queue.put((priority_value, time.time(), task_id, func, args, kwargs))
        
        task_info.status = TaskStatus.QUEUED
        self.metrics["total_submitted"] += 1
        self.metrics["current_queue_size"] = self.pending_queue.qsize()
        
        if self.config.enable_detailed_logging:
            logger.debug(f"Task {task_id} ({task_info.name}) submitted with priority {priority.name}")
        
        return task_id
    
    async def _worker(self, worker_name: str) -> None:
        """워커 루프"""
        logger.debug(f"Worker {worker_name} started")
        
        while self.is_running:
            try:
                # 큐에서 작업 가져오기
                try:
                    priority, timestamp, task_id, func, args, kwargs = await asyncio.wait_for(
                        self.pending_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # 세마포어 획득
                async with self.semaphore:
                    await self._execute_task(task_id, func, args, kwargs)
                
                # 큐 작업 완료 표시
                self.pending_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
        
        logger.debug(f"Worker {worker_name} stopped")
    
    async def _execute_task(self, task_id: str, func: Callable, args: tuple, kwargs: dict) -> None:
        """작업 실행"""
        task_info = self.tasks.get(task_id)
        if not task_info:
            logger.error(f"Task {task_id} not found")
            return
        
        # 취소된 작업 확인
        if task_info.status == TaskStatus.CANCELLED:
            return
        
        # 작업 시작
        task_info.status = TaskStatus.RUNNING
        task_info.started_at = datetime.now()
        self.metrics["active_tasks"] += 1
        
        # 콜백 호출 (시작)
        await self._call_callbacks(task_id, 'on_started', task_info)
        
        try:
            # 타임아웃 설정
            timeout = task_info.timeout_seconds
            
            # 함수 실행
            if asyncio.iscoroutinefunction(func):
                if timeout:
                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                else:
                    result = await func(*args, **kwargs)
            else:
                # 동기 함수는 스레드 풀에서 실행
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    if timeout:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(executor, lambda: func(*args, **kwargs)), 
                            timeout=timeout
                        )
                    else:
                        result = await loop.run_in_executor(executor, lambda: func(*args, **kwargs))
            
            # 성공 완료
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now()
            task_info.result = result
            
            self.metrics["total_completed"] += 1
            await self._call_callbacks(task_id, 'on_completed', task_info, result)
            
            if self.config.enable_detailed_logging:
                logger.debug(f"Task {task_id} completed successfully")
        
        except asyncio.TimeoutError:
            # 타임아웃
            task_info.status = TaskStatus.TIMEOUT
            task_info.completed_at = datetime.now()
            task_info.error_message = f"Task timed out after {timeout} seconds"
            
            self.metrics["total_failed"] += 1
            await self._call_callbacks(task_id, 'on_failed', task_info, TimeoutError(task_info.error_message))
            
            logger.warning(f"Task {task_id} timed out after {timeout} seconds")
        
        except asyncio.CancelledError:
            # 취소됨
            task_info.status = TaskStatus.CANCELLED
            task_info.completed_at = datetime.now()
            
            self.metrics["total_cancelled"] += 1
            await self._call_callbacks(task_id, 'on_cancelled', task_info)
            
            logger.info(f"Task {task_id} was cancelled")
        
        except Exception as e:
            # 실패
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now()
            task_info.error = e
            task_info.error_message = str(e)
            
            self.metrics["total_failed"] += 1
            await self._call_callbacks(task_id, 'on_failed', task_info, e)
            
            logger.error(f"Task {task_id} failed: {e}")
        
        finally:
            self.metrics["active_tasks"] -= 1
            self.metrics["current_queue_size"] = self.pending_queue.qsize()
            
            # 실행 중인 작업에서 제거
            self.running_tasks.pop(task_id, None)
    
    async def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """작업 상태 조회"""
        task_info = self.tasks.get(task_id)
        return task_info.status if task_info else None
    
    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """작업 정보 조회"""
        return self.tasks.get(task_id)
    
    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Result[Any, str]:
        """
        작업 결과 조회
        
        Args:
            task_id: 작업 ID
            timeout: 대기 타임아웃 (초)
            
        Returns:
            Result: 작업 결과 또는 오류
        """
        task_info = self.tasks.get(task_id)
        if not task_info:
            return Failure(f"Task {task_id} not found")
        
        # 이미 완료된 경우
        if task_info.is_finished:
            if task_info.status == TaskStatus.COMPLETED:
                return Success(task_info.result)
            else:
                return Failure(task_info.error_message or f"Task {task_id} {task_info.status.value}")
        
        # 완료까지 대기
        start_time = time.time()
        while not task_info.is_finished:
            if timeout and (time.time() - start_time) > timeout:
                return Failure(f"Timeout waiting for task {task_id} result")
            
            await asyncio.sleep(0.1)
        
        # 완료 후 결과 반환
        if task_info.status == TaskStatus.COMPLETED:
            return Success(task_info.result)
        else:
            return Failure(task_info.error_message or f"Task {task_id} {task_info.status.value}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        작업 취소
        
        Args:
            task_id: 작업 ID
            
        Returns:
            bool: 취소 성공 여부
        """
        task_info = self.tasks.get(task_id)
        if not task_info:
            return False
        
        # 이미 완료된 작업은 취소할 수 없음
        if task_info.is_finished:
            return False
        
        # 실행 중인 작업 취소
        if task_id in self.running_tasks:
            running_task = self.running_tasks[task_id]
            running_task.cancel()
        
        # 상태 업데이트
        task_info.status = TaskStatus.CANCELLED
        task_info.completed_at = datetime.now()
        
        return True
    
    async def wait_for_completion(self, task_ids: List[str], timeout: Optional[float] = None) -> Dict[str, Result]:
        """
        여러 작업의 완료를 기다림
        
        Args:
            task_ids: 작업 ID 목록
            timeout: 대기 타임아웃 (초)
            
        Returns:
            Dict[str, Result]: 작업별 결과
        """
        results = {}
        
        # 각 작업의 결과를 비동기적으로 가져오기
        async def get_task_result(task_id: str) -> tuple[str, Result]:
            result = await self.get_result(task_id, timeout)
            return task_id, result
        
        # 모든 작업 결과 수집
        tasks = [get_task_result(task_id) for task_id in task_ids]
        
        try:
            if timeout:
                completed_results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
            else:
                completed_results = await asyncio.gather(*tasks)
            
            for task_id, result in completed_results:
                results[task_id] = result
        
        except asyncio.TimeoutError:
            # 타임아웃 시 부분 결과 반환
            for task_id in task_ids:
                if task_id not in results:
                    results[task_id] = Failure(f"Timeout waiting for task {task_id}")
        
        return results
    
    def register_callback(self, task_id: str, callback: TaskCallback) -> None:
        """작업별 콜백 등록"""
        if task_id not in self.callbacks:
            self.callbacks[task_id] = []
        self.callbacks[task_id].append(callback)
    
    def register_global_callback(self, callback: TaskCallback) -> None:
        """전역 콜백 등록"""
        self.global_callbacks.append(callback)
    
    async def _call_callbacks(self, task_id: str, method_name: str, *args) -> None:
        """콜백 호출"""
        # 작업별 콜백
        if task_id in self.callbacks:
            for callback in self.callbacks[task_id]:
                try:
                    method = getattr(callback, method_name)
                    await method(*args)
                except Exception as e:
                    logger.error(f"Callback error for task {task_id}: {e}")
        
        # 전역 콜백
        for callback in self.global_callbacks:
            try:
                method = getattr(callback, method_name)
                await method(*args)
            except Exception as e:
                logger.error(f"Global callback error for task {task_id}: {e}")
    
    async def _cleanup_loop(self) -> None:
        """주기적 정리 루프"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_completed_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_completed_tasks(self) -> None:
        """완료된 작업 정리"""
        if not self.config.enable_result_caching:
            return
        
        current_time = datetime.now()
        expired_tasks = []
        
        for task_id, task_info in self.tasks.items():
            if (task_info.is_finished and 
                task_info.completed_at and
                (current_time - task_info.completed_at).total_seconds() > self.config.result_cache_ttl):
                expired_tasks.append(task_id)
        
        # 만료된 작업 제거
        for task_id in expired_tasks:
            del self.tasks[task_id]
            self.callbacks.pop(task_id, None)
        
        if expired_tasks:
            logger.debug(f"Cleaned up {len(expired_tasks)} expired tasks")
    
    async def _metrics_loop(self) -> None:
        """메트릭 수집 루프"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.metrics_interval)
                await self._update_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics loop error: {e}")
    
    async def _update_metrics(self) -> None:
        """메트릭 업데이트"""
        # 평균 실행 시간 계산
        completed_tasks = [task for task in self.tasks.values() 
                          if task.status == TaskStatus.COMPLETED and task.execution_time]
        
        if completed_tasks:
            total_execution_time = sum(task.execution_time for task in completed_tasks)
            self.metrics["average_execution_time"] = total_execution_time / len(completed_tasks)
        
        # 큐 크기 업데이트
        self.metrics["current_queue_size"] = self.pending_queue.qsize()
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 조회"""
        return self.metrics.copy()
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskInfo]:
        """상태별 작업 목록 조회"""
        return [task for task in self.tasks.values() if task.status == status]
    
    def get_tasks_by_tag(self, tag: str) -> List[TaskInfo]:
        """태그별 작업 목록 조회"""
        return [task for task in self.tasks.values() if tag in task.tags]


# 전역 작업 매니저
_default_task_manager: Optional[AsyncTaskManager] = None


def get_default_task_manager() -> AsyncTaskManager:
    """기본 작업 매니저 조회"""
    global _default_task_manager
    if _default_task_manager is None:
        _default_task_manager = AsyncTaskManager()
    return _default_task_manager


def create_task_manager(config: TaskManagerConfig = None) -> AsyncTaskManager:
    """새 작업 매니저 생성"""
    return AsyncTaskManager(config or TaskManagerConfig())


# 편의 함수들
async def submit_task(func: Callable, *args, **kwargs) -> str:
    """기본 매니저에 작업 제출"""
    manager = get_default_task_manager()
    return await manager.submit(func, *args, **kwargs)


async def get_task_result(task_id: str, timeout: Optional[float] = None) -> Result[Any, str]:
    """기본 매니저에서 작업 결과 조회"""
    manager = get_default_task_manager()
    return await manager.get_result(task_id, timeout)


# 예제 및 테스트
if __name__ == "__main__":
    async def example_usage():
        """사용 예제"""
        print("🧪 AsyncTaskManager Example")
        
        # 작업 매니저 생성
        config = TaskManagerConfig(max_workers=5, enable_detailed_logging=True)
        manager = AsyncTaskManager(config)
        
        # 예제 함수들
        async def async_task(name: str, delay: float) -> str:
            await asyncio.sleep(delay)
            return f"Task {name} completed after {delay}s"
        
        def sync_task(name: str, value: int) -> int:
            time.sleep(0.1)  # 작업 시뮬레이션
            return value * 2
        
        # 작업 제출
        task1_id = await manager.submit(async_task, "async1", 1.0, priority=TaskPriority.HIGH)
        task2_id = await manager.submit(sync_task, "sync1", 42, priority=TaskPriority.NORMAL)
        task3_id = await manager.submit(async_task, "async2", 0.5, priority=TaskPriority.CRITICAL)
        
        print(f"Submitted tasks: {task1_id[:8]}, {task2_id[:8]}, {task3_id[:8]}")
        
        # 결과 대기
        results = await manager.wait_for_completion([task1_id, task2_id, task3_id], timeout=5.0)
        
        for task_id, result in results.items():
            if result.is_success():
                print(f"Task {task_id[:8]}: {result.value}")
            else:
                print(f"Task {task_id[:8]} failed: {result.error}")
        
        # 메트릭 조회
        metrics = manager.get_metrics()
        print(f"Metrics: {metrics}")
        
        # 정리
        await manager.stop()
        print("Example completed!")
    
    asyncio.run(example_usage())