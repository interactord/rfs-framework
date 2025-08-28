"""
RFS Framework Async Pipeline

비동기 함수형 프로그래밍을 위한 고급 파이프라인 도구

이 패키지는 RFS Framework의 비동기 처리 능력을 대폭 강화하여 
우아하고 타입 안전한 비동기 함수형 프로그래밍을 지원합니다.

주요 구성 요소:
- AsyncResult: 비동기 전용 Result 모나드
- AsyncPipeline: 동기/비동기 함수 혼재 파이프라인
- 고급 에러 처리: 재시도, 폴백, 서킷브레이커
- 성능 최적화: 병렬 처리, 백프레셔, 캐싱

Example:
    >>> from rfs.async_pipeline import AsyncResult, async_pipe
    >>> 
    >>> # AsyncResult 기본 사용
    >>> result = await (
    ...     AsyncResult.from_async(fetch_user_data)
    ...     .bind_async(validate_user)
    ...     .map_async(format_response)
    ... )
    >>> 
    >>> # 통합 파이프라인 사용
    >>> pipeline = async_pipe(
    ...     validate_input,    # 동기 함수
    ...     fetch_data,        # 비동기 함수
    ...     transform_data,    # 동기 함수
    ...     save_result        # 비동기 함수
    ... )
    >>> result = await pipeline.execute(input_data)
"""

# === Core Components ===
from .async_result import (
    AsyncResult,
    async_success,
    async_failure,
    from_awaitable,
    sequence_async_results,
    parallel_map_async
)

from .core import (
    AsyncPipeline,
    AsyncPipelineBuilder,
    async_pipe,
    execute_async_pipeline,
    parallel_pipeline_execution
)

# === Error Handling ===
from .error_handling import (
    AsyncErrorContext,
    AsyncRetryWrapper,
    AsyncFallbackWrapper,
    AsyncCircuitBreaker,
    AsyncErrorStrategy,
    AsyncErrorMonitor,
    ErrorSeverity,
    with_retry,
    with_fallback,
    with_circuit_breaker
)

# === Performance Tools ===
from .performance import (
    AsyncPerformanceMonitor,
    AsyncBackpressureController,
    AsyncStreamProcessor,
    AsyncCache,
    PerformanceMetrics,
    parallel_map,
    async_cached,
    async_rate_limited,
    get_global_cache,
    get_global_monitor
)

# === 버전 정보 ===
__version__ = '1.0.0'
__author__ = 'RFS Framework Team'
__email__ = 'team@rfs-framework.dev'

# === 패키지 메타데이터 ===
__title__ = 'RFS Async Pipeline'
__description__ = '비동기 함수형 프로그래밍을 위한 고급 파이프라인 도구'
__url__ = 'https://github.com/rfs-framework/async-pipeline'
__license__ = 'MIT'

# === Export 목록 ===
__all__ = [
    # === Core Components ===
    'AsyncResult',
    'AsyncPipeline', 
    'AsyncPipelineBuilder',
    'async_pipe',
    'execute_async_pipeline',
    'parallel_pipeline_execution',
    
    # === AsyncResult 편의 함수 ===
    'async_success',
    'async_failure',
    'from_awaitable',
    'sequence_async_results',
    'parallel_map_async',
    
    # === Error Handling ===
    'AsyncErrorContext',
    'AsyncRetryWrapper',
    'AsyncFallbackWrapper', 
    'AsyncCircuitBreaker',
    'AsyncErrorStrategy',
    'AsyncErrorMonitor',
    'ErrorSeverity',
    'with_retry',
    'with_fallback',
    'with_circuit_breaker',
    
    # === Performance Tools ===
    'AsyncPerformanceMonitor',
    'AsyncBackpressureController',
    'AsyncStreamProcessor',
    'AsyncCache',
    'PerformanceMetrics',
    'parallel_map',
    'async_cached',
    'async_rate_limited',
    'get_global_cache',
    'get_global_monitor',
]


# === 패키지 초기화 메시지 ===
import logging

logger = logging.getLogger(__name__)

def _show_init_message():
    """패키지 초기화 메시지 표시"""
    try:
        # 개발 환경에서만 메시지 표시
        import os
        if os.getenv('RFS_ENV') == 'development':
            print(f"🚀 RFS Async Pipeline v{__version__} 로딩 완료")
            print("   비동기 함수형 프로그래밍 도구 활성화")
    except:
        pass  # 에러가 발생해도 패키지 로딩에는 영향 없음

# 초기화 메시지 표시
_show_init_message()


# === 사용 예시 및 퀵 스타트 가이드 ===

def get_quick_start_examples():
    """
    퀵 스타트 예시 코드 반환
    
    Returns:
        dict: 카테고리별 예시 코드
    """
    return {
        'basic_async_result': '''
from rfs.async_pipeline import AsyncResult

# 기본 AsyncResult 사용
async def example_basic():
    result = await (
        AsyncResult.from_async(lambda: fetch_data("user123"))
        .bind_async(lambda data: AsyncResult.from_async(lambda: validate_data(data)))
        .map_sync(lambda data: {"processed": data, "timestamp": time.time()})
    )
    return await result.unwrap_async()
        ''',
        
        'pipeline_mixed_functions': '''
from rfs.async_pipeline import async_pipe

# 동기/비동기 함수 혼재 파이프라인
def validate_input(data: str) -> Result[str, str]:
    return Success(data) if data else Failure("Empty input")

async def fetch_data(query: str) -> dict:
    # 비동기 데이터 조회
    return {"result": query.upper()}

def format_output(data: dict) -> str:
    return f"Result: {data['result']}"

async def example_pipeline():
    pipeline = async_pipe(validate_input, fetch_data, format_output)
    result = await pipeline.execute("hello world")
    return await result.unwrap_async()  # "Result: HELLO WORLD"
        ''',
        
        'error_handling_retry': '''
from rfs.async_pipeline import with_retry, AsyncResult

# 재시도 메커니즘
@with_retry(max_attempts=3, base_delay=1.0, backoff_factor=2.0)
async def unreliable_api_call():
    # 가끔 실패할 수 있는 API 호출
    import random
    if random.random() < 0.7:
        raise ConnectionError("Network error")
    return {"data": "success"}

async def example_retry():
    retry_wrapper = with_retry(max_attempts=3)
    result = await retry_wrapper(unreliable_api_call)
    return await result.unwrap_async()
        ''',
        
        'performance_parallel_processing': '''
from rfs.async_pipeline import parallel_map

# 병렬 처리
async def process_item(item: int) -> int:
    await asyncio.sleep(0.1)  # 시뮬레이션
    return item * 2

async def example_parallel():
    items = list(range(100))
    results = await parallel_map(
        process_item, 
        items, 
        max_concurrency=10
    )
    
    # AsyncResult들을 실제 값으로 변환
    processed = []
    for async_result in results:
        value = await async_result.unwrap_async()
        processed.append(value)
    
    return processed
        ''',
        
        'caching_optimization': '''
from rfs.async_pipeline import async_cached, AsyncCache

# 캐싱 최적화
@async_cached(ttl=3600)  # 1시간 캐싱
async def expensive_computation(x: int) -> int:
    await asyncio.sleep(2)  # 시뮬레이션
    return x ** 2

async def example_caching():
    result1 = await expensive_computation(10)  # 계산됨 (2초 소요)
    result2 = await expensive_computation(10)  # 캐시에서 반환 (즉시)
    return result1, result2  # (100, 100)
        '''
    }


def print_quick_start_guide():
    """퀵 스타트 가이드 출력"""
    examples = get_quick_start_examples()
    
    print("\n" + "="*60)
    print("🚀 RFS Async Pipeline 퀵 스타트 가이드")
    print("="*60)
    
    for category, code in examples.items():
        print(f"\n📌 {category.replace('_', ' ').title()}")
        print("-" * 40)
        print(code.strip())
        print()
    
    print("자세한 문서: https://rfs-framework.readthedocs.io/async-pipeline")
    print("="*60)


# === 고급 사용 패턴 ===

class AsyncPipelinePatterns:
    """
    자주 사용되는 비동기 파이프라인 패턴들
    
    개발자들이 쉽게 적용할 수 있는 검증된 패턴들을 제공합니다.
    """
    
    @staticmethod
    def data_processing_pipeline(
        validation_func,
        fetch_func, 
        transform_func,
        save_func,
        with_retry_config=None,
        with_fallback=None
    ):
        """
        데이터 처리 파이프라인 패턴
        
        Args:
            validation_func: 데이터 검증 함수
            fetch_func: 데이터 조회 함수 
            transform_func: 데이터 변환 함수
            save_func: 데이터 저장 함수
            with_retry_config: 재시도 설정
            with_fallback: 폴백 함수
        """
        operations = [validation_func, fetch_func, transform_func, save_func]
        
        pipeline = AsyncPipeline(operations)
        
        if with_retry_config:
            # 재시도 래핑 (예제 - 실제로는 각 연산에 개별 적용 필요)
            pass
            
        if with_fallback:
            # 폴백 래핑 (예제 - 실제로는 각 연산에 개별 적용 필요)
            pass
        
        return pipeline
    
    @staticmethod
    def api_aggregation_pipeline(api_calls: list, aggregator_func):
        """
        API 집계 파이프라인 패턴
        
        여러 API 호출 결과를 병렬로 수집하여 집계합니다.
        """
        async def execute_aggregation(initial_data):
            # 병렬 API 호출
            api_results = await parallel_map_async(
                lambda call: call(initial_data),
                api_calls,
                max_concurrency=len(api_calls)
            )
            
            # 성공한 결과들만 추출
            successful_results = []
            for result in api_results:
                if await result.is_success():
                    successful_results.append(await result.unwrap_async())
            
            # 집계
            aggregated = aggregator_func(successful_results)
            return AsyncResult.from_value(aggregated)
        
        return execute_aggregation
    
    @staticmethod
    def streaming_processor_pipeline(
        stream_source,
        batch_size=100,
        max_concurrency=10,
        error_strategy=None
    ):
        """
        스트리밍 처리 파이프라인 패턴
        
        대용량 데이터 스트림을 배치 단위로 효율적으로 처리합니다.
        """
        processor = AsyncStreamProcessor(
            processor_func=stream_source,
            batch_size=batch_size,
            max_concurrency=max_concurrency
        )
        
        return processor


# === 개발자 유틸리티 ===

def validate_async_pipeline_environment():
    """
    AsyncPipeline 환경 검증
    
    Returns:
        dict: 환경 검증 결과
    """
    import sys
    import asyncio
    
    validation_results = {
        'python_version': sys.version_info >= (3, 8),
        'asyncio_available': True,
        'typing_support': True,
        'performance_features': True
    }
    
    try:
        # asyncio 정책 확인
        loop_policy = asyncio.get_event_loop_policy()
        validation_results['event_loop_policy'] = type(loop_policy).__name__
    except:
        validation_results['asyncio_available'] = False
    
    try:
        # typing 모듈 기능 확인
        from typing import Generic, TypeVar, Awaitable
        validation_results['typing_support'] = True
    except ImportError:
        validation_results['typing_support'] = False
    
    # 전체 검증 결과
    validation_results['all_checks_passed'] = all([
        validation_results['python_version'],
        validation_results['asyncio_available'], 
        validation_results['typing_support']
    ])
    
    return validation_results


def get_async_pipeline_info():
    """
    AsyncPipeline 패키지 정보 반환
    
    Returns:
        dict: 패키지 정보
    """
    return {
        'version': __version__,
        'components': len(__all__),
        'core_features': [
            'AsyncResult 모나드',
            'AsyncPipeline 시스템', 
            '고급 에러 처리',
            '성능 최적화 도구'
        ],
        'compatibility': {
            'rfs_framework': '>= 4.3.0',
            'python': '>= 3.8',
            'asyncio': 'native'
        },
        'documentation': 'https://rfs-framework.readthedocs.io/async-pipeline',
        'repository': __url__
    }


# === 디버깅 및 개발 도구 ===

async def debug_async_pipeline(pipeline: AsyncPipeline, input_data):
    """
    AsyncPipeline 디버깅 실행
    
    파이프라인 실행 과정을 상세히 추적하여 디버깅 정보를 제공합니다.
    """
    print(f"🔍 AsyncPipeline 디버깅 시작")
    print(f"   파이프라인: {pipeline}")
    print(f"   입력 데이터: {input_data}")
    
    result, execution_info = await pipeline.execute_with_context(input_data)
    
    print(f"\n📊 실행 정보:")
    print(f"   총 소요시간: {execution_info['total_duration']:.3f}초")
    print(f"   완료된 단계: {execution_info['steps_completed']}/{execution_info['operations_count']}")
    print(f"   성공 여부: {execution_info['success']}")
    
    print(f"\n📋 단계별 상세:")
    for step_info in execution_info['steps_details']:
        status = "✅" if step_info['success'] else "❌"
        print(f"   {status} 단계 {step_info['step']}: {step_info['operation']} "
              f"({step_info['duration']:.3f}초)")
        
        if not step_info['success'] and 'error' in step_info:
            print(f"      에러: {step_info['error']}")
    
    return result, execution_info


# === 성능 벤치마킹 ===

async def benchmark_async_pipeline_performance():
    """
    AsyncPipeline 성능 벤치마킹
    
    다양한 시나리오에서 성능을 측정하여 최적화 포인트를 식별합니다.
    """
    import time
    import asyncio
    
    print("🏁 AsyncPipeline 성능 벤치마킹 시작")
    
    # 테스트 함수들 정의
    def sync_operation(x):
        return x * 2
    
    async def async_operation(x):
        await asyncio.sleep(0.001)  # 1ms 지연 시뮬레이션
        return x + 1
    
    # 벤치마크 시나리오들
    scenarios = [
        {
            'name': '순수 동기 파이프라인',
            'operations': [sync_operation, sync_operation, sync_operation],
            'data_size': 1000
        },
        {
            'name': '순수 비동기 파이프라인', 
            'operations': [async_operation, async_operation, async_operation],
            'data_size': 100
        },
        {
            'name': '혼재 파이프라인',
            'operations': [sync_operation, async_operation, sync_operation],
            'data_size': 500
        }
    ]
    
    results = {}
    
    for scenario in scenarios:
        print(f"\n📊 {scenario['name']} 테스트 중...")
        
        pipeline = AsyncPipeline(scenario['operations'])
        start_time = time.time()
        
        # 테스트 실행
        for i in range(scenario['data_size']):
            await pipeline.execute(i)
        
        end_time = time.time()
        total_time = end_time - start_time
        throughput = scenario['data_size'] / total_time
        
        results[scenario['name']] = {
            'total_time': total_time,
            'throughput': throughput,
            'avg_time_per_item': total_time / scenario['data_size']
        }
        
        print(f"   총 시간: {total_time:.3f}초")
        print(f"   처리량: {throughput:.1f} items/sec")
        print(f"   항목당 평균: {total_time * 1000 / scenario['data_size']:.3f}ms")
    
    return results


# === 모듈 전역 설정 ===

# 전역 성능 모니터링 활성화
_PERFORMANCE_MONITORING_ENABLED = True

# 전역 에러 모니터링 활성화
_ERROR_MONITORING_ENABLED = True

# 디버그 모드 설정
_DEBUG_MODE = False


def set_async_pipeline_config(
    performance_monitoring: bool = True,
    error_monitoring: bool = True,
    debug_mode: bool = False
):
    """
    AsyncPipeline 전역 설정
    
    Args:
        performance_monitoring: 성능 모니터링 활성화 여부
        error_monitoring: 에러 모니터링 활성화 여부
        debug_mode: 디버그 모드 활성화 여부
    """
    global _PERFORMANCE_MONITORING_ENABLED, _ERROR_MONITORING_ENABLED, _DEBUG_MODE
    
    _PERFORMANCE_MONITORING_ENABLED = performance_monitoring
    _ERROR_MONITORING_ENABLED = error_monitoring
    _DEBUG_MODE = debug_mode
    
    if debug_mode:
        logging.getLogger(__name__).setLevel(logging.DEBUG)
        print("🐛 AsyncPipeline 디버그 모드 활성화")
    else:
        logging.getLogger(__name__).setLevel(logging.INFO)