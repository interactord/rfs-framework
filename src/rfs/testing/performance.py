"""
RFS Testing Framework - Performance Testing Module
성능 테스트 지원 모듈
"""

import asyncio
import time
import tracemalloc
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import psutil

from ..core.result import Failure, Result, Success


@dataclass
class PerformanceMetrics:
    """성능 메트릭"""

    execution_time: float = 0.0
    cpu_percent: float = 0.0
    memory_usage: float = 0.0
    memory_peak: float = 0.0
    throughput: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0

    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "execution_time": self.execution_time,
            "cpu_percent": self.cpu_percent,
            "memory_usage": self.memory_usage,
            "memory_peak": self.memory_peak,
            "throughput": self.throughput,
            "latency_p50": self.latency_p50,
            "latency_p95": self.latency_p95,
            "latency_p99": self.latency_p99,
        }


class PerformanceTest:
    """성능 테스트 베이스 클래스"""

    def __init__(self, name="PerformanceTest"):
        """초기화"""
        self.name = name
        self.metrics = []
        self.process = psutil.Process()

    def measure(
        self, func: Callable, *args, **kwargs
    ) -> Result[PerformanceMetrics, str]:
        """성능 측정"""
        try:
            # 초기 상태
            tracemalloc.start()
            cpu_before = self.process.cpu_percent()
            mem_before = self.process.memory_info().rss / 1024 / 1024  # MB

            # 실행
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()

            # 측정
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            cpu_after = self.process.cpu_percent()
            mem_after = self.process.memory_info().rss / 1024 / 1024  # MB

            # 메트릭 생성
            metrics = PerformanceMetrics(
                execution_time=end_time - start_time,
                cpu_percent=(cpu_after - cpu_before),
                memory_usage=(mem_after - mem_before),
                memory_peak=peak / 1024 / 1024,  # MB
            )

            self.metrics.append(metrics)
            return Success(metrics)

        except Exception as e:
            return Failure(f"Performance measurement failed: {str(e)}")

    async def measure_async(
        self, func: Callable, *args, **kwargs
    ) -> Result[PerformanceMetrics, str]:
        """비동기 성능 측정"""
        try:
            # 초기 상태
            tracemalloc.start()
            cpu_before = self.process.cpu_percent()
            mem_before = self.process.memory_info().rss / 1024 / 1024  # MB

            # 실행
            start_time = time.perf_counter()
            result = await func(*args, **kwargs)
            end_time = time.perf_counter()

            # 측정
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            cpu_after = self.process.cpu_percent()
            mem_after = self.process.memory_info().rss / 1024 / 1024  # MB

            # 메트릭 생성
            metrics = PerformanceMetrics(
                execution_time=end_time - start_time,
                cpu_percent=(cpu_after - cpu_before),
                memory_usage=(mem_after - mem_before),
                memory_peak=peak / 1024 / 1024,  # MB
            )

            self.metrics.append(metrics)
            return Success(metrics)

        except Exception as e:
            return Failure(f"Async performance measurement failed: {str(e)}")

    def get_summary(self) -> Dict[str, float]:
        """요약 통계"""
        if not self.metrics:
            return {}

        execution_times = [m.execution_time for m in self.metrics]
        memory_usages = [m.memory_usage for m in self.metrics]

        return {
            "avg_execution_time": sum(execution_times) / len(execution_times),
            "min_execution_time": min(execution_times),
            "max_execution_time": max(execution_times),
            "avg_memory_usage": sum(memory_usages) / len(memory_usages),
            "max_memory_peak": max(m.memory_peak for m in self.metrics),
        }


class LoadTest(PerformanceTest):
    """부하 테스트"""

    def __init__(self, name="LoadTest", concurrent_users=10):
        """초기화"""
        super().__init__(name)
        self.concurrent_users = concurrent_users

    async def run(
        self, func: Callable, duration: float = 10.0, *args, **kwargs
    ) -> Result[Dict[str, Any], str]:
        """부하 테스트 실행"""
        try:
            start_time = time.time()
            tasks = []
            request_times = []

            async def worker():
                while time.time() - start_time < duration:
                    req_start = time.perf_counter()
                    await func(*args, **kwargs)
                    req_end = time.perf_counter()
                    request_times.append(req_end - req_start)
                    await asyncio.sleep(0.01)  # 짧은 대기

            # 동시 사용자 시뮬레이션
            for _ in range(self.concurrent_users):
                tasks.append(asyncio.create_task(worker()))

            await asyncio.gather(*tasks)

            # 통계 계산
            if request_times:
                request_times.sort()
                total_requests = len(request_times)

                results = {
                    "total_requests": total_requests,
                    "duration": duration,
                    "concurrent_users": self.concurrent_users,
                    "throughput": total_requests / duration,
                    "avg_latency": sum(request_times) / total_requests,
                    "min_latency": request_times[0],
                    "max_latency": request_times[-1],
                    "p50_latency": request_times[int(total_requests * 0.5)],
                    "p95_latency": request_times[int(total_requests * 0.95)],
                    "p99_latency": request_times[int(total_requests * 0.99)],
                }

                return Success(results)

            return Failure("No requests completed")

        except Exception as e:
            return Failure(f"Load test failed: {str(e)}")


