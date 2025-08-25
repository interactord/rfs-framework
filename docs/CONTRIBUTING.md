# Contributing to RFS Framework

RFS Framework는 오픈소스 프로젝트입니다. 기여를 환영합니다!

## 🚀 시작하기

### 1. 개발 환경 설정

```bash
# 저장소 포크 및 클론
git clone https://github.com/interactord/rfs-framework.git
cd rfs-framework

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 개발용 의존성 설치
pip install -e ".[dev,test,docs]"

# 프리커밋 훅 설정
pre-commit install
```

### 2. 개발 워크플로우

```bash
# 새 브랜치 생성
git checkout -b feature/awesome-feature

# 코드 작성
# ...

# 테스트 실행
pytest tests/

# 코드 품질 검사
black src/
isort src/
mypy src/

# 커밋 및 푸시
git add .
git commit -m "feat: add awesome feature"
git push origin feature/awesome-feature
```

## 📝 기여 가이드라인

### 코드 스타일
- **Python**: PEP 8 준수, Black 포맷터 사용
- **타입 힌트**: 모든 공개 API에 타입 힌트 필수
- **Docstring**: Google 스타일 docstring 사용
- **테스트**: 새로운 기능에 대한 테스트 코드 필수

### 커밋 메시지 규칙
```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
style: 코드 포맷팅
refactor: 코드 리팩토링
test: 테스트 코드 추가/수정
chore: 빌드 프로세스 또는 도구 변경
```

### Pull Request 가이드라인
1. **명확한 제목**: 변경사항을 간결하게 설명
2. **상세한 설명**: 변경 이유와 방법을 설명
3. **테스트 결과**: 모든 테스트가 통과하는지 확인
4. **문서 업데이트**: 필요시 문서 업데이트 포함

## 🧪 테스트

### 단위 테스트
```bash
# 모든 테스트 실행
pytest

# 특정 모듈 테스트
pytest tests/unit/core/

# 커버리지 확인
pytest --cov=rfs --cov-report=html
```

### 통합 테스트
```bash
# 통합 테스트 실행
pytest tests/integration/

# 성능 테스트
pytest tests/performance/
```

## 📖 문서화

### Wiki 문서
- 모든 새로운 기능은 wiki 문서 업데이트 필요
- `wiki/` 디렉토리의 적절한 파일에 추가
- 한국어로 작성, 예제 코드 포함

### API 문서
- Docstring은 Google 스타일 사용
- 매개변수, 반환값, 예외 상황 모두 문서화
- 사용 예제 포함 권장

## 🐛 버그 리포트

버그를 발견하시면 GitHub Issues에 다음 정보와 함께 리포트해 주세요:

### 버그 리포트 템플릿
```markdown
**환경 정보**
- Python 버전:
- RFS Framework 버전:
- 운영체제:

**버그 설명**
버그에 대한 명확하고 간결한 설명

**재현 단계**
1. '...'로 이동
2. '...'를 클릭
3. '...'까지 스크롤
4. 오류 발생

**예상 동작**
예상했던 동작에 대한 명확하고 간결한 설명

**실제 동작**
실제 발생한 동작에 대한 설명

**스크린샷**
해당되는 경우 스크린샷을 첨부

**추가 컨텍스트**
이 문제에 대한 기타 컨텍스트를 여기에 추가
```

## 🎯 기여 영역

### 우선순위 높음
- 버그 수정
- 성능 개선
- 테스트 커버리지 향상
- 문서화 개선

### 환영하는 기여
- 새로운 기능 추가
- 예제 코드 개선
- 튜토리얼 작성
- 번역 작업

### 개발 중인 기능
현재 개발 중인 기능은 [TODO.md](./TODO.md)를 참조하세요.

## 📞 연락처

질문이나 제안사항이 있으시면 언제든지 연락해 주세요:

- **GitHub Issues**: 버그 리포트, 기능 요청
- **Discord**: 실시간 토론 및 질의응답
- **Email**: support@rfs-framework.dev

## 📄 라이선스

기여하신 코드는 프로젝트의 MIT 라이선스 하에 배포됩니다.

---

**RFS Framework 팀과 함께 더 나은 프레임워크를 만들어 나가요! 🚀**