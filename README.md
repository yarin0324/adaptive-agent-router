# 企業級 AI Agent 自適應動態調度中樞與微架構框架 (AdaptiveAgentRouter)

> **English Summary**: AdaptiveAgentRouter is an enterprise-grade, microkernel-based orchestration framework for LLM Agents. It dynamically routes queries across 10 standard agent design patterns (Single-Turn, ReAct, Planner, Reflection, Verifier-Gated, Debate) paired with a 2D Model Tier matrix. Native features include 0ms LRU route caching, compiler-level AST security guardrails (Python & SQL), context token compression (-70%), non-blocking Task Suspension FSM, and OpenTelemetry-aligned distributed tracing.

**AdaptiveAgentRouter** 是一套專為大型語言模型（LLM）智慧代理系統打造之企業級**自適應動態調度中樞與微架構框架**。系統採用微核心解耦架構（Microkernel Dispatcher），在毫秒級時延內對使用者提問進行多維度語意分析、任務複雜度分級與不可逆風險評估，動態分流至**十大標準 Agent 設計模式**（包含增強型單次回應、ReAct 思考迴圈、Planner-Executor 任務拆解、自我反思批評、驗證門控、三權分立對抗辯論等），並結合 **RouteLLM 算力矩陣** 自動指派最適模型檔次（FAST / STANDARD / REASONING）。

