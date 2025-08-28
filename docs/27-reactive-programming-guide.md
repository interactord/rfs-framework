# 반응형 프로그래밍 가이드

RFS Framework의 Mono/Flux 리액티브 스트림과 AsyncResult 모나드를 활용한 현대적인 비동기 프로그래밍 가이드입니다.

## 개요

RFS Framework는 Spring Reactor에서 영감을 받은 강력한 반응형 스트림 라이브러리를 제공합니다. 함수형 프로그래밍의 모나드 패턴과 리액티브 스트림을 결합하여 우아하고 타입 안전한 비동기 프로그래밍을 가능하게 합니다.

### 핵심 구성요소

- **Mono**: 0-1개의 값을 비동기로 처리하는 리액티브 스트림
- **Flux**: 0-N개의 값을 비동기로 처리하는 리액티브 스트림  
- **AsyncResult**: 비동기 전용 Result 모나드
- **HOF Integration**: Higher-Order Functions와의 완벽한 통합

## 1. AsyncResult 모나드 - 비동기 함수형 프로그래밍

AsyncResult는 기존 Result 패턴을 비동기 환경으로 확장한 모나드입니다.

### 1.1 기본 사용법

```python
from rfs.async_pipeline import AsyncResult
from rfs.core.result import Success, Failure
import asyncio

# 비동기 함수를 AsyncResult로 래핑
async def fetch_user_data(user_id: str) -> dict:
    """사용자 데이터를 비동기로 가져옵니다."""
    if user_id == "invalid":
        raise ValueError("Invalid user ID")
    return {"id": user_id, "name": f"User {user_id}", "email": f"user{user_id}@example.com"}

# AsyncResult 생성
user_result = AsyncResult.from_async(lambda: fetch_user_data("123"))

# 결과 처리
async def main():
    if await user_result.is_success():
        user = await user_result.unwrap_async()
        print(f"사용자: {user['name']}")
    else:
        print("사용자 조회 실패")

asyncio.run(main())
```

### 1.2 모나딕 체이닝과 변환

```python
from rfs.async_pipeline import AsyncResult
from rfs.hof.core import pipe

# 사용자 검증 파이프라인
async def validate_user_age(user: dict) -> dict:
    """사용자 나이 검증"""
    if user.get("age", 0) < 18:
        raise ValueError("미성년자는 가입할 수 없습니다")
    return user

async def enrich_user_profile(user: dict) -> dict:
    """사용자 프로필 보강"""
    return {
        **user,
        "profile_completed": True,
        "created_at": "2025-01-01T00:00:00Z"
    }

async def save_user_to_db(user: dict) -> dict:
    """사용자 데이터베이스 저장"""
    print(f"사용자 저장: {user['name']}")
    return {**user, "id": "generated-id-123"}

# AsyncResult 모나딕 체이닝
async def register_user(user_data: dict):
    result = await (
        AsyncResult.from_value(user_data)
        .bind_async(lambda user: AsyncResult.from_async(lambda: validate_user_age(user)))
        .bind_async(lambda user: AsyncResult.from_async(lambda: enrich_user_profile(user)))
        .bind_async(lambda user: AsyncResult.from_async(lambda: save_user_to_db(user)))
        .to_result()
    )
    
    if result.is_success():
        saved_user = result.unwrap()
        print(f"사용자 등록 완료: {saved_user['id']}")
        return saved_user
    else:
        print(f"등록 실패: {result.unwrap_error()}")
        return None

# 사용
user_data = {"name": "홍길동", "age": 25, "email": "hong@example.com"}
await register_user(user_data)
```

### 1.3 에러 처리와 복구

```python
from rfs.async_pipeline import AsyncResult

# 회복 가능한 비동기 작업
async def fetch_from_primary_db(query: str) -> dict:
    """주 데이터베이스에서 조회 (실패 가능성 있음)"""
    if query == "fail":
        raise ConnectionError("주 데이터베이스 연결 실패")
    return {"data": f"Primary: {query}"}

async def fetch_from_backup_db(query: str) -> dict:
    """백업 데이터베이스에서 조회"""
    return {"data": f"Backup: {query}"}

async def fetch_from_cache(error, query: str) -> dict:
    """캐시에서 조회 (최후 수단)"""
    print(f"캐시에서 조회 중... (원인: {error})")
    return {"data": f"Cache: {query}", "stale": True}

# 계층화된 에러 복구
async def resilient_data_fetch(query: str):
    result = await (
        AsyncResult.from_async(lambda: fetch_from_primary_db(query))
        .recover_async(lambda _: fetch_from_backup_db(query))
        .recover_async(lambda error: fetch_from_cache(error, query))
        .to_result()
    )
    
    if result.is_success():
        data = result.unwrap()
        is_stale = data.get("stale", False)
        print(f"데이터 조회 성공: {data['data']} {'(오래된 데이터)' if is_stale else ''}")
        return data
    else:
        print(f"모든 조회 방법 실패: {result.unwrap_error()}")
        return None

# 테스트
await resilient_data_fetch("normal")  # Primary DB 성공
await resilient_data_fetch("fail")    # Primary 실패 → Backup 성공
```

