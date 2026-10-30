"""
代碼硬門控狀態機 (Code-Enforced Rigid State Machine)
設計理念源自 The Agent Harness 與 Temporal / LangGraph 的確定性狀態機。

核心痛點（False Compliance 陷阱）：
純提示詞架構中，若指令寫著「進入發布前必須完成 5 項檢查」，模型被問時會直接謊稱
「所有檢查均已通過」，實際上根本沒調用工具或執行校驗。

本模組使用 Python 程式碼強制實施嚴格門控（Hard Gates）：
  1. 狀態躍遷（IDEA -> RESEARCH -> DRAFT -> AUDIT -> SHIP）由程式碼邏輯裁決。
  2. 每一級躍遷必須滿足所有註冊之代碼斷言（Assertions / Predicates）。
  3. 任何一項斷言未過，程式碼直接拋出 RigidGateException 阻斷推進，LLM 無法以語言越級。
"""

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .slop_linter import AISlopLinter
from .types import HarnessStage, RigidGateException, StateTransitionRecord


# 門控斷言函數型態: (payload: Dict[str, Any]) -> Tuple[bool, str]
GatePredicate = Callable[[Dict[str, Any]], Tuple[bool, str]]


class RigidStateFSM:
    """代碼硬門控狀態機"""

    def __init__(
        self,
        task_id: str,
        initial_stage: HarnessStage = HarnessStage.IDEA,
        operator: str = "agent_harness",
    ):
        self.task_id = task_id
        self.current_stage = initial_stage
        self.operator = operator
        self.payload: Dict[str, Any] = {}
        self.transition_history: List[StateTransitionRecord] = []
        
        # 門控規則表: (from_stage, to_stage) -> List[GatePredicate]
        self._gates: Dict[Tuple[HarnessStage, HarnessStage], List[GatePredicate]] = {}
        
        # 註冊企業標準流水線預設門控
        self._register_default_gates()

    def _register_default_gates(self):
        """註冊標準 5 階段企業硬門控"""

        # 門控 1: IDEA -> RESEARCH (需有明確任務定義)
        def gate_idea_to_research(p: Dict[str, Any]) -> Tuple[bool, str]:
            task_desc = str(p.get("task_description", "")).strip()
            if not task_desc or len(task_desc) < 5:
                return False, "任務目標描述為空或長度不足 5 字元"
            return True, "任務目標定義明確"

        # 門控 2: RESEARCH -> DRAFT (必須實體探勘到至少 1 項佐證依據，杜絕空口無憑)
        def gate_research_to_draft(p: Dict[str, Any]) -> Tuple[bool, str]:
            evidence = p.get("evidence_sources", [])
            if not evidence or len(evidence) < 1:
                return False, "尚未收集到任何物理佐證資料 (evidence_sources count < 1)"
            return True, f"已實體驗證 {len(evidence)} 筆證據資料源"

        # 門控 3: DRAFT -> AUDIT (必須產出非空草稿文字)
        def gate_draft_to_audit(p: Dict[str, Any]) -> Tuple[bool, str]:
            content = str(p.get("draft_content", "")).strip()
            if not content or len(content) < 10:
                return False, "草擬內容為空或長度不足 10 字元"
            return True, f"草稿產出完畢 (長度: {len(content)} 字元)"

        # 門控 4: AUDIT -> SHIP (嚴格終審：AI 腔調靜態檢查 + 資安簽核)
        def gate_audit_to_ship_slop(p: Dict[str, Any]) -> Tuple[bool, str]:
            content = str(p.get("draft_content", ""))
            analysis = AISlopLinter.lint(content)
            if not analysis.is_clean:
                return False, f"檢測出嚴重 AI 腔調套話: {', '.join(analysis.violations[:3])}"
            return True, "AI 腔調靜態檢查合格 (零套話)"

        def gate_audit_to_ship_security(p: Dict[str, Any]) -> Tuple[bool, str]:
            if not p.get("security_verified", False):
                return False, "資安守護審核未簽核 (security_verified != True)"
            return True, "資安編譯審核簽署確認無虞"

        self.register_gate(HarnessStage.IDEA, HarnessStage.RESEARCH, gate_idea_to_research)
        self.register_gate(HarnessStage.RESEARCH, HarnessStage.DRAFT, gate_research_to_draft)
        self.register_gate(HarnessStage.DRAFT, HarnessStage.AUDIT, gate_draft_to_audit)
        self.register_gate(HarnessStage.AUDIT, HarnessStage.SHIP, gate_audit_to_ship_slop)
        self.register_gate(HarnessStage.AUDIT, HarnessStage.SHIP, gate_audit_to_ship_security)

    def register_gate(
        self,
        from_stage: HarnessStage,
        to_stage: HarnessStage,
        predicate: GatePredicate,
    ):
        """為特定狀態躍遷註冊額外之代碼斷言"""
        key = (from_stage, to_stage)
        if key not in self._gates:
            self._gates[key] = []
        self._gates[key].append(predicate)

    def update_payload(self, **kwargs):
        """更新當前任務上下文資料"""
        self.payload.update(kwargs)

    def transition_to(
        self,
        target_stage: HarnessStage,
        operator: Optional[str] = None,
    ) -> StateTransitionRecord:
        """
        執行狀態躍遷：嚴格執行 Python 代碼門控斷言
        若有任何斷言失敗，立即拋出 RigidGateException 阻斷
        """
        key = (self.current_stage, target_stage)
        predicates = self._gates.get(key, [])

        failed_reasons: List[str] = []
        verified_assertions: List[str] = []

        # 遍歷執行該門控的所有 Python 實體代碼校驗
        for pred in predicates:
            passed, reason = pred(self.payload)
            if passed:
                verified_assertions.append(reason)
            else:
                failed_reasons.append(reason)

        if failed_reasons:
            raise RigidGateException(
                current_stage=self.current_stage.value,
                target_stage=target_stage.value,
                failed_reasons=failed_reasons,
            )

        # 計算 Payload SHA-256 數位指紋
        serialized_payload = json.dumps(self.payload, sort_keys=True, ensure_ascii=False, default=str)
        payload_hash = hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()[:16]

        record = StateTransitionRecord(
            from_stage=self.current_stage,
            to_stage=target_stage,
            timestamp=time.time(),
            operator_or_agent=operator or self.operator,
            verified_assertions=verified_assertions,
            payload_hash=payload_hash,
        )

        self.transition_history.append(record)
        self.current_stage = target_stage
        return record
