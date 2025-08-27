"""
RFS Performance Profiling Suite (RFS v4.2)

종합적인 성능 프로파일링 시스템
- 시스템 리소스 모니터링
- 메모리 사용량 분석
- CPU 성능 프로파일링
- I/O 성능 분석
- 실시간 성능 대시보드
"""

from .cpu_profiler import CPUMetrics, CPUProfiler, CPUSnapshot
from .io_profiler import IOMetrics, IOProfiler, IOSnapshot
from .memory_profiler import MemoryMetrics, MemoryProfiler, MemorySnapshot
from .system_profiler import ResourceUsage, SystemMetrics, SystemProfiler

# 전역 프로파일러 인스턴스
_system_profiler = None
_memory_profiler = None
_cpu_profiler = None
_io_profiler = None
_profiling_dashboard = None
_performance_analyzer = None


def get_system_profiler() -> SystemProfiler:
    """전역 시스템 프로파일러 인스턴스 반환"""
    # global _system_profiler - removed for functional programming
    if _system_profiler is None:
        _system_profiler = SystemProfiler()
    return _system_profiler


def get_memory_profiler() -> MemoryProfiler:
    """전역 메모리 프로파일러 인스턴스 반환"""
    # global _memory_profiler - removed for functional programming
    if _memory_profiler is None:
        _memory_profiler = MemoryProfiler()
    return _memory_profiler


def get_cpu_profiler() -> CPUProfiler:
    """전역 CPU 프로파일러 인스턴스 반환"""
    # global _cpu_profiler - removed for functional programming
    if _cpu_profiler is None:
        _cpu_profiler = CPUProfiler()
    return _cpu_profiler


def get_io_profiler() -> IOProfiler:
    """전역 I/O 프로파일러 인스턴스 반환"""
    # global _io_profiler - removed for functional programming
    if _io_profiler is None:
        _io_profiler = IOProfiler()
    return _io_profiler


# 편의 함수들
async def start_profiling():
    """모든 프로파일러 시작"""
    await get_system_profiler().start()
    await get_memory_profiler().start()
    await get_cpu_profiler().start()
    await get_io_profiler().start()


async def stop_profiling():
    """모든 프로파일러 중지"""
    await get_system_profiler().stop()
    await get_memory_profiler().stop()
    await get_cpu_profiler().stop()
    await get_io_profiler().stop()


__all__ = [
    # Core Profilers
    "SystemProfiler",
    "SystemMetrics",
    "ResourceUsage",
    "MemoryProfiler",
    "MemoryMetrics",
    "MemorySnapshot",
    "CPUProfiler",
    "CPUMetrics",
    "CPUSnapshot",
    "IOProfiler",
    "IOMetrics",
    "IOSnapshot",
    # Factory Functions
    "get_system_profiler",
    "get_memory_profiler",
    "get_cpu_profiler",
    "get_io_profiler",
    # Convenience Functions
    "start_profiling",
    "stop_profiling",
]
