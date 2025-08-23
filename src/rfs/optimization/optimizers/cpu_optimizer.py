"""
CPU Optimization Engine for RFS Framework

CPU 성능 최적화, 동시성 튜닝, 비동기 처리 최적화
- CPU 집약적 작업 최적화
- 스레드 풀 및 프로세스 풀 관리
- 비동기 작업 최적화
- CPU 바운드 vs I/O 바운드 작업 분석
"""

import asyncio
import threading
import multiprocessing as mp
import concurrent.futures
import time
import psutil
import os
import sys
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic, Union, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import functools
import weakref

from rfs.core.result import Result, Success, Failure
from rfs.core.config import get_config
from rfs.reactive.mono import Mono
from rfs.events.event import Event

T = TypeVar('T')
R = TypeVar('R')

class CPUOptimizationStrategy(Enum):
    """CPU 최적화 전략"""
    SINGLE_THREAD = "single_thread"      # 단일 스레드
    MULTI_THREAD = "multi_thread"        # 멀티 스레드
    MULTI_PROCESS = "multi_process"      # 멀티 프로세스
    HYBRID = "hybrid"                    # 하이브리드 (스레드 + 프로세스)
    ASYNC_OPTIMIZED = "async_optimized"  # 비동기 최적화

class TaskType(Enum):
    """작업 유형"""
    CPU_BOUND = "cpu_bound"      # CPU 집약적
    IO_BOUND = "io_bound"        # I/O 집약적
    MIXED = "mixed"              # 혼합
    UNKNOWN = "unknown"          # 알 수 없음

class ConcurrencyLevel(Enum):
    """동시성 수준"""
    LOW = 1
    MEDIUM = 2
    HIGH = 4
    MAXIMUM = 8

@dataclass
class CPUThresholds:
    """CPU 임계값 설정"""
    high_usage_percent: float = 80.0      # 높은 사용률 임계값
    critical_usage_percent: float = 95.0  # 위험 사용률 임계값
    thread_pool_max: int = 32             # 최대 스레드 수
    process_pool_max: int = 8             # 최대 프로세스 수
    task_timeout_seconds: float = 300.0   # 작업 타임아웃
    monitoring_interval: float = 5.0      # 모니터링 간격

@dataclass
class CPUStats:
    """CPU 통계"""
    usage_percent: float
    core_count: int
    active_threads: int
    active_processes: int
    task_queue_size: int
    completed_tasks: int
    failed_tasks: int
    avg_task_duration: float
    optimization_score: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class CPUOptimizationConfig:
    """CPU 최적화 설정"""
    strategy: CPUOptimizationStrategy = CPUOptimizationStrategy.HYBRID
    concurrency_level: ConcurrencyLevel = ConcurrencyLevel.MEDIUM
    thresholds: CPUThresholds = field(default_factory=CPUThresholds)
    enable_monitoring: bool = True
    auto_scaling: bool = True
    prefer_threads_for_io: bool = True
    prefer_processes_for_cpu: bool = True

class TaskProfile:
    """작업 프로파일"""
    
    def __init__(self, name: str):
        self.name = name
        self.execution_times: deque = deque(maxlen=100)
        self.cpu_usage: deque = deque(maxlen=100)
        self.memory_usage: deque = deque(maxlen=100)
        self.task_type = TaskType.UNKNOWN
        self.success_count = 0
        self.failure_count = 0
        self.last_execution = None
    
    def record_execution(self, duration: float, cpu_usage: float, memory_usage: float, success: bool):
        """실행 기록"""
        self.execution_times.append(duration)
        self.cpu_usage.append(cpu_usage)
        self.memory_usage.append(memory_usage)
        self.last_execution = datetime.now()
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        # 작업 유형 추론
        self._infer_task_type()
    
    def _infer_task_type(self):
        """작업 유형 추론"""
        if len(self.cpu_usage) < 5:
            return
        
        avg_cpu = sum(self.cpu_usage) / len(self.cpu_usage)
        avg_duration = sum(self.execution_times) / len(self.execution_times)
        
        if avg_cpu > 50 and avg_duration > 1.0:
            self.task_type = TaskType.CPU_BOUND
        elif avg_cpu < 20 and avg_duration > 0.1:
            self.task_type = TaskType.IO_BOUND
        else:
            self.task_type = TaskType.MIXED
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            'name': self.name,
            'task_type': self.task_type.value,
            'avg_duration': sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0,
            'avg_cpu_usage': sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0,
            'success_rate': self.success_count / max(1, self.success_count + self.failure_count),
            'total_executions': self.success_count + self.failure_count
        }

