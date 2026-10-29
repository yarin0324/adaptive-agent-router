"""
模式 10: 情境式記憶 (Contextual / Semantic Memory)
負責跨輪次持久化知識累積、使用者畫像與工作階段記憶管理。
原生整合 RRF (Reciprocal Rank Fusion) 倒數排名融合混合檢索。
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from ..cache.rrf_engine import RRFEngine


class MemoryEntry(BaseModel):
    entry_id: str
    user_id: str
    session_id: str
    topic: str
    content: str
    importance: float = 1.0


class MemoryManager:
    """記憶體管理器 (具備 RRF 混合檢索能力)"""

    def __init__(self, rrf_k: int = 60):
        self._store: Dict[str, MemoryEntry] = {}
        self.rrf_engine = RRFEngine(k=rrf_k, w_lex=1.0, w_sem=1.0)
        self._counter = 0

    def save_memory(
        self,
        user_id: str,
        session_id: str,
        topic: str,
        content: str,
        importance: float = 1.0,
    ) -> str:
        self._counter += 1
        entry_id = f"mem_{self._counter:05d}"
        entry = MemoryEntry(
            entry_id=entry_id,
            user_id=user_id,
            session_id=session_id,
            topic=topic,
            content=content,
            importance=importance,
        )
        self._store[entry_id] = entry
        return entry_id

    def retrieve_relevant(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        採用 RRF (Reciprocal Rank Fusion) 倒數排名融合進行混合召回
        融合「關鍵字頻率排名」與「語意餘弦相似度排名」
        """
        if not self._store:
            return []

        # 整理候選文本集合
        candidates: List[Tuple[str, str]] = [
            (eid, f"{m.topic} {m.content}") for eid, m in self._store.items()
        ]

        # 1. 關鍵字檢索排名 (Lexical Rank)
        lexical_ranked = self.rrf_engine.lexical_rank(query, candidates)

        # 2. 語意向量相似度排名 (Semantic Rank)
        semantic_ranked = self.rrf_engine.semantic_rank(query, candidates)

        # 3. 執行 RRF 融合公式
        fused_ranks = self.rrf_engine.fuse(lexical_ranked, semantic_ranked)

        results = []
        for eid, score in fused_ranks[:limit]:
            item = self._store[eid].model_dump()
            item["rrf_score"] = round(score, 5)
            results.append(item)

        return results

    def clear(self):
        self._store.clear()
        self._counter = 0