## 2. Mono 리액티브 스트림 - 단일 값 비동기 처리

Mono는 0-1개의 값을 처리하는 리액티브 스트림입니다.

### 2.1 웹 API 통합

```python
from rfs.reactive import Mono
from rfs.web.fastapi_helpers import async_result_to_response
from rfs.logging.async_logging import AsyncResultLogger, log_async_chain
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()
logger = AsyncResultLogger()

# 외부 API 호출을 Mono로 래핑
def fetch_user_profile(user_id: str) -> Mono[dict]:
    """외부 API에서 사용자 프로필 조회"""
    async def fetch():
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.example.com/users/{user_id}")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    
    return Mono.from_callable(fetch)

def enrich_profile(profile: dict) -> Mono[dict]:
    """프로필 정보 보강"""
    async def enrich():
        # 추가 정보 조회 시뮬레이션
        return {
            **profile,
            "last_login": "2025-01-01T10:00:00Z",
            "profile_completeness": 85
        }
    
    return Mono.from_callable(enrich)

# FastAPI 엔드포인트에서 Mono 활용
@app.get("/users/{user_id}/profile")
@log_async_chain(logger, "get_user_profile")
async def get_user_profile(user_id: str):
    """사용자 프로필 조회 API"""
    
    # Mono 체이닝으로 비동기 작업 구성
    profile_result = await (
        fetch_user_profile(user_id)
        .flat_map(lambda profile: enrich_profile(profile))
        .map(lambda profile: {"profile": profile, "status": "active"})
        .on_error_return({"error": "프로필 조회 실패", "status": "error"})
        .to_future()
    )
    
    return profile_result

# 캐시와 함께 사용
@app.get("/users/{user_id}/cached-profile")
async def get_cached_profile(user_id: str):
    """캐시된 사용자 프로필 조회"""
    
    def get_cached_profile_data() -> Mono[dict]:
        # 캐시에서 조회 (빈 결과 시뮬레이션)
        return Mono.empty()
    
    def fetch_fresh_profile() -> Mono[dict]:
        return fetch_user_profile(user_id).flat_map(enrich_profile)
    
    result = await (
        get_cached_profile_data()
        .switch_if_empty(fetch_fresh_profile())
        .map(lambda profile: {"profile": profile, "cached": False})
        .on_error_return({"error": "프로필 조회 실패"})
        .to_future()
    )
    
    return result
```

### 2.2 타임아웃과 재시도

```python
from rfs.reactive import Mono
import asyncio
import random

# 불안정한 서비스 시뮬레이션
async def unreliable_service_call() -> str:
    """70% 확률로 실패하는 서비스 호출"""
    await asyncio.sleep(random.uniform(0.1, 2.0))  # 랜덤 지연
    
    if random.random() < 0.7:
        raise RuntimeError("서비스 일시적 장애")
    
    return "서비스 호출 성공!"

# 견고한 서비스 호출 패턴
async def robust_service_call():
    result = await (
        Mono.from_callable(unreliable_service_call)
        .timeout(1.5)  # 1.5초 타임아웃
        .retry(max_attempts=3)  # 최대 3회 재시도
        .on_error_return("서비스 이용 불가")
        .do_on_next(lambda value: print(f"성공: {value}"))
        .do_on_error(lambda error: print(f"최종 실패: {error}"))
        .to_future()
    )
    
    return result

# 여러 서비스 호출을 병렬로 처리
async def parallel_service_calls():
    service1 = Mono.from_callable(lambda: unreliable_service_call()).timeout(1.0).on_error_return("Service1 실패")
    service2 = Mono.from_callable(lambda: unreliable_service_call()).timeout(1.0).on_error_return("Service2 실패")
    service3 = Mono.from_callable(lambda: unreliable_service_call()).timeout(1.0).on_error_return("Service3 실패")
    
    # 모든 서비스 호출 결과 결합
    combined_result = await (
        service1.zip_with(service2)
        .zip_with(service3)
        .map(lambda results: {
            "service1": results[0][0],
            "service2": results[0][1], 
            "service3": results[1]
        })
        .to_future()
    )
    
    return combined_result

# 실행
print(await robust_service_call())
print(await parallel_service_calls())
```

## 3. Flux 리액티브 스트림 - 다중 값 스트림 처리

Flux는 0-N개의 값을 처리하는 리액티브 스트림입니다.

### 3.1 실시간 데이터 처리 파이프라인

