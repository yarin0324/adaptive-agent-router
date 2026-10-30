"""
模式 2: 快速混合檢索策略 (Fast Hybrid RAG Strategy)
學術借鏡：
- BM25S (Soldaini et al., 2024: Fast Python/NumPy BM25)
- RRF 倒數排名融合 (Cormack et al., SIGIR 2009)
適用情境：包含專有名詞、代碼、料號或明確事實查詢，需兼顧關鍵字精準度與語意泛化。
"""

import time
from typing import Any, Dict, List, Optional
from ..base import BaseRAGStrategy, BaseRetriever
from ..types import RAGMode, RAGResult, RetrievedChunk
from ...cache.rrf_engine import RRFEngine


class FastHybridRAGStrategy(BaseRAGStrategy):
    """快速混合檢索：BM25/詞頻關鍵字 + 向量語意雙路召回，經 RRF 倒數排名融合"""

    mode = RAGMode.FAST_HYBRID

    def __init__(self, top_k: int = 5, rrf_k: int = 60):
        self.top_k = top_k
        self.rrf_engine = RRFEngine(k=rrf_k, w_lex=1.0, w_sem=1.0)

    def execute(
        self,
        query: str,
        retriever: BaseRetriever,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RAGResult:
        start_ts = time.time()
        
        # 1. 向底層檢索器撈取候選切片 (取 top_k * 2 作為融合池)
        candidate_pool_size = max(10, self.top_k * 2)
        raw_candidates = retriever.retrieve(query, top_k=candidate_pool_size)

        if not raw_candidates:
            return RAGResult(
                mode_used=self.mode,
                chunks=[],
                query=query,
                confidence_score=0.0,
                latency_ms=round((time.time() - start_ts) * 1000.0, 3),
                fallback_triggered=True,
                metadata={"reason": "No candidates returned from underlying retriever."}
            )

        # 2. 構建 RRF 候選池 [(id, content), ...]
        chunk_map = {c.id: c for c in raw_candidates}
        candidates = [(c.id, c.content) for c in raw_candidates]

        # 3. 雙路排名與倒數融合
        lex_ids = self.rrf_engine.lexical_rank(query, candidates)
        sem_ids = self.rrf_engine.semantic_rank(query, candidates)
        fused_rankings = self.rrf_engine.fuse(lex_ids, sem_ids)

        # 4. 挑選 Top-K 切片並重算 RRF 正規化分數
        selected_chunks: List[RetrievedChunk] = []
        max_rrf_score = fused_rankings[0][1] if fused_rankings else 1.0

        for cid, rrf_score in fused_rankings[:self.top_k]:
            orig_chunk = chunk_map[cid]
            # 將 RRF 分數歸一化至 0.0 ~ 1.0 區間
            norm_score = round(rrf_score / max_rrf_score if max_rrf_score > 0 else 0.5, 4)
            selected_chunks.append(RetrievedChunk(
                id=orig_chunk.id,
                content=orig_chunk.content,
                source=orig_chunk.source,
                score=norm_score,
                metadata={
                    **orig_chunk.metadata,
                    "rrf_raw_score": round(rrf_score, 6),
                    "retrieval_method": "hybrid_rrf"
                }
            ))

        latency_ms = round((time.time() - start_ts) * 1000.0, 3)
        avg_confidence = round(sum(c.score for c in selected_chunks) / len(selected_chunks), 4) if selected_chunks else 0.0

        return RAGResult(
            mode_used=self.mode,
            chunks=selected_chunks,
            query=query,
            confidence_score=avg_confidence,
            latency_ms=latency_ms,
            fallback_triggered=False,
            metadata={"top_k": self.top_k, "fusion_method": "RRF (k=60)"}
        )
