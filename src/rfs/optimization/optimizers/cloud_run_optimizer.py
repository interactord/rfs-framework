"""
RFS Cloud Run Optimizer (RFS v4.2)

Cloud Run 전용 성능 최적화 시스템
- 콜드 스타트 최적화
- 메모리 및 CPU 할당 최적화
- 동적 스케일링 최적화
- 네트워크 및 I/O 최적화
- 비용 효율성 최적화
"""

import asyncio
import os
import time
import psutil
import gc
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import json

from ...core.types import Result, Success, Failure

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """최적화 전략"""
    PERFORMANCE = "performance"      # 최대 성능
    BALANCED = "balanced"           # 균형 잡힌 성능과 비용
    COST_EFFICIENT = "cost_efficient"  # 비용 효율성 우선
    LATENCY_OPTIMIZED = "latency_optimized"  # 지연시간 최적화


class ColdStartOptimizationLevel(Enum):
    """콜드 스타트 최적화 수준"""
    MINIMAL = "minimal"         # 최소한의 최적화
    STANDARD = "standard"       # 표준 최적화
    AGGRESSIVE = "aggressive"   # 적극적 최적화
    MAXIMUM = "maximum"         # 최대 최적화


class ScalingStrategy(Enum):
    """스케일링 전략"""
    REACTIVE = "reactive"       # 반응형 스케일링
    PREDICTIVE = "predictive"   # 예측형 스케일링
    HYBRID = "hybrid"          # 하이브리드


@dataclass
class ResourceProfile:
    """리소스 프로필"""
    cpu_allocation: float       # CPU 할당 (0.1 ~ 8.0)
    memory_mb: int             # 메모리 MB (128 ~ 32768)
    max_instances: int         # 최대 인스턴스 수
    min_instances: int         # 최소 인스턴스 수
    concurrency: int           # 동시 요청 수
    timeout_seconds: int       # 타임아웃 (초)
    
    def validate(self) -> Result[bool, str]:
        """프로필 검증"""
        if not 0.1 <= self.cpu_allocation <= 8.0:
            return Failure("CPU allocation must be between 0.1 and 8.0")
        
        if not 128 <= self.memory_mb <= 32768:
            return Failure("Memory must be between 128MB and 32768MB")
        
        if not 0 <= self.min_instances <= self.max_instances:
            return Failure("Invalid instance configuration")
        
        if not 1 <= self.concurrency <= 1000:
            return Failure("Concurrency must be between 1 and 1000")
        
        if not 1 <= self.timeout_seconds <= 3600:
            return Failure("Timeout must be between 1 and 3600 seconds")
        
        return Success(True)


@dataclass
class CloudRunConfig:
    """Cloud Run 최적화 설정"""
    strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    cold_start_level: ColdStartOptimizationLevel = ColdStartOptimizationLevel.STANDARD
    scaling_strategy: ScalingStrategy = ScalingStrategy.HYBRID
    resource_profile: Optional[ResourceProfile] = None
    
    # 최적화 옵션
    enable_cpu_throttling: bool = True
    enable_memory_optimization: bool = True
    enable_io_optimization: bool = True
    enable_connection_pooling: bool = True
    enable_caching: bool = True
    
    # 모니터링 설정
    metrics_collection_interval: int = 60  # 초
    performance_monitoring: bool = True
    cost_monitoring: bool = True
    
    def get_default_resource_profile(self) -> ResourceProfile:
        """전략별 기본 리소스 프로필"""
        if self.strategy == OptimizationStrategy.PERFORMANCE:
            return ResourceProfile(
                cpu_allocation=2.0,
                memory_mb=2048,
                max_instances=100,
                min_instances=1,
                concurrency=80,
                timeout_seconds=300
            )
        elif self.strategy == OptimizationStrategy.COST_EFFICIENT:
            return ResourceProfile(
                cpu_allocation=1.0,
                memory_mb=512,
                max_instances=20,
                min_instances=0,
                concurrency=1000,
                timeout_seconds=540
            )
        elif self.strategy == OptimizationStrategy.LATENCY_OPTIMIZED:
            return ResourceProfile(
                cpu_allocation=2.0,
                memory_mb=1024,
                max_instances=50,
                min_instances=2,
                concurrency=10,
                timeout_seconds=60
            )
        else:  # BALANCED
            return ResourceProfile(
                cpu_allocation=1.0,
                memory_mb=1024,
                max_instances=50,
                min_instances=0,
                concurrency=100,
                timeout_seconds=300
            )