```python
from rfs.reactive import Flux
from rfs.hof.collections import compact_map, group_by
import asyncio
import json
from datetime import datetime

# 실시간 로그 데이터 시뮬레이션
class LogEntry:
    def __init__(self, level: str, message: str, timestamp: str = None):
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self):
        return {"level": self.level, "message": self.message, "timestamp": self.timestamp}

async def log_stream_generator():
    """실시간 로그 스트림 생성기"""
    import random
    levels = ["INFO", "WARN", "ERROR", "DEBUG"]
    messages = [
        "사용자 로그인",
        "API 요청 처리",
        "데이터베이스 연결 실패", 
        "캐시 업데이트",
        "서비스 응답 지연"
    ]
    
    for i in range(20):
        level = random.choice(levels)
        message = f"{random.choice(messages)} #{i}"
        yield LogEntry(level, message)
        await asyncio.sleep(0.1)  # 100ms 간격

# 로그 분석 파이프라인
async def analyze_log_stream():
    """실시간 로그 분석"""
    
    # Flux로 로그 스트림 생성
    log_flux = Flux.from_async_iterable(log_stream_generator())
    
    # 에러 레벨 로그만 필터링하고 분석
    error_analysis = await (
        log_flux
        .filter(lambda log: log.level in ["ERROR", "WARN"])
        .map(lambda log: {
            "level": log.level,
            "message": log.message,
            "timestamp": log.timestamp,
            "severity": 2 if log.level == "ERROR" else 1
        })
        .buffer(5)  # 5개씩 배치 처리
        .map(lambda batch: {
            "batch_size": len(batch),
            "total_severity": sum(log["severity"] for log in batch),
            "error_count": len([log for log in batch if log["level"] == "ERROR"]),
            "logs": batch
        })
        .collect_list()
    )
    
    print("에러 로그 분석 결과:")
    for batch in error_analysis:
        print(f"배치 크기: {batch['batch_size']}, 총 심각도: {batch['total_severity']}")
    
    return error_analysis
```

### 3.2 데이터 변환 및 집계 파이프라인

```python
from rfs.reactive import Flux
import asyncio

# 센서 데이터 시뮬레이션
async def sensor_data_generator():
    """IoT 센서 데이터 생성기"""
    import random
    sensors = ["temperature", "humidity", "pressure"]
    
    for i in range(50):
        sensor_type = random.choice(sensors)
        value = {
            "temperature": random.uniform(15, 35),
            "humidity": random.uniform(30, 90), 
            "pressure": random.uniform(990, 1020)
        }[sensor_type]
        
        yield {
            "sensor_id": f"{sensor_type}_001",
            "type": sensor_type,
            "value": round(value, 2),
            "timestamp": f"2025-01-01T10:{i:02d}:00Z"
        }
        await asyncio.sleep(0.05)

# 센서 데이터 집계 및 알림
async def process_sensor_data():
    """센서 데이터 실시간 처리"""
    
    sensor_flux = Flux.from_async_iterable(sensor_data_generator())
    
    # 온도 센서 데이터만 처리하여 이상 온도 감지
    temperature_alerts = await (
        sensor_flux
        .filter(lambda data: data["type"] == "temperature")
        .window(size=5)  # 5개씩 윈도우 처리
        .flat_map(lambda window: window.collect_list())
        .map(lambda temp_batch: {
            "avg_temperature": sum(data["value"] for data in temp_batch) / len(temp_batch),
            "max_temperature": max(data["value"] for data in temp_batch),
            "min_temperature": min(data["value"] for data in temp_batch),
            "readings_count": len(temp_batch),
            "timeframe": f"{temp_batch[0]['timestamp']} - {temp_batch[-1]['timestamp']}"
        })
        .filter(lambda stats: stats["max_temperature"] > 30 or stats["avg_temperature"] > 25)
        .collect_list()
    )
    
    print("온도 경고 분석:")
    for alert in temperature_alerts:
        print(f"평균: {alert['avg_temperature']:.1f}°C, 최고: {alert['max_temperature']:.1f}°C")
    
    # 모든 센서 타입별 집계
    sensor_summary = await (
        Flux.from_async_iterable(sensor_data_generator())
        .reduce({}, lambda acc, data: {
            **acc,
            data["type"]: acc.get(data["type"], []) + [data["value"]]
        })
    )
    
    summary = await sensor_summary
    for sensor_type, values in summary.items():
        avg_value = sum(values) / len(values)
        print(f"{sensor_type}: 평균 {avg_value:.2f}, 샘플 수 {len(values)}")
    
    return temperature_alerts
```

### 3.3 병렬 처리와 백프레셔 제어

