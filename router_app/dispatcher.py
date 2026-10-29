"""
自適應調度總管 (Adaptive Agent Dispatcher)
統一入口，負責整合 Router、各模式執行器、工具庫與情境記憶。
"""

from typing import Any, Dict, List, Optional
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
    console = Console()
    
except ImportError:
    HAS_RICH = False
    console = None

from .types import AgentMode, ExecutionResult, RoutingDecision
from .router import AdaptiveRouter
from .memory.memory_manager import MemoryManager
from .tools.base_tool import BaseTool
from .tools.common_tools import (
    DatabaseQueryTool,
    DatabaseWriteTool,
    WebSearchTool,
    CalculatorTool,
)
from .modes import (
    SingleTurnMode,
    ReActMode,
    PlannerExecutorMode,
    ReflectionMode,
    VerifierGatedMode,
    MultiAgentMode,
    ToolAgentMode,
    EnsembleMode,
)
from .guardrails import TaskCircuitBreaker, CircuitBreakerException, AdaptiveEscalationEngine




class AdaptiveAgentDispatcher:
    """
    通用自適應 Agent 總管
    其他專案只要實例化此類別，即可獲得完整的動態路由能力！
    """

    def __init__(
        self,
        custom_tools: Optional[List[BaseTool]] = None,
        custom_modes: Optional[Dict[AgentMode, Any]] = None,
        enable_logging: bool = True,
    ):
        self.router = AdaptiveRouter()
        self.memory = MemoryManager()
        self.enable_logging = enable_logging

        # 註冊預設工具 + 外部傳入的自訂工具
        self.tools: List[BaseTool] = [
            DatabaseQueryTool(),
            DatabaseWriteTool(),
            WebSearchTool(),
            CalculatorTool(),
        ]
        if custom_tools:
            self.tools.extend(custom_tools)

        # 模式註冊表
        self.mode_registry = {
            AgentMode.SINGLE_TURN: SingleTurnMode(),
            AgentMode.REACT: ReActMode(),
            AgentMode.PLANNER_EXECUTOR: PlannerExecutorMode(),
            AgentMode.REFLECTION: ReflectionMode(),
            AgentMode.VERIFIER_GATED: VerifierGatedMode(),
            AgentMode.MULTI_AGENT: MultiAgentMode(),
            AgentMode.TOOL_USE: ToolAgentMode(),
            AgentMode.ENSEMBLE: EnsembleMode(),
        }
        if custom_modes:
            self.mode_registry.update(custom_modes)

    def register_tool(self, tool: BaseTool):
        """動態新增專案自訂工具"""
        self.tools.append(tool)

    def process(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        forced_mode: Optional[AgentMode] = None,
    ) -> ExecutionResult:
        """
        核心執行函式：接收問題 ➜ 路由器決策 ➜ 派發至最合適模式 ➜ 返回結果
        """
        # 1. 路由決策
        if forced_mode:
            decision = RoutingDecision(
                mode=forced_mode,
                reasoning="使用者強制指定執行模式",
                tags=["forced_override"]
            )
        else:
            decision = self.router.route(prompt, context)

        if self.enable_logging:
            self._log_decision(prompt, decision)

        # 2. 初始化任務熔斷守護者 (Circuit Breaker)
        breaker = TaskCircuitBreaker()

        try:
            # 獲取對應模式執行器
            executor = self.mode_registry.get(decision.mode)
            if not executor:
                # 降級保護
                executor = self.mode_registry[AgentMode.SINGLE_TURN]

            # 3. 執行任務
            result = executor.run(prompt=prompt, tools=self.tools, context=context)

            # 計量並記錄步驟
            breaker.record_step(tokens=result.total_tokens_used or 0)

            # 4. 記錄執行元數據與遙測指標 (Telemetry)
            result.metadata["routing_decision"] = decision.model_dump()
            result.metadata["telemetry"] = breaker.get_telemetry()

        except CircuitBreakerException as cbe:
            # 觸發熔斷時的優雅降級回傳
            result = ExecutionResult(
                output=f"⚠️ {str(cbe)}",
                mode_used=decision.mode,
                success=False,
                metadata={"telemetry": breaker.get_telemetry(), "circuit_breaker_tripped": True}
            )

        if self.enable_logging:
            self._log_result(result)

        return result

    def _log_decision(self, prompt: str, decision: RoutingDecision):
        """美化輸出路由決策日誌"""
        if HAS_RICH and console:
            table = Table(title="🧭 [bold cyan]Adaptive Agent Router 決策分流[/bold cyan]")
            table.add_column("項目", style="bold yellow")
            table.add_column("內容", style="white")

            table.add_row("使用者提問", prompt)
            table.add_row("指派模式", f"[green]{decision.mode.value}[/green]")
            table.add_row("判斷理由", decision.reasoning)
            table.add_row("風險評級", f"[red]{decision.risk_level.value}[/red]" if decision.risk_level.value in ["high", "critical"] else f"[blue]{decision.risk_level.value}[/blue]")
            table.add_row("需人工審批", str(decision.require_human_confirmation))
            table.add_row("標籤 Tags", ", ".join(decision.tags))

            console.print(table)
        else:
            print("\n┌─ [Adaptive Agent Router 決策分流] ──────────────────────")
            print(f"│ 使用者提問: {prompt}")
            print(f"│ 指派模式:   {decision.mode.value}")
            print(f"│ 判斷理由:   {decision.reasoning}")
            print(f"│ 風險評級:   {decision.risk_level.value}")
            print(f"│ 需人工審批: {decision.require_human_confirmation}")
            print(f"│ 標籤 Tags:  {', '.join(decision.tags)}")
            print("└────────────────────────────────────────────────────────\n")

    def _log_result(self, result: ExecutionResult):
        """美化輸出執行結果"""
        if HAS_RICH and console:
            status_color = "green" if result.success else "bold red"
            console.print(Panel(
                result.output,
                title=f"[{status_color}]執行回傳成果 ({result.mode_used.value})[/{status_color}]",
                border_style="cyan"
            ))
        else:
            status = "SUCCESS" if result.success else "ALERT / PAUSED"
            print(f"=== 執行成果 [{result.mode_used.value}] ({status}) ===")
            print(result.output)
            print("=" * 60 + "\n")
