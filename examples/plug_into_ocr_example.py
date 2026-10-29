"""
示範：如何將 Adaptive Agent Router 公版快速套進 OCR 專案
只需 3 步驟：
1. 引入 AdaptiveAgentDispatcher
2. 註冊 OCR 專屬工具 (如影像前處理、PaddleOCR/Tesseract、表格校正)
3. 呼叫 dispatcher.process()
"""

import sys
import os

# 引入公版路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import AdaptiveAgentDispatcher, BaseTool


# 步驟 1: 定義你的 OCR 專用工具
class InvoiceOCRTool(BaseTool):
    name = "invoice_ocr_parser"
    description = "對台灣統一發票影像進行版面分析、字元辨識與欄位抽取"
    risk_level = "low"

    def execute(self, image_path: str = "", **kwargs):
        return f"[OCR Success] 已辨識發票 {image_path}: 發票號碼 AA-12345678, 總金額 NT$ 5,200"


class ImageDenoiseTool(BaseTool):
    name = "image_preprocess_denoise"
    description = "執行影像去噪、傾斜校正與對比度增強"
    risk_level = "low"

    def execute(self, image_path: str = "", **kwargs):
        return f"[Preprocess Done] 影像 {image_path} 已完成旋轉校正與高斯濾波去噪。"


# 步驟 2: 實例化並註冊工具
def run_ocr_agent():
    print("\n=======================================================")
    print("📄 套用至 OCR 專案示範 (Adaptive OCR Intelligent Agent)")
    print("=======================================================\n")

    ocr_agent = AdaptiveAgentDispatcher(
        custom_tools=[InvoiceOCRTool(), ImageDenoiseTool()]
    )

    # 模擬問題 A: 簡單單張發票辨識
    print(">> 狀況 A: 簡單發票辨識")
    ocr_agent.process("幫我把這張發票 invoice_001.png 整理成表格並萃取金額")

    # 模擬問題 B: 遇到破損或模糊影像，需要邊看邊調參數探索
    print("\n>> 狀況 B: 模糊辨識問題排查")
    ocr_agent.process("為什麼 invoice_999.png 統編辨識一直是亂碼？幫我調查原因找找看解法")

    # 模擬問題 C: 大規模辨識規劃
    print("\n>> 狀況 C: 百萬張票據自動化處理")
    ocr_agent.process("公司有 10 萬張歷史憑證需要批次辨識並入庫，請提出完整方案與步驟分解")


if __name__ == "__main__":
    run_ocr_agent()
