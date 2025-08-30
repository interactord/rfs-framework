# MkDocs 문서 배포 가이드

RFS Framework 문서는 MkDocs와 GitHub Pages를 사용하여 자동 배포됩니다.

## 배포 설정

### 1. 환경 구성

- **플랫폼**: GitHub Pages
- **빌드 도구**: MkDocs with Material Theme
- **CI/CD**: GitHub Actions
- **자동 배포**: main 브랜치에 docs 변경사항 푸시 시

### 2. MkDocs 설정

```yaml
# mkdocs.yml 주요 설정
site_name: RFS Framework
site_url: https://interactord.github.io/rfs-framework/
theme:
  name: material
  language: ko
```

### 3. GitHub Actions 워크플로우

문서는 `.github/workflows/deploy-docs.yml`를 통해 자동 배포됩니다:

- **트리거**: main 브랜치의 docs 폴더 변경
- **빌드**: Python 3.11 환경에서 MkDocs 빌드
- **배포**: GitHub Pages로 자동 배포

## 로컬 개발

### 설치

```bash
pip install mkdocs mkdocs-material
pip install mkdocstrings[python]
pip install mkdocs-mermaid2-plugin
pip install mkdocs-awesome-pages-plugin
pip install mkdocs-git-revision-date-localized-plugin
pip install mkdocs-git-committers-plugin-2
pip install mkdocs-minify-plugin
```

### 로컬 서버 실행

```bash
# 개발 서버 시작
mkdocs serve

# 특정 주소와 포트로 시작
mkdocs serve --dev-addr=127.0.0.1:8000

# 문서 빌드
mkdocs build

# 정리 후 빌드
mkdocs build --clean
```

## 문서 구조

```
docs/
├── index.md                    # 메인 페이지
├── getting-started.md          # 시작하기
├── installation.md             # 설치 가이드
├── changelog.md                # 변경 이력
├── 01-core-patterns.md         # 핵심 개념
├── ...                         # 기타 가이드 문서
├── api/                        # API 레퍼런스
│   ├── core/                   # 코어 모듈
│   ├── reactive/               # 리액티브 모듈
│   ├── llm/                    # LLM 모듈 (새로 추가)
│   └── ...
└── assets/                     # 정적 파일
```

## 새로운 문서 추가

### 1. 문서 파일 생성

```bash
# docs 폴더에 마크다운 파일 생성
touch docs/새로운-기능.md
```

### 2. mkdocs.yml 네비게이션 업데이트

```yaml
nav:
  - 홈:
    - index.md
    - 새로운 기능: 새로운-기능.md  # 추가
```

### 3. 변경사항 커밋 및 푸시

```bash
git add docs/새로운-기능.md mkdocs.yml
git commit -m "docs: 새로운 기능 문서 추가"
git push origin main
```

## 플러그인 설정

### 사용 중인 플러그인

1. **mkdocstrings**: Python API 자동 문서화
2. **mermaid2**: 다이어그램 지원
3. **git-revision-date-localized**: 마지막 수정 날짜
4. **git-committers**: 기여자 정보
5. **minify**: HTML/CSS/JS 압축
6. **awesome-pages**: 페이지 구성 자동화

### 설정 예시

```yaml
plugins:
  - search
  - minify
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
```

## 문제 해결

### 빌드 에러

```bash
# 엄격 모드로 빌드하여 문제 확인
mkdocs build --strict

# 상세 로그로 빌드
mkdocs build --verbose
```

### 링크 문제

- 상대 경로 사용: `../other-page.md`
- 앵커 링크: `page.md#section`
- API 링크: `::: module.function`

### 플러그인 문제

```bash
# 플러그인 재설치
pip install --upgrade mkdocs-material

# 의존성 확인
pip list | grep mkdocs
```

## 배포 URL

- **메인 사이트**: https://interactord.github.io/rfs-framework/
- **개발 서버**: http://127.0.0.1:8000/ (로컬)

## 모니터링

GitHub Actions의 "Deploy Documentation" 워크플로우를 통해 배포 상태를 확인할 수 있습니다:

1. GitHub 저장소 → Actions 탭
2. "Deploy Documentation" 워크플로우 선택
3. 최근 실행 결과 확인