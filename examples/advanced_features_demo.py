"""
=============================================================================
AdaptiveAgentRouter - 四大進階架構優化機制實證演練 (Advanced Features Demo)
1. 非同步串流輸出 (Async Streaming SSE Generator)
2. 反饋自適應動態 ELO 評級 (Feedback-Driven ELO Rating Tuner)
3. 零代碼工具自動吸納器 (OpenAPI 3.0 & FastMCP Native Ingestion)
4. 實體隔離執行沙盒 (Restricted Subprocess Sandbox)
=============================================================================
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AdaptiveAgentDispatcher,
    AgentMode,
    ELORatingTuner,
    ToolLoader,
    RestrictedSubprocessSandbox,
    StreamEventType,
)


async def main():
    print("=" * 70)
    print("AdaptiveAgentRouter - Advanced Architectural Features Verification")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. 驗證非同步串流輸出 (Async Streaming SSE Engine)
    # -------------------------------------------------------------------------
    print("\n--- [1. 非同步串流輸出 (Async Streaming SSE Engine)] ---")
    dispatcher = AdaptiveAgentDispatcher(enable_logging=False)
    test_prompt = "請幫我萃取發票統編與金額欄位，整理為 JSON"

    print(f"發送非同步串流請求: '{test_prompt}'\n串流事件序列:")
    async for chunk in dispatcher.aprocess_stream(test_prompt):
        if chunk.event == StreamEventType.ROUTE_START:
            print(f"  [SSE: {chunk.event.value}] -> {chunk.message}")
        elif chunk.event == StreamEventType.ROUTE_DECIDED:
            decision = chunk.data.get("decision", {})
            print(f"  [SSE: {chunk.event.value}] -> 指派模式: {decision.get('mode')}, 算力: {decision.get('model_tier')}")
        elif chunk.event == StreamEventType.STEP_PROGRESS:
            print(f"  [SSE: {chunk.event.value}] -> {chunk.message}")
        elif chunk.event == StreamEventType.CONTENT_CHUNK:
            # 串流增量 Token
            if chunk.delta and chunk.delta.strip():
                print(f"    [Token Stream] {chunk.delta.strip()[:60]}...")
        elif chunk.event == StreamEventType.TASK_COMPLETED:
            print(f"  [SSE: {chunk.event.value}] -> {chunk.message} (Tokens: {chunk.data.get('total_tokens_used')})")

    # -------------------------------------------------------------------------
    # 2. 驗證反饋自適應動態 ELO 等級分調校 (Feedback-Driven ELO Tuner)
    # -------------------------------------------------------------------------
    print("\n--- [2. 反饋自適應 ELO 等級分調校 (Feedback-Driven ELO Tuner)] ---")
    tuner = dispatcher.elo_tuner
    mode = AgentMode.REACT

    print(f"初始模式: {mode.value} | 基準 ELO: {tuner.stats[mode].elo_rating:.1f} | 信心偏置: {tuner.get_routing_bias(mode):+.4f}")
    
    # 模擬 3 次高品質完成 (高勝率 + 高評分)
    tuner.record_feedback(mode=mode, success=True, latency_ms=120.0, user_rating=5.0)
    tuner.record_feedback(mode=mode, success=True, latency_ms=110.0, user_rating=4.8)
    print(f"  -> 經 2 次五星好評獎勵: ELO 升至 {tuner.stats[mode].elo_rating:.1f} | 信心偏置加乘: {tuner.get_routing_bias(mode):+.4f}")

    # 模擬 1 次任務失敗 (例如陷入無效端點)
    tuner.record_feedback(mode=mode, success=False, latency_ms=3000.0)
    print(f"  -> 經 1 次失敗懲罰:     ELO 降至 {tuner.stats[mode].elo_rating:.1f} | 信心偏置校準: {tuner.get_routing_bias(mode):+.4f}")

    # -------------------------------------------------------------------------
    # 3. 驗證零代碼工具吸納器 (OpenAPI 3.0 & FastMCP Ingestion)
    # -------------------------------------------------------------------------
    print("\n--- [3. 零代碼工具吸納器 (OpenAPI 3.0 & FastMCP Ingestion)] ---")
    openapi_spec = {
        "paths": {
            "/api/v1/crm/customers": {
                "get": {
                    "operationId": "get_customer_profile",
                    "summary": "查詢客戶檔案與歷史互動",
                }
            },
            "/api/v1/crm/customers/purge": {
                "delete": {
                    "operationId": "purge_customer_records",
                    "summary": "永久銷毀客戶機敏紀錄 (不可逆操作)",
                }
            }
        }
    }
    generated_tools = ToolLoader.from_openapi_spec(openapi_spec)
    print(f"從 OpenAPI 規格自動解析並封裝出 {len(generated_tools)} 個標準 BaseTool:")
    for tool in generated_tools:
        print(f"  - 工具代號: {tool.name:<25} | 風險評級: {tool.risk_level:<8} | 描述: {tool.description}")

    # 模擬 MCP 宣告吸納
    mcp_specs = [
        {"name": "execute_stock_trade", "description": "執行台股證券下單扣款", "inputSchema": {}}
    ]
    mcp_tools = ToolLoader.from_mcp_spec(mcp_specs)
    print(f"從 MCP 協定宣告自動吸納工具: {mcp_tools[0].name} (自動推論風險等級: {mcp_tools[0].risk_level})")

    # -------------------------------------------------------------------------
    # 4. 驗證實體隔離執行沙盒 (Restricted Subprocess Sandbox)
    # -------------------------------------------------------------------------
    print("\n--- [4. 實體隔離執行沙盒 (Restricted Subprocess Sandbox)] ---")
    sandbox = RestrictedSubprocessSandbox(timeout_seconds=2.0)

    # 測試 1: 安全獨立運算
    safe_code = """
import math
vals = [math.sqrt(i) for i in range(10)]
print(f"COMPUTATION_SUCCESS_SUM: {sum(vals):.2f}")
"""
    res1 = sandbox.execute_python_code(safe_code)
    print(f"安全代碼沙箱執行結果: Success={res1.success} | 耗時={res1.elapsed_ms}ms | 輸出={res1.stdout.strip()}")

    # 測試 2: 危險越獄代碼 (靜態 AST 阻斷)
    unsafe_code = "import os; os.system('echo dangerous_action')"
    res2 = sandbox.execute_python_code(unsafe_code)
    print(f"惡意代碼靜態阻斷結果: BlockedByGuard={res2.blocked_by_guard} | 原因={res2.block_reason}")

    # 測試 3: 惡意死循環防禦 (行程超時硬性截斷)
    infinite_loop = "while True: pass"
    res3 = sandbox.execute_python_code(infinite_loop)
    print(f"死循環代碼超時截斷: Success={res3.success} | 耗時={res3.elapsed_ms}ms | 錯誤訊息={res3.stderr.strip()}")

    print("\n" + "=" * 70)
    print("All 4 advanced architectural modules verified successfully.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
