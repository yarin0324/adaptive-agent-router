"""
系統韌性與前沿測試單元測試套件 (Resilience & Advanced Testing Suite)
涵蓋 Agent Chaos Monkey, Deterministic Simulation Testing (DST),
SWE-bench Test-as-Oracle Runner, 以及 Production Shadow Dual-Run。
"""

import unittest
from router_app import (
    AgentChaosMonkey,
    ChaosInjectionConfig,
    ChaosFaultType,
    ChaosInjectionException,
    DeterministicSimulationRunner,
    VirtualClock,
    TestAsOracle,
    OracleExecutionResult,
    ShadowDualRunner,
    ShadowComparisonReport,
)


class TestResilienceSuite(unittest.TestCase):
    """前沿韌性與測試架構單元測試"""

    # =========================================================================
    # 1. Agent Chaos Monkey 混沌工程測試
    # =========================================================================
    def test_chaos_monkey_timeout_injection(self):
        """測試混沌猴子精準注入 HTTP 504 逾時異常"""
        cfg = ChaosInjectionConfig(enabled=True, timeout_probability=1.0, seed=42)
        monkey = AgentChaosMonkey(config=cfg)

        def mock_db_tool(query: str):
            return {"status": "ok", "rows": [1, 2, 3]}

        with self.assertRaises(ChaosInjectionException) as ctx:
            monkey.execute_with_chaos("db_tool", mock_db_tool, query="SELECT *")

        self.assertEqual(ctx.exception.fault_type, ChaosFaultType.TIMEOUT)
        summary = monkey.get_summary()
        self.assertEqual(summary["total_injected_events"], 1)
        self.assertEqual(summary["fault_breakdown"]["timeout"], 1)

    def test_chaos_monkey_malformed_json_injection(self):
        """測試混沌猴子注入殘缺畸形 JSON 輸出"""
        cfg = ChaosInjectionConfig(enabled=True, malformed_json_probability=1.0, seed=42)
        monkey = AgentChaosMonkey(config=cfg)

        def mock_api_tool():
            return '{"status": "success"}'

        result = monkey.execute_with_chaos("api_tool", mock_api_tool)
        # 驗證回傳值為畸形字串，無法以 json.loads 解析
        import json
        with self.assertRaises(json.JSONDecodeError):
            json.loads(result)

    def test_chaos_monkey_indirect_injection(self):
        """測試混沌猴子注入間接提示詞攻擊"""
        cfg = ChaosInjectionConfig(enabled=True, indirect_injection_probability=1.0, seed=42)
        monkey = AgentChaosMonkey(config=cfg)

        def mock_web_scraper():
            return "Normal web page content"

        result = monkey.execute_with_chaos("web_scraper", mock_web_scraper)
        self.assertIn("SYSTEM OVERRIDE INSTRUCTION", result)

    def test_chaos_monkey_passthrough(self):
        """測試未觸發混沌條件下的正常執行穿透"""
        cfg = ChaosInjectionConfig(enabled=False)
        monkey = AgentChaosMonkey(config=cfg)

        def add_tool(a: int, b: int):
            return a + b

        res = monkey.execute_with_chaos("add_tool", add_tool, 10, 20)
        self.assertEqual(res, 30)

    # =========================================================================
    # 2. Deterministic Simulation Testing (DST) 確定性模擬測試
    # =========================================================================
    def test_deterministic_simulation_trace_reproducibility(self):
        """測試相同隨機種子下，模擬事件軌跡指紋 100% 絕對重現"""
        steps = [
            {"component": "Planner", "duration_ms": 12.0, "action": "decompose"},
            {"component": "ToolExecutor", "duration_ms": 25.0, "action": "fetch_db"},
            {"component": "Reflexion", "duration_ms": 18.0, "action": "verify_rubric"},
        ]

        def dummy_handler(step_def, clock):
            return f"STATE_AFTER_{step_def['action']}", {"processed_at": clock.now_ms()}

        # 第一次模擬
        sim1 = DeterministicSimulationRunner(seed=999)
        hash1 = sim1.run_multi_step_scenario("INIT", steps, dummy_handler)

        # 第二次重跑模擬 (相同種子)
        sim2 = DeterministicSimulationRunner(seed=999)
        hash2 = sim2.run_multi_step_scenario("INIT", steps, dummy_handler)

        # 斷言密碼學指紋 100% 吻合
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(sim1.events), 5)  # START + 3 STEPS + END
        # 驗證虛擬時鐘推進 12 + 25 + 18 = 55ms
        self.assertEqual(sim1.clock.now_ms(), 55.0)

    def test_virtual_clock_travel_backwards_rejection(self):
        """測試虛擬時鐘禁止時光倒流防護"""
        clock = VirtualClock(100.0)
        with self.assertRaises(ValueError):
            clock.advance_ms(-5.0)

    # =========================================================================
    # 3. SWE-bench Test-as-Oracle 實體代碼測試裁判
    # =========================================================================
    def test_oracle_unit_test_execution_pass(self):
        """測試 Oracle 執行成功通過之單元測試類別"""
        class SamplePassTest(unittest.TestCase):
            def test_addition(self):
                self.assertEqual(2 + 2, 4)

        result = TestAsOracle.run_unit_tests([SamplePassTest])
        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.test_count, 1)
        self.assertEqual(result.failure_count, 0)

    def test_oracle_unit_test_execution_fail(self):
        """測試 Oracle 執行失敗之單元測試類別"""
        class SampleFailTest(unittest.TestCase):
            def test_bad_math(self):
                self.assertEqual(1 + 1, 3)

        result = TestAsOracle.run_unit_tests([SampleFailTest])
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.failure_count, 1)
        self.assertTrue(len(result.failure_details) > 0)

    def test_oracle_verify_code_patch_safe(self):
        """測試候選代碼與驗證代碼在安全沙盒中的正向檢驗"""
        candidate_code = "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)"
        test_code = "assert fib(5) == 5\nassert fib(6) == 8"

        result = TestAsOracle.verify_code_patch(candidate_code, test_code)
        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)

    def test_oracle_verify_code_patch_malicious_blocked(self):
        """測試候選代碼包含惡意 AST 語法時被編譯器層級阻斷"""
        malicious_code = "import os\nos.system('echo dangerous')"
        test_code = "pass"

        result = TestAsOracle.verify_code_patch(malicious_code, test_code)
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 126)
        self.assertIn("Security AST Violation", result.stderr)

    # =========================================================================
    # 4. Production Shadow Dual-Run 陰影雙跑比對
    # =========================================================================
    def test_shadow_dual_run_comparison(self):
        """測試生產環境主鏈路與陰影鏈路之比對與統計指標"""
        runner = ShadowDualRunner(agreement_threshold=0.75)

        def primary_pipeline(payload):
            # 模擬傳統 ReAct 流程 (耗費高 Token、高時延)
            return {"result": "用戶帳單為 500 元", "tier": "legacy"}, 2500, 850.0

        def shadow_pipeline(payload):
            # 模擬自適應路由器 (結構壓縮、低 Token、極速)
            return {"result": "用戶帳單為 500 元", "tier": "fast"}, 300, 45.0, "mode_1_single_turn"

        payload = {"user_id": "U123"}
        res, report = runner.execute_dual_run(payload, primary_pipeline, shadow_pipeline)

        self.assertEqual(res["result"], "用戶帳單為 500 元")
        self.assertGreater(report.token_savings_ratio, 0.80)  # (2500 - 300) / 2500 = 88%
        self.assertGreater(report.latency_savings_ratio, 0.90) # (850 - 45) / 850 = 94.7%
        self.assertGreater(report.agreement_score, 0.5)
        self.assertEqual(report.shadow_mode_used, "mode_1_single_turn")

        # 檢驗總體遙測指標
        stats = runner.get_aggregate_stats()
        self.assertEqual(stats["total_dual_runs"], 1)
        self.assertGreater(stats["avg_token_savings_ratio"], 0.80)


if __name__ == "__main__":
    unittest.main()
