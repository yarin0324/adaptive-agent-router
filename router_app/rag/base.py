"""
RAG 基礎抽象介面與開箱即用檢索器 (Base RAG Interfaces & Reference Retrievers)
提供可插拔之 BaseRetriever 與 BaseRAGStrategy 契約，並內建純 Python 零依賴之 InMemoryVectorRetriever。
"""

from abc import ABC, abstractmethod
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter
from .types import RAGMode, RAGResult, RetrievedChunk


class BaseRetriever(ABC):
    """底層實體知識庫檢索器介面 (相容 Chroma, Pinecone, Qdrant, Elasticsearch 等)"""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> List[RetrievedChunk]:
        """執行底層檢索，返回相關切片清單"""
        pass


class InMemoryVectorRetriever(BaseRetriever):
    """
    開箱即用之純 Python 記憶體向量與關鍵字檢索器
    零外部依賴 (無需安裝 heavy C++ 向量庫)，採用 N-gram 詞頻與餘弦相似度實現高精度比對。
    """

    def __init__(self, documents: Optional[List[Dict[str, Any]]] = None):
        """
        documents 格式範例:
        [
            {"id": "doc_1", "content": "公司統編為 28459201，發票開立需填寫此統編。", "source": "corp_handbook.md"},
            {"id": "doc_2", "content": "伺服器重啟命令為 sudo systemctl restart nginx。", "source": "ops_sop.md"}
        ]
        """
        self.documents: List[Dict[str, Any]] = documents or []

    def add_document(self, content: str, doc_id: Optional[str] = None, source: str = "kb", metadata: Optional[Dict[str, Any]] = None):
        """動態加入文件切片"""
        doc_id = doc_id or f"doc_{len(self.documents) + 1}"
        self.documents.append({
            "id": doc_id,
            "content": content,
            "source": source,
            "metadata": metadata or {}
        })

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text_lower = text.lower()
        words = re.findall(r"[a-zA-Z0-9_\-\.]{2,}", text_lower)
        chars = re.findall(r"[\u4e00-\u9fa5]", text_lower)
        ngrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
        return words + chars + ngrams

    def _cosine_similarity(self, tokens1: List[str], tokens2: List[str]) -> float:
        if not tokens1 or not tokens2:
            return 0.0
        c1 = Counter(tokens1)
        c2 = Counter(tokens2)
        intersection = set(c1.keys()) & set(c2.keys())
        numerator = sum(c1[t] * c2[t] for t in intersection)
        sum1 = sum(v ** 2 for v in c1.values())
        sum2 = sum(v ** 2 for v in c2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        if not denominator:
            return 0.0
        return float(numerator / denominator)

    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> List[RetrievedChunk]:
        """依餘弦相似度排序返回切片"""
        if not self.documents:
            return []

        q_tokens = self._tokenize(query)
        scored: List[Tuple[Dict[str, Any], float]] = []

        for doc in self.documents:
            d_tokens = self._tokenize(doc["content"])
            sim = self._cosine_similarity(q_tokens, d_tokens)
            scored.append((doc, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        results: List[RetrievedChunk] = []

        for doc, score in scored[:top_k]:
            results.append(RetrievedChunk(
                id=doc["id"],
                content=doc["content"],
                source=doc.get("source", "kb"),
                score=round(score, 4),
                metadata=doc.get("metadata", {})
            ))

        return results


class BaseRAGStrategy(ABC):
    """自適應 RAG 策略抽象基底類別 (Strategy Pattern)"""

    mode: RAGMode

    @abstractmethod
    def execute(
        self,
        query: str,
        retriever: BaseRetriever,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RAGResult:
        """執行該模式對應之檢索管線"""
        pass
