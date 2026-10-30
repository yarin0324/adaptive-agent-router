"""
RAG 適配器核心資料模型與型別定義 (Adaptive RAG Data Models & Types)
學術借鏡：
- Adaptive-RAG (Jeong et al., NAACL 2024, arXiv:2403.14403)
- Corrective RAG (Yan et al., 2024, arXiv:2401.15884)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RAGMode(str, Enum):
    """自適應 RAG 檢索策略模式 (5-Tier RAG Strategy Taxonomy)"""
    NO_RAG = "no_rag"                      # 不檢索：直接由 LLM 參數量與 System Prompt 回答 (0ms)
    FAST_HYBRID = "fast_hybrid"            # 快速混合檢索：BM25 關鍵字 + 向量餘弦 + RRF 倒數排名融合
    PRECISION_RERANK = "precision_rerank"  # 精準重排序：混合召回 + 輕量 Cross-Encoder/FlashRank 二階段精濾
    CORRECTIVE_CRAG = "corrective_crag"    # 糾錯自檢 (CRAG)：檢索品質評估 + 信心門控 + 意圖重寫/外網退避
    AGENTIC_MULTIHOP = "agentic_multihop"  # 多跳代理檢索：子問題拆解 + 多輪迭代檢索 + 關聯脈絡合成


class RetrievedChunk(BaseModel):
    """檢索文本切片資料模型"""
    id: str = Field(description="切片唯一識別碼")
    content: str = Field(description="檢索文本內容")
    source: str = Field(default="knowledge_base", description="資料來源標籤 (檔案路徑、URL 或資料庫名)")
    score: float = Field(default=0.0, description="相關度分數 (0.0 ~ 1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="擴充中繼資料")


class RAGDecision(BaseModel):
    """自適應 RAG 路由器分流決策"""
    mode: RAGMode = Field(description="指派之 RAG 檢索模式")
    reasoning: str = Field(description="路由器判定依據與特徵命中說明")
    complexity_level: str = Field(default="simple", description="提問複雜度級別 (simple / medium / complex)")
    confidence: float = Field(default=1.0, description="路由決策置信度 (0.0 ~ 1.0)")
    requires_web_fallback: bool = Field(default=False, description="是否標記可能需退避至外部搜尋")
    tags: List[str] = Field(default_factory=list, description="特徵標籤 (e.g. entity_lookup, multi_hop, chitchat)")


class RAGResult(BaseModel):
    """RAG 適配器最終檢索交付結果"""
    mode_used: RAGMode = Field(description="實際執行的 RAG 策略模式")
    chunks: List[RetrievedChunk] = Field(default_factory=list, description="檢索與過濾後之切片清單")
    query: str = Field(description="原始提問")
    transformed_query: Optional[str] = Field(default=None, description="經 CRAG 或多跳拆解改寫後之查詢")
    confidence_score: float = Field(default=1.0, description="檢索結果綜合置信度評分")
    latency_ms: float = Field(default=0.0, description="檢索總耗時 (毫秒)")
    fallback_triggered: bool = Field(default=False, description="是否觸發降級或退避機制")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="執行過程詳細中繼數據")

    def to_context_text(self) -> str:
        """將切片轉換為標準 Prompt 注入字串"""
        if not self.chunks:
            return ""
        lines = []
        for idx, chunk in enumerate(self.chunks, 1):
            src = f" [Source: {chunk.source}]" if chunk.source else ""
            lines.append(f"[{idx}]{src} {chunk.content.strip()}")
        return "\n".join(lines)
