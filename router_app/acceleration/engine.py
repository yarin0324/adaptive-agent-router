"""
LLM 推論加速整合控制器 (LLM Acceleration Controller)
作為 Agent Gateway 與底層推論叢集（vLLM / SGLang / Mooncake）之間的統一中介層。

串聯五大核心優化：
  1. Canonical Prompt Layout (前綴確定性解耦)
  2. Selective Prompt Pruner (資訊熵語意去噪)
  3. Disaggregated Workload Splitter (Prefill/Decode 分流)
  4. Cache-Aware Affinity Router (前綴快取一致性雜湊)
  5. Adaptive Speculative Decoding Gator (動態推測解碼門控)
"""

import time
from typing import Any, Dict, List, Optional, Union

from .affinity_router import CacheAwareAffinityRouter
from .canonical_layout import CanonicalPromptFormatter
from .disaggregated_splitter import DisaggregatedWorkloadSplitter
from .prompt_pruner import SelectivePromptPruner
from .speculative_gator import AdaptiveSpeculativeGator
from .types import (
    AccelerationDecision,
    CanonicalPromptResult,
    WorkerNode,
    WorkloadType,
)


class LLMAccelerationController:
    """端到端 LLM 推論加速控制器"""

    def __init__(
        self,
        router: Optional[CacheAwareAffinityRouter] = None,
        enable_pruning: bool = True,
        enable_speculative: bool = True,
    ):
        self.router = router or CacheAwareAffinityRouter()
        self.enable_pruning = enable_pruning
        self.enable_speculative = enable_speculative

    def optimize_and_route(
        self,
        system_prompt: str,
        user_query: str,
        tools: Optional[List[Union[Dict[str, Any], str]]] = None,
        rag_context: Optional[Union[List[Dict[str, Any]], str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        mode: str = "mode_1_single_turn",
        expected_output_tokens: int = 256,
        format_constraint: Optional[str] = None,
        ephemeral_metadata: Optional[Dict[str, Any]] = None,
    ) -> AccelerationDecision:
        """
        端到端執行 Prompt 標準化、去噪、負載分流、節點指派與推測解碼門控
        """
        start_time = time.perf_counter()

        # 1. 選擇性去噪壓縮 (若有長篇 RAG 上下文或冗長問句)
        original_tokens = max(1, int((len(system_prompt) + len(user_query) + len(str(rag_context or ""))) / 3.6))
        final_rag_context = rag_context

        pruned = False
        if self.enable_pruning and rag_context:
            if isinstance(rag_context, str):
                compress_res = SelectivePromptPruner.prune(rag_context)
                final_rag_context = compress_res.compressed_text
                pruned = True
            elif isinstance(rag_context, list):
                # 針對 list 內每個 chunk 的 content 進行去噪
                new_chunks = []
                for c in rag_context:
                    if isinstance(c, dict) and "content" in c:
                        pruned_c = dict(c)
                        c_res = SelectivePromptPruner.prune(c["content"])
                        pruned_c["content"] = c_res.compressed_text
                        new_chunks.append(pruned_c)
                    else:
                        new_chunks.append(c)
                final_rag_context = new_chunks
                pruned = True

        # 2. 確定性標準化 Prompt 佈局 (分離靜態前綴與動態後綴)
        canonical_res: CanonicalPromptResult = CanonicalPromptFormatter.format(
            system_prompt=system_prompt,
            tools=tools,
            rag_context=final_rag_context,
            chat_history=chat_history,
            user_query=user_query,
            ephemeral_metadata=ephemeral_metadata,
        )

        final_tokens = canonical_res.estimated_tokens
        saved_ratio = max(0.0, (original_tokens - final_tokens) / original_tokens) if pruned else 0.0

        # 3. 工作負載特徵分類 (Prefill-bound vs Decode-bound)
        workload_meta = DisaggregatedWorkloadSplitter.classify(
            prompt_tokens=final_tokens,
            expected_output_tokens=expected_output_tokens,
            mode=mode,
        )
        workload_type: WorkloadType = workload_meta["workload_type"]

        # 4. 快取感知親和性路由 (指派最適 WorkerNode)
        worker, is_cache_hit = self.router.dispatch(
            prefix_hash=canonical_res.prefix_hash,
            workload_type=workload_type,
        )

        # 5. 自適應推測解碼門控
        if self.enable_speculative:
            spec_decision = AdaptiveSpeculativeGator.evaluate(
                query=user_query,
                mode=mode,
                format_constraint=format_constraint,
            )
        else:
            from .types import SpeculativeMode
            from .types import SpeculativeDecision
            spec_decision = SpeculativeDecision(
                enabled=False,
                mode=SpeculativeMode.OFF,
                draft_tokens=0,
                predicted_acceptance_rate=0.0,
                estimated_speedup=1.0,
                rationale="推測解碼已手動停用。",
            )

        routing_latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 6. 組裝下游推論引擎請求參數 (符合 vLLM / SGLang / OpenAI API 規範)
        spec_params = AdaptiveSpeculativeGator.to_downstream_payload(spec_decision)
        downstream_params = {
            "node_id": worker.node_id,
            "target_endpoint": worker.endpoint,
            "prompt": canonical_res.canonical_prompt,
            "prefix_hash": canonical_res.prefix_hash,
            "is_cache_hit": is_cache_hit,
            "workload_type": workload_type.value,
            "batching_hint": workload_meta["batching_hint"],
            **spec_params,
        }

        return AccelerationDecision(
            target_node_id=worker.node_id,
            is_cache_hit=is_cache_hit,
            prefix_hash=canonical_res.prefix_hash,
            workload_type=workload_type,
            speculative=spec_decision,
            prompt_pruned=pruned,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
            tokens_saved_ratio=round(saved_ratio, 4),
            routing_latency_ms=round(routing_latency_ms, 3),
            downstream_params=downstream_params,
        )

    def release_worker(self, node_id: str):
        """請求完成後釋放節點"""
        self.router.release(node_id)
