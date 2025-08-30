# LLM Providers

RFS Framework는 다양한 LLM Provider를 지원합니다. 각 Provider는 공통 인터페이스를 구현하여 일관된 방식으로 사용할 수 있습니다.

!!! info "구현 상태"
    LLM Provider들은 v4.5.0에서 추가된 새로운 기능입니다. 상세한 API 문서는 구현 완료 후 업데이트됩니다.

## 지원되는 Provider

### 1. OpenAI Provider

#### 사용법

```python
from rfs.llm.providers.openai import OpenAIProvider

# API 키로 초기화
provider = OpenAIProvider(api_key="your-openai-api-key")

# 텍스트 생성
result = await provider.generate(
    "Explain machine learning", 
    model="gpt-4"
)

if result.is_success():
    response = result.unwrap()
    print(response)
```

#### 지원 모델
- `gpt-4`: GPT-4 모델
- `gpt-4-turbo`: GPT-4 Turbo 모델
- `gpt-3.5-turbo`: GPT-3.5 Turbo 모델

### 2. Anthropic Provider

#### 사용법

```python
from rfs.llm.providers.anthropic import AnthropicProvider

# API 키로 초기화
provider = AnthropicProvider(api_key="your-anthropic-api-key")

# 텍스트 생성
result = await provider.generate(
    "Write a poem about technology", 
    model="claude-3-opus-20240229"
)

if result.is_success():
    response = result.unwrap()
    print(response)
```

#### 지원 모델
- `claude-3-opus-20240229`: Claude 3 Opus
- `claude-3-sonnet-20240229`: Claude 3 Sonnet
- `claude-3-haiku-20240307`: Claude 3 Haiku

### 3. Google Gemini Provider

#### 사용법

```python
from rfs.llm.providers.gemini import GeminiProvider

# API 키 모드
provider = GeminiProvider(
    api_key="your-google-api-key",
    use_vertex=False
)

# Vertex AI 모드
vertex_provider = GeminiProvider(
    project="your-project-id",
    location="us-central1",
    use_vertex=True
)

# 텍스트 생성
result = await provider.generate(
    "Describe the benefits of renewable energy", 
    model="gemini-1.5-pro"
)

if result.is_success():
    response = result.unwrap()
    print(response)
```

#### 지원 모델
- `gemini-1.5-pro`: Gemini 1.5 Pro
- `gemini-1.5-flash`: Gemini 1.5 Flash
- `gemini-pro`: Gemini Pro

#### 설정 옵션
- **API Key 모드**: 직접 Google AI API 사용
- **Vertex AI 모드**: Google Cloud Vertex AI 사용

### 4. AWS Bedrock Provider

#### 사용법

```python
from rfs.llm.providers.bedrock import BedrockProvider

# Bearer Token 방식 (새로운 방식)
provider = BedrockProvider(
    api_key="your-bearer-token",
    region="us-east-1"
)

# 기존 AWS 자격 증명 방식
aws_provider = BedrockProvider(
    aws_access_key="your-access-key",
    aws_secret_key="your-secret-key",
    region="us-west-2"
)

# 텍스트 생성
result = await provider.generate(
    "Explain cloud computing architecture", 
    model="anthropic.claude-3-haiku-20240307-v1:0"
)

if result.is_success():
    response = result.unwrap()
    print(response)
```

#### 지원 모델
- `anthropic.claude-3-opus-20240229-v1:0`: Claude 3 Opus
- `anthropic.claude-3-sonnet-20240229-v1:0`: Claude 3 Sonnet
- `anthropic.claude-3-haiku-20240307-v1:0`: Claude 3 Haiku
- `meta.llama2-70b-chat-v1`: Llama 2 70B Chat
- `amazon.titan-text-express-v1`: Titan Text Express

#### 인증 방식
- **Bearer Token 방식**: 새로운 API 키 기반 인증
- **AWS 자격 증명 방식**: 기존 Access Key/Secret Key 방식

## 공통 Provider 인터페이스

모든 Provider는 다음 메서드를 구현합니다:

### 공통 메서드

#### `generate(prompt, model, **kwargs)`
- **목적**: 텍스트 생성
- **반환**: `Result[str, str]`
- **매개변수**:
  - `prompt`: 입력 텍스트
  - `model`: 사용할 모델명
  - `**kwargs`: Provider별 추가 옵션

#### `embed(text, model=None, **kwargs)`
- **목적**: 텍스트 임베딩 생성
- **반환**: `Result[List[float], str]`
- **매개변수**:
  - `text`: 임베딩할 텍스트
  - `model`: 임베딩 모델명 (선택사항)

#### `get_token_count(text, model=None, **kwargs)`
- **목적**: 토큰 수 계산
- **반환**: `Result[int, str]`
- **매개변수**:
  - `text`: 계산할 텍스트
  - `model`: 모델명 (선택사항)

#### `is_available()`
- **목적**: Provider 사용 가능 여부 확인
- **반환**: `bool`

#### `get_available_models()`
- **목적**: 지원 모델 목록 조회
- **반환**: `List[str]`

## Provider 선택 가이드

### 성능 기준

| Provider | 응답 속도 | 품질 | 비용 | 지원 언어 |
|----------|---------|------|------|----------|
| OpenAI   | 빠름    | 높음 | 중간 | 다국어    |
| Anthropic| 빠름    | 높음 | 중간 | 영어 중심 |
| Gemini   | 매우빠름 | 높음 | 저렴 | 다국어    |
| Bedrock  | 보통    | 높음 | 변동 | 모델별    |

### 용도별 추천

- **일반적인 텍스트 생성**: OpenAI GPT-4
- **대화형 AI**: Anthropic Claude-3
- **빠른 응답 필요**: Google Gemini Flash
- **기업 환경**: AWS Bedrock (규정 준수)
- **비용 절약**: Google Gemini Pro

## 에러 처리

모든 Provider 메서드는 `Result` 패턴을 사용합니다:

```python
result = await provider.generate("test prompt")

if result.is_success():
    response = result.unwrap()
    # 성공 처리
elif result.is_failure():
    error = result.unwrap_error()
    # 에러 유형별 처리
    if "API key" in error:
        # 인증 에러 처리
    elif "rate limit" in error:
        # 속도 제한 에러 처리
    else:
        # 기타 에러 처리
```

## 커스텀 Provider 개발

새로운 Provider를 개발하려면 `BaseLLMProvider`를 상속받아 구현하세요:

```python
from rfs.llm.providers.base import BaseLLMProvider
from rfs.core.result import Result, Success, Failure

class CustomProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def generate(self, prompt: str, model: str, **kwargs) -> Result[str, str]:
        try:
            # 실제 API 호출 로직
            response = await self._call_api(prompt, model)
            return Success(response)
        except Exception as e:
            return Failure(f"생성 실패: {str(e)}")
    
    async def embed(self, text: str, model=None, **kwargs) -> Result[list[float], str]:
        # 임베딩 구현
        pass
    
    async def get_token_count(self, text: str, model=None, **kwargs) -> Result[int, str]:
        # 토큰 수 계산 구현
        pass
    
    def is_available(self) -> bool:
        # 사용 가능 여부 확인
        return bool(self.api_key)
    
    def get_available_models(self) -> list[str]:
        # 지원 모델 목록 반환
        return ["custom-model-1", "custom-model-2"]
```