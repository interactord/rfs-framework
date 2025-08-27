# RFS Framework 로드맵

## 현재 버전: v4.3.1 (Production Ready)

### 완료된 기능 ✅
- ✅ Result 패턴 구현
- ✅ Reactive Streams (Mono/Flux)
- ✅ Cloud Run 최적화
- ✅ 의존성 주입 시스템
- ✅ 13개 한국어 문서 모듈
- ✅ 기본 CLI 명령어 (version, status, config, help)

### 진행 중 🔄
- 🔄 Gateway 모듈 완성 (REST 완료, GraphQL 진행 중)
- 🔄 CLI 고급 기능 개발

## v4.4.0 (계획 중 - 2025 Q1)

### CLI 확장 기능
- [ ] `rfs init` - 프로젝트 스캐폴딩
  - 프로젝트 템플릿 선택
  - 의존성 자동 설정
  - 기본 구조 생성
  
- [ ] `rfs dev` - 개발 서버 통합
  - 자동 재시작
  - 핫 리로딩
  - 디버그 모드
  
- [ ] `rfs test` - 테스트 실행기
  - 유닛 테스트 통합
  - 통합 테스트 지원
  - 커버리지 리포트

### Gateway 모듈 완성
- [ ] GraphQL 게이트웨이 구현
  - 스키마 정의
  - 리졸버 시스템
  - 구독 지원
  
- [ ] 미들웨어 시스템
  - 인증 미들웨어
  - CORS 미들웨어
  - 로깅 미들웨어
  
- [ ] 프록시 게이트웨이
  - 로드 밸런싱
  - 헬스 체크
  - 서비스 디스커버리

## v4.5.0 (계획 중 - 2025 Q2)

### 배포 및 CI/CD
- [ ] `rfs build` - 프로덕션 빌드
  - 최적화 빌드
  - 도커 이미지 생성
  - 환경별 설정
  
- [ ] `rfs deploy` - Cloud Run 배포
  - 자동 배포 파이프라인
  - Blue-Green 배포
  - 롤백 지원
  
- [ ] `rfs docs` - 문서 생성
  - API 문서 자동 생성
  - Swagger/OpenAPI 지원
  - MkDocs 통합

### 성능 최적화
- [ ] Cold Start 최적화 개선
- [ ] 메모리 사용량 최적화
- [ ] 비동기 처리 개선

## v5.0.0 (장기 계획 - 2025 Q3)

### 주요 아키텍처 개선
- [ ] 플러그인 시스템
- [ ] 마이크로서비스 지원
- [ ] 멀티 클라우드 지원 (AWS Lambda, Azure Functions)

### 엔터프라이즈 기능
- [ ] 분산 트랜잭션
- [ ] 이벤트 소싱
- [ ] CQRS 패턴 지원
- [ ] 멀티 테넌시

### 개발자 경험 향상
- [ ] Visual Studio Code 확장
- [ ] 디버깅 툴체인
- [ ] 성능 프로파일링 도구
- [ ] 대화형 CLI (REPL)

## 기여 방법

RFS Framework는 오픈소스 프로젝트입니다. 기여를 환영합니다!

### 기여 가이드라인
1. Issue 등록 또는 기존 Issue 확인
2. Fork 후 feature 브랜치 생성
3. 변경사항 구현 및 테스트 작성
4. Pull Request 제출

### 우선순위가 높은 작업
- 🔴 **긴급**: Gateway 모듈 GraphQL 구현
- 🟠 **높음**: CLI 고급 명령어 구현
- 🟡 **중간**: 문서화 및 예제 추가
- 🟢 **낮음**: 성능 최적화

## 알려진 이슈

### v4.3.1 현재
- ⚠️ 일부 CLI 명령어 미구현 (init, dev, build, deploy, test, docs)
- ⚠️ Gateway 모듈 일부 기능 플레이스홀더
- ⚠️ FastAPI 의존성이 선택적이지만 많은 예제에서 필요

### 해결 예정
- v4.4.0: CLI 명령어 완성
- v4.4.0: Gateway 모듈 전체 구현
- v4.5.0: 선택적 의존성 관리 개선

## 릴리즈 사이클

- **Patch 릴리즈** (x.x.1): 매주 버그 수정
- **Minor 릴리즈** (x.1.0): 매월 새 기능
- **Major 릴리즈** (1.0.0): 분기별 주요 변경

## 연락처

- GitHub: https://github.com/interactord/rfs-framework
- PyPI: https://pypi.org/project/rfs-framework/
- 이슈 트래커: https://github.com/interactord/rfs-framework/issues

---

*최종 업데이트: 2025-08-27*