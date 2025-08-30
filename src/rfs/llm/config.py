"""
LLM Configuration Management

LLM Provider들에 대한 설정 관리
"""

from enum import Enum
from typing import Dict, Optional, List, Any
from pathlib import Path

try:
    from pydantic import BaseModel, Field, validator
    from rfs.core.config import RFSBaseSettings
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = dict
    RFSBaseSettings = dict
    Field = lambda default=None, **kwargs: default
    PYDANTIC_AVAILABLE = False


class LLMProviderType(str, Enum):
    """LLM Provider 타입"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    GEMINI = "gemini"
    BEDROCK = "bedrock"


class LLMModel(BaseModel):
    """LLM 모델 설정"""
    name: str = Field(description="모델 이름")
    provider: LLMProviderType = Field(description="Provider 타입")
    max_tokens: Optional[int] = Field(default=None, description="최대 토큰 수")
    temperature: Optional[float] = Field(default=0.7, description="Temperature 설정")
    supports_streaming: bool = Field(default=False, description="스트리밍 지원 여부")
    supports_function_calling: bool = Field(default=False, description="함수 호출 지원 여부")
    supports_vision: bool = Field(default=False, description="비전 모델 지원 여부")


if PYDANTIC_AVAILABLE:
    class OpenAIProviderConfig(BaseModel):
        """OpenAI Provider 설정"""
        api_key: Optional[str] = Field(default=None, description="OpenAI API Key")
        organization: Optional[str] = Field(default=None, description="Organization ID")
        base_url: Optional[str] = Field(default=None, description="Base URL")
        timeout: int = Field(default=30, description="Timeout (초)")
        max_retries: int = Field(default=3, description="최대 재시도 횟수")
        default_model: str = Field(default="gpt-3.5-turbo", description="기본 모델")
        
        @validator('api_key')
        def validate_api_key(cls, v):
            if v and not v.startswith('sk-'):
                raise ValueError('OpenAI API Key는 sk-로 시작해야 합니다')
            return v


    class AnthropicProviderConfig(BaseModel):
        """Anthropic Provider 설정"""
        api_key: Optional[str] = Field(default=None, description="Anthropic API Key")
        base_url: Optional[str] = Field(default=None, description="Base URL")
        timeout: int = Field(default=30, description="Timeout (초)")
        max_retries: int = Field(default=3, description="최대 재시도 횟수")
        default_model: str = Field(default="claude-3-haiku-20240307", description="기본 모델")


    class GeminiProviderConfig(BaseModel):
        """Google Gemini Provider 설정"""
        api_key: Optional[str] = Field(default=None, description="Google API Key")
        project: Optional[str] = Field(default=None, description="Google Cloud Project ID")
        location: str = Field(default="us-central1", description="Google Cloud Location")
        use_vertex: bool = Field(default=False, description="Vertex AI 사용 여부")
        timeout: int = Field(default=30, description="Timeout (초)")
        max_retries: int = Field(default=3, description="최대 재시도 횟수")
        default_model: str = Field(default="gemini-1.5-flash", description="기본 모델")


    class BedrockProviderConfig(BaseModel):
        """AWS Bedrock Provider 설정"""
        api_key: Optional[str] = Field(default=None, description="AWS Bearer Token API Key")
        region: str = Field(default="us-east-1", description="AWS Region")
        aws_access_key: Optional[str] = Field(default=None, description="AWS Access Key")
        aws_secret_key: Optional[str] = Field(default=None, description="AWS Secret Key")
        timeout: int = Field(default=60, description="Timeout (초)")
        max_retries: int = Field(default=3, description="최대 재시도 횟수")
        default_model: str = Field(default="anthropic.claude-3-haiku-20240307-v1:0", description="기본 모델")


    class RAGConfig(BaseModel):
        """RAG 시스템 설정"""
        vector_store_type: str = Field(default="memory", description="Vector Store 타입")
        chunk_size: int = Field(default=1000, description="텍스트 청크 크기")
        chunk_overlap: int = Field(default=200, description="청크 오버랩")
        embedding_model: str = Field(default="text-embedding-ada-002", description="임베딩 모델")
        similarity_threshold: float = Field(default=0.7, description="유사도 임계값")
        max_results: int = Field(default=5, description="최대 검색 결과 수")
        
        # ChromaDB 설정
        chroma_persist_directory: Optional[str] = Field(default=None, description="ChromaDB 저장 경로")
        chroma_collection_name: str = Field(default="documents", description="ChromaDB 컬렉션 이름")


    class LLMSettings(RFSBaseSettings):
        """LLM 모듈 통합 설정
        
        환경 변수를 통한 설정 관리:
        - OPENAI_API_KEY: OpenAI API 키
        - ANTHROPIC_API_KEY: Anthropic API 키  
        - GOOGLE_API_KEY: Google API 키
        - AWS_BEDROCK_API_KEY: AWS Bedrock Bearer Token
        - AWS_ACCESS_KEY_ID: AWS Access Key
        - AWS_SECRET_ACCESS_KEY: AWS Secret Key
        """
        
        # Provider 활성화 설정
        enabled_providers: List[LLMProviderType] = Field(
            default_factory=lambda: [LLMProviderType.OPENAI],
            description="활성화된 Provider 목록"
        )
        
        # 기본 Provider
        default_provider: LLMProviderType = Field(
            default=LLMProviderType.OPENAI,
            description="기본 Provider"
        )
        
        # Provider별 설정
        openai: OpenAIProviderConfig = Field(default_factory=OpenAIProviderConfig)
        anthropic: AnthropicProviderConfig = Field(default_factory=AnthropicProviderConfig)
        gemini: GeminiProviderConfig = Field(default_factory=GeminiProviderConfig)
        bedrock: BedrockProviderConfig = Field(default_factory=BedrockProviderConfig)
        
        # RAG 설정
        rag: RAGConfig = Field(default_factory=RAGConfig)
        
        # 모니터링 설정
        enable_monitoring: bool = Field(default=True, description="모니터링 활성화")
        enable_caching: bool = Field(default=True, description="캐싱 활성화")
        cache_ttl: int = Field(default=3600, description="캐시 TTL (초)")
        
        # 로깅 설정
        log_requests: bool = Field(default=False, description="요청 로깅")
        log_responses: bool = Field(default=False, description="응답 로깅")
        
        class Config:
            env_prefix = "LLM_"
            case_sensitive = False
            
            @staticmethod
            def env_file_path():
                return Path.cwd() / ".env"

else:
    # Pydantic 없을 때의 기본 설정
    class LLMSettings(dict):
        def __init__(self):
            super().__init__({
                "enabled_providers": ["openai"],
                "default_provider": "openai",
                "enable_monitoring": True,
                "enable_caching": True,
                "cache_ttl": 3600,
                "log_requests": False,
                "log_responses": False
            })


# 싱글톤 설정 인스턴스
_llm_settings: Optional[LLMSettings] = None


def get_llm_settings() -> LLMSettings:
    """LLM 설정 반환"""
    global _llm_settings
    if _llm_settings is None:
        _llm_settings = LLMSettings()
    return _llm_settings


def configure_llm_settings(**kwargs) -> LLMSettings:
    """LLM 설정 업데이트"""
    global _llm_settings
    
    if PYDANTIC_AVAILABLE:
        _llm_settings = LLMSettings(**kwargs)
    else:
        _llm_settings = LLMSettings()
        _llm_settings.update(kwargs)
    
    return _llm_settings


# 미리 정의된 모델 목록
PREDEFINED_MODELS = {
    LLMProviderType.OPENAI: [
        LLMModel(name="gpt-4", provider=LLMProviderType.OPENAI, max_tokens=8192, 
                supports_function_calling=True),
        LLMModel(name="gpt-4-turbo", provider=LLMProviderType.OPENAI, max_tokens=128000,
                supports_function_calling=True, supports_vision=True),
        LLMModel(name="gpt-3.5-turbo", provider=LLMProviderType.OPENAI, max_tokens=4096,
                supports_function_calling=True),
        LLMModel(name="text-embedding-ada-002", provider=LLMProviderType.OPENAI,
                max_tokens=8191, supports_streaming=False),
    ],
    LLMProviderType.ANTHROPIC: [
        LLMModel(name="claude-3-opus-20240229", provider=LLMProviderType.ANTHROPIC,
                max_tokens=4096, supports_function_calling=True),
        LLMModel(name="claude-3-sonnet-20240229", provider=LLMProviderType.ANTHROPIC,
                max_tokens=4096, supports_function_calling=True),
        LLMModel(name="claude-3-haiku-20240307", provider=LLMProviderType.ANTHROPIC,
                max_tokens=4096, supports_function_calling=True),
    ],
    LLMProviderType.GEMINI: [
        LLMModel(name="gemini-1.5-pro", provider=LLMProviderType.GEMINI,
                max_tokens=8192, supports_function_calling=True, supports_vision=True),
        LLMModel(name="gemini-1.5-flash", provider=LLMProviderType.GEMINI,
                max_tokens=8192, supports_function_calling=True, supports_vision=True),
        LLMModel(name="text-embedding-004", provider=LLMProviderType.GEMINI,
                max_tokens=2048, supports_streaming=False),
    ],
    LLMProviderType.BEDROCK: [
        LLMModel(name="anthropic.claude-3-opus-20240229-v1:0", provider=LLMProviderType.BEDROCK,
                max_tokens=4096, supports_function_calling=True),
        LLMModel(name="anthropic.claude-3-sonnet-20240229-v1:0", provider=LLMProviderType.BEDROCK,
                max_tokens=4096, supports_function_calling=True),
        LLMModel(name="anthropic.claude-3-haiku-20240307-v1:0", provider=LLMProviderType.BEDROCK,
                max_tokens=4096, supports_function_calling=True),
        LLMModel(name="meta.llama3-70b-instruct-v1:0", provider=LLMProviderType.BEDROCK,
                max_tokens=2048),
        LLMModel(name="amazon.titan-text-express-v1", provider=LLMProviderType.BEDROCK,
                max_tokens=8192),
    ]
}


def get_available_models(provider: Optional[LLMProviderType] = None) -> List[LLMModel]:
    """사용 가능한 모델 목록 반환"""
    if provider:
        return PREDEFINED_MODELS.get(provider, [])
    
    all_models = []
    for models in PREDEFINED_MODELS.values():
        all_models.extend(models)
    return all_models


def get_model_info(model_name: str) -> Optional[LLMModel]:
    """모델 정보 반환"""
    for models in PREDEFINED_MODELS.values():
        for model in models:
            if model.name == model_name:
                return model
    return None