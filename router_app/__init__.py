"""
自適應動態路由器 (Adaptive Agent Router) 企業核心架構
"""

from .dispatcher import AdaptiveAgentDispatcher
from .router import AdaptiveRouter
from .types import AgentMode, RiskLevel, ModelTier, RoutingDecision, ExecutionResult
from .tools.base_tool import BaseTool, SimpleFunctionTool
from .cache import RouteCache, SemanticPrototypeMatcher, RRFEngine
from .tracing import TraceContext, TraceSpan
from .compression import ContextCompressor
from .guardrails import (
    TaskCircuitBreaker,
    TaskSuspensionManager,
    SuspendedTask,
    InputSecurityRail,
    OutputPIISanitizerRail,
    TaskCheckpointer,
    CheckpointSnapshot,
    PythonASTSecurityGuard,
    SQLASTSecurityGuard,
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
    "RRFEngine",
    "TraceContext",
    "TraceSpan",
    "ContextCompressor",
    "TaskCircuitBreaker",
    "TaskSuspensionManager",
    "SuspendedTask",
    "InputSecurityRail",
    "OutputPIISanitizerRail",
    "TaskCheckpointer",
    "CheckpointSnapshot",
    "PythonASTSecurityGuard",
    "SQLASTSecurityGuard",
]
