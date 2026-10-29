"""
通用預設範例工具 (Common Mock Tools)
提供在缺乏真實外部系統時的標準示範工具。
"""

from .base_tool import BaseTool, SimpleFunctionTool


class DatabaseQueryTool(BaseTool):
    name = "db_query"
    description = "執行唯讀資料庫查詢 (例如：取得客戶名單、發票記錄、庫存清單)"
    risk_level = "low"

    def execute(self, query: str = "", **kwargs):
        return f"[DB Result] 查詢成功：找到與 '{query}' 相關的記錄 3 筆。"


class DatabaseWriteTool(BaseTool):
    name = "db_write_or_delete"
    description = "修改、更新或刪除資料庫重要記錄 (如更改訂單狀態、刪除檔案)"
    risk_level = "critical"

    def execute(self, table: str = "", action: str = "", **kwargs):
        return f"[DB Write Alert] 成功在表 '{table}' 執行不可逆動作: {action}"


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜尋即時網頁資訊或最新產業情報"
    risk_level = "low"

    def execute(self, query: str = "", **kwargs):
        return f"[Search Results] 找到關於 '{query}' 的最新 5 條市場動態與新聞分析。"


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "執行精確的數學計算與財務公式"
    risk_level = "low"

    def execute(self, expression: str = "", **kwargs):
        try:
            # 僅作為示範安全評估
            allowed = "0123456789+-*/(). "
            if all(c in allowed for c in expression):
                return str(eval(expression))
            return "運算式包含不安全字元"
        except Exception as e:
            return f"計算錯誤: {e}"
