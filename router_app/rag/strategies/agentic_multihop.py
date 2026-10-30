"""
模式 5: 多跳代理檢索策略 (Agentic Multi-Hop RAG Strategy)
學術借鏡：
- FLARE: Active Retrieval Augmented Generation (Jiang et al., EMNLP 2023)
- IRCoT: Interleaving Retrieval with Chain-of-Thought (Trivedi et al., 2023)
適用情境：跨文件多實體比對、因果推導分析、需分段探勘多個子問題的複雜任務。
"""

import re
import time
from typing import Any, Dict, List, Optional, Set
from ..base import BaseRAGStrategy, BaseRetriever
from ..types import RAGMode, RAGResult, RetrievedChunk


class AgenticMultiHopRAGStrategy(BaseRAGStrategy):
    """多跳代理檢索：自動將複雜多實體提問拆解為獨立子問題，分段探勘並關聯整合"""

    mode = RAGMode.AGENTIC_MULTIHOP

    # 比較型與多實體連接標記
    SPLIT_PATTERNS = [
        r"\s+(?:與|和|跟|以及|相較於|對比|versus|vs\.?)\s+",
        r"[\,\;與和]\s*",
        r"\s+以及\s+"
    ]

    def __init__(self, top_k_per_hop: int = 3, max_hops: int = 3):
        self.top_k_per_hop = top_k_per_hop
        self.max_hops = max_hops

    def _decompose_query(self, query: str) -> List[str]:
        """
        純 Python 啟發式多跳子問題拆解 (Query Decomposition)
        例：「比較 2024 與 2025 伺服器營收」-> ['2024 伺服器營收', '2025 伺服器營收']
        """
        # 1. 檢驗是否帶有比較或雙實體句型
        compare_match = re.search(r"比較\s*(.*?)\s*(?:與|和|跟|vs\.?)\s*(.*?)(?:的|在|之)?(.*)", query, re.IGNORECASE)
        if compare_match:
            entity_a = compare_match.group(1).strip()
            entity_b = compare_match.group(2).strip()
            subject = compare_match.group(3).strip()
            if entity_a and entity_b:
                return [
                    f"{entity_a} {subject}".strip(),
                    f"{entity_b} {subject}".strip()
                ]

        # 2. 檢驗年份/時間跨度型比對
        years = re.findall(r"\b(20\d\d|19\d\d)年?", query)
        if len(years) >= 2:
            base_q = re.sub(r"\b(20\d\d|19\d\d)年?", "", query).replace("比較", "").replace("差距", "").strip()
            return [f"{y} {base_q}".strip() for y in years[:self.max_hops]]

        # 3. 泛用分割：若含有「與 / 和 / vs」
        for pat in self.SPLIT_PATTERNS:
            parts = re.split(pat, query)
            if len(parts) >= 2:
                sub_queries = [p.strip() for p in parts if len(p.strip()) >= 3]
                if len(sub_queries) >= 2:
                    return sub_queries[:self.max_hops]

        # 無法拆解時維持原提問作為單一跳
        return [query]

    def execute(
        self,
        query: str,
        retriever: BaseRetriever,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RAGResult:
        start_ts = time.time()

        # 1. 子問題拆解
        sub_queries = self._decompose_query(query)

        # 2. 依序執行多跳探勘 (Multi-Hop Retrieval)
        aggregated_chunks: List[RetrievedChunk] = []
        seen_ids: Set[str] = set()
        hop_details: List[Dict[str, Any]] = []

        for hop_idx, sub_q in enumerate(sub_queries, 1):
            hop_chunks = retriever.retrieve(sub_q, top_k=self.top_k_per_hop)
            hop_details.append({
                "hop": hop_idx,
                "sub_query": sub_q,
                "retrieved_count": len(hop_chunks),
                "top_score": hop_chunks[0].score if hop_chunks else 0.0
            })

            for chunk in hop_chunks:
                if chunk.id not in seen_ids:
                    seen_ids.add(chunk.id)
                    # 標註子問題來源溯源資訊
                    enriched_metadata = dict(chunk.metadata)
                    enriched_metadata["hop"] = hop_idx
                    enriched_metadata["sub_query"] = sub_q
                    
                    aggregated_chunks.append(RetrievedChunk(
                        id=chunk.id,
                        content=chunk.content,
                        source=chunk.source,
                        score=chunk.score,
                        metadata=enriched_metadata
                    ))

        latency_ms = round((time.time() - start_ts) * 1000.0, 3)
        avg_confidence = round(sum(c.score for c in aggregated_chunks) / len(aggregated_chunks), 4) if aggregated_chunks else 0.0

        return RAGResult(
            mode_used=self.mode,
            chunks=aggregated_chunks,
            query=query,
            transformed_query=" | ".join(sub_queries) if len(sub_queries) > 1 else None,
            confidence_score=avg_confidence,
            latency_ms=latency_ms,
            fallback_triggered=len(aggregated_chunks) == 0,
            metadata={
                "hops_count": len(sub_queries),
                "sub_queries": sub_queries,
                "hop_details": hop_details
            }
        )
