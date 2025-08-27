# RFS Framework Wiki 📚

## 개요

RFS Framework의 핵심 개념, 아키텍처 패턴, 그리고 실무 가이드를 제공하는 종합 문서입니다.

---

## 📖 문서 목차

### 🎯 Core Concepts (핵심 개념)

#### 1. [Core Patterns](01-core-patterns.md)
Result 패턴을 중심으로 한 함수형 에러 핸들링과 Railway Oriented Programming 소개
- Result/Either/Maybe 모나드
- 함수형 에러 처리
- 타입 안전성

#### 2. [Dependency Injection](02-dependency-injection.md)
레지스트리 기반 의존성 주입과 서비스 관리
- @stateless 데코레이터
- @inject 패턴
- 서비스 레지스트리

#### 3. [Configuration Management](03-configuration.md)
Pydantic 기반 환경별 설정 관리
- 환경 프로파일 (development, production, cloud_run)
- 설정 검증
- 동적 설정 로딩

#### 15. [Configuration Injection](15-configuration-injection.md) 🆕
설정 값을 구현체에 주입하는 다양한 패턴과 방법
- 직접 가져오기 패턴
- 헬퍼 함수 패턴
- 생성자 주입 패턴
- 의존성 주입 패턴
- 레지스트리 기반 주입

#### 16. [HOF Usage Guide](16-hof-usage-guide.md) ⭐ **필수**
Higher-Order Functions 라이브러리 활용 가이드
- **내장 HOF 우선 사용 원칙**
- 함수 합성 (pipe, compose, curry)
- Swift 스타일 컬렉션 연산 (first, compact_map, flat_map)
- 모나드 패턴 (Maybe, Result, Either)
- 비동기 HOF 및 실전 예제

#### 4. [Transactions](04-transactions.md)
분산 트랜잭션과 데이터 일관성 관리
- 트랜잭션 데코레이터
- 분산 트랜잭션
- 롤백 전략

---

### 🚀 Production & Deployment (프로덕션 & 배포)

#### 5. [Deployment](05-deployment.md)
Google Cloud Run 배포 전략과 최적화
- Blue-Green 배포
- Canary 배포
- Rolling 배포

#### 6. [Rollback](06-rollback.md)
안전한 롤백 전략과 재해 복구
- 자동 롤백
- 수동 롤백
- 복구 전략

#### 7. [Logging](07-logging.md)
구조화된 로깅과 추적 시스템
- 구조화된 로그
- 분산 추적
- 로그 집계

#### 8. [Monitoring](08-monitoring.md)
실시간 모니터링과 알림 시스템
- 메트릭 수집
- 알림 설정
- 대시보드 구성

---

### 🔒 Security & Validation (보안 & 검증)

#### 9. [Validation](09-validation.md)
포괄적인 시스템 검증과 품질 보증
- 입력 검증
- 비즈니스 규칙 검증
- 스키마 검증

#### 10. [Access Control](10-access-control.md)
RBAC/ABAC 기반 접근 제어
- 역할 기반 접근 제어 (RBAC)
- 속성 기반 접근 제어 (ABAC)
- 권한 관리

#### 11. [Security](11-security.md)
보안 강화와 취약점 관리
- 취약점 스캔
- 암호화
- 보안 모범 사례

---

### ⚡ Resilience & Performance (복원력 & 성능)

#### 12. [Circuit Breaker](12-circuit-breaker.md)
장애 격리와 복원력 패턴
- Circuit Breaker 패턴
- 재시도 전략
- Fallback 메커니즘

#### 13. [Load Balancing](13-load-balancing.md)
클라이언트 사이드 로드 밸런싱
- 라운드 로빈
- 가중치 기반
- 헬스 체크

---

### 🛠️ Development Tools (개발 도구)

#### 14. [CLI Interface](14-cli-interface.md)
Rich UI 기반 명령줄 인터페이스
- 프로젝트 관리
- 개발 도구
- 배포 명령어

#### 20. [Code Quality](20-code-quality.md)
코드 품질 관리와 함수형 프로그래밍 가이드
- 품질 표준
- 함수형 프로그래밍 규칙
- 자동화 도구

#### 22. [HOF Library](22-hot-library.md)
Higher-Order Functions 라이브러리
- 함수형 프로그래밍 유틸리티
- Swift/Haskell 영감 받은 패턴
- 모나드와 컴비네이터

#### 17. [Implementation Status](99-implementation-status.md)
구현 현황과 TBD 항목 추적
- 완성된 모듈
- 미완성 항목
- 개선 계획

---

## 🚦 빠른 시작 가이드

