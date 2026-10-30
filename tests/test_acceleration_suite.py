"""
LLM 推論加速控制平面單元測試套件 (Acceleration Test Suite)
涵蓋 Canonical Prompt Layout, Cache-Aware Affinity Router,
Adaptive Speculative Gating, Selective Prompt Pruning,
Disaggregated Workload Splitting 以及 Dispatcher 端到端整合。
"""

import unittest
from router_app import (
    AdaptiveAgentDispatcher,
    AdaptiveRAGAdapter,
    InMemoryVectorRetriever,
    LLMAccelerationController,
    CacheAwareAffinityRouter,
    CanonicalPromptFormatter,
    AdaptiveSpeculativeGator,
    SelectivePromptPruner,
    DisaggregatedWorkloadSplitter,
    WorkerNode,
    WorkloadType,
    SpeculativeMode,
)


class TestAccelerationSuite(unittest.TestCase):
    """LLM 加速控制平面單元測試"""

    def test_canonical_prompt_formatter(self):
        """測試提示詞標準化佈局與確定性排序"""
        sys_prompt = "你是企業級資深系統架構師。"
        tools = [
            {"name": "zebra_tool", "description": "Zebra tool description"},
            {"name": "alpha_tool", "description": "Alpha tool description"},
        ]
        rag_context = [
            {"chunk_id": "c2", "content": "第二條核心規則"},
            {"chunk_id": "c1", "content": "第一條核心規則"},
        ]
        user_query = "請協助分析微服務架構。"

        res = CanonicalPromptFormatter.format(
            system_prompt=sys_prompt,
            tools=tools,
            rag_context=rag_context,
            user_query=user_query,
        )

        self.assertTrue(res.is_cache_friendly)
        self.assertEqual(len(res.sanitization_warnings), 0)
        self.assertIn("alpha_tool", res.static_prefix)
        # 驗證 tools 字母排序確定性: alpha_tool 應出現在 zebra_tool 之前
        alpha_idx = res.static_prefix.find("alpha_tool")
        zebra_idx = res.static_prefix.find("zebra_tool")
        self.assertLess(alpha_idx, zebra_idx)
        # 驗證 prefix_hash 存在
        self.assertEqual(len(res.prefix_hash), 16)
        # 驗證動態後綴包含用戶問題
        self.assertIn("請協助分析微服務架構。", res.dynamic_suffix)

    def test_canonical_prompt_dynamic_warning(self):
        """測試動態變數誤植 System Prompt 時的預警能力"""
        sys_prompt = "目前時間是 2026-10-30 10:15:00，你是助手。"
        res = CanonicalPromptFormatter.format(system_prompt=sys_prompt, user_query="你好")
        self.assertFalse(res.is_cache_friendly)
        self.assertGreater(len(res.sanitization_warnings), 0)

    def test_cache_aware_affinity_router(self):
        """測試前綴快取一致性親和性路由與命中率"""
        nodes = [
            WorkerNode(node_id="gpu_node_1", endpoint="http://10.0.0.1:8000/v1", capacity=10),
            WorkerNode(node_id="gpu_node_2", endpoint="http://10.0.0.2:8000/v1", capacity=10),
        ]
        router = CacheAwareAffinityRouter(nodes=nodes)

        prefix_a = "hash_system_hr_policy"
        # 第一次派發：Cache Miss，指派指定節點並建立快取綁定
        node_1, hit_1 = router.dispatch(prefix_a)
        self.assertFalse(hit_1)
        self.assertEqual(node_1.active_requests, 1)

        # 第二次相同前綴派發：Cache Hit，必定指派同一台節點
        node_2, hit_2 = router.dispatch(prefix_a)
        self.assertTrue(hit_2)
        self.assertEqual(node_1.node_id, node_2.node_id)
        self.assertEqual(node_2.active_requests, 2)

        # 釋放節點 Slot
        router.release(node_1.node_id)
        self.assertEqual(node_1.active_requests, 1)

        stats = router.get_stats()
        self.assertEqual(stats["total_routed"], 2)
        self.assertEqual(stats["cluster_cache_hits"], 1)
        self.assertEqual(stats["cluster_cache_hit_ratio"], 0.5)

    def test_adaptive_speculative_gator(self):
        """測試自適應推測解碼門控評估"""
        # 案例 1: JSON 格式化提取 -> 積極推測 (K=5)
        decision_json = AdaptiveSpeculativeGator.evaluate(
            query="請將訂單資訊整理成 JSON 格式並提取金額欄位",
            mode="mode_1_single_turn",
        )
        self.assertTrue(decision_json.enabled)
        self.assertEqual(decision_json.mode, SpeculativeMode.AGGRESSIVE)
        self.assertEqual(decision_json.draft_tokens, 5)
        self.assertGreater(decision_json.predicted_acceptance_rate, 0.75)

        # 案例 2: 複雜數理證明 -> 停用推測 (K=0) 避免 Rollback 負優化
        decision_math = AdaptiveSpeculativeGator.evaluate(
            query="請數學推演並證明黎曼幾何中高斯曲率之極限特徵",
            mode="mode_5_reflection",
        )
        self.assertFalse(decision_math.enabled)
        self.assertEqual(decision_math.mode, SpeculativeMode.OFF)
        self.assertEqual(decision_math.draft_tokens, 0)

        # 案例 3: 一般問答 -> 保守推測 (K=3)
        decision_normal = AdaptiveSpeculativeGator.evaluate(
            query="請問明天下午的專案例行會議有哪些核心議題？",
            mode="mode_2_react",
        )
        self.assertTrue(decision_normal.enabled)
        self.assertEqual(decision_normal.mode, SpeculativeMode.CONSERVATIVE)
        self.assertEqual(decision_normal.draft_tokens, 3)

    def test_selective_prompt_pruner(self):
        """測試選擇性提示詞去噪壓縮器與結構保護"""
        raw_text = (
            "您好！身為一個人工智慧語言模型，感謝您的提問，我將竭誠為您服務！\n\n\n\n"
            "以下為您提供範例代碼：\n"
            "```python\ndef calculate_sum(a, b):\n    return a + b\n```\n\n"
            "希望能對您有所幫助！若有任何問題歡迎隨時提問！！！"
        )
        res = SelectivePromptPruner.prune(raw_text)

        # 驗證代碼塊完好無損
        self.assertIn("```python\ndef calculate_sum(a, b):\n    return a + b\n```", res.compressed_text)
        # 驗證廢話套話被剔除
        self.assertNotIn("身為一個人工智慧語言模型", res.compressed_text)
        self.assertNotIn("我將竭誠為您服務", res.compressed_text)
        # 驗證 Token 確實被縮減
        self.assertLess(res.compressed_tokens, res.original_tokens)
        self.assertGreater(res.reduction_ratio, 0.15)
        self.assertLess(res.latency_ms, 5.0)  # 必須極致輕量 < 5ms

    def test_disaggregated_workload_splitter(self):
        """測試 Prefill-Decode 解耦工作負載分類"""
        # Prefill-Bound: 長文本輸入 (2500 tokens)，短輸出 (100 tokens)
        res_prefill = DisaggregatedWorkloadSplitter.classify(prompt_tokens=2500, expected_output_tokens=100)
        self.assertEqual(res_prefill["workload_type"], WorkloadType.PREFILL_BOUND)
        self.assertTrue(res_prefill["batching_hint"]["enable_chunked_prefill"])

        # Decode-Bound: 短輸入 (100 tokens)，長多步推理 (1200 tokens)
        res_decode = DisaggregatedWorkloadSplitter.classify(prompt_tokens=100, expected_output_tokens=1200)
        self.assertEqual(res_decode["workload_type"], WorkloadType.DECODE_BOUND)

        # Balanced: 500 tokens in, 300 tokens out
        res_balanced = DisaggregatedWorkloadSplitter.classify(prompt_tokens=500, expected_output_tokens=300)
        self.assertEqual(res_balanced["workload_type"], WorkloadType.BALANCED)

    def test_end_to_end_dispatcher_with_acceleration(self):
        """測試 Dispatcher 原生串接 RAG Adapter + LLM 加速控制器"""
        retriever = InMemoryVectorRetriever()
        retriever.add_document("doc_01", "2025 年伺服器總出貨量成長 54%，達到 18,500 台。")

        rag_adapter = AdaptiveRAGAdapter(retriever=retriever)
        acc_controller = LLMAccelerationController()

        dispatcher = AdaptiveAgentDispatcher(
            rag_adapter=rag_adapter,
            acceleration_controller=acc_controller,
            enable_logging=False,
        )

        query = "請查詢 2025 年伺服器出貨量並將結果格式化輸出為 JSON"
        res = dispatcher.process(query)

        self.assertTrue(res.success)
        # 驗證 RAG 檢索元數據
        self.assertIn("rag", res.metadata)
        self.assertEqual(res.metadata["rag"]["chunks_count"], 1)

        # 驗證 Acceleration 加速控制平面元數據
        self.assertIn("acceleration", res.metadata)
        acc_meta = res.metadata["acceleration"]
        self.assertIn("target_node_id", acc_meta)
        self.assertIn("prefix_hash", acc_meta)
        self.assertTrue(acc_meta["speculative_enabled"])
        self.assertEqual(acc_meta["speculative_draft_tokens"], 5)  # 命中 JSON 格式化


if __name__ == "__main__":
    unittest.main()
