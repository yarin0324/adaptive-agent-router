"""
Prefill-Decode 解耦工作負載分類器 (Disaggregated Workload Splitter)
設計理念源自 DistServe (Zhong et al., OSDI 2024) 與 Mooncake (月之暗面 Kimi, 2024)。

核心原理：
在 LLM 推論中：
  - Prefill 階段為「計算密集型 (Compute-Bound)」：一次性並行處理長 Prompt 矩陣相乘，需最大化 GPU Tensor Core 吞吐。
  - Decode 階段為「記憶體頻寬密集型 (Memory-Bandwidth Bound)」：逐字吐出 Token，受限於顯存傳輸速率。
將兩者混在同一 GPU 上處理，會導致正在即時吐字的用戶遭遇嚴重的突發首字卡頓（Head-of-Line Blocking）。

本模組評估輸入 Context 與預期輸出長度，將請求精準標註為 PREFILL_BOUND 或 DECODE_BOUND，
以便下游調度器將長文本送往 Prefill 運算池，將對話推理送往 Decode 吐字池。
"""

from typing import Any, Dict

from .types import WorkloadType


class DisaggregatedWorkloadSplitter:
    """Prefill-Decode 負載特徵分類器"""

    PREFILL_TOKEN_THRESHOLD = 1200      # 超過此長度視為長文本 Prefill 偏重
    DECODE_TOKEN_THRESHOLD = 600        # 輸出超過此長度視為深度生成 Decode 偏重

    @classmethod
    def classify(
        cls,
        prompt_tokens: int,
        expected_output_tokens: int = 256,
        mode: str = "mode_1_single_turn",
    ) -> Dict[str, Any]:
        """
        評估工作負載特徵並產出調度建議
        """
        # 模式特性修正
        if mode in ("mode_4_planner", "mode_7_multi_agent", "mode_9_ensemble"):
            # 涉及多輪或多步推理，Decode 比重放大
            effective_output_tokens = max(expected_output_tokens, 800)
        else:
            effective_output_tokens = expected_output_tokens

        # 1. 判斷 Prefill-Bound
        if prompt_tokens >= cls.PREFILL_TOKEN_THRESHOLD and (prompt_tokens / max(1, effective_output_tokens)) >= 2.5:
            workload = WorkloadType.PREFILL_BOUND
            batching_hint = {
                "enable_chunked_prefill": True,
                "chunk_size": 512,
                "priority_queue": "high_throughput_prefill",
                "precision_preference": "fp8_e4m3",
            }
            rationale = f"輸入長度達 {prompt_tokens} Tokens，顯著大於輸出長度 ({effective_output_tokens})，歸類為 Prefill-Bound 計算密集型。"

        # 2. 判斷 Decode-Bound
        elif effective_output_tokens >= cls.DECODE_TOKEN_THRESHOLD and (effective_output_tokens / max(1, prompt_tokens)) >= 1.5:
            workload = WorkloadType.DECODE_BOUND
            batching_hint = {
                "enable_chunked_prefill": False,
                "continuous_batching_priority": "latency_sensitive",
                "priority_queue": "low_latency_decode",
                "precision_preference": "fp16",
            }
            rationale = f"預期生成長度達 {effective_output_tokens} Tokens，歸類為 Decode-Bound 記憶體頻寬密集型。"

        # 3. 平衡型
        else:
            workload = WorkloadType.BALANCED
            batching_hint = {
                "enable_chunked_prefill": True,
                "chunk_size": 256,
                "priority_queue": "default",
                "precision_preference": "fp16",
            }
            rationale = f"輸入 ({prompt_tokens} Tokens) 與輸出 ({effective_output_tokens} Tokens) 分佈均衡，指派平衡型排程。"

        return {
            "workload_type": workload,
            "prompt_tokens": prompt_tokens,
            "expected_output_tokens": effective_output_tokens,
            "batching_hint": batching_hint,
            "rationale": rationale,
        }
