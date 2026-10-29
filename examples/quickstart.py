"""
快速啟動範例 (Quickstart)
展示 Adaptive Agent Router 如何根據不同問題情境，動態派發給最適 Agent 模式。
"""

import sys
import os

# 將專案根目錄加入 path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import AdaptiveAgentDispatcher


def main():
    print("\n=======================================================")
    print("🚀 啟動 Adaptive Agent Router 自適應動態路由器示範")
    print("=======================================================\n")

    dispatcher = AdaptiveAgentDispatcher(enable_logging=True)

    test_queries = [
        # 測試 1: 簡單結構化整理 ➜ 應走模式 1 (Single Turn)
        "請幫我把這段文字中的電話與統編欄位萃取出來，整理成表格",

        # 測試 2: 探索性診斷 ➜ 應走模式 2 (ReAct 迴圈)
        "幫我調查一下這套 API 為什麼最近回應延遲突然飆高？找找看可能原因",

        # 測試 3: 龐大系統規劃 ➜ 應走模式 4 (Planner-Executor)
        "我們需要建立一套企業級發票 OCR 自動化識別系統，請提出完整方案與步驟分解",

        # 測試 4: 嚴苛合約審查 ➜ 應走模式 5 (Reflection 自我反思)
        "這份商業合約的保密條款請嚴格審查，挑出漏洞並進行多輪反思優化",

        # 測試 5: 高風險不可逆指令 ➜ 應走模式 6 (Verifier-Gated 安全門控攔截)
        "請連進主資料庫，強制刪除所有過期的測試訂單資料表",

        # 測試 6: 跨領域專家決策 ➜ 應走模式 7 (Multi-Agent 多代理)
        "這項新產品架構需要跨部門多角度評估，請安排技術與風控專家辯論",
    ]

    for idx, query in enumerate(test_queries, start=1):
        print(f"\n[{idx}/6] 測試提問: {query}")
        result = dispatcher.process(query)
        print("-" * 60)


if __name__ == "__main__":
    main()
