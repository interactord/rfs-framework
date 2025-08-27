# Git 커밋 메시지 작성 규칙

## 개요

RFS Framework 프로젝트의 Git 커밋 메시지는 한글로 작성하되, 깃헙 표준 커밋 스타일을 따릅니다. 명확하고 일관된 커밋 메시지를 통해 프로젝트 히스토리를 효과적으로 관리합니다.

## 커밋 타입

### 기본 타입
- **feat**: 새로운 기능 추가
- **fix**: 버그 수정
- **docs**: 문서 수정
- **style**: 코드 포맷팅, 세미콜론 누락 등 코드 변경이 없는 경우
- **refactor**: 코드 리팩토링
- **test**: 테스트 코드, 리팩토링 테스트 코드 추가
- **chore**: 빌드 업무 수정, 패키지 매니저 수정
- **perf**: 성능 개선

## 커밋 메시지 구조

```
<타입>: <제목>

[본문]

[꼬리말]
```

### 제목 작성 규칙
- **120자 이내**로 작성
- **한글**로 명확하고 간결하게 작성
- 마침표(.) 사용하지 않음
- 변경사항을 명확하게 설명

### 본문 작성 규칙
- 제목만으로 설명이 부족한 경우 작성
- **bullet point** (-)로 주요 변경사항 요약
- 각 변경사항은 명확하고 구체적으로 설명
- **무엇을** 변경했는지와 **왜** 변경했는지 설명
- 한 줄은 72자 이내로 작성

### 꼬리말
- 이슈 트래커 ID 참조 (예: `Resolves: #123`)
- Breaking Change가 있는 경우 명시
- 관련 이슈나 PR 참조

## 커밋 분리 원칙

### 논리적 단위로 분리
```bash
# ❌ 잘못된 예 - 여러 기능이 섞인 커밋
git commit -m "사용자 기능 추가, 버그 수정, 문서 업데이트"

# ✅ 좋은 예 - 기능별로 분리
git commit -m "feat: 사용자 인증 기능 추가"
git commit -m "fix: 로그인 세션 만료 버그 수정"
git commit -m "docs: API 문서 업데이트"
```

### 파일 범위별 분리
큰 변경사항은 모듈이나 레이어별로 분리:
```bash
# 도메인 레이어 변경
git add src/domain/*
git commit -m "refactor: 도메인 엔티티 불변성 적용"

# 애플리케이션 레이어 변경
git add src/application/*
git commit -m "feat: 사용자 생성 유스케이스 구현"
```

## 복합 타입 처리

여러 타입이 섞인 경우 처리 방법:

### 1. 커밋 분리 (권장)
```bash
# 문서와 기능이 섞인 경우 - 분리
git add src/services/user.py
git commit -m "feat: 사용자 프로필 조회 기능 추가"

git add docs/api.md
git commit -m "docs: 사용자 API 문서 업데이트"
```

### 2. 복합 타입 사용 (분리 어려운 경우)
```
fix,docs: 핵심 모듈의 문서화 번역 및 설정 오류 수정

docs: 문서화 문자열 한글 번역
- 설정 관리 (config.py) 문서화 한글 번역
- 의존성 주입 (dependencies.py) 문서화 한글 번역

fix: Pydantic 검증 오류 수정
- stt_v2_api_key를 선택적 필드로 변경
- 레거시 환경 변수 복원
```

## 커밋 메시지 예시

### 단순 기능 추가
```
feat: JWT 기반 사용자 인증 구현

- access token과 refresh token 발급 로직 추가
- 토큰 검증 미들웨어 구현
- 토큰 갱신 엔드포인트 추가
```

### 버그 수정
```
fix: Result 체이닝 시 에러 전파 안되는 문제 해결

bind 메서드에서 Failure 상태일 때 후속 연산을 건너뛰도록 수정
이전에는 Failure 상태에서도 bind 연산이 실행되어 예기치 않은 동작 발생

Resolves: #45
```

