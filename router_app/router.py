"""
核心動態路由器 (Adaptive Agent Router)
整合「靜態安全快篩」、「語意原型相似度比對 (Semantic Router)」與「雙維度矩陣分流 (RouteLLM: Pattern × Model Tier)」。
"""

import os
import re
from typing import Any, Dict, List, Optional
from .types import AgentMode, RiskLevel, ModelTier, RoutingDecision
from .config import config
from .cache.semantic_matcher import SemanticPrototypeMatcher
from .cache.elo_tuner import ELORatingTuner


class AdaptiveRouter:
    """
    動態路由器 (模式 3: Router)
    分析使用者輸入與系統脈絡，自動輸出 (Pattern × Model Tier) 最佳解。
    整合 ELO 動態等級分調校偏好。
    """

    # 模式與算力階層之映射矩陣 (借鏡 RouteLLM)
    MODEL_TIER_MAP = {
        AgentMode.SINGLE_TURN: ModelTier.FAST,
        AgentMode.TOOL_USE: ModelTier.FAST,
        AgentMode.REACT: ModelTier.STANDARD,
        AgentMode.VERIFIER_GATED: ModelTier.STANDARD,
        AgentMode.PLANNER_EXECUTOR: ModelTier.REASONING,
        AgentMode.REFLECTION: ModelTier.REASONING,
        AgentMode.MULTI_AGENT: ModelTier.REASONING,
        AgentMode.ENSEMBLE: ModelTier.REASONING,
        AgentMode.MEMORY_AUGMENTED: ModelTier.FAST,
    }

    def __init__(self, default_model: Optional[str] = None, elo_tuner: Optional[ELORatingTuner] = None):
        self.default_model = default_model or config.ROUTER_MODEL
        self.semantic_matcher = SemanticPrototypeMatcher()
        self.elo_tuner = elo_tuner or ELORatingTuner()

    def route(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> RoutingDecision:
        """
        分層級決策管線
        """
        # 第一道防線：高風險與安全性關鍵字快篩 (0 延遲)
        critical_match = self._check_safety_guardrails(prompt)
        if critical_match:
            return critical_match

        # 第二道防線：語意原型相似度比對 (借鏡 Semantic Router，5ms 快速匹配)
        semantic_match = self._semantic_prototype_route(prompt)
        if semantic_match:
            return semantic_match

        # 第三道防線：特徵啟發式規則評估 (Rule-based Fast Router)
        heuristic_match = self._heuristic_route(prompt)
        if heuristic_match:
            return heuristic_match

        # 第四道防線：動態降級為工具調用模式
        return self._fallback_route(prompt, context)

    def _check_safety_guardrails(self, prompt: str) -> Optional[RoutingDecision]:
        """檢查是否涉及不可逆操作或高風險指令"""
        p_lower = prompt.lower()
        critical_keywords = [
            "刪除", "delete", "drop table", "truncate", "清空", 
            "轉帳", "付款", "下單", "交易執行", "永久銷毀"
        ]
        
        for kw in critical_keywords:
            if kw in p_lower:
                mode = AgentMode.VERIFIER_GATED
                return RoutingDecision(
                    mode=mode,
                    model_tier=self.MODEL_TIER_MAP[mode],
                    reasoning=f"偵測到高風險操作關鍵字「{kw}」，啟動安全門控機制以防誤操作。",
                    risk_level=RiskLevel.CRITICAL,
                    estimated_steps=2,
                    require_human_confirmation=True,
                    tags=["safety_gate", "critical_operation"]
                )
        return None

    def _semantic_prototype_route(self, prompt: str) -> Optional[RoutingDecision]:
        """借鏡 Semantic Router: 餘弦語意原型快速匹配 + ELO 動態權重修正"""
        match_result = self.semantic_matcher.match(prompt)
        if match_result:
            mode, score, prototype = match_result
            bias = self.elo_tuner.get_routing_bias(mode)
            calibrated_score = score + bias

            # 若經 ELO 懲罰後分數低於門檻 (0.50)，暫緩推薦
            if calibrated_score < 0.50:
                return None

            elo_stat = self.elo_tuner.stats.get(mode)
            elo_val = elo_stat.elo_rating if elo_stat else 1200.0

            return RoutingDecision(
                mode=mode,
                model_tier=self.MODEL_TIER_MAP.get(mode, ModelTier.STANDARD),
                reasoning=f"命中語意原型特徵 (原始分 {score:.2f}, ELO偏置 {bias:+.2f} ➜ 校準分 {calibrated_score:.2f}): '{prototype}'",
                risk_level=RiskLevel.MEDIUM if mode == AgentMode.REFLECTION else RiskLevel.LOW,
                estimated_steps=3 if mode in [AgentMode.PLANNER_EXECUTOR, AgentMode.MULTI_AGENT] else 1,
                tags=["semantic_prototype_hit", f"score_{score:.2f}", f"elo_{elo_val:.0f}"]
            )
        return None

    def _heuristic_route(self, prompt: str) -> Optional[RoutingDecision]:
        """基於語意特徵與意圖樣式的快篩路由"""
        p_lower = prompt.lower()

        if any(w in p_lower for w in ["規劃", "完整方案", "步驟分解", "專案計劃", "拆解", "roadmap"]):
            mode = AgentMode.PLANNER_EXECUTOR
            return RoutingDecision(
                mode=mode,
                model_tier=self.MODEL_TIER_MAP[mode],
                reasoning="問題屬於長流程且具多步驟結構，需先由 Planner 拆解並行執行。",
                risk_level=RiskLevel.LOW,
                estimated_steps=4,
                tags=["multi_step", "structured_plan"]
            )

        if any(w in p_lower for w in ["反思", "挑出漏洞", "合約審查", "嚴格批評", "自我優化", "精煉"]):
            mode = AgentMode.REFLECTION
            return RoutingDecision(
                mode=mode,
                model_tier=self.MODEL_TIER_MAP[mode],
                reasoning="任務對品質與精準度要求極高，指派 Critic 模型執行多輪自我反思優化。",
                risk_level=RiskLevel.MEDIUM,
                estimated_steps=3,
                tags=["high_quality", "reflection"]
            )

        if any(w in p_lower for w in ["專家辯論", "多角度評估", "跨部門", "紅隊審查", "多代理"]):
            mode = AgentMode.MULTI_AGENT
            return RoutingDecision(
                mode=mode,
                model_tier=self.MODEL_TIER_MAP[mode],
                reasoning="需要不同學門或角色的專家協同作業與交叉論證。",
                risk_level=RiskLevel.LOW,
                estimated_steps=3,
                tags=["collaboration", "cross_domain"]
            )

        if any(w in p_lower for w in ["並行計算", "多數決", "交叉驗證", "高可信度投票"]):
            mode = AgentMode.ENSEMBLE
            return RoutingDecision(
                mode=mode,
                model_tier=self.MODEL_TIER_MAP[mode],
                reasoning="需要排除模型偶發性幻覺，進行多次採樣與投票融合。",
                risk_level=RiskLevel.LOW,
                estimated_steps=3,
                tags=["ensemble", "high_consistency"]
            )

        if any(w in p_lower for w in ["調查", "找找看", "探索", "摸索", "為什麼會這樣"]):
            mode = AgentMode.REACT
            return RoutingDecision(
                mode=mode,
                model_tier=self.MODEL_TIER_MAP[mode],
                reasoning="目標路徑動態不確定，需要一邊探索一邊調整假設的 ReAct 迴圈。",
                risk_level=RiskLevel.LOW,
                estimated_steps=3,
                tags=["exploratory", "dynamic_loop"]
            )

        if any(w in p_lower for w in ["萃取", "欄位", "整理成表格", "翻譯", "摘要", "總結成3點"]):
            mode = AgentMode.SINGLE_TURN
            return RoutingDecision(
                mode=mode,
                model_tier=self.MODEL_TIER_MAP[mode],
                reasoning="任務屬性單一明確，採用單次增強型推論即可滿足，以獲得最低延遲。",
                risk_level=RiskLevel.LOW,
                estimated_steps=1,
                tags=["low_latency", "cost_efficient"]
            )

        return None

    def _fallback_route(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> RoutingDecision:
        mode = AgentMode.TOOL_USE
        return RoutingDecision(
            mode=mode,
            model_tier=self.MODEL_TIER_MAP[mode],
            reasoning="語意複雜且包含自訂參數，導向彈性工具調用代理 (Tool Use Agent)。",
            risk_level=RiskLevel.LOW,
            estimated_steps=2,
            tags=["dynamic_fallback", "tool_use"]
        )
