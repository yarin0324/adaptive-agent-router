"""
示範：如何將 Adaptive Agent Router 公版套進 台股投研/金融風控專案
展示高風險動作（下單/停損）觸發安全門控，以及跨領域辯論模式。
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import AdaptiveAgentDispatcher, BaseTool


class StockQuoteTool(BaseTool):
    name = "tw_stock_quote"
    description = "查詢台股即時報價、成交量與日K資料"
    risk_level = "low"

    def execute(self, symbol: str = "2330", **kwargs):
        return f"[Quote] {symbol} 最新價格 1,020 元, 漲幅 +1.5%, 成交量 32,000 張。"


class StockOrderTool(BaseTool):
    name = "tw_broker_order"
    description = "送出券商下單委託 (買進/賣出/當沖停損)"
    risk_level = "critical"

    def execute(self, symbol: str = "", action: str = "BUY", qty: int = 1, **kwargs):
        return f"[Order Sent] 已向券商主機發送 {action} {symbol} {qty} 張委託！"


def run_stock_agent():
    print("\n=======================================================")
    print("📈 套用至台股投研風控專案 (Adaptive Taiwan Stock Agent)")
    print("=======================================================\n")

    stock_agent = AdaptiveAgentDispatcher(
        custom_tools=[StockQuoteTool(), StockOrderTool()]
    )

    # 狀況 1: 查報價 (直接調用工具或單次回應)
    print(">> 狀況 1: 一般行情報價查詢")
    stock_agent.process("查詢 2330 台積電今天收盤價與成交量")

    # 狀況 2: 涉及下單交易 (高風險！必須觸發門控)
    print("\n>> 狀況 2: 敏感操作 (下單買進)")
    stock_agent.process("幫我連線券商 API 下單買進 2330 台積電 5 張，市價單送出")

    # 狀況 3: 多空辯論
    print("\n>> 狀況 3: 投資決策多視角審查")
    stock_agent.process("針對半導體板塊後市進行跨部門多角度評估，請安排牛熊雙方專家辯論")


if __name__ == "__main__":
    run_stock_agent()
