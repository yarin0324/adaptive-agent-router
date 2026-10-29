"""
型別定義與資料結構 (Types & Models)
提供跨專案標準化的 Context, Mode 與 RoutingDecision 格式。
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    """
    對應 AI Agent 十大設計架構模式
    """
    SINGLE_TURN = "mode_1_single_turn"           # 1. 增強型單次回應 (RAG / 一問一答 / 格式轉換)
    REACT = "mode_2_react"                       # 2. 反思迴圈 (思考 ➜ 工具 ➜ 觀察 ➜ 修正)
    ROUTER = "mode_3_router"                     # 3. 路由器 (系統核心指揮官)
    PLANNER_EXECUTOR = "mode_4_planner"          # 4. 規劃 - 執行器 (任務拆解、長流程多步驟)
    REFLECTION = "mode_5_reflection"             # 5. 評估 - 優化自我反思 (Critic 審查與重構)
    VERIFIER_GATED = "mode_6_verifier_gated"     # 6. 驗證門控 (安全護欄、不可逆操作二次授權)
    MULTI_AGENT = "mode_7_multi_agent"           # 7. 多代理協作 (專家辯論、領域協作)
    TOOL_USE = "mode_8_tool_use"                 # 8. 工具使用代理 (靈活工具調用)
    ENSEMBLE = "mode_9_ensemble"                 # 9. 並行自洽 / 多模型投票 (高穩定度輸出)
    MEMORY_AUGMENTED = "mode_10_memory"          # 10. 情境式記憶 (長期記憶喚醒)


class RiskLevel(str, Enum):
    """操作風險評估"""
    LOW = "low"            # 純讀取、日常閒聊、知識查詢
    MEDIUM = "medium"      # 涉及外部 API 頻率限制、多文件大量解析
    HIGH = "high"          # 涉及資料庫寫入、系統檔案修改、發送郵件/外部通知
    CRITICAL = "critical"  # 金融交易下單、刪除資料表、不可逆付款或系統停機


class ModelTier(str, Enum):
    """
    模型算力檔次矩陣 (借鏡 RouteLLM 設計)
    動態為不同複雜度的 Pattern 指派最經濟算力階層
    """
    FAST = "fast"              # 輕量快速 (如 gpt-4o-mini, gemini-1.5-flash) - 適用 Mode 1, 8
    STANDARD = "standard"      # 標準通用 (如 gpt-4o, claude-3-5-haiku) - 適用 Mode 2, 6
    REASONING = "reasoning"    # 深度推理 (如 claude-3-5-sonnet, o1, gemini-1.5-pro) - 適用 Mode 4, 5, 7, 9


class RoutingDecision(BaseModel):
    """
    路由器輸出的結構化決策 (2D 矩陣: Pattern × Model Tier)
    """
    mode: AgentMode = Field(..., description="選擇的 Agent 執行模式")
    model_tier: ModelTier = Field(default=ModelTier.STANDARD, description="指派之最經濟算力階層")
    reasoning: str = Field(..., description="選擇此模式的判斷理由與底層思考")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="評估該任務的風險等級")
    estimated_steps: int = Field(default=1, description="預估需要的執行步數或輪次")
    require_human_confirmation: bool = Field(default=False, description="是否需要人工審核確認才可執行")
    tags: List[str] = Field(default_factory=list, description="任務屬性標籤，例如 ['sql', 'high_latency', 'critical_data']")


class ExecutionResult(BaseModel):
    """
    執行器回傳的標準化成果
    """
    output: str = Field(..., description="最終呈現給使用者的答案或成果")
    mode_used: AgentMode = Field(..., description="本次執行的模式")
    execution_steps: List[Dict[str, Any]] = Field(default_factory=list, description="思考過程與中間工具呼叫記錄")
    total_tokens_used: Optional[int] = Field(default=0, description="消耗 Token 數估計")
    success: bool = Field(default=True, description="任務是否執行成功")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="專案自訂的擴充中繼資料")
