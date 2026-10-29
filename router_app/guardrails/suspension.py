"""
人機協同任務掛起與恢復狀態機 (Task Suspension & Resume State Machine)
適用於非同步微服務環境：當遭遇高風險門控時，序列化當前狀態並掛起任務，
等待非同步外部審批信號 (如 Webhook / API / Slack) 喚醒後接續執行。
"""

import time
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SuspendedTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str
    target_mode: str
    risk_level: str
    created_at: float = Field(default_factory=time.time)
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)
    status: str = "SUSPENDED"  # SUSPENDED, APPROVED, REJECTED


class TaskSuspensionManager:
    """任務掛起管理中心"""

    def __init__(self):
        self._suspended_tasks: Dict[str, SuspendedTask] = {}

    def suspend(
        self,
        prompt: str,
        target_mode: str,
        risk_level: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SuspendedTask:
        """掛起當前任務並產生審批憑證"""
        task = SuspendedTask(
            prompt=prompt,
            target_mode=target_mode,
            risk_level=risk_level,
            context_snapshot=context or {},
        )
        self._suspended_tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[SuspendedTask]:
        return self._suspended_tasks.get(task_id)

    def review_task(self, task_id: str, approved: bool) -> Optional[SuspendedTask]:
        """外部審批簽核處理"""
        task = self._suspended_tasks.get(task_id)
        if not task:
            return None
        task.status = "APPROVED" if approved else "REJECTED"
        return task

    def pop_task(self, task_id: str) -> Optional[SuspendedTask]:
        return self._suspended_tasks.pop(task_id, None)
