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
from .guardrails import (
    TaskCircuitBreaker,
    CircuitBreakerException,
    AdaptiveEscalationEngine,
    TaskSuspensionManager,
    SuspendedTask,
)
from .cache import RouteCache
from .tracing import TraceContext




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
        self.cache = RouteCache()
        self.suspension_manager = TaskSuspensionManager()
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
        trace_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        核心執行函式：接收問題 ➜ 快取檢索 ➜ 路由器決策 ➜ 派發至最適模式 ➜ 返回結果
        """
        tracer = TraceContext(trace_id=trace_id)
        span_total = tracer.start_span("process_request", {"prompt": prompt})

        # 1. 路由決策 (優先檢索 RouteCache)
        cached_decision = self.cache.get(prompt) if not forced_mode else None
        if cached_decision:
            decision = cached_decision
            is_cached = True
        elif forced_mode:
            decision = RoutingDecision(
                mode=forced_mode,
                reasoning="使用者強制指定執行模式",
                tags=["forced_override"]
            )
            is_cached = False
        else:
            span_route = tracer.start_span("route_decision")
            decision = self.router.route(prompt, context)
            span_route.finish()
            self.cache.set(prompt, decision)
            is_cached = False

        if self.enable_logging:
            self._log_decision(prompt, decision, is_cached=is_cached)

        # 2. 檢驗高風險掛起 (Human-in-the-Loop Suspend Pattern)
        if decision.require_human_confirmation:
            suspended = self.suspension_manager.suspend(
                prompt=prompt,
                target_mode=decision.mode.value,
                risk_level=decision.risk_level.value,
                context=context
            )
            span_total.finish("SUSPENDED")
            return ExecutionResult(
                output=(
                    f"【安全門控攔截 (Task Suspended)】\n"
                    f"偵測到高風險操作，任務已掛起等待審批。\n"
                    f"審批憑證 Task ID: {suspended.task_id}\n"
                    f"呼叫 dispatcher.resume_task('{suspended.task_id}', approved=True) 即可接續執行。"
                ),
                mode_used=decision.mode,
                success=False,
                metadata={
                    "task_id": suspended.task_id,
                    "status": "SUSPENDED",
                    "routing_decision": decision.model_dump(),
                    "trace": tracer.export()
                }
            )

        # 3. 初始化任務熔斷守護者 (Circuit Breaker)
        breaker = TaskCircuitBreaker()
        span_exec = tracer.start_span("execute_mode", {"mode": decision.mode.value})

        try:
            # 獲取對應模式執行器
            executor = self.mode_registry.get(decision.mode)
            if not executor:
                executor = self.mode_registry[AgentMode.SINGLE_TURN]

            # 執行任務
            result = executor.run(prompt=prompt, tools=self.tools, context=context)
            breaker.record_step(tokens=result.total_tokens_used or 0)
            span_exec.finish("OK")

            # 記錄執行元數據與遙測指標 (Telemetry & Tracing)
            result.metadata["routing_decision"] = decision.model_dump()
            result.metadata["telemetry"] = breaker.get_telemetry()
            result.metadata["trace"] = tracer.export()

        except CircuitBreakerException as cbe:
            span_exec.finish("CIRCUIT_BREAKER_TRIPPED")
            result = ExecutionResult(
                output=f"⚠️ {str(cbe)}",
                mode_used=decision.mode,
                success=False,
                metadata={
                    "telemetry": breaker.get_telemetry(),
                    "circuit_breaker_tripped": True,
                    "trace": tracer.export()
                }
            )

        span_total.finish("OK" if result.success else "FAILED")

        if self.enable_logging:
            self._log_result(result)

        return result

    def resume_task(self, task_id: str, approved: bool = True) -> ExecutionResult:
        """
        外部非同步審批通過後，喚醒掛起的任務並放行執行
        """
        task = self.suspension_manager.pop_task(task_id)
        if not task:
            return ExecutionResult(
                output=f"審批失敗：找不到對應的 Task ID: {task_id}",
                mode_used=AgentMode.VERIFIER_GATED,
                success=False
            )

        if not approved:
            return ExecutionResult(
                output=f"任務 {task_id} 已由審批人員正式拒絕，操作已取消。",
                mode_used=AgentMode.VERIFIER_GATED,
                success=False,
                metadata={"status": "REJECTED"}
            )

        # 審批通過，直接執行目標模式
        mode_enum = AgentMode(task.target_mode)
        executor = self.mode_registry.get(mode_enum, self.mode_registry[AgentMode.SINGLE_TURN])
        resume_context = dict(task.context_snapshot)
        resume_context["approved_by_human"] = True
        result = executor.run(prompt=task.prompt, tools=self.tools, context=resume_context)
        result.metadata["resume_task_id"] = task_id
        result.metadata["approved_by_human"] = True
        return result

    def _log_decision(self, prompt: str, decision: RoutingDecision, is_cached: bool = False):
        """美化輸出路由決策日誌"""
        cache_indicator = " [HIT CACHE]" if is_cached else ""
        if HAS_RICH and console:
            table = Table(title=f"🧭 [bold cyan]Adaptive Agent Router 決策分流{cache_indicator}[/bold cyan]")
            table.add_column("項目", style="bold yellow")
            table.add_column("內容", style="white")

            table.add_row("使用者提問", prompt)
            table.add_row("指派模式", f"[green]{decision.mode.value}[/green]")
            table.add_row("判斷理由", decision.reasoning)
            table.add_row("快取狀態", "[magenta]HIT (0ms)[/magenta]" if is_cached else "[dim]MISS[/dim]")
            table.add_row("風險評級", f"[red]{decision.risk_level.value}[/red]" if decision.risk_level.value in ["high", "critical"] else f"[blue]{decision.risk_level.value}[/blue]")
            table.add_row("需人工審批", str(decision.require_human_confirmation))
            table.add_row("標籤 Tags", ", ".join(decision.tags))

            console.print(table)
        else:
            print(f"\n┌─ [Adaptive Agent Router 決策分流{cache_indicator}] ──────────────────────")
            print(f"│ 使用者提問: {prompt}")
            print(f"│ 指派模式:   {decision.mode.value}")
            print(f"│ 快取狀態:   {'HIT (0ms)' if is_cached else 'MISS'}")
            print(f"│ 判斷理由:   {decision.reasoning}")
            print(f"│ 風險評級:   {decision.risk_level.value}")
            print(f"│ 需人工審批: {decision.require_human_confirmation}")
            print(f"│ 標籤 Tags:  {', '.join(decision.tags)}")
            print("└────────────────────────────────────────────────────────\n")
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
