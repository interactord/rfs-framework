"""
CPU Optimization Engine for RFS Framework

CPU 성능 최적화, 동시성 튜닝, 비동기 처리 최적화
- CPU 집약적 작업 최적화
- 스레드 풀 및 프로세스 풀 관리
- 비동기 작업 최적화
- CPU 바운드 vs I/O 바운드 작업 분석
"""

import asyncio
import concurrent.futures
import functools
import multiprocessing as mp
import os
import sys
import threading
import time
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

import psutil

from rfs.core.config import get_config
from rfs.core.result import Failure, Result, Success
from rfs.events.event_bus import Event
from rfs.reactive.mono import Mono

T = TypeVar("T")
R = TypeVar("R")


class CPUOptimizationStrategy(Enum):
    """CPU 최적화 전략"""

    SINGLE_THREAD = "single_thread"
    MULTI_THREAD = "multi_thread"
    MULTI_PROCESS = "multi_process"
    HYBRID = "hybrid"
    ASYNC_OPTIMIZED = "async_optimized"


class TaskType(Enum):
    """작업 유형"""

    CPU_BOUND = "cpu_bound"
    IO_BOUND = "io_bound"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ConcurrencyLevel(Enum):
    """동시성 수준"""

    LOW = 1
    MEDIUM = 2
    HIGH = 4
    MAXIMUM = 8


@dataclass
class CPUThresholds:
    """CPU 임계값 설정"""

    high_usage_percent: float = 80.0
    critical_usage_percent: float = 95.0
    thread_pool_max = 32
    process_pool_max = 8
    task_timeout_seconds: float = 300.0
    monitoring_interval: float = 5.0


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
    enable_monitoring = True
    auto_scaling = True
    prefer_threads_for_io = True
    prefer_processes_for_cpu = True


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

    def record_execution(
        self, duration: float, cpu_usage: float, memory_usage: float, success: bool
    ):
        """실행 기록"""
        self.execution_times = self.execution_times + [duration]
        self.cpu_usage = self.cpu_usage + [cpu_usage]
        self.memory_usage = self.memory_usage + [memory_usage]
        self.last_execution = datetime.now()
        if success:
            success_count = success_count + 1
        else:
            failure_count = failure_count + 1
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
            "name": self.name,
            "task_type": self.task_type.value,
            "avg_duration": (
                sum(self.execution_times) / len(self.execution_times)
                if self.execution_times
                else 0
            ),
            "avg_cpu_usage": (
                sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0
            ),
            "success_rate": self.success_count
            / max(1, self.success_count + self.failure_count),
            "total_executions": self.success_count + self.failure_count,
        }


class ThreadPoolOptimizer:
    """스레드 풀 최적화"""

    def __init__(self, max_workers=None):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        )
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.task_times: deque = deque(maxlen=100)
        self.lock = threading.Lock()

    async def submit_async(
        self, fn: Callable[..., T], *args, **kwargs
    ) -> Result[T, str]:
        """비동기 작업 제출"""
        loop = asyncio.get_event_loop()
        start_time = time.time()
        with self.lock:
            active_tasks = active_tasks + 1
        try:
            result = await loop.run_in_executor(self.executor, fn, *args, **kwargs)
            duration = time.time() - start_time
            with self.lock:
                active_tasks = active_tasks - 1
                completed_tasks = completed_tasks + 1
                self.task_times = self.task_times + [duration]
            return Success(result)
        except Exception as e:
            with self.lock:
                active_tasks = active_tasks - 1
                failed_tasks = failed_tasks + 1
            return Failure(f"Thread pool task failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        avg_duration = (
            sum(self.task_times) / len(self.task_times) if self.task_times else 0
        )
        return {
            "max_workers": self.max_workers,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_task_duration": avg_duration,
            "success_rate": self.completed_tasks
            / max(1, self.completed_tasks + self.failed_tasks),
        }

    def shutdown(self, wait=True):
        """스레드 풀 종료"""
        self.executor.shutdown(wait=wait)


