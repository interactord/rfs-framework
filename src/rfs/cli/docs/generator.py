"""
Documentation Generator (RFS v4)

종합적인 문서 자동 생성 시스템
- 다양한 형식 지원 (Markdown, HTML, PDF)
- 템플릿 기반 생성
- 자동 코드 분석 및 문서화
- 다국어 지원
"""

import ast
import asyncio
import inspect
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rfs.core.registry import stateless

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ...core.config import get_config
from ...core.result import Failure, Result, Success

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class DocFormat(Enum):
    """문서 형식"""

    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    SPHINX = "sphinx"


class DocType(Enum):
    """문서 유형"""

    API = "api"
    USER_GUIDE = "user_guide"
    DEVELOPER_GUIDE = "developer_guide"
    ARCHITECTURE = "architecture"
    TUTORIAL = "tutorial"
    REFERENCE = "reference"
    CHANGELOG = "changelog"


@dataclass
class DocConfig:
    """문서 생성 설정"""

    output_dir: str = "docs"
    formats: List[DocFormat] = field(default_factory=lambda: [DocFormat.MARKDOWN])
    include_private: bool = False
    include_source: bool = True
    language: str = "ko"
    theme: str = "default"
    auto_toc: bool = True
    include_examples: bool = True
    generate_index: bool = True
    project_info: Dict[str, Any] = field(default_factory=dict)
    custom_templates: Dict[str, str] = field(default_factory=dict)


