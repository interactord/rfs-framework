# LLM Configuration

RFS Framework의 LLM 설정 시스템은 환경 변수, 설정 파일, 코드를 통한 동적 구성을 지원합니다.

!!! info "구현 상태"
    LLM Configuration은 v4.5.0에서 추가된 새로운 기능입니다. 상세한 API 문서는 구현 완료 후 업데이트됩니다.

## Provider 설정 클래스

### OpenAI Provider 설정

```python
from rfs.llm.config import OpenAIProviderConfig

config = OpenAIProviderConfig(
    api_key="your-openai-api-key",
    default_model="gpt-4",
    max_tokens=2000,
    temperature=0.7
)
```

### Anthropic Provider 설정

```python
from rfs.llm.config import AnthropicProviderConfig

config = AnthropicProviderConfig(
    api_key="your-anthropic-api-key",
    default_model="claude-3-opus-20240229",
    max_tokens=4000
)
```

### Google Gemini Provider 설정

```python
from rfs.llm.config import GeminiProviderConfig

# API Key 모드
api_config = GeminiProviderConfig(
    api_key="your-google-api-key",
    use_vertex=False,
    default_model="gemini-1.5-pro"
)

# Vertex AI 모드
vertex_config = GeminiProviderConfig(
    project="your-project-id",
    location="us-central1",
    use_vertex=True,
    default_model="gemini-1.5-pro"
)
```

### AWS Bedrock Provider 설정

```python
from rfs.llm.config import BedrockProviderConfig

# Bearer Token 방식
token_config = BedrockProviderConfig(
    api_key="your-bearer-token",
    region="us-east-1",
    default_model="anthropic.claude-3-haiku-20240307-v1:0"
)

# AWS 자격 증명 방식
credential_config = BedrockProviderConfig(
    aws_access_key="your-access-key",
    aws_secret_key="your-secret-key",
    region="us-west-2",
    default_model="anthropic.claude-3-sonnet-20240229-v1:0"
)
```

## RAG 설정

```python
from rfs.llm.config import RAGConfig

rag_config = RAGConfig(
    vector_store_type="chroma",
    chunk_size=1000,
    chunk_overlap=200,
    similarity_threshold=0.7,
    max_results=5
)
```

## LLM Provider 타입

```python
from rfs.llm.config import LLMProviderType

# Provider 타입 사용
print(LLMProviderType.OPENAI)     # "openai"
print(LLMProviderType.ANTHROPIC)  # "anthropic"
print(LLMProviderType.GEMINI)     # "gemini"
print(LLMProviderType.BEDROCK)    # "bedrock"
```

## 모델 정보 조회

```python
from rfs.llm.config import get_available_models, get_model_info, LLMProviderType

# 전체 모델 목록
all_models = get_available_models()
print(f"사용 가능한 모델 수: {len(all_models)}")

# 특정 Provider 모델 목록
openai_models = get_available_models(LLMProviderType.OPENAI)
print(f"OpenAI 모델: {[model.name for model in openai_models]}")

# 특정 모델 정보
gpt4_info = get_model_info("gpt-4")
if gpt4_info:
    print(f"모델명: {gpt4_info.name}")
    print(f"Provider: {gpt4_info.provider}")
    print(f"최대 토큰: {gpt4_info.max_tokens}")
```

## 환경 변수 기반 설정

### 기본 환경 변수

```bash
# OpenAI
export OPENAI_API_KEY="your-openai-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Google Gemini
export GOOGLE_API_KEY="your-google-api-key"

# AWS Bedrock (새로운 방식)
export AWS_BEDROCK_API_KEY="your-bearer-token"

# AWS Bedrock (기존 방식)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### 설정 옵션 환경 변수

```bash
# 기본 Provider 설정
export RFS_LLM_DEFAULT_PROVIDER="openai"

# 활성화할 Provider 목록
export RFS_LLM_ENABLED_PROVIDERS="openai,anthropic,gemini"

# 모니터링 설정
export RFS_LLM_ENABLE_MONITORING="true"

# 로깅 설정
export RFS_LLM_LOG_LEVEL="INFO"
```

## 설정 파일 기반 구성

### YAML 설정 파일

```yaml
# config/llm.yaml
llm:
  default_provider: "openai"
  enabled_providers:
    - "openai"
    - "anthropic"
    - "gemini"
  
  providers:
    openai:
      default_model: "gpt-4"
      max_tokens: 2000
      temperature: 0.7
    
    anthropic:
      default_model: "claude-3-opus-20240229"
      max_tokens: 4000
    
    gemini:
      use_vertex: false
      default_model: "gemini-1.5-pro"
    
    bedrock:
      region: "us-east-1"
      default_model: "anthropic.claude-3-haiku-20240307-v1:0"
  
  rag:
    vector_store_type: "chroma"
    chunk_size: 1000
    chunk_overlap: 200
    similarity_threshold: 0.7
```

### JSON 설정 파일

```json
{
  "llm": {
    "default_provider": "openai",
    "enabled_providers": ["openai", "anthropic"],
    "providers": {
      "openai": {
        "default_model": "gpt-4",
        "max_tokens": 2000,
        "temperature": 0.7
      },
      "anthropic": {
        "default_model": "claude-3-opus-20240229",
        "max_tokens": 4000
      }
    }
  }
}
```

## 동적 설정 구성

### 코드를 통한 설정 업데이트

```python
from rfs.llm.config import configure_llm_settings

# 런타임에 설정 업데이트
settings = configure_llm_settings(
    default_provider="anthropic",
    enabled_providers=["openai", "anthropic", "gemini"],
    enable_monitoring=True
)

print(f"업데이트된 설정: {settings}")
```

### 조건부 설정

```python
from rfs.llm.config import get_llm_settings, configure_llm_settings
import os

# 환경에 따른 조건부 설정
if os.getenv("ENV") == "production":
    settings = configure_llm_settings(
        default_provider="bedrock",  # 프로덕션에서는 Bedrock 사용
        enabled_providers=["bedrock"],
        enable_monitoring=True,
        log_level="WARNING"
    )
else:
    settings = configure_llm_settings(
        default_provider="openai",   # 개발에서는 OpenAI 사용
        enabled_providers=["openai", "anthropic"],
        enable_monitoring=False,
        log_level="DEBUG"
    )
```

## 자동 Manager 생성

### 기본 자동 생성

```python
from rfs.llm import create_llm_manager_from_config

# 환경 변수와 설정을 기반으로 자동 생성
manager_result = create_llm_manager_from_config()

if manager_result.is_success():
    manager = manager_result.unwrap()
    
    # 사용 가능한 Provider 확인
    providers = manager.list_providers()
    print(f"구성된 Provider: {providers}")
    
    # 텍스트 생성 테스트
    result = await manager.generate("Hello, world!")
    if result.is_success():
        print(f"응답: {result.unwrap()}")
else:
    error = manager_result.unwrap_error()
    print(f"Manager 생성 실패: {error}")
```

### 커스텀 설정으로 자동 생성

```python
from rfs.llm import create_llm_manager_from_config
from rfs.llm.config import configure_llm_settings

# 먼저 설정 업데이트
configure_llm_settings(
    default_provider="gemini",
    enabled_providers=["gemini", "openai"],
    enable_monitoring=True
)

# 업데이트된 설정으로 Manager 생성
manager_result = create_llm_manager_from_config()

if manager_result.is_success():
    manager = manager_result.unwrap()
    
    # Gemini가 기본 Provider로 설정됨
    result = await manager.generate("Explain AI")
    if result.is_success():
        print(f"Gemini 응답: {result.unwrap()}")
```

## 설정 검증

### API 키 유효성 검사

```python
from rfs.llm.config import validate_provider_config

# Provider 설정 검증
openai_valid = validate_provider_config("openai")
if openai_valid:
    print("OpenAI 설정이 유효합니다")
else:
    print("OpenAI API 키를 확인하세요")

# 전체 설정 검증
all_valid = validate_all_provider_configs()
print(f"유효한 Provider 수: {len(all_valid)}")
```

### 설정 상태 조회

```python
from rfs.llm.config import get_configuration_status

# 현재 설정 상태 확인
status = get_configuration_status()
print(f"설정 상태: {status}")

# {
#   "default_provider": "openai",
#   "available_providers": ["openai", "anthropic"],
#   "missing_keys": ["GOOGLE_API_KEY"],
#   "configuration_complete": false
# }
```

## 문제 해결

### 일반적인 설정 문제

1. **API 키 누락**
   ```bash
   # 환경 변수 설정 확인
   echo $OPENAI_API_KEY
   ```

2. **Provider 초기화 실패**
   ```python
   from rfs.llm.config import debug_provider_initialization
   
   debug_info = debug_provider_initialization("openai")
   print(debug_info)
   ```

3. **설정 충돌**
   ```python
   from rfs.llm.config import reset_llm_settings
   
   # 설정 초기화
   reset_llm_settings()
   
   # 새로운 설정 적용
   configure_llm_settings(default_provider="openai")
   ```

### 디버깅 도구

```python
from rfs.llm.config import get_debug_info

# 전체 설정 정보 출력
debug_info = get_debug_info()
print(f"디버그 정보: {debug_info}")

# 특정 Provider 디버그
provider_debug = get_debug_info("openai")
print(f"OpenAI 디버그: {provider_debug}")
```