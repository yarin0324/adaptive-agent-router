"""
Agent 外骨骼治理層 (The Agent Harness Module)
提供代碼硬門控狀態機、去 AI 味靜態檢查器、漸進式技能註冊表與無菌室子代理隔離。
"""

from .clean_room import CleanRoomSubagentRunner
from .engine import AgentHarness
from .progressive_skills import ProgressiveSkillRegistry
from .slop_linter import AISlopLinter
from .state_machine import RigidStateFSM
from .types import (
    AISlopAnalysis,
    AISlopViolationException,
    CleanRoomResult,
    HarnessStage,
    RigidGateException,
    SkillDescriptor,
    StateTransitionRecord,
)

__all__ = [
    "HarnessStage",
    "RigidGateException",
    "AISlopViolationException",
    "AISlopAnalysis",
    "SkillDescriptor",
    "StateTransitionRecord",
    "CleanRoomResult",
    "AISlopLinter",
    "RigidStateFSM",
    "ProgressiveSkillRegistry",
    "CleanRoomSubagentRunner",
    "AgentHarness",
]