class DocumentationGenerator:
    """문서 생성 메인 클래스"""

    def __init__(self, config: Optional[DocConfig] = None):
        self.config = config or DocConfig()
        self.project_path = Path.cwd()
        self.output_path = Path(self.config.output_dir)
        self.templates_path = Path(__file__).parent / "templates"
        self._collect_project_info()

    def _collect_project_info(self):
        """프로젝트 정보 자동 수집"""
        try:
            if not self.config.project_info:
                self.config.project_info = {}
            self.config.project_info.setdefault("name", self.project_path.name)
            self.config.project_info.setdefault("version", "1.0.0")
            self.config.project_info.setdefault("description", "RFS v4 프로젝트")
            self.config.project_info.setdefault("author", "RFS Team")
            self.config.project_info.setdefault(
                "generated_at", datetime.now().isoformat()
            )
            setup_py = self.project_path / "setup.py"
            if setup_py.exists():
                self._parse_setup_py(setup_py)
            pyproject_toml = self.project_path / "pyproject.toml"
            if pyproject_toml.exists():
                self._parse_pyproject_toml(pyproject_toml)
        except Exception as e:
            if console:
                console.print(
                    f"⚠️  프로젝트 정보 수집 중 오류: {str(e)}", style="yellow"
                )

    def _parse_setup_py(self, setup_file: Path):
        """setup.py 파싱"""
        try:
            content = setup_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if (
                    type(node).__name__ == "Call"
                    and hasattr(node.func, "id")
                    and (node.func.id == "setup")
                ):
                    for keyword in node.keywords:
                        if keyword.arg in ["name", "version", "description", "author"]:
                            if type(keyword.value).__name__ == "Str":
                                self.config.project_info = {
                                    **self.config.project_info,
                                    keyword.arg: keyword.value.s,
                                }
                            elif type(keyword.value).__name__ == "Constant":
                                self.config.project_info = {
                                    **self.config.project_info,
                                    keyword.arg: keyword.value.value,
                                }
        except Exception:
            pass

    def _parse_pyproject_toml(self, toml_file: Path):
        """pyproject.toml 파싱"""
        try:
            import tomllib

            content = toml_file.read_text(encoding="utf-8")
            data = tomllib.loads(content)
            project = data.get("project", {})
            for key in ["name", "version", "description"]:
                if key in project:
                    self.config.project_info = {
                        **self.config.project_info,
                        key: project[key],
                    }
            authors = project.get("authors", [])
            if authors and (
                hasattr(authors[0], "__class__")
                and authors[0].__class__.__name__ == "dict"
            ):
                self.config.project_info = {
                    **self.config.project_info,
                    "author": authors[0].get("name", "Unknown"),
                }
        except Exception:
            pass

    async def generate_all_docs(
        self, doc_types: Optional[List[DocType]] = None
    ) -> Result[Dict[str, str], str]:
        """모든 문서 생성"""
        try:
            if doc_types is None:
                doc_types = [DocType.API, DocType.USER_GUIDE, DocType.DEVELOPER_GUIDE]
            if console:
                console.print(
                    Panel(
                        f"📚 RFS v4 문서 자동 생성 시작\n\n📁 출력 디렉토리: {self.output_path}\n📄 형식: {', '.join([f.value for f in self.config.formats])}\n🌍 언어: {self.config.language}\n📋 문서 유형: {len(doc_types)}개",
                        title="문서 생성",
                        border_style="blue",
                    )
                )
            self.output_path.mkdir(parents=True, exist_ok=True)
            generated_docs = {}
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console,
            ) as progress:
                for doc_type in doc_types:
                    task = progress.add_task(
                        f"{doc_type.value} 문서 생성 중...", total=100
                    )
                    match doc_type:
                        case DocType.API:
                            result = await self._generate_api_docs()
                        case DocType.USER_GUIDE:
                            result = await self._generate_user_guide()
                        case DocType.DEVELOPER_GUIDE:
                            result = await self._generate_developer_guide()
                        case DocType.ARCHITECTURE:
                            result = await self._generate_architecture_docs()
                        case DocType.TUTORIAL:
                            result = await self._generate_tutorial()
                        case DocType.REFERENCE:
                            result = await self._generate_reference()
                        case DocType.CHANGELOG:
                            result = await self._generate_changelog()
                        case _:
                            result = Failure(f"지원하지 않는 문서 유형: {doc_type}")
                    if result.is_success():
                        generated_docs[doc_type.value] = {
                            doc_type.value: result.unwrap()
                        }
                    progress = {**progress, **task}
            if self.config.generate_index:
                await self._generate_index_page(generated_docs)
            if console:
                console.print(
                    Panel(
                        f"✅ 문서 생성 완료!\n\n📁 생성된 문서: {len(generated_docs)}개\n📂 위치: {self.output_path.absolute()}\n\n🌐 브라우저에서 보기:\n  file://{(self.output_path / 'index.html').absolute()}",
                        title="문서 생성 완료",
                        border_style="green",
                    )
                )
            return Success(generated_docs)
        except Exception as e:
            return Failure(f"문서 생성 실패: {str(e)}")

    async def _generate_api_docs(self) -> Result[str, str]:
        """API 문서 생성"""
        try:
            modules = await self._analyze_python_modules()
            api_content = self._render_api_template(modules)
            for format_type in self.config.formats:
                if format_type == DocFormat.MARKDOWN:
                    api_file = self.output_path / "api.md"
                    api_file.write_text(api_content, encoding="utf-8")
                elif format_type == DocFormat.HTML:
                    html_content = self._markdown_to_html(api_content)
                    api_file = self.output_path / "api.html"
                    api_file.write_text(html_content, encoding="utf-8")
            return Success(str(api_file))
        except Exception as e:
            return Failure(f"API 문서 생성 실패: {str(e)}")

    async def _analyze_python_modules(self) -> List[Dict[str, Any]]:
        """Python 모듈 분석"""
        modules = []
        try:
            python_files = list(self.project_path.rglob("*.py"))
            for py_file in python_files:
                if py_file.name.startswith("__"):
                    continue
                try:
                    module_info = await self._analyze_module(py_file)
                    if module_info:
                        modules = modules + [module_info]
                except Exception as e:
                    if console:
                        console.print(
                            f"⚠️  모듈 분석 실패 {py_file}: {str(e)}", style="yellow"
                        )
        except Exception as e:
            if console:
                console.print(f"⚠️  모듈 분석 중 오류: {str(e)}", style="yellow")
        return modules

    async def _analyze_module(self, py_file: Path) -> Optional[Dict[str, Any]]:
        """개별 모듈 분석"""
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            module_info = {
                "name": py_file.stem,
                "path": str(py_file.relative_to(self.project_path)),
                "docstring": ast.get_docstring(tree),
                "classes": [],
                "functions": [],
                "imports": [],
            }
            for node in ast.walk(tree):
                if type(node).__name__ == "ClassDef":
                    class_info = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "methods": [],
                        "line_number": node.lineno,
                    }
                    for item in node.body:
                        if type(item).__name__ == "FunctionDef":
                            method_info = {
                                "name": item.name,
                                "docstring": ast.get_docstring(item),
                                "args": [arg.arg for arg in item.args.args],
                                "line_number": item.lineno,
                                "is_async": type(item).__name__ == "AsyncFunctionDef",
                            }
                            class_info["methods"] = class_info.get("methods") + [
                                method_info
                            ]
                    module_info["classes"] = module_info.get("classes") + [class_info]
                elif type(node).__name__ in ["FunctionDef", "AsyncFunctionDef"]:
                    if not any(
                        (
                            type(parent).__name__ == "ClassDef"
                            for parent in ast.walk(tree)
                            if hasattr(parent, "body")
                            and node in getattr(parent, "body", [])
                        )
                    ):
                        function_info = {
                            "name": node.name,
                            "docstring": ast.get_docstring(node),
                            "args": [arg.arg for arg in node.args.args],
                            "line_number": node.lineno,
                            "is_async": type(node).__name__ == "AsyncFunctionDef",
                        }
                        module_info["functions"] = module_info.get("functions") + [
                            function_info
                        ]
                elif type(node).__name__ in ["Import", "ImportFrom"]:
                    if type(node).__name__ == "Import":
                        for alias in node.names:
                            module_info["imports"] = module_info.get("imports") + [
                                alias.name
                            ]
                    elif node.module:
                        module_info["imports"] = module_info.get("imports") + [
                            node.module
                        ]
            return module_info
        except Exception as e:
            return None

    def _render_api_template(self, modules: List[Dict[str, Any]]) -> str:
        """API 문서 템플릿 렌더링"""
        content = f"# {self.config.project_info.get('name', 'Project')} API 문서\n\n{self.config.project_info.get('description', '')}\n\n**버전:** {self.config.project_info.get('version', '1.0.0')}  \n**생성일:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n## 목차\n\n"
        for module in modules:
            content = content + f"- [{module['name']}](#{module['name'].lower()})\n"
            for cls in module.get("classes"):
                content = content + f"  - [{cls['name']}](#{cls['name'].lower()})\n"
            for func in module.get("functions"):
                content = content + f"  - [{func['name']}()](#{func['name'].lower()})\n"
        content = content + "\n---\n\n"
        for module in modules:
            content = content + f"## {module['name']}\n\n"
            if module.get("docstring"):
                content = content + f"{module['docstring']}\n\n"
            content = content + f"**파일:** `{module['path']}`\n\n"
            if module.get("imports"):
                content = content + "**의존성:**\n"
                for imp in module.get("imports"):
                    content = content + f"- `{imp}`\n"
                content = content + "\n"
            for cls in module.get("classes"):
                content = content + f"### {cls['name']}\n\n"
                if cls.get("docstring"):
                    content = content + f"{cls['docstring']}\n\n"
                if cls.get("methods"):
                    content = content + "**메서드:**\n\n"
                    for method in cls.get("methods"):
                        async_marker = "async " if method["is_async"] else ""
                        args_str = ", ".join(method["args"]) if method["args"] else ""
                        content = (
                            content
                            + f"#### {async_marker}`{method['name']}({args_str})`\n\n"
                        )
                        if method.get("docstring"):
                            content = content + f"{method['docstring']}\n\n"
                        else:
                            content = content + "문서화되지 않은 메서드입니다.\n\n"
            for func in module.get("functions"):
                async_marker = "async " if func["is_async"] else ""
                args_str = ", ".join(func["args"]) if func["args"] else ""
                content = (
                    content + f"### {async_marker}`{func['name']}({args_str})`\n\n"
                )
                if func.get("docstring"):
                    content = content + f"{func['docstring']}\n\n"
                else:
                    content = content + "문서화되지 않은 함수입니다.\n\n"
            content = content + "---\n\n"
        return content

    async def _generate_user_guide(self) -> Result[str, str]:
        """사용자 가이드 생성"""
        try:
            project_name = self.config.project_info.get("name", "Project")
            project_description = self.config.project_info.get("description", "")
            project_package = self.config.project_info.get("name", "project").lower()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            guide_content = f"""# {project_name} 사용자 가이드

{project_description}

## 빠른 시작

### 1. 설치

```bash
pip install {project_package}
```

### 2. 기본 사용법

```python
from {project_package} import RFSConfig

# 기본 설정
config = RFSConfig()

# 애플리케이션 시작
app = RFSApplication(config)
await app.start()
```

### 3. 설정

환경 변수를 통해 애플리케이션을 설정할 수 있습니다:

```env
RFS_ENVIRONMENT=production
RFS_DEBUG=false
RFS_LOG_LEVEL=INFO
```

## 주요 기능

### Result Pattern

RFS Framework는 함수형 프로그래밍의 Result 패턴을 사용합니다:

```python
from rfs import Result, Success, Failure

def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Failure("0으로 나눌 수 없습니다")
    return Success(a / b)

result = divide(10, 2)
if result.is_success():
    print(f"결과: {{result.unwrap()}}")
else:
    print(f"오류: {{result.unwrap_err()}}")
```

### Cloud Run 통합

Google Cloud Run에 최적화된 기능들:

```python
from rfs.cloud_run import initialize_cloud_run_services

# Cloud Run 서비스 초기화
await initialize_cloud_run_services(
    project_id="your-project",
    service_name="your-service"
)
```

## 고급 사용법

### 서비스 등록

```python
from rfs import stateless

@stateless
class UserService:
    async def get_user(self, user_id: str) -> Result[User, str]:
        # 사용자 조회 로직
        pass
```

### 이벤트 시스템

```python
from rfs import get_event_bus, event_handler

@event_handler("user_created")
async def handle_user_created(event):
    print(f"새 사용자 생성됨: {{event.data}}")

# 이벤트 발생
await get_event_bus().publish("user_created", {{"user_id": "123"}})
```

## 문제 해결

### 일반적인 오류

1. **설정 오류**: `.env` 파일 확인
2. **의존성 오류**: `pip install -r requirements.txt` 실행
3. **포트 충돌**: `RFS_PORT` 환경 변수 설정

### 디버깅

```bash
# 디버그 모드로 실행
RFS_DEBUG=true python main.py

# 로그 레벨 설정
RFS_LOG_LEVEL=DEBUG python main.py
```

## API 참조

자세한 API 문서는 [API 문서](api.md)를 참조하세요.

---

생성일: {current_time}
"""
            guide_file = self.output_path / "user-guide.md"
            guide_file.write_text(guide_content, encoding="utf-8")
            if DocFormat.HTML in self.config.formats:
                html_content = self._markdown_to_html(guide_content)
                html_file = self.output_path / "user-guide.html"
                html_file.write_text(html_content, encoding="utf-8")
            return Success(str(guide_file))
        except Exception as e:
            return Failure(f"사용자 가이드 생성 실패: {str(e)}")

    async def _generate_developer_guide(self) -> Result[str, str]:
        """개발자 가이드 생성"""
        try:
            # 프로젝트 정보 추출
            project_name = self.config.project_info.get("name", "Project")
            project_package = self.config.project_info.get("name", "project").lower()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 개발자 가이드 템플릿
            dev_guide_content = f"""# {project_name} 개발자 가이드

이 문서는 {project_name} 프로젝트의 개발에 참여하는 개발자들을 위한 가이드입니다.

## 개발 환경 설정

### 필수 요구사항

- Python 3.10+
- Docker
- Google Cloud SDK (Cloud Run 사용 시)

### 개발 환경 구축

```bash
# 저장소 클론
git clone <repository-url>
cd {project_package}

# 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# 의존성 설치
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 개발 서버 실행
python main.py
```

## 프로젝트 구조

```
{project_name}/
├── {project_package}/
│   ├── core/           # 핵심 모듈
│   ├── cloud_run/      # Cloud Run 전용 기능
│   ├── cli/           # CLI 도구
│   └── __init__.py
├── tests/             # 테스트 코드
├── docs/              # 문서
├── requirements.txt   # 의존성
└── main.py           # 진입점
```

## 개발 가이드라인

### 코딩 스타일

- **포매터**: Black
- **린터**: Ruff
- **타입 체크**: MyPy
- **주석**: 한국어 사용

```python
def calculate_score(user_id: str, metrics: Dict[str, float]) -> Result[float, str]:
    \"\"\"
    사용자 점수 계산
    
    Args:
        user_id: 사용자 ID
        metrics: 메트릭 데이터
        
    Returns:
        Result[float, str]: 계산된 점수 또는 오류 메시지
    \"\"\"
    if not user_id:
        return Failure("사용자 ID가 필요합니다")
    
    # 점수 계산 로직
    score = sum(metrics.values()) / len(metrics)
    return Success(score)
```

### Git 워크플로우

1. **브랜치 생성**: `feature/기능명` 또는 `bugfix/이슈번호`
2. **커밋 메시지**: `feat: 기능 추가` 형식
3. **Pull Request**: 코드 리뷰 후 병합
4. **테스트**: 모든 테스트 통과 필수

### 테스트 작성

```python
import pytest
from rfs import Result, Success, Failure

@stateless
class TestUserService:
    @pytest.mark.asyncio
    async def test_get_user_success(self):
        # Given
        user_service = UserService()
        user_id = "test_user"
        
        # When
        result = await user_service.get_user(user_id)
        
        # Then
        assert result.is_success()
        user = result.unwrap()
        assert user.id == user_id
```

## 배포 가이드

### 로컬 테스트

```bash
# 단위 테스트
pytest tests/

# 통합 테스트  
pytest tests/integration/

# 코드 품질 검사
ruff check .
black --check .
mypy .
```

### Cloud Run 배포

```bash
# Docker 빌드
docker build -t gcr.io/project-id/app:latest .

# 이미지 푸시
docker push gcr.io/project-id/app:latest

# Cloud Run 배포
gcloud run deploy app \\
  --image gcr.io/project-id/app:latest \\
  --region asia-northeast3 \\
  --allow-unauthenticated
```

## 아키텍처

### 핵심 원칙

1. **함수형 프로그래밍**: Result 패턴 사용
2. **의존성 주입**: stateless 데코레이터 활용
3. **비동기 처리**: async/await 패턴
4. **타입 안전성**: 강한 타입 힌트

### 모듈 구조

- `core/`: 핵심 기능 (Result, Config, Services)
- `cloud_run/`: Cloud Run 전용 기능
- `cli/`: 명령행 도구
- `reactive/`: 리액티브 스트림
- `events/`: 이벤트 시스템

## 기여 방법

1. **이슈 확인**: GitHub Issues에서 작업할 항목 선택
2. **브랜치 생성**: 기능별 브랜치 생성
3. **개발**: 가이드라인에 따라 코드 작성
4. **테스트**: 충분한 테스트 작성
5. **Pull Request**: 코드 리뷰 요청

## 문제 해결

### 개발 환경 문제

- Python 버전 확인: `python --version`
- 의존성 재설치: `pip install -r requirements.txt --force-reinstall`
- 가상 환경 재생성: `rm -rf venv && python -m venv venv`

### 테스트 실패

- 개별 테스트 실행: `pytest tests/test_specific.py -v`
- 테스트 디버깅: `pytest --pdb`
- 커버리지 확인: `pytest --cov=.`

---

생성일: {current_time}
"""
            dev_guide_file = self.output_path / "developer-guide.md"
            dev_guide_file.write_text(dev_guide_content, encoding="utf-8")
            return Success(str(dev_guide_file))
        except Exception as e:
            return Failure(f"개발자 가이드 생성 실패: {str(e)}")

    async def _generate_index_page(self, generated_docs: Dict[str, str]) -> None:
        """인덱스 페이지 생성"""
        try:
            index_content = f"# {self.config.project_info.get('name', 'Project')} 문서\n\n{self.config.project_info.get('description', '')}\n\n## 문서 목록\n\n"
            for doc_type, doc_path in generated_docs.items():
                doc_name = {
                    "api": "API 참조",
                    "user_guide": "사용자 가이드",
                    "developer_guide": "개발자 가이드",
                    "architecture": "아키텍처 문서",
                    "tutorial": "튜토리얼",
                    "reference": "레퍼런스",
                }.get(doc_type, doc_type.title())
                filename = Path(doc_path).name
                index_content = index_content + f"- [{doc_name}]({filename})\n"
            index_content = (
                index_content
                + f"\n\n## 프로젝트 정보\n\n- **버전**: {self.config.project_info.get('version', '1.0.0')}\n- **작성자**: {self.config.project_info.get('author', 'Unknown')}\n- **생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n이 문서는 RFS v4 문서 생성기로 자동 생성되었습니다.\n"
            )
            index_file = self.output_path / "index.md"
            index_file.write_text(index_content, encoding="utf-8")
            if DocFormat.HTML in self.config.formats:
                html_content = self._markdown_to_html(index_content)
                html_file = self.output_path / "index.html"
                html_file.write_text(html_content, encoding="utf-8")
        except Exception as e:
            if console:
                console.print(f"⚠️  인덱스 페이지 생성 실패: {str(e)}", style="yellow")

    def _markdown_to_html(self, markdown_content: str) -> str:
        """Markdown을 HTML로 변환"""
        try:
            html_template = f"""<!DOCTYPE html>\n<html lang="{self.config.language}">\n<head>\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>{self.config.project_info.get('name', 'Documentation')}</title>\n    <style>\n        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; \n               line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}\n        h1, h2, h3 {{ color: #2563eb; }}\n        code {{ background: #f1f5f9; padding: 2px 4px; border-radius: 4px; }}\n        pre {{ background: #f8fafc; padding: 16px; border-radius: 8px; overflow-x: auto; }}\n        blockquote {{ border-left: 4px solid #e2e8f0; margin: 0; padding: 0 16px; }}\n    </style>\n</head>\n<body>\n    <div id="content">\n        {self._simple_markdown_to_html(markdown_content)}\n    </div>\n</body>\n</html>"""
            return html_template
        except Exception:
            return f"<html><body><pre>{markdown_content}</pre></body></html>"

    def _simple_markdown_to_html(self, text: str) -> str:
        """간단한 Markdown -> HTML 변환"""
        lines = text.split("\n")
        html_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                html_lines = html_lines + ["<br>"]
            elif line.startswith("# "):
                html_lines = html_lines + [f"<h1>{line[2:]}</h1>"]
            elif line.startswith("## "):
                html_lines = html_lines + [f"<h2>{line[3:]}</h2>"]
            elif line.startswith("### "):
                html_lines = html_lines + [f"<h3>{line[4:]}</h3>"]
            elif line.startswith("- "):
                html_lines = html_lines + [f"<li>{line[2:]}</li>"]
            elif line.startswith("```"):
                if line.endswith("```"):
                    html_lines = html_lines + ["<code>"]
                else:
                    html_lines = html_lines + ["<pre><code>"]
            else:
                html_lines = html_lines + [f"<p>{line}</p>"]
        return "\n".join(html_lines)

    async def get_documentation_status(self) -> Dict[str, Any]:
        """문서 생성 상태 조회"""
        try:
            status = {
                "output_directory": str(self.output_path.absolute()),
                "formats": [f.value for f in self.config.formats],
                "project_info": self.config.project_info,
                "generated_files": [],
            }
            if self.output_path.exists():
                for file in self.output_path.glob("*"):
                    if file.is_file():
                        status["generated_files"] = status.get(
                            "generated_files", []
                        ) + [
                            {
                                "name": file.name,
                                "size": file.stat().st_size,
                                "modified": datetime.fromtimestamp(
                                    file.stat().st_mtime
                                ).isoformat(),
                            }
                        ]
            return status
        except Exception as e:
            return {"error": str(e)}