class StressTest(PerformanceTest):
    """스트레스 테스트"""

    def __init__(self, name="StressTest"):
        """초기화"""
        super().__init__(name)
        self.breaking_point = None

    async def find_breaking_point(
        self,
        func: Callable,
        initial_load=10,
        step=10,
        max_load=1000,
        threshold_ms: float = 1000.0,
    ) -> Result[int, str]:
        """임계점 찾기"""
        try:
            current_load = initial_load

            while current_load <= max_load:
                # 현재 부하로 테스트
                load_test = LoadTest(concurrent_users=current_load)
                result = await load_test.run(func, duration=5.0)

                if isinstance(result, Success):
                    metrics = result.value
                    avg_latency_ms = metrics["avg_latency"] * 1000

                    # 임계점 확인
                    if avg_latency_ms > threshold_ms:
                        self.breaking_point = current_load
                        return Success(current_load)

                current_load += step

            return Success(max_load)  # 최대 부하에서도 안정적

        except Exception as e:
            return Failure(f"Stress test failed: {str(e)}")


# 벤치마크 데코레이터
def benchmark(iterations=100) -> Callable:
    """벤치마크 데코레이터"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            times = []

            for _ in range(iterations):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                end = time.perf_counter()
                times.append(end - start)

            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            print(f"Benchmark results for {func.__name__}:")
            print(f"  Iterations: {iterations}")
            print(f"  Average: {avg_time*1000:.3f}ms")
            print(f"  Min: {min_time*1000:.3f}ms")
            print(f"  Max: {max_time*1000:.3f}ms")

            return result

        return wrapper

    return decorator


def measure_performance(func: Callable) -> Callable:
    """성능 측정 데코레이터"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        test = PerformanceTest(func.__name__)
        result = test.measure(func, *args, **kwargs)

        if isinstance(result, Success):
            metrics = result.value
            print(f"Performance metrics for {func.__name__}:")
            print(f"  Execution time: {metrics.execution_time*1000:.3f}ms")
            print(f"  Memory usage: {metrics.memory_usage:.2f}MB")
            print(f"  Memory peak: {metrics.memory_peak:.2f}MB")

        return func(*args, **kwargs)

    return wrapper


def profile_function(func: Callable) -> Callable:
    """프로파일링 데코레이터"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        import cProfile
        import io
        import pstats

        profiler = cProfile.Profile()
        profiler.enable()

        result = func(*args, **kwargs)

        profiler.disable()

        # 프로파일 결과 출력
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(10)  # 상위 10개

        print(f"Profile results for {func.__name__}:")
        print(stream.getvalue())

        return result

    return wrapper


# Assertion 함수들
def assert_performance(
    metrics: PerformanceMetrics,
    max_execution_time=None,
    max_memory_usage=None,
) -> Result[None, str]:
    """성능 assertion"""
    if max_execution_time and metrics.execution_time > max_execution_time:
        return Failure(
            f"Execution time {metrics.execution_time:.3f}s exceeds "
            f"maximum {max_execution_time:.3f}s"
        )

    if max_memory_usage and metrics.memory_usage > max_memory_usage:
        return Failure(
            f"Memory usage {metrics.memory_usage:.2f}MB exceeds "
            f"maximum {max_memory_usage:.2f}MB"
        )

    return Success(None)


def assert_response_time(response_time: float, max_time: float) -> Result[None, str]:
    """응답 시간 assertion"""
    if response_time > max_time:
        return Failure(
            f"Response time {response_time:.3f}s exceeds " f"maximum {max_time:.3f}s"
        )
    return Success(None)


def assert_throughput(throughput: float, min_throughput: float) -> Result[None, str]:
    """처리량 assertion"""
    if throughput < min_throughput:
        return Failure(
            f"Throughput {throughput:.2f} req/s is below "
            f"minimum {min_throughput:.2f} req/s"
        )
    return Success(None)


def assert_memory_usage(memory_mb: float, max_memory_mb: float) -> Result[None, str]:
    """메모리 사용량 assertion"""
    if memory_mb > max_memory_mb:
        return Failure(
            f"Memory usage {memory_mb:.2f}MB exceeds " f"maximum {max_memory_mb:.2f}MB"
        )
    return Success(None)


__all__ = [
    "PerformanceMetrics",
    "PerformanceTest",
    "LoadTest",
    "StressTest",
    "benchmark",
    "measure_performance",
    "profile_function",
    "assert_performance",
    "assert_response_time",
    "assert_throughput",
    "assert_memory_usage",
]
