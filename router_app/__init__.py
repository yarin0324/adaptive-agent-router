"""
自適應動態路由器 (Adaptive Agent Router) 企業核心架構
"""

from .dispatcher import AdaptiveAgentDispatcher
from .router import AdaptiveRouter
from .types import AgentMode, RiskLevel, RoutingDecision, ExecutionResult
from .tools.base_tool import BaseTool, SimpleFunctionTool
from .cache import RouteCache
from .tracing import TraceContext, TraceSpan
from .guardrails import TaskCircuitBreaker, TaskSuspensionManager, SuspendedTask

__all__ = [
    "AdaptiveAgentDispatcher",
    "AdaptiveRouter",
    "AgentMode",
    "RiskLevel",
    "RoutingDecision",
    "ExecutionResult",
    "BaseTool",
    "SimpleFunctionTool",
    "RouteCache",
    "TraceContext",
    "TraceSpan",
    "TaskCircuitBreaker",
    "TaskSuspensionManager",
    "SuspendedTask",
]
