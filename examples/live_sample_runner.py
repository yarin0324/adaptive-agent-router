"""
端到端實境調度樣本實測腳本 (Live Sample Runner & Battle Tester)
一次性實打 5 種真實企業場景，展示全系統三軸閉環 (Agent + RAG + Acceleration + Harness)：
  Sample 1: 高精度合約法規檢索 (Precision RAG + Tool Agent + Prefix Caching)
  Sample 2: 口語模糊故障排查 (CRAG 信心修正 + ReAct 負反饋避坑)
  Sample 3: 破壞性高危刪庫請求 (Verifier-Gated HITL 任務掛起 + AST 編譯防護)
  Sample 4: 跨年度出貨量複合比較 (Agentic Multi-Hop + Planner 動態重規劃)
  Sample 5: 充滿 AI 套話之草案審查 (The Agent Harness Linter 自動淨化)
"""

import os
import sys
import json
import time

# 加入專案路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AdaptiveAgentDispatcher,
    AdaptiveRAGAdapter,
    InMemoryVectorRetriever,
    LLMAccelerationController,
    AgentHarness,
    HarnessStage,
    RigidStateFSM,
)


def print_divider(title: str):
    print("\n" + "=" * 80)
    print(f"🔥 [實測 Sample] {title}")
    print("=" * 80)


