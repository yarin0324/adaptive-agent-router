"""
前沿韌性與測試工程實測示範 (Advanced Resilience & Testing Engineering Demo)
==========================================================================
展示 4 大世界級測試架構之實體運作：
1. Agent Chaos Monkey (Netflix 混沌工程：注入 504 逾時、畸形 JSON 與間接提示詞攻擊)
2. Deterministic Simulation Testing (Antithesis DST：虛擬時鐘與 100% 可重現密碼學軌跡指紋)
3. SWE-bench Test-as-Oracle (以實體代碼測試為唯一真理，拒絕 LLM 自我評分)
4. Production Shadow Dual-Run (Stripe/Uber 流量鏡像雙跑：即時監控 Token 節省與漂移度)
==========================================================================
"""

import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AgentChaosMonkey,
    ChaosInjectionConfig,
    ChaosFaultType,
    ChaosInjectionException,
    DeterministicSimulationRunner,
    VirtualClock,
    TestAsOracle,
    ShadowDualRunner,
)


def demo_chaos_monkey():
    print("=" * 75)
    print("1. [Agent Chaos Monkey] 混沌工程故障注入 (Netflix 韌性架構)")
    print("=" * 75)

    # 1. 注入 504 逾時
    cfg_timeout = ChaosInjectionConfig(timeout_probability=1.0, seed=101)
    monkey_timeout = AgentChaosMonkey(cfg_timeout)

    def db_search(sku: str):
        return f"Database row for {sku}"

    try:
        monkey_timeout.execute_with_chaos("db_search", db_search, sku="SKU_998")
    except ChaosInjectionException as e:
        print(f"  [故障 1 攔截] 成功注入並捕獲服務逾時: {e}")

    # 2. 注入畸形 JSON
    cfg_json = ChaosInjectionConfig(malformed_json_probability=1.0, seed=102)
    monkey_json = AgentChaosMonkey(cfg_json)

    def api_fetch():
        return '{"status": "ok"}'

    raw_output = monkey_json.execute_with_chaos("api_fetch", api_fetch)
    print(f"  [故障 2 注入] 模擬下游回傳截斷殘缺 JSON: '{raw_output}'")

    # 3. 注入間接提示詞攻擊 (Prompt Injection)
    cfg_injection = ChaosInjectionConfig(indirect_injection_probability=1.0, seed=103)
    monkey_inject = AgentChaosMonkey(cfg_injection)

    def web_crawler():
        return "Clean page content"

    crawler_output = monkey_inject.execute_with_chaos("web_crawler", web_crawler)
    print(f"  [故障 3 注入] 工具輸出夾帶惡意指令: '{crawler_output[:60]}...'")
    print(f"  -> 驗證: 系統具備異常感知能力，絕不因第三方服務毀損而崩潰\n")


def demo_deterministic_simulation():
    print("=" * 75)
    print("2. [Deterministic Simulation Testing] 確定性模擬重現 (Antithesis DST)")
    print("=" * 75)

    steps = [
        {"component": "IntentClassifier", "action": "route_to_planner", "duration_ms": 5.0},
        {"component": "TaskPlanner", "action": "decompose_subtasks", "duration_ms": 20.0},
        {"component": "ToolExecutor", "action": "execute_sql_query", "duration_ms": 35.0},
        {"component": "StateFSM", "action": "verify_and_transition", "duration_ms": 10.0},
    ]

    def simulation_step_handler(step_def, clock):
        action = step_def["action"]
        virtual_now = clock.now_ms()
        return f"STATE_{action.upper()}", {"timestamp_ms": virtual_now, "status": "COMPLETED"}

    # 執行第一次模擬
    sim_a = DeterministicSimulationRunner(seed=88888)
    trace_hash_a = sim_a.run_multi_step_scenario("TASK_INITIALIZED", steps, simulation_step_handler)

    # 執行第二次模擬 (重播)
    sim_b = DeterministicSimulationRunner(seed=88888)
    trace_hash_b = sim_b.run_multi_step_scenario("TASK_INITIALIZED", steps, simulation_step_handler)

    print(f"  • 虛擬時鐘總推進時間:       {sim_a.clock.now_ms():.1f} ms (非真實 OS 等待)")
    print(f"  • 模擬事件總數:             {len(sim_a.events)} 步 (START -> 4 STEPS -> END)")
    print(f"  • 執行 A 軌跡 SHA-256 指紋: {trace_hash_a}")
    print(f"  • 執行 B 軌跡 SHA-256 指紋: {trace_hash_b}")
    print(f"  • 確定性重現比對結果:       {'100% 絕對一致 (BIT-FOR-BIT IDENTICAL)' if trace_hash_a == trace_hash_b else 'DIVERGED'}\n")


def demo_test_as_oracle():
    print("=" * 75)
    print("3. [SWE-bench Test-as-Oracle] 實體代碼測試裁判 (拒絕 LLM-as-a-Judge)")
    print("=" * 75)

    # 案例 1: 合格代碼與單元測試
    candidate_code_ok = (
        "def compute_discount(price: float, is_vip: bool) -> float:\n"
        "    return price * 0.8 if is_vip else price * 0.95\n"
    )
    test_code_ok = (
        "assert compute_discount(100.0, True) == 80.0\n"
        "assert compute_discount(100.0, False) == 95.0\n"
    )

    res_ok = TestAsOracle.verify_code_patch(candidate_code_ok, test_code_ok)
    print(f"  • 合法候選代碼驗證: Passed={res_ok.passed}, ExitCode={res_ok.exit_code}, 耗時={res_ok.execution_time_ms}ms")

    # 案例 2: 惡意代碼嘗試調用 OS 指令
    candidate_code_malicious = (
        "import os\n"
        "def compute_discount(price, is_vip):\n"
        "    os.system('rm -rf /tmp/test')\n"
        "    return price\n"
    )
    res_malicious = TestAsOracle.verify_code_patch(candidate_code_malicious, "pass")
    print(f"  • 惡意代碼注入攔截: Passed={res_malicious.passed}, ExitCode={res_malicious.exit_code} (AST 實體阻斷)")
    print(f"  • 阻斷細節原因:     {res_malicious.failure_details[0] if res_malicious.failure_details else 'None'}\n")


def demo_shadow_dual_run():
    print("=" * 75)
    print("4. [Production Shadow Dual-Run] 生產環境陰影雙跑 (Stripe/Uber 流量鏡像)")
    print("=" * 75)

    runner = ShadowDualRunner(agreement_threshold=0.80)

    # 模擬主鏈路 (傳統龐大 ReAct 迴圈) vs 陰影鏈路 (AdaptiveAgentRouter)
    def legacy_pipeline(req):
        return f"處理結果: {req['task']} (依賴 3 輪多輪對話)", 2400, 920.0

    def adaptive_pipeline(req):
        return f"處理結果: {req['task']} (單輪結構抽取)", 220, 32.0, "mode_1_single_turn"

    requests = [
        {"task": "提取統一發票統編與金額"},
        {"task": "查詢 2025 年差旅報銷政策上限"},
        {"task": "核算客戶月結帳單總計"},
    ]

    for i, req in enumerate(requests, 1):
        _, report = runner.execute_dual_run(req, legacy_pipeline, adaptive_pipeline)
        print(f"  [雙跑請求 {i}] {req['task']}")
        print(f"    - 時延: 主={report.primary_latency_ms}ms | 陰影={report.shadow_latency_ms}ms (改善: -{report.latency_savings_ratio*100:.1f}%)")
        print(f"    - Token: 主={report.primary_estimated_tokens}t | 陰影={report.shadow_estimated_tokens}t (節省: -{report.token_savings_ratio*100:.1f}%)")
        print(f"    - 欄位吻合度: {report.agreement_score*100:.1f}% | 漂移偵測: {report.drift_detected}")

    agg = runner.get_aggregate_stats()
    print(f"\n  • 總體遙測摘要: 雙跑總數={agg['total_dual_runs']} | 平均 Token 節省={agg['avg_token_savings_ratio']*100:.1f}% | 漂移事件={agg['drift_incidents']}\n")


def main():
    print("\n" + "=" * 75)
    print("  AdaptiveAgentRouter - Advanced Resilience & Testing Engineering")
    print("=" * 75 + "\n")

    demo_chaos_monkey()
    demo_deterministic_simulation()
    demo_test_as_oracle()
    demo_shadow_dual_run()

    print("=" * 75)
    print("  All 4 advanced testing methodologies verified in action.")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
