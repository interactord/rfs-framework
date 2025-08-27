"""
RFS Advanced Optimizers Suite (RFS v4.2)

고급 성능 최적화 시스템
- Cloud Run 전용 최적화
- 메모리 최적화
- CPU 최적화
- I/O 최적화
- 데이터베이스 최적화
- 네트워크 최적화
- 스케일링 최적화
"""

from typing import Any, Dict

from .cloud_run_optimizer import (
    CloudRunConfig,
    CloudRunOptimizer,
    ColdStartOptimizationLevel,
    OptimizationStrategy,
    ResourceProfile,
    ScalingStrategy,
    get_cloud_run_optimizer,
    optimize_for_cloud_run,
)
from .cpu_optimizer import (
    AsyncOptimizer,
    ConcurrencyTuner,
    CPUOptimizationConfig,
    CPUOptimizationStrategy,
    CPUOptimizer,
    ThreadPoolOptimizer,
    get_cpu_optimizer,
    optimize_cpu_usage,
)
from .database_optimizer import (
    ConnectionPoolOptimizer,
    DatabaseOptimizationConfig,
    DatabaseOptimizer,
    IndexOptimizer,
    QueryOptimizer,
    get_database_optimizer,
    optimize_database_performance,
)
from .io_optimizer import (
    BufferingStrategy,
    CompressionStrategy,
    IOOptimizationConfig,
    IOOptimizationStrategy,
    IOOptimizer,
    get_io_optimizer,
    optimize_io_performance,
)
from .memory_optimizer import (
    GarbageCollectionTuner,
    MemoryOptimizationConfig,
    MemoryOptimizationStrategy,
    MemoryOptimizer,
    ObjectPooling,
    get_memory_optimizer,
    optimize_memory_usage,
)
from .network_optimizer import (
    CachingOptimizer,
    ConnectionOptimizer,
    NetworkOptimizationConfig,
    NetworkOptimizer,
    RequestOptimizer,
    get_network_optimizer,
    optimize_network_performance,
)
from .scaling_optimizer import (
    AutoScalingConfig,
    PredictiveScaling,
    ResourcePrediction,
    ScalingDecisionEngine,
    ScalingOptimizer,
    get_scaling_optimizer,
    optimize_scaling_strategy,
)

_cloud_run_optimizer = None
_memory_optimizer = None
_cpu_optimizer = None
_io_optimizer = None
_database_optimizer = None
_network_optimizer = None
_scaling_optimizer = None


def get_all_optimizers():
    """모든 optimizer 인스턴스 반환"""
    return {
        "cloud_run": get_cloud_run_optimizer(),
        "memory": get_memory_optimizer(),
        "cpu": get_cpu_optimizer(),
        "io": get_io_optimizer(),
        "database": get_database_optimizer(),
        "network": get_network_optimizer(),
        "scaling": get_scaling_optimizer(),
    }


async def run_comprehensive_optimization():
    """종합적인 시스템 최적화 실행"""
    optimizers = get_all_optimizers()
    results = {}
    for name, optimizer in optimizers.items():
        try:
            result = await optimizer.optimize()
            results[name] = {name: result}
        except Exception as e:
            results[name] = {name: {"error": str(e)}}
    return results


__all__ = [
    "CloudRunOptimizer",
    "CloudRunConfig",
    "OptimizationStrategy",
    "ColdStartOptimizationLevel",
    "ScalingStrategy",
    "ResourceProfile",
    "get_cloud_run_optimizer",
    "optimize_for_cloud_run",
    "MemoryOptimizer",
    "MemoryOptimizationConfig",
    "GarbageCollectionTuner",
    "ObjectPooling",
    "MemoryOptimizationStrategy",
    "get_memory_optimizer",
    "optimize_memory_usage",
    "CPUOptimizer",
    "CPUOptimizationConfig",
    "ConcurrencyTuner",
    "AsyncOptimizer",
    "CPUOptimizationStrategy",
    "ThreadPoolOptimizer",
    "get_cpu_optimizer",
    "optimize_cpu_usage",
    "IOOptimizer",
    "IOOptimizationConfig",
    "IOOptimizationStrategy",
    "BufferingStrategy",
    "CompressionStrategy",
    "get_io_optimizer",
    "optimize_io_performance",
    "DatabaseOptimizer",
    "DatabaseOptimizationConfig",
    "QueryOptimizer",
    "ConnectionPoolOptimizer",
    "IndexOptimizer",
    "get_database_optimizer",
    "optimize_database_performance",
    "NetworkOptimizer",
    "NetworkOptimizationConfig",
    "ConnectionOptimizer",
    "RequestOptimizer",
    "CachingOptimizer",
    "get_network_optimizer",
    "optimize_network_performance",
    "ScalingOptimizer",
    "AutoScalingConfig",
    "PredictiveScaling",
    "ScalingDecisionEngine",
    "ResourcePrediction",
    "get_scaling_optimizer",
    "optimize_scaling_strategy",
    "get_all_optimizers",
    "run_comprehensive_optimization",
]
