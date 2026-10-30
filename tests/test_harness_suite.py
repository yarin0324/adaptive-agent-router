"""
Agent 外骨骼治理層 (The Agent Harness) 單元測試套件
涵蓋去 AI 味靜態檢查器 (AISlopLinter)、代碼硬門控狀態機 (RigidStateFSM)、
漸進式技能註冊表 (ProgressiveSkillRegistry)、無菌室子代理隔離執行 (CleanRoomSubagentRunner)
以及 Dispatcher 端到端整合。
"""

import unittest
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


class TestHarnessSuite(unittest.TestCase):
    """The Agent Harness 單元測試"""

    def test_slop_linter_detection(self):
        """測試去 AI 味靜態檢查器之檢出率與自動去噪"""
        dirty_text = (
            "您好！身為一個人工智慧語言模型，值得注意的是，這無疑是一個雙刃劍的議題。"
            "我們需要深入探討背後的本質。綜上所述，這是不可否認的事實。"
            "希望能對您有所幫助！若有任何問題歡迎隨時提問！"
        )
        analysis = AISlopLinter.lint(dirty_text)

        self.assertFalse(analysis.is_clean)
        self.assertGreater(analysis.slop_score, 0.05)
        self.assertGreaterEqual(len(analysis.violations), 4)
        
        # 驗證自動去噪功能
        cleaned = analysis.cleaned_text
        self.assertNotIn("身為一個人工智慧語言模型", cleaned)
        self.assertNotIn("值得注意的是", cleaned)
        self.assertNotIn("綜上所述", cleaned)
        self.assertNotIn("希望能對您有所幫助", cleaned)

        # 驗證斷言阻斷異常
        with self.assertRaises(AISlopViolationException):
            AISlopLinter.assert_clean(dirty_text)

    def test_slop_linter_clean_text(self):
        """測試專業乾淨文本不受誤殺"""
        clean_text = "系統架構已重構完成。資料庫連線池上限提升至 50，查詢延遲降低 35%。"
        analysis = AISlopLinter.lint(clean_text)
        self.assertTrue(analysis.is_clean)
        self.assertEqual(len(analysis.violations), 0)
        # 斷言不應拋出異常
        AISlopLinter.assert_clean(clean_text)

    def test_rigid_state_fsm_gate_blocking(self):
        """測試代碼硬門控對偷懶跳步與未滿足條件之阻斷"""
        fsm = RigidStateFSM(task_id="task_audit_001")
        self.assertEqual(fsm.current_stage, HarnessStage.IDEA)

        # 案例 1: 尚未提供任務描述，嘗試推進至 RESEARCH -> 必須拋出 RigidGateException
        with self.assertRaises(RigidGateException) as ctx:
            fsm.transition_to(HarnessStage.RESEARCH)
        self.assertIn("任務目標描述為空", str(ctx.exception))

        # 填入合法任務描述後，成功躍遷
        fsm.update_payload(task_description="重構高併發資料庫快取層")
        rec_1 = fsm.transition_to(HarnessStage.RESEARCH)
        self.assertEqual(fsm.current_stage, HarnessStage.RESEARCH)
        self.assertEqual(rec_1.to_stage, HarnessStage.RESEARCH)

        # 案例 2: 尚未收集佐證依據，嘗試推進至 DRAFT -> 必須拋出異常阻斷
        with self.assertRaises(RigidGateException) as ctx:
            fsm.transition_to(HarnessStage.DRAFT)
        self.assertIn("尚未收集到任何物理佐證資料", str(ctx.exception))

        # 填入佐證後，推進至 DRAFT
        fsm.update_payload(evidence_sources=["benchmark_log.csv", "profiler_dump.json"])
        fsm.transition_to(HarnessStage.DRAFT)
        self.assertEqual(fsm.current_stage, HarnessStage.DRAFT)

        # 案例 3: 草稿長度不足，嘗試推進至 AUDIT -> 阻斷
        with self.assertRaises(RigidGateException):
            fsm.transition_to(HarnessStage.AUDIT)

        fsm.update_payload(draft_content="本方案透過 Redis 叢集取代原本地雜湊表，大幅降低記憶體佔用。")
        fsm.transition_to(HarnessStage.AUDIT)
        self.assertEqual(fsm.current_stage, HarnessStage.AUDIT)

        # 案例 4: 進入 SHIP 前，未通過資安簽核或含有 AI 套話 -> 阻斷
        with self.assertRaises(RigidGateException) as ctx:
            fsm.transition_to(HarnessStage.SHIP)
        self.assertIn("資安守護審核未簽核", str(ctx.exception))

        # 補充資安簽核且文本乾淨 -> 成功發布 (SHIP)
        fsm.update_payload(security_verified=True)
        rec_ship = fsm.transition_to(HarnessStage.SHIP)
        self.assertEqual(fsm.current_stage, HarnessStage.SHIP)
        self.assertGreater(len(fsm.transition_history), 3)

    def test_progressive_skill_registry(self):
        """測試漸進式技能揭露與上下文 Token 節約"""
        registry = ProgressiveSkillRegistry()
        registry.register(
            name="sql_sandbox_query",
            summary="執行 AST 語法防護之唯讀 SQL 查詢",
            category="database",
            full_instructions="必須使用 WITH (NOLOCK)，嚴禁 DROP、DELETE 與 TRUNCATE 語句。",
            parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        registry.register(
            name="security_audit_guard",
            summary="執行編譯器語法樹安全檢查",
            category="security",
            full_instructions="檢查模組是否包含 os.system, exec, eval 等高危調用。",
            parameters_schema={"type": "object", "properties": {"code": {"type": "string"}}},
        )

        # 1. 驗證極簡目錄常駐
        compact_index = registry.get_compact_index()
        self.assertIn("sql_sandbox_query", compact_index)
        self.assertIn("security_audit_guard", compact_index)
        self.assertNotIn("WITH (NOLOCK)", compact_index)  # 詳細規格不應洩漏至常駐目錄

        # 2. 驗證隨需載入特定技能
        resolved = registry.resolve_skills(["sql_sandbox_query"])
        self.assertIn("WITH (NOLOCK)", resolved)
        self.assertNotIn("os.system", resolved)  # 未要求的技能不加載

        # 3. 驗證節省率
        savings = registry.calculate_token_savings()
        self.assertEqual(savings["total_skills"], 2)
        self.assertGreater(savings["saving_ratio"], 0.20)

    def test_clean_room_subagent_isolation(self):
        """測試無菌室子代理隔離執行"""
        def heavy_scraping_worker(query: str, target_count: int):
            # 模擬內部繁複過程 (不外洩至主上下文)
            intermediate_debug_logs = [f"fetching item {i}..." for i in range(target_count)]
            return {
                "summary": f"成功從資料庫探勘並比對 {target_count} 筆交易記錄，均值為 450 元。",
                "artifacts": {"item_count": target_count, "avg_amount": 450},
                "tokens_consumed": 380,
            }

        res = CleanRoomSubagentRunner.execute_in_clean_room(
            subagent_id="subagent_finance_miner",
            task_description="探勘客戶歷史訂單數據",
            task_fn=heavy_scraping_worker,
            query="order_records",
            target_count=100,
        )

        self.assertTrue(res.success)
        self.assertEqual(res.subagent_id, "subagent_finance_miner")
        self.assertIn("成功從資料庫探勘並比對 100 筆交易記錄", res.summary_output)
        self.assertEqual(res.structured_artifacts["avg_amount"], 450)
        self.assertLess(res.execution_time_ms, 50.0)

    def test_dispatcher_with_harness_integration(self):
        """測試 Dispatcher 原生串接 Agent Harness 去 AI 味"""
        harness = AgentHarness()
        dispatcher = AdaptiveAgentDispatcher(
            harness=harness,
            enable_logging=False,
        )

        res = dispatcher.process("請總結這週的伺服器運維情況")
        self.assertTrue(res.success)
        self.assertIn("harness", res.metadata)
        self.assertTrue(res.metadata["harness"]["is_clean"])


if __name__ == "__main__":
    unittest.main()
