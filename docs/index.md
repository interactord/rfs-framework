# RFS Framework

<div align="center">

![RFS Framework Logo](https://img.shields.io/badge/RFS-Framework-blue?style=for-the-badge&logo=python&logoColor=white)

**Enterprise-Grade Reactive Functional Serverless Framework for Python**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/Version-4.3.6-green.svg)](https://pypi.org/project/rfs-framework/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://interactord.github.io/rfs-framework/)

</div>

## 🎯 프레임워크 소개

RFS Framework는 현대적인 엔터프라이즈 Python 애플리케이션을 위한 종합적인 프레임워크입니다. 함수형 프로그래밍 패턴, 반응형 아키텍처, 그리고 Google Cloud Platform과의 완벽한 통합을 제공합니다.

## ✨ 핵심 특징

### 🎯 함수형 프로그래밍
- **Result Pattern**: 예외 없는 안전한 에러 처리
- **HOF Library**: Swift/Haskell 영감의 고차 함수
- **Readable HOF**: 자연어에 가까운 선언적 코드 패턴
- **Monads**: Maybe, Either, Result 모나드 지원
- **불변성**: 순수 함수와 불변 데이터 구조

### ⚡ 반응형 스트림
- **Mono/Flux**: 비동기 반응형 스트림 처리
- **백프레셔**: 자동 흐름 제어
- **30+ 연산자**: map, filter, flat_map 등
- **병렬 처리**: 멀티스레드 실행 컨텍스트

### 🔒 엔터프라이즈 보안
- **RBAC/ABAC**: 역할 및 속성 기반 접근 제어
- **JWT 인증**: 토큰 기반 인증 시스템
- **취약점 스캐닝**: 자동 보안 검사
- **암호화**: AES-256 데이터 암호화

### 🚀 프로덕션 준비
- **배포 전략**: Blue-Green, Canary, Rolling
- **Circuit Breaker**: 장애 격리 패턴
- **모니터링**: 실시간 성능 메트릭
- **자동 롤백**: 체크포인트 기반 복구

## 📊 성능 지표

| 메트릭 | 값 | 비고 |
|--------|-----|------|
| **시작 시간** | ~50ms | CLI 초기화 |
| **메모리 사용** | ~25MB | 기본 실행 |
| **응답 시간** | <100ms | API 호출 |
| **처리량** | 1200 RPS | 벤치마크 |
| **완성도** | 93% | v4.3.6 |

## 🚀 빠른 시작

### 설치

=== "PyPI"

    ```bash
    # 기본 설치
    pip install rfs-framework
    
    # 모든 기능 포함
    pip install rfs-framework[all]
    ```

=== "GitHub"

    ```bash
    # 최신 버전 설치
    pip install git+https://github.com/interactord/rfs-framework.git
    ```

### 첫 번째 예제

=== "Result Pattern"

    ```python
    from rfs import Result, Success, Failure

    def divide(a: int, b: int) -> Result[float, str]:
        """안전한 나눗셈 연산"""
        if b == 0:
            return Failure("Cannot divide by zero")
        return Success(a / b)

    # 사용 예제
    result = divide(10, 2)
    if result.is_success:
        print(f"결과: {result.unwrap()}")  # 결과: 5.0
    else:
        print(f"오류: {result.unwrap_err()}")
    ```

=== "Readable HOF"

    ```python
    from rfs.hof.readable import validate_config, required, range_check

    # 자연어 같은 선언적 검증
    config = {"api_key": "secret", "timeout": 30, "port": 8080}
    
    result = validate_config(config).against_rules([
        required("api_key", "API 키가 필요합니다"),
        range_check("timeout", 1, 300, "타임아웃은 1-300초 사이"),
        range_check("port", 1, 65535, "포트 범위 오류")
    ])
    
    if result.is_success():
        print("✅ 설정이 유효합니다")
    else:
        print(f"❌ {result.unwrap_error()}")
    ```

## 📚 문서 구조

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } **핵심 개념**

    ---

    Result 패턴, 의존성 주입, 설정 관리 등 프레임워크의 핵심 개념을 학습합니다.

    [:octicons-arrow-right-24: 핵심 개념 보기](01-core-patterns.md)

-   :material-rocket-launch:{ .lg .middle } **프로덕션**

    ---

    배포, 모니터링, 롤백 등 프로덕션 운영에 필요한 모든 기능을 다룹니다.

    [:octicons-arrow-right-24: 프로덕션 가이드](05-deployment.md)

-   :material-shield-lock:{ .lg .middle } **보안**

    ---

    인증, 인가, 보안 강화 등 엔터프라이즈 보안 기능을 설명합니다.

    [:octicons-arrow-right-24: 보안 문서](11-security.md)

-   :material-api:{ .lg .middle } **API 레퍼런스**

    ---

    모든 클래스, 함수, 메서드의 상세한 API 문서를 제공합니다.

    [:octicons-arrow-right-24: API 문서](api/index.md)

</div>

## 🛠️ 기술 스택

- **언어**: Python 3.10+
- **타입 체크**: mypy, Pydantic v2
- **테스트**: pytest, pytest-asyncio
- **포맷팅**: black, isort
- **문서화**: MkDocs Material
- **CI/CD**: GitHub Actions
- **클라우드**: Google Cloud Run

## 🤝 기여하기

RFS Framework는 오픈소스 프로젝트입니다. 기여를 환영합니다!

- [기여 가이드](CONTRIBUTING.md)
- [이슈 보고](https://github.com/interactord/rfs-framework/issues)
- [토론 참여](https://github.com/interactord/rfs-framework/discussions)

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE.md) 파일을 참조하세요.

---

<div align="center">
<strong>Made with ❤️ by the RFS Framework Team</strong>
</div>