```python
from rfs.reactive import Flux
import asyncio
import time

# 무거운 작업 시뮬레이션
async def heavy_computation(item: int) -> dict:
    """CPU 집약적 작업 시뮬레이션"""
    await asyncio.sleep(0.2)  # 200ms 작업 시뮬레이션
    return {
        "input": item,
        "result": item ** 2,
        "processed_at": time.time()
    }

async def lightweight_processing(item: int) -> dict:
    """가벼운 작업 시뮬레이션"""  
    await asyncio.sleep(0.01)  # 10ms 작업
    return {"input": item, "doubled": item * 2}

# 백프레셔 제어를 통한 효율적인 병렬 처리
async def controlled_parallel_processing():
    """백프레셔와 병렬성 제어"""
    
    start_time = time.time()
    
    # 대량의 작업을 효율적으로 처리
    results = await (
        Flux.range(1, 100)
        .parallel(max_concurrency=5)  # 최대 5개 동시 실행
        .flat_map(
            lambda item: Flux.from_callable(lambda: heavy_computation(item)),
            max_concurrency=3  # flatMap도 동시성 제어
        )
        .buffer(10)  # 10개씩 배치로 모음
        .map(lambda batch: {
            "batch_size": len(batch),
            "avg_processing_time": sum(r["processed_at"] for r in batch) / len(batch),
            "results": [r["result"] for r in batch]
        })
        .collect_list()
    )
    
    end_time = time.time()
    total_processed = sum(batch["batch_size"] for batch in results)
    
    print(f"총 처리 시간: {end_time - start_time:.2f}초")
    print(f"처리된 항목 수: {total_processed}")
    print(f"처리 속도: {total_processed / (end_time - start_time):.1f} 항목/초")
    
    return results

# 적응형 백프레셔 (처리 속도에 따라 동적 조정)
async def adaptive_processing():
    """처리 속도에 따른 적응형 처리"""
    
    # 빠른 생성, 느린 처리 상황 시뮬레이션
    fast_producer = Flux.range(1, 1000)
    
    processed = await (
        fast_producer
        .on_backpressure_buffer(max_size=50)  # 버퍼 크기 제한
        .flat_map(
            lambda item: Flux.from_callable(lambda: lightweight_processing(item)),
            max_concurrency=10
        )
        .sample(duration=0.5)  # 500ms마다 샘플링하여 백프레셔 완화
        .take(20)  # 처음 20개만 수집
        .collect_list()
    )
    
    print(f"적응형 처리로 {len(processed)}개 항목 처리 완료")
    return processed

# 실행
await controlled_parallel_processing()
await adaptive_processing()
```

## 4. AsyncResult와 Reactive Streams 통합

AsyncResult와 Mono/Flux를 함께 사용하여 더욱 견고한 비동기 시스템을 구축할 수 있습니다.

### 4.1 통합 데이터 처리 파이프라인

```python
from rfs.async_pipeline import AsyncResult
from rfs.reactive import Mono, Flux
from rfs.core.result import Success, Failure

# AsyncResult를 Mono로 변환
def async_result_to_mono(async_result: AsyncResult) -> Mono:
    """AsyncResult를 Mono로 변환"""
    async def converter():
        result = await async_result.to_result()
        if result.is_success():
            return result.unwrap()
        else:
            raise Exception(result.unwrap_error())
    
    return Mono.from_callable(converter)

# Mono를 AsyncResult로 변환
def mono_to_async_result(mono: Mono) -> AsyncResult:
    """Mono를 AsyncResult로 변환"""
    async def converter():
        try:
            value = await mono.to_future()
            return Success(value)
        except Exception as e:
            return Failure(str(e))
    
    return AsyncResult(converter())

# 통합 예제: 사용자 데이터 처리 시스템
class UserDataProcessor:
    def __init__(self):
        self.processed_users = []
    
    async def validate_user(self, user_data: dict) -> AsyncResult[dict, str]:
        """사용자 데이터 검증 (AsyncResult 반환)"""
        async def validation():
            if not user_data.get("email"):
                return Failure("이메일이 필요합니다")
            if not user_data.get("name"):
                return Failure("이름이 필요합니다")
            if len(user_data.get("name", "")) < 2:
                return Failure("이름은 2자 이상이어야 합니다")
            return Success(user_data)
        
        return AsyncResult(validation())
    
    def enrich_user_data(self, user: dict) -> Mono[dict]:
        """사용자 데이터 보강 (Mono 반환)"""
        async def enrichment():
            return {
                **user,
                "id": f"user_{len(self.processed_users) + 1}",
                "created_at": "2025-01-01T00:00:00Z",
                "status": "active"
            }
        
        return Mono.from_callable(enrichment)
    
    async def save_user(self, user: dict) -> AsyncResult[dict, str]:
        """사용자 저장 (AsyncResult 반환)"""
        async def saving():
            # 저장 성공 시뮬레이션
            self.processed_users.append(user)
            return Success(user)
        
        return AsyncResult(saving())
    
    async def process_user(self, user_data: dict) -> dict:
        """단일 사용자 처리 (AsyncResult + Mono 통합)"""
        # 1. AsyncResult로 검증
        validation_result = await self.validate_user(user_data)
        if await validation_result.is_failure():
            return {"error": await validation_result.to_result().then(lambda r: r.unwrap_error())}
        
        validated_user = await validation_result.unwrap_async()
        
        # 2. Mono로 데이터 보강
        enriched_user = await self.enrich_user_data(validated_user).to_future()
        
        # 3. AsyncResult로 저장
        save_result = await self.save_user(enriched_user)
        if await save_result.is_success():
            return {"success": await save_result.unwrap_async()}
        else:
            return {"error": await save_result.to_result().then(lambda r: r.unwrap_error())}

# 대량 사용자 처리 (Flux + AsyncResult 통합)
async def process_user_batch():
    """사용자 배치 처리"""
    processor = UserDataProcessor()
    
    # 테스트 사용자 데이터
    user_data_list = [
        {"name": "김철수", "email": "kim@example.com"},
        {"name": "이영희", "email": "lee@example.com"}, 
        {"name": "", "email": "invalid@example.com"},  # 잘못된 데이터
        {"name": "박민수", "email": "park@example.com"},
        {"name": "최지현", "email": ""},  # 잘못된 데이터
    ]
    
    # Flux로 배치 처리
    results = await (
        Flux.from_iterable(user_data_list)
        .flat_map(lambda user_data: 
            Flux.from_callable(lambda: processor.process_user(user_data))
        )
        .buffer(2)  # 2개씩 배치 처리
        .map(lambda batch: {
            "batch_size": len(batch),
            "successful": len([r for r in batch if "success" in r]),
            "failed": len([r for r in batch if "error" in r]),
            "results": batch
        })
        .collect_list()
    )
    
    print("배치 처리 결과:")
    total_success = 0
    total_failed = 0
    
    for batch in results:
        print(f"배치: 성공 {batch['successful']}, 실패 {batch['failed']}")
        total_success += batch['successful']
        total_failed += batch['failed']
        
        # 에러 상세 출력
        for result in batch['results']:
            if 'error' in result:
                print(f"  에러: {result['error']}")
    
    print(f"\n전체 결과: 성공 {total_success}, 실패 {total_failed}")
    print(f"처리된 사용자 수: {len(processor.processed_users)}")
    
    return results

# 실행
await process_user_batch()
```

