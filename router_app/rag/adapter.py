"""
自適應 RAG 適配器中介軟體 (Adaptive RAG Middleware Adapter)
統一封裝 5 大檢索模式、三階級聯路由器與底層檢索器，提供無縫可插拔之情境感知檢索服務。
"""

from typing import Any, Dict, List, Optional
from .types import RAGDecision, RAGMode, RAGResult, RetrievedChunk
from .base import BaseRAGStrategy, BaseRetriever, InMemoryVectorRetriever
from .classifier import AdaptiveRAGRouter
from .strategies import (
    NoRAGStrategy,
    FastHybridRAGStrategy,
    PrecisionRerankRAGStrategy,
    CorrectiveRAGStrategy,
    AgenticMultiHopRAGStrategy,
)


class AdaptiveRAGAdapter:
    """自適應情境感知 RAG 調度適配器"""

    def __init__(
        self,
        retriever: Optional[BaseRetriever] = None,
        custom_strategies: Optional[Dict[RAGMode, BaseRAGStrategy]] = None,
        router: Optional[AdaptiveRAGRouter] = None,
    ):
        self.retriever = retriever or InMemoryVectorRetriever()
        self.router = router or AdaptiveRAGRouter()

        # 註冊五大標準策略
        self.strategies: Dict[RAGMode, BaseRAGStrategy] = {
            RAGMode.NO_RAG: NoRAGStrategy(),
            RAGMode.FAST_HYBRID: FastHybridRAGStrategy(),
            RAGMode.PRECISION_RERANK: PrecisionRerankRAGStrategy(),
            RAGMode.CORRECTIVE_CRAG: CorrectiveRAGStrategy(),
            RAGMode.AGENTIC_MULTIHOP: AgenticMultiHopRAGStrategy(),
        }

        if custom_strategies:
            self.strategies.update(custom_strategies)

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> RAGDecision:
        """快速路由決策：判定提問該採用哪種 RAG 檢索模式 (時延 < 2ms)"""
        return self.router.route(query, context)

    def dispatch(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        forced_mode: Optional[RAGMode] = None,
    ) -> RAGResult:
        """
        核心分流與執行管線：
        1. 路由器評估提問複雜度
        2. 指派至最適 RAG 策略 (No-RAG, Fast Hybrid, Precision, CRAG, Multi-Hop)
        3. 調用底層檢索器執行切片萃取
        4. 返回結構化 RAGResult 供 LLM Prompt 注入
        """
        if forced_mode and forced_mode in self.strategies:
            strategy = self.strategies[forced_mode]
            decision_mode = forced_mode
        else:
            decision = self.route(query, context)
            strategy = self.strategies.get(decision.mode, self.strategies[RAGMode.FAST_HYBRID])
            decision_mode = decision.mode

        result = strategy.execute(
            query=query,
            retriever=self.retriever,
            context=context
        )
        return result

    @staticmethod
    def format_prompt_with_context(prompt: str, rag_result: RAGResult) -> str:
        """
        將檢索成果優雅格式化注入至使用者 Prompt 前端
        若為 No-RAG 或無切片則維持原 Prompt，零額外 Token 負擔
        """
        if not rag_result.chunks:
            return prompt

        context_block = rag_result.to_context_text()
        return (
            f"【知識庫檢索參考資料 (RAG Strategy: {rag_result.mode_used.value})】\n"
            f"{context_block}\n\n"
            f"【使用者提問】\n{prompt}"
        )
