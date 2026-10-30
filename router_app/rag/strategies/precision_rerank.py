"""
模式 3: 精準重排序策略 (Precision RAG with Lightweight Reranker)
開源借鏡：
- FlashRank (Prithiviraj Damodaran: Ultra-lightweight Cross-Encoder Reranker)
適用情境：法規合約、審計條款、高精度技術規範等需嚴格排除雜訊切片的任務。
"""

import math
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from ..base import BaseRAGStrategy, BaseRetriever
from ..types import RAGMode, RAGResult, RetrievedChunk


class PrecisionRerankRAGStrategy(BaseRAGStrategy):
    """精準重排序：先寬鬆初召回，再以輕量級交叉特徵評分過濾雜訊"""

    mode = RAGMode.PRECISION_RERANK

    def __init__(self, top_k: int = 3, min_rerank_score: float = 0.25):
        self.top_k = top_k
        self.min_rerank_score = min_rerank_score

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text_lower = text.lower()
        words = re.findall(r"[a-zA-Z0-9_\-\.]{2,}", text_lower)
        chars = re.findall(r"[\u4e00-\u9fa5]", text_lower)
        ngrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
        return words + chars + ngrams

    def _cross_match_score(self, query: str, document: str) -> float:
        """
        純 Python 交叉匹配與連續詞塊親和度評分 (Cross-Encoder 輕量代理)
        考量：
        1. 提問關鍵詞在文章中的覆蓋率 (Coverage)
        2. 局部詞頻密度 (Density)
        3. 2-gram 連續詞彙精確命中率 (Exact Phrase Match)
        """
        q_tokens = self._tokenize(query)
        d_tokens = self._tokenize(document)

        if not q_tokens or not d_tokens:
            return 0.0

        q_set = set(q_tokens)
        d_counts = Counter(d_tokens)

        # 1. 覆蓋率 (Query Coverage)
        matched_tokens = q_set & set(d_counts.keys())
        coverage = len(matched_tokens) / len(q_set) if q_set else 0.0

        # 2. 局部密度加權
        density = sum(d_counts[t] for t in matched_tokens) / (len(d_tokens) + 10)

        # 3. 連續短語命中 (Bigram Match)
        q_phrases = [q_tokens[i] + " " + q_tokens[i+1] for i in range(len(q_tokens)-1)] if len(q_tokens) > 1 else []
        d_text = " ".join(d_tokens)
        phrase_hits = sum(1 for p in q_phrases if p in d_text)
        phrase_ratio = phrase_hits / max(1, len(q_phrases)) if q_phrases else coverage

        # 綜合交叉相關性得分
        final_score = (0.5 * coverage) + (0.3 * phrase_ratio) + (0.2 * min(1.0, density * 5.0))
        return min(1.0, max(0.0, final_score))

    def execute(
        self,
        query: str,
        retriever: BaseRetriever,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RAGResult:
        start_ts = time.time()

        # 1. 擴大召回池 (取 top_k * 3 筆初選候選)
        recall_pool_size = max(12, self.top_k * 3)
        raw_candidates = retriever.retrieve(query, top_k=recall_pool_size)

        if not raw_candidates:
            return RAGResult(
                mode_used=self.mode,
                chunks=[],
                query=query,
                confidence_score=0.0,
                latency_ms=round((time.time() - start_ts) * 1000.0, 3),
                fallback_triggered=True,
                metadata={"reason": "Empty initial recall."}
            )

        # 2. 二階段交叉重排序 (Reranking)
        reranked: List[Tuple[RetrievedChunk, float]] = []
        for c in raw_candidates:
            score = self._cross_match_score(query, c.content)
            reranked.append((c, score))

        # 依交叉重排分數降序排列
        reranked.sort(key=lambda x: x[1], reverse=True)

        # 3. 過濾低於門檻之無效切片並取 Top-K
        selected_chunks: List[RetrievedChunk] = []
        for orig_chunk, score in reranked:
            if score >= self.min_rerank_score or len(selected_chunks) == 0:
                selected_chunks.append(RetrievedChunk(
                    id=orig_chunk.id,
                    content=orig_chunk.content,
                    source=orig_chunk.source,
                    score=round(score, 4),
                    metadata={
                        **orig_chunk.metadata,
                        "initial_score": orig_chunk.score,
                        "rerank_score": round(score, 4),
                        "reranker": "FlashRank-style CrossMatch"
                    }
                ))
            if len(selected_chunks) >= self.top_k:
                break

        latency_ms = round((time.time() - start_ts) * 1000.0, 3)
        avg_confidence = round(sum(c.score for c in selected_chunks) / len(selected_chunks), 4) if selected_chunks else 0.0

        return RAGResult(
            mode_used=self.mode,
            chunks=selected_chunks,
            query=query,
            confidence_score=avg_confidence,
            latency_ms=latency_ms,
            fallback_triggered=len(selected_chunks) == 0,
            metadata={"initial_pool": len(raw_candidates), "reranked_top_k": len(selected_chunks)}
        )
