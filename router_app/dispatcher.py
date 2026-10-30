"""
自適應調度總管 (Adaptive Agent Dispatcher)
統一入口，負責整合 Router、各模式執行器、工具庫與情境記憶。
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
    console = Console()
    
except ImportError:
    HAS_RICH = False
    console = None

from .types import AgentMode, ExecutionResult, RoutingDecision, StreamEventType, RouterStreamChunk
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
    MemoryAugmentedMode,
)
from .guardrails import (
    TaskCircuitBreaker,
    CircuitBreakerException,
    AdaptiveEscalationEngine,
    TaskSuspensionManager,
    SuspendedTask,
    InputSecurityRail,
    OutputPIISanitizerRail,
    TaskCheckpointer,
    TamperProofAuditLogger,
    IndirectInjectionSanitizer,
    ToolRBACGuard,
    PermissionDeniedException,
    SlidingWindowRateLimiter,
    SystemPromptLeakGuard,
)
from .cache import RouteCache, ELORatingTuner
from .tracing import TraceContext, metrics




class AdaptiveAgentDispatcher:
    """
    通用自適應 Agent 總管
    其他專案只要實例化此類別，即可獲得完整的動態路由能力！
    """

    def __init__(
        self,
        custom_tools: Optional[List[BaseTool]] = None,
        custom_modes: Optional[Dict[AgentMode, Any]] = None,
        elo_tuner: Optional[ELORatingTuner] = None,
        audit_log_path: Optional[str] = None,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        rag_adapter: Optional[Any] = None,
        enable_logging: bool = True,
    ):
        self.elo_tuner = elo_tuner or ELORatingTuner()
        self.router = AdaptiveRouter(elo_tuner=self.elo_tuner)
        self.memory = MemoryManager()
        self.cache = RouteCache()
        self.suspension_manager = TaskSuspensionManager()
        self.audit_logger = TamperProofAuditLogger(log_file_path=audit_log_path)
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()
        self.rag_adapter = rag_adapter
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
            AgentMode.MEMORY_AUGMENTED: MemoryAugmentedMode(memory_manager=self.memory),
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
        shadow_mode: Optional[AgentMode] = None,
        trace_id: Optional[str] = None,
        operator_id: str = "system",
        user_roles: Optional[List[str]] = None,
        client_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        核心執行函式：接收問題 ➜ 快取檢索 ➜ 路由器決策 ➜ 派發至最適模式 ➜ 返回結果
        支援影子流量乾跑 (Shadow Routing / Canary Evaluation)、Prometheus 遙測、RBAC 權限與不可篡改審計日誌。
        """
        import time
        start_ts = time.time()

        # 0. 前置頻率限制與 Token 炸彈防護 (OWASP LLM10)
        if client_id:
            allowed, rl_msg, retry_after = self.rate_limiter.check_limit(client_id, prompt_str=prompt)
            if not allowed:
                self.audit_logger.record_event(
                    event_type="RATE_LIMIT_BLOCKED",
                    prompt=prompt,
                    mode_used="none",
                    risk_level="high",
                    details={"reason": rl_msg, "retry_after": retry_after},
                    operator_id=operator_id,
                )
                return ExecutionResult(
                    output=f"⚠️ {rl_msg} (Retry-After: {retry_after}s)",
                    mode_used=AgentMode.SINGLE_TURN,
                    success=False,
                    metadata={"retry_after": retry_after, "blocked_by": "SlidingWindowRateLimiter"},
                )

        tracer = TraceContext(trace_id=trace_id)
        span_total = tracer.start_span("process_request", {"prompt": prompt})

        # 0. 前置安全軌道防禦 (借鏡 Guardrails AI: Input Rail)
        is_safe, security_msg = InputSecurityRail.validate_prompt(prompt)
        if not is_safe:
            span_total.finish("BLOCKED_BY_INPUT_RAIL")
            metrics.record_request(mode="input_rail", tier="none", status="blocked")
            self.audit_logger.record_event(
                event_type="SECURITY_BLOCKED",
                prompt=prompt,
                mode_used="input_rail",
                risk_level="critical",
                details={"reason": security_msg},
                operator_id=operator_id,
            )
            blocked_result = ExecutionResult(
                output=f"【安全防禦攔截 (Input Rail Blocked)】\n{security_msg}",
                mode_used=AgentMode.VERIFIER_GATED,
                success=False,
                metadata={"blocked_by": "InputSecurityRail"}
            )
            if self.enable_logging:
                self._log_result(blocked_result)
            return blocked_result

        # 1. 路由決策 (優先檢索 RouteCache)
        cached_decision = self.cache.get(prompt) if not forced_mode else None
        if cached_decision:
            decision = cached_decision
            is_cached = True
            metrics.record_cache_hit()
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
            metrics.record_suspended_task()
            suspended = self.suspension_manager.suspend(
                prompt=prompt,
                target_mode=decision.mode.value,
                risk_level=decision.risk_level.value,
                context=context
            )
            span_total.finish("SUSPENDED")
            metrics.record_request(mode=decision.mode.value, tier=decision.model_tier.value, status="suspended")
            self.audit_logger.record_event(
                event_type="TASK_SUSPENDED",
                prompt=prompt,
                mode_used=decision.mode.value,
                risk_level=decision.risk_level.value,
                details={"task_id": suspended.task_id, "reasoning": decision.reasoning},
                operator_id=operator_id,
            )
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

        # 工具層級 RBAC 角色權限過濾 (OWASP LLM03 & LLM06)
        authorized_tools = [
            t for t in self.tools if ToolRBACGuard.verify_tool_access(t, user_roles)[0]
        ]

        # 自適應 RAG 前置檢索與情境注入 (Adaptive RAG Ingestion)
        effective_prompt = prompt
        effective_context = dict(context or {})
        rag_meta = {}
        if self.rag_adapter:
            rag_res = self.rag_adapter.dispatch(prompt, context=effective_context)
            effective_context["rag_result"] = rag_res.model_dump()
            effective_context["retrieved_chunks"] = [c.model_dump() for c in rag_res.chunks]
            effective_prompt = self.rag_adapter.format_prompt_with_context(prompt, rag_res)
            rag_meta = {
                "strategy": rag_res.mode_used.value,
                "chunks_count": len(rag_res.chunks),
                "confidence": rag_res.confidence_score,
                "latency_ms": rag_res.latency_ms,
                "fallback_triggered": rag_res.fallback_triggered,
            }

        try:
            # 獲取對應模式執行器
            executor = self.mode_registry.get(decision.mode)
            if not executor:
                executor = self.mode_registry[AgentMode.SINGLE_TURN]

            # 執行任務
            result = executor.run(prompt=effective_prompt, tools=authorized_tools, context=effective_context)
            breaker.record_step(tokens=result.total_tokens_used or 0)
            
            # 後置個資脫敏過濾 (借鏡 Guardrails AI: Output PII Sanitizer)
            result.output = OutputPIISanitizerRail.sanitize(result.output)

            # 系統提示詞洩漏阻斷審查 (OWASP LLM07)
            result.output, has_leak, leak_details = SystemPromptLeakGuard.inspect_and_sanitize(result.output)
            if has_leak:
                result.metadata["system_prompt_leak_neutralized"] = leak_details

            if rag_meta:
                result.metadata["rag"] = rag_meta

            span_exec.finish("OK")

            # 記錄執行元數據與遙測指標 (Telemetry & Tracing)
            result.metadata["routing_decision"] = decision.model_dump()
            result.metadata["telemetry"] = breaker.get_telemetry()
            result.metadata["trace"] = tracer.export()

            # 影子流量 A/B 乾跑評估 (Shadow Canary Evaluation)
            if shadow_mode and shadow_mode in self.mode_registry:
                shadow_start = time.time()
                shadow_executor = self.mode_registry[shadow_mode]
                shadow_res = shadow_executor.run(prompt=prompt, tools=authorized_tools, context=context)
                shadow_dur = time.time() - shadow_start
                result.metadata["shadow_evaluation"] = {
                    "primary_mode": decision.mode.value,
                    "shadow_mode": shadow_mode.value,
                    "primary_tokens": result.total_tokens_used or 0,
                    "shadow_tokens": shadow_res.total_tokens_used or 0,
                    "token_delta": (shadow_res.total_tokens_used or 0) - (result.total_tokens_used or 0),
                    "shadow_latency_ms": round(shadow_dur * 1000, 2),
                    "shadow_output_preview": shadow_res.output[:150] + "...",
                }
                metrics.record_request(mode=shadow_mode.value, tier="shadow", status="shadow_success")

        except CircuitBreakerException as cbe:
            span_exec.finish("CIRCUIT_BREAKER_TRIPPED")
            metrics.record_circuit_breaker_trip()
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

        duration = time.time() - start_ts
        metrics.record_request(
            mode=decision.mode.value,
            tier=decision.model_tier.value,
            status="success" if result.success else "failed",
            duration_seconds=duration,
        )
        metrics.record_tokens(consumed=result.total_tokens_used or 0)
        span_total.finish("OK" if result.success else "FAILED")

        # 記錄不可篡改審計事件
        self.audit_logger.record_event(
            event_type="TASK_COMPLETED" if result.success else "TASK_FAILED",
            prompt=prompt,
            mode_used=result.mode_used.value,
            risk_level=decision.risk_level.value,
            details={"tokens": result.total_tokens_used or 0, "success": result.success},
            operator_id=operator_id,
        )

        if self.enable_logging:
            self._log_result(result)

        return result

    def resume_task(
        self,
        task_id: str,
        approved: bool = True,
        operator_id: str = "security_officer",
        reason: str = "",
    ) -> ExecutionResult:
        """
        外部非同步審批通過後，喚醒掛起的任務並放行執行
        記錄不可篡改審批簽章與操作者身分留痕
        """
        task = self.suspension_manager.pop_task(task_id)
        if not task:
            return ExecutionResult(
                output=f"審批失敗：找不到對應的 Task ID: {task_id}",
                mode_used=AgentMode.VERIFIER_GATED,
                success=False
            )

        # 記錄審批不可篡改日誌
        self.audit_logger.record_event(
            event_type="TASK_APPROVED" if approved else "TASK_REJECTED",
            prompt=task.prompt,
            mode_used=task.target_mode,
            risk_level=task.risk_level,
            details={"task_id": task_id, "reason": reason, "approved": approved},
            operator_id=operator_id,
        )

        if not approved:
            return ExecutionResult(
                output=f"任務 {task_id} 已由審批人員 ({operator_id}) 正式拒絕，操作已取消。理由: {reason}",
                mode_used=AgentMode.VERIFIER_GATED,
                success=False,
                metadata={"status": "REJECTED", "operator_id": operator_id}
            )

        # 審批通過，直接執行目標模式
        try:
            mode_enum = AgentMode(task.target_mode)
        except Exception:
            mode_enum = AgentMode.SINGLE_TURN

        executor = self.mode_registry.get(mode_enum, self.mode_registry[AgentMode.SINGLE_TURN])
        resume_context = dict(task.context_snapshot)
        resume_context["approved_by_human"] = True
        
        # 審批後放行之工具過濾 (允許 admin / security_officer 授權)
        approved_roles = ["admin", "security_officer"]
        authorized_tools = [
            t for t in self.tools if ToolRBACGuard.verify_tool_access(t, approved_roles)[0]
        ]
        try:
            result = executor.run(prompt=task.prompt, tools=authorized_tools, context=resume_context)
            result.metadata["resume_task_id"] = task_id
            result.metadata["approved_by_human"] = True
            
            # 個資脫敏與系統提示詞洩漏審查
            result.output = OutputPIISanitizerRail.sanitize(result.output)
            result.output, _, _ = SystemPromptLeakGuard.inspect_and_sanitize(result.output)

            self.audit_logger.record_event(
                event_type="TASK_COMPLETED" if result.success else "TASK_FAILED",
                prompt=task.prompt,
                mode_used=result.mode_used.value,
                risk_level=task.risk_level,
                details={"task_id": task_id, "tokens": result.total_tokens_used or 0, "resumed": True},
                operator_id=operator_id,
            )

            return result
        except CircuitBreakerException as cbe:
            self.audit_logger.record_event(
                event_type="TASK_FAILED",
                prompt=task.prompt,
                mode_used=mode_enum.value,
                risk_level=task.risk_level,
                details={"task_id": task_id, "error": str(cbe), "circuit_breaker": True},
                operator_id=operator_id,
            )
            return ExecutionResult(
                output=f"⚠️ 審批放行後執行觸發熔斷防禦: {str(cbe)}",
                mode_used=mode_enum,
                success=False,
                metadata={"circuit_breaker_tripped": True, "resume_task_id": task_id}
            )
        except Exception as e:
            self.audit_logger.record_event(
                event_type="TASK_FAILED",
                prompt=task.prompt,
                mode_used=mode_enum.value,
                risk_level=task.risk_level,
                details={"task_id": task_id, "error": str(e)},
                operator_id=operator_id,
            )
            return ExecutionResult(
                output=f"審批放行後執行異常: {str(e)}",
                mode_used=mode_enum,
                success=False,
                metadata={"error": str(e), "resume_task_id": task_id}
            )

    def record_feedback(
        self,
        mode: AgentMode,
        success: bool,
        latency_ms: float = 0.0,
        user_rating: Optional[float] = None,
    ) -> float:
        """
        向 ELO 調校器提交執行成果反饋，即時更新該 Agent 模式之動態等級分
        """
        new_rating = self.elo_tuner.record_feedback(
            mode=mode,
            success=success,
            latency_ms=latency_ms,
            user_rating=user_rating,
        )
        if self.enable_logging:
            print(f"📊 [ELO Tuner] 模式 {mode.value} 反饋已記錄: 評分調校至 {new_rating:.1f}")
        return new_rating

    async def aprocess(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        forced_mode: Optional[AgentMode] = None,
        trace_id: Optional[str] = None,
        operator_id: str = "system",
        user_roles: Optional[List[str]] = None,
        client_id: Optional[str] = None,
    ) -> ExecutionResult:
        """非同步無阻塞呼叫 (Async Non-blocking Dispatch)"""
        return await asyncio.to_thread(
            self.process,
            prompt=prompt,
            context=context,
            forced_mode=forced_mode,
            trace_id=trace_id,
            operator_id=operator_id,
            user_roles=user_roles,
            client_id=client_id,
        )

    async def aprocess_stream(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        forced_mode: Optional[AgentMode] = None,
        trace_id: Optional[str] = None,
        operator_id: str = "system",
        user_roles: Optional[List[str]] = None,
        client_id: Optional[str] = None,
    ) -> AsyncGenerator[RouterStreamChunk, None]:
        """
        非同步串流輸出引擎 (Async Streaming SSE Generator)
        逐段產出路由決策、步驟進度、思考過程與結果 Token 區塊。
        """
        # 0. 前置頻率限制與 Token 炸彈防護 (OWASP LLM10)
        if client_id:
            allowed, rl_msg, retry_after = self.rate_limiter.check_limit(client_id, prompt_str=prompt)
            if not allowed:
                self.audit_logger.record_event(
                    event_type="RATE_LIMIT_BLOCKED",
                    prompt=prompt,
                    mode_used="none",
                    risk_level="high",
                    details={"reason": rl_msg, "retry_after": retry_after},
                    operator_id=operator_id,
                )
                yield RouterStreamChunk(
                    event=StreamEventType.TASK_FAILED,
                    message=f"⚠️ {rl_msg} (Retry-After: {retry_after}s)",
                    data={"retry_after": retry_after, "blocked_by": "SlidingWindowRateLimiter"},
                )
                return

        # 1. 廣播路由啟動事件
        yield RouterStreamChunk(
            event=StreamEventType.ROUTE_START,
            message="正在進行安全快篩與自適應路由分析...",
            data={"prompt": prompt},
        )

        # 2. 前置安全軌道防禦
        is_safe, security_msg = InputSecurityRail.validate_prompt(prompt)
        if not is_safe:
            self.audit_logger.record_event(
                event_type="SECURITY_BLOCKED",
                prompt=prompt,
                mode_used="input_rail",
                risk_level="critical",
                details={"reason": security_msg},
                operator_id=operator_id,
            )
            yield RouterStreamChunk(
                event=StreamEventType.TASK_FAILED,
                message=f"Prompt 被安全衛兵阻斷: {security_msg}",
                data={"blocked_by": "InputSecurityRail"},
            )
            return

        # 3. 路由決策
        cached_decision = self.cache.get(prompt) if not forced_mode else None
        if cached_decision:
            decision = cached_decision
            is_cached = True
        elif forced_mode:
            decision = RoutingDecision(
                mode=forced_mode,
                reasoning="使用者強制指定執行模式",
                tags=["forced_override"],
            )
            is_cached = False
        else:
            decision = self.router.route(prompt, context)
            self.cache.set(prompt, decision)
            is_cached = False

        yield RouterStreamChunk(
            event=StreamEventType.ROUTE_DECIDED,
            message=f"已成功分流至模式: {decision.mode.value} (算力階層: {decision.model_tier.value})",
            data={
                "decision": decision.model_dump(),
                "is_cached": is_cached,
            },
        )

        # 4. 檢驗高風險掛起
        if decision.require_human_confirmation:
            suspended = self.suspension_manager.suspend(
                prompt=prompt,
                target_mode=decision.mode.value,
                risk_level=decision.risk_level.value,
                context=context,
            )
            self.audit_logger.record_event(
                event_type="TASK_SUSPENDED",
                prompt=prompt,
                mode_used=decision.mode.value,
                risk_level=decision.risk_level.value,
                details={"task_id": suspended.task_id, "reasoning": decision.reasoning},
                operator_id=operator_id,
            )
            yield RouterStreamChunk(
                event=StreamEventType.TASK_SUSPENDED,
                task_id=suspended.task_id,
                message=f"偵測到不可逆高風險指令，任務已掛起等待審批 (Task ID: {suspended.task_id})",
                data={"risk_level": decision.risk_level.value},
            )
            return

        # 5. 工具層級 RBAC 角色權限過濾 (OWASP LLM03 & LLM06)
        authorized_tools = [
            t for t in self.tools if ToolRBACGuard.verify_tool_access(t, user_roles)[0]
        ]

        # 6. 執行模式
        executor = self.mode_registry.get(decision.mode, self.mode_registry[AgentMode.SINGLE_TURN])
        
        # 自適應 RAG 前置檢索與情境注入
        effective_prompt = prompt
        effective_context = dict(context or {})
        if self.rag_adapter:
            rag_res = self.rag_adapter.dispatch(prompt, context=effective_context)
            effective_context["rag_result"] = rag_res.model_dump()
            effective_context["retrieved_chunks"] = [c.model_dump() for c in rag_res.chunks]
            effective_prompt = self.rag_adapter.format_prompt_with_context(prompt, rag_res)
            yield RouterStreamChunk(
                event=StreamEventType.STEP_PROGRESS,
                message=f"RAG 自適應檢索完成 (策略: {rag_res.mode_used.value}, 切片數: {len(rag_res.chunks)})",
                data={"rag_mode": rag_res.mode_used.value, "chunks_count": len(rag_res.chunks), "latency_ms": rag_res.latency_ms},
            )

        # 發送執行開始信號
        yield RouterStreamChunk(
            event=StreamEventType.STEP_PROGRESS,
            message=f"正在啟動 {decision.mode.value} 執行引擎...",
            data={"estimated_steps": decision.estimated_steps},
        )

        # 非同步執行運算 (避免卡死 Event Loop)
        try:
            result = await asyncio.to_thread(executor.run, prompt=effective_prompt, tools=authorized_tools, context=effective_context)
        except CircuitBreakerException as cbe:
            yield RouterStreamChunk(
                event=StreamEventType.TASK_FAILED,
                message=f"⚠️ 觸發任務熔斷防禦: {str(cbe)}",
                data={"circuit_breaker_tripped": True},
            )
            return
        except Exception as e:
            yield RouterStreamChunk(
                event=StreamEventType.TASK_FAILED,
                message=f"執行階段異常: {str(e)}",
                data={"error": str(e)},
            )
            return

        # 廣播中間步驟進度
        for idx, step in enumerate(result.execution_steps, 1):
            yield RouterStreamChunk(
                event=StreamEventType.STEP_PROGRESS,
                message=f"步驟 {idx} 執行完成",
                data={"step_detail": step},
            )

        # 個資脫敏與系統提示詞洩漏審查 (OWASP LLM02 & LLM07)
        sanitized_output = OutputPIISanitizerRail.sanitize(result.output)
        sanitized_output, has_leak, leak_details = SystemPromptLeakGuard.inspect_and_sanitize(sanitized_output)

        # 記錄審計日誌
        self.audit_logger.record_event(
            event_type="TASK_COMPLETED" if result.success else "TASK_FAILED",
            prompt=prompt,
            mode_used=result.mode_used.value,
            risk_level=decision.risk_level.value,
            details={"tokens": result.total_tokens_used or 0, "success": result.success},
            operator_id=operator_id,
        )

        # 模擬串流 Token 增量推送 (依段落或 Token 分塊)
        paragraphs = sanitized_output.split("\n")
        for p in paragraphs:
            yield RouterStreamChunk(
                event=StreamEventType.CONTENT_CHUNK,
                delta=p + "\n",
            )
            await asyncio.sleep(0.01)

        # 任務完成
        yield RouterStreamChunk(
            event=StreamEventType.TASK_COMPLETED,
            message="任務順利交付完畢",
            data={
                "mode_used": result.mode_used.value,
                "total_tokens_used": result.total_tokens_used,
                "success": result.success,
            },
        )

    def _log_decision(self, prompt: str, decision: RoutingDecision, is_cached: bool = False):
        """美化輸出路由決策日誌"""
        cache_indicator = " [HIT CACHE]" if is_cached else ""
        tier_str = decision.model_tier.value.upper()
        if HAS_RICH and console:
            table = Table(title=f"🧭 [bold cyan]Adaptive Agent Router 決策分流{cache_indicator}[/bold cyan]")
            table.add_column("項目", style="bold yellow")
            table.add_column("內容", style="white")

            table.add_row("使用者提問", prompt)
            table.add_row("指派模式", f"[green]{decision.mode.value}[/green]")
            table.add_row("算力階層", f"[magenta]{tier_str}[/magenta]")
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
            print(f"│ 算力階層:   {tier_str}")
            print(f"│ 快取狀態:   {'HIT (0ms)' if is_cached else 'MISS'}")
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
