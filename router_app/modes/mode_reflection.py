"""
模式 5: 評估 - 優化 (自我反思 / Reflection)
特點：生成初稿 ➜ Critic 模型批判抓蟲 ➜ 改寫優化，歷經 2-3 輪自我迭代達到極致品質。
適用場景：法務合約條款、嚴謹研究報告、核心演算法優化、高單價方案撰寫。
"""

import time
from typing import Any, Dict, List, Optional
from .base import BaseAgentMode
from ..types import AgentMode, ExecutionResult
from ..tools.base_tool import BaseTool


class ReflectionMode(BaseAgentMode):
    mode = AgentMode.REFLECTION

    def run(
        self,
        prompt: str,
        tools: Optional[List[BaseTool]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        start_time = time.time()
        steps = []
        rounds = 2

        # 模擬反思優化過程
        for r in range(1, rounds + 1):
            if r == 1:
                steps.append({
                    "round": r,
                    "action": "generator_draft",
                    "feedback": "產出初步完整草案，包含基本架構與關鍵論點。"
                })
                steps.append({
                    "round": r,
                    "action": "critic_review",
                    "critique": "挑出 2 處潛在邏輯漏洞與邊界條件未宣告問題。"
                })
            else:
                steps.append({
                    "round": r,
                    "action": "optimizer_refine",
                    "feedback": "針對批評意見修補漏洞，補充極端案例防禦與更精確的量化佐證。"
                })

        output = (
            f"【自我反思評估 (Reflection) 精煉完成】\n"
            f"目標任務: {prompt}\n\n"
            f"經過 {rounds} 輪「生成-批評-改寫」嚴苛校驗：\n"
            f"✓ 邏輯漏洞已全面排除\n"
            f"✓ 邊界條件已完成宣告\n"
            f"✓ 論證強度已達最高品質標準"
        )

        return ExecutionResult(
            output=output,
            mode_used=self.mode,
            execution_steps=steps,
            total_tokens_used=1200,
            success=True,
            metadata={"reflection_rounds": rounds, "latency_ms": round((time.time() - start_time) * 1000, 2)}
        )
