"""
LLM 推論加速控制平面展示 (LLM Inference Acceleration & Serving Demo)
展示五大關鍵提速技術：
  1. Canonical Prompt Layout (提示詞標準化佈局與確定性前綴雜湊)
  2. Cache-Aware Affinity Routing (前綴快取一致性雜湊親和性路由)
  3. Adaptive Speculative Decoding Gator (自適應推測解碼門控)
  4. Selective Prompt Pruner (語意去噪與結構保護壓縮)
  5. Disaggregated Workload Splitter (Prefill/Decode 解耦分類)
  6. AdaptiveAgentDispatcher 端到端整合
"""

import os
import sys
import json

# 加入專案路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
)


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(title)
    print("=" * 75)


def run_acceleration_demo():
    print_banner("1. 提示詞標準化佈局 (Canonical Layout & Prefix Caching)")
    tools = [
        {"name": "zebra_export", "description": "匯出資料"},
        {"name": "alpha_lookup", "description": "查詢客戶資料庫"},
    ]
    rag_docs = [
        {"chunk_id": "doc_02", "content": "企業 SLA 條款：系統全年可用率需達 99.95%。"},
        {"chunk_id": "doc_01", "content": "統一編號：28459201，發票抬頭為鴻昇數位科技。"},
    ]
    canonical_res = CanonicalPromptFormatter.format(
        system_prompt="你是由企業資安嚴格審核之智慧助手。",
        tools=tools,
        rag_context=rag_docs,
        user_query="請查詢客戶統編與 SLA",
    )
    print(f"靜態前綴長度: {len(canonical_res.static_prefix)} 字元")
    print(f"前綴指紋 (Prefix Hash): {canonical_res.prefix_hash}")
    print(f"快取友善評估: {canonical_res.is_cache_friendly}")
    print("靜態前綴預覽 (已保證 Tools 與 RAG 確定性排序):\n" + canonical_res.static_prefix[:220] + "...\n")

    print_banner("2. 快取感知親和性路由 (Cache-Aware Affinity Routing)")
    nodes = [
        WorkerNode(node_id="vllm_node_alpha", endpoint="http://gpu-01:8000/v1", gpu_type="H100-SXM5", capacity=16),
        WorkerNode(node_id="vllm_node_beta", endpoint="http://gpu-02:8000/v1", gpu_type="H100-SXM5", capacity=16),
    ]
    affinity_router = CacheAwareAffinityRouter(nodes=nodes)

    requests = [
        ("req_1", canonical_res.prefix_hash, "請求 1 (初次進線)"),
        ("req_2", canonical_res.prefix_hash, "請求 2 (相同前綴)"),
        ("req_3", canonical_res.prefix_hash, "請求 3 (相同前綴)"),
        ("req_4", "another_hash_9999", "請求 4 (不同業務前綴)"),
        ("req_5", canonical_res.prefix_hash, "請求 5 (相同前綴)"),
    ]

    for req_id, p_hash, desc in requests:
        target_node, is_hit = affinity_router.dispatch(p_hash)
        status = "HIT (命中本地 KV Cache)" if is_hit else "MISS (首字計算並建立快取)"
        print(f"  [{req_id}] {desc} -> 分派至: {target_node.node_id} | 狀態: {status}")

    stats = affinity_router.get_stats()
    print(f"\n叢集整體表現: 總請求數: {stats['total_routed']} | 快取命中次數: {stats['cluster_cache_hits']} | 命中率: {stats['cluster_cache_hit_ratio']*100:.1f}%")

    print_banner("3. 自適應推測解碼門控 (Adaptive Speculative Decoding)")
    test_queries = [
        ("請提取客戶訂單中的統編與總金額，輸出為乾淨的 JSON 欄位", "mode_1_single_turn"),
        ("請推導並以數學歸納法證明高階張量收縮運算的極限複雜度", "mode_5_reflection"),
        ("請為我們安排下週二的產品規劃跨部門審查會議議程", "mode_2_react"),
    ]

    for q, m in test_queries:
        dec = AdaptiveSpeculativeGator.evaluate(q, mode=m)
        print(f"提問: {q[:35]}...")
        print(f"  模式傾向: {dec.mode.value} | 啟用推測: {dec.enabled} | 草稿步數 (K): {dec.draft_tokens}")
        print(f"  預估接受率: {dec.predicted_acceptance_rate*100:.0f}% | 預估加速比: {dec.estimated_speedup:.2f}x")
        print(f"  理由: {dec.rationale}\n")

    print_banner("4. 選擇性提示詞去噪壓縮 (Selective Prompt Pruner)")
    verbose_prompt = (
        "您好！身為一個人工智慧語言模型，非常感謝您的提問，我將竭誠為您服務！\n\n\n\n"
        "針對您的需求，以下為您提供專案的核心演算法實作代碼：\n"
        "```python\n"
        "def compute_hash(data: str) -> str:\n"
        "    return hashlib.sha256(data.encode()).hexdigest()\n"
        "```\n\n"
        "希望以上說明能對您的開發有所幫助！若後續有任何問題歡迎隨時提問！！！"
    )
    compress_res = SelectivePromptPruner.prune(verbose_prompt)
    print(f"原始 Token 數: {compress_res.original_tokens} | 壓縮後: {compress_res.compressed_tokens}")
    print(f"去噪率: {compress_res.reduction_ratio*100:.1f}% | 運算耗時: {compress_res.latency_ms:.3f} ms")
    print("壓縮後文字預覽 (代碼塊 100% 完整保留):\n---\n" + compress_res.compressed_text + "\n---")

    print_banner("5. Prefill-Decode 解耦工作負載分類 (Disaggregated Splitter)")
    workload_samples = [
        ("長篇合約審查", 3200, 150),
        ("多步複雜代碼生成", 200, 1200),
        ("日常對話即問即答", 450, 250),
    ]
    for name, p_tok, out_tok in workload_samples:
        w_res = DisaggregatedWorkloadSplitter.classify(prompt_tokens=p_tok, expected_output_tokens=out_tok)
        print(f"場景: {name} (輸入: {p_tok}t, 輸出: {out_tok}t) -> 工作類型: {w_res['workload_type'].value}")
        print(f"  排程建議: {w_res['rationale']}")
        print(f"  批次參數: {w_res['batching_hint']}\n")

    print_banner("6. 端到端 Dispatcher 整合 (RAG + Agent + LLM 加速控制器)")
    retriever = InMemoryVectorRetriever()
    retriever.add_document("sla_doc", "企業級 SLA 條款：全年可用率 99.95%，超出中斷每小時扣抵 5% 費用。")

    acc_ctrl = LLMAccelerationController()
    dispatcher = AdaptiveAgentDispatcher(
        rag_adapter=AdaptiveRAGAdapter(retriever=retriever),
        acceleration_controller=acc_ctrl,
        enable_logging=False,
    )

    query = "請查詢企業 SLA 賠償規定並將各項指標整理為 JSON 格式"
    result = dispatcher.process(query)

    print(f"執行狀態: Success={result.success}")
    print(f"RAG 檢索元數據: {result.metadata.get('rag')}")
    print(f"LLM 加速元數據: {result.metadata.get('acceleration')}")
    print("=" * 75)


if __name__ == "__main__":
    run_acceleration_demo()
