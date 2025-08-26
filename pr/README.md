# RFS Framework 버그 리포트 및 개선 제안

이 폴더는 RFS Framework에서 발견된 버그와 개선사항을 정리하여 Pull Request로 제출하기 위한 문서들을 포함합니다.

## 🐛 발견된 이슈

### 1. `NameError: name 'field' is not defined` 버그
- **파일**: `rfs/core/config.py:97`
- **심각도**: Critical
- **상세**: [ISSUE-001-field-import-error.md](./ISSUE-001-field-import-error.md)

## 🚀 제안된 개선사항

### 1. Import 구문 표준화
- **상세**: [IMPROVEMENT-001-import-standardization.md](./IMPROVEMENT-001-import-standardization.md)

### 2. 타입 힌트 개선
- **상세**: [IMPROVEMENT-002-type-hints.md](./IMPROVEMENT-002-type-hints.md)

## 📋 PR 제출 순서

1. **버그 수정** (우선순위 높음)
   - ISSUE-001: field import 오류 수정

2. **개선사항** (우선순위 중간)
   - IMPROVEMENT-001: Import 표준화
   - IMPROVEMENT-002: 타입 힌트 개선

## 🧪 테스트 케이스

각 이슈별 테스트 케이스는 `tests/` 폴더에 포함되어 있습니다.

## 📝 PR 템플릿

```markdown
## 변경사항
- [x] 버그 수정: field import 오류
- [ ] 개선: Import 표준화
- [ ] 개선: 타입 힌트

## 테스트
- [x] 기존 테스트 통과
- [x] 새로운 테스트 추가

## 체크리스트
- [x] 코드 리뷰 완료
- [x] 문서 업데이트
- [x] 테스트 케이스 추가
```