"""
Agent 外骨骼治理核心引擎 (Agent Harness Engine)
統一對外提供：
  1. 代碼硬門控狀態機 (RigidStateFSM)
  2. 去 AI 味靜態檢查器 (AISlopLinter)
  3. 漸進式技能註冊表 (ProgressiveSkillRegistry)
  4. 無菌室子代理隔離執行 (CleanRoomSubagentRunner)
"""

from typing import Any, Callable, Dict, List, Optional

from .clean_room import CleanRoomSubagentRunner
from .progressive_skills import ProgressiveSkillRegistry
from .slop_linter import AISlopLinter
from .state_machine import RigidStateFSM
from .types import (
    AISlopAnalysis,
    CleanRoomResult,
    HarnessStage,
    RigidGateException,
    SkillDescriptor,
    StateTransitionRecord,
)


class AgentHarness:
    """Agent 外骨骼核心協調器"""

    def __init__(
        self,
        skill_registry: Optional[ProgressiveSkillRegistry] = None,
        max_allowed_slop: float = 0.05,
    ):
        self.skill_registry = skill_registry or ProgressiveSkillRegistry()
        self.max_allowed_slop = max_allowed_slop
        self.linter = AISlopLinter
        self._active_fsms: Dict[str, RigidStateFSM] = {}

    def create_workflow(
        self,
        task_id: str,
        task_description: str,
    ) -> RigidStateFSM:
        """建立全新任務之硬門控狀態機"""
        fsm = RigidStateFSM(task_id=task_id)
        fsm.update_payload(task_description=task_description)
        self._active_fsms[task_id] = fsm
        return fsm

    def get_workflow(self, task_id: str) -> Optional[RigidStateFSM]:
        """檢索進行中之狀態機"""
        return self._active_fsms.get(task_id)

    def lint_text(self, text: str) -> AISlopAnalysis:
        """對文字進行 AI 腔調靜態掃描與去噪"""
        return self.linter.lint(text, max_allowed_slop=self.max_allowed_slop)

    def assert_clean(self, text: str):
        """代碼硬斷言：含有嚴重 AI 腔調即刻阻斷"""
        self.linter.assert_clean(text, max_allowed_slop=self.max_allowed_slop)

    def run_subagent(
        self,
        subagent_id: str,
        task_description: str,
        task_fn: Callable[..., Dict[str, Any]],
        **kwargs,
    ) -> CleanRoomResult:
        """在隔離無菌室中運行子代理"""
        return CleanRoomSubagentRunner.execute_in_clean_room(
            subagent_id=subagent_id,
            task_description=task_description,
            task_fn=task_fn,
            **kwargs,
        )

    def register_skill(
        self,
        name: str,
        summary: str,
        category: str = "general",
        full_instructions: str = "",
        parameters_schema: Optional[Dict[str, Any]] = None,
    ):
        """註冊一項漸進式技能"""
        self.skill_registry.register(
            name=name,
            summary=summary,
            category=category,
            full_instructions=full_instructions,
            parameters_schema=parameters_schema,
        )

    def get_skill_index(self) -> str:
        """取得常態常駐極簡技能目錄"""
        return self.skill_registry.get_compact_index()

    def resolve_skills(self, names: List[str]) -> str:
        """隨需加載完整技能說明"""
        return self.skill_registry.resolve_skills(names)
