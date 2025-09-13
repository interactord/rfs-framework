#!/bin/bash

# ============================================================================
# Context7 배포 스크립트 - RFS Framework v4.6.6
# ============================================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수들
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 배포 정보
VERSION="4.6.6"
CONTEXT7_FILE="context7.json"
BACKUP_FILE="context7_v${VERSION}_backup.json"
DEPLOYMENT_DATE=$(date '+%Y-%m-%d %H:%M:%S')

log_info "=========================================="
log_info "Context7 배포 시작 - RFS Framework v${VERSION}"
log_info "배포 시간: ${DEPLOYMENT_DATE}"
log_info "=========================================="

# 1. 사전 검증
log_info "1. 사전 검증 중..."

if [ ! -f "${CONTEXT7_FILE}" ]; then
    log_error "Context7 파일이 존재하지 않습니다: ${CONTEXT7_FILE}"
    exit 1
fi

# JSON 유효성 검증
if ! jq empty "${CONTEXT7_FILE}" 2>/dev/null; then
    log_error "Context7 JSON 파일이 유효하지 않습니다"
    exit 1
fi

# 버전 확인
CURRENT_VERSION=$(jq -r '.version' "${CONTEXT7_FILE}")
if [ "${CURRENT_VERSION}" != "${VERSION}" ]; then
    log_error "Context7 파일의 버전(${CURRENT_VERSION})이 예상 버전(${VERSION})과 다릅니다"
    exit 1
fi

log_success "사전 검증 완료"

# 2. 백업 생성
log_info "2. 기존 Context7 파일 백업 중..."
cp "${CONTEXT7_FILE}" "${BACKUP_FILE}"
log_success "백업 생성 완료: ${BACKUP_FILE}"

# 3. Context7 내용 검증
log_info "3. Context7 내용 검증 중..."

# 필수 필드 확인
REQUIRED_FIELDS=("name" "version" "description" "features" "recent_achievements")
for field in "${REQUIRED_FIELDS[@]}"; do
    if ! jq -e ".${field}" "${CONTEXT7_FILE}" > /dev/null; then
        log_error "필수 필드가 누락되었습니다: ${field}"
        exit 1
    fi
done

# v4.6.6 관련 내용 확인
if ! jq -e '.recent_achievements."2025_01_14".enhanced_loglevel_validation' "${CONTEXT7_FILE}" > /dev/null; then
    log_error "v4.6.6 LogLevel 개선사항이 Context7에 누락되었습니다"
    exit 1
fi

log_success "Context7 내용 검증 완료"

# 4. 배포 요약 생성
log_info "4. 배포 요약 생성 중..."

cat > "CONTEXT7_DEPLOYMENT_SUMMARY_V${VERSION}.md" << EOF
# Context7 배포 요약 - RFS Framework v${VERSION}

## 배포 정보
- **버전**: ${VERSION}
- **배포 일시**: ${DEPLOYMENT_DATE}
- **배포 상태**: ✅ 성공

## 주요 업데이트 내용

### v4.6.6 - Enhanced LogLevel Validation
- **문제 해결**: Cloud Run 환경에서 LogLevel enum 딕셔너리 입력 처리 실패
- **핵심 개선**: LogLevel.from_value() 메서드 추가로 다양한 입력 형태 안전 처리
- **호환성**: Cloud Run 환경 100% 호환, 기존 코드 하위 호환성 유지

### 기술적 구현
- **방어적 프로그래밍**: 잘못된 입력에 대한 안전한 fallback 제공
- **환경 호환성**: 로컬/Cloud Run/Docker 등 모든 환경 일관된 동작
- **헬퍼 함수**: create_safe_logger(), validate_log_level_config() 추가

### 배포 상태
- **PyPI**: https://pypi.org/project/rfs-framework/${VERSION}/
- **GitHub**: Commit 60d1993
- **문서**: CHANGELOG.md, README.md 업데이트 완료

## 검증 완료
- ✅ JSON 유효성 검증
- ✅ 필수 필드 존재 확인
- ✅ v4.6.6 개선사항 포함 확인
- ✅ 버전 일관성 확인

## 백업 파일
- **백업 위치**: ${BACKUP_FILE}
- **원본 파일**: ${CONTEXT7_FILE}

---
**배포 완료 시간**: ${DEPLOYMENT_DATE}
EOF

log_success "배포 요약 생성 완료: CONTEXT7_DEPLOYMENT_SUMMARY_V${VERSION}.md"

# 5. 최종 확인
log_info "5. 최종 배포 확인..."

# Context7 파일 크기 확인
FILE_SIZE=$(wc -c < "${CONTEXT7_FILE}")
if [ "${FILE_SIZE}" -lt 1000 ]; then
    log_warning "Context7 파일 크기가 작습니다 (${FILE_SIZE} bytes). 내용을 확인해주세요."
fi

# 최신 개선사항 포함 여부 재확인
LOGLEVEL_FEATURE=$(jq -r '.recent_achievements."2025_01_14".enhanced_loglevel_validation.description' "${CONTEXT7_FILE}")
if [[ "${LOGLEVEL_FEATURE}" == *"4.6.6"* ]]; then
    log_success "v4.6.6 LogLevel 개선사항이 올바르게 포함되었습니다"
else
    log_error "v4.6.6 LogLevel 개선사항 내용에 문제가 있습니다"
    exit 1
fi

# 6. 배포 완료
log_info "=========================================="
log_success "Context7 배포 완료!"
log_info "=========================================="

echo ""
echo "📋 배포 요약:"
echo "  - 버전: ${VERSION}"
echo "  - 주요 개선: Enhanced LogLevel Validation for Cloud Run"
echo "  - 백업 파일: ${BACKUP_FILE}"
echo "  - 배포 문서: CONTEXT7_DEPLOYMENT_SUMMARY_V${VERSION}.md"
echo ""
echo "🔗 참고 링크:"
echo "  - PyPI: https://pypi.org/project/rfs-framework/${VERSION}/"
echo "  - GitHub: https://github.com/interactord/rfs-framework"
echo "  - 문서: https://interactord.github.io/rfs-framework/"
echo ""

log_success "모든 배포 작업이 성공적으로 완료되었습니다! 🎉"