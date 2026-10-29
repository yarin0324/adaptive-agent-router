"""
自適應動態路由器 (Adaptive Agent Router) 企業核心架構
"""

from .dispatcher import AdaptiveAgentDispatcher
from .router import AdaptiveRouter
from .types import AgentMode, RiskLevel, ModelTier, RoutingDecision, ExecutionResult
from .tools.base_tool import BaseTool, SimpleFunctionTool
from .cache import RouteCache, SemanticPrototypeMatcher
from .tracing import TraceContext, TraceSpan
from .guardrails import (
    TaskCircuitBreaker,
    TaskSuspensionManager,
    SuspendedTask,
    InputSecurityRail,
    OutputPIISanitizerRail,
    TaskCheckpointer,
    CheckpointSnapshot,
)

__all__ = [
    "AdaptiveAgentDispatcher",
    "AdaptiveRouter",
    "AgentMode",
    "RiskLevel",
    "ModelTier",
    "RoutingDecision",
    "ExecutionResult",
    "BaseTool",
    "SimpleFunctionTool",
    "RouteCache",
    "SemanticPrototypeMatcher",
    "TraceContext",
    "TraceSpan",
    "TaskCircuitBreaker",
    "TaskSuspensionManager",
    "SuspendedTask",
    "InputSecurityRail",
    "OutputPIISanitizerRail",
    "TaskCheckpointer",
    "CheckpointSnapshot",
]