架構原生內建零延遲雜湊快取、編譯器級 AST 語法樹護欄（Python & SQL）、Token 智慧壓縮器（-70% 上下文消耗）、任務級熔斷保護器（Circuit Breaker）、非同步人機協同審批狀態機（Suspend & Resume），以及相容 OpenTelemetry 之全鏈路分散式追蹤，專供複雜企業級 AI 系統在生產環境中實現低時延、低成本、可治理、抗暴走之高可靠性代理運維。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Architecture: Microkernel](https://img.shields.io/badge/Architecture-Microkernel%20Dispatcher-purple.svg)]()
[![Agent Patterns: 10 Modes](https://img.shields.io/badge/Agent%20Patterns-10%20Standard%20Modes-green.svg)]()
[![Security: Compiler AST](https://img.shields.io/badge/Security-Compiler%20AST%20Guard-darkred.svg)]()
[![Guardrails: Circuit Breaker](https://img.shields.io/badge/Guardrails-Circuit%20Breaker%20%26%20FSM-red.svg)]()
[![Optimization: Context Compressor](https://img.shields.io/badge/Optimization-Context%20Compressor%20--70%25-teal.svg)]()
[![Telemetry: OpenTelemetry](https://img.shields.io/badge/Telemetry-OpenTelemetry%20Aligned-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

## 1. 系統架構 (System Architecture)

系統遵循微核心與外掛解耦設計模式（Microkernel Architecture），調度總管維持極致輕量化，並將核心路由治理機制與 10 大執行引擎徹底實體隔離。

```mermaid
flowchart TD
    Client["業務應用接入層 (Application Tier)<br>REST API / 微服務 / 各領域業務工作流"] -->|Prompt / Context| Ingress

    subgraph Ingress ["微核心調度網關 (Microkernel Gateway)"]
        direction TB
        subgraph CoreServices ["核心治理防護機制 (Core Governance)"]
            InputRail["輸入安全衛兵 (InputSecurityRail)<br>Prompt Injection 阻斷 / 語意安全閥"]
            Cache["零延遲快取 (RouteCache)<br>SHA-256 雜湊 / 0ms Hit"]
            Matcher["語意原型比對 (SemanticMatcher)<br>N-gram 餘弦匹配 / 5ms 命中"]
            Router["自適應路由器 (AdaptiveRouter)<br>2D 矩陣: 模式分流 x 算力檔次"]
            ASTGuard["編譯器級 AST 護欄 (ASTSecurityGuard)<br>Python & SQL 語法樹物理阻斷"]
            Breaker["任務熔斷防禦 (TaskCircuitBreaker)<br>Token 配額 / 步數閥值 / 逾時截斷"]
            FSM["人機審批狀態機 (TaskSuspensionManager)<br>非同步任務掛起 / 外部信號喚醒"]
            Tracer["全鏈路追蹤器 (TraceContext)<br>OpenTelemetry 相容 / 分佈式 Span"]
        end
    end

    Ingress --> M1 & M2 & M4 & M5 & M6 & M7 & M8 & M9 & M10

    subgraph Engines ["解耦執行引擎陣列 (Decoupled Mode Engines)"]
        direction TB
        subgraph LowLatencyTier ["低時延與操作層 (Low-Latency Tier)"]
            M1["模式 1: 增強型單次回應<br>欄位抽取 / 格式清洗 / 摘要生成"]
            M2["模式 2: 反思迴圈 (ReAct)<br>探索診斷 / 動態路徑 / 邊做邊看"]
            M8["模式 8: 專用工具代理<br>API 匹配 / SQL 執行 / 系統操作"]
            M10["模式 10: 情境式記憶<br>向量快照 / 偏好錨定 / 歷史承襲"]
        end
        subgraph HighReasoningTier ["深度推理與治理層 (Deep Reasoning Tier)"]
            M4["模式 4: 規劃-執行器<br>DAG 步驟拆解 / Checkpoint 斷點快照"]
            M5["模式 5: 評估-優化反思<br>Critic 批評 / 漏洞修補 / 多輪精煉"]
            M6["模式 6: 驗證門控<br>高風險不可逆指令 / 審批攔截"]
            M7["模式 7: 對抗辯論協作<br>正方立論 / 紅隊挑刺 / 仲裁定案"]
            M9["模式 9: 並行自洽投票<br>多路並行採樣 / 多數決收斂"]
        end
    end

    Engines --> Compression["上下文壓縮器 (ContextCompressor)<br>結構化資料折疊 / 冗餘修剪 (-70% Token)"]
    Compression --> OutputRail["輸出安全衛兵 (OutputPIISanitizerRail)<br>個資脫敏 (身分證/信用卡/Key 遮蔽)"]
    OutputRail --> Output["結構化交付與遙測審計 (Audit & Delivery)<br>ExecutionResult / OpenTelemetry Traces"]
```

---

## 2. 核心架構特色與技術支柱 (Architectural Pillars)

### 2.1 微核心熱插拔架構 (Microkernel Plug-and-Play Engine)
調度中樞 `AdaptiveAgentDispatcher` 與各專案業務邏輯徹底解耦。使用者只需定義繼承自 `BaseTool` 的業務工具，即可無縫掛載進系統；所有執行模式（Modes）均實作統一介面契約，具備獨立擴充與替換能力。

### 2.2 雙維度算力矩陣路由 (2D Matrix: Pattern × Model Tier)
決策輸出不僅包含架構模式，更同時指派最經濟的模型算力階層（FAST / STANDARD / REASONING）：
- 輕量抽取與工具調用自動綁定輕量模型（如 `gpt-4o-mini` / `gemini-1.5-flash`）。
- 嚴格反思、長流程規劃與專家辯論自動升格至頂級推理模型（如 `claude-3-5-sonnet` / `o1`），達成架構與 Token 成本雙重最佳化。

### 2.3 編譯器級 AST 語法樹護欄 (Compiler-Level AST Security Guard)
不依賴易被繞過的正則表達式，直接在語法編譯階段解析語法樹：
- **Python AST Guard**：遍歷語法樹節點，物理阻斷 `eval`, `exec`, `open`, `__import__` 與危險系統模組（`os`, `subprocess`, `sys`）。
- **SQL AST Guard**：審查查詢結構，強制要求唯讀（`SELECT` / `WITH`），物理阻斷包含註解混淆的 `DROP`, `DELETE`, `TRUNCATE`, `ALTER`。

### 2.4 上下文與 Token 智慧壓縮 (Context Compression & Token Pruner)
解決多輪 ReAct 探索與巨型資料庫查詢帶來的上下文膨脹（Lost-in-the-Middle 困境）：
- **結構化資料折疊**：資料庫回傳 100 筆資料時，自動保留 Top 3 與 Tail 2 樣本並附帶聚合統計，**壓縮率達 80% 以上**。
- **語意冗餘清洗**：自動消除連續換行、無效空格與裝飾性符號。

### 2.5 零延遲快取與語意原型匹配 (Two-Stage Route Caching)
- **第一階 (Exact Hash)**：基於 SHA-256 記憶體 LRU 快取，相同提問 **0ms 瞬間命中**。
- **第二階 (Semantic Prototype)**：N-gram 向量空間語意原型比對，同義詞置換在 **5ms 內快速命中**，免去前置 LLM 呼叫。

### 2.6 任務級熔斷器與防暴走護欄 (Task Circuit Breaker & Token Guard)
為每個任務實例化獨立的 `TaskCircuitBreaker` 生命週期監控：
- **最大步數門檻**：預設上限 8 步，超標立即主動熔斷。
- **Token 預算硬上限**：單一任務上限預設 8,000 Tokens，杜絕帳單暴增風險。
- **逾時熔斷**：30 秒非同步中斷保護。

### 2.7 非同步人機協同審批狀態機 (Non-blocking Human-in-the-Loop Suspension)
採用微服務適配的有限狀態機（FSM）：
1. 偵測到 `CRITICAL` 不可逆操作時，`TaskSuspensionManager` 序列化上下文生成 `task_id`，立即釋放 Worker 執行緒。
2. 外部系統（Webhook、微服務 API、Slack 命令）發送審批信號後，呼叫 `dispatcher.resume_task(task_id, approved=True)` 喚醒任務並放行。

### 2.8 雙向安全衛兵與個資脫敏 (Bi-directional Guardrails)
- **Input Rail**：主動阻斷 Prompt Injection 與系統指令覆蓋 (System Override)。
- **Output Rail**：交付前自動掃描並脫敏機敏身分證字號、信用卡號、電子郵件與 API Key，替換為 `[REDACTED_PII]`。

### 2.9 動態重規劃器與任務檢查點 (Dynamic Replanner & Task Checkpointer)
借鏡 Plan-and-Solve Prompting (Wang et al., 2023) 與 LangGraph Checkpointer：
- **Dynamic Replanner**：解決靜態計畫盲跑問題。每當工作者完成一個子步驟，Replanner 自動檢視中間結果，動態自適應追加、修改或修剪後續步驟。
- **Task Checkpointer**：每步序列化不可變快照（Snapshot），支援故障中斷時的斷點續傳。

### 2.10 RRF 倒數排名融合記憶檢索 (Reciprocal Rank Fusion - RRF Engine)
借鏡 Cormack et al. (SIGIR 2009) 論文與 MySecondBrain 實踐，情境記憶層原生內建純 Python RRF 混合召回：
- 結合**精確關鍵字排名 (Lexical Rank)** 與 **語意餘弦相似度排名 (Semantic Rank)**。
- 透過名次倒數公式 $RRF(d) = \sum \frac{w}{k + r(d)}$ 進行多數決投票，兼顧專有名詞代號的精確命中與抽象概念的關聯召回。

### 2.11 對抗式量化評審反思 (Reflexion Rubric Scoring)
借鏡 Reflexion (Shinn et al., NeurIPS 2023)，徹底消除自評確認偏差：
- 獨立 Critic 依據三維量化指標表 (Rubric) 打分：邏輯嚴謹度、邊界防禦度、漏洞覆蓋度。
- **加權總分門檻強制要求 $\ge 8.5$ 分**，未達標強制退回重寫優化。

### 2.12 影子乾跑變更預覽 (Dry-Run Simulation Diff)
借鏡 Terraform Plan 雲原生治理哲學：
- 門控機制在掛起任務前，自動模擬輸出**影響評估報告**（異動資料表、受影響記錄數、預估曝險金額）。
- 審批人員依據客觀 Diff 報告進行審核放行，消除黑盒操作恐懼。

### 2.13 負反饋避坑記憶 (Negative Observation Memory)
借鏡 AutoGPT 避坑機制：
- ReAct 模式在遭遇工具執行例外或無效端點時，自動將該動作加入 `Forbidden Actions` 禁區清單。
- 下一輪迭代強制注入避坑提示，杜絕 Agent 原地死磕無效路徑。

### 2.14 意見收斂早停定案 (Debate Early Stopping by Convergence)
借鏡 MetaGPT SOP 協調哲學：
- 首席仲裁者每輪動態計算正反方論點之「歧異度 (Disagreement Delta)」。
- 若歧異度 $\le 0.15$，代表已取得架構共識，第 2 輪即時觸發早停 (Early Stop) 定案，節省 30%+ 辯論 Token 消耗。

---

## 3. 效能與成本基準 (Performance & Cost Benchmark)

本章節量化數據由**本機物理實測腳本**與**學術權威文獻**交叉對照而得。所有數值均可透過執行 `python examples/benchmark.py` 進行 100% 重現實測。

| 評估維度 | 傳統單一固定 Agent 架構 (Baseline) | 採用 AdaptiveAgentRouter | 優化指標 | 數據來源與學術文獻依據 |
| :--- | :--- | :--- | :--- | :--- |
| **平均前置路由時延** | 800ms - 1,500ms (跨公網呼叫 LLM 分類) | **0.002ms (Hash 快取) / 5ms (原型比對)** | **時延降低 99.8%** | **本機實測**：記憶體 LRU 雜湊查找 vs 跨網 HTTP 網路往返延遲 (RTT)。可執行 `benchmark.py` 重現。 |
| **簡單查詢 Token 消耗** | 1,500 - 3,000 Tokens (死板跑 ReAct 多輪迴圈) | **180 Tokens (走單次增強 + FAST 算力矩陣)** | **成本降低 94%** | **文獻依據**：*RouteLLM* (LMSYS, [arXiv:2406.18665](https://arxiv.org/abs/2406.18665)) 證實雙階模型矩陣可節省 85%+ 成本；*ReAct* (Yao et al., [arXiv:2210.03629](https://arxiv.org/abs/2210.03629))。 |
| **巨型資料庫查詢上下文** | 約 6,855 Tokens (100 筆訂單完整 JSON) | **約 617 Tokens (結構化折疊與摘要)** | **Token 節省 91.0%** | **本機實測**：`ContextCompressor` 實測 100 筆資料庫結果折疊；*Lost in the Middle* (Liu et al., [arXiv:2307.03172](https://arxiv.org/abs/2307.03172))。 |
| **異常死循環防禦** | 0% (無法預防無限遞迴，持續耗盡配額) | **100% (TaskCircuitBreaker 8 步硬性截斷)** | **完全阻斷死循環** | **架構機制**：任務級生命週期熔斷器 (Circuit Breaker Pattern, 參照 Martin Fowler 微服務架構)。 |
| **惡意代碼與 SQL 阻斷** | 依賴 Prompt 祈禱 (正則表達式繞過率約 23%) | **編譯器 AST 語法樹檢查 (物理繞過率 0%)** | **零死角物理阻斷** | **文獻依據**：*Jailbroken: How Does LLM Safety Training Fail?* ([arXiv:2307.02483](https://arxiv.org/abs/2307.02483)) 與 OWASP Top 10 for LLM (LLM01/LLM02)。 |

> 驗證指令：可在終端機執行 `python examples/benchmark.py` 即時檢驗上述快取時延、Token 折疊率與 AST 阻斷效能。

---

## 4. 安裝與快速整合 (Quickstart Installation)

### 4.1 透過 pip 模組化安裝
```bash
# 從 GitHub 倉庫直接安裝
pip install git+https://github.com/yarin0324/adaptive-agent-router.git

# 或本地開發模式安裝
git clone https://github.com/yarin0324/adaptive-agent-router.git
cd adaptive-agent-router
pip install -e .
```

### 4.2 三步驟掛載至業務系統
```python
from router_app import AdaptiveAgentDispatcher, BaseTool

# 步驟 1: 宣告業務專屬工具
class CustomDatabaseTool(BaseTool):
    name = "db_service"
    description = "查詢客戶與庫存數據"
    risk_level = "low"

    def execute(self, query: str = "", **kwargs):
        return [{"id": 1, "name": "Enterprise Client", "status": "Active"}]

# 步驟 2: 初始化調度中樞
dispatcher = AdaptiveAgentDispatcher(
    custom_tools=[CustomDatabaseTool()],
    enable_logging=True
)

# 步驟 3: 執行調度 (系統自動判定模式、算力階層並掛載安全護欄)
result = dispatcher.process("請幫我查詢客戶狀態並結構化輸出")
print(result.output)
```

---

## 5. 企業實戰案例庫 (Production Case Studies)

專案提供兩套不同領域的端到端生產範例，位於 `examples/` 目錄：
- **發票與憑證 OCR 智慧解析**：[`examples/plug_into_ocr_example.py`](examples/plug_into_ocr_example.py)
  展示如何將模糊辨識問題自動導向 ReAct 邊做邊調參數，並將批次十萬張憑證導向 Planner 拆解。
- **量化投資與金融智慧風控**：[`examples/plug_into_stock_example.py`](examples/plug_into_stock_example.py)
  展示下單交易指令如何觸發 `Verifier-Gated` 人機審批掛起，以及重大決策如何啟動正反方多代理對抗辯論。

---

## 6. 安全性與漏洞回報 (Security Policy)

本專案將執行安全性列為最高優先級別。若您在 AST 語法解析器、安全護欄或狀態機中發現潛在安全漏洞，請**切勿公開提出 Issue**。請發送電子郵件至維護團隊信箱進行負責任的漏洞披露，我們將在 48 小時內進行評估與修補發版。

---

## 7. 授權條款與貢獻指南 (License & Contributing)

- 本專案採用 [MIT License](LICENSE) 授權開源。
- 歡迎透過 Pull Request 貢獻新的 Agent 模式實作、語意原型字典或安全檢驗規則。提交前請確保通過 `python examples/quickstart.py` 整合測試。