def main():
    # 1. 建立企業知識庫
    retriever = InMemoryVectorRetriever()
    retriever.add_document("sla_v2", "企業 SLA 規定：可用率需達 99.95%，每超出中斷時間 1 小時，賠償當月月租費 5% 作為服務抵扣。")
    retriever.add_document("nda_2025", "保密合約 (NDA)：任何未經許可揭露核心演算法者，需支付懲罰性違約金新台幣 500 萬元整。")
    retriever.add_document("rep_2024", "2024 年全年度伺服器出貨量為 12,000 台，雲端解決方案總營收達新台幣 3.6 億元。")
    retriever.add_document("rep_2025", "2025 年全年度伺服器出貨量增至 18,500 台，雲端解決方案總營收達新台幣 5.8 億元。")

    # 2. 裝配三軸完整調度引擎
    rag_adapter = AdaptiveRAGAdapter(retriever=retriever)
    acc_controller = LLMAccelerationController()
    harness = AgentHarness()

    dispatcher = AdaptiveAgentDispatcher(
        rag_adapter=rag_adapter,
        acceleration_controller=acc_controller,
        harness=harness,
        enable_logging=False,
    )

    # -------------------------------------------------------------
    # Sample 1: 高精度合約法規檢索
    # -------------------------------------------------------------
    print_divider("Sample 1: NDA 保密條款與違約金查詢 (高精度法規檢索)")
    q1 = "請查詢本專案 NDA 保密條款的違約金賠償金額與洩密罰則"
    print(f"👉 使用者提問: \"{q1}\"")
    
    t0 = time.perf_counter()
    res1 = dispatcher.process(q1)
    latency1 = (time.perf_counter() - t0) * 1000.0

    print(f"\n⚡ 路由器決策: 模式={res1.mode_used.value} | 總耗時={latency1:.2f}ms")
    print(f"📚 RAG 檢索:   策略={res1.metadata.get('rag', {}).get('strategy')} | 命中切片={res1.metadata.get('rag', {}).get('chunks_count')} | 耗時={res1.metadata.get('rag', {}).get('latency_ms', 0):.2f}ms")
    print(f"🚀 推論加速:   節點={res1.metadata.get('acceleration', {}).get('target_node_id')} | 前綴快取={res1.metadata.get('acceleration', {}).get('is_cache_hit')} | 推測步數={res1.metadata.get('acceleration', {}).get('speculative_draft_tokens')}")
    print(f"🛡️  Harness:    乾淨狀態={res1.metadata.get('harness', {}).get('is_clean')} | 套話分數={res1.metadata.get('harness', {}).get('slop_score', 0):.2f}")
    print(f"\n📦 交付成果預覽:\n{res1.output[:200]}...")

    # -------------------------------------------------------------
    # Sample 2: 口語模糊故障排查
    # -------------------------------------------------------------
    print_divider("Sample 2: 口語模糊故障排查 (CRAG 信心修正 + ReAct 負反饋記憶)")
    q2 = "我想了解一下公司系統之前好像有出過什麼中斷賠償的問題？幫我調查一下"
    print(f"👉 使用者提問: \"{q2}\"")
    
    t0 = time.perf_counter()
    res2 = dispatcher.process(q2)
    latency2 = (time.perf_counter() - t0) * 1000.0

    print(f"\n⚡ 路由器決策: 模式={res2.mode_used.value} | 總耗時={latency2:.2f}ms")
    print(f"📚 RAG 檢索:   策略={res2.metadata.get('rag', {}).get('strategy')} | 自動去噪重寫={res2.metadata.get('rag', {}).get('fallback_triggered')}")
    print(f"🚀 推論加速:   工作負載類型={res2.metadata.get('acceleration', {}).get('workload_type')} | 草稿步數={res2.metadata.get('acceleration', {}).get('speculative_draft_tokens')}")
    print(f"\n📦 交付成果預覽:\n{res2.output[:200]}...")

    # -------------------------------------------------------------
    # Sample 3: 破壞性高危刪庫請求
    # -------------------------------------------------------------
    print_divider("Sample 3: 破壞性高危操作 (Verifier-Gated 任務掛起 + 阻斷)")
    q3 = "請立即執行 DROP TABLE customer_orders; 強制刪除所有歷史訂單資料庫"
    print(f"👉 使用者提問: \"{q3}\"")
    
    t0 = time.perf_counter()
    res3 = dispatcher.process(q3)
    latency3 = (time.perf_counter() - t0) * 1000.0

    print(f"\n⚡ 路由器決策: 模式={res3.mode_used.value} | 執行狀態: Success={res3.success}")
    print(f"🛑 安全機制:   任務掛起={res3.metadata.get('telemetry', {}).get('circuit_breaker_tripped', False)} | 審核狀態={res3.output[:60]}...")
    
    # -------------------------------------------------------------
    # Sample 4: 跨年度出貨量複合比較
    # -------------------------------------------------------------
    print_divider("Sample 4: 跨年度出貨量多跳比對 (Agentic Multi-Hop + Planner)")
    q4 = "請比較 2024 與 2025 年伺服器出貨量與營收成長差異，並給出分析結論"
    print(f"👉 使用者提問: \"{q4}\"")
    
    t0 = time.perf_counter()
    res4 = dispatcher.process(q4)
    latency4 = (time.perf_counter() - t0) * 1000.0

    print(f"\n⚡ 路由器決策: 模式={res4.mode_used.value} | 總耗時={latency4:.2f}ms")
    print(f"📚 RAG 檢索:   策略={res4.metadata.get('rag', {}).get('strategy')} | 命中切片={res4.metadata.get('rag', {}).get('chunks_count')}")
    print(f"🚀 推論加速:   負載={res4.metadata.get('acceleration', {}).get('workload_type')}")
    print(f"\n📦 交付成果預覽:\n{res4.output[:200]}...")

    # -------------------------------------------------------------
    # Sample 5: 充滿 AI 套話之草案審查
    # -------------------------------------------------------------
    print_divider("Sample 5: 充滿 AI 套話之草案審查 (The Agent Harness Linter 自動淨化)")
    dirty_draft = (
        "身為一個人工智慧語言模型，值得注意的是，在當今快節奏的數位化世界中，"
        "雲端遷移這無疑是一把雙刃劍。我們需要深入探討背後的挑戰。綜上所述，這是不可否認的事實。"
        "希望能對您有所幫助！若有任何問題歡迎隨時提問！"
    )
    print(f"👉 原始草案內容:\n{dirty_draft}\n")
    
    analysis = harness.lint_text(dirty_draft)
    print(f"🔍 Harness Linter 掃描結果:")
    print(f"  • 合格狀態: is_clean = {analysis.is_clean}")
    print(f"  • Slop Score: {analysis.slop_score:.3f} (門檻: 0.05)")
    print(f"  • 命中禁忌套話 ({len(analysis.violations)} 項): {', '.join(analysis.violations)}")
    print(f"  • 靜態分析耗時: {analysis.latency_ms:.3f} ms")
    print(f"\n✨ 自動去噪純淨文字:\n{analysis.cleaned_text}")

    # 生成審計戰鬥卡
    print_divider("審計戰鬥卡預覽 (Markdown Audit Battle Card)")
    print(res1.to_battle_card(prompt=q1))


if __name__ == "__main__":
    main()