### 4.2 실시간 모니터링 시스템

```python
from rfs.async_pipeline import AsyncResult, sequence_async_results
from rfs.reactive import Flux, Mono
import asyncio
import random
import time

class SystemMonitor:
    """시스템 모니터링 클래스"""
    
    def __init__(self):
        self.alerts = []
        self.metrics_history = []
    
    async def check_cpu_usage(self) -> AsyncResult[float, str]:
        """CPU 사용률 체크"""
        async def check():
            # CPU 사용률 시뮬레이션
            usage = random.uniform(10, 95)
            if usage > 90:
                return Failure(f"CPU 사용률 위험: {usage:.1f}%")
            return Success(usage)
        
        return AsyncResult(check())
    
    async def check_memory_usage(self) -> AsyncResult[float, str]:
        """메모리 사용률 체크"""
        async def check():
            usage = random.uniform(20, 85)
            if usage > 80:
                return Failure(f"메모리 사용률 위험: {usage:.1f}%")
            return Success(usage)
        
        return AsyncResult(check())
    
    async def check_disk_usage(self) -> AsyncResult[float, str]:
        """디스크 사용률 체크"""
        async def check():
            usage = random.uniform(30, 95)
            if usage > 90:
                return Failure(f"디스크 사용률 위험: {usage:.1f}%")
            return Success(usage)
        
        return AsyncResult(check())
    
    def create_health_check_mono(self) -> Mono[dict]:
        """시스템 상태 체크를 Mono로 반환"""
        async def health_check():
            # 모든 체크를 병렬로 실행
            checks = [
                self.check_cpu_usage(),
                self.check_memory_usage(), 
                self.check_disk_usage()
            ]
            
            # AsyncResult들을 병렬로 실행하여 결과 수집
            results = await sequence_async_results(checks).to_result()
            
            if results.is_success():
                cpu, memory, disk = results.unwrap()
                return {
                    "status": "healthy",
                    "metrics": {
                        "cpu": cpu,
                        "memory": memory,
                        "disk": disk
                    },
                    "timestamp": time.time()
                }
            else:
                # 개별 체크 결과 수집
                individual_results = []
                for check in checks:
                    result = await check.to_result()
                    if result.is_success():
                        individual_results.append({"success": result.unwrap()})
                    else:
                        individual_results.append({"error": result.unwrap_error()})
                
                return {
                    "status": "unhealthy", 
                    "individual_checks": individual_results,
                    "timestamp": time.time()
                }
        
        return Mono.from_callable(health_check)

# 실시간 모니터링 스트림
async def run_monitoring_system():
    """실시간 시스템 모니터링"""
    monitor = SystemMonitor()
    
    # 5초마다 상태 체크를 하는 무한 스트림
    monitoring_stream = (
        Flux.interval(1.0)  # 1초마다
        .take(10)  # 10번만 실행 (데모용)
        .flat_map(lambda _: monitor.create_health_check_mono())
        .do_on_next(lambda health: 
            print(f"[{time.strftime('%H:%M:%S')}] 상태: {health['status']}")
        )
        .filter(lambda health: health["status"] == "unhealthy")
        .do_on_next(lambda health: 
            print(f"🚨 알림: 시스템 이상 감지 - {health.get('individual_checks', [])}")
        )
    )
    
    # 모니터링 실행
    print("시스템 모니터링 시작...")
    alerts = await monitoring_stream.collect_list()
    
    print(f"\n모니터링 완료. 총 {len(alerts)}개의 알림 발생")
    return alerts

# 실행
await run_monitoring_system()
```

## 5. 실제 프로덕션 예제

### 5.1 마이크로서비스 간 통신