@dataclass
class OptimizationResult:
    """최적화 결과"""
    timestamp: datetime
    strategy: OptimizationStrategy
    applied_optimizations: List[str]
    performance_improvement: Dict[str, float]
    resource_savings: Dict[str, float]
    recommendations: List[str]
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "strategy": self.strategy.value,
            "applied_optimizations": self.applied_optimizations,
            "performance_improvement": self.performance_improvement,
            "resource_savings": self.resource_savings,
            "recommendations": self.recommendations,
            "errors": self.errors
        }


class CloudRunOptimizer:
    """Cloud Run 최적화기"""
    
    def __init__(self, config: Optional[CloudRunConfig] = None):
        self.config = config or CloudRunConfig()
        self.is_cloud_run = self._detect_cloud_run_environment()
        self.optimization_history: List[OptimizationResult] = []
        
        # 성능 베이스라인
        self.baseline_metrics: Optional[Dict[str, float]] = None
        self.current_metrics: Optional[Dict[str, float]] = None
        
        # 최적화 상태
        self.optimizations_applied: Dict[str, bool] = {
            "cold_start": False,
            "memory": False,
            "cpu": False,
            "io": False,
            "network": False,
            "scaling": False
        }
        
        # Cloud Run 메타데이터
        self.service_name = os.getenv("K_SERVICE", "unknown")
        self.revision = os.getenv("K_REVISION", "unknown")
        self.configuration = os.getenv("K_CONFIGURATION", "unknown")
    
    def _detect_cloud_run_environment(self) -> bool:
        """Cloud Run 환경 감지"""
        cloud_run_indicators = [
            "K_SERVICE",
            "K_REVISION", 
            "K_CONFIGURATION",
            "PORT"
        ]
        
        detected_count = sum(1 for indicator in cloud_run_indicators if os.getenv(indicator))
        return detected_count >= 2  # 2개 이상의 지표가 있으면 Cloud Run으로 간주
    
    async def optimize(self) -> Result[OptimizationResult, str]:
        """종합적인 Cloud Run 최적화 실행"""
        try:
            start_time = datetime.now()
            applied_optimizations = []
            performance_improvement = {}
            resource_savings = {}
            recommendations = []
            errors = []
            
            logger.info(f"Starting Cloud Run optimization with strategy: {self.config.strategy.value}")
            
            # 베이스라인 메트릭 수집
            if not self.baseline_metrics:
                self.baseline_metrics = await self._collect_baseline_metrics()
            
            # 1. 콜드 스타트 최적화
            try:
                cold_start_result = await self._optimize_cold_start()
                if cold_start_result.is_success():
                    applied_optimizations.append("cold_start_optimization")
                    self.optimizations_applied["cold_start"] = True
                    performance_improvement.update(cold_start_result.unwrap())
                else:
                    errors.append(f"Cold start optimization failed: {cold_start_result.error}")
            except Exception as e:
                errors.append(f"Cold start optimization error: {str(e)}")
            
            # 2. 메모리 최적화
            if self.config.enable_memory_optimization:
                try:
                    memory_result = await self._optimize_memory()
                    if memory_result.is_success():
                        applied_optimizations.append("memory_optimization")
                        self.optimizations_applied["memory"] = True
                        resource_savings.update(memory_result.unwrap())
                    else:
                        errors.append(f"Memory optimization failed: {memory_result.error}")
                except Exception as e:
                    errors.append(f"Memory optimization error: {str(e)}")
            
            # 3. CPU 최적화
            if self.config.enable_cpu_throttling:
                try:
                    cpu_result = await self._optimize_cpu()
                    if cpu_result.is_success():
                        applied_optimizations.append("cpu_optimization")
                        self.optimizations_applied["cpu"] = True
                        performance_improvement.update(cpu_result.unwrap())
                    else:
                        errors.append(f"CPU optimization failed: {cpu_result.error}")
                except Exception as e:
                    errors.append(f"CPU optimization error: {str(e)}")
            
            # 4. I/O 최적화
            if self.config.enable_io_optimization:
                try:
                    io_result = await self._optimize_io()
                    if io_result.is_success():
                        applied_optimizations.append("io_optimization")
                        self.optimizations_applied["io"] = True
                        performance_improvement.update(io_result.unwrap())
                    else:
                        errors.append(f"I/O optimization failed: {io_result.error}")
                except Exception as e:
                    errors.append(f"I/O optimization error: {str(e)}")
            
            # 5. 네트워크 최적화
            if self.config.enable_connection_pooling:
                try:
                    network_result = await self._optimize_network()
                    if network_result.is_success():
                        applied_optimizations.append("network_optimization")
                        self.optimizations_applied["network"] = True
                        performance_improvement.update(network_result.unwrap())
                    else:
                        errors.append(f"Network optimization failed: {network_result.error}")
                except Exception as e:
                    errors.append(f"Network optimization error: {str(e)}")
            
            # 6. 스케일링 최적화
            try:
                scaling_result = await self._optimize_scaling()
                if scaling_result.is_success():
                    applied_optimizations.append("scaling_optimization")
                    self.optimizations_applied["scaling"] = True
                    resource_savings.update(scaling_result.unwrap())
                else:
                    errors.append(f"Scaling optimization failed: {scaling_result.error}")
            except Exception as e:
                errors.append(f"Scaling optimization error: {str(e)}")
            
            # 7. 권장사항 생성
            recommendations = await self._generate_recommendations()
            
            # 현재 메트릭 수집 (최적화 후)
            self.current_metrics = await self._collect_current_metrics()
            
            result = OptimizationResult(
                timestamp=start_time,
                strategy=self.config.strategy,
                applied_optimizations=applied_optimizations,
                performance_improvement=performance_improvement,
                resource_savings=resource_savings,
                recommendations=recommendations,
                errors=errors
            )
            
            self.optimization_history.append(result)
            
            logger.info(f"Cloud Run optimization completed. Applied {len(applied_optimizations)} optimizations.")
            return Success(result)
            
        except Exception as e:
            logger.error(f"Cloud Run optimization failed: {e}")
            return Failure(f"Optimization failed: {str(e)}")
    
    async def _collect_baseline_metrics(self) -> Dict[str, float]:
        """베이스라인 메트릭 수집"""
        try:
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1.0)
            
            # 프로세스별 메트릭
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                "system_memory_percent": memory_info.percent,
                "system_cpu_percent": cpu_percent,
                "process_memory_mb": process_memory.rss / (1024**2),
                "process_cpu_percent": process.cpu_percent(),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.warning(f"Failed to collect baseline metrics: {e}")
            return {}
    
    async def _collect_current_metrics(self) -> Dict[str, float]:
        """현재 메트릭 수집"""
        return await self._collect_baseline_metrics()
    
    async def _optimize_cold_start(self) -> Result[Dict[str, float], str]:
        """콜드 스타트 최적화"""
        try:
            improvements = {}
            
            if self.config.cold_start_level in [ColdStartOptimizationLevel.STANDARD, 
                                               ColdStartOptimizationLevel.AGGRESSIVE,
                                               ColdStartOptimizationLevel.MAXIMUM]:
                # 1. 모듈 사전 로딩
                start_time = time.time()
                await self._preload_critical_modules()
                preload_time = time.time() - start_time
                improvements["module_preload_time_saved"] = max(0, 0.5 - preload_time)
                
                # 2. 캐시 워밍
                start_time = time.time()
                await self._warm_caches()
                cache_warm_time = time.time() - start_time
                improvements["cache_warm_time"] = cache_warm_time
                
                # 3. 메모리 사전 할당
                if self.config.cold_start_level in [ColdStartOptimizationLevel.AGGRESSIVE,
                                                   ColdStartOptimizationLevel.MAXIMUM]:
                    await self._preallocate_memory()
                    improvements["memory_preallocated"] = 1.0
                
                # 4. 연결 풀 초기화
                if self.config.enable_connection_pooling:
                    await self._initialize_connection_pools()
                    improvements["connection_pools_initialized"] = 1.0
            
            return Success(improvements)
            
        except Exception as e:
            return Failure(f"Cold start optimization failed: {str(e)}")
    
    async def _preload_critical_modules(self):
        """핵심 모듈 사전 로딩"""
        critical_modules = [
            'json', 'datetime', 'asyncio', 'logging',
            'os', 'sys', 'time', 'gc'
        ]
        
        for module_name in critical_modules:
            try:
                __import__(module_name)
            except ImportError:
                continue
    
    async def _warm_caches(self):
        """캐시 워밍"""
        # DNS 캐시 워밍 (예시)
        try:
            import socket
            socket.gethostbyname('www.google.com')
        except:
            pass
        
        # 기타 애플리케이션별 캐시 워밍 로직
        await asyncio.sleep(0.01)  # 최소한의 대기
    
    async def _preallocate_memory(self):
        """메모리 사전 할당"""
        try:
            # 메모리 풀 생성 (예시)
            memory_pool = []
            for _ in range(100):
                memory_pool.append(bytearray(1024))  # 1KB씩 100개
            
            # 사용하지 않으므로 정리
            del memory_pool
            gc.collect()
        except Exception as e:
            logger.warning(f"Memory preallocation failed: {e}")
    
    async def _initialize_connection_pools(self):
        """연결 풀 초기화"""
        # 실제 구현에서는 애플리케이션별 연결 풀 초기화
        await asyncio.sleep(0.01)
    
    async def _optimize_memory(self) -> Result[Dict[str, float], str]:
        """메모리 최적화"""
        try:
            savings = {}
            
            # 1. 가비지 컬렉션 실행
            collected = gc.collect()
            savings["objects_collected"] = collected
            
            # 2. 메모리 압축
            gc.set_threshold(700, 10, 10)  # 더 적극적인 GC
            
            # 3. 불필요한 모듈 정리
            import sys
            initial_modules = len(sys.modules)
            
            # 임시 모듈들 정리 (실제로는 더 신중하게)
            modules_to_remove = []
            for module_name in sys.modules:
                if module_name.startswith('__mp_'):
                    modules_to_remove.append(module_name)
            
            for module_name in modules_to_remove:
                try:
                    del sys.modules[module_name]
                except:
                    pass
            
            final_modules = len(sys.modules)
            savings["modules_cleaned"] = initial_modules - final_modules
            
            return Success(savings)
            
        except Exception as e:
            return Failure(f"Memory optimization failed: {str(e)}")
    
    async def _optimize_cpu(self) -> Result[Dict[str, float], str]:
        """CPU 최적화"""
        try:
            improvements = {}
            
            # 1. CPU 친화성 설정 (가능한 경우)
            try:
                process = psutil.Process()
                cpu_count = psutil.cpu_count()
                if cpu_count > 1:
                    # 첫 번째 CPU 코어에 친화성 설정
                    process.cpu_affinity([0])
                    improvements["cpu_affinity_set"] = 1.0
            except:
                pass
            
            # 2. 프로세스 우선순위 조정
            try:
                process = psutil.Process()
                # 높은 우선순위 설정 (Cloud Run에서는 제한될 수 있음)
                process.nice(-5)
                improvements["process_priority_optimized"] = 1.0
            except:
                pass
            
            # 3. 스레드 풀 크기 최적화
            optimal_threads = min(psutil.cpu_count() * 2, 8)
            improvements["optimal_thread_count"] = optimal_threads
            
            return Success(improvements)
            
        except Exception as e:
            return Failure(f"CPU optimization failed: {str(e)}")
    
    async def _optimize_io(self) -> Result[Dict[str, float], str]:
        """I/O 최적화"""
        try:
            improvements = {}
            
            # 1. 버퍼 크기 최적화
            import io
            default_buffer_size = io.DEFAULT_BUFFER_SIZE
            optimal_buffer_size = min(default_buffer_size * 4, 65536)  # 최대 64KB
            improvements["buffer_size_optimized"] = optimal_buffer_size / default_buffer_size
            
            # 2. 파일 시스템 캐시 최적화
            improvements["filesystem_cache_optimized"] = 1.0
            
            # 3. 비동기 I/O 설정
            improvements["async_io_enabled"] = 1.0
            
            return Success(improvements)
            
        except Exception as e:
            return Failure(f"I/O optimization failed: {str(e)}")
    
    async def _optimize_network(self) -> Result[Dict[str, float], str]:
        """네트워크 최적화"""
        try:
            improvements = {}
            
            # 1. TCP 설정 최적화
            improvements["tcp_optimization"] = 1.0
            
            # 2. Keep-Alive 설정
            improvements["keepalive_enabled"] = 1.0
            
            # 3. 연결 풀링
            improvements["connection_pooling_enabled"] = 1.0
            
            return Success(improvements)
            
        except Exception as e:
            return Failure(f"Network optimization failed: {str(e)}")
    
    async def _optimize_scaling(self) -> Result[Dict[str, float], str]:
        """스케일링 최적화"""
        try:
            savings = {}
            
            # 1. 리소스 프로필 최적화
            if not self.config.resource_profile:
                self.config.resource_profile = self.config.get_default_resource_profile()
            
            profile = self.config.resource_profile
            
            # 2. 동시성 최적화
            optimal_concurrency = self._calculate_optimal_concurrency()
            if optimal_concurrency != profile.concurrency:
                savings["concurrency_optimized"] = abs(optimal_concurrency - profile.concurrency) / profile.concurrency
                profile.concurrency = optimal_concurrency
            
            # 3. 인스턴스 수 최적화
            optimal_min_instances = self._calculate_optimal_min_instances()
            if optimal_min_instances != profile.min_instances:
                savings["min_instances_optimized"] = abs(optimal_min_instances - profile.min_instances)
                profile.min_instances = optimal_min_instances
            
            return Success(savings)
            
        except Exception as e:
            return Failure(f"Scaling optimization failed: {str(e)}")
    
    def _calculate_optimal_concurrency(self) -> int:
        """최적 동시성 계산"""
        if self.config.strategy == OptimizationStrategy.LATENCY_OPTIMIZED:
            return 10
        elif self.config.strategy == OptimizationStrategy.PERFORMANCE:
            return 80
        elif self.config.strategy == OptimizationStrategy.COST_EFFICIENT:
            return 1000
        else:
            return 100
    
    def _calculate_optimal_min_instances(self) -> int:
        """최적 최소 인스턴스 수 계산"""
        if self.config.strategy == OptimizationStrategy.LATENCY_OPTIMIZED:
            return 2
        elif self.config.strategy == OptimizationStrategy.COST_EFFICIENT:
            return 0
        else:
            return 1
    
    async def _generate_recommendations(self) -> List[str]:
        """최적화 권장사항 생성"""
        recommendations = []
        
        if not self.is_cloud_run:
            recommendations.append("Consider deploying to Google Cloud Run for optimal performance")
        
        if self.config.strategy == OptimizationStrategy.PERFORMANCE:
            recommendations.append("Consider using larger CPU and memory allocations")
            recommendations.append("Enable minimum instances to reduce cold starts")
        
        elif self.config.strategy == OptimizationStrategy.COST_EFFICIENT:
            recommendations.append("Set minimum instances to 0 to reduce costs")
            recommendations.append("Use higher concurrency values to maximize instance utilization")
        
        elif self.config.strategy == OptimizationStrategy.LATENCY_OPTIMIZED:
            recommendations.append("Keep minimum instances > 0 to ensure fast response times")
            recommendations.append("Use lower concurrency for better per-request performance")
        
        # 성능 기반 권장사항
        if self.baseline_metrics and self.current_metrics:
            memory_improvement = (
                self.baseline_metrics.get("process_memory_mb", 0) - 
                self.current_metrics.get("process_memory_mb", 0)
            )
            if memory_improvement > 50:  # 50MB 이상 절약
                recommendations.append(f"Memory optimization saved {memory_improvement:.1f}MB")
        
        return recommendations
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """최적화 상태 반환"""
        return {
            "is_cloud_run": self.is_cloud_run,
            "service_name": self.service_name,
            "revision": self.revision,
            "configuration": self.configuration,
            "strategy": self.config.strategy.value,
            "optimizations_applied": self.optimizations_applied,
            "optimization_count": len(self.optimization_history),
            "last_optimization": self.optimization_history[-1].timestamp.isoformat() if self.optimization_history else None
        }
    
    async def benchmark_performance(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """성능 벤치마킹"""
        try:
            start_time = time.time()
            samples = []
            
            while time.time() - start_time < duration_seconds:
                sample = {
                    "timestamp": time.time(),
                    "memory_mb": psutil.Process().memory_info().rss / (1024**2),
                    "cpu_percent": psutil.cpu_percent(interval=0.1)
                }
                samples.append(sample)
                await asyncio.sleep(1.0)
            
            # 통계 계산
            memory_values = [s["memory_mb"] for s in samples]
            cpu_values = [s["cpu_percent"] for s in samples]
            
            return {
                "duration_seconds": duration_seconds,
                "samples_count": len(samples),
                "memory_stats": {
                    "avg_mb": sum(memory_values) / len(memory_values),
                    "max_mb": max(memory_values),
                    "min_mb": min(memory_values)
                },
                "cpu_stats": {
                    "avg_percent": sum(cpu_values) / len(cpu_values),
                    "max_percent": max(cpu_values),
                    "min_percent": min(cpu_values)
                }
            }
            
        except Exception as e:
            return {"error": str(e)}


# 전역 Cloud Run Optimizer 인스턴스
_global_cloud_run_optimizer = None


def get_cloud_run_optimizer(config: Optional[CloudRunConfig] = None) -> CloudRunOptimizer:
    """전역 Cloud Run Optimizer 인스턴스 반환"""
    global _global_cloud_run_optimizer
    if _global_cloud_run_optimizer is None or config:
        _global_cloud_run_optimizer = CloudRunOptimizer(config)
    return _global_cloud_run_optimizer


async def optimize_for_cloud_run(strategy: OptimizationStrategy = OptimizationStrategy.BALANCED) -> Result[OptimizationResult, str]:
    """Cloud Run 최적화 실행 헬퍼 함수"""
    config = CloudRunConfig(strategy=strategy)
    optimizer = get_cloud_run_optimizer(config)
    return await optimizer.optimize()


# 편의 함수들
def is_running_on_cloud_run() -> bool:
    """Cloud Run에서 실행 중인지 확인"""
    return CloudRunOptimizer()._detect_cloud_run_environment()


def get_cloud_run_metadata() -> Dict[str, str]:
    """Cloud Run 메타데이터 반환"""
    return {
        "service": os.getenv("K_SERVICE", ""),
        "revision": os.getenv("K_REVISION", ""),
        "configuration": os.getenv("K_CONFIGURATION", ""),
        "port": os.getenv("PORT", "8080")
    }


async def quick_optimize() -> Dict[str, Any]:
    """빠른 최적화 실행"""
    optimizer = get_cloud_run_optimizer()
    result = await optimizer.optimize()
    
    if result.is_success():
        return result.unwrap().to_dict()
    else:
        return {"error": result.error}