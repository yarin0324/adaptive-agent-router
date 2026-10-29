"""
=============================================================================
AdaptiveAgentRouter - 全模式端到端真實效果展示 (All Modes & Models Showcase)
逐一示範 9 大核心執行模式與對應 Model Tier 算力階層的物理輸出與內部機制。
=============================================================================
"""

import os
import sys
import asyncio
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AdaptiveAgentDispatcher,
    AgentMode,
    ModelTier,
    StreamEventType,
)


def print_banner(title: str):
    print("\n" + "=" * 76)
    print(f"  {title}")
    print("=" * 76)


def main():
    dispatcher = AdaptiveAgentDispatcher(enable_logging=False)

    print_banner("AdaptiveAgentRouter - Complete Architectural Showcase")

    cases = [
        (
            "1. 增強型單次回應 (Single-Turn Augmented Mode)",
            "請幫我從這段採購單文字中，萃取統編 28459201 與採購總金額 $128,500 並轉為表格",
            AgentMode.SINGLE_TURN,
            ModelTier.FAST,
        ),
        (
            "2. 探索反思迴圈 (ReAct with Negative Observation Memory)",
            "幫我調查為什麼這條微服務 API 延遲突然飆高到 3000ms？找找看可能原因與解法",
            AgentMode.REACT,
            ModelTier.STANDARD,
        ),
        (
            "3. 動態規劃執行器 (Planner-Executor with Dynamic Replanner)",
            "公司計畫導入高併發 OCR 票據識別自動化管線，請提出架構規劃與完整步驟分解",
            AgentMode.PLANNER_EXECUTOR,
            ModelTier.REASONING,
        ),
        (
            "4. 評估-優化反思 (Reflexion Rubric Scoring: Threshold >= 8.5)",
            "這份商業合約的保密條款與智慧財產權條例請嚴格審查，挑出漏洞並多輪批評反思優化",
            AgentMode.REFLECTION,
            ModelTier.REASONING,
        ),
        (
            "5. 驗證門控人機協同 (Verifier-Gated with Dry-Run Diff Simulation)",
            "連線正式資料庫，強制刪除所有已過期的測試訂單資料表 (DROP TABLE)",
            AgentMode.VERIFIER_GATED,
            ModelTier.STANDARD,
        ),
        (
            "6. 對抗辯論協作 (Multi-Agent Dialectical Debate with Early Stopping)",
            "針對企業大模型地端部署 vs 雲端 API 選型進行跨部門評估，請安排正反方專家辯論",
            AgentMode.MULTI_AGENT,
            ModelTier.REASONING,
        ),
        (
            "7. 專用工具調用 (Tool Agent with Compiler AST Protection)",
            "請調用資料庫查詢工具，檢索客戶編號 CUST-8802 的最新收貨地址與聯絡電話",
            AgentMode.TOOL_USE,
            ModelTier.FAST,
        ),
        (
            "8. 並行自洽投票 (Self-Consistency Ensemble Voting)",
            "針對複雜的容錯演算法進行並行多數決推理計算，排除單一模型的偶然性幻覺",
            AgentMode.ENSEMBLE,
            ModelTier.REASONING,
        ),
        (
            "9. 情境式記憶增強 (Contextual Memory Augmented with Pure Python RRF)",
            "請說明本專案資料庫查詢的防死鎖與 WITH (NOLOCK) 規範",
            AgentMode.MEMORY_AUGMENTED,
            ModelTier.FAST,
        ),
    ]

    for title, prompt, expected_mode, expected_tier in cases:
        print_banner(title)
        print(f"👉 使用者輸入 (Prompt): \"{prompt}\"")

        # 執行調度
        decision = dispatcher.router.route(prompt)
        print(f"🧭 路由器分流決策:")
        print(f"  • 指派架構模式: {decision.mode.value} (預期: {expected_mode.value})")
        print(f"  • 匹配算力階層: {decision.model_tier.value.upper()} (預期: {expected_tier.value.upper()})")
        print(f"  • 決策判定依據: {decision.reasoning}")
        print(f"  • 風險等級評定: {decision.risk_level.value.upper()} | 需人工審批: {decision.require_human_confirmation}")

        # 若為門控掛起，演示掛起攔截與喚醒
        if decision.require_human_confirmation:
            print("\n🚨 [安全門控機制觸發]")
            result = dispatcher.process(prompt)
            print(f"  狀態: 任務已自動掛起 (Task ID: {result.metadata.get('task_id')})")
            print(f"  乾跑預覽 (Dry-Run Diff):")
            # 模擬管理者審批放行
            task_id = result.metadata.get("task_id")
            if task_id:
                print(f"  👤 管理人員收到 Diff 報告，按下 [APPROVED] 放行訊號...")
                resumed = dispatcher.resume_task(task_id, approved=True)
                print(f"  喚醒執行結果: {resumed.output.strip()[:180]}...")
        else:
            # 實際執行
            result = dispatcher.process(prompt, forced_mode=decision.mode)
            print(f"\n📦 模式執行實際成果 (Output Preview):")
            # 縮排印出結果
            for line in result.output.strip().split("\n"):
                print(f"  {line}")
            print(f"\n📊 遙測指標: 消耗 Tokens: {result.total_tokens_used} | 步數: {len(result.execution_steps)}")

    # -------------------------------------------------------------------------
    # 10. 演示非同步 SSE 串流動態效果
    # -------------------------------------------------------------------------
    print_banner("10. 非同步即時串流輸出效果 (Async Streaming SSE Live Demo)")
    stream_prompt = "請幫我分析微服務叢集架構並整理出三點核心結論"
    print(f"👉 串流請求: \"{stream_prompt}\"\n")

    async def run_live_stream():
        chunk_count = 0
        async for chunk in dispatcher.aprocess_stream(stream_prompt):
            chunk_count += 1
            if chunk.event in [StreamEventType.ROUTE_START, StreamEventType.ROUTE_DECIDED]:
                print(f"  ⚡ [{chunk.event.value:<14}] {chunk.message}")
            elif chunk.event == StreamEventType.STEP_PROGRESS:
                print(f"  ⚙️  [{chunk.event.value:<14}] {chunk.message}")
            elif chunk.event == StreamEventType.CONTENT_CHUNK:
                if chunk.delta and chunk.delta.strip():
                    print(f"    📝 [SSE Token] {chunk.delta.strip()[:70]}")
            elif chunk.event == StreamEventType.TASK_COMPLETED:
                print(f"  ✅ [{chunk.event.value:<14}] {chunk.message} (總事件數: {chunk_count})")

    asyncio.run(run_live_stream())

    print("\n" + "=" * 76)
    print("  All 10 Agent Modes & Model Tiers Demonstrated Successfully.")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
