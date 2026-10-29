"""
工具基礎類別 (Base Tool Specification)
定義所有可插拔工具的標準介面。
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel


class BaseTool(ABC):
    """自訂工具基礎介面"""
    name: str
    description: str
    risk_level: str = "low"  # low, medium, high, critical

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """執行工具邏輯"""
        pass

    def to_schema(self) -> Dict[str, Any]:
        """產出 LLM 可識別的 Function / Tool 規格"""
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
        }


class SimpleFunctionTool(BaseTool):
    """快速將既有 Python 函數封裝成 Tool 的包裝器"""
    def __init__(self, name: str, description: str, func: Callable, risk_level: str = "low"):
        self.name = name
        self.description = description
        self.func = func
        self.risk_level = risk_level

    def execute(self, **kwargs) -> Any:
        return self.func(**kwargs)
