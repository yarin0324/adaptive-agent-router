"""
自適應動態路由器 (Adaptive Agent Router) 企業核心架構
"""

from .dispatcher import AdaptiveAgentDispatcher
from .router import AdaptiveRouter
from .types import (
    AgentMode,
    RiskLevel,
    ModelTier,
    RoutingDecision,
    ExecutionResult,
    StreamEventType,
    RouterStreamChunk,
)
from .tools import (
    BaseTool,
    SimpleFunctionTool,
    ToolLoader,
    DynamicOpenAPITool,
    DynamicMCPTool,
)
from .cache import (
    RouteCache,
    SemanticPrototypeMatcher,
    RRFEngine,
    ELORatingTuner,
    ModeFeedbackStats,
)
from .tracing import TraceContext, TraceSpan
from .compression import ContextCompressor
from .guardrails import (
    TaskCircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerException,
    AdaptiveEscalationEngine,
    TaskSuspensionManager,
    SuspendedTask,
    InputSecurityRail,
    OutputPIISanitizerRail,
    TaskCheckpointer,
    CheckpointSnapshot,
    PythonASTSecurityGuard,
    SQLASTSecurityGuard,
    RestrictedSubprocessSandbox,
    SandboxExecutionResult,
)

__all__ = [
    "AdaptiveAgentDispatcher",
    "AdaptiveRouter",
    "AgentMode",
    "RiskLevel",
    "ModelTier",
    "RoutingDecision",
    "ExecutionResult",
    "StreamEventType",
    "RouterStreamChunk",
    "BaseTool",
    "SimpleFunctionTool",
    "ToolLoader",
    "DynamicOpenAPITool",
    "DynamicMCPTool",
    "RouteCache",
    "SemanticPrototypeMatcher",
    "RRFEngine",
    "ELORatingTuner",
    "ModeFeedbackStats",
    "TraceContext",
    "TraceSpan",
    "ContextCompressor",
    "TaskCircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerException",
    "AdaptiveEscalationEngine",
    "TaskSuspensionManager",
    "SuspendedTask",
    "InputSecurityRail",
    "OutputPIISanitizerRail",
    "TaskCheckpointer",
    "CheckpointSnapshot",
    "PythonASTSecurityGuard",
    "SQLASTSecurityGuard",
    "RestrictedSubprocessSandbox",
    "SandboxExecutionResult",
]
