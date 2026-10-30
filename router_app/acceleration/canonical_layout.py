"""
提示詞確定性標準化佈局格式化器 (Canonical Prompt Layout Formatter)
設計理念源自 SGLang RadixAttention 與 vLLM Automatic Prefix Caching (APC)。

核心原則：
KV Cache 的前綴複用是由 Token Index 0 開始依序比對。若將動態變數（如時間戳、UUID）
放置於 System Prompt 開頭，會直接導致後續數千字的靜態規則與工具定義無法命中快取。
本模組嚴格將 Prompt 解耦為「純靜態前綴（Static Prefix）」與「動態執行後綴（Dynamic Suffix）」，
並確保工具定義與 RAG 上下文之確定性排序（Deterministic Sorting）。
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Union

from .types import CanonicalPromptResult


class CanonicalPromptFormatter:
    """提示詞前綴標準化佈局器"""

    # 常見動態變數樣式 (避免出現在靜態前綴中)
    DYNAMIC_PATTERNS = [
        re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\b"),  # 完整時間戳
        re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),  # UUID
        re.compile(r"\{\{\s*(?:timestamp|datetime|time|request_id|uuid|session_id)\s*\}\}", re.I),
    ]

    @classmethod
    def format(
        cls,
        system_prompt: str,
        tools: Optional[List[Union[Dict[str, Any], str]]] = None,
        rag_context: Optional[Union[List[Dict[str, Any]], str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        user_query: str = "",
        ephemeral_metadata: Optional[Dict[str, Any]] = None,
    ) -> CanonicalPromptResult:
        """
        將散落的各組件組裝為標準化的 Cache-Friendly Prompt
        
        靜態前綴結構 (Static Prefix):
          1. System Directives (靜態系統指令)
          2. Tool Definitions (經字母順序確定性排序之工具規格)
          3. Static Knowledge / RAG Context (若屬於跨請求共享之長篇文檔)
          
        動態後綴結構 (Dynamic Suffix):
          1. Dynamic Context & Ephemeral Metadata (時間戳、使用者 Session ID)
          2. Chat History (多輪對話歷史)
          3. Current User Query (當前使用者最新提問)
        """
        warnings = []
        clean_sys = system_prompt.strip()

        # 檢驗 System Prompt 是否誤植動態變數
        for pat in cls.DYNAMIC_PATTERNS:
            if pat.search(clean_sys):
                warnings.append("System Prompt 中偵測到動態變數或時間戳，將降低底層 KV Cache 跨請求命中率。")
                break

        static_parts = [clean_sys]

        # 1. 確定性工具定義排序 (防止因 dict 順序不同導致 Cache Miss)
        if tools:
            serialized_tools = []
            for t in tools:
                if isinstance(t, dict):
                    serialized_tools.append(json.dumps(t, sort_keys=True, ensure_ascii=False))
                else:
                    serialized_tools.append(str(t).strip())
            serialized_tools.sort()  # 字母排序以保證確定性
            static_parts.append("[AVAILABLE_TOOLS]\n" + "\n---\n".join(serialized_tools))

        # 2. 靜態檢索上下文 (若為固定文檔或 RAG 參考資料)
        if rag_context:
            if isinstance(rag_context, list):
                # 若為 chunk 清單，依 ID 或內容確定性排序
                sorted_chunks = []
                for c in rag_context:
                    if isinstance(c, dict):
                        cid = c.get("chunk_id", "")
                        content = c.get("content", "")
                        sorted_chunks.append(f"[{cid}] {content}".strip())
                    else:
                        sorted_chunks.append(str(c).strip())
                sorted_chunks.sort()
                static_parts.append("[REFERENCE_KNOWLEDGE]\n" + "\n".join(sorted_chunks))
            else:
                static_parts.append(f"[REFERENCE_KNOWLEDGE]\n{str(rag_context).strip()}")

        static_prefix = "\n\n".join(static_parts).strip()
        
        # 計算前綴專屬 SHA-256 指紋
        prefix_hash = hashlib.sha256(static_prefix.encode("utf-8")).hexdigest()[:16]

        # 3. 動態執行後綴組裝
        dynamic_parts = []

        if ephemeral_metadata:
            meta_str = json.dumps(ephemeral_metadata, sort_keys=True, ensure_ascii=False)
            dynamic_parts.append(f"[EXECUTION_METADATA]\n{meta_str}")

        if chat_history:
            history_lines = []
            for msg in chat_history:
                role = msg.get("role", "user").capitalize()
                content = msg.get("content", "")
                history_lines.append(f"{role}: {content}")
            dynamic_parts.append("[CONVERSATION_HISTORY]\n" + "\n".join(history_lines))

        if user_query:
            dynamic_parts.append(f"[CURRENT_QUERY]\n{user_query.strip()}")

        dynamic_suffix = "\n\n".join(dynamic_parts).strip()

        canonical_prompt = f"{static_prefix}\n\n{dynamic_suffix}" if dynamic_suffix else static_prefix
        
        # 粗估 Token 數量 (字元數 / 3.6 經驗值)
        estimated_tokens = max(1, int(len(canonical_prompt) / 3.6))

        return CanonicalPromptResult(
            canonical_prompt=canonical_prompt,
            static_prefix=static_prefix,
            dynamic_suffix=dynamic_suffix,
            prefix_hash=prefix_hash,
            estimated_tokens=estimated_tokens,
            is_cache_friendly=(len(warnings) == 0),
            sanitization_warnings=warnings,
        )
