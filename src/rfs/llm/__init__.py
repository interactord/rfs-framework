"""
RFS Framework LLM Integration Module

엔터프라이즈급 LLM 통합을 위한 모듈
Result Pattern, HOF, DI가 완전히 통합된 LLM 모듈

주요 기능:
- Multi-Provider 지원 (OpenAI, Anthropic, Google Gemini, AWS Bedrock)
- Result Pattern 기반 에러 처리
- HOF 파이프라인 통합
- 프롬프트 템플릿 시스템
- RAG (Retrieval Augmented Generation)
- LLM 체인 및 워크플로우
- 토큰 사용량 모니터링 및 최적화
"""

from .manager import LLMManager, create_llm_manager_from_config
from .providers.base import LLMProvider
from .config import (
    get_llm_settings, 
    configure_llm_settings,
    LLMProviderType,
    get_available_models,
    get_model_info
)

try:
    from .providers.openai import OpenAIProvider
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from .providers.anthropic import AnthropicProvider
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from .providers.gemini import GeminiProvider
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from .providers.bedrock import BedrockProvider
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False

__all__ = [
    "LLMManager",
    "LLMProvider", 
    "create_llm_manager_from_config",
    "get_llm_settings",
    "configure_llm_settings",
    "LLMProviderType",
    "get_available_models", 
    "get_model_info",
]

if OPENAI_AVAILABLE:
    __all__.append("OpenAIProvider")

if ANTHROPIC_AVAILABLE:
    __all__.append("AnthropicProvider")

if GEMINI_AVAILABLE:
    __all__.append("GeminiProvider")

if BEDROCK_AVAILABLE:
    __all__.append("BedrockProvider")

__version__ = "1.0.0"