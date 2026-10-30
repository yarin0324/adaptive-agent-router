"""
自適應推測解碼門控器 (Adaptive Speculative Decoding Gator)
設計理念源自 EAGLE-2 (Li et al., 2024) 與 Medusa (Cai et al., 2024)。

核心原理：
推測解碼（Speculative Decoding）透過輕量 Draft Head 或小模型預測未來 K 個 Token，
再由大模型一次性驗證。然而推測解碼的加速效益極度依賴於「草稿接受率 (Acceptance Rate α)」：
  - 當 α >= 80% (格式化 JSON、實體摘錄、摘要)：可達成 2.0x ~ 2.8x 的有感提速。
  - 當 α <= 35% (數學邏輯證明、複雜代碼生成、安全審計)：因頻繁猜錯驗證 Rollback，
    額外計算開銷反致整體延遲惡化 (+20% ~ +35%)。

本模組於 Gateway 層依據任務意圖、Agent 架構模式與輸出約束，
動態向下游推論引擎（vLLM / SGLang）發送最佳推測參數（K=0, K=3 或 K=5）。
"""

import re
from typing import Any, Dict, Optional

from .types import SpeculativeDecision, SpeculativeMode


class AdaptiveSpeculativeGator:
    """自適應推測解碼門控器"""

    # 典型高接受率 (High Alpha) 任務特徵
    HIGH_ALPHA_PATTERNS = [
        re.compile(r"(?:json|xml|yaml|csv|表格|列表|欄位|整理成|格式化|提取|抽出|summary|summarize)", re.I),
        re.compile(r"(?:翻譯|英翻中|中翻英|潤飾|改寫|糾錯|校對)", re.I),
        re.compile(r"(?:統一編號|電話|地址|身分證|金額|發票|日期|訂單)", re.I),
    ]

    # 典型低接受率 (Low Alpha - 嚴格邏輯/高熵值) 任務特徵
    LOW_ALPHA_PATTERNS = [
        re.compile(r"(?:證明|推演|數學|幾何|極限|積分|微積分|矩陣分解)", re.I),
        re.compile(r"(?:漏洞分析|逆向工程|二進位|緩衝區溢位|exploit|安全審計)", re.I),
        re.compile(r"(?:撰寫完整演算法|實作紅黑樹|動態規劃|leetcode|並行死鎖)", re.I),
        re.compile(r"(?:辯論|反駁|哲學|倫理困境|權衡分析)", re.I),
    ]

    # 依 Agent 架構模式的預設傾向
    MODE_PREFERENCES = {
        "mode_1_single_turn": SpeculativeMode.AGGRESSIVE,
        "mode_2_react": SpeculativeMode.CONSERVATIVE,
        "mode_3_plan_solve": SpeculativeMode.CONSERVATIVE,
        "mode_4_planner": SpeculativeMode.CONSERVATIVE,
        "mode_5_reflection": SpeculativeMode.OFF,          # 反思審計不宜過度猜測
        "mode_6_verifier_gated": SpeculativeMode.OFF,      # 安全門控需單次精確
        "mode_7_multi_agent": SpeculativeMode.OFF,         # 多代理思辨高熵
        "mode_8_tool_agent": SpeculativeMode.AGGRESSIVE,   # 工具參數大多高度結構化
        "mode_9_ensemble": SpeculativeMode.CONSERVATIVE,
        "mode_10_memory": SpeculativeMode.AGGRESSIVE,
    }

    @classmethod
    def evaluate(
        cls,
        query: str,
        mode: str = "mode_1_single_turn",
        format_constraint: Optional[str] = None,
    ) -> SpeculativeDecision:
        """
        評估推測解碼適用性並輸出調度參數
        """
        # 1. 強格式約束優先檢查 (如指定 JSON 輸出，結構高度確定)
        if format_constraint and "json" in format_constraint.lower():
            return SpeculativeDecision(
                enabled=True,
                mode=SpeculativeMode.AGGRESSIVE,
                draft_tokens=5,
                predicted_acceptance_rate=0.88,
                estimated_speedup=2.45,
                rationale="偵測到嚴格 JSON Schema 約束，Token 轉移轉移機率高度確定，啟用積極推測 (K=5)。",
            )

        # 2. 低接受率特徵掃描 (優先避坑)
        for pat in cls.LOW_ALPHA_PATTERNS:
            if pat.search(query):
                return SpeculativeDecision(
                    enabled=False,
                    mode=SpeculativeMode.OFF,
                    draft_tokens=0,
                    predicted_acceptance_rate=0.32,
                    estimated_speedup=1.00,
                    rationale="偵測到高複雜度數理推導、核心代碼或安全審計特徵，預估草稿接受率低於 35%，停用推測解碼以避免驗證 Rollback 負優化。",
                )

        # 3. 高接受率特徵掃描
        for pat in cls.HIGH_ALPHA_PATTERNS:
            if pat.search(query):
                return SpeculativeDecision(
                    enabled=True,
                    mode=SpeculativeMode.AGGRESSIVE,
                    draft_tokens=5,
                    predicted_acceptance_rate=0.82,
                    estimated_speedup=2.25,
                    rationale="偵測到資訊抽取、格式轉換或摘要任務，文字規律性高，啟用積極推測 (K=5)。",
                )

        # 4. 依照 Agent 架構模式基準進行分流
        default_pref = cls.MODE_PREFERENCES.get(mode, SpeculativeMode.CONSERVATIVE)
        if default_pref == SpeculativeMode.AGGRESSIVE:
            return SpeculativeDecision(
                enabled=True,
                mode=SpeculativeMode.AGGRESSIVE,
                draft_tokens=5,
                predicted_acceptance_rate=0.78,
                estimated_speedup=2.10,
                rationale=f"架構模式 {mode} 具備良好結構化特性，啟用積極推測 (K=5)。",
            )
        elif default_pref == SpeculativeMode.OFF:
            return SpeculativeDecision(
                enabled=False,
                mode=SpeculativeMode.OFF,
                draft_tokens=0,
                predicted_acceptance_rate=0.40,
                estimated_speedup=1.00,
                rationale=f"架構模式 {mode} 涉及多步推導或嚴格門控驗證，停用推測解碼保障精度。",
            )
        else:
            return SpeculativeDecision(
                enabled=True,
                mode=SpeculativeMode.CONSERVATIVE,
                draft_tokens=3,
                predicted_acceptance_rate=0.68,
                estimated_speedup=1.55,
                rationale="常規推論任務，啟用保守推測解碼 (K=3) 在穩定性與吐字延遲間取得平衡。",
            )

    @classmethod
    def to_downstream_payload(cls, decision: SpeculativeDecision) -> Dict[str, Any]:
        """產出符合 vLLM / SGLang / TensorRT-LLM 介面規範的調度參數"""
        if not decision.enabled:
            return {
                "use_speculative": False,
                "speculative_draft_tokens": 0,
            }
        return {
            "use_speculative": True,
            "speculative_draft_tokens": decision.draft_tokens,
            "speculative_max_model_len": 4096,
            "draft_temperature": 0.0,
        }
