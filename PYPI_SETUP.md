# PyPI 배포 가이드

RFS Framework를 PyPI에 배포하기 위한 단계별 가이드입니다.

## 1. PyPI 계정 설정

### 1.1 PyPI 계정 생성
1. [PyPI](https://pypi.org/account/register/)에서 계정 생성
2. 이메일 인증 완료

### 1.2 API 토큰 생성
1. PyPI 계정 설정 페이지로 이동
2. "API tokens" 섹션에서 "Add API token" 클릭
3. 토큰 이름 입력 (예: "rfs-framework-token")
4. Scope를 "Entire account" 또는 특정 프로젝트로 설정
5. 생성된 토큰을 안전한 곳에 저장 (한 번만 표시됨)

### 1.3 .pypirc 파일 설정
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

**보안 주의사항:**
- `.pypirc` 파일의 권한을 600으로 설정: `chmod 600 ~/.pypirc`
- 절대로 이 파일을 git에 커밋하지 마세요

## 2. 패키지 빌드

### 2.1 필요한 도구 설치
```bash
pip install --upgrade pip
pip install --upgrade build twine
```

### 2.2 패키지 빌드
```bash
# 프로젝트 루트 디렉토리에서 실행
python -m build
```

빌드가 완료되면 `dist/` 디렉토리에 다음 파일들이 생성됩니다:
- `rfs_framework-4.0.0-py3-none-any.whl` (wheel 파일)
- `rfs_framework-4.0.0.tar.gz` (소스 배포 파일)

### 2.3 빌드 검증
```bash
# 패키지 메타데이터 검증
twine check dist/*

# 로컬 테스트 설치
pip install dist/rfs_framework-4.0.0-py3-none-any.whl

# 설치 확인
python -c "import rfs; print(rfs.__version__)"
```

## 3. TestPyPI로 테스트 (권장)

### 3.1 TestPyPI 계정 생성
1. [TestPyPI](https://test.pypi.org/account/register/)에서 별도 계정 생성
2. API 토큰 생성 (PyPI와 동일한 방법)

### 3.2 TestPyPI에 업로드
```bash
twine upload --repository testpypi dist/*
```

### 3.3 TestPyPI에서 설치 테스트
```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps rfs-framework
```

## 4. PyPI 정식 배포

### 4.1 최종 확인사항
- [ ] 버전 번호 확인 (`src/rfs/__init__.py`와 `pyproject.toml` 동기화)
- [ ] README.md 내용 확인 (PyPI에서 잘 표시되는지)
- [ ] 모든 테스트 통과
- [ ] 라이선스 파일 포함
- [ ] CHANGELOG.md 업데이트

### 4.2 PyPI에 업로드
```bash
twine upload dist/*
```

### 4.3 배포 확인
```bash
# 새로운 가상환경에서 테스트
python -m venv test_env
source test_env/bin/activate  # Windows: test_env\Scripts\activate
pip install rfs-framework

# CLI 명령어 테스트
rfs-cli --help

# Python import 테스트
python -c "from rfs import Result, Success, Failure; print('Success!')"
```

## 5. 버전 업데이트 시

### 5.1 버전 번호 변경
1. `src/rfs/__init__.py`의 `__version__` 업데이트
2. `pyproject.toml`의 `version` 업데이트
3. `CHANGELOG.md`에 변경사항 기록

### 5.2 이전 빌드 제거
```bash
rm -rf dist/ build/ *.egg-info
```

### 5.3 새 버전 빌드 및 배포
```bash
python -m build
twine check dist/*
twine upload dist/*
```

## 6. 문제 해결

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

## 7. 자동화 스크립트

`scripts/publish.sh` 파일을 사용하여 배포 프로세스를 자동화할 수 있습니다:

```bash
chmod +x scripts/publish.sh
./scripts/publish.sh
```

## 8. GitHub Actions 자동 배포

GitHub에 태그를 푸시하면 자동으로 PyPI에 배포되도록 설정되어 있습니다:

```bash
git tag v4.0.1
git push origin v4.0.1
```

GitHub Actions가 자동으로:
1. 테스트 실행
2. 패키지 빌드
3. PyPI에 업로드

## 유용한 링크

- [PyPI 공식 문서](https://packaging.python.org/tutorials/packaging-projects/)
- [Twine 문서](https://twine.readthedocs.io/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [RFS Framework PyPI 페이지](https://pypi.org/project/rfs-framework/) (배포 후)