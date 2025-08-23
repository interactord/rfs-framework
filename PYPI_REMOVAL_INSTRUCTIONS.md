# PyPI Package 삭제 및 이전 가이드

## 현재 상황

PyPI에 두 개의 패키지가 존재합니다:
- `rfs-v4` (4.0.0, 4.0.1) - 삭제 예정
- `rfs-framework` (새로운 공식 패키지명)

## rfs-v4 패키지 삭제 방법

### 방법 1: PyPI 웹 인터페이스 사용 (권장)

1. **PyPI 로그인**
   - https://pypi.org/account/login/ 접속
   - 계정 로그인

2. **패키지 관리 페이지 접속**
   - https://pypi.org/manage/project/rfs-v4/
   - 또는 Your projects → rfs-v4 선택

3. **릴리스 삭제**
   - "Releases" 탭 클릭
   - 각 버전(4.0.0, 4.0.1)에서 "Delete" 클릭
   - 삭제 확인

4. **패키지 완전 삭제 (선택사항)**
   - "Settings" 탭
   - "Delete project" 섹션
   - 프로젝트명 입력 후 삭제

### 방법 2: twine 명령어 사용

```bash
# 특정 버전 삭제
twine delete rfs-v4/4.0.0
twine delete rfs-v4/4.0.1

# 인증 정보 필요
# - PyPI 사용자명/비밀번호
# - 또는 API 토큰
```

### 방법 3: pip 명령어 (yanked 처리)

패키지를 완전히 삭제하는 대신 "yanked" 처리하여 새로운 설치를 방지:

```bash
# PyPI 웹 인터페이스에서
# 각 릴리스 페이지에서 "Yank" 버튼 클릭
```

Yanked 패키지는:
- 이미 설치된 곳에서는 계속 작동
- 새로운 설치는 불가능
- pip install rfs-v4 실행 시 경고 표시

## 사용자 마이그레이션 안내

### 기존 rfs-v4 사용자를 위한 안내

```bash
# 1. 기존 패키지 제거
pip uninstall rfs-v4

# 2. 새 패키지 설치
pip install rfs-framework

# 3. 코드에서 import 변경 불필요 (동일한 모듈명 사용)
from rfs import Result, Flux, Mono  # 그대로 사용 가능
```

### requirements.txt 업데이트

```diff
- rfs-v4>=4.0.0
+ rfs-framework>=4.0.2
```

### pyproject.toml 업데이트

```diff
dependencies = [
-    "rfs-v4>=4.0.0",
+    "rfs-framework>=4.0.2",
]
```

## 권장 삭제 절차

1. **경고 기간 설정** (권장: 1-2주)
   - rfs-v4 패키지에 deprecation 경고 추가
   - README 업데이트하여 이전 안내

2. **Yank 처리** (권장)
   - 기존 사용자 영향 최소화
   - 새 설치만 차단

3. **완전 삭제** (선택사항)
   - 충분한 시간 후 (예: 1개월)
   - 모든 사용자가 이전 완료 확인 후

## 체크리스트

- [ ] PyPI 로그인 정보 확인
- [ ] rfs-v4 패키지 백업 (필요시)
- [ ] 사용자 공지 (GitHub, 이메일 등)
- [ ] rfs-framework 패키지 정상 작동 확인
- [ ] rfs-v4 패키지 Yank 또는 삭제
- [ ] 문서 업데이트 완료
- [ ] Context7 등록 업데이트

## 주의사항

⚠️ **경고**: 패키지 삭제는 되돌릴 수 없습니다.
⚠️ **권장**: Yank 처리를 먼저 시도하고, 완전 삭제는 나중에 고려하세요.
⚠️ **중요**: 기존 사용자에게 충분한 이전 시간을 제공하세요.

## 문제 해결

### 삭제 권한이 없는 경우
- 패키지 소유자 확인
- PyPI 지원팀 문의: https://pypi.org/help/

### 실수로 삭제한 경우
- 동일한 버전 번호로 재업로드 불가
- 새 버전 번호로 재업로드 필요

## 다음 단계

1. **rfs-framework 패키지 홍보**
   - README 업데이트 ✅
   - GitHub 저장소 업데이트 ✅
   - 문서 업데이트 ✅

2. **PyPI에서 rfs-v4 처리**
   - Yank 처리 (권장) ⏳
   - 또는 완전 삭제 ⏳

3. **Context7 등록**
   - rfs-framework로 등록 ⏳
   - 문서 검증 ⏳

---

*마지막 업데이트: 2024년 1월*