"""
自適應 RAG 路由器 (Adaptive RAG Router & Complexity Classifier)
學術借鏡：
- Adaptive-RAG: Learning to Adapt Retrieval-Augmented LLMs through Question Complexity (Jeong et al., NAACL 2024, arXiv:2403.14403)
透過三階階梯式漏斗 (Three-Stage Cascade)，以極低時延 (< 2ms) 動態決定提問該走哪種 RAG 策略。
"""

import hashlib
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from .types import RAGDecision, RAGMode


class AdaptiveRAGRouter:
    """自適應 RAG 決策路由器：依提問複雜度、意圖屬性與實體密度分流"""

    # 1. 閒聊問候與純通用邏輯樣式 (L1 No-RAG 快篩)
    CHITCHAT_PATTERNS = [
        r"^(?:你好|哈囉|嗨|早安|午安|晚安|hello|hi|hey|[\!！\s\?？\.\,，。])+$",
        r"^(你是誰|自我介紹|你是什麼模型|who are you)",
        r"(寫一個|幫我寫|實作|用\s*python\s*寫).*(排序|氣泡排序|二元搜尋|反轉字串|斐波那契|leet\s*code)",
        r"^(謝謝|感謝|thx|thank you)",
    ]

    # 2. 多跳比較與跨文件關聯樣式 (L2 Agentic Multi-Hop)
    MULTIHOP_PATTERNS = [
        r"(比較|對比|差異|差距|versus|vs\.?).*(與|和|跟|以及)",
        r"(如何影響|為何導致|因果關聯|演變歷程|跨期分析)",
        r"同時符合.*(且|以及|和).*(條件|要求)",
    ]

    # 3. 高精度合約與條款檢索樣式 (L2 Precision Rerank)
    PRECISION_PATTERNS = [
        r"(合約|保密協議|ndc|條款|賠償|法規|罰則|著作權|專利|資安規範)",
        r"(精確條文|違約責任|免責聲明|終止條件)",
    ]

    # 4. 模糊口語與易幻覺提問樣式 (L2 Corrective CRAG)
    CORRECTIVE_PATTERNS = [
        r"(請教一下|我想問|隨便問問|好像|聽說|不知道有沒有|我想了解一下|好像有提到)",
        r"(是不是真的|有沒有這種事|謠傳|八卦|有沒有提到過)",
    ]

    def __init__(self, cache_size: int = 1000):
        self.cache_size = cache_size
        self._cache: Dict[str, RAGDecision] = {}
        self._lock = threading.Lock()

    def _normalize_key(self, query: str) -> str:
        cleaned = "".join(query.strip().lower().split())
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> RAGDecision:
        """
        三階級聯路由判定核心 (Three-Stage Cascade Decision)
        時延預期: 0.05ms ~ 1.5ms
        """
        if not query or not query.strip():
            return RAGDecision(
                mode=RAGMode.NO_RAG,
                reasoning="提問為空，直接略過檢索。",
                complexity_level="simple",
                confidence=1.0,
                tags=["empty_input"]
            )

        # L0: 檢查精確快取
        cache_key = self._normalize_key(query)
        with self._lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                return cached

        q_lower = query.strip().lower()

        # L1: 啟發式閒聊與通用推導快篩 (No-RAG)
        for pattern in self.CHITCHAT_PATTERNS:
            if re.search(pattern, q_lower):
                decision = RAGDecision(
                    mode=RAGMode.NO_RAG,
                    reasoning="命中通用閒聊/代碼演算法特徵，由模型固有參數回答，無需外掛檢索。",
                    complexity_level="simple",
                    confidence=0.98,
                    tags=["chitchat", "zero_latency"]
                )
                self._cache_decision(cache_key, decision)
                return decision

        # L2-A: 多跳比較與因果關聯分析 (Agentic Multi-Hop)
        for pattern in self.MULTIHOP_PATTERNS:
            if re.search(pattern, q_lower):
                decision = RAGDecision(
                    mode=RAGMode.AGENTIC_MULTIHOP,
                    reasoning="偵測到跨實體比較或因果多跳推導特徵，指派多跳代理分段拆解子問題。",
                    complexity_level="complex",
                    confidence=0.92,
                    tags=["multi_hop", "comparative_reasoning"]
                )
                self._cache_decision(cache_key, decision)
                return decision

        # L2-B: 口語模糊與易幻覺提問 (Corrective CRAG)
        for pattern in self.CORRECTIVE_PATTERNS:
            if re.search(pattern, q_lower):
                decision = RAGDecision(
                    mode=RAGMode.CORRECTIVE_CRAG,
                    reasoning="提問意圖模糊或帶有口語雜訊，指派 CRAG 信心門控與自動重寫機制。",
                    complexity_level="medium",
                    confidence=0.88,
                    requires_web_fallback=True,
                    tags=["corrective_crag", "ambiguous_intent"]
                )
                self._cache_decision(cache_key, decision)
                return decision

        # L2-C: 高精度合約與條款規範 (Precision Rerank)
        for pattern in self.PRECISION_PATTERNS:
            if re.search(pattern, q_lower):
                decision = RAGDecision(
                    mode=RAGMode.PRECISION_RERANK,
                    reasoning="偵測到高精度法規條款或商業合約特徵，指派二階段 Cross-Encoder 重排序嚴格去噪。",
                    complexity_level="medium",
                    confidence=0.95,
                    tags=["precision_audit", "legal_terms"]
                )
                self._cache_decision(cache_key, decision)
                return decision

        # L2-D: 預設實體事實與技術查詢 (Fast Hybrid)
        decision = RAGDecision(
            mode=RAGMode.FAST_HYBRID,
            reasoning="明確事實或特定業務知識檢索，指派 BM25 + 向量雙路 RRF 混合召回以獲得最佳平衡。",
            complexity_level="medium",
            confidence=0.90,
            tags=["fast_hybrid", "entity_lookup"]
        )
        self._cache_decision(cache_key, decision)
        return decision

    def _cache_decision(self, key: str, decision: RAGDecision):
        with self._lock:
            if len(self._cache) >= self.cache_size:
                first_k = next(iter(self._cache))
                del self._cache[first_k]
            self._cache[key] = decision
