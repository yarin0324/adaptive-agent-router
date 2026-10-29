"""
模式 1: 增強型 LLM (單次回應 - Single-Turn RAG / Extraction)
特點：一次呼叫，無反覆迴圈，延遲最低、成本最省。
適用場景：資料整理、欄位抽取、摘要、格式轉換、單純問答。
"""

import time
from typing import Any, Dict, List, Optional
from .base import BaseAgentMode
from ..types import AgentMode, ExecutionResult
from ..tools.base_tool import BaseTool


class SingleTurnMode(BaseAgentMode):
    mode = AgentMode.SINGLE_TURN

    def run(
        self,
        prompt: str,
        tools: Optional[List[BaseTool]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        start_time = time.time()
        steps = []

        # 模擬/執行單次處理
        steps.append({
            "step": 1,
            "action": "direct_inference",
            "detail": "使用輕量提示詞進行單次高吞吐生成，無反覆迭代。"
        })

        output = (
            f"【增強型單次回應結果】\n"
            f"針對您的需求：「{prompt}」已完成單次結構化整理。\n"
            f"- 處理模式: 增強型單次回應 (低延遲、經濟實惠)\n"
            f"- 耗時: {time.time() - start_time:.3f} 秒"
        )

        return ExecutionResult(
            output=output,
            mode_used=self.mode,
            execution_steps=steps,
            total_tokens_used=180,
            success=True,
            metadata={"latency_ms": round((time.time() - start_time) * 1000, 2)}
        )