### 리팩토링
```
refactor: ServiceRegistry 불변성 패턴 적용

- 딕셔너리 직접 수정 대신 스프레드 연산자 사용
- 리스트 append 대신 새 리스트 생성
- 모든 상태 변경이 새로운 인스턴스 반환하도록 수정
```

### 성능 개선
```
perf: 대용량 데이터 처리 시 메모리 사용량 개선

- 제너레이터 패턴 적용으로 메모리 사용량 70% 감소
- 배치 처리 크기를 1000에서 500으로 조정
- 불필요한 중간 리스트 생성 제거

벤치마크: 100만 건 처리 시 메모리 2GB → 600MB
```

### 문서 업데이트
```
docs: Result 패턴 사용법 가이드 추가

- 기본 사용법 및 체이닝 예제 추가
- 비동기 Result 처리 방법 설명
- 다중 Result 조합 패턴 문서화
```

### Breaking Change가 있는 경우
```
feat!: Result API 인터페이스 변경

- unwrap() 메서드가 실패 시 예외 발생하도록 변경
- unwrap_or() 메서드로 기존 동작 대체 가능

BREAKING CHANGE: unwrap() 호출 시 Failure 상태면 
UnwrapError 예외가 발생합니다. 안전한 값 추출을 위해 
unwrap_or()를 사용하세요.
```

## 주의사항

### 1. Claude 코드 사이니지 제거
커밋 메시지에 다음과 같은 내용 **절대 포함 금지**:
- ❌ `🤖 Generated with Claude Code`
- ❌ `Co-Authored-By: Claude <noreply@anthropic.com>`
- ❌ Claude AI, Anthropic 관련 언급

### 2. 의미 있는 커밋 작성
```bash
# ❌ 의미 없는 커밋 메시지
git commit -m "수정"
git commit -m "테스트"
git commit -m "작업 완료"

# ✅ 구체적인 커밋 메시지
git commit -m "fix: 사용자 입력 검증 로직 누락 부분 수정"
git commit -m "test: UserService 단위 테스트 추가"
git commit -m "feat: 사용자 프로필 이미지 업로드 기능 구현"
```

### 3. 커밋 전 체크리스트
- [ ] 코드가 정상 작동하는가?
- [ ] 테스트가 모두 통과하는가?
- [ ] 불필요한 디버그 코드나 주석이 제거되었는가?
- [ ] 커밋 메시지가 변경사항을 명확히 설명하는가?
- [ ] Claude 관련 사이니지가 제거되었는가?

## Git 명령어 예시

### 대화형 커밋 메시지 작성
```bash
# 에디터를 열어 상세한 커밋 메시지 작성
git commit

# 또는 여러 줄 메시지 직접 입력
git commit -m "feat: 사용자 알림 기능 추가" -m "- 이메일 알림 발송 구현" -m "- 푸시 알림 발송 구현"
```

### 커밋 수정
```bash
# 마지막 커밋 메시지 수정
git commit --amend

# Claude 사이니지 제거가 필요한 경우
git rebase -i HEAD~3  # 최근 3개 커밋 수정
```

### 커밋 분리
```bash
# 스테이지된 파일 확인
git status

# 특정 파일만 스테이징
git add src/domain/*.py
git commit -m "refactor: 도메인 모델 Result 패턴 적용"

git add tests/domain/*.py
git commit -m "test: 도메인 모델 테스트 Result 패턴 적용"
```

## 모범 사례

1. **자주 커밋하기**: 작은 단위로 자주 커밋
2. **의미 있는 단위로 커밋**: 하나의 커밋은 하나의 목적
3. **커밋 전 리뷰**: 변경사항 확인 후 커밋
4. **일관성 유지**: 프로젝트 전체에서 동일한 스타일 유지
5. **히스토리 관리**: 깔끔한 커밋 히스토리 유지