"""
模式 1: 不檢索策略 (No-RAG Strategy)
適用情境：閒聊問候、單純代碼重構、常識邏輯推導、模型固有參數記憶即可回答之任務。
延遲: 0ms | 成本: 0 Token
"""

import time
from typing import Any, Dict, Optional
from ..base import BaseRAGStrategy, BaseRetriever
from ..types import RAGMode, RAGResult


class NoRAGStrategy(BaseRAGStrategy):
    """不檢索策略：直接由 LLM 模型參數庫與 System Prompt 處理"""

    mode = RAGMode.NO_RAG

    def execute(
        self,
        query: str,
        retriever: BaseRetriever,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RAGResult:
        start_ts = time.time()
        latency_ms = round((time.time() - start_ts) * 1000.0, 3)

        return RAGResult(
            mode_used=self.mode,
            chunks=[],
            query=query,
            transformed_query=None,
            confidence_score=1.0,
            latency_ms=latency_ms,
            fallback_triggered=False,
            metadata={"strategy": "no_rag", "reason": "Query requires no external factual retrieval."}
        )
