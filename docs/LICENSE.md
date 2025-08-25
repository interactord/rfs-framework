# MIT License

Copyright (c) 2025 RFS Framework Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 제3자 라이브러리 라이선스

RFS Framework는 다음 오픈소스 라이브러리들을 사용합니다:

### 핵심 의존성

- **Pydantic** (MIT License)
  - 데이터 검증 및 설정 관리
  - https://github.com/pydantic/pydantic

### 웹 모듈 의존성 ([web])

- **FastAPI** (MIT License)
  - 웹 프레임워크
  - https://github.com/tiangolo/fastapi

- **Uvicorn** (BSD License)
  - ASGI 서버
  - https://github.com/encode/uvicorn

### 데이터베이스 모듈 의존성 ([database])

- **SQLAlchemy** (MIT License)
  - ORM 및 데이터베이스 추상화
  - https://github.com/sqlalchemy/sqlalchemy

- **Alembic** (MIT License)
  - 데이터베이스 마이그레이션
  - https://github.com/sqlalchemy/alembic

- **Redis-py** (MIT License)
  - Redis 클라이언트
  - https://github.com/redis/redis-py

### 테스트 모듈 의존성 ([test])

- **Pytest** (MIT License)
  - 테스팅 프레임워크
  - https://github.com/pytest-dev/pytest

- **Pytest-asyncio** (Apache 2.0 License)
  - 비동기 테스트 지원
  - https://github.com/pytest-dev/pytest-asyncio

- **Coverage.py** (Apache 2.0 License)
  - 코드 커버리지 측정
  - https://github.com/nedbat/coveragepy

### 개발 도구 의존성 ([dev])

- **Black** (MIT License)
  - 코드 포매터
  - https://github.com/psf/black

- **MyPy** (MIT License)
  - 정적 타입 검사
  - https://github.com/python/mypy

- **isort** (MIT License)
  - Import 정렬
  - https://github.com/PyCQA/isort

- **Flake8** (MIT License)
  - 린터
  - https://github.com/PyCQA/flake8

### 문서화 도구 의존성 ([docs])

- **MkDocs** (BSD License)
  - 문서 생성기
  - https://github.com/mkdocs/mkdocs

- **MkDocs-Material** (MIT License)
  - Material Design 테마
  - https://github.com/squidfunk/mkdocs-material

- **mkdocstrings** (ISC License)
  - API 문서 자동 생성
  - https://github.com/mkdocstrings/mkdocstrings

### Google Cloud 의존성

- **Google Cloud Run SDK** (Apache 2.0 License)
  - Cloud Run 통합
  - https://github.com/googleapis/python-run

- **Google Cloud Logging** (Apache 2.0 License)
  - 로깅 통합
  - https://github.com/googleapis/python-logging

## 기여자

RFS Framework는 다음 개발자들의 기여로 만들어졌습니다:

- **RFS Framework Team** - 핵심 개발 및 유지보수
- **Community Contributors** - 버그 수정, 기능 개선, 문서 작성

## 상표권

- **RFS Framework**는 RFS Framework Team의 상표입니다.
- **Google Cloud Run**은 Google LLC의 상표입니다.
- 기타 모든 상표는 해당 소유자의 자산입니다.

## 면책 조항

이 소프트웨어는 "있는 그대로" 제공되며, 어떠한 보증도 하지 않습니다. 소프트웨어 사용으로 인한 모든 위험은 사용자가 부담합니다.

자세한 내용은 위의 MIT 라이선스 전문을 참조하세요.