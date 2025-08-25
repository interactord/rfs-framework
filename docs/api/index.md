# API 레퍼런스

RFS Framework의 모든 공개 API에 대한 상세한 문서입니다.

## 🔧 Core (핵심)

핵심 프레임워크 기능을 제공합니다.

- **[Result Pattern](core/result.md)** - 함수형 에러 핸들링
- **[Configuration](core/config.md)** - 설정 관리 시스템
- **[Registry](core/registry.md)** - 의존성 주입 레지스트리

## ⚡ Reactive (반응형)

비동기 반응형 스트림 처리를 위한 API입니다.

- **[Mono](reactive/mono.md)** - 단일 값 비동기 스트림
- **[Flux](reactive/flux.md)** - 다중 값 비동기 스트림

## 🎯 HOF (Higher-Order Functions)

함수형 프로그래밍을 위한 고차 함수 라이브러리입니다.

- **[Core Functions](hof/core.md)** - compose, pipe, curry 등
- **[Collections](hof/collections.md)** - 컬렉션 처리 유틸리티
- **[Monads](hof/monads.md)** - Maybe, Either, Result 모나드

## 📚 추가 모듈

### 🌐 Web
- FastAPI/Flask 통합
- 미들웨어 시스템
- 라우팅 관리

### 💾 Database  
- SQLAlchemy 통합
- Redis 캐시
- 마이그레이션 도구

### 🛡️ Security
- RBAC/ABAC 접근 제어
- JWT 인증
- 보안 스캐너

### 📊 Monitoring
- 성능 메트릭
- 헬스 체크
- 로깅 시스템

### 🚀 Production
- 배포 전략
- 롤백 관리
- 최적화 도구

## 사용 예제

각 API 문서에는 다음이 포함되어 있습니다:

- **개요**: 기능 설명
- **파라미터**: 입력 매개변수
- **반환값**: 출력 형태
- **예제**: 실제 사용 코드
- **관련 API**: 연관된 다른 API

## 버전별 변경사항

API 변경사항은 [CHANGELOG](../changelog.md)에서 확인할 수 있습니다.