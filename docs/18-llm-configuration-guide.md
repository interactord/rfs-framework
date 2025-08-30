# LLM Configuration Guide

RFS Framework의 LLM 모듈 설정 가이드입니다.

## 개요

LLM 모듈은 다양한 LLM Provider들을 통합 관리하기 위한 설정 시스템을 제공합니다. 환경 변수, 설정 파일, 코드를 통한 설정을 지원하며, 각 Provider별 세부 설정이 가능합니다.

## 지원 Provider

- **OpenAI**: GPT-4, GPT-3.5-turbo 등
- **Anthropic**: Claude 3 시리즈
- **Google Gemini**: Gemini 1.5 Pro/Flash
- **AWS Bedrock**: Claude, Llama, Titan 모델

## 기본 설정

### 환경 변수 설정

```bash
# 기본 Provider 설정
export LLM_DEFAULT_PROVIDER=openai
export LLM_ENABLED_PROVIDERS=openai,anthropic,gemini

# OpenAI 설정
export OPENAI_API_KEY=sk-your-openai-key
export OPENAI_ORGANIZATION=org-your-org-id

# Anthropic 설정  
export ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Google Gemini 설정
export GOOGLE_API_KEY=your-google-api-key
export GOOGLE_CLOUD_PROJECT=your-project-id

# AWS Bedrock 설정 (API Key 방식)
export AWS_BEDROCK_API_KEY=your-bedrock-bearer-token
export AWS_REGION=us-east-1

# 또는 기존 AWS 자격 증명 방식
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Python 코드 설정

```python
from rfs.llm import configure_llm_settings, create_llm_manager_from_config

# 프로그래매틱 설정
settings = configure_llm_settings(
    default_provider="openai",
    enabled_providers=["openai", "anthropic"],
    openai={
        "api_key": "sk-your-key",
        "default_model": "gpt-4"
    },
    anthropic={
        "api_key": "sk-ant-your-key",
        "default_model": "claude-3-haiku-20240307"
    }
)

# 설정 기반 Manager 생성
manager_result = create_llm_manager_from_config()
if manager_result.is_success():
    manager = manager_result.unwrap()
    print(f"등록된 Provider: {manager.list_providers()}")
```

## Provider별 상세 설정

### OpenAI Provider

```python
from rfs.llm.config import OpenAIProviderConfig

openai_config = OpenAIProviderConfig(
    api_key="sk-your-openai-key",
    organization="org-your-org-id",
    base_url="https://api.openai.com/v1",  # 커스텀 엔드포인트
    timeout=30,
    max_retries=3,
    default_model="gpt-4"
)
```

### Anthropic Provider

```python
from rfs.llm.config import AnthropicProviderConfig

anthropic_config = AnthropicProviderConfig(
    api_key="sk-ant-your-anthropic-key",
    base_url="https://api.anthropic.com",
    timeout=30,
    max_retries=3,
    default_model="claude-3-haiku-20240307"
)
```

### Google Gemini Provider

```python
from rfs.llm.config import GeminiProviderConfig

# API Key 방식 (직접 Gemini API)
gemini_config = GeminiProviderConfig(
    api_key="your-google-api-key",
    use_vertex=False,
    default_model="gemini-1.5-flash"
)

# Vertex AI 방식
gemini_vertex_config = GeminiProviderConfig(
    project="your-gcp-project-id",
    location="us-central1", 
    use_vertex=True,
    default_model="gemini-1.5-pro"
)
```

### AWS Bedrock Provider

```python
from rfs.llm.config import BedrockProviderConfig

# Bearer Token API Key 방식 (새로운 방식)
bedrock_config = BedrockProviderConfig(
    api_key="your-bedrock-bearer-token",
    region="us-east-1",
    default_model="anthropic.claude-3-haiku-20240307-v1:0"
)

# 기존 AWS 자격 증명 방식
bedrock_legacy_config = BedrockProviderConfig(
    aws_access_key="your-access-key",
    aws_secret_key="your-secret-key", 
    region="us-east-1",
    default_model="anthropic.claude-3-sonnet-20240229-v1:0"
)
```

## RAG 시스템 설정

```python
from rfs.llm.config import RAGConfig

rag_config = RAGConfig(
    vector_store_type="chroma",
    chunk_size=1000,
    chunk_overlap=200,
    embedding_model="text-embedding-ada-002",
    similarity_threshold=0.7,
    max_results=5,
    
    # ChromaDB 설정
    chroma_persist_directory="./vector_db",
    chroma_collection_name="documents"
)
```

## 통합 설정 클래스

```python
from rfs.llm.config import LLMSettings

settings = LLMSettings(
    enabled_providers=["openai", "anthropic", "gemini"],
    default_provider="openai",
    
    openai=OpenAIProviderConfig(api_key="sk-your-key"),
    anthropic=AnthropicProviderConfig(api_key="sk-ant-your-key"),
    gemini=GeminiProviderConfig(api_key="your-google-key"),
    
    rag=RAGConfig(vector_store_type="memory"),
    
    # 모니터링 설정
    enable_monitoring=True,
    enable_caching=True,
    cache_ttl=3600,
    
    # 로깅 설정
    log_requests=False,  # 운영 환경에서는 False
    log_responses=False
)
```

## 사용 예시

### 기본 사용법

```python
from rfs.llm import create_llm_manager_from_config

# 환경 변수에서 설정 자동 로드
manager_result = create_llm_manager_from_config()

if manager_result.is_success():
    manager = manager_result.unwrap()
    
    # 기본 Provider로 텍스트 생성
    result = await manager.generate(
        prompt="Hello, world!",
        model="gpt-3.5-turbo"
    )
    
    if result.is_success():
        print(f"응답: {result.unwrap()}")
else:
    print(f"Manager 생성 실패: {manager_result.unwrap_error()}")
```

### 다중 Provider 사용

```python
# 여러 Provider 동시 사용
result = await manager.create_multi_provider_pipeline(
    providers=["openai", "anthropic"],
    model="default"
)("Explain quantum computing")

if result.is_success():
    responses = result.unwrap()
    print(f"OpenAI: {responses['openai']}")
    print(f"Anthropic: {responses['anthropic']}")
```

### HOF 패턴 사용

```python
from rfs.hof.core import pipe

# 파이프라인 생성
qa_pipeline = pipe(
    manager.create_generation_pipeline("openai", "gpt-3.5-turbo"),
    lambda response: f"답변: {response.unwrap()}" if response.is_success() else "오류 발생"
)

# 사용
result = await qa_pipeline("Python의 장점은 무엇인가요?")
print(result)
```

## 설정 검증 및 디버깅

### 설정 상태 확인

```python
# 현재 설정 확인
settings_info = manager.get_settings_info()
print(f"설정 정보: {settings_info}")

# 등록된 Provider 확인
providers = manager.list_providers()
print(f"등록된 Provider: {providers}")

# Provider별 정보 확인
all_info = manager.get_all_provider_info()
print(f"모든 Provider 정보: {all_info}")
```

### 사용 가능한 모델 확인

```python
from rfs.llm import get_available_models, get_model_info

# 모든 사용 가능한 모델
all_models = get_available_models()
print(f"전체 모델 수: {len(all_models)}")

# 특정 Provider 모델
openai_models = get_available_models(LLMProviderType.OPENAI)
print(f"OpenAI 모델: {[m.name for m in openai_models]}")

# 특정 모델 정보
model_info = get_model_info("gpt-4")
if model_info:
    print(f"GPT-4 정보: {model_info}")
```

## 보안 고려사항

### API 키 관리

- **환경 변수 사용**: API 키는 반드시 환경 변수로 관리
- **코드에 하드코딩 금지**: 소스 코드에 API 키 포함 금지
- **권한 최소화**: 필요한 최소 권한만 부여
- **정기적 로테이션**: API 키 정기적 교체

### 로깅 설정

```python
# 운영 환경에서는 민감한 정보 로깅 비활성화
settings = LLMSettings(
    log_requests=False,    # 요청 데이터에 민감 정보 포함 가능
    log_responses=False,   # 응답 데이터에 민감 정보 포함 가능
    enable_monitoring=True # 성능 메트릭만 수집
)
```

## 성능 최적화

### 캐싱 설정

```python
settings = LLMSettings(
    enable_caching=True,
    cache_ttl=3600,  # 1시간 캐시
)
```

### 연결 풀링

```python
# Provider별 연결 설정
openai_config = OpenAIProviderConfig(
    timeout=30,
    max_retries=3
)
```

## 환경별 설정

### 개발 환경

```python
# 개발 환경 설정
dev_settings = LLMSettings(
    enabled_providers=["openai"],
    default_provider="openai", 
    log_requests=True,   # 개발 중 디버깅용
    log_responses=True,
    enable_caching=False # 개발 중에는 캐시 비활성화
)
```

### 운영 환경

```python
# 운영 환경 설정
prod_settings = LLMSettings(
    enabled_providers=["openai", "anthropic", "bedrock"],
    default_provider="anthropic",  # 안정성 우선
    log_requests=False,
    log_responses=False,
    enable_caching=True,
    enable_monitoring=True
)
```

## 문제 해결

### 일반적인 설정 오류

1. **Provider 등록 실패**
   - API 키 확인
   - SDK 설치 여부 확인
   - 네트워크 연결 상태 확인

2. **인증 오류**
   - API 키 유효성 확인
   - 권한 설정 확인
   - 사용량 한도 확인

3. **모델 사용 불가**
   - 모델명 정확성 확인
   - Provider별 지원 모델 확인
   - 계정 접근 권한 확인

### 디버깅 팁

```python
# 상세 오류 정보 확인
try:
    manager = create_llm_manager_from_config().unwrap()
except Exception as e:
    print(f"상세 오류: {e}")
    import traceback
    traceback.print_exc()

# Provider별 연결 테스트
for provider_name in manager.list_providers():
    result = await manager.generate(
        prompt="test",
        model="default",
        provider=provider_name
    )
    print(f"{provider_name}: {'성공' if result.is_success() else result.unwrap_error()}")
```

이 가이드를 통해 RFS Framework의 LLM 모듈을 효과적으로 설정하고 사용할 수 있습니다.