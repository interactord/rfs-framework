#!/bin/bash

# RFS Framework PyPI 배포 스크립트
# 사용법: ./scripts/publish.sh [--test]

set -e  # 오류 발생 시 즉시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 함수: 메시지 출력
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 함수: 종속성 확인
check_dependencies() {
    log_info "필수 도구 확인 중..."
    
    if ! command -v python &> /dev/null; then
        log_error "Python이 설치되어 있지 않습니다."
        exit 1
    fi
    
    if ! command -v pip &> /dev/null; then
        log_error "pip가 설치되어 있지 않습니다."
        exit 1
    fi
    
    log_info "필수 패키지 설치 중..."
    pip install --upgrade pip build twine
}

# 함수: 이전 빌드 정리
clean_build() {
    log_info "이전 빌드 파일 정리 중..."
    rm -rf dist/ build/ *.egg-info src/*.egg-info
    log_info "정리 완료"
}

# 함수: 버전 확인
check_version() {
    log_info "버전 정보 확인 중..."
    
    # pyproject.toml에서 버전 추출
    PYPROJECT_VERSION=$(grep "^version" pyproject.toml | cut -d'"' -f2)
    
    # __init__.py에서 버전 추출
    INIT_VERSION=$(grep "__version__" src/rfs/__init__.py | cut -d'"' -f2)
    
    log_info "pyproject.toml 버전: $PYPROJECT_VERSION"
    log_info "__init__.py 버전: $INIT_VERSION"
    
    if [ "$PYPROJECT_VERSION" != "$INIT_VERSION" ]; then
        log_error "버전이 일치하지 않습니다!"
        log_error "pyproject.toml과 src/rfs/__init__.py의 버전을 동기화하세요."
        exit 1
    fi
    
    VERSION=$PYPROJECT_VERSION
}

# 함수: 패키지 빌드
build_package() {
    log_info "패키지 빌드 중..."
    python -m build
    
    if [ $? -eq 0 ]; then
        log_info "빌드 성공!"
        ls -la dist/
    else
        log_error "빌드 실패!"
        exit 1
    fi
}

# 함수: 패키지 검증
validate_package() {
    log_info "패키지 검증 중..."
    twine check dist/*
    
    if [ $? -eq 0 ]; then
        log_info "패키지 검증 성공!"
    else
        log_error "패키지 검증 실패!"
        exit 1
    fi
}

# 함수: TestPyPI에 업로드
upload_test() {
    log_info "TestPyPI에 업로드 중..."
    
    if [ ! -f ~/.pypirc ]; then
        log_error "~/.pypirc 파일이 없습니다. PYPI_SETUP.md를 참고하여 설정하세요."
        exit 1
    fi
    
    twine upload --repository testpypi dist/*
    
    if [ $? -eq 0 ]; then
        log_info "TestPyPI 업로드 성공!"
        log_info "다음 명령어로 테스트할 수 있습니다:"
        echo "pip install --index-url https://test.pypi.org/simple/ --no-deps rfs-framework"
    else
        log_error "TestPyPI 업로드 실패!"
        exit 1
    fi
}

# 함수: PyPI에 업로드
upload_pypi() {
    log_info "PyPI에 업로드 중..."
    
    if [ ! -f ~/.pypirc ]; then
        log_error "~/.pypirc 파일이 없습니다. PYPI_SETUP.md를 참고하여 설정하세요."
        exit 1
    fi
    
    # 최종 확인
    echo -e "${YELLOW}정말로 PyPI에 배포하시겠습니까? (버전: $VERSION)${NC}"
    read -p "계속하려면 'yes'를 입력하세요: " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_warning "배포가 취소되었습니다."
        exit 0
    fi
    
    twine upload dist/*
    
    if [ $? -eq 0 ]; then
        log_info "PyPI 업로드 성공!"
        log_info "다음 명령어로 설치할 수 있습니다:"
        echo "pip install rfs-framework"
        log_info "PyPI 페이지: https://pypi.org/project/rfs-framework/"
    else
        log_error "PyPI 업로드 실패!"
        exit 1
    fi
}

# 메인 실행
main() {
    echo "========================================="
    echo "   RFS Framework PyPI 배포 스크립트"
    echo "========================================="
    echo ""
    
    # 종속성 확인
    check_dependencies
    
    # 이전 빌드 정리
    clean_build
    
    # 버전 확인
    check_version
    
    # 패키지 빌드
    build_package
    
    # 패키지 검증
    validate_package
    
    # 업로드 대상 결정
    if [ "$1" == "--test" ]; then
        upload_test
    else
        log_info "프로덕션 PyPI 배포 모드"
        upload_pypi
    fi
    
    log_info "배포 프로세스 완료!"
}

# 스크립트 실행
main "$@"