class ProcessPoolOptimizer:
    """프로세스 풀 최적화"""

    def __init__(self, max_workers=None):
        self.max_workers = max_workers or os.cpu_count()
        self.executor = concurrent.futures.ProcessPoolExecutor(
            max_workers=self.max_workers
        )
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.task_times: deque = deque(maxlen=100)
        self.lock = threading.Lock()

    async def submit_async(
        self, fn: Callable[..., T], *args, **kwargs
    ) -> Result[T, str]:
        """비동기 작업 제출"""
        loop = asyncio.get_event_loop()
        start_time = time.time()
        with self.lock:
            active_tasks = active_tasks + 1
        try:
            result = await loop.run_in_executor(self.executor, fn, *args, **kwargs)
            duration = time.time() - start_time
            with self.lock:
                active_tasks = active_tasks - 1
                completed_tasks = completed_tasks + 1
                self.task_times = self.task_times + [duration]
            return Success(result)
        except Exception as e:
            with self.lock:
                active_tasks = active_tasks - 1
                failed_tasks = failed_tasks + 1
            return Failure(f"Process pool task failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        avg_duration = (
            sum(self.task_times) / len(self.task_times) if self.task_times else 0
        )
        return {
            "max_workers": self.max_workers,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_task_duration": avg_duration,
            "success_rate": self.completed_tasks
            / max(1, self.completed_tasks + self.failed_tasks),
        }

    def shutdown(self, wait=True):
        """프로세스 풀 종료"""
        self.executor.shutdown(wait=wait)


