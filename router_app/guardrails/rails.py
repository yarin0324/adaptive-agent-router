"""
雙軌安全衛兵 (Bi-directional Guardrails: Input & Output Rails)
借鏡自 Guardrails AI / NeMo Guardrails
- Input Rail: 阻斷 Prompt Injection、指令覆蓋 (System Override) 與惡意指令
- Output Rail: 自動脫敏機敏個人資料 (PII Masking: 身分證、信用卡、電話、金鑰)
"""

import re
from typing import Tuple


class InputSecurityRail:
    """輸入端安全過濾軌道"""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+(all\s+)?guidelines",
        r"system\s*:\s*override",
        r"jailbreak",
        r"bypass\s+security\s+check",
    ]

    @classmethod
    def validate_prompt(cls, prompt: str) -> Tuple[bool, str]:
        """驗證使用者輸入，若發現 Injection 嘗試則返回 False"""
        p_lower = prompt.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, p_lower):
                return False, f"檢測到潛在的 Prompt Injection 攻擊模式: '{pattern}'"
        return True, "Input validation passed."


class OutputPIISanitizerRail:
    """輸出端個資脫敏過濾軌道"""

    # 台灣身分證正規表達式: 1 英文大寫 + 1 或 2 + 8 數字
    TW_ID_PATTERN = r"\b[A-Z][12]\d{8}\b"
    # 信用卡號 (16 碼含分隔符)
    CREDIT_CARD_PATTERN = r"\b(?:\d{4}[-\s]?){3}\d{4}\b"
    # 敏感 API Key (如 sk-..., ghp_..., AIza...)
    API_KEY_PATTERN = r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9-_]{35})\b"
    # 電子郵件
    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"

    @classmethod
    def sanitize(cls, text: str) -> str:
        """對輸出內容執行自動脫敏 (Masking)"""
        sanitized = re.sub(cls.TW_ID_PATTERN, "[REDACTED_ID]", text)
        sanitized = re.sub(cls.CREDIT_CARD_PATTERN, "[REDACTED_CARD]", sanitized)
        sanitized = re.sub(cls.API_KEY_PATTERN, "[REDACTED_API_KEY]", sanitized)
        sanitized = re.sub(cls.EMAIL_PATTERN, "[REDACTED_EMAIL]", sanitized)
        return sanitized
