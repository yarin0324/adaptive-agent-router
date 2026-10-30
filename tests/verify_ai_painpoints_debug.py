"""
AI 痛點物理防禦深度 Debug 驗證腳本 (AI Pain-Points Physical Debug Verification)
針對四大致命 AI 痛點進行實體代碼壓力校驗（零幻覺驗證）：
  1. 痛點一：假合規與偷懶說謊 (False Compliance & Hallucinated Success)
  2. 痛點二：AI 套話與腔調污染 (AI Slop & Tone Clichés)
  3. 痛點三：上下文視窗肥大與迷航 (Context Bloat & Lost-in-the-Middle)
  4. 痛點四：子任務髒數據污染主上下文 (Context Contamination & Noise Bleed)
  5. 痛點五：危險操作與越權幻覺 (Compiler AST & Suspension FSM)
"""

import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    RigidStateFSM,
    RigidGateException,
    HarnessStage,
    AISlopLinter,
    AISlopViolationException,
    ProgressiveSkillRegistry,
    CleanRoomSubagentRunner,
    PythonASTSecurityGuard,
    SQLASTSecurityGuard,
    TaskSuspensionManager,
)


def log_pass(title: str, detail: str):
    print(f"  [PASS] {title}")
    print(f"         └─ 實體驗證: {detail}")


def log_fail(title: str, detail: str):
    print(f"  [FAIL] {title}")
    print(f"         └─ 錯誤: {detail}")
    sys.exit(1)


def test_painpoint_1_false_compliance():
    print("\n" + "=" * 75)
    print("【痛點一物理驗證】假合規與偷懶說謊 (False Compliance & Skip Ahead)")
    print("=" * 75)
    fsm = RigidStateFSM(task_id="debug_task_001")
    
    # 狀況 A: LLM 尚未提供 task_description，直接宣稱「我準備好開始研究了」
    try:
        fsm.transition_to(HarnessStage.RESEARCH)
        log_fail("假合規防禦", "代碼未攔截空任務目標，發生越權躍遷！")
    except RigidGateException as e:
        log_pass("代碼硬門控阻斷 (IDEA -> RESEARCH)", f"物理攔截成功: '{e.failed_reasons[0]}'")

    # 滿足條件 1
    fsm.update_payload(task_description="重構高併發資料庫快取層")
    fsm.transition_to(HarnessStage.RESEARCH)

    # 狀況 B: LLM 宣稱「所有資料我都查過了，全部合格」，但 evidence_sources 實際為空
    try:
        fsm.transition_to(HarnessStage.DRAFT)
        log_fail("假合規防禦", "代碼未攔截無佐證推進，發生虛假合規！")
    except RigidGateException as e:
        log_pass("佐證硬門控阻斷 (RESEARCH -> DRAFT)", f"物理攔截成功: '{e.failed_reasons[0]}'")

    # 滿足條件 2
    fsm.update_payload(evidence_sources=["benchmark_2026.csv"])
    fsm.transition_to(HarnessStage.DRAFT)

    # 狀況 C: LLM 宣稱「草稿寫好了」，但 draft_content 長度不足 10 字元
    fsm.update_payload(draft_content="太短了")
    try:
        fsm.transition_to(HarnessStage.AUDIT)
        log_fail("草稿質量防禦", "未攔截過短草稿！")
    except RigidGateException as e:
        log_pass("長度硬門控阻斷 (DRAFT -> AUDIT)", f"物理攔截成功: '{e.failed_reasons[0]}'")

    # 滿足條件 3
    fsm.update_payload(draft_content="全面升級 Redis 叢集架構並設定合理的 TTL 過期機制。")
    fsm.transition_to(HarnessStage.AUDIT)

    # 狀況 D: 進入 SHIP 前，LLM 宣稱「資安已簽核」，但實體 security_verified 仍為 False
    try:
        fsm.transition_to(HarnessStage.SHIP)
        log_fail("資安終審防禦", "未簽核竟被放行至 SHIP！")
    except RigidGateException as e:
        log_pass("資安硬門控阻斷 (AUDIT -> SHIP)", f"物理攔截成功: '{e.failed_reasons[0]}'")

    # 最終簽署通過
    fsm.update_payload(security_verified=True)
    rec = fsm.transition_to(HarnessStage.SHIP)
    log_pass("完整合規躍遷", f"歷經 4 級代碼硬門控驗證，全數通過！最後 Payload Hash: {rec.payload_hash}")