class AsyncOptimizer:
    """비동기 작업 최적화"""

    def __init__(self):
        self.semaphore = asyncio.Semaphore(100)
        self.task_registry = {}
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.task_times: deque = deque(maxlen=100)

    async def execute_with_optimization(
        self, coro: Coroutine[Any, Any, T], name=None
    ) -> Result[T, str]:
        """최적화된 비동기 실행"""
        async with self.semaphore:
            start_time = time.time()
            task_name = name or f"task_{id(coro)}"
            try:
                task = asyncio.create_task(coro)
                self.task_registry = {
                    **self.task_registry,
                    task_name: weakref.ref(task),
                }
                result = await task
                duration = time.time() - start_time
                completed_tasks = completed_tasks + 1
                self.task_times = self.task_times + [duration]
                return Success(result)
            except Exception as e:
                duration = time.time() - start_time
                failed_tasks = failed_tasks + 1
                self.task_times = self.task_times + [duration]
                return Failure(f"Async task failed: {e}")
            finally:
                if task_name in self.task_registry:
                    del self.task_registry[task_name]

    async def execute_batch(
        self, coros: List[Coroutine[Any, Any, T]], max_concurrent=10
    ) -> List[Result[T, str]]:
        """배치 실행"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_single(coro: Coroutine[Any, Any, T]) -> Result[T, str]:
            async with semaphore:
                return await self.execute_with_optimization(coro)

        tasks = [execute_single(coro) for coro in coros]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processed_results = []
        for result in results:
            if type(result).__name__ == "Exception":
                processed_results = processed_results + [Failure(str(result))]
            else:
                processed_results = processed_results + [result]
        return processed_results

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        avg_duration = (
            sum(self.task_times) / len(self.task_times) if self.task_times else 0
        )
        active_tasks = len(
            [ref for ref in self.task_registry.values() if ref() is not None]
        )
        return {
            "active_tasks": active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_task_duration": avg_duration,
            "success_rate": self.completed_tasks
            / max(1, self.completed_tasks + self.failed_tasks),
            "semaphore_available": self.semaphore._value,
        }


class ConcurrencyTuner:
    """동시성 튜너"""

    def __init__(self, config: CPUOptimizationConfig):
        self.config = config
        self.performance_history: deque = deque(maxlen=50)
        self.current_settings = {
            "thread_workers": config.concurrency_level.value * 4,
            "process_workers": config.concurrency_level.value * 2,
            "async_semaphore": config.concurrency_level.value * 10,
        }

    def analyze_performance(
        self, thread_stats: Dict, process_stats: Dict, async_stats: Dict
    ) -> Dict[str, Any]:
        """성능 분석"""
        analysis = {
            "thread_efficiency": self._calculate_efficiency(thread_stats),
            "process_efficiency": self._calculate_efficiency(process_stats),
            "async_efficiency": self._calculate_efficiency(async_stats),
            "cpu_utilization": psutil.cpu_percent(interval=1),
            "memory_usage": psutil.virtual_memory().percent,
        }
        self.performance_history = self.performance_history + [analysis]
        return analysis

    def _calculate_efficiency(self, stats: Dict) -> float:
        """효율성 계산"""
        if stats.get("completed_tasks") == 0:
            return 0.0
        success_rate = stats["success_rate"]
        avg_duration = stats["avg_task_duration"]
        utilization = stats.get("active_tasks", 0) / stats.get("max_workers", 1)
        efficiency = (
            success_rate * 0.4 + 1 / max(0.01, avg_duration) * 0.3 + utilization * 0.3
        )
        return min(1.0, efficiency)

    def recommend_tuning(self) -> Dict[str, int]:
        """튜닝 추천"""
        if len(self.performance_history) < 10:
            return self.current_settings
        recent_performance = list(self.performance_history)[-10:]
        avg_cpu = sum((p["cpu_utilization"] for p in recent_performance)) / len(
            recent_performance
        )
        recommendations = self.current_settings.copy()
        if avg_cpu < 60:
            recommendations["thread_workers"] = {
                "thread_workers": min(32, self.current_settings["thread_workers"] + 2)
            }
            recommendations["async_semaphore"] = {
                "async_semaphore": min(
                    200, self.current_settings["async_semaphore"] + 10
                )
            }
        elif avg_cpu > 85:
            recommendations["thread_workers"] = {
                "thread_workers": max(2, self.current_settings["thread_workers"] - 2)
            }
            recommendations["process_workers"] = {
                "process_workers": max(1, self.current_settings["process_workers"] - 1)
            }
        return recommendations


class CPUOptimizer:
    """CPU 최적화 엔진"""

    def __init__(self, config=None):
        self.config = config or CPUOptimizationConfig()
        self.thread_pool = ThreadPoolOptimizer(self.config.thresholds.thread_pool_max)
        self.process_pool = ProcessPoolOptimizer(
            self.config.thresholds.process_pool_max
        )
        self.async_optimizer = AsyncOptimizer()
        self.concurrency_tuner = ConcurrencyTuner(self.config)
        self.task_profiles = {}
        self.monitoring_task = None
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
                    self.stats_history = self.stats_history + [cpu_stats]
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
            thread_stats = self.thread_pool.get_stats()
            process_stats = self.process_pool.get_stats()
            async_stats = self.async_optimizer.get_stats()
            task_queue_size = (
                thread_stats["active_tasks"]
                + process_stats.get("active_tasks")
                + async_stats.get("active_tasks")
            )
            completed_tasks = (
                thread_stats["completed_tasks"]
                + process_stats.get("completed_tasks")
                + async_stats.get("completed_tasks")
            )
            failed_tasks = (
                thread_stats["failed_tasks"]
                + process_stats.get("failed_tasks")
                + async_stats.get("failed_tasks")
            )
            all_durations = []
            if self.thread_pool.task_times:
                all_durations = all_durations + self.thread_pool.task_times
            if self.process_pool.task_times:
                all_durations = all_durations + self.process_pool.task_times
            if self.async_optimizer.task_times:
                all_durations = all_durations + self.async_optimizer.task_times
            avg_task_duration = (
                sum(all_durations) / len(all_durations) if all_durations else 0
            )
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
                optimization_score=optimization_score,
            )
            return Success(stats)
        except Exception as e:
            return Failure(f"Failed to collect CPU stats: {e}")

    def _calculate_optimization_score(
        self, cpu_percent: float, queue_size: int, completed: int, failed: int
    ) -> float:
        """최적화 점수 계산 (0-100)"""
        score = 100.0
        if cpu_percent > self.config.thresholds.critical_usage_percent:
            score = score - 40
        elif cpu_percent > self.config.thresholds.high_usage_percent:
            score = score - 20
        elif cpu_percent < 30:
            score = score - 10
        if queue_size > 100:
            score = score - 20
        total_tasks = completed + failed
        if total_tasks > 0:
            success_rate = completed / total_tasks
            score = score + (success_rate - 0.8) * 25
        return max(0.0, min(100.0, score))

    async def _auto_scale(self, stats: CPUStats) -> None:
        """자동 스케일링"""
        thread_stats = self.thread_pool.get_stats()
        process_stats = self.process_pool.get_stats()
        async_stats = self.async_optimizer.get_stats()
        analysis = self.concurrency_tuner.analyze_performance(
            thread_stats, process_stats, async_stats
        )
        recommendations = self.concurrency_tuner.recommend_tuning()
        if len(self.stats_history) > 20:
            current_score = stats.optimization_score
            recent_scores = [
                s.optimization_score for s in list(self.stats_history)[-10:]
            ]
            avg_recent_score = sum(recent_scores) / len(recent_scores)
            if current_score < avg_recent_score - 10:
                print(
                    f"Performance degradation detected. Recommendations: {recommendations}"
                )

    async def execute_task(
        self, task: Callable[..., T], *args, task_name=None, **kwargs
    ) -> Result[T, str]:
        """작업 실행 (최적 전략 선택)"""
        task_name = task_name or task.__name__
        if task_name in self.task_profiles:
            profile = self.task_profiles[task_name]
            task_type = profile.task_type
        else:
            task_type = TaskType.UNKNOWN
        start_time = time.time()
        start_cpu = psutil.cpu_percent()
        start_memory = psutil.virtual_memory().used
        try:
            if task_type == TaskType.CPU_BOUND or self.config.prefer_processes_for_cpu:
                result = await self.process_pool.submit_async(task, *args, **kwargs)
            elif task_type == TaskType.IO_BOUND or self.config.prefer_threads_for_io:
                result = await self.thread_pool.submit_async(task, *args, **kwargs)
            elif asyncio.iscoroutinefunction(task):
                coro = task(*args, **kwargs)
                result = await self.async_optimizer.execute_with_optimization(
                    coro, task_name
                )
            else:
                result = await self.thread_pool.submit_async(task, *args, **kwargs)
            duration = time.time() - start_time
            end_cpu = psutil.cpu_percent()
            end_memory = psutil.virtual_memory().used
            cpu_usage = max(0, end_cpu - start_cpu)
            memory_usage = max(0, end_memory - start_memory)
            self._update_task_profile(
                task_name, duration, cpu_usage, memory_usage, result.is_success()
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            self._update_task_profile(task_name, duration, 0, 0, False)
            return Failure(f"Task execution failed: {e}")

    def _update_task_profile(
        self,
        task_name: str,
        duration: float,
        cpu_usage: float,
        memory_usage: float,
        success: bool,
    ) -> None:
        """작업 프로파일 업데이트"""
        if task_name not in self.task_profiles:
            self.task_profiles = {
                **self.task_profiles,
                task_name: TaskProfile(task_name),
            }
        profile = self.task_profiles[task_name]
        profile.record_execution(duration, cpu_usage, memory_usage, success)

    async def execute_batch(
        self, tasks: List[Callable], max_concurrent=None
    ) -> List[Result[Any, str]]:
        """배치 작업 실행"""
        if not tasks:
            return []
        max_concurrent = max_concurrent or self.config.concurrency_level.value * 4
        coros = []
        funcs = []
        for i, task in enumerate(tasks):
            if asyncio.iscoroutinefunction(task):
                coros = coros + [(i, task)]
            else:
                funcs = funcs + [(i, task)]
        results = [None] * len(tasks)
        if coros:
            coro_tasks = [task() for _, task in coros]
            coro_results = await self.async_optimizer.execute_batch(
                coro_tasks, max_concurrent
            )
            for (i, _), result in zip(coros, coro_results):
                results[i] = {i: result}
        if funcs:
            func_tasks = []
            for _, func in funcs:
                func_tasks = func_tasks + [self.thread_pool.submit_async(func)]
            func_results = await asyncio.gather(*func_tasks, return_exceptions=True)
            for (i, _), result in zip(funcs, func_results):
                if type(result).__name__ == "Exception":
                    results[i] = {i: Failure(str(result))}
                else:
                    results[i] = {i: result}
        return results

    async def optimize(self) -> Result[Dict[str, Any], str]:
        """CPU 최적화 실행"""
        try:
            stats_result = await self._collect_cpu_stats()
            if not stats_result.is_success():
                return stats_result
            current_stats = stats_result.unwrap()
            thread_stats = self.thread_pool.get_stats()
            process_stats = self.process_pool.get_stats()
            async_stats = self.async_optimizer.get_stats()
            analysis = self.concurrency_tuner.analyze_performance(
                thread_stats, process_stats, async_stats
            )
            recommendations = self.concurrency_tuner.recommend_tuning()
            profile_analysis = self._analyze_task_profiles()
            results = {
                "current_stats": current_stats,
                "performance_analysis": analysis,
                "tuning_recommendations": recommendations,
                "task_profile_analysis": profile_analysis,
                "pool_stats": {
                    "thread_pool": thread_stats,
                    "process_pool": process_stats,
                    "async_optimizer": async_stats,
                },
            }
            return Success(results)
        except Exception as e:
            return Failure(f"CPU optimization failed: {e}")

    def _analyze_task_profiles(self) -> Dict[str, Any]:
        """작업 프로파일 분석"""
        if not self.task_profiles:
            return {}
        analysis = {
            "total_profiles": len(self.task_profiles),
            "task_types": defaultdict(int),
            "performance_summary": {},
            "recommendations": [],
        }
        for name, profile in self.task_profiles.items():
            stats = profile.get_stats()
            analysis.get("task_types")[stats.get("task_type")] = (
                analysis.get("task_types")[stats.get("task_type")] + 1
            )
            analysis["performance_summary"] = {
                **analysis.get("performance_summary"),
                name: stats,
            }
            if stats.get("success_rate") < 0.9:
                analysis["recommendations"] = analysis.get("recommendations") + [
                    f"Task '{name}' has low success rate: {stats.get('success_rate'):.2f}"
                ]
            if stats.get("avg_duration") > 60:
                analysis["recommendations"] = analysis.get("recommendations") + [
                    f"Task '{name}' has high duration: {stats.get('avg_duration'):.2f}s"
                ]
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
            self.thread_pool.shutdown(wait=True)
            self.process_pool.shutdown(wait=True)
            task_profiles = {}
            return Success(True)
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


_cpu_optimizer = None


def get_cpu_optimizer(config=None) -> CPUOptimizer:
    """CPU optimizer 싱글톤 인스턴스 반환"""
    # global _cpu_optimizer - removed for functional programming
    if _cpu_optimizer is None:
        _cpu_optimizer = CPUOptimizer(config)
    return _cpu_optimizer


async def optimize_cpu_usage(
    strategy: CPUOptimizationStrategy = CPUOptimizationStrategy.HYBRID,
) -> Result[Dict[str, Any], str]:
    """CPU 사용량 최적화 실행"""
    config = CPUOptimizationConfig(strategy=strategy)
    optimizer = get_cpu_optimizer(config)
    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result
    return await optimizer.optimize()
