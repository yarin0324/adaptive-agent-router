"""
自適應 RAG 調度適配器核心模組 (Adaptive RAG Adapter Subsystem)
"""

from .types import RAGMode, RetrievedChunk, RAGDecision, RAGResult
from .base import BaseRetriever, InMemoryVectorRetriever, BaseRAGStrategy
from .classifier import AdaptiveRAGRouter
from .adapter import AdaptiveRAGAdapter
from .strategies import (
    NoRAGStrategy,
    FastHybridRAGStrategy,
    PrecisionRerankRAGStrategy,
    CorrectiveRAGStrategy,
    AgenticMultiHopRAGStrategy,
)

__all__ = [
    "RAGMode",
    "RetrievedChunk",
    "RAGDecision",
    "RAGResult",
    "BaseRetriever",
    "InMemoryVectorRetriever",
    "BaseRAGStrategy",
    "AdaptiveRAGRouter",
    "AdaptiveRAGAdapter",
    "NoRAGStrategy",
    "FastHybridRAGStrategy",
    "PrecisionRerankRAGStrategy",
    "CorrectiveRAGStrategy",
    "AgenticMultiHopRAGStrategy",
]
