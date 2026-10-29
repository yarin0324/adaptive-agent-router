"""
長流程任務檢查點與斷點續傳器 (Task Checkpointer & State Snapshots)
借鏡自 LangGraph Checkpointer
在 Planner-Executor 或 ReAct 多步驟任務中，每執行一個階段即寫入檢查點快照，
提供故障中斷時的斷點續傳 (Resume from Checkpoint) 能力，避免重複運算浪費。
"""

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CheckpointSnapshot(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    step_index: int
    step_name: str
    output_state: Any
    timestamp: float = Field(default_factory=time.time)


class TaskCheckpointer:
    """任務狀態持久化快照存儲器"""

    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or str(uuid.uuid4())
        self.checkpoints: List[CheckpointSnapshot] = []

    def save_step(self, step_index: int, step_name: str, output_state: Any) -> CheckpointSnapshot:
        """保存當前步驟快照"""
        cp = CheckpointSnapshot(
            step_index=step_index,
            step_name=step_name,
            output_state=output_state,
        )
        self.checkpoints.append(cp)
        return cp

    def get_latest_checkpoint(self) -> Optional[CheckpointSnapshot]:
        """取得最近一次成功的檢查點"""
        if self.checkpoints:
            return self.checkpoints[-1]
        return None

    def get_history(self) -> List[Dict[str, Any]]:
        return [cp.model_dump() for cp in self.checkpoints]