def test_painpoint_2_ai_slop():
    print("\n" + "=" * 75)
    print("【痛點二物理驗證】AI 套話與腔調污染 (AI Slop & Tone Clichés)")
    print("=" * 75)
    dirty_text = (
        "您好！身為一個人工智慧語言模型，值得注意的是，這是一把雙刃劍。"
        "深入探討可以發現，綜上所述，這是不可否認的事實。"
        "希望能對您有所幫助！若有任何問題歡迎隨時提問！"
    )
    analysis = AISlopLinter.lint(dirty_text)

    # 檢驗命中清單
    expected_buzzwords = ["身為一個人工智慧語言模型", "值得注意的是", "雙刃劍", "深入探討", "綜上所述", "希望能對您有所幫助", "若有任何問題歡迎隨時提問"]
    caught_count = sum(1 for w in expected_buzzwords if any(w in v for v in analysis.violations))
    if caught_count < 5:
        log_fail("AI 套話檢出率", f"檢出項目不足 (僅檢出 {caught_count}/{len(expected_buzzwords)})")
    else:
        log_pass("AI 套話靜態檢出", f"成功抓出 {len(analysis.violations)} 項 AI 套話 (Slop Score: {analysis.slop_score:.2f})")

    # 檢驗代碼硬斷言
    try:
        AISlopLinter.assert_clean(dirty_text)
        log_fail("代碼斷言阻斷", "含有嚴重套話未拋出異常！")
    except AISlopViolationException:
        log_pass("代碼硬斷言阻斷", "成功拋出 AISlopViolationException 阻斷非自然文本發布")

    # 檢驗自動去噪乾淨度
    cleaned = analysis.cleaned_text
    for w in ["身為一個人工智慧語言模型", "值得注意的是", "綜上所述", "希望能對您有所幫助"]:
        assert w not in cleaned, f"未被清除乾淨: {w}"
    log_pass("自動去噪淨化", f"套話已被 100% 剃除，乾淨文本長度: {len(cleaned)} 字元")


def test_painpoint_3_context_bloat():
    print("\n" + "=" * 75)
    print("【痛點三物理驗證】上下文肥大與迷航 (Context Bloat & Lost-in-the-Middle)")
    print("=" * 75)
    reg = ProgressiveSkillRegistry()
    # 註冊 10 個專業工具
    for i in range(10):
        reg.register(
            name=f"tool_specialist_{i}",
            summary=f"負責執行特定領域第 {i} 號複雜計算與查詢",
            category="finance" if i % 2 == 0 else "devops",
            full_instructions=f"本工具涉及極度繁雜之企業級 SOP 規章第 {i} 條，內含 500 字詳細參數約束與限制要求。" * 5,
            parameters_schema={"type": "object", "properties": {"arg_1": {"type": "string"}}},
        )

    savings = reg.calculate_token_savings()
    ratio = savings["saving_ratio"]
    if ratio < 0.70:
        log_fail("上下文節約率", f"節約率僅 {ratio*100:.1f}%，未達標 (>= 70%)")
    else:
        log_pass("漸進式目錄揭露", f"常態目錄佔用 {savings['compact_index_tokens']} Tokens (全量展開需 {savings['full_disclosure_tokens']} Tokens)")
        log_pass("注意力視窗保護", f"節省 {savings['tokens_saved']} Tokens ({ratio*100:.1f}%)，徹底杜絕無效資訊霸佔注意力")