class ThreadPoolOptimizer:
    """스레드 풀 최적화"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.task_times: deque = deque(maxlen=100)
        self.lock = threading.Lock()
    
    async def submit_async(self, fn: Callable[..., T], *args, **kwargs) -> Result[T, str]:
        """비동기 작업 제출"""
        loop = asyncio.get_event_loop()
        start_time = time.time()
        
        with self.lock:
            self.active_tasks += 1
        
        try:
            result = await loop.run_in_executor(self.executor, fn, *args, **kwargs)
            duration = time.time() - start_time
            
            with self.lock:
                self.active_tasks -= 1
                self.completed_tasks += 1
                self.task_times.append(duration)
            
            return Success(result)
            
        except Exception as e:
            with self.lock:
                self.active_tasks -= 1
                self.failed_tasks += 1
            
            return Failure(f"Thread pool task failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        avg_duration = sum(self.task_times) / len(self.task_times) if self.task_times else 0
        
        return {
            'max_workers': self.max_workers,
            'active_tasks': self.active_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'avg_task_duration': avg_duration,
            'success_rate': self.completed_tasks / max(1, self.completed_tasks + self.failed_tasks)
        }
    
    def shutdown(self, wait: bool = True):
        """스레드 풀 종료"""
        self.executor.shutdown(wait=wait)

class ProcessPoolOptimizer:
    """프로세스 풀 최적화"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or os.cpu_count()
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers)
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.task_times: deque = deque(maxlen=100)
        self.lock = threading.Lock()
    
    async def submit_async(self, fn: Callable[..., T], *args, **kwargs) -> Result[T, str]:
        """비동기 작업 제출"""
        loop = asyncio.get_event_loop()
        start_time = time.time()
        
        with self.lock:
            self.active_tasks += 1
        
        try:
            result = await loop.run_in_executor(self.executor, fn, *args, **kwargs)
            duration = time.time() - start_time
            
            with self.lock:
                self.active_tasks -= 1
                self.completed_tasks += 1
                self.task_times.append(duration)
            
            return Success(result)
            
        except Exception as e:
            with self.lock:
                self.active_tasks -= 1
                self.failed_tasks += 1
            
            return Failure(f"Process pool task failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        avg_duration = sum(self.task_times) / len(self.task_times) if self.task_times else 0
        
        return {
            'max_workers': self.max_workers,
            'active_tasks': self.active_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'avg_task_duration': avg_duration,
            'success_rate': self.completed_tasks / max(1, self.completed_tasks + self.failed_tasks)
        }
    
    def shutdown(self, wait: bool = True):
        """프로세스 풀 종료"""
        self.executor.shutdown(wait=wait)

class AsyncOptimizer:
    """비동기 작업 최적화"""
    
    def __init__(self):
        self.semaphore = asyncio.Semaphore(100)  # 동시 실행 제한
        self.task_registry: Dict[str, weakref.ref] = {}
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.task_times: deque = deque(maxlen=100)
    
    async def execute_with_optimization(self, coro: Coroutine[Any, Any, T], name: str = None) -> Result[T, str]:
        """최적화된 비동기 실행"""
        async with self.semaphore:
            start_time = time.time()
            task_name = name or f"task_{id(coro)}"
            
            try:
                # 작업 등록
                task = asyncio.create_task(coro)
                self.task_registry[task_name] = weakref.ref(task)
                
                result = await task
                duration = time.time() - start_time
                
                self.completed_tasks += 1
                self.task_times.append(duration)
                
                return Success(result)
                
            except Exception as e:
                duration = time.time() - start_time
                self.failed_tasks += 1
                self.task_times.append(duration)
                
                return Failure(f"Async task failed: {e}")
            
            finally:
                # 작업 정리
                if task_name in self.task_registry:
                    del self.task_registry[task_name]
    
    async def execute_batch(self, coros: List[Coroutine[Any, Any, T]], max_concurrent: int = 10) -> List[Result[T, str]]:
        """배치 실행"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_single(coro: Coroutine[Any, Any, T]) -> Result[T, str]:
            async with semaphore:
                return await self.execute_with_optimization(coro)
        
        tasks = [execute_single(coro) for coro in coros]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외를 Result로 변환
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(Failure(str(result)))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        avg_duration = sum(self.task_times) / len(self.task_times) if self.task_times else 0
        active_tasks = len([ref for ref in self.task_registry.values() if ref() is not None])
        
        return {
            'active_tasks': active_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'avg_task_duration': avg_duration,
            'success_rate': self.completed_tasks / max(1, self.completed_tasks + self.failed_tasks),
            'semaphore_available': self.semaphore._value
        }

class ConcurrencyTuner:
    """동시성 튜너"""
    
    def __init__(self, config: CPUOptimizationConfig):
        self.config = config
        self.performance_history: deque = deque(maxlen=50)
        self.current_settings = {
            'thread_workers': config.concurrency_level.value * 4,
            'process_workers': config.concurrency_level.value * 2,
            'async_semaphore': config.concurrency_level.value * 10
        }
    
    def analyze_performance(self, thread_stats: Dict, process_stats: Dict, async_stats: Dict) -> Dict[str, Any]:
        """성능 분석"""
        analysis = {
            'thread_efficiency': self._calculate_efficiency(thread_stats),
            'process_efficiency': self._calculate_efficiency(process_stats),
            'async_efficiency': self._calculate_efficiency(async_stats),
            'cpu_utilization': psutil.cpu_percent(interval=1),
            'memory_usage': psutil.virtual_memory().percent
        }
        
        self.performance_history.append(analysis)
        return analysis
    
    def _calculate_efficiency(self, stats: Dict) -> float:
        """효율성 계산"""
        if stats['completed_tasks'] == 0:
            return 0.0
        
        success_rate = stats['success_rate']
        avg_duration = stats['avg_task_duration']
        utilization = stats.get('active_tasks', 0) / stats.get('max_workers', 1)
        
        # 성공률, 응답시간, 활용률을 고려한 효율성 점수
        efficiency = (success_rate * 0.4) + ((1 / max(0.01, avg_duration)) * 0.3) + (utilization * 0.3)
        return min(1.0, efficiency)
    
    def recommend_tuning(self) -> Dict[str, int]:
        """튜닝 추천"""
        if len(self.performance_history) < 10:
            return self.current_settings
        
        recent_performance = list(self.performance_history)[-10:]
        avg_cpu = sum(p['cpu_utilization'] for p in recent_performance) / len(recent_performance)
        
        recommendations = self.current_settings.copy()
        
        # CPU 사용률이 낮으면 동시성 증가
        if avg_cpu < 60:
            recommendations['thread_workers'] = min(32, self.current_settings['thread_workers'] + 2)
            recommendations['async_semaphore'] = min(200, self.current_settings['async_semaphore'] + 10)
        
        # CPU 사용률이 높으면 동시성 감소
        elif avg_cpu > 85:
            recommendations['thread_workers'] = max(2, self.current_settings['thread_workers'] - 2)
            recommendations['process_workers'] = max(1, self.current_settings['process_workers'] - 1)
        
        return recommendations

class CPUOptimizer:
    """CPU 최적화 엔진"""
    
    def __init__(self, config: Optional[CPUOptimizationConfig] = None):
        self.config = config or CPUOptimizationConfig()
        self.thread_pool = ThreadPoolOptimizer(self.config.thresholds.thread_pool_max)
        self.process_pool = ProcessPoolOptimizer(self.config.thresholds.process_pool_max)
        self.async_optimizer = AsyncOptimizer()
        self.concurrency_tuner = ConcurrencyTuner(self.config)
        
        self.task_profiles: Dict[str, TaskProfile] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self.stats_history: deque = deque(maxlen=100)
        self.is_running = False
    
    async def initialize(self) -> Result[bool, str]:
        """최적화 엔진 초기화"""
        try:
            if self.config.enable_monitoring:
                await self.start_monitoring()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"CPU optimizer initialization failed: {e}")
    
    async def start_monitoring(self) -> Result[bool, str]:
        """CPU 모니터링 시작"""
        if self.is_running:
            return Success(True)
            
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to start CPU monitoring: {e}")
    
    async def stop_monitoring(self) -> Result[bool, str]:
        """CPU 모니터링 중지"""
        try:
            self.is_running = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to stop CPU monitoring: {e}")
    
    async def _monitoring_loop(self) -> None:
        """CPU 모니터링 루프"""
        while self.is_running:
            try:
                stats = await self._collect_cpu_stats()
                if stats.is_success():
                    cpu_stats = stats.unwrap()
                    self.stats_history.append(cpu_stats)
                    
                    # 자동 스케일링
                    if self.config.auto_scaling:
                        await self._auto_scale(cpu_stats)
                
                await asyncio.sleep(self.config.thresholds.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"CPU monitoring error: {e}")
                await asyncio.sleep(self.config.thresholds.monitoring_interval)
    
    async def _collect_cpu_stats(self) -> Result[CPUStats, str]:
        """CPU 통계 수집"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            core_count = psutil.cpu_count()
            
            # 스레드 및 프로세스 통계
            thread_stats = self.thread_pool.get_stats()
            process_stats = self.process_pool.get_stats()
            async_stats = self.async_optimizer.get_stats()
            
            # 작업 큐 크기 계산
            task_queue_size = (thread_stats['active_tasks'] + 
                             process_stats['active_tasks'] + 
                             async_stats['active_tasks'])
            
            # 완료된 작업 수
            completed_tasks = (thread_stats['completed_tasks'] + 
                             process_stats['completed_tasks'] + 
                             async_stats['completed_tasks'])
            
            # 실패한 작업 수
            failed_tasks = (thread_stats['failed_tasks'] + 
                          process_stats['failed_tasks'] + 
                          async_stats['failed_tasks'])
            
            # 평균 작업 시간
            all_durations = []
            if self.thread_pool.task_times:
                all_durations.extend(self.thread_pool.task_times)
            if self.process_pool.task_times:
                all_durations.extend(self.process_pool.task_times)
            if self.async_optimizer.task_times:
                all_durations.extend(self.async_optimizer.task_times)
            
            avg_task_duration = sum(all_durations) / len(all_durations) if all_durations else 0
            
            # 최적화 점수 계산
            optimization_score = self._calculate_optimization_score(
                cpu_percent, task_queue_size, completed_tasks, failed_tasks
            )
            
            stats = CPUStats(
                usage_percent=cpu_percent,
                core_count=core_count,
                active_threads=threading.active_count(),
                active_processes=len(psutil.pids()),
                task_queue_size=task_queue_size,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                avg_task_duration=avg_task_duration,
                optimization_score=optimization_score
            )
            
            return Success(stats)
            
        except Exception as e:
            return Failure(f"Failed to collect CPU stats: {e}")
    
    def _calculate_optimization_score(self, cpu_percent: float, queue_size: int, 
                                    completed: int, failed: int) -> float:
        """최적화 점수 계산 (0-100)"""
        score = 100.0
        
        # CPU 사용률 평가
        if cpu_percent > self.config.thresholds.critical_usage_percent:
            score -= 40
        elif cpu_percent > self.config.thresholds.high_usage_percent:
            score -= 20
        elif cpu_percent < 30:  # 너무 낮은 사용률도 비효율
            score -= 10
        
        # 큐 크기 평가
        if queue_size > 100:
            score -= 20
        
        # 성공률 평가
        total_tasks = completed + failed
        if total_tasks > 0:
            success_rate = completed / total_tasks
            score += (success_rate - 0.8) * 25  # 80% 이상이면 보너스
        
        return max(0.0, min(100.0, score))
    
    async def _auto_scale(self, stats: CPUStats) -> None:
        """자동 스케일링"""
        # 성능 분석
        thread_stats = self.thread_pool.get_stats()
        process_stats = self.process_pool.get_stats()
        async_stats = self.async_optimizer.get_stats()
        
        analysis = self.concurrency_tuner.analyze_performance(
            thread_stats, process_stats, async_stats
        )
        
        # 튜닝 추천
        recommendations = self.concurrency_tuner.recommend_tuning()
        
        # 실제 적용은 신중하게 (프로덕션 환경에서는 점진적 적용 필요)
        if len(self.stats_history) > 20:  # 충분한 데이터가 있을 때만
            current_score = stats.optimization_score
            recent_scores = [s.optimization_score for s in list(self.stats_history)[-10:]]
            avg_recent_score = sum(recent_scores) / len(recent_scores)
            
            if current_score < avg_recent_score - 10:  # 성능이 저하된 경우
                # 여기서는 로그만 남기고 실제 적용은 관리자 승인 후
                print(f"Performance degradation detected. Recommendations: {recommendations}")
    
    async def execute_task(self, task: Callable[..., T], *args, task_name: str = None, **kwargs) -> Result[T, str]:
        """작업 실행 (최적 전략 선택)"""
        task_name = task_name or task.__name__
        
        # 작업 프로파일 확인
        if task_name in self.task_profiles:
            profile = self.task_profiles[task_name]
            task_type = profile.task_type
        else:
            # 새로운 작업은 기본 전략 사용
            task_type = TaskType.UNKNOWN
        
        # 전략에 따라 실행 방법 선택
        start_time = time.time()
        start_cpu = psutil.cpu_percent()
        start_memory = psutil.virtual_memory().used
        
        try:
            if task_type == TaskType.CPU_BOUND or self.config.prefer_processes_for_cpu:
                result = await self.process_pool.submit_async(task, *args, **kwargs)
            elif task_type == TaskType.IO_BOUND or self.config.prefer_threads_for_io:
                result = await self.thread_pool.submit_async(task, *args, **kwargs)
            else:
                # 코루틴인 경우 비동기 최적화 사용
                if asyncio.iscoroutinefunction(task):
                    coro = task(*args, **kwargs)
                    result = await self.async_optimizer.execute_with_optimization(coro, task_name)
                else:
                    # 기본은 스레드 풀 사용
                    result = await self.thread_pool.submit_async(task, *args, **kwargs)
            
            # 프로파일 업데이트
            duration = time.time() - start_time
            end_cpu = psutil.cpu_percent()
            end_memory = psutil.virtual_memory().used
            
            cpu_usage = max(0, end_cpu - start_cpu)
            memory_usage = max(0, end_memory - start_memory)
            
            self._update_task_profile(task_name, duration, cpu_usage, memory_usage, result.is_success())
            
            return result
            
        except Exception as e:
            # 프로파일 업데이트 (실패)
            duration = time.time() - start_time
            self._update_task_profile(task_name, duration, 0, 0, False)
            
            return Failure(f"Task execution failed: {e}")
    
    def _update_task_profile(self, task_name: str, duration: float, cpu_usage: float, 
                           memory_usage: float, success: bool) -> None:
        """작업 프로파일 업데이트"""
        if task_name not in self.task_profiles:
            self.task_profiles[task_name] = TaskProfile(task_name)
        
        profile = self.task_profiles[task_name]
        profile.record_execution(duration, cpu_usage, memory_usage, success)
    
    async def execute_batch(self, tasks: List[Callable], max_concurrent: int = None) -> List[Result[Any, str]]:
        """배치 작업 실행"""
        if not tasks:
            return []
        
        max_concurrent = max_concurrent or self.config.concurrency_level.value * 4
        
        # 코루틴과 일반 함수 분리
        coros = []
        funcs = []
        
        for i, task in enumerate(tasks):
            if asyncio.iscoroutinefunction(task):
                coros.append((i, task))
            else:
                funcs.append((i, task))
        
        results = [None] * len(tasks)
        
        # 코루틴 실행
        if coros:
            coro_tasks = [task() for _, task in coros]
            coro_results = await self.async_optimizer.execute_batch(coro_tasks, max_concurrent)
            for (i, _), result in zip(coros, coro_results):
                results[i] = result
        
        # 일반 함수 실행 (스레드 풀 사용)
        if funcs:
            func_tasks = []
            for _, func in funcs:
                func_tasks.append(self.thread_pool.submit_async(func))
            
            func_results = await asyncio.gather(*func_tasks, return_exceptions=True)
            for (i, _), result in zip(funcs, func_results):
                if isinstance(result, Exception):
                    results[i] = Failure(str(result))
                else:
                    results[i] = result
        
        return results
    
    async def optimize(self) -> Result[Dict[str, Any], str]:
        """CPU 최적화 실행"""
        try:
            # 현재 통계 수집
            stats_result = await self._collect_cpu_stats()
            if not stats_result.is_success():
                return stats_result
            
            current_stats = stats_result.unwrap()
            
            # 성능 분석
            thread_stats = self.thread_pool.get_stats()
            process_stats = self.process_pool.get_stats()
            async_stats = self.async_optimizer.get_stats()
            
            analysis = self.concurrency_tuner.analyze_performance(
                thread_stats, process_stats, async_stats
            )
            
            # 튜닝 추천
            recommendations = self.concurrency_tuner.recommend_tuning()
            
            # 작업 프로파일 분석
            profile_analysis = self._analyze_task_profiles()
            
            results = {
                'current_stats': current_stats,
                'performance_analysis': analysis,
                'tuning_recommendations': recommendations,
                'task_profile_analysis': profile_analysis,
                'pool_stats': {
                    'thread_pool': thread_stats,
                    'process_pool': process_stats,
                    'async_optimizer': async_stats
                }
            }
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"CPU optimization failed: {e}")
    
    def _analyze_task_profiles(self) -> Dict[str, Any]:
        """작업 프로파일 분석"""
        if not self.task_profiles:
            return {}
        
        analysis = {
            'total_profiles': len(self.task_profiles),
            'task_types': defaultdict(int),
            'performance_summary': {},
            'recommendations': []
        }
        
        for name, profile in self.task_profiles.items():
            stats = profile.get_stats()
            analysis['task_types'][stats['task_type']] += 1
            analysis['performance_summary'][name] = stats
            
            # 개별 작업 추천
            if stats['success_rate'] < 0.9:
                analysis['recommendations'].append(f"Task '{name}' has low success rate: {stats['success_rate']:.2f}")
            
            if stats['avg_duration'] > 60:  # 1분 이상
                analysis['recommendations'].append(f"Task '{name}' has high duration: {stats['avg_duration']:.2f}s")
        
        return analysis
    
    def get_task_profile(self, task_name: str) -> Result[TaskProfile, str]:
        """작업 프로파일 조회"""
        if task_name not in self.task_profiles:
            return Failure(f"Task profile '{task_name}' not found")
        
        return Success(self.task_profiles[task_name])
    
    def get_current_stats(self) -> Result[CPUStats, str]:
        """현재 CPU 통계"""
        if not self.stats_history:
            return Failure("No statistics available")
        
        return Success(self.stats_history[-1])
    
    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            
            # 스레드 풀 종료
            self.thread_pool.shutdown(wait=True)
            
            # 프로세스 풀 종료
            self.process_pool.shutdown(wait=True)
            
            # 작업 프로파일 정리
            self.task_profiles.clear()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")

# 전역 optimizer 인스턴스
_cpu_optimizer: Optional[CPUOptimizer] = None

def get_cpu_optimizer(config: Optional[CPUOptimizationConfig] = None) -> CPUOptimizer:
    """CPU optimizer 싱글톤 인스턴스 반환"""
    global _cpu_optimizer
    if _cpu_optimizer is None:
        _cpu_optimizer = CPUOptimizer(config)
    return _cpu_optimizer

async def optimize_cpu_usage(strategy: CPUOptimizationStrategy = CPUOptimizationStrategy.HYBRID) -> Result[Dict[str, Any], str]:
    """CPU 사용량 최적화 실행"""
    config = CPUOptimizationConfig(strategy=strategy)
    optimizer = get_cpu_optimizer(config)
    
    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result
    
    return await optimizer.optimize()