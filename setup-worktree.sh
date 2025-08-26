#!/bin/bash
# RFS Framework - Worktree 환경 설정 스크립트

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 현재 디렉토리 확인
CURRENT_DIR=$(basename "$PWD")

echo -e "${BLUE}=== RFS Framework Worktree Setup ===${NC}"
echo -e "${YELLOW}현재 디렉토리: $CURRENT_DIR${NC}"

# Python 가상환경 생성
if [ ! -d "venv" ]; then
    echo -e "${GREEN}1. Python 가상환경 생성 중...${NC}"
    python3 -m venv venv
else
    echo -e "${YELLOW}가상환경이 이미 존재합니다.${NC}"
fi

# 가상환경 활성화
echo -e "${GREEN}2. 가상환경 활성화 중...${NC}"
source venv/bin/activate

# pip 업그레이드
echo -e "${GREEN}3. pip 업그레이드 중...${NC}"
pip install --upgrade pip setuptools wheel

# 테스트 패키지 설치
echo -e "${GREEN}4. 테스트 패키지 설치 중...${NC}"
if [ -f "requirements-test-minimal.txt" ]; then
    pip install -r requirements-test-minimal.txt
else
    # 상위 디렉토리에서 복사
    cp ../requirements-test-minimal.txt . 2>/dev/null || cp ../rfs-framework/requirements-test-minimal.txt . 2>/dev/null
    pip install -r requirements-test-minimal.txt
fi

# RFS 패키지 개발 모드로 설치
echo -e "${GREEN}5. RFS Framework 개발 모드 설치 중...${NC}"
pip install -e .

# 워크트리별 특정 설정
case "$CURRENT_DIR" in
    *async-tests*)
        echo -e "${BLUE}=== Async Tasks 테스트 환경 설정 완료 ===${NC}"
        echo "다음 명령으로 테스트를 실행하세요:"
        echo "pytest tests/unit/async_tasks/ -v --cov=rfs.async_tasks"
        ;;
    *database-tests*)
        echo -e "${BLUE}=== Database 테스트 환경 설정 완료 ===${NC}"
        echo "다음 명령으로 테스트를 실행하세요:"
        echo "pytest tests/unit/database/ -v --cov=rfs.database"
        ;;
    *analytics-tests*)
        echo -e "${BLUE}=== Analytics 테스트 환경 설정 완료 ===${NC}"
        echo "다음 명령으로 테스트를 실행하세요:"
        echo "pytest tests/unit/analytics/ -v --cov=rfs.analytics"
        ;;
    *)
        echo -e "${BLUE}=== 테스트 환경 설정 완료 ===${NC}"
        echo "다음 명령으로 전체 테스트를 실행하세요:"
        echo "pytest tests/ -v --cov=rfs"
        ;;
esac

echo -e "${GREEN}✅ 설정 완료!${NC}"
echo -e "${YELLOW}가상환경 활성화: source venv/bin/activate${NC}"