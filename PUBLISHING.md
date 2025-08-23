# RFS Framework 배포 문서

## 빠른 시작 가이드

### 1. 첫 배포를 위한 준비

```bash
# 1. PyPI 계정 생성 (https://pypi.org)
# 2. API 토큰 생성 및 ~/.pypirc 설정 (PYPI_SETUP.md 참조)

# 3. 빌드 도구 설치
pip install --upgrade build twine

# 4. 패키지 빌드 및 배포
./scripts/publish.sh --test  # TestPyPI로 테스트
./scripts/publish.sh          # PyPI로 정식 배포
```

### 2. 버전 업데이트 및 재배포

```bash
# 1. 버전 번호 업데이트
# src/rfs/__init__.py의 __version__ 수정
# pyproject.toml의 version 수정

# 2. 변경사항 기록
# CHANGELOG.md 업데이트

# 3. 커밋 및 태그
git add .
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