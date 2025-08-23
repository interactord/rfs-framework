"""
RFS v4.1 Cold Start Optimizer
서버리스 환경(Cloud Run)에서 Cold Start 지연 최소화

주요 기능:
- 모듈 사전 로딩
- 캐시 워밍업
- 메모리 최적화
- 시작 시간 측정 및 분석
- 성능 메트릭 수집
"""

import time
import asyncio
import gc
import sys
import importlib
import threading
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import psutil
import os

logger = logging.getLogger(__name__)


class OptimizationLevel(Enum):
    """최적화 수준"""
    MINIMAL = "minimal"      # 기본적인 최적화만
    MODERATE = "moderate"    # 균형있는 최적화
    AGGRESSIVE = "aggressive" # 최대 성능 최적화


@dataclass
class StartupMetrics:
    """시작 메트릭"""
    total_startup_time: float = 0.0
    import_time: float = 0.0
    initialization_time: float = 0.0
    warmup_time: float = 0.0
    gc_time: float = 0.0
    
    # 메모리 메트릭
    initial_memory_mb: float = 0.0
    final_memory_mb: float = 0.0
    memory_saved_mb: float = 0.0
    
    # 모듈 메트릭
    preloaded_modules: int = 0
    failed_imports: int = 0
    cached_objects: int = 0
    
    # 시스템 메트릭
    cpu_cores: int = 0
    available_memory_mb: float = 0.0
    python_version: str = ""
    
    def __post_init__(self):
        if not self.python_version:
            self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if not self.cpu_cores:
            self.cpu_cores = os.cpu_count() or 1
        if not self.available_memory_mb:
            self.available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)


@dataclass
class OptimizationConfig:
    """최적화 설정"""
    level: OptimizationLevel = OptimizationLevel.MODERATE
    
    # 모듈 사전 로딩
    preload_modules: List[str] = field(default_factory=list)
    preload_patterns: List[str] = field(default_factory=list)  # 패턴 기반 로딩
    max_preload_time: float = 5.0  # 최대 사전 로딩 시간 (초)
    
    # 캐시 워밍업
    enable_cache_warmup: bool = True
    cache_warmup_functions: List[Callable] = field(default_factory=list)
    max_warmup_time: float = 3.0  # 최대 워밍업 시간 (초)
    
    # 메모리 최적화
    enable_gc_optimization: bool = True
    gc_freeze: bool = True  # GC freeze로 성능 향상
    memory_threshold_mb: float = 100.0  # 메모리 임계값
    
    # 동시성 설정
    max_workers: int = 4  # 병렬 처리 워커 수
    enable_async_warmup: bool = True
    
    # 모니터링
    collect_detailed_metrics: bool = True
    log_optimization_steps: bool = True


class ColdStartOptimizer:
    """
    Cold Start 최적화 핵심 클래스
    
    사용법:
        optimizer = ColdStartOptimizer()
        optimizer.preload_modules(['numpy', 'pandas'])
        await optimizer.warm_up()
        metrics = optimizer.get_metrics()
    """
    
    def __init__(self, config: OptimizationConfig = None):
        self.config = config or OptimizationConfig()
        self.start_time = time.time()
        self.metrics = StartupMetrics()
        
        # 상태 추적
        self._preloaded_modules: Set[str] = set()
        self._warmup_functions: List[Callable] = []
        self._optimization_completed = False
        
        # 성능 추적
        self._phase_times: Dict[str, float] = {}
        self._import_times: Dict[str, float] = {}
        
        # 메모리 초기화
        self.metrics.initial_memory_mb = self._get_memory_usage()
        
        if self.config.log_optimization_steps:
            logger.info(f"ColdStartOptimizer initialized with {self.config.level.value} optimization level")
    
    def preload_modules(self, modules: List[str], timeout: float = None) -> Dict[str, bool]:
        """
        모듈들을 사전 로딩
        
        Args:
            modules: 로딩할 모듈 목록
            timeout: 로딩 타임아웃 (초)
            
        Returns:
            Dict[str, bool]: 모듈별 로딩 성공 여부
        """
        phase_start = time.time()
        timeout = timeout or self.config.max_preload_time
        
        results = {}
        failed_count = 0
        
        if self.config.level == OptimizationLevel.AGGRESSIVE and self.config.max_workers > 1:
            # 병렬 로딩
            results = self._parallel_module_loading(modules, timeout)
            failed_count = sum(1 for success in results.values() if not success)
        else:
            # 순차 로딩
            for module_name in modules:
                start_time = time.time()
                try:
                    importlib.import_module(module_name)
                    self._preloaded_modules.add(module_name)
                    results[module_name] = True
                    
                    import_time = time.time() - start_time
                    self._import_times[module_name] = import_time
                    
                    if self.config.log_optimization_steps:
                        logger.debug(f"Preloaded {module_name} in {import_time:.3f}s")
                
                except ImportError as e:
                    results[module_name] = False
                    failed_count += 1
                    if self.config.log_optimization_steps:
                        logger.warning(f"Failed to preload {module_name}: {e}")
                
                except Exception as e:
                    results[module_name] = False
                    failed_count += 1
                    logger.error(f"Error preloading {module_name}: {e}")
                
                # 타임아웃 체크
                if time.time() - phase_start > timeout:
                    logger.warning(f"Module preloading timeout after {timeout}s")
                    break
        
        phase_time = time.time() - phase_start
        self._phase_times['preload'] = phase_time
        self.metrics.import_time = phase_time
        self.metrics.preloaded_modules = len(self._preloaded_modules)
        self.metrics.failed_imports = failed_count
        
        if self.config.log_optimization_steps:
            logger.info(f"Preloaded {len(self._preloaded_modules)} modules in {phase_time:.3f}s")
        
        return results
    
    def _parallel_module_loading(self, modules: List[str], timeout: float) -> Dict[str, bool]:
        """병렬 모듈 로딩"""
        results = {}
        
        def load_module(module_name: str) -> tuple[str, bool, float]:
            start_time = time.time()
            try:
                importlib.import_module(module_name)
                load_time = time.time() - start_time
                return module_name, True, load_time
            except Exception:
                load_time = time.time() - start_time
                return module_name, False, load_time
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # 모든 모듈 로딩 작업 제출
            future_to_module = {
                executor.submit(load_module, module): module 
                for module in modules
            }
            
            # 결과 수집 (타임아웃 포함)
            for future in as_completed(future_to_module, timeout=timeout):
                try:
                    module_name, success, load_time = future.result()
                    results[module_name] = success
                    self._import_times[module_name] = load_time
                    
                    if success:
                        self._preloaded_modules.add(module_name)
                
                except Exception as e:
                    module_name = future_to_module[future]
                    results[module_name] = False
                    logger.error(f"Parallel loading error for {module_name}: {e}")
        
        return results
    
    def register_warmup_function(self, func: Callable, priority: int = 0) -> None:
        """
        워밍업 함수 등록
        
        Args:
            func: 워밍업 함수
            priority: 우선순위 (낮을수록 먼저 실행)
        """
        self._warmup_functions.append((priority, func))
        # 우선순위로 정렬
        self._warmup_functions.sort(key=lambda x: x[0])
    
    async def warm_up(self, timeout: float = None) -> Dict[str, Any]:
        """
        캐시 및 연결 워밍업
        
        Args:
            timeout: 워밍업 타임아웃 (초)
            
        Returns:
            Dict[str, Any]: 워밍업 결과
        """
        if not self.config.enable_cache_warmup:
            return {"skipped": True, "reason": "cache warmup disabled"}
        
        phase_start = time.time()
        timeout = timeout or self.config.max_warmup_time
        
        results = {
            "successful": 0,
            "failed": 0,
            "total_time": 0.0,
            "function_results": {}
        }
        
        # 등록된 워밍업 함수들 실행
        warmup_functions = self._warmup_functions + [(999, func) for func in self.config.cache_warmup_functions]
        
        if self.config.enable_async_warmup:
            results = await self._async_warmup(warmup_functions, timeout)
        else:
            results = await self._sync_warmup(warmup_functions, timeout)
        
        phase_time = time.time() - phase_start
        self._phase_times['warmup'] = phase_time
        self.metrics.warmup_time = phase_time
        results["total_time"] = phase_time
        
        if self.config.log_optimization_steps:
            logger.info(f"Warmup completed in {phase_time:.3f}s: {results['successful']} success, {results['failed']} failed")
        
        return results
    
    async def _async_warmup(self, warmup_functions: List[tuple], timeout: float) -> Dict[str, Any]:
        """비동기 워밍업 실행"""
        results = {"successful": 0, "failed": 0, "function_results": {}}
        
        async def execute_warmup(priority_func_tuple):
            priority, func = priority_func_tuple
            func_name = getattr(func, '__name__', str(func))
            
            try:
                start_time = time.time()
                
                if asyncio.iscoroutinefunction(func):
                    result = await func()
                else:
                    result = func()
                
                exec_time = time.time() - start_time
                results["function_results"][func_name] = {
                    "success": True,
                    "result": result,
                    "execution_time": exec_time
                }
                results["successful"] += 1
                
            except Exception as e:
                exec_time = time.time() - start_time
                results["function_results"][func_name] = {
                    "success": False,
                    "error": str(e),
                    "execution_time": exec_time
                }
                results["failed"] += 1
                
                if self.config.log_optimization_steps:
                    logger.warning(f"Warmup function {func_name} failed: {e}")
        
        # 모든 워밍업 함수 비동기 실행
        tasks = [execute_warmup(pf) for pf in warmup_functions]
        
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Warmup timeout after {timeout}s")
        
        return results
    
    async def _sync_warmup(self, warmup_functions: List[tuple], timeout: float) -> Dict[str, Any]:
        """동기 워밍업 실행"""
        results = {"successful": 0, "failed": 0, "function_results": {}}
        start_time = time.time()
        
        for priority, func in warmup_functions:
            if time.time() - start_time > timeout:
                logger.warning(f"Warmup timeout after {timeout}s")
                break
            
            func_name = getattr(func, '__name__', str(func))
            
            try:
                func_start = time.time()
                
                if asyncio.iscoroutinefunction(func):
                    result = await func()
                else:
                    result = func()
                
                exec_time = time.time() - func_start
                results["function_results"][func_name] = {
                    "success": True,
                    "result": result,
                    "execution_time": exec_time
                }
                results["successful"] += 1
                
            except Exception as e:
                exec_time = time.time() - func_start
                results["function_results"][func_name] = {
                    "success": False,
                    "error": str(e),
                    "execution_time": exec_time
                }
                results["failed"] += 1
                
                if self.config.log_optimization_steps:
                    logger.warning(f"Warmup function {func_name} failed: {e}")
        
        return results
    
    def optimize_memory(self) -> Dict[str, Any]:
        """
        메모리 사용 최적화
        
        Returns:
            Dict[str, Any]: 메모리 최적화 결과
        """
        if not self.config.enable_gc_optimization:
            return {"skipped": True, "reason": "gc optimization disabled"}
        
        phase_start = time.time()
        initial_memory = self._get_memory_usage()
        
        optimization_results = {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": 0.0,
            "memory_freed_mb": 0.0,
            "gc_collections": 0,
            "optimization_time": 0.0
        }
        
        try:
            # 1. 강제 가비지 컬렉션
            collected_objects = []
            for generation in range(3):
                collected = gc.collect()
                collected_objects.append(collected)
                optimization_results["gc_collections"] += collected
            
            # 2. GC 통계 확인
            gc_stats = gc.get_stats()
            if self.config.collect_detailed_metrics:
                optimization_results["gc_stats"] = gc_stats
            
            # 3. GC freeze (성능 향상)
            if self.config.gc_freeze and hasattr(gc, 'freeze'):
                gc.freeze()
                optimization_results["gc_frozen"] = True
            
            # 4. 메모리 사용량 재측정
            final_memory = self._get_memory_usage()
            optimization_results["final_memory_mb"] = final_memory
            optimization_results["memory_freed_mb"] = max(0, initial_memory - final_memory)
            
            # 5. GC 임계값 조정 (aggressive 모드)
            if self.config.level == OptimizationLevel.AGGRESSIVE:
                # GC 임계값을 늘려서 빈도 줄이기
                original_thresholds = gc.get_threshold()
                new_thresholds = (original_thresholds[0] * 2, 
                                original_thresholds[1] * 2, 
                                original_thresholds[2] * 2)
                gc.set_threshold(*new_thresholds)
                optimization_results["gc_thresholds"] = {
                    "original": original_thresholds,
                    "new": new_thresholds
                }
        
        except Exception as e:
            optimization_results["error"] = str(e)
            logger.error(f"Memory optimization error: {e}")
        
        phase_time = time.time() - phase_start
        optimization_results["optimization_time"] = phase_time
        self._phase_times['memory_optimization'] = phase_time
        self.metrics.gc_time = phase_time
        self.metrics.memory_saved_mb = optimization_results["memory_freed_mb"]
        
        if self.config.log_optimization_steps:
            logger.info(f"Memory optimization completed in {phase_time:.3f}s, freed {optimization_results['memory_freed_mb']:.1f}MB")
        
        return optimization_results
    
    def _get_memory_usage(self) -> float:
        """현재 메모리 사용량 조회 (MB)"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0
    
    def get_metrics(self) -> StartupMetrics:
        """시작 메트릭 조회"""
        if not self._optimization_completed:
            self._finalize_metrics()
        
        return self.metrics
    
    def _finalize_metrics(self):
        """메트릭 최종화"""
        self.metrics.total_startup_time = time.time() - self.start_time
        self.metrics.final_memory_mb = self._get_memory_usage()
        
        # 초기화 시간 계산 (전체 - 명시적 단계들)
        explicit_time = (self.metrics.import_time + 
                        self.metrics.warmup_time + 
                        self.metrics.gc_time)
        self.metrics.initialization_time = max(0, self.metrics.total_startup_time - explicit_time)
        
        self._optimization_completed = True
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """상세 최적화 보고서"""
        metrics = self.get_metrics()
        
        report = {
            "optimization_config": {
                "level": self.config.level.value,
                "max_preload_time": self.config.max_preload_time,
                "max_warmup_time": self.config.max_warmup_time,
                "max_workers": self.config.max_workers,
            },
            "startup_metrics": {
                "total_startup_time": metrics.total_startup_time,
                "import_time": metrics.import_time,
                "initialization_time": metrics.initialization_time,
                "warmup_time": metrics.warmup_time,
                "gc_time": metrics.gc_time,
            },
            "module_metrics": {
                "preloaded_modules": metrics.preloaded_modules,
                "failed_imports": metrics.failed_imports,
                "import_details": self._import_times.copy(),
            },
            "memory_metrics": {
                "initial_memory_mb": metrics.initial_memory_mb,
                "final_memory_mb": metrics.final_memory_mb,
                "memory_saved_mb": metrics.memory_saved_mb,
                "available_memory_mb": metrics.available_memory_mb,
            },
            "system_info": {
                "cpu_cores": metrics.cpu_cores,
                "python_version": metrics.python_version,
            },
            "phase_times": self._phase_times.copy(),
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """성능 개선 추천사항 생성"""
        recommendations = []
        metrics = self.get_metrics()
        
        # 시작 시간 기반 추천
        if metrics.total_startup_time > 5.0:
            recommendations.append("Consider reducing the number of preloaded modules")
        
        # 메모리 기반 추천
        if metrics.final_memory_mb > 200:
            recommendations.append("Consider enabling more aggressive memory optimization")
        
        # Import 시간 기반 추천
        if metrics.import_time > 3.0:
            recommendations.append("Consider async module loading or reducing module dependencies")
        
        # 실패율 기반 추천
        if metrics.failed_imports > 0:
            recommendations.append("Review and update the list of preloaded modules")
        
        # 시스템 리소스 기반 추천
        if metrics.cpu_cores > 2 and self.config.max_workers < metrics.cpu_cores:
            recommendations.append(f"Consider increasing max_workers to {metrics.cpu_cores} for better parallel performance")
        
        return recommendations
    
    def export_metrics_json(self) -> str:
        """메트릭을 JSON으로 export"""
        import json
        report = self.get_detailed_report()
        return json.dumps(report, indent=2, default=str)


# 편의 함수들
def create_optimizer(level: OptimizationLevel = OptimizationLevel.MODERATE,
                    modules: List[str] = None,
                    warmup_functions: List[Callable] = None) -> ColdStartOptimizer:
    """
    Cold Start Optimizer 생성 편의 함수
    
    Args:
        level: 최적화 수준
        modules: 사전 로딩할 모듈들
        warmup_functions: 워밍업 함수들
        
    Returns:
        ColdStartOptimizer: 설정된 옵티마이저
    """
    config = OptimizationConfig(
        level=level,
        preload_modules=modules or [],
        cache_warmup_functions=warmup_functions or []
    )
    
    return ColdStartOptimizer(config)


async def quick_optimize(modules: List[str] = None,
                        warmup_functions: List[Callable] = None,
                        level: OptimizationLevel = OptimizationLevel.MODERATE) -> StartupMetrics:
    """
    빠른 최적화 실행 함수
    
    Args:
        modules: 사전 로딩할 모듈들
        warmup_functions: 워밍업 함수들
        level: 최적화 수준
        
    Returns:
        StartupMetrics: 최적화 결과 메트릭
    """
    optimizer = create_optimizer(level, modules, warmup_functions)
    
    # 모듈 사전 로딩
    if modules:
        optimizer.preload_modules(modules)
    
    # 워밍업 실행
    await optimizer.warm_up()
    
    # 메모리 최적화
    optimizer.optimize_memory()
    
    return optimizer.get_metrics()


# 예제 및 테스트
if __name__ == "__main__":
    async def example_usage():
        """사용 예제"""
        print("🚀 RFS Cold Start Optimizer Example")
        
        # 1. 기본 사용법
        optimizer = ColdStartOptimizer()
        
        # 2. 모듈 사전 로딩
        common_modules = ['json', 'datetime', 'uuid', 'logging']
        results = optimizer.preload_modules(common_modules)
        print(f"Preloaded modules: {sum(results.values())}/{len(results)}")
        
        # 3. 워밍업 함수 등록
        def cache_warmup():
            """캐시 워밍업 예제"""
            return {"cache": "warmed"}
        
        async def async_warmup():
            """비동기 워밍업 예제"""
            await asyncio.sleep(0.1)  # 비동기 작업 시뮬레이션
            return {"async_cache": "warmed"}
        
        optimizer.register_warmup_function(cache_warmup)
        optimizer.register_warmup_function(async_warmup)
        
        # 4. 워밍업 실행
        warmup_results = await optimizer.warm_up()
        print(f"Warmup completed: {warmup_results['successful']} successful")
        
        # 5. 메모리 최적화
        memory_results = optimizer.optimize_memory()
        print(f"Memory optimized: freed {memory_results.get('memory_freed_mb', 0):.1f}MB")
        
        # 6. 메트릭 조회
        metrics = optimizer.get_metrics()
        print(f"Total startup time: {metrics.total_startup_time:.3f}s")
        print(f"Import time: {metrics.import_time:.3f}s")
        print(f"Warmup time: {metrics.warmup_time:.3f}s")
        print(f"Memory usage: {metrics.final_memory_mb:.1f}MB")
        
        # 7. 상세 보고서
        report = optimizer.get_detailed_report()
        print(f"\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")
        
        # 8. 빠른 최적화 예제
        print("\n🏃 Quick optimization example:")
        quick_metrics = await quick_optimize(
            modules=['os', 'sys', 'time'],
            level=OptimizationLevel.AGGRESSIVE
        )
        print(f"Quick optimization completed in {quick_metrics.total_startup_time:.3f}s")
    
    asyncio.run(example_usage())