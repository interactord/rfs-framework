# RFS Framework 설치 가이드

## 📦 PyPI 패키지 정보

**최신 버전**: 4.0.0 (PyPI 등록)  
**프로젝트 버전**: 4.3.0 (소스 코드)

> ⚠️ **주의**: PyPI에 등록된 버전(4.0.0)과 현재 소스 코드 버전(4.3.0)이 다릅니다.  
> 최신 기능을 사용하려면 GitHub에서 직접 설치하는 것을 권장합니다.

## 🚀 설치 방법

### 1. 기본 설치

```bash
# PyPI에서 설치 (v4.0.0)
pip install rfs-framework

# GitHub에서 최신 버전 설치 (v4.3.0)
pip install git+https://github.com/interactord/rfs-framework.git
```

### 2. 선택적 모듈 설치

RFS Framework는 다양한 용도에 맞춰 선택적으로 설치할 수 있는 6개의 추가 모듈을 제공합니다:

#### 📱 **[web]** - FastAPI 웹 프레임워크 지원 **(완료)**
```bash
pip install rfs-framework[web]
```
포함 패키지:
- `fastapi>=0.104.0` - 모던 웹 API 프레임워크
- `uvicorn[standard]>=0.24.0` - ASGI 서버
- `gunicorn>=21.2.0` - 프로덕션 WSGI 서버

✅ **구현 상태**: 완전 구현됨
- Web server, middleware, routing 모듈 구현
- FastAPI/Flask 듀얼 지원

#### 💾 **[database]** - 데이터베이스 지원 **(완료)**
```bash
pip install rfs-framework[database]
```
포함 패키지:
- `sqlalchemy>=2.0.23` - SQL 툴킷 및 ORM
- `alembic>=1.13.0` - 데이터베이스 마이그레이션
- `asyncpg>=0.29.0` - PostgreSQL 비동기 드라이버
- `aiosqlite>=0.19.0` - SQLite 비동기 드라이버
- `redis>=5.0.1` - Redis 클라이언트

✅ **구현 상태**: 완전 구현됨
- Database models, session, migration 모듈 구현
- Redis cache, distributed cache 구현
- 36개 파일에서 활용 중

#### 🧪 **[test]** - 테스팅 프레임워크 **(완료)**
```bash
pip install rfs-framework[test]
```
포함 패키지:
- `pytest>=7.4.0` - 테스트 프레임워크
- `pytest-asyncio>=0.21.0` - 비동기 테스트 지원
- `pytest-cov>=4.1.0` - 코드 커버리지
- `pytest-mock>=3.12.0` - Mock 지원
- `httpx>=0.25.0` - FastAPI 테스트용
- `faker>=20.1.0` - 테스트 데이터 생성

✅ **구현 상태**: 완전 구현됨
- 25개 테스트 파일 작성
- Unit, Integration 테스트 구조 완성
- conftest.py 설정 완료

#### 🛠️ **[dev]** - 개발 도구 **(완료)**
```bash
pip install rfs-framework[dev]
```
포함 패키지:
- `black>=23.11.0` - 코드 포매터
- `isort>=5.12.0` - import 정렬
- `flake8>=6.1.0` - 린터
- `mypy>=1.7.0` - 타입 체커
- `pre-commit>=3.6.0` - Git 훅
- `bandit>=1.7.5` - 보안 린팅

✅ **구현 상태**: 설정 파일만 필요
- pyproject.toml에 설정 포함
- 개발 도구는 별도 구현 불필요

#### 📚 **[docs]** - 문서화 도구 **(TBD)**
```bash
pip install rfs-framework[docs]
```
포함 패키지:
- `mkdocs>=1.5.3` - 문서 생성기
- `mkdocs-material>=9.4.0` - Material 테마
- `mkdocstrings[python]>=0.24.0` - Python docstring 파서
- `mkdocs-mermaid2-plugin>=1.1.1` - 다이어그램 지원

⚠️ **구현 상태**: 부분 구현
- mkdocs.yml 설정 파일 없음
- API 문서는 있으나 MkDocs 통합 미완성
- Wiki 문서는 완성 (17개 모듈)

#### 🤖 **[ai]** - AI/ML 통합 **(TBD)**
```bash
pip install rfs-framework[ai]
```
포함 패키지:
- `openai>=1.3.0` - OpenAI API 클라이언트
- `anthropic>=0.7.0` - Anthropic API 클라이언트
- `transformers>=4.35.0` - Hugging Face Transformers

⚠️ **구현 상태**: 미구현
- AI 통합 모듈 없음
- 2개 파일에서 언급만 있음
- 실제 AI 기능 구현 필요

### 3. 전체 설치

#### **[all]** - 모든 선택적 모듈 포함
```bash
pip install rfs-framework[all]
```
위의 6개 모듈(`web`, `database`, `test`, `dev`, `docs`, `ai`)을 모두 포함합니다.

## 🎯 사용 목적별 권장 설치

### 웹 API 개발
```bash
pip install rfs-framework[web,database,test]
```

### 데이터 처리 애플리케이션
```bash
pip install rfs-framework[database,test]
```

### 오픈소스 기여자
```bash
pip install rfs-framework[dev,test,docs]
```

### 풀스택 개발
```bash
pip install rfs-framework[all]
```

### 최소 설치 (코어 기능만)
```bash
pip install rfs-framework
```

## 🔧 개발 환경 설정

### 로컬 개발 환경
```bash
# 저장소 클론
git clone https://github.com/interactord/rfs-framework.git
cd rfs-framework

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 개발 모드로 설치 (editable install)
pip install -e .

# 개발 도구 포함 설치
pip install -e ".[dev,test]"

# 모든 기능 포함 개발 설치
pip install -e ".[all]"
```

## 📊 설치 확인

```bash
# 패키지 설치 확인
pip show rfs-framework

# 버전 확인
python -c "import rfs; print(rfs.__version__)"

# CLI 도구 확인
rfs --version
rfs status
```

## ⚠️ 주의사항

1. **Python 버전**: Python 3.10 이상 필요
2. **가상환경 사용 권장**: 의존성 충돌 방지
3. **PyPI vs GitHub**: 
   - PyPI (v4.0.0): 안정 버전
   - GitHub (v4.3.0): 최신 기능 포함

## 🆘 문제 해결

### 설치 오류 발생 시

```bash
# pip 업그레이드
pip install --upgrade pip

# 캐시 삭제 후 재설치
pip cache purge
pip install rfs-framework --no-cache-dir

# 특정 버전 설치
pip install rfs-framework==4.0.0
```

### 의존성 충돌 시

```bash
# 의존성 확인
pip check

# 충돌하는 패키지 제거 후 재설치
pip uninstall conflicting-package
pip install rfs-framework
```

## 📚 추가 정보

- [프로젝트 홈페이지](https://github.com/interactord/rfs-framework)
- [PyPI 패키지 페이지](https://pypi.org/project/rfs-framework/)
- [문제 보고](https://github.com/interactord/rfs-framework/issues)