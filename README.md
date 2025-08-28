# RFS Framework 🚀

📖 **[Documentation](https://interactord.github.io/rfs-framework/)** | [한국어 문서](./docs/)

> **Enterprise-Grade Reactive Functional Serverless Framework for Python**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/Version-4.4.0-green.svg)](https://pypi.org/project/rfs-framework/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Cloud Run Ready](https://img.shields.io/badge/Cloud%20Run-Ready-green.svg)](https://cloud.google.com/run)
[![Code Coverage](https://codecov.io/gh/interactord/rfs-framework/branch/main/graph/badge.svg)](https://codecov.io/gh/interactord/rfs-framework)
[![Build Status](https://github.com/interactord/rfs-framework/workflows/CI/badge.svg)](https://github.com/interactord/rfs-framework/actions)
[![Code Quality](https://img.shields.io/codacy/grade/YOUR_PROJECT_ID?label=Code%20Quality)](https://www.codacy.com/gh/interactord/rfs-framework)
[![PyPI Downloads](https://img.shields.io/pypi/dm/rfs-framework.svg)](https://pypi.org/project/rfs-framework/)
[![GitHub Stars](https://img.shields.io/github/stars/interactord/rfs-framework?style=social)](https://github.com/interactord/rfs-framework)
[![GitHub Issues](https://img.shields.io/github/issues/interactord/rfs-framework)](https://github.com/interactord/rfs-framework/issues)

현대적인 엔터프라이즈 Python 애플리케이션을 위한 함수형 프로그래밍 프레임워크입니다.

## 🎯 Why RFS Framework?

- **타입 안전성**: Result 패턴으로 예외 없는 에러 처리
- **반응형 스트림**: Mono/Flux 패턴의 비동기 처리  
- **웹 통합**: FastAPI + AsyncResult 완벽 통합 ✨ **NEW v4.4.0**
- **프로덕션 로깅**: 민감 데이터 마스킹 및 메트릭 수집 ✨ **NEW v4.4.0**
- **포괄적 테스팅**: AsyncResult 전용 테스팅 도구 ✨ **NEW v4.4.0**
- **클라우드 네이티브**: Google Cloud Run 최적화
- **프로덕션 준비**: 모니터링, 보안, 배포 전략 내장

## ⚡ Quick Start

### Installation

```bash
# PyPI에서 최신 버전 설치 (v4.4.0)
pip install rfs-framework

# 새로운 웹 통합 기능 포함 🚀
pip install "rfs-framework[web]"     # FastAPI + AsyncResult 통합
pip install "rfs-framework[database]"  # 데이터베이스 지원
pip install "rfs-framework[test]"      # AsyncResult 테스팅 도구
pip install "rfs-framework[dev]"       # 개발 도구 및 코드 품질
pip install "rfs-framework[docs]"      # 문서화 도구
pip install "rfs-framework[ai]"        # AI/ML 통합 (Experimental)

# 모든 기능 포함 (권장)
pip install "rfs-framework[all]"

# 최신 개발 버전 설치
pip install git+https://github.com/interactord/rfs-framework.git
```

자세한 설치 옵션은 [설치 가이드](./INSTALLATION.md)를 참조하세요.

### Basic Example

```python
from rfs import Result, Success, Failure

def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Failure("Cannot divide by zero")
    return Success(a / b)

# 안전한 에러 처리
result = divide(10, 2)
if result.is_success:
    print(f"Result: {result.unwrap()}")  # Result: 5.0
```

### 🆕 AsyncResult Web Integration (v4.4.0)

```python
from fastapi import FastAPI, HTTPException
from rfs.web.fastapi_helpers import async_result_to_response
from rfs.logging.async_logging import AsyncResultLogger, log_async_chain

app = FastAPI()
logger = AsyncResultLogger()

# FastAPI + AsyncResult 완벽 통합
@app.get("/users/{user_id}")
@log_async_chain(logger, "get_user")  # 자동 로깅 및 메트릭
async def get_user(user_id: str):
    # AsyncResult 체인 (함수형 프로그래밍)
    result = await (
        fetch_user(user_id)
        .bind(validate_permissions)
        .bind(enrich_user_profile)
    )
    
    # AsyncResult → JSONResponse 자동 변환
    return await async_result_to_response(
        result,
        error_mapper=lambda e: HTTPException(status_code=404, detail=str(e))
    )

# 민감 데이터 자동 마스킹, p50/p90/p99 메트릭 자동 수집
```

### Reactive Streams

```python
from rfs.reactive import Flux
import asyncio

async def process_data():
    result = await (
        Flux.from_iterable(range(100))
        .parallel(4)  # 4개 스레드 병렬 처리
        .map(lambda x: x * x)
        .filter(lambda x: x % 2 == 0)
        .collect_list()
    )
    return result
```

더 많은 예제는 [Examples Directory](./examples/)를 참조하세요.

## 🏗️ Architecture

```
Application Layer
├── CLI & Tools       → 개발자 도구
├── Web Framework     → FastAPI + AsyncResult 통합 ✨
├── Testing Suite     → AsyncResult 전용 테스팅 도구 ✨
└── Cloud Services    → GCP 통합

Core Layer
├── Result Pattern    → 함수형 에러 처리
├── Reactive Streams  → 비동기 스트림
├── AsyncResult Web   → FastAPI 완벽 통합 ✨ NEW
├── State Machine     → 상태 관리
└── Event Sourcing    → CQRS/이벤트 스토어

Infrastructure Layer
├── Security          → RBAC/ABAC, JWT
├── Monitoring        → 메트릭, 프로덕션 로깅 ✨
├── Deployment        → Blue-Green, Canary
└── Optimization      → 성능 최적화
```

## 📚 Documentation

### 핵심 문서
- **[핵심 개념](./docs/01-core-patterns.md)** - Result 패턴과 함수형 프로그래밍
- **[API Reference](./docs/API_REFERENCE.md)** - 전체 API 문서
- **[사용자 가이드](./docs/USER_GUIDE.md)** - 단계별 사용 안내

### 주제별 가이드
- **[설정 관리](./docs/03-configuration.md)** - 환경별 설정
- **[보안](./docs/11-security.md)** - 인증, 인가, 보안 강화
- **[배포](./docs/05-deployment.md)** - 프로덕션 배포 전략
- **[CLI 도구](./docs/14-cli-interface.md)** - 명령행 인터페이스

### 전체 문서
- **[📖 Docs (한국어)](./docs/)** - 17개 모듈 상세 문서
- **[📚 HOF Library](./docs/22-hot-library.md)** - Higher-Order Functions
- **[마이그레이션 가이드](./MIGRATION_GUIDE.md)** - v3에서 v4로 업그레이드

## 🛠️ Development

### RFS Framework 규칙 준수 🔴

**필수**: 개발 전 [규칙 문서](./rules/README.md) 숙지 필요

```bash
# 규칙 검증 (필수)
python scripts/validate_rfs_rules.py

# 한글 주석 및 Result 패턴 자동 검증
python scripts/validate_rfs_rules.py --strict

# pre-commit 훅 설정 (권장)
pip install pre-commit
pre-commit install
```

**핵심 준수 사항**:
- ✅ 모든 주석은 한글로 작성
- ✅ 예외 대신 Result 패턴 사용
- ✅ RFS Framework 기능 우선 사용
- ✅ 불변성 유지 (frozen dataclass 등)

### Commands

```bash
# 개발 서버
rfs-cli dev --reload

# 테스트
pytest --cov=rfs

# 코드 품질
black src/ && mypy src/

# 시스템 상태
rfs status  # 16개 핵심 기능 모니터링
```

### Project Structure

```
rfs-framework/
├── src/rfs/
│   ├── core/          # Result 패턴, DI, 설정
│   ├── reactive/      # Mono/Flux 스트림
│   ├── hof/           # Higher-Order Functions
│   ├── production/    # 프로덕션 시스템
│   └── cloud_run/     # Cloud Run 통합
├── tests/             # 테스트 스위트
├── docs/              # 한국어 문서
└── examples/          # 예제 코드
```

## ✨ Key Features

### 🎯 함수형 프로그래밍
- Result/Maybe/Either 모나드
- 함수 합성과 커링
- 불변성과 순수 함수
- [상세 문서 →](./docs/01-core-patterns.md)

### ⚡ 반응형 스트림
- 비동기 Mono/Flux 패턴
- 백프레셔 지원
- 30+ 연산자
- [상세 문서 →](./docs/README.md#reactive-programming)

### 🔒 엔터프라이즈 보안
- RBAC/ABAC 접근 제어
- JWT 인증
- 취약점 스캐닝
- [상세 문서 →](./docs/11-security.md)

### 🚀 프로덕션 준비
- Blue-Green/Canary 배포
- Circuit Breaker 패턴
- 성능 모니터링
- [상세 문서 →](./docs/05-deployment.md)

## 📊 Performance

| Metric | Value | Note |
|--------|-------|------|
| **시작 시간** | ~50ms | CLI 초기화 |
| **메모리 사용** | ~25MB | 기본 실행 |
| **응답 시간** | <100ms | API 호출 |
| **처리량** | 1200 RPS | 벤치마크 |

## 🚧 Status

- **완성도**: 95% (v4.4.0) - [현재 커버리지 ~10%](https://codecov.io/gh/interactord/rfs-framework)
- **프로덕션 준비**: ✅ Ready
- **미완성 항목**: [TODO.md](./TODO.md) 참조

## 🤝 Contributing

기여를 환영합니다! [Contributing Guide](./CONTRIBUTING.md)를 참조하세요.

```bash
# 개발 환경 설정
git clone https://github.com/interactord/rfs-framework
cd rfs-framework
pip install -e ".[dev]"

# 규칙 검증 및 준수 (필수)
python scripts/validate_rfs_rules.py

# 테스트 실행
pytest

# PR 제출 전 최종 검증
python scripts/validate_rfs_rules.py --strict
git checkout -b feature/your-feature
git commit -m "feat: 새로운 기능 추가"  # 한글 커밋 메시지
git push origin feature/your-feature
```

## 📄 License

MIT License - [LICENSE](./LICENSE) 참조

## 🆘 Support

- **문제 보고**: [GitHub Issues](https://github.com/interactord/rfs-framework/issues)
- **토론**: [Discussions](https://github.com/interactord/rfs-framework/discussions)
- **문서**: [Wiki](https://github.com/interactord/rfs-framework/wiki)

---

**Made with ❤️ by the RFS Framework Team**