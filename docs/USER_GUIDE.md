# RFS Framework v4.2 사용자 가이드

## 소개

RFS Framework v4.2는 엔터프라이즈급 Python 애플리케이션을 위한 종합적인 프레임워크입니다. 성능 최적화, 프로덕션 관리, 그리고 고급 통합 기능을 제공합니다.

### 주요 특징

- ⚡ **성능 최적화**: 실시간 프로파일링 및 자동 최적화
- 🔍 **프로덕션 모니터링**: 24/7 모니터링 및 알림
- 🔄 **재해 복구**: 자동 백업 및 복구 시스템
- 🌐 **API Gateway**: 엔터프라이즈급 API 관리
- 💾 **분산 캐시**: 고성능 멀티레벨 캐싱
- 🔌 **웹 통합**: REST, GraphQL, WebSocket 지원

## 빠른 시작

### 설치

```bash
# 전체 기능 설치
pip install rfs-framework[all]

# 특정 기능만 설치
pip install rfs-framework[performance,production,integration]
```

### 기본 설정

```python
# config.py
from rfs.config import RFSConfig

config = RFSConfig(
    environment="production",
    cloud_run_enabled=True,
    monitoring_enabled=True,
    cache_backend="redis",
    api_gateway_enabled=True
)
```

## 사용 예제

### 1. 성능 최적화

#### 애플리케이션 프로파일링

```python
import asyncio
from rfs.performance.profiling import get_system_profiler

async def profile_application():
    profiler = get_system_profiler()
    await profiler.start()
    
    # 프로파일링할 작업
    await profiler.start_profile("data_processing")
    
    # 실제 작업 수행
    data = await process_large_dataset()
    
    # 프로파일 결과 확인
    result = await profiler.stop_profile("data_processing")
    profile = result.value
    
    print(f"작업 시간: {profile.duration}초")
    print(f"메모리 사용: {profile.memory_used / 1024 / 1024:.2f} MB")
    print(f"CPU 사용률: {profile.cpu_usage}%")
    
    # 병목 현상 분석
    bottlenecks = profile.bottlenecks
    for bottleneck in bottlenecks:
        print(f"병목: {bottleneck.function_name} - {bottleneck.time_spent}초")
    
    await profiler.stop()

asyncio.run(profile_application())
```

#### Cloud Run 최적화

```python
from rfs.performance.optimization import get_cloud_run_optimizer

async def optimize_for_cloud_run():
    optimizer = get_cloud_run_optimizer()
    
    # 환경 분석 및 최적화
    recommendations = await optimizer.optimize()
    
    print("추천 설정:")
    print(f"- 동시 실행: {recommendations.value['concurrency']}")
    print(f"- 메모리: {recommendations.value['memory']} MB")
    print(f"- CPU: {recommendations.value['cpu']}")
    
    # 자동 스케일링 설정
    await optimizer.configure_autoscaling(
        min_instances=1,
        max_instances=100,
        target_cpu_utilization=70
    )

asyncio.run(optimize_for_cloud_run())
```

### 2. 프로덕션 관리

#### 실시간 모니터링

```python
from rfs.production.monitoring import get_production_monitor, get_alert_manager

async def setup_monitoring():
    monitor = get_production_monitor()
    alert_manager = get_alert_manager()
    
    await monitor.start()
    await alert_manager.start()
    
    # 알림 규칙 설정
    alert_manager.add_rule(
        rule_id="high_cpu",
        name="CPU 사용량 높음",
        condition="cpu_percent > 80",
        level="WARNING",
        channels=["email", "slack"]
    )
    
    alert_manager.add_rule(
        rule_id="low_memory",
        name="메모리 부족",
        condition="memory_available < 100",  # MB
        level="CRITICAL",
        channels=["email", "slack", "pagerduty"]
    )
    
    # 모니터링 실행
    while True:
        metrics = monitor.get_current_metrics()
        
        print(f"CPU: {metrics['system']['cpu_percent']}%")
        print(f"메모리: {metrics['system']['memory_percent']}%")
        print(f"디스크: {metrics['system']['disk_percent']}%")
        
        await asyncio.sleep(60)  # 1분마다 확인

asyncio.run(setup_monitoring())
```

#### 백업 및 복구

```python
from rfs.production.recovery import (
    get_backup_manager,
    BackupPolicy,
    BackupTarget,
    BackupType
)

async def setup_backup_system():
    backup_manager = get_backup_manager()
    await backup_manager.start()
    
    # 백업 정책 설정
    policy = BackupPolicy(
        id="daily_backup",
        name="일일 백업",
        backup_type=BackupType.INCREMENTAL,
        schedule="0 2 * * *",  # 매일 새벽 2시
        retention_days=30
    )
    
    backup_manager.add_policy(policy)
    
    # 백업 대상 설정
    target = BackupTarget(
        id="database",
        name="데이터베이스",
        type="database",
        source_path="postgresql://localhost/mydb"
    )
    
    backup_manager.add_target(target)
    
    # 수동 백업 실행
    backup_operation = await backup_manager.create_backup(
        policy_id="daily_backup",
        target_id="database",
        manual=True
    )
    
    print(f"백업 시작: {backup_operation.value.id}")

asyncio.run(setup_backup_system())
```

### 3. API Gateway 구성

```python
from rfs.integration import (
    get_api_gateway,
    Route,
    Backend,
    LoadBalanceStrategy
)

async def setup_api_gateway():
    gateway = get_api_gateway()
    await gateway.start()
    
    # 백엔드 서버 설정
    backends = [
        Backend("server1", "10.0.1.10", 8080, weight=2),
        Backend("server2", "10.0.1.11", 8080, weight=1),
        Backend("server3", "10.0.1.12", 8080, weight=1)
    ]
    
    # API 라우트 설정
    user_route = Route(
        id="user_api",
        path="/api/v1/users",
        methods=["GET", "POST", "PUT", "DELETE"],
        backends=backends,
        authentication="JWT",
        rate_limit={
            "requests_per_second": 100,
            "burst_size": 200
        },
        cache_config={
            "ttl": 60,
            "key_pattern": "user_{id}"
        }
    )
    
    gateway.add_route(user_route)
    
    # 로드 밸런싱 전략 설정
    gateway.load_balancer.strategy = LoadBalanceStrategy.LEAST_CONNECTIONS
    
    print("API Gateway가 시작되었습니다.")

asyncio.run(setup_api_gateway())
```

### 4. 분산 캐시 사용

```python
from rfs.integration import (
    get_distributed_cache_manager,
    CacheConfig,
    CacheBackend,
    EvictionPolicy
)

async def use_distributed_cache():
    # Redis 백엔드 캐시 설정
    config = CacheConfig(
        backend=CacheBackend.REDIS,
        eviction_policy=EvictionPolicy.LRU,
        max_size=100000,
        max_memory_mb=512,
        default_ttl=3600
    )
    
    cache = get_distributed_cache_manager(config)
    await cache.start()
    
    # 데이터 캐싱
    user_data = {
        "id": "123",
        "name": "John Doe",
        "email": "john@example.com"
    }
    
    await cache.set("user:123", user_data, ttl=1800)
    
    # 캐시 조회
    result = await cache.get("user:123")
    if result.value:
        print(f"캐시에서 조회: {result.value}")
    
    # 캐시 파티션 사용
    cache.create_partition(
        "session_cache",
        "세션 캐시",
        CacheConfig(
            backend=CacheBackend.MEMORY,
            max_size=1000,
            default_ttl=900  # 15분
        )
    )
    
    # 세션 데이터 저장
    await cache.set(
        "session:abc123",
        {"user_id": "123", "login_time": "2025-01-01T10:00:00"},
        partition_id="session_cache"
    )

asyncio.run(use_distributed_cache())
```

## 고급 기능

### 통합 워크플로우

```python
import asyncio
from rfs.performance import get_system_profiler, get_cloud_run_optimizer
from rfs.production import get_production_monitor, get_alert_manager
from rfs.integration import get_api_gateway, get_distributed_cache_manager

async def integrated_application():
    # 1. 프로파일링 시작
    profiler = get_system_profiler()
    await profiler.start()
    
    # 2. 모니터링 시작
    monitor = get_production_monitor()
    alert_manager = get_alert_manager()
    await monitor.start()
    await alert_manager.start()
    
    # 3. 캐시 초기화
    cache = get_distributed_cache_manager()
    await cache.start()
    
    # 4. API Gateway 시작
    gateway = get_api_gateway()
    await gateway.start()
    
    # 5. 애플리케이션 로직
    async def handle_request(request):
        # 캐시 확인
        cached = await cache.get(f"request:{request.id}")
        if cached.value:
            return cached.value
        
        # 프로파일링
        await profiler.start_profile(f"request_{request.id}")
        
        # 실제 처리
        result = await process_request(request)
        
        # 프로파일 종료
        profile = await profiler.stop_profile(f"request_{request.id}")
        
        # 성능이 나쁘면 알림
        if profile.value.duration > 1.0:  # 1초 이상
            await alert_manager.create_alert(
                rule_id="slow_request",
                title="느린 요청 감지",
                message=f"요청 {request.id}가 {profile.value.duration}초 걸림"
            )
        
        # 결과 캐싱
        await cache.set(f"request:{request.id}", result, ttl=300)
        
        return result
    
    # 애플리케이션 실행
    while True:
        # 요청 처리
        request = await get_next_request()
        result = await handle_request(request)
        await send_response(result)

asyncio.run(integrated_application())
```

## 모범 사례

### 1. 에러 처리

```python
from rfs.core import Success, Failure

async def safe_operation():
    result = await some_api_call()
    
    if isinstance(result, Success):
        # 성공 처리
        data = result.value
        return process_data(data)
    else:
        # 실패 처리
        error = result.error
        logger.error(f"작업 실패: {error}")
        
        # 재시도 로직
        for attempt in range(3):
            retry_result = await some_api_call()
            if isinstance(retry_result, Success):
                return retry_result.value
            await asyncio.sleep(2 ** attempt)  # 지수 백오프
        
        # 모든 재시도 실패
        return None
```

### 2. 리소스 정리

```python
async def managed_resources():
    monitor = get_production_monitor()
    cache = get_distributed_cache_manager()
    
    try:
        # 리소스 초기화
        await monitor.start()
        await cache.start()
        
        # 작업 수행
        await do_work()
        
    finally:
        # 항상 정리
        await monitor.stop()
        await cache.stop()
```

### 3. 성능 최적화 팁

1. **캐싱 적극 활용**: 자주 접근하는 데이터는 항상 캐시
2. **비동기 처리**: I/O 작업은 항상 비동기로 처리
3. **배치 처리**: 가능한 경우 요청을 배치로 처리
4. **연결 풀링**: 데이터베이스와 외부 서비스 연결은 풀링 사용
5. **프로파일링**: 정기적으로 프로파일링하여 병목 현상 파악

### 4. 프로덕션 체크리스트

- [ ] 모니터링 설정 완료
- [ ] 알림 규칙 구성
- [ ] 백업 정책 설정
- [ ] 재해 복구 계획 수립
- [ ] 컴플라이언스 검증
- [ ] API 속도 제한 설정
- [ ] 캐시 전략 수립
- [ ] 로드 밸런싱 구성
- [ ] 헬스 체크 설정
- [ ] 로깅 구성

## 문제 해결

### 일반적인 문제

#### 1. 높은 메모리 사용

```python
from rfs.performance.optimization import get_memory_optimizer

async def fix_memory_issues():
    optimizer = get_memory_optimizer()
    
    # 메모리 분석
    analysis = await optimizer.analyze()
    
    # 자동 최적화
    await optimizer.optimize(strategy="AGGRESSIVE")
    
    # 가비지 컬렉션 강제
    await optimizer.force_garbage_collection()
```

#### 2. 느린 API 응답

```python
# 1. 프로파일링으로 병목 확인
profile = await profiler.profile_endpoint("/api/slow")

# 2. 캐시 추가
await cache.set(cache_key, response_data, ttl=300)

# 3. 데이터베이스 쿼리 최적화
# 4. 비동기 처리 추가
```

#### 3. 캐시 미스율 높음

```python
# 캐시 통계 확인
stats = cache.get_statistics()
print(f"히트율: {stats.hit_ratio}%")

# 캐시 워밍
await cache.add_warmup_task(
    task_id="popular_data",
    loader=load_popular_data,
    keys=popular_keys,
    schedule="startup"
)
```

## 추가 리소스

- [API 레퍼런스](API_REFERENCE.md)
- [마이그레이션 가이드](./MIGRATION_GUIDE.md)
- [변경 로그](changelog.md)
- [GitHub 저장소](https://github.com/your-org/rfs-framework)

## 지원

문제가 발생하거나 도움이 필요한 경우:

1. [이슈 트래커](https://github.com/your-org/rfs-framework/issues)에 문제 제출
2. [토론 포럼](https://github.com/your-org/rfs-framework/discussions) 참여
3. [공식 문서](https://rfs-framework.readthedocs.io) 확인

## 라이선스

RFS Framework는 MIT 라이선스 하에 배포됩니다.