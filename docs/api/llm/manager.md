# LLM Manager

RFS Framework의 LLM Manager는 여러 LLM Provider를 통합적으로 관리하고 사용할 수 있는 중앙 관리자입니다.

!!! info "구현 상태"
    LLM Manager는 v4.5.0에서 추가된 새로운 기능입니다. 상세한 API 문서는 구현 완료 후 업데이트됩니다.

## 기본 사용법

### Manager 생성

```python
from rfs.llm.manager import LLMManager
from rfs.llm.providers.openai import OpenAIProvider

# 기본 Manager 생성
manager = LLMManager()

# Provider 추가
openai_provider = OpenAIProvider(api_key="your-api-key")
manager.add_provider("openai", openai_provider, default=True)
```

### 설정 기반 Manager 생성

```python
from rfs.llm import create_llm_manager_from_config

# 환경 변수와 설정을 기반으로 자동 생성
manager_result = create_llm_manager_from_config()

if manager_result.is_success():
    manager = manager_result.unwrap()
    # Manager 사용
else:
    error = manager_result.unwrap_error()
    print(f"Manager 생성 실패: {error}")
```

### 텍스트 생성

```python
# 기본 Provider로 텍스트 생성
result = await manager.generate("Hello, world!")

if result.is_success():
    response = result.unwrap()
    print(response)
else:
    error = result.unwrap_error()
    print(f"생성 실패: {error}")
```

### 특정 Provider 사용

```python
# 특정 Provider와 모델 지정
result = await manager.generate(
    "Explain quantum computing",
    model="gpt-4",
    provider="openai"
)

if result.is_success():
    response = result.unwrap()
    print(response)
```

### 임베딩 생성

```python
# 텍스트 임베딩 생성
embedding_result = await manager.embed("This is a test text")

if embedding_result.is_success():
    embeddings = embedding_result.unwrap()
    print(f"임베딩 차원: {len(embeddings)}")
```

## Manager 상태 관리

### Provider 목록 조회

```python
# 등록된 Provider 목록
providers = manager.list_providers()
print(f"등록된 Provider: {providers}")

# 기본 Provider 확인
default_provider = manager.get_default_provider_name()
print(f"기본 Provider: {default_provider}")
```

### 자동 구성

```python
# 환경 변수 기반 자동 구성
result = manager.auto_configure_from_settings()

if result.is_success():
    print("자동 구성 완료")
    providers = manager.list_providers()
    print(f"구성된 Provider: {providers}")
```

### 설정 정보 조회

```python
# 현재 설정 정보 조회
settings_info = manager.get_settings_info()
print(f"설정 정보: {settings_info}")

# 구성된 Provider 정보
configured_providers = manager.get_configured_providers()
print(f"구성된 Provider: {configured_providers}")
```

## 고급 사용법

### 토큰 수 계산

```python
# 텍스트의 토큰 수 계산
token_result = await manager.get_token_count("This is a test message")

if token_result.is_success():
    token_count = token_result.unwrap()
    print(f"토큰 수: {token_count}")
```

### Provider 선택 전략

Manager는 다음 순서로 Provider를 선택합니다:

1. 명시적으로 지정된 `provider` 매개변수
2. 설정된 기본 Provider
3. 등록된 첫 번째 Provider

### 에러 처리

모든 Manager 메서드는 `Result` 패턴을 사용합니다:

```python
from rfs.core.result import Result

result = await manager.generate("test")

# 성공/실패 확인
if result.is_success():
    response = result.unwrap()
    # 성공 처리
elif result.is_failure():
    error = result.unwrap_error()
    # 에러 처리
```

## 설정 기반 사용

환경 변수와 설정 파일을 통한 자동 구성이 가능합니다:

```bash
# OpenAI
export OPENAI_API_KEY=your-openai-key

# Anthropic
export ANTHROPIC_API_KEY=your-anthropic-key

# Google Gemini
export GOOGLE_API_KEY=your-google-key

# AWS Bedrock
export AWS_BEDROCK_API_KEY=your-bedrock-token
```

자세한 설정 방법은 [LLM 설정 가이드](../../18-llm-configuration-guide.md)를 참조하세요.