"""
動態升級與狀態遷移引擎 (Adaptive Escalation Engine)
借鏡自 TradingAgents Graph 條件邊 (Conditional Edge) 與狀態機設計。
當初步模式（如單次回應）檢測到置信度不足或複雜度超出預期時，自動平滑升級到更高階模式。
"""

from typing import Dict, Any, Tuple
from ..types import AgentMode


class AdaptiveEscalationEngine:
    """模式動態升級評估器"""

    # 定義升級階梯 (Escalation Ladder)
    LADDER = {
        AgentMode.SINGLE_TURN: AgentMode.REACT,           # 單次回答不出來 ➜ 升級 ReAct 探索
        AgentMode.REACT: AgentMode.PLANNER_EXECUTOR,      # ReAct 步數過多 ➜ 升級 Planner 全面拆解
        AgentMode.PLANNER_EXECUTOR: AgentMode.MULTI_AGENT # 拆解後分歧過大 ➜ 升級 Multi-Agent 專家辯論
    }

    @classmethod
    def evaluate_escalation(
        cls,
        current_mode: AgentMode,
        confidence_score: float,
        needs_more_tools: bool = False,
    ) -> Tuple[bool, AgentMode, str]:
        """
        評估是否需要動態升級
        :param current_mode: 當前執行模式
        :param confidence_score: 當前模型輸出的置信度 (0.0 ~ 1.0)
        :param needs_more_tools: 是否需要額外未載入的工具
        :return: (是否升級, 目標模式, 升級原因)
        """
        # 置信度低於 0.6 或明確缺少工具，且存在更高階階梯
        if (confidence_score < 0.6 or needs_more_tools) and current_mode in cls.LADDER:
            target_mode = cls.LADDER[current_mode]
            reason = (
                f"置信度低於門檻 ({confidence_score:.2f} < 0.60)，"
                f"由 {current_mode.value} 自動無縫升級為 {target_mode.value} 進行深度推演。"
            )
            return True, target_mode, reason

        return False, current_mode, "置信度足夠，無需升級。"
