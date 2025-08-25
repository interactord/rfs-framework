# 배포 전략 (Deployment Strategies)

## 📌 개요

RFS Framework는 프로덕션 환경을 위한 다양한 배포 전략을 제공합니다. Blue-Green, Canary, Rolling 등의 전략을 통해 무중단 배포와 안전한 롤백이 가능합니다.

## 🎯 핵심 개념

### 배포 전략 종류
- **Blue-Green**: 두 개의 동일한 환경을 사용한 즉시 전환
- **Canary**: 점진적으로 트래픽을 증가시키는 배포
- **Rolling**: 인스턴스를 순차적으로 업데이트
- **A/B Testing**: 두 버전을 동시에 운영하며 테스트

### 배포 단계
1. **준비**: 체크포인트 생성, 헬스체크
2. **배포**: 선택된 전략에 따른 배포 실행
3. **검증**: 메트릭 수집 및 검증
4. **완료/롤백**: 성공 시 완료, 실패 시 자동 롤백

## 📚 API 레퍼런스

### DeploymentStrategy 클래스

```python
from rfs.production.strategies import (
    DeploymentStrategy,
    DeploymentConfig,
    DeploymentType,
    DeploymentMetrics
)
```

### 주요 설정 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `deployment_type` | 배포 전략 타입 | BLUE_GREEN |
| `health_check_interval` | 헬스체크 간격 | 30초 |
| `max_deployment_time` | 최대 배포 시간 | 600초 |
| `auto_rollback` | 자동 롤백 활성화 | True |
| `rollback_on_error_rate` | 롤백 트리거 에러율 | 5% |

## 💡 사용 예제

### Blue-Green 배포

```python
from rfs.production.strategies import (
    DeploymentStrategyFactory,
    DeploymentConfig,
    DeploymentType
)
from rfs.production.deployment import ProductionDeployer

# Blue-Green 배포 설정
config = DeploymentConfig(
    deployment_type=DeploymentType.BLUE_GREEN,
    switch_delay=60,  # 트래픽 전환 전 60초 대기
    health_check_interval=30,
    auto_rollback=True,
    rollback_on_error_rate=0.05  # 5% 에러율 시 롤백
)

# 배포 전략 생성
strategy = DeploymentStrategyFactory.create(
    DeploymentType.BLUE_GREEN,
    config
)

# 배포 실행
async def deploy_blue_green():
    result = await strategy.deploy(
        service_name="api-service",
        new_version="v2.0.0"
    )
    
    if result.is_success():
        metrics = result.value
        print(f"배포 성공!")
        print(f"소요 시간: {metrics.deployment_duration}")
        print(f"성공률: {metrics.success_rate:.2%}")
    else:
        print(f"배포 실패: {result.error}")
```

### Canary 배포

```python
from rfs.production.strategies import CanaryStrategy

# Canary 배포 설정
config = DeploymentConfig(
    deployment_type=DeploymentType.CANARY,
    canary_percentage=10,      # 초기 10% 트래픽
    canary_increment=10,        # 10%씩 증가
    canary_interval=60,         # 60초마다 증가
    auto_rollback=True,
    rollback_on_error_rate=0.02  # 2% 에러율 시 롤백
)

strategy = CanaryStrategy(config)

async def deploy_canary():
    """점진적 Canary 배포"""
    result = await strategy.deploy(
        service_name="api-service",
        new_version="v2.0.0"
    )
    
    # 배포 과정 모니터링
    # 10% -> 20% -> 30% -> ... -> 100%
    # 각 단계에서 메트릭 확인 후 자동 진행
```

### Rolling 배포

```python
from rfs.production.strategies import RollingStrategy

# Rolling 배포 설정
config = DeploymentConfig(
    deployment_type=DeploymentType.ROLLING,
    batch_size=2,              # 한 번에 2개 인스턴스 업데이트
    batch_interval=30,          # 배치 간 30초 대기
    health_check_timeout=10,
    auto_rollback=True
)

strategy = RollingStrategy(config)

async def deploy_rolling():
    """순차적 Rolling 배포"""
    result = await strategy.deploy(
        service_name="api-service",
        new_version="v2.0.0",
        instance_count=10  # 총 10개 인스턴스
    )
    
    if result.is_success():
        metrics = result.value
        print(f"모든 인스턴스 업데이트 완료")
        print(f"건강한 인스턴스: {metrics.healthy_instances}/{metrics.instance_count}")
```

### ProductionDeployer 통합 사용

```python
from rfs.production.deployment import (
    ProductionDeployer,
    DeploymentConfig,
    DeploymentStrategy
)

# 통합 배포 관리자
deployer_config = DeploymentConfig(
    strategy=DeploymentStrategy.BLUE_GREEN,
    target_environment="production",
    health_check_url="/health",
    rollback_on_failure=True,
    max_rollback_attempts=3,
    deployment_timeout=1800  # 30분
)

deployer = ProductionDeployer(deployer_config)

# 배포 훅 설정
async def pre_deployment_hook(result):
    """배포 전 실행"""
    print("배포 전 데이터베이스 마이그레이션...")
    # 마이그레이션 로직

async def post_deployment_hook(result):
    """배포 후 실행"""
    print("캐시 초기화...")
    # 캐시 클리어 로직

deployer.config.pre_deployment_hooks.append(pre_deployment_hook)
deployer.config.post_deployment_hooks.append(post_deployment_hook)

# 배포 실행
async def deploy_to_production():
    result = await deployer.deploy(
        version="v2.0.0",
        environment="production",
        strategy=DeploymentStrategy.CANARY
    )
    
    if result.is_success():
        deployment = result.value
        print(f"배포 ID: {deployment.deployment_id}")
        print(f"상태: {deployment.status}")
        print(f"버전: {deployment.version}")
        
        # 배포 히스토리 조회
        history = deployer.get_deployment_history()
        for dep in history[:5]:
            print(f"- {dep.deployment_id}: {dep.status}")
```

### 커스텀 배포 전략

```python
from rfs.production.strategies import DeploymentStrategy

class CustomStrategy(DeploymentStrategy):
    """커스텀 배포 전략"""
    
    async def deploy(
        self,
        service_name: str,
        new_version: str,
        **kwargs
    ) -> Result[DeploymentMetrics, str]:
        self.metrics = DeploymentMetrics(start_time=datetime.now())
        
        try:
            # 1. 커스텀 배포 로직
            print(f"커스텀 배포 시작: {service_name} -> {new_version}")
            
            # 2. 헬스체크
            health_result = await self.health_check(service_name, new_version)
            if health_result != HealthStatus.HEALTHY:
                return Failure("헬스체크 실패")
            
            # 3. 메트릭 수집
            metrics_result = await self.collect_metrics(service_name, new_version)
            if self.should_rollback(metrics_result.value):
                await self.rollback(service_name)
                return Failure("메트릭 기준 미달")
            
            # 4. 완료
            self.metrics.end_time = datetime.now()
            self.metrics.success_rate = 0.99
            
            return Success(self.metrics)
            
        except Exception as e:
            return Failure(f"배포 실패: {str(e)}")
```

### 배포 모니터링

```python
from rfs.production.deployment import get_production_deployer
import asyncio

async def monitor_deployment(deployment_id: str):
    """실시간 배포 모니터링"""
    deployer = get_production_deployer()
    
    while True:
        result = deployer.get_deployment_status(deployment_id)
        
        if not result:
            print("배포를 찾을 수 없습니다")
            break
        
        print(f"상태: {result.status}")
        print(f"진행률: {calculate_progress(result)}%")
        
        if result.status in [DeploymentStatus.COMPLETED, 
                            DeploymentStatus.FAILED,
                            DeploymentStatus.ROLLED_BACK]:
            print(f"배포 종료: {result.status}")
            if result.errors:
                print(f"에러: {result.errors}")
            break
        
        await asyncio.sleep(5)  # 5초마다 체크

def calculate_progress(deployment) -> int:
    """배포 진행률 계산"""
    if deployment.status == DeploymentStatus.PENDING:
        return 0
    elif deployment.status == DeploymentStatus.IN_PROGRESS:
        # 메트릭 기반 진행률 계산
        return 50
    elif deployment.status == DeploymentStatus.VALIDATING:
        return 80
    else:
        return 100
```

### 배포 검증

```python
from rfs.production.strategies import DeploymentConfig
import aiohttp

class DeploymentValidator:
    """배포 검증 도구"""
    
    async def validate_deployment(
        self,
        service_url: str,
        expected_version: str
    ) -> bool:
        """배포 검증"""
        checks = [
            self.check_version(service_url, expected_version),
            self.check_health(service_url),
            self.check_critical_endpoints(service_url),
            self.run_smoke_tests(service_url)
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"검증 실패 {i+1}: {result}")
                return False
        
        return all(results)
    
    async def check_version(self, url: str, version: str) -> bool:
        """버전 확인"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/version") as resp:
                data = await resp.json()
                return data.get("version") == version
    
    async def check_health(self, url: str) -> bool:
        """헬스체크"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/health") as resp:
                return resp.status == 200
    
    async def check_critical_endpoints(self, url: str) -> bool:
        """핵심 엔드포인트 확인"""
        endpoints = ["/api/users", "/api/products", "/api/orders"]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                async with session.get(f"{url}{endpoint}") as resp:
                    if resp.status >= 500:
                        return False
        return True
    
    async def run_smoke_tests(self, url: str) -> bool:
        """스모크 테스트"""
        # 기본 시나리오 테스트
        return True
```

## 🎨 베스트 프랙티스

### 1. 체크포인트 생성

```python
# 배포 전 항상 체크포인트 생성
from rfs.production.rollback import RollbackManager

rollback_manager = RollbackManager()

checkpoint = await rollback_manager.create_checkpoint(
    service_name="api-service",
    version="v1.0.0",
    configuration=current_config,
    environment_variables=os.environ.copy()
)
```

### 2. 단계별 검증

```python
# 각 배포 단계마다 검증
config = DeploymentConfig(
    # 검증 설정
    validation_duration=300,  # 5분간 검증
    health_check_interval=30,
    
    # 자동 롤백 조건
    auto_rollback=True,
    rollback_on_error_rate=0.05,
    rollback_on_latency=2.0  # 2초 이상 지연
)
```

### 3. 메트릭 기반 결정

```python
# 메트릭 기반 자동 롤백
if metrics.error_rate > 0.05:
    await rollback()
elif metrics.p99_latency > 2000:  # 2초
    await rollback()
elif metrics.cpu_usage > 90:
    await rollback()
```

## ⚠️ 주의사항

### 1. 데이터베이스 마이그레이션
- 배포 전 항상 백업
- 역방향 마이그레이션 준비
- Blue-Green에서는 양쪽 버전 호환성 확보

### 2. 상태 관리
- Stateless 서비스 우선
- 세션 데이터는 외부 저장소 사용
- 캐시 무효화 전략 수립

### 3. 모니터링
- 실시간 메트릭 수집
- 알람 설정
- 로그 집계 및 분석

## 🔗 관련 문서
- [롤백 관리](./06-rollback.md)
- [모니터링](./08-monitoring.md)
- [로드 밸런싱](./13-load-balancing.md)