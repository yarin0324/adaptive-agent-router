"""
間接提示詞注入防護器 (Indirect Prompt Injection Sanitizer - OWASP LLM01)
防範第三方檢索內容 (RAG 上下文、資料庫記錄、OCR 辨識文本、網頁爬蟲) 夾帶惡意指令欺騙 Agent。
包含零寬字元隱寫清除、隱藏 HTML 註解剝除、特殊 Token 標籤中和與 Markdown 外部滲透連結阻斷。
"""

import re
from typing import Any, Dict, List, Tuple, Union


class IndirectInjectionSanitizer:
    """間接提示詞注入審查與中和清洗器"""

    # 1. 隱藏指令與特殊控制 Token 樣式
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
        r"disregard\s+(all\s+)?guidelines?",
        r"system\s*:\s*override",
        r"\[\s*system\s*(override)?\s*\]",
        r"new\s+instructions?:",
        r"<\s*\|\s*im_start\s*\|>",
        r"<\s*\|\s*im_end\s*\|>",
        r"\[\s*instruction\s*\]",
        r"human\s*:\s*",
        r"assistant\s*:\s*",
    ]

    # 2. 零寬字元 (Zero-width characters)
    ZERO_WIDTH_CHARS = r"[\u200b\u200c\u200d\u200e\u200f\ufeff]"

    # 3. 隱藏 HTML 註解與無效樣式標籤
    HIDDEN_HTML_PATTERN = r"<!--[\s\S]*?-->|<[^>]*style\s*=\s*['\"][^'\"]*display\s*:\s*none[^'\"]*['\"][^>]*>[\s\S]*?<\/[^>]+>"

    # 4. 惡意資料外洩 Markdown 連結 (如 ![exfil](https://attacker.com?leak=))
    EXFILTRATION_IMG_PATTERN = r"!\[.*?\]\((https?:\/\/[^\s\)]+)\)"

    @classmethod
    def sanitize_text(cls, text: str) -> Tuple[str, bool, List[str]]:
        """
        清洗單一檢索字串
        回傳: (清洗後文本, 是否偵測到威脅, 觸發之威脅項目)
        """
        if not text or not isinstance(text, str):
            return "" if text is None else str(text), False, []

        threats = []
        sanitized = text

        # A. 剝除零寬字元隱寫
        if re.search(cls.ZERO_WIDTH_CHARS, sanitized):
            threats.append("偵測並清除零寬字元隱寫 (Zero-Width Steganography)")
            sanitized = re.sub(cls.ZERO_WIDTH_CHARS, "", sanitized)

        # B. 清理 HTML 隱藏指令
        if re.search(cls.HIDDEN_HTML_PATTERN, sanitized, re.IGNORECASE):
            threats.append("偵測並剝除隱藏 HTML 註解/樣式注入 (Hidden HTML Comments)")
            sanitized = re.sub(cls.HIDDEN_HTML_PATTERN, "[REMOVED_HIDDEN_HTML]", sanitized, flags=re.IGNORECASE)

        # C. 標記與中和指令覆蓋語句
        for pattern in cls.INJECTION_PATTERNS:
            matches = re.findall(pattern, sanitized, re.IGNORECASE)
            if matches:
                threats.append(f"中和間接指令覆蓋語句: '{pattern}'")
                sanitized = re.sub(pattern, "[NEUTRALIZED_COMMAND]", sanitized, flags=re.IGNORECASE)

        # D. 中和可疑圖片滲透外洩
        if re.search(cls.EXFILTRATION_IMG_PATTERN, sanitized):
            threats.append("中和潛在 Markdown 資料外洩圖片標籤")
            sanitized = re.sub(cls.EXFILTRATION_IMG_PATTERN, "[REMOVED_EXFIL_LINK]", sanitized)

        is_threat = len(threats) > 0
        return sanitized, is_threat, threats

    @classmethod
    def sanitize_payload(cls, payload: Any) -> Tuple[Any, bool, List[str]]:
        """遞迴清洗各類結構化資料 (List / Dict)"""
        if isinstance(payload, str):
            return cls.sanitize_text(payload)

        elif isinstance(payload, dict):
            new_dict = {}
            all_threats = []
            has_threat = False
            for k, v in payload.items():
                clean_v, thr, t_list = cls.sanitize_payload(v)
                new_dict[k] = clean_v
                if thr:
                    has_threat = True
                    all_threats.extend(t_list)
            return new_dict, has_threat, list(set(all_threats))

        elif isinstance(payload, list):
            new_list = []
            all_threats = []
            has_threat = False
            for item in payload:
                clean_item, thr, t_list = cls.sanitize_payload(item)
                new_list.append(clean_item)
                if thr:
                    has_threat = True
                    all_threats.extend(t_list)
            return new_list, has_threat, list(set(all_threats))

        return payload, False, []

    @classmethod
    def sanitize_data(cls, data: Any) -> Any:
        """遞迴清洗任意結構資料 (dict, list, str)，直接回傳乾淨資料"""
        clean_res, _, _ = cls.sanitize_payload(data)
        return clean_res
