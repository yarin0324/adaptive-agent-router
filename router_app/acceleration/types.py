"""
LLM 推論加速與控制平面核心型態定義 (LLM Acceleration & Serving Types)
涵蓋 Workload 分流、前綴快取結構、推測解碼門控與工作節點定義。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class WorkloadType(str, Enum):
    """計算負載特徵類型 (借鏡 DistServe / Mooncake Prefill-Decode 解耦)"""
    PREFILL_BOUND = "prefill_bound"   # 輸入極長，輸出較短 (Compute-bound, 適合高併發 Chunked Prefill 節點)
    DECODE_BOUND = "decode_bound"     # 輸入短，輸出極長/多步推理 (Memory-bandwidth bound, 適合低延遲 TP/Decode 節點)
    BALANCED = "balanced"             # 平衡型工作負載


class SpeculativeMode(str, Enum):
    """推測解碼門控模式 (借鏡 EAGLE-2 / Medusa)"""
    OFF = "off"                       # 停用推測解碼 (高難度數理/代碼合成，避免 Rollback 負優化)
    CONSERVATIVE = "conservative"     # 保守推測 (K=3 草稿步數，適用一般問答)
    AGGRESSIVE = "aggressive"         # 積極推測 (K=5~6 草稿步數，適用高規律 JSON / 格式化提取)


@dataclass
class SpeculativeDecision:
    """自適應推測解碼門控決策"""
    enabled: bool
    mode: SpeculativeMode
    draft_tokens: int
    predicted_acceptance_rate: float
    estimated_speedup: float
    rationale: str


@dataclass
class CanonicalPromptResult:
    """提示詞前綴標準化分離結果 (Prefix Caching 最佳化)"""
    canonical_prompt: str
    static_prefix: str
    dynamic_suffix: str
    prefix_hash: str
    estimated_tokens: int
    is_cache_friendly: bool
    sanitization_warnings: List[str] = field(default_factory=list)


@dataclass
class CompressionResult:
    """提示詞選擇性去噪壓縮結果 (借鏡 LLMLingua-2)"""
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    reduction_ratio: float
    latency_ms: float


@dataclass
class WorkerNode:
    """後端 GPU 推論節點 (相容 vLLM / SGLang / Mooncake / Ollama 叢集)"""
    node_id: str
    endpoint: str
    gpu_type: str = "NVIDIA-H100"
    capacity: int = 32
    active_requests: int = 0
    workload_preference: WorkloadType = WorkloadType.BALANCED
    cached_prefixes: Set[str] = field(default_factory=set)
    total_served: int = 0
    cache_hits: int = 0


@dataclass
class AccelerationDecision:
    """端到端加速控制決策報告"""
    target_node_id: str
    is_cache_hit: bool
    prefix_hash: str
    workload_type: WorkloadType
    speculative: SpeculativeDecision
    prompt_pruned: bool
    original_tokens: int
    final_tokens: int
    tokens_saved_ratio: float
    routing_latency_ms: float
    downstream_params: Dict[str, Any] = field(default_factory=dict)
