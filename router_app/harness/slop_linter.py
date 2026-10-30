"""
AI 腔調與套話靜態代碼檢查器 (AI Slop & Tone Linter)
設計理念源自 The Agent Harness 與去 AI 味工程原則。

核心痛點：
透過 System Prompt 警告模型「不要有 AI 味、禁止使用廢話套話」，模型依然會頻繁產出
「值得注意的是」、「綜上所述」、「身為一個人工智慧」等虛假敷衍的 AI 口吻。

本模組使用純 Python 靜態正規表示式與語義模式庫，在程式碼層面進行「零容忍」檢查：
  1. 掃描中英文典型 AI 宣示詞、空洞開頭、過渡套話與機械式結尾。
  2. 計算 AI 腔調密度分數 (Slop Score)。
  3. 支援嚴格阻斷模式 (assert_clean) 與自動自然化去噪 (sanitize)。
"""

import re
import time
from typing import List, Tuple

from .types import AISlopAnalysis, AISlopViolationException


class AISlopLinter:
    """去 AI 味靜態代碼檢查器"""

    # 1. 身份宣示與機械式自我介紹
    META_AI_PATTERNS = [
        re.compile(r"(?:身為|作為)?(?:一個)?(?:人工智慧|AI|大型語言模型|智慧助手)(?:語言模型)?[，,。]?", re.I),
        re.compile(r"\b(?:as an ai(?: language model)?|i am an ai|as a large language model)\b[,\.]?", re.I),
    ]

    # 2. 典型空洞開頭與陳腐引言
    HOLLOW_OPENERS = [
        re.compile(r"(?:在當今(?:快節奏|數位化|日新月異|飛速發展)的(?:時代|世界|環境)中)[，,]?", re.I),
        re.compile(r"(?:值得注意的是|不可否認的是|毋庸置疑的是|不難看出的是)[，,]?", re.I),
        re.compile(r"(?:這是一個複雜且多維度(?:的議題|的問題|的挑戰))[，,]?", re.I),
        re.compile(r"\b(?:in today's (?:fast-paced|digital|interconnected) world)\b[,\.]?", re.I),
        re.compile(r"\b(?:it is (?:worth noting|important to remember|crucial to understand) that)\b", re.I),
    ]

    # 3. 泛濫之 AI 標籤過渡詞與成語
    CLICHE_PATTERNS = [
        re.compile(r"(?:綜上所述|總而言之|由此可見|基於上述分析|深入探討|雙刃劍|扮演著舉足輕重的角色)[，,]?", re.I),
        re.compile(r"\b(?:delve into|tapestry of|double-edged sword|pivotal role|testament to|beacon of hope)\b", re.I),
        re.compile(r"\b(?:in conclusion|to sum up|all in all|last but not least)\b[,\.]?", re.I),
    ]

    # 4. 機械式關懷結語
    HOLLOW_CLOSURES = [
        re.compile(r"(?:希望能對您有所幫助|希望以上(?:回答|內容|資訊)對您有幫助|若有任何問題歡迎隨時提問)[。！!]*", re.I),
        re.compile(r"(?:如果您需要進一步的資訊|我將竭誠為您服務|請隨時與我聯繫)[。！!]*", re.I),
        re.compile(r"\b(?:let me know if you (?:have any questions|need anything else)|feel free to ask)\b[!\.]?", re.I),
        re.compile(r"\b(?:hope (?:this|that) helps)\b[!\.]?", re.I),
    ]

    ALL_PATTERNS = META_AI_PATTERNS + HOLLOW_OPENERS + CLICHE_PATTERNS + HOLLOW_CLOSURES

    @classmethod
    def lint(
        cls,
        text: str,
        max_allowed_slop: float = 0.05,
    ) -> AISlopAnalysis:
        """
        對文本進行 AI 腔調靜態掃描
        """
        start_time = time.perf_counter()
        violations: List[str] = []

        # 掃描所有禁忌規則
        for pat in cls.ALL_PATTERNS:
            matches = pat.findall(text)
            for m in matches:
                m_str = m.strip() if isinstance(m, str) else str(m)
                if m_str:
                    violations.append(m_str)

        # 估算總詞數 (以字元數 / 2 估算中英混合詞數)
        total_words = max(1, int(len(text) / 2))
        raw_score = len(violations) / max(1, total_words * 0.1)
        slop_score = min(1.0, round(raw_score, 4))
        is_clean = (slop_score <= max_allowed_slop) and (len(violations) == 0)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        cleaned_text = cls.sanitize(text)

        return AISlopAnalysis(
            slop_score=slop_score,
            is_clean=is_clean,
            violations=violations,
            total_words=total_words,
            cleaned_text=cleaned_text,
            latency_ms=round(latency_ms, 3),
        )

    @classmethod
    def sanitize(cls, text: str) -> str:
        """
        自動自然化去噪：移除或替換低資訊量套話
        """
        working = text
        for pat in cls.ALL_PATTERNS:
            working = pat.sub("", working)

        # 規整殘留的孤立標點與連續換行
        working = re.sub(r"^[，,。；;]\s*", "", working, flags=re.M)
        working = re.sub(r"\n{3,}", "\n\n", working)
        return working.strip()

    @classmethod
    def assert_clean(
        cls,
        text: str,
        max_allowed_slop: float = 0.05,
    ):
        """
        代碼硬門控斷言：若檢測出任何嚴重 AI 腔調，立即拋出異常阻斷流程
        """
        res = cls.lint(text, max_allowed_slop=max_allowed_slop)
        if not res.is_clean:
            raise AISlopViolationException(score=res.slop_score, violations=res.violations)
