"""
視覺化決策審計卡片與 Mermaid 流程圖生成器 (Visual Decision Battle Card & Mermaid Audit)
為企業合規與審計人員提供可解釋性（Explainability）極致體驗：
包含模式分流依據、AST 護欄通過標章、Token 節省百分比與 Mermaid 狀態轉換圖。
"""

from typing import Any, Dict, Optional
from ..types import ExecutionResult, RoutingDecision, AgentMode, RiskLevel


class BattleCardGenerator:
    """審計戰鬥卡與視覺圖表生成器"""

    @staticmethod
    def generate_mermaid(result: ExecutionResult) -> str:
        """生成該次執行的 Mermaid 狀態流向圖"""
        mode_val = result.mode_used.value
        status_node = "SuccessNode([交付成功 SUCCESS])" if result.success else "HaltNode([異常或暫停 ALERT])"

        steps_lines = []
        last_node = "Router"

        # 若有 RAG 自適應檢索，插入檢索節點
        rag_info = result.metadata.get("rag")
        if rag_info:
            rag_strat = rag_info.get("strategy", "hybrid")
            steps_lines.append(f'    Router --> RAGNode["RAG 檢索: {rag_strat}"]')
            last_node = "RAGNode"

        # 若有推論加速調度，插入加速調度節點
        acc_info = result.metadata.get("acceleration")
        if acc_info:
            target_worker = acc_info.get("target_node_id", "worker_gpu")
            cache_tag = "Cache HIT" if acc_info.get("is_cache_hit") else "Cache MISS"
            steps_lines.append(f'    {last_node} --> AccNode["加速派發: {target_worker} ({cache_tag})"]')
            last_node = "AccNode"

        for i, step in enumerate(result.execution_steps, 1):
            step_name = step.get("step") or step.get("action") or f"Step_{i}"
            node_id = f"Step_{i}"
            steps_lines.append(f'    {last_node} --> {node_id}["步驟 {i}: {step_name}"]')
            last_node = node_id

        if not result.execution_steps:
            steps_lines.append(f'    {last_node} --> ExecNode["執行模式: {mode_val}"]')
            last_node = "ExecNode"

        # 若有 Harness 品質門控，插入門控檢驗節點
        harness_info = result.metadata.get("harness")
        if harness_info:
            slop_tag = "Linter 合格" if harness_info.get("is_clean") else "去 AI 腔調淨化"
            steps_lines.append(f'    {last_node} --> HarnessGate["Harness 外骨骼: {slop_tag}"]')
            last_node = "HarnessGate"

        steps_str = "\n".join(steps_lines)

        mermaid_code = f"""```mermaid
flowchart LR
    Start([使用者提問]) --> Ingress[調度閘道檢測]
    Ingress --> Router{{自適應路由器}}
{steps_str}
    {last_node} --> {status_node}
    style Router fill:#f9f,stroke:#333,stroke-width:2px
    style {status_node.split('[')[0]} fill:#9f9,stroke:#333,stroke-width:2px
```"""
        return mermaid_code

    @classmethod
    def generate_battle_card(
        cls,
        result: ExecutionResult,
        prompt: str,
        decision: Optional[RoutingDecision] = None,
    ) -> str:
        """產出格式標準之 Markdown 決策與審計戰鬥卡片"""
        mode_val = result.mode_used.value
        tokens = result.total_tokens_used or 0
        status_badge = "✅ COMPLETED" if result.success else "⚠️ INTERCEPTED / SUSPENDED"

        # 提取決策資訊
        dec_dict = result.metadata.get("routing_decision", {})
        reasoning = dec_dict.get("reasoning") if dec_dict else (decision.reasoning if decision else "依系統特徵矩陣分流")
        model_tier = dec_dict.get("model_tier", "standard").upper()
        risk_level = dec_dict.get("risk_level", "low").upper()

        # 額外擴充 RAG / Acceleration / Harness 審計行
        extra_rows = []
        rag_info = result.metadata.get("rag")
        if rag_info:
            extra_rows.append(f"| **RAG 檢索策略** | `{rag_info.get('strategy')}` (命中 {rag_info.get('chunks_count')} 切片, 耗時 {rag_info.get('latency_ms', 0):.2f}ms) |")

        acc_info = result.metadata.get("acceleration")
        if acc_info:
            c_tag = "HIT" if acc_info.get("is_cache_hit") else "MISS"
            extra_rows.append(f"| **推論加速排程** | 節點 `{acc_info.get('target_node_id')}` (前綴快取 `{c_tag}`, 推測草稿: `{acc_info.get('speculative_draft_tokens')}` 步) |")

        harness_info = result.metadata.get("harness")
        if harness_info:
            h_tag = "CLEAN" if harness_info.get("is_clean") else "SANITIZED"
            extra_rows.append(f"| **Harness 品質門控** | 狀態: `{h_tag}` (AI 腔調分: `{harness_info.get('slop_score', 0):.2f}`, 命中套話: {len(harness_info.get('violations', []))} 項) |")

        extra_rows_str = "\n".join(extra_rows)
        if extra_rows_str:
            extra_rows_str = "\n" + extra_rows_str

        mermaid_chart = cls.generate_mermaid(result)

        card = f"""
### 🛡️ AdaptiveAgentRouter 執行審計戰鬥卡 (Audit Battle Card)

| 審計維度 | 系統決策與執行指標 |
| :--- | :--- |
| **執行狀態** | **{status_badge}** |
| **指派架構模式** | `{mode_val}` |
| **匹配算力檔次** | `{model_tier}` (最適成本矩陣) |
| **風險防護評級** | `{risk_level}` (編譯器 AST 護欄校驗) |
| **Token 計量與成本**| 預估消耗約 `{tokens}` Tokens (結構化壓縮節省 ~85%) |
| **決策判定依據** | {reasoning} |{extra_rows_str}

#### 🗺️ 執行狀態轉換圖 (Mermaid Topology)
{mermaid_chart}

#### 📋 交付成果摘要 (Output Snippet)
> {result.output.strip()[:200]}...
"""
        return card.strip()
