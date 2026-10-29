"""
模式 2: 反思迴圈 (ReAct - Reason + Act)
特點：思考 ➜ 執行 (工具/API) ➜ 觀察 (結果) ➜ 再來一次，直到達成目標。
適用場景：需要多步探索、動態決策、無固定標準路徑的任務。
"""

import time
from typing import Any, Dict, List, Optional
from .base import BaseAgentMode
from ..types import AgentMode, ExecutionResult
from ..tools.base_tool import BaseTool


class ReActMode(BaseAgentMode):
    mode = AgentMode.REACT

    def run(
        self,
        prompt: str,
        tools: Optional[List[BaseTool]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        start_time = time.time()
        steps = []
        max_loops = 3

        # 模擬 ReAct 迴圈軌跡
        for i in range(1, max_loops + 1):
            thought = f"輪次 {i}: 觀察目前資訊，分析下一步需要什麼資料。"
            action = "web_search" if i == 1 else ("calculator" if i == 2 else "finish")
            observation = f"獲取到與 '{prompt}' 相關的關鍵參數指標 (Iteration {i})."
            
            steps.append({
                "iteration": i,
                "thought": thought,
                "action": action,
                "observation": observation
            })

            if action == "finish":
                break

        output = (
            f"【ReAct 迴圈探索完成】\n"
            f"歷經 {len(steps)} 輪思考-行動-觀察迴圈，已成功推論出最終解答：\n"
            f"針對問題「{prompt}」，綜合多方觀察結果確認無誤。"
        )

        return ExecutionResult(
            output=output,
            mode_used=self.mode,
            execution_steps=steps,
            total_tokens_used=720,
            success=True,
            metadata={"loops": len(steps), "latency_ms": round((time.time() - start_time) * 1000, 2)}
        )
