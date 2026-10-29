"""
系統提示詞與架構機密洩漏防護器 (System Prompt Leakage Guard - OWASP LLM07)
防止模型在越獄或誘導攻擊下，無意中在輸出中輸出內部 System Prompt、開發者指令、API 密鑰或後端架構設定。
"""

import re
from typing import List, Optional, Tuple


class SystemPromptLeakGuard:
    """系統提示詞洩漏審查與脫敏器"""

    # 常見系統提示詞洩漏特徵樣式
    SYSTEM_LEAK_PATTERNS = [
        r"you\s+are\s+an\s+ai\s+(agent|assistant)\s+designed\s+to",
        r"my\s+instructions\s+are\s+to",
        r"internal\s+system\s+prompt\s*:",
        r"here\s+is\s+my\s+prompt\s*:",
        r"<\s*instructions\s*>[\s\S]*?<\s*\/\s*instructions\s*>",
        r"\[system_instruction\][\s\S]*?\[\/system_instruction\]",
        r"below\s+are\s+the\s+rules\s+given\s+to\s+me\s+by\s+the\s+system",
    ]

    @classmethod
    def inspect_and_sanitize(
        cls,
        output_text: str,
        custom_forbidden_phrases: Optional[List[str]] = None,
    ) -> Tuple[str, bool, List[str]]:
        """
        掃描模型輸出並脫敏系統機密指示
        回傳: (清洗後輸出, 是否檢測到洩漏, 觸發特徵清單)
        """
        if not output_text or not isinstance(output_text, str):
            return output_text, False, []

        leaks = []
        sanitized = output_text

        # 1. 內建洩漏特徵匹配
        for pattern in cls.SYSTEM_LEAK_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                leaks.append(f"檢測到系統指令洩漏樣式: '{pattern}'")
                sanitized = re.sub(pattern, "[INTERNAL_SYSTEM_DIRECTIVE_REDACTED]", sanitized, flags=re.IGNORECASE)

        # 2. 專案自訂機敏片語 (如專有名詞、特定密鑰標籤)
        if custom_forbidden_phrases:
            for phrase in custom_forbidden_phrases:
                if phrase.lower() in sanitized.lower():
                    leaks.append(f"檢測到專屬機敏片語洩漏: '{phrase}'")
                    sanitized = re.sub(re.escape(phrase), "[CONFIDENTIAL_POLICY_REDACTED]", sanitized, flags=re.IGNORECASE)

        has_leak = len(leaks) > 0
        return sanitized, has_leak, leaks
