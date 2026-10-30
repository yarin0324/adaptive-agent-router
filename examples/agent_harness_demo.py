"""
Agent 外骨骼治理架構展示 (The Agent Harness Showcase Demo)
設計理念源自 The Agent Harness 原則：
  "Code enforces rules, State machine tracks workflow, LLM only handles judgment."

展示四大關鍵外骨骼能力：
  1. AI Slop & Tone Linter (去 AI 味代碼靜態檢查器與自動去噪)
  2. Code-Enforced Rigid State Machine (代碼硬門控狀態機防偷懶跳步)
  3. Progressive Skill Disclosure (漸進式技能揭露與上下文 Token 節約)
  4. Clean-Room Subagents (無菌室隔離子代理防止上下文污染)
"""

import os
import sys

# 加入專案根目錄
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AdaptiveAgentDispatcher,
    AgentHarness,
    AISlopLinter,
    AISlopViolationException,
    RigidStateFSM,
    RigidGateException,
    HarnessStage,
    ProgressiveSkillRegistry,
    CleanRoomSubagentRunner,
)


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(title)
    print("=" * 75)


def run_harness_demo():
    print_banner("1. 去 AI 味靜態代碼檢查器 (AI Slop & Tone Linter)")
    dirty_text = (
        "您好！身為一個人工智慧語言模型，值得注意的是，這無疑是一個雙刃劍的複雜議題。"
        "我們需要深入探討背後的本質。綜上所述，這是不可否認的事實。"
        "希望能對您有所幫助！若有任何問題歡迎隨時提問！"
    )
    print("【原始充滿 AI 套話之文本】:\n" + dirty_text + "\n")

    analysis = AISlopLinter.lint(dirty_text)
    print(f"檢驗結果: is_clean = {analysis.is_clean} | Slop Score: {analysis.slop_score:.3f}")
    print(f"命中禁忌套話 ({len(analysis.violations)} 項): {', '.join(analysis.violations)}")
    print(f"靜態分析耗時: {analysis.latency_ms:.3f} ms")
    print("\n【自動去噪後的乾淨文本】:\n" + analysis.cleaned_text)

    # 驗證代碼硬門控阻斷
    try:
        AISlopLinter.assert_clean(dirty_text)
    except AISlopViolationException as e:
        print(f"\n[門控阻斷驗證] 成功阻斷非自然文本發布: {e}")

    print_banner("2. 代碼硬門控狀態機 (Code-Enforced Rigid State Machine)")
    print("演示『False Compliance 防禦』：LLM 無法僅靠語言謊稱通過，必須由代碼斷言放行！")
    
    fsm = RigidStateFSM(task_id="harness_task_2026")
    print(f"初始階段: {fsm.current_stage.value}")

    # 嘗試在空 Payload 情況下推進至 RESEARCH
    try:
        fsm.transition_to(HarnessStage.RESEARCH)
    except RigidGateException as e:
        print(f"\n[阻斷 1 成功] 嘗試推進至 RESEARCH 遭到攔截:\n  -> {e.failed_reasons[0]}")

    # 滿足條件 1: 填入明確任務定義
    fsm.update_payload(task_description="設計高可用微服務架構並產出部署 SOP")
    rec_res = fsm.transition_to(HarnessStage.RESEARCH)
    print(f"  -> 條件滿足，躍遷至: {rec_res.to_stage.value} (理由: {rec_res.verified_assertions[0]})")

    # 嘗試跳過佐證收集直接進入 DRAFT
    try:
        fsm.transition_to(HarnessStage.DRAFT)
    except RigidGateException as e:
        print(f"\n[阻斷 2 成功] 嘗試在缺乏佐證情況下推進至 DRAFT 遭到攔截:\n  -> {e.failed_reasons[0]}")

    # 滿足條件 2: 注入探勘證據
    fsm.update_payload(evidence_sources=["k8s_benchmarks.log", "load_test_report.csv"])
    rec_draft = fsm.transition_to(HarnessStage.DRAFT)
    print(f"  -> 佐證到位，躍遷至: {rec_draft.to_stage.value} (理由: {rec_draft.verified_assertions[0]})")

    # 滿足條件 3: 撰寫草稿並推進至 AUDIT
    fsm.update_payload(draft_content="生產環境全面啟用 HPA 自動水平擴展，並限制容器 CPU 資源上限。")
    rec_audit = fsm.transition_to(HarnessStage.AUDIT)
    print(f"  -> 草稿完成，躍遷至: {rec_audit.to_stage.value} (理由: {rec_audit.verified_assertions[0]})")

    # 嘗試在無資安簽核前發布 (SHIP)
    try:
        fsm.transition_to(HarnessStage.SHIP)
    except RigidGateException as e:
        print(f"\n[阻斷 3 成功] 嘗試在缺乏資安簽核情況下發布遭到攔截:\n  -> {e.failed_reasons[0]}")

    # 滿足條件 4: 資安簽核通過 -> 正式 SHIP
    fsm.update_payload(security_verified=True)
    rec_ship = fsm.transition_to(HarnessStage.SHIP)
    print(f"  -> 終審全數合格！成功躍遷至: {rec_ship.to_stage.value} (Payload Hash: {rec_ship.payload_hash})")
    print(f"  -> 歷史躍遷總步數: {len(fsm.transition_history)} 步，全程受代碼嚴格審計。")

    print_banner("3. 漸進式技能揭露 (Progressive Skill Disclosure)")
    registry = ProgressiveSkillRegistry()
    registry.register(
        name="finance_calc",
        summary="財務與投資報酬率量化計算器",
        category="finance",
        full_instructions="支援 IRR, NPV, Sharpe Ratio 與複利折現模型，計算過程保留小數點後四位。",
        parameters_schema={"type": "object", "properties": {"cash_flows": {"type": "array"}}},
    )
    registry.register(
        name="sql_ast_query",
        summary="編譯器 AST 唯讀安全防護之 SQL 查詢工具",
        category="database",
        full_instructions="僅允許 SELECT 查詢，必須強制包含 WITH (NOLOCK)，嚴禁所有 DDL/DML 語句。",
        parameters_schema={"type": "object", "properties": {"sql": {"type": "string"}}},
    )

    print("【常態常駐極簡目錄預覽 (Compact Index)】:\n" + registry.get_compact_index())
    
    savings = registry.calculate_token_savings()
    print(f"\nToken 節約效益: 常駐 Token: {savings['compact_index_tokens']} | 全展開 Token: {savings['full_disclosure_tokens']}")
    print(f"上下文節省率: {savings['saving_ratio']*100:.1f}% (徹底解決 Lost-in-the-Middle 困境)")

    print("\n【隨需展開單一技能 (On-Demand Resolution)】:")
    resolved = registry.resolve_skills(["sql_ast_query"])
    print(resolved[:240] + "...\n")

    print_banner("4. 無菌室子代理隔離執行 (Clean-Room Subagents)")
    def scrape_and_analyze_database(table_name: str, sample_size: int):
        # 模擬繁雜的資料探勘過程 (100 次資料庫操作不外洩至主上下文)
        return {
            "summary": f"無菌室探勘完成：已分析 {table_name} 內 {sample_size} 筆樣本，異常率低於 0.02%。",
            "artifacts": {"table": table_name, "sample_size": sample_size, "anomaly_rate": 0.0018},
            "tokens_consumed": 520,
        }

    sub_res = CleanRoomSubagentRunner.execute_in_clean_room(
        subagent_id="subagent_db_profiler",
        task_description="獨立無菌室分析資料庫健康度",
        task_fn=scrape_and_analyze_database,
        table_name="production_orders",
        sample_size=1000,
    )
    print(f"子代理 ID: {sub_res.subagent_id} | 成功: {sub_res.success} | 耗時: {sub_res.execution_time_ms} ms")
    print(f"繳回主上下文之精華摘要: {sub_res.summary_output}")
    print(f"結構化產物: {sub_res.structured_artifacts}")
    print("主對話上下文視窗：保持 100% 乾淨無污染！")

    print_banner("5. 端到端 Dispatcher 整合 (Agent Harness Quality Gate)")
    harness = AgentHarness()
    dispatcher = AdaptiveAgentDispatcher(
        harness=harness,
        enable_logging=False,
    )
    result = dispatcher.process("請總結企業微服務架構治理方案")
    print(f"執行狀態: Success={result.success}")
    print(f"Harness 品質門控審查: {result.metadata.get('harness')}")
    print("=" * 75)


if __name__ == "__main__":
    run_harness_demo()
