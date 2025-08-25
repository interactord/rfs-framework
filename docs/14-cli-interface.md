# CLI 인터페이스 (Command Line Interface)

## 개요

RFS Framework CLI는 개발자 경험을 극대화하기 위해 설계된 Enterprise-Grade 명령행 인터페이스입니다. Rich UI를 통한 아름다운 출력, 포괄적인 시스템 모니터링, 그리고 직관적인 명령어 체계를 제공합니다.

## 핵심 특징

### 🎨 Rich Console UI
- **컬러풀한 출력**: 상태별 색상 코딩 (성공: 초록, 경고: 노랑, 오류: 빨강)
- **테이블 형태**: 구조화된 정보 표시
- **진행률 표시**: 작업 진행 상황 시각화
- **아이콘 지원**: 이모지를 활용한 직관적 정보 전달

### 🔍 포괄적인 시스템 모니터링
- **16개 핵심 기능**: 모든 프레임워크 기능의 상태 실시간 확인
- **의존성 검증**: 필수 및 선택적 의존성 상태 확인
- **환경 감지**: 개발/테스트/프로덕션 환경 자동 감지
- **프로젝트 탐지**: RFS 프로젝트 루트 자동 탐지

### ⚡ 고성능 및 안정성
- **독립 실행**: 프레임워크 임포트 오류와 무관하게 실행
- **빠른 응답**: 100ms 이내 명령어 응답
- **메모리 효율**: 최소 메모리 사용량
- **오류 복구**: Graceful error handling

## 설치 및 요구사항

### 시스템 요구사항

#### 필수 요구사항
```yaml
Python: 3.10 이상
운영체제: Linux, macOS, Windows
메모리: 최소 512MB RAM
디스크: 최소 100MB 여유공간
```

#### 권장 사양
```yaml
Python: 3.11 이상
메모리: 1GB 이상 RAM
터미널: True Color 지원 터미널
폰트: Nerd Font 또는 Unicode 지원 폰트
```

### 의존성

#### 필수 의존성
```toml
pydantic = ">=2.5.0"  # 타입 안전성 및 설정 관리
typing-extensions = ">=4.8.0"  # Python 3.10 호환성
```

#### 권장 의존성
```toml
rich = ">=13.7.0"  # Rich Console UI (없으면 기본 텍스트)
```

#### 선택적 의존성
```toml
# 웹 개발
fastapi = ">=0.104.0"
uvicorn = ">=0.24.0"

# 클라우드
google-cloud-run = ">=0.10.0"
google-cloud-tasks = ">=2.15.0"
google-cloud-monitoring = ">=2.16.0"

# 데이터베이스
sqlalchemy = ">=2.0.23"
asyncpg = ">=0.29.0"
redis = ">=5.0.1"
```

## 설치 방법

### 1. PyPI 패키지 설치 (권장)

```bash
# 기본 설치
pip install rfs-framework

# Rich UI 포함 설치
pip install rfs-framework[dev]

# 모든 기능 포함 설치
pip install rfs-framework[all]

# 설치 확인
rfs version
```

### 2. 소스 코드에서 설치

```bash
# 저장소 클론
git clone https://github.com/interactord/rfs-framework.git
cd rfs-framework

# 개발 모드 설치
pip install -e ".[dev]"

# CLI 실행 확인
python3 rfs_cli.py version
```

### 3. Docker를 통한 실행

```dockerfile
FROM python:3.11-slim

# RFS Framework 설치
RUN pip install rfs-framework[all]

# CLI 실행
CMD ["rfs", "status"]
```

## 명령어 상세 가이드

### 1. `rfs version` - 버전 정보 표시

프레임워크의 상세한 버전 정보와 모든 기능을 확인합니다.

#### 사용법
```bash
rfs version
rfs --version
rfs -v
```

#### 출력 정보
```yaml
버전: 4.3.0
릴리스 날짜: 2025년 8월
개발 단계: Production Ready
Python 요구사항: 3.10+
클라우드 플랫폼: Google Cloud Run
아키텍처: Hexagonal Architecture
보안: RBAC/ABAC with JWT
모니터링: Performance & Security Monitoring
최적화: Circuit Breaker & Load Balancing
문서화: 13개 한국어 모듈 완성
배포 전략: Blue-Green, Canary, Rolling Strategies
```

#### Rich UI 출력 예시
```
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

### 2. `rfs status` - 시스템 상태 모니터링

프레임워크의 모든 기능 상태와 시스템 환경을 포괄적으로 점검합니다.

#### 사용법
```bash
rfs status
rfs stat
```

#### 모니터링되는 16개 핵심 기능

| 카테고리 | 기능 | 설명 | 버전 |
|---------|------|------|------|
| **Core** | Result Pattern & Functional Programming | 함수형 에러 핸들링 | v4.3.0 |
| **Core** | Reactive Streams (Mono/Flux) | 비동기 스트림 처리 | v4.3.0 |
| **Architecture** | Hexagonal Architecture | 포트-어댑터 패턴 | v4.3.0 |
| **Architecture** | Annotation-based Dependency Injection | 어노테이션 기반 DI | v4.3.0 |
| **Security** | RBAC/ABAC Access Control | 역할/속성 기반 접근 제어 | v4.3.0 |
| **Security** | JWT Authentication | JWT 인증 시스템 | v4.3.0 |
| **Resilience** | Circuit Breaker Pattern | 장애 허용 패턴 | v4.3.0 |
| **Resilience** | Client-side Load Balancing | 클라이언트 로드 밸런싱 | v4.3.0 |
| **Monitoring** | Performance Monitoring & Metrics | 성능 모니터링 | v4.3.0 |
| **Monitoring** | Security Event Logging | 보안 이벤트 로깅 | v4.3.0 |
| **Deployment** | Blue-Green Strategy | 블루-그린 배포 | v4.3.0 |
| **Deployment** | Canary Strategy | 카나리 배포 | v4.3.0 |
| **Deployment** | Rolling Strategy | 롤링 배포 | v4.3.0 |
| **Deployment** | Rollback Management | 롤백 관리 | v4.3.0 |
| **Cloud** | Google Cloud Run Optimization | 클라우드 런 최적화 | v4.3.0 |
| **Docs** | Korean Documentation (13 modules) | 한국어 문서화 | v4.3.0 |

#### 의존성 상태 확인
```bash
Dependencies Status:
  ✅ pydantic (>=2.5.0)
  ✅ rich (>=13.7.0)
  ❌ fastapi (>=0.104.0) - optional
  ✅ google-cloud-run (>=0.10.0) - optional
```

#### 시스템 정보
```yaml
프레임워크 상태: Production Ready
Python 버전: 3.12.8
프로젝트 루트: /path/to/your/project
환경: Development/Production
```

### 3. `rfs help` - 도움말 및 사용법

모든 사용 가능한 명령어와 옵션을 확인합니다.

#### 사용법
```bash
rfs help
rfs --help
rfs -h
```

#### 표시되는 정보
- 사용 가능한 모든 명령어
- 각 명령어의 설명 및 예시
- 전역 옵션
- 프레임워크 정보 및 링크

### 4. `rfs config` - 설정 정보 표시

현재 프레임워크 설정과 프로젝트 정보를 확인합니다.

#### 사용법
```bash
rfs config
rfs cfg
```

#### 표시되는 설정 정보
```yaml
Framework Configuration:
  버전: 4.3.0
  개발 상태: Production Ready
  최소 Python: 3.10+
  핵심 기능: 16개 모듈
  문서화: Korean (13 modules)
  아키텍처: Hexagonal
  보안: RBAC/ABAC
  클라우드 플랫폼: Google Cloud Run
  패키지 이름: rfs-framework
```

## 고급 사용법

### 1. 프로젝트 감지

CLI는 현재 디렉토리에서 상위로 탐색하여 RFS 프로젝트를 자동 감지합니다.

#### 프로젝트 마커 파일
```yaml
우선순위 1: rfs.yaml, rfs.json
우선순위 2: pyproject.toml
우선순위 3: requirements.txt
```

#### 프로젝트 구조 예시
```
my-rfs-project/
├── rfs.yaml              # RFS 프로젝트 설정
├── pyproject.toml        # Python 프로젝트 설정
├── src/
│   └── main.py
├── tests/
└── requirements.txt
```

### 2. 환경별 실행

```bash
# 개발 환경에서 실행
RFS_ENV=development rfs status

# 프로덕션 환경에서 실행
RFS_ENV=production rfs status

# 디버그 모드 활성화
RFS_DEBUG=true rfs version
```

### 3. 출력 형식 제어

```bash
# Rich UI 사용 (기본값, rich가 설치된 경우)
rfs status

# 플레인 텍스트 출력 (rich가 없거나 비활성화)
RFS_NO_RICH=true rfs status

# JSON 출력 (향후 버전)
rfs status --format json
```

## 성능 및 최적화

### CLI 성능 지표

| 메트릭 | 목표 | 실제 성과 |
|-------|------|----------|
| 시작 시간 | <100ms | ~50ms |
| 메모리 사용량 | <50MB | ~25MB |
| 명령어 응답 시간 | <200ms | ~100ms |
| 의존성 체크 시간 | <500ms | ~200ms |

### 최적화 기법

1. **지연 임포트**: 필요한 모듈만 동적으로 로드
2. **캐싱**: 반복적인 검사 결과 캐싱
3. **병렬 처리**: 의존성 체크를 병렬로 수행
4. **메모리 관리**: 사용 후 즉시 리소스 해제

## 문제 해결

### 일반적인 문제

#### 1. Python 버전 호환성
```bash
❌ RFS Framework requires Python 3.10 or higher
Current version: Python 3.9

해결방법:
- pyenv install 3.11.0
- pyenv global 3.11.0
- python3 --version  # 확인
```

#### 2. 의존성 설치 실패
```bash
❌ pydantic (>=2.5.0)

해결방법:
- pip install --upgrade pip
- pip install pydantic>=2.5.0
- pip install rfs-framework[all]
```

#### 3. Rich UI 관련 문제
```bash
# Rich가 설치되지 않은 경우
pip install rich>=13.7.0

# 터미널 호환성 문제
export TERM=xterm-256color
```

#### 4. 권한 문제
```bash
# 사용자 설치
pip install --user rfs-framework

# 가상환경 사용
python3 -m venv rfs-env
source rfs-env/bin/activate
pip install rfs-framework
```

### 디버깅 모드

```bash
# 상세한 오류 정보
RFS_DEBUG=true rfs status

# 스택 트레이스 포함
RFS_VERBOSE=true rfs version

# 로그 레벨 설정
RFS_LOG_LEVEL=DEBUG rfs help
```

## 확장 및 커스터마이징

### 1. 설정 파일 (rfs.yaml)

```yaml
# rfs.yaml
rfs:
  version: "4.3.0"
  environment: "development"
  
cli:
  default_format: "rich"  # rich | plain | json
  show_dependencies: true
  show_performance_metrics: false
  
features:
  enable_all: true
  experimental: false
```

### 2. 환경 변수 설정

```bash
# ~/.bashrc 또는 ~/.zshrc
export RFS_ENV=development
export RFS_CLI_FORMAT=rich
export RFS_PROJECT_ROOT=/path/to/project
```

### 3. 별칭 (Aliases) 설정

```bash
# 자주 사용하는 명령어 별칭
alias rfv="rfs version"
alias rfs="rfs status"
alias rfc="rfs config"
alias rfh="rfs help"
```

## CI/CD 통합

### GitHub Actions

```yaml
name: RFS Framework Check
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    - name: Install RFS Framework
      run: pip install rfs-framework[all]
    - name: Check Framework Status
      run: |
        rfs version
        rfs status
        rfs config
```

### Docker 통합

```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder
RUN pip install rfs-framework[all]

FROM python:3.11-slim
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/rfs /usr/local/bin/rfs

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD rfs status || exit 1

CMD ["rfs", "status"]
```

## API 레퍼런스

### 명령어 구조
```
rfs [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]
```

### 전역 옵션
```bash
--version, -v      버전 정보 표시
--help, -h         도움말 표시
--verbose          상세 출력 (향후)
--format FORMAT    출력 형식 지정 (향후)
--no-color         색상 출력 비활성화 (향후)
```

### 명령어 목록
```bash
version            프레임워크 버전 및 기능 정보
status             시스템 상태 및 기능 모니터링
help               도움말 및 사용법
config             설정 정보 표시
```

### 종료 코드
```bash
0                  성공
1                  일반 오류
2                  잘못된 사용법
130                사용자 중단 (Ctrl+C)
```

## 베스트 프랙티스

### 1. 개발 워크플로우 통합

```bash
# 프로젝트 시작 전 상태 확인
rfs status

# 개발 중 주기적 점검
watch -n 30 rfs status

# 배포 전 최종 확인
rfs version && rfs status
```

### 2. 자동화 스크립트

```bash
#!/bin/bash
# check_rfs.sh - RFS 상태 자동 점검

echo "🔍 RFS Framework 상태 점검 시작..."

# 버전 확인
echo "📋 버전 정보:"
rfs version

# 시스템 상태 확인
echo "🔧 시스템 상태:"
rfs status

# 설정 확인
echo "⚙️ 설정 정보:"
rfs config

echo "✅ 상태 점검 완료!"
```

### 3. 모니터링 통합

```python
# monitoring.py - CLI 결과를 모니터링 시스템에 전송
import subprocess
import json

def check_rfs_status():
    result = subprocess.run(['rfs', 'status'], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        # 성공적으로 실행됨
        send_metric("rfs.status", "ok")
    else:
        # 오류 발생
        send_metric("rfs.status", "error")
        send_alert(f"RFS Status Check Failed: {result.stderr}")
```

이 문서는 RFS Framework CLI의 모든 기능과 사용법을 포괄적으로 다루고 있습니다. 추가적인 질문이나 특정 기능에 대한 세부사항이 필요하시면 언제든지 문의해 주세요.