```python
from rfs.async_pipeline import AsyncResult
from rfs.reactive import Mono, Flux
from rfs.web.fastapi_helpers import async_result_to_response
from fastapi import FastAPI
import httpx

app = FastAPI()

class MicroserviceClient:
    """마이크로서비스 클라이언트"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def call_service(self, endpoint: str, data: dict = None) -> Mono[dict]:
        """서비스 호출을 Mono로 래핑"""
        async def call():
            async with httpx.AsyncClient() as client:
                if data:
                    response = await client.post(f"{self.base_url}{endpoint}", json=data)
                else:
                    response = await client.get(f"{self.base_url}{endpoint}")
                
                if response.status_code == 200:
                    return response.json()
                else:
                    raise Exception(f"서비스 호출 실패: {response.status_code}")
        
        return Mono.from_callable(call).timeout(5.0)  # 5초 타임아웃

# 서비스 인스턴스들
user_service = MicroserviceClient("http://user-service")
order_service = MicroserviceClient("http://order-service")
payment_service = MicroserviceClient("http://payment-service")

@app.post("/api/orders")
async def create_order(order_data: dict):
    """주문 생성 API - 여러 서비스 조율"""
    
    # 1. 사용자 검증 
    user_validation = user_service.call_service(f"/users/{order_data['user_id']}/validate")
    
    # 2. 재고 확인
    inventory_check = user_service.call_service("/inventory/check", {
        "items": order_data["items"]
    })
    
    # 3. 가격 계산
    price_calculation = order_service.call_service("/calculate-price", order_data)
    
    # 병렬로 검증 수행
    validation_result = await (
        user_validation
        .zip_with(inventory_check)
        .zip_with(price_calculation)
        .map(lambda results: {
            "user_valid": results[0][0],
            "inventory_available": results[0][1], 
            "pricing": results[1]
        })
        .on_error_return({"error": "검증 중 오류 발생"})
        .to_future()
    )
    
    if "error" in validation_result:
        return validation_result
    
    # 4. 주문 생성 및 결제 처리
    create_and_pay = await (
        order_service.call_service("/orders", {
            **order_data,
            "total_price": validation_result["pricing"]["total"]
        })
        .flat_map(lambda order: 
            payment_service.call_service("/payments", {
                "order_id": order["id"],
                "amount": order["total_price"],
                "user_id": order["user_id"]
            })
        )
        .map(lambda payment: {
            "order_created": True,
            "payment_processed": True,
            "payment_id": payment["id"]
        })
        .on_error_return({"error": "주문 생성 또는 결제 실패"})
        .to_future()
    )
    
    return create_and_pay

# 배치 주문 처리
@app.post("/api/orders/batch")
async def process_batch_orders(orders: list[dict]):
    """대량 주문 배치 처리"""
    
    # Flux로 배치 처리
    batch_results = await (
        Flux.from_iterable(orders)
        .flat_map(
            lambda order_data: Flux.from_callable(lambda: create_order(order_data)),
            max_concurrency=5  # 최대 5개 동시 처리
        )
        .buffer(10)  # 10개씩 배치로 수집
        .map(lambda batch: {
            "processed": len(batch),
            "successful": len([r for r in batch if not r.get("error")]),
            "failed": len([r for r in batch if r.get("error")])
        })
        .collect_list()
    )
    
    return {
        "batches": batch_results,
        "total_orders": len(orders)
    }
```

### 5.2 이벤트 스트림 처리

```python
from rfs.reactive import Flux
from rfs.async_pipeline import AsyncResult
import json
import asyncio

class EventProcessor:
    """이벤트 스트림 처리기"""
    
    def __init__(self):
        self.processed_events = []
        self.error_events = []
    
    async def event_stream_generator(self):
        """이벤트 스트림 시뮬레이션"""
        events = [
            {"type": "user_login", "user_id": "user123", "timestamp": "2025-01-01T10:00:00Z"},
            {"type": "order_created", "order_id": "order456", "user_id": "user123", "amount": 100},
            {"type": "payment_processed", "payment_id": "pay789", "order_id": "order456"},
            {"type": "user_logout", "user_id": "user123", "timestamp": "2025-01-01T10:30:00Z"},
            {"type": "invalid_event", "data": "malformed"},  # 잘못된 이벤트
            {"type": "order_cancelled", "order_id": "order456", "reason": "user_request"}
        ]
        
        for event in events:
            yield event
            await asyncio.sleep(0.1)
    
    async def validate_event(self, event: dict) -> AsyncResult[dict, str]:
        """이벤트 검증"""
        async def validation():
            required_fields = ["type", "timestamp"] if event.get("type") != "invalid_event" else ["type"]
            
            for field in required_fields:
                if field not in event:
                    return Failure(f"필수 필드 누락: {field}")
            
            # 특정 타입별 추가 검증
            if event["type"] == "order_created" and "amount" not in event:
                return Failure("주문 생성 이벤트에 금액 정보 누락")
            
            if event.get("type") == "invalid_event":
                return Failure("잘못된 이벤트 타입")
            
            return Success(event)
        
        return AsyncResult(validation())
    
    async def enrich_event(self, event: dict) -> AsyncResult[dict, str]:
        """이벤트 정보 보강"""
        async def enrichment():
            enriched = {
                **event,
                "processed_at": "2025-01-01T12:00:00Z",
                "processor_id": "proc_001"
            }
            
            # 이벤트 타입별 추가 정보
            if event["type"] == "user_login":
                enriched["session_id"] = f"session_{event['user_id']}"
            elif event["type"] == "order_created":
                enriched["order_status"] = "pending"
            
            return Success(enriched)
        
        return AsyncResult(enrichment())
    
    async def store_event(self, event: dict) -> AsyncResult[dict, str]:
        """이벤트 저장"""
        async def storage():
            # 저장 시뮬레이션
            self.processed_events.append(event)
            return Success({"stored": True, "event_id": len(self.processed_events)})
        
        return AsyncResult(storage())

# 이벤트 처리 파이프라인
async def run_event_processing():
    """이벤트 스트림 처리 실행"""
    processor = EventProcessor()
    
    print("이벤트 처리 시작...")
    
    # 이벤트 스트림을 Flux로 처리
    processing_results = await (
        Flux.from_async_iterable(processor.event_stream_generator())
        .do_on_next(lambda event: print(f"이벤트 수신: {event['type']}"))
        
        # 검증 단계
        .flat_map(lambda event: 
            Flux.from_callable(lambda: processor.validate_event(event).to_result())
        )
        .on_error_continue(lambda error, event: 
            print(f"검증 실패: {event} - {error}")
        )
        
        # 성공한 이벤트만 보강
        .filter(lambda result: result.is_success())
        .map(lambda result: result.unwrap())
        .flat_map(lambda event:
            Flux.from_callable(lambda: processor.enrich_event(event).to_result())
        )
        .filter(lambda result: result.is_success())
        .map(lambda result: result.unwrap())
        
        # 저장
        .flat_map(lambda event:
            Flux.from_callable(lambda: processor.store_event(event).to_result())
        )
        .collect_list()
    )
    
    # 결과 분석
    successful_stores = [r for r in processing_results if r.is_success()]
    failed_stores = [r for r in processing_results if r.is_failure()]
    
    print(f"\n처리 완료:")
    print(f"성공적으로 저장된 이벤트: {len(successful_stores)}")
    print(f"저장 실패한 이벤트: {len(failed_stores)}")
    print(f"총 처리된 이벤트: {len(processor.processed_events)}")
    
    # 이벤트 타입별 통계
    event_types = {}
    for event in processor.processed_events:
        event_type = event["type"]
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    print("\n이벤트 타입별 통계:")
    for event_type, count in event_types.items():
        print(f"  {event_type}: {count}개")
    
    return processing_results

# 실행
await run_event_processing()
```

## 6. 성능 최적화 및 베스트 프랙티스

### 6.1 메모리 효율적인 스트림 처리

```python
from rfs.reactive import Flux
import asyncio
import sys

# 메모리 사용량 모니터링
def get_memory_usage():
    """현재 메모리 사용량 반환 (MB)"""
    import psutil
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

# 대용량 데이터 스트림 처리
async def process_large_dataset():
    """메모리 효율적인 대용량 데이터 처리"""
    
    print(f"시작 메모리 사용량: {get_memory_usage():.1f} MB")
    
    # 백만 개의 숫자를 생성하되, 메모리에 모두 로드하지 않음
    def large_number_generator():
        for i in range(1000000):
            yield i
    
    # 스트림으로 처리 (메모리 효율적)
    result = await (
        Flux.from_iterable(large_number_generator())
        .filter(lambda x: x % 1000 == 0)  # 1000의 배수만
        .map(lambda x: x ** 2)            # 제곱
        .buffer(100)                      # 100개씩 배치 처리
        .map(lambda batch: {
            "batch_sum": sum(batch),
            "batch_size": len(batch),
            "memory_usage": get_memory_usage()
        })
        .take(5)  # 처음 5개 배치만 처리 (데모용)
        .collect_list()
    )
    
    print(f"처리 완료 메모리 사용량: {get_memory_usage():.1f} MB")
    
    for i, batch_info in enumerate(result):
        print(f"배치 {i+1}: 합계={batch_info['batch_sum']}, "
              f"메모리={batch_info['memory_usage']:.1f}MB")
    
    return result

# 백프레셔를 활용한 안정적인 처리
async def stable_stream_processing():
    """백프레셔 제어로 안정적인 스트림 처리"""
    
    # 빠른 데이터 생성기
    async def fast_producer():
        for i in range(10000):
            yield f"data_{i}"
            if i % 1000 == 0:
                print(f"생성됨: {i}개")

    # 느린 처리기
    async def slow_processor(item: str) -> str:
        await asyncio.sleep(0.001)  # 1ms 지연
        return f"processed_{item}"
    
    start_time = asyncio.get_event_loop().time()
    
    # 백프레셔 제어
    processed_items = await (
        Flux.from_async_iterable(fast_producer())
        .on_backpressure_buffer(max_size=100)  # 버퍼 크기 제한
        .flat_map(
            lambda item: Flux.from_callable(lambda: slow_processor(item)),
            max_concurrency=10  # 동시 처리 제한
        )
        .take(1000)  # 1000개만 처리
        .collect_list()
    )
    
    end_time = asyncio.get_event_loop().time()
    processing_time = end_time - start_time
    
    print(f"백프레셔 제어 처리: {len(processed_items)}개 항목을 "
          f"{processing_time:.2f}초에 처리")
    print(f"처리 속도: {len(processed_items) / processing_time:.1f} 항목/초")
    
    return processed_items

# 실행
await process_large_dataset()
await stable_stream_processing()
```

