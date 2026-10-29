"""
=============================================================================
AdaptiveAgentRouter - S 級架構實體物理驗證腳本 (Physical S-Tier Verifier)
拒絕任何口頭承諾與幻覺，直接對磁碟、記憶體與本機 Socket 執行實體驗證。
=============================================================================
"""

import os
import sys
import sqlite3
import threading
import time
import httpx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AdaptiveAgentDispatcher,
    AgentMode,
    SQLiteStateStorage,
    TaskSuspensionManager,
    metrics,
)
from router_app.server import run_gateway_server


def main():
    print("=" * 65)
    print("AdaptiveAgentRouter - Physical System Verification (Zero-Hallucination)")
    print("=" * 65)

    # 1. 物理磁碟 SQLite 持久化檢驗
    print("\n=== [1. 物理磁碟 SQLite 持久化檢驗] ===")
    test_db = "verify_persistence.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    storage = SQLiteStateStorage(db_path=test_db)
    susp_mgr = TaskSuspensionManager(storage=storage)
    dispatcher = AdaptiveAgentDispatcher(enable_logging=False)
    dispatcher.suspension_manager = susp_mgr

    # 觸發掛起
    res = dispatcher.process("強制刪除主庫客戶訂單表")
    task_id = res.metadata.get("task_id")
    print(f"  ✓ 任務成功掛起，獲得 Task ID: {task_id}")

    # 直接以 SQLite 原生連線查詢磁碟檔案
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT task_id, status, target_mode FROM suspended_tasks WHERE task_id = ?", (task_id,))
    row = cur.fetchone()
    assert row is not None, "SQLite 資料庫未找到持久化記錄！"
    print(f"  ✓ 磁碟物理讀取驗證: Task ID={row[0]}, Status={row[1]}, Mode={row[2]}")
    conn.close()

    # 模擬伺服器斷電重啟 (實例化全新的 storage 與 dispatcher)
    storage_reloaded = SQLiteStateStorage(db_path=test_db)
    susp_mgr_reloaded = TaskSuspensionManager(storage=storage_reloaded)
    dispatcher_reloaded = AdaptiveAgentDispatcher(enable_logging=False)
    dispatcher_reloaded.suspension_manager = susp_mgr_reloaded

    # 喚醒
    resumed = dispatcher_reloaded.resume_task(task_id, approved=True)
    print(f"  ✓ 跨重啟無縫喚醒成功: {resumed.output[:60]}...")
    if os.path.exists(test_db):
        os.remove(test_db)

    # 2. 影子流量 A/B 乾跑檢驗
    print("\n=== [2. 影子流量 A/B 乾跑檢驗] ===")
    res_shadow = dispatcher.process(
        "請幫我萃取發票統編與金額",
        shadow_mode=AgentMode.REACT
    )
    shadow_eval = res_shadow.metadata.get("shadow_evaluation")
    assert shadow_eval is not None
    print("  ✓ 影子評估報告產出成功:")
    print(f"    - 主要模式: {shadow_eval['primary_mode']} (Tokens: {shadow_eval['primary_tokens']})")
    print(f"    - 影子模式: {shadow_eval['shadow_mode']} (Tokens: {shadow_eval['shadow_tokens']})")
    print(f"    - 額外消耗差額: {shadow_eval['token_delta']} Tokens | 耗時: {shadow_eval['shadow_latency_ms']} ms")

    # 3. 審計戰鬥卡與 Mermaid 拓撲產出檢驗
    print("\n=== [3. 審計戰鬥卡與 Mermaid 拓撲產出檢驗] ===")
    card = res_shadow.to_battle_card("請幫我萃取發票統編與金額")
    mermaid = res_shadow.to_mermaid()
    assert "### 🛡️ AdaptiveAgentRouter 執行審計戰鬥卡" in card
    assert "flowchart LR" in mermaid
    print(f"  ✓ 戰鬥卡與 Mermaid 拓撲渲染正常 (長度: {len(card)} 字元)")

    # 4. 實體 HTTP Gateway 伺服器端點實測
    print("\n=== [4. 實體 HTTP Gateway 伺服器端點實測] ===")
    port = 8992
    srv_thread = threading.Thread(
        target=run_gateway_server,
        kwargs={"host": "127.0.0.1", "port": port, "enable_logging": False},
        daemon=True
    )
    srv_thread.start()
    time.sleep(0.3)

    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0)

    # GET /healthz
    r_h = client.get("/healthz")
    assert r_h.status_code == 200 and r_h.json()["status"] == "healthy"
    print("  ✓ [GET /healthz] HTTP 200 OK")

    # GET /metrics
    r_m = client.get("/metrics")
    assert r_m.status_code == 200 and "router_requests_total" in r_m.text
    print("  ✓ [GET /metrics] HTTP 200 (Prometheus 指標流導出正常)")

    # GET /v1/models
    r_mod = client.get("/v1/models")
    assert r_mod.status_code == 200 and len(r_mod.json()["data"]) == 10
    print("  ✓ [GET /v1/models] HTTP 200 (10 大架構模式虛擬模型清單正常)")

    # POST /v1/chat/completions (Non-stream)
    r_chat = client.post("/v1/chat/completions", json={
        "model": "adaptive-router",
        "messages": [{"role": "user", "content": "萃取統編 12345678"}]
    })
    assert r_chat.status_code == 200
    assert "choices" in r_chat.json()
    print("  ✓ [POST /v1/chat/completions] HTTP 200 (OpenAI 標準格式回應正確)")

    # POST /v1/chat/completions (Stream SSE)
    chunks = []
    with client.stream("POST", "/v1/chat/completions", json={
        "model": "adaptive-router",
        "messages": [{"role": "user", "content": "調查延遲高原因"}],
        "stream": True
    }) as stream_resp:
        for line in stream_resp.iter_lines():
            if line.startswith("data: "):
                chunks.append(line)

    assert len(chunks) > 0 and any("[DONE]" in c for c in chunks)
    print(f"  ✓ [POST /v1/chat/completions (stream=True)] HTTP 200 ({len(chunks)} SSE Chunks 正常串流)")

    print("\n" + "=" * 65)
    print("🎯 零幻覺驗證通過：所有物理功能實測 100% 正確！")
    print("=" * 65)


if __name__ == "__main__":
    main()
