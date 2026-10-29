"""
雲原生狀態儲存適配器 (Pluggable State Storage: Memory & SQLite Persistence)
提供無阻塞人機審批狀態機 (TaskSuspensionManager) 與任務檢查點 (TaskCheckpointer) 之跨節點持久化支援。
預設提供零依賴 Memory 記憶體儲存與 SQLite 本地 ACID 關箱重啟復原儲存。
"""

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from .suspension import SuspendedTask


class BaseStateStorage(ABC):
    """持久化狀態儲存抽象介面"""

    @abstractmethod
    def save_task(self, task: SuspendedTask) -> None:
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[SuspendedTask]:
        pass

    @abstractmethod
    def pop_task(self, task_id: str) -> Optional[SuspendedTask]:
        pass

    @abstractmethod
    def update_task_status(self, task_id: str, status: str, reviewed_at: Optional[float] = None) -> Optional[SuspendedTask]:
        pass

    @abstractmethod
    def list_tasks(self, status: Optional[str] = None) -> List[SuspendedTask]:
        pass


class MemoryStateStorage(BaseStateStorage):
    """記憶體暫存 (單行程快速執行)"""

    def __init__(self):
        self._tasks: Dict[str, SuspendedTask] = {}

    def save_task(self, task: SuspendedTask) -> None:
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[SuspendedTask]:
        return self._tasks.get(task_id)

    def pop_task(self, task_id: str) -> Optional[SuspendedTask]:
        return self._tasks.pop(task_id, None)

    def update_task_status(self, task_id: str, status: str, reviewed_at: Optional[float] = None) -> Optional[SuspendedTask]:
        task = self._tasks.get(task_id)
        if task:
            task.status = status
            task.reviewed_at = reviewed_at or time.time()
        return task

    def list_tasks(self, status: Optional[str] = None) -> List[SuspendedTask]:
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())


class SQLiteStateStorage(BaseStateStorage):
    """
    SQLite ACID 持久化儲存 (純 Python 標準庫，零依賴)
    伺服器重啟或容器重新部署後，掛起的審批任務依然完整保留！
    """

    def __init__(self, db_path: str = "suspended_tasks.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS suspended_tasks (
                    task_id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    target_mode TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    reviewed_at REAL,
                    context_snapshot TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_task(self, task: SuspendedTask) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO suspended_tasks 
                (task_id, prompt, target_mode, risk_level, status, created_at, reviewed_at, context_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.prompt,
                    task.target_mode,
                    task.risk_level,
                    task.status,
                    task.created_at,
                    task.reviewed_at,
                    json.dumps(task.context_snapshot, ensure_ascii=False, default=str),
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[SuspendedTask]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM suspended_tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            return SuspendedTask(
                task_id=row["task_id"],
                prompt=row["prompt"],
                target_mode=row["target_mode"],
                risk_level=row["risk_level"],
                status=row["status"],
                created_at=row["created_at"],
                reviewed_at=row["reviewed_at"],
                context_snapshot=json.loads(row["context_snapshot"]),
            )

    def pop_task(self, task_id: str) -> Optional[SuspendedTask]:
        task = self.get_task(task_id)
        if task:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM suspended_tasks WHERE task_id = ?", (task_id,))
                conn.commit()
        return task

    def update_task_status(self, task_id: str, status: str, reviewed_at: Optional[float] = None) -> Optional[SuspendedTask]:
        rev_time = reviewed_at or time.time()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE suspended_tasks SET status = ?, reviewed_at = ? WHERE task_id = ?",
                (status, rev_time, task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[SuspendedTask]:
        with self._get_connection() as conn:
            if status:
                cur = conn.execute("SELECT * FROM suspended_tasks WHERE status = ?", (status,))
            else:
                cur = conn.execute("SELECT * FROM suspended_tasks")
            rows = cur.fetchall()
            return [
                SuspendedTask(
                    task_id=r["task_id"],
                    prompt=r["prompt"],
                    target_mode=r["target_mode"],
                    risk_level=r["risk_level"],
                    status=r["status"],
                    created_at=r["created_at"],
                    reviewed_at=r["reviewed_at"],
                    context_snapshot=json.loads(r["context_snapshot"]),
                )
                for r in rows
            ]