### 6.2 에러 복구 전략

```python
from rfs.reactive import Mono, Flux
from rfs.async_pipeline import AsyncResult
import random
import asyncio

# 회복력 있는 서비스 호출
class ResilientService:
    """회복력 있는 서비스 클래스"""
    
    def __init__(self, failure_rate: float = 0.3):
        self.failure_rate = failure_rate
        self.call_count = 0
        self.success_count = 0
    
    async def unreliable_call(self, data: str) -> str:
        """불안정한 서비스 호출 시뮬레이션"""
        self.call_count += 1
        
        if random.random() < self.failure_rate:
            raise RuntimeError(f"서비스 호출 실패: {data}")
        
        self.success_count += 1
        return f"성공: {data}"
    
    def create_resilient_call_mono(self, data: str) -> Mono[str]:
        """회복력 있는 호출을 Mono로 래핑"""
        return (
            Mono.from_callable(lambda: self.unreliable_call(data))
            .retry(max_attempts=3, delay=0.1)  # 3회 재시도, 100ms 지연
            .timeout(2.0)  # 2초 타임아웃
            .on_error_return(f"최종실패: {data}")
        )

# 서킷 브레이커 패턴
class CircuitBreaker:
    """서킷 브레이커 구현"""
    
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 10.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def should_allow_request(self) -> bool:
        """요청 허용 여부 확인"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if asyncio.get_event_loop().time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """성공 기록"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """실패 기록"""
        self.failure_count += 1
        self.last_failure_time = asyncio.get_event_loop().time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

# 회복력 있는 처리 파이프라인
async def resilient_processing_pipeline():
    """회복력 있는 처리 파이프라인"""
    service = ResilientService(failure_rate=0.4)  # 40% 실패율
    circuit_breaker = CircuitBreaker()
    
    # 테스트 데이터
    test_data = [f"request_{i}" for i in range(20)]
    
    print("회복력 있는 처리 시작...")
    
    # Flux를 사용한 배치 처리
    results = await (
        Flux.from_iterable(test_data)
        .flat_map(lambda data: 
            # 서킷 브레이커 체크
            Mono.just(data)
            .filter(lambda _: circuit_breaker.should_allow_request())
            .switch_if_empty(Mono.just(f"차단됨: {data}"))
            .flat_map(lambda d: 
                service.create_resilient_call_mono(d)
                .do_on_next(lambda _: circuit_breaker.record_success())
                .on_error_return(lambda e: (
                    circuit_breaker.record_failure(),
                    f"서킷브레이커_실패: {d}"
                )[1])
            ),
            max_concurrency=5
        )
        .collect_list()
    )
    
    # 결과 분석
    successful = [r for r in results if r.startswith("성공:")]
    failed = [r for r in results if "실패" in r or "차단됨" in r]
    
    print(f"\n처리 결과:")
    print(f"총 요청: {len(test_data)}개")
    print(f"성공: {len(successful)}개")
    print(f"실패/차단: {len(failed)}개")
    print(f"서비스 호출 통계: {service.call_count}회 호출, {service.success_count}회 성공")
    print(f"서킷 브레이커 상태: {circuit_breaker.state}")
    
    return results

# 실행
await resilient_processing_pipeline()
```

## 7. 마무리 및 권장사항

### 7.1 언제 무엇을 사용할까?

- **AsyncResult**: 단순한 비동기 작업에서 Result 패턴이 필요한 경우
- **Mono**: 0-1개의 값을 처리하는 비동기 작업 (HTTP 요청, 데이터베이스 쿼리 등)
- **Flux**: 스트림 데이터 처리, 실시간 처리, 대용량 데이터 처리

### 7.2 성능 최적화 팁

1. **백프레셔 제어**: `on_backpressure_buffer()`, `sample()` 활용
2. **병렬 처리**: `parallel()`, `flat_map(max_concurrency=N)` 사용
3. **메모리 관리**: `buffer()`, `window()` 활용하여 배치 처리
4. **에러 처리**: `retry()`, `timeout()`, 서킷 브레이커 패턴 적용

### 7.3 베스트 프랙티스

1. **타입 안전성**: 항상 명확한 타입 힌트 사용
2. **에러 처리**: Result 패턴과 reactive error operators 조합
3. **테스트**: 비동기 테스트 유틸리티 적극 활용
4. **로깅**: AsyncResult 로깅으로 디버깅 용이성 확보
5. **모니터링**: 실시간 스트림으로 시스템 상태 모니터링

이 가이드를 통해 RFS Framework의 반응형 프로그래밍 기능을 효과적으로 활용하여 견고하고 확장 가능한 비동기 애플리케이션을 구축하시길 바랍니다.

## 관련 문서

- [AsyncResult API 문서](./api/async-pipeline/async-result.md)
- [Mono API 문서](./api/reactive/mono.md)
- [Flux API 문서](./api/reactive/flux.md)
- [AsyncResult Web Integration](./26-asyncresult-web-integration.md)
- [HOF 사용 가이드](./16-hof-usage-guide.md)