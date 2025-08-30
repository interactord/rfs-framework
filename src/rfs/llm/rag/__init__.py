"""
RAG (Retrieval Augmented Generation) 시스템

벡터 데이터베이스를 사용한 검색 증강 생성 기능을 제공합니다.
Result Pattern과 HOF 패턴이 완전히 통합되어 있습니다.
"""

from .vector_store import VectorStore
from .engine import RAGEngine

try:
    from .chroma import ChromaVectorStore
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

__all__ = [
    "VectorStore", 
    "RAGEngine"
]

if CHROMA_AVAILABLE:
    __all__.append("ChromaVectorStore")