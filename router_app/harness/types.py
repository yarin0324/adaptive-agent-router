"""
Agent 外骨骼治理層 (The Agent Harness) 核心型態定義
涵蓋硬性狀態機階段、AI 腔調靜態檢查結果、漸進式技能描述符與無菌室子代理回傳。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class HarnessStage(str, Enum):
    """硬性代碼狀態機工作流程階段 (Rigid State FSM)"""
    IDEA = "idea"           # 原始意圖 / 需求接收入口
    RESEARCH = "research"   # 依據資料源進行事實探勘與 RAG 檢索
    DRAFT = "draft"         # 產出初步執行內容或草案
    AUDIT = "audit"         # 代碼靜態檢查 (Linter / AST / 安全門控)
    SHIP = "ship"           # 門控全數通過，正式發布 / 落盤執行


class RigidGateException(Exception):
    """當代碼硬門控斷言失敗時拋出，徹底阻斷 LLM 虛假合規跳級"""
    def __init__(self, current_stage: str, target_stage: str, failed_reasons: List[str]):
        self.current_stage = current_stage
        self.target_stage = target_stage
        self.failed_reasons = failed_reasons
        msg = (
            f"【代碼硬門控阻斷】無法從階段 '{current_stage}' 躍遷至 '{target_stage}'！\n"
            f"未滿足之代碼斷言: {'; '.join(failed_reasons)}"
        )
        super().__init__(msg)


class AISlopViolationException(Exception):
    """當生成內容含有過多禁用的 AI 套話或虛假腔調時拋出"""
    def __init__(self, score: float, violations: List[str]):
        self.score = score
        self.violations = violations
        super().__init__(f"AI 腔調靜態檢查未通過 (Slop Score: {score:.2f})！違規項目: {', '.join(violations[:5])}")


@dataclass
class AISlopAnalysis:
    """AI 腔調靜態檢查結果報告"""
    slop_score: float                # 0.0 (純淨自然) ~ 1.0 (嚴重 AI 套話)
    is_clean: bool                   # 是否低於容許門檻
    violations: List[str]            # 命中之禁忌詞彙 / 句型清單
    total_words: int                 # 總詞數
    cleaned_text: str                # 自動去噪後的自然文字
    latency_ms: float                # 檢查耗時 (毫秒)


@dataclass
class SkillDescriptor:
    """漸進式揭露技能描述符 (Progressive Skill Disclosure)"""
    name: str                        # 技能唯一識別碼
    summary: str                     # 單行簡要說明 (~15-20 Tokens，常駐於 System Prompt)
    category: str = "general"        # 分類 (security, finance, tool, reasoning)
    full_instructions: str = ""      # 完整詳細指令與規範 (僅在被調用時隨需載入)
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    is_loaded: bool = False          # 是否已加載完整上下文


@dataclass
class StateTransitionRecord:
    """狀態機躍遷物理稽核記錄"""
    from_stage: HarnessStage
    to_stage: HarnessStage
    timestamp: float
    operator_or_agent: str
    verified_assertions: List[str]
    payload_hash: str


@dataclass
class CleanRoomResult:
    """無菌室子代理隔離執行結果 (Clean-Room Subagent Output)"""
    subagent_id: str
    task_description: str
    success: bool
    summary_output: str              # 僅將濃縮摘要繳回主上下文
    structured_artifacts: Dict[str, Any] = field(default_factory=dict)
    tokens_consumed: int = 0
    execution_time_ms: float = 0.0
