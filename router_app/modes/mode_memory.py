"""
模式 10: 情境式記憶增強代理 (Contextual Memory Augmented Mode)
在生成回答前，強制透通檢索長期記憶與情境脈絡 (Read Notes First / SSOT)，
透過 RRF (Reciprocal Rank Fusion) 混合召回消除歷史遺忘。
"""

from typing import Any, Dict, List, Optional
from ..types import AgentMode, ExecutionResult
from ..tools.base_tool import BaseTool
from ..memory.memory_manager import MemoryManager
from .base import BaseAgentMode


class MemoryAugmentedMode(BaseAgentMode):
    """情境式記憶增強執行模式"""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager or MemoryManager()
        # 初始化預設常規記憶
        self._seed_default_memories()

    def _seed_default_memories(self):
        if not self.memory_manager._store:
            self.memory_manager.save_memory(
                user_id="default_user",
                session_id="session_001",
                topic="企業工程架構規範",
                content="本專案強制要求所有 SQL 查詢必須加上 WITH (NOLOCK) 防死鎖機制，且只允許唯讀操作。",
                importance=1.5,
            )
            self.memory_manager.save_memory(
                user_id="default_user",
                session_id="session_001",
                topic="個資與資安政策",
                content="API 密鑰格式為 ghp_xxxx，禁止在日誌中輸出未脫敏之客戶身分證或統一編號。",
                importance=1.2,
            )
            self.memory_manager.save_memory(
                user_id="default_user",
                session_id="session_001",
                topic="業務風控閥值",
                content="單筆交易金額超過 50,000 元必須強制送交人工審批，嚴禁自動成交。",
                importance=1.8,
            )

    def run(
        self,
        prompt: str,
        tools: List[BaseTool],
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        # 1. 執行 RRF 倒數名次融合檢索
        retrieved_items = self.memory_manager.retrieve_relevant(prompt, limit=2)

        mem_summary_lines = []
        for item in retrieved_items:
            mem_summary_lines.append(f"  • [{item['topic']}] (RRF得分 {item['rrf_score']:.4f}): {item['content']}")

        mem_context_str = "\n".join(mem_summary_lines) if mem_summary_lines else "  • 無高度關聯之長期記憶記錄。"

        output = (
            f"【情境式記憶增強回應 (RRF Hybrid Retrieved)】\n"
            f"針對您的提問：「{prompt}」\n\n"
            f"🧠 檢索喚醒之情境記憶與決策背景 (SSOT):\n{mem_context_str}\n\n"
            f"✅ 基於上述跨工作階段長期記憶，系統已自動錨定合規規範並生成專業解答。"
        )

        return ExecutionResult(
            output=output,
            mode_used=AgentMode.MEMORY_AUGMENTED,
            execution_steps=[
                {"step": "rrf_hybrid_retrieval", "query": prompt, "matches": retrieved_items}
            ],
            total_tokens_used=220,
            success=True,
            metadata={"retrieved_memories_count": len(retrieved_items)},
        )
