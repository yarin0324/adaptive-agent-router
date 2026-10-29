"""
模式 8: 工具使用代理 (Tool Use Agent)
特點：專精於從眾多工具庫中動態選擇、組合與執行適當工具，並彙總結果。
適用場景：資料庫查詢、呼叫外部 API、檔案轉換、系統日常維運。
"""

import time
from typing import Any, Dict, List, Optional
from .base import BaseAgentMode
from ..types import AgentMode, ExecutionResult
from ..tools.base_tool import BaseTool


class ToolAgentMode(BaseAgentMode):
    mode = AgentMode.TOOL_USE

    def run(
        self,
        prompt: str,
        tools: Optional[List[BaseTool]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        start_time = time.time()
        steps = []
        tools = tools or []

        # 模擬工具挑選與執行
        selected_tool = tools[0] if tools else None
        tool_result = "無可用工具"

        if selected_tool:
            tool_result = selected_tool.execute(query=prompt)
            steps.append({
                "action": "call_tool",
                "tool_name": selected_tool.name,
                "input": prompt,
                "output": tool_result
            })
        else:
            steps.append({
                "action": "no_tool",
                "detail": "使用內建工具選擇器匹配工具"
            })

        output = (
            f"【工具代理執行結果】\n"
            f"提問: {prompt}\n"
            f"調用工具: {selected_tool.name if selected_tool else '默認解析器'}\n"
            f"執行結果: {tool_result}"
        )

        return ExecutionResult(
            output=output,
            mode_used=self.mode,
            execution_steps=steps,
            total_tokens_used=350,
            success=True,
            metadata={"tool_invoked": selected_tool.name if selected_tool else None}
        )
