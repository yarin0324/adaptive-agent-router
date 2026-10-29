"""
系統集成測試與架構示範 (System Integration Verification)
展示 Adaptive Agent Router 的語義分流、安全門控掛起與審批恢復 (Suspend & Resume)、
以及高頻查詢路由快取 (RouteCache Hit)。
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import AdaptiveAgentDispatcher


def main():
    print("=================================================================")
    print("Adaptive Agent Router - Architecture Verification Test")
    print("=================================================================\n")

    dispatcher = AdaptiveAgentDispatcher(enable_logging=True)

    test_queries = [
        # 1. 結構化單次抽取
        "請幫我把這段文字中的電話與統編欄位萃取出來，整理成表格",

        # 2. 探索性診斷
        "幫我調查一下這套 API 為什麼最近回應延遲突然飆高？找找看可能原因",

        # 3. 系統長流程規劃
        "我們需要建立一套企業級發票 OCR 自動化識別系統，請提出完整方案與步驟分解",

        # 4. 嚴格反思與條款審查
        "這份商業合約的保密條款請嚴格審查，挑出漏洞並進行多輪反思優化",

        # 5. 高風險不可逆指令 (觸發安全門控掛起)
        "請連進主資料庫，強制刪除所有過期的測試訂單資料表",

        # 6. 跨領域對抗辯論
        "這項新產品架構需要跨部門多角度評估，請安排技術與風控專家辯論",
    ]

    last_suspended_task_id = None

    for idx, query in enumerate(test_queries, start=1):
        print(f"[{idx}/{len(test_queries)}] Request: {query}")
        result = dispatcher.process(query)
        if result.metadata.get("status") == "SUSPENDED":
            last_suspended_task_id = result.metadata.get("task_id")
        print("-" * 65)

    # 驗證機制 1: 路由快取測試 (相同提問再次發送)
    print("\n[Cache Test] 再次發送相同提問驗證快取命中 (Cache Hit)...")
    dispatcher.process("請幫我把這段文字中的電話與統編欄位萃取出來，整理成表格")
    print("-" * 65)

    # 驗證機制 2: 人機協同非同步審批恢復 (Resume Suspended Task)
    if last_suspended_task_id:
        print(f"\n[Human-in-the-Loop] 收到管理員非同步審批訊號，放行 Task ID: {last_suspended_task_id}")
        resume_result = dispatcher.resume_task(last_suspended_task_id, approved=True)
        print(f"審批放行執行結果: {resume_result.output}")
        print("-" * 65)


if __name__ == "__main__":
    main()