### 처음 시작하는 분들을 위한 추천 순서

1. **기본 개념 이해**
   - [Core Patterns](01-core-patterns.md) - Result 패턴 이해
   - [Configuration](03-configuration.md) - 설정 관리
   - [Code Quality](20-code-quality.md) - 코드 작성 가이드

2. **개발 시작**
   - [CLI Interface](14-cli-interface.md) - CLI 도구 사용법
   - [Dependency Injection](02-dependency-injection.md) - DI 패턴
   - [Validation](09-validation.md) - 검증 구현

3. **프로덕션 준비**
   - [Deployment](05-deployment.md) - 배포 전략
   - [Monitoring](08-monitoring.md) - 모니터링 설정
   - [Security](11-security.md) - 보안 강화

---

## 📊 문서별 난이도

| 문서 | 난이도 | 필수 여부 | 예상 학습 시간 |
|------|--------|-----------|----------------|
| Core Patterns | ⭐⭐⭐ | 필수 | 30분 |
| Configuration | ⭐⭐ | 필수 | 20분 |
| CLI Interface | ⭐ | 필수 | 15분 |
| Dependency Injection | ⭐⭐⭐ | 권장 | 25분 |
| Code Quality | ⭐⭐ | 필수 | 30분 |
| Deployment | ⭐⭐⭐ | 권장 | 30분 |
| Security | ⭐⭐⭐⭐ | 권장 | 40분 |
| Circuit Breaker | ⭐⭐⭐⭐ | 선택 | 25분 |
| HOF Library | ⭐⭐⭐ | 권장 | 35분 |
| Implementation Status | ⭐ | 참고 | 10분 |

---

## 🔍 주요 키워드 인덱스

### A-F
- **ABAC**: [Access Control](10-access-control.md)
- **Blue-Green**: [Deployment](05-deployment.md)
- **Circuit Breaker**: [Circuit Breaker](12-circuit-breaker.md)
- **Configuration**: [Configuration](03-configuration.md)
- **Dependency Injection**: [Dependency Injection](02-dependency-injection.md)
- **Functional Programming**: [Code Quality](20-code-quality.md)

### G-M
- **HOF (Higher-Order Functions)**: [HOF Library](22-hot-library.md)
- **Load Balancing**: [Load Balancing](13-load-balancing.md)
- **Logging**: [Logging](07-logging.md)
- **Monitoring**: [Monitoring](08-monitoring.md)
- **Monad**: [Core Patterns](01-core-patterns.md), [HOF Library](22-hot-library.md)

### N-R
- **Pydantic**: [Configuration](03-configuration.md)
- **RBAC**: [Access Control](10-access-control.md)
- **Result Pattern**: [Core Patterns](01-core-patterns.md)
- **Rollback**: [Rollback](06-rollback.md)

### S-Z
- **Security**: [Security](11-security.md)
- **Transaction**: [Transactions](04-transactions.md)
- **Validation**: [Validation](09-validation.md)

---

## 💡 Tips

### 효과적인 학습 방법
1. **실습 위주**: 각 문서의 코드 예제를 직접 실행해보세요
2. **점진적 학습**: 기본 개념부터 차근차근 익혀나가세요
3. **프로젝트 적용**: 학습한 내용을 실제 프로젝트에 적용해보세요

### 문서 활용 팁
- 각 문서는 독립적으로 읽을 수 있도록 구성되어 있습니다
- 코드 예제는 복사하여 바로 사용 가능합니다
- 관련 문서 링크를 통해 깊이 있는 학습이 가능합니다

---

## 🤝 기여하기

문서 개선에 기여하고 싶으신가요?

1. 오타나 오류를 발견하면 Issue를 생성해주세요
2. 새로운 예제나 설명을 추가하고 싶다면 PR을 보내주세요
3. 질문이 있다면 Discussions에서 논의해주세요

---

## 📅 최근 업데이트

- **2025-08-26**: HOF Library 문서 추가 및 Context7 업데이트
- **2025-08-26**: 함수형 프로그래밍 유틸리티 문서화
- **2025-08-25**: Wiki README.md 생성
- **2025-08-24**: Implementation Status 문서 추가
- **2025-08-24**: Code Quality 가이드라인 업데이트

---

## 📚 추가 리소스

- [프로젝트 README](../README.md) - 프로젝트 개요
- [TODO List](../TODO.md) - 개발 진행 상황
- [API Reference](../docs/API_REFERENCE.md) - API 문서
- [Examples](../examples/) - 예제 코드

---

**RFS Framework Wiki** - 엔터프라이즈급 Python 프레임워크의 완벽한 가이드