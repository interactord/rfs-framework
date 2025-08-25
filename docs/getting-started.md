# 시작하기

## 요구 사항

RFS Framework를 사용하기 위한 최소 요구 사항:

- **Python**: 3.10 이상
- **메모리**: 512MB RAM (권장: 1GB+)
- **운영체제**: Linux, macOS, Windows

## 설치

### 기본 설치

```bash
pip install rfs-framework
```

### 선택적 모듈

용도에 따라 필요한 모듈을 선택적으로 설치할 수 있습니다:

| 모듈 | 설명 | 상태 | 설치 명령 |
|------|------|------|-----------|
| **web** | FastAPI 웹 프레임워크 | ✅ 완료 | `pip install rfs-framework[web]` |
| **database** | 데이터베이스 지원 | ✅ 완료 | `pip install rfs-framework[database]` |
| **test** | 테스팅 도구 | ✅ 완료 | `pip install rfs-framework[test]` |
| **dev** | 개발 도구 | ✅ 완료 | `pip install rfs-framework[dev]` |
| **docs** | 문서화 도구 | ⚠️ TBD | `pip install rfs-framework[docs]` |
| **ai** | AI/ML 통합 | ⚠️ TBD | `pip install rfs-framework[ai]` |
| **all** | 모든 모듈 | - | `pip install rfs-framework[all]` |

## 첫 번째 프로젝트

### 1. 프로젝트 생성

```bash
# CLI를 사용한 프로젝트 생성
rfs-cli create-project my-app --template basic

# 프로젝트 디렉토리로 이동
cd my-app
```

### 2. 기본 예제

```python title="app.py"
from rfs import Result, Success, Failure
from rfs.reactive import Flux
import asyncio

# Result 패턴 사용
def process_data(data: dict) -> Result[dict, str]:
    """데이터 처리 함수"""
    if not data:
        return Failure("데이터가 비어있습니다")
    
    # 데이터 변환
    processed = {
        "id": data.get("id"),
        "name": data.get("name", "").upper(),
        "timestamp": datetime.now()
    }
    return Success(processed)

# 반응형 스트림 사용
async def stream_processing():
    """비동기 스트림 처리"""
    result = await (
        Flux.from_iterable(range(10))
        .map(lambda x: x * 2)
        .filter(lambda x: x > 5)
        .collect_list()
    )
    return result

# 실행
if __name__ == "__main__":
    # Result 패턴 테스트
    result = process_data({"id": 1, "name": "test"})
    if result.is_success:
        print(f"성공: {result.unwrap()}")
    
    # 반응형 스트림 테스트
    stream_result = asyncio.run(stream_processing())
    print(f"스트림 결과: {stream_result}")
```

### 3. 웹 API 생성

```python title="web_app.py"
from rfs.web import RFSApp
from rfs import Result, Success, Failure

# 앱 생성
app = RFSApp()

@app.route("/health", method="GET")
async def health_check() -> Result[dict, str]:
    """헬스 체크 엔드포인트"""
    return Success({"status": "healthy", "version": "4.3.0"})

@app.route("/users/{user_id}", method="GET")
async def get_user(user_id: int) -> Result[dict, str]:
    """사용자 조회"""
    # 실제로는 데이터베이스에서 조회
    if user_id == 1:
        return Success({"id": 1, "name": "John Doe"})
    return Failure(f"User {user_id} not found")

# 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## 개발 환경 설정

### VS Code 설정

`.vscode/settings.json`:

```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.linting.mypyEnabled": true,
    "editor.formatOnSave": true,
    "python.testing.pytestEnabled": true
}
```

### Pre-commit 설정

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
```

설치 및 활성화:

```bash
pip install pre-commit
pre-commit install
```

## 다음 단계

- [핵심 개념](01-core-patterns.md) - Result 패턴과 함수형 프로그래밍
- [설정 관리](03-configuration.md) - 환경별 설정
- [CLI 도구](14-cli-interface.md) - 명령행 인터페이스
- [API 레퍼런스](api/index.md) - 상세 API 문서