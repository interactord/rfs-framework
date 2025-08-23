# RFS Framework 🚀

> **Enterprise-Grade Python Framework for Modern Applications**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Cloud Run Ready](https://img.shields.io/badge/Cloud%20Run-Ready-green.svg)](https://cloud.google.com/run)
[![Type Safety](https://img.shields.io/badge/Type%20Safety-100%25-green.svg)](https://mypy.readthedocs.io/)

RFS Framework는 현대적인 엔터프라이즈 Python 애플리케이션을 위한 종합적인 프레임워크입니다. 함수형 프로그래밍 패턴, 반응형 아키텍처, 그리고 Google Cloud Platform과의 완벽한 통합을 제공합니다.

## ✨ Key Features

### 🔧 Core Framework
- **🎯 Result Pattern**: 함수형 에러 핸들링과 타입 안전성
- **⚙️ Configuration Management**: 환경별 설정과 검증 시스템  
- **🔗 Dependency Injection**: 레지스트리 기반 서비스 관리
- **🔒 Type Safety**: 완전한 타입 힌트 지원 (Python 3.10+)

### ⚡ Reactive Programming
- **📡 Mono/Flux**: 비동기 반응형 스트림 처리
- **🔄 Operators**: `map`, `filter`, `flat_map` 등 30+ 연산자
- **⏰ Schedulers**: 멀티스레드 및 비동기 실행 컨텍스트
- **🎭 Backpressure**: 자동 흐름 제어

### 🏗️ Advanced Patterns
- **🎭 State Machine**: 함수형 상태 관리
- **📡 Event Sourcing**: CQRS와 이벤트 스토어
- **🎪 Saga Pattern**: 분산 트랜잭션 오케스트레이션
- **☁️ Cloud Native**: Google Cloud Run 최적화

### 🚀 New in v4.0.3
- **🔄 Advanced Reactive Operators**: parallel(), window(), throttle(), sample() 등 10+ 새로운 연산자
- **☁️ Cloud Native Helpers**: 서비스 디스커버리, 작업 큐, 모니터링, 자동 스케일링
- **🚢 Production Deployment**: Blue-Green, Canary, Rolling 배포 전략 지원
- **🔒 Security Hardening**: 정책 기반 보안 강화 및 컴플라이언스 검증

### 🛠️ Developer Experience
- **🖥️ Rich CLI**: 프로젝트 생성, 개발, 배포 명령어
- **🤖 Automation**: CI/CD 파이프라인 자동화
- **🧪 Testing**: 통합 테스트 프레임워크
- **📖 Docs**: 자동 문서 생성

### 🔒 Production Ready
- **✅ Validation**: 포괄적인 시스템 검증
- **⚡ Optimization**: 메모리, CPU, I/O 최적화
- **🛡️ Security**: 취약점 스캐닝 및 보안 강화
- **🚀 Deployment**: 프로덕션 준비성 검증

## 🚀 Quick Start

### Installation

```bash
pip install rfs-framework
```

### Basic Usage

```python
from rfs import Result, Success, Failure
from rfs import SystemValidator, PerformanceOptimizer

# Result 패턴으로 안전한 에러 핸들링
def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Failure("0으로 나눌 수 없습니다")
    return Success(a / b)

# 결과 처리
result = divide(10, 2)
if result.is_success:
    print(f"결과: {result.unwrap()}")  # 결과: 5.0
else:
    print(f"오류: {result.unwrap_err()}")

# 시스템 검증 사용
validator = SystemValidator()
validation_result = validator.validate_system()
print(f"시스템 상태: {'정상' if validation_result.is_valid else '문제 발견'}")
```

### Advanced Reactive Streams (New!)

```python
from rfs.reactive import Flux, Mono
import asyncio

# 병렬 처리 (New in v4.0.3)
async def process_data():
    result = await (
        Flux.from_iterable(range(100))
        .parallel(parallelism=4)  # 4개 스레드로 병렬 처리
        .map(lambda x: x * x)
        .filter(lambda x: x % 2 == 0)
        .collect_list()
    )
    return result

# 윈도우 처리 (New in v4.0.3)
async def window_processing():
    result = await (
        Flux.interval(0.1)  # 0.1초마다 숫자 생성
        .take(100)
        .window(size=10)  # 10개씩 묶어서 처리
        .flat_map(lambda window: window.reduce(0, lambda a, b: a + b))
        .collect_list()
    )
    return result

# 스로틀링 (New in v4.0.3)
async def rate_limited_api_calls():
    result = await (
        Flux.from_iterable(api_requests)
        .throttle(elements=10, duration=1.0)  # 초당 10개로 제한
        .flat_map(lambda req: call_api(req))
        .collect_list()
    )
    return result
```

### Production Deployment (New!)

```python
from rfs import ProductionDeployer, DeploymentStrategy
from rfs import deploy_to_production, rollback_deployment

# Blue-Green 배포
async def deploy_blue_green():
    result = await deploy_to_production(
        version="v2.0.0",
        strategy=DeploymentStrategy.BLUE_GREEN,
        environment="production"
    )
    
    if result.is_failure():
        # 자동 롤백
        await rollback_deployment(result.deployment_id)
    
    return result

# Canary 배포
async def deploy_canary():
    deployer = ProductionDeployer()
    result = await deployer.deploy(
        version="v2.0.0",
        strategy=DeploymentStrategy.CANARY,
        canary_percentage=10  # 10% 트래픽으로 시작
    )
    return result
```

### Security Hardening (New!)

```python
from rfs import SecurityHardening, SecurityPolicy, SecurityLevel
from rfs import apply_security_hardening

# 보안 정책 생성
policy = SecurityPolicy(
    name="production_policy",
    level=SecurityLevel.HIGH,
    require_mfa=True,
    min_password_length=16,
    encryption_algorithm="AES-256"
)

# 보안 강화 적용
hardening = SecurityHardening(policy)
result = hardening.apply_hardening()

if result.is_compliant:
    print(f"보안 점수: {result.success_rate}%")
else:
    print(f"보안 이슈: {result.critical_issues}")
```

### 설정 관리

```python
from rfs import RFSConfig, get_config

# 설정 파일 로드 (config.toml)
config = get_config()
print(f"애플리케이션 환경: {config.environment}")
print(f"데이터베이스 URL: {config.database.url}")

# 환경별 설정 사용
if config.environment == "production":
    print("프로덕션 환경에서 실행 중")
else:
    print("개발 환경에서 실행 중")
```

### State Machine

```python
from rfs import StateMachine, State, Transition
from rfs import Result

# 간단한 주문 상태 머신
order_machine = StateMachine(
    initial_state="pending",
    states=["pending", "processing", "completed", "cancelled"]
)

# 상태 전환
print(f"현재 상태: {order_machine.current_state}")  # pending
order_machine.transition_to("processing")
print(f"변경된 상태: {order_machine.current_state}")  # processing
```

## 🖥️ CLI Usage

### Project Management
```bash
# 새 프로젝트 생성
rfs-cli create-project my-awesome-app --template fastapi

# 프로젝트 정보 확인
rfs-cli project info

# 의존성 관리
rfs-cli project deps --install
```

### Development
```bash
# 개발 서버 실행
rfs-cli dev --reload --port 8000

# 코드 품질 검사
rfs-cli dev lint
rfs-cli dev test
rfs-cli dev security-scan
```

### Deployment
```bash
# Cloud Run 배포
rfs-cli deploy cloud-run --region asia-northeast3

# 배포 상태 확인
rfs-cli deploy status

# 로그 확인
rfs-cli deploy logs --follow
```

## 🏗️ Architecture

RFS Framework v4는 모듈러 아키텍처로 설계되어 필요에 따라 컴포넌트를 선택적으로 사용할 수 있습니다.

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                    │
├─────────────────────────────────────────────────────────┤
│  🛠️ CLI Tool        │  📊 Monitoring      │  🔒 Security  │
├─────────────────────────────────────────────────────────┤
│  ⚡ Reactive         │  🎭 State Machine   │  📡 Events    │  
├─────────────────────────────────────────────────────────┤
│  ☁️ Serverless       │  🔧 Core            │  🧪 Testing   │
├─────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                 │
└─────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Description | Key Components |
|--------|-------------|----------------|
| **Core** | 기본 패턴과 유틸리티 | Result, Config, Registry |
| **Reactive** | 반응형 프로그래밍 | Mono, Flux, Operators |
| **State Machine** | 상태 관리 | States, Transitions, Actions |
| **Events** | 이벤트 기반 아키텍처 | Event Store, CQRS, Saga |
| **Serverless** | 클라우드 네이티브 | Cloud Run, Functions |
| **CLI** | 개발자 도구 | Commands, Workflows |

## 📖 Examples

### E-commerce API

```python
from rfs import Result, Success, Failure
from rfs import StateMachine, State, Transition
from rfs.reactive import Flux, Mono

app = RFSApp()

# 주문 상태 머신
order_states = StateMachine.builder() \
    .add_state("pending") \
    .add_state("paid") \
    .add_state("shipped") \
    .add_state("delivered") \
    .add_transition("pending", "pay", "paid") \
    .add_transition("paid", "ship", "shipped") \
    .add_transition("shipped", "deliver", "delivered") \
    .build()

@app.route("/orders", method="POST")
async def create_order(order_data: dict) -> Result[dict, str]:
    # 주문 검증
    validation_result = await validate_order(order_data)
    if validation_result.is_failure():
        return validation_result
    
    # 상태 머신으로 주문 생성
    order = await order_states.create_instance(
        initial_state="pending",
        data=order_data
    )
    
    return Result.success({"order_id": order.id, "status": order.state})

@app.route("/orders/{order_id}/items")
async def get_order_items(order_id: str) -> Result[list, str]:
    # 반응형 스트림으로 주문 아이템 처리
    items = await (
        Flux.from_database(f"orders/{order_id}/items")
        .map(lambda item: {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "quantity": item.quantity
        })
        .filter(lambda item: item["quantity"] > 0)
        .collect_list()
        .to_result()
    )
    
    return items
```

## 🔧 Configuration

### Environment Configuration

```python
# config.toml
[development]
database_url = "sqlite:///dev.db"
redis_url = "redis://localhost:6379"
log_level = "DEBUG"

[production]
database_url = "${DATABASE_URL}"
redis_url = "${REDIS_URL}"
log_level = "INFO"

[cloud_run]
extends = "production"
port = 8080
workers = 4
```

### Application Configuration

```python
from rfs import RFSConfig, get_config

config = get_config()

# 환경별 설정 로드
if config.profile == ConfigProfile.PRODUCTION:
    # 프로덕션 설정
    pass
elif config.profile == ConfigProfile.DEVELOPMENT:
    # 개발 설정  
    pass
```

## 🧪 Testing

### Unit Testing

```python
import pytest
from rfs import Result, Success, Failure
from rfs.reactive import Mono, Flux

class TestUserService:
    async def test_get_user_success(self):
        result = await get_user(1)
        
        assert result.is_success()
        assert result.value["id"] == 1
    
    async def test_get_user_not_found(self):
        result = await get_user(999)
        
        assert result.is_failure()
        assert "not found" in result.error
        
    async def test_reactive_processing(self):
        result = await (
            Mono.just([1, 2, 3])
            .flat_map(lambda items: Flux.from_iterable(items))
            .map(lambda x: x * 2)
            .collect_list()
            .to_result()
        )
        
        assert result.is_success()
        assert result.value == [2, 4, 6]
```

### Integration Testing

```bash
# CLI를 통한 통합 테스트
rfs-cli test --integration

# 특정 모듈 테스트
rfs-cli test --module core
rfs-cli test --module reactive
```

## 📊 Performance

### Benchmarks

| Operation | RFS v3 | RFS v4 | Improvement |
|-----------|--------|--------|-------------|
| Cold Start | 3.2s | 1.8s | **44% faster** |
| Memory Usage | 128MB | 89MB | **30% less** |
| Throughput | 750 RPS | 1200 RPS | **60% more** |
| Response Time | 45ms | 28ms | **38% faster** |

### Optimization Tips

```python
# 1. 메모리 최적화를 위한 스트림 사용
async def process_large_dataset():
    return await (
        Flux.from_database("large_table")
        .buffer(100)  # 배치 처리
        .map(process_batch)
        .flat_map(lambda batch: Flux.from_iterable(batch))
        .collect_list()
        .to_result()
    )

# 2. 캐싱으로 성능 향상
@app.cache(ttl=300)  # 5분 캐시
async def expensive_operation() -> Result[str, str]:
    # 비용이 큰 연산
    pass

# 3. 비동기 병렬 처리
async def parallel_processing():
    tasks = [
        process_user(user_id) 
        for user_id in user_ids
    ]
    results = await Flux.merge(*tasks).collect_list().to_result()
    return results
```

## 🔒 Security

RFS v4는 보안을 최우선으로 설계되었습니다.

### Security Features
- **🔍 Vulnerability Scanning**: 자동 취약점 탐지
- **🔐 Encryption**: AES-256 데이터 암호화  
- **🎫 Authentication**: JWT 토큰 기반 인증
- **🛡️ Input Validation**: 자동 입력 검증 및 살균
- **📋 Compliance**: OWASP Top 10 준수

### Security Best Practices

```python
from rfs import SecurityScanner, SecurityHardening, SecurityPolicy

# 보안 스캔
scanner = SecurityScanner()
vulnerabilities = await scanner.scan_directory("./src")

# 데이터 암호화
encrypted_data = encrypt("sensitive information", key)
decrypted_data = decrypt(encrypted_data, key)

# 입력 검증
@app.route("/api/users")
@validate_input(UserCreateSchema)
async def create_user(data: dict) -> Result[dict, str]:
    # 자동으로 검증된 데이터
    pass
```

## 🚀 Deployment

### Cloud Run Deployment

```bash
# 1. 프로젝트 빌드
rfs-cli build --platform cloud-run

# 2. 배포
rfs-cli deploy cloud-run \
  --region asia-northeast3 \
  --memory 1Gi \
  --cpu 2 \
  --max-instances 100

# 3. 도메인 매핑
rfs-cli deploy domain --name api.example.com
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["rfs-cli", "serve", "--port", "8080"]
```

## 📚 Documentation

### 📖 상세 문서 (Wiki)

RFS Framework의 모든 기능에 대한 상세한 가이드와 예제를 제공합니다:

#### 🔧 핵심 시스템
- **[핵심 패턴](./wiki/01-core-patterns.md)** - Result 패턴과 함수형 프로그래밍
- **[의존성 주입](./wiki/02-dependency-injection.md)** - 헥사고날 아키텍처와 DI 시스템
- **[설정 관리](./wiki/03-configuration.md)** - 환경별 설정과 동적 재로딩
- **[트랜잭션](./wiki/04-transactions.md)** - 분산 트랜잭션과 Saga 패턴

#### 🚀 프로덕션 기능
- **[배포 전략](./wiki/05-deployment.md)** - Blue-Green, Canary, Rolling 배포
- **[롤백 관리](./wiki/06-rollback.md)** - 체크포인트 기반 복구 시스템
- **[로깅](./wiki/07-logging.md)** - 감사 로깅과 로깅 데코레이터
- **[모니터링](./wiki/08-monitoring.md)** - 성능 메트릭과 모니터링

#### 🔒 보안 & 검증
- **[검증 시스템](./wiki/09-validation.md)** - 포괄적인 시스템 검증
- **[접근 제어](./wiki/10-access-control.md)** - RBAC/ABAC 구현
- **[보안 강화](./wiki/11-security.md)** - 보안 스캐닝과 취약점 검사

#### ⚡ 고급 패턴
- **[서킷 브레이커](./wiki/12-circuit-breaker.md)** - 장애 격리와 복구
- **[로드 밸런싱](./wiki/13-load-balancing.md)** - 다양한 로드 밸런싱 알고리즘

### 📚 일반 문서
- **[API Reference](./docs/api/)** - 완전한 API 문서
- **[User Guide](./docs/guide/)** - 단계별 사용 가이드  
- **[Examples](./examples/)** - 실제 예제 코드
- **[Migration Guide](./docs/migration/)** - v3에서 v4로 마이그레이션
- **[Contributing](./CONTRIBUTING.md)** - 기여 가이드
- **[Changelog](./CHANGELOG.md)** - 변경 이력

## 🤝 Contributing

RFS Framework는 오픈소스 프로젝트입니다. 기여를 환영합니다!

```bash
# 1. 저장소 포크
git clone https://github.com/interactord/rfs-framework.git

# 2. 개발 환경 설정
cd rfs-framework
pip install -e ".[dev]"

# 3. 테스트 실행
rfs-cli test --all

# 4. PR 생성
git checkout -b feature/awesome-feature
git commit -m "feat: add awesome feature"
git push origin feature/awesome-feature
```

### Development Setup

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 개발용 의존성 설치
pip install -e ".[dev,test,docs]"

# 프리커밋 훅 설정
pre-commit install
```

## 📊 Roadmap

### v4.1 (2025 Q3)
- 🔌 플러그인 시스템
- 🌐 GraphQL 지원
- 📱 모바일 SDK

### v4.2 (2025 Q4)  
- 🤖 AI/ML 통합
- 📊 고급 모니터링
- 🔄 자동 스케일링 개선

### v5.0 (2026 Q1)
- 🦀 Rust 확장
- ⚡ 성능 최적화
- 🌍 다중 클라우드 지원

## 🆘 Support

### Community
- **💬 Discord**: [RFS Community](https://discord.gg/rfs-framework)
- **📧 Email**: support@rfs-framework.dev
- **🐛 Issues**: [GitHub Issues](https://github.com/interactord/rfs-framework/issues)
- **📖 Docs**: [Documentation](https://github.com/interactord/rfs-framework#documentation)

### Enterprise Support
엔터프라이즈 지원이 필요하시면 enterprise@rfs-framework.dev로 연락해 주세요.

## 📄 License

MIT License - 자세한 내용은 [LICENSE](./LICENSE) 파일을 참조하세요.

---

**Made with ❤️ by the RFS Framework Team**

[![GitHub stars](https://img.shields.io/github/stars/interactord/rfs-framework.svg?style=social&label=Star)](https://github.com/interactord/rfs-framework)
[![GitHub forks](https://img.shields.io/github/forks/interactord/rfs-framework.svg?style=social&label=Fork)](https://github.com/interactord/rfs-framework/fork)
[![PyPI version](https://badge.fury.io/py/rfs-framework.svg)](https://pypi.org/project/rfs-framework/)