"""
倒數排名融合混合檢索與路由引擎 (Reciprocal Rank Fusion - RRF Engine)
借鏡自 MySecondBrain/mcp_server/rrf_search.py 與 Cormack et al. (SIGIR 2009)
融合「精確關鍵字排名 (Lexical Rank)」與「語意概念排名 (Semantic Vector Rank)」，
透過倒數名次多數決投票消除各自盲區，無需繁複分數標準化，純 Python 零重量依賴實作。
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from ..types import AgentMode


class RRFEngine:
    """倒數排名融合引擎 (Reciprocal Rank Fusion)"""

    def __init__(self, k: int = 60, w_lex: float = 1.0, w_sem: float = 1.0):
        self.k = k  # RRF 平滑常數，文獻推薦值 60
        self.w_lex = w_lex  # 關鍵字檢索權重
        self.w_sem = w_sem  # 語意向量檢索權重

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """中英雙軌分詞與 2-gram 萃取"""
        if not text:
            return []
        text_lower = text.lower()
        # 英數字與單詞
        words = re.findall(r"[a-zA-Z0-9_\-\.]{2,}", text_lower)
        # 中文字元與雙字元 N-gram
        c_chars = re.findall(r"[\u4e00-\u9fa5]", text_lower)
        c_ngrams = [c_chars[i] + c_chars[i + 1] for i in range(len(c_chars) - 1)]
        return words + c_chars + c_ngrams

    @classmethod
    def lexical_rank(cls, query: str, candidates: List[Tuple[str, str]]) -> List[str]:
        """
        關鍵字精準頻率排名 (BM25 / TF-IDF 簡化評分)
        candidates: [(item_id, content_text), ...]
        """
        query_tokens = cls.tokenize(query)
        if not query_tokens:
            return [cid for cid, _ in candidates]

        scores: List[Tuple[str, float]] = []
        for cid, content in candidates:
            content_tokens = cls.tokenize(content)
            counts = Counter(content_tokens)
            score = sum(counts[q] for q in query_tokens if q in counts)
            scores.append((cid, float(score)))

        # 按分數降序排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return [cid for cid, _ in scores]

    @classmethod
    def semantic_rank(cls, query: str, candidates: List[Tuple[str, str]]) -> List[str]:
        """
        語意向量餘弦相似度排名
        candidates: [(item_id, content_text), ...]
        """
        query_tokens = Counter(cls.tokenize(query))
        query_norm = math.sqrt(sum(v * v for v in query_tokens.values()))
        if query_norm == 0:
            return [cid for cid, _ in candidates]

        scores: List[Tuple[str, float]] = []
        for cid, content in candidates:
            content_tokens = Counter(cls.tokenize(content))
            dot_product = sum(query_tokens[k] * content_tokens[k] for k in query_tokens if k in content_tokens)
            content_norm = math.sqrt(sum(v * v for v in content_tokens.values()))
            similarity = dot_product / (query_norm * content_norm) if content_norm > 0 else 0.0
            scores.append((cid, similarity))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [cid for cid, _ in scores]

    def fuse(
        self,
        lexical_ranked_ids: List[str],
        semantic_ranked_ids: List[str],
    ) -> List[Tuple[str, float]]:
        """
        執行 RRF 倒數名次融合公式:
        RRF_score(d) = w_lex / (k + rank_lex(d)) + w_sem / (k + rank_sem(d))
        """
        rrf_scores: Dict[str, float] = {}

        # 累加關鍵字排名得分 (rank 從 1 開始)
        for rank, cid in enumerate(lexical_ranked_ids, start=1):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (self.w_lex / (self.k + rank))

        # 累加語意排名得分
        for rank, cid in enumerate(semantic_ranked_ids, start=1):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (self.w_sem / (self.k + rank))

        # 排序產出融合清單
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results
