# RFS Framework CLI 가이드

RFS Framework v4.3.1의 명령행 인터페이스(CLI) 사용 가이드입니다.

> ⚠️ **주의**: 일부 CLI 명령어는 현재 개발 중이며, 향후 릴리즈에서 제공될 예정입니다.

## 개요

RFS CLI는 Enterprise-Grade Reactive Functional Serverless Framework의 개발 워크플로우를 지원하는 강력한 도구입니다.

### 주요 특징

- 🎨 **Rich UI**: 아름다운 콘솔 출력과 테이블
- 🏗️ **Production Ready**: 모든 프레임워크 기능 완성
- 🔧 **독립 실행**: 임포트 오류 없는 안정적 실행  
- 📊 **상태 모니터링**: 시스템 및 기능 상태 확인
- 🌐 **한국어 지원**: 완전한 한국어 문서 및 메시지

## 설치 및 실행

### 패키지 설치를 통한 실행

```bash
# PyPI에서 최신 버전 설치
pip install rfs-framework

# 특정 버전 설치 (버그 수정된 버전)
pip install rfs-framework==4.3.1

# CLI 실행
rfs-cli version
rfs-cli status

# 또는 짧은 명령어
rfs version
rfs status
```

### 소스에서 직접 실행

```bash
# 저장소 클론
git clone https://github.com/interactord/rfs-framework
cd rfs-framework

# 직접 실행
python3 rfs_cli.py version
```

## 사용 가능한 명령어

### 기본 명령어

#### `rfs version`
프레임워크 버전 및 기능 정보 표시

```bash
$ rfs-cli version
╭────────────────────────── RFS Framework 버전 정보 ───────────────────────────╮
│ 🏷️  버전: 4.3.1                                                               │
│ 📅 릴리스: 2025년 8월                                                        │
│ 🎯 단계: Production Ready                                                    │
│ 🐍 Python: 3.10+                                                             │
│ ☁️  플랫폼: Google Cloud Run                                                  │
│ 🏗️  아키텍처: Hexagonal Architecture                                          │
│ 🔒 보안: RBAC/ABAC with JWT                                                  │
│ 📊 모니터링: Performance & Security Monitoring                               │
│ ⚡ 최적화: Circuit Breaker & Load Balancing                                  │
│ 📚 문서: 13개 한국어 모듈 완성                                               │
│ 🚀 배포: Blue-Green, Canary, Rolling Strategies                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

#### `rfs status`
시스템 상태 및 프레임워크 기능 상태 확인

```bash
$ rfs status
RFS Framework System Status
Framework: ✅ Production Ready
Python: 3.12.8
Environment: Production Ready

# 16개 핵심 기능의 상태 테이블 표시:
# - Core: Result Pattern, Reactive Streams
# - Architecture: Hexagonal Architecture, DI
# - Security: RBAC/ABAC, JWT Authentication  
# - Resilience: Circuit Breaker, Load Balancing
# - Monitoring: Performance Monitoring, Security Logging
# - Deployment: Blue-Green, Canary, Rolling, Rollback
# - Cloud: Google Cloud Run Optimization
# - Docs: Korean Documentation (13 modules)
```

#### `rfs help`
사용 가능한 명령어 및 옵션 표시

```bash
$ rfs-cli help
RFS Framework CLI v4.3.1
Enterprise-Grade Reactive Functional Serverless Framework

Available Commands:
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Command ┃ Description              ┃ Example                             ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ version │ Show framework version   │ rfs version                         │
│ status  │ Check system status      │ rfs status                          │
│ help    │ Show this help message   │ rfs help                            │
│ config  │ Show configuration       │ rfs config                          │
└─────────┴──────────────────────────┴─────────────────────────────────────┘
```

#### `rfs config`
프레임워크 설정 정보 표시

```bash
$ rfs-cli config
RFS Framework Configuration
Version: 4.3.1
Phase: Production Ready
Project Root: /path/to/your/project
```

### 전역 옵션

```bash
# 버전 정보 표시
rfs --version
rfs -v

# 도움말 표시  
rfs --help
rfs -h

# Verbose 모드 (계획됨)
rfs --verbose status
```

## 프레임워크 기능 상태

RFS Framework v4.3.0에서 지원하는 모든 기능들:

### ✅ 구현 완료된 기능

1. **Core Pattern (핵심 패턴)**
   - Result Pattern & Functional Programming
   - Reactive Streams (Mono/Flux)

2. **Architecture (아키텍처)**
   - Hexagonal Architecture
   - Annotation-based Dependency Injection

3. **Security (보안)**
   - RBAC/ABAC Access Control
   - JWT Authentication

4. **Resilience (복원력)**
   - Circuit Breaker Pattern
   - Client-side Load Balancing

5. **Monitoring (모니터링)**
   - Performance Monitoring & Metrics
   - Security Event Logging

6. **Deployment (배포)**
   - Blue-Green Strategy
   - Canary Strategy
   - Rolling Strategy
   - Rollback Management

7. **Cloud (클라우드)**
   - Google Cloud Run Optimization

8. **Documentation (문서)**
   - Korean Documentation (13 modules)

## 🖥️ 서버 실행 방법

### Python으로 직접 서버 실행

RFS Framework를 사용한 웹 서버 애플리케이션 실행:

```python
# app.py - 기본 RFS 서버 애플리케이션
from fastapi import FastAPI
from rfs.core.result import Success, Failure

# FastAPI 앱 생성
app = FastAPI(title="RFS API Server")

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "RFS Framework Server", "version": "4.3.1"}

@app.get("/health")
async def health():
    """헬스 체크"""
    return Success({"status": "healthy", "framework": "RFS"}).unwrap()

# Uvicorn으로 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
```

**서버 실행 명령어:**
```bash
# 직접 Python으로 실행
python app.py

# Uvicorn으로 실행 (자동 재시작)
uvicorn app:app --reload --host 0.0.0.0 --port 8080

# 프로덕션 모드 (Gunicorn)
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

### RFS 게이트웨이 서버 (FastAPI 필요)

```python
# gateway_server.py - RFS 게이트웨이 사용
# 주의: FastAPI 설치 필요 (pip install fastapi[all])
from rfs.gateway import create_gateway_app
from rfs.core.result import Success, Failure

# 게이트웨이 앱 생성 (FastAPI 앱 반환)
app = create_gateway_app(
    title="RFS Gateway API",
    version="1.0.0"
)

if app is None:
    print("FastAPI가 설치되지 않았습니다. pip install fastapi[all] 실행 필요")
    import sys
    sys.exit(1)

@app.post("/api/process")
async def process_data(data: dict):
    """데이터 처리 API"""
    # Result 패턴 사용
    if not data:
        result = Failure("No data provided")
        return {"success": False, "error": result.error}
    
    # 처리 로직
    processed = {**data, "processed": True}
    result = Success(processed)
    return {"success": True, "data": result.value}

# 실행: uvicorn gateway_server:app --reload
```

### 환경 변수 설정

```bash
# .env 파일
RFS_ENV=development
RFS_LOG_LEVEL=DEBUG
RFS_PORT=8080

# 환경변수와 함께 실행
export $(cat .env | xargs) && python app.py
```

### 🚧 계획된 기능 (향후 릴리즈)

다음 CLI 명령어들은 현재 개발 중이며 향후 릴리즈에서 제공될 예정입니다:

- `rfs init` - 새 프로젝트 초기화 (계획됨)
- `rfs dev` - 개발 서버 시작 (현재는 uvicorn 직접 사용)
- `rfs build` - 프로덕션 빌드 (계획됨)
- `rfs deploy` - Cloud Run 배포 (계획됨)
- `rfs test` - 테스트 실행 (계획됨)
- `rfs docs` - 문서 생성 (계획됨)

**현재 사용 가능한 명령어**: `version`, `status`, `config`, `help`

## 시스템 요구사항

- **Python**: 3.10 이상
- **운영체제**: Linux, macOS, Windows
- **필수 의존성**: 
  - pydantic >= 2.5.0
  - rich >= 13.7.0 (UI용)
- **선택적 의존성** (웹 서버 기능):
  - fastapi >= 0.104.0 (웹 애플리케이션)
  - uvicorn >= 0.24.0 (ASGI 서버)
  - google-cloud-run >= 0.10.0 (Cloud Run 최적화)

## 📝 개발 워크플로우

### 1. 새 프로젝트 시작

```bash
# 디렉토리 생성
mkdir my-rfs-app && cd my-rfs-app

# RFS Framework 설치
pip install rfs-framework==4.3.1

# 웹 서버 기능을 사용할 경우 추가 패키지 설치
pip install fastapi uvicorn

# 가상환경 설정 (권장)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\\Scripts\\activate  # Windows
```

### 2. 프로젝트 구조

```
my-rfs-app/
├── app.py              # 메인 애플리케이션
├── requirements.txt    # 의존성
├── .env               # 환경 변수
├── src/
│   ├── api/          # API 엔드포인트
│   ├── services/     # 비즈니스 로직
│   └── models/       # 데이터 모델
└── tests/
    └── test_app.py   # 테스트
```

### 3. 개발 서버 실행

```bash
# 개발 모드로 실행 (자동 재시작)
uvicorn app:app --reload

# 특정 포트로 실행
uvicorn app:app --reload --port 8000

# 외부 접속 허용
uvicorn app:app --reload --host 0.0.0.0
```

### 4. 테스트 실행

```bash
# pytest 설치
pip install pytest pytest-asyncio

# 테스트 실행
pytest tests/

# 커버리지 포함
pytest --cov=src tests/
```

## 문제 해결

### 일반적인 문제

**Python 버전 오류**
```bash
❌ RFS Framework requires Python 3.10 or higher
Current version: Python 3.9
```
→ Python 3.10 이상으로 업그레이드

**의존성 누락**
```bash
Dependencies Status:
❌ pydantic (>=2.5.0)
```
→ `pip install pydantic>=2.5.0`

**Rich UI 미사용**
- Rich가 설치되지 않은 경우 기본 텍스트 출력 사용
- `pip install rich>=13.7.0` 설치 권장

**FastAPI 누락 오류**
```python
ModuleNotFoundError: No module named 'fastapi'
```
→ `pip install fastapi uvicorn` 실행

**게이트웨이 앱 생성 실패**
```python
FastAPI not installed. Install with: pip install fastapi[all]
```
→ FastAPI와 관련 의존성 설치: `pip install fastapi[all]`

### 디버깅

CLI에서 오류가 발생하는 경우:

1. Python 버전 확인: `python3 --version`
2. 의존성 상태 확인: `rfs status`
3. 프로젝트 루트 확인: `rfs config`

## 관련 링크

- 📚 **Korean Docs**: [13개 모듈 문서](./docs/)
- 🔗 **GitHub**: https://github.com/interactord/rfs-framework
- 📦 **PyPI**: https://pypi.org/project/rfs-framework/
- 🏷️ **Latest Release**: v4.3.1 (Bug Fix Release)
- 🐛 **Fixed**: field import error in config.py

## 최근 변경사항

### v4.3.1 (2025-08-27)
- 🐛 **버그 수정**: config.py의 field import 오류 해결
- 🐛 **버그 수정**: gateway 모듈 import 오류 수정 (임시 플레이스홀더 추가)
- 📝 **문서 개선**: CLI 가이드 업데이트 및 서버 실행 방법 추가
- ✅ **안정성**: Pydantic 경로 일관성 확보
- ⚠️ **알려진 문제**: 일부 CLI 명령어가 아직 구현되지 않음 (init, dev, build, deploy, test, docs)

### v4.3.0 (2025-08)  
- 🚀 **Production Ready**: 모든 핵심 기능 완성
- 📚 **문서화**: 13개 한국어 모듈 완성
- ☁️ **Cloud Run**: 최적화 완료

---

*이 문서는 RFS Framework v4.3.1 기준으로 작성되었습니다.*