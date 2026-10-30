"""
模式 4: 糾錯自檢策略 (Corrective RAG - CRAG)
學術借鏡：
- CRAG: Corrective Retrieval Augmented Generation (Yan et al., 2024, arXiv:2401.15884)
- Self-RAG (Asai et al., ICLR 2024: Self-Reflection on Retrieval Confidence)
適用情境：原始提問帶有口語雜訊、意圖模糊，或本地知識庫可能缺乏資料之高風險場景。
"""

import re
import time
from typing import Any, Dict, List, Optional
from ..base import BaseRAGStrategy, BaseRetriever
from ..types import RAGMode, RAGResult, RetrievedChunk


class CorrectiveRAGStrategy(BaseRAGStrategy):
    """
    糾錯自檢 (CRAG)：三段式置信度轉移機制
    - Correct (高分 >= 0.60): 直接放行
    - Ambiguous (中分 0.25 <= score < 0.60): 啟動提問重寫 (Query Reformulation) 與二次補撈
    - Incorrect (低分 < 0.25): 阻斷硬編幻覺，標記需外網檢索退避 (Web Fallback)
    """

    mode = RAGMode.CORRECTIVE_CRAG

    # 常見口語廢話與冗餘語氣詞 (用於啟發式提問去噪)
    FILLER_WORDS = [
        r"^請(問|幫我|協助一下|查一下)\s*",
        r"我想(知道|了解|請教一下)\s*",
        r"(有沒有辦法|能否|可以告訴我)\s*",
        r"最近", r"大概", r"到底", r"究竟", r"的相關資訊", r"的詳細內容"
    ]

    def __init__(self, upper_threshold: float = 0.50, lower_threshold: float = 0.08, top_k: int = 4):
        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold
        self.top_k = top_k

    def _reformulate_query(self, query: str) -> str:
        """提問去噪與關鍵詞提煉 (Query Denoising & Expansion)"""
        cleaned = query.strip()
        for pattern in self.FILLER_WORDS:
            cleaned = re.sub(pattern, "", cleaned)
        cleaned = cleaned.strip("？?，,。！! \t\n")
        return cleaned if cleaned else query

    def execute(
        self,
        query: str,
        retriever: BaseRetriever,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RAGResult:
        start_ts = time.time()

        # 1. 第一輪初檢
        first_pass_chunks = retriever.retrieve(query, top_k=self.top_k)
        best_score = first_pass_chunks[0].score if first_pass_chunks else 0.0

        # 情境 A: 檢索品質優良 (Correct)
        if best_score >= self.upper_threshold:
            latency_ms = round((time.time() - start_ts) * 1000.0, 3)
            return RAGResult(
                mode_used=self.mode,
                chunks=first_pass_chunks,
                query=query,
                transformed_query=None,
                confidence_score=best_score,
                latency_ms=latency_ms,
                fallback_triggered=False,
                metadata={"crag_status": "CORRECT", "passes": 1}
            )

        # 情境 B: 檢索品質模糊 (Ambiguous) -> 觸發 Query Reformulation 二次檢索
        if best_score >= self.lower_threshold:
            reformed_q = self._reformulate_query(query)
            second_pass_chunks = retriever.retrieve(reformed_q, top_k=self.top_k)
            second_best = second_pass_chunks[0].score if second_pass_chunks else 0.0

            # 比較兩輪品質，採用更優的一組
            chosen_chunks = second_pass_chunks if second_best >= best_score else first_pass_chunks
            final_conf = max(best_score, second_best)
            latency_ms = round((time.time() - start_ts) * 1000.0, 3)

            return RAGResult(
                mode_used=self.mode,
                chunks=chosen_chunks,
                query=query,
                transformed_query=reformed_q,
                confidence_score=final_conf,
                latency_ms=latency_ms,
                fallback_triggered=False,
                metadata={
                    "crag_status": "AMBIGUOUS_REFINED",
                    "passes": 2,
                    "first_score": best_score,
                    "second_score": second_best,
                }
            )

        # 情境 C: 檢索品質極低 (Incorrect) -> 資料庫無相關知識，觸發退避以防幻覺
        latency_ms = round((time.time() - start_ts) * 1000.0, 3)
        return RAGResult(
            mode_used=self.mode,
            chunks=[],  # 清空垃圾切片，嚴防模型對無關文本進行硬編幻覺
            query=query,
            transformed_query=None,
            confidence_score=best_score,
            latency_ms=latency_ms,
            fallback_triggered=True,
            metadata={
                "crag_status": "INCORRECT_FALLBACK",
                "passes": 1,
                "reason": f"Max retrieval score {best_score} is below lower threshold {self.lower_threshold}",
                "requires_web_fallback": True
            }
        )
