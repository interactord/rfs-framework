# RFS Framework CLI 가이드

RFS Framework v4.3.0의 명령행 인터페이스(CLI) 사용 가이드입니다.

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
# PyPI에서 설치
pip install rfs-framework

# CLI 실행
rfs version
rfs-cli status
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
$ rfs version
╭────────────────────────── RFS Framework 버전 정보 ───────────────────────────╮
│ 🏷️  버전: 4.3.0                                                               │
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
$ rfs help
RFS Framework CLI v4.3.0
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
$ rfs config
RFS Framework Configuration
Version: 4.3.0
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

### 🚧 계획된 기능

향후 릴리즈에서 CLI를 통해 제공될 기능들:

- `rfs init` - 새 프로젝트 초기화
- `rfs dev` - 개발 서버 시작
- `rfs build` - 프로덕션 빌드
- `rfs deploy` - Cloud Run 배포
- `rfs test` - 테스트 실행
- `rfs docs` - 문서 생성

## 시스템 요구사항

- **Python**: 3.10 이상
- **운영체제**: Linux, macOS, Windows
- **필수 의존성**: 
  - pydantic >= 2.5.0
  - rich >= 13.7.0 (UI용)
- **선택적 의존성**:
  - fastapi >= 0.104.0 (웹 기능)
  - google-cloud-run >= 0.10.0 (Cloud Run)

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

### 디버깅

CLI에서 오류가 발생하는 경우:

1. Python 버전 확인: `python3 --version`
2. 의존성 상태 확인: `rfs status`
3. 프로젝트 루트 확인: `rfs config`

## 관련 링크

- 📚 **Korean Docs**: [13개 모듈 문서](./docs/)
- 🔗 **GitHub**: https://github.com/interactord/rfs-framework
- 📦 **PyPI**: https://pypi.org/project/rfs-framework/
- 🏷️ **Latest Release**: v4.3.0 (Production Ready)

---

*이 문서는 RFS Framework v4.3.0 기준으로 작성되었습니다.*