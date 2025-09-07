"""
Performance Optimization Integration Tests
"""

import asyncio
import time
from typing import Any, Dict

import pytest

from rfs.core import Failure, Success
from rfs.optimization import (
    OptimizationStrategy,
    get_cloud_run_optimizer,
    get_cpu_optimizer,
    get_memory_optimizer,
)
from rfs.optimization.profiling import SystemProfiler, get_system_profiler


@pytest.mark.asyncio
class TestPerformanceOptimization:
    """성능 최적화 통합 테스트"""

    async def test_system_profiling(self):
        """시스템 프로파일링 테스트"""
        profiler = get_system_profiler()

        # 프로파일러 시작
        start_result = await profiler.start()
        assert isinstance(start_result, Success)

        # 프로파일 시작
        profile_result = await profiler.start_profile(
            "test_operation", level=ProfileLevel.DETAILED
        )
        assert isinstance(profile_result, Success)

        # 테스트 작업 수행
        await asyncio.sleep(0.1)
        data = list(range(1000000))  # 메모리 사용
        sum(data)  # CPU 사용

        # 프로파일 종료
        stop_result = await profiler.stop_profile("test_operation")
        assert isinstance(stop_result, Success)

        profile = stop_result.value
        assert profile.operation_name == "test_operation"
        assert profile.duration > 0
        assert profile.memory_used > 0
        assert profile.cpu_usage >= 0

        # 프로파일러 중지
        await profiler.stop()

    async def test_cloud_run_optimization(self):
        """Cloud Run 최적화 테스트"""
        optimizer = get_cloud_run_optimizer()

        # 최적화 수행
        optimization_result = await optimizer.optimize()
        assert isinstance(optimization_result, Success)

        recommendations = optimization_result.value
        assert "concurrency" in recommendations
        assert "memory" in recommendations
        assert "cpu" in recommendations

        # 자동 스케일링 설정
        scaling_result = await optimizer.configure_autoscaling(
            min_instances=1, max_instances=10, target_cpu_utilization=80
        )
        assert isinstance(scaling_result, Success)

    async def test_memory_optimization(self):
        """메모리 최적화 테스트"""
        optimizer = get_memory_optimizer()

        # 최적화 시작
        start_result = await optimizer.start()
        assert isinstance(start_result, Success)

        # 메모리 사용량 분석
        analysis_result = await optimizer.analyze()
        assert isinstance(analysis_result, Success)

        analysis = analysis_result.value
        assert "total_memory" in analysis
        assert "used_memory" in analysis
        assert "available_memory" in analysis

        # 최적화 수행
        optimization_result = await optimizer.optimize(
            strategy=OptimizationStrategy.AGGRESSIVE
        )
        assert isinstance(optimization_result, Success)

        # 최적화 중지
        await optimizer.stop()

    async def test_cpu_optimization(self):
        """CPU 최적화 테스트"""
        optimizer = get_cpu_optimizer()

        # CPU 바운드 작업 감지
        def cpu_intensive_task():
            return sum(i * i for i in range(1000000))

        # 최적화 전 실행
        start_time = time.time()
        result = cpu_intensive_task()
        original_time = time.time() - start_time

        # 최적화 수행
        optimization_result = await optimizer.optimize()
        assert isinstance(optimization_result, Success)

        # CPU 친화도 설정
        affinity_result = await optimizer.set_cpu_affinity([0, 1])
        assert isinstance(affinity_result, Success)

    async def test_optimization_pipeline(self):
        """최적화 파이프라인 테스트"""
        # 프로파일링
        profiler = get_system_profiler()
        await profiler.start()

        # 프로파일 수집
        await profiler.start_profile("pipeline_test")

        # 시뮬레이션 작업
        await asyncio.sleep(0.1)

        await profiler.stop_profile("pipeline_test")

        # 각 최적화 수행
        optimizers = [
            get_memory_optimizer(),
            get_cpu_optimizer(),
            get_cloud_run_optimizer(),
        ]

        for optimizer in optimizers:
            if hasattr(optimizer, "start"):
                await optimizer.start()

            result = await optimizer.optimize()
            assert isinstance(result, Success)

            if hasattr(optimizer, "stop"):
                await optimizer.stop()

        await profiler.stop()


@pytest.mark.asyncio
class TestOptimizationStrategies:
    """최적화 전략 테스트"""

    async def test_conservative_strategy(self):
        """보수적 전략 테스트"""
        optimizer = get_memory_optimizer()

        result = await optimizer.optimize(strategy=OptimizationStrategy.CONSERVATIVE)
        assert isinstance(result, Success)

        # 보수적 전략은 안전한 최적화만 수행
        recommendations = result.value
        assert recommendations["risk_level"] == "low"

    async def test_balanced_strategy(self):
        """균형 전략 테스트"""
        optimizer = get_cpu_optimizer()

        result = await optimizer.optimize(strategy=OptimizationStrategy.BALANCED)
        assert isinstance(result, Success)

        recommendations = result.value
        assert recommendations["risk_level"] == "medium"

    async def test_aggressive_strategy(self):
        """공격적 전략 테스트"""
        optimizer = get_cloud_run_optimizer()

        result = await optimizer.optimize(strategy=OptimizationStrategy.AGGRESSIVE)
        assert isinstance(result, Success)

        recommendations = result.value
        assert recommendations["risk_level"] == "high"