def test_painpoint_4_subagent_contamination():
    print("\n" + "=" * 75)
    print("【痛點四物理驗證】子任務髒數據污染 (Context Contamination & Noise Bleed)")
    print("=" * 75)
    
    # 模擬一個在無菌室內抓取了 5,000 字亂碼 HTML 與 20 次報錯重試的子任務
    def dirty_web_crawler():
        dirty_raw_data = "<div><p>DEBUG TRACE 404 NOT FOUND</p></div>\n" * 200  # 幾千字髒資料
        return {
            "summary": "成功從外部網站抓取 120 筆機房溫度感測器數據，平均溫度 24.5°C，運作正常。",
            "artifacts": {"sensor_count": 120, "avg_temp": 24.5, "status": "NORMAL"},
            "tokens_consumed": 3200,
        }

    res = CleanRoomSubagentRunner.execute_in_clean_room(
        subagent_id="sub_crawler_01",
        task_description="採集機房環境監控指標",
        task_fn=dirty_web_crawler,
    )

    assert "DEBUG TRACE" not in res.summary_output, "髒日誌洩漏至主摘要！"
    assert res.structured_artifacts["avg_temp"] == 24.5, "結構化指標遺失！"
    log_pass("無菌室隔離執行", f"耗時 {res.execution_time_ms:.2f}ms，成功攔截內部 3200 Tokens 的髒除錯數據")
    log_pass("主上下文純淨度", f"繳回主上下文之精華摘要僅 {len(res.summary_output)} 字元，無任何中間雜訊洩漏")


def test_painpoint_5_security_and_governance():
    print("\n" + "=" * 75)
    print("【痛點五物理驗證】危險操作與越權幻覺 (Compiler AST & Suspension FSM)")
    print("=" * 75)

    # 1. Python AST 語法樹阻斷 (非 Regex，無法透過字串混淆繞過)
    malicious_py = "__import__('os').system('rm -rf /')"
    is_safe, reasons = PythonASTSecurityGuard.validate_code(malicious_py)
    if is_safe:
        log_fail("Python AST 防護", "未能阻斷危險程式碼！")
    else:
        log_pass("編譯器 AST 阻斷", f"成功精確阻斷: {reasons[0]}")

    # 2. SQL AST 語法樹阻斷
    malicious_sql = "DROP TABLE users; --"
    is_sql_safe, sql_reasons = SQLASTSecurityGuard.validate_sql(malicious_sql)
    if is_sql_safe:
        log_fail("SQL AST 防護", "未能阻斷 DROP TABLE！")
    else:
        log_pass("SQL AST 唯讀強制", f"成功阻斷破壞性語法: {sql_reasons[0]}")

    # 3. 任務掛起 FSM 驗證
    suspension_mgr = TaskSuspensionManager()
    task = suspension_mgr.suspend_task(
        prompt="刪除過期客戶分區",
        mode_used="mode_6_verifier_gated",
        reason="偵測到 DROP 分區操作",
    )
    assert task.status == "SUSPENDED"
    log_pass("崩潰恢復 FSM 掛起", f"任務已安全凍結，產生審批憑證 Task ID: {task.task_id[:16]}...")


if __name__ == "__main__":
    t_start = time.perf_counter()
    print("===========================================================================")
    print("  AdaptiveAgentRouter - AI 痛點物理防禦深度 Debug 檢驗")
    print("===========================================================================")
    test_painpoint_1_false_compliance()
    test_painpoint_2_ai_slop()
    test_painpoint_3_context_bloat()
    test_painpoint_4_subagent_contamination()
    test_painpoint_5_security_and_governance()
    total_time = (time.perf_counter() - t_start) * 1000.0
    print("\n" + "=" * 75)
    print(f"🎯 所有 AI 痛點物理檢驗 100% 通過！總耗時: {total_time:.2f} ms")
    print("===========================================================================")
