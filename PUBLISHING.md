# RFS Framework PyPI 배포 가이드

> **RFS Framework v4.3.0 PyPI 배포 완전 가이드**

## 📋 목차

1. [빠른 시작](#빠른-시작)
2. [PyPI 계정 설정](#pypi-계정-설정)
3. [패키지 빌드](#패키지-빌드)
4. [테스트 배포 (TestPyPI)](#테스트-배포-testpypi)
5. [정식 배포 (PyPI)](#정식-배포-pypi)
6. [배포 후 관리](#배포-후-관리)
7. [문제 해결](#문제-해결)

## 🚀 빠른 시작

### 첫 배포를 위한 준비

```bash
# 1. PyPI 계정 생성 (https://pypi.org)
# 2. API 토큰 생성 및 ~/.pypirc 설정

# 3. 빌드 도구 설치
pip install --upgrade build twine

# 4. 패키지 빌드 및 배포
./scripts/publish.sh --test  # TestPyPI로 테스트
./scripts/publish.sh          # PyPI로 정식 배포
```

## 🔧 PyPI 계정 설정

### 1. PyPI 계정 생성
1. [PyPI](https://pypi.org/account/register/)에서 계정 생성
2. 이메일 인증 완료

### 2. API 토큰 생성
1. PyPI 계정 설정 페이지로 이동
2. "API tokens" 섹션에서 "Add API token" 클릭
3. 토큰 이름 입력 (예: "rfs-framework-token")
4. Scope를 "Entire account" 또는 특정 프로젝트로 설정
5. 생성된 토큰을 안전한 곳에 저장 (한 번만 표시됨)

### 3. .pypirc 파일 설정
홈 디렉토리에 `.pypirc` 파일을 생성하고 다음 내용을 추가:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_API_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TEST_API_TOKEN_HERE
```

**⚠️ 보안 주의사항:**
- `.pypirc` 파일의 권한을 600으로 설정: `chmod 600 ~/.pypirc`
- 절대로 이 파일을 git에 커밋하지 마세요

## 📦 패키지 빌드

### 1. 필요한 도구 설치
```bash
pip install --upgrade pip
pip install --upgrade build twine
```

### 2. 패키지 빌드
```bash
# 프로젝트 루트 디렉토리에서 실행
python -m build
```

빌드가 완료되면 `dist/` 디렉토리에 다음 파일들이 생성됩니다:
- `rfs_framework-4.3.0-py3-none-any.whl` (wheel 파일)
- `rfs_framework-4.3.0.tar.gz` (소스 배포 파일)

### 3. 빌드 검증
```bash
# 패키지 메타데이터 검증
twine check dist/*

# 로컬 테스트 설치
pip install dist/rfs_framework-4.3.0-py3-none-any.whl

# 설치 확인
python -c "import rfs; print(rfs.__version__)"
```

## 🧪 테스트 배포 (TestPyPI)

### 1. TestPyPI 계정 생성
1. [TestPyPI](https://test.pypi.org/account/register/)에서 별도 계정 생성
2. API 토큰 생성 (PyPI와 동일한 방법)

### 2. TestPyPI에 업로드
```bash
twine upload --repository testpypi dist/*
```

### 3. TestPyPI에서 설치 테스트
```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps rfs-framework
```

## 🚀 정식 배포 (PyPI)

### 1. 최종 확인사항
- [ ] 버전 번호 확인 (`src/rfs/__init__.py`와 `pyproject.toml` 동기화)
- [ ] README.md 내용 확인 (PyPI에서 잘 표시되는지)
- [ ] 모든 테스트 통과
- [ ] 라이선스 파일 포함
- [ ] CHANGELOG.md 업데이트

### 2. PyPI에 업로드
```bash
twine upload dist/*
```

### 3. 배포 확인
```bash
# 새로운 가상환경에서 테스트
python -m venv test_env
source test_env/bin/activate  # Windows: test_env\Scripts\activate
pip install rfs-framework

# CLI 명령어 테스트
rfs --help

# Python import 테스트
python -c "from rfs import Result, Success, Failure; print('Success!')"
```

## 🔄 배포 후 관리

### 버전 업데이트 시

#### 1. 버전 번호 변경
1. `src/rfs/__init__.py`의 `__version__` 업데이트
2. `pyproject.toml`의 `version` 업데이트
3. `CHANGELOG.md`에 변경사항 기록

#### 2. 이전 빌드 제거
```bash
rm -rf dist/ build/ *.egg-info
```

#### 3. 새 버전 빌드 및 배포
```bash
python -m build
twine check dist/*
twine upload dist/*
```

### 자동화 스크립트 사용
```bash
chmod +x scripts/publish.sh
./scripts/publish.sh  # 정식 배포
./scripts/publish.sh --test  # 테스트 배포
```

### GitHub Actions 자동 배포
태그를 푸시하면 자동으로 PyPI에 배포:

```bash
git tag v4.3.0
git push origin v4.3.0
```

## 🔧 문제 해결

### 자주 발생하는 문제들

#### 인증 실패
- API 토큰이 올바른지 확인
- 토큰 앞에 `pypi-` 접두사가 있는지 확인
- username이 `__token__`인지 확인

#### 패키지 이름 충돌
- PyPI에서 이미 사용 중인 이름인지 확인
- 다른 이름 사용 고려

#### 메타데이터 오류
- `pyproject.toml`의 필수 필드 확인
- 이메일 주소와 URL 형식 확인

### 패키지 제거 (주의 필요)

**⚠️ 경고**: PyPI에서 패키지를 제거하면 복구할 수 없습니다.

```bash
# yank 명령으로 특정 버전을 숨김 처리
# (완전 삭제가 아닌 새 설치 방지)
twine upload --repository pypi --skip-existing dist/*
```

## 📚 유용한 링크

- [PyPI 공식 문서](https://packaging.python.org/tutorials/packaging-projects/)
- [Twine 문서](https://twine.readthedocs.io/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [RFS Framework PyPI 페이지](https://pypi.org/project/rfs-framework/)

---

**RFS Framework v4.3.0** - Enterprise-Grade Reactive Functional Serverless Framework
git commit -m "Release v4.0.1"
git tag v4.0.1
git push origin main --tags

# 4. GitHub Actions가 자동으로 배포 진행
```

## 배포 전 체크리스트

- [ ] 모든 테스트 통과 확인
- [ ] 버전 번호 동기화 (pyproject.toml, __init__.py)
- [ ] CHANGELOG.md 업데이트
- [ ] README.md 검토
- [ ] 의존성 버전 확인
- [ ] 라이선스 파일 확인

## 배포 방법

### 방법 1: 수동 배포 (스크립트 사용)

```bash
# TestPyPI로 테스트 배포
./scripts/publish.sh --test

# 테스트 설치
pip install --index-url https://test.pypi.org/simple/ --no-deps rfs-framework

# PyPI로 정식 배포
./scripts/publish.sh
```

### 방법 2: GitHub Actions 자동 배포

태그를 푸시하면 자동으로 배포됩니다:

```bash
# 정식 버전 배포 (v로 시작하는 태그)
git tag v4.0.1
git push origin v4.0.1

# 프리릴리즈 배포 (rc 포함 시 TestPyPI로)
git tag v4.0.1rc1
git push origin v4.0.1rc1
```

### 방법 3: 수동 빌드 및 배포

```bash
# 이전 빌드 정리
rm -rf dist/ build/ *.egg-info

# 패키지 빌드
python -m build

# 빌드 검증
twine check dist/*

# PyPI 업로드
twine upload dist/*
```

## GitHub Secrets 설정

GitHub Actions 자동 배포를 위해 다음 Secrets를 설정해야 합니다:

1. GitHub 저장소 → Settings → Secrets and variables → Actions
2. 다음 Secrets 추가:
   - `PYPI_API_TOKEN`: PyPI API 토큰
   - `TEST_PYPI_API_TOKEN`: TestPyPI API 토큰

## 배포 후 확인

### PyPI에서 확인

```bash
# 패키지 설치
pip install rfs-framework

# 버전 확인
python -c "import rfs; print(rfs.__version__)"

# CLI 명령어 확인
rfs-cli --help
```

### 패키지 페이지 확인

- PyPI: https://pypi.org/project/rfs-framework/
- TestPyPI: https://test.pypi.org/project/rfs-framework/

## 버전 관리 정책

### 버전 번호 체계

Semantic Versioning (SemVer) 사용:
- **MAJOR.MINOR.PATCH** (예: 4.0.1)
- **MAJOR**: 호환되지 않는 API 변경
- **MINOR**: 하위 호환 기능 추가
- **PATCH**: 하위 호환 버그 수정

### 프리릴리즈 버전

- **Alpha**: 4.1.0a1 (초기 개발)
- **Beta**: 4.1.0b1 (기능 완성, 버그 수정 중)
- **Release Candidate**: 4.1.0rc1 (최종 테스트)

## 문제 해결

### 일반적인 문제

#### 1. 인증 실패

```bash
# ~/.pypirc 파일 확인
cat ~/.pypirc

# 권한 설정
chmod 600 ~/.pypirc
```

#### 2. 패키지 이름 충돌

- PyPI에서 이름 사용 가능 여부 확인
- 필요시 패키지 이름 변경 (pyproject.toml)

#### 3. 메타데이터 오류

```bash
# 메타데이터 검증
twine check dist/*

# pyproject.toml 린트
pip install validate-pyproject
validate-pyproject pyproject.toml
```

#### 4. 빌드 실패

```bash
# 빌드 도구 업데이트
pip install --upgrade pip setuptools wheel build

# 클린 빌드
rm -rf dist/ build/ *.egg-info
python -m build
```

## 롤백 절차

문제 발생 시 이전 버전으로 롤백:

```bash
# PyPI에서는 삭제된 버전을 재업로드할 수 없음
# 새로운 패치 버전으로 수정사항 배포

# 예: 4.0.1에 문제가 있는 경우
# 1. 문제 수정
# 2. 버전을 4.0.2로 업데이트
# 3. 재배포
```

## 유용한 명령어

```bash
# 현재 설치된 버전 확인
pip show rfs-framework

# 특정 버전 설치
pip install rfs-framework==4.0.0

# 최신 버전으로 업그레이드
pip install --upgrade rfs-framework

# 개발 모드 설치
pip install -e .

# 의존성 트리 확인
pip install pipdeptree
pipdeptree -p rfs-framework
```

## 연락처 및 지원

- 이슈 리포트: https://github.com/rfs-framework/rfs-python/issues
- 이메일: team@rfs-framework.dev
- 문서: https://docs.rfs-framework.dev