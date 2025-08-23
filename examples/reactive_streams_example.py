"""
Advanced Reactive Streams Examples (RFS v4.0.3)

새로운 Reactive Streams 연산자들의 사용 예제:
- 병렬 처리 (parallel)
- 윈도우 처리 (window)
- 스로틀링 (throttle)
- 샘플링 (sample)
- 에러 복구 (on_error_continue)
"""

import asyncio
import time
from typing import List
from rfs.reactive import Flux, Mono


async def parallel_processing_example():
    """병렬 처리 예제"""
    print("🔄 병렬 처리 예제")
    
    # CPU 집약적인 작업 시뮬레이션
    def cpu_intensive_work(x: int) -> int:
        # 간단한 CPU 작업 시뮬레이션
        for _ in range(1000):
            x = (x * 31 + 17) % 1000007
        return x
    
    start_time = time.time()
    
    # 병렬 처리 (4개 스레드)
    result = await (
        Flux.from_iterable(range(50))
        .parallel(parallelism=4)
        .map(cpu_intensive_work)
        .collect_list()
    )
    
    parallel_time = time.time() - start_time
    
    # 순차 처리와 비교
    start_time = time.time()
    sequential_result = [cpu_intensive_work(x) for x in range(50)]
    sequential_time = time.time() - start_time
    
    print(f"   병렬 처리 시간: {parallel_time:.3f}초")
    print(f"   순차 처리 시간: {sequential_time:.3f}초")
    print(f"   성능 향상: {((sequential_time - parallel_time) / sequential_time * 100):.1f}%")
    print(f"   결과 개수: {len(result)}")
    print()


async def window_processing_example():
    """윈도우 처리 예제"""
    print("📊 윈도우 처리 예제")
    
    # 크기 기반 윈도우
    print("  크기 기반 윈도우 (5개씩):")
    size_window_result = await (
        Flux.from_iterable(range(23))
        .window(size=5)
        .flat_map(lambda window: window.reduce(0, lambda a, b: a + b))
        .collect_list()
    )
    print(f"    윈도우별 합계: {size_window_result}")
    
    # 시간 기반 윈도우 (짧은 시간으로 테스트)
    print("  시간 기반 윈도우 (0.1초 간격):")
    time_window_result = await (
        Flux.interval(0.05)  # 0.05초마다 값 생성
        .take(20)            # 20개만 가져오기
        .window(duration=0.2) # 0.2초 윈도우
        .flat_map(lambda window: window.count())
        .collect_list()
    )
    print(f"    윈도우별 카운트: {time_window_result}")
    print()


async def throttling_example():
    """스로틀링 예제"""
    print("⏱️ 스로틀링 예제")
    
    # API 요청 시뮬레이션
    async def api_request(request_id: int) -> dict:
        await asyncio.sleep(0.01)  # 짧은 지연
        return {"request_id": request_id, "result": f"data_{request_id}"}
    
    start_time = time.time()
    
    # 초당 10개로 제한하여 20개 요청 처리
    result = await (
        Flux.from_iterable(range(20))
        .throttle(elements=5, duration=0.1)  # 0.1초당 5개로 제한
        .flat_map(lambda req_id: Mono.from_callable(lambda: api_request(req_id)))
        .collect_list()
    )
    
    elapsed_time = time.time() - start_time
    
    print(f"   처리된 요청 수: {len(result)}")
    print(f"   총 소요 시간: {elapsed_time:.3f}초")
    print(f"   실제 처리율: {len(result) / elapsed_time:.1f} 요청/초")
    print()


async def sampling_example():
    """샘플링 예제"""
    print("🔢 샘플링 예제")
    
    # 빠르게 변하는 값에서 주기적으로 샘플링
    counter = 0
    
    def generate_value():
        nonlocal counter
        counter += 1
        return counter * counter  # 제곱값
    
    # 0.02초마다 값 생성, 0.1초마다 샘플링
    sample_result = await (
        Flux.interval(0.02)
        .map(lambda _: generate_value())
        .sample(0.1)  # 0.1초마다 최신 값만 샘플링
        .take(8)      # 8개 샘플만
        .collect_list()
    )
    
    print(f"   샘플링된 값들: {sample_result}")
    print()


async def error_handling_example():
    """에러 처리 예제"""
    print("🛠️ 에러 처리 예제")
    
    def risky_operation(x: int) -> int:
        if x % 7 == 0:  # 7의 배수에서 에러 발생
            raise ValueError(f"Error at {x}")
        return x * 2
    
    # 에러 발생 시 계속 진행
    error_continue_result = await (
        Flux.from_iterable(range(15))
        .on_error_continue()
        .map(risky_operation)
        .collect_list()
    )
    
    print(f"   에러 무시하고 계속: {error_continue_result}")
    
    # 에러 발생 시 기본값 반환
    error_default_result = await (
        Flux.from_iterable(range(15))
        .map(lambda x: risky_operation(x) if x % 7 != 0 else -1)
        .on_error_return(-999)
        .collect_list()
    )
    
    print(f"   에러 시 기본값(-1): {error_default_result}")
    print()


async def complex_pipeline_example():
    """복합 파이프라인 예제"""
    print("🔧 복합 파이프라인 예제")
    print("  로그 데이터 분석 시뮬레이션:")
    
    # 로그 엔트리 시뮬레이션
    log_entries = [
        {"timestamp": i, "level": "INFO" if i % 3 != 0 else "ERROR", "size": i * 10}
        for i in range(100)
    ]
    
    # 복잡한 데이터 처리 파이프라인
    analysis_result = await (
        Flux.from_iterable(log_entries)
        .filter(lambda entry: entry["level"] == "ERROR")  # 에러 로그만
        .window(size=5)                                   # 5개씩 윈도우
        .parallel(parallelism=2)                          # 2개 스레드로 병렬 처리
        .flat_map(lambda window: window.map(lambda e: e["size"]).reduce(0, lambda a, b: a + b))
        .throttle(elements=3, duration=0.05)              # 스로틀링
        .collect_list()
    )
    
    print(f"   에러 로그 크기 합계 (윈도우별): {analysis_result}")
    print()


async def main():
    """모든 예제 실행"""
    print("🚀 RFS Framework - Advanced Reactive Streams 예제")
    print("=" * 60)
    
    await parallel_processing_example()
    await window_processing_example()
    await throttling_example()
    await sampling_example()
    await error_handling_example()
    await complex_pipeline_example()
    
    print("✅ 모든 Reactive Streams 예제 완료!")


if __name__ == "__main__":
    asyncio.run(main())