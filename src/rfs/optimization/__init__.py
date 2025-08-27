"""
Performance Optimization Framework (RFS)

RFS 성능 최적화 및 튜닝 프레임워크
- 자동 성능 프로파일링
- 메모리 최적화
- CPU 사용량 최적화
- I/O 최적화
- Cloud Run 전용 최적화
"""

# Cold Start Optimizer (NEW - 구현됨)
from .cold_start_optimizer import (
    CacheWarmupStrategy,
    ColdStartConfig,
    ColdStartOptimizer,
    MemoryOptimizationStrategy,
    OptimizationPhase,
    PreloadingStrategy,
    get_default_cold_start_optimizer,
    measure_cold_start_time,
    optimize_cold_start,
)
from .optimizer import (
    OptimizationCategory,
    OptimizationResult,
    OptimizationSuite,
    OptimizationType,
    PerformanceOptimizer,
)

# 임시로 기본값 설정 (구현 중)
SystemProfiler = None
MemoryProfiler = None
CPUProfiler = None
IOProfiler = None

MemoryOptimizer = None
GarbageCollectionTuner = None
ObjectPooling = None

CPUOptimizer = None
ConcurrencyTuner = None
AsyncOptimizer = None

IOOptimizer = None
DatabaseOptimizer = None
NetworkOptimizer = None

CloudRunOptimizer = None
ScalingOptimizer = None


# Helper functions for backward compatibility
def get_cloud_run_optimizer():
    """Get Cloud Run optimizer instance"""
    from .optimizers.cloud_run_optimizer import LegacyCloudRunOptimizer

    return LegacyCloudRunOptimizer()


def get_memory_optimizer():
    """Get memory optimizer instance"""
    from .optimizers.memory_optimizer import LegacyMemoryOptimizer

    return LegacyMemoryOptimizer()


def get_cpu_optimizer():
    """Get CPU optimizer instance"""
    from .optimizers.cpu_optimizer import LegacyCPUOptimizer

    return LegacyCPUOptimizer()


class OptimizationStrategy:
    """Optimization strategy base class"""

    pass


__all__ = [
    # 핵심 최적화 시스템
    "PerformanceOptimizer",
    "OptimizationSuite",
    "OptimizationResult",
    "OptimizationType",
    "OptimizationCategory",
    # Cold Start Optimizer (NEW - 구현됨)
    "ColdStartOptimizer",
    "ColdStartConfig",
    "OptimizationPhase",
    "PreloadingStrategy",
    "CacheWarmupStrategy",
    "MemoryOptimizationStrategy",
    "get_default_cold_start_optimizer",
    "optimize_cold_start",
    "measure_cold_start_time",
    # 프로파일러
    "SystemProfiler",
    "MemoryProfiler",
    "CPUProfiler",
    "IOProfiler",
    # 메모리 최적화
    "MemoryOptimizer",
    "GarbageCollectionTuner",
    "ObjectPooling",
    # CPU 최적화
    "CPUOptimizer",
    "ConcurrencyTuner",
    "AsyncOptimizer",
    # I/O 최적화
    "IOOptimizer",
    "DatabaseOptimizer",
    "NetworkOptimizer",
    # Cloud Run 최적화
    "CloudRunOptimizer",
    "ScalingOptimizer",
    # Helper functions
    "get_cloud_run_optimizer",
    "get_memory_optimizer",
    "get_cpu_optimizer",
    "OptimizationStrategy",
]
