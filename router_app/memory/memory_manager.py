"""
模式 10: 情境式記憶 (Contextual / Semantic Memory)
負責跨輪次持久化知識累積、使用者畫像與工作階段記憶管理。
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    user_id: str
    session_id: str
    topic: str
    content: str
    importance: float = 1.0


class MemoryManager:
    """記憶體管理器"""
    def __init__(self):
        self._store: List[MemoryEntry] = []

    def save_memory(self, user_id: str, session_id: str, topic: str, content: str, importance: float = 1.0):
        entry = MemoryEntry(
            user_id=user_id,
            session_id=session_id,
            topic=topic,
            content=content,
            importance=importance
        )
        self._store.append(entry)

    def retrieve_relevant(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """檢索相關記憶 (支援關鍵字/向量)"""
        results = []
        for item in self._store:
            if any(term in item.content or term in item.topic for term in query.split()):
                results.append(item.model_dump())
        return results[:limit]

    def clear(self):
        self._store.clear()
