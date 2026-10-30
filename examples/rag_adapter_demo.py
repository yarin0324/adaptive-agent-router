"""
Adaptive RAG Adapter 端到端架構演練範例 (Adaptive RAG Showcase)
展示基於提問複雜度之 5 大自適應檢索策略：
1. No-RAG (0ms Direct LLM)
2. Fast Hybrid RAG (BM25 + Vector + RRF)
3. Precision RAG (FlashRank-style Cross-Encoder Rerank)
4. Corrective RAG (CRAG Confidence Gating & Query Reformulation)
5. Agentic Multi-Hop RAG (Query Decomposition & Provenance Tracking)
6. 與 AdaptiveAgentDispatcher 雙軸一體化調度
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AdaptiveAgentDispatcher,
    AdaptiveRAGAdapter,
    InMemoryVectorRetriever,
    RAGMode,
)


def main():
    print("=" * 75)
    print("Adaptive RAG Adapter - Context-Aware Strategy Verification")
    print("=" * 75)

    # 1. 建立示範知識庫 (企業內部營運、合約與法規切片)
    knowledge_base = [
        {
            "id": "kb_tax_01",
            "content": "鴻昇科技統一編號為 28459201，發票抬頭為鴻昇數位科技有限公司，開立二聯或三聯發票皆需載明。",
            "source": "finance_policy.md"
        },
        {
            "id": "kb_contract_nda",
            "content": "本專案 NDA 保密協議條款規定：任何涉及核心演算法與模型權重之營業秘密，未經書面許可不得對第三方披露，違者需支付懲罰性違約金新台幣 500 萬元。",
            "source": "legal_nda_v2.pdf"
        },
        {
            "id": "kb_contract_sla",
            "content": "企業級服務 SLA 條款：系統全年可用率需達 99.95%，每超出中斷時間 1 小時，賠償當月月租費 5% 作為服務抵扣。",
            "source": "sla_policy.md"
        },
        {
            "id": "kb_fin_2024",
            "content": "2024 年全年度伺服器出貨量為 12,000 台，雲端解決方案總營收達新台幣 3.6 億元，毛利率 42%。",
            "source": "annual_report_2024.pdf"
        },
        {
            "id": "kb_fin_2025",
            "content": "2025 年全年度伺服器出貨量增至 18,500 台，雲端解決方案總營收成長至新台幣 5.8 億元，毛利率提升至 46%。",
            "source": "annual_report_2025.pdf"
        },
        {
            "id": "kb_ops_deploy",
            "content": "產線微服務部署 SOP：所有映像檔必須通過 Trivy 弱點掃描，並由資安長簽核方可部署至 Kubernetes 叢集。",
            "source": "devops_sop.md"
        }
    ]

    retriever = InMemoryVectorRetriever(documents=knowledge_base)
    adapter = AdaptiveRAGAdapter(retriever=retriever)

    test_queries = [
        # 1. 閒聊 / 通用程式碼 -> No-RAG
        ("你好，請用 Python 寫一個快速排序演算法", "閒聊與通用演算法，無需外掛檢索"),

        # 2. 精確料號 / 統編 / 明確事實 -> Fast Hybrid RAG
        ("請問鴻昇科技的統一編號是多少？發票該如何開立？", "明確事實檢索，走 BM25 + 向量 RRF 混合召回"),

        # 3. 合約 / 保密 / 違約金條款 -> Precision Rerank
        ("這份 NDA 保密條款的洩密罰則與違約金賠償金額是多少？", "高精度法律條款，走 FlashRank 交叉重排序"),

        # 4. 模糊語句 / 易幻覺 -> Corrective RAG (CRAG)
        ("我想了解一下公司內部好像有提到什麼中斷賠償的事？", "口語模糊提問，觸發 CRAG 信心門控與去噪重寫"),

        # 5. 跨年份比較 / 多實體分析 -> Agentic Multi-Hop
        ("請比較 2024 與 2025 年伺服器出貨量與營收成長差異", "跨年份多實體比對，自動拆解子問題多跳探勘"),
    ]

    for idx, (query, intent_desc) in enumerate(test_queries, 1):
        print(f"\n--- [案例 {idx}] 提問: {query} ---")
        print(f"預期行為: {intent_desc}")

        # 1. 路由器決策
        decision = adapter.route(query)
        print(f"決策分流: {decision.mode.value} (複雜度: {decision.complexity_level}, 置信度: {decision.confidence})")
        print(f"判定理由: {decision.reasoning}")

        # 2. 執行檢索策略
        result = adapter.dispatch(query)
        print(f"檢索成果: 命中切片 {len(result.chunks)} 筆 | 耗時 {result.latency_ms} ms | 綜合信心 {result.confidence_score}")
        if result.transformed_query:
            print(f"改寫提問: {result.transformed_query}")

        for c_idx, chunk in enumerate(result.chunks, 1):
            src = f" ({chunk.source})" if chunk.source else ""
            print(f"  [{c_idx}] Score: {chunk.score:.4f}{src} -> {chunk.content[:70]}...")

    # 6. 雙軸一體化：將 Adaptive RAG 掛載至 AdaptiveAgentDispatcher
    print("\n" + "=" * 75)
    print("雙軸自適應整合驗證 (Adaptive Agent + Adaptive RAG Dual-Engine)")
    print("=" * 75)

    dispatcher = AdaptiveAgentDispatcher(
        rag_adapter=adapter,
        enable_logging=False
    )

    full_query = "請比較 2024 與 2025 年伺服器出貨量與營收成長，並產出結構化分析"
    exec_res = dispatcher.process(full_query)

    print(f"輸入問題: {full_query}")
    print(f"Agent 模式指派: {exec_res.mode_used.value}")
    print(f"RAG 檢索元數據: {exec_res.metadata.get('rag')}")
    print(f"執行狀態: Success={exec_res.success}")
    print(f"最終生成摘要 (預覽):\n{exec_res.output[:200]}...")
    print("=" * 75)


if __name__ == "__main__":
    main()
