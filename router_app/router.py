"""
核心動態路由器 (Adaptive Agent Router)
整合「快速啟發式規則過濾」與「LLM 結構化意圖判定」，提供極速且精準的模式路由。
"""

import os
import re
from typing import Any, Dict, List, Optional
from .types import AgentMode, RiskLevel, RoutingDecision
from .config import config


class AdaptiveRouter:
    """
    動態路由器 (模式 3: Router)
    分析使用者輸入與系統脈絡，自動指派最合適的 Agent 執行架構模式。
    """

    def __init__(self, default_model: Optional[str] = None):
        self.default_model = default_model or config.ROUTER_MODEL

    def route(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> RoutingDecision:
        """
        分析提示詞並做出路由決策
        """
        # 第一道防線：高風險與安全性關鍵字快篩 (0 延遲，防止惡意繞過)
        critical_match = self._check_safety_guardrails(prompt)
        if critical_match:
            return critical_match

        # 第二道防線：特徵啟發式規則評估 (Rule-based Fast Router)
        heuristic_match = self._heuristic_route(prompt)
        if heuristic_match:
            return heuristic_match

        # 第三道防線：若無明顯規則特徵，走 LLM 深度語義分析
        return self._llm_semantic_route(prompt, context)

    def _check_safety_guardrails(self, prompt: str) -> Optional[RoutingDecision]:
        """檢查是否涉及不可逆操作或高風險指令"""
        p_lower = prompt.lower()
        critical_keywords = [
            "刪除", "delete", "drop table", "truncate", "清空", 
            "轉帳", "付款", "下單", "交易執行", "永久銷毀"
        ]
        
        for kw in critical_keywords:
            if kw in p_lower:
                return RoutingDecision(
                    mode=AgentMode.VERIFIER_GATED,
                    reasoning=f"偵測到高風險操作關鍵字「{kw}」，啟動安全門控機制以防誤操作。",
                    risk_level=RiskLevel.CRITICAL,
                    estimated_steps=2,
                    require_human_confirmation=True,
                    tags=["safety_gate", "critical_operation"]
                )
        return None

    def _heuristic_route(self, prompt: str) -> Optional[RoutingDecision]:
        """基於語意特徵與意圖樣式的快篩路由"""
        p_lower = prompt.lower()

        # 1. 規劃與長流程特徵
        if any(w in p_lower for w in ["規劃", "完整方案", "步驟分解", "專案計劃", "拆解", "roadmap"]):
            return RoutingDecision(
                mode=AgentMode.PLANNER_EXECUTOR,
                reasoning="問題屬於長流程且具多步驟結構，需先由 Planner 拆解並行執行。",
                risk_level=RiskLevel.LOW,
                estimated_steps=4,
                tags=["multi_step", "structured_plan"]
            )

        # 2. 批判、反思、合約挑刺特徵
        if any(w in p_lower for w in ["反思", "挑出漏洞", "合約審查", "嚴格批評", "自我優化", "精煉"]):
            return RoutingDecision(
                mode=AgentMode.REFLECTION,
                reasoning="任務對品質與精準度要求極高，指派 Critic 模型執行多輪自我反思優化。",
                risk_level=RiskLevel.MEDIUM,
                estimated_steps=3,
                tags=["high_quality", "reflection"]
            )

        # 3. 跨領域專家、多角色辯論特徵
        if any(w in p_lower for w in ["專家辯論", "多角度評估", "跨部門", "紅隊審查", "多代理"]):
            return RoutingDecision(
                mode=AgentMode.MULTI_AGENT,
                reasoning="需要不同學門或角色的專家協同作業與交叉論證。",
                risk_level=RiskLevel.LOW,
                estimated_steps=3,
                tags=["collaboration", "cross_domain"]
            )

        # 4. 高可靠度、投票與並行自洽
        if any(w in p_lower for w in ["並行計算", "多數決", "交叉驗證", "高可信度投票"]):
            return RoutingDecision(
                mode=AgentMode.ENSEMBLE,
                reasoning="需要排除模型偶發性幻覺，進行多次採樣與投票融合。",
                risk_level=RiskLevel.LOW,
                estimated_steps=3,
                tags=["ensemble", "high_consistency"]
            )

        # 5. 探索性問題 (ReAct 思考迴圈)
        if any(w in p_lower for w in ["調查", "找找看", "探索", "摸索", "為什麼會這樣"]):
            return RoutingDecision(
                mode=AgentMode.REACT,
                reasoning="目標路徑動態不確定，需要一邊探索一邊調整假設的 ReAct 迴圈。",
                risk_level=RiskLevel.LOW,
                estimated_steps=3,
                tags=["exploratory", "dynamic_loop"]
            )

        # 6. 單純資料整理、欄位抽取、翻譯摘要 (單次回應)
        if any(w in p_lower for w in ["萃取", "欄位", "整理成表格", "翻譯", "摘要", "總結成3點"]):
            return RoutingDecision(
                mode=AgentMode.SINGLE_TURN,
                reasoning="任務屬性單一明確，採用單次增強型推論即可滿足，以獲得最低延遲。",
                risk_level=RiskLevel.LOW,
                estimated_steps=1,
                tags=["low_latency", "cost_efficient"]
            )

        return None

    def _llm_semantic_route(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> RoutingDecision:
        """
        當規則無法完全判定時，呼叫輕量 LLM 或降級為工具/單次回應
        """
        # 如果有設定 LiteLLM 且有 API Key，可在此處調用 LLM.with_structured_output
        # 預設做優雅降級 (Fallback to Tool Use / ReAct)
        return RoutingDecision(
            mode=AgentMode.TOOL_USE,
            reasoning="語意複雜且包含自訂參數，導向彈性工具調用代理 (Tool Use Agent)。",
            risk_level=RiskLevel.LOW,
            estimated_steps=2,
            tags=["dynamic_fallback", "tool_use"]
        )
