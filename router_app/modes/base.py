"""
執行模式基礎介面 (Base Agent Mode Interface)
所有 10 大模式均繼承此類別，確保各專案可自由替換實作。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from ..types import AgentMode, ExecutionResult
from ..tools.base_tool import BaseTool


class BaseAgentMode(ABC):
    """Agent 模式抽象介面"""
    mode: AgentMode

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name

    @abstractmethod
    def run(
        self,
        prompt: str,
        tools: Optional[List[BaseTool]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        執行該模式的主邏輯
        """
        pass
