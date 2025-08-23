# PyPI 정식 배포 안내

RFS Framework를 PyPI에 정식 배포하기 위한 단계별 안내입니다.

## ⚠️ 중요: PyPI 계정 설정이 필요합니다

현재 PyPI 인증 정보가 설정되어 있지 않습니다. 다음 단계를 따라 설정해주세요:

## 1단계: PyPI 계정 생성 및 API 토큰 발급

1. **PyPI 계정 생성**
   - https://pypi.org/account/register/ 에서 계정 생성
   - 이메일 인증 완료

2. **API 토큰 생성**
   - PyPI 로그인 후 계정 설정으로 이동
   - "API tokens" 섹션에서 "Add API token" 클릭
   - 토큰 이름: "rfs-framework-token"
   - Scope: "Entire account" 선택
   - 생성된 토큰 복사 (한 번만 표시됨!)

## 2단계: .pypirc 파일 생성

홈 디렉토리에 `.pypirc` 파일을 생성하세요:

```bash
nano ~/.pypirc
```

다음 내용을 입력하고 YOUR_API_TOKEN_HERE를 실제 토큰으로 교체:

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

파일 권한 설정:
```bash
chmod 600 ~/.pypirc
```

## 3단계: 배포 실행

### 옵션 1: 스크립트 사용 (권장)

```bash
# 패키지 빌드 및 배포
cd /Users/sangbongmoon/Workspace/rfs-framework
./scripts/publish.sh
```

### 옵션 2: 수동 배포

```bash
# 1. 이전 빌드 정리
rm -rf dist/ build/ *.egg-info src/*.egg-info

# 2. 패키지 빌드
python3 -m build

# 3. 패키지 검증
python3 -m twine check dist/*

# 4. PyPI 업로드
python3 -m twine upload dist/*
```

## 4단계: 배포 확인

```bash
# 잠시 기다린 후 설치 테스트
pip install rfs-framework

# 확인
python -c "import rfs; print(rfs.__version__)"
```

## 현재 패키지 상태

- **패키지명**: rfs-framework
- **버전**: 4.0.0
- **Python 요구사항**: >=3.10
- **빌드 상태**: ✅ 준비 완료
- **테스트 상태**: ✅ 모든 테스트 통과

## 주의사항

1. **패키지 이름 중복**: 'rfs-framework'가 이미 PyPI에 존재할 수 있습니다. 
   - 이 경우 다른 이름을 사용해야 합니다 (예: rfs-framework-v4, rfs-reactive 등)
   
2. **첫 배포**: 한 번 배포하면 같은 버전을 다시 업로드할 수 없습니다.
   - 수정이 필요하면 버전을 올려야 합니다 (예: 4.0.1)

3. **TestPyPI 먼저 테스트**: 정식 배포 전에 TestPyPI로 테스트하는 것을 권장합니다.

## 다음 단계

위의 1단계와 2단계를 완료한 후, 다시 알려주시면 배포를 진행하겠습니다.

또는 직접 3단계의 명령어를 실행하여 배포할 수 있습니다.