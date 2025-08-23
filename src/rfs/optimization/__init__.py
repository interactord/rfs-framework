"""
Performance Optimization Framework (RFS)

RFS 성능 최적화 및 튜닝 프레임워크
- 자동 성능 프로파일링
- 메모리 최적화
- CPU 사용량 최적화
- I/O 최적화
- Cloud Run 전용 최적화
"""

from .optimizer import PerformanceOptimizer, OptimizationSuite, OptimizationResult, OptimizationType, OptimizationCategory

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
ColdStartOptimizer = None
ScalingOptimizer = None

__all__ = [
    # 핵심 최적화 시스템
    "PerformanceOptimizer", "OptimizationSuite", "OptimizationResult",
    
    # 프로파일러
    "SystemProfiler", "MemoryProfiler", "CPUProfiler", "IOProfiler",
    
    # 메모리 최적화
    "MemoryOptimizer", "GarbageCollectionTuner", "ObjectPooling",
    
    # CPU 최적화
    "CPUOptimizer", "ConcurrencyTuner", "AsyncOptimizer",
    
    # I/O 최적화
    "IOOptimizer", "DatabaseOptimizer", "NetworkOptimizer",
    
    # Cloud Run 최적화
    "CloudRunOptimizer", "ColdStartOptimizer", "ScalingOptimizer